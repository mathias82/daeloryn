"""AI-assisted repair proposal with exact-context consent and no repository mutation."""
import hashlib
from patch_proposal import propose_with_model
from repair_agent import suggest

def prepare(path,source,failed_test_log,*,attempt=1):
 if not isinstance(path,str) or not isinstance(source,str) or not source or len(source)>1800:
  raise ValueError("bounded source required")
 diagnosis=suggest(failed_test_log,attempt=attempt)
 task=("Repair the failing test without changing unrelated behavior. "
       +diagnosis["diagnoses"][0]["category"]+": "
       +diagnosis["diagnoses"][0]["suggestion"])
 # Context digest binds source, task and failure classification.
 payload=path+"\0"+source+"\0"+task
 return {"path":path,"source":source,"task":task,
         "sha256":hashlib.sha256(payload.encode()).hexdigest(),
         "diagnosis":diagnosis,"source_transmitted":False,
         "approval_required":True}

def propose(prepared,approved_sha256,model,transport):
 if not isinstance(prepared,dict) or not all(isinstance(prepared.get(k),str) for k in ("path","source","task")):
  raise ValueError("invalid prepared proposal")
 payload=prepared["path"]+"\0"+prepared["source"]+"\0"+prepared["task"]
 digest=hashlib.sha256(payload.encode()).hexdigest()
 if approved_sha256!=digest or prepared.get("sha256")!=digest:
  raise PermissionError("exact source context approval required")
 patch=propose_with_model(prepared["path"],prepared["source"],prepared["task"],model,transport)
 return {"patch":patch,"source_transmitted":True,"patch_applied":False,
         "tests_executed":False,"approval_required":True}
