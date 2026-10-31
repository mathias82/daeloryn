import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from code_context import scan
from code_review import review

class CodeAwareTests(unittest.TestCase):
 def setUp(self):
  self.temp=TemporaryDirectory()
  self.root=Path(self.temp.name)
  self.repo=self.root/"demo"
  self.repo.mkdir()
  (self.repo/".git").mkdir()
  (self.repo/"src").mkdir()
 def tearDown(self):
  self.temp.cleanup()
 def test_read_code_and_evidence(self):
  (self.repo/"src"/"Demo.java").write_text(
   "class Demo {\n void stop() { System.exit(1); }\n}\n")
  result=review(self.root,"demo","Review Java")
  self.assertEqual("src/Demo.java",result["findings"][0]["file"])
  self.assertEqual(2,result["findings"][0]["line"])
  self.assertFalse(result["changes_made"])
 def test_sensitive_file_excluded(self):
  (self.repo/"src"/"credentials.py").write_text("password='secret'")
  self.assertEqual([],scan(self.root,"demo")["files"])
 def test_redact_sensitive_line(self):
  (self.repo/"src"/"safe.py").write_text("token = 'not-for-model'\nprint('ok')")
  text=scan(self.root,"demo")["files"][0]["excerpt"]
  self.assertNotIn("not-for-model",text)
  self.assertIn("[REDACTED]",text)
 def test_symlink_excluded(self):
  outside=self.root/"outside.py"
  outside.write_text("print('outside')")
  (self.repo/"src"/"outside.py").symlink_to(outside)
  self.assertEqual([],scan(self.root,"demo")["files"])
 def test_oversize_file_excluded(self):
  (self.repo/"src"/"huge.java").write_text("x"*30000)
  self.assertEqual([],scan(self.root,"demo")["files"])
if __name__=="__main__":unittest.main()
