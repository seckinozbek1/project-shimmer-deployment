"""Authorized feature diagnostic only; one A10, $1 soft / $2 hard ceiling."""
import argparse,hashlib,json,os,shlex,subprocess,sys,tarfile,time,zipfile
from pathlib import Path
from cloud_run_common import require,credential_locations,write_json
from lambda_experiment_provider import LambdaExperiment
from run_remote_experiment import poll_state,termination
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/fix/auditor_feature_remote_run';FROZEN=ROOT/'tuning/second_domain_agnostic_v2'
CREDENTIAL=Path('C:/Users/secki/local/api_keys/config.py');REMOTE='/home/ubuntu/shimmer-auditor-feature-diagnostic'

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
    from prepare_auditor_feature_remote import prepare as build
    build()


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
    m=read(BASE/'manifest.json');require(read(BASE/'LOCAL_GATES.json')['passed'],'Local gates missing');require(read(BASE/'bundle_check_results.json')['passed'],'Packaged integration gates missing')
    require(m['soft_usd']==1 and m['hard_usd']==2 and m['hourly_rate']==1.29 and m['region']=='us-east-1' and m['instance']['type']=='gpu_1x_a10','Exact diagnostic authorization caps')
    require(m['workload_deadline_seconds']<=2/1.29*3600-900 and m['watchdog_deadline_seconds']<=2/1.29*3600-180,'Budget reserves')
    require(git('rev-parse','HEAD').decode().strip()==m['source_commit'],'Tested HEAD changed')
    require(all(line.startswith('?? ') for line in git('status','--porcelain').decode().splitlines()),'Tracked source changed')
    require(not (BASE/'LAUNCH_INTENT.json').exists(),'Authorization already consumed')
    require(sha(BASE/'runtime_bundle.zip')==m['bundle_sha256'],'Bundle changed')
    provider=LambdaExperiment(CREDENTIAL);require(provider.request('instances')['data']==[],'Inventory is no longer empty')
    current=next(x for x in provider.request('instance-types')['data'] if x['metadata']['type']==m['instance']['type'])
    require(current['metadata']['type']=='gpu_1x_a10' and current['metadata']['hourly_rate']==m['hourly_rate'] and m['region'] in current['regions'],'Price/capacity changed')
    identity=BASE/'ssh_identity';registration=None;iid=None;ssh=None;host=None;options=[];start=time.time();deadline=start+m['workload_deadline_seconds']
    def transport(label,argv,timeout=60,required=True):
        if iid:
            timeout=min(timeout,max(1,int(start+m['watchdog_deadline_seconds']-30-time.time())))
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
        if time.time()>=start+m['soft_seconds']:
            # Recheck setup overrun; remote per-update checks handle the running workload.
            remaining_work=900
            fits=time.time()+remaining_work+600<start+m['hard_seconds']
            write('soft_budget_recheck.json',dict(epoch=time.time(),phase=label,remaining_work_seconds=remaining_work,reserve_seconds=600,fits=fits))
            require(fits,'Soft-budget mandatory-work estimate exceeds hard limit')
        remaining=int(deadline-time.time());require(remaining>0,'Workload budget cutoff reached')
        print(label,flush=True)
        return transport(label,ssh+[command],min(timeout,remaining),required)
    try:
        result=subprocess.run(['ssh-keygen','-t','ed25519','-N','','-f',str(identity),'-C',m['name']],capture_output=True)
        require(result.returncode==0,'Temporary SSH key creation failed')
        registration=provider.request('ssh-keys',dict(name=m['name'],public_key=Path(str(identity)+'.pub').read_text().strip()))['data'][0]
        write('ssh_registration.json',registration)
        start=time.time();deadline=start+m['workload_deadline_seconds']
        with (BASE/'LAUNCH_INTENT.json').open('x') as lock:json.dump(dict(epoch=start,maximum_instances=1,authorization='explicit feature diagnostic only; one instance; soft1 hard2; no training'),lock)
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
        permit=read(BASE/'diagnostic_authorization.json');permit.update(launch_epoch=start,workload_deadline_epoch=deadline,hourly_rate=m['hourly_rate']);write('diagnostic_authorization.json',permit)
        remote('python_gate',"/usr/bin/python3.12 -I -S -c 'import sys;assert sys.version_info[:3]==(3,12,3);print(sys.version)'",30)
        remote('mkdir','mkdir -p '+REMOTE)
        transport('runtime_transfer',['scp',*options,str(BASE/'runtime_bundle.zip'),str(BASE/'diagnostic_authorization.json'),host+':'+REMOTE+'/'],120)
        prefix='cd '+REMOTE+' && ';exe=REMOTE+'/.venv/bin/python'
        remote('unpack',prefix+'echo '+shlex.quote(m['bundle_sha256']+'  runtime_bundle.zip')+' | sha256sum -c - && /usr/bin/python3.12 -m zipfile -e runtime_bundle.zip .')
        remote('venv',prefix+'/usr/bin/python3.12 -m venv .venv',120)
        remote('torch_install',prefix+exe+' -m pip --disable-pip-version-check install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121',1200)
        deps=read(ROOT/'tuning/auditor_final/runtime_contract.json')['packages']
        remote('dependencies_install',prefix+exe+' -m pip --disable-pip-version-check install '+' '.join(shlex.quote(k+'=='+v) for k,v in deps.items() if k!='torch'),900)
        remote('pre_acquisition',prefix+exe+' -B tools/auditor_feature_remote.py preflight',120)
        remote('acquisition',prefix+exe+' -B tools/auditor_feature_remote.py acquire',1800)
        env=' '.join(k+'='+shlex.quote(v) for k,v in read(ROOT/'tuning/first_domain_agnostic_v1/experiment.json')['environment'].items())+' HF_HUB_DISABLE_TELEMETRY=1 '
        write('budget.json',dict(launch_epoch=start,workload_deadline_epoch=deadline,termination_deadline_epoch=start+m['termination_deadline_seconds'],soft_epoch=start+m['soft_seconds'],hard_epoch=start+m['hard_seconds'],hourly_rate=m['hourly_rate']))
        transport('budget_transfer',['scp',*options,str(BASE/'budget.json'),host+':'+REMOTE+'/budget.json'],30)
        result=remote('feature_diagnostic',prefix+env+exe+' -B -u tools/auditor_feature_remote.py execute',3600,False)
        write('WORKLOAD_FINISHED.json',dict(epoch=time.time(),returncode=result.returncode,diagnostic_only=True))
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
                    transport('stop_workloads',ssh+['pkill -TERM -f "[t]ools/auditor_feature_remote.py" || true'],30,False)
                    transport('process_final',ssh+['nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader'],30,False)
                    transport('pack_evidence',ssh+['cd '+REMOTE+' && tar -czf evidence.tar.gz evidence execution_manifest.json diagnostic_authorization.json budget.json tools diagnostic_payload'],120,False)
                    evidence_hash=transport('evidence_hash',ssh+['sha256sum '+REMOTE+'/evidence.tar.gz'],30)
                    transport('evidence_download',['scp',*options,host+':'+REMOTE+'/evidence.tar.gz',str(BASE/'evidence.tar.gz')],600)
                    require(evidence_hash.stdout.decode().split()[0]==sha(BASE/'evidence.tar.gz'),'Evidence hash mismatch')
                    write('collection_integrity.json',dict(sha256=sha(BASE/'evidence.tar.gz'),bytes=(BASE/'evidence.tar.gz').stat().st_size,verified_epoch=time.time()))
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
        # New authorization is nonsecret evidence and is retained.
        inventory=provider.request('instances')['data'];write('final_inventory_confirmation.json',dict(instances=inventory,zero_billable_resources=inventory==[],epoch=time.time()));require(inventory==[],'Final inventory not empty')
        write('cleanup.json',dict(temporary_ssh_removed=True,local_key_material_removed=True,historical_permits_reused=False))
        independent=LambdaExperiment(CREDENTIAL)
        inventory=independent.request('instances')['data']
        keys=independent.request('ssh-keys')['data']
        registration_absent=registration is None or all(x['id']!=registration['id'] for x in keys)
        local_absent=not identity.exists() and not Path(str(identity)+'.pub').exists()
        write('independent_inventory_confirmation.json',dict(instances=inventory,temporary_ssh_registration_absent=registration_absent,local_key_material_absent=local_absent,epoch=time.time()))
        require(inventory==[] and registration_absent and local_absent,'independent cleanup verification')
        print('Terminated:',(BASE/'TERMINATION_VERIFIED.json').exists(),flush=True)

def status():
    for name in ('CURRENT_PHASE.json','cost.json','feature_diagnostic_timing.json','WORKLOAD_FINISHED.json','TERMINATION_VERIFIED.json','controller_failure.json'):
        if (BASE/name).exists():print(name,json.dumps(read(BASE/name)))
    if (BASE/'activation.json').exists() and not (BASE/'TERMINATION_VERIFIED.json').exists():
        state=read(BASE/'activation.json')['metadata'];identity=BASE/'ssh_identity'
        args=['ssh','-i',str(identity),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(BASE/'known_hosts'),'-o','ConnectTimeout=10','ubuntu@'+state['public_ip'],"cat "+REMOTE+'/evidence/progress.json']
        value=subprocess.run(args,capture_output=True,timeout=20)
        require(not credential_locations(value.stdout,'progress'),'Sensitive diagnostic withheld')
        if value.returncode==0:print(value.stdout.decode())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','execute','watch','status']);a=p.parse_args();globals()[a.action]()
