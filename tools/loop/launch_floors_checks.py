"""Check 530: a Lambda launch is never refused for laptop RAM; each step kind holds its own declared floor.

Seckin, 18 Nov 18:54 (the lead 18:58). tools/loop/launch_floors.py reads config/launch_ram_floors.json at each call;
each launch folder's launch.py loads it by path and asks it for its step's floor; the launch chain names the step it
preflights. Proofs, each run as built, neutralised (must fail), restored (must pass), on fixtures, no provider call:

  kinds_hold_their_floors   at 0.6 GiB free the request, the seal, a part and the watch pass, the admission, a local
                            step and a bare preflight are refused, and an unreadable reading is refused
  read_at_call_time         a floor changed in the file takes effect on the next call; an unreadable file falls back
                            to the D-726 floor, never lower
  chain_names_the_step      a launch chain pass at 0.6 GiB free launches a part (its preflight told the step) and
                            holds an admission on its preflight
  shipped_floors_declared   the repository's declaration names every kind: the Lambda kinds under the fallback, the
                            laptop kinds at it

The laptop disk rule (Seckin 19 Nov 2026 12:03, config/laptop_disk_floor.json):

  disk_footprint_plus_margin     free disk >= the job's footprint + 12 GiB, the reason naming each figure; an unknown
                                 footprint said so and held to the old 30 GiB, never to the margin alone
  disk_rule_read_at_call_time    margin and Lambda launch floor read at each call; malformed or missing: 30 GiB
                                 fallback, never lower; the shipped file declares 12 and 12
  resource_reading_alerts_at_margin  the 30-minute reading alerts under the margin (not at 20 GiB, as the old 30 did)
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import launch_floors as lf  # noqa: E402
import launch_chain as lc  # noqa: E402
import launch_chain_checks as lcc  # noqa: E402

FLOORS = {'fallback_gib': 1.2, 'kinds': {'request': {'floor_gib': 0.5}, 'seal': {'floor_gib': 0.3},
                                         'part': {'floor_gib': 0.3}, 'watch': {'floor_gib': 0.3},
                                         'admit': {'floor_gib': 1.2}, 'local': {'floor_gib': 1.2}}}

HELPER_PREFLIGHT = r'''
if step == 'preflight' and 'ram_gib' in S:
    sys.path.insert(0, S['tools_loop'])
    import launch_floors
    told = sys.argv[2] if len(sys.argv) > 2 else 'preflight'
    problem = launch_floors.ram_problem(told, S['ram_gib'], S.get('lambda_steps', []), S.get('floors_config'))
    print('preflight: free RAM %.2f GiB; %s' % (S['ram_gib'], problem or 'all checks hold'))
    raise SystemExit(1 if problem else 0)
'''


def write_floors(path, cfg):
    Path(path).write_text(json.dumps(cfg), encoding='utf-8')
    return path


def observe_kinds_hold_their_floors():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = write_floors(Path(tmp) / 'floors.json', FLOORS)
        steps = ['request', 'seal', 'mplain', 'watch', 'admit', 'inventory', 'preflight']
        held = [lf.ram_problem(s, 0.6, ('seal', 'mplain'), cfg) is None for s in steps]
        return held, lf.ram_problem('mplain', float('nan'), ('mplain',), cfg) is not None


def expected_kinds_hold_their_floors():
    return [True, True, True, True, False, False, False], True


def neutralise_kinds_hold_their_floors():
    return patch.object(lf, 'kind_of', lambda step, lambda_steps=(): 'local')


def observe_read_at_call_time():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = write_floors(Path(tmp) / 'floors.json', FLOORS)
        first = lf.ram_problem('mplain', 0.6, ('mplain',), cfg) is None
        changed = json.loads(json.dumps(FLOORS))
        changed['kinds']['part']['floor_gib'] = 0.9
        write_floors(cfg, changed)
        second = lf.ram_problem('mplain', 0.6, ('mplain',), cfg) is None
        Path(cfg).write_text('{not json', encoding='utf-8')
        third = lf.floor_gib('mplain', ('mplain',), cfg)
        return first, second, third


def expected_read_at_call_time():
    return True, False, (1.2, 'part', 'fallback')


def neutralise_read_at_call_time():
    cache = {}
    real = lf.load

    def once(path=None):
        if 'cfg' not in cache:
            cache['cfg'] = real(path)
        return cache['cfg']
    return patch.object(lf, 'load', once)


def _helper_folder(f, name, status, admitted, cfg):
    d = f.folder(name, lcc.gate_chain(), status, admitted=admitted, ram_gib=0.6, tools_loop=str(HERE),
                 lambda_steps=['seal', 'part'], floors_config=str(cfg))
    fake = lcc.FAKE_LAUNCH.replace("if step == 'status':\n", HELPER_PREFLIGHT + "if step == 'status':\n", 1)
    (d / 'launch.py').write_text(fake, encoding='utf-8')
    return d


def observe_chain_names_the_step():
    with lcc.Fixture() as f:
        cfg = write_floors(f.base / 'floors.json', FLOORS)
        part = _helper_folder(f, 'P1', {'seal': lcc.ENDED, 'part': lcc.NOT}, True, cfg)
        admit = _helper_folder(f, 'P2', {'seal': lcc.ENDED, 'part': lcc.NOT}, False, cfg)
        lc.run_once(f.root)
        return f.launches(part), f.launches(admit), 'preflight_failed' in f.results()


def expected_chain_names_the_step():
    return ['part'], [], True


def neutralise_chain_names_the_step():
    real = lc.call_launch

    def unnamed(folder, args, timeout):
        return real(folder, args[:1] if args[:1] == ['preflight'] else args, timeout)
    return patch.object(lc, 'call_launch', unnamed)


def observe_shipped_floors_declared():
    fallback = lf.FALLBACK_GIB
    out = []
    for kind, probe in (('request', 'request'), ('seal', 'seal'), ('part', 'p'), ('watch', 'watch'),
                        ('admit', 'admit'), ('local', 'inventory')):
        value, got, source = lf.floor_gib(probe, ('p',))
        out.append((kind, got == kind and source == 'config',
                    value < fallback if kind in ('request', 'seal', 'part', 'watch') else value == fallback))
    return out


def expected_shipped_floors_declared():
    return [(k, True, True) for k in ('request', 'seal', 'part', 'watch', 'admit', 'local')]


def neutralise_shipped_floors_declared():
    return patch.object(lf, 'CONFIG', Path(tempfile.gettempdir()) / 'no_launch_ram_floors_here.json')


DISK_RULE = {'margin_gib': 12, 'lambda_launch_floor_gib': 12}


def observe_disk_footprint_plus_margin():
    """Seckin 19 Nov 2026 12:03: free disk >= footprint + margin. A 5 GiB job at 17.5 GiB free passes and at 16.9
    is refused with free, footprint, margin and the sum named; at 20 GiB a 10 GiB job is refused (the old 30 GiB
    floor would refuse even a 0.5 GiB job there, the new rule passes it); an unknown footprint is said so and held
    to the 30 GiB fallback, never to the margin alone."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = write_floors(Path(tmp) / 'disk.json', DISK_RULE)
        reason = lf.disk_problem(5, 16.9, path=cfg)
        unknown = lf.disk_problem(None, 20.0, path=cfg)
        return (lf.disk_problem(5, 17.5, path=cfg) is None, reason, lf.disk_problem(0.5, 20.0, path=cfg) is None,
                lf.disk_problem(10, 20.0, path=cfg) is not None, unknown, lf.disk_problem(None, 30.0, path=cfg) is None,
                lf.disk_problem(-1, 20.0, path=cfg) is not None)


def expected_disk_footprint_plus_margin():
    return (True, 'free disk 16.90 GiB is under 17.00 GiB (job footprint 5.00 GiB + margin 12.0 GiB, config rule)', True,
            True, 'free disk 20.00 GiB is under 30.00 GiB (job footprint not known: the 30 GiB fallback floor holds; '
                  'margin 12.0 GiB, config rule)', True, True)


def neutralise_disk_footprint_plus_margin():
    real = lf.required_gib

    def margin_only(footprint_gib, path=None):
        need, margin, source, known = real(0, path)
        return need, margin, source, True
    return patch.object(lf, 'required_gib', margin_only)


def observe_disk_rule_read_at_call_time():
    """The margin and the Lambda launch floor are read from the file at each call; a malformed file or a missing
    number falls back to the old 30 GiB, never lower; the shipped file declares 10 and 10 from D-849 (12 and 12 until 20 November 2026)."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = write_floors(Path(tmp) / 'disk.json', DISK_RULE)
        first = lf.disk_problem(2, 15.0, path=cfg) is None
        write_floors(cfg, dict(DISK_RULE, margin_gib=14))
        second = lf.disk_problem(2, 15.0, path=cfg) is None
        write_floors(cfg, {'lambda_launch_floor_gib': 'twelve'})
        missing = (lf.margin_gib(cfg), lf.lambda_launch_floor_gib(cfg))
        Path(cfg).write_text('{not json', encoding='utf-8')
        broken = (lf.margin_gib(cfg), lf.lambda_launch_floor_gib(cfg), 'fallback rule' in (lf.disk_problem(1, 20, path=cfg) or ''))
    shipped = lf.load_disk()
    return first, second, missing, broken, (lf.margin_gib(), lf.lambda_launch_floor_gib(),
                                            '2026-11-19 12:03' in shipped.get('decision', ''))


def expected_disk_rule_read_at_call_time():
    return (True, False, ((30.0, 'fallback'), (30.0, 'fallback')), ((30.0, 'fallback'), (30.0, 'fallback'), True),
            ((10.0, 'config'), (10.0, 'config'), True))


def neutralise_disk_rule_read_at_call_time():
    cache = {}
    real = lf.load_disk

    def once(path=None):
        if 'cfg' not in cache:
            cache['cfg'] = real(path)
        return cache['cfg']
    return patch.object(lf, 'load_disk', once)


def observe_resource_reading_alerts_at_margin():
    """The 30-minute resource reading (no job of its own) alerts when free disk is under the margin any heavy job
    needs, read from the rule now: 20 GiB free no alert (the old 30 GiB floor alerted), 11 GiB one alert naming the
    margin, and a margin of 25 in the file alerts at 20 GiB."""
    import types
    import mechanism_common as mc
    import resource_reading as rr
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        cfg = write_floors(Path(tmp) / 'disk.json', DISK_RULE)
        for free, margin in ((20, 12), (11, 12), (20, 25)):
            write_floors(cfg, dict(DISK_RULE, margin_gib=margin))
            alerts, traces = [], []
            with patch.object(lf, 'DISK_CONFIG', cfg), patch.object(mc, 'alert', lambda key, text: alerts.append(text)), \
                    patch.object(mc, 'trace', lambda name, result, **kw: traces.append(kw)), \
                    patch.object(mc, 'memory', lambda: {'ram_free_gib': 8.0}), patch.object(mc, 'read_trace', lambda: []), \
                    patch.object(rr, 'processes', lambda: {}), patch.object(rr, 'pagefile_gib', lambda: None), \
                    patch.object(rr.shutil, 'disk_usage', lambda p, _f=free: types.SimpleNamespace(free=_f * mc.GIB)):
                rr.main()
            out.append((len(alerts), bool(alerts) and ('%d GiB margin' % margin) in alerts[0], traces[0]['below_floor']))
    return out


def expected_resource_reading_alerts_at_margin():
    return [(0, False, []), (1, True, ['disk']), (1, True, ['disk'])]


def neutralise_resource_reading_alerts_at_margin():
    # The old fixed 30 GiB floor back in the reading.
    return patch.object(lf, 'margin_gib', lambda path=None: (30.0, 'config'))


PROOFS = ['kinds_hold_their_floors', 'read_at_call_time', 'chain_names_the_step', 'shipped_floors_declared',
          'disk_footprint_plus_margin', 'disk_rule_read_at_call_time', 'resource_reading_alerts_at_margin']


def caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return 'raised %s' % type(exc).__name__


def run_all(names=None):
    done, space = [], globals()
    for name in names or PROOFS:
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
        done.append('%s (neutralised: %s)' % (name, str(broken)[:140]))
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass, no provider call: %s' % (len(done), '; '.join(done))


if __name__ == '__main__':
    status, detail = run_all(sys.argv[1:] or None)
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
