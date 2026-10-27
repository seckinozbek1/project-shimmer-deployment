"""Read-only live provider preflight for a bound launch. Launches nothing.

Reverifies against the live provider, through the allowlisted adapter only:
empty inventory, a sealed instance candidate offered at its sealed rate cap or lower
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
import loop_budget_guard as guard


def main(bundle):
    base = Path(bundle).resolve()
    binding = read(base / 'authorization_binding.json')
    require(sha(base / 'execution_manifest.json') == binding['manifest_sha256'], 'Manifest differs from the binding')
    m = read(base / 'execution_manifest.json')
    provider = LambdaExperiment(credential_path())
    instances = provider.request('instances')['data']
    require(instances == [], 'Provider inventory not empty')
    types = provider.request('instance-types')['data']
    # One reading of the free inventory, the IV.3 type rule over the sealed candidates: the
    # A10 in us-east-1 if offered within its rate cap, otherwise the first admissible
    # candidate (the launch itself polls before falling back).
    candidate, region, rate, _ = guard.select_instance(lambda: types, m['instance_candidates'], m['a10_reference_rate'],
                                                       time, poll_seconds=0)
    current = next(x for x in types if x['metadata']['type'] == candidate['type'])
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
