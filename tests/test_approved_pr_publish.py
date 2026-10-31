import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_pr_publish import publish

class PublishTests(unittest.TestCase):
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
