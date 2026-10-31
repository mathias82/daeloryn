"""Coverage for blinded Copilot trials with actual Java project build context."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_blind_java_review import prepare


class BlindProjectContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.project = self.work / "sample-project"
        self.java = self.project / "src/main/java/Inventory.java"
        self.java.parent.mkdir(parents=True)
        self.java.write_text("public class Inventory {}\n", encoding="utf-8")
        (self.project / "pom.xml").write_text(
            "<project><properties><maven.compiler.source>1.8"
            "</maven.compiler.source></properties></project>\n", encoding="utf-8"
        )
        self.output = self.work / "trial-001"

    def test_same_source_and_build_context_but_agent_only_in_specialist(self):
        result = prepare(self.java, self.output, self.project, ["pom.xml"])
        self.assertEqual(result["fixture"], "src/main/java/Inventory.java")
        expected = {"pom.xml", "src/main/java/Inventory.java"}
        self.assertEqual(set(result["context_sha256"]), expected)
        for arm in ("baseline", "daeloryn"):
            base = self.output / arm
            for path in expected:
                self.assertEqual((base / path).read_bytes(),
                                 (self.project / path).read_bytes())
                self.assertEqual(
                    result["context_sha256"][path],
                    hashlib.sha256((base / path).read_bytes()).hexdigest()
                )
        self.assertFalse((self.output / "baseline/.github").exists())
        self.assertTrue(
            (self.output / "daeloryn/.github/agents/java-reviewer.agent.md").is_file()
        )
        self.assertEqual(
            json.loads((self.output / "manifest.json").read_text(encoding="utf-8")),
            result
        )
        self.assertEqual(result["status"], "prepared_only_no_model_runs")

    def test_rejects_agent_instructions_and_gold_answers(self):
        (self.project / "AGENTS.md").write_text("hidden instructions", encoding="utf-8")
        (self.project / "ground-truth.java").write_text("class Gold {}", encoding="utf-8")
        for forbidden in ("../outside.java", "AGENTS.md",
                          ".github/copilot-instructions.md", "ground-truth.java"):
            with self.subTest(path=forbidden):
                with self.assertRaises(ValueError):
                    prepare(self.java, self.output, self.project, [forbidden])
                self.assertFalse(self.output.exists())

    def test_refuses_output_inside_source_project(self):
        with self.assertRaises(ValueError):
            prepare(self.java, self.project / "trials/trial-001", self.project,
                    ["pom.xml"])
        self.assertFalse((self.project / "trials").exists())

    def test_context_requires_explicit_project_root(self):
        with self.assertRaises(ValueError):
            prepare(self.java, self.output, include=["pom.xml"])
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
