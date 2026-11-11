"""Read-only live provider preflight for a bound launch. Launches nothing.

Reverifies against the live provider, through the allowlisted adapter only:
no instance outside the loop and fewer loop instances than the limit (D-S17), a sealed instance candidate offered at its sealed rate cap or lower
(the A10 in us-east-1 first, IV.3), and the prepared image still offered. Writes
authorized_live_preflight.json.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'scripts')]
from ordinary_final_run import read, write, require, sha
from lambda_experiment_provider import LambdaExperiment
from ordinary_final_cloud import credential_path
import ordinary_final_cloud as cloud
import loop_budget_guard as guard


def sealed_type_rule(manifest):
    """The manifest's sealed type rule, read exactly as the controller reads it
    (`ordinary_final_cloud.execute`): a declared order (D-S78 item 2, D-S79) or the A10 first."""
    return manifest.get('type_rule', 'a10_first')


def main(bundle):
    base = Path(bundle).resolve()
    binding = read(base / 'authorization_binding.json')
    require(sha(base / 'execution_manifest.json') == binding['manifest_sha256'], 'Manifest differs from the binding')
    m = read(base / 'execution_manifest.json')
    provider = LambdaExperiment(credential_path())
    instances = provider.request('instances')['data']
    guard.refuse_foreign_inventory(instances)  # loop instances only, any number of them (D-S95)
    types = provider.request('instance-types')['data']
    # One reading of the free inventory under the manifest's sealed type rule, as the controller
    # applies it: a declared order takes the first offered type at its sealed rate; the A10-first
    # rule the A10 in us-east-1 if offered within its rate cap, otherwise the first admissible
    # candidate (the launch itself polls before falling back).
    candidate, region, rate, _ = guard.select_instance(lambda: types, m['instance_candidates'], m['a10_reference_rate'],
                                                       time, poll_seconds=0, type_rule=sealed_type_rule(m))
    current = next(x for x in types if x['metadata']['type'] == candidate['type'])
    # D-421 (F7): an undeclared us-east-1 bundle is refused here too, before the launch.
    seal = read(base / 'seal.json') if (base / 'seal.json').is_file() else {}
    sealed = seal.get('exposure') == 'sealed'
    copy = None if sealed else cloud.asset_copy_declaration(base, m['assets_archive']['sha256'])
    cloud.require_asset_copy_or_reason(copy, region, base, sealed)
    # F1 (D-421): standing orders 1 to 3 hold before the launch, as the controller's guard checks again.
    guard.standing_orders_refusal()
    images = provider.request('images')['data']
    require(m['image'] in images, 'Prepared image no longer offered')
    receipt = dict(epoch=time.time(), instances=instances, instance=current, image=m['image'], region=region,
                   manifest_sha256=binding['manifest_sha256'], rate_authorized_ceiling=candidate['max_hourly_rate'], passed=True,
                   launched=False, provider_calls=['instances', 'instance-types', 'images'])
    write(base / 'authorized_live_preflight.json', receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    main(parser.parse_args().bundle)
