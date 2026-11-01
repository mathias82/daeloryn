"""Explicit real-Docker checks. Missing Docker/image is a failure, never a skip."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "workflow_live_trial.py"


class DockerWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("docker"):
            raise RuntimeError("real Docker integration requires Docker")
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=30)
        cls.image = os.environ["DAELORYN_E2E_IMAGE"]

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.source = self.directory / "source"
        self.source.mkdir()
        self.git("init")
        (self.source / "README.md").write_text("Disposable local fixture\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-m", "fixture")
        self.workspace = self.directory / "trial"

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.source, capture_output=True, check=True)

    def cli(self, phase, *args):
        return subprocess.run([sys.executable, str(CLI), phase, "--workspace", str(self.workspace),
                               "--repository", "org/repo", *args], capture_output=True,
                              text=True, timeout=120)

    def run_tests(self, scenario="pass", timeout=60):
        result = self.cli("tests", "--source-checkout", str(self.source), "--image", self.image,
                          "--approve-fixture", "--approve-tests", "--scenario", scenario,
                          "--timeout", str(timeout))
        report = json.loads((self.workspace / "report.json").read_text(encoding="utf-8"))
        return result, report

    def state(self):
        return json.loads((self.workspace / "state" / "trial.json").read_text(encoding="utf-8"))

    def test_real_container_then_restart_requires_separate_publication_approval(self):
        result, report = self.run_tests()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("passed", report["outcome"])
        self.assertTrue(report["tests"]["containerized"])
        self.assertIn("OK", report["tests"]["output"])
        self.assertFalse((self.workspace / "checkout" / "scratch.txt").exists())
        self.assertFalse((self.workspace / "checkout" / "host-write.txt").exists())
        self.assertEqual("tests_passed", self.state()["stage"])
        # Fresh process: even valid evidence cannot authorize publication alone.
        denied = self.cli("publish", "--expected-commit", report["commit"],
                          "--approval-digest", report["publication_digest"])
        self.assertEqual(2, denied.returncode)
        self.assertIn("separate explicit publication approval", denied.stderr)
        self.assertEqual("tests_passed", self.state()["stage"])
        self.assertEqual("not_attempted", report["publication"])

    def test_real_failing_tests_cannot_publish(self):
        result, report = self.run_tests("fail")
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual("failed", report["outcome"])
        self.assertEqual("patch_approved", self.state()["stage"])
        denied = self.cli("publish", "--approve-publication", "--expected-commit", report["commit"],
                          "--approval-digest", "a" * 64)
        self.assertEqual(2, denied.returncode)
        self.assertNotIn("test_evidence", self.state())

    def test_real_timeout_stops_container_and_blocks_automatic_retry_after_restart(self):
        result, report = self.run_tests("timeout", timeout=3)
        self.assertEqual(2, result.returncode)
        self.assertEqual("unknown", report["outcome"])
        self.assertTrue(report["cleanup_verified"], result.stderr)
        self.assertEqual("tests_running", self.state()["stage"])
        remaining = subprocess.run(["docker", "ps", "-aq", "--filter", "name=" + report["container_name"]],
                                   capture_output=True, text=True, check=True, timeout=20)
        self.assertEqual("", remaining.stdout.strip())
        retry = self.cli("tests", "--source-checkout", str(self.source), "--image", self.image,
                         "--approve-fixture", "--approve-tests")
        self.assertEqual(2, retry.returncode)
        self.assertIn("never automatically retried", retry.stderr)
        self.assertEqual(1, self.state()["attempts"])

    def test_post_test_mutation_blocks_publication_before_github_access(self):
        result, report = self.run_tests()
        self.assertEqual(0, result.returncode, result.stderr)
        (self.workspace / "checkout" / "README.md").write_text("unapproved", encoding="utf-8")
        denied = self.cli("publish", "--approve-publication", "--expected-commit", report["commit"],
                          "--approval-digest", report["publication_digest"])
        self.assertEqual(2, denied.returncode)
        self.assertIn("clean checkout", denied.stderr)
        self.assertEqual("tests_passed", self.state()["stage"])


if __name__ == "__main__":
    unittest.main()
