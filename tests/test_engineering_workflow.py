import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from engineering_workflow import Workflow, Stage, advance, describe
from code_review import review
from tempfile import TemporaryDirectory

DIGEST = "a"*64
class WorkflowTests(unittest.TestCase):
 def test_approval_and_sequence(self):
  workflow=Workflow("demo")
  with self.assertRaises(ValueError):
   advance(workflow,Stage.PROPOSAL_READY)
  with self.assertRaises(PermissionError):
   advance(workflow,Stage.CONTEXT_APPROVED,digest=DIGEST)
  workflow=advance(workflow,Stage.CONTEXT_APPROVED,approval=True,digest=DIGEST)
  workflow=advance(workflow,Stage.PROPOSAL_READY)
  with self.assertRaises(PermissionError):
   advance(workflow,Stage.PATCH_APPROVED,digest=DIGEST)
  workflow=advance(workflow,Stage.PATCH_APPROVED,approval=True,digest=DIGEST)
  with self.assertRaises(ValueError):
   advance(workflow,Stage.TESTS_VERIFIED,evidence={"verified":False})
  workflow=advance(workflow,Stage.TESTS_VERIFIED,evidence={"verified":True})
  workflow=advance(workflow,Stage.PR_READY,evidence={"verified":True})
  self.assertEqual(Stage.PR_READY,workflow.stage)
  self.assertFalse(describe(workflow)["pr_created"])
 def test_review_exposes_unexecuted_workflow(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   checkout=root/"demo"
   checkout.mkdir()
   (checkout/".git").mkdir()
   (checkout/"Demo.java").write_text("class Demo {}")
   state=review(root,"demo","Review Java")["workflow"]
   self.assertEqual("inspected",state["stage"])
   self.assertFalse(state["source_transmitted"])
   self.assertFalse(state["patch_applied"])
   self.assertFalse(state["pr_created"])
 def test_invalid_digest(self):
  with self.assertRaises(ValueError):
   advance(Workflow("demo"),Stage.CONTEXT_APPROVED,approval=True,digest="bad")
if __name__=="__main__":unittest.main()
