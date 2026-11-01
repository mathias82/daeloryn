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
from console_api import make_handler
from paired_review_benchmark import prepare, execute


class PairedBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "demo"
        self.project.mkdir()
        (self.project / ".git").mkdir()
        (self.project / "App.java").write_text("class App { int value; }\n", encoding="utf-8")

    def selection(self, **updates):
        return {"repository": "demo", "mode": "review",
                "model": "test", "agent": "java-reviewer", **updates}

    def test_prepare_uses_same_snapshot_without_model_calls(self):
        manifest = prepare(self.root, **self.selection())
        self.assertFalse(manifest["source_transmitted"])
        self.assertTrue(manifest["approval_required"])
        self.assertEqual(manifest["baseline"]["files"], manifest["daeloryn"]["files"])
        self.assertEqual(2, manifest["total_model_calls"])
        self.assertIsNone(manifest["baseline"]["agent"])
        self.assertEqual("java-reviewer", manifest["daeloryn"]["agent"])
        self.assertIn("class App", manifest["baseline"]["prompt"])
        self.assertIn("class App", manifest["daeloryn"]["prompt"])

    def test_paired_execution_is_sequential_and_has_no_fake_winner(self):
        manifest = prepare(self.root, **self.selection())
        events, calls = [], []
        def fake_provider(request, **kwargs):
            calls.append(request)
            return {"reply": "source based finding"}
        result = execute(manifest, manifest["sha256"], transport=fake_provider,
                         progress=events.append)
        self.assertEqual(["baseline", "daeloryn"],
                         [e["arm"] for e in events if e["type"] == "arm_started"])
        self.assertEqual(2, len(calls))
        self.assertNotIn("agent", calls[0])
        self.assertEqual("java-reviewer", calls[1]["agent"])
        self.assertEqual("completed", result["status"])
        self.assertEqual("not_determined", result["winner"])
        self.assertFalse(result["independent_checks_executed"])
        self.assertEqual(2, len([e for e in events if e["type"] == "batch_reply"]))

    def test_coverage_partial_baseline_does_not_block_challenger_on_resume(self):
        (self.project / 'Large.java').write_bytes(b'x' * (300 * 1024))
        manifest = prepare(self.root, **self.selection())
        calls=[]
        def provider(request, **kwargs):
            calls.append(request)
            return {'reply': 'App.java:1 finding'}
        result=execute(manifest,manifest['sha256'],transport=provider,
                       resume_completed={'baseline':{1:'Previously completed baseline'}})
        self.assertEqual(1,len(calls))
        self.assertEqual('java-reviewer',calls[0]['agent'])
        self.assertEqual('partial',result['status'])
        self.assertEqual({'baseline','daeloryn'},set(result['arms']))
        self.assertTrue(result['arms']['baseline']['execution_complete'])
        self.assertTrue(result['arms']['daeloryn']['execution_complete'])
        self.assertFalse(result['arms']['baseline']['coverage']['all_eligible_files_included'])
        self.assertEqual('not_determined',result['winner'])

    def test_wrong_digest_prevents_every_provider_call(self):
        manifest = prepare(self.root, **self.selection())
        with self.assertRaises(PermissionError):
            execute(manifest, "0" * 64, transport=lambda *_args, **_kw: self.fail("provider called"))
        self.assertNotEqual(manifest["sha256"],
                            prepare(self.root, **self.selection(mode="architecture"))["sha256"])
        self.assertNotEqual(manifest["sha256"],
                            prepare(self.root, **self.selection(agent="java-architect"))["sha256"])

    def test_baseline_failure_stops_second_arm_without_retry(self):
        manifest = prepare(self.root, **self.selection())
        calls = []
        def fails(request, **kwargs):
            calls.append(request)
            raise RuntimeError("provider outcome unknown")
        result = execute(manifest, manifest["sha256"], transport=fails)
        self.assertEqual(1, len(calls))
        self.assertEqual("partial", result["status"])
        self.assertNotIn("daeloryn", result["arms"])

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            prepare(self.root, **self.selection(mode="execute-tests"))


class PairedBenchmarkApiTests(PairedBenchmarkTests):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0),
                                          make_handler(enable_copilot=True, repository_roots=[self.root]))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.worker.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, path, payload, accept=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        self.addCleanup(conn.close)
        headers = {"Content-Type": "application/json", "Origin": "http://127.0.0.1:5173"}
        if accept:
            headers["Accept"] = accept
        conn.request("POST", path, json.dumps(payload), headers)
        return conn, conn.getresponse()

    def test_manifest_and_digest_gate(self):
        req = self.selection()
        conn, response = self.post("/api/benchmark/prepare", req)
        self.assertEqual(200, response.status)
        manifest = json.loads(response.read())
        self.assertEqual("test", manifest["model"])
        self.assertFalse(manifest["source_transmitted"])
        with patch("console_api.execute_pair") as model:
            conn, response = self.post("/api/benchmark/execute",
                                       {**req, "approved_sha256": "b" * 64},
                                       "application/x-ndjson")
            self.assertEqual(400, response.status)
            self.assertIn("changed", json.loads(response.read())["error"])
            model.assert_not_called()
        # Any source drift invalidates consent, before any provider call.
        (self.project / "App.java").write_text("class Changed {}\n", encoding="utf-8")
        with patch("console_api.execute_pair") as model:
            conn, response = self.post("/api/benchmark/execute",
                                       {**req, "approved_sha256": manifest["sha256"]},
                                       "application/x-ndjson")
            self.assertEqual(400, response.status)
            model.assert_not_called()

    def test_real_ndjson_progress_and_two_arms(self):
        req = self.selection()
        conn, response = self.post("/api/benchmark/prepare", req)
        manifest = json.loads(response.read())
        from paired_review_benchmark import execute as real_execute
        calls = []
        def fake_provider(request, **kwargs):
            calls.append(request)
            return {"reply": "review fixture"}
        def injected(manifest, approved, **kwargs):
            return real_execute(manifest, approved, transport=fake_provider, **kwargs)
        with patch("console_api.execute_pair", side_effect=injected):
            conn, response = self.post("/api/benchmark/execute",
                                       {**req, "approved_sha256": manifest["sha256"]},
                                       "application/x-ndjson")
            self.assertEqual(200, response.status)
            events = [json.loads(line) for line in response.read().splitlines()]
        self.assertEqual(2, len(calls))
        self.assertEqual(["baseline", "daeloryn"],
                         [e["arm"] for e in events if e["type"] == "arm_started"])
        self.assertEqual("completed", events[-1]["result"]["status"])
        self.assertEqual("not_determined", events[-1]["result"]["winner"])

    def test_auto_model_routes_only_during_prepare(self):
        req = self.selection(model="auto")
        with patch("console_api.route_chat", return_value=({"model": "test", "messages": []}, None)) as routing:
            conn, response = self.post("/api/benchmark/prepare", req)
            manifest = json.loads(response.read())
        self.assertEqual(200, response.status)
        self.assertEqual("test", manifest["model"])
        routing.assert_called_once()
        conn, response = self.post("/api/benchmark/execute",
                                   {**req, "approved_sha256": manifest["sha256"]},
                                   "application/x-ndjson")
        self.assertEqual(400, response.status)

    def test_untrusted_origin_never_prepares_project(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        self.addCleanup(conn.close)
        conn.request("POST", "/api/benchmark/prepare", json.dumps(self.selection()),
                     {"Content-Type": "application/json", "Origin": "https://untrusted.example"})
        response = conn.getresponse()
        self.assertEqual(403, response.status)
        response.read()


if __name__ == "__main__":
    unittest.main()
