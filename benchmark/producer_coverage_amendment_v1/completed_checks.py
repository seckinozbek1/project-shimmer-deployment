"""Completed producer audit, preserving failures rather than promoting them."""
import unittest
from collections import Counter
from datetime import datetime
import semantics as s
s.sys.path.insert(0,str(s.HERE))
import review_flow as f
import reserve_guard
B=s.HERE/'blind_evidence';P=s.HERE/'post_freeze';A=s.HERE/'machine_adjudicated_producer_candidates_v1'

class Completed(unittest.TestCase):
 def test_historical_selection_cannot_be_overwritten(self):
  import select_population as sp
  before=s.digest((s.HERE/'selection.json').read_bytes())
  with self.assertRaisesRegex(ValueError,'Historical selection is immutable'):sp.main()
  self.assertEqual(before,s.digest((s.HERE/'selection.json').read_bytes()))

 def test_method_and_packet_freezes(self):
  policy=f.policy_intact();freeze=f.verify_freeze();sel=s.read(s.HERE/'selection.json')
  self.assertLess(datetime.fromisoformat(policy['frozen_at']),datetime.fromisoformat(sel['selected_at']))
  opened=s.read(P/'GOLD_COMPARISON_STARTED.json')
  self.assertLess(datetime.fromisoformat(freeze['frozen_at']),datetime.fromisoformat(opened['started_at']))
  self.assertEqual(opened['pre_gold_commit'],'6f12153e3bf53dcb3a629572179edb82c39dd90f')
  for n,h in sel['packet_hashes'].items():self.assertEqual(s.digest((s.HERE/'inputs'/n).read_bytes()),h)
 def test_primary_slots_and_actual_validity(self):
  packets=f.packets();cons=s.read(B/'consensus.json');count=0
  for slot in 'ABC':
   paths=list((B/slot/'reviews').glob('*.json'));self.assertEqual(len(paths),80);self.assertEqual({p.stem for p in paths},set(packets))
   self.assertFalse(list((B/slot/'repairs').glob('*.json')))
   for p in paths:
    v=s.read(p)
    try:f.validate(v,packets[p.stem],slot);valid=True
    except ValueError:valid=False
    self.assertEqual(valid,cons[p.stem]['primary_valid'][slot]);count+=valid
    self.assertEqual(s.digest(p.read_bytes()),s.read(B/slot/'PRIMARY_HASHES.json')[p.name])
  self.assertEqual(count,222)
 def test_consensus_recomputed(self):
  cons=s.read(B/'consensus.json')
  for pid,c in cons.items():
   result=f.consensus([s.read(B/slot/'reviews'/(pid+'.json')) for slot in 'ABC'])
   for k,v in result.items():self.assertEqual(c[k],v)
  self.assertEqual(Counter(c['state'] for c in cons.values()),dict(unanimous=67,majority=12,no_majority=1))
 def test_required_adjudication(self):
  dis=s.read(B/'disagreements.json');cons=s.read(B/'consensus.json');av=s.read(B/'adjudication_validation.json')
  required=set(dis['hard'])|{pid for pid,c in cons.items() if c['state']=='no_majority' or not all(c['primary_valid'].values())}
  self.assertEqual(required,set(av));self.assertEqual(len(av),26);self.assertEqual(len(dis['hard']),20)
  self.assertTrue(all(av[pid]['valid'] for pid in dis['hard']))
  packets=f.packets()
  for pid in required:
   v=s.read(B/'adjudications'/(pid+'.json'))
   try:f.validate(v,packets[pid],'D');valid=True
   except ValueError:valid=False
   self.assertEqual(valid,av[pid]['valid']);self.assertFalse(v['label']['review_ambiguity'])
 def test_canonical_bindings(self):
  labels=s.read(B/'labels.json');targets=s.read(B/'canonical_targets.json')
  for pid,e in labels.items():
   self.assertEqual(s.render(e['review']['label']),targets[pid])
   if e['valid']:self.assertEqual(s.validate_label(e['review']['label'],f.packets()[pid]['input']),targets[pid])
 def test_population_train_dev_and_no_evaluation(self):
  sel=s.read(s.HERE/'selection.json');self.assertEqual(len(sel['rows']),80)
  self.assertEqual(Counter(r['split'] for r in sel['rows']),dict(train=48,dev=32))
  self.assertTrue(all(s.eligible_metadata(r) for r in sel['rows']))
  self.assertEqual(len(sel['base_ids']),48);self.assertEqual(len(sel['reserve_ids']),32)
  self.assertFalse(set(sel['base_ids'])&set(sel['reserve_ids']))
 def test_reserve_selection_reproducibility(self):
  import select_population as sp
  root=s.ROOT/'benchmark/task_semantics_v2';meta={r['example_id']:r for r in s.read(root/'family_manifest.json')};rows=[]
  for pid,ids in s.read(root/'review_admin_mapping.json')['packet_to_examples'].items():
   packet=s.read(root/'review_packets'/(pid+'.json'))['input']
   if packet['role']!='producer':continue
   for eid in ids:
    r=dict(meta[eid],role='producer',features=sp.features(packet))
    if s.eligible_metadata(r):rows.append(r)
  sel=s.read(s.HERE/'selection.json');base=set(sel['base_ids']);actual=[]
  for split in ('train','dev'):
   required=[r for r in rows if r['example_id'] in base and r['split']==split]
   pool=[r for r in rows if r['example_id'] not in base and r['split']==split]
   actual += [r['example_id'] for r in sp.choose(pool,16,required)]
   guarded=reserve_guard.compliant_reserve(pool,16,required)
   self.assertTrue(all(r['features']['substantive'] for r in guarded))
   self.assertEqual(len(guarded),0 if split=='train' else 16)
  self.assertEqual(set(actual),set(sel['reserve_ids']))
 def test_noncompliant_reserve_fail_closed(self):
  compliance=s.read(s.HERE/'selection_compliance.json');self.assertFalse(compliance['selection_governance_pass']);self.assertEqual(compliance['disallowed_reserve_count'],16)
  allowed=set(s.read(A/'manifest.json')['allowed_ids']);self.assertFalse(allowed&set(compliance['disallowed_reserve_ids']))
 def test_candidates_only_resolved_valid_machine_labels(self):
  labels=s.read(B/'labels.json');comp=s.read(P/'legacy_comparison.json');packets=f.packets()
  rows=s.read(A/'train.json')+s.read(A/'dev.json');self.assertEqual(len(rows),36)
  for r in rows:
   pid=r['packet_id'];entry=labels[pid]
   self.assertTrue(all(entry['primary_valid'].values()));self.assertTrue(entry['valid']);self.assertTrue(comp[pid]['material_dispute_resolved'])
   self.assertFalse(r['human_reviewed']);self.assertFalse(r['typed_label']['review_ambiguity']);self.assertEqual(r['provenance'],'machine_adjudicated_producer_candidate_v1')
   self.assertEqual(s.validate_label(r['typed_label'],packets[pid]['input']),r['canonical_target'])
  manifest=s.read(A/'manifest.json')
  for n,h in manifest['files'].items():self.assertEqual(s.digest((A/n).read_bytes()),h)
  self.assertFalse(manifest['training_authorized'])
 def test_no_diagnostic_or_admin_in_candidate_directory(self):
  self.assertEqual({p.name for p in A.iterdir()},{'train.json','dev.json','manifest.json'})
  self.assertFalse((s.HERE/'balanced_training_manifests').exists())
 def test_v2_v1_acceptance_immutable(self):
  for name in ('machine_adjudication_v1','machine_adjudication_v2'):
   root=s.ROOT/'benchmark'/name
   for n,h in s.read(root/'release_freeze.json')['hashes'].items():self.assertEqual(s.digest((root/n).read_bytes()),h)
  self.assertEqual(s.digest((s.ROOT/'benchmark/first_tuning_experiment_v1/acceptance_registration.json').read_bytes()),'8b70b096b128183707b2cc77c7577efebc8a5232336316a498f133306e3495da')
 def test_auditor_unchanged_and_human_pending(self):
  root=s.ROOT/'benchmark/machine_adjudication_v2/machine_adjudicated_training_access_v2'
  for split,n in [('train',46),('dev',24)]:
   rows=[r for r in s.read(root/(split+'.json')) if r['role']=='auditor'];self.assertEqual(len(rows),n);self.assertTrue(all(not r['human_reviewed'] for r in rows))
  self.assertEqual(s.read(s.ROOT/'benchmark/first_tuning_review_cohort_v2/readiness.json')['status'],'FIRST_TUNING_EXPERIMENT_REVIEW_PENDING')
 def test_r06_actual_population_invariant(self):
  s.sys.path.insert(0,str(s.ROOT/'benchmark/machine_adjudication_v1'));import r06
  pop=s.read(s.ROOT/'benchmark/machine_adjudication_v1/post_freeze/r06_population.json')['eligible_evaluation_metadata'];self.assertEqual(len(pop),114)
  self.assertFalse(any(r['split']=='train' for r in pop));scores=[dict(example_id=r['example_id'],accepted_outcome=True) for r in pop]
  train=[dict(example_id='injected-'+str(i),split='train',document_family='injected') for i in range(32)]
  first=r06.family_metric(scores,pop,[r['example_id'] for r in pop]);second=r06.family_metric(scores+[dict(example_id=r['example_id'],accepted_outcome=False) for r in train],pop+train,[r['example_id'] for r in pop+train])
  self.assertEqual(first,second)
