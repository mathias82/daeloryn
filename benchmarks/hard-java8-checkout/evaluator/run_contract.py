#!/usr/bin/env python3
"""Compile selected Java production sources and evaluator suite, then run assertions.

Run in a disposable reconstruction or explicitly pass --project. Executes candidate
code with caller permissions; no isolation or provider invocation is implied.
"""
import argparse
from pathlib import Path
import shutil
import re
import sys
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path.cwd())
    args = parser.parse_args()
    project = args.project.resolve(strict=True)
    sources = sorted((project / 'src/main/java').rglob('*.java'))
    if not sources:
        parser.exit(2, 'ERROR: no Java production sources\n')
    if any(path.is_symlink() or path.resolve() != path.absolute() for path in sources):
        parser.exit(2, 'ERROR: symlink sources rejected\n')
    java = shutil.which('java')
    javac = shutil.which('javac')
    if not java:
        parser.exit(2, 'ERROR: Java toolchain unavailable\n')
    compiler = [javac] if javac else [java, '-m', 'jdk.compiler/com.sun.tools.javac.Main']
    suite = Path(__file__).with_name('CheckoutContractSuite.java')
    with tempfile.TemporaryDirectory(prefix='checkout-contract-') as tmp:
        # --release checks both Java 8 language and platform API compatibility.
        compilation = subprocess.run(compiler + ['--release', '8', '-d', tmp]
                                     + [str(path) for path in sources] + [str(suite)],
                                     timeout=60, check=False)
        if compilation.returncode:
            raise SystemExit(2)  # Setup/compile failure is not a failed behavior assertion.
        result = subprocess.run([java, '-cp', tmp,
                                 'dev.daeloryn.benchmark.CheckoutContractSuite'],
                                timeout=60, check=False, capture_output=True, text=True)
        print(result.stdout, end='')
        print(result.stderr, end='', file=sys.stderr)
        summaries = re.findall(r'^SUMMARY total=(\d+) passed=(\d+) failed=(\d+)$',
                               result.stdout, flags=re.MULTILINE)
        cases = re.findall(r'^(PASS|FAIL) (\S+)(?:[ \t][^\r\n]*)?$', result.stdout, flags=re.MULTILINE)
        if (len(summaries) != 1 or len(cases) != 23 or len({name for _, name in cases}) != 23):
            parser.exit(2, 'ERROR: missing, duplicate or incomplete independent assertions\n')
        total, passed, failed = map(int, summaries[0])
        if (total != 23 or passed + failed != total
                or passed != sum(status == 'PASS' for status, _ in cases)
                or failed != sum(status == 'FAIL' for status, _ in cases)
                or result.returncode != (1 if failed else 0)):
            parser.exit(2, 'ERROR: inconsistent assertion summary or process outcome\n')
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
