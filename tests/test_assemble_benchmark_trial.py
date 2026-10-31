import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from assemble_benchmark_trial import assemble

def comparison():
    return {"schema_version": 1, "kind": "paired-implementation-evaluation",
            "outcome": "daeloryn_passed_baseline_failed", "comparable": True,
            "independent_checks_executed": True,
            "arms": {"original": {"status": "failed"}, "baseline": {"status": "failed"},
                     "daeloryn": {"status": "passed"}}}

def capture(provider="copilot", status="completed"):
    return {"schema_version": 1, "kind": "local-provider-cli-capture",
            "provider": provider, "status": status, "requested_model": "model",
            "actual_model": "unverified"}

class AssemblerTests(unittest.TestCase):
    def test_valid_record_never_claims_model_verification(self):
        result = assemble("java-reviewer", "copilot", "run-1", comparison(),
                          {"baseline": capture(), "daeloryn": capture()})
        self.assertFalse(result["model_identity_verified"])
        self.assertFalse(result["agent_selection_verified"])
        self.assertEqual("daeloryn_passed_baseline_failed", result["outcome"])

    def test_rejects_incomplete_provider_run(self):
        with self.assertRaises(ValueError):
            assemble("java-reviewer", "copilot", "run-1", comparison(),
                     {"baseline": capture(status="failed"), "daeloryn": capture()})

    def test_rejects_provider_mismatch(self):
        with self.assertRaises(ValueError):
            assemble("java-reviewer", "copilot", "run-1", comparison(),
                     {"baseline": capture("gemini"), "daeloryn": capture()})

    def test_rejects_missing_arm(self):
        with self.assertRaises(ValueError):
            assemble("java-reviewer", "copilot", "run-1", comparison(),
                     {"baseline": capture()})

    def test_rejects_incomplete_evaluator(self):
        result = comparison()
        result["arms"]["baseline"]["status"] = "error"
        with self.assertRaises(ValueError):
            assemble("java-reviewer", "copilot", "run-1", result,
                     {"baseline": capture(), "daeloryn": capture()})

if __name__ == "__main__":
    unittest.main()
