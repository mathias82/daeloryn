"""Offline, writable ephemeral workspace for containerized test runs.

Docker required. No host execution fallback. Dependency caches are not mounted.
"""
from pathlib import Path
import shutil
import subprocess

SUITES={
 "python":("python:3.11-alpine",["python","-m","unittest","discover","-s","tests"]),
 "maven":("maven:3.9-eclipse-temurin-21",["mvn","-B","-o","test"]),
 "gradle":("gradle:8.10-jdk21",["gradle","--offline","test","--no-daemon"]),
 "npm":("node:20-alpine",["npm","test","--","--runInBand"]),
}

def run(checkout,suite,*,approved=False,timeout=300,runner=subprocess.run):
 if approved is not True:raise PermissionError("explicit approval required")
 if suite not in SUITES:raise ValueError("unsupported suite")
 root=Path(checkout).resolve(strict=True)
 if not (root/".git").is_dir() or (root/".git").is_symlink():raise ValueError("git checkout required")
 if not shutil.which("docker"):raise RuntimeError("Docker required; no host fallback")
 image,command=SUITES[suite]
 args=["docker","run","--rm","--network","none","--cap-drop","ALL",
       "--security-opt","no-new-privileges","--pids-limit","128",
       "--memory","2g","--cpus","2","--user","65534:65534",
       "--read-only","--tmpfs","/tmp:rw,nosuid,size=256m",
       "--mount",f"type=bind,src={root},dst=/source,readonly",
       "--tmpfs","/workspace:rw,nosuid,size=1024m",
       "--workdir","/workspace",image,
       "sh","-c","cp -R /source/. /workspace/ && "+ " ".join(command)]
 try:result=runner(args,capture_output=True,text=True,timeout=timeout,check=False)
 except subprocess.TimeoutExpired as exc:raise RuntimeError("test timeout") from exc
 return {"suite":suite,"verified":result.returncode==0,"containerized":True,
         "returncode":result.returncode,"output":(result.stdout+"\n"+result.stderr)[:12000],
         "warning":"Offline dependencies must be present in copied workspace. Container is not a hardened VM."}
