import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from workflow_orchestrator import WorkflowStore

class WorkflowTests(unittest.TestCase):
 def test_persists_and_rejects_skips(self):
  with TemporaryDirectory() as tmp:
   store=WorkflowStore(tmp)
   store.create("one","demo","Fix bug")
   with self.assertRaises(ValueError):store.transition("one","published",expected_version=0,approved=True,evidence={"verified":True})
   s=store.transition("one","prepare",expected_version=0)
   with self.assertRaises(PermissionError):store.transition("one","approve_patch",expected_version=1)
   s=store.transition("one","approve_patch",expected_version=1,approved=True)
   self.assertEqual("patch_approved",WorkflowStore(tmp).load("one")["stage"])
   with self.assertRaises(RuntimeError):store.transition("one","start_tests",expected_version=1,approved=True)
 def test_failed_tests_return_for_review(self):
  with TemporaryDirectory() as tmp:
   store=WorkflowStore(tmp);store.create("one","demo","Fix")
   for event,approved in [("prepare",False),("approve_patch",True),("start_tests",True),("tests_failed",False)]:
    s=store.load("one");store.transition("one",event,expected_version=s["version"],approved=approved)
   self.assertEqual("patch_approved",store.load("one")["stage"])
if __name__=="__main__":unittest.main()
