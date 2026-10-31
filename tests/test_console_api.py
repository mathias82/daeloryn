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

    def test_no_write_handler(self):
        handler = make_handler()
        self.assertTrue(hasattr(handler, "do_POST"))
        self.assertTrue(hasattr(handler, "do_PUT"))
        self.assertTrue(hasattr(handler, "do_DELETE"))
        self.assertFalse(hasattr(handler, "do_PATCH"))

if __name__ == "__main__":
    unittest.main()
