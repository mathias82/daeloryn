import json
import sys
import time
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from secure_runtime import verify_oidc

class OIDCTests(unittest.TestCase):
    def setUp(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import base64
        self.jwt=jwt
        self.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        pub=self.key.public_key().public_numbers()
        def enc(n):
            raw=n.to_bytes((n.bit_length()+7)//8,"big")
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")
        self.jwks={"keys":[{"kty":"RSA","kid":"test","use":"sig","n":enc(pub.n),"e":enc(pub.e)}]}
        self.claims={"iss":"https://issuer.test","aud":"engineering-approvals",
            "sub":"reviewer1","jti":"once","iat":int(time.time()),
            "exp":int(time.time())+300,"run_id":"run","step":"gate","workflow_hash":"digest"}

    def token(self):
        return self.jwt.encode(self.claims,self.key,algorithm="RS256",headers={"kid":"test"})

    def test_valid_signature_and_authorized_subject(self):
        result=verify_oidc(self.token(),self.jwks,"https://issuer.test",
                           "engineering-approvals",{"reviewer1"})
        self.assertEqual(result["sub"],"reviewer1")

    def test_wrong_audience_or_subject_rejected(self):
        with self.assertRaises(Exception):
            verify_oidc(self.token(),self.jwks,"https://issuer.test","wrong",{"reviewer1"})
        with self.assertRaises(Exception):
            verify_oidc(self.token(),self.jwks,"https://issuer.test",
                        "engineering-approvals",{"unauthorized"})

    def test_expired_and_bad_signature_rejected(self):
        self.claims["exp"]=int(time.time())-100
        with self.assertRaises(Exception):
            verify_oidc(self.token(),self.jwks,"https://issuer.test","engineering-approvals")
        self.claims["exp"]=int(time.time())+300
        other=self.key
        from cryptography.hazmat.primitives.asymmetric import rsa
        self.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        with self.assertRaises(Exception):
            verify_oidc(self.token(),self.jwks,"https://issuer.test","engineering-approvals")
