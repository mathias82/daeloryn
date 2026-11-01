import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_repair_proposal import prepare,propose

class RepairProposalTests(unittest.TestCase):
 def test_no_model_call_without_exact_consent(self):
  prepared=prepare("App.java","class App {}","AssertionError")
  calls=[]
  def transport(req):
   calls.append(req);return {"reply":"class App { }"}
  with self.assertRaises(PermissionError):
   propose(prepared,"0"*64,"model",transport)
  self.assertEqual([],calls)
  result=propose(prepared,prepared["sha256"],"model",transport)
  self.assertEqual(1,len(calls))
  self.assertFalse(result["patch_applied"])
  self.assertTrue(result["patch"]["approval_required"])
 def test_rejects_tampered_context(self):
  prepared=prepare("App.java","class App {}","AssertionError")
  prepared["source"]="class Changed {}"
  with self.assertRaises(PermissionError):
   propose(prepared,prepared["sha256"],"model",lambda x:None)
if __name__=="__main__":unittest.main()
