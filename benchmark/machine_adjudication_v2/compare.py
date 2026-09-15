"""Diagnostic authored comparison, strictly after committed V2 label freeze."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import argparse
import review as m
m.sys.path.insert(0,str(m.HERE))
import pipeline
import projection
import atoms


def fields(target,keys):
    return {k:sorted({(i.get('span',''),v) for i in target.get('items',[]) for v in i.get(k,[])}) for k in keys}


def stats(ids,cons,labels):
    ids=list(ids);n=len(ids);counts=Counter(cons[i]['state'] for i in ids)
    return dict(n=n,unanimous=counts['unanimous'],majority=counts['majority'],no_majority=counts['no_majority'],
      unanimous_rate=counts['unanimous']/n if n else None,majority_rate=counts['majority']/n if n else None,no_majority_rate=counts['no_majority']/n if n else None,
      review_ambiguity=sum(labels[i]['review_ambiguity'] for i in ids),source_uncertainty=sum(labels[i]['source_uncertainty_present'] for i in ids))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pre-gold-commit',required=True);args=parser.parse_args()
    frozen=pipeline.verify_freeze()
    pfreeze=m.read(m.HERE/'PRE_GOLD_PROJECTION_FREEZE.json')
    for n,h in pfreeze['hashes'].items():
        if m.sha((m.HERE/n).read_bytes())!=h:raise ValueError('Projection changed after registration')
    out=m.HERE/'post_freeze'
    m.write(out/'GOLD_COMPARISON_STARTED.json',dict(started_at=datetime.now(timezone.utc).isoformat(),frozen_at=frozen['frozen_at'],pre_gold_commit=args.pre_gold_commit,
      freeze_sha256=m.sha((m.HERE/'blind_evidence/PRE_GOLD_FREEZE.json').read_bytes()),projection_sha256=m.sha((m.HERE/'projection.py').read_bytes())),exclusive=True)
    # No authored semantic target is opened in this task before the checkpoint.
    rows=m.read(m.ROOT/'benchmark/task_semantics/seed.json')+m.read(m.ROOT/'benchmark/task_semantics_v2/extension.json')
    index={r['example_id']:r for r in rows}
    exports=m.read(m.ROOT/'benchmark/first_tuning_review_cohort_v2/export_admin_manifest.json')
    first=next(v for v in exports.values() if v['slot']==1);mapping=dict(zip(first['packet_ids'],first['ids']))
    labels=m.read(m.HERE/'blind_evidence/labels.json');cons=m.read(m.HERE/'blind_evidence/consensus.json');ps=m.packets()
    comparisons={};producer=Counter();auditor=Counter();train=[];dev=[];excluded=[];evaluation=[];groups=defaultdict(list)
    for ident,eid in mapping.items():
        row=index[eid];label=labels[ident];review=label['review'];gold=row['gold_target'];target=review['semantic_target'];role=row['role']
        result=dict(example_id=eid,packet_id=ident,role=role,refusal_agreement=(review['semantic_judgment']=='INSUFFICIENT_EVIDENCE')==row['expected_refusal'],
                    machine_target=target,authored_target=gold,authored_typed_reason_components=None)
        counters=producer if role=='producer' else auditor;counters['total']+=1
        counters['refusal_agreement']+=result['refusal_agreement']
        if role=='producer':
            af=fields(target,['claims','questions','uncertainty','refs']);gf=fields(gold,['claims','questions','uncertainty','refs'])
            projected_gaps=[];projected_unc=[];errors=[]
            spans={s['alias']:s['text'] for s in ps[ident]['input']['source_spans']}
            for item in gold['items']:
                for key,kind,dest in [('questions','gap',projected_gaps),('uncertainty','uncertainty',projected_unc)]:
                    for text in item[key]:
                        try:dest.append(projection.project(text,spans[item['span']],item['span'],item['refs'],kind))
                        except ValueError as exc:errors.append(dict(field=key,span=item['span'],wording=text,error=str(exc)))
            result.update(claim_agreement=af['claims']==gf['claims'],evidence_agreement=af['refs']==gf['refs'],
              typed_gap_agreement=not any(e['field']=='questions' for e in errors) and atoms.material(review['gap_atoms'])==atoms.material(projected_gaps),
              typed_uncertainty_agreement=not any(e['field']=='uncertainty' for e in errors) and atoms.material(review['uncertainty_atoms'])==atoms.material(projected_unc),
              wording_difference=af['questions']!=gf['questions'] or af['uncertainty']!=gf['uncertainty'],
              projected_authored_gaps=projected_gaps,projected_authored_uncertainty=projected_unc,projection_errors=errors,
              empty_refusal_state_agreement=review['semantic_judgment']==row['abstract_relation'])
            semantic=all(result[k] for k in ('claim_agreement','evidence_agreement','typed_gap_agreement','typed_uncertainty_agreement','refusal_agreement','empty_refusal_state_agreement'))
            result['wording_only_difference']=semantic and result['wording_difference']
            for k in ('claim_agreement','typed_gap_agreement','typed_uncertainty_agreement','evidence_agreement','wording_only_difference'):counters[k]+=result[k]
            counters['projection_unresolved']+=bool(errors)
        else:
            result.update(relation_agreement=review['semantic_judgment']==row['abstract_relation'],
              evidence_agreement=fields(target,['ref_ids'])==fields(gold,['ref_ids']),
              confidence_agreement=[i.get('confidence') for i in target['items']]==[i.get('confidence') for i in gold['items']],
              typed_reason_agreement=None,typed_reason_note='Authored records lack typed reason components; no invented annotation or statistic.')
            semantic=all(result[k] for k in ('relation_agreement','evidence_agreement','refusal_agreement','confidence_agreement'))
            for k in ('relation_agreement','evidence_agreement','confidence_agreement'):counters[k]+=result[k]
        counters['structured_semantic_agreement']+=semantic
        result['status']='TYPED_SEMANTIC_AGREEMENT' if semantic else 'LABEL_DISPUTE_REQUIRING_CAUTION'
        comparisons[ident]=result
        eligible=m.candidate(row,label,cons[ident]['primary_valid'],not semantic)
        if row['split'] in ('train','dev') and row['domain'] not in ('astronomy','ecology'):
            if eligible:
                item=dict(example_id=eid,packet_id=ident,split=row['split'],role=role,provenance='machine_adjudicated_training_candidate',human_reviewed=False,
                  input=ps[ident]['input'],input_sha256=review['input_sha256'],semantic_target=target,gap_atoms=review['gap_atoms'],uncertainty_atoms=review['uncertainty_atoms'],
                  source_uncertainty_present=review['source_uncertainty_present'],review_ambiguity=False)
                (train if row['split']=='train' else dev).append(item)
            else:excluded.append(dict(example_id=eid,packet_id=ident,role=role,split=row['split'],semantic_dispute=not semantic,review_ambiguity=review['review_ambiguity'],invalid_primary=not all(cons[ident]['primary_valid'].values())))
        else:evaluation.append(dict(example_id=eid,packet_id=ident,held_out=row['domain'] in ('astronomy','ecology'),label=label,semantic_dispute=not semantic))
        for k,v in [('role',role),('domain',row['domain']),('template',row['template_family']),('relation',row['abstract_relation']),('held_out',str(row['domain'] in ('astronomy','ecology'))),('unseen',str(row['split'] in ('test','sealed_adversarial'))),('refusal',str(row['expected_refusal'])),('gap',str(bool(any(i.get('questions') for i in gold['items'])))),('source_uncertainty',str(review['source_uncertainty_present']))]:groups[(k,v)].append(ident)
    m.write(out/'authored_comparison.json',comparisons,exclusive=True)
    m.write(out/'comparison_summary.json',dict(producer=dict(producer),auditor=dict(auditor),
      semantic_disputes=sum(v['status']!='TYPED_SEMANTIC_AGREEMENT' for v in comparisons.values()),
      note='V2 methodology changes representation, not model capability. Wording-only differences are not semantic errors; unsupported legacy projections remain disputes.'),exclusive=True)
    agreement=stats(mapping,cons,labels);agreement['breakdowns']={}
    for (kind,name),ids in sorted(groups.items()):agreement['breakdowns'].setdefault(kind,{})[name]=stats(ids,cons,labels)
    primaries={i:[pipeline.effective(s,i) for s in 'ABC'] for i in mapping}
    prod=[i for i in mapping if ps[i]['input']['role']=='producer'];aud=[i for i in mapping if ps[i]['input']['role']=='auditor']
    agreement['producer_typed_gap_unanimous']=sum(len({m.sha(atoms.material(v['gap_atoms'])) for v in primaries[i]})==1 for i in prod)
    agreement['producer_typed_uncertainty_unanimous']=sum(len({m.sha(atoms.material(v['uncertainty_atoms'])) for v in primaries[i]})==1 for i in prod)
    agreement['auditor_relation_unanimous']=sum(len({v['semantic_judgment'] for v in primaries[i]})==1 for i in aud)
    agreement['adjudications']=sum(v['provenance']=='machine_agent_adjudication' for v in labels.values())
    agreement['overturns']=sum(v['adjudicator_agrees_with_majority'] is False for v in labels.values())
    agreement['majority_adjudicated']=sum(v['adjudicator_agrees_with_majority'] is not None for v in labels.values())
    m.write(out/'agreement_statistics.json',agreement,exclusive=True)
    access=m.HERE/'machine_adjudicated_training_access_v2'
    m.write(access/'train.json',train,exclusive=True);m.write(access/'dev.json',dev,exclusive=True)
    m.write(access/'manifest.json',dict(protocol=m.PROTOCOL,provenance='machine_adjudicated_training_candidate',human_reviewed=False,
       train_count=len(train),dev_count=len(dev),allowed_ids=[v['example_id'] for v in train+dev],
       files={n:m.sha((access/n).read_bytes()) for n in ('train.json','dev.json')},training_authorized=False,
       scope='Only this directory for future separately approved tuning; DEV stays validation; surrounding evaluation/admin labels excluded.'),exclusive=True)
    m.write(out/'excluded_candidates.json',excluded,exclusive=True);m.write(out/'evaluation_reference.json',evaluation,exclusive=True)
    m.write(out/'summary.json',dict(protocol=m.PROTOCOL,primary_count=576,valid_effective_primary=sum(sum(v['primary_valid'].values()) for v in cons.values()),
      adjudications=agreement['adjudications'],review_ambiguities=agreement['review_ambiguity'],source_uncertainty=agreement['source_uncertainty'],
      train_candidates=len(train),dev_candidates=len(dev),candidate_roles=dict(Counter(v['role'] for v in train+dev)),excluded=len(excluded),
      excluded_disputes=sum(v['semantic_dispute'] for v in excluded),excluded_review_ambiguity=sum(v['review_ambiguity'] for v in excluded),
      human_first_reviews=0,human_second_reviews=0,human_adjudications=0,training_authorized=False),exclusive=True)
    print(__import__('json').dumps(dict(summary=m.read(out/'summary.json'),producer=dict(producer),auditor=dict(auditor)),indent=2))


if __name__=='__main__':main()
