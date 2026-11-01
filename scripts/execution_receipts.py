"""Local append-only action receipts for approval-gated execution.

Receipts are diagnostic records, not a substitute for authenticated audit logs.
"""
import json
import os
import time
from pathlib import Path

def append_receipt(path,*,subject,repository,action,digest,outcome):
 if outcome not in ("started","succeeded","failed","uncertain"):
  raise ValueError("unsupported outcome")
 if not all(isinstance(v,str) and 0<len(v)<=256 for v in (subject,repository,action,digest)):
  raise ValueError("invalid receipt fields")
 target=Path(path)
 if target.is_symlink():
  raise ValueError("receipt path cannot be symlink")
 record={"timestamp":time.time(),"subject":subject,"repository":repository,
         "action":action,"digest":digest,"outcome":outcome}
 # Local append with restrictive creation mode; use an operator-controlled directory.
 fd=os.open(str(target),os.O_WRONLY|os.O_APPEND|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
 try:
  if os.fstat(fd).st_mode & 0o077:
   raise PermissionError("receipt file must not be group/world accessible")
  with os.fdopen(fd,"a",encoding="utf-8") as f:
   fd=-1
   f.write(json.dumps(record,sort_keys=True)+"\n")
   f.flush()
   os.fsync(f.fileno())
 finally:
  if fd>=0:os.close(fd)
 return record
