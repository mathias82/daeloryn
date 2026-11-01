import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from execution_request import parse_request

class ExecutionRequestTests(unittest.TestCase):
 def setUp(self):
  self.data={"repository":"org/repo","suite":"python","digest":"a"*64,"approval_token":"token"}
 def test_valid(self):
  self.assertEqual(self.data,parse_request(json.dumps(self.data).encode()))
 def test_reject_extra_fields(self):
  for key,value in (("checkout","/tmp/evil"),("command","rm -rf /"),("approved",True)):
   with self.subTest(key=key):
    with self.assertRaises(ValueError):
     parse_request(json.dumps({**self.data,key:value}).encode())
 def test_reject_duplicate_keys_and_unhashable_suite(self):
  duplicate=('{"repository":"org/repo","repository":"org/other","suite":"python","digest":"'+"a"*64+'","approval_token":"token"}').encode()
  with self.assertRaises(ValueError):parse_request(duplicate)
  for suite in ([],{},["python"],42,None):
   with self.subTest(suite=suite),self.assertRaises(ValueError):
    parse_request(json.dumps({**self.data,"suite":suite}).encode())
 def test_reject_oversized_and_invalid(self):
  for payload in (b"x"*4097,b"not json",b"[]",b"{}"):
   with self.subTest(payload=payload[:10]),self.assertRaises(ValueError):
    parse_request(payload)
if __name__=="__main__":unittest.main()
