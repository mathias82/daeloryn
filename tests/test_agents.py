import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from agents import catalog, install, parse

class AgentTests(unittest.TestCase):
    def test_catalog_is_unique_and_valid(self):
        agents = catalog()
        self.assertEqual(len(agents), 22)
        self.assertEqual(len({a[0]["name"] for a in agents}), 22)

    def test_all_agents_have_evidence_contract_and_examples(self):
        for meta, body in catalog():
            with self.subTest(agent=meta["name"]):
                self.assertIn("evidence contract", body.lower())
                self.assertIn("example", body.lower())

    def test_reject_missing_evidence_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "java" / "java-developer.md"
            path.parent.mkdir()
            path.write_text("---\nname: java-developer\ndescription: Demo\nscope: java\n---\n"
                            + "Example: good design. " * 30)
            with self.assertRaisesRegex(ValueError, "quality sections"):
                parse(path)

    def test_reject_nested_symlink_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            outside = target / "outside"
            outside.mkdir()
            (target / ".github").mkdir()
            (target / ".github" / "agents").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                install(target, "shared", "copilot")
            self.assertEqual(list(outside.iterdir()), [])

    def test_install_spring_across_all_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.assertEqual(install(target, "spring", "all"), 24)
            self.assertTrue((target / ".codex/agents/spring-boot-engineer.toml").exists())
            self.assertTrue((target / ".claude/agents/spring-security-engineer.md").exists())
            self.assertTrue((target / ".github/agents/spring-reactive-engineer.agent.md").exists())
            self.assertTrue((target / ".gemini/agents/spring-testing-engineer.md").exists())

    def test_platform_all_adapters(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.assertEqual(install(target, "platform", "all"), 24)
            self.assertTrue((target / ".codex/agents/kubernetes-engineer.toml").is_file())
            self.assertTrue((target / ".claude/agents/docker-engineer.md").is_file())
            self.assertTrue((target / ".github/agents/cicd-engineer.agent.md").is_file())
            self.assertTrue((target / ".gemini/agents/gitops-engineer.md").is_file())

    def test_install_java_codex(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.assertEqual(install(target, "java", "codex"), 4)
            result = target / ".codex/agents/java-developer.toml"
            config = tomllib.loads(result.read_text())
            self.assertEqual(config["name"], "java-developer")
            self.assertIn("Spring Boot", config["developer_instructions"])

    def test_install_react_claude(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.assertEqual(install(target, "react", "claude"), 4)
            self.assertTrue((target / ".claude/agents/react-reviewer.md").exists())

    def test_install_copilot(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.assertEqual(install(target, "shared", "copilot"), 2)
            output = (target / ".github/agents/security-reviewer.agent.md").read_text()
            self.assertIn("description: ", output)
            self.assertIn("name: security-reviewer", output)

    def test_install_gemini(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.assertEqual(install(target, "shared", "gemini"), 2)
            output = (target / ".gemini/agents/security-reviewer.md").read_text()
            self.assertIn("kind: local", output)
            self.assertIn("name: security-reviewer", output)

    def test_install_all_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.assertEqual(install(target, "java", "all"), 16)
            self.assertTrue((target / ".github/agents/java-developer.agent.md").is_file())
            self.assertTrue((target / ".gemini/agents/java-developer.md").is_file())

    def test_failed_write_restores_previous_contents(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            install(target, "shared", "both")
            old = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
            real_replace = os.replace
            attempts = [0]
            def fail_on_second(src, dst):
                if ".agent-stage-" in str(src):
                    attempts[0] += 1
                    if attempts[0] == 2:
                        raise OSError("simulated second install failure")
                return real_replace(src, dst)
            with patch("agents.os.replace", side_effect=fail_on_second):
                with self.assertRaisesRegex(OSError, "simulated"):
                    install(target, "shared", "both", force=True)
            self.assertEqual({p: p.read_bytes() for p in old}, old)
            self.assertFalse(list(target.rglob(".agent-stage-*")))

    def test_failed_write_removes_newly_created_files(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            real_replace = os.replace
            attempts = [0]
            def fail_on_second(src, dst):
                if ".agent-stage-" in str(src):
                    attempts[0] += 1
                    if attempts[0] == 2:
                        raise OSError("simulated write failure")
                return real_replace(src, dst)
            with patch("agents.os.replace", side_effect=fail_on_second):
                with self.assertRaises(OSError):
                    install(target, "shared", "both")
            self.assertFalse(list(target.rglob("*.toml")))
            self.assertFalse(list(target.rglob("*.md")))

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            self.assertEqual(install(target, "shared", "all", dry_run=True), 8)
            self.assertFalse((target / ".codex").exists())
            self.assertFalse((target / ".github").exists())

    def test_no_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            install(target, "shared", "both")
            with self.assertRaises(FileExistsError):
                install(target, "shared", "both")
            self.assertEqual(install(target, "shared", "both", force=True), 4)

    def test_reject_symlink_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            other = Path(temp) / "outside"
            other.mkdir()
            (target / ".codex").symlink_to(other, target_is_directory=True)
            with self.assertRaises(ValueError):
                install(target, "java", "codex")

if __name__ == "__main__":
    unittest.main()
