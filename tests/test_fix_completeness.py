"""Offline regression checks for complete-fix review instructions.

These verify canonical definitions and host adapter packaging, not AI compliance.
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

GATE = "Fix completeness and regression gate (mandatory)"
EXAMPLE = "### Fix completeness example"
REQUIRED = (
    "positive, negative, boundary and failure-path",
    "contract-dependent",
    "not run",
    "regression check",
)


class FixCompletenessTests(unittest.TestCase):
    def test_all_22_agents_map_fixes_to_full_regression_coverage(self):
        entries = catalog()
        self.assertEqual(22, len(entries))
        self.assertEqual(22, len({m["name"] for m, _ in entries}))
        for meta, body in entries:
            with self.subTest(agent=meta["name"]):
                self.assertIn(GATE, body)
                self.assertIn(EXAMPLE, body)
                after_example = body.split(EXAMPLE, 1)[1]
                self.assertGreaterEqual(after_example.count("~~~"), 2)
                self.assertIn("Incomplete", after_example)
                for phrase in REQUIRED:
                    self.assertIn(phrase, body.lower())
                self.assertTrue(
                    "Java 8" in body if meta["scope"] in ("java", "spring")
                    else True,
                    "Java/Spring agent must preserve Java 8 compatibility",
                )

    def test_copilot_claude_codex_gemini_preserve_quality_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(88, install(target, "all", "all"))
            for meta, _ in catalog():
                name = meta["name"]
                entries = (
                    Path(".codex/agents") / (name + ".toml"),
                    Path(".claude/agents") / (name + ".md"),
                    Path(".github/agents") / (name + ".agent.md"),
                    Path(".gemini/agents") / (name + ".md"),
                )
                for relative in entries:
                    with self.subTest(agent=name, adapter=str(relative)):
                        text = (target / relative).read_text(encoding="utf-8")
                        if relative.suffix == ".toml":
                            text = tomllib.loads(text)["developer_instructions"]
                        self.assertIn(GATE, text)
                        self.assertIn(EXAMPLE, text)
                        self.assertIn("Run status: **not run**", text)


if __name__ == "__main__":
    unittest.main()
