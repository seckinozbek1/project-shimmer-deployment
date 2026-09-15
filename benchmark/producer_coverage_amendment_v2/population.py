"""Full substantive tuning population, gold-free input artifacts only."""
from collections import Counter
from datetime import datetime,timezone
import re,shutil
import semantics as s
SEED='producer-coverage-amendment-v2-20260915'
WORK=s.ROOT/'output/producer_coverage_amendment_v2'
def features(packet):
 text=' '.join(x['text'] for x in packet['source_spans']);low=text.lower()
 return dict(substantive=bool(re.search(r'CLM-',text)),absence=bool(re.search(r'no .*submitted|not submitted|no .*recorded|no .*appears',low)),deictic=bool(re.search(r'\bthis\b|\bthat\b',low)),order_content=bool(re.search(r'what .*entered|what followed|entry order',low)),temporal=bool(re.search(r'\bdate\b|\bwhen\b',low)),gap=bool(re.search(r'\?|missing|absent|unavailable|unnamed',low)),uncertainty=bool(re.search(r'uncertain|unclear|unknown|unresolved',low)),conflict=bool(re.search(r'conflict|contradict',low)),multi_claim=len(set(re.findall(r'CLM-[A-Za-z0-9-]+',text)))>1,evidence_selection=len(packet.get('supplied_refs',[]))>1,context=bool(packet.get('context_only_spans')),multi_span=len(packet['source_spans'])>1)
def inventory():
 root=s.ROOT/'benchmark/task_semantics_v2';meta={r['example_id']:r for r in s.read(root/'family_manifest.json')};rows=[];inputs={}
 for old_id,ids in s.read(root/'review_admin_mapping.json')['packet_to_examples'].items():
  packet=s.read(root/'review_packets'/(old_id+'.json'))['input']
  if packet['role']!='producer':continue
  for eid in ids:
   row=dict(meta[eid],role='producer',features=features(packet))
   if s.eligible_metadata(row):rows.append(row);inputs[eid]=packet
 return sorted(rows,key=lambda x:x['example_id']),inputs

def hard_audit(rows):
 chosen=[]
 for split in ('train','dev'):
  pool=[r for r in rows if r['split']==split];part=[]
  while len(part)<8:
   domains={r['domain'] for r in part};templates={r['template_family'] for r in part};families={r['document_family'] for r in part};feat={k for r in part for k,v in r['features'].items() if v}
   def key(r):return (sum(v and k not in feat for k,v in r['features'].items()),r['template_family'] not in templates,r['domain'] not in domains,r['document_family'] not in families,sum(r['features'].values()),s.digest((SEED+r['example_id']).encode()))
   r=max(pool,key=key);part.append(r);pool.remove(r)
  chosen+=part
 return sorted(r['example_id'] for r in chosen)

def main():
 if (s.HERE/'population.json').exists():raise ValueError('Frozen population cannot be overwritten')
 rows,inputs=inventory()
 if Counter(r['split'] for r in rows)!=dict(train=32,dev=32):raise ValueError('Expected exact32/32 substantive inventory')
 hard=hard_audit(rows);hashes={}
 for r in rows:
  r['packet_id']='producer-v2-'+s.digest((SEED+r['example_id']).encode())[:24];pid=r['packet_id'];inp=inputs[r['example_id']]
  packet=dict(protocol=s.PROTOCOL,policy=s.POLICY,evidence_kind='training_label_curation_evidence',use='curation_only',packet_id=pid,input_sha256=s.digest(inp),input=inp)
  s.write(s.HERE/'inputs'/(pid+'.json'),packet);hashes[pid+'.json']=s.digest((s.HERE/'inputs'/(pid+'.json')).read_bytes())
 s.write(s.HERE/'population.json',dict(protocol=s.PROTOCOL,evidence_kind='training_label_curation_evidence',use='curation_only',selected_at=datetime.now(timezone.utc).isoformat(),seed=SEED,rows=rows,hard_packet_ids=[r['packet_id'] for r in rows if r['example_id'] in hard],packet_hashes=hashes,domains=sorted({r['domain'] for r in rows}),templates=sorted({r['template_family'] for r in rows}),reserve_count=0,authored_targets_accessed=False))
 for slot in 'ABC':
  folder=WORK/('reviewer_'+slot);(folder/'packets').mkdir(parents=True,exist_ok=False);(folder/'reviews').mkdir()
  for name in hashes:shutil.copyfile(s.HERE/'inputs'/name,folder/'packets'/name)
  for name,dest in [('policy.md','POLICY.md'),('reviewer_instructions.md','INSTRUCTIONS.md'),('schema.json','SCHEMA.json')]:shutil.copyfile(s.HERE/name,folder/dest)
  s.isolated(folder,hashes)
 print(__import__('json').dumps(dict(population=Counter(r['split'] for r in rows),hard=len(hard),domains=len({r['domain'] for r in rows}),templates=len({r['template_family'] for r in rows}),reserve=0)))
if __name__=='__main__':main()
