"""Regression checks for completeness-aware cross-stack scoring."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from score_agents import score


class CoverageScoringTests(unittest.TestCase):
    def setUp(self):
        self.reference = {"cases": [
            {"id": "java", "expected": ["J1"]},
            {"id": "spring", "expected": ["S1"]},
            {"id": "react", "expected": ["R1"]},
        ]}

    def test_partial_submission_is_explicitly_marked_incomplete(self):
        result = score({"cases": [{"case_id": "java", "findings": [
            {"id": "J1", "evidence": "line 5"}]}]}, self.reference)
        self.assertFalse(result["complete"])
        self.assertEqual(["react", "spring"], result["missing_cases"])
        self.assertEqual(1, result["submitted_case_count"])
        self.assertEqual(3, result["expected_case_count"])
        self.assertEqual(2, result["fn"])

    def test_strict_mode_rejects_missing_cases(self):
        with self.assertRaisesRegex(ValueError, "missing evaluated cases"):
            score({"cases": []}, self.reference, require_complete=True)

    def test_strict_mode_accepts_explicit_empty_findings(self):
        submission = {"cases": [
            {"case_id": "java", "findings": [{"id": "J1", "evidence": "line 5"}]},
            {"case_id": "spring", "findings": []},
            {"case_id": "react", "findings": []},
        ]}
        result = score(submission, self.reference, require_complete=True)
        self.assertTrue(result["complete"])
        self.assertEqual([], result["missing_cases"])
        self.assertEqual(2, result["fn"])

    def test_duplicate_case_rejected_even_in_permissive_mode(self):
        with self.assertRaisesRegex(ValueError, "duplicate case_id"):
            score({"cases": [{"case_id": "java"}, {"case_id": "java"}]}, self.reference)


if __name__ == "__main__":
    unittest.main()
