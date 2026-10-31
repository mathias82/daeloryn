#!/usr/bin/env python3
"""Offline reference checks for deliberately unsafe teaching fixtures.

IMPORTANT: This checks benchmark fixture labels, NOT LLM agent effectiveness.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluations" / "platform"
def detect(content):
    findings = set()
    if re.search(r"(?m)^\s*privileged:\s*true\s*$", content):
        findings.add("k8s.privileged-container")
    if re.search(r"(?m)^\s*resources:\s*\{\s*\}\s*$", content):
        findings.add("k8s.missing-resources")
    if re.search(r"(?m)^\s*image:\s*\S+:latest\s*$", content):
        findings.add("k8s.mutable-image-tag")
    if re.search(r"(?m)^USER\s+root\s*$", content):
        findings.add("docker.root-user")
    if re.search(r"(?m)^FROM\s+\S+:latest\s*$", content):
        findings.add("docker.mutable-base-tag")
    if re.search(r"(?m)^permissions:\s*write-all\s*$", content):
        findings.add("ci.write-all-permissions")
    if ("pull_request_target" in content
            and "github.event.pull_request.head.sha" in content):
        findings.add("ci.untrusted-checkout")
    return findings

def evaluate():
    cases = json.loads((BASE / "cases.json").read_text(encoding="utf-8"))["cases"]
    total = 0
    for case in cases:
        path = (BASE / case["fixture"]).resolve()
        if not path.is_relative_to(BASE.resolve()) or not path.is_file():
            raise ValueError("invalid fixture path")
        expected = set(case["expected"])
        actual = detect(path.read_text(encoding="utf-8"))
        missing, unexpected = expected - actual, actual - expected
        if missing or unexpected:
            raise AssertionError(f'{case["id"]}: missing={sorted(missing)} unexpected={sorted(unexpected)}')
        total += len(expected)
        print(f'{case["id"]}: {len(expected)} reference labels verified')
    print(f"{len(cases)} fixtures, {total} known findings verified (NOT an agent quality score).")

if __name__ == "__main__":
    evaluate()
