"""Opt-in local Ollama chat: no tools, file access, shell or remote provider keys."""
import json
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

OLLAMA = "http://127.0.0.1:11434"
MODEL = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}$")
MAX_REPLY = 65536
MAX_REQUEST = 32768


def fetch_json(path, payload=None, timeout=5):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(OLLAMA + path, data=data,
                  headers={"Content-Type": "application/json"}, method="GET" if data is None else "POST")
    with urlopen(req, timeout=timeout) as response:
        raw = response.read(MAX_REPLY + 1)
        if len(raw) > MAX_REPLY:
            raise ValueError("Ollama response exceeds limit")
        return json.loads(raw)


def installed_models():
    response = fetch_json("/api/tags")
    models = response.get("models")
    if not isinstance(models, list):
        raise ValueError("invalid Ollama model catalog")
    names = [m.get("name") for m in models if isinstance(m, dict)]
    return sorted(set(n for n in names if isinstance(n, str) and MODEL.fullmatch(n)))


def chat(request):
    if not isinstance(request, dict) or set(request) != {"model", "messages"}:
        raise ValueError("model and messages required")
    model = request["model"]
    messages = request["messages"]
    if not isinstance(model, str) or not MODEL.fullmatch(model) or model not in installed_models():
        raise ValueError("model must be installed locally")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 20:
        raise ValueError("1..20 messages required")
    safe = []
    for m in messages:
        if not isinstance(m, dict) or set(m) != {"role", "content"} or m["role"] not in ("user", "assistant"):
            raise ValueError("only user/assistant messages allowed")
        if not isinstance(m["content"], str) or not 1 <= len(m["content"]) <= 4000:
            raise ValueError("message length must be 1..4000")
        safe.append(m)
    if safe[-1]["role"] != "user":
        raise ValueError("last message must be from user")
    if len(json.dumps(safe).encode("utf-8")) > MAX_REQUEST:
        raise ValueError("conversation too large")
    result = fetch_json("/api/chat", {"model": model, "messages": safe, "stream": False,
                                     "options": {"num_predict": 1024}}, timeout=120)
    reply = result.get("message")
    if not isinstance(reply, dict) or not isinstance(reply.get("content"), str):
        raise ValueError("invalid Ollama response")
    return {"model": model, "reply": reply["content"][:16000], "provider": "ollama-local",
            "model_identity_verified": False, "agent_selected": None,
            "tools_executed": False}
