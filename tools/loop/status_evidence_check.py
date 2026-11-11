"""Check that no record calls something done, verified, closed, merged, measured or applied
without evidence that resolves (loop D-S101 item 3; the sibling of
tools/loop/request_ledger_check.py).

D-S101 item 1 allows four states: requested, in progress, done (finished, with its evidence:
a decision, a commit, a file or a run folder) and verified (done and its evidence resolved by
a fresh agent or a script). This script reads the records of item 1 that are machine-readable
and fails on every claim of a finished state whose evidence does not resolve, or names none.

Records read (each only when given or found; one claim count per record is printed):
  ledger         the request ledger: every row whose Status starts DONE or VERIFIED;
  loose ends     `LOOSE_ENDS.md`: every row of a table with a State column whose State cell
                 opens with a finished state; its other lines in the declared forms below;
  return brief   `RETURN_BRIEF.md`, in the declared forms;
  for seckin     `FOR_SECKIN.md`, in the declared forms, Turkish state words included;
  push record    `PUSH_RECORD.md`, in the declared forms;
  plan           `docs/loop/stages/AFTER_V1_PLAN.md`, read from the loop branch unless
                 `--plan` is given, in the declared forms;
  progress       `PROGRESS.json`: every object whose `status` is done or verified, its
                 evidence read from its `evidence`, `name` and `note` fields (its own `id` is
                 removed from them first: an object naming itself is not evidence);
  issues         gh's closed-issue JSON, given as a file (`gh issue list --state closed --json
                 number,title,stateReason,comments`), never fetched here: every issue closed as
                 completed, its evidence read from its comments (D-S16 item 3c). An issue closed
                 as not planned claims no done and is counted apart.
A record that holds a finished-state word (`STATE_WORDS`) and yields no claim fails: its
states are written in a form this script cannot read.

Not read, and why (the omissions D-S101 item 1 names): the progress page
(`docs/progress/index.html`, generated from the scoreboard and run records, which this script
reads at their source), the 12 November package (not yet built; its records are those above)
and promises to Seckin never closed (FOR_SECKIN or the return brief saying something will be
done; a promise is not a claim of a finished state, and the D-S97 look-back reads them).

A claim in a Markdown record is read only in these declared forms, never from prose (so
"not yet done" is no claim): the word in capitals (`DONE`, `MERGED`); bold (`**Done**`,
`**Merged.**`, `**Bitti:**`); in brackets or parentheses (`(done)`, `[verified]`,
`(done, D-123)`); the word followed by a parenthesis that holds a pointer (`done (D-123)`, `bitti (19:22,
D-314)`; "done (evidence named)" is prose); as a
label opening a line or a table cell (`Done:`, `Applied.`); `Status: done`; or a table cell
that opens with the word (`| done (D-123) |`). The words are `STATE_WORDS`: done, verified,
closed, merged, measured, applied, and the Turkish bitti, doğrulandı, kapandı, birleşti,
birleştirildi, ölçüldü, uygulandı. A state stated any other way is not read, and D-S101 item 1
asks the records to use these forms. A stated limit: FOR_SECKIN and the return brief also use
these words in running prose (Turkish and English) outside the forms; such a sentence is not a
claim this script reads, so a finished state written only in prose goes unchecked here and is
the D-S97 look-back's to read.

What resolves:
  a decision `D-NNN`  a heading `## D-NNN.` in DECISIONS.md (read from the loop branch unless
                      `--decisions` is given). For a claim with an own id (a ledger row's id, a
                      PROGRESS stage's id), at least one decision it names must name that id in
                      its own text (a ledger `D-Sn.m` row: the entry `D-Sn`; `C-Rn`: `Rn` or
                      `C-Rn`; a stage: its id), else the claim fails as unrelated. Not checkable,
                      stated: a decision that names the id but is about something else; a
                      claim's other decisions (a superseded row rightly cites the decision that
                      applied the superseding entry, which names that entry, not this row); a
                      relayed note's row (`N-`), a PROGRESS object with no id and any Markdown or
                      issue claim, which carry no id a decision would name.
  a commit            in backticks, or a bare 7 to 40 hex word that git knows as a commit (a
                      bare hex word git does not know is a digest, not a pointer, and is
                      skipped; a backticked one must exist): an ancestor of the loop branch, or,
                      in the push record only, of the pushed ref (`--push-ref`, default
                      refs/remotes/origin/main: the progress page lives on main by design, D-S98,
                      D-192), read as the local copy of that ref stands; `--fetch-push-ref` runs
                      a read-only `git fetch origin main` first (the one network read, opt-in); and
                      every tracked path the claim names must have been CHANGED by at least one
                      commit the claim names (git diff-tree against the first parent), not
                      merely held by it. A commit named with no path is checked for ancestry
                      only: what it changed is then not compared with the claim.
  a file              a backticked path (a slash or an extension) inside the root or the private
                      folder (an absolute path or one leaving them through `..` is refused) that
                      exists and is not empty, on disk or, when the checkout's disk lags the loop
                      branch, tracked on the loop branch (git cat-file, non-empty there); a bare file name is looked for only directly under
                      the root and the private folder, never searched for below them;
  a run folder        a backticked path that is a folder holding `result.json` or
                      `FINAL_STATUS.json` directly or in its `evidence/` (the controller's layout),
                      parsed as JSON and not empty (`{}` and `[]` are no result). Its content is
                      not judged: a result that says the run failed still resolves the claim that
                      the run happened, and what it measured is the scorer's to read.
Not pointers, so a claim naming only these fails as naming no evidence: an Annex D entry
(`D-S101`), a decision id under three digits (`D-35`), a stage name, an issue number. A
record of item 1 that is absent fails unless the caller names it with `--skip` (printed as
"not read"); closed issues are read only from `--closed-issues`, so a run without that file must
say `--skip issues`. The ledger's Status vocabulary is DONE, VERIFIED, RUNNING, SCHEDULED,
DEFERRED and BLOCKED as the first word (`RUNNING (standing)` included); any other first word
fails, so a `Done`, `DONE(` or `MERGED` row is never skipped silently.
A branch name (`lane/x`, `loop/x`) is no pointer and no evidence: a lane is in progress until
merged, and its merge commit is the evidence.
Every pointer a claim names must resolve, and a claim naming none fails. One line per record
and one count line; exit 1 on any failure. Standard library and git only, no network; git runs
with no window.

    py -3.12 -X utf8 tools/loop/status_evidence_check.py --root . --closed-issues closed.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloud_run_common import no_window  # noqa: E402
import request_ledger_check as ledger_check  # noqa: E402

DEFAULT_LOOP_REF = 'loop/2026-10-27'
PRIVATE = Path('docs') / 'loop' / 'private'
DECISIONS_PATH = 'docs/loop/DECISIONS.md'
PLAN_PATH = 'docs/loop/stages/AFTER_V1_PLAN.md'
RESULT_FILES = ('result.json', 'FINAL_STATUS.json')
RUN_DEPTH = 3
CLAIM_STATES = ('done', 'verified')
LEDGER_STATES = ('DONE', 'VERIFIED')
STATE_WORDS = ('done', 'verified', 'closed', 'merged', 'measured', 'applied',
               'bitti', 'doğrulandı', 'kapandı', 'birleşti', 'birleştirildi', 'ölçüldü', 'uygulandı')


def _variants(word):
    """A word as written, capitalised and in capitals, Turkish dotted capitals included."""
    upper = word.replace('i', 'İ').replace('ı', 'I').upper()
    return {word, word[0].upper() + word[1:], upper, upper.replace('İ', 'I')}


_ALL = sorted({v for w in STATE_WORDS for v in _variants(w)}, key=len, reverse=True)
_WORD = '(?:' + '|'.join(map(re.escape, _ALL)) + ')'
_CAPS = '(?:' + '|'.join(re.escape(v) for w in STATE_WORDS for v in _variants(w) if v == v.upper()) + ')'
_EDGE_L, _EDGE_R = r'(?<![\w-])', r'(?![\w-])'
CLAIM_FORMS = (
    re.compile(_EDGE_L + _CAPS + _EDGE_R),                                          # capitals
    re.compile(r'\*\*\s*' + _WORD + r'\s*[.:,]?\s*\*\*'),                           # bold
    re.compile(r'[(\[]\s*' + _WORD + r'\s*(?:[)\],:;]|$)'),                        # bracketed
    re.compile(_EDGE_L + _WORD + r'\s+\((?=[^)]*(?:D-\d{3}|`|[0-9a-f]{7}))'),        # word (a pointer)
    re.compile(r'^(?:[-*+]\s+|\d+\.\s+|\|\s*)?' + _WORD + r'\s*[:.,]'),            # label
    re.compile(r'\b(?:[Ss]tatus|[Ss]tate|STATUS|STATE)\s*:\s*' + _WORD + _EDGE_R),  # Status: done
    re.compile(r'\|\s*' + _WORD + _EDGE_R + r'(?=[^|]*\|)'),                        # a cell opening with the word
)
STATE_WORD = re.compile(_EDGE_L + _WORD + _EDGE_R)
LEDGER_VOCABULARY = ('DONE', 'VERIFIED', 'RUNNING', 'SCHEDULED', 'DEFERRED', 'BLOCKED')
NOT_CLAIMED_REASONS = ('NOT_PLANNED',)
PUSH_RECORDS = ('push record',)
DEFAULT_PUSH_REF = 'refs/remotes/origin/main'
RECORDS = ('ledger', 'loose ends', 'return brief', 'for seckin', 'push record', 'plan', 'progress', 'issues')
BRANCH = re.compile(r'^(?:lane|loop|origin|refs)/')
BARE_HEX = re.compile(r'(?<![\w/.-])([0-9a-f]{7,40})(?![\w/.-])')


# ---- git and the file system

def _git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, creationflags=no_window())


class Repository:
    """The git and file-system questions a pointer asks, one place, cached."""

    def __init__(self, root, private, loop_ref, push_ref=DEFAULT_PUSH_REF):
        self.root, self.private, self.loop_ref, self.push_ref = Path(root), Path(private), loop_ref, push_ref
        self._commits, self._ancestors, self._tracked, self._changed = {}, {}, {}, {}

    def is_commit(self, digest):
        if digest not in self._commits:
            self._commits[digest] = _git(self.root, 'cat-file', '-e', digest + '^{commit}').returncode == 0
        return self._commits[digest]

    def is_ancestor(self, digest):
        if digest not in self._ancestors:
            self._ancestors[digest] = _git(self.root, 'merge-base', '--is-ancestor', digest,
                                           self.loop_ref).returncode == 0
        return self._ancestors[digest]

    def is_pushed(self, digest):
        """True when the commit is an ancestor of the pushed ref (refs/remotes/origin/main by
        default), as read locally; `--fetch-push-ref` refreshes that ref first."""
        key = ('pushed', digest)
        if key not in self._ancestors:
            self._ancestors[key] = _git(self.root, 'merge-base', '--is-ancestor', digest,
                                        self.push_ref).returncode == 0
        return self._ancestors[key]

    def tracked(self, path):
        if path not in self._tracked:
            self._tracked[path] = _git(self.root, 'cat-file', '-e', '%s:%s' % (self.loop_ref, path)).returncode == 0
        return self._tracked[path]

    def commit_changes(self, digest, path):
        """True when the commit changed the path against its first parent (a root commit
        against nothing). A path that is a folder counts when any file under it changed."""
        key = (digest, path)
        if key not in self._changed:
            out = _git(self.root, 'diff-tree', '--no-commit-id', '--name-only', '-r', '--root', '-m',
                       '--first-parent', digest, '--', path)
            self._changed[key] = out.returncode == 0 and bool(out.stdout.strip())
        return self._changed[key]

    def locate(self, token):
        """The existing file or folder a path token names inside the root or the private
        folder, or None. An absolute path, a drive, or one leaving them is refused."""
        rel = token.rstrip('/')
        if not inside_scope(rel):
            return None
        candidates = [self.root / rel, self.private / rel]
        prefix = PRIVATE.as_posix() + '/'
        if rel.startswith(prefix):
            candidates.append(self.private / rel[len(prefix):])
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def tracked_has_content(self, path):
        """True when the loop branch tracks the path as a non-empty file or as a folder."""
        kind = _git(self.root, 'cat-file', '-t', '%s:%s' % (self.loop_ref, path))
        if kind.returncode != 0:
            return False
        if kind.stdout.strip() == 'tree':
            return True
        size = _git(self.root, 'cat-file', '-s', '%s:%s' % (self.loop_ref, path))
        return size.returncode == 0 and size.stdout.strip().isdigit() and int(size.stdout.strip()) > 0

    def show(self, path):
        shown = _git(self.root, 'show', '%s:%s' % (self.loop_ref, path))
        return shown.stdout if shown.returncode == 0 else None

    def decisions_text(self, override=None):
        if override is not None:
            return Path(override).read_text(encoding='utf-8')
        return self.show(DECISIONS_PATH) or ''


def inside_scope(rel):
    """False for an absolute path, a drive letter or a path that climbs out with `..`."""
    path = Path(rel)
    return not (path.is_absolute() or path.drive or rel.startswith(('/', '\\')) or '..' in path.parts)


def file_has_content(path):
    return Path(path).is_dir() or Path(path).stat().st_size > 0


def run_folder_holds_result(folder, depth=RUN_DEPTH):
    """True when the folder, or its `evidence/`, holds a result file that parses as a
    non-empty JSON object or list. `depth` is kept for callers and no longer searched."""
    folder = Path(folder)
    for place in (folder, folder / 'evidence'):
        for name in RESULT_FILES:
            candidate = place / name
            if candidate.is_file():
                try:
                    data = json.loads(candidate.read_text(encoding='utf-8-sig'))
                except (ValueError, OSError):
                    continue
                if isinstance(data, (dict, list)) and data:
                    return True
    return False


def decision_sections(text):
    """{'D-NNN': its section's text} for every `## D-NNN.` heading."""
    sections, current = {}, None
    for line in text.splitlines():
        match = re.match(r'^## (D-\d{3,})\.', line)
        if match:
            current = match.group(1)
            sections[current] = []
        elif line.startswith('## '):
            current = None
        if current:
            sections[current].append(line)
    return {key: '\n'.join(value) for key, value in sections.items()}


# ---- pointers and claims

class Claim:
    """One claim of a finished state: where it stands, the text its evidence is read from,
    and the id a decision it names must name (None when no id applies)."""

    def __init__(self, where, text, own_id=None):
        self.where, self.text, self.own_id = where, text, own_id


def pointers(text, lenient_hex=True, repo=None):
    """[(kind, value)] named in one text: decisions, backticked commits and paths (through the
    ledger check's reader, so both read pointers the same way), and bare hex words git knows
    as commits when `lenient_hex`."""
    found = [(kind, value) for kind, value in ledger_check.pointers(text)
             if not (kind == 'path' and BRANCH.match(value))]
    if lenient_hex and repo is not None:
        named = {value for kind, value in found if kind == 'commit'}
        for digest in BARE_HEX.findall(re.sub(r'`[^`\n]*`', ' ', text)):
            if digest not in named and re.search(r'\d', digest) and repo.is_commit(digest):
                found.append(('commit', digest))
                named.add(digest)
    return found


def no_evidence(found):
    return not found


def decision_resolves(value, headings):
    return value in headings


def id_patterns(own_id):
    """The patterns a decision's text must match to name an own id, or None when no id can be
    named (a relayed note)."""
    if not own_id or own_id.startswith('N-'):
        return None
    entry = re.match(r'^(D-S\d+)', own_id)
    if entry:
        return [re.compile(re.escape(entry.group(1)) + r'(?!\d)')]
    annex_c = re.match(r'^C-([A-Z]+\d+)$', own_id)
    if annex_c:
        return [re.compile(r'(?<![\w-])(?:C-)?' + re.escape(annex_c.group(1)) + r'(?!\d)')]
    return [re.compile(r'(?<![\w-])' + re.escape(own_id) + r'(?![\w-])')]


def decision_names(section, own_id):
    patterns = id_patterns(own_id)
    return patterns is None or any(p.search(section) for p in patterns)


def resolve(found, headings, repo, own_id=None, sections=None, pushed=False):
    """The reasons a claim's pointers do not resolve ([] when every one does)."""
    if no_evidence(found):
        return ['a finished state with no evidence named']
    reasons = []
    decisions = [value for kind, value in found if kind == 'decision']
    commits = [value for kind, value in found if kind == 'commit']
    paths = [value.rstrip('/') for kind, value in found if kind == 'path']
    for value in decisions:
        if not decision_resolves(value, headings):
            reasons.append('no heading "## %s." in DECISIONS.md' % value)
    known = [d for d in decisions if decision_resolves(d, headings)]
    if known and sections is not None and id_patterns(own_id) is not None:
        if not any(decision_names(sections.get(d, ''), own_id) for d in known):
            reasons.append('unrelated: no decision it names (%s) names %s' % (', '.join(known), own_id))
    good = []
    for value in commits:
        if not repo.is_commit(value):
            reasons.append('commit %s does not exist' % value)
        elif not repo.is_ancestor(value) and not (pushed and repo.is_pushed(value)):
            reasons.append('commit %s is not an ancestor of %s%s' % (
                value, repo.loop_ref, ' or %s' % repo.push_ref if pushed else ''))
        else:
            good.append(value)
    if good:
        for rel in paths:
            if repo.tracked(rel) and not any(repo.commit_changes(c, rel) for c in good):
                reasons.append('no commit it names (%s) changed %s' % (', '.join(good), rel))
    for rel in paths:
        located = repo.locate(rel)
        if located is None and inside_scope(rel) and repo.tracked(rel):
            if not repo.tracked_has_content(rel):
                reasons.append('file %s is empty on %s' % (rel, repo.loop_ref))
            continue
        if located is None:
            reasons.append('path %s does not exist inside the root or the private folder, nor on %s' % (
                rel, repo.loop_ref))
        elif located.is_dir() and not run_folder_holds_result(located):
            reasons.append('folder %s holds no non-empty %s, directly or in evidence/' % (rel, ' or '.join(RESULT_FILES)))
        elif not file_has_content(located):
            reasons.append('file %s is empty' % rel)
    return reasons


def claims_in_line(line):
    """True when a Markdown line claims a finished state in one of the declared forms."""
    text = line.strip()
    return any(form.search(text) for form in CLAIM_FORMS)


def fence_toggles(line):
    """True on a line that opens or closes a fenced code block."""
    return line.lstrip().startswith('```')


def holds_state_words(text):
    """True when a record holds a finished-state word outside fenced code."""
    fenced = False
    for line in text.splitlines():
        if fence_toggles(line):
            fenced = not fenced
            continue
        if not fenced and STATE_WORD.search(line):
            return True
    return False


# ---- the records

def ledger_status_errors(text):
    """One failure for every ledger row whose Status does not open with a vocabulary word,
    written in capitals as a whole word."""
    errors = []
    for row in ledger_check.ledger_rows(text):
        status = row['cells'].get('Status', '')
        first = re.match(r'^([A-Za-z]+)(?![\w(-])', status)
        if not first or first.group(1) not in LEDGER_VOCABULARY:
            errors.append('row %s: status %r does not open with one of %s' % (
                row['id'], status[:30], '/'.join(LEDGER_VOCABULARY)))
    return errors


def ledger_claims(text):
    """[Claim] for every ledger row whose Status starts DONE or VERIFIED, its own id the row's."""
    out = []
    for row in ledger_check.ledger_rows(text):
        status = row['cells'].get('Status', '')
        if status.split(' ')[0].rstrip(',') in LEDGER_STATES:
            out.append(Claim('row %s' % row['id'], status + ' ' + row['cells'].get('Evidence or where', ''),
                             row['id']))
    return out


def state_column_claims(text):
    """{line number: Claim} for every row of a table with a State column whose State cell
    opens with a finished-state word (`STATE_WORDS`, all thirteen)."""
    out, header = {}, None
    for number, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith('|'):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-{3,}:?', c) for c in cells if c):
            continue
        if header is None:
            header = cells
            continue
        if 'State' not in header or len(cells) <= header.index('State'):
            continue
        state = cells[header.index('State')]
        if state.split(' ')[0].rstrip('(,;:.').lower() in STATE_WORDS:
            out[number] = Claim('line %d (State)' % number, line)
    return out


def markdown_claims(text, state_column=False):
    """[Claim] for every line of a Markdown record that claims a finished state; with
    `state_column` a table with a State column is read by that column instead; a fenced code
    block is not read."""
    states = state_column_claims(text) if state_column else {}
    in_state_table = set()
    if state_column:
        header = None
        for number, line in enumerate(text.splitlines(), 1):
            if not line.lstrip().startswith('|'):
                header = None
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if header is None:
                header = cells
            if 'State' in header:
                in_state_table.add(number)
    out, fenced = [], False
    for number, line in enumerate(text.splitlines(), 1):
        if fence_toggles(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        if number in states:
            out.append(states[number])
        elif number not in in_state_table and claims_in_line(line):
            out.append(Claim('line %d' % number, line))
    return out


def progress_claims(data):
    """[Claim] for every object of PROGRESS.json whose status is done or verified; a stage's
    id is its own id, removed from its own fields before pointers are read."""
    out = []

    def walk(node, where):
        if isinstance(node, dict):
            if str(node.get('status', '')).strip().lower() in CLAIM_STATES:
                evidence = node.get('evidence', '')
                if isinstance(evidence, list):
                    evidence = ' '.join(map(str, evidence))
                text = ' '.join([str(evidence), str(node.get('name', '')), str(node.get('note', ''))])
                own = str(node['id']) if node.get('id') else None
                if own:
                    text = re.sub(r'(?<![\w-])' + re.escape(own) + r'(?![\w-])', ' ', text)
                label = own or node.get('name') or where
                out.append(Claim('%s (%s)' % (where, str(label)[:60]), text, own))
            for key, value in node.items():
                walk(value, '%s.%s' % (where, key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, '%s[%d]' % (where, index))

    walk(data, '$')
    return out


def issue_claims(issues):
    """([Claim] for every issue closed as completed, count closed as not planned)."""
    out, not_planned = [], 0
    for issue in issues:
        reason = str(issue.get('stateReason') or '').upper()
        if reason in NOT_CLAIMED_REASONS:
            not_planned += 1
            continue
        comments = issue.get('comments') or []
        text = ' '.join(str(c.get('body', '')) if isinstance(c, dict) else str(c) for c in comments)
        out.append(Claim('issue #%s' % issue.get('number'), text))
    return out, not_planned


# ---- the check

def nothing_read(counts):
    return not counts


def check(records, headings, repo, sections=None):
    """records: [(record name, [Claim], lenient_hex, source text or None[, problems])] ->
    (claims, failures, {record name: claim count})."""
    claims, failures, counts = 0, [], {}
    for record in records:
        name, items, lenient, source = record[:4]
        failures.extend('%s %s' % (name, problem) for problem in (record[4] if len(record) > 4 else ()))
        counts[name] = len(items)
        if not items and source is not None and holds_state_words(source):
            failures.append('%s: holds a finished-state word but no claim in a declared form' % name)
        for claim in items:
            claims += 1
            for reason in resolve(pointers(claim.text, lenient, repo), headings, repo, claim.own_id, sections,
                                  name in PUSH_RECORDS):
                failures.append('%s %s: %s' % (name, claim.where, reason))
    return claims, failures, counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--root', default=str(ROOT), help='repository root (default: this checkout)')
    parser.add_argument('--loop-ref', default=DEFAULT_LOOP_REF, help='the loop branch (default %s)' % DEFAULT_LOOP_REF)
    parser.add_argument('--private', help='the private folder (default <root>/%s)' % PRIVATE.as_posix())
    parser.add_argument('--decisions', help='DECISIONS.md (default: read from the loop branch)')
    parser.add_argument('--ledger', help='the request ledger (default <private>/SECKIN_REQUESTS.md if present)')
    parser.add_argument('--loose-ends', help='LOOSE_ENDS.md (default <private>/LOOSE_ENDS.md if present)')
    parser.add_argument('--return-brief', help='RETURN_BRIEF.md (default <private>/RETURN_BRIEF.md if present)')
    parser.add_argument('--for-seckin', help='FOR_SECKIN.md (default <private>/FOR_SECKIN.md if present)')
    parser.add_argument('--push-record', help='PUSH_RECORD.md (default <private>/PUSH_RECORD.md if present)')
    parser.add_argument('--plan', help='AFTER_V1_PLAN.md (default: read from the loop branch)')
    parser.add_argument('--progress', help='PROGRESS.json (default <private>/PROGRESS.json if present)')
    parser.add_argument('--closed-issues', help="gh's closed-issue JSON, a file (never fetched here)")
    parser.add_argument('--push-ref', default=DEFAULT_PUSH_REF,
                        help='the ref a push record\'s commits may be ancestors of (default %s)' % DEFAULT_PUSH_REF)
    parser.add_argument('--fetch-push-ref', action='store_true',
                        help='run a read-only `git fetch origin main` before reading the push ref')
    parser.add_argument('--skip', action='append', default=[], choices=RECORDS,
                        help='a record of D-S101 item 1 deliberately not read this run (repeatable); '
                             'any other absent record fails')
    args = parser.parse_args(argv)

    root = Path(args.root)
    private = Path(args.private) if args.private else root / PRIVATE
    repo = Repository(root, private, args.loop_ref, args.push_ref)
    if args.fetch_push_ref:
        fetched = _git(root, 'fetch', '--quiet', 'origin', 'main')
        if fetched.returncode != 0:
            print('git fetch origin main failed: FAIL')
            return 1
    if _git(root, 'rev-parse', '--verify', args.loop_ref).returncode != 0:
        print('loop branch %s not found under %s: FAIL' % (args.loop_ref, root))
        return 1
    decisions_text = repo.decisions_text(args.decisions)
    headings = set(re.findall(r'^## (D-\d{3,})\.', decisions_text, re.MULTILINE))
    if not headings:
        print('no decision heading read from DECISIONS.md: FAIL')
        return 1
    sections = decision_sections(decisions_text)
    skipped = set(args.skip)

    def given(value, default):
        path = Path(value) if value else private / default
        return path if path.is_file() else None

    records, not_planned, absent = [], 0, []
    ledger = None if 'ledger' in skipped else given(args.ledger, 'SECKIN_REQUESTS.md')
    if ledger:
        text = ledger.read_text(encoding='utf-8')
        records.append(('ledger', ledger_claims(text), False, None, ledger_status_errors(text)))
    elif 'ledger' not in skipped:
        absent.append('ledger')
    for label, value, default, state_column in (
            ('loose ends', args.loose_ends, 'LOOSE_ENDS.md', True),
            ('return brief', args.return_brief, 'RETURN_BRIEF.md', False),
            ('for seckin', args.for_seckin, 'FOR_SECKIN.md', False),
            ('push record', args.push_record, 'PUSH_RECORD.md', False)):
        if label in skipped:
            continue
        path = given(value, default)
        if path:
            text = path.read_text(encoding='utf-8')
            records.append((label, markdown_claims(text, state_column), True, text))
        else:
            absent.append(label)
    if 'plan' not in skipped:
        plan_path = Path(args.plan) if args.plan else None
        plan_text = (plan_path.read_text(encoding='utf-8') if plan_path and plan_path.is_file()
                     else None if plan_path else repo.show(PLAN_PATH))
        if plan_text is not None:
            records.append(('plan', markdown_claims(plan_text), True, plan_text))
        else:
            absent.append('plan')
    if 'progress' not in skipped:
        progress = given(args.progress, 'PROGRESS.json')
        if progress:
            records.append(('progress', progress_claims(json.loads(progress.read_text(encoding='utf-8-sig'))),
                            True, None))
        else:
            absent.append('progress')
    if 'issues' not in skipped:
        closed = Path(args.closed_issues) if args.closed_issues else None
        if closed and closed.is_file():
            issues, not_planned = issue_claims(json.loads(closed.read_text(encoding='utf-8')))
            records.append(('issues', issues, True, None))
        else:
            absent.append('issues')

    claims, failures, counts = check(records, headings, repo, sections)
    failures.extend('%s: absent, and not named with --skip' % name for name in absent)
    if nothing_read(counts):
        failures.append('no record was read')
    for failure in failures:
        print('UNRESOLVED ' + failure)
    if skipped:
        print('not read (skipped by the caller): ' + ', '.join(name for name in RECORDS if name in skipped))
    print('claims per record: ' + ', '.join('%s %d' % item for item in counts.items()))
    print('records read %d; claims %d, unresolved %d, closed as not planned %d (not claims): %s' % (
        len(counts), claims, len(failures), not_planned, 'FAIL' if failures else 'PASS'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
