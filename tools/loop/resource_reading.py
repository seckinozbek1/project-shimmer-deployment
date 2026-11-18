"""30-minute resource reading of the laptop (D-659 item 3; supervisor batch 2026-11-18 12:30 item E).

    py -3.12 -X utf8 tools/loop/resource_reading.py        # one reading, one trace line

Run by the Windows task ShimmerResourceReading every 30 minutes (pyw.exe, no window), so it does not die
with a Claude session. Each run reads free RAM, free disk on C:, the commit charge (RAM plus page file),
the page file size, and how many python and claude processes are open with their memory, then appends one
line to docs/loop/private/mechanism_trace.jsonl (mechanism resource_reading). Below a floor (RAM 2 GiB,
disk 30 GiB) it writes a dated line at the top of docs/loop/private/ALERT.md, at most once per hour per
floor. It also checks that the 15-minute watchdog has left a trace line in the last 45 minutes (the watchdog
of the watchdog). It reads only; it deletes and stops nothing.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mechanism_common as mc  # noqa: E402

NAME = 'resource_reading'
GROUPS = {'python': ('python.exe', 'pythonw.exe', 'py.exe', 'pyw.exe'), 'claude': ('claude.exe',)}
WATCHDOG_STALE_S = 45 * 60


def processes():
    """{group: {'count': n, 'mem_gib': x}} from tasklist (names only, no command lines)."""
    out = {g: {'count': 0, 'mem_gib': 0.0} for g in GROUPS}
    done = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True, timeout=60,
                          stdin=subprocess.DEVNULL, creationflags=mc.no_window())
    for row in csv.reader(io.StringIO(done.stdout)):
        if len(row) < 5:
            continue
        name = row[0].lower()
        kb = int(''.join(ch for ch in row[4] if ch.isdigit()) or 0)
        for g, names in GROUPS.items():
            if name in names:
                out[g]['count'] += 1
                out[g]['mem_gib'] += kb / 1024 / 1024
    for g in out:
        out[g]['mem_gib'] = round(out[g]['mem_gib'], 2)
    return out


def pagefile_gib():
    try:
        return round(os.stat('C:/pagefile.sys').st_size / mc.GIB, 2)
    except OSError:
        return None


def watchdog_age_s(lines, t):
    last = None
    for line in lines:
        if line.get('mechanism') == 'mechanism_watchdog':
            last = line.get('time')
    if not last:
        return None
    try:
        return (t - dt.datetime.fromisoformat(last)).total_seconds()
    except ValueError:
        return None


def main():
    reading = {}
    alerts = []
    try:
        reading.update(mc.memory())
    except OSError as exc:
        reading['memory_error'] = str(exc)
    reading['disk_free_gib'] = round(shutil.disk_usage('C:/').free / mc.GIB, 2)
    reading['pagefile_gib'] = pagefile_gib()
    try:
        reading['processes'] = processes()
    except (OSError, subprocess.SubprocessError) as exc:
        reading['processes_error'] = type(exc).__name__
    ram = reading.get('ram_free_gib')
    if ram is not None and ram < mc.RAM_FLOOR_GIB:
        alerts.append('ram')
        mc.alert('resource_ram', 'RAM below the 2 GiB floor: %.2f GiB free (resource reading, task '
                 'ShimmerResourceReading). Python processes %s, claude processes %s. Nothing was stopped.' % (
                     ram, reading.get('processes', {}).get('python', {}).get('count', '?'),
                     reading.get('processes', {}).get('claude', {}).get('count', '?')))
    if reading['disk_free_gib'] < mc.DISK_FLOOR_GIB:
        alerts.append('disk')
        mc.alert('resource_disk', 'Disk below the 30 GiB floor: %.2f GiB free on C: (resource reading, task '
                 'ShimmerResourceReading). Nothing was deleted.' % reading['disk_free_gib'])
    age = watchdog_age_s(mc.read_trace(), mc.now())
    reading['watchdog_age_min'] = None if age is None else round(age / 60, 1)
    if age is not None and age > WATCHDOG_STALE_S:
        alerts.append('watchdog')
        mc.alert('watchdog_stale', 'The mechanism watchdog (task ShimmerMechanismWatchdog, every 15 minutes) '
                 'left no trace line for %.0f minutes.' % (age / 60))
    mc.trace(NAME, 'alert' if alerts else 'ok', below_floor=alerts, **reading)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
