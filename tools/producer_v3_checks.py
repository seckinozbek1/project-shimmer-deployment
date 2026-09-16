"""Offline integration tests; no model import, optimizer construction or provider."""
import ast,json,math,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tuning/second_tuning_eval_runtime_v2_1'));import eval_runtime as ev
SOURCE=ROOT/'tools/producer_v3_remote.py';TREE=ast.parse(SOURCE.read_text())
node=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='per_pass_speed');ns={'math':math};exec(compile(ast.Module(body=[node],type_ignores=[]),'<speed gate>','exec'),ns)
class Checks(unittest.TestCase):
    def test_each_pass_not_combined(self):
        slow=[dict(output_tokens=10,generation_seconds=3)]*6;fast=[dict(output_tokens=100,generation_seconds=3)]*6
        with self.assertRaises(AssertionError):ns['per_pass_speed'](slow,fast,4.438538339317307)
        self.assertEqual(ns['per_pass_speed'](fast,fast,4.438538339317307),[100/3,100/3])
        for bad in (0.,float('nan'),float('inf')):
            with self.assertRaises(AssertionError):ns['per_pass_speed']([dict(output_tokens=10,generation_seconds=bad)]*6,fast,4.4)
    def test_frozen_schedule(self):
        p=json.loads((ROOT/'tuning/producer_v3/execution_plan.json').read_text());s=json.loads((ROOT/'tuning/producer_v3/split.json').read_text())
        from collections import Counter
        self.assertEqual([x['step'] for x in p['optimizer_schedule']],list(range(1,169)))
        self.assertEqual(Counter(i for u in p['optimizer_schedule'] for i in u['example_ids']),Counter({i:2 for i in s['train']}))
        self.assertFalse(set(s['train'])&set(s['validation']))
        self.assertEqual([x['checkpoint'] for x in p['checkpoints']],[84,168])
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
        self.assertLess(text.index("assert len(results) == 84"),text.index('restore_rng(saved_rng)'))
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
            p=ROOT/f'tools/producer_v3_{name}.py';compile(p.read_text(),str(p),'exec')
if __name__=='__main__':unittest.main(verbosity=2)
