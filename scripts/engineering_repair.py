"""Bounded visible-test repair; independent evaluator feedback never enters context.

Commands and test fixtures are operator-owned. Host execution is not a sandbox.
Unknown effects require operator reconciliation and a new run, never automatic retry.
"""
import json
import math
from pathlib import Path
import tempfile
import time

from engineering_context import pack
from engineering_handoff import validate_fix, fingerprint
from invariant_mutation import parse_result
from verify_implementation import read_file, digest, write_files, run_check, container_check


def install(db):
    db.execute('CREATE TABLE IF NOT EXISTS engineering_repairs '
               '(run TEXT PRIMARY KEY, state TEXT NOT NULL, config TEXT NOT NULL, '
               'hash TEXT NOT NULL, result TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS engineering_repair_events '
               '(seq INTEGER PRIMARY KEY, run TEXT NOT NULL, round INTEGER NOT NULL, '
               'kind TEXT NOT NULL, value TEXT NOT NULL)')


def selection(db, run, fallback):
    row = db.execute('SELECT state,result FROM engineering_repairs WHERE run=?', (run,)).fetchone()
    if row is None:
        return fallback
    if row[0] != 'completed' or json.loads(row[1])['status'] != 'passed':
        raise ValueError('repair has not passed visible checks; independent acceptance blocked')
    return json.loads(row[1])['submission']


def visible_plan(plan, trial, manifest):
    if not isinstance(plan, dict) or set(plan) != {'suite_root', 'suite_files', 'command', 'cases'}:
        raise ValueError('visible plan needs suite_root, suite_files, command and cases')
    if not isinstance(plan['suite_root'], str) or not plan['suite_root']:
        raise ValueError('visible suite_root must be a path string')
    root = Path(plan['suite_root']).resolve(strict=True)
    if root == trial or trial in root.parents or root in trial.parents:
        raise ValueError('visible tests must be separate from trial/evaluator')
    names, command, cases = plan['suite_files'], plan['command'], plan['cases']
    if (not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names)
            or len(set(names)) != len(names)
            or not isinstance(command, list) or not command
            or not all(isinstance(a, str) and a and '\x00' not in a for a in command)
            or not isinstance(cases, list) or not cases
            or not all(isinstance(c, str) and c.strip() for c in cases)
            or len(set(cases)) != len(cases)):
        raise ValueError('invalid visible files, command or required case IDs')
    tests = {name: read_file(root, name) for name in names}
    if any(digest(data) in manifest['suite_sha256'].values() for data in tests.values()):
        raise ValueError('independent evaluator files cannot be reused as visible tests')
    return tests


def run(db, run_id, plan, *, max_repairs=3, max_seconds=300, max_output_tokens=4096,
        execute_provider=False, execute_checks=False, allow_host=False,
        sandbox_image=None, provider=None):
    import engineering_cycle as cycle
    from openai_artifact_adapter import invoke
    provider = provider or invoke
    config = cycle.load(db, run_id)
    trial, manifest = cycle.snapshots(config)
    tests = visible_plan(plan, trial, manifest)
    if (type(max_repairs) is not int or not 1 <= max_repairs <= 10
            or type(max_seconds) is not int or not 1 <= max_seconds <= 3600
            or type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 32768):
        raise ValueError('repair budget outside allowed bounds')
    if not execute_checks or (not allow_host and sandbox_image is None):
        raise ValueError('visible checks require explicit execution and host/container boundary')
    if not execute_provider:
        raise ValueError('repair requires explicit provider opt-in')
    if sandbox_image is not None:
        from sandbox_runner import DIGEST_IMAGE
        if not DIGEST_IMAGE.fullmatch(sandbox_image):
            raise ValueError('sandbox image must be digest-pinned')
    policy = {'plan': plan, 'suite_sha256': {n: digest(b) for n, b in tests.items()},
              'max_repairs': max_repairs, 'max_seconds': max_seconds,
              'max_output_tokens_per_call': max_output_tokens,
              'sandbox_image': sandbox_image, 'allow_host': allow_host}
    policy_json = cycle.encoded(policy)
    # One owner for the entire loop. No automatic recovery of running/unknown effects.
    db.execute('BEGIN IMMEDIATE')
    try:
        prior = db.execute('SELECT state,config,hash,result FROM engineering_repairs WHERE run=?',
                           (run_id,)).fetchone()
        if prior:
            if prior[1] != policy_json or digest(prior[1].encode()) != prior[2]:
                raise ValueError('repair policy or visible tests changed; new run required')
            if prior[0] != 'completed':
                raise ValueError('repair running/unknown; stop worker and reconcile before a new run')
            db.execute('COMMIT')
            return json.loads(prior[3])
        handoff = cycle.artifact(db, run_id, 'review')
        submission = cycle.artifact(db, run_id, 'implement')
        state = cycle.status(db, run_id)['stages']['verify']['status']
        if state != 'pending':
            raise ValueError('repair must precede independent verification')
        if not validate_fix(trial / 'evaluator/source', handoff, submission,
                            manifest['editable'])['ready_for_verification']:
            raise ValueError('unresolved findings require operator review')
        db.execute('INSERT INTO engineering_repairs VALUES(?,?,?,?,NULL)',
                   (run_id, 'running', policy_json, digest(policy_json.encode())))
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise
    started = time.monotonic()
    rounds = 0
    last = None

    def record(kind, value):
        db.execute('INSERT INTO engineering_repair_events(run,round,kind,value) VALUES(?,?,?,?)',
                   (run_id, rounds, kind, cycle.encoded(value)))

    def remaining():
        return math.floor(max_seconds - (time.monotonic() - started))

    def complete(reason):
        result = {'status': reason, 'rounds': rounds, 'submission': submission,
                  'visible_checks': last, 'independent_acceptance': 'not_run',
                  'policy_sha256': digest(policy_json.encode())}
        db.execute("UPDATE engineering_repairs SET state='completed',result=? WHERE run=? AND state='running'",
                   (cycle.encoded(result), run_id))
        return result

    try:
        seen = set()
        while True:
            cycle.snapshots(config)
            if visible_plan(plan, trial, manifest) != tests:
                raise ValueError('visible tests changed during repair')
            if remaining() < 1:
                return complete('time_budget_exhausted')
            originals = {n: read_file(trial / 'evaluator/source', n) for n in manifest['source_sha256']}
            candidate = {**originals, **{n: t.encode() for n, t in submission['files'].items()}}
            candidate_hash = fingerprint({n: digest(b) for n, b in candidate.items()})
            if candidate_hash in seen:
                return complete('stalled')
            seen.add(candidate_hash)
            # Fresh reconstruction every iteration, with immutable evaluator-owned test inputs.
            with tempfile.TemporaryDirectory(prefix='engineering-repair-') as tmp:
                work = Path(tmp)
                write_files(work, candidate)
                write_files(work / '_visible', tests)
                raw = (run_check(plan['command'], work, min(60, remaining()))
                       if sandbox_image is None else
                       container_check(sandbox_image, plan['command'], work, min(60, remaining())))
                last = parse_result(raw, set(plan['cases']))
                record('visible_check', {'candidate_sha256': candidate_hash, **last})
                if remaining() < 1:
                    return complete('time_budget_exhausted')
                if last['status'] == 'passed':
                    return complete('passed')
                if last['status'] == 'inconclusive':
                    return complete('inconclusive')
                if rounds >= max_repairs:
                    return complete('attempt_budget_exhausted')
                # Only visible structured results are forwarded, never independent suite output.
                task = cycle.FIX_TASK + '\n' + cycle.encoded({
                    'review_sha256': fingerprint(handoff), 'review': handoff['review'],
                    'editable': manifest['editable'], 'previous_submission': submission,
                    'visible_tests': {n: b.decode('utf-8') for n, b in tests.items()},
                    'visible_feedback': last,
                    'instruction': 'Repair the candidate using the visible failing cases. Return complete '
                                   'cumulative replacements relative to the original, not incremental edits. '
                                   'Tests are frozen. Independent evaluation is unavailable.'})
                # Context uses a pristine reconstruction: test execution cannot rewrite model input.
                with tempfile.TemporaryDirectory(prefix='engineering-repair-context-') as ctx_tmp:
                    write_files(Path(ctx_tmp), candidate)
                    context = pack(Path(ctx_tmp), manifest['source_sha256'],
                                   config.get('developer_agent', 'java-developer')
                                   if config['arm'] == 'daeloryn' else None, task,
                                   max_bytes=config['max_bytes'], deduplicate=config['deduplicate_context'])
                if remaining() < 1:
                    return complete('time_budget_exhausted')
                rounds += 1
                record('provider_started', {'context_sha256': context['context_sha256'],
                                           'max_output_tokens': max_output_tokens})
                response = provider(context, config['model'], enabled=True,
                                    timeout=min(120, remaining()), max_output_tokens=max_output_tokens)
                record('provider_result', {'usage': response.get('usage', {}),
                                          'response_id': response.get('response_id'),
                                          'actual_model': response.get('actual_model'),
                                          'artifact_sha256': fingerprint(response['artifact'])})
                updated = response['artifact']
                if not validate_fix(trial / 'evaluator/source', handoff, updated,
                                    manifest['editable'])['ready_for_verification']:
                    raise ValueError('repair left unresolved findings')
                submission = updated
                record('candidate', submission)
    except BaseException:
        db.execute("UPDATE engineering_repairs SET state='unknown' WHERE run=? AND state='running'", (run_id,))
        raise
