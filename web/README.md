# Daeloryn Engineering Console

Responsive React + TypeScript + Vite frontend with a chat-first workspace.

## Screens

- **Overview**: status summary, workflow diagram and task shortcuts.
- **Chat**: multiple locally saved conversations, agent/model selectors, opt-in local providers, and explicit execution status.
- **Agents**: validated repository specialist catalog when the local API is available; samples otherwise.
- **Workflows**: approval-gated lifecycle visualization (not an active runner).
- **Benchmarks**: start a real read-only paired Copilot A/B pilot directly from the browser, with explicit approval and progress, alongside the separate independently verified-results dashboard. No fabricated winner.
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

With **GitHub Copilot** and a confirmed local project selected, only an explicit
full-project request (or the deliberate Full context override) prepares all eligible
supported sources. Focused questions prepare a small relevant subset; generic chat
uses no repository source. The chat shows the exact source manifest, chosen model,
agent profile, exclusions and potentially billable call count before any source
is transmitted. Inspect and explicitly approve the SHA-256-bound snapshot to begin;
the server handles sequential batches and streams completed batch replies and
progress into chat. Automatic model routing resolves to a concrete discovered model
at preparation and cannot silently re-route after approval.

Turn off **Use selected local project for chat** for inexpensive text-only prompts.
The previous review flow is still available under **Advanced: manual source review**.
Changing model, project or agent invalidates pending approval. Disconnections and
unknown outcomes are never automatically retried. All batches are reviewed
independently: complete source inclusion does not prove cross-file semantic analysis.
Nothing in chat edits sources, executes commands or runs tests. CLI deny flags are
not an OS sandbox; provider model/agent compliance is not independently attested.
Chat names and messages persist unencrypted in browser localStorage; enabled providers
receive submitted prompts. Never send secrets or expose these servers publicly.

## Run a paired read-only A/B benchmark from the frontend

1. Launch the loopback console with `--enable-copilot-chat --enable-project-picker`,
   with Copilot CLI installed/authenticated and the optional SDK available for
   live model discovery. Register an explicit local checkout using Chat → Add project.
2. Open **Benchmarks** → **New A/B benchmark**. Select that local project, a real
   discovered Copilot model, benchmark mode and a trusted Daeloryn specialist.
   Code review and architecture modes analyze sources; fix-plan mode only proposes
   changes/tests (it does **not** apply patches or execute checks).
3. Select **Prepare A/B benchmark**. The API builds a single bounded source snapshot
   shared by baseline and specialist. Inspect **both exact source prompts**, omissions,
   selected model, agent, source/approval SHA-256 hashes and combined potentially
   billable batch-call count. No model call occurs during preparation.
4. Check the explicit approval box, then choose **Approve & run A/B**. The API
   re-reads the project and rejects stale source/agent/model changes, starts only
   one A/B run at a time, invokes Copilot without file/shell/network/memory tools
   in separate temporary sessions, and streams completed batches and both answers.
   It never automatically retries unknown outcomes.
5. Compare side-by-side cited issues and validate genuine defects and false
   positives independently. The result clearly reads **Winner: Not determined**;
   no unsupported evaluation metric or independent model identity attestation is
   invented. This pilot is intentionally **not** counted as a verified trial in
   the existing Benchmarks coverage matrix. Optional human-entered counts for
   confirmed unique defects, false positives and file/line references can produce
   a clearly labeled **human-assessed pilot advantage**, only if one arm dominates
   both measures. These are not verified benchmark scores. Page refresh does not
   persist private model transcripts. An interrupted browser stream may leave a provider call
   with unknown external outcome.

Source inclusion is limited to eligible supported text files under existing
source/call/time budgets. Batches are independent; this is not a complete
cross-file reasoning guarantee. The Copilot deny flags are **not an OS sandbox**.
Do not use confidential customer checkouts, host credentials or an untrusted
development workstation without external isolation and authorization. For a
real **Bug Fix + Regression Tests** contest, use the separately documented
frozen-test/isolated evaluator protocol until the secure runner is integrated.

## Persistent A/B benchmarks and live workflow progress

- **Overview → Discovered models** counts the provider-advertised Copilot and
  Ollama catalog entries separately. These are *not* verified sessions or proof
  of availability for inference.
- **Benchmarks → Prepare → Approve & run A/B** now starts a durable loopback
  background worker, not an HTTP response-owned run. Each approved attempt gets
  a new ID. **Saved A/B runs** lists up to 30 runs; selecting one restores
  transcripts, batch counts, status and per-arm failure details across page
  navigation and refresh.
- Private run receipts are stored under
  `~/.daeloryn/benchmark-runs/*.json` with restricted file permissions.
  Model responses may contain confidential content. The source snapshot and
  exact user approval prompts are **not** written to run receipts. Back up or
  protect the directory accordingly. The UI provides no deletion of benchmark
  receipts yet; chat deletion does not delete them.
- If the server crashes/restarts mid-run, the saved status is marked
  **interrupted**, not successful. A partially completed baseline or specialist
  is preserved without automatic retry. Source approval, model and batch limits
  are still validated before the run starts. History storage is bounded to 30
  runs (new attempts are rejected when full rather than silently deleting data).
- **Workflows** is now an evidence-based view of these recorded A/B runs:
  source approval, baseline and specialist progress and failure receipts. Steps
  requiring independent defect review, patch writes, tests and GitHub publication
  remain explicitly pending/not available; no boxes can manufacture completed
  stages. The review pipeline remains **read-only**.
- **Chat → Recent chats** supports deleting one selected conversation with
  confirmation. The remaining conversations persist in browser localStorage;
  when deleting the last one, an empty replacement chat is created. Pending
  source approval or model calls block deletion to avoid orphaned outcomes.

Previous in-memory benchmark results that disappeared before this feature
cannot be recovered. A brand-new approved run is required to populate the
new durable history; do not repeat an uncertain prior run without reconciling
its external provider usage.

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

Project picker access is confined to `~/IdeaProjects` by default. To allow another
trusted parent, explicitly start with `--project-picker-root /absolute/parent`
(repeatable; explicit values replace the default). Both preview and registration
validate normalized path boundaries before filesystem inspection. Prefix lookalike
folders, parent traversal and symlink escapes are rejected. Saved projects outside
the current allowed roots are not exposed. This does not change the separately
configured `--repository-root` catalog.

### Saved conversations and progressive display

Chat messages, source-review results, renamed titles and the active conversation
are saved in browser `localStorage` under `daeloryn.chat-history.v1`. This is local
unencrypted browser storage, not a backend database or cross-device sync. Limits:
50 conversations, 200 messages per conversation, 2 MB total. Invalid stored data is
not executed or silently overwritten; use Settings → Clear local conversation
history to reset it. Storage errors are visible; in-memory chat continues.
Rename the active conversation in its toolbar. An explicitly renamed title is not
replaced by an automatic first-message title. Clearing site data also erases history.
Multiple tabs use last-write-wins storage; use a single active console tab.

New replies are revealed progressively (line boundaries where available), with a
Show full reply control. This is explicitly **buffered display after provider
completion**, not live token streaming. Reduced-motion users and restored messages
show the full text immediately. Complete text is saved before animation finishes.

### Smart Context and readable chat history

Chat defaults to **Smart (recommended)** when a registered local checkout is selected:
general greetings/questions are **text-only** and cannot trigger a repository
read or source upload; explicit full-project review requests prepare the existing
whole-source manifest. Focused project questions use a bounded, filename-ranked
selection (up to 8 files / 64 KiB, plus no full source-content search), with
potential omissions clearly disclosed. The selection is conservative and
heuristic: if a relevant file was not selected, narrow the question or request
a full review explicitly. Review prepares exact source excerpts for inspection,
then requires a new per-selection consent before sending any source to Copilot.

In Session configuration, **Context behavior** can be Smart, Text only, or Full
project for every message. The Full override still requires explicit source
approval on each request and may invoke numerous model calls. Before approval,
the UI gives the **exact batch/model-call count**. AI Credit/currency cost is
marked **unavailable** because this CLI provides no independently verified
per-request credit usage; the system never derives actual billing from guesses.

New chat messages store UTC ISO timestamps in existing local history and render
the browser's local date and time. Older saved messages remain readable and
are labeled without inventing timestamps. The scroll follows a gradually
revealed answer when the reader is near the bottom, but pauses when the reader
scrolls up and resumes upon returning to the bottom. The progressive display
is **not actual provider token streaming**.

### Whole-project source review

Plain chat remains text-only; selecting a folder does not grant plain-chat tools.
Use Prepare AI review context, inspect the full manifest and approve the exact
source/model/profile digest. Whole-project preparation inventories supported Java,
Kotlin, Python, TypeScript, JavaScript, Go, XML, Gradle sources plus README and
conventional build files. It does not choose the first four files. All characters
of included files are split into line-numbered batches; the manifest records any
omissions and exclusions. Eligible unreadable/oversized files produce partial
coverage, never a full-coverage claim. Hidden, dependency/build, sensitive filenames,
symlinks, binaries and unsupported formats are excluded. Heuristic redaction is not
a secret scanner; inspect the exact prompts before sending to a provider.

Limits: 500 files, 256 KiB per file, 1 MiB total source, 10,000 filesystem entries,
depth 20, 64 model calls. Each approved batch may incur provider usage; the UI shows
the number before approval. A run stops before starting another call after five
minutes or its output budget; the in-progress call retains its own timeout.
Completed batches are preserved on provider failure. Unknown external outcomes are
reported explicitly, no retry is automatic, and remaining batches are not run.
Full source inclusion does not prove that the model reasoned over all relationships:
batches are independent and cross-batch reasoning is not guaranteed. Results still
require human verification. No edits, builds or tests are performed.

The plain chat request limits remain unchanged. Only server-prepared, digest-approved
review batches use an internal 24,000-character message allowance; clients cannot
enable that allowance through arbitrary JSON fields.

Review batching groups contiguous source into compact blocks carrying the file,
original starting line/column and ending line. File paths are not repeated for
every individual line. This preserves every character of included source and
original evidence coordinates while reducing unnecessary context expansion. The
64-call approval limit and source/request budgets remain unchanged. If genuinely
over budget, preparation reports the required call count before any provider call.

Source reviews stream NDJSON batch status to the browser: completed/total calls, the active batch and elapsed seconds. Replies still arrive once each model call completes, rather than token by token. The 300-second coordinator budget is checked between calls; the active call may take up to 90 additional seconds. The browser stops waiting at 420 seconds and reports an unknown outcome without retrying. Disconnecting does not cancel a provider call already in flight; subsequent stream writes stop further calls when the disconnect is detected. Do not resubmit while the outcome is unknown. JSON API callers remain supported without the NDJSON Accept header.
