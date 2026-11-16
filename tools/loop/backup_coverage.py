"""Backup coverage of the main checkout's data (D-702 item 4, D-704 item 3; standing orders 98 and 101).

    py -3.12 -X utf8 tools/loop/backup_coverage.py           # one line per part, then a summary
    py -3.12 -X utf8 tools/loop/backup_coverage.py --gaps 5  # also up to five uncovered paths per part
    py -3.12 -X utf8 tools/loop/backup_coverage.py --json    # the same as one JSON document

Read-only. It walks the main checkout's docs/loop/private, output/ and external/ (found through shared_paths,
never through a link) without ever entering a junction or symlink: a link is recorded as a link, its target is
not walked. A part is a top-level folder of a root (the root's loose files are one part, `(files)`), and each
folder of external/s05 is its own part. Each file is covered when one of the two backups holds it:

(a) the private git backup: the last snapshot of backup_records, the `records/private` branch of the bare
    repository <USER_HOME>/local/shimmer-history-backup/records, read with `git ls-tree -r`; a file is covered
    when its path is in the tree with the blob id its present content has (the id `git hash-object --no-filters`
    gives, computed here without writing any object);
(b) a verified Google Drive archive: a backup_log.jsonl line with `verified: true` whose archive is present on
    the Drive folder with the logged size. A file is covered when the archive's manifest (drive_archive) or its
    member list (a zip, or a tar.gz up to LIST_MAX bytes) holds its path with the same size and modification
    time. A larger legacy tar.gz with no manifest is judged by time only: a file of its part is covered when it
    was last written or created no later than the archive.

Each part is COVERED (every file held), STALE (a backup holds the part but some files are newer than it or not
in it) or NOT COVERED (no backup holds anything of it); the line gives the bytes and newest time not covered.
Deliberately excluded, never counted as gaps: credential-like names (CRED), the files backup_records holds back
for review (its last log line), files its secret scan would hold back now, and the folders it leaves out as
regenerable (output/cloud_wheels, __pycache__). The exit is 1 when an irreplaceable part (the records under
docs/loop/private, run evidence under external/s05, fingerprints under external/gate_prep*, a sealed set: any
part holding a seal.json) is STALE or NOT COVERED, 2 when the coverage cannot be read, otherwise 0.

Drive-only roots outside the repository (operator, 16 November 2026 20:41): config/backup_extra_roots.json
declares folders under the roles root (SHIMMER_ROLES_ROOT when set, else the main checkout's sibling folder it
names), today the role exchange folder `_xfer` and role N's negotiation sets. Each is walked as
`roles/<folder>/...`, its top-level folders are parts, and every part is covered by verified Drive archives
only: the git snapshot is never counted for them, and a snapshot that holds any `roles/` path is a fault (exit
1). Declared role folders (at the roles root and directly under a declared root) and any name containing a
declared word are never opened: they are recorded as excluded by declaration. For these roots the printed and
JSON report carry counts only, never a path inside a part.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shared_paths  # noqa: E402
from cloud_run_common import no_window  # noqa: E402  (HIDDEN-A; on the path through shared_paths)

ROOTS = (('private', ('docs', 'loop', 'private')), ('output', ('output',)), ('external', ('external',)))
SPLIT = ('external/s05',)                      # folders whose sub-folders are parts of their own
REGENERABLE = {'output/cloud_wheels': 'rebuilt from the pinned requirements (backup_records leaves it out)'}
SKIP_DIRS = ('__pycache__',)
BRANCH = 'records/private'
GIT_MAX = 50 * 1024 * 1024                     # backup_records stores nothing larger
LIST_MAX = 256 * 1024 * 1024                   # a legacy tar.gz up to this size is read for its member list
MTIME_SLACK = 2.0                              # zip times have two-second steps
CRED = ('.env', 'credential', 'api_key', 'secret', 'token', 'config.py', '.pem', '.key')
DRIVE_TOOLS = ('drive_archive', 'drive_external', 'drive_backup')
LOOSE = '(files)'
EXTRA_CONFIG = HERE.parents[1] / 'config' / 'backup_extra_roots.json'
EXTRA_NS = 'roles'                             # every declared extra root is walked as roles/<folder>/...


class CoverageError(Exception):
    """The coverage cannot be read (a git failure, an unreadable log)."""


def default_paths(main=None, environ=None, config_path=None):
    main = Path(main) if main else shared_paths.main_checkout()
    return {'main': main, 'repo': main.parent / 'shimmer-history-backup' / 'records',
            'drive': Path('G:/My Drive/Shimmer_backups'),
            'log': main.joinpath('docs', 'loop', 'private', 'backup_log.jsonl'),
            'extra': extra_roots(main, environ, config_path)}


def load_extra_config(path=None):
    """The declared drive-only roots, or None with no declaration; a malformed one raises CoverageError."""
    path = Path(path or EXTRA_CONFIG)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as exc:
        raise CoverageError('%s is not JSON (%s)' % (path.name, exc))
    if data.get('version') != 1 or not isinstance(data.get('roots'), list):
        raise CoverageError('%s is not a version 1 declaration' % path.name)
    for r in data['roots']:
        folder = str(r.get('folder') or '')
        if not folder or folder in ('.', '..') or any(c in folder for c in '/\\:'):
            raise CoverageError('%s: a root folder must be one plain folder name' % path.name)
        if r.get('drive_only') is not True:
            raise CoverageError('%s: root %s is not declared drive_only; the git backup never carries a '
                                'root outside the repository' % (path.name, folder))
    return data


def excluded_name(name, depth, spec):
    """Why a name is out of scope by declaration, or ''. depth 0 is a declared root itself, 1 an entry directly
    under it, deeper entries more; role folders match at depth 0 and 1, declared words at any depth."""
    if not spec:
        return ''
    low = name.casefold()
    if any(str(w).casefold() in low for w in spec.get('name_contains', ())):
        return 'declared name'
    if depth <= 1 and low in {str(r).casefold() for r in spec.get('role_folders', ())}:
        return 'declared role folder'
    return ''


def roles_location(main, environ=None, location=None):
    """(folder, how) of the roles root: the declared variable when set (an absolute folder, not a link), else
    the main checkout's sibling folder the declaration names."""
    environ = os.environ if environ is None else environ
    location = location or {}
    var = location.get('env')
    value = str(environ.get(var) or '').strip() if var else ''
    if value:
        p = Path(value)
        if not p.is_absolute() or is_link(p) or not p.is_dir():
            raise CoverageError('%s must name an existing folder by an absolute path, not a link' % var)
        return p, var
    sibling = location.get('sibling_of_main_checkout')
    if not sibling:
        return None, 'not declared'
    return Path(main).parent / sibling, 'sibling of the main checkout'


def extra_roots(main, environ=None, config_path=None):
    """{'roots': [{logical, disk, irreplaceable}], 'refused': [(logical, why)], 'missing': [logical],
    'location', 'how', 'spec' (the exclusions)}; nothing declared when the file is absent."""
    data = load_extra_config(config_path)
    out = {'roots': [], 'refused': [], 'missing': [], 'location': None, 'how': 'not declared', 'spec': {}}
    if not data:
        return out
    location, how = roles_location(main, environ, data.get('roots_location'))
    out.update(location=str(location) if location else None, how=how, spec=data.get('excluded') or {})
    for r in data['roots']:
        logical = EXTRA_NS + '/' + r['folder']
        why = excluded_name(r['folder'], 0, out['spec'])
        if why:
            out['refused'].append((logical, why))
            continue
        disk = location / r['folder'] if location is not None else None
        if disk is None or not (disk.exists() or is_link(disk)):
            out['missing'].append(logical)
            continue
        out['roots'].append({'logical': logical, 'disk': disk,
                             'irreplaceable': r.get('irreplaceable') or 'drive-only root'})
    return out


def drive_only(logical):
    """A path or part under a declared drive-only root (roles/...): Drive archives only, never git."""
    return str(logical).split('/')[0] == EXTRA_NS


def drive_only_carried(files, location=None):
    """The repo paths of (repo path, disk path, ...) entries a git snapshot must refuse: a roles/ path, or a
    file inside the roles root."""
    loc = Path(location).resolve() if location else None
    bad = []
    for f in files:
        rel, disk = f[0], f[1]
        if drive_only(rel):
            bad.append(rel)
        elif loc is not None:
            try:
                Path(disk).resolve().relative_to(loc)
                bad.append(rel)
            except ValueError:
                pass
    return bad


def is_link(path):
    p = str(path)
    return os.path.islink(p) or bool(getattr(os.path, 'isjunction', lambda q: False)(p))


def credential_name(name):
    low = name.lower()
    return any(c in low for c in CRED)


def changed_time(st):
    """The later of the last write and (on Windows) the creation of this name: a copy or move keeps the old
    write time but gets a new creation time."""
    return max(st.st_mtime, getattr(st, 'st_birthtime', 0.0) or 0.0)


def part_of(logical):
    bits = logical.split('/')
    if bits[0] == EXTRA_NS and len(bits) >= 3:
        return '/'.join(bits[:2]) + '/' + (bits[2] if len(bits) > 3 else LOOSE)
    for split in SPLIT:
        depth = split.count('/') + 1
        if logical.startswith(split + '/'):
            return split + '/' + (bits[depth] if len(bits) > depth + 1 else LOOSE)
    return bits[0] + '/' + (bits[1] if len(bits) > 2 else LOOSE)


def link_part(logical):
    if '/' not in logical or (drive_only(logical) and logical.count('/') == 1):
        return logical + '/' + LOOSE
    return part_of(logical)


def wanted(logical_dir, within):
    """Whether a walk limited to the part `within` enters this folder."""
    return (within is None or logical_dir == within or within.startswith(logical_dir + '/')
            or logical_dir.startswith(within + '/'))


def walk(main, within=None, extra=None, declared=None):
    """(files {logical: (disk path, size, mtime, changed, (device, inode))}, links [logical], regenerable
    {part: reason}); with `within` (a part), only the folders that part can hold are entered. `extra` adds the
    declared drive-only roots; a name they exclude by declaration is never opened and goes into `declared`
    {logical: (why, is a folder)}."""
    files, links, skipped = {}, [], {}
    declared = {} if declared is None else declared
    extra = extra or {}
    sources = [(name, Path(main).joinpath(*rel), None) for name, rel in ROOTS]
    sources += [(r['logical'], Path(r['disk']), extra.get('spec') or {}) for r in extra.get('roots', ())]
    for name, root, spec in sources:
        if within is not None and not (within == name or within.startswith(name + '/')):
            continue
        if is_link(root):
            links.append(name)
            continue
        if not root.is_dir():
            continue
        stack = [(root, name)]
        while stack:
            d, logical_dir = stack.pop()
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                logical = logical_dir + '/' + e.name
                if spec is not None:
                    why = excluded_name(e.name, logical.count('/') - name.count('/'), spec)
                    if why:           # never opened: the entry's type comes from the folder listing
                        declared[logical] = (why, e.is_dir(follow_symlinks=False))
                        continue
                if is_link(e.path):
                    links.append(logical)
                    continue
                if e.is_dir(follow_symlinks=False):
                    if logical in REGENERABLE:
                        skipped[logical] = REGENERABLE[logical]
                    elif e.name in SKIP_DIRS:
                        if part_of(logical + '/x') == logical:      # a part of its own; deeper ones are skipped
                            skipped[logical] = 'regenerable (__pycache__)'
                    elif wanted(logical, within):
                        stack.append((Path(e.path), logical))
                    continue
                # os.stat, not the entry's: on Windows only it fills st_ino and st_dev (hard links counted once)
                st = os.stat(e.path, follow_symlinks=False)
                files[logical] = (e.path, st.st_size, st.st_mtime, changed_time(st), (st.st_dev, st.st_ino))
    return files, links, skipped


def blob_id(path):
    """The id `git hash-object --no-filters` gives the file, computed without writing an object."""
    h = hashlib.sha1()
    h.update(b'blob %d\0' % os.path.getsize(path))
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def git_holds(tree, logical, disk, size):
    """The snapshot holds this path with the blob id of the file's present content."""
    held = tree.get(logical)
    return bool(held) and size <= GIT_MAX and blob_id(disk) == held


def git(repo, *args):
    done = subprocess.run(['git', '--git-dir', str(repo), *args], capture_output=True, timeout=600,
                          stdin=subprocess.DEVNULL, creationflags=no_window())
    if done.returncode != 0:
        raise CoverageError('git %s failed: %s' % (args[0], done.stderr.decode('utf-8', 'replace').strip()[:200]))
    return done.stdout.decode('utf-8', 'replace')


def git_snapshot(repo, branch=BRANCH):
    """(tree {path: blob id}, commit, commit time) of the last snapshot; ({}, None, None) with no repository."""
    if not Path(repo).is_dir():
        return {}, None, None
    try:
        commit = git(repo, 'rev-parse', '--verify', '-q', 'refs/heads/' + branch).strip()
    except CoverageError:
        return {}, None, None
    when = float(git(repo, 'log', '-1', '--format=%ct', commit).strip())
    tree = {}
    for rec in git(repo, 'ls-tree', '-r', '-z', commit).split('\0'):
        if '\t' in rec:
            meta, path = rec.split('\t', 1)
            bits = meta.split()
            if len(bits) == 3 and bits[1] == 'blob':
                tree[path] = bits[2]
    return tree, commit, when


def read_log(log):
    lines = []
    if not Path(log).exists():
        return lines
    with open(log, encoding='utf-8') as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                try:
                    lines.append(json.loads(raw))
                except ValueError:
                    continue
    return lines


def parse_time(text):
    try:
        return dt.datetime.fromisoformat(str(text)).timestamp()
    except (TypeError, ValueError):
        return None


def held_back(lines):
    """The paths backup_records' last run held back for review (repo paths: private/..., output/...)."""
    for line in reversed(lines):
        if line.get('tool') == 'backup_records':
            return set(line.get('held_back_for_review') or [])
    return set()


class Archive:
    """One verified Drive archive: the file, its time, and what it holds (members, or a scope judged by time)."""

    def __init__(self, line, path, when):
        self.line, self.path, self.when = line, Path(path), when
        self.members = None          # {logical: (size, mtime)} when the content list is known
        self.scope = None            # a logical folder, judged by time, when it is not
        self.how = ''

    @property
    def name(self):
        return self.path.name


def archive_ok(line, path):
    """The log says verified and the archive is on Drive with the logged size."""
    try:
        return bool(line.get('verified') is True and path.is_file() and int(line.get('bytes')) == path.stat().st_size)
    except (TypeError, ValueError, OSError):
        return False


def legacy_scope(part, main):
    """drive_external's part name: s05__X is external/s05/X, any other name external/<name>; a time suffix
    (s05__GATE_1845) is dropped when the folder with the suffix does not exist."""
    rel = part.replace('__', '/')
    logical = 'external/' + rel
    if not Path(main).joinpath('external', *rel.split('/')).exists():
        stripped = re.sub(r'_\d{4}$', '', logical)
        if stripped != logical:
            return stripped
    return logical


def read_manifest(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    return {e['path']: (e['size'], e['mtime']) for e in data['entries']}


def list_members(archive, prefix, list_max=None):
    p = archive.path
    if p.suffix == '.zip':
        out = {}
        with zipfile.ZipFile(p) as z:
            for i in z.infolist():
                if not i.is_dir():
                    out[prefix + i.filename] = (i.file_size, time.mktime(i.date_time + (0, 0, -1)))
        return out
    if p.name.endswith('.tar.gz') and p.stat().st_size <= (LIST_MAX if list_max is None else list_max):
        out = {}
        with tarfile.open(p, 'r|gz') as t:
            for m in t:
                if m.isfile():
                    out[prefix + m.name] = (m.size, float(m.mtime))
                elif m.islnk():          # a hard link member carries no size; its target holds the bytes
                    out[prefix + m.name] = (None, float(m.mtime))
        return out
    return None


def drive_archives(lines, drive, main, list_max=None):
    found = []
    for line in lines:
        tool = line.get('tool')
        if tool not in DRIVE_TOOLS or not line.get('file'):
            continue
        path = Path(line['file'])
        if not path.is_absolute():
            path = Path(drive) / path
        when = parse_time(line.get('time'))
        if when is None or not archive_ok(line, path):
            continue
        a = Archive(line, path, when)
        prefix = line.get('arc_prefix', 'external/' if tool == 'drive_external' else '')
        manifest = line.get('manifest')
        if manifest:
            mpath = Path(manifest) if Path(manifest).is_absolute() else Path(drive) / manifest
            if mpath.is_file() and (not line.get('manifest_sha256')
                                    or sha256_file(mpath) == line['manifest_sha256']):
                a.members, a.how = read_manifest(mpath), 'manifest'
        if a.members is None:
            try:
                a.members = list_members(a, prefix, list_max)
                a.how = 'members' if a.members is not None else ''
            except (OSError, tarfile.TarError, zipfile.BadZipFile, EOFError):
                a.members = None
        if a.members is None:
            if tool == 'drive_external' and line.get('part'):
                a.scope, a.how = legacy_scope(line['part'], main), 'time'
            elif line.get('source'):
                a.scope, a.how = line['source'], 'time'
            else:
                continue
        found.append(a)
    return found


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def drive_holds(archive, logical, size, mtime, changed):
    if archive.members is not None:
        held = archive.members.get(logical)
        if held is None:
            return False
        hsize, hmtime = held
        return (hsize is None or hsize == size) and abs(float(hmtime) - mtime) <= MTIME_SLACK
    return (logical == archive.scope or logical.startswith(archive.scope + '/')) and changed <= archive.when


def touches(archive, part):
    if archive.members is not None:
        if not hasattr(archive, 'parts'):
            archive.parts = {part_of(m) for m in archive.members}
        return part in archive.parts
    return archive.scope == part or archive.scope.startswith(part + '/') or part.startswith(archive.scope + '/')


def default_secret_check(uncovered):
    """backup_records' own scan over uncovered records and outputs: paths it would hold back now."""
    try:
        import backup_records
    except Exception:
        return set()
    files = [(rel, path, size) for rel, path, size in uncovered
             if size <= 5 * 1024 * 1024 and rel.split('/')[0] in ('private', 'output')]
    flagged = {rel for rel, _ in backup_records.secret_hits(files)}
    # a drive-only file holding a key body is left out by drive_archive, so it is excluded here too
    patterns = [rx for _, rx in backup_records.STRICT]
    for rel, path, size in uncovered:
        if drive_only(rel) and size <= 5 * 1024 * 1024:
            try:
                text = Path(path).read_bytes().decode('utf-8', errors='ignore')
            except OSError:
                continue
            if any(rx.search(text) for rx in patterns):
                flagged.add(rel)
    return flagged


def irreplaceable(part, files_in_part):
    """Why the part cannot be rebuilt ('records', 'run evidence', 'fingerprint', 'sealed set'), or ''."""
    if part.startswith('private/'):
        return 'records'
    if part.startswith('external/s05/'):
        return 'run evidence'
    if part.startswith('external/gate_prep'):
        return 'fingerprint'
    if any(Path(logical).name == 'seal.json' for logical in files_in_part):
        return 'sealed set'
    return ''


def unique_bytes(pairs):
    """The bytes of (size, (device, inode)) pairs with each hard-linked file counted once."""
    seen, loose = {}, 0
    for size, ident in pairs:
        if ident[1]:
            seen[ident] = size
        else:                    # no inode number: counted as it is
            loose += size
    return sum(seen.values()) + loose


def coverage(paths, secret_check=default_secret_check, list_max=None):
    """{'parts': [...], 'links': [...], 'excluded': [...], 'git': {...}, 'drive': [...]}."""
    main = paths['main']
    extra = paths.get('extra') or {}
    declared = {}
    files, links, skipped = walk(main, extra=extra, declared=declared)
    reasons = {r['logical']: r['irreplaceable'] for r in extra.get('roots', ())}
    tree, commit, git_when = git_snapshot(paths['repo'])
    in_git_refused = sorted(p for p in tree if drive_only(p))
    lines = read_log(paths['log'])
    archives = drive_archives(lines, paths['drive'], main, list_max)
    held = held_back(lines)
    by_part = {}
    for logical, info in files.items():
        by_part.setdefault(part_of(logical), {})[logical] = info
    for logical in links:
        by_part.setdefault(link_part(logical), {})
    for part in skipped:
        by_part.setdefault(part, {})
    own_declared, declared_in = {}, {}
    for logical, (why, is_dir) in declared.items():
        if is_dir and logical.count('/') == 2:          # a folder directly under a declared root: its own part
            own_declared[logical] = why
            by_part.setdefault(logical, {})
        else:
            declared_in[part_of(logical)] = declared_in.get(part_of(logical), 0) + 1
            by_part.setdefault(part_of(logical), {})
    uncovered_all = []
    result = {}
    for part, members in sorted(by_part.items()):
        row = {'part': part, 'files': len(members), 'bytes': unique_bytes((i[1], i[4]) for i in members.values()),
               'git_files': 0, 'drive_files': 0, 'gap': [], 'excluded': [],
               'links': sorted(x for x in links if link_part(x) == part),
               'regenerable': skipped.get(part), 'irreplaceable': irreplaceable(part, members),
               'drive_only': drive_only(part), 'declared': own_declared.get(part),
               'declared_excluded': declared_in.get(part, 0) + (1 if part in own_declared else 0)}
        if row['drive_only']:      # its declared reason; a part out of scope by declaration is never a fault
            row['irreplaceable'] = '' if row['declared'] else reasons.get('/'.join(part.split('/')[:2]),
                                                                           'drive-only root')
        row['git_time'] = None if row['drive_only'] else (
            git_when if any(part_of(p) == part for p in tree) else None)
        times = [a.when for a in archives if touches(a, part)]
        row['drive_time'] = max(times) if times else None
        for logical, (disk, size, mtime, changed, ident) in members.items():
            in_git = (not row['drive_only']) and git_holds(tree, logical, disk, size)
            in_drive = any(drive_holds(a, logical, size, mtime, changed) for a in archives)
            row['git_files'] += in_git
            row['drive_files'] += in_drive
            if not (in_git or in_drive):
                if credential_name(Path(logical).name) or logical in held:
                    row['excluded'].append(logical)
                else:
                    row['gap'].append((logical, disk, size, max(mtime, changed), ident))
        uncovered_all.extend(g[:3] for g in row['gap'])
        result[part] = row
    flagged = secret_check(uncovered_all) if uncovered_all else set()
    for row in result.values():
        keep = []
        for g in row['gap']:
            (row['excluded'] if g[0] in flagged else keep).append(g[0] if g[0] in flagged else g)
        row['gap'] = keep
        row['gap_bytes'] = unique_bytes((g[2], g[4]) for g in keep)
        row['gap_newest'] = max((g[3] for g in keep), default=None)
        row['gap_files'], row['links_count'], row['excluded_count'] = len(keep), len(row['links']), len(row['excluded'])
        if (row['regenerable'] or row['declared']) and not row['files']:
            row['status'] = 'EXCLUDED'
        elif not row['gap']:
            row['status'] = 'COVERED'
        elif row['git_time'] or row['drive_time'] or row['git_files'] or row['drive_files']:
            row['status'] = 'STALE'
        else:
            row['status'] = 'NOT COVERED'
    return {'parts': list(result.values()), 'links': sorted(links), 'held_back': sorted(held),
            'git': {'repo': str(paths['repo']), 'commit': commit, 'time': git_when, 'files': len(tree),
                    'drive_only_in_git': len(in_git_refused)},
            'drive': [{'file': str(a.path), 'time': a.when, 'how': a.how} for a in archives],
            'skipped': skipped,
            'extra': {'location': extra.get('location'), 'how': extra.get('how', 'not declared'),
                      'roots': [r['logical'] for r in extra.get('roots', ())],
                      'missing': list(extra.get('missing', ())), 'refused': list(extra.get('refused', ())),
                      'declared_excluded': len(declared)}}


def faults(report):
    return [r for r in report['parts'] if r['irreplaceable'] and r['status'] in ('STALE', 'NOT COVERED')]


def git_refusal(report):
    """How many paths under a drive-only root the git snapshot holds: never allowed, a fault of its own."""
    return int(report['git'].get('drive_only_in_git') or 0)


def public(report):
    """The report as printed or written: a drive-only part carries counts only, never a path inside it."""
    out = dict(report, parts=[])
    for r in report['parts']:
        r = dict(r)
        if r.get('drive_only'):
            r['gap'], r['excluded'], r['links'] = [], [], []
        out['parts'].append(r)
    out['links'] = [x for x in report['links'] if not drive_only(x)]
    out['drive_only_links'] = len(report['links']) - len(out['links'])
    out['held_back'] = [x for x in report.get('held_back', ()) if not drive_only(x)]
    return out


def stamp(t):
    if t is None:
        return '-'
    return dt.datetime.fromtimestamp(t).astimezone().strftime('%Y-%m-%d %H:%M')


def render(report, gaps=0):
    full, report = report, public(report)
    out = []
    for r in report['parts']:
        line = '%-11s %-46s files %5d  git %-16s drive %-16s' % (
            r['status'], r['part'], r['files'], stamp(r['git_time']), stamp(r['drive_time']))
        if r['gap_files']:
            line += '  not covered %d files, %d bytes, newest %s' % (r['gap_files'], r['gap_bytes'],
                                                                     stamp(r['gap_newest']))
        if r['irreplaceable'] and r['status'] != 'EXCLUDED':
            line += '  [irreplaceable: %s]' % r['irreplaceable']
        if r['links_count']:
            line += '  links %d' % r['links_count']
        if r['excluded_count']:
            line += '  excluded %d' % r['excluded_count']
        if r.get('declared_excluded'):
            line += '  excluded by declaration %d' % r['declared_excluded']
        if r.get('drive_only'):
            line += '  [drive only]'
        if r['regenerable'] and r['status'] == 'EXCLUDED':
            line += '  (%s)' % r['regenerable']
        if r.get('declared') and r['status'] == 'EXCLUDED':
            line += '  (%s, never opened)' % r['declared']
        out.append(line)
        if r.get('drive_only') and gaps and r['gap_files']:
            out.append('    paths not printed (drive-only root)')
        for g in r['gap'][:gaps]:
            out.append('    not covered: %s (%d bytes, %s)' % (g[0], g[2], stamp(g[3])))
    excluded = sorted(x for r in report['parts'] for x in r['excluded'])
    if excluded:
        out.append('deliberately excluded (credential names, held back by backup_records), never gaps:')
        out.extend('    ' + x for x in excluded)
    if report['links']:
        out.append('links recorded, never followed:')
        out.extend('    ' + x for x in report['links'])
    if report['drive_only_links']:
        out.append('links under drive-only roots recorded, never followed: %d' % report['drive_only_links'])
    x = report.get('extra') or {}
    if x.get('roots') or x.get('missing') or x.get('refused'):
        out.append('drive-only roots (%s, %s): %s; missing %s; refused %s; excluded by declaration, never '
                   'opened: %d' % (x.get('location'), x.get('how'), ', '.join(x.get('roots') or []) or 'none',
                                   ', '.join(x.get('missing') or []) or 'none',
                                   ', '.join('%s (%s)' % tuple(r) for r in x.get('refused') or []) or 'none',
                                   x.get('declared_excluded', 0)))
    if git_refusal(full):
        out.append('REFUSED: the git backup holds %d paths under a drive-only root; they must never be in git'
                   % git_refusal(full))
    g = report['git']
    out.append('git backup: %s, commit %s, %s, %d files' % (g['repo'], (g['commit'] or 'none')[:12], stamp(g['time']),
                                                         g['files']))
    out.append('drive archives verified and present: %d (%d with a content list, %d judged by time)' % (
        len(report['drive']), sum(1 for a in report['drive'] if a['how'] != 'time'),
        sum(1 for a in report['drive'] if a['how'] == 'time')))
    counts = {}
    for r in report['parts']:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    bad = faults(report)
    out.append('bytes not covered (hard links once): all parts %d, irreplaceable parts %d' % (
        unique_bytes((g[2], g[4]) for r in report['parts'] for g in r['gap']),
        unique_bytes((g[2], g[4]) for r in bad for g in r['gap'])))
    out.append('parts: %s; irreplaceable not covered or stale: %d%s' % (
        ', '.join('%s %d' % kv for kv in sorted(counts.items())), len(bad),
        (' (' + ', '.join(r['part'] for r in bad) + ')') if bad else ''))
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--main', help='the main checkout (default: shared_paths)')
    ap.add_argument('--repo')
    ap.add_argument('--drive')
    ap.add_argument('--log')
    ap.add_argument('--gaps', type=int, default=0, help='print up to N uncovered paths per part')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    try:
        paths = default_paths(args.main)
        for key in ('repo', 'drive', 'log'):
            if getattr(args, key):
                paths[key] = Path(getattr(args, key))
        report = coverage(paths)
    except (CoverageError, shared_paths.MainCheckoutError, OSError) as exc:
        print('coverage not readable: %s' % exc)
        return 2
    if args.json:
        print(json.dumps(public(report), default=str, indent=1))
    else:
        print(render(report, args.gaps))
    return 1 if faults(report) or git_refusal(report) else 0


if __name__ == '__main__':
    raise SystemExit(main())
