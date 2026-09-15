"""Minimal remote preparation, explicitly separate from inference."""
import json,sys,subprocess,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'evidence';OUT.mkdir(exist_ok=True)
data={'started_epoch':time.time(),'steps':[]}
def save(): (OUT/'setup.json').write_text(json.dumps(data,indent=2))
def run(label,args,timeout):
    begin=time.time()
    with (OUT/(label+'.log')).open('w') as log:
        p=subprocess.run(args,stdout=log,stderr=log,timeout=timeout)
    data['steps'].append(dict(label=label,start_epoch=begin,seconds=time.time()-begin,returncode=p.returncode));save()
    if p.returncode:raise RuntimeError(label+' failed')
save()
run('readiness',['bash','-c','nvidia-smi; lscpu; free -b; df -B1 .; python3 --version; python3 -m pip list'],30)
run('venv',['python3','-m','venv','--system-site-packages','.venv'],30)
py=str(ROOT/'.venv/bin/python')
run('dependencies',[py,'-m','pip','install','transformers==4.52.3','tokenizers==0.21.4','accelerate==1.10.1','bitsandbytes==0.48.2','huggingface_hub==0.36.2','psutil','sentence-transformers==4.1.0'],600)
# Keep an existing compatible CUDA PyTorch; record its exact version. No new serving engine.
run('cuda_check',[py,'-c','import torch; assert torch.cuda.is_available(); print(torch.__version__,torch.version.cuda); print(torch.ones(1,device="cuda"))'],60)
script='''import json,time
from pathlib import Path
from huggingface_hub import snapshot_download
root=Path.cwd(); pins=json.loads((root/'models.json').read_text()); rows=[]
for model,revision in pins.items():
 if not model.startswith('unsloth/'):continue
 begin=time.time()
 try:snapshot_download(model,revision=revision,local_files_only=True); cached=True
 except Exception:cached=False
 path=snapshot_download(model,revision=revision,allow_patterns=['*.json','*.safetensors','tokenizer*','*.model','*.txt'],max_workers=4)
 ref=Path(path).parents[1]/'refs'/'main';ref.parent.mkdir(exist_ok=True);ref.write_text(revision)
 rows.append(dict(model=model,revision=revision,cache_present_before=cached,seconds=time.time()-begin,path=path))
 (root/'evidence/model_acquisition.json').write_text(json.dumps(rows,indent=2))
'''
run('model_acquisition',[py,'-c',script],900)
data['finished_epoch']=time.time();save()
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
run('bounded_probe',[py,'-u','probe.py'],700)
