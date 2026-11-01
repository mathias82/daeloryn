"""Run a workflow's approved test stage with durable state and explicit evidence.

No automatic patch approval, PR publication, or user-controlled checkout path.
"""
from registered_container_tests import run_registered_tests
from reliable_container_tests import run as container_run
from workflow_evidence import test_subject, digest as evidence_digest
from execution_authorization import authorize

def run_workflow_tests(store,workflow_id,expected_version,authorization,authenticator,
                       registry,suite,digest,approval_token,approval_gate,*,
                       receipt_path=None,test_runner=container_run):
 state=store.load(workflow_id)
 if state["version"]!=expected_version or state["stage"]!="patch_approved":
  raise RuntimeError("workflow must be at approved patch stage and expected version")
 repository=state["repository"]
 authorize(authenticator.authenticate(authorization),repository,"run_tests")
 subject=test_subject(registry,repository,suite)
 if digest!=subject["digest"]:
  raise PermissionError("approval does not cover current test inputs")
 running=None
 def bound_runner(checkout,selected_suite,*,approved):
  nonlocal running
  if str(checkout)!=subject["snapshot"]["checkout"] or selected_suite!=suite:
   raise PermissionError("test checkout or suite changed")
  if test_subject(registry,repository,suite)!=subject:
   raise PermissionError("checkout changed before tests")
  running=store.transition(workflow_id,"start_tests",expected_version=expected_version,approved=True)
  result=test_runner(checkout,selected_suite,approved=approved)
  if test_subject(registry,repository,suite)!=subject:
   raise PermissionError("checkout changed during tests; results are unverified")
  return result
 # The authenticated dispatcher consumes approval before the runner reserves
 # state. Authentication/preflight failures therefore never start the workflow.
 try:
  result=run_registered_tests(authorization,authenticator,repository,registry,suite,
                              digest,approval_token,approval_gate,
                              receipt_path=receipt_path,test_runner=bound_runner)
 except BaseException:
  # Fail closed; uncertain executions require operator reconciliation.
  raise
 if not isinstance(result,dict) or result.get("verified") is not True or result.get("containerized") is not True:
  store.transition(workflow_id,"tests_failed",expected_version=running["version"])
  return {"passed":False,"tests":result}
 passed=store.transition(workflow_id,"tests_passed",expected_version=running["version"],
                         evidence={"verified":True,"subject":subject,"suite":suite,
                                   "result_sha256":evidence_digest(result)})
 return {"passed":True,"tests":result,"workflow":passed}
