"""Paced Google Drive backup, run daily by Windows (standing orders 98 and 101; supervisor batch 2026-11-18
12:30 item D.2). The committed form of the 16 November scratchpad uploader, built on tools/loop/drive_archive.py.

    py -3.12 -X utf8 tools/loop/drive_paced.py                       # archive every part Drive does not cover, paced
    py -3.12 -X utf8 tools/loop/drive_paced.py --confirm-only        # only check earlier archives against Drive
    py -3.12 -X utf8 tools/loop/drive_paced.py --max-wait-min 0      # one pacing check, then stop if short of disk

Task ShimmerDriveBackup runs it once a day (pyw.exe, no window).

Pacing (Seckin, 16 November 19:56 and the lead's 21:05 note): one part at a time; before each part wait until
free disk on C: is at least 12 GiB (D-729; 33 before) plus the part's size, irreplaceable parts first and
smallest first, and the Drive app's local folder has drained (under
3 GiB, or flat within 0.2 GiB for 20 minutes and under 20 GiB). It pauses while short, checking every 2
minutes and writing a "waiting" trace line every 30 minutes, for at most --max-wait-min (default 240); then
it stops with a "held" trace line and an ALERT.md line, and the next daily run starts again. A part too big
for the disk right now goes after the parts that fit.

Each part is written by drive_archive.archive_part (its rules hold: links never followed, credential names
and key bodies left out, .partial then rename, sha256 while writing and again from the file, a manifest, one
backup_log.jsonl line). A part larger than the Google Drive account's free space (keeping drive_archive's
4 GiB) is skipped with a "skipped_too_big_for_drive" line and one ALERT.md line a day, and the smaller parts
go on (the 13:07 run of 18 November ended at the first such part). Drive-only parts (roles/...) are left out unless --include-drive-only is given.

What "verified" means here: drive_archive's check reads the file back from G:\\My Drive, which is the Drive
app's LOCAL copy and proves nothing about the cloud. This tool then looks the archive up in the Drive app's
own metadata database (read-only): an item with a Google cloud id, the same size, and the MD5 checksum that
Google's servers computed from the uploaded bytes equal to the MD5 of the local archive is traced as
"cloud_confirmed". That checksum comes from the server, but it is read from the app's synced metadata, not
by a live call to the Google Drive API (that needs an OAuth login this machine does not have); the trace
line says so in its "how" field. An archive with no matching cloud checksum yet is traced
"not_yet_on_drive" and checked again on the next run. Nothing is ever deleted by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import msvcrt
import os
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mechanism_common as mc  # noqa: E402
import backup_coverage as cov  # noqa: E402
import drive_archive as da  # noqa: E402

NAME = 'drive_paced'
GIB = mc.GIB
DISK_FLOOR = 12 * GIB  # D-729 (supervisor for Seckin, 18 Nov 13:08): never waits on the laptop's general floor (was 33)
CACHE_LOW = 3 * GIB
CACHE_FLAT_MAX = 20 * GIB
FLAT_WINDOW_S = 20 * 60
FLAT_BAND = int(0.2 * GIB)
POLL_S = 120
WAIT_TRACE_S = 30 * 60
LEGACY_MD5_MAX = 100 * 1024 * 1024    # an older archive is hashed for MD5 only when this small
HOW = ('server MD5 and cloud id read from the Drive app metadata database (read-only); '
       'not a live Google Drive API read, which needs a login')
DRIVEFS = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'Google' / 'DriveFS'
HEX32 = re.compile(rb'(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])')


def account_dirs():
    try:
        return [p for p in DRIVEFS.iterdir() if p.is_dir() and p.name.isdigit() and (p / 'metadata_sqlite_db').exists()]
    except OSError:
        return []


def cache_bytes():
    total = 0
    for acc in account_dirs():
        for p in acc.rglob('*'):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                pass
    return total


def md5_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def cloud_lookup(path):
    """[(cloud id, size, [32-hex tokens in the item record], parent title)] for items titled path.name."""
    found = []
    for acc in account_dirs():
        try:
            con = sqlite3.connect('file:%s?mode=ro' % (acc / 'metadata_sqlite_db').as_posix(), uri=True, timeout=5)
        except sqlite3.Error:
            continue
        try:
            con.text_factory = bytes
            rows = con.execute('select stable_id, id, file_size, proto from items where local_title = ? and '
                               'is_folder = 0 and trashed = 0 and is_tombstone = 0', (path.name,)).fetchall()
            for sid, cid, size, proto in rows:
                parent = con.execute('select i.local_title from stable_parents p join items i on '
                                     'i.stable_id = p.parent_stable_id where p.item_stable_id = ?', (sid,)).fetchone()
                found.append((cid.decode('ascii', 'replace') if isinstance(cid, bytes) else str(cid), size,
                              [m.decode() for m in HEX32.findall(proto or b'')],
                              parent[0].decode('utf-8', 'replace') if parent else None))
        except sqlite3.Error:
            pass
        finally:
            con.close()
    return found


def confirm(path, md5=None):
    """('cloud_confirmed' | 'cloud_present' | 'not_yet_on_drive' | 'missing', details)."""
    path = Path(path)
    if not path.is_file():
        return 'missing', {}
    size = path.stat().st_size
    items = [i for i in cloud_lookup(path) if i[3] in (None, path.parent.name)]
    cloud = [i for i in items if i[0] and not i[0].startswith('local') and i[1] == size]
    if not cloud:
        return 'not_yet_on_drive', {'items_found': len(items)}
    if md5 is None and size <= LEGACY_MD5_MAX:
        md5 = md5_file(path)
    if md5 and any(md5 in i[2] for i in cloud):
        return 'cloud_confirmed', {'cloud_id': cloud[0][0], 'md5': md5}
    if md5:
        return 'not_yet_on_drive', {'items_found': len(items), 'note': 'cloud item has no matching server MD5 yet'}
    return 'cloud_present', {'cloud_id': cloud[0][0], 'note': 'size and cloud id match; MD5 not compared (large)'}


def confirm_pass(paths):
    """Check every verified Drive archive in backup_log.jsonl not yet traced as cloud_confirmed."""
    done = {x.get('file') for x in mc.read_trace() if x.get('mechanism') == NAME and x.get('result') == 'cloud_confirmed'}
    known_md5 = {x.get('file'): x.get('md5') for x in mc.read_trace() if x.get('mechanism') == NAME and x.get('md5')}
    counts = {}
    for line in cov.read_log(paths['log']):
        if line.get('tool') not in cov.DRIVE_TOOLS or not line.get('file') or line.get('verified') is not True:
            continue
        f = line['file'] if Path(line['file']).is_absolute() else str(Path(paths['drive']) / line['file'])
        if f in done:
            counts['cloud_confirmed_before'] = counts.get('cloud_confirmed_before', 0) + 1
            continue
        state, det = confirm(f, known_md5.get(f))
        counts[state] = counts.get(state, 0) + 1
        if state == 'cloud_confirmed':
            mc.trace(NAME, 'cloud_confirmed', file=f, archive_time=line.get('time'), bytes=line.get('bytes'),
                     how=HOW, **det)
            done.add(f)
    return counts


def drive_free_bytes(paths):
    """Free space the Drive folder reports (the Google account's free quota under Drive for desktop)."""
    drive = Path(paths['drive'])
    try:
        return shutil.disk_usage(drive if drive.exists() else drive.anchor).free
    except OSError:
        return None


def free_disk():
    return shutil.disk_usage('C:/').free


def wait_for_room(part, need, max_wait_s):
    """True when the part may start; False when the wait ran out (a 'held' line is then written)."""
    start, seen, last_trace = time.time(), [], 0.0
    while True:
        free, cache, t = free_disk(), cache_bytes(), time.time()
        seen = [(s, c) for s, c in seen if t - s <= FLAT_WINDOW_S + 300] + [(t, cache)]
        flat = (t - seen[0][0] >= FLAT_WINDOW_S and max(c for _, c in seen) - min(c for _, c in seen) <= FLAT_BAND
                and cache < CACHE_FLAT_MAX)
        if free >= DISK_FLOOR + need and (cache < CACHE_LOW or flat):
            return True
        state = {'part': part, 'free_gib': round(free / GIB, 2), 'cache_gib': round(cache / GIB, 2),
                 'need_gib': round((DISK_FLOOR + need) / GIB, 2)}
        if t - start >= max_wait_s:
            mc.trace(NAME, 'held', waited_min=round((t - start) / 60, 1), **state)
            mc.alert('drive_paced:held', 'Drive backup held (task ShimmerDriveBackup): part %s needs %.1f GiB free '
                     'on C: and a drained Drive cache; free %.1f GiB, cache %.1f GiB. Nothing was written; the next '
                     'daily run tries again.' % (part, state['need_gib'], state['free_gib'], state['cache_gib']))
            return False
        if t - last_trace >= WAIT_TRACE_S:
            mc.trace(NAME, 'waiting', **state)
            last_trace = t
        time.sleep(POLL_S)


def pending(paths, include_drive_only):
    for attempt in range(3):     # a file another process holds open (Windows) refuses a read: try again
        try:
            report = cov.coverage(paths, secret_check=lambda u: set(), list_max=0)
            break
        except OSError as exc:
            mc.trace(NAME, 'coverage_retry', attempt=attempt + 1, reason='%s: %s' % (type(exc).__name__, exc)[:200])
            if attempt == 2:
                raise
            time.sleep(30)
    out = []
    for r in report['parts']:
        if r['status'] == 'EXCLUDED' or not r['files']:
            continue
        if r.get('drive_only') and not include_drive_only:
            continue
        if r['drive_files'] + r.get('located_files', 0) + len(r['excluded']) >= r['files']:
            continue      # held by Drive, by a located copy, or left out by declaration (config read at call time)
        # what the archive will carry: the bytes not yet covered and not left out by declaration (an excluded
        # 20 GiB asset bundle must not make a 1 GiB evidence part wait for 54 GiB of free disk)
        r['need_bytes'] = r.get('gap_bytes', r['bytes'])
        out.append(r)
    out.sort(key=lambda r: (not r.get('irreplaceable'), 'vllm_test' in r['part'], r['need_bytes'], r['part']))  # D-729: smallest first
    free = free_disk()
    return ([r for r in out if free >= DISK_FLOOR + r['need_bytes']]
            + [r for r in out if free < DISK_FLOOR + r['need_bytes']])


def lock():
    f = open(mc.PRIVATE / 'drive_paced.lock', 'a+')
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        return None
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--confirm-only', action='store_true')
    ap.add_argument('--include-drive-only', action='store_true', help='also archive roles/... parts')
    ap.add_argument('--max-wait-min', type=float, default=240)
    ap.add_argument('--confirm-wait-min', type=float, default=60, help='how long to wait for a new archive to reach Drive')
    ap.add_argument('--limit', type=int, default=0, help='archive at most this many parts (0: all)')
    ap.add_argument('--parts', nargs='+', help='these parts first (for example today\'s evidence)')
    ap.add_argument('--only', action='store_true', help='with --parts: only those parts')
    args = ap.parse_args(argv)
    held = lock()
    if held is None:
        mc.trace(NAME, 'skipped', reason='another drive_paced run holds the lock')
        return 0
    if not mc.wait_for_ram(NAME):
        mc.trace(NAME, 'deferred_ram', ram_free_gib=mc.free_ram_gib())
        mc.alert('drive_paced:ram', 'Drive backup did not start: free RAM stayed under 2.1 GiB for 10 minutes.')
        return 3
    paths = cov.default_paths()
    if not Path(paths['drive']).exists():
        mc.trace(NAME, 'error', reason='the Drive folder is not there', drive=str(paths['drive']))
        mc.alert('drive_paced:nodrive', 'Drive backup failed: %s is not there (Drive app not running?).' % paths['drive'])
        return 1
    counts = confirm_pass(paths)
    mc.trace(NAME, 'confirm_pass', counts=counts, how=HOW)
    if args.confirm_only:
        return 0
    todo = pending(paths, args.include_drive_only)
    if args.parts:      # the named parts first, in the order given; the rest after them unless --only
        named = {r['part']: r for r in todo}
        missing = [p for p in args.parts if p not in named]
        if missing:
            mc.trace(NAME, 'named_not_pending', parts=missing)
        todo = [named[p] for p in args.parts if p in named] + ([] if args.only else
                                                                [r for r in todo if r['part'] not in args.parts])
    if args.limit:
        todo = todo[:args.limit]
    mc.trace(NAME, 'plan', parts=len(todo), bytes=sum(r['need_bytes'] for r in todo),
             free_gib=round(free_disk() / GIB, 2), drive_only_included=args.include_drive_only)
    status = 0
    too_big = []
    for r in todo:
        part = r['part']
        drive_free = drive_free_bytes(paths)
        if drive_free is not None and drive_free - r['need_bytes'] < da.FLOOR:
            # The 13:07 run ended with exit 1 here: drive_archive refuses a part that would leave under 4 GiB
            # free on Drive (DEV_contradoc15, far larger than the account's free space), and the loop then
            # stopped every later part too. A part too big for Drive is now skipped, named once, and the
            # smaller parts go on.
            too_big.append(part)
            mc.trace(NAME, 'skipped_too_big_for_drive', part=part, part_gib=round(r['need_bytes'] / GIB, 2),
                     drive_free_gib=round(drive_free / GIB, 2))
            continue
        if not wait_for_room(part, r['need_bytes'], args.max_wait_min * 60):
            return 4
        try:
            line = da.archive_part(paths, part)
        except da.Refused as exc:
            mc.trace(NAME, 'refused', part=part, reason=str(exc)[:200])
            status = 1
            continue
        except Exception as exc:  # noqa: BLE001 - one part's failure is written down; the next part goes on
            mc.trace(NAME, 'error', part=part, reason='%s: %s' % (type(exc).__name__, str(exc)[:200]))
            mc.alert('drive_paced:error', 'Drive backup error on part %s: %s.' % (part, type(exc).__name__))
            status = 1
            continue
        if line.get('stopped') or not line.get('file'):
            mc.trace(NAME, 'skipped_too_big_for_drive' if line.get('stopped') else 'stopped', part=part,
                     reason=line.get('stopped'))
            too_big.append(part)
            continue
        md5 = md5_file(line['file'])
        mc.trace(NAME, 'written', part=part, file=line['file'], bytes=line.get('bytes'), sha256=line.get('sha256'),
                 md5=md5, local_verified=line.get('verified'), archive_time=line.get('time'),
                 note='written to the Drive app folder; local read-back only until cloud_confirmed')
        deadline = time.time() + args.confirm_wait_min * 60
        while True:
            state, det = confirm(line['file'], md5)
            if state == 'cloud_confirmed' or time.time() >= deadline:
                break
            time.sleep(POLL_S)
        mc.trace(NAME, state, part=part, file=line['file'], archive_time=line.get('time'), bytes=line.get('bytes'),
                 how=HOW, **det)
        if state != 'cloud_confirmed':
            status = status or 0     # not an error yet: the next run's confirm pass checks it again
    if too_big:
        mc.alert('drive_paced:too_big:' + ','.join(sorted(too_big)), 'Drive backup (task ShimmerDriveBackup): %d '
                 'part(s) are larger than the free space on the Google Drive account (keeping 4 GiB free) and were '
                 'skipped: %s. They need more Drive space or a split; the other parts went on.' % (
                     len(too_big), ', '.join(too_big[:8])), every=24 * 3600)
        mc.trace(NAME, 'done_with_skips', skipped_too_big=too_big)
        status = status or 5
    else:
        mc.trace(NAME, 'done')
    return status


if __name__ == '__main__':
    raise SystemExit(main())
