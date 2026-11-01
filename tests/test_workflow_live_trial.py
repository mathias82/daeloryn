import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from workflow_live_trial import prepare, publish, configure, claim_and_publish
from reliable_container_tests import ContainerTestTimeout, SUITES
from workflow_test_support import WorkflowFixture


class LiveTrialTests(unittest.TestCase):
    def test_remote_claim_failure_prevents_push_and_pr(self):
        report={"source_revision":"a"*40,"repository":"org/repo","publication_digest":"b"*64}
        with patch("workflow_live_trial.command",side_effect=RuntimeError("claim exists or outcome unknown")) as claim:
            with patch("workflow_live_trial.publish_draft") as publisher:
                with self.assertRaises(RuntimeError):claim_and_publish(report,"checkout")
                publisher.assert_not_called()
        payload=json.loads(claim.call_args.kwargs["payload"])
        self.assertEqual("refs/tags/daeloryn-e2e-claim-"+"b"*64,payload["ref"])
        self.assertEqual("a"*40,payload["sha"])
    def setUp(self):
        self.policy = SUITES["python"]
        self.addCleanup(SUITES.__setitem__, "python", self.policy)

    def fixture(self, d, result=None):
        source = WorkflowFixture(d).root
        workspace = Path(d) / "trial"
        with patch("workflow_live_trial.shutil.which", return_value="docker"):
            with patch("workflow_live_trial.run", return_value=result or {"verified": True, "containerized": True}):
                report = prepare(workspace, "org/repo", source, "python@sha256:" + "a" * 64,
                                 approve_fixture=True, approve_tests=True)
        return workspace, report

    def test_requires_both_approvals_before_creating_workspace(self):
        with TemporaryDirectory() as d:
            workspace = Path(d) / "trial"
            for fixture, tests in ((False, True), (True, False)):
                with self.assertRaises(PermissionError):
                    prepare(workspace, "org/repo", d, "invalid", approve_fixture=fixture, approve_tests=tests)
                self.assertFalse(workspace.exists())

    def test_requires_pinned_python_image(self):
        for image in ("python:3.11-alpine", "alpine@sha256:" + "a" * 64, "python@sha256:bad"):
            with self.assertRaises(ValueError):configure(image)

    def test_durable_evidence_does_not_grant_publication_approval(self):
        with TemporaryDirectory() as d:
            workspace, report = self.fixture(d)
            self.assertEqual("passed", report["outcome"])
            self.assertEqual("not_attempted", report["publication"])
            with patch("workflow_live_trial.publish_workflow_draft") as publisher:
                with self.assertRaises(PermissionError):
                    publish(workspace, "org/repo", report["commit"], report["publication_digest"])
                publisher.assert_not_called()

    def test_wrong_commit_digest_and_repository_cannot_publish(self):
        with TemporaryDirectory() as d:
            workspace, report = self.fixture(d)
            for repo, commit, digest in (("org/other", report["commit"], report["publication_digest"]),
                                         ("org/repo", "b" * 40, report["publication_digest"]),
                                         ("org/repo", report["commit"], "b" * 64)):
                with patch("workflow_live_trial.publish_workflow_draft") as publisher:
                    with self.assertRaises(PermissionError):publish(workspace, repo, commit, digest, approved=True)
                    publisher.assert_not_called()

    def test_failed_tests_do_not_offer_publication_digest(self):
        with TemporaryDirectory() as d:
            workspace, report = self.fixture(d, {"verified": False, "containerized": True})
            self.assertEqual("failed", report["outcome"])
            self.assertNotIn("publication_digest", report)
            with self.assertRaises(RuntimeError):publish(workspace, "org/repo", report["commit"], "a" * 64, approved=True)

    def test_cleanup_failure_remains_unknown_after_restart(self):
        with TemporaryDirectory() as d:
            source = WorkflowFixture(d).root
            workspace = Path(d) / "trial"
            with patch("workflow_live_trial.shutil.which", return_value="docker"):
                with patch("workflow_live_trial.run", side_effect=ContainerTestTimeout("container", False)):
                    with self.assertRaises(ContainerTestTimeout):
                        prepare(workspace, "org/repo", source, "python@sha256:" + "a" * 64,
                                approve_fixture=True, approve_tests=True)
            report = json.loads((workspace / "report.json").read_text())
            self.assertEqual("unknown", report["outcome"])
            self.assertFalse(report["cleanup_verified"])
            self.assertEqual("tests_running", report["stage"])


if __name__ == "__main__":unittest.main()
