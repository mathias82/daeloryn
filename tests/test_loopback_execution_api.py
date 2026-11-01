import http.client
import json
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from loopback_execution_api import serve_execution
from trusted_checkout_registry import TrustedCheckoutRegistry
from local_bearer_auth import LocalBearerAuthenticator
from execution_authorization import Principal
from durable_approval_gate import DurableApprovalGate

class ExecutionHttpTests(unittest.TestCase):
 def test_local_endpoint_denies_cross_origin_and_replay(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"repo"
   (root/".git").mkdir(parents=True)
   registry=TrustedCheckoutRegistry({"org/repo":root})
   gate=DurableApprovalGate(Path(d)/"approvals.sqlite")
   token=gate.prepare("run_tests","org/repo","a"*64)
   auth=LocalBearerAuthenticator({"s"*48:Principal("dev",frozenset({"org/repo"}),frozenset({"run_tests"}),True)})
   calls=[]
   server=serve_execution(auth,registry,gate,port=0,
                          test_runner=lambda *args,**kwargs:calls.append(1) or "ok")
   thread=threading.Thread(target=server.serve_forever,daemon=True)
   thread.start()
   try:
    port=server.server_port
    body=json.dumps({"repository":"org/repo","suite":"python","digest":"a"*64,"approval_token":token})
    def request(headers):
     conn=http.client.HTTPConnection("127.0.0.1",port,timeout=3)
     conn.request("POST","/api/execution/tests",body=body,headers={"Content-Type":"application/json",**headers})
     response=conn.getresponse()
     status=response.status
     response.read()
     conn.close()
     return status
    self.assertEqual(403,request({"Origin":"https://attacker.invalid"}))
    self.assertEqual([],calls)
    self.assertEqual(403,request({"Authorization":"Bearer "+"x"*48}))
    self.assertEqual(200,request({"Authorization":"Bearer "+"s"*48}))
    self.assertEqual(403,request({"Authorization":"Bearer "+"s"*48}))
    self.assertEqual([1],calls)
   finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
if __name__=="__main__":unittest.main()
