"""Offline regression tests for benchmark provenance and strict evidence gates."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from record_benchmark import record
from summarize_benchmarks import summarize


class BenchmarkIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "Case.java").write_text("class Case { int value = 1; }\n", encoding="utf-8")
        self.reference = {"cases": [{"id": "java", "fixture": "Case.java", "expected": ["J1"]},
                                    {"id": "react", "fixture": "Case.java", "expected": ["R1"]}]}

    def submission(self, line=1):
        return {"cases": [
            {"case_id": "java", "findings": [
                {"id": "J1", "evidence": "value", "line": line, "quote": "int value = 1"}]},
            {"case_id": "react", "findings": []}]}

    def test_strict_valid_complete_run(self):
        result = record(self.submission(), self.reference, self.root, "copilot", "model", "r1", strict=True)
        self.assertTrue(result["metrics"]["complete"])
        self.assertTrue(result["strict_evidence_gate"])
        self.assertEqual(64, len(result["reference_sha256"]))

    def test_strict_rejects_invalid_evidence(self):
        with self.assertRaisesRegex(ValueError, "invalid source-line"):
            record(self.submission(line=99), self.reference, self.root, "copilot", "model", "r1", strict=True)

    def test_strict_rejects_missing_cases(self):
        submission = self.submission()
        submission["cases"].pop()
        with self.assertRaisesRegex(ValueError, "missing evaluated cases"):
            record(submission, self.reference, self.root, "copilot", "model", "r1", strict=True)

    def test_summary_rejects_different_reference_corpora(self):
        a = record(self.submission(), self.reference, self.root, "copilot", "m", "r1", strict=True)
        b = record(self.submission(), self.reference, self.root, "claude", "m", "r2", strict=True)
        b["reference_sha256"] = "0" * 64
        paths = [self.root / "a.json", self.root / "b.json"]
        for path, item in zip(paths, (a, b)):
            path.write_text(json.dumps(item), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "different or unknown"):
            summarize(paths)

    def test_summary_accepts_matching_reference_corpora(self):
        a = record(self.submission(), self.reference, self.root, "copilot", "m", "r1", strict=True)
        b = record(self.submission(), self.reference, self.root, "claude", "m", "r2", strict=True)
        paths = [self.root / "a.json", self.root / "b.json"]
        for path, item in zip(paths, (a, b)):
            path.write_text(json.dumps(item), encoding="utf-8")
        result = summarize(paths)
        self.assertTrue(result["reference_comparable"])
        self.assertEqual(a["reference_sha256"], result["reference_sha256"])


if __name__ == "__main__":
    unittest.main()
