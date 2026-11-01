import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from execution_authorization import Principal,authorize,authorize_and_consume
from durable_approval_gate import DurableApprovalGate

class AuthorizationTests(unittest.TestCase):
 def test_anonymous_and_cross_repository_denied(self):
  user=Principal("dev",frozenset({"repo-a"}),frozenset({"run_tests"}))
  with self.assertRaises(PermissionError):authorize(user,"repo-a","run_tests")
  authenticated=Principal("dev",frozenset({"repo-a"}),frozenset({"run_tests"}),True)
  with self.assertRaises(PermissionError):authorize(authenticated,"repo-b","run_tests")
  with self.assertRaises(PermissionError):authorize(authenticated,"repo-a","publish_pr")
  self.assertTrue(authorize(authenticated,"repo-a","run_tests"))
 def test_authorization_before_token_consumption(self):
  with TemporaryDirectory() as d:
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","repo-a","a"*64)
   denied=Principal("dev",frozenset({"repo-b"}),frozenset({"run_tests"}),True)
   allowed=Principal("dev",frozenset({"repo-a"}),frozenset({"run_tests"}),True)
   with self.assertRaises(PermissionError):
    authorize_and_consume(denied,"repo-a","run_tests","a"*64,token,gate)
   self.assertTrue(authorize_and_consume(allowed,"repo-a","run_tests","a"*64,token,gate))
   with self.assertRaises(PermissionError):
    authorize_and_consume(allowed,"repo-a","run_tests","a"*64,token,gate)
if __name__=="__main__":unittest.main()
