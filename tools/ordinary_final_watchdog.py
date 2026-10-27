"""Operator-side budget watchdog for one authorized ordinary final run; cannot launch."""
import argparse
import math
import os
from pathlib import Path
import time

from ordinary_final_run import authorization, read, require, selected_candidate, sha, write


def deadlines(start, rate, soft, hard, rate_cap, stop_reserve, terminate_reserve):
    """Turn the manifest's caps into deadlines. Every figure is a sealed manifest value or
    the selected candidate's sealed rate cap; none is typed here."""
    values=(start,rate,soft,hard,rate_cap,stop_reserve,terminate_reserve)
    require(all(isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) for v in values), 'Invalid budget')
    require(start>0 and 0<rate<=rate_cap and 0<soft<hard and 0<terminate_reserve<stop_reserve<hard/rate*3600,
            'Invalid budget bounds')
    return dict(soft=start+soft/rate*3600, stop=start+hard/rate*3600-stop_reserve,
                terminate=start+hard/rate*3600-terminate_reserve, ceiling=start+hard/rate*3600)


def manifest_deadlines(manifest, permit):
    return deadlines(permit['active_start_epoch'],permit['hourly_rate'],manifest['soft_budget_usd'],
                     manifest['hard_ceiling_usd'],selected_candidate(manifest,permit)['max_hourly_rate'],
                     manifest['workload_stop_reserve_seconds'],manifest['termination_reserve_seconds'])


def watch(base, provider, permit, manifest, now=time.time, sleep=time.sleep):
    base=Path(base)
    limits=manifest_deadlines(manifest,permit)
    identity=permit['instance_id']
    requested=False
    # A batch session guards every bundle of the batch; the controller lists them before arming.
    batch=read(base/'batch_manifests.json') if (base/'batch_manifests.json').exists() else []
    while True:
        current=now()
        write(base/'WATCHDOG_ARMED.json',dict(instance_id=identity,pid=os.getpid(),
            heartbeat_epoch=current,execution_manifest_sha256=sha(base/'execution_manifest.json'),
            batch_manifest_sha256s=batch))
        write(base/'cost.json',dict(active_start_epoch=permit['active_start_epoch'],observed_epoch=current,
            estimated_infrastructure_usd=max(0,current-permit['active_start_epoch'])*permit['hourly_rate']/3600,
            hourly_rate=permit['hourly_rate'],invoice=False))
        if current>=limits['soft']:
            write(base/'SOFT_BUDGET_REACHED.json',dict(epoch=current))
        if current>=limits['stop']:
            (base/'STOP_WORKLOAD').touch()
        if requested or current>=limits['terminate'] or (base/'TERMINATE_REQUEST').exists():
            requested=True
            try:
                state=provider.instance(identity)
                if state['status']=='terminated':
                    write(base/'TERMINATION_VERIFIED.json',dict(instance_id=identity,
                        confirmed_epoch=now(),provider='Lambda',status='terminated'))
                    return
                provider.terminate(identity)
            except Exception as exc:
                write(base/'TERMINATION_RETRY.json',dict(error_type=type(exc).__name__,
                    ceiling_at_risk=current>=limits['ceiling']))
        sleep(5)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--credential-file',type=Path,required=True)
    parser.add_argument('--arm',action='store_true',required=True)
    args=parser.parse_args()
    manifest=read(args.bundle/'execution_manifest.json')
    require(sha(args.bundle/'execution_manifest.json')==read(args.bundle/'seal.json')['execution_manifest_sha256'],'Seal mismatch')
    root=Path(__file__).resolve().parents[1]
    for name,digest in manifest['local_control_hashes'].items():
        require(sha(root/name)==digest,'Operator controller source mismatch')
    permit=read(args.bundle/'operator_authorization.json')
    authorization(args.bundle,manifest,permit)
    from cloud_run_watchdog import LambdaTermination
    watch(args.bundle,LambdaTermination(args.credential_file),permit,manifest)
