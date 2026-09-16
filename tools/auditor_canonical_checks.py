"""Offline integration tests; no model import, optimizer construction or provider."""
import ast,json,math,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tuning/auditor_canonical_execution'));import eval_runtime as ev
SOURCE=ROOT/'tools/auditor_canonical_remote.py';TREE=ast.parse(SOURCE.read_text())
node=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='per_pass_speed');ns={'math':math};exec(compile(ast.Module(body=[node],type_ignores=[]),'<speed gate>','exec'),ns)
class Checks(unittest.TestCase):
    def test_each_pass_not_combined(self):
        slow=[dict(output_tokens=10,generation_seconds=3)]*5;fast=[dict(output_tokens=100,generation_seconds=3)]*5
        with self.assertRaises(AssertionError):ns['per_pass_speed'](slow,fast,4.438538339317307)
        self.assertEqual(ns['per_pass_speed'](fast,fast,4.438538339317307),[100/3,100/3])
        for bad in (0.,float('nan'),float('inf')):
            with self.assertRaises(AssertionError):ns['per_pass_speed']([dict(output_tokens=10,generation_seconds=bad)]*5,fast,4.4)
    def test_frozen_schedule(self):
        p=json.loads((ROOT/'tuning/auditor_canonical_execution/execution_plan.json').read_text());s=json.loads((ROOT/'tuning/auditor_canonical_execution/split.json').read_text())
        from collections import Counter
        self.assertEqual([x['step'] for x in p['optimizer_schedule']],list(range(1,121)))
        self.assertEqual(Counter(i for u in p['optimizer_schedule'] for i in u['example_ids']),Counter({i:2 for i in s['train']}))
        self.assertFalse(set(s['train'])&set(s['validation']))
        self.assertEqual(p['checkpoint_steps'],[60,120])
    def test_no_old_adapter_or_ambient_trace(self):
        calls=[ast.unparse(n.func) for n in ast.walk(TREE) if isinstance(n,ast.Call)]
        for forbidden in ('sys.settrace','sys.setprofile','set_peft_model_state_dict','model.load_adapter','PeftModel.from_pretrained'):
            self.assertNotIn(forbidden,calls)
        self.assertEqual(calls.count('get_peft_model'),1)
        self.assertEqual(calls.count('torch.optim.AdamW'),1)
        self.assertEqual(calls.count('opt.step'),1)
        self.assertEqual(calls.count('scheduler.step'),1)
    def test_checkpoint_restore_order(self):
        execute=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
        evaluate=next(n for n in execute.body if isinstance(n,ast.FunctionDef) and n.name=='evaluate')
        text=ast.unparse(evaluate)
        self.assertLess(text.index('ev.real_runtime_context_preflight'),text.index("run('cache_1'"))
        self.assertLess(text.index("assert len(results) == 60"),text.index('restore_rng(saved_rng)'))
        self.assertLess(text.index('assert before == after'),text.index('ev._PREFLIGHTS.pop(model)'))
        self.assertIn('digest_state(rng()) == rng_before',text)
    def test_state_restoration_without_generation(self):
        from types import SimpleNamespace
        from contextlib import contextmanager
        class Model:
            def __init__(self):self.training=True;self.config=SimpleNamespace(use_cache=False);self.generation_config=None;self.active_adapters=['default'];self.p=SimpleNamespace(dtype='float32',device='cpu',requires_grad=True,_version=0,grad=None)
            def modules(self):return [self]
            def parameters(self):return [self.p]
            def eval(self):self.training=False
        class Torch:
            @staticmethod
            @contextmanager
            def inference_mode():yield
            @staticmethod
            def is_grad_enabled():return False
        m=Model();self.assertTrue(ev.real_runtime_context_preflight(m,Torch)['passed']);self.assertTrue(m.training);self.assertIsNone(m.generation_config)
        with self.assertRaises(ValueError):ev.real_runtime_context_preflight(m,Torch)
        ev._PREFLIGHTS.pop(m);self.assertTrue(ev.real_runtime_context_preflight(m,Torch)['passed'])
    def test_sources_compile(self):
        for name in ('remote','prepare','cloud'):
            p=ROOT/f'tools/auditor_canonical_{name}.py';compile(p.read_text(),str(p),'exec')
    def test_producer_and_wrong_cap_rejected(self):
        from copy import deepcopy
        d=ROOT/'tuning/auditor_canonical_execution'
        protocol=json.loads((d/'evaluation_protocol.json').read_text());records=json.loads((d/'prepared_dev.json').read_text())
        ev.validate_records(records,protocol)
        changed=deepcopy(records);changed[0]['role']='producer'
        with self.assertRaises(ValueError):ev.validate_records(changed,protocol)
        changed=deepcopy(protocol);changed['generation_kwargs']['max_new_tokens']=288
        with self.assertRaises(ValueError):ev.validate_generation(changed['generation_kwargs'],changed)
        calls=[ast.unparse(n.func) for n in ast.walk(ast.parse((d/'eval_runtime.py').read_text())) if isinstance(n,ast.Call)]
        self.assertNotIn('sys.settrace',calls);self.assertNotIn('sys.setprofile',calls)
    def test_scoped_state_mechanism_unchanged(self):
        original=ast.parse((ROOT/'tuning/second_tuning_eval_runtime_v2_1/eval_runtime.py').read_text())
        adapted=ast.parse((ROOT/'tuning/auditor_canonical_execution/eval_runtime.py').read_text())
        def node(tree,name):
            n=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            if isinstance(n.body[0],ast.Expr) and isinstance(n.body[0].value,ast.Constant):n.body=n.body[1:]
            return ast.dump(n)
        for name in ('evaluation_state','real_runtime_context_preflight','parameter_state','cache_probe','cache_effect_gate'):
            self.assertEqual(node(original,name),node(adapted,name),name)
        self.assertEqual((ROOT/'tuning/second_tuning_eval_runtime_v2_1/config_state.py').read_bytes(),(ROOT/'tuning/auditor_canonical_execution/config_state.py').read_bytes())
    def test_duplicate_control_mismatch_rejected(self):
        from copy import deepcopy
        from binding import control_gate
        d=ROOT/'tuning/auditor_canonical_execution';p=json.loads((d/'evaluation_protocol.json').read_text());adapter={'step':60}
        values=[dict(example_id=i,adapter=adapter,checkpoint=60,role='auditor',generation_seconds=1.,prompt='p',input_ids=[1],attention_mask=[1],output_token_ids=[2],raw_output='x',raw_output_with_special_tokens='x',metrics={'contract':True},stop_reason='eos') for i in p['control_ids']]
        self.assertTrue(control_gate(values,deepcopy(values),p,adapter,60)['passed'])
        altered=deepcopy(values);altered[0]['output_token_ids']=[3]
        with self.assertRaises(AssertionError):control_gate(values,altered,p,adapter,60)
if __name__=='__main__':unittest.main(verbosity=2)
