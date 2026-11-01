"""On-demand local-only full-file preview for an already approved review manifest.

Never calls a model. Never reads arbitrary local paths. A caller must present the
exact approved source digest and a path in that snapshot's selected file allowlist.
"""
import hashlib
import os
from pathlib import Path

from code_context import EXCLUDE_DIRS, EXCLUDE_NAMES, SENSITIVE

MAX_SOURCE_VIEW_BYTES = 512 * 1024
MAX_SOURCE_VIEW_LINES = 20000


def read_approved_source(root, repository, prepared, approved_sha256, file):
    if not isinstance(prepared, dict) or not isinstance(approved_sha256, str):
        raise ValueError("source review approval required")
    if prepared.get("repository") != repository or prepared.get("sha256") != approved_sha256:
        raise PermissionError("approved source snapshot changed; prepare the review again")
    allowed = prepared.get("files")
    if not isinstance(allowed, list) or not isinstance(file, str) or file not in allowed:
        raise PermissionError("file was not part of the approved source review")
    if (not file or len(file) > 500 or any(ord(ch) < 32 for ch in file) or
            "\\" in file or file.startswith("/")):
        raise ValueError("invalid checkout-relative source path")
    relative = Path(file)
    if (relative.is_absolute() or not relative.parts or
            any(part in ("..", ".") or part.startswith(".") or part in EXCLUDE_DIRS
                for part in relative.parts) or relative.name in EXCLUDE_NAMES or
            SENSITIVE.search(relative.name)):
        raise PermissionError("unsafe source path")
    base = Path(root).resolve(strict=True) / repository
    if base.is_symlink() or not base.is_dir():
        raise PermissionError("registered checkout unavailable")
    path = base.joinpath(*relative.parts)
    # Reject links anywhere in the ancestor chain, including a replaced parent.
    current = base
    for segment in relative.parts:
        current = current / segment
        if current.is_symlink():
            raise PermissionError("source file or parent is a symbolic link")
    if path.resolve(strict=True) != path or not path.is_file():
        raise PermissionError("source file changed since approval")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if st.st_size > MAX_SOURCE_VIEW_BYTES:
            raise ValueError("source file too large for safe full-class preview")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read(MAX_SOURCE_VIEW_BYTES + 1)
        if len(raw) > MAX_SOURCE_VIEW_BYTES or b"\0" in raw:
            raise ValueError("source is oversized or binary")
        text = raw.decode("utf-8")
    finally:
        os.close(fd)
    lines = text.splitlines()
    if len(lines) > MAX_SOURCE_VIEW_LINES:
        raise ValueError("too many source lines for full-class preview")
    # Local preview only; use the same defensive line redaction as project context.
    redacted = [number for number, line in enumerate(lines, 1) if SENSITIVE.search(line)]
    safe_lines = ["[REDACTED]" if number in set(redacted) else line
                  for number, line in enumerate(lines, 1)]
    return {
        "repository": repository, "file": file, "line_count": len(lines),
        "lines": safe_lines, "redacted_lines": redacted,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "local_only": True, "model_calls": 0,
        "warning": ("Read-only full local file preview. No source was sent to a provider. "
                    "Model-cited ranges are navigation aids, not verified defects. "
                    "Sensitive-line redaction is heuristic."),
    }
