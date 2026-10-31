#!/usr/bin/env python3
"""Export real blinded engineering fixtures and score actual submitted findings.

Never include reference labels in provider-visible exports.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from evaluate_engineering import BASE, prompt_for, reference
from score_agents import score


def build_pack():
    source = reference()
    prompts = []
    for case in source["cases"]:
        task = prompt_for(case["id"])
        if any(label in task for label in case["expected"]):
            raise ValueError("gold label leaked into prompt")
        prompts.append({"id": case["id"], "agent": case["agent"],
                        "task": task,
                        "task_sha256": hashlib.sha256(task.encode("utf-8")).hexdigest()})
    return {"schema_version": 1, "kind": "blinded-engineering-case-pack",
            "cases": prompts,
            "reference_sha256": hashlib.sha256(
                (BASE / "cases.json").read_bytes()).hexdigest(),
            "warning": "Reference labels withheld; fixtures are synthetic teaching examples, not independent real-world performance evidence."}


def grade(submission):
    ref = reference()
    result = score(submission, ref, require_complete=True)
    result["reference_sha256"] = hashlib.sha256(
        (BASE / "cases.json").read_bytes()).hexdigest()
    result["benchmark_kind"] = "synthetic-engineering-fixtures"
    result["model_identity_verified"] = False
    return result


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)
    export = sub.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    evaluate = sub.add_parser("score")
    evaluate.add_argument("--submission", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists() or a.output.is_symlink():
        p.error("output exists")
    try:
        if a.action == "export":
            report = build_pack()
        else:
            report = grade(json.loads(a.submission.read_text(encoding="utf-8")))
    except (ValueError, OSError, KeyError, TypeError, AssertionError) as exc:
        p.error(str(exc))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(a.output), "kind": report.get("kind", "engineering-score")},
                     indent=2))


if __name__ == "__main__":
    sys.exit(main())
