"""Local read-only operational checks. No secrets or execution controls exposed."""
from pathlib import Path
import shutil

def assess(workflow_dir=None):
 checks={"docker_available":shutil.which("docker") is not None}
 if workflow_dir is not None:
  root=Path(workflow_dir)
  checks["workflow_dir_accessible"]=root.is_dir() and not root.is_symlink()
 return {"checks":checks,"execution_enabled":False,
         "production_certified":False}
