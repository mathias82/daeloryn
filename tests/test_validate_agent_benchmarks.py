import json
import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_agent_benchmarks import validate_cases

class CaseCoverageTests(unittest.TestCase):
    def test_empty_cases_report_missing_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_cases(tmp, agents=["java-reviewer"])
            self.assertFalse(result["ready"])
            self.assertEqual(["java-reviewer"], result["missing_agents"])

    def test_valid_pinned_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "java-reviewer.json"
            path.write_text(json.dumps({"schema_version": 1, "agent": "java-reviewer",
                "cases": [{"id": "c1", "task": "Review the code",
                           "evaluator": {"suite_sha256": "a" * 64}}]}))
            result = validate_cases(tmp, agents=["java-reviewer"])
            self.assertTrue(result["ready"])
            self.assertEqual(1, result["cases"]["java-reviewer"]["case_count"])

    def test_duplicate_case_ids_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = {"id": "c1", "task": "Review", "evaluator": {"suite_sha256": "a" * 64}}
            (Path(tmp) / "java-reviewer.json").write_text(json.dumps({
                "schema_version": 1, "agent": "java-reviewer", "cases": [case, case]}))
            result = validate_cases(tmp, agents=["java-reviewer"])
            self.assertFalse(result["ready"])
            self.assertTrue(result["errors"])

    def test_invalid_evaluator_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "java-reviewer.json").write_text(json.dumps({
                "schema_version": 1, "agent": "java-reviewer",
                "cases": [{"id": "c1", "task": "Review", "evaluator": {"suite_sha256": "bad"}}]}))
            self.assertFalse(validate_cases(tmp, agents=["java-reviewer"])["ready"])

if __name__ == "__main__":
    unittest.main()
