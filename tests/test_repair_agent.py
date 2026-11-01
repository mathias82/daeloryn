import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from repair_agent import suggest
class RepairTests(unittest.TestCase):
 def test_classifies_failure(self):
  result=suggest("AssertionError: expected: 1 but was: 2")
  self.assertEqual("Assertion failure",result["diagnoses"][0]["category"])
  self.assertFalse(result["patch_generated"])
 def test_limits_retries(self):
  result=suggest("TimeoutException",attempt=3)
  self.assertFalse(result["retry_allowed"])
  with self.assertRaises(ValueError):suggest("failure",attempt=6)
 def test_bounded_output(self):
  self.assertTrue(suggest("x"*10000)["log_truncated"])
if __name__=="__main__":unittest.main()
