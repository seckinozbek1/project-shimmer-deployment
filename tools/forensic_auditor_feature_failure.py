"""Audit retained TRAIN evidence and source only; never execute a model/workload."""
import ast,hashlib,json,sys,zipfile,subprocess,re,tarfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def staged():
 # Never print staged contents. Scan before each subsequent Git operation.
 diff=subprocess.run(['git','diff','--cached','--no-ext-diff','--unified=0'],cwd=ROOT,capture_output=True,check=True).stdout.decode('utf-8','replace')
 patterns=[r'sk-ant-[A-Za-z0-9_-]{12,}',r'sk-(?:proj-)?[A-Za-z0-9_-]{20,}',r'AKIA[A-Z0-9]{16}',r'AIza[A-Za-z0-9_-]{35}',r'(?i)\b(?:api_key|secret|token|password|credential)\b[\"\x27]?\s*[=:]\s*[\"\x27]([^\"\x27\n]+)']
 for line_number,line in enumerate(diff.splitlines(),1):
  for pattern in patterns:
   match=re.search(pattern,line)
   if not match:continue
   value=match.group(1) if match.lastindex else match.group(0)
   if value in ('YOUR_KEY_HERE','fixture','placeholder') or value.isdigit() or re.fullmatch(r'[a-fA-F0-9]{40}|[a-fA-F0-9]{64}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}',value):continue
   raise SystemExit(f'WARNING: Possible API key detected in staged_diff:{line_number}. Do not push. Rotate the key immediately.')
OUT=ROOT/'docs/fix/auditor_failure_forensics';OUT.mkdir(exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
runs={k:ROOT/'docs/fix'/v for k,v in {'historical':'auditor_classifier_lora_current_runtime_run','failed':'auditor_final_run','remote':'auditor_feature_remote_run','hpo':'auditor_optuna_hpo_run'}.items()}
result={'scope':'Saved TRAIN arrays and Python source only; no model execution or evaluation data opened.','source':{}}
for name,root in runs.items():
 m=read(root/'execution_manifest.json');checks=[]
 with zipfile.ZipFile(root/'runtime_bundle.zip') as z:
  names=z.namelist()
  for p,h in m['files'].items():
   if not p.endswith('.py'):continue
   b=z.read(p);staged();git_result=subprocess.run(['git','show',m['source_commit']+':'+p],cwd=ROOT,capture_output=True)
   g=git_result.stdout if git_result.returncode==0 else None
   d=root/'downloaded'/p
   checks.append(dict(path=p,manifest_matches_bundle=sha(b)==h,git_present=g is not None,git_bytes_equal=b==g,git_normalized_equal=g is not None and b.replace(b'\r\n',b'\n')==g.replace(b'\r\n',b'\n'),git_ast_equal=g is not None and ast.dump(ast.parse(b))==ast.dump(ast.parse(g)),downloaded_present=d.exists(),downloaded_matches=d.exists() and sha(d.read_bytes())==h))
  result['source'][name]=dict(commit=m['source_commit'],checks=checks,bundle_pyc=[p for p in names if p.endswith('.pyc')])
  assert all(x['manifest_matches_bundle'] and (x['git_ast_equal'] or not x['git_present']) and (not x['downloaded_present'] or x['downloaded_matches']) for x in checks)
runtime_inventory={}
for name,root in runs.items():
 libs={}
 archive_hash=sha((root/'evidence.tar.gz').read_bytes())
 assert archive_hash==read(root/'collection_integrity.json')['sha256']
 for path in root.glob('*install.log'):
  for line in path.read_text(errors='replace').splitlines():
   if line.startswith('Successfully installed '):
    for item in line[len('Successfully installed '):].split():
     if item.startswith(('nvidia-','torch-','triton-','bitsandbytes-')):
      key,value=item.rsplit('-',1);libs[key]=value
 with tarfile.open(root/'evidence.tar.gz','r:gz') as archive:
  pycs=[entry for entry in archive.getnames() if entry.endswith('.pyc')]
  archived=set(archive.getnames())
  for check in result['source'][name]['checks']:
   path=check['path'];check['archive_present']=path in archived
   check['archive_matches']=path in archived and sha(archive.extractfile(path).read())==read(root/'execution_manifest.json')['files'][path]
   assert not check['archive_present'] or check['archive_matches']
 runtime_inventory[name]=dict(archive_sha256=archive_hash,archive_collection_hash_verified=True,install_reported_native_packages=libs,archive_pyc=pycs)
(OUT/'runtime_inventory.json').write_text(json.dumps(runtime_inventory,indent=2)+'\n')
froot=runs['failed']/'downloaded/evidence';hroot=runs['historical']/'downloaded/evidence';rroot=runs['remote']/'downloaded/evidence'
f=np.load(froot/'train_features.npy',mmap_mode='r',allow_pickle=False)[:31].copy();h=np.load(hroot/'current_train_features.npy',mmap_mode='r',allow_pickle=False)
fmeta=[json.loads(s) for s in (froot/'events.jsonl').read_text().splitlines() if json.loads(s).get('event')=='feature'];hmeta=[json.loads(s) for s in (hroot/'current_train_features.jsonl').read_text().splitlines()]
rows=[]
train=read(ROOT/'tuning/auditor_final/records_train_only.json')
assert len(fmeta)==31 and sha((hroot/'current_train_features.npy').read_bytes())=='06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287'
for i in range(31):
 a=f[i].astype('float64');b=h[i].astype('float64');delta=a-b
 # Test pure output storage conversions, not internal arithmetic.
 bf=h[i].copy().view('uint32');bf=((bf+0x7fff+((bf>>16)&1))&0xffff0000).view('float32')
 rows.append(dict(row=i+1,receipt_verified=sha(f[i].tobytes())==fmeta[i]['feature_sha256'],historical_receipt_verified=sha(h[i].tobytes())==hmeta[i]['feature_sha256'],token_and_id_match=all(fmeta[i][k]==hmeta[i][k] for k in ['index','example_id','token_sha256']),bitwise=bool(np.array_equal(f[i],h[i])),different_coordinates=int(np.count_nonzero(delta)),max_abs=float(abs(delta).max()),rms=float(np.sqrt(np.mean(delta**2))),cosine=float(a@b/np.linalg.norm(a)/np.linalg.norm(b)),pure_fp16_cast_match=bool(np.array_equal(f[i],h[i].astype('float16').astype('float32'))),pure_bf16_cast_match=bool(np.array_equal(f[i],bf))))
result['failed_prefix']=rows
for i,row in enumerate(rows):
 row['sequence_length']=len(train[i]['input_ids'])
 row['train_payload_token_match']=sha(json.dumps(train[i]['input_ids'],separators=(',',':')).encode())==fmeta[i]['token_sha256']
 assert row['receipt_verified'] and row['historical_receipt_verified'] and row['token_and_id_match'] and row['train_payload_token_match']
result['remote_vectors']=[dict(file=p.name,bitwise_historical=bool(np.array_equal(np.load(p,allow_pickle=False),h[int(p.stem.split('row')[1])-1]))) for p in sorted(rroot.glob('*-row*.npy'))]
assert len(result['remote_vectors'])==38 and all(x['bitwise_historical'] for x in result['remote_vectors'])
result['local_overlap']=[]
local_receipt=read(ROOT/'docs/fix/auditor_feature_blocker/gpu_rows30_33/probe.json')
result['local_source']=[]
for name,digest in local_receipt['extraction_path']['files'].items():
 staged();blob=subprocess.run(['git','show','459d694:tools/'+name],cwd=ROOT,capture_output=True,check=True).stdout
 result['local_source'].append(dict(path='tools/'+name,receipt_matches_git=sha(blob)==digest))
assert all(x['receipt_matches_git'] for x in result['local_source'])
for i in [29,30]:
 l=np.load(ROOT/f'docs/fix/auditor_feature_blocker/gpu_rows30_33/row-{i+1}.npy');a=(f[i]-h[i]).astype('float64');b=(l-h[i]).astype('float64')
 result['local_overlap'].append(dict(row=i+1,failed_local_max_abs=float(abs(f[i]-l).max()),error_cosine=float(a@b/np.linalg.norm(a)/np.linalg.norm(b))))
(OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'source':{k:dict(files=len(v['checks']),all_ast_equal=all(x['git_ast_equal'] for x in v['checks']),all_bundle_match=all(x['manifest_matches_bundle'] for x in v['checks']),all_downloaded_match=all(x['downloaded_matches'] for x in v['checks'])) for k,v in result['source'].items()},'rows':rows,'remote_count':len(result['remote_vectors']),'remote_all_equal':all(x['bitwise_historical'] for x in result['remote_vectors']),'local':result['local_overlap']},indent=2))
