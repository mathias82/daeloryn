#!/usr/bin/env python3
"""Evaluate a prepared two-arm implementation trial using independent frozen checks.

This runs evaluator commands, NOT model providers. Model invocation must be
performed separately in isolated sessions and independently attested.
"""
import argparse
import json
import sys
from pathlib import Path

from verify_implementation import verify


def compare(trial, timeout=60, sandbox_image=None, verifier=verify):
    if type(timeout) is not int or timeout <= 0:
        raise ValueError("timeout must be a positive integer")
    results = {}
    for arm in ("original", "baseline", "daeloryn"):
        try:
            results[arm] = verifier(trial, arm, timeout, sandbox_image)
        except (OSError, ValueError) as exc:
            results[arm] = {"arm": arm, "status": "error", "error": str(exc)}
    reports = list(results.values())
    manifests = {r.get("manifest_sha256") for r in reports}
    suites = {json.dumps(r.get("suite_sha256"), sort_keys=True) for r in reports}
    comparable = (len(manifests) == 1 and None not in manifests and len(suites) == 1
                  and all(r.get("status") != "error" for r in reports))
    gates = {}
    if comparable:
        names = set(results["original"]["checks"])
        comparable = all(set(results[a]["checks"]) == names for a in results)
        if comparable:
            for name in sorted(names):
                gates[name] = {a: results[a]["checks"][name]["status"] for a in results}
    baseline_pass = comparable and results["baseline"]["status"] == "passed"
    daeloryn_pass = comparable and results["daeloryn"]["status"] == "passed"
    if not comparable:
        outcome = "invalid_comparison"
    elif baseline_pass and daeloryn_pass:
        outcome = "tie_all_gates_passed"
    elif daeloryn_pass:
        outcome = "daeloryn_passed_baseline_failed"
    elif baseline_pass:
        outcome = "baseline_passed_daeloryn_failed"
    else:
        outcome = "neither_passed"
    return {"schema_version": 1, "kind": "paired-implementation-evaluation",
            "provider_invoked": False, "model_identity_verified": False,
            "independent_checks_executed": True, "comparable": bool(comparable),
            "outcome": outcome, "gate_statuses": gates, "arms": results,
            "warning": "Do not claim a live AI comparison without independent provider transcripts, model IDs and isolated trial provenance."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--sandbox-image", help="digest-pinned local Docker image; recommended for untrusted candidate code")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    try:
        result = compare(args.trial, args.timeout, args.sandbox_image)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"comparable": result["comparable"], "outcome": result["outcome"],
                      "report": str(args.output)}, indent=2))
    return 0 if result["comparable"] else 1


if __name__ == "__main__":
    sys.exit(main())
