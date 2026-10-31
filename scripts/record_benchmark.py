#!/usr/bin/env python3
"""Record external provider output with line-verified evidence; never invoke a provider."""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from score_agents import score

ROOT=Path(__file__).resolve().parents[1]
PROVIDERS={"codex","claude","copilot","gemini"}

def evidence_audit(submission,reference,base):
    case_map={c["id"]:c for c in reference["cases"]}
    rows=[]
    for case in submission["cases"]:
        cid=case["case_id"]
        if cid not in case_map:
            raise ValueError("unknown case")
        fixture=(base/case_map[cid]["fixture"]).resolve()
        if not fixture.is_relative_to(base.resolve()):
            raise ValueError("unsafe fixture path")
        lines=fixture.read_text(encoding="utf-8").splitlines()
        for finding in case.get("findings",[]):
            line=finding.get("line")
            quote=finding.get("quote")
            valid=isinstance(line,int) and not isinstance(line,bool) and 1<=line<=len(lines) and isinstance(quote,str) and len(quote.strip())>=4 and quote.strip() in lines[line-1]
            rows.append({"case_id":cid,"finding_id":finding["id"],"evidence_line_valid":valid,
                         "reference_match":finding["id"] in case_map[cid]["expected"],
                         "manual_adjudication_required":True})
    return rows

def record(submission,reference,base,provider,model,run_id,strict=False):
    if provider not in PROVIDERS or not isinstance(model,str) or not model.strip() or not run_id.strip():
        raise ValueError("provider, model and run id required")
    if submission.get("tool") not in (None,provider):
        raise ValueError("submission tool and provider disagree")
    if submission.get("model") not in (None,model):
        raise ValueError("submission model mismatch")
    submission={**submission,"tool":provider,"model":model,"run_id":run_id}
    metrics=score(submission,reference,require_complete=strict)
    evidence=evidence_audit(submission,reference,base)
    if strict and any(not row['evidence_line_valid'] for row in evidence):
        raise ValueError('invalid source-line evidence in strict benchmark run')
    return {"schema_version":1,"kind":"recorded-external-output","recorded_at":datetime.now(timezone.utc).isoformat(),
            "provider":provider,"model":model,"run_id":run_id,
            "source_sha256":hashlib.sha256(json.dumps(submission,sort_keys=True).encode()).hexdigest(),
            "reference_sha256":hashlib.sha256(json.dumps(reference,sort_keys=True).encode()).hexdigest(),
            "strict_evidence_gate":strict,"metrics":metrics,"evidence":evidence,
            "evidence_line_valid_fraction":round(sum(x["evidence_line_valid"] for x in evidence)/len(evidence),4) if evidence else 0.0,
            "note":"Line and quote consistency is automated; finding correctness still requires blinded human review. This script does not invoke a model."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--submission",type=Path,required=True)
    p.add_argument("--reference",type=Path,default=ROOT/"evaluations/engineering/cases.json")
    p.add_argument("--provider",choices=sorted(PROVIDERS),required=True)
    p.add_argument("--model",required=True)
    p.add_argument("--run-id",required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--strict",action="store_true",help="require all cases and valid source-line evidence")
    a=p.parse_args()
    if a.output.exists():
        p.error("output exists; refusing overwrite")
    reference=json.loads(a.reference.read_text(encoding="utf-8"))
    result=record(json.loads(a.submission.read_text(encoding="utf-8")),reference,a.reference.parent,a.provider,a.model,a.run_id,strict=a.strict)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"provider":a.provider,"run_id":a.run_id,"f1":result["metrics"]["f1"],
                      "line_evidence_fraction":result["evidence_line_valid_fraction"]},indent=2))
if __name__=="__main__":
    main()
