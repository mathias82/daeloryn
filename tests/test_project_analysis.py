import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from project_analysis import analyze_local
class ProjectAnalysisTests(unittest.TestCase):
 def test_markers_without_source_reads(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp); p=root/"payment-service";p.mkdir()
   (p/".git").mkdir();(p/"pom.xml").write_text("secret should not appear")
   (p/"src").mkdir()
   result=analyze_local(root,"payment-service")
   self.assertEqual(0,result["files_read"])
   self.assertEqual("not_run",result["execution"])
   self.assertIn("src",result["top_level_directories"])
   self.assertNotIn("secret",str(result))
 def test_reject_traversal(self):
  with TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):analyze_local(tmp,"../outside")
 def test_reject_symlink_checkout(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp); p=root/"real";p.mkdir();(p/".git").mkdir()
   (root/"alias").symlink_to(p,target_is_directory=True)
   with self.assertRaises(ValueError):analyze_local(root,"alias")
 def test_reject_missing_git(self):
  with TemporaryDirectory() as tmp:
   (Path(tmp)/"plain").mkdir()
   with self.assertRaises(ValueError):analyze_local(tmp,"plain")
if __name__=="__main__":unittest.main()
