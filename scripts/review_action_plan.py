"""Generate explicit, non-executable remediation plans from bounded review evidence.

Plans are suggestions, never patches or executable commands.
"""
MAX_ACTIONS = 30
TEST_HINTS = {
    "java-swallowed-interrupt": "Add a cancellation regression test asserting the thread interrupt flag is restored or interruption propagates.",
    "python-shell-true": "Add tests with untrusted metacharacters and verify no shell interpretation occurs.",
    "java-system-exit": "Add a lifecycle test ensuring an application failure does not terminate the hosting process.",
}

def plan(review_result):
    if not isinstance(review_result, dict):
        raise ValueError("invalid review")
    findings = review_result.get("findings")
    if not isinstance(findings, list):
        raise ValueError("invalid findings")
    actions = []
    for finding in findings[:MAX_ACTIONS]:
        if not isinstance(finding, dict):
            raise ValueError("invalid finding")
        rule = finding.get("rule")
        path = finding.get("file")
        line = finding.get("line")
        suggestion = finding.get("suggested_fix")
        if not isinstance(rule, str) or not isinstance(path, str) or not isinstance(line, int) or line < 1 or not isinstance(suggestion, str):
            raise ValueError("invalid finding evidence")
        actions.append({"file": path, "line": line, "rule": rule,
                        "suggested_change": suggestion,
                        "regression_test": TEST_HINTS.get(rule, "Add a targeted regression test reproducing the reported condition."),
                        "status": "requires_human_review"})
    return {"actions": actions, "approval_required": True,
            "patch_generated": False, "tests_executed": False,
            "branch_created": False, "pull_request_created": False,
            "limitations": "Heuristic findings are not verified defects; inspect code and reproduce before editing."}
