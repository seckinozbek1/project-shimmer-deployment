"""Read-only Lambda snapshot for the loop: running instances and live single-GPU prices.

Used at S0 and at every stage boundary (H4): it lists running instances, marks which carry
the loop prefix, and reads ``metadata.hourly_rate`` per instance type from the provider
adapter's ``instance-types`` projection. It can neither launch nor terminate. The
credential is found by the existing resolver and is never printed; any provider error is
reduced to its class name. Loop machinery, not product code.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'scripts'))

PREFIX = 'shimmer-loop-'


def main():
    out = {'time_utc': datetime.now(timezone.utc).isoformat()}
    try:
        from agent_wrapper import resolve_config_path
        from lambda_experiment_provider import LambdaExperiment
        from cloud_run_watchdog import load_credential
        path = resolve_config_path()
        out['credential_file_resolved'] = path is not None
        if path is None:
            print(json.dumps(out, indent=1))
            return 1
        out['credential_loaded'] = bool(load_credential(str(path)))
        provider = LambdaExperiment(str(path))
        instances = provider.request('instances')['data']
        out['instances'] = [{'name': i.get('name'), 'status': i.get('status'), 'type': i.get('type'),
                             'region': i.get('region'), 'loop_instance': str(i.get('name') or '').startswith(PREFIX)}
                            for i in instances]
        types = provider.request('instance-types')['data']
        out['instance_types'] = sorted(
            ({'type': t['metadata'].get('type'), 'hourly_rate': t['metadata'].get('hourly_rate'),
              'gpu': t['metadata'].get('gpu_type'), 'regions_with_capacity': t['regions']} for t in types),
            key=lambda t: (t['hourly_rate'] or 0))
        code = 0
    except Exception as exc:
        out['error'] = type(exc).__name__ + ': ' + (str(exc) if type(exc).__name__ == 'InvalidPreparation' else '')
        code = 1
    print(json.dumps(out, indent=1))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
