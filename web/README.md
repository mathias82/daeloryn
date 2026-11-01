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

## Start frontend and backend together

The backend already ships inside Daeloryn (`scripts/console_api.py`). Install
frontend dependencies once with `cd web && npm install`, then from the repository
root, using the Python environment with the optional Copilot SDK installed:

```bash
python3 scripts/console.py --enable-copilot-chat --enable-project-picker --open
```

This starts the API on 127.0.0.1:8765 and Vite on 127.0.0.1:5173, waits for both,
and optionally opens the browser. Ctrl+C stops both owned processes. A failed
startup or exited child stops its companion. Busy ports fail clearly; existing
services are never killed. The launcher does not install anything, authenticate
the CLI, invoke AI or enable provider access by default. `--repository-root`,
`--projects-file`, `--records-dir`, `--workflow-dir`, `--enable-local-chat` and
`--enable-github-repositories` may also be supplied explicitly. It is a development
launcher, not a deployed production server. Native macOS chooser behavior still
requires a manual Mac check; browser tests mock that boundary.

In the message field **Enter** sends, **Shift+Enter** inserts a new line. IME
composition, modified Enter keys, blank messages and in-flight requests do not
trigger an additional keyboard submission.

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

### Add local projects from the console

Start the loopback API with explicit opt-in:

```bash
python3 scripts/console_api.py --enable-copilot-chat --enable-project-picker
```

In Chat → Session configuration → **Add project**, enter an absolute project
path, or use **Browse folders (macOS)**. The native chooser opens on the machine
running the Python backend, not on a remote browser. Other operating systems use
the path field. Canceling the chooser adds nothing. Select **Find projects in
subfolders** to search a parent such as `~/IdeaProjects` (expand `~` or use the
absolute path). Review the candidate paths, select projects and explicitly approve
registration. Then choose a project in Local repository and select a concrete
Copilot model and agent before preparing AI review context.

Only selected exact project paths are saved, by default to
`~/.config/daeloryn/projects.json` (override with `--projects-file`). No checkout
files are changed. Restarting with `--enable-project-picker` reloads this list;
without that flag persisted projects are not exposed. Registration does not
upload source, run repository code or enable edits/tests. AI context approval is
still separate. Existing `--repository-root` configuration remains supported.

Discovery is bounded to 100 projects, 10,000 entries and depth 8. Dependency/build
and hidden directories are skipped; symlinks and `.git` file worktrees are not
supported. Duplicate folder names across different paths are rejected on add
because existing review endpoints address repositories by name. Rename a checkout
folder to make its name unique. Moved/deleted saved paths are skipped. To remove
saved registrations, stop the API and edit/delete the local registry file.

Security review: the opt-in management endpoint extends local read authorization
only after an explicit selection and approval. It retains the existing Host/Origin
checks and bounded JSON requests, invokes a fixed macOS chooser command without a
shell, and atomically writes a private registry file. It is a local single-user
feature, not production authentication or a sandbox. Native dialog timeout and
cancellation do not authorize a project. Native macOS interaction must be manually
verified on a Mac; automated tests use a chooser fake.
