#!/usr/bin/env python3
"""Opt-in review -> implementation artifact -> independent verification.

SQLite checkpoints never automatically retry unknown external effects. OpenAI is
an optional data-only provider; no model-selected shell commands run. This local
operator CLI is not an authorization service or a production deployment engine.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import uuid

from agents import catalog
from engineering_context import pack
from engineering_handoff import seal, current, fingerprint, validate_fix
from engineering_telemetry import Telemetry
from openai_artifact_adapter import invoke
import engineering_repair
from verify_implementation import digest, read_file, write_files, verify

STAGES = ('review', 'implement', 'verify')
REVIEW_TASK = '''Review this source read-only. Return a source-evidence report object with
schema_version=1 and findings=[...]. Each finding needs a unique string id,
disposition ACTIONABLE/CONDITIONAL/DISCARD, evidence_level STATICALLY VERIFIED,
RUNTIME REPRODUCED, LIKELY or CONTRACT-DEPENDENT, and source={path,line,quote}.
ACTIONABLE findings also require root_cause, invariant, trigger, impact, fix,
regression and invariant_basis SOURCE_SEMANTICS/DOCUMENTED_CONTRACT/OBSERVED_RUNTIME.
DOCUMENTED_CONTRACT requires contract_evidence={path,line,quote}. Never claim runtime
reproduction: this adapter has no execution tools. Conditional findings need
missing_evidence. Include no speculative defects or duplicates. Quotes must match
numbered source text without the displayed line-number prefix.'''
FIX_TASK = '''Independently check the supplied review and implement its supported fixes.
Preserve source/runtime versions and public contracts. Return an object with
review_sha256, files={editable path: complete replacement text}, resolutions=[
{finding: actionable finding id, status: fixed/rejected/unresolved, rationale:
source-grounded explanation, regression_assertions:[observable checks or explicit
unverified limitations]}]. Resolve every actionable finding exactly once.
Only replace declared editable files. Do not claim tests ran. The independent
verifier will execute separately. If a full fix needs undeclared files, report
unresolved rather than bypassing the allowed scope.'''


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def connect(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError('database symlink paths rejected')
    if not path.exists():
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS engineering_runs '
               '(id TEXT PRIMARY KEY, config TEXT NOT NULL, hash TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS engineering_stages '
               '(run TEXT, stage TEXT, status TEXT, attempt INTEGER, artifact TEXT, '
               'PRIMARY KEY(run,stage))')
    db.execute('CREATE TABLE IF NOT EXISTS engineering_events '
               '(seq INTEGER PRIMARY KEY, run TEXT, stage TEXT, status TEXT, at INTEGER)')
    db.execute('CREATE TABLE IF NOT EXISTS engineering_provider_results '
               '(run TEXT, stage TEXT, attempt INTEGER, metadata TEXT, PRIMARY KEY(run,stage,attempt))')
    engineering_repair.install(db)
    return db


def event(db, run, stage, status):
    db.execute('INSERT INTO engineering_events(run,stage,status,at) VALUES(?,?,?,?)',
               (run, stage, status, time.time_ns()))


def begin(db, trial, arm='daeloryn', model=None, max_bytes=196608, deduplicate=False,
          reviewer_agent='java-reviewer', developer_agent='java-developer'):
    if arm not in ('baseline', 'daeloryn'):
        raise ValueError('unknown trial arm')
    trial = Path(trial).resolve(strict=True)
    manifest_bytes = read_file(trial, 'evaluator/manifest.json')
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise ValueError('unsupported trial manifest')
    files = manifest.get('source_sha256')
    if not isinstance(files, dict) or not files:
        raise ValueError('trial must contain explicit source hashes')
    for name, expected in files.items():
        if digest(read_file(trial / arm, name)) != expected:
            raise ValueError('trial arm already differs from pinned original: ' + name)
    definitions = {m['name']: body for m, body in catalog()}
    if reviewer_agent not in definitions or developer_agent not in definitions:
        raise ValueError('unknown reviewer/developer agent')
    if 'reviewer' in developer_agent or 'architect' in developer_agent:
        raise ValueError('read-only review/architecture agents cannot be repair executors')
    agents = {name: digest(definitions[name].encode())
              for name in (reviewer_agent, developer_agent)}
    config = {'trial': str(trial), 'arm': arm, 'model': model, 'max_bytes': max_bytes,
              'manifest_sha256': digest(manifest_bytes), 'agent_sha256': agents,
              'deduplicate_context': bool(deduplicate),
              'reviewer_agent': reviewer_agent, 'developer_agent': developer_agent}
    run = uuid.uuid4().hex
    db.execute('BEGIN IMMEDIATE')
    try:
        db.execute('INSERT INTO engineering_runs VALUES(?,?,?)',
                   (run, encoded(config), digest(encoded(config).encode())))
        db.executemany('INSERT INTO engineering_stages VALUES(?,?,?,0,NULL)',
                       [(run, stage, 'pending') for stage in STAGES])
        event(db, run, None, 'created')
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise
    return run


def load(db, run):
    row = db.execute('SELECT config,hash FROM engineering_runs WHERE id=?', (run,)).fetchone()
    if row is None or digest(row[0].encode()) != row[1]:
        raise ValueError('unknown run or changed configuration')
    return json.loads(row[0])


def status(db, run):
    load(db, run)
    rows = db.execute('SELECT stage,status,attempt FROM engineering_stages WHERE run=?', (run,)).fetchall()
    states = {stage: {'status': state, 'attempt': attempt} for stage, state, attempt in rows}
    outcome = None
    if states['verify']['status'] == 'completed':
        outcome = artifact(db, run, 'verify')['status']
    repair_row = db.execute('SELECT state,result FROM engineering_repairs WHERE run=?', (run,)).fetchone()
    repair_state = None if repair_row is None else {
        'state': repair_row[0], 'outcome': json.loads(repair_row[1])['status'] if repair_row[1] else None}
    return {'run_id': run, 'repair': repair_state, 'stages': {stage: states[stage] for stage in STAGES},
            'verification_outcome': outcome, 'accepted': outcome == 'passed'}


def artifact(db, run, stage):
    row = db.execute('SELECT status,artifact FROM engineering_stages WHERE run=? AND stage=?',
                     (run, stage)).fetchone()
    if row is None or row[0] != 'completed':
        raise ValueError('prerequisite artifact is not completed')
    return json.loads(row[1])


def snapshots(config):
    trial = Path(config['trial'])
    raw = read_file(trial, 'evaluator/manifest.json')
    if digest(raw) != config['manifest_sha256']:
        raise ValueError('trial manifest changed; start a new reviewed run')
    manifest = json.loads(raw)
    # Revalidate frozen input for every resume, including caller/config context.
    for name, expected in manifest['source_sha256'].items():
        if digest(read_file(trial / 'evaluator/source', name)) != expected:
            raise ValueError('original snapshot changed')
        if digest(read_file(trial / config['arm'], name)) != expected:
            raise ValueError('candidate arm changed after run creation')
    for name, expected in manifest['suite_sha256'].items():
        if digest(read_file(trial / 'evaluator/suite', name)) != expected:
            raise ValueError('independent suite changed')
    agents = {m['name']: digest(body.encode()) for m, body in catalog()
              if m['name'] in config['agent_sha256']}
    if agents != config['agent_sha256']:
        raise ValueError('agent definitions changed; re-review required')
    return trial, manifest


def claim(db, run, stage):
    if stage not in STAGES:
        raise ValueError('unknown stage')
    db.execute('BEGIN IMMEDIATE')
    try:
        for prerequisite in STAGES[:STAGES.index(stage)]:
            artifact(db, run, prerequisite)
        if stage == 'verify':
            engineering_repair.selection(db, run, None)
        row = db.execute('SELECT status,attempt FROM engineering_stages WHERE run=? AND stage=?',
                         (run, stage)).fetchone()
        if row is None or row[0] != 'pending' or row[1] >= 3:
            raise ValueError('stage is not pending; unknown/failed effects require explicit recovery')
        db.execute("UPDATE engineering_stages SET status='running',attempt=attempt+1 WHERE run=? AND stage=?",
                   (run, stage))
        event(db, run, stage, 'running')
        db.execute('COMMIT')
        return row[1] + 1
    except BaseException:
        db.execute('ROLLBACK')
        raise


def finish(db, run, stage, attempt, outcome, result=None):
    db.execute('BEGIN IMMEDIATE')
    try:
        cursor = db.execute("UPDATE engineering_stages SET status=?,artifact=? WHERE run=? AND stage=? AND status='running' AND attempt=?",
                            (outcome, encoded(result) if result is not None else None, run, stage, attempt))
        if cursor.rowcount != 1:
            raise ValueError('lost stage ownership')
        event(db, run, stage, outcome)
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


def recover(db, run, stage, *, acknowledge_unknown=False):
    load(db, run)
    if stage not in STAGES or not acknowledge_unknown:
        raise ValueError('explicit acknowledgement of possible duplicate external effects required')
    db.execute('BEGIN IMMEDIATE')
    try:
        cursor = db.execute("UPDATE engineering_stages SET status='pending' WHERE run=? AND stage=? "
                            "AND status IN ('running','unknown','failed') AND attempt < 3", (run, stage))
        if cursor.rowcount != 1:
            raise ValueError('stage not recoverable or retry budget exhausted')
        event(db, run, stage, 'operator_reset_after_reconciliation')
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


def advance(db, run, stage, *, imported=None, execute_provider=False, execute_checks=False,
            allow_host=False, sandbox_image=None, provider=invoke, telemetry=None):
    config = load(db, run)
    if stage not in STAGES:
        raise ValueError('unknown stage')
    # Reading an already-completed stage never repeats a paid call or test run.
    if status(db, run)['stages'][stage]['status'] == 'completed':
        return artifact(db, run, stage)
    if stage == 'verify':
        if not execute_checks or (not allow_host and sandbox_image is None):
            raise ValueError('verification requires --execute-checks and sandbox image or explicit --allow-host-execution')
    elif imported is None and not execute_provider:
        raise ValueError('explicit provider opt-in or a manual imported artifact required')
    trial, manifest = snapshots(config)
    root = trial / 'evaluator/source'
    attempt = claim(db, run, stage)
    telemetry = telemetry or Telemetry()
    try:
        with telemetry.span(run, stage) as attributes:
            if stage == 'verify':
                handoff = artifact(db, run, 'review')
                submission = engineering_repair.selection(db, run, artifact(db, run, 'implement'))
                validated = validate_fix(root, handoff, submission, manifest['editable'])
                if not validated['ready_for_verification']:
                    raise ValueError('unresolved/rejected findings require operator review; not accepted as complete')
                # Reconstruct in a new disposable directory; never patch the user's copies.
                with tempfile.TemporaryDirectory(prefix='engineering-cycle-') as tmp:
                    destination = Path(tmp)
                    originals = {name: read_file(root, name) for name in manifest['source_sha256']}
                    tests = {name: read_file(trial / 'evaluator/suite', name) for name in manifest['suite_sha256']}
                    candidate = dict(originals)
                    candidate.update({name: text.encode() for name, text in submission['files'].items()})
                    write_files(destination / 'baseline', candidate)
                    write_files(destination / 'evaluator/source', originals)
                    write_files(destination / 'evaluator/suite', tests)
                    write_files(destination, {'evaluator/manifest.json': encoded(manifest).encode()})
                    original_result = verify(destination, 'original', sandbox_image=sandbox_image)
                    result = verify(destination, 'baseline', sandbox_image=sandbox_image)
                    result['original_status'] = original_result['status']
                    result['original_checks'] = original_result['checks']
                attributes['exit_code'] = 0 if result['status'] == 'passed' else 1
            else:
                task = REVIEW_TASK
                agent = config.get('reviewer_agent', 'java-reviewer') if config['arm'] == 'daeloryn' else None
                if stage == 'implement':
                    handoff = artifact(db, run, 'review')
                    current(root, handoff)
                    task = FIX_TASK + '\n' + encoded({'review_sha256': fingerprint(handoff),
                        'review': handoff['review'], 'editable': manifest['editable']})
                    agent = config.get('developer_agent', 'java-developer') if config['arm'] == 'daeloryn' else None
                context = pack(root, manifest['source_sha256'], agent, task,
                               max_bytes=config['max_bytes'], deduplicate=config['deduplicate_context'])
                attributes['input_sha256'] = context['context_sha256']
                if imported is None:
                    response = provider(context, config['model'], enabled=execute_provider)
                    result = response['artifact']
                    attributes.update(response['usage'])
                    metadata = {'usage': response['usage'], 'response_id': response.get('response_id'),
                                'actual_model': response.get('actual_model'),
                                'context_sha256': context['context_sha256']}
                    db.execute('INSERT INTO engineering_provider_results VALUES(?,?,?,?)',
                               (run, stage, attempt, encoded(metadata)))
                else:
                    result = imported
                if stage == 'review':
                    result = seal(root, result, manifest['source_sha256'])
                else:
                    validate_fix(root, handoff, result, manifest['editable'])
            attributes['artifact_sha256'] = digest(encoded(result).encode())
            finish(db, run, stage, attempt, 'completed', result)
            return result
    except BaseException:
        # Failure after claim can follow a paid request or executed candidate effect.
        # Never infer that an absent response means nothing happened.
        try:
            finish(db, run, stage, attempt, 'unknown')
        except ValueError:
            pass  # A recovered attempt must never overwrite a newer attempt.
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('start'); p.add_argument('--trial', type=Path, required=True)
    p.add_argument('--arm', choices=('baseline', 'daeloryn'), default='daeloryn')
    p.add_argument('--model'); p.add_argument('--max-context-bytes', type=int, default=196608)
    p.add_argument('--deduplicate-context', action='store_true')
    p.add_argument('--reviewer-agent', default='java-reviewer')
    p.add_argument('--developer-agent', default='java-developer')
    p = sub.add_parser('status'); p.add_argument('--run', required=True)
    p = sub.add_parser('step'); p.add_argument('--run', required=True)
    p.add_argument('--stage', choices=STAGES, required=True)
    p.add_argument('--import-artifact', type=Path); p.add_argument('--trace', type=Path)
    p.add_argument('--execute-provider', action='store_true')
    p.add_argument('--execute-checks', action='store_true')
    p.add_argument('--allow-host-execution', action='store_true'); p.add_argument('--sandbox-image')
    p = sub.add_parser('repair'); p.add_argument('--run', required=True)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--max-repairs', type=int, default=3)
    p.add_argument('--max-seconds', type=int, default=300)
    p.add_argument('--max-output-tokens', type=int, default=4096)
    p.add_argument('--execute-provider', action='store_true')
    p.add_argument('--execute-checks', action='store_true')
    p.add_argument('--allow-host-execution', action='store_true'); p.add_argument('--sandbox-image')
    p = sub.add_parser('recover'); p.add_argument('--run', required=True)
    p.add_argument('--stage', choices=STAGES, required=True)
    p.add_argument('--acknowledge-unknown-outcome', action='store_true')
    args = parser.parse_args()
    db = connect(args.db)
    try:
        if args.command == 'start':
            result = {'run_id': begin(db, args.trial, args.arm, args.model, args.max_context_bytes, args.deduplicate_context,
                                      args.reviewer_agent, args.developer_agent)}
        elif args.command == 'status':
            result = status(db, args.run)
        elif args.command == 'repair':
            result = engineering_repair.run(db, args.run, json.loads(args.plan.read_text()),
                max_repairs=args.max_repairs, max_seconds=args.max_seconds,
                max_output_tokens=args.max_output_tokens, execute_provider=args.execute_provider,
                execute_checks=args.execute_checks, allow_host=args.allow_host_execution,
                sandbox_image=args.sandbox_image)
        elif args.command == 'recover':
            recover(db, args.run, args.stage, acknowledge_unknown=args.acknowledge_unknown_outcome)
            result = status(db, args.run)
        else:
            telemetry = Telemetry(args.trace)
            result = advance(db, args.run, args.stage,
                imported=json.loads(args.import_artifact.read_text()) if args.import_artifact else None,
                execute_provider=args.execute_provider, execute_checks=args.execute_checks,
                allow_host=args.allow_host_execution, sandbox_image=args.sandbox_image,
                telemetry=telemetry)
            if telemetry.dropped:
                sys.stderr.write('WARNING: telemetry delivery failed; business outcome preserved\n')
        print(json.dumps(result, indent=2))
        if args.command == 'repair' and result['status'] != 'passed':
            return 1
    except (ValueError, OSError, RuntimeError) as error:
        # Do not print untrusted provider error content or credentials.
        parser.exit(2, 'ERROR: ' + type(error).__name__ + '; inspect stage status and operator inputs\n')
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main())
