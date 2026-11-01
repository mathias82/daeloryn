from execution_receipts import append_receipt
"""Local-only approved action dispatcher.

No HTTP endpoints, shell commands, or implicit approvals. Callers must
authenticate Principal independently and provide a trusted action handler.
"""
from execution_authorization import authorize

def dispatch(principal,repository,action,digest,token,gate,handler,*,receipt_path=None):
 authorize(principal,repository,action)
 if not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
  raise ValueError("invalid digest")
 if not isinstance(token,str) or not token:
  raise PermissionError("approval token required")
 if not callable(handler):
  raise TypeError("trusted action handler required")
 # Token is spent before any side effect; a failed handler must be reconciled
 # explicitly rather than retried with the same approval.
 gate.consume(token,action,repository,digest)
 if receipt_path is not None:
  append_receipt(receipt_path,subject=principal.subject,repository=repository,action=action,digest=digest,outcome="started")
 try:
  result=handler()
 except BaseException:
  if receipt_path is not None:
   append_receipt(receipt_path,subject=principal.subject,repository=repository,action=action,digest=digest,outcome="uncertain")
  raise
 if receipt_path is not None:
  append_receipt(receipt_path,subject=principal.subject,repository=repository,action=action,digest=digest,outcome="succeeded")
 return result
