"""Non-mutating execution authorization and approval preflight."""
from execution_authorization import authorize

def preflight(principal,repository,action,digest,token,gate):
 authorize(principal,repository,action)
 if not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
  raise ValueError("invalid approved digest")
 if not isinstance(token,str) or not token:
  raise PermissionError("explicit approval token required")
 # Consume only after caller has independently authenticated principal.
 gate.consume(token,action,repository,digest)
 return {"authorized":True,"approved":True,"action":action,"repository":repository,
         "digest":digest,"executed":False}
