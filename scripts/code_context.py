"""Bounded, read-only source context for explicit local Git checkouts.

Never execute repository code or follow symlinks; source text is untrusted.
"""
from pathlib import Path
import re
from project_analysis import analyze_local

EXTENSIONS = {".java", ".kt", ".py", ".ts", ".tsx", ".js", ".jsx", ".go"}
EXCLUDE_DIRS = {".git", "node_modules", "target", "build", "dist", ".venv",
                "vendor", "coverage", ".next"}
EXCLUDE_NAMES = {".env", ".env.local", ".npmrc", ".pypirc", "id_rsa",
                 "credentials.json", "secrets.json", "application-prod.yml"}
MAX_FILES = 80
MAX_FILE_BYTES = 24 * 1024
MAX_TOTAL_BYTES = 256 * 1024
MAX_DEPTH = 12
SENSITIVE = re.compile(r"(secret|credential|password|private.?key|token|\.env)", re.I)
CLASS = re.compile(r"\b(class|interface|enum|record)\s+([A-Za-z_][A-Za-z_0-9]*)")
IMPORT = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][\w.]*)", re.M)

def scan(root, name):
    analyze_local(root, name)
    base = (Path(root).resolve(strict=True) / name).resolve(strict=True)
    files = []
    remaining = MAX_TOTAL_BYTES
    skipped = 0
    def visit(directory, depth):
        nonlocal remaining, skipped
        if depth > MAX_DEPTH:
            skipped += 1
            return
        for child in sorted(directory.iterdir()):
            if child.is_symlink():
                skipped += 1
                continue
            if child.is_dir():
                if child.name not in EXCLUDE_DIRS and not child.name.startswith("."):
                    visit(child, depth + 1)
                continue
            if not child.is_file() or child.suffix.lower() not in EXTENSIONS:
                continue
            if child.name in EXCLUDE_NAMES or SENSITIVE.search(child.name):
                skipped += 1
                continue
            if len(files) >= MAX_FILES or remaining <= 0:
                skipped += 1
                continue
            size = child.stat().st_size
            if size > MAX_FILE_BYTES or size > remaining:
                skipped += 1
                continue
            raw = child.read_bytes()
            if len(raw) > MAX_FILE_BYTES or b"\0" in raw:
                skipped += 1
                continue
            try:
                body = raw.decode("utf-8")
            except UnicodeDecodeError:
                skipped += 1
                continue
            # Prevent accidentally returning common inline credentials.
            lines = body.splitlines()
            redacted = ["[REDACTED]" if SENSITIVE.search(line) else line for line in lines]
            excerpt = "\n".join(redacted)
            relative = child.relative_to(base).as_posix()
            files.append({"path": relative, "line_count": len(lines),
                          "excerpt": excerpt,
                          "symbols": [m.group(2) for m in CLASS.finditer(body)][:40],
                          "imports": list(dict.fromkeys(IMPORT.findall(body)))[:40]})
            remaining -= len(raw)
    visit(base, 0)
    return {"repository": name, "source": "local-checkout",
            "files": files, "files_read": len(files), "skipped": skipped,
            "bytes_budget": MAX_TOTAL_BYTES, "execution": "not_run",
            "warning": "Untrusted source; heuristic redaction is not a secret scanner. Review before sending to AI."}
