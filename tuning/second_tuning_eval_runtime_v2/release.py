"""Prospective release hashing/verification. No model or network operations."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPORTS = ['docs/fix/PRODUCER_DEV_GENERATION_PATH_AUDIT.md',
           'docs/fix/EVALUATION_RUNTIME_V2_IMPLEMENTATION.md']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def history():
    entries = read(HERE / 'historical_preservation.json')
    for name, expected in entries.items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or digest(path) != expected:
            raise ValueError('Historical artifact changed: ' + name)
    pilot = read(ROOT / 'docs/fix/second_tuning_canonical_pilot/RECOMPUTED_RESULTS.json')
    assert pilot['verdict'] == 'SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE'
    assert pilot['FULL_GROUPED_CV_CONTINUATION_RECOMMENDED'] is False
    for name in ('runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json',
                 'runs/second-domain-agnostic-v2/PROTECTED_ACCESS_CONSUMED.json',
                 'docs/fix/first_real_tuning_20260916/downloaded/runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json'):
        assert not (ROOT / name).exists(), 'Protected receipt consumed'
    return len(entries)


def freeze():
    destination = HERE / 'freeze.json'
    if destination.exists():
        raise ValueError('Release already frozen; no automatic replacement')
    count = history()
    tests = read(HERE / 'test_results.json')
    assert tests['passed'] and tests['tests'] == 50 and tests['real_model_generations'] == 0
    assert read(HERE / 'dry_run_evidence.json')['status'] == 'PASS'
    assert read(HERE / 'adapter_binding.json')['verified'] is True
    protocol = read(HERE / 'protocol.json')
    assert protocol['operator_authorized'] is False and protocol['cloud_authorized'] is False
    files = [p for p in HERE.iterdir() if p.is_file() and p.name != 'freeze.json']
    files += [ROOT / p for p in REPORTS]
    value = dict(name='second-tuning-eval-runtime-v2', readiness='EVALUATION_RUNTIME_V2_READY',
                 diagnosis_status='GENERATION_PATH_DIAGNOSIS_COMPLETE',
                 execution_diagnosis='TELEMETRY_OVERHEAD', output_length_diagnosis='REFUSAL_TO_SUBSTANTIVE_SHIFT',
                 diagnosis_limit='Global observer overhead established locally; exact GPU causal fraction and real token equivalence not measured',
                 source_head_before_changes='886dc78a89c8c3162c2f0e5195ca502b053117b9',
                 historical_files_preserved=count,
                 historical_pilot_verdict='SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE',
                 FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=False,
                 original_v2_sha256='bb27d49234fcc30cf02438ac0ce1c43dc690cf514aa9ebbe8d4ae4f6341aa78d',
                 cloud_authorized=False, model_execution_authorized=False, training_authorized=False,
                 protected_authorized=False, auditor_authorized=False,
                 files={p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(files)})
    with destination.open('x', encoding='utf8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')
    return verify()


def verify():
    frozen = read(HERE / 'freeze.json')
    for name, expected in frozen['files'].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or digest(path) != expected:
            raise ValueError('Runtime release changed: ' + name)
    count = history()
    return dict(status=frozen['readiness'], runtime_release_sha256=digest(HERE / 'freeze.json'),
                bound_files=len(frozen['files']), historical_files_verified=count,
                protected_receipt='UNCONSUMED', cloud_authorized=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('freeze', 'verify'))
    args = parser.parse_args()
    print(json.dumps(freeze() if args.action == 'freeze' else verify(), indent=2))
