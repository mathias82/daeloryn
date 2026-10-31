# Roadmap

## Implemented

- Canonical agent definitions for Java, Spring, React, Platform and Shared specialties
- Installer adapters for Codex, Claude Code, GitHub Copilot and Gemini CLI
- Static catalog validation, installer unit tests and GitHub Actions checks
- Deliberately unsafe Platform fixtures, reference checker and JSON finding scorer
- Declarative DAG workflow templates and dependency-aware planning
- Local manual-handoff execution state machine with evidence hashes and HMAC-signed approval tokens
- Experimental SQLite transactional workflow runtime, RS256/JWKS verification component and opt-in Docker isolation

## Current milestone: unified execution service (partial)

- [x] Shared CLI for planning, starting, inspecting and completing manual workflow handoffs
- [x] Transaction-backed state and central OIDC verification entry point
- [x] Strict provider request interface with dry-run metadata and hosted provider execution disabled
- [x] Opt-in network-disabled, digest-pinned container invocation (manual, no credentials or implicit state transitions)
- [x] Tests for concurrent single-winner completion and approval-gate enforcement
- [ ] Reviewed sandboxed provider implementations, credential brokering and end-to-end tests

## Next major milestone: unified execution service

Bring the current planning, state, approval and sandbox components under one service, with:

1. **AI-provider adapters** — explicit, version-tested integrations for supported CLIs/APIs, without assuming all tools share an execution interface.
2. **Controlled credentials** — separate provider credentials, short-lived access where supported, secret redaction and environment-scoped permissions.
3. **Isolated execution** — opt-in sandboxed runs, restricted filesystem/network access, resource limits, timeouts and cancellation.
4. **Externally enforced approvals** — trusted identity-provider integration, authorization policies and protected execution boundaries. The current JWT verifier is not a complete OIDC login or release authorization service.
5. **Concurrency-safe persistence** — consolidate SQLite transactions with run lifecycle, retry semantics, idempotency, crash recovery and integrity-protected audit events.
6. **Integration tests and observability** — verified approval blocking, negative security scenarios, adapter contracts, structured logs and traceable outcomes.

The unified service is **not implemented yet**. Existing components are experimental and must not independently authorize production deployments.

## Benchmark harness

- [x] JSON recorder for externally obtained Codex, Claude, Copilot and Gemini outputs
- [x] Source-line/quote evidence consistency audit and reproducible finding-ID scoring
- [x] Summary that identifies missing providers rather than fabricating scores
- [x] Documented blinded baseline-versus-specialist protocol and human evidence rubric
- [ ] Actual provider runs on identical cases with provenance and independently reviewed evidence
- [ ] Repeated experiments, time/token-cost measurements and held-out regression corpus

## Further work

- Independent benchmarks with blinded reference labels and human adjudication
- More Java/Spring/React regression fixtures
- End-to-end compatibility testing across four coding tools
- Versioned releases and distribution packaging

Prioritize correctness and safety over agent count.

## Experimental engineering cycle additions

Implemented an independent Java checkout development suite on the benchmark branch, source/context-pinned handoffs, content-free trace records with an optional OpenTelemetry bridge, a bounded data-only OpenAI Responses adapter, hardened opt-in container checks, transactional stage checkpoints with explicit recovery, and bounded/deduplicated context preparation. See [engineering cycle](engineering-cycle.md).

These additions do not enable the older automatic provider adapter, production deployment authorization or an autonomous tool loop. Live OpenAI/Docker/OpenTelemetry integration tests, independent human security review, unseen benchmark cases and real repeated provider comparisons remain outstanding.

## Code-validation tools (initial supported scope)

Implemented javac-resolved source indexing and conservative file-level impact, operator-selected invariant assertions/mutations, native Avro reader/writer checking, a conservative OpenAPI JSON subset matrix, and scoped instructions for all 22 agents. Added a sequential manual validation workflow and extended CI with JDK 17, code-analysis dependency audit and regression tests. See [supported boundaries](code-change-validation.md). Full runtime dispatch/DI impact, automatic invariant discovery, native PIT integration, complete OpenAPI/gRPC/migration checking and deployed consumer test execution remain outside this initial scope.
