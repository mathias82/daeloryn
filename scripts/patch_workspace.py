"""Read-only local patch preview with exact-source revalidation.

No AI transmission, repository write or command execution occurs here.
"""
import hashlib
from pathlib import Path
from patch_proposal import proposal

MAX_SOURCE_BYTES=12000

def preview(root, repository, path, replacement):
    if not isinstance(repository,str) or not repository or "/" in repository or "\\" in repository or repository in (".",".."):
        raise ValueError("invalid repository")
    if not isinstance(replacement,str) or not replacement or len(replacement.encode("utf-8"))>MAX_SOURCE_BYTES:
        raise ValueError("invalid replacement")
    # proposal validates path before any read.
    proposal(path,"placeholder","replacement")
    base=Path(root).resolve(strict=True)
    checkout=base/repository
    if checkout.is_symlink() or not checkout.is_dir() or not (checkout/".git").is_dir():
        raise ValueError("real local git checkout required")
    file=checkout/path
    if file.is_symlink() or not file.is_file() or checkout.resolve(strict=True) not in file.resolve(strict=True).parents:
        raise ValueError("unsafe file")
    if file.stat().st_size>MAX_SOURCE_BYTES:
        raise ValueError("source file too large")
    original=file.read_bytes().decode("utf-8")
    return proposal(path,original,replacement)

def verify_preview(root, repository, path, replacement, digest):
    result=preview(root,repository,path,replacement)
    if not isinstance(digest,str) or digest!=result["sha256"]:
        raise PermissionError("source changed or patch approval invalid")
    return result
