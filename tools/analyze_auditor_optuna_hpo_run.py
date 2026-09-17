"""Local saved-evidence verification only; no backbone, optimizer, or cloud."""
import hashlib
import json
import math
import sqlite3
import numpy as np
import tarfile
from pathlib import Path
import auditor_optuna_hpo as h
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'docs/fix/auditor_optuna_hpo_run'


def read(p):return json.loads(p.read_bytes())
def write(p,v):p.write_bytes((json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())


def analyze():
    h.require((B/'TERMINATION_VERIFIED.json').exists(),'teardown evidence required')
    h.require(read(B/'instances_after.json')==[] and read(B/'final_inventory_confirmation.json')['zero_billable_resources'],'empty inventory')
    cleanup=read(B/'cleanup.json');h.require(cleanup['temporary_ssh_removed'] and cleanup['local_key_material_removed'],'SSH cleanup')
    independent=read(B/'independent_inventory_confirmation.json')
    h.require(independent['instances']==[] and independent['zero_billable_resources'] and independent['temporary_ssh_registration_absent'] and independent['local_key_material_absent'],'independent provider teardown check')
    h.require(not (B/'ssh_identity').exists() and not (B/'ssh_identity.pub').exists(),'local private/public key absent')
    preserved=read(B/'preservation_before.json')
    h.require(h.sha(ROOT/'tuning/auditor_optuna_hpo/seal.json')==preserved['approved_seal_sha256'],'approved seal preserved')
    for r in preserved['artifacts'].values():h.require(h.sha(ROOT/r['path'])==r['sha256'],'source artifact preserved')
    h.require(h.sha(ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/EVIDENCE_MANIFEST.json')==preserved['prior_evidence_manifest_sha256'],'historical evidence manifest preserved')
    archive=B/'evidence.tar.gz';h.require(h.sha(archive)==read(B/'collection_integrity.json')['sha256'],'download archive identity')
    destination=B/'downloaded';destination.mkdir(exist_ok=True)
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar.getmembers():
            h.require((destination/member.name).resolve().is_relative_to(destination.resolve()) and not member.issym() and not member.islnk(),'archive safe paths')
        tar.extractall(destination,filter='data')
    e=destination/'evidence';manifest=read(B/'execution_manifest.json')
    h.require(h.sha(destination/'execution_manifest.json')==h.sha(B/'execution_manifest.json'),'executed manifest')
    for name,digest in manifest['files'].items():
        p=destination/name
        if p.exists():h.require(h.sha(p)==digest,'downloaded executed source '+name)
    events=[]
    if (e/'events.jsonl').exists():
        for line in (e/'events.jsonl').read_bytes().splitlines():
            events.append(json.loads(line))
    evals=[r for r in events if r['event']=='inner_val'];updates=[r for r in events if r['event']=='update'];prunes=[r for r in events if r['event']=='numerical_prune']
    split=read(ROOT/'tuning/auditor_optuna_hpo/split.json');plan=h.schedule(split)
    val_ids=[r['example_id'] for r in split['assignments'] if r['split']=='inner_val']
    pending_forwards=[];microbatches={}
    for r in events:
        if r['event']=='forward_boundary':pending_forwards.append(r)
        if r['event']=='microbatch':microbatches.setdefault((r['trial'],r['update']),[]).append(r)
        if r['event']=='inner_val':
            scored=pending_forwards[-360:]
            h.require([x['example_id'] for x in scored]==val_ids and all(not x['train_mode'] for x in scored),'exact eval-only INNER_VAL population')
            h.require(math.isclose(sum(x['ce']['max'] for x in scored)/360,r['metrics']['ce'],abs_tol=1e-12),'recomputed INNER_VAL CE')
            pending_forwards=[]
    for r in updates:
        micro=microbatches[(r['trial'],r['update'])]
        h.require([x['microbatch'] for x in micro]==[1,2,3,4] and [x['example_id'] for x in micro]==plan[r['update']-1],'exact INNER_TRAIN microbatch schedule')
        h.require(math.isclose(sum(x['ce']['max'] for x in micro)/4,r['ce'],abs_tol=1e-12),'recomputed update CE')
        h.require(r['train_mode'] and all(x['train_mode'] for x in micro),'training mode')
        for key in ('head_gradient_norm','lora_gradient_norm','head_parameter_delta_norm','lora_parameter_delta_norm'):
            h.require(math.isfinite(r[key]) and r[key]>0,'active finite parameter group '+key)
    diagnostic_drift={};initial_vectors={}
    for r in events:
        if r['event']!='diagnostic':continue
        h.require(r['rng_restored'] and r['no_grad'] and not r['eval']['train_mode'] and r['train']['train_mode'],'nonmutating paired diagnostic')
        vectors=r['vectors'];trial=r['trial']
        eh=np.asarray(vectors['eval_hidden'],dtype=np.float64);th=np.asarray(vectors['train_hidden'],dtype=np.float64)
        ez=np.asarray(vectors['eval_standardized'],dtype=np.float64);tz=np.asarray(vectors['train_standardized'],dtype=np.float64)
        el=np.asarray(vectors['eval_logits'],dtype=np.float64);tl=np.asarray(vectors['train_logits'],dtype=np.float64)
        for key,a,b in [('hidden_difference_l2',eh,th),('standardized_difference_l2',ez,tz),('logit_difference_l2',el,tl)]:
            h.require(math.isclose(float(np.linalg.norm(a-b)),r[key],rel_tol=2e-6,abs_tol=2e-5),'matched diagnostic recomputation')
        if r['update']==0:initial_vectors[trial]=dict(hidden=eh,z=ez,logits=el)
        h.require(trial in initial_vectors,'diagnostic starts at zero')
        drift=float(np.linalg.norm(ez-initial_vectors[trial]['z']))
        diagnostic_drift[trial]=max(diagnostic_drift.get(trial,0.),drift)
    initial_probe_equal=all(np.array_equal(v[k],next(iter(initial_vectors.values()))[k]) for v in initial_vectors.values() for k in v) if initial_vectors else None
    for r in evals:
        m=r['metrics'];cm=m['confusion_matrix'];h.require(len(cm)==4 and all(len(x)==4 and sum(x)==90 for x in cm),'INNER_VAL confusion population')
        recall=[cm[i][i]/90 for i in range(4)]
        f1=[2*cm[i][i]/(90+sum(row[i] for row in cm)) for i in range(4)]
        h.require(math.isclose(m['macro_f1'],sum(f1)/4,abs_tol=1e-12),'recomputed macro F1')
        h.require(math.isclose(m['minimum_class_recall'],min(recall),abs_tol=1e-12),'recomputed minimum recall')
        h.require(all(math.isclose(m['per_class_recall'][label],recall[i],abs_tol=1e-12) for i,label in enumerate(h.CLASSES)),'recomputed class recalls')
        h.require(math.isclose(m['accuracy'],sum(cm[i][i] for i in range(4))/360,abs_tol=1e-12),'recomputed accuracy')
        h.require(math.isclose(r['objective'],h.objective_value(m),abs_tol=1e-12),'recomputed objective')
    trials=read(e/'trials.json') if (e/'trials.json').exists() else []
    winner=read(e/'winner.json') if (e/'winner.json').exists() else None
    if trials:
        h.require(len(trials)==15 and [t['number'] for t in trials]==list(range(15)),'one bounded study')
        h.require(set(initial_vectors)==set(range(15)) and initial_probe_equal,'identical clean initial eval probes')
        with sqlite3.connect((e/'study.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
            h.require(db.execute('select count(*) from studies').fetchone()[0]==1,'one stored study')
            stored=db.execute('select number,state from trials order by number').fetchall()
            h.require(stored==[(t['number'],t['state']) for t in trials],'SQLite trial states')
        for t in trials:
            h.validate_params(t['params'])
            actual=[r for r in updates if r['trial']==t['number']]
            h.require([r['update'] for r in actual]==list(range(1,len(actual)+1)) and len(actual)<=80,'trial update prefix')
            scored=[r for r in evals if r['trial']==t['number']]
            h.require([r['update'] for r in scored]==[u for u in (20,40,80) if u<=len(actual)],'checkpoint scoring schedule')
            if t['state']=='COMPLETE':
                h.require(len(actual)==80 and t['attrs']['completed_result']['metrics']==scored[-1]['metrics'],'complete final metrics')
            for r in actual:
                h.require(math.isclose(r['actual_lora_lr'],h.lora_lr(t['params'],r['update']),rel_tol=1e-12),'warmup LR')
                h.require(r['actual_head_lr']==t['params']['head_lr'],'head LR')
                h.require(r['dropout']==t['params']['dropout'] and r['post_clip_norm']<=1.00001,'dropout/clipping')
        completed=[t['attrs']['completed_result'] for t in trials if t['state']=='COMPLETE']
        for r in completed:h.require(math.isclose(r['representation_drift'],diagnostic_drift[r['trial_number']],rel_tol=1e-12,abs_tol=1e-12),'drift tie-break')
        h.require(winner==h.freeze_winner(completed),'candidate selection')
    access=read(e/'data_access.json') if (e/'data_access.json').exists() else None
    if access:h.require(access['access_counts']==dict.fromkeys(h.FORBIDDEN,0) and access['denied_before_open']==0,'data access receipt')
    admitted=[r for r in events if r['event']=='reuse_admitted']
    h.require(len(admitted)==1 and admitted[0]['passed'] and admitted[0]['full_train_passes']==1 and admitted[0]['rows']==1792 and admitted[0]['controls']==16,'one compatibility pass')
    baseline=read(ROOT/'tuning/auditor_optuna_hpo/clean_initialization/starting_metrics.json')['inner_val']
    baseline_comparison=dict(starting_clean_head=baseline,starting_objective=h.objective_value(baseline))
    if winner and 'metrics' in winner:
        baseline_comparison.update(selected_objective=h.objective_value(winner['metrics']),objective_delta=h.objective_value(winner['metrics'])-h.objective_value(baseline),macro_f1_delta=winner['metrics']['macro_f1']-baseline['macro_f1'],minimum_recall_delta=winner['metrics']['minimum_class_recall']-baseline['minimum_class_recall'])
    launch=read(B/'launch.json');end=read(B/'final_inventory_confirmation.json')['epoch'];rate=read(B/'manifest.json')['hourly_rate']
    result=dict(verdict=winner['verdict'] if winner else 'AUDITOR_OPTUNA_HPO_INDETERMINATE',winner=winner,trial_count=len(trials),
        completed_trials=sum(t['state']=='COMPLETE' for t in trials),pruned_trials=sum(t['state']=='PRUNED' for t in trials),optimizer_updates=len(updates),inner_val_evaluations=evals,numerical_prunes=prunes,
        reuse_admission=admitted,baseline_comparison=baseline_comparison,maximum_observed_eval_representation_drift=diagnostic_drift,initial_probe_bitwise_equal_across_trials=initial_probe_equal,data_access=access,zero_billable_resources=True,ssh_cleanup=True,
        duration_upper_bound_seconds=end-launch['epoch'],estimated_cost_upper_bound_usd=(end-launch['epoch'])*rate/3600,hourly_rate=rate,
        collection_sha256=h.sha(archive),source_preserved=True,limitations='Confusion-derived metrics/objectives and recorded schedules are independently recomputed; no backbone forward or unavailable per-row prediction reconstruction.')
    write(B/'RECOMPUTED_RESULTS.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['inner_val_evaluations','numerical_prunes','data_access','reuse_admission']},indent=2))


if __name__=='__main__':analyze()
