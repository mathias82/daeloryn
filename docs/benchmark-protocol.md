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

The Java source must exist. The output path must be new and outside this repository. Do **not** copy `*-ground-truth.md`, `cases.json`, other evaluation answers, old run transcripts or review instructions into either arm. The preparation script does not prevent a coding host from accessing global memory, parent-directory instructions or other configured connectors; inspect its search/read logs and discard contaminated trials.

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
