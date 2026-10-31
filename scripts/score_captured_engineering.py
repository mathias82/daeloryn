#!/usr/bin/env python3
"""Grade strict JSON transcripts from real captured engineering fixture runs.

This does not execute providers or attest model identity.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from evaluate_engineering import reference
from score_agents import score


def parse_answer(output):
    if not isinstance(output, str) or len(output.encode("utf-8")) > 1048576:
        raise ValueError("bounded UTF-8 transcript required")
    value = output.strip()
    if value.startswith("```json") and value.endswith("```"):
        value = value[7:-3].strip()
    try:
        answer = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON response") from exc
    if not isinstance(answer, dict) or set(answer) != {"case_id", "findings"}:
        raise ValueError("unexpected answer fields")
    return answer


def evaluate(captures, provider, model):
    cases = reference()["cases"]
    if not isinstance(captures, dict) or set(captures) != {c["id"] for c in cases}:
        raise ValueError("all reference cases required")
    answers, hashes = [], {}
    for case in cases:
        cid = case["id"]
        report = captures[cid]
        if not isinstance(report, dict) or report.get("schema_version") != 1 or report.get("kind") != "local-provider-cli-capture":
            raise ValueError("invalid capture")
        if report.get("provider") != provider or report.get("requested_model") != model:
            raise ValueError("provider/model mismatch")
        if report.get("status") != "completed" or report.get("output_truncated") is not False:
            raise ValueError("incomplete or truncated transcript")
        answer = parse_answer(report.get("output"))
        if answer["case_id"] != cid:
            raise ValueError("wrong case response")
        answers.append(answer)
        hashes[cid] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    scored = score({"run_id": "captured-engineering", "tool": provider, "model": model,
                    "cases": answers}, reference(), require_complete=True)
    scored.update({"kind": "captured-engineering-score", "capture_hashes": hashes,
                   "model_identity_verified": False, "agent_selection_verified": False,
                   "warning": "CLI transcripts and labels are not proof of actual model identity, agent activation or evidence correctness."})
    return scored


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--captures", type=Path, required=True)
    p.add_argument("--provider", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists() or a.output.is_symlink():
        p.error("output exists")
    try:
        result = evaluate(json.loads(a.captures.read_text(encoding="utf-8")), a.provider, a.model)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with a.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        p.error(str(exc))
    print(json.dumps({"output": str(a.output), "f1": result["f1"],
                      "model_identity_verified": False}))

if __name__ == "__main__":
    sys.exit(main())
