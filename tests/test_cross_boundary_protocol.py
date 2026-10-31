"""Verify the cross-boundary review proof protocol is shipped to all hosts.

These are instruction/adapter tests; they do not measure LLM behavior.
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

MARKER = "Cross-boundary outcome and fix-proof protocol (mandatory)"


class CrossBoundaryProtocolTests(unittest.TestCase):
    def test_all_22_agents_include_outcome_matrix_and_specific_challenge(self):
        agents = catalog()
        self.assertEqual(22, len(agents))
        challenges = set()
        for meta, body in agents:
            with self.subTest(agent=meta["name"]):
                self.assertEqual(body.count("## " + MARKER), 1)
                tail = body.split("## " + MARKER, 1)[1]
                for phrase in (
                    "unknown outcome", "negative control", "UNVERIFIED",
                    "no confirmed findings", "not run",
                    "Role-specific outcome challenge:"
                ):
                    self.assertIn(phrase.lower(), tail.lower())
                challenge = tail.split("**Role-specific outcome challenge:**", 1)[1].strip()
                self.assertGreater(len(challenge), 70)
                self.assertIn("Example:", challenge)
                challenges.add(challenge)
        self.assertEqual(22, len(challenges), "each specialty must have a unique scenario")

    def test_all_88_generated_adapters_retain_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(88, install(target, "all", "all"))
            for meta, _ in catalog():
                name = meta["name"]
                for path in (
                    Path(".github/agents") / (name + ".agent.md"),
                    Path(".claude/agents") / (name + ".md"),
                    Path(".codex/agents") / (name + ".toml"),
                    Path(".gemini/agents") / (name + ".md")
                ):
                    with self.subTest(agent=name, host=str(path)):
                        result = (target / path).read_text(encoding="utf-8")
                        if path.suffix == ".toml":
                            result = tomllib.loads(result)["developer_instructions"]
                        self.assertIn(MARKER, result)
                        self.assertIn("unknown outcome", result)
                        self.assertIn("negative control", result)


if __name__ == "__main__":
    unittest.main()
