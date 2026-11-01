"""Strict JSON request boundary for future loopback test execution endpoint.

Never accepts a filesystem path, command, shell, handler, or approval grant.
"""
import json
from registered_container_tests import run_registered_tests

FIELDS=frozenset(("repository","suite","digest","approval_token"))
SUITES=frozenset(("python","maven","gradle","npm"))

def _unique_object(pairs):
 result={}
 for key,value in pairs:
  if key in result:
   raise ValueError("duplicate JSON field")
  result[key]=value
 return result

def parse_request(payload):
 if not isinstance(payload,(bytes,bytearray)) or len(payload)>4096:
  raise ValueError("invalid request size")
 try:
  data=json.loads(payload.decode("utf-8"),object_pairs_hook=_unique_object)
 except (UnicodeError,ValueError) as exc:
  raise ValueError("invalid JSON") from exc
 if not isinstance(data,dict) or set(data)!=FIELDS:
  raise ValueError("unexpected request fields")
 repository=data["repository"]
 digest=data["digest"]
 token=data["approval_token"]
 if not isinstance(repository,str) or not 1<=len(repository)<=256:
  raise ValueError("invalid repository")
 if not isinstance(data["suite"],str) or data["suite"] not in SUITES:
  raise ValueError("unsupported suite")
 if not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
  raise ValueError("invalid digest")
 if not isinstance(token,str) or not 1<=len(token)<=256:
  raise ValueError("invalid approval token")
 return data

def execute_request(payload,authorization,authenticator,registry,approval_gate,
                    *,receipt_path=None,test_runner=None):
 data=parse_request(payload)
 kwargs={"receipt_path":receipt_path}
 if test_runner is not None:
  kwargs["test_runner"]=test_runner
 return run_registered_tests(authorization,authenticator,data["repository"],registry,
                             data["suite"],data["digest"],data["approval_token"],
                             approval_gate,**kwargs)
