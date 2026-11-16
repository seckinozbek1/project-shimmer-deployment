"""Proofs for tools/loop/working_store.py (standing order 99), check 504, on a temporary main checkout only: no
network, no provider, no instance, no real external/. Each proof is run as built (passes), neutralised (must
fail), restored (passes again).

    py -3.12 -X utf8 tools/loop/working_store_checks.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cloud_run_common import no_window  # noqa: E402  (HIDDEN-A)
import step_cost as sc  # noqa: E402
import working_store as ws  # noqa: E402

KNOWN = 'a' * 64
LIMITS = dict(step_preapproved_usd=5.0, remaining_limit_usd=140.0, remaining_baseline_usd=197.0,
              remaining_ceiling_usd=337.0, decision='D-708')
INVENTORY = dict(read_only=True, observed_at='2026-11-16T18:10:15+00:00', instances=[], images=[],
                 instance_types=[dict(metadata=dict(type='gpu_1x_a10', hourly_rate=1.29), regions=['us-east-1'])])
RECORD = dict(usd_per_gb_month=0.2)
MB = 10 ** 6


def config(**over):
    value = ws.read_config()           # the repository's own declaration, its fixtures' digest added
    value = copy.deepcopy(value)
    value['on_store']['digests'] = [dict(sha256=KNOWN, source='fixture')]
    value['lambda_reads'] = []
    value.update(over)
    return value


def write(path, nbytes, text=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is not None:
        path.write_text(text, encoding='utf-8')
    else:
        path.write_bytes(b'x' * nbytes)


def build(base):
    """A main checkout with: two answer keys, role B's held items, a credential-like name, plain data, an asset
    archive the store holds and one it does not."""
    main = Path(base) / 'main'
    ext = main / 'external'
    write(ext / 's05' / 'D-S45' / 'build' / 'b1' / 'answer_key.json', 0, '{"never": "opened"}')
    write(ext / 's05' / 'D-S45' / 'build' / 'b1' / 'items.json', 3 * MB)
    write(ext / 's05' / 'GATE' / 'held_D-S100' / 'items.json', 2 * MB)
    write(ext / 's05' / 'GATE' / 'claim_set_ids.json', 1 * MB)
    write(ext / 'foo' / '.env', 0, 'NOT_A_KEY=placeholder')
    write(ext / 'foo' / 'data.json', 6 * MB)
    write(ext / 's05' / 'P1' / 'P3' / 'assets.tar', 60 * MB)
    write(ext / 's05' / 'P1' / 'P3' / 'asset_verification.json', 0, json.dumps(dict(archive_sha256=KNOWN)))
    write(ext / 's05' / 'P1' / 'P4' / 'assets.tar', 12 * MB)
    write(ext / 's05' / 'P1' / 'P4' / 'asset_verification.json', 0, json.dumps(dict(archive_sha256='b' * 64)))
    return main


def plan(main, cfg=None):
    return ws.plan(main, cfg or config(), INVENTORY, RECORD, LIMITS)


def proof_stay_local_files_are_never_sent(base):
    """Answer keys (by name, never opened), role B's held items and a credential-like name stay local: they are
    in no part's upload list and no command, while plain data beside them is sent."""
    main = build(base)
    result = plan(main)
    sent = {c for r in result['parts'].values() for c in r['candidates']}
    for local in ('external/s05/D-S45/build/b1/answer_key.json', 'external/s05/GATE/held_D-S100/items.json',
                  'external/foo/.env'):
        assert local not in sent, local
    for kept in ('external/s05/D-S45/build/b1/items.json', 'external/s05/GATE/claim_set_ids.json',
                 'external/foo/data.json'):
        assert kept in sent, kept
    assert result['parts']['external/s05/D-S45']['local_files'] == 1
    assert result['parts']['external/s05/GATE']['local_bytes'] == 2 * MB
    assert not any('answer_key' in line or 'held_D-S100' in line for line in result['commands']), result['commands']


def proof_an_archive_the_store_holds_is_not_sent(base):
    """An asset archive whose recorded digest the store holds is counted on the store; one with any other
    digest is a candidate like any file."""
    main = build(base)
    p1 = plan(main)['parts']['external/s05/P1']
    assert p1['on_store_bytes'] == 60 * MB, p1
    assert 'external/s05/P1/P4/assets.tar' in p1['candidates'] and 'external/s05/P1/P3/assets.tar' not in p1['candidates']


def proof_the_move_has_two_figures(base):
    """The move is priced by the estimator: without the saving measure it sends the on-store archive again
    (60 MB more), with asset_copy only the candidates; the upload minutes are bytes over the measured rate."""
    main = build(base)
    result = plan(main)
    candidate = sum(r['candidate_bytes'] for r in result['parts'].values())
    rate = config()['upload']['mb_per_second'] * MB
    move = result['move']
    boot = config()['launch']['boot_minutes']
    assert abs(move['without']['minutes'] - (boot + round((candidate + 60 * MB) / rate / 60, 2))) < 0.02, move['without']
    assert abs(move['with_measures']['minutes'] - (boot + round(candidate / rate / 60, 2))) < 0.02, move['with_measures']
    assert move['without']['usd'] > move['with_measures']['usd'], move
    assert [m['name'] for m in move['measures']] == ['asset_copy'], move['measures']
    text = '\n'.join(ws.report(result))
    assert 'Without the saving measures' in text and 'With the saving measures' in text, text


def proof_a_part_read_again_is_priced_per_launch(base):
    """A part declared as read by 4 launches costs 4 sends without the warm file system and none with it (its
    storage added); an unknown part, or one holding only stay-local files, is refused."""
    main = build(base)
    result = plan(main, config(lambda_reads=[dict(part='external/foo', launches=4, source='fixture')]))
    read = result['reads'][0]
    one = round(6 * MB / (config()['upload']['mb_per_second'] * MB) / 60, 2)
    assert abs(read['without']['minutes'] - 4 * one) < 0.02 and read['with_measures']['minutes'] == 0, read
    assert read['with_measures']['storage_usd'] > 0, read
    for bad, needle in ((dict(part='external/nowhere', launches=1, source='x'), 'did not find'),
                        (dict(part='external/foo', launches=0, source='x'), 'launches and a source')):
        try:
            plan(main, config(lambda_reads=[bad]))
        except ws.WorkingStoreError as exc:
            assert needle in str(exc), str(exc)
        else:
            raise AssertionError('not refused: %s' % bad)


def proof_the_plan_is_a_dry_run(base):
    """The plan starts no process and opens no connection, and the command has no execute switch."""
    main = build(base)
    calls = []

    def refuse_process(*a, **k):
        calls.append(('process', a[:1]))
        raise OSError('refused by check 504')

    def refuse_connection(*a, **k):
        calls.append(('connection', a[:1]))
        raise OSError('refused by check 504')

    saved = (subprocess.run, subprocess.Popen, socket.create_connection)
    subprocess.run, subprocess.Popen, socket.create_connection = refuse_process, refuse_process, refuse_connection
    try:
        plan(main)
    finally:
        subprocess.run, subprocess.Popen, socket.create_connection = saved
    assert not calls, calls
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            ws.main(['--execute'])
        except SystemExit as exc:
            assert exc.code == 2, exc.code
        else:
            raise AssertionError('an execute switch exists')


def patch_attr(owner, name, value):
    def apply():
        saved = getattr(owner, name)
        setattr(owner, name, value)
        return lambda: setattr(owner, name, saved)
    return apply


_move_step, _read_step, _plan = ws.move_step, ws.read_step, ws.plan


def _move_without_measures(parts, cfg):
    step = _move_step(parts, cfg)
    step['measures'] = []
    return step


def _read_once(parts, entry, cfg):
    step = _read_step(parts, entry, cfg)
    step['launches'] = 1
    return step


def _plan_that_executes(*a, **k):
    result = _plan(*a, **k)
    subprocess.run(['ssh', '<instance>', 'true'], creationflags=no_window())  # HIDDEN-A even here (check 292)
    return result


NEUTRALISE = {
    'proof_stay_local_files_are_never_sent': patch_attr(ws, 'stays_local', lambda logical, rules: None),
    'proof_an_archive_the_store_holds_is_not_sent': patch_attr(ws, 'on_store', lambda disk, logical, block: False),
    'proof_the_move_has_two_figures': patch_attr(ws, 'move_step', _move_without_measures),
    'proof_a_part_read_again_is_priced_per_launch': patch_attr(ws, 'read_step', _read_once),
    'proof_the_plan_is_a_dry_run': patch_attr(ws, 'plan', _plan_that_executes),
}
PROOFS = [proof_stay_local_files_are_never_sent, proof_an_archive_the_store_holds_is_not_sent,
          proof_the_move_has_two_figures, proof_a_part_read_again_is_priced_per_launch, proof_the_plan_is_a_dry_run]


def run(proof):
    with tempfile.TemporaryDirectory() as base:
        proof(base)


def neutralised(proof):
    restore = NEUTRALISE[proof.__name__]()
    try:
        run(proof)
    except Exception:
        return True
    finally:
        restore()
    return False


def check():
    passed = []
    for proof in PROOFS:
        try:
            run(proof)
            if not neutralised(proof):
                return 'FAIL', proof.__name__ + ' still passes when neutralised'
            run(proof)
        except Exception as exc:
            return 'FAIL', '%s: %s %s' % (proof.__name__, type(exc).__name__, str(exc)[:200])
        passed.append(proof.__name__)
    return 'PASS', ('%d proofs, each neutralise, fail, restore, pass, on a temporary main checkout: answer keys (by '
                    'name), held-out items and credential-like names never in an upload list or command; an archive '
                    'the store holds not sent; the move priced by the estimator without and with asset_copy; a part '
                    'read again priced per launch and with the warm file system; no process, no connection and no '
                    'execute switch' % len(passed))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
