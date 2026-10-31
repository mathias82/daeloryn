"""Privacy-first preflight for optional AI review context.

This module never sends data to a model. An explicit, separate approval
and transport implementation is required before any source disclosure.
"""
import hashlib
from code_context import scan

MAX_PREVIEW_FILES = 20
MAX_PREVIEW_CHARS = 12000

def preflight(root, repository):
    context = scan(root, repository)
    entries = []
    total = 0
    for file in context["files"]:
        if len(entries) >= MAX_PREVIEW_FILES:
            break
        excerpt = file["excerpt"]
        if total + len(excerpt) > MAX_PREVIEW_CHARS:
            continue
        entries.append({"file": file["path"],
                        "lines": file["line_count"],
                        "sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                        "characters": len(excerpt)})
        total += len(excerpt)
    return {"repository": repository, "files": entries,
            "total_characters": total, "approval_required": True,
            "approved": False, "source_transmitted": False,
            "model_invoked": False, "execution": "not_run",
            "warning": "Preview is metadata only. Heuristic redaction does not guarantee secrets are removed. "
                       "Never send code to a remote model without independent secret scanning and explicit consent."}
