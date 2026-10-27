"""SessionStart hook: tell a new or resumed lead session that a loop is in progress.

If ``docs/loop/private/LOOP_STATE.md`` exists and its status is not DONE, prints the notice,
this session's id (from the hook's own JSON input), the full state file and the newest
handoff. Claude Code adds this output to the session's context. Loop machinery, not
product code.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / 'docs' / 'loop' / 'private'
NOTICE = ('A Shimmer loop is in progress. If you are the lead session started by Seckin in the '
          'main checkout, read `prompts/SHIMMER_AUTONOMOUS_LOOP_2026-10-27.md`, then '
          '`docs/loop/private/LOOP_STATE.md`, then the newest file in `docs/loop/private/handoff/`, '
          'before anything else. Otherwise ignore this.')


def main():
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
