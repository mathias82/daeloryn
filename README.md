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

## Local web console

The Python backend is included at `scripts/console_api.py`. After installing
frontend dependencies once (`cd web && npm install`), launch both servers from
the repository root with one command:

```bash
python3 scripts/console.py --enable-copilot-chat --enable-project-picker --open
```

Use the same Python environment that has `github-copilot-sdk` installed for model
discovery. Copilot CLI must already be installed and authenticated. Both servers
bind loopback; Ctrl+C stops both. Existing services on ports 5173/8765 are never
killed or reused silently. Without the explicit enable flags, AI and project
registration stay disabled. See [console setup](web/README.md) and the
[paired Java review protocol](docs/local-java-review-benchmark.md).

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

## Executable fixes and production quality

All 22 specialists now require a fix-verification handoff and role-specific acceptance for code quality, observability, security, reliability and compatibility. The opt-in [implementation verifier](docs/implementation-verification.md) prepares paired copies and runs the same pinned evaluator-owned checks against both patches. It records actual command results and rejects changed test snapshots or frozen build context; it does not invoke models or provide a security sandbox. Benchmark fixtures remain on the dedicated benchmark branch. **Real-provider code quality equivalence or superiority has not been established.**

## Optional engineering verification cycle

The [experimental engineering cycle](docs/engineering-cycle.md) adds pinned review-to-fix handoffs, content-free tracing, SQLite checkpoints, explicit recovery and bounded context. An opt-in OpenAI Responses adapter returns validated data artifacts; independent checks run separately with explicit host/container execution authorization. Existing manual adapters remain disabled for automatic provider execution. The checkout evaluator stays on the benchmark branch; `python3 scripts/check_checkout_benchmark.py --project /path/to/existing/copy --execute-checks` runs it without modifying that copy. Real provider performance and live container/API integrations remain unverified.

## Code impact, invariants and service contracts

[Three opt-in engineering gates](docs/code-change-validation.md) add compiler-resolved Java impact, pinned business-invariant/targeted mutation checks, and explicit consumer/provider compatibility matrices using native Avro plus a conservative OpenAPI JSON subset. All 22 specialists and 88 host adapters include scoped rules for these checks. Missing dependencies, unsupported contracts and unexecuted checks remain explicit; static compatibility never means production readiness. Full regression tests now require JDK 17 and `requirements-code-analysis.txt` as well as the security test dependencies.

## Documentation

[Getting started](docs/getting-started.md) · [Workflows](docs/workflows.md) · [Architecture](docs/architecture.md) · [Pros & cons](docs/pros-cons.md) · [Evaluations](docs/evaluations.md) · [Benchmark protocol](docs/benchmark-protocol.md) · [Roadmap](docs/roadmap.md) · [Release gates](docs/release-gates.md) · [Host compatibility](docs/host-compatibility.md)

**Status:** developer preview. An opt-in offline container adapter is available for trusted, digest-pinned images; it does not provide hosted AI API connectivity. Static validation and synthetic evaluation tests exist, but production readiness and cross-provider runtime behavior are not verified.

[Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [MIT License](LICENSE)


Recovery and model routing updates: [recovery verification](docs/recovery-verification.md)
adds an opt-in five-case development extension without changing the original 23 checks.
[Copilot model routing](docs/model-routing.md) discovers host models and selects a
requested model by task/risk policy; native execution is explicit and live behavior
still requires validation on a compatible installed SDK/CLI.

## Single-command checkout verification (experimental)

For the frozen Java 8 checkout exercise, [`scripts/checkout_workflow.py`](docs/checkout-workflow.md)
chains Copilot source review, operator-approved interactive fixes, and pinned
independent contract/recovery checks into one opt-in command. Approval prompts
remain interactive and verification runs only after explicit operator consent.
This is a developer workflow for trusted disposable copies, **not** production
autonomy, a security sandbox, or evidence that Daeloryn outperforms Copilot.
