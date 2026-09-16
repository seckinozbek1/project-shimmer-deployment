"""Post-termination V3 verification from durable raw evidence; no model execution."""
import ast
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/fix/producer_tuning_v3_run'
V3 = ROOT / 'tuning/producer_v3'
RT = ROOT / 'tuning/second_tuning_eval_runtime_v2_1'
os.environ.update(USE_TORCH='0', USE_TF='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
sys.path.insert(0, str(RT))
import eval_runtime as ev
sys.path.insert(0, str(ROOT / 'tuning/second_tuning_eval_runtime_v2'))
import audit
sys.path.insert(0, str(V3))
import selection
from cloud_run_common import credential_locations
r = audit.frozen


def read(p):
    return json.loads(Path(p).read_text(encoding='utf8'))


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding='utf8').splitlines() if x.strip()]


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(name, value):
    r.write(BASE / name, value)


def rate(values):
    return sum(x['output_tokens'] for x in values) / sum(x['generation_seconds'] for x in values)


def main():
    termination = read(BASE / 'TERMINATION_VERIFIED.json')
    assert read(BASE / 'instances_after.json') == []
    assert read(BASE / 'final_inventory_confirmation.json')['zero_billable_resources']
    assert all(read(BASE / 'cleanup.json')[k] for k in ('temporary_ssh_removed', 'local_key_material_removed'))
    assert sha(BASE / 'evidence.tar.gz') == read(BASE / 'collection_integrity.json')['sha256']
    # The frozen verifier runs with its own metadata-only protected/weight guard.
    verified = subprocess.run([sys.executable, '-B', str(V3 / 'release.py')], cwd=ROOT, capture_output=True, check=True)
    (BASE / 'release_post_run.log').write_bytes(verified.stdout + verified.stderr)
    preservation = json.loads(verified.stdout)
    data = BASE / 'downloaded'
    out = data / 'evidence'
    manifest = read(BASE / 'manifest.json')
    execution = read(BASE / 'execution_manifest.json')
    assert read(data / 'execution_manifest.json') == execution
    for p in (data / 'tools').rglob('*.py'):
        assert sha(p) == execution['files'][p.relative_to(data).as_posix()]
    for p in (data / 'tuning').rglob('*'):
        if p.is_file():
            assert sha(p) == sha(ROOT / p.relative_to(data))
    assert read(data / 'training_authorization.json') == read(BASE / 'training_authorization.json')
    assert sha(V3 / 'freeze.json') == '68afb77a9a5ff7c9360075c2699e6cb1d4cc57e1828728496a6648c49a3b7850'
    assert sha(V3 / 'dataset.json') == 'b036707820a1851e94432319cc340cafec10a1b6093fab39b573cc4a47b9ecf0'
    assert sha(RT / 'freeze.json') == '8d1fd41d1ab059e47b1297c1c39cd29711acd8fa5446a60780f9a97faef1d1fa'
    spec = read(V3 / 'experiment.json')
    split = read(V3 / 'split.json')
    plan = read(V3 / 'execution_plan.json')
    protocol = read(V3 / 'evaluation_protocol.json')
    prepared = read(V3 / 'prepared_dev.json')
    ev.validate_records(prepared, protocol)
    prepared_by = {x['example_id']: x for x in prepared}
    gold = {x['example_id']: x for x in read(V3 / 'dataset.json')}
    assert len(gold) == 420 and all(x['role'] == 'producer' for x in gold.values())
    assert len(split['train']) == 336 and len(split['validation']) == 84
    assert not set(split['train']) & set(split['validation'])
    assert not {gold[i]['leakage_group'] for i in split['train']} & {gold[i]['leakage_group'] for i in split['validation']}
    assert read(out / 'preflight.json')['passed']
    assert read(out / 'acquisition.json')['files'] == dict(spec['asset_hashes'], **spec['base_weight_hashes'])
    init = read(out / 'initialization.json')
    assert init['fresh_lora'] and not init['old_adapter_loaded'] and init['lora_B_all_zero'] and init['seed'] == 7
    identities = {}
    for step in (0, 84, 168):
        folder = out / f'checkpoint-{step}'
        identity = read(folder / 'identity.json')
        for name, expected in identity['files'].items():
            assert sha(folder / name) == expected
        cfg = read(folder / 'adapter_config.json')
        for key, value in spec['lora'].items():
            assert (set(cfg[key]) == set(value)) if key == 'target_modules' else (cfg[key] == value)
        assert cfg['base_model_name_or_path'] == spec['model_id'] and cfg['revision'] == spec['revision']
        identities[str(step)] = identity
    assert len({x['files']['adapter_model.safetensors'] for x in identities.values()}) == 3
    assert init['adapter'] == identities['0']
    # Inspect the new initialization tensors only; never open any historical adapter.
    from safetensors import safe_open
    with safe_open(str(out / 'checkpoint-0/adapter_model.safetensors'), framework='numpy') as f:
        b_names = [k for k in f.keys() if 'lora_B' in k]
        assert b_names and all(not f.get_tensor(k).any() for k in b_names)
        assert sum(f.get_tensor(k).size for k in f.keys()) == 20185088
    training = rows(out / 'training.jsonl')
    assert len(training) == 168
    scheduled = plan['optimizer_schedule']
    assert len(scheduled) == 168
    seen = Counter()
    wall = 0.
    for i, (actual, expected) in enumerate(zip(training, scheduled), 1):
        assert actual['step'] == expected['step'] == i and expected['loss_divisor'] == 4
        assert actual['example_ids'] == expected['example_ids'] and len(actual['example_ids']) == 4
        assert actual['epoch'] == expected['epoch'] and actual['examples_processed'] == i * 4
        assert all(x in split['train'] and x not in split['validation'] for x in actual['example_ids'])
        seen.update(actual['example_ids'])
        lr = lambda s: 1e-4 * min(s + 1, max(0., (168 - s) / 167))
        assert math.isclose(actual['learning_rate'], lr(i - 1), rel_tol=1e-12)
        assert math.isclose(actual['next_learning_rate'], lr(i), rel_tol=1e-12, abs_tol=1e-15)
        assert math.isfinite(actual['loss']) and actual['step_seconds'] > 0
        wall += actual['step_seconds']
        assert math.isclose(wall, actual['training_seconds'], rel_tol=1e-12)
    assert seen == Counter({x: 2 for x in split['train']})
    optimizer_receipt = read(out / 'optimizer_config.json')
    assert optimizer_receipt['schedule'] == scheduled and optimizer_receipt['training'] == spec['training']
    # Execute only the frozen pure control checker, avoiding model or training imports.
    tree = ast.parse((V3 / 'runtime_binding.py').read_text())
    nodes = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'optimized_control_gate']
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<frozen control checker>', 'exec'), namespace)
    tok = r.old.tokenizer('producer')
    all_described = {}
    checkpoints = []
    results = {}
    raw_count = 0
    for step in (84, 168):
        folder = out / f'checkpoint-{step}'
        identity = identities[str(step)]
        context = read(folder / 'context_preflight.json')
        assert context['passed'] and context['state_restored'] and context['generation_calls'] == 0
        state = read(folder / 'state_restoration.json')
        assert state['passed'] and state['before'] == state['after']
        assert state['rng_sha256'] == state['restored_rng_sha256']
        assert state['before']['completed_updates'] == step
        cache = read(folder / 'cache_admission.json')
        assert cache['passed'] and not cache['tracing']
        assert ev.cache_effect_gate(dict(zip(('reference', 'optimized'), cache['optimized_passes'])))
        def verify_set(label, expected_ids):
            nonlocal raw_count
            raw = rows(folder / (label + '.jsonl'))
            scored = read(folder / (label + '_scored.json'))
            assert [x['example_id'] for x in raw] == expected_ids and len(raw) == len(scored)
            for item, saved in zip(raw, scored):
                assert item == {k: v for k, v in saved.items() if k != 'metrics'}
                assert item['role'] == 'producer' and item['split'] == 'canonical' and item['checkpoint'] == step
                assert item['runtime'] == 'second-tuning-eval-runtime-v2_1' and item['adapter'] == identity
                # V3 binds the base once through acquisition + frozen experiment;
                # the low-level V2.1 sink does not repeat it in each raw row.
                assert item['experiment'] == 'producer-targeted-v3'
                source = prepared_by[item['example_id']]
                for key in ('prompt', 'input_ids', 'attention_mask'):
                    assert item[key] == source[key]
                assert item['prompt_sha256'] == hashlib.sha256(source['prompt'].encode()).hexdigest()
                assert item['input_ids_sha256'] == ev.digest(source['input_ids'])
                ids = item['output_token_ids']
                assert len(ids) == item['output_tokens'] and 0 < len(ids) <= 288
                assert tok.decode(ids, skip_special_tokens=True) == item['raw_output']
                assert tok.decode(ids, skip_special_tokens=False) == item['raw_output_with_special_tokens']
                eos = ids[-1] == 151645
                assert item['stop_reason'] == ('eos' if eos else 'length') and item['truncated'] == (not eos)
                assert math.isfinite(item['generation_seconds']) and item['generation_seconds'] > 0
                score = r.score(gold[item['example_id']], item['raw_output'], truncated=not eos)
                assert score == saved['metrics']
                item['metrics'] = score
            raw_count += len(raw)
            return raw
        for label in ('cache_1', 'cache_2'):
            verify_set(label, protocol['control_ids'][:1])
        first = verify_set('controls_1', protocol['control_ids'])
        second = verify_set('controls_2', protocol['control_ids'])
        control = namespace['optimized_control_gate'](first, second, protocol, identity, step)
        speeds = [rate(first), rate(second)]
        assert all(x >= 4.438538339317307 for x in speeds)
        control['per_pass_tokens_per_second'] = speeds
        assert control == read(folder / 'control_admission.json')
        full = verify_set('full_dev', protocol['dev_ids'])
        assert len(full) == 84
        scores = [x['metrics'] for x in full]
        metrics = r.aggregate(scores)
        assert metrics == read(folder / 'metrics.json')
        failures = []
        for direction, bounds in spec['selection_gates'].items():
            for name, threshold in bounds.items():
                value = metrics[name]
                assert type(value) in (int, float) and math.isfinite(value)
                if (direction == 'minimum' and value < threshold) or (direction == 'maximum' and value > threshold):
                    failures.append(dict(gate=name, actual=value, direction=direction, threshold=threshold))
        for name, count in metrics['catastrophic'].items():
            if count:
                failures.append(dict(gate='catastrophic.' + name, actual=count, maximum=0))
        passed = not failures
        assert passed == selection.passes(metrics, spec['selection_gates'])
        assert read(folder / 'status.json') == dict(complete=True, rows=84, passes=passed)
        counts = {}
        for key in ('claims', 'evidence', 'typed_gaps', 'typed_uncertainty'):
            values = {k: sum(s[key][k] for s in scores) for k in ('tp', 'fp', 'fn')}
            tp, fp, fn = (values[k] for k in ('tp', 'fp', 'fn'))
            values.update(precision=tp / (tp + fp), recall=tp / (tp + fn), f1=2 * tp / (2 * tp + fp + fn))
            assert values['f1'] == metrics[key + '_f1']
            counts[key] = values
        described = [audit.describe(x, gold[x['example_id']], 288) for x in full]
        efficiency = audit.summarize(described, 'COMPLETE_FRESH_V3_DEV')
        tokens = sum(x['output_tokens'] for x in full)
        efficiency['aggregate_correct_atoms_per_output_token'] = {k: v['tp'] / tokens for k, v in counts.items()}
        accepted = [x for x in described if x['accepted'] and x['contract_valid']]
        groups = {name: [x for x in accepted if pred(x)] for name, pred in (
            ('correct_refusals', lambda x: x['refused']),
            ('correct_empty', lambda x: not x['refused'] and x['efficiency']['required_atoms'] == 0),
            ('substantive_successes', lambda x: x['efficiency']['required_atoms'] > 0))}
        groups = {k: dict(count=len(v), total_tokens=sum(x['tokens'] for x in v), token_cost=audit.distribution(x['tokens'] for x in v)) for k, v in groups.items()}
        all_described[str(step)] = described
        checkpoints.append(dict(step=step, metrics=metrics, adapter_sha256=identity['files']['adapter_model.safetensors'], identity=identity))
        results[str(step)] = dict(identity=identity, controls=control, full_dev_rows=84, generation_seconds=sum(x['generation_seconds'] for x in full),
            output_tokens=tokens, tokens_per_second=rate(full), metrics=metrics, atom_metrics=counts, failed_gates=failures,
            efficiency=efficiency, accepted_groups=groups, passes=passed, state_restored=True)
    assert raw_count == 196 and checkpoints == read(out / 'checkpoints.json')
    chosen = selection.select(checkpoints, spec)
    assert chosen == read(out / 'selection.json')
    verdict = 'PRODUCER_TUNING_V3_PASS' if chosen['verdict'] == 'PRODUCER_V3_PASS' else 'PRODUCER_TUNING_V3_FAIL'
    assert read(out / 'status.json') == dict(verdict=verdict, training_updates=168, checkpoint_rows={'84': 84, '168': 84}, training_seconds=wall, selection=chosen)
    if verdict.endswith('_PASS'):
        for name, digest in identities[str(chosen['selected_step'])]['files'].items():
            assert sha(out / 'selected_adapter' / name) == digest
    else:
        assert not (out / 'selected_adapter').exists()
    samples = rows(out / 'telemetry.jsonl')
    train_samples = [s for s in samples if any(x['epoch_seconds'] - x['step_seconds'] <= s['epoch'] <= x['epoch_seconds'] for x in training)]
    def telemetry(values):
        return dict(samples=len(values), gpu_utilization_percent=audit.distribution(float(x['gpu'].split(',')[0]) for x in values if x.get('gpu')),
                    cpu_percent=audit.distribution(x['cpu_percent'] for x in values), rss_bytes=audit.distribution(x['rss'] for x in values),
                    host_ram_used_bytes=audit.distribution(x['host_ram_used'] for x in values))
    budget = rows(out / 'budget_timeline.jsonl')
    assert budget and all(x['continue_run'] for x in budget)
    result = dict(verdict=verdict, source_commit=manifest['source_commit'], dataset_sha256=sha(V3 / 'dataset.json'),
        cloud=dict(provider='Lambda Cloud', region=manifest['region'], gpu=manifest['instance']['gpu_type'], hourly_rate=manifest['hourly_rate'], termination=termination, zero_billable_resources=True),
        training=dict(updates=168, examples_processed=672, each_train_example_seen=2, dev_gradient_examples=0, training_seconds=wall,
            initial_loss=training[0]['loss'], final_loss=training[-1]['loss'], update_seconds=audit.distribution(x['step_seconds'] for x in training),
            peak_vram_allocated_bytes=max(x['max_memory_allocated'] for x in training), peak_vram_reserved_bytes=max(x['max_memory_reserved'] for x in training),
            telemetry=telemetry(train_samples), overall_telemetry=telemetry(samples), initialization=init, identities=identities),
        checkpoints=results, selection=chosen, passing_checkpoints=[x['step'] for x in checkpoints if selection.passes(x['metrics'], spec['selection_gates'])],
        preservation=preservation, preservation_scope=read(V3 / 'freeze.json')['preservation'], archive_sha256=sha(BASE / 'evidence.tar.gz'),
        AUDITOR_STATUS='UNTOUCHED', PROTECTED_RECEIPT_STATUS='UNCONSUMED', next_action='Stop Producer LoRA branch; no automatic V4; separate architecture/model-choice review only.')
    write('RECOMPUTED_RESULTS.json', result)
    write('RECOMPUTED_PER_ROW.json', all_described)
    scanned = []
    for p in BASE.rglob('*'):
        if not p.is_file() or 'bundle_check' in p.parts or p.suffix not in ('.py', '.json', '.jsonl', '.md', '.log'):
            continue
        hits = credential_locations(p.read_bytes(), p.relative_to(ROOT).as_posix())
        if hits:
            for h in hits:
                print(f"WARNING: Possible API key detected in {h['file']}:{h['line']}. Do not push. Rotate the key immediately.")
            raise SystemExit(1)
        scanned.append(p)
    write('POST_RUN_VERIFICATION.json', dict(passed=True, raw_rows_recomputed=196, full_dev_rows=168, control_pairs_verified=12,
        updates_verified=168, fresh_initialization_verified=True, state_and_rng_restored_at_both_checkpoints=True,
        no_training_after_168=True, dataset_split_schedule_verified=True, adapter_hashes_verified=[0, 84, 168],
        historical_preservation_verified=True, credential_files_scanned=len(scanned), credential_findings=0, zero_billable_resources=True))
    print(json.dumps(dict(verdict=verdict, passing_checkpoints=result['passing_checkpoints'], updates=168,
                         raw_rows_verified=raw_count, failed_gates={k: v['failed_gates'] for k, v in results.items()}), indent=2))


if __name__ == '__main__':
    main()
