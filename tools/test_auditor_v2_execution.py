"""Exact binding and metric tests; never train a model or head."""
import copy
import unittest
from pathlib import Path
import auditor_v2_execution as c


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d=Path(__file__).resolve().parents[1]/'tuning/auditor_v2_diagnostic'
        cls.records=c.read(d/'records.json');cls.spec=c.read(d/'experiment.json')
        cls.challenges=c.read(d/'challenges.json');cls.baseline=c.read(d/'baseline.json')

    def test_exact_scope(self):
        c.validate(self.records,self.spec,self.challenges,self.baseline)

    def test_metadata_and_count_rejected(self):
        for mutate in ['metadata','count','split','label']:
            records=copy.deepcopy(self.records)
            if mutate=='metadata':records[0]['dataset']='untrusted'
            if mutate=='count':records.pop()
            if mutate=='split':records[-1]['split']='train'
            if mutate=='label':records[0]['relation']='INSUFFICIENT_EVIDENCE'
            with self.assertRaises(AssertionError):c.validate(records,self.spec,self.challenges,self.baseline)

    def test_hyperparameter_change_rejected(self):
        spec=copy.deepcopy(self.spec);spec['head']['updates']=201
        with self.assertRaises(AssertionError):c.validate(self.records,spec,self.challenges,self.baseline)

    def test_perfect_results_and_precision(self):
        pred={r['example_id']:r['relation'] for r in self.records[1792:]}
        result=c.evaluate(self.records,pred,self.challenges,self.baseline)
        self.assertEqual(result['verdict'],'AUDITOR_V2_DIAGNOSTIC_PASS')
        self.assertEqual(result['external']['macro_precision'],1.)
        pred[self.records[-1]['example_id']]='MATCH'
        result=c.evaluate(self.records,pred,self.challenges,self.baseline)
        self.assertLess(result['historical']['macro_f1'],1.)


if __name__=='__main__':unittest.main()
