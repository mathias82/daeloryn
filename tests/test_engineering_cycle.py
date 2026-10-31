"""Offline integration of source handoffs, state recovery, provider data and checks.

Toy patches/mock Responses are not real model performance or sandbox validation.
"""
import copy
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from engineering_context import pack
from engineering_handoff import seal, current, fingerprint, validate_fix
from engineering_telemetry import Telemetry
import engineering_cycle as cycle
from openai_artifact_adapter import invoke, ProviderOutcomeUnknown, NoRedirect
from verify_implementation import prepare, container_check


def response(artifact):
    return {'status': 'completed', 'id': 'response-test',
            'output': [{'type': 'message', 'content': [{'type': 'output_text',
            'text': json.dumps({'artifact_json': json.dumps(artifact)})}]}],
            'usage': {'input_tokens': 123, 'output_tokens': 45}}


class Fixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / 'calc.py').write_text('def add(a, b): return a - b\n')
        (self.project / 'runtime.txt').write_text('runtime-context\n')
        self.suite = self.root / 'suite'
        self.suite.mkdir()
        (self.suite / 'check.py').write_text('from calc import add\nassert add(2, 3) == 5\n')
        self.report = {'schema_version': 1, 'findings': [{
            'id': 'wrong-operation', 'disposition': 'ACTIONABLE',
            'evidence_level': 'STATICALLY VERIFIED',
            'source': {'path': 'calc.py', 'line': 1, 'quote': 'a - b'},
            'root_cause': 'subtracts instead of adding', 'invariant': 'addition result',
            'trigger': 'add(2,3)', 'impact': 'incorrect result', 'fix': 'use addition',
            'regression': 'assert add(2,3)==5', 'invariant_basis': 'SOURCE_SEMANTICS'}]}
        self.handoff = seal(self.project, self.report, ['calc.py', 'runtime.txt'])
        self.fix = {'review_sha256': fingerprint(self.handoff),
                    'files': {'calc.py': 'def add(a, b): return a + b\n'},
                    'resolutions': [{'finding': 'wrong-operation', 'status': 'fixed',
                                     'rationale': 'use addition for the evidenced operation',
                                     'regression_assertions': ['assert add(2,3)==5']} ]}
        self.trial = self.root / 'trial'
        prepare(self.project, ['calc.py', 'runtime.txt'], ['calc.py'], self.suite,
                ['check.py'], {'correctness': [sys.executable, '-c',
                 "exec(open('_suite/check.py').read())"]}, self.trial)
        self.db_path = self.root / 'cycle.sqlite'
        self.db = cycle.connect(self.db_path)
        self.addCleanup(self.db.close)
        self.run = cycle.begin(self.db, self.trial, model='explicit-test-model')

    def review(self):
        return cycle.advance(self.db, self.run, 'review', imported=self.report)

    def implementation(self):
        handoff = self.review()
        fix = copy.deepcopy(self.fix)
        fix['review_sha256'] = fingerprint(handoff)
        return cycle.advance(self.db, self.run, 'implement', imported=fix)


class HandoffTests(Fixture):
    def test_seal_does_not_mutate_report_and_validates_fix_mapping(self):
        self.assertNotIn('source_sha256', self.report)
        result = validate_fix(self.project, self.handoff, self.fix, ['calc.py'])
        self.assertTrue(result['ready_for_verification'])
        self.assertFalse(result['tests_executed'])

    def test_context_change_requires_rereview_even_when_quote_unchanged(self):
        (self.project / 'runtime.txt').write_text('new effective configuration')
        with self.assertRaisesRegex(ValueError, 'stale review context'):
            current(self.project, self.handoff)

    def test_source_change_outside_quote_is_stale(self):
        (self.project / 'calc.py').write_text('def add(a, b): return a - b\n# changed\n')
        with self.assertRaises(ValueError):
            current(self.project, self.handoff)

    def test_missing_duplicate_or_unknown_resolution_rejected(self):
        for resolutions in ([], self.fix['resolutions'] * 2,
                            [{**self.fix['resolutions'][0], 'finding': 'unknown'}]):
            with self.subTest(resolutions=resolutions), self.assertRaises(ValueError):
                validate_fix(self.project, self.handoff, {**self.fix, 'resolutions': resolutions}, ['calc.py'])

    def test_wrong_review_or_undeclared_edit_rejected(self):
        for changed in ({'review_sha256': 'wrong'}, {'files': {'../outside': 'bad'}},
                        {'files': {'runtime.txt': 'different'}}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_fix(self.project, self.handoff, {**self.fix, **changed}, ['calc.py'])

    def test_rejected_finding_not_misrepresented_as_complete(self):
        fix = copy.deepcopy(self.fix)
        fix['resolutions'][0]['status'] = 'rejected'
        self.assertFalse(validate_fix(self.project, self.handoff, fix, ['calc.py'])['ready_for_verification'])


class CycleTests(Fixture):
    def test_manual_end_to_end_reconstruction_preserves_user_source(self):
        self.implementation()
        result = cycle.advance(self.db, self.run, 'verify', execute_checks=True, allow_host=True)
        self.assertEqual('passed', result['status'])
        self.assertTrue(cycle.status(self.db, self.run)['accepted'])
        self.assertIn('a - b', (self.trial / 'daeloryn/calc.py').read_text())

    def test_mock_provider_end_to_end_persists_observed_usage(self):
        def provider(context, model, **kwargs):
            if 'review_sha256' in context['input']:
                handoff = cycle.artifact(self.db, self.run, 'review')
                value = {**self.fix, 'review_sha256': fingerprint(handoff)}
            else:
                value = self.report
            return {'artifact': value, 'usage': {'input_tokens': 10, 'output_tokens': 20},
                    'response_id': 'mock-response', 'actual_model': 'mock-model'}
        for stage in ('review', 'implement'):
            cycle.advance(self.db, self.run, stage, execute_provider=True, provider=provider)
        result = cycle.advance(self.db, self.run, 'verify', execute_checks=True, allow_host=True)
        self.assertEqual('failed', result['original_status'])
        self.assertEqual('passed', result['status'])
        rows = self.db.execute('SELECT metadata FROM engineering_provider_results WHERE run=?', (self.run,)).fetchall()
        self.assertEqual(2, len(rows))
        self.assertEqual({'input_tokens': 10, 'output_tokens': 20}, json.loads(rows[0][0])['usage'])

    def test_concurrent_step_attempts_invoke_provider_only_once(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []
        def provider(*args, **kwargs):
            calls.append(True)
            entered.set()
            if not release.wait(3):
                raise RuntimeError('bounded test coordination timeout')
            return {'artifact': self.report, 'usage': {}}
        def step():
            db = cycle.connect(self.db_path)
            try:
                return cycle.advance(db, self.run, 'review', execute_provider=True, provider=provider)
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(step)
            self.assertTrue(entered.wait(3))
            try:
                second = pool.submit(step)
                with self.assertRaises(ValueError):
                    second.result(timeout=3)
            finally:
                release.set()
            first.result(timeout=3)
        self.assertEqual(1, len(calls))

    def test_failed_suite_completes_execution_but_is_not_accepted(self):
        self.review()
        fix = copy.deepcopy(self.fix)
        fix['review_sha256'] = fingerprint(cycle.artifact(self.db, self.run, 'review'))
        fix['files'] = {}  # Model claiming fixed does not make it true.
        cycle.advance(self.db, self.run, 'implement', imported=fix)
        result = cycle.advance(self.db, self.run, 'verify', execute_checks=True, allow_host=True)
        self.assertEqual('failed', result['status'])
        self.assertFalse(cycle.status(self.db, self.run)['accepted'])

    def test_no_provider_call_or_execution_without_opt_in(self):
        with self.assertRaises(ValueError):
            cycle.advance(self.db, self.run, 'review')
        self.assertEqual('pending', cycle.status(self.db, self.run)['stages']['review']['status'])
        self.implementation()
        with self.assertRaises(ValueError):
            cycle.advance(self.db, self.run, 'verify', execute_checks=True)
        self.assertEqual('pending', cycle.status(self.db, self.run)['stages']['verify']['status'])

    def test_completed_stage_resume_does_not_call_provider(self):
        expected = self.review()
        result = cycle.advance(self.db, self.run, 'review', execute_provider=True,
                               provider=lambda *a, **k: self.fail('must not repeat a paid call'))
        self.assertEqual(expected, result)
        second = cycle.connect(self.db_path)
        self.addCleanup(second.close)
        self.assertEqual(expected, cycle.artifact(second, self.run, 'review'))

    def test_unknown_provider_outcome_never_auto_retries(self):
        calls = []
        def unavailable(*args, **kwargs):
            calls.append(True)
            raise ProviderOutcomeUnknown('unknown')
        with self.assertRaises(ProviderOutcomeUnknown):
            cycle.advance(self.db, self.run, 'review', execute_provider=True, provider=unavailable)
        with self.assertRaises(ValueError):
            cycle.advance(self.db, self.run, 'review', execute_provider=True, provider=unavailable)
        self.assertEqual(1, len(calls))
        self.assertEqual('unknown', cycle.status(self.db, self.run)['stages']['review']['status'])

    def test_crashed_running_attempt_requires_explicit_reconciliation(self):
        old = cycle.claim(self.db, self.run, 'review')
        with self.assertRaises(ValueError):
            self.review()
        with self.assertRaises(ValueError):
            cycle.recover(self.db, self.run, 'review')
        cycle.recover(self.db, self.run, 'review', acknowledge_unknown=True)
        new = cycle.claim(self.db, self.run, 'review')
        self.assertGreater(new, old)
        with self.assertRaises(ValueError):
            cycle.finish(self.db, self.run, 'review', old, 'completed', {})
        self.assertEqual('running', cycle.status(self.db, self.run)['stages']['review']['status'])

    def test_retry_budget_is_bounded(self):
        for _ in range(3):
            attempt = cycle.claim(self.db, self.run, 'review')
            cycle.finish(self.db, self.run, 'review', attempt, 'unknown')
            if attempt < 3:
                cycle.recover(self.db, self.run, 'review', acknowledge_unknown=True)
        with self.assertRaises(ValueError):
            cycle.recover(self.db, self.run, 'review', acknowledge_unknown=True)

    def test_changed_config_or_suite_blocks_resume(self):
        (self.trial / 'evaluator/suite/check.py').write_text('pass')
        with self.assertRaisesRegex(ValueError, 'suite changed'):
            self.review()
        self.assertEqual('pending', cycle.status(self.db, self.run)['stages']['review']['status'])

    def test_predecessor_required_and_single_winner_claim(self):
        with self.assertRaises(ValueError):
            cycle.claim(self.db, self.run, 'implement')
        cycle.claim(self.db, self.run, 'review')
        second = cycle.connect(self.db_path)
        self.addCleanup(second.close)
        with self.assertRaises(ValueError):
            cycle.claim(second, self.run, 'review')

    def test_baseline_does_not_receive_specialist_instructions(self):
        run = cycle.begin(self.db, self.trial, arm='baseline', model='test')
        captured = []
        def provider(context, *args, **kwargs):
            captured.append(context)
            return {'artifact': self.report, 'usage': {}}
        cycle.advance(self.db, run, 'review', execute_provider=True, provider=provider)
        self.assertNotIn('Review accuracy protocol', captured[0]['instructions'])
        self.assertIn('software engineering assistant', captured[0]['instructions'])


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.context = {'instructions': 'operator rules', 'input': 'explicit source'}
        self.env = patch.dict(os.environ, {'OPENAI_API_KEY': 'private-test-key'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_provider_is_explicit_and_has_no_tools_or_storage(self):
        seen = []
        def send(payload, key, timeout):
            seen.append(payload)
            self.assertEqual('private-test-key', key)
            return response({'findings': []})
        with self.assertRaises(ValueError):
            invoke(self.context, 'test', send=send)
        result = invoke(self.context, 'test', enabled=True, send=send)
        self.assertEqual({'findings': []}, result['artifact'])
        self.assertEqual([], seen[0]['tools'])
        self.assertFalse(seen[0]['store'])
        self.assertTrue(seen[0]['text']['format']['strict'])
        self.assertEqual({'input_tokens': 123, 'output_tokens': 45}, result['usage'])
        self.assertNotIn('private-test-key', json.dumps(result))

    def test_incomplete_refusal_malformed_and_nonobject_artifacts_rejected(self):
        cases = [None, {'status': 'incomplete'}, {'status': 'completed', 'output': []},
                 {'status': 'completed', 'output': [{'type': 'message',
                   'content': [{'type': 'refusal', 'refusal': 'no'}]}]}, response([])]
        for body in cases:
            with self.subTest(body=body), self.assertRaises((ValueError, ProviderOutcomeUnknown)):
                invoke(self.context, 'test', enabled=True, send=lambda *a: body)

    def test_missing_key_no_call_and_no_redirect(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            invoke(self.context, 'test', enabled=True, send=lambda *a: self.fail('network attempted'))
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid'))


class TelemetryContextTests(Fixture):
    def test_sink_failure_cannot_hide_success_or_original_error(self):
        path = self.root / 'missing' / 'trace.jsonl'
        telemetry = Telemetry(path)
        with telemetry.span(self.run, 'review'):
            pass
        self.assertEqual(1, telemetry.dropped)
        with self.assertRaisesRegex(RuntimeError, 'original business error'):
            with telemetry.span(self.run, 'review'):
                raise RuntimeError('original business error')
        self.assertEqual(2, telemetry.dropped)

    def test_redaction_happens_before_local_write_and_export(self):
        records = []
        path = self.root / 'trace.jsonl'
        telemetry = Telemetry(path, records.append)
        with telemetry.span(self.run, 'review') as attributes:
            attributes.update({'prompt': 'secret', 'input_sha256': 'secret',
                               'input_tokens': 123, 'output_tokens': True,
                               'artifact_sha256': 'a' * 64})
        text = path.read_text()
        self.assertNotIn('secret', text)
        self.assertEqual({'input_tokens': 123, 'artifact_sha256': 'a' * 64}, records[0]['attributes'])
        self.assertEqual(records[0], json.loads(text))

    def test_bounded_context_and_baseline_context(self):
        context = pack(self.project, ['calc.py'], 'java-reviewer', 'review')
        self.assertIn('1: def add', context['input'])
        self.assertIsNone(context['token_count'])
        self.assertIn('Review accuracy protocol', context['instructions'])
        compact = pack(self.project, ['calc.py'], 'java-reviewer', 'review', deduplicate=True)
        self.assertLessEqual(compact['bytes'], context['bytes'])
        with self.assertRaises(ValueError):
            pack(self.project, ['calc.py'], 'java-reviewer', 'review', max_bytes=1024)
        for path in ('../outside', '.env', 'evaluator/answers.txt'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                pack(self.project, [path], 'java-reviewer', 'review')

    def test_container_command_is_pinned_restricted_and_cleanup_attempted(self):
        work = self.root / 'work'; work.mkdir()
        image = 'example/toolchain@sha256:' + 'a' * 64
        with patch('verify_implementation.run_check', return_value={'status': 'timeout'}) as run, \
             patch('verify_implementation.subprocess.run') as cleanup:
            result = container_check(image, ['python3', '_suite/check.py'], work, 5)
        self.assertEqual('timeout', result['status'])
        argv = run.call_args.args[0]
        for flag in ('--network=none', '--read-only', '--cap-drop=ALL', '--memory=1g'):
            self.assertIn(flag, argv)
        self.assertTrue(any('dst=/work,readonly' in arg for arg in argv))
        self.assertEqual(['docker', 'rm', '-f'], cleanup.call_args.args[0][:3])
        with self.assertRaises(ValueError):
            container_check('unpinned:latest', ['true'], work, 5)


if __name__ == '__main__':
    unittest.main()
