import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_pr_publish import publish

class PublishTests(unittest.TestCase):
 def test_push_uses_approved_object_and_explicit_repository(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp);(root/".git").mkdir()
   url="https://github.com/org/repo.git"
   with patch("approved_pr_publish._git",side_effect=["daeloryn/fix","a"*40,"",url,""]) as git:
    with patch("approved_pr_publish.subprocess.run",return_value=SimpleNamespace(returncode=0,stdout="https://github.com/org/repo/pull/1")) as gh:
     publish(root,"Title","Body","a"*40,approved=True,
             expected_repository="org/repo",expected_push_url=url)
   git.assert_any_call(root,"push",url,"a"*40+":refs/heads/daeloryn/fix")
   self.assertEqual(["gh","pr","create","--draft","--head","daeloryn/fix",
                     "--title","Title","--body","Body","--repo","org/repo"],gh.call_args.args[0])
 def test_changed_push_url_is_denied_before_network(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp);(root/".git").mkdir()
   with patch("approved_pr_publish._git",side_effect=["daeloryn/fix","a"*40,"","https://github.com/org/other.git"]) as git:
    with patch("approved_pr_publish.subprocess.run") as gh:
     with self.assertRaises(PermissionError):
      publish(root,"Title","Body","a"*40,approved=True,
              expected_repository="org/repo",expected_push_url="https://github.com/org/repo.git")
     gh.assert_not_called()
   self.assertFalse(any(call.args[1]=="push" for call in git.call_args_list))
 def test_requires_approval_before_git(self):
  with patch("approved_pr_publish.subprocess.run") as runner:
   with self.assertRaises(PermissionError):
    publish("/missing","Title","Body","a"*40)
   runner.assert_not_called()
 def test_rejects_invalid_commit(self):
  with self.assertRaises(ValueError):
   publish("/missing","Title","Body","not-a-sha",approved=True)
 def test_rejects_non_git_checkout(self):
  with TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):
    publish(tmp,"Title","Body","a"*40,approved=True)
if __name__=="__main__":unittest.main()
