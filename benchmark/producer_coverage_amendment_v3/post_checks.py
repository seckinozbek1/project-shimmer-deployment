"""Deferred post-phase integrity checks. Importing this module reads no data."""
import importlib.util
import json

import access_guard

ACCEPTANCE_SHA256 = '8b70b096b128183707b2cc77c7577efebc8a5232336316a498f133306e3495da'


def require_post():
    guard = access_guard._default()
    if not guard.installed or not guard.authorized:
        raise PermissionError('Installed, authorized V3 guard required before post-phase reads')
    return guard.verify_post_phase()


def load_source(name, path):
    require_post()
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run():
    binding = require_post()
    import semantics as s
    def demand(condition, message):
        if not condition:
            raise ValueError(message)
    def hashes(root, manifest_name, member=None):
        require_post()
        manifest = s.read(root / manifest_name)
        values = manifest[member] if member else manifest
        demand(isinstance(values, dict) and bool(values), 'Missing historical hash entries')
        for relative, digest in values.items():
            path = (root / relative).resolve()
            demand(path.is_relative_to(root.resolve()), 'Historical manifest path escapes release')
            demand(s.digest(path.read_bytes()) == digest, 'Historical evidence drift: ' + str(path))
        return len(values)
    frozen = {}
    for name in ('machine_adjudication_v1', 'machine_adjudication_v2', 'producer_coverage_amendment_v1', 'producer_coverage_amendment_v2'):
        frozen[name] = hashes(s.ROOT / 'benchmark' / name, 'release_freeze.json', 'hashes')
    frozen['historical_contract_ab'] = hashes(s.ROOT / 'docs/fix/contract_model_ab_20260915', 'ARTIFACT_HASHES.json')
    registration_root = s.ROOT / 'benchmark/first_tuning_experiment_v1'
    frozen['first_tuning_experiment_v1'] = hashes(registration_root, 'freeze.json', 'hashes')
    acceptance_path = registration_root / 'acceptance_registration.json'
    demand(s.digest(acceptance_path.read_bytes()) == ACCEPTANCE_SHA256, 'Frozen acceptance registration hash changed')
    acceptance = s.read(acceptance_path)
    demand(len(acceptance['criteria']) == 27 and len({c['id'] for c in acceptance['criteria']}) == 27,
           'Acceptance must preserve exactly 27 independent criteria')
    limits = acceptance['catastrophic_limits']
    demand(len(limits) == 6, 'Acceptance must preserve six catastrophic limits')
    # Exact historical registration hash above binds every limit to its original zero value.
    demand(acceptance['derived_hard_gate']['id'] == 'R07'
           and acceptance['derived_hard_gate']['operator'] == '=='
           and acceptance['derived_hard_gate']['value'] == 0, 'Derived catastrophic zero gate changed')
    access = s.ROOT / 'benchmark/machine_adjudication_v2/machine_adjudicated_training_access_v2'
    auditors = {}
    for split, expected in [('train', 46), ('dev', 24)]:
        rows = s.read(access / (split + '.json'))
        auditors[split] = sum(row['role'] == 'auditor' for row in rows)
        demand(auditors[split] == expected, 'Preserved auditor count differs')
    r06 = load_source('v3_preserved_r06', s.ROOT / 'benchmark/machine_adjudication_v1/r06.py')
    population = s.read(s.ROOT / 'benchmark/machine_adjudication_v1/post_freeze/r06_population.json')['eligible_evaluation_metadata']
    demand(len(population) == 114 and len({r['example_id'] for r in population}) == 114,
           'R06 must preserve exactly 114 unique evaluation examples')
    demand(all(r06.non_train(row) for row in population), 'TRAIN leaked into R06 population')
    # Independently rebuild the exact eligible IDs from the frozen registered cohort.
    cohort_ids = set(s.read(registration_root / 'cohort.json')['ids'])
    authored = s.read(s.ROOT / 'benchmark/task_semantics/seed.json') + s.read(s.ROOT / 'benchmark/task_semantics_v2/extension.json')
    expected_rows = [row for row in authored if row['example_id'] in cohort_ids and r06.non_train(row)]
    demand({row['example_id'] for row in expected_rows} == {row['example_id'] for row in population},
           'R06 exact registered evaluation ID population changed')
    expected_meta = {row['example_id']: (row['split'], row['document_family']) for row in expected_rows}
    demand(all(expected_meta[row['example_id']] == (row['split'], row['document_family']) for row in population),
           'R06 split or family metadata changed')
    scores = [dict(example_id=row['example_id'], accepted_outcome=True) for row in population]
    injection = [dict(example_id='v3-synthetic-train-' + str(i), split='train', document_family='v3-synthetic-train') for i in range(32)]
    extra_scores = [dict(example_id=row['example_id'], accepted_outcome=False) for row in injection]
    ids = [row['example_id'] for row in population]
    baseline = r06.family_metric(scores, population, ids)
    def assert_excluded():
        demand(r06.family_metric(scores + extra_scores, population + injection,
                                 ids + [row['example_id'] for row in injection]) == baseline,
               'R06 TRAIN injection changed evaluation')
    assert_excluded()
    original = r06.non_train
    r06.non_train = lambda row: True
    try:
        try:
            assert_excluded()
        except ValueError:
            effect_failed = True
        else:
            effect_failed = False
    finally:
        r06.non_train = original
    demand(effect_failed, 'R06 TRAIN exclusion effect proof failed to detect neutralization')
    assert_excluded()
    require_post()
    report = dict(pre_gold_commit=binding['commit'], frozen_files=frozen, preserved_auditor=auditors,
                  r06_exact_non_train_population=114, r06_train_exclusion_effect=True,
                  registered_criteria=27, catastrophic_zero_limits=6,
                  evidence_kind='training_label_curation_evidence', use='curation_only',
                  training_authorized=False, final_model_acceptance=False)
    s.write(s.HERE / 'post_freeze/historical_integrity.json', report)
    return report


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
