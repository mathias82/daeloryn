#!/usr/bin/env python3
"""Audit agent/provider coverage from independently captured benchmark records.

Never treats a CLI exit code as verified model identity or test correctness.
"""
import argparse
import json
from pathlib import Path
from agents import catalog

PROVIDERS = ("copilot", "claude", "codex", "gemini")
ARMS = ("baseline", "daeloryn")
OUTCOMES = {"tie_all_gates_passed", "daeloryn_passed_baseline_failed",
            "baseline_passed_daeloryn_failed", "neither_passed", "invalid_comparison"}


def matrix(records, agents=None):
    agents = sorted(agents if agents is not None else (meta["name"] for meta, _ in catalog()))
    if not agents or len(set(agents)) != len(agents):
        raise ValueError("unique nonempty agent catalog required")
    expected = {(agent, provider, arm) for agent in agents for provider in PROVIDERS for arm in ARMS}
    observed = {}
    for record in records:
        if record.get("schema_version") != 1 or record.get("kind") != "benchmark-trial":
            raise ValueError("unsupported benchmark record")
        key = (record.get("agent"), record.get("provider"), record.get("arm"))
        if key not in expected:
            raise ValueError("unknown agent/provider/arm")
        run = record.get("run_id")
        if not isinstance(run, str) or not run.strip():
            raise ValueError("nonempty run_id required")
        identity = (*key, run)
        if identity in observed:
            raise ValueError("duplicate benchmark trial")
        outcome = record.get("outcome")
        if outcome not in OUTCOMES:
            raise ValueError("unknown evaluation outcome")
        observed[identity] = record
    covered = {key[:3] for key in observed}
    missing = sorted(expected - covered)
    verified = [r for r in observed.values() if r.get("model_identity_verified") is True
                and r.get("agent_selection_verified") is True
                and r.get("independent_checks_executed") is True
                and r.get("comparable") is True]
    outcomes = {outcome: sum(r["outcome"] == outcome for r in verified)
                for outcome in sorted(OUTCOMES)}
    return {"schema_version": 1, "kind": "benchmark-coverage-dashboard",
            "agent_count": len(agents), "provider_count": len(PROVIDERS),
            "expected_cells": len(expected), "observed_cells": len(covered),
            "missing_cells": [{"agent": a, "provider": p, "arm": arm} for a, p, arm in missing],
            "verified_trial_count": len(verified), "verified_outcomes": outcomes,
            "coverage_percent": round(100 * len(covered) / len(expected), 2),
            "warning": "Observed records are self-declared. Only externally attested identities and independent tests qualify for verified outcomes."}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("records", type=Path, nargs="*")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.output and (args.output.exists() or args.output.is_symlink()):
        p.error("output already exists")
    try:
        report = matrix([json.loads(path.read_text(encoding="utf-8")) for path in args.records])
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
