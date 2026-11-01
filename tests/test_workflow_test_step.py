import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from workflow_orchestrator import WorkflowStore
from workflow_test_support import WorkflowFixture


class WorkflowTestStepTests(unittest.TestCase):
 def test_successful_approved_test_step(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   result=f.run_tests()
   self.assertTrue(result["passed"])
   state=WorkflowStore(Path(d)/"workflows").load("run1")
   self.assertEqual("tests_passed",state["stage"])
   evidence=state["test_evidence"]
   self.assertEqual(f.commit,evidence["subject"]["snapshot"]["commit"])
   self.assertEqual("org/repo",evidence["subject"]["snapshot"]["repository"])
   self.assertEqual(64,len(evidence["result_sha256"]))
   with self.assertRaises(RuntimeError):f.run_tests()
 def test_failed_test_result_does_not_advance(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   result=f.run_tests(lambda *a,**k:{"verified":False,"containerized":True})
   self.assertFalse(result["passed"])
   self.assertEqual("patch_approved",f.state["stage"])
   self.assertNotIn("test_evidence",f.state)
 def test_arbitrary_digest_never_runs_or_changes_state(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   runner=Mock()
   with self.assertRaises(PermissionError):f.run_tests(runner,digest="a"*64)
   runner.assert_not_called()
   self.assertEqual("patch_approved",f.store.load("run1")["stage"])
 def test_invalid_token_does_not_reserve_workflow(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   runner=Mock()
   with self.assertRaises(PermissionError):f.run_tests(runner,token="invalid")
   runner.assert_not_called()
   self.assertEqual("patch_approved",f.store.load("run1")["stage"])
 def test_mutation_during_successful_tests_is_unverified(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   def runner(*a,**kw):
    (f.root/"source.txt").write_text("changed",encoding="utf-8")
    return {"verified":True,"containerized":True}
   with self.assertRaises(PermissionError):f.run_tests(runner)
   state=f.store.load("run1")
   self.assertEqual("tests_running",state["stage"])
   self.assertNotIn("test_evidence",state)
 def test_timeout_requires_reconciliation(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   def runner(*a,**kw):raise TimeoutError("unknown runner outcome")
   with self.assertRaises(TimeoutError):f.run_tests(runner)
   self.assertEqual("tests_running",f.store.load("run1")["stage"])

if __name__=="__main__":unittest.main()
