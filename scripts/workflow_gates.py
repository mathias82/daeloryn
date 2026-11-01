"""Fail-closed workflow authorization for local engineering operations.

This is a local Python API, not an HTTP endpoint or durable permission store.
"""
import hashlib
import hmac
import json
from dataclasses import dataclass, replace
from pathlib import Path

STAGES=("prepared","patch_approved","tests_verified","publication_approved","published")

@dataclass(frozen=True)
class Evidence:
    checkout: str
    branch: str
    patch_sha256: str
    commit_sha: str = ""
    stage: str = "prepared"
    tests_sha256: str = ""

def _digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def approve_patch(evidence, supplied_sha256):
    if evidence.stage!="prepared" or not hmac.compare_digest(evidence.patch_sha256,supplied_sha256):
        raise PermissionError("exact patch approval required")
    return replace(evidence,stage="patch_approved")

def verify_tests(evidence, result, commit_sha):
    if evidence.stage!="patch_approved":
        raise PermissionError("patch must be approved first")
    if not isinstance(result,dict) or result.get("verified") is not True or result.get("containerized") is not True:
        raise PermissionError("successful containerized tests required")
    if not isinstance(commit_sha,str) or len(commit_sha)!=40 or any(c not in "0123456789abcdef" for c in commit_sha):
        raise ValueError("valid commit SHA required")
    return replace(evidence,stage="tests_verified",commit_sha=commit_sha,tests_sha256=_digest(result))

def approve_publication(evidence, expected_commit):
    if evidence.stage!="tests_verified" or not hmac.compare_digest(evidence.commit_sha,expected_commit):
        raise PermissionError("exact tested commit approval required")
    return replace(evidence,stage="publication_approved")

def publish_approved(evidence, title, body, *, publish):
    if evidence.stage!="publication_approved":
        raise PermissionError("publication approval required")
    root=Path(evidence.checkout).resolve(strict=True)
    if not (root/".git").is_dir():
        raise ValueError("git checkout required")
    result=publish(root,title,body,evidence.commit_sha,approved=True)
    return replace(evidence,stage="published"),result
