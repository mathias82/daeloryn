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
