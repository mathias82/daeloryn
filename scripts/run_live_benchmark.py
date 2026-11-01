#!/usr/bin/env python3
"""Opt-in sequential benchmark orchestrator for a preprepared isolated trial.

Commands are operator-supplied argv, never shell commands. Does not provide
sandbox isolation or attest actual provider model/agent identity.
"""
import argparse
import json
from pathlib import Path
import sys

from capture_provider_cli import capture, HOSTS
from compare_implementation_trials import compare
from assemble_benchmark_trial import assemble


def validate(plan, trial):
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("unsupported plan")
    provider = plan.get("provider")
    if provider not in HOSTS:
        raise ValueError("unsupported provider")
    if not isinstance(plan.get("agent"), str) or not plan["agent"].strip():
        raise ValueError("agent required")
    if not isinstance(plan.get("run_id"), str) or not plan["run_id"].strip():
        raise ValueError("run ID required")
    arms = plan.get("arms")
    if not isinstance(arms, dict) or set(arms) != {"baseline", "daeloryn"}:
        raise ValueError("both arms required")
    trial = Path(trial).resolve(strict=True)
    for arm in ("baseline", "daeloryn"):
        config = arms[arm]
        if not isinstance(config, dict) or (not isinstance(config.get("model"), str) or not config["model"].strip()):
            raise ValueError("explicit model required")
        if not isinstance(config.get("argv"), list):
            raise ValueError("explicit argv required")
        path = trial / arm
        if path.is_symlink() or not path.is_dir() or path.resolve() != path:
            raise ValueError("real prepared arm required")
    if arms["baseline"]["model"] != arms["daeloryn"]["model"]:
        raise ValueError("paired benchmark requires the same requested model in both arms")
    return provider


def run(plan, trial, *, execute=False, timeout=900, evaluator_timeout=60,
        sandbox_image=None, capturer=capture, comparator=compare):
    provider = validate(plan, trial)
    if not execute:
        return {"schema_version": 1, "kind": "benchmark-orchestrator-preview",
                "provider_invoked": False, "provider": provider,
                "agent": plan["agent"], "run_id": plan["run_id"],
                "arms": ["baseline", "daeloryn"]}
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("invalid provider timeout")
    if type(evaluator_timeout) is not int or evaluator_timeout <= 0:
        raise ValueError("invalid evaluator timeout")
    if sandbox_image is None:
        raise ValueError("digest-pinned evaluator sandbox image required for execution")
    from sandbox_runner import DIGEST_IMAGE
    if not DIGEST_IMAGE.fullmatch(sandbox_image):
        raise ValueError("invalid sandbox image digest")
    trial = Path(trial).resolve(strict=True)
    captures = {}
    for arm in ("baseline", "daeloryn"):
        spec = plan["arms"][arm]
        captures[arm] = capturer(trial / arm, provider, spec["model"], spec["argv"], timeout)
        if captures[arm].get("status") != "completed":
            return {"schema_version": 1, "kind": "benchmark-orchestrator-result",
                    "status": "stopped_provider_failure", "provider_invoked": True,
                    "failed_arm": arm, "captures": captures,
                    "warning": "No retry: remote outcome may be unknown"}
    evaluation = comparator(trial, timeout=evaluator_timeout, sandbox_image=sandbox_image)
    if not evaluation.get("comparable"):
        return {"schema_version": 1, "kind": "benchmark-orchestrator-result",
                "status": "invalid_comparison", "captures": captures,
                "comparison": evaluation, "provider_invoked": True}
    record = assemble(plan["agent"], provider, plan["run_id"], evaluation, captures)
    return {"schema_version": 1, "kind": "benchmark-orchestrator-result",
            "status": "evaluated", "provider_invoked": True,
            "captures": captures, "comparison": evaluation, "trial_record": record,
            "warning": "CLI invocations are not proof of remote model identity, agent activation or workspace isolation"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trial", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--evaluator-timeout", type=int, default=60)
    p.add_argument("--sandbox-image", help="required for execution: preinstalled digest-pinned image")
    a = p.parse_args()
    if a.output.exists() or a.output.is_symlink():
        p.error("output exists")
    try:
        plan = json.loads(a.plan.read_text(encoding="utf-8"))
        result = run(plan, a.trial, execute=a.execute, timeout=a.timeout,
                     evaluator_timeout=a.evaluator_timeout, sandbox_image=a.sandbox_image)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        p.error(str(exc))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result.get("status", "preview"),
                      "output": str(a.output)}, indent=2))
    return 0 if not a.execute or result.get("status") == "evaluated" else 1


if __name__ == "__main__":
    sys.exit(main())
