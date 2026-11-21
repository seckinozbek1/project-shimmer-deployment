"""30-minute resource reading of the laptop (D-659 item 3; supervisor batch 2026-11-18 12:30 item E).

    py -3.12 -X utf8 tools/loop/resource_reading.py        # one reading, one trace line

Run by the Windows task ShimmerResourceReading every 30 minutes (pyw.exe, no window), so it does not die
with a Claude session. Each run reads free RAM, free disk on C:, the commit charge (RAM plus page file),
the page file size, how many python and claude processes are open with their memory, the five largest
processes by memory (names only), and the graphics card's memory, load and temperature, then appends one
line to docs/loop/private/mechanism_trace.jsonl (mechanism resource_reading). Below a floor (RAM 2 GiB;
disk: the 12 GiB margin of config/laptop_disk_floor.json, read at each run, since any heavy laptop job needs its
own footprint plus that margin, Seckin 19 Nov 2026 12:03) it writes a dated line at the top of
docs/loop/private/ALERT.md, at most once per hour per floor. It also checks that the 15-minute watchdog has left a trace line in the last 45 minutes (the watchdog
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
import launch_floors  # noqa: E402

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


def gpu():
    """The graphics card's memory in use, its total, load and temperature from nvidia-smi (G-20261121-1030:
    after the 10:14 graphics driver crash of 21 Nov no record held the card's memory); None when absent."""
    exe = shutil.which('nvidia-smi')
    if not exe:
        return None
    done = subprocess.run([exe, '--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu',
                           '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=30,
                          stdin=subprocess.DEVNULL, creationflags=mc.no_window())
    first = (done.stdout.strip().splitlines() or [''])[0]
    parts = [p.strip() for p in first.split(',')]
    if done.returncode != 0 or len(parts) != 4:
        return {'error': 'nvidia-smi exit %d' % done.returncode}
    keys = ('mem_used_mib', 'mem_total_mib', 'util_percent', 'temp_c')
    return {k: (int(v) if v.isdigit() else None) for k, v in zip(keys, parts)}


def top_memory(n=5):
    """The n largest processes by working set, names and GiB only (no command lines)."""
    done = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True, timeout=60,
                          stdin=subprocess.DEVNULL, creationflags=mc.no_window())
    rows = []
    for row in csv.reader(io.StringIO(done.stdout)):
        if len(row) >= 5:
            rows.append((int(''.join(ch for ch in row[4] if ch.isdigit()) or 0), row[0]))
    rows.sort(reverse=True)
    return [[name, round(kb / 1024 / 1024, 2)] for kb, name in rows[:n]]


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
    try:
        reading['gpu'] = gpu()
        reading['top_memory'] = top_memory()
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        reading['gpu_error'] = type(exc).__name__
    ram = reading.get('ram_free_gib')
    if ram is not None and ram < mc.RAM_FLOOR_GIB:
        alerts.append('ram')
        mc.alert('resource_ram', 'RAM below the 2 GiB floor: %.2f GiB free (resource reading, task '
                 'ShimmerResourceReading). Python processes %s, claude processes %s. Nothing was stopped.' % (
                     ram, reading.get('processes', {}).get('python', {}).get('count', '?'),
                     reading.get('processes', {}).get('claude', {}).get('count', '?')))
    margin, source = launch_floors.margin_gib()
    reading['disk_margin_gib'] = margin
    if reading['disk_free_gib'] < margin:
        alerts.append('disk')
        mc.alert('resource_disk', 'Disk below the %.0f GiB margin (%s rule: heavy laptop work needs its own footprint '
                 'plus this): %.2f GiB free on C: (resource reading, task ShimmerResourceReading). No heavy laptop '
                 'job can start. Nothing was deleted.' % (margin, source, reading['disk_free_gib']))
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
