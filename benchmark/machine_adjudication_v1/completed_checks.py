"""Verify completed machine evidence without treating failed judgments as passes."""
from collections import Counter
from datetime import datetime
from copy import deepcopy
import unittest
from unittest.mock import patch
import review as m
import checkpoint_metrics as adapter
import r06


class CompletedChecks(unittest.TestCase):
    def test_576_unique_primaries_and_bounded_repairs(self):
        base=m.HERE/'blind_evidence'
        for slot in 'ABC':
            self.assertEqual(len(list((base/slot/'reviews').glob('*.json'))),192)
            self.assertEqual(len(list((base/slot/'repairs').glob('*.json'))),84)
            for p in (base/slot/'repairs').glob('*.json'):
                original=m.read(base/slot/'reviews'/p.name);repaired=m.read(p)
                self.assertEqual(repaired['original_sha256'],m.sha((base/slot/'reviews'/p.name).read_bytes()))
                self.assertEqual(repaired['repair_attempt'],1)
                self.assertEqual({k:v for k,v in repaired.items() if k not in ('original_sha256','repair_kind','repair_attempt','semantic_judgment')},
                                 {k:v for k,v in original.items() if k!='semantic_judgment'})

    def test_all_required_and_hard_adjudications_completed(self):
        dis=m.read(m.HERE/'blind_evidence/disagreements.json')
        actual={p.stem for p in (m.HERE/'blind_evidence/adjudications').glob('*.json')}
        self.assertEqual(actual,set(dis['required_adjudication']));self.assertEqual(len(actual),87)
        self.assertEqual(len(dis['designated_hard']),48);self.assertTrue(set(dis['designated_hard'])<=actual)
        packets=m.packets()
        for ident in actual:self.assertTrue(m.validate(m.read(m.HERE/'blind_evidence/adjudications'/(ident+'.json')),packets[ident],'D'))

    def test_freeze_before_actual_gold_opening(self):
        freeze=m.verify_pre_gold(m.HERE/'blind_evidence/PRE_GOLD_FREEZE.json')
        opened=m.read(m.HERE/'post_freeze/GOLD_COMPARISON_STARTED.json')
        self.assertLess(datetime.fromisoformat(freeze['frozen_at']),datetime.fromisoformat(opened['started_at']))
        self.assertEqual(opened['pre_gold_manifest_sha256'],m.sha((m.HERE/'blind_evidence/PRE_GOLD_FREEZE.json').read_bytes()))
        self.assertEqual(opened['pre_gold_commit'],'d151ae7a8b54e380cb528eefbc286be2a3ea93d9')

    def test_machine_human_namespaces_separate(self):
        status=m.read(m.HERE/'post_freeze/readiness.json')
        self.assertEqual(status['human_first_reviews'],0);self.assertEqual(status['human_second_reviews'],0);self.assertEqual(status['human_adjudications'],0)
        self.assertFalse(status['training_authorized']);self.assertFalse(status['final_model_acceptance_ready'])
        self.assertEqual(m.read(m.ROOT/'benchmark/first_tuning_review_cohort_v2/readiness.json')['status'],'FIRST_TUNING_EXPERIMENT_REVIEW_PENDING')
        for slot in 'ABC':
            for p in (m.HERE/'blind_evidence'/slot/'reviews').glob('*.json'):m.machine_provenance(m.read(p))

    def test_training_namespace_has_only_allowed_files(self):
        access=m.HERE/'machine_adjudicated_training_access'
        self.assertEqual({p.name for p in access.iterdir()},{'train.json','dev.json','manifest.json'})
        manifest=m.read(access/'manifest.json')
        for name,expected in manifest['files'].items():self.assertEqual(m.sha((access/name).read_bytes()),expected)
        records=m.read(access/'train.json')+m.read(access/'dev.json')
        self.assertEqual(len(records),39);self.assertEqual(len({r['example_id'] for r in records}),39)
        self.assertEqual(set(manifest['allowed_ids']),{r['example_id'] for r in records})
        self.assertTrue(all(r['provenance']=='machine_adjudicated_training_candidate' and r['human_reviewed'] is False for r in records))

    def test_74_evaluation_labels_excluded(self):
        reference=m.read(m.HERE/'post_freeze/held_out_machine_reference.json')
        self.assertEqual(len(reference),74);self.assertEqual(sum(r['held_out_domain'] for r in reference),72)
        candidates=m.read(m.HERE/'machine_adjudicated_training_access/manifest.json')['allowed_ids']
        self.assertFalse(set(candidates)&{r['example_id'] for r in reference})

    def test_invalid_disputed_ambiguous_never_training(self):
        labels=m.read(m.HERE/'blind_evidence/consensus_labels.json');comp=m.read(m.HERE/'post_freeze/authored_comparison.json')
        candidates=m.read(m.HERE/'machine_adjudicated_training_access/train.json')+m.read(m.HERE/'machine_adjudicated_training_access/dev.json')
        for row in candidates:
            value=labels[row['packet_id']]
            self.assertTrue(value['valid']);self.assertTrue(all(value['primary_valid'].values()))
            self.assertFalse(value['unresolved']);self.assertFalse(value['review']['ambiguity'])
            self.assertEqual(comp[row['packet_id']]['status'],'STRUCTURED_AUTHORED_AGREEMENT')

    def test_invalid_primaries_remain_a_readiness_blocker(self):
        labels=m.read(m.HERE/'blind_evidence/consensus_labels.json')
        self.assertEqual(sum(sum(not x for x in v['primary_valid'].values()) for v in labels.values()),35)
        status=m.read(m.HERE/'post_freeze/readiness.json')
        self.assertEqual(status['valid_effective_primary'],541)
        self.assertEqual(status['machine_status'],'AGENT_ADJUDICATED_TUNING_EXPERIMENT_NOT_READY')

    def test_no_invented_refs_rules_in_accepted_labels(self):
        labels=m.read(m.HERE/'blind_evidence/consensus_labels.json');packets=m.packets()
        for ident,label in labels.items():
            if label['valid']:self.assertTrue(m.validate(label['review'],packets[ident]))

    def test_actual_r06_population(self):
        pop=m.read(m.HERE/'post_freeze/r06_population.json')['eligible_evaluation_metadata']
        self.assertEqual(len(pop),114);self.assertFalse(any(r['split']=='train' for r in pop))
        self.assertEqual(Counter(r['split'] for r in pop),{'dev':40,'test':37,'sealed_adversarial':37})
        result=r06.family_metric([],pop,[r['example_id'] for r in pop])
        self.assertEqual(sum(v['status']=='INSUFFICIENT_MEASUREMENT' for v in result['families'].values()),12)
        self.assertEqual(sum(v['status']=='insufficient_sample_for_family_gate' for v in result['families'].values()),22)
        self.assertIsNone(result['passed'])

    def test_adapter_replaces_legacy_population_without_human_promotion(self):
        rows=[dict(example_id=f'e{i}',split='dev',document_family='evaluation') for i in range(4)]
        rows+=[dict(example_id='t',split='train',document_family='training')]
        scores=[dict(example_id=r['example_id'],accepted_outcome=r['split']!='train') for r in rows]
        coverage=dict(status='FIRST_TUNING_EXPERIMENT_REVIEW_PENDING',accepted_targets={r['example_id']:None for r in rows})
        stub=dict(criteria={'R06':dict(measured=0,passed=False),'R01':dict(measured=0,passed=False)},families={},measurement_complete=True,R07=dict(passed=True))
        with patch.object(adapter.legacy,'evaluate_thresholds',return_value=deepcopy(stub)) as legacy:
            result=adapter.evaluate(scores,rows,coverage)
            self.assertEqual(len(legacy.call_args.args[0]),4)
        self.assertEqual(result['criteria']['R06']['measured'],1.0)
        self.assertFalse(result['criteria']['R01']['passed']);self.assertFalse(result['promising_checkpoint'])


if __name__=='__main__':unittest.main()
