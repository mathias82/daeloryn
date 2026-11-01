"""Local-only authorization primitives for future workflow execution endpoints.

No HTTP mutation endpoints are enabled by this module.
"""
import hashlib
import hmac
import secrets
import time

class ApprovalGate:
 def __init__(self, secret=None, ttl_seconds=120, clock=time.monotonic):
  self._secret=secret or secrets.token_bytes(32)
  self._ttl=ttl_seconds
  self._clock=clock
  self._pending={}
 def prepare(self, action, repository, digest):
  if action not in ("apply_patch","run_tests","publish_pr"):
   raise ValueError("unsupported action")
  if not isinstance(repository,str) or not repository or not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
   raise ValueError("invalid approval subject")
  token=secrets.token_urlsafe(32)
  key=hashlib.sha256(token.encode()).hexdigest()
  self._pending[key]=(action,repository,digest,self._clock()+self._ttl)
  return token
 def consume(self,token,action,repository,digest):
  if not isinstance(token,str) or len(token)>256:
   raise PermissionError("invalid token")
  key=hashlib.sha256(token.encode()).hexdigest()
  record=self._pending.pop(key,None)
  if record is None:
   raise PermissionError("approval absent or already used")
  expected=(action,repository,digest)
  if record[3]<self._clock() or not all(hmac.compare_digest(str(a),str(b)) for a,b in zip(record[:3],expected)):
   raise PermissionError("approval expired or subject mismatch")
  return True
