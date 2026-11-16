"""Restore drill for the two backups (D-702 item 4: now and weekly).

    py -3.12 -X utf8 tools/loop/restore_drill.py                    # one small covered part from each backup
    py -3.12 -X utf8 tools/loop/restore_drill.py --part private/hooks --kinds git

For each backup kind (git: the records/private snapshot of the private git backup; drive: a verified Drive
archive with a content list) it picks the smallest part that backup_coverage finds fully held by that kind
and unchanged for at least --settle minutes (or the named --part), restores it into a NEW folder
<scratch root>/restore_drill_<YYYYMMDD-HHMMSS>/<kind>/ (default scratch root: the main checkout's sibling
shimmer-scratch; a folder inside the main checkout, a link, or an existing drill folder is refused), and
compares the SHA-256 of every restored file with the live copy. The drill reads the backups and the live
files only, writes only inside its own new folder (and drill_result.json there), deletes nothing, and says
the folder's path. PASS when every kind found a part and every file matched; exit 0 on PASS, 1 on FAIL, 2
when refused.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import backup_coverage as cov  # noqa: E402

KINDS = ('git', 'drive')
SMALL = 20 * 1024 * 1024        # a drilled part is at most this many bytes
ARCHIVE_MAX = cov.LIST_MAX      # a drive drill reads an archive at most this large


class DrillRefused(Exception):
    pass


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def drill_folder(scratch_root, main, now):
    scratch_root = Path(scratch_root)
    if inside(scratch_root, main):
        raise DrillRefused('the scratch root %s is inside the main checkout' % scratch_root)
    probe = scratch_root
    while True:
        if probe.exists() and cov.is_link(probe):
            raise DrillRefused('the scratch root %s is or lies under a link' % scratch_root)
        if probe.parent == probe:
            break
        probe = probe.parent
    folder = scratch_root / ('restore_drill_' + now.strftime('%Y%m%d-%H%M%S'))
    if folder.exists():
        raise DrillRefused('%s exists already' % folder)
    folder.mkdir(parents=True)
    return folder


def live_files(main, part):
    files, _, _ = cov.walk(main, within=part)
    return {lg: info for lg, info in files.items() if cov.part_of(lg) == part}


def candidates(report, kind, settle, now_ts):
    rows = []
    for r in report['parts']:
        if r['status'] != 'COVERED' or not r['files'] or r['excluded'] or r['bytes'] > SMALL:
            continue
        if r.get('drive_only'):      # a drive-only root (roles/...) is not drilled: its mismatch lines name files
            continue
        if kind == 'git' and r['git_files'] != r['files']:
            continue
        if kind == 'drive' and r['drive_files'] != r['files']:
            continue
        rows.append(r)
    return sorted(rows, key=lambda r: (r['bytes'], r['part']))


def settled(main, part, settle, now_ts):
    return all(now_ts - max(i[2], i[3]) >= settle * 60 for i in live_files(main, part).values())


def safe_rel(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or ':' in name:
        raise DrillRefused('an unsafe member name in a backup: %s' % name)
    return p


def restore_git(paths, part, dest):
    tree, commit, _ = cov.git_snapshot(paths['repo'])
    wanted = {p: s for p, s in tree.items() if cov.part_of(p) == part}
    for logical, blob in wanted.items():
        out = dest.joinpath(*safe_rel(logical).parts)
        out.parent.mkdir(parents=True, exist_ok=True)
        done = subprocess.run(['git', '--git-dir', str(paths['repo']), 'cat-file', 'blob', blob],
                              capture_output=True, timeout=600, stdin=subprocess.DEVNULL,
                              creationflags=cov.no_window())
        if done.returncode != 0:
            raise cov.CoverageError('git cat-file failed for %s' % logical)
        out.write_bytes(done.stdout)
    return set(wanted), 'git %s' % (commit or '')[:12]


def pick_archive(paths, part, live):
    """The newest verified archive with a content list that holds every live file of the part."""
    lines = cov.read_log(paths['log'])
    best = None
    for a in cov.drive_archives(lines, paths['drive'], paths['main']):
        if a.members is None or a.path.stat().st_size > ARCHIVE_MAX:
            continue
        if all(cov.drive_holds(a, lg, i[1], i[2], i[3]) for lg, i in live.items()):
            if best is None or a.when > best.when:
                best = a
    return best


def restore_drive(paths, part, dest, live):
    a = pick_archive(paths, part, live)
    if a is None:
        raise DrillRefused('no small verified archive with a content list holds %s' % part)
    prefix = a.line.get('arc_prefix', 'external/' if a.line.get('tool') == 'drive_external' else '')
    got = set()
    if a.path.suffix == '.zip':
        with zipfile.ZipFile(a.path) as z:
            for i in z.infolist():
                logical = prefix + i.filename
                if i.is_dir() or cov.part_of(logical) != part:
                    continue
                out = dest.joinpath(*safe_rel(logical).parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(i) as src, open(out, 'wb') as f:
                    for chunk in iter(lambda: src.read(8 << 20), b''):
                        f.write(chunk)
                got.add(logical)
    else:
        with tarfile.open(a.path, 'r:gz') as t:
            members = [m for m in t.getmembers() if (m.isfile() or m.islnk())
                       and cov.part_of(prefix + m.name) == part]
            for m in members:
                safe_rel(m.name)
            # the data filter refuses absolute names, names outside dest and device files
            t.extractall(dest.joinpath(*safe_rel(prefix).parts) if prefix else dest, members=members,
                         filter='data')
            got = {prefix + m.name for m in members}
    return got, a.name


def compare(live, restored_root, restored):
    """[(logical, reason)] for every file that differs, is missing, or is extra."""
    bad = []
    for logical, info in sorted(live.items()):
        out = restored_root.joinpath(*PurePosixPath(logical).parts)
        if logical not in restored or not out.is_file():
            bad.append((logical, 'not restored'))
        elif cov.sha256_file(out) != cov.sha256_file(info[0]):
            bad.append((logical, 'hash differs'))
    for logical in sorted(set(restored) - set(live)):
        bad.append((logical, 'in the backup, not live'))
    return bad


def drill(paths, scratch_root, kinds=KINDS, part=None, settle=10, now=None):
    now = now or dt.datetime.now().astimezone()
    folder = drill_folder(scratch_root, paths['main'], now)
    report = cov.coverage(paths, secret_check=lambda u: set())
    results = []
    for kind in kinds:
        res = {'kind': kind}
        try:
            if part:
                chosen = part
            else:
                pool = [r['part'] for r in candidates(report, kind, settle, now.timestamp())
                        if settled(paths['main'], r['part'], settle, now.timestamp())]
                if not pool:
                    raise DrillRefused('no small, settled part is fully held by the %s backup' % kind)
                chosen = pool[0]
            res['part'] = chosen
            live = live_files(paths['main'], chosen)
            dest = folder / kind
            dest.mkdir()
            if kind == 'git':
                restored, source = restore_git(paths, chosen, dest)
            else:
                restored, source = restore_drive(paths, chosen, dest, live)
            bad = compare(live, dest, restored)
            res.update(source=source, files=len(live), restored=len(restored), mismatches=bad[:50],
                       result='PASS' if not bad and live else 'FAIL')
        except (DrillRefused, cov.CoverageError, OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
            res.update(result='FAIL', reason=str(exc)[:300])
        results.append(res)
    overall = 'PASS' if results and all(r['result'] == 'PASS' for r in results) else 'FAIL'
    summary = {'time': now.isoformat(timespec='seconds'), 'folder': str(folder), 'result': overall, 'kinds': results}
    (folder / 'drill_result.json').write_text(json.dumps(summary, indent=1), encoding='utf-8', newline='\n')
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--kinds', default=','.join(KINDS))
    ap.add_argument('--part')
    ap.add_argument('--settle', type=float, default=10, help='minutes a drilled part must be unchanged')
    ap.add_argument('--scratch-root')
    ap.add_argument('--main')
    ap.add_argument('--repo')
    ap.add_argument('--drive')
    ap.add_argument('--log')
    args = ap.parse_args(argv)
    paths = cov.default_paths(args.main)
    for key in ('repo', 'drive', 'log'):
        if getattr(args, key):
            paths[key] = Path(getattr(args, key))
    scratch = Path(args.scratch_root) if args.scratch_root else Path(paths['main']).parent / 'shimmer-scratch'
    kinds = [k for k in args.kinds.split(',') if k]
    if any(k not in KINDS for k in kinds):
        print('kinds are git and drive')
        return 2
    try:
        summary = drill(paths, scratch, kinds, args.part, args.settle)
    except DrillRefused as exc:
        print('REFUSED: %s' % exc)
        return 2
    for r in summary['kinds']:
        print('%s %s: part %s, %s files, restored %s, from %s%s' % (
            r['result'], r['kind'], r.get('part', '-'), r.get('files', 0), r.get('restored', 0), r.get('source', '-'),
            ('; ' + r['reason']) if r.get('reason') else ''))
        for logical, why in r.get('mismatches', []):
            print('    %s: %s' % (logical, why))
    print('%s; drill folder left in place: %s' % (summary['result'], summary['folder']))
    return 0 if summary['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
