"""Regression tests for unified offline benchmark orchestration."""
import subprocess
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_benchmark_suite import COMMANDS, run_suite


class SuiteTests(unittest.TestCase):
    def test_all_checks_pass(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "ok", "")
        result = run_suite(runner=runner)
        self.assertTrue(result["passed"])
        self.assertFalse(result["provider_invoked"])
        self.assertFalse(result["implementation_verified"])
        self.assertEqual(len(COMMANDS), len(calls))

    def test_failed_check_does_not_skip_remaining_checks(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 1 if len(calls) == 1 else 0, "", "failure")
        result = run_suite(runner=runner)
        self.assertFalse(result["passed"])
        self.assertEqual("failed", result["checks"][0]["status"])
        self.assertEqual(len(COMMANDS), len(calls))

    def test_timeout_is_reported(self):
        def runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 1)
        result = run_suite(runner=runner)
        self.assertFalse(result["passed"])
        self.assertTrue(all(x["status"] == "timeout" for x in result["checks"]))

    def test_invalid_timeout(self):
        with self.assertRaises(ValueError):
            run_suite(timeout=0)


if __name__ == "__main__":
    unittest.main()
