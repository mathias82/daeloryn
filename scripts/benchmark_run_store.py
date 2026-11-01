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
from paired_evidence_evaluator import evaluate as evaluate_evidence, source_from_prepared, source_from_context, context_digest

RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
MAX_RECORDS = 30
MAX_SAVED_BYTES = 4 * 1024 * 1024


def _utc():
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else Path.home() / ".daeloryn" / "benchmark-runs"
        self.guard = threading.RLock()
        self.active = None
        self.active_record = None
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

    def comparison_summaries(self):
        """Sanitized local A/B observations for the Benchmarks comparison table."""
        with self.guard:
            results = []
            for row in self.list():
                detail = self._read(row["run_id"])
                comparison = detail.get("comparison")
                if not isinstance(comparison, dict):
                    continue
                scores = comparison.get("arms", {})
                results.append({
                    "run_id": row["run_id"],
                    "repository": row["repository"],
                    "mode": row["mode"],
                    "model": row["model"],
                    "agent": row["agent"],
                    "status": row["status"],
                    "evaluation_status": comparison["status"],
                    "provisional_evidence_lead": comparison["provisional_evidence_lead"],
                    "baseline_score": scores["baseline"]["evidence_traceability_score"],
                    "daeloryn_score": scores["daeloryn"]["evidence_traceability_score"],
                    "verified_winner": None,
                })
            return results

    def evaluate_saved(self, run_id, context):
        """Post-hoc offline evaluation of legacy run; fail closed on source drift."""
        with self.guard:
            record = self._read(run_id)
            if record["status"] in ("running", "stopping") or run_id == self.active:
                raise RuntimeError("wait for both model arms to finish")
            if context_digest(context) != record.get("source_sha256"):
                raise PermissionError("approved source snapshot changed; cannot evaluate old replies against different code")
            source = source_from_context(context)
            if not source:
                raise ValueError("no eligible original source for comparison")
            comparison = evaluate_evidence(record, source)
            record["comparison"] = comparison
            record["updated_at"] = _utc()
            self._save(record)
            return {"run_id": run_id, "comparison": comparison}

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
            if self.active_record is not None and self.active_record.get('run_id') == run_id:
                self.active_record['status'] = 'stopping'
            record['error'] = ('Stop requested. In-flight Copilot calls are being terminated locally; '
                               'provider-side outcome may be unknown.')
            record['updated_at'] = _utc()
            if self.active_record is not None and self.active_record.get('run_id') == run_id:
                self.active_record['error'] = record['error']
                self.active_record['updated_at'] = record['updated_at']
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

    def resume(self, run_id, prepared, approved_digest, runner, acknowledge_unknown=False):
        """Explicitly approved continuation of the SAME run, never new baseline calls."""
        with self.guard:
            record=self._read(run_id)
            if self.active is not None:
                raise RuntimeError('another benchmark is still running')
            if record.get('status') not in ('partial','failed','stopped','interrupted'):
                raise ValueError('only incomplete terminal runs can be resumed')
            if record.get('approved_sha256') != approved_digest or prepared.get('sha256') != approved_digest:
                raise PermissionError('project, source, model, agent or approval changed')
            if (record.get('source_sha256') != prepared.get('source_sha256') or
                any(record.get(k) != prepared.get(k) for k in ('repository','mode','model','agent'))):
                raise PermissionError('benchmark identity changed')
            if not all(isinstance(record.get('arms',{}).get(arm,{}).get('batches'),dict)
                       for arm in ('baseline','daeloryn')):
                raise ValueError('This legacy run has no per-batch receipts; safe resume is unavailable')
            completed={}
            unknown=[]
            for arm in ('baseline','daeloryn'):
                entries=record['arms'][arm]['batches']
                total=prepared[arm]['batch_count']
                confirmed={}
                for index, row in entries.items():
                    if not index.isdigit() or not 1 <= int(index) <= total or not isinstance(row,dict):
                        raise ValueError('invalid persisted batch receipts')
                    if row.get('status')=='completed' and isinstance(row.get('reply'),str) and row['reply']:
                        confirmed[int(index)]=row['reply']
                    else:
                        unknown.append('%s:%s'%(arm,index))
                completed[arm]=confirmed
            if not unknown and all(len(completed[arm])==prepared[arm]['batch_count']
                                   for arm in ('baseline','daeloryn')):
                raise ValueError('all batches are already complete')
            if unknown and acknowledge_unknown is not True:
                raise PermissionError('Unknown in-flight batches '+', '.join(unknown[:12])+
                    '; acknowledge possible duplicate provider usage before retry')
            if record.get('resume_attempts',0)>=5:
                raise ValueError('maximum five manually approved continuation attempts')
            record['resume_attempts']=record.get('resume_attempts',0)+1
            record['status']='running'
            record['error']=None
            record.pop('comparison', None)
            record['result']=None
            record['updated_at']=_utc()
            # start() writes the journal under the same lock and creates the
            # worker. Do not start it if any prior run is still active.
            return self.start(prepared,approved_digest,runner,_resume=(record,completed))

    def start(self, prepared, approved_digest, runner, *, _resume=None):
        if prepared.get("sha256") != approved_digest:
            raise PermissionError("benchmark approval changed; prepare again")
        with self.guard:
            if self.active is not None:
                raise RuntimeError("a benchmark is already running")
            self._ensure_dir()
            if _resume is None and len(list(self.directory.glob("*.json"))) >= MAX_RECORDS:
                raise ValueError("benchmark history is full (30 runs); archive old local receipts first")
            run_id = uuid.uuid4().hex if _resume is None else _resume[0]['run_id']
            record = {
                "run_id": run_id, "status": "running", "created_at": _utc(),
                "updated_at": _utc(), "repository": prepared["repository"],
                "mode": prepared["mode"], "model": prepared["model"],
                "agent": prepared["agent"], "source_sha256": prepared["source_sha256"],
                "approved_sha256": approved_digest,
                "total_model_calls": prepared["total_model_calls"],
                "arms": {arm: {"status": "pending", "completed_batches": 0,
                               "total_batches": prepared[arm]["batch_count"],
                               "reply": "", "failure": None, "batches": {}}
                         for arm in ("baseline", "daeloryn")},
                "result": None, "error": None,
                "verified_trial": False
            } if _resume is None else _resume[0]
            self._save(record)
            self.active = run_id
            self.active_record = record
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
                        elif event_type == 'batch_started':
                            number=event.get('batch')
                            if isinstance(number,int) and number>0:
                                row['batches'][str(number)]={'status':'unknown','reply':''}
                        elif event_type == 'batch_failed':
                            number=event.get('batch')
                            if isinstance(number,int) and number>0:
                                row['batches'][str(number)]={'status':'unknown','reply':''}
                        elif event_type == "batch_reply" and isinstance(event.get("reply"), str):
                            # Per-batch receipts are persisted before the next remote call.
                            # Bound transcript size; show truncation honestly.
                            number=event.get('batch')
                            if isinstance(number,int) and number>0:
                                full=event['reply']
                                # A resumed batch must reuse the exact response, not a
                                # truncated paraphrase. The Copilot CLI already caps a
                                # response to 64KiB; persist its complete text.
                                row['batches'][str(number)]={'status':'completed','reply':full}
                            piece = event["reply"][:65536]
                            next_reply = row["reply"] + ("\n\n" if row["reply"] else "") + \
                                ("Batch %s:\n" % event.get("batch", "?")) + piece
                            row["reply"] = (next_reply[:200000] +
                                            ("\n[Transcript truncated for local storage]" if len(next_reply) > 200000 else ""))
                        elif event_type == "arm_finished":
                            row["status"] = event.get("status", "partial")
                        # Writing+fsync for every dispatched batch is expensive.
                        # Persist material progress on completed replies/arm state;
                        # keep transient in-flight counts in memory.
                        if event_type in ('arm_started', 'arm_finished', 'batch_started', 'batch_failed', 'batch_reply'):
                            record["updated_at"] = _utc()
                            self._save(record)

                run_kwargs={'progress':progress,'cancel_event':cancel_event,'parallelism':2}
                if _resume is not None:
                    run_kwargs['resume_completed']=_resume[1]
                result = runner(prepared, approved_digest, **run_kwargs)
                # Reuse only the in-memory approved source snapshot (no
                # provider call or filesystem rescan). Older/fixture runners
                # may not carry per-batch source prompts. Evidence evaluation
                # must never turn a valid partial or completed provider receipt
                # into "failed": preserve model output and disclose the missing
                # evaluation separately.
                try:
                    source = source_from_prepared(prepared)
                except (KeyError, TypeError, ValueError):
                    source = {}
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
                    if source:
                        try:
                            record["comparison"] = evaluate_evidence(record, source)
                            record.pop("comparison_error", None)
                        except (KeyError, TypeError, ValueError):
                            record.pop("comparison", None)
                            record["comparison_error"] = (
                                "Offline evidence evaluation was unavailable; original "
                                "model results are preserved. No winner was verified.")
                    else:
                        record.pop("comparison", None)
                        record["comparison_error"] = (
                            "Approved source-line manifest unavailable for offline "
                            "evaluation. The saved run and model replies are preserved.")
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
                        self.active_record = None
                    self.stop_events.pop(run_id, None)

        thread = threading.Thread(target=work, daemon=True, name="benchmark-" + run_id[:8])
        thread.start()
        return {"run_id": run_id, "status": "running", "created_at": record["created_at"]}
