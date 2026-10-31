#!/usr/bin/env python3
"""Optional Docker isolation for single agent prompts.

Runs only an explicitly provided digest-pinned image with no host mounts,
network, extra Linux capabilities, or elevated privileges. Disabled by default.
This does not integrate with state transitions or mark handoffs complete.
"""
import argparse
import re
import subprocess

DIGEST_IMAGE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9./_:-]*@sha256:[a-f0-9]{64}$")
def command(image):
    if not DIGEST_IMAGE.fullmatch(image):
        raise ValueError("Docker image must be pinned to sha256 digest")
    return ["docker","run","--rm","--interactive",
            "--network=none","--read-only","--cap-drop=ALL",
            "--security-opt=no-new-privileges","--pids-limit=64",
            "--memory=512m","--cpus=1","--user=65534:65534",
            "--tmpfs=/tmp:rw,nosuid,noexec,size=32m",
            image]

def run(image,prompt,enabled=False,timeout=60):
    if not enabled:
        raise ValueError("sandbox execution disabled; explicit --execute required")
    if not 1 <= timeout <= 120 or len(prompt.encode()) > 65536:
        raise ValueError("invalid timeout or oversized prompt")
    # The selected image must be operator-reviewed, without side effects.
    return subprocess.run(command(image),input=prompt,text=True,capture_output=True,
                          timeout=timeout,check=False)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--image",required=True)
    p.add_argument("--prompt",required=True)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--timeout",type=int,default=60)
    a=p.parse_args()
    result=run(a.image,a.prompt,a.execute,a.timeout)
    print(result.stdout)
    if result.returncode:
        raise SystemExit(result.returncode)

if __name__=="__main__":
    main()
