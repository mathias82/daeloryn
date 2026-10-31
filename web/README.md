# Daeloryn Engineering Console

Responsive React + TypeScript + Vite frontend with a chat-first workspace.

## Screens

- **Overview**: status summary, workflow diagram and task shortcuts.
- **Chat**: multiple in-memory conversations, agent/model preview selectors, local message composer, and explicit non-execution feedback.
- **Agents**: searchable sample specialist profiles; the full 22-agent catalog is **not loaded from the repository yet**.
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

Open the localhost URL printed by Vite. The frontend currently has **no API or AI provider connection**. Chat messages remain in React memory (not persisted), disappear on reload, and are never transmitted. The UI cannot execute code, open repositories, apply changes, or approve actions. Do not enter credentials or secrets.

## Production integration requirements

Before enabling any remote functionality: authenticate users, enforce backend authorization per workspace and agent, use CSRF protections as appropriate, enforce server-side request limits, never accept arbitrary shell commands, use isolated workers and ephemeral scoped credentials, require explicit approval for write actions, and expose independently validated execution events. The frontend must distinguish requested model from verified model identity. Do not claim live execution from a CLI invocation alone.

## Testing status

This PR has not been independently build- or browser-tested by its author. Run `npm run build` and review keyboard navigation, responsive layouts, and accessibility before merge.
