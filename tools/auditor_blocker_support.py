"""Diagnostic-only parity and post-boundary capture. No training entry point."""
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from cloud_run_common import credential_locations

ACTION='auditor-blocker-closure-two-process-only'
OUTCOMES=('O_DIVERGES_D_MATCHES','BOTH_DIVERGE','O_MATCHES_D_DIVERGES','BOTH_MATCH_THROUGH_32','REMOTE_DIAGNOSTIC_INCOMPLETE')
ENV_NAMES=('USE_TORCH','HF_HUB_DISABLE_TELEMETRY','CUDA_LAUNCH_BLOCKING','PYTHONPATH','LD_LIBRARY_PATH','LD_PRELOAD','PYTHONHASHSEED','CUBLAS_WORKSPACE_CONFIG','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','TOKENIZERS_PARALLELISM','CUDA_VISIBLE_DEVICES','CUDA_MODULE_LOADING','PYTORCH_CUDA_ALLOC_CONF','PYTORCH_ALLOC_CONF','NVIDIA_TF32_OVERRIDE','CUDNN_DETERMINISTIC','OMP_NUM_THREADS','MKL_NUM_THREADS')

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()

def read(path):return json.loads(Path(path).read_bytes())

def write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 data=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
 hits=credential_locations(data,str(path))
 if hits:raise RuntimeError('WARNING: Possible API key detected in '+str(path)+'. Do not push. Rotate the key immediately.')
 with path.open('wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())

def require(value,message):
 if not value:raise RuntimeError(message)

def authorize(root):
 root=Path(root);p=read(root/'diagnostic_authorization.json');m=read(root/'execution_manifest.json')
 require(p.get('operator_authorized') is True and p.get('action')==ACTION,'Separate operator authorization required; diagnostic only')
 require(p['execution_manifest_sha256']==sha(root/'execution_manifest.json'),'Permit identity')
 require(p['instances']==1 and p['region']=='us-east-1' and p['soft_usd']==1 and p['hard_usd']==2 and p['hourly_rate']==1.29,'One A10/caps')
 require(p['optimizer_updates']==0 and p['arms']==['O','D'] and p['max_rows_per_arm']==32,'Bounded two arms')
 require(0<p['launch_epoch']<p['workload_deadline_epoch']<=p['launch_epoch']+2/p['hourly_rate']*3600-900,'Budget reserve')
 require(time.time()<p['workload_deadline_epoch'],'Expired permit')
 for name,digest in m['files'].items():
  path=(root/name).resolve();require(path.is_relative_to(root.resolve()) and sha(path)==digest,'Payload identity: '+name)
 return p

class Divergence(RuntimeError):
 def __init__(self,index,reason):self.index=index;self.reason=reason;super().__init__(reason)

def reason(np,vector,expected):
 if vector is None or vector.shape!=(3072,):return 'wrong_vector_shape'
 if not np.isfinite(vector).all():return 'nonfinite_vector'
 if vector.dtype!=expected.dtype or vector.tobytes()!=expected.tobytes():return 'historical_bitwise_mismatch'
 return None

def compare(np,vector,expected,index,persist):
 """CPU-only immediate comparison; persist before refusal. Never return a replacement."""
 why=reason(np,vector,expected)
 if why:
  persist(why)
  raise Divergence(index,why)
 return vector

def process_identity():
 value=dict(pid=os.getpid(),ppid=os.getppid(),executable=sys.executable,cwd=os.getcwd(),python=platform.python_version(),observed_epoch=time.time())
 if Path('/proc/self/stat').exists():value['linux_start_ticks']=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
 return value

def command(argv):
 try:
  r=subprocess.run(argv,capture_output=True,text=True,timeout=15)
  value=dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
  require(not credential_locations(json.dumps(value).encode(),'boundary command'),'Possible credential detected; output withheld')
  return value
 except (OSError,subprocess.TimeoutExpired) as exc:return dict(unavailable=type(exc).__name__)

def capture(root,out,torch,np,model,row,index,raw,hidden,vector,ids,mask,why,expected):
 """Called only after a bad boundary. Minimal evidence survives optional probe failure."""
 import auditor_feature_diagnostics as d
 out=Path(out)/'first_divergence';out.mkdir(exist_ok=False)
 record=dict(row_one_based=index+1,index=index,example_id=row['example_id'],reason=why,capture_complete=False,process=process_identity(),token_sha256=d.digest(row['input_ids']),expected_feature_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),errors={})
 write(out/'boundary.json',record)
 if vector is not None:
  with (out/'vector.npy').open('wb') as stream:np.save(stream,vector,allow_pickle=False);stream.flush();os.fsync(stream.fileno())
  record['vector_sha256']=sha(out/'vector.npy');write(out/'boundary.json',record)
 def attempt(name,fn):
  try:record[name]=fn()
  except Exception as exc:record['errors'][name]=type(exc).__name__
  write(out/'boundary.json',record)
 def save_tensor(name,value):
  if value is None:return None
  target=out/(name+'.pt')
  with target.open('wb') as stream:torch.save(value.detach().cpu(),stream);stream.flush();os.fsync(stream.fileno())
  return dict(path=target.name,sha256=sha(target),summary=d.tensor_summary(torch,value))
 attempt('raw_hidden',lambda:save_tensor('raw_hidden',raw))
 attempt('pooled',lambda:d.tensor_summary(torch,hidden))
 attempt('vector',lambda:d.tensor_summary(torch,torch.from_numpy(vector)) if vector is not None else None)
 attempt('input',lambda:dict(shape=list(ids.shape),dtype=str(ids.dtype),device=str(ids.device),sha256=d.digest(ids.cpu().tolist())))
 attempt('mask',lambda:dict(shape=list(mask.shape),dtype=str(mask.dtype),device=str(mask.device),sha256=d.digest(mask.cpu().tolist())))
 attempt('model',lambda:d.model_state(torch,model))
 attempt('runtime',lambda:d.runtime_state(torch))
 attempt('torch_build',lambda:torch.__config__.show())
 attempt('python_rng_sha256',lambda:hashlib.sha256(repr(__import__('random').getstate()).encode()).hexdigest())
 attempt('environment',lambda:{name:os.environ.get(name) for name in ENV_NAMES})
 attempt('numpy_rng_sha256',lambda:hashlib.sha256(np.random.get_state()[1].tobytes()).hexdigest())
 def tensors():
  parameters={};buffers={};saved={}
  for name,value in model.named_parameters():
   cpu=value.detach().cpu().contiguous();parameters[name]=dict(shape=list(value.shape),dtype=str(value.dtype),device=str(value.device),sha256=hashlib.sha256(cpu.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest())
  modules=dict(model.named_modules())
  for name,value in model.named_buffers():
   parent,_,leaf=name.rpartition('.');cpu=value.detach().cpu().contiguous();saved[name]=cpu
   buffers[name]=dict(persistent=leaf not in modules[parent]._non_persistent_buffers_set,shape=list(value.shape),dtype=str(value.dtype),device=str(value.device),sha256=hashlib.sha256(cpu.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest())
  with (out/'buffers.pt').open('wb') as stream:torch.save(saved,stream);stream.flush();os.fsync(stream.fileno())
  write(out/'parameter_hashes.json',parameters);write(out/'buffers.json',buffers)
  return dict(parameters=len(parameters),buffers=len(buffers),buffers_sha256=sha(out/'buffers.pt'),parameter_hashes_sha256=sha(out/'parameter_hashes.json'))
 attempt('tensor_inventory',tensors)
 def origins():
  roots=('torch','transformers','peft','bitsandbytes','accelerate','numpy','safetensors','auditor_')
  return {name:dict(file=getattr(module,'__file__',None),origin=getattr(getattr(module,'__spec__',None),'origin',None)) for name,module in sorted(sys.modules.items()) if name.startswith(roots)}
 attempt('module_origins',origins)
 def libraries():
  maps=Path('/proc/self/maps').read_text();selected=sorted({line.split()[-1] for line in maps.splitlines() if '/' in line and '.so' in line})
  return dict(files={path:sha(path) for path in selected if Path(path).is_file()},maps=[line for line in maps.splitlines() if '.so' in line])
 attempt('loaded_libraries',libraries)
 attempt('allocator',lambda:torch.cuda.memory_summary())
 attempt('driver',lambda:Path('/proc/driver/nvidia/version').read_text())
 attempt('device_health',lambda:command(['nvidia-smi','-q','-d','ECC,PAGE_RETIREMENT,ROW_REMAPPER']))
 def faults():
  value=command(['dmesg','--color=never']);value['stdout']='\n'.join(line for line in value.get('stdout','').splitlines() if 'NVRM' in line or 'Xid' in line);return value
 attempt('device_faults',faults)
 record['capture_complete']=not record['errors'];write(out/'boundary.json',record)

def admit(root,out,torch,np,model,row,index,raw,hidden,vector,ids,mask,expected):
 def persist(why):capture(root,out,torch,np,model,row,index,raw,hidden,vector,ids,mask,why,expected)
 if raw is not None and tuple(raw.shape)!=(1,len(row['input_ids']),3072):
  persist('wrong_raw_shape');raise Divergence(index,'wrong_raw_shape')
 return compare(np,vector,expected,index,persist)

def budget_check(self,phase,remaining=None):
 p=self.permit;now=time.time();good=not self.stopped and now+120<p['workload_deadline_epoch']
 root=Path(__file__).resolve().parents[1]
 write(root/'evidence'/os.environ['AUDITOR_CLOSURE_ARM']/'progress.json',dict(epoch=now,phase=phase,updates=0,feature_rows=self.features,continue_run=good,estimated_usd=(now-p['launch_epoch'])*p['hourly_rate']/3600))
 require(good,'Diagnostic budget/resource stop; no retry')

def outcome(o,d):
 if not o or not d or o.get('status') not in ('MATCHES','DIVERGES') or d.get('status') not in ('MATCHES','DIVERGES'):return OUTCOMES[-1]
 if o['process']['pid']==d['process']['pid']:return OUTCOMES[-1]
 return {('DIVERGES','MATCHES'):OUTCOMES[0],('DIVERGES','DIVERGES'):OUTCOMES[1],('MATCHES','DIVERGES'):OUTCOMES[2],('MATCHES','MATCHES'):OUTCOMES[3]}[(o['status'],d['status'])]

def run(root):
 root=Path(root);authorize(root);out=root/'evidence';out.mkdir(exist_ok=True)
 with (out/'TWO_ARMS_ATTEMPTED').open('x') as stream:stream.write('One O then one D; no resume/retry.\n')
 results={}
 try:
  for arm in ('O','D'):
   p=authorize(root);require(time.time()+120<p['workload_deadline_epoch'],'Insufficient remaining budget')
   env=dict(os.environ,AUDITOR_CLOSURE_ARM=arm)
   with (out/(arm+'.log')).open('wb') as stream:
    child=subprocess.run([sys.executable,'-B','-u',str(root/'tools/auditor_blocker_arm.py'),arm],cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=max(1,p['workload_deadline_epoch']-time.time()))
   path=out/arm/'result.json';results[arm]=read(path) if path.exists() else None
   require(child.returncode==0 and results[arm] and results[arm]['status'] in ('MATCHES','DIVERGES'),'Incomplete arm; no further forwards')
 finally:write(out/'result.json',dict(outcome=outcome(results.get('O'),results.get('D')),arms=results,optimizer_updates=0,finished_epoch=time.time()))

def preflight(root):
 root=Path(root);authorize(root);contract=read(root/'tuning/auditor_final/runtime_contract.json')
 require(sys.platform=='linux' and platform.python_version()==contract['python'],'Pinned platform')
 for name,value in contract['packages'].items():require(importlib.metadata.version(name)==value,'Pinned package '+name)
 import torch
 require(torch.cuda.device_count()==1 and torch.cuda.get_device_name()=='NVIDIA A10' and torch.cuda.get_device_properties(0).total_memory>=22*2**30,'One A10 24GB')
 require(torch.version.cuda==contract['cuda_runtime'] and torch.cuda.is_bf16_supported(),'CUDA/BF16')
 write(root/'evidence/preflight.json',dict(passed=True,packages=contract['packages'],forwards=0))

def acquire(root):
 root=Path(root);preflight(root);contract=read(root/'tuning/auditor_final/runtime_contract.json')
 from huggingface_hub import snapshot_download
 hashes=dict(contract['asset_hashes'],**{'model.safetensors':contract['base_weight_sha256']})
 path=Path(snapshot_download(contract['model_id'],revision=contract['revision'],allow_patterns=list(hashes),local_dir=root/'base_model'))
 for name,digest in hashes.items():require(sha(path/name)==digest,'Base acquisition identity')
 write(root/'evidence/acquisition.json',dict(files=hashes,forwards=0))

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['preflight','acquire','run']);args=parser.parse_args()
 globals()[args.action](Path(__file__).resolve().parents[1])
