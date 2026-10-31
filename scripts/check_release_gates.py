#!/usr/bin/env python3
"""Fail closed on absent v1.0 P0 evidence; never manufacture a green release."""
import argparse
import json
from pathlib import Path

REQUIRED=(
    "ci_matrix",
    "installer_security",
    "security_review",
    "codex_host",
    "claude_host",
    "copilot_host",
    "gemini_host",
    "provider_benchmark",
    "human_evidence_review",
    "field_pilots",
    "release_candidate_regression",
)

def check(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version")!=1 or not isinstance(data.get("gates"),dict):
        raise ValueError("invalid release evidence format")
    missing=[]
    for name in REQUIRED:
        row=data["gates"].get(name,{})
        if (not isinstance(row,dict) or row.get("passed") is not True
                or not isinstance(row.get("evidence_url"),str)
                or not row["evidence_url"].startswith("https://")):
            missing.append(name)
    return missing

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",type=Path,required=True)
    args=p.parse_args()
    missing=check(args.evidence)
    if missing:
        p.exit(1,"Release BLOCKED, missing verified gate evidence: "+", ".join(missing)+"\n")
    print("All required gate records present; independently verify evidence and release SHA before publication.")
if __name__=="__main__":
    main()
