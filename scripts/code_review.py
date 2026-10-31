"""Deterministic evidence-backed local source review; no code execution or edits."""
import re
from code_context import scan
from architecture_inventory import inventory
from review_action_plan import plan
from agent_router import recommend

RULES = (
 ("java-swallowed-interrupt", "medium", re.compile(r"catch\s*\(\s*InterruptedException\b[^)]*\)\s*\{\s*\}", re.S),
  "Empty InterruptedException catch may swallow cancellation",
  "Restore interrupt status or propagate interruption"),
 ("python-shell-true", "high", re.compile(r"subprocess\.(?:run|Popen|call|check_output)\s*\([^\n]*shell\s*=\s*True"),
  "Shell execution requires review of command input",
  "Use an argument array with shell=False where possible"),
 ("java-system-exit", "medium", re.compile(r"System\.exit\s*\("),
  "Process termination from application code may disrupt services",
  "Prefer structured exception propagation and lifecycle management"),
)

def review(root, repository, task):
    context = scan(root, repository)
    findings = []
    for file in context["files"]:
        for rule, severity, pattern, message, remedy in RULES:
            for match in list(pattern.finditer(file["excerpt"]))[:20]:
                line = file["excerpt"].count("\n", 0, match.start()) + 1
                findings.append({"rule": rule, "severity": severity,
                                 "file": file["path"], "line": line,
                                 "evidence": message, "suggested_fix": remedy,
                                 "confidence": "pattern-match"})
    result = {"repository": repository, "findings": findings[:100],
            "architecture": inventory(context),
            "agent_recommendation": recommend(task),
            "source_files_scanned": context["files_read"],
            "skipped": context["skipped"],
            "execution": "not_run", "changes_made": False,
            "limitations": "Pattern matches are review leads, not verified defects; no tests executed"}
    result["remediation_plan"] = plan(result)
    return result
