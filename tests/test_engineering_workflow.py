import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from engineering_workflow import Workflow, Stage, advance, describe

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
 def test_invalid_digest(self):
  with self.assertRaises(ValueError):
   advance(Workflow("demo"),Stage.CONTEXT_APPROVED,approval=True,digest="bad")
if __name__=="__main__":unittest.main()
