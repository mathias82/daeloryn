import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from secure_runtime import connect,create,advance,digest
from sandbox_runner import command,run

class SecureTests(unittest.TestCase):
    def test_gate_and_separate_connections(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"state.db"
            a=connect(p)
            b=connect(p)
            wf=json.loads((ROOT/"workflows/spring-feature.json").read_text())
            rid=create(a,wf)["run_id"]
            with self.assertRaises(ValueError):
                advance(b,rid,"finalize","complete",evidence=b"proof")
            for sid in ("design","implement","security","tests"):
                advance(a,rid,sid,"complete",evidence=b"proof")
            with self.assertRaises(ValueError):
                advance(b,rid,"finalize","complete",evidence=b"proof")
            claim={"iss":"https://issuer.example","sub":"reviewer","jti":"unique-1",
                "run_id":rid,"step":"gate","workflow_hash":digest(wf)}
            advance(b,rid,"gate","approve",claims=claim)
            with self.assertRaises(ValueError):
                advance(a,rid,"gate","approve",claims=claim)
            advance(a,rid,"finalize","complete",evidence=b"proof")
            a.close()
            b.close()

    def test_sandbox_opt_in_and_digest(self):
        with self.assertRaises(ValueError):
            command("ubuntu:latest")
        image="example.invalid/test@sha256:"+"a"*64
        with self.assertRaises(ValueError):
            run(image,"hello")
        self.assertIn("--network=none",command(image))
        self.assertIn("--read-only",command(image))
