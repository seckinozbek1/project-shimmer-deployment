"""Bounded producer primary collection and committed pre-gold evidence."""
import shutil
from datetime import datetime,timezone
from collections import Counter
import semantics as s
WORK=s.ROOT/'output/producer_coverage_amendment_v1'
def policy_intact():
 f=s.read(s.HERE/'POLICY_FREEZE.json')
 for n,h in f['hashes'].items():
  if s.digest((s.HERE/n).read_bytes())!=h:raise ValueError('Frozen policy drift: '+n)
 return f

def packets():return {p.stem:s.read(p) for p in (s.HERE/'inputs').glob('*.json')}
def validate(v,p,slot):
 required={'protocol','policy','packet_id','input_sha256','slot','provenance','reviewed_at','label','rationale'}
 allowed=required|({'decision','disagreement_causes'} if slot=='D' else set())|{'original_sha256','repair_attempt','repair_kind'}
 if not required<=set(v) or set(v)-allowed:raise ValueError('Outer review schema')
 if v['protocol']!=s.PROTOCOL or v['policy']!=s.POLICY or v['slot']!=slot:raise ValueError('Protocol/slot mismatch')
 if v['packet_id']!=p['packet_id'] or v['input_sha256']!=p['input_sha256'] or p['input_sha256']!=s.digest(p['input']):raise ValueError('Packet/hash binding mismatch')
 if v['provenance']!=('machine_agent_adjudication' if slot=='D' else 'machine_agent_primary'):raise ValueError('Machine provenance required')
 if not isinstance(v['rationale'],str) or not v['rationale'].strip():raise ValueError('Rationale required')
 datetime.fromisoformat(v['reviewed_at'].replace('Z','+00:00'))
 return s.validate_label(v['label'],p['input'])

def effective(slot,pid,base=WORK):
 folder=base/('reviewer_'+slot);original=folder/'reviews'/(pid+'.json');repair=folder/'repairs'/(pid+'.json')
 value=s.read(repair if repair.exists() else original)
 if repair.exists() and (value.get('repair_attempt')!=1 or value.get('repair_kind')!='schema_only' or value.get('original_sha256')!=s.digest(original.read_bytes())):raise ValueError('Unbound/non-schema repair')
 return value

def consensus(values):
 hashes=[s.digest(s.material(v['label'])) for v in values];counts=Counter(hashes);common,n=counts.most_common(1)[0]
 return dict(state='unanimous' if n==3 else 'majority' if n==2 else 'no_majority',selected_slot=values[hashes.index(common)]['slot'] if n>=2 else None,material_hashes=dict(zip('ABC',hashes)))

def collect():
 policy_intact();ps=packets();selection=s.read(s.HERE/'selection.json');required=set(selection['hard_packet_ids']);records={};invalid=[]
 for slot in 'ABC':
  folder=WORK/('reviewer_'+slot);s.isolated(folder,selection['packet_hashes'])
  actual={p.stem for p in (folder/'reviews').glob('*.json')}
  if actual!=set(ps):raise ValueError('Primary population incomplete: '+slot)
  manifest={p.name:s.digest(p.read_bytes()) for p in (folder/'reviews').glob('*.json')};dest=folder/'PRIMARY_HASHES.json'
  if dest.exists() and s.read(dest)!=manifest:raise ValueError('Original primaries changed')
  if not dest.exists():s.write(dest,manifest)
 for pid,p in ps.items():
  values=[effective(slot,pid) for slot in 'ABC'];valid={}
  for slot,v in zip('ABC',values):
   try:validate(v,p,slot);valid[slot]=True
   except (ValueError,TypeError,KeyError) as exc:valid[slot]=False;invalid.append(dict(packet_id=pid,slot=slot,error=str(exc)))
  try:c=consensus(values)
  except (ValueError,TypeError,KeyError):c=dict(state='no_majority',selected_slot=None,material_hashes={})
  c['primary_valid']=valid;records[pid]=c
  if not all(valid.values()) or c['state']=='no_majority':required.add(pid)
 if (WORK/'consensus.json').exists():raise ValueError('Do not overwrite collected evidence')
 s.write(WORK/'consensus.json',records);s.write(WORK/'disagreements.json',dict(required_adjudication=sorted(required),hard=selection['hard_packet_ids'],invalid_primaries=invalid))
 folder=WORK/'adjudicator';(folder/'cases').mkdir(parents=True,exist_ok=False);(folder/'adjudications').mkdir()
 for pid in sorted(required):s.write(folder/'cases'/(pid+'.json'),dict(packet=ps[pid],candidates={slot:effective(slot,pid) for slot in 'ABC'}))
 for src,dest in [('policy.md','POLICY.md'),('schema.json','SCHEMA.json')]:shutil.copyfile(s.HERE/src,folder/dest)
 instruction=(s.HERE/'reviewer_instructions.md').read_text(encoding='utf8')
 instruction+='\nADJUDICATOR: You are fresh D. Read all cases (packet + neutral A/B/C). Write adjudications/<packet_id>.json once. slot D, provenance machine_agent_adjudication. Add decision candidate_A/candidate_B/candidate_C/corrected/unresolved, and disagreement_causes array. Return your complete label. Rationale explains source evidence under policy. Select candidates only if all material fields match. Unresolved means review_ambiguity true. No gold or earlier review outputs. No outside reads. No primary semantic retries.\n'
 (folder/'INSTRUCTIONS.md').write_text(instruction,encoding='utf8')
 print(__import__('json').dumps(dict(primaries=len(ps)*3,invalid=len(invalid),agreement=Counter(r['state'] for r in records.values()),adjudications=len(required))))

def freeze():
 policy_intact();ps=packets();cons=s.read(WORK/'consensus.json');dis=s.read(WORK/'disagreements.json');required=set(dis['required_adjudication'])
 ad=WORK/'adjudicator/adjudications'
 if {p.stem for p in ad.glob('*.json')}!=required:raise ValueError('Adjudications incomplete')
 dest=s.HERE/'blind_evidence'
 if dest.exists():raise ValueError('Never overwrite freeze')
 labels={};av={};canonical={}
 for pid,p in ps.items():
  if pid in required:
   v=s.read(ad/(pid+'.json'))
   try:wire=validate(v,p,'D');valid=True;error=None
   except (ValueError,TypeError,KeyError) as exc:wire=s.render(v['label']);valid=False;error=str(exc)
   av[pid]=dict(valid=valid,error=error)
   if v.get('decision') not in ('candidate_A','candidate_B','candidate_C','corrected','unresolved'):raise ValueError('Adjudication decision')
   if (v['decision']=='unresolved')!=v['label']['review_ambiguity']:raise ValueError('Unresolved flag mismatch')
   if v['decision'].startswith('candidate_') and s.material(v['label'])!=s.material(effective(v['decision'][-1],pid)['label']):raise ValueError('Candidate decision differs from label')
  else:v=effective(cons[pid]['selected_slot'],pid);wire=validate(v,p,v['slot']);valid=True
  labels[pid]=dict(review=v,primary_valid=cons[pid]['primary_valid'],valid=valid,human_reviewed=False);canonical[pid]=wire
 for slot in 'ABC':
  folder=WORK/('reviewer_'+slot)
  for name,h in s.read(folder/'PRIMARY_HASHES.json').items():
   if s.digest((folder/'reviews'/name).read_bytes())!=h:raise ValueError('Primary changed')
  for sub in ('reviews','repairs'):
   for p in (folder/sub).glob('*.json'):
    target=dest/slot/sub/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
  for name in ('PRIMARY_HASHES.json','INSTRUCTIONS.md','POLICY.md','SCHEMA.json'):shutil.copyfile(folder/name,dest/slot/name)
 shutil.copytree(ad,dest/'adjudications')
 for name in ('consensus.json','disagreements.json'):shutil.copyfile(WORK/name,dest/name)
 for name in ('POLICY_FREEZE.json','selection.json'):shutil.copyfile(s.HERE/name,dest/name)
 s.write(dest/'labels.json',labels);s.write(dest/'canonical_targets.json',canonical);s.write(dest/'adjudication_validation.json',av)
 s.write(dest/'isolation.json',dict(fresh_primary_contexts=3,fresh_adjudicator=True,detected_violations=0,method='Exact packet hashes, folder-only instructions and agent attestations; shared filesystem/parent model, no OS enforcement or cross-model diversity',human_reviewed=False))
 s.write(dest/'PRE_GOLD_FREEZE.json',dict(protocol=s.PROTOCOL,frozen_at=datetime.now(timezone.utc).isoformat(),primaries=len(ps)*3,repairs=sum(len(list((dest/slot/'repairs').glob('*.json'))) for slot in 'ABC'),adjudications=len(required),hashes={p.relative_to(dest).as_posix():s.digest(p.read_bytes()) for p in dest.rglob('*') if p.is_file()}))
 print('Pre-gold freeze complete:',len(labels),'labels;',len(required),'adjudications')
def verify_freeze():
 f=s.read(s.HERE/'blind_evidence/PRE_GOLD_FREEZE.json')
 for n,h in f['hashes'].items():
  if s.digest((s.HERE/'blind_evidence'/n).read_bytes())!=h:raise ValueError('Frozen review drift')
 return f
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['collect','freeze']);a=p.parse_args();(collect if a.stage=='collect' else freeze)()
