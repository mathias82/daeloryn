"""Opt-in containerized tests; fail closed if Docker isolation is unavailable.

Not a security boundary against malicious kernel-level container escapes.
"""
from pathlib import Path
import shutil
import subprocess

SUITES = {
 "python": ("python:3.11-alpine", ["python","-m","unittest","discover","-s","tests"]),
 "maven": ("maven:3.9-eclipse-temurin-21", ["mvn","-B","-o","test"]),
 "npm": ("node:20-alpine", ["npm","test","--","--runInBand"]),
}

def run(checkout, suite, *, approved=False, timeout=180, runner=subprocess.run):
    if approved is not True:
        raise PermissionError("explicit test execution approval required")
    if suite not in SUITES:
        raise ValueError("unsupported test suite")
    root=Path(checkout).resolve(strict=True)
    if not (root/".git").is_dir() or (root/".git").is_symlink():
        raise ValueError("real git checkout required")
    if not shutil.which("docker"):
        raise RuntimeError("Docker unavailable: refusing host execution")
    image,cmd=SUITES[suite]
    args=["docker","run","--rm","--network","none","--read-only",
          "--cap-drop","ALL","--security-opt","no-new-privileges",
          "--pids-limit","128","--memory","1g","--cpus","2",
          "--user","65534:65534",
          "--tmpfs","/tmp:rw,noexec,nosuid,size=128m",
          "--mount","type=bind,src="+str(root)+",dst=/workspace,readonly",
          "--workdir","/workspace",image]+cmd
    try:
        result=runner(args,capture_output=True,text=True,timeout=timeout,check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("isolated test timeout") from exc
    return {"suite":suite,"verified":result.returncode==0,"returncode":result.returncode,
            "output":(result.stdout+"\n"+result.stderr)[:12000],
            "containerized":True,"network_disabled":True,
            "warning":"Container isolation reduces risk but is not a hardened VM. Read-only mount may prevent build tools from writing outputs."}
