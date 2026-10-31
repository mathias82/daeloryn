import json
import sys
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from execution_service import describe, complete_from_file, approve_verified, preview
from secure_runtime import connect, create, advance, digest
from agent_adapter import Invocation, prepare, execute

class ServiceTests(unittest.TestCase):
    def test_plan_is_read_only(self):
        wf=json.loads((ROOT/"workflows/spring-feature.json").read_text())
        self.assertFalse(preview(wf)["will_invoke_agent"])

    def test_transactional_lifecycle_and_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            db=connect(Path(temp)/"runs.sqlite")
            wf=json.loads((ROOT/"workflows/spring-feature.json").read_text())
            run=create(db,wf)["run_id"]
            proof=Path(temp)/"proof.txt"
            proof.write_text("Reviewed test evidence")
            with self.assertRaises(ValueError):
                complete_from_file(db,run,"finalize",proof)
            for step in ("design","implement","security","tests"):
                complete_from_file(db,run,step,proof)
            self.assertEqual(next(s for s in describe(db,run)["steps"] if s["id"]=="gate")["status"],"awaiting_approval")
            with self.assertRaises(ValueError):
                complete_from_file(db,run,"finalize",proof)
            with self.assertRaises(ValueError):
                approve_verified(db,run,"gate","bad",{},"https://issuer.invalid","aud",[])
            db.close()

    def test_oidc_trust_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            db=connect(Path(temp)/"runs.sqlite")
            wf=json.loads((ROOT/"workflows/spring-feature.json").read_text())
            run=create(db,wf)["run_id"]
            with patch("execution_service.verify_oidc",return_value={"run_id":"other","step":"gate"}):
                with self.assertRaises(ValueError):
                    approve_verified(db,run,"gate","token",{},"https://issuer.invalid","aud",["reviewer"])
            db.close()

    def test_adapters_never_execute(self):
        request=Invocation("codex","java-reviewer","run","review","Check behavior")
        self.assertFalse(prepare(request)["provider_invoked"])
        with self.assertRaises(RuntimeError):
            execute(request)
        with self.assertRaises(ValueError):
            prepare(Invocation("unknown","a","r","s","hello"))

    def test_concurrent_completion_exactly_once(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"state.db"
            db=connect(file)
            wf=json.loads((ROOT/"workflows/spring-feature.json").read_text())
            run=create(db,wf)["run_id"]
            db.close()
            def worker(_):
                con=connect(file)
                try:
                    advance(con,run,"design","complete",evidence=b"proof")
                    return True
                except ValueError:
                    return False
                finally:
                    con.close()
            with ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(worker,range(4)))
            self.assertEqual(results.count(True),1)
            con=connect(file)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM events WHERE run_id=? AND step='design' AND action='complete'",(run,)).fetchone()[0],1)
            con.close()

    def test_approval_only_after_oidc_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            db=connect(Path(temp)/"state.db")
            wf=json.loads((ROOT/"workflows/spring-feature.json").read_text())
            run=create(db,wf)["run_id"]
            for step in ("design","implement","security","tests"):
                advance(db,run,step,"complete",evidence=b"evidence")
            claims={"run_id":run,"step":"gate","workflow_hash":digest(wf),
                    "iss":"https://issuer.example","sub":"reviewer","jti":"unique-one"}
            with patch("execution_service.verify_oidc",return_value=claims) as verifier:
                approve_verified(db,run,"gate","token",{"keys":[]},"https://issuer.example","workflow",["reviewer"])
                verifier.assert_called_once()
            self.assertEqual(next(s for s in describe(db,run)["steps"] if s["id"]=="finalize")["status"],"awaiting_agent")
            with patch("execution_service.verify_oidc",return_value=claims):
                with self.assertRaises(ValueError):
                    approve_verified(db,run,"gate","token",{}, "https://issuer.example","workflow",["reviewer"])
            db.close()
