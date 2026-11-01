"""Opt-in loopback-only execution HTTP server, separate from read-only console."""
import json
import ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from execution_request import execute_request

MAX_BODY=4096

def make_execution_handler(authenticator,registry,approval_gate,*,receipt_path=None,
                           test_runner=None):
 class Handler(BaseHTTPRequestHandler):
  def respond(self,status,body):
   raw=json.dumps(body).encode("utf-8")
   self.send_response(status)
   self.send_header("Content-Type","application/json")
   self.send_header("Cache-Control","no-store")
   self.send_header("Content-Length",str(len(raw)))
   self.end_headers()
   self.wfile.write(raw)
  def do_POST(self):
   # Reject ambiguous framing and duplicate security-sensitive headers.
   if any(len(self.headers.get_all(name,[]))!=1 for name in ("Host","Content-Type","Content-Length")):
    return self.respond(400,{"error":"ambiguous headers"})
   if len(self.headers.get_all("Authorization",[]))!=1:
    return self.respond(403,{"error":"authorization required"})
   host=self.headers.get("Host","")
   expected=("127.0.0.1:"+str(self.server.server_port),"localhost:"+str(self.server.server_port))
   if host not in expected or self.headers.get("Origin") is not None:
    return self.respond(403,{"error":"forbidden"})
   if self.path!="/api/execution/tests" or self.headers.get("Content-Type")!="application/json":
    return self.respond(404,{"error":"not found"})
   if self.headers.get_all("Transfer-Encoding",[]):
    return self.respond(400,{"error":"unsupported transfer encoding"})
   lengths=self.headers.get_all("Content-Length",[])
   if len(lengths)!=1 or not lengths[0].isascii() or not lengths[0].isdecimal():
    return self.respond(400,{"error":"invalid length"})
   length=int(lengths[0])
   if length>MAX_BODY:
    return self.respond(413,{"error":"request too large"})
   if length==0:
    return self.respond(400,{"error":"empty request"})
   payload=self.rfile.read(length)
   if len(payload)!=length:
    return self.respond(400,{"error":"incomplete request"})
   try:
    result=execute_request(payload,self.headers.get("Authorization"),
                           authenticator,registry,approval_gate,
                           receipt_path=receipt_path,test_runner=test_runner)
   except (ValueError,UnicodeError):
    return self.respond(400,{"error":"invalid request"})
   except PermissionError:
    return self.respond(403,{"error":"not authorized"})
   except Exception:
    return self.respond(500,{"error":"execution failed; check receipts"})
   return self.respond(200,{"status":"completed","result":str(result)[:512]})
  def do_GET(self):
   self.respond(405,{"error":"method not allowed"})
  def do_PUT(self):
   self.respond(405,{"error":"method not allowed"})
  def do_DELETE(self):
   self.respond(405,{"error":"method not allowed"})
 return Handler

def serve_execution(authenticator,registry,approval_gate,*,port=8766,
                    receipt_path=None,test_runner=None):
 if not isinstance(port,int) or isinstance(port,bool) or not 0<=port<=65535:
  raise ValueError("invalid port")
 handler=make_execution_handler(authenticator,registry,approval_gate,
                                receipt_path=receipt_path,test_runner=test_runner)
 server=ThreadingHTTPServer(("127.0.0.1",port),handler)
 if not ipaddress.ip_address(server.server_address[0]).is_loopback:
  server.server_close()
  raise RuntimeError("loopback binding required")
 return server
