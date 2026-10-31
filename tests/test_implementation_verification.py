"""Exercise the evaluator with toy code, not real provider/model runs."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from agents import catalog, install
from verify_implementation import prepare, verify


class ImplementationVerificationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = self.root / 'project'
        self.suite = self.root / 'suite'
        self.project.mkdir()
        self.suite.mkdir()
        (self.project / 'calc.py').write_text('def add(a, b): return a - b\n')
        (self.project / 'runtime.txt').write_text('pinned runtime\n')
        (self.suite / 'check.py').write_text(
            'from calc import add\nassert add(2, 3) == 5\nassert add(-2, 3) == 1\n')
        self.trial = self.root / 'trial'
        self.command = [sys.executable, '-c',
                        "exec(open('_suite/check.py').read())"]

    def prepare(self, checks=None):
        return prepare(self.project, ['calc.py', 'runtime.txt'], ['calc.py'],
                       self.suite, ['check.py'], checks or {'correctness': self.command},
                       self.trial)

    def test_original_fails_fixed_arm_passes_other_arm_stays_broken(self):
        manifest = self.prepare()
        self.assertEqual('prepared_only_no_model_runs', manifest['status'])
        self.assertFalse((self.trial / 'baseline/_suite').exists())
        self.assertTrue((self.trial / 'daeloryn/.github/agents/java-developer.agent.md').exists())
        self.assertEqual('failed', verify(self.trial, 'original')['status'])
        (self.trial / 'daeloryn/calc.py').write_text('def add(a, b): return a + b\n')
        result = verify(self.trial, 'daeloryn')
        self.assertEqual('passed', result['status'])
        self.assertEqual(['calc.py'], result['changed_files'])
        self.assertEqual(manifest['suite_sha256'], result['suite_sha256'])
        self.assertEqual('failed', verify(self.trial, 'baseline')['status'])

    def test_candidate_replacement_suite_and_build_outputs_are_not_used(self):
        self.prepare()
        (self.trial / 'daeloryn/_suite').mkdir()
        (self.trial / 'daeloryn/_suite/check.py').write_text('pass\n')
        (self.trial / 'daeloryn/calc.pyc').write_bytes(b'not trusted')
        self.assertEqual('failed', verify(self.trial, 'daeloryn')['status'])

    def test_tampered_evaluator_suite_rejected(self):
        self.prepare()
        (self.trial / 'evaluator/suite/check.py').write_text('pass\n')
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            verify(self.trial, 'baseline')

    def test_tampered_original_rejected(self):
        self.prepare()
        (self.trial / 'evaluator/source/calc.py').write_text('pass\n')
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            verify(self.trial, 'original')

    def test_frozen_build_context_changes_rejected(self):
        self.prepare()
        (self.trial / 'baseline/runtime.txt').write_text('different runtime')
        with self.assertRaisesRegex(ValueError, 'frozen context'):
            verify(self.trial, 'baseline')

    def test_candidate_missing_file_or_symlink_rejected(self):
        self.prepare()
        path = self.trial / 'baseline/calc.py'
        path.unlink()
        with self.assertRaises(ValueError):
            verify(self.trial, 'baseline')
        path.symlink_to(self.project / 'calc.py')
        with self.assertRaises(ValueError):
            verify(self.trial, 'baseline')

    def test_timeout_and_runner_error_are_not_passes(self):
        self.prepare({'timeout': [sys.executable, '-c', 'import time; time.sleep(10)'],
                      'missing_tool': ['nonexistent-daeloryn-tool-8712']})
        result = verify(self.trial, 'original', timeout=1)
        self.assertEqual('failed', result['status'])
        self.assertEqual('timeout', result['checks']['timeout']['status'])
        self.assertEqual('runner_error', result['checks']['missing_tool']['status'])

    def test_gates_have_independent_fresh_inputs(self):
        self.prepare({'modify': [sys.executable, '-c', "open('runtime.txt','w').write('changed')"],
                      'inspect': [sys.executable, '-c',
                                  "assert open('runtime.txt').read() == 'pinned runtime\\n'"]})
        self.assertEqual('passed', verify(self.trial, 'original')['status'])

    def test_invalid_prepare_writes_nothing(self):
        for kwargs in ({'files': ['../escape']}, {'editable': ['missing']},
                       {'checks': {'x': []}}, {'agent': 'unknown'}):
            options = dict(project=self.project, files=['calc.py'], editable=['calc.py'],
                           suite=self.suite, suite_files=['check.py'],
                           checks={'correctness': self.command}, output=self.trial)
            options.update(kwargs)
            with self.subTest(options=kwargs), self.assertRaises(ValueError):
                prepare(**options)
            self.assertFalse(self.trial.exists())

    def test_existing_output_preserved(self):
        self.prepare()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertTrue((self.trial / 'evaluator/manifest.json').is_file())


class AgentAcceptanceTests(unittest.TestCase):
    def test_all_definitions_and_88_adapters_preserve_acceptance_protocol(self):
        sections = ('Executable verification handoff (mandatory)',
                    'Production quality acceptance (mandatory)',
                    'Security settings verification (mandatory)')
        specialties = set()
        entries = catalog()
        self.assertEqual(22, len(entries))
        for meta, body in entries:
            for section in sections:
                self.assertEqual(1, body.count('## ' + section), meta['name'])
            specialties.add(body.split('**Specialty acceptance:**', 1)[1].strip())
            for phrase in ('bounded label cardinality', 'error provenance',
                           'code_quality', 'failed compensation', 'not run',
                           'actual declared and runtime types', 'blinded human assessment',
                           'TLS verification', 'CORS/CSRF', 'denied-access regression check'):
                self.assertIn(phrase, body)
        self.assertEqual(22, len(specialties))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(88, install(target, 'all', 'all'))
            for meta, body in entries:
                name = meta['name']
                paths = [f'.codex/agents/{name}.toml', f'.claude/agents/{name}.md',
                         f'.github/agents/{name}.agent.md', f'.gemini/agents/{name}.md']
                for relative in paths:
                    rendered = (target / relative).read_text()
                    if relative.endswith('.toml'):
                        rendered = tomllib.loads(rendered)['developer_instructions']
                    with self.subTest(agent=name, adapter=relative):
                        # Windows Git checkouts may use CRLF while the
                        # generated adapters use LF. Compare logical lines.
                        # A Windows text-mode write can expand CRLF source to
                        # CRCRLF. Remove carriage returns only for this
                        # content-equivalence assertion, preserving all text.
                        normalized_body = body.replace('\r', '')
                        normalized_rendered = rendered.replace('\r', '')
                        self.assertIn(normalized_body, normalized_rendered)


if __name__ == '__main__':
    unittest.main()
