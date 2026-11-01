"""Check that every deferral the loop records says who made it and has an issue (loop Annex D
D-S24 item 4, extending the stage gate of D-S16 item 2).

A sibling of `request_ledger_check.py`, whose ledger parser it reuses. It reads the open
issues from a JSON file (`--issues`, the output of
`gh issue list --state open --limit 500 --json number,title,labels,milestone,body`) and never
fetches them, so it runs offline. It fails when:

(a) an open issue carries neither the `operator-deferred` nor the `loop-deferred` label and
    no stage milestone (`STAGE_MILESTONES`, S05 to S14): it is neither planned nor deferred;
(b) an issue labelled `honesty-or-release` sits in a milestone after v1
    (`AFTER_V1_MILESTONES`) labelled `loop-deferred`: D-S24 item 3 lets such an issue sit
    after v1 only with `operator-deferred`;
(c) a row of the private request ledger whose status is SCHEDULED or DEFERRED names no issue
    (no `#nnn` anywhere in the row);
(d) a decision in `docs/loop/DECISIONS.md` that moves, drops or skips work names no issue.

How (d) is decided, and why. Whether a sentence moves work is a question of what its words
mean, and CLAUDE.md's WORDS-A rule keeps such questions away from literal keyword tables; it
names no exception for loop tooling. So this script reads no prose for (d). It reads one
DECLARED STRUCTURE instead: from D-179 on (`FIRST_MARKED_DECISION`, the decision that applied
D-S24), a decision that moves, defers, drops or skips work carries a marker line, a bullet
opening with `**Moves.**`, `**Defers.**`, `**Drops.**` or `**Skips.**` (or a line opening
`Moves:`, `Defers:`, `Drops:`, `Skips:`), and every such line must name an issue (`#nnn`) on
that line. A marker line with no issue fails; a decision that moves work without writing the
marker is not seen by this script, which is what the outside audit of each stage close reads
for (D-S24 item 5). Decisions before D-179 are grandfathered: they carry no markers, are not
read for (d), and are reported as a count.

Prints each failure on one line and then one count line; exits 1 on any failure. Standard
library only, no network.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from request_ledger_check import ROOT, DEFAULT_DECISIONS, ledger_rows  # noqa: E402

# The stage milestones on GitHub (D-S16 item 3a: one for each remaining stage, S5 to S14).
STAGE_MILESTONES = frozenset('S%02d' % n for n in range(5, 15))
# The stages moved after v1 by Annex D D-S18 item 3 ("L9a and L9b; L13; the S6 items ...; S9
# ...; preregistration version 3 and the sealed evaluation [S8] ...; S12 (D-S17); then S14").
# S9 is in that sentence and has a milestone, so it is here too.
AFTER_V1_MILESTONES = frozenset({'S06', 'S08', 'S09', 'S12', 'S14'})
OPERATOR_DEFERRED = 'operator-deferred'
LOOP_DEFERRED = 'loop-deferred'
HONESTY = 'honesty-or-release'
LEDGER_DEFERRAL_STATUSES = ('SCHEDULED', 'DEFERRED')
FIRST_MARKED_DECISION = 179
MARKERS = ('Moves', 'Defers', 'Drops', 'Skips')

ISSUE_REF = re.compile(r'(?<![\w&/])#(\d+)\b')
DECISION_HEADING = re.compile(r'^## D-(\d{3,})\.')
MARKER_LINE = re.compile(r'^\s*(?:[-*]\s+)?(?:\*\*(%s)\.\*\*|(%s):)' % ('|'.join(MARKERS), '|'.join(MARKERS)))


# the issues

def read_issues(text):
    """[{'number', 'labels': set, 'milestone': str or None}] from gh's JSON; anything else
    raises ValueError."""
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError('the issues file is not a JSON list')
    issues = []
    for entry in data:
        if not isinstance(entry, dict) or not isinstance(entry.get('number'), int):
            raise ValueError('an issue without a number: %r' % (entry,))
        labels = {label.get('name', '') if isinstance(label, dict) else str(label)
                  for label in entry.get('labels') or []}
        milestone = entry.get('milestone')
        title = milestone.get('title') if isinstance(milestone, dict) else None
        issues.append({'number': entry['number'], 'labels': labels, 'milestone': title or None})
    return issues


def unplanned_issues(issues):
    """(a) open issues with neither deferral label and no stage milestone."""
    return [(i['number'], 'no %s or %s label and no stage milestone (milestone: %s)'
             % (OPERATOR_DEFERRED, LOOP_DEFERRED, i['milestone'] or 'none'))
            for i in issues
            if not ({OPERATOR_DEFERRED, LOOP_DEFERRED} & i['labels']) and i['milestone'] not in STAGE_MILESTONES]


def loop_deferred_honesty(issues):
    """(b) honesty-or-release issues after v1 that the loop, not the operator, deferred."""
    return [(i['number'], '%s in %s (after v1) labelled %s' % (HONESTY, i['milestone'], LOOP_DEFERRED))
            for i in issues
            if HONESTY in i['labels'] and i['milestone'] in AFTER_V1_MILESTONES and LOOP_DEFERRED in i['labels']]


# the ledger

def rows_without_issue(rows):
    """(c) SCHEDULED or DEFERRED ledger rows naming no issue."""
    return [(row['id'], '%s and names no issue' % row['cells'].get('Status', '').split()[0])
            for row in rows
            if row['cells'].get('Status', '').startswith(LEDGER_DEFERRAL_STATUSES) and not ISSUE_REF.search(row['line'])]


# the decisions

def decision_blocks(text):
    """[(number, [lines])] for every `## D-NNN.` decision, fenced code skipped."""
    blocks, current, fenced = [], None, False
    for line in text.splitlines():
        if line.startswith('```'):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = DECISION_HEADING.match(line)
        if match:
            current = (int(match.group(1)), [])
            blocks.append(current)
        elif line.startswith('#'):
            current = None
        elif current is not None:
            current[1].append(line)
    return blocks


def markers_without_issue(blocks):
    """(d) ([(decision id, reason)], grandfathered count, marker lines read)."""
    failures, grandfathered, read = [], 0, 0
    for number, lines in blocks:
        if number < FIRST_MARKED_DECISION:
            grandfathered += 1
            continue
        for line in lines:
            match = MARKER_LINE.match(line)
            if not match:
                continue
            read += 1
            if not ISSUE_REF.search(line):
                failures.append(('D-%03d' % number, '"%s" line names no issue' % (match.group(1) or match.group(2))))
    return failures, grandfathered, read


# the report

def check(issues_text, ledger_text, decisions_text):
    issues = read_issues(issues_text)
    rows = ledger_rows(ledger_text)
    blocks = decision_blocks(decisions_text)
    unplanned = unplanned_issues(issues)
    honesty = loop_deferred_honesty(issues)
    unissued = rows_without_issue(rows)
    unmarked, grandfathered, markers = markers_without_issue(blocks)
    lines = ['UNPLANNED ISSUE #%d: %s' % pair for pair in unplanned]
    lines += ['LOOP-DEFERRED HONESTY ISSUE #%d: %s' % pair for pair in honesty]
    lines += ['LEDGER ROW WITHOUT ISSUE %s: %s' % pair for pair in unissued]
    lines += ['DECISION WITHOUT ISSUE %s: %s' % pair for pair in unmarked]
    failed = bool(unplanned or honesty or unissued or unmarked)
    lines.append('open issues %d, ledger rows %d, decisions %d (%d before D-%03d grandfathered, %d marker lines read); '
                 'unplanned issues %d, loop-deferred honesty issues after v1 %d, scheduled or deferred rows without '
                 'an issue %d, deferring decisions without an issue %d: %s'
                 % (len(issues), len(rows), len(blocks), grandfathered, FIRST_MARKED_DECISION, markers,
                    len(unplanned), len(honesty), len(unissued), len(unmarked), 'FAIL' if failed else 'PASS'))
    return failed, lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--issues', required=True,
                        help='JSON of `gh issue list --state open --limit 500 --json number,title,labels,milestone,body`')
    parser.add_argument('--ledger', required=True, help='the private request ledger')
    parser.add_argument('--decisions', help='DECISIONS.md, default <this checkout>/%s' % DEFAULT_DECISIONS.as_posix())
    args = parser.parse_args(argv)
    decisions = Path(args.decisions) if args.decisions else ROOT / DEFAULT_DECISIONS
    try:
        failed, lines = check(Path(args.issues).read_text(encoding='utf-8-sig'),
                              Path(args.ledger).read_text(encoding='utf-8'),
                              decisions.read_text(encoding='utf-8'))
    except ValueError as error:
        parser.error('--issues %s: %s' % (args.issues, error))
    print('\n'.join(lines))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
