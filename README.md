# Daeloryn

**Open-source AI engineering agents and a local, chat-first review console.**

Java · Spring Boot · React · Kubernetes · CI/CD · Security  
**MIT · Developer preview**

Daeloryn provides reusable specialist profiles for GitHub Copilot, Codex, Claude Code and Gemini CLI. Its local console supports read-only code inspection, explicit source approval and evidence-oriented A/B comparisons. It is **not** an autonomous code-change or production deployment service.

## Quick start

**Requirements:** Python 3.11+. For the local console, Node.js/npm. Copilot-based chat/reviews additionally require the GitHub Copilot CLI to be installed and authenticated.

```bash
git clone https://github.com/mathias82/daeloryn.git
cd daeloryn
python3 scripts/agents.py validate
python3 scripts/agents.py install --target /path/to/project --module java --tool copilot
```

For the optional **local web console**:

```bash
cd web && npm ci && cd ..
python3 scripts/console.py --enable-copilot-chat --enable-project-picker --open
```

The console binds to localhost. Agent installation and the console are independent; use only what you need. Other modules, tools, dry-run options and platform setup: [Getting started](docs/getting-started.md).

## What it does

- **Chat + automatic specialist routing:** selects a registered Java/Spring/React/platform agent from the question; manual agent selection takes precedence and the actual choice appears in Session configuration.
- **Smart Review:** ordinary questions remain text-only; questions about project code select bounded relevant source excerpts with **approval before Copilot receives them**.
- **Docs only / Text only:** Docs mode reads documentation, excluding source code and build files; Text only reads no project files. **A full-project scan occurs only when explicitly requested** and still requires source approval.
- **Code Inspector:** read-only side panel with source excerpts, clickable file/line references, batch progress and clear warnings about unverified model findings.
- **A/B Benchmarks:** compare plain Copilot with Copilot + Daeloryn on the same approved source snapshot and model; persist run receipts locally, show partial failures and support Stop, Delete and explicitly approved Resume for newly journaled runs.
- **Workflows:** show observed execution progress rather than manually ticking completion boxes.

## Important limits

Large source reviews use bounded batches (up to **38,000 characters per approved prompt**, subject to Copilot acceptance), at most two simultaneous provider requests per benchmark arm and a time/output budget. Every batch may trigger a billable provider call; **actual AI Credits are not independently available**. A failed call can have an unknown external outcome: Resume requires consent before resubmitting it. Old runs without per-batch receipts are not safely resumable.

File/line links show references present in the approved snapshot; they **do not prove that reported bugs are real**. The console does not automatically apply patches, execute regression tests or publish PRs, and it cannot certify that Daeloryn outperforms Copilot.

## Documentation

[Console & benchmark guide](docs/console-and-benchmarks.md) · [Extended setup and feature reference](docs/extended-feature-reference.md) · [Agent quality](docs/agent-quality-standard.md) · [Architecture](docs/architecture.md) · [Evaluations](docs/evaluations.md) · [Roadmap](docs/roadmap.md)

[Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [MIT License](LICENSE)
