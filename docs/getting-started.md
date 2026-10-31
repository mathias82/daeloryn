# Getting started

Requires Python 3.11+ and a checkout of this repository.

```bash
git clone https://github.com/mathias82/enterprise-engineering-agents.git
cd enterprise-engineering-agents
python3 scripts/agents.py validate
python3 -m unittest discover -s tests -v
```

Install only what your project needs:

```bash
python3 scripts/agents.py install --target /path/to/project --module spring --tool copilot
python3 scripts/agents.py install --target /path/to/project --module java --tool codex
python3 scripts/agents.py install --target /path/to/project --module react --tool claude
python3 scripts/agents.py install --target /path/to/project --module platform --tool gemini
```

For every module and all four tools:

```bash
python3 scripts/agents.py install --target /path/to/project --module all --tool all
```

Supported modules: `java`, `spring`, `react`, `platform`, `shared`. Supported tools: `codex`, `claude`, `copilot`, `gemini`, `all`, and legacy `both` (Codex + Claude).

| Tool | Generated definition |
| --- | --- |
| Codex | `.codex/agents/<name>.toml` |
| Claude Code | `.claude/agents/<name>.md` |
| GitHub Copilot | `.github/agents/<name>.agent.md` |
| Gemini CLI | `.gemini/agents/<name>.md` |

The installer refuses overwrites by default. Use `--force` only after reviewing generated changes. The target directory must already exist. Installed agents require a supported version of the corresponding host tool; file generation alone does not prove runtime compatibility. Configure tool permissions and sandboxing in the host application. Agents do not automatically invoke each other or gain separate models.

### Workflow planning

Plan the included workflows without running agents, commands or deployments:

```bash
python3 scripts/workflows.py --validate-all
python3 scripts/workflows.py workflows/spring-feature.json
python3 scripts/workflows.py workflows/platform-release.json
```

These commands only validate workflow dependencies and print execution waves. The DAG planner only describes approval steps; the separate local execution engine enforces signed-token approval transitions when creating manual handoffs. It does **not** invoke AI tools or verify approver identity through SSO. See [workflow documentation](workflows.md).

### Troubleshooting

If validation fails, check the agent frontmatter (`name`, `description`, `scope`) and matching `agents/<module>/<name>.md` path. If an installation fails, check the target path and existing generated files. For CI failures, inspect the exact commit and failed step; old red runs do not update after a fix.
