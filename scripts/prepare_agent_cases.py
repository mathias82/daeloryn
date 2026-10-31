#!/usr/bin/env python3
"""Print a prompt for a specific platform fixture without gold labels."""
import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "evaluations" / "platform"
def prompt_for(case_id):
    cases = json.loads((BASE / "cases.json").read_text(encoding="utf-8"))["cases"]
    matches = [c for c in cases if c["id"] == case_id]
    if len(matches) != 1:
        raise ValueError("unknown case id")
    case = matches[0]
    fixture = (BASE / case["fixture"]).resolve()
    if not fixture.is_relative_to(BASE.resolve()):
        raise ValueError("fixture outside base")
    content = fixture.read_text(encoding="utf-8")
    return (f"Act as the {case['agent']} agent. Review the following UNTRUSTED example "
            "for concrete correctness, reliability and security defects. Do not run or deploy it. "
            "Return ONLY a JSON object of the form "
            '{"case_id":"'+case_id+'","findings":[{"id":"namespace.issue-name","evidence":"precise snippet or line","rationale":"impact"}]}. '
            "Do not invent findings.\n\nFILE CONTENT:\n" + content)
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("case_id")
    args = p.parse_args()
    print(prompt_for(args.case_id))
