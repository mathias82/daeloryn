"""Opt-in read-only GitHub repository catalog via an already authenticated gh CLI.

No token handling, clone, checkout, mutation or arbitrary shell execution.
"""
import json
import re
import shutil
import subprocess

FULL_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
MAX_BYTES = 512 * 1024

def list_github_repositories(executable=None, runner=subprocess.run):
    executable = executable or shutil.which("gh")
    if not executable:
        raise RuntimeError("GitHub CLI (gh) not installed")
    result = runner([executable, "api", "--method", "GET",
                     "user/repos?per_page=100&page=1&sort=updated&direction=desc"],
                    capture_output=True, timeout=20, check=False)
    if result.returncode != 0 or len(result.stdout) > MAX_BYTES:
        raise RuntimeError("GitHub repository catalog unavailable")
    try:
        data = json.loads(result.stdout)
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("Invalid GitHub response") from exc
    if not isinstance(data, list):
        raise RuntimeError("Invalid GitHub catalog")
    output = []
    for item in data:
        if not isinstance(item, dict):
            raise RuntimeError("Invalid repository record")
        name = item.get("full_name")
        if not isinstance(name, str) or not FULL_NAME.fullmatch(name):
            raise RuntimeError("Invalid repository name")
        if item.get("archived") is True or item.get("disabled") is True:
            continue
        output.append({"name": name, "private": item.get("private") is True,
                       "description": item.get("description") if isinstance(item.get("description"), str) else "",
                       "language": item.get("language") if isinstance(item.get("language"), str) else "",
                       "source": "github"})
    return output

def recommend_github(task, repositories):
    from repository_router import suggest
    if not isinstance(repositories, list):
        raise ValueError("invalid catalog")
    # Matching uses repository name and public metadata only, never source code.
    normalized = [{"name": r["name"], "technologies":
                   ["java-maven"] if r.get("language", "").lower() == "java" else
                   ["python"] if r.get("language", "").lower() == "python" else
                   ["node"] if r.get("language", "").lower() in ("typescript", "javascript") else []}
                  for r in repositories]
    decision = suggest(task, normalized)
    if decision["repository"] is not None:
        name = decision["repository"]["name"]
        decision["repository"] = next(r for r in repositories if r["name"] == name)
    return decision
