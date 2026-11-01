import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from local_bearer_auth import LocalBearerAuthenticator
from execution_authorization import Principal

class LocalAuthTests(unittest.TestCase):
 def setUp(self):
  self.principal=Principal("dev",frozenset({"repo"}),frozenset({"run_tests"}),True)
  self.token="a"*48
  self.auth=LocalBearerAuthenticator({self.token:self.principal})
 def test_known_bearer(self):
  self.assertEqual(self.principal,self.auth.authenticate("Bearer "+self.token))
 def test_unknown_and_malformed_rejected(self):
  for value in (None,"","Basic "+self.token,"Bearer "+"b"*48,"Bearer "+self.token+" extra","Bearer short"):
   with self.subTest(value=value),self.assertRaises(PermissionError):
    self.auth.authenticate(value)
 def test_no_unauthenticated_grants(self):
  with self.assertRaises(ValueError):
   LocalBearerAuthenticator({self.token:Principal("dev",frozenset({"repo"}),frozenset({"run_tests"}))})
if __name__=="__main__":unittest.main()
