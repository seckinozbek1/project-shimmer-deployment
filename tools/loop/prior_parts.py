#!/usr/bin/env python3
"""A hand launch of a measurement's part N+1 refuses while an earlier part has a failed table (beta item 25, OPEN_ITEMS 174).

The table tool measurement's V2 parts were launched by hand on 20 November 2026 while OFF V1 had four tables with
exit 2; the launch chain would have held them, the hand path had no such check. This module is the one reading both
paths use: every launch folder's launch.py loads it from the main checkout by path and calls `refusal` in its
preflight for a part step, so `launch.py <part>` by hand and `launch.py preflight <part>` from the chain refuse alike.

What it reads, all from files the controller already writes (no ledger, no model, no reply, never through a link):
- the parts of the folder in plan.json order (`bundles`: part -> bundle names); the parts before the named one are
  the earlier parts;
- the earlier parts of the other arms of the same measurement: the folders plan.json names in `prior_arms` (names
  of sibling launch folders), and any sibling folder whose plan.json declares the same non-empty `bench` and `set`
  and an `arm` of its own (the table tool measurement's ON and OFF folders); an arm's part counts as earlier when
  its place in that arm's order is before the named part's place in this folder;
- each earlier part's run folder, admitted/<first bundle> (a retry's <first bundle>.N, the highest N, when there):
  one workload_return.json per table under batch/NN_* for a batch, else workload_return.json at its top, plus
  controller_failure.json and the ending files (TERMINATION_VERIFIED.json, CURRENT_PHASE.json terminated_and_cleaned).

An earlier part is a problem when a table returned a non-zero or unreadable exit code, when a table has
entry_failure.json (the controller ended it after its transport failed), when the controller wrote
controller_failure.json, or when the part ended with fewer tables returned than it has bundles or with a returned
table lacking collected_evidence.tar.gz (the chain's batch reading needs one per table). A part has ended when
TERMINATION_VERIFIED.json or CURRENT_PHASE terminated_and_cleaned is there, when the ledger's last launch or
termination line for its purpose (plan.json purposes) is a termination, or when CURRENT_PHASE.json is older than
STALE_PHASE_HOURS (a controller killed with nothing written). A part not launched or still running is not a problem
(parts may run side by side). A decision id (D-NNN, given as
`launch.py <part> --decision D-NNN`) lets the launch go on, and the refusal is printed with it.

A launch folder's launch.py uses it so (docs/loop/LAUNCH_CHAIN.md, "Earlier parts"):
    spec = importlib.util.spec_from_file_location('prior_parts', M / 'tools' / 'loop' / 'prior_parts.py')
    ...; problem = module.refusal(HERE, step, decision)      # None, or one line for preflight's problems
A launcher that cannot load the module refuses the part (it never launches on an unread earlier part).

    py -3.12 -X utf8 tools/loop/prior_parts.py LAUNCH_FOLDER PART [--decision D-NNN]
prints the reading and exits 1 on a refusal. Read-only: nothing is written, created or deleted.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

DECISION = re.compile(r'^D-\d+$')
ENDED_PHASE = 'terminated_and_cleaned'
SHOWN = 4                      # failed tables named in a refusal line
STALE_PHASE_HOURS = 6.0        # a CURRENT_PHASE.json older than this with no ending record: the controller is gone
EVIDENCE = 'collected_evidence.tar.gz'
LEDGER = None                  # the ledger path; None: the main checkout's (tools/loop/shared_paths.py)


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _is_link(path):
    try:
        p = Path(path)
        return p.is_symlink() or bool(getattr(p, 'is_junction', lambda: False)())
    except OSError:
        return True


def _through_links(base, path):
    """True when any step from base down to path is a link or a junction (never followed)."""
    base, path = Path(base), Path(path)
    try:
        parts = path.relative_to(base).parts
    except ValueError:
        return True
    current = base
    for part in parts:
        current = current / part
        if _is_link(current):
            return True
    return False


def plan_of(folder):
    plan = _json(Path(folder) / 'plan.json')
    return plan if isinstance(plan, dict) else {}


def parts_of(plan):
    bundles = plan.get('bundles') or {}
    return [(p, b) for p, b in bundles.items() if isinstance(b, list) and b and all(isinstance(x, str) for x in b)]


def run_folder(folder, bundles):
    """admitted/<first bundle>, or its highest retry <first bundle>.N; None when neither is there."""
    base, name = Path(folder) / 'admitted', bundles[0]
    found = []
    if (base / name).is_dir():
        found.append((1, base / name))
    try:
        entries = list(base.iterdir())
    except OSError:
        entries = []
    for item in entries:
        head, dot, tail = item.name.rpartition('.')
        if dot and head == name and tail.isdigit() and int(tail) >= 2 and item.is_dir():
            found.append((int(tail), item))
    found = [(n, f) for n, f in found if not _through_links(folder, f)]
    return max(found)[1] if found else None


def phase_age_hours(run):
    """Hours since CURRENT_PHASE.json was written (its epoch, else the file time); None when it cannot be read."""
    path = run / 'CURRENT_PHASE.json'
    if not path.is_file():
        return None
    current = _json(path)
    try:
        epoch = current.get('epoch') if isinstance(current, dict) else None
        epoch = float(epoch) if isinstance(epoch, (int, float)) and not isinstance(epoch, bool) else path.stat().st_mtime
    except OSError:
        return None
    return max(0.0, (time.time() - epoch) / 3600)


def ledger_path():
    """The budget ledger of the main checkout (tools/loop/shared_paths.py); LEDGER when set (fixtures)."""
    if LEDGER is not None:
        return Path(LEDGER)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('shared_paths_for_prior', Path(__file__).resolve().parent / 'shared_paths.py')
        shared = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shared)
        return Path(shared.ledger(start=Path(__file__).resolve().parent))
    except Exception:     # noqa: BLE001 - no main checkout named: no ledger reading
        return None


def ledger_terminated(purpose):
    """True when the ledger's last launch or termination line for `purpose` is a termination."""
    path = ledger_path() if purpose else None
    if path is None or not path.is_file():
        return False
    last = None
    try:
        with open(path, encoding='utf-8') as f:
            for raw in f:
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get('purpose') == purpose and row.get('event') in ('launch', 'termination'):
                    last = row['event']
    except OSError:
        return False
    return last == 'termination'


def ended(run, purpose=None):
    """(ended, how): TERMINATION_VERIFIED.json, CURRENT_PHASE terminated_and_cleaned, a ledger termination for the
    part's purpose, or a CURRENT_PHASE.json older than STALE_PHASE_HOURS (a controller killed with no record)."""
    if (run / 'TERMINATION_VERIFIED.json').is_file():
        return True, 'termination verified'
    current = _json(run / 'CURRENT_PHASE.json')
    if isinstance(current, dict) and current.get('phase') == ENDED_PHASE:
        return True, ENDED_PHASE
    if ledger_terminated(purpose):
        return True, 'ledger termination'
    age = phase_age_hours(run)
    if age is not None and age > STALE_PHASE_HOURS:
        return True, 'no phase written for %.1f hours' % age
    return False, ''


def tables(folder, run):
    """[(table, exit code or None, entry_failure, evidence)]: one per batch/NN_* folder, else the top one when it
    wrote workload_return.json. exit code is False for a table with no workload_return.json."""
    batch = run / 'batch'
    out = []
    if batch.is_dir() and not _through_links(folder, batch):
        for entry in sorted(p for p in batch.iterdir() if p.is_dir() and re.match(r'^\d\d_', p.name)):
            if _through_links(folder, entry):
                continue
            ret = entry / 'workload_return.json'
            value = _json(ret) if ret.is_file() else False
            code = value.get('exit_code') if isinstance(value, dict) else (False if value is False else None)
            out.append((entry.name, code, (entry / 'entry_failure.json').is_file(), (entry / EVIDENCE).is_file()))
        return out
    if (run / 'workload_return.json').is_file():
        value = _json(run / 'workload_return.json')
        out.append((run.name, value.get('exit_code') if isinstance(value, dict) else None, False, True))
    return out


def _named(rows):
    return ', '.join(rows[:SHOWN]) + (', ...' if len(rows) > SHOWN else '')


def part_problem(folder, part, bundles, purpose=None):
    """One line for an earlier part that failed, else None (not launched or running is no problem)."""
    where = '%s %s' % (Path(folder).name, part)
    run = run_folder(folder, bundles)
    if run is None:
        return None
    if (run / 'controller_failure.json').is_file():
        failure = _json(run / 'controller_failure.json') or {}
        return '%s: controller_failure %s' % (where, failure.get('error_type') if isinstance(failure, dict) else '?')
    rows = tables(folder, run)
    failed = [t for t, _c, f, _e in rows if f]
    if failed:
        return '%s: %d of %d tables with entry_failure.json (%s)' % (where, len(failed), len(rows), _named(failed))
    returned = [(t, c) for t, c, _f, _e in rows if c is not False]
    bad = [(t, c) for t, c in returned if not (isinstance(c, int) and not isinstance(c, bool) and c == 0)]
    if bad:
        return '%s: %d of %d tables with a non-zero exit code (%s)' % (
            where, len(bad), len(returned), _named(['%s exit %s' % x for x in bad]))
    over, how = ended(run, purpose)
    if not over:
        return None
    if len(returned) < len(bundles):
        return '%s: ended (%s) with %d of %d tables returned' % (where, how, len(returned), len(bundles))
    no_evidence = [t for t, c, _f, e in rows if c is not False and not e]
    if no_evidence:
        return '%s: ended with %d tables without %s (%s)' % (where, len(no_evidence), EVIDENCE, _named(no_evidence))
    return None


def arms_of(folder, plan):
    """Sibling launch folders of the same measurement: plan.json prior_arms, and same bench and set with an arm."""
    folder = Path(folder)
    out = []
    for name in plan.get('prior_arms') or []:
        if isinstance(name, str) and name and '/' not in name and '\\' not in name:
            other = folder.parent / name
            if other.is_dir() and not _is_link(other) and other.resolve() != folder.resolve():
                out.append(other)
    bench, set_name = plan.get('bench'), plan.get('set')
    if bench and set_name and 'arm' in plan:
        try:
            siblings = sorted(p for p in folder.parent.iterdir() if p.is_dir())
        except OSError:
            siblings = []
        for other in siblings:
            if other.resolve() == folder.resolve() or other in out or _is_link(other):
                continue
            theirs = plan_of(other)
            if theirs.get('bench') == bench and theirs.get('set') == set_name and 'arm' in theirs \
                    and theirs.get('arm') != plan.get('arm'):
                out.append(other)
    return out


def problems(folder, step):
    """Every earlier part's problem line, this folder first, then each other arm."""
    folder = Path(folder)
    plan = plan_of(folder)
    order = parts_of(plan)
    names = [p for p, _b in order]
    if step not in names:
        return []
    place = names.index(step)
    purposes = plan.get('purposes') or {}
    out = [x for x in (part_problem(folder, p, b, purposes.get(p)) for p, b in order[:place]) if x]
    for other in arms_of(folder, plan):
        theirs = plan_of(other)
        out += [x for x in (part_problem(other, p, b, (theirs.get('purposes') or {}).get(p))
                            for p, b in parts_of(theirs)[:place]) if x]
    return out


def refusal(folder, step, decision=None):
    """None when the part may launch; else one line naming each earlier part's problem. A valid decision id lets
    the launch go on (None) after printing the refusal it overrides; a malformed one is itself a refusal."""
    found = problems(folder, step)
    if not found:
        return None
    line = 'an earlier part failed, %s is not launched without a decision id (launch.py %s --decision D-NNN): %s' % (
        step, step, ' | '.join(found))
    if decision is None:
        return line
    if not DECISION.match(str(decision)):
        return 'the decision id %r is not of the form D-NNN; %s' % (decision, line)
    print('prior parts: launched under %s although %s' % (decision, ' | '.join(found)), flush=True)
    return None


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    decision = None
    if '--decision' in args:
        i = args.index('--decision')
        decision = args[i + 1] if i + 1 < len(args) else ''
        del args[i:i + 2]
    if len(args) != 2:
        print(__doc__)
        return 2
    line = refusal(args[0], args[1], decision)
    print('prior parts %s %s: %s' % (Path(args[0]).name, args[1], line or 'no earlier part failed'))
    return 1 if line else 0


if __name__ == '__main__':
    raise SystemExit(main())
