#!/usr/bin/env python3
"""Fail-closed adapter boundary. No real provider CLI is invoked.

Provider executors require separate security review, credential isolation,
network policy and integration tests. Never run arbitrary provider commands
from workflow JSON or untrusted agent definitions.
"""
import hashlib
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

def execute_isolated(request, image, *, enabled=False, timeout=60):
    """Opt-in offline container execution with an operator-reviewed image.

    The image entrypoint is responsible for interpreting the prompt. This method
    supplies no tokens, network, project mounts, or host credentials. It never
    completes workflow steps or grants approvals. It is not suitable for
    cloud provider API calls while the sandbox network is disabled.
    """
    validate(request)
    if not enabled:
        raise ValueError("isolated execution must be explicitly enabled")
    from sandbox_runner import run
    result = run(image, request.prompt, enabled=True, timeout=timeout)
    return {"provider": request.provider, "run_id": request.run_id, "step": request.step,
            "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
            "completed_workflow_step": False, "credentials_loaded": False}

