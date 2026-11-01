"""Operator-only, two-invocation Docker -> Draft PR trial on a disposable branch.

Tests do not push. Publication requires an explicit approval digest and commit from
that completed trial. Keep the workspace private; it is trusted local state.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import uuid

from durable_approval_gate import DurableApprovalGate
from execution_authorization import Principal
from local_bearer_auth import LocalBearerAuthenticator
from reliable_container_tests import SUITES, run, ContainerTestTimeout
from trusted_checkout_registry import TrustedCheckoutRegistry
from workflow_draft_publication import publish_workflow_draft
from approved_pr_publish import publish as publish_draft
from workflow_evidence import publication_subject, test_subject, REPOSITORY, SHA
from workflow_orchestrator import WorkflowStore
from workflow_test_step import run_workflow_tests

IMAGE = re.compile(r"(?:docker.io/library/)?python@sha256:[0-9a-f]{64}\Z")
PROBE = '''import os
import socket
import unittest
from pathlib import Path

class ContainerProbe(unittest.TestCase):
 def test_isolation_and_writable_workspace(self):
  self.assertEqual(65534,os.getuid())
  self.assertNotIn("GH_TOKEN",os.environ)
  Path("scratch.txt").write_text("container-only")
  with self.assertRaises(OSError):Path("/source/host-write.txt").write_text("forbidden")
  with self.assertRaises(OSError):Path("/rootfs-write.txt").write_text("forbidden")
  with socket.socket() as connection:
   connection.settimeout(0.2)
   with self.assertRaises(OSError):connection.connect(("198.51.100.1",443))
'''


def command(args, cwd=None, payload=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            timeout=90, check=False, input=payload)
    if result.returncode:
        # Do not expose credential-helper or arbitrary Git hook output.
        raise RuntimeError("external command failed: " + args[0])
    return result.stdout.strip()


def save(workspace, report):
    target = workspace / "report.json"
    if target.is_symlink():
        raise ValueError("symlink report")
    temp = workspace / "report.tmp"
    with temp.open("x", encoding="utf-8") as handle:
        os.chmod(temp, 0o600)
        json.dump(report, handle, sort_keys=True, indent=2)
    temp.replace(target)


def load(workspace, repository):
    target = workspace / "report.json"
    if target.is_symlink():
        raise ValueError("symlink report")
    report = json.loads(target.read_text(encoding="utf-8"))
    if report.get("repository") != repository or not IMAGE.fullmatch(report.get("image", "")):
        raise PermissionError("trial repository or image mismatch")
    return report


def configure(image):
    if not isinstance(image, str) or not IMAGE.fullmatch(image):
        raise ValueError("pre-pulled Python image digest required")
    # Fixed probe command only; no user-provided shell command or suite injection.
    SUITES["python"] = (image, ["python", "-m", "unittest", "discover", "-s", ".daeloryn-e2e-tests"])


def services(workspace, repository):
    registry = TrustedCheckoutRegistry({repository: workspace / "checkout"})
    principal = Principal("trial-operator", frozenset({repository}),
                          frozenset({"run_tests", "publish_pr"}), True)
    return WorkflowStore(workspace / "state"), registry, principal, DurableApprovalGate(workspace / "approvals.sqlite")


def prepare(workspace, repository, source, image, *, approve_fixture=False,
            approve_tests=False, scenario="pass", timeout=60):
    if approve_fixture is not True or approve_tests is not True:
        raise PermissionError("separate fixture and test approvals required")
    if not REPOSITORY.fullmatch(repository) or scenario not in ("pass", "fail", "timeout") or not 1<=timeout<=300:
        raise ValueError("invalid trial inputs")
    configure(image)
    if not shutil.which("docker"):
        raise RuntimeError("Docker required; no host fallback")
    workspace = Path(workspace).absolute()
    if workspace.exists() or workspace.is_symlink():
        raise FileExistsError("use a fresh private workspace; trials are never automatically retried")
    workspace.mkdir(mode=0o700, parents=True)
    workspace = workspace.resolve(strict=True)
    root = workspace / "checkout"
    # Clone only an operator-selected checkout. --no-hardlinks makes the artifact
    # self-contained. Credentials/hooks from its working tree are not installed.
    command(["git", "clone", "--no-hardlinks", str(Path(source).resolve(strict=True)), str(root)])
    source_revision = command(["git", "rev-parse", "HEAD"], root)
    branch = "daeloryn/e2e-" + uuid.uuid4().hex[:16]
    command(["git", "checkout", "-b", branch], root)
    command(["git", "remote", "set-url", "origin", "https://github.com/" + repository + ".git"], root)
    probe = root / ".daeloryn-e2e-tests"
    probe.mkdir()
    code = PROBE
    if scenario == "fail":
        code += '\n def test_deliberate_failure(self):self.fail("expected negative control")\n'
    if scenario == "timeout":
        code += '\n def test_timeout(self):\n  import time\n  time.sleep(60)\n'
    (probe / "test_probe.py").write_text(code, encoding="utf-8")
    command(["git", "add", ".daeloryn-e2e-tests/test_probe.py"], root)
    command(["git", "-c", "user.name=Daeloryn E2E", "-c", "user.email=e2e@example.invalid",
             "-c", "commit.gpgsign=false", "commit", "-m", "test: disposable Daeloryn workflow probe"], root)
    commit = command(["git", "rev-parse", "HEAD"], root)
    report = {"schema_version": 1, "repository": repository, "commit": commit,
              "source_revision": source_revision,
              "branch": branch, "image": image, "scenario": scenario,
              "outcome": "not_executed", "publication": "not_attempted"}
    save(workspace, report)
    store, registry, principal, gate = services(workspace, repository)
    store.create("trial", repository, "Disposable Docker-to-Draft-PR trial")
    store.transition("trial", "prepare", expected_version=0)
    state = store.transition("trial", "approve_patch", expected_version=1, approved=True)
    bearer = secrets.token_urlsafe(48)
    auth = LocalBearerAuthenticator({bearer: principal})
    subject = test_subject(registry, repository, "python")
    token = gate.prepare("run_tests", repository, subject["digest"])
    try:
        result = run_workflow_tests(store, "trial", state["version"], "Bearer " + bearer,
                                    auth, registry, "python", subject["digest"], token, gate,
                                    test_runner=lambda checkout, suite, **kw: run(checkout, suite, timeout=timeout, **kw))
    except ContainerTestTimeout as exc:
        report.update(outcome="unknown", cleanup_verified=exc.cleanup_verified,
                      container_name=exc.container_name, stage=store.load("trial")["stage"])
        save(workspace, report)
        raise
    except Exception:
        report.update(outcome="unknown", stage=store.load("trial")["stage"])
        save(workspace, report)
        raise
    report.update(outcome="passed" if result["passed"] else "failed",
                  stage=store.load("trial")["stage"], tests=result["tests"])
    if result["passed"]:
        subject = publication_subject(store, "trial", result["workflow"]["version"],
                                      registry, title(report), body(report), commit)
        report["publication_digest"] = subject["digest"]
    save(workspace, report)
    return report


def title(report):
    return "[Daeloryn E2E] disposable workflow trial " + report["branch"].split("/")[-1]


def body(report):
    return ("Disposable integration trial; do not merge.\n\n"
            "Tested commit: " + report["commit"] + "\n"
            "Container image: " + report["image"] + "\n"
            "Close this Draft PR and delete its trial branch after verification.")


def claim_and_publish(report, *args, **kwargs):
    # GitHub atomically rejects creation of an existing ref. This durable claim
    # survives restoring an older tests artifact or losing a runner workspace.
    # Never delete it automatically: a preceding push/PR outcome may be unknown.
    revision = report.get("source_revision")
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise PermissionError("trusted source revision required")
    claim = "refs/tags/daeloryn-e2e-claim-" + report["publication_digest"]
    command(["gh", "api", "--method", "POST", "repos/" + report["repository"] + "/git/refs",
             "--input", "-"], payload=json.dumps({"ref": claim, "sha": revision}))
    return publish_draft(*args, **kwargs)


def publish(workspace, repository, expected_commit, approval_digest, *, approved=False):
    if approved is not True:
        raise PermissionError("separate explicit publication approval required")
    workspace = Path(workspace).resolve(strict=True)
    report = load(workspace, repository)
    configure(report["image"])
    if not isinstance(expected_commit, str) or not SHA.fullmatch(expected_commit) or expected_commit != report["commit"]:
        raise PermissionError("exact trial commit approval required")
    store, registry, principal, gate = services(workspace, repository)
    state = store.load("trial")
    subject = publication_subject(store, "trial", state["version"], registry,
                                  title(report), body(report), expected_commit)
    if approval_digest != subject["digest"] or approval_digest != report.get("publication_digest"):
        raise PermissionError("exact trial publication digest required")
    if not shutil.which("gh"):
        raise RuntimeError("authenticated GitHub CLI required")
    token = gate.prepare("publish_pr", repository, approval_digest)
    try:
        result = publish_workflow_draft(store, "trial", state["version"], principal,
                                        registry, approval_digest, token, gate,
                                        title(report), body(report), expected_commit,
                                        publisher=lambda *a, **kw: claim_and_publish(report, *a, **kw))
    except Exception:
        report.update(publication="unknown", stage=store.load("trial")["stage"])
        save(workspace, report)
        raise
    report.update(publication="created", stage=result["workflow"]["stage"],
                  draft_pr=result["publication"])
    save(workspace, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("tests", "publish"))
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-checkout", default=".")
    parser.add_argument("--image")
    parser.add_argument("--scenario", choices=("pass", "fail", "timeout"), default="pass")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--approve-fixture", action="store_true")
    parser.add_argument("--approve-tests", action="store_true")
    parser.add_argument("--approve-publication", action="store_true")
    parser.add_argument("--expected-commit")
    parser.add_argument("--approval-digest")
    args = parser.parse_args()
    try:
        if args.phase == "tests":
            result = prepare(args.workspace, args.repository, args.source_checkout, args.image,
                             approve_fixture=args.approve_fixture, approve_tests=args.approve_tests,
                             scenario=args.scenario, timeout=args.timeout)
        else:
            result = publish(args.workspace, args.repository, args.expected_commit,
                             args.approval_digest, approved=args.approve_publication)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0 if result["outcome"] == "passed" else 1
    except (OSError, ValueError, PermissionError, RuntimeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
