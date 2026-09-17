"""No model, no Torch, no optimization: cached arrays and synthetic callback fixtures."""
import ast
import copy
import math
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
import numpy as np
from safetensors.numpy import load_file
import auditor_classifier_lora_stable as s
import auditor_classifier_lora_core as c

ROOT=Path(__file__).resolve().parents[1];D=ROOT/'tuning/auditor_classifier_lora_stable'


def clean_micro(g,micro=1,ce=1.):
    g.begin(g.next_update,micro)
    for stage in s.PRE_STAGES:g.stage(stage,True)
    g.backward(ce,lambda:None)
    g.gradients(True,.1,.2,math.hypot(.1,.2))


def clean_update(g,ce=1.,events=None):
    events=[] if events is None else events
    for m in range(1,5):clean_micro(g,m,ce)
    g.step(lambda:events.append('grad'),lambda:events.append('clip'),lambda:events.append('clipped'),lambda:events.append('step'),lambda:events.append('parameters'),lambda:True)


class StableTests(unittest.TestCase):
    def gate(self):
        events=[];g=s.HealthGate(13.862943611198906,events.append);g.admit_initial(True);return g,events

    def test_01_artifact_bindings(self):
        for name,digest in c.read(D/'source_bindings.json').items():self.assertEqual(s.verify_bound(ROOT/name,digest),digest)

    def test_02_tampered_artifact_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'head';p.write_bytes(b'changed')
            with self.assertRaises(s.NumericalStop):s.verify_bound(p,'0'*64)

    def test_03_cached_parity_receipt(self):
        p=c.read(D/'parity.json');self.assertEqual(p['rows_checked'],2040)
        self.assertTrue(p['prediction_identity'] and p['all_saved_metrics_identical'])
        self.assertLess(p['max_error_vs_saved_dev_logits'],2e-4)
        self.assertFalse(p['future_fresh_representation_parity_proven'])

    def test_04_normalization_algebra(self):
        h=np.array([[1.,3.,9.],[4.,8.,2.]],np.float32);w=np.arange(12,dtype=np.float32).reshape(4,3)/10
        b=np.arange(4,dtype=np.float32);mean=np.array([2,4,6],np.float32);std=np.array([1,2,3],np.float32)
        z,actual=s.fp32_numpy(np,h,w,b,mean,std)
        folded=h@(w/std).T+(b-(w*(mean/std)).sum(axis=1))
        np.testing.assert_allclose(actual,folded,rtol=1e-5,atol=1e-5)
        self.assertEqual(z.dtype,actual.dtype);self.assertEqual(actual.dtype,np.float32)

    def test_05_fp32_reference_ce(self):
        logits=np.zeros((4,4),np.float32);ce=s.ce_numpy(np,logits,np.arange(4))
        self.assertEqual(ce.dtype,np.float32);np.testing.assert_allclose(ce,np.log(4),rtol=1e-6)

    def test_06_nonfinite_reference_denial(self):
        for kind in ['hidden','weight','std']:
            h=np.ones((1,3),np.float32);w=np.ones((4,3),np.float32);std=np.ones(3,np.float32)
            if kind=='hidden':h[0,0]=np.nan
            elif kind=='weight':w[0,0]=np.inf
            else:std[0]=0
            with self.assertRaises(s.NumericalStop):s.fp32_numpy(np,h,w,np.zeros(4,np.float32),np.zeros(3,np.float32),std)

    def test_07_initial_control_parity(self):
        ctrl=c.read(D/'update0_controls.json');v=np.asarray(ctrl['logits'],np.float32)
        self.assertTrue(s.update0(np,ctrl,v,ctrl['example_ids'],np.asarray(ctrl['labels']))['passed'])

    def test_08_changed_control_logits_denied(self):
        ctrl=c.read(D/'update0_controls.json');v=np.asarray(ctrl['logits'],np.float32);v[0,0]+=1
        with self.assertRaises(s.NumericalStop):s.update0(np,ctrl,v,ctrl['example_ids'],np.asarray(ctrl['labels']))

    def test_09_control_ids_denied(self):
        ctrl=c.read(D/'update0_controls.json')
        with self.assertRaises(s.NumericalStop):s.update0(np,ctrl,np.asarray(ctrl['logits'],np.float32),ctrl['example_ids'][::-1],np.asarray(ctrl['labels']))

    def test_10_backward_blocked_on_each_nonfinite_stage(self):
        for bad in s.PRE_STAGES:
            g,events=self.gate();g.begin(1,1);called=[]
            with self.assertRaises(s.NumericalStop):
                for stage in s.PRE_STAGES:g.stage(stage,stage!=bad)
                g.backward(1.,lambda:called.append(True))
            self.assertEqual(called,[]);self.assertEqual(events[-1]['first_failing_stage'],bad)

    def test_11_check_order(self):
        g,_=self.gate();g.begin(1,1)
        with self.assertRaises(s.NumericalStop):g.stage('logits',True)

    def test_12_bad_gradient_blocks_step(self):
        g,_=self.gate()
        for m in range(1,5):clean_micro(g,m)
        called=[]
        with self.assertRaises(s.NumericalStop):g.step(lambda:g.gradients(False,None,1,None),lambda:None,lambda:None,lambda:called.append(True),lambda:None,lambda:True)
        self.assertEqual(called,[])

    def test_13_bad_clipped_gradient_blocks_step(self):
        g,_=self.gate()
        for m in range(1,5):clean_micro(g,m)
        called=[]
        with self.assertRaises(s.NumericalStop):g.step(lambda:None,lambda:None,lambda:g.gradients(False,1,None,None,True),lambda:called.append(True),lambda:None,lambda:True)
        self.assertEqual(called,[])

    def test_14_parameters_stop_without_retry(self):
        g,_=self.gate()
        for m in range(1,5):clean_micro(g,m)
        steps=[]
        with self.assertRaises(s.NumericalStop):g.step(lambda:None,lambda:None,lambda:None,lambda:steps.append(1),lambda:g.require(False,'parameters_after_step'),lambda:True)
        self.assertEqual(steps,[1])
        with self.assertRaises(s.NumericalStop):g.begin(1,1)

    def test_15_admission20_exact(self):
        g,events=self.gate()
        for _ in range(19):clean_update(g)
        self.assertFalse(g.admitted20());clean_update(g);self.assertTrue(g.admitted20())
        self.assertEqual(sum(x['event']=='NUMERICAL_ADMISSION_20_PASS' for x in events),1)
        clean_update(g);self.assertEqual(g.next_update,22)

    def test_16_explosion_and_no_skip(self):
        g,_=self.gate()
        with self.assertRaises(s.NumericalStop):clean_update(g,ce=53.)
        self.assertFalse(g.admitted20())
        h,_=self.gate()
        with self.assertRaises(s.NumericalStop):h.begin(2,1)

    def test_17_stochastic_variation_allowed(self):
        g,_=self.gate()
        for i,ce in enumerate([20.,0.,0.,0.],1):clean_micro(g,i,ce)
        calls=[];g.step(lambda:calls.append('grad'),lambda:calls.append('clip'),lambda:calls.append('post'),lambda:calls.append('step'),lambda:calls.append('param'),lambda:True)
        self.assertEqual(calls,['grad','clip','post','step','param'])

    def test_18_scope_denial(self):
        for name in ['holdout.json','producer/data','protected/targets','checkpoint-120/adapter','features.npy']:
            with self.assertRaises(s.NumericalStop):s.deny_scope(name)
        for split in ['external_dev','historical_dev','holdout']:
            with self.assertRaises(s.NumericalStop):s.require_training_split(split)

    def test_19_schedule_and_checkpoints(self):
        spec=c.read(D/'experiment.json');self.assertEqual(spec['training']['updates'],896);self.assertEqual(spec['training']['checkpoints'],[448,896])
        records=c.read(ROOT/'tuning/auditor_classifier_lora/records.json');schedule=c.read(ROOT/'tuning/auditor_classifier_lora/schedule.json')
        self.assertEqual(schedule,c.schedule([r['example_id'] for r in records[:1792]]))
        self.assertEqual(c.select([],20)['verdict'],'AUDITOR_CLASSIFIER_LORA_INDETERMINATE')

    def test_20_exact_optimizer_groups(self):
        class P:
            requires_grad=True;dtype='float32'
            def __init__(self,n):self.n=n
            def numel(self):return self.n
        torch=SimpleNamespace(float32='float32',optim=SimpleNamespace(AdamW=lambda groups,**kw:(groups,kw)))
        a=P(14942208);b=P(12292);groups,kw=s.optimizer_groups(torch,[a],[b])
        self.assertEqual([x['lr'] for x in groups],[1e-4,1e-3]);self.assertEqual(kw,dict(betas=(.9,.999),eps=1e-8,weight_decay=0))
        with self.assertRaises(s.NumericalStop):s.optimizer_groups(torch,[a],[a])

    def test_21_no_model_or_generation_entry(self):
        tree=ast.parse((ROOT/'tools/auditor_classifier_lora_stable.py').read_text())
        calls=[x.func.attr for x in ast.walk(tree) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)]
        self.assertNotIn('generate',calls);self.assertNotIn('from_pretrained',calls)
        text=(ROOT/'tools/auditor_classifier_lora_stable.py').read_text()
        self.assertIn('enabled=False',text);self.assertIn('hidden.float()',text)

    def test_22_representation_blocker(self):
        spec=c.read(D/'experiment.json')
        self.assertFalse(spec['historical_adapter_loaded']);self.assertFalse(spec['execution_authorized'])
        self.assertEqual(spec['readiness'],'AUDITOR_CLASSIFIER_LORA_STABILIZED_NOT_READY')
        g=s.HealthGate(14,lambda x:None)
        with self.assertRaises(s.NumericalStop):g.admit_initial(False)

    def test_23_unauthorized_change_blocks_admission(self):
        g,_=self.gate()
        for m in range(1,5):clean_micro(g,m)
        with self.assertRaises(s.NumericalStop):g.step(lambda:None,lambda:None,lambda:None,lambda:None,lambda:None,lambda:False)
        self.assertFalse(g.admitted20())


if __name__=='__main__':unittest.main()
