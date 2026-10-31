#!/usr/bin/env python3
"""Score submitted agent findings against reference labels; no AI calls are made."""
import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "evaluations" / "platform"
def score(submission, reference):
    if not isinstance(submission, dict) or not isinstance(submission.get("cases"), list):
        raise ValueError("submission must contain a cases array")
    if not isinstance(reference, dict) or not isinstance(reference.get("cases"), list):
        raise ValueError("reference must contain a cases array")
    expected = {c["id"]: set(c["expected"]) for c in reference["cases"]}
    if len(expected) != len(reference["cases"]):
        raise ValueError("duplicate reference case id")
    submitted = {}
    for case in submission["cases"]:
        if not isinstance(case, dict) or case.get("case_id") not in expected:
            raise ValueError("unknown or malformed case_id")
        case_id = case["case_id"]
        if case_id in submitted:
            raise ValueError("duplicate case_id")
        findings = case.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("findings must be an array")
        found = set()
        for item in findings:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
                raise ValueError("finding must contain nonempty id")
            if not isinstance(item.get("evidence"), str) or not item["evidence"].strip():
                raise ValueError("finding must include evidence")
            if item["id"] in found:
                raise ValueError("duplicate finding id")
            found.add(item["id"])
        submitted[case_id] = found
    tp = fp = fn = 0
    rows = []
    for case_id, gold in expected.items():
        predicted = submitted.get(case_id, set())
        correct = gold & predicted
        false = predicted - gold
        missed = gold - predicted
        tp += len(correct); fp += len(false); fn += len(missed)
        rows.append({"case_id": case_id, "true_positive": sorted(correct),
                     "false_positive": sorted(false), "false_negative": sorted(missed)})
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"run_id": submission.get("run_id", "unspecified"), "tool": submission.get("tool", "unspecified"),
            "model": submission.get("model", "unspecified"), "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "cases": rows}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", type=Path, help="JSON findings from an actual agent run")
    ap.add_argument("--reference", type=Path, default=BASE / "cases.json")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    result = score(json.loads(args.submission.read_text(encoding="utf-8")),
                   json.loads(args.reference.read_text(encoding="utf-8")))
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
if __name__ == "__main__":
    main()
