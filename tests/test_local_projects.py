import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from local_projects import ProjectRegistry, candidates
from console_api import make_handler


class LocalProjectsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.one = self.base / 'group' / 'one'
        (self.one / '.git').mkdir(parents=True)
        self.two = self.base / 'group' / 'deeper' / 'two'
        (self.two / '.git').mkdir(parents=True)
        self.file = self.base / 'settings' / 'projects.json'

    def test_nested_preview_does_not_persist_and_skips_dependencies(self):
        (self.base / 'node_modules' / 'hidden' / '.git').mkdir(parents=True)
        rows = candidates(str(self.base), True)
        self.assertEqual({'one', 'two'}, {row['name'] for row in rows})
        self.assertFalse(self.file.exists())

    def test_exact_registration_persists_without_authorizing_sibling(self):
        store = ProjectRegistry(self.file)
        store.add([str(self.one)], [])
        self.assertEqual([str(self.one)], [row['path'] for row in ProjectRegistry(self.file).list()])
        self.assertEqual([str(self.one)], json.loads(self.file.read_text()))
        if os.name != 'nt':
            self.assertEqual(0o600, self.file.stat().st_mode & 0o777)
        self.assertEqual({'.git'}, {path.name for path in self.one.iterdir()})

    def test_reject_non_git_relative_symlinks_and_worktrees(self):
        for value in ['relative/path', str(self.base), str(self.base / '..')]:
            with self.assertRaises(ValueError):
                candidates(value)
        alias = self.base / 'alias'
        try:
            alias.symlink_to(self.one, target_is_directory=True)
        except OSError:
            return
        with self.assertRaises(ValueError):
            candidates(str(alias))
        worktree = self.base / 'worktree'
        worktree.mkdir()
        (worktree / '.git').write_text('gitdir: elsewhere')
        with self.assertRaises(ValueError):
            candidates(str(worktree))

    def test_collision_rejected_after_restart_and_duplicate_add_is_idempotent(self):
        store = ProjectRegistry(self.file)
        store.add([str(self.one)], [])
        store.add([str(self.one)], store.list())
        self.assertEqual(1, len(store.list()))
        duplicate = self.base / 'other' / 'one'
        (duplicate / '.git').mkdir(parents=True)
        with self.assertRaises(ValueError):
            ProjectRegistry(self.file).add([str(duplicate)], [])
        self.assertEqual([str(self.one)], json.loads(self.file.read_text()))

    def test_catalog_limit_and_registry_symlink_rejected_without_write(self):
        store = ProjectRegistry(self.file)
        existing = [{'name': 'other', 'path': str(self.two)}]
        with patch('local_projects.MAX_PROJECTS', 1):
            with self.assertRaises(ValueError):
                store.add([str(self.one)], existing)
        self.assertFalse(self.file.exists())
        self.file.parent.mkdir()
        target = self.base / 'untouched.json'
        target.write_text('[]')
        try:
            self.file.symlink_to(target)
        except OSError:
            return
        with self.assertRaises(ValueError):
            store.add([str(self.one)], [])
        self.assertEqual('[]', target.read_text())

    def test_stale_path_and_oversized_registry(self):
        store = ProjectRegistry(self.file)
        store.add([str(self.one)], [])
        self.one.rename(self.one.with_name('moved'))
        self.assertEqual([], store.list())
        self.file.write_text('x' * (512 * 1024 + 1))
        with self.assertRaises(ValueError):
            store.list()

    def test_bounded_search(self):
        with patch('local_projects.MAX_ENTRIES', 1):
            with self.assertRaises(ValueError):
                candidates(str(self.base), True)

    def start_api(self, enabled=True):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(projects_file=self.file if enabled else None))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_port

    def call(self, port, payload=None, path='/api/repositories/manage', origin=True):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = 'http://127.0.0.1:5173'
        connection.request('POST' if payload is not None else 'GET', path,
                           json.dumps(payload) if payload is not None else None, headers)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_api_requires_opt_in_origin_and_explicit_approval(self):
        port = self.start_api()
        body = {'action': 'add', 'paths': [str(self.one)], 'approved': True}
        self.assertEqual(403, self.call(port, body, origin=False)[0])
        self.assertEqual(400, self.call(port, {**body, 'approved': False})[0])
        self.assertFalse(self.file.exists())
        disabled = self.start_api(False)
        self.assertEqual(405, self.call(disabled, body)[0])
        self.assertEqual(200, self.call(port, body)[0])
        self.assertEqual(['one'], [row['name'] for row in self.call(port, path='/api/repositories')[1]['repositories']])
        # Only the selected project can be addressed by downstream source endpoints.
        self.assertEqual(200, self.call(port, {'repository': 'one'}, '/api/project-analysis')[0])
        self.assertEqual(400, self.call(port, {'repository': 'two'}, '/api/project-analysis')[0])
        restarted = self.start_api()
        self.assertEqual(1, len(self.call(restarted, path='/api/repositories')[1]['repositories']))

    def test_browse_cancellation_and_preview_never_register(self):
        port = self.start_api()
        with patch('console_api.choose_directory', return_value=''):
            self.assertEqual((200, {'path': ''}), self.call(port, {'action': 'browse'}))
        status, result = self.call(port, {'action': 'preview', 'path': str(self.base), 'recursive': True})
        self.assertEqual(200, status)
        self.assertEqual(2, len(result['candidates']))
        self.assertFalse(self.file.exists())
        self.assertEqual([], self.call(port, path='/api/repositories')[1]['repositories'])


if __name__ == '__main__':
    unittest.main()
