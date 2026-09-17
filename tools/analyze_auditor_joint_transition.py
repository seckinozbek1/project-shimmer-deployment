"""Saved numeric evidence only. No Torch, model forward, optimizer or network."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
import auditor_classifier_lora_core as c
import auditor_classifier_lora_stable as stable

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run';E=B/'downloaded/evidence'
OUT=B/'local_transition_analysis'


def lines(path):return [json.loads(x) for x in path.read_bytes().splitlines()]
def norms(a):return float(np.linalg.norm(a.astype(np.float64)))
def distribution(a):
    v=np.asarray(a,dtype=np.float64)
    return dict(min=float(v.min()),p1=float(np.percentile(v,1)),p5=float(np.percentile(v,5)),median=float(np.median(v)),p95=float(np.percentile(v,95)),p99=float(np.percentile(v,99)),max=float(v.max()))


def delta_group(before,after,lr):
    total=0;old_sq=0.;new_sq=0.;delta_sq=0.;maximum=0.;ratios=[];per=[]
    for name in sorted(before):
        a=before[name];b=after[name];assert a.shape==b.shape and a.dtype==b.dtype==np.float32
        d=b.astype(np.float64)-a.astype(np.float64)
        an=norms(a);bn=norms(b);dn=float(np.linalg.norm(d));total+=a.size
        old_sq+=an*an;new_sq+=bn*bn;delta_sq+=dn*dn;maximum=max(maximum,float(np.abs(d).max()))
        ratios.append((np.abs(d)/lr).astype(np.float32).ravel())
        per.append(dict(name=name,parameters=a.size,before_norm=an,after_norm=bn,delta_norm=dn,relative_delta_norm=dn/an if an else None,max_abs_delta=float(np.abs(d).max())))
    ratios=np.concatenate(ratios)
    return dict(parameters=total,before_norm=math.sqrt(old_sq),after_norm=math.sqrt(new_sq),norm_change=math.sqrt(new_sq)-math.sqrt(old_sq),delta_norm=math.sqrt(delta_sq),relative_delta_norm=math.sqrt(delta_sq/old_sq),max_abs_delta=maximum,
        abs_delta_over_lr=distribution(ratios),fraction_ge_90pct_lr=float(np.mean(ratios>=.9)),fraction_ge_99pct_lr=float(np.mean(ratios>=.99)),fraction_zero=float(np.mean(ratios==0)),lr_sqrt_parameter_count_bound=lr*math.sqrt(total),per_tensor=per)


def ce_head_change_bound(weight_delta,bias_delta,z_norm,label):
    # CE=logsumexp_k(l_k-l_y), so its absolute change is bounded by
    # max_k |delta(l_k-l_y)|; use Cauchy when the post-step vector is absent.
    pair=weight_delta.astype(np.float64)-weight_delta[label].astype(np.float64)
    bias=bias_delta.astype(np.float64)-float(bias_delta[label])
    return float(np.max(np.linalg.norm(pair,axis=1)*z_norm+np.abs(bias)))


def analyze():
    OUT.mkdir(exist_ok=True)
    names=['checkpoint-0/classifier_fork/adapter_model.safetensors','head-200.safetensors','finite_partial_state.safetensors','mean.npy','std.npy','current_train_features.npy','numerical_health.jsonl','training.jsonl','optimizer.json','parameter_inventory.json','current_train_baseline.json','head_train_predictions.jsonl','update0_predictions.jsonl','runtime_ceilings.json','status.json']
    bindings={str((E/n).relative_to(ROOT)).replace('\\','/'):c.sha(E/n) for n in names}
    old_adapter=load_file(str(E/names[0]));old_head=load_file(str(E/'head-200.safetensors'));partial=load_file(str(E/'finite_partial_state.safetensors'))
    new_adapter={k.replace('.classifier_fork.','.'):v for k,v in partial.items() if '.classifier_fork.' in k}
    new_head={k.removeprefix('head.'):v for k,v in partial.items() if k.startswith('head.')}
    assert set(old_adapter)==set(new_adapter) and len(old_adapter)==448 and set(new_head)=={'weight','bias'}
    adapter=delta_group(old_adapter,new_adapter,1e-4);head=delta_group(old_head,new_head,1e-3)
    features=np.load(E/'current_train_features.npy',allow_pickle=False);mean=np.load(E/'mean.npy',allow_pickle=False);std=np.load(E/'std.npy',allow_pickle=False)
    records=c.read(ROOT/'tuning/auditor_classifier_lora/records.json')[:1792];plan=c.read(ROOT/'tuning/auditor_classifier_lora/schedule.json');by={r['example_id']:i for i,r in enumerate(records)}
    events=lines(E/'numerical_health.jsonl');contexts={}
    for x in events:
        if x['event']=='microbatch_boundary':contexts.setdefault((x['update'],x['microbatch']),{})[x['stage']]=x
    rows=[]
    for (update,micro),stages in sorted(contexts.items()):
        identifier=plan[update-1]['example_ids'][micro-1];i=by[identifier];r=records[i];label=c.CLASSES.index(r['relation'])
        z,l0=stable.fp32_numpy(np,features[i:i+1],old_head['weight'],old_head['bias'],mean,std)
        _,l1=stable.fp32_numpy(np,features[i:i+1],new_head['weight'],new_head['bias'],mean,std)
        ce0=float(stable.ce_numpy(np,l0,np.array([label]))[0]);ce1=float(stable.ce_numpy(np,l1,np.array([label]))[0])
        rows.append(dict(update=update,microbatch=micro,example_id=identifier,label=r['relation'],saved_eval_initial=dict(hidden_norm=norms(features[i]),standardized_norm=norms(z[0]),max_abs_standardized=float(np.abs(z).max()),logits=l0[0].tolist(),ce=ce0),observed_training={k:{n:v for n,v in x.items() if n not in ['event','update','microbatch','stage']} for k,x in stages.items()},head_only_on_saved_eval=dict(logits=l1[0].tolist(),ce=ce1,max_abs_logit_change=float(np.abs(l1-l0).max()))))
    target=rows[-1];assert (target['update'],target['microbatch'])==(2,1)
    dw=new_head['weight'].astype(np.float64)-old_head['weight'].astype(np.float64);db=new_head['bias'].astype(np.float64)-old_head['bias'].astype(np.float64)
    label=c.CLASSES.index(target['label']);postnorm=target['observed_training']['normalized_hidden']['norm_max']
    bound=ce_head_change_bound(dw,db,postnorm,label)
    z0=(features-mean)/std
    old_logits=z0@old_head['weight'].T+old_head['bias'];new_logits=z0@new_head['weight'].T+new_head['bias']
    labels=np.array([c.CLASSES.index(r['relation']) for r in records])
    new_ce=stable.ce_numpy(np,new_logits,labels)
    inv=1/std.astype(np.float64);order=np.argsort(inv)[-10:][::-1]
    normalization=dict(std=distribution(std),inverse_std=distribution(inv),counts={str(t):int(np.sum(std<=t)) for t in [1e-6,1.01e-6,2e-6,1e-5,1e-4,.001,.01,.1]},largest_multipliers=[dict(dimension=int(i),std=float(std[i]),inverse_std=float(inv[i])) for i in order],post_hidden_dimension_alignment_available=False)
    pre=next(x for x in reversed(events) if x['event']=='gradients' and x['update']==1)
    clipped=next(x for x in events if x['event']=='clipped_gradients')
    sgd_bound=math.hypot(1e-3*clipped['head_gradient_norm'],1e-4*clipped['lora_gradient_norm'])
    transition=dict(adapter=adapter,head=head,combined_delta_norm=math.hypot(adapter['delta_norm'],head['delta_norm']),gradient_pre_clip=pre,gradient_post_clip=clipped,gradient_scale=clipped['combined_gradient_norm']/pre['combined_gradient_norm'],hypothetical_sgd_delta_norm_same_clipped_gradients=sgd_bound)
    counterfactual=dict(target=target,head_change_ce_bound_on_unknown_actual_post_z=bound,old_head_ce_on_actual_post_z_lower_bound=max(0.,target['observed_training']['ce']['max']-bound),standardized_representation_change_norm_lower_bound=abs(postnorm-target['saved_eval_initial']['standardized_norm']),
        all_train_fixed_features_new_head=dict(mean_ce=float(new_ce.mean(dtype=np.float32)),accuracy=float(np.mean(new_logits.argmax(axis=1)==labels)),max_ce=float(new_ce.max()),prediction_changes=int(np.sum(new_logits.argmax(axis=1)!=old_logits.argmax(axis=1))),max_abs_logit_change=float(np.abs(new_logits-old_logits).max())),
        limits='No post-step full hidden vector, training-mode pre-update2 counterfactual, saved per-coordinate gradients or Adam moments. Bounds use scalar norm telemetry, not a model forward.')
    result=dict(bindings=bindings,normalization=normalization,transition=transition,telemetry_rows=rows,counterfactual=counterfactual,verdict='AUDITOR_JOINT_TRAINING_STABILIZATION_UNISOLATED',most_likely='Representation-side response to the first classifier-LoRA AdamW step; dropout/train-mode contribution is not separated.',classification='MIXED_OR_UNISOLATED',torch_imported='torch' in __import__('sys').modules)
    assert not result['torch_imported']
    for p,h in bindings.items():assert c.sha(ROOT/p)==h
    (OUT/'results.json').write_bytes((json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())
    compact=dict(normalization=normalization,adapter={k:v for k,v in adapter.items() if k!='per_tensor'},head={k:v for k,v in head.items() if k!='per_tensor'},counterfactual=counterfactual,gradient_pre_clip=pre,gradient_post_clip=clipped,sgd_comparison=sgd_bound)
    print(json.dumps(compact,indent=2));return result


if __name__=='__main__':analyze()
