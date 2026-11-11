"""Read the provider inventory the sealer needs, for the console's cloud mode. Launches nothing.

Three read-only requests through the allowlisted provider adapter, the same three the bound live
preflight makes (instances, instance types, images), written as `provider_inventory.json` in the
shape `tools/prepare_ordinary_final_run.py --inputs-from` reads. The credential file is located by
the controller's own `credential_path()` and read only by the adapter; nothing here prints it. A
failure is reduced to one line naming its class.

    py -3.12 tools/console_cloud_inventory.py --out output/cloud/<plan>/inputs/provider_inventory.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'scripts')]


def inventory(provider, now=None):
    """The inventory record from one adapter; `provider.request(name)` is the adapter's call."""
    now = now or datetime.now(timezone.utc)
    return dict(read_only=True, observed_at=now.isoformat(),
                instances=provider.request('instances')['data'],
                instance_types=provider.request('instance-types')['data'],
                images=provider.request('images')['data'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        from lambda_experiment_provider import LambdaExperiment
        from ordinary_final_cloud import credential_path
        record = inventory(LambdaExperiment(credential_path()))
    except Exception as error:  # one line, never the credential or its path
        # A refusal of this repository's own (the missing-credential line among them) is a fixed
        # sentence and is shown; anything else is named by its class only, as lambda_snapshot does.
        own = type(error).__name__ == 'InvalidPreparation'
        print('Provider inventory not read: %s' % (str(error) if own else type(error).__name__), flush=True)
        return 1
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(record, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print('Provider inventory read: %d instances listed, %d instance types' % (len(record['instances']),
                                                                              len(record['instance_types'])), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
