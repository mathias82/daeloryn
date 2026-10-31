"""Opt-in local patch application, test invocation and draft PR creation.

Commands run with the current user's privileges; this is NOT a sandbox.
Use only trusted checkouts and explicit human approvals.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

BRANCH = re.compile(r"daeloryn/[a-z0-9][a-z0-9-]{0,50}\Z")
TESTS = {"python": ["python3","-m","unittest","discover","-s","tests"],
         "maven": ["mvn","-B","test"], "npm": ["npm","test","--","--runInBand"]}

def command(args, cwd, timeout=120):
    result=subprocess.run(args,cwd=str(cwd),capture_output=True,text=True,
                          timeout=timeout,check=False)
    return {"returncode":result.returncode,
            "output":(result.stdout+"\n"+result.stderr)[:12000]}

def _safe_file(checkout, relative):
    root=Path(checkout).resolve(strict=True)
    if not (root/".git").is_dir() or (root/".git").is_symlink():
        raise ValueError("real git checkout required")
    path=root/relative
    if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent != root and root not in path.resolve(strict=True).parents:
        raise ValueError("unsafe file")
    return root,path

def apply_approved(checkout, path, before, after, approved_digest, branch):
    from patch_proposal import proposal
    preview=proposal(path,before,after)
    if approved_digest != preview["sha256"] or not BRANCH.fullmatch(branch):
        raise PermissionError("exact patch approval and safe branch name required")
    root,target=_safe_file(checkout,path)
    if len(target.read_bytes())>12000 or target.read_text(encoding="utf-8")!=before:
        raise ValueError("file changed since preview")
    if command(["git","status","--porcelain"],root)["output"].strip():
        raise ValueError("checkout must be clean")
    if command(["git","switch","-c",branch],root)["returncode"]!=0:
        raise RuntimeError("could not create isolated branch")
    # Exclusive creation is not needed: verified existing file, re-check immediately before write.
    if target.read_text(encoding="utf-8")!=before:
        raise ValueError("source changed during branch creation")
    target.write_text(after,encoding="utf-8")
    return {"branch":branch,"path":path,"sha256":approved_digest,
            "applied":True,"tests_executed":False,"pr_created":False}

def run_tests(checkout, suite, *, approved=False):
    if approved is not True or suite not in TESTS:
        raise PermissionError("explicit test command approval required")
    root=Path(checkout).resolve(strict=True)
    if not (root/".git").is_dir():
        raise ValueError("git checkout required")
    result=command(TESTS[suite],root,timeout=180)
    return {"suite":suite,"command":TESTS[suite],"verified":result["returncode"]==0,
            "returncode":result["returncode"],"output":result["output"],
            "warning":"Executed local project code with host user privileges; NOT sandboxed."}

def create_draft_pr(checkout, title, body, *, approved=False, verified_tests=None):
    if approved is not True or not isinstance(verified_tests,dict) or verified_tests.get("verified") is not True:
        raise PermissionError("PR approval and successful test evidence required")
    if not isinstance(title,str) or not 1<=len(title)<=120 or not isinstance(body,str) or len(body)>4000:
        raise ValueError("invalid PR metadata")
    root=Path(checkout).resolve(strict=True)
    if not (root/".git").is_dir():
        raise ValueError("git checkout required")
    branch=command(["git","branch","--show-current"],root)
    if branch["returncode"] or not BRANCH.fullmatch(branch["output"].strip()):
        raise ValueError("expected dedicated daeloryn branch")
    # Caller must commit and push explicitly; no implicit publication of code.
    result=command(["gh","pr","create","--draft","--title",title,"--body",body],root)
    if result["returncode"]!=0:
        raise RuntimeError("GitHub draft PR creation failed: "+result["output"][:500])
    return {"pr_created":True,"url":result["output"].strip(),"tests_verified":True}
