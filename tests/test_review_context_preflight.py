import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from review_context_preflight import preflight

class ContextPreflightTests(unittest.TestCase):
 def test_metadata_only_and_no_transmission(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   repo=root/"demo"
   repo.mkdir()
   (repo/".git").mkdir()
   (repo/"Demo.java").write_text("class Demo {}")
   result=preflight(root,"demo")
   self.assertEqual("Demo.java",result["files"][0]["file"])
   self.assertEqual(64,len(result["files"][0]["sha256"]))
   self.assertNotIn("excerpt",str(result))
   self.assertTrue(result["approval_required"])
   self.assertFalse(result["source_transmitted"])
   self.assertFalse(result["model_invoked"])
if __name__=="__main__":unittest.main()
