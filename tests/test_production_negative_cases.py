import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from execution_authorization import Principal
from execution_authorization import authorize_and_consume

class NegativeSecurityCases(unittest.TestCase):
 def test_unauthenticated_preflight_never_consumes_token(self):
  class Gate:
   def consume(self,*args):
    raise AssertionError("must not consume")
  p=Principal("anonymous",frozenset({"repo"}),frozenset({"run_tests"}))
  with self.assertRaises(PermissionError):
   authorize_and_consume(p,"repo","run_tests","a"*64,"token",Gate())
 def test_cross_repository_preflight_never_consumes_token(self):
  class Gate:
   def consume(self,*args):
    raise AssertionError("must not consume")
  p=Principal("dev",frozenset({"repo-a"}),frozenset({"run_tests"}),True)
  with self.assertRaises(PermissionError):
   preflight(p,"repo-b","run_tests","a"*64,"token",Gate())
if __name__=="__main__":unittest.main()
