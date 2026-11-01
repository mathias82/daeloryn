# Local Console and A/B Benchmark Operations

This is the detailed guide for [Daeloryn](../README.md). Developer-preview functionality only.

## Installation and startup

Requires Python 3.11+, Node.js/npm and, for Copilot requests, an installed/authenticated GitHub Copilot CLI. For model discovery use the same Python interpreter that has `github-copilot-sdk` installed.

```bash
cd web && npm ci && cd ..
./start.sh
```

`./start.sh` starts the API and Vite together with explicit Copilot chat and project-picker opt-ins, then opens the browser. You can forward launcher flags like `./start.sh --repository-root /path/to/projects`. Press **Ctrl+C** to stop both owned services. Existing processes on occupied ports are never killed; missing dependencies produce actionable errors. For custom/manual startup, the equivalent is `python3 scripts/console.py --enable-copilot-chat --enable-project-picker --open`. Use `python3 scripts/console.py --help` for all flags. Both servers bind to loopback; the console does not silently reclaim occupied ports.

For agent-only installation without a web console:

```bash
python3 scripts/agents.py install --target /path/to/project --module spring --tool copilot
```

Dry-run, all modules and other host tools: [Getting started](getting-started.md), [Host compatibility](host-compatibility.md).

## Chat workflow and source access

1. In Chat choose **GitHub Copilot**, a discovered model, and a **registered local checkout**. The application never reads cloud-only GitHub repositories as local files.
2. Keep Context behavior at **Smart (recommended)**. Questions like "review bugs in this class" prepare a **focused** source snapshot. Basic questions and greetings do not read project files.
3. Use **Docs only** for Markdown/reStructuredText/AsciiDoc and conventional root documentation. This excludes Java, TypeScript, configuration source and build manifests. Use **Text only** for absolutely no checkout access.
4. To scan all eligible project files, **explicitly** ask "full scan of my entire project". This overrides Smart's focused selection for that request only; there is no persistent full-scan-every-message setting.
5. When relevant source is prepared, inspect the exact manifest (file names, model, named agent, SHA-256 and expected call count), then explicitly approve. No code is uploaded to Copilot before this approval. The snapshot is regenerated at execution to reject changed files.
6. The agent is selected from installed, trusted profiles based on the question/technology (for example, Java Reviewer for Java bug review), and the **Agent** selector reflects that choice. Selecting an agent manually disables the automatic override until you re-enable it.
7. The read-only **Code Inspector** opens beside Chat, showing source excerpts with original line numbers. Click matching `file:line` references in completed model batches to navigate. A link being present in the source snapshot proves only the reference can be located, not that the bug is genuine. Unverified references are marked separately.

## Batching and costs

The approved source-review builder groups source into prompts of up to **38,000 characters** with an internal 40,000-character review-request validation ceiling. The plain-chat limit stays 3,000 characters per message; large previous responses are omitted from outgoing plain chat (not deleted from local history) to prevent HTTP 413.

Larger batches generally reduce the number of calls compared with the previous 23,500-character builder, but **are not guaranteed to be accepted or faster on every Copilot model or host**. The CLI can fail on token limits, timeouts, output limits or provider rate limits. The runner uses at most two simultaneous model calls per arm, a time budget and output cap. It reports partial outcomes rather than claiming a full review. The call count is a planning metric, **not verified AI Credit consumption**.

## Benchmarks: prepare, run, stop, resume, delete

- **Prepare A/B benchmark:** select a local project, model, mode and trusted agent. Plain Copilot and Copilot+Daeloryn receive the same source snapshot/task. Inspect the manifest and approve potentially billable calls.
- **Saved A/B runs:** results are stored in `~/.daeloryn/benchmark-runs/` as private JSON with restricted permissions. They may include confidential model output. Navigating away does not cancel the server-owned worker.
- **Stop run:** cooperative cancellation stops dispatching further model calls. In-flight provider requests may already have been received or billed. Completed results remain saved.
- **Resume remaining batches:** available only for partial/stopped/interrupted runs created **after per-batch journaling was introduced**. It uses the **same run ID**. The server re-reads the current source snapshot and rejects changes to the approved source/model/agent/batch packing. Completed batches with full saved responses are skipped. Previously started but unconfirmed calls are **unknown**; re-sending them needs a separate acknowledgment of possible duplicate billing. There is **no automatic retry**. At most five explicit continuation attempts are allowed.
- **Legacy runs:** an older run without per-batch receipts cannot be resumed safely; start a fresh benchmark after inspecting the cost and source manifest. A change in batching rules makes a prior approval digest incompatible with a new snapshot.
- **Delete:** only terminal runs can be deleted. Deleting a chat does not delete benchmark receipts.
- **Evaluation:** comparing text replies does not prove a winner. Independently inspect unique real defects, false positives, source coverage, proposed fixes and actual regression tests before making a quality claim.

## Security and operational boundaries

The local code context contains untrusted source, never executable agent instructions. Profiles come from Daeloryn's trusted catalog. Copilot runs with tool access disabled and without working-directory access to the inspected checkout. The console does not apply patches, run commands or publish pull requests as part of the chat review. Verify authorization before reviewing proprietary code.

For additional information: [Benchmark protocol](benchmark-protocol.md) · [Local Java review](local-java-review-benchmark.md) · [Production readiness](production-readiness.md).

## Full-screen Code Inspector and model-highlighted lines

In Chat, the read-only Code Inspector shows file:line references reported by completed review batches. Click a grounded reference to jump to the matching line in the approved snapshot. A model-reported **possible bug** and a **suggested change** have different highlights; ungrounded references remain non-navigable. A highlighted code line is *not* proof of a defect. Select **Full screen** to expand the panel, browse source lines, and use **Esc** or **Exit full screen** to return. Select **Edit suggestion** to draft a source replacement beside the original lines. You can change the proposed code, preview a unified diff, copy the patch, or load an explicit model-proposed code snippet if one was returned near the cited location. Suggestions are never written to project files by this UI. Changing the approved source snapshot clears drafts. This UI never edits a checkout.

## Source coverage: generic bugs versus explicit full scan

Questions such as `inspect the project for bugs` trigger a bounded focused review **prioritizing eligible production source** over README/pom; it searches up to eight files, not the full repository. The UI must not claim it analyzed the whole project. For real full scope use explicit language such as `full scan of the entire project for bugs`, inspect file coverage/exclusions, then approve the exact snapshot and model-call count. Docs-only never sends program source.

## Evidence-only A/B evaluation and comparison results

After both arms finish, Daeloryn evaluates their stored replies **offline**, without additional provider calls. The evaluator counts deduplicated source-line locations that actually exist in the same approved snapshot and unsupported citations. It shows an explanatory traceability score from 0 to 100 and, only for fully completed comparable arms, a **provisional evidence lead** (Plain Copilot, Daeloryn, tie or inconclusive). It **does not** prove a cited line is a real bug, that a fix works, or that the requested model/agent identity was verified. Independent regression tests and human adjudication remain separate. The main Benchmarks **Comparison results** table polls saved local comparisons; the independent verified-trial table reports external attestations separately.

For older saved runs without a comparison, choose **Evaluate saved run (offline, no AI calls)**. Re-evaluation re-reads the registered local repository and refuses the request if its source digest changed. An incomplete run can be evaluated for diagnostic evidence but is **not** marked comparable; Resume still requires explicit consent for unconfirmed provider calls.
