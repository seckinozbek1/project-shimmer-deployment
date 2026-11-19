"""Proofs that no backup tool reads a file under the Google Drive folder (D-763, 19 November 2026; checks 575 to
578). Google Drive for desktop downloads a cloud-only file the moment its content is read; the read-backs of
drive_archive and drive_paced, the member listing of backup_coverage and the extraction of restore_drill pulled
whole archives (38.8 GiB) into its cache on C:.

Fixtures only: a temporary main checkout and a temporary folder standing for Drive (backup_coverage_checks'
Fixture). Every open of a file is seen through a Python audit hook ('open' events, which also catch tarfile's
and zipfile's own opens); a read open of any path under the fake Drive folder is a fault. A cloud-only file is
faked by a monkeypatched backup_coverage.drive_stat that adds FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS. Each proof
is run as built (passes), neutralised (must fail), restored (passes). Nothing real is read or written: the
Drive app's metadata database is replaced by a stub and the mechanism trace by a list.

    py -3.12 -X utf8 tools/loop/drive_no_download_checks.py             # all four
    py -3.12 -X utf8 tools/loop/drive_no_download_checks.py drill       # archive, paced, coverage or drill
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backup_coverage as cov  # noqa: E402
import backup_coverage_checks as bcc  # noqa: E402
import drive_archive as da  # noqa: E402
import drive_paced as dp  # noqa: E402
import restore_drill as rd  # noqa: E402

WATCH = {'root': None, 'reads': []}


def _hook(event, args):
    root = WATCH['root']
    if event != 'open' or root is None or not args:
        return
    target = args[0]
    if isinstance(target, int):
        return
    try:
        p = os.path.normcase(os.path.abspath(os.fsdecode(target)))
    except (TypeError, ValueError):
        return
    if not (p == root or p.startswith(root + os.sep)):
        return
    mode = args[1] if len(args) > 1 else None
    flags = args[2] if len(args) > 2 else 0
    if isinstance(mode, str):
        reads = 'r' in mode or '+' in mode
    else:
        reads = (flags or 0) & 3 != os.O_WRONLY
    if reads:
        WATCH['reads'].append(p)


sys.addaudithook(_hook)


class Watching:
    """Records every read open under `root` while active."""

    def __init__(self, root):
        self.root = os.path.normcase(os.path.abspath(str(root)))

    def __enter__(self):
        WATCH['root'], WATCH['reads'] = self.root, []
        return WATCH['reads']

    def __exit__(self, *exc):
        WATCH['root'] = None
        return False


def sha256_md5(path):
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest(), hashlib.md5(data).hexdigest()


def cloud_stat(drive, size_delta=0):
    """A drive_stat under which every file under `drive` is a cloud-only placeholder (and, with size_delta,
    reports a different size)."""
    real = os.stat
    root = os.path.normcase(os.path.abspath(str(drive)))

    class St:
        def __init__(self, st):
            self._st = st
            self.st_size = st.st_size + size_delta
            self.st_mtime = st.st_mtime
            self.st_file_attributes = (getattr(st, 'st_file_attributes', 0) or 0) | cov.FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS

    def fake(path):
        st = real(path, follow_symlinks=False)
        p = os.path.normcase(os.path.abspath(str(path)))
        return St(st) if p.startswith(root + os.sep) else st
    return fake


def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    return lambda: setattr(owner, name, old)


# --- 575 drive_archive -----------------------------------------------------------------------------------

@bcc.with_fixture
def proof_archive_never_reads_drive(fx):
    with Watching(fx.paths['drive']) as reads:
        line = bcc.archive_now(fx, 'external/s05/GATE')
    assert not reads, 'drive_archive read %d file(s) under Drive' % len(reads)
    assert line['verified'] is True and 'os.stat' in line['verified_how'], line
    assert (line['sha256'], line['md5']) == sha256_md5(line['file']), 'the stream hashes differ from the file'
    local = Path(line['manifest_local'])
    assert local.is_file() and not cov.under(local, fx.paths['drive'])
    assert hashlib.sha256(local.read_bytes()).hexdigest() == line['manifest_sha256']
    # a Drive copy of the wrong size is not verified, still without a read
    restore = patched(cov, 'drive_stat', cloud_stat(fx.paths['drive'], size_delta=1))
    try:
        with Watching(fx.paths['drive']) as reads:
            bad = bcc.archive_now(fx, 'external/s05/P1')
    finally:
        restore()
    assert bad['verified'] is False and not reads, (bad['verified'], len(reads))


def reread_verify(target, written):
    """The regression: verify by reading the Drive file back."""
    return cov.drive_stat(target).st_size == written and bool(cov.sha256_file(target))


# --- 576 drive_paced ---------------------------------------------------------------------------------------

@bcc.with_fixture
def proof_paced_confirms_without_reading(fx):
    line = bcc.archive_now(fx, 'external/s05/GATE')
    target = Path(line['file'])
    size = target.stat().st_size
    traced = []
    restores = [patched(dp, 'cloud_lookup', lambda p: [('cloud-id-1', size, [line['md5']], p.parent.name)]),
                patched(dp.mc, 'read_trace', lambda *a, **k: []),
                patched(dp.mc, 'trace', lambda *a, **k: traced.append((a, k))),
                patched(cov, 'drive_stat', cloud_stat(fx.paths['drive']))]
    try:
        with Watching(fx.paths['drive']) as reads:
            got = dp.confirm(target, line['md5'])
            legacy = dp.confirm(target, None)
            counts = dp.confirm_pass(fx.paths)
    finally:
        for r in reversed(restores):
            r()
    assert not reads, 'drive_paced read %d file(s) under Drive' % len(reads)
    assert got[0] == 'cloud_confirmed' and got[1]['md5'] == line['md5'], got
    assert legacy[0] == 'cloud_present' and 'no MD5 recorded' in legacy[1]['note'], legacy
    assert counts == {'cloud_confirmed': 1}, counts      # the md5 taken from the log line
    assert traced and traced[0][0][1] == 'cloud_confirmed'


def confirm_hashing_drive(path, md5=None):
    """The regression: an archive with no recorded MD5 is hashed from the Drive file."""
    if md5 is None:
        md5 = hashlib.md5(Path(path).read_bytes()).hexdigest()
    return REAL_CONFIRM(path, md5)


REAL_CONFIRM = dp.confirm


# --- 577 backup_coverage -----------------------------------------------------------------------------------

@bcc.with_fixture
def proof_coverage_reads_log_and_stat_only(fx):
    line = bcc.archive_now(fx, 'external/s05/GATE')
    # a legacy archive with no manifest, small enough for the old member listing
    legacy = fx.paths['drive'] / 'external_20261116' / 's05__P1.tar.gz'
    legacy.parent.mkdir()
    body = b'a legacy archive the old member listing would have streamed'
    legacy.write_bytes(body)
    later = dt.datetime.now().astimezone() + dt.timedelta(seconds=60)
    fx.log(tool='drive_external', part='s05__P1', file=str(legacy), bytes=legacy.stat().st_size, verified=True,
           sha256=hashlib.sha256(body).hexdigest(), time=later.isoformat(timespec='seconds'))
    restore = patched(cov, 'drive_stat', cloud_stat(fx.paths['drive']))
    try:
        with Watching(fx.paths['drive']) as reads:
            report = fx.report()
            archives = cov.drive_archives(cov.read_log(fx.paths['log']), fx.paths['drive'], fx.main)
        assert not reads, 'backup_coverage read %d file(s) under Drive' % len(reads)
        assert bcc.row(report, 'external/s05/GATE')['status'] == 'COVERED'
        assert bcc.row(report, 'external/s05/P1')['status'] == 'COVERED'
        assert sorted(a.how for a in archives) == ['manifest', 'time'], [a.how for a in archives]
        # the local manifest copy gone: judged by time, the Drive manifest still never opened
        os.replace(line['manifest_local'], line['manifest_local'] + '.moved')
        with Watching(fx.paths['drive']) as reads:
            archives = cov.drive_archives(cov.read_log(fx.paths['log']), fx.paths['drive'], fx.main)
        assert not reads and sorted(a.how for a in archives) == ['time', 'time'], [a.how for a in archives]
    finally:
        restore()


def manifest_from_drive(line, drive):
    """The regression: the manifest read from beside the archive on Drive."""
    m = line.get('manifest')
    return Path(m) if m and Path(m).is_file() else None


# --- 578 restore_drill -------------------------------------------------------------------------------------

@bcc.with_fixture
def proof_drill_refuses_cloud_only(fx):
    scratch = bcc.drill_setup(fx)
    cfg = fx.base / 'drive_no_download.json'
    cfg.write_text(json.dumps({'restore_drill': {'local_max_bytes': 1 << 20, 'cloud_only_max_bytes': 0}}),
                   encoding='utf-8')
    restores = [patched(cov, 'NO_DOWNLOAD_CONFIG', cfg), patched(cov, 'drive_stat', cloud_stat(fx.paths['drive']))]
    try:
        with Watching(fx.paths['drive']) as reads:
            s = rd.drill(fx.paths, scratch, kinds=['drive'], part='external/s05/GATE', settle=0)
        assert not reads, 'restore_drill read %d file(s) under Drive' % len(reads)
        k = s['kinds'][0]
        assert s['result'] == 'FAIL' and 'cloud-only' in k['reason'], k
        # a small cloud-only archive within the declared cloud_only_max_bytes is read and restored
        cfg.write_text(json.dumps({'restore_drill': {'local_max_bytes': 1 << 20, 'cloud_only_max_bytes': 1 << 20}}),
                       encoding='utf-8')
        s = rd.drill(fx.paths, fx.base / 'scratch2', kinds=['drive'], part='external/s05/GATE', settle=0)
        assert s['result'] == 'PASS', s
    finally:
        for r in reversed(restores):
            r()
    # an archive already local (no recall attribute) is restored; one above local_max_bytes is refused unread
    s = rd.drill(fx.paths, fx.base / 'scratch3', kinds=['drive'], part='external/s05/GATE', settle=0)
    assert s['result'] == 'PASS', s
    cfg.write_text(json.dumps({'restore_drill': {'local_max_bytes': 1, 'cloud_only_max_bytes': 0}}), encoding='utf-8')
    restore = patched(cov, 'NO_DOWNLOAD_CONFIG', cfg)
    try:
        with Watching(fx.paths['drive']) as reads:
            s = rd.drill(fx.paths, fx.base / 'scratch4', kinds=['drive'], part='external/s05/GATE', settle=0)
    finally:
        restore()
    assert s['result'] == 'FAIL' and 'local_max_bytes' in s['kinds'][0]['reason'] and not reads, s


GROUPS = {
    'archive': (575, proof_archive_never_reads_drive, lambda: patched(da, 'verify_upload', reread_verify)),
    'paced': (576, proof_paced_confirms_without_reading, lambda: patched(dp, 'confirm', confirm_hashing_drive)),
    'coverage': (577, proof_coverage_reads_log_and_stat_only, lambda: patched(cov, 'local_manifest',
                                                                              manifest_from_drive)),
    'drill': (578, proof_drill_refuses_cloud_only, lambda: patched(rd, 'read_refusal', lambda path, config=None: '')),
}

DETAIL = {
    'archive': 'drive_archive opens no file under the Drive folder: SHA-256 and MD5 from the write stream equal '
               'the file\'s, the Drive copy verified by os.stat size (a wrong size is not verified), the manifest '
               'hashed in memory and kept as a local copy outside Drive',
    'paced': 'drive_paced confirms against the Drive app metadata (stubbed) with the MD5 recorded at write time, '
             'an archive with no recorded MD5 compared by size and cloud id only, never hashed from Drive',
    'coverage': 'backup_coverage reads the log, the local manifest copy and os.stat only: a cloud-only archive '
                'with its manifest copy covered by manifest, a legacy archive and one without a local copy '
                'judged by time, no Drive manifest and no member listing opened',
    'drill': 'restore_drill refuses a cloud-only archive (RECALL_ON_DATA_ACCESS faked through drive_stat) above '
             'the declared cloud_only_max_bytes and a local one above local_max_bytes before opening it, and '
             'restores a local archive or a cloud-only one within the declared limit',
}


def run_group(name):
    number, proof, neutralise = GROUPS[name]
    try:
        proof()
        restore = neutralise()
        try:
            proof()
            held = False
        except Exception:
            held = True
        finally:
            restore()
        if not held:
            return 'FAIL', proof.__name__ + ' still passes when neutralised'
        proof()
    except Exception as exc:
        return 'FAIL', '%s: %s %s' % (proof.__name__, type(exc).__name__, str(exc)[:200])
    return 'PASS', 'check %d, one proof neutralised, failed, restored and passed, fixtures only: %s' % (
        number, DETAIL[name])


if __name__ == '__main__':
    names = sys.argv[1:] or list(GROUPS)
    worst = 0
    for n in names:
        status, detail = run_group(n)
        print(n, status, detail)
        worst = worst or (status != 'PASS')
    raise SystemExit(1 if worst else 0)
