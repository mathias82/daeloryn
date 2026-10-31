"""Read-only local repository discovery and conservative task-based suggestions.

No GitHub tokens, clone, network access, git subprocesses or repository writes.
Operators explicitly configure trusted local checkout roots.
"""
import os
from pathlib import Path
import re

MAX_REPOS = 100
MAX_ROOTS = 10
TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)

def discover(roots):
    if not isinstance(roots, (list, tuple)) or len(roots) > MAX_ROOTS:
        raise ValueError("invalid repository roots")
    results = []
    seen = set()
    for root in roots:
        path = Path(root)
        if path.is_symlink() or not path.is_dir():
            raise ValueError("repository root must be an existing non-symlink directory")
        root_path = path.resolve(strict=True)
        for child in sorted(root_path.iterdir()):
            if len(results) >= MAX_REPOS:
                raise ValueError("repository catalog exceeds limit")
            if child.is_symlink() or not child.is_dir():
                continue
            # Do not traverse beyond configured root or follow .git redirects.
            git = child / ".git"
            if git.is_symlink() or not git.is_dir():
                continue
            canonical = child.resolve(strict=True)
            if root_path not in canonical.parents or str(canonical) in seen:
                continue
            seen.add(str(canonical))
            markers = []
            for filename, label in (("pom.xml", "java-maven"), ("build.gradle", "java-gradle"),
                                    ("build.gradle.kts", "java-gradle"), ("package.json", "node"),
                                    ("pyproject.toml", "python"), ("requirements.txt", "python"),
                                    ("go.mod", "go")):
                marker = child / filename
                if marker.is_file() and not marker.is_symlink():
                    markers.append(label)
            results.append({"name": child.name, "path": str(canonical),
                            "technologies": sorted(set(markers))})
    return results

def suggest(task, repositories):
    if not isinstance(task, str) or not task.strip() or len(task) > 3000:
        raise ValueError("invalid task")
    if not isinstance(repositories, list):
        raise ValueError("invalid repositories")
    words = set(w.lower() for w in TOKEN.findall(task))
    scored = []
    for repo in repositories:
        if not isinstance(repo, dict) or not isinstance(repo.get("name"), str):
            raise ValueError("invalid repository metadata")
        name_tokens = set(w.lower() for w in TOKEN.findall(repo["name"]))
        score = len(words & name_tokens) * 3
        technologies = repo.get("technologies", [])
        if not isinstance(technologies, list) or not all(isinstance(t,str) for t in technologies):
            raise ValueError("invalid repository technologies")
        if "java" in words and any(t.startswith("java-") for t in technologies):
            score += 1
        if "python" in words and "python" in technologies:
            score += 1
        if ("react" in words or "typescript" in words) and "node" in technologies:
            score += 1
        if score:
            scored.append((score, repo["name"], repo))
    scored.sort(key=lambda row: (-row[0], row[1]))
    if not scored or (len(scored)>1 and scored[0][0] == scored[1][0]):
        return {"repository": None, "reason": "No unique matching repository",
                "requires_confirmation": True, "execution": "not_run"}
    return {"repository": scored[0][2], "reason": "Repository name or technology matched",
            "requires_confirmation": True, "execution": "not_run"}
