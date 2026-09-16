"""Decompose saved scores and raw atoms; never invoke the historical scorer."""
from local_common import *
import itertools

EVIDENCE = ROOT/'docs/fix/producer_checkpoint120_eval_v2_1/downloaded/evidence'
TAGS = ['refusal_when_substantive_required','missing_gap','partially_missing_gap_set',
        'wrong_gap_referent','wrong_gap_attribute','wrong_gap_state_type',
        'missing_uncertainty','extra_uncertainty','claim_failure','evidence_failure',
        'status_inconsistency','contract_failure','other_semantic_incompleteness']
CATEGORIES = ['omission','referent','attribute','state_type','ordinal_order_content',
              'temporal_role','absence_vs_unknown','other']

def atoms(obj):
    return [dict(kind=kind, span=i['span'], **json.loads(value.split(': ',1)[1]))
            for i in obj['items'] for key,kind in [('questions','gap'),('uncertainty','uncertainty')]
            for value in i[key]]

def deltas(gold, pred):
    g={canonical(x):x for x in atoms(gold)};p={canonical(x):x for x in atoms(pred)}
    return [g[k] for k in sorted(g.keys()-p.keys())],[p[k] for k in sorted(p.keys()-g.keys())]

def category(g,p):
    if p is None:return 'omission'
    if g is None:return 'other'
    if g['kind']!=p['kind']:return 'absence_vs_unknown' if g['kind']=='gap' else 'state_type'
    changed={k for k in g if g[k]!=p[k]}
    if changed<={'subject','span'}:return 'referent'
    if changed=={'attribute'}:
        temporal=lambda a:a.endswith('_time') or a=='date_unspecified'
        return 'temporal_role' if temporal(g['attribute']) and temporal(p['attribute']) else 'attribute'
    if g['attribute'] in ('entry_order','entry_content') or changed=={'ordinal'}:return 'ordinal_order_content'
    if changed<={'state','category'}:return 'state_type'
    if 'attribute' in changed:return 'attribute'
    return 'other'

def pair(fn,fp):
    # Human-readable deterministic minimum-field-distance attribution only.
    # TP/FP/FN stay the exact frozen string counts; pairing changes no metric.
    if not fn:return [(None,p) for p in fp]
    if not fp:return [(g,None) for g in fn]
    n=max(len(fn),len(fp));gs=fn+[None]*(n-len(fn));ps=fp+[None]*(n-len(fp))
    def cost(g,p):
        if g is None or p is None:return 6
        return sum(g[k]!=p[k] for k in g)+3*(g['span']!=p['span'])
    perm=min(itertools.permutations(range(n)),key=lambda ix:(sum(cost(g,ps[i]) for g,i in zip(gs,ix)),ix))
    return [(g,ps[i]) for g,i in zip(gs,perm)]

def features(row,raw):
    label=row['typed_label'];items=label['items'];text='\n'.join(x['text'] for x in row['input']['source_spans'])
    return dict(domain=row['domain'],structural_family=row['template_family'],rendering_template=row.get('rendering_template',row['template_family']),source_chars=len(text),
        prompt_tokens=len(raw['input_ids']),source_spans=len(row['input']['source_spans']),
        claims=sum(len(i['claims']) for i in items),refs=len(row['input']['required_refs']),
        gaps=sum(len(i['gap_atoms']) for i in items),uncertainties=sum(len(i['uncertainty_atoms']) for i in items),
        gap_attributes=[a['attribute'] for i in items for a in i['gap_atoms']],
        conflicting_claims='same entry as' in text,absence_language=any(w in text.lower() for w in ('missing','unavailable','unspecified','no first','not recorded','not submitted')),
        ontology_boundary_wording='quantitative value' in text,source=text)

def run():
    dataset={r['example_id']:r for r in read(ROOT/'tuning/second_domain_agnostic_v2/dataset.json') if r['role']=='producer'}
    raw=read(EVIDENCE/'full_dev_scored.json');assert len(raw)==60
    failures=[];counts=Counter({k:0 for k in TAGS});gap_counts={k:Counter({c:0 for c in CATEGORIES}) for k in ('fn','fp')}
    totals={k:sum(x['metrics']['typed_gaps'][k] for x in raw) for k in ('tp','fp','fn')}
    cohorts={'false_refusal':[],'valid_refusal':[],'substantive_non_refusal':[]}
    for x in raw:
        row=dataset[x['example_id']];m=x['metrics'];gold=row['canonical_target'];pred=json.loads(x['raw_output'])
        f=features(row,x)
        cohort='valid_refusal' if m['expected_refusal'] else 'false_refusal' if m['predicted_refusal'] else 'substantive_non_refusal' if row['substantive'] else None
        if cohort:cohorts[cohort].append(dict(example_id=x['example_id'],**f))
        if m['accepted_outcome']:continue
        fn,fp=deltas(gold,pred);pairs=pair(fn,fp);tags=set();records=[]
        for g,p in pairs:
            c=category(g,p);records.append(dict(expected=g,observed=p,primary_class=c))
            for k,a in [('fn',g),('fp',p)]:
                if a and a['kind']=='gap':gap_counts[k][c]+=1
            if g and g['kind']=='gap':
                tags.add('missing_gap')
                if p:
                    if g['subject']!=p['subject'] or g['span']!=p['span']:tags.add('wrong_gap_referent')
                    if g['attribute']!=p['attribute']:tags.add('wrong_gap_attribute')
                    if any(g[k]!=p[k] for k in ('kind','state','category')):tags.add('wrong_gap_state_type')
        if m['predicted_refusal']:tags|={'refusal_when_substantive_required','status_inconsistency'}
        if m['typed_gaps']['tp'] and m['typed_gaps']['fn']:tags.add('partially_missing_gap_set')
        if m['typed_uncertainty']['fn']:tags.add('missing_uncertainty')
        if m['typed_uncertainty']['fp']:tags.add('extra_uncertainty')
        for metric,tag in [('claims','claim_failure'),('evidence','evidence_failure')]:
            if m[metric]['fn'] or m[metric]['fp']:tags.add(tag)
        if not m['contract_valid']:tags.add('contract_failure')
        for item in pred['items']:
            expected_status='extracted' if any(item[k] for k in ('claims','questions','uncertainty')) else 'empty'
            if item['status']!=expected_status:tags.add('status_inconsistency')
        if not tags:tags.add('other_semantic_incompleteness')
        counts.update(tags)
        failures.append(dict(example_id=x['example_id'],features=f,tags=sorted(tags),saved_metrics=m,
            expected=gold,observed=pred,atom_edits=records,semantic_atom_corrections=len(records),
            attribution_note='Minimum field-distance diagnostic pairing; multi-field pairs are descriptive, not a causal claim.'))
    assert len(failures)==25
    assert sum(gap_counts['fn'].values())==totals['fn'] and sum(gap_counts['fp'].values())==totals['fp']
    # Compare against saved score counts without calling score/aggregate.
    for x in failures:
        for kind,key in [('gap','typed_gaps'),('uncertainty','typed_uncertainty')]:
            assert sum(a['expected'] is not None and a['expected']['kind']==kind for a in x['atom_edits'])==x['saved_metrics'][key]['fn']
            assert sum(a['observed'] is not None and a['observed']['kind']==kind for a in x['atom_edits'])==x['saved_metrics'][key]['fp']
    complete=dict(failed_rows=25,failed_non_refusal=22,failed_refusal=3,
        all_claims_preserved_but_gap_deficit=sum(x['saved_metrics']['typed_gaps']['fn']>0 for x in failures),
        nonrefusal_all_claims_preserved_but_gap_deficit=sum(not x['saved_metrics']['predicted_refusal'] and x['saved_metrics']['typed_gaps']['fn']>0 for x in failures),
        missing_uncertainty=counts['missing_uncertainty'],partially_correct_gap_sets=counts['partially_missing_gap_set'],
        one_atom_correction=sum(x['semantic_atom_corrections']==1 for x in failures),multiple_atom_corrections=sum(x['semantic_atom_corrections']>1 for x in failures),
        correction_distribution=dict(Counter(x['semantic_atom_corrections'] for x in failures)))
    train_ids=set(read(ROOT/'tuning/second_domain_agnostic_v2/splits.json')['canonical']['train'])
    train_atoms=Counter(canonical({k:a[k] for k in ('kind','category','subject','attribute','ordinal','state')})
        for row in dataset.values() if row['example_id'] in train_ids for i in row['typed_label']['items'] for a in i['gap_atoms'])
    for case in cohorts['false_refusal']:
        row=dataset[case['example_id']]
        case['gold_gap_train_occurrences']=[dict(attribute=a['attribute'],count=train_atoms[canonical({k:a[k] for k in ('kind','category','subject','attribute','ordinal','state')})]) for i in row['typed_label']['items'] for a in i['gap_atoms']]
    result=dict(method='Read saved verdicts/scores; inspect raw vs gold atom differences. No historical rescoring or relabeling.',
        failure_tags=counts,gap_totals=totals,gap_error_classes=gap_counts,completeness=complete,failed_rows=failures,refusal_cohorts=cohorts)
    write(HERE/'failure_audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('failed_rows','refusal_cohorts')},indent=2))

if __name__=='__main__':run()
