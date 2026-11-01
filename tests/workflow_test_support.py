"""Real local Git fixtures; runners and publishers never access the network."""
import subprocess
from pathlib import Path

from durable_approval_gate import DurableApprovalGate
from execution_authorization import Principal
from local_bearer_auth import LocalBearerAuthenticator
from trusted_checkout_registry import TrustedCheckoutRegistry
from workflow_evidence import publication_subject, test_subject
from workflow_orchestrator import WorkflowStore
from workflow_test_step import run_workflow_tests


class WorkflowFixture:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.root = (self.directory / "checkout").resolve()
        self.root.mkdir()
        self.git("init")
        self.git("checkout", "-b", "daeloryn/fix")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("remote", "add", "origin", "https://github.com/org/repo.git")
        (self.root / "source.txt").write_text("original\n", encoding="utf-8")
        self.git("add", "source.txt")
        self.git("commit", "-m", "fixture")
        self.commit = self.git("rev-parse", "HEAD")
        self.store = WorkflowStore(self.directory / "workflows")
        self.state = self.store.create("run1", "org/repo", "Review patch")
        self.state = self.store.transition("run1", "prepare", expected_version=0)
        self.state = self.store.transition("run1", "approve_patch", expected_version=1, approved=True)
        self.registry = TrustedCheckoutRegistry({"org/repo": self.root})
        self.gate = DurableApprovalGate(self.directory / "approvals.sqlite")
        self.principal = Principal("dev", frozenset({"org/repo"}),
                                   frozenset({"run_tests", "publish_pr"}), True)
        self.auth = LocalBearerAuthenticator({"s" * 48: self.principal})

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True,
                              text=True, check=True).stdout.strip()

    def run_tests(self, runner=None, digest=None, token=None):
        subject = test_subject(self.registry, "org/repo", "python")
        digest = digest or subject["digest"]
        token = token or self.gate.prepare("run_tests", "org/repo", digest)
        result = run_workflow_tests(
            self.store, "run1", self.state["version"], "Bearer " + "s" * 48,
            self.auth, self.registry, "python", digest, token, self.gate,
            test_runner=runner or (lambda *a, **kw: {"verified": True, "containerized": True}))
        self.state = self.store.load("run1")
        return result

    def publication(self, title="Title", body="Body"):
        subject = publication_subject(self.store, "run1", self.state["version"],
                                      self.registry, title, body, self.commit)
        token = self.gate.prepare("publish_pr", "org/repo", subject["digest"])
        return subject["digest"], token
