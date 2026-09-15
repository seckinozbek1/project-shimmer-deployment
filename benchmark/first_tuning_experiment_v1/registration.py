"""Prospective first-experiment registration; no training or model execution.

The new layer reads immutable v1/v2 inputs. Reviewer exports are byte-identical
blank packets; only admin artifacts may contain selection metadata and labels.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'benchmark/task_semantics_v2'))
import hardening as h

VERSION='first-tuning-experiment-v1'
SEED='shimmer-first-review-20260915-v1'
read,write,digest=h.read,h.write,h.digest


def records():return read(h.V1/'seed.json')+read(h.HERE/'extension.json')


def feature_set(row):
    items=row['gold_target']['items']
    features={'role:'+row['role'],'relation:'+row['abstract_relation']}
    if row['expected_refusal']:features.add('refusal:'+row['role'])
    if any(i.get('questions') for i in items):features.add('information_gap')
    if row['expected_uncertainty']:features.add('uncertainty')
    if row['required_refs']:features.add('evidence_selection')
    if row['context_only_aliases']:features.add('context_ownership')
    if row['hard_negative_tags']:features.update('hard:'+x for x in row['hard_negative_tags'])
    if 'conflict' in row['source_text']:features.add('contradictory_source')
    if len(row['owned_aliases'])>1:features.add('multi_span')
    if row['role']=='producer' and row['abstract_relation']=='EXTRACTED':features.add('substantive_producer')
    return features


def select(rows,size,mandatory=(),role_target=None):
    """Deterministic lexicographic diversity selection, not first-N sampling.

    Mandatory rows first; role caps are hard constraints. At each step maximize
    new document family, new template, new domain, least represented family,
    new semantic feature, then substantive producer coverage. SHA-256 of the
    prospective seed+ID resolves ties. These priorities and seed are frozen.
    """
    by_id={r['example_id']:r for r in rows}
    chosen=set(mandatory)
    if not chosen<=set(by_id) or len(chosen)>size:raise ValueError('Invalid mandatory selection')
    targets=role_target or {'producer':size//2,'auditor':size-size//2}
    while len(chosen)<size:
        selected=[by_id[i] for i in chosen]
        roles=Counter(r['role'] for r in selected)
        families=Counter(r['document_family'] for r in selected)
        templates=Counter(r['template_family'] for r in selected)
        domains=Counter(r['domain'] for r in selected)
        features=set().union(*(feature_set(r) for r in selected)) if selected else set()
        eligible=[r for r in rows if r['example_id'] not in chosen and roles[r['role']]<targets[r['role']]]
        if not eligible:raise ValueError('Role balance incompatible with mandatory coverage')
        def key(row):
            extra=feature_set(row)-features
            return (row['document_family'] not in families,row['template_family'] not in templates,
                    row['domain'] not in domains,-families[row['document_family']],len(extra),
                    row['role']=='producer' and row['abstract_relation']=='EXTRACTED',
                    -domains[row['domain']],-templates[row['template_family']],
                    digest((SEED+row['example_id']).encode('utf-8')))
        chosen.add(max(eligible,key=key)['example_id'])
    result=sorted(chosen)
    if Counter(by_id[i]['role'] for i in result)!=Counter(targets):raise ValueError('Role target not met')
    return result


def selection(rows):
    held={r['example_id'] for r in rows if r['domain'] in ('astronomy','ecology')}
    if len(held)!=72:raise ValueError('Mandatory domain population changed')
    first=select(rows,192,held,{'producer':96,'auditor':96})
    second=select([r for r in rows if r['example_id'] in first],48,role_target={'producer':24,'auditor':24})
    return first,second


def composition(rows):
    result={key:dict(sorted(Counter(r[key] for r in rows).items())) for key in
            ('role','domain','template_family','document_family','abstract_relation','split')}
    result.update(total=len(rows),held_out_domains=sum(r['domain'] in ('astronomy','ecology') for r in rows),
        unseen_templates=sum(r['split'] in ('test','sealed_adversarial') for r in rows),
        substantive_producer=sum(r['role']=='producer' and r['abstract_relation']=='EXTRACTED' for r in rows),
        refusals=sum(r['expected_refusal'] for r in rows),
        information_gaps=sum(any(i.get('questions') for i in r['gold_target']['items']) for r in rows),
        uncertainty=sum(r['expected_uncertainty'] for r in rows),
        features=sorted(set().union(*(feature_set(r) for r in rows))))
    return result


def profile():
    p=[('claim_precision','>=',.95),('claim_recall','>=',.95),('information_gap_precision','>=',.95),
       ('information_gap_recall','>=',.95),('evidence_reference_precision','==',1.),('evidence_reference_recall','>=',.98),
       ('refusal_precision','>=',.95),('refusal_recall','>=',.95),('semantic_completeness','>=',.95),
       ('contract_validity','>=',.99),('uncertainty_preservation','>=',.95)]
    a=[('overall_relation_accuracy','>=',.95),('macro_relation_f1','>=',.93),('minimum_supported_relation_recall','>=',.90),
       ('refusal_precision','>=',.95),('refusal_recall','>=',.95),('reason_correctness','>=',.90),
       ('evidence_reference_precision','==',1.),('evidence_reference_recall','>=',.98),
       ('contract_validity','>=',.99),('uncertainty_preservation','>=',.95)]
    r=[('independently_reviewed_fraction_of_selected_experimental_cohort','==',1.),
       ('double_independent_review_fraction','>=',.25),('reviewed_structural_template_coverage','==',1.),
       ('reviewed_held_out_domain_examples','==',1.),('reviewed_unseen_template_examples','>=',64),
       ('worst_sufficiently_sampled_family_accepted_outcome_rate','>=',.80)]
    criteria=[dict(id=prefix+str(i+1).zfill(2),scope=scope,metric=name,operator=op,value=value)
              for prefix,scope,values in [('P','producer',p),('A','auditor',a),('R','review_generalization',r)]
              for i,(name,op,value) in enumerate(values)]
    old=read(h.HERE/'acceptance_specification.json')
    return dict(profile=VERSION,decision='FIRST_TUNING_EXPERIMENT',production_contract=h.CONTRACT,
        benchmark=h.VERSION,status='PROSPECTIVELY_REGISTERED',registered_before_any_tuning=True,
        authorization='Operator request: local registration and reviewer preparation only; training is not authorized.',
        interpretation='prospectively registered first-experiment decision thresholds; not universal constants, near-perfect or production acceptance',
        criteria=criteria,criteria_count=27,
        derived_hard_gate=dict(id='R07',metric='catastrophic_failure_count',operator='==',value=0,
            interpretation='Derived conjunction of six separately registered hard limits, not a 28th independent numeric threshold.'),
        catastrophic_limits=old['catastrophic_limits'],
        sufficiently_sampled_family=dict(unit='document_family',minimum_independently_reviewed_examples=4,
            insufficient_status='insufficient_sample_for_family_gate',exclude_poor_performers=False),
        denominators=dict(R01=192,R02=192,designated_second_reviews=48,R03=16,R04=72,
            supported_relation='at least one gold instance in the independently reviewed evaluation set',
            undefined_metric='INSUFFICIENT_MEASUREMENT; never a pass'),
        reviewer_verification='Operator-verified independent human roster required. Operator, authors, LLMs and automated judges cannot count.',
        metric_interpretations=dict(P09='Semantic completeness on non-refusal producer outcomes; refusals have P07/P08.',
            A01='Five supported semantic relations including insufficiency; invalid/uncompleted outputs receive no relation credit.',
            A02='Macro F1 across gold-supported relations; support counts must be reported.',
            A10='Exact reviewed confidence/uncertainty status for non-refusal comparisons; source uncertainty truth is also assessed by A06 reason review.',
            A06='Unassessed reasons count against truth coverage; correct refusals are scored separately.'),
        review_readiness_requirements=['192 valid independent first reviews','all designated 48 valid second reviews',
            'material disagreements resolved','all 72 held-out examples reviewed','16 templates reviewed','at least 64 unseen-template examples reviewed',
            'frozen registration','leakage/access/governance/evidence gates pass'],
        checkpoint_performance_requirements='P01-P11, A01-A10, R06 and derived R07 apply to future saved outputs against reviewed labels; no outputs are required merely to prepare review.',
        evaluation_population='All reviewed selected DEV/TEST/public-adversarial examples, excluding TRAIN; complete unique saved-output coverage required.',
        sealed_final_required_for_first_experiment=False,training_authorized=False,
        final_model_acceptance=dict(separate_profile=True,ready=False,genuine_independent_sealed_material_required=True,
            external_account_acl_required=True,blind_evaluation_required=True,stronger_adjudication_required=True,
            family_domain_generalization_required=True,governance_evidence_required=True,final_numeric_thresholds_unchanged=True,
            existing_specification_sha256=digest((h.HERE/'acceptance_specification.json').read_bytes())))


def verify_profile(value):
    expected=profile()
    if value!=expected:raise ValueError('Prospective registration deviates from operator rules')
    if len(value['criteria'])!=27 or len({c['id'] for c in value['criteria']})!=27:raise ValueError('Expected 27 independent criteria')
    return True


def verify_frozen():
    h.verify_baseline();h.verify_freeze()
    frozen=read(HERE/'freeze.json')
    for path,expected in frozen['hashes'].items():
        if digest((HERE/path).read_bytes())!=expected:raise ValueError('First-experiment freeze drift: '+path)
    verify_profile(read(HERE/'acceptance_registration.json'))
    return True


def expected_export_files(expected_packets):
    expected={'INSTRUCTIONS.md':(HERE/'reviewer_instructions.md').read_bytes()}
    for ident in expected_packets:
        for suffix in ('.json','.md'):
            expected[ident+suffix]=(h.HERE/'review_packets'/(ident+suffix)).read_bytes()
    return expected


def audit_export(root,expected_packets):
    """Exact file/byte allowlist, not a blacklist of known leaked gold names."""
    root=Path(root);expected=expected_export_files(expected_packets)
    paths=[p for p in root.rglob('*') if p.is_file()]
    actual={p.relative_to(root).as_posix() for p in paths}
    if actual!=set(expected):raise ValueError('Unapproved file in reviewer export')
    for path in paths:
        name=path.relative_to(root).as_posix()
        if path.is_symlink() or path.resolve().parent!=root.resolve():raise ValueError('Export path escape')
        if path.read_bytes()!=expected[name]:raise ValueError('Reviewer export differs from approved blank packet: '+name)
    return dict(files=len(paths),packets=len(expected_packets),gold_findings=0,split_findings=0,admin_findings=0,historical_answer_findings=0)


def review_coverage(rows,cohort,double,journal,reviewer_registry=None):
    """Read actual v2 journal responses; never synthesize reviews or compare to authored gold as approval."""
    index={r['example_id']:r for r in rows};double=set(double);journal=Path(journal)
    reviewed={};first_valid=set();second_valid=set();disagreements=[];invalid=[]
    registry=(reviewer_registry or {}).get('reviewers',{})
    for ident in cohort:
        row=index[ident];packet_id=h.packet(row)['packet_id']
        submissions=[read(p) for p in sorted(journal.glob(packet_id+'-submission-*.json'))] if journal.exists() else []
        if not submissions:continue
        try:
            for submission in submissions:
                attestation=registry.get(submission.get('reviewer_id'),{})
                if (attestation.get('human') is not True or attestation.get('operator_verified') is not True or
                    attestation.get('independent_of_authorship') is not True or attestation.get('is_operator') is not False):
                    raise ValueError('Reviewer is not an operator-verified independent human')
            final_path=journal/(packet_id+'-final.json')
            stored=read(final_path) if final_path.exists() else None
            resolution=stored.get('resolution') if stored else None
            if resolution:
                resolver=registry.get(resolution.get('adjudicator_id'),{})
                if (resolver.get('human') is not True or resolver.get('operator_verified') is not True or
                    resolver.get('independent_of_authorship') is not True or resolver.get('is_operator') is not False):
                    raise ValueError('Resolver is not an operator-verified independent human')
            state=h.adjudication_state(row,submissions,resolution)
            # Human semantic targets must themselves satisfy the immutable wire
            # contract. A malformed annotation cannot become training gold.
            for submission in submissions:
                if not h.baseline.classify(row,json.dumps(submission['semantic_target']))[1]:raise ValueError('Invalid reviewed target')
            first_valid.add(ident)
            if len(submissions)==2:second_valid.add(ident)
            if state['state']=='disagreement':disagreements.append(ident);continue
            if ident in double and len(submissions)!=2:continue
            if len(submissions)==2:
                if (not stored or sorted(stored.get('submission_hashes',[]))!=sorted(digest(r) for r in submissions) or
                    stored.get('final_target')!=state['final_target'] or stored.get('input_sha256')!=h.packet(row)['input_sha256']):
                    raise ValueError('Final adjudication/submission binding mismatch')
                target=state['final_target']
            else:target=submissions[0]['semantic_target']
            reviewed[ident]=target
        except (ValueError,TypeError,KeyError):invalid.append(ident)
    accepted_rows=[index[i] for i in reviewed]
    held={r['example_id'] for r in rows if r['domain'] in ('astronomy','ecology')}
    templates={r['template_family'] for r in accepted_rows}
    unseen=sum(r['split'] in ('test','sealed_adversarial') for r in accepted_rows)
    ready=(len(reviewed)==192 and set(double)<=second_valid and held<=set(reviewed) and len(templates)==16 and unseen>=64 and not disagreements and not invalid)
    return dict(status='FIRST_TUNING_EXPERIMENT_REVIEW_READY' if ready else 'FIRST_TUNING_EXPERIMENT_REVIEW_PENDING',
        selected=192,first_reviews_valid=len(first_valid),designated_second_reviews_valid=len(set(double)&second_valid),
        reviewed_accepted=len(reviewed),reviewed_held_out=len(held&set(reviewed)),reviewed_templates=len(templates),
        reviewed_unseen_templates=unseen,unresolved_disagreements=disagreements,invalid_review_examples=invalid,
        accepted_targets=reviewed,final_model_acceptance_ready=False,sealed_final_required_for_review_ready=False)


def eligible_training(rows,coverage):
    groups={name:[] for name in ('independently_reviewed_train','independently_reviewed_dev','authored_only',
                                 'held_out_domain','test','public_adversarial','regression')}
    for row in rows:
        ident=row['example_id']
        if row['domain'] in ('astronomy','ecology'):category='held_out_domain'
        elif row['split']=='test':category='test'
        elif row['split']=='sealed_adversarial':category='public_adversarial'
        elif row['split']=='regression':category='regression'
        elif ident in coverage['accepted_targets']:category='independently_reviewed_'+row['split']
        else:category='authored_only'
        groups[category].append(ident)
    return dict(profile=VERSION,categories=groups,allowed_ids=groups['independently_reviewed_train']+groups['independently_reviewed_dev'],
                sealed_final_ids=[],training_authorized=False)


def export_training_labels(rows,coverage,destination):
    """Export only validated tuning-access labels, never the admin target map."""
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    manifest=eligible_training(rows,coverage)
    allowed=set(manifest['allowed_ids'])
    for split in ('train','dev'):
        values=[dict(example_id=row['example_id'],split=split,input=h.review_input(row),
                reviewed_target=coverage['accepted_targets'][row['example_id']],label_source='independent_human_review',
                input_sha256=h.packet(row)['input_sha256']) for row in rows if row['example_id'] in allowed and row['split']==split]
        write(destination/(split+'.json'),values)
    manifest['allowed_files']={split+'.json':digest((destination/(split+'.json')).read_bytes()) for split in ('train','dev')}
    write(destination/'manifest.json',manifest)
    return manifest


def metric_pr(tp,fp,fn):
    return (tp/(tp+fp) if tp+fp else None,tp/(tp+fn) if tp+fn else None)


def performance_metrics(scores):
    """Future saved-output metrics. Missing denominators never count as passing."""
    metrics={};cat=Counter()
    for role,prefix in [('producer','P'),('auditor','A')]:
        rs=[r for r in scores if r['role']==role]
        def rate(key,exclude_refusal=False):
            values=[r[key] for r in rs if type(r.get(key)) is bool and (not exclude_refusal or not r['expected_refusal'])]
            return sum(values)/len(values) if values else None
        def micro(field):
            values=[r[field] for r in rs if isinstance(r.get(field),dict)]
            return metric_pr(*(sum(v[k] for v in values) for k in ('tp','fp','fn')))
        refused=metric_pr(sum(r['predicted_refusal'] and r['expected_refusal'] for r in rs),
                          sum(r['predicted_refusal'] and not r['expected_refusal'] for r in rs),
                          sum(not r['predicted_refusal'] and r['expected_refusal'] for r in rs))
        ep,er=micro('evidence')
        if role=='producer':
            cp,cr=micro('claims');gp,gr=micro('information_gaps')
            # Exact preservation of uncertainty observations; only examples
            # with a positive uncertainty reference are in this denominator.
            applicable=[r['uncertainty'] for r in rs if r.get('uncertainty',{}).get('tp',0)+r.get('uncertainty',{}).get('fn',0)>0]
            up=sum(v['fp']==v['fn']==0 for v in applicable)/len(applicable) if applicable else None
            values=[cp,cr,gp,gr,ep,er,*refused,rate('semantic_completeness',True),rate('contract_valid'),up]
        else:
            counts=defaultdict(lambda:Counter(tp=0,fp=0,fn=0,support=0));correct=0
            for row in rs:
                expected=row.get('expected_relation')
                actual='INSUFFICIENT_EVIDENCE' if row['predicted_refusal'] else row.get('predicted_relation')
                # An unaccepted prefix cannot receive relation credit.
                if not row['contract_valid'] or not row['transport_complete']:actual=None
                correct+=actual==expected
                for label in ('MATCH','DIVERGENCE','OMISSION','ADDITION','INSUFFICIENT_EVIDENCE'):
                    counts[label]['support']+=expected==label
                    counts[label]['tp']+=actual==expected==label
                    counts[label]['fp']+=actual==label and expected!=label
                    counts[label]['fn']+=expected==label and actual!=label
            supported=[v for v in counts.values() if v['support']>0]
            metrics['auditor_relation_support']={label:dict(value) for label,value in counts.items()}
            f1=[2*v['tp']/(2*v['tp']+v['fp']+v['fn']) for v in supported]
            recalls=[v['tp']/v['support'] for v in supported]
            # Unassessed reasons count against the required truth coverage;
            # correct refusals are not scored as free-form reason assertions.
            reason_rows=[r for r in rs if not r['expected_refusal']]
            reason=sum(r.get('reason_correct') is True for r in reason_rows)/len(reason_rows) if reason_rows else None
            values=[correct/len(rs) if rs else None,sum(f1)/len(f1) if f1 else None,min(recalls) if recalls else None,
                    *refused,reason,ep,er,rate('contract_valid'),rate('uncertainty_preserved',True)]
        metrics.update({prefix+str(i+1).zfill(2):value for i,value in enumerate(values)})
    for row in scores:
        cat['invented_evidence']+=row.get('catastrophic',{}).get('invented_evidence',False)
        cat['unrouted_rule_attribution']+=row.get('catastrophic',{}).get('invented_rule',False)
        cat['confident_wrong_match_divergence']+=row.get('catastrophic',{}).get('incorrect_confident_judgment',False)
        cat['truncation']+=row.get('truncated',False)
        cat['producer_source_copy']+=row.get('copied_source_violation',False)
    return metrics,dict(cat)


def evaluate_thresholds(scores,rows,coverage,governance_violations=0):
    spec=read(HERE/'acceptance_registration.json');verify_profile(spec)
    metrics,cat=performance_metrics(scores);cat['governance_violations']=governance_violations
    metrics.update(R01=coverage['reviewed_accepted']/192,R02=coverage['designated_second_reviews_valid']/192,
                   R03=coverage['reviewed_templates']/16,R04=coverage['reviewed_held_out']/72,R05=coverage['reviewed_unseen_templates'])
    index={r['example_id']:r for r in rows};grouped=defaultdict(list)
    expected_ids={i for i in coverage['accepted_targets'] if index[i]['split']!='train'}
    actual_ids=[s['example_id'] for s in scores]
    measurement_complete=bool(expected_ids) and len(actual_ids)==len(set(actual_ids)) and set(actual_ids)==expected_ids
    for row in scores:
        if row['example_id'] in coverage['accepted_targets']:grouped[index[row['example_id']]['document_family']].append(row)
    family={}
    reviewed_counts=Counter(index[i]['document_family'] for i in coverage['accepted_targets'])
    for name,n in reviewed_counts.items():
        observations=grouped[name]
        if n<4:family[name]=dict(status='insufficient_sample_for_family_gate',reviewed=n)
        elif len({r['example_id'] for r in observations})!=n:family[name]=dict(status='INSUFFICIENT_MEASUREMENT',reviewed=n)
        else:family[name]=dict(status='measured',reviewed=n,rate=sum(r['accepted_outcome'] for r in observations)/n)
    rates=[v['rate'] for v in family.values() if v['status']=='measured']
    metrics['R06']=min(rates) if rates and not any(v['status']=='INSUFFICIENT_MEASUREMENT' for v in family.values()) else None
    results={c['id']:dict(measured=metrics[c['id']],passed=None if metrics[c['id']] is None else
             (metrics[c['id']]==c['value'] if c['operator']=='==' else metrics[c['id']]>=c['value'])) for c in spec['criteria']}
    catastrophic_pass=all(cat.get(key,0)==0 for key in spec['catastrophic_limits'])
    return dict(criteria=results,R07=dict(passed=catastrophic_pass,counts=cat),families=family,
                measurement_complete=measurement_complete,auditor_relation_support=metrics.get('auditor_relation_support',{}),
                promising_checkpoint=coverage['status']=='FIRST_TUNING_EXPERIMENT_REVIEW_READY' and measurement_complete and catastrophic_pass and all(r['passed'] is True for r in results.values()),
                final_model_acceptance_ready=False,training_authorized=False)
