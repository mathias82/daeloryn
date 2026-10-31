# Recovery development extension

The original 23-check evaluator and all original exercise inputs remain unchanged.
`evaluator/run_recovery.py --project /path/to/candidate` adds five separate public
post-comparison checks: duplicate after failed refund, duplicate after accepted
charge/lost response, changed SKU at equal total through a fresh service instance,
valid fresh-instance replay, and known rejection restoring stock.

The provider fake is deliberately non-idempotent: the interface has no documented
deduplication guarantee. Unknown outcomes must block blind retry pending reconciliation;
this suite does not invent a provider query API or demand a particular stock retention
policy after unknown compensation. Both attempts are observed. The fresh-instance
control prevents accepting a strategy that simply rejects every persisted replay.

Compile with Java 8 platform APIs using JDK 17. Exit 0 means all five assertions
passed, 1 means behavioral failure, 2 means setup/compilation/incomplete output.
These are development checks derived after inspecting two candidate implementations,
not a hidden holdout, production certification, or evidence of general AI superiority.
Do not expose evaluator files to a blind trial. No user candidate implementation is
published here and the original scores must be kept separately.

A save that commits and then throws needs additional documented store/reconciliation
semantics. That observation is intentionally not scored by this extension. Distributed
process coordination, crash durability and deployed provider behavior are not certified.
