#!/usr/bin/env python3
"""Plan by default. --execute is only for a manually provisioned, identified GPU."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

from cloud_run_common import budget_deadlines, digest, require, safe_metadata, verify_bundle, verify_files, write_json
from runtime_contract import load_contract, remote_resolver_command, compatible


def host_value(value):
    require(value.startswith('ubuntu@'), 'host must be ubuntu@<public IP>')
    ipaddress.IPv4Address(value.split('@')[1])
    return value


def plan(bundle, host, running_epoch):
    ready = verify_bundle(bundle)
    require(ready.get('runtime_source_preflight_passed') is True,
            'bundle predates runtime/source preflight; reseal locally before provisioning')
    require(ready.get('runtime_contract_sha256') == digest(Path(__file__).with_name('runtime_contract.py')) == digest(bundle / 'runtime_contract.py'),
            'runtime preflight implementation changed; reseal locally')
    require(json.loads((bundle / 'runtime.json').read_text()) == load_contract(),
            'sealed runtime contract differs from current requirement')
    host_value(host)
    exp = json.loads((bundle / 'experiment.json').read_text())
    require(exp['max_runs'] == 1 and exp['source_commit'] == ready['source_commit'], 'invalid experiment identity')
    require(exp['experiment_id'] == ready['experiment_id'] and re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', exp['experiment_id']), 'unsafe experiment ID')
    remote = '/home/ubuntu/shimmer_experiments/' + exp['experiment_id']
    limits = budget_deadlines(exp['hourly_rate_usd'], running_epoch)
    return {'host': host, 'remote_directory': remote, 'experiment_id': exp['experiment_id'], 'hourly_rate': exp['hourly_rate_usd'],
            'max_runs': 1, 'budget': limits, 'steps': ['arm independent local termination watchdog',
            'verify manually provisioned instance identity and IP', 'first SSH success',
            'resolve absolute compatible Python before transfer', 'verify A100 identity/VRAM', 'create exclusive experiment directory',
            'transfer sealed bundle', 'verify transfer/source hashes', 'compile and import source before dependencies',
            'install offline hashed Linux wheels', 'minimal CUDA/PyTorch sanity',
            'concurrent fixed-revision hydration and model hashes', 'run immediately once', 'score and collect',
            'terminate and verify provider status']}


def run_transport(command, timeout, runner=subprocess.run, interactive=False):
    # OpenSSH owns passphrase entry in interactive mode; this tool never reads it.
    return runner(command, check=True, stdout=None if interactive else subprocess.DEVNULL,
                  stderr=None if interactive else subprocess.DEVNULL, timeout=timeout)


def upload_timeout(requested, terminate_epoch, now=None):
    """Bound transfer time while leaving two minutes for cleanup before termination."""
    require(isinstance(requested, (int, float)) and not isinstance(requested, bool)
            and math.isfinite(requested) and requested > 0, 'upload timeout must be positive and finite')
    remaining = terminate_epoch - (time.time() if now is None else now) - 120
    require(remaining > 0, 'insufficient budget remaining for transfer')
    return min(requested, remaining)


def transport_plan(host, bundle, remote, identity_file=None, known_hosts=None, interactive=False, python_executable=None):
    host_value(host)
    require(re.fullmatch(r'/home/ubuntu/shimmer_experiments/[a-z0-9][a-z0-9_-]{0,63}', remote), 'unsafe remote path')
    # Bound dead connections during both long runs and transfers. These options
    # do not impose a time limit on a healthy remote model process.
    options = ['-o', 'BatchMode=no' if interactive else 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
               '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3']
    if identity_file is not None:
        options += ['-i', str(Path(identity_file).resolve()), '-o', 'IdentitiesOnly=yes']
    if known_hosts is not None:
        options += ['-o', 'UserKnownHostsFile=' + Path(known_hosts).resolve().as_posix()]
    ssh = ['ssh', *options, host]
    runtime = load_contract()
    probe = ('import sys,subprocess,ensurepip,platform; assert sys.version.split()[0]==' + repr(runtime['python']) + '; '
             'assert ensurepip.version()==' + repr(runtime['pip']) + '; assert platform.machine()=="x86_64"; '
             'assert tuple(map(int,platform.libc_ver()[1].split("."))) >= (2,35); '
             'r=subprocess.check_output(["nvidia-smi","--query-gpu=name,memory.total",'
             '"--format=csv,noheader,nounits"],text=True).strip().splitlines(); '
             'assert len(r)==1; n,m=r[0].split(","); '
             'assert n.strip()=="NVIDIA A100-SXM4-40GB" and float(m)>=40000')
    # No shell interprets the local command. Remote paths are validated and quoted.
    if python_executable is not None:
        require(python_executable.startswith('/') and '\n' not in python_executable, 'invalid resolved remote Python')
    python_command = shlex.quote(python_executable) if python_executable else '"$SHIMMER_PYTHON"'
    return {'connect': ssh + ['true'],
            'resolve_python': ssh + [remote_resolver_command()],
            'gpu_before_transfer': ssh + [python_command + ' -c ' + shlex.quote(probe)],
            'create': ssh + ['mkdir -p /home/ubuntu/shimmer_experiments && mkdir -- ' + shlex.quote(remote)],
            'upload': ['scp', *options, '-r', str(bundle) + '/.', host + ':' + remote + '/'],
            'ssh': ssh, 'options': options}


def execute(args, runner=subprocess.run, provider=None):
    from cloud_run_watchdog import LambdaTermination, operator_preflight
    bundle = args.bundle.resolve()
    timestamp = datetime.fromisoformat(args.running_since.replace('Z', '+00:00'))
    require(timestamp.tzinfo is not None, 'running-since must include UTC offset')
    epoch = timestamp.timestamp()
    config = plan(bundle, args.host, epoch)
    requested_upload_timeout = getattr(args, 'upload_timeout_seconds', 1200)
    require(isinstance(requested_upload_timeout, (int, float)) and not isinstance(requested_upload_timeout, bool)
            and math.isfinite(requested_upload_timeout) and requested_upload_timeout > 0,
            'upload timeout must be positive and finite')
    config['upload_timeout_seconds'] = requested_upload_timeout
    config['upload_cleanup_reserve_seconds'] = 120
    operator = operator_preflight(getattr(args, 'credential_file', None), getattr(args, 'identity_file', None))
    sealed_operator = json.loads((bundle / 'operator_readiness.json').read_text())
    require(operator['ssh_public_key_sha256'] == sealed_operator['ssh_public_key_sha256'], 'SSH identity differs from prepared key')
    if not args.execute:
        print(json.dumps({'dry_run': True, 'network_contacted': False, **config}, indent=2))
        return 0
    require(args.hourly_rate == config['hourly_rate'], 'operator deployment rate differs from sealed rate')
    require(0 <= time.time()-epoch < 600, 'running timestamp is future or setup already delayed; terminate and prepare locally')
    require(re.fullmatch('[a-f0-9]{32}|[a-f0-9-]{36}', args.instance_id), 'invalid instance ID')
    require(config['budget']['soft_epoch'] > time.time(), 'soft budget already exhausted')
    # This is outside the immutable bundle. It is never uploaded to the instance.
    local = args.collection.resolve() / config['experiment_id']
    local.mkdir(parents=True, exist_ok=False)
    write_json(local / 'deployment_plan.json', config)
    watch_cmd = [sys.executable, str(Path(__file__).with_name('cloud_run_watchdog.py')), '--arm',
                 '--instance-id', args.instance_id, '--hourly-rate', str(config['hourly_rate']),
                 '--running-epoch', str(epoch), '--directory', str(local)]
    if getattr(args, 'credential_file', None):
        watch_cmd += ['--credential-file', str(args.credential_file.resolve())]
    flags = (getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
             | getattr(subprocess, 'CREATE_NO_WINDOW', 0)) if os.name == 'nt' else 0
    watchdog = subprocess.Popen(watch_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=flags, start_new_session=os.name != 'nt')
    for _ in range(100):
        require(watchdog.poll() is None, 'watchdog did not arm')
        if (local / 'WATCHDOG_ARMED.json').exists():
            break
        time.sleep(0.1)
    require((local / 'WATCHDOG_ARMED.json').is_file(), 'watchdog arm timed out')
    provider = provider or LambdaTermination(getattr(args, 'credential_file', None))
    success = False
    remote = config['remote_directory']
    interactive = getattr(args, 'interactive_ssh', False)
    transport = transport_plan(args.host, bundle, remote, args.identity_file, local / 'known_hosts', interactive)
    try:
        state = provider.instance(args.instance_id)
        require(state.get('public_ip') == args.host.split('@')[1] and state.get('status') == 'active', 'instance identity/status mismatch')
        require(state.get('type') == 'gpu_1x_a100_sxm4' and state.get('gpu_count') == 1, 'instance class mismatch')
        require(state.get('hourly_rate') == config['hourly_rate'], 'operator rate differs from reported rate')
        write_json(local / 'instance_metadata.json', safe_metadata(state))
        run_transport(transport['connect'], 60 if interactive else 20, runner, interactive)
        first_ssh = time.time()
        deployment_start = time.time()
        write_json(local / 'lifecycle.json', {'instance_reported_running_epoch': epoch, 'first_ssh_success_epoch': first_ssh,
                                            'deployment_start_epoch': deployment_start})
        try:
            resolved_result = runner(transport['resolve_python'], check=True, capture_output=True, text=True, timeout=60)
        except subprocess.CalledProcessError as exc:
            write_json(local / 'runtime_resolution_failure.json', {
                'required': load_contract()['python_profiles']['sealed_reference'],
                'observed_versions': re.findall(r'observed ([0-9]+\.[0-9]+\.[0-9]+)', exc.stderr or '')})
            raise
        resolved = json.loads(resolved_result.stdout)
        require(compatible(resolved['version'], profile='sealed_reference'), 'remote Python version mismatch')
        write_json(local / 'resolved_remote_interpreter.json', resolved)
        transport = transport_plan(args.host, bundle, remote, args.identity_file, local / 'known_hosts', interactive, resolved['executable'])
        run_transport(transport['gpu_before_transfer'], 60 if interactive else 30, runner, interactive)
        run_transport(transport['create'], 60 if interactive else 20, runner, interactive)
        run_transport(transport['upload'], upload_timeout(requested_upload_timeout, config['budget']['terminate_epoch']),
                      runner, interactive)
        require(watchdog.poll() is None, 'watchdog stopped')
        command = ('cd -- ' + shlex.quote(remote) + ' && ' + shlex.quote(resolved['executable']) + ' cloud_run_remote.py --execute --running-epoch '
                   + str(epoch) + ' --first-ssh-epoch ' + str(first_ssh) + ' --deployment-start-epoch ' + str(deployment_start))
        remaining = config['budget']['terminate_epoch'] - time.time()
        require(remaining > 120, 'insufficient remaining budget')
        run_transport(transport['ssh'] + [command], remaining, runner, interactive)
        collect = ['scp', *transport['options'], '-r', args.host + ':' + remote + '/evidence', str(local)]
        run_transport(collect, min(120, max(1, config['budget']['terminate_epoch']-time.time())), runner, interactive)
        evidence = local / 'evidence'
        hashes = json.loads((evidence / 'collection_hashes.json').read_text())
        verify_files(evidence, hashes, exact=False)
        result = json.loads((evidence / 'result.json').read_text())
        require(result['exit_code'] == 0 and result['completed_runs'] == 1, 'run not completed exactly once')
        success = True
    except Exception as exc:
        write_json(local / 'deployment_failure.json', {'classification': 'ABORTED / NON-BENCHMARK', 'error_type': type(exc).__name__})
        # Prompt termination takes priority over retrieving an incomplete run.
    finally:
        (local / 'TERMINATE_REQUEST').touch()
        # Keep this controller observable; the detached watchdog continues retries if it exits.
        for _ in range(60):
            if (local / 'TERMINATION_VERIFIED.json').is_file():
                break
            time.sleep(1)
        terminated = (local / 'TERMINATION_VERIFIED.json').is_file()
        write_json(local / 'EXPERIMENT_STATUS.json', {'benchmark_valid': success and terminated,
            'classification': 'COMPLETED / COLLECTED / TERMINATED' if success and terminated else 'ABORTED / NON-BENCHMARK',
            'termination_verified': terminated, 'exactly_one_run': success,
            'watchdog_continues_until_verified': not terminated})
    print(json.dumps({'collection': str(local), 'run_collected': success, 'termination_verified': terminated}))
    return 0 if success and terminated else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--instance-id', required=True)
    parser.add_argument('--running-since', required=True, help='Provider boot/billing timestamp in ISO-8601 with offset')
    parser.add_argument('--hourly-rate', type=float, required=True, help='Operator rate; must equal the sealed rate')
    parser.add_argument('--credential-file', type=Path, help='Local private Python config containing LAMBDA_API_KEY; never uploaded')
    parser.add_argument('--identity-file', type=Path, required=True, help='Prepared local SSH private key; never uploaded')
    parser.add_argument('--interactive-ssh', action='store_true', help='Let OpenSSH prompt locally for a protected key; otherwise use batch authentication')
    parser.add_argument('--upload-timeout-seconds', type=float, default=1200,
                        help='Upload timeout (default 1200), capped to leave 120 seconds before the termination deadline')
    parser.add_argument('--collection', type=Path, default=Path('output/cloud_collected'))
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except Exception as exc:
        report = {'deployment_refused': True, 'error_type': type(exc).__name__}
        if args.execute and re.fullmatch('[a-f0-9]{32}|[a-f0-9-]{36}', args.instance_id):
            # Even a local prerequisite discovered AFTER provisioning triggers
            # termination. Never leave a paid instance idle while repairing setup.
            from cloud_run_watchdog import LambdaTermination, watch
            emergency = args.collection.resolve() / ('emergency_' + str(time.time_ns()))
            emergency.mkdir(parents=True)
            (emergency / 'TERMINATE_REQUEST').touch()
            try:
                epoch = datetime.fromisoformat(args.running_since.replace('Z', '+00:00')).timestamp()
                watch(LambdaTermination(args.credential_file), args.instance_id, args.hourly_rate, epoch, emergency)
                report['termination_verified'] = True
            except Exception as stop_error:
                report.update(termination_verified=False, termination_error_type=type(stop_error).__name__,
                              operator_action='Terminate the specified instance immediately and verify provider status.')
        print(json.dumps(report))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
