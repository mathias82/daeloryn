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
export EEA_APPROVAL_KEY="<strong-secret-provided-out-of-band>"\npython3 scripts/approval_tokens.py --state .agent-runs/example.json --step gate --actor reviewer\n# Paste the returned token into the next command (avoid shell history in shared machines):\npython3 scripts/execution_engine.py approve --state .agent-runs/example.json --step gate --actor reviewer --reason "Accepted test and security evidence" --token "<signed-token>"
```

Approval now requires an expiring HMAC-signed token scoped to the run, workflow hash and step. The key must be supplied out-of-band, and the signer should operate with a key unavailable to the workflow operator. This is **shared-secret authorization, not verified identity/SSO**. An operator with access to the signing key can self-approve; a state-file administrator can still tamper with the audit log. Never put keys in a repo or CI logs. Protect the local state file using OS permissions and repository policy; do not commit run files or evidence containing secrets.

## Templates and DAG planning

- [Spring feature](../workflows/spring-feature.json) — design → implementation → security & tests → approval → final review
- [Platform release](../workflows/platform-release.json) — container → Kubernetes & supply-chain security → pipeline → approval → release review

```bash
python3 scripts/workflows.py --validate-all
```

The planner computes dependency waves; the execution state machine opens and completes handoffs only in dependency order. Handoffs use manually collected evidence with a SHA-256 fingerprint. There are no automatic retries or external agent invocations.

## Production hardening needed

SSO/OIDC-based verified approver identity, state locking/transaction isolation, durable append-only audit, credential isolation, trusted sandboxed execution adapters, cancellation, retry budgets, timeout enforcement, and authorization checks before actual deployments are **not implemented**. Do not use this tool as a production release gate.
