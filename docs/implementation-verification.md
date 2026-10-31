# Implementation verification and production quality

## What ships

All 22 agents require evidence verification, source-grounded failure simulation and executable fix verification when implementation is requested. Each also has a distinct specialty acceptance check covering code quality and production behavior. The 88 generated host adapters preserve these instructions. Instruction integrity tests do **not** prove that an LLM follows them.

`scripts/verify_implementation.py` supplies an opt-in paired implementation trial, rather than another review scoring prompt. It does not invoke providers. Existing checkout benchmark fixtures stay on `benchmark/hard-java8-checkout-20261031`; no answer keys or benchmark implementations are added to the main agent catalog.

## Preparation

An independent evaluator selects source, build context, editable files, test files and explicit commands **before** either model runs. Use an independently authored suite outside the candidate workspace and keep answers/transcripts out of both arms. The generic runner supports any installed toolchain; it does not install a JDK, dependencies, linters or an observability stack.

For the Java checkout benchmark, use `java-developer` for implementation rather than selecting a read-only reviewer. Select all eight Java source files using repeated `--file`; mark the files each participant may change with repeated `--editable`. Include the original `pom.xml` as frozen context. Predeclare any new helper file as a common empty stub in the initial project, or design another trial: this version evaluates a fixed file set and does not support additions/deletions.

Example invocation (replace paths with real files; this example was not a provider run):

```bash
python3 scripts/verify_implementation.py prepare \
  --project /trial-input/project \
  --file src/main/java/example/Inventory.java --file pom.xml \
  --editable src/main/java/example/Inventory.java \
  --suite /private/evaluator-suite --suite-file run_checks.py \
  --checks /private/checks.json \
  --agent java-developer --output /trials/inventory-r1
```

`checks.json` maps independently chosen gate names to argument arrays; no shell interpretation is performed. For example, `{"correctness": ["python3", "_suite/run_checks.py"]}`. The evaluator-owned script can compile sources with the actual target (e.g. `javac --release 8` on an installed compatible JDK), run assertions and propagate nonzero failures. A Maven-based evaluator must use a frozen, evaluator-owned test/build configuration; never run a candidate-supplied test script or accept candidate test output as evaluator evidence.

Preparation creates byte-identical source in `baseline/` and `daeloryn/`, a Copilot-format selected agent only in `daeloryn/.github/agents/`, and an `evaluator/` directory containing pinned originals, tests and manifest. For other hosts, install/select the same canonical agent using the normal host installer and record the generated definition hash separately. The evaluator directory must be inaccessible to model sessions through actual host isolation; separate directories alone do not provide this.

## Run and evaluate

1. Freeze the same implementation prompt, contract, source snapshot, toolchain, host/model version, budgets and permissions. Verify no baseline custom instructions and actual specialist selection in the Daeloryn arm. Keep each transcript and note any contamination. Use new sessions and randomize/repeat order.
2. Run the suite against `original` before either implementation. Inspect failures: demonstrate the targeted assertion fails for the defect, while positive paths and safe controls pass. Missing dependencies or compilation/setup errors do not establish a useful regression test.
3. Ask each actual provider to implement the complete correction and its own regression tests in its arm. Do not reveal evaluator tests or answers. Candidate-authored tests are useful review evidence but cannot replace independent tests.
4. Evaluate both arms with the same frozen manifest and suite:

```bash
python3 scripts/verify_implementation.py verify --trial /trials/inventory-r1 --arm original
python3 scripts/verify_implementation.py verify --trial /trials/inventory-r1 --arm baseline
python3 scripts/verify_implementation.py verify --trial /trials/inventory-r1 --arm daeloryn
```

Each named gate runs in a fresh temporary reconstruction containing only declared candidate files plus the pinned evaluator suite under `_suite/`. Frozen context changes, missing files, symlinks and altered evaluator snapshots are rejected. Candidate copies of evaluator scripts and stale build output never enter reconstruction. The runner records commands, exit codes, output (last 64 KiB per check, truncation marked), source/test/manifest hashes and changed selected files. Exit 1 means a check failed/timed out/could not launch; invalid inputs exit 2. Preserve the returned JSON and full provider transcripts externally. A check returning zero is recorded as passed; the evaluator must inspect test counts, skipped assertions and warning-only tools. The tool does not understand arbitrary test-runner semantics.

## Acceptance dimensions

| Dimension | Independent evidence | Blocking criterion |
| --- | --- | --- |
| Correctness and recovery | Positive/boundary/negative assertions; injected timeouts, partial success, duplicate retries and failed compensation; final state and error provenance | Any required invariant fails |
| Code quality | Compiler/linter/static analysis on the same versions; blinded human review of naming, cohesion, complexity and patch scope | New required-tool failures or a material maintainability regression |
| Observability | Captured logs/spans/metrics; correlation continuity, error visibility, bounded labels, redaction; telemetry-sink failure test | Required signals missing, sensitive data leaked or telemetry changes the business outcome |
| Security | Authorization/tenant/negative controls; dependency and secret scans where applicable | Critical supported security regression, regardless of aggregate score |
| Compatibility | Actual source/bytecode/runtime target; API/event contracts and migration checks | Unsupported APIs or broken required contracts |
| Performance and reliability | Comparable environment/workload, latency distribution, allocation/query counts, bounded queues and overload recovery | Preregistered budget exceeded; no estimated performance wins |

Only configure gates backed by a real contract and executable checks. Record absent tools as not run, and irrelevant dimensions as not applicable with reasons in evaluator notes. Do not use a no-op command as evidence for observability or security. For Java examples, compile on the configured target; runtime-only availability does not establish compiler availability.

Compare each corrected arm with the original and with the other arm. Require all critical checks before considering aggregate scores. Use blinded maintainability review: automatic suite success alone cannot rank readability. A tie or insufficient evidence is a valid result. No provider run, full code quality equivalence, or general superiority is established by the offline toy regression suite.

## Execution and trust limits

This is an explicit **code-execution** tool, with the caller's environment, network and filesystem permissions. The evaluator manifest and commands are trusted inputs; hashes detect accidental snapshot changes, not a malicious evaluator that edits hashes too. Candidate code can attempt filesystem/network/process access. Use a real disposable container/VM with no secrets, limited network/resources and inaccessible evaluator storage for untrusted candidates. POSIX timeout kills the process group; on non-POSIX hosts only the direct child is killed. Fresh reconstruction prevents ordinary build/test contamination; it is not hostile-code confinement. No CI workflow automatically executes candidate code through this utility.

## One-command paired evaluation after actual model runs

After preparing a trial and running **both** baseline and specialist sessions
in isolated workspaces, evaluate the original, baseline and Daeloryn arms
against identical frozen evaluator checks:

```bash
python3 scripts/compare_implementation_trials.py \
  --trial /trials/inventory-r1 \
  --output /private/reports/inventory-r1.json
```

Use `--sandbox-image` with a locally available digest-pinned Docker image
for stronger isolation of candidate code. The report includes each arm's
gate statuses, manifest and evaluator hashes, and a conservative outcome:
tie, one arm passed, neither passed, or invalid comparison. It fails closed
when evaluator manifests or suites differ or verification errors occur.

**This command does not invoke an AI model.** An actual live-provider
benchmark additionally requires separately authenticated provider execution,
fresh sessions, model identity, raw transcripts, source hashes and an
independent check that each host used the intended agent. The comparison
result alone is never evidence that any provider was called.
