"""Executable visible-feedback loop with mocked provider; no model-quality claims."""
import copy
import json
from pathlib import Path
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from test_engineering_cycle import Fixture
import engineering_cycle as cycle
import engineering_repair as repair
from engineering_handoff import fingerprint
from openai_artifact_adapter import ProviderOutcomeUnknown


class RepairTests(Fixture):
    def setUp(self):
        super().setUp()
        self.visible = self.root / 'visible'
        self.visible.mkdir()
        (self.visible / 'check.py').write_text('''import json
from calc import add
ok = add(4, 5) == 9
print(json.dumps({'cases': [{'id': 'addition', 'status': 'passed' if ok else 'failed', 'assertions': 1}]}))
raise SystemExit(0 if ok else 1)
''')
        self.plan = {'suite_root': str(self.visible), 'suite_files': ['check.py'],
                     'command': [sys.executable, '_visible/check.py'], 'cases': ['addition']}
        # Use -c to give Python the reconstructed project as sys.path[0].
        self.plan['command'] = [sys.executable, '-c', "exec(open('_visible/check.py').read())"]
        self.review()
        self.initial = copy.deepcopy(self.fix)
        self.initial['review_sha256'] = fingerprint(cycle.artifact(self.db, self.run, 'review'))
        self.initial['files'] = {}
        cycle.advance(self.db, self.run, 'implement', imported=self.initial)
        self.calls = []

    def provider(self, context, model, **kwargs):
        self.calls.append((context, kwargs))
        fixed = {**self.fix, 'review_sha256': self.initial['review_sha256']}
        return {'artifact': fixed, 'usage': {'input_tokens': 12, 'output_tokens': 8},
                'response_id': 'mock', 'actual_model': 'mock-model'}

    def repair(self, **kwargs):
        return repair.run(self.db, self.run, self.plan, execute_provider=True,
                          execute_checks=True, allow_host=True,
                          provider=kwargs.pop('provider', self.provider), **kwargs)

    def test_failed_candidate_repaired_and_independently_verified_without_changing_user_copy(self):
        result = self.repair(max_repairs=2, max_output_tokens=256)
        self.assertEqual('passed', result['status'])
        self.assertEqual(1, result['rounds'])
        self.assertFalse(cycle.status(self.db, self.run)['accepted'])
        context, limits = self.calls[0]
        self.assertIn('addition', context['input'])
        self.assertIn('add(4, 5)', context['input'])
        self.assertNotIn("assert add(2, 3) == 5", context['input'])
        self.assertNotIn('original_checks', context['input'])
        self.assertEqual(256, limits['max_output_tokens'])
        final = cycle.advance(self.db, self.run, 'verify', execute_checks=True, allow_host=True)
        self.assertEqual('passed', final['status'])
        self.assertTrue(cycle.status(self.db, self.run)['accepted'])
        self.assertIn('a - b', (self.trial / 'daeloryn/calc.py').read_text())
        events = self.db.execute('SELECT kind,value FROM engineering_repair_events WHERE run=?',
                                 (self.run,)).fetchall()
        self.assertEqual(2, sum(k == 'visible_check' for k, v in events))
        self.assertEqual(12, json.loads(next(v for k, v in events if k == 'provider_result'))['usage']['input_tokens'])

    def test_completed_resume_is_cached_without_repeating_checks_or_provider(self):
        expected = self.repair()
        with patch('engineering_repair.run_check', side_effect=AssertionError('repeated check')):
            actual = self.repair(provider=lambda *a, **k: self.fail('repeated paid call'))
        self.assertEqual(expected, actual)

    def test_repeated_candidate_stops_and_blocks_independent_acceptance(self):
        result = self.repair(provider=lambda *a, **k: {'artifact': self.initial})
        self.assertEqual('stalled', result['status'])
        with self.assertRaisesRegex(ValueError, 'repair has not passed'):
            cycle.advance(self.db, self.run, 'verify', execute_checks=True, allow_host=True)
        self.assertEqual('pending', cycle.status(self.db, self.run)['stages']['verify']['status'])

    def test_attempt_budget_counts_provider_calls_and_never_selects_unchecked_candidate(self):
        def wrong(context, model, **kwargs):
            self.calls.append(True)
            candidate = copy.deepcopy(self.initial)
            candidate['files'] = {'calc.py': 'def add(a, b): return 0 # round %d\n' % len(self.calls)}
            return {'artifact': candidate}
        result = self.repair(provider=wrong, max_repairs=2)
        self.assertEqual('attempt_budget_exhausted', result['status'])
        self.assertEqual(2, len(self.calls))
        self.assertEqual(2, result['rounds'])
        self.assertEqual('failed', result['visible_checks']['status'])

    def test_unknown_provider_outcome_is_never_retried(self):
        def unknown(*args, **kwargs):
            self.calls.append(True)
            raise ProviderOutcomeUnknown('timeout')
        with self.assertRaises(ProviderOutcomeUnknown):
            self.repair(provider=unknown)
        with self.assertRaisesRegex(ValueError, 'running/unknown'):
            self.repair(provider=unknown)
        self.assertEqual(1, len(self.calls))
        self.assertEqual('unknown', cycle.status(self.db, self.run)['repair']['state'])

    def test_timeout_invalid_zero_skipped_and_incomplete_cases_do_not_pass_or_trigger_repairs(self):
        for raw in (
            {'status': 'timeout', 'exit_code': None, 'output': ''},
            {'status': 'runner_error', 'exit_code': None, 'output': 'missing tool'},
            {'status': 'failed', 'exit_code': 2, 'output': 'compile error'},
            {'status': 'passed', 'exit_code': 0, 'output': '{"cases":[]}'},
            {'status': 'passed', 'exit_code': 0, 'output': '{"cases":[{"id":"addition","status":"skipped","assertions":0}]}'},
        ):
            # Each scenario is a separate trial run, not a retry of an unknown effect.
            run_id = cycle.begin(self.db, self.trial, model='test')
            cycle.advance(self.db, run_id, 'review', imported=self.report)
            handoff = cycle.artifact(self.db, run_id, 'review')
            cycle.advance(self.db, run_id, 'implement', imported={**self.initial, 'review_sha256': fingerprint(handoff)})
            with self.subTest(raw=raw), patch('engineering_repair.run_check', return_value=raw):
                result = repair.run(self.db, run_id, self.plan, execute_provider=True,
                                    execute_checks=True, allow_host=True, provider=self.provider)
                self.assertEqual('inconclusive', result['status'])
        self.assertEqual([], self.calls)

    def test_changed_visible_tests_or_budget_blocks_cached_reuse(self):
        self.repair()
        with self.assertRaisesRegex(ValueError, 'policy or visible tests changed'):
            self.repair(max_repairs=1)
        (self.visible / 'check.py').write_text('print("weakened")')
        with self.assertRaisesRegex(ValueError, 'policy or visible tests changed'):
            self.repair()

    def test_visible_tests_cannot_point_to_or_duplicate_independent_evaluator(self):
        self.plan['suite_root'] = str(self.trial / 'evaluator/suite')
        with self.assertRaisesRegex(ValueError, 'separate'):
            self.repair()
        self.plan['suite_root'] = str(self.visible)
        (self.visible / 'check.py').write_bytes((self.suite / 'check.py').read_bytes())
        with self.assertRaisesRegex(ValueError, 'cannot be reused'):
            self.repair()

    def test_undeclared_edit_rejected_and_unknown_cannot_be_accepted(self):
        def injected(*args, **kwargs):
            return {'artifact': {**self.initial, 'files': {'runtime.txt': 'bypass'}}}
        with self.assertRaisesRegex(ValueError, 'undeclared edit'):
            self.repair(provider=injected)
        with self.assertRaises(ValueError):
            cycle.advance(self.db, self.run, 'verify', execute_checks=True, allow_host=True)

    def test_explicit_opt_ins_and_finite_budgets_required_before_claim(self):
        for options in ({}, {'execute_provider': True},
                        {'execute_provider': True, 'execute_checks': True},
                        {'execute_provider': True, 'execute_checks': True, 'allow_host': True, 'max_repairs': 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                repair.run(self.db, self.run, self.plan, **options)
        self.assertIsNone(cycle.status(self.db, self.run)['repair'])

    def test_wall_budget_stops_before_provider_and_does_not_accept_unchecked_patch(self):
        with patch('engineering_repair.time.monotonic', side_effect=[0, 0, 0, 2]):
            result = self.repair(max_seconds=1)
        self.assertEqual('time_budget_exhausted', result['status'])
        self.assertEqual([], self.calls)

    def test_concurrent_repair_and_verification_cannot_duplicate_work(self):
        entered, release = threading.Event(), threading.Event()
        def provider(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test coordination timeout')
            return self.provider(*args, **kwargs)
        def worker():
            db = cycle.connect(self.db_path)
            try:
                return repair.run(db, self.run, self.plan, execute_provider=True,
                                  execute_checks=True, allow_host=True, provider=provider)
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            task = pool.submit(worker)
            self.assertTrue(entered.wait(3))
            try:
                with self.assertRaisesRegex(ValueError, 'running/unknown'):
                    self.repair()
                with self.assertRaises(ValueError):
                    cycle.advance(self.db, self.run, 'verify', execute_checks=True, allow_host=True)
            finally:
                release.set()
            self.assertEqual('passed', task.result(timeout=3)['status'])
        self.assertEqual(1, len(self.calls))

    def test_two_repairs_use_latest_candidate_and_preserve_independent_gate(self):
        def provider(context, model, **kwargs):
            self.calls.append(context)
            candidate = copy.deepcopy(self.initial)
            candidate['files'] = {'calc.py': ('def add(a, b): return 0\n' if len(self.calls) == 1
                                             else self.fix['files']['calc.py'])}
            return {'artifact': candidate}
        result = self.repair(provider=provider, max_repairs=2)
        self.assertEqual('passed', result['status'])
        self.assertEqual(2, result['rounds'])
        self.assertIn('return 0', self.calls[1]['input'])
        self.assertEqual('not_run', result['independent_acceptance'])

    def test_visible_pass_does_not_mask_independent_regression(self):
        def overfit(*args, **kwargs):
            return {'artifact': {**self.initial, 'files': {'calc.py': 'def add(a, b): return 9\n'}}}
        self.assertEqual('passed', self.repair(provider=overfit)['status'])
        final = cycle.advance(self.db, self.run, 'verify', execute_checks=True, allow_host=True)
        self.assertEqual('failed', final['status'])
        self.assertFalse(cycle.status(self.db, self.run)['accepted'])

    def test_already_passing_candidate_needs_no_paid_repair(self):
        # Different run with a genuine passing implementation artifact.
        run_id = cycle.begin(self.db, self.trial, model='test')
        cycle.advance(self.db, run_id, 'review', imported=self.report)
        handoff = cycle.artifact(self.db, run_id, 'review')
        cycle.advance(self.db, run_id, 'implement',
                      imported={**self.fix, 'review_sha256': fingerprint(handoff)})
        result = repair.run(self.db, run_id, self.plan, execute_provider=True, execute_checks=True,
                            allow_host=True, provider=lambda *a, **k: self.fail('unnecessary paid call'))
        self.assertEqual('passed', result['status'])
        self.assertEqual(0, result['rounds'])

    def test_selected_react_agent_reaches_repair_context(self):
        run_id = cycle.begin(self.db, self.trial, model='test', reviewer_agent='react-reviewer',
                             developer_agent='react-developer')
        cycle.advance(self.db, run_id, 'review', imported=self.report)
        handoff = cycle.artifact(self.db, run_id, 'review')
        cycle.advance(self.db, run_id, 'implement',
                      imported={**self.initial, 'review_sha256': fingerprint(handoff)})
        def provider(context, *args, **kwargs):
            self.assertIn('# react-developer', context['instructions'])
            self.assertNotIn('# java-developer', context['instructions'])
            return {'artifact': {**self.fix, 'review_sha256': fingerprint(handoff)}}
        result = repair.run(self.db, run_id, self.plan, execute_provider=True, execute_checks=True,
                            allow_host=True, provider=provider)
        self.assertEqual('passed', result['status'])

    def test_non_java_agents_selected_and_read_only_roles_not_repair_executors(self):
        run_id = cycle.begin(self.db, self.trial, reviewer_agent='react-reviewer', developer_agent='react-developer')
        self.assertEqual('react-developer', cycle.load(self.db, run_id)['developer_agent'])
        for name in ('java-reviewer', 'react-architect', 'security-reviewer'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'read-only'):
                cycle.begin(self.db, self.trial, developer_agent=name)
