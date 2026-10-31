"""Apply a reviewed local patch with a digest and a clean dedicated branch."""
from pathlib import Path
from engineering_executor import apply_approved
from patch_workspace import verify_preview

def apply(root, repository, path, replacement, approved_sha256, branch):
    checked=verify_preview(root,repository,path,replacement,approved_sha256)
    checkout=Path(root).resolve(strict=True)/repository
    file=checkout/path
    original=file.read_text(encoding="utf-8")
    # apply_approved independently validates digest, source and clean git state.
    return apply_approved(checkout,path,original,replacement,checked["sha256"],branch)
