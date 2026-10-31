# Enterprise Engineering Agents

**Technology-focused AI engineering agents for Codex, Claude Code, GitHub Copilot and Gemini CLI.**

Modular · Open source (MIT) · Developer preview

Specialists for **Java, Spring Boot, React, Kubernetes, Docker, CI/CD, GitOps and Security**. Install only the modules you need.

## Quick start

Requires Python 3.11+.

```bash
git clone https://github.com/mathias82/enterprise-engineering-agents.git
cd enterprise-engineering-agents
python3 scripts/agents.py validate
python3 scripts/agents.py install --target /path/to/project --module spring --tool copilot
```

To install every module for all four tools:

```bash
python3 scripts/agents.py install --target /path/to/project --module all --tool all
```

| Module | Focus |
| --- | --- |
| Java | JVM architecture, development, review, testing |
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

## Documentation

[Getting started](docs/getting-started.md) · [Workflows](docs/workflows.md) · [Architecture](docs/architecture.md) · [Pros & cons](docs/pros-cons.md) · [Evaluations](docs/evaluations.md) · [Roadmap](docs/roadmap.md)

**Status:** developer preview. An opt-in offline container adapter is available for trusted, digest-pinned images; it does not provide hosted AI API connectivity. Static validation and synthetic evaluation tests exist, but production readiness and cross-provider runtime behavior are not verified.

[Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [MIT License](LICENSE)
