"""Durable loopback benchmark observations, without persisting project prompts/source.

Runs execute in a server-owned worker rather than an HTTP response connection.
UI navigation/disconnect never retries or interrupts an already approved run.
Stored records may contain sensitive *model responses* and are local, private,
bounded JSON; no secrets, auth tokens, source snapshots or CLI argv are stored.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
import uuid

RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
MAX_RECORDS = 30
MAX_SAVED_BYTES = 1024 * 1024


def _utc():
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else Path.home() / ".daeloryn" / "benchmark-runs"
        self.guard = threading.RLock()
        self.active = None
        self.stop_events = {}

    def _ensure_dir(self):
        parent = self.directory.parent
        if parent.is_symlink() or self.directory.is_symlink():
            raise ValueError("benchmark storage cannot use symlink directories")
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.directory.mkdir(mode=0o700, exist_ok=True)
        if os.name == "posix":
            # Existing directory needs to be protected before writing transcripts.
            self.directory.chmod(0o700)

    def _path(self, run_id):
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise ValueError("invalid run id")
        return self.directory / (run_id + ".json")

    def _save(self, record):
        self._ensure_dir()
        raw = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_SAVED_BYTES:
            raise ValueError("benchmark response exceeds local persistence limit")
        target = self._path(record["run_id"])
        tmp = self.directory / (record["run_id"] + "." + uuid.uuid4().hex + ".tmp")
        try:
            fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
        finally:
            if tmp.exists():
                tmp.unlink()

    def _read(self, run_id):
        path = self._path(run_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SAVED_BYTES:
            raise FileNotFoundError("benchmark run unavailable")
        result = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict) or result.get("run_id") != run_id:
            raise ValueError("invalid persisted benchmark receipt")
        if result.get("status") in ("running", "stopping") and self.active != run_id:
            result["status"] = "interrupted"
            result["error"] = ("The local benchmark service restarted during this run. "
                               "Remote provider outcome is unknown; never auto-retry.")
            result["updated_at"] = _utc()
            self._save(result)
        return result

    def get(self, run_id):
        with self.guard:
            return self._read(run_id)

    def list(self):
        with self.guard:
            if not self.directory.is_dir():
                return []
            paths = sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if len(paths) > MAX_RECORDS:
                # Bounded, predictable storage; do not silently discard runs.
                paths = paths[:MAX_RECORDS]
            rows = []
            for path in paths:
                if path.is_symlink() or not RUN_ID.fullmatch(path.stem):
                    continue
                receipt = self._read(path.stem)
                # No transcripts in list payload; individual run retrieval is explicit.
                rows.append({k: receipt.get(k) for k in
                            ("run_id", "status", "repository", "mode", "model", "agent",
                             "created_at", "updated_at", "error")})
            return rows

    def stop(self, run_id):
        with self.guard:
            record = self._read(run_id)
            if record['status'] in ('stopped', 'stopping'):
                return {'run_id':run_id,'status':record['status']}
            if record['status'] != 'running' or self.active != run_id:
                raise ValueError('only an active benchmark can be stopped')
            event = self.stop_events.get(run_id)
            if event is None:
                raise ValueError('run is no longer active')
            # Cooperative stop; up to two in-flight Copilot processes can be
            # terminated locally, but the provider-side outcome may be unknown.
            event.set()
            record['status'] = 'stopping'
            record['error'] = ('Stop requested. In-flight Copilot calls are being terminated locally; '
                               'provider-side outcome may be unknown.')
            record['updated_at'] = _utc()
            self._save(record)
            return {'run_id':run_id,'status':'stopping'}

    def delete(self, run_id):
        with self.guard:
            record = self._read(run_id)
            if run_id == self.active or record['status'] in ('running', 'stopping'):
                raise RuntimeError('Stop the running benchmark and wait for it to finish before deleting')
            target = self._path(run_id)
            if target.is_symlink():
                raise ValueError('unsafe run record path')
            target.unlink()
            return {'run_id':run_id,'deleted':True}

    def start(self, prepared, approved_digest, runner):
        if prepared.get("sha256") != approved_digest:
            raise PermissionError("benchmark approval changed; prepare again")
        with self.guard:
            if self.active is not None:
                raise RuntimeError("a benchmark is already running")
            self._ensure_dir()
            if len(list(self.directory.glob("*.json"))) >= MAX_RECORDS:
                raise ValueError("benchmark history is full (30 runs); archive old local receipts first")
            run_id = uuid.uuid4().hex
            record = {
                "run_id": run_id, "status": "running", "created_at": _utc(),
                "updated_at": _utc(), "repository": prepared["repository"],
                "mode": prepared["mode"], "model": prepared["model"],
                "agent": prepared["agent"], "source_sha256": prepared["source_sha256"],
                "approved_sha256": approved_digest,
                "total_model_calls": prepared["total_model_calls"],
                "arms": {arm: {"status": "pending", "completed_batches": 0,
                               "total_batches": prepared[arm]["batch_count"],
                               "reply": "", "failure": None}
                         for arm in ("baseline", "daeloryn")},
                "result": None, "error": None,
                "verified_trial": False
            }
            self._save(record)
            self.active = run_id
            cancel_event = threading.Event()
            self.stop_events[run_id] = cancel_event

        def work():
            try:
                def progress(event):
                    arm = event.get("arm")
                    if arm not in ("baseline", "daeloryn"):
                        return
                    with self.guard:
                        row = record["arms"][arm]
                        event_type = event.get("type")
                        if event_type == "arm_started":
                            row["status"] = "running"
                        elif event_type == "progress":
                            row["completed_batches"] = event.get("completed", row["completed_batches"])
                            row["total_batches"] = event.get("total", row["total_batches"])
                        elif event_type == "batch_reply" and isinstance(event.get("reply"), str):
                            # Preserve completed batches independently of final provider result.
                            piece = event["reply"][:65536]
                            next_reply = row["reply"] + ("\n\n" if row["reply"] else "") + \
                                ("Batch %s:\n" % event.get("batch", "?")) + piece
                            row["reply"] = (next_reply[:200000] +
                                            ("\n[Transcript truncated for local storage]" if len(next_reply) > 200000 else ""))
                        elif event_type == "arm_finished":
                            row["status"] = event.get("status", "partial")
                        record["updated_at"] = _utc()
                        self._save(record)

                result = runner(prepared, approved_digest, progress=progress,
                                cancel_event=cancel_event, parallelism=2)
                with self.guard:
                    # Avoid duplicating large model transcripts in the receipt.
                    record["result"] = {
                        **result,
                        "arms": {key: {
                            **value, "review": {
                                **value.get("review", {}), "reply": ""
                            }
                        } for key, value in result.get("arms", {}).items()}
                    }
                    record["status"] = "stopped" if cancel_event.is_set() else result["status"]
                    for arm, outcome in result.get("arms", {}).items():
                        if arm in record["arms"]:
                            record["arms"][arm].update({
                                "status": outcome.get("status", "partial"),
                                "completed_batches": outcome.get("completed_batches", 0),
                                "total_batches": outcome.get("total_batches", 0),
                                "failure": outcome.get("failure"),
                                "reply": (outcome.get("review", {}).get("reply", "") or
                                          record["arms"][arm]["reply"])[:200000]
                            })
                    if cancel_event.is_set():
                        record["error"] = ("Stopped by user. Pending batches were not invoked. "
                                           "In-flight provider outcomes may be unknown; no auto-retry.")
                    elif result["status"] != "completed":
                        record["error"] = ("Partial benchmark: a provider batch failed, timed out "
                                           "or reached a review budget. See per-arm failure; do not auto-retry.")
                    record["updated_at"] = _utc()
                    self._save(record)
            except Exception as exc:
                with self.guard:
                    record["status"] = "stopped" if cancel_event.is_set() else "failed"
                    # Avoid serializing arbitrary provider exception text / secrets.
                    record["error"] = ("Stop requested; provider outcome may be unknown."
                                       if cancel_event.is_set() else
                                       "Benchmark worker failed (" + type(exc).__name__ +
                                       "). External provider outcome may be unknown; do not auto-retry.")
                    record["updated_at"] = _utc()
                    try:
                        self._save(record)
                    except OSError:
                        pass
            finally:
                with self.guard:
                    if self.active == run_id:
                        self.active = None
                    self.stop_events.pop(run_id, None)

        thread = threading.Thread(target=work, daemon=True, name="benchmark-" + run_id[:8])
        thread.start()
        return {"run_id": run_id, "status": "running", "created_at": record["created_at"]}
