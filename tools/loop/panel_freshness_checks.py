#!/usr/bin/env python3
"""Check 680 (PANEL-FRESH-A, Seckin 20 November 2026, G-20261120-1220 and G-20261120-1227): tools/loop/panel_freshness.py.

On invented fixtures in a temporary directory only (a panel, saved copies, a DECISIONS.md, chg_decisions.json,
done_since.json and a panel_status reading); no real panel copy, private record, ALERT.md or trace is read or written.

  fresh_passes     a panel whose rows were first seen an hour ago, whose bars match panel_status and whose one
                   decision has its CHG line, has no finding
  stale_flagged    a running V105 row first seen 30 hours ago in a saved copy is STALE; the same row with no copy and
                   no date is not
  missing_chg      a decision from decisions_from on with no CHG line named for it is NO-CHG
  past_time        "Tahmini başlangıç 17:30" in a row first seen on 19 Nov 15:10 is PAST on 20 Nov 12:30
  bars_count       a BARS count 17 of 30 against panel_status 18 of 30 is BARS
  move_and_words   an OPEN row done for 30 hours is MOVE, `move` takes it out of OPEN into one CHG line in date order;
                   "sürüyor" in a done row is WORD
  mark_records     mark records a newly done row with the time now, keeps an earlier sighting, drops a row back to run
  alert_once       the alert mode reads the newest saved copy and writes one ALERT line naming the stale section
                   through the injected alert writer, and one trace line; a fresh copy writes none
  cli_exit         `check` exits 1 on a stale panel and 0 on a fresh one

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes).
"""
from __future__ import annotations

import contextlib
import copy
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
import panel_freshness as pf  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=3))
NOW = dt.datetime(2026, 11, 20, 12, 30, tzinfo=TZ)
CFG = pf.load_config()
CFG['decisions_from'] = 'D-900'
PROOFS = ['fresh_passes', 'stale_flagged', 'missing_chg', 'past_time', 'bars_count', 'move_and_words',
          'mark_records', 'alert_once', 'cli_exit']
_cfg = {'value': CFG}


def cfg():
    return _cfg['value']


@contextlib.contextmanager
def cfg_changed(**kw):
    saved = _cfg['value']
    new = copy.deepcopy(saved)
    new.update(kw)
    _cfg['value'] = new
    try:
        yield
    finally:
        _cfg['value'] = saved


def iso(t):
    return t.isoformat(timespec='seconds')


def panel(v105_note='Ölçüm sürüyor', plan_done=17, open_note='Bitti 20 Kasım 11:00, 1,20 dolar'):
    return {
        'STAMP_ISO': iso(NOW - dt.timedelta(minutes=10)),
        'KPIS': [{'l': 'Para', 'n': "435 doların 300,00'ü harcandı", 'v': '135,00 dolar kaldı'}],
        'BARS': [{'t': 'Ana plan', 'n': 'Biten adım: %d. Toplam adım: 30.' % plan_done, 'v': plan_done / 30},
                 {'t': 'Harcanan para', 'n': "435 doların 300,00'ü", 'v': 300 / 435}],
        'PLAN': [['1', 'İş bir', 'done', '']],
        'V105': [['Hız', 'run', v105_note]],
        'OPEN': [['Yeni iş', 'done', open_note]],
        'RES': [['Makine', 'run', 'Çalışıyor']],
        'ISTEK': [['İstek bir', 'run', 'Yapılıyor']],
        'CHG': [['20 Kas', 'Karar bir', 'a', 'b']],
    }


STATUS = {'cubuklar': [{'ad': 'Plan', 'deger': 17, 'hedef': 30}, {'ad': 'Harcama', 'deger': 300.0, 'hedef': 435.0}],
          'kullanim': None}
DECISIONS = '# Decisions\n\n## D-899: old\nWritten 2026-11-19 09:00 +0300 by the lead.\n\n' \
            '## D-900: one\nWritten 2026-11-20 09:00 +0300 by the lead.\n'
CHG_MAP = {'D-900': '20 Kas|Karar bir'}


def fixture(root, p=None, copy_at=None, decisions=DECISIONS, done_since=None):
    """A main checkout in root: DECISIONS.md, chg map, done_since, one saved copy of p stamped copy_at."""
    root = Path(root)
    (root / 'docs' / 'loop' / 'private' / 'panel' / 'copies').mkdir(parents=True, exist_ok=True)
    (root / cfg()['decisions_file']).write_text(decisions, encoding='utf-8')
    (root / cfg()['chg_map']).write_text(json.dumps(CHG_MAP, ensure_ascii=False), encoding='utf-8')
    (root / cfg()['done_since']).write_text(json.dumps(done_since or {
        'OPEN|Yeni iş': {'since': iso(NOW - dt.timedelta(hours=2)), 'state': 'done'}}, ensure_ascii=False),
        encoding='utf-8')
    p = p or panel()
    saved = dict(p, STAMP_ISO=iso(copy_at or NOW - dt.timedelta(hours=1)))
    (root / 'docs' / 'loop' / 'private' / 'panel' / 'copies' / 'durum_a.json').write_text(
        json.dumps(saved, ensure_ascii=False), encoding='utf-8')
    return root


def run_check(root, p, status=STATUS):
    copies = pf.load_copies(pf.copy_paths(cfg(), root))
    res = pf.check(p, cfg(), NOW, status=status, copies=copies,
                   decisions=pf.read_decisions(Path(root) / cfg()['decisions_file']),
                   chg_map=pf.read_json(Path(root) / cfg()['chg_map']),
                   done_since=pf.read_json(Path(root) / cfg()['done_since']))
    return sorted((f['kind'], f['section'], f['row']) for f in res['findings'])


@contextlib.contextmanager
def tmp():
    with tempfile.TemporaryDirectory(prefix='shimmer_gate_panelfresh_') as d, \
            patch.dict(os.environ, {CFG['copies_env']: ''}):
        yield Path(d)


# ---------------------------------------------------------------- proofs

def observe_fresh_passes():
    with tmp() as d:
        return run_check(fixture(d), panel())


def expected_fresh_passes():
    return []


def neutralise_fresh_passes():
    return cfg_changed(max_age_hours=-1)


def observe_stale_flagged():
    with tmp() as d:
        stale = run_check(fixture(d, copy_at=NOW - dt.timedelta(hours=30)), panel())
    with tmp() as d:
        root = fixture(d)
        (root / 'docs' / 'loop' / 'private' / 'panel' / 'copies' / 'durum_a.json').unlink()
        undated = run_check(root, panel())
    return stale, undated


def expected_stale_flagged():
    # every unfinished row and every card first seen 30 hours ago; the finished PLAN and OPEN rows and CHG never
    return ([('STALE', 'BARS', 'Ana plan'), ('STALE', 'BARS', 'Harcanan para'), ('STALE', 'ISTEK', 'İstek bir'),
             ('STALE', 'KPIS', 'Para'), ('STALE', 'RES', 'Makine'), ('STALE', 'V105', 'Hız')], [])


def neutralise_stale_flagged():
    return patch.object(pf, 'first_seen', lambda copies, c: ({}, None))


def observe_missing_chg():
    with tmp() as d:
        return run_check(fixture(d, decisions=DECISIONS + '\n## D-901: two\nWritten 2026-11-20 10:00 +0300 by x.\n'),
                         panel())


def expected_missing_chg():
    return [('NO-CHG', 'CHG', 'D-901')]


def neutralise_missing_chg():
    real = pf.read_decisions
    return patch.object(pf, 'read_decisions', lambda path: [x for x in real(path) if x[0] != 'D-901'])


def observe_past_time():
    with tmp() as d:
        p = panel(v105_note='Tahmini başlangıç 17:30')
        return run_check(fixture(d, p=p, copy_at=dt.datetime(2026, 11, 19, 15, 10, tzinfo=TZ)), p)


def expected_past_time():
    return [('PAST', 'V105', 'Hız')]


def neutralise_past_time():
    return patch.object(pf, 'nearest', lambda h, m, anchor: None)


def observe_bars_count():
    with tmp() as d:
        status = copy.deepcopy(STATUS)
        status['cubuklar'][0]['deger'] = 18
        return run_check(fixture(d), panel(), status=status)


def expected_bars_count():
    return [('BARS', 'BARS', 'Ana plan')]


def neutralise_bars_count():
    return patch.object(pf, 'bar_findings', lambda p, s, c: [])


def observe_move_and_words():
    old = {'OPEN|Yeni iş': {'since': iso(dt.datetime(2026, 11, 19, 9, 0, tzinfo=TZ)), 'state': 'done'}}
    with tmp() as d:
        p = panel(open_note='Bitti, ölçüm sürüyor')
        found = run_check(fixture(d, done_since=old), p)
    moved, new = pf.move(p, cfg(), NOW, old)
    return found, [r[0] for r in moved['OPEN']], [r[:2] for r in moved['CHG']], len(new)


def expected_move_and_words():
    return ([('MOVE', 'OPEN', 'Yeni iş'), ('WORD', 'OPEN', 'Yeni iş')], [],
            [['19 Kas', 'Yeni iş'], ['20 Kas', 'Karar bir']], 1)


def neutralise_move_and_words():
    return cfg_changed(move_states=[])


def observe_mark_records():
    earlier = iso(NOW - dt.timedelta(hours=5))
    p = panel()
    p['ISTEK'] = [['İstek bir', 'done', 'Bitti 20 Kasım 12:00'], ['İstek iki', 'run', 'Yapılıyor']]
    out = pf.mark(p, cfg(), NOW, {'OPEN|Yeni iş': {'since': earlier, 'state': 'done'},
                                  'ISTEK|İstek iki': {'since': earlier, 'state': 'done'}})
    return sorted((k, v['since']) for k, v in out.items())


def expected_mark_records():
    return [('ISTEK|İstek bir', iso(NOW)), ('OPEN|Yeni iş', iso(NOW - dt.timedelta(hours=5)))]


def neutralise_mark_records():
    return cfg_changed(move_states=[])


def observe_alert_once():
    out = []
    for at in (NOW - dt.timedelta(hours=30), NOW - dt.timedelta(hours=1)):
        alerts, traces = [], []
        with tmp() as d:
            res = pf.run_alert(cfg(), fixture(d, copy_at=at), NOW, status=STATUS,
                               alert=lambda key, text, every: alerts.append((key, text)) or True,
                               trace=lambda name, result, **kw: traces.append((name, result)))
        out.append((res['result'], len(alerts), all('V105' in k for k, _ in alerts), traces))
    return out


def expected_alert_once():
    return [('alert', 1, True, [('panel_freshness', 'alert')]), ('ok', 0, True, [('panel_freshness', 'ok')])]


def neutralise_alert_once():
    return cfg_changed(saved_copies=[])


def observe_cli_exit():
    codes = []
    for at in (NOW - dt.timedelta(hours=30), NOW - dt.timedelta(hours=1)):
        with tmp() as d:
            root = fixture(d, copy_at=at)
            cur = root / 'cur.json'
            cur.write_text(json.dumps(panel(), ensure_ascii=False), encoding='utf-8')
            st = root / 'status.json'
            st.write_text(json.dumps(STATUS), encoding='utf-8')
            cf = root / 'cfg.json'
            cf.write_text(json.dumps(cfg(), ensure_ascii=False), encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                codes.append(pf.main(['check', str(cur), '--main', str(root), '--status', str(st), '--now', iso(NOW),
                                      '--config', str(cf)]))
    return codes


def expected_cli_exit():
    return [1, 0]


def neutralise_cli_exit():
    return patch.object(pf, 'check', lambda *a, **k: {'findings': [], 'sections': {}})


def caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return 'raised %s: %s' % (type(exc).__name__, exc)


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
        done.append('%s (neutralised: %s)' % (name, str(broken)[:120]))
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass, fixtures only: %s' % (len(done), '; '.join(done))


if __name__ == '__main__':
    status, detail = run_all()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
