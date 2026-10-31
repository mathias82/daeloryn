# Checkout Service — Java 8 code review exercise

A small, dependency-free Java 8 checkout implementation for an in-memory catalog and pluggable payment and order storage providers. The exercise intentionally uses plain Java to expose API boundaries and failure behavior without reliance on a framework.

## Business contract

- A checkout is associated with a tenant and a client request ID. A repeat of **the same request within the same tenant**, including concurrent repeats, must not produce a second charge or reservation. Different tenants may use the same request ID without sharing results.
- Every checkout contains at least one line. Each line has a nonblank SKU, a quantity between 1 and 1,000 inclusive and a strictly positive unit price in integer cents. Reusing an ID for materially different order details is invalid.
- A checkout can only succeed when it is **strictly before** its expiry instant. The checkout total must be exact and must fit a signed 64-bit integer. A rejected request must not reserve stock or charge money.
- Stock is shared by SKU. Successful orders consume exactly their quantities. A failed order, including a later-line stock failure or payment/storage failure, must not leave reserved stock or an uncompensated charge. A refund attempt can fail; the system must not misreport that as a cleanly rolled-back transaction.
- Receipt lookup is tenant-isolated: a caller must not be able to retrieve another tenant's receipt by guessing the request ID.
- Valid single-SKU reserve/release operations and immutable value objects are acceptable when implemented correctly; do not treat these as defects solely for being in memory or using synchronization.

## Review scope

Inspect `pom.xml` and all files under `src/main/java`. Provide unique, source-evidenced findings with accurate paths and lines, prerequisites for their severity, a credible trigger, and a complete minimal remedy compatible with Java 8. Separate real code behavior from assumptions and design alternatives. Propose regression tests without modifying any files or pretending tests ran.

There is no gold answer or benchmark scoring metadata in this project.
