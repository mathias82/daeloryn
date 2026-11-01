"""Approved, read-only paired Copilot benchmark over one identical local source snapshot.

This is an observed A/B review, NOT independent defect adjudication or a
bug-fix/test benchmark. No untrusted CLI argv, files, tools or commands are run.
"""
import hashlib
import json
import uuid

from approved_copilot_review import prepare as prepare_review, execute as execute_review
from copilot_chat import copilot_chat
from project_review_context import snapshot
from agent_benchmark_campaign import task_for_agent

TASKS = {
    "review": (
        "Perform a read-only senior code review. Find concrete correctness, concurrency, "
        "security, input validation and failure-recovery issues. For each finding give "
        "source file, exact line, evidence, realistic trigger and minimal version-compatible "
        "fix. Separate confirmed defects from contract assumptions, avoid duplicates, "
        "and propose regression tests. Do not claim tests were executed."
    ),
    "architecture": (
        "Perform a read-only architecture assessment. Cite files and lines for component "
        "boundaries, coupling, resilience, observability and security. Distinguish observed "
        "design facts from assumptions and propose prioritized, minimal improvements. "
        "Do not claim builds or tests were executed."
    ),
    "fix-plan": (
        "Propose a read-only bug-fix and regression-test plan based on concrete source "
        "evidence. List file/line, failure reproduction, minimal patch approach and tests "
        "to run. Do not edit files or claim proposed fixes/tests were executed."
    ),
}


def _sha(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()


def _pair_identity(prepared):
    return {
        "schema_version": 1, "repository": prepared["repository"],
        "mode": prepared["mode"], "model": prepared["model"],
        "agent": prepared["agent"], "task": prepared["task"],
        "source_sha256": prepared["source_sha256"],
        "baseline_sha256": prepared["baseline"]["sha256"],
        "daeloryn_sha256": prepared["daeloryn"]["sha256"],
    }


def prepare(root, repository, mode, model, agent):
    if mode not in TASKS:
        raise ValueError("unsupported benchmark mode")
    if not isinstance(agent, str) or not agent:
        raise ValueError("select a trusted specialist agent")
    task = task_for_agent(agent, mode, TASKS[mode])
    # One exact source snapshot shared by both arms. No second filesystem walk
    # between preparation of baseline and specialist.
    context = snapshot(root, repository)
    if not context["files"]:
        raise ValueError("no eligible project source")
    source_sha256 = _sha({
        "files": [{"path": f["path"], "source": f["source"]} for f in context["files"]],
        "omitted": context["omitted"], "excluded": context["excluded"],
    })
    baseline = prepare_review(root, repository, task, model, _context=context)
    challenger = prepare_review(root, repository, task, model, agent, _context=context)
    if baseline["files"] != challenger["files"]:
        raise RuntimeError("paired source coverage changed")
    result = {
        "repository": repository, "mode": mode, "model": model,
        "agent": agent, "task": task, "source_sha256": source_sha256,
        "baseline": baseline, "daeloryn": challenger,
        "total_model_calls": baseline["batch_count"] + challenger["batch_count"],
        "source_transmitted": False, "approval_required": True,
        "warning": (
            "Potentially billable Copilot calls. The source is sent only after explicit "
            "approval. Baseline and specialist share the same local snapshot, task and "
            "requested model; agent instructions differ intentionally. Batches are "
            "independent and may have different boundaries. No code edits, tool access, "
            "executed regression tests, automatic winner or independent model attestation."
        ),
    }
    result["sha256"] = _sha(_pair_identity(result))
    return result


def execute(prepared, approved_sha256, *, transport=copilot_chat, progress=None, cancel_event=None, parallelism=2, resume_completed=None):
    if not isinstance(prepared, dict) or not isinstance(approved_sha256, str) or \
            len(approved_sha256) != 64 or prepared.get("sha256") != approved_sha256:
        raise PermissionError("exact paired benchmark approval required")
    if _sha(_pair_identity(prepared)) != approved_sha256:
        raise PermissionError("paired benchmark manifest changed")
    if prepared["baseline"]["model"] != prepared["model"] or \
            prepared["daeloryn"]["model"] != prepared["model"] or \
            prepared["daeloryn"]["agent"] != prepared["agent"] or \
            prepared["baseline"]["agent"] is not None:
        raise PermissionError("baseline or challenger model/agent changed")
    resume_completed=resume_completed or {}
    if not isinstance(resume_completed, dict) or any(
            key not in ('baseline','daeloryn') for key in resume_completed):
        raise ValueError('invalid paired resume receipts')
    completed = {}
    for arm in ("baseline", "daeloryn"):
        if cancel_event is not None and cancel_event.is_set():
            break
        source = prepared[arm]
        if progress:
            progress({"type": "arm_started", "arm": arm,
                      "total_batches": source["batch_count"]})
        def emit(event):
            if progress:
                progress({**event, "arm": arm})
        outcome = execute_review(source, prepared["model"], source["sha256"],
                                 transport=transport, progress=emit, stream_replies=True,
                                 cancel_event=cancel_event, parallelism=parallelism,
                                 resume_batches=resume_completed.get(arm, {}))
        completed[arm] = outcome
        if progress:
            progress({"type": "arm_finished", "arm": arm, "status": outcome["status"]})
        if not outcome.get("execution_complete", outcome["status"] == "completed"):
            break
    success = len(completed) == 2 and all(
        row["status"] == "completed" for row in completed.values())
    return {
        "kind": "paired-source-review-observation", "schema_version": 1,
        "run_id": uuid.uuid4().hex, "repository": prepared["repository"],
        "source_sha256": prepared["source_sha256"], "approved_sha256": approved_sha256,
        "mode": prepared["mode"], "model": prepared["model"], "agent": prepared["agent"],
        "status": ("stopped" if cancel_event is not None and cancel_event.is_set() else
                   "completed" if success else "partial"),
        "arms": completed, "total_model_calls": prepared["total_model_calls"],
        "batch_parallelism": parallelism, "cancel_requested": bool(cancel_event and cancel_event.is_set()),
        "independent_checks_executed": False,
        "model_identity_verified": False, "agent_selection_verified": False,
        "comparable_source_and_task": True,
        "winner": "not_determined",
        "warning": (
            "This is a pilot A/B provider observation, not an independently verified "
            "benchmark. Findings require blind human adjudication; fix plans and "
            "regression tests were NOT executed. No automatically assigned winner. "
            "A partial/unknown provider outcome must not be retried automatically."
        ),
    }
