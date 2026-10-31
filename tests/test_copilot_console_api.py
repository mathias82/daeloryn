"""HTTP regression coverage for opt-in Copilot integration."""
import http.client
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from console_api import make_handler

class CopilotApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(enable_copilot=True))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

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
