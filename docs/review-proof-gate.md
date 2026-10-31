# Daeloryn Evidence-Gated Review — opt-in verification

The differentiator is **an external, deterministic quality gate** coupled to the 22 agent specialties—not just longer review prompts. GitHub Copilot itself also supports agents, skills, hooks and subagents; Daeloryn does **not** claim to have invented those capabilities.

## 1. Run a source-grounded review

Choose a custom Daeloryn agent and ask it to inspect the *real* project, verify compiler/framework versions, and distinguish observed defects from contract choices. Keep the source and benchmark's gold answers separate.

The agent should check relevant failure outcomes, including a **timeout after a possible side effect**, a downstream failure after an upstream success, concurrent duplicates and interrupted compensation. It must not invent these cases if the source has no such path.

## 2. Request a structured review artifact

Ask the agent to save a **separate JSON review report** (only when file creation is authorized) using this schema. A normal prose review can also be delivered; the audit is optional. The example below is a hypothetical project, not a claim about any real source file:

```json
{
  "schema_version": 1,
  "findings": [
    {
      "id": "F1",
      "disposition": "ACTIONABLE",
      "evidence_level": "STATICALLY VERIFIED",
      "source": {
        "path": "src/Example.java",
        "line": 12,
        "quote": "int total = current + delta;"
      },
      "root_cause": "unchecked total increment",
      "invariant": "the total must not wrap",
      "invariant_basis": "DOCUMENTED_CONTRACT",
      "contract_evidence": {
        "path": "README.md",
        "line": 7,
        "quote": "The total must not wrap."
      },
      "trigger": "the sum exceeds the signed int range",
      "impact": "the total can become negative",
      "fix": "check the range or use Math.addExact",
      "regression": "assert overflow is rejected and leaves total unchanged"
    },
    {
      "id": "C1",
      "disposition": "CONDITIONAL",
      "evidence_level": "CONTRACT-DEPENDENT",
      "missing_evidence": "whether null identifiers are supported by the public API"
    }
  ]
}
```

Use `invariant_basis` of `SOURCE_SEMANTICS`, `DOCUMENTED_CONTRACT`, or `OBSERVED_RUNTIME` based on actual evidence. A documented contract needs a second verified file/line/quote. `RUNTIME REPRODUCED` also requires a recorded `runtime_evidence` object containing a genuine command, exit code and observed output. These fields remain **self-reported**, not independently authenticated.

## 3. Audit source citations and duplicate root causes

Run this **outside** the model's analysis, using your copy of Daeloryn and the reviewed source checkout:

```bash
python3 /path/to/daeloryn/scripts/audit_review_evidence.py \\
  --root /path/to/reviewed/project \\
  --report /path/to/review-report.json
```

The command prints `PASS` or `FAIL`, exact source SHA-256 hashes and finding-specific errors; a failing report exits nonzero. Fix an incorrect line or missing contract citation before accepting the report.

**The audit does not prove semantic causality, security exploitability, that a build ran, or that a proposed patch works.** It rejects structural errors and mismatched actual source lines. A passing audit is **not** a quality score.

### Pin the reviewed source revision

For CI or later re-audits, add a top-level `source_sha256` object to the review report. Map every cited source and contract path to its lowercase SHA-256 digest, calculated from the **raw file bytes at review time**. Use canonical project-relative paths, for example `src/Example.java`. The audit output already contains this mapping for successfully located evidence; retain it only after verifying that this is the revision actually reviewed. Do not refresh hashes just to make a stale review pass.

```bash
python3 /path/to/daeloryn/scripts/audit_review_evidence.py \
  --root /path/to/reviewed/project \
  --report /path/to/review-report.json \
  --require-source-hashes
```

Strict mode rejects a missing manifest. When a manifest is supplied, both modes reject missing cited hashes, mismatches and unused entries. Even a change outside a quoted line invalidates that file's pinned digest. Reports without a manifest remain supported in the default mode. Each resolved file is read once per audit so repeated citations use the same bytes.

Digests detect revision mismatches; they do not authenticate the reviewer, establish when a review occurred, or prove its conclusions. Run against a stable checkout: this is not an atomic snapshot of a directory being concurrently modified. Runtime commands and exit codes are still self-reported, and this tool never executes report content. Malformed enum values are rejected as audit issues; invalid report-level schema or hash manifests produce a CLI usage error.

## 4. Prove the fix against failures, not just happy paths

For each verified root cause, require these checks when applicable:

- **Expected success / negative control:** existing correct code stays unflagged and still works.
- **Invalid and boundary inputs:** mutation does not occur on rejection; arithmetic and serialization constraints are respected.
- **Concurrency and retries:** simultaneous calls, duplicate request IDs, idempotency keys, lost responses.
- **Partial success:** remote effect succeeded, local persistence failed; compensation failed; retry after unknown outcome.
- **Runtime and compatibility:** actual compiler target, framework/tool versions and executable regression tests.
- **Independent verdict:** compare the completed implementation on new unseen cases, not the same fixture used while tuning the agents.

Report **not run** when any proposed test was not executed. Keep the verifier's output and test logs outside the model-visible benchmark folders. Use the existing benchmark recording process described in [benchmark protocol](benchmark-protocol.md) for blinded comparisons.

## Limits and positioning

Copilot already supports custom agents, Agent Skills, MCP tools, hooks and code-review agents. Daeloryn's aim is an **opinionated, portable, source-grounded review protocol** paired with an external evidence audit and controlled cross-provider measurement. Those checks can themselves be used *with* Copilot; they are not features exclusively unavailable in Copilot. Actual superiority must be demonstrated, not asserted.
