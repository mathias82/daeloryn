import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from isolated_provider_runner import docker_argv, capture_isolated

IMAGE = "example/provider@sha256:" + "a" * 64

class IsolatedRunnerTests(unittest.TestCase):
    def test_security_flags(self):
        argv = docker_argv(IMAGE, "copilot", ["copilot", "--help"])
        self.assertIn("--network=none", argv)
        self.assertIn("--cap-drop=ALL", argv)
        self.assertIn("--read-only", argv)
        self.assertNotIn("-v", argv)
        self.assertNotIn("--privileged", argv)

    def test_unpinned_image_rejected(self):
        with self.assertRaises(ValueError):
            docker_argv("provider:latest", "copilot", ["copilot"])

    def test_mismatched_provider_rejected(self):
        with self.assertRaises(ValueError):
            docker_argv(IMAGE, "copilot", ["gemini"])

    def test_network_not_enabled(self):
        with self.assertRaises(ValueError):
            docker_argv(IMAGE, "copilot", ["copilot"], network="bridge")

    def test_mock_execution_not_model_attestation(self):
        class Result:
            returncode = 0
            stdout = b"offline smoke"
            stderr = b""
        def runner(*args, **kwargs):
            return Result()
        result = capture_isolated(IMAGE, "copilot", "sonnet", ["copilot", "--help"], runner=runner)
        self.assertEqual("completed", result["status"])
        self.assertEqual("unverified", result["actual_model"])

if __name__ == "__main__":
    unittest.main()
