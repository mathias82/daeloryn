import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from console_api import agent_data, benchmark_data, make_handler

class ConsoleApiTests(unittest.TestCase):
    def test_catalog_uses_repository(self):
        agents = agent_data()
        self.assertTrue(agents)
        self.assertTrue(all(set(a) == {"name", "description", "scope"} for a in agents))
        self.assertEqual(len(agents), len({a["name"] for a in agents}))

    def test_empty_benchmark_report_has_no_verified_trials(self):
        report = benchmark_data()
        self.assertEqual(0, report["verified_trial_count"])
        self.assertEqual(0, report["observed_cells"])

    def test_bad_record_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "bad.json").write_text('{"kind":"fake"}')
            with self.assertRaises(ValueError):
                benchmark_data(tmp)

    def test_trial_summary_excludes_private_fields_and_preserves_unverified_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = {"schema_version": 1, "kind": "benchmark-trial", "agent": "java-reviewer",
                      "provider": "copilot", "arm": "daeloryn", "run_id": "run-1",
                      "outcome": "tie_all_gates_passed", "comparable": True,
                      "independent_checks_executed": True,
                      "requested_models": {"baseline": "sonnet", "daeloryn": "sonnet"},
                      "transcript": "PRIVATE", "argv": ["PRIVATE"], "token": "PRIVATE"}
            (Path(tmp)/"trial.json").write_text(json.dumps(record))
            report = benchmark_data(tmp)
            self.assertEqual(0, report["verified_trial_count"])
            self.assertNotIn("PRIVATE", json.dumps(report))
            row = report["trials"][0]
            self.assertEqual("sonnet", row["baseline_model"])
            self.assertEqual("tie_all_gates_passed", row["outcome"])
            self.assertFalse(row["model_identity_verified"])
            self.assertFalse(row["agent_selection_verified"])
            self.assertTrue(row["independent_checks_executed"])
            record["requested_models"] = {"baseline": {"unexpected": "object"}}
            (Path(tmp)/"trial.json").write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                benchmark_data(tmp)

    def test_legacy_record_without_models_has_explicit_unknown_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = {"schema_version":1,"kind":"benchmark-trial","agent":"java-reviewer",
                      "provider":"copilot","arm":"baseline","run_id":"legacy",
                      "outcome":"neither_passed"}
            (Path(tmp)/"trial.json").write_text(json.dumps(record))
            row=benchmark_data(tmp)["trials"][0]
            self.assertEqual("Not recorded",row["baseline_model"])
            self.assertFalse(row["comparable"])
            self.assertFalse(row["independent_checks_executed"])

    def test_no_write_handler(self):
        handler = make_handler()
        self.assertTrue(hasattr(handler, "do_POST"))
        self.assertTrue(hasattr(handler, "do_PUT"))
        self.assertTrue(hasattr(handler, "do_DELETE"))
        self.assertFalse(hasattr(handler, "do_PATCH"))

if __name__ == "__main__":
    unittest.main()
