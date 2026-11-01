import http.client
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from console_api import make_handler
from patch_workspace import preview

class PatchApplyApiTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.repo=self.root/'demo';self.repo.mkdir()
  for args in [['init'],['config','user.name','Fixture'],['config','user.email','fixture@example.invalid'],['config','core.autocrlf','false']]:
   subprocess.run(['git',*args],cwd=self.repo,check=True,capture_output=True)
  self.file=self.repo/'App.java';self.file.write_bytes(b'class App {}\n')
  subprocess.run(['git','add','App.java'],cwd=self.repo,check=True,capture_output=True)
  subprocess.run(['git','commit','-m','Fixture'],cwd=self.repo,check=True,capture_output=True)
 def start(self,enabled):
  server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(repository_roots=[self.root],enable_patch_apply=enabled))
  worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
  self.addCleanup(worker.join,2);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
  return server
 def post(self,server,body,origin='http://127.0.0.1:5173'):
  conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
  conn.request('POST','/api/patch/apply',json.dumps(body),{'Origin':origin,'Content-Type':'application/json'})
  response=conn.getresponse();code=response.status;data=json.loads(response.read());conn.close();return code,data
 def payload(self):
  replacement='class App { int x; }\n'
  p=preview(self.root,'demo','App.java',replacement)
  return {'repository':'demo','path':'App.java','replacement':replacement,'approved_sha256':p['sha256'],'branch':'daeloryn/fixture-fix','approved':True}
 def test_disabled_origin_consent_and_stale_source_never_write(self):
  body=self.payload();server=self.start(False)
  self.assertEqual(405,self.post(server,body)[0])
  server=self.start(True)
  self.assertEqual(403,self.post(server,body,'https://evil.invalid')[0])
  self.assertEqual(400,self.post(server,{**body,'approved':False})[0])
  self.assertEqual(400,self.post(server,{**body,'approved_sha256':'bad'})[0])
  self.file.write_bytes(b'class Changed {}\n')
  self.assertEqual(400,self.post(server,body)[0])
  self.assertEqual(b'class Changed {}\n',self.file.read_bytes())
 def test_exact_patch_applies_on_dedicated_branch_without_commit_or_tests(self):
  body=self.payload();server=self.start(True)
  old=subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.repo)
  code,result=self.post(server,body)
  self.assertEqual(200,code);self.assertTrue(result['applied']);self.assertFalse(result['tests_executed'])
  self.assertEqual(body['replacement'].encode(),self.file.read_bytes())
  self.assertEqual('daeloryn/fixture-fix',subprocess.check_output(['git','branch','--show-current'],cwd=self.repo,text=True).strip())
  self.assertEqual(old,subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.repo))
  self.assertEqual(400,self.post(server,body)[0])
 def test_dirty_checkout_rejects_before_branch_creation(self):
  body=self.payload();(self.repo/'untracked.txt').write_bytes(b'dirty')
  self.assertEqual(400,self.post(self.start(True),body)[0])
  self.assertEqual(b'class App {}\n',self.file.read_bytes())
