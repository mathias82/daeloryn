import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('console_launcher', Path(__file__).resolve().parents[1] / 'scripts' / 'console.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class ConsoleLauncherTests(unittest.TestCase):
    def test_occupied_port_is_rejected_without_starting_or_killing_service(self):
        with socket.socket() as listener:
            try:
                listener.bind(('127.0.0.1', 8765))
            except OSError:
                self.skipTest('API port already occupied by another service')
            listener.listen()
            with self.assertRaisesRegex(RuntimeError, '8765'):
                launcher.require_free_ports()
            self.assertGreater(listener.fileno(), -1)

    def test_stop_terminates_owned_process(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=launcher.os.name == 'posix')
        self.addCleanup(lambda: launcher.stop([process]))
        launcher.stop([process])
        self.assertIsNotNone(process.poll())

    def test_failed_startup_stops_both_children_and_preserves_opt_in(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'web' / 'node_modules' / 'vite' / 'bin').mkdir(parents=True)
            (root / 'web' / 'node_modules' / 'vite' / 'bin' / 'vite.js').write_text('')
            processes = [unittest.mock.Mock(), unittest.mock.Mock()]
            with patch.object(launcher, 'ROOT', root), patch.object(launcher.shutil, 'which', return_value='/node'), patch.object(launcher, 'require_free_ports'), patch.object(launcher.subprocess, 'Popen', side_effect=processes) as spawn, patch.object(launcher, 'wait_ready', side_effect=RuntimeError('not ready')), patch.object(launcher, 'stop') as stop:
                self.assertEqual(1, launcher.main([]))
                api_args = spawn.call_args_list[0].args[0]
                self.assertNotIn('--enable-copilot-chat', api_args)
                self.assertNotIn('--enable-project-picker', api_args)
                stop.assert_called_once_with(processes)


if __name__ == '__main__':
    unittest.main()
