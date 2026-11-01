"""Smoke tests for the root POSIX launcher without invoking real providers."""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "start.sh"


@unittest.skipUnless(os.name == "posix", "start.sh requires a POSIX shell")
class StartScriptTests(unittest.TestCase):
    def test_executable_syntax_and_no_install_or_background(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(SCRIPT.stat().st_mode & stat.S_IXUSR, "start.sh must be executable in git")
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, capture_output=True)
        text = SCRIPT.read_text()
        self.assertIn("exec python3", text)
        self.assertNotIn("npm install", text)
        self.assertNotIn("killall", text)

    def test_passes_flags_and_arguments_from_another_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "checkout"
            root.mkdir()
            script = root / "start.sh"
            shutil.copy2(SCRIPT, script)
            (root / "scripts").mkdir()
            (root / "scripts" / "console.py").write_text("# mock launcher\n")
            vite = root / "web" / "node_modules" / "vite" / "bin"
            vite.mkdir(parents=True)
            (vite / "vite.js").write_text("// fixture\n")
            executables = Path(temp) / "bin"
            executables.mkdir()
            for name, body in (
                ("node", "#!/bin/sh\nexit 0\n"),
                ("python3", "#!/bin/sh\nprintf 'ARG=%s\\n' \"$@\"\n"),
            ):
                executable = executables / name
                executable.write_text(body)
                executable.chmod(0o755)
            environment = dict(os.environ, PATH=str(executables) + os.pathsep + os.environ["PATH"])
            completed = subprocess.run([str(script), "--repository-root", "/tmp/fixture"],
                                       cwd="/", env=environment, capture_output=True,
                                       text=True, timeout=5, check=True)
            self.assertEqual(completed.stdout.splitlines(), [
                "ARG=" + str(root / "scripts" / "console.py"),
                "ARG=--enable-copilot-chat",
                "ARG=--enable-project-picker",
                "ARG=--open",
                "ARG=--repository-root",
                "ARG=/tmp/fixture",
            ])

    def test_missing_frontend_does_not_start_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "checkout"
            root.mkdir()
            script = root / "start.sh"
            shutil.copy2(SCRIPT, script)
            # No node_modules directory => no backend process should be started.
            result = subprocess.run([str(script)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertIn("npm ci", result.stderr)


if __name__ == "__main__":
    unittest.main()
