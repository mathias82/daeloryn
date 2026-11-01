"""Conservative recovery of interrupted local workflow runs.

Recovery never executes commands, approves actions, or publishes a PR.
"""
from pathlib import Path
from workflow_orchestrator import WorkflowStore

def inspect_interrupted(directory):
 store=WorkflowStore(directory)
 results=[]
 for path in sorted(Path(directory).glob("*.json")):
  if path.is_symlink() or not path.is_file():
   continue
  identifier=path.stem
  try:
   state=store.load(identifier)
  except (ValueError, OSError, KeyError):
   continue
  if state.get("stage")=="tests_running":
   results.append({"id":identifier,"version":state.get("version"),
                   "stage":"tests_running","action":"manual_reconcile",
                   "reason":"Test process outcome unknown after restart; do not assume success or retry automatically."})
  elif state.get("stage")=="publication_approved":
   results.append({"id":identifier,"version":state.get("version"),
                   "stage":"publication_approved","action":"check_remote_pr",
                   "reason":"GitHub publication outcome may be unknown; reconcile remote state before retry."})
 return results

def recover_failed_test(directory,identifier,expected_version,*,confirmed_not_running=False):
 if confirmed_not_running is not True:
  raise PermissionError("operator must confirm no test process is still running")
 store=WorkflowStore(directory)
 state=store.load(identifier)
 if state.get("stage")!="tests_running":
  raise ValueError("workflow is not awaiting test recovery")
 return store.transition(identifier,"tests_failed",expected_version=expected_version)
