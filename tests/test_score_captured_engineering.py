import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from score_captured_engineering import evaluate, parse_answer
from evaluate_engineering import reference

def captures():
    result = {}
    for c in reference()["cases"]:
        result[c["id"]] = {"schema_version": 1, "kind": "local-provider-cli-capture",
            "provider": "copilot", "requested_model": "test-model", "status": "completed",
            "output_truncated": False, "output": '{"case_id":"' + c["id"] + '","findings":[]}'}
    return result

class CapturedEngineeringTests(unittest.TestCase):
    def test_valid_complete_capture(self):
        result = evaluate(captures(), "copilot", "test-model")
        self.assertEqual(4, result["submitted_case_count"])
        self.assertFalse(result["model_identity_verified"])

    def test_missing_case_fails(self):
        reports = captures()
        reports.pop(next(iter(reports)))
        with self.assertRaises(ValueError):
            evaluate(reports, "copilot", "test-model")

    def test_truncated_capture_fails(self):
        reports = captures()
        next(iter(reports.values()))["output_truncated"] = True
        with self.assertRaises(ValueError):
            evaluate(reports, "copilot", "test-model")

    def test_wrong_case_fails(self):
        reports = captures()
        next(iter(reports.values()))["output"] = '{"case_id":"wrong","findings":[]}'
        with self.assertRaises(ValueError):
            evaluate(reports, "copilot", "test-model")

    def test_markdown_fence_supported(self):
        self.assertEqual("x", parse_answer('```json\n{"case_id":"x","findings":[]}\n```')["case_id"])

if __name__ == "__main__":
    unittest.main()
