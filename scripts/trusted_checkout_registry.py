"""Operator-controlled repository-to-checkout binding for local actions.

Never derive filesystem paths from client-supplied repository identifiers.
"""
from pathlib import Path

class TrustedCheckoutRegistry:
 def __init__(self,checkouts):
  if not isinstance(checkouts,dict) or not checkouts:
   raise ValueError("trusted checkout mappings required")
  self._roots={}
  for repository,checkout in checkouts.items():
   if not isinstance(repository,str) or not repository or len(repository)>256:
    raise ValueError("invalid repository identifier")
   path=Path(checkout)
   if path.is_symlink():
    raise ValueError("symlink checkout not allowed")
   root=path.resolve(strict=True)
   if not root.is_dir() or not (root/".git").is_dir() or (root/".git").is_symlink():
    raise ValueError("git checkout required")
   self._roots[repository]=root

 def resolve(self,repository):
  if not isinstance(repository,str) or repository not in self._roots:
   raise PermissionError("repository not configured")
  root=self._roots[repository]
  if not root.is_dir() or root.is_symlink() or not (root/".git").is_dir() or (root/".git").is_symlink():
   raise PermissionError("checkout no longer valid")
  if root.resolve(strict=True)!=root:
   raise PermissionError("checkout path changed")
  return root
