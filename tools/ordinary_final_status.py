"""One status block for an authorized ordinary final run. Read-only; launches nothing.

Reads the controller's receipts under the bundle and, unless --no-provider is given,
asks the provider for the instance's own lifecycle state through the allowlisted
adapter. Remote-work liveness and controller-connection health are reported as two
separate lines, from the controller's per-poll status file. Values that are not
measurable are reported as unknown.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'scripts')]
from ordinary_final_run import read

CREDENTIAL = Path('C:/Users/secki/local/api_keys/config.py')
PHASE_DEADLINES = dict(ssh_ready=20, python_gate=30, fresh_directory=30, support_transfer=300, assets_transfer=10800,
                       archive_integrity=300, extract_payload=900, create_environment=180, install_pinned_wheels=1800,
                       dependency_closure=120, gpu_metadata=30, watchdog_receipt_transfer=30, stop_workload=30,
                       final_gpu_state=30, pack_evidence=180, evidence_hash=60, evidence_download=600)


def load(base, name):
    try:
        return read(base / name)
    except (OSError, ValueError):
        return None


def minutes(seconds):
    return 'unknown' if seconds is None else '%.1f min' % (seconds / 60)


def main(bundle, stage, use_provider):
    base = Path(bundle)
    now = time.time()
    launch = load(base, 'launch.json')
    current = load(base, 'CURRENT_PHASE.json') or {}
    status = load(base, 'phase_status.json')
    manifest = load(base, 'execution_manifest.json') or {}
    rate = (launch or {}).get('hourly_rate')
    phase = current.get('phase', 'not launched')
    lines = ['STATUS ' + stage + ' | phase: ' + phase]
    if launch:
        terminated = load(base, 'TERMINATION_VERIFIED.json')
        end = terminated['confirmed_epoch'] if terminated and terminated.get('confirmed_epoch') else now
        since_launch = end - launch['epoch']
        lines.append('elapsed since launch: ' + minutes(since_launch) + (' (frozen at provider-confirmed termination)' if terminated else ''))
        in_phase = now - current['epoch'] if current.get('epoch') else None
        if status and status.get('phase') == phase and status.get('deadline_epoch'):
            deadline = status['deadline_epoch'] - status['started_epoch']
        else:
            deadline = PHASE_DEADLINES.get(phase.rstrip('0123456789_'), None)
            if phase == 'ordinary_workload' and rate:
                deadline = launch['epoch'] + 7 / rate * 3600 - 840 - current['epoch']
        lines.append('elapsed in phase: ' + minutes(in_phase) + ' of deadline ' + (minutes(deadline) if deadline else 'unknown'))
        spend = since_launch * rate / 3600 if rate else None
        soft, hard = manifest.get('soft_budget_usd'), manifest.get('hard_ceiling_usd')
        lines.append('estimated spend: ' + ('$%.3f' % spend if spend is not None else 'unknown')
                     + ' | headroom to soft $%s: ' % soft + ('$%.3f' % (soft - spend) if spend is not None and soft else 'unknown')
                     + ' | to hard $%s: ' % hard + ('$%.3f' % (hard - spend) if spend is not None and hard else 'unknown'))
    else:
        lines.append('elapsed since launch: not launched | spend: $0.000')
    # Instance state as the provider reports it.
    state = 'unknown'
    if use_provider and launch:
        try:
            from lambda_experiment_provider import LambdaExperiment
            found = [x for x in LambdaExperiment(CREDENTIAL).request('instances')['data'] if x.get('instance_id') == launch['instance_id']]
            state = 'listed, ' + (found[0].get('status') or 'status not projected') if found else 'not in inventory (terminated or never listed)'
        except Exception as exc:
            state = 'unknown (provider query failed: ' + type(exc).__name__ + ')'
    elif not launch:
        state = 'no instance'
    lines.append('instance (provider): ' + state)
    # Watchdog.
    armed = load(base, 'WATCHDOG_ARMED.json')
    process = load(base, 'watchdog_process.json')
    alive = 'unknown'
    if process:
        try:
            out = subprocess.run(['tasklist', '/FI', 'PID eq %d' % process['pid']], capture_output=True, text=True, timeout=20).stdout
            alive = 'alive' if str(process['pid']) in out else 'exited'
        except Exception:
            alive = 'unknown'
    heartbeat = ('heartbeat %.0f s old' % (now - armed['heartbeat_epoch'])) if armed else 'no heartbeat file'
    lines.append('watchdog: ' + alive + ', ' + heartbeat)
    # Remote work versus connection: two lines, never one.
    if status and status.get('phase') == phase:
        age = now - status['last_poll_epoch'] if status.get('last_poll_epoch') else None
        lines.append('remote work: ' + str(status.get('remote_work')) + ' (remote pid ' + str(status.get('remote_pid') or 'unknown')
                     + ', exit code ' + str(status.get('exit_code')) + ')')
        lines.append('controller connection: ' + str(status.get('connection')) + ' | polls ' + str(status.get('polls'))
                     + ', unreachable ' + str(status.get('unreachable_polls')) + ', last poll ' + (('%.0f s ago' % age) if age is not None else 'unknown'))
    else:
        lines.append('remote work: unknown (no detached phase in progress)')
        lines.append('controller connection: unknown (no detached phase in progress)')
    if phase == 'ordinary_workload':
        progress = base / 'workload_progress.log'
        if progress.exists():
            tail = progress.read_text(encoding='utf8', errors='replace').splitlines()[-6:]
            lines.append('workload progress (last lines):')
            lines += ['  ' + t[:160] for t in tail]
        else:
            lines.append('workload progress: none received yet')
    for name in ('controller_failure.json', 'SECURITY_STOP.json', 'SOFT_BUDGET_REACHED.json', 'collection_failure.json'):
        if (base / name).exists():
            lines.append('EVENT ' + name + ': ' + (base / name).read_text(encoding='utf8')[:200].replace('\n', ' '))
    print('\n'.join(lines))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--stage', default='C')
    parser.add_argument('--no-provider', action='store_true')
    args = parser.parse_args()
    main(args.bundle, args.stage, not args.no_provider)
