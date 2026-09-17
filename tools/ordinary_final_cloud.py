"""Operator-authorized one-instance execution of the sealed ordinary final run.

No runtime source modification, model acquisition outside the transfer allowlist,
second instance, or full-run retry. Provider diagnostics are allowlisted.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

from ordinary_final_run import read, write, sha, require
from cloud_run_common import credential_locations
from lambda_experiment_provider import LambdaExperiment
from run_remote_experiment import poll_state, termination

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/ordinary_final_cloud_run'
CREDENTIAL=Path('C:/Users/secki/local/api_keys/config.py')
REMOTE='/home/ubuntu/shimmer-ordinary-final'
MANIFEST='dcc3aa913b2e59ca2831bc92009b9f888ca0a23e617f4a8d02acb0761876f223'
SEAL='93d2c5b2fe371f19143abe536569fe7bf15bcf9307b3136826b6440e028a4916'


def save(name,value):write(BASE/name,value)


def execute():
    require(sha(BASE/'execution_manifest.json')==MANIFEST and sha(BASE/'seal.json')==SEAL,'Authorized seal changed')
    m=read(BASE/'execution_manifest.json')
    require(read(BASE/'AUTHORIZED_LOCAL_REVERIFICATION.json')['passed'],'Local reverification missing')
    for name,digest in m['local_control_hashes'].items():require(sha(ROOT/name)==digest,'Controller source changed')
    for name,digest in m['support_files'].items():require(sha(BASE/name)==digest,'Support source changed')
    require(sha(BASE/'project.tar.gz')==m['source_archive_sha256'],'Project archive changed')
    assets=read(BASE/'assets_transfer_archive.json')
    require(assets['manifest_sha256']==MANIFEST and sha(ROOT/assets['path'])==assets['sha256'],'Transfer archive changed')
    require(not (BASE/'LAUNCH_INTENT.json').exists(),'Authorization consumed; no launch retry')
    provider=LambdaExperiment(CREDENTIAL)
    require(provider.request('instances')['data']==[],'Provider inventory not empty')
    current=next(x for x in provider.request('instance-types')['data'] if x['metadata']['type']=='gpu_1x_a10')
    rate=current['metadata']['hourly_rate']
    require(current['architecture']=='x86_64' and 'us-east-1' in current['regions'] and 0<rate<=1.29,'Approved rate/capacity unavailable')
    require(m['image'] in provider.request('images')['data'],'Prepared image unavailable')
    save('launch_preflight.json',dict(epoch=time.time(),instances=[],instance=current,image=m['image'],manifest_sha256=MANIFEST))
    identity=BASE/'ssh_identity'
    require(not identity.exists() and not Path(str(identity)+'.pub').exists(),'Temporary key path occupied')
    name='shimmer-ordinary-final-776d8c1'
    registration=iid=ssh=host=None
    options=[]
    start=time.time()
    def phase(label):
        save('CURRENT_PHASE.json',dict(phase=label,epoch=time.time(),instance_id=iid,
            estimated_infrastructure_usd=max(0,time.time()-start)*rate/3600 if iid else 0))
        print(label,flush=True)
    def transport(label,argv,timeout=60,required=True):
        phase(label)
        if iid:
            remaining=start+7/rate*3600-240-time.time()
            require(remaining>0,'Termination reserve reached')
            timeout=min(timeout,max(1,int(remaining)))
        begin=time.time()
        try:r=subprocess.run(argv,capture_output=True,timeout=timeout)
        except subprocess.TimeoutExpired:
            save(label+'_timing.json',dict(start_epoch=begin,seconds=time.time()-begin,timeout=True))
            raise RuntimeError('Transport deadline exceeded') from None
        data=r.stdout+r.stderr
        hits=credential_locations(data,label)
        if hits:
            save('SECURITY_STOP.json',dict(file=label,line=hits[0]['line']))
            raise RuntimeError('Possible credential detected; diagnostics withheld')
        (BASE/(label+'.log')).write_bytes(data)
        save(label+'_timing.json',dict(start_epoch=begin,seconds=time.time()-begin,returncode=r.returncode))
        require(not required or r.returncode==0,'Execution phase failed: '+label)
        return r
    def remote(label,command,timeout=60,required=True):
        require(ssh is not None,'SSH unavailable')
        if time.time()>start+5/rate*3600 and label not in {'stop_workload','pack_evidence','evidence_hash','final_gpu_state'}:
            save('soft_budget_assessment.json',dict(phase=label,epoch=time.time(),continued=False,
                reason='No justified remaining-work estimate; preserve evidence and terminate'))
            raise RuntimeError('Soft budget reached before next phase')
        return transport(label,ssh+[command],timeout,required)
    try:
        phase('temporary_ssh_identity')
        r=subprocess.run(['ssh-keygen','-t','ed25519','-N','','-f',str(identity),'-C',name],capture_output=True)
        require(r.returncode==0,'Temporary SSH generation failed')
        registration=provider.request('ssh-keys',dict(name=name,public_key=Path(str(identity)+'.pub').read_text().strip()))['data'][0]
        save('ssh_registration.json',registration)
        start=time.time()
        with (BASE/'LAUNCH_INTENT.json').open('x',encoding='utf8') as stream:
            json.dump(dict(epoch=start,maximum_instances=1,operator_authorized=True,
                execution_manifest_sha256=MANIFEST,seal_sha256=SEAL,controller_sha256=sha(__file__)),stream)
        phase('launch_one_a10')
        launch=provider.request('instance-operations/launch',dict(region_name='us-east-1',
            instance_type_name='gpu_1x_a10',ssh_key_names=[registration['name']],quantity=1,
            name=name,image={'id':m['image']['id']}))['data']
        iid=launch['instance_ids'][0]
        save('launch.json',dict(instance_id=iid,epoch=start,hourly_rate=rate))
        permit=dict(operator_authorized=True,action='one-ordinary-final-cloud-run',
            execution_manifest_sha256=MANIFEST,seal_sha256=SEAL,source_commit=m['source_commit'],
            preparation_commit='776d8c131279c88798e4a27d6099c98e8d5d7643',controller_sha256=sha(__file__),
            soft_budget_usd=5,hard_ceiling_usd=7,provider='Lambda',instance_type='gpu_1x_a10',region='us-east-1',
            instance_id=iid,hourly_rate=rate,active_start_epoch=start,maximum_instances=1,maximum_runs=1,
            protected_data=False,multi_round=False,automatic_full_run_retry=False,
            authorization='Explicit operator approval in conversation for this manifest and scope')
        save('operator_authorization.json',permit)
        flags=getattr(subprocess,'DETACHED_PROCESS',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'CREATE_NO_WINDOW',0)
        watchdog=subprocess.Popen([sys.executable,str(ROOT/'tools/ordinary_final_watchdog.py'),'--bundle',str(BASE),
            '--credential-file',str(CREDENTIAL),'--arm'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,creationflags=flags)
        save('watchdog_process.json',dict(pid=watchdog.pid))
        for _ in range(30):
            if (BASE/'WATCHDOG_ARMED.json').exists():break
            require(watchdog.poll() is None,'Watchdog exited before arming')
            time.sleep(.5)
        require((BASE/'WATCHDOG_ARMED.json').exists(),'Watchdog did not arm')
        phase('activation')
        while time.time()-start<600:
            state=poll_state(provider,iid,BASE)
            if state['status']=='active' and state.get('public_ip'):break
            time.sleep(5)
        else:raise RuntimeError('Activation timeout')
        require(state['hourly_rate']==rate,'Activated rate changed')
        save('activation.json',dict(seconds=time.time()-start,metadata=state))
        host='ubuntu@'+state['public_ip']
        options=['-i',str(identity),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new',
            '-o','UserKnownHostsFile='+str(BASE/'known_hosts'),'-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2']
        ssh=['ssh',*options,host]
        for n in range(30):
            if transport('ssh_ready_'+str(n),ssh+['true'],20,False).returncode==0:break
            time.sleep(5)
        else:raise RuntimeError('SSH not ready')
        remote('python_gate',"/usr/bin/python3.12 -I -S -c 'import sys;assert sys.version_info[:3]==(3,12,3);print(sys.version)'",30)
        remote('fresh_directory','test ! -e '+REMOTE+' && mkdir -p '+REMOTE+'/project',30)
        support=['project.tar.gz','execution_manifest.json','seal.json','operator_authorization.json',*m['support_files']]
        transport('support_transfer',['scp',*options,*[str(BASE/n) for n in support],host+':'+REMOTE+'/'],300)
        transport('assets_transfer',['scp',*options,str(ROOT/assets['path']),host+':'+REMOTE+'/assets.tar'],10800)
        prefix='cd '+REMOTE+' && '
        remote('archive_integrity',prefix+"printf '%s\\n' "+shlex.quote(m['source_archive_sha256']+'  project.tar.gz')+' '+shlex.quote(assets['sha256']+'  assets.tar')+' | sha256sum -c -',300)
        remote('extract_payload',prefix+'tar -xzf project.tar.gz -C project && tar -xf assets.tar',900)
        remote('create_environment',prefix+'/usr/bin/python3.12 -m venv venv',180)
        exe=REMOTE+'/venv/bin/python'
        remote('install_pinned_wheels',prefix+exe+' -m pip --disable-pip-version-check install --no-index --find-links wheels --require-hashes -r install.lock',1800)
        remote('dependency_closure',prefix+exe+' -m pip check',120)
        remote('gpu_metadata','nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader',30)
        receipt=None
        for _ in range(5):
            try:receipt=read(BASE/'WATCHDOG_ARMED.json');break
            except json.JSONDecodeError:time.sleep(.1)
        require(receipt is not None and time.time()-receipt['heartbeat_epoch']<20,'Watchdog heartbeat stale')
        save('watchdog_transfer_receipt.json',receipt)
        transport('watchdog_receipt_transfer',['scp',*options,str(BASE/'watchdog_transfer_receipt.json'),host+':'+REMOTE+'/WATCHDOG_ARMED.json'],30)
        # Exactly one entry-point invocation. A nonzero return is evidence, never
        # permission to patch the sealed source, remove RUN_CLAIMED or try again.
        with (BASE/'WORKLOAD_LAUNCH_INTENT.json').open('x',encoding='utf8') as stream:
            json.dump(dict(epoch=time.time(),maximum_runs=1,command=exe+' -B '+REMOTE+'/ordinary_final_run.py --bundle '+REMOTE+' --execute'),stream)
        remaining=int(start+7/rate*3600-840-time.time())
        require(remaining>0,'Workload budget exhausted')
        r=remote('ordinary_workload',prefix+exe+' -B '+REMOTE+'/ordinary_final_run.py --bundle '+REMOTE+
            ' --execute > workload.stdout.log 2> workload.stderr.log',remaining,False)
        save('workload_return.json',dict(exit_code=r.returncode,epoch=time.time(),full_run_retried=False))
    except Exception as exc:
        save('controller_failure.json',dict(error_type=type(exc).__name__,message=str(exc) if isinstance(exc,RuntimeError) else 'Controller failure; see phase evidence'))
        print('Controller stopped:',type(exc).__name__,flush=True)
    finally:
        if iid is None and (BASE/'LAUNCH_INTENT.json').exists():
            matches=[x for x in provider.request('instances')['data'] if x.get('name')==name]
            require(len(matches)<=1,'Ambiguous launch recovery; inspect inventory')
            if matches:iid=matches[0]['instance_id']
        if iid:
            if ssh:
                try:
                    remote('stop_workload',"pkill -TERM -f '"+REMOTE+"/[o]rdinary_final_run.py' || true",30,False)
                    remote('final_gpu_state','nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader',30,False)
                    pack="""import pathlib,tarfile,json,hashlib
b=pathlib.Path('.'); paths=[]
for root in ['evidence','project/durable','project/ontology','project/logs','project/output']:
 p=b/root
 if p.exists():paths.extend(x for x in p.rglob('*') if x.is_file())
paths.extend(p for p in b.iterdir() if p.is_file() and (p.suffix in ('.json','.log') or p.name=='RUN_CLAIMED'))
manifest={}
with tarfile.open('collected_evidence.tar.gz','w:gz') as archive:
 for p in sorted(set(paths)):
  h=hashlib.sha256(p.read_bytes()).hexdigest();manifest[p.as_posix()]={'sha256':h,'bytes':p.stat().st_size};archive.add(p,arcname=p.as_posix(),recursive=False)
pathlib.Path('remote_collection_manifest.json').write_text(json.dumps(manifest,indent=2))
"""
                    remote('pack_evidence','cd '+REMOTE+' && /usr/bin/python3.12 -c '+shlex.quote(pack),180)
                    r=remote('evidence_hash','sha256sum '+REMOTE+'/collected_evidence.tar.gz',60)
                    digest=r.stdout.decode().split()[0]
                    transport('evidence_download',['scp',*options,host+':'+REMOTE+'/collected_evidence.tar.gz',host+':'+REMOTE+'/remote_collection_manifest.json',str(BASE)+'/'],600)
                    require(sha(BASE/'collected_evidence.tar.gz')==digest,'Collected archive hash mismatch')
                    save('collection_integrity.json',dict(sha256=digest,bytes=(BASE/'collected_evidence.tar.gz').stat().st_size,verified_epoch=time.time()))
                except Exception as exc:
                    save('collection_failure.json',dict(error_type=type(exc).__name__,partial_evidence=True))
            (BASE/'TERMINATE_REQUEST').touch()
            phase('terminate_instance')
            while True:
                try:
                    if termination(provider,iid,BASE,start,rate):break
                except Exception:pass
                time.sleep(5)
            save('instances_after.json',provider.request('instances')['data'])
        if registration:
            provider.request('ssh-keys/'+registration['id'],method='DELETE')
            require(all(x['id']!=registration['id'] for x in provider.request('ssh-keys')['data']),'Temporary SSH registration remains')
        identity.unlink(missing_ok=True);Path(str(identity)+'.pub').unlink(missing_ok=True)
        independent=LambdaExperiment(CREDENTIAL)
        inventory=independent.request('instances')['data'];keys=independent.request('ssh-keys')['data']
        absent=registration is None or all(x['id']!=registration['id'] for x in keys)
        local_absent=not identity.exists() and not Path(str(identity)+'.pub').exists()
        save('independent_inventory_confirmation.json',dict(instances=inventory,temporary_ssh_registration_absent=absent,
            local_key_material_absent=local_absent,epoch=time.time(),no_persistent_storage_created=True))
        require(inventory==[] and absent and local_absent,'Independent cleanup failed')
        save('cleanup.json',dict(temporary_provider_ssh_removed=True,local_ssh_material_removed=True,inventory_empty=True))
        phase('terminated_and_cleaned')


if __name__=='__main__':execute()
