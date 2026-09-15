"""Source-only deterministic reserve selection; never opens seed/extension targets."""
import re,math,shutil
from collections import Counter
from datetime import datetime,timezone
import semantics as s
SEED='producer-coverage-amendment-v1-20260915'
WORK=s.ROOT/'output/producer_coverage_amendment_v1'
def features(packet):
 text=' '.join(v['text'] for v in packet['source_spans']);low=text.lower()
 return dict(substantive=bool(re.search(r'CLM-',text)),multi_claim=len(set(re.findall(r'CLM-[A-Za-z0-9-]+',text)))>1,
 gap=bool(re.search(r'\?|missing|unavailable|absent|not supplied|not provided|unnamed',low)),uncertainty=bool(re.search(r'uncertain|unclear|unknown|unresolved',low)),
 contradiction=bool(re.search(r'conflict|contradict',low)),context=bool(packet.get('context_only_spans')),multi_span=len(packet['source_spans'])>1,
 evidence_selection=len(set(packet.get('supplied_refs',[])))>1)
def choose(rows,n,initial=()):
 chosen=[];prior=list(initial);pool=list(rows)
 while pool and len(chosen)<n:
  covered=prior+chosen;counts={k:Counter(r[k] for r in covered) for k in ('domain','template_family','document_family')}
  feat=Counter(k for r in covered for k,v in r['features'].items() if v)
  def key(r):
   f=r['features']
   return (f['substantive'],sum(f[k] and not feat[k] for k in f),r['template_family'] not in counts['template_family'],r['domain'] not in counts['domain'],r['document_family'] not in counts['document_family'],sum(f.values()),-counts['document_family'][r['document_family']],s.digest((SEED+r['example_id']).encode()))
  r=max(pool,key=key);chosen.append(r);pool.remove(r)
 return chosen

def main():
 freeze=s.read(s.HERE/'POLICY_FREEZE.json')
 for n,h in freeze['hashes'].items():
  if s.digest((s.HERE/n).read_bytes())!=h:raise ValueError('Policy drift before selection')
 root=s.ROOT/'benchmark/task_semantics_v2';mapping=s.read(root/'review_admin_mapping.json')['packet_to_examples'];families={r['example_id']:r for r in s.read(root/'family_manifest.json')}
 current=set(s.read(s.ROOT/'benchmark/first_tuning_review_cohort_v2/cohort.json')['ids']);rows=[];packets={}
 for packet_id,ids in mapping.items():
  # Packet artifacts are already gold-free, unlike authored seed/extension files.
  packet=s.read(root/'review_packets'/(packet_id+'.json'))['input']
  if packet['role']!='producer':continue
  for eid in ids:
   row=dict(families[eid],role='producer')
   if not s.eligible_metadata(row):continue
   row.update(packet_id=packet_id,features=features(packet));rows.append(row);packets[eid]=packet
 base=[r for r in rows if r['example_id'] in current]
 if Counter(r['split'] for r in base)!=dict(train=32,dev=16):raise ValueError('Active producer population changed')
 selected=[];reserves=[];available={}
 for split in ('train','dev'):
  required=[r for r in base if r['split']==split];unused=[r for r in rows if r['split']==split and r['example_id'] not in current]
  reserve=choose(unused,min(16,len(unused)),required);reserves+=reserve;selected+=required+reserve
  available[split]=dict(total=len(required)+len(unused),unused=len(unused),reserve_selected=len(reserve))
 selected=sorted(selected,key=lambda r:r['example_id']);hard=[]
 for split in ('train','dev'):
  part=[r for r in selected if r['split']==split];hard+=choose(part,math.ceil(len(part)/4))
 # Rebind each packet to this amendment without split/domain/admin fields.
 allhash={}
 for r in selected:
  inp=packets[r['example_id']];pid='producer-'+s.digest((SEED+r['example_id']).encode())[:24];r['packet_id']=pid
  packet=dict(protocol=s.PROTOCOL,policy=s.POLICY,packet_id=pid,input_sha256=s.digest(inp),input=inp)
  s.write(s.HERE/'inputs'/(pid+'.json'),packet);allhash[pid+'.json']=s.digest((s.HERE/'inputs'/(pid+'.json')).read_bytes())
 # hard entries share row objects, hence already rebound.
 selection=dict(protocol=s.PROTOCOL,seed=SEED,selected_at=datetime.now(timezone.utc).isoformat(),policy_freeze_sha256=s.digest((s.HERE/'POLICY_FREEZE.json').read_bytes()),
  available=available,attainable_domains=sorted({r['domain'] for r in rows}),attainable_templates=sorted({r['template_family'] for r in rows}),
  base_ids=sorted(r['example_id'] for r in base),reserve_ids=sorted(r['example_id'] for r in reserves),rows=selected,hard_packet_ids=sorted(r['packet_id'] for r in hard),packet_hashes=allhash,
  source_admin_files={n:s.digest((root/n).read_bytes()) for n in ('review_admin_mapping.json','family_manifest.json')},authored_targets_accessed=False)
 s.write(s.HERE/'selection.json',selection)
 for slot in 'ABC':
  folder=WORK/('reviewer_'+slot);(folder/'packets').mkdir(parents=True,exist_ok=False);(folder/'reviews').mkdir()
  for pid in allhash:shutil.copyfile(s.HERE/'inputs'/pid,folder/'packets'/pid)
  for src,dest in [('policy.md','POLICY.md'),('reviewer_instructions.md','INSTRUCTIONS.md'),('schema.json','SCHEMA.json')]:shutil.copyfile(s.HERE/src,folder/dest)
  s.isolated(folder,allhash)
 print(__import__('json').dumps(dict(selected=Counter(r['split'] for r in selected),available=available,hard=len(hard),domains=len(selection['attainable_domains']),templates=len(selection['attainable_templates']))))
if __name__=='__main__':main()
