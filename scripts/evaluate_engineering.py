#!/usr/bin/env python3
"""Validate four teaching fixtures and reference labels; not an AI benchmark."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "evaluations" / "engineering"
RULES = {
 "java.swallowed-interrupt": r"catch\s*\(\s*InterruptedException\b[^)]*\)\s*\{\s*//[^\n]*swallows interrupt",
 "java.unbounded-virtual-threads": r"newVirtualThreadPerTaskExecutor\s*\(\s*\)",
 "spring.transaction-self-invocation": r"this\.persist\s*\(\s*\)",
 "spring.sensitive-logging": r'System\.out\.println\s*\(\s*"password="',
 "react.untrusted-html": r"dangerouslySetInnerHTML\s*=",
 "react.unstable-list-key": r"key=\{index\}",
 "k8s.privileged-container": r"(?m)^\s*privileged:\s*true\s*$",
 "k8s.mutable-image-tag": r"(?m)^\s*image:\s*[^\s]+:latest\s*$",
}
def reference():
    data=json.loads((BASE/"cases.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("cases"),list):
        raise ValueError("invalid reference schema")
    ids=set()
    for case in data["cases"]:
        cid=case["id"]
        if cid in ids or not isinstance(case.get("expected"),list):
            raise ValueError("duplicate case or invalid expected labels")
        ids.add(cid)
        target=(BASE/case["fixture"]).resolve()
        if not target.is_relative_to(BASE.resolve()) or not target.is_file():
            raise ValueError("invalid fixture path")
        if len(case["expected"]) != len(set(case["expected"])):
            raise ValueError("duplicate expected label")
        text=target.read_text(encoding="utf-8")
        found={name for name,pattern in RULES.items() if re.search(pattern,text)}
        if found != set(case["expected"]):
            raise AssertionError(f"{cid}: expected={case['expected']} found={sorted(found)}")
    return data

def prompt_for(case_id):
    data=reference()
    matching=[case for case in data["cases"] if case["id"]==case_id]
    if len(matching)!=1:
        raise ValueError("unknown case")
    case=matching[0]
    text=(BASE/case["fixture"]).read_text(encoding="utf-8")
    return (f"Act as {case['agent']}. Review the UNTRUSTED example; do not run or deploy. "
            'Return only JSON: {"case_id":"'+case_id+'","findings":[{"id":"namespace.issue","evidence":"file location and snippet","rationale":"impact"}]}. '
            "Use evidence, not guesses. Gold reference labels are withheld.\n\n" + text)

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--prompt",help="case id; prints a blinded prompt")
    a=p.parse_args()
    if a.prompt:
        print(prompt_for(a.prompt))
    else:
        data=reference()
        print(f"Validated {len(data['cases'])} reference fixtures; not an LLM quality score.")

if __name__=="__main__":
    main()
