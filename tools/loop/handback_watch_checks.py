#!/usr/bin/env python3
"""Check 529 (lane/handback-watch): the watchdog's role hand-back watch (tools/loop/handback_watch.py), the lead
18 November 2026 16:05.

On invented fixtures in a temporary directory: a roles root found through the config's roots_location (the
environment variable it names), the declared exchange folders holding *_DONE.json and *_HANDBACK.json files with
set modification times, other files, a junction, and an ack file. No real role folder is listed or read.

  late_unacknowledged_alerts  a hand-back over 10 minutes old with no ack, or acked before its newer version,
                              writes "role hand-back not taken up: <name> since <time>" and a trace line; one
                              under 10 minutes, or acked after its time, does not
  once_per_file               a second run writes no second ALERT line for the same file and version, but a
                              trace line every run
  names_only                  only declared patterns in declared folders count; no file is ever opened under the
                              roles root and no junction is followed

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes).
"""
from __future__ import annotations

import builtins
import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import handback_watch as hw  # noqa: E402
import mechanism_common as mc  # noqa: E402

NOW = dt.datetime.now().astimezone().replace(microsecond=0)


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self.tmp.name)
        self.private = self.base / 'private'
        self.private.mkdir()
        self.roles = self.base / 'roles_fixture'
        self.cfg = hw.load_config()
        for folder in self.cfg['folders']:
            (self.roles / folder).mkdir(parents=True)
        self.links = []
        self.patches = [patch.object(mc, 'PRIVATE', self.private), patch.object(mc, 'TRACE', self.private / 'trace.jsonl'),
                        patch.object(mc, 'ALERT', self.private / 'ALERT.md'),
                        patch.object(mc, 'ALERT_STATE', self.private / 'alert_state.json'),
                        patch.dict(os.environ, {self.cfg['roots_location']['env']: str(self.roles)})]

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for link in self.links:          # each junction removed as a link, its target untouched
            try:
                if os.name == 'nt':
                    os.rmdir(link)       # a junction is removed as a link by rmdir
                else:
                    os.unlink(link)      # a symlink is removed as a link by unlink
            except OSError:
                pass
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def put(self, folder, name, minutes_ago):
        path = self.roles / folder / name
        path.write_text('{"secret": "never read"}', encoding='utf-8')
        t = (NOW - dt.timedelta(minutes=minutes_ago)).timestamp()
        os.utime(path, (t, t))
        return path

    def ack(self, acks):
        (self.private / 'handback_ack.json').write_text(json.dumps(
            {k: (NOW - dt.timedelta(minutes=m)).isoformat() for k, m in acks.items()}), encoding='utf-8')

    def check(self):
        return hw.check(now=NOW, cfg=self.cfg, private=self.private)

    def alert_lines(self):
        try:
            return [x for x in mc.ALERT.read_text(encoding='utf-8').splitlines() if 'role hand-back not taken up' in x]
        except OSError:
            return []

    def traces(self):
        return [x.get('result') for x in mc.read_trace() if x.get('mechanism') == hw.NAME]


def caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return 'raised %s' % type(exc).__name__


def observe_late_unacknowledged_alerts():
    with Fixture() as f:
        f.put('_xfer/N_to_lead', 'N35_DONE.json', 90)          # no ack: late
        f.put('_xfer/S_to_lead', 'S2_HANDBACK.json', 5)        # under 10 minutes: not yet
        f.put('_xfer/B_to_lead_dev', 'B7_DONE.json', 60)       # acked after its time
        f.put('_xfer/_handoff', 'N36_DONE.json', 30)           # acked before this newer version: late
        f.ack({'B7_DONE.json': 1, '_xfer/_handoff/N36_DONE.json': 40})
        r = f.check()
        lines = f.alert_lines()
        return (sorted(x['name'] for x in r['late']), len(lines),
                all(' since ' in x for x in lines), f.traces())


def expected_late_unacknowledged_alerts():
    return ['_xfer/N_to_lead/N35_DONE.json', '_xfer/_handoff/N36_DONE.json'], 2, True, ['alert']


def neutralise_late_unacknowledged_alerts():
    return patch.object(hw, 'acknowledged', lambda acks, folder, name, mtime: True)


def observe_once_per_file():
    with Fixture() as f:
        f.put('_xfer/N_to_lead', 'N35_DONE.json', 90)
        f.check()
        f.check()
        return len(f.alert_lines()), f.traces()


def expected_once_per_file():
    return 1, ['alert', 'alert']


def neutralise_once_per_file():
    return patch.object(hw, 'ONCE', 0)


def observe_names_only():
    with Fixture() as f:
        f.put('_xfer/N_to_lead', 'N35_DONE.json', 90)
        f.put('_xfer/N_to_lead', 'N35_notes.json', 90)          # not a declared pattern
        f.put('_xfer/N_to_lead', 'answer_DONE.txt', 90)         # not a declared pattern
        outside = f.base / 'outside'
        outside.mkdir()
        (outside / 'X9_DONE.json').write_text('{}', encoding='utf-8')
        os.utime(outside / 'X9_DONE.json', ((NOW - dt.timedelta(hours=2)).timestamp(),) * 2)
        link = f.roles / '_xfer' / 'B_to_lead_dev_link'          # a declared folder that is a junction: skipped
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(outside), str(link))
        else:                                                     # a directory symlink on POSIX
            os.symlink(str(outside), str(link), target_is_directory=True)
        f.cfg = dict(f.cfg, folders=f.cfg['folders'] + ['_xfer/B_to_lead_dev_link'])
        f.links.append(link)
        other = f.roles / '_xfer' / 'other_folder'
        other.mkdir()
        (other / 'Q1_DONE.json').write_text('{}', encoding='utf-8')
        opened = []
        real_open = builtins.open

        def guarded(file, *a, **k):
            if str(f.roles) in str(file):
                opened.append(str(file))
            return real_open(file, *a, **k)
        with patch.object(builtins, 'open', guarded):
            r = f.check()
        return sorted(x['name'] for x in r['late']), opened


def expected_names_only():
    return ['_xfer/N_to_lead/N35_DONE.json'], []


def neutralise_names_only():
    return patch.object(hw, 'matches', lambda name, patterns: True)


PROOFS = ('late_unacknowledged_alerts', 'once_per_file', 'names_only')


def run_all():
    done, space = [], globals()
    for name in PROOFS:
        observe, expected, neutralise = space['observe_' + name], space['expected_' + name], space['neutralise_' + name]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                first = observe()
                with neutralise():
                    broken = caught(observe)
                again = observe()
        except Exception as exc:  # noqa: BLE001
            return 'FAIL', '%s: %s %s' % (name, type(exc).__name__, str(exc)[:300])
        if first != expected():
            return 'FAIL', '%s as built: %s' % (name, str(first)[:600])
        if broken == expected():
            return 'FAIL', '%s still passes when neutralised' % name
        if again != expected():
            return 'FAIL', '%s after restore: %s' % (name, str(again)[:400])
        done.append('%s (neutralised: %s)' % (name, str(broken)[:200]))
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass, no role folder read: %s' % (len(done), '; '.join(done))


if __name__ == '__main__':
    status, detail = run_all()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
