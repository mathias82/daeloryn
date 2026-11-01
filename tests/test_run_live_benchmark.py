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
    def test_model_mismatch_stops_before_provider_or_evaluator(self):
        with tempfile.TemporaryDirectory() as tmp:
            for arm in ("baseline", "daeloryn"):
                (Path(tmp) / arm).mkdir()
            for model in ("different-model", "", " "):
                for execute in (False, True):
                    with self.subTest(model=model, execute=execute):
                        spec = plan()
                        spec["arms"]["daeloryn"]["model"] = model
                        with self.assertRaises(ValueError):
                            run(spec, tmp, execute=execute,
                                capturer=lambda *a: self.fail("provider invoked"),
                                comparator=lambda *a, **kw: self.fail("evaluator invoked"))

    def test_bad_second_arm_never_starts_first_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            for arm in ("baseline", "daeloryn"):
                (Path(tmp) / arm).mkdir()
            for argv in ([], ["wrong-provider"], ["copilot", 1], ["copilot", ""], ["copilot", "bad\x00arg"]):
                for execute in (False, True):
                    with self.subTest(argv=argv, execute=execute):
                        spec = plan()
                        spec["arms"]["daeloryn"]["argv"] = argv
                        with self.assertRaises(ValueError):
                            run(spec, tmp, execute=execute,
                                sandbox_image="fixture@sha256:" + "a" * 64,
                                capturer=lambda *a: self.fail("provider invoked"),
                                comparator=lambda *a, **kw: self.fail("evaluator invoked"))

    def test_model_syntax_validated_before_discovery_or_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            for arm in ("baseline", "daeloryn"):
                (Path(tmp) / arm).mkdir()
            spec = plan()
            for arm in spec["arms"].values():
                arm["model"] = "invalid model"
            with self.assertRaises(ValueError):
                run(spec, tmp, execute=True, capturer=lambda *a: self.fail("provider invoked"))

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
