#!/usr/bin/env python3
"""Offline workflow DAG validation and deterministic wave planning.

This script does not execute AI tools, shell commands, deployments, or approvals.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def known_agents():
    result = set()
    for p in (ROOT / "agents").glob("*/*.md"):
        result.add(p.stem)
    return result

def plan(data, agents=None):
    agents = known_agents() if agents is None else agents
    if data.get("schema_version") != 1:
        raise ValueError("unsupported schema version")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("nonempty steps required")
    by_id = {}
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("id"), str):
            raise ValueError("invalid step")
        sid = step["id"]
        if not sid or sid in by_id:
            raise ValueError("empty or duplicate step id")
        if step.get("type", "agent") not in ("agent", "approval"):
            raise ValueError("unsupported step type")
        if step.get("type", "agent") == "agent" and step.get("agent") not in agents:
            raise ValueError("unknown agent: " + str(step.get("agent")))
        if not isinstance(step.get("depends_on"), list) or any(not isinstance(x, str) for x in step["depends_on"]):
            raise ValueError("depends_on must be a list of ids")
        by_id[sid] = step
    for sid, step in by_id.items():
        deps = step["depends_on"]
        if sid in deps or len(deps) != len(set(deps)) or any(d not in by_id for d in deps):
            raise ValueError("invalid dependencies")
    remaining = set(by_id)
    done = set()
    waves = []
    while remaining:
        ready = sorted(k for k in remaining if set(by_id[k]["depends_on"]) <= done)
        if not ready:
            raise ValueError("cyclic workflow")
        waves.append(ready)
        done.update(ready)
        remaining.difference_update(ready)
    return {"workflow": data.get("name", "unnamed"), "waves": waves,
            "requires_approval": [s["id"] for s in steps if s.get("type") == "approval"]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow", type=Path, nargs="?")
    parser.add_argument("--validate-all", action="store_true")
    args = parser.parse_args()
    if args.validate_all:
        files = sorted((ROOT / "workflows").glob("*.json"))
        if not files:
            raise ValueError("no workflows")
    elif args.workflow:
        files = [args.workflow]
    else:
        parser.error("provide workflow or --validate-all")
    for path in files:
        print(json.dumps(plan(json.loads(path.read_text(encoding="utf-8"))), indent=2))

if __name__ == "__main__":
    main()
