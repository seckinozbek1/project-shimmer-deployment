"""Post-termination Auditor verification from durable raw evidence; no model execution."""
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
BASE = ROOT / 'docs/fix/auditor_canonical_tuning_run'
V3 = ROOT / 'tuning/auditor_canonical_execution'
RT = V3
os.environ.update(USE_TORCH='0', USE_TF='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
sys.path.insert(0, str(RT))
import eval_runtime as ev
sys.path.insert(0, str(ROOT / 'tuning/second_tuning_eval_runtime_v2'))
import audit
sys.path.insert(0, str(V3))
import selection
from binding import control_gate
from auditor_canonical_local import verify_history
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


def describe_auditor(full, scores):
    classes=list(r.CLASSES)
    labels=classes+sorted({s['predicted_relation'] for s in scores}-set(classes))
    confusion={c:{p:0 for p in labels} for c in classes}
    per_class={}
    for s in scores:confusion[s['expected_relation']][s['predicted_relation']]+=1
    for c in classes:
        tp=sum(s['expected_relation']==c and s['predicted_relation']==c and s['contract_valid'] for s in scores)
        fp=sum(s['predicted_relation']==c and (s['expected_relation']!=c or not s['contract_valid']) for s in scores)
        fn=sum(s['expected_relation']==c and (s['predicted_relation']!=c or not s['contract_valid']) for s in scores)
        support=sum(s['expected_relation']==c for s in scores)
        per_class[c]=dict(precision=tp/(tp+fp) if tp+fp else 0.,recall=tp/(tp+fn),f1=r.f1(dict(tp=tp,fp=fp,fn=fn)),support=support,tp=tp,fp=fp,fn=fn,predicted=tp+fp)
    macros={k:sum(x[k] for x in per_class.values())/5 for k in ('precision','recall','f1')}
    metrics=r.aggregate(scores)
    assert math.isclose(macros['f1'],metrics['macro_relation_f1'],rel_tol=1e-12)
    assert all(per_class[c]['recall']==metrics['per_class_recall'][c] for c in classes)
    evidence={k:sum(s['evidence'][k] for s in scores) for k in ('tp','fp','fn')}
    tp,fp,fn=(evidence[k] for k in ('tp','fp','fn'))
    evidence.update(precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,f1=r.f1(evidence))
    assert evidence['f1']==metrics['evidence_f1']
    refusal=dict(expected=sum(s['expected_refusal'] for s in scores),predicted=sum(s['predicted_refusal'] for s in scores),
        correct=sum(s['expected_refusal'] and s['predicted_refusal'] for s in scores),
        false=sum(not s['expected_refusal'] and s['predicted_refusal'] for s in scores),
        missed=sum(s['expected_refusal'] and not s['predicted_refusal'] for s in scores),
        over_refusal_rate=metrics['over_refusal_rate'],false_refusals_by_class={c:sum(s['expected_relation']==c and not s['expected_refusal'] and s['predicted_refusal'] for s in scores) for c in classes})
    described=[]
    for item,s in zip(full,scores):
        try:obj=r.core.strict_json(item['raw_output'])
        except (ValueError,TypeError):obj={}
        refs=r.values(obj,'ref_ids') if isinstance(obj,dict) else []
        items=obj.get('items',[]) if isinstance(obj,dict) else []
        duplicate_items=len(items)-len({r.sha(i) for i in items}) if isinstance(items,list) else 0
        described.append(dict(example_id=item['example_id'],expected=s['expected_relation'],predicted=s['predicted_relation'],contract_valid=s['contract_valid'],accepted=s['accepted_outcome'],
            correct_refusal=s['expected_refusal'] and s['predicted_refusal'],reason_correct=s['reason_correct'],tokens=item['output_tokens'],
            eos_before_cap=item['stop_reason']=='eos' and item['output_tokens']<192,cap_hit=item['output_tokens']>=192,
            decorations=audit.decorations(item['raw_output']),duplicate_refs=len(refs)-len(set(refs)),duplicate_items=duplicate_items,
            correct_evidence_atoms=s['evidence']['tp'],evidence_atoms_per_output_token=s['evidence']['tp']/item['output_tokens']))
    accepted=[x for x in described if x['accepted'] and x['contract_valid']]
    groups={name:[x for x in accepted if x['correct_refusal']==flag] for name,flag in [('correct_refusals',True),('substantive_successes',False)]}
    groups={name:dict(count=len(v),total_tokens=sum(x['tokens'] for x in v),token_cost=audit.distribution(x['tokens'] for x in v)) for name,v in groups.items()}
    tokens=sum(x['tokens'] for x in described)
    efficiency=dict(output_tokens=audit.distribution(x['tokens'] for x in described),eos_before_cap_rate=sum(x['eos_before_cap'] for x in described)/60,
        cap_hit_rate=sum(x['cap_hit'] for x in described)/60,decorations={k:sum(x['decorations'][k] for x in described) for k in described[0]['decorations']},
        duplicate_refs=sum(x['duplicate_refs'] for x in described),duplicate_items=sum(x['duplicate_items'] for x in described),
        correct_evidence_atoms_per_output_token=tp/tokens,accepted_output_token_cost=audit.distribution(x['tokens'] for x in accepted),accepted_groups=groups,
        all_attempt_tokens_per_accepted_outcome=tokens/len(accepted) if accepted else None)
    return dict(confusion_matrix=confusion,confusion_columns=labels,per_class=per_class,macro=macros,
        precision_zero_division_policy='Diagnostic class precision is 0 when no prediction exists; frozen F1/recall and eligibility unchanged.',
        evidence=evidence,refusal=refusal,accepted_count=len(accepted),efficiency=efficiency,per_row=described,
        relation_correct_but_reason_incorrect=sum(s['relation_correct'] and s['reason_correct'] is not True for s in scores))


def main():
    termination = read(BASE / 'TERMINATION_VERIFIED.json')
    assert read(BASE / 'instances_after.json') == []
    assert read(BASE / 'final_inventory_confirmation.json')['zero_billable_resources']
    assert all(read(BASE / 'cleanup.json')[k] for k in ('temporary_ssh_removed', 'local_key_material_removed'))
    assert sha(BASE / 'evidence.tar.gz') == read(BASE / 'collection_integrity.json')['sha256']
    preservation = verify_history()
    data = BASE / 'downloaded'
    out = data / 'evidence'
    manifest = read(BASE / 'manifest.json')
    execution = read(BASE / 'execution_manifest.json')
    assert read(data / 'execution_manifest.json') == execution
    for p in (data / 'tools').rglob('*.py'):
        assert sha(p) == execution['files'][p.relative_to(data).as_posix()]
    for p in (data / 'tuning').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            assert sha(p) == sha(ROOT / p.relative_to(data))
    assert read(data / 'training_authorization.json') == read(BASE / 'training_authorization.json')
    assert sha(V3 / 'freeze.json') == manifest['release_sha256']
    binding = read(V3 / 'source_binding.json')
    assert sha(V3 / 'dataset.json') == binding['export_sha256']
    spec = read(V3 / 'experiment.json')
    split = read(V3 / 'split.json')
    plan = read(V3 / 'execution_plan.json')
    protocol = read(V3 / 'evaluation_protocol.json')
    prepared = read(V3 / 'prepared_dev.json')
    ev.validate_records(prepared, protocol)
    prepared_by = {x['example_id']: x for x in prepared}
    gold = {x['example_id']: x for x in read(V3 / 'dataset.json')}
    assert len(gold) == 300 and all(x['role'] == 'auditor' for x in gold.values())
    assert len(split['train']) == 240 and len(split['validation']) == 60
    assert not set(split['train']) & set(split['validation'])
    assert not {gold[i]['leakage_group'] for i in split['train']} & {gold[i]['leakage_group'] for i in split['validation']}
    assert read(out / 'preflight.json')['passed']
    assert read(out / 'acquisition.json')['files'] == dict(spec['asset_hashes'], **spec['base_weight_hashes'])
    architecture=read(out/'loaded_architecture.json')
    assert architecture['model_type']==spec['architecture']['family']=='llama'
    assert architecture['architectures']==['LlamaForCausalLM']
    assert architecture['config_sha256']==spec['asset_hashes']['config.json']
    init = read(out / 'initialization.json')
    assert init['fresh_lora'] and not init['old_adapter_loaded'] and init['lora_B_all_zero'] and init['seed'] == 7
    identities = {}
    for step in (0, 60, 120):
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
        assert sum(f.get_tensor(k).size for k in f.keys()) == 14942208
    training = rows(out / 'training.jsonl')
    assert len(training) == 120
    scheduled = plan['optimizer_schedule']
    assert len(scheduled) == 120
    seen = Counter()
    wall = 0.
    for i, (actual, expected) in enumerate(zip(training, scheduled), 1):
        assert actual['step'] == expected['step'] == i and expected['loss_divisor'] == 4
        assert actual['example_ids'] == expected['example_ids'] and len(actual['example_ids']) == 4
        assert actual['epoch'] == expected['epoch'] and actual['examples_processed'] == i * 4
        assert all(x in split['train'] and x not in split['validation'] for x in actual['example_ids'])
        seen.update(actual['example_ids'])
        lr = lambda s: 1e-4 * min(s + 1, max(0., (120 - s) / 119))
        assert math.isclose(actual['learning_rate'], lr(i - 1), rel_tol=1e-12)
        assert math.isclose(actual['next_learning_rate'], lr(i), rel_tol=1e-12, abs_tol=1e-15)
        assert math.isfinite(actual['loss']) and actual['step_seconds'] > 0
        wall += actual['step_seconds']
        assert math.isclose(wall, actual['training_seconds'], rel_tol=1e-12)
    assert seen == Counter({x: 2 for x in split['train']})
    optimizer_receipt = read(out / 'optimizer_config.json')
    assert optimizer_receipt['schedule'] == scheduled and optimizer_receipt['training'] == spec['training']
    tok = r.old.tokenizer('auditor')
    all_described = {}
    checkpoints = []
    results = {}
    raw_count = 0
    for step in (60, 120):
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
                assert item['role'] == 'auditor' and item['split'] == 'canonical' and item['checkpoint'] == step
                assert item['runtime'] == 'auditor-canonical-scoped-v1' and item['adapter'] == identity
                # V3 binds the base once through acquisition + frozen experiment;
                # the low-level V2.1 sink does not repeat it in each raw row.
                assert item['experiment'] == 'auditor-canonical-v2'
                source = prepared_by[item['example_id']]
                for key in ('prompt', 'input_ids', 'attention_mask'):
                    assert item[key] == source[key]
                assert item['prompt_sha256'] == hashlib.sha256(source['prompt'].encode()).hexdigest()
                assert item['input_ids_sha256'] == ev.digest(source['input_ids'])
                ids = item['output_token_ids']
                assert len(ids) == item['output_tokens'] and 0 < len(ids) <= 192
                assert tok.decode(ids, skip_special_tokens=True) == item['raw_output']
                assert tok.decode(ids, skip_special_tokens=False) == item['raw_output_with_special_tokens']
                eos = ids[-1] in spec['terminal_token_ids']
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
        control = control_gate(first, second, protocol, identity, step)
        speeds = [rate(first), rate(second)]
        assert all(math.isfinite(x) and x > 0 for x in speeds)
        control['per_pass_tokens_per_second'] = speeds
        assert control == read(folder / 'control_admission.json')
        full = verify_set('full_dev', protocol['dev_ids'])
        assert len(full) == 60
        scores = [x['metrics'] for x in full]
        metrics = r.aggregate(scores)
        assert metrics == read(folder / 'metrics.json')
        failures = []
        for direction, bounds in spec['selection_gates'].items():
            for name, threshold in bounds.items():
                value = metrics['per_class_recall'][name] if direction == 'per_class_recall' else metrics[name]
                assert type(value) in (int, float) and math.isfinite(value)
                if (direction in ('minimum','per_class_recall') and value < threshold) or (direction == 'maximum' and value > threshold):
                    failures.append(dict(gate=('per_class_recall.' if direction=='per_class_recall' else '')+name, actual=value, direction=direction, threshold=threshold))
        for name, count in metrics['catastrophic'].items():
            if count:
                failures.append(dict(gate='catastrophic.' + name, actual=count, maximum=0))
        passed = not failures
        assert passed == r.selection_pass(metrics, spec['selection_gates'])
        assert read(folder / 'status.json') == dict(complete=True, rows=60, passes=passed)
        diagnostics = describe_auditor(full, scores)
        all_described[str(step)] = diagnostics.pop('per_row')
        checkpoints.append(dict(step=step, metrics=metrics, adapter_sha256=r.sha(identity['files']), identity=identity))
        results[str(step)] = dict(identity=identity, controls=control, full_dev_rows=60, generation_seconds=sum(x['generation_seconds'] for x in full),
            output_tokens=sum(x['output_tokens'] for x in full), tokens_per_second=rate(full), metrics=metrics, failed_gates=failures,
            diagnostics=diagnostics, passes=passed, state_restored=True)
    assert raw_count == 144 and checkpoints == read(out / 'checkpoints.json')
    chosen = selection.select(checkpoints, spec)
    assert chosen == read(out / 'selection.json')
    verdict = 'AUDITOR_TUNING_PASS' if chosen['verdict'] == 'AUDITOR_TUNING_PASS' else 'AUDITOR_TUNING_FAIL'
    assert read(out / 'status.json') == dict(verdict=verdict, training_updates=120, checkpoint_rows={'60': 60, '120': 60}, training_seconds=wall, selection=chosen)
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
    result = dict(verdict=verdict, source_commit=manifest['source_commit'], dataset_sha256=binding['source_dataset_sha256'],auditor_export_sha256=sha(V3/'dataset.json'),
        cloud=dict(provider='Lambda Cloud', region=manifest['region'], gpu=manifest['instance']['gpu_type'], hourly_rate=manifest['hourly_rate'], termination=termination, zero_billable_resources=True),
        training=dict(updates=120, examples_processed=480, each_train_example_seen=2, dev_gradient_examples=0, training_seconds=wall,
            initial_loss=training[0]['loss'], final_loss=training[-1]['loss'], update_seconds=audit.distribution(x['step_seconds'] for x in training),
            peak_vram_allocated_bytes=max(x['max_memory_allocated'] for x in training), peak_vram_reserved_bytes=max(x['max_memory_reserved'] for x in training),
            telemetry=telemetry(train_samples), overall_telemetry=telemetry(samples), initialization=init, identities=identities,loaded_architecture=architecture),
        checkpoints=results, selection=chosen, passing_checkpoints=[x['step'] for x in checkpoints if r.selection_pass(x['metrics'], spec['selection_gates'])],
        preservation=preservation, source_release_sha256=binding['source_release_sha256'], archive_sha256=sha(BASE / 'evidence.tar.gz'),
        PRODUCER_STATUS='PRESERVED_UNEXECUTED', PROTECTED_RECEIPT_STATUS='UNCONSUMED', next_action=('Separately authorize Producer168 + selected Auditor + existing governance/re-fire system test.' if verdict.endswith('_PASS') else 'No automatic Auditor retraining; local failure diagnosis only.'))
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
    write('POST_RUN_VERIFICATION.json', dict(passed=True, raw_rows_recomputed=144, full_dev_rows=120, control_pairs_verified=10,
        updates_verified=120, fresh_initialization_verified=True, state_and_rng_restored_at_both_checkpoints=True,
        no_training_after_120=True, dataset_split_schedule_verified=True, adapter_hashes_verified=[0, 60, 120],
        historical_preservation_verified=True, credential_files_scanned=len(scanned), credential_findings=0, zero_billable_resources=True))
    print(json.dumps(dict(verdict=verdict, passing_checkpoints=result['passing_checkpoints'], updates=120,
                         raw_rows_verified=raw_count, failed_gates={k: v['failed_gates'] for k, v in results.items()}), indent=2))


if __name__ == '__main__':
    main()
