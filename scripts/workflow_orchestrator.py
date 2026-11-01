"""Durable local workflow state machine with atomic writes and explicit retries.

No command execution, AI calls, or implicit approvals.
"""
import json
import contextlib
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STAGES=("planned","patch_prepared","patch_approved","tests_running","tests_passed","publication_approved","published")
TRANSITIONS={
 "planned":{"prepare":"patch_prepared"},
 "patch_prepared":{"approve_patch":"patch_approved"},
 "patch_approved":{"start_tests":"tests_running"},
 "tests_running":{"tests_passed":"tests_passed","tests_failed":"patch_approved"},
 "tests_passed":{"approve_publication":"publication_approved"},
 "publication_approved":{"published":"published"},
 "published":{},
}
IDENTIFIER=re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")

class WorkflowStore:
 def __init__(self, directory):
  self.directory=Path(directory).resolve()
  self.directory.mkdir(parents=True,exist_ok=True)
 @contextlib.contextmanager
 def _lock(self,identifier):
  path=self._path(identifier).with_suffix(".lock")
  if path.is_symlink():raise ValueError("symlink lock file")
  # SQLite's exclusive writer reservation serializes threads and processes on
  # Windows as well as POSIX. A timeout fails closed before state is read.
  fd=os.open(path,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
  os.close(fd)
  db=sqlite3.connect(path,timeout=30,isolation_level=None)
  try:
   db.execute("BEGIN IMMEDIATE")
   yield
  finally:
   db.close()
 def _path(self,identifier):
  if not isinstance(identifier,str) or not IDENTIFIER.fullmatch(identifier):
   raise ValueError("invalid workflow identifier")
  return self.directory/(identifier+".json")
 def load(self,identifier):
  path=self._path(identifier)
  if path.is_symlink():
   raise ValueError("symlink workflow file")
  return json.loads(path.read_text(encoding="utf-8"))
 def _save(self,identifier,state,*,create=False):
  target=self._path(identifier)
  if target.is_symlink():
   raise ValueError("symlink workflow file")
  if create and target.exists():
   raise FileExistsError(identifier)
  fd,name=tempfile.mkstemp(prefix=".workflow-",dir=self.directory)
  try:
   with os.fdopen(fd,"w",encoding="utf-8") as handle:
    json.dump(state,handle,sort_keys=True)
    handle.flush()
    os.fsync(handle.fileno())
   os.replace(name,target)
  finally:
   if os.path.exists(name):os.unlink(name)
 def create(self,identifier,repository,task):
  if not isinstance(repository,str) or not repository.strip() or not isinstance(task,str) or not 1<=len(task.strip())<=300:
   raise ValueError("repository and bounded task required")
  state={"id":identifier,"repository":repository,"task":task,"stage":"planned","version":0,"attempts":0,"events":[]}
  with self._lock(identifier):
   self._save(identifier,state,create=True)
  return state
 def transition(self,identifier,event,*,expected_version,approved=False,evidence=None):
  with self._lock(identifier):
   return self._transition_locked(identifier,event,expected_version=expected_version,approved=approved,evidence=evidence)
 def _transition_locked(self,identifier,event,*,expected_version,approved=False,evidence=None):
  state=self.load(identifier)
  if not isinstance(expected_version,int) or isinstance(expected_version,bool) or expected_version!=state["version"]:
   raise RuntimeError("stale workflow version")
  next_stage=TRANSITIONS.get(state["stage"],{}).get(event)
  if not next_stage:raise ValueError("invalid workflow transition")
  if event in ("approve_patch","start_tests","approve_publication","published") and approved is not True:
   raise PermissionError("explicit approval required")
  if event in ("tests_passed","published") and (not isinstance(evidence,dict) or evidence.get("verified") is not True):
   raise PermissionError("verified evidence required")
  if event=="start_tests" and state["attempts"]>=3:
   raise RuntimeError("retry limit exceeded")
  state["stage"]=next_stage
  state["version"]+=1
  if event=="start_tests":state["attempts"]+=1
  state["events"].append({"event":event,"stage":next_stage,"time":datetime.now(timezone.utc).isoformat()})
  self._save(identifier,state)
  return state
