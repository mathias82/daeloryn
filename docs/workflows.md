# Workflow execution and approvals

The workflow engine implements **local, human-in-the-loop handoffs**. It never invokes an AI model, executes shell commands or deploys workloads. Its approval gates block downstream handoffs until an operator explicitly records approval.

## Dry-run (default: no files written)

```bash
python3 scripts/execution_engine.py start workflows/spring-feature.json --state .agent-runs/example.json
```

## Start and advance a run

```bash
python3 scripts/execution_engine.py start workflows/spring-feature.json --state .agent-runs/example.json --execute
python3 scripts/execution_engine.py status --state .agent-runs/example.json
```

The engine opens the first agent handoff. Run the named agent **manually** in its host coding tool, inspect its actual output, and save the evidence to a local nonempty file.

```bash
python3 scripts/execution_engine.py complete --state .agent-runs/example.json --step design --evidence /path/to/design-review.txt
```

Repeat for dependent steps. After security and testing are completed, the `gate` step becomes `awaiting_approval`. The downstream `finalize` handoff remains `pending`.

```bash
python3 scripts/execution_engine.py approve --state .agent-runs/example.json --step gate --actor "reviewer" --reason "Accepted test and security evidence"
```

This action records a self-declared actor and a reason in the event log. **It is not verified identity, cryptographically tamper-proof approval, or authorization to deploy.** Protect the local state file using OS permissions and repository policy; do not commit run files or evidence containing secrets.

## Templates and DAG planning

- [Spring feature](../workflows/spring-feature.json) — design → implementation → security & tests → approval → final review
- [Platform release](../workflows/platform-release.json) — container → Kubernetes & supply-chain security → pipeline → approval → release review

```bash
python3 scripts/workflows.py --validate-all
```

The planner computes dependency waves; the execution state machine opens and completes handoffs only in dependency order. Handoffs use manually collected evidence with a SHA-256 fingerprint. There are no automatic retries or external agent invocations.

## Production hardening needed

Identity-backed approvals, state locking/transaction isolation, durable append-only audit, credential isolation, execution adapters, cancellation, retry budgets, timeout enforcement, and authorization checks before actual deployments are **not implemented**. Do not use this tool as a production release gate.
