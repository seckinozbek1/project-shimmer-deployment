"""No-model local gates and strictly allowlisted Producer V3 upload bundle."""
import hashlib,json,subprocess,sys,zipfile
from pathlib import Path
from cloud_run_common import require,credential_locations,write_json
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/fix/producer_tuning_v3_run';V3=ROOT/'tuning/producer_v3'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(*args):
    require(not credential_locations(subprocess.run(['git','diff','--cached','--no-ext-diff'],capture_output=True,check=True).stdout,'staged diff'),'Possible staged credential; stop')
    return subprocess.run(['git',*args],capture_output=True,check=True).stdout
def run_checks():
    for label,script in [('release_before','tuning/producer_v3/release.py'),('dry_run','tuning/producer_v3/dry_run.py'),('leakage','tuning/producer_v3/leakage.py'),('release_after','tuning/producer_v3/release.py'),('integration','tools/producer_v3_checks.py')]:
        result=subprocess.run([sys.executable,'-B',script],capture_output=True)
        require(not credential_locations(result.stdout+result.stderr,label),'Possible credential diagnostic; withheld')
        (BASE/(label+'.log')).write_bytes(result.stdout+result.stderr);require(result.returncode==0,'Local gate failed: '+label)
def prepare():
    BASE.mkdir(exist_ok=True);require(not (BASE/'LAUNCH_INTENT.json').exists(),'One-instance authorization already consumed')
    run_checks()
    require(sha(V3/'freeze.json')=='68afb77a9a5ff7c9360075c2699e6cb1d4cc57e1828728496a6648c49a3b7850','Frozen V3 changed')
    require(sha(V3/'dataset.json')=='b036707820a1851e94432319cc340cafec10a1b6093fab39b573cc4a47b9ecf0','Wrong authorized dataset')
    require(read(BASE/'instances.json')==[],'Existing instances')
    choices=[x for x in read(BASE/'instance-types.json') if x['metadata']['type']=='gpu_1x_a10' and x['architecture']=='x86_64' and x['regions']]
    require(len(choices)==1,'NO_GO: no suitable A10; do not substitute')
    choice=choices[0];rate=choice['metadata']['hourly_rate'];region='us-east-1' if 'us-east-1' in choice['regions'] else choice['regions'][0]
    image=next(x for x in read(BASE/'images.json') if x['region']==region and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    projected=read(V3/'projection.json')['conservative_seconds'];require(projected*rate/3600<6,'Conservative experiment cannot fit hard ceiling')
    scope=dict(experiment='producer-targeted-v3.0',action='producer-v3-fresh-training',operator_authorized=True,role='producer',split='canonical',
        v3_freeze_sha256=sha(V3/'freeze.json'),dataset_sha256=sha(V3/'dataset.json'),runtime_release_sha256=sha(ROOT/'tuning/second_tuning_eval_runtime_v2_1/freeze.json'),
        maximum_instances=1,gpu_type='gpu_1x_a10',provider='https://cloud.lambda.ai',soft_budget_usd=3,hard_budget_usd=6,
        fresh_adapter=True,training=True,auditor=False,protected_access=False,checkpoint_steps=[84,168],updates=168,
        request_attachment='3022274b-cb22-4d6c-a0c0-3842d1ad0952')
    names=['tools/producer_v3_remote.py','tuning/second_domain_agnostic_v2/runtime.py','tuning/first_domain_agnostic_v1/common.py','tuning/first_domain_agnostic_v1/dependency_lock.json',
        'scripts/compact_contracts.py','scripts/bounded_extraction.py','scripts/pairing_map.py','scripts/finding_record.py','scripts/localization.py',
        'benchmark/producer_coverage_amendment_v3/semantics.py','benchmark/producer_coverage_amendment_v3/structural.py','benchmark/task_semantics/core.py']
    names+=['tuning/producer_v3/'+n for n in ('freeze.json','dataset.json','split.json','experiment.json','execution_plan.json','evaluation_protocol.json','prepared_dev.json','runtime_binding.py','selection.py')]
    names+=['tuning/second_tuning_eval_runtime_v2_1/'+n for n in ('freeze.json','eval_runtime.py','config_state.py','telemetry_worker.py')]
    head=git('rev-parse','HEAD').decode().strip();require(all(x.startswith('?? ') for x in git('status','--short').decode().splitlines()),'Commit tested tracked changes before packaging')
    blobs={}
    for name in names:
        data=(ROOT/name).read_bytes();require(not credential_locations(data,name),'Possible credential in bundle')
        require(data.replace(b'\r\n',b'\n')==git('show',head+':'+name).replace(b'\r\n',b'\n'),'Uncommitted source '+name)
        blobs[name]=data
    blobs['environment.json']=(json.dumps(read(ROOT/'tuning/first_domain_agnostic_v1/experiment.json')['environment'],indent=2)+'\n').encode()
    m=dict(source_commit=head,v3_freeze_sha256=scope['v3_freeze_sha256'],runtime_release_sha256=scope['runtime_release_sha256'],files={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()},
        producer_rows=420,train=336,dev=84,auditor_files=0,protected_files=0,old_adapters=0,credentials=0)
    blobs['execution_manifest.json']=(json.dumps(m,indent=2)+'\n').encode()
    with zipfile.ZipFile(BASE/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,data in blobs.items():z.writestr(name,data)
    write_json(BASE/'execution_manifest.json',m);write_json(BASE/'training_authorization.json',scope)
    manifest=dict(source_commit=head,release_sha256=scope['v3_freeze_sha256'],bundle_sha256=sha(BASE/'runtime_bundle.zip'),
        instance=choice['metadata'],region=region,image=image,hourly_rate=rate,soft_usd=3,hard_usd=6,reserve_seconds=600,
        soft_seconds=3/rate*3600,hard_seconds=6/rate*3600,workload_deadline_seconds=6/rate*3600-600,
        watchdog_deadline_seconds=6/rate*3600-60,projected_seconds_with_reserve=projected,projected_cost=projected*rate/3600,name='shimmer-producer-v3')
    write_json(BASE/'manifest.json',manifest);write_json(BASE/'LOCAL_GATES.json',dict(passed=True,authorization=scope,source_commit=head,bundle=m))
    # Extract and execute only scope validation in the actual packaged tree.
    check=BASE/'bundle_check';check.mkdir(exist_ok=True)
    with zipfile.ZipFile(BASE/'runtime_bundle.zip') as z:z.extractall(check)
    write_json(check/'training_authorization.json',scope)
    code="import sys;sys.path.insert(0,'tools');import producer_v3_remote as m;m.scope();print('Packaged 420 rows,168 updates,84 DEV and pinned source scope passed')"
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=check,capture_output=True)
    require(not credential_locations(result.stdout+result.stderr,'bundle check'),'Possible credential diagnostic')
    (BASE/'bundle_check.log').write_bytes(result.stdout+result.stderr);require(result.returncode==0,'Packaged scope failed')
    write_json(BASE/'bundle_check_results.json',dict(passed=True,members=len(blobs)))
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':prepare()
