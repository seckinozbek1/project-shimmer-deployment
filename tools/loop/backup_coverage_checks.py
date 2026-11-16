"""Proofs for backup_coverage.py, drive_archive.py and restore_drill.py (D-702 item 4, D-704 item 3; the
drive-only roles roots, operator 16 November 2026 20:41: groups roles and roles_archive, checks 470 and 471), on
fixtures only: a temporary main checkout, a fake bare repository, a fake Drive folder and a fake log. No real
data is read or written. Each proof is run as built (passes), neutralised (must fail), restored (passes).

    py -3.12 -X utf8 tools/loop/backup_coverage_checks.py            # all five groups
    py -3.12 -X utf8 tools/loop/backup_coverage_checks.py coverage   # one group: coverage, archive, drill,
                                                                     # roles or roles_archive
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backup_coverage as cov  # noqa: E402
import drive_archive as da  # noqa: E402
import restore_drill as rd  # noqa: E402

GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME='fixture', GIT_AUTHOR_EMAIL='fixture@localhost',
               GIT_COMMITTER_NAME='fixture', GIT_COMMITTER_EMAIL='fixture@localhost')
FAKE_KEY = 'sk-' + 'ant-' + 'A' * 30   # a key body for the scan; not a key


def git(repo, *args, inp=None, env=None):
    done = subprocess.run(['git', '--git-dir', str(repo), *args], input=inp, capture_output=True,
                          env=env or GIT_ENV, timeout=120, creationflags=cov.no_window())
    assert done.returncode == 0, done.stderr.decode('utf-8', 'replace')[:200]
    return done.stdout.decode('utf-8', 'replace').strip()


class Fixture:
    """A temporary main checkout with the three roots, a bare repository, a Drive folder and a log."""

    def __init__(self, base):
        self.base = Path(base)
        self.main = self.base / 'main'
        self.paths = {'main': self.main, 'repo': self.base / 'repo', 'drive': self.base / 'drive',
                      'log': self.base / 'backup_log.jsonl'}
        self.paths['drive'].mkdir()
        self.links = []
        self.write('docs/loop/private/notes/a.md', 'note a\n')
        self.write('docs/loop/private/notes/b.md', 'note b\n')
        self.write('docs/loop/private/LOOP_STATE.md', 'state\n')
        self.write('docs/loop/private/.env', 'NAME=value\n')
        self.write('output/runs/r1.json', '{"r": 1}\n')
        self.write('output/cloud_wheels/w.whl', 'wheel')
        self.write('external/s05/P1/x.bin', 'x' * 1000)
        self.write('external/s05/GATE/ids.json', '[1, 2]\n')
        self.write('external/other/y.txt', 'y\n')

    def write(self, rel, text):
        p = self.main.joinpath(*rel.split('/'))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8', newline='\n')
        return p

    def snapshot(self, logicals):
        """A records/private commit holding these logical paths, as backup_records builds it."""
        repo = self.paths['repo']
        if not repo.exists():
            subprocess.run(['git', 'init', '--bare', '-q', str(repo)], check=True, capture_output=True,
                           creationflags=cov.no_window())
        files = cov.walk(self.main)[0]
        lines = []
        for lg in logicals:
            sha = git(repo, 'hash-object', '-w', '--no-filters', files[lg][0])
            lines.append('100644 %s\t%s\n' % (sha, lg))
        env = dict(GIT_ENV, GIT_INDEX_FILE=str(self.base / 'index'))
        if (self.base / 'index').exists():
            os.remove(self.base / 'index')
        git(repo, 'update-index', '--add', '--index-info', inp=''.join(lines).encode(), env=env)
        tree = git(repo, 'write-tree', env=env)
        commit = git(repo, 'commit-tree', tree, '-m', 'snapshot')
        git(repo, 'update-ref', 'refs/heads/records/private', commit)
        return commit

    def log(self, **line):
        with open(self.paths['log'], 'a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(line) + '\n')

    def junction(self, rel, target):
        """A junction (Windows) or symlink at rel pointing at target; removed as a link only by close()."""
        link = self.main.joinpath(*rel.split('/'))
        link.parent.mkdir(parents=True, exist_ok=True)
        Path(target).mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(str(target), str(link), target_is_directory=True)
        self.links.append(link)
        return link

    def close(self):
        for link in self.links:      # the link alone, never its target (DELETE-SAFE-A)
            if os.name == 'nt':
                os.rmdir(link)
            else:
                os.unlink(link)
        self.links = []

    def report(self, **kw):
        return cov.coverage(self.paths, secret_check=lambda u: set(), **kw)


def row(report, part):
    return {r['part']: r for r in report['parts']}[part]


def with_fixture(fn):
    def run():
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            try:
                fn(fx)
            finally:
                fx.close()
    run.__name__ = fn.__name__
    return run


def archive_now(fx, part, when=None):
    return da.archive_part(fx.paths, part, now=when, patterns=da.strict_patterns(), free=lambda p: 100 * 2 ** 30)


# --- coverage -------------------------------------------------------------------------------------------

@with_fixture
def proof_git_blob_ids_decide(fx):
    fx.snapshot(['private/notes/a.md', 'private/notes/b.md', 'private/LOOP_STATE.md', 'output/runs/r1.json'])
    fx.write('docs/loop/private/notes/a.md', 'note a, changed after the snapshot\n')
    r = fx.report()
    notes = row(r, 'private/notes')
    assert notes['status'] == 'STALE', notes['status']
    assert [g[0] for g in notes['gap']] == ['private/notes/a.md'], notes['gap']
    assert row(r, 'private/(files)')['status'] == 'COVERED'
    assert row(r, 'output/runs')['status'] == 'COVERED'
    assert row(r, 'output/cloud_wheels')['status'] == 'EXCLUDED'
    assert row(r, 'external/s05/P1')['status'] == 'NOT COVERED'


@with_fixture
def proof_drive_needs_verified_and_size(fx):
    good = archive_now(fx, 'external/s05/GATE')
    assert good['verified'] is True
    # a second archive of P1 whose logged size is wrong, and a third marked not verified
    bad = archive_now(fx, 'external/s05/P1', when=dt.datetime.now().astimezone() + dt.timedelta(seconds=1))
    lines = [json.loads(x) for x in fx.paths['log'].read_text(encoding='utf-8').splitlines()]
    lines[1]['bytes'] += 1
    lines.append(dict(lines[1], bytes=lines[1]['bytes'] - 1, verified=False))
    fx.paths['log'].write_text(''.join(json.dumps(x) + '\n' for x in lines), encoding='utf-8')
    assert bad['file']
    r = fx.report()
    assert row(r, 'external/s05/GATE')['status'] == 'COVERED'
    assert row(r, 'external/s05/P1')['status'] == 'NOT COVERED', row(r, 'external/s05/P1')['status']


@with_fixture
def proof_links_recorded_never_followed(fx):
    fx.junction('docs/loop/private/notes/jlink', fx.base / 'outside')
    (fx.base / 'outside' / 'secret_target.txt').write_text('outside\n', encoding='utf-8')
    r = fx.report()
    assert 'private/notes/jlink' in r['links'], r['links']
    assert row(r, 'private/notes')['links'] == ['private/notes/jlink']
    walked = [lg for p in r['parts'] for lg, *_ in p['gap']]
    assert not any('jlink/' in lg for lg in walked), walked


@with_fixture
def proof_exit_on_irreplaceable_gap(fx):
    argv = ['--main', str(fx.main), '--repo', str(fx.paths['repo']), '--drive', str(fx.paths['drive']),
            '--log', str(fx.paths['log'])]
    fx.snapshot(['private/notes/a.md', 'private/notes/b.md', 'private/LOOP_STATE.md'])
    for part in ('external/s05/GATE', 'external/s05/P1'):
        archive_now(fx, part)
    # only output/runs and external/other are not covered: not irreplaceable, exit 0
    assert quiet(cov.main, argv) == 0
    fx.write('external/s05/P1/new_evidence.json', '{}\n')
    r = fx.report()
    assert [x['part'] for x in cov.faults(r)] == ['external/s05/P1'], cov.faults(r)
    assert quiet(cov.main, argv) == 1


@with_fixture
def proof_credentials_and_held_back_excluded(fx):
    fx.write('output/runs/held.json', '{"held": true}\n')
    fx.log(tool='backup_records', time='2026-11-16T10:00:00+03:00', held_back_for_review=['output/runs/held.json'])
    r = fx.report()
    priv = row(r, 'private/(files)')
    assert 'private/.env' in priv['excluded'], priv['excluded']
    assert 'private/.env' not in [g[0] for g in priv['gap']]
    assert 'output/runs/held.json' in row(r, 'output/runs')['excluded']


@with_fixture
def proof_time_only_legacy_archive(fx):
    target = fx.paths['drive'] / 'external_20261116' / 's05__P1.tar.gz'
    target.parent.mkdir()
    target.write_bytes(b'not read: judged by time')
    later = dt.datetime.now().astimezone() + dt.timedelta(seconds=60)
    fx.log(tool='drive_external', part='s05__P1', file=str(target), bytes=target.stat().st_size, verified=True,
           time=later.isoformat(timespec='seconds'))
    assert row(fx.report(list_max=0), 'external/s05/P1')['status'] == 'COVERED'
    p = fx.main / 'external' / 's05' / 'P1' / 'x.bin'
    future = time.time() + 3600
    os.utime(p, (future, future))
    assert row(fx.report(list_max=0), 'external/s05/P1')['status'] == 'STALE'


# --- drive archive --------------------------------------------------------------------------------------

@with_fixture
def proof_archive_hashes_twice_and_logs(fx):
    line = archive_now(fx, 'external/s05/GATE')
    assert line['verified'] is True and line['tool'] == 'drive_archive'
    assert cov.sha256_file(line['file']) == line['sha256']
    manifest = json.loads(Path(line['manifest']).read_text(encoding='utf-8'))
    live = fx.main / 'external' / 's05' / 'GATE' / 'ids.json'
    assert manifest['entries'] == [dict(manifest['entries'][0], sha256=cov.sha256_file(live))]
    assert row(fx.report(), 'external/s05/GATE')['status'] == 'COVERED'


@with_fixture
def proof_archive_leaves_out_links_and_keys(fx):
    fx.write('external/other/.env', 'NAME=value\n')
    fx.write('external/other/note.txt', 'a line with ' + FAKE_KEY + '\n')
    fx.junction('external/other/jlink', fx.base / 'outside2')
    line = archive_now(fx, 'external/other')
    import tarfile
    with tarfile.open(line['file'], 'r:gz') as t:
        names = t.getnames()
    assert names == ['external/other/y.txt'], names
    assert sorted(line['left_out']) == ['external/other/.env', 'external/other/note.txt'], line['left_out']
    assert line['links'] == ['external/other/jlink']


@with_fixture
def proof_keep_report_deletes_nothing(fx):
    start = dt.datetime.now().astimezone()
    files = [archive_now(fx, 'external/s05/GATE', when=start + dt.timedelta(seconds=i))['file'] for i in range(4)]
    real_remove, real_unlink = os.remove, os.unlink

    def refuse(*a, **k):
        raise AssertionError('the keep report tried to delete')
    os.remove = os.unlink = refuse
    try:
        report = da.keep_report(fx.paths, 2)
    finally:
        os.remove, os.unlink = real_remove, real_unlink
    assert report == [('external/s05/GATE', [files[1], files[0]])], report
    assert all(Path(f).exists() for f in files)


@with_fixture
def proof_drive_floor_stops_before_writing(fx):
    line = da.archive_part(fx.paths, 'external/s05/P1', patterns=[], free=lambda p: 3 * 2 ** 30)
    assert line.get('stopped'), line
    assert not list(fx.paths['drive'].rglob('*.tar.gz*'))


# --- restore drill --------------------------------------------------------------------------------------

def drill_setup(fx):
    fx.snapshot(['private/notes/a.md', 'private/notes/b.md', 'private/LOOP_STATE.md'])
    archive_now(fx, 'external/s05/GATE')
    return fx.base / 'scratch'


@with_fixture
def proof_drill_restores_and_matches(fx):
    scratch = drill_setup(fx)
    before = {lg: cov.sha256_file(i[0]) for lg, i in cov.walk(fx.main)[0].items()}
    s = rd.drill(fx.paths, scratch, settle=0)
    assert s['result'] == 'PASS', s
    # private/(files) holds the excluded .env, so the smallest fully held git part is private/notes
    assert {k['kind']: k['part'] for k in s['kinds']} == {'git': 'private/notes', 'drive': 'external/s05/GATE'}, s
    assert Path(s['folder']).is_dir() and Path(s['folder']).parent == scratch
    assert (Path(s['folder']) / 'git' / 'private' / 'notes' / 'a.md').is_file()
    assert {lg: cov.sha256_file(i[0]) for lg, i in cov.walk(fx.main)[0].items()} == before


@with_fixture
def proof_drill_detects_a_difference(fx):
    scratch = drill_setup(fx)
    fx.write('docs/loop/private/notes/a.md', 'changed after the snapshot, same size?\n')
    s = rd.drill(fx.paths, scratch, kinds=['git'], part='private/notes', settle=0)
    assert s['result'] == 'FAIL', s
    assert ['private/notes/a.md', 'hash differs'] in [list(m) for m in s['kinds'][0]['mismatches']], s


@with_fixture
def proof_drill_refuses_inside_main(fx):
    drill_setup(fx)
    try:
        rd.drill(fx.paths, fx.main / 'scratch', settle=0)
    except rd.DrillRefused:
        assert not (fx.main / 'scratch').exists()
        return
    raise AssertionError('a drill folder inside the main checkout was accepted')


# --- drive-only roots (operator, 16 November 2026 20:41) -------------------------------------------------

SENTINEL = 'zq_inner_name'          # inner file names carry it; no printed or logged line may


class RolesFixture(Fixture):
    """The checkout fixture plus a roles root beside it, read through the shipped config/backup_extra_roots.json
    with SHIMMER_ROLES_ROOT pointing at it."""

    def __init__(self, base):
        super().__init__(base)
        self.roles = self.base / 'roles_root'
        for rel, text in (('_xfer/ex1/%s_a.txt' % SENTINEL, 'exchange a\n'), ('_xfer/ex2/%s_b.txt' % SENTINEL, 'b\n'),
                          ('_xfer/B/%s_hidden.txt' % SENTINEL, 'role B\n'),
                          ('N/set1/%s_t1.txt' % SENTINEL, 'negotiation text\n'),
                          ('N/set1/answer_key.json', '{"k": 1}\n'), ('N/%s_loose.txt' % SENTINEL, 'loose\n'),
                          ('B/x.txt', 'role B\n'), ('_seckin/y.txt', 'operator\n')):
            p = self.roles.joinpath(*rel.split('/'))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding='utf-8', newline='\n')
        self.environ = {'SHIMMER_ROLES_ROOT': str(self.roles)}
        self.paths['extra'] = cov.extra_roots(self.main, environ=self.environ)

    def roles_junction(self, rel, target):
        """A link under the roles root; removed as a link only by close()."""
        link = self.roles.joinpath(*rel.split('/'))
        Path(target).mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(str(target), str(link), target_is_directory=True)
        self.links.append(link)
        return link

    def roles_write(self, rel, text):
        p = self.roles.joinpath(*rel.split('/'))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8', newline='\n')
        return p


def with_roles(fn):
    def run():
        with tempfile.TemporaryDirectory() as t:
            fx = RolesFixture(t)
            try:
                fn(fx)
            finally:
                fx.close()
    run.__name__ = fn.__name__
    return run


@with_roles
def proof_roles_parts_covered_by_drive_only(fx):
    r = fx.report()
    ex1 = row(r, 'roles/_xfer/ex1')
    assert ex1['status'] == 'NOT COVERED' and ex1['drive_only'], ex1
    assert ex1['irreplaceable'] == 'role exchange', ex1['irreplaceable']
    assert row(r, 'roles/N/set1')['irreplaceable'] == 'negotiation set'
    assert row(r, 'roles/N/(files)')['files'] == 1
    assert 'roles/_xfer/ex1' in [x['part'] for x in cov.faults(r)]
    archive_now(fx, 'roles/_xfer/ex1')
    assert row(fx.report(), 'roles/_xfer/ex1')['status'] == 'COVERED'
    fx.roles_write('_xfer/ex1/%s_new.txt' % SENTINEL, 'new\n')
    assert row(fx.report(), 'roles/_xfer/ex1')['status'] == 'STALE'


@with_roles
def proof_git_never_counts_or_carries_drive_only(fx):
    # a records snapshot that (wrongly) holds a roles/ path with the file's exact blob id
    disk = fx.roles / '_xfer' / 'ex2' / ('%s_b.txt' % SENTINEL)
    repo = fx.paths['repo']
    subprocess.run(['git', 'init', '--bare', '-q', str(repo)], check=True, capture_output=True,
                   creationflags=cov.no_window())
    sha = git(repo, 'hash-object', '-w', '--no-filters', str(disk))
    env = dict(GIT_ENV, GIT_INDEX_FILE=str(fx.base / 'index'))
    git(repo, 'update-index', '--add', '--index-info',
        inp=('100644 %s\troles/_xfer/ex2/%s_b.txt\n' % (sha, SENTINEL)).encode(), env=env)
    git(repo, 'update-ref', 'refs/heads/records/private', git(repo, 'commit-tree', git(repo, 'write-tree', env=env),
                                                                   '-m', 'snapshot'))
    r = fx.report()
    ex2 = row(r, 'roles/_xfer/ex2')
    assert ex2['git_files'] == 0 and ex2['git_time'] is None and ex2['status'] == 'NOT COVERED', ex2
    assert cov.git_refusal(r) == 1, r['git']
    assert 'REFUSED' in cov.render(r)
    assert cov.drive_only_carried([('private/x', str(disk), 1)], fx.roles) == ['private/x']
    assert cov.drive_only_carried([('private/x', str(fx.main / 'docs'), 1)], fx.roles) == []


@with_roles
def proof_records_snapshot_refuses_drive_only(fx):
    import backup_records as br
    target = fx.base / 'records_repo'
    old = br.REPO
    br.REPO = target
    try:
        disk = fx.roles / 'N' / 'set1' / ('%s_t1.txt' % SENTINEL)
        try:
            br.snapshot([('roles/N/set1/%s_t1.txt' % SENTINEL, str(disk), disk.stat().st_size)])
            refused = False
        except br.bp.BackupError:
            refused = True
    finally:
        br.REPO = old
    assert refused and not target.exists(), 'a drive-only path reached the git snapshot'


@with_roles
def proof_declared_exclusions_never_opened(fx):
    opened = []
    real_scandir, real_stat = os.scandir, os.stat

    def scandir(p='.'):
        opened.append(str(p))
        return real_scandir(p)

    def stat(p, *a, **k):
        opened.append(str(p))
        return real_stat(p, *a, **k)
    os.scandir, os.stat = scandir, stat
    try:
        r = fx.report()
    finally:
        os.scandir, os.stat = real_scandir, real_stat
    bad = [p for p in opened if Path(p).name in ('B', '_seckin') or 'answer_key' in Path(p).name
           or ('_xfer' in Path(p).parts and 'B' in Path(p).parts)]
    assert not bad, len(bad)
    b = row(r, 'roles/_xfer/B')
    assert b['status'] == 'EXCLUDED' and b['declared'] == 'declared role folder' and not b['irreplaceable'], b
    assert row(r, 'roles/N/set1')['declared_excluded'] == 1 and row(r, 'roles/N/set1')['files'] == 1
    assert r['extra']['declared_excluded'] == 2 and r['extra']['roots'] == ['roles/_xfer', 'roles/N'], r['extra']
    assert not any(p['part'].startswith(('roles/B', 'roles/_seckin')) for p in r['parts'])


@with_roles
def proof_public_report_counts_only(fx):
    fx.roles_junction('N/set1/%s_link' % SENTINEL, fx.base / 'outside_r')
    r = fx.report()
    text = cov.render(r, gaps=10)
    dumped = json.dumps(cov.public(r), default=str)
    assert SENTINEL not in text and SENTINEL not in dumped and 'answer_key' not in dumped
    assert 'paths not printed (drive-only root)' in text and 'excluded by declaration 1' in text
    assert row(cov.public(r), 'roles/N/set1')['links_count'] == 1


def proof_roles_location_declared():
    with tempfile.TemporaryDirectory() as t:
        base = Path(t)
        (base / 'main').mkdir()
        (base / 'sib' / 'N').mkdir(parents=True)
        (base / 'env_root' / '_xfer').mkdir(parents=True)
        cfg = base / 'roots.json'
        decl = {'version': 1, 'roots_location': {'env': 'SHIMMER_ROLES_ROOT', 'sibling_of_main_checkout': 'sib'},
                'roots': [{'folder': '_xfer', 'drive_only': True}, {'folder': 'N', 'drive_only': True},
                          {'folder': 'C', 'drive_only': True}],
                'excluded': {'role_folders': ['C'], 'name_contains': ['answer_key']}}
        cfg.write_text(json.dumps(decl), encoding='utf-8')
        sib = cov.extra_roots(base / 'main', environ={}, config_path=cfg)
        assert [r['logical'] for r in sib['roots']] == ['roles/N'] and sib['missing'] == ['roles/_xfer'], sib
        assert sib['refused'] == [('roles/C', 'declared role folder')], sib['refused']
        env = cov.extra_roots(base / 'main', environ={'SHIMMER_ROLES_ROOT': str(base / 'env_root')}, config_path=cfg)
        assert [r['logical'] for r in env['roots']] == ['roles/_xfer'] and env['how'] == 'SHIMMER_ROLES_ROOT', env
        for environ, changed in (({'SHIMMER_ROLES_ROOT': 'relative/folder'}, None),
                                 ({}, dict(decl, roots=[{'folder': 'N', 'drive_only': False}]))):
            if changed:
                cfg.write_text(json.dumps(changed), encoding='utf-8')
            try:
                cov.extra_roots(base / 'main', environ=environ, config_path=cfg)
            except cov.CoverageError:
                continue
            raise AssertionError('a relative roles root or a root not declared drive_only was accepted')


@with_roles
def proof_roles_archive_counts_only(fx):
    fx.roles_write('N/set1/.env', 'NAME=value\n')
    fx.roles_write('N/set1/%s_k.txt' % SENTINEL, 'a line with ' + FAKE_KEY + '\n')
    fx.roles_junction('N/set1/%s_link' % SENTINEL, fx.base / 'outside_a')
    line = archive_now(fx, 'roles/N/set1')
    logged = fx.paths['log'].read_text(encoding='utf-8')
    assert line['verified'] is True and line['drive_only'] is True, line
    assert SENTINEL not in json.dumps(line) and SENTINEL not in logged and 'answer_key' not in logged
    assert line['left_out_counts'] == {'declared out of scope': 1, 'credential name': 1, 'key pattern': 1}, line
    assert line['links_not_followed'] == 1 and line['files'] == 1
    assert cov.sha256_file(line['file']) == line['sha256']
    # the coverage's own scan excludes the key-bearing file the archive left out: the part is COVERED
    after = row(cov.coverage(fx.paths), 'roles/N/set1')
    assert after['status'] == 'COVERED' and after['excluded_count'] == 2, after['status']


@with_roles
def proof_roles_archive_never_opens_declared(fx):
    import tarfile
    opened = []
    real_scandir = os.scandir

    def scandir(p='.'):
        opened.append(str(p))
        return real_scandir(p)
    os.scandir = scandir
    try:
        line = archive_now(fx, 'roles/N/set1')
        files, links, left = da.gather(fx.main, 'roles/_xfer/B', [], fx.paths['extra'])
    finally:
        os.scandir = real_scandir
    with tarfile.open(line['file'], 'r:gz') as t:
        names = t.getnames()
    assert names == ['roles/N/set1/%s_t1.txt' % SENTINEL], len(names)
    assert files == [] and left == [('roles/_xfer/B', 'declared out of scope')], (len(files), len(left))
    assert not any(Path(p).name == 'B' for p in opened), len(opened)


@with_roles
def proof_roles_archive_refuses_drive_inside_backup(fx):
    fx.paths['drive'] = fx.main / 'drive_in_checkout'
    try:
        archive_now(fx, 'roles/_xfer/ex1')
        refused = False
    except da.Refused:
        refused = True
    assert refused and not fx.paths['drive'].exists(), 'a drive-only part was written inside the main checkout'
    assert not fx.paths['log'].exists()


def quiet(fn, argv):
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(argv)


def patch_attr(owner, name, value):
    def apply():
        old = getattr(owner, name)
        setattr(owner, name, value)
        return lambda: setattr(owner, name, old)
    return apply


def hashwriter_not_hashing():
    def write(self, b):
        self.n += len(b)
        return self.f.write(b)
    return patch_attr(da.HashWriter, 'write', write)


def git_restore_writes_nothing(paths, part, dest):
    tree = cov.git_snapshot(paths['repo'])[0]
    return {p for p in tree if cov.part_of(p) == part}, 'git'


GROUPS = {
    'coverage': [
        # content no longer compared: the path alone counts as covered
        (proof_git_blob_ids_decide, patch_attr(cov, 'git_holds', lambda tree, logical, disk, size: logical in tree)),
        # every logged archive accepted, whatever its verification and size
        (proof_drive_needs_verified_and_size, patch_attr(cov, 'archive_ok', lambda line, path: True)),
        # links no longer recognised: the walk enters the junction
        (proof_links_recorded_never_followed, patch_attr(cov, 'is_link', lambda p: False)),
        # nothing counted as irreplaceable
        (proof_exit_on_irreplaceable_gap, patch_attr(cov, 'irreplaceable', lambda part, files: False)),
        # credential names no longer recognised
        (proof_credentials_and_held_back_excluded, patch_attr(cov, 'credential_name', lambda name: False)),
        # the change time no longer read
        (proof_time_only_legacy_archive, patch_attr(cov, 'changed_time', lambda st: 0.0)),
    ],
    'archive': [
        (proof_archive_hashes_twice_and_logs, hashwriter_not_hashing()),
        (proof_archive_leaves_out_links_and_keys, patch_attr(cov, 'credential_name', lambda name: False)),
        (proof_keep_report_deletes_nothing, patch_attr(cov, 'drive_archives', lambda *a, **k: [])),
        (proof_drive_floor_stops_before_writing, patch_attr(da, 'FLOOR', 0)),
    ],
    'drill': [
        (proof_drill_restores_and_matches, patch_attr(rd, 'restore_git', git_restore_writes_nothing)),
        (proof_drill_detects_a_difference, patch_attr(rd, 'compare', lambda live, root, restored: [])),
        (proof_drill_refuses_inside_main, patch_attr(rd, 'inside', lambda path, root: False)),
    ],
    'roles': [
        # the roles/ namespace no longer split into parts: roles/<root>/<folder> is never reported
        (proof_roles_parts_covered_by_drive_only, patch_attr(cov, 'EXTRA_NS', 'not-roles')),
        # nothing counted as drive-only: the git snapshot counts for roles/ paths again
        (proof_git_never_counts_or_carries_drive_only, patch_attr(cov, 'drive_only', lambda logical: False)),
        # the records snapshot's refusal emptied: a roles/ path is stored in git
        (proof_records_snapshot_refuses_drive_only, patch_attr(cov, 'drive_only_carried', lambda *a, **k: [])),
        # declared exclusions no longer matched: role folders and answer_key names are opened
        (proof_declared_exclusions_never_opened, patch_attr(cov, 'excluded_name', lambda *a, **k: '')),
        # the report printed whole: inner paths of a drive-only part are shown
        (proof_public_report_counts_only, patch_attr(cov, 'public', lambda r: dict(r, drive_only_links=0))),
        # the roles root variable ignored: only the sibling folder is read
        (proof_roles_location_declared, patch_attr(
            cov, 'roles_location', lambda main, environ=None, location=None:
            (Path(main).parent / location['sibling_of_main_checkout'], 'sibling of the main checkout'))),
    ],
    'roles_archive': [
        # the log line carries the left-out names again
        (proof_roles_archive_counts_only, patch_attr(da, 'left_counts', lambda left: {'left_out': [p for p, _ in left]})),
        # declared exclusions no longer matched: answer_key and role folders archived
        (proof_roles_archive_never_opens_declared, patch_attr(cov, 'excluded_name', lambda *a, **k: '')),
        # the Drive folder check removed: a drive-only part written inside the main checkout
        (proof_roles_archive_refuses_drive_inside_backup, patch_attr(da, 'refuse_drive_inside_backup',
                                                                     lambda paths: None)),
    ],
}

DETAIL = {
    'coverage': 'git coverage by blob id, Drive coverage only from verified archives of the logged size, links '
                'recorded and never followed, exit 1 on an irreplaceable gap, credential names and held-back '
                'files excluded, a legacy archive judged by time',
    'archive': 'each archive hashed while written and again from Drive with a per-member manifest, links and '
               'key-bearing or credential-named files left out, the keep-last-N report deleting nothing, the '
               'Drive floor stopping a part before anything is written',
    'drill': 'both backups restored into a new folder outside the checkout and matched by hash, a changed file '
             'caught, a drill folder inside the main checkout refused',
    'roles': 'the declared drive-only roots (role exchange folders, negotiation sets) reported part by part '
             'as COVERED, STALE or NOT COVERED by Drive archives only, the git snapshot never counted and a '
             'snapshot holding a roles/ path a fault, backup_records refusing such a snapshot before storing, '
             'declared role folders and answer_key names never opened and recorded as excluded, the printed '
             'and JSON report carrying counts only, the roots location read from SHIMMER_ROLES_ROOT or the '
             'declared sibling folder and a relative root or a root not declared drive_only refused',
    'roles_archive': 'a drive-only part archived and verified with counts, sizes and hashes only in the log '
                     'and printed line, declared names never opened or archived, a Drive folder inside the '
                     'main checkout refused before anything is written',
}


def run_group(name):
    passed = 0
    for proof, neutralise in GROUPS[name]:
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
        passed += 1
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass, fixtures only: %s' % (passed, DETAIL[name])


def check_coverage():
    return run_group('coverage')


def check_archive():
    return run_group('archive')


def check_drill():
    return run_group('drill')


def check_roles():
    return run_group('roles')


def check_roles_archive():
    return run_group('roles_archive')


if __name__ == '__main__':
    names = sys.argv[1:] or list(GROUPS)
    worst = 0
    for n in names:
        status, detail = run_group(n)
        print(n, status, detail)
        worst = worst or (status != 'PASS')
    raise SystemExit(1 if worst else 0)
