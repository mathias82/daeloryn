"""Bounded failure-analysis repair suggestions; no automatic writes or AI uploads."""
import re

MAX_LOG=6000
PATTERNS=(
 (re.compile(r"AssertionError|expected:.*but was:",re.I),"Assertion failure","Inspect assertion and expected behavior; add a focused regression test."),
 (re.compile(r"Compilation failure|cannot find symbol|error:.*\.java",re.I),"Java compilation","Check imports, API compatibility and compiler output."),
 (re.compile(r"ModuleNotFoundError|ImportError",re.I),"Python dependency/import","Verify dependency declaration and module path."),
 (re.compile(r"npm ERR!|Cannot find module|ERR_MODULE_NOT_FOUND",re.I),"Node dependency/build","Check lockfile, dependency installation and test command."),
 (re.compile(r"TimeoutExpired|timed out|TimeoutException",re.I),"Timeout","Identify blocked dependency or long-running test before increasing limits."),
)
def suggest(log,*,attempt=1,max_attempts=3):
 if not isinstance(log,str) or not log.strip():raise ValueError("test output required")
 if not isinstance(attempt,int) or isinstance(attempt,bool) or not 1<=attempt<=max_attempts<=5:
  raise ValueError("invalid bounded retry attempt")
 excerpt=log[:MAX_LOG]
 matches=[{"category":name,"suggestion":hint} for pattern,name,hint in PATTERNS if pattern.search(excerpt)]
 if not matches:matches=[{"category":"Unclassified failure","suggestion":"Inspect the first failing test and reproduce locally before proposing a patch."}]
 return {"attempt":attempt,"max_attempts":max_attempts,"retry_allowed":attempt<max_attempts,
         "diagnoses":matches,"log_truncated":len(log)>MAX_LOG,
         "requires_human_review":True,"patch_generated":False,"tests_executed":False}
