import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from patch_proposal import proposal, propose_with_model
from engineering_executor import apply_approved, run_tests, create_draft_pr
from engineering_pipeline import plan

class EngineeringPipelineTests(unittest.TestCase):
 def test_diff_digest_and_path_rejection(self):
  result=proposal("src/App.java","class App {}\n","class App { }\n")
  self.assertIn("-class App {}",result["diff"])
  self.assertFalse(result["applied"])
  for path in ("../secret.py","/tmp/a.py",".github/workflow.py","src\\a.py"):
   with self.assertRaises(ValueError):
    proposal(path,"before","after")
 def test_model_proposes_without_write(self):
  with patch("engineering_executor.command") as run:
   result=propose_with_model("App.java","class App {}","Fix spacing","test",
     lambda _:{"reply":"class App { }"})
   self.assertTrue(result["approval_required"])
   run.assert_not_called()
 def test_approval_blocks_writes(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   (root/".git").mkdir()
   (root/"App.java").write_text("before")
   with self.assertRaises(PermissionError):
    apply_approved(root,"App.java","before","after","bad","daeloryn/fix")
   self.assertEqual("before",(root/"App.java").read_text())
   with self.assertRaises(PermissionError):
    run_tests(root,"python",approved=False)
   with self.assertRaises(PermissionError):
    create_draft_pr(root,"Fix","Body",approved=False,verified_tests={"verified":True})
 def test_pipeline_is_not_claimed_autonomous(self):
  p=plan("Fix bug","repo")
  self.assertEqual(5,len(p["steps"]))
  self.assertFalse(p["autonomous"])
if __name__=="__main__":unittest.main()
