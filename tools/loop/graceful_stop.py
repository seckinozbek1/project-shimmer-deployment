#!/usr/bin/env python3
"""Graceful stop of the Claude-free chain (D-916): disable the tasks that START new work, leave the rest running.

    py -3.12 -X utf8 tools/loop/graceful_stop.py              # dry run: prints what it would do, changes nothing
    py -3.12 -X utf8 tools/loop/graceful_stop.py --execute    # disables the `stop` tasks of config/graceful_stop.json
    py -3.12 -X utf8 tools/loop/graceful_stop.py --resume     # re-enables exactly the tasks GRACEFUL_STOP.json disabled

Only `schtasks /query` and `schtasks /change /tn <name> /disable|/enable` are ever run. It never kills a process,
never ends an instance (a running machine is left to its deadline and the reaper) and never touches a tag or a
staged bundle. Idempotent: a task already disabled is not touched, and a second --execute changes nothing.
GRACEFUL_STOP.json records the time, each task it disabled with its prior state, the open ledger launches and a
re-enable command per task; one line goes to the top of ALERT.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mechanism_common as mc  # noqa: E402

CONFIG = HERE.parents[1] / 'config' / 'graceful_stop.json'
RECORD = 'GRACEFUL_STOP.json'


def real_runner(args):
    """(exit code, stdout) of schtasks with the given arguments; no window."""
    done = subprocess.run(['schtasks'] + list(args), capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          creationflags=mc.no_window())
    return done.returncode, done.stdout or ''


def load_config(path=None):
    return json.loads(Path(path or CONFIG).read_text(encoding='utf-8'))


def task_state(name, runner):
    """'Ready', 'Running', 'Disabled', ... or None when the task is not found."""
    rc, out = runner(['/query', '/tn', name, '/fo', 'csv', '/nh'])
    if rc != 0 or not out.strip():
        return None
    cells = [c.strip().strip('"') for c in out.strip().splitlines()[0].split('","')]
    return cells[2].strip('"') if len(cells) >= 3 else None


def open_launches(rows):
    """Ledger launches with no later termination of the same instance: (instance name, deadline)."""
    open_ = {}
    for r in rows:
        key = r.get('instance_name')
        if r.get('event') == 'launch' and key:
            open_[key] = r.get('deadline_utc')
        elif r.get('event') == 'termination' and key:
            open_.pop(key, None)
    return [{'instance_name': k, 'deadline_utc': v} for k, v in open_.items()]


def read_rows(private):
    out = []
    try:
        with open(Path(private) / 'budget_ledger.jsonl', encoding='utf-8') as f:
            for raw in f:
                try:
                    out.append(json.loads(raw))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def read_record(private):
    try:
        return json.loads((Path(private) / RECORD).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def write_record(private, record):
    path = Path(private) / RECORD
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.writing')
    tmp.write_text(json.dumps(record, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, path)


def enable_cmd(name):
    return 'schtasks /change /tn %s /enable' % name


def stop(config, runner, private, execute, alert=None, out=print):
    """Returns the list of tasks disabled by this call."""
    alert = alert or mc.alert
    record = read_record(private)
    active = record if record and record.get('status') == 'stopped' else None
    ours = {d['task']: d for d in (active or {}).get('disabled', [])}
    changes, notes = [], []
    for name in config['stop']:
        state = task_state(name, runner)
        if state is None:
            notes.append('%s: not found' % name)
        elif state.lower() == 'disabled':
            notes.append('%s: already disabled%s' % (name, ' (by this tool)' if name in ours else ', left as it is'))
        else:
            changes.append({'task': name, 'prior_state': state, 're_enable': enable_cmd(name)})
    for name in config.get('keep', []):
        notes.append('%s: kept running (not touched)' % name)
    for c in changes:
        out('%s %s: disable (now %s)' % ('DISABLE' if execute else 'would disable', c['task'], c['prior_state']))
    for n in notes:
        out(n)
    if not execute:
        out('dry run: nothing changed')
        return []
    done = []
    for c in changes:
        rc, _ = runner(['/change', '/tn', c['task'], '/disable'])
        if rc == 0:
            done.append(c)
        else:
            out('FAILED to disable %s (exit %s)' % (c['task'], rc))
    if done:
        disabled = list(ours.values()) + done
        write_record(private, {'status': 'stopped', 'time': mc.iso(), 'disabled': disabled, 'kept': config.get('keep', []),
                               'open_launches': open_launches(read_rows(private))})
        alert('graceful_stop', 'GRACEFUL STOP: disabled %s; running machines left to their deadlines and the reaper; '
              'tools/loop/graceful_stop.py --resume re-enables them' % ', '.join(c['task'] for c in done), every=0)
    return done


def resume(runner, private, out=print):
    record = read_record(private)
    if not record or record.get('status') != 'stopped':
        out('nothing to resume: no active GRACEFUL_STOP.json')
        return []
    done = []
    for d in record['disabled']:
        rc, _ = runner(['/change', '/tn', d['task'], '/enable'])
        out('%s %s' % ('re-enabled' if rc == 0 else 'FAILED to re-enable', d['task']))
        if rc == 0:
            done.append(d['task'])
    record['status'] = 'resumed' if len(done) == len(record['disabled']) else 'stopped'
    record['disabled'] = [d for d in record['disabled'] if d['task'] not in done]
    record.setdefault('resumed', []).extend(done)
    record['resumed_at'] = mc.iso()
    write_record(private, record)
    return done


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if any(a not in ('--execute', '--resume') for a in argv) or set(argv) == {'--execute', '--resume'}:
        print('usage: graceful_stop.py [--execute | --resume]')
        return 2
    if '--resume' in argv:
        resume(real_runner, mc.PRIVATE)
    else:
        stop(load_config(), real_runner, mc.PRIVATE, '--execute' in argv)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
