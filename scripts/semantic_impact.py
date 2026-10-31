#!/usr/bin/env python3
"""Compiler-resolved Java source impact, conservatively expanded at file granularity.

Does not execute project code or annotation processors. Reflection, DI wiring,
generated sources, runtime configuration and external callers require other checks.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from agents import ROOT
from verify_implementation import digest, read_file, write_files


def index(root, paths, release, classpath=()):
    root = Path(root).resolve(strict=True)
    if not isinstance(release, str) or not release.isdigit():
        raise ValueError('explicit numeric Java release required')
    paths = sorted(set(paths))
    if not paths or any(not name.endswith('.java') for name in paths):
        raise ValueError('explicit Java source files required')
    sources = {name: read_file(root, name) for name in paths}
    pinned_classpath = classpath_hashes(classpath)
    java = shutil.which('java')
    if java is None:
        raise ValueError('Java JDK toolchain unavailable')
    # Compile only the trusted helper; project processors/plugins are never loaded.
    version = subprocess.run([java, '--version'],capture_output=True,text=True,timeout=10)
    if version.returncode:
        raise ValueError('JDK 17+ runtime required for compiler analysis')
    java_version = version.stdout.splitlines()[0] if version.stdout else 'unknown'
    helper = ROOT / 'scripts/java/ImpactIndex.java'
    with tempfile.TemporaryDirectory(prefix='semantic-index-') as tmp:
        snapshot = (Path(tmp) / 'source').resolve()
        write_files(snapshot,sources)
        compiler = [shutil.which('javac')] if shutil.which('javac') else [java, '-m', 'jdk.compiler/com.sun.tools.javac.Main']
        build = subprocess.run(compiler + ['-proc:none', '-d', tmp, str(helper)],
                               capture_output=True, text=True, timeout=60)
        if build.returncode:
            raise ValueError('compiler helper unavailable; use a full JDK 17+ toolchain')
        # Empty explicit classpath avoids implicitly loading cwd build output.
        cp = os.pathsep.join(str(Path(p).resolve(strict=True)) for p in classpath) or str(Path(tmp) / 'empty')
        result = subprocess.run([java, '--add-modules', 'jdk.compiler', '-cp', tmp,
            'dev.daeloryn.analysis.ImpactIndex', str(snapshot), release, cp]
            + [str(snapshot / name) for name in paths], capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise ValueError('compiler analysis failed; inspect toolchain/source configuration')
        data = json.loads(result.stdout)
    # Detect ordinary source changes while javac was reading. Not a hostile-writer lock.
    if any(read_file(root, name) != content for name, content in sources.items()):
        raise ValueError('source changed during analysis; rerun on a pinned snapshot')
    if classpath_hashes(classpath) != pinned_classpath:
        raise ValueError('classpath changed during analysis; use a pinned snapshot')
    return {'schema_version': 1, 'kind': 'java-semantic-index', 'release': release,
            'analysis_status': 'incomplete' if data['errors'] else 'complete',
            'source_sha256': {name: digest(content) for name, content in sources.items()},
            'classpath_sha256': pinned_classpath, 'java_version': java_version, **data}


def classpath_hashes(paths):
    hashes = {}
    for item in paths:
        path = Path(item).resolve(strict=True)
        if path.is_file():
            hashes[str(path)] = digest(path.read_bytes())
        elif path.is_dir():
            entries = {}
            for file in sorted(path.rglob('*.class')):
                entries[file.relative_to(path).as_posix()] = digest(read_file(path, file.relative_to(path).as_posix()))
            hashes[str(path)] = digest(json.dumps(entries, sort_keys=True).encode())
        else:
            raise ValueError('classpath entry must be a regular JAR or class directory')
    return hashes


def impact(after, changed, before=None):
    indexes = [after] + ([before] if before is not None else [])
    reverse = {}
    known = set()
    witnesses = []
    for item in indexes:
        if (not isinstance(item, dict) or item.get('kind') != 'java-semantic-index'
                or type(item.get('schema_version')) is not int or item['schema_version'] != 1
                or item.get('analysis_status') not in ('complete', 'incomplete')
                or not isinstance(item.get('source_sha256'), dict)
                or not all(isinstance(name,str) and isinstance(h,str) and len(h)==64
                           and all(c in '0123456789abcdef' for c in h)
                           for name,h in item['source_sha256'].items())
                or not isinstance(item.get('definitions'),list) or not isinstance(item.get('references'),list)):
            raise ValueError('unsupported semantic index')
        known.update(item['source_sha256'])
        definitions = {}
        for entry in item.get('definitions', []):
            if (not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) and entry[k] for k in ('symbol', 'path'))
                    or entry['path'] not in item['source_sha256']
                    or type(entry.get('line')) is not int or entry['line'] < 1):
                raise ValueError('invalid symbol definition')
            definitions[entry['symbol']] = entry['path']
        for ref in item.get('references', []):
            if (not isinstance(ref, dict) or not all(isinstance(ref.get(k), str) and ref[k] for k in ('target', 'path'))
                    or ref['path'] not in item['source_sha256']
                    or type(ref.get('line')) is not int or ref['line'] < 1):
                raise ValueError('invalid semantic reference')
            target_path = definitions.get(ref['target'])
            if target_path and target_path != ref['path']:
                reverse.setdefault(target_path, set()).add(ref['path'])
                witnesses.append({**ref, 'target_path': target_path})
    if not isinstance(changed, (list, tuple)) or not changed or any(not isinstance(name,str) or name not in known for name in changed):
        raise ValueError('changed file must exist in the before or after source index')
    affected = set(changed)
    pending = list(changed)
    while pending:
        for caller in reverse.get(pending.pop(), ()):
            if caller not in affected:
                affected.add(caller); pending.append(caller)
    incomplete = any(item.get('analysis_status') != 'complete' for item in indexes)
    return {'schema_version': 1, 'analysis_status': 'incomplete' if incomplete else 'complete',
            'changed': sorted(set(changed)), 'potentially_affected': sorted(affected),
            'evidence': [ref for ref in witnesses if ref['target_path'] in affected],
            'source_sha256': after['source_sha256'],
            'limitations': 'Conservative file-level impact from resolved source symbols, not runtime reachability. '
                          'Does not prove absence of reflection/DI/configuration/external consumer impacts.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--source', action='append')
    selection.add_argument('--source-root', help='explicit project-relative source tree')
    parser.add_argument('--release', required=True)
    parser.add_argument('--classpath', action='append', default=[])
    parser.add_argument('--changed', action='append', default=[])
    parser.add_argument('--before-index', type=Path)
    args = parser.parse_args()
    try:
        paths = args.source
        if args.source_root is not None:
            root = args.root.resolve(strict=True)
            relative = Path(args.source_root)
            directory = root / relative
            if relative.is_absolute() or '..' in relative.parts or directory.resolve() != directory.absolute() or not directory.is_dir():
                raise ValueError('source-root must be a real project-relative directory')
            paths = [p.relative_to(root).as_posix() for p in sorted(directory.rglob('*.java'))]
        data = index(args.root, paths, args.release, args.classpath)
        result = (impact(data, args.changed, json.loads(args.before_index.read_text()) if args.before_index else None)
                  if args.changed else data)
    except (ValueError, OSError, subprocess.SubprocessError):
        parser.exit(2, 'ERROR: invalid source/index or unavailable compiler toolchain\n')
    print(json.dumps(result, indent=2))
    if result['analysis_status'] != 'complete':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
