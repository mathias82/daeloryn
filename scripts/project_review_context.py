"""Complete inventory of supported text sources for explicit whole-project review."""
import os
from pathlib import Path
from code_context import EXCLUDE_DIRS, EXCLUDE_NAMES, SENSITIVE
from project_analysis import NAME, analyze_local

MAX_FILES = 500
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 1024 * 1024
MAX_ENTRIES = 10000
SOURCE_EXTENSIONS = {'.java', '.kt', '.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.xml', '.gradle', '.kts'}
BUILD_NAMES = {'README.md', 'package.json', 'pyproject.toml', 'requirements.txt', 'Dockerfile'}


def snapshot(root, name):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError('Invalid repository name')
    trusted = os.path.realpath(os.fspath(root))
    normalized = os.path.abspath(os.path.join(trusted, name))
    if not normalized.startswith(trusted.rstrip(os.sep) + os.sep):
        raise ValueError('Repository must remain inside its trusted parent')
    analyze_local(root, name)
    base = Path(normalized)
    files, omitted, excluded = [], [], []
    total, entries = 0, 0

    def visit(directory, depth):
        nonlocal total, entries
        if depth > 20:
            raise ValueError('Review depth exceeds 20; select a smaller project')
        with os.scandir(directory) as iterator:
            children = []
            for entry in iterator:
                entries += 1
                if entries > MAX_ENTRIES:
                    raise ValueError('Review exceeds 10000 entries; select a smaller project')
                children.append(entry)
        for entry in sorted(children, key=lambda child: child.name):
            path = Path(entry.path)
            relative = path.relative_to(base).as_posix()
            if entry.is_symlink():
                excluded.append({'path': relative, 'reason': 'symbolic link'})
                continue
            if entry.is_dir(follow_symlinks=False):
                if entry.name.startswith('.') or entry.name in EXCLUDE_DIRS:
                    excluded.append({'path': relative, 'reason': 'hidden/dependency/build directory'})
                else:
                    visit(path, depth + 1)
                continue
            if not entry.is_file(follow_symlinks=False) or (path.suffix.lower() not in SOURCE_EXTENSIONS and path.name not in BUILD_NAMES):
                continue
            if path.name in EXCLUDE_NAMES or SENSITIVE.search(path.name):
                excluded.append({'path': relative, 'reason': 'sensitive filename'})
                continue
            size = entry.stat(follow_symlinks=False).st_size
            if len(files) >= MAX_FILES or size > MAX_FILE_BYTES or size + total > MAX_TOTAL_BYTES:
                omitted.append({'path': relative, 'reason': 'source budget exceeded'})
                continue
            try:
                with path.open('rb') as source:
                    raw = source.read(MAX_FILE_BYTES + 1)
                if len(raw) > MAX_FILE_BYTES or len(raw) + total > MAX_TOTAL_BYTES or b'\0' in raw:
                    omitted.append({'path': relative, 'reason': 'binary or oversized source'})
                    continue
                body = raw.decode('utf-8')
            except (OSError, UnicodeError):
                omitted.append({'path': relative, 'reason': 'unreadable or non-UTF-8 source'})
                continue
            lines = body.splitlines(keepends=True)
            redacted = ''.join('[REDACTED]\n' if SENSITIVE.search(line) else line for line in lines)
            files.append({'path': relative, 'source': redacted, 'line_count': len(lines)})
            total += len(raw)
    visit(base, 0)
    return {'files': files, 'omitted': omitted, 'excluded': excluded, 'bytes_read': total,
            'scope': 'supported project text sources, build files and README; dependencies, hidden paths, secrets and binary formats excluded',
            'all_eligible_files_included': not omitted}
