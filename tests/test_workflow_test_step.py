import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from workflow_test_step import run_workflow_tests
from workflow_orchestrator import WorkflowStore
from trusted_checkout_registry import TrustedCheckoutRegistry
from local_bearer_auth import LocalBearerAuthenticator
from execution_authorization import Principal
from durable_approval_gate import DurableApprovalGate

class WorkflowTestStepTests(unittest.TestCase):
 def test_successful_approved_test_step(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"checkout"
   (root/".git").mkdir(parents=True)
   store=WorkflowStore(Path(d)/"workflows")
   state=store.create("run1","org/repo","Review patch")
   state=store.transition("run1","prepare",expected_version=state["version"])
   state=store.transition("run1","approve_patch",expected_version=state["version"],approved=True)
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","org/repo","a"*64)
   auth=LocalBearerAuthenticator({"s"*48:Principal("dev",frozenset({"org/repo"}),frozenset({"run_tests"}),True)})
   registry=TrustedCheckoutRegistry({"org/repo":root})
   result=run_workflow_tests(store,"run1",state["version"],"Bearer "+"s"*48,auth,
                             registry,"python","a"*64,token,gate,
                             test_runner=lambda *a,**k:{"verified":True,"containerized":True})
   self.assertTrue(result["passed"])
   self.assertEqual("tests_passed",store.load("run1")["stage"])
   with self.assertRaises(RuntimeError):
    run_workflow_tests(store,"run1",state["version"],"Bearer "+"s"*48,auth,
                       registry,"python","a"*64,token,gate)
 def test_failed_test_result_does_not_advance(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"checkout"
   (root/".git").mkdir(parents=True)
   store=WorkflowStore(Path(d)/"workflows")
   state=store.create("run2","org/repo","Review patch")
   state=store.transition("run2","prepare",expected_version=state["version"])
   state=store.transition("run2","approve_patch",expected_version=state["version"],approved=True)
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","org/repo","b"*64)
   auth=LocalBearerAuthenticator({"s"*48:Principal("dev",frozenset({"org/repo"}),frozenset({"run_tests"}),True)})
   registry=TrustedCheckoutRegistry({"org/repo":root})
   result=run_workflow_tests(store,"run2",state["version"],"Bearer "+"s"*48,auth,
                             registry,"python","b"*64,token,gate,
                             test_runner=lambda *a,**k:{"verified":False,"containerized":True})
   self.assertFalse(result["passed"])
   self.assertEqual("patch_approved",store.load("run2")["stage"])
if __name__=="__main__":unittest.main()
