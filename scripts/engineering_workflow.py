"""Fail-closed engineering workflow state machine.

Explicitly separates source inspection, AI disclosure, patch review and writes.
No operation in this module executes code, sends source or writes a repository.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class Stage(str, Enum):
    INSPECTED = "inspected"
    CONTEXT_APPROVED = "context_approved"
    PROPOSAL_READY = "proposal_ready"
    PATCH_APPROVED = "patch_approved"
    TESTS_VERIFIED = "tests_verified"
    PR_READY = "pr_ready"

@dataclass(frozen=True)
class Workflow:
    repository: str
    stage: Stage = Stage.INSPECTED
    context_digest: Optional[str] = None
    patch_digest: Optional[str] = None

def advance(workflow, target, *, approval=False, digest=None, evidence=None):
    if not isinstance(workflow, Workflow) or not isinstance(target, Stage):
        raise ValueError("invalid workflow transition")
    steps = list(Stage)
    current = steps.index(workflow.stage)
    if current == len(steps) - 1 or steps[current + 1] != target:
        raise ValueError("stages must be completed in order")
    if target in (Stage.CONTEXT_APPROVED, Stage.PATCH_APPROVED) and approval is not True:
        raise PermissionError("explicit approval required")
    if target in (Stage.CONTEXT_APPROVED, Stage.PATCH_APPROVED):
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("SHA-256 digest required to bind approval to exact content")
    if target in (Stage.TESTS_VERIFIED, Stage.PR_READY):
        if not isinstance(evidence, dict) or evidence.get("verified") is not True:
            raise ValueError("verified external evidence required")
    return Workflow(workflow.repository, target,
                    digest if target == Stage.CONTEXT_APPROVED else workflow.context_digest,
                    digest if target == Stage.PATCH_APPROVED else workflow.patch_digest)

def describe(workflow):
    if not isinstance(workflow, Workflow):
        raise ValueError("invalid workflow")
    return {"repository": workflow.repository, "stage": workflow.stage.value,
            "context_digest": workflow.context_digest,
            "patch_digest": workflow.patch_digest,
            "source_transmitted": False, "patch_applied": False,
            "tests_executed": False, "pr_created": False,
            "limitations": "State-machine validation only; no AI, git, test runner or GitHub writer is connected."}
