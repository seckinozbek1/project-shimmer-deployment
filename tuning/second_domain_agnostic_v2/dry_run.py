"""Deterministic no-model verification, fault injection and readiness assessment."""
import sys
import os
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
ALLOWED_METADATA={str((ROOT/p).resolve()).lower() for p in (
    'benchmark/task_semantics_v2/family_manifest.json','benchmark/task_semantics_v2/review_admin_mapping.json')}
access=dict(protected_target_reads=0,model_weight_reads=0,network_calls=0)


def guard(event,args):
    if event in ('socket.connect','socket.getaddrinfo','subprocess.Popen','os.system'):
        raise PermissionError('Offline no-model dry-run rejects network/subprocess')
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        p=Path(os.fsdecode(args[0])).resolve();s=str(p).lower()
        if p.suffix.lower() in ('.safetensors','.bin','.pt','.pth','.gguf'):
            raise PermissionError('Model weights forbidden')
        if p.is_relative_to(ROOT/'benchmark') and p.suffix not in ('.py','.pyc') and s not in ALLOWED_METADATA:
            raise PermissionError('Benchmark data forbidden; metadata allowlist only')


sys.addaudithook(guard)
from runtime import *
from release import contamination
from runner import plan
from copy import deepcopy


def rejection(fn):
    try:fn()
    except (ValueError,PermissionError):return True
    raise AssertionError('Fault injection was not rejected')


def review_check(rows):
    issues=[];counts={}
    for role in ('producer','auditor'):
        p=HERE/'blind_review'/role/'review.json'
        if not p.exists():issues.append(role+': missing blind review');continue
        review=read(p);packets=HERE/'blind_review'/role/'packets.json'
        if review['input_sha256']!=sha(packets.read_bytes()):issues.append(role+': stale blind review');continue
        reviewed={r['example_id']:r for r in review['rows']};rr=[r for r in rows if r['role']==role]
        if set(reviewed)!={r['example_id'] for r in rr}:issues.append(role+': incomplete review coverage');continue
        disagreement=[]
        for r in rr:
            v=reviewed[r['example_id']]
            if role=='auditor':
                if v['prediction']!=r['relation'] or v.get('invalid_task'):disagreement.append(r['example_id'])
            else:
                gold=r['typed_label'];expected='refused' if refused(target(r)) else 'empty' if not r['substantive'] else 'extracted'
                if v['predicted_status']!=expected:disagreement.append(r['example_id']);continue
                if not refused(target(r)):
                    predicted=[sem.normalize(a) for i in v['items'] for a in i['atoms']]
                    actual=[sem.normalize(a) for i in gold['items'] for a in i['gap_atoms']+i['uncertainty_atoms']]
                    if sorted(map(sha,predicted))!=sorted(map(sha,actual)):disagreement.append(r['example_id'])
        counts[role]=dict(reviewed=len(reviewed),disagreements=disagreement,input_sha256=review['input_sha256'])
        if disagreement:issues.append(role+': '+str(len(disagreement))+' unresolved blind label disagreements')
    return dict(counts=counts,blockers=issues,human_reviews=0,method='Fresh agent input-only contexts; shared filesystem, no OS sandbox claim. Producer shares frozen ontology; auditor independent text comparison.')


def run():
    rows=read(HERE/'dataset.json');splits=read(HERE/'splits.json');audit=read(HERE/'run1_audit.json')
    require(len({r['example_id'] for r in rows})==len(rows),'Duplicate dataset IDs')
    for role,minimum in [('producer',256),('auditor',280)]:
        signatures=[sha(r['semantic_signature']) for r in rows if r['role']==role and r['substantive']]
        require(len(signatures)>=minimum and len(signatures)==len(set(signatures)),'Substantive expansion insufficient or duplicate')
    for name,digest in audit['inputs'].items():require(sha((ROOT/name).read_bytes())==digest,'Run-1 evidence changed: '+name)
    receipt=ROOT/'docs/fix/first_real_tuning_20260916/downloaded/runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json'
    require(not receipt.exists(),'Unexpected protected receipt')
    for name,digest in read(ROOT/'tuning/first_domain_agnostic_v1/experiment.json')['protected_component_hashes'].items():
        require(sha((ROOT/name).read_bytes())==digest,'Protected control changed')
    for row in rows:
        require(contract(row,target(row)),'Invalid target contract')
        if row['role']=='producer':require(sem.validate_label(row['typed_label'],row['input'])==target(row),'Renderer mismatch')
    split_results=[check_split(rows,f) for f in splits['folds']]
    check_split(rows,splits['canonical'])
    require(Counter(i for f in splits['folds'] for i in f['validation'])==Counter(r['example_id'] for r in rows),'CV coverage')
    require(splits['canonical']['validation']==splits['folds'][0]['validation'],'Canonical changed after CV')
    leakage=contamination(rows)
    encoded_counts={};plans=[];fixture_metrics={}
    for role in ('producer','auditor'):
        tok=old.tokenizer(role);spec=read(HERE/role/'experiment.json');rr=[r for r in rows if r['role']==role]
        for r in rr:
            e=encode(r,tok)
            require(len(e['input_ids'])<=spec['max_seq_length'],'Sequence ceiling')
            require(e['target_length']<=spec['generation']['max_new_tokens'],'Generation cap')
            require(all(x==-100 for x in e['labels'][:e['prompt_length']]),'Prompt loss contamination')
        encoded_counts[role]=len(rr)
        for split in ['canonical','0','1','2','3','4']:plans.append(plan(role,split,rows))
        oracle=[score(r,old.canonical(target(r)).decode()) for r in rr]
        m=aggregate(oracle);require(selection_pass(m,spec['selection_gates']),'Perfect fixture rejected')
        collapse=aggregate([score(r,'{"items":[],"status":"refused"}') for r in rr])
        require(not selection_pass(collapse,spec['selection_gates']),'Refusal-collapse fixture admitted')
        malformed=aggregate([score(r,'{"items":[{"claims":null,"span":[]}]}') for r in rr])
        require(not selection_pass(malformed,spec['selection_gates']),'Malformed fixture admitted')
        poisoned=deepcopy(m);poisoned['contract_validity']=float('nan')
        require(not selection_pass(poisoned,spec['selection_gates']),'Nonfinite gate metric admitted')
        fold_metrics=[aggregate([s for s in oracle if s['example_id'] in f['validation']]) for f in splits['folds']]
        fixture_metrics[role]=dict(oracle= m,all_refusal=collapse,cv_aggregation=cv_summary(fold_metrics),purpose='Synthetic deterministic metric tests, not measured model performance')
    faults={}
    changed=deepcopy(splits['folds'][0]);changed['validation'].append(changed['train'][0])
    faults['membership_overlap']=rejection(lambda:check_split(rows,changed))
    changed_rows=deepcopy(rows);a=next(r for r in changed_rows if r['example_id'] in splits['folds'][0]['train']);b=next(r for r in changed_rows if r['example_id'] in splits['folds'][0]['validation'])
    for field in GROUP_FIELDS:
        altered=deepcopy(rows);next(r for r in altered if r['example_id']==a['example_id'])[field]=b[field]
        faults[field+'_crossing']=rejection(lambda altered=altered:check_split(altered,splits['folds'][0]))
    changed_rows=deepcopy(rows);changed_rows[0]['parent_ids']=['unknown-parent']
    faults['unknown_ancestry']=rejection(lambda:check_split(changed_rows,splits['folds'][0]))
    for field in ('input','semantic_signature'):
        changed_rows=deepcopy(rows);next(r for r in changed_rows if r['example_id']==a['example_id'])[field]=b[field]
        faults[field+'_duplicate']=rejection(lambda:check_split(changed_rows,splits['folds'][0]))
    changed_rows=deepcopy(rows);next(r for r in changed_rows if r['example_id']==a['example_id'])['parent_ids']=[b['example_id']]
    faults['ancestry_crossing']=rejection(lambda:check_split(changed_rows,splits['folds'][0]))
    changed_rows=deepcopy(rows);changed_rows[0]['example_id']=read(ROOT/'tuning/first_domain_agnostic_v1/protected_population.json')['metadata'][0]['example_id']
    faults['protected_metadata_contamination']=rejection(lambda:contamination(changed_rows))
    faults['protected_read']=rejection(lambda:read(ROOT/'benchmark/task_semantics/seed.json'))
    faults['weight_read']=rejection(lambda:(HERE/'nonexistent.safetensors').read_bytes())
    reviews=review_check(rows)
    blockers=list(reviews['blockers'])
    # Blind reviewers' unresolved population-level concerns must be adjudicated
    # explicitly; a label match alone cannot certify substantial expansion.
    adjudication=read(HERE/'review_adjudication.json') if (HERE/'review_adjudication.json').exists() else {}
    for role in ('producer','auditor'):
        path=HERE/'blind_review'/role/'review.json'
        if path.exists() and adjudication.get('review_sha256',{}).get(role)!=sha(path.read_bytes()):blockers.append(role+': adjudication not bound to final review')
    if not adjudication.get('substantive_expansion_accepted',False):blockers.append('Substantive expansion review not accepted')
    if adjudication.get('unresolved_blockers'):blockers.extend(adjudication['unresolved_blockers'])
    result=dict(passed=True,verdict='SECOND_TUNING_EXPERIMENT_DESIGN_NOT_READY' if blockers else 'SECOND_TUNING_EXPERIMENT_DESIGN_READY',
        readiness_blockers=blockers,encoded_rows=encoded_counts,folds=split_results,leakage=leakage,
        fault_injection=faults,reviews=reviews,access=access,
        planned_cv=dict(role_runs=10,optimizer_updates=1200,example_visits=4800,validation_generations=1200),
        planned_canonical=dict(role_runs=2,optimizer_updates=240,example_visits=960,validation_generations=240),
        execution=dict(training=False,generation=False,cloud=False,paid_api=False,weight_changes=False,full_pipeline=False,multi_round=False,push=False),
        limitations=['Dry-run runner materializes plans. Future train.py is implemented but not model-tested; it requires separate role/split/release-bound authorization. No protected path exists in V2.',
                    'Five conservative structural leakage groups; 600 document IDs are not 600 statistically independent template families.',
                    'Alternative generated auditor rationales require independent adjudication; unknown reason correctness fails accepted-outcome gates.'])
    write(HERE/'plans.json',plans);write(HERE/'metric_fixture_evidence.json',fixture_metrics)
    write(HERE/'dry_run_evidence.json',result)
    print(json.dumps(dict(verdict=result['verdict'],blockers=blockers,encoded_rows=encoded_counts,fault_checks=len(faults)),indent=2))


if __name__=='__main__':run()
