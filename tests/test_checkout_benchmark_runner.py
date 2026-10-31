"""Wrapper contract tests with synthetic Git objects, not Java/model scoring."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_checkout_benchmark import evaluate, PREFIX


class CheckoutRunnerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / 'existing-copy'
        self.project.mkdir()
        self.original = {'src/main/java/Example.java': b'original',
                         'pom.xml': b'original-build', 'README.md': b'contract'}
        self.suite = {'run_contract.py': b"from pathlib import Path\nassert Path('src/main/java/Example.java').read_text() == 'corrected'\n",
                      'CheckoutContractSuite.java': b'// synthetic wrapper fixture only\n'}
        for name, data in self.original.items():
            target = self.project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        def git(*args):
            if args[0] == 'rev-parse':
                return b'frozen-commit\n'
            if args[0] == 'ls-tree':
                return (PREFIX + 'src/main/java/Example.java\n').encode()
            if args[0] == 'show':
                name = args[1].split(':', 1)[1][len(PREFIX):]
                return self.suite[name[len('evaluator/'):]] if name.startswith('evaluator/') else self.original[name]
            self.fail('unexpected git operation')
        stub = patch('check_checkout_benchmark.git', side_effect=git)
        stub.start()
        self.addCleanup(stub.stop)

    def test_dry_run_never_executes_candidate(self):
        with patch('check_checkout_benchmark.verify', side_effect=AssertionError('executed')):
            result = evaluate(self.project)
        self.assertEqual('prepared_only_checks_not_run', result['status'])
        self.assertFalse(result['provider_invoked'])

    def test_existing_copy_compared_to_frozen_original_without_modification(self):
        target = self.project / 'src/main/java/Example.java'
        target.write_text('corrected')
        result = evaluate(self.project, execute=True)
        self.assertEqual('failed', result['original']['status'])
        self.assertEqual('passed', result['candidate']['status'])
        self.assertEqual('corrected', target.read_text())
        self.assertEqual('frozen-commit', result['benchmark_commit'])
        self.assertEqual(result['suite_sha256']['run_contract.py'], result['candidate']['suite_sha256']['run_contract.py'])

    def test_original_copy_fails_same_independent_suite(self):
        result = evaluate(self.project, execute=True)
        self.assertEqual('failed', result['status'])
        self.assertEqual(result['original']['source_sha256'], result['candidate']['source_sha256'])

    def test_changed_build_extra_helper_or_missing_source_are_not_silently_ignored(self):
        (self.project / 'pom.xml').write_text('different-build')
        with self.assertRaises(ValueError):
            evaluate(self.project)
        (self.project / 'pom.xml').write_bytes(self.original['pom.xml'])
        helper = self.project / 'src/main/java/Helper.java'
        helper.write_text('helper')
        with self.assertRaises(ValueError):
            evaluate(self.project)
        helper.unlink()
        (self.project / 'src/main/java/Example.java').unlink()
        with self.assertRaises(ValueError):
            evaluate(self.project)


if __name__ == '__main__':
    unittest.main()
