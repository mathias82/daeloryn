import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from workflow_draft_publication import publish_workflow_draft
from workflow_orchestrator import WorkflowStore
from trusted_checkout_registry import TrustedCheckoutRegistry
from execution_authorization import Principal
from durable_approval_gate import DurableApprovalGate

class DraftPublicationTests(unittest.TestCase):
 def test_verified_tests_to_draft_publication(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"repo"
   (root/".git").mkdir(parents=True)
   registry=TrustedCheckoutRegistry({"org/repo":root})
   store=WorkflowStore(Path(d)/"workflows")
   state=store.create("run1","org/repo","Review code")
   for event in ("prepare","approve_patch","start_tests","tests_passed"):
    state=store.transition("run1",event,expected_version=state["version"],
                           approved=event in ("approve_patch","start_tests"),
                           evidence={"verified":True} if event=="tests_passed" else None)
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("publish_pr","org/repo","a"*64)
   principal=Principal("dev",frozenset({"org/repo"}),frozenset({"publish_pr"}),True)
   calls=[]
   def publisher(checkout,title,body,commit,*,approved):
    calls.append((checkout,approved))
    return {"published":True,"draft_pr_created":True,"url":"https://example.invalid/pr/1"}
   result=publish_workflow_draft(store,"run1",state["version"],principal,registry,
                                 "a"*64,token,gate,"Title","Body","b"*40,publisher=publisher)
   self.assertEqual("published",result["workflow"]["stage"])
   self.assertEqual([(root.resolve(),True)],calls)
   with self.assertRaises(RuntimeError):
    publish_workflow_draft(store,"run1",state["version"],principal,registry,
                           "a"*64,token,gate,"Title","Body","b"*40,publisher=publisher)
 def test_unverified_workflow_denied(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"repo"
   (root/".git").mkdir(parents=True)
   store=WorkflowStore(Path(d)/"workflows")
   state=store.create("run2","org/repo","Review code")
   registry=TrustedCheckoutRegistry({"org/repo":root})
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("publish_pr","org/repo","a"*64)
   principal=Principal("dev",frozenset({"org/repo"}),frozenset({"publish_pr"}),True)
   with self.assertRaises(RuntimeError):
    publish_workflow_draft(store,"run2",state["version"],principal,registry,
                           "a"*64,token,gate,"Title","Body","b"*40,
                           publisher=lambda *a,**kw:self.fail("published"))
if __name__=="__main__":unittest.main()
