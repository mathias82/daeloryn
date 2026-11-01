import http.client
import json
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from console_api import make_handler

class ApprovedReviewApiTests(unittest.TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory()
  self.root=Path(self.tmp.name)
  self.repo=self.root/"demo"
  self.repo.mkdir()
  (self.repo/".git").mkdir()
  (self.repo/"App.java").write_text("class App {}")
  self.server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(enable_copilot=True,repository_roots=[self.root]))
  self.worker=threading.Thread(target=self.server.serve_forever,daemon=True)
  self.worker.start()
 def tearDown(self):
  self.server.shutdown()
  self.server.server_close()
  self.worker.join(timeout=2)
  self.tmp.cleanup()
 def post(self,path,body):
  conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
  conn.request("POST",path,json.dumps(body),{"Host":"127.0.0.1:"+str(self.server.server_port),"Origin":"http://127.0.0.1:5173","Content-Type":"application/json"})
  response=conn.getresponse()
  result=response.status,json.loads(response.read())
  conn.close()
  return result
 def test_prepare_requires_model_to_bind_approval(self):
  code,_=self.post("/api/copilot/review/prepare",{"repository":"demo","task":"Review"})
  self.assertEqual(400,code)
 def test_requires_exact_digest_and_rechecks_source(self):
  request={"repository":"demo","task":"Review","model":"test"}
  code,prepared=self.post("/api/copilot/review/prepare",request)
  self.assertEqual(200,code)
  self.assertIn("class App",prepared["prompt"])
  self.assertFalse(prepared["source_transmitted"])
  with patch("console_api.execute_ai_review",side_effect=PermissionError("bad digest")) as mocked:
   code,_=self.post("/api/copilot/review/execute",{**request,"model":"test","approved_sha256":"bad"})
   self.assertEqual(400,code)
   mocked.assert_called_once()
  from approved_copilot_review import execute as actual
  with self.assertRaises(PermissionError):
   actual(prepared,"test","bad",transport=lambda _: {"reply":"never"})
  self.repo.joinpath("App.java").write_text("class Changed {}")
  code,changed=self.post("/api/copilot/review/prepare",request)
  self.assertEqual(200,code)
  self.assertNotEqual(prepared["sha256"],changed["sha256"])
 def test_stream_flushes_progress_before_provider_completion(self):
  from approved_copilot_review import execute as actual
  entered=threading.Event()
  release=threading.Event()
  def transport(request, **kwargs):
   entered.set()
   if not release.wait(3):raise RuntimeError("test release timed out")
   return {"reply":"Fixture review"}
  def executor(prepared, model, digest, **kwargs):
   return actual(prepared,model,digest,transport=transport,**kwargs)
  request={"repository":"demo","task":"Review","model":"test"}
  _,prepared=self.post("/api/copilot/review/prepare",request)
  conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
  self.addCleanup(conn.close)
  self.addCleanup(release.set)
  with patch("console_api.execute_ai_review",side_effect=executor):
   conn.request("POST","/api/copilot/review/execute",json.dumps({**request,"approved_sha256":prepared["sha256"]}),
    {"Origin":"http://127.0.0.1:5173","Content-Type":"application/json","Accept":"application/x-ndjson"})
   response=conn.getresponse()
   self.assertEqual(200,response.status)
   event=json.loads(response.readline())
   self.assertEqual("running",event["phase"])
   self.assertTrue(entered.wait(1))
   release.set()
   events=[json.loads(line) for line in response.read().splitlines()]
   self.assertEqual("completed_batch",events[0]["phase"])
   self.assertEqual("completed",events[-1]["result"]["status"])
   self.assertIn("Fixture review",events[-1]["result"]["review"]["reply"])
if __name__=="__main__":unittest.main()
