"""SessionStart hook: tell a new or resumed lead session that a loop is in progress.

If ``docs/loop/private/LOOP_STATE.md`` exists and its status is not DONE, prints the notice,
this session's id (from the hook's own JSON input), the standing orders with the last check's
result (D-S110 item 3a), the full state file and the newest handoff. `--orders` prints the
standing orders alone, for a lane or a checker at its own start. Claude Code adds this output to the session's context. Loop machinery, not
product code.
"""
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / 'docs' / 'loop' / 'private'
NOTICE = ('A Shimmer loop is in progress. If you are the lead session started by Seckin in the '
          'main checkout, read `prompts/SHIMMER_AUTONOMOUS_LOOP_2026-10-27.md`, then '
          '`docs/loop/private/LOOP_STATE.md`, then the newest file in `docs/loop/private/handoff/`, '
          'before anything else. Otherwise ignore this.')
TABLET = 'STANDING_ORDERS.md'
LAST_CHECK = 'standing_orders_last.json'


def compact_reminder(state):
    """D-S36: first in the output, since a long hook output is shown by its opening only. The
    rule lives in the private folder; without it a fixed line says the same."""
    try:
        spec = importlib.util.spec_from_file_location('continue_hook', PRIVATE / 'continue_hook.py')
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        return 'A compaction is never a stopping point. ' + hook.reminder(state)
    except Exception:
        return 'A compaction is never a stopping point: continue from the NEXT line of LOOP_STATE.'


COUNT_LABELS = (('kept', 'kept'), ('kept_in_part', 'kept in part'), ('code_only', 'code proven, not the order'),
                ('nothing_yet', 'nothing to check yet'), ('broken', 'broken'), ('not_built', 'check not built'),
                ('unable', 'unable to check'), ('unchecked', 'not checked by code'), ('withdrawn', 'withdrawn'))
STALE_HOURS = 24


def stale_reasons(last, tablet_text, now=None):
    """Why the last result no longer stands (D-430, F4): over 24 hours old, or the tablet changed."""
    out = []
    try:
        when = datetime.fromisoformat(str(last.get('time_utc')).replace('Z', '+00:00'))
        age = ((now or datetime.now(timezone.utc)) - when).total_seconds() / 3600
        if age > STALE_HOURS:
            out.append('the result is %.1f hours old (at most %d)' % (age, STALE_HOURS))
    except (TypeError, ValueError):
        out.append('the result has no readable time')
    if last.get('tablet_sha256') != hashlib.sha256(tablet_text.encode('utf-8')).hexdigest():
        out.append('the tablet changed since the result was written')
    return out


def standing_orders_block(private=None):
    """D-S110 item 3a: the tablet's orders, one line each, and the last check's result, for the
    lead, every lane and every checker at session start. Never raises: an absent or unreadable
    tablet or result is said so."""
    private = Path(private) if private else PRIVATE
    lines = ['## Standing orders (D-S110): kept or broken at every moment']
    try:
        text = (private / TABLET).read_text(encoding='utf-8')
    except OSError:
        return '\n'.join(lines + ['The tablet (%s) cannot be read.' % TABLET])
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if line.lstrip().startswith('|') and len(cells) >= 2 and cells[0].isdigit():
            lines.append('%s. %s' % (cells[0], cells[1]))
    try:
        last = json.loads((private / LAST_CHECK).read_text(encoding='utf-8'))
        counts = last.get('counts') or {}
        said = ', '.join('%s %s' % (counts.get(key, 0), label) for key, label in COUNT_LABELS if key in counts)
        lines.append('Last check (tools/loop/standing_orders_check.py) at %s: %s, %d unreadable.' % (
            last.get('time_utc'), said, len(last.get('unreadable') or [])))
        stale = stale_reasons(last, text)
        if stale:
            lines.append('STALE: ' + '; '.join(stale) + '. Run tools/loop/standing_orders_check.py again.')
        shown = [o['line'] for o in last.get('orders') or [] if o.get('state') in ('broken', 'unable')]
        lines.extend('  ' + b for b in shown)
    except (OSError, ValueError, AttributeError):
        lines.append('No standing-orders check result yet: run tools/loop/standing_orders_check.py.')
    return '\n'.join(lines)


def main():
    if '--orders' in sys.argv[1:]:
        print(standing_orders_block())
        return 0
    try:
        data = json.loads(sys.stdin.buffer.read().decode('utf-8-sig') or '{}')
    except ValueError:
        data = {}
    state = PRIVATE / 'LOOP_STATE.md'
    if not state.exists():
        return 0
    text = state.read_text(encoding='utf-8')
    if '- Status: DONE' in text:
        return 0
    if data.get('source') == 'compact':
        print(compact_reminder(text))
        print()
    print(standing_orders_block())
    print()
    print(NOTICE)
    print()
    print('This session id: {}'.format(data.get('session_id') or 'unknown'))
    print()
    print('## LOOP_STATE.md')
    print(text)
    handoffs = sorted((PRIVATE / 'handoff').glob('*.md'), key=lambda p: p.stat().st_mtime)
    if handoffs:
        print('## Newest handoff: ' + handoffs[-1].name)
        print(handoffs[-1].read_text(encoding='utf-8'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
