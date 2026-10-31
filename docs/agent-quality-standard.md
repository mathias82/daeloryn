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
