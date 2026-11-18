"""Proofs for the session hooks (audit H, 18 November 2026). Loop machinery, not product code.

1. continue_hook.reminder names the TOPMOST NEXT line of LOOP_STATE (the newest block is first).
2. session_start's output stays under a cap and puts the state before the standing orders.
Run: py -3.12 -X utf8 tools/loop/session_hook_checks.py   (exit 0 when both pass)
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_reminder():
    hook = load('continue_hook', ROOT / 'docs' / 'loop' / 'private' / 'continue_hook.py')
    state = ('## CURRENT (new)\n- Status: RUNNING\n- NEXT: the current step\n\n'
             '## CURRENT (old)\n- NEXT: a step from weeks ago\n')
    text = hook.reminder(state)
    return 'the current step' in text and 'weeks ago' not in text


def check_cap():
    ss = load('session_start', ROOT / 'tools' / 'loop' / 'session_start.py')
    big = 'x' * 50000
    out = ss.capped(big, 1000, 'some/file.md')
    return len(out) < 1200 and 'some/file.md' in out and ss.capped('short', 1000, 'f') == 'short'


def check_expired_cutoff():
    """A cut-off more than 12 hours past lets no stop through; one an hour past still does with a fresh handoff."""
    import datetime
    hook = load('continue_hook', ROOT / 'docs' / 'loop' / 'private' / 'continue_hook.py')
    fixed = datetime.datetime(2026, 11, 18, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
    hook.now = lambda: fixed
    hook.rules = lambda: {'cutoff': '2026-11-17T03:00:00+03:00'}
    expired = hook.cutoff_state() is None
    hook.rules = lambda: {'cutoff': '2026-11-18T11:00:00+03:00'}
    recent = hook.cutoff_state() is not None
    return expired and recent


def check_start_files_effort():
    """No role start file asks for maximum or high effort (standing order 104)."""
    import re
    folder = ROOT / 'docs' / 'loop' / 'private' / 'role_starts'
    bad = [p.name for p in folder.glob('start_*.cmd')
           if re.search(r'(?i)(--effort\s+(max|high)\b|EFFORT_LEVEL=(max|high)\b)', p.read_text(errors='replace'))]
    if bad:
        print('start files above medium: ' + ', '.join(bad))
    return not bad


def main():
    results = {'reminder_takes_topmost_next': check_reminder(), 'output_capped': check_cap(),
               'expired_cutoff_lets_nothing_through': check_expired_cutoff(),
               'start_files_at_medium': check_start_files_effort()}
    for k, v in results.items():
        print('%s: %s' % (k, 'PASS' if v else 'FAIL'))
    return 0 if all(results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
