import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from durable_approval_gate import DurableApprovalGate

class DurableGateTests(unittest.TestCase):
 def test_survives_restart_and_rejects_replay(self):
  with TemporaryDirectory() as d:
   path=Path(d)/"approvals.sqlite"
   token=DurableApprovalGate(path).prepare("run_tests","repo","a"*64)
   gate=DurableApprovalGate(path)
   self.assertTrue(gate.consume(token,"run_tests","repo","a"*64))
   with self.assertRaises(PermissionError):
    gate.consume(token,"run_tests","repo","a"*64)
 def test_concurrent_consumption_only_once(self):
  with TemporaryDirectory() as d:
   path=Path(d)/"approvals.sqlite"
   token=DurableApprovalGate(path).prepare("publish_pr","repo","b"*64)
   def attempt(_):
    try:return DurableApprovalGate(path).consume(token,"publish_pr","repo","b"*64)
    except PermissionError:return False
   with ThreadPoolExecutor(max_workers=8) as pool:
    results=list(pool.map(attempt,range(8)))
   self.assertEqual(1,sum(results))
 def test_mismatch_consumes_token(self):
  with TemporaryDirectory() as d:
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("apply_patch","repo","c"*64)
   with self.assertRaises(PermissionError):gate.consume(token,"run_tests","repo","c"*64)
   with self.assertRaises(PermissionError):gate.consume(token,"apply_patch","repo","c"*64)
if __name__=="__main__":unittest.main()
