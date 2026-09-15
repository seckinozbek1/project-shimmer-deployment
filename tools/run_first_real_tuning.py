"""One authorized cloud training experiment with independent budget watchdog."""
import hashlib,json,os,shlex,subprocess,sys,tarfile,time,zipfile
from pathlib import Path
from cloud_run_common import require,credential_locations,safe_metadata,write_json,digest
from lambda_experiment_provider import LambdaExperiment
from run_remote_experiment import poll_state,termination

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/first_real_tuning_20260916'
FROZEN=ROOT/'tuning/first_domain_agnostic_v1'
CREDENTIAL=Path('C:/Users/secki/local/api_keys/config.py')
REMOTE='/home/ubuntu/shimmer-first-tuning-20260916'

def write(name,v):write_json(BASE/name,v)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

def prepare():
    require(read(BASE/'LOCAL_GATES.json')['pass'] is True,'Local gates absent')
    inventory=read(BASE/'instance-types.json')
    # Turing RTX6000 is not BF16 suitable. Architecture and locked CUDA exclude ARM/Blackwell.
    choices=[x for x in inventory if x['architecture']=='x86_64' and x['regions'] and
        x['metadata']['type'] in ('gpu_1x_a10','gpu_1x_a6000','gpu_1x_a100','gpu_1x_a100_sxm4','gpu_1x_h100_pcie','gpu_1x_h100_sxm5')]
    require(choices,'No suitable inventory')
    choice=min(choices,key=lambda x:x['metadata']['hourly_rate']);rate=choice['metadata']['hourly_rate']
    projected=read(FROZEN/'projections.json')['total_wall_minutes'][1]+7 # increase old 3-minute teardown to 10
    require(projected*rate/60<=3,'Frozen projection exceeds hard ceiling')
    region='us-east-1' if 'us-east-1' in choice['regions'] else choice['regions'][0]
    images=read(BASE/'images.json')
    image=next(x for x in images if x['region']==region and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    manifest=dict(instance=choice['metadata'],region=region,image=image,hourly_rate=rate,soft_usd=2,hard_usd=3,
        reserve_seconds=600,soft_seconds=2/rate*3600,hard_seconds=3/rate*3600,
        workload_deadline_seconds=3/rate*3600-600,projected_minutes_with_reserve=projected,
        projected_cost_with_reserve=projected*rate/60,name='shimmer-first-tuning-20260916',
        frozen_source_commit='a704fe8ca04032932981f32643aebad98ef2f619',
        training_bundle_sha256=sha(FROZEN/'training_bundle.zip'),freeze_sha256=sha(FROZEN/'freeze.json'),
        runtime_wrapper_sha256=sha(ROOT/'tools/first_tuning_remote.py'))
    require(manifest['training_bundle_sha256']=='155b6b539d9d924bc56d473fd5fcc34dcacab5379554c91b351fc4f535f48a70','Frozen archive changed')
    write('manifest.json',manifest)
    policy=dict(operator_scope_action='first bounded tuning experiment',operator_scope_experiment='first_domain_agnostic_v1',
        experiment='first-domain-agnostic-tuning-v1',experiment_freeze_sha256=manifest['freeze_sha256'],
        operator_authorized=True,roles=['producer','auditor'],real_lora_sft=True,cloud_authorized=True,
        maximum_instances=1,soft_budget_usd=2,hard_budget_usd=3,full_pipeline=False,multi_round=False,
        model_pin_config_changes=False,protected_only_after_both_selection_freezes=True,
        training_after_protected=False,reselection_after_protected=False,repeated_protected_evaluation=False)
    for action,name in [('train','training_authorization.json'),('protected_evaluation','protected_authorization.json')]:
        write(name,dict(policy,action=action))
    write('authorization_provenance.json',dict(operator_request_attachment='3f71a5ae-a9e5-422a-b729-582035f6f794',
        runner_action_mapping={'first bounded tuning experiment':'train','one-shot protected evaluation':'protected_evaluation'},
        hashes={n:sha(BASE/n) for n in ('training_authorization.json','protected_authorization.json')},consumed=False))
    write('signal_policy.json',dict(frozen_before_launch=True,positive='all tuned catastrophic counts zero; no contract, truncation or evidence regression; exact role semantic mean strictly greater',
        negative='new per-example catastrophic failure, worse evidence, any lower contract rate, new truncation or lower exact semantic mean',
        neutral='no regression and equal exact semantic mean',indeterminate='incomplete/unavailable/invalid protected comparison',
        minimum_posthoc_effect_threshold=None,semantic_formula='unchanged DEV role arithmetic score applied to protected outputs',
        followup='neither role negative/indeterminate, at least one positive, no catastrophic/integrity regression'))
    print(json.dumps(manifest,indent=2))

def execute():
    m=read(BASE/'manifest.json');require(not (BASE/'LAUNCH_INTENT.json').exists(),'Authorization consumed')
    require(sha(FROZEN/'training_bundle.zip')==m['training_bundle_sha256'],'Bundle changed')
    require(sha(ROOT/'tools/first_tuning_remote.py')==m['runtime_wrapper_sha256'],'Runtime envelope changed')
    provider=LambdaExperiment(CREDENTIAL);key=BASE/'ssh_identity';registration=None;iid=None;ssh=None;host=None;options=[]
    start=time.time();deadline=start+m['workload_deadline_seconds']
    def transport(label,argv,timeout=60,required=True):
        begin=time.time()
        try:r=subprocess.run(argv,capture_output=True,timeout=timeout)
        except subprocess.TimeoutExpired:
            write(label+'_timing.json',dict(status='timeout',seconds=time.time()-begin));raise RuntimeError('Transport timeout: '+label) from None
        content=r.stdout+r.stderr
        require(not credential_locations(content,label),'Possible credential in remote diagnostic; withheld')
        (BASE/(label+'.log')).write_bytes(content)
        write(label+'_timing.json',dict(start_epoch=begin,seconds=time.time()-begin,returncode=r.returncode))
        require(not required or r.returncode==0,'Stage failed: '+label)
        return r
    def remote(label,command,timeout=60,required=True):
        write('CURRENT_PHASE.json',dict(phase=label,epoch=time.time(),cost_upper_bound=(time.time()-start)*m['hourly_rate']/3600))
        remaining=int(deadline-time.time());require(remaining>0,'Budget reserve reached')
        return transport(label,ssh+[command],min(timeout,remaining),required)
    try:
        r=subprocess.run(['ssh-keygen','-t','ed25519','-N','','-f',str(key),'-C',m['name']],capture_output=True)
        require(r.returncode==0,'Key creation failed')
        registration=provider.request('ssh-keys',dict(name=m['name'],public_key=Path(str(key)+'.pub').read_text().strip()))['data'][0]
        write('ssh_registration.json',registration)
        start=time.time();deadline=start+m['workload_deadline_seconds']
        write('LAUNCH_INTENT.json',dict(epoch=start,name=m['name'],maximum_instances=1))
        launched=provider.request('instance-operations/launch',dict(region_name=m['region'],instance_type_name=m['instance']['type'],
            ssh_key_names=[registration['name']],quantity=1,name=m['name'],image={'id':m['image']['id']}))['data']
        iid=launched['instance_ids'][0];write('launch.json',dict(instance_id=iid,epoch=start))
        flags=getattr(subprocess,'DETACHED_PROCESS',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'CREATE_NO_WINDOW',0)
        subprocess.Popen([sys.executable,str(ROOT/'tools/run_remote_experiment.py'),'watch','--directory',str(BASE),'--credential-file',str(CREDENTIAL)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
        for _ in range(20):
            if (BASE/'WATCHDOG_ARMED.json').exists():break
            time.sleep(.5)
        require((BASE/'WATCHDOG_ARMED.json').exists(),'Watchdog not armed')
        while time.time()-start<600:
            state=poll_state(provider,iid,BASE)
            if state['status']=='active' and state.get('public_ip'):break
            time.sleep(5)
        else:raise RuntimeError('Activation timeout')
        require(state['hourly_rate']==m['hourly_rate'],'Price changed')
        write('activation.json',dict(seconds=time.time()-start,metadata=state))
        host='ubuntu@'+state['public_ip'];options=['-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new',
            '-o','UserKnownHostsFile='+str(BASE/'known_hosts'),'-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2']
        ssh=['ssh',*options,host]
        for attempt in range(30):
            if transport('ssh_ready_'+str(attempt),ssh+['true'],20,False).returncode==0:break
            time.sleep(5)
        else:raise RuntimeError('SSH unavailable')
        remote('python_gate',"/usr/bin/python3.12 -I -S -c 'import sys;assert sys.version_info[:3]==(3,12,3);print(sys.executable,sys.version)'",30)
        remote('mkdir','mkdir -p '+REMOTE+'/tools '+REMOTE+'/evidence')
        transport('training_transfer',['scp',*options,str(FROZEN/'training_bundle.zip'),str(ROOT/'tools/first_tuning_remote.py'),str(BASE/'training_authorization.json'),host+':'+REMOTE+'/'],120)
        prefix='cd '+REMOTE+' && '
        remote('archive_integrity',prefix+'echo '+shlex.quote(m['training_bundle_sha256']+'  training_bundle.zip')+' | sha256sum -c - && /usr/bin/python3.12 -m zipfile -e training_bundle.zip . && mv first_tuning_remote.py tools/first_tuning_remote.py')
        code='import sys;from pathlib import Path;sys.path.insert(0,"tuning/first_domain_agnostic_v1");import common;common.frozen();[compile((Path.cwd()/n).read_text(),n,"exec") for n in common.read(common.HERE/"freeze.json")["files"] if n.endswith(".py")];assert common.digest(Path("tools/first_tuning_remote.py").read_bytes())=='+repr(m['runtime_wrapper_sha256'])
        remote('source_preflight',prefix+'/usr/bin/python3.12 -I -S -B -c '+shlex.quote(code))
        remote('venv',prefix+'/usr/bin/python3.12 -m venv .venv',120)
        exe=REMOTE+'/.venv/bin/python'
        remote('torch_install',prefix+exe+' -m pip --disable-pip-version-check install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121',1200)
        deps=read(FROZEN/'dependency_lock.json')['packages']
        remote('dependencies_install',prefix+exe+' -m pip --disable-pip-version-check install '+' '.join(shlex.quote(k+'=='+v) for k,v in deps.items() if k!='torch'),900)
        remote('runtime_preflight',prefix+exe+' -B tools/first_tuning_remote.py preflight',120)
        remote('acquisition',prefix+exe+' -B tools/first_tuning_remote.py acquire',1800)
        env=' '.join(k+'='+shlex.quote(v) for k,v in read(FROZEN/'experiment.json')['environment'].items())+' HF_HUB_DISABLE_TELEMETRY=1 '
        for role in ('producer','auditor'):
            require(time.time()+900<deadline,'Insufficient role budget and reserve')
            remote(role+'_training',prefix+env+exe+' -B -u tools/first_tuning_remote.py train --role '+role,3600,False)
            remote(role+'_released','nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader',30)
        code='import sys,json;from pathlib import Path;sys.path.insert(0,"tuning/first_domain_agnostic_v1");from evaluation import verify_selection;root=Path("runs/first-domain-agnostic-tuning-v1");v={};\nfor role in ("producer","auditor"):\n try: verify_selection(role,root/role);v[role]=True\n except Exception:v[role]=False\nprint(json.dumps(v))'
        r=remote('selection_verification',prefix+exe+' -B -c '+shlex.quote(code),120)
        selections=json.loads(r.stdout);write('BOTH_SELECTIONS.json',dict(roles=selections,both=all(selections.values())))
        if all(selections.values()):
            require(time.time()+1800<deadline,'Insufficient protected evaluation budget')
            # Only now may local authored sources be read/packed for the frozen mechanism.
            names=['tuning/first_domain_agnostic_v1/protected_eval.py','tuning/first_domain_agnostic_v1/protected_population.json',
                'benchmark/first_tuning_experiment_v1/registration.py','benchmark/first_tuning_experiment_v1/acceptance_registration.json',
                'benchmark/machine_adjudication_v1/r06.py','benchmark/task_semantics_v2/hardening.py',
                'benchmark/task_semantics/seed.json','benchmark/task_semantics_v2/extension.json']
            with zipfile.ZipFile(BASE/'protected_control.zip','w',zipfile.ZIP_DEFLATED) as z:
                for n in names:
                    data=(ROOT/n).read_bytes();require(not credential_locations(data,n),'Protected bundle credential finding');z.writestr(n,data)
            write('protected_bundle_manifest.json',dict(files={n:sha(ROOT/n) for n in names},sha256=sha(BASE/'protected_control.zip'),
                source_files_required_by_frozen_reader=True,evaluated_ids=114,selection_verified_before_creation=True))
            transport('protected_transfer',['scp',*options,str(BASE/'protected_control.zip'),str(BASE/'protected_authorization.json'),host+':'+REMOTE+'/'],120)
            remote('protected_unpack',prefix+'echo '+shlex.quote(sha(BASE/'protected_control.zip')+'  protected_control.zip')+' | sha256sum -c - && '+exe+' -m zipfile -e protected_control.zip .')
            remote('protected_evaluation',prefix+env+exe+' -B -u tools/first_tuning_remote.py protected',2400,False)
    except Exception as exc:
        write('controller_failure.json',dict(type=type(exc).__name__,message='Stopped at recorded safe phase; inspect stage diagnostics'))
    finally:
        if iid is None and (BASE/'LAUNCH_INTENT.json').exists():
            matches=[x for x in provider.request('instances')['data'] if x.get('name')==m['name']]
            require(len(matches)<=1,'Ambiguous launch recovery')
            if matches:iid=matches[0]['instance_id']
        if iid:
            if ssh:
                try:
                    transport('stop_workloads',ssh+['pkill -TERM -f "[t]ools/first_tuning_remote.py" || true'],30,False)
                    transport('process_final',ssh+['nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader'],30,False)
                    transport('pack_evidence',ssh+['cd '+REMOTE+' && tar -czf evidence.tar.gz evidence runs tuning/first_domain_agnostic_v1/freeze.json tools/first_tuning_remote.py'],120,False)
                    r=transport('evidence_hash',ssh+['sha256sum '+REMOTE+'/evidence.tar.gz'],30)
                    transport('evidence_download',['scp',*options,host+':'+REMOTE+'/evidence.tar.gz',str(BASE/'evidence.tar.gz')],240)
                    require(r.stdout.decode().split()[0]==sha(BASE/'evidence.tar.gz'),'Evidence archive hash mismatch')
                    write('collection_integrity.json',dict(sha256=sha(BASE/'evidence.tar.gz'),bytes=(BASE/'evidence.tar.gz').stat().st_size))
                except Exception:write('collection_failure.json',dict(message='Collection incomplete; teardown still required'))
            (BASE/'TERMINATE_REQUEST').touch()
            while True:
                try:
                    if termination(provider,iid,BASE,start,m['hourly_rate']):break
                except Exception:pass
                time.sleep(5)
            remaining=provider.request('instances')['data'];write('instances_after.json',remaining)
            require(not any(x.get('instance_id')==iid for x in remaining),'Experiment instance remains')
        if registration:
            provider.request('ssh-keys/'+registration['id'],method='DELETE')
            require(not any(x['id']==registration['id'] for x in provider.request('ssh-keys')['data']),'SSH registration persists')
        key.unlink(missing_ok=True);Path(str(key)+'.pub').unlink(missing_ok=True)
        for n in ('training_authorization.json','protected_authorization.json'):(BASE/n).unlink(missing_ok=True)
        write('cleanup.json',dict(provider_ssh_registration_removed=True,local_keys_removed=True,ephemeral_authorizations_removed=True))
        print('Controller finished; termination evidence:',(BASE/'TERMINATION_VERIFIED.json').exists())

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='execute':execute()
