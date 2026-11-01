import json
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
 def test_target_read_does_not_depend_on_whole_project_source_budget(self):
  from unittest.mock import patch
  with patch('project_review_context.MAX_TOTAL_BYTES',1):
   prepared=prepare(self.root,'demo','App.java','Review','sonnet')
  self.assertEqual(self.file.read_text(),prepared['source'])
 def test_specific_source_rejections_and_exact_size_boundary(self):
  with self.assertRaisesRegex(ValueError,'not found'):
   prepare(self.root,'demo','Missing.java','Review','sonnet')
  self.file.write_bytes(b'/'*12001)
  with self.assertRaisesRegex(ValueError,'exceeds 12000'):
   prepare(self.root,'demo','App.java','Review','sonnet')
  # An exact-boundary file previously failed because preparation added a newline.
  self.file.write_bytes(b'/'*12000)
  self.assertEqual(12000,len(prepare(self.root,'demo','App.java','Review','sonnet')['source'].encode()))
  self.file.write_bytes(b'class App {}\n// password placeholder\n')
  with self.assertRaisesRegex(ValueError,'redaction on lines 2'):
   prepare(self.root,'demo','App.java','Review','sonnet')
  self.file.write_bytes(b'\xff')
  with self.assertRaisesRegex(ValueError,'UTF-8'):
   prepare(self.root,'demo','App.java','Review','sonnet')
  self.file.write_bytes(b'abc\0def')
  with self.assertRaisesRegex(ValueError,'nonempty text'):
   prepare(self.root,'demo','App.java','Review','sonnet')
 def test_dependency_and_symbolic_link_paths_are_not_read(self):
  from unittest.mock import patch
  with patch('review_developer.read_source') as reader:
   with self.assertRaisesRegex(ValueError,'excluded'):
    prepare(self.root,'demo','node_modules/App.java','Review','sonnet')
   reader.assert_not_called()
  try:
   (self.repo/'alias').symlink_to(self.repo,target_is_directory=True)
  except (OSError,NotImplementedError):
   self.skipTest('symlinks unavailable')
  with self.assertRaisesRegex(ValueError,'symbolic links'):
   prepare(self.root,'demo','alias/App.java','Review','sonnet')
 def test_handoff_returns_diff_without_modification(self):
  original=self.file.read_text();p=prepare(self.root,'demo','App.java','App.java:1 initialize x to 1','sonnet')
  calls=[]
  def transport(request,**kwargs):
   calls.append(request);self.assertEqual('java-developer',request['agent'])
   return {'reply':json.dumps({'replacement':'class App { int x = 1; }\n'})}
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
   self.file.write_text('class Concurrent {}\n');return {'reply':json.dumps({'replacement':'class Proposed {}\n'})}
  with self.assertRaises(PermissionError):execute(p,p['sha256'],self.root,transport=transport)
 def test_crlf_handoff_hash_preview_and_apply_preserve_exact_bytes(self):
  from unittest.mock import patch
  from approved_patch_apply import apply
  original = b'class App { int x = 0; }\r\n'
  replacement = 'class App { int x = 1; }\r\n'
  self.file.write_bytes(original)
  prepared = prepare(self.root,'demo','App.java','Review','sonnet')
  self.assertEqual(original.decode(),prepared['source'])
  result = execute(prepared,prepared['sha256'],self.root,transport=lambda *a,**kw:{'reply':json.dumps({'replacement':replacement})})
  self.assertEqual(original,self.file.read_bytes())
  with patch('engineering_executor.command',return_value={'returncode':0,'output':''}):
   applied = apply(self.root,'demo','App.java',replacement,result['patch']['sha256'],'daeloryn/crlf-fix')
  self.assertTrue(applied['applied'])
  self.assertEqual(replacement.encode(),self.file.read_bytes())
  # Even a newline-only modification must invalidate the exact source approval.
  self.file.write_bytes(original.replace(b'\r\n',b'\n'))
  changed = prepare(self.root,'demo','App.java','Review','sonnet')
  with self.assertRaises(PermissionError):
   execute(changed,prepared['sha256'],self.root,transport=lambda *a,**kw:self.fail('provider invoked'))
 def test_unchanged_source_with_cli_statistics_produces_no_patch(self):
  p=prepare(self.root,'demo','App.java','List the classes','sonnet')
  reply=json.dumps({'replacement':p['source']})+'\nChanges +0 -0\nAI Credits 4.23 (4s)\nTokens 100\nResume copilot --resume=abc-123'
  result=execute(p,p['sha256'],self.root,transport=lambda *a,**kw:{'reply':reply})
  self.assertEqual('no_change',result['status'])
  self.assertNotIn('patch',result)

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


class DeveloperEnvelopeTests(unittest.TestCase):
 def test_cli_statistics_never_become_source(self):
  from review_developer import parse_replacement
  source='class App {}\n'
  trailer='\n\nChanges +0 -0\nAI Credits 4.23 (4s)\nTokens ↑ 17.9k • ↓ 292\nResume copilot --resume=abc-123'
  self.assertEqual(source,parse_replacement(json.dumps({'replacement':source})+trailer))
 def test_ambiguous_raw_source_or_extra_payload_fails_closed(self):
  from review_developer import parse_replacement
  for answer in ['class App {}\nAI Credits 4.23',json.dumps({'replacement':'class App {}'})+' malicious text',json.dumps({'replacement':'x','command':'run'}),'```json\n{}\n```']:
   with self.assertRaises(ValueError):parse_replacement(answer)
