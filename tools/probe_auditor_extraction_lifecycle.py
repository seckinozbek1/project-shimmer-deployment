"""Synthetic CPU tests of extraction lifetime and state-hash coverage, not CUDA causality."""
import sys,json
from types import SimpleNamespace
from pathlib import Path
import torch,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from auditor_feature_diagnostics import extract_train_vector
class Model:
 def __init__(self):self.model=self;self.previous=None;self.alive=[];self.ids_inference=[];self.refs=[]
 def get_base_model(self):return self
 def __call__(self,**kw):
  self.alive.append(False if self.previous is None else not torch.UntypedStorage._expired(self.previous))
  self.ids_inference.append(torch.is_inference(kw['input_ids']))
  raw=torch.arange(2*3072,dtype=torch.float32).reshape(1,2,3072)
  self.previous=raw.untyped_storage()._weak_ref();self.refs.append(self.previous)
  return SimpleNamespace(last_hidden_state=raw)
old=Model()
for i in range(2):
 with torch.inference_mode():
  ids=torch.tensor([[1,2]],dtype=torch.long)
  with torch.autocast('cpu',dtype=torch.bfloat16):hidden=old.get_base_model().model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,return_dict=True).last_hidden_state[0,-1]
  v=hidden.float().cpu().numpy().copy()
new=Model()
for i in range(2):w=extract_train_vector(torch,np,new,dict(split='train',input_ids=[1,2]),i,'cpu','unused.json')
from auditor_classifier_lora_stable import FrozenAudit
m=torch.nn.Sequential(torch.nn.Linear(2,2),torch.nn.Dropout(.05));m.register_buffer('unpersisted',torch.ones(2),persistent=False);m.requires_grad_(False);m.eval();audit=FrozenAudit(torch,m);m.train();m[1].p=.7;m.unpersisted.zero_()
r=dict(torch=torch.__version__,device='cpu',inline_prior_storage_alive_at_entry=old.alive,helper_prior_storage_alive_at_entry=new.alive,inline_input_inference=old.ids_inference,helper_input_inference=new.ids_inference,pooled_equal=bool(np.array_equal(v,w)),state_hash_unchanged_after_train_and_dropout_mutation=audit.hash()==audit.initial_hash,scope='Synthetic CPU model only; lifetime/hash coverage test, not a reproduction of CUDA failure.')
assert old.alive==[False,True] and new.alive==[False,False]
assert old.ids_inference==[True,True] and new.ids_inference==[False,False]
assert r['pooled_equal'] and r['state_hash_unchanged_after_train_and_dropout_mutation']
r['nonpersistent_buffer_mutation_also_undetected']=True
Path('docs/fix/auditor_failure_forensics/cpu_probe.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
for obj in [old,new]:
 for ref in obj.refs:torch.UntypedStorage._free_weak_ref(ref)
