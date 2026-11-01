import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from workflow_orchestrator import WorkflowStore

class WorkflowConcurrencyTests(unittest.TestCase):
 def test_stale_transition_rejected(self):
  with TemporaryDirectory() as d:
   store=WorkflowStore(d)
   store.create("job","repo","task")
   store.transition("job","prepare",expected_version=0)
   with self.assertRaises(RuntimeError):
    store.transition("job","prepare",expected_version=0)
 def test_last_failure_recorded_and_fourth_attempt_blocked(self):
  with TemporaryDirectory() as d:
   store=WorkflowStore(d)
   store.create("job","repo","task")
   store.transition("job","prepare",expected_version=0)
   store.transition("job","approve_patch",expected_version=1,approved=True)
   for n in range(3):
    store.transition("job","start_tests",expected_version=2+n*2,approved=True)
    store.transition("job","tests_failed",expected_version=3+n*2)
   self.assertEqual(3,store.load("job")["attempts"])
   with self.assertRaises(RuntimeError):
    store.transition("job","start_tests",expected_version=8,approved=True)
if __name__=="__main__":unittest.main()
