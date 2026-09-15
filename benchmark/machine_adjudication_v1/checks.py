"""Deterministic controls independent of authored targets and actual reviews."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import review as m
import r06
import eligibility as e


class Controls(unittest.TestCase):
    def test_r06_population(self):
        rows=[dict(example_id=f'e{i}',split='test',document_family='evaluation') for i in range(4)]
        rows += [dict(example_id=f't{i}',split='train',document_family='training') for i in range(4)]
        scores=[dict(example_id=f'e{i}',accepted_outcome=True) for i in range(4)]
        base=r06.family_metric(scores,rows,[r['example_id'] for r in rows])
        self.assertEqual(base['measured'],1.0);self.assertEqual(base['population'],['e0','e1','e2','e3'])
        for accepted in (False,True):
            extra=[dict(example_id=f't{i}',accepted_outcome=accepted) for i in range(4)]
            self.assertEqual(r06.family_metric(scores+extra,rows,[r['example_id'] for r in rows]),base)

    def test_train_exclusion_effect(self):
        rows=[dict(example_id=f'e{i}',split='dev',document_family='development') for i in range(4)]
        rows += [dict(example_id=f't{i}',split='train',document_family='training') for i in range(4)]
        scores=[dict(example_id=r['example_id'],accepted_outcome=r['split']!='train') for r in rows]
        def invariant():self.assertEqual(r06.family_metric(scores,rows,[r['example_id'] for r in rows])['measured'],1.0)
        with patch.object(r06,'non_train',return_value=True):
            with self.assertRaises(AssertionError):invariant()
        invariant()

    def test_train_cannot_improve_worst_family(self):
        rows=[dict(example_id=f'e{i}',split='test',document_family='same') for i in range(4)]
        rows += [dict(example_id=f't{i}',split='train',document_family='same') for i in range(8)]
        scores=[dict(example_id=r['example_id'],accepted_outcome=r['split']=='train') for r in rows]
        result=r06.family_metric(scores,rows,[r['example_id'] for r in rows])
        self.assertEqual(result['measured'],0.0);self.assertFalse(result['passed'])

    def test_missing_outputs_and_sparse_families(self):
        rows=[dict(example_id=f'e{i}',split='test',document_family='x') for i in range(4)]
        result=r06.family_metric([],rows,[r['example_id'] for r in rows])
        self.assertFalse(result['measurement_complete']);self.assertIsNone(result['passed'])
        result=r06.family_metric([dict(example_id='e0',accepted_outcome=False)],rows,['e0'])
        self.assertEqual(result['families']['x']['status'],'insufficient_sample_for_family_gate')
        self.assertIsNone(result['passed'])

    def test_duplicate_and_foreign_eval_rejected(self):
        rows=[dict(example_id='e',split='dev',document_family='x')]
        with self.assertRaises(ValueError):r06.family_metric([dict(example_id='unknown',accepted_outcome=True)],rows,['e'])
        with self.assertRaises(ValueError):r06.family_metric([dict(example_id='e',accepted_outcome=True)]*2,rows,['e'])

    def test_machine_provenance_effect(self):
        value=dict(provenance='independent_machine_agent_review',human=True)
        def invariant():
            with self.assertRaises(ValueError):m.machine_provenance(value)
        with patch.object(m,'machine_provenance',return_value=None):
            with self.assertRaises(AssertionError):invariant()
        invariant()

    def test_held_out_training_effect(self):
        row=dict(split='train',domain='astronomy')
        label=dict(valid=True,unresolved=False,review=dict(ambiguity=False))
        def invariant():self.assertFalse(e.candidate(row,label,dict(A=True,B=True,C=True),False))
        with patch.object(e,'held_out',return_value=False):
            with self.assertRaises(AssertionError):invariant()
        invariant()

    def test_dispute_ambiguity_invalid_exclusion(self):
        row=dict(split='dev',domain='catalogue');label=dict(valid=True,unresolved=False,review=dict(ambiguity=False))
        self.assertTrue(e.candidate(row,label,dict(A=True,B=True,C=True),False))
        self.assertFalse(e.candidate(row,label,dict(A=True,B=True,C=True),True))
        self.assertFalse(e.candidate(row,label,dict(A=True,B=True,C=False),False))
        label['review']['ambiguity']=True
        self.assertFalse(e.candidate(row,label,dict(A=True,B=True,C=True),False))

    def test_material_agreement_is_not_rationale_similarity(self):
        a=dict(semantic_judgment='MATCH',ambiguity=False,reason_components=['preserved_claim'],semantic_target=dict(items=[dict(finding='MATCH',ref_ids=['REF-0001'],confidence='CONFIDENT',reasoning='same')]))
        b=deepcopy(a);b['semantic_target']['items'][0]['reasoning']='a completely different explanation'
        self.assertEqual(m.material(a,'auditor'),m.material(b,'auditor'))
        b['semantic_target']['items'][0]['ref_ids']=['REF-0002']
        self.assertNotEqual(m.material(a,'auditor'),m.material(b,'auditor'))

    def test_pre_gold_hash_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);m.write(root/'labels.json',{})
            m.write(root/'freeze.json',dict(phase='MACHINE_LABELS_FROZEN_BEFORE_GOLD',hashes={'labels.json':m.sha((root/'labels.json').read_bytes())}))
            m.verify_pre_gold(root/'freeze.json')
            m.write(root/'labels.json',{'changed':True})
            with self.assertRaises(ValueError):m.verify_pre_gold(root/'freeze.json')

    def test_gold_isolation_effect(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'packets').mkdir();(root/'reviews').mkdir()
            (root/'authored_gold.json').write_text('{}',encoding='utf-8')
            def invariant():
                with self.assertRaises(ValueError):m.verify_clean_workspace(root,{})
            with patch.object(m,'verify_clean_workspace',return_value=None):
                with self.assertRaises(AssertionError):invariant()
            invariant()


if __name__=='__main__':unittest.main()
