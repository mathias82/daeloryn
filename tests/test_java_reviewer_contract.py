"""Static guardrails for reviewer prompt quality, not model-performance tests."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REVIEWER = ROOT / "agents" / "java" / "java-reviewer.md"


class JavaReviewerContractTests(unittest.TestCase):
    def test_required_review_guardrails(self):
        instructions = REVIEWER.read_text(encoding="utf-8").lower()
        for phrase in (
            "line accuracy",
            "statically verified",
            "runtime reproduced",
            "no duplicate inflation",
            "contract-aware severity",
            "java-version fidelity",
            "fix consistency",
            "concurrenthashmap",
            "math.addexact",
            "semaphore",
            "not verified / contract questions",
        ):
            with self.subTest(rule=phrase):
                self.assertIn(phrase, instructions)

    def test_installer_preserves_reviewer_contract_in_copilot_output(self):
        import sys
        import tempfile
        sys.path.insert(0, str(ROOT / "scripts"))
        from agents import install
        with tempfile.TemporaryDirectory() as directory:
            install(Path(directory), "java", "copilot")
            output = (Path(directory) / ".github" / "agents" / "java-reviewer.agent.md").read_text(encoding="utf-8")
            self.assertIn("Review accuracy protocol (mandatory)", output)
            self.assertIn("runtime reproduced", output)
            self.assertIn("no duplicate inflation", output)


if __name__ == "__main__":
    unittest.main()
