import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from code_review import review
from review_action_plan import plan

class RemediationPlanTests(unittest.TestCase):
 def test_plan_has_explicit_non_execution_flags(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   repo=root/"demo"
   repo.mkdir()
   (repo/".git").mkdir()
   (repo/"Demo.java").write_text("class Demo { void stop() { System.exit(1); } }")
   result=review(root,"demo","Review Java")
   remediation=result["remediation_plan"]
   self.assertTrue(remediation["approval_required"])
   self.assertFalse(remediation["patch_generated"])
   self.assertFalse(remediation["tests_executed"])
   self.assertFalse(remediation["pull_request_created"])
   self.assertIn("lifecycle",remediation["actions"][0]["regression_test"])
 def test_rejects_invalid_findings(self):
  with self.assertRaises(ValueError):
   plan({"findings":[{"file":"a","line":0,"rule":"x","suggested_fix":"fix"}]})
if __name__=="__main__":unittest.main()
