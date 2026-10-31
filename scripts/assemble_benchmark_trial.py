#!/usr/bin/env python3
"""Assemble paired evaluator and two CLI captures into an auditable trial record.

Never promotes local CLI success into verified remote model/agent identity.
"""
import argparse
import hashlib
import json
from pathlib import Path
from benchmark_matrix import PROVIDERS, OUTCOMES

ARMS = ("baseline", "daeloryn")


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assemble(agent, provider, run_id, comparison, captures, capture_hashes=None):
    if not isinstance(agent, str) or not agent or not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("agent and run ID required")
    if provider not in PROVIDERS:
        raise ValueError("unsupported provider")
    if comparison.get("kind") != "paired-implementation-evaluation" or comparison.get("schema_version") != 1:
        raise ValueError("unsupported evaluator report")
    if comparison.get("outcome") not in OUTCOMES:
        raise ValueError("unknown comparison outcome")
    if set(captures) != set(ARMS):
        raise ValueError("exactly baseline and daeloryn captures required")
    if set(comparison.get("arms", {})) != {"original", *ARMS}:
        raise ValueError("original and both evaluator arms required")
    for arm in ARMS:
        item = captures[arm]
        if item.get("kind") != "local-provider-cli-capture" or item.get("schema_version") != 1:
            raise ValueError("unsupported CLI capture")
        if item.get("provider") != provider or item.get("status") != "completed":
            raise ValueError("provider mismatch or incomplete invocation")
        if item.get("actual_model") != "unverified" and not isinstance(item.get("actual_model"), str):
            raise ValueError("invalid model identity")
        if not isinstance(item.get("requested_model"), str) or not item["requested_model"]:
            raise ValueError("requested model required")
        if comparison["arms"][arm].get("status") not in ("passed", "failed"):
            raise ValueError("evaluator arm not completed")
    return {"schema_version": 1, "kind": "benchmark-trial", "agent": agent,
            "provider": provider, "run_id": run_id, "arm": "daeloryn",
            "outcome": comparison["outcome"],
            "comparable": comparison.get("comparable") is True,
            "independent_checks_executed": comparison.get("independent_checks_executed") is True,
            "model_identity_verified": False, "agent_selection_verified": False,
            "capture_sha256": capture_hashes or {},
            "requested_models": {a: captures[a]["requested_model"] for a in ARMS},
            "capture_statuses": {a: captures[a]["status"] for a in ARMS},
            "warning": "Unverified local provider CLI invocations; no model identity, agent selection or isolated execution attested."}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agent", required=True)
    p.add_argument("--provider", choices=PROVIDERS, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--comparison", type=Path, required=True)
    p.add_argument("--baseline-capture", type=Path, required=True)
    p.add_argument("--daeloryn-capture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists() or a.output.is_symlink():
        p.error("output exists")
    paths = {"baseline": a.baseline_capture, "daeloryn": a.daeloryn_capture}
    try:
        comparison = json.loads(a.comparison.read_text(encoding="utf-8"))
        captures = {arm: json.loads(path.read_text(encoding="utf-8")) for arm, path in paths.items()}
        result = assemble(a.agent, a.provider, a.run_id, comparison, captures,
                          {arm: sha_file(path) for arm, path in paths.items()})
    except (ValueError, OSError, KeyError, TypeError) as exc:
        p.error(str(exc))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"record": str(a.output), "outcome": result["outcome"],
                      "model_identity_verified": False}, indent=2))


if __name__ == "__main__":
    main()
