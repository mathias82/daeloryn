# Independent checkout contract suite

This evaluator lives on the benchmark branch. Keep it out of both model-visible workspaces and freeze its Git commit before either implementation. The project sources and their original README contract are unchanged.

The 23 assertions cover valid checkout, strict expiry equality, quantity bounds, nonempty lines, blank SKU, positive prices, multiplication/addition overflow, stock rollback, payment rejection, save compensation, visible failed compensation, sequential/concurrent duplicates, mismatched replay details, tenant isolation and immutable/stock positive controls. Assertions use Java 8 APIs and compile with `--release 8` under a compatible JDK 9+ toolchain. The Python runner can invoke the compiler module when a `javac` launcher is absent.

```bash
python3 evaluator/run_contract.py --project /absolute/path/to/existing/checkout
```

The script compiles production Java and evaluator-owned assertions into a temporary directory. It does not run Maven, candidate tests or candidate build scripts. Exit 0 means all 23 assertions passed; exit 1 means behavior assertions failed; exit 2 means setup/compile/incomplete-output failure. The runner rejects missing/duplicate/inconsistent summaries, including accidental zero-test process exits. It is not resistant to deliberately malicious candidate code forging stdout; run in a real sandbox and independently review patches.

## Observed development validation

The unchanged fixture produced `total=23 passed=5 failed=18` during local development on Java 17. The five passing controls were valid order, past expiry rejection, sequential idempotency, safe positive stock reserve/release and immutable request behavior. The concurrency check uses a coordinated start and repeated executions; it is schedule-sensitive and must not be interpreted as proof of race freedom when passing. A separately authored temporary correction passed 23/23 as a suite consistency control. That correction was not a model submission and is not a published gold implementation.

These are public development fixtures, not unseen holdouts or evidence of provider superiority. The suite is not exhaustive. In particular, the payment interface supplies no durable query/reconciliation protocol for unknown charge outcomes and the order interface supplies no cross-instance transaction primitive. Those limitations require explicit contract/design review; the suite does not pretend that ordinary local retries solve them. The failed-refund assertion also requires retained save/refund error provenance from the implementation prompt; review any alternative structured recovery contract before ranking a candidate.

## Existing Mac copies

From an updated main checkout, the opt-in `scripts/check_checkout_benchmark.py` loads this suite from frozen local Git objects and reconstructs both original and candidate in temporary directories. It requires no new permanent copies and never changes the existing benchmark workspace. Fetch the benchmark branch first. Candidate additions/deletions or changed README/pom require a separately declared extended trial; the fixed-set v1 evaluator rejects them rather than silently ignoring changes.
