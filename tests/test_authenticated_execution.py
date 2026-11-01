import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from authenticated_execution import authenticated_dispatch
from local_bearer_auth import LocalBearerAuthenticator
from execution_authorization import Principal
from durable_approval_gate import DurableApprovalGate

class AuthenticatedExecutionTests(unittest.TestCase):
 def test_authentication_and_one_use_approval(self):
  with TemporaryDirectory() as d:
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","repo","a"*64)
   bearer="s"*48
   principal=Principal("dev",frozenset({"repo"}),frozenset({"run_tests"}),True)
   auth=LocalBearerAuthenticator({bearer:principal})
   called=[]
   def handler():
    called.append(1)
    return "done"
   with self.assertRaises(PermissionError):
    authenticated_dispatch("Bearer "+"x"*48,auth,"repo","run_tests","a"*64,token,gate,handler)
   self.assertEqual([],called)
   self.assertEqual("done",authenticated_dispatch("Bearer "+bearer,auth,"repo","run_tests","a"*64,token,gate,handler))
   with self.assertRaises(PermissionError):
    authenticated_dispatch("Bearer "+bearer,auth,"repo","run_tests","a"*64,token,gate,handler)
   self.assertEqual([1],called)
 def test_cross_repository_denied(self):
  with TemporaryDirectory() as d:
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","repo-b","b"*64)
   bearer="s"*48
   principal=Principal("dev",frozenset({"repo-a"}),frozenset({"run_tests"}),True)
   auth=LocalBearerAuthenticator({bearer:principal})
   with self.assertRaises(PermissionError):
    authenticated_dispatch("Bearer "+bearer,auth,"repo-b","run_tests","b"*64,token,gate,lambda:self.fail("executed"))
if __name__=="__main__":unittest.main()
