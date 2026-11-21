#!/usr/bin/env python3
"""The chain board (D-916): one read-only picture of the Claude-free chain for a supervising chat.

Writes docs/loop/private/CHAIN_BOARD.json and CHAIN_BOARD.md (temp file then os.replace). It reads the launch
folders named in config/chain_board.json (chain.json, or chain.json.held when not armed), reuses launch_chain's
step model and status logic, and gives each step one of: pending, ready, running, done, failed, held.
Hand-back files are checked by existence, size and modification time only; no file under them is ever opened.
It never launches, stops or deletes anything. Run every 5 minutes by a Windows task (pyw).

overall: failed (a stop file, FREEZE_REFUSED or a failed step), else done (every `final` file present), else
running (a step running or launching), else idle.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import launch_chain as lc  # noqa: E402
import mechanism_common as mc  # noqa: E402

CONFIG = HERE.parents[1] / 'config' / 'chain_board.json'
MAP = {'done': 'done', 'running': 'running', 'launching': 'running', 'failed': 'failed', 'ready': 'ready',
       'held': 'held', 'unconfirmed': 'held', 'pending': 'pending', 'waiting': 'pending', 'unknown': 'pending'}


def load_config(path=None):
    return json.loads(Path(path or CONFIG).read_text(encoding='utf-8'))


def stat_line(path):
    """Existence, size and modification time of one path; nothing is opened."""
    try:
        st = os.stat(path)
    except OSError:
        return {'exists': False}
    return {'exists': True, 'size': st.st_size, 'modified': mc.iso(mc.dt.datetime.fromtimestamp(st.st_mtime).astimezone())}


def watch(entry, main):
    """One watched entry: the pattern's matches (a * name is listed with os.scandir, never opened)."""
    p = Path(entry['path'])
    p = p if p.is_absolute() else Path(main) / p
    files = []
    if '*' in p.name:
        try:
            with os.scandir(p.parent) as it:
                names = sorted(e.name for e in it if Path(e.name).match(p.name))
        except OSError:
            names = []
        files = [{'file': n, **stat_line(p.parent / n)} for n in names]
    else:
        s = stat_line(p)
        if s['exists']:
            files = [{'file': p.name, **s}]
    return {'name': entry['name'], 'role': entry.get('role', 'info'), 'present': bool(files), 'files': files}


def load_steps(folder):
    """(chain or None, armed): chain.json is armed, chain.json.held is not."""
    folder = Path(folder)
    chain = lc.load_chain(folder)
    if chain is not None:
        return chain, True
    held = folder / 'chain.json.held'
    if not held.is_file():
        return None, False
    tmp_chain = json.loads(held.read_text(encoding='utf-8'))
    # the same checks load_chain makes, on the held text (purposes filled in), without writing anything
    purposes = lc.launch_purposes(folder)
    for s in tmp_chain.get('steps', []):
        if s.get('kind') == 'ledger':
            lc.check_ledger_step(s, tmp_chain['steps'], purposes)
    return tmp_chain, False


def last_launch_row(rows, purpose):
    own = [r for r in rows if purpose and r.get('purpose') == purpose and r.get('event') in ('launch', 'termination')]
    return own[-1] if own else None


def folder_board(folder, trace, rows, t, status_fn):
    name = Path(folder).name
    try:
        chain, armed = load_steps(folder)
    except (lc.ChainError, OSError, ValueError, KeyError, TypeError) as exc:
        return {'folder': name, 'error': '%s: %s' % (type(exc).__name__, exc), 'steps': []}
    if chain is None:
        return {'folder': name, 'error': 'no chain.json or chain.json.held', 'armed': False, 'steps': []}
    status, status_error = {}, ''
    if any(s['kind'] == 'ledger' for s in chain['steps']):
        try:
            status = status_fn(folder)
        except Exception as exc:  # noqa: BLE001 - a unreadable status shows as unknown steps, never stops the board
            status_error = '%s: %s' % (type(exc).__name__, str(exc)[:160])
    states = lc.evaluate(folder, chain, status, trace, t, rows=rows)
    steps = []
    for step in chain['steps']:
        row = states[step['step']]
        state = MAP.get(row['state'], 'pending')
        why = row['why']
        if not armed and state != 'done':
            state, why = 'held', 'not armed (chain.json.held); ' + why
        purpose = step.get('purpose')
        launch = last_launch_row(rows, purpose)
        acts = [x for x in trace if x.get('mechanism') == lc.NAME and x.get('folder') == name and x.get('step') == step['step']]
        s_row = status.get(step['step'])
        steps.append({'step': step['step'], 'kind': step['kind'], 'state': state, 'why': why,
                      'last_trace': acts[-1]['time'] if acts else None,
                      'spend_usd': s_row['cost'] if s_row else None,
                      'deadline': launch.get('deadline_utc') if launch and launch.get('event') == 'launch' else None})
    out = {'folder': name, 'armed': armed, 'steps': steps}
    if status_error:
        out['status_error'] = status_error
    return out


def build(config, main=None, trace=None, rows=None, t=None, status_fn=None, root=None):
    main = Path(main or mc.MAIN)
    root = Path(root or main / 'external' / 's05')
    t = t or mc.now()
    trace = mc.read_trace() if trace is None else trace
    rows = lc.read_ledger() if rows is None else rows
    status_fn = status_fn or lc.read_status
    folders = [folder_board(root / n, trace, rows, t, status_fn) for n in config['folders']]
    watched = [watch(e, main) for e in config['watched']]
    steps = [s for f in folders for s in f['steps']]
    stops = [w['name'] for w in watched if w['role'] == 'stop' and w['present']]
    finals = [w for w in watched if w['role'] == 'final']
    failed_steps = ['%s:%s' % (f['folder'], s['step']) for f in folders for s in f['steps'] if s['state'] == 'failed']
    reasons = ['%s present' % n for n in stops] + ['%s failed' % n for n in failed_steps]
    if reasons:
        overall = 'failed'
    elif finals and all(w['present'] for w in finals):
        overall = 'done'
    elif any(s['state'] == 'running' for s in steps):
        overall = 'running'
    else:
        overall = 'idle'
    return {'written': mc.iso(t), 'overall': overall, 'overall_reasons': reasons, 'folders': folders, 'watched': watched}


def render_md(board):
    lines = ['# CHAIN BOARD', '', 'Written %s. Overall: %s%s' % (
        board['written'], board['overall'], (' (%s)' % '; '.join(board['overall_reasons'])) if board['overall_reasons'] else ''), '']
    for f in board['folders']:
        lines.append('## %s%s' % (f['folder'], '' if f.get('armed', True) else ' (not armed)'))
        if f.get('error'):
            lines.append('- error: %s' % f['error'])
        for s in f['steps']:
            spend = '' if s['spend_usd'] is None else ', %.3f USD' % s['spend_usd']
            dl = ', deadline %s' % s['deadline'] if s['deadline'] else ''
            lines.append('- %s: %s%s%s (last trace %s)' % (s['step'], s['state'], spend, dl, s['last_trace'] or 'none'))
        lines.append('')
    lines.append('## Hand-back files')
    for w in board['watched']:
        for f in (w['files'] or [None]):
            lines.append('- %s: %s' % (w['name'], ('%s, %d bytes, %s' % (f['file'], f['size'], f['modified'])) if f else 'absent'))
    return '\n'.join(lines) + '\n'


def write_atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.writing')
    tmp.write_text(text, encoding='utf-8', newline='\n')
    os.replace(tmp, path)


def write_board(board, private=None):
    private = Path(private or mc.PRIVATE)
    write_atomic(private / 'CHAIN_BOARD.json', json.dumps(board, indent=1, sort_keys=True) + '\n')
    write_atomic(private / 'CHAIN_BOARD.md', render_md(board))


def main(argv=None):
    board = build(load_config())
    write_board(board)
    print('chain board: %s' % board['overall'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
