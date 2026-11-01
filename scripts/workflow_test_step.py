"""Run a workflow's approved test stage with durable state and explicit evidence.

No automatic patch approval, PR publication, or user-controlled checkout path.
"""
from registered_container_tests import run_registered_tests
from reliable_container_tests import run as container_run

def run_workflow_tests(store,workflow_id,expected_version,authorization,authenticator,
                       registry,suite,digest,approval_token,approval_gate,*,
                       receipt_path=None,test_runner=container_run):
 state=store.load(workflow_id)
 if state["version"]!=expected_version or state["stage"]!="patch_approved":
  raise RuntimeError("workflow must be at approved patch stage and expected version")
 repository=state["repository"]
 # The state transition is a reservation, not a claim that tests passed.
 running=store.transition(workflow_id,"start_tests",expected_version=expected_version,approved=True)
 try:
  result=run_registered_tests(authorization,authenticator,repository,registry,suite,
                              digest,approval_token,approval_gate,
                              receipt_path=receipt_path,test_runner=test_runner)
 except BaseException:
  # Fail closed; uncertain executions require operator reconciliation.
  raise
 if not isinstance(result,dict) or result.get("verified") is not True or result.get("containerized") is not True:
  store.transition(workflow_id,"tests_failed",expected_version=running["version"])
  return {"passed":False,"tests":result}
 passed=store.transition(workflow_id,"tests_passed",expected_version=running["version"],
                         evidence={"verified":True})
 return {"passed":True,"tests":result,"workflow":passed}
