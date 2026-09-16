"""One-instance canonical V2 controller; never schedules CV 1-4 or protected work."""
import argparse,hashlib,json,os,shlex,subprocess,sys,tarfile,time,zipfile
from pathlib import Path
from cloud_run_common import require,credential_locations,write_json
from lambda_experiment_provider import LambdaExperiment
from run_remote_experiment import poll_state,termination
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/fix/second_tuning_canonical_pilot';FROZEN=ROOT/'tuning/second_domain_agnostic_v2'
CREDENTIAL=Path('C:/Users/secki/local/api_keys/config.py');REMOTE='/home/ubuntu/shimmer-second-canonical-pilot'

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def write(name,value):write_json(BASE/name,value)
def git(*args):
    staged=subprocess.run(['git','diff','--cached','--no-ext-diff'],cwd=ROOT,capture_output=True,check=True).stdout
    require(not credential_locations(staged,'staged diff'),'Possible credential in staged files; stop')
    return subprocess.run(['git',*args],cwd=ROOT,capture_output=True,check=True).stdout

def prepare():
    BASE.mkdir(exist_ok=True);require(not (BASE/'LAUNCH_INTENT.json').exists(),'This authorization was consumed')
    sys.path.insert(0,str(FROZEN));import runner
    binding=runner.verify_freeze();dry=read(FROZEN/'dry_run_evidence.json')
    require(dry['passed'] and dry['verdict']=='SECOND_TUNING_EXPERIMENT_DESIGN_READY','No-model gates failed')
    freeze=read(FROZEN/'freeze.json');split=read(FROZEN/'splits.json')
    require(split['canonical']['train']==split['folds'][0]['train'] and split['canonical']['validation']==split['folds'][0]['validation'],'Fold0 binding failed')
    plans={role:runner.plan(role,'canonical') for role in ('producer','auditor')}
    for plan in plans.values():require(len(plan['train_ids'])==240 and len(plan['validation_ids'])==60 and len(plan['optimizer_schedule'])==120,'Unexpected schedule')
    for path in [ROOT/'runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json',ROOT/'runs/second-domain-agnostic-v2/PROTECTED_ACCESS_CONSUMED.json',ROOT/'docs/fix/first_real_tuning_20260916/downloaded/runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json']:
        require(not path.exists(),'Protected receipt consumed')
    names={name.replace('\\','/') for key in ('files','dependency_files') for name in freeze[key]}
    names.update(['tuning/second_domain_agnostic_v2/freeze.json','scripts/pairing_map.py','scripts/finding_record.py','scripts/localization.py','tools/second_tuning_remote.py'])
    forbidden={'benchmark/task_semantics/seed.json','benchmark/task_semantics_v2/extension.json','tuning/first_domain_agnostic_v1/protected_eval.py'}
    require(not names&forbidden and not any(x.startswith(('config/','input/','durable/')) for x in names),'Private/protected bundle member')
    head=git('rev-parse','HEAD').decode().strip();tracked=set(git('ls-files','-z').decode().split('\0'));require(names<=tracked,'Bundle sources must be committed first')
    blobs={}
    for name in sorted(names):
        content=(ROOT/name).read_bytes();require(not credential_locations(content,name),'Possible credential in bundle; stop')
        committed=git('show',head+':'+name)
        require(content.replace(b'\r\n',b'\n')==committed.replace(b'\r\n',b'\n'),'Bundle source differs from tested commit: '+name)
        blobs[name]=dict(sha256=hashlib.sha256(content).hexdigest(),bytes=len(content),commit_blob_sha256=hashlib.sha256(committed).hexdigest(),
            checkout_line_endings_only=content!=committed)
    with zipfile.ZipFile(BASE/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in sorted(names):z.writestr(name,(ROOT/name).read_bytes())
    inventory=read(BASE/'instance-types.json');require(read(BASE/'instances.json')==[],'Existing billable instances; do not add one')
    choices=[x for x in inventory if x['architecture']=='x86_64' and x['regions'] and x['metadata']['type'] in ('gpu_1x_a10','gpu_1x_a6000','gpu_1x_a100','gpu_1x_a100_sxm4','gpu_1x_h100_pcie','gpu_1x_h100_sxm5')]
    require(choices,'No suitable GPU');choice=min(choices,key=lambda x:x['metadata']['hourly_rate']);rate=choice['metadata']['hourly_rate']
    region='us-east-1' if 'us-east-1' in choice['regions'] else choice['regions'][0]
    image=next(x for x in read(BASE/'images.json') if x['region']==region and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    lengths=read(FROZEN/'token_analysis.json');projection={}
    for role,step_seconds,throughput in [('producer',5.468,8.850),('auditor',3.414,7.828)]:
        ids=set(plans[role]['validation_ids']);target=sum(x['target'] for x in lengths[role]['lengths'] if x['example_id'] in ids)*2
        projection[role]=dict(training_seconds=step_seconds*120*1.3,dev_seconds=target/throughput*1.4,projected_output_tokens=target)
    projected=600+600+sum(x['training_seconds']+x['dev_seconds'] for x in projection.values())
    require(projected*rate/3600<3,'Projected pilot exceeds $3; do not provision')
    manifest=dict(source_commit=head,release_sha256=binding,bundle_sha256=sha(BASE/'runtime_bundle.zip'),files=blobs,
        instance=choice['metadata'],region=region,image=image,hourly_rate=rate,soft_usd=2,hard_usd=3,reserve_seconds=600,
        soft_seconds=2/rate*3600,hard_seconds=3/rate*3600,workload_deadline_seconds=3/rate*3600-600,
        watchdog_deadline_seconds=3/rate*3600-60,projection=projection,projected_seconds_with_reserve=projected,
        projected_cost=projected*rate/3600,name='shimmer-second-canonical-pilot',freeze_unchanged=True)
    write('manifest.json',manifest)
    scope=dict(experiment='second-domain-agnostic-v2',operator_authorized=True,release_sha256=binding,roles=['producer','auditor'],splits=['canonical'],
        canonical_equals_fold=0,protected_access=False,maximum_instances=1,soft_budget_usd=2,hard_budget_usd=3,request_attachment='027f0f09-1368-4830-bed2-97f438ddff75')
    write('pilot_scope.json',scope)
    for role in scope['roles']:write(role+'_authorization.json',dict(experiment=scope['experiment'],operator_authorized=True,release_sha256=binding,role=role,split='canonical',action='train'))
    # Execute the frozen authorization function for every forbidden split.
    import importlib.util
    spec=importlib.util.spec_from_file_location('permit_probe',FROZEN/'train.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    denied=[]
    for role in scope['roles']:
        module.authorize(BASE/(role+'_authorization.json'),role,'canonical',binding)
        for fold in ('0','1','2','3','4'):
            try:module.authorize(BASE/(role+'_authorization.json'),role,fold,binding)
            except ValueError:denied.append(role+':'+fold)
            else:raise ValueError('Unauthorized fold admitted')
    write('LOCAL_GATES.json',dict(passed=True,source_commit=head,release_sha256=binding,plans=plans,forbidden_fold_permits_rejected=denied,
        protected_labels_in_bundle=0,protected_evaluator_in_bundle=False,credential_findings=0,authorization_consumed=False,
        path_portability='Root-local literal-backslash symlinks to verified POSIX members preserve all freeze bytes; resolved paths must stay under runtime root.',
        authorization_file_hashes={role:sha(BASE/(role+'_authorization.json')) for role in scope['roles']}))
    print(json.dumps({k:manifest[k] for k in ('source_commit','release_sha256','hourly_rate','projected_cost','projected_seconds_with_reserve','workload_deadline_seconds')},indent=2))

def watch():
    m=read(BASE/'manifest.json');launch=read(BASE/'launch.json');provider=LambdaExperiment(CREDENTIAL)
    write('WATCHDOG_ARMED.json',dict(pid=os.getpid(),deadline_epoch=launch['epoch']+m['watchdog_deadline_seconds']))
    while not (BASE/'TERMINATION_VERIFIED.json').exists():
        write('cost.json',dict(epoch=time.time(),estimated_usd=(time.time()-launch['epoch'])*m['hourly_rate']/3600))
        if time.time()>=launch['epoch']+m['watchdog_deadline_seconds'] or (BASE/'TERMINATE_REQUEST').exists():
            try:
                if termination(provider,launch['instance_id'],BASE,launch['epoch'],m['hourly_rate']):return
            except Exception:write('watch_error.json',dict(error='Provider termination retry required'))
        time.sleep(5)

def execute():
    m=read(BASE/'manifest.json');require(read(BASE/'LOCAL_GATES.json')['passed'],'Local gates missing')
    require(git('rev-parse','HEAD').decode().strip()==m['source_commit'],'Tested HEAD changed')
    require(not (BASE/'LAUNCH_INTENT.json').exists(),'Authorization already consumed')
    require(sha(BASE/'runtime_bundle.zip')==m['bundle_sha256'],'Bundle changed')
    provider=LambdaExperiment(CREDENTIAL);require(provider.request('instances')['data']==[],'Inventory is no longer empty')
    current=next(x for x in provider.request('instance-types')['data'] if x['metadata']['type']==m['instance']['type'])
    require(current['metadata']['hourly_rate']==m['hourly_rate'] and m['region'] in current['regions'],'Price/capacity changed')
    identity=BASE/'ssh_identity';registration=None;iid=None;ssh=None;host=None;options=[];start=time.time();deadline=start+m['workload_deadline_seconds']
    def transport(label,argv,timeout=60,required=True):
        begin=time.time()
        try:result=subprocess.run(argv,capture_output=True,timeout=timeout)
        except subprocess.TimeoutExpired:
            write(label+'_timing.json',dict(seconds=time.time()-begin,status='timeout'));raise RuntimeError('Timeout: '+label) from None
        output=result.stdout+result.stderr
        require(not credential_locations(output,label),'Possible credential in diagnostic; withheld; stop')
        (BASE/(label+'.log')).write_bytes(output);write(label+'_timing.json',dict(seconds=time.time()-begin,returncode=result.returncode,start_epoch=begin))
        require(not required or result.returncode==0,'Phase failed: '+label)
        return result
    def remote(label,command,timeout=60,required=True):
        write('CURRENT_PHASE.json',dict(phase=label,epoch=time.time(),estimated_cost=(time.time()-start)*m['hourly_rate']/3600))
        remaining=int(deadline-time.time());require(remaining>0,'Workload budget cutoff reached')
        print(label,flush=True)
        return transport(label,ssh+[command],min(timeout,remaining),required)
    try:
        result=subprocess.run(['ssh-keygen','-t','ed25519','-N','','-f',str(identity),'-C',m['name']],capture_output=True)
        require(result.returncode==0,'Temporary SSH key creation failed')
        registration=provider.request('ssh-keys',dict(name=m['name'],public_key=Path(str(identity)+'.pub').read_text().strip()))['data'][0]
        write('ssh_registration.json',registration)
        start=time.time();deadline=start+m['workload_deadline_seconds']
        write('LAUNCH_INTENT.json',dict(epoch=start,maximum_instances=1,request_attachment='027f0f09-1368-4830-bed2-97f438ddff75'))
        launched=provider.request('instance-operations/launch',dict(region_name=m['region'],instance_type_name=m['instance']['type'],ssh_key_names=[registration['name']],quantity=1,name=m['name'],image={'id':m['image']['id']}))['data']
        iid=launched['instance_ids'][0];write('launch.json',dict(instance_id=iid,epoch=start))
        flags=getattr(subprocess,'DETACHED_PROCESS',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'CREATE_NO_WINDOW',0)
        subprocess.Popen([sys.executable,str(Path(__file__)),'watch'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
        for _ in range(20):
            if (BASE/'WATCHDOG_ARMED.json').exists():break
            time.sleep(.5)
        require((BASE/'WATCHDOG_ARMED.json').exists(),'Watchdog failed to arm')
        while time.time()-start<600:
            state=poll_state(provider,iid,BASE)
            if state['status']=='active' and state.get('public_ip'):break
            time.sleep(5)
        else:raise RuntimeError('Activation timeout')
        require(state['hourly_rate']==m['hourly_rate'],'Runtime price changed')
        write('activation.json',dict(seconds=time.time()-start,metadata=state))
        host='ubuntu@'+state['public_ip'];options=['-i',str(identity),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(BASE/'known_hosts'),'-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2'];ssh=['ssh',*options,host]
        for i in range(30):
            if transport('ssh_ready_'+str(i),ssh+['true'],20,False).returncode==0:break
            time.sleep(5)
        else:raise RuntimeError('SSH unavailable')
        remote('python_gate',"/usr/bin/python3.12 -I -S -c 'import sys;assert sys.version_info[:3]==(3,12,3);print(sys.version)'",30)
        remote('mkdir','mkdir -p '+REMOTE)
        transport('runtime_transfer',['scp',*options,str(BASE/'runtime_bundle.zip'),str(BASE/'pilot_scope.json'),str(BASE/'producer_authorization.json'),str(BASE/'auditor_authorization.json'),host+':'+REMOTE+'/'],120)
        prefix='cd '+REMOTE+' && ';exe=REMOTE+'/.venv/bin/python'
        remote('unpack',prefix+'echo '+shlex.quote(m['bundle_sha256']+'  runtime_bundle.zip')+' | sha256sum -c - && /usr/bin/python3.12 -m zipfile -e runtime_bundle.zip .')
        # Windows backslashes are literal characters on Linux. Verified aliases
        # adapt filesystem spelling only; no frozen JSON/code bytes are edited.
        code="import json;from pathlib import Path;root=Path.cwd();f=json.loads((root/'tuning/second_domain_agnostic_v2/freeze.json').read_text());\nfor section in ('files','dependency_files'):\n for name in f[section]:\n  target=(root/name.replace(chr(92),'/')).resolve();assert target.is_relative_to(root) and target.is_file();alias=root/name\n  if alias!=target:alias.symlink_to(target.relative_to(root))\n"
        remote('path_aliases',prefix+'/usr/bin/python3.12 -I -S -B -c '+shlex.quote(code))
        remote('source_gate',prefix+"/usr/bin/python3.12 -B tuning/second_domain_agnostic_v2/runner.py --role producer --split canonical --dry-run",30)
        remote('venv',prefix+'/usr/bin/python3.12 -m venv .venv',120)
        remote('torch_install',prefix+exe+' -m pip --disable-pip-version-check install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121',1200)
        deps=read(ROOT/'tuning/first_domain_agnostic_v1/dependency_lock.json')['packages']
        remote('dependencies_install',prefix+exe+' -m pip --disable-pip-version-check install '+' '.join(shlex.quote(k+'=='+v) for k,v in deps.items() if k!='torch')+' psutil==7.0.0',900)
        remote('pre_acquisition',prefix+exe+' -B tools/second_tuning_remote.py preflight',120)
        remote('acquisition',prefix+exe+' -B tools/second_tuning_remote.py acquire',1800)
        env=' '.join(k+'='+shlex.quote(v) for k,v in read(ROOT/'tuning/first_domain_agnostic_v1/experiment.json')['environment'].items())+' HF_HUB_DISABLE_TELEMETRY=1 '
        for role in ('producer','auditor'):
            projected=m['projection'][role]['training_seconds']+m['projection'][role]['dev_seconds']
            require(time.time()+projected<deadline,'Remaining frozen role cannot fit budget with reserve')
            result=remote(role+'_training',prefix+env+exe+' -B -u tools/second_tuning_remote.py train --role '+role,7200,False)
            released=remote(role+'_released','nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader',30)
            require(not released.stdout.strip(),'GPU workload did not release')
            require(result.returncode==0,'Frozen runtime failed; no rescue or second instance')
        write('MANDATORY_WORK_FINISHED.json',dict(epoch=time.time(),canonical_only=True))
    except Exception as exc:
        write('controller_failure.json',dict(type=type(exc).__name__,message=str(exc)))
    finally:
        if iid is None and (BASE/'LAUNCH_INTENT.json').exists():
            matches=[x for x in provider.request('instances')['data'] if x.get('name')==m['name']]
            require(len(matches)<=1,'Ambiguous launch recovery')
            if matches:iid=matches[0]['instance_id']
        if iid:
            if ssh:
                try:
                    transport('stop_workloads',ssh+['pkill -TERM -f "[t]ools/second_tuning_remote.py" || true'],30,False)
                    transport('process_final',ssh+['nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader'],30,False)
                    transport('pack_evidence',ssh+['cd '+REMOTE+' && tar -czf evidence.tar.gz evidence runs tools/second_tuning_remote.py tuning/second_domain_agnostic_v2/freeze.json'],120,False)
                    evidence_hash=transport('evidence_hash',ssh+['sha256sum '+REMOTE+'/evidence.tar.gz'],30)
                    transport('evidence_download',['scp',*options,host+':'+REMOTE+'/evidence.tar.gz',str(BASE/'evidence.tar.gz')],240)
                    require(evidence_hash.stdout.decode().split()[0]==sha(BASE/'evidence.tar.gz'),'Evidence hash mismatch')
                    write('collection_integrity.json',dict(sha256=sha(BASE/'evidence.tar.gz'),bytes=(BASE/'evidence.tar.gz').stat().st_size))
                except Exception:write('collection_failure.json',dict(message='Evidence incomplete; teardown required'))
            (BASE/'TERMINATE_REQUEST').touch()
            while True:
                try:
                    if termination(provider,iid,BASE,start,m['hourly_rate']):break
                except Exception:pass
                time.sleep(5)
            remaining=provider.request('instances')['data'];write('instances_after.json',remaining);require(remaining==[],'Billable resources remain')
        if registration:
            provider.request('ssh-keys/'+registration['id'],method='DELETE')
            require(not any(x['id']==registration['id'] for x in provider.request('ssh-keys')['data']),'Temporary SSH registration remains')
        identity.unlink(missing_ok=True);Path(str(identity)+'.pub').unlink(missing_ok=True)
        for name in ('producer_authorization.json','auditor_authorization.json'):(BASE/name).unlink(missing_ok=True)
        write('cleanup.json',dict(temporary_ssh_removed=True,local_key_material_removed=True,role_permits_removed=True))
        print('Terminated:',(BASE/'TERMINATION_VERIFIED.json').exists(),flush=True)

def status():
    for name in ('CURRENT_PHASE.json','cost.json','producer_training_timing.json','auditor_training_timing.json','TERMINATION_VERIFIED.json','controller_failure.json'):
        if (BASE/name).exists():print(name,json.dumps(read(BASE/name)))
    if (BASE/'activation.json').exists() and not (BASE/'TERMINATION_VERIFIED.json').exists():
        state=read(BASE/'activation.json')['metadata'];identity=BASE/'ssh_identity'
        args=['ssh','-i',str(identity),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(BASE/'known_hosts'),'-o','ConnectTimeout=10','ubuntu@'+state['public_ip'],"cat "+REMOTE+'/evidence/progress.json']
        value=subprocess.run(args,capture_output=True,timeout=20)
        require(not credential_locations(value.stdout,'progress'),'Sensitive diagnostic withheld')
        if value.returncode==0:print(value.stdout.decode())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','execute','watch','status']);a=p.parse_args();globals()[a.action]()
