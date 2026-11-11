"""Check every standing order on the tablet (D-S110 item 2; STANDING-ORDERS-A).

The tablet is `docs/loop/private/STANDING_ORDERS.md`: one table, one numbered order a row, each
with how it is proven to hold now. This script reads that table on every run, so a line the
backfill adds is picked up; a row it cannot read fails. The proof cell opens with its kind:

  script: ...        checked here. A registered checker below, bound to the order's number and
                     guarded by a word of its text (a renumbered tablet fails rather than checking
                     the wrong order); else every gate check the proof names by number ("check 174",
                     "gate checks 176 and 213": only after the words "gate check") is run through
                     scripts/verify_session1.py and must PASS; a script proof with neither is
                     "check not built".
  record: ...        printed as "not checked by code: <record>".
  broken today: ...  printed as broken, as the tablet declares it.
  none               only for an order whose text opens "(withdrawn": printed as withdrawn.
Anything else fails as unreadable. The states (D-426, D-429, D-430), each its own line label:
  kept                the check found the order held;
  kept in part        it held as far as the check reaches, and the check does not reach all of it;
  code proven, not the order   the check proves the code that should keep it, not the order itself;
  nothing to check yet         there is nothing yet the order applies to;
  BROKEN              a violation found;
  check not built     a script proof with no checker and no gate check, or "script (to build):";
  UNABLE TO CHECK     the check could not read what it needs (a checker that raised, an unreadable
                      record, a gate check that did not run);
  not checked by code a record proof; withdrawn for a withdrawn order.
Exit 1 on any broken or unreadable order, and on UNABLE TO CHECK for orders 1 to 3 only; "check
not built" never blocks. One count line, and the result written to `standing_orders_last.json`
beside the tablet with the tablet's digest (read by tools/loop/session_start.py, which says
STALE when the result is over 24 hours old or the tablet changed since).

The registered checkers, and what each reads:
  1  image      every us-east-1 loop launch (launch.json under external/, one per instance)
                from the landing of the launch records check (tools/loop/asset_copy_launch_check.py
                on the loop branch) started from the copy (receipt MATCH and used), or recorded a
                non-empty reason it admits (the first seed of a missing digest; a sealed run);
                the history since 5 November is reported once; an unreadable launch record is
                unable to check. Before the landing every launch since 5 November is read.
  2  API key    every cloud_reference_spend.jsonl close line since D-S106 (9 Nov 14:44 UTC) names
                a FOR_SECKIN heading with exactly one "Seckin: evet (...)" line under it, no two
                run chains share a heading, and its key_source is a name of the repository's
                credential rule (agent_wrapper.candidate_config_paths); earlier lines are counted
                apart.
  3  budget     D-S121's two ceilings, no figure in code. Lambda: the latest budget line gives the
                budget, the hard stop and warning_usd (the reaper's rules; no warning_usd is unable
                to check); the reaper's status is at most 15 minutes old (else unable to check); its
                Lambda spend is below the warning, or FOR_SECKIN holds the warning in its own form
                (a heading naming the warning figure whose entry states the spend in USD and the
                budget); at the budget or more, FOR_SECKIN holds "<budget> doları geçtik" and no
                launch intent follows it. API: the spend store's latest ceiling line (none is unable
                to check); spend past the ceiling is broken; spend and running caps at its warning
                need an API warning in that form (the reaper writes both warnings).
  4  states     tools/loop/status_evidence_check.py passes (`--skip issues`, and `--fetch-push-ref`
                when this script is given it).
  6  fresh read no fresh-set read is recorded (docs/loop/FRESH_READS.md, or an attempt in
                docs/loop/FRESH_ATTEMPTS.json, on the loop branch) unless a scoreboard benchmark
                row's "Gap to (a) / (b)" cell opens with "passed".
  7  metric     every scoreboard benchmark row names a primary metric other than bare accuracy, a
                class setting, and the system's figure with a [low, high] interval.
  8  page       the newest scoreboard benchmark row is not later than the last commit touching
                docs/progress on refs/remotes/origin/main (as read locally).
  10 keys       no key-shaped value (the global pattern) and nothing guard_secrets' own rules
                refuse (scan_line on every added line, is_refused_path on every path) in the
                commits on the loop branch since the last check's loop head, merges included
                (their first-parent diff); the last 24 hours when there is no last check.
  13 held-out   every HELDOUT_OPENINGS row on the loop branch has k at least 1, alpha equal to
                0.05 / 2^k, and a tuning record commit git knows.
  14 disk       free disk under the root at least 30 GiB.
F5 (D-421): a decision that suspends or narrows a standing order says so on a marker line, a
bullet opening `**Suspends.**` or `**Narrows.**` (or a line opening `Suspends:` / `Narrows:`)
naming `order N`; the line must quote the reading it rests on (in double quotes or backticks)
with its time (HH:MM or an ISO time). A marker line without both makes order N broken, whatever
its own check says. Decisions are read from docs/loop/DECISIONS.md on the loop branch.
  19 machine    the factor record's checks pass (tools/factor_record_checks.py: the same-type
                refusal among them).
Standard library and git only; the one network read is `--fetch-push-ref`, passed to order 4.

    py -3.12 -X utf8 tools/loop/standing_orders_check.py --root . [--fetch-push-ref]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import contextlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from cloud_run_common import no_window  # noqa: E402

DEFAULT_LOOP_REF = 'loop/2026-10-27'
PRIVATE = Path('docs') / 'loop' / 'private'
TABLET = 'STANDING_ORDERS.md'
LAST = 'standing_orders_last.json'
KINDS = ('script', 'record', 'broken today', 'script (to build)')
WITHDRAWN = 'none'
SINCE_LAUNCHES = datetime(2026, 11, 4, 21, 0, tzinfo=timezone.utc)   # 5 November 00:00 +0300
SINCE_D_S106 = datetime(2026, 11, 9, 14, 44, tzinfo=timezone.utc)    # 9 November 17:44 +0300
DISK_FLOOR = 30 * 2 ** 30
# The global key patterns, assembled from parts so this file holds none of them whole.
_SK = 'sk' + '-'
KEY_PATTERN = re.compile('|'.join([_SK + 'ant-[A-Za-z0-9_-]{8,}', _SK + 'proj-[A-Za-z0-9_-]{8,}', _SK + '[a-zA-Z0-9]{20,}',
                                   'AK' + 'IA[A-Z0-9]{16}', 'AI' + 'za[A-Za-z0-9_-]{35}',
                                   'api' + r'''_key\s*=\s*["'][A-Za-z0-9_-]{16,}''',
                                   'sec' + r'''ret\s*=\s*["'][A-Za-z0-9_-]{16,}''']), re.IGNORECASE)
EVET = re.compile(r'Seckin: evet \(.+\)')
INTERVAL = re.compile(r'\[\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*\]')
GATE_CHECK = re.compile(r'\bgate checks?\s+(\d{1,3})(?:\s*(?:,|and)\s*(\d{1,3}))*')
STATE_LABEL = {'kept': 'kept', 'kept_in_part': 'kept in part', 'code_only': 'code proven, not the order',
               'nothing_yet': 'nothing to check yet', 'broken': 'BROKEN', 'not_built': 'check not built',
               'unable': 'UNABLE TO CHECK', 'unchecked': 'not checked by code', 'withdrawn': 'withdrawn'}
# UNABLE TO CHECK blocks only these orders (D-429): the launch's image, key and budget.
BLOCKING_UNABLE = frozenset({1, 2, 3})
# Orders whose registered check reaches only part of them, or only the code (D-429), from
# status-tool-check's review: filled by order number when that list is read, never guessed.
PARTIAL = {
    # status-tool-check's list A (D-447): only the numbered checks of the proof run
    24: ('kept_in_part', 'gate check 174 runs; its record part does not'),
    50: ('kept_in_part', 'gate check 292 runs; the controller check\'s start scan does not'),
    # list B: fixture proofs of the code, not a reading of the order's own records
    19: ('code_only', 'factor_record_checks are fixture proofs; no launch\'s machine type is read'),
    23: ('code_only', 'gate check 279 is a fixture proof of round reuse, and the launch checks do not run'),
    26: ('code_only', 'gate check 176 is a parser regression proof; the WORDS-A checks and its record do not run'),
    52: ('code_only', 'gate check 331 is a fixture judge; gate check 174 is the one real scan'),
}
LAUNCH_CHECK = 'tools/loop/asset_copy_launch_check.py'
# The fresh set's folder is never read, never even listed (as tools/loop/upload_losses.py).
SKIP_DIRS = ('D-S56',)
# The receipt's own reasons, each checked by the controller before the launch (lane/tiers F7).
RECEIPT_UPLOAD_REASONS = ('another region', 'sealed run', 'seed of a missing digest')
RECEIPT_ABSENCE_REASONS = ('another region', 'sealed run')
# The controller's own recorded fallbacks to the upload (D-464 item 1): the probe past its deadline,
# an unreachable copy, a failed cp after MATCH; a MISMATCH only when recorded suspect. A MISSING copy
# is always an admitted upload (seeded, refused for room, failed or never reached; D-467 item 1).
# Each is written by the controller, never by hand.
RECEIPT_FALLBACK_STATES = ('PROBE_TIMEOUT', 'UNREACHABLE', 'USE_FAILED')
REAPER_STALE_MINUTES = 15   # the reaper runs every five minutes
UPLOAD_REASONS = ('seed of a missing digest', 'sealed run')
SUSPEND_MARKER = re.compile(r'^\s*(?:[-*]\s+)?(?:\*\*(Suspends|Narrows)\.\*\*|(Suspends|Narrows):)')
ORDER_REF = re.compile(r'\border (\d{1,3})\b')
QUOTED = re.compile(r'"[^"]{3,}"|`[^`]{3,}`')
READ_TIME = re.compile(r'\b\d{1,2}:\d{2}\b|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')
DECISION_HEAD = re.compile(r'^## (D-\d+)\.')


def _git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, creationflags=no_window())


class Context:
    """What the checkers read, one place, so a proof can point every path at fixtures."""

    def __init__(self, root, private=None, loop_ref=DEFAULT_LOOP_REF, fetch_push_ref=False):
        self.root = Path(root)
        self.private = Path(private) if private else self.root / PRIVATE
        self.loop_ref = loop_ref
        self.fetch_push_ref = fetch_push_ref
        self.previous = _json(self.private / LAST) or {}
        self.notes = {}

    def show(self, path):
        shown = _git(self.root, 'show', '%s:%s' % (self.loop_ref, path))
        return shown.stdout if shown.returncode == 0 else None

    def private_text(self, name):
        try:
            return (self.private / name).read_text(encoding='utf-8')
        except OSError:
            return None

    def ledger_rows(self):
        rows = []
        for name in ('budget_ledger.jsonl',):
            text = self.private_text(name) or ''
            for line in text.splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
        return rows


# ---- the tablet

def parse_tablet(text):
    """([order dict], [unreadable reason]) from the tablet's one table."""
    orders, problems, header = [], [], None
    for number, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith('|'):
            if header is not None and orders:
                header = None
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-{3,}:?', c) for c in cells if c):
            continue
        if header is None:
            header = cells
            continue
        if len(cells) != len(header) or len(cells) < 4:
            problems.append('line %d: %d cells where the header has %d' % (number, len(cells), len(header)))
            continue
        row = dict(zip(header, cells))
        try:
            order_no = int(row.get('#', ''))
        except ValueError:
            problems.append('line %d: no order number' % number)
            continue
        proof = row.get('How it is proven to hold now', '')
        kind = next((k for k in KINDS if proof.lower().startswith(k + ':')), None)
        if kind is None and proof.strip().lower() == WITHDRAWN and row.get('Order', '').lstrip().startswith('(withdrawn'):
            kind = 'withdrawn'
        if kind is None:
            problems.append('order %d: its proof opens with none of %s' % (order_no, ', '.join(k + ':' for k in KINDS)))
            continue
        orders.append({'number': order_no, 'order': row.get('Order', ''), 'proof': proof, 'kind': kind})
    if not orders and not problems:
        problems.append('no order read from the tablet')
    return orders, problems


# ---- the checkers: each returns (kept, evidence)

def _iso(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


def _json(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _digest(folder):
    """The asset archive's digest a launch folder records (its declaration, else its manifest)."""
    for name in ('asset_copy_declaration.json', 'execution_manifest.json'):
        record = _json(folder / name) or {}
        archive = record.get('assets_archive')
        value = record.get('assets_sha256') or (archive.get('sha256') if isinstance(archive, dict) else None)
        if value:
            return str(value)
    return None


def launch_records(root):
    """Every launch.json under external/, shallowest first, never entering a SKIP_DIRS folder."""
    found = []
    for folder, dirs, files in os.walk(Path(root) / 'external'):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        if 'launch.json' in files:
            found.append(Path(folder) / 'launch.json')
    return sorted(found, key=lambda p: (len(p.parts), p.as_posix()))


def image_launches(root, unreadable=None):
    """Every loop launch since 5 November, one per instance (a batch entry's copy of the
    session's launch.json is the same launch), oldest first: (epoch, folder, record). A launch
    record that cannot be read is added to `unreadable`."""
    seen, out = set(), []
    for path in launch_records(root):
        record = _json(path)
        try:
            epoch = float((record or {}).get('epoch'))
        except (TypeError, ValueError):
            if unreadable is not None:
                unreadable.append(path.parent.relative_to(root).as_posix())
            continue
        if datetime.fromtimestamp(epoch, timezone.utc) < SINCE_LAUNCHES:
            continue
        ident = record.get('instance_id') or path.parent.as_posix()
        if ident in seen:
            continue
        seen.add(ident)
        out.append((epoch, path.parent, record))
    return sorted(out, key=lambda item: (item[0], item[1].as_posix()))


def launch_check_landing(ctx):
    """When the launch records check first reached the loop branch, or None before it lands."""
    done = _git(ctx.root, 'log', '--diff-filter=A', '--format=%cI', ctx.loop_ref, '--', LAUNCH_CHECK)
    times = [t for t in done.stdout.split() if t] if done.returncode == 0 else []
    return _iso(times[-1]) if times else None


def sealed_run(folder):
    """A sealed run never reads the copy (ASSET-COPY-A): its seal says so."""
    return (_json(Path(folder) / 'seal.json') or {}).get('exposure') == 'sealed'


def uploaded(folder):
    """Whether the launch uploaded the archive: its own `assets_transfer_timing.json`, the record the
    launch records check reads (tools/loop/upload_losses.py, D-467 item 1)."""
    return (Path(folder) / 'assets_transfer_timing.json').is_file()


def judge_launches(ctx, launches):
    """(bad, covered, elsewhere) over us-east-1 launches, in time order. Only a launch that uploaded
    is judged (D-467 item 1): one that ended before the probe, or used the copy, uploaded nothing."""
    bad, covered, elsewhere, seen_digests = [], 0, 0, set()
    for _epoch, folder, record in launches:
        if record.get('region') != 'us-east-1':
            elsewhere += 1
            continue
        covered += 1
        if not uploaded(folder):
            continue
        receipt = _json(folder / 'asset_copy_receipt.json') or {}
        digest = _digest(folder)
        reason = str(receipt.get('upload_reason') or '').strip()
        absence = str(receipt.get('absence_reason') or '').strip()
        if receipt.get('declared') and receipt.get('state') == 'MATCH' and receipt.get('used'):
            ok = True
        elif receipt.get('declared') and receipt.get('state') == 'MISSING':
            ok = True   # the copy was missing: the upload was the only way, seeded or not (D-443, D-467)
        elif reason in RECEIPT_UPLOAD_REASONS or absence in RECEIPT_ABSENCE_REASONS:
            ok = True   # a reason the controller checked before the launch (D-443)
        elif receipt.get('declared') and fallback_recorded(receipt):
            ok = True   # the controller fell back to the upload and recorded why (D-464 item 1)
        else:
            ok = False
        if digest and (receipt.get('used') or receipt.get('seeded')):
            seen_digests.add(digest)   # the filesystem holds this digest from here on
        if not ok:
            why = 'no receipt' if not receipt else 'receipt %s%s' % (
                receipt.get('state') or 'undeclared', ', reason %r' % reason if reason else ', no reason')
            bad.append('%s (%s)' % (folder.relative_to(ctx.root).as_posix(), why))
    return bad, covered, elsewhere


def fallback_recorded(receipt):
    """Whether a declared receipt records one of the controller's own fallbacks (D-464 item 1)."""
    state = receipt.get('state')
    if state in RECEIPT_FALLBACK_STATES:
        return True
    if state == 'MISMATCH':
        return receipt.get('suspect') is True
    return False


def check_image(ctx):
    """F1 (D-421, D-426, D-430): see the module header."""
    unreadable = []
    launches = image_launches(ctx.root, unreadable)
    if unreadable:
        return 'unable', 'launch record(s) cannot be read: ' + ', '.join(unreadable[:5])
    landing = launch_check_landing(ctx)
    since = 'since 5 Nov' if landing is None else 'since the launch check landed (%s)' % landing.isoformat()
    judged = launches if landing is None else [l for l in launches if l[0] >= landing.timestamp()]
    history = '' if landing is None else _image_history(ctx, [l for l in launches if l[0] < landing.timestamp()])
    bad, covered, elsewhere = judge_launches(ctx, judged)
    tail = ('; %d outside us-east-1 not covered' % elsewhere if elsewhere else '') + history
    if bad:
        return 'broken', '%d of %d us-east-1 launches %s did not start from the copy: %s%s' % (
            len(bad), covered, since, ', '.join(bad[:6]) + (' ...' if len(bad) > 6 else ''), tail)
    if not covered:
        return 'nothing_yet', 'no us-east-1 launch %s%s' % (since, tail)
    return 'kept', '%d us-east-1 launches %s, each from the copy or with an admitted reason%s' % (covered, since, tail)


def _image_history(ctx, before):
    """The launches before the landing, reported once (D-426): the first result after the
    landing carries them; later results only say they were reported."""
    if ctx.previous.get('order1_history_reported'):
        return '; the history before the landing was reported at %s' % ctx.previous['order1_history_reported']
    bad, covered, _ = judge_launches(ctx, before)
    ctx.notes['order1_history_reported'] = datetime.now(timezone.utc).isoformat()
    return '; history since 5 Nov, reported once: %d of %d us-east-1 launches did not start from the copy' % (
        len(bad), covered)

def rule_names():
    spec = importlib.util.spec_from_file_location('agent_wrapper', ROOT / 'scripts' / 'agent_wrapper.py')
    module = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        spec.loader.exec_module(module)
    return {name for name, _ in module.candidate_config_paths()}


# The spend store's lines that record a paid run (D-S121): the store also holds the API's own
# ceiling, reserve and skipped lines, which name no FOR_SECKIN heading and are not runs.
SPEND_EVENTS = (None, 'close')


def check_api_key(ctx, names=None):
    store = ctx.private_text('cloud_reference_spend.jsonl') or ''
    seckin = (ctx.private_text('FOR_SECKIN.md') or '').splitlines()
    rows = []
    for line in store.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get('event') in SPEND_EVENTS:
            rows.append(row)
    before = [r for r in rows if (_iso(r.get('time_utc')) or SINCE_D_S106) < SINCE_D_S106]
    after = [r for r in rows if r not in before]
    if not after:
        return True, 'no paid API run closed since D-S106 (%d before it, counted apart)' % len(before)
    try:
        names = rule_names() if names is None else names
    except Exception as exc:  # the credential rule cannot be read: nothing is proven
        return False, 'the credential rule names cannot be read (%s)' % type(exc).__name__
    problems, chains = [], {}
    for row in after:
        approval = row.get('seckin_approved')
        heading = approval.get('heading') if isinstance(approval, dict) else row.get('seckin_approved_heading')
        run = row.get('run_id')
        if not heading:
            problems.append('%s names no FOR_SECKIN heading' % run)
            continue
        heads = [i for i, l in enumerate(seckin) if l.startswith('#') and l.strip() == heading.strip()]
        if len(heads) != 1:
            problems.append('%s: heading %r found %d times in FOR_SECKIN' % (run, heading, len(heads)))
        else:
            end = next((i for i in range(heads[0] + 1, len(seckin)) if seckin[i].startswith('#')), len(seckin))
            if sum(1 for l in seckin[heads[0] + 1:end] if EVET.fullmatch(l.strip())) != 1:
                problems.append('%s: no single "Seckin: evet (...)" line under its heading' % run)
        if row.get('key_source') not in names:
            problems.append('%s: key_source %r is not a name of the credential rule' % (run, row.get('key_source')))
        chain = set(row.get('chain_run_ids_before') or []) | {run}
        for other_run, other_chain in chains.get(heading, []):
            if not (chain & other_chain):
                problems.append('%s and %s, two run chains, share the heading %r' % (run, other_run, heading))
        chains.setdefault(heading, []).append((run, chain))
    if problems:
        return False, '; '.join(problems)
    return True, '%d paid run(s) since D-S106, each with one evet, one chain and a rule-named key source' % len(after)


def _budget_lines(rows):
    return [r for r in rows if r.get('event') in ('budget_open', 'budget_change')]


def _seckin_heading_times(lines, needle):
    out = []
    for line in lines:
        match = re.match(r'^## (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) \+0300', line)
        if match and needle in line:
            out.append(datetime.fromisoformat('%sT%s:00+03:00' % match.groups()))
    return out


def _figure(value):
    return '%g' % float(value)


def _names(text, value):
    """Whether the text writes this figure as a number of its own (not inside a longer one)."""
    return re.search(r'(?<![\d.])%s(?![\d]|\.\d)' % re.escape(_figure(value)), text) is not None


def warning_entries(lines, warning, stop, kind=None):
    """The warnings in their own form (D-S103 item 2, D-S121): a heading naming the warning figure
    (and the kind, where given) whose entry states the spend in USD and the stop figure. The figures
    are the ledger's and the store's, never a code constant."""
    out = []
    for i, line in enumerate(lines):
        if line.startswith('## ') and _names(line, warning) and (kind is None or kind in line):
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith('## ')), len(lines))
            body = '\n'.join(lines[i + 1:end])
            if re.search(r'\d[\d.,]*\s*USD', body) and _names(body, stop):
                out.append(line)
    return out


def budget_figures(rows):
    """(budget, hard stop) by the reaper's own rule (instance_reaper.budget_figures)."""
    sys.path.insert(0, str(ROOT / 'tools' / 'loop'))
    import instance_reaper
    return instance_reaper.budget_figures(rows)


def warning_figure(rows):
    """The Lambda warning by the reaper's own rule (instance_reaper.warning_figure, D-S121)."""
    sys.path.insert(0, str(ROOT / 'tools' / 'loop'))
    import instance_reaper
    return instance_reaper.warning_figure(rows)


def api_budget(ctx, seckin):
    """(state, evidence) for the API ceiling (D-S121): read from the spend store's latest ceiling
    line; at its warning FOR_SECKIN holds an API warning in its form; spend past it is broken."""
    sys.path.insert(0, str(ROOT / 'tools' / 'loop'))
    import cloud_reference_spend as spend
    store = ctx.private / 'cloud_reference_spend.jsonl'
    try:
        limits = spend.ceiling(store)
        figures = spend.state(store)
    except spend.SpendStoreError as exc:
        return 'unable', str(exc)
    if limits is None:
        return 'unable', 'the API spend store holds no ceiling line (D-S121)'
    used = figures['spent_usd'] + figures['running_caps_usd']
    if figures['spent_usd'] > limits['ceiling_usd']:
        return False, 'API spend %.2f is past its ceiling %s' % (figures['spent_usd'], _figure(limits['ceiling_usd']))
    if used >= limits['warning_usd'] and not warning_entries(seckin, limits['warning_usd'], limits['ceiling_usd'], 'API'):
        return False, ('API spend and running caps %.2f are at or past its warning %s and FOR_SECKIN holds no API '
                       'warning in its form' % (used, _figure(limits['warning_usd'])))
    return True, 'API %.2f of %s (warning %s)' % (used, _figure(limits['ceiling_usd']), _figure(limits['warning_usd']))


def answered(lines, heading):
    """Whether a "Seckin:" answer line stands under this FOR_SECKIN heading."""
    try:
        start = lines.index(heading)
    except ValueError:
        return False
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('## ')), len(lines))
    return any(line.strip().startswith('Seckin:') for line in lines[start + 1:end])


def check_budget(ctx):
    rows = ctx.ledger_rows()
    budget, hard_stop = budget_figures(rows)
    if budget is None:
        return False, 'no readable budget line in the ledger'
    warning = warning_figure(rows)
    if warning is None:
        return 'unable', 'no budget line names warning_usd (D-S121): the Lambda warning is not a code figure'
    try:
        status = json.loads(ctx.private_text('reaper_status.json') or '{}')
        spend = float(status.get('total_spend_usd'))
    except (TypeError, ValueError, AttributeError):
        return 'unable', 'no Lambda spend readable from reaper_status.json'
    last = _iso(status.get('last_run_utc'))
    if last is None or (datetime.now(timezone.utc) - last).total_seconds() > REAPER_STALE_MINUTES * 60:
        return 'unable', 'the reaper\'s spend reading is stale (last pass %s)' % status.get('last_run_utc')
    seckin = (ctx.private_text('FOR_SECKIN.md') or '').splitlines()
    if spend >= warning and not warning_entries(seckin, warning, budget):
        return False, ('Lambda spend %.2f is at or past %s and FOR_SECKIN holds no warning in its form (a heading '
                       'naming %s whose entry states the spend in USD and the %s stop)'
                       % (spend, _figure(warning), _figure(warning), _figure(budget)))
    if status.get('error'):
        return 'unable', 'the reaper\'s last pass recorded an error'
    if spend >= budget:
        words = '%s doları geçtik' % _figure(budget)
        headings = [l for l in seckin if l.startswith('## ') and words in l]
        crossed = _seckin_heading_times(headings, words)
        if not crossed:
            return False, 'Lambda spend %.2f is past %s and FOR_SECKIN does not say "%s"' % (spend, _figure(budget), words)
        if not any(answered(seckin, h) for h in headings):
            # an untimed intent cannot be shown to precede the crossing: it counts as after it
            later = [r for r in rows if r.get('event') == 'launch_intent'
                     and (_iso(r.get('time_utc')) is None or _iso(r.get('time_utc')) > min(crossed))]
            if later:
                return False, '%d launch intent(s) after "%s" with no "Seckin:" answer under it' % (len(later), words)
    api_state, api_said = api_budget(ctx, seckin)
    if api_state is not True:
        return api_state, api_said
    return True, ('budget %s, hard stop %s, warning %s (the reaper\'s rule); Lambda spend %.2f; %s'
                  % (budget, hard_stop, _figure(warning), spend, api_said))


def check_states(ctx):
    argv = [sys.executable, '-X', 'utf8', str(ROOT / 'tools' / 'loop' / 'status_evidence_check.py'),
            '--root', str(ctx.root), '--private', str(ctx.private), '--loop-ref', ctx.loop_ref, '--skip', 'issues']
    if ctx.fetch_push_ref:
        argv.append('--fetch-push-ref')
    done = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', creationflags=no_window())
    last = (done.stdout.strip().splitlines() or ['no output'])[-1]
    return done.returncode == 0, 'status_evidence_check: ' + last


def _scoreboard_rows(ctx):
    text = ctx.private_text('GATE_SCOREBOARD.md') or ''
    rows, header, in_section = [], None, False
    for line in text.splitlines():
        if line.startswith('## '):
            in_section = line.strip() == '## Benchmark rows'
            header = None
            continue
        if not in_section or not line.lstrip().startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-{3,}:?', c) for c in cells if c):
            continue
        if header is None:
            header = cells
            continue
        row = dict(zip(header, cells))
        if row.get('Row', '').startswith('(none'):
            continue
        rows.append(row)
    return rows


def check_fresh_read(ctx):
    reads = bool(ctx.show('docs/loop/FRESH_READS.md'))
    attempts = ctx.show('docs/loop/FRESH_ATTEMPTS.json')
    try:
        reads = reads or bool(json.loads(attempts or '{}').get('attempts'))
    except ValueError:
        return False, 'docs/loop/FRESH_ATTEMPTS.json on the loop branch cannot be read'
    if not reads:
        return 'nothing_yet', 'no fresh-set read recorded'
    read_at = first_commit_time(ctx, ('docs/loop/FRESH_READS.md', 'docs/loop/FRESH_ATTEMPTS.json'))
    passed = []
    for r in _scoreboard_rows(ctx):
        if not r.get('Gap to (a) / (b)', '').lower().startswith('passed'):
            continue
        try:
            when = datetime.fromisoformat(r.get('Time', '').strip() + ':00+03:00')
        except ValueError:
            return 'unable', 'scoreboard row %s has no readable time' % r.get('Row')
        if read_at is not None and when <= read_at:
            passed.append(r)
    if passed:
        return True, 'the fresh-set read (%s) follows a passing scoreboard row (%s)' % (read_at.isoformat(), passed[0].get('Row'))
    return False, 'a fresh-set read is recorded and no scoreboard row passed the gate before it'


def first_commit_time(ctx, paths):
    """When the first of these paths first reached the loop branch, or None."""
    times = []
    for path in paths:
        done = _git(ctx.root, 'log', '--diff-filter=A', '--format=%cI', ctx.loop_ref, '--', path)
        times += [_iso(t) for t in done.stdout.split() if _iso(t)]
    return min(times) if times else None


def check_metric(ctx):
    if not _scoreboard_rows(ctx):
        return 'nothing_yet', 'no scoreboard benchmark row yet'
    bad = []
    for row in _scoreboard_rows(ctx):
        metric = row.get('Primary metric (D-S99)', '').strip()
        if not metric or metric.lower() == 'accuracy' or not row.get('Class setting', '').strip() \
                or not INTERVAL.search(row.get('System (95% CI)', '')):
            bad.append(row.get('Row') or '?')
    if bad:
        return False, 'scoreboard rows without a primary metric, class setting or interval: ' + ', '.join(bad)
    return True, '%d scoreboard benchmark row(s), each with its metric, setting and interval' % len(_scoreboard_rows(ctx))


def check_page(ctx):
    rows = _scoreboard_rows(ctx)
    times = []
    for row in rows:
        try:
            times.append(datetime.fromisoformat(row.get('Time', '').strip() + ':00+03:00'))
        except ValueError:
            return False, 'scoreboard row %s has no readable time' % row.get('Row')
    if not times:
        return 'nothing_yet', 'no scoreboard row yet, nothing to publish'
    pushed = _git(ctx.root, 'log', '-1', '--format=%cI', 'refs/remotes/origin/main', '--', 'docs/progress')
    try:
        last = datetime.fromisoformat(pushed.stdout.strip())
    except ValueError:
        return False, 'no commit touching docs/progress on refs/remotes/origin/main'
    if max(times) > last:
        return False, 'the newest row (%s) is later than the page\'s last push (%s)' % (max(times).isoformat(), last.isoformat())
    return True, 'the page\'s last push (%s) follows the newest row' % last.isoformat()


def guard_rules(ctx):
    """guard_secrets' own scan_line and is_refused_path, loaded from the loop branch's file."""
    source = ctx.show('scripts/guard_secrets.py')
    if source is None:
        return None
    namespace = {'__name__': 'guard_secrets_loop', '__file__': str(ctx.root / 'scripts' / 'guard_secrets.py')}
    exec(compile(source, 'guard_secrets.py', 'exec'), namespace)
    return namespace['scan_line'], namespace['is_refused_path']


def key_span(ctx):
    """(git log range, words): the commits since the last check's loop head when git knows it as
    an ancestor, else the last 24 hours. Records this run's head for the next."""
    ctx.notes['loop_head'] = _git(ctx.root, 'rev-parse', ctx.loop_ref).stdout.strip()
    previous = ctx.previous.get('loop_head')
    if previous and _git(ctx.root, 'merge-base', '--is-ancestor', previous, ctx.loop_ref).returncode == 0:
        return ['%s..%s' % (previous, ctx.loop_ref)], 'since the last check (%s)' % previous[:8]
    return ['--since=24.hours', ctx.loop_ref], 'in the last 24 hours'


def check_keys(ctx):
    try:
        rules = guard_rules(ctx)
    except Exception as exc:
        return 'unable', 'guard_secrets cannot be loaded (%s)' % type(exc).__name__
    if rules is None:
        return False, 'scripts/guard_secrets.py is not on the loop branch'
    scan_line, refused_path = rules
    span, said = key_span(ctx)
    log = _git(ctx.root, 'log', '-p', '--diff-merges=first-parent', '--format=commit %H', *span)
    if log.returncode != 0:
        return 'unable', 'git log on the loop branch failed'
    hits, commit, path = [], '', ''
    for line in log.stdout.splitlines():
        if line.startswith('commit '):
            commit = line[len('commit '):][:8]
        elif line.startswith('+++ b/'):
            path = line[len('+++ b/'):]
            if refused_path(path):
                hits.append('%s in %s (a path guard_secrets refuses)' % (path, commit))
        elif line.startswith('+') and not line.startswith('+++') and (KEY_PATTERN.search(line) or list(scan_line(line[1:]))):
            hits.append('%s in %s' % (path, commit))
    if hits:
        # Where, never the value: the lead reads the line and decides whether it is a key.
        return False, '%d added line(s) or path(s) %s match a key pattern or a guard_secrets rule: %s' % (
            len(hits), said, ', '.join(sorted(set(hits))))
    return True, 'no key-shaped value or refused path added on the loop branch %s' % said


def check_heldout(ctx):
    text = ctx.show('docs/loop/HELDOUT_OPENINGS.md')
    if text is None:
        return False, 'docs/loop/HELDOUT_OPENINGS.md is not on the loop branch'
    problems, rows, header = [], 0, None
    for line in text.splitlines():
        if not line.lstrip().startswith('|'):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-{3,}:?', c) for c in cells if c):
            continue
        if header is None:
            header = cells
            continue
        row = dict(zip(header, cells))
        rows += 1
        try:
            k, alpha = int(row.get('k', '')), float(row.get('Alpha', ''))
        except ValueError:
            problems.append('%s: k or alpha unreadable' % row.get('Part'))
            continue
        if k < 1 or abs(alpha - 0.05 / 2 ** k) > 1e-9:
            problems.append('%s: alpha %s is not 0.05/2^%d' % (row.get('Part'), alpha, k))
        commit = next(iter(re.findall(r'\b[0-9a-f]{7,40}\b', row.get('Tuning pass record (commit)', ''))), None)
        if commit is None or _git(ctx.root, 'cat-file', '-e', commit + '^{commit}').returncode != 0:
            problems.append('%s: no tuning record commit git knows' % row.get('Part'))
    if problems:
        return False, '; '.join(problems)
    if not rows:
        return 'nothing_yet', 'no held-out opening recorded'
    return True, '%d opening(s), each at 0.05/2^k with a known tuning record' % rows


def check_disk(ctx):
    free = shutil.disk_usage(ctx.root).free
    return free >= DISK_FLOOR, 'free disk %.1f GiB (floor 30)' % (free / 2 ** 30)


def check_machine(ctx):
    spec = importlib.util.spec_from_file_location('factor_record_checks', ROOT / 'tools' / 'factor_record_checks.py')
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / 'tools'))
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        spec.loader.exec_module(module)
        status, detail = module.check()
    return status == 'PASS', 'factor_record_checks: %s' % status


# Order 35 (D-S84, D-S107 item 3, D-412 item 4): the reaper runs, and the sign-out task runs the
# main checkout's hook, a file that exists, read again at every wake.
REAPER_TASK = 'ShimmerLoopReaper'
SESSION_TASK = 'ShimmerLoopSessionEnd'
HOOK_SCRIPT = 'tools/loop/session_end_salvage.py'


def schtasks_xml(name):
    """The task's XML as schtasks prints it, or None when no such task is registered."""
    try:
        done = subprocess.run(['schtasks', '/Query', '/TN', name, '/XML'], capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL, creationflags=no_window())
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 and '<Task' in done.stdout else None


def check_salvage_tasks(ctx):
    problems = []
    try:
        status = json.loads((ctx.private / 'reaper_status.json').read_text(encoding='utf-8'))
        last = _iso(status.get('last_run_utc'))
    except (OSError, ValueError, AttributeError):
        status, last = {}, None
    age = None if last is None else (datetime.now(timezone.utc) - last).total_seconds() / 60
    if age is None or age > REAPER_STALE_MINUTES:
        problems.append('the reaper last ran %s' % ('never (no readable reaper_status.json)' if age is None
                                                    else '%d minutes ago (at most %d)' % (age, REAPER_STALE_MINUTES)))
    elif status.get('error'):
        problems.append('the reaper\'s last pass recorded an error')
    if schtasks_xml(REAPER_TASK) is None:
        problems.append('%s is not registered' % REAPER_TASK)
    xml = schtasks_xml(SESSION_TASK)
    if xml is None:
        problems.append('the sign-out task %s is not registered' % SESSION_TASK)
    else:
        found = re.search(r'<Arguments>[^<]*?"([^"<]+)"', xml)
        script = Path(found.group(1)) if found else None
        main = (ctx.root / HOOK_SCRIPT).resolve()
        if script is None or not script.is_file():
            problems.append('the sign-out task runs %s, which does not exist' % (script or 'no script'))
        elif script.resolve() != main:
            problems.append('the sign-out task runs %s, not the main checkout\'s %s' % (script, HOOK_SCRIPT))
    if problems:
        return False, '; '.join(problems)
    return True, 'the reaper ran %d minutes ago; %s registered; %s runs the main checkout\'s %s' % (
        age, REAPER_TASK, SESSION_TASK, HOOK_SCRIPT)


def _ledger_tool(ctx, script, extra=()):
    """(exit code, last line) of one of the ledger tools of this checkout, on the private ledger
    and the loop branch's specification and decisions."""
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        files = {}
        for name, path in (('spec', 'prompts/SHIMMER_AUTONOMOUS_LOOP_2026-10-27.md'), ('decisions', 'docs/loop/DECISIONS.md')):
            # the specification is the operator's file in the root (never committed); the decisions the loop branch's
            text = ctx.show(path) if name == 'decisions' else (ctx.root / path).read_text(encoding='utf-8')
            if text is None:
                raise OSError('%s is not on the loop branch' % path)
            files[name] = Path(folder) / (name + '.md')
            files[name].write_text(text, encoding='utf-8')
        argv = [sys.executable, '-X', 'utf8', str(ROOT / 'tools' / 'loop' / script), '--ledger',
                str(ctx.private / 'SECKIN_REQUESTS.md'), '--decisions', str(files['decisions'])]
        if script == 'request_ledger_check.py':
            argv += ['--spec', str(files['spec']), '--root', str(ctx.root)]
        done = subprocess.run(argv + list(extra), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', creationflags=no_window())
    return done.returncode, (done.stdout.strip().splitlines() or ['no output'])[-1]


ISSUES_FILE = 'open_issues.json'   # gh issue list ... --json, saved by issues-keeper; never fetched here


def check_deferral_issues(ctx):
    issues = ctx.private / ISSUES_FILE
    if not issues.is_file():
        return 'unable', 'no saved issue list (%s) to read' % ISSUES_FILE
    code, last = _ledger_tool(ctx, 'issue_deferral_check.py', ['--issues', str(issues)])
    return ('kept_in_part' if code == 0 else 'broken'), 'issue_deferral_check: %s (the FOR_SECKIN push part is not checked)' % last


def check_ledger(ctx):
    code, last = _ledger_tool(ctx, 'request_ledger_check.py')
    if code != 0:
        return False, 'request_ledger_check: ' + last
    issues = ctx.private / ISSUES_FILE
    if not issues.is_file():
        return 'unable', 'request_ledger_check passes; no saved issue list (%s) for issue_deferral_check' % ISSUES_FILE
    code, other = _ledger_tool(ctx, 'issue_deferral_check.py', ['--issues', str(issues)])
    return code == 0, 'request_ledger_check: %s; issue_deferral_check: %s' % (last, other)


def check_ledger_rows(ctx):
    code, last = _ledger_tool(ctx, 'request_ledger_check.py')
    if re.search(r'\bmissing 0\b', last):
        return 'kept_in_part', 'every Annex D item has a row (%s); the decisions part is a record' % last
    return False, 'request_ledger_check: ' + last


CHECKERS = {
    1: ('image', check_image),
    2: ('API key', check_api_key),
    3: ('Budget', check_budget),
    4: ('Four states', check_states),
    6: ('fresh read', check_fresh_read),
    7: ('metric', check_metric),
    8: ('progress page', check_page),
    10: ('API key value', check_keys),
    13: ('held-out', check_heldout),
    14: ('disk', check_disk),
    19: ('machine type', check_machine),
    30: ('not now', check_deferral_issues),
    31: ('request ledger', check_ledger),
    35: ('salvage', check_salvage_tasks),
    48: ('verbatim', check_ledger_rows),
}


def gate_numbers(proof):
    """The gate check numbers a script proof names ("check 174", "checks 176 and 213")."""
    out = []
    for match in GATE_CHECK.finditer(proof.split('record:')[0]):
        out.extend(int(n) for n in re.findall(r'\d{1,3}', match.group(0)))
    return out


def run_gate_checks(numbers, root=ROOT):
    """{number: status} for the named gate checks, run in a child gate process through the
    gate's own `--checks` and `--results` flags (one line per check), never imported here."""
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        results_path = Path(folder) / 'results.jsonl'
        subprocess.run([sys.executable, '-X', 'utf8', str(Path(root) / 'scripts' / 'verify_session1.py'),
                        '--checks', ','.join(str(n) for n in numbers), '--results', str(results_path)],
                       cwd=str(root), stdin=subprocess.DEVNULL, capture_output=True, creationflags=no_window(),
                       env=dict(os.environ, KMP_DUPLICATE_LIB_OK='TRUE'))  # the laptop's known OpenMP clash
        results = {n: 'MISSING' for n in numbers}
        try:
            lines = results_path.read_text(encoding='utf-8').splitlines()
        except OSError:
            lines = []
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get('number') in results:
                results[row['number']] = row.get('status')
    return results


def unquoted_suspensions(ctx):
    """{order number: [decision ids]} for marker lines that suspend or narrow an order without
    quoting the reading they rest on, with its time (F5)."""
    text = ctx.show('docs/loop/DECISIONS.md') or ''
    out, decision = {}, None
    for line in text.splitlines():
        head = DECISION_HEAD.match(line)
        if head:
            decision = head.group(1)
            continue
        if not SUSPEND_MARKER.match(line):
            continue
        if QUOTED.search(line) and READ_TIME.search(line):
            continue
        for number in ORDER_REF.findall(line):
            out.setdefault(int(number), []).append(decision or '?')
    return out


def _verdict(value):
    """A checker's answer as (state, evidence): True and False read as kept and broken."""
    state, evidence = value
    if isinstance(state, bool):
        state = 'kept' if state else 'broken'
    if state not in STATE_LABEL:
        raise ValueError('unknown state %r' % state)
    return state, evidence


def judge(order, ctx, gate_runner=run_gate_checks):
    """(state, evidence) for one order, one of STATE_LABEL's states."""
    if order['kind'] == 'withdrawn':
        return 'withdrawn', order['order'].strip()
    if order['kind'] == 'record':
        return 'unchecked', 'not checked by code: ' + order['proof'][len('record:'):].strip()
    if order['kind'] == 'broken today':
        return 'broken', 'declared broken on the tablet: ' + order['proof'][len('broken today:'):].strip()
    if order['kind'] == 'script (to build)':
        # A proof not built yet proves nothing, and is not a violation found (D-426).
        return 'not_built', order['proof'][len('script (to build):'):].strip()
    bound = CHECKERS.get(order['number'])
    if bound is not None:
        word, checker = bound
        if word.lower() not in order['order'].lower():
            return 'unable', 'the checker bound to order %d (%r) does not match its text: renumbered?' % (
                order['number'], word)
        try:
            state, evidence = _verdict(checker(ctx))
        except Exception as exc:  # the check could not read what it needs: not a violation found
            return 'unable', 'its checker raised %s' % type(exc).__name__
        if state == 'kept' and order['number'] in PARTIAL:
            state, why = PARTIAL[order['number']]
            evidence = '%s (%s)' % (evidence, why)
        return state, evidence
    numbers = gate_numbers(order['proof'])
    if not numbers:
        return 'not_built', 'a script proof with no checker and no gate check named'
    results = gate_runner(numbers)
    said = 'gate checks: ' + ', '.join('%d %s' % (n, results.get(n)) for n in numbers)
    if any(results.get(n) == 'FAIL' for n in numbers):
        return 'broken', said
    if all(results.get(n) == 'PASS' for n in numbers):
        if order['number'] in PARTIAL:
            state, why = PARTIAL[order['number']]
            return state, '%s (%s)' % (said, why)
        return 'kept', said
    return 'unable', said


# The progress page's reading (demo-console): the tag, the proof kind and a state in its words.
PUBLIC_TAG = '[public]'
PAGE_PROOF = {'script': 'script', 'script (to build)': 'script', 'record': 'record', 'broken today': 'broken today',
              'withdrawn': 'none'}
PAGE_STATE = {'kept': 'kept', 'kept_in_part': 'kept_in_part', 'code_only': 'code_only', 'nothing_yet': 'nothing_yet',
              'broken': 'broken', 'not_built': 'not_built', 'unable': 'unable', 'unchecked': 'not_checked',
              'withdrawn': 'withdrawn'}


def launch_refusals(ctx, numbers=(1, 2, 3)):
    """[(order, state, evidence)] for each of these orders that stops a launch (F1, D-430): broken
    or unable to check. The guard and the preflight call this, never a checker's truthiness."""
    out = []
    for number in numbers:
        word, checker = CHECKERS[number]
        try:
            state, evidence = _verdict(checker(ctx))
        except Exception as exc:
            state, evidence = 'unable', 'its checker raised %s' % type(exc).__name__
        if state in ('broken', 'unable'):
            out.append((number, state, evidence))
    return out


def blocks(number, state):
    """Whether an order in this state stops the step it guards."""
    return state == 'broken' or (state == 'unable' and number in BLOCKING_UNABLE)


def run(ctx, tablet_text, gate_runner=run_gate_checks, only=None):
    orders, problems = parse_tablet(tablet_text)
    try:
        unquoted = unquoted_suspensions(ctx)
    except Exception as exc:  # the decisions cannot be read: said, never taken as clean
        unquoted, problems = {}, problems + ['the decisions cannot be read for F5 (%s)' % type(exc).__name__]
    if only:
        missing = sorted(set(only) - {order['number'] for order in orders})
        orders = [order for order in orders if order['number'] in only]
        problems = problems + ['order %d is not on the tablet' % n for n in missing]
    lines, counts, blocking = [], {state: 0 for state in STATE_LABEL}, []
    for order in orders:
        state, evidence = judge(order, ctx, gate_runner)
        if order['number'] in unquoted and state != 'withdrawn':
            state, evidence = 'broken', '%s suspend(s) or narrow(s) it without quoting the reading and its time (F5); %s' % (
                ', '.join(unquoted[order['number']]), evidence)
        counts[state] += 1
        if blocks(order['number'], state):
            blocking.append(order['number'])
        label = STATE_LABEL[state]
        text = order['order'].strip()
        public = text.startswith(PUBLIC_TAG)
        lines.append({'number': order['number'], 'state': state, 'n': order['number'], 'public': public,
                      'text': text[len(PUBLIC_TAG):].strip() if public else text,
                      'proof': PAGE_PROOF.get(order['kind'], order['kind']),
                      'page_state': PAGE_STATE[state],
                      'line': 'order %d %s: %s' % (order['number'], label, evidence if state != 'unchecked'
                                                   else evidence[len('not checked by code: '):])})
    now = datetime.now(timezone.utc).isoformat()
    result = {'time_utc': now, 'checked_utc': now, 'orders': lines, 'unreadable': problems, 'counts': counts,
              'blocking': blocking, 'ok': not problems and not blocking,
              'tablet_sha256': hashlib.sha256(tablet_text.encode('utf-8')).hexdigest()}
    result.update(ctx.notes)
    for key in ('order1_history_reported', 'loop_head'):
        if key not in result and ctx.previous.get(key):
            result[key] = ctx.previous[key]
    return result


def count_line(counts, unreadable):
    """One count per state, in STATE_LABEL's order, and the unreadable rows."""
    return ', '.join('%d %s' % (counts.get(state, 0), STATE_LABEL[state].lower()) for state in STATE_LABEL) + \
        ', %d unreadable' % unreadable


def main(argv=None):
    parser = argparse.ArgumentParser(description='Check every standing order on the tablet (D-S110).')
    parser.add_argument('--root', default=str(ROOT))
    parser.add_argument('--private', help='the private folder (default <root>/%s)' % PRIVATE.as_posix())
    parser.add_argument('--loop-ref', default=DEFAULT_LOOP_REF)
    parser.add_argument('--tablet', help='the tablet (default <private>/%s)' % TABLET)
    parser.add_argument('--result', help='where the result goes (default <private>/%s)' % LAST)
    parser.add_argument('--fetch-push-ref', action='store_true', help='passed to status_evidence_check (order 4)')
    parser.add_argument('--only', help='check only these orders (comma-separated), e.g. --only 1 before every launch '
                                       '(F1, D-421); the full result file is then left as it was')
    args = parser.parse_args(argv)
    ctx = Context(args.root, args.private, args.loop_ref, args.fetch_push_ref)
    tablet = Path(args.tablet) if args.tablet else ctx.private / TABLET
    try:
        text = tablet.read_text(encoding='utf-8')
    except OSError:
        print('the tablet %s cannot be read: FAIL' % tablet)
        return 1
    only = sorted({int(n) for n in args.only.split(',') if n.strip()}) if args.only else None
    result = run(ctx, text, only=only)
    for problem in result['unreadable']:
        print('UNREADABLE ' + problem)
    for line in result['orders']:
        print(line['line'])
    c = result['counts']
    print('standing orders: ' + count_line(c, len(result['unreadable'])) + ': ' + ('PASS' if result['ok'] else 'FAIL'))
    if only and not args.result:
        return 0 if result['ok'] else 1
    out = Path(args.result) if args.result else ctx.private / LAST
    try:
        out.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding='utf-8')
    except OSError:
        pass
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
