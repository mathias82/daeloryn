"""Confirm teaching-fixture defects and safe controls remain distinguishable."""
from pathlib import Path
import subprocess
import sys

suite = Path(__file__).parent
project = suite.parent
result = subprocess.run([sys.executable, str(suite / 'run_contract.py'), '--project', str(project)],
                        capture_output=True, text=True, timeout=120)
print(result.stdout, end='')
print(result.stderr, end='', file=sys.stderr)
if result.returncode != 1:
    raise SystemExit('expected behavior-assertion failures, not compile/setup success or error')
controls = ('valid-order', 'past-expiry-control', 'sequential-idempotency-control',
            'stock-safe-positive-control', 'immutable-request-control')
failures = ('expiry-equality', 'zero-quantity', 'negative-quantity', 'excess-quantity',
            'empty-lines', 'blank-sku', 'invalid-price-0', 'invalid-price--1',
            'multiplication-overflow', 'addition-overflow', 'later-line-stock-rollback',
            'payment-rejection-releases-stock', 'save-failure-compensation',
            'failed-refund-is-visible', 'different-details-same-id',
            'tenant-independent-ids', 'receipt-isolation')
lines = result.stdout.splitlines()
if any('PASS ' + name not in lines for name in controls):
    raise SystemExit('a safe negative control regressed')
if any(not any(line.startswith('FAIL ' + name + ' ') for line in lines) for name in failures):
    raise SystemExit('an expected source-supported defect was not detected')
# Concurrent duplicates may occasionally pass depending on the schedule.
print('Development baseline and safe controls verified; not an AI quality score.')
