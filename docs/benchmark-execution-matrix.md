# Controlled benchmark execution matrix — 24 actual trials per configuration

Status: **NOT RUN**. This is a preregistered experiment, not observed data.

## Fixed conditions

- Run each configuration twice per fixture (4 fixtures × 3 repetitions × 2 arms = 24 runs **per provider**, 96 runs across four providers). Baseline and specialist arms must use the same actual model version and host for valid comparisons.
- Use deterministic pairing: the same fixture and model version in baseline and specialist arms, separated into fresh isolated sessions.
- Randomize order within each pair by a recorded seed and record model randomness options when the host exposes them.
- Include only read-only filesystem access to a disposable checkout; prohibit execution/deployment and keep secrets out.
- Hide gold reference labels from models and reviewers assessing generated output; reviewers may access fixture code and reproducible test evidence.
- Keep original transcript and tool-reported timings/token usage in non-public secured storage, with SHA-256 provenance. Never invent unavailable token usage.

## Trial identifiers

For each provider in `codex, claude, copilot, gemini`, run these 24 trial slots:

| Case | Baseline IDs | Specialist IDs |
| --- | --- | --- |
| Java 25 interruption | java25-baseline-r1/r2/r3 | java25-agent-r1/r2/r3 |
| Spring transaction boundary | spring-baseline-r1/r2/r3 | spring-agent-r1/r2/r3 |
| React security/list identity | react-baseline-r1/r2/r3 | react-agent-r1/r2/r3 |
| Kubernetes hardening | k8s-baseline-r1/r2/r3 | k8s-agent-r1/r2/r3 |

These are **trial slots**, not results.

## Independent evidence review

Two reviewers separately assign a 0/1/2 evidence grade for each proposed finding, together with a reason and source line. Disagreements require adjudication before scoring. A correct finding ID with an unsupported snippet must not count as a verified evidence success. Record inter-reviewer agreement and publish only aggregated, redacted results.

## Progress threshold

Do not claim a measured improvement without actual runs, preserved outputs, adjudication and a baseline comparison. Current status: 0 verified completed provider trials, 0 verified reviewer assessments, 0 pilot repository results in the evidence provided to this project.
