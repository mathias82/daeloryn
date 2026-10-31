"""Routing policy and one-shot argv tests; live Copilot behavior is not exercised."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from model_router import select, launch, model_ids

CATALOG = ['claude-haiku-test', 'claude-sonnet-test', 'claude-opus-test']


class ModelRouterTests(unittest.TestCase):
    def test_small_work_prefers_haiku_and_code_review_prefers_sonnet(self):
        self.assertEqual(CATALOG[0], select(CATALOG, 'Rephrase a README paragraph', kind='small')['requested_model'])
        for kind in ('code', 'review', 'security', 'architecture'):
            self.assertEqual(CATALOG[1], select(CATALOG, 'Inspect this implementation', kind=kind)['requested_model'])

    def test_small_label_cannot_send_observed_risk_or_previous_failure_to_haiku(self):
        for task in ('Fix payment retry', 'Update authorization', 'Διόρθωσε την πληρωμή'):
            result = select(CATALOG, task, kind='small')
            self.assertEqual(CATALOG[1], result['requested_model'])
            self.assertTrue(result['risk_detected'])
        self.assertEqual(CATALOG[2], select(CATALOG, 'Small change', kind='small', previous_failure=True)['requested_model'])

    def test_availability_allowlist_and_unavailable_preference(self):
        self.assertEqual(CATALOG[1], select(CATALOG[1:], 'Small documentation update', kind='small')['requested_model'])
        self.assertEqual(CATALOG[2], select(CATALOG, 'Implement feature', allowed=[CATALOG[2]])['requested_model'])
        with self.assertRaises(ValueError):
            select(CATALOG, 'Implement feature', allowed=[CATALOG[0]])
        with self.assertRaises(ValueError):
            select([{'id': CATALOG[1], 'available': False}], 'Implement feature')

    def test_specialist_routing_never_downgrades_a_lightweight_sounding_task(self):
        for kind in ('auto', 'small'):
            with self.subTest(kind=kind):
                result = select(CATALOG, 'Summarize this paragraph',
                                kind=kind, agent='security-reviewer')
                self.assertEqual(CATALOG[1], result['requested_model'])
                self.assertEqual('code', result['effective_kind'])
                self.assertEqual('security-reviewer', result['selected_agent'])
        with self.assertRaises(ValueError):
            select(CATALOG, 'Short summary', kind='small', agent='invented-agent')

    def test_security_identifiers_in_code_and_prose_block_small_routing(self):
        for task in ('Read tenant_id', 'Configure OAuth2', 'Audit JWT', 'RBAC rules',
                     'Review CSRF', 'Update personal_data', 'Assess race-condition'):
            with self.subTest(task=task):
                result = select(CATALOG, task, kind='small')
                self.assertTrue(result['risk_detected'])
                self.assertEqual(CATALOG[1], result['requested_model'])

    def test_runtime_policy_disabled_or_unconfigured_models_are_excluded(self):
        from types import SimpleNamespace
        models = [
            {'id': CATALOG[0], 'policy': {'state': 'disabled'}},
            SimpleNamespace(id=CATALOG[2], policy=SimpleNamespace(state='unconfigured')),
            SimpleNamespace(id=CATALOG[1], policy=SimpleNamespace(state='enabled')),
        ]
        self.assertEqual(CATALOG[1], select(models, 'Rephrase text', kind='small')['requested_model'])

    def test_unknown_models_bad_ids_and_empty_catalog_do_not_guess(self):
        for models in ([], ['unknown-engine'], ['--allow-all'], [{'id': 'bad\nmodel'}]):
            with self.subTest(models=models), self.assertRaises(ValueError):
                select(models, 'Implement a feature')
        self.assertEqual([CATALOG[1]], model_ids([{'id': CATALOG[1]}, {'id': CATALOG[1]}]))

    def test_launch_uses_single_shell_free_call_and_preserves_host_permissions(self):
        task = 'Implement feature; $(touch should-not-run)'
        plan = select(CATALOG, task, agent='java-developer')
        with tempfile.TemporaryDirectory() as tmp, patch('model_router.subprocess.run') as run:
            profile = Path(tmp) / '.github' / 'agents' / 'java-developer.agent.md'
            profile.parent.mkdir(parents=True)
            profile.write_text('installed agent definition')
            run.return_value.returncode = 1
            result = launch(plan, task, Path(tmp), 'java-developer', execute=True, executable='/reviewed/copilot')
            self.assertEqual(1, run.call_count)
            argv = run.call_args.args[0]
            self.assertEqual('--prompt=' + task, argv[-1])
            self.assertEqual('--model=' + CATALOG[1], argv[1])
            self.assertNotIn('--allow-all', argv)
            self.assertNotIn('shell', run.call_args.kwargs)
            self.assertEqual('not_verified_by_router', result['actual_model'])
            self.assertEqual('failed', result['execution'])

    def test_auto_routing_is_conservative_for_ambiguous_or_code_work(self):
        self.assertEqual(CATALOG[0], select(CATALOG, 'Translate this paragraph', kind='auto')['requested_model'])
        for task in ('Summarize Java code', 'Fix a bug', 'Help me', 'Translate payment instructions'):
            with self.subTest(task=task):
                self.assertEqual(CATALOG[1], select(CATALOG, task, kind='auto')['requested_model'])

    def test_discovery_reads_runtime_catalog_without_starting_a_model_session(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, Mock
        from model_router import discover_copilot
        client = SimpleNamespace(start=AsyncMock(), stop=AsyncMock(),
                                 list_models=AsyncMock(return_value=[{'id': CATALOG[1]}]))
        factory = Mock(return_value=client)
        connection = SimpleNamespace(for_stdio=Mock(return_value='explicit-installed-runtime'))
        with patch.dict(sys.modules, {'copilot': SimpleNamespace(CopilotClient=factory, RuntimeConnection=connection)}):
            self.assertEqual([CATALOG[1]], asyncio.run(discover_copilot('/installed/copilot')))
        connection.for_stdio.assert_called_once_with(path='/installed/copilot')
        client.list_models.assert_awaited_once()
        client.stop.assert_awaited_once()

    def test_discovery_failure_is_not_retried_or_replaced_with_an_offline_guess(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, Mock
        from model_router import discover_copilot
        client = SimpleNamespace(start=AsyncMock(), stop=AsyncMock(),
                                 list_models=AsyncMock(side_effect=RuntimeError('unavailable')))
        sdk = SimpleNamespace(CopilotClient=Mock(return_value=client),
                              RuntimeConnection=SimpleNamespace(for_stdio=Mock(return_value='runtime')))
        with patch.dict(sys.modules, {'copilot': sdk}), self.assertRaises(RuntimeError):
            asyncio.run(discover_copilot('/installed/copilot'))
        client.list_models.assert_awaited_once()
        client.stop.assert_awaited_once()

    def test_no_launch_without_opt_in_or_if_task_changes(self):
        task = 'Implement feature'
        plan = select(CATALOG, task, agent='java-developer')
        with patch('model_router.subprocess.run') as run, tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / '.github' / 'agents' / 'java-developer.agent.md'
            profile.parent.mkdir(parents=True)
            profile.write_text('installed agent definition')
            with self.assertRaises(ValueError):
                launch(plan, task, tmp, 'java-developer')
            with self.assertRaises(ValueError):
                launch(plan, 'other task', tmp, 'java-developer', execute=True)
            with self.assertRaises(ValueError):
                launch(plan, task, tmp, 'security-reviewer', execute=True)
            self.assertEqual(0, run.call_count)

    def test_launch_fails_closed_for_missing_and_symlinked_agent_profiles(self):
        plan = select(CATALOG, 'Implement feature', agent='java-developer')
        with tempfile.TemporaryDirectory() as tmp, patch('model_router.subprocess.run') as run:
            with self.assertRaises(ValueError):
                launch(plan, 'Implement feature', tmp, 'java-developer',
                       execute=True, executable='/installed/copilot')
            profile = Path(tmp) / '.github' / 'agents' / 'java-developer.agent.md'
            profile.parent.mkdir(parents=True)
            outside = Path(tmp) / 'external-agent.md'
            outside.write_text('do not follow')
            profile.symlink_to(outside)
            with self.assertRaises(ValueError):
                launch(plan, 'Implement feature', tmp, 'java-developer',
                       execute=True, executable='/installed/copilot')
            self.assertEqual(0, run.call_count)
