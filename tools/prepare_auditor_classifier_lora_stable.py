"""Local cached-feature parity and stabilization design; no Torch/model/network."""
import json
import math
import sys
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
import auditor_classifier_lora_core as prior
import auditor_classifier_lora_stable as stable
import auditor_v2_execution as old

ROOT=Path(__file__).resolve().parents[1];D=ROOT/'tuning/auditor_classifier_lora_stable';E=ROOT/'docs/fix/auditor_v2_diagnostic_run/downloaded/evidence'


def write(name,value):
    D.mkdir(exist_ok=True);(D/name).write_bytes((json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())


def lines(path):return [json.loads(x) for x in Path(path).read_bytes().splitlines()]


def prepare():
    manifest=prior.read(ROOT/'docs/fix/auditor_v2_diagnostic_run/EVIDENCE_MANIFEST.json')
    bindings={}
    for name in ['head-200.safetensors','mean.npy','std.npy','features.npy','features.jsonl','head_result.json','normalization.json','external_dev.jsonl','historical_dev.jsonl','results.json']:
        path=E/name;relative=path.relative_to(ROOT).as_posix();entries=manifest['local_only_binaries'] if name.endswith(('.npy','.safetensors')) else manifest['text_files']
        expected=entries[relative]['sha256'];stable.verify_bound(path,expected);bindings[relative]=expected
    records=prior.read(ROOT/'tuning/auditor_v2_diagnostic/records.json')
    head=load_file(str(E/'head-200.safetensors'));weight=head['weight'];bias=head['bias']
    mean=np.load(E/'mean.npy',allow_pickle=False);std=np.load(E/'std.npy',allow_pickle=False);features=np.load(E/'features.npy',allow_pickle=False)
    assert features.shape==(2040,3072) and weight.shape==(4,3072) and bias.shape==(4,)
    assert mean.shape==std.shape==(3072,) and all(v.dtype==np.float32 for v in [features,weight,bias,mean,std])
    receipts=lines(E/'features.jsonl');assert [r['example_id'] for r in receipts]==[r['example_id'] for r in records]
    import hashlib
    for f,r in zip(features,receipts):assert hashlib.sha256(f.tobytes()).hexdigest()==r['sha256']
    # Verification-only recomputation: the initializer remains the saved arrays.
    np.testing.assert_array_equal(features[:1792].mean(axis=0,dtype=np.float32),mean)
    np.testing.assert_array_equal(np.maximum(features[:1792].std(axis=0,ddof=0,dtype=np.float32),np.float32(1e-6)),std)
    normalization=prior.read(E/'normalization.json');assert normalization['train_ids']==[r['example_id'] for r in records[:1792]] and not normalization['dev_fit']
    z,logits=stable.fp32_numpy(np,features,weight,bias,mean,std)
    # Independent explicit per-row dot-product reference covers all 2,040 rows.
    row_reference=np.stack([weight@((h-mean)/std)+bias for h in features])
    np.testing.assert_allclose(logits,row_reference,rtol=1e-4,atol=2e-4)
    assert np.array_equal(logits.argmax(axis=1),row_reference.argmax(axis=1))
    saved=lines(E/'external_dev.jsonl')+lines(E/'historical_dev.jsonl')
    assert [x['example_id'] for x in saved]==[r['example_id'] for r in records[1792:]]
    saved_logits=np.asarray([x['logits'] for x in saved],dtype=np.float32)
    np.testing.assert_allclose(logits[1792:],saved_logits,rtol=1e-4,atol=2e-4)
    assert [prior.CLASSES[i] for i in logits[1792:].argmax(axis=1)]==[x['predicted'] for x in saved]
    train_metrics=old.metrics([r['relation'] for r in records[:1792]],[prior.CLASSES[i] for i in logits[:1792].argmax(axis=1)])
    assert train_metrics==prior.read(E/'head_result.json')['metrics']
    challenges=prior.read(ROOT/'tuning/auditor_v2_diagnostic/challenges.json')
    preds={r['example_id']:prior.CLASSES[int(v.argmax())] for r,v in zip(records[1792:],logits[1792:])}
    evaluation=old.evaluate(records,preds,challenges,prior.read(ROOT/'tuning/auditor_v2_diagnostic/baseline.json'))
    assert evaluation==prior.read(E/'results.json')
    labels=np.array([prior.CLASSES.index(r['relation']) for r in records[:1792]],dtype=np.int64)
    losses=stable.ce_numpy(np,logits[:1792],labels);ce=float(losses.mean(dtype=np.float32))
    assert abs(ce-prior.read(E/'head_result.json')['final_ce'])<1e-4
    selected=[]
    for cls in prior.CLASSES:
        pool=[i for i,r in enumerate(records[:1792]) if r['relation']==cls]
        selected.extend(sorted(pool,key=lambda i:hashlib.sha256(('stable-controls-v1|7|'+records[i]['example_id']).encode()).hexdigest())[:4])
    control_ce=float(losses[selected].mean(dtype=np.float32));delta=max(1e-4,.01*control_ce)
    controls=dict(example_ids=[records[i]['example_id'] for i in selected],labels=labels[selected].tolist(),logits=logits[selected].tolist(),
        predicted_indices=logits[selected].argmax(axis=1).tolist(),rtol=1e-4,atol=2e-4,expected_ce=control_ce,ce_range=[max(0.,control_ce-delta),control_ce+delta],
        selection='Four per TRAIN class, ascending SHA256(stable-controls-v1|7|example_id); never selected by prediction or loss.',
        expected_representation='base + historical step120 adapter',future_representation='base + fresh zero-B classifier LoRA',future_equivalence_proven=False)
    assert stable.update0(np,controls,logits[selected].copy(),controls['example_ids'],labels[selected])['passed']
    ceiling=max(10*math.log(4),20*ce)
    config=prior.read(ROOT/'tuning/auditor_classifier_lora/experiment.json')
    config['head']['initialization']='bound expanded-data head-200.safetensors'
    config['optimizer']['head_lr']=1e-3;config['normalization']='fixed historical TRAIN mean/std, explicit FP32; no L2'
    config.update(execution_authorized=False,cloud_authorized=False,readiness='AUDITOR_CLASSIFIER_LORA_STABILIZED_NOT_READY',
        blocker='Cached parity is from base+step120 features. Fresh classifier LoRA with B=0 removes the step120 transformation; update0 equivalence is not established and cannot be inferred from head/normalization reuse.',
        initialization_artifacts={n:dict(path=(E/n).relative_to(ROOT).as_posix(),sha256=prior.sha(E/n)) for n in ['head-200.safetensors','mean.npy','std.npy']},
        classification_dtypes={k:'float32' for k in ['hidden_cast','normalization','head','logits','ce','regularization','total_loss','accumulated_loss']},
        numerical_gate=dict(updates=20,mean_update_ce_ceiling=ceiling,microbatch_ce_ceiling=4*ceiling,
            ceiling_formula='max(10*ln(4), 20*cached_full_TRAIN_mean_CE)',finite_at_every_stage=True,skip_updates=False,retries=False,dev_at_20=False,
            rationale='Ten times uniform four-class CE; >170x cached mean CE here, generous for stochastic variation but rejects prior 50+ update-mean CE. Per-microbatch cap is four times this bound.',
            continue_same_run_only_after_pass=True),
        initial_cached_train_ce=ce,initial_cached_train_ce_range=[max(0.,ce-max(1e-4,.01*ce)),ce+max(1e-4,.01*ce)],
        update0_scope='16 TRAIN controls only; their bound CE range is distinct from full cached TRAIN CE. No full-TRAIN remote CE is inferred from controls.')
    write('experiment.json',config);write('update0_controls.json',controls);write('source_bindings.json',bindings)
    for name in ['records.json','schedule.json','challenges.json']:
        source=ROOT/'tuning/auditor_classifier_lora'/name
        write(name+'_binding.json',dict(path=source.relative_to(ROOT).as_posix(),sha256=prior.sha(source)))
    write('parity.json',dict(rows_checked=2040,train_rows=1792,external_dev_rows=200,historical_dev_rows=48,
        max_error_vs_saved_dev_logits=float(np.max(np.abs(logits[1792:]-saved_logits))),saved_logit_rows=248,
        max_error_vs_independent_row_reference=float(np.max(np.abs(logits-row_reference))),prediction_identity=True,all_saved_metrics_identical=True,
        train_logits_limitation='No per-row TRAIN logits/predictions were persisted; TRAIN metrics match, and all TRAIN predictions match independent per-row recomputation.',
        cached_train_ce=ce,max_train_row_ce=float(losses.max()),future_fresh_representation_parity_proven=False,
        rtol=1e-4,atol=2e-4,base_or_lora_weights_loaded=False,torch_imported='torch' in sys.modules))
    executed=ROOT/'docs/fix/auditor_classifier_lora_run/downloaded/tools/auditor_classifier_lora_remote.py'
    inventory=prior.read(ROOT/'docs/fix/auditor_classifier_lora_run/downloaded/evidence/parameter_inventory.json')
    norm=next(x for x in inventory['items'] if x['name']=='base_model.model.model.norm.weight')
    assert norm['dtype']=='torch.float32'
    write('failure_audit.json',dict(verdict='NUMERICAL_FAILURE_SOURCE_NOT_ISOLATED',executed_source_sha256=prior.sha(executed),
        completed_update_ce=[1.3862943649291992,58.268070220947266,53.68067717552185],failed_attempted_update=4,
        observed_failure='Non-finite CE + regularization at pre-backward assertion; first offending tensor was not logged.',
        dtype_path=dict(prompt_ids='int64',base_storage='NF4 packed uint8',base_compute='BF16 autocast / mixed FP32 embedding and RMSNorm arithmetic',
            classifier_lora_parameters='FP32',final_normalized_hidden='FP32 inferred from pinned LlamaRMSNorm and recorded FP32 norm weight; activation dtype not logged',
            hidden_for_head='explicit FP32 cast',head_weights_and_matmul='FP32; outside BF16 autocast',logits='FP32',ce='FP32',regularization='FP32',
            total_and_divide_by_four='FP32',gradients='FP32 parameter-gradient storage expected; per-tensor gradient dtypes not logged',clipping='combined max norm 1; only returned pre-clip norm logged',optimizer='AdamW on FP32 LoRA/head groups; no per-step parameter-finiteness log'),
        causal_limit='Observed configuration was unstable; no ablation or tensor-stage evidence identifies zero initialization, LR, base kernels, activations or optimizer state as the unique cause.',
        old_head_was_already_fp32=True,new_fp32_contract_is_instrumented_enforcement_not_a_proven_root_cause_fix=True))
    write('telemetry_schema.json',dict(events=['microbatch_boundary','pre_forward_parameters','gradients','clipped_gradients','post_step_parameters','update_complete','STOP','NUMERICAL_ADMISSION_20_PASS'],
        per_microbatch=['update','microbatch','stage','dtype','finite','min','max','max_abs','norm_min','norm_mean','norm_max','CE','regularization','total_loss','head_gradient_norm','lora_gradient_norm','combined_gradient_norm'],
        per_update=['head_gradient_norm','lora_gradient_norm','combined_pre_clip_norm','combined_post_clip_norm','head_parameter_norm','lora_parameter_norm','head_finite','lora_finite','mean_ce','ceiling','unauthorized_parameter_unchanged'],
        failures='Persist first failing stage before raising; latch stop; no rollback/reinitialization/retry.',full_tensors_dumped=False,
        frozen_state='Use FrozenAudit.unchanged each step; full base-state hash additionally at update20/448/896. Persist initial and comparison hashes.',
        save_on_failure='Future runner must persist compact telemetry and finite partial state before teardown; not implemented as a cloud controller in this blocked local package.'))
    histories=lines(ROOT/'docs/fix/auditor_classifier_lora_run/downloaded/evidence/training.jsonl')
    canonical=lines(ROOT/'docs/fix/auditor_canonical_tuning_run/downloaded/evidence/training.jsonl')
    short_mean=sum(x['update_seconds'] for x in histories)/len(histories)
    historical_p95=float(np.percentile([x['step_seconds'] for x in canonical],95))
    write('projection.json',dict(historical_rate_usd_per_hour=1.29,live_price_queried=False,prior_three_update_mean_seconds=short_mean,historical_update_p95_seconds=historical_p95,
        training_minutes=[896*short_mean/60,896*historical_p95*1.2/60],planning_total_minutes=[65,120],planning_cost_usd=[65/60*1.29,2*1.29],
        assumptions='Three finite updates are weak timing evidence. Upper training allowance adds 20% instrumentation overhead to historical p95; no stability or completion guarantee. Setup, two 248-row checkpoint evaluations, update0 TRAIN controls, hashing/collection/teardown included in total planning range.',
        price_and_capacity_recheck_required_before_separately_authorized_run=True,cloud_authorized=False,readiness_blocked=True))
    assert 'torch' not in sys.modules
    print(json.dumps(dict(cached_train_ce=ce,control_ce=control_ce,ceiling=ceiling,saved_dev_error=float(np.max(np.abs(logits[1792:]-saved_logits))),row_reference_error=float(np.max(np.abs(logits-row_reference))),readiness=config['readiness'])))


if __name__=='__main__':prepare()
