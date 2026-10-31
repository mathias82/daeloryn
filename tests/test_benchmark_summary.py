import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from summarize_benchmarks import summarize

class SummaryTests(unittest.TestCase):
    def test_missing_providers_are_not_faked(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"run.json"
            path.write_text(json.dumps({"schema_version":1,"kind":"recorded-external-output",
                "provider":"codex","model":"m","run_id":"r","metrics":{"precision":0.5,"recall":0.5,"f1":0.5},
                "evidence_line_valid_fraction":1.0}))
            result=summarize([path])
            self.assertEqual(result["status"],"partial")
            self.assertEqual(set(result["providers_missing"]),{"claude","gemini","copilot"})
            with self.assertRaises(ValueError):
                summarize([path,path])
if __name__=="__main__":
    unittest.main()
