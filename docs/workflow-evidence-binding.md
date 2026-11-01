# Approval binding for local workflow publication

The durable workflow stores test evidence for a specific repository, canonical
checkout path, commit, Git tree, dedicated branch, origin push URL, test suite and
suite configuration. It also records a SHA-256 digest of the runner's result.
The publication approval covers that evidence, workflow ID/version and PR metadata.
These are local checks, not a cryptographic attestation from GitHub CI.

## Operator sequence

Use an operator-owned `TrustedCheckoutRegistry`, `WorkflowStore`, authenticator,
`DurableApprovalGate` and test runner. Keep workflow databases, receipts and Python
environments outside the checkout. The checkout must contain only committed inputs;
ignored and untracked files are rejected because the Docker runner copies them too.

1. Prepare the patch and obtain its separate explicit approval as before.
2. Call `workflow_evidence.test_subject(registry, repository, suite)` to display
   the exact test inputs to the operator. After explicit execution approval, call
   `gate.prepare("run_tests", repository, subject["digest"])`.
3. Pass that digest and token to `run_workflow_tests`. A successful result is persisted
   only if the checkout binding still matches after the runner returns. A changed
   checkout or runner exception leaves `tests_running`, requiring reconciliation.
4. After tests pass, call `workflow_evidence.publication_subject(store, workflow_id,
   expected_version, registry, title, body, expected_commit)`. Display its contents.
   The commit must match the persisted test evidence.
5. After a **separate explicit publication approval**, prepare a `publish_pr` token
   for the returned digest and pass both to `publish_workflow_draft`.

Helpers that describe approval subjects do not grant authorization. Token issuance
must remain behind the operator's explicit approval; never expose it as an
unauthenticated web endpoint. Existing workflows with boolean-only test evidence
must run approved tests again before publication.

## Denials and uncertain outcomes

- Invalid credentials, mismatched inputs, wrong/expired tokens and changed PR metadata
  invoke no publisher. Invalid publication approval leaves `tests_passed` available.
- Approval is consumed before the versioned publication reservation. Concurrent
  callers cannot both publish; a losing caller can consume its token without publishing.
- Once `publication_approved` is reserved, errors and unverified publisher responses
  leave it reserved. Do not automatically retry: inspect GitHub and reconcile first.
- The default publisher pushes the approved commit object to the approved URL and
  explicitly passes the authorized repository to `gh pr create --draft`. Publisher
  overrides must accept `expected_repository`, `expected_push_url` and
  `expected_branch`, honor these
  bindings, and report the actual commit and branch in their result.
- Origin must resolve to one matching GitHub HTTPS/SSH push URL; mirror mode is rejected.

## Remaining boundaries

The operator, local Git configuration/hooks, approval/state directories and injected
runners/publishers are trusted. Before/after checks cannot detect a hostile writer
that changes and restores files during a run. This does not provide a filesystem
snapshot, remote branch locking, signed CI attestations or pinned container images.
An independent real Docker-to-GitHub E2E trial, security review and the remaining
[production release gates](production-readiness.md) are still required.
