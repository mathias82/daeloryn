"""Regression checks: 22 specialized agents retain truthful evidence standards.

These are offline text and adapter integrity tests. They do not measure AI quality.
"""
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from agents import catalog, install

SCOPES = {"java": 4, "spring": 6, "react": 4, "platform": 6, "shared": 2}
CONTRACT = "Review evidence and accuracy protocol (mandatory)"
SPECIALIST = {
    "java": "Java specialist checks",
    "spring": "Spring specialist checks",
    "react": "React specialist checks",
    "platform": "Platform specialist checks",
    "shared": "Shared specialist checks",
}


class AllAgentQualityTests(unittest.TestCase):
    def test_all_22_agent_definitions_retain_review_standards(self):
        definitions = catalog()
        self.assertEqual(len(definitions), 22)
        for scope, expected_count in SCOPES.items():
            self.assertEqual(len(catalog(scope)), expected_count)
        for meta, body in definitions:
            with self.subTest(agent=meta["name"]):
                if meta["name"] == "java-reviewer":
                    self.assertIn("Review accuracy protocol (mandatory)", body)
                    self.assertIn("One finding per independent root cause", body)
                else:
                    self.assertIn(CONTRACT, body)
                    self.assertIn(SPECIALIST[meta["scope"]], body)
                    self.assertIn("One independent root cause per finding", body)
                for term in ("STATICALLY VERIFIED", "RUNTIME REPRODUCED",
                             "LIKELY", "CONTRACT-DEPENDENT",
                             "Verification actually performed"):
                    self.assertIn(term, body)

    def test_quality_rules_survive_all_88_generated_host_adapters(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.assertEqual(install(target, "all", "all"), 88)
            self.assertEqual(len(list((target / ".codex" / "agents").glob("*.toml"))), 22)
            self.assertEqual(len(list((target / ".claude" / "agents").glob("*.md"))), 22)
            self.assertEqual(len(list((target / ".github" / "agents").glob("*.agent.md"))), 22)
            self.assertEqual(len(list((target / ".gemini" / "agents").glob("*.md"))), 22)
            for meta, _ in catalog():
                name = meta["name"]
                files = (
                    target / ".codex" / "agents" / (name + ".toml"),
                    target / ".claude" / "agents" / (name + ".md"),
                    target / ".github" / "agents" / (name + ".agent.md"),
                    target / ".gemini" / "agents" / (name + ".md"),
                )
                for file in files:
                    with self.subTest(agent=name, file=file.suffix):
                        rendered = file.read_text(encoding="utf-8")
                        if file.suffix == ".toml":
                            rendered = tomllib.loads(rendered)["developer_instructions"]
                        self.assertIn("STATICALLY VERIFIED", rendered)
                        self.assertIn("RUNTIME REPRODUCED", rendered)
                        self.assertIn("CONTRACT-DEPENDENT", rendered)
                        self.assertIn("Verification actually performed", rendered)
                        self.assertIn("Review", rendered)


if __name__ == "__main__":
    unittest.main()
