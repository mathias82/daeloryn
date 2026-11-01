import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from workflow_orchestrator import WorkflowStore
from workflow_recovery import inspect_interrupted,recover_failed_test

class RecoveryTests(unittest.TestCase):
 def test_recovery_requires_confirmation(self):
  with TemporaryDirectory() as d:
   store=WorkflowStore(d)
   store.create("job","repo","task")
   store.transition("job","prepare",expected_version=0)
   store.transition("job","approve_patch",expected_version=1,approved=True)
   store.transition("job","start_tests",expected_version=2,approved=True)
   self.assertEqual("manual_reconcile",inspect_interrupted(d)[0]["action"])
   with self.assertRaises(PermissionError):
    recover_failed_test(d,"job",3)
   state=recover_failed_test(d,"job",3,confirmed_not_running=True)
   self.assertEqual("patch_approved",state["stage"])
 def test_normal_workflow_not_reported(self):
  with TemporaryDirectory() as d:
   WorkflowStore(d).create("job","repo","task")
   self.assertEqual([],inspect_interrupted(d))
if __name__=="__main__":unittest.main()
