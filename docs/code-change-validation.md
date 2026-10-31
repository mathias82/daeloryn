# Code change validation: three opt-in engineering gates

All 22 canonical specialists and 88 generated adapters require scoped impact analysis, evidenced business invariants and consumer/provider compatibility checks. These are instruction contracts, not guarantees that a host/model follows them. The following tools provide executable checks; none establishes overall correctness or production readiness.

Install the optional code-analysis dependency for native Avro checking and use a full JDK 17+ for Java analysis/tests. No model/provider credentials are required:

```bash
python3 -m pip install -r requirements-security.txt -r requirements-code-analysis.txt
```

## 1. Compiler-resolved Java impact

```bash
python3 scripts/semantic_impact.py \
  --root /absolute/project --source-root src/main/java --release 8 \
  --changed src/main/java/example/PaymentGateway.java
```

Alternatively select individual files with repeated `--source`. Supply resolved dependency JARs/class directories with repeated `--classpath`. Choose the release from the actual Maven/Gradle toolchain; it is required and never upgraded automatically. Version conflicts or missing dependencies produce `analysis_status=incomplete` and exit 1, rather than a verified clean result. Invalid inputs/unavailable toolchains exit 2.

The trusted Java helper uses javac parse/analyze, `Trees.getElement` and source positions. It indexes types, fields, methods, constructors and method references; overloads and namespaces are resolved by the compiler. It does not use name matching as semantic proof. Selected source bytes are reconstructed in a disposable snapshot; the compiler does not execute project bytecode, annotation processors, Maven/Gradle scripts or plugins. Implicit source lookup is disabled. Annotation-generated code must be supplied as explicit source or compiled dependencies; otherwise the result may be incomplete. No `.class` files are generated in the source project.

The graph conservatively expands at file granularity: all symbols in a changed file are considered, then source callers/dependencies transitively. Unchanged unrelated types with the same simple name are not merged. Save the JSON index before a change (omit `--changed`), then pass it via `--before-index` to retain references to deleted/renamed symbols. Indexes record selected source, classpath hashes, actual Java runtime version and release. Classpath before/after checks detect ordinary changes, not a malicious concurrent writer. Old indexes are provenance records, not signed attestations; protect them.

`complete` means compiler analysis of the selected source set completed. It does not mean all production impact was discovered. Reflection, virtual dispatch to implementations, runtime DI/proxies, framework configuration, dynamically loaded code, generated sources not included, services outside the selection and behavioral contracts require additional analysis/tests. A caller missing from an explicitly incomplete source selection cannot be discovered by this tool. Caller/config/build evidence remains required in agent findings.

Observed development smoke check: indexing the checkout Java 8 fixture resolves `PaymentGateway` dependencies to `CheckoutService`. That observation is not a runtime reproduction or a model benchmark.

## 2. Business invariants and targeted mutation tests

`scripts/invariant_mutation.py` takes an operator-authored JSON spec. It validates the exact contract quote, source line mutation, invariant IDs and explicit evaluator argv, then pins source and suite hashes. It never infers business rules from names or evaluates model-provided expressions. Pin first, then evaluate the saved manifest:

```bash
python3 scripts/invariant_mutation.py --root /project \
  --suite-root /private/evaluator --manifest /private/spec.json --pin
# Save that JSON as pinned.json outside model-visible context.
python3 scripts/invariant_mutation.py --root /project \
  --suite-root /private/evaluator --manifest /private/pinned.json --execute
```

Without `--execute` only inputs/provenance are validated. Execution uses caller permissions unless an explicitly reviewed, preloaded digest-pinned `--sandbox-image` is supplied. Keep secrets and evaluator storage inaccessible to untrusted candidates. The sandbox boundaries/cleanup limits are those documented in [implementation verification](implementation-verification.md) and [engineering cycle](engineering-cycle.md).

Spec shape (paths/locators/mutations must match the actual project, not this illustration):

```json
{
  "schema_version": 1,
  "sources": ["Quantity.java", "CONTRACT.txt"],
  "suite": ["run_checks.py"],
  "command": ["python3", "_suite/run_checks.py"],
  "invariants": [{"id": "positive-quantity", "contract": {
    "path": "CONTRACT.txt", "line": 1, "quote": "Only positive quantities"}}],
  "mutants": [{"id": "allow-zero", "path": "Quantity.java", "line": 2,
    "before": "quantity > 0", "after": "quantity >= 0",
    "targets": ["positive-quantity"]}]
}
```

The frozen evaluator command must emit a single JSON object with `cases`, exactly one per declared invariant, and return exit 0 for all passed / 1 for assertion failures:

```json
{"cases": [{"id": "positive-quantity", "status": "passed", "assertions": 3}]}
```

Positive assertion counts and names are supplied by the independently owned test runner; the verifier checks consistency but cannot establish that a malicious runner told the truth. Missing, skipped, duplicate, zero-assertion, inconsistent or truncated reports are inconclusive. Keep evaluator tests outside model-visible contexts and inspect them independently. Original stdout is hashed rather than exposed by the mutation report.

A passing baseline is mandatory. Each mutation runs alone against fresh source and the same tests. A mutation is `killed` only when a valid assertion report fails an explicitly targeted invariant. Compilation/import errors, crashes, timeouts, unrelated failures and invalid reports are not kills. `survived` requires adjudication: a mutation may be equivalent or reveal weak tests. The score is killed/(killed+survived); any inconclusive mutant prevents overall `passed`, even if that partial score is 100%. At most 100 explicitly selected mutants and a bounded per-run timeout are accepted. Exact mutations must be selected again if the candidate source changes.

This is targeted mutation execution, not a complete PIT integration, automatic mutation discovery or a proof that tests are exhaustive. Existing PIT/property-based checks can be independently integrated through the same trusted evaluator command/report protocol. The regression suite runs actual Java 8-compatible compilation/assertions plus toy Python cases, including a meaningful killed mutant, a survivor, invalid compilation and a failing baseline.

On the benchmark branch, `evaluator/run_invariants.py` adapts the same 23 checkout cases to this report protocol. It does not reward the original fixture's already-failing baseline. The original source/pom/README remain unchanged. See that branch's evaluator README for fixed-set trial limits and public-development-fixture contamination rules.

## 3. Consumer/provider compatibility matrix

```bash
python3 scripts/service_compatibility.py --root /contracts \
  --manifest /private/contracts.json --pin
# Save the pinned output, then check those exact versions.
python3 scripts/service_compatibility.py --root /contracts \
  --manifest /private/contracts-pinned.json
```

Manifest example:

```json
{"schema_version": 1, "contracts": [
  {"id": "order-event-billing", "provider": "orders", "consumer": "billing",
   "kind": "avro", "writer": "orders-v2.avsc", "reader": "billing-reader-v1.avsc"},
  {"id": "order-http-web", "provider": "orders", "consumer": "web",
   "kind": "openapi", "before": "web-supported-api.json", "after": "orders-candidate-api.json"}
]}
```

The pin command adds per-entry `sha256`; checking requires them to match. Duplicate IDs, missing paths and stale schema hashes are rejected. Contracts are snapshotted and checked for ordinary concurrent changes. Consumer/provider identities must come from observed configuration/ownership; these strings do not discover deployed services or prove authentication.

Avro uses Apache Avro's native Python reader/writer compatibility checker, records its version, resolves named/recursive records, promotions, defaults, unions and aliases according to that implementation. Invalid defaults are rejected. A new writer must be readable by the selected consumer reader. For backward/forward/full evolution supply the appropriate explicit writer-reader pairs as separate entries. Logical-type/codec semantic compatibility is `unknown`; this is not a Schema Registry live compatibility call or a substitute for Java serializer/version tests.

The HTTP adapter supports a **conservative OpenAPI 3.0/3.1 JSON subset**: existing operations, documented request bodies/media, response statuses/media and typed object/array/scalar schemas with required fields, enum, nullable, additional-properties policy and nonrecursive local refs. Request direction requires the new provider to accept old client inputs; response direction requires the old consumer contract to accept new outputs. Closed-reader/additional-property rules are considered. Unsupported constructs (`format`, patterns/ranges/combinators, recursive/external/sibling refs, parameters, callbacks, response headers/links, changed security/server configuration, etc.) produce `unknown`, never a green compatibility claim. This is not a complete OpenAPI validator. YAML, gRPC/protobuf and DB migration compatibility are not implemented by this adapter. Use another validated checker and runtime tests for those boundaries.

`compatible` is static recorded-contract evidence only; exit 1 covers incompatible/unknown results and exit 2 invalid inputs. Reports always retain `runtime_consumer_tests=not_run` and `production_ready=false`. Run actual consumer/provider tests against the intended versions separately; never use this matrix alone to authorize deployment.

## Agents, workflow and validation

`workflows/code-change-validation.json` orders manual handoffs: Java reviewer for source impact, Java testing for invariant strength, integration reviewer for service contracts, then an approval step. The planner does not execute these CLIs or manufacture evidence. Non-Java specialists must use their domain's actual compiler/LSP/configuration tools and mark absent tooling not run. They must not use a Java graph to certify React or Kubernetes changes.

```bash
python3 scripts/agents.py validate
python3 scripts/workflows.py --validate-all
python3 scripts/evaluate_platform.py
python3 -m unittest discover -s tests -v
```

CI installs JDK 17 and the code-analysis dependency for Python 3.11/3.12/3.13, and includes that dependency in SBOM/audit workflows. Tests verify compiler-resolved overloads/namespaces, transitive/deleted callers, incomplete inputs, mutation outcomes, native Avro direction/defaults/unions, HTTP directional compatibility and all 22 definitions/88 adapters. They do not prove live model adherence or superiority over Copilot/other frameworks.
