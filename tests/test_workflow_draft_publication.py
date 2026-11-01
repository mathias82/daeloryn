import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from workflow_draft_publication import publish_workflow_draft
from workflow_orchestrator import WorkflowStore
from workflow_test_support import WorkflowFixture
from reliable_container_tests import SUITES
from execution_authorization import Principal


class DraftPublicationTests(unittest.TestCase):
 def publish(self,f,digest,token,publisher,**overrides):
  args=dict(store=f.store,workflow_id="run1",expected_version=f.state["version"],
            principal=f.principal,registry=f.registry,digest=digest,
            approval_token=token,approval_gate=f.gate,title="Title",body="Body",
            expected_commit=f.commit,publisher=publisher)
  args.update(overrides)
  return publish_workflow_draft(**args)
 def publisher(self,f):
  return Mock(return_value={"published":True,"draft_pr_created":True,
                           "commit":f.commit,"branch":"daeloryn/fix"})
 def test_verified_tests_to_draft_publication_survives_restart(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   f.run_tests()
   digest,token=f.publication()
   f.store=WorkflowStore(Path(d)/"workflows")
   publisher=self.publisher(f)
   result=self.publish(f,digest,token,publisher)
   self.assertEqual("published",result["workflow"]["stage"])
   saved=WorkflowStore(Path(d)/"workflows").load("run1")
   self.assertEqual(digest,saved["publication_evidence"]["subject"]["digest"])
   publisher.assert_called_once_with(f.root,"Title","Body",f.commit,approved=True,
     expected_repository="org/repo",expected_push_url="https://github.com/org/repo.git",
     expected_branch="daeloryn/fix")
   with self.assertRaises(RuntimeError):self.publish(f,digest,token,publisher)
   publisher.assert_called_once()
 def test_unverified_workflow_denied(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   publisher=self.publisher(f)
   with self.assertRaises(RuntimeError):self.publish(f,"a"*64,"token",publisher)
   publisher.assert_not_called()
 def test_legacy_boolean_evidence_requires_retesting(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   f.state=f.store.transition("run1","start_tests",expected_version=2,approved=True)
   f.state=f.store.transition("run1","tests_passed",expected_version=3,evidence={"verified":True})
   publisher=self.publisher(f)
   with self.assertRaises((PermissionError,ValueError)):
    self.publish(f,"a"*64,"token",publisher)
   publisher.assert_not_called()
 def test_expired_or_invalid_token_does_not_poison_state(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   f.run_tests()
   digest,token=f.publication()
   publisher=self.publisher(f)
   with self.assertRaises(PermissionError):self.publish(f,digest,"invalid",publisher)
   self.assertEqual("tests_passed",f.store.load("run1")["stage"])
   publisher.assert_not_called()
   self.publish(f,digest,token,publisher)
   publisher.assert_called_once()
 def test_expired_token_leaves_verified_workflow_available(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   f.run_tests()
   digest,token=f.publication()
   publisher=self.publisher(f)
   with patch.object(f.gate,"clock",return_value=10**12):
    with self.assertRaises(PermissionError):self.publish(f,digest,token,publisher)
   self.assertEqual("tests_passed",f.store.load("run1")["stage"])
   publisher.assert_not_called()
   with self.assertRaises(PermissionError):f.gate.consume(token,"publish_pr","org/repo",digest)
 def test_unauthorized_repository_does_not_consume_token(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   f.run_tests()
   digest,token=f.publication()
   publisher=self.publisher(f)
   principal=Principal("other",frozenset({"org/other"}),frozenset({"publish_pr"}),True)
   with self.assertRaises(PermissionError):self.publish(f,digest,token,publisher,principal=principal)
   publisher.assert_not_called()
   self.assertTrue(f.gate.consume(token,"publish_pr","org/repo",digest))
 def test_metadata_or_commit_change_does_not_consume_approval(self):
  for change in ({"title":"Different"},{"body":"Different"},{"expected_commit":"b"*40}):
   with self.subTest(change=change),TemporaryDirectory() as d:
    f=WorkflowFixture(d)
    f.run_tests()
    digest,token=f.publication()
    publisher=self.publisher(f)
    with self.assertRaises(PermissionError):self.publish(f,digest,token,publisher,**change)
    publisher.assert_not_called()
    self.assertEqual("tests_passed",f.store.load("run1")["stage"])
    self.assertTrue(f.gate.consume(token,"publish_pr","org/repo",digest))
 def test_changed_checkout_or_destination_never_published(self):
  def dirty(f): (f.root/"source.txt").write_text("modified",encoding="utf-8")
  def new_commit(f): f.git("commit","--allow-empty","-m","unapproved")
  def branch(f): f.git("checkout","-b","daeloryn/other")
  def destination(f): f.git("remote","set-url","--push","origin","https://github.com/org/other.git")
  def multiple_destinations(f):
   f.git("remote","set-url","--push","origin","https://github.com/org/repo.git")
   f.git("remote","set-url","--add","--push","origin","https://github.com/org/other.git")
  def mirror(f): f.git("config","remote.origin.mirror","true")
  def ignored(f):
   (f.root/".git"/"info"/"exclude").write_text("hidden.txt\n",encoding="utf-8")
   (f.root/"hidden.txt").write_text("untracked build input",encoding="utf-8")
  for mutate in (dirty,new_commit,branch,destination,multiple_destinations,mirror,ignored):
   with self.subTest(mutate=mutate.__name__),TemporaryDirectory() as d:
    f=WorkflowFixture(d)
    f.run_tests()
    digest,token=f.publication()
    mutate(f)
    publisher=self.publisher(f)
    with self.assertRaises(PermissionError):self.publish(f,digest,token,publisher)
    publisher.assert_not_called()
    self.assertEqual("tests_passed",f.store.load("run1")["stage"])
    self.assertTrue(f.gate.consume(token,"publish_pr","org/repo",digest))
 def test_changed_suite_configuration_requires_retesting(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   f.run_tests()
   digest,token=f.publication()
   publisher=self.publisher(f)
   with patch.dict(SUITES,{"python":("different-image",["different-command"])}):
    with self.assertRaises(PermissionError):self.publish(f,digest,token,publisher)
   publisher.assert_not_called()
 def test_changed_result_evidence_invalidates_approval(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   f.run_tests()
   digest,token=f.publication()
   state=f.store.load("run1")
   state["test_evidence"]["result_sha256"]="b"*64
   f.store._save("run1",state)
   publisher=self.publisher(f)
   with self.assertRaises(PermissionError):self.publish(f,digest,token,publisher)
   publisher.assert_not_called()
 def test_concurrent_attempts_publish_once(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   f.run_tests()
   digest,token=f.publication()
   publisher=self.publisher(f)
   def attempt(_):
    try:
     self.publish(f,digest,token,publisher)
     return True
    except (PermissionError,RuntimeError):return False
   with ThreadPoolExecutor(max_workers=2) as pool:
    self.assertEqual(1,sum(pool.map(attempt,range(2))))
   publisher.assert_called_once()
 def test_mutation_during_approval_never_invokes_publisher(self):
  with TemporaryDirectory() as d:
   f=WorkflowFixture(d)
   f.run_tests()
   digest,token=f.publication()
   publisher=self.publisher(f)
   consume=f.gate.consume
   def mutate(*args):
    result=consume(*args)
    (f.root/"source.txt").write_text("changed",encoding="utf-8")
    return result
   with patch.object(f.gate,"consume",side_effect=mutate):
    with self.assertRaises(PermissionError):self.publish(f,digest,token,publisher)
   publisher.assert_not_called()
   self.assertEqual("publication_approved",f.store.load("run1")["stage"])
 def test_unknown_or_incorrect_publication_outcome_cannot_retry(self):
  for mode in ("timeout","unverified","wrong_commit"):
   with self.subTest(mode=mode),TemporaryDirectory() as d:
    f=WorkflowFixture(d)
    f.run_tests()
    digest,token=f.publication()
    publisher=self.publisher(f)
    if mode=="timeout":publisher.side_effect=TimeoutError("push may have succeeded")
    elif mode=="unverified":publisher.return_value={"published":True}
    else:publisher.return_value["commit"]="b"*40
    with self.assertRaises((TimeoutError,RuntimeError)):self.publish(f,digest,token,publisher)
    self.assertEqual("publication_approved",f.store.load("run1")["stage"])
    with self.assertRaises(RuntimeError):self.publish(f,digest,token,publisher)
    publisher.assert_called_once()

if __name__=="__main__":unittest.main()
