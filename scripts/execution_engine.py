#!/usr/bin/env python3
"""Local, human-in-the-loop workflow execution state machine.

No shell commands, network calls, or AI tool invocations are performed.
'Execute' opens auditable agent handoffs; completion and approval are explicit.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import secrets
from datetime import datetime, timezone

from workflows import plan

STATES = {"pending", "awaiting_agent", "completed", "awaiting_approval"}
MAX_EVIDENCE_BYTES = 1024 * 1024

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def workflow_digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save_new(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create refuses overwriting old runs and symlinks.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(state, out, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())

def save_existing(path, state):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("state must be an existing, non-symlink file")
    fd, name = tempfile.mkstemp(prefix=".workflow-", dir=path.parent)
    try:
        os.chmod(name, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(state, out, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def load(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink state files are not supported")
    state = read_json(path)
    if state.get("schema_version") != 1:
        raise ValueError("unsupported state schema")
    if workflow_digest(state["workflow"]) != state["workflow_hash"]:
        raise ValueError("workflow hash mismatch")
    plan(state["workflow"])
    ids = {s["id"] for s in state["workflow"]["steps"]}
    if set(state["steps"]) != ids or any(s not in STATES for s in state["steps"].values()):
        raise ValueError("invalid state steps")
    return state

def event(state, action, step, **extra):
    state["events"].append({"at": utc_now(), "action": action, "step": step, **extra})

def start(workflow_file, state_file, execute=False):
    workflow = read_json(workflow_file)
    layout = plan(workflow)
    if not execute:
        return {"mode": "dry-run", **layout, "state_changed": False}
    state = {
        "schema_version": 1, "run_id": secrets.token_hex(16), "workflow": workflow,
        "workflow_hash": workflow_digest(workflow),
        "steps": {s["id"]: "pending" for s in workflow["steps"]},
        "events": [], "evidence": {}
    }
    event(state, "run_created", None)
    save_new(state_file, state)
    return {"mode": "handoff", "state": str(state_file), "state_changed": True, **advance(state_file)}

def ready(state):
    done = {sid for sid, status in state["steps"].items() if status == "completed"}
    return [s for s in state["workflow"]["steps"] if
            state["steps"][s["id"]] == "pending" and set(s["depends_on"]) <= done]

def advance(state_file):
    state = load(state_file)
    handoffs = []
    approvals = []
    for s in ready(state):
        sid = s["id"]
        if s.get("type") == "approval":
            state["steps"][sid] = "awaiting_approval"
            event(state, "approval_requested", sid)
            approvals.append(sid)
        else:
            state["steps"][sid] = "awaiting_agent"
            event(state, "handoff_opened", sid, agent=s["agent"])
            handoffs.append({"step": sid, "agent": s["agent"]})
    if handoffs or approvals:
        save_existing(state_file, state)
    return {"handoffs": handoffs, "approvals_required": approvals, "steps": state["steps"]}

def complete(state_file, step, evidence_file):
    state = load(state_file)
    if state["steps"].get(step) != "awaiting_agent":
        raise ValueError("only an active agent handoff may be completed")
    file = Path(evidence_file)
    if file.is_symlink() or not file.is_file() or file.stat().st_size not in range(1, MAX_EVIDENCE_BYTES + 1):
        raise ValueError("evidence must be a nonempty regular file (max 1 MiB)")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    state["steps"][step] = "completed"
    state["evidence"][step] = {"sha256": digest, "path": str(file.resolve())}
    event(state, "handoff_completed", step, evidence_sha256=digest)
    save_existing(state_file, state)
    return advance(state_file)

def approve(state_file, step, actor, reason, token=None):
    if not actor.strip() or not reason.strip():
        raise ValueError("actor and reason are required")
    if not token:
        raise ValueError("signed approval token is required")
    state = load(state_file)
    from approval_tokens import key_from_env, verify
    claim = verify(token, key_from_env(), state["run_id"], state["workflow_hash"], step)
    if claim["actor"] != actor:
        raise ValueError("approver does not match signed identity")
    if any(e.get("nonce") == claim["nonce"] for e in state["events"]):
        raise ValueError("approval token replay")
    if state["steps"].get(step) != "awaiting_approval":
        raise ValueError("approval is not pending or was already granted")
    # Actor is self-declared, not a verified identity.
    state["steps"][step] = "completed"
    event(state, "approved", step, actor=actor.strip(), reason=reason.strip(), nonce=claim["nonce"])
    save_existing(state_file, state)
    return advance(state_file)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    begin = sub.add_parser("start")
    begin.add_argument("workflow", type=Path)
    begin.add_argument("--state", type=Path, required=True)
    begin.add_argument("--execute", action="store_true", help="create handoff state; never runs AI or shell")
    next_cmd = sub.add_parser("advance")
    next_cmd.add_argument("--state", type=Path, required=True)
    done = sub.add_parser("complete")
    done.add_argument("--state", type=Path, required=True)
    done.add_argument("--step", required=True)
    done.add_argument("--evidence", type=Path, required=True)
    gate = sub.add_parser("approve")
    gate.add_argument("--state", type=Path, required=True)
    gate.add_argument("--step", required=True)
    gate.add_argument("--actor", required=True)
    gate.add_argument("--reason", required=True)
    gate.add_argument("--token", required=True, help="scoped HMAC approval token; do not store in git")
    status = sub.add_parser("status")
    status.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "start":
            output = start(args.workflow, args.state, args.execute)
        elif args.command == "advance":
            output = advance(args.state)
        elif args.command == "complete":
            output = complete(args.state, args.step, args.evidence)
        elif args.command == "approve":
            output = approve(args.state, args.step, args.actor, args.reason, args.token)
        else:
            state = load(args.state)
            output = {"steps": state["steps"], "events": state["events"], "evidence": state["evidence"]}
        print(json.dumps(output, indent=2))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
