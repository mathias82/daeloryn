# Workflow orchestration

The initial workflow layer is a **safe deterministic planner**, not an AI execution engine. It validates agent references, checks dependencies and cycles, and produces execution waves. No code is run, no agent is launched, no external API is contacted, and approval nodes are only modeled.

## Try it

```bash
python3 scripts/workflows.py --validate-all
python3 scripts/workflows.py workflows/spring-feature.json
```

## Included templates

- [Spring feature](../workflows/spring-feature.json): architecture → implementation → security and testing in parallel → approval.
- [Platform release](../workflows/platform-release.json): container review → Kubernetes and supply-chain security → CI/CD → approval.

Each JSON step declares `id`, optional `type` (`agent` or `approval`), an `agent` when applicable, and `depends_on`. A step is eligible only after its dependencies succeed; **eligibility is not permission to execute it automatically**.

## What is missing before live orchestration

1. Host-specific invoke adapters and runtime compatibility tests for Codex, Claude Code, Copilot, and Gemini.
2. Persisted execution state, structured step output, retry budgets, cancellation and resume semantics.
3. Strict approval enforcement and environment-scoped tool permissions.
4. Execution logs, tracing, privacy controls, resource limits and sandboxed dry-run.
5. Integration tests proving blocked actions are never executed before approval.

Do not treat the printed waves or approval markers as an operational authorization control. Human review, actual tool permissions and CI/CD release gates remain required.
