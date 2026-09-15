"""Completed curation audit; no promotion of invalid or quarantined labels."""
import unittest,tempfile
from pathlib import Path
from datetime import datetime
from collections import Counter
import semantics as s
s.sys.path.insert(0,str(s.HERE))
import review_flow as f
import population as pop
import regression_phase_guard as phase
B=s.HERE/'blind_evidence';P=s.HERE/'post_freeze';A=s.HERE/'machine_adjudicated_producer_candidates_v2'

class Completed(unittest.TestCase):
 def test_method_population_label_chronology(self):
  method=f.policy_intact();freeze=f.verify_freeze();opened=s.read(P/'GOLD_COMPARISON_STARTED.json')
  self.assertLess(datetime.fromisoformat(method['frozen_at']),datetime.fromisoformat(freeze['frozen_at']))
  self.assertLess(datetime.fromisoformat(freeze['frozen_at']),datetime.fromisoformat(opened['started_at']))
  self.assertEqual(opened['pre_gold_commit'],'3f5d4f4520e85db40b42a5c075a7166cd349bd7a')
  self.assertTrue(phase.require_label_commit(opened['pre_gold_commit']))
 def test_exact_substantive_population_and_hard_selection(self):
  rows,inputs=pop.inventory();frozen=s.read(s.HERE/'population.json')
  self.assertEqual(Counter(r['split'] for r in rows),dict(train=32,dev=32));self.assertTrue(all(s.eligible_metadata(r) for r in rows))
  self.assertEqual({r['example_id'] for r in rows},{r['example_id'] for r in frozen['rows']})
  self.assertEqual(frozen['reserve_count'],0);self.assertEqual(len(frozen['templates']),8)
  by={r['packet_id']:r['example_id'] for r in frozen['rows']}
  self.assertEqual(set(pop.hard_audit(rows)),{by[pid] for pid in frozen['hard_packet_ids']})
  for n,h in frozen['packet_hashes'].items():self.assertEqual(s.digest((s.HERE/'inputs'/n).read_bytes()),h)
  before=s.digest((s.HERE/'population.json').read_bytes())
  with self.assertRaises(ValueError):pop.main()
  self.assertEqual(before,s.digest((s.HERE/'population.json').read_bytes()))
 def test_all_primary_slots_and_recomputed_validation(self):
  packets=f.packets();cons=s.read(B/'consensus.json');valid_count=0
  for slot in 'ABC':
   paths=list((B/slot/'reviews').glob('*.json'));self.assertEqual(len(paths),64);self.assertEqual({p.stem for p in paths},set(packets))
   self.assertFalse(list((B/slot/'repairs').glob('*.json')))
   for path in paths:
    self.assertEqual(s.digest(path.read_bytes()),s.read(B/slot/'PRIMARY_HASHES.json')[path.name])
    try:f.validate(s.read(path),packets[path.stem],slot);valid=True
    except ValueError:valid=False
    self.assertEqual(valid,cons[path.stem]['primary_valid'][slot]);valid_count+=valid
  self.assertEqual(valid_count,180)
 def test_actual_consensus(self):
  cons=s.read(B/'consensus.json')
  for pid,c in cons.items():
   actual=f.consensus([s.read(B/slot/'reviews'/(pid+'.json')) for slot in 'ABC'])
   for k,v in actual.items():self.assertEqual(c[k],v)
  self.assertEqual(Counter(c['state'] for c in cons.values()),{'unanimous':64})
 def test_all_required_adjudications_preserve_invalid_results(self):
  cons=s.read(B/'consensus.json');dis=s.read(B/'disagreements.json');av=s.read(B/'adjudication_validation.json');packets=f.packets()
  required=set(dis['hard'])|{pid for pid,c in cons.items() if c['state']=='no_majority' or not all(c['primary_valid'].values())}
  self.assertEqual(set(av),required);self.assertEqual(len(av),19);self.assertEqual(len(dis['hard']),16)
  self.assertEqual(sum(v['valid'] for v in av.values()),15)
  for pid in required:
   v=s.read(B/'adjudications'/(pid+'.json'))
   try:f.validate(v,packets[pid],'D');valid=True
   except ValueError:valid=False
   self.assertEqual(valid,av[pid]['valid']);self.assertFalse(v['label']['review_ambiguity'])
   self.assertEqual(s.material(v['label']),s.material(s.read(B/'A/reviews'/(pid+'.json'))['label']))
 def test_canonical_targets_and_exact_support(self):
  labels=s.read(B/'labels.json');targets=s.read(B/'canonical_targets.json');packets=f.packets()
  for pid,e in labels.items():
   self.assertEqual(s.render(e['review']['label']),targets[pid])
   for i in e['review']['label']['items']:
    text=next(v['text'] for v in packets[pid]['input']['source_spans'] if v['alias']==i['span'])
    for a in i['gap_atoms']+i['uncertainty_atoms']:self.assertTrue(s.ground(a,text,i['refs']))
   if e['valid']:self.assertEqual(s.validate_label(e['review']['label'],packets[pid]['input']),targets[pid])
 def test_curation_only_every_primary_and_adjudication(self):
  paths=[p for slot in 'ABC' for p in (B/slot/'reviews').glob('*.json')]+list((B/'adjudications').glob('*.json'))
  for p in paths:
   v=s.read(p);self.assertEqual(v['use'],'curation_only');self.assertEqual(v['evidence_kind'],'training_label_curation_evidence')
  summary=s.read(P/'summary.json');self.assertFalse(summary['independent_generalization_evidence']);self.assertFalse(summary['blind_final_evaluation'])
 def test_governance_failure_not_hidden(self):
  audit=s.read(s.HERE/'PRE_GOLD_ACCESS_AUDIT.json');self.assertFalse(audit['governance_pass']);self.assertFalse(audit['strict_target_access_order_pass'])
  self.assertFalse(audit['reviewer_target_exposure_detected'])
  self.assertEqual(audit,s.read(B/'PRE_GOLD_ACCESS_AUDIT.json'))
  for e in s.read(P/'excluded_candidates.json'):self.assertIn('pre_gold_access_governance_failure',e['reasons'])
 def test_eligible_namespace_empty_and_separate(self):
  self.assertEqual({p.name for p in A.iterdir()},{'train.json','dev.json','manifest.json'})
  for split in ('train','dev'):self.assertEqual(s.read(A/(split+'.json')),[])
  manifest=s.read(A/'manifest.json');self.assertFalse(manifest['training_authorized']);self.assertFalse(manifest['human_reviewed'])
  for n,h in manifest['files'].items():self.assertEqual(s.digest((A/n).read_bytes()),h)
 def test_quarantine_supported_but_not_training(self):
  rows=s.read(P/'quarantined_semantically_qualified_labels.json');labels=s.read(B/'labels.json');meta={r['example_id']:r for r in s.read(s.HERE/'population.json')['rows']}
  self.assertEqual(Counter(r['split'] for r in rows),dict(train=32,dev=28))
  for r in rows:
   self.assertTrue(s.eligible_metadata(meta[r['example_id']]));self.assertTrue(all(labels[r['packet_id']]['primary_valid'].values()))
   self.assertFalse(r['training_authorized']);self.assertEqual(r['provenance'],'quarantined_producer_label_v2');self.assertEqual(r['use'],'curation_only')
 def test_post_freeze_diagnostic_counts(self):
  values=s.read(P/'legacy_comparison.json');summary=s.read(P/'summary.json')['legacy']
  self.assertEqual(sum(not v['material_dispute_resolved'] for v in values.values()),summary['unresolved'])
  self.assertEqual(Counter(v['classification'] for v in values.values()),dict(semantic_agreement=58,legacy_authored_target_under_specification=5,unresolved=1))
 def test_all_history_and_acceptance_immutable(self):
  for name in ('machine_adjudication_v1','machine_adjudication_v2','producer_coverage_amendment_v1'):
   root=s.ROOT/'benchmark'/name
   for n,h in s.read(root/'release_freeze.json')['hashes'].items():self.assertEqual(s.digest((root/n).read_bytes()),h)
  self.assertEqual(s.digest((s.ROOT/'benchmark/first_tuning_experiment_v1/acceptance_registration.json').read_bytes()),'8b70b096b128183707b2cc77c7577efebc8a5232336316a498f133306e3495da')
 def test_auditors_and_humans_unchanged(self):
  root=s.ROOT/'benchmark/machine_adjudication_v2/machine_adjudicated_training_access_v2'
  for split,n in [('train',46),('dev',24)]:self.assertEqual(sum(r['role']=='auditor' for r in s.read(root/(split+'.json'))),n)
  self.assertEqual(s.read(s.ROOT/'benchmark/first_tuning_review_cohort_v2/readiness.json')['status'],'FIRST_TUNING_EXPERIMENT_REVIEW_PENDING')
 def test_regression_phase_guard_before_authored_access(self):
  with tempfile.TemporaryDirectory(dir=s.ROOT/'output') as d:
   with self.assertRaisesRegex(ValueError,'Label freeze required'):phase.require_label_commit('0'*40,Path(d),lambda ref:self.fail('Git/data read before missing-freeze guard'))
 def test_real_r06_population_train_injection(self):
  s.sys.path.insert(0,str(s.ROOT/'benchmark/machine_adjudication_v1'));import r06
  pop=s.read(s.ROOT/'benchmark/machine_adjudication_v1/post_freeze/r06_population.json')['eligible_evaluation_metadata'];self.assertEqual(len(pop),114)
  scores=[dict(example_id=r['example_id'],accepted_outcome=True) for r in pop]
  train=[dict(example_id='injected-'+str(i),split='train',document_family='injected') for i in range(32)]
  self.assertEqual(r06.family_metric(scores,pop,[r['example_id'] for r in pop]),r06.family_metric(scores+[dict(example_id=r['example_id'],accepted_outcome=False) for r in train],pop+train,[r['example_id'] for r in pop+train]))
