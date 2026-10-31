# Daeloryn Console (frontend MVP)

React + TypeScript + Vite. Local preview UI with Chat, Agents, Workflows and Benchmarks navigation.

```bash
cd web
npm install
npm run dev
npm run build
```

Open the localhost URL printed by Vite. **Chat is local-only**: submitting a prompt adds it to the browser's in-memory conversation and displays an explicit not-executed status. No model calls, backend API, filesystem access, credentials, persistence, agent activation or benchmark data are wired yet. Avoid entering secrets.

Next: authenticated backend with narrowly scoped agent catalog and verified execution sessions; stream status and audit events, require explicit approval for modifications. Do not expose arbitrary CLI execution through a web endpoint.
