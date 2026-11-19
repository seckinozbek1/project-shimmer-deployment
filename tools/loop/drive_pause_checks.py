"""Proofs of the Drive upload pause (D-764, Seckin 19 November 2026 08:17; checks 640 to 643). Before each
archive write and between its files, drive_archive reads free disk on the disk config/drive_no_download.json
upload_pause declares and stops writing under its floor_gib, with one ALERT.md line ("Drive uploads paused: C:
free X GiB under floor Y GiB"); drive_paced stops its run (exit 6) and the next run resumes above the floor.

Fixtures only: backup_coverage_checks' temporary main checkout and fake Drive folder, a temporary config file
(backup_coverage.NO_DOWNLOAD_CONFIG patched), mechanism_common's ALERT.md, alert state and trace redirected to
the fixture, and the disk reading monkeypatched (drive_archive.read_disk_free). The real C:, Drive folder,
ALERT.md and tasks are never touched. Each proof is run as built (passes), neutralised (must fail), restored
(passes).

    py -3.12 -X utf8 tools/loop/drive_pause_checks.py               # all four
    py -3.12 -X utf8 tools/loop/drive_pause_checks.py between       # before, between, paced or config
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backup_coverage as cov  # noqa: E402
import backup_coverage_checks as bcc  # noqa: E402
import drive_archive as da  # noqa: E402
import drive_paced as dp  # noqa: E402
import mechanism_common as mc  # noqa: E402

GIB = 2 ** 30
PREFIX = 'Drive uploads paused: C: free '


def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    return lambda: setattr(owner, name, old)


class Env:
    """A fixture config (upload_pause floor) and mechanism_common writing into the fixture only."""

    def __init__(self, fx, floor_gib=12, reading=None):
        self.fx = fx
        self.cfg = fx.base / 'drive_no_download.json'
        self.set_floor(floor_gib)
        private = fx.base / 'private'
        private.mkdir(exist_ok=True)
        self.alert = private / 'ALERT.md'
        self.reads = []
        self.reading = reading or (lambda: 100 * GIB)
        self.restores = [patched(cov, 'NO_DOWNLOAD_CONFIG', self.cfg),
                         patched(mc, 'PRIVATE', private), patched(mc, 'TRACE', private / 'trace.jsonl'),
                         patched(mc, 'ALERT', self.alert), patched(mc, 'ALERT_STATE', private / 'alert_state.json'),
                         patched(da, 'read_disk_free', self.read)]

    def set_floor(self, floor_gib):
        body = {} if floor_gib is None else {'upload_pause': {'disk': 'C:/', 'floor_gib': floor_gib}}
        self.cfg.write_text(json.dumps(body), encoding='utf-8')

    def read(self, disk):
        self.reads.append(disk)
        return self.reading()

    def alert_lines(self):
        if not self.alert.is_file():
            return []
        return [x for x in self.alert.read_text(encoding='utf-8').splitlines() if 'Drive uploads paused' in x]

    def trace(self):
        return mc.read_trace()

    def close(self):
        for r in reversed(self.restores):
            r()


def archive(fx, part):
    """drive_archive.archive_part as drive_paced calls it (no disk_free override: the patched reader)."""
    return da.archive_part(fx.paths, part, patterns=da.strict_patterns(), free=lambda p: 100 * GIB)


def drive_files(fx):
    return sorted(p.name for p in Path(fx.paths['drive']).rglob('*') if p.is_file())


# --- 640 before the archive write ------------------------------------------------------------------------

@bcc.with_fixture
def proof_pause_before_write(fx):
    env = Env(fx, reading=lambda: int(9.5 * GIB))
    try:
        line = archive(fx, 'external/s05/GATE')
        assert line.get('paused', '').startswith(PREFIX + '9.5 GiB under floor 12.0 GiB'), line
        assert drive_files(fx) == [], drive_files(fx)          # nothing written under Drive, not even a folder file
        assert line.get('partial_left') is None and 'file' not in line, line
        alerts = env.alert_lines()
        assert len(alerts) == 1 and PREFIX + '9.5 GiB under floor 12.0 GiB' in alerts[0], alerts
        logged = [json.loads(x) for x in Path(fx.paths['log']).read_text(encoding='utf-8').splitlines()]
        assert logged[-1].get('paused') and logged[-1]['tool'] == 'drive_archive', logged[-1]
        # above the floor the same part is written and verified as before
        env.reading = lambda: 40 * GIB
        ok = archive(fx, 'external/s05/GATE')
        assert ok.get('verified') is True and 'paused' not in ok, ok
        assert len(env.alert_lines()) == 1
    finally:
        env.close()


# --- 641 between files -----------------------------------------------------------------------------------

@bcc.with_fixture
def proof_pause_between_files(fx):
    for i in range(4):
        fx.write('external/s05/MULTI/f%d.txt' % i, 'file %d\n' % i * 50)
    seq = iter([20 * GIB, 20 * GIB, 11 * GIB] + [11 * GIB] * 10)  # before; file 1; file 2 under the floor
    env = Env(fx, reading=lambda: next(seq))
    try:
        line = archive(fx, 'external/s05/MULTI')
        assert line.get('paused', '').startswith(PREFIX + '11.0 GiB under floor 12.0 GiB'), line
        names = drive_files(fx)
        assert not any(n.endswith('.tar.gz') for n in names), names      # never renamed into an archive
        assert len([n for n in names if n.endswith('.partial')]) == 1 and line['partial_left'], (names, line)
        assert not any(n.endswith('.manifest.json') for n in names), names
        assert len(env.reads) == 3, env.reads                             # stopped at the second file's check
        assert len(env.alert_lines()) == 1
    finally:
        env.close()


def write_archive_without_guard(real):
    def write(target, files, guard=None):
        return real(target, files)
    return write


# --- 642 drive_paced stops the run and the next run resumes ---------------------------------------------

@bcc.with_fixture
def proof_paced_stops_and_next_run_resumes(fx):
    env = Env(fx, reading=lambda: 8 * GIB)
    calls = []
    todo = [{'part': 'external/s05/GATE', 'need_bytes': 10}, {'part': 'external/s05/P1', 'need_bytes': 10}]

    def fake_archive(paths, part):
        calls.append(part)
        return {'file': str(Path(paths['drive']) / (part.replace('/', '__') + '.tar.gz')), 'md5': '0' * 32,
                'verified': True, 'time': 'now'}

    restores = [patched(dp, 'lock', lambda: object()), patched(dp.mc, 'wait_for_ram', lambda name: True),
                patched(dp.cov, 'default_paths', lambda *a, **k: fx.paths),
                patched(dp, 'confirm_pass', lambda paths: {}), patched(dp, 'pending', lambda paths, inc: list(todo)),
                patched(dp, 'wait_for_room', lambda part, need, s: True), patched(dp, 'free_disk', lambda: 8 * GIB),
                patched(dp, 'drive_free_bytes', lambda paths: 100 * GIB),
                patched(dp.da, 'archive_part', fake_archive),
                patched(dp, 'confirm', lambda f, md5=None: ('cloud_confirmed', {'md5': md5}))]
    try:
        code = dp.main(['--confirm-wait-min', '0'])
        assert code == da.PAUSED_EXIT and calls == [], (code, calls)
        assert len(env.alert_lines()) == 1, env.alert_lines()
        assert any(x.get('result') == 'paused' for x in env.trace()), env.trace()
        # the next scheduled run, free disk above the floor: every part goes, no new pause line
        env.reading = lambda: 30 * GIB
        code = dp.main(['--confirm-wait-min', '0'])
        assert code == 0 and calls == ['external/s05/GATE', 'external/s05/P1'], (code, calls)
        assert len(env.alert_lines()) == 1
    finally:
        for r in reversed(restores):
            r()
        env.close()


# --- 643 the floor is read from config at call time; none declared refuses --------------------------------

@bcc.with_fixture
def proof_floor_from_config(fx):
    env = Env(fx, reading=lambda: 20 * GIB)
    try:
        assert 'paused' not in archive(fx, 'external/s05/GATE')          # 20 GiB above the declared 12
        env.set_floor(30)                                                 # the config changed, no restart
        line = archive(fx, 'external/s05/P1')
        assert line.get('paused', '').startswith(PREFIX + '20.0 GiB under floor 30.0 GiB'), line
        env.set_floor(None)                                               # no declaration: nothing written
        before = drive_files(fx)
        try:
            archive(fx, 'external/other')
            raise AssertionError('no declared floor was not refused')
        except da.Refused as exc:
            assert 'upload_pause' in str(exc), exc
        assert drive_files(fx) == before
    finally:
        env.close()


def floor_typed_in(config=None):
    return 12 * GIB, 'C:/'


GROUPS = {
    'before': (640, proof_pause_before_write, lambda: patched(da, 'pause_check', lambda config=None, reader=None: 0)),
    'between': (641, proof_pause_between_files,
                lambda: patched(da, 'write_archive', write_archive_without_guard(da.write_archive))),
    'paced': (642, proof_paced_stops_and_next_run_resumes, lambda: patched(dp, 'paused_now', lambda part: False)),
    'config': (643, proof_floor_from_config, lambda: patched(da, 'pause_floor', floor_typed_in)),
}

DETAIL = {
    'before': 'drive_archive under the declared floor (C: free 9.5 GiB monkeypatched, floor 12) writes nothing '
              'under Drive, logs a paused line and puts one ALERT.md line "Drive uploads paused: C: free 9.5 GiB '
              'under floor 12.0 GiB"; above the floor the part is written and verified',
    'between': 'free disk falling under the floor between the files of one archive stops the write at the next '
               'file: the .partial stays, is never renamed, no manifest, one ALERT.md line',
    'paced': 'drive_paced under the floor starts no part, exits 6 with a paused trace and one ALERT.md line; '
             'the next run above the floor archives every part',
    'config': 'the floor is read from config/drive_no_download.json at call time (12 then 30 GiB at the same '
              '20 GiB reading); with no upload_pause.floor_gib the write is refused and nothing is written',
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
