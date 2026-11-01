"""Auditor-only binding and deterministic tests, no experiment training/generation."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'tuning/auditor_linear_probe'
BASE=ROOT/'docs/fix/auditor_linear_probe_run'
OLD=ROOT/'tuning/auditor_canonical_execution'
sys.path.insert(0,str(ROOT/'tools'))
import auditor_linear_core as c
from cloud_run_common import credential_locations,write_json
sys.path.insert(0,str(ROOT/'tuning/second_domain_agnostic_v2'))
import runtime as r


def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def preserve():
    counts={}
    for folder in ('auditor_canonical_tuning_run','producer_tuning_v3_run'):
        m=read(ROOT/'docs/fix'/folder/'EVIDENCE_MANIFEST.json')
        for name,e in m['text_files'].items():assert sha(ROOT/name)==e['sha256'],name
        for name,e in m['local_only_binaries'].items():assert (ROOT/name).stat().st_size==e['bytes'],name
        counts[folder]=len(m['text_files'])
    m=read(ROOT/'docs/fix/auditor_relation_diagnosis/VERIFICATION.json')
    for name,e in m['files'].items():assert sha(ROOT/name)==e['sha256'],name
    return counts


def build():
    assert not (BASE/'LAUNCH_INTENT.json').exists(),'Authorization consumed'
    D.mkdir(exist_ok=True);BASE.mkdir(exist_ok=True)
    history=preserve();rows=read(OLD/'dataset.json');split=read(OLD/'split.json');protocol=read(OLD/'evaluation_protocol.json');model=read(OLD/'experiment.json')
    tok=r.old.tokenizer('auditor');records=[];allowances=[]
    for row in rows:
        normalized,mapping=c.normalized_input(row['input']);record=dict(example_id=row['example_id'],alias_map=mapping)
        for name,value in [('original',row['input']),('normalized',normalized)]:
            prompt=tok.apply_chat_template(r.task_messages(dict(role='auditor',input=value)),tokenize=False,add_generation_prompt=True)
            record[name+'_prompt']=prompt;record[name+'_ids']=tok(prompt,add_special_tokens=False)['input_ids']
        assert row['example_id'] not in record['normalized_prompt']
        record['reason_allowances']={cl:192-(len(tok(c.assemble(row['input'],cl,''),add_special_tokens=False)['input_ids'])+1)+2 for cl in c.CLASSES[:4]}
        allowances.extend(record['reason_allowances'].values());records.append(record)
    assert len(rows)==300 and len(split['train'])==240 and len(split['validation'])==60
    source=ROOT/'docs/fix/auditor_canonical_tuning_run/downloaded/evidence/checkpoint-120'
    adapter_hashes={name:sha(source/name) for name in ['adapter_config.json','adapter_model.safetensors']}
    assert adapter_hashes['adapter_model.safetensors']=='733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6'
    spec=dict(name='auditor-linear-probe',design_commit='25f7dc0cb1bd11d652debbec52940f84e9d64193',model=model,adapter_hashes=adapter_hashes,
        head=dict(input_dim=3072,classes=c.CLASSES,parameters=15365,updates=200,lr=.01,regularization=.001,seed=7),generation=protocol['generation_kwargs'],control_ids=protocol['control_ids'],max_reason_allowance=max(allowances),
        original_dataset_sha256=sha(OLD/'dataset.json'),original_split_sha256=sha(OLD/'split.json'),design_sha256=sha(ROOT/'docs/fix/AUDITOR_RELATION_FAILURE_DIAGNOSIS.md'),
        standardization=dict(ddof=0,train_only=True,clamp=1e-6),limits=dict(workload_seconds=3000,termination_seconds=3300,instances=1,hard_usd=3,soft_usd=1.5))
    # Exact data and split bytes, no row editing or new examples.
    (D/'dataset.json').write_bytes((OLD/'dataset.json').read_bytes());(D/'split.json').write_bytes((OLD/'split.json').read_bytes())
    write_json(D/'experiment.json',spec);write_json(D/'records.json',records)
    write_json(D/'binding.json',dict(files={p.name:sha(p) for p in D.iterdir() if p.is_file() and p.name!='binding.json'},history=history,design_commit=spec['design_commit']))
    return rows,split,tok,records,spec


class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rows,cls.split,cls.tok,cls.records,cls.spec=build()

    def test_alias_invariance_all_300(self):
        for row,record in zip(self.rows,self.records):
            value=copy.deepcopy(row['input']);first,mapping=c.normalized_input(value)
            rename={old:f'REF-{987654321+1009*n}' for n,old in enumerate(mapping)}
            def sub(v):
                if isinstance(v,str):return c.REF.sub(lambda m:rename[m.group()],v)
                if isinstance(v,list):return [sub(x) for x in v]
                if isinstance(v,dict):return {k:sub(x) for k,x in v.items()}
                return v
            second,_=c.normalized_input(sub(value));self.assertEqual(first,second)
            self.assertEqual(value,row['input'])
            self.assertEqual(record['normalized_prompt'],self.tok.apply_chat_template(r.task_messages(dict(role='auditor',input=second)),tokenize=False,add_generation_prompt=True))

    def test_leakage_rejected(self):
        for key in ('example_id','gold_relation','reason','template_family','row_position','saved_prediction'):
            value=copy.deepcopy(self.rows[0]['input']);value[key]='DO_NOT_USE'
            with self.assertRaises(AssertionError):c.normalized_input(value)
        for row in self.rows:
            self.assertEqual(set(row['input']),c.INPUT_KEYS)
            for span in row['input']['source_spans']+row['input']['context_only_spans']:self.assertEqual(set(span),{'alias','text'})

    def test_saved_prefixes_60_and_fail_closed(self):
        saved=read(ROOT/'docs/fix/auditor_canonical_tuning_run/downloaded/evidence/checkpoint-120/full_dev_scored.json')
        for row in saved:
            found='waiting'
            for n in range(1,17):
                ids=row['output_token_ids'][:n];found=c.probe_state(self.tok.decode(ids,skip_special_tokens=True),ids[-1] in self.spec['generation']['eos_token_id'])
                if found!='waiting':break
            self.assertEqual(found,'refusal' if row['metrics']['predicted_refusal'] else 'nonempty')
        for bad in ['hello','{"items":[],"status":"ok"}',c.REFUSAL+'x']:
            with self.assertRaises(ValueError):c.probe_state(bad)
        with self.assertRaises(ValueError):c.probe_state('{"items":',True)

    def test_reason_parser(self):
        for reason in ['quoted "value"','backslash \\','unicode λ','line\nbreak','trailing slash\\','']:
            escaped=json.dumps(reason,ensure_ascii=False)[1:]
            for n in range(len(escaped)):self.assertEqual(c.parse_reason(escaped[:n])['state'],'waiting')
            found=c.parse_reason(escaped+',"ref_ids":');self.assertEqual(found['state'],'complete');self.assertEqual(found['reason'],reason)
        for bad in ['bad\\q"','bad\n"','bad\\uZZZZ"']:self.assertEqual(c.parse_reason(bad)['state'],'malformed')

    def test_contract_cap_and_routing(self):
        for row in self.rows:
            if row['relation']=='INSUFFICIENT_EVIDENCE':continue
            gold=row['semantic_target']['items'][0];assembled=c.assemble(row['input'],row['relation'],gold['reasoning'])
            self.assertTrue(r.score(row,assembled)['accepted_outcome'])
            self.assertLessEqual(len(self.tok(assembled,add_special_tokens=False)['input_ids'])+1,192)
        invalid=copy.deepcopy(self.rows[0]['input']);invalid['required_refs']*=2
        with self.assertRaises(AssertionError):c.assemble(invalid,'MATCH','x')
        invalid=copy.deepcopy(self.rows[0]['input']);invalid['required_refs']=['REF-0000']
        with self.assertRaises(AssertionError):c.assemble(invalid,'MATCH','x')
        self.assertEqual(c.route('refusal','MATCH'),'INSUFFICIENT_EVIDENCE');self.assertEqual(c.route('nonempty','OMISSION'),'OMISSION')
        self.assertGreater(len(self.tok(c.assemble(self.rows[0]['input'],'MATCH','long '*500),add_special_tokens=False)['input_ids'])+1,192)

    def test_train_only_statistics(self):
        import numpy as np
        x=np.zeros((300,3072),dtype=np.float32);x[:240]=np.arange(240,dtype=np.float32)[:,None]
        a,b,_=c.standardized(np,x,list(range(240)));x[240:]=1e9;aa,bb,_=c.standardized(np,x,list(range(240)))
        np.testing.assert_array_equal(a,aa);np.testing.assert_array_equal(b,bb)
        x[:240]=0;_,std,_=c.standardized(np,x,list(range(240)));self.assertTrue((std==np.float32(1e-6)).all())

    def test_training_contract_static(self):
        source=(ROOT/'tools/auditor_linear_core.py').read_text(encoding='utf8');tree=ast.parse(source)
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='train_head');text=ast.get_source_segment(source,fn)
        for bound in ['range(1,201)','torch.nn.Linear(3072,5','head.weight.zero_()','head.bias.zero_()','callback(0,head','lr=.01','weight_decay=0']:self.assertIn(bound,text)
        names={node.id for node in ast.walk(fn) if isinstance(node,ast.Name)}
        self.assertFalse(names & {'dev','dev_indices','model','backbone','validation'})
        objective=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='objective');self.assertIn('.001*head.weight.square().mean()',ast.get_source_segment(source,objective))

    def test_200_update_protocol_with_standins(self):
        from contextlib import nullcontext
        from types import SimpleNamespace as NS
        from unittest.mock import patch
        events=[]
        class Scalar(float):
            def __add__(self,other):return Scalar(float(self)+float(other))
            def backward(self):events.append('backward')
            def detach(self):return self
        class Parameter:
            def __init__(self,n):self.n=n
            def numel(self):return self.n
            def zero_(self):events.append(('zero',self.n))
        class Head:
            def __init__(self,a,b,**kw):assert (a,b)==(3072,5);self.weight=Parameter(a*b);self.bias=Parameter(b)
            def parameters(self):return [self.weight,self.bias]
        class Adam:
            def __init__(self,params,**kw):
                self.params=list(params);assert sum(p.numel() for p in self.params)==15365
                assert kw==dict(lr=.01,betas=(.9,.999),eps=1e-8,weight_decay=0)
            def zero_grad(self,**kw):assert kw==dict(set_to_none=True)
            def step(self):events.append('step')
        fake=NS(float32='FP32',manual_seed=lambda n:events.append(('seed',n)),nn=NS(Linear=Head),optim=NS(Adam=Adam),no_grad=nullcontext,isfinite=lambda v:NS(item=lambda:True))
        x=NS(shape=(240,3072),dtype='FP32',device='fake');y=NS(shape=(240,),bincount=lambda **kw:NS(tolist=lambda:[48]*5));steps=[]
        with patch.object(c,'objective',return_value=(Scalar(1.6094379124341003),Scalar(0))):
            c.train_head(fake,x,y,lambda step,*_:steps.append(step))
        self.assertEqual(steps,list(range(201)));self.assertEqual(events.count('step'),200);self.assertEqual(events.count('backward'),200)

    def test_provider_watchdog_with_standins(self):
        from unittest.mock import patch
        import auditor_linear_cloud as cloud
        writes=[];terminated=[]
        def read_fake(path):
            return dict(watchdog_deadline_seconds=3180,hourly_rate=1.29) if path.name=='manifest.json' else dict(epoch=100,instance_id='test-instance')
        with patch.object(cloud,'read',side_effect=read_fake),patch.object(cloud,'write',side_effect=lambda n,v:writes.append((n,v))),patch.object(cloud,'LambdaExperiment',return_value=object()),patch.object(cloud.time,'time',return_value=3280),patch.object(cloud,'termination',side_effect=lambda *args:terminated.append(args) or True):
            cloud.watch()
        self.assertEqual(len(terminated),1);self.assertEqual(writes[0][1]['deadline_epoch'],3280)

    def test_feature_position_and_frozen_forward(self):
        # A synthetic decoder stand-in checks indexing/cache/grad behavior; no model.
        import numpy as np
        from contextlib import contextmanager
        class Tensor:
            def __init__(self,value):self.value=np.asarray(value)
            def __getitem__(self,key):return Tensor(self.value[key])
            def detach(self):return self
            def float(self):return self
            def cpu(self):return self
            def numpy(self):return self.value
        class Torch:
            long='long';grad=True
            @contextmanager
            def inference_mode(self):
                self.grad=False
                try:yield
                finally:self.grad=True
            def tensor(self,value,**kwargs):return Tensor(value)
            def ones_like(self,value):return Tensor(np.ones_like(value.value))
            def is_grad_enabled(self):return self.grad
        torch=Torch()
        class Decoder:
            def __call__(self,**kw):
                assert kw['use_cache'] is False and kw['output_hidden_states'] is False and not torch.is_grad_enabled()
                out=type('Output',(),{})();out.last_hidden_state=Tensor(np.arange(3*3072,dtype=np.float32).reshape(1,3,3072));return out
        class Fake:
            training=False;device='cpu'
            def parameters(self):return []
            def get_base_model(self):return type('Base',(),{'model':Decoder()})()
        value=c.final_feature(torch,Fake(),[1,2,3]);self.assertEqual(value.shape,(3072,));self.assertEqual(value[0],6144)

    def test_durability_and_watchdog_static(self):
        source=(ROOT/'tools/auditor_linear_remote.py').read_text(encoding='utf8');ast.parse(source)
        self.assertLess(source.index("append(phase+'.jsonl',raw)"),source.index('scored=dict(raw,metrics=r.score'))
        self.assertIn("time.time()<budget['workload_deadline_epoch']",source)
        self.assertIn('os.kill(pid,signal.SIGTERM)',source)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    BASE.mkdir(exist_ok=True);write_json(BASE/'local_checks.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,alias_rows=300,prefix_rows=60,model_generation=False,experiment_training=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
