"""PreCompact hook: a mechanical safety copy of the loop state before compaction.

Copies ``docs/loop/private/LOOP_STATE.md`` and the last 50 lines of
``docs/loop/DECISIONS.md`` into ``docs/loop/private/handoff/AUTO_PRECOMPACT_<timestamp>.md``.
It always exits 0, even after an error, because exit code 2 would block compaction. It
does not replace the handoff the lead writes. Loop machinery, not product code.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / 'docs' / 'loop' / 'private'


def read(path, tail=None):
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except Exception as exc:
        return '(could not read {}: {})'.format(path.name, type(exc).__name__)
    return '\n'.join(lines[-tail:] if tail else lines)


def main():
    try:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        out = PRIVATE / 'handoff' / f'AUTO_PRECOMPACT_{stamp}.md'
        out.parent.mkdir(parents=True, exist_ok=True)
        body = ['# Automatic pre-compaction copy', '', f'Written {stamp} UTC by tools/loop/precompact.py.',
                'Mechanical copy only; read the newest HANDOFF_*.md too.', '', '## LOOP_STATE.md', '',
                read(PRIVATE / 'LOOP_STATE.md'), '', '## Last 50 lines of DECISIONS.md', '',
                read(ROOT / 'docs' / 'loop' / 'DECISIONS.md', tail=50), '']
        out.write_text('\n'.join(body), encoding='utf-8')
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    sys.stdin.read() if not sys.stdin.isatty() else None
    sys.exit(main())
