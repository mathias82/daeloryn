#!/usr/bin/env python3
"""Unified offline benchmark gate. Never invokes models or deploys fixtures."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    ("agent-definitions", [sys.executable, "scripts/agents.py", "validate"]),
    ("platform-fixtures", [sys.executable, "scripts/evaluate_platform.py"]),
    ("engineering-fixtures", [sys.executable, "scripts/evaluate_engineering.py"]),
    ("unit-regressions", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
)


def run_suite(root=ROOT, timeout=180, runner=None):
    """Execute independent offline gates; continue after individual failures."""
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    runner = runner or subprocess.run
    results = []
    for name, command in COMMANDS:
        started = time.monotonic()
        try:
            completed = runner(command, cwd=str(root), capture_output=True,
                               text=True, timeout=timeout, check=False)
            status = "passed" if completed.returncode == 0 else "failed"
            result = {"name": name, "status": status, "exit_code": completed.returncode,
                      "stdout": completed.stdout[-8000:], "stderr": completed.stderr[-8000:]}
        except subprocess.TimeoutExpired:
            result = {"name": name, "status": "timeout", "exit_code": None,
                      "stdout": "", "stderr": "execution timed out"}
        except OSError as exc:
            result = {"name": name, "status": "error", "exit_code": None,
                      "stdout": "", "stderr": str(exc)}
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        results.append(result)
    return {"schema_version": 1, "kind": "offline-benchmark-suite",
            "provider_invoked": False, "implementation_verified": False,
            "passed": all(x["status"] == "passed" for x in results),
            "checks": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="write JSON report; refuses overwrite")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("output exists; refusing overwrite")
    result = run_suite(timeout=args.timeout)
    report = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print(report, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
