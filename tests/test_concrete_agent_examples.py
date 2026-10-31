"""Keep concrete examples and compatibility checks in every specialist.

These assertions verify markdown and packaging, NOT AI execution or code correctness.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from agents import catalog, install


class ConcreteAgentExamplesTests(unittest.TestCase):
    def test_all_22_have_code_fences_and_version_checks(self):
        definitions = catalog()
        self.assertEqual(len(definitions), 22)
        for meta, body in definitions:
            with self.subTest(agent=meta["name"]):
                self.assertGreaterEqual(body.count("~~~"), 2, "missing concrete code fence")
                if meta["scope"] in ("java", "spring"):
                    self.assertIn("Java 8", body)
                elif meta["scope"] == "react":
                    self.assertIn("package.json", body)
                elif meta["scope"] == "platform":
                    self.assertTrue(
                        "version" in body.lower() or "toolchain" in body.lower()
                    )
                else:
                    self.assertIn("version", body.lower())

    def test_host_adapters_preserve_concrete_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self.assertEqual(install(target, "all", "all"), 88)
            for meta, _ in catalog():
                name = meta["name"]
                for suffix in (
                    Path(".codex/agents") / (name + ".toml"),
                    Path(".claude/agents") / (name + ".md"),
                    Path(".github/agents") / (name + ".agent.md"),
                    Path(".gemini/agents") / (name + ".md"),
                ):
                    with self.subTest(name=name, tool=str(suffix)):
                        self.assertIn("~~~", (target / suffix).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
