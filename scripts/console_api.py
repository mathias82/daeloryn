#!/usr/bin/env python3
"""Loopback-only, read-only JSON API for the Daeloryn console.

Optionally accepts bounded local-only chat prompts; never commands or credentials.
"""
import argparse
from copilot_chat import copilot_chat
from local_chat import installed_models, chat, MAX_REQUEST
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

from agents import catalog
from benchmark_matrix import matrix

ROOT = Path(__file__).resolve().parents[1]
MAX_RECORD_BYTES = 128 * 1024
MAX_RECORDS = 500


def agent_data():
    return [{"name": meta["name"], "description": meta["description"],
             "scope": meta["scope"]} for meta, _ in catalog()]


def benchmark_data(records_dir=None):
    records = []
    if records_dir is not None:
        directory = Path(records_dir)
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("benchmark records directory must be a real directory")
        files = sorted(directory.glob("*.json"))
        if len(files) > MAX_RECORDS:
            raise ValueError("too many benchmark records")
        for path in files:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECORD_BYTES:
                raise ValueError("unsafe or oversized benchmark record")
            records.append(json.loads(path.read_text(encoding="utf-8")))
    return matrix(records)


def make_handler(records_dir=None, enable_chat=False):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if host not in ("127.0.0.1:8765", "localhost:8765",
                            "127.0.0.1:" + str(self.server.server_port),
                            "localhost:" + str(self.server.server_port)):
                self.reply(403, {"error": "invalid host"})
                return
            if origin is not None and origin not in ("http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:" + str(self.server.server_port), "http://localhost:" + str(self.server.server_port)):
                self.reply(403, {"error": "untrusted origin"})
                return
            path = urlsplit(self.path)
            if path.query or path.fragment:
                self.reply(400, {"error": "query parameters not supported"})
                return
            try:
                if path.path == "/api/health":
                    payload = {"status": "ok", "execution_enabled": False,
                               "provider_connected": False, "local_chat_enabled": enable_chat}
                elif path.path == "/api/copilot/status":
                    payload = {"enabled": enable_copilot, "provider": "github-copilot-cli",
                               "model_discovery": "not_verified"}
                elif path.path == "/api/agents":
                    payload = {"agents": agent_data(), "source": "repository"}
                elif path.path == "/api/models":
                    try:
                        names = installed_models() if enable_chat else []
                        available = enable_chat
                    except (OSError, ValueError, KeyError, TypeError):
                        names, available = [], False
                    payload = {"models": names, "provider": "ollama-local", "chat_enabled": available}
                elif path.path == "/api/benchmarks":
                    payload = benchmark_data(records_dir)
                else:
                    self.reply(404, {"error": "unknown endpoint"})
                    return
            except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError):
                self.reply(503, {"error": "data unavailable or invalid"})
                return
            self.reply(200, payload)

        def do_POST(self):
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            allowed_host = host in ("127.0.0.1:" + str(self.server.server_port),
                                    "localhost:" + str(self.server.server_port))
            if not allowed_host or origin not in ("http://127.0.0.1:5173", "http://localhost:5173",
                                                  "http://127.0.0.1:" + str(self.server.server_port),
                                                  "http://localhost:" + str(self.server.server_port)):
                self.reply(403, {"error": "untrusted request origin"})
                return
            if not enable_chat or self.path != "/api/chat":
                self.reply(405, {"error": "chat disabled or unsupported endpoint"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self.reply(415, {"error": "JSON required"})
                return
            length = self.headers.get("Content-Length", "")
            if not length.isdigit() or not 0 < int(length) <= MAX_REQUEST:
                self.reply(413, {"error": "request too large or missing length"})
                return
            try:
                payload = json.loads(self.rfile.read(int(length)))
                result = chat(payload)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                self.reply(400, {"error": "invalid chat request or provider response"})
                return
            except (OSError, TimeoutError):
                self.reply(503, {"error": "local model unavailable"})
                return
            self.reply(200, result)

        def do_PUT(self):
            self.reply(405, {"error": "read-only API"})

        def do_DELETE(self):
            self.reply(405, {"error": "read-only API"})

        def reply(self, status, payload):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--enable-copilot-chat", action="store_true", help="opt in to Copilot CLI inference")
    p.add_argument("--enable-local-chat", action="store_true", help="opt in to local Ollama inference")
    p.add_argument("--records-dir", type=Path)
    a = p.parse_args()
    if not 1024 <= a.port <= 65535:
        p.error("port must be 1024..65535")
    if a.records_dir is not None and (a.records_dir.is_symlink() or not a.records_dir.is_dir()):
        p.error("records-dir must be an existing real directory")
    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(a.records_dir, a.enable_local_chat))
    print("Daeloryn local console API listening on http://127.0.0.1:" + str(a.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    sys.exit(main())
