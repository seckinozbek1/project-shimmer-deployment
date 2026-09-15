"""Post-freeze diagnostic comparison only; never rewrites machine/authored labels."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import argparse
import json
import sys
import review as m
import eligibility as e


def set_fields(target,role):
    keys=('claims','questions','uncertainty','refs') if role=='producer' else ('ref_ids',)
    return {k:sorted({(i.get('span',''),m.normal_string(v)) for i in target.get('items',[]) for v in i.get(k,[])}) for k in keys}


def breakdown(ids,cons,labels):
    ids=list(ids);n=len(ids)
    counts=Counter(cons[i]['state'] for i in ids)
    adjud=[i for i in ids if labels[i]['provenance']=='machine_agent_adjudication']
    majority_adjud=[i for i in adjud if labels[i]['adjudicator_agrees_with_majority'] is not None]
    overturn=sum(labels[i]['adjudicator_agrees_with_majority'] is False for i in majority_adjud)
    unresolved=sum(labels[i]['unresolved'] for i in ids)
    return dict(packets=n,unanimous=counts['unanimous'],majority_2_of_3=counts['majority'],no_majority=counts['no_majority'],
                unanimous_rate=counts['unanimous']/n if n else None,majority_rate=counts['majority']/n if n else None,
                no_majority_rate=counts['no_majority']/n if n else None,adjudicated=len(adjud),
                majority_adjudicated=len(majority_adjud),overturns=overturn,overturn_rate=overturn/len(majority_adjud) if majority_adjud else None,
                unresolved=unresolved,unresolved_rate=unresolved/n if n else None)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pre-gold-commit',required=True)
    args=parser.parse_args()
    freeze_path=m.HERE/'blind_evidence/PRE_GOLD_FREEZE.json';freeze=m.verify_pre_gold(freeze_path)
    out=m.HERE/'post_freeze';out.mkdir(exist_ok=True)
    m.write(out/'GOLD_COMPARISON_STARTED.json',dict(started_at=datetime.now(timezone.utc).isoformat(),
            pre_gold_frozen_at=freeze['frozen_at'],pre_gold_manifest_sha256=m.sha(freeze_path.read_bytes()),
            pre_gold_commit=args.pre_gold_commit,freeze_verified=True),exclusive=True)
    # First semantic opening of authored targets in this task. Reviewer and
    # adjudicator sessions are complete; no further label-generation pass occurs.
    rows=m.read(m.ROOT/'benchmark/task_semantics/seed.json')+m.read(m.ROOT/'benchmark/task_semantics_v2/extension.json')
    index={r['example_id']:r for r in rows}
    exports=m.read(m.ROOT/'benchmark/first_tuning_review_cohort_v2/export_admin_manifest.json')
    first=next(v for v in exports.values() if v['slot']==1)
    mapping=dict(zip(first['packet_ids'],first['ids']))
    labels=m.read(m.HERE/'blind_evidence/consensus_labels.json')
    cons=m.read(m.HERE/'blind_evidence/consensus_initial.json')
    packets=m.packets();comparisons={};train=[];dev=[];evaluation=[];excluded=[]
    producer=Counter();auditor=Counter();relation_pairs=Counter();groups=defaultdict(list)
    for ident,example_id in mapping.items():
        row=index[example_id];label=labels[ident];review=label['review'];gold=row['gold_target'];target=review['semantic_target']
        actual=set_fields(target,row['role']);expected=set_fields(gold,row['role'])
        differences={k:dict(machine_only=sorted(set(actual[k])-set(expected[k])),authored_only=sorted(set(expected[k])-set(actual[k]))) for k in actual if actual[k]!=expected[k]}
        refusal_diff=(review['semantic_judgment']=='INSUFFICIENT_EVIDENCE')!=row['expected_refusal']
        relation_diff=review['semantic_judgment']!=row['abstract_relation']
        confidence_diff=False
        if row['role']=='auditor':
            confidence_diff=([i.get('confidence') for i in target['items']]!=[i.get('confidence') for i in gold['items']])
        dispute=bool(differences or refusal_diff or relation_diff or confidence_diff)
        comparison=dict(example_id=example_id,packet_id=ident,role=row['role'],
                status='LABEL_DISPUTE_REQUIRING_CAUTION' if dispute else 'STRUCTURED_AUTHORED_AGREEMENT',
                relation_match=not relation_diff,machine_relation=review['semantic_judgment'],authored_relation=row['abstract_relation'],
                differences=differences,refusal_difference=refusal_diff,confidence_difference=confidence_diff,
                machine_target=target,authored_target=gold,
                authored_reason_components=None,reason_component_comparison='NOT_AVAILABLE: frozen authored records contain prose rationale, not typed reason-component annotations.',
                machine_reason_components=review['reason_components'],
                rationale_exact_match=[i.get('reasoning') for i in target['items']]==[i.get('reasoning') for i in gold['items']] if row['role']=='auditor' else None,
                caveat='Exact semantic-field/set differences are diagnostic; question/uncertainty paraphrases are conservatively disputed, not proved wrong. Neither label source automatically wins.')
        comparisons[ident]=comparison
        counts=producer if row['role']=='producer' else auditor
        counts['total']+=1;counts['structured_agreement']+=not dispute;counts['refusal_disagreement']+=refusal_diff
        if row['role']=='producer':
            for key in ('claims','questions','uncertainty','refs'):counts[key+'_disagreement']+=key in differences
        else:
            counts['relation_agreement']+=not relation_diff;counts['evidence_disagreement']+='ref_ids' in differences
            counts['confidence_disagreement']+=confidence_diff;counts['rationale_exact_match']+=comparison['rationale_exact_match']
            if relation_diff:relation_pairs[(row['abstract_relation'],review['semantic_judgment'])]+=1
        eligible=e.candidate(row,label,cons[ident]['primary_valid'],dispute)
        if row['split'] in ('train','dev') and not e.held_out(row):
            if eligible:
                value=e.machine_label(row,label);value['input']=packets[ident]['input'];value['packet_id']=ident
                (train if row['split']=='train' else dev).append(value)
            else:excluded.append(dict(example_id=example_id,packet_id=ident,split=row['split'],disputed=dispute,
                    ambiguous=label['unresolved'],invalid_primary=not all(cons[ident]['primary_valid'].values())))
        else:evaluation.append(dict(example_id=example_id,packet_id=ident,held_out_domain=e.held_out(row),label=label,disputed=dispute))
        dimensions=dict(role=row['role'],domain=row['domain'],template=row['template_family'],semantic_relation=row['abstract_relation'],
                        refusal=str(row['expected_refusal']),information_gap=str(any(i.get('questions') for i in gold['items'])),
                        uncertainty=str(row['expected_uncertainty']),held_out=str(e.held_out(row)),unseen_template=str(row['split'] in ('test','sealed_adversarial')))
        for dimension,value in dimensions.items():groups[(dimension,value)].append(ident)
    m.write(out/'authored_comparison.json',comparisons,exclusive=True)
    m.write(out/'comparison_summary.json',dict(producer=dict(producer),auditor=dict(auditor),
            auditor_relation_disagreements=[dict(authored=a,machine=b,count=n) for (a,b),n in sorted(relation_pairs.items())],
            reason_component_agreement=None,reason_component_limitation='No authored typed component annotations; no invented comparison statistic.',
            disputes=sum(v['status']=='LABEL_DISPUTE_REQUIRING_CAUTION' for v in comparisons.values())),exclusive=True)
    stats=breakdown(mapping,cons,labels)
    by_dimension={}
    for (dimension,value),ids in sorted(groups.items()):by_dimension.setdefault(dimension,{})[value]=breakdown(ids,cons,labels)
    # Fleiss kappa is meaningful only for categorical auditor relation ratings;
    # structured producer fields remain exact/set agreement, never a fake kappa.
    auditor_ids=[i for i,eid in mapping.items() if index[eid]['role']=='auditor']
    cats=Counter();agreement=[]
    for ident in auditor_ids:
        ratings=Counter(m.effective(slot,ident)['semantic_judgment'] for slot in 'ABC')
        cats.update(ratings);agreement.append(sum(n*(n-1) for n in ratings.values())/6)
    pbar=sum(agreement)/len(agreement);pe=sum((n/(3*len(auditor_ids)))**2 for n in cats.values())
    stats['auditor_relation_fleiss_kappa']=(pbar-pe)/(1-pe) if pe!=1 else None
    stats['kappa_scope']='96 auditor categorical relation ratings only; same-model correlated agents, not human reliability.'
    stats['breakdowns']=by_dimension
    m.write(out/'agreement_statistics.json',stats,exclusive=True)
    access=m.HERE/'machine_adjudicated_training_access'
    m.write(access/'train.json',train,exclusive=True);m.write(access/'dev.json',dev,exclusive=True)
    m.write(access/'manifest.json',dict(provenance='machine_adjudicated_training_candidate',human_reviewed=False,
            protocol=m.PROTOCOL,cohort_revision='first-tuning-review-cohort-v2',
            train_count=len(train),dev_count=len(dev),allowed_ids=[r['example_id'] for r in train+dev],
            files={name:m.sha((access/name).read_bytes()) for name in ('train.json','dev.json')},
            training_authorized=False,dev_usage='Validation/tuning decisions; not automatically gradient training.',
            scope='Only this directory may be supplied to a future separately authorized job. No evaluation labels or surrounding admin files.'),exclusive=True)
    m.write(out/'excluded_tuning_candidates.json',excluded,exclusive=True)
    m.write(out/'held_out_machine_reference.json',evaluation,exclusive=True)
    m.write(out/'r06_population.json',dict(adapter='r06-non-train-v1',
            eligible_evaluation_metadata=[dict(example_id=eid,split=index[eid]['split'],document_family=index[eid]['document_family']) for eid in mapping.values() if index[eid]['split']!='train'],
            population_count=114,dev=40,held_out=72,additional_evaluation=2,threshold=.80,minimum_family_sample=4,
            training_predictions_used=False,checkpoint_performance_measured=False),exclusive=True)
    valid_primary=sum(sum(v['primary_valid'].values()) for v in cons.values())
    adjud=m.read(m.HERE/'blind_evidence/adjudication_validation.json')
    ready=valid_primary==576 and all(v['valid'] for v in adjud.values()) and bool(train) and bool(dev)
    status=dict(machine_status='AGENT_ADJUDICATED_TUNING_EXPERIMENT_READY' if ready else 'AGENT_ADJUDICATED_TUNING_EXPERIMENT_NOT_READY',
            human_status='FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING',human_first_reviews=0,human_second_reviews=0,human_adjudications=0,
            primary_judgments=576,valid_effective_primary=valid_primary,invalid_effective_primary=576-valid_primary,
            designated_adjudications=48,all_adjudications=len(adjud),train_candidates=len(train),dev_candidates=len(dev),
            excluded_tuning_candidates=len(excluded),unresolved_packet_labels=stats['unresolved'],
            held_out_reviewed=72,held_out_training_excluded=True,r06_fixed=True,
            training_authorized=False,final_model_acceptance_ready=False,
            blockers=['Not all 576 primary reviews satisfy evidence constraints.'] if not ready else [])
    m.write(out/'readiness.json',status,exclusive=True)
    print(json.dumps(dict(status=status,agreement={k:v for k,v in stats.items() if k!='breakdowns'},producer=dict(producer),auditor=dict(auditor)),indent=2))


if __name__=='__main__':main()
