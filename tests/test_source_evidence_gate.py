"""Enforce evidence-gated recommendations for all engineering agent definitions.

Static instructions and adapter tests do not establish actual model compliance.
"""
import contextlib
import io
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from agents import catalog, install

GATE = "Source-evidence gate for all recommendations (mandatory)"
STATUS = ("STATICALLY VERIFIED", "RUNTIME REPRODUCED", "CONTRACT-DEPENDENT")


class SourceEvidenceGateTests(unittest.TestCase):
    def test_every_agent_requires_evidence_and_separates_hypotheses(self):
        agents = catalog()
        self.assertEqual(len(agents), 22)
        for meta, body in agents:
            with self.subTest(agent=meta["name"]):
                self.assertEqual(body.count(GATE), 1)
                for label in STATUS:
                    self.assertIn(label, body)
                text = body.lower()
                self.assertIn("actual", text)
                self.assertIn("file:line", text)
                self.assertIn("not run", text)
                self.assertIn("confirmed", text)
                self.assertTrue("inspect" in text or "read" in text)
                self.assertIn("fix completeness and regression gate", text)

    def test_adapters_retain_evidence_gate_for_each_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install(target, "all", "all"), 88)
            for meta, _ in catalog():
                name = meta["name"]
                for relative in (
                    Path(".codex/agents") / (name + ".toml"),
                    Path(".claude/agents") / (name + ".md"),
                    Path(".github/agents") / (name + ".agent.md"),
                    Path(".gemini/agents") / (name + ".md"),
                ):
                    with self.subTest(agent=name, host=str(relative)):
                        text = (target / relative).read_text(encoding="utf-8")
                        if relative.suffix == ".toml":
                            text = tomllib.loads(text)["developer_instructions"]
                        self.assertIn(GATE, text)
                        self.assertIn("CONTRACT-DEPENDENT", text)
                        self.assertIn("RUNTIME REPRODUCED", text)

    def test_java_reviewer_adjudicates_false_positives(self):
        body = next(body for meta, body in catalog("java")
                    if meta["name"] == "java-reviewer")
        for phrase in (
            "Adversarial finding adjudication",
            "Try to falsify the claim",
            "ACTIONABLE",
            "CONDITIONAL",
            "DISCARD",
            "negative controls",
        ):
            with self.subTest(rule=phrase):
                self.assertIn(phrase.lower(), body.lower())


if __name__ == "__main__":
    unittest.main()
