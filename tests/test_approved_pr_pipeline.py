import sys
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_pr_pipeline import execute

class PipelineTests(unittest.TestCase):
 def make_checkout(self,root):
  def git(*args):
   return subprocess.run(["git",*args],cwd=root,check=True,capture_output=True,text=True).stdout.strip()
  git("init")
  git("-c","user.name=Test","-c","user.email=test@example.invalid",
      "-c","commit.gpgsign=false","commit","--allow-empty","-m","fixture")
  return git("rev-parse","HEAD")
 def test_requires_test_approval(self):
  with self.assertRaises(PermissionError):
   execute("/missing","python","Title","Body","a"*40)
 def test_never_publishes_failed_tests(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp);(root/".git").mkdir()
   publisher=Mock()
   with patch("approved_pr_pipeline._head",return_value="a"*40), patch("approved_pr_pipeline._clean"):
    result=execute(root,"python","Title","Body","a"*40,approve_tests=True,approve_publication=True,
      test_runner=lambda *a,**kw:{"verified":False,"containerized":True},publisher=publisher)
   self.assertFalse(result["published"])
   publisher.assert_not_called()
 def test_success_still_requires_publication_approval(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   commit=self.make_checkout(root)
   publisher=Mock()
   result=execute(root,"python","Title","Body",commit,approve_tests=True,
     test_runner=lambda *a,**kw:{"verified":True,"containerized":True},publisher=publisher)
   self.assertFalse(result["published"])
   self.assertEqual("explicit publication approval required",result["reason"])
   publisher.assert_not_called()
 def test_dirty_checkout_denied_before_tests(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   commit=self.make_checkout(root)
   (root/"untracked.txt").write_text("unapproved change",encoding="utf-8")
   runner,publisher=Mock(),Mock()
   with self.assertRaises(PermissionError):
    execute(root,"python","Title","Body",commit,approve_tests=True,
      approve_publication=True,test_runner=runner,publisher=publisher)
   runner.assert_not_called()
   publisher.assert_not_called()
 def test_checkout_changed_by_tests_never_published(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   commit=self.make_checkout(root)
   publisher=Mock()
   def runner(*args,**kwargs):
    (root/"untracked.txt").write_text("change during tests",encoding="utf-8")
    return {"verified":True,"containerized":True}
   with self.assertRaises(PermissionError):
    execute(root,"python","Title","Body",commit,approve_tests=True,
      approve_publication=True,test_runner=runner,publisher=publisher)
   publisher.assert_not_called()
if __name__=="__main__":unittest.main()
