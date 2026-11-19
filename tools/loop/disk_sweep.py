"""Delete only regenerable files inside the main checkout, by declared kinds (D-611, issue #266).

The standing approval of 13 November 2026 (D-611) lets the loop delete regenerable intermediates,
caches and finished-run temporaries on a schedule, and whenever free disk is under the sweep's own
32 GiB trigger (register_disk_sweep.py; set from the old 30 GiB floor of D-099, which the 19 November 2026
rule of a job's footprint plus 12 GiB replaced for heavy work). This tool is that deletion and nothing wider:

* It deletes ONLY a path that a kind declared in `config/disk_sweep.json` matches (a name rule, a
  reason and how to regenerate it). Anything unmatched is kept.
* It never deletes: anything under docs/loop, docs/fix, config, durable, ontology, .git or .claude; any
  private folder; a fingerprint; any file git tracks (or a folder holding one); a sealed bundle (a folder
  holding a seal or manifest file, or inside one) unless its kind says it may sit in or hold one and the
  other refusals pass; the run folder of a launch with no termination line in the budget ledger; any
  path named inside a seal, manifest, FINAL_STATUS, fingerprint, REQUEST file or `_xfer` / `_handoff`
  hand-off folder (the reference index: path strings and 64-hex digests found in those files); a link
  or junction.
* The worktree kind only REPORTS (a lane worktree whose branch is merged into the loop ref and whose tree
  is clean); no version of this tool deletes one.
* Every run reads the free disk first; `--dry-run` deletes nothing; `--apply` deletes by
  `safe_delete.check` then `safe_delete.delete` on the exact path (DELETE-SAFE-A; links inside are refused), after re-checking that path against every refusal
  just before deleting it, and appends one JSON line per deletion to
  `docs/loop/private/disk_sweep_log.jsonl` of the MAIN checkout (time from the clock, path, bytes, kind,
  reason, regenerate). After the run a post-check confirms that every indexed path that existed still
  exists. One summary line is printed: freed GiB, items, free disk before and after.
* `--apply` is refused unless `--root` is the main checkout, the reference index is complete and the budget
  ledger is readable (a failed read never reads as "no open launch").

    py -3.12 -X utf8 tools/loop/disk_sweep.py --dry-run [--root <main checkout>] [--inventory]
    py -3.12 -X utf8 tools/loop/disk_sweep.py --apply --if-free-below-gib 32   # the load watcher's call

Nothing here opens benchmark data, a key or an answer file: sizes and names only, plus the text of the
reference files named above (scanned for path strings and digests).
"""
from __future__ import annotations

import argparse
import bisect
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud_run_common import no_window  # noqa: E402  (D-079, HIDDEN-A)

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
ROOT = HERE.parents[1]
CONFIG = ROOT / 'config' / 'disk_sweep.json'
LOG_NAME = 'disk_sweep_log.jsonl'
LOCK_NAME = 'disk_sweep.lock'
LOCK_STALE_SECONDS = 6 * 3600
GIB = 1 << 30
HASH_FILE_CAP = 256 << 20       # a file in a candidate larger than this is not hashed: the candidate is refused
HASH_TOTAL_CAP = 2 * GIB
NLINK_PROBE_BYTES = 1 << 20     # only files this large are asked for their link count (os.stat per file is slow)

PATH_RE = re.compile(rb'(?:[A-Za-z]:)?[\\/]{0,4}(?:[A-Za-z0-9_.@+=\-]+[\\/]{1,4})+[A-Za-z0-9_.@+=\-]+')
FILE_RE = re.compile(rb'[A-Za-z_][A-Za-z0-9_\-]*\.[A-Za-z][A-Za-z0-9]{0,7}')
DIGEST_RE = re.compile(rb'(?<![0-9A-Fa-f])[0-9a-fA-F]{64}(?![0-9A-Fa-f])')
CHUNK = 1 << 20
DEVICE_NAMES = {'nul', 'con', 'prn', 'aux'} | {'com%d' % n for n in range(1, 10)} | {'lpt%d' % n for n in range(1, 10)}
OVERLAP = 4096


class SweepError(RuntimeError):
    pass


# ----------------------------------------------------------------------------------------- paths

def norm(path):
    """One spelling for comparing paths: forward slashes, no repeated slash, lower case."""
    text = str(path).replace('\\', '/')
    text = re.sub(r'/{2,}', '/', text)
    if text.startswith('./'):
        text = text[2:]
    return text.rstrip('/').lower() if len(text) > 1 else text.lower()


def is_link(path):
    try:
        if os.path.islink(path):
            return True
        junction = getattr(os.path, 'isjunction', None)
        return bool(junction and junction(path))
    except OSError:
        return True


def load_config(path=None):
    cfg = json.loads(Path(path or CONFIG).read_text(encoding='utf-8'))
    if cfg.get('version') != 1 or not isinstance(cfg.get('kinds'), list):
        raise SweepError('config/disk_sweep.json is not a version 1 declaration')
    for kind in cfg['kinds']:
        for field in ('name', 'type', 'reason', 'regenerate'):
            if not kind.get(field):
                raise SweepError('kind %r has no %s' % (kind.get('name'), field))
    return cfg


def main_root(start=HERE, runner=subprocess.run):
    """The main checkout by shared_paths' one rule (SHIMMER_MAIN_CHECKOUT, else git's common directory), as
    tools/loop/session_end_salvage.py finds it."""
    import shared_paths
    try:
        return shared_paths.main_checkout(start, runner=runner)
    except shared_paths.MainCheckoutError as exc:
        raise SweepError(str(exc))


def git(root, *args, timeout=120):
    done = subprocess.run(['git', '-C', str(root)] + list(args), capture_output=True, timeout=timeout,
                          stdin=subprocess.DEVNULL, creationflags=no_window())
    if done.returncode != 0:
        raise SweepError('git %s failed (exit %d)' % (args[0], done.returncode))
    return done.stdout


# ----------------------------------------------------------------------------------------- kinds

def rel_of(root, path):
    return norm(os.path.relpath(str(path), str(root)))


def match_kind(cfg, rel, name, is_dir):
    """The declared kind that matches this entry, or None. `rel` is the root-relative normalised path."""
    for kind in cfg['kinds']:
        if kind.get('report_only') or kind['type'] not in ('dir', 'file'):
            continue
        if (kind['type'] == 'dir') != bool(is_dir):
            continue
        globs = [kind['name_glob']] + list(kind.get('also_name_globs', []))
        if not any(fnmatch.fnmatch(name.lower(), g.lower()) for g in globs):
            continue
        under = kind.get('under')
        if under and not any(rel == u or rel.startswith(u.lower().rstrip('/') + '/') for u in under):
            continue
        return kind
    return None


class Candidate:
    def __init__(self, path, kind):
        self.path = str(path)
        self.kind = kind

    def __repr__(self):
        return 'Candidate(%s, %s)' % (self.path, self.kind['name'])


class Scan:
    def __init__(self):
        self.candidates = []
        self.bundle_dirs = []      # folders holding a seal or manifest marker
        self.reference_files = []  # files the reference index reads
        self.errors = []


def _no_descend(cfg, name):
    return any(fnmatch.fnmatch(name.lower(), g.lower()) for g in cfg['no_descend_names'])


def _walk_all(folder):
    for base, dirs, files in os.walk(folder, followlinks=False):
        dirs[:] = [d for d in dirs if not is_link(os.path.join(base, d))]
        for name in files:
            yield os.path.join(base, name)


def scan_tree(root, cfg):
    """One walk of the checkout: candidates, sealed folders, reference files. A sealed folder is a leaf (only
    its direct entries are read, and a `batch` folder is entered); links are never followed or matched."""
    scan = Scan()
    markers = {m.lower() for m in cfg['sealed_markers']}
    ref_files = cfg['reference_file_globs']
    ref_dirs = cfg['reference_dir_globs']
    stack = [str(root)]
    while stack:
        folder = stack.pop()
        try:
            with os.scandir(folder) as it:
                entries = list(it)
        except OSError as exc:
            scan.errors.append('%s: %s' % (folder, type(exc).__name__))
            continue
        sealed = any(e.name.lower() in markers and e.is_file(follow_symlinks=False) for e in entries)
        if sealed:
            scan.bundle_dirs.append(folder)
        for entry in entries:
            if is_link(entry.path) or entry.name.split('.')[0].lower() in DEVICE_NAMES:
                continue
            is_dir = entry.is_dir(follow_symlinks=False)
            rel = rel_of(root, entry.path)
            if is_dir and any(fnmatch.fnmatch(entry.name.lower(), g.lower()) for g in ref_dirs):
                scan.reference_files.extend(_walk_all(entry.path))
            if not is_dir and any(fnmatch.fnmatch(entry.name.lower(), g.lower()) for g in ref_files):
                scan.reference_files.append(entry.path)
            kind = match_kind(cfg, rel, entry.name, is_dir)
            if kind is not None:
                scan.candidates.append(Candidate(entry.path, kind))
                if is_dir and any(os.path.isfile(os.path.join(entry.path, m)) for m in cfg['sealed_markers']):
                    scan.bundle_dirs.append(entry.path)     # a candidate folder may itself be a launch's bundle
                continue
            if is_dir:
                if _no_descend(cfg, entry.name):
                    continue
                if sealed and entry.name.lower() != 'batch':
                    continue
                stack.append(entry.path)
    return scan


# ----------------------------------------------------------------------------------------- reference index

class Index:
    """Path strings and 64-hex digests named in the reference files. `existing` are the indexed paths that
    exist inside the root when the index is built (what the post-check confirms again)."""

    def __init__(self):
        self.paths = set()
        self.sorted = []
        self.digests = set()
        self.errors = []
        self.skipped = []
        self.existing = set()
        self.files_read = 0

    def finish(self, root):
        self.sorted = sorted(self.paths)
        top = norm(root)
        for p in self.paths:
            if p == top or p.startswith(top + '/'):
                self.existing.add(p)


def _tokens(data):
    for m in PATH_RE.finditer(data):
        yield m.group(0), True
    for m in FILE_RE.finditer(data):
        yield m.group(0), False


def read_reference_file(index, root, path, cfg):
    """Path strings and digests of one reference file, read in chunks. A file over `reference_max_bytes` (50 MB)
    or named like a fingerprint is not read: fingerprints and archives are refused by kind and name."""
    name = os.path.basename(path).lower()
    if any(fnmatch.fnmatch(name, g.lower()) for g in cfg['never_name_globs']):
        index.skipped.append(path)
        return
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        index.errors.append('%s: %s' % (path, type(exc).__name__))
        return
    if size > cfg['reference_max_bytes']:
        index.skipped.append(path)
        return
    base = norm(os.path.dirname(path))
    top = norm(root)
    local = set()
    try:
        with open(path, 'rb') as stream:
            tail = b''
            while True:
                block = stream.read(CHUNK)
                if not block:
                    break
                data = tail + block
                for m in DIGEST_RE.finditer(data):
                    index.digests.add(m.group(0).decode('ascii').lower())
                for token, has_sep in _tokens(data):
                    text = norm(token.decode('ascii', 'ignore').replace('\\', '/'))
                    if not text:
                        continue
                    if re.match(r'^[a-z]:/', text):
                        local.add(text)
                    else:
                        local.add(base + '/' + text)
                        if has_sep:
                            local.add(top + '/' + text)
                tail = data[-OVERLAP:]
        index.files_read += 1
    except OSError as exc:
        index.errors.append('%s: %s' % (path, type(exc).__name__))
        return
    for text in local:       # only a path that exists can be a candidate or be removed: keep those
        if text in index.paths:
            continue
        if os.path.lexists(text):
            index.paths.add(text)


def build_index(root, reference_files, cfg):
    index = Index()
    for n, path in enumerate(reference_files):
        if n and n % 500 == 0:
            print('  index: %d files read' % n, file=sys.stderr, flush=True)
        read_reference_file(index, root, path, cfg)
    index.finish(root)
    return index


def indexed_reference(index, path):
    """What names this path: an indexed path equal to it, inside it, or one it lies inside; else None."""
    c = norm(path)
    if c in index.paths:
        return c
    parent = c.rsplit('/', 1)[0]
    if parent in index.paths:          # the folder it sits in is named (a bundle folder, a run folder)
        return parent
    i = bisect.bisect_left(index.sorted, c + '/')
    if i < len(index.sorted) and index.sorted[i].startswith(c + '/'):
        return index.sorted[i]
    return None


# ----------------------------------------------------------------------------------------- contents

class Contents:
    def __init__(self):
        self.files = 0
        self.logical = 0
        self.freed = 0               # bytes of files whose only link is inside the candidate
        self.names = set()           # lower-case file and folder names seen
        self.oversize = []           # files too large to hash
        self.hash_files = []         # (path, size) of files to hash for the digest check
        self.tracked_hit = None


def contents_of(path):
    out = Contents()
    p = str(path)
    if os.path.isfile(p):
        walker = [(os.path.dirname(p), [], [os.path.basename(p)])]
    else:
        walker = os.walk(p, followlinks=False)
    for base, dirs, files in walker:
        dirs[:] = [d for d in dirs if not is_link(os.path.join(base, d))]
        for d in dirs:
            out.names.add(d.lower())
        for name in files:
            full = os.path.join(base, name)
            out.names.add(name.lower())
            if is_link(full):
                continue
            try:
                st = os.lstat(full)
            except OSError:
                continue
            out.files += 1
            out.logical += st.st_size
            nlink = 1
            if st.st_size >= NLINK_PROBE_BYTES:
                nlink = getattr(st, 'st_nlink', 1) or 1
            if nlink <= 1:
                out.freed += st.st_size
                if st.st_size > HASH_FILE_CAP:
                    out.oversize.append(full)
                else:
                    out.hash_files.append((full, st.st_size))
    return out


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            digest.update(block)
    return digest.hexdigest()


# ----------------------------------------------------------------------------------------- the context

class Context:
    """What the guards read: the config, the root, the tracked set, the open run folders and the index."""

    def __init__(self, root, cfg, tracked, tracked_dirs, open_dirs, index, ledger_ok, git_runner=None):
        self.root = Path(root)
        self.cfg = cfg
        self.tracked = tracked
        self.tracked_dirs = tracked_dirs
        self.open_dirs = open_dirs
        self.index = index
        self.ledger_ok = ledger_ok
        self.git_runner = git_runner
        self.fresh = False
        self.ledger = None


def tracked_sets(root):
    out = git(root, 'ls-files', '-z', timeout=300)
    files, dirs = set(), set()
    for raw in out.split(b'\0'):
        if not raw:
            continue
        rel = norm(raw.decode('utf-8', 'replace'))
        files.add(rel)
        parts = rel.split('/')
        for n in range(1, len(parts)):
            dirs.add('/'.join(parts[:n]))
    return files, dirs


def read_ledger(path):
    """(rows, ok). A missing or unreadable ledger is not ok: it never reads as no open launch."""
    try:
        rows = []
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows, True
    except (OSError, ValueError):
        return [], False


def open_instance_names(rows):
    """Instance names of launches (or launch intents) with no termination line, matched by name or id."""
    ended_names = {r.get('instance_name') for r in rows if r.get('event') == 'termination'}
    ended_ids = {r.get('instance_id') for r in rows if r.get('event') == 'termination' and r.get('instance_id')}
    names = set()
    for r in rows:
        if r.get('event') not in ('launch', 'launch_intent'):
            continue
        name = r.get('instance_name')
        if not name or name in ended_names:
            continue
        if r.get('instance_id') and r.get('instance_id') in ended_ids:
            continue
        names.add(name)
    return names


def open_run_folders(rows, bundle_dirs):
    """The folders of open launches: a bundle's name ends in the first eight hex digits of its
    execution_manifest.json digest, so every folder whose digest matches an open name's tail is held."""
    keys = {n.rsplit('-', 1)[-1] for n in open_instance_names(rows)}
    held = set()
    if not keys:
        return held
    for folder in bundle_dirs:
        manifest = os.path.join(folder, 'execution_manifest.json')
        if os.path.isfile(manifest):
            try:
                if sha256_of(manifest)[:8] in keys:
                    held.add(norm(folder))
            except OSError:
                held.add(norm(folder))
    return held


def reload_open(ctx):
    """Read the ledger and the bundle manifests again (the last re-check before each deletion)."""
    rows, ok = read_ledger(ctx.ledger)
    ctx.ledger_ok = ok
    ctx.open_dirs = open_run_folders(rows, ctx.scan.bundle_dirs)


def make_context(root, cfg, ledger, scan=None):
    scan = scan or scan_tree(root, cfg)
    files, dirs = tracked_sets(root)
    rows, ok = read_ledger(ledger)
    index = build_index(root, scan.reference_files, cfg)
    ctx = Context(root, cfg, files, dirs, open_run_folders(rows, scan.bundle_dirs), index, ok)
    ctx.scan = scan
    ctx.ledger = ledger
    return ctx


# ----------------------------------------------------------------------------------------- guards
# Each returns a reason string (the path is refused) or None. `refusal` calls them by module name, so a
# proof can neutralise one and see the refusal go.

def _g_unmatched(ctx, cand, contents):
    p = Path(cand.path)
    try:
        rel = rel_of(ctx.root, p)
    except ValueError:
        return 'outside the root'
    kind = match_kind(ctx.cfg, rel, p.name, p.is_dir())
    if kind is None or kind['name'] != cand.kind['name']:
        return 'matched by no declared kind'
    return None


def _g_protected(ctx, cand, contents):
    rel = rel_of(ctx.root, cand.path)
    if rel in ('', '.') or rel.startswith('..'):
        return 'outside the root or the root itself'
    for prefix in ctx.cfg['protected_prefixes']:
        pre = prefix.lower().rstrip('/')
        if rel == pre or rel.startswith(pre + '/'):
            return 'under protected area %s' % prefix
    return None


def _g_private(ctx, cand, contents):
    names = {n.lower() for n in ctx.cfg['protected_names']}
    parts = rel_of(ctx.root, cand.path).split('/')
    if any(part in names for part in parts) or (names & contents.names):
        return 'a private folder'
    return None


def _g_fingerprint(ctx, cand, contents):
    globs = ctx.cfg['never_name_globs']
    parts = rel_of(ctx.root, cand.path).split('/')
    for name in parts + sorted(contents.names):
        if any(fnmatch.fnmatch(name.lower(), g.lower()) for g in globs):
            return 'a fingerprint (%s)' % name
    return None


def _g_tracked(ctx, cand, contents):
    rel = rel_of(ctx.root, cand.path)
    if rel in ctx.tracked or rel in ctx.tracked_dirs:
        return 'git tracks it or a file in it'
    if getattr(ctx, 'fresh', False):      # the last re-check asks git again, not the list taken at the start
        if git(ctx.root, 'ls-files', '-z', '--', rel).strip(b'\0'):
            return 'git tracks it or a file in it'
    return None


def _sealed_ancestor(ctx, path):
    markers = {m.lower() for m in ctx.cfg['sealed_markers']}
    top = ctx.root.resolve()
    folder = Path(path).resolve().parent
    while folder != top and top in folder.parents:
        try:
            names = {n.lower() for n in os.listdir(folder)}
        except OSError:
            return str(folder)
        if names & markers:
            return str(folder)
        folder = folder.parent
    return None


def _g_sealed(ctx, cand, contents):
    kind = cand.kind
    markers = {m.lower() for m in ctx.cfg['sealed_markers']}
    if not kind.get('allow_in_sealed'):
        holder = _sealed_ancestor(ctx, cand.path)
        if holder:
            return 'inside a sealed bundle folder'
    if not kind.get('allow_self_markers') and (markers & contents.names):
        return 'holds a seal or manifest file'
    return None


def _g_open_launch(ctx, cand, contents):
    if not ctx.ledger_ok:
        return 'the budget ledger is unreadable: open launches unknown'
    c = norm(cand.path)
    for held in ctx.open_dirs:
        if c == held or c.startswith(held + '/') or held.startswith(c + '/'):
            return 'the run folder of a launch with no termination line'
    return None


def _g_referenced(ctx, cand, contents):
    hit = indexed_reference(ctx.index, cand.path)
    if hit:
        return 'named in a seal, manifest, status, fingerprint, request or hand-off file'
    if contents.oversize:
        return 'holds a file too large to check against recorded digests'
    for path, _size in contents.hash_files:
        if sha256_of(path) in ctx.index.digests:
            return 'a file in it has a digest recorded in a seal, manifest or request'
    return None


def _g_requires(ctx, cand, contents):
    for need in cand.kind.get('requires', []):
        reason = REQUIRES[need](ctx, cand, contents)
        if reason:
            return reason
    age = cand.kind.get('min_age_days', 0)
    if age:
        newest = newest_mtime(cand.path)
        if newest is None or time.time() - newest < age * 86400:
            return 'younger than %s days' % age
    return None


def newest_mtime(path):
    try:
        newest = os.lstat(path).st_mtime
        if os.path.isdir(path):
            with os.scandir(path) as it:
                for e in it:
                    newest = max(newest, e.stat(follow_symlinks=False).st_mtime)
        return newest
    except OSError:
        return None


def _r_not_launched(ctx, cand, contents):
    launched = {m.lower() for m in ctx.cfg['launched_markers']}
    if launched & contents.names:
        return 'it was launched (a launch marker is in it)'
    return None


def _r_base_sibling_exists(ctx, cand, contents):
    name = Path(cand.path).name
    base = re.sub(r'\.killed_for_memory_\d+$', '', name)
    if base == name or not (Path(cand.path).parent / base).is_dir():
        return 'the unsuffixed folder that holds the restart does not exist'
    return None


def _r_collected_tar_digest_recorded(ctx, cand, contents):
    parent = Path(cand.path).parent
    tar = parent / 'collected_evidence.tar.gz'
    record = parent / 'collection_integrity.json'
    if not tar.is_file() or not record.is_file():
        return 'no collected_evidence.tar.gz with a collection_integrity.json beside it'
    try:
        recorded = json.loads(record.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return 'collection_integrity.json is unreadable'
    if str(recorded.get('sha256', '')).lower() != sha256_of(tar):
        return 'collected_evidence.tar.gz does not match its recorded digest'
    return None


REQUIRES = {'not_launched': _r_not_launched, 'base_sibling_exists': _r_base_sibling_exists,
            'collected_tar_digest_recorded': _r_collected_tar_digest_recorded}

_GUARDS = ('_g_unmatched', '_g_protected', '_g_private', '_g_fingerprint', '_g_tracked', '_g_sealed',
           '_g_open_launch', '_g_referenced', '_g_requires')


def refusal(ctx, cand, contents=None):
    """The first reason to keep this path, or None. A link, a missing path and a path that resolves
    elsewhere are refused first."""
    path = cand.path
    if not os.path.lexists(path):
        return 'it does not exist'
    if is_link(path):
        return 'a link or junction'
    if os.path.isdir(path) and _safe_delete().scan(path)[0]:
        return 'a link or junction inside it (DELETE-SAFE-A: remove the links alone first)'
    try:
        if Path(path).resolve() != Path(os.path.abspath(path)).resolve() or \
                ctx.root.resolve() not in Path(path).resolve().parents:
            return 'it resolves outside its own place under the root'
    except OSError:
        return 'it cannot be resolved'
    contents = contents or contents_of(path)
    module = sys.modules[__name__]
    for name in _GUARDS:
        reason = getattr(module, name)(ctx, cand, contents)
        if reason:
            return reason
    return None


# ----------------------------------------------------------------------------------------- run

def free_bytes(path):
    return shutil.disk_usage(str(path)).free


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _on_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def log_line(when, rel, row):
    """The one record of a deletion: time from the clock, path, bytes, kind, reason, how to regenerate it."""
    return {'time_utc': when, 'path': rel, 'bytes': row['bytes'], 'kind': row['kind'], 'reason': row['reason'],
            'regenerate': row['regenerate']}


def _safe_delete():
    """tools/loop/safe_delete.py, the one deletion path (DELETE-SAFE-A, standing order 96)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('safe_delete', str(Path(__file__).with_name('safe_delete.py')))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def delete_exact(path):
    """Through safe_delete on the exact path: never a shell, never a glob, never through a link."""
    sd = _safe_delete()
    if is_link(path):
        raise SweepError('refused: %s is a link' % path)
    problems, entries = sd.check(path, allow_under_protected=True)
    if problems:
        raise SweepError('refused by safe_delete: %s' % '; '.join(problems))
    sd.delete(entries)


def worktree_report(root, cfg, loop_ref=None):
    """Lane worktrees under the root whose branch is merged into the loop ref and whose tree is clean.
    REPORT ONLY: nothing here deletes."""
    ref = loop_ref or cfg.get('loop_ref', 'HEAD')
    rows = []
    try:
        listing = git(root, 'worktree', 'list', '--porcelain').decode('utf-8', 'replace')
    except SweepError:
        return rows
    entries, current = [], {}
    for line in listing.splitlines() + ['']:
        if not line.strip():
            if current:
                entries.append(current)
            current = {}
        elif ' ' in line:
            key, value = line.split(' ', 1)
            current[key] = value
        else:
            current[line] = True
    base = norm(Path(root) / '.claude' / 'worktrees')
    for entry in entries:
        path = entry.get('worktree')
        branch = entry.get('branch', '').replace('refs/heads/', '')
        if not path or not norm(path).startswith(base + '/'):
            continue
        row = {'path': path, 'branch': branch or None, 'merged': None, 'clean': None, 'bytes': None}
        if branch:
            ok = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', branch, ref],
                                capture_output=True, stdin=subprocess.DEVNULL, creationflags=no_window()).returncode
            row['merged'] = ok == 0
            try:
                row['clean'] = git(path, 'status', '--porcelain').strip() == b''
            except (SweepError, OSError):
                row['clean'] = None
        try:
            row['bytes'] = contents_of(path).freed
        except OSError:
            pass
        row['superseded'] = bool(row['merged'] and row['clean'])
        rows.append(row)
    return rows


def post_check(index):
    """Every indexed path that existed when the index was built must still exist."""
    return sorted(p for p in index.existing if not os.path.lexists(p))


def take_lock(private):
    lock = Path(private) / LOCK_NAME
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if time.time() - lock.stat().st_mtime < LOCK_STALE_SECONDS:
            raise SweepError('another sweep holds %s' % lock)
        lock.unlink()
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return lock


def sweep(root, cfg, ledger, log_path, apply, scan=None, ctx=None, clock=now_utc, free=free_bytes, top=15):
    """Plan every candidate, and with `apply` delete the ones that survive their last re-check. Returns a
    result dict; deletes nothing without `apply`."""
    before = free(root)
    ctx = ctx or make_context(root, cfg, ledger, scan)
    scan = ctx.scan
    plan, kept = [], []
    for cand in scan.candidates:
        contents = contents_of(cand.path)
        reason = refusal(ctx, cand, contents)
        row = {'path': cand.path, 'kind': cand.kind['name'], 'bytes': contents.freed, 'logical': contents.logical,
               'files': contents.files, 'reason': cand.kind['reason'], 'regenerate': cand.kind['regenerate']}
        (kept if reason else plan).append(dict(row, refused=reason) if reason else row)
    result = {'free_before': before, 'plan': plan, 'refused': kept, 'deleted': [], 'failed': [],
              'post_check_missing': [], 'index_errors': list(ctx.index.errors) + list(scan.errors),
              'index_paths': len(ctx.index.paths), 'index_digests': len(ctx.index.digests),
              'worktrees': worktree_report(root, cfg)}
    if not apply:
        result['free_after'] = before
        return result
    if ctx.index.errors or scan.errors:
        raise SweepError('the reference index is incomplete (%d errors); nothing deleted'
                         % (len(ctx.index.errors) + len(scan.errors)))
    if not ctx.ledger_ok:
        raise SweepError('the budget ledger is unreadable; nothing deleted')
    ctx.fresh = True
    by_path = {c.path: c for c in scan.candidates}
    for row in plan:
        cand = by_path[row['path']]
        reload_open(ctx)
        again = refusal(ctx, cand)          # the last re-check, just before the deletion
        if again:
            result['failed'].append(dict(row, refused=again))
            continue
        try:
            delete_exact(cand.path)
        except OSError as exc:
            result['failed'].append(dict(row, error=type(exc).__name__))
            continue
        line = log_line(clock(), rel_of(root, cand.path), row)
        with open(log_path, 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(line) + '\n')
        result['deleted'].append(row)
    result['post_check_missing'] = post_check(ctx.index)
    result['free_after'] = free(root)
    return result


def summary_line(result, apply):
    items = result['deleted'] if apply else result['plan']
    freed = sum(r['bytes'] for r in items)
    return ('disk_sweep %s: %s %.2f GiB in %d items; free disk %.2f GiB before, %.2f GiB %s'
            % ('apply' if apply else 'dry-run', 'freed' if apply else 'would free', freed / GIB, len(items),
               result['free_before'] / GIB,
               (result['free_after'] if apply else result['free_before'] + freed) / GIB,
               'after' if apply else 'if applied'))


def inventory(root, depth_roots=('external', 'output'), top=12):
    """Sizes of the largest folders under each root, names and sizes only (opens no file)."""
    rows = []
    for name in depth_roots:
        base = Path(root) / name
        if not base.is_dir():
            continue
        sizes = []
        with os.scandir(base) as it:
            for e in it:
                if e.is_dir(follow_symlinks=False) and not is_link(e.path):
                    sizes.append((contents_of(e.path).freed, name + '/' + e.name))
        rows.extend(sorted(sizes, reverse=True)[:top])
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--root', help='the checkout to sweep (--apply needs the main checkout)')
    parser.add_argument('--config', help='the declared kinds (default config/disk_sweep.json)')
    parser.add_argument('--ledger', help='budget ledger (default: the main checkout private folder)')
    parser.add_argument('--log', help='sweep log (default: the main checkout private folder)')
    parser.add_argument('--if-free-below-gib', type=float, default=None,
                        help='do nothing unless free disk is under this many GiB (the load watcher and seal gate call)')
    parser.add_argument('--top', type=int, default=12)
    parser.add_argument('--inventory', action='store_true', help='also list the largest kept folders under external/ and output/')
    args = parser.parse_args(argv)
    try:
        main_checkout = main_root()
        root = Path(args.root).resolve() if args.root else main_checkout
        if args.apply and root != main_checkout.resolve():
            raise SweepError('--apply needs the main checkout (%s), not %s' % (main_checkout, root))
        cfg = load_config(args.config)
        private = main_checkout / 'docs' / 'loop' / 'private'
        ledger = Path(args.ledger) if args.ledger else private / 'budget_ledger.jsonl'
        log_path = Path(args.log) if args.log else private / LOG_NAME
        free = free_bytes(root)
        if args.if_free_below_gib is not None and free / GIB >= args.if_free_below_gib:
            print('disk_sweep: free disk %.2f GiB is not under %.1f GiB; nothing to do' % (free / GIB, args.if_free_below_gib))
            return 0
        lock = take_lock(private) if args.apply else None
        try:
            result = sweep(root, cfg, ledger, log_path, args.apply)
        finally:
            if lock:
                lock.unlink()
    except SweepError as exc:
        print('disk_sweep refused: %s' % exc)
        return 2
    by_kind = {}
    for row in result['plan'] if not args.apply else result['deleted']:
        d = by_kind.setdefault(row['kind'], [0, 0])
        d[0] += 1
        d[1] += row['bytes']
    for name, (n, b) in sorted(by_kind.items()):
        print('  kind %-34s %5d items %9.3f GiB' % (name, n, b / GIB))
    refused = {}
    for row in result['refused'] + result['failed']:
        d = refused.setdefault(row['refused'], [0, 0])
        d[0] += 1
        d[1] += row['bytes']
    for reason, (n, b) in sorted(refused.items(), key=lambda kv: -kv[1][1]):
        print('  refused %5d items %9.3f GiB: %s' % (n, b / GIB, reason))
    big = sorted(result['refused'] + result['failed'], key=lambda r: -r['bytes'])[:args.top]
    for row in big:
        if row['bytes'] >= (50 << 20):
            print('  refused-large %9.3f GiB %s [%s]: %s' % (row['bytes'] / GIB, rel_of(root, row['path']), row['kind'],
                                                           row['refused']))
    for row in result['worktrees']:
        if row['superseded']:
            print('  worktree (report only) %s branch %s merged, clean, %.2f GiB' % (
                rel_of(root, row['path']), row['branch'], (row['bytes'] or 0) / GIB))
    print('  index: %d paths, %d digests, %d errors' % (result['index_paths'], result['index_digests'],
                                                       len(result['index_errors'])))
    if args.inventory:
        for size, name in inventory(root, top=args.top):
            print('  kept (matched by no kind) %9.2f GiB %s' % (size / GIB, name))
    print(summary_line(result, args.apply))
    if result['post_check_missing']:
        print('POST-CHECK FAILED: %d indexed paths no longer exist, first: %s' % (
            len(result['post_check_missing']), result['post_check_missing'][0]))
        return 3
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
