#!/usr/bin/env python3
"""Evaluate an existing checkout copy against the suite on the benchmark branch.

Reads frozen Git objects locally; never fetches, modifies candidate files, invokes
models or trusts candidate tests. Explicit execution authorization is required.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from agents import ROOT
from verify_implementation import digest, prepare, read_file, verify, write_files

PREFIX = 'benchmarks/hard-java8-checkout/'
SUITE_FILES = ('run_contract.py', 'CheckoutContractSuite.java')


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.DEVNULL)


def evaluate(project, ref='origin/benchmark/hard-java8-checkout-20261031',
             *, execute=False, sandbox_image=None):
    project = Path(project).resolve(strict=True)
    # Resolve the ref once; later branch movement cannot mix revisions in one run.
    commit = git('rev-parse', '--verify', ref + '^{commit}').decode().strip()
    paths = git('ls-tree', '-r', '--name-only', commit, '--', PREFIX).decode().splitlines()
    selected = [name for name in paths if name.startswith(PREFIX + 'src/main/java/')
                and name.endswith('.java')]
    if not selected:
        raise ValueError('no benchmark Java sources in selected ref')
    sources = {name[len(PREFIX):]: git('show', commit + ':' + name) for name in selected}
    for name in ('README.md', 'pom.xml'):
        sources[name] = git('show', commit + ':' + PREFIX + name)
    suite = {name: git('show', commit + ':' + PREFIX + 'evaluator/' + name) for name in SUITE_FILES}
    candidate = {name: read_file(project, name) for name in sources}
    for name in ('README.md', 'pom.xml'):
        if candidate[name] != sources[name]:
            raise ValueError('frozen benchmark contract/build changed: ' + name)
    # Fixed-set trial: never silently ignore a new production helper class.
    candidate_java = {p.relative_to(project).as_posix() for p in (project / 'src/main/java').rglob('*.java')}
    if candidate_java != {name for name in sources if name.endswith('.java')}:
        raise ValueError('production file set changed; requires a preregistered extended trial')
    provenance = {'benchmark_commit': commit, 'source_sha256': {k: digest(v) for k, v in sources.items()},
                  'suite_sha256': {k: digest(v) for k, v in suite.items()},
                  'candidate_sha256': {k: digest(v) for k, v in candidate.items()},
                  'provider_invoked': False}
    if not execute:
        return {**provenance, 'status': 'prepared_only_checks_not_run'}
    with tempfile.TemporaryDirectory(prefix='checkout-evaluation-') as tmp:
        base = Path(tmp)
        write_files(base / 'original', sources)
        write_files(base / 'suite', suite)
        python = 'python3' if sandbox_image is not None else sys.executable
        prepare(base / 'original', list(sources), [name for name in sources if name.endswith('.java')],
                base / 'suite', list(suite), {'checkout_contract': [python, '_suite/run_contract.py']},
                base / 'trial')
        write_files(base / 'trial/baseline', candidate)
        original = verify(base / 'trial', 'original', sandbox_image=sandbox_image)
        corrected = verify(base / 'trial', 'baseline', sandbox_image=sandbox_image)
    return {**provenance, 'status': corrected['status'], 'original': original, 'candidate': corrected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--suite-ref', default='origin/benchmark/hard-java8-checkout-20261031')
    parser.add_argument('--execute-checks', action='store_true')
    parser.add_argument('--sandbox-image')
    args = parser.parse_args()
    try:
        result = evaluate(args.project, args.suite_ref, execute=args.execute_checks,
                          sandbox_image=args.sandbox_image)
    except (ValueError, OSError, subprocess.SubprocessError):
        parser.exit(2, 'ERROR: invalid project, unavailable benchmark Git objects or toolchain; '
                       'fetch the benchmark branch and inspect the frozen file set\n')
    print(json.dumps(result, indent=2))
    if result['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
