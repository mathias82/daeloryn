#!/usr/bin/env python3
"""Unified local workflow service: plan, state, gated completion and dry-run adapter.

Agent execution is intentionally NOT enabled here. External approval tokens are
verified before they reach the transactional state machine. This file is not
a network-facing authorization service.
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from secure_runtime import connect, create, advance, verify_oidc
from workflows import plan

MAX_EVIDENCE = 1024 * 1024

def describe(db, run_id):
    row = db.execute("SELECT workflow,digest FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise ValueError("unknown run")
    steps = db.execute("SELECT id,status,evidence_sha256 FROM steps WHERE run_id=? ORDER BY rowid",(run_id,)).fetchall()
    return {"run_id": run_id, "workflow_hash": row[1],
            "steps": [{"id": sid,"status": status,"evidence_sha256": proof} for sid,status,proof in steps]}

def complete_from_file(db, run_id, step, path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not (0 < path.stat().st_size <= MAX_EVIDENCE):
        raise ValueError("evidence must be a nonempty regular file <= 1MiB")
    return advance(db,run_id,step,"complete",evidence=path.read_bytes())

def approve_verified(db, run_id, step, token, trusted_jwks, issuer, audience, subjects):
    if not subjects:
        raise ValueError("explicit approver allowlist required")
    claims = verify_oidc(token, trusted_jwks, issuer, audience, set(subjects))
    if claims.get("run_id") != run_id or claims.get("step") != step:
        raise ValueError("token scope mismatch")
    # The transactional backend checks the workflow hash and jti uniqueness.
    return advance(db,run_id,step,"approve",claims=claims)

def preview(workflow):
    return {"mode":"dry-run","will_invoke_agent":False,"will_deploy":False,**plan(workflow)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",type=Path,default=Path(".agent-runs/service.sqlite"))
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("plan");p.add_argument("workflow",type=Path)
    p=sub.add_parser("start");p.add_argument("workflow",type=Path);p.add_argument("--execute",action="store_true")
    p=sub.add_parser("status");p.add_argument("--run",required=True)
    p=sub.add_parser("complete");p.add_argument("--run",required=True);p.add_argument("--step",required=True);p.add_argument("--evidence",type=Path,required=True)
    p=sub.add_parser("approve");p.add_argument("--run",required=True);p.add_argument("--step",required=True);p.add_argument("--token-file",type=Path,required=True);p.add_argument("--jwks",type=Path,required=True);p.add_argument("--issuer",required=True);p.add_argument("--audience",required=True);p.add_argument("--allowed-subject",action="append",required=True)
    args=parser.parse_args()
    if args.command in ("plan","start"):
        workflow=json.loads(args.workflow.read_text(encoding="utf-8"))
        if args.command=="plan" or not args.execute:
            print(json.dumps(preview(workflow),indent=2))
            return
    if args.db.is_symlink():
        raise ValueError("database symlink rejected")
    args.db.parent.mkdir(parents=True,exist_ok=True)
    db=connect(args.db)
    try:
        if args.command=="start":
            result=create(db,workflow)
        elif args.command=="status":
            result=describe(db,args.run)
        elif args.command=="complete":
            result=complete_from_file(db,args.run,args.step,args.evidence)
        else:
            token_path=args.token_file
            if token_path.is_symlink() or not token_path.is_file():
                raise ValueError("invalid approval token file")
            result=approve_verified(db,args.run,args.step,token_path.read_text(encoding="utf-8").strip(),
                  json.loads(args.jwks.read_text(encoding="utf-8")),args.issuer,args.audience,args.allowed_subject)
        print(json.dumps(result,indent=2))
    finally:
        db.close()

if __name__=="__main__":
    main()
