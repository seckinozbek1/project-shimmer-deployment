"""Compressed archives of the main checkout's data on the private Google Drive folder (standing orders 98 and 101).

The reviewed, committed form of the 16 November scratchpad archiver (drive_external.py).

    py -3.12 -X utf8 tools/loop/drive_archive.py --dry-run              # the parts, files, bytes and what is left out
    py -3.12 -X utf8 tools/loop/drive_archive.py external/s05/GATE      # archive the named parts
    py -3.12 -X utf8 tools/loop/drive_archive.py --all                  # every part not already covered on Drive
    py -3.12 -X utf8 tools/loop/drive_archive.py --keep-report --keep 3 # which older archives exceed the last 3

A part is one of backup_coverage's parts (external/s05/<run>, external/<folder>, private/<folder>, ...); a
part already COVERED by a verified Drive archive is skipped unless --force. Each part becomes one tar.gz in
<drive>/parts_<YYYYMMDD>/<part with / as __>__<YYYYMMDD-HHMMSS>.tar.gz, members named by their logical path
(external/s05/GATE/...). Rules:
- Links are never followed: a junction or symlink is stored as nothing and its path is listed in the log line.
- Credential-like names (backup_coverage.CRED) and files up to 5 MB holding a key body (backup_records.STRICT)
  are left out and listed by path only; a match is never printed.
- The archive is hashed while written and hashed again from Drive; a manifest (path, size, modification
  time, SHA-256 of every member) is written beside it and hashed too.
- A part of a declared drive-only root (roles/<folder>/..., config/backup_extra_roots.json: the role exchange
  folders and the negotiation sets outside the repository) goes to Drive only: refused when the Drive folder
  is inside the main checkout or the git backup repository; a name the declaration excludes (role folders B,
  V, R, C, _seckin; anything named answer_key) is never opened; the log and printed line carry counts, sizes
  and hashes only (left_out_counts by reason, links as a count), never a name inside the part. The archive is written as .partial and
  renamed only when complete; a part whose archive would leave under 4 GiB free on Drive is not started.
- One line per part goes to docs/loop/private/backup_log.jsonl (tool drive_archive): file, bytes, sha256,
  files, links, left_out, manifest, manifest_sha256, verified.
- The keep-last-N policy is a REPORT only: it prints the verified archives of each part older than the
  newest N. Nothing is ever deleted by this tool.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import backup_coverage as cov  # noqa: E402

FLOOR = 4 * 2 ** 30
SCAN_MAX = 5 * 1024 * 1024
TOOL = 'drive_archive'


def strict_patterns():
    try:
        import backup_records
        return [rx for _, rx in backup_records.STRICT]
    except Exception:
        return []


class HashWriter:
    """A file object that hashes and counts every byte written through it."""

    def __init__(self, f):
        self.f, self.h, self.n = f, hashlib.sha256(), 0

    def write(self, b):
        self.h.update(b)
        self.n += len(b)
        return self.f.write(b)

    def flush(self):
        self.f.flush()


class HashReader:
    def __init__(self, f):
        self.f, self.h = f, hashlib.sha256()

    def read(self, n=-1):
        b = self.f.read(n)
        self.h.update(b)
        return b


class Refused(Exception):
    """A part this tool must not archive (an undeclared drive-only root, a Drive folder inside a backup)."""


def part_root(main, part, extra=None):
    """The disk folder of a part, or for a `(files)` part the folder whose loose files it is. A drive-only
    part (roles/<folder>/...) is found under its declared root in `extra` (backup_coverage.extra_roots)."""
    bits = part.split('/')
    loose = bits[-1] == cov.LOOSE
    if cov.drive_only(part):
        roots = {r['logical']: Path(r['disk']) for r in (extra or {}).get('roots', ())}
        base = roots.get('/'.join(bits[:2]))
        if base is None or len(bits) < 3:
            raise Refused('not a part of a declared drive-only root')
        return base.joinpath(*(bits[2:-1] if loose else bits[2:])), loose
    rel = dict(cov.ROOTS)[bits[0]]
    return Path(main).joinpath(*rel, *(bits[1:-1] if loose else bits[1:])), loose


def gather(main, part, patterns, extra=None):
    """(files [(logical, disk path)], links [logical], left_out [(logical, reason)]) of one part. Under a
    drive-only root a name the declaration excludes is never opened; it is left out as 'declared out of scope'."""
    root, loose = part_root(main, part, extra)
    prefix = part.rsplit('/', 1)[0] if loose else part
    spec = (extra or {}).get('spec') or {} if cov.drive_only(part) else None
    base_depth = 1
    files, links, left = [], [], []
    if spec is not None:
        why = cov.excluded_name(root.name, 1, spec) if not loose else ''
        if why:
            return files, links, [(prefix, 'declared out of scope')]
    if cov.is_link(root):
        return files, [prefix], left
    stack = [(root, prefix)]
    while stack:
        d, logical_dir = stack.pop()
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError:
            continue
        for e in entries:
            logical = logical_dir + '/' + e.name
            if spec is not None and cov.excluded_name(e.name, logical.count('/') - base_depth, spec):
                left.append((logical, 'declared out of scope'))     # never opened
                continue
            if cov.is_link(e.path):
                links.append(logical)
            elif e.is_dir(follow_symlinks=False):
                if not loose and e.name not in cov.SKIP_DIRS and logical not in cov.REGENERABLE:
                    stack.append((Path(e.path), logical))
            elif cov.credential_name(e.name):
                left.append((logical, 'credential name'))
            elif patterns and e.stat(follow_symlinks=False).st_size <= SCAN_MAX and key_body(e.path, patterns):
                left.append((logical, 'key pattern'))
            else:
                files.append((logical, e.path))
    return files, links, left


def key_body(path, patterns):
    try:
        text = Path(path).read_bytes().decode('utf-8', errors='ignore')
    except OSError:
        return False
    return any(rx.search(text) for rx in patterns)


def write_archive(target, files):
    """Write files into target (.partial first); returns (bytes, sha256, manifest entries)."""
    tmp = target.with_name(target.name + '.partial')
    entries, by_arc = [], {}
    with open(tmp, 'wb') as raw:
        hw = HashWriter(raw)
        with tarfile.open(fileobj=hw, mode='w|gz', compresslevel=1) as tar:
            for logical, disk in files:
                info = tar.gettarinfo(disk, arcname=logical)
                if info.islnk():
                    tar.addfile(info)
                    digest = by_arc.get(info.linkname)
                else:
                    with open(disk, 'rb') as f:
                        hr = HashReader(f)
                        tar.addfile(info, hr)
                        digest = hr.h.hexdigest()
                    by_arc[logical] = digest
                st = os.stat(disk, follow_symlinks=False)
                entries.append({'path': logical, 'size': st.st_size, 'mtime': st.st_mtime, 'sha256': digest})
    os.replace(tmp, target)
    return hw.n, hw.h.hexdigest(), entries


def archive_part(paths, part, now=None, patterns=None, free=None):
    """Archive one part; returns the log line (also appended to the log)."""
    now = now or dt.datetime.now().astimezone()
    patterns = strict_patterns() if patterns is None else patterns
    only = cov.drive_only(part)
    drive = Path(paths['drive'])
    if only:
        refuse_drive_inside_backup(paths)
    files, links, left = gather(paths['main'], part, patterns, paths.get('extra'))
    size = sum(os.path.getsize(d) for _, d in files)
    line = {'part': part, 'source': part.rsplit('/', 1)[0] if part.endswith('/' + cov.LOOSE) else part}
    if only:
        line['drive_only'] = True
    have = (free or (lambda p: shutil.disk_usage(p).free))(drive if drive.exists() else drive.anchor)
    if have - size < FLOOR:
        line.update(stopped='Drive free would fall below 4 GiB', free=have, part_bytes=size)
    else:
        folder = drive / ('parts_' + now.strftime('%Y%m%d'))
        folder.mkdir(parents=True, exist_ok=True)
        stem = part.replace('/', '__').replace('(', '').replace(')', '') + '__' + now.strftime('%Y%m%d-%H%M%S')
        target = folder / (stem + '.tar.gz')
        written, digest, entries = write_archive(target, files)
        manifest = folder / (stem + '.manifest.json')
        manifest.write_text(json.dumps({'part': part, 'archive': target.name, 'entries': entries}, indent=0),
                            encoding='utf-8', newline='\n')
        mdigest = cov.sha256_file(manifest)
        ok = target.stat().st_size == written and cov.sha256_file(target) == digest
        line.update(file=str(target), bytes=written, sha256=digest, files=len(files), arc_prefix='',
                    links_not_followed=len(links), manifest=str(manifest), manifest_sha256=mdigest, verified=ok)
        line.update(left_counts(left) if only else {'links': links, 'left_out': [p for p, _ in left]})
    line.update(time=now.isoformat(timespec='seconds'), tool=TOOL)
    with open(paths['log'], 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(line) + '\n')
    return line


def left_counts(left):
    """A drive-only part's log and printed line: what was left out, by reason, as counts; never a name."""
    counts = {}
    for _, why in left:
        counts[why] = counts.get(why, 0) + 1
    return {'left_out_counts': counts}


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def refuse_drive_inside_backup(paths):
    """A drive-only part is written to Drive only: a Drive folder inside the main checkout or the git backup
    repository would put it where git carries it."""
    for key in ('main', 'repo'):
        if paths.get(key) and inside(paths['drive'], paths[key]):
            raise Refused('the Drive folder is inside the %s; a drive-only part never goes there' % key)


def keep_report(paths, keep):
    """[(part, [archive paths beyond the newest `keep`])]: a report; nothing is deleted."""
    lines = cov.read_log(paths['log'])
    groups = {}
    for a in cov.drive_archives(lines, paths['drive'], paths['main'], list_max=0):
        key = a.line.get('source') or (a.scope if a.scope else a.line.get('part')) or a.name
        groups.setdefault(key, []).append(a)
    out = []
    for key, items in sorted(groups.items()):
        items.sort(key=lambda a: a.when, reverse=True)
        if len(items) > keep:
            out.append((key, [str(a.path) for a in items[keep:]]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('parts', nargs='*')
    ap.add_argument('--all', action='store_true', help='every part not already covered on Drive')
    ap.add_argument('--force', action='store_true', help='archive a part even when Drive already covers it')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--keep-report', action='store_true')
    ap.add_argument('--keep', type=int, default=3)
    ap.add_argument('--main')
    ap.add_argument('--drive')
    ap.add_argument('--log')
    ap.add_argument('--repo')
    args = ap.parse_args(argv)
    paths = cov.default_paths(args.main)
    for key in ('drive', 'log', 'repo'):
        if getattr(args, key):
            paths[key] = Path(getattr(args, key))
    if args.keep_report:
        report = keep_report(paths, args.keep)
        for key, older in report:
            print('%s: %d archives beyond the newest %d (report only, nothing deleted)' % (key, len(older), args.keep))
            for p in older:
                print('    ' + p)
        if not report:
            print('no part has more than %d verified archives' % args.keep)
        return 0
    report = cov.coverage(paths, secret_check=lambda u: set())
    rows = {r['part']: r for r in report['parts']}
    wanted = list(args.parts) or ([p for p, r in rows.items() if r['status'] != 'EXCLUDED'] if args.all else [])
    if not wanted:
        print('name parts or pass --all')
        return 2
    # irreplaceable parts first, vllm_test last (it is large and regenerable)
    wanted.sort(key=lambda p: (not rows.get(p, {}).get('irreplaceable'), 'vllm_test' in p, p))
    status = 0
    for part in wanted:
        row = rows.get(part)
        if row is None or row['status'] == 'EXCLUDED':
            print(json.dumps({'part': part, 'refused': 'not a part, or excluded as regenerable'}))
            status = 2
            continue
        drive_full = row['files'] > 0 and row['drive_files'] + len(row['excluded']) >= row['files']
        if drive_full and not args.force:
            print(json.dumps({'part': part, 'skipped': 'already covered on Drive'}))
            continue
        try:
            if args.dry_run:
                files, links, left = gather(paths['main'], part, strict_patterns(), paths.get('extra'))
                out = {'part': part, 'files': len(files), 'bytes': sum(os.path.getsize(d) for _, d in files),
                       'links_not_followed': len(links)}
                out.update(left_counts(left) if cov.drive_only(part) else {'left_out': [p for p, _ in left]})
                print(json.dumps(out))
                continue
            line = archive_part(paths, part)
        except Refused as exc:
            print(json.dumps({'part': part, 'refused': str(exc)}))
            status = 2
            continue
        print(json.dumps(line), flush=True)
        if line.get('stopped'):
            return 1
        if not line.get('verified'):
            status = 1
    return status


if __name__ == '__main__':
    raise SystemExit(main())
