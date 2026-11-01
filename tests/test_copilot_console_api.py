"""HTTP regression coverage for opt-in Copilot integration."""
import http.client
import json
from pathlib import Path
import sys
import threading
import tempfile
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from console_api import make_handler
from approved_copilot_review import execute as execute_review

class CopilotApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.root = Path(self.workspace.name)
        (self.root / "demo" / ".git").mkdir(parents=True)
        (self.root / "demo" / "App.java").write_text("class App {}")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            enable_copilot=True, repository_roots=[self.root]))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

        self.workspace.cleanup()

    def request(self, method, path, body=None, origin=None):
        port = self.server.server_port
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        headers = {"Host": "127.0.0.1:" + str(port)}
        if origin:
            headers["Origin"] = origin
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        status, payload = response.status, json.loads(response.read())
        conn.close()
        return status, payload

    def test_status_enabled(self):
        code, result = self.request("GET", "/api/copilot/status")
        self.assertEqual(200, code)
        self.assertTrue(result["enabled"])

    def test_copilot_chat_route(self):
        with patch("console_api.copilot_chat", return_value={"reply": "OK"}) as call:
            code, result = self.request("POST", "/api/copilot/chat",
                json.dumps({"model":"test","messages":[{"role":"user","content":"Hi"}]}),
                "http://127.0.0.1:5173")
        self.assertEqual(200, code)
        self.assertEqual("OK", result["reply"])
        call.assert_called_once()

    def test_named_agent_reaches_chat_transport(self):
        payload = {"model": "claude-sonnet-4", "agent": "java-reviewer",
                   "messages": [{"role": "user", "content": "Review Java"}]}
        with patch("console_api.copilot_chat", return_value={"reply": "fixture"}) as call:
            code, _ = self.request("POST", "/api/copilot/chat", json.dumps(payload),
                                   "http://127.0.0.1:5173")
        self.assertEqual(200, code)
        call.assert_called_once_with(payload)
        with patch("console_api.copilot_chat") as call:
            code, _ = self.request("POST", "/api/copilot/chat",
                                   json.dumps({**payload, "agent": "../outside"}),
                                   "http://127.0.0.1:5173")
        self.assertEqual(400, code)
        call.assert_not_called()

    def test_http_source_review_selection_and_stale_approval(self):
        payload = {"repository": "demo", "task": "Review Java",
                   "model": "claude-sonnet-4", "agent": "java-reviewer"}
        origin = "http://127.0.0.1:5173"
        code, prepared = self.request("POST", "/api/copilot/review/prepare",
                                      json.dumps(payload), origin)
        self.assertEqual(200, code)
        self.assertEqual("java-reviewer", prepared["agent"])
        self.assertIn("Review accuracy protocol", prepared["agent_profile"])
        execution = {**payload, "approved_sha256": prepared["sha256"]}
        calls = []
        def transport(request, **kwargs):
            calls.append((request, kwargs))
            return {"reply": "fixture review", "requested_model": request["model"],
                    "agent_selected": request["agent"]}
        def executor(context, model, digest):
            return execute_review(context, model, digest, transport=transport)
        with patch("console_api.execute_ai_review", side_effect=executor):
            for changed in ({"model": "claude-haiku-4"}, {"agent": "java-developer"}):
                code, _ = self.request("POST", "/api/copilot/review/execute",
                                       json.dumps({**execution, **changed}), origin)
                self.assertEqual(400, code)
            self.assertEqual([], calls)
            code, result = self.request("POST", "/api/copilot/review/execute",
                                        json.dumps(execution), origin)
            self.assertEqual(200, code)
            self.assertEqual("java-reviewer", result["review"]["agent_selected"])
            self.assertEqual("claude-sonnet-4", calls[0][0]["model"])
            self.assertEqual(prepared["agent_profile_sha256"], calls[0][1]["expected_agent_sha256"])
            (self.root / "demo" / "App.java").write_text("class Changed {}")
            code, _ = self.request("POST", "/api/copilot/review/execute", json.dumps(execution), origin)
            self.assertEqual(400, code)
            self.assertEqual(1, len(calls))

    def test_reject_foreign_origin(self):
        code, _ = self.request("POST", "/api/copilot/chat", "{}", "https://evil.example")
        self.assertEqual(403, code)

    def test_reject_missing_origin(self):
        code, _ = self.request("POST", "/api/copilot/chat", "{}")
        self.assertEqual(403, code)

    def test_copilot_disabled_by_default(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler())
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        code, result = self.request("GET", "/api/copilot/status")
        self.assertEqual(200, code)
        self.assertFalse(result["enabled"])

if __name__ == "__main__":
    unittest.main()
