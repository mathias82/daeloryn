# Single-command Java checkout engineering workflow (experimental)

This opt-in CLI stages the **public Java 8 checkout development exercise only**:
read-only-focused Copilot review → human-approved interactive fix → pinned
independent evaluator → an evidence-limited PASS/FAIL report. It is **not**
a production agent orchestrator, sandbox, proof of semantic correctness or
Copilot-vs-Daeloryn superiority.

## Prepare a disposable Java checkout copy

From the Daeloryn tools checkout:

```bash
git fetch origin
python3 scripts/agents.py install --target "$PROJECT" --module java --tool copilot
```

`PROJECT` must refer to the operator-owned disposable Java 8 checkout copy,
not the Daeloryn source repository or a production project. The copy must
include the exercise README.md, pom.xml and existing production source set.

Create UTF-8 operator-owned prompt files `/tmp/daeloryn-review.txt` and
`/tmp/daeloryn-fix.txt`. A real installed and authenticated Copilot CLI
and compatible github-copilot-sdk are required.

## Run the complete cycle with one command

```bash
python3 scripts/checkout_workflow.py \
  --project "$PROJECT" \
  --review-prompt /tmp/daeloryn-review.txt \
  --fix-prompt /tmp/daeloryn-fix.txt \
  --timeout-seconds 900 \
  --report /tmp/checkout-workflow-result-1.json \
  --execute
```

The runner discovers models once and selects by the existing model_router policy:
`java-reviewer` for review, `java-developer` for implementation. Model IDs
in the report are *requested*, not verified effective provider IDs.

1. **Review**: non-interactive CLI with explicit `--deny-tool=write` and
   `--deny-tool=shell`. The runner captures bounded output and compares
   source/build hashes after review. These restrictions are not a sandbox.
2. **IMPLEMENT**: the operator reads the report and types exactly `IMPLEMENT`.
   The review output is included only as **untrusted diagnostic data**; the
   developer must independently validate findings. Declining stops the cycle.
3. **Fix**: a **native interactive Copilot session** with ordinary host
   approvals, no blanket allow-all flag. Approve each edit or command as
   appropriate, then enter `/exit` to return to the workflow. The runner
   checks that README.md, pom.xml and the original production Java file set
   remain unchanged. It does not automatically retry failed/unknown actions.
4. **VERIFY**: type exactly `VERIFY` to authorize the existing
   `check_checkout_benchmark.evaluate()` host checks, which reconstruct
   disposable sources and run 23 original and five recovery checks. The
   evaluator suite branch is resolved once to a SHA *before* provider use.
5. **Quality report**: PASS requires the evaluator's overall passing status
   and both named checks with successful exit codes. Reports include only
   checks, changed production paths, requested models and hashes—not prompts
   or raw source. `--report` creates a private mode-0600 JSON file and
   refuses to overwrite an existing file.

The runner does **not** run without `--execute` and an interactive terminal.
Review output is capped at 128 KiB, prompts at 64 KiB each, and each local
Copilot session has a configurable 1–3600 second timeout. A timeout is not
proof of remote cancellation, rollback, absence of cost or child cleanup.
For the interactive session, termination is only best-effort for the local CLI
leader. The operator must reconcile changed files or remote effects before
another attempt.

The evaluator uses host privileges in this workflow and compiles Java with
the Java 8 target. It is only appropriate for trusted development fixtures.
Pinning checks and preserving the README contract does **not** establish
real-JDK-8 runtime behavior, production safety, or held-out model accuracy.
The 28 public checks were exposed during previous development, so benchmark
PASS cannot be presented as a blinded model comparison.

This is an **initial supported workflow**, not a general solution for Java,
Spring, React or deployment. Provider/SDK/CLI end-to-end execution is not run
by CI. Offline unit tests mock the host boundary and exercise sequencing,
approvals, provenance gates and refusal modes.
