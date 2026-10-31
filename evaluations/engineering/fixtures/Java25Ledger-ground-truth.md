# Java25Ledger review ground truth — keep out of review workspaces

This document is an evaluation rubric, not a benchmark result. Copy **only** `Java25Ledger.java` into each isolated review directory. Reviewers must not see this document.

Independent expected findings (judge semantic matches, not exact prose):

1. **Unsafe shared state**: `HashMap` is accessed by multiple virtual-thread tasks without synchronization. Concurrent operations can corrupt state or race.
2. **Lost updates / non-atomic read-modify-write**: `deposit` reads a previous balance then writes an incremented value; even swapping to `ConcurrentHashMap` alone would not make this compound update atomic.
3. **Integer overflow**: `previous + amount` overflows for sufficiently large positive balances, producing wrong/negative values.
4. **Transfer mutates before validating**: negative or zero `amount` changes the source balance before throwing. For negative amounts, source balance increases.
5. **Transfer not atomic**: source is debited before crediting destination; if destination deposit fails (for example, amount overflow is unchecked, but errors such as null keys with alternate map choices or OOM), state may be partially changed. Concurrent observers can also see inconsistent intermediate balances.
6. **Unsafe withdrawal for missing accounts**: `balances.remove(account)` can return null; unboxing to `int` throws `NullPointerException`.

Notes: Findings 1 and 2 are related but can be counted separately if the reviewer explains the distinct collection-safety and atomicity defects. Do not count generic 'no timeout' claims as confirmed without evidence of task behavior. Null account input is accepted by HashMap and is not by itself a demonstrated defect. The executor is closeable and has explicit cleanup via `AutoCloseable`; do not claim it is necessarily leaked.

Adjudication: compare source line evidence against the exact copied file and distinguish a credible *potential* consistency issue from a demonstrated exception. Do not quote this rubric in prompts. At least five independent runs per arm should be sampled before any performance claim.
