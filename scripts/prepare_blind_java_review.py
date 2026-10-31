#!/usr/bin/env python3
"""Create clean, separate baseline and Copilot-specialist review workspaces.

Only the selected Java source is copied. Gold answers and benchmark rubrics
are deliberately kept outside both model-visible workspaces.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from agents import catalog, format_copilot

ROOT = Path(__file__).resolve().parents[1]


def prepare(source: Path, output: Path) -> dict:
    source = source.expanduser().resolve(strict=True)
    output = output.expanduser().resolve(strict=False)
    if not source.is_file() or source.suffix.lower() != ".java":
        raise ValueError("source must be an existing Java source file")
    if output == ROOT or ROOT in output.parents:
        raise ValueError("output must be outside the Daeloryn checkout")
    if output.exists():
        raise FileExistsError(f"output already exists: {output}; select a new trial directory")

    reviewers = [(meta, body) for meta, body in catalog("java")
                 if meta["name"] == "java-reviewer"]
    if len(reviewers) != 1:
        raise ValueError("expected exactly one java-reviewer definition")
    metadata, instructions = reviewers[0]
    source_bytes = source.read_bytes()
    agent_file = format_copilot(metadata, instructions).encode("utf-8")
    result = {
        "fixture": source.name,
        "fixture_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "agent": metadata["name"],
        "agent_definition_sha256": hashlib.sha256(agent_file).hexdigest(),
        "arms": ["baseline", "daeloryn"],
        "status": "prepared_only_no_model_runs",
    }

    output.mkdir(parents=True)
    try:
        baseline = output / "baseline"
        specialist = output / "daeloryn"
        baseline.mkdir()
        specialist.mkdir()
        (baseline / source.name).write_bytes(source_bytes)
        (specialist / source.name).write_bytes(source_bytes)
        agent_dir = specialist / ".github" / "agents"
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
                        help="Java fixture to copy to each arm (not a gold answer)")
    parser.add_argument("--output", type=Path, required=True,
                        help="New trial root directory outside this repository")
    args = parser.parse_args()
    try:
        result = prepare(args.source, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(status=1, message=f"ERROR: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
