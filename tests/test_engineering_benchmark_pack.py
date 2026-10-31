import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from engineering_benchmark_pack import build_pack, grade
from evaluate_engineering import reference

class EngineeringPackTests(unittest.TestCase):
    def test_real_fixture_prompts_blinded(self):
        pack = build_pack()
        self.assertEqual(4, len(pack["cases"]))
        self.assertEqual(4, len({c["id"] for c in pack["cases"]}))
        self.assertTrue(all(c["task_sha256"] for c in pack["cases"]))
        self.assertNotIn("expected", str(pack))

    def test_perfect_submission_scores_all_reference_findings(self):
        source = reference()
        submission = {"run_id": "test", "cases": [
            {"case_id": case["id"], "findings": [
                {"id": label, "evidence": "fixture location", "rationale": "impact"}
                for label in case["expected"]]}
            for case in source["cases"]]}
        result = grade(submission)
        self.assertEqual(1.0, result["f1"])
        self.assertEqual(4, result["submitted_case_count"])
        self.assertFalse(result["model_identity_verified"])

    def test_missing_case_rejected(self):
        with self.assertRaises(ValueError):
            grade({"cases": []})

    def test_false_positive_is_penalized(self):
        source = reference()
        submission = {"cases": [
            {"case_id": case["id"], "findings": [
                {"id": "invented.issue", "evidence": "fake", "rationale": "none"}]}
            for case in source["cases"]]}
        result = grade(submission)
        self.assertEqual(0, result["tp"])
        self.assertGreater(result["fp"], 0)

if __name__ == "__main__":
    unittest.main()
