import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from execution_authorization import Principal
from durable_approval_gate import DurableApprovalGate
from approved_execution_dispatch import dispatch

class DispatchTests(unittest.TestCase):
 def test_authorized_once(self):
  with TemporaryDirectory() as d:
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","repo","a"*64)
   p=Principal("dev",frozenset({"repo"}),frozenset({"run_tests"}),True)
   calls=[]
   self.assertEqual("ok",dispatch(p,"repo","run_tests","a"*64,token,gate,lambda:calls.append(1) or "ok"))
   self.assertEqual([1],calls)
   with self.assertRaises(PermissionError):
    dispatch(p,"repo","run_tests","a"*64,token,gate,lambda:calls.append(2))
   self.assertEqual([1],calls)
 def test_denied_never_runs_handler(self):
  with TemporaryDirectory() as d:
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("publish_pr","repo","b"*64)
   p=Principal("dev",frozenset({"repo"}),frozenset({"run_tests"}),True)
   with self.assertRaises(PermissionError):
    dispatch(p,"repo","publish_pr","b"*64,token,gate,lambda:self.fail("executed"))
if __name__=="__main__":unittest.main()
