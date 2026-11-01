"""Offline, writable ephemeral workspace for containerized test runs.

Docker required. No host execution fallback. Dependency caches are not mounted.
"""
from pathlib import Path
import shutil
import subprocess
import uuid

SUITES={
 "python":("python:3.11-alpine",["python","-m","unittest","discover","-s","tests"]),
 "maven":("maven:3.9-eclipse-temurin-21",["mvn","-B","-o","test"]),
 "gradle":("gradle:8.10-jdk21",["gradle","--offline","test","--no-daemon"]),
 "npm":("node:20-alpine",["npm","test","--","--runInBand"]),
}

class ContainerTestTimeout(RuntimeError):
 def __init__(self,name,cleanup_verified):
  super().__init__("test timeout; container cleanup "+("verified" if cleanup_verified else "unverified"))
  self.container_name=name
  self.cleanup_verified=cleanup_verified

def run(checkout,suite,*,approved=False,timeout=300,runner=subprocess.run):
 if approved is not True:raise PermissionError("explicit approval required")
 if suite not in SUITES:raise ValueError("unsupported suite")
 root=Path(checkout).resolve(strict=True)
 if not (root/".git").is_dir() or (root/".git").is_symlink():raise ValueError("git checkout required")
 if not shutil.which("docker"):raise RuntimeError("Docker required; no host fallback")
 image,command=SUITES[suite]
 name="daeloryn-tests-"+uuid.uuid4().hex
 args=["docker","run","--rm","--name",name,"--network","none","--cap-drop","ALL",
       "--security-opt","no-new-privileges","--pids-limit","128",
       "--memory","2g","--cpus","2","--user","65534:65534",
       "--read-only","--tmpfs","/tmp:rw,nosuid,size=256m,mode=1777",
       "--mount",f"type=bind,src={root},dst=/source,readonly",
       "--tmpfs","/workspace:rw,nosuid,size=1024m,mode=1777",
       "--workdir","/workspace",image,
       "sh","-c","cp -R /source/. /workspace/ && "+ " ".join(command)]
 try:result=runner(args,capture_output=True,text=True,timeout=timeout,check=False)
 except subprocess.TimeoutExpired as exc:
  # Killing the Docker CLI alone does not stop its daemon-owned container.
  # Only remove our unique container; never prune unrelated daemon resources.
  cleaned=False
  try:
   cleanup=subprocess.run(["docker","rm","--force",name],capture_output=True,
                          text=True,timeout=20,check=False)
   cleaned=cleanup.returncode==0
  except (OSError,subprocess.TimeoutExpired):
   pass
  raise ContainerTestTimeout(name,cleaned) from exc
 return {"suite":suite,"verified":result.returncode==0,"containerized":True,
         "returncode":result.returncode,"output":(result.stdout+"\n"+result.stderr)[:12000],
         "warning":"Offline dependencies must be present in copied workspace. Container is not a hardened VM."}
