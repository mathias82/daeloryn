import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from capture_provider_cli import capture

class ProviderCaptureTests(unittest.TestCase):
    def test_invalid_provider_and_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                capture(tmp, "other", "model", ["other"])
            with self.assertRaises(ValueError):
                capture(tmp, "copilot", "bad model", ["copilot"])

    def test_executable_must_match_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                capture(tmp, "copilot", "sonnet", ["python3", "-V"])

    def test_timeout_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                capture(tmp, "copilot", "sonnet", ["copilot"], timeout=0)

    @unittest.skipUnless(os.name == "posix", "POSIX-only capture")
    def test_launch_error_is_not_provider_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("capture_provider_cli.subprocess.Popen", side_effect=OSError("missing")):
                result = capture(tmp, "copilot", "sonnet", ["copilot"])
        self.assertEqual("launch_error", result["status"])
        self.assertFalse(result["provider_invoked"])

if __name__ == "__main__":
    unittest.main()
