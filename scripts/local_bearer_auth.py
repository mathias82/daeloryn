"""Opt-in loopback bearer-token authentication for local execution callers.

Tokens are configured out of band; never accepted from URL query parameters.
This does not turn the read-only console into an execution server.
"""
import hashlib
import hmac
import re
from execution_authorization import Principal

TOKEN_PATTERN=re.compile(r"[A-Za-z0-9_-]{32,256}\Z")

class LocalBearerAuthenticator:
 def __init__(self, credentials):
  if not isinstance(credentials,dict) or not credentials:
   raise ValueError("nonempty credential mapping required")
  self._entries={}
  for token,grants in credentials.items():
   if not isinstance(token,str) or not TOKEN_PATTERN.fullmatch(token):
    raise ValueError("invalid token")
   if not isinstance(grants,Principal):
    raise ValueError("invalid principal")
   if grants.authenticated is not True:
    raise ValueError("principal must be authenticated")
   digest=hashlib.sha256(token.encode("ascii")).digest()
   if digest in self._entries:raise ValueError("duplicate credential")
   self._entries[digest]=grants

 def authenticate(self,authorization):
  if not isinstance(authorization,str) or len(authorization)>300:
   raise PermissionError("authorization required")
  scheme,sep,token=authorization.partition(" ")
  if scheme.lower()!="bearer" or not sep or not TOKEN_PATTERN.fullmatch(token):
   raise PermissionError("invalid bearer authorization")
  digest=hashlib.sha256(token.encode("ascii")).digest()
  principal=None
  for key,grant in self._entries.items():
   if hmac.compare_digest(key,digest):
    principal=grant
  if principal is None:
   raise PermissionError("invalid bearer credential")
  return principal
