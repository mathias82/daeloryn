#!/usr/bin/env python3
"""HMAC-authenticated local approvals (experimental; not production identity).

Approvers must possess an out-of-band shared key. Tokens bind to a workflow
hash, state-file run ID, step and expiration. Never store keys in the repo.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

def key_from_env():
    raw = os.environ.get("EEA_APPROVAL_KEY", "")
    if len(raw) < 32:
        raise ValueError("EEA_APPROVAL_KEY must contain at least 32 characters")
    return raw.encode()

def sign(payload, key):
    digest = hmac.new(key, canonical(payload), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(canonical(payload)).decode().rstrip("=") + "." + base64.urlsafe_b64encode(digest).decode().rstrip("=")

def verify(token, key, expected_run, expected_hash, expected_step):
    try:
        data, mac = token.split(".")
        body = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        tag = base64.urlsafe_b64decode(mac + "=" * (-len(mac) % 4))
        if not hmac.compare_digest(hmac.new(key, body, hashlib.sha256).digest(), tag):
            raise ValueError("invalid approval signature")
        payload = json.loads(body)
    except (TypeError, UnicodeError, ValueError) as exc:
        raise ValueError("malformed or invalid approval token") from exc
    if payload.get("run_id") != expected_run or payload.get("workflow_hash") != expected_hash or payload.get("step") != expected_step:
        raise ValueError("approval token scope mismatch")
    if payload.get("action") != "approve" or not isinstance(payload.get("expires"), int) or payload["expires"] <= int(time.time()):
        raise ValueError("approval token expired or invalid")
    if not isinstance(payload.get("actor"), str) or not payload["actor"].strip():
        raise ValueError("invalid approver")
    return payload

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True, type=Path)
    p.add_argument("--step", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--ttl-seconds", type=int, default=300)
    args = p.parse_args()
    if not 1 <= args.ttl_seconds <= 900:
        p.error("ttl must be 1..900 seconds")
    from execution_engine import load
    state = load(args.state)
    if state["steps"].get(args.step) != "awaiting_approval":
        p.error("step is not awaiting approval")
    token = sign({"action":"approve", "actor":args.actor, "step":args.step,
        "run_id":state["run_id"],"workflow_hash":state["workflow_hash"],
        "expires":int(time.time())+args.ttl_seconds,"nonce":secrets.token_hex(16)},key_from_env())
    print(token)

if __name__ == "__main__":
    main()
