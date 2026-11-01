import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from registered_container_tests import run_registered_tests
from trusted_checkout_registry import TrustedCheckoutRegistry
from local_bearer_auth import LocalBearerAuthenticator
from execution_authorization import Principal
from durable_approval_gate import DurableApprovalGate

class RegisteredTests(unittest.TestCase):
 def test_approved_registered_repository(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"repo"
   (root/".git").mkdir(parents=True)
   registry=TrustedCheckoutRegistry({"org/repo":root})
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","org/repo","a"*64)
   auth=LocalBearerAuthenticator({"s"*48:Principal("dev",frozenset({"org/repo"}),frozenset({"run_tests"}),True)})
   calls=[]
   def runner(checkout,suite,*,approved):
    calls.append((checkout,suite,approved))
    return {"verified":True,"containerized":True}
   result=run_registered_tests("Bearer "+"s"*48,auth,"org/repo",registry,"python","a"*64,token,gate,test_runner=runner)
   self.assertTrue(result["verified"])
   self.assertEqual([(root.resolve(),"python",True)],calls)
 def test_unregistered_repository_never_consumes_approval(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"repo"
   (root/".git").mkdir(parents=True)
   registry=TrustedCheckoutRegistry({"org/repo":root})
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","org/other","b"*64)
   auth=LocalBearerAuthenticator({"s"*48:Principal("dev",frozenset({"org/other"}),frozenset({"run_tests"}),True)})
   with self.assertRaises(PermissionError):
    run_registered_tests("Bearer "+"s"*48,auth,"org/other",registry,"python","b"*64,token,gate,
                         test_runner=lambda *a,**kw:self.fail("executed"))
   self.assertTrue(gate.consume(token,"run_tests","org/other","b"*64))
if __name__=="__main__":unittest.main()
