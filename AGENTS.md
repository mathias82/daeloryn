# Repository instructions

This repository distributes agent definitions, a Python installer, evaluation utilities and a declarative workflow planner; it is not an agent execution engine.

- Agent definitions live only in `agents/<module>/<name>.md`, using three-field YAML-style frontmatter: `name`, `description`, `scope`.
- Keep agents original, actionable, concise and technology-specific; avoid copying third-party prompts.
- Do not claim sandbox restrictions from prompt instructions. Host execution permissions take precedence.
- Never add credentials, tokens, production endpoints or customer data to fixtures.
- Run `python3 scripts/agents.py validate`, `python3 scripts/workflows.py --validate-all`, `python3 scripts/evaluate_platform.py` and `python3 -m unittest discover -s tests -v` after changes.
- Update the module catalog documentation when adding an agent; include at least one negative case or evaluation scenario.
- Workflow files belong in `workflows/*.json`; do not claim planner approval nodes enforce authorization or execute agents.
- Security-impacting changes require explicit description and human review.
