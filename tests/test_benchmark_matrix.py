import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from benchmark_matrix import matrix

def record(agent="java-reviewer", provider="copilot", arm="baseline", run="r1"):
    return {"schema_version": 1, "kind": "benchmark-trial",
            "agent": agent, "provider": provider, "arm": arm,
            "run_id": run, "outcome": "tie_all_gates_passed"}

class MatrixTests(unittest.TestCase):
    def test_empty_matrix_has_no_claimed_results(self):
        result = matrix([], agents=["java-reviewer"])
        self.assertEqual(8, result["expected_cells"])
        self.assertEqual(0, result["observed_cells"])
        self.assertEqual(0, result["verified_trial_count"])
        self.assertEqual(8, len(result["missing_cells"]))

    def test_partial_unverified_results(self):
        result = matrix([record()], agents=["java-reviewer"])
        self.assertEqual(1, result["observed_cells"])
        self.assertEqual(0, result["verified_trial_count"])

    def test_explicitly_attested_results(self):
        item = record()
        item.update(model_identity_verified=True, agent_selection_verified=True,
                    independent_checks_executed=True, comparable=True)
        result = matrix([item], agents=["java-reviewer"])
        self.assertEqual(1, result["verified_trial_count"])
        self.assertEqual(1, result["verified_outcomes"]["tie_all_gates_passed"])

    def test_duplicate_record_rejected(self):
        with self.assertRaises(ValueError):
            matrix([record(), record()], agents=["java-reviewer"])

    def test_unknown_agent_rejected(self):
        with self.assertRaises(ValueError):
            matrix([record(agent="unknown")], agents=["java-reviewer"])

    def test_invalid_outcome_rejected(self):
        item = record()
        item["outcome"] = "superior"
        with self.assertRaises(ValueError):
            matrix([item], agents=["java-reviewer"])

if __name__ == "__main__":
    unittest.main()
