# Local read-only Console API

The Python standard-library API exposes only `GET /api/health`,
`GET /api/agents`, and `GET /api/benchmarks`. It reads validated
repository agent metadata and an optional operator-supplied directory of
benchmark trial JSON records. No provider execution, prompt submission,
filesystem browsing, credentials, write routes or model access is exposed.

## Start locally

Terminal A:

```bash
python3 scripts/console_api.py --port 8765
# optional: --records-dir /private/benchmark-trials
```

Terminal B:

```bash
cd web
npm install
npm run dev
npm run build
```

Vite proxies `/api` to the loopback-only Python API. **Do not expose
the development server or API to untrusted networks.** No authentication
is implemented: production requires authentication, authorization,
TLS, CSRF/CORS policy review, resource limits and an explicit API threat model.

The API deliberately returns a summary rather than untrusted raw benchmark
transcripts. Matrix trial flags are operator-provided; they are not independent
attestation by this server. If the API is unavailable, the UI shows
illustrative agent profiles and no benchmark score. The chat remains
in-memory and does not invoke any model.

## Test

```bash
python3 -m unittest discover -s tests -p 'test_console_api.py'
```

## Optional real local AI Chat (Ollama)

The console can now send bounded chat messages to an **installed local Ollama
model**. This is explicitly opt-in and does not execute shell commands, access
the repository, activate a specialist agent, or call cloud providers.

1. Install Ollama separately, download a model, and start its local server
   bound to loopback (the default local API is `127.0.0.1:11434`).
2. Start the Daeloryn API:
   ```bash
   python3 scripts/console_api.py --enable-local-chat
   ```
3. Start the Vite frontend as above. Select an installed model in the Chat
   sidebar and send a message. A live reply is marked as an assistant message.

The server only accepts `POST /api/chat` when explicitly enabled, requires a
trusted local browser Origin, bounds request size, message count, message length,
model name, response size, and provider timeout, and checks the model against
the installed Ollama catalog. `GET /api/models` reports installed models.
The frontend is still a local developer tool: **do not expose either server
to a network**. There is no user authentication, streaming, tool calling,
workspace access, or cryptographic proof of model identity. Ollama model
availability is verified from its local API but model identity is not attested.
Prompts are sent to the user's local Ollama process, not kept solely in React
memory once local chat is enabled. Do not paste secrets.

Tests:
```bash
python3 -m unittest discover -s tests -p 'test_local_chat.py'
```

## Opt-in GitHub Copilot CLI Chat

This alternative to the local Ollama integration uses your **installed and
authenticated GitHub Copilot CLI**. The web console sends chat messages to a
bounded, one-shot `copilot --prompt ... --model ...` invocation.

```bash
# Authenticate Copilot CLI separately, using the official GitHub workflow.
python3 scripts/console_api.py --enable-copilot-chat
# In a second terminal:
cd web && npm install && npm run dev
```

In the Chat sidebar, enter a Copilot model identifier available to your account
and send a message. The model ID is requested, **not independently verified**.
The server launches each request from a fresh temporary working directory with
`--deny-tool=shell,write,read,url,memory`, disables built-in MCP servers,
custom instructions and automatic updates, and does not grant all-tools access.
An optional `agent` field activates a validated Daeloryn catalog profile.
The launcher stages only that profile in a temporary `.github/agents` directory,
restricts its tools to `[]`, and passes a unique CLI agent ID with `--agent`.
This avoids collisions with same-named user profiles without changing their files.
It does not load target-repository instructions or reuse existing IDE sessions.
The response reports `agent_selected`, `agent_profile_sha256`, and
`agent_identity_verified: false`; selection is not proof of provider compliance.

**Important security boundary:** Copilot CLI may load user-installed extensions,
other configured MCP integrations or user-level settings. CLI deny rules and a
temporary working directory are not a sandbox or proof of zero side effects.
Use a dedicated OS account/container without workspace mounts or sensitive
credentials for untrusted prompts. Do not expose the unauthenticated console API
or Vite development server beyond localhost. Prompts can be sent to GitHub's
Copilot service and may appear in process arguments; never send secrets.
Requests may consume Copilot usage. A timeout does not prove cancellation of
remote work. This implementation is synchronous and does not stream responses.

Run `python3 -m unittest discover -s tests -p 'test_copilot_chat.py'`.

## Automatic Copilot model routing (opt-in)

With `--enable-copilot-chat`, the console can request `GET /api/copilot/models`.
This calls the installed authenticated Copilot runtime through the optional
`github-copilot-sdk` Python package (install it in the API Python environment).
No models are invented when discovery fails. The UI exposes only returned model
IDs plus `Automatic (task-based)`.

For `model: "auto"`, the server discovers the current catalog and uses
`scripts/model_router.py` to choose a model. Short translation/summary tasks
prefer an available Haiku family; coding and risky tasks prefer an available
Sonnet family. If no approved family is available, it returns a failure rather
than silently using a different model. The response reports the **requested**
model and routing reason, not a verified provider identity. Each auto request
performs live discovery; this may add latency. No automatic retry is performed.

Explicit agent selections survive model routing. Automatic agent recommendations
remain advisory and do not select a specialist. Neither mode grants target
workspace access. CLI and SDK installation,
authentication, model entitlements and real model inference must be validated
on the operator's machine.

## Local repository discovery (opt-in, advisory only)

Start the console with a trusted local parent directory of Git checkouts:
`python3 scripts/console_api.py --enable-copilot-chat --repository-root /path/to/workspaces`.
Repeat `--repository-root` for additional directories (maximum 10).
Without this option, no local repositories are exposed.

`GET /api/repositories` lists up to 100 direct child directories with
non-symlink `.git` directories and reports basic technology markers from
file names only. `POST /api/repository-routing` accepts
`{"task":"Review payments Java service"}` and returns a conservative
suggestion. Ambiguous matches are not selected. Every suggestion requires
explicit user confirmation. No cloning, repository contents reading, GitHub
token use, remote GitHub API access, or agent execution occurs.

The Chat UI can show local repositories and a suggested repository; the
current Copilot chat adapter does **not** use the repository, even after UI
selection. Do not treat the selector as authorization for filesystem access.
Git worktrees with a `.git` file are intentionally excluded.

## Opt-in GitHub repository catalog

Install and authenticate GitHub CLI (`gh auth login`) locally, then start
`python3 scripts/console_api.py --enable-github-repositories`.
`GET /api/github/repositories` lists up to the first 100 recently updated
repositories visible to the authenticated GitHub account. This is a **partial**
catalog (not exhaustive pagination), including private repository names if the
account has access. Only metadata is returned; no repository source files are
downloaded, no clone occurs and no remote changes are made.

The React repository selector includes the returned GitHub repositories.
Choosing an entry is **advisory only** and does not grant the chat adapter
repository access. The existing local checkout routing remains separate.
Do not expose this loopback API via a public proxy: repository names may be
sensitive. When `gh` is missing or authentication fails, the API returns
503 without exposing CLI stderr.

## Read-only local project fingerprint

With one or more `--repository-root` options, POST
`/api/project-analysis` with `{"repository":"checkout-name"}` to inspect
top-level technology marker file **names** and direct child directory names.
The checkout must resolve uniquely among configured roots and contain a
non-symlink `.git` directory. No source file contents are read, no commands
are executed, and no modifications are made. This endpoint does not yet
support remote GitHub repositories, deep dependency inspection or agent execution.

## Bounded source review (local repositories only)

POST `/api/code-review` with `{"repository":"checkout-name","task":"Review Java concurrency"}`
after configuring `--repository-root`. This opt-in request reads up to 80
small source files (256 KiB total), excludes common secret file names,
symlinks and build folders, and returns conservative pattern-based findings
with file paths and line numbers plus an advisory agent recommendation.
No code is executed, no edits are made, and no pull requests are opened.

**Security caveat:** Redaction is heuristic, not a complete secret detector.
Do not forward returned excerpts to external AI providers without separate
consent and a stronger secret-scanning/redaction gate. Findings are leads for
review, not confirmed vulnerabilities. Repository contents are untrusted.
Remote GitHub code review, dependency graph, verified tests, model invocation
and approval-gated branch/PR creation are not yet implemented.

## Local code review from the React console

Select a **local checkout** from the Chat session configuration and click
**Run local code review (read-only)**. The console calls the existing
`POST /api/code-review` endpoint with the explicitly selected local repository.
The results show the number of scanned files, line-level pattern matches,
and suggested fixes. GitHub cloud repositories are not supported by this
operation; no source is sent to Copilot, no files are modified and no tests
or agents are executed. The chat provider and model selector remain separate.


## Copilot model + agent source review

`POST /api/copilot/chat` accepts `{model, messages, agent?}`. Unknown profile
names, paths and extra properties fail before inference. Generic chat without
`agent` remains supported. Profiles come from the installed Daeloryn catalog.

`POST /api/copilot/review/prepare` now requires `{repository, task, model, agent?}`;
`model` must be concrete, not `auto`. The response includes the exact prompt,
profile and SHA-256 approval digest. `POST /api/copilot/review/execute` accepts
the same fields plus `approved_sha256`. The API re-prepares from current source
and profile; changed source, repository, model or profile invalidates approval.
The launcher also checks the expected profile hash immediately before staging.
Approval is per exact content/selection, not a persistent authorization token
or single-use execution claim. No automatic retries are made on provider error.

The frontend no longer silently substitutes the first discovered model for
source review. Choose the desired Sonnet ID explicitly. Review remains bounded
to four excerpts/1700 source characters and requires manual inspection; it is
not a complete repository review or a secret-scanning guarantee. Authentication,
entitlements and live inference must be checked on the operator's machine.

References: [GitHub custom-agent invocation](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/invoke-custom-agents)
and [CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).
