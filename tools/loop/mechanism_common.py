"""Shared pieces of the loop's standing mechanisms (supervisor batch 2026-11-18 12:30, items D, E and G).

Every standing mechanism started by Windows Task Scheduler leaves one JSON line per run in
docs/loop/private/mechanism_trace.jsonl:

    {"time": "<ISO, local +03:00>", "mechanism": "<name>", "result": "<ok|alert|...>", ...details}

and writes a dated line at the top of docs/loop/private/ALERT.md when something needs the operator. An
alert of the same key is written at most once per hour (state in mechanism_alert_state.json beside the
trace). Nothing here deletes or overwrites anything except its own state file; ALERT.md only gains a line.
"""
from __future__ import annotations

import ctypes
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import shared_paths
    MAIN = shared_paths.main_checkout(start=HERE, fallback=HERE.parents[1])
except Exception:  # noqa: BLE001 - an unreadable SHIMMER_MAIN_CHECKOUT falls back to this file's own tree
    MAIN = HERE.parents[1]
PRIVATE = MAIN / 'docs' / 'loop' / 'private'
TRACE = PRIVATE / 'mechanism_trace.jsonl'
ALERT = PRIVATE / 'ALERT.md'
ALERT_STATE = PRIVATE / 'mechanism_alert_state.json'
GIB = 2 ** 30
RAM_FLOOR_GIB = 2.0          # the operator's floor
RAM_START_GIB = 2.1          # a heavy Python job waits below this
# The laptop disk rule (Seckin 19 Nov 2026 12:03: a job's own footprint plus a 12 GiB margin) is read from
# config/laptop_disk_floor.json at each call by launch_floors.py (disk_problem, margin_gib); no figure is kept here.
ALERT_EVERY_S = 3600


def no_window():
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0


def now():
    return dt.datetime.now().astimezone()


def iso(t=None):
    return (t or now()).isoformat(timespec='seconds')


def trace(mechanism, result, **details):
    line = {'time': iso(), 'mechanism': mechanism, 'result': result}
    line.update(details)
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACE, 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(line, default=str) + '\n')
    return line


def read_trace():
    out = []
    try:
        with open(TRACE, encoding='utf-8') as f:
            for raw in f:
                raw = raw.strip()
                if raw:
                    try:
                        out.append(json.loads(raw))
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def _load_state():
    try:
        return json.loads(ALERT_STATE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def alert(key, text, every=ALERT_EVERY_S):
    """Put one dated line at the top of ALERT.md, at most once per `every` seconds for `key`.
    Returns True when a line was written."""
    state = _load_state()
    last = state.get(key)
    t = now()
    if last:
        try:
            if (t - dt.datetime.fromisoformat(last)).total_seconds() < every:
                return False
        except ValueError:
            pass
    line = '%s: %s' % (t.strftime('%Y-%m-%d %H:%M %z'), text)
    try:
        old = ALERT.read_text(encoding='utf-8')
    except OSError:
        old = '# ALERT\n'
    head, sep, rest = old.partition('\n')
    if head.startswith('# '):
        new = head + '\n\n' + line + '\n' + (('\n' + rest.lstrip('\n')) if rest.strip() else '')
    else:
        new = '# ALERT\n\n' + line + '\n\n' + old
    tmp = ALERT.with_name(ALERT.name + '.writing')
    tmp.write_text(new, encoding='utf-8', newline='\n')
    os.replace(tmp, ALERT)
    state[key] = iso(t)
    ALERT_STATE.write_text(json.dumps(state, indent=1, sort_keys=True), encoding='utf-8', newline='\n')
    return True


class _MemStatus(ctypes.Structure):
    _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]


def memory():
    """{'ram_free_gib', 'ram_total_gib', 'commit_used_gib', 'commit_limit_gib'} from GlobalMemoryStatusEx."""
    m = _MemStatus()
    m.dwLength = ctypes.sizeof(_MemStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise OSError('GlobalMemoryStatusEx failed')
    return {'ram_free_gib': round(m.ullAvailPhys / GIB, 2), 'ram_total_gib': round(m.ullTotalPhys / GIB, 2),
            'commit_used_gib': round((m.ullTotalPageFile - m.ullAvailPageFile) / GIB, 2),
            'commit_limit_gib': round(m.ullTotalPageFile / GIB, 2)}


def free_ram_gib():
    return memory()['ram_free_gib']


def wait_for_ram(mechanism, floor=RAM_START_GIB, tries=10, pause=60):
    """Wait 60 s at a time while free RAM is under `floor`; True when it rose above, False after `tries`."""
    for _ in range(tries):
        if free_ram_gib() >= floor:
            return True
        time.sleep(pause)
    return free_ram_gib() >= floor


def python_cmd():
    """The interpreter for a child tool: this one (pythonw under a task, so no window)."""
    return [sys.executable, '-X', 'utf8']
