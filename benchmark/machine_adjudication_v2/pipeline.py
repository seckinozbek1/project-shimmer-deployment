"""Collect fresh primary evidence and freeze V2 before authored comparison."""
from pathlib import Path
from datetime import datetime,timezone
import shutil,json
import review as m


def effective(slot,ident):
    folder=m.WORK/('reviewer_'+slot);original=folder/'reviews'/(ident+'.json');value=m.read(original)
    repaired=folder/'repairs'/(ident+'.json')
    if repaired.exists():
        value=m.read(repaired)
        if value.get('original_sha256')!=m.sha(original.read_bytes()) or value.get('repair_attempt')!=1 or value.get('repair_kind')!='schema_only':
            raise ValueError('Unbound repair')
    return value


def collect():
    ps=m.packets();all_cons={};issues=[]
    exports=m.read(m.ROOT/'benchmark/first_tuning_review_cohort_v2/export_admin_manifest.json')
    hard=set(next(v['packet_ids'] for v in exports.values() if v['slot']==2));required=set(hard)
    for slot in 'ABC':
        folder=m.WORK/('reviewer_'+slot)
        paths=list((folder/'reviews').glob('*.json'))
        if {p.stem for p in paths}!=set(ps):raise ValueError('Primary slot population incomplete: '+slot)
        hashes={p.name:m.sha(p.read_bytes()) for p in sorted(paths)}
        if (folder/'PRIMARY_HASHES.json').exists():
            if m.read(folder/'PRIMARY_HASHES.json')!=hashes:raise ValueError('Primary overwritten')
        else:m.write(folder/'PRIMARY_HASHES.json',hashes,exclusive=True)
    for ident,p in ps.items():
        values=[effective(slot,ident) for slot in 'ABC'];valid={}
        for v in values:
            try:m.validate(v,p,v['slot']);valid[v['slot']]=True
            except (ValueError,TypeError,KeyError) as exc:
                valid[v['slot']]=False;issues.append(dict(packet_id=ident,slot=v['slot'],error=str(exc)))
        try:record=m.consensus(values,p['input']['role'])
        except (ValueError,KeyError,TypeError):record=dict(state='no_majority',selected_slot=None,agreeing_slots=[],material_hashes={})
        record.update(primary_valid=valid,designated_hard=ident in hard)
        if record['state']=='no_majority' or not all(valid.values()):required.add(ident)
        all_cons[ident]=record
    m.write(m.WORK/'consensus.json',all_cons,exclusive=True)
    m.write(m.WORK/'disagreements.json',dict(required_adjudication=sorted(required),designated_hard=sorted(hard),invalid_primaries=issues),exclusive=True)
    folder=m.WORK/'adjudicator';(folder/'cases').mkdir(parents=True,exist_ok=True);(folder/'adjudications').mkdir(exist_ok=True)
    for ident in sorted(required):m.write(folder/'cases'/(ident+'.json'),dict(packet=ps[ident],candidates={s:effective(s,ident) for s in 'ABC'}),exclusive=True)
    shutil.copyfile(m.HERE/'reviewer_instructions.md',folder/'INSTRUCTIONS.md')
    schema=m.read(m.WORK/'reviewer_A/MACHINE_SCHEMA.json');schema.update(slot='D',provenance='machine_agent_adjudication',run_id='machine-agent-review-v2-D',
       extra_fields=['decision','disagreement_causes'],decisions=['candidate_A','candidate_B','candidate_C','corrected','unresolved'])
    m.write(folder/'MACHINE_SCHEMA.json',schema)
    from collections import Counter
    print(json.dumps(dict(agreement=dict(Counter(v['state'] for v in all_cons.values())),invalid=len(issues),adjudications=len(required))))


def freeze():
    ps=m.packets();cons=m.read(m.WORK/'consensus.json');dis=m.read(m.WORK/'disagreements.json')
    required=set(dis['required_adjudication']);ad=m.WORK/'adjudicator/adjudications'
    if {p.stem for p in ad.glob('*.json')}!=required:raise ValueError('Adjudications incomplete')
    dest=m.HERE/'blind_evidence'
    if dest.exists():raise ValueError('Never overwrite frozen review evidence')
    iso=m.read(m.WORK/'isolation_manifest.json');repair_count=0
    method=m.read(m.HERE/'PRE_REVIEW_METHOD_FREEZE.json')
    for name,expected in method['hashes'].items():
        if m.sha((m.HERE/name).read_bytes())!=expected:raise ValueError('Prospective method drift')
    for slot in 'ABC':
        folder=m.WORK/('reviewer_'+slot);m.verify_isolation(folder,iso['packet_hashes'])
        for name,h in m.read(folder/'PRIMARY_HASHES.json').items():
            if m.sha((folder/'reviews'/name).read_bytes())!=h:raise ValueError('Primary changed')
        for sub in ('reviews','repairs'):
            for p in (folder/sub).glob('*.json'):
                target=dest/slot/sub/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
                if sub=='repairs':repair_count+=1
        for name in ('PRIMARY_HASHES.json','INSTRUCTIONS.md','MACHINE_SCHEMA.json'):
            shutil.copyfile(folder/name,dest/slot/name)
    labels={};ad_valid={}
    for ident,p in ps.items():
        initial=cons[ident]
        if ident in required:
            value=m.read(ad/(ident+'.json'))
            if value.get('decision') not in ('candidate_A','candidate_B','candidate_C','corrected','unresolved'):raise ValueError('Adjudicator decision absent')
            if not isinstance(value.get('disagreement_causes'),list):raise ValueError('Typed disagreement cause absent')
            try:m.validate(value,p,'D');valid=True;error=None
            except (ValueError,TypeError,KeyError) as exc:valid=False;error=str(exc)
            ad_valid[ident]=dict(valid=valid,error=error)
            target=dest/'adjudications'/(ident+'.json');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ad/(ident+'.json'),target)
            same=(m.material(value,p['input']['role'])==m.material(effective(initial['selected_slot'],ident),p['input']['role'])) if initial['selected_slot'] and valid else None
            provenance='machine_agent_adjudication'
        else:
            value=effective(initial['selected_slot'],ident);valid=True;same=None;provenance='machine_agent_consensus'
        labels[ident]=dict(packet_id=ident,review=value,valid=valid,primary_valid=initial['primary_valid'],provenance=provenance,human_reviewed=False,
                          review_ambiguity=value['review_ambiguity'],source_uncertainty_present=value['source_uncertainty_present'],adjudicator_agrees_with_majority=same)
    m.write(dest/'labels.json',labels,exclusive=True);m.write(dest/'adjudication_validation.json',ad_valid,exclusive=True)
    for name in ('consensus.json','disagreements.json','isolation_manifest.json'):shutil.copyfile(m.WORK/name,dest/name)
    projection=m.read(m.HERE/'PRE_GOLD_PROJECTION_FREEZE.json')
    for name,expected in projection['hashes'].items():
        if m.sha((m.HERE/name).read_bytes())!=expected:raise ValueError('Pre-gold projection drift')
    for name in ('PRE_REVIEW_METHOD_FREEZE.json','PRE_GOLD_PROJECTION_FREEZE.json','protocol.json'):shutil.copyfile(m.HERE/name,dest/name)
    m.write(dest/'adjudicator_input_hashes.json',{p.name:m.sha(p.read_bytes()) for p in sorted((m.WORK/'adjudicator/cases').glob('*.json'))},exclusive=True)
    hashes={p.relative_to(dest).as_posix():m.sha(p.read_bytes()) for p in sorted(dest.rglob('*')) if p.is_file()}
    m.write(dest/'PRE_GOLD_FREEZE.json',dict(phase='V2_MACHINE_LABELS_FROZEN_BEFORE_GOLD',frozen_at=datetime.now(timezone.utc).isoformat(),
            primary_judgments=576,repairs=repair_count,adjudications=len(required),labels=192,hashes=hashes),exclusive=True)
    print('V2 pre-gold freeze:',len(labels),'labels;',len(required),'adjudications;',sum(not v['valid'] for v in ad_valid.values()),'invalid adjudications')


def verify_freeze():
    f=m.read(m.HERE/'blind_evidence/PRE_GOLD_FREEZE.json')
    for name,expected in f['hashes'].items():
        if m.sha((m.HERE/'blind_evidence'/name).read_bytes())!=expected:raise ValueError('V2 frozen evidence changed')
    return f


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['collect','freeze']);args=p.parse_args()
    (collect if args.stage=='collect' else freeze)()
