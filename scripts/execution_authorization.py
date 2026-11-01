"""Fail-closed authorization policy for future local execution services.

Authentication is performed by the caller. This module never trusts a username
supplied by an unauthenticated HTTP request and never executes an action.
"""
import re
from dataclasses import dataclass
from typing import FrozenSet

ACTIONS=frozenset(("apply_patch","run_tests","publish_pr"))
IDENTITY=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}\Z")

@dataclass(frozen=True)
class Principal:
 subject: str
 repositories: FrozenSet[str]
 actions: FrozenSet[str]
 authenticated: bool = False

 def __post_init__(self):
  if not isinstance(self.subject,str) or not IDENTITY.fullmatch(self.subject):
   raise ValueError("invalid subject")
  if not isinstance(self.repositories,frozenset) or not all(isinstance(x,str) and 1<=len(x)<=256 for x in self.repositories):
   raise ValueError("invalid repository grants")
  if not isinstance(self.actions,frozenset) or not self.actions.issubset(ACTIONS):
   raise ValueError("invalid action grants")

def authorize(principal,repository,action):
 if not isinstance(principal,Principal) or principal.authenticated is not True:
  raise PermissionError("authenticated principal required")
 if action not in ACTIONS or not isinstance(repository,str):
  raise PermissionError("unsupported action or repository")
 if repository not in principal.repositories or action not in principal.actions:
  raise PermissionError("action not authorized for repository")
 return True

def authorize_and_consume(principal,repository,action,digest,token,gate):
 """Authorize before consuming a one-time approval; caller owns principal authentication."""
 authorize(principal,repository,action)
 return gate.consume(token,action,repository,digest)
