#!/usr/bin/env python3
"""Start the local API and Vite together; stop both with Ctrl+C.

Uses existing dependencies. Never installs packages or enables AI by default.
"""
import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def require_free_ports():
    sockets = []
    try:
        for port in (8765, 5173):
            probe = socket.socket()
            sockets.append(probe)
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1', port))
            except OSError as exc:
                raise RuntimeError(f'Port {port} is already in use. Stop the existing API/frontend first.') from exc
    finally:
        for probe in sockets:
            probe.close()


def stop(processes):
    for process in reversed(processes):
        if process.poll() is None:
            try:
                if os.name == 'posix':
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
            except ProcessLookupError:
                pass
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()


def wait_ready(processes, urls, timeout=20):
    deadline = time.monotonic() + timeout
    # Never route local health requests through an environment HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    remaining = set(urls)
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError('A console process exited during startup; see its output above.')
        for url in tuple(remaining):
            try:
                with opener.open(url, timeout=0.5) as response:
                    if response.status == 200:
                        remaining.remove(url)
            except (OSError, urllib.error.URLError):
                pass
        if not remaining:
            return
        time.sleep(0.1)
    raise RuntimeError('Console startup timed out; both processes will be stopped.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-copilot-chat', action='store_true')
    parser.add_argument('--enable-local-chat', action='store_true')
    parser.add_argument('--enable-project-picker', action='store_true')
    parser.add_argument('--enable-github-repositories', action='store_true')
    parser.add_argument('--repository-root', action='append', default=[])
    parser.add_argument('--project-picker-root', action='append', default=[])
    parser.add_argument('--projects-file')
    parser.add_argument('--records-dir')
    parser.add_argument('--workflow-dir')
    parser.add_argument('--open', action='store_true', help='open the console in your default browser')
    args = parser.parse_args(argv)
    processes = []
    try:
        node = shutil.which('node')
        vite = ROOT / 'web' / 'node_modules' / 'vite' / 'bin' / 'vite.js'
        if not node or not vite.is_file():
            raise RuntimeError('Install Node.js and frontend dependencies first: cd web && npm install')
        require_free_ports()
        api = [sys.executable, str(ROOT / 'scripts' / 'console_api.py')]
        for flag in ('enable_copilot_chat', 'enable_local_chat', 'enable_project_picker', 'enable_github_repositories'):
            if getattr(args, flag):
                api.append('--' + flag.replace('_', '-'))
        for root in args.repository_root:
            api.extend(['--repository-root', root])
        for root in args.project_picker_root:
            api.extend(['--project-picker-root', root])
        for flag in ('projects_file', 'records_dir', 'workflow_dir'):
            if getattr(args, flag):
                api.extend(['--' + flag.replace('_', '-'), getattr(args, flag)])
        commands = [api, [node, str(vite), '--host', '127.0.0.1', '--port', '5173', '--strictPort']]
        for command in commands:
            processes.append(subprocess.Popen(command, cwd=ROOT / 'web' if command[0] == node else ROOT,
                                              start_new_session=os.name == 'posix'))
        wait_ready(processes, ['http://127.0.0.1:8765/api/health', 'http://127.0.0.1:5173/'])
        print('\nDaeloryn ready: http://127.0.0.1:5173 — Ctrl+C stops frontend and backend.', flush=True)
        if args.open:
            webbrowser.open('http://127.0.0.1:5173/')
        while True:
            for process in processes:
                if process.poll() is not None:
                    raise RuntimeError('A console process exited; stopping its companion.')
            time.sleep(0.2)
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError) as exc:
        print('Console startup failed: ' + str(exc), file=sys.stderr)
        return 1
    finally:
        stop(processes)


if __name__ == '__main__':
    raise SystemExit(main())
