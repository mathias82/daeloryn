# Release and rollback

**No v1.0 release is authorized yet.** See [release gates](release-gates.md).

1. Resolve all P0 release blockers and confirm green matrix tests on the exact candidate SHA.
2. Verify four actual host runtimes using [compatibility protocol](host-compatibility.md).
3. Complete baseline-vs-specialist evidence benchmark and field pilot review.
4. Obtain independent security review; check CodeQL and dependency audit.
5. Freeze a versioned candidate tag; build a source archive reproducibly from the tag.
6. Generate SHA-256 checksums and publish a changelog recording breaking changes.
7. Stage in an isolated test repository; if regression is discovered, do not publish a stable tag.
8. Once the checklist is fully verified, publish GitHub release and keep prior version available for rollback.

For installations, `--force` overwrites target host config files; back up and review changes before using it. Do not describe installer overwrites as transactional until rollback handling is implemented and tested.
