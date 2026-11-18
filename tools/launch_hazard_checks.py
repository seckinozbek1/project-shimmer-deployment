"""Gate checks 511 to 514: the four launch hazards of open item 155 (the night of 16 to 17 November 2026).

511 (a): the seal route refuses a route S workload with no `_review_targets.json` at its top before any job is
    launched: write_request before anything is written (a folder and a test archive alike), and request_error on a
    written request whose workloads archive lacks it; a workload that holds it is written and admitted.
512 (b): the standing-order check (order 1, the launch records) still refuses when a launch record cannot be read,
    and names the record: a record folder moved or renamed while it was read is named with where it is now and the
    name to move it back to; a record whose launch.json holds no epoch is named with its restore.
513 (c): the request step reads the provider inventory again when its reading is older than the newest termination
    line of the ledgers, so a request is not refused for an instance the provider has already dropped; the fresh
    reading is the one the job carries; an inventory read after the termination is not read again; a fresh reading
    still older refuses.
514 (d): `ordinary_final_bound_cloud.py --bundle ... --batch ... --output-dir ...` is refused at argument parsing,
    before anything is read or written, with one line; either flag alone is not refused by that rule.

Each proof runs on the code as shipped (passes), with the fix neutralised (fails), and on the code again (passes).
Fixtures and stand-ins only: nothing reaches a provider."""
import io
import json
import os
import sys
import tarfile
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / 'tools', ROOT / 'tools' / 'loop', ROOT / 'scripts'):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import seal_route as sr  # noqa: E402

TARGETS = sr.TARGETS_FILE


def _write_request(tmp, prep, reuse, inputs, requests_path, private, **extra):
    return sr.write_request(tmp / 'request', 'HEAD', requests_path, reuse, inputs,
                            {'forecast_minutes': 25, 'storage_forecast_usd': 0.5}, prep=prep, private=private,
                            r_ledger=tmp / 'no_r_ledger.jsonl', refusals=[], **extra)


def _attempt(call):
    try:
        return call(), None
    except Exception as exc:
        return None, str(exc)


# ---- 511 ---------------------------------------------------------------------------------------------------------

def _set_workload(tmp, requests_path, workload):
    requests_path.write_text(json.dumps({'requests': [{'name': 'r0', 'argv': ['--workload', str(workload)]}]}),
                             encoding='utf-8')


def proof_write_request_refuses_a_workload_without_targets():
    import seal_route_checks as src
    out = {}
    for case in ('folder without', 'archive without', 'folder with', 'archive with'):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            prep, reuse, inputs, requests_path, private, _root = src.request_inputs(tmp)
            held = tmp / 'held'
            (held / 'context').mkdir(parents=True)
            (held / 'context' / 'doc.md').write_text('text\n', encoding='utf-8')
            (held / 'conventions').mkdir()
            if case.endswith('with'):
                (held / TARGETS).write_text('{"targets": ["doc.md"]}\n', encoding='utf-8')
            workload = held
            if case.startswith('archive'):
                workload = tmp / 'held.tar'
                with tarfile.open(workload, 'w') as stream:
                    stream.add(str(held), arcname='.')
            _set_workload(tmp, requests_path, workload)
            _request, refusal = _attempt(lambda: _write_request(tmp, prep, reuse, inputs, requests_path, private))
            out[case] = (refusal, (tmp / 'request').exists())
    ok = all(out[c][0] and 'r0' in out[c][0] and TARGETS in out[c][0] and not out[c][1]
             for c in ('folder without', 'archive without')) and \
        all(out[c] == (None, True) for c in ('folder with', 'archive with'))
    return ok, 'outcomes %s' % out


def proof_request_error_refuses_a_written_request_without_targets():
    import seal_route_checks as src
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        out, _request, root = src.request_fixture(tmp)
        admitted = sr.request_error(out, root)
        # The written request's workloads archive without its targets member, every digest kept true, so only the
        # targets rule can refuse it.
        archive = out / sr.WORKLOADS
        with tarfile.open(archive) as stream:
            kept = [(m, stream.extractfile(m).read() if m.isfile() else None) for m in stream.getmembers()
                    if not m.name.endswith('/' + TARGETS)]
        with tarfile.open(archive, 'w', format=tarfile.PAX_FORMAT) as stream:
            for member, data in kept:
                stream.addfile(member, io.BytesIO(data) if data is not None else None)
        request = json.loads((out / sr.REQUEST_FILE).read_text(encoding='utf-8'))
        request['files'][sr.WORKLOADS] = sr.sha(archive)
        sr.write(out / sr.REQUEST_FILE, request)
        refused = sr.request_error(out, root)
    ok = admitted is None and bool(refused) and TARGETS in refused and 'r0' in refused
    return ok, 'as written %r; without the targets member %r' % (admitted, refused)


# ---- 512 ---------------------------------------------------------------------------------------------------------

def _launch(folder, epoch=1794865134.1):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'launch.json').write_text(json.dumps(dict(epoch=epoch, instance_id=folder.name, region='us-east-1')),
                                        encoding='utf-8')


def proof_a_moved_record_is_named_with_its_restore():
    import standing_orders_check as soc
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _launch(root / 'external' / 'a' / 'one.run')
        _launch(root / 'external' / 'b' / 'request.run')
        real = soc.launch_records
        calls = []

        def listing_then_rename(where):
            found = real(where)
            if not calls:      # the folder is renamed after the walk listed it, before it is read
                os.rename(root / 'external' / 'b' / 'request.run', root / 'external' / 'b' / 'request.run.try1')
            calls.append(1)
            return found
        with patch.object(soc, 'launch_records', listing_then_rename):
            state, evidence = soc.check_image(types.SimpleNamespace(root=root))
    ok = state == 'unable' and 1 in soc.BLOCKING_UNABLE and 'external/b/request.run (' in evidence and \
        'moved or renamed' in evidence and 'now at external/b/request.run.try1' in evidence and \
        'move it back to external/b/request.run,' in evidence
    return ok, '%s: %s' % (state, evidence)


def proof_a_spoilt_record_is_named_with_its_restore():
    import standing_orders_check as soc
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _launch(root / 'external' / 'a' / 'one.run')
        spoilt = root / 'external' / 'b' / 'request.run'
        spoilt.mkdir(parents=True)
        (spoilt / 'launch.json').write_text('{"region": "us-east-1"}', encoding='utf-8')
        state, evidence = soc.check_image(types.SimpleNamespace(root=root))
    ok = state == 'unable' and 'external/b/request.run (' in evidence and 'no readable epoch' in evidence and \
        'restore' in evidence
    return ok, '%s: %s' % (state, evidence)


def old_unreadable_record(root, path, listed):
    """The neutralisation: the line before the fix, the folder alone."""
    return path.parent.relative_to(root).as_posix()


# ---- 513 ---------------------------------------------------------------------------------------------------------

BEFORE, ENDED, AFTER = '2026-11-16T21:30:00+00:00', '2026-11-16T21:59:05+00:00', '2026-11-16T22:05:00+00:00'
GONE = 'shimmer-loop-7633ea8-fd8cfbbb'


def _inventory(observed, instances):
    return dict(read_only=True, observed_at=observed, instances=[dict(name=n) for n in instances], instance_types=[],
                images=[dict(id='img', family='lambda-stack-24-04', version='1', architecture='x86_64', region='us-east-1')])


def _stale_case(observed, fresh_observed):
    import seal_route_checks as src
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        prep, reuse, inputs, requests_path, private, _root = src.request_inputs(tmp)
        (inputs / 'provider_inventory.json').write_text(json.dumps(_inventory(observed, [GONE])), encoding='utf-8')
        with (private / 'budget_ledger.jsonl').open('a', encoding='utf-8') as ledger:
            ledger.write(json.dumps(dict(event='termination', instance_name=GONE, time_utc=ENDED)) + '\n')
        seen, reads = [], []

        def budget_fields(provider, budget, now, arm='B3'):
            # The guard's rule, in small: a listed loop instance no running record names refuses.
            listed = [i['name'] for i in provider['instances'] if i['name'].startswith('shimmer-loop-')]
            sr.require(not listed, 'A loop instance no ledger records is running (%s)' % ', '.join(listed))
            seen.append(provider['observed_at'])
            return dict(arm=arm, forecast_minutes=budget['forecast_minutes'], per_run_cap_usd=1.0)
        prep.budget_fields = budget_fields

        def reread():
            reads.append(1)
            return _inventory(fresh_observed, [])
        _request, refusal = _attempt(lambda: _write_request(tmp, prep, reuse, inputs, requests_path, private,
                                                            reread=reread))
        carried = None
        if (tmp / 'request' / sr.WORKLOADS).is_file():
            with tarfile.open(tmp / 'request' / sr.WORKLOADS) as stream:
                carried = json.loads(stream.extractfile('inputs/provider_inventory.json').read())['observed_at']
        written = json.loads((inputs / 'provider_inventory.json').read_text(encoding='utf-8'))['observed_at']
    return dict(refusal=refusal, reads=len(reads), sealed_from=seen, carried=carried, written=written)


def proof_a_stale_inventory_is_read_again():
    stale = _stale_case(BEFORE, AFTER)
    ok = stale['refusal'] is None and stale['reads'] == 1 and stale['sealed_from'] == [AFTER] and \
        stale['carried'] == AFTER and stale['written'] == AFTER
    return ok, 'read before the termination: %s' % stale


def proof_a_fresh_inventory_is_not_read_again_and_a_stale_reread_refuses():
    # Read after the termination: never read again, so the instance it still lists is the guard's to judge (the
    # stand-in refuses it as listed). Read again and still older: refused before the request is written.
    fresh = _stale_case(AFTER, AFTER)
    still = _stale_case(BEFORE, BEFORE)
    ok = fresh['reads'] == 0 and bool(fresh['refusal']) and GONE in fresh['refusal'] and \
        still['reads'] == 1 and bool(still['refusal']) and 'still older than the last termination' in still['refusal']
    return ok, 'read after: %s; read again and still older: %s' % (fresh, still)


# ---- 514 ---------------------------------------------------------------------------------------------------------

def proof_batch_with_output_dir_is_refused_at_parsing():
    import ordinary_final_bound_cloud as wrapper
    out = {}
    for case, flags in (('both', ['--batch', 'B', '--output-dir', 'O']), ('batch alone', ['--batch', 'B']),
                        ('output dir alone', ['--output-dir', 'O'])):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            argv = ['--bundle', str(tmp / 'bundle'), '--ledger', str(tmp / 'ledger.jsonl'), '--purpose', 'fixture',
                    '--forecast-minutes', '25', '--storage-forecast-usd', '0.5']
            argv += [str(tmp / f) if f in ('B', 'O') else f for f in flags]
            _result, refusal = _attempt(lambda: wrapper.main(argv))
            out[case] = (refusal, sorted(p.name for p in tmp.iterdir()))
    ok = out['both'] == (wrapper.BATCH_OUTPUT_REFUSAL, []) and '\n' not in wrapper.BATCH_OUTPUT_REFUSAL and \
        all(out[c][0] != wrapper.BATCH_OUTPUT_REFUSAL for c in ('batch alone', 'output dir alone'))
    return ok, 'outcomes %s' % out


# ---- running ------------------------------------------------------------------------------------------------------

PROOFS = {
    511: [('write_request refuses a workload without the targets file', proof_write_request_refuses_a_workload_without_targets),
          ('request_error refuses a written request without it', proof_request_error_refuses_a_written_request_without_targets)],
    512: [('a moved record is named with where it is and its old name', proof_a_moved_record_is_named_with_its_restore),
          ('a spoilt record is named with its restore', proof_a_spoilt_record_is_named_with_its_restore)],
    513: [('a stale inventory is read again and carried', proof_a_stale_inventory_is_read_again),
          ('a fresh one is not; a stale re-read refuses', proof_a_fresh_inventory_is_not_read_again_and_a_stale_reread_refuses)],
    514: [('the pair is refused at parsing', proof_batch_with_output_dir_is_refused_at_parsing)],
}


def neutralisations(number):
    if number == 511:
        return [('write_request without the targets rule', lambda: patch.object(sr, 'workload_targets_error', lambda r: None)),
                ('request_error without the targets rule', lambda: patch.object(sr, 'request_targets_error', lambda f, j: None))]
    if number == 512:
        import standing_orders_check as soc
        return [('the record named by its folder alone', lambda: patch.object(soc, 'unreadable_record', old_unreadable_record))]
    if number == 513:
        return [('the inventory never read again', lambda: patch.object(sr, 'inventory_stale', lambda p, l: False))]
    import ordinary_final_bound_cloud as wrapper
    return [('the pair not refused', lambda: patch.object(wrapper, 'batch_output_refusal', lambda a: None))]


def run(proofs):
    out = {}
    for name, proof in proofs:
        try:
            out[name] = proof()
        except Exception as exc:
            out[name] = (False, '%s: %s' % (type(exc).__name__, exc))
    return all(ok for ok, _ in out.values()), out


def run_check(number):
    """('PASS' or 'FAIL', detail): every proof passes as shipped, at least one fails on each neutralised copy, and
    every proof passes again after it."""
    ok, detail = run(PROOFS[number])
    if not ok:
        return 'FAIL', '%d: %s' % (number, '; '.join('%s: %s' % (k, d) for k, (v, d) in detail.items() if not v))
    names = []
    for name, neutralise in neutralisations(number):
        with neutralise():
            still, _ = run(PROOFS[number])
        if still:
            return 'FAIL', '%d: still passes when neutralised (%s)' % (number, name)
        again, after = run(PROOFS[number])
        if not again:
            return 'FAIL', '%d: fails when restored (%s): %s' % (number, name, after)
        names.append(name)
    return 'PASS', '%d proofs, each neutralised, failed, restored, passed: %s' % (len(PROOFS[number]), '; '.join(names))


if __name__ == '__main__':
    for n in map(int, sys.argv[1:] or PROOFS):
        print(n, *run_check(n))
