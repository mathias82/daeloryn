# Daeloryn Engineering Console

Responsive React + TypeScript + Vite frontend with a chat-first workspace.

## Screens

- **Overview**: status summary, workflow diagram and task shortcuts.
- **Chat**: multiple in-memory conversations, agent/model selectors, opt-in local providers, and explicit execution status.
- **Agents**: validated repository specialist catalog when the local API is available; samples otherwise.
- **Workflows**: approval-gated lifecycle visualization (not an active runner).
- **Benchmarks**: no fabricated scores; shows an honest empty state until verified data is available.
- **Models**: illustrative routing tiers, not real model discovery or pricing.
- **Settings**: explicit connection/security status and local conversation reset.

## Local development

```bash
cd web
npm install
npm run dev
npm run build
```

Open the localhost URL printed by Vite. Start the loopback API from the repository root with:

```bash
python3 scripts/console_api.py --enable-copilot-chat --repository-root /path/to/workspaces
```

Copilot CLI must already be installed and authenticated. Install the optional
`github-copilot-sdk` in the API environment for live model discovery. In Chat,
select **GitHub Copilot**, an available **Sonnet model ID**, and **java-reviewer**.
Named selections use a staged Daeloryn custom profile via CLI `--agent` together
with `--model`; they no longer serve only as preview labels. This uses the
trusted catalog shipped with Daeloryn, not arbitrary profiles from your target
repository or an existing IDE session. Automatic agent recommendations remain
advisory; Automatic model routing preserves an explicitly selected agent.

Plain chat sends messages without target repository access. For source review,
confirm a local repository and a concrete model, enter the review task, then
**Prepare AI review context**. Inspect the source excerpts and expandable agent
profile, approve the selection, and send it. Source, repository, model, agent
and profile digest are bound together; changing the selection resets approval.
Only up to four bounded source excerpts are sent, not a complete project review.
No source edits or tests are performed by this review path. CLI deny flags are
not an OS sandbox; provider model/agent compliance is not independently attested.
Messages remain in React memory and disappear on reload, but enabled providers
receive submitted prompts. Never send secrets or expose these servers publicly.

## Production integration requirements

Before enabling any remote functionality: authenticate users, enforce backend authorization per workspace and agent, use CSRF protections as appropriate, enforce server-side request limits, never accept arbitrary shell commands, use isolated workers and ephemeral scoped credentials, require explicit approval for write actions, and expose independently validated execution events. The frontend must distinguish requested model from verified model identity. Do not claim live execution from a CLI invocation alone.

## Testing status

Run `npm test` for frontend request and approval identity checks and `npm run build`
for type checking and production bundling. Python HTTP and fake-CLI process tests
exercise agent selection and approval invalidation. These do not prove live
Copilot inference; verify that separately with your authenticated CLI.

## Browser integration checks

Run `npx playwright install chromium --only-shell`, then `npm run test:e2e`
from `web/`. The suite starts its own loopback Vite server, intercepts every
`/api/` request with fixtures, and never contacts Copilot or executes repository
code. It checks model/agent request wiring, stale approval reset and honest
benchmark evidence labels. CI installs Chromium and retains traces/screenshots
on failure. These are browser integration tests, not live provider verification.
