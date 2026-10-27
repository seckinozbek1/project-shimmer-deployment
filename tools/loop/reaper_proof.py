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
6. The hard stop is the ledger's own (D-S9): a spend past an earlier 49 USD stop but below
   the latest line's 69 USD leaves the instance alone; once spend reaches 69 it is
   terminated.
8. With no budget line at all, every loop instance is terminated.
9. An intent whose launch created no instance is left open before its deadline and closed
   once after it (reason ``intent_without_instance``), charged to the deadline.
10. With two ledgers (the private one and R's), each such intent is closed in the ledger that
   holds it, so a launch recorded only in R's ledger is closed where R's guard reads it.
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


def budget_line(event, budget, moment):
    """A budget line of the private ledger's shape; the reaper reads its stop from it."""
    return {'event': event, 'time_utc': iso(moment), 'loop_start_utc': iso(moment), 'budget_usd': budget,
            'storage_usd_per_day': 0.0}


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
    (work / 'ledger.jsonl').write_text(json.dumps(budget_line('budget_open', 70.0, datetime.now(timezone.utc)))
                                       + '\n', encoding='utf-8')

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
    results['1_intent_written_before_launch'] = ledger_rows[1]['event'] == 'launch_intent'

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
        budget_line('budget_open', 50.0, now - timedelta(hours=50)),
        dict(budget_line('budget_change', 70.0, now - timedelta(hours=45)), hard_stop_usd=69.0),
        {'event': 'launch', 'instance_id': 'd' * 32, 'instance_name': 'shimmer-loop-old',
         'price_usd_per_hour': 1.29, 'launch_requested_utc': iso(now - timedelta(hours=40))},
        {'event': 'termination', 'instance_id': 'd' * 32, 'instance_name': 'shimmer-loop-old', 'actual_cost': 49.5},
        {'event': 'launch', 'instance_id': 'c' * 32, 'instance_name': 'shimmer-loop-proof-0002',
         'price_usd_per_hour': 1.29, 'launch_requested_utc': iso(now), 'deadline_utc': iso(now + timedelta(hours=1))},
    ]) + '\n', encoding='utf-8')
    code, out = run_reaper(hard, now)
    state = json.loads((hard / 'mock_state.json').read_text(encoding='utf-8'))
    results['6_old_49_stop_no_longer_applies'] = (code == 0 and state['instances'][0]['status'] == 'active'
                                                  and '"hard_stop_usd": 69.0' in out)
    with open(hard / 'ledger.jsonl', 'a', encoding='utf-8') as handle:
        for row in ({'event': 'launch', 'instance_id': 'e' * 32, 'instance_name': 'shimmer-loop-old2',
                     'price_usd_per_hour': 1.29, 'launch_requested_utc': iso(now - timedelta(hours=30))},
                    {'event': 'termination', 'instance_id': 'e' * 32, 'instance_name': 'shimmer-loop-old2',
                     'actual_cost': 19.6}):
            handle.write(json.dumps(row) + '\n')
    code, out = run_reaper(hard, now)
    state = json.loads((hard / 'mock_state.json').read_text(encoding='utf-8'))
    results['6_hard_stop_terminates'] = state['instances'][0]['status'] == 'terminated' and 'hard_stop_spend_reached' in out

    bare = work / 'bare'
    bare.mkdir()
    (bare / 'mock_state.json').write_text(json.dumps({'instances': [
        {'instance_id': 'f' * 32, 'name': 'shimmer-loop-proof-0003', 'status': 'active'}]}), encoding='utf-8')
    (bare / 'ledger.jsonl').write_text(json.dumps(
        {'event': 'launch', 'instance_id': 'f' * 32, 'instance_name': 'shimmer-loop-proof-0003', 'price_usd_per_hour': 1.29,
         'launch_requested_utc': iso(now), 'deadline_utc': iso(now + timedelta(hours=1))}) + '\n', encoding='utf-8')
    code, out = run_reaper(bare, now)
    state = json.loads((bare / 'mock_state.json').read_text(encoding='utf-8'))
    results['8_no_budget_line_terminates'] = state['instances'][0]['status'] == 'terminated' and 'no_budget_recorded' in out

    # 9. An intent whose launch created no instance (the controller died between the intent
    # line and the launch reply): left open before its deadline, closed after it with one
    # line charged to the deadline, and never touched again.
    lost = work / 'lost'
    lost.mkdir()
    (lost / 'mock_state.json').write_text(json.dumps({'instances': []}), encoding='utf-8')
    deadline = now + timedelta(minutes=30)
    (lost / 'ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in [
        budget_line('budget_open', 70.0, now - timedelta(hours=1)),
        {'event': 'launch_intent', 'time_utc': iso(now), 'instance_name': 'shimmer-loop-proof-0004',
         'launch_requested_utc': iso(now), 'deadline_utc': iso(deadline), 'price_usd_per_hour': 1.29},
    ]) + '\n', encoding='utf-8')
    code, out = run_reaper(lost, deadline - timedelta(seconds=30))
    results['9_intent_before_deadline_left_open'] = (
        code == 0 and len((lost / 'ledger.jsonl').read_text(encoding='utf-8').splitlines()) == 2)
    code, out = run_reaper(lost, deadline + timedelta(seconds=1))
    lines = [json.loads(l) for l in (lost / 'ledger.jsonl').read_text(encoding='utf-8').splitlines() if l]
    results['9_intent_without_instance_closed'] = (
        code == 0 and len(lines) == 3 and lines[-1]['event'] == 'termination'
        and lines[-1]['reason'] == 'intent_without_instance' and lines[-1]['actual_minutes'] == 30)
    code, out = run_reaper(lost, deadline + timedelta(minutes=10))
    results['9_closed_once'] = code == 0 and len((lost / 'ledger.jsonl').read_text(encoding='utf-8').splitlines()) == 3

    # 10. Two ledgers, as the scheduled reaper reads them (the private ledger and R's): an
    # intent recorded only in R's ledger is closed in R's ledger, one recorded only in the
    # private ledger in the private one, each once, charged to its deadline.
    two = work / 'two'
    two.mkdir()
    (two / 'mock_state.json').write_text(json.dumps({'instances': []}), encoding='utf-8')
    intent = lambda name: {'event': 'launch_intent', 'time_utc': iso(now), 'instance_name': name,
                           'launch_requested_utc': iso(now), 'deadline_utc': iso(deadline), 'price_usd_per_hour': 1.29}
    private, r_ledger = two / 'private.jsonl', two / 'R_ledger.jsonl'
    private.write_text('\n'.join(json.dumps(r) for r in [budget_line('budget_open', 70.0, now - timedelta(hours=1)),
                                                          intent('shimmer-loop-proof-private')]) + '\n', encoding='utf-8')
    r_ledger.write_text(json.dumps(intent('shimmer-loop-proof-r')) + '\n', encoding='utf-8')
    args = [sys.executable, str(REAPER), '--mock-state', str(two / 'mock_state.json'), '--ledger', str(private),
            '--ledger', str(r_ledger), '--append-to', str(private), '--status', str(two / 'reaper_status.json'),
            '--now', iso(deadline + timedelta(seconds=1))]
    code = subprocess.run(args, capture_output=True, text=True, timeout=60).returncode
    ends = lambda path: [(r['instance_name'], r['reason'], r['actual_minutes'])
                         for r in map(json.loads, path.read_text(encoding='utf-8').splitlines()) if r['event'] == 'termination']
    results['10_closed_in_the_ledger_that_holds_it'] = (
        code == 0 and ends(r_ledger) == [('shimmer-loop-proof-r', 'intent_without_instance', 30)]
        and ends(private) == [('shimmer-loop-proof-private', 'intent_without_instance', 30)])

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
