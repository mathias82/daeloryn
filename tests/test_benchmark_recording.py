import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from record_benchmark import record,evidence_audit

BASE=ROOT/"evaluations/engineering"

class BenchmarkRecordingTests(unittest.TestCase):
    def setUp(self):
        self.reference=json.loads((BASE/"cases.json").read_text())

    def test_real_format_with_line_verified_evidence(self):
        fixture=(BASE/"fixtures/Java25Worker.java").read_text().splitlines()
        line=next(i for i,x in enumerate(fixture,1) if "newVirtualThreadPerTaskExecutor()" in x)
        quote="newVirtualThreadPerTaskExecutor()"
        submission={"cases":[{"case_id":"java25-interruption","findings":[
            {"id":"java.unbounded-virtual-threads","line":line,"quote":quote,
             "evidence":f"Java25Worker.java:{line}: {quote}"}]}]}
        result=record(submission,self.reference,BASE,"codex","test-model","test-run")
        self.assertEqual(result["kind"],"recorded-external-output")
        self.assertTrue(result["evidence"][0]["evidence_line_valid"])
        self.assertEqual(result["metrics"]["tp"],1)
        self.assertTrue(result["evidence"][0]["manual_adjudication_required"])

    def test_hallucinated_quote_and_line_are_rejected_as_evidence(self):
        submission={"cases":[{"case_id":"java25-interruption","findings":[
            {"id":"java.swallowed-interrupt","evidence":"claimed", "line":999,"quote":"does not exist"}]}]}
        result=record(submission,self.reference,BASE,"claude","test-model","test-run")
        self.assertFalse(result["evidence"][0]["evidence_line_valid"])
        self.assertEqual(result["evidence_line_valid_fraction"],0.0)

    def test_mismatch_provider_fails(self):
        with self.assertRaises(ValueError):
            record({"tool":"copilot","cases":[]},self.reference,BASE,"gemini","model","run")
        with self.assertRaises(ValueError):
            record({"cases":[]},self.reference,BASE,"fake-provider","model","run")

    def test_duplicate_case_rejected_by_scorer(self):
        submission={"cases":[{"case_id":"java25-interruption","findings":[]},
                             {"case_id":"java25-interruption","findings":[]}]}
        with self.assertRaises(ValueError):
            record(submission,self.reference,BASE,"codex","model","run")

if __name__=="__main__":
    unittest.main()
