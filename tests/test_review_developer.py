import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_developer import prepare,execute

class DeveloperTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.repo=self.root/'demo';(self.repo/'.git').mkdir(parents=True)
  self.file=self.repo/'App.java';self.file.write_text('class App { int x = 0; }\n')
 def test_handoff_returns_diff_without_modification(self):
  original=self.file.read_text();p=prepare(self.root,'demo','App.java','App.java:1 initialize x to 1','sonnet')
  calls=[]
  def transport(request,**kwargs):
   calls.append(request);self.assertEqual('java-developer',request['agent'])
   return {'reply':'class App { int x = 1; }\n'}
  with self.assertRaises(PermissionError):execute(p,'bad',self.root,transport=transport)
  self.assertEqual([],calls)
  result=execute(p,p['sha256'],self.root,transport=transport)
  self.assertIn('+class App',result['patch']['diff']);self.assertFalse(result['patch_applied'])
  self.assertEqual(original,self.file.read_text())
 def test_source_changes_invalidate_api_reprepared_digest(self):
  p=prepare(self.root,'demo','App.java','Review','sonnet');self.file.write_text('class Changed {}\n')
  changed=prepare(self.root,'demo','App.java','Review','sonnet')
  with self.assertRaises(PermissionError):execute(changed,p['sha256'],self.root,transport=lambda *a,**kw:self.fail('called'))
 def test_changed_source_during_model_call_discards_patch(self):
  p=prepare(self.root,'demo','App.java','Review','sonnet')
  def transport(*args,**kwargs):
   self.file.write_text('class Concurrent {}\n');return {'reply':'class Proposed {}\n'}
  with self.assertRaises(PermissionError):execute(p,p['sha256'],self.root,transport=transport)
 def test_paths_redaction_and_auto_rejected(self):
  for path in ['../App.java','/etc/passwd','missing.java']:
   with self.assertRaises(ValueError):prepare(self.root,'demo',path,'Review','sonnet')
  with self.assertRaises(ValueError):prepare(self.root,'demo','App.java','Review','auto')
  self.file.write_text('class App { String password = "fake"; }\n')
  with self.assertRaises(ValueError):prepare(self.root,'demo','App.java','Review','sonnet')

class DeveloperApiTests(unittest.TestCase):
 def test_api_rechecks_source_and_rejects_unknown_fields(self):
  import http.client,json,threading
  from http.server import ThreadingHTTPServer
  from console_api import make_handler
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);repo=root/'demo';(repo/'.git').mkdir(parents=True)
   file=repo/'App.java';file.write_text('class App {}\n')
   server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(enable_copilot=True,repository_roots=[root]))
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   def post(path,body):
    conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
    conn.request('POST',path,json.dumps(body),{'Origin':'http://127.0.0.1:5173','Content-Type':'application/json'})
    response=conn.getresponse();code=response.status;data=json.loads(response.read());conn.close();return code,data
   try:
    request={'repository':'demo','path':'App.java','findings':'App.java:1 review','model':'sonnet'}
    code,prepared=post('/api/copilot/developer/prepare',request);self.assertEqual(200,code)
    self.assertFalse(prepared['source_transmitted'])
    file.write_text('class Changed {}\n')
    code,_=post('/api/copilot/developer/execute',{**request,'approved_sha256':prepared['sha256']});self.assertEqual(400,code)
    code,_=post('/api/copilot/developer/prepare',{**request,'run_shell':True});self.assertEqual(400,code)
   finally:server.shutdown();server.server_close();thread.join(2)
