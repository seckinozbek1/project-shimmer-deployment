"""Prepare a sealed, unapproved two-process diagnostic; no provider calls."""
import ast
import hashlib
import json
import zipfile
from pathlib import Path
from cloud_run_common import credential_locations
import auditor_blocker_support as s

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/auditor_blocker_closure_run'
PAYLOAD=ROOT/'.tmp/auditor_blocker_closure_payload'
FAILED=ROOT/'docs/fix/auditor_final_run'


def replace_function(source,name,new):
 node=next(n for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
 lines=source.splitlines(keepends=True);return ''.join(lines[:node.lineno-1])+new+'\n'+''.join(lines[node.end_lineno:])


def generate_arm(original):
 prefix=original[:original.index('def training():')]
 prefix=replace_function(prefix,'authorize','def authorize():\n    return closure.authorize(ROOT)')
 # Keep original constructor/signal state; the remaining-work estimate must fit a diagnostic, not 896 updates.
 prefix+='\nimport auditor_blocker_support as closure\nBudget.check=closure.budget_check\n\n'
 start=original[original.index('def training():'):original.index('        begin=time.perf_counter()')]
 start=start.replace('def training():','def execute(arm):').replace("OUT/'TRAINING_ATTEMPTED'","OUT/'ARM_ATTEMPTED'").replace('One authorized final attempt; no resume/retry.','One diagnostic arm; no resume/retry.')
 start=start.replace('    try:\n','    result=dict(arm=arm,status="INCOMPLETE",forwards=0,matched_rows=0,optimizer_updates=0,process=closure.process_identity())\n    try:\n',1)
 loop='''        prior=np.load(ROOT/'closure_payload/historical32.npy',allow_pickle=False)
        f.require(prior.shape==(32,3072) and prior.dtype==np.float32 and np.isfinite(prior).all(),'Bound historical prefix')
        begin=time.perf_counter()
        for i,row in enumerate(rows[:32]):
            budget.check('fresh_train_features')
            raw=mask=vector=None
            result['forwards']=i+1
            if arm=='O':
                try:
                    with torch.inference_mode():
                        ids=torch.tensor([row['input_ids']],device='cuda',dtype=torch.long)
                        with torch.autocast('cuda',dtype=torch.bfloat16):
                            raw=model.get_base_model().model(input_ids=ids,attention_mask=(mask:=torch.ones_like(ids)),use_cache=False,return_dict=True).last_hidden_state
                            hidden=raw[0,-1]
                        vector=hidden.float().cpu().numpy().copy()
                except Exception:
                    why='wrong_raw_shape' if raw is not None and tuple(raw.shape)!=(1,len(row['input_ids']),3072) else 'forward_or_index_exception'
                    closure.capture(ROOT,OUT,torch,np,model,row,i,raw,None,vector,ids if raw is not None else None,mask,why,prior[i])
                    if why=='wrong_raw_shape':raise closure.Divergence(i,why)
                    raise
                closure.admit(ROOT,OUT,torch,np,model,row,i,raw,hidden,vector,ids,mask,prior[i])
            else:
                import auditor_blocker_helper as helper
                def boundary_callback(raw,hidden,vector,ids,mask,failure):
                    if failure and failure.startswith('forward_or_extraction_exception:'):
                        closure.capture(ROOT,OUT,torch,np,model,row,i,raw,hidden,vector,ids,mask,failure,prior[i])
                        return
                    closure.admit(ROOT,OUT,torch,np,model,row,i,raw,hidden,vector,ids,mask,prior[i])
                vector=helper.extract_train_vector(torch,np,model,row,i,'cuda',OUT/f'row-{i+1:02d}.json',record_success=True,boundary_callback=boundary_callback)
            f.require(vector.shape==(3072,) and np.isfinite(vector).all(),'finite TRAIN hidden')
            features[i]=vector;features.flush();budget.features=i+1
            emit(dict(event='feature',index=i,example_id=row['example_id'],token_sha256=fork.token_hash(row['input_ids']),feature_sha256=hashlib.sha256(vector.tobytes()).hexdigest(),norm=float(np.linalg.norm(vector.astype(np.float64)))))
            result['matched_rows']=i+1
            del raw,mask
        result['status']='MATCHES'
    except closure.Divergence as exc:
        result.update(status='DIVERGES',first_divergence_index=exc.index,reason=exc.reason)
    except Exception as exc:
        result.update(status='INCOMPLETE',error_type=type(exc).__name__)
        raise
    finally:
        result['data_access']=boundary.receipt
        result['finished_epoch']=time.time()
        write('result.json',result)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('arm',choices=['O','D']);args=parser.parse_args()
    f.require(os.environ.get('AUDITOR_CLOSURE_ARM')==args.arm,'Supervisor arm identity')
    OUT=ROOT/'evidence'/args.arm
    execute(args.arm)
'''
 return prefix+start+loop


def generate_helper(original):
 old='diagnostic_path, record_success=False):'
 s.require(original.count(old)==1,'Helper signature unchanged')
 result=original.replace(old,'diagnostic_path, record_success=False, boundary_callback=None):')
 marker='    if failure or record_success:\n'
 s.require(result.count(marker)==1,'Helper callback boundary unchanged')
 return result.replace(marker,'    if boundary_callback is not None:\n        boundary_callback(raw, hidden, vector, ids, mask, failure)\n'+marker)


def prepare():
 import numpy as np
 BASE.mkdir(exist_ok=True);s.require(not (BASE/'LAUNCH_INTENT.json').exists(),'Attempt already consumed')
 s.require(not (BASE/'diagnostic_authorization.json').exists() or not s.read(BASE/'diagnostic_authorization.json').get('operator_authorized'),'Do not overwrite operator authorization')
 PAYLOAD.mkdir(exist_ok=True)
 original_manifest=s.read(FAILED/'execution_manifest.json');blobs={}
 with zipfile.ZipFile(FAILED/'runtime_bundle.zip') as archive:
  for name,digest in original_manifest['files'].items():
   value=archive.read(name);s.require(hashlib.sha256(value).hexdigest()==digest,'Failed payload identity '+name);blobs[name]=value
 original=blobs['tools/auditor_final_remote.py'].decode()
 blobs['tools/auditor_blocker_arm.py']=generate_arm(original).encode()
 source_files=['tools/auditor_blocker_support.py','tools/prepare_auditor_blocker_closure.py','tools/auditor_blocker_closure_cloud.py','tools/test_auditor_blocker_closure.py','tools/analyze_auditor_blocker_closure.py','tuning/first_domain_agnostic_v1/experiment.json','tools/auditor_feature_diagnostics.py','tools/cloud_run_common.py']
 for name in source_files:blobs[name]=(ROOT/name).read_bytes()
 blobs['tools/auditor_blocker_helper.py']=generate_helper(blobs['tools/auditor_feature_diagnostics.py'].decode('utf-8-sig')).encode()
 rows=json.loads(blobs['tuning/auditor_final/records_train_only.json']);s.require(len(rows)==1792 and all(r['split']=='train' for r in rows),'Original TRAIN scope')
 historical=ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/downloaded/evidence/current_train_features.npy'
 s.require(s.sha(historical)=='06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287','Historical cache identity')
 receipts=[json.loads(line) for line in historical.with_suffix('.jsonl').read_bytes().splitlines()]
 prior=np.load(historical,mmap_mode='r',allow_pickle=False)[:32].copy()
 for i,row in enumerate(rows[:32]):
  s.require(receipts[i]['index']==i and receipts[i]['example_id']==row['example_id'] and receipts[i]['token_sha256']==hashlib.sha256(json.dumps(row['input_ids'],separators=(',',':')).encode()).hexdigest(),'Historical token identity')
  s.require(receipts[i]['feature_sha256']==hashlib.sha256(prior[i].tobytes()).hexdigest(),'Historical feature receipt')
 import io
 stream=io.BytesIO();np.save(stream,prior,allow_pickle=False);blobs['closure_payload/historical32.npy']=stream.getvalue()
 blobs['closure_payload/provenance.json']=(json.dumps(dict(historical_full_sha256=s.sha(historical),historical_receipts_sha256=s.sha(historical.with_suffix('.jsonl')),failed_source_commit=original_manifest['source_commit'],rows=32,receipts=receipts[:32]),indent=2)+'\n').encode()
 for name,value in blobs.items():
  path=PAYLOAD/name;s.require(path.resolve().is_relative_to(PAYLOAD.resolve()),'Payload path')
  if path.suffix not in ('.npy','.safetensors'):
   hits=credential_locations(value,name)
   if hits:raise RuntimeError('WARNING: Possible API key detected in '+name+':'+str(hits[0]['line'])+'. Do not push. Rotate the key immediately.')
  path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
 manifest=dict(baseline_commit='d0b218e',failed_source_commit=original_manifest['source_commit'],source_identity='content hashes; new diagnostic code is not attributed to baseline commit',files={name:hashlib.sha256(value).hexdigest() for name,value in sorted(blobs.items())},local_source_hashes={name:s.sha(ROOT/name) for name in source_files},arms=['O','D'],maximum_prefix_row=32,maximum_total_forwards=64,train_payload_rows=1792,optimizer_updates=0)
 s.write(BASE/'execution_manifest.json',manifest);s.write(PAYLOAD/'execution_manifest.json',manifest)
 with zipfile.ZipFile(BASE/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as archive:
  for name,value in sorted(dict(blobs,**{'execution_manifest.json':(PAYLOAD/'execution_manifest.json').read_bytes()}).items()):
   info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,value)
 image=s.read(FAILED/'manifest.json')['image'];rate=1.29;hard=2/rate*3600
 s.write(BASE/'manifest.json',dict(baseline_commit='d0b218e',bundle_sha256=s.sha(BASE/'runtime_bundle.zip'),execution_manifest_sha256=s.sha(BASE/'execution_manifest.json'),instance=dict(type='gpu_1x_a10'),image=image,region='us-east-1',hourly_rate=rate,rate_status='Historical cap; must reverify before provisioning',soft_usd=1,hard_usd=2,soft_seconds=1/rate*3600,hard_seconds=hard,workload_deadline_seconds=hard-900,watchdog_deadline_seconds=hard-180,termination_deadline_seconds=hard,reserve_seconds=900,name='shimmer-auditor-blocker-closure'))
 s.write(BASE/'diagnostic_authorization.json',dict(operator_authorized=False,action=s.ACTION,execution_manifest_sha256=s.sha(BASE/'execution_manifest.json'),instances=1,region='us-east-1',hourly_rate=rate,soft_usd=1,hard_usd=2,optimizer_updates=0,arms=['O','D'],max_rows_per_arm=32,launch_epoch=0,workload_deadline_epoch=0,request_attachment='af149acd-35f7-45a3-92aa-3ae863ec1c74'))
 for name in ('auditor_blocker_arm.py','auditor_blocker_helper.py'):(BASE/name).write_bytes(blobs['tools/'+name])
 s.write(BASE/'bundle_check_results.json',dict(passed=True,kind='offline payload/hash/AST generation only; CPU tests separately required',original_files_verified=len(original_manifest['files']),maximum_total_forwards=64,no_evaluation_payload=True,operator_authorized=False))
 print(json.dumps(dict(bundle_sha256=s.sha(BASE/'runtime_bundle.zip'),execution_manifest_sha256=s.sha(BASE/'execution_manifest.json'),operator_authorized=False)))

if __name__=='__main__':prepare()
