"""Maintained single-instance bounded controller. No raw provider responses escape the client.

prepare: local tests, safe inventory, reviewed tracked bundle and decision.
execute: one explicit authorized launch, runtime-gated probes, recovery, termination.
watch: independent budget enforcement for this experiment only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone

from cloud_run_common import require, safe_metadata, write_json, digest, credential_locations
from lambda_experiment_provider import LambdaExperiment
from prepare_cloud_run import git
from prepare_source_layer import manifest as source_manifest
import runtime_contract as runtime

ROOT=Path(__file__).resolve().parents[1]
CONFIGS=('local_models.json','constitution.json','agent_contracts.json')
def utc():return datetime.now(timezone.utc).isoformat()


def poll_state(provider, instance_id, directory):
    # Defense in depth for injected providers; real transport already projects.
    state=safe_metadata(provider.instance(instance_id))
    write_json(Path(directory)/'instance_state.json',dict(utc=utc(),metadata=state))
    return state


def bundle(root, directory):
    root, directory=Path(root),Path(directory)
    tracked=set(git(root,'ls-files','-z').decode().split('\0'))
    source=source_manifest(root)
    for name in CONFIGS:
        p=root/'config'/name
        source['source_files']['config/'+name]=dict(sha256=digest(p),bytes=p.stat().st_size)
    for name in source['source_files']:
        require(name in tracked,'bundle member is not tracked: '+name)
        require(not credential_locations((root/name).read_bytes(),name),'credential detected in bundle member: '+name)
        require(name.split('/')[0] in ('scripts','tools','corpus_ingest','config'),'unexpected bundle member')
    write_json(directory/'source_layer.json',source)
    with tarfile.open(directory/'source.tar.gz','w:gz') as tar:
        for name in source['source_files']:tar.add(root/name,arcname=name,recursive=False)
        tar.add(directory/'source_layer.json',arcname='source_layer.json',recursive=False)
    return dict(file_count=len(source['source_files'])+1,bytes=(directory/'source.tar.gz').stat().st_size,
        sha256=digest(directory/'source.tar.gz'),manifest_sha256=digest(directory/'source_layer.json'),
        tracked_only=True,credentials_excluded=True,operator_data_excluded=True)


def prepare(args):
    base=args.directory; base.mkdir(parents=True,exist_ok=False)
    suites=('lambda_metadata_checks.py','runtime_contract_checks.py','cloud_run_checks.py',
            'cloud_run_transport_checks.py','cloud_run_transfer_checks.py')
    checks=[]
    for suite in suites:
        result=subprocess.run([sys.executable,str(ROOT/'tools'/suite)],capture_output=True,timeout=120)
        require(not credential_locations(result.stdout+result.stderr,suite),'sensitive test diagnostic')
        (base/(suite+'.log')).write_bytes(result.stdout+result.stderr)
        require(result.returncode==0,'local gate failed: '+suite)
        checks.append(dict(suite=suite,passed=True))
    selected=runtime.resolve(root=ROOT)
    preflight=runtime.subprocess_check(selected,ROOT)
    write_json(base/'local_source_preflight.json',preflight)
    status=git(ROOT,'status','--short').decode()
    require(all(line.startswith('?? ') for line in status.splitlines()),'commit tracked source before preparation')
    head=git(ROOT,'rev-parse','HEAD').decode().strip()
    reviewed=bundle(ROOT,base)
    provider=LambdaExperiment(args.credential_file)
    inventory=provider.request('instance-types')['data'];write_json(base/'inventory.json',inventory)
    images=provider.request('images')['data'];write_json(base/'images.json',images)
    available=[x for x in inventory if x['metadata']['gpu_count']==1 and x['architecture']=='x86_64' and x['regions']]
    choice=min(available,key=lambda x:x['metadata']['hourly_rate'])
    require(choice['metadata']['hourly_rate']<=1.29,'no suitable instance within intended hourly price')
    region='us-east-1' if 'us-east-1' in choice['regions'] else choice['regions'][0]
    image=next(x for x in images if x['region']==region and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    initial=provider.request('instances')['data'];write_json(base/'instances_before.json',initial)
    cfg=json.loads((ROOT/'config/local_models.json').read_text());pins=json.loads((ROOT/'tools/cloud_run/models.json').read_text())
    write_json(base/'manifest.json',dict(source_commit=head,git_status=status,bundle=reviewed,instance=choice['metadata'],region=region,image=image,
        hourly_rate=choice['metadata']['hourly_rate'],soft_usd=1,hard_usd=2,reserve_seconds=180,
        name='shimmer-'+base.name,multi_round=False,full_pipeline=False,paid_inference_api=False,
        runtime_contract=runtime.load_contract(),runtime_profile='experiment',environment_policy='Explicit fresh isolated venv from verified image Python; all experiment Python uses final absolute venv executable',
        models={role:dict(id=cfg[role],revision=pins[cfg[role]]) for role in ('active_producer','active_auditor')},
        generation=dict(max_new_tokens=384,max_time_seconds=25,seed=7,do_sample=False),maximum_calls=9,
        probes=['readiness','producer load','one compact PROCESSOR partition','one source-copy comparison','one independent auditor','one required producer-auditor pair','two independent tasks serial/admitted2 only after quality gates','no capacity4 without useful real capacity2'],
        hardware_policy='Cheapest available suitable x86_64 single GPU; prefer 24GB; no second instance'))
    write_json(base/'LOCAL_GATES.json',dict(REMOTE_RETRY_LOCAL_GATES_PASS=True,checks=checks,source_preflight=preflight,bundle=reviewed,source_commit=head))
    print(json.dumps(dict(REMOTE_RETRY_LOCAL_GATES_PASS=True,source_commit=head,bundle=reviewed,hardware=choice['metadata'])))


def termination(provider, iid, base, start, rate):
    state=poll_state(provider,iid,base)
    if state['status']=='terminated':
        end=time.time()
        write_json(base/'TERMINATION_VERIFIED.json',dict(instance_id=iid,utc=utc(),epoch=end,metadata=state,
            billable_duration_upper_bound_seconds=end-start,estimated_cost_upper_bound_usd=(end-start)*rate/3600))
        return True
    provider.terminate(iid)
    if not (base/'termination_requested.json').exists():write_json(base/'termination_requested.json',dict(instance_id=iid,utc=utc(),epoch=time.time()))
    return False


def watch(args):
    base=args.directory; m=json.loads((base/'manifest.json').read_text());info=json.loads((base/'launch.json').read_text())
    iid=info['instance_id'];start=info['epoch'];rate=m['hourly_rate'];provider=LambdaExperiment(args.credential_file)
    deadline=start+2/rate*3600-m['reserve_seconds']
    write_json(base/'WATCHDOG_ARMED.json',dict(pid=os.getpid(),instance_id=iid,deadline_epoch=deadline,utc=utc()))
    while not (base/'TERMINATION_VERIFIED.json').exists():
        write_json(base/'cost.json',dict(utc=utc(),estimated_usd=(time.time()-start)*rate/3600))
        if time.time()>=deadline or (base/'TERMINATE_REQUEST').exists():
            try:
                if termination(provider,iid,base,start,rate):return
            except Exception:write_json(base/'watch_error.json',dict(error='provider termination retry required',utc=utc()))
        time.sleep(5)


def execute(args):
    base=args.directory;m=json.loads((base/'manifest.json').read_text());gate=json.loads((base/'LOCAL_GATES.json').read_text())
    require(gate['REMOTE_RETRY_LOCAL_GATES_PASS'] is True,'local gates not passed')
    require(git(ROOT,'rev-parse','HEAD').decode().strip()==m['source_commit'],'source HEAD changed')
    require(digest(base/'source.tar.gz')==m['bundle']['sha256'],'reviewed archive changed')
    require(not (base/'launch_intent.json').exists(),'one launch only')
    provider=LambdaExperiment(args.credential_file);identity=base/'ssh_identity'
    generated=subprocess.run(['ssh-keygen','-t','ed25519','-N','','-f',str(identity),'-C',m['name']],capture_output=True)
    require(generated.returncode==0,'SSH identity generation failed')
    # Check the private identity is readable by OpenSSH without displaying it.
    check=subprocess.run(['ssh-keygen','-y','-f',str(identity)],capture_output=True)
    require(check.returncode==0,'OpenSSH cannot read temporary identity')
    registration=provider.request('ssh-keys',dict(name=m['name'],public_key=Path(str(identity)+'.pub').read_text().strip()))['data'][0]
    write_json(base/'ssh_registration.json',registration)
    start=time.time();write_json(base/'launch_intent.json',dict(epoch=start,utc=utc(),name=m['name']))
    iid=None;ssh=None;options=None;host=None;remote='/home/ubuntu/'+m['name']
    def transport(label, command, timeout=30, required=True):
        begin=time.time()
        try:p=subprocess.run(command,capture_output=True,timeout=timeout)
        except subprocess.TimeoutExpired:
            write_json(base/(label+'_timing.json'),dict(seconds=time.time()-begin,status='timeout'))
            raise RuntimeError('transport timeout: '+label) from None
        content=p.stdout+p.stderr
        require(not credential_locations(content,label),'sensitive transport diagnostic withheld: '+label)
        (base/(label+'.log')).write_bytes(content)
        write_json(base/(label+'_timing.json'),dict(start_epoch=begin,seconds=time.time()-begin,returncode=p.returncode))
        require(not required or p.returncode==0,'transport failed: '+label)
        return p
    try:
        launched=provider.request('instance-operations/launch',dict(region_name=m['region'],instance_type_name=m['instance']['type'],
            ssh_key_names=[registration['name']],quantity=1,name=m['name'],image=dict(id=m['image']['id'])))['data']
        iid=launched['instance_ids'][0];write_json(base/'launch.json',dict(instance_id=iid,epoch=start,utc=utc()))
        flags=getattr(subprocess,'DETACHED_PROCESS',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'CREATE_NO_WINDOW',0)
        subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'watch','--directory',str(base),'--credential-file',str(args.credential_file)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
        for _ in range(20):
            if (base/'WATCHDOG_ARMED.json').exists():break
            time.sleep(.5)
        require((base/'WATCHDOG_ARMED.json').exists(),'watchdog failed to arm')
        while time.time()-start<600:
            state=poll_state(provider,iid,base)
            if state['status']=='active' and state.get('public_ip'):break
            time.sleep(5)
        else:raise RuntimeError('instance active timeout')
        write_json(base/'provisioning.json',dict(seconds=time.time()-start,metadata=state,utc=utc()))
        require(state['hourly_rate']==m['hourly_rate'],'provider hourly price changed')
        host='ubuntu@'+state['public_ip'];options=['-i',str(identity),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new',
            '-o','UserKnownHostsFile='+str(base/'known_hosts'),'-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2']
        ssh=['ssh',*options,host];sshstart=time.time()
        for attempt in range(30):
            p=transport('ssh_readiness_%02d'%attempt,ssh+['true'],timeout=20,required=False)
            if p.returncode==0:break
            time.sleep(5)
        else:raise RuntimeError('SSH readiness timeout')
        write_json(base/'ssh_ready.json',dict(seconds=time.time()-sshstart,from_launch_seconds=time.time()-start,utc=utc()))
        result=transport('runtime_resolver',ssh+[runtime.remote_resolver_command(profile='experiment')])
        selected=json.loads(result.stdout);write_json(base/'bootstrap_interpreter.json',selected);exe=selected['executable'];require(exe.startswith('/'),'absolute Python required')
        transport('mkdir',ssh+['mkdir '+shlex.quote(remote)])
        transport('source_transfer',['scp',*options,str(base/'source.tar.gz'),host+':'+remote+'/source.tar.gz'],90)
        prefix='cd '+shlex.quote(remote)+' && '
        transport('source_integrity',ssh+[prefix+'printf "%s  source.tar.gz\n" '+m['bundle']['sha256']+' | sha256sum -c - && tar -xzf source.tar.gz'])
        # Verify hashes and compile/import BEFORE creating the isolated package environment.
        verify='import sys,json;from pathlib import Path;sys.path.insert(0,"tools");from cloud_run_common import verify_files;v=json.load(open("source_layer.json"));verify_files(Path.cwd(),{k:x["sha256"] for k,x in v["source_files"].items()},exact=False)'
        transport('source_preflight',ssh+[prefix+shlex.quote(exe)+' -B -c '+shlex.quote(verify)+' && '+shlex.quote(exe)+' -I -S -B tools/runtime_contract.py --source '+shlex.quote(remote)],90)
        transport('isolated_environment',ssh+[prefix+shlex.quote(exe)+' -B -m venv .venv'],90)
        final=remote+'/.venv/bin/python'
        resolved=transport('final_interpreter',ssh+[prefix+shlex.quote(final)+' -B tools/runtime_contract.py --resolve --candidate '+shlex.quote(final)])
        selected=json.loads(resolved.stdout);require(selected['executable']==final,'final interpreter identity mismatch');write_json(base/'resolved_interpreter.json',selected)
        transport('hardware',ssh+['nvidia-smi; lscpu; free -b; df -B1 '+shlex.quote(remote)])
        duration=min(2100,int(start+2/m['hourly_rate']*3600-300-time.time()));require(duration>0,'budget exhausted')
        command=prefix+'SHIMMER_EXPERIMENT_SOURCE_COMMIT='+m['source_commit']+' HF_HUB_DISABLE_TELEMETRY=1 timeout --signal=TERM --kill-after=15 '+str(duration)+' '+shlex.quote(final)+' -B -u tools/prepare_remote_experiment.py --root '+shlex.quote(remote)+' --manifest source_layer.json --output '+shlex.quote(remote+'/evidence')+' --interpreter '+shlex.quote(final)+' --execute --install-missing'
        transport('maintained_preparation_probe',ssh+[command],duration+30)
    except Exception as exc:
        # Local errors may include subprocess command/output; never serialize str(exc).
        write_json(base/'controller_failure.json',dict(error_type=type(exc).__name__,message='bounded controller stopped; inspect safe stage evidence',utc=utc()))
    finally:
        if iid is None:
            matches=[x for x in provider.request('instances')['data'] if x.get('name')==m['name']]
            require(len(matches)<=1,'ambiguous launch recovery')
            if matches:iid=matches[0]['instance_id']
        if iid:
            if ssh:
                try:
                    transport('stop_workloads',ssh+['pkill -TERM -f "[t]ools/prepare_remote_experiment.py|[t]ools/remote_short_burst_probe.py|[t]ools/remote_experiment_models.py" || true'],required=False)
                    transport('remote_process_final',ssh+['pgrep -af "[t]ools/prepare_remote_experiment.py|[t]ools/remote_short_burst_probe.py|[t]ools/remote_experiment_models.py" || true'],required=False)
                    p=transport('pack_evidence',ssh+['cd '+shlex.quote(remote)+' && tar -czf evidence.tar.gz evidence'],required=False)
                    if p.returncode==0:
                        transport('collect',['scp',*options,host+':'+remote+'/evidence.tar.gz',str(base/'evidence.tar.gz')],90)
                        with tarfile.open(base/'evidence.tar.gz') as tar:tar.extractall(base,filter='data')
                        write_json(base/'collection_integrity.json',dict(sha256=digest(base/'evidence.tar.gz'),bytes=(base/'evidence.tar.gz').stat().st_size,tar_valid=True))
                except Exception:write_json(base/'collection_failure.json',dict(message='collection failed; provider teardown still required'))
            (base/'TERMINATE_REQUEST').touch()
            while not (base/'TERMINATION_VERIFIED.json').exists():
                try:
                    if termination(provider,iid,base,start,m['hourly_rate']):break
                except Exception:pass
                time.sleep(5)
        provider.request('ssh-keys/'+registration['id'],method='DELETE')
        require(not any(x['id']==registration['id'] for x in provider.request('ssh-keys')['data']),'SSH registration cleanup unverified')
        identity.unlink(missing_ok=True);Path(str(identity)+'.pub').unlink(missing_ok=True)
        write_json(base/'ssh_cleanup.json',dict(provider_registration_removed=True,local_key_removed=True,utc=utc()))
        print(json.dumps(dict(finished=True,instance_id=iid,termination_verified=(base/'TERMINATION_VERIFIED.json').exists())))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','execute','watch'))
    p.add_argument('--directory',type=Path,required=True);p.add_argument('--credential-file',type=Path,required=True)
    args=p.parse_args();args.directory=args.directory.absolute()
    globals()[args.action](args)
if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps(dict(controller_failed=True,error_type=type(exc).__name__)))
        raise SystemExit(2)
