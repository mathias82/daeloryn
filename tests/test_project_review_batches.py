from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from approved_copilot_review import prepare, execute, source_blocks
from copilot_chat import validate
from project_review_context import snapshot


class ProjectReviewBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'demo'
        (self.project / '.git').mkdir(parents=True)

    def test_all_files_beyond_old_four_file_limit_and_whole_large_file_are_included(self):
        for n in range(7):
            (self.project / ('App%d.java' % n)).write_text('class App%d {}\n' % n)
        body = '\n'.join('int value%d = %d;' % (i, i) for i in range(1500))
        (self.project / 'Large.java').write_text(body)
        (self.project / 'README.md').write_text('Java 8 business rules')
        (self.project / 'pom.xml').write_text('<project/>')
        prepared = prepare(self.root, 'demo', 'Review', 'sonnet')
        self.assertEqual(10, len(prepared['files']))
        self.assertGreater(prepared['batch_count'], 1)
        self.assertIn('value1499', prepared['prompt'])
        self.assertIn('"end_line": 1500', prepared['prompt'])
        self.assertTrue(prepared['coverage']['all_eligible_files_included'])
        calls = []
        def transport(request, **kwargs):
            calls.append(request)
            return {'reply': 'Checked batch'}
        result = execute(prepared, 'sonnet', prepared['sha256'], transport=transport)
        self.assertEqual(prepared['batch_count'], len(calls))
        self.assertEqual('completed', result['status'])
        self.assertEqual(0, result['remaining_not_run'])
        self.assertFalse(result['tests_executed'])
        self.assertFalse(result['patch_applied'])

    def test_near_budget_project_short_lines_and_long_paths_fit_without_losing_sources(self):
        package = self.project / 'src/main/java/example/engineering/application/review'
        package.mkdir(parents=True)
        body = 'int a;\n' * 16000
        for index in range(8):
            # Explicit LF bytes: Windows text defaults expand every newline to CRLF,
            # making this near-budget fixture exceed the same 64-batch budget.
            (package / ('ExampleSourceClass%d.java' % index)).write_bytes(body.encode('utf-8'))
        prepared = prepare(self.root, 'demo', 'Review Java', 'sonnet')
        self.assertEqual(8, len(prepared['files']))
        self.assertTrue(prepared['coverage']['all_eligible_files_included'])
        self.assertLessEqual(prepared['batch_count'], 64)
        import json
        rebuilt = {}
        for prompt in prepared['prompts']:
            for line in prompt.splitlines():
                if line.startswith('{"file":'):
                    block = json.loads(line)
                    rebuilt.setdefault(block['file'], '')
                    rebuilt[block['file']] += block['source']
        self.assertEqual(set(prepared['files']), set(rebuilt))
        self.assertTrue(all(source == body for source in rebuilt.values()))

    def test_source_block_positions_and_long_line_splits_are_exact(self):
        source = 'first\r\n' + 'x' * 7000 + '\nlast'
        blocks = list(source_blocks({'path': 'App.java', 'source': source}))
        self.assertEqual(source, ''.join(block['source'] for block in blocks))
        for block in blocks:
            lines = source.splitlines(keepends=True)
            position = sum(len(line) for line in lines[:block['line'] - 1]) + block['column'] - 1
            self.assertEqual(block['source'], source[position:position + len(block['source'])])
        self.assertEqual(3, blocks[-1]['end_line'])

    def test_manifest_change_invalidates_approval_and_no_provider_is_called(self):
        path = self.project / 'App.java'
        path.write_text('class App {}')
        first = prepare(self.root, 'demo', 'Review', 'sonnet')
        path.write_text('class App { int changed; }')
        second = prepare(self.root, 'demo', 'Review', 'sonnet')
        with self.assertRaises(PermissionError):
            execute(second, 'sonnet', first['sha256'], transport=lambda _: self.fail('provider called'))
        second['prompts'][0] += 'tampered'
        with self.assertRaises(PermissionError):
            execute(second, 'sonnet', second['sha256'], transport=lambda _: self.fail('provider called'))

    def test_failure_preserves_completed_work_and_never_retries_unknown_outcome(self):
        (self.project / 'App.java').write_text('\n'.join('int v%d;' % i for i in range(2000)))
        prepared = prepare(self.root, 'demo', 'Review', 'sonnet')
        calls = []
        def transport(request, **kwargs):
            calls.append(request)
            if len(calls) == 2:
                raise RuntimeError('timeout')
            return {'reply': 'First completed batch'}
        result = execute(prepared, 'sonnet', prepared['sha256'], transport=transport)
        self.assertEqual(2, len(calls))
        self.assertEqual('partial', result['status'])
        self.assertEqual(1, result['completed_batches'])
        self.assertIn('unknown', result['failure'])
        self.assertIn('First completed batch', result['review']['reply'])

    def test_budget_omissions_exclusions_and_redaction_are_explicit(self):
        (self.project / 'App.java').write_text('class App {}\nString password = "not-real";\n')
        (self.project / '.env').write_text('FAKE=value')
        (self.project / 'node_modules').mkdir()
        (self.project / 'node_modules' / 'Ignored.java').write_text('class Ignored {}')
        with patch('project_review_context.MAX_FILE_BYTES', 1):
            data = snapshot(self.root, 'demo')
        self.assertFalse(data['all_eligible_files_included'])
        self.assertEqual('App.java', data['omitted'][0]['path'])
        data = snapshot(self.root, 'demo')
        self.assertIn('[REDACTED]', data['files'][0]['source'])
        self.assertNotIn('not-real', data['files'][0]['source'])
        self.assertTrue(any(row['path'] == 'node_modules' for row in data['excluded']))

    def test_snapshot_rejects_traversal_before_walking(self):
        for name in ['../elsewhere', '/etc', 'demo/../elsewhere']:
            with patch('project_review_context.os.scandir') as walk:
                with self.assertRaises(ValueError):
                    snapshot(self.root, name)
                walk.assert_not_called()

    def test_unicode_sources_respect_encoded_request_limits_without_losing_tail(self):
        (self.project / 'App.java').write_text('/* ' + 'α中🙂' * 12000 + ' END */', encoding='utf-8')
        prepared = prepare(self.root, 'demo', 'Review', 'sonnet')
        self.assertIn('END', prepared['prompt'])
        self.assertTrue(prepared['coverage']['all_eligible_files_included'])
        for prompt in prepared['prompts']:
            validate({'model': 'sonnet', 'messages': [{'role': 'user', 'content': prompt}]}, review_context=True)

    def test_local_budget_before_first_batch_has_known_no_provider_outcome(self):
        (self.project / 'App.java').write_text('class App {}')
        prepared = prepare(self.root, 'demo', 'Review', 'sonnet')
        with patch('approved_copilot_review.MAX_SECONDS', 0):
            result = execute(prepared, 'sonnet', prepared['sha256'], transport=lambda _: self.fail('provider called'))
        self.assertFalse(result['source_transmitted'])
        self.assertEqual(0, result['completed_batches'])
        self.assertEqual(prepared['batch_count'], result['remaining_not_run'])
        self.assertEqual('partial', result['status'])

    def test_plain_chat_limits_remain_and_review_budget_needs_internal_opt_in(self):
        request = {'model': 'sonnet', 'messages': [{'role': 'user', 'content': 'x' * 4000}]}
        with self.assertRaises(ValueError):
            validate(request)
        validate(request, review_context=True)
        with self.assertRaises(ValueError):
            validate({**request, 'review_context': True})

    def test_progress_precedes_each_call_and_disconnect_stops_future_calls(self):
        (self.project / 'App.java').write_text('int a;\n' * 8000)
        prepared = prepare(self.root, 'demo', 'Review', 'sonnet')
        events = []
        def transport(request, **kwargs):
            self.assertEqual('running', events[-1]['phase'])
            return {'reply': 'Completed finding'}
        result = execute(prepared, 'sonnet', prepared['sha256'], transport=transport, progress=events.append)
        self.assertEqual(prepared['batch_count'] * 2, len(events))
        self.assertEqual(result['completed_batches'], events[-1]['completed'])
        calls = []
        def disconnected(event):
            raise BrokenPipeError('observer disconnected')
        with self.assertRaises(BrokenPipeError):
            execute(prepared, 'sonnet', prepared['sha256'],
                    transport=lambda *a, **kw: calls.append(a), progress=disconnected)
        self.assertEqual([], calls)
