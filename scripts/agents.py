#!/usr/bin/env python3
"""Dependency-free catalog validator and safe Codex/Claude/Copilot adapter installer."""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = {"java", "react", "shared"}
KEYS = {"name", "description", "scope"}
SLUG = re.compile(r"^[a-z][a-z0-9-]{2,63}$")

def parse(path):
    content = path.read_text(encoding="utf-8")
    pieces = content.split("---", 2)
    if len(pieces) != 3 or pieces[0].strip():
        raise ValueError(f"{path}: missing frontmatter")
    meta = {}
    for line in pieces[1].strip().splitlines():
        if ":" not in line:
            raise ValueError(f"{path}: malformed metadata")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if key in meta or key not in KEYS or not value:
            raise ValueError(f"{path}: invalid field {key}")
        meta[key] = value
    if set(meta) != KEYS or not SLUG.fullmatch(meta["name"]):
        raise ValueError(f"{path}: missing or invalid fields")
    if meta["scope"] not in MODULES or path.parent.name != meta["scope"] or path.stem != meta["name"]:
        raise ValueError(f"{path}: scope or name/path mismatch")
    body = pieces[2].strip()
    if len(body) < 200:
        raise ValueError(f"{path}: instructions too short")
    return meta, body

def catalog(module="all"):
    paths = sorted((ROOT / "agents").glob("*/*.md"))
    selected = []
    seen = set()
    for path in paths:
        meta, body = parse(path)
        if meta["name"] in seen:
            raise ValueError(f"duplicate agent: {meta['name']}")
        seen.add(meta["name"])
        if module in ("all", meta["scope"]):
            selected.append((meta, body))
    if not selected:
        raise ValueError("no agents found")
    return selected

def format_codex(meta, body):
    # JSON strings are valid TOML basic string values; no external TOML writer needed.
    return "\n".join([
        "name = " + json.dumps(meta["name"]),
        "description = " + json.dumps(meta["description"]),
        "developer_instructions = " + json.dumps(body),
        "",
    ])

def format_claude(meta, body):
    return "---\nname: " + meta["name"] + "\ndescription: " + meta["description"] + "\n---\n\n" + body + "\n"

def format_copilot(meta, body):
    return "---\nname: " + meta["name"] + "\ndescription: " + meta["description"] + "\n---\n\n" + body + "\n"

def install(target, module, tool, force=False):
    if target.is_symlink():
        raise ValueError("target cannot be a symlink")
    target = target.resolve()
    if not target.is_dir():
        raise ValueError("target must be an existing directory")
    output = []
    for meta, body in catalog(module):
        if tool in ("codex", "both", "all"):
            output.append((target / ".codex" / "agents" / (meta["name"] + ".toml"), format_codex(meta, body)))
        if tool in ("claude", "both", "all"):
            output.append((target / ".claude" / "agents" / (meta["name"] + ".md"), format_claude(meta, body)))
        if tool in ("copilot", "all"):
            output.append((target / ".github" / "agents" / (meta["name"] + ".agent.md"), format_copilot(meta, body)))
    # Preflight everything before any write.
    for path, _ in output:
        if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
            raise ValueError(f"symlink destination rejected: {path}")
        if path.exists() and not force:
            raise FileExistsError(f"already exists (use --force): {path}")
    for path, content in output:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(path)
    return len(output)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    cmd = sub.add_parser("install")
    cmd.add_argument("--target", type=Path, required=True)
    cmd.add_argument("--module", choices=["all", *sorted(MODULES)], default="all")
    cmd.add_argument("--tool", choices=["codex", "claude", "copilot", "both", "all"], default="both")
    cmd.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            print(f"Validated {len(catalog())} agent definitions.")
        else:
            print(f"Installed {install(args.target, args.module, args.tool, args.force)} adapter files.")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
