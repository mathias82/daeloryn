"""Explicit opt-in Git publication of an already reviewed local branch.

No implicit remote selection, force pushes or background publication.
"""
from pathlib import Path
import re
import subprocess
from engineering_executor import BRANCH

SHA = re.compile(r"[0-9a-f]{40}\Z")
REMOTE = re.compile(r"[A-Za-z0-9._-]{1,80}\Z")

def _git(root, *args):
    result=subprocess.run(["git",*args],cwd=str(root),capture_output=True,text=True,timeout=60,check=False)
    if result.returncode:
        raise RuntimeError("git command failed: "+args[0])
    return result.stdout.strip()

def publish(checkout, title, body, expected_commit, *, approved=False, remote="origin"):
    if approved is not True:
        raise PermissionError("explicit publication approval required")
    if not isinstance(expected_commit,str) or not SHA.fullmatch(expected_commit):
        raise ValueError("expected exact commit SHA")
    if not isinstance(remote,str) or not REMOTE.fullmatch(remote):
        raise ValueError("invalid remote")
    if not isinstance(title,str) or not 1<=len(title)<=120 or not isinstance(body,str) or len(body)>4000:
        raise ValueError("invalid PR metadata")
    root=Path(checkout).resolve(strict=True)
    if not (root/".git").is_dir() or (root/".git").is_symlink():
        raise ValueError("real git checkout required")
    branch=_git(root,"branch","--show-current")
    if not BRANCH.fullmatch(branch):
        raise ValueError("dedicated daeloryn branch required")
    if _git(root,"rev-parse","HEAD") != expected_commit:
        raise PermissionError("HEAD changed since approval")
    if _git(root,"status","--porcelain"):
        raise ValueError("commit changes before publishing")
    # No force, no automatic commit, no arbitrary remote URL accepted.
    _git(root,"remote","get-url",remote)
    _git(root,"push","--set-upstream",remote,branch)
    result=subprocess.run(["gh","pr","create","--draft","--head",branch,
                           "--title",title,"--body",body],
                          cwd=str(root),capture_output=True,text=True,timeout=90,check=False)
    if result.returncode:
        raise RuntimeError("push succeeded but draft PR creation failed; inspect GitHub before retry")
    return {"published":True,"draft_pr_created":True,"url":result.stdout.strip(),
            "commit":expected_commit,"branch":branch,
            "warning":"Approval covers the expected commit SHA, not the remote destination or a cryptographic CI attestation."}
