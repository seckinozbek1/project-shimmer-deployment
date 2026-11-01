"""Allowlisted Auditor-only bundle and budget-bound authorization; no cloud launch."""
import hashlib,json,subprocess,sys,zipfile
from pathlib import Path
from cloud_run_common import require,credential_locations,write_json
from auditor_canonical_local import build
from auditor_canonical_cloud import git
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/fix/auditor_canonical_tuning_run';D=ROOT/'tuning/auditor_canonical_execution'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepare():
    require(not (BASE/'LAUNCH_INTENT.json').exists(),'Authorization already consumed')
    build()
    result=subprocess.run([sys.executable,'-B','tools/auditor_canonical_checks.py'],capture_output=True)
    require(not credential_locations(result.stdout+result.stderr,'checks'),'Credential diagnostic withheld')
    (BASE/'integration.log').write_bytes(result.stdout+result.stderr);require(result.returncode==0,'Integration tests failed')
    require(read(BASE/'instances.json')==[],'Existing instances')
    choices=[x for x in read(BASE/'instance-types.json') if x['metadata']['type']=='gpu_1x_a10' and x['architecture']=='x86_64' and x['regions']]
    require(len(choices)==1,'NO_GO: suitable A10 unavailable')
    choice=choices[0];rate=choice['metadata']['hourly_rate'];region='us-east-1' if 'us-east-1' in choice['regions'] else choice['regions'][0]
    image=next(x for x in read(BASE/'images.json') if x['region']==region and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    # Bounds all 144 outputs at the unchanged 192-token cap. The rate is a
    # planning assumption, not a quality gate; measured budget checks fail closed.
    projected=900+120*10+144*192/6+600
    require(projected*rate/3600<3,'Frozen experiment cannot reasonably fit $3')
    scope=dict(experiment='auditor-canonical-v2',action='auditor-canonical-fresh-training',operator_authorized=True,role='auditor',split='canonical',
        execution_freeze_sha256=sha(D/'freeze.json'),source_release_sha256=read(D/'source_binding.json')['source_release_sha256'],dataset_sha256=read(D/'source_binding.json')['source_dataset_sha256'],
        maximum_instances=1,gpu_type='gpu_1x_a10',provider='https://cloud.lambda.ai',soft_budget_usd=1.5,hard_budget_usd=3,
        fresh_adapter=True,training=True,producer_execution=False,protected_access=False,full_pipeline=False,checkpoint_steps=[60,120],updates=120,
        request_attachment='ea56d7c9-febe-421d-9f5d-817905c15c81')
    names=['tools/auditor_canonical_remote.py','tuning/second_domain_agnostic_v2/runtime.py','tuning/first_domain_agnostic_v1/common.py','tuning/first_domain_agnostic_v1/dependency_lock.json',
        'scripts/compact_contracts.py','scripts/bounded_extraction.py','scripts/pairing_map.py','scripts/finding_record.py','scripts/localization.py',
        'benchmark/producer_coverage_amendment_v3/semantics.py','benchmark/producer_coverage_amendment_v3/structural.py','benchmark/task_semantics/core.py',
        'tuning/second_tuning_eval_runtime_v2_1/telemetry_worker.py']
    names += [p.relative_to(ROOT).as_posix() for p in sorted(D.iterdir()) if p.is_file()]
    head=git('rev-parse','HEAD').decode().strip();require(all(x.startswith('?? ') for x in git('status','--short').decode().splitlines()),'Commit reviewed source before bundling')
    blobs={}
    for name in names:
        value=(ROOT/name).read_bytes();require(not credential_locations(value,name),'Credential in bundle')
        require(value.replace(b'\r\n',b'\n')==git('show',head+':'+name).replace(b'\r\n',b'\n'),'Uncommitted source '+name)
        blobs[name]=value
    blobs['environment.json']=(json.dumps(read(ROOT/'tuning/first_domain_agnostic_v1/experiment.json')['environment'],indent=2)+'\n').encode()
    manifest=dict(source_commit=head,execution_freeze_sha256=scope['execution_freeze_sha256'],files={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()},
        auditor_rows=300,train=240,dev=60,producer_payloads=0,protected_files=0,old_adapters=0,credentials=0,folds_1_to_4=0)
    blobs['execution_manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    with zipfile.ZipFile(BASE/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,value in blobs.items():z.writestr(name,value)
    write_json(BASE/'execution_manifest.json',manifest);write_json(BASE/'training_authorization.json',scope)
    cloud=dict(source_commit=head,release_sha256=scope['execution_freeze_sha256'],bundle_sha256=sha(BASE/'runtime_bundle.zip'),instance=choice['metadata'],region=region,image=image,hourly_rate=rate,
        soft_usd=1.5,hard_usd=3,reserve_seconds=600,soft_seconds=1.5/rate*3600,hard_seconds=3/rate*3600,workload_deadline_seconds=3/rate*3600-600,
        watchdog_deadline_seconds=3/rate*3600-60,projected_seconds_with_reserve=projected,projected_cost=projected*rate/3600,name='shimmer-auditor-canonical',
        projection_assumptions=dict(setup_seconds=900,seconds_per_update=10,output_tokens_per_second=6,all_outputs_at_cap=True))
    write_json(BASE/'manifest.json',cloud);write_json(BASE/'LOCAL_GATES.json',dict(passed=True,authorization=scope,source_commit=head,bundle=manifest))
    check=BASE/'bundle_check';check.mkdir(exist_ok=True)
    with zipfile.ZipFile(BASE/'runtime_bundle.zip') as z:z.extractall(check)
    write_json(check/'training_authorization.json',scope)
    code="import sys;sys.path.insert(0,'tools');import auditor_canonical_remote as m;m.scope();print('Auditor-only 300 rows,120 updates,60 DEV packaged scope passed')"
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=check,capture_output=True)
    require(not credential_locations(result.stdout+result.stderr,'bundle check'),'Credential diagnostic withheld')
    (BASE/'bundle_check.log').write_bytes(result.stdout+result.stderr);require(result.returncode==0,'Packaged scope failed')
    write_json(BASE/'bundle_check_results.json',dict(passed=True,members=len(blobs)))
    print(json.dumps(cloud,indent=2))
if __name__=='__main__':prepare()
