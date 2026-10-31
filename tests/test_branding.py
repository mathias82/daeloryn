"""Guard canonical project links against accidental pre-rename regressions."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BrandingTests(unittest.TestCase):
    def test_readme_and_getting_started_use_canonical_clone_url(self):
        canonical = "https://github.com/mathias82/daeloryn.git"
        for relative in ("README.md", "docs/getting-started.md"):
            with self.subTest(path=relative):
                contents = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(canonical, contents)
                self.assertNotIn("github.com/mathias82/enterprise-engineering-agents.git", contents)
                self.assertIn("cd daeloryn", contents)


if __name__ == "__main__":
    unittest.main()
