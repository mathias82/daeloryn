#!/usr/bin/env python3
"""Run a provider CLI in a disposable Docker container with no host credentials.

Operator must build/review a digest-pinned image containing the provider CLI
and explicitly supply non-sensitive credentials through an external broker.
No Docker socket, host mounts, privileged mode or network by default.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from sandbox_runner import DIGEST_IMAGE
from capture_provider_cli import HOSTS, MODEL

def docker_argv(image, provider, argv, network="none"):
    if not DIGEST_IMAGE.fullmatch(image):
        raise ValueError("digest-pinned image required")
    if provider not in HOSTS or not isinstance(argv, list) or not argv:
        raise ValueError("supported provider and argv required")
    if Path(argv[0]).name != provider:
        raise ValueError("provider executable mismatch")
    if any(not isinstance(a, str) or not a or "\x00" in a for a in argv):
        raise ValueError("invalid argument")
    if network != "none":
        raise ValueError("network must be disabled unless separately reviewed")
    return ["docker", "run", "--rm", "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--pids-limit=64", "--memory=1g", "--cpus=2",
            "--user=65534:65534", "--tmpfs=/tmp:rw,nosuid,size=128m",
            "--workdir=/workspace", image, *argv]

def capture_isolated(image, provider, model, argv, timeout=900, runner=subprocess.run):
    if not isinstance(model, str) or not MODEL.fullmatch(model):
        raise ValueError("invalid model")
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("invalid timeout")
    command = docker_argv(image, provider, argv)
    start = time.monotonic()
    try:
        proc = runner(command, stdin=subprocess.DEVNULL, capture_output=True,
                      timeout=timeout, check=False)
        status = "completed" if proc.returncode == 0 else "failed"
        output = proc.stdout + proc.stderr
        code = proc.returncode
    except subprocess.TimeoutExpired:
        status, output, code = "timeout_unknown_remote_outcome", b"", None
    except OSError:
        status, output, code = "launch_error", b"", None
    return {"schema_version": 1, "kind": "local-provider-cli-capture",
            "provider": provider, "requested_model": model,
            "actual_model": "unverified", "agent_selected": "unverified",
            "status": status, "exit_code": code,
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "output_sha256": hashlib.sha256(output[:1048576]).hexdigest(),
            "output_truncated": len(output) > 1048576,
            "output": output[:1048576].decode("utf-8", errors="replace"),
            "provider_invoked": status in ("completed", "failed", "timeout_unknown_remote_outcome"),
            "isolation": "docker_no_network_no_host_mounts",
            "warning": "No network means remote AI APIs are unavailable. This mode is for offline provider smoke tests, not live model comparisons."}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--provider", choices=HOSTS, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--execute", action="store_true")
    p.add_argument("command", nargs=argparse.REMAINDER)
    a = p.parse_args()
    if a.output.exists() or a.output.is_symlink():
        p.error("output exists")
    argv = a.command[1:] if a.command and a.command[0] == "--" else a.command
    try:
        command = docker_argv(a.image, a.provider, argv)
        result = (capture_isolated(a.image, a.provider, a.model, argv, a.timeout)
                  if a.execute else {"kind": "isolated-provider-preview",
                                     "provider_invoked": False, "docker_argv": command})
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(a.output), "status": result.get("status", "preview")}))
    return 0 if not a.execute or result["status"] == "completed" else 1

if __name__ == "__main__":
    sys.exit(main())
