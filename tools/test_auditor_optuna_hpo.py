"""Deterministic synthetic-only tests. No Torch, real model, or cloud."""
import copy
import contextlib
import json
import math
import random
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.tmp/auditor_hpo_deps'))
import numpy as np
import optuna
import auditor_optuna_hpo as h
from auditor_optuna_hpo_backend import TorchBackend
from auditor_optuna_hpo_remote import authorize,forbidden_path
optuna.logging.set_verbosity(optuna.logging.WARNING)
D=ROOT/'tuning/auditor_optuna_hpo'
SPLIT=json.loads((D/'split.json').read_bytes())
P=dict(lora_peak_lr=1e-5,head_lr=1e-4,warmup_steps=10,dropout=.05)


def result(number=0,**kw):
    r=dict(trial_number=number,params=dict(P),updates=80,stable=True,representation_drift=.1,
           metrics=dict(macro_f1=.7,minimum_class_recall=.6,ce=.4))
    r.update(kw);return r


class FakeBackend:
    """Hand-authored state transitions, never a model or a trained surrogate."""
    def __init__(self,explode=False):
        self.admitted=True;self.state={'adapter':[1.,2.],'head':[3.,4.]};self.opt=None;self.grad=None
        self.starts=[];self.updates=[];self.diagnostics=[];self.evaluations=[];self.explode=explode
    def snapshot(self):return copy.deepcopy(self.state)
    def state_hash(self):return h.digest(self.state)
    def restore(self,x):self.state=x
    def discard_optimizer(self):self.opt=None
    def clear_gradients(self):self.grad=None
    def gradients_empty(self):return self.grad is None
    def set_dropout(self,x):self.dropout=x
    def seed(self,x):self.seed_value=x
    def new_optimizer(self,p):self.opt={};self.starts.append(copy.deepcopy(self.state))
    def optimizer_empty(self):return self.opt=={}
    def set_lrs(self,l,r):self.lrs=(l,r)
    def update(self,ids,step,gate):
        if self.explode:gate.micro(134.58)
        self.state['adapter'][0]+=1.;self.opt['step']=step;self.updates.append(step)
        return {'ce':.1}
    def diagnostic(self,i,step,gate):self.diagnostics.append(step);return dict(telemetry={'no_grad':True,'rng_restored':True},x=step)
    def drift(self,a,b):return float(b['x'])
    def evaluate(self,ids,gate):self.evaluations.append(tuple(ids));return dict(macro_f1=.7,minimum_class_recall=.6,ce=.4)


class HPOTests(unittest.TestCase):
    def test_01_frozen_split(self):
        rows=[dict(example_id=r['example_id'],relation=r['relation'],dataset=r['source_family']) for r in SPLIT['assignments']]
        self.assertEqual(h.freeze_split(rows),SPLIT)
        self.assertEqual(h.freeze_split(rows[::-1]),SPLIT)
    def test_02_class_source_balance(self):
        for label in h.CLASSES:
            for split,n,hist in [('inner_train',358,38),('inner_val',90,10)]:
                rows=[r for r in SPLIT['assignments'] if r['relation']==label and r['split']==split]
                self.assertEqual(len(rows),n);self.assertEqual(sum(r['source_family']=='historical' for r in rows),hist)
    def test_03_split_hashes(self):
        for name in ['inner_train','inner_val']:
            self.assertEqual(h.digest([r for r in SPLIT['assignments'] if r['split']==name]),SPLIT[name+'_sha256'])
    def denied(self,name):
        boundary=h.DataBoundary({})
        with patch.object(Path,'read_bytes',side_effect=AssertionError('opened')):
            with self.assertRaises(PermissionError):boundary.read(name)
        self.assertEqual(sum(boundary.access_counts.values()),0)
    def test_04_external_dev_denial(self):self.denied('external_dev.json')
    def test_05_historical_dev_denial(self):self.denied('historical_dev.json')
    def test_06_holdout_denial(self):self.denied('holdout.json')
    def test_07_protected_denial(self):self.denied('protected/data.json')
    def test_08_challenges_denial(self):
        for name in ['shorter.json','longer.json','challenges.json']:self.denied(name)
    def test_09_mixed_file_denial(self):self.denied('tuning/auditor_classifier_lora/records.json')
    def test_10_unbound_denial(self):self.denied('anything.json')
    def test_11_clean_reset(self):
        b=FakeBackend();reset=h.CleanReset(b);reset.reset(b,P);b.state['head'][0]=999;b.grad=42;b.opt['moment']=99
        reset.reset(b,P);self.assertEqual(b.starts[0],b.starts[1]);self.assertIsNone(b.grad);self.assertEqual(b.opt,{})
    def test_12_bad_reset_fails(self):
        b=FakeBackend();reset=h.CleanReset(b);b.state['head'][0]=999;b.restore=lambda x:None
        with self.assertRaisesRegex(ValueError,'reset identity'):reset.reset(b,P)
    def test_13_optimizer_state_leakage(self):
        b=FakeBackend();reset=h.CleanReset(b);b.new_optimizer=lambda p:setattr(b,'opt',{'moment':1})
        with self.assertRaisesRegex(ValueError,'optimizer state leakage'):reset.reset(b,P)
    def test_14_exact_search_space(self):
        study=h.create_study(optuna);trial=study.ask();p=h.sample(trial)
        self.assertEqual(set(p),h.PARAMS)
        self.assertEqual(trial.distributions['lora_peak_lr'],optuna.distributions.FloatDistribution(1e-6,1e-4,log=True))
        self.assertEqual(trial.distributions['head_lr'],optuna.distributions.FloatDistribution(1e-4,1e-3,log=True))
        self.assertEqual(list(trial.distributions['warmup_steps'].choices),[0,5,10,20,40])
        self.assertEqual(list(trial.distributions['dropout'].choices),[0.,.05])
    def test_15_warmup_arithmetic(self):
        for n in [0,5,10,20,40]:
            p=dict(P,warmup_steps=n)
            self.assertAlmostEqual(h.lora_lr(p,1),p['lora_peak_lr']/(n or 1))
            self.assertEqual(h.lora_lr(p,80),p['lora_peak_lr'])
            if n:self.assertEqual(h.lora_lr(p,n),p['lora_peak_lr'])
        for step in [0,81]:
            with self.assertRaises(ValueError):h.lora_lr(P,step)
    def test_16_dropout_selection(self):
        b=FakeBackend();r=h.CleanReset(b)
        for d in [0.,.05]:r.reset(b,dict(P,dropout=d));self.assertEqual(b.dropout,d)
        with self.assertRaises(ValueError):h.validate_params(dict(P,dropout=.1))
    def test_17_nonfinite_pruning(self):
        for x in [float('nan'),float('inf'),-float('inf')]:
            with self.assertRaises(h.Instability):h.Stability(.08585).finite(x)
    def test_18_explosion_pruning(self):
        g=h.Stability(.08585197478532791)
        self.assertAlmostEqual(g.micro_ceiling,55.451774444795625)
        g.update([.006]*4)
        with self.assertRaisesRegex(h.Instability,'microbatch'):g.micro(134.577728)
        with self.assertRaisesRegex(h.Instability,'mean_update'):g.update([20.]*4)
    def test_19_objective(self):self.assertAlmostEqual(h.objective_value(result()['metrics']),.675)
    def test_20_metrics(self):
        m=h.metrics(h.CLASSES,h.CLASSES,[.1]*4)
        self.assertEqual(m['macro_f1'],1.);self.assertEqual(m['minimum_class_recall'],1.)
        self.assertEqual(m['confusion_matrix'],np.eye(4,dtype=int).tolist())
    def test_21_tie_breaks(self):
        a=result(1);b=result(2);self.assertLess(h.winner_key(a),h.winner_key(b))
        b['params']['lora_peak_lr']=1e-6;self.assertLess(h.winner_key(b),h.winner_key(a))
        a['representation_drift']=0.;self.assertLess(h.winner_key(a),h.winner_key(b))
        b['metrics']['ce']=.1;self.assertLess(h.winner_key(b),h.winner_key(a))
        # Equal objective: larger F1 wins before minimum recall.
        a['metrics']=dict(macro_f1=.8,minimum_class_recall=.3,ce=.9)
        self.assertAlmostEqual(h.objective_value(a['metrics']),h.objective_value(b['metrics']))
        self.assertLess(h.winner_key(a),h.winner_key(b))
    def test_22_successive_halving_actual(self):
        s=h.create_study(optuna);a=s.ask();h.sample(a);a.report(.9,20);self.assertFalse(a.should_prune());a.report(.9,40);self.assertFalse(a.should_prune());s.tell(a,.9)
        b=s.ask();h.sample(b);b.report(.1,20);self.assertTrue(b.should_prune())
        c=s.ask();h.sample(c);c.report(.95,20);self.assertFalse(c.should_prune());c.report(.1,40);self.assertTrue(c.should_prune())
    def test_23_winner_freeze(self):
        r=h.freeze_winner([result()]);self.assertEqual(set(r['hyperparameters']),h.PARAMS)
        self.assertFalse(r['full_training_auto_execute']);self.assertEqual(r['future_separate_design']['checkpoints'],[448,896])
    def test_24_no_candidate(self):
        for r in [result(updates=40),result(stable=False),result(metrics=dict(macro_f1=.59,minimum_class_recall=.5,ce=.1)),result(metrics=dict(macro_f1=.8,minimum_class_recall=.44,ce=.1))]:
            self.assertEqual(h.freeze_winner([r])['verdict'],'AUDITOR_OPTUNA_HPO_NO_CANDIDATE')
    def test_25_trial_and_update_caps(self):
        b=FakeBackend();events=[];s,w=h.run_study(optuna,b,SPLIT,.08585,events.append)
        self.assertEqual(len(s.trials),15);self.assertEqual(len(b.updates),1200);self.assertEqual(max(b.updates),80)
        self.assertTrue(all(x==b.starts[0] for x in b.starts));self.assertEqual(len(b.evaluations),45)
        self.assertEqual(b.diagnostics,list(h.DIAGNOSTICS)*15);self.assertFalse(w['full_training_auto_execute'])
    def test_26_numerical_prune_no_candidate(self):
        s,w=h.run_study(optuna,FakeBackend(True),SPLIT,.08585,lambda x:None)
        self.assertTrue(all(t.state==optuna.trial.TrialState.PRUNED for t in s.trials));self.assertEqual(w['verdict'],'AUDITOR_OPTUNA_HPO_NO_CANDIDATE')
    def test_27_sampler_determinism(self):
        def run():
            s=h.create_study(optuna)
            for _ in range(15):
                t=s.ask();p=h.sample(t);s.tell(t,p['lora_peak_lr']/1e-4)
            return [t.params for t in s.trials]
        self.assertEqual(run(),run())
    def test_28_schedule_train_only(self):
        train={r['example_id'] for r in SPLIT['assignments'] if r['split']=='inner_train'}
        plan=h.schedule(SPLIT);self.assertEqual(len(plan),80);self.assertTrue(all(len(b)==4 and set(b)<=train for b in plan))
    def test_29_admission_required(self):
        b=FakeBackend();b.admitted=False
        with self.assertRaisesRegex(ValueError,'reuse admission'):h.run_study(optuna,b,SPLIT,.1,lambda x:None)
    def admission(self):
        rows=[dict(example_id=str(i),relation=h.CLASSES[i%4]) for i in range(1792)]
        feats=np.zeros((1792,3),np.float32);m=np.zeros(3,np.float32);s=np.ones(3,np.float32);w=np.zeros((4,3),np.float32);b=np.zeros(4,np.float32)
        baseline=dict(predicted_indices=[0]*1792,ce_range=[1.38,1.39],metrics=dict(macro_f1=.1))
        gate=h.ReuseAdmission(np,feats,m,s,w,b,rows,[str(i) for i in range(16)],{'runtime':7},baseline)
        observe=lambda r:dict(hidden=feats[int(r['example_id'])].copy(),standardized=np.zeros(3,np.float32),logits=np.zeros(4,np.float32))
        return gate,observe
    def test_30_reuse_one_pass(self):
        gate,observe=self.admission();calls=[]
        def f(row):calls.append(row['example_id']);return observe(row)
        r=gate.run({'runtime':7},f,lambda s:None,lambda:None)
        self.assertEqual(len(calls),1792+32);self.assertEqual(r['full_train_passes'],1)
        with self.assertRaises(ValueError):gate.run({'runtime':7},f,lambda s:None,lambda:None)
    def test_31_reuse_runtime_mismatch(self):
        gate,observe=self.admission()
        with self.assertRaisesRegex(ValueError,'runtime mismatch'):gate.run({'runtime':8},observe,lambda s:None,lambda:None)
        self.assertFalse(gate.passed)
    def test_32_reuse_features_mismatch(self):
        gate,observe=self.admission()
        def bad(row):r=observe(row);r['hidden'][0]=1.;return r
        with self.assertRaisesRegex(ValueError,'current-cache'):gate.run({'runtime':7},bad,lambda s:None,lambda:None)
        self.assertFalse(gate.passed)
    def test_33_no_authorization_created(self):
        with self.assertRaises(ValueError):authorize({},'abc')
        self.assertFalse(h.config()['cloud_authorized']);self.assertFalse(h.config()['full_training_auto_execute'])
    def test_34_audit_deny_paths(self):
        for p in ['external_dev.json','historical_dev.json','shorter.json','longer.json','holdout.json','protected/data','finite_partial_state.safetensors']:
            self.assertTrue(forbidden_path(p))
        self.assertFalse(forbidden_path('records_train_only.json'))
    def test_35_matched_diagnostic_context_rng_and_modes(self):
        # Exercise the production context manager with a minimal RNG/module facade.
        module=SimpleNamespace(training=False);head=SimpleNamespace(training=True)
        state={'cpu':7,'gpu':9}
        fake_t=SimpleNamespace(get_rng_state=lambda:state['cpu'],set_rng_state=lambda v:state.__setitem__('cpu',v),no_grad=contextlib.nullcontext,
            cuda=SimpleNamespace(get_rng_state_all=lambda:state['gpu'],set_rng_state_all=lambda v:state.__setitem__('gpu',v)))
        backend=TorchBackend.__new__(TorchBackend);backend.t=fake_t;backend.np=np
        backend.model=SimpleNamespace(modules=lambda:[module]);backend.head=SimpleNamespace(modules=lambda:[head]);backend.state_hash=lambda:'immutable';backend.gradients_empty=lambda:True
        random.seed(7);np.random.seed(7);py_before=random.getstate();np_before=np.random.get_state()
        with backend.diagnostic_context():
            random.random();np.random.rand();state.update(cpu=99,gpu=99);module.training=True;head.training=False
        self.assertEqual(random.getstate(),py_before);self.assertTrue(np.array_equal(np.random.get_state()[1],np_before[1]));self.assertEqual(state,{'cpu':7,'gpu':9})
        self.assertFalse(module.training);self.assertTrue(head.training)
    def test_36_artifact_hashes_and_no_partial(self):
        artifacts=json.loads((D/'artifacts.json').read_bytes())
        for name,digest in h.ARTIFACT_HASHES.items():self.assertEqual(artifacts[name]['sha256'],digest)
        self.assertFalse(any('partial' in r['path'] for r in artifacts.values()))
    def test_37_real_optuna_dependency(self):self.assertEqual(optuna.__version__,'4.5.0')
    def test_38_no_model_import(self):self.assertNotIn('torch',sys.modules)
    def test_39_process_audit_before_open(self):
        code="""import sys
sys.path.insert(0,'tools')
from auditor_optuna_hpo_remote import install_audit
r={'denied_before_open':0};install_audit(r)
for name in ['external_dev.json','historical_dev.json','shorter.json','longer.json','holdout.json','protected.json']:
    try:open(name,'rb')
    except PermissionError:pass
    else:raise AssertionError('not denied')
assert r['denied_before_open']==6
"""
        p=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr.decode())
    def test_40_authorization_budget_reserve(self):
        p=dict(operator_authorized=True,action='auditor-optuna-train-only-hpo',seal_sha256='abc',instances=1,gpus=1,n_jobs=1,max_trials=15,max_updates=80,
            soft_budget_usd=7.,hard_budget_usd=9.,full_training_authorized=False,provider='https://cloud.lambda.ai',region='us-east-1',instance_type='gpu_1x_a10',launch_epoch=1000.,hourly_rate=1.29,workload_deadline_epoch=2000.)
        authorize(p,'abc')
        p['workload_deadline_epoch']=1000+9/1.29*3600
        with self.assertRaisesRegex(ValueError,'teardown reserve'):authorize(p,'abc')
    def test_41_diagnostic_schedule_and_drift(self):
        self.assertEqual(h.DIAGNOSTICS,(0,1,2,5,10,20,40,80))
        backend=TorchBackend.__new__(TorchBackend);backend.np=np
        self.assertEqual(backend.drift({'eval_standardized':np.array([0.,0.])},{'eval_standardized':np.array([3.,4.])}),5.)
    def test_42_preparation_access_receipt(self):
        receipt=json.loads((D/'preparation_receipt.json').read_bytes())
        self.assertEqual(receipt['process_audit']['access_counts'],dict.fromkeys(h.FORBIDDEN,0))
        self.assertEqual(receipt['process_audit']['denied_before_open'],0)
        self.assertTrue(receipt['all_1792_prompt_token_hashes_match'])
        self.assertFalse(receipt['local_model_load'])
    def test_43_production_dropout_replacement(self):
        backend=TorchBackend.__new__(TorchBackend)
        modules=[SimpleNamespace(lora_dropout={'classifier_fork':None}) for _ in range(224)]
        cfg=SimpleNamespace(lora_dropout=.05)
        backend.model=SimpleNamespace(modules=lambda:modules,peft_config={'classifier_fork':cfg})
        backend.t=SimpleNamespace(nn=SimpleNamespace(Dropout=lambda p:SimpleNamespace(p=p)))
        for value in [0.,.05]:
            backend.set_dropout(value)
            self.assertEqual(cfg.lora_dropout,value)
            self.assertTrue(all(m.lora_dropout['classifier_fork'].p==value for m in modules))
    def test_44_matched_telemetry(self):
        class Array(np.ndarray):
            def detach(self):return self
            def cpu(self):return self
            def numpy(self):return np.asarray(self)
        class Module:
            training=False
            def train(self):self.training=True
            def eval(self):self.training=False
        b=TorchBackend.__new__(TorchBackend);b.model=Module();b.head=Module();b.splits={'control':'inner_train'}
        b.seed=lambda n:None;b.diagnostic_context=contextlib.nullcontext;b.t=SimpleNamespace(linalg=SimpleNamespace(vector_norm=np.linalg.norm))
        calls=[]
        def forward(i,g,diagnostic_only=False):
            calls.append((b.model.training,diagnostic_only))
            v=np.array([[float(b.model.training),0.]]).view(Array)
            return v,v,v,134.58,{'train_mode':b.model.training,'ce':134.58}
        b.forward=forward
        r=b.diagnostic('control',1,h.Stability(.08585))
        self.assertEqual(calls,[(False,True),(True,True)])
        self.assertEqual(r['telemetry']['hidden_difference_l2'],1.)
        self.assertTrue(r['telemetry']['rng_restored']);self.assertTrue(r['telemetry']['no_grad'])
        self.assertEqual(set(r['telemetry']['vectors']),{'eval_hidden','eval_standardized','eval_logits','train_hidden','train_standardized','train_logits'})
    def test_45_extra_search_parameter_denied(self):
        with self.assertRaises(ValueError):h.validate_params(dict(P,rank=16))
    def test_46_admission_thresholds_inclusive(self):
        r=result(metrics=dict(macro_f1=.60,minimum_class_recall=.45,ce=1.))
        self.assertEqual(h.freeze_winner([r])['verdict'],'AUDITOR_OPTUNA_HPO_CANDIDATE')


if __name__=='__main__':unittest.main()
