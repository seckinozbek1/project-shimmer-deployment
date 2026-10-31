"""Check the private ledger of the operator's requests against the loop specification
(loop D-S16 item 1).

The ledger is kept, worked and checked by the same loop, so a request misread or quietly
dropped could slip through. This script does not rest on the loop's attention:

(a) it reads every Annex C row and every Annex D entry (`**D-Sn.` and `**D-Sn item m.`),
    with each numbered item and each lettered sub-item, from the specification itself;
(b) it reads the ids in every table of the ledger;
(c) it fails when a specification item has no row or a row matches no item (relayed notes,
    ids starting `N-`, are exempt and listed apart);
(d) for every DONE row it resolves each evidence pointer in the evidence column: a decision
    id `D-NNN` needs a heading `## D-NNN.` in DECISIONS.md, a commit in backticks (7 to 40
    hex) must exist, a path in backticks (a slash or a file extension) must exist under the
    repository root or the private folder; a DONE row with no pointer fails;
(e) it flags every RUNNING row (not `RUNNING (standing)`) whose last change is more than 24
    hours old, or unreadable, and whose status or evidence names no running launch, lane or
    role session. Running is read from evidence, never from a name alone: a launch runs only
    when the budget ledger (`--budget-ledger`, default `budget_ledger.jsonl` in the private
    folder) holds a `launch_intent` or `launch` line for the purpose or instance name the row
    names with no later `termination` line for that instance (matched by name or instance id);
    a lane runs only when `git worktree list` of the root shows the branch the row names
    (`lane/x`, or `lane-x` for the lane's agent name, both meaning branch `lane/x`). A role
    session or an agent has no record this script can read offline, so a row naming only one
    of those, or a launch series such as `L12`, is NOT exempt;
(f) it prints one count line and exits 1 on any failure.

How ids are formed. Annex C row `R1` is ledger id `C-R1`. An entry with no numbered items is
one id (`D-S6`); otherwise each numbered item is one (`D-S5.1`), under an entry headed
`D-Sn item m` as `D-Sn.m.k`. Lettered sub-items written as a list (an indented `a.` or `(a)`
line) each need their own row (`D-S13.6a`). Letters inside a sentence, `(a) ... (b) ...`
from `(a)` on, may be one request: a row for the item covers them, otherwise every letter
needs its row (`D-S12.2a`). Standard library only, no network; git runs with no window.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from cloud_run_common import no_window  # noqa: E402

DEFAULT_SPEC = Path('prompts') / 'SHIMMER_AUTONOMOUS_LOOP_2026-10-27.md'
DEFAULT_DECISIONS = Path('docs') / 'loop' / 'DECISIONS.md'
PRIVATE_PREFIX = 'docs/loop/private/'
STALE_AFTER = timedelta(hours=24)

ENTRY = re.compile(r'^\*\*D-S(\d+)(?: item (\d+))?\.')
NUMBERED = re.compile(r'^(\d+)\.\s')
LETTER_LINE = re.compile(r'^\s+(?:\(([a-z])\)|([a-z])\.)\s')
LETTER_INLINE = re.compile(r'\(([a-z])\)\s')
ANNEX_C = re.compile(r'^# ANNEX C\b')
ANNEX_C_ROW = re.compile(r'^\|\s*([A-Z]+\d+)\s*\|')
DECISION = re.compile(r'(?<![\w-])D-(\d{3,})(?![\w-])')
BACKTICK = re.compile(r'`([^`\n]+)`')
HEX = re.compile(r'[0-9a-f]{7,40}')
EXTENSION = re.compile(r'\.[A-Za-z][A-Za-z0-9_-]*$')
TIME = re.compile(r'(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?\s*([+-]\d{2}):?(\d{2})')
LANE = re.compile(r'(?<![\w/-])lane[/-]([A-Za-z0-9_.-]*[A-Za-z0-9_])')
WORD = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9]')
DEFAULT_BUDGET_LEDGER = 'budget_ledger.jsonl'


# (a) the specification

def _entry_blocks(lines):
    """[(entry id, [lines])] for every Annex D entry, fenced code skipped; an entry ends at
    the next entry, heading or rule."""
    blocks, current, fenced = [], None, False
    for line in lines:
        if line.startswith('```'):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = ENTRY.match(line)
        if match:
            current = ['D-S' + match.group(1) + ('.' + match.group(2) if match.group(2) else ''), []]
            blocks.append(current)
            continue
        if line.startswith('#') or line.strip() == '---':
            current = None
        elif current is not None:
            current[1].append(line)
    return blocks


def _sub_items(text_lines):
    """(letters, 'list' or 'inline') for one numbered item's lines."""
    listed = [m.group(1) or m.group(2) for m in map(LETTER_LINE.match, text_lines) if m]
    if listed:
        return listed, 'list'
    seen = []
    for letter in LETTER_INLINE.findall(' '.join(text_lines)):
        if letter not in seen:
            seen.append(letter)
    run = []
    for letter in seen:
        if letter != chr(ord('a') + len(run)):
            break
        run.append(letter)
    return (run, 'inline') if len(run) >= 2 else ([], None)


def specification_items(text):
    """[{'id', 'subs': [ids], 'form': None|'list'|'inline', 'source'}], Annex C first."""
    lines = text.splitlines()
    items = []
    in_c = False
    for line in lines:
        if ANNEX_C.match(line):
            in_c = True
            continue
        if in_c and line.startswith('# '):
            break
        match = ANNEX_C_ROW.match(line) if in_c else None
        if match:
            items.append({'id': 'C-' + match.group(1), 'subs': [], 'form': None, 'source': 'Annex C'})
    for entry, body in _entry_blocks(lines):
        numbered = []
        for line in body:
            match = NUMBERED.match(line)
            if match:
                numbered.append([match.group(1), [line]])
            elif numbered:
                numbered[-1][1].append(line)
        if not numbered:
            items.append({'id': entry, 'subs': [], 'form': None, 'source': entry})
            continue
        for number, item_lines in numbered:
            letters, form = _sub_items(item_lines)
            item_id = '%s.%s' % (entry, number)
            items.append({'id': item_id, 'subs': [item_id + letter for letter in letters], 'form': form,
                          'source': entry})
    return items


# (b) the ledger

def _cells(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def ledger_rows(text):
    """[{'id', 'cells': {column: text}, 'line', 'number'}] for every row of every table."""
    rows, header = [], None
    lines = text.splitlines()
    for number, line in enumerate(lines, 1):
        if not line.lstrip().startswith('|'):
            header = None
            continue
        cells = _cells(line)
        if all(re.fullmatch(r':?-{3,}:?', c) for c in cells if c):
            continue
        if header is None:
            header = cells
            continue
        rows.append({'id': cells[0], 'cells': dict(zip(header, cells)), 'line': line, 'number': number})
    return rows


def _status(row):
    return row['cells'].get('Status', '')


def _evidence(row):
    return row['cells'].get('Evidence or where', '')


# (c) coverage

def coverage(items, rows):
    ids = [row['id'] for row in rows]
    present = set(ids)
    missing, valid = [], set()
    for item in items:
        valid.add(item['id'])
        valid.update(item['subs'])
        if not item['subs']:
            if item['id'] not in present:
                missing.append(item['id'])
            continue
        if item['form'] == 'inline' and item['id'] in present:
            continue
        absent = [sub for sub in item['subs'] if sub not in present]
        if item['form'] == 'inline' and len(absent) == len(item['subs']):
            missing.append('%s (or each of %s)' % (item['id'], ', '.join(item['subs'])))
        else:
            missing.extend(absent)
    notes = [i for i in ids if i.startswith('N-')]
    unmatched = [i for i in ids if not i.startswith('N-') and i not in valid]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    return missing, unmatched, notes, duplicates


# (d) evidence

def _git_commit_exists(root, digest):
    result = subprocess.run(['git', '-C', str(root), 'cat-file', '-e', digest + '^{commit}'],
                            stdin=subprocess.DEVNULL, capture_output=True, creationflags=no_window())
    return result.returncode == 0


def _path_exists(token, root, private):
    rel = token.rstrip('/')
    candidates = [root / rel, private / rel]
    if rel.startswith(PRIVATE_PREFIX):
        candidates.append(private / rel[len(PRIVATE_PREFIX):])
    if any(c.exists() for c in candidates):
        return True
    if '/' not in rel and private.is_dir():
        return any(True for _ in private.rglob(rel))
    return False


def pointers(evidence):
    """[(kind, value)] for every decision, commit and path pointer in one evidence cell."""
    found = [('decision', 'D-' + n) for n in DECISION.findall(evidence)]
    for span in BACKTICK.findall(evidence):
        span = span.strip()
        if HEX.fullmatch(span):
            found.append(('commit', span))
            continue
        token = span.split()[0].rstrip('.,;:')
        if token.startswith('-') or any(ch in token for ch in '<>*?') or '://' in token or '...' in token:
            continue
        if '/' in token or EXTENSION.search(token.rstrip('/').rsplit('/', 1)[-1]):
            found.append(('path', token))
    return found


def unresolved_evidence(rows, decisions_text, root, private, commit_exists=_git_commit_exists):
    headings = set(re.findall(r'^## (D-\d{3,})\.', decisions_text, re.MULTILINE))
    failures = []
    for row in rows:
        if not _status(row).startswith('DONE'):
            continue
        found = pointers(_evidence(row))
        if not found:
            failures.append((row['id'], 'DONE without an evidence pointer'))
        for kind, value in found:
            if kind == 'decision' and value not in headings:
                failures.append((row['id'], 'no heading "## %s." in DECISIONS.md' % value))
            elif kind == 'commit' and not commit_exists(root, value):
                failures.append((row['id'], 'commit %s does not exist' % value))
            elif kind == 'path' and not _path_exists(value, root, private):
                failures.append((row['id'], 'path %s does not exist' % value))
    return failures


# (e) stale RUNNING rows

def parse_time(text):
    match = TIME.search(text or '')
    if not match:
        return None
    day, hour, minute, second, off_h, off_m = match.groups()
    sign = -1 if off_h.startswith('-') else 1
    offset = timedelta(hours=int(off_h[1:]), minutes=int(off_m)) * sign
    return datetime.strptime('%s %s:%s:%s' % (day, hour, minute, second or '00'), '%Y-%m-%d %H:%M:%S').replace(
        tzinfo=timezone(offset))


def open_launches(budget_text):
    """Lower-cased purposes and instance names of every launch the budget ledger opened (a
    `launch_intent` or `launch` line) and did not close (a `termination` line for the same
    instance name or instance id). Every instance name is a launch of its own, so a line
    copied from another ledger after the termination does not reopen it. An unreadable line
    is skipped."""
    opened, ids, closed = {}, {}, []
    for line in (budget_text or '').splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        name, instance = record.get('instance_name'), record.get('instance_id')
        if record.get('event') in ('launch_intent', 'launch') and name:
            opened.setdefault(name, set()).add(name.lower())
            if record.get('purpose'):
                opened[name].add(str(record['purpose']).lower())
            if instance:
                ids[instance] = name
        elif record.get('event') == 'termination':
            closed.append((name, instance))
    for name, instance in closed:
        opened.pop(name, None)
        opened.pop(ids.get(instance), None)
    return set().union(*opened.values()) if opened else set()


def _git_worktree_branches(root):
    """The branches `git worktree list` of the root shows checked out, as `lane/x`."""
    result = subprocess.run(['git', '-C', str(root), 'worktree', 'list', '--porcelain'], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, creationflags=no_window())
    prefix = 'branch refs/heads/'
    return {line[len(prefix):] for line in result.stdout.splitlines() if line.startswith(prefix)}


def names_running(text, launches, branches):
    """The launches and lanes the text names that are running by the evidence read."""
    found = sorted({w.lower() for w in WORD.findall(text)} & launches)
    found += sorted({'lane/' + name for name in LANE.findall(text)} & branches)
    return found


def stale_running(rows, now, launches=frozenset(), branches=frozenset()):
    stale = []
    for row in rows:
        status = _status(row)
        if not status.startswith('RUNNING') or status.startswith('RUNNING (standing)'):
            continue
        changed = parse_time(row['cells'].get('Last change', ''))
        if changed is not None and now - changed <= STALE_AFTER:
            continue
        if names_running(status + ' ' + _evidence(row), launches, branches):
            continue
        stale.append((row['id'], 'no readable Last change' if changed is None
                      else 'last change %s, names no running launch or lane' % changed.isoformat()))
    return stale


# (f) the report

def check(spec_text, ledger_text, decisions_text, root, private, now, commit_exists=_git_commit_exists,
          budget_text='', worktree_branches=_git_worktree_branches):
    items = specification_items(spec_text)
    rows = ledger_rows(ledger_text)
    missing, unmatched, notes, duplicates = coverage(items, rows)
    unresolved = unresolved_evidence(rows, decisions_text, root, private, commit_exists)
    stale = stale_running(rows, now, open_launches(budget_text), worktree_branches(root))
    annex_c = sum(1 for i in items if i['source'] == 'Annex C')
    entries = len({i['source'] for i in items if i['source'] != 'Annex C'})
    subs = sum(len(i['subs']) for i in items)
    lines = ['specification: %d Annex C rows, %d Annex D entries, %d items, %d lettered sub-items'
             % (annex_c, entries, len(items) - annex_c, subs),
             'ledger: %d rows (%d relayed notes, exempt from (c): %s)' % (len(rows), len(notes), ', '.join(notes) or 'none')]
    lines += ['MISSING (no row): %s' % m for m in missing]
    lines += ['UNMATCHED (no specification item): %s' % u for u in unmatched]
    lines += ['DUPLICATE id: %s' % d for d in duplicates]
    lines += ['UNRESOLVED %s: %s' % pair for pair in unresolved]
    lines += ['STALE RUNNING %s: %s' % pair for pair in stale]
    failed = bool(missing or unmatched or duplicates or unresolved or stale)
    lines.append('specification items %d, ledger rows %d, missing %d, unmatched %d, duplicate %d, '
                 'unresolved evidence %d, stale running %d: %s'
                 % (len(items) + subs, len(rows), len(missing), len(unmatched), len(duplicates),
                    len(unresolved), len(stale), 'FAIL' if failed else 'PASS'))
    return failed, lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--root', default=str(ROOT), help='repository root (default: this checkout)')
    parser.add_argument('--spec', help='specification, default <root>/%s' % DEFAULT_SPEC.as_posix())
    parser.add_argument('--ledger', required=True, help='the private request ledger')
    parser.add_argument('--decisions', help='DECISIONS.md, default <root>/%s' % DEFAULT_DECISIONS.as_posix())
    parser.add_argument('--private', help='the private folder, default the ledger\'s folder')
    parser.add_argument('--budget-ledger', help='the loop\'s budget ledger read for running launches, default '
                        '<private>/%s; with none, no launch counts as running' % DEFAULT_BUDGET_LEDGER)
    parser.add_argument('--now', help='ISO time with offset to judge staleness against (default: the clock)')
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    ledger = Path(args.ledger)
    spec = Path(args.spec) if args.spec else root / DEFAULT_SPEC
    decisions = Path(args.decisions) if args.decisions else root / DEFAULT_DECISIONS
    private = Path(args.private) if args.private else ledger.resolve().parent
    budget = Path(args.budget_ledger) if args.budget_ledger else private / DEFAULT_BUDGET_LEDGER
    if args.budget_ledger and not budget.is_file():
        parser.error('--budget-ledger %s is not a file' % budget)
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        parser.error('--now needs a date, a time and an offset')
    failed, lines = check(spec.read_text(encoding='utf-8'), ledger.read_text(encoding='utf-8'),
                          decisions.read_text(encoding='utf-8'), root, private, now,
                          budget_text=budget.read_text(encoding='utf-8') if budget.is_file() else '')
    print('\n'.join(lines))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
