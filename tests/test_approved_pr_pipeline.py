import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_pr_pipeline import execute

class PipelineTests(unittest.TestCase):
 def test_requires_test_approval(self):
  with self.assertRaises(PermissionError):
   execute("/missing","python","Title","Body","a"*40)
 def test_never_publishes_failed_tests(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp);(root/".git").mkdir()
   publisher=Mock()
   with patch("approved_pr_pipeline._head",return_value="a"*40):
    result=execute(root,"python","Title","Body","a"*40,approve_tests=True,approve_publication=True,
      test_runner=lambda *a,**kw:{"verified":False,"containerized":True},publisher=publisher)
   self.assertFalse(result["published"])
   publisher.assert_not_called()
 def test_success_still_requires_publication_approval(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp);(root/".git").mkdir()
   publisher=Mock()
   with patch("approved_pr_pipeline._head",return_value="a"*40):
    result=execute(root,"python","Title","Body","a"*40,approve_tests=True,
      test_runner=lambda *a,**kw:{"verified":True,"containerized":True},publisher=publisher)
   self.assertFalse(result["published"])
   publisher.assert_not_called()
if __name__=="__main__":unittest.main()
