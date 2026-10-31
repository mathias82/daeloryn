"""Planner → Developer → Reviewer → Tester → PR Creator handoff.

This is a human-operated plan; no background agents, automatic source upload,
unattended writes or sandbox are implied.
"""
from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class Step:
    agent: str
    action: str
    requires: str

STEPS: Tuple[Step,...] = (
    Step("Planner","Choose one bounded task and checkout","repository selected"),
    Step("Developer","Generate a digest-bound source diff","explicit model context approval"),
    Step("Reviewer","Inspect diff and approve exact SHA-256","human approval"),
    Step("Tester","Apply on dedicated branch and run allowlisted tests","patch approval and test execution approval"),
    Step("PR Creator","Publish manually then create draft PR","successful tests and explicit PR approval"),
)

def plan(task, repository):
    if not isinstance(task,str) or not 1<=len(task.strip())<=300:
        raise ValueError("bounded task required")
    if not isinstance(repository,str) or not repository.strip():
        raise ValueError("repository required")
    return {"repository":repository,"task":task,
            "steps":[{"agent":s.agent,"action":s.action,"requires":s.requires} for s in STEPS],
            "autonomous":False,"approval_required":True,
            "limitations":"Sequential handoff contract; no autonomous multi-agent execution or sandbox."}
