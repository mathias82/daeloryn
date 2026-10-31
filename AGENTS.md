# Repository instructions

This repository distributes agent definitions and a Python installer, not application code.

- Agent definitions live only in `agents/<module>/<name>.md`, using three-field YAML-style frontmatter: `name`, `description`, `scope`.
- Keep agents original, actionable, concise and technology-specific; avoid copying third-party prompts.
- Do not claim sandbox restrictions from prompt instructions. Host execution permissions take precedence.
- Never add credentials, tokens, production endpoints or customer data to fixtures.
- Run `python3 scripts/agents.py validate` and `python3 -m unittest discover -s tests -v` after changes.
- Update README catalog when adding an agent; include at least one negative case or evaluation scenario.
- Security-impacting changes require explicit description and human review.
