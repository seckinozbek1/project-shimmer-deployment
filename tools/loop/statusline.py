"""Claude Code status line for the loop: record context and usage figures, print one line.

Claude Code runs this with a JSON object on standard input. It writes
``.claude/loop_status.json`` (UTC time, session id, the context fields and the rate-limit
fields; any of them may be null early in a session) and prints a short line. Loop
machinery, not product code.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.claude' / 'loop_status.json'


def pick(data, *path):
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode('utf-8-sig') or '{}')
    except ValueError:
        data = {}
    record = {
        'time_utc': datetime.now(timezone.utc).isoformat(),
        'session_id': data.get('session_id'),
        'context_used_percentage': pick(data, 'context_window', 'used_percentage'),
        'context_remaining_percentage': pick(data, 'context_window', 'remaining_percentage'),
        'context_window_size': pick(data, 'context_window', 'context_window_size'),
        'five_hour_used_percentage': pick(data, 'rate_limits', 'five_hour', 'used_percentage'),
        'five_hour_resets_at': pick(data, 'rate_limits', 'five_hour', 'resets_at'),
        'seven_day_used_percentage': pick(data, 'rate_limits', 'seven_day', 'used_percentage'),
        'seven_day_resets_at': pick(data, 'rate_limits', 'seven_day', 'resets_at'),
    }
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT  # an explicit path is for proofs only
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=1), encoding='utf-8')
    except OSError:
        pass
    ctx = record['context_used_percentage']
    five = record['five_hour_used_percentage']
    print('ctx {} | 5h {}'.format('?' if ctx is None else f'{ctx}%', '?' if five is None else f'{five}%'))


if __name__ == '__main__':
    main()
