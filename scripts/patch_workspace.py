"""Read-only local patch preview with exact-source revalidation.

No AI transmission, repository write or command execution occurs here.
"""
import hashlib
from pathlib import Path
from patch_proposal import proposal

MAX_SOURCE_BYTES=12000

def read_source(root, repository, path):
    """Read just one confined source file, with a byte bound and no mutation."""
    if not isinstance(repository,str) or not repository or "/" in repository or "\\" in repository or repository in (".",".."):
        raise ValueError("invalid repository")
    proposal(path,"placeholder","replacement")
    base=Path(root).resolve(strict=True)
    checkout=base/repository
    if checkout.is_symlink() or not checkout.is_dir() or not (checkout/".git").is_dir() or (checkout/".git").is_symlink():
        raise ValueError("real local git checkout required")
    parts=Path(path).parts
    if any(checkout.joinpath(*parts[:i]).is_symlink() for i in range(1,len(parts)+1)):
        raise ValueError("source path must not contain symbolic links")
    file=checkout/path
    if not file.is_file():
        raise ValueError("Selected source file was not found; use its exact checkout-relative path")
    if checkout.resolve(strict=True) not in file.resolve(strict=True).parents:
        raise ValueError("unsafe file")
    with file.open('rb') as handle:
        raw=handle.read(MAX_SOURCE_BYTES+1)
    if len(raw)>MAX_SOURCE_BYTES:
        raise ValueError("Selected source exceeds 12000 bytes; complete-file handoff is unavailable")
    if not raw or b'\0' in raw:
        raise ValueError("Selected source must be a nonempty text file")
    try:
        return raw.decode('utf-8')
    except UnicodeError as exc:
        raise ValueError("Selected source must use UTF-8 encoding") from exc


def preview(root, repository, path, replacement):
    if not isinstance(replacement,str) or not replacement or len(replacement.encode("utf-8"))>MAX_SOURCE_BYTES:
        raise ValueError("invalid replacement")
    original=read_source(root,repository,path)
    return proposal(path,original,replacement)

def verify_preview(root, repository, path, replacement, digest):
    result=preview(root,repository,path,replacement)
    if not isinstance(digest,str) or digest!=result["sha256"]:
        raise PermissionError("source changed or patch approval invalid")
    return result
