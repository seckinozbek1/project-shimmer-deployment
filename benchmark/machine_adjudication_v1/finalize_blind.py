"""Freeze machine evidence before any authored-target comparison is permitted."""
from datetime import datetime,timezone
from pathlib import Path
import shutil
import review as m


def main():
    packets=m.packets();cons=m.read(m.WORK/'consensus_initial.json');dis=m.read(m.WORK/'disagreements.json')
    required=set(dis['required_adjudication']);adjud_dir=m.WORK/'adjudicator/adjudications'
    if {p.stem for p in adjud_dir.glob('*.json')}!=required:raise ValueError('Adjudication set incomplete')
    destination=m.HERE/'blind_evidence'
    if destination.exists():raise ValueError('Do not overwrite frozen machine evidence')
    isolation=m.read(m.WORK/'isolation_manifest.json')
    labels={};adjudication_validation={}
    for slot in 'ABC':
        folder=m.WORK/('reviewer_'+slot)
        m.verify_clean_workspace(folder,isolation['packet_hashes'])
        primary=m.read(folder/'PRIMARY_HASHES.json')
        if len(primary)!=192:raise ValueError('Incomplete primary hash manifest')
        for name,expected in primary.items():
            if m.sha((folder/'reviews'/name).read_bytes())!=expected:raise ValueError('Primary overwritten')
        for sub in ['reviews','repairs']:
            for p in sorted((folder/sub).glob('*.json')):
                target=destination/slot/sub/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        for name in ['PRIMARY_HASHES.json','MACHINE_SCHEMA.json','INSTRUCTIONS.md','schema_feedback.json']:
            shutil.copyfile(folder/name,destination/slot/name)
    for ident,packet in packets.items():
        initial=cons[ident]
        if ident in required:
            path=adjud_dir/(ident+'.json');value=m.read(path)
            if value.get('decision') not in ('candidate_A','candidate_B','candidate_C','corrected','unresolved'):
                raise ValueError('Adjudication decision absent')
            if not isinstance(value.get('disagreement_causes'),list):raise ValueError('Typed adjudication causes absent')
            try:m.validate(value,packet,'D');valid=True;error=None
            except (ValueError,KeyError,TypeError) as exc:valid=False;error=str(exc)
            adjudication_validation[ident]=dict(valid=valid,error=error)
            target=destination/'adjudications'/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
            unresolved=value['decision']=='unresolved' or value['ambiguity']
            agrees=(m.material(value,packet['input']['role'])==m.material(m.effective(initial['selected_slot'],ident),packet['input']['role'])) if initial['selected_slot'] else None
            provenance='machine_agent_adjudication'
        else:
            if not initial['clean_consensus']:raise ValueError('Missing required adjudication')
            value=m.effective(initial['selected_slot'],ident);valid=True;unresolved=value['ambiguity'];agrees=None;provenance='machine_agent_consensus'
        labels[ident]=dict(packet_id=ident,provenance=provenance,human_reviewed=False,review=value,
                          valid=valid,unresolved=bool(unresolved),adjudicator_agrees_with_majority=agrees,
                          primary_valid=initial['primary_valid'])
    m.write(destination/'consensus_labels.json',labels,exclusive=True)
    for name in ['consensus_initial.json','disagreements.json','isolation_manifest.json','primary_validation_initial.json']:
        shutil.copyfile(m.WORK/name,destination/name)
    shutil.copyfile(m.HERE/'protocol.json',destination/'protocol.json')
    m.write(destination/'adjudication_validation.json',adjudication_validation,exclusive=True)
    # Pin source/instructions passed to adjudicator and all primary input hashes,
    # without putting any authored answers into a reviewer-facing workspace.
    m.write(destination/'adjudicator_input_hashes.json',{p.name:m.sha(p.read_bytes()) for p in sorted((m.WORK/'adjudicator/cases').glob('*.json'))},exclusive=True)
    m.write(destination/'review_control_code_hashes.json',{p.name:m.sha(p.read_bytes()) for p in [m.HERE/'review.py',m.HERE/'finalize_blind.py',m.HERE/'eligibility.py',m.HERE/'r06.py']},exclusive=True)
    hashes={p.relative_to(destination).as_posix():m.sha(p.read_bytes()) for p in sorted(destination.rglob('*')) if p.is_file()}
    m.write(destination/'PRE_GOLD_FREEZE.json',dict(phase='MACHINE_LABELS_FROZEN_BEFORE_GOLD',
            frozen_at=datetime.now(timezone.utc).isoformat(),primary_count=576,repair_count=252,
            adjudication_count=len(required),label_count=len(labels),human_reviews=0,
            authored_targets_opened_for_comparison=False,hashes=hashes),exclusive=True)
    m.verify_pre_gold(destination/'PRE_GOLD_FREEZE.json')
    print('Machine review labels frozen before gold:',len(labels),'adjudications:',len(required),'invalid adjudications:',sum(not v['valid'] for v in adjudication_validation.values()))


if __name__=='__main__':main()
