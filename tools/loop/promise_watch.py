"""Promise watch, run by the watchdog (Seckin 18 November 2026 21:46, SUPERVISOR_INBOX: nothing silently waits).

    py -3.12 -X utf8 tools/loop/promise_watch.py               # one check, one trace line, the result on screen
    py -3.12 -X utf8 tools/loop/promise_watch.py ready         # every planned step ready but not launched or not running
    py -3.12 -X utf8 tools/loop/promise_watch.py add --step S --owner lead --expected-start ISO [--folder F]
        [--chain-step X] [--purpose P] [--role-session "N S41" --exit-file n41_exit.txt] [--needs PATH ...]
        [--output GLOB ...] [--output-lines PATH:N ...] [--needs-exit EXIT_FILE ...] [--needs-any-exit F1,F2] [--note TEXT]
    py -3.12 -X utf8 tools/loop/promise_watch.py close --step S --why TEXT

docs/loop/private/PLANNED_STEPS.jsonl holds one line per planned step (the lead appends with `add`; a later line for
the same step replaces the earlier one, a `close` line ends it): {step, owner, folder (a launch folder under
external/s05) or role_session (with exit_file in docs/loop/private/role_starts, named bare or by that path), needs (outputs it waits for),
expected_start, expected_output (path globs, or {path, min_lines}), since (optional: chain and ledger evidence older
than it is ignored, so an earlier attempt of the same step does not count)}. A relative path resolves inside the step's
launch folder when it names one, else inside the main checkout. Each run compares the plan with the launch chain's
trace lines (mechanism launch_chain, by folder and chain step), the budget ledger (by purpose) and the role exit
files, and writes one ALERT.md line once per cause for:

  late          a step past expected_start + 5 minutes with no launch and no output;
  failed        a failed launch (launch_failed, or rc != 0) not followed by a new launch within 5 minutes;
  role_gap      a role session whose exit file shows its exit while its expected_output does not exist.

Role outputs are checked by existence only; no file in a role folder is ever opened (standing order 110: read,
record and alert only). An unforeseen state (a plan line that is not JSON, lacks a declared field or carries an
unreadable time) does nothing else: one ALERT line, a trace line with result stopped, and the check ends.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mechanism_common as mc  # noqa: E402

NAME = 'promise_watch'
ONCE = 10 ** 9          # once per cause


class Unforeseen(Exception):
    pass


def config_path():
    return Path(__file__).resolve().parents[2] / 'config' / 'promise_watch.json'


def load_config(path=None):
    return json.loads(Path(path or config_path()).read_text(encoding='utf-8'))


def parse_time(text):
    try:
        t = dt.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.astimezone()


def read_jsonl(path):
    out = []
    try:
        with open(path, encoding='utf-8') as f:
            for raw in f:
                raw = raw.strip()
                if raw:
                    try:
                        out.append(json.loads(raw))
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def validate(line, cfg):
    """The reason a plan line cannot be read, or None."""
    if not isinstance(line, dict) or not isinstance(line.get('step'), str) or not line['step']:
        return 'no step name'
    if line.get('closed'):
        return None
    missing = [k for k in cfg['required_fields'] if k not in line]
    if missing:
        return 'missing %s' % ','.join(missing)
    if parse_time(line['expected_start']) is None:
        return 'expected_start %r is not an ISO time' % (line['expected_start'],)
    if line.get('since') is not None and parse_time(line['since']) is None:
        return 'since %r is not an ISO time' % (line['since'],)
    if not isinstance(line['needs'], list) or not isinstance(line['expected_output'], list):
        return 'needs and expected_output must be lists'
    for out in line['expected_output']:
        if not valid_entry(out):
            return 'an expected_output entry is neither a glob nor {path, min_lines}'
    for need in line['needs']:
        if not valid_entry(need, need=True):
            return 'a needs entry is neither a glob, {path, min_lines}, {exit_line} nor {any: [...]}'
    if line.get('role_session') and not line.get('exit_file'):
        return 'a role session names no exit_file'
    return None


def read_plan(path, cfg):
    """{step: its newest line} in first-seen order; Unforeseen on any unreadable line."""
    plan = {}
    try:
        text = Path(path).read_text(encoding='utf-8')
    except FileNotFoundError:
        return plan
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            line = json.loads(raw)
        except ValueError:
            raise Unforeseen('line %d is not JSON' % n)
        why = validate(line, cfg)
        if why:
            raise Unforeseen('line %d: %s' % (n, why))
        if line.get('closed'):
            plan.pop(line['step'], None)
        else:
            plan.pop(line['step'], None)
            plan[line['step']] = line
    return plan


def resolve(path, step, cfg, main):
    p = Path(path)
    if p.is_absolute():
        return p
    if step.get('folder'):
        return Path(main) / cfg['launch_root'] / step['folder'] / p
    return Path(main) / p


def valid_entry(entry, need=False):
    """A glob, {path, min_lines}, or for a need also {exit_line: exit file} and {any: [needs]}."""
    if isinstance(entry, str):
        return True
    if not isinstance(entry, dict):
        return False
    if isinstance(entry.get('path'), str) and isinstance(entry.get('min_lines'), int):
        return True
    if need and isinstance(entry.get('exit_line'), str):
        return True
    return need and isinstance(entry.get('any'), list) and bool(entry['any']) and all(
        valid_entry(x, need=True) for x in entry['any'])


def exit_path(name, exit_dir, cfg, main):
    """An exit file named bare (n41_exit.txt) lives in the exit folder; one named by its path from the main checkout
    (docs/loop/private/role_starts/n41_exit.txt) also lands there, never in the exit folder twice over; any other
    relative path resolves inside the main checkout, an absolute one stays as it is."""
    p = Path(str(name).replace('\\', '/'))
    if p.is_absolute():
        return p
    prefix = tuple(x.lower() for x in Path(cfg['role_exit_dir']).parts)
    parts = p.parts
    if tuple(x.lower() for x in parts[:len(prefix)]) == prefix:
        return Path(exit_dir).joinpath(*parts[len(prefix):])
    if len(parts) > 1:
        return Path(main) / p
    return Path(exit_dir) / p


def has_exit_line(name, cfg, main):
    """The lead's own exit file (written by the start .cmd) holds an exit line."""
    exit_dir = Path(cfg['_exit_dir']) if cfg.get('_exit_dir') else Path(main) / cfg['role_exit_dir']
    try:
        lines = exit_path(name, exit_dir, cfg, main).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return False
    return any(x.strip().startswith('exit') for x in lines)


def need_label(entry):
    if isinstance(entry, str):
        return entry
    if 'exit_line' in entry:
        return 'an exit line in %s' % entry['exit_line']
    if 'any' in entry:
        return 'one of (%s)' % ' or '.join(need_label(x) for x in entry['any'])
    return '%s with %d lines' % (entry['path'], entry['min_lines'])


def exists(entry, step, cfg, main):
    """Existence only (glob over names); a {path, min_lines} entry counts the lines of a file the lead owns; a need
    may also be {exit_line: exit file in role_starts} or {any: [needs]} (one of them holds)."""
    if isinstance(entry, dict) and 'exit_line' in entry:
        return has_exit_line(entry['exit_line'], cfg, main)
    if isinstance(entry, dict) and 'any' in entry:
        return any(exists(x, step, cfg, main) for x in entry['any'])
    if isinstance(entry, dict):
        target = resolve(entry['path'], step, cfg, main)
        try:
            with open(target, encoding='utf-8', errors='replace') as f:
                return sum(1 for _ in f) >= entry['min_lines']
        except OSError:
            return False
    return bool(glob.glob(str(resolve(entry, step, cfg, main))))


def done(step, cfg, main):
    outs = step['expected_output']
    return bool(outs) and all(exists(o, step, cfg, main) for o in outs)


def missing_needs(step, cfg, main):
    return [n for n in step['needs'] if not exists(n, step, cfg, main)]


def chain_events(step, trace, cfg):
    """[(time, 'launched'|'failed')] for this step's folder and chain step, oldest first."""
    if not step.get('folder'):
        return []
    name = step.get('chain_step') or step['step']
    since = parse_time(step.get('since')) if step.get('since') else None
    out = []
    for x in trace:
        if x.get('mechanism') != 'launch_chain' or x.get('folder') != step['folder'] or x.get('step') != name:
            continue
        t = parse_time(x.get('time'))
        if t is None or (since and t < since):
            continue
        rc = x.get('rc')
        if x.get('result') in cfg['failed_results'] or (isinstance(rc, int) and rc != 0):
            out.append((t, 'failed'))
        elif x.get('result') in cfg['launched_results']:
            out.append((t, 'launched'))
    return sorted(out)


def ledger_launched(step, ledger, cfg):
    purpose = step.get('purpose')
    since = parse_time(step.get('since')) if step.get('since') else None
    return bool(purpose) and any(x.get('purpose') == purpose and x.get('event') in cfg['ledger_launch_events']
                                 and not (since and (parse_time(x.get('time_utc')) or since) < since) for x in ledger)


def role_exit(step, exit_dir, cfg=None, main=None):
    """(started, exited, exit file mtime) from the lead's own exit file (written by the start .cmd)."""
    if not step.get('role_session'):
        return False, False, None
    path = exit_path(step['exit_file'], exit_dir, cfg or load_config(), main or mc.MAIN)
    try:
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        mtime = dt.datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    except OSError:
        return False, False, None
    started = any(x.strip().startswith('start') for x in lines)
    exited = any(x.strip().startswith('exit') for x in lines)
    return started or exited, exited, mtime


def is_late(now, start, minutes):
    return (now - start).total_seconds() > 60 * minutes


def assess(step, now, cfg, main, trace, ledger, exit_dir):
    """The step's state and its causes [(kind, key, text)]."""
    is_done = done(step, cfg, main)
    events = chain_events(step, trace, cfg)
    started, exited, exit_mtime = role_exit(step, exit_dir, cfg, main)
    launched = bool([e for e in events if e[1] == 'launched']) or ledger_launched(step, ledger, cfg) or started
    causes = []
    start = parse_time(step['expected_start'])
    label = step['step']
    if not is_done and not launched and not events and is_late(now, start, cfg['late_minutes']):
        need = missing_needs(step, cfg, main)
        causes.append(('late', 'promise:late:%s:%s' % (label, step['expected_start']),
                       'Planned step late: %s (owner %s) expected to start %s, no launch after %d minutes%s.'
                       % (label, step['owner'], start.strftime('%H:%M'), cfg['late_minutes'],
                          '; waiting for %s' % ', '.join(need_label(n) for n in need) if need else '; every need exists')))
    failures = [t for t, kind in events if kind == 'failed']
    failed_open = False
    if failures and not is_done:
        last_fail = failures[-1]
        relaunched = any(kind == 'launched' and t > last_fail for t, kind in events)
        if not relaunched:
            failed_open = True
            if is_late(now, last_fail, cfg['relaunch_minutes']):
                causes.append(('failed', 'promise:failed:%s:%s' % (label, last_fail.isoformat()),
                               'Planned step failed and not launched again: %s (folder %s) failed at %s, no new '
                               'launch within %d minutes; read mechanism_trace.jsonl (launch_chain).'
                               % (label, step['folder'], last_fail.strftime('%H:%M'), cfg['relaunch_minutes'])))
    if exited and not is_done:
        causes.append(('role_gap', 'promise:role_gap:%s:%s' % (label, exit_mtime.isoformat()),
                       'Role session ended without its output: %s (%s) exit file %s shows exit at %s, expected output '
                       'missing: %s.' % (label, step['role_session'], step['exit_file'], exit_mtime.strftime('%H:%M'),
                                         ', '.join(str(o if isinstance(o, str) else o['path'])
                                                   for o in step['expected_output']
                                                   if not exists(o, step, cfg, main)))))
    if is_done:
        state = 'done'
    elif exited:
        state = 'exited_without_output'
    elif failed_open:
        state = 'failed'
    elif launched:
        state = 'running'
    else:
        state = 'not_launched'
    return state, causes


def context(cfg, main, private):
    main = Path(main or mc.MAIN)
    priv = Path(private) if private else None
    plan_file = priv / Path(cfg['planned_file']).name if priv else main / cfg['planned_file']
    ledger = priv / Path(cfg['ledger']).name if priv else main / cfg['ledger']
    exit_dir = priv / 'role_starts' if priv else main / cfg['role_exit_dir']
    cfg['_exit_dir'] = str(exit_dir)
    return main, plan_file, ledger, exit_dir


def check(now=None, cfg=None, main=None, private=None):
    """The plan against the evidence, the alerts and one trace line; returns the trace line's details."""
    now = now or mc.now()
    cfg = cfg or load_config()
    main, plan_file, ledger_file, exit_dir = context(cfg, main, private)
    try:
        plan = read_plan(plan_file, cfg)
    except Unforeseen as exc:
        digest = hashlib.sha256(str(exc).encode('utf-8')).hexdigest()[:12]
        mc.alert('promise:unforeseen:%s' % digest, 'Promise watch stopped, nothing checked: %s cannot be read (%s). '
                 'A model must look.' % (Path(plan_file).name, exc), every=ONCE)
        mc.trace(NAME, 'stopped', why=str(exc))
        return {'result': 'stopped', 'why': str(exc), 'causes': [], 'states': {}}
    trace, ledger = mc.read_trace(), read_jsonl(ledger_file)
    states, found = {}, []
    for name, step in plan.items():
        state, causes = assess(step, now, cfg, main, trace, ledger, exit_dir)
        states[name] = state
        for kind, key, text in causes:
            found.append({'step': name, 'kind': kind})
            mc.alert(key, text, every=ONCE)
    result = 'alert' if found else 'ok'
    mc.trace(NAME, result, causes=found, states=states)
    return {'result': result, 'causes': found, 'states': states}


def ready(now=None, cfg=None, main=None, private=None):
    """[(step, reason)] for every step whose needs all exist but which is not launched or not running."""
    now = now or mc.now()
    cfg = cfg or load_config()
    main, plan_file, ledger_file, exit_dir = context(cfg, main, private)
    plan = read_plan(plan_file, cfg)
    trace, ledger = mc.read_trace(), read_jsonl(ledger_file)
    out = []
    for name, step in plan.items():
        state, _ = assess(step, now, cfg, main, trace, ledger, exit_dir)
        if state == 'exited_without_output':       # reported whatever its needs: the session already ran
            out.append((name, 'role session ended without output (%s, exit file %s)' % (
                step['role_session'], step['exit_file'])))
            continue
        if missing_needs(step, cfg, main):
            continue
        if state == 'not_launched':
            start = parse_time(step['expected_start'])
            out.append((name, 'ready, not launched (expected %s, %s)' % (
                start.strftime('%H:%M'), 'late' if start < now else 'not yet due')))
        elif state == 'failed':
            out.append((name, 'ready, its last launch failed and none followed'))
    return out


def plan_line(args, now):
    line = {'step': args.step, 'owner': args.owner, 'needs': (args.needs or []) + [
                {'exit_line': x} for x in args.needs_exit or []] + [
                {'any': [{'exit_line': y} for y in x.split(',')]} for x in args.needs_any_exit or []],
            'expected_start': args.expected_start or mc.iso(now),
            'expected_output': (args.output or []) + [
                {'path': x.rsplit(':', 1)[0], 'min_lines': int(x.rsplit(':', 1)[1])} for x in args.output_lines or []],
            'added': mc.iso(now)}
    for key in ('folder', 'chain_step', 'purpose', 'role_session', 'exit_file', 'since', 'note'):
        if getattr(args, key):
            line[key] = getattr(args, key)
    return line


def append(path, line):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(line, ensure_ascii=False) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd')
    sub.add_parser('check')
    sub.add_parser('ready')
    add = sub.add_parser('add')
    add.add_argument('--step', required=True)
    add.add_argument('--owner', required=True)
    add.add_argument('--expected-start')
    for key in ('--folder', '--chain-step', '--purpose', '--role-session', '--exit-file', '--since', '--note'):
        add.add_argument(key)
    add.add_argument('--needs', action='append')
    add.add_argument('--output', action='append')
    add.add_argument('--output-lines', action='append')
    add.add_argument('--needs-exit', action='append')
    add.add_argument('--needs-any-exit', action='append')
    close = sub.add_parser('close')
    close.add_argument('--step', required=True)
    close.add_argument('--why', required=True)
    args = ap.parse_args(argv)
    cfg = load_config()
    plan_file = Path(mc.MAIN) / cfg['planned_file']
    if args.cmd == 'add':
        line = plan_line(args, mc.now())
        why = validate(line, cfg)
        if why:
            print('REFUSED %s' % why)
            return 2
        append(plan_file, line)
        print('ADDED %s' % json.dumps(line, ensure_ascii=False))
        return 0
    if args.cmd == 'close':
        append(plan_file, {'step': args.step, 'closed': mc.iso(), 'why': args.why})
        print('CLOSED %s' % args.step)
        return 0
    if args.cmd == 'ready':
        try:
            rows = ready(cfg=cfg)
        except Unforeseen as exc:
            print('STOPPED %s cannot be read (%s)' % (plan_file.name, exc))
            return 3
        print('READY %d step(s) ready but not launched or not running (%s)' % (len(rows), mc.iso()))
        for name, why in rows:
            print('  %s: %s' % (name, why))
        return 0
    print(json.dumps(check(cfg=cfg), indent=1, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
