import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from durable_approval_gate import DurableApprovalGate
from execution_authorization import Principal
from approved_execution_dispatch import dispatch

class DispatchReceiptTests(unittest.TestCase):
 def test_success_receipts(self):
  with TemporaryDirectory() as d:
   path=Path(d)/"events.jsonl"
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","repo","a"*64)
   p=Principal("dev",frozenset({"repo"}),frozenset({"run_tests"}),True)
   self.assertEqual("ok",dispatch(p,"repo","run_tests","a"*64,token,gate,lambda:"ok",receipt_path=path))
   self.assertEqual(["started","succeeded"],[json.loads(x)["outcome"] for x in path.read_text().splitlines()])
 def test_handler_failure_is_uncertain(self):
  with TemporaryDirectory() as d:
   path=Path(d)/"events.jsonl"
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","repo","b"*64)
   p=Principal("dev",frozenset({"repo"}),frozenset({"run_tests"}),True)
   def fail():raise RuntimeError("ambiguous outcome")
   with self.assertRaises(RuntimeError):
    dispatch(p,"repo","run_tests","b"*64,token,gate,fail,receipt_path=path)
   self.assertEqual(["started","uncertain"],[json.loads(x)["outcome"] for x in path.read_text().splitlines()])
if __name__=="__main__":unittest.main()
