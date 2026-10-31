#!/usr/bin/env python3
"""Pinned business-invariant assertions and targeted source mutation checks.

Not PIT or automatic invariant discovery. Operator-authored mutations and trusted
suite reports are executed only with explicit authorization in fresh snapshots.
"""
import argparse
import json
from pathlib import Path
import tempfile

from verify_implementation import digest, read_file, write_files, run_check, container_check


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate(spec):
    if not isinstance(spec, dict) or type(spec.get('schema_version')) is not int or spec['schema_version'] != 1:
        raise ValueError('schema_version=1 required')
    for field in ('sources', 'suite'):
        values = spec.get(field)
        if not isinstance(values, list) or not values or not all(text(name) for name in values) or len(set(values)) != len(values):
            raise ValueError(field + ' requires unique explicit files')
    command = spec.get('command')
    if not isinstance(command, list) or not command or not all(text(arg) and '\x00' not in arg for arg in command):
        raise ValueError('explicit evaluator command argv required')
    invariants = spec.get('invariants')
    if not isinstance(invariants, list) or not invariants:
        raise ValueError('at least one documented invariant required')
    ids = set()
    for item in invariants:
        if not isinstance(item, dict) or not text(item.get('id')) or item['id'] in ids:
            raise ValueError('invariant IDs must be unique strings')
        ids.add(item['id'])
        locator = item.get('contract')
        if (not isinstance(locator, dict) or locator.get('path') not in spec['sources']
                or type(locator.get('line')) is not int or locator['line'] < 1
                or not text(locator.get('quote')) or '\n' in locator['quote'] or '\r' in locator['quote']):
            raise ValueError('invariant needs an exact contract locator in selected sources')
    mutants = spec.get('mutants')
    if not isinstance(mutants, list) or not 1 <= len(mutants) <= 100:
        raise ValueError('1..100 explicitly selected mutants required')
    seen = set()
    for item in mutants:
        if (not isinstance(item, dict) or not text(item.get('id')) or item['id'] in seen
                or item.get('path') not in spec['sources'] or item['path'].startswith('_suite/')
                or type(item.get('line')) is not int or item['line'] < 1
                or not text(item.get('before')) or not isinstance(item.get('after'), str)
                or item['before'] == item['after'] or '\n' in item['before'] or '\r' in item['before']
                or '\n' in item['after'] or '\r' in item['after']):
            raise ValueError('invalid exact-line source mutation')
        targets = item.get('targets')
        if not isinstance(targets, list) or not targets or not all(text(t) and t in ids for t in targets):
            raise ValueError('mutation must target declared invariants')
        seen.add(item['id'])
    return ids


def mutate(data, mutation):
    lines = data.decode('utf-8').splitlines(keepends=True)
    line = mutation['line'] - 1
    if line >= len(lines) or lines[line].count(mutation['before']) != 1:
        raise ValueError('mutation is ambiguous or does not match pinned source')
    lines[line] = lines[line].replace(mutation['before'], mutation['after'], 1)
    return ''.join(lines).encode('utf-8')


def pin(root, suite_root, spec):
    validate(spec)
    sources = {name: read_file(Path(root).resolve(strict=True), name) for name in spec['sources']}
    suites = {name: read_file(Path(suite_root).resolve(strict=True), name) for name in spec['suite']}
    if any(Path(name).parts[0] == '_suite' for name in sources):
        raise ValueError('source cannot occupy reserved _suite path')
    for item in spec['invariants']:
        locator = item['contract']
        lines = sources[locator['path']].decode('utf-8').splitlines()
        if locator['line'] > len(lines) or locator['quote'] not in lines[locator['line'] - 1]:
            raise ValueError('invariant contract quote does not match source')
    for item in spec['mutants']:
        mutate(sources[item['path']], item)
    return {**spec, 'source_sha256': {n: digest(data) for n, data in sources.items()},
            'suite_sha256': {n: digest(data) for n, data in suites.items()}}


def parse_result(result, expected):
    observation = {'execution_status': result['status'], 'exit_code': result['exit_code'],
                   'output_sha256': digest(result['output'].encode())}
    if 'container_cleanup' in result:
        observation['container_cleanup'] = result['container_cleanup']
    if result['status'] in ('timeout', 'runner_error') or result.get('output_truncated'):
        return {**observation, 'status': 'inconclusive'}
    try:
        report = json.loads(result['output'])
        cases = report.get('cases') if isinstance(report, dict) else None
        if not isinstance(cases, list) or len(cases) != len(expected):
            raise ValueError('missing assertions')
        seen = set()
        failed = []
        for case in cases:
            if (not isinstance(case, dict) or not text(case.get('id')) or case['id'] not in expected
                    or case['id'] in seen or case.get('status') not in ('passed', 'failed')
                    or type(case.get('assertions')) is not int or case['assertions'] < 1):
                raise ValueError('invalid assertion record')
            seen.add(case['id'])
            if case['status'] == 'failed':
                failed.append(case['id'])
        if result['exit_code'] != (1 if failed else 0):
            raise ValueError('test exit code inconsistent with assertions')
        return {**observation, 'status': 'failed' if failed else 'passed', 'failed_cases': failed,
                'assertion_count': sum(case['assertions'] for case in cases)}
    except (ValueError, TypeError):
        return {**observation, 'status': 'inconclusive'}


def evaluate(root, suite_root, manifest, *, execute=False, timeout=60, sandbox_image=None):
    expected = validate(manifest)
    if type(timeout) is not int or not 1 <= timeout <= 120:
        raise ValueError('timeout must be 1..120')
    frozen = pin(root, suite_root, manifest)
    for field in ('source_sha256', 'suite_sha256'):
        if manifest.get(field) != frozen[field]:
            raise ValueError('missing or stale pinned ' + field)
    sources = {name: read_file(Path(root).resolve(), name) for name in manifest['sources']}
    suites = {name: read_file(Path(suite_root).resolve(), name) for name in manifest['suite']}
    # Bind evaluation to the already checked snapshot, not later rereads.
    if any(digest(data) != frozen['source_sha256'][n] for n, data in sources.items()) or any(
            digest(data) != frozen['suite_sha256'][n] for n, data in suites.items()):
        raise ValueError('inputs changed while preparing checks')
    provenance = {'source_sha256': frozen['source_sha256'], 'suite_sha256': frozen['suite_sha256'],
                  'manifest_sha256': digest(json.dumps(manifest, sort_keys=True).encode()),
                  'command': manifest['command']}
    if not execute:
        return {**provenance, 'status': 'not_run', 'mutation_score': None}
    def run(snapshot):
        with tempfile.TemporaryDirectory(prefix='invariant-check-') as tmp:
            work = Path(tmp)
            write_files(work, snapshot); write_files(work / '_suite', suites)
            observed = (run_check(manifest['command'], work, timeout) if sandbox_image is None
                        else container_check(sandbox_image, manifest['command'], work, timeout))
        return parse_result(observed, expected)
    baseline = run(sources)
    if baseline['status'] != 'passed':
        return {**provenance, 'status': 'baseline_not_passing', 'baseline': baseline,
                'mutants': [], 'mutation_score': None}
    results = []
    for mutation in manifest['mutants']:
        changed = dict(sources)
        changed[mutation['path']] = mutate(sources[mutation['path']], mutation)
        observation = run(changed)
        status = ('survived' if observation['status'] == 'passed' else
                  'killed' if observation['status'] == 'failed' and
                  set(observation['failed_cases']) & set(mutation['targets']) else 'inconclusive')
        results.append({'id': mutation['id'], 'status': status, 'observation': observation,
                        'mutant_sha256': digest(changed[mutation['path']])})
    killed = sum(item['status'] == 'killed' for item in results)
    survived = sum(item['status'] == 'survived' for item in results)
    incomplete = killed + survived != len(results)
    return {**provenance, 'baseline': baseline, 'mutants': results,
            'status': 'inconclusive' if incomplete else 'failed' if survived else 'passed',
            'mutation_score': killed / (killed + survived) if killed + survived else None,
            'limitations': 'Targeted operator-authored mutations; equivalent mutants need adjudication. '
                          'Compile errors, crashes, skipped assertions and timeouts are not mutation kills.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--suite-root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--pin', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--sandbox-image')
    args = parser.parse_args()
    try:
        spec = json.loads(args.manifest.read_text())
        result = (pin(args.root, args.suite_root, spec) if args.pin else
                  evaluate(args.root, args.suite_root, spec, execute=args.execute,
                           timeout=args.timeout, sandbox_image=args.sandbox_image))
    except (ValueError, OSError):
        parser.exit(2, 'ERROR: invalid invariant spec, stale evidence or unavailable inputs\n')
    print(json.dumps(result, indent=2))
    if not args.pin and result['status'] not in ('passed', 'not_run'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
