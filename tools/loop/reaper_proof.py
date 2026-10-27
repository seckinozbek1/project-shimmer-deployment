"""Proof, on a mocked provider, that the reaper ends a loop instance whose controller died.

Run: python tools/loop/reaper_proof.py <empty working folder>

Steps, each checked:
1. A fake controller starts as a detached process. It writes the instance name and
   deadline to the ledger before "launching", launches a ``shimmer-loop-`` instance on the
   mock provider, and asks Windows to stay awake (SetThreadExecutionState).
2. The controller process is killed.
3. The reaper, run before the deadline, leaves the instance alone.
4. The reaper, run after the deadline, terminates it and appends exactly one ledger line.
5. An instance without the loop prefix is never touched.
6. Once spend reaches the hard stop, a loop instance inside its deadline is terminated.
7. A provider error that carries a key-shaped string never reaches the reaper's output.
"""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REAPER = HERE / 'instance_reaper.py'
FAKE_KEY = 'PROOFONLY0a1b2c3d4e5f6a7b8c9d0e1f'


def iso(moment):
    return moment.isoformat()


def fake_controller(work):
    """Body of the detached fake controller."""
    sys.path.insert(0, str(HERE))
    import keep_awake
    work = Path(work)
    now = datetime.now(timezone.utc)
    name = 'shimmer-loop-proof-0001'
    deadline = now + timedelta(minutes=10)
    ledger = work / 'ledger.jsonl'
    with open(ledger, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps({'event': 'launch_intent', 'time_utc': iso(now), 'instance_name': name,
                                 'deadline_utc': iso(deadline), 'price_usd_per_hour': 1.29,
                                 'launch_requested_utc': iso(now), 'purpose': 'reaper proof'}) + '\n')
    state = json.loads((work / 'mock_state.json').read_text(encoding='utf-8'))
    instance_id = 'a' * 32
    state['instances'].append({'instance_id': instance_id, 'name': name, 'status': 'active',
                               'type': 'gpu_1x_a10', 'region': 'us-east-1'})
    (work / 'mock_state.json').write_text(json.dumps(state, indent=1), encoding='utf-8')
    with open(ledger, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps({'event': 'launch', 'time_utc': iso(now), 'instance_name': name,
                                 'instance_id': instance_id, 'deadline_utc': iso(deadline),
                                 'price_usd_per_hour': 1.29, 'launch_requested_utc': iso(now)}) + '\n')
    held = keep_awake.hold()
    (work / 'controller.json').write_text(json.dumps({'pid': os.getpid(), 'keep_awake_held': held,
                                                      'deadline_utc': iso(deadline)}), encoding='utf-8')
    while True:
        time.sleep(5)


def run_reaper(work, now, ledger=None):
    args = [sys.executable, str(REAPER), '--mock-state', str(work / 'mock_state.json'),
            '--ledger', str(ledger or work / 'ledger.jsonl'), '--append-to', str(ledger or work / 'ledger.jsonl'),
            '--status', str(work / 'reaper_status.json'), '--now', iso(now)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return result.returncode, result.stdout + result.stderr


def alive(pid):
    out = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True)
    return str(pid) in out.stdout


def main(work):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise SystemExit('working folder must be empty')
    results = {}
    (work / 'mock_state.json').write_text(json.dumps({'instances': [
        {'instance_id': 'b' * 32, 'name': 'someone-else-instance', 'status': 'active',
         'type': 'gpu_1x_a10', 'region': 'us-east-1'}]}, indent=1), encoding='utf-8')
    (work / 'ledger.jsonl').write_text('', encoding='utf-8')

    flags = 0x00000008 | 0x00000200 if os.name == 'nt' else 0  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--fake-controller', str(work)],
                            creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL, close_fds=True)
    for _ in range(60):
        if (work / 'controller.json').exists():
            break
        time.sleep(0.5)
    controller = json.loads((work / 'controller.json').read_text(encoding='utf-8'))
    results['1_detached_controller_started'] = controller['pid'] == proc.pid
    results['1_keep_awake_held'] = controller['keep_awake_held']
    ledger_rows = [json.loads(l) for l in (work / 'ledger.jsonl').read_text(encoding='utf-8').splitlines() if l]
    results['1_intent_written_before_launch'] = ledger_rows[0]['event'] == 'launch_intent'

    os.kill(proc.pid, signal.SIGTERM)
    time.sleep(1.5)
    results['2_controller_killed'] = not alive(proc.pid)

    deadline = datetime.fromisoformat(controller['deadline_utc'])
    code, out = run_reaper(work, deadline - timedelta(seconds=30))
    state = json.loads((work / 'mock_state.json').read_text(encoding='utf-8'))
    loop_item = [i for i in state['instances'] if i['name'].startswith('shimmer-loop-')][0]
    results['3_before_deadline_left_alone'] = code == 0 and loop_item['status'] == 'active'

    before = len((work / 'ledger.jsonl').read_text(encoding='utf-8').splitlines())
    code, out = run_reaper(work, deadline + timedelta(seconds=1))
    state = json.loads((work / 'mock_state.json').read_text(encoding='utf-8'))
    loop_item = [i for i in state['instances'] if i['name'].startswith('shimmer-loop-')][0]
    other = [i for i in state['instances'] if not i['name'].startswith('shimmer-loop-')][0]
    lines = (work / 'ledger.jsonl').read_text(encoding='utf-8').splitlines()
    new = [json.loads(l) for l in lines[before:]]
    results['4_terminated_after_deadline'] = code == 0 and loop_item['status'] == 'terminated'
    results['4_exactly_one_ledger_line'] = (len(new) == 1 and new[0]['event'] == 'termination'
                                            and new[0]['reason'] == 'deadline_passed')
    results['5_unprefixed_untouched'] = other['status'] == 'active'

    hard = work / 'hard'
    hard.mkdir()
    now = datetime.now(timezone.utc)
    (hard / 'mock_state.json').write_text(json.dumps({'instances': [
        {'instance_id': 'c' * 32, 'name': 'shimmer-loop-proof-0002', 'status': 'active'}]}), encoding='utf-8')
    (hard / 'ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in [
        {'event': 'launch', 'instance_id': 'd' * 32, 'instance_name': 'shimmer-loop-old',
         'price_usd_per_hour': 1.29, 'launch_requested_utc': iso(now - timedelta(hours=40))},
        {'event': 'termination', 'instance_id': 'd' * 32, 'instance_name': 'shimmer-loop-old', 'actual_cost': 49.5},
        {'event': 'launch', 'instance_id': 'c' * 32, 'instance_name': 'shimmer-loop-proof-0002',
         'price_usd_per_hour': 1.29, 'launch_requested_utc': iso(now), 'deadline_utc': iso(now + timedelta(hours=1))},
    ]) + '\n', encoding='utf-8')
    code, out = run_reaper(hard, now)
    state = json.loads((hard / 'mock_state.json').read_text(encoding='utf-8'))
    results['6_hard_stop_terminates'] = state['instances'][0]['status'] == 'terminated' and 'hard_stop_spend_reached' in out

    leak = work / 'leak'
    leak.mkdir()
    (leak / 'mock_state.json').write_text(json.dumps({'instances': [], 'raise_with': FAKE_KEY}), encoding='utf-8')
    (leak / 'ledger.jsonl').write_text('', encoding='utf-8')
    code, out = run_reaper(leak, now)
    status_text = (leak / 'reaper_status.json').read_text(encoding='utf-8')
    results['7_error_reported'] = code == 1 and '"error"' in out
    results['7_key_never_printed'] = FAKE_KEY not in out and FAKE_KEY not in status_text

    results['all_passed'] = all(v is True for v in results.values())
    (work / 'proof_result.json').write_text(json.dumps(results, indent=1), encoding='utf-8')
    print(json.dumps(results, indent=1))
    return 0 if results['all_passed'] else 1


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--fake-controller':
        fake_controller(sys.argv[2])
    else:
        raise SystemExit(main(sys.argv[1]))
