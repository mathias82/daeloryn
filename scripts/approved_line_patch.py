"""Explicitly approved local source-line patch application on a new Git branch.

The assistant may suggest an exact code replacement, but never writes on
ordinary chat/review. No model calls, commits, pushes or tests here. The caller
must additionally enable local writes and approve this concrete diff.
"""
import hashlib
import os
from pathlib import Path
import secrets
import stat

from approved_source_view import read_approved_source, MAX_SOURCE_VIEW_BYTES
from engineering_executor import BRANCH, command

MAX_PATCH_BYTES = 12000
MAX_EDIT_LINES = 80
SUFFIXES = {".java", ".kt", ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".xml", ".gradle", ".kts"}


def apply_line_patch(root, repository, prepared, approved_sha256, file,
                     start, end, original, replacement, source_sha256, branch,
                     *, approved=False):
    if approved is not True:
        raise PermissionError("Approve the exact patch diff explicitly before writing files")
    if not isinstance(branch, str) or not BRANCH.fullmatch(branch):
        raise ValueError("A new daeloryn/<name> branch is required")
    if not isinstance(prepared, dict) or prepared.get("scope") == "docs":
        raise PermissionError("Docs-only context cannot authorize source edits")
    if not isinstance(file, str) or Path(file).suffix.lower() not in SUFFIXES:
        raise PermissionError("Only approved source/build files can be modified")
    if (type(start) is not int or type(end) is not int or
            start < 1 or end < start or end-start >= MAX_EDIT_LINES):
        raise ValueError("Invalid or too-large source line range")
    if not isinstance(original, str) or not isinstance(replacement, str):
        raise ValueError("Original and replacement must be strings")
    if (not original or not replacement or original == replacement or
            len(original.encode("utf-8")) > MAX_PATCH_BYTES or
            len(replacement.encode("utf-8")) > MAX_PATCH_BYTES or
            "\r" in original or "\r" in replacement or "\0" in replacement):
        raise ValueError("Invalid, unchanged or oversized source replacement")
    if (not isinstance(source_sha256,str) or len(source_sha256)!=64 or
            any(c not in "0123456789abcdef" for c in source_sha256)):
        raise ValueError("Full source SHA-256 is required")

    # These checks reject unapproved names, stale manifest, symlink parents,
    # traversal, oversized, binary and sensitive filenames.
    view = read_approved_source(root,repository,prepared,approved_sha256,file)
    if source_sha256 != view["source_sha256"]:
        raise PermissionError("The source changed; repeat preparation and explicit approval")
    if end > view["line_count"]:
        raise ValueError("Source range exceeds the reviewed file")
    if any(start <= n <= end for n in view["redacted_lines"]):
        raise PermissionError("Sensitive or redacted source lines cannot be modified")
    base = Path(root).resolve(strict=True) / repository
    if not (base/".git").is_dir() or (base/".git").is_symlink():
        raise PermissionError("A real local Git checkout is required to apply a patch")
    target = base.joinpath(*Path(file).parts)
    raw = target.read_bytes()
    if len(raw)>MAX_SOURCE_VIEW_BYTES or hashlib.sha256(raw).hexdigest()!=source_sha256:
        raise PermissionError("File changed before write")
    text = raw.decode("utf-8")
    old_lines = text.splitlines(keepends=True)
    original_lines = "\n".join(line.rstrip("\r\n") for line in old_lines[start-1:end])
    if original_lines != original:
        raise PermissionError("Exact original lines do not match current source")
    separator = "\r\n" if b"\r\n" in raw else "\n"
    was_terminated = old_lines[end-1].endswith("\n")
    new_bytes = (separator.join(replacement.split("\n")) +
                 (separator if was_terminated else "")).encode("utf-8")
    updated = b"".join(x.encode("utf-8") for x in old_lines[:start-1]) + new_bytes + \
              b"".join(x.encode("utf-8") for x in old_lines[end:])
    if len(updated)>MAX_SOURCE_VIEW_BYTES:
        raise ValueError("The resulting file is too large")
    # A dirty checkout is a hard stop; avoid trampling user work.
    status = command(["git", "status", "--porcelain"], base, timeout=20)
    if status["returncode"]!=0 or status["output"].strip():
        raise PermissionError("Working tree must be clean before creating an isolated fix branch")
    switch = command(["git", "switch", "-c", branch], base, timeout=20)
    if switch["returncode"]!=0:
        raise PermissionError("Could not create the requested new fix branch")
    if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=source_sha256:
        raise PermissionError("File changed during branch creation; no patch written")
    # Atomic same-directory write; preserve executable bits and prevent a partial
    # file if a short write/process failure occurs.
    tmp = target.with_name(".daeloryn-patch-"+secrets.token_hex(12)+".tmp")
    fd = None
    try:
        mode = stat.S_IMODE(target.stat().st_mode)
        fd=os.open(tmp, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0), 0o600)
        with os.fdopen(fd,"wb",closefd=False) as output:
            output.write(updated)
            output.flush()
            os.fsync(output.fileno())
        os.fchmod(fd,mode)
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=source_sha256:
            raise PermissionError("File changed concurrently; no patch written")
        os.replace(tmp,target)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp.exists():
            tmp.unlink()
    return {
        "status":"applied", "repository":repository, "file":file,
        "line_start":start, "line_end":end, "branch":branch,
        "before_sha256":source_sha256,
        "after_sha256":hashlib.sha256(updated).hexdigest(),
        "changed_files":[file], "source_modified":True,
        "tests_executed":False, "commit_created":False, "pull_request_created":False,
        "provider_calls":0,
        "warning":"Approved fix applied locally to a new Git branch. Run tests separately; no tests, commits, pushes or PRs were performed. Review snapshot is now stale.",
    }
