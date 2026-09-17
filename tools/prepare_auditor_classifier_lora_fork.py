"""Copy and inspect adapter bytes; cached NumPy parity only, no Torch/model loading."""
import copy
import json
import sys
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
import auditor_classifier_lora_fork as fork
import auditor_classifier_lora_stable as stable
import auditor_v2_execution as previous

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'tuning/auditor_classifier_lora_fork'
OLD=ROOT/'tuning/auditor_classifier_lora_stable'
SOURCE=ROOT/'docs/fix/auditor_canonical_tuning_run/downloaded/evidence/checkpoint-120'


def read(p):return json.loads(Path(p).read_bytes())
def write(name,value):(D/name).write_bytes((json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode())


def prepare():
    for path,h in read(OLD/'seal.json')['files'].items():stable.verify_bound(ROOT/path,h)
    D.mkdir(exist_ok=True)
    receipt=fork.create_fork(SOURCE,D/'classifier_adapter_init')
    receipt.update(source_path=SOURCE.relative_to(ROOT).as_posix(),fork_path=(D/'classifier_adapter_init').relative_to(ROOT).as_posix(),tensor_values_deserialized=False,model_function_parity_measured=False)
    write('adapter_copy.json',receipt)
    spec=copy.deepcopy(read(OLD/'experiment.json'))
    config=read(SOURCE/'adapter_config.json')
    for key in ['r','lora_alpha','lora_dropout','bias','task_type']:
        assert config[key]==spec['lora'][key]
    assert set(config['target_modules'])==set(spec['lora']['target_modules'])
    assert receipt['parameters']==spec['expected_lora_parameters']
    spec.update(architecture='pinned base -> classifier fork initialized from immutable step120 -> fixed TRAIN normalization -> pretrained four-way head',
                historical_adapter_loaded='read-only reference during update0 only; removed before optimizer creation',
                readiness='AUDITOR_CLASSIFIER_LORA_STABILIZED_READY',blocker=None,
                initializer='exact step120 copy into classifier_adapter_init; never randomize/reinitialize fork',
                reference_adapter_sha256=fork.SOURCE_SHA,fork_adapter_sha256=receipt['fork_adapter_sha256'],adapter_config_sha256=fork.CONFIG_SHA,
                runtime_model_function_parity_proven=False,
                update0_scope='16 TRAIN reference/candidate controls followed by all 1792 TRAIN rows; no optimizer before both pass',
                source_immutable=True,cloud_authorized=False,execution_authorized=False)
    write('experiment.json',spec)
    controls=read(OLD/'update0_controls.json')
    controls['future_representation']='base + exact historical step120 copy in classifier-specific adapter'
    controls['future_equivalence_proven']=False
    write('update0_controls.json',controls)
    records=read(ROOT/'tuning/auditor_classifier_lora/records.json')
    train=records[:1792];assert all(r['split']=='train' for r in train)
    artifacts=spec['initialization_artifacts']
    for a in artifacts.values():stable.verify_bound(ROOT/a['path'],a['sha256'])
    runtime_paths=[SOURCE/'adapter_model.safetensors',SOURCE/'adapter_config.json',D/'classifier_adapter_init/adapter_model.safetensors',D/'classifier_adapter_init/adapter_config.json',*[ROOT/a['path'] for a in artifacts.values()]]
    write('runtime_bindings.json',{p.relative_to(ROOT).as_posix():fork.sha(p) for p in runtime_paths})
    evidence=ROOT/'docs/fix/auditor_v2_diagnostic_run/downloaded/evidence'
    for p,h in read(OLD/'source_bindings.json').items():stable.verify_bound(ROOT/p,h)
    head=load_file(str(evidence/'head-200.safetensors'))
    mean=np.load(evidence/'mean.npy',allow_pickle=False);std=np.load(evidence/'std.npy',allow_pickle=False)
    features=np.load(evidence/'features.npy',allow_pickle=False)
    _,logits=stable.fp32_numpy(np,features,head['weight'],head['bias'],mean,std)
    preds=logits[:1792].argmax(axis=1).tolist();classes=spec['classes']
    metrics=previous.metrics([r['relation'] for r in train],[classes[i] for i in preds])
    assert metrics==read(evidence/'head_result.json')['metrics']
    ce=float(stable.ce_numpy(np,logits[:1792],np.array([classes.index(r['relation']) for r in train])).mean(dtype=np.float32))
    assert abs(ce-spec['initial_cached_train_ce'])<1e-7
    write('train_baseline.json',dict(classes=classes,example_ids=[r['example_id'] for r in train],input_id_hashes=[fork.token_hash(r['input_ids']) for r in train],
        labels=[r['relation'] for r in train],predicted_indices=preds,metrics=metrics,ce=ce,ce_range=spec['initial_cached_train_ce_range'],
        prediction_origin='Recomputed from preserved cached TRAIN features and hash-bound head; original per-row TRAIN predictions were not saved. Aggregate metrics equal saved evidence.'))
    write('bindings.json',{p.relative_to(ROOT).as_posix():fork.sha(p) for p in [OLD/'seal.json',OLD/'parity.json',OLD/'telemetry_schema.json',OLD/'projection.json',ROOT/'tools/auditor_classifier_lora_stable.py',*[ROOT/'tuning/auditor_classifier_lora'/n for n in ['records.json','schedule.json','challenges.json']]]})
    write('remote_protocol.json',dict(order=['verify_artifact_hashes','load_two_named_adapter_slots','freeze_all_eval_disable_dropout','16_reference_controls','16_fork_controls','compare_hidden_normalized_logits_argmax_ce','compare_cached_controls','delete_reference','1792_fork_train_baseline_no_grad','check_predictions_metrics_ce','enable_only_fork_and_head','create_optimizer','admit_health_gate','20_numerical_updates','continue_same_schedule_448_896'],
        rtol=1e-4,atol=2e-4,dropout_during_preflight=False,reference_slot=fork.REFERENCE,candidate_slot=fork.CANDIDATE,
        config_copy_inference_mode=True,runtime_trainability='PEFT trainability is explicitly disabled for both slots throughout preflight; only candidate LoRA and head enabled after reference deletion and TRAIN baseline pass. Config source is never edited.',
        failure='sticky NO_GO before optimizer; no retry',functional_parity_measured_locally=False))
    old=read(OLD/'projection.json')
    write('projection.json',dict(historical_rate_usd_per_hour=1.29,live_price_queried=False,training_minutes=old['training_minutes'],
        planning_total_minutes=[75,140],planning_cost_usd=[75/60*1.29,140/60*1.29],
        added_preflight='32 control forwards plus 1792 full-TRAIN forwards; 10-20 minute planning allowance, not measured. Includes prior setup/evaluations/collection estimate.',
        no_authorization_implied=True,hard_budget_fit_not_established=True))
    assert 'torch' not in sys.modules
    print(json.dumps(dict(tensors=receipt['tensors_compared'],parameters=receipt['parameters'],exact_equal=receipt['exact_equal'],train_ce=ce,readiness=spec['readiness'])))


if __name__=='__main__':prepare()
