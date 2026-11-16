"""Gate checks 505 and 506: the sealed image is the launch region's (16 November 2026, three seal-route launches
refused at launch_instance as an opaque transport failure: the sealed id was provider['images'][0], us-east-2's,
for a us-east-1 launch).

505: the sealer (prepare_ordinary_final_run.prepare) and the seal route (seal_route.write_request) seal the image
of the launch region through the one helper, prepare_ordinary_final_run.region_image, on fixture inventories whose
first image is another region's; a region that lists no image of that family and version is refused.
506: the controller (ordinary_final_cloud.execute) refuses a sealed image of another region before any launch call
(no instance, no ledger launch_intent or launch line), and the provider adapter's transport refusal carries the HTTP
status, digits only, never the response body.

Each proof is run on the code as shipped (passes), on a neutralised copy (fails), and on the code again (passes).
Fixtures and mocks only: nothing reaches a provider."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / 'tools', ROOT / 'scripts'):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import lambda_experiment_provider as adapter  # noqa: E402
import ordinary_final_cloud as controller  # noqa: E402
import prepare_ordinary_final_run as sealer  # noqa: E402

FAMILY, VERSION = 'lambda-stack-24-04', '24.4.5-4040'
LAUNCH_REGION = 'us-east-1'
OTHER_ID = '517e9546' + '0' * 24
LAUNCH_ID = 'ff79a459' + '1' * 24


def image(identifier, region, family=FAMILY, version=VERSION):
    return dict(id=identifier, family=family, version=version, architecture='x86_64', region=region)


# The 21:10 shape: the provider's first entry is another region's id of the same family and version.
IMAGES = [image(OTHER_ID, 'us-east-2'), image('2' * 32, 'us-east-2', 'gpu-base-24-04'),
          image(LAUNCH_ID, LAUNCH_REGION), image('3' * 32, LAUNCH_REGION, 'gpu-base-24-04')]


def old_rule(images, region):
    """The neutralisation: the rule before the fix, the provider's first entry whatever its region."""
    return dict(images[0])


# ---- 505 ---------------------------------------------------------------------------------------------------------

def proof_helper():
    chosen = sealer.region_image(json.loads(json.dumps(IMAGES)), LAUNCH_REGION)
    refusal = None
    try:
        sealer.region_image([image(OTHER_ID, 'us-east-2'), image('3' * 32, LAUNCH_REGION, 'gpu-base-24-04')], LAUNCH_REGION)
    except Exception as exc:  # the clear refusal for a region without the family and version
        refusal = str(exc)
    ok = (chosen['id'], chosen['region']) == (LAUNCH_ID, LAUNCH_REGION) and bool(refusal) and \
        'No image of family %s version %s' % (FAMILY, VERSION) in refusal and LAUNCH_REGION in refusal
    return ok, 'helper chose %s in %s; refusal %r' % (chosen['id'][:8], chosen['region'], refusal)


def proof_sealer():
    import multi_round_launch_checks as mr
    import ordinary_final_controller_checks as cc
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mr.write_workload(root / 'workload', mr.live_case())
        inputs = root / 'inputs'
        inputs.mkdir()
        (inputs / 'runtime.candidate.lock').write_text('', encoding='utf-8')
        (inputs / 'provider_inventory.json').write_text(json.dumps(dict(
            instances=[], instance_types=[cc.A10_TYPE], images=IMAGES, observed_at='fixture')), encoding='utf-8')
        ledger = root / 'ledger' / 'budget_ledger.jsonl'
        cc.open_ledger(ledger)
        with mr.sealing_stand_ins():
            sealer.prepare(root / 'bundle', budget=dict(ledgers=[ledger], forecast_minutes=cc.FORECAST_MINUTES,
                                                        storage_forecast_usd=cc.STORAGE_USD, reaped=[ledger],
                                                        uncompared=True),
                           workload=root / 'workload', inputs_from=inputs, now_epoch=cc.FakeClock().now)
        manifest = json.loads((root / 'bundle' / 'execution_manifest.json').read_text(encoding='utf-8'))
    sealed = manifest['image']
    ok = (sealed['id'], sealed['region'], manifest['region']) == (LAUNCH_ID, LAUNCH_REGION, LAUNCH_REGION)
    return ok, 'sealer sealed %s of %s for a %s launch' % (sealed['id'][:8], sealed['region'], manifest['region'])


def proof_seal_route():
    import seal_route
    import seal_route_checks as src
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        prep, reuse, inputs, requests_path, private, _root = src.request_inputs(tmp)
        (inputs / 'provider_inventory.json').write_text(json.dumps(dict(images=IMAGES, instance_types=[])),
                                                        encoding='utf-8')
        request = seal_route.write_request(tmp / 'request', 'HEAD', requests_path, reuse, inputs,
                                           {'forecast_minutes': 25, 'storage_forecast_usd': 0.5}, prep=prep,
                                           private=private, r_ledger=tmp / 'no_r_ledger.jsonl', refusals=[])
    sealed = request['image']
    ok = (sealed['id'], sealed['region']) == (LAUNCH_ID, LAUNCH_REGION)
    return ok, 'seal route sealed %s of %s' % (sealed['id'][:8], sealed['region'])


# ---- 506 ---------------------------------------------------------------------------------------------------------

def proof_launch_refusal():
    """The controller on a bundle sealed with us-east-2's image, the live inventory listing both regions' entries
    (so the old `m['image'] in images` check passed): refused before any launch, intent or launch line."""
    import ordinary_final_controller_checks as cc

    class BothRegions(cc.FakeProvider):
        def request(self, endpoint, body=None, method=None):
            if endpoint == 'images':
                return {'data': [dict(cc.IMAGE, id=OTHER_ID, region='us-east-2'), dict(cc.IMAGE)]}
            return super().request(endpoint, body, method)

    case = cc.ControllerChecks('test_poll_outcome_classifies_connection_failure_as_unreachable_not_a_result')
    case.setUp()
    try:
        case.remanifest(image=dict(cc.IMAGE, id=OTHER_ID, region='us-east-2'))
        message = None
        try:
            _t, _c, failure = case.execute(provider=BothRegions)
            message = failure and failure.get('message')
        except Exception as exc:
            message = str(exc)
        launches = (cc.FakeProvider.state or {}).get('launches', 0)
        events = [r.get('event') for r in cc.ledger_rows(case.ledger)]
    finally:
        case.doCleanups()
    ok = bool(message) and 'image ids are per region' in message and 'us-east-2' in message and \
        LAUNCH_REGION in message and launches == 0 and not any(e in ('launch_intent', 'launch') for e in events)
    return ok, 'refusal %r; launches %s; ledger events %s' % (message, launches, events)


# The adapter module the status proof runs on: the shipped one, or its neutralised copy. Every stand-in (curl,
# which, the credential reader) is patched into this same module, whose globals its class reads, so no copy of the
# adapter can ever reach the real curl.
ADAPTER = [adapter]


def proof_http_status():
    """A refused provider request names its HTTP status (digits only), never its body; a reply with no status
    line says nothing more."""
    module = ADAPTER[0]
    body = 'region us-east-1 has no image ' + OTHER_ID
    messages = []
    for stdout in (json.dumps(dict(error=dict(message=body))) + '\n400', 'no status line'):
        process = SimpleNamespace(run=lambda *a, **k: SimpleNamespace(returncode=0, stdout=stdout, stderr=''))
        which = SimpleNamespace(which=lambda name: 'curl-fixture')
        with patch.object(module, 'subprocess', process), patch.object(module, 'shutil', which), \
                patch.object(module, 'load_credential', lambda path: 'fixture-placeholder'):
            try:
                module.LambdaExperiment(None).request('images')
                messages.append(None)
            except Exception as exc:
                messages.append(str(exc))
    ok = messages == ['provider experiment request failed during transport (HTTP 400)',
                      'provider experiment request failed during transport'] and \
        not any(OTHER_ID in (m or '') or 'region' in (m or '') for m in messages)
    return ok, 'messages %s' % messages


def neutralised_adapter():
    """The adapter loaded from its own source with the status suffix removed."""
    import types
    source = Path(adapter.__file__).read_text(encoding='utf-8')
    line = "            code=' (HTTP %s)'%status if isinstance(status,str) and re.fullmatch('[0-9]{3}',status) else ''"
    if source.count(line) != 1:
        raise RuntimeError('the status line to neutralise is not found once in the adapter')
    module = types.ModuleType('lambda_experiment_provider_neutralised')
    module.__file__ = adapter.__file__
    exec(compile(source.replace(line, "            code=''"), adapter.__file__, 'exec'), module.__dict__)
    return module


# ---- running ------------------------------------------------------------------------------------------------------

PROOFS = {
    505: [('the helper picks the launch region\'s image', proof_helper),
          ('the sealer seals it', proof_sealer),
          ('the seal route seals it', proof_seal_route)],
    506: [('the controller refuses another region\'s image before any launch', proof_launch_refusal),
          ('the adapter names the HTTP status, digits only', proof_http_status)],
}


def neutralisations(number):
    if number == 505:
        return [('region_image back to the first listed image', lambda: patch.object(sealer, 'region_image', old_rule))]
    return [('the launch region check removed', lambda: patch.object(controller, 'image_region_refusal',
                                                                      lambda image, region: None)),
            ('the status suffix removed', lambda: patch.dict(globals(), ADAPTER=[neutralised_adapter()]))]


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
