import ast
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import auditor_classifier_lora_fork as f
import auditor_classifier_lora_stable as s
import auditor_v2_execution as old

ROOT=Path(__file__).resolve().parents[1];D=ROOT/'tuning/auditor_classifier_lora_fork'
def read(p):return json.loads(p.read_bytes())


class P:
    def __init__(self,train=False):self.requires_grad=train
    def requires_grad_(self,v):self.requires_grad=v;return self


class Model:
    def __init__(self):
        self.peft_config={f.CANDIDATE:None};self.active_adapters=[f.CANDIDATE]
        self.items=[('base.weight',P()),('layer.lora_A.classifier_fork.weight',P(True)),('layer.lora_B.classifier_fork.weight',P(True))]
    def named_parameters(self):return iter(self.items)
    def parameters(self):return iter([p for _,p in self.items])
    def set_adapter(self,x):self.active_adapters=[x]
    def eval(self):return self


class Tests(unittest.TestCase):
    def fixture(self):
        classes=['MATCH','DIVERGENCE','OMISSION','ADDITION']
        rows=[dict(example_id=str(i),split='train',input_ids=[1,i+2],relation=c) for i,c in enumerate(classes)]
        logits=np.eye(4,dtype=np.float32)*3
        ce=float(s.ce_numpy(np,logits,np.arange(4)).mean())
        controls=dict(example_ids=[r['example_id'] for r in rows],labels=list(range(4)),logits=logits.tolist(),predicted_indices=list(range(4)),rtol=1e-4,atol=2e-4,ce_range=[ce-.001,ce+.001])
        baseline=dict(classes=classes,example_ids=controls['example_ids'],input_id_hashes=[f.token_hash(r['input_ids']) for r in rows],labels=classes,predicted_indices=list(range(4)),metrics=old.metrics(classes,classes),ce_range=controls['ce_range'])
        events=[];state={'slot':None,'removed':False}
        gate=f.Preflight(np,controls,baseline,events.append)
        def select(slot):state['slot']=slot;events.append(slot)
        def observe(row):
            i=int(row['example_id']);return dict(input_ids=row['input_ids'],hidden=np.array([i,2],dtype=np.float32),normalized=np.array([i,2],dtype=np.float32),logits=logits[i].copy())
        def remove():state['removed']=True;events.append('removed')
        return gate,rows,select,observe,remove,lambda:state['removed'],state,events

    def test_01_artifact_copy(self):
        r=read(D/'adapter_copy.json');source=ROOT/r['source_path'];dest=ROOT/r['fork_path']
        self.assertEqual(f.sha(source/'adapter_model.safetensors'),f.SOURCE_SHA)
        self.assertEqual(f.sha(dest/'adapter_model.safetensors'),f.SOURCE_SHA)
        self.assertEqual(f.sha(source/'adapter_config.json'),f.CONFIG_SHA)
        self.assertEqual(f.sha(dest/'adapter_config.json'),f.CONFIG_SHA)
        self.assertEqual(f.inventory(source/'adapter_model.safetensors'),f.inventory(dest/'adapter_model.safetensors'))
        self.assertEqual(r['tensors_compared'],448);self.assertEqual(r['parameters'],14942208)
        self.assertFalse((source/'adapter_model.safetensors').samefile(dest/'adapter_model.safetensors'))

    def test_02_source_destination_rejected(self):
        source=ROOT/read(D/'adapter_copy.json')['source_path']
        with self.assertRaises(s.NumericalStop):f.create_fork(source,source)
        with self.assertRaises(s.NumericalStop):f.create_fork(source,source/'nested')

    def test_03_corrupt_source_rejected_without_write(self):
        with tempfile.TemporaryDirectory() as t:
            src=Path(t)/'src';src.mkdir();(src/'adapter_model.safetensors').write_bytes(b'invalid')
            with self.assertRaises(s.NumericalStop):f.create_fork(src,Path(t)/'dest')
            self.assertFalse((Path(t)/'dest').exists())

    def test_04_protocol_success(self):
        g,rows,select,obs,remove,verify,state,events=self.fixture()
        self.assertTrue(g.run(rows,select,obs,remove,verify)['passed'])
        self.assertTrue(state['removed']);self.assertLess(events.index(f.REFERENCE),events.index(f.CANDIDATE))
        self.assertLess(events.index('removed'),next(i for i,v in enumerate(events) if isinstance(v,dict) and v['event']=='UPDATE0_PASS'))

    def test_05_each_parity_boundary_fails_sticky(self):
        for key in ['hidden','normalized','logits']:
            g,rows,sel,obs,remove,verify,state,_=self.fixture()
            def bad(row):
                v=obs(row)
                if state['slot']==f.CANDIDATE:v[key]=v[key]+1
                return v
            with self.assertRaises(s.NumericalStop):g.run(rows,sel,bad,remove,verify)
            self.assertFalse(state['removed']);self.assertTrue(g.failed)
            with self.assertRaises(s.NumericalStop):g.run(rows,sel,obs,remove,verify)

    def test_06_tokens_and_labels_bound(self):
        for field,value in [('input_ids',[9]),('relation','ADDITION'),('example_id','other'),('split','historical_dev')]:
            g,rows,sel,obs,remove,verify,_,_=self.fixture();rows[0][field]=value
            with self.assertRaises(s.NumericalStop):g.run(rows,sel,obs,remove,verify)

    def test_07_nan_rejected(self):
        g,rows,sel,obs,remove,verify,_,_=self.fixture()
        def bad(row):
            v=obs(row);v['hidden'][0]=np.nan;return v
        with self.assertRaises(s.NumericalStop):g.run(rows,sel,bad,remove,verify)

    def test_08_reference_removal_required(self):
        g,rows,sel,obs,remove,_,_,_=self.fixture()
        with self.assertRaises(s.NumericalStop):g.run(rows,sel,obs,remove,lambda:False)

    def test_09_full_train_baseline_rejected(self):
        for predictions in [True,False]:
            g,rows,sel,obs,remove,verify,_,_=self.fixture()
            if predictions:g.baseline['predicted_indices']=[3]*4
            else:g.baseline['ce_range']=[5,6]
            with self.assertRaises(s.NumericalStop):g.run(rows,sel,obs,remove,verify)

    def test_10_metrics_rejected(self):
        g,rows,sel,obs,remove,verify,_,_=self.fixture();g.baseline['metrics']={}
        with self.assertRaises(s.NumericalStop):g.run(rows,sel,obs,remove,verify)

    def test_11_optimizer_before_gate_denied(self):
        g,*_=self.fixture()
        with self.assertRaises(s.NumericalStop):g.optimizer(None,None,None,None)

    def test_12_only_fork_trainable(self):
        m=Model();head=SimpleNamespace(parameters=lambda:iter([P(True)]))
        self.assertEqual(len(f.trainable_fork_only(m,head)),2)
        m.items[0][1].requires_grad=True
        with self.assertRaises(s.NumericalStop):f.trainable_fork_only(m,head)

    def test_13_reference_slot_and_dual_path_denied(self):
        for mode in ['slot','active','parameter']:
            m=Model();head=SimpleNamespace(parameters=lambda:iter([P(True)]))
            if mode=='slot':m.peft_config[f.REFERENCE]=None
            elif mode=='active':m.active_adapters.append(f.REFERENCE)
            else:m.items.append(('layer.lora_A.historical_reference.weight',P()))
            with self.assertRaises(s.NumericalStop):f.trainable_fork_only(m,head)
            health=s.HealthGate(14,lambda x:None)
            with self.assertRaises(s.NumericalStop):f.prospective_update(None,m,head,None,None,None,None,None,health,None)
            self.assertTrue(health.failed)

    def test_14_freeze_reference(self):
        m=Model();hp=P(True);head=SimpleNamespace(parameters=lambda:iter([hp]),eval=lambda:None)
        f.freeze_slots(m,head)
        self.assertFalse(any(p.requires_grad for p in m.parameters()));self.assertFalse(hp.requires_grad)
        f.activate_fork_training(m,head);self.assertTrue(hp.requires_grad);self.assertFalse(m.items[0][1].requires_grad)

    def test_15_unchanged_contract(self):
        before=read(ROOT/'tuning/auditor_classifier_lora_stable/experiment.json');after=read(D/'experiment.json')
        for key in ['lora','optimizer','training','gates','challenge_gates','numerical_gate','initialization_artifacts','classification_dtypes']:
            self.assertEqual(before[key],after[key])
        for p,h in read(D/'bindings.json').items():self.assertEqual(f.sha(ROOT/p),h)
        self.assertFalse(after['cloud_authorized']);self.assertFalse(after['runtime_model_function_parity_proven'])

    def test_16_no_model_loading_or_generation(self):
        for name in ['auditor_classifier_lora_fork.py','prepare_auditor_classifier_lora_fork.py']:
            tree=ast.parse((ROOT/'tools'/name).read_text())
            calls=[x.func.attr for x in ast.walk(tree) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)]
            self.assertNotIn('generate',calls);self.assertNotIn('from_pretrained',calls)
        text=(ROOT/'tools/auditor_classifier_lora_fork.py').read_text()
        self.assertIn('torch.inference_mode()',text);self.assertIn('model.delete_adapter(REFERENCE)',text)

    def test_17_forbidden_scope(self):
        for x in ['holdout','Producer','protected']:
            with self.assertRaises(s.NumericalStop):s.deny_scope(x)

    def test_18_optimizer_only_after_preflight(self):
        g,rows,sel,obs,remove,verify,_,_=self.fixture();g.run(rows,sel,obs,remove,verify)
        m=Model();hp=P(True)
        for _,p in m.items:p.dtype='float32'
        hp.dtype='float32';hp.numel=lambda:12292
        m.items[1][1].numel=lambda:7471104;m.items[2][1].numel=lambda:7471104
        head=SimpleNamespace(parameters=lambda:iter([hp]));calls=[]
        torch=SimpleNamespace(float32='float32',optim=SimpleNamespace(AdamW=lambda groups,**kw:calls.append((groups,kw)) or 'optimizer'))
        health=s.HealthGate(13.862943611198906,lambda x:None)
        self.assertEqual(g.optimizer(torch,m,head,health),'optimizer')
        self.assertTrue(health.initial_parity)
        self.assertEqual(calls[0][0][0]['params'],[m.items[1][1],m.items[2][1]])
        with self.assertRaises(s.NumericalStop):g.optimizer(torch,m,head,health)
        self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()
