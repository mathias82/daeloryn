# Public v1.0 release gates

Status: **BLOCKED — developer preview**, until all mandatory P0 gates pass. This checklist covers the Community agent toolkit, **not** production autonomous deployment/orchestration.

| Gate | How to verify | Status |
| --- | --- | --- |
| P0: validation green on Python 3.11/3.12/3.13 | GitHub Actions matrix, all jobs passing on release commit | Unverified |
| P0: installer refuses path escape/symlink and handles errors safely | Automated negative cases, dry-run tests passed in CI, rollback and manual audit still required | Partial |
| P0: static and dependency security checks | Security workflow added; check completion and triage findings | Unverified |
| P0: four host adapter formats | Disposable project installation and CLI/host recognition for Codex, Claude, Copilot, Gemini | Pending |
| P0: observed comparison to baseline | Repeated actual model runs, identical conditions, independent review | Pending |
| P0: evidence adjudication | File/line confirmation plus reviewers checking semantic validity | Pending |
| P0: field pilots | 2–3 real consenting test repos, recorded developer feedback | Pending |
| P0: release candidate regression | frozen tag candidate; all P0 issues closed; audit pass | Pending |
| P1: packaging and migration docs | semver and reproducible checksum artifacts | Pending |
| P1: operational tooling | clear errors, consistent exit codes and run metadata | Partial |

## Tracking the 13 agreed workstreams

1. CI/CD: matrix added; green run unverified.
2. Four host integrations: format outputs exist; live tests pending.
3. Benchmarks: recording/scoring harness exists; observed runs pending.
4. Evidence: line/quote verification exists; semantic human adjudication pending.
5. Installer: dry-run and symlink preflight exist; atomic rollback/diff pending.
6. Security: CodeQL and pip-audit workflows added; findings and threat modeling pending.
7. Agent quality: 22 definitions have evidence/examples; live quality pending.
8. Versioning: changelog/release procedure drafted; tag pending.
9. Documentation: quick start, protocol, compatibility and pilot guides added; user validation pending.
10. Observability: full lifecycle, timeouts and recovery pending.
11. Supply chain: Dependabot and scans added; SBOM, action SHA pinning pending.
12. End-to-end pilots: template ready, no pilots run.
13. Release candidate: BLOCKED until all P0 requirements pass.

## Release process

1. Stabilize the installer and close correctness/security bugs before adding features.
2. Run all local and CI tests for every supported Python version.
3. Verify agent definitions in each host with explicit tested product/version and isolated fixture repos.
4. Run blinded specialist-vs-baseline benchmarks and independently adjudicate source evidence.
5. Perform pilot feedback review and independent security review.
6. Only after mandatory gates pass: tag a release candidate, rebuild artifacts from that tag, publish checksums and release notes, then publish v1.0.0.

## Honest scope

Python validation and regex fixture checks do not test hosted AI execution. An OIDC token verifier, SQLite state prototype and offline sandbox helper are not a production authorization/deployment service. Never grant a benchmark agent production credentials or authority to deploy.
