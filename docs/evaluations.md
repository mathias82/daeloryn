# Evaluations

There are three deliberately unsafe Platform fixtures (Kubernetes, Docker and CI/CD) and seven reference findings. **Never deploy or run the unsafe fixtures.**

Reference-data validation:

```bash
python3 scripts/evaluate_platform.py
python3 -m unittest discover -s tests -v
```

Prepare a benchmark prompt without gold labels:

```bash
python3 scripts/prepare_agent_cases.py docker-root
```

Run the prompt in a selected AI tool, collect its result in the structure of `evaluations/platform/submission.example.json`, and score:

```bash
python3 scripts/score_agents.py results.json --output scored.json
```

The scorer reports true positives, false positives, false negatives, precision, recall and F1 for matching finding IDs. It checks that evidence is present but **does not verify evidence correctness** or run the AI tools. Human adjudication is needed for synonyms and valid unexpected findings. Store the tool/model/version and avoid giving reference labels to the evaluated agent.

CI currently tests the reference evaluator and scorer using synthetic data, **not measured AI performance**. See [full evaluation protocol](../evaluations/platform/README.md).

## Cross-stack engineering evaluation (Java 25, Spring, React, Kubernetes)

A second deliberately unsafe fixture corpus is provided under `evaluations/engineering/`. It contains **4 cases and 8 reference findings**, for Java 25-capable code, Spring transaction boundaries, React UI security/correctness and Kubernetes hardening. **Do not deploy or use these snippets in production.**

```bash
# Check fixture/reference consistency only (no model calls)
python3 scripts/evaluate_engineering.py

# Obtain a blinded prompt without the expected finding IDs
python3 scripts/evaluate_engineering.py --prompt java25-interruption

# Score a recorded agent JSON submission against this corpus
python3 scripts/score_agents.py results.json --reference evaluations/engineering/cases.json
```

Use the same submission schema as the Platform corpus. Run the selected agent in an actual host with reference labels withheld, preserve its full output and model/tool version, and have a human adjudicate evidence quality. The offline regex checker only detects planted teaching patterns, while synthetic scoring tests validate arithmetic, **not** observed AI accuracy. Expand with realistic negative fixtures and blinded reviews before publishing quality claims.

## Real-provider benchmark capture

Use [the controlled benchmark protocol](benchmark-protocol.md), `scripts/record_benchmark.py`, and `scripts/summarize_benchmarks.py` to record observed runs with source-line evidence. These scripts **do not invoke AI providers**, and there are currently no verified real-provider measurements in the project.
