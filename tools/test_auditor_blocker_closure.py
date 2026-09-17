"""CPU-only tests. No cloud or real-model execution."""
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
import auditor_blocker_support as s
from prepare_auditor_blocker_closure import generate_arm,generate_helper,ROOT,PAYLOAD

class ParityTests(unittest.TestCase):
 def check_bad(self,value,why):
  with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as folder:
   path=Path(folder)/'failure.json'
   def persist(reason):s.write(path,dict(reason=reason))
   with self.assertRaises(s.Divergence):s.compare(np,value,np.ones(3072,dtype=np.float32),10,persist)
   self.assertEqual(s.read(path)['reason'],why)
 def test_exact_passes_without_capture(self):
  value=np.ones(3072,dtype=np.float32)
  self.assertIs(s.compare(np,value,value.copy(),0,lambda _:self.fail('capture on success')),value)
 def test_finite_drift_fails(self):
  value=np.ones(3072,dtype=np.float32);value[0]=np.nextafter(value[0],np.float32(2))
  self.check_bad(value,'historical_bitwise_mismatch')
 def test_shape_fails(self):self.check_bad(np.ones((1,3072),dtype=np.float32),'wrong_vector_shape')
 def test_nonfinite_fails(self):
  for bad in (np.nan,np.inf,-np.inf):
   value=np.ones(3072,dtype=np.float32);value[0]=bad
   self.check_bad(value,'nonfinite_vector')
 def test_dtype_and_signed_zero_are_bitwise(self):
  self.check_bad(np.ones(3072,dtype=np.float64),'historical_bitwise_mismatch')
  a=np.zeros(3072,dtype=np.float32);b=a.copy();b[0]=-0.
  self.assertEqual(s.reason(np,a,b),'historical_bitwise_mismatch')
 def test_evidence_io_failure_stops(self):
  def broken(_):raise OSError('synthetic I/O failure')
  with self.assertRaises(OSError):s.compare(np,np.zeros(3072,dtype=np.float32),np.ones(3072,dtype=np.float32),0,broken)
 def test_neutralize_fail_restore_pass(self):
  stream=io.StringIO()
  with patch.object(s,'reason',return_value=None):
   failed=unittest.TextTestRunner(stream=stream).run(unittest.TestSuite([ParityTests('test_finite_drift_fails')]))
  restored=unittest.TextTestRunner(stream=stream).run(unittest.TestSuite([ParityTests('test_finite_drift_fails')]))
  self.assertFalse(failed.wasSuccessful());self.assertTrue(restored.wasSuccessful())
  s.write(ROOT/'docs/fix/auditor_blocker_closure_run/neutralize_restore.json',dict(scope='diagnostic comparator only, not a production fix',neutralized_test_failed=True,restored_test_passed=True))

class ProtocolTests(unittest.TestCase):
 def test_unauthorized_refused_before_runtime(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as folder:
   root=Path(folder);s.write(root/'diagnostic_authorization.json',dict(operator_authorized=False));s.write(root/'execution_manifest.json',{})
   with self.assertRaisesRegex(RuntimeError,'Separate operator authorization'):s.authorize(root)
 def test_outcomes(self):
  for a,b,want in [('DIVERGES','MATCHES',s.OUTCOMES[0]),('DIVERGES','DIVERGES',s.OUTCOMES[1]),('MATCHES','DIVERGES',s.OUTCOMES[2]),('MATCHES','MATCHES',s.OUTCOMES[3])]:
   self.assertEqual(s.outcome(dict(status=a,process=dict(pid=1)),dict(status=b,process=dict(pid=2))),want)
  self.assertEqual(s.outcome(None,None),s.OUTCOMES[-1])
  self.assertEqual(s.outcome(dict(status='MATCHES',process=dict(pid=1)),dict(status='MATCHES',process=dict(pid=1))),s.OUTCOMES[-1])
 def test_two_sequential_subprocesses_and_no_resume(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as folder:
   root=Path(folder);calls=[]
   def child(argv,**kw):
    arm=argv[-1];calls.append(arm);s.write(root/'evidence'/arm/'result.json',dict(status='MATCHES',process=dict(pid=len(calls))))
    return types.SimpleNamespace(returncode=0)
   with patch.object(s,'authorize',return_value=dict(workload_deadline_epoch=s.time.time()+500)),patch.object(s.subprocess,'run',side_effect=child):
    s.run(root)
    with self.assertRaises(FileExistsError):s.run(root)
   self.assertEqual(calls,['O','D'])
 def test_incomplete_o_prevents_d(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as folder:
   with patch.object(s,'authorize',return_value=dict(workload_deadline_epoch=s.time.time()+500)),patch.object(s.subprocess,'run',return_value=types.SimpleNamespace(returncode=1)) as child:
    with self.assertRaises(RuntimeError):s.run(Path(folder))
    self.assertEqual(child.call_count,1)
   self.assertEqual(s.read(Path(folder)/'evidence/result.json')['outcome'],s.OUTCOMES[-1])
 def test_cloud_refused_before_provider(self):
  import auditor_blocker_closure_cloud as cloud
  read=cloud.read
  def local_read(path):
   if Path(path).name=='LOCAL_GATES.json':return dict(passed=True,execution_manifest_sha256=s.sha(cloud.BASE/'execution_manifest.json'))
   return read(path)
  with patch.object(cloud,'read',side_effect=local_read),patch.object(cloud,'git',return_value=b''),patch.object(cloud,'LambdaExperiment') as provider:
   with self.assertRaisesRegex(Exception,'Separate operator authorization'):cloud.execute()
   provider.assert_not_called()
 def test_analyzer_refuses_without_teardown(self):
  import analyze_auditor_blocker_closure as analyzer
  with self.assertRaisesRegex(RuntimeError,'Teardown verification required'):analyzer.analyze()
 def test_generated_code_bounds_and_shared_loader(self):
  original=(ROOT/'docs/fix/auditor_final_run/downloaded/tools/auditor_final_remote.py').read_text()
  code=generate_arm(original)
  import ast
  old={n.name:ast.dump(n) for n in ast.parse(original).body if isinstance(n,ast.FunctionDef)}
  new={n.name:ast.dump(n) for n in ast.parse(code).body if isinstance(n,ast.FunctionDef)}
  for name in ['scope','runtime','load_base']:self.assertEqual(old[name],new[name])
  self.assertNotIn('evaluation',new);self.assertNotIn('training',new)
  self.assertIn('rows[:32]',code);self.assertIn('shape=(1792,3072)',code)
  for forbidden in ['current.normalize(', 'fit_head(', '.backward(', '.new_optimizer(', '.step(']:self.assertNotIn(forbidden,code)

class TorchProxy:
 def __init__(self):
  self.nn=types.SimpleNamespace(Linear=lambda *a,**kw:torch.nn.Linear(*a,**dict(kw,device='cpu')))
 def __getattr__(self,name):return getattr(torch,name)
 def tensor(self,*a,**kw):return torch.tensor(*a,**dict(kw,device='cpu'))
 def autocast(self,device,*a,**kw):return torch.autocast('cpu',*a,**kw)

class FakeModel(torch.nn.Module):
 def __init__(self,bad=None,shape=False):super().__init__();self.weight=torch.nn.Parameter(torch.ones(1),requires_grad=False);self.calls=[];self.bad=bad;self.shape=shape
 @property
 def model(self):return self
 def get_base_model(self):return self
 def forward(self,input_ids,**kwargs):
  self.calls.append(torch.is_inference(input_ids));value=torch.ones((1,input_ids.shape[1],3072))
  if len(self.calls)==self.bad:
   if self.shape:value=torch.ones((1,input_ids.shape[1],3))
   else:value[0,-1,0]=2
  return types.SimpleNamespace(last_hidden_state=value)

class GeneratedArmTests(unittest.TestCase):
 def run_arm(self,arm,bad=None,shape=False):
  import auditor_classifier_lora_fork as fork
  import auditor_classifier_lora_current_core as current
  import auditor_classifier_lora_stable as stable
  import auditor_final_core as f
  import auditor_classifier_lora_core as c
  with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as folder:
   root=Path(folder);(root/'closure_payload').mkdir();np.save(root/'closure_payload/historical32.npy',np.ones((32,3072),dtype=np.float32))
   spec=importlib.util.spec_from_file_location('synthetic_arm',PAYLOAD/'tools/auditor_blocker_arm.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   helper_spec=importlib.util.spec_from_file_location('auditor_blocker_helper',PAYLOAD/'tools/auditor_blocker_helper.py');helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)
   module.ROOT=root;module.D=root/'adapter';module.OUT=root/'evidence'/arm;module.OUT.mkdir(parents=True)
   model=FakeModel(bad,shape);proxy=TorchProxy();rows=[dict(split='train',example_id=str(i),input_ids=[1,2]) for i in range(32)]
   module.runtime=lambda:(rows,dict(base_state_sha256='synthetic'),{},proxy,np);module.load_base=lambda *_:model;module.Budget.check=lambda *_:None
   peft=types.ModuleType('peft');peft.PeftModel=types.SimpleNamespace(from_pretrained=lambda *a,**k:model)
   safetensors=types.ModuleType('safetensors.torch');safetensors.save_file=lambda *a,**k:None
   class Boundary:
    receipt=dict(successful_access_counts={},denied_before_open=0)
    def __init__(self,*a):pass
    def install(self):pass
   def digest(path):return fork.CONFIG_SHA if Path(path).suffix=='.json' else fork.SOURCE_SHA
   with patch.dict(sys.modules,{'peft':peft,'safetensors.torch':safetensors,'auditor_blocker_helper':helper}),patch.object(f,'Boundary',Boundary),patch.object(c,'sha',side_effect=digest),patch.object(fork,'inventory',return_value={}),patch.object(current,'verify_adapter'),patch.object(stable,'FrozenAudit',return_value=types.SimpleNamespace(initial_hash='synthetic')),patch.object(helper,'model_state',return_value={}):
    module.execute(arm)
   result=s.read(module.OUT/'result.json')
   if bad:
    self.assertEqual(result['status'],'DIVERGES');self.assertEqual(len(model.calls),bad);self.assertEqual(result['matched_rows'],bad-1)
    evidence=s.read(module.OUT/'first_divergence/boundary.json');self.assertEqual(evidence['row_one_based'],bad)
    if not (arm=='D' and shape):self.assertTrue((module.OUT/'first_divergence/vector.npy').exists())
    else:self.assertTrue((module.OUT/'first_divergence/raw_hidden.pt').exists())
    features=np.load(module.OUT/'train_features.npy');self.assertTrue(np.array_equal(features[bad-1],np.zeros(3072)))
   else:self.assertEqual(result['status'],'MATCHES');self.assertEqual(len(model.calls),32)
   self.assertEqual(model.calls,[arm=='O']*len(model.calls))
   self.assertFalse((module.OUT/'normalization.json').exists());self.assertFalse((module.OUT/'optimizer_initial.json').exists())
 def test_o_matches_32(self):self.run_arm('O')
 def test_d_matches_32(self):self.run_arm('D')
 def test_o_first_finite_drift_stops(self):self.run_arm('O',11)
 def test_d_first_finite_drift_stops(self):self.run_arm('D',11)
 def test_o_wrong_shape_stops(self):self.run_arm('O',2,True)
 def test_d_wrong_shape_stops(self):self.run_arm('D',2,True)

if __name__=='__main__':unittest.main()
