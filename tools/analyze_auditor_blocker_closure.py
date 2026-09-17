"""Read-only interpretation after verified teardown. Never loads a model or .pt files."""
import json
import tarfile
from pathlib import Path
import numpy as np
import auditor_blocker_support as s
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/auditor_blocker_closure_run'


def cost_usd(elapsed_seconds, hourly_rate):
 s.require(elapsed_seconds>=0 and hourly_rate>=0,"Nonnegative cost inputs")
 return elapsed_seconds*hourly_rate/3600


def analyze():
 s.require((BASE/'TERMINATION_VERIFIED.json').exists(),'Teardown verification required')
 cleanup=s.read(BASE/'independent_inventory_confirmation.json')
 s.require(cleanup['instances']==[] and cleanup['temporary_ssh_registration_absent'] and cleanup['local_key_material_absent'],'Independent teardown incomplete')
 archive=BASE/'evidence.tar.gz';s.require(s.sha(archive)==s.read(BASE/'collection_integrity.json')['sha256'],'Archive identity')
 dest=BASE/'downloaded';dest.mkdir(exist_ok=True)
 with tarfile.open(archive,'r:gz') as tar:
  for member in tar.getmembers():
   path=(dest/member.name).resolve()
   s.require(path.is_relative_to(dest.resolve()) and (member.isfile() or member.isdir()),'Unsafe archive')
   s.require(member.name.split('/')[0] in ('evidence','tools','tuning','closure_payload','execution_manifest.json','diagnostic_authorization.json','budget.json'),'Unexpected archived scope')
   if member.isdir():path.mkdir(parents=True,exist_ok=True)
   else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(tar.extractfile(member).read())
 m=s.read(BASE/'execution_manifest.json');s.require(s.sha(dest/'execution_manifest.json')==s.sha(BASE/'execution_manifest.json'),'Executed manifest')
 for name,digest in m['files'].items():s.require(s.sha(dest/name)==digest,'Executed payload '+name)
 prior=np.load(dest/'closure_payload/historical32.npy',allow_pickle=False)
 rows=s.read(dest/'tuning/auditor_final/records_train_only.json');arms={};coverage={}
 for arm in ('O','D'):
  folder=dest/'evidence'/arm
  if not (folder/'result.json').exists():arms[arm]=None;continue
  r=s.read(folder/'result.json');arms[arm]=r
  if r['status'] not in ('MATCHES','DIVERGES'):continue
  n=r['matched_rows'];s.require(r['optimizer_updates']==0 and 0<=n<=32 and 1<=r['forwards']<=32,'Arm bounds')
  s.require(r['data_access']['denied_before_open']==0 and not any(r['data_access']['successful_access_counts'].values()),'Forbidden access')
  features=np.load(folder/'train_features.npy',mmap_mode='r',allow_pickle=False)
  s.require(features.shape==(1792,3072),'Original memmap allocation')
  events=[json.loads(line) for line in (folder/'events.jsonl').read_bytes().splitlines()] if (folder/'events.jsonl').exists() else []
  s.require(len(events)==n,'Matched receipts')
  for i,event in enumerate(events):
   s.require(event['index']==i and event['example_id']==rows[i]['example_id'],'Row order')
   s.require(event['feature_sha256']==s.hashlib.sha256(features[i].tobytes()).hexdigest() and features[i].tobytes()==prior[i].tobytes(),'Live historical parity')
  if r['status']=='MATCHES':s.require(n==r['forwards']==32,'Complete matching prefix')
  else:
   s.require(r['first_divergence_index']==n and r['forwards']==n+1,'First divergence bounds')
   boundary=s.read(folder/'first_divergence/boundary.json');s.require(boundary['index']==n and boundary['example_id']==rows[n]['example_id'],'Failure boundary identity')
   vector_path=folder/'first_divergence/vector.npy'
   if vector_path.exists():
    s.require(s.sha(vector_path)==boundary['vector_sha256'],'Failure vector identity')
    value=np.load(vector_path,allow_pickle=False);s.require(s.reason(np,value,prior[n]) is not None or boundary['reason']=='wrong_raw_shape','Genuine divergent vector')
   else:s.require(boundary['reason'] in ('wrong_raw_shape','forward_or_index_exception'),'Missing vector without raw failure')
   if boundary.get('raw_hidden'):s.require(s.sha(folder/'first_divergence'/boundary['raw_hidden']['path'])==boundary['raw_hidden']['sha256'],'Raw tensor retained')
   coverage[arm]=dict(capture_complete=boundary['capture_complete'],errors=boundary['errors'],row_one_based=n+1)
 outcome=s.outcome(arms.get('O'),arms.get('D'))
 if outcome!=s.OUTCOMES[-1]:
  s.require(arms['O']['finished_epoch']<=arms['D']['process']['observed_epoch'],'Sequential fresh processes')
  if any(not value['capture_complete'] for value in coverage.values()):outcome=s.OUTCOMES[-1]
 result=dict(outcome=outcome,arms=arms,capture_coverage=coverage,root_cause='ROOT_CAUSE_UNRESOLVED',safe_admission_boundary_established=False,training_authorized=False,estimated_cost_upper_bound_usd=cost_usd(cleanup['epoch']-s.read(BASE/'launch.json')['epoch'],s.read(BASE/'manifest.json')['hourly_rate']),interpretation='Evidence verified; causal analysis and any production safeguard require separate review. No automatic training.')
 s.write(BASE/'RECOMPUTED_RESULTS.json',result);print(json.dumps(dict(outcome=outcome,training_authorized=False)))

if __name__=='__main__':analyze()
