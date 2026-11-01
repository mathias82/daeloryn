import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from authenticated_container_tests import run_approved_tests
from local_bearer_auth import LocalBearerAuthenticator
from execution_authorization import Principal
from durable_approval_gate import DurableApprovalGate

class AuthenticatedContainerTests(unittest.TestCase):
 def test_valid_approval_invokes_only_allowlisted_suite(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"checkout"
   (root/".git").mkdir(parents=True)
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","repo","a"*64)
   auth=LocalBearerAuthenticator({"s"*48:Principal("dev",frozenset({"repo"}),frozenset({"run_tests"}),True)})
   calls=[]
   def runner(path,suite,*,approved):
    calls.append((path,suite,approved))
    return {"verified":True,"containerized":True}
   result=run_approved_tests("Bearer "+"s"*48,auth,"repo",root,"python","a"*64,token,gate,test_runner=runner)
   self.assertTrue(result["verified"])
   self.assertEqual([(root.resolve(),"python",True)],calls)
   with self.assertRaises(PermissionError):
    run_approved_tests("Bearer "+"s"*48,auth,"repo",root,"python","a"*64,token,gate,test_runner=runner)
   self.assertEqual(1,len(calls))
 def test_invalid_suite_never_consumes_token(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"checkout"
   (root/".git").mkdir(parents=True)
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","repo","b"*64)
   auth=LocalBearerAuthenticator({"s"*48:Principal("dev",frozenset({"repo"}),frozenset({"run_tests"}),True)})
   with self.assertRaises(ValueError):
    run_approved_tests("Bearer "+"s"*48,auth,"repo",root,"shell","b"*64,token,gate)
   self.assertTrue(gate.consume(token,"run_tests","repo","b"*64))
if __name__=="__main__":unittest.main()
