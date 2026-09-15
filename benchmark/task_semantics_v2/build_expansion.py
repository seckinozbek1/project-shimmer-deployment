"""Author structural examples; all allocations precede derivative construction."""
from copy import deepcopy
from pathlib import Path
import json
import re

import hardening as h

HERE=h.HERE
FORMATS={
 'paragraph':('train',lambda a,b,c:f'{a} In a separate statement, {b} Finally, {c}'),
 'bullet_list':('train',lambda a,b,c:f'- {a}\n- {b}\n- {c}'),
 'form_fields':('train',lambda a,b,c:f'ENTRY A = {a}\nENTRY B = {b}\nFOLLOW-UP FIELD = {c}'),
 'chronological_events':('dev',lambda a,b,c:f'08:10 event opened: {a}\n09:25 event amended: {b}\n11:40 follow-up: {c}'),
 'question_answer':('dev',lambda a,b,c:f'Question: What was entered first?\nAnswer: {a}\nQuestion: What followed?\nAnswer: {b}\nClerk note: {c}'),
 'memo_sections':('dev',lambda a,b,c:f'MEMORANDUM\nSubject: retained observations\nDecision recorded: {a}\nSupporting entry: {b}\nUnresolved matters: {c}'),
 'compact_table':('test',lambda a,b,c:f'| Field | Content |\n|---|---|\n| Primary | {a} |\n| Secondary | {b} {c} |'),
 'multirow_table':('test',lambda a,b,c:f'| Sequence | Evidence |\n|---|---|\n| 1 | {a} |\n| 2 | {b} |\n| 3 | {c} |'),
 'mixed_prose_table':('test',lambda a,b,c:f'Opening statement: {a}\n\n| Supplement | Content |\n|---|---|\n| Detail | {b} |\n\nClosing qualification: {c}'),
 'nested_provisions':('sealed_adversarial',lambda a,b,c:f'1. Scope\n  1(a) {a}\n  1(b) Exceptions\n    (i) {b}\n    (ii) {c}'),
 'transaction_register':('sealed_adversarial',lambda a,b,c:f'BEGIN REGISTER\nDEBIT OBSERVATION :: {a}\nCREDIT OBSERVATION :: {b}\nMEMO ONLY :: {c}\nEND REGISTER'),
 'machine_records':('sealed_adversarial',lambda a,b,c:f'RECORD{{kind=primary; text="{a}"}}\nRECORD{{kind=secondary; text="{b}"}}\nRECORD{{kind=qualification; text="{c}"}}'),
}
DOMAINS={
 'train':('negotiation','contracts','procurement','device'),
 'dev':('catalogue','regulation','clinical','nonsense'),
 'test':('astronomy','ecology','negotiation','device'),
 'sealed_adversarial':('astronomy','ecology','contracts','nonsense'),
}
VOCAB={
 'negotiation':('delegation','offered seats'), 'contracts':('service desk','delivery windows'),
 'procurement':('vendor','pallets'), 'device':('sensor bank','pulses'),
 'catalogue':('collection','entries'), 'regulation':('filing office','notices'),
 'clinical':('fictional case','recorded events'), 'nonsense':('vraxlet','flomquils'),
 'astronomy':('observing station','exposures'), 'ecology':('survey plot','quadrats'),
}
COMPOUNDS=('wrong_relation_and_irrelevant_ref','claims_preserved_gap_omitted','correct_content_invented_rule',
           'match_missing_evidence','ambiguity_forced_answer','omission_plus_addition','context_and_owned_claim',
           'uncertainty_removed_facts_retained','semantic_content_empty_status')


def gold_source(source,ident,max_chars=1200):
    items=[]
    for span in h.baseline.ex.ledger(source,ident,max_chars):
        if 'CONTEXT ONLY' in span.text:continue
        claims=re.findall(r'\bCLM-[A-Za-z0-9-]+',span.text)
        # Authored questions have explicit bounded punctuation in this corpus;
        # this is construction metadata, not an evaluator heuristic for truth.
        questions=[q.strip(' |\n') for q in re.findall(r'(?:What|When|Who|Where)[^?\n|]*\?',span.text)]
        uncertainty=['The interpretation remains uncertain.'] if 'The interpretation remains uncertain.' in span.text else []
        refs=sorted(set(re.findall(r'\bREF-\d{4,}\b',span.text)))
        items.append(dict(span=h.baseline.ex.wire_id(span),claims=claims,questions=questions,uncertainty=uncertainty,
                          status='extracted' if claims or questions or uncertainty else 'empty',refs=refs))
    return {'items':items}


def make_record(prototype, family, template, split, domain, source, suffix, role='producer',
                relation='EXTRACTED',extraction='',parent=None,gold=None,tags=(),max_chars=1200):
    row=deepcopy(prototype)
    spans=h.baseline.ex.ledger(source,family,max_chars)
    target=gold if gold is not None else gold_source(source,family,max_chars)
    actual_owned=[s for s in spans if 'CONTEXT ONLY' not in s.text]
    owned_refs=sorted({ref for s in actual_owned for ref in re.findall(r'\bREF-\d{4,}\b',s.text)})
    row.update(example_id=family+'-'+suffix,role=role,task_type='bounded_extraction' if role=='producer' else 'fidelity',
        abstract_relation=relation,domain=domain,document_type=template,language='en',style=template,
        document_family=family,template_family='v2-'+template,derivation_group=family,paraphrase_family=family,
        renamed_family='v2-'+template,near_duplicate_family=family,parent_id=parent,split=split,
        split_plan_id='v2-allocated-before-variants',source_text=source,extraction_text=extraction,ledger_max_chars=max_chars,
        owned_aliases=[h.baseline.ex.wire_id(s) for s in actual_owned],context_only_aliases=[h.baseline.ex.wire_id(s) for s in spans if s not in actual_owned],
        supplied_refs=sorted(set(re.findall(r'\bREF-\d{4,}\b',source))),
        required_refs=[] if relation in ('EMPTY','INSUFFICIENT_EVIDENCE') else owned_refs,
        routed_rules=[],distractor_rules=['CONV-UNROUTED'],gold_target=target,
        expected_refusal=relation=='INSUFFICIENT_EVIDENCE',
        expected_uncertainty=role=='producer' and any(i.get('uncertainty') for i in target['items']),
        hard_negative_tags=list(tags),notes='New public structural fixture. Independent review pending. No domain advice.')
    row['provenance']=dict(source='newly authored structural fixture',rights='project_authored',privacy='authored_public_synthetic',public_regression=False)
    row['adjudication']=dict(state='authored_single',first_id='expansion-author-assistant',first_judgment=deepcopy(target),
        second_id=None,second_judgment=None,agreement='not_reviewed',final_target=deepcopy(target),rationale='Authored construction; independent semantic review required.',ambiguity=False)
    return row


def auditor_target(relation,reason,refs):
    return {'items':[dict(finding=relation,ref_ids=refs,reasoning=reason,severity='low' if relation=='MATCH' else 'medium',confidence='CONFIDENT')]}


def main():
    if (HERE/'baseline_reference.json').exists():h.verify_baseline()
    if (HERE/'freeze.json').exists() and h.read(HERE/'freeze.json')['version']==h.VERSION:
        h.verify_freeze()
    base=h.read(h.V1/'seed.json')
    prototype=next(r for r in base if r['role']=='producer' and r['abstract_relation']=='EXTRACTED')
    allocation=[dict(family=f'v2-{template}-{domain}',template=template,split=split,domain=domain)
                for template,(split,render) in FORMATS.items() for domain in DOMAINS[split]]
    h.write(HERE/'allocation.json',dict(version=h.VERSION,order='before variants',families=allocation))
    extension=[];negatives=[];metadata={}
    for row in base:
        metadata[row['example_id']]=dict(dataset_version=h.VERSION,production_contract=h.CONTRACT,origin='immutable_v1',
             independent_review_state='pending',reason_components=['evidence_insufficient'] if row['expected_refusal'] else [],
             author_id=row['adjudication']['first_id'])
    for number,plan in enumerate(allocation):
        family,template,split,domain=(plan[k] for k in ('family','template','split','domain'))
        render=FORMATS[template][1];entity,unit=VOCAB[domain]
        # Independent names/numeric instances per document; variants below are
        # explicitly same-family descendants, not independent sample inflation.
        name=f'{entity} {number+41}'
        quantity=17+number*3
        a=f'CLM-A: {name} recorded {quantity} {unit} (REF-1001).'
        b=f'CLM-B: {name} retained {quantity+5} {unit} (REF-1002).'
        if number%4==0:b='No second claim was submitted.'
        c='The date is absent. When was this recorded?'
        if number%3==0:c+=' The recorder is unnamed. Who recorded it?'
        if number%2==0:c+=' The interpretation remains uncertain.'
        source=render(a,b,c)
        root=make_record(prototype,family,template,split,domain,source,'primary')
        extension.append(root)
        # A second authored scenario preserves an explicit contradiction rather
        # than resolving it: same entity, different quantities, distinct claim IDs.
        follow=render(f'CLM-C: {name} is assigned {quantity} {unit} (REF-1003).',
                      f'CLM-D: the same {name} is assigned {quantity+2} {unit} (REF-1004).',
                      'These statements conflict. The effective time is missing. When does it take effect? The interpretation remains uncertain.')
        boundary=len(follow)+2
        if 'table' in template:
            follow+='\n\n| External | Content |\n|---|---|\n| CONTEXT ONLY | CLM-Z: an unrelated neighbor lists a separate observation (REF-9999). |'
            boundary=1200
        else:
            follow+='\n\nCONTEXT ONLY: CLM-Z: an unrelated neighbor lists a separate observation (REF-9999).'
        semantic=make_record(prototype,family,template,split,domain,follow,'conflicting',parent=root['example_id'],max_chars=boundary)
        if not semantic['context_only_aliases']:raise ValueError('Context fixture failed to create a separate source span')
        extension.append(semantic)
        empty_source=re.sub(r'(?:What|When|Who|Where)[^?\n|]*\?','',render('Divider for '+name+'.','No semantic entry.','End marker.'))
        empty=make_record(prototype,family,template,split,domain,empty_source,'empty',
                          relation='EMPTY',parent=root['example_id'])
        extension.append(empty)
        refusal=make_record(prototype,family,template,split,domain,render('Unreadable entry for '+name+'.','[unrecoverable fragment]','The semantic content cannot be established.'),
                    'refusal',relation='INSUFFICIENT_EVIDENCE',parent=root['example_id'],gold={'items':[],'status':'refused'})
        extension.append(refusal)
        refs=root['required_refs']
        match=make_record(prototype,family,template,split,domain,source,'match','auditor','MATCH',source,root['example_id'],
                auditor_target('MATCH','The extraction preserves the explicit statements and the recorded missing information and uncertainty, where present.',refs))
        extension.append(match)
        relation=('DIVERGENCE','OMISSION','ADDITION')[number%3]
        if relation=='DIVERGENCE':changed=source.replace(f'recorded {quantity}',f'recorded {quantity+1}',1);reason='The recorded quantity changed while its entity remained the same.';components=['changed_quantity']
        elif relation=='OMISSION':changed=source.replace(c,'');reason='The explicitly missing information and its questions were omitted.';components=['gap_omitted']
        else:changed=source+' The entry was approved by an external director.';reason='Director approval was added without source support.';components=['added_claim']
        audit=make_record(prototype,family,template,split,domain,source,'changed','auditor',relation,changed,match['example_id'],auditor_target(relation,reason,refs),['authored_input_change'])
        extension.append(audit)
        for row in extension[-6:]:
            metadata[row['example_id']]=dict(dataset_version=h.VERSION,production_contract=h.CONTRACT,origin='v2_expansion',
                independent_review_state='pending',author_id='expansion-author-assistant',
                reason_components=components if row is audit else (['evidence_insufficient'] if row['expected_refusal'] else ['preserved_claim','gap_preserved']))
        for kind in COMPOUNDS:
            parent=semantic if kind in ('uncertainty_removed_facts_retained','context_and_owned_claim') else root
            if kind in ('correct_content_invented_rule','match_missing_evidence','wrong_relation_and_irrelevant_ref'):parent=match if kind!='wrong_relation_and_irrelevant_ref' else audit
            if kind=='ambiguity_forced_answer':parent=refusal
            obj=deepcopy(parent['gold_target'])
            if kind=='ambiguity_forced_answer':obj=deepcopy(root['gold_target'])
            elif kind=='correct_content_invented_rule':obj['items'][0]['reasoning']+=' CONV-UNROUTED establishes compliance.'
            elif kind=='match_missing_evidence':obj['items'][0]['ref_ids']=[]
            elif kind=='wrong_relation_and_irrelevant_ref':
                obj['items'][0].update(finding='MATCH',severity='low',ref_ids=refs+['REF-9998'])
            else:
                content=next(i for i in obj['items'] if i['claims'])
                if kind=='claims_preserved_gap_omitted':
                    for i in obj['items']:i['questions']=[]
                elif kind=='omission_plus_addition':content['claims']=content['claims'][1:]+['CLM-UNSUPPORTED']
                elif kind=='context_and_owned_claim':obj['items'].append(dict(content,span=parent['context_only_aliases'][0],claims=['CLM-Z'],refs=['REF-9999']))
                elif kind=='uncertainty_removed_facts_retained':
                    for i in obj['items']:i['uncertainty']=[]
                elif kind=='semantic_content_empty_status':content['status']='empty'
            negatives.append(dict(candidate_id=family+'-'+kind,parent_id=parent['example_id'],split=split,
                derivation_group=family,types=[kind],raw=json.dumps(obj),expected_accepted=False,
                adjudication='authored_single_pending_independent_review',rationale='Deliberate error relative to the supplied authored target; review packet exposes input, not this label.'))
    rows=base+extension
    h.write(HERE/'extension.json',extension)
    h.write(HERE/'metadata.json',metadata)
    h.write(HERE/'compound_negatives.json',negatives)
    h.write(HERE/'family_manifest.json',[{k:r[k] for k in ('example_id','split','document_family','template_family','derivation_group','parent_id','domain')} for r in rows])
    policy=dict(version=h.VERSION,training_access_domains=sorted({r['domain'] for r in rows if r['split'] in ('train','dev')}),
        held_out_domains=['astronomy','ecology'],sealed_domain_reservations=['independent_domain_pending'],
        axes='Ordinary family split is unchanged; domain holdout is a second filter. New held-out domains have no train/dev labels or renamed descendants.')
    h.write(HERE/'domain_holdout.json',policy)
    train_templates={r['template_family'] for r in rows if r['split']=='train'}
    h.write(HERE/'unseen_templates.json',dict(training_templates=sorted(train_templates),
        unseen_examples=[r['example_id'] for r in rows if r['split'] in ('test','sealed_adversarial') and r['template_family'] not in train_templates],
        notice='Explicit structural families, not new names for training templates. Report known legacy and new structures separately.'))
    h.write(HERE/'reason_rubric.json',dict(version=h.VERSION,components=list(h.REASONS),
        rule='Components describe source/extraction facts, not fluency. Alternate wording requires independent input+output-bound review.',
        evidence='Each reviewer selects exact supplied refs and explains the observed change/preservation; formatting is separate.'))
    h.write(HERE/'sealed_final_manifest.json',h.sealed_manifest())
    thresholds={
        'producer':['claim_precision','claim_recall','gap_precision','gap_recall','evidence_precision','evidence_recall','refusal_precision','refusal_recall','semantic_completeness','contract_validity','uncertainty_preservation'],
        'auditor':['relation_accuracy','per_class_precision','per_class_recall','refusal_precision','refusal_recall','reason_correctness','evidence_precision','evidence_recall','contract_validity','uncertainty_preservation'],
        'shared':['minimum_independent_review_coverage','minimum_document_families','minimum_template_families','heldout_domain_floor','unseen_template_floor','maximum_family_variability'],
    }
    specification=dict(version='model-acceptance-prereg-v2',dataset_version=h.VERSION,production_contract=h.CONTRACT,
        state='PARTIALLY_REGISTERED_REQUIRES_OPERATOR_REGISTRATION',created_before_any_tuning=True,
        thresholds={role:{name:'REQUIRES_OPERATOR_REGISTRATION' for name in metrics} for role,metrics in thresholds.items()},
        catastrophic_limits={'invented_evidence':0,'unrouted_rule_attribution':0,'confident_wrong_match_divergence':0,'truncation':0,'producer_source_copy':0,'governance_violations':0},
        rationale='Zero limits implement existing exact evidence, governance, no-copy and zero-truncation invariants. No measured independent sample supports inventing other numeric quality/family thresholds.',
        selection_rule='No single aggregate F1 acceptance. Independent review, domain/template holdout and family-aware uncertainty are required.',
        registration_rule='Operator must register all unresolved thresholds prospectively and freeze a new specification before training; never fit them after model test results.')
    h.write(HERE/'acceptance_specification.json',specification)
    h.validate(rows,metadata,policy)
    packet_dir=HERE/'review_packets'
    if packet_dir.exists():
        for path in packet_dir.iterdir():
            if path.is_file() and re.fullmatch(r'review-[0-9a-f]{24}\.(json|md)',path.name):path.unlink()
    mapping=h.make_packets(rows,HERE/'review_packets')
    h.write(HERE/'review_admin_mapping.json',dict(packet_to_examples=mapping,reviewed=0,pending_examples=len(rows),
          warning='Administrator mapping is excluded from the reviewer packet export. No independent review has occurred.'))
    h.export_training(rows,metadata,policy,HERE/'training_view')
    baseline_files=[p for p in h.V1.iterdir() if p.is_file()]+[h.ROOT/'config/semantic_task_contract_v1.json']
    baseline_files += [p for p in (h.ROOT/'docs/fix/domain_agnostic_tuning_20260915').iterdir() if p.is_file()]
    h.write(HERE/'baseline_reference.json',dict(version=h.CONTRACT,commits=['090b3d5','cab07cd'],
        hashes={p.relative_to(h.ROOT).as_posix():h.digest(p.read_bytes()) for p in baseline_files}))
    files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='freeze.json' and p.suffix in ('.py','.json','.md')]
    h.write(HERE/'freeze.json',dict(version=h.VERSION,production_contract=h.CONTRACT,
        hashes={p.relative_to(HERE).as_posix():h.digest(p.read_bytes()) for p in sorted(files)}))
    print(json.dumps(dict(total=len(rows),new=len(extension),compound_candidates=len(negatives),packets=len(mapping))))


if __name__=='__main__':main()
