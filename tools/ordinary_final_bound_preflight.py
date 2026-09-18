"""Read-only live provider preflight for a bound launch. Launches nothing.

Reverifies against the live provider, through the allowlisted adapter only:
empty inventory, A10 capacity in us-east-1 at the authorized rate or lower, and
the prepared image still offered. Writes authorized_live_preflight.json.
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

CREDENTIAL = Path('C:/Users/secki/local/api_keys/config.py')


def main(bundle):
    base = Path(bundle).resolve()
    binding = read(base / 'authorization_binding.json')
    require(sha(base / 'execution_manifest.json') == binding['manifest_sha256'], 'Manifest differs from the binding')
    m = read(base / 'execution_manifest.json')
    provider = LambdaExperiment(CREDENTIAL)
    instances = provider.request('instances')['data']
    require(instances == [], 'Provider inventory not empty')
    types = provider.request('instance-types')['data']
    current = next((x for x in types if x['metadata']['type'] == 'gpu_1x_a10'), None)
    require(current is not None, 'gpu_1x_a10 not offered')
    rate = current['metadata']['hourly_rate']
    require(current['architecture'] == 'x86_64', 'Architecture changed')
    require('us-east-1' in current['regions'], 'No A10 capacity in us-east-1 right now')
    require(0 < rate <= m['max_hourly_rate'], 'Rate above the authorized ceiling')
    images = provider.request('images')['data']
    require(m['image'] in images, 'Prepared image no longer offered')
    receipt = dict(epoch=time.time(), instances=instances, instance=current, image=m['image'],
                   manifest_sha256=binding['manifest_sha256'], rate_authorized_ceiling=m['max_hourly_rate'], passed=True,
                   launched=False, provider_calls=['instances', 'instance-types', 'images'])
    write(base / 'authorized_live_preflight.json', receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    main(parser.parse_args().bundle)
