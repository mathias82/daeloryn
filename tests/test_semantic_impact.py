"""Real javac symbol resolution. Requires a JDK 17+ compiler (no source execution)."""
import copy
from contextlib import nullcontext
from unittest.mock import patch
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from semantic_impact import index, impact


class SemanticImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.files = {
            'a/Price.java': 'package a; public class Price { public int value(int n) { return n; } public int value(String s) { return s.length(); } }',
            'b/Price.java': 'package b; public class Price { public int value(int n) { return n * 2; } }',
            'app/Client.java': 'package app; public class Client { public int call(a.Price p) { return p.value(1); } }',
            'app/Facade.java': 'package app; public class Facade { public int call(Client c, a.Price p) { return c.call(p); } }',
            'app/Other.java': 'package app; public class Other { public int call(b.Price p) { return p.value(1); } }',
        }
        for name, text in cls.files.items():
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        cls.observed = index(cls.root, list(cls.files), '8')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_actual_types_and_overloads_resolved_without_running_or_generating_source(self):
        self.assertEqual('complete', self.observed['analysis_status'])
        calls = [r['target'] for r in self.observed['references'] if r['owner'] == 'app.Client#call(a.Price)']
        self.assertIn('a.Price#value(int)', calls)
        self.assertNotIn('a.Price#value(java.lang.String)', calls)
        self.assertNotIn('b.Price#value(int)', calls)
        self.assertFalse(list(self.root.rglob('*.class')))

    def test_transitive_impact_does_not_blend_same_named_types(self):
        result = impact(self.observed, ['a/Price.java'])
        self.assertEqual(['a/Price.java', 'app/Client.java', 'app/Facade.java'], result['potentially_affected'])
        self.assertTrue(all(ref['line'] >= 1 for ref in result['evidence']))
        self.assertEqual('complete', result['analysis_status'])

    def test_before_graph_retains_deleted_symbol_callers(self):
        after = copy.deepcopy(self.observed)
        after['source_sha256'].pop('a/Price.java')
        after['definitions'] = [d for d in after['definitions'] if d['path'] != 'a/Price.java']
        after['references'] = [r for r in after['references'] if r['path'] != 'a/Price.java']
        after['analysis_status'] = 'incomplete'
        result = impact(after, ['a/Price.java'], self.observed)
        self.assertIn('app/Client.java', result['potentially_affected'])
        self.assertEqual('incomplete', result['analysis_status'])

    def test_unresolved_dependency_returns_incomplete_not_verified_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Bad.java').write_text('public class Bad { Missing dependency; }')
            result = index(root, ['Bad.java'], '8')
            self.assertEqual('incomplete', result['analysis_status'])
            self.assertTrue(result['errors'])
            self.assertEqual('incomplete', impact(result, ['Bad.java'])['analysis_status'])

    def test_syntax_error_does_not_create_a_successful_empty_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Bad.java').write_text('public class Bad { int broken( }')
            result = index(root, ['Bad.java'], '8')
            self.assertEqual('incomplete', result['analysis_status'])

    def test_symlinked_system_temp_directory_keeps_canonical_project_paths(self):
        # macOS commonly exposes /var/folders through /private/var/folders.
        with tempfile.TemporaryDirectory() as parent:
            base=Path(parent)
            real=base/'real-temp'; real.mkdir()
            alias=base/'temp-alias'; alias.symlink_to(real,target_is_directory=True)
            with patch('semantic_impact.tempfile.TemporaryDirectory',return_value=nullcontext(str(alias))):
                result=index(self.root,list(self.files),'8')
            self.assertEqual('complete',result['analysis_status'])
            self.assertTrue(all(d['path'] in self.files for d in result['definitions']))
            self.assertIn('app/Client.java',impact(result,['a/Price.java'])['potentially_affected'])

    def test_symlinks_invalid_release_and_unknown_changed_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Escape.java').symlink_to(self.root / 'a/Price.java')
            with self.assertRaises(ValueError):
                index(root, ['Escape.java'], '8')
        with self.assertRaises(ValueError):
            index(self.root, list(self.files), '8 --bad-option')
        with self.assertRaises(ValueError):
            impact(self.observed, ['unknown.java'])
