import importlib.util
import tempfile
import unittest
from pathlib import Path
import sys
import os
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from execution_engine import start, complete, approve, advance, load
from approval_tokens import sign

WORKFLOW = ROOT / "workflows" / "spring-feature.json"

class ExecutionEngineTests(unittest.TestCase):
    def test_dry_run_does_not_create_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            result = start(WORKFLOW, state)
            self.assertEqual(result["mode"], "dry-run")
            self.assertFalse(state.exists())

    def test_real_gate_blocks_downstream_until_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            evidence = Path(tmp) / "evidence.txt"
            evidence.write_text("verified by operator", encoding="utf-8")
            start(WORKFLOW, state, execute=True)
            self.assertEqual(load(state)["steps"]["design"], "awaiting_agent")
            with self.assertRaises(ValueError):
                approve(state, "gate", "someone", "premature")
            complete(state, "design", evidence)
            complete(state, "implement", evidence)
            self.assertEqual(load(state)["steps"]["security"], "awaiting_agent")
            self.assertEqual(load(state)["steps"]["tests"], "awaiting_agent")
            complete(state, "security", evidence)
            complete(state, "tests", evidence)
            self.assertEqual(load(state)["steps"]["gate"], "awaiting_approval")
            self.assertEqual(load(state)["steps"]["finalize"], "pending")
            with self.assertRaises(ValueError):
                complete(state, "finalize", evidence)
            current = load(state)
            token = sign({"action":"approve","actor":"reviewer","step":"gate",
                "run_id":current["run_id"],"workflow_hash":current["workflow_hash"],
                "expires":int(time.time())+300,"nonce":"test-once"},b"x"*40)
            with self.assertRaises(ValueError):
                approve(state, "gate", "reviewer", "tests and security reviewed")
            with patch.dict(os.environ, {"EEA_APPROVAL_KEY":"x"*40}):
                approve(state, "gate", "reviewer", "tests and security reviewed",token)
            self.assertEqual(load(state)["steps"]["finalize"], "awaiting_agent")

    def test_wrong_run_or_expired_token_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            evidence = Path(tmp) / "evidence.txt"
            evidence.write_text("approved evidence")
            start(WORKFLOW, state, execute=True)
            for sid in ("design", "implement", "security", "tests"):
                complete(state, sid, evidence)
            current = load(state)
            payload = {"action":"approve","actor":"reviewer","step":"gate",
                "run_id":"different","workflow_hash":current["workflow_hash"],
                "expires":int(time.time())+300,"nonce":"wrong-run"}
            with patch.dict(os.environ, {"EEA_APPROVAL_KEY":"x"*40}):
                with self.assertRaises(ValueError):
                    approve(state, "gate", "reviewer", "reviewed", sign(payload,b"x"*40))
                payload["run_id"] = current["run_id"]
                payload["expires"] = int(time.time())-1
                with self.assertRaises(ValueError):
                    approve(state, "gate", "reviewer", "reviewed", sign(payload,b"x"*40))
            self.assertEqual(load(state)["steps"]["gate"], "awaiting_approval")

    def test_duplicate_run_and_duplicate_completion_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "run.json"
            evidence = Path(tmp) / "proof.txt"
            evidence.write_text("ok")
            start(WORKFLOW, state, execute=True)
            with self.assertRaises(FileExistsError):
                start(WORKFLOW, state, execute=True)
            complete(state, "design", evidence)
            with self.assertRaises(ValueError):
                complete(state, "design", evidence)

    def test_missing_evidence_and_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "run.json"
            start(WORKFLOW, state, execute=True)
            with self.assertRaises(ValueError):
                complete(state, "design", Path(tmp) / "missing.txt")
            data = load(state)
            data["workflow"]["name"] = "tampered"
            import json
            state.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                advance(state)

if __name__ == "__main__":
    unittest.main()
