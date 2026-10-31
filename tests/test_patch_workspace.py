import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from patch_workspace import preview,verify_preview

class PatchWorkspaceTests(unittest.TestCase):
 def test_preview_is_read_only_and_stale_digest_fails(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   repo=root/"demo"
   repo.mkdir()
   (repo/".git").mkdir()
   source=repo/"App.java"
   source.write_text("class App {}")
   result=preview(root,"demo","App.java","class App { }")
   self.assertIn("-class App {}",result["diff"])
   self.assertEqual("class App {}",source.read_text())
   verify_preview(root,"demo","App.java","class App { }",result["sha256"])
   source.write_text("class Changed {}")
   with self.assertRaises(PermissionError):
    verify_preview(root,"demo","App.java","class App { }",result["sha256"])
 def test_reject_path_traversal(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   repo=root/"demo"
   repo.mkdir()
   (repo/".git").mkdir()
   with self.assertRaises(ValueError):
    preview(root,"demo","../secret.py","print(1)")
if __name__=="__main__":unittest.main()
