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
The web UI agent selector is **not yet connected to the Copilot agent system**.

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
