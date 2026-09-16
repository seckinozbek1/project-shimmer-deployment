"""Freeze a local-only dataset/design release. Does not execute training."""
import argparse
import math
from collections import Counter
from pathlib import Path
from runtime import *
from audit_run1 import components
from author import build

# Conservative structural superfamilies bind superficially different renderers.
# Every layout is held out; domain is a stratification factor, not an ancestry ID.
STRUCTURES={
    'sectioned': ['memo','meeting_minutes','incident_report','structured_notice'],
    'tabular': ['compact_table','multi_row_table','comparison_matrix','mixed_prose_table'],
    'enumerated': ['bullet_list','checklist','nested_clauses','form_fields'],
    'anchored': ['timeline','register','machine_log','footnoted_record'],
    'discourse': ['prose','question_answer','correspondence','dialogue'],
}
GATES={
    'producer':dict(minimum=dict(contract_validity=1.,typed_gaps_f1=.80,semantic_completeness=.75,
        claims_f1=.95,evidence_f1=.95,typed_uncertainty_f1=.80,refusal_precision=.90,refusal_recall=.80,
        accepted_semantic_outcomes=.75),maximum=dict(over_refusal_rate=.05)),
    'auditor':dict(minimum=dict(contract_validity=1.,refusal_precision=.90,refusal_recall=.80,
        substantive_non_refusal_coverage=.90,accepted_semantic_outcomes=.70,macro_relation_f1=.75,evidence_f1=.85),
        maximum=dict(over_refusal_rate=.05),per_class_recall={c:.60 for c in CLASSES}),
}


def contamination(rows):
    """Use only existing identifier/fingerprint metadata, never target sources."""
    protected=read(ROOT/'tuning/first_domain_agnostic_v1/protected_population.json')
    family=read(ROOT/'benchmark/task_semantics_v2/family_manifest.json')
    mapping=read(ROOT/'benchmark/task_semantics_v2/review_admin_mapping.json')
    known_ids={r['example_id'] for r in family}|{r['example_id'] for r in protected['metadata']}
    known_families={r['document_family'] for r in family}|{r['document_family'] for r in protected['metadata']}
    require(not known_ids&{r['example_id'] for r in rows},'Legacy/protected/regression ID contamination')
    require(not known_families&{r['document_family'] for r in rows},'Legacy/protected/regression family contamination')
    packet_prefixes={k.removeprefix('review-') for k in mapping['packet_to_examples']}
    for r in rows:
        # Old review packet IDs use the first 24 characters of canonical packet
        # hashes. Check both historical serialization conventions.
        candidates=[sha(r['input']),core.digest(r['input'])]
        require(not any(x[:24] in packet_prefixes for x in candidates),'Legacy packet fingerprint collision')
    return dict(passed=True,protected_population=len(protected['metadata']),metadata_ids_checked=len(known_ids),
        legacy_packet_fingerprints=len(packet_prefixes),findings=[],
        protected_target_reads=0,regression_policy='No legacy fixture used as authoring input; IDs/families and all available review packet fingerprints excluded.',
        limits='Metadata/fingerprint and provenance checks, not a semantic-similarity search over protected text. Protected target files are never opened.',
        original_protected_source_hashes=protected['target_source_hashes'])


def make():
    rows=build()
    for r in rows:
        rendering=r['template_family'];structure=next(k for k,v in STRUCTURES.items() if rendering in v)
        r.update(rendering_template=rendering,template_family=structure,leakage_group='v2-structure-'+structure)
        require(contract(r,target(r)),'Invalid authored contract: '+r['example_id'])
    write(HERE/'dataset.json',rows)
    # Equal-size superfamilies already have balanced class/domain coverage.
    groups=sorted({r['leakage_group'] for r in rows},key=lambda g:sha(['split_seed',29,g]))
    folds=[]
    for fold,group in enumerate(groups):
        value=dict(fold=fold,seed=29,validation_groups=[group],
            train=[r['example_id'] for r in rows if r['leakage_group']!=group],
            validation=[r['example_id'] for r in rows if r['leakage_group']==group])
        value['statistics']=check_split(rows,value);folds.append(value)
    canonical=dict(folds[0],name='canonical',frozen_before_cv_results=True)
    require(Counter(i for f in folds for i in f['validation'])==Counter(r['example_id'] for r in rows),'CV exact-once failure')
    write(HERE/'splits.json',dict(seed=29,allocation='Hash-order of five equal-size, relation-balanced conservative structural superfamilies; canonical=fold0 fixed before results.',
        group_fields=list(GROUP_FIELDS),domain_policy='Mixed-domain strata; no domain holdout claim. New astronomy/ecology sources do not alter run-1 eligibility.',
        structural_groups=STRUCTURES,canonical=canonical,folds=folds))
    totals=stats(rows)
    token_report={};specs={}
    for role in ('producer','auditor'):
        tok=old.tokenizer(role); rr=[r for r in rows if r['role']==role]
        comp=Counter();lengths=[];byclass={}
        for r in rr:
            encoded=encode(r,tok);counts=components(target(r),tok);comp.update(counts)
            lengths.append(dict(example_id=r['example_id'],prompt=encoded['prompt_length'],target=encoded['target_length'],total=len(encoded['input_ids'])))
            cls=r.get('relation','REFUSAL' if refused(target(r)) else 'EXTRACTED')
            byclass.setdefault(cls,[]).append(encoded['target_length'])
        canonical_train=set(canonical['train']);train_comp=Counter()
        for r in rr:
            if r['example_id'] in canonical_train:train_comp.update(components(target(r),tok))
        supervised=sum(x['target'] for x in lengths)
        train_supervised=sum(x['target'] for x in lengths if x['example_id'] in canonical_train)
        token_report[role]=dict(all_components=dict(comp),all_percent={k:100*v/sum(comp.values()) for k,v in comp.items()},
            canonical_train_components=dict(train_comp),canonical_train_percent={k:100*v/sum(train_comp.values()) for k,v in train_comp.items()},
            native_termination_tokens=sum(x['target'] for x in lengths)-sum(comp.values()),
            all_supervised_tokens=supervised,canonical_train_supervised_tokens=train_supervised,
            all_supervised_percent={k:100*v/supervised for k,v in dict(comp,native_termination=supervised-sum(comp.values())).items()},
            canonical_train_supervised_percent={k:100*v/train_supervised for k,v in dict(train_comp,native_termination=train_supervised-sum(train_comp.values())).items()},
            lengths=lengths,target_lengths_by_class={k:dict(min=min(v),max=max(v),mean=mean(v)) for k,v in byclass.items()},
            attribution='Actual tokenizer offsets; midpoint token attribution. Typed atom JSON inside strings counts under its semantic component, not just semantic value tokens.')
        oldspec=read(ROOT/f'tuning/first_domain_agnostic_v1/{role}/experiment.json')
        spec={k:oldspec[k] for k in ('model_id','revision','asset_hashes','architecture','quantization','lora','training','generation','terminal_token_ids')}
        spec['training']=dict(spec['training'],steps_per_epoch=60,max_steps=120,data_epochs=2,warmup_steps=1,
            last_accumulation_group='actual group mean; 240 examples divide evenly into groups of four')
        spec['generation']=dict(spec['generation'],max_new_tokens=32*math.ceil((max(x['target'] for x in lengths)+32)/32))
        spec.update(experiment='second-domain-agnostic-v2',role=role,checkpoint_steps=[60,120],
            max_seq_length=32*math.ceil(max(x['total'] for x in lengths)/32),dataset_sha256=sha((HERE/'dataset.json').read_bytes()),
            selection_gates=GATES[role],objective='Per-example mean cross entropy over assistant target plus native termination only; equal example weights, no component weighting.',
            configuration_reason='Retain rank8, seven projection modules, lr1e-4, two passes and example-average objective: run-1 does not isolate rank/LR as causes; gaps already 40.17% of Producer TRAIN tokens and auditor TRAIN classes were 8/9/9/9/11. Change corpus, validation and prospective semantic gates. Updates scale with two passes; evaluate once per pass to limit generation overhead.',
            training_authorized=False,execution_mode='dry_run_only',tokenizer_only=True)
        spec['base_weight_hashes']={'model.safetensors':('99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d' if role=='producer' else 'e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a')}
        spec['base_weight_hash_provenance']='Preserved run-1 results report; weights not opened during V2 design/dry-run.'
        specs[role]=spec;write(HERE/role/'experiment.json',spec)
    write(HERE/'token_analysis.json',token_report)
    write(HERE/'statistics.json',totals)
    write(HERE/'leakage_audit.json',contamination(rows))
    write(HERE/'selection_rules.json',dict(gates=GATES,catastrophic_zero_limits=['invented_evidence','invented_rule','confident_wrong_match_divergence','truncation','producer_source_copy','governance_violations'],
        thresholds='Prospective engineering requirements, not empirically calibrated or tuned on V2 outputs. Undefined metrics fail closed.',
        producer_ranking=['semantic_completeness','typed_gaps_f1','earliest_step','adapter_hash'],
        auditor_ranking=['macro_relation_f1','accepted_semantic_outcomes','earliest_step','adapter_hash'],
        cv_rule='Use identical configurations across folds; no per-fold hyperparameter changes; no aggregate score selects configurations.',
        canonical_rule='Select only canonical DEV checkpoint after all gates; CV never changes canonical membership.',
        protected_rule='No protected execution path in V2. Existing one-shot controls remain untouched; future BASE-vs-tuned admission requires separate authorization.'))
    for role in ('producer','auditor'):
        folder=HERE/'blind_review'/role;folder.mkdir(parents=True,exist_ok=True)
        write(folder/'packets.json',[dict(example_id=r['example_id'],input=r['input']) for r in rows if r['role']==role])
    print({role:dict(rows=totals[role]['rows'],substantive=totals[role]['substantive'],max_seq=specs[role]['max_seq_length'],generation_cap=specs[role]['generation']['max_new_tokens']) for role in totals})


def freeze():
    require((HERE/'dry_run_evidence.json').exists(),'Dry-run evidence required')
    report=read(HERE/'dry_run_evidence.json')
    require(report['passed'],'Dry-run failed')
    files={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(HERE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='freeze.json'}
    write(HERE/'freeze.json',dict(release='second-domain-agnostic-v2',training_authorized=False,files=files,
        readiness=report['verdict'],protected_target_accesses=0,
        dependency_files={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in [
            ROOT/'tuning/first_domain_agnostic_v1/common.py',ROOT/'tuning/first_domain_agnostic_v1/dependency_lock.json',
            ROOT/'tuning/first_domain_agnostic_v1/experiment.json',ROOT/'scripts/compact_contracts.py',ROOT/'scripts/bounded_extraction.py',
            ROOT/'benchmark/producer_coverage_amendment_v3/semantics.py',ROOT/'benchmark/producer_coverage_amendment_v3/structural.py',ROOT/'benchmark/task_semantics/core.py',
            ROOT/'tuning/first_domain_agnostic_v1/producer/experiment.json',ROOT/'tuning/first_domain_agnostic_v1/auditor/experiment.json',
            ROOT/'tuning/first_domain_agnostic_v1/protected_population.json',ROOT/'benchmark/task_semantics_v2/family_manifest.json',
            ROOT/'benchmark/task_semantics_v2/review_admin_mapping.json',
            ROOT/'docs/fix/SECOND_TUNING_DATA_AND_FAILURE_AUDIT.md',ROOT/'docs/fix/SECOND_TUNING_EXPERIMENT_IMPLEMENTATION.md']}))
    print(report['verdict'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args()
    freeze() if args.freeze else make()
