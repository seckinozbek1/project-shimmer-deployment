"""Prospective semantic fixtures; no authored benchmark targets consulted."""
from copy import deepcopy
import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import atoms as a
import review as r
sys=r.sys
sys.path.insert(0,str(r.ROOT/'benchmark/machine_adjudication_v1'));import r06


class NormalizerChecks(unittest.TestCase):
    def test_missing_date_paraphrases(self):
        text='The reporting date is unavailable.'
        values=[a.wording_to_atoms(s,text,'s0',[],'gap') for s in ['Reporting date is unavailable.','What is the reporting date?','Date of report is not provided.']]
        self.assertTrue(all(a.material([v])==a.material(values[:1]) for v in values))

    def test_unavailability_synonyms(self):
        x=a.make('missing_information','reporting date','s0',wording='unavailable')
        y=a.make('missing_information','date of report','s0',wording='not provided')
        self.assertEqual(a.material([x]),a.material([y]))

    def test_uncertainty_synonyms(self):
        text='The interpretation remains uncertain.'
        x=a.wording_to_atoms('interpretation uncertain',text,'s0',[],'uncertainty')
        y=a.wording_to_atoms('interpretation unresolved',text,'s0',[],'uncertainty')
        self.assertEqual(a.material([x]),a.material([y]))

    def test_real_semantic_differences_preserved(self):
        base=a.make('missing_information','recording_date','s0')
        for k,v in [('type','unknown'),('target','quantity'),('subject','different_record'),('unit','kg'),('type','conflicting'),('span','s1'),('refs',['REF-0001'])]:
            changed=dict(base,**{k:v});self.assertNotEqual(a.material([base]),a.material([changed]),k)
        self.assertNotEqual(a.material([base]),a.material([]))
        self.assertNotEqual(a.material([]),a.material([a.make('unknown','interpretation','s0')]))

    def test_unsupported_paraphrases_and_inference_rejected(self):
        with self.assertRaises(ValueError):a.wording_to_atoms('some mystery','The date is absent.','s0',[],'gap')
        with self.assertRaises(ValueError):a.normalize(dict(a.make('unknown','interpretation','s0'),origin='reviewer_inferred'))
        with self.assertRaises(ValueError):a.ground(a.make('unknown','interpretation','s0'),'A clear statement.','s0',[])

    def test_gap_normalization_effect(self):
        x=a.make('missing_information','reporting date','s0');y=a.make('missing_information','date of report','s0')
        def invariant():self.assertEqual(a.material([x]),a.material([y]))
        with patch.object(a,'TARGET_ALIASES',{}):
            with self.assertRaises(AssertionError):invariant()
        invariant()

    def test_uncertainty_normalization_effect(self):
        x=a.make('unknown','interpretation','s0',wording='uncertain');y=dict(x,wording='unresolved')
        original=a.normalize
        def bad(v):return dict(original(v),wording=v.get('wording'))
        def invariant():self.assertEqual(a.material([x]),a.material([y]))
        with patch.object(a,'normalize',side_effect=bad):
            with self.assertRaises(AssertionError):invariant()
        invariant()

    def test_evidence_validation_effect(self):
        value=a.make('missing_information','recording_date','s0',refs=['REF-0002'])
        def invariant():
            with self.assertRaises(ValueError):a.ground(value,'The date is absent.','s0',['REF-0001'])
        with patch.object(a,'ground',return_value=True):
            with self.assertRaises(AssertionError):invariant()
        invariant()

    def test_review_ambiguity_separation_effect(self):
        row=dict(split='train',domain='catalogue');label=dict(valid=True,review=dict(source_uncertainty_present=True,review_ambiguity=False))
        def invariant():self.assertTrue(r.candidate(row,label,dict(A=True,B=True,C=True),False))
        with patch.object(r,'candidate',return_value=False):
            with self.assertRaises(AssertionError):invariant()
        invariant();label['review']['review_ambiguity']=True
        self.assertFalse(r.candidate(row,label,dict(A=True,B=True,C=True),False))

    def test_gold_isolation_effect(self):
        with tempfile.TemporaryDirectory() as f:
            p=Path(f);(p/'packets').mkdir();(p/'authored_gold.json').write_text('{}')
            def invariant():
                with self.assertRaises(ValueError):r.verify_isolation(p,{})
            with patch.object(r,'verify_isolation',return_value=None):
                with self.assertRaises(AssertionError):invariant()
            invariant()

    def test_held_out_exclusion_effect(self):
        row=dict(split='train',domain='astronomy');label=dict(valid=True,review=dict(review_ambiguity=False))
        def invariant():self.assertFalse(r.candidate(row,label,dict(A=True,B=True,C=True),False))
        with patch.object(r,'candidate',return_value=True):
            with self.assertRaises(AssertionError):invariant()
        invariant()

    def test_preserved_r06_train_exclusion_effect(self):
        rows=[dict(example_id=str(i),split='test',document_family='x') for i in range(4)]+[dict(example_id='t'+str(i),split='train',document_family='y') for i in range(4)]
        scores=[dict(example_id=x['example_id'],accepted_outcome=x['split']=='test') for x in rows]
        def invariant():self.assertEqual(r06.family_metric(scores,rows,[x['example_id'] for x in rows])['measured'],1)
        with patch.object(r06,'non_train',return_value=True):
            with self.assertRaises(AssertionError):invariant()
        invariant()


if __name__=='__main__':unittest.main()
