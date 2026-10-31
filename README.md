# Enterprise Engineering Agents

**Technology-focused AI engineering agents for Codex, Claude Code, GitHub Copilot and Gemini CLI.**

Independent of BMAD · Modular · Open source (MIT) · Experimental

Specialists for **Java, Spring Boot, React, Kubernetes, Docker, CI/CD, GitOps and Security**. Install only the modules you need; each agent follows evidence-based engineering and review guidance.

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
| Spring | Boot, Framework, Security, Data, WebFlux, testing |
| React | TypeScript, frontend architecture, review, testing |
| Platform | Kubernetes, Docker, CI/CD, GitOps, reliability |
| Shared | Security and integration review |

## Why use it?

**Pros:** focused reusable specialists; technology-by-technology installation; shared definitions for four tools; testable installer and evaluation infrastructure.

**Trade-offs:** workflow DAG planning is available, but live agent orchestration and project-management workflows are not; host capabilities differ, and production changes require human oversight.

**Why not BMAD?** Different purpose, not a claim of superiority. BMAD helps organize software delivery and planning; this toolkit focuses on specialists for everyday implementation and review. They can be used together. [Full comparison](docs/why-not-bmad.md).

## Workflows

DAG planning and local, approval-gated **manual agent handoffs** for Spring features and platform releases. No automatic AI invocation or deployments. See [Workflow orchestration](docs/workflows.md).

## Documentation

[Getting started](docs/getting-started.md) · [Workflows](docs/workflows.md) · [Architecture](docs/architecture.md) · [Pros & cons](docs/pros-cons.md) · [Why not BMAD?](docs/why-not-bmad.md) · [Evaluations](docs/evaluations.md) · [Roadmap](docs/roadmap.md)

**Project status:** experimental. Static validation and synthetic benchmark tests are available, but agent performance and runtime compatibility across all four tools are not yet fully verified.

[Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [MIT License](LICENSE)
