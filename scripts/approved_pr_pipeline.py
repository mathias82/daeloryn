"""Local approval-gated pipeline for an existing clean, committed branch.

No unattended source edits, network execution API or automatic approval.
"""
from pathlib import Path
import subprocess
from reliable_container_tests import run as run_container_tests
from approved_pr_publish import publish as publish_pr

def _head(root):
 result=subprocess.run(["git","rev-parse","HEAD"],cwd=str(root),capture_output=True,text=True,timeout=20,check=False)
 if result.returncode:raise RuntimeError("unable to resolve HEAD")
 return result.stdout.strip()

def _clean(root):
 result=subprocess.run(["git","status","--porcelain","--untracked-files=all"],cwd=str(root),
                       capture_output=True,text=True,timeout=20,check=False)
 if result.returncode or result.stdout.strip():
  raise PermissionError("checkout must remain clean throughout validation")

def execute(checkout,suite,title,body,expected_commit,*,approve_tests=False,approve_publication=False,
            test_runner=run_container_tests,publisher=publish_pr):
 if approve_tests is not True:raise PermissionError("test execution approval required")
 root=Path(checkout).resolve(strict=True)
 if not (root/".git").is_dir() or (root/".git").is_symlink():
  raise ValueError("real git checkout required")
 _clean(root)
 if _head(root)!=expected_commit:raise PermissionError("HEAD differs from approved commit")
 result=test_runner(root,suite,approved=True)
 if result.get("verified") is not True or result.get("containerized") is not True:
  return {"published":False,"tests":result,"reason":"container tests did not pass"}
 _clean(root)
 if _head(root)!=expected_commit:raise PermissionError("HEAD changed after tests")
 if approve_publication is not True:
  return {"published":False,"tests":result,"reason":"explicit publication approval required"}
 published=publisher(root,title,body,expected_commit,approved=True)
 return {"published":True,"tests":result,"pr":published}
