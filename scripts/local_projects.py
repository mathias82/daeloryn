"""Opt-in local project registry. No Git commands, source upload or project writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Lock

from project_analysis import NAME

MAX_PROJECTS = 100
MAX_ENTRIES = 10000
MAX_DEPTH = 8
EXCLUDED = {'.git', 'node_modules', '.venv', 'venv', 'target', 'build', 'dist', 'vendor'}


def real_directory(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise ValueError('Enter an absolute local directory path')
    path = Path(value).expanduser()
    if not path.is_absolute() or any(part == '..' for part in path.parts):
        raise ValueError('Use an absolute path without parent traversal')
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_dir():
        raise ValueError('Directory must exist and must not use symbolic links')
    return path.resolve(strict=True)


def project(value):
    path = real_directory(value)
    if not NAME.fullmatch(path.name):
        raise ValueError('Unsupported project name (use letters, digits, dots, underscores or hyphens)')
    git = path / '.git'
    if git.is_symlink() or not git.is_dir():
        raise ValueError('Select a Git checkout with a real .git directory; worktrees are not supported')
    markers = (("pom.xml", "java-maven"), ("build.gradle", "java-gradle"),
               ("build.gradle.kts", "java-gradle"), ("package.json", "node"),
               ("pyproject.toml", "python"), ("requirements.txt", "python"), ("go.mod", "go"))
    technologies = sorted({label for name, label in markers
                           if (path / name).is_file() and not (path / name).is_symlink()})
    return {'name': path.name, 'path': str(path), 'technologies': technologies}


def candidates(value, recursive=False):
    base = real_directory(value)
    if not recursive:
        return [project(str(base))]
    result, visited = [], 0
    stack = [(base, 0)]
    while stack:
        directory, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise ValueError('Folder search exceeds depth 8; choose a narrower folder')
        if (directory / '.git').is_dir() and not (directory / '.git').is_symlink():
            result.append(project(str(directory)))
            if len(result) > MAX_PROJECTS:
                raise ValueError('More than 100 projects; choose a narrower folder')
        with os.scandir(directory) as entries:
            for child in entries:
                visited += 1
                if visited > MAX_ENTRIES:
                    raise ValueError('Folder search exceeds 10000 entries; choose a narrower folder')
                if child.name.startswith('.') or child.name in EXCLUDED or child.is_symlink():
                    continue
                if child.is_dir(follow_symlinks=False):
                    stack.append((Path(child.path), depth + 1))
    return sorted(result, key=lambda row: row['path'])


def choose_directory():
    # Static AppleScript, no user-controlled script or shell interpolation.
    if sys.platform != 'darwin':
        raise RuntimeError('Native folder selection is available on macOS; enter a path instead')
    result = subprocess.run(['osascript', '-e',
        'try\nreturn POSIX path of (choose folder with prompt "Select a local project or projects folder for Daeloryn")\non error number -128\nreturn ""\nend try'],
        capture_output=True, text=True, timeout=120, check=True)
    return result.stdout.strip()


class ProjectRegistry:
    def __init__(self, file):
        self.file = Path(file).expanduser()
        self.lock = Lock()
        self.picker_lock = Lock()

    def _check_file(self):
        if not self.file.is_absolute() or any(p.is_symlink() for p in (self.file, *self.file.parents)):
            raise ValueError('Project registry must be an absolute non-symlink path')
        if self.file.exists() and (not self.file.is_file() or self.file.stat().st_size > 512 * 1024):
            raise ValueError('Invalid project registry')

    def _read(self):
        self._check_file()
        if not self.file.exists():
            return []
        data = json.loads(self.file.read_text(encoding='utf-8'))
        if not isinstance(data, list) or len(data) > MAX_PROJECTS or any(not isinstance(p, str) for p in data):
            raise ValueError('Invalid project registry')
        return data

    def list(self):
        with self.lock:
            rows = []
            for path in self._read():
                try:
                    rows.append(project(path))
                except (OSError, ValueError):
                    continue  # Deleted/moved projects are never re-authorized by name alone.
            return rows

    def add(self, paths, existing):
        if not isinstance(paths, list) or not paths or len(paths) > MAX_PROJECTS:
            raise ValueError('Select between 1 and 100 projects')
        selected = [project(path) for path in paths]
        with self.lock:
            saved = self._read()
            combined = list(dict.fromkeys(saved + [row['path'] for row in selected]))
            if len(combined) > MAX_PROJECTS:
                raise ValueError('Project registry limit is 100')
            names = {}
            saved_rows = []
            for path in saved:
                try:
                    saved_rows.append(project(path))
                except (ValueError, OSError):
                    continue
            if len({row['path'] for row in existing + saved_rows + selected}) > MAX_PROJECTS:
                raise ValueError('Combined project catalog limit is 100')
            for row in existing + saved_rows + selected:
                if row['name'] in names and names[row['name']] != row['path']:
                    raise ValueError('A different project has the same name; rename the checkout folder first')
                names[row['name']] = row['path']
            self.file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._check_file()
            fd, temporary = tempfile.mkstemp(prefix='.projects-', dir=self.file.parent)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as out:
                    json.dump(combined, out)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temporary, self.file)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return selected
