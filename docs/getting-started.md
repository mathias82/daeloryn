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

## Java 25 support

The Java agents recognize Java 17, 21 and **25** as distinct project baselines. Determine the actual Maven/Gradle toolchain, JDK runtime, Spring Boot version and dependency compatibility before changing a target. Java 25 examples cover virtual-thread caveats, compiler/release settings, CI JDK and multi-stage container builds. Installing an agent does **not** install or upgrade a JDK.

Every agent definition contains an example and an evidence contract: concrete repository paths and line references, expected versus observed behavior, reproduction commands, confidence and tests actually executed.

## Quality validation and evidence

`python3 scripts/agents.py validate` now rejects canonical agents that lack an **evidence contract** or a concrete **example**. Validation checks that these sections exist; it cannot establish that an LLM actually produces correct findings or follows these rules at runtime.

The installer also preflights every destination ancestor for symlinks, including nested host agent directories, and refuses any symlinked destination. It still writes to the explicitly selected target directory only. Use a disposable checkout to verify host compatibility and review diffs before using `--force`.

## Dry-run preview

Use `python3 scripts/agents.py install --target /path/to/project --module all --tool all --dry-run` to run destination preflight and list intended files without writing any outputs. The installer is **not yet transactional** if an unexpected mid-write failure occurs; back up before using `--force`.
