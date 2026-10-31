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

Approval requires an expiring HMAC-signed token scoped to the run, workflow hash and step. The key must be supplied out-of-band, and the signer should operate with a key unavailable to the workflow operator. These CLI commands are a local demonstration: using the same key and machine for signing and workflow operation does **not** provide separation of duties. This is **shared-secret authorization, not verified identity/SSO**. An operator with access to the signing key can self-approve; a state-file administrator can still tamper with the audit log. Never put keys in a repo or CI logs. Protect the local state file using OS permissions and repository policy; do not commit run files or evidence containing secrets.

## Templates and DAG planning

- [Spring feature](../workflows/spring-feature.json) — design → implementation → security & tests → approval → final review
- [Platform release](../workflows/platform-release.json) — container → Kubernetes & supply-chain security → pipeline → approval → release review

```bash
python3 scripts/workflows.py --validate-all
```

The planner computes dependency waves; the execution state machine opens and completes handoffs only in dependency order. Handoffs use manually collected evidence with a SHA-256 fingerprint. There are no automatic retries or external agent invocations.

## Production hardening needed

SSO/OIDC-based verified approver identity, state locking/transaction isolation, durable append-only audit, credential isolation, trusted sandboxed execution adapters, cancellation, retry budgets, timeout enforcement, and authorization checks before actual deployments are **not implemented**. Do not use this tool as a production release gate.

## Experimental SQLite runtime (opt-in)

The newer `scripts/secure_runtime.py` uses SQLite `BEGIN IMMEDIATE` transactions and WAL journaling for atomic dependency and approval transitions across local processes. It does not invoke a model. It is separate from the legacy JSON state CLI.

```bash
python3 scripts/secure_runtime.py --db .agent-runs/runtime.db start workflows/spring-feature.json
python3 scripts/secure_runtime.py --db .agent-runs/runtime.db start workflows/spring-feature.json --execute
python3 scripts/secure_runtime.py --db .agent-runs/runtime.db complete --run RUN_ID --step design --evidence /path/to/evidence.txt
```

### OIDC-based approval verification

Install `python3 -m pip install -r requirements-security.txt`. An administrator must provision a **trusted** JWKS file and issuer/audience values from their identity provider. The token must be a signed RS256 JWT carrying `iss`, `aud`, `exp`, `iat`, `sub`, `jti` and custom `run_id`, `step`, `workflow_hash` claims. The subject must match an explicit allowlist. This is a token verification interface, **not** an OIDC login/token-issuance flow; a normal identity-provider ID token will not automatically contain the custom claims.

```bash
python3 scripts/secure_runtime.py --db .agent-runs/runtime.db approve --run RUN_ID --step gate --token-file /secure/approval.jwt --jwks /secure/jwks.json --issuer https://issuer.example --audience engineering-approvals --allowed-subject reviewer-subject-id
```

For production authorization, move token validation inside a protected server boundary rather than exposing direct library functions or a writable state DB to untrusted operators. Do not treat the CLI alone as a production authorization service. Key rotation, federation, role mapping and identity-provider integration need environment-specific work.

### Experimental container isolation

`scripts/sandbox_runner.py` is an operator-invoked Docker adapter, **disabled unless `--execute` is supplied**. It requires an image pinned by SHA-256 digest, denies network access, removes capabilities, applies limits, and mounts no host directories. It is not wired to workflow handoffs and does not autonomously run Codex, Claude, Copilot or Gemini.

```bash
python3 scripts/sandbox_runner.py --image example.invalid/review@sha256:DIGEST --prompt "Review a sample" --execute
```

Replace `DIGEST` with an actual 64-character lowercase hexadecimal digest of a trusted, pre-reviewed image. Docker isolation is not a security guarantee against malicious containers; use rootless Docker or stronger sandboxing on a dedicated host for adversarial inputs. No production deployments are authorized.

## Unified execution service (developer preview)

The new `scripts/execution_service.py` combines workflow planning, SQLite state, evidence completion and OIDC-verified approvals behind a single CLI. Unlike the older `execution_engine.py`, the unified service uses transactional SQLite state. It **does not run AI models, containers or deployments**.

```bash
python3 scripts/execution_service.py plan workflows/spring-feature.json
python3 scripts/execution_service.py start workflows/spring-feature.json --execute
python3 scripts/execution_service.py status --run RUN_ID
python3 scripts/execution_service.py complete --run RUN_ID --step design --evidence /path/to/review.txt
```

The `approve` command takes an operator-provisioned trusted JWKS, expected issuer, audience and allowed subjects. For safety, provider adapters currently support validation and dry-run metadata only; `execute()` explicitly rejects real execution. Provider credentials are not read or managed by this project yet. See `scripts/agent_adapter.py`.

**Security boundary:** the Python library and local SQLite database must only be accessible to trusted operators. A caller with direct database access can bypass application-level approval checks. OIDC verification on the CLI is not a remote identity service or production release authorization mechanism.

## Isolated adapter boundary

`agent_adapter.execute_isolated(request, image, enabled=True)` can run a **trusted operator-reviewed image** through the network-disabled Docker sandbox. This is a deliberately narrow local execution path: no host mounts, API credentials, model network connectivity or automatic workflow completion. Provider selection is metadata; it does **not** mean Codex/Claude/Copilot/Gemini are actually invoked. The image must already contain a compatible entrypoint that reads the prompt from stdin. The caller must explicitly opt in and assess the image's safety. The normal `agent_adapter.execute()` remains fail-closed.

Concurrency tests ensure only one transaction can complete a given step. OIDC authorization is still tied to a trusted CLI caller and database access policy; production-grade identity enforcement requires a protected service boundary.
