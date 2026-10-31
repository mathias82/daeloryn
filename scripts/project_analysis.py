"""Read-only project fingerprint from bounded metadata and conventional marker files."""
from pathlib import Path
import re

NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
MARKERS = {"pom.xml":"Java / Maven","build.gradle":"Java / Gradle",
           "build.gradle.kts":"Java / Gradle","package.json":"Node / frontend",
           "pyproject.toml":"Python","requirements.txt":"Python",
           "go.mod":"Go","Dockerfile":"Docker","Chart.yaml":"Helm"}
MAX_FILES = 200

def analyze_local(root, name):
    if not isinstance(name,str) or not NAME.fullmatch(name):
        raise ValueError("invalid repository name")
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("invalid root")
    root = root.resolve(strict=True)
    path = root / name
    if path.is_symlink() or not path.is_dir() or path.resolve(strict=True).parent != root:
        raise ValueError("repository outside root")
    if (path/".git").is_symlink() or not (path/".git").is_dir():
        raise ValueError("not a supported local checkout")
    found = []
    for filename,label in MARKERS.items():
        file = path / filename
        if not file.is_symlink() and file.is_file():
            found.append({"file":filename,"technology":label})
    dirs = []
    for item in sorted(path.iterdir()):
        if len(dirs) >= MAX_FILES:
            raise ValueError("too many top-level entries")
        if item.name.startswith(".") or item.is_symlink():
            continue
        if item.is_dir():
            dirs.append(item.name)
    return {"repository":name,"source":"local-checkout",
            "technology_markers":found,"top_level_directories":dirs,
            "files_read":0,"execution":"not_run",
            "limitations":"Top-level names only; no source code inspection"}
