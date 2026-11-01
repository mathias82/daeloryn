"""Deterministic, offline source-reference evaluator for paired review observations.

A reference matching a source line is evidence of *traceability*, not evidence
that a reported defect exists. Does not call a provider, run tests or attest
model identity. Refuses to invent an independently verified winner.
"""
import hashlib
import json
import re

from project_review_context import SOURCE_EXTENSIONS

CODE_SUFFIXES = {".java", ".kt", ".py", ".ts", ".tsx", ".js", ".jsx", ".go"}
MAX_REFERENCES = 300
MAX_FINDINGS = 35
ARM_NAMES = ("baseline", "daeloryn")


def source_from_prepared(prepared):
    """Extract path/line ranges from already approved in-memory JSON blocks."""
    result = {}
    for prompt in prepared["baseline"]["prompts"]:
        for line in prompt.splitlines():
            if not line.startswith('{"file":'):
                continue
            try:
                block = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(block, dict):
                continue
            path, start, end, source = (block.get(key) for key in
                                        ("file", "line", "end_line", "source"))
            if (not isinstance(path, str) or not path or
                not isinstance(start, int) or isinstance(start, bool) or start < 1 or
                not isinstance(end, int) or end < start or
                not isinstance(source, str)):
                continue
            result.setdefault(path, set()).update(range(start, min(end, start + 3000) + 1))
    return result


def source_from_context(context):
    """Only use independently re-read source after its original SHA is verified."""
    result = {}
    for file in context["files"]:
        text = file["source"]
        result[file["path"]] = set(range(1, len(text.splitlines()) + 1))
    return result


def context_digest(context):
    data = {
        "files": [{"path": f["path"], "source": f["source"]} for f in context["files"]],
        "omitted": context["omitted"], "excluded": context["excluded"],
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _citations(reply, source):
    # Source filename aliases only when unique: two Foo.java paths must never
    # silently resolve the same basename to an arbitrary class.
    aliases = {}
    for name in source:
        aliases.setdefault(name, set()).add(name)
        basename = name.rsplit("/", 1)[-1]
        aliases.setdefault(basename, set()).add(name)
    candidates = sorted(aliases, key=lambda x: (-len(x), x))
    # Exact path references have priority over a basename inside the same span.
    claimed, spans = [], []
    for alias in candidates:
        escaped = re.escape(alias)
        pattern = re.compile(
            r"(?<![\w./-])" + escaped +
            r"(?:\s*[:#]\s*L?|\s+[Ll]ines?\s+)(\d{1,6})(?:\s*[-–]\s*(\d{1,6}))?",
            re.IGNORECASE)
        for match in pattern.finditer(reply):
            if any(match.start() >= begin and match.end() <= end for begin, end in spans):
                continue
            matches = aliases[alias]
            line = int(match.group(1))
            if not matches or len(matches) != 1:
                claimed.append({"file": alias, "line": line, "status": "ambiguous_filename"})
            else:
                path = next(iter(matches))
                valid = line in source[path]
                claimed.append({"file": path, "line": line,
                                "status": "source_line_found" if valid else "line_not_in_snapshot",
                                "source_kind": "code" if "." + path.rsplit(".", 1)[-1].lower() in CODE_SUFFIXES else "other"})
            spans.append(match.span())
            if len(claimed) >= MAX_REFERENCES:
                break
        if len(claimed) >= MAX_REFERENCES:
            break
    return claimed


def _assess(reply, source):
    refs = _citations(reply, source)
    unique_valid = {(r["file"], r["line"]) for r in refs
                    if r["status"] == "source_line_found"}
    code_valid = {(r["file"], r["line"]) for r in refs
                  if r["status"] == "source_line_found" and r.get("source_kind") == "code"}
    invalid = [r for r in refs if r["status"] != "source_line_found"]
    # This measures discoverable, grounded *locations*, never defect truth.
    points = max(0, min(100, len(code_valid) * 12 - len(invalid) * 8))
    return {
        "evidence_traceability_score": points,
        "cited_references": len(refs),
        "source_matched_references": sum(r["status"] == "source_line_found" for r in refs),
        "unique_matched_locations": len(unique_valid),
        "unique_code_locations": len(code_valid),
        "unsupported_references": len(invalid),
        "duplicate_matched_citations": sum(r["status"] == "source_line_found" for r in refs) - len(unique_valid),
        "citation_precision_percent": round(100 * (len(refs) - len(invalid)) / len(refs), 1) if refs else None,
        "references": refs[:MAX_FINDINGS],
    }


def evaluate(record, source):
    if not isinstance(record, dict) or not isinstance(source, dict):
        raise ValueError("invalid paired benchmark evidence")
    arms = record.get("arms")
    if not isinstance(arms, dict) or not all(isinstance(arms.get(a), dict) for a in ARM_NAMES):
        raise ValueError("both persisted A/B arms required")
    data = {}
    for arm in ARM_NAMES:
        row = arms[arm]
        # Prefer full per-batch receipts: they preserve all responses even if
        # the aggregate reply was truncated for local storage.
        batches = row.get("batches")
        if isinstance(batches, dict) and batches:
            ordered = sorted(((int(key), item) for key, item in batches.items()
                              if key.isdecimal() and isinstance(item, dict) and
                              item.get("status") == "completed" and isinstance(item.get("reply"), str)),
                             key=lambda item: item[0])
            reply = "\n".join(item["reply"] for _, item in ordered)
        else:
            reply = row.get("reply") or row.get("review", {}).get("reply") or ""
        if not isinstance(reply, str):
            reply = ""
        data[arm] = _assess(reply[:500000], source)
    comparable = (record.get("status") == "completed" and
                  all(arms[a].get("status") == "completed" for a in ARM_NAMES) and
                  all(arms[a].get("completed_batches") == arms[a].get("total_batches")
                      and isinstance(arms[a].get("total_batches"), int)
                      and arms[a]["total_batches"] > 0 for a in ARM_NAMES))
    b, d = data["baseline"], data["daeloryn"]
    gap = d["evidence_traceability_score"] - b["evidence_traceability_score"]
    if not comparable:
        lead, status = "not_comparable", "partial_or_incomplete"
    elif not b["cited_references"] and not d["cited_references"]:
        lead, status = "inconclusive", "no_source_citations"
    elif not (b["unique_code_locations"] or d["unique_code_locations"]):
        lead, status = "inconclusive", "no_grounded_code_locations"
    elif gap >= 12:
        lead, status = "daeloryn", "provisional_traceability"
    elif gap <= -12:
        lead, status = "baseline", "provisional_traceability"
    elif gap == 0:
        lead, status = "tie", "provisional_traceability"
    else:
        lead, status = "inconclusive", "small_score_difference"
    return {
        "kind": "paired-source-evidence-comparison",
        "schema_version": 1,
        "method": "offline-source-line-grounding",
        "status": status,
        "comparable_completed_arms": comparable,
        "source_sha256": record.get("source_sha256"),
        "provisional_evidence_lead": lead,
        "verified_winner": None,
        "independent_checks_executed": False,
        "model_identity_verified": False,
        "agent_selection_verified": False,
        "score_definition": "12 points per unique source-grounded code location minus 8 per unsupported citation; bounded 0–100. Measures citation traceability ONLY, not defect correctness.",
        "source_files_inspected": len(source),
        "arms": data,
        "warning": "A cited line existing in source DOES NOT establish a bug, fix quality, or a confirmed winner. Model identity, selected agent and independent regression tests were not verified. Manual blind adjudication required.",
    }
