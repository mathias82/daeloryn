"""Offline tests for blinded, repeatable Java review workspaces."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_blind_java_review import prepare


class BlindJavaReviewTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT / "evaluations/engineering/fixtures/Java25Ledger.java"

    def test_creates_clean_baseline_and_single_specialist_agent(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "trial-001"
            result = prepare(self.source, target)
            original = self.source.read_bytes()
            self.assertEqual((target / "baseline" / self.source.name).read_bytes(), original)
            self.assertEqual((target / "daeloryn" / self.source.name).read_bytes(), original)
            self.assertEqual(list((target / "baseline").iterdir()),
                             [target / "baseline" / self.source.name])
            agents = list((target / "daeloryn" / ".github" / "agents").iterdir())
            self.assertEqual([p.name for p in agents], ["java-reviewer.agent.md"])
            self.assertIn("One finding per independent root cause",
                          agents[0].read_text(encoding="utf-8"))
            self.assertEqual(
                result["fixture_sha256"], hashlib.sha256(original).hexdigest()
            )
            self.assertEqual(
                json.loads((target / "manifest.json").read_text(encoding="utf-8")),
                result,
            )
            self.assertEqual(result["status"], "prepared_only_no_model_runs")
            self.assertFalse((target / "baseline" / "AGENTS.md").exists())
            self.assertFalse((target / "daeloryn" / "Java25Ledger-ground-truth.md").exists())

    def test_refuses_existing_trial_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "trial"
            target.mkdir()
            sentinel = target / "keep.txt"
            sentinel.write_text("unchanged", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare(self.source, target)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")

    def test_rejects_non_java_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "not-java.txt"
            source.write_text("contents", encoding="utf-8")
            with self.assertRaises(ValueError):
                prepare(source, Path(temp) / "trial")


if __name__ == "__main__":
    unittest.main()
