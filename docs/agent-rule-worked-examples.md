# Worked examples for the six shared agent quality rules

These are **teaching examples**, not findings from a user's project. Before proposing code, each agent must inspect the actual source/build/dependencies and respect the target environment. The 22 agent definitions contain their own role-specific code/configuration examples because host adapters do not automatically import this document.

## 1. Accurate source evidence

Bad: claim `Inventory.java:15` without checking line numbers.

Good procedure:
```sh
nl -ba src/main/java/Inventory.java
```
Only then quote the exact statement and its verified line. If the file is unavailable, omit line numbers and say `not verified`.

## 2. Static inspection versus executed proof

Source (Java 8):
```java
int next = current + quantity;
```
Possible overflow is **STATICALLY VERIFIED** from `int` arithmetic. A scenario such as `Integer.MAX_VALUE + 1` is a **proposed reproduction**, not `RUNTIME REPRODUCED`, until actually executed. State `Tests not run`.

## 3. Deduplicate one root cause

Source (Java 8):
```java
Map<String, Integer> stock = new HashMap<String, Integer>();
stock.put(sku, stock.getOrDefault(sku, 0) + quantity);
```
When called concurrently, unsynchronized access and a lost update are related symptoms. Report one root-cause finding with the shared evidence, not two inflated findings. A separate input-validation flaw may still deserve its own finding.

## 4. Distinguish defects from undocumented contracts

```java
void reserve(String sku, int quantity) {
    stock.put(sku, stock.getOrDefault(sku, 0) - quantity);
}
```
If the documented domain invariant is `quantity > 0`, negative input is an actionable validation bug. Without that invariant, mark negative-quantity handling **CONTRACT-DEPENDENT** rather than asserting an arbitrary policy. Show what evidence would settle it.

## 5. Use only version-compatible fixes

Java 8-compatible:
```java
ConcurrentMap<String, Integer> counts = new ConcurrentHashMap<String, Integer>();
counts.merge("A", 1, Math::addExact);
```
Do not suggest records, `var`, virtual threads or a Spring Boot 3/Jakarta migration to an unmodified Java 8/Spring 5 project. Verify compiler release, dependencies, CI and runtime, not just the developer machine's `java -version`.

## 6. Check the whole fix and propose regression coverage

An incomplete fix synchronizes `reserve` but still allows negative quantities under a positive-quantity contract:

```java
public synchronized int reserve(String sku, int quantity) {
    int available = stock.getOrDefault(sku, 0);
    if (available < quantity) throw new IllegalStateException();
    stock.put(sku, available - quantity);
    return available - quantity;
}
```

A more complete Java 8-compatible correction for that **specified contract**:
```java
public synchronized int reserve(String sku, int quantity) {
    if (quantity <= 0) throw new IllegalArgumentException("quantity");
    int available = stock.getOrDefault(sku, 0);
    if (available < quantity) throw new IllegalStateException("insufficient stock");
    int remaining = available - quantity;
    stock.put(sku, remaining);
    return remaining;
}
```
Other writers must use the same lock; overflow in `add` needs a **separate check**. Proposed regression cases: successful reserve; zero/negative rejected without state change; insufficient stock rejected; concurrent reservations never oversell; `add` overflow rejected. Test status: **not run**.

## Apply this protocol beyond Java

For React, recheck success, loading, rejection, unmount and stale-response races after a UI fix. For Spring, check transaction rollback, security 401/403, database isolation and dependency failures. For Kubernetes/CI, check manifests or workflow triggers, permissions, rollout/rollback and runtime evidence rather than concluding success from static YAML. These conditions and test steps must reflect the actual stack and operational contract.

An example in an agent prompt does not demonstrate model compliance. Benchmark with unseen, isolated cases and preserved real model outputs.
