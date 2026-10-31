# Architecture and design

The framework distributes focused, independent coding-agent definitions. It includes a deterministic workflow DAG planner and a local manual-handoff execution state machine, but **not** automatic AI-agent execution or a hosted inference service.

```text
agents/{java,spring,react,platform,shared}/*.md
                       |
               scripts/agents.py
                       |
      +----------------+----------------+----------------+
      |                |                |                |
  Codex TOML       Claude MD       Copilot agent.md  Gemini MD
```

Each definition uses a small metadata header and original technical instructions. The Python installer validates the catalog and emits host-specific files; it performs no network calls. The host controls whether a subagent is selected, which tools it receives and whether it is allowed to modify files.

### Design principles

- **Modularity:** install specific technologies without pulling in unrelated agents.
- **Single source of truth:** maintain canonical instructions under `agents/`.
- **Evidence-first:** reviews should cite actual files, observed behavior and unverified assumptions.
- **Minimal privilege:** prompts alone cannot enforce access restrictions; configure host sandboxes.
- **Version awareness:** Spring, React, Kubernetes and other APIs vary by project version.
- **Measurability:** benchmark definitions and scoring are separate from prompt authoring.

### Module boundaries

Java covers language/JVM engineering; Spring covers application framework semantics; React covers frontend architecture and behavior; Platform covers containers, Kubernetes, delivery and reliability; Shared covers cross-cutting security and integration. Overlap is intentional only when expertise crosses domains. The optional planner orders declared agent steps; there is no autonomous coordinator invoking agents.

### Limitations

Adapter file generation and static tests are not the same as full end-to-end validation in Codex, Claude Code, GitHub Copilot and Gemini CLI. The four runtimes can differ in metadata support, permissions, invocation and available tools. Prefer checking actual runtime behavior in a disposable test project before using in production.

## Workflow DAG planning

Workflows are declarative JSON under `workflows/`. The dependency validator in `scripts/workflows.py` checks referenced agents, cycles, duplicate steps and dependency ordering. It emits waves eligible for parallel execution; it does not invoke agents or enforce approvals. The separate state machine enforces scoped HMAC-token approval transitions for local handoffs, without SSO-backed identity or deployment authorization. See [workflows](workflows.md).

## Agent quality contract

The 22 canonical module Markdown definitions include focused practical scenarios and an evidence contract. Agents must distinguish confirmed findings from hypotheses, cite concrete repository lines and runtime/test evidence, report actual command results, and propose minimal verifiable corrections. Java examples explicitly consider Java 25 where the project's toolchain supports it. These are instruction-level requirements, **not proof that every host model will obey them**.
