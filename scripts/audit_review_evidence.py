#!/usr/bin/env python3
"""Offline source-evidence audit for structured AI code reviews.

This validates paths, line quotations, claim structure and root-cause IDs.
It does NOT determine whether the claimed defect is semantically correct,
whether a contract is genuine or whether a test was really executed.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

LEVELS = {"STATICALLY VERIFIED", "RUNTIME REPRODUCED",
          "LIKELY", "CONTRACT-DEPENDENT"}
DISPOSITIONS = {"ACTIONABLE", "CONDITIONAL", "DISCARD"}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def audit(root, report):
    """Return a deterministic source-evidence audit; do not execute code."""
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("root must be a directory")
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("report requires schema_version=1")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError("findings must be a list")

    issues = []
    seen_ids = set()
    seen_causes = set()
    sources = {}

    def fail(fid, code, detail):
        issues.append({"finding": fid, "code": code, "detail": detail})

    def evidence(fid, entry, field):
        if not isinstance(entry, dict):
            fail(fid, "MISSING_EVIDENCE", field + " must be a source locator")
            return False
        name, line, quote = entry.get("path"), entry.get("line"), entry.get("quote")
        if not nonempty(name) or not isinstance(line, int) or isinstance(line, bool) or not nonempty(quote):
            fail(fid, "INVALID_LOCATOR", field + " requires path, integer line and nonempty quote")
            return False
        path = Path(name)
        if path.is_absolute() or any(part in ("..", ".") for part in path.parts):
            fail(fid, "UNSAFE_PATH", name)
            return False
        resolved = (root / path).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            fail(fid, "UNAVAILABLE_SOURCE", name)
            return False
        try:
            data = resolved.read_bytes()
            lines = data.decode("utf-8").splitlines()
        except (OSError, UnicodeError):
            fail(fid, "UNREADABLE_SOURCE", name)
            return False
        if line < 1 or line > len(lines):
            fail(fid, "INCORRECT_LINE", name + ":" + str(line))
            return False
        if "\n" in quote or "\r" in quote or quote.strip() not in lines[line - 1]:
            fail(fid, "QUOTE_NOT_ON_LINE", name + ":" + str(line))
            return False
        sources[path.as_posix()] = hashlib.sha256(data).hexdigest()
        return True

    for index, finding in enumerate(findings):
        fid = str(index + 1)
        if not isinstance(finding, dict):
            fail(fid, "INVALID_FINDING", "finding must be an object")
            continue
        fid = finding.get("id")
        if not nonempty(fid):
            fid = "#" + str(index + 1)
            fail(fid, "MISSING_ID", "each finding needs a nonempty id")
        if fid in seen_ids:
            fail(fid, "DUPLICATE_ID", "finding IDs must be unique")
        seen_ids.add(fid)

        disposition = finding.get("disposition")
        level = finding.get("evidence_level")
        if disposition not in DISPOSITIONS:
            fail(fid, "INVALID_DISPOSITION", "use ACTIONABLE, CONDITIONAL or DISCARD")
            continue
        if level not in LEVELS:
            fail(fid, "INVALID_LEVEL", "unsupported evidence level")
        if disposition == "ACTIONABLE" and level not in {"STATICALLY VERIFIED", "RUNTIME REPRODUCED"}:
            fail(fid, "UNSUPPORTED_ACTIONABLE", "likely or contract-dependent is not verified")
        if disposition == "CONDITIONAL" and level not in {"LIKELY", "CONTRACT-DEPENDENT"}:
            fail(fid, "INVALID_CONDITIONAL", "conditional claims must indicate uncertainty")
        if disposition == "ACTIONABLE":
            for field in ("root_cause", "invariant", "trigger", "impact", "fix", "regression"):
                if not nonempty(finding.get(field)):
                    fail(fid, "INCOMPLETE_FINDING", field + " must be evidenced or proposed")
            cause = finding.get("root_cause")
            if nonempty(cause):
                normalized = " ".join(cause.lower().split())
                if normalized in seen_causes:
                    fail(fid, "DUPLICATE_ROOT_CAUSE", "same root cause is claimed twice")
                seen_causes.add(normalized)
            evidence(fid, finding.get("source"), "source")
            basis = finding.get("invariant_basis")
            if basis not in {"SOURCE_SEMANTICS", "DOCUMENTED_CONTRACT", "OBSERVED_RUNTIME"}:
                fail(fid, "UNKNOWN_CONTRACT_BASIS", "declare how the invariant is evidenced")
            elif basis == "DOCUMENTED_CONTRACT":
                evidence(fid, finding.get("contract_evidence"), "contract_evidence")
            elif basis == "OBSERVED_RUNTIME":
                if level != "RUNTIME REPRODUCED":
                    fail(fid, "UNVERIFIED_RUNTIME_BASIS", "runtime invariant requires runtime evidence level")
            if level == "RUNTIME REPRODUCED":
                run = finding.get("runtime_evidence")
                if not isinstance(run, dict) or not all(
                    nonempty(run.get(key)) for key in ("command", "observed_output")
                ) or not isinstance(run.get("exit_code"), int):
                    fail(fid, "MISSING_RUNTIME_RECORD", "provide actual command, output and exit code")
        elif disposition == "CONDITIONAL":
            if not nonempty(finding.get("missing_evidence")):
                fail(fid, "MISSING_UNCERTAINTY", "state evidence needed to promote this claim")
            if finding.get("source") is not None:
                evidence(fid, finding["source"], "source")
        elif finding.get("source") is not None:
            evidence(fid, finding["source"], "source")

    return {
        "schema_version": 1,
        "kind": "daeloryn-source-evidence-audit",
        "result": "PASS" if not issues else "FAIL",
        "checked_findings": len(findings),
        "source_sha256": dict(sorted(sources.items())),
        "issues": issues,
        "limitations": (
            "Checks report structure and exact quoted source lines only. "
            "Does not prove semantic correctness, runtime results, production reachability, "
            "review quality, or superiority over another agent."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="project checkout")
    parser.add_argument("--report", type=Path, required=True, help="structured review JSON")
    args = parser.parse_args()
    try:
        result = audit(args.root, json.loads(args.report.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
