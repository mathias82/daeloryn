# Platform evaluation fixtures

**Fixtures are deliberately insecure and must never be deployed or copied into production.**

This is a starting benchmark corpus for Kubernetes, Docker, and CI/CD reviewers. The cases specify expected finding IDs, while `scripts/evaluate_platform.py` validates only that the labels correspond to the fixture text. It is **not** an evaluation of LLM agents.

Run the reference checker:

```bash
python3 scripts/evaluate_platform.py
python3 -m unittest discover -s tests -v
```

To benchmark actual agents, present each fixture **without its expected labels** to the selected agent. Record its findings in a separate machine-readable output, map them to IDs using human-reviewed criteria, and calculate precision, recall and false positives against the hidden labels. A passing CI run must not be presented as proof of agent quality.
