import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_repair_validation import validate_repair
class RepairValidationTests(unittest.TestCase):
 def test_no_mutation_without_both_approvals(self):
  applier=Mock()
  with self.assertRaises(PermissionError):
   validate_repair("/missing","demo","App.java","replacement","a"*64,"daeloryn/fix","python",approve_apply=True,applier=applier)
  applier.assert_not_called()
 def test_failed_tests_not_reported_verified(self):
  with TemporaryDirectory() as tmp:
   result=validate_repair(tmp,"demo","App.java","replacement","a"*64,"daeloryn/fix","python",
    approve_apply=True,approve_tests=True,
    applier=lambda *a,**kw:{"applied":True,"sha256":"a"*64},
    runner=lambda *a,**kw:{"verified":False,"containerized":True})
   self.assertFalse(result["verified"])
   self.assertFalse(result["pr_created"])
 def test_non_containerized_results_rejected(self):
  with TemporaryDirectory() as tmp:
   result=validate_repair(tmp,"demo","App.java","replacement","a"*64,"daeloryn/fix","python",
    approve_apply=True,approve_tests=True,
    applier=lambda *a,**kw:{"applied":True,"sha256":"a"*64},
    runner=lambda *a,**kw:{"verified":True,"containerized":False})
   self.assertFalse(result["verified"])
if __name__=="__main__":unittest.main()
