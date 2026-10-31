# Recovery verification after the paired checkout trial

The uploaded default-Copilot and Daeloryn candidates both passed the same original
23-check development suite. Additional post-comparison probes found a failed-refund
retry regression in the Daeloryn candidate and unknown-charge/fresh-instance intent
problems in both. Those are observations about two fixed candidates, not a general
provider ranking. Preserve those candidates and original reports; do not relabel a
hand-corrected patch or instruction update as a new model result.

## Agent and runtime changes

All 22 definitions now require applicable second-attempt effect counts, retained
unresolved state, explicit provider guarantees, complete intent verification across
the claimed replay scope and final-patch/report consistency. Each specialty has a
scoped check; read-only tasks stay read-only. The optional API implementation task
uses the same rules. These instructions cannot enforce model compliance in an IDE.
Unknown effects cannot be treated as rejected merely because an exception occurred,
a lock was released, or a request-ID parameter exists. Failed compensation requires
reconciliation before automatic repeat of the original mutation. Ordinary lock
release is allowed; clearing unresolved operation state is a different action.

## Executable development extension

The separate benchmark branch now supplies `run_recovery.py` and
`RecoveryContractSuite.java`. They add five checks without changing the original
23 assertions or exercise production inputs:

1. A second same-ID call after a failed refund does not charge again.
2. A second same-ID call after accepted charge/lost response does not charge again.
3. A fresh service instance rejects a different SKU with the same ID and total,
   without additional charge or stock mutation.
4. A fresh service instance still permits an identical successful replay.
5. A known payment rejection restores stock without a charge.

The first two use a non-idempotent fake, permitted by the existing interface.
The fourth is a positive control against rejecting all stored replays. The runner
compiles with `--release 8`, requires all five unique registered assertion IDs,
checks summary/exit consistency and treats setup failures as exit 2, not a score.
A store that commits and then throws remains an additional observation requiring
specified reconciliation semantics; it is not scored in these five checks.

From the tools checkout, fetch then freeze the benchmark commit once:

```bash
git fetch origin
RECOVERY_SUITE_SHA="$(git rev-parse origin/benchmark/hard-java8-checkout-20261031)"
python3 scripts/check_checkout_benchmark.py \
  --project /path/to/frozen-candidate --suite-ref "$RECOVERY_SUITE_SHA" \
  --recovery-checks --execute-checks
```

Use that same SHA for both arms. The opt-in wrapper pins both suites and runs each
on fresh reconstructions of original/candidate. Both named checks must pass for
combined `status=passed`. Without `--recovery-checks`, prior behavior remains the
original 23 checks. A pinned commit without recovery files fails explicitly rather
than silently skipping the extension. Default local execution uses caller privileges;
use the existing reviewed/preloaded digest-pinned container option for untrusted code.
The CLI does not invoke an AI provider or modify candidate projects.

## Interpretation and next trial

The five checks are public development cases derived after seeing the earlier
outputs, so passing them is not blind evidence of superiority. A new agent run must
use isolated fresh inputs, actual selection/model records and equal budgets, with
separate unseen holdouts. Keep correctness, report accuracy, security and quality
results separate. Do not equate more self-authored checks with better performance.
