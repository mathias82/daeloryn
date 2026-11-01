import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from execution_approval_gate import ApprovalGate

class GateTests(unittest.TestCase):
 def test_one_time_and_bound_to_subject(self):
  g=ApprovalGate()
  token=g.prepare("apply_patch","demo","a"*64)
  with self.assertRaises(PermissionError):g.consume(token,"publish_pr","demo","a"*64)
  with self.assertRaises(PermissionError):g.consume(token,"apply_patch","demo","a"*64)
  token=g.prepare("apply_patch","demo","a"*64)
  self.assertTrue(g.consume(token,"apply_patch","demo","a"*64))
  with self.assertRaises(PermissionError):g.consume(token,"apply_patch","demo","a"*64)
 def test_expiration(self):
  now=[0]
  g=ApprovalGate(ttl_seconds=10,clock=lambda:now[0])
  token=g.prepare("run_tests","demo","b"*64)
  now[0]=11
  with self.assertRaises(PermissionError):g.consume(token,"run_tests","demo","b"*64)
if __name__=="__main__":unittest.main()
