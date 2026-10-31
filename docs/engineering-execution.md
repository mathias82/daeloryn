# Engineering execution (opt-in, local-only)

This is an **experimental Python API**, not an autonomous agent or a production sandbox. The existing Copilot review API and UI do **not** automatically invoke these functions.

1. `patch_proposal.propose_with_model(path, original, task, model, transport)` requests a full replacement from a text-only model transport and returns a unified diff plus digest. Source disclosure requires separate explicit approval by the caller; this function itself does **not** implement the approval UI.
2. A human inspects the diff. `engineering_executor.apply_approved(checkout, path, before, after, approved_digest, branch)` requires the exact digest, a clean real checkout, and a new `daeloryn/...` branch. It modifies one local file.
3. `run_tests(checkout, suite, approved=True)` runs an allowlisted command (python/maven/npm) **on the host, without sandbox isolation**. Only use trusted projects; do not run untrusted code.
4. The operator must inspect, commit and push the branch manually. `create_draft_pr(..., approved=True, verified_tests=...)` invokes `gh pr create --draft` with successful evidence supplied by the caller. The evidence is **not cryptographically authenticated**; this is not a secure remote CI attestation.
5. `engineering_pipeline.plan` describes the five handoffs and approvals. It does not run multiple agents.

Not implemented: durable authorization, robust prompt-injection or secret scanning, sandboxed test isolation, retries, agent collaboration, UI patch approval, automated git commit/push, verified GitHub PR checks. Do not expose these local mutation helpers directly through an unauthenticated HTTP endpoint.
