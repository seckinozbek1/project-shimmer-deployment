#!/usr/bin/env python3
"""Which run folder a launch folder's `launch.py status` reads (check 517, the lead 18 Nov 22:2x).

tools/ordinary_final_bound_cloud.py run_folder writes a part into <output-dir>/<bundle name>, and an attempt whose
folder is already there takes the next name (<bundle name>.2, .3, ...). A status that read only <bundle name> read
the first attempt and missed the retry's workload_return.json (ROUTE_GATE_3efb3a37, ALERT 21:24: a green gate
reported failed). The rule: of the folders NAME, NAME.2, NAME.3 ..., the one whose launch record carries the
instance id of the ledger's newest launch line for the step's purpose; if that cannot be told, the highest suffix.
The chosen folder and the reason are printed. Read-only: nothing is written, created or deleted.

A launch folder's launch.py loads this file from the main checkout by path:
    folder = __import__('runpy').run_path(str(M / 'tools/loop/run_folder_pick.py'))['chosen'](folder, BUNDLE, LEDGER, PURPOSES[part], part)
"""
from __future__ import annotations

import json
from pathlib import Path

# The run folder files that name the instance the attempt launched, in the order they are written.
INSTANCE_FILES = ('launch.json', 'CURRENT_PHASE.json', 'TERMINATION_VERIFIED.json', 'termination_requested.json')


def candidates(base, name):
    """[(suffix, folder)] for base/name (suffix 1) and base/name.N (N >= 2), lowest suffix first."""
    base, out = Path(base), []
    if (base / name).is_dir():
        out.append((1, base / name))
    try:
        entries = list(base.iterdir())
    except OSError:
        entries = []
    for item in entries:
        head, dot, tail = item.name.rpartition('.')
        if dot and head == name and tail.isdigit() and int(tail) >= 2 and item.is_dir():
            out.append((int(tail), item))
    return sorted(out, key=lambda x: x[0])


def folder_instance(folder):
    for file in INSTANCE_FILES:
        try:
            value = json.loads((Path(folder) / file).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict) and value.get('instance_id'):
            return value['instance_id']
    return None


def ledger_rows(ledger):
    rows = []
    try:
        with open(ledger, encoding='utf-8') as f:
            for raw in f:
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except (OSError, TypeError):
        pass
    return rows


def pick(base, name, rows, purpose):
    """(folder or None, reason): the folder of the ledger's newest launch for `purpose`, else the highest suffix."""
    found = candidates(base, name)
    if not found:
        return None, 'no run folder %s yet' % name
    launches = [r for r in rows if r.get('purpose') == purpose and r.get('event') == 'launch' and r.get('instance_id')]
    if launches:
        wanted = launches[-1]['instance_id']
        own = [folder for _, folder in found if folder_instance(folder) == wanted]
        if len(own) == 1:
            return own[0], "the ledger's newest launch for %s" % purpose
    return found[-1][1], 'the highest suffix (the ledger names no single folder)'


def chosen(base, name, ledger, purpose, label):
    """The folder `launch.py status` reads for step `label`, printed with its reason; `base` when none exists yet."""
    folder, why = pick(base, name, ledger_rows(ledger), purpose)
    if folder is None:
        print('%s reads %s (%s)' % (label, Path(base).name, why), flush=True)
        return Path(base)
    print('%s reads %s/%s (%s)' % (label, Path(base).name, folder.name, why), flush=True)
    return folder
