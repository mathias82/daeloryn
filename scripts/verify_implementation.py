#!/usr/bin/env python3
"""Prepare paired implementation trials and run trusted, pinned evaluator checks.

Runs code with the caller's permissions. This is NOT a sandbox or an AI runner.
Only explicitly selected candidate files enter the disposable evaluation copy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import uuid

from agents import ROOT, catalog, format_copilot


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_file(root, name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('invalid relative file path')
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != name:
        raise ValueError('noncanonical relative file path: ' + name)
    target = root / path
    if target.resolve() != target.absolute() or not target.is_file():
        raise ValueError('missing file or symlink: ' + name)
    return target.read_bytes()


def checks_valid(checks):
    if not isinstance(checks, dict) or not checks:
        raise ValueError('checks must be a nonempty object of name -> argv')
    for name, command in checks.items():
        if (not isinstance(name, str) or not name.strip()
                or not isinstance(command, list) or not command
                or not all(isinstance(arg, str) and arg and '\x00' not in arg for arg in command)):
            raise ValueError('each check requires a name and nonempty argv strings')


def write_files(root, files):
    for name, data in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def prepare(project, files, editable, suite, suite_files, checks, output,
            agent='java-developer'):
    project, suite = Path(project).resolve(strict=True), Path(suite).resolve(strict=True)
    output = Path(output).absolute()

    # Normalize macOS system aliases such as /var -> /private/var.
    # The output itself must be new; resolve the existing parent first.
    parent = output.parent.resolve(strict=True)

    if output.exists() or output.is_symlink():
        raise ValueError('output must be new')

    if output.name in ('', '.', '..'):
        raise ValueError('invalid output directory')

    output = parent / output.name
    if any(output == root or root in output.parents or output in root.parents
           for root in (project, suite, ROOT)):
        raise ValueError('trial must be separate from project, suite and Daeloryn checkout')
    checks_valid(checks)
    sources = {name: read_file(project, name) for name in files}
    tests = {name: read_file(suite, name) for name in suite_files}
    if not sources or not tests or not editable or not set(editable) <= sources.keys():
        raise ValueError('source, suite and editable lists required; editable must be selected')
    for name in sources:
        if (any(part.startswith('.') for part in Path(name).parts)
                or Path(name).name.lower() in ('agents.md', 'claude.md', 'gemini.md')
                or any(word in name.lower() for word in ('ground-truth', 'answer-key', 'gold-label'))
                or Path(name).parts[0] == '_suite'):
            raise ValueError('instructions, answer keys or reserved paths cannot enter arms')
    definitions = [(m, b) for m, b in catalog() if m['name'] == agent]
    if len(definitions) != 1:
        raise ValueError('unknown specialist agent')
    instructions = format_copilot(*definitions[0]).encode()
    manifest = {
        'schema_version': 1, 'status': 'prepared_only_no_model_runs',
        'source_sha256': {k: digest(v) for k, v in sources.items()},
        'suite_sha256': {k: digest(v) for k, v in tests.items()},
        'editable': sorted(set(editable)), 'checks': checks,
        'agent': agent, 'agent_sha256': digest(instructions),
    }
    output.mkdir(parents=True)
    for arm in ('baseline', 'daeloryn'):
        write_files(output / arm, sources)
    write_files(output / 'daeloryn', {
        '.github/agents/' + agent + '.agent.md': instructions})
    write_files(output / 'evaluator/source', sources)
    write_files(output / 'evaluator/suite', tests)
    (output / 'evaluator/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def run_check(command, work, timeout):
    # Regular files avoid deadlock/unbounded RAM if a candidate floods output.
    with tempfile.TemporaryFile() as log:
        try:
            process = subprocess.Popen(command, cwd=work, stdout=log,
                                       stderr=subprocess.STDOUT,
                                       start_new_session=(os.name == 'posix'))
        except OSError as exc:
            return {'status': 'runner_error', 'exit_code': None, 'output': str(exc)}
        try:
            code = process.wait(timeout=timeout)
            status = 'passed' if code == 0 else 'failed'
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()
            code, status = None, 'timeout'
        log.seek(0, 2)
        size = log.tell()
        log.seek(max(0, size - 65536))
        return {'status': status, 'exit_code': code,
                'output': log.read().decode('utf-8', errors='replace'),
                'output_truncated': size > 65536}


def container_check(image, command, work, timeout):
    from sandbox_runner import DIGEST_IMAGE
    if not isinstance(image, str) or not DIGEST_IMAGE.fullmatch(image):
        raise ValueError('sandbox image must be digest-pinned')
    name = 'daeloryn-check-' + uuid.uuid4().hex
    argv = ['docker', 'run', '--rm', '--pull=never', '--name', name, '--network=none',
            '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--pids-limit=128', '--memory=1g', '--cpus=1', '--user=65534:65534',
            '--tmpfs=/tmp:rw,nosuid,size=256m', '--workdir=/work',
            '--mount', 'type=bind,src=' + str(work) + ',dst=/work,readonly',
            '--entrypoint', command[0], image] + command[1:]
    # Permit the container's unprivileged UID to read only this disposable snapshot.
    work.chmod(0o755)
    result = None
    try:
        result = run_check(argv, work, timeout)
        return result
    finally:
        cleanup_status = 'not_verified'
        try:
            removed = subprocess.run(['docker', 'rm', '-f', name], capture_output=True,
                                     timeout=10, check=False)
            if removed.returncode == 0:
                cleanup_status = 'confirmed_removed'
        except (OSError, subprocess.TimeoutExpired):
            pass  # Never replace the original outcome with a cleanup error.
        if result is not None:
            result['container_cleanup'] = cleanup_status


def verify(trial, arm, timeout=60, sandbox_image=None):
    if arm not in ('baseline', 'daeloryn', 'original'):
        raise ValueError('arm must be baseline, daeloryn or original')
    if type(timeout) is not int or timeout <= 0:
        raise ValueError('timeout must be a positive integer')
    trial = Path(trial).resolve(strict=True)
    raw_manifest = read_file(trial, 'evaluator/manifest.json')
    manifest = json.loads(raw_manifest)
    if (not isinstance(manifest, dict)
            or type(manifest.get('schema_version')) is not int
            or manifest.get('schema_version') != 1):
        raise ValueError('unsupported manifest')
    checks_valid(manifest.get('checks'))
    originals, tests = {}, {}
    for field, folder, target in (
            ('source_sha256', 'source', originals), ('suite_sha256', 'suite', tests)):
        hashes = manifest.get(field)
        if not isinstance(hashes, dict) or not hashes:
            raise ValueError('missing pinned file hashes')
        for name, expected in hashes.items():
            data = read_file(trial / 'evaluator' / folder, name)
            if digest(data) != expected:
                raise ValueError('evaluator snapshot changed: ' + name)
            target[name] = data
    editable = manifest.get('editable')
    if (not isinstance(editable, list) or not editable
            or not all(isinstance(name, str) for name in editable)
            or not set(editable) <= originals.keys()):
        raise ValueError('invalid editable file list')
    sources = dict(originals)
    if arm != 'original':
        # Copy only selected source, never candidate tests, build output or instructions.
        for name in originals:
            data = read_file(trial / arm, name)
            if name not in editable and data != originals[name]:
                raise ValueError('candidate changed frozen context: ' + name)
            sources[name] = data
    results = {}
    # Each gate gets fresh inputs; earlier gates cannot alter later gates' source.
    for name, command in manifest['checks'].items():
        with tempfile.TemporaryDirectory(prefix='daeloryn-check-') as check_tmp:
            check_work = Path(check_tmp)
            write_files(check_work, sources)
            write_files(check_work / '_suite', tests)
            result = (run_check(command, check_work, timeout) if sandbox_image is None
                      else container_check(sandbox_image, command, check_work, timeout))
            results[name] = {'command': command, **result}
    return {'schema_version': 1, 'arm': arm,
            'manifest_sha256': digest(raw_manifest),
            'source_sha256': {k: digest(v) for k, v in sources.items()},
            'suite_sha256': manifest['suite_sha256'],
            'changed_files': sorted(k for k in sources if sources[k] != originals[k]),
            'status': 'passed' if all(r['status'] == 'passed' for r in results.values()) else 'failed',
            'checks': results, 'execution_mode': 'host' if sandbox_image is None else 'container',
            'sandbox_image': sandbox_image, 'model_execution': 'not_run_by_this_tool'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    prep = subs.add_parser('prepare')
    for flag in ('project', 'suite', 'checks', 'output'):
        prep.add_argument('--' + flag, type=Path, required=True)
    for flag in ('file', 'editable', 'suite-file'):
        prep.add_argument('--' + flag, action='append', required=True)
    prep.add_argument('--agent', default='java-developer')
    run = subs.add_parser('verify')
    run.add_argument('--trial', type=Path, required=True)
    run.add_argument('--arm', choices=('original', 'baseline', 'daeloryn'), required=True)
    run.add_argument('--timeout', type=int, default=60)
    run.add_argument('--sandbox-image', help='opt-in reviewed digest-pinned Docker image')
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            result = prepare(args.project, args.file, args.editable, args.suite,
                             args.suite_file, json.loads(args.checks.read_text()),
                             args.output, args.agent)
        else:
            result = verify(args.trial, args.arm, args.timeout, args.sandbox_image)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'ERROR: {exc}\n')
    print(json.dumps(result, indent=2))
    if args.action == 'verify' and result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
