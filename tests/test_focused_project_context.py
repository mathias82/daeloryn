"""Focused context, consent binding, and no unrelated source upload."""
import http.client
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from focused_project_context import snapshot_focused
from approved_copilot_review import prepare, execute
from console_api import make_handler


class FocusedContextTests(unittest.TestCase):
    def test_greek_read_code_request_includes_program_source(self):
        (self.project / 'Unmatched.java').write_text('class Unmatched {}', encoding='utf-8')
        context = snapshot_focused(self.parent, 'demo', 'χρησιμοποιησε εργαλεια να δεις τον κωδικα και πες μου ποιες ειναι')
        self.assertTrue(any(item['path'].endswith('.java') for item in context['files']))

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.project = self.parent / "demo"
        self.project.mkdir()
        (self.project / ".git").mkdir()
        (self.project / "src").mkdir()
        (self.project / "README.md").write_text("Sample service", encoding="utf-8")
        (self.project / "pom.xml").write_text("<project/>", encoding="utf-8")
        (self.project / "src/TelemetryService.java").write_text("class TelemetryService {}", encoding="utf-8")
        (self.project / "src/Inventory.java").write_text("class Inventory {}", encoding="utf-8")
        (self.project / "src/application.properties").write_text("management.tracing.enabled=true", encoding="utf-8")
        (self.project / "src/application-prod.yml").write_text("private-key: unsafe", encoding="utf-8")

    def test_filename_ranked_context_excludes_unrelated_sources(self):
        context = snapshot_focused(self.parent, "demo", "How does observability work in this project?")
        paths = [item["path"] for item in context["files"]]
        self.assertIn("src/TelemetryService.java", paths)
        self.assertIn("README.md", paths)
        self.assertIn("pom.xml", paths)
        self.assertNotIn("src/Inventory.java", paths)
        self.assertNotIn("src/application-prod.yml", paths)
        self.assertLessEqual(len(paths), 8)
        self.assertFalse(context["all_eligible_files_included"])
        self.assertEqual("focused", context["scope_type"])

    def test_generic_bug_review_reads_real_java_source_not_only_readme_and_pom(self):
        context = snapshot_focused(self.parent, "demo", "inspect the project for bugs")
        paths = [item["path"] for item in context["files"]]
        self.assertIn("src/Inventory.java", paths)
        self.assertIn("src/TelemetryService.java", paths)
        self.assertTrue(any(path.endswith(".java") for path in paths))
        self.assertLessEqual(len(paths), 8)
        self.assertFalse(context["all_eligible_files_included"])
        self.assertIn("NOT all project files", context["scope"])

    def test_generic_bug_review_fails_without_any_program_source(self):
        (self.project / "src/TelemetryService.java").unlink()
        (self.project / "src/Inventory.java").unlink()
        with self.assertRaisesRegex(ValueError, "no eligible source"):
            snapshot_focused(self.parent, "demo", "inspect the project for bugs")

    def test_scope_changes_digest_and_full_scope_reads_more(self):
        task = "How does observability work in this project?"
        focused = prepare(self.parent, "demo", task, "test", scope="focused")
        full = prepare(self.parent, "demo", task, "test")
        self.assertNotIn("src/Inventory.java", focused["files"])
        self.assertIn("src/Inventory.java", full["files"])
        self.assertNotEqual(focused["sha256"], full["sha256"])
        self.assertEqual("focused", focused["scope"])
        self.assertTrue(all("Inventory.java" not in prompt for prompt in focused["prompts"]))
        result = execute(focused, "test", focused["sha256"],
                         transport=lambda *_a, **_kw: {"reply": "Focused answer"})
        self.assertEqual("completed", result["status"])
        self.assertIsNone(result["verified_usage_credits"])

    def test_focused_read_invalidates_drift_before_model_call(self):
        task = "How does observability work in this project?"
        prepared = prepare(self.parent, "demo", task, "test", scope="focused")
        (self.project / "src/TelemetryService.java").write_text("class ChangedTelemetry {}", encoding="utf-8")
        latest = prepare(self.parent, "demo", task, "test", scope="focused")
        self.assertNotEqual(prepared["sha256"], latest["sha256"])
        with self.assertRaises(PermissionError):
            execute(latest, "test", prepared["sha256"],
                    transport=lambda *_a, **_kw: self.fail("unexpected model call"))

    def test_invalid_scope_rejected(self):
        with self.assertRaises(ValueError):
            prepare(self.parent, "demo", "Hi", "test", scope="silent-upload")

    def test_source_budget_is_bounded(self):
        for index in range(15):
            (self.project / "src" / ("TracingHelper%02d.java" % index)).write_text("class TracingHelper{}")
        result = snapshot_focused(self.parent, "demo", "How does tracing work in project?")
        self.assertLessEqual(len(result["files"]), 8)
        self.assertLessEqual(result["bytes_read"], 64 * 1024)

class FocusedContextApiTests(FocusedContextTests):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0),
            make_handler(enable_copilot=True, repository_roots=[self.parent]))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.worker.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, path, payload, accept=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        self.addCleanup(conn.close)
        headers = {"Content-Type": "application/json",
                   "Origin": "http://127.0.0.1:5173"}
        if accept is not None:
            headers["Accept"] = accept
        conn.request("POST", path, json.dumps(payload), headers)
        return conn.getresponse()

    def test_focused_api_and_stale_scope_approval(self):
        request = {"repository": "demo", "task": "How is observability implemented?",
                   "model": "test", "scope": "focused"}
        response = self.post("/api/copilot/review/prepare", request)
        self.assertEqual(200, response.status)
        manifest = json.loads(response.read())
        self.assertEqual("focused", manifest["scope"])
        self.assertNotIn("Inventory.java", manifest["prompt"])
        # Use the real digest verifier with an injected no-call provider;
        # mocking the entire executor would bypass the safety assertion.
        from approved_copilot_review import execute as real_execute
        invoked = []
        def never_provider(*_args, **_kwargs):
            invoked.append(True)
            raise AssertionError("provider must not be called")
        with patch("console_api.execute_ai_review", side_effect=lambda prepared, model, digest, **kwargs:
                   real_execute(prepared, model, digest, transport=never_provider, **kwargs)):
            response = self.post("/api/copilot/review/execute",
                {**request, "scope": "full", "approved_sha256": manifest["sha256"]},
                accept="application/x-ndjson")
            self.assertEqual(400, response.status)
            self.assertEqual([], invoked)

    def test_no_model_is_called_on_invalid_scope(self):
        with patch("console_api.prepare_ai_review") as prepare_mock:
            response = self.post("/api/copilot/review/prepare",
                {"repository": "demo", "task": "Review", "model": "test", "scope": "unsafe"})
            self.assertEqual(400, response.status)
            prepare_mock.assert_not_called()

if __name__ == "__main__":
    unittest.main()
