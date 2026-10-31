import unittest
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("platform_eval", ROOT / "scripts" / "evaluate_platform.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class ReferenceFixtureTests(unittest.TestCase):
    def test_known_findings_are_consistent(self):
        MODULE.evaluate()

    def test_non_vulnerable_snippets_do_not_match(self):
        content = "FROM alpine:3.20\nUSER 10001\npermissions:\n  contents: read\n"
        self.assertEqual(MODULE.detect(content), set())

if __name__ == "__main__":
    unittest.main()
