import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from workflow_gates import Evidence,approve_patch,verify_tests,approve_publication,publish_approved

class WorkflowGateTests(unittest.TestCase):
 def test_rejects_out_of_order_and_unverified_tests(self):
  e=Evidence("/tmp/missing","daeloryn/fix","a"*64)
  with self.assertRaises(PermissionError): verify_tests(e,{"verified":True,"containerized":True},"b"*40)
  with self.assertRaises(PermissionError): approve_patch(e,"0"*64)
  e=approve_patch(e,"a"*64)
  with self.assertRaises(PermissionError): verify_tests(e,{"verified":True,"containerized":False},"b"*40)
  e=verify_tests(e,{"verified":True,"containerized":True},"b"*40)
  with self.assertRaises(PermissionError): approve_publication(e,"c"*40)
 def test_publish_requires_approval_and_exact_commit(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp); (root/".git").mkdir()
   e=Evidence(str(root),"daeloryn/fix","a"*64)
   called=[]
   def publish(*args,**kwargs):
    called.append((args,kwargs));return {"draft_pr_created":True}
   with self.assertRaises(PermissionError):
    publish_approved(e,"title","body",publish=publish)
   e=approve_patch(e,"a"*64)
   e=verify_tests(e,{"verified":True,"containerized":True},"b"*40)
   e=approve_publication(e,"b"*40)
   final,result=publish_approved(e,"title","body",publish=publish)
   self.assertEqual("published",final.stage)
   self.assertEqual("b"*40,called[0][0][3])
if __name__=="__main__":unittest.main()
