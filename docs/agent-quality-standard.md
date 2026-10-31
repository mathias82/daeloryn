# Quality and evidence standard for all 22 agents

**Scope:** 4 Java, 6 Spring, 4 React, 6 Platform and 2 Shared agents. This document describes the common instruction contract; it is not a claim that any host or LLM obeys it at runtime.

## Requirements

Each agent must:
- Locate the exact requested file or configuration and verify the real source line map before claiming `path:line`; never invent line references or use gold labels as evidence.
- Distinguish **STATICALLY VERIFIED** (supported by inspected source), **RUNTIME REPRODUCED** (an actual executed reproducer), **LIKELY** (missing context) and **CONTRACT-DEPENDENT** (business/API assumptions).
- Group multiple consequences of one cause rather than inflate the finding count; keep different root causes separate.
- Explain severity from concrete impact and reachability. Treat lifecycle decisions, input validation policy and optional hardening as contract-dependent unless the relevant contract is documented.
- Recommend the smallest complete, version-aware fix, including exception paths, concurrency boundaries and rollback where appropriate.
- End with **Verification actually performed** and **Not verified / contract questions**. Never invent a passing test, performance improvement, security exploit, or production diagnosis.

The specialized rules in the files under `agents/java/`, `agents/spring/`, `agents/react/`, `agents/platform/` and `agents/shared/` remain authoritative for framework-specific behavior. The `java-reviewer` has a more detailed equivalent review accuracy protocol.

## Offline regression coverage

```bash
python3 scripts/agents.py validate
python3 -m unittest discover -s tests -v
```

The tests include `tests/test_all_agent_quality.py` to check the common rules in **22 canonical definitions** and in their **88 generated adapters** (Codex, Claude, Copilot and Gemini). `tests/test_java_reviewer_quality.py` additionally checks detailed Java-review requirements. The tests prove packaging/text consistency only, **not AI adherence or benchmark performance**.

## Updating an existing installation

Inspect a diff, then deliberately apply the updated definitions (the installer refuses to overwrite by default):

```bash
python3 scripts/agents.py install --target /path/to/project --module all --tool copilot --diff
python3 scripts/agents.py install --target /path/to/project --module all --tool copilot --force
```

Do not auto-overwrite developer-customized agent files without backup and review. This command only updates definitions; restart or reselect the custom agent in the host and verify the correct workspace was loaded.

## Benchmarks and release claims

Existing `Java25Worker.java` and `Java25Ledger.java` were used during agent tuning and are **development fixtures**, not unseen evaluation sets. Create fresh, blinded, isolated holdout cases before claiming improvement. See [benchmark protocol](benchmark-protocol.md). Neither a larger number of reported findings nor passing static tests alone proves better precision, recall, security or usability.

## Concrete examples and supported versions

All 22 canonical agents include at least one fenced, role-specific code/configuration example (Java, SQL, TSX, GitHub Actions, Dockerfile, Kubernetes YAML or PromQL). These are illustrative examples, not assertions about the user's repository.

Before proposing an implementation, inspect the project's actual compiler target, framework dependencies, CI and runtime. **Java 8 remains supported:** Java 8/Spring Boot 2.x users must not be offered Java 17+ records, Java 21+ virtual threads, Spring Boot 3/Jakarta migration or modern-only APIs unless they explicitly request and validate an upgrade. React agents must inspect package.json/lockfiles; platform agents must verify their actual tool and API versions. No agent should recommend migration as a default improvement.

The offline regression file `tests/test_concrete_agent_examples.py` checks example presence across 22 canonical agents and their four host adapters. It cannot compile every illustrative fragment or prove model compliance.

## Fix completeness: role-specific examples and regression checks

Every one of the **22** canonical agents contains a mandatory `Fix completeness and regression gate`, plus a **concrete example** showing an incomplete change, a fuller approach, a proposed regression test and the explicit `not run` status. These are illustrative fragments and not substitutes for checking the user's actual project. The offline regression test `tests/test_fix_completeness.py` checks the 22 definitions and the 88 generated Copilot/Claude/Codex/Gemini adapters.

The [shared quality-rule worked examples](agent-rule-worked-examples.md) give before/after patterns for each of the six common evidence/quality rules. They are teaching materials, **not** proof that the models follow each rule. Specialty-specific rules still require the domain context and actual dependencies.

Do not claim a fix is complete until its proposed patch is re-evaluated against **all independently supported defects**, conditional contract assumptions are called out, and missing/failed verification is explicitly recorded.

## Evidence-gated recommendations across all 22 agents

Every agent now contains a mandatory `Source-evidence gate for all recommendations`. An agent must inspect the user's **actual requested code, build/configuration or observed logs**, verify real file lines and relevant toolchain, and establish a credible trigger and violated invariant **before** claiming a defect or prescribing a defect fix. Generic hardening, style opinions, hypothetical risks, or assumptions about API requirements are **not confirmed findings**.

Use `STATICALLY VERIFIED` only for demonstrated source semantics; this is not an executed reproduction. Use `RUNTIME REPRODUCED` only after a genuinely run test and observed output. Use `LIKELY` or `CONTRACT-DEPENDENT` where callers, reachability or policy remain unknown; list what evidence would settle it. The `java-reviewer` additionally uses an adversarial check that attempts to **falsify** each candidate finding, deduplicates root causes, and discards unsupported issues. Correct code paths must remain correct, without invented flaws.

A user-requested new feature or architecture may be discussed as an **explicit design proposal**, even when there is no pre-existing code; proposals cannot be disguised as diagnosed bugs. All fixes must be checked against the actual source/version and all supported findings, with unexecuted checks marked `not run`.

The `tests/test_source_evidence_gate.py` suite checks the 22 definitions and generated 88 host adapters for these instructions. **Passing those tests verifies only text and installation, not behavioral compliance or superior model quality.** External outputs still require blinded benchmarking and human verification of actual source-grounded claims.

## Executable fixes and production acceptance

All 22 definitions now include `Executable verification handoff` and `Production quality acceptance`, with unique specialty checks. They require type/caller/effective-config verification, fault-path state assertions, regression failure before correction, combined-fix validation and scoped observability/code-quality/security/compatibility evidence. Small changes may mark irrelevant dimensions not applicable with a reason. See [implementation verification](implementation-verification.md) for actual paired execution tooling and its trust limits. `tests/test_implementation_verification.py` checks packaging plus evaluator behavior on toy patches; this does not measure model compliance or Copilot superiority.

## Code impact, invariant strength and cross-service contracts

Every canonical agent now has a mandatory code-validation section and a unique specialty check. Java/Spring roles use compiler/type evidence where available; React/platform roles must use appropriate domain tooling rather than treating a Java graph as applicable. Missing source/classpath, runtime wiring, unsupported contract constructs and unexecuted checks remain explicit. Targeted mutation scoring requires a passing baseline and does not count compile errors/timeouts as kills. Static schemas cannot certify authorization or deployed consumer behavior. See [code change validation](code-change-validation.md) for executable tools, workflow, examples and limitations. The instruction/adapter tests verify 22 definitions/88 generated files, not model compliance.

## Bounded repair feedback by role

All 22 definitions carry the bounded repair/test feedback policy, propagated by the existing installer to all four hosts. Only authorized implementation tasks enter a repair cycle; read-only reviews and architecture proposals remain read-only. Platform/security tasks select applicable configuration and integration checks. Visible test feedback must not weaken assertions or expose frozen independent evaluator details, and unknown side effects require reconciliation before retry.

This is a host-agent instruction policy. The optional `engineering_cycle.py` API adapter remains a single implementation artifact followed by independent verification; it does not yet implement an automatic visible-test repair scheduler. Instruction packaging checks cannot demonstrate behavioral compliance or comparative model quality.
