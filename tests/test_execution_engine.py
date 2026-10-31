import importlib.util
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from execution_engine import start, complete, approve, advance, load

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
            approve(state, "gate", "reviewer", "tests and security reviewed")
            self.assertEqual(load(state)["steps"]["finalize"], "awaiting_agent")

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
