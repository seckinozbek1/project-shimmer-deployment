"""Benchmark v2: review/access/statistical controls, with frozen v1 adapters.

No inference or training. Independent human provenance must be supplied by a
reviewer; this module cannot create it or certify a person's identity.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
V1=ROOT/'benchmark/task_semantics'
sys.path.insert(0,str(V1))
import core as baseline

VERSION='semantic-benchmark-v2'
CONTRACT='semantic-task-v1'
read,write,digest=baseline.read,baseline.write,baseline.digest
REASONS=('preserved_claim','missing_claim','added_claim','changed_label','changed_quantity',
         'changed_unit','gap_preserved','gap_omitted','evidence_insufficient',
         'unsupported_attribution','ambiguity','uncertainty_preserved','uncertainty_omitted')


def now():return datetime.now(timezone.utc).isoformat()


def verify_baseline():
    reference=read(HERE/'baseline_reference.json')
    for name,expected in reference['hashes'].items():
        if digest((ROOT/name).read_bytes())!=expected:
            raise ValueError('Immutable v1 baseline changed: '+name)
    baseline.verify_freeze()
    return len(reference['hashes'])


def verify_freeze():
    freeze=read(HERE/'freeze.json')
    for name,expected in freeze['hashes'].items():
        if digest((HERE/name).read_bytes())!=expected:raise ValueError('Benchmark freeze changed: '+name)
    return True


def validate(records, metadata, domain_policy):
    result=baseline.leakage(records)
    index={r['example_id']:r for r in records}
    if set(index)!=set(metadata):raise ValueError('Missing or extra benchmark metadata')
    forbidden=set(domain_policy['held_out_domains'])|set(domain_policy['sealed_domain_reservations'])
    for row in records:
        meta=metadata[row['example_id']]
        if meta['dataset_version']!=VERSION or meta['production_contract']!=CONTRACT:
            raise ValueError('Benchmark/production version mismatch')
        if row['split'] in ('train','dev') and row['domain'] in forbidden:
            raise ValueError('Domain-holdout leakage')
        if row['domain'] in domain_policy['sealed_domain_reservations']:
            raise ValueError('Reserved blind domain cannot be populated by public author')
        if row['provenance']['privacy']!='authored_public_synthetic':raise ValueError('Private input excluded')
        if meta['independent_review_state']!='pending':raise ValueError('Seed review cannot be self-approved')
        if not set(meta['reason_components'])<=set(REASONS):raise ValueError('Unknown reason component')
    # Explicit second-axis definition; never infer domain holdout from row count.
    observed={r['domain'] for r in records if r['split'] in ('train','dev')}
    if observed!=set(domain_policy['training_access_domains']):raise ValueError('Domain policy mismatch')
    return dict(result,domain_holdout_findings=0)


def review_input(record):
    """Allowlist only. No ID/family/split/gold/transformation/relation label."""
    spans=baseline.ex.ledger(record['source_text'],record['example_id'],record['ledger_max_chars'])
    payload=dict(role=record['role'],production_contract=CONTRACT,
        source_spans=[dict(alias=baseline.ex.wire_id(s),text=s.text) for s in spans if baseline.ex.wire_id(s) in record['owned_aliases']],
        context_only_spans=[dict(alias=baseline.ex.wire_id(s),text=s.text) for s in spans if baseline.ex.wire_id(s) in record['context_only_aliases']],
        supplied_refs=record['supplied_refs'],required_refs=record['required_refs'],routed_rules=record['routed_rules'])
    if record['role']=='auditor':payload['extraction']=record['extraction_text']
    return payload


def packet(record):
    payload=review_input(record)
    binding=digest(payload)
    ident='review-'+binding[:24]
    return dict(packet_version=VERSION,packet_id=ident,input_sha256=binding,input=payload,
        instructions='Review independently without consulting authored labels, split files, or transformation metadata. '
        'Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. '
        'Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. '
        'Auditor item fields: finding, ref_ids, reasoning, severity, confidence. '
        'Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.',
        response_template=dict(packet_id=ident,input_sha256=binding,review_version=VERSION,
            reviewer_id=None,reviewer_kind=None,independence_attestation=False,reviewed_at=None,
            semantic_target=None,semantic_judgment=None,reason_components=[],rationale=None,ambiguity=None,formatting_judgment='not_assessed'))


def make_packets(records, destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    mapping={}
    for row in records:
        p=packet(row)
        # Identical review inputs legitimately share one packet, never fabricate
        # two independent reviews by renaming the same packet.
        mapping.setdefault(p['packet_id'],[]).append(row['example_id'])
        write(destination/(p['packet_id']+'.json'),p)
        text='# Independent semantic review\n\nPacket: '+p['packet_id']+'\n\n'+p['instructions']+'\n\n'
        text+='```json\n'+json.dumps(p['input'],indent=2,ensure_ascii=False)+'\n```\n\n'
        text+='## Response template (pending, not a submitted review)\n\n```json\n'+json.dumps(p['response_template'],indent=2)+'\n```\n'
        (destination/(p['packet_id']+'.md')).write_text(text,encoding='utf-8')
    return mapping


def validate_review(response, p, author_ids):
    required={'packet_id','input_sha256','reviewer_id','reviewer_kind','independence_attestation','reviewed_at',
              'semantic_target','semantic_judgment','reason_components','rationale','ambiguity','formatting_judgment','review_version'}
    if set(response)!=required:raise ValueError('Review fields missing or unexpected')
    if response['packet_id']!=p['packet_id'] or response['input_sha256']!=p['input_sha256']:
        raise ValueError('Review input binding mismatch')
    if response['review_version']!=VERSION:raise ValueError('Review version mismatch')
    if response['reviewer_kind']!='human' or response['reviewer_id'] in author_ids or not response['reviewer_id']:
        raise ValueError('Independent human review required; self/machine review excluded')
    if response['independence_attestation'] is not True:raise ValueError('Independence attestation missing')
    timestamp=datetime.fromisoformat(response['reviewed_at'])
    if timestamp.tzinfo is None:raise ValueError('Review date requires timezone')
    if not response['rationale'] or type(response['ambiguity']) is not bool:raise ValueError('Review rationale/ambiguity missing')
    if response['formatting_judgment'] not in ('valid','invalid','not_assessed'):raise ValueError('Formatting judgment invalid')
    if response['semantic_judgment'] not in ('EXTRACTED','EMPTY','MATCH','DIVERGENCE','OMISSION','ADDITION','INSUFFICIENT_EVIDENCE'):
        raise ValueError('Semantic judgment invalid')
    permitted={'EXTRACTED','EMPTY','INSUFFICIENT_EVIDENCE'} if p['input']['role']=='producer' else {'MATCH','DIVERGENCE','OMISSION','ADDITION','EMPTY','INSUFFICIENT_EVIDENCE'}
    if response['semantic_judgment'] not in permitted:raise ValueError('Judgment does not belong to reviewed role')
    if not isinstance(response['reason_components'],list) or not set(response['reason_components'])<=set(REASONS):
        raise ValueError('Typed reason component invalid')
    if not isinstance(response['semantic_target'],dict):raise ValueError('Semantic target required')
    return True


def adjudication_state(record, reviews, resolution=None):
    p=packet(record);authors={record['adjudication']['first_id'],'seed-author-assistant','expansion-author-assistant'}
    if not reviews:return dict(state='pending',independently_reviewed=False,final_target=None)
    if len(reviews)>2:raise ValueError('At most two independent first judgments')
    for response in reviews:
        validate_review(response,p,authors)
        state,valid,obj=baseline.classify(record,json.dumps(response['semantic_target']))
        if valid:
            judgment={'semantic_refusal':'INSUFFICIENT_EVIDENCE','examined_empty':'EMPTY','extracted':'EXTRACTED'}.get(state)
            if state=='fidelity':judgment=obj['items'][0]['finding']
            if judgment!=response['semantic_judgment']:raise ValueError('Semantic judgment contradicts target')
    if len({r['reviewer_id'] for r in reviews})!=len(reviews):raise ValueError('Second reviewer is not independent')
    if len(reviews)==1:
        return dict(state='first_review_received',independently_reviewed=True,final_target=None,
                    authored_agreement=reviews[0]['semantic_target']==record['gold_target'])
    def semantic(r):return {k:r[k] for k in ('semantic_target','semantic_judgment','reason_components','ambiguity')}
    agreement=semantic(reviews[0])==semantic(reviews[1])
    if not agreement and resolution is None:
        return dict(state='disagreement',independently_reviewed=True,final_target=None)
    final=reviews[0]['semantic_target'] if agreement else resolution['final_target']
    if resolution is not None:
        if (not resolution.get('rationale') or not resolution.get('adjudicator_id') or
            resolution.get('input_sha256')!=p['input_sha256'] or resolution['adjudicator_id'] in authors or
            resolution.get('adjudicator_kind')!='human' or resolution.get('independence_attestation') is not True or
            resolution.get('review_version')!=VERSION or not resolution.get('adjudicated_at')):
            raise ValueError('Resolution requires non-author identity, rationale and exact binding')
        if datetime.fromisoformat(resolution['adjudicated_at']).tzinfo is None:raise ValueError('Resolution date requires timezone')
    # Semantic assessment and wire judgment stay separate; incompatible targets
    # cannot silently become labels even if both reviewers call the prose good.
    state,valid,_=baseline.classify(record,json.dumps(final))
    if not valid:raise ValueError('Adjudicated target has invalid compact contract')
    return dict(state='agreed' if agreement else 'adjudicated',independently_reviewed=True,final_target=final,
                input_sha256=p['input_sha256'],formatting_judgments=[r['formatting_judgment'] for r in reviews])


def ingest_review(response, records, journal, resolution=None):
    """Admin-only append-only submissions; never modifies frozen authored labels."""
    journal=Path(journal).resolve()
    if journal.is_relative_to((HERE/'review_packets').resolve()):raise PermissionError('Responses must not be exposed in reviewer packet export')
    by_packet={packet(row)['packet_id']:row for row in records}
    ident=response.get('packet_id')
    if ident not in by_packet:raise ValueError('Unknown review packet')
    record=by_packet[ident]
    journal.mkdir(parents=True,exist_ok=True)
    previous=[read(p) for p in sorted(journal.glob(ident+'-submission-*.json'))]
    if any(r['reviewer_id']==response.get('reviewer_id') for r in previous):raise ValueError('Duplicate reviewer submission')
    state=adjudication_state(record,previous+[response],resolution)
    path=journal/(ident+'-submission-'+digest(response['reviewer_id'])[:20]+'.json')
    with path.open('x',encoding='utf-8') as handle:json.dump(response,handle,indent=2,ensure_ascii=False)
    if state['final_target'] is not None:
        final=dict(state,review_version=VERSION,recorded_at=now(),submission_hashes=[digest(r) for r in previous+[response]],resolution=resolution)
        with (journal/(ident+'-final.json')).open('x',encoding='utf-8') as handle:json.dump(final,handle,indent=2,ensure_ascii=False)
    return dict(packet_id=ident,state=state['state'],submissions=len(previous)+1)


def resolve_review(ident, records, journal, resolution):
    journal=Path(journal).resolve()
    if journal.is_relative_to((HERE/'review_packets').resolve()):raise PermissionError('Admin journal must be separate')
    by_packet={packet(row)['packet_id']:row for row in records}
    if ident not in by_packet:raise ValueError('Unknown review packet')
    reviews=[read(p) for p in sorted(journal.glob(ident+'-submission-*.json'))]
    if len(reviews)!=2:raise ValueError('Two independent submissions required for resolution')
    state=adjudication_state(by_packet[ident],reviews,resolution)
    if state['final_target'] is None:raise ValueError('Explicit final resolution required')
    final=dict(state,review_version=VERSION,recorded_at=now(),submission_hashes=[digest(r) for r in reviews],resolution=resolution)
    with (journal/(ident+'-final.json')).open('x',encoding='utf-8') as handle:json.dump(final,handle,indent=2,ensure_ascii=False)
    return dict(packet_id=ident,state=state['state'])


def assess_reason(record, raw, reason_review):
    """Non-canonical paraphrases require a human, input+output-bound rubric."""
    p=packet(record)
    expected={'packet_id','input_sha256','raw_sha256','reviewer_id','reviewer_kind','independence_attestation',
              'reviewed_at','components','correct','rationale'}
    if set(reason_review)!=expected:raise ValueError('Reason review schema mismatch')
    if (reason_review['packet_id']!=p['packet_id'] or reason_review['input_sha256']!=p['input_sha256'] or
        reason_review['raw_sha256']!=digest(raw.encode('utf-8'))):raise ValueError('Reason review binding mismatch')
    if (reason_review['reviewer_kind']!='human' or reason_review['independence_attestation'] is not True or not reason_review['reviewer_id'] or
        reason_review['reviewer_id'] in {record['adjudication']['first_id'],'expansion-author-assistant','seed-author-assistant'}):
        raise ValueError('Reason requires independent human review')
    if not set(reason_review['components'])<=set(REASONS) or not reason_review['rationale'] or type(reason_review['correct']) is not bool:
        raise ValueError('Reason rubric invalid')
    if datetime.fromisoformat(reason_review['reviewed_at']).tzinfo is None:raise ValueError('Reason date requires timezone')
    result=baseline.evaluate(record,raw,reason_review=dict(raw_sha256=reason_review['raw_sha256'],
        example_id=record['example_id'],state='independently_reviewed',reviewer_id=reason_review['reviewer_id'],
        rationale=reason_review['rationale'],correct=reason_review['correct']))
    result['reason_components']=reason_review['components']
    return result


def training_records(records, metadata, domain_policy):
    validate(records,metadata,domain_policy)
    return [r for r in records if r['split'] in ('train','dev') and r['domain'] in domain_policy['training_access_domains']]


def export_training(records, metadata, policy, destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    allowed=training_records(records,metadata,policy)
    for split in ('train','dev'):write(destination/(split+'.json'),[r for r in allowed if r['split']==split])
    manifest=dict(version=VERSION,purpose='future_training_selection_only_not_training_authorization',
        allowed_files={s+'.json':digest((destination/(s+'.json')).read_bytes()) for s in ('train','dev')},
        allowed_ids=[r['example_id'] for r in allowed],forbidden_splits=['test','sealed_adversarial','regression'],
        held_out_domains=policy['held_out_domains'],operator_data=False,durable_state=False)
    write(destination/'manifest.json',manifest)
    return manifest


def load_training_file(root, name, trusted_manifest):
    """Only names in the caller's frozen manifest; reject escape/symlink reads."""
    root=Path(root).resolve()
    if name not in trusted_manifest['allowed_files']:raise PermissionError('Not a tuning-access file')
    path=(root/name).resolve()
    if path.parent!=root or (root/name).is_symlink():raise PermissionError('Tuning path escape')
    raw=path.read_bytes()
    if digest(raw)!=trusted_manifest['allowed_files'][name]:raise ValueError('Training-view integrity mismatch')
    rows=json.loads(raw)
    if any(r['split'] not in ('train','dev') or r['example_id'] not in trusted_manifest['allowed_ids'] or
           r['domain'] in trusted_manifest['held_out_domains'] for r in rows):raise PermissionError('Held-out row in training view')
    return rows


def sealed_manifest():
    return dict(version=VERSION,state='PENDING_INDEPENDENT_CONTRIBUTION',populated_examples=0,labels_sha256=None,
                storage='external_operator_controlled_vault_required',normal_development_access=False,
                final_mode_required=True,results_append_only=True,
                warning='Repository application controls are not OS isolation. Operator must use a separate account/ACL for real labels.')


def audit_public_artifacts(paths, protected_value_hashes):
    """Check public outputs using contributed hashes, without opening a vault."""
    def protected_digests(value):
        if isinstance(value,str):yield digest(value.encode('utf-8'))
        elif isinstance(value,dict):
            yield digest(value)
            for item in value.values():yield from protected_digests(item)
        elif isinstance(value,list):
            yield digest(value)
            for item in value:yield from protected_digests(item)
    findings=[]
    for path in paths:
        path=Path(path);raw=path.read_bytes()
        values={digest(raw)}
        if path.suffix=='.json':values.update(protected_digests(json.loads(raw)))
        if values & set(protected_value_hashes):
            findings.append(dict(path=path.name,classification='sealed_answer_exposure'))
    if findings:raise ValueError('Sealed answer exposure in '+','.join(r['path'] for r in findings))
    return dict(files=len(paths),sealed_answer_findings=0)


def read_sealed(vault, mode, permit):
    vault=Path(vault).resolve()
    if mode!='final_evaluation':raise PermissionError('Explicit final-evaluation mode required')
    if vault.is_relative_to(ROOT.resolve()):raise PermissionError('Real sealed vault must be outside repository')
    if (permit.get('purpose')!='final_evaluation_only' or permit.get('operator_authorized') is not True or
        not permit.get('acceptance_registration_sha256') or not permit.get('model_candidate_sha256')):
        raise PermissionError('Final evaluation permit incomplete')
    manifest=read(vault/'manifest.json')
    if manifest.get('state')!='independently_populated' or manifest.get('independence_attestation') is not True:
        raise PermissionError('No independently contributed final labels')
    original=vault/'labels.json';path=original.resolve()
    if path.parent!=vault or original.is_symlink():raise PermissionError('Sealed path escape')
    raw=path.read_bytes()
    if digest(raw)!=manifest['labels_sha256'] or manifest['labels_sha256']!=permit.get('labels_sha256'):
        raise ValueError('Sealed label integrity/binding mismatch')
    return json.loads(raw)


def seal_contribution(vault, records, attestation):
    """Independent contributor operation, not used to relabel this public seed."""
    vault=Path(vault).resolve()
    if vault.is_relative_to(ROOT.resolve()):raise PermissionError('Sealed contribution belongs outside repository')
    if (attestation.get('contributor_kind')!='human' or attestation.get('independent_material') is not True or
        not attestation.get('contributor_id') or attestation['contributor_id'] in {'seed-author-assistant','expansion-author-assistant'} or
        attestation.get('operator_authorized') is not True):raise PermissionError('Independent human contribution and authorization required')
    if not records:raise ValueError('Empty final contribution')
    ids=set()
    for row in records:
        if row['example_id'] in ids:raise ValueError('Duplicate sealed example')
        ids.add(row['example_id'])
        if (row['adjudication']['state'] not in ('independently_reviewed','adjudicated') or
            not row['adjudication']['second_id'] or row['adjudication']['second_judgment'] is None or
            row['adjudication']['second_id']==row['adjudication']['first_id']):
            raise ValueError('Independent review required before sealing')
        if row['provenance']['privacy']!='independent_synthetic_sealed':raise ValueError('Public authored/operator material cannot be relabeled blind')
        if not baseline.classify(row,json.dumps(row['gold_target']))[1]:raise ValueError('Invalid sealed target contract')
    vault.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(records,indent=2,ensure_ascii=False)+'\n').encode('utf-8')
    with (vault/'labels.json').open('xb') as file:file.write(raw)
    manifest=dict(version=VERSION,state='independently_populated',examples=len(records),labels_sha256=digest(raw),
        independence_attestation=True,contributor_id=attestation['contributor_id'],contributed_at=now(),
        attestation_sha256=digest(attestation),label_value_hashes=[digest(r['gold_target']) for r in records])
    with (vault/'manifest.json').open('x',encoding='utf-8') as file:json.dump(manifest,file,indent=2)
    return {k:manifest[k] for k in ('version','state','examples','labels_sha256')}


def append_final_result(vault, run_id, summary, permit):
    """Exclusive-create hash-chained log; no label/response content accepted."""
    vault=Path(vault)
    if not run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in run_id):
        raise ValueError('Unsafe final run ID')
    if set(summary)!={'candidate_count','accepted_count','contract_count','truncated_count'}:
        raise ValueError('Only aggregate final results may leave evaluator')
    results=vault/'results';results.mkdir(exist_ok=True)
    lock=results/'.writer.lock'
    with lock.open('x',encoding='utf-8') as handle:handle.write(run_id)
    try:
        previous=None
        for file in sorted(results.glob('*.json')):
            item=read(file)
            if item['previous_sha256']!=previous:raise ValueError('Final log history changed')
            previous=digest(file.read_bytes())
        if any(read(p)['run_id']==run_id for p in results.glob('*.json')):raise FileExistsError('Final run already recorded')
        value=dict(run_id=run_id,recorded_at=now(),summary=summary,permit_sha256=digest(permit),previous_sha256=previous)
        target=results/(str(len(list(results.glob('*.json')))).zfill(6)+'-'+run_id+'.json')
        with target.open('x',encoding='utf-8') as handle:json.dump(value,handle,indent=2)
        return digest(target.read_bytes())
    finally:lock.unlink()


def final_evaluate(vault, mode, permit, candidates, run_id):
    labels=read_sealed(vault,mode,permit)
    if digest(candidates)!=permit['model_candidate_sha256']:raise ValueError('Final candidate binding mismatch')
    label_ids={r['example_id'] for r in labels};candidate_ids={r['example_id'] for r in candidates}
    if len(labels)!=len(candidates) or len(label_ids)!=len(labels) or len(candidate_ids)!=len(candidates) or label_ids!=candidate_ids:
        raise ValueError('Final evaluation must cover every frozen example exactly once')
    index={r['example_id']:r for r in labels}
    scored=[baseline.evaluate(index[r['example_id']],r['raw'],truncated=r['truncated'],completed=r['completed']) for r in candidates]
    summary=dict(candidate_count=len(scored),accepted_count=sum(r['accepted_outcome'] for r in scored),
                 contract_count=sum(r['contract_valid'] for r in scored),truncated_count=sum(r['truncated'] for r in scored))
    append_final_result(vault,run_id,summary,permit)
    return summary


def family_statistics(scores, records, seed=1701, draws=1000):
    index={r['example_id']:r for r in records}
    dimensions=('document_family','template_family','domain')
    result={}
    for dimension in dimensions:
        groups=defaultdict(list)
        for row in scores:groups[index[row['example_id']][dimension]].append(row)
        details={key:baseline.aggregate(values) for key,values in groups.items()}
        observations=defaultdict(list)
        def rates(value,prefix=''):
            if not isinstance(value,dict):return
            if {'tp','fp','fn'}<=set(value) and value['tp']+value['fp']+value['fn']==0:return
            for key,item in value.items():
                path=prefix+'.'+key if prefix else key
                if key in ('rate','precision','recall') and isinstance(item,(int,float)):yield path,item
                elif isinstance(item,dict):yield from rates(item,path)
        for detail in details.values():
            for path,value in rates({'aggregate':detail['aggregate'],'per_role':detail['per_role']}):observations[path].append(value)
        macros={path:dict(mean=statistics.mean(values),contributing_groups=len(values)) for path,values in observations.items()}
        means=[sum(r['accepted_outcome'] for r in values)/len(values) for values in groups.values()]
        interval=None
        if len(means)>=8:
            rng=random.Random(seed)
            samples=sorted(statistics.mean(rng.choices(means,k=len(means))) for _ in range(draws))
            interval=[samples[int(.025*draws)],samples[min(draws-1,int(.975*draws))]]
        result[dimension]=dict(group_count=len(groups),per_group=details,
            metric_macros=macros,
            macro_accepted_outcome=statistics.mean(means) if means else None,
            range_accepted_outcome=[min(means),max(means)] if means else None,
            exploratory_cluster_bootstrap95=interval,bootstrap_unit=dimension,draws=draws,
            warning='Exploratory equal-weight group bootstrap, not row CI. Authored targets are not model trials; higher-level shared ancestry limits independence. Fewer than 8 groups: interval withheld.')
    return result


def acceptance(scores, specification, context):
    catastrophic_counts=dict(invented_evidence=sum(r.get('catastrophic',{}).get('invented_evidence',False) for r in scores),
        unrouted_rule_attribution=sum(r.get('catastrophic',{}).get('invented_rule',False) for r in scores),
        confident_wrong_match_divergence=sum(r.get('catastrophic',{}).get('incorrect_confident_judgment',False) for r in scores),
        truncation=sum(r.get('truncated',False) for r in scores),producer_source_copy=sum(r.get('copied_source_violation',False) for r in scores),
        governance_violations=context.get('governance_violations',0))
    if any(v=='REQUIRES_OPERATOR_REGISTRATION' for role in specification['thresholds'].values() for v in role.values()):
        return dict(verdict='NOT_REGISTERED',blocking='Quality thresholds require prospective operator registration',catastrophic_counts=catastrophic_counts)
    if any(catastrophic_counts[k]>limit for k,limit in specification['catastrophic_limits'].items()):
        return dict(verdict='CATASTROPHIC_FAILURE',catastrophic_counts=catastrophic_counts)
    if (context.get('specification_sha256')!=digest(specification) or not context.get('registered_before_run') or
        not context.get('independent_review_sufficient') or not context.get('governance_verified') or
        not context.get('heldout_domain_verified') or not context.get('unseen_template_verified')):
        return dict(verdict='CONTEXT_INCOMPLETE')
    # v2 intentionally cannot approve a model by merely filling a template. The
    # next registered release must implement each quantitative operator rule.
    return dict(verdict='REQUIRES_REGISTERED_RULE_IMPLEMENTATION',blocking='No arbitrary default thresholds or aggregate-F1 shortcut')
