#!/usr/bin/env python3
"""Opt-in Copilot model discovery, conservative task routing and one-shot CLI launch.

No automatic paid retries, host setting changes, permission widening or claim that
model family implies measured quality. SDK discovery requires an installed CLI.
"""
import argparse
import asyncio
import json
import os
import signal
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from agents import catalog
from verify_implementation import digest

MODEL_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}')
RISK = re.compile(r'\b(auth\w*|security\w*|tenant\w*|payment\w*|refund\w*|transaction\w*|'
                  r'credential\w*|secret\w*|encrypt\w*|migration\w*|concurren\w*|'
                  r'rollback|retry|timeout|compensation|idempotenc\w*|'
                  r'oauth\w*|jwt\w*|csrf\w*|xss\w*|rbac\w*|'
                  r'access[-_ ]?control|personal[-_ ]?data|pii|gdpr|privacy|'
                  r'deadlock|race[-_ ]?condition|toctou|injection)\b', re.I)
DEFAULT_TIMEOUT_SECONDS = 900
MAX_TIMEOUT_SECONDS = 3600
KIND_FAMILIES = {'small': ('haiku', 'sonnet'), 'code': ('sonnet', 'opus'),
                 'review': ('sonnet', 'opus'), 'security': ('sonnet', 'opus'),
                 'architecture': ('sonnet', 'opus')}


def model_ids(models):
    if not isinstance(models, list) or not models:
        raise ValueError('nonempty host model catalog required')
    ids = []
    for item in models:
        if isinstance(item, str):
            identifier, enabled = item, True
        elif isinstance(item, dict):
            identifier = item.get('id')
            enabled = item.get('enabled', True) is True and item.get('available', True) is True
        else:
            identifier = getattr(item, 'id', None)
            enabled = getattr(item, 'enabled', True) is True and getattr(item, 'available', True) is True
        if not isinstance(identifier, str) or not MODEL_ID.fullmatch(identifier):
            raise ValueError('invalid model ID in catalog')
        policy = item.get('policy') if isinstance(item, dict) else getattr(item, 'policy', None)
        if policy is not None:
            state = policy.get('state') if isinstance(policy, dict) else getattr(policy, 'state', None)
            enabled = enabled and state == 'enabled'
        if enabled and identifier not in ids:
            ids.append(identifier)
    if not ids:
        raise ValueError('no enabled catalog models')
    return ids


def select(models, task, *, kind='code', previous_failure=False, allowed=None, agent=None):
    if kind not in ('auto', *KIND_FAMILIES) or not isinstance(task, str) or not task.strip():
        raise ValueError('explicit task and supported work kind required')
    # Every currently defined Daeloryn specialist is an engineering role; even a
    # summary-style prompt requires the engineering tier when one is invoked.
    if agent is not None and (not isinstance(agent, str)
                              or agent not in {meta['name'] for meta, _ in catalog()}):
        raise ValueError('unknown Daeloryn agent')
    available = model_ids(models)
    if allowed is not None:
        allowed_ids = set(model_ids(allowed))
        available = [identifier for identifier in available if identifier in allowed_ids]
    risk = bool(RISK.search(task)) or any(word in task.casefold() for word in
           ('πληρωμ', 'ασφάλ', 'ασφαλ', 'χρέω', 'χρεω', 'επιστροφ', 'κρυπτο', 'ταυτόχρον', 'συναλλαγ'))
    classified = kind
    if kind == 'auto':
        lightweight = re.search(r'(summari[sz]e|translate|rephrase|proofread|μετάφρα|μεταφρα|περίληψ|περιληψ)', task, re.I)
        engineering = re.search(r'(code|java|python|typescript|sql|implement|fix|refactor|review|κώδικ|κωδικ|διορθ)', task, re.I)
        classified = 'small' if lightweight and not engineering and not risk else 'code'
    tier = 'code' if classified == 'small' and (risk or previous_failure or agent is not None) else classified
    families = ('opus', 'sonnet') if previous_failure else KIND_FAMILIES[tier]
    chosen = None
    for family in families:
        chosen = next((identifier for identifier in available
                       if re.search(r'(?:^|[-_/])' + family + r'(?:[-_.]|$)', identifier, re.I)), None)
        if chosen:
            break
    if chosen is None:
        raise ValueError('no policy-approved model available; do not silently downgrade')
    reasons = [f'work kind: {kind}', f'policy tier: {tier}']
    if risk:
        reasons.append('task text contains risk indicators; small-model routing excluded')
    if previous_failure:
        reasons.append('previous failure: prefer configured escalation family, no automatic retry')
    if agent is not None:
        reasons.append('engineering specialist selected: small-model routing excluded')
    return {'requested_model': chosen, 'requested_kind': kind, 'effective_kind': tier,
            'selected_agent': agent,
            'risk_detected': risk, 'previous_failure': bool(previous_failure),
            'reason': reasons, 'task_sha256': digest(task.encode()),
            'catalog_sha256': digest(json.dumps(available, separators=(',', ':')).encode()),
            'actual_model': 'not_verified_by_router', 'execution': 'not_run',
            'cost_estimate': None}


async def discover_copilot(executable):
    # Explicit installed runtime avoids silently downloading SDK-managed executables.
    try:
        from copilot import CopilotClient, RuntimeConnection
    except ImportError as error:
        raise RuntimeError('optional github-copilot-sdk with RuntimeConnection required') from error
    client = CopilotClient(connection=RuntimeConnection.for_stdio(path=executable))
    try:
        await asyncio.wait_for(client.start(), 30)
        models = await asyncio.wait_for(client.list_models(), 30)
        return model_ids(models)
    finally:
        await asyncio.wait_for(client.stop(), 10)


def _terminate_session(process):
    """Best-effort POSIX process-group termination; not proof of remote cancellation."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        # A child may still be running after the CLI leader has exited.
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def launch(plan, task, project, agent, *, execute=False, executable=None,
           timeout_seconds=DEFAULT_TIMEOUT_SECONDS):
    if not execute:
        raise ValueError('explicit --execute required for a Copilot task')
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS):
        raise ValueError('session timeout must be 1..3600 whole seconds')
    if os.name != 'posix':
        raise RuntimeError('bounded Copilot sessions require a POSIX host')
    project = Path(project).resolve(strict=True)
    if not project.is_dir() or agent not in {meta['name'] for meta, _ in catalog()}:
        raise ValueError('explicit project and known Daeloryn agent required')
    if plan.get('selected_agent') != agent:
        raise ValueError('agent differs from the model-routing decision')
    # Do not ask the host to resolve a missing or redirected profile silently.
    github_dir = project / '.github'
    profiles_dir = github_dir / 'agents'
    profile = profiles_dir / (agent + '.agent.md')
    if (github_dir.is_symlink() or profiles_dir.is_symlink() or profile.is_symlink()
            or not profile.is_file()):
        raise ValueError('installed non-symlink Copilot agent profile required')
    if not isinstance(plan.get('requested_model'), str) or not MODEL_ID.fullmatch(plan['requested_model']):
        raise ValueError('invalid requested model')
    if plan.get('task_sha256') != digest(task.encode()):
        raise ValueError('task changed after routing')
    executable = executable or shutil.which('copilot')
    if executable is None:
        raise RuntimeError('installed Copilot CLI required')
    # A distinct process group enables best-effort cleanup of local descendants.
    # The host may still have remote side effects; never automatically retry.
    process = subprocess.Popen([executable, '--model=' + plan['requested_model'],
                                '--agent=' + agent, '--prompt=' + task],
                               cwd=project, start_new_session=True)
    try:
        exit_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_session(process)
        return {**plan, 'execution': 'timed_out', 'exit_code': None,
                'outcome': 'unknown', 'local_termination': 'best_effort',
                'timeout_seconds': timeout_seconds}
    except BaseException:
        _terminate_session(process)
        raise
    return {**plan, 'execution': 'completed' if exit_code == 0 else 'failed',
            'exit_code': exit_code, 'outcome': 'host_exit_code_only',
            'timeout_seconds': timeout_seconds}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--discover-copilot', action='store_true')
    source.add_argument('--models-json', type=Path, help='offline array of available model IDs/records')
    parser.add_argument('--kind', choices=('auto', *KIND_FAMILIES), default='auto')
    parser.add_argument('--prompt-file', type=Path, required=True)
    parser.add_argument('--previous-failure', action='store_true')
    parser.add_argument('--allowed-model', action='append')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--project', type=Path); parser.add_argument('--agent')
    parser.add_argument('--timeout-seconds', type=int, default=DEFAULT_TIMEOUT_SECONDS,
                        help='POSIX session deadline (1..3600); timeout is not proof of cancellation')
    args = parser.parse_args()
    try:
        task = args.prompt_file.read_text(encoding='utf-8')
        if len(task.encode()) > 196608:
            raise ValueError('prompt exceeds router byte budget')
        if args.execute and (not args.discover_copilot or args.project is None or args.agent is None):
            raise ValueError('execution requires live discovery, project and agent')
        if args.discover_copilot:
            executable = shutil.which('copilot')
            if executable is None:
                raise RuntimeError('installed Copilot CLI required; no automatic installation')
            models = asyncio.run(discover_copilot(executable))
            origin = 'live_copilot_runtime'
        else:
            executable = None
            models = json.loads(args.models_json.read_text())
            origin = 'operator_supplied_offline_catalog'
        plan = select(models, task, kind=args.kind, previous_failure=args.previous_failure,
                      allowed=args.allowed_model, agent=args.agent)
        plan.update({'catalog_origin': origin, 'selected_at_ns': time.time_ns()})
        print(json.dumps(plan, indent=2), flush=True)
        if args.execute:
            result = launch(plan, task, args.project, args.agent, execute=True,
                            executable=executable, timeout_seconds=args.timeout_seconds)
            print(json.dumps(result, indent=2))
            return 0 if result['execution'] == 'completed' else 1
    except (ValueError, OSError, RuntimeError, asyncio.TimeoutError):
        parser.exit(2, 'ERROR: routing/discovery failed; no automatic fallback or task retry\n')


if __name__ == '__main__':
    sys.exit(main())
