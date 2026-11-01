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
    from copilot_chat import validate
    # Validate model, conversation and selected profile before provider discovery.
    validate(request)
    if request["model"] != "auto":
        return request, None
    messages = request["messages"]
    if not isinstance(messages, list) or not messages or not isinstance(messages[-1], dict):
        raise ValueError("invalid messages")
    last = messages[-1]
    if last.get("role") != "user" or not isinstance(last.get("content"), str):
        raise ValueError("last message must be user text")
    models = discover()
    plan = select(models, last["content"], kind="auto")
    return {**request, "model": plan["requested_model"]}, plan
