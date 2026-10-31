#!/usr/bin/env python3
"""Prepare clean Copilot baseline and Daeloryn review workspaces.

The two arms receive byte-identical, explicitly selected project source/build
files. No gold answers, previous transcripts or AI instructions are copied.
The tool never invokes AI models or claims model evaluation results.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from agents import catalog, format_copilot

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_EXTENSIONS = {".java", ".xml", ".properties", ".gradle", ".kts",
                      ".yaml", ".yml"}
EXCLUDED_DIRS = {".github", ".git", ".codex", ".claude", ".gemini",
                 ".venv", "target", "build", "node_modules", "__pycache__"}
EXCLUDED_NAMES = ("gold", "ground-truth", "answer-key", "rubric",
                  "agent-instruction", "copilot-instruction", "benchmark-result")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validated_file(root, relative):
    relative = Path(relative)
    parts = relative.parts
    if (not parts or relative.is_absolute() or ".." in parts
            or any(part.startswith(".") or part in EXCLUDED_DIRS for part in parts)
            or any(word in relative.name.lower() for word in EXCLUDED_NAMES)
            or relative.suffix.lower() not in ALLOWED_EXTENSIONS):
        raise ValueError("unsafe or unsupported project context: " + str(relative))
    path = root / relative
    # Both direct and parent-directory symlinks are excluded; never follow
    # arbitrary outside-workspace source paths during an opt-in copy.
    if not path.is_file() or path.resolve() != path.absolute():
        raise ValueError("context must be a regular file inside project: " + str(relative))
    return relative, path.read_bytes()


def prepare(source: Path, output: Path, project_root=None, include=()) -> dict:
    source = source.expanduser().resolve(strict=True)
    output = output.expanduser().resolve(strict=False)
    if not source.is_file() or source.suffix.lower() != ".java":
        raise ValueError("source must be an existing Java source file")
    if output == ROOT or ROOT in output.parents:
        raise ValueError("output must be outside the Daeloryn checkout")
    if output.exists():
        raise FileExistsError(f"output already exists: {output}; select a new trial directory")
    if include and project_root is None:
        raise ValueError("--include requires --project-root")

    if project_root is None:
        root = source.parent
        source_relative = Path(source.name)
    else:
        root = Path(project_root).expanduser().resolve(strict=True)
        if not root.is_dir() or root not in source.parents:
            raise ValueError("source must be inside --project-root")
        source_relative = source.relative_to(root)
    if output == root or root in output.parents:
        raise ValueError("trial directory must be outside source project")

    # Validate *all* paths and prepare their bytes before writing the trial.
    files = {}
    for requested in [source_relative, *list(include)]:
        relative, data = validated_file(root, requested)
        files[relative.as_posix()] = data

    reviewers = [(meta, body) for meta, body in catalog("java")
                 if meta["name"] == "java-reviewer"]
    if len(reviewers) != 1:
        raise ValueError("expected exactly one java-reviewer definition")
    metadata, instructions = reviewers[0]
    agent_file = format_copilot(metadata, instructions).encode("utf-8")
    result = {
        "fixture": source_relative.as_posix(),
        "fixture_sha256": sha256(files[source_relative.as_posix()]),
        "context_sha256": {name: sha256(data) for name, data in sorted(files.items())},
        "agent": metadata["name"],
        "agent_definition_sha256": sha256(agent_file),
        "arms": ["baseline", "daeloryn"],
        "status": "prepared_only_no_model_runs",
    }

    output.mkdir(parents=True)
    try:
        for arm in result["arms"]:
            destination = output / arm
            destination.mkdir()
            for name, data in files.items():
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        agent_dir = output / "daeloryn" / ".github" / "agents"
        agent_dir.mkdir(parents=True)
        (agent_dir / "java-reviewer.agent.md").write_bytes(agent_file)
        (output / "manifest.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    except BaseException:
        shutil.rmtree(output)
        raise
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="Java source file, not a ground-truth reference")
    parser.add_argument("--output", type=Path, required=True,
                        help="fresh trial directory outside the source and Daeloryn checkout")
    parser.add_argument("--project-root", type=Path,
                        help="project root; preserves source-relative paths")
    parser.add_argument("--include", action="append", default=[],
                        help="explicit project-relative build/context file; repeatable")
    args = parser.parse_args()
    try:
        result = prepare(args.source, args.output, args.project_root, args.include)
    except (OSError, ValueError) as exc:
        parser.exit(status=1, message=f"ERROR: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
