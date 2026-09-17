"""Authorized FP32 affine-head fitting on cached INNER_TRAIN only; no backbone."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.tmp/auditor_hpo_deps'))
import json
import time
import hashlib
import numpy as np
from threadpoolctl import threadpool_limits
from safetensors.numpy import save_file
import auditor_optuna_hpo as h

D=ROOT/'tuning/auditor_optuna_hpo'
C=D/'clean_initialization'
E=ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/downloaded/evidence'
FEATURE_SHA='06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287'
HEAD_SPEC=dict(input_dim=3072,outputs=4,initialization='zero',seed=7,dtype='float32',population=1432,updates=200,
               optimizer='Adam',lr=.01,betas=[.9,.999],eps=1e-8,weight_decay=0,regularization=.001,ddof=0,std_clamp=1e-6)


def write(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with path.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())


def select_fit_inputs(features,ids,assignments):
    by={r['example_id']:r for r in assignments}
    indices=[i for i,identifier in enumerate(ids) if by[identifier]['split']=='inner_train']
    h.require(len(indices)==1432 and len(set(ids))==1792,'exact INNER_TRAIN population')
    # INNER_VAL labels and feature rows are never supplied to fit().
    labels=np.array([h.CLASSES.index(by[ids[i]]['relation']) for i in indices],dtype=np.int64)
    return np.asarray(features[indices],dtype=np.float32).copy(),labels,[ids[i] for i in indices]


def fit(x,labels):
    h.require(x.shape==(1432,3072) and x.dtype==np.float32 and np.isfinite(x).all(),'INNER_TRAIN features')
    h.require(labels.shape==(1432,) and np.array_equal(np.bincount(labels,minlength=4),[358]*4),'1432 balanced INNER_TRAIN labels')
    np.random.seed(7)
    mean=x.mean(axis=0,dtype=np.float32)
    std=np.maximum(x.std(axis=0,ddof=0,dtype=np.float32),np.float32(1e-6))
    z=np.asarray((x-mean)/std,dtype=np.float32)
    w=np.zeros((4,3072),dtype=np.float32);b=np.zeros(4,dtype=np.float32)
    mw=np.zeros_like(w);vw=np.zeros_like(w);mb=np.zeros_like(b);vb=np.zeros_like(b)
    trace=[];n=np.float32(len(x))
    for step in range(1,201):
        logits=z@w.T+b;shift=logits-logits.max(axis=1,keepdims=True)
        exp=np.exp(shift);denom=exp.sum(axis=1,keepdims=True,dtype=np.float32)
        ce=np.mean(np.log(denom[:,0])-shift[np.arange(len(x)),labels],dtype=np.float32)
        reg=np.float32(.001)*np.mean(w*w,dtype=np.float32)
        residual=exp/denom;residual[np.arange(len(x)),labels]-=np.float32(1);residual/=n
        gw=residual.T@z+np.float32(.002/w.size)*w
        gb=residual.sum(axis=0,dtype=np.float32)
        for p,g,m,v in [(w,gw,mw,vw),(b,gb,mb,vb)]:
            m*=np.float32(.9);m+=np.float32(.1)*g
            v*=np.float32(.999);v+=np.float32(.001)*(g*g)
            # Bias-corrected Adam; all array arithmetic remains FP32.
            denominator=np.sqrt(v)/np.float32((1-.999**step)**.5)+np.float32(1e-8)
            p-=np.float32(.01/(1-.9**step))*m/denominator
        h.require(all(a.dtype==np.float32 and np.isfinite(a).all() for a in [w,b,gw,gb,mw,vw,mb,vb]),'finite FP32 fit state')
        trace.append(dict(update=step,ce=float(ce),regularization=float(reg),gradient_rows=1432))
    return dict(mean=mean,std=std,weight=w,bias=b),trace


def evaluate(x,labels,state):
    # Affine evaluation of already cached vectors; no model forward or gradients.
    logits=((x-state['mean'])/state['std'])@state['weight'].T+state['bias']
    shift=logits-logits.max(axis=1,keepdims=True)
    ce=np.log(np.exp(shift).sum(axis=1,dtype=np.float32))-shift[np.arange(len(x)),labels]
    m=h.metrics([h.CLASSES[i] for i in labels],[h.CLASSES[i] for i in logits.argmax(axis=1)],ce.tolist())
    return m,logits


def persist(folder,state):
    folder.mkdir(parents=True,exist_ok=True)
    np.save(folder/'hpo_mean.npy',state['mean'],allow_pickle=False)
    np.save(folder/'hpo_std.npy',state['std'],allow_pickle=False)
    save_file({'weight':state['weight'],'bias':state['bias']},str(folder/'hpo_head-200.safetensors'))
    return {n:h.sha(folder/n) for n in ['hpo_mean.npy','hpo_std.npy','hpo_head-200.safetensors']}


def main():
    from auditor_optuna_hpo_remote import install_audit
    access=dict(access_counts=dict.fromkeys(h.FORBIDDEN,0),denied_before_open=0)
    install_audit(access)
    C.mkdir(exist_ok=True)
    h.require(not (C/'FROZEN.json').exists(),'initialization already frozen; do not refit after validation')
    feature_path=E/'current_train_features.npy'
    h.require(h.sha(feature_path)==FEATURE_SHA,'current feature identity')
    split=json.loads((D/'split.json').read_bytes())
    h.require(split['split_sha256']=='b630fc2fbd451c1a0b1a0c7240778031f1432f3a3aa0ad50dd31c37f8d12ba2b','frozen split')
    receipts=[json.loads(line) for line in (E/'current_train_features.jsonl').read_bytes().splitlines()]
    ids=[r['example_id'] for r in receipts]
    features=np.load(feature_path,mmap_mode='r',allow_pickle=False)
    x,labels,fit_ids=select_fit_inputs(features,ids,split['assignments'])
    events=[dict(event='fit_inputs_selected',rows=1432,inner_val_fit_rows=0)]
    start=time.perf_counter()
    with threadpool_limits(limits=1):
        state,trace=fit(x,labels)
        hashes=persist(C,state)
        repeat,repeat_trace=fit(x,labels)
        h.require(all(np.array_equal(state[k],repeat[k]) for k in state) and trace==repeat_trace,'deterministic repeat')
        repeat_hashes=persist(C/'repeat_verification',repeat)
        h.require(hashes==repeat_hashes,'serialized artifact repeatability')
    elapsed=time.perf_counter()-start
    events.append(dict(event='repeatability_passed',updates_each=200,identical_artifact_hashes=True))
    # Freeze is flushed to disk BEFORE any INNER_VAL feature selection/evaluation.
    frozen=dict(artifacts=hashes,head_spec=HEAD_SPEC,feature_sha256=FEATURE_SHA,split_sha256=split['split_sha256'],fit_ids=fit_ids,
        fit_ids_sha256=h.digest(fit_ids),fit_labels_sha256=hashlib.sha256(labels.tobytes()).hexdigest(),fit_feature_sha256=hashlib.sha256(x.tobytes()).hexdigest(),
        initialization_inner_val_feature_contributions=0,initialization_inner_val_label_contributions=0,inner_val_gradient_rows=0,
        deterministic_repeats=2,updates_per_repeat=200,arrays_bitwise_equal=True,serialized_hashes_equal=True,fit_seconds_including_repeat=elapsed,
        arithmetic='NumPy 2.0.2 FP32 bias-corrected Adam; one BLAS thread; numerical procedure matches frozen head fit; GPU bitwise identity not asserted',
        source_sha256=h.sha(Path(__file__)),parameter_choice_before_validation='HEAD_SPEC fixed before fitting; no early stopping or validation selection')
    write(C/'FROZEN.json',frozen);freeze_sha=h.sha(C/'FROZEN.json')
    events.append(dict(event='initialization_frozen',sha256=freeze_sha))
    write(C/'fit_trace.json',trace)
    with threadpool_limits(limits=1):
        train_metrics,train_logits=evaluate(x,labels,state)
        by={r['example_id']:r for r in split['assignments']}
        indices=[i for i,identifier in enumerate(ids) if by[identifier]['split']=='inner_val']
        val_x=np.asarray(features[indices],dtype=np.float32)
        val_labels=np.array([h.CLASSES.index(by[ids[i]]['relation']) for i in indices],dtype=np.int64)
        h.require(len(indices)==360,'INNER_VAL population')
        val_metrics,_=evaluate(val_x,val_labels,state)
    events.append(dict(event='inner_val_information_only_evaluation',rows=360,after_freeze_sha256=freeze_sha,gradient_rows=0))
    h.require({n:h.sha(C/n) for n in hashes}==hashes and h.sha(C/'FROZEN.json')==freeze_sha,'post-validation artifacts unchanged')
    write(C/'starting_metrics.json',dict(inner_train=train_metrics,inner_val=val_metrics,information_only=True,artifacts_changed_after_validation=False,freeze_sha256=freeze_sha))
    write(C/'fit_receipt.json',dict(events=events,access=access,backbone_loaded=False,backbone_inference=False,head_fit_authorized=True,cloud=False,feature_sha256_after=h.sha(feature_path)))
    # Baseline thresholds use INNER_TRAIN only, never validation labels/CE.
    ce=train_metrics['ce'];delta=max(1e-4,.01*ce)
    baseline=dict(example_ids=fit_ids,predicted_indices=train_logits.argmax(axis=1).tolist(),ce=ce,ce_range=[max(0,ce-delta),ce+delta],metrics=train_metrics)
    write(C/'inner_train_baseline.json',baseline)
    print(json.dumps(dict(hashes=hashes,inner_train=train_metrics,inner_val=val_metrics,fit_seconds=elapsed),indent=2))


if __name__=='__main__':main()
