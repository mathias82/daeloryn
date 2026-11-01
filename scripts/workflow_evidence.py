"""Local, deterministic approval subjects. Not a remote CI attestation.

Only operator-owned checkout registries, workflow stores and runners are trusted.
The subject binds approvals to GitHub destination, exact Git inputs and test policy.
"""
import hashlib
import json
import re
import subprocess

from reliable_container_tests import SUITES
from engineering_executor import BRANCH

SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


def digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def git(checkout, *args):
    result = subprocess.run(["git", *args], cwd=checkout, capture_output=True,
                            text=True, timeout=20, check=False)
    if result.returncode:
        raise PermissionError("unable to verify checkout: " + args[0])
    return result.stdout.strip()


def snapshot(registry, repository):
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
        raise PermissionError("GitHub owner/repository identifier required")
    root = registry.resolve(repository)
    # Ignored inputs are copied into the container too. Reject them rather than
    # treating a clean tracked tree as evidence for untracked test/build inputs.
    if git(root, "status", "--porcelain", "--untracked-files=all", "--ignored"):
        raise PermissionError("tests require a clean checkout without ignored inputs")
    commit = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    branch = git(root, "branch", "--show-current")
    if not SHA.fullmatch(commit) or not SHA.fullmatch(tree) or not BRANCH.fullmatch(branch):
        raise PermissionError("committed dedicated daeloryn branch required")
    # Push URLs override fetch URLs; multiple push destinations are not allowed.
    urls = git(root, "remote", "get-url", "--push", "--all", "origin").splitlines()
    accepted = {"https://github.com/" + repository,
                "https://github.com/" + repository + ".git",
                "git@github.com:" + repository,
                "git@github.com:" + repository + ".git"}
    if len(urls) != 1 or urls[0] not in accepted:
        raise PermissionError("origin push destination differs from authorized repository")
    # An explicit refspec is used by the publisher. Mirror mode could still
    # override its semantics, so fail closed on that repository configuration.
    config = subprocess.run(["git", "config", "--bool", "--get", "remote.origin.mirror"],
                            cwd=root, capture_output=True, text=True, timeout=20,
                            check=False)
    if config.returncode not in (0, 1) or config.stdout.strip() not in ("", "false"):
        raise PermissionError("mirror publication is not allowed")
    return {"repository": repository, "checkout": str(root), "commit": commit,
            "tree": tree, "branch": branch, "push_url": urls[0]}


def test_subject(registry, repository, suite):
    if not isinstance(suite, str) or suite not in SUITES:
        raise ValueError("unsupported test suite")
    subject = {"schema_version": 1, "snapshot": snapshot(registry, repository),
               "suite": suite, "suite_config_sha256": digest(SUITES[suite])}
    return {**subject, "digest": digest(subject)}


def publication_subject(store, workflow_id, expected_version, registry,
                        title, body, expected_commit):
    state = store.load(workflow_id)
    if state["version"] != expected_version or state["stage"] != "tests_passed":
        raise RuntimeError("verified tests required before publication")
    evidence = state.get("test_evidence")
    if not isinstance(evidence, dict) or evidence.get("verified") is not True:
        raise PermissionError("bound test evidence required; rerun approved tests")
    current = test_subject(registry, state["repository"], evidence.get("suite"))
    result_digest = evidence.get("result_sha256")
    if (evidence.get("subject") != current or not isinstance(result_digest, str)
            or not DIGEST.fullmatch(result_digest)):
        raise PermissionError("checkout or test policy differs from tested inputs")
    if expected_commit != current["snapshot"]["commit"]:
        raise PermissionError("publication must use the exact tested commit")
    if not isinstance(title, str) or not 1 <= len(title) <= 120:
        raise ValueError("invalid PR title")
    if not isinstance(body, str) or len(body) > 4000:
        raise ValueError("invalid PR body")
    subject = {"schema_version": 1, "action": "publish_pr", "workflow_id": workflow_id,
               "version": expected_version, "repository": state["repository"],
               "test_evidence_sha256": digest(evidence), "title": title, "body": body}
    return {**subject, "digest": digest(subject)}
