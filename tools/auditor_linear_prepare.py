"""Package reviewed linear-probe code/data/one frozen adapter, never provision."""
import hashlib,json,subprocess,sys,zipfile
from pathlib import Path
from cloud_run_common import require,credential_locations,write_json
from auditor_linear_cloud import git
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/fix/auditor_linear_probe_run';D=ROOT/'tuning/auditor_linear_probe'
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prepare():
    require(not (BASE/'LAUNCH_INTENT.json').exists(),'Authorization already consumed')
    run=subprocess.run([sys.executable,'-B','tools/auditor_linear_local.py'],capture_output=True)
    require(not credential_locations(run.stdout+run.stderr,'local checks'),'Credential diagnostic withheld')
    (BASE/'local_checks.log').write_bytes(run.stdout+run.stderr);require(run.returncode==0,'Local tests failed')
    require(read(BASE/'instances.json')==[],'Existing instances')
    choices=[x for x in read(BASE/'instance-types.json') if x['metadata']['type']=='gpu_1x_a10' and x['architecture']=='x86_64' and x['regions']]
    require(len(choices)==1,'NO_GO: suitable A10 unavailable')
    choice=choices[0];rate=choice['metadata']['hourly_rate'];region='us-east-1' if 'us-east-1' in choice['regions'] else choice['regions'][0]
    image=next(x for x in read(BASE/'images.json') if x['region']==region and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    spec=read(D/'experiment.json');projected=600+300+70*(spec['max_reason_allowance']+16)/6+60+300
    require(projected<3300 and projected-300<3000 and 3300*rate/3600<3,'NO_GO: exact experiment cannot reasonably fit time/cost')
    permit=dict(action='auditor-linear-head-only',operator_authorized=True,design_commit=spec['design_commit'],updates=200,trainable_parameters=15365,maximum_instances=1,hard_budget_usd=3,soft_budget_usd=1.5,
        provider='https://cloud.lambda.ai',backbone_updates=False,lora_updates=False,producer_execution=False,protected_access=False,workload_seconds=3000,termination_seconds=3300,
        request_attachment='9f0ba690-8742-4328-9662-7a330e3321db',binding_sha256=sha(D/'binding.json'))
    names=['tools/auditor_linear_remote.py','tools/auditor_linear_core.py','tuning/second_domain_agnostic_v2/runtime.py','tuning/first_domain_agnostic_v1/common.py','tuning/first_domain_agnostic_v1/dependency_lock.json',
        'scripts/compact_contracts.py','scripts/bounded_extraction.py','scripts/pairing_map.py','scripts/finding_record.py','scripts/localization.py',
        'benchmark/producer_coverage_amendment_v3/semantics.py','benchmark/producer_coverage_amendment_v3/structural.py','benchmark/task_semantics/core.py',
        'tuning/second_tuning_eval_runtime_v2_1/telemetry_worker.py','tuning/auditor_canonical_execution/eval_runtime.py','tuning/auditor_canonical_execution/config_state.py']
    names += [p.relative_to(ROOT).as_posix() for p in sorted(D.iterdir()) if p.is_file()]
    head=git('rev-parse','HEAD').decode().strip();require(all(x.startswith('?? ') for x in git('status','--short').decode().splitlines()),'Commit reviewed source before bundling')
    blobs={}
    for name in names:
        value=(ROOT/name).read_bytes();require(not credential_locations(value,name),'Credential in bundle')
        require(value.replace(b'\r\n',b'\n')==git('show',head+':'+name).replace(b'\r\n',b'\n'),'Uncommitted source '+name);blobs[name]=value
    old=ROOT/'docs/fix/auditor_canonical_tuning_run/downloaded/evidence/checkpoint-120'
    for name,digest in spec['adapter_hashes'].items():
        require(sha(old/name)==digest,'Historical adapter identity changed');blobs['adapter/'+name]=(old/name).read_bytes()
    blobs['environment.json']=(json.dumps(read(ROOT/'tuning/first_domain_agnostic_v1/experiment.json')['environment'],indent=2)+'\n').encode()
    manifest=dict(source_commit=head,design_commit=spec['design_commit'],files={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()},auditor_rows=300,train=240,dev=60,
        producer_payloads=0,protected_files=0,frozen_auditor_adapters=1,credentials=0,folds_1_to_4=0)
    blobs['execution_manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    with zipfile.ZipFile(BASE/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,value in blobs.items():z.writestr(name,value)
    write_json(BASE/'execution_manifest.json',manifest);write_json(BASE/'training_authorization.json',permit)
    cloud=dict(source_commit=head,bundle_sha256=sha(BASE/'runtime_bundle.zip'),instance=choice['metadata'],region=region,image=image,hourly_rate=rate,
        soft_usd=1.5,hard_usd=3,reserve_seconds=300,soft_seconds=1.5/rate*3600,hard_seconds=3/rate*3600,workload_deadline_seconds=3000,
        watchdog_deadline_seconds=3180,termination_deadline_seconds=3300,projected_seconds_with_reserve=projected,projected_cost=projected*rate/3600,
        minute50_cost=3000*rate/3600,minute55_cost=3300*rate/3600,name='shimmer-auditor-linear-probe',
        projection_assumptions=dict(setup_seconds=600,features_seconds=300,head_and_checks_seconds=60,outputs=70,max_reason_tokens=spec['max_reason_allowance'],max_probe_tokens=16,model_tokens_per_second=6,cleanup_seconds=300))
    write_json(BASE/'manifest.json',cloud);write_json(BASE/'LOCAL_GATES.json',dict(passed=True,authorization=permit,source_commit=head,bundle=manifest))
    check=BASE/'bundle_check';check.mkdir(exist_ok=True)
    with zipfile.ZipFile(BASE/'runtime_bundle.zip') as z:z.extractall(check)
    write_json(check/'training_authorization.json',permit)
    run=subprocess.run([sys.executable,'-B','tools/auditor_linear_remote.py','scope'],cwd=check,capture_output=True)
    require(not credential_locations(run.stdout+run.stderr,'bundle check'),'Credential diagnostic withheld')
    (BASE/'bundle_check.log').write_bytes(run.stdout+run.stderr);require(run.returncode==0,'Packaged scope failed')
    write_json(BASE/'bundle_check_results.json',dict(passed=True,members=len(blobs)))
    print(json.dumps(cloud,indent=2))

if __name__=='__main__':prepare()
