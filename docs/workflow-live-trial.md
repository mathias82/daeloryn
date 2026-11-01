# Real Docker and separately approved GitHub trial

This trial exercises the durable workflow from a real container run to an opt-in
Draft PR. It uses a disposable local clone and a unique `daeloryn/e2e-*` branch
in the same authorized GitHub repository. It never merges or changes `main`.
Close the trial Draft PR and delete its trial branch after inspection.

## What runs automatically in CI

`Real Docker workflow / Ubuntu` pulls the official Python probe image, records its
immutable digest, then executes offline containers using that digest. These are
real Docker checks, not mocked subprocesses. Missing Docker/image is a failure.

The four scenarios verify:

- successful non-root execution, writable ephemeral workspace, read-only host source
  and root filesystem, no container network and no forwarded GitHub token;
- failing tests block publication;
- a real timeout removes only the runner's unique container and leaves the workflow
  in `tests_running`; a restarted process cannot automatically rerun that trial;
- mutation after successful tests blocks publication before accessing GitHub.

The PR job has read-only repository permissions and never pushes or creates PRs.
The unit suite separately checks cleanup failure, approval binding and uncertain
publication outcomes. Those unit checks are not live GitHub failure-injection tests.

## Live GitHub test: two separate manual invocations

After this workflow is merged into `main`, open **Actions → Approved live workflow
trial → Run workflow**, selecting `main`.

1. Select `phase=tests` and check `approve_tests`. Leave publication approval off.
   This authorizes the small disposable probe fixture and its Docker execution.
   The summary supplies `test_run_id`, `expected_commit` and `approval_digest`.
   No publication approval token is minted at this stage.
2. Review the successful run and the exact commit/digest. Start a **new invocation**
   with `phase=publish`, check `approve_publication`, and copy those three values.
   This phase accepts only a successful source run of this exact workflow revision
   from `main`, restores its durable state, and verifies the supplied commit/digest
   before issuing a short-lived single-use approval.
   Before pushing, it atomically creates a uniquely named
   `daeloryn-e2e-claim-*` Git tag. An existing claim blocks another publication,
   even if the earlier workspace is lost or the tests artifact is restored again.
3. Inspect the resulting Draft PR. Its only new content is a disposable probe test.
   Do not merge it. Close it and delete its uniquely named trial branch.

The tests artifact and publication-state artifact are retained for seven days.
They contain local Git objects, workflow state, result hashes and diagnostic output;
no bearer credential or GitHub token is deliberately stored. Treat them as trusted
operator state, not as public signed CI attestations. No Docker image is run by the
publication phase, and no GitHub write token is passed to the tests phase.

The publication job needs repository settings that allow GitHub Actions to create
pull requests. If policy rejects it, that is a failed or uncertain trial, not a pass.
A change to `main` between the two invocations invalidates the source run; run tests
again on the new revision rather than bypassing this check.

## Timeout, restart and reconciliation

Killing `docker run` does not guarantee container termination. The runner assigns a
unique name and attempts `docker rm --force` only for that container on timeout.
`cleanup_verified=false` means cleanup was not confirmed; it does not mean that a
container definitely remains. Inspect the named container before further execution.

The publisher preserves `publication_approved` if push/PR creation fails or returns
an unverified result. Download `workflow-publication-state` and inspect the recorded
repository, branch and commit. Check GitHub for that exact branch SHA and Draft PR
before taking any further action. **Do not repeat the publish invocation after an
unknown result**: reusing the earlier tests artifact would restore an older state.
The durable GitHub claim blocks replay across invocations. Keep this claim tag
after closing the trial PR; deleting it would remove the cross-run replay guard.
This manual trial is not an unattended publication service.

## Local operator CLI

Use a pre-pulled `python@sha256:...` image, a private workspace outside the source
checkout, Docker, and authenticated `gh` for the separately approved publish phase:

```sh
python3 scripts/workflow_live_trial.py tests \
  --workspace /absolute/private/trial --repository OWNER/REPOSITORY \
  --source-checkout /absolute/source --image 'python@sha256:EXACT_DIGEST' \
  --approve-fixture --approve-tests

python3 scripts/workflow_live_trial.py publish \
  --workspace /absolute/private/trial --repository OWNER/REPOSITORY \
  --expected-commit EXACT_TESTED_SHA --approval-digest EXACT_PUBLICATION_DIGEST \
  --approve-publication
```

Separate invocations deliberately model process restart. This does not provide
host-crash injection, immutable filesystem snapshots, remote branch locking or a
fully authenticated multi-user service. See [production-readiness.md](production-readiness.md).
