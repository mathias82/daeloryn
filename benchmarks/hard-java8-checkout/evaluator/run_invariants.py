#!/usr/bin/env python3
"""Adapt the trusted Java contract suite to the targeted mutation report protocol."""
import json
from pathlib import Path
import re
import subprocess
import sys

runner = Path(__file__).with_name('run_contract.py')
result = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True, timeout=120)
cases = re.findall(r'^(PASS|FAIL) (\S+)(?:[ \t][^\r\n]*)?$', result.stdout, flags=re.MULTILINE)
if result.returncode not in (0, 1) or len(cases) != 23 or len({name for _, name in cases}) != 23:
    print(json.dumps({'cases': [], 'setup': 'failed_or_incomplete'}))
    raise SystemExit(2)
print(json.dumps({'cases': [{'id': name, 'status': 'passed' if status == 'PASS' else 'failed',
                             'assertions': 1} for status, name in cases]}))
raise SystemExit(result.returncode)
