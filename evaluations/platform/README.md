# Platform evaluation fixtures

**Fixtures are deliberately insecure and must never be deployed or copied into production.**

This is a starting benchmark corpus for Kubernetes, Docker, and CI/CD reviewers. The cases specify expected finding IDs, while `scripts/evaluate_platform.py` validates only that the labels correspond to the fixture text. It is **not** an evaluation of LLM agents.

Run the reference checker:

```bash
python3 scripts/evaluate_platform.py
python3 -m unittest discover -s tests -v
```

To benchmark actual agents, present each fixture **without its expected labels** to the selected agent. Record its findings in a separate machine-readable output, map them to IDs using human-reviewed criteria, and calculate precision, recall and false positives against the hidden labels. A passing CI run must not be presented as proof of agent quality.

## Scoring actual agent outputs

Run each case's prompt **in the selected AI tool**, without giving the agent access to `cases.json`, `score_agents.py`, or other answer keys. Example:

```bash
python3 scripts/prepare_agent_cases.py docker-root
```

Collect outputs in the structure shown by `submission.example.json` (one result per case; include `run_id`, `tool`, and `model`), then score:

```bash
python3 scripts/score_agents.py path/to/submission.json --output scored.json
```

Missing cases count as false negatives. Unexpected finding IDs count as false positives. The score reports micro-averaged precision, recall, and F1, along with per-case finding IDs.

**Limitations:** Finding IDs require human adjudication when an agent produces paraphrases or discovers valid issues not yet labeled. The scorer verifies that evidence is non-empty, not that it is correct. Avoid benchmark contamination: never provide reference labels to the model. CI tests the scorer with synthetic data and does not run or benchmark any external AI model.
