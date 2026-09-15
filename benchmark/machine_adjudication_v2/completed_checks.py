"""Executed checks of frozen V2 evidence and separate candidate access."""
from collections import Counter
from datetime import datetime
from copy import deepcopy
import unittest
import review as m
m.sys.path.insert(0,str(m.HERE))
import pipeline

B=m.HERE/'blind_evidence'
P=m.HERE/'post_freeze'
A=m.HERE/'machine_adjudicated_training_access_v2'

class CompletedChecks(unittest.TestCase):
    def test_comparison_uses_review_pipeline_without_model_imports(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('v2_compare_guard',m.HERE/'compare.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(m.HERE/'pipeline.py',m.Path(module.pipeline.__file__))
        self.assertFalse({'torch','transformers','openai','anthropic'} & set(m.sys.modules))

    def test_primary_coverage_validity_and_immutability(self):
        packets=m.packets()
        self.assertEqual(len(packets),192)
        for slot in 'ABC':
            paths=list((B/slot/'reviews').glob('*.json'))
            self.assertEqual({p.stem for p in paths},set(packets))
            self.assertFalse(list((B/slot/'repairs').glob('*.json')))
            hashes=m.read(B/slot/'PRIMARY_HASHES.json')
            for p in paths:
                self.assertEqual(m.sha(p.read_bytes()),hashes[p.name])
                m.validate(m.read(p),packets[p.stem],slot)

    def test_consensus_recomputed_from_frozen_primaries(self):
        packets=m.packets();cons=m.read(B/'consensus.json')
        for ident,packet in packets.items():
            result=m.consensus([m.read(B/s/'reviews'/(ident+'.json')) for s in 'ABC'],packet['input']['role'])
            for k,v in result.items():self.assertEqual(cons[ident][k],v)
        self.assertEqual(Counter(v['state'] for v in cons.values()),dict(unanimous=154,majority=29,no_majority=9))

    def test_adjudication_union_and_decision_consistency(self):
        cons=m.read(B/'consensus.json');dis=m.read(B/'disagreements.json');packets=m.packets()
        required=set(dis['designated_hard'])|{i for i,c in cons.items() if c['state']=='no_majority' or not all(c['primary_valid'].values())}
        self.assertEqual(required,set(dis['required_adjudication']))
        self.assertEqual(required,{p.stem for p in (B/'adjudications').glob('*.json')})
        self.assertEqual(len(dis['designated_hard']),48)
        for ident in required:
            v=m.read(B/'adjudications'/(ident+'.json'));m.validate(v,packets[ident],'D')
            if v['decision'].startswith('candidate_'):
                selected=m.read(B/v['decision'][-1]/'reviews'/(ident+'.json'))
                self.assertEqual(m.material(v,packets[ident]['input']['role']),m.material(selected,packets[ident]['input']['role']))
            self.assertEqual(v['decision']=='unresolved',v['review_ambiguity'])

    def test_final_labels_valid_and_bound(self):
        packets=m.packets();labels=m.read(B/'labels.json');cons=m.read(B/'consensus.json')
        self.assertEqual(set(labels),set(packets))
        for ident,label in labels.items():
            v=label['review'];m.validate(v,packets[ident],v['slot'])
            path=B/'adjudications'/(ident+'.json') if label['provenance']=='machine_agent_adjudication' else B/cons[ident]['selected_slot']/'reviews'/(ident+'.json')
            self.assertEqual(v,m.read(path));self.assertFalse(label['human_reviewed']);self.assertTrue(label['valid'])

    def test_freezes_and_order(self):
        freeze=pipeline.verify_freeze();opened=m.read(P/'GOLD_COMPARISON_STARTED.json')
        self.assertLess(datetime.fromisoformat(freeze['frozen_at']),datetime.fromisoformat(opened['started_at']))
        self.assertEqual(opened['freeze_sha256'],m.sha((B/'PRE_GOLD_FREEZE.json').read_bytes()))
        self.assertEqual(opened['pre_gold_commit'],'b22c8566a16e0930a3ccb8cf941e3b0fc689cb8d')
        for name in ('PRE_REVIEW_METHOD_FREEZE.json','PRE_GOLD_PROJECTION_FREEZE.json'):
            for rel,h in m.read(m.HERE/name)['hashes'].items():self.assertEqual(m.sha((m.HERE/rel).read_bytes()),h)

    def test_candidate_namespace_and_provenance(self):
        self.assertEqual({p.name for p in A.iterdir()},{'train.json','dev.json','manifest.json'})
        manifest=m.read(A/'manifest.json');rows=m.read(A/'train.json')+m.read(A/'dev.json')
        for n,h in manifest['files'].items():self.assertEqual(m.sha((A/n).read_bytes()),h)
        self.assertEqual(set(manifest['allowed_ids']),{r['example_id'] for r in rows})
        self.assertEqual(len(rows),len(set(manifest['allowed_ids'])))
        self.assertFalse(manifest['training_authorized'])
        for r in rows:
            self.assertFalse(r['human_reviewed']);self.assertEqual(r['provenance'],'machine_adjudicated_training_candidate')
            label=m.read(B/'labels.json')[r['packet_id']]
            self.assertEqual(r['semantic_target'],label['review']['semantic_target'])

    def test_evaluation_exclusion_and_coverage(self):
        refs=m.read(P/'evaluation_reference.json');allowed=m.read(A/'manifest.json')['allowed_ids']
        self.assertEqual(len(refs),74);self.assertEqual(sum(r['held_out'] for r in refs),72)
        self.assertFalse(set(allowed)&{r['example_id'] for r in refs})
        self.assertTrue(all(r['label']['valid'] and all(r['label']['primary_valid'].values()) for r in refs))

    def test_eligibility_and_source_uncertainty_separation(self):
        labels=m.read(B/'labels.json');comp=m.read(P/'authored_comparison.json')
        rows=m.read(A/'train.json')+m.read(A/'dev.json')
        self.assertTrue(any(r['source_uncertainty_present'] for r in rows))
        for r in rows:
            label=labels[r['packet_id']]
            self.assertTrue(all(label['primary_valid'].values()));self.assertFalse(label['review_ambiguity'])
            self.assertEqual(comp[r['packet_id']]['status'],'TYPED_SEMANTIC_AGREEMENT')
        excluded=m.read(P/'excluded_candidates.json')
        self.assertEqual(len(excluded),36);self.assertTrue(all(r['semantic_dispute'] for r in excluded))

    def test_evidence_negative_behavior_on_real_packets(self):
        packets=m.packets()
        for role in ('producer','auditor'):
            ident=next(i for i,p in packets.items() if p['input']['role']==role and m.read(B/'A/reviews'/(i+'.json'))['semantic_target']['items'])
            v=deepcopy(m.read(B/'A/reviews'/(ident+'.json')))
            item=v['semantic_target']['items'][0];key='refs' if role=='producer' else 'ref_ids'
            item[key]=['REF-99999999']
            with self.assertRaises(ValueError):m.validate(v,packets[ident],'A')

    def test_v1_release_and_acceptance_unchanged(self):
        v1=m.ROOT/'benchmark/machine_adjudication_v1'
        for n,h in m.read(v1/'release_freeze.json')['hashes'].items():self.assertEqual(m.sha((v1/n).read_bytes()),h)
        self.assertEqual(m.sha((m.ROOT/'benchmark/first_tuning_experiment_v1/acceptance_registration.json').read_bytes()),'8b70b096b128183707b2cc77c7577efebc8a5232336316a498f133306e3495da')

    def test_human_status_remains_pending(self):
        s=m.read(P/'summary.json')
        self.assertEqual([s[k] for k in ('human_first_reviews','human_second_reviews','human_adjudications')],[0,0,0])
        self.assertEqual(m.read(m.ROOT/'benchmark/first_tuning_review_cohort_v2/readiness.json')['status'],'FIRST_TUNING_EXPERIMENT_REVIEW_PENDING')

    def test_r06_registered_population_preserved(self):
        import r06
        pop=m.read(m.ROOT/'benchmark/machine_adjudication_v1/post_freeze/r06_population.json')['eligible_evaluation_metadata']
        self.assertEqual(len(pop),114);self.assertFalse(any(r['split']=='train' for r in pop))
        scores=[dict(example_id=r['example_id'],accepted_outcome=True) for r in pop]
        train=[dict(example_id='synthetic-train-'+str(i),split='train',document_family='injected') for i in range(10)]
        before=r06.family_metric(scores,pop,[r['example_id'] for r in pop])
        after=r06.family_metric(scores+[dict(example_id=r['example_id'],accepted_outcome=False) for r in train],pop+train,[r['example_id'] for r in pop+train])
        self.assertEqual(before,after)
