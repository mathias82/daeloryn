import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_copilot_review import prepare, execute

class ApprovedCopilotReviewTests(unittest.TestCase):
 def test_digest_approval_and_no_writes(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   checkout=root/"demo"
   checkout.mkdir()
   (checkout/".git").mkdir()
   (checkout/"App.java").write_text("class App {}")
   prepared=prepare(root,"demo","Review Java","gpt-5")
   calls=[]
   def transport(request):
    calls.append(request)
    return {"reply":"No verified findings"}
   with self.assertRaises(PermissionError):
    execute(prepared,"gpt-5", "bad",transport=transport)
   self.assertEqual([],calls)
   result=execute(prepared,"gpt-5",prepared["sha256"],transport=transport)
   self.assertEqual(1,len(calls))
   self.assertFalse(result["patch_applied"])
   self.assertFalse(result["tests_executed"])
   self.assertFalse(result["pull_request_created"])
 def test_tampered_prompt_fails_closed(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   checkout=root/"demo"
   checkout.mkdir()
   (checkout/".git").mkdir()
   (checkout/"App.java").write_text("class App {}")
   prepared=prepare(root,"demo","Review","gpt-5")
   prepared["prompt"]+="tampered"
   with self.assertRaises(PermissionError):
    execute(prepared,"gpt-5",prepared["sha256"],transport=lambda _: {})
if __name__=="__main__":unittest.main()
