import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from compare_implementation_trials import compare

class PairedTests(unittest.TestCase):
    def test_outcomes(self):
        for baseline, daeloryn, expected in [
            ("failed", "passed", "daeloryn_passed_baseline_failed"),
            ("passed", "failed", "baseline_passed_daeloryn_failed"),
            ("passed", "passed", "tie_all_gates_passed"),
            ("failed", "failed", "neither_passed"),
        ]:
            statuses = {"original": "failed", "baseline": baseline, "daeloryn": daeloryn}
            def verifier(trial, arm, timeout, image):
                return {"arm": arm, "status": statuses[arm], "manifest_sha256": "same",
                        "suite_sha256": {"test": "same"},
                        "checks": {"test": {"status": statuses[arm]}}}
            result = compare("/trial", verifier=verifier)
            self.assertEqual(expected, result["outcome"])
            self.assertFalse(result["provider_invoked"])

    def test_mismatched_manifest(self):
        def verifier(trial, arm, timeout, image):
            return {"arm": arm, "status": "passed", "manifest_sha256": arm,
                    "suite_sha256": {"test": "same"}, "checks": {"test": {"status": "passed"}}}
        self.assertEqual("invalid_comparison", compare("/trial", verifier=verifier)["outcome"])

    def test_invalid_timeout(self):
        with self.assertRaises(ValueError):
            compare("/trial", timeout=0)

if __name__ == "__main__":
    unittest.main()
