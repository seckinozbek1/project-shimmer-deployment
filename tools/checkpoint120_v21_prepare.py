"""Local pre-provision gates and allowlisted Producer-only deployment bundle."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from cloud_run_common import credential_locations, require, write_json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/producer_checkpoint120_eval_v2_1'
RT=ROOT/'tuning/second_tuning_eval_runtime_v2_1'
OLD=ROOT/'tuning/second_tuning_eval_runtime_v2'
sys.path.insert(0,str(RT))
import eval_runtime as ev
import release
sys.path.append(str(OLD))
import protocol_builder as pb

def read(p):return json.loads(Path(p).read_text())
def sha(p):return pb.filehash(p)
def git(*args):
    require(not credential_locations(subprocess.run(['git','diff','--cached','--no-ext-diff'],capture_output=True,check=True).stdout,'staged diff'),'Possible staged credential; stop')
    return subprocess.run(['git',*args],capture_output=True,check=True).stdout
def prepare():
    require(not (BASE/'LAUNCH_INTENT.json').exists(),'Authorization already consumed')
    proof=release.verify()
    require(proof['release_sha256']=='8d1fd41d1ab059e47b1297c1c39cd29711acd8fa5446a60780f9a97faef1d1fa','Wrong authorized V2.1 freeze')
    tests=subprocess.run([sys.executable,'-B',str(RT/'checks.py')],capture_output=True)
    require(not credential_locations(tests.stdout+tests.stderr,'local tests'),'Possible credential; stop')
    (BASE/'runtime_tests.log').write_bytes(tests.stdout+tests.stderr)
    require(tests.returncode==0,'Runtime tests failed');release.verify()
    protocol=read(RT/'protocol.json');records=read(OLD/'prepared_dev.json')
    # Fresh tokenizer-only proof; do not regenerate frozen evidence files.
    # Tokenization is done by a dedicated subprocess with its restrictive boundary.
    code="import sys,json;from pathlib import Path;sys.path.insert(0,'tuning/second_tuning_eval_runtime_v2');import protocol_builder as p;from boundary import install;install(p.ROOT);_,rows=p.tokenize();assert rows==p.frozen.read(p.HERE/'prepared_dev.json');print('60 exact prompt/token identities')"
    tokencheck=subprocess.run([sys.executable,'-B','-c',code],capture_output=True)
    require(tokencheck.returncode==0,'Guarded tokenizer dry-run failed')
    ev.validate_records(records,protocol)
    rows=pb.producer_rows();require([x['example_id'] for x in rows]==protocol['dev_ids'],'Wrong DEV order')
    adapter=ROOT/'docs/fix/second_tuning_canonical_pilot/downloaded/runs/second-domain-agnostic-v2/canonical/producer/checkpoint-120'
    for name,value in protocol['adapter']['files'].items():require(sha(adapter/name)==value,'Adapter changed')
    scope=dict(experiment='second-tuning-eval-runtime-v2_1',action='producer-checkpoint120-evaluation-only',operator_authorized=True,
        role='producer',split='canonical',checkpoint=120,runtime_release_sha256=proof['release_sha256'],
        protocol_sha256=ev.digest(protocol),adapter_sha256=protocol['adapter']['files']['adapter_model.safetensors'],
        protected_access=False,training=False,auditor=False,maximum_instances=1,soft_budget_usd=2.5,hard_budget_usd=3,
        request_attachment='9ec2056f-90b3-4950-b45b-e7915a487b60',historical_permits_reused=False)
    ev.authorize(scope,protocol,proof['release_sha256'])
    require(read(BASE/'instances.json')==[],'Existing cloud instances')
    choices=[x for x in read(BASE/'instance-types.json') if x['architecture']=='x86_64' and x['regions'] and x['metadata']['type'] in ('gpu_1x_a10','gpu_1x_a6000','gpu_1x_a100','gpu_1x_a100_sxm4','gpu_1x_h100_pcie','gpu_1x_h100_sxm5')]
    require(choices,'No suitable capacity');choice=min(choices,key=lambda x:x['metadata']['hourly_rate'])
    rate=choice['metadata']['hourly_rate'];region='us-east-1' if 'us-east-1' in choice['regions'] else choice['regions'][0]
    image=next(x for x in read(BASE/'images.json') if x['region']==region and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    projected=6619.7109;require(projected*rate/3600<3,'Cannot fit budget')
    names=['tools/checkpoint120_v21_remote.py','tools/second_tuning_remote.py',
        'tuning/second_domain_agnostic_v2/runtime.py','tuning/second_domain_agnostic_v2/freeze.json','tuning/second_domain_agnostic_v2/producer/experiment.json',
        'tuning/first_domain_agnostic_v1/common.py','tuning/first_domain_agnostic_v1/dependency_lock.json','tuning/first_domain_agnostic_v1/experiment.json','tuning/first_domain_agnostic_v1/producer/experiment.json',
        'scripts/compact_contracts.py','scripts/bounded_extraction.py','scripts/pairing_map.py','scripts/finding_record.py','scripts/localization.py',
        'benchmark/producer_coverage_amendment_v3/semantics.py','benchmark/producer_coverage_amendment_v3/structural.py','benchmark/task_semantics/core.py']
    names+=['tuning/second_tuning_eval_runtime_v2/'+n for n in ('audit.py','prepared_dev.json','freeze.json')]
    names+=['tuning/second_tuning_eval_runtime_v2_1/'+n for n in ('eval_runtime.py','config_state.py','remote_preflight.py','telemetry_worker.py','protocol.json','freeze.json')]
    head=git('rev-parse','HEAD').decode().strip()
    status=git('status','--short').decode();require(all(x.startswith('?? ') for x in status.splitlines()),'Tracked changes must be committed')
    blobs={}
    for name in names:
        data=(ROOT/name).read_bytes();require(not credential_locations(data,name),'Possible credential in source; stop')
        committed=git('show',head+':'+name)
        require(data.replace(b'\r\n',b'\n')==committed.replace(b'\r\n',b'\n'),'Uncommitted source: '+name)
        blobs[name]=data
    blobs['producer_dev.json']=(json.dumps(rows,indent=2)+'\n').encode()
    for name in protocol['adapter']['files']:blobs['adapter/'+name]=(adapter/name).read_bytes()
    execution=dict(source_commit=head,runtime_release_sha256=proof['release_sha256'],files={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()},
        protected_files=0,auditor_files=0,training_executors=0,full_release_verified_locally=True)
    blobs['execution_manifest.json']=(json.dumps(execution,indent=2)+'\n').encode()
    with zipfile.ZipFile(BASE/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in blobs.items():archive.writestr(name,data)
    write_json(BASE/'execution_manifest.json',execution);write_json(BASE/'evaluation_authorization.json',scope)
    manifest=dict(source_commit=head,release_sha256=proof['release_sha256'],bundle_sha256=sha(BASE/'runtime_bundle.zip'),
        instance=choice['metadata'],region=region,image=image,hourly_rate=rate,soft_usd=2.5,hard_usd=3,reserve_seconds=600,
        soft_seconds=2.5/rate*3600,hard_seconds=3/rate*3600,workload_deadline_seconds=3/rate*3600-600,
        watchdog_deadline_seconds=3/rate*3600-60,projected_seconds_with_reserve=projected,projected_cost=projected*rate/3600,name='shimmer-checkpoint120-v21')
    write_json(BASE/'manifest.json',manifest)
    write_json(BASE/'LOCAL_GATES.json',dict(passed=True,runtime=proof,tests=read(RT/'test_results.json'),exact_prompt_token_identities=60,adapter_verified=True,
        authorization=scope,bundle=execution,protected_paths_denied=True,auditor_paths_denied=True,model_generations=0))
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':prepare()
