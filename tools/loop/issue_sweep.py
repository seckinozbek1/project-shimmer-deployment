"""The record of a full GitHub issue sweep (Seckin, 20 November 2026 13:27, D-839).

Every issue update is a full sweep: the same pass scans all open issues, closes those with no real work left or
that are stale (with evidence: a decision id, a commit, a result file, or the issue that covers it), and updates
those that need it. At the end of the sweep the lead runs

    py -3.12 -X utf8 tools/loop/issue_sweep.py record --closed N --updated M
    py -3.12 -X utf8 tools/loop/issue_sweep.py line

`record` reads the per-milestone open and closed issue counts live with
`gh api repos/<owner>/<name>/milestones?state=all&per_page=100` (counts and titles only, never an issue's text),
<owner>/<name> being the main checkout's origin, which must be the project repository (any other origin is refused
and gh is not called), and writes docs/loop/private/issue_sweep.json (the time from the clock, the two counts the
lead gives, the counts by milestone). The private folder is the main checkout's, found through
tools/loop/shared_paths.py (mechanism_common.PRIVATE). `line` prints the plain FOR_SECKIN line and, on the next
line, the JSON object for the panel's REL gh field, {alpha, beta, full, v11: {open, closed, at}}.

tools/loop/sync_watch.py reads the record: an issue update counts as done only when the sweep is newer than the
decision or result that made it due, and a sweep over 24 hours old alerts "issue sweep due".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mechanism_common as mc  # noqa: E402
import sync_watch as sw  # noqa: E402

RECORD_NAME = 'issue_sweep.json'
# Panel REL gh keys, in the order of the FOR_SECKIN line, and the milestone title each stands for.
PANEL_KEYS = (('alpha', 'v1.0-alpha'), ('beta', 'v1.0-beta'), ('full', 'v1.0'), ('v11', 'v1.1'))


class SweepError(Exception):
    """The counts cannot be read: a refused origin, a gh failure, or a reply that is not a milestone list."""


def record_path(private=None):
    return Path(private or mc.PRIVATE) / RECORD_NAME


def _count(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SweepError('a milestone count is not a whole number')
    return value


def milestone_counts(main=None, runner=None):
    """{title: {open, closed}} for every milestone of the project repository, read live from gh."""
    runner = runner or sw.run
    repo = sw.origin_repo(Path(main or mc.MAIN), runner)
    if repo is None:
        raise SweepError('origin is not %s; gh not called' % sw.PROJECT_REPO)
    rc, text = runner(['gh', 'api', 'repos/%s/milestones?state=all&per_page=100' % repo])
    if rc != 0:
        raise SweepError('gh api milestones exit %d' % rc)
    try:
        reply = json.loads(text or '')
    except ValueError:
        raise SweepError('gh api milestones printed no JSON')
    if not isinstance(reply, list):
        raise SweepError('gh api milestones printed no list')
    out = {}
    for m in reply:
        if not isinstance(m, dict) or not isinstance(m.get('title'), str):
            raise SweepError('a milestone has no title')
        out[m['title']] = {'open': _count(m.get('open_issues')), 'closed': _count(m.get('closed_issues'))}
    return out


def record(closed, updated, main=None, private=None, runner=None, now=None):
    """Write the sweep record; returns it."""
    body = {'at': (now or mc.now()).isoformat(timespec='seconds'), 'closed': _count(closed),
            'updated': _count(updated), 'milestones': milestone_counts(main, runner)}
    path = record_path(private)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(body, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(tmp, path)
    return body


def load(private=None):
    """The last sweep record, or None when there is none or it cannot be read."""
    try:
        body = json.loads(record_path(private).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def panel_gh(body):
    """The panel REL gh field: {alpha, beta, full, v11: {open, closed, at}} (None counts for a missing milestone)."""
    milestones = body.get('milestones') or {}
    return {key: {'open': (milestones.get(title) or {}).get('open'), 'closed': (milestones.get(title) or {}).get('closed'),
                  'at': body.get('at')} for key, title in PANEL_KEYS}


def for_seckin_line(body):
    milestones = body.get('milestones') or {}

    def shown(title):
        value = (milestones.get(title) or {}).get('open')
        return '-' if value is None else str(value)
    return 'GitHub taraması: %s konu kapandı, %s güncellendi; açık: %s' % (
        body.get('closed'), body.get('updated'), ', '.join('%s %s' % (t, shown(t)) for _, t in PANEL_KEYS))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='cmd', required=True)
    rec = sub.add_parser('record', help='write docs/loop/private/issue_sweep.json at the end of a sweep')
    rec.add_argument('--closed', type=int, required=True)
    rec.add_argument('--updated', type=int, required=True)
    sub.add_parser('line', help='print the FOR_SECKIN line and the panel REL gh JSON of the last sweep')
    args = parser.parse_args(argv)
    if args.cmd == 'record':
        try:
            body = record(args.closed, args.updated)
        except SweepError as exc:
            print('issue sweep not recorded: %s' % exc)
            return 2
        print('recorded %s at %s' % (record_path(), body['at']))
        return 0
    body = load()
    if body is None:
        print('no issue sweep recorded (%s)' % record_path())
        return 2
    print(for_seckin_line(body))
    print(json.dumps(panel_gh(body), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
