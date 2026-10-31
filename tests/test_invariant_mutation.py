"""Execute pinned toy invariant suites; crashes/setup errors are never kills."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from invariant_mutation import pin, evaluate, parse_result


class InvariantMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        self.suite = Path(self.temp.name) / 'trusted'
        self.root.mkdir(); self.suite.mkdir()
        (self.root / 'rule.py').write_text('def valid(n): return n > 0\n')
        (self.root / 'CONTRACT.txt').write_text('Only positive quantities are valid.\n')
        (self.suite / 'check.py').write_text('''import json
from rule import valid
passed = valid(1) is True and valid(0) is False and valid(-1) is False
print(json.dumps({'cases':[{'id':'positive-quantity','status':'passed' if passed else 'failed','assertions':3}]}))
raise SystemExit(0 if passed else 1)
''')
        self.spec = {'schema_version': 1, 'sources': ['rule.py', 'CONTRACT.txt'],
            'suite': ['check.py'], 'command': [sys.executable, '-c', "exec(open('_suite/check.py').read())"],
            'invariants': [{'id': 'positive-quantity', 'contract': {'path': 'CONTRACT.txt', 'line': 1, 'quote': 'Only positive'}}],
            'mutants': [{'id':'allow-zero','path':'rule.py','line':1,'before':'> 0','after':'>= 0','targets':['positive-quantity']}]}
        self.manifest = pin(self.root, self.suite, self.spec)

    def test_real_invariant_failure_kills_mutant_and_does_not_change_original(self):
        result = evaluate(self.root, self.suite, self.manifest, execute=True)
        self.assertEqual('passed', result['status'])
        self.assertEqual(1.0, result['mutation_score'])
        self.assertEqual('killed', result['mutants'][0]['status'])
        self.assertEqual(3, result['baseline']['assertion_count'])
        self.assertEqual('def valid(n): return n > 0\n', (self.root/'rule.py').read_text())

    def test_actual_java_8_invariant_and_mutant_execution(self):
        (self.root/'Quantity.java').write_text('public final class Quantity { public static boolean valid(int n) { return n > 0; } }\n')
        (self.suite/'QuantityChecks.java').write_text('''public final class QuantityChecks {
 public static void main(String[] args) {
  boolean valid = Quantity.valid(1);
  valid = (!Quantity.valid(0)) & valid;
  valid = (!Quantity.valid(-1)) & valid;
  System.out.println("{\\\"cases\\\":[{\\\"id\\\":\\\"positive-quantity\\\",\\\"status\\\":\\\"" + (valid ? "passed" : "failed") + "\\\",\\\"assertions\\\":3}]}");
  if (!valid) System.exit(1);
 }
}''')
        (self.suite/'run_java.py').write_text('''from pathlib import Path
import shutil, subprocess, tempfile
with tempfile.TemporaryDirectory() as target:
 compiler = [shutil.which('javac')] if shutil.which('javac') else [shutil.which('java'), '-m', 'jdk.compiler/com.sun.tools.javac.Main']
 r = subprocess.run(compiler + ['--release','8','-d',target,'Quantity.java','_suite/QuantityChecks.java'],capture_output=True)
 if r.returncode: raise SystemExit(2)
 r = subprocess.run([shutil.which('java'),'-cp',target,'QuantityChecks'],check=False)
 raise SystemExit(r.returncode)
''')
        spec=copy.deepcopy(self.spec)
        spec['sources']=['Quantity.java','CONTRACT.txt']
        spec['suite']=['run_java.py','QuantityChecks.java']
        spec['command']=[sys.executable,'_suite/run_java.py']
        spec['mutants'][0].update(path='Quantity.java')
        result=evaluate(self.root,self.suite,pin(self.root,self.suite,spec),execute=True)
        self.assertEqual('passed',result['status'],result)
        self.assertEqual('killed',result['mutants'][0]['status'])

    def test_dry_run_never_runs_test_command(self):
        result = evaluate(self.root, self.suite, self.manifest)
        self.assertEqual('not_run', result['status'])
        self.assertIsNone(result['mutation_score'])

    def test_surviving_equivalent_mutation_is_not_claimed_detected(self):
        spec = copy.deepcopy(self.spec)
        spec['mutants'][0]['after'] = '> (0)'
        result = evaluate(self.root, self.suite, pin(self.root,self.suite,spec), execute=True)
        self.assertEqual('failed', result['status'])
        self.assertEqual('survived', result['mutants'][0]['status'])
        self.assertEqual(0, result['mutation_score'])

    def test_compile_or_import_failure_does_not_count_as_kill(self):
        spec = copy.deepcopy(self.spec)
        spec['mutants'][0]['after'] = '> invalid syntax'
        result = evaluate(self.root, self.suite, pin(self.root,self.suite,spec), execute=True)
        self.assertEqual('inconclusive', result['status'])
        self.assertIsNone(result['mutation_score'])

    def test_baseline_failure_stops_mutation_scoring(self):
        (self.root/'rule.py').write_text('def valid(n): return n >= 0\n')
        spec = copy.deepcopy(self.spec)
        spec['mutants'][0].update(before='>= 0', after='> 0')
        result = evaluate(self.root,self.suite,pin(self.root,self.suite,spec),execute=True)
        self.assertEqual('baseline_not_passing', result['status'])
        self.assertEqual([], result['mutants'])

    def test_stale_source_tests_and_wrong_contract_locator_rejected(self):
        (self.suite/'check.py').write_text('print("green")')
        with self.assertRaises(ValueError):
            evaluate(self.root,self.suite,self.manifest,execute=True)
        spec = copy.deepcopy(self.spec)
        spec['invariants'][0]['contract']['quote']='not the contract'
        with self.assertRaises(ValueError):
            pin(self.root,self.suite,spec)

    def test_ambiguous_mutation_rejected_before_execution(self):
        spec = copy.deepcopy(self.spec)
        spec['mutants'][0]['before']='absent'
        with self.assertRaises(ValueError):
            pin(self.root,self.suite,spec)

    def test_zero_skipped_missing_inconsistent_and_timeout_records_not_passes(self):
        records = [({'cases':[]},0), ({'cases':[{'id':'positive-quantity','status':'passed','assertions':0}]},0),
                   ({'cases':[{'id':'positive-quantity','status':'skipped','assertions':1}]},0),
                   ({'cases':[{'id':'positive-quantity','status':'passed','assertions':1}]},1)]
        for report, code in records:
            result={'status':'passed' if code==0 else 'failed','exit_code':code,'output':json.dumps(report)}
            with self.subTest(report=report):
                self.assertEqual('inconclusive', parse_result(result,{'positive-quantity'})['status'])
        self.assertEqual('inconclusive', parse_result({'status':'timeout','exit_code':None,'output':''},{'positive-quantity'})['status'])
