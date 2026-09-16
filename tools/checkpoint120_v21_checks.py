"""No-model tests of the new controller-to-frozen-preflight integration."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
RT=ROOT/'tuning/second_tuning_eval_runtime_v2_1'
sys.path.insert(0,str(RT))
import eval_runtime as ev
import remote_preflight
# Load the historical stand-ins without running its tests or touching weights.
spec=importlib.util.spec_from_file_location('historical_standins',ROOT/'tuning/second_tuning_eval_runtime_v2/checks.py')
standins=importlib.util.module_from_spec(spec);spec.loader.exec_module(standins)

class IntegrationChecks(unittest.TestCase):
    def session(self):
        p=json.loads((RT/'protocol.json').read_text())
        permit=dict(operator_authorized=True,experiment=p['name'],action='producer-checkpoint120-evaluation-only',role='producer',split='canonical',checkpoint=120,runtime_release_sha256='integration-test-only',protocol_sha256=ev.digest(p),adapter_sha256=p['adapter']['files']['adapter_model.safetensors'])
        return ev.EvaluationSession(permit,p,'integration-test-only')

    def block(self):
        source=ast.parse((ROOT/'tools/checkpoint120_v21_remote.py').read_text())
        execute=next(x for x in source.body if isinstance(x,ast.FunctionDef) and x.name=='execute')
        block=next(x for x in execute.body if isinstance(x,ast.Try) and any(isinstance(n,ast.Call) and ast.unparse(n.func)=='remote_preflight.run' for n in ast.walk(x)))
        trace=next(x for x in execute.body if isinstance(x,ast.Assign) and isinstance(x.value,ast.Call) and ast.unparse(x.value.func)=='audit.historical_trace_callback')
        self.assertLess(block.lineno,trace.lineno)
        return compile(ast.fix_missing_locations(ast.Module(body=[block],type_ignores=[])),'<actual-remote-context-handoff>','exec')

    def test_context_before_cache_success(self):
        model=standins.Model();model.child.generation_config=None;events=[]
        exec(self.block(),dict(session=self.session(),model=model,torch=standins.TorchFacade(),remote_preflight=remote_preflight,write=lambda n,v:events.append((n,v))))
        self.assertEqual(events[0][0],'REAL_RUNTIME_CONTEXT_PREFLIGHT.json');self.assertTrue(events[0][1]['passed'])
        self.assertEqual(model.calls,[]);ev.require_context_preflight(model)

    def test_context_failure_no_go_teardown(self):
        model=standins.Model();model.config.unsupported=set();events=[]
        with self.assertRaises(TypeError):exec(self.block(),dict(session=self.session(),model=model,torch=standins.TorchFacade(),remote_preflight=remote_preflight,write=lambda n,v:events.append((n,v))))
        self.assertEqual([n for n,v in events],['REAL_RUNTIME_CONTEXT_PREFLIGHT.json','TEARDOWN_REQUIRED.json','status.json'])
        self.assertEqual(events[-1][1]['status'],'CHECKPOINT120_EVALUATION_NO_GO');self.assertEqual(model.calls,[])

    def test_sources_compile_and_no_training_calls(self):
        for p in (ROOT/'tools').glob('checkpoint120_v21_*.py'):compile(p.read_text(),str(p),'exec')
        tree=ast.parse((ROOT/'tools/checkpoint120_v21_remote.py').read_text())
        calls=[ast.unparse(x.func) for x in ast.walk(tree) if isinstance(x,ast.Call)]
        self.assertFalse(any(x in ('model.train','torch.optim.AdamW','torch.optim.Optimizer','model.merge_and_unload') for x in calls))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IntegrationChecks))
    raise SystemExit(not result.wasSuccessful())
