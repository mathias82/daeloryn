#!/usr/bin/env python3
"""Summarize recorded benchmark runs without inventing missing providers."""
import argparse
import json
from pathlib import Path

PROVIDERS=("codex","claude","copilot","gemini")
def summarize(files):
    runs=[]
    seen=set()
    for path in files:
        item=json.loads(Path(path).read_text(encoding="utf-8"))
        if item.get("schema_version")!=1 or item.get("kind")!="recorded-external-output" or item.get("provider") not in PROVIDERS:
            raise ValueError(f"{path}: not a recorded benchmark run")
        ident=(item["provider"],item["run_id"])
        if ident in seen:
            raise ValueError("duplicate provider run id")
        seen.add(ident)
        runs.append({"provider":item["provider"],"model":item["model"],"run_id":item["run_id"],
                     "precision":item["metrics"]["precision"],"recall":item["metrics"]["recall"],
                     "f1":item["metrics"]["f1"],"evidence_line_valid_fraction":item["evidence_line_valid_fraction"],
                     "human_evidence_reviewed":False})
    return {"status":"partial" if len({x["provider"] for x in runs})<4 else "collected_needs_human_review",
            "providers_missing":sorted(set(PROVIDERS)-{x["provider"] for x in runs}),
            "runs":sorted(runs,key=lambda r:(r["provider"],r["run_id"])),
            "warning":"Scores reflect submitted finding IDs; line checks do not validate semantic correctness. Human adjudication required."}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("records",type=Path,nargs="+")
    args=p.parse_args()
    print(json.dumps(summarize(args.records),indent=2))
if __name__=="__main__":
    main()
