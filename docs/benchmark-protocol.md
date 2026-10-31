# Reproducible provider benchmark protocol

**Current status: harness implemented; no verified real provider results have been published.** Do not confuse reference fixtures, synthetic tests, or a manually authored submission with a real Codex/Claude/Copilot/Gemini run.

## Scope and comparison

Use the four deliberately unsafe fixtures in `evaluations/engineering`: Java 25, Spring, React and Kubernetes. They contain eight planted findings. Keep the gold labels in `cases.json` **out of the model context**. Run each case twice using the same exact provider/model version and environment: (a) normal baseline instructions and (b) the corresponding installed specialized agent. Randomize order and repeat across several runs; keep full responses, exact prompts, tool versions, execution time, token use where actually measurable, and any failures. Do not compare different providers as if they were controlled same-model baseline comparisons.

## Blinded Java review workspaces (Copilot)

For Java review comparisons, prepare each repetition as a **new** isolated trial directory outside the Daeloryn checkout. The preparation script copies only the requested Java source into the two model-visible workspaces and installs **only** the Java reviewer definition in the specialist arm. It writes SHA-256 provenance to a manifest outside both arms; it does not invoke AI models or generate results.

```bash
python3 scripts/prepare_blind_java_review.py \\
  --source /absolute/path/to/UNSEEN/JavaCase.java \\
  --output "$HOME/daeloryn-trials/java-case-r1"
```

The Java source must exist. The output path must be new and outside this repository.

For **actual Java/Spring projects**, use a project root and explicitly include the needed build and dependency-context files in both arms, so the same Java version and caller contracts can be checked without the reviewer guessing:

```bash
python3 scripts/prepare_blind_java_review.py \\
  --source "$HOME/daeloryn-java8-test/src/main/java/Inventory.java" \\
  --project-root "$HOME/daeloryn-java8-test" \\
  --include pom.xml \\
  --output "$HOME/daeloryn-trials/inventory-independent-r1"
```

This preserves `src/main/java/Inventory.java` and `pom.xml` paths under **both** arms, verifies byte hashes in `manifest.json`, and installs the reviewer only under the `daeloryn` arm. Use `--include` again for other explicitly needed source, config or build files. Hidden agent instructions, answer keys, gold-label files, recursive project copies and out-of-root paths are disallowed. For a fair **unseen holdout**, choose new code that was not previously used to tune the agent. The public `Inventory.java` example is a teaching case, not a blind holdout. Do **not** copy `*-ground-truth.md`, `cases.json`, other evaluation answers, old run transcripts or review instructions into either arm. The preparation script does not prevent a coding host from accessing global memory, parent-directory instructions or other configured connectors; inspect its search/read logs and discard contaminated trials.

Run Copilot CLI from `.../java-case-r1/baseline` for the baseline, and from `.../java-case-r1/daeloryn` for the specialist. In the latter, select `/agent` → `java-reviewer` and verify the host reports the custom agent as selected; otherwise the run is **not** a Daeloryn trial. For the baseline, verify no custom agent or project-specific instructions were activated. Use the same host, model ID/version, read-only prompt, tool permissions and fresh session for each arm.

Record each run's original transcript, source hash, agent hash (from `manifest.json`), model version, evidence, duration if observed, and reviewer adjudication **outside** the model-visible workspaces. Review source-line claims and duplicate root causes before computing scores. Mark unverified times and token costs as missing; never estimate them.

**Holdout rule:** Fixtures used while tuning `java-reviewer` (including `Java25Worker.java` and `Java25Ledger.java`) are development examples, **not** unseen holdouts. Do not use subsequent tests on those fixtures as independent proof of superiority. Collect new consented/independently-authored cases and preregister expected findings before revealing either arm's output.

## Capture protocol

1. Generate a blinded case prompt: `python3 scripts/evaluate_engineering.py --prompt java25-interruption`.
2. Run this prompt in the actual coding tool. The runner intentionally does **not** launch provider CLIs: their auth, CLI interfaces, model names and sandbox behavior require host-specific configuration.
3. Store a JSON submission with `cases` entries; each finding needs `id`, nonempty `evidence`, `line` (1-based), and `quote` (exact substring of the source line). Keep a separate original provider transcript with secrets removed.
4. Record the claimed provider/model and a unique run ID. Run the recorder:

```bash
python3 scripts/record_benchmark.py \
  --submission /secure/recorded-codex.json \
  --reference evaluations/engineering/cases.json \
  --provider codex --model MODEL_VERSION --run-id codex-001 \
  --output /secure/records/codex-001.json
```

Repeat with `--provider claude`, `copilot`, `gemini` **only after running that actual provider**.

5. Summarize available records:

```bash
python3 scripts/summarize_benchmarks.py /secure/records/*.json
```

Missing providers appear explicitly as **missing**, never as zero scores or fabricated experiments.

## Evidence review rubric

The automatic verifier checks only whether the submitted `quote` appears on the claimed `line` of the fixture. That guards against some fabricated locations, not incorrect causality. Each finding also needs blinded human review:

- **0 — unsupported:** quote/line is wrong, no plausible code-level evidence, or clear false positive.
- **1 — partially supported:** code exists, but impact or reproduction remains unclear.
- **2 — verified:** source confirms the issue and concrete, reproducible failure mechanism is documented.

Have at least two reviewers independently assess ambiguous findings; reconcile disagreements and keep adjudication notes. Record false positives, missed findings, precision/recall/F1, case-by-case evidence grade, time/cost and variance across repeats. Never claim a model's superiority from these four teaching cases alone.

## Security and reproducibility

Never run the unsafe fixtures in production or let tools deploy them. Treat fixture text and model outputs as untrusted. Keep API tokens out of the repository and do not publish provider transcripts containing secrets or proprietary customer code. Do not store fake model runs as observational data. Preserve the original output and audit trail independently from the normalized scoring JSON.

## Next stage: working code, not only reviews

Use the [implementation verification protocol](implementation-verification.md) for paired implementation trials. Both participants must implement fixes, then an independent evaluator runs the same frozen tests and quality checks on reconstructed copies. Preserve the dedicated `benchmark/hard-java8-checkout-20261031` fixture branch; its public case is a development benchmark, not an unseen holdout. Read-only review scores cannot establish implementation quality.

## Strict evidence and corpus provenance (opt-in)

For a complete recorded cross-stack review, add `--strict` to
`scripts/record_benchmark.py`. This rejects missing cases and any finding
whose claimed quote is not present at the cited source line. The recorder
also embeds a SHA-256 fingerprint of the reference JSON, so
`scripts/summarize_benchmarks.py` rejects comparisons across different
reference corpora. Legacy records without fingerprints remain individually
viewable; a summary mixing fingerprinted and unverified records fails.

These are **structural integrity gates**, not proof that a model was called,
that a quoted finding is semantically correct, or that a code patch passes
tests. Human review and independently executed fix verification remain
mandatory before publishing comparative results.

## Opt-in local provider CLI capture (POSIX)

After independently preparing baseline and Daeloryn workspaces, a trusted
operator may run a locally installed provider CLI using an explicit argv
(no shell interpolation). Example for a configured Copilot CLI:

```bash
python3 scripts/capture_provider_cli.py \
  --arm /trials/example/baseline --provider copilot --model MODEL_ID \
  --output /private/records/copilot-baseline.json -- \
  copilot --model=MODEL_ID --prompt="Review this project"
```

Repeat in the Daeloryn arm with the appropriate selected agent, then run
the independent evaluator and retain all reports. This command captures
local CLI output, limits retained output to 1 MiB and terminates local POSIX
process groups on timeout. It does **not** automatically validate CLI
arguments, provider authentication, actual remote model selection, agent
activation, or sandbox isolation. Use separate externally enforced host
isolation and a trusted command. Never enable permissive unattended
write/deploy flags on untrusted code.

**Sensitive data:** the captured transcript may contain secrets. Store
reports only in private access-controlled storage, inspect/redact before
sharing, and do not upload them as public CI artifacts. Timeouts leave
remote outcomes unknown; do not automatically retry. This opt-in capture
is a building block, not a completed four-provider unattended benchmark.

## Full catalog coverage matrix and machine-readable dashboard

```bash
python3 scripts/benchmark_matrix.py --output /private/reports/coverage.json
python3 scripts/benchmark_matrix.py /private/trials/*.json
```

The matrix is derived from the **current** agent catalog and four named
providers, with separate baseline and specialist arms. For 22 agents this
means 176 expected agent/provider/arm cells, not 176 completed experiments.
Missing cells are explicit. Records must use schema version 1, kind
`benchmark-trial`, and provide `agent`, `provider`, `arm`,
`run_id`, and an evaluator `outcome` (one of the paired evaluator
outcomes). Duplicates and unknown catalog entries are rejected.

A record counts toward verified outcomes only if
`model_identity_verified`, `agent_selection_verified`,
`independent_checks_executed`, and `comparable` are all true.
These are **attestations supplied by the trial operator**, not independently
validated cryptographic proofs; preserve evidence and review externally.
Do not synthesize benchmark-trial records from CLI exit codes alone.

This is a coverage/reporting stage. Fully unattended, securely isolated
provider execution across all 22 agents remains a separate integration task,
requiring each provider's supported CLI/SDK contract, authorized credentials,
per-agent benchmark tasks, trusted external isolation and human review.

## Join live CLI capture with independent evaluator results

After both provider captures and `compare_implementation_trials.py` finish,
assemble a single machine-readable record:

```bash
python3 scripts/assemble_benchmark_trial.py \
  --agent java-reviewer --provider copilot --run-id java-review-r1 \
  --comparison /private/reports/java-review-r1.json \
  --baseline-capture /private/records/baseline.json \
  --daeloryn-capture /private/records/daeloryn.json \
  --output /private/trials/java-review-r1.json
python3 scripts/benchmark_matrix.py /private/trials/java-review-r1.json
```

The assembler rejects incomplete CLI captures, provider mismatches and missing
or incomplete evaluator arms. It hashes input capture files and **never**
claims to have verified the actual model, selected agent or sandbox isolation.
The output is an unverified record for coverage tracking; it does not
establish comparative AI performance. Capture logs can contain sensitive
information: keep all trial files private. Real unattended execution still
requires provider-specific adapters, credentials and externally enforced
isolation; this command does not bypass those requirements.
