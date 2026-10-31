# Daeloryn

**Technology-focused AI engineering agents for Codex, Claude Code, GitHub Copilot and Gemini CLI.**

Modular · Open source (MIT) · Developer preview

Specialists for **Java, Spring Boot, React, Kubernetes, Docker, CI/CD, GitOps and Security**. Install only the modules you need. Java 25 is supported as a **version-aware target**, not an automatic upgrade of existing projects.

## Quick start

Requires Python 3.11+.

```bash
git clone https://github.com/mathias82/daeloryn.git
cd daeloryn
python3 scripts/agents.py validate
python3 scripts/agents.py install --target /path/to/project --module spring --tool copilot
```

Preview the installer without writing files:

```bash
python3 scripts/agents.py install --target /path/to/project --module all --tool all --dry-run
```

To install every module for all four tools:

```bash
python3 scripts/agents.py install --target /path/to/project --module all --tool all
```

| Module | Focus |
| --- | --- |
| Java | Java 17/21/25-aware JVM architecture, development, review, testing |
| Spring | Spring Boot, Security, Data, WebFlux, testing |
| React | TypeScript, frontend architecture, review, testing |
| Platform | Kubernetes, Docker, CI/CD, GitOps, reliability |
| Shared | Security and integration review |

## Why use it?

**Pros:** reusable specialists, modular installation, common definitions for four tools, testable installer and evaluations.

**Trade-offs:** the current workflow engine supports dependency planning and approval-gated manual handoffs, **not** automatic AI agent execution. Tool compatibility and agent effectiveness still need end-to-end verification.

## Workflows

Spring feature and platform release templates provide DAG planning, local state, signed approval transitions and experimental SQLite/OIDC verification and Docker isolation components. These do **not** constitute a production deployment approval service.

## Unified execution service (developer preview)

The new `scripts/execution_service.py` provides a common SQLite workflow CLI with dry-run, status, manual evidence completion and OIDC-verified approval entry points. `scripts/agent_adapter.py` defines a fail-closed provider boundary: **no AI provider is invoked automatically**.

## Next milestone

Unify the current components into a single execution service with **real AI-provider integrations**, **controlled credentials**, **isolated execution**, **externally enforced approvals**, and **auditable state transitions**. See the [roadmap](docs/roadmap.md).

## Cross-stack evaluations

An additional offline reference corpus covers **Java 25, Spring, React and Kubernetes**, with 4 unsafe fixtures and 8 expected findings. CI validates fixture labels and scoring tests; actual model accuracy has **not** been measured. [Evaluation protocol](docs/evaluations.md).

## Measured AI evaluation (in progress)

The cross-provider benchmark harness now records external Codex, Claude, Copilot and Gemini outputs, checks claimed source-line evidence and compares recorded findings. **No real-provider results are published yet**; synthetic offline scores must not be treated as measured agent accuracy. See the [benchmark protocol](docs/benchmark-protocol.md).

## Engineering review quality

All 22 specialists now include source-grounded review requirements: verified file locations, explicit static-versus-runtime evidence, root-cause deduplication, contract-aware severity, and minimal version-specific fixes. Automated tests check that these rules survive generation for all four hosts; **live model quality improvements remain unproven**. See [Agent quality standard](docs/agent-quality-standard.md).

## Evidence audit (opt-in)

All 22 agents now include an outcome-aware review protocol. The [review proof gate](docs/review-proof-gate.md) adds an independent CLI that checks structured findings against exact source lines, source hashes, contract references and duplicate root causes. Optional `--require-source-hashes` mode also rejects reports whose cited file revisions have changed. These checks are **not proof of semantic correctness or model superiority**.

```bash
python3 scripts/audit_review_evidence.py --root /path/to/project --report /path/to/review.json
```

## Documentation

[Getting started](docs/getting-started.md) · [Workflows](docs/workflows.md) · [Architecture](docs/architecture.md) · [Pros & cons](docs/pros-cons.md) · [Evaluations](docs/evaluations.md) · [Benchmark protocol](docs/benchmark-protocol.md) · [Roadmap](docs/roadmap.md) · [Release gates](docs/release-gates.md) · [Host compatibility](docs/host-compatibility.md)

**Status:** developer preview. An opt-in offline container adapter is available for trusted, digest-pinned images; it does not provide hosted AI API connectivity. Static validation and synthetic evaluation tests exist, but production readiness and cross-provider runtime behavior are not verified.

[Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [MIT License](LICENSE)
