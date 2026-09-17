"""Deterministic local contracts and invalid fixtures; no model training."""
import ast
import copy
from pathlib import Path
import unittest
import auditor_classifier_lora_core as c

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'tuning/auditor_classifier_lora'


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records=c.read(D/'records.json');cls.spec=c.read(D/'experiment.json');cls.ch=c.read(D/'challenges.json');cls.plan=c.read(D/'schedule.json')

    def test_exact_scope_and_two_passes(self):
        c.validate(self.records,self.spec,self.ch,self.plan)
        wanted={r['example_id'] for r in self.records[:1792]}
        for batches in [self.plan[:448],self.plan[448:]]:
            ids=[i for b in batches for i in b['example_ids']]
            self.assertEqual(len(ids),1792);self.assertEqual(set(ids),wanted)
        self.assertEqual([b['step'] for b in self.plan],[*range(1,897)])

    def test_invalid_binding_schedule_and_hparams(self):
        for kind in ['metadata','dev_gradient','rank','normalization','adapter','missing_dev','checkpoint']:
            rows=copy.deepcopy(self.records);spec=copy.deepcopy(self.spec);plan=copy.deepcopy(self.plan)
            if kind=='metadata':rows[0]['provenance']='forbidden'
            elif kind=='dev_gradient':plan[0]['example_ids'][0]=rows[-1]['example_id']
            elif kind=='rank':spec['lora']['r']=16
            elif kind=='normalization':spec['normalization']='dev_fit'
            elif kind=='adapter':spec['historical_adapter_loaded']=True
            elif kind=='missing_dev':rows.pop()
            else:spec['training']['checkpoints']=[400,896]
            with self.assertRaises(AssertionError):c.validate(rows,spec,self.ch,plan)

    def test_trainable_inventory(self):
        entries=[]
        for layer in range(32):
            for target in c.TARGETS:
                inn,out=(8192,3072) if target=='down_proj' else (3072,8192) if target in ['gate_proj','up_proj'] else (3072,3072)
                for which,shape in [('A',[8,inn]),('B',[out,8])]:
                    entries.append(dict(name=f'base.model.layers.{layer}.{target}.lora_{which}.default.weight',shape=shape,numel=shape[0]*shape[1],dtype='torch.float32',trainable=True))
        entries += [dict(name='head.weight',shape=[4,3072],numel=12288,dtype='torch.float32',trainable=True),dict(name='head.bias',shape=[4],numel=4,dtype='torch.float32',trainable=True)]
        self.assertEqual(c.inventory(entries)['total'],14954500)
        bad=copy.deepcopy(entries);bad.append(dict(name='base.lm_head.weight',shape=[1],numel=1,dtype='torch.float32',trainable=True))
        with self.assertRaises(AssertionError):c.inventory(bad)
        with self.assertRaises(AssertionError):c.inventory(entries[:-1])

    def test_selection_requires_both_complete(self):
        pred={r['example_id']:r['relation'] for r in self.records[1792:]}
        metrics=c.evaluate(self.records,pred,self.ch)
        a=dict(step=448,metrics=metrics,complete=True,lora_sha256='a'*64,head_sha256='b'*64)
        b=dict(a,step=896,lora_sha256='c'*64)
        self.assertEqual(c.select([a],448)['verdict'],'AUDITOR_CLASSIFIER_LORA_INDETERMINATE')
        self.assertEqual(c.select([a,b],896)['selected']['step'],448)
        b=copy.deepcopy(b);b['metrics']['historical']['macro_f1']=.99
        self.assertEqual(c.select([a,b],896)['selected']['step'],448)
        a=copy.deepcopy(a);a['metrics']['passed']=False
        self.assertEqual(c.select([a,b],896)['selected']['step'],896)
        b['metrics']['passed']=False
        self.assertIsNone(c.select([a,b],896)['selected'])

    def test_coprimary_and_challenge_metrics(self):
        pred={r['example_id']:r['relation'] for r in self.records[1792:]}
        for row in self.records[1992:]:pred[row['example_id']]=c.CLASSES[(c.CLASSES.index(row['relation'])+1)%4]
        m=c.evaluate(self.records,pred,self.ch)
        self.assertTrue(m['gates']['external']);self.assertFalse(m['passed'])
        self.assertEqual(c.metrics(c.CLASSES[:3],['ADDITION']*3,c.CLASSES[:3])['macro_f1'],0.)
        pred['unbound']='MATCH'
        with self.assertRaises(AssertionError):c.evaluate(self.records,pred,self.ch)

    def test_no_generation_or_old_adapter_loading_call(self):
        tree=ast.parse((ROOT/'tools/auditor_classifier_lora_remote.py').read_text())
        names=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertNotIn('generate',names);self.assertNotIn('load_adapter',names)
        self.assertNotIn('PeftModel',(ROOT/'tools/auditor_classifier_lora_remote.py').read_text())

    def test_budget_projection(self):
        self.assertGreater(c.remaining_seconds(0,[],496),c.remaining_seconds(448,[4.]*10,248))
        self.assertEqual(c.remaining_seconds(896,[4.],0),180)


if __name__=='__main__':unittest.main()
