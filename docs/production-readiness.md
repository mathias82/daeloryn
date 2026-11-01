# Daeloryn production release gate (not yet certified)

Daeloryn is an alpha engineering console. Existing read-only endpoints and local Python
approval libraries do **not** constitute a secure multi-user execution service.

## Release blockers

1. **Identity and authorization**: authenticated sessions, per-repository authorization,
   CSRF/origin protection, one-time approval persistence and expiry, audit actor identity.
   Keep remote execution and repository write HTTP endpoints **disabled** until reviewed.
2. **Execution isolation**: pin container image digests, prohibit privileged Docker,
   provide writable ephemeral workspaces with offline dependency strategy, bound disk,
   CPU, memory, processes and runtime; validate Docker daemon access and threat model.
3. **Workflow integrity**: atomic cross-process state transitions, idempotency keys,
   recovery of interrupted test jobs, immutable patch and commit evidence, no approval
   reuse across revisions, reject dirty checkouts and concurrent mutation.
4. **Integration**: complete authenticated UI-to-backend-to-agent-to-sandbox-to-GitHub
   flow with distinct approvals for source transmission, patch apply, tests and publish.
5. **Operations**: structured logs with redaction, metrics/alerts, retention policy,
   backup/restore drill, health/readiness, deployment rollback and incident owner.
6. **Verification**: branch protection requires Python and frontend checks; run real
   Docker integration tests, security tests, malicious repository fixtures, crash/restart
   recovery, concurrency and load tests. No critical/high unresolved findings.

## Release procedure

- Freeze release candidate commit SHA; record dependency and container image digests.
- Run required CI on the exact SHA, including newly added regression tests.
- Verify frontend production build and manual end-to-end scenarios on a disposable
  repository, including denied approvals, failed tests, timeout and retry exhaustion.
- Perform a security review of credentials, logs, model prompt context and GitHub scopes.
- Deploy to staging with execution disabled by default; confirm health and rollback.
- Conduct backup/restore and rollback drills; capture outcomes and responsible approvers.
- Enable limited pilot access only after all blockers are resolved and signed off.

## Rollback

Disable execution capabilities first, revoke scoped credentials, stop in-flight workers,
preserve redacted audit records, roll back to the last known-good image digest and
verify the health endpoint. Do not auto-retry publication after an uncertain outcome;
reconcile GitHub PR state first.

## Evidence checklist

Record release SHA, CI run URLs, security review, E2E logs, image digests, restore
result, rollback result, approver, date, and any accepted residual risks.
**No production-ready claim is justified without this evidence.**
