#!/usr/bin/env python3
"""Loopback-only JSON API with opt-in local project registration.

Optionally accepts bounded chat prompts; never arbitrary commands or credentials.
"""
import argparse
from copilot_chat import copilot_chat
from copilot_auto import available_models, route_chat
from agent_router import recommend
from repository_router import discover, suggest
from local_projects import ProjectRegistry, candidates, choose_directory
from github_repository_catalog import list_github_repositories
from project_analysis import analyze_local
from code_review import review
from approved_copilot_review import prepare as prepare_ai_review, execute as execute_ai_review
from patch_workspace import preview as preview_patch
from repair_agent import suggest as diagnose_failure
from workflow_recovery import inspect_interrupted
from local_chat import installed_models, chat, MAX_REQUEST
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import subprocess
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
    report = matrix(records)
    # Expose an allowlist only: records may contain private transcripts/argv.
    trials = []
    for record in records:
        models = record.get("requested_models", {})
        if not isinstance(models, dict):
            raise ValueError("invalid requested models")
        values = [record["run_id"], *models.values()]
        if any(not isinstance(value, str) or not value.strip() or len(value) > 160
               or any(ord(char) < 32 for char in value) for value in values):
            raise ValueError("invalid benchmark labels")
        trials.append({"run_id": record["run_id"], "agent": record["agent"],
                       "provider": record["provider"], "arm": record["arm"],
                       "outcome": record["outcome"],
                       "baseline_model": models.get("baseline", "Not recorded"),
                       "daeloryn_model": models.get("daeloryn", "Not recorded"),
                       "model_identity_verified": record.get("model_identity_verified") is True,
                       "agent_selection_verified": record.get("agent_selection_verified") is True,
                       "independent_checks_executed": record.get("independent_checks_executed") is True,
                       "comparable": record.get("comparable") is True})
    return {**report, "trials": trials}


def make_handler(records_dir=None, enable_chat=False, enable_copilot=False, repository_roots=(), enable_github_repositories=False, workflow_dir=None, projects_file=None, project_picker_roots=None):
    registry = ProjectRegistry(projects_file, project_picker_roots) if projects_file is not None else None

    def repository_catalog():
        rows = discover(repository_roots)
        if registry is not None:
            rows += registry.list()
        unique = {row["path"]: row for row in rows}
        if len(unique) > 100:
            raise ValueError("repository catalog exceeds limit")
        return list(unique.values())

    def resolve_repository(name):
        rows = [row for row in repository_catalog() if row["name"] == name]
        if len(rows) != 1:
            raise ValueError("repository must resolve uniquely")
        return [Path(rows[0]["path"]).parent]

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
                elif path.path == "/api/copilot/models":
                    if not enable_copilot:
                        self.reply(405, {"error": "Copilot disabled"})
                        return
                    try:
                        payload = {"models": available_models(), "source": "live-copilot-sdk",
                                   "automatic_routing": True}
                    except (RuntimeError, OSError, ValueError, TimeoutError):
                        self.reply(503, {"error": "Copilot model discovery unavailable"})
                        return
                elif path.path == "/api/github/repositories":
                    if not enable_github_repositories:
                        self.reply(405, {"error": "GitHub discovery disabled"})
                        return
                    try:
                        payload = {"repositories": list_github_repositories(),
                                   "source": "authenticated-gh-cli", "partial": True,
                                   "execution_enabled": False}
                    except (RuntimeError, OSError, ValueError):
                        self.reply(503, {"error": "GitHub discovery unavailable"})
                        return
                elif path.path == "/api/project-analysis":
                    self.reply(405, {"error": "POST required"})
                    return
                elif path.path == "/api/repositories":
                    payload = {"repositories": repository_catalog(), "source": "configured-local-checkouts",
                               "execution_enabled": False, "project_management_enabled": registry is not None}
                elif path.path == "/api/agents":
                    payload = {"agents": agent_data(), "source": "repository"}
                elif path.path == "/api/agent-routing":
                    self.reply(405, {"error": "POST required"})
                    return
                elif path.path == "/api/models":
                    try:
                        names = installed_models() if enable_chat else []
                        available = enable_chat
                    except (OSError, ValueError, KeyError, TypeError):
                        names, available = [], False
                    payload = {"models": names, "provider": "ollama-local", "chat_enabled": available}
                elif path.path == "/api/workflows/interrupted":
                    if workflow_dir is None:
                        self.reply(405, {"error": "workflow inspection disabled"})
                        return
                    payload = {"interrupted": inspect_interrupted(workflow_dir),
                               "read_only": True, "execution_enabled": False}
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
            if self.path == "/api/repositories/manage":
                if registry is None:
                    self.reply(405, {"error": "Restart the local API with --enable-project-picker"})
                    return
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "JSON required"})
                    return
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or not 0 < int(length) <= 65536:
                    self.reply(413, {"error": "invalid request size"})
                    return
                try:
                    payload = json.loads(self.rfile.read(int(length)))
                    if not isinstance(payload, dict):
                        raise ValueError("Invalid project request")
                    action = payload.get("action")
                    if action == "browse" and set(payload) == {"action"}:
                        if not registry.picker_lock.acquire(blocking=False):
                            raise ValueError("A folder chooser is already open")
                        try:
                            result = {"path": choose_directory()}
                        finally:
                            registry.picker_lock.release()
                    elif action == "preview" and set(payload) == {"action", "path", "recursive"} and isinstance(payload["recursive"], bool):
                        result = {"candidates": candidates(payload["path"], payload["recursive"], registry.allowed_roots)}
                    elif action == "add" and set(payload) == {"action", "paths", "approved"} and payload["approved"] is True:
                        registry.add(payload["paths"], repository_catalog())
                        result = {"repositories": repository_catalog()}
                    else:
                        raise ValueError("Select projects and explicitly approve local registration")
                except (ValueError, OSError, TypeError, KeyError) as exc:
                    self.reply(400, {"error": str(exc)})
                    return
                except (RuntimeError, TimeoutError, subprocess.SubprocessError):
                    self.reply(503, {"error": "Folder chooser unavailable or timed out; enter the absolute path instead"})
                    return
                self.reply(200, result)
                return
            if self.path in ("/api/copilot/review/prepare", "/api/copilot/review/execute"):
                if not enable_copilot:
                    self.reply(405, {"error": "Copilot disabled"})
                    return
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "JSON required"})
                    return
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or not 0 < int(length) <= 16384:
                    self.reply(413, {"error": "invalid request size"})
                    return
                streaming = False
                def emit(event):
                    nonlocal streaming
                    if not streaming:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Connection", "close")
                        self.end_headers()
                        self.close_connection = True
                        streaming = True
                    self.wfile.write((json.dumps(event) + "\n").encode("utf-8"))
                    self.wfile.flush()
                try:
                    payload = json.loads(self.rfile.read(int(length)))
                    is_execute = self.path.endswith("/execute")
                    expected = {"repository", "task", "model", "approved_sha256"} if is_execute else {"repository", "task", "model"}
                    if not isinstance(payload, dict) or set(payload) not in (expected, expected | {"agent"}):
                        raise ValueError("invalid review payload")
                    # Resolve automatic routing only at preparation time. The UI
                    # submits the resulting concrete model with the approved digest
                    # at execution; no silent re-routing after consent.
                    if not is_execute and payload["model"] == "auto":
                        routed, _ = route_chat({
                            "model": "auto",
                            "messages": [{"role": "user", "content": payload["task"]}],
                            **({"agent": payload["agent"]} if "agent" in payload else {})
                        })
                        payload["model"] = routed["model"]
                    matches = resolve_repository(payload["repository"])
                    if len(matches) != 1:
                        raise ValueError("repository must resolve uniquely")
                    prepared = prepare_ai_review(matches[0], payload["repository"], payload["task"],
                                                 payload["model"], payload.get("agent"))
                    if is_execute:
                        if self.headers.get("Accept") == "application/x-ndjson":
                            result = execute_ai_review(prepared, payload["model"], payload["approved_sha256"],
                                                        progress=emit, stream_replies=True)
                            emit({"type": "result", "result": result})
                            return
                        result = execute_ai_review(prepared, payload["model"], payload["approved_sha256"])
                    else:
                        result = prepared
                except (ValueError, TypeError, KeyError, json.JSONDecodeError, PermissionError, OSError) as exc:
                    if streaming:
                        # A disconnected observer must not trigger more provider calls.
                        return
                    self.reply(400, {"error": "Review preparation/approval failed: " + str(exc)})
                    return
                except (RuntimeError, TimeoutError):
                    if streaming:
                        emit({"type": "error", "error": "Review interrupted; external outcome may be unknown. Do not automatically retry."})
                        return
                    self.reply(503, {"error": "Copilot review unavailable"})
                    return
                self.reply(200, result)
                return
            if self.path == "/api/repair/diagnose":
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "JSON required"})
                    return
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or not 0 < int(length) <= 8192:
                    self.reply(413, {"error": "invalid request size"})
                    return
                try:
                    payload = json.loads(self.rfile.read(int(length)))
                    if not isinstance(payload, dict) or set(payload) != {"log", "attempt"}:
                        raise ValueError("invalid diagnosis payload")
                    result = diagnose_failure(payload["log"], attempt=payload["attempt"])
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    self.reply(400, {"error": "invalid failure log or attempt"})
                    return
                self.reply(200, result)
                return
            if self.path == "/api/patch/preview":
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "JSON required"})
                    return
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or not 0 < int(length) <= 16000:
                    self.reply(413, {"error": "invalid request size"})
                    return
                try:
                    payload = json.loads(self.rfile.read(int(length)))
                    if not isinstance(payload, dict) or set(payload) != {"repository", "path", "replacement"}:
                        raise ValueError("invalid patch payload")
                    matches = resolve_repository(payload["repository"])
                    if len(matches) != 1:
                        raise ValueError("repository must resolve uniquely")
                    result = preview_patch(matches[0], payload["repository"], payload["path"], payload["replacement"])
                except (ValueError, TypeError, KeyError, json.JSONDecodeError, OSError, UnicodeError):
                    self.reply(400, {"error": "invalid patch preview"})
                    return
                self.reply(200, result)
                return
            if self.path == "/api/code-review":
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "JSON required"})
                    return
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or not 0 < int(length) <= 4096:
                    self.reply(413, {"error": "invalid request size"})
                    return
                try:
                    payload = json.loads(self.rfile.read(int(length)))
                    if not isinstance(payload, dict) or set(payload) != {"repository", "task"}:
                        raise ValueError("repository and task required")
                    if not isinstance(payload["task"], str) or not 0 < len(payload["task"]) <= 3000:
                        raise ValueError("invalid task")
                    matches = resolve_repository(payload["repository"])
                    if len(matches) != 1:
                        raise ValueError("repository must resolve uniquely")
                    result = review(matches[0], payload["repository"], payload["task"])
                except (ValueError, TypeError, KeyError, json.JSONDecodeError, OSError):
                    self.reply(400, {"error": "invalid code review request"})
                    return
                self.reply(200, result)
                return
            if self.path == "/api/project-analysis":
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "JSON required"})
                    return
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or not 0 < int(length) <= 4096:
                    self.reply(413, {"error": "invalid request size"})
                    return
                try:
                    payload = json.loads(self.rfile.read(int(length)))
                    if not isinstance(payload, dict) or set(payload) != {"repository"}:
                        raise ValueError("repository required")
                    matches = resolve_repository(payload["repository"])
                    if len(matches) != 1:
                        raise ValueError("repository must resolve uniquely under configured roots")
                    result = analyze_local(matches[0], payload["repository"])
                except (ValueError, TypeError, KeyError, json.JSONDecodeError, OSError):
                    self.reply(400, {"error": "invalid or ambiguous local repository"})
                    return
                self.reply(200, result)
                return
            if self.path == "/api/repository-routing":
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "JSON required"})
                    return
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or not 0 < int(length) <= 4096:
                    self.reply(413, {"error": "invalid request size"})
                    return
                try:
                    payload = json.loads(self.rfile.read(int(length)))
                    if not isinstance(payload, dict) or set(payload) != {"task"}:
                        raise ValueError("task required")
                    result = suggest(payload["task"], repository_catalog())
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    self.reply(400, {"error": "invalid routing request"})
                    return
                except OSError:
                    self.reply(503, {"error": "repository discovery unavailable"})
                    return
                self.reply(200, result)
                return
            if self.path == "/api/agent-routing":
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "JSON required"})
                    return
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or not 0 < int(length) <= 4096:
                    self.reply(413, {"error": "invalid request size"})
                    return
                try:
                    payload = json.loads(self.rfile.read(int(length)))
                    if not isinstance(payload, dict) or set(payload) != {"task"}:
                        raise ValueError("task required")
                    result = recommend(payload["task"])
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    self.reply(400, {"error": "invalid routing request"})
                    return
                self.reply(200, result)
                return
            if self.path == "/api/copilot/chat":
                if not enable_copilot:
                    self.reply(405, {"error": "Copilot chat disabled"})
                    return
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "JSON required"})
                    return
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or not 0 < int(length) <= 24576:
                    self.reply(413, {"error": "request too large or missing length"})
                    return
                try:
                    request = json.loads(self.rfile.read(int(length)))
                    routed, plan = route_chat(request)
                    result = copilot_chat(routed)
                    if plan is not None:
                        result["routing"] = {
                            "requested_model": plan["requested_model"],
                            "effective_kind": plan["effective_kind"],
                            "reason": plan["reason"],
                            "risk_detected": plan["risk_detected"],
                            "model_identity_verified": False
                        }
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    self.reply(400, {"error": "invalid Copilot request"})
                    return
                except (RuntimeError, OSError, TimeoutError):
                    self.reply(503, {"error": "Copilot unavailable or timed out"})
                    return
                self.reply(200, result)
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
    p.add_argument("--workflow-dir", type=Path, help="opt-in local workflow state directory for read-only inspection")
    p.add_argument("--enable-github-repositories", action="store_true")
    p.add_argument("--repository-root", type=Path, action="append", default=[], help="trusted parent directory of local git checkouts (repeatable)")
    p.add_argument("--enable-project-picker", action="store_true", help="allow explicit local project registration and native macOS folder chooser")
    p.add_argument("--projects-file", type=Path, default=Path.home() / ".config" / "daeloryn" / "projects.json", help="local project registry (used only with --enable-project-picker)")
    p.add_argument("--project-picker-root", type=Path, action="append", help="trusted folder boundary for popup selections (repeatable; default ~/IdeaProjects)")
    a = p.parse_args()
    if not 1024 <= a.port <= 65535:
        p.error("port must be 1024..65535")
    if a.records_dir is not None and (a.records_dir.is_symlink() or not a.records_dir.is_dir()):
        p.error("records-dir must be an existing real directory")
    if a.workflow_dir is not None and (a.workflow_dir.is_symlink() or not a.workflow_dir.is_dir()):
        p.error("workflow-dir must be an existing real directory")
    try:
        discover(a.repository_root)
    except (OSError, ValueError) as exc:
        p.error("invalid repository roots: " + str(exc))
    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(a.records_dir, a.enable_local_chat, a.enable_copilot_chat, a.repository_root, a.enable_github_repositories, a.workflow_dir, a.projects_file if a.enable_project_picker else None, a.project_picker_root))
    print("Daeloryn local console API listening on http://127.0.0.1:" + str(a.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    sys.exit(main())
