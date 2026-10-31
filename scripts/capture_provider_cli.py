#!/usr/bin/env python3
"""Opt-in local CLI capture for one preprepared benchmark arm.

No shell, no automatic retries, no claim of model identity verification.
Run only inside an independently isolated, trusted benchmark environment.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

HOSTS = ("copilot", "claude", "codex", "gemini")
MAX_TIMEOUT = 3600
MAX_OUTPUT = 1024 * 1024
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}\Z")


def capture(arm, provider, model, argv, timeout=900):
    arm = Path(arm).resolve(strict=True)
    if not arm.is_dir() or provider not in HOSTS:
        raise ValueError("existing arm directory and supported provider required")
    if not isinstance(model, str) or not MODEL.fullmatch(model):
        raise ValueError("invalid model identifier")
    if type(timeout) is not int or not 1 <= timeout <= MAX_TIMEOUT:
        raise ValueError("timeout must be 1..3600")
    if os.name != "posix":
        raise ValueError("bounded provider capture requires POSIX")
    if not isinstance(argv, list) or not argv or not all(
            isinstance(x, str) and x and "\x00" not in x for x in argv):
        raise ValueError("explicit nonempty argv required")
    if os.path.basename(argv[0]) not in (provider, provider + ".exe"):
        raise ValueError("executable must match declared provider")
    started = time.monotonic()
    with tempfile.TemporaryFile(mode="w+b") as stream:
        try:
            if os.name != 'posix':
                raise ValueError('bounded provider capture currently requires POSIX')
            process = subprocess.Popen(argv, cwd=arm, stdin=subprocess.DEVNULL,
                                       stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            try:
                code = process.wait(timeout=timeout)
                status = 'completed' if code == 0 else 'failed'
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                status, code = 'timeout_unknown_remote_outcome', None
        except OSError:
            status, code = "launch_error", None
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(0)
        output = stream.read(MAX_OUTPUT)
    return {"schema_version": 1, "kind": "local-provider-cli-capture",
            "provider": provider, "requested_model": model,
            "actual_model": "unverified", "agent_selected": "unverified",
            "arm": str(arm), "argv": argv, "status": status, "exit_code": code,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "output_sha256": hashlib.sha256(output).hexdigest(),
            "output_truncated": size > MAX_OUTPUT,
            "output": output.decode("utf-8", errors="replace"),
            "provider_invoked": status in ("completed", "failed", "timeout_unknown_remote_outcome"),
            "warning": "CLI invocation is not proof of remote model execution, model identity or correct agent selection; inspect sanitized transcript."}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arm", type=Path, required=True)
    p.add_argument("--provider", choices=HOSTS, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("command", nargs=argparse.REMAINDER,
                   help="provider executable and exact arguments, after --")
    a = p.parse_args()
    if a.output.exists() or a.output.is_symlink():
        p.error("output exists")
    command = a.command[1:] if a.command and a.command[0] == "--" else a.command
    try:
        report = capture(a.arm, a.provider, a.model, command, a.timeout)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(a.output),
                      "actual_model": report["actual_model"]}, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
