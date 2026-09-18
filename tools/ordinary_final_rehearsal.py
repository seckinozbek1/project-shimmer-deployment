"""Full phase-sequence rehearsal of the ordinary final controller against a local Linux target.

The real controller execute() runs its own command strings, in its own order, through
its own detached-phase transport, against a local Ubuntu (WSL) standing in for the
instance: every `ssh host cmd` becomes `bash -c cmd` on that Ubuntu, one shell layer as
sshd runs it, and every `scp` becomes a copy across the Windows and Linux mounts. The
provider is mocked (no instance exists), the watchdog is a local heartbeat thread and
the temporary ssh identity is real. The sealed project archive, the runner, the
observer, the install lock and the wheels are the real sealed ones; the asset archive
is a rehearsal build with the same wheels and Hub refs but no model weights, because
model loading is out of scope. The runner therefore starts, passes its cache, runtime,
adapter and pair admissions, and refuses at the hardware admission (this GPU is not an
A10), which is the designed boundary.

Two polarities of the controller's own precondition are rehearsed in sequence: an
absent remote root (the run proceeds to the workload) and a present one (the run
refuses at fresh_directory and tears down). Further preconditions with both
polarities: archive integrity (a corrupted archive fails sha256sum), the single
workload claim (a second invocation is refused), a present temporary key path.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'scripts')]
import ordinary_final_cloud as controller
from ordinary_final_run import read, write, sha, require, cache_ref_bytes
from ordinary_final_controller_checks import FakeProvider, INSTANCE
from prepare_ordinary_final_assets import build_assets

SOURCE_BUNDLE = ROOT / 'docs/fix/ordinary_final_cloud_run_v4'
WORK = ROOT / '.tmp/rehearsal'
WHEELS = ROOT / 'output/cloud_wheels/ordinary_final_cp312'
LINUX_ROOT = '/home/seckinozbek/shimmer-rehearsal'
REMOTE = LINUX_ROOT + '/shimmer-ordinary-final'
DISTRO = 'Ubuntu'


def linux(command, timeout=600, stdin=None):
    """One command through exactly one Linux shell, as sshd runs `ssh host cmd`."""
    return subprocess.run(['wsl.exe', '-d', DISTRO, '-e', 'bash', '-c', command], capture_output=True, timeout=timeout, input=stdin)


def to_linux(path):
    p = Path(path).resolve()
    return '/mnt/' + p.drive[0].lower() + p.as_posix()[2:]


class LinuxTransport:
    """The controller's ssh, scp and ssh-keygen calls, executed against the local Ubuntu."""
    def __init__(self, base):
        self.base = base
        self.calls = []

    def run(self, argv, capture_output=True, timeout=None):
        self.calls.append((list(argv), timeout))
        if argv[0] == 'ssh-keygen':
            return subprocess.run(argv, capture_output=True, timeout=timeout)
        if argv[0] == 'ssh':
            return linux(argv[-1], timeout=timeout or 600)
        assert argv[0] == 'scp', argv
        operands = []
        skip = False
        for token in argv[1:]:
            if skip:
                skip = False
                continue
            if token in ('-i', '-o'):
                skip = True
                continue
            if token.startswith('-'):
                continue
            operands.append(token)
        *sources, destination = operands
        if ':' in destination and not sources[0].split(':')[0].startswith('ubuntu@'):
            target = destination.split(':', 1)[1]
            script = ''
            if target.endswith('/'):
                script += 'mkdir -p ' + shlex.quote(target) + ' && '
            script += ' && '.join('cp ' + shlex.quote(to_linux(s)) + ' ' + shlex.quote(target) for s in sources)
            return linux(script, timeout=timeout or 600)
        local = to_linux(destination)
        script = ' && '.join('cp ' + shlex.quote(s.split(':', 1)[1]) + ' ' + shlex.quote(local + '/') for s in sources)
        return linux(script, timeout=timeout or 600)

    def popen(self, argv, **kwargs):
        stop = threading.Event()
        base = self.base

        def heartbeat():
            while not stop.is_set() and not (base / 'TERMINATION_VERIFIED.json').exists():
                write(base / 'WATCHDOG_ARMED.json', dict(instance_id=INSTANCE, pid=os.getpid(), heartbeat_epoch=time.time(),
                                                        execution_manifest_sha256=sha(base / 'execution_manifest.json')))
                stop.wait(2)
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        return SimpleNamespace(pid=os.getpid(), poll=lambda: None, stop=stop)


def rehearsal_assets(source_manifest):
    """The wheels and Hub refs of the sealed manifest, with every snapshot's model weights left out."""
    models = []
    for model in source_manifest['models']:
        files = {n: e for n, e in model['files'].items() if not n.endswith('.safetensors')}
        item = dict(model_id=model['model_id'], revision=model['revision'], files=files)
        ref = cache_ref_bytes(item)
        item['cache_ref'] = dict(bytes=len(ref), sha256=hashlib.sha256(ref).hexdigest())
        models.append(item)
    archive = WORK / 'assets.tar'
    receipt = WORK / 'assets.json'
    if archive.exists() and receipt.exists():
        return read(receipt), models
    if archive.exists():
        archive.unlink()
    assets = build_assets(archive, models, source_manifest['wheels'], Path.home() / '.cache/huggingface/hub', WHEELS)
    write(receipt, assets)
    return assets, models


def make_bundle(name, assets, models):
    """A rehearsal bundle: the sealed archive, runner, observer, lock and support files, a rehearsal manifest."""
    base = WORK / name
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    for file in ('project.tar.gz', 'ordinary_final_run.py', 'ordinary_final_summary.py', 'cloud_run_observer.py', 'topology.json',
                 'install.lock', 'runtime.candidate.lock', 'provider_inventory.json'):
        shutil.copyfile(SOURCE_BUNDLE / file, base / file)
    m = read(SOURCE_BUNDLE / 'execution_manifest.json')
    m['models'] = models
    m['assets_archive'] = assets
    m['classification'] = 'REHEARSAL_NOT_AUTHORIZED'
    m['rehearsal'] = dict(source_bundle=SOURCE_BUNDLE.relative_to(ROOT).as_posix(), model_weights_included=False,
                          provider='mocked', transport='local Ubuntu shell')
    write(base / 'execution_manifest.json', m)
    write(base / 'seal.json', dict(execution_manifest_sha256=sha(base / 'execution_manifest.json'), source_commit=m['source_commit'],
                                   operator_authorized=False, classification='REHEARSAL_NOT_AUTHORIZED'))
    write(base / 'AUTHORIZED_LOCAL_REVERIFICATION.json', dict(passed=True, rehearsal=True))
    write(base / 'assets_transfer_archive.json', dict(path=(WORK / 'assets.tar').relative_to(ROOT).as_posix(), bytes=assets['bytes'],
                                                       sha256=assets['sha256'], manifest_sha256=sha(base / 'execution_manifest.json')))
    return base


def run_controller(base, remote_root_present):
    """Execute the real controller against the Linux target; return the console lines and failure."""
    linux('rm -rf ' + shlex.quote(REMOTE) + ' ' + shlex.quote(controller.phases_dir(REMOTE)) + '; mkdir -p ' + shlex.quote(LINUX_ROOT)
          + ('; mkdir -p ' + shlex.quote(REMOTE) if remote_root_present else ''))
    FakeProvider.state = None
    transport = LinuxTransport(base)
    fake_subprocess = SimpleNamespace(run=transport.run, Popen=transport.popen, TimeoutExpired=subprocess.TimeoutExpired,
                                      CompletedProcess=subprocess.CompletedProcess, DEVNULL=subprocess.DEVNULL,
                                      DETACHED_PROCESS=8, CREATE_NEW_PROCESS_GROUP=512, CREATE_NO_WINDOW=0)
    console = io.StringIO()
    with patch.object(controller, 'BASE', base), patch.object(controller, 'REMOTE', REMOTE), \
            patch.object(controller, 'MANIFEST', sha(base / 'execution_manifest.json')), \
            patch.object(controller, 'SEAL', sha(base / 'seal.json')), \
            patch.object(controller, 'PREPARATION', 'rehearsal'), patch.object(controller, 'INSTANCE_NAME', 'shimmer-rehearsal'), \
            patch.object(controller, 'LambdaExperiment', FakeProvider), patch.object(controller, 'subprocess', fake_subprocess), \
            contextlib.redirect_stdout(console):
        controller.execute()
    failure = base / 'controller_failure.json'
    return transport, console.getvalue().splitlines(), (read(failure) if failure.exists() else None)


def workload_stderr(base):
    """The runner's stderr from the collected evidence archive, or '' without one."""
    evidence = base / 'collected_evidence.tar.gz'
    if not evidence.exists():
        return ''
    with tarfile.open(evidence) as archive:
        for member in archive.getmembers():
            if member.name.endswith('workload.stderr.log'):
                return archive.extractfile(member).read().decode('utf8', 'replace')
    return ''


def phase_receipts(base):
    rows = {}
    for path in sorted(base.glob('*_timing.json')):
        name = path.name[:-len('_timing.json')]
        if name.endswith(('_start', '_collect', '_poll')):
            continue
        rows[name] = read(path)
    return rows


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    started = time.time()
    require(linux('echo ready').stdout.strip() == b'ready', 'Linux target unavailable')
    source = read(SOURCE_BUNDLE / 'execution_manifest.json')
    assets, models = rehearsal_assets(source)
    report = dict(passed=False, target=dict(distro=linux('. /etc/os-release; echo $PRETTY_NAME').stdout.decode().strip(),
                                            python=linux('/usr/bin/python3.12 -c "import sys;print(sys.version.split()[0])"').stdout.decode().strip(),
                                            gpu=linux('nvidia-smi --query-gpu=name --format=csv,noheader').stdout.decode().strip()),
                  rehearsal_assets=dict(bytes=assets['bytes'], members=len(assets['members']), model_weights_included=False),
                  source_bundle=SOURCE_BUNDLE.relative_to(ROOT).as_posix(), polarities={}, preconditions={}, unrehearsed={})

    # Polarity 1: absent remote root; the full sequence through the workload's admission refusal and teardown.
    base = make_bundle('absent_root', assets, models)
    transport, console, failure = run_controller(base, remote_root_present=False)
    phases = phase_receipts(base)
    workload = read(base / 'workload_return.json') if (base / 'workload_return.json').exists() else None
    stderr_text = ''
    evidence = base / 'collected_evidence.tar.gz'
    if evidence.exists():
        with tarfile.open(evidence) as archive:
            for member in archive.getmembers():
                if member.name.endswith('workload.stderr.log'):
                    stderr_text = archive.extractfile(member).read().decode('utf8', 'replace')
    refusal = next((line.strip() for line in stderr_text.splitlines() if 'RuntimeError' in line), '')
    report['polarities']['absent_remote_root'] = dict(
        console=console, controller_failure=failure, phases={n: dict(returncode=r.get('returncode'), seconds=round(r.get('seconds', 0), 1),
                                                                     detached=r.get('detached', False), polls=r.get('polls'),
                                                                     unreachable_polls=r.get('unreachable_polls')) for n, r in phases.items()},
        workload_return=workload, workload_refusal_line=refusal,
        runner_reached_hardware_admission='A10 memory admission' in stderr_text,
        evidence_archive_verified=(base / 'collection_integrity.json').exists(),
        torn_down=(base / 'TERMINATION_VERIFIED.json').exists() and read(base / 'CURRENT_PHASE.json')['phase'] == 'terminated_and_cleaned')
    (out / 'absent_root_console.log').write_text('\n'.join(console) + '\n', encoding='utf8')
    (out / 'absent_root_workload.stderr.log').write_text(stderr_text, encoding='utf8')

    # Precondition: the single workload claim, second polarity (a second invocation is refused).
    intent = read(base / 'WORKLOAD_LAUNCH_INTENT.json') if (base / 'WORKLOAD_LAUNCH_INTENT.json').exists() else None
    if intent:
        write(base / 'WATCHDOG_ARMED.json', dict(instance_id=INSTANCE, pid=os.getpid(), heartbeat_epoch=time.time(),
                                                 execution_manifest_sha256=sha(base / 'execution_manifest.json')))
        linux('cp ' + shlex.quote(to_linux(base / 'WATCHDOG_ARMED.json')) + ' ' + shlex.quote(REMOTE + '/WATCHDOG_ARMED.json'))
        second = linux(intent['command'] + ' 2>&1', timeout=300)
        text = second.stdout.decode('utf8', 'replace')
        report['preconditions']['single_workload_claim'] = dict(
            first_invocation_claimed=(linux('test -f ' + shlex.quote(REMOTE + '/RUN_CLAIMED') + ' && echo yes || echo no').stdout.strip() == b'yes'),
            second_invocation_exit=second.returncode, second_invocation_refused='FileExistsError' in text and 'RUN_CLAIMED' in text)

    # Precondition: archive integrity, second polarity (a corrupted archive fails sha256sum -c).
    corrupt = linux('cd ' + shlex.quote(REMOTE) + ' && cp assets.tar assets.corrupt && printf x | dd of=assets.corrupt bs=1 seek=100 conv=notrunc 2>/dev/null; '
                    + "printf '%s\\n' " + shlex.quote(assets['sha256'] + '  assets.corrupt') + ' | sha256sum -c -')
    good = linux('cd ' + shlex.quote(REMOTE) + " && printf '%s\\n' " + shlex.quote(source['source_archive_sha256'] + '  project.tar.gz') + ' '
                 + shlex.quote(assets['sha256'] + '  assets.tar') + ' | sha256sum -c -')
    report['preconditions']['archive_integrity'] = dict(intact_exit=good.returncode, corrupted_exit=corrupt.returncode,
                                                        controller_phase_exit=phases.get('archive_integrity', {}).get('returncode'))

    # Polarity 2: present remote root; the controller must refuse at fresh_directory and tear down.
    base2 = make_bundle('present_root', assets, models)
    transport2, console2, failure2 = run_controller(base2, remote_root_present=True)
    phases2 = phase_receipts(base2)
    report['polarities']['present_remote_root'] = dict(
        console=console2, controller_failure=failure2,
        fresh_directory_exit=phases2.get('fresh_directory', {}).get('returncode'),
        transferred_anything=any(a[0] == 'scp' and any('project.tar.gz' in x for x in a) for a, _ in transport2.calls),
        torn_down=(base2 / 'TERMINATION_VERIFIED.json').exists() and read(base2 / 'CURRENT_PHASE.json')['phase'] == 'terminated_and_cleaned')
    (out / 'present_root_console.log').write_text('\n'.join(console2) + '\n', encoding='utf8')

    # Polarities 3 to 5: the operator-declared provider-side asset copy, against a
    # directory on the Linux target standing in for the attached filesystem. A
    # matching copy is used and nothing is uploaded; a corrupt copy is refused, the
    # upload runs and the copy is left untouched; a missing copy is uploaded and
    # then seeded under its hash-keyed name only after archive_integrity passed.
    mount = LINUX_ROOT + '/nfs'
    copy_path = mount + '/assets-' + assets['sha256'] + '.tar'
    source_copy = shlex.quote(to_linux(WORK / 'assets.tar'))

    def copy_polarity(name, prepare):
        base_c = make_bundle(name, assets, models)
        write(base_c / 'asset_copy_declaration.json', dict(filesystem_name='rehearsal-fs', mount=mount, operator_authorized=True))
        linux('rm -rf ' + shlex.quote(mount) + ' && mkdir -p ' + shlex.quote(mount) + (' && ' + prepare if prepare else ''))
        transport_c, console_c, failure_c = run_controller(base_c, remote_root_present=False)
        phases_c = phase_receipts(base_c)
        receipt = read(base_c / 'asset_copy_receipt.json') if (base_c / 'asset_copy_receipt.json').exists() else None
        digest_after = linux('test -f ' + shlex.quote(copy_path) + ' && sha256sum ' + shlex.quote(copy_path)
                             + " | cut -d' ' -f1 || echo absent").stdout.decode().strip()
        (out / (name + '_console.log')).write_text('\n'.join(console_c) + '\n', encoding='utf8')
        return dict(controller_failure=failure_c, receipt=receipt,
                    phases={n: dict(returncode=r.get('returncode'), seconds=round(r.get('seconds', 0), 1)) for n, r in phases_c.items()},
                    uploaded_assets=any(a[0] == 'scp' and any(x.endswith('/assets.tar') for x in a) for a, _ in transport_c.calls),
                    copy_digest_after=digest_after,
                    runner_reached_hardware_admission='A10 memory admission' in workload_stderr(base_c),
                    torn_down=(base_c / 'TERMINATION_VERIFIED.json').exists() and read(base_c / 'CURRENT_PHASE.json')['phase'] == 'terminated_and_cleaned')

    report['polarities']['asset_copy_match'] = copy_polarity('asset_copy_match', 'cp ' + source_copy + ' ' + shlex.quote(copy_path))
    report['polarities']['asset_copy_mismatch'] = copy_polarity(
        'asset_copy_mismatch', 'cp ' + source_copy + ' ' + shlex.quote(copy_path)
        + ' && printf x | dd of=' + shlex.quote(copy_path) + ' bs=1 seek=100 conv=notrunc 2>/dev/null')
    report['polarities']['asset_copy_missing'] = copy_polarity('asset_copy_missing', '')

    # Precondition: a present temporary key path refuses before any provider action.
    base3 = make_bundle('key_path_present', assets, models)
    (base3 / 'ssh_identity').write_text('leftover', encoding='utf8')
    FakeProvider.state = None
    with patch.object(controller, 'BASE', base3), patch.object(controller, 'MANIFEST', sha(base3 / 'execution_manifest.json')), \
            patch.object(controller, 'SEAL', sha(base3 / 'seal.json')), patch.object(controller, 'LambdaExperiment', FakeProvider), \
            contextlib.redirect_stdout(io.StringIO()):
        try:
            controller.execute()
            key_refusal = None
        except RuntimeError as exc:
            key_refusal = str(exc)
    report['preconditions']['temporary_key_path'] = dict(present_path_refused=key_refusal, launches=FakeProvider.state['launches'] if FakeProvider.state else 0)
    (base3 / 'ssh_identity').unlink()

    report['preconditions']['fresh_directory'] = dict(absent_root_exit=phases.get('fresh_directory', {}).get('returncode'),
                                                      present_root_exit=phases2.get('fresh_directory', {}).get('returncode'))
    report['unrehearsed'] = {
        'provider actions (launch, instance state, terminate, ssh-key registration)': 'mocked; they need the provider',
        'asset upload over scp': 'replaced by a local copy of the rehearsal archive; the real 13 GB upload needs the provider',
        'model weights in the asset archive, their remote hashing and model loading': 'left out by design; the runner refused at hardware admission before any load',
        'hardware admission on an A10': 'this GPU is not an A10, so the runner refuses there; that refusal is the rehearsal boundary',
        'the ssh and scp transports themselves': 'replaced by a local shell and file copies; the polling and detached-phase code is the controller\'s own',
        'the real watchdog process': 'replaced by a local heartbeat thread; its own checks are separate',
        'the provider filesystem attach at launch': 'mocked; a directory on the Linux target stands in for the mounted copy, so the '
                                                    'copy probe, use and seed commands ran through a real shell but no filesystem was attached',
    }
    a, b = report['polarities']['absent_remote_root'], report['polarities']['present_remote_root']
    cm, cx, cs = (report['polarities'][k] for k in ('asset_copy_match', 'asset_copy_mismatch', 'asset_copy_missing'))
    copy_ok = bool(
        cm['controller_failure'] is None and cm['receipt'] and cm['receipt']['state'] == 'MATCH' and cm['receipt']['used']
        and not cm['receipt']['seeded'] and not cm['uploaded_assets'] and cm['phases'].get('archive_integrity', {}).get('returncode') == 0
        and 'asset_copy_seed' not in cm['phases'] and cm['runner_reached_hardware_admission'] and cm['torn_down']
        and cm['copy_digest_after'] == assets['sha256']
        and cx['controller_failure'] is None and cx['receipt'] and cx['receipt']['state'] == 'MISMATCH' and cx['receipt']['suspect']
        and not cx['receipt']['used'] and not cx['receipt']['seeded'] and cx['uploaded_assets'] and 'asset_copy_seed' not in cx['phases']
        and cx['copy_digest_after'] not in ('absent', assets['sha256']) and cx['runner_reached_hardware_admission'] and cx['torn_down']
        and cs['controller_failure'] is None and cs['receipt'] and cs['receipt']['state'] == 'MISSING' and cs['receipt']['seeded']
        and not cs['receipt']['used'] and cs['uploaded_assets'] and cs['phases'].get('asset_copy_seed', {}).get('returncode') == 0
        and cs['copy_digest_after'] == assets['sha256'] and cs['runner_reached_hardware_admission'] and cs['torn_down'])
    report['preconditions']['asset_copy'] = dict(
        match_used_without_upload=bool(cm['receipt'] and cm['receipt']['used'] and not cm['uploaded_assets']),
        mismatch_refused_uploaded_untouched=bool(cx['receipt'] and cx['receipt']['state'] == 'MISMATCH' and cx['uploaded_assets']
                                                 and cx['copy_digest_after'] not in ('absent', assets['sha256'])),
        missing_uploaded_then_seeded=bool(cs['receipt'] and cs['receipt']['seeded'] and cs['copy_digest_after'] == assets['sha256']),
        passed=copy_ok)
    expected_sequence = ['python_gate', 'fresh_directory', 'archive_integrity', 'extract_payload', 'create_environment',
                         'install_pinned_wheels', 'dependency_closure', 'gpu_metadata', 'ordinary_workload', 'stop_workload',
                         'final_gpu_state', 'pack_evidence', 'evidence_hash']
    sequence_ok = all(n in a['phases'] and a['phases'][n]['returncode'] == (None if n == 'ordinary_workload' else 0) or
                      (n == 'ordinary_workload' and a['phases'][n]['returncode'] not in (None, 0)) for n in expected_sequence)
    report['passed'] = bool(
        a['controller_failure'] is None and sequence_ok and a['runner_reached_hardware_admission'] and a['torn_down']
        and a['evidence_archive_verified'] and a['workload_return'] is not None and a['workload_return']['full_run_retried'] is False
        and b['controller_failure'] and b['controller_failure']['message'] == 'Execution phase failed: fresh_directory'
        and b['fresh_directory_exit'] == 1 and not b['transferred_anything'] and b['torn_down']
        and report['preconditions']['archive_integrity']['intact_exit'] == 0 and report['preconditions']['archive_integrity']['corrupted_exit'] != 0
        and report['preconditions']['single_workload_claim']['first_invocation_claimed']
        and report['preconditions']['single_workload_claim']['second_invocation_refused']
        and report['preconditions']['temporary_key_path']['present_path_refused'] == 'Temporary key path occupied'
        and report['preconditions']['temporary_key_path']['launches'] == 0
        and copy_ok)
    report['seconds'] = round(time.time() - started, 1)
    linux('rm -rf ' + shlex.quote(LINUX_ROOT))
    report['linux_target_cleaned'] = linux('test -e ' + shlex.quote(LINUX_ROOT) + ' && echo present || echo absent').stdout.strip() == b'absent'
    (out / 'rehearsal.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf8')
    summary = {k: report[k] for k in ('passed', 'seconds', 'target', 'preconditions', 'unrehearsed')}
    summary['absent_root_phases'] = a['phases']
    summary['absent_root_failure'] = a['controller_failure']
    summary['workload_refusal_line'] = a['workload_refusal_line']
    summary['present_root'] = {k: b[k] for k in ('controller_failure', 'fresh_directory_exit', 'transferred_anything', 'torn_down')}
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--source-bundle', type=Path, default=None,
                        help='the sealed bundle whose archive, runner and locks are rehearsed (default: the v4 bundle)')
    arguments = parser.parse_args()
    if arguments.source_bundle is not None:
        # The archive rehearsed is the one about to be launched, never a stale one.
        SOURCE_BUNDLE = arguments.source_bundle if arguments.source_bundle.is_absolute() else (ROOT / arguments.source_bundle).resolve()
    raise SystemExit(main(arguments.output_dir))
