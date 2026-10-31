#!/usr/bin/env python3
"""SQLite-backed experimental orchestration with offline OIDC checks.

No shell or AI execution occurs from this state machine.
OIDC claims are verified against an operator-provisioned JWKS; no implicit trust
in user-provided URLs or unsigned JWT payloads.
"""
import argparse
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from workflows import plan

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def connect(path):
    db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, workflow TEXT NOT NULL, digest TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS steps (run_id TEXT NOT NULL, id TEXT NOT NULL, status TEXT NOT NULL, evidence_sha256 TEXT, PRIMARY KEY(run_id,id))")
    db.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, step TEXT, action TEXT NOT NULL, actor TEXT, at INTEGER NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS approvals (issuer TEXT NOT NULL, subject TEXT NOT NULL, token_id TEXT NOT NULL, PRIMARY KEY(issuer,subject,token_id))")
    return db

def log(db, run, step, action, actor=None):
    db.execute("INSERT INTO events(run_id,step,action,actor,at) VALUES (?,?,?,?,?)",
               (run, step, action, actor, int(time.time())))

def move_ready(db, run, workflow):
    status = dict(db.execute("SELECT id,status FROM steps WHERE run_id=?", (run,)).fetchall())
    finished = {k for k,v in status.items() if v == "completed"}
    opened = []
    for step in workflow["steps"]:
        sid = step["id"]
        if status[sid] == "pending" and set(step["depends_on"]) <= finished:
            kind = "awaiting_approval" if step.get("type") == "approval" else "awaiting_agent"
            db.execute("UPDATE steps SET status=? WHERE run_id=? AND id=?", (kind, run, sid))
            log(db, run, sid, "approval_requested" if kind == "awaiting_approval" else "handoff_opened")
            opened.append({"step":sid,"status":kind})
    return opened

def create(db, workflow):
    plan(workflow)
    run = uuid.uuid4().hex
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("INSERT INTO runs(id,workflow,digest) VALUES(?,?,?)",
                   (run,json.dumps(workflow),digest(workflow)))
        db.executemany("INSERT INTO steps(run_id,id,status) VALUES(?,?,'pending')",
                       [(run,s["id"]) for s in workflow["steps"]])
        log(db,run,None,"created")
        opened = move_ready(db,run,workflow)
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return {"run_id":run,"opened":opened}

def advance(db,run,step,action,evidence=None,claims=None):
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT workflow,digest FROM runs WHERE id=?", (run,)).fetchone()
        if not row:
            raise ValueError("unknown run")
        workflow = json.loads(row[0])
        if digest(workflow) != row[1]:
            raise ValueError("workflow changed")
        current = db.execute("SELECT status FROM steps WHERE run_id=? AND id=?", (run,step)).fetchone()
        expected = "awaiting_approval" if action == "approve" else "awaiting_agent"
        if not current or current[0] != expected:
            raise ValueError("step not eligible")
        if action == "approve":
            if claims is None or claims.get("run_id") != run or claims.get("step") != step:
                raise ValueError("approval claims not scoped to this run/step")
            if claims.get("workflow_hash") != row[1]:
                raise ValueError("workflow digest mismatch")
            subject = claims.get("sub")
            issuer = claims.get("iss")
            token_id = claims.get("jti")
            if not all(isinstance(x,str) and x for x in (subject,issuer,token_id)):
                raise ValueError("missing identity or unique token id")
            db.execute("INSERT INTO approvals(issuer,subject,token_id) VALUES(?,?,?)",
                       (issuer,subject,token_id))
            actor = issuer + "/" + subject
            evidence_hash = None
        elif action == "complete":
            if not isinstance(evidence,bytes) or not evidence or len(evidence)>1048576:
                raise ValueError("evidence required (max 1 MiB)")
            evidence_hash = hashlib.sha256(evidence).hexdigest()
            actor = None
        else:
            raise ValueError("unsupported action")
        db.execute("UPDATE steps SET status='completed', evidence_sha256=? WHERE run_id=? AND id=?",
                   (evidence_hash,run,step))
        log(db,run,step,action,actor)
        opened = move_ready(db,run,workflow)
        db.execute("COMMIT")
        return {"opened":opened}
    except Exception:
        db.execute("ROLLBACK")
        raise

def verify_oidc(token, jwks, issuer, audience, allowed_subjects=None):
    """Fail closed; caller supplies trusted JWKS and issuer, never token-derived URLs."""
    try:
        import jwt
    except ImportError as exc:
        raise RuntimeError("install PyJWT[crypto] for OIDC verification") from exc
    if not issuer.startswith("https://") or not audience:
        raise ValueError("trusted HTTPS issuer and audience required")
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"),str):
        raise ValueError("only pinned RS256 keys are accepted")
    keys = [k for k in jwks.get("keys",[]) if k.get("kid")==header["kid"] and k.get("kty")=="RSA" and k.get("use","sig")=="sig"]
    if len(keys)!=1:
        raise ValueError("unknown or ambiguous key")
    key = jwt.PyJWK.from_dict(keys[0], algorithm="RS256").key
    claims = jwt.decode(token,key,algorithms=["RS256"],issuer=issuer,audience=audience,
                        options={"require":["iss","aud","exp","iat","sub","jti"]},leeway=30)
    if allowed_subjects is not None and claims["sub"] not in allowed_subjects:
        raise ValueError("approver not authorized")
    return claims

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True,type=Path)
    sub=p.add_subparsers(dest="command",required=True)
    s=sub.add_parser("start");s.add_argument("workflow",type=Path);s.add_argument("--execute",action="store_true")
    s=sub.add_parser("complete");s.add_argument("--run",required=True);s.add_argument("--step",required=True);s.add_argument("--evidence",type=Path,required=True)
    s=sub.add_parser("approve");s.add_argument("--run",required=True);s.add_argument("--step",required=True);s.add_argument("--token-file",type=Path,required=True);s.add_argument("--jwks",type=Path,required=True);s.add_argument("--issuer",required=True);s.add_argument("--audience",required=True);s.add_argument("--allowed-subject",action="append",required=True)
    args=p.parse_args()
    if args.command=="start" and not args.execute:
        print(json.dumps({"mode":"dry-run",**plan(json.loads(args.workflow.read_text()))},indent=2))
        return
    if args.db.is_symlink():
        raise ValueError("database symlink not permitted")
    args.db.parent.mkdir(parents=True,exist_ok=True)
    db=connect(args.db)
    if args.command=="start":
        result=create(db,json.loads(args.workflow.read_text()))
    elif args.command=="complete":
        result=advance(db,args.run,args.step,"complete",evidence=args.evidence.read_bytes())
    else:
        claims=verify_oidc(args.token_file.read_text().strip(),json.loads(args.jwks.read_text()),
                           args.issuer,args.audience,set(args.allowed_subject))
        result=advance(db,args.run,args.step,"approve",claims=claims)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
