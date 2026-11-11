"""A live view of an exposed cloud run, item by item, read from the instance's own records.

Annex D D-S66 of the loop specification. Beside `tools/ordinary_final_progress.py` (PROGRESS-A),
which gives one measured line for the phase now running, this reader shows each call as it
finishes: passed, refused (with its reason), out of memory or crashed, and its seconds; the
running counts per outcome; the phase, the cost so far and the measured progress line; and a
stall warning when nothing has finished for longer than the run's own measured per-item time
allows. It renders a local page that refreshes itself and prints a one-line summary, then one
`ALERT` line per failure pattern (the same failure repeating, out of memory, a crash, a refusal
rate above the run's development figure, a stall) for the lead to act on. It never pushes and
never writes to FOR_SECKIN: acting on an alert is the lead's.

    py -3.12 -X utf8 tools/ordinary_final_live.py --bundle external/s05/P1/P3_TRAIN_B
    py -3.12 -X utf8 tools/ordinary_final_live.py --bundle B --watch 60 --development-refusals 9/84

What it reads, and what it never reads. The instance keeps one JSON record per model call under
`audit/model_replies/` and, for a pipeline run, the outcome of each call in `outcomes.jsonl`
beside them (scripts/reply_records.py). The one remote program (`REMOTE_SCRIPT`) runs on the
instance over the run's own key, through `ordinary_final_progress.observe`, reads those files
and prints ONLY the fields named in `ITEM_FIELDS`: counts, ids, outcomes, reasons and times. A
record's payload and reply (the text, and even their digests) never leave the instance. It opens
every file for reading only and writes, moves and deletes nothing (`remote_script_is_read_only`).

A sealed bundle (SEALED-RUN-A) is read in counts mode: the remote program sends no id, no
document name and no reason, the snapshot is stripped of them again here, the page and the
summary show counts and timings only, and `--items` is refused. Whether a bundle is exposed is
read from its `seal.json` and fails closed: anything but `exposure: exposed` with no test
manifest is treated as sealed, and a sealed bundle's page may not be written inside the
repository.

This tool is not part of the bound controller (no `local_control_hashes` names it), so no bundle
is re-sealed for it, and it changes nothing on the instance. `--observations` replays a saved
map of remote command to remote answer instead of reaching the instance, which is how its proofs
(`tools/ordinary_final_live_checks.py`, gate check 340) run with no network; `--save-observations`
writes that map from a live reading.
"""
import argparse
import base64
import html
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools')]
import ordinary_final_progress as progress
from cloud_run_common import no_window

REMOTE_ROOT = progress.REMOTE_ROOT
MARKER = 'shimmer-live-view-v1'
# The fields of one finished call the remote program may send in detail mode. Nothing else
# leaves the instance: no payload, no reply, no digest of either, no error text beyond its
# category (reply_records cuts it at the first colon, and the remote program keeps only
# letters, digits and a few separators of that).
ITEM_FIELDS = ('folder', 'sequence', 'call_id', 'agent', 'doc_id', 'phase', 'backend_ok', 'error_category',
               'finished_epoch', 'over_context', 'dead_end', 'outcome', 'outcome_source')
# What a sealed bundle's counts mode sends per call: the inputs of its class and its time.
COUNT_FIELDS = ('backend_ok', 'oom', 'finished_epoch', 'over_context', 'dead_end', 'outcome')
STATUSES = ('passed', 'refused', 'out_of_memory', 'crashed')
# Outcomes of reply_records.OUTCOMES that mean the call's answer was not taken.
REFUSED_OUTCOMES = ('refused', 'contract_violation', 'retry_skipped_deterministic')
CRASHED_OUTCOMES = ('backend_failure', 'classifier_failed')
# The alert rules, stated. A stall is a time since the last finish longer than STALL_FACTOR
# times the run's own median seconds per item, and never shorter than its slowest measured item;
# it is judged only once STALL_MIN_MEASURED items have a measured time. A repeated failure is
# the last REPEAT_RUN finished items failing with the same status and reason. A refusal rate is
# compared with the development figure only once RATE_MIN_ITEMS items have finished.
STALL_FACTOR = 3.0
STALL_MIN_MEASURED = 3
REPEAT_RUN = 3
RATE_MIN_ITEMS = 10
DEFAULT_REFRESH_SECONDS = 60
# What the sealer writes in place of a test manifest's digest on an exposed seal (SEALED-RUN-A).
EXPOSED_MANIFEST = 'exposed, no manifest'

REMOTE_SCRIPT = r'''
import json, os, re, sys, time
mode = sys.argv[1]
roots = ('evidence', 'project/output/runs')
SAFE = re.compile(r'[^A-Za-z0-9_. -]')
OOM = re.compile(r'out of memory|outofmemory', re.I)
def epoch(stamp):
    try:
        from datetime import datetime
        return datetime.fromisoformat(stamp).timestamp()
    except Exception:
        return None
def folders():
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for here, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in ('hf_cache', 'venv', 'wheels', 'candidate', 'candidate_half'))
            if os.path.basename(here) == 'model_replies' and os.path.basename(os.path.dirname(here)) == 'audit':
                found.append(here)
    return found
def outcomes(here):
    current = {}
    path = os.path.join(here, 'outcomes.jsonl')
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get('call_id'):
                    current[str(row['call_id'])] = (str(row.get('outcome', '')), str(row.get('source', '')))
    return current
items = []
for here in folders():
    decided = outcomes(here)
    for name in sorted(os.listdir(here)):
        if not name.endswith('.json'):
            continue
        try:
            with open(os.path.join(here, name), 'r', encoding='utf-8') as stream:
                record = json.load(stream)
        except Exception:
            continue
        if not isinstance(record, dict):
            continue
        category = SAFE.sub('', str(record.get('error_category') or ''))[:80]
        context = record.get('context') if isinstance(record.get('context'), dict) else {}
        constraint = record.get('decoding_constraint') if isinstance(record.get('decoding_constraint'), dict) else {}
        outcome, source = decided.get(str(record.get('call_id')), ('', ''))
        row = dict(backend_ok=bool(record.get('backend_ok')), finished_epoch=epoch(str(record.get('timestamp') or '')),
                   over_context=bool(context.get('over_context')), dead_end=bool(constraint.get('dead_end')),
                   outcome=outcome)
        if mode == 'detail':
            row.update(folder=here, sequence=record.get('sequence'), call_id=str(record.get('call_id') or ''),
                       agent=str(record.get('agent') or ''), doc_id=str(record.get('doc_id') or ''),
                       phase=str(record.get('phase') or ''), error_category=category, outcome_source=source)
        else:
            row.update(oom=bool(OOM.search(category)))
        items.append(row)
markers = dict(traceback=0, out_of_memory=0)
if os.path.isfile('workload.stderr.log'):
    with open('workload.stderr.log', 'r', encoding='utf-8', errors='replace') as stream:
        for line in stream:
            if 'Traceback (most recent call last)' in line:
                markers['traceback'] += 1
            if OOM.search(line):
                markers['out_of_memory'] += 1
training = None
for pattern_root in ('evidence/b1',):
    newest = None
    if os.path.isdir(pattern_root):
        for here, dirs, files in os.walk(pattern_root):
            dirs[:] = [d for d in dirs if d not in ('audit', 'candidate', 'candidate_half')]
            if os.path.basename(here) == 'training' and 'progress.json' in files:
                path = os.path.join(here, 'progress.json')
                if newest is None or os.path.getmtime(path) > os.path.getmtime(newest):
                    newest = path
    if newest:
        try:
            with open(newest, 'r', encoding='utf-8') as stream:
                state = json.load(stream)
            training = {k: state.get(k) for k in ('phase', 'update', 'of', 'elapsed_seconds', 'seconds_per_update',
                                                   'questions_total', 'started_epoch') if k in state}
            training['written_epoch'] = os.path.getmtime(newest)
        except Exception:
            training = dict(unreadable=True)
expected = None
if os.path.isfile('evidence/b1/expected_records'):
    with open('evidence/b1/expected_records', 'r', encoding='utf-8') as stream:
        text = stream.read().strip()
    expected = int(text) if text.isdigit() else None
print(json.dumps(dict(marker='MARKER', mode=mode, now=time.time(), items=items, stderr_markers=markers,
                      training=training, expected_records=expected), sort_keys=True))
'''.replace('MARKER', MARKER)


class SealedRefusal(Exception):
    """Item-level detail asked of a sealed bundle (SEALED-RUN-A)."""


def remote_command(mode):
    """The one read-only shell command run on the instance: the remote program, sent encoded so
    no quoting can break it, run by the instance's own python3 in isolated mode."""
    if mode not in ('detail', 'counts'):
        raise ValueError('unknown remote mode')
    encoded = base64.b64encode(REMOTE_SCRIPT.encode('utf8')).decode('ascii')
    return 'cd %s && echo %s | base64 -d | python3 -I - %s # %s' % (REMOTE_ROOT, encoded, mode, observation_key(mode))


def observation_key(mode):
    """The stable tail of the remote command, by which a saved observation is found again even
    after the remote program's text changes."""
    return '%s %s' % (MARKER, mode)


def observe_to_file(bundle, host, command, timeout=90):
    """One read-only observation whose answer can be large: the same ssh call as
    `ordinary_final_progress.observe`, with its output taken into a temporary file. Measured, not
    preferred: on this machine an ssh answer of more than about 32 KB read through a pipe never
    completed (40,000 bytes timed out where 9,000 took 2 s), and the same answer into a file took
    2 s. Returns the answer, or None if unreadable."""
    argv = ['ssh', '-i', str(Path(bundle) / 'ssh_identity'), *progress.SSH_OPTIONS,
            '-o', 'UserKnownHostsFile=' + str(Path(bundle) / 'known_hosts'), host, command]
    with tempfile.TemporaryFile() as answer:
        try:
            result = subprocess.run(argv, stdout=answer, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                    timeout=timeout, creationflags=no_window())
        except (subprocess.TimeoutExpired, OSError):
            return None
        if result.returncode != 0:
            return None
        answer.seek(0)
        return answer.read().decode('utf8', 'replace').strip()


def remote_script_is_read_only(source=None):
    """True when the remote program opens every file for reading and calls nothing that writes,
    moves, deletes or starts a process. Read from the program's own syntax tree."""
    import ast
    tree = ast.parse(source if source is not None else REMOTE_SCRIPT)
    forbidden = {'remove', 'unlink', 'rename', 'replace', 'rmdir', 'removedirs', 'mkdir', 'makedirs', 'write',
                 'writelines', 'write_text', 'write_bytes', 'system', 'popen', 'Popen', 'run', 'call', 'check_call',
                 'check_output', 'chmod', 'chown', 'truncate', 'symlink', 'link', 'utime', 'kill', 'exec', 'eval'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            names = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) else [])
            if any(n in ('subprocess', 'shutil', 'socket', 'urllib', 'http') for n in names if n):
                return False
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ''
            if name in forbidden:
                return False
            if name == 'open':
                modes = [a.value for a in node.args[1:2] if isinstance(a, ast.Constant)]
                modes += [k.value.value for k in node.keywords if k.arg == 'mode' and isinstance(k.value, ast.Constant)]
                if not modes or any(set(str(m)) - set('rbt') for m in modes):
                    return False
    return True


def exposure(bundle):
    """'exposed' only when the bundle's seal says exposed and carries no test manifest; 'sealed'
    for everything else, an unreadable or missing seal included (fails closed)."""
    try:
        seal = json.loads((Path(bundle) / 'seal.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        return 'sealed'
    if (isinstance(seal, dict) and seal.get('exposure') == 'exposed'
            and seal.get('test_manifest_sha256') in (None, EXPOSED_MANIFEST)):
        return 'exposed'
    return 'sealed'


def is_oom(item):
    if 'oom' in item:
        return bool(item['oom'])
    category = str(item.get('error_category') or '').lower().replace(' ', '')
    return 'outofmemory' in category


def classify(item):
    """(status, reason) of one finished call, from its record and its outcome only."""
    outcome = item.get('outcome') or ''
    if not item.get('backend_ok', True):
        if is_oom(item):
            return 'out_of_memory', 'out of memory'
        return 'crashed', item.get('error_category') or 'backend call failed'
    if outcome in CRASHED_OUTCOMES:
        return 'crashed', outcome
    if item.get('over_context'):
        return 'refused', 'prompt_over_context'
    if item.get('dead_end'):
        return 'refused', 'decoding_dead_end'
    if outcome in REFUSED_OUTCOMES:
        return 'refused', outcome
    return 'passed', ''


def finishes(items):
    """The finished calls in the order they finished, each with its status, its reason and its
    seconds: the time since the call before it in the same records folder finished (the first in
    a folder has no earlier finish, so its seconds are not measured)."""
    rows = sorted((dict(item) for item in items if item.get('finished_epoch') is not None),
                  key=lambda r: (r['finished_epoch'], r.get('sequence') or 0))
    last = {}
    for row in rows:
        row['status'], row['reason'] = classify(row)
        key = row.get('folder', '')
        row['seconds'] = row['finished_epoch'] - last[key] if key in last else None
        last[key] = row['finished_epoch']
    return rows


def stall_allowance(seconds):
    """The longest quiet time the run's own measured items allow, or None when too few are measured."""
    measured = [s for s in seconds if s is not None and s >= 0]
    if len(measured) < STALL_MIN_MEASURED:
        return None
    return max(STALL_FACTOR * statistics.median(measured), max(measured))


def development_rate(text):
    """'9/84' (refusals of items on the development set) as a fraction, or None."""
    if not text:
        return None
    refused, _, total = str(text).partition('/')
    if not (refused.strip().isdigit() and total.strip().isdigit()) or int(total) <= 0:
        raise ValueError('a development figure is written refused/total, for example 9/84')
    return int(refused) / int(total)


def strip_for_sealed(snapshot):
    """A sealed bundle's snapshot keeps counts and timings only, whatever the remote side sent."""
    kept = dict(snapshot)
    kept['rows'] = [dict(status=r['status'], seconds=r['seconds'], finished_epoch=r['finished_epoch'])
                    for r in snapshot.get('rows', [])]
    kept['documents'] = []
    kept['reasons'] = {}
    return kept


def oom_signal(snapshot):
    """Words for the out-of-memory evidence (calls, and lines of the workload's own log), or None."""
    markers = snapshot.get('stderr_markers') or {}
    calls, lines = snapshot['counts']['out_of_memory'], markers.get('out_of_memory', 0)
    if not (calls or lines):
        return None
    return '%d calls out of memory, %d out-of-memory lines in the workload log' % (calls, lines)


def crash_signal(snapshot):
    """Words for the crash evidence (crashed calls, tracebacks in the workload's log, a workload
    that exited with a code other than 0), or None."""
    markers = snapshot.get('stderr_markers') or {}
    calls, tracebacks = snapshot['counts']['crashed'], markers.get('traceback', 0)
    exit_code = snapshot.get('workload_exit_code')
    if not (calls or tracebacks or exit_code not in (None, 0)):
        return None
    return '%d calls crashed, %d tracebacks in the workload log, workload exit %s' % (
        calls, tracebacks, 'not yet' if exit_code is None else exit_code)


def bound_controller_files():
    """The files every new seal pins as the controller (`local_control_hashes`), read from the
    sealer's own source, so this tool can show it is not among them."""
    source = (ROOT / 'tools' / 'prepare_ordinary_final_run.py').read_text(encoding='utf8')
    block = source.split('local_control_hashes={n:sha(ROOT/n) for n in (', 1)[1].split(')}', 1)[0]
    import re
    return sorted(set(re.findall(r"'(tools/[^']+\.py)'", block)))


def alerts(snapshot, dev_rate):
    """The failure patterns, one line each, from the snapshot's counts, rows and markers."""
    found = []
    name = snapshot['bundle_name']
    counts, rows = snapshot['counts'], snapshot['rows']
    oom = oom_signal(snapshot)
    if oom:
        found.append('ALERT %s out_of_memory: %s' % (name, oom))
    crash = crash_signal(snapshot)
    if crash:
        found.append('ALERT %s crash: %s' % (name, crash))
    tail = rows[-REPEAT_RUN:]
    if len(tail) == REPEAT_RUN and all(r['status'] != 'passed' for r in tail):
        kinds = {(r['status'], r.get('reason', '')) for r in tail}
        if len(kinds) == 1:
            status, reason = kinds.pop()
            found.append('ALERT %s repeated: the last %d finished calls were %s%s'
                         % (name, REPEAT_RUN, status, (' (%s)' % reason) if reason else ''))
    finished = len(rows)
    if dev_rate is not None and finished >= RATE_MIN_ITEMS:
        rate = counts['refused'] / finished
        if rate > dev_rate:
            found.append('ALERT %s refusal_rate: %d of %d refused (%.1f%%), above the development figure %.1f%%'
                         % (name, counts['refused'], finished, 100 * rate, 100 * dev_rate))
    stall = snapshot.get('stall') or {}
    if stall.get('stalled'):
        found.append('ALERT %s stall: nothing finished for %.0f s; the run\'s own measured %s allow %.0f s'
                     % (name, stall['quiet_seconds'], stall['basis'], stall['allowance_seconds']))
    return found


def stall_reading(rows, training, now):
    """Is the run quiet for longer than its own measured time allows? During training the unit is
    an update (its progress file's measured seconds per update and the time the file was last
    written); once questions run, the unit is a finished call."""
    if training and not training.get('unreadable') and training.get('phase') == 'training':
        each = training.get('seconds_per_update')
        written = training.get('written_epoch')
        if not each or written is None:
            return dict(stalled=False, judged=False, why='the training progress file states no seconds per update yet')
        allowance = STALL_FACTOR * float(each)
        quiet = now - float(written)
        return dict(stalled=quiet > allowance, judged=True, quiet_seconds=quiet, allowance_seconds=allowance,
                    basis='seconds per training update (%.1f s)' % float(each))
    allowance = stall_allowance([r['seconds'] for r in rows])
    if allowance is None:
        return dict(stalled=False, judged=False,
                    why='fewer than %d finished calls have a measured time' % STALL_MIN_MEASURED)
    quiet = now - rows[-1]['finished_epoch']
    return dict(stalled=quiet > allowance, judged=True, quiet_seconds=quiet, allowance_seconds=allowance,
                basis='seconds per call (median %.1f s, slowest %.1f s)'
                      % (statistics.median([r['seconds'] for r in rows if r['seconds'] is not None]),
                         max(r['seconds'] for r in rows if r['seconds'] is not None)))


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf8'))
    except (OSError, ValueError):
        return None


def cost_reading(bundle, now):
    """The controller's own cost figure and, from its hourly rate and the instance's active start,
    the cost to this reading. Both are the provider's price times time; neither is an invoice."""
    cost = read_json(Path(bundle) / 'cost.json') or {}
    if 'estimated_infrastructure_usd' not in cost:
        return dict(text='cost not readable (the bundle has no cost.json yet)')
    text = 'cost $%.2f at the controller\'s last reading' % float(cost['estimated_infrastructure_usd'])
    value = dict(controller_usd=float(cost['estimated_infrastructure_usd']))
    if cost.get('hourly_rate') and cost.get('active_start_epoch'):
        to_now = float(cost['hourly_rate']) * max(now - float(cost['active_start_epoch']), 0) / 3600
        value['to_now_usd'] = to_now
        text += ', $%.2f to now at $%.2f/h since the instance became active' % (to_now, float(cost['hourly_rate']))
    value['text'] = text
    return value


def snapshot_for(bundle, observations=None, now=None, record=None):
    """One reading of the bundle's run. `observations` replays saved remote answers; `record`, a
    dict, collects every remote command and answer of a live reading for --save-observations."""
    bundle = Path(bundle)
    level = exposure(bundle)
    mode = 'detail' if level == 'exposed' else 'counts'
    current = read_json(bundle / 'CURRENT_PHASE.json') or {}
    status = read_json(bundle / 'ordinary_workload_status.json') or {}
    command = remote_command(mode)

    if observations is not None:
        raw = next((value for key, value in observations.items() if key.endswith(observation_key(mode))), None)
        line = progress.reading_for(bundle, observations=observations, now=now)
    else:
        original = progress.observe

        def recording(b, host, text, timeout=40):
            answer = original(b, host, text, timeout=timeout)
            if record is not None:
                record[text] = answer
            return answer
        progress.observe = recording
        try:
            host = progress.host_for(bundle)
            raw = observe_to_file(bundle, host, command) if host else None
            if record is not None:
                record[command] = raw
            line = progress.reading_for(bundle, now=now)
        finally:
            progress.observe = original

    remote = None
    if raw:
        try:
            remote = json.loads(raw.strip().splitlines()[-1])
        except (ValueError, IndexError):
            remote = None
    now = now if now is not None else (remote or {}).get('now', time.time())
    snapshot = dict(bundle_name=bundle.name, exposure=level, phase=current.get('phase', 'unknown'),
                    progress=line, cost=cost_reading(bundle, now), now=now,
                    workload_exit_code=status.get('exit_code'), remote_work=status.get('remote_work'),
                    readable=remote is not None and remote.get('marker') == MARKER)
    if not snapshot['readable']:
        snapshot.update(rows=[], counts={s: 0 for s in STATUSES}, documents=[], reasons={}, stderr_markers={},
                        stall=dict(stalled=False, judged=False, why='the instance did not answer the reading'),
                        expected_records=None, training=None)
        return strip_for_sealed(snapshot) if level != 'exposed' else snapshot
    rows = finishes(remote.get('items') or [])
    counts = {s: sum(1 for r in rows if r['status'] == s) for s in STATUSES}
    reasons = {}
    documents = {}
    for r in rows:
        if r['status'] != 'passed':
            reasons[(r['status'], r['reason'])] = reasons.get((r['status'], r['reason']), 0) + 1
        doc = documents.setdefault(r.get('doc_id', ''), dict(doc_id=r.get('doc_id', ''), calls=0, worst='passed',
                                                               last_epoch=None))
        doc['calls'] += 1
        doc['last_epoch'] = r['finished_epoch']
        if STATUSES.index(r['status']) > STATUSES.index(doc['worst']):
            doc['worst'] = r['status']
    snapshot['undecided'] = sum(1 for r in rows if r['status'] == 'passed' and not r.get('outcome'))
    snapshot.update(rows=rows, counts=counts, documents=list(documents.values()),
                    reasons={'%s: %s' % k: v for k, v in reasons.items()},
                    stderr_markers=remote.get('stderr_markers') or {}, training=remote.get('training'),
                    expected_records=remote.get('expected_records'))
    snapshot['stall'] = stall_reading(rows, remote.get('training'), now) if rows or remote.get('training') else dict(
        stalled=False, judged=False, why='nothing has finished yet')
    return strip_for_sealed(snapshot) if level != 'exposed' else snapshot


def summary_line(snapshot):
    counts = snapshot['counts']
    finished = sum(counts.values())
    parts = ['%s [%s] phase %s' % (snapshot['bundle_name'], snapshot['exposure'], snapshot['phase'])]
    if not snapshot['readable']:
        parts.append('item records not readable (the instance did not answer)')
    else:
        total = snapshot.get('expected_records')
        stated = (' of %d' % total) if total and finished <= total else ''
        parts.append('%d%s calls finished: %s' % (finished, stated,
                                                  ', '.join('%d %s' % (counts[s], s.replace('_', ' ')) for s in STATUSES)))
        if total and finished > total:
            parts.append('the expected-records file states %d, fewer than the records counted, so records of '
                         'earlier passes are among them' % total)
        if snapshot.get('undecided'):
            parts.append('%d of the passed returned with no outcome recorded (their replies are judged after the run)'
                         % snapshot['undecided'])
        if snapshot['rows']:
            parts.append('last finish %.0f s ago' % (snapshot['now'] - snapshot['rows'][-1]['finished_epoch']))
    stall = snapshot['stall']
    parts.append(('STALLED' if stall.get('stalled') else 'not stalled') if stall.get('judged')
                 else 'stall not judged (%s)' % stall.get('why'))
    parts.append(snapshot['cost']['text'])
    return '; '.join(parts) + ' | ' + snapshot['progress']


def item_lines(snapshot, limit=None):
    if snapshot['exposure'] != 'exposed':
        raise SealedRefusal('Sealed bundle: counts and timings only (SEALED-RUN-A); item detail is refused')
    rows = snapshot['rows'][-limit:] if limit else snapshot['rows']
    return ['%s %s %s %s %s%s %s' % (time.strftime('%H:%M:%S', time.gmtime(r['finished_epoch'])), r.get('call_id', '')[:12],
                                     r.get('agent', ''), r.get('doc_id', ''), r['status'],
                                     (' (%s)' % r['reason']) if r['reason'] else '',
                                     'n/a s' if r['seconds'] is None else '%.1f s' % r['seconds']) for r in rows]


PAGE_STYLE = '''
:root{--bg:#f7f7f5;--fg:#1d1d1b;--muted:#666660;--line:#d9d9d4;--card:#ffffff;--ok:#2f6f3e;--warn:#9a5b00;--bad:#a02828}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#161615;--fg:#ececea;--muted:#a3a39e;--line:#33332f;--card:#1f1f1d;--ok:#7fc28f;--warn:#e0a552;--bad:#ef7d7d}}
:root[data-theme="dark"]{--bg:#161615;--fg:#ececea;--muted:#a3a39e;--line:#33332f;--card:#1f1f1d;--ok:#7fc28f;--warn:#e0a552;--bad:#ef7d7d}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0;padding:16px}
h1{font-size:18px;margin:0 0 4px}p{margin:4px 0}.muted{color:var(--muted)}
.cards{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 12px;min-width:110px}
.card b{display:block;font-size:20px}.alert{border:1px solid var(--bad);color:var(--bad);border-radius:6px;padding:6px 10px;margin:6px 0}
table{border-collapse:collapse;width:100%;background:var(--card)}td,th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto}.passed{color:var(--ok)}.refused{color:var(--warn)}.out_of_memory,.crashed{color:var(--bad)}
'''


def page(snapshot, alert_lines, refresh):
    e = html.escape
    counts = snapshot['counts']
    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           '<meta http-equiv="refresh" content="%d">' % int(refresh),
           '<title>Live run view</title><style>%s</style></head><body>' % PAGE_STYLE,
           '<h1>%s</h1>' % e(snapshot['bundle_name']),
           '<p class="muted">%s run, phase %s, read %s UTC; this page refreshes every %d s.</p>'
           % (e(snapshot['exposure']), e(snapshot['phase']),
              e(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(snapshot['now']))), int(refresh)),
           '<p>%s</p><p>%s</p>' % (e(snapshot['progress']), e(snapshot['cost']['text']))]
    if snapshot.get('undecided'):
        out.append('<p class="muted">%d of the passed calls returned with no outcome recorded: passed here means the call '
                   'returned and nothing refused it; its reply is judged after the run.</p>' % snapshot['undecided'])
    out.append('<div class="cards">' + ''.join('<div class="card"><b class="%s">%d</b>%s</div>' % (s, counts[s], e(s.replace('_', ' ')))
                                               for s in STATUSES) + '</div>')
    stall = snapshot['stall']
    out.append('<p>%s</p>' % e(('Stalled: ' if stall.get('stalled') else 'Not stalled: ') +
                               'quiet %.0f s, allowed %.0f s by the measured %s' % (stall['quiet_seconds'], stall['allowance_seconds'], stall['basis'])
                               if stall.get('judged') else 'Stall not judged: ' + str(stall.get('why'))))
    for line in alert_lines:
        out.append('<div class="alert">%s</div>' % e(line))
    if snapshot['exposure'] != 'exposed':
        out.append('<p class="muted">Sealed run: counts and timings only (SEALED-RUN-A). No call id, document, agent or reason is shown.</p>')
        out.append('<div class="wrap"><table><tr><th>finished (UTC)</th><th>outcome</th><th>seconds</th></tr>')
        for r in reversed(snapshot['rows'][-200:]):
            out.append('<tr><td>%s</td><td class="%s">%s</td><td>%s</td></tr>'
                       % (time.strftime('%H:%M:%S', time.gmtime(r['finished_epoch'])), r['status'], e(r['status']),
                          'n/a' if r['seconds'] is None else '%.1f' % r['seconds']))
        out.append('</table></div></body></html>')
        return '\n'.join(out)
    if snapshot['reasons']:
        out.append('<h2>Reasons</h2><ul>' + ''.join('<li>%s: %d</li>' % (e(k), v) for k, v in sorted(snapshot['reasons'].items())) + '</ul>')
    out.append('<h2>Documents</h2><div class="wrap"><table><tr><th>document</th><th>calls</th><th>worst outcome</th></tr>')
    for doc in reversed(snapshot['documents'][-200:]):
        out.append('<tr><td>%s</td><td>%d</td><td class="%s">%s</td></tr>' % (e(doc['doc_id'] or '(none)'), doc['calls'], doc['worst'], e(doc['worst'])))
    out.append('</table></div><h2>Calls, latest first</h2><div class="wrap"><table><tr><th>finished (UTC)</th><th>call</th>'
               '<th>agent</th><th>document</th><th>outcome</th><th>reason</th><th>seconds</th></tr>')
    for r in reversed(snapshot['rows'][-500:]):
        out.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td><td>%s</td><td>%s</td></tr>'
                   % (time.strftime('%H:%M:%S', time.gmtime(r['finished_epoch'])), e(r.get('call_id', '')[:12]), e(r.get('agent', '')),
                      e(r.get('doc_id', '')), r['status'], e(r['status']), e(r['reason']),
                      'n/a' if r['seconds'] is None else '%.1f' % r['seconds']))
    out.append('</table></div></body></html>')
    return '\n'.join(out)


def inside_repository(path):
    try:
        Path(path).resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def write_page(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + '.partial')
    partial.write_text(text, encoding='utf8')
    os.replace(partial, path)


def one_reading(bundle, arguments, observations, dev_rate, record):
    snapshot = snapshot_for(bundle, observations=observations, now=arguments.now, record=record)
    found = alerts(snapshot, dev_rate)
    target = arguments.page or (Path(bundle) / 'live_view' / 'index.html')
    if snapshot['exposure'] != 'exposed' and inside_repository(target):
        raise SealedRefusal('Sealed bundle: its page is never written inside the repository (SEALED-RUN-A)')
    if not arguments.no_page:
        write_page(target, page(snapshot, found, arguments.watch or DEFAULT_REFRESH_SECONDS))
    print(summary_line(snapshot))
    if arguments.items:
        for line in item_lines(snapshot, arguments.items):
            print('  ' + line)
    if dev_rate is None and snapshot['readable']:
        print('  refusal-rate alert not judged: no development figure given (--development-refusals)')
    for line in found:
        print(line)
    return snapshot, found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--bundle', type=Path, action='append', required=True,
                        help='A run folder (repeat for several runs).')
    parser.add_argument('--page', type=Path, default=None, help='Page path (one bundle only); default <bundle>/live_view/index.html.')
    parser.add_argument('--no-page', action='store_true', help='Print the summary only.')
    parser.add_argument('--items', type=int, default=0, help='Also print the last N finished calls (refused for a sealed bundle).')
    parser.add_argument('--watch', type=int, default=0, help='Read again every N seconds until interrupted.')
    parser.add_argument('--development-refusals', default=None, help='The development figure, refused/total, e.g. 9/84.')
    parser.add_argument('--observations', type=Path, default=None, help='A saved {command: answer} map replacing every remote call.')
    parser.add_argument('--save-observations', type=Path, default=None, help='Write the remote commands and answers of this reading.')
    parser.add_argument('--now', type=float, default=None, help='The reading time, for a replayed reading.')
    arguments = parser.parse_args(argv)
    if arguments.page and len(arguments.bundle) > 1:
        parser.error('--page names one page; give one bundle')
    if (arguments.observations or arguments.save_observations) and len(arguments.bundle) > 1:
        parser.error('observations are saved and replayed for one bundle')
    dev_rate = development_rate(arguments.development_refusals)
    observations = json.loads(arguments.observations.read_text(encoding='utf8')) if arguments.observations else None
    try:
        while True:
            for bundle in arguments.bundle:
                record = {} if arguments.save_observations else None
                one_reading(bundle, arguments, observations, dev_rate, record)
                if record is not None:
                    arguments.save_observations.write_text(json.dumps(record, indent=1, sort_keys=True) + '\n', encoding='utf8')
            if not arguments.watch:
                return 0
            sys.stdout.flush()
            time.sleep(arguments.watch)
    except SealedRefusal as refusal:
        print(str(refusal))
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
