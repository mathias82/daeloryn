"""Ensure recovery development assertions catch the original defects and retain a control."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
result = subprocess.run([sys.executable, str(root / 'evaluator/run_recovery.py'),
                         '--project', str(root)], capture_output=True, text=True, timeout=120)
print(result.stdout, end='')
print(result.stderr, end='', file=sys.stderr)
expected = {
    'no-recharge-after-failed-refund': 'FAIL',
    'no-recharge-after-accepted-but-timed-out-charge': 'FAIL',
    'same-total-different-SKU-rejected-by-new-service': 'FAIL',
    'identical-replay-by-new-service-control': 'PASS',
    'known-rejection-rolls-back-control': 'FAIL',
}
observed = {}
for line in result.stdout.splitlines():
    fields = line.split()
    if fields and fields[0] in ('PASS', 'FAIL'):
        if len(fields) < 2 or fields[1] in observed:
            raise SystemExit('duplicate/missing recovery assertion')
        observed[fields[1]] = fields[0]
if result.returncode != 1 or observed != expected or 'SUMMARY total=5 passed=1 failed=4' not in result.stdout:
    raise SystemExit('unexpected original recovery baseline or setup failure')
