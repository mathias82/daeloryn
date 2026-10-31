"""Regression guards for the Java review evidence contract and host adapters.

These checks validate *instructions and packaging*, not LLM compliance or accuracy.
"""
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from agents import catalog, install


class JavaReviewerQualityTests(unittest.TestCase):
    def test_canonical_reviewer_contains_accuracy_contract(self):
        reviewers = [(meta, body) for meta, body in catalog("java")
                     if meta["name"] == "java-reviewer"]
        self.assertEqual(len(reviewers), 1)
        _, body = reviewers[0]
        required = (
            "Target isolation and real source lines",
            "line count",
            "STATICALLY VERIFIED",
            "RUNTIME REPRODUCED",
            "One finding per independent root cause",
            "Contract-sensitive claims and severity",
            "Java semantics and fix integrity",
            "ConcurrentHashMap",
            "Math.addExact",
            "ExecutorService.close()",
            "Java 24+",
            "Verification actually performed",
            "Not verified",
        )
        for phrase in required:
            with self.subTest(contract=phrase):
                self.assertIn(phrase, body)

    def test_java_reviewer_contract_survives_each_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self.assertEqual(install(target, "java", "all"), 16)
            names = (
                ".codex/agents/java-reviewer.toml",
                ".claude/agents/java-reviewer.md",
                ".github/agents/java-reviewer.agent.md",
                ".gemini/agents/java-reviewer.md",
            )
            for name in names:
                with self.subTest(adapter=name):
                    text = (target / name).read_text(encoding="utf-8")
                    if name.endswith(".toml"):
                        text = tomllib.loads(text)["developer_instructions"]
                    self.assertIn("Target isolation and real source lines", text)
                    self.assertIn("RUNTIME REPRODUCED", text)
                    self.assertIn("One finding per independent root cause", text)
                    self.assertIn("Contract-sensitive claims and severity", text)
                    self.assertIn("Verification actually performed", text)

    def test_java_ledger_fixture_does_not_include_gold_answers(self):
        source = (ROOT / "evaluations/engineering/fixtures/Java25Ledger.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("class Java25Ledger", source)
        self.assertNotIn("ground truth", source.lower())
        self.assertNotIn("deliberately unsafe", source.lower())


if __name__ == "__main__":
    unittest.main()
