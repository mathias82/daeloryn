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

For the optional **local web console** (frontend + backend together):

```bash
cd web && npm ci && cd ..
./start.sh
```

Run `./start.sh --repository-root /path/to/projects` to add a checkout root. `start.sh` enables Copilot chat and the local project picker, and opens the browser at `http://127.0.0.1:5173/`. `Ctrl+C` stops both services; startup fails safely when ports 5173/8765 are occupied or dependencies are missing. The script does not automatically install packages or kill other processes. The console binds to localhost. Agent installation and the console are independent; use only what you need. Other modules, tools, dry-run options and platform setup: [Getting started](docs/getting-started.md).

## What it does

- **Chat + automatic specialist routing:** selects a registered Java/Spring/React/platform agent from the question; manual agent selection takes precedence and the actual choice appears in Session configuration.
- **Smart Review:** ordinary questions remain text-only; questions about project code select bounded relevant source excerpts with **approval before Copilot receives them**. Generic bug reviews prioritize real source classes rather than only README and build manifests; full-project scans require explicit wording.
- **Docs only / Text only:** Docs mode reads documentation, excluding source code and build files; Text only reads no project files. **A full-project scan occurs only when explicitly requested** and still requires source approval.
- **Code Inspector:** read-only side panel with clickable file/line references, highlighted model-reported bugs and suggested changes, **full-screen mode**, an **Edit Suggestion** draft with original/replacement code and a copyable diff (no automatic writes), batch progress and clear warnings about unverified findings.
- **A/B Benchmarks:** compare plain Copilot with Copilot + Daeloryn on the same approved source snapshot and model; persist partial results, resume safely, and score source citations offline. A sequential **22-agent evaluation campaign** uses role-specific prompts and offers Markdown/JSON reports with candidate rule improvements (not automatically applied). An offline evaluator displays source-citation traceability and provisional evidence leads, **not a verified correctness winner**.
- **Workflows:** show observed execution progress rather than manually ticking completion boxes.

## Important limits

Large source reviews use bounded batches (up to **38,000 characters per approved prompt**, subject to Copilot acceptance), at most two simultaneous provider requests per benchmark arm and a time/output budget. Every batch may trigger a billable provider call; **actual AI Credits are not independently available**. A failed call can have an unknown external outcome: Resume requires consent before resubmitting it. Old runs without per-batch receipts are not safely resumable.

File/line links show references present in the approved snapshot; they **do not prove that reported bugs are real**. The console does not automatically apply patches, execute regression tests or publish PRs, and it cannot certify that Daeloryn outperforms Copilot.

## Documentation

[Console & benchmark guide](docs/console-and-benchmarks.md) · [Extended setup and feature reference](docs/extended-feature-reference.md) · [Agent quality](docs/agent-quality-standard.md) · [Architecture](docs/architecture.md) · [Evaluations](docs/evaluations.md) · [Roadmap](docs/roadmap.md)

[Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [MIT License](LICENSE)
