"""Operator-authorized one-instance execution of the sealed ordinary final run.

No runtime source modification, model acquisition outside the transfer allowlist,
second instance, or full-run retry. Provider diagnostics are allowlisted.

Every launch is a loop launch (IV.3): it needs a launch plan (LAUNCH, set by the bound
wrapper) naming the ledger, the purpose and the measured forecast basis. Before the launch
request the budget guard decides, and the instance name (always `shimmer-loop-`) and its
deadline are written to the ledger; launch and termination lines follow. The instance type
is chosen by the IV.3 type rule from the sealed candidates at the live price, and every cap,
rate cap and reserve is read from the sealed manifest. A sealed run (Annex B) prints counts
and timings only, never touches persistent cloud storage, and writes nothing in the
repository except ledger lines.
"""
import base64
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
import time

from ordinary_final_run import read, write, sha, require
import ordinary_final_run as runner
from cloud_run_common import credential_locations
from lambda_experiment_provider import LambdaExperiment
from run_remote_experiment import poll_state, termination
import loop_budget_guard as guard

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/ordinary_final_cloud_run'
REMOTE='/home/ubuntu/shimmer-ordinary-final'
MANIFEST='dcc3aa913b2e59ca2831bc92009b9f888ca0a23e617f4a8d02acb0761876f223'
SEAL='93d2c5b2fe371f19143abe536569fe7bf15bcf9307b3136826b6440e028a4916'
PREPARATION='776d8c131279c88798e4a27d6099c98e8d5d7643'
INSTANCE_NAME='shimmer-loop-ordinary-final-776d8c1'
# The launch plan (dict), set by the bound wrapper; execute() refuses without one.
LAUNCH=None
BATCH_ARMS=('B3','B1')
BUDGET_KEYS=('soft_budget_usd','hard_ceiling_usd','instance_candidates','a10_reference_rate',
             'workload_stop_reserve_seconds','termination_reserve_seconds')


def save(name,value):write(BASE/name,value)


def utc(epoch):
    return datetime.fromtimestamp(float(epoch),timezone.utc).isoformat()


def launch_plan():
    """The launch plan every loop launch needs, validated; a one-line refusal without it."""
    plan=LAUNCH
    require(isinstance(plan,dict) and plan.get('ledger') and isinstance(plan.get('purpose'),str)
            and plan.get('forecast_minutes') is not None and plan.get('storage_forecast_usd') is not None
            and type(plan.get('forecast_includes_upload')) is bool,
            'Loop launch plan required: ledger, purpose, forecast minutes, storage forecast, upload in forecast')
    # The purpose is a short identifier, refused here, before any provider call, rather than
    # at the intent line after the temporary key is registered.
    guard.require_purpose(plan['purpose'])
    value=dict(read_ledgers=[],r_inputs=None,test_manifest=None,frozen_tag=None,batch=None,report={},
               poll_seconds=guard.POLL_LIMIT_SECONDS,reaped=None,bundle_folder=None)
    value.update(plan)
    return value


FROZEN_TAG=re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}')


def frozen_commit(tag):
    """The commit a frozen tag names, from git at the repository root.

    Only a tag resolves: refs/tags/<name>, annotated or lightweight, peeled to its commit.
    A branch, a commit id, HEAD or any other revision expression is refused, so a sealed
    run is never admitted on a revision that can move or that names no frozen tag."""
    import subprocess as process
    require(isinstance(tag,str) and FROZEN_TAG.fullmatch(tag) is not None and '..' not in tag
            and not tag.endswith(('.','.lock')),'Frozen tag not found')
    result=process.run(['git','rev-parse','--verify','--quiet','refs/tags/'+tag+'^{commit}'],cwd=ROOT,
                       capture_output=True,timeout=30)
    require(result.returncode==0,'Frozen tag not found')
    return result.stdout.decode().strip()


def case_documents(archive):
    """The bundled context documents by id, loaded by the bound pipeline's own corpus rules."""
    with tarfile.open(archive) as tar:
        members={m.name[len('input/context/'):]:tar.extractfile(m).read() for m in tar.getmembers()
                 if m.isfile() and m.name.startswith('input/context/')}
        source=tar.extractfile('scripts/pipeline.py').read()
    return runner.case_corpus_documents(members,source)


def admit(m,seal,plan,base):
    """Declared, sealed and valid, or refused: the workload, the case manifest and (sealed runs
    only) the test manifest, the bundle hash and the frozen tag's commit."""
    workload=runner.admit_workload(m,seal,base)
    if m['multi_round']:
        runner.validate_live_case_manifest(read(base/runner.CASE_MANIFEST),case_documents(base/'project.tar.gz'))
    if workload['exposure']=='sealed':
        require(plan['test_manifest'] and plan['frozen_tag'],'A sealed run needs the test manifest and the frozen tag')
        require(sha(plan['test_manifest'])==seal['test_manifest_sha256'],'Test manifest differs from the seal')
        test=read(plan['test_manifest'])
        require(test.get('archive_sha256')==seal['test_archive_sha256']==m['test_archive_sha256'],'Bundle hash differs from the seal')
        require(frozen_commit(plan['frozen_tag'])==m['source_commit']==test.get('code_commit'),
                'Code commit differs from the frozen tag')
        require(not Path(base).resolve().is_relative_to(Path(ROOT).resolve()),'A sealed run folder must sit outside the repository')
    else:
        require(plan['test_manifest'] is None,'An exposed run takes no test manifest')
    return workload


def consumed(bundle):
    """A bundle launched once, in place (LAUNCH_INTENT.json) or in a run folder (RUN_FOLDER.json)."""
    return (Path(bundle)/'LAUNCH_INTENT.json').exists() or (Path(bundle)/'RUN_FOLDER.json').exists()


def batch_schedule(entries):
    """B3 and B1 on the same items, item by item: (i1,B3),(i1,B1),(i2,B3),(i2,B1)... so a stop
    at any point leaves every finished item paired except, at most, the one in progress."""
    require(isinstance(entries,list) and entries,'Batch entries required')
    items=[]
    for e in entries:
        require(isinstance(e,dict) and set(e)=={'item','arm','bundle'} and e['arm'] in BATCH_ARMS
                and isinstance(e['item'],str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',e['item']),
                'Batch entry needs item, arm (B3 or B1) and bundle')
        if e['item'] not in items:items.append(e['item'])
    schedule=[e for item in items for arm in BATCH_ARMS for e in entries if e['item']==item and e['arm']==arm]
    require(len(schedule)==len(entries)==len(BATCH_ARMS)*len(items),'Every batch item runs B3 and B1 exactly once')
    require(len({str(Path(e['bundle']).resolve()) for e in entries})==len(entries),'Each batch entry has its own bundle')
    return [dict(e,index=k,paired_with=k+1 if e['arm']==BATCH_ARMS[0] else k-1) for k,e in enumerate(schedule)]


def batch_entries(plan,m,assets):
    """Each batch bundle verified locally as the session bundle is, sharing one environment
    and one sealed budget; [] without a batch."""
    if not plan['batch']:return []
    schedule=batch_schedule(plan['batch'])
    require(Path(schedule[0]['bundle']).resolve()==Path(BASE).resolve(),'The first batch entry is the session bundle')
    for e in schedule:
        b=Path(e['bundle']).resolve()
        em=read(b/'execution_manifest.json');es=read(b/'seal.json')
        require(es['execution_manifest_sha256']==sha(b/'execution_manifest.json'),'Batch manifest seal mismatch')
        require(read(b/'AUTHORIZED_LOCAL_REVERIFICATION.json')['passed'],'Batch local reverification missing')
        for name,digest in em['support_files'].items():require(sha(b/name)==digest,'Batch support source changed')
        require(sha(b/'project.tar.gz')==em['source_archive_sha256'],'Batch project archive changed')
        require(em['assets_archive']['sha256']==assets['sha256'] and em['image']==m['image']
                and em['support_files'].get('install.lock')==m['support_files'].get('install.lock')
                and em['local_control_hashes']==m['local_control_hashes'],'Batch bundles share one environment')
        require(all(em[k]==m[k] for k in BUDGET_KEYS),'Batch bundles share the session sealed budget')
        require(em['max_runs']==1 and em['model_mode']=='final','Ordinary final run only')
        admit(em,es,plan,b)
        # Every entry, the session bundle among them: launched once in place (LAUNCH_INTENT.json)
        # or in a run folder with --output-dir (RUN_FOLDER.json) is consumed either way.
        require(not consumed(b),'Batch bundle already consumed')
        e.update(base=b,manifest=em,seal=es,manifest_sha256=sha(b/'execution_manifest.json'),seal_sha256=sha(b/'seal.json'),
                 runner=em.get('runner','ordinary_final_run.py'),
                 folder=Path(BASE)/'batch'/('%02d_%s_%s'%(e['index'],e['item'],e['arm'])))
        require(e['runner'] in em['support_files'],'Batch runner is not a sealed support file')
    return schedule


def park_command(remote,index):
    """Move one finished batch entry aside on the instance, keeping only the shared environment."""
    target=remote.rstrip('/')+'-batch/'+str(index)
    return ('cd '+shlex.quote(remote)+' && mkdir -p '+shlex.quote(target)+' && for f in *; do case "$f" in '
            'hf_cache|wheels|venv|assets.tar) ;; *) mv -- "$f" '+shlex.quote(target+'/')+' ;; esac; done && mkdir project')


CREDENTIAL_REFUSAL='No provider credential file found; set SHIMMER_CONFIG_PATH to the operator credential file'


def credential_path():
    """The provider credential file, resolved at the moment of use and never at import.

    It is the repository's one resolver, agent_wrapper.resolve_config_path(): first
    $SHIMMER_CONFIG_PATH, then the sibling ../api_keys/config.py, then the repo-root
    .env_path pointer. No path is written in this file and nothing is read here; the
    file is only located. With none found the caller is refused in one line that
    names SHIMMER_CONFIG_PATH."""
    scripts=str(Path(__file__).resolve().parents[1]/'scripts')
    if scripts not in sys.path:sys.path.append(scripts)
    import agent_wrapper
    path=agent_wrapper.resolve_config_path()
    require(path is not None,CREDENTIAL_REFUSAL)
    return Path(path)


# A remote phase runs detached from any one connection. Run v3 (2026-09-18) lost a
# phase whose remote work had finished because the single connection carrying it
# stopped delivering and the client never noticed; the workload phase has the same
# shape with the remaining budget as its deadline. So every phase's work now runs
# under setsid/nohup on the instance, writing its output and exit code to files in
# this directory, and completion is polled over fresh short connections until the
# phase's own deadline. An unreachable poll is recorded and retried; it is never a
# phase result. Remote liveness and connection health are two separate facts.
FIRST_POLL=2
POLL_INTERVAL=10
PROGRESS_MARKER='---PROGRESS---'


def phases_dir(remote):
    """The phase bookkeeping directory: a SIBLING of the remote root, never inside it.

    The controller's own fresh_directory phase requires the remote root to be absent.
    Run v4 (2026-09-18) failed at that phase because the launcher created the root
    two seconds earlier by keeping the phase files under it."""
    return remote.rstrip('/')+'-phases'


def detached_launch_command(remote,label,command):
    """One short remote command: store `command` as a script, start it detached, print its pid.

    Two guards close the launch race in which the session's hang-up reaches the child
    between fork and exec, before setsid and nohup have taken effect (seen on a real
    Linux shell one launch in four): the launching shell ignores HUP before forking,
    which the child inherits across fork and exec, and the launcher does not return
    until the detached wrapper has written its started marker. A wrapper that never
    starts fails the launch itself, at once, instead of surfacing later as DEAD."""
    base=phases_dir(remote)
    script,out,err,rc,pid,started=(base+'/'+label+ext for ext in ('.sh','.out','.err','.rc','.pid','.started'))
    encoded=base64.b64encode(command.encode('utf8')).decode('ascii')
    wrapper=('echo started > '+shlex.quote(started)+'; sh '+shlex.quote(script)+' > '+shlex.quote(out)
             +' 2> '+shlex.quote(err)+'; echo $? > '+shlex.quote(rc))
    return ('mkdir -p '+shlex.quote(base)+' && printf %s '+shlex.quote(encoded)+' | base64 -d > '+shlex.quote(script)
            +" && trap '' HUP && (setsid nohup sh -c "+shlex.quote(wrapper)+' > /dev/null 2>&1 < /dev/null & echo $! > '
            +shlex.quote(pid)+'); i=0; while [ ! -f '+shlex.quote(started)+' ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done; '
            +'test -f '+shlex.quote(started)+' && cat '+shlex.quote(pid))


def detached_poll_command(remote,label,progress=None):
    """One short remote command reporting RC=<code>, RUNNING or DEAD, then an optional progress tail."""
    base=phases_dir(remote)+'/'+label
    line=('if [ -f '+shlex.quote(base+'.rc')+' ]; then printf "RC=%s\\n" "$(cat '+shlex.quote(base+'.rc')+')"; '
          'elif kill -0 "$(cat '+shlex.quote(base+'.pid')+' 2>/dev/null)" 2>/dev/null; then echo RUNNING; else echo DEAD; fi')
    if progress:
        # The tail is informational: a progress file not yet written must not turn
        # a successful status poll into an unreachable one.
        line+='; echo '+PROGRESS_MARKER+'; tail -n 12 '+shlex.quote(progress)+' 2>/dev/null || true'
    return line


# A PROVIDER-SIDE ASSET COPY, declared by the operator and off by default. The
# asset archive (13 GB, unchanged since v5) is uploaded on every run and is about
# 70 percent of billed time. With a declaration (asset_copy_declaration.json in
# the bundle: filesystem_name, mount, operator_authorized), the instance is
# launched with that filesystem attached, a probe hashes the copy under its
# hash-keyed name and compares it to the sealed manifest's digest, a MATCH is
# copied into place and the upload skipped, and every other state (MISSING,
# MISMATCH, UNREACHABLE, or a copy that fails) falls back to the upload exactly
# as it runs today. archive_integrity then hashes whatever is on the instance,
# as it always has. A MISSING copy is seeded only after that integrity phase has
# passed, under the hash-keyed name, with no-clobber, so a stale or corrupt file
# is never overwritten; a MISMATCH is recorded as suspect for the operator and
# never replaced by a run. Without a declaration none of this runs and the launch
# body and transfer argv are byte-identical to the v9 path.
ASSET_COPY_STATES=('MATCH','MISSING','MISMATCH','UNREACHABLE')


def asset_copy_declaration(base, digest):
    """The operator's declaration of a provider-side asset copy for THIS bundle, or None
    without one. A declaration is tied to the archive digest it was written from
    (tools/declare_asset_copy.py); one naming another archive is refused, never reused.
    The controller only reads it; it never writes one."""
    path=Path(base)/'asset_copy_declaration.json'
    if not path.exists():return None
    d=read(path)
    require(isinstance(d,dict) and d.get('operator_authorized') is True and isinstance(d.get('filesystem_name'),str)
            and d['filesystem_name'] and isinstance(d.get('mount'),str) and d['mount'].startswith('/'),
            'Asset copy declaration incomplete')
    require(d.get('assets_sha256')==digest,'Asset copy declaration is for another bundle')
    return dict(filesystem_name=d['filesystem_name'],mount=d['mount'].rstrip('/'))


def asset_copy_path(mount,digest):
    """The copy is keyed by the sealed archive's own digest, so a bundle naming a
    different archive can never match an earlier copy."""
    return mount.rstrip('/')+'/assets-'+digest+'.tar'


def asset_copy_probe_command(mount,digest):
    """One remote command printing exactly one of ASSET_COPY_STATES. It computes the
    copy's digest on the instance and compares it to the sealed manifest's value;
    the sidecar this machine could write is never the proof."""
    path=asset_copy_path(mount,digest)
    return ('if ! [ -d '+shlex.quote(mount)+' ] || ! [ -r '+shlex.quote(mount)+' ]; then echo UNREACHABLE; '
            'elif ! [ -f '+shlex.quote(path)+' ]; then echo MISSING; '
            'elif [ "$(sha256sum '+shlex.quote(path)+' | cut -d\' \' -f1)" = '+shlex.quote(digest)+' ]; then echo MATCH; '
            'else echo MISMATCH; fi')


def asset_copy_use_command(mount,digest,remote):
    return 'cp '+shlex.quote(asset_copy_path(mount,digest))+' '+shlex.quote(remote.rstrip('/')+'/assets.tar')


def asset_copy_seed_command(mount,digest,remote):
    """Seed the copy from the archive the instance has ALREADY verified: write beside
    the final name, then move into place with no-clobber, so nothing there is
    ever overwritten by a run."""
    path=asset_copy_path(mount,digest)
    return ('cp '+shlex.quote(remote.rstrip('/')+'/assets.tar')+' '+shlex.quote(path+'.partial')
            +' && mv -n '+shlex.quote(path+'.partial')+' '+shlex.quote(path)+' && test -f '+shlex.quote(path))


def asset_copy_state(returncode,stdout):
    """The probe's word, or UNREACHABLE for a probe that failed or said anything else."""
    if returncode!=0:return 'UNREACHABLE'
    words=stdout.decode('utf8',errors='replace').split()
    return words[0] if words and words[0] in ASSET_COPY_STATES else 'UNREACHABLE'


def poll_outcome(returncode,stdout):
    """Classify one completion poll: (kind, exit_code, progress_lines).

    kind is one of unreachable (the connection failed or answered nonsense: retry),
    running, dead (the wrapper vanished without an exit code) or completed."""
    if returncode!=0:
        return 'unreachable',None,[]
    text=stdout.decode('utf8',errors='replace')
    head,_,tail=text.partition(PROGRESS_MARKER)
    lines=[l.strip() for l in head.splitlines() if l.strip()]
    progress=[l.rstrip() for l in tail.splitlines() if l.strip()]
    first=lines[0] if lines else ''
    if first.startswith('RC='):
        try:return 'completed',int(first[3:].strip()),progress
        except ValueError:return 'unreachable',None,progress
    if first=='RUNNING':return 'running',None,progress
    if first=='DEAD':return 'dead',None,progress
    return 'unreachable',None,progress


def execute():
    require(sha(BASE/'execution_manifest.json')==MANIFEST and sha(BASE/'seal.json')==SEAL,'Authorized seal changed')
    m=read(BASE/'execution_manifest.json')
    seal=read(BASE/'seal.json')
    require(read(BASE/'AUTHORIZED_LOCAL_REVERIFICATION.json')['passed'],'Local reverification missing')
    for name,digest in m['local_control_hashes'].items():require(sha(ROOT/name)==digest,'Controller source changed')
    for name,digest in m['support_files'].items():require(sha(BASE/name)==digest,'Support source changed')
    require(sha(BASE/'project.tar.gz')==m['source_archive_sha256'],'Project archive changed')
    assets=read(BASE/'assets_transfer_archive.json')
    require(assets['manifest_sha256']==MANIFEST and sha(ROOT/assets['path'])==assets['sha256'],'Transfer archive changed')
    require(not (BASE/'LAUNCH_INTENT.json').exists(),'Authorization consumed; no launch retry')
    plan=launch_plan()
    workload=admit(m,seal,plan,BASE)
    sealed=workload['exposure']=='sealed'
    batch=batch_entries(plan,m,assets)
    soft,hard=m['soft_budget_usd'],m['hard_ceiling_usd']
    # The controller's own margins follow from the sealed reserves: it stops issuing remote
    # work a minute before the watchdog's termination reserve, and starts the workload only
    # with a minute more than the runner's own stop reserve.
    transport_reserve=m['termination_reserve_seconds']+60
    workload_reserve=m['workload_stop_reserve_seconds']-60
    # A sealed run never attaches persistent cloud storage, so it never reads or seeds a copy.
    copy=None if sealed else asset_copy_declaration(BASE,assets['sha256'])
    copy_state=None
    record=dict(purpose=plan['purpose'],exposure=workload['exposure'],
                test_manifest_sha256=seal.get('test_manifest_sha256',runner.EXPOSED_NO_MANIFEST),
                multi_round=m['multi_round'],protected_test=m['protected_test'],
                shimmer_inst_finder=m['environment'].get('SHIMMER_INST_FINDER'),
                frozen_tag=plan['frozen_tag'],batch_entries=len(batch),report=dict(plan['report']))
    save('run_record.json',record)
    CREDENTIAL=credential_path()
    provider=LambdaExperiment(CREDENTIAL)
    inventory=provider.request('instances')['data']
    require(inventory==[],'Provider inventory not empty')
    types={}
    def list_types():
        rows=provider.request('instance-types')['data']
        types.update({x['metadata']['type']:x for x in rows})
        return rows
    candidate,region,rate,polls=guard.select_instance(list_types,m['instance_candidates'],m['a10_reference_rate'],
                                                     time,plan['poll_seconds'])
    current=types[candidate['type']]
    if region!=guard.PREFERRED_REGION:copy=None  # the declared filesystem lives in us-east-1
    copy_receipt=dict(declared=copy is not None,used=False,seeded=False,suspect=False,state=None,
                      filesystem_name=copy['filesystem_name'] if copy else None,
                      path=asset_copy_path(copy['mount'],assets['sha256']) if copy else None)
    save('asset_copy_receipt.json',copy_receipt)
    require(copy is not None or plan['forecast_includes_upload'],
            'No asset-copy declaration applies to this bundle: the forecast must include the upload')
    # The launch's own ledger must be one the reaper reads (a mocked launch names its own).
    guard.require_reaped(plan['ledger'],plan['reaped'])
    reserve_minutes=m['workload_stop_reserve_seconds']/60
    # One decision at a time: the lock is held from here through the intent line, and the
    # inventory is read again now, since the type poll above can last 30 minutes (A12).
    lock=guard.acquire_lock(plan['ledger'])
    try:
        inventory=provider.request('instances')['data']
        require(inventory==[],'Provider inventory not empty')
        decision=guard.check(ledgers=[plan['ledger'],*plan['read_ledgers']],forecast_minutes=plan['forecast_minutes'],
                             hourly_rate=rate,storage_forecast_usd=plan['storage_forecast_usd'],now_epoch=time.time(),
                             reserve_minutes=reserve_minutes,provider_names=[x.get('name') for x in inventory],
                             instance_type=candidate['type'],r_inputs=plan['r_inputs'],reaped=plan['reaped'])
        require(decision['cap_usd']+1e-9>=hard,'Loop cap at launch %.2f dollars is below the sealed hard cap %.2f dollars; reseal'
                %(decision['cap_usd'],hard))
        require(hard>=decision['forecast_usd'] and hard/rate*60>=plan['forecast_minutes']+reserve_minutes,
                'Sealed hard cap leaves less than the forecast at the live price')
        require(m['image'] in provider.request('images')['data'],'Prepared image unavailable')
        save('launch_preflight.json',dict(epoch=time.time(),instances=[],instance=current,image=m['image'],manifest_sha256=MANIFEST,
             selected=dict(type=candidate['type'],region=region,hourly_rate=rate,polls=polls),budget=decision))
        identity=BASE/'ssh_identity'
        require(not identity.exists() and not Path(str(identity)+'.pub').exists(),'Temporary key path occupied')
        name=INSTANCE_NAME
        require(name.startswith(guard.PREFIX),'Loop instance names start with '+guard.PREFIX)
    except BaseException:
        guard.release_lock(lock)
        raise
    registration=iid=ssh=host=None
    launch_line=False
    options=[]
    start=time.time()
    intent=False
    held=False
    counter=[0]
    def ledger(event,**fields):
        guard.append(plan['ledger'],guard.ledger_line(event,instance_name=name,type=candidate['type'],region=region,
            price_usd_per_hour=rate,purpose=plan['purpose'],forecast_usd=decision['forecast_usd'],cap_usd=hard,**fields))
    def phase(label):
        counter[0]+=1
        save('CURRENT_PHASE.json',dict(phase=label,epoch=time.time(),instance_id=iid,
            estimated_infrastructure_usd=max(0,time.time()-start)*rate/3600 if iid else 0))
        # B.8: a sealed run's progress is counts and timings only.
        if sealed:print('phase %d at %.0f s'%(counter[0],max(0,time.time()-start)),flush=True)
        else:print(label,flush=True)
    def bounded(timeout):
        if iid:
            remaining=start+hard/rate*3600-transport_reserve-time.time()
            require(remaining>0,'Termination reserve reached')
            timeout=min(timeout,max(1,int(remaining)))
        return timeout
    def transport(label,argv,timeout=60,required=True,announce=True,record=True,tolerate_timeout=False,tag=None,into=None):
        if announce:phase(label)
        key=label if tag is None else label+'_'+tag
        folder=BASE if into is None else into
        timeout=bounded(timeout)
        begin=time.time()
        try:r=subprocess.run(argv,capture_output=True,timeout=timeout)
        except subprocess.TimeoutExpired:
            if tolerate_timeout:
                # A poll that hangs is an unreachable poll, not a phase result.
                return subprocess.CompletedProcess(args=argv,returncode=255,stdout=b'',stderr=b'')
            write(folder/(key+'_timing.json'),dict(start_epoch=begin,seconds=time.time()-begin,timeout=True))
            raise RuntimeError('Transport deadline exceeded') from None
        data=r.stdout+r.stderr
        hits=credential_locations(data,key)
        if hits:
            save('SECURITY_STOP.json',dict(file=key,line=hits[0]['line']))
            raise RuntimeError('Possible credential detected; diagnostics withheld')
        if record:
            (folder/(key+'.log')).write_bytes(data)
            write(folder/(key+'_timing.json'),dict(start_epoch=begin,seconds=time.time()-begin,returncode=r.returncode))
        require(not required or r.returncode==0,'Execution phase failed: '+label)
        return r
    def detached(label,command,timeout,required,tag=None,into=None):
        """Run a remote phase detached from any one connection and poll for its exit code.

        The work runs under setsid/nohup on the instance and writes its output and
        exit code to files; completion is polled over fresh short connections until
        the phase's deadline. An unreachable poll is recorded and retried, never
        counted as the phase's result, so a connection that dies after the remote
        work completed (the v3 failure) cannot consume the phase. The remote work's
        liveness and the connection's health are recorded as two separate facts."""
        phase(label)
        key=label if tag is None else label+'_'+tag
        folder=BASE if into is None else into
        remaining=start+hard/rate*3600-transport_reserve-time.time()
        require(remaining>0,'Termination reserve reached')
        timeout=min(timeout,max(1,int(remaining)))
        begin=time.time()
        deadline=begin+timeout
        progress=REMOTE+'/workload.stderr.log' if label in ('ordinary_workload','batch_workload') else None
        r=transport(label+'_start',ssh+[detached_launch_command(REMOTE,key,command)],60,True,announce=False,tag=tag,into=into)
        lines=r.stdout.decode('utf8',errors='replace').strip().splitlines()
        pid=lines[-1].strip() if lines else ''
        status=dict(phase=label,started_epoch=begin,deadline_epoch=deadline,remote_pid=pid,polls=0,unreachable_polls=0,
                    connection='ok',remote_work='running',last_poll_epoch=time.time(),exit_code=None)
        write(folder/(key+'_status.json'),status);save('phase_status.json',status)
        wait=FIRST_POLL
        while True:
            now=time.time()
            if now>=deadline:
                status.update(remote_work='not finished by the phase deadline')
                write(folder/(key+'_status.json'),status);save('phase_status.json',status)
                raise RuntimeError('Phase deadline exceeded: '+label)
            time.sleep(min(wait,max(0,deadline-now)))
            wait=POLL_INTERVAL
            r=transport(label+'_poll',ssh+[detached_poll_command(REMOTE,key,progress)],30,False,
                        announce=False,record=False,tolerate_timeout=True)
            kind,code,progress_lines=poll_outcome(r.returncode,r.stdout)
            status['polls']+=1;status['last_poll_epoch']=time.time()
            if kind=='unreachable':
                status['unreachable_polls']+=1;status['connection']='unreachable'
                status['remote_work']='unknown (connection unreachable)'
            else:
                status['connection']='ok';status['remote_work']=kind
                if progress_lines:
                    (BASE/'workload_progress.log').write_text('\n'.join(progress_lines)+'\n',encoding='utf8')
            if kind=='completed':status['exit_code']=code
            write(folder/(key+'_status.json'),status);save('phase_status.json',status)
            if kind in ('completed','dead'):break
        base=phases_dir(REMOTE)+'/'+key
        r=transport(label+'_collect',ssh+['cat '+shlex.quote(base+'.out')+' '+shlex.quote(base+'.err')],120,False,
                    announce=False,tag=tag,into=into)
        (folder/(key+'.log')).write_bytes(r.stdout+r.stderr)
        code=status['exit_code']
        write(folder/(key+'_timing.json'),dict(start_epoch=begin,seconds=time.time()-begin,returncode=code,detached=True,
            remote_pid=pid,polls=status['polls'],unreachable_polls=status['unreachable_polls'],remote_work=status['remote_work']))
        require(not required or code==0,'Execution phase failed: '+label)
        return subprocess.CompletedProcess(args=[label],returncode=-1 if code is None else code,stdout=r.stdout,stderr=b'')
    def remote(label,command,timeout=60,required=True,tag=None,into=None):
        require(ssh is not None,'SSH unavailable')
        if time.time()>start+soft/rate*3600 and label not in {'stop_workload','pack_evidence','evidence_hash','final_gpu_state'}:
            save('soft_budget_assessment.json',dict(phase=label,epoch=time.time(),continued=False,
                reason='No justified remaining-work estimate; preserve evidence and terminate'))
            raise RuntimeError('Soft budget reached before next phase')
        return detached(label,command,timeout,required,tag,into)
    def send_receipt(tag=None):
        receipt=None
        for _ in range(5):
            try:receipt=read(BASE/'WATCHDOG_ARMED.json');break
            except json.JSONDecodeError:time.sleep(.1)
        require(receipt is not None and time.time()-receipt['heartbeat_epoch']<20,'Watchdog heartbeat stale')
        save('watchdog_transfer_receipt.json',receipt)
        transport('watchdog_receipt_transfer',['scp',*options,str(BASE/'watchdog_transfer_receipt.json'),host+':'+REMOTE+'/WATCHDOG_ARMED.json'],30,
                  tag=tag)
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
    def collect(label_prefix,into,tag=None):
        """Pack, hash and download the instance's current evidence into `into`, verified."""
        remote(label_prefix+'pack_evidence','cd '+REMOTE+' && /usr/bin/python3.12 -c '+shlex.quote(pack),180,tag=tag,into=into)
        r=remote(label_prefix+'evidence_hash','sha256sum '+REMOTE+'/collected_evidence.tar.gz',60,tag=tag,into=into)
        digest=r.stdout.decode().split()[0]
        transport(label_prefix+'evidence_download',['scp',*options,host+':'+REMOTE+'/collected_evidence.tar.gz',
                  host+':'+REMOTE+'/remote_collection_manifest.json',str(into)+'/'],600,tag=tag,into=into)
        require(sha(into/'collected_evidence.tar.gz')==digest,'Collected archive hash mismatch')
        write(into/'collection_integrity.json',dict(sha256=digest,bytes=(into/'collected_evidence.tar.gz').stat().st_size,
              verified_epoch=time.time()))
    def run_entry(entry,permit,exe,prefix):
        """One batch entry: its own run folder, seal entry, authorization, workload and evidence."""
        k=entry['index'];tag=str(k);folder=entry['folder'];b=entry['base']
        folder.mkdir(parents=True,exist_ok=False)
        write(folder/'execution_manifest.json',entry['manifest']);write(folder/'seal.json',entry['seal'])
        write(folder/'seal_entry.json',dict(index=k,item=entry['item'],arm=entry['arm'],paired_with=entry['paired_with'],
              bundle=b.as_posix(),
              execution_manifest_sha256=entry['manifest_sha256'],seal_sha256=entry['seal_sha256'],
              exposure=entry['seal'].get('exposure','exposed'),
              test_manifest_sha256=entry['seal'].get('test_manifest_sha256',runner.EXPOSED_NO_MANIFEST)))
        write(folder/'operator_authorization.json',dict(permit,execution_manifest_sha256=entry['manifest_sha256'],
              seal_sha256=entry['seal_sha256'],source_commit=entry['manifest']['source_commit'],
              multi_round=entry['manifest']['multi_round'],protected_data=entry['manifest']['protected_test']))
        if k>0:
            remote('batch_park',park_command(REMOTE,k-1),120,tag=tag,into=folder)
            files=[str(b/'project.tar.gz'),str(b/'execution_manifest.json'),str(b/'seal.json'),
                   str(folder/'operator_authorization.json'),*[str(b/n) for n in entry['manifest']['support_files']]]
            transport('batch_transfer',['scp',*options,*files,host+':'+REMOTE+'/'],300,tag=tag,into=folder)
            remote('batch_integrity',prefix+"printf '%s\\n' "+shlex.quote(entry['manifest']['source_archive_sha256']+'  project.tar.gz')
                   +' | sha256sum -c -',300,tag=tag,into=folder)
            remote('batch_extract',prefix+'tar -xzf project.tar.gz -C project',900,tag=tag,into=folder)
            send_receipt(tag)
        with (folder/'WORKLOAD_LAUNCH_INTENT.json').open('x',encoding='utf8') as stream:
            json.dump(dict(epoch=time.time(),maximum_runs=1,index=k),stream)
        remaining=int(start+hard/rate*3600-workload_reserve-time.time())
        require(remaining>0,'Workload budget exhausted')
        r=remote('batch_workload',prefix+exe+' -B '+REMOTE+'/'+entry['runner']+' --bundle '+REMOTE+
                 ' --execute > workload.stdout.log 2> workload.stderr.log',remaining,False,tag=tag,into=folder)
        write(folder/'workload_return.json',dict(exit_code=r.returncode,epoch=time.time(),full_run_retried=False))
        collect('batch_',folder,tag)
    try:
        phase('temporary_ssh_identity')
        r=subprocess.run(['ssh-keygen','-t','ed25519','-N','','-f',str(identity),'-C',name],capture_output=True)
        require(r.returncode==0,'Temporary SSH generation failed')
        registration=provider.request('ssh-keys',dict(name=name,public_key=Path(str(identity)+'.pub').read_text().strip()))['data'][0]
        save('ssh_registration.json',registration)
        start=time.time()
        deadline=start+hard/rate*3600
        # IV.3: the name and the deadline are in the ledger before the launch request.
        ledger('launch_intent',time_utc=utc(start),launch_requested_utc=utc(start),deadline_utc=utc(deadline))
        intent=True
        guard.release_lock(lock);lock=None
        for entry in batch:
            if entry['base']!=Path(BASE).resolve():
                with (entry['base']/'LAUNCH_INTENT.json').open('x',encoding='utf8') as stream:
                    json.dump(dict(epoch=start,batch_session=MANIFEST),stream)
        with (BASE/'LAUNCH_INTENT.json').open('x',encoding='utf8') as stream:
            json.dump(dict(epoch=start,maximum_instances=1,operator_authorized=True,
                execution_manifest_sha256=MANIFEST,seal_sha256=SEAL,controller_sha256=sha(__file__)),stream)
        if plan['bundle_folder'] and Path(plan['bundle_folder']).resolve()!=Path(BASE).resolve():
            # The bundle records its run folder only once the launch intent exists (A6): a
            # refusal before this point leaves the bundle launchable, and after it the
            # bundle refuses a second launch with or without --output-dir.
            with (Path(plan['bundle_folder'])/'RUN_FOLDER.json').open('x',encoding='utf8') as stream:
                json.dump(dict(run_folder=Path(BASE).resolve().as_posix()),stream)
        # Keep this machine awake while an instance can exist; the request ends with the process.
        held=keep_awake('hold')
        save('keep_awake.json',dict(held=held))
        phase('launch_instance')
        launch_body=dict(region_name=region,
            instance_type_name=candidate['type'],ssh_key_names=[registration['name']],quantity=1,
            name=name,image={'id':m['image']['id']})
        if copy:launch_body['file_system_names']=[copy['filesystem_name']]
        launch=provider.request('instance-operations/launch',launch_body)['data']
        iid=launch['instance_ids'][0]
        ledger('launch',time_utc=utc(time.time()),launch_requested_utc=utc(start),instance_id=iid,deadline_utc=utc(deadline))
        launch_line=True
        save('launch.json',dict(instance_id=iid,epoch=start,hourly_rate=rate,instance_type=candidate['type'],region=region))
        permit=dict(operator_authorized=True,action='one-ordinary-final-cloud-run',
            execution_manifest_sha256=MANIFEST,seal_sha256=SEAL,source_commit=m['source_commit'],
            preparation_commit=PREPARATION,controller_sha256=sha(__file__),
            soft_budget_usd=soft,hard_ceiling_usd=hard,provider='Lambda',instance_type=candidate['type'],region=region,
            instance_candidate=candidate,instance_id=iid,hourly_rate=rate,active_start_epoch=start,maximum_instances=1,
            maximum_runs=max(1,len(batch)),protected_data=m['protected_test'],multi_round=m['multi_round'],
            automatic_full_run_retry=False,asset_copy=copy,
            authorization='Explicit operator approval in conversation for this manifest and scope')
        save('operator_authorization.json',permit)
        write(BASE/'batch_manifests.json',[e['manifest_sha256'] for e in batch])
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
        if copy:
            r=remote('asset_copy_probe',asset_copy_probe_command(copy['mount'],assets['sha256']),300,False)
            copy_state=asset_copy_state(r.returncode,r.stdout)
            copy_receipt.update(state=copy_state,suspect=copy_state=='MISMATCH')
            save('asset_copy_receipt.json',copy_receipt)
            if copy_state=='MATCH':
                r=remote('asset_copy_use',asset_copy_use_command(copy['mount'],assets['sha256'],REMOTE),1800,False)
                if r.returncode==0:copy_receipt['used']=True
                else:copy_state='USE_FAILED';copy_receipt['state']=copy_state
                save('asset_copy_receipt.json',copy_receipt)
        if not copy_receipt['used']:
            # The v9 path, byte for byte: the same scp invocation whether no copy was
            # declared or the copy was missing, unreachable, corrupt or unusable.
            transport('assets_transfer',['scp',*options,str(ROOT/assets['path']),host+':'+REMOTE+'/assets.tar'],10800)
        prefix='cd '+REMOTE+' && '
        remote('archive_integrity',prefix+"printf '%s\\n' "+shlex.quote(m['source_archive_sha256']+'  project.tar.gz')+' '+shlex.quote(assets['sha256']+'  assets.tar')+' | sha256sum -c -',300)
        if copy and copy_state=='MISSING':
            # Only after the instance has verified the uploaded bytes, only for an
            # absent copy, never over a stale or corrupt one; a failed seed never
            # fails the run.
            r=remote('asset_copy_seed',asset_copy_seed_command(copy['mount'],assets['sha256'],REMOTE),1800,False)
            copy_receipt['seeded']=r.returncode==0
            save('asset_copy_receipt.json',copy_receipt)
        remote('extract_payload',prefix+'tar -xzf project.tar.gz -C project && tar -xf assets.tar',900)
        remote('create_environment',prefix+'/usr/bin/python3.12 -m venv venv',180)
        exe=REMOTE+'/venv/bin/python'
        remote('install_pinned_wheels',prefix+exe+' -m pip --disable-pip-version-check install --no-index --find-links wheels --require-hashes -r install.lock',1800)
        remote('dependency_closure',prefix+exe+' -m pip check',120)
        remote('gpu_metadata','nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader',30)
        send_receipt()
        if batch:
            # Several bundles in one instance session, item by item, each collected as
            # soon as it finishes, so any stop leaves the finished pairs complete.
            for entry in batch:run_entry(entry,permit,exe,prefix)
        else:
            # Exactly one entry-point invocation. A nonzero return is evidence, never
            # permission to patch the sealed source, remove RUN_CLAIMED or try again.
            with (BASE/'WORKLOAD_LAUNCH_INTENT.json').open('x',encoding='utf8') as stream:
                json.dump(dict(epoch=time.time(),maximum_runs=1,command=exe+' -B '+REMOTE+'/ordinary_final_run.py --bundle '+REMOTE+' --execute'),stream)
            remaining=int(start+hard/rate*3600-workload_reserve-time.time())
            require(remaining>0,'Workload budget exhausted')
            r=remote('ordinary_workload',prefix+exe+' -B '+REMOTE+'/ordinary_final_run.py --bundle '+REMOTE+
                ' --execute > workload.stdout.log 2> workload.stderr.log',remaining,False)
            save('workload_return.json',dict(exit_code=r.returncode,epoch=time.time(),full_run_retried=False))
    except Exception as exc:
        save('controller_failure.json',dict(error_type=type(exc).__name__,message=str(exc) if isinstance(exc,RuntimeError) else 'Controller failure; see phase evidence'))
        if sealed:print('Controller stopped at phase %d'%counter[0],flush=True)
        else:print('Controller stopped:',type(exc).__name__,flush=True)
    finally:
        # A failure before the intent line never leaves the ledger lock behind.
        guard.release_lock(lock)
        recovered=True
        if iid is None and (BASE/'LAUNCH_INTENT.json').exists():
            try:
                matches=[x for x in provider.request('instances')['data'] if x.get('name')==name]
                require(len(matches)<=1,'Ambiguous launch recovery; inspect inventory')
                if matches:iid=matches[0]['instance_id']
            except Exception as exc:
                # Unknown whether an instance exists: the ledger stays open for the reaper,
                # which ends the instance at its deadline and closes the launch by name or id.
                recovered=False
                save('launch_recovery_failure.json',dict(error_type=type(exc).__name__))
        if iid:
            if ssh:
                try:
                    remote('stop_workload',"pkill -TERM -f '"+REMOTE+"/[o]rdinary_final_run.py' || true",30,False)
                    remote('final_gpu_state','nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader',30,False)
                    collect('',BASE)
                except Exception as exc:
                    save('collection_failure.json',dict(error_type=type(exc).__name__,partial_evidence=True))
            (BASE/'TERMINATE_REQUEST').touch()
            phase('terminate_instance')
            while True:
                try:
                    if termination(provider,iid,BASE,start,rate):break
                except Exception:pass
                time.sleep(5)
        if intent and recovered:
            # The ledger is closed first, once the instance is gone, in its own try (A1, A2):
            # a recovered id whose launch line was never written gets that line now, so the
            # launch and its termination share an id, and the termination time is read from
            # either writer's shape of TERMINATION_VERIFIED.json.
            try:
                end=termination_epoch(BASE/'TERMINATION_VERIFIED.json') if iid else time.time()
                if iid and not launch_line:
                    ledger('launch',time_utc=utc(end),launch_requested_utc=utc(start),instance_id=iid,deadline_utc=utc(deadline))
                    launch_line=True
                minutes=max(0,math.ceil((end-start)/60)) if iid else 0
                ledger('termination',time_utc=utc(end),launch_requested_utc=utc(start),instance_id=iid,
                       actual_minutes=minutes,actual_cost=round(rate*minutes/60,4))
            except Exception as exc:
                save('ledger_close_failure.json',dict(error_type=type(exc).__name__))
        if iid:
            save('instances_after.json',provider.request('instances')['data'])
        if held:keep_awake('release')
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
        for entry in batch:
            # Each batch run folder carries the session's launch and cleanup records, so
            # the analyser reads one folder per bundle exactly as it reads a single run.
            if entry['folder'].exists():
                for shared in ('launch.json','independent_inventory_confirmation.json','cleanup.json','run_record.json',
                               'asset_copy_receipt.json'):
                    if (BASE/shared).exists():(entry['folder']/shared).write_bytes((BASE/shared).read_bytes())
        phase('terminated_and_cleaned')


def termination_epoch(path):
    """When termination was verified. Two writers make this file: the controller's termination
    step writes `epoch`, the watchdog writes `confirmed_epoch`; either is read, and with neither
    (or no file) the moment of reading stands in."""
    try:
        value=read(path)
    except (OSError,ValueError):
        return time.time()
    for key in ('epoch','confirmed_epoch'):
        if isinstance(value,dict) and type(value.get(key)) in (int,float):
            return value[key]
    return time.time()


def keep_awake(action):
    """SetThreadExecutionState through the loop's helper; never a power setting."""
    loop=str(Path(__file__).resolve().parent/'loop')
    if loop not in sys.path:sys.path.append(loop)
    try:
        import keep_awake as helper
    except ImportError:
        return False
    return helper.hold() if action=='hold' else helper.release()


if __name__=='__main__':
    # Not an entry point of its own any more (loop stage S2): every launch needs a launch plan,
    # which tools/ordinary_final_bound_cloud.py builds, so this refuses at launch_plan().
    execute()
