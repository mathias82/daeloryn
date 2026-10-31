# Engineering verification cycle (experimental)

This optional CLI implements explicit review → implementation artifact → independent verification. It complements the existing manual workflow state machine; it does not enable the old `agent_adapter.execute()` function or production deployments. Existing Copilot sessions and project copies are not controlled by this CLI.

## 1. Independent Java tests on existing copies

The evaluator source is on `benchmark/hard-java8-checkout-20261031`, outside the main agent catalog. It contains 23 Java 8-compatible contract checks, five safe controls, a Python compiler/test runner and a CI baseline check. Fetch its Git objects, then run from an updated main checkout:

```bash
git pull --ff-only origin main
git fetch origin
python3 scripts/check_checkout_benchmark.py \
  --project /Users/matthaios.stavrou/daeloryn-hard-review/baseline \
  --execute-checks
python3 scripts/check_checkout_benchmark.py \
  --project /Users/matthaios.stavrou/daeloryn-hard-review/daeloryn \
  --execute-checks
```

Without `--execute-checks`, only provenance/preparation validation happens. Evaluation resolves the suite branch once to a commit and records its hash. Use `--suite-ref COMMIT_SHA` for the exact same frozen suite in repeated runs; record the same commit before running either arm. It compares the pinned original and existing candidate with evaluator-owned tests in disposable reconstructions, without altering either existing project. Exit 0 means candidate assertions passed, 1 means a check failed, and 2 means invalid input or wrapper setup failed. Inspect the nested check exit code: Java assertion failure uses 1; compilation/missing or incomplete assertion output uses 2. A compiler failure is not a reproduced behavioral defect.

The v1 trial fixes the production file set, README contract and pom. An added/deleted helper or changed build requires a separately preregistered extended trial; the wrapper rejects these rather than silently scoring a partial patch. It ignores candidate test scripts/build output and compiles against Java 8 platform APIs. This does not establish Maven dependency compatibility, bytecode behavior on an actual Java 8 runtime, full code quality or security. Concurrency assertions are schedule-sensitive. Unknown charge outcomes cannot be fully reconciled using the supplied fixture interfaces. The failed-refund check requires retained save/refund error provenance from the implementation task; alternatives need adjudication. See evaluator documentation on the benchmark branch for coverage and limitations.

These are public development tests used during implementation. They are not unseen holdouts. Local observed results were 5/23 for the original and 23/23 for a temporary manually authored correction used only as a consistency control. Neither result is a real model/provider comparison.

## 2. Structured handoff

`engineering_handoff.py` reuses the source-evidence auditor and pins cited code plus explicitly selected caller/config/build context. The developer must resolve each actionable finding once, declare fixed/rejected/unresolved with rationale and regression assertions, and identify the exact review hash. Changed context or quotes require re-review. A rejection is not silently accepted as a completed correction. These checks validate structure/provenance, not semantic truth or whether a proposed test was executed.

```bash
python3 scripts/engineering_handoff.py --root /project seal \
  --report /private/review.json --context pom.xml
python3 scripts/engineering_handoff.py --root /project check \
  --handoff /private/handoff.json
```

The seal command prints the handoff JSON. Persist it externally as appropriate. The input report follows the [review proof gate](review-proof-gate.md) schema. A fix artifact has `review_sha256`, a `files` mapping of editable path to complete UTF-8 replacement, and `resolutions` entries containing `finding`, `status`, `rationale`, `regression_assertions`.

## 3. Observability

The cycle records stage state, attempts, content hashes and optional observed provider usage in SQLite. Optional `--trace /private/run.jsonl` writes content-free spans with hexadecimal trace/span IDs and start/end times. Only allowlisted numeric counters and validated hashes can enter traces. Raw source, prompts, paths, API keys, tool outputs and error strings are excluded. Telemetry failure preserves the business outcome and increments a dropped counter; the CLI warns without printing sink details. Hashes are correlation metadata, not anonymization guarantees. Local trace and state stores are not tamper-proof audit systems; protect their directory. Newly created SQLite databases and JSONL trace files use mode 0600.

`engineering_telemetry.otel_exporter(tracer)` is an optional Python bridge to an operator-configured OpenTelemetry SDK tracer/exporter. The base install does not require that SDK and configures no external telemetry destination. SDK/exporter end-to-end behavior needs separate integration validation; local sanitization/sink-failure behavior is tested offline.

## 4. Provider and execution boundaries

`openai_artifact_adapter.py` is an opt-in OpenAI Responses integration. It sends selected source to a fixed HTTPS endpoint with certificate verification and redirects disabled, `store=false`, a bounded output token limit, no tools and no automatic retries. `store=false` is not a promise of zero provider-side retention; apply the organization's API data policy. The response is a Structured Outputs envelope containing a JSON artifact, then host code validates the review/fix independently. No model-provided command executes and no generated patch is applied to the user's originals. Refused, incomplete, invalid or unknown responses cannot advance acceptance.

The adapter requires an explicit model and `OPENAI_API_KEY` provided through a trusted environment/secret mechanism. Never put credentials in source, JSON artifacts or prompts. Live API calls are not performed by CI. Mocked transport tests do not establish model availability or provider quality. Usage is recorded only when returned; no token/cost estimates are invented. The model has no execution tools. The optional host-controlled repair stage can run pinned visible tests between data-only patch responses; independent execution remains a separate final stage.

For candidate execution use `--sandbox-image registry/toolchain@sha256:DIGEST` with an explicitly reviewed, preloaded image. Containers get only the disposable read-only reconstruction, no inherited credential environment, no network, dropped capabilities, nonroot UID and CPU/memory/PID limits. Docker auto-pull is disabled. Timeout cleanup is attempted for the uniquely named container; the report marks cleanup as unverified if removal cannot be confirmed, including already-auto-removed containers. This is container hardening, not a guarantee against kernel/container escape. Image contents and dependencies must be reviewed separately. Alternatively, `--allow-host-execution` explicitly accepts execution with caller permissions. No original project directories are mounted or modified.

## 5. Checkpoints and recovery

First prepare a trial using [implementation verification](implementation-verification.md). The trial owns `evaluator/source`, `evaluator/suite` and a pinned manifest. Keep evaluator state inaccessible to model sessions. Then:

```bash
python3 scripts/engineering_cycle.py --db /private/cycle.sqlite start \
  --trial /trials/prepared-r1 --arm daeloryn --model YOUR_EXPLICIT_MODEL
# Copy the returned run_id into RUN_ID below.
python3 scripts/engineering_cycle.py --db /private/cycle.sqlite step \
  --run RUN_ID --stage review --execute-provider --trace /private/run.jsonl
python3 scripts/engineering_cycle.py --db /private/cycle.sqlite step \
  --run RUN_ID --stage implement --execute-provider --trace /private/run.jsonl
python3 scripts/engineering_cycle.py --db /private/cycle.sqlite step \
  --run RUN_ID --stage verify --execute-checks \
  --sandbox-image registry/toolchain@sha256:YOUR_REVIEWED_DIGEST
python3 scripts/engineering_cycle.py --db /private/cycle.sqlite status --run RUN_ID
```

For default-vs-specialist artifact trials use identical model, budget, source/suite and tasks; only `--arm` changes which agent instructions are included. The baseline receives no specialist definition. These OpenAI API runs are distinct from default Copilot sessions; do not mix their results.

Use `--import-artifact /private/review.json` or `/private/fix.json` instead of `--execute-provider` for manual handoffs. Imported artifacts are not proof of a provider run. The verifier reconstructs both original and proposed candidate, executes the same pinned checks, and records both outcomes. A stage marked `completed` means execution finished; `accepted=true` requires candidate checks passed. It is not human approval, semantic proof, deployment authorization or a security certification.

SQLite transactions allow one attempt to claim a stage. Completed stages return stored artifacts without repeating external operations. A stale worker cannot overwrite the result of a newer attempt. Interrupted/provider-unknown stages do not automatically retry. After confirming that the old worker is stopped and reconciling possible paid requests/external effects, an operator may explicitly reset a stage:

```bash
python3 scripts/engineering_cycle.py --db /private/cycle.sqlite recover \
  --run RUN_ID --stage review --acknowledge-unknown-outcome
```

There are at most three attempts per stage. This local operator acknowledgement is not an identity-backed approval protocol. Never reset a still-running worker or assume that a timeout cancelled a remote request. State/config/source/agent/suite changes require revalidation or a new run. The old workflow service's approval controls are unchanged and are not bypassed by this CLI.

## 6. Context budget

Only explicitly declared source/context and the selected specialist are sent. Source includes verified line numbers and hashes. Hidden instruction directories/evaluator paths are rejected; budgets use actual UTF-8 bytes and fail explicitly rather than silently truncating evidence. `--deduplicate-context` optionally removes exact duplicate paragraphs only. Full canonical instructions remain the default. No LLM summaries or automatic rule deletion are used, and token counts are unknown unless observed from the provider. Context compression quality/latency gains remain to be measured.

## Validation limits

Offline tests exercise handoff staleness, incomplete fixes, simulated Responses, provenance, concurrency, checkpoint recovery, retry budgets, redaction, sink failure and original-vs-fixed toy patches. The Java development suite is executed separately. Live OpenAI, Docker execution, OpenTelemetry backend delivery and users' local Copilot sessions were not run in the development environment when unavailable. No cross-provider superiority or production readiness is claimed.


## 7. Automatic visible-test repair (opt-in)

From the tools repository, run `repair` after `step --stage implement` and before `step --stage verify`. The initial artifact is tested first. On a valid failing assertion report the host supplies the visible tests, failed case IDs and latest candidate to the selected implementation specialist. The response must provide cumulative replacements relative to the pinned original and resolve the same reviewed findings. Each candidate is tested in a fresh disposable reconstruction. User project copies are never patched.

The operator supplies a separate, trusted visible suite and JSON plan, for example `/private/visible-plan.json`:

```json
{
  "suite_root": "/private/visible-suite",
  "suite_files": ["check.py"],
  "command": ["python3", "-c", "exec(open('_visible/check.py').read())"],
  "cases": ["valid-order", "negative-quantity"]
}
```

The trusted command must output one JSON object with exactly the preregistered case IDs. Each case has `id`, `status` (`passed` or `failed`) and a positive integer `assertions`; exit 0 means all passed, exit 1 means at least one failed. Example:

```json
{"cases":[{"id":"valid-order","status":"passed","assertions":2},{"id":"negative-quantity","status":"failed","assertions":1}]}
```

Missing/duplicate/skipped/zero-assertion cases, truncated output, crashes, compilation/setup errors and timeouts produce `inconclusive`, stop the loop and block acceptance. Ordinary pytest/JUnit text needs an operator-owned structured adapter; it is not silently treated as a valid assertion report. Test files, case IDs, argv and budgets are pinned in SQLite. The model cannot modify these through its artifact. This protocol is not protection against a malicious candidate forging stdout or escaping a trusted host execution environment.

```bash
python3 scripts/engineering_cycle.py --db /private/cycle.sqlite repair \
  --run RUN_ID --plan /private/visible-plan.json \
  --max-repairs 3 --max-seconds 300 --max-output-tokens 4096 \
  --execute-provider --execute-checks \
  --sandbox-image registry/toolchain@sha256:YOUR_REVIEWED_DIGEST
# Only after visible success, run the independent evaluator:
python3 scripts/engineering_cycle.py --db /private/cycle.sqlite step \
  --run RUN_ID --stage verify --execute-checks \
  --sandbox-image registry/toolchain@sha256:YOUR_REVIEWED_DIGEST
```

Use `--allow-host-execution` instead of the image only for trusted code with caller permissions. Commands are operator-selected argv, never model output. A container still uses the existing preloaded/digest-pinned/no-network/nonroot restrictions. Verify the image provides the declared command. This feature does not modify OS/host permissions or legacy approval controls.

`--max-repairs` bounds additional provider calls (1..10); the initial implementation is outside this repair budget. `--max-output-tokens` bounds output per repair call, so the requested repair output allowance is at most their product. Input is bounded separately by the run's context-byte budget. Currency costs depend on actual provider usage/pricing and are not estimated. `--max-seconds` (1..3600) bounds work scheduling and each subprocess/provider request gets a timeout bounded by remaining time. Network read semantics, process startup and container cleanup can exceed the scheduling deadline; this is not a hard real-time cancellation guarantee. A candidate returned after the budget is exhausted cannot be accepted without its tests.

Repeated candidate hashes stop as `stalled`. Exhausted attempts/time, unresolved findings, invalid/undeclared edits and unknown provider effects cannot be accepted. Unknown/in-flight loops have no automatic retry or reset: stop the old worker, reconcile any paid request or external effect, then explicitly create a new reviewed run if needed. Completed repair commands with the same pinned policy return their cached result without re-executing checks/calls. `status` exposes repair state/outcome. A non-passing repair exits 1; invalid/unknown execution exits 2. SQLite stores candidate artifacts and provider usage/model/response identifiers; protect this private content store. No credential values are intentionally included.

Frozen independent evaluator files/output never enter the repair prompt. The CLI rejects visible roots inside/around the trial and byte-identical evaluator files. The operator must still select genuinely separate public tests and review commands/dependencies for disclosure; these checks cannot prove semantic independence or block a host process from reading unrelated paths. Independent verification runs once after candidate selection and receives the repaired artifact; a visible pass alone never sets `accepted=true`. A failed independent check is terminal for that run's selection and is not fed back into repair.

Specialists can be chosen at run creation for Java, Spring, React, platform and shared review tasks:

```bash
python3 scripts/engineering_cycle.py --db /private/cycle.sqlite start \
  --trial /trials/prepared-react --model YOUR_EXPLICIT_MODEL \
  --reviewer-agent react-reviewer --developer-agent react-developer
```

Use the appropriate specialist and matching prepared trial/tests. Reviewer/architect definitions can be selected for the read-only review stage; they are rejected as implementation/repair executors. A baseline arm retains generic instructions with identical repair tasks and budgets. Offline integration tests use real Python assertion subprocesses and mocked provider responses; they establish orchestration, not model quality, live API success or Docker isolation.
