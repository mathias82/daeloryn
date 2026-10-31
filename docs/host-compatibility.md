# Host compatibility verification matrix

**Status: UNVERIFIED across all four live hosts.** Generating a file does not establish that a specific host release accepts it.

| Host | Generated location | Static generation | Live recognition | Sample invocation |
| --- | --- | --- | --- | --- |
| Codex | `.codex/agents/*.toml` | Implemented | Not verified | Pending |
| Claude Code | `.claude/agents/*.md` | Implemented | Not verified | Pending |
| GitHub Copilot | `.github/agents/*.agent.md` | Implemented | Not verified | Pending |
| Gemini CLI | `.gemini/agents/*.md` | Implemented | Not verified | Pending |

## Verification procedure

1. Create an isolated disposable project with no production credentials.
2. Record host name, version, OS and supported agent definition format from official host documentation.
3. Run the installer with `--dry-run`, then install only the module under test.
4. Open the actual host, verify the agent is discovered and can be explicitly selected; keep logs with secrets removed.
5. Run a read-only fixture review and verify that the response uses the selected agent definition.
6. Document observed pass/fail, exact version, run ID and commit SHA. Do not mark a host compatible if just the file was generated.

Run this procedure independently on Codex, Claude Code, Copilot and Gemini CLI. Host documentation and interfaces can change.
