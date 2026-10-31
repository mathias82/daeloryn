#!/usr/bin/env python3
"""Fail-closed adapter boundary. No real provider CLI is invoked.

Provider executors require separate security review, credential isolation,
network policy and integration tests. Never run arbitrary provider commands
from workflow JSON or untrusted agent definitions.
"""
import json
from dataclasses import dataclass

SUPPORTED = frozenset({"codex","claude","copilot","gemini"})

@dataclass(frozen=True)
class Invocation:
    provider: str
    agent: str
    run_id: str
    step: str
    prompt: str

def validate(request):
    if not isinstance(request, Invocation):
        raise TypeError("Invocation required")
    if request.provider not in SUPPORTED:
        raise ValueError("unknown provider")
    if not all(isinstance(x,str) and x.strip() for x in (request.agent,request.run_id,request.step,request.prompt)):
        raise ValueError("missing invocation data")
    if len(request.prompt.encode("utf-8"))>65536:
        raise ValueError("prompt size limit exceeded")
    return request

def prepare(request):
    request=validate(request)
    return {"mode":"dry-run","provider":request.provider,"agent":request.agent,
        "run_id":request.run_id,"step":request.step,"prompt_sha256":__import__("hashlib").sha256(request.prompt.encode()).hexdigest(),
        "provider_invoked":False,"credentials_loaded":False}

def execute(request):
    validate(request)
    raise RuntimeError("provider execution disabled pending reviewed adapters and sandboxed integration tests")
