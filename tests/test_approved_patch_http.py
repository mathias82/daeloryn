"""Local code writes/tests are opt-in, origin-bound and require exact approvals."""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from console_api import make_handler


class CodeWriteHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.checkout=self.root/"demo"
        (self.checkout/".git").mkdir(parents=True)
        self.file=self.checkout/"App.java"
        self.file.write_text("class App {}\n")
        self.servers=[]
        self.addCleanup(self.shutdown_servers)
    def shutdown_servers(self):
        for server,thread in self.servers:
            server.shutdown()
            thread.join(3)
            server.server_close()
    def start(self,enabled):
        server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(
            enable_copilot=True,repository_roots=[self.root],enable_code_writes=enabled))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.servers.append((server,thread))
        return server.server_port
    def request(self,port,path,body,origin=True):
        connection=http.client.HTTPConnection("127.0.0.1",port,timeout=5)
        headers={"Host":"127.0.0.1:"+str(port),"Content-Type":"application/json"}
        if origin:headers["Origin"]="http://127.0.0.1:5173"
        connection.request("POST",path,body=json.dumps(body),headers=headers)
        response=connection.getresponse()
        status=response.status
        payload=json.loads(response.read())
        connection.close()
        return status,payload
    def test_writes_disabled_by_default_even_with_copilot_enabled(self):
        port=self.start(False)
        code,payload=self.request(port,"/api/copilot/review/patch/apply",{})
        self.assertEqual(405,code)
        self.assertIn("--enable-code-writes",payload["error"])
        code,_=self.request(port,"/api/copilot/review/tests",{})
        self.assertEqual(405,code)
        self.assertEqual("class App {}\n",self.file.read_text())
    def test_cross_origin_and_missing_diff_approval_block_writes(self):
        port=self.start(True)
        payload={
            "repository":"demo","task":"Fix App.java","model":"claude-sonnet-4",
            "agent":None,"scope":"focused","approved_sha256":"a"*64,
            "file":"App.java","start":1,"end":1,
            "original":"class App {}","replacement":"class App { }",
            "source_sha256":"b"*64,"branch":"daeloryn/test-fix",
            "approved":False
        }
        status,_=self.request(port,"/api/copilot/review/patch/apply",payload,origin=False)
        self.assertEqual(403,status)
        status,_=self.request(port,"/api/copilot/review/patch/apply",payload)
        self.assertEqual(409,status)
        status,_=self.request(port,"/api/copilot/review/tests",{
            "repository":"demo","branch":"daeloryn/test-fix",
            "suite":"maven","approved":False})
        self.assertEqual(409,status)
        self.assertEqual("class App {}\n",self.file.read_text())


if __name__=="__main__":
    unittest.main()
