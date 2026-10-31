"""Tests for deterministic source-evidence audit; no provider is invoked."""
import sys
import hashlib
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_review_evidence import audit


class ReviewEvidenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = self.root / "src/Inventory.java"
        source.parent.mkdir()
        source.write_text("class Inventory {\n int current = 1;\n int total = current + 1;\n}\n", encoding="utf-8")
        (self.root / "README.md").write_text(
            "# Contract\nAn inventory total must not overflow.\n", encoding="utf-8"
        )
        self.valid = {
            "schema_version": 1,
            "findings": [{
                "id": "F1",
                "disposition": "ACTIONABLE",
                "evidence_level": "STATICALLY VERIFIED",
                "source": {
                    "path": "src/Inventory.java", "line": 3,
                    "quote": "int total = current + 1;"
                },
                "root_cause": "unchecked integer addition",
                "invariant": "inventory total must not overflow",
                "invariant_basis": "DOCUMENTED_CONTRACT",
                "contract_evidence": {
                    "path": "README.md", "line": 2,
                    "quote": "An inventory total must not overflow."
                },
                "trigger": "total reaches signed int maximum",
                "impact": "stored total wraps",
                "fix": "use Math.addExact for addition",
                "regression": "assert overflow rejects before mutation"
            }]
        }

    def test_verified_paths_contracts_and_digests(self):
        result = audit(self.root, self.valid)
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(len(result["issues"]), 0)
        self.assertEqual(len(result["source_sha256"]), 2)
        self.assertIn("Does not prove semantic correctness", result["limitations"])

    def test_line_mismatch_fails_closed(self):
        self.valid["findings"][0]["source"]["line"] = 2
        result = audit(self.root, self.valid)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("QUOTE_NOT_ON_LINE", [x["code"] for x in result["issues"]])

    def test_missing_contract_evidence_is_rejected(self):
        self.valid["findings"][0].pop("contract_evidence")
        result = audit(self.root, self.valid)
        self.assertIn("MISSING_EVIDENCE", [x["code"] for x in result["issues"]])

    def test_unknown_runtime_claim_cannot_be_asserted(self):
        self.valid["findings"][0]["evidence_level"] = "RUNTIME REPRODUCED"
        result = audit(self.root, self.valid)
        self.assertIn("MISSING_RUNTIME_RECORD", [x["code"] for x in result["issues"]])

    def test_duplicate_root_causes_rejected(self):
        duplicate = dict(self.valid["findings"][0])
        duplicate["id"] = "F2"
        self.valid["findings"].append(duplicate)
        result = audit(self.root, self.valid)
        self.assertIn("DUPLICATE_ROOT_CAUSE", [x["code"] for x in result["issues"]])

    def test_contract_dependent_must_stay_outside_confirmed_findings(self):
        finding = self.valid["findings"][0]
        finding["disposition"] = "ACTIONABLE"
        finding["evidence_level"] = "CONTRACT-DEPENDENT"
        self.assertIn("UNSUPPORTED_ACTIONABLE", [
            x["code"] for x in audit(self.root, self.valid)["issues"]
        ])

    def test_hypothesis_must_explain_missing_evidence(self):
        self.valid["findings"] = [{
            "id": "C1", "disposition": "CONDITIONAL",
            "evidence_level": "CONTRACT-DEPENDENT"
        }]
        self.assertIn("MISSING_UNCERTAINTY", [
            x["code"] for x in audit(self.root, self.valid)["issues"]
        ])
        self.valid["findings"][0]["missing_evidence"] = "caller threading model"
        self.assertEqual(audit(self.root, self.valid)["result"], "PASS")

    def test_rejects_source_path_escape_and_symlink_escape(self):
        item = self.valid["findings"][0]["source"]
        item["path"] = "../outside.java"
        self.assertIn("UNSAFE_PATH", [
            x["code"] for x in audit(self.root, self.valid)["issues"]
        ])
        item["path"] = "src/Inventory.java"
        with tempfile.TemporaryDirectory() as outside:
            bad = Path(self.tmp.name) / "src/escape.java"
            target = Path(outside) / "secret.java"
            target.write_text("int secret = 1;\n")
            bad.symlink_to(target)
            item["path"] = "src/escape.java"
            item["line"] = 1
            item["quote"] = "int secret = 1;"
            self.assertIn("UNAVAILABLE_SOURCE", [
                x["code"] for x in audit(self.root, self.valid)["issues"]
            ])

    def pin_sources(self):
        self.valid["source_sha256"] = {
            path: hashlib.sha256((self.root / path).read_bytes()).hexdigest()
            for path in ("src/Inventory.java", "README.md")
        }

    def test_pinned_report_detects_change_outside_quoted_line(self):
        self.pin_sources()
        self.assertEqual(audit(self.root, self.valid, require_source_hashes=True)["result"], "PASS")
        source = self.root / "src/Inventory.java"
        source.write_text(source.read_text() + "// newer revision\n")
        result = audit(self.root, self.valid)
        self.assertIn("SOURCE_HASH_MISMATCH", [x["code"] for x in result["issues"]])
        self.assertNotIn("QUOTE_NOT_ON_LINE", [x["code"] for x in result["issues"]])

    def test_snapshot_requires_all_cited_files_including_contract(self):
        self.pin_sources()
        del self.valid["source_sha256"]["README.md"]
        self.assertIn("MISSING_SOURCE_HASH", [x["code"] for x in audit(self.root, self.valid)["issues"]])

    def test_snapshot_rejects_unreferenced_hashes(self):
        self.pin_sources()
        self.valid["source_sha256"]["unused.java"] = "0" * 64
        self.assertIn("UNUSED_SOURCE_HASH", [x["code"] for x in audit(self.root, self.valid)["issues"]])

    def test_snapshot_cannot_be_silently_omitted_in_strict_mode(self):
        with self.assertRaisesRegex(ValueError, "required in snapshot mode"):
            audit(self.root, self.valid, require_source_hashes=True)

    def test_malformed_hash_maps_are_rejected(self):
        for value in ([], "hash", {"src/Inventory.java": True}, {"src/Inventory.java": "xyz"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit(self.root, dict(self.valid, source_sha256=value))

    def test_malformed_enum_fields_fail_without_type_errors(self):
        for field in ("disposition", "evidence_level", "invariant_basis"):
            for value in ([], {}, True, None, 123):
                report = copy.deepcopy(self.valid)
                report["findings"][0][field] = value
                with self.subTest(field=field, value=value):
                    self.assertEqual(audit(self.root, report)["result"], "FAIL")

    def test_boolean_is_not_schema_version_or_exit_code(self):
        with self.assertRaises(ValueError):
            audit(self.root, dict(self.valid, schema_version=True))
        finding = self.valid["findings"][0]
        finding["evidence_level"] = "RUNTIME REPRODUCED"
        finding["runtime_evidence"] = {"command": "test", "observed_output": "ok", "exit_code": True}
        self.assertIn("MISSING_RUNTIME_RECORD", [x["code"] for x in audit(self.root, self.valid)["issues"]])
        finding["runtime_evidence"]["exit_code"] = 0
        self.assertEqual(audit(self.root, self.valid)["result"], "PASS")

    def test_invalid_filesystem_path_fails_without_exception(self):
        self.valid["findings"][0]["source"]["path"] = "src/invalid\0.java"
        self.assertEqual(audit(self.root, self.valid)["result"], "FAIL")

    def test_snapshot_cli_pass_failure_and_missing_manifest(self):
        self.pin_sources()
        report = self.root / "review.json"
        command = [sys.executable, str(ROOT / "scripts/audit_review_evidence.py"),
                   "--root", str(self.root), "--report", str(report), "--require-source-hashes"]
        for expected, mutate in ((0, False), (1, True)):
            if mutate:
                self.valid["source_sha256"]["README.md"] = "0" * 64
            report.write_text(json.dumps(self.valid))
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)
            self.assertEqual(json.loads(result.stdout)["result"], "FAIL" if mutate else "PASS")
        del self.valid["source_sha256"]
        report.write_text(json.dumps(self.valid))
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("required in snapshot mode", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_rejects_unstructured_reports(self):
        with self.assertRaises(ValueError):
            audit(self.root, {"findings": []})
        with self.assertRaises(ValueError):
            audit(self.root, {"schema_version": 1, "findings": "bad"})


if __name__ == "__main__":
    unittest.main()
