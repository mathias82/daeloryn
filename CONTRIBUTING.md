# Contributing

Thanks for helping build engineering agents that can be tested instead of merely described.

1. Open an issue describing the specific engineering gap and desired behavior.
2. Add or update the canonical `agents/<module>/*.md` definition with a narrow scope, clear non-goals and observable output.
3. Add a test or evaluation case for the new behavior. Do not submit copied prompts.
4. Run `python3 scripts/agents.py validate` and `python3 -m unittest discover -s tests -v`.
5. In the PR, describe expected behavior, verified behavior, security implications and remaining limitations.

No real credentials, proprietary code or customer datasets. All contributions are under the MIT license.
