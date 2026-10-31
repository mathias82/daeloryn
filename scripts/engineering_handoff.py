#!/usr/bin/env python3
"""Pin a source-audited review and validate a complete implementation handoff.

Hashes and locators establish provenance, not semantic truth or test execution.
"""
import argparse
import copy
import json
from pathlib import Path

from audit_review_evidence import audit
from verify_implementation import digest, read_file


def seal(root, report, context=()):
    root = Path(root).resolve(strict=True)
    checked = audit(root, report)
    if checked['result'] != 'PASS':
        raise ValueError('review failed source evidence audit: ' + json.dumps(checked['issues']))
    pinned = copy.deepcopy(report)
    pinned['source_sha256'] = checked['source_sha256']
    audit_result = audit(root, pinned, require_source_hashes=True)
    if audit_result['result'] != 'PASS':
        raise ValueError('review failed pinned evidence audit')
    context_hashes = {name: digest(read_file(root, name)) for name in context}
    return {'schema_version': 1, 'kind': 'engineering-review-handoff',
            'review': pinned, 'context_sha256': context_hashes}


def fingerprint(handoff):
    return digest(json.dumps(handoff, sort_keys=True, separators=(',', ':')).encode())


def current(root, handoff):
    if (not isinstance(handoff, dict) or type(handoff.get('schema_version')) is not int
            or handoff['schema_version'] != 1 or handoff.get('kind') != 'engineering-review-handoff'):
        raise ValueError('unsupported handoff')
    context = handoff.get('context_sha256')
    if not isinstance(context, dict):
        raise ValueError('context hashes required')
    for name, expected in context.items():
        if digest(read_file(Path(root).resolve(strict=True), name)) != expected:
            raise ValueError('stale review context; re-review required: ' + name)
    checked = audit(root, handoff.get('review'), require_source_hashes=True)
    if checked['result'] != 'PASS':
        raise ValueError('stale or invalid review: ' + json.dumps(checked['issues']))
    return fingerprint(handoff)


def validate_fix(root, handoff, submission, editable):
    expected = current(root, handoff)
    if not isinstance(submission, dict) or submission.get('review_sha256') != expected:
        raise ValueError('fix must identify its exact review_sha256')
    resolutions = submission.get('resolutions')
    if not isinstance(resolutions, list):
        raise ValueError('resolutions must be a list')
    required = {f['id'] for f in handoff['review']['findings'] if f['disposition'] == 'ACTIONABLE'}
    seen = set()
    for entry in resolutions:
        if not isinstance(entry, dict) or not isinstance(entry.get('finding'), str):
            raise ValueError('invalid resolution')
        fid = entry['finding']
        if fid not in required or fid in seen:
            raise ValueError('unknown or duplicate finding resolution')
        seen.add(fid)
        if entry.get('status') not in ('fixed', 'rejected', 'unresolved'):
            raise ValueError('invalid resolution status')
        if not isinstance(entry.get('rationale'), str) or not entry['rationale'].strip():
            raise ValueError('each resolution needs evidence/rationale')
        tests = entry.get('regression_assertions')
        if (not isinstance(tests, list) or not tests
                or not all(isinstance(test, str) and test.strip() for test in tests)):
            raise ValueError('each resolution needs regression assertions or an explicit unverified limitation')
    if seen != required:
        raise ValueError('missing independent finding resolutions')
    edits = submission.get('files')
    if not isinstance(edits, dict):
        raise ValueError('files must map declared editable paths to UTF-8 content')
    allowed = set(editable)
    for name, text in edits.items():
        if name not in allowed or not isinstance(text, str):
            raise ValueError('undeclared edit or non-text content')
        read_file(Path(root).resolve(strict=True), name)
        if len(text.encode('utf-8')) > 1024 * 1024:
            raise ValueError('oversized replacement file')
    return {'review_sha256': expected, 'resolution_count': len(seen),
            'changed_files': sorted(edits),
            'ready_for_verification': all(r['status'] == 'fixed' for r in resolutions),
            'semantic_correctness': 'not_verified', 'tests_executed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    subs = parser.add_subparsers(dest='action', required=True)
    p = subs.add_parser('seal'); p.add_argument('--report', type=Path, required=True)
    p.add_argument('--context', action='append', default=[])
    p = subs.add_parser('check'); p.add_argument('--handoff', type=Path, required=True)
    p = subs.add_parser('check-fix'); p.add_argument('--handoff', type=Path, required=True)
    p.add_argument('--submission', type=Path, required=True)
    p.add_argument('--editable', action='append', required=True)
    args = parser.parse_args()
    try:
        if args.action == 'seal':
            result = seal(args.root, json.loads(args.report.read_text()), args.context)
        else:
            handoff = json.loads(args.handoff.read_text())
            result = ({'review_sha256': current(args.root, handoff)} if args.action == 'check'
                      else validate_fix(args.root, handoff,
                                        json.loads(args.submission.read_text()), args.editable))
    except (ValueError, OSError) as error:
        parser.exit(2, 'ERROR: ' + str(error) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
