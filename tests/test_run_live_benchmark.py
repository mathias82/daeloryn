import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_live_benchmark import run

def plan():
    return {"schema_version": 1, "provider": "copilot", "agent": "java-reviewer",
            "run_id": "trial-1", "arms": {
                "baseline": {"model": "sonnet", "argv": ["copilot", "--prompt=test"]},
                "daeloryn": {"model": "sonnet", "argv": ["copilot", "--prompt=test"]}}}

class OrchestratorTests(unittest.TestCase):
    def test_preview_does_not_call_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            for arm in ("baseline", "daeloryn"):
                (Path(tmp) / arm).mkdir()
            result = run(plan(), tmp, capturer=lambda *a: self.fail("provider invoked"))
            self.assertFalse(result["provider_invoked"])

    def test_execute_requires_pinned_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            for arm in ("baseline", "daeloryn"):
                (Path(tmp) / arm).mkdir()
            with self.assertRaises(ValueError):
                run(plan(), tmp, execute=True)

    def test_rejects_missing_arm(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "baseline").mkdir()
            with self.assertRaises(ValueError):
                run(plan(), tmp)

    def test_rejects_bad_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            for arm in ("baseline", "daeloryn"):
                (Path(tmp) / arm).mkdir()
            spec = plan()
            spec["provider"] = "unknown"
            with self.assertRaises(ValueError):
                run(spec, tmp)

if __name__ == "__main__":
    unittest.main()
