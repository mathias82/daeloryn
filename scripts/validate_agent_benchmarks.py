#!/usr/bin/env python3
"""Validate agent-specific benchmark cases and report coverage without inventing scores."""
import argparse
import hashlib
import json
from pathlib import Path
from agents import catalog

def validate_cases(root, agents=None):
    root = Path(root)
    agents = sorted(agents if agents is not None else (meta["name"] for meta, _ in catalog()))
    if not agents or len(agents) != len(set(agents)):
        raise ValueError("unique agent catalog required")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("existing non-symlink case directory required")
    found, errors = {}, []
    for agent in agents:
        path = root / (agent + ".json")
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 131072:
            errors.append(agent + ": unsafe or oversized case file")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("schema_version") != 1 or payload.get("agent") != agent:
                raise ValueError("schema or agent mismatch")
            cases = payload.get("cases")
            if not isinstance(cases, list) or not cases:
                raise ValueError("nonempty cases required")
            ids = set()
            for case in cases:
                if not isinstance(case, dict) or set(case) != {"id", "task", "evaluator"}:
                    raise ValueError("case requires id, task and evaluator")
                if not isinstance(case["id"], str) or not case["id"].strip() or case["id"] in ids:
                    raise ValueError("unique nonempty case IDs required")
                ids.add(case["id"])
                if not isinstance(case["task"], str) or not case["task"].strip():
                    raise ValueError("nonempty task required")
                ev = case["evaluator"]
                if not isinstance(ev, dict) or not isinstance(ev.get("suite_sha256"), str) or len(ev["suite_sha256"]) != 64:
                    raise ValueError("pinned evaluator suite SHA-256 required")
                if any(c not in "0123456789abcdef" for c in ev["suite_sha256"]):
                    raise ValueError("invalid suite digest")
            found[agent] = {"case_count": len(cases), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        except (ValueError, TypeError, UnicodeError) as exc:
            errors.append(agent + ": " + str(exc))
    return {"schema_version": 1, "kind": "agent-benchmark-case-coverage",
            "expected_agents": len(agents), "covered_agents": len(found),
            "missing_agents": sorted(set(agents) - set(found)),
            "cases": found, "errors": errors,
            "ready": len(found) == len(agents) and not errors,
            "warning": "Manifest validation does not execute or independently validate evaluator suites."}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cases", type=Path, required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    if a.output and (a.output.exists() or a.output.is_symlink()):
        p.error("output exists")
    try:
        report = validate_cases(a.cases)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    data = json.dumps(report, indent=2) + "\n"
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(data, encoding="utf-8")
    print(data, end="")
    return 0 if report["ready"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
