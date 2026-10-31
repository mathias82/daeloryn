"""Opt-in live Copilot catalog and fail-closed per-request model routing.

Discovery requires the optional Copilot SDK and an authenticated installed CLI.
No guessed model IDs, no fallback to an unverified model and no automatic retry.
"""
import asyncio
import shutil
from model_router import discover_copilot, select

def available_models():
    executable = shutil.which("copilot")
    if not executable:
        raise RuntimeError("Copilot CLI not installed")
    return asyncio.run(discover_copilot(executable))

def route_chat(request, discover=available_models):
    if not isinstance(request, dict) or set(request) != {"model", "messages"}:
        raise ValueError("model and messages required")
    if request["model"] != "auto":
        return request, None
    messages = request["messages"]
    if not isinstance(messages, list) or not messages or not isinstance(messages[-1], dict):
        raise ValueError("invalid messages")
    last = messages[-1]
    if last.get("role") != "user" or not isinstance(last.get("content"), str):
        raise ValueError("last message must be user text")
    # Validate all input before any potentially expensive provider discovery.
    from copilot_chat import validate
    validate({"model": "auto", "messages": messages})
    models = discover()
    plan = select(models, last["content"], kind="auto")
    return {"model": plan["requested_model"], "messages": messages}, plan
