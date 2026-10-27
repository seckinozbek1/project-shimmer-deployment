"""Mocked controller checks: detached remote phases survive a dead client connection.

Every provider action, ssh, scp, ssh-keygen, the watchdog process and the clock are
replaced. The real controller execute() runs end to end against them, so the
phase sequence, the detached-phase polling, the failure teardown and the cleanup
are the controller's own code paths. No real credential is read (one test reads a
fixture file holding a random sentinel, through the real adapter with only curl
replaced, to prove no key value is ever printed), no network is used, no
instance exists. Run v3 (2026-09-18) is the case under test: a phase whose
remote work completes while the connection carrying it dies must be recognised
as completed, never failed, and the workload must then run.
"""
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time as time_module
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'scripts')]
import agent_wrapper
import cloud_run_common
import cloud_run_watchdog
import lambda_experiment_provider as provider_adapter
import loop_budget_guard as guard
import ordinary_final_cloud as controller
import ordinary_final_bound_cloud as bound
import ordinary_final_run as runner
import ordinary_final_watchdog as watchdog_module
import prepare_ordinary_final_run as sealer
from ordinary_final_run import read, write, sha
import instance_reaper

INSTANCE = 'a' * 32
KEY_ID = 'b' * 32
IMAGE = dict(id='9211995d-2377-4ea8-94d2-18eea01ec3f6', family='gpu-base-24-04', version='24.4.4-2141',
             architecture='x86_64', region='us-east-1')
EVIDENCE = b'collected evidence fixture'
A10_TYPE = dict(metadata=dict(type='gpu_1x_a10', gpu_type='A10 (24 GB PCIe)', gpu_count=1, cpu=30,
                              ram_gib=200, storage_gib=1400, hourly_rate=1.29),
                architecture='x86_64', regions=['us-east-1', 'us-west-1'])
FORECAST_MINUTES = 120
STORAGE_USD = 3.9
# The budget every fixture ledger opens with (its own figure; the guard reads it from the ledger).
FIXTURE_BUDGET_USD = 50.0
LOOP_NAME = 'shimmer-loop-fixture'


def fixture_budget(types=None, reference=1.29):
    """The sealed IV.3 budget a fixture bundle carries: candidates from the fixture inventory and
    the soft (forecast) and hard (per-run cap) figures from the guard's own formula."""
    candidates = guard.instance_candidates(types or [A10_TYPE], reference)
    forecast = guard.forecast_usd(FORECAST_MINUTES, candidates[0]['max_hourly_rate'])
    # The fixture ledger's opening line names no hard stop: the stop is the budget less the margin.
    cap = guard.per_run_cap(forecast, 0.0, 0.0, STORAGE_USD, FIXTURE_BUDGET_USD - guard.RESERVE_USD)
    return dict(instance_candidates=candidates, a10_reference_rate=reference, max_hourly_rate=candidates[0]['max_hourly_rate'],
                region='us-east-1', soft_budget_usd=forecast, hard_ceiling_usd=cap, per_run_cap_usd=cap,
                forecast_minutes=FORECAST_MINUTES, workload_stop_reserve_seconds=900, termination_reserve_seconds=180)


def fixture_manifest(project, assets, **changes):
    value = dict(source_commit='f' * 40, image=IMAGE, support_files={}, local_control_hashes={}, max_runs=1,
                 model_mode='final', multi_round=False, protected_test=False, argv=runner.ARGV,
                 environment=dict(SHIMMER_INST_FINDER='on'), source_archive_sha256=sha(project),
                 assets_archive=dict(filename='assets.tar', sha256=sha(assets), bytes=assets.stat().st_size),
                 **fixture_budget())
    value.update(changes)
    return value


def make_bundle(base, assets, project=b'project fixture', support=None, **changes):
    """A sealed fixture bundle at `base` whose asset archive is `assets` (anywhere)."""
    base.mkdir(parents=True, exist_ok=True)
    (base / 'project.tar.gz').write_bytes(project)
    for name, data in (support or {}).items():
        (base / name).write_bytes(data)
    if support:
        changes['support_files'] = {name: sha(base / name) for name in support}
    write(base / 'execution_manifest.json', fixture_manifest(base / 'project.tar.gz', assets, **changes))
    reseal(base, assets)


def reseal(base, assets, **seal_fields):
    write(base / 'seal.json', dict(execution_manifest_sha256=sha(base / 'execution_manifest.json'), **seal_fields))
    write(base / 'AUTHORIZED_LOCAL_REVERIFICATION.json', dict(passed=True, manifest_sha256=sha(base / 'execution_manifest.json')))
    try:
        path = assets.relative_to(controller.ROOT).as_posix()
    except ValueError:
        path = assets.as_posix()
    write(base / 'assets_transfer_archive.json', dict(path=path, sha256=sha(assets),
          manifest_sha256=sha(base / 'execution_manifest.json'), bytes=assets.stat().st_size))


def open_ledger(path, start=1_000_000.0):
    write_lines(path, [dict(event='budget_open', time_utc=guard.utc(start), loop_start_utc=guard.utc(start), budget_usd=FIXTURE_BUDGET_USD,
                            storage_usd_per_day=0.13, a10_reference_price_usd_per_hour=1.29)])


def write_lines(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def ledger_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def fixture_plan(ledger, **changes):
    # `reaped`: in a fixture the (mocked) reaper reads this ledger, never the loop's real ones.
    value = dict(ledger=ledger, purpose='controller-fixture', forecast_minutes=FORECAST_MINUTES,
                 forecast_includes_upload=True, storage_forecast_usd=STORAGE_USD, reaped=[ledger])
    value.update(changes)
    return value


class FakeClock:
    """time() advances only through sleep(); sleep refreshes the watchdog heartbeat like the live watchdog."""
    def __init__(self, base=None):
        self.now, self.slept = 1_000_000.0, 0.0
        # Only while a fixture run is in progress (run_controller sets it): never the
        # repository's own bundle folder, which is controller.BASE outside a run.
        self.active = False

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(0.0, float(seconds))
        self.slept += max(0.0, float(seconds))
        armed = Path(controller.BASE) / 'WATCHDOG_ARMED.json'
        if self.active and armed.exists():
            row = json.loads(armed.read_text(encoding='utf8'))
            row['heartbeat_epoch'] = self.now
            armed.write_text(json.dumps(row), encoding='utf8')


class FakeProvider:
    """Allowlisted provider surface with shared state across instances, as the live adapter behaves."""
    state = None
    types = None
    ledger = None

    def __init__(self, credential=None):
        if FakeProvider.state is None:
            FakeProvider.state = dict(instances=[], keys=[], launches=0, terminate_calls=0, status={}, credentials=[],
                                      type_reads=0)
        self.s = FakeProvider.state
        # The path the controller handed over, never its contents: nothing is read.
        self.s.setdefault('credentials', []).append(credential)

    def request(self, endpoint, body=None, method=None):
        s = self.s
        if endpoint == 'instances':
            return {'data': [dict(instance_id=i, name=n) for i, n in s['instances']]}
        if endpoint == 'instance-types':
            s['type_reads'] += 1
            types = FakeProvider.types if FakeProvider.types is not None else [A10_TYPE]
            return {'data': json.loads(json.dumps(types(s['type_reads']) if callable(types) else types))}
        if endpoint == 'images':
            return {'data': [dict(IMAGE)]}
        if endpoint == 'ssh-keys' and body is not None:
            s['keys'].append(dict(id=KEY_ID, name=body['name']))
            return {'data': [dict(id=KEY_ID, name=body['name'])]}
        if endpoint == 'ssh-keys':
            return {'data': list(s['keys'])}
        if endpoint.startswith('ssh-keys/') and method == 'DELETE':
            s['keys'] = [k for k in s['keys'] if k['id'] != endpoint.split('/')[1]]
            return {'data': {}}
        if endpoint == 'instance-operations/launch':
            s['launches'] += 1
            s['launch_body'] = dict(body)
            # What the ledger held at the moment of the launch request (IV.3: the name and
            # the deadline are written before it).
            s['ledger_at_launch'] = ledger_rows(FakeProvider.ledger) if FakeProvider.ledger and Path(FakeProvider.ledger).exists() else []
            s['instances'].append((INSTANCE, body['name']))
            s['status'][INSTANCE] = 'active'
            types = FakeProvider.types if FakeProvider.types is not None else [A10_TYPE]
            types = types(s['type_reads']) if callable(types) else types
            s['launch_rate'] = next(t['metadata']['hourly_rate'] for t in types if t['metadata']['type'] == body['instance_type_name'])
            return {'data': dict(instance_ids=[INSTANCE])}
        raise AssertionError('unexpected provider endpoint ' + endpoint)

    def instance(self, instance_id):
        status = self.s['status'].get(instance_id, 'terminated')
        rate = (self.s.get('launch_rate') or 1.29)
        return dict(instance_id=instance_id, status=status, public_ip='10.0.0.2', hourly_rate=rate,
                    name='fixture', type='gpu_1x_a10', region='us-east-1')

    def terminate(self, instance_id):
        self.s['terminate_calls'] += 1
        self.s['status'][instance_id] = 'terminated'
        self.s['instances'] = [x for x in self.s['instances'] if x[0] != instance_id]


class FakeCurl:
    """The provider's HTTP API behind the REAL adapter (LambdaExperiment and the
    LambdaTermination it extends). Only the curl process is replaced: the adapter
    loads the credential from the operator file and writes it into curl's stdin
    configuration exactly as it does live, and every response is in the provider's
    raw shape, so the adapter's own projection runs. Nothing reaches the network."""
    def __init__(self):
        self.instances, self.keys, self.launches, self.argvs, self.stdins = [], [], 0, [], []

    @staticmethod
    def raw_type():
        return dict(name='gpu_1x_a10', gpu_description='A10 (24 GB PCIe)', architecture='x86_64',
                    specs=dict(gpus=1, vcpus=30, memory_gib=200, storage_gib=1400), price_cents_per_hour=129)

    def answer(self, endpoint, method, body):
        if endpoint == 'instances':
            return [dict(id=i, name=n, status='active', ip='10.0.0.2', region=dict(name='us-east-1'),
                         instance_type=self.raw_type()) for i, n in self.instances]
        if endpoint == 'instance-types':
            return {'gpu_1x_a10': dict(instance_type=self.raw_type(),
                                       regions_with_capacity_available=[dict(name='us-east-1')])}
        if endpoint == 'images':
            return [dict(id=IMAGE['id'], family=IMAGE['family'], version=IMAGE['version'],
                         architecture=IMAGE['architecture'], region=dict(name=IMAGE['region']))]
        if endpoint == 'ssh-keys' and body is not None:
            self.keys.append(dict(id=KEY_ID, name=body['name']))
            return dict(id=KEY_ID, name=body['name'], public_key=body['public_key'])
        if endpoint == 'ssh-keys':
            return list(self.keys)
        if endpoint.startswith('ssh-keys/') and method == 'DELETE':
            self.keys = [k for k in self.keys if k['id'] != endpoint.split('/')[1]]
            return {}
        if endpoint == 'instance-operations/launch':
            self.launches += 1
            self.instances.append((INSTANCE, body['name']))
            return dict(instance_ids=[INSTANCE])
        if endpoint == 'instance-operations/terminate':
            self.instances = [x for x in self.instances if x[0] not in body['instance_ids']]
            return dict(terminated_instances=[])
        raise AssertionError('unexpected provider endpoint ' + endpoint)

    def run(self, args, input=None, **kwargs):
        self.argvs.append(list(args))
        self.stdins.append(input)
        endpoint = args[-1].split('/api/v1/', 1)[1]
        method = args[args.index('--request') + 1] if '--request' in args else None
        body = json.loads(args[args.index('--data-binary') + 1]) if '--data-binary' in args else None
        payload = json.dumps(dict(data=self.answer(endpoint, method, body)))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=payload + '\n200', stderr='')

    @contextlib.contextmanager
    def installed(self):
        """Replace only curl, in the two adapter modules; the adapter code itself runs."""
        process = SimpleNamespace(run=self.run, CompletedProcess=subprocess.CompletedProcess)
        which = SimpleNamespace(which=lambda name: 'curl-fixture' if name.startswith('curl') else None)
        with patch.object(provider_adapter, 'subprocess', process), patch.object(provider_adapter, 'shutil', which), \
                patch.object(cloud_run_watchdog, 'subprocess', process), patch.object(cloud_run_watchdog, 'shutil', which):
            yield self


class FakeTransport:
    """Interprets the controller's ssh, scp and ssh-keygen invocations against a scenario.

    polls: label -> list of responses, each 'unreachable', 'RUNNING', 'DEAD' or an int exit code.
    A label with no scripted responses completes with exit code 0 at its first poll."""
    def __init__(self, base, polls=None, outputs=None, progress=None, existing=(), mount=None):
        self.base, self.polls = base, {k: list(v) for k, v in (polls or {}).items()}
        self.outputs = dict(outputs or {})
        self.progress = list(progress or [])
        self.started, self.polled, self.calls = [], [], []
        # The remote filesystem as far as preconditions go: every directory a launch
        # command creates is recorded, so a phase whose command requires a path to be
        # absent answers from that record instead of an unconditional 0 (run v4).
        self.created = set(existing)
        # The provider filesystem the asset copy lives on, as a model: present or
        # not, and {digest the file is NAMED by: digest of its actual bytes}. The
        # probe, use and seed commands are evaluated against it, the way the
        # instance would evaluate them against a real mount.
        self.mount = mount
        self.assets_uploaded = False
        self.assets_from_copy = False
        self.seed_writes = []

    def fresh_directory_result(self):
        remote = controller.REMOTE
        if any(p == remote or p.startswith(remote + '/') for p in self.created):
            return 1
        self.created.update({remote, remote + '/project'})
        return 0

    def run(self, argv, capture_output=True, timeout=None):
        self.calls.append((list(argv), timeout))
        done = lambda rc, out=b'': subprocess.CompletedProcess(args=argv, returncode=rc, stdout=out, stderr=b'')
        if argv[0] == 'ssh-keygen':
            identity = Path(argv[argv.index('-f') + 1])
            identity.write_text('private fixture', encoding='utf8')
            Path(str(identity) + '.pub').write_text('ssh-ed25519 AAAAfixture fixture', encoding='utf8')
            return done(0)
        if argv[0] == 'scp':
            if any('collected_evidence.tar.gz' in a for a in argv):
                # Delivered where the controller asked: the session folder or a batch run folder.
                destination = Path(argv[-1].rstrip('/\\'))
                (destination / 'collected_evidence.tar.gz').write_bytes(EVIDENCE)
                (destination / 'remote_collection_manifest.json').write_text('{}', encoding='utf8')
            if any(a.endswith('/assets.tar') for a in argv):
                self.assets_uploaded = True
            return done(0)
        assert argv[0] == 'ssh', argv
        command = argv[-1]
        if command == 'true':
            return done(0)
        if 'setsid nohup' in command:
            label = re.search(r'/([A-Za-z0-9_]+)\.pid', command).group(1)
            self.started.append(label)
            for made in re.findall(r"mkdir -p (\S+)", command):
                self.created.add(made.strip("'\""))
            if label.startswith('asset_copy_'):
                self.evaluate_asset_copy(label, command)
            return done(0, b'4242\n')
        if 'RUNNING' in command and '.rc' in command:
            label = re.search(r'/([A-Za-z0-9_]+)\.rc', command).group(1)
            script = self.polls.get(label)
            if script:
                response = script.pop(0)
            elif label == 'fresh_directory':
                response = self.fresh_directory_result()
            else:
                response = 0
            self.polled.append((label, response))
            if response == 'unreachable':
                return done(255)
            text = response if isinstance(response, str) else 'RC=%d' % response
            if controller.PROGRESS_MARKER in command:
                text += '\n' + controller.PROGRESS_MARKER + '\n' + '\n'.join(self.progress)
            return done(0, (text + '\n').encode())
        if command.startswith('cat ') and '.out' in command:
            label = re.search(r'/([A-Za-z0-9_]+)\.out', command).group(1)
            if label not in self.outputs and 'evidence_hash' in label:
                return done(0, self.outputs['evidence_hash'])
            return done(0, self.outputs.get(label, b''))
        raise AssertionError('unexpected ssh command: ' + command[:80])

    def evaluate_asset_copy(self, label, command):
        """Evaluate the copy probe, use and seed scripts against the modelled mount.

        The script is decoded from the launch command exactly as the instance
        would receive it. A probe that literally echoes a word (a neutralised
        probe) is answered with that word, so a probe that no longer hashes the
        copy is exercised as written rather than replaced by the model."""
        encoded = re.search(r"printf %s '?([A-Za-z0-9+/=]+)'?", command).group(1)
        script = base64.b64decode(encoded).decode()
        digest = re.search(r'/assets-([0-9a-f]{64})\.tar', script)
        digest = digest.group(1) if digest else None
        present = bool(self.mount and self.mount.get('present'))
        files = (self.mount or {}).get('files', {})
        if label == 'asset_copy_probe':
            if script.startswith('echo '):
                word = script.split()[1]
            elif not present:
                word = 'UNREACHABLE'
            elif digest not in files:
                word = 'MISSING'
            elif files[digest] == digest:
                word = 'MATCH'
            else:
                word = 'MISMATCH'
            self.outputs['asset_copy_probe'] = (word + '\n').encode()
        elif label == 'asset_copy_use':
            self.assets_from_copy = present and digest in files
        elif label == 'asset_copy_seed':
            # cp to .partial then mv -n: an existing file under the name is never replaced.
            self.seed_writes.append(digest)
            if present and digest not in files:
                files[digest] = digest

    def popen(self, argv, **kwargs):
        self.popen_argv = list(argv)
        folder = Path(argv[argv.index('--bundle') + 1])
        write(folder / 'WATCHDOG_ARMED.json', dict(instance_id=INSTANCE, pid=777, heartbeat_epoch=controller.time.time(),
                                                   execution_manifest_sha256=sha(folder / 'execution_manifest.json')))
        return SimpleNamespace(pid=777, poll=lambda: None)


def run_controller(root, base, plan, transport, provider, clock, credential, call=None, keep=None):
    """The real controller (or `call`) against the fakes, every outside effect replaced;
    returns (transport, console lines, the run folder the controller used)."""
    fake_subprocess = SimpleNamespace(run=transport.run, Popen=transport.popen, TimeoutExpired=subprocess.TimeoutExpired,
                                      CompletedProcess=subprocess.CompletedProcess, DEVNULL=subprocess.DEVNULL,
                                      DETACHED_PROCESS=8, CREATE_NEW_PROCESS_GROUP=512, CREATE_NO_WINDOW=0)
    console = io.StringIO()
    with patch.object(controller, 'ROOT', root), patch.object(controller, 'BASE', base), \
            patch.object(controller, 'MANIFEST', sha(base / 'execution_manifest.json')), \
            patch.object(controller, 'SEAL', sha(base / 'seal.json')), \
            patch.object(controller, 'PREPARATION', 'f' * 40), \
            patch.object(controller, 'INSTANCE_NAME', LOOP_NAME), \
            patch.object(controller, 'LAUNCH', plan), \
            patch.object(controller, 'LambdaExperiment', provider), \
            patch.object(controller, 'subprocess', fake_subprocess), \
            patch.object(controller, 'time', clock), \
            patch.object(controller, 'keep_awake', keep or (lambda action: action == 'hold')), \
            patch.dict(os.environ, {agent_wrapper.CONFIG_ENV_VAR: str(credential)}), \
            contextlib.redirect_stdout(console):
        clock.active = True
        try:
            (call or controller.execute)()
        finally:
            clock.active = False
        ran = Path(controller.BASE)
    return transport, console.getvalue().splitlines(), ran


class ControllerChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / 'bundle'
        (self.root / 'assets.tar').write_bytes(b'assets fixture')
        with patch.object(controller, 'ROOT', self.root):
            make_bundle(self.base, self.root / 'assets.tar')
        FakeProvider.state = None
        FakeProvider.types = None
        self.clock = FakeClock(self.base)
        # A stand-in operator file the resolver can find. It holds no key and is never
        # read: the provider is mocked, and the controller only passes its path on.
        self.credential = self.root / 'operator_provider_access.txt'
        self.credential.write_text('placeholder, not a key\n', encoding='utf8')
        # The loop ledger the guard reads and the controller appends to.
        self.ledger = self.root / 'ledger' / 'budget_ledger.jsonl'
        open_ledger(self.ledger)
        # The reaper's default ledgers point at fixtures: no check ever reads the loop's real ones.
        for name in ('PRIVATE_LEDGER', 'R_LEDGER'):
            patcher = patch.object(instance_reaper, name, self.root / 'reaper_defaults' / (name.lower() + '.jsonl'))
            patcher.start()
            self.addCleanup(patcher.stop)
        FakeProvider.ledger = self.ledger
        self.addCleanup(setattr, FakeProvider, 'ledger', None)
        self.addCleanup(setattr, FakeProvider, 'types', None)

    def declare_copy(self, mount='/lambda/nfs/fixture', digest=None):
        write(self.base / 'asset_copy_declaration.json', dict(filesystem_name='fixture-fs', mount=mount, operator_authorized=True,
              assets_sha256=digest or self.assets_digest()))

    def remanifest(self, **changes):
        """Change the fixture manifest and seal it again, as the sealer would."""
        manifest = read(self.base / 'execution_manifest.json')
        manifest.update(changes)
        write(self.base / 'execution_manifest.json', manifest)
        with patch.object(controller, 'ROOT', self.root):
            reseal(self.base, self.root / 'assets.tar', **{k: v for k, v in read(self.base / 'seal.json').items()
                                                          if k != 'execution_manifest_sha256'})

    def execute(self, polls=None, outputs=None, progress=None, existing=(), mount=None, provider=None, plan=None,
                call=None, root=None, base=None):
        """Run the real controller against the fakes; return (transport, console, failure or None).
        `provider` replaces FakeProvider (the real adapter, over FakeCurl, in the key test);
        `call` replaces controller.execute (the bound wrapper, in the path tests)."""
        base = base or self.base
        outputs = dict(outputs or {})
        outputs.setdefault('evidence_hash', (hashlib.sha256(EVIDENCE).hexdigest() + '  collected_evidence.tar.gz\n').encode())
        transport = FakeTransport(base, polls, outputs, progress, existing, mount)
        transport, console, ran = run_controller(root or self.root, base, fixture_plan(self.ledger) if plan is None else plan,
                                                 transport, provider or FakeProvider, self.clock, self.credential, call)
        failure = ran / 'controller_failure.json'
        self.ran = ran
        return transport, console, (json.loads(failure.read_text()) if failure.exists() else None)

    def assert_torn_down(self):
        self.assertTrue((self.base / 'TERMINATION_VERIFIED.json').exists())
        self.assertEqual(json.loads((self.base / 'instances_after.json').read_text()), [])
        cleanup = json.loads((self.base / 'cleanup.json').read_text())
        self.assertTrue(cleanup['inventory_empty'] and cleanup['temporary_provider_ssh_removed'] and cleanup['local_ssh_material_removed'])
        confirm = json.loads((self.base / 'independent_inventory_confirmation.json').read_text())
        self.assertEqual(confirm['instances'], [])
        self.assertTrue(confirm['temporary_ssh_registration_absent'] and confirm['local_key_material_absent'])
        self.assertFalse((self.base / 'ssh_identity').exists() or (self.base / 'ssh_identity.pub').exists())
        self.assertEqual(FakeProvider.state['launches'], 1)
        self.assertEqual(json.loads((self.base / 'CURRENT_PHASE.json').read_text())['phase'], 'terminated_and_cleaned')

    def test_poll_outcome_classifies_connection_failure_as_unreachable_not_a_result(self):
        self.assertEqual(controller.poll_outcome(255, b''), ('unreachable', None, []))
        self.assertEqual(controller.poll_outcome(1, b'RC=0\n'), ('unreachable', None, []))
        self.assertEqual(controller.poll_outcome(0, b'RC=0\n'), ('completed', 0, []))
        self.assertEqual(controller.poll_outcome(0, b'RC=143\n'), ('completed', 143, []))
        self.assertEqual(controller.poll_outcome(0, b'RUNNING\n'), ('running', None, []))
        self.assertEqual(controller.poll_outcome(0, b'DEAD\n'), ('dead', None, []))
        self.assertEqual(controller.poll_outcome(0, b'garbage\n')[0], 'unreachable')
        self.assertEqual(controller.poll_outcome(0, b'RC=x\n')[0], 'unreachable')
        kind, code, progress = controller.poll_outcome(0, ('RUNNING\n' + controller.PROGRESS_MARKER + '\n[progress] a\n[progress] b\n').encode())
        self.assertEqual((kind, code, progress), ('running', None, ['[progress] a', '[progress] b']))

    def test_detached_commands_round_trip_the_phase_command_and_report_liveness(self):
        command = "cd /home/ubuntu/x && venv/bin/python -m pip install --no-index 'a b' | tee log"
        launch = controller.detached_launch_command('/home/ubuntu/x', 'install', command)
        encoded = re.search(r"printf %s '?([A-Za-z0-9+/=]+)'?", launch).group(1)
        self.assertEqual(base64.b64decode(encoded).decode(), command)  # the script is the exact command
        phases = controller.phases_dir('/home/ubuntu/x')
        self.assertEqual(phases, '/home/ubuntu/x-phases')  # a sibling, never inside the remote root
        for needle in ('setsid nohup sh -c', "trap '' HUP", phases + '/install.sh', phases + '/install.out', phases + '/install.err',
                       phases + '/install.rc', phases + '/install.pid', phases + '/install.started',
                       'test -f ' + phases + '/install.started && cat ' + phases + '/install.pid'):
            self.assertIn(needle, launch)
        self.assertNotIn('/home/ubuntu/x/', launch)  # nothing under the remote root is named, so nothing there is created
        poll = controller.detached_poll_command('/home/ubuntu/x', 'install')
        self.assertIn(phases + '/install.rc', poll)
        self.assertIn('kill -0', poll)
        self.assertNotIn(controller.PROGRESS_MARKER, poll)
        poll = controller.detached_poll_command('/home/ubuntu/x', 'ordinary_workload', '/home/ubuntu/x/workload.stderr.log')
        self.assertIn(controller.PROGRESS_MARKER, poll)
        self.assertIn('tail -n 12', poll)
        self.assertTrue(poll.endswith('|| true'))  # a missing progress file never fails the status poll

    def test_dead_connection_after_remote_completion_is_completed_and_the_run_proceeds(self):
        """The v3 failure: the install finishes on the instance while every connection carrying it dies."""
        transport, console, failure = self.execute(polls={'install_pinned_wheels': ['unreachable', 'unreachable', 'unreachable', 0]})
        self.assertIsNone(failure, failure)
        self.assertEqual([p for p in transport.polled if p[0] == 'install_pinned_wheels'],
                         [('install_pinned_wheels', 'unreachable')] * 3 + [('install_pinned_wheels', 0)])
        timing = json.loads((self.base / 'install_pinned_wheels_timing.json').read_text())
        self.assertEqual((timing['returncode'], timing['detached'], timing['unreachable_polls'], timing['polls']), (0, True, 3, 4))
        status = json.loads((self.base / 'install_pinned_wheels_status.json').read_text())
        self.assertEqual((status['connection'], status['remote_work'], status['exit_code']), ('ok', 'completed', 0))
        for later in ('dependency_closure', 'gpu_metadata', 'ordinary_workload'):
            self.assertIn(later, transport.started)  # the run went on past the survived phase
        self.assertTrue((self.base / 'WORKLOAD_LAUNCH_INTENT.json').exists())
        self.assertEqual(json.loads((self.base / 'workload_return.json').read_text())['exit_code'], 0)
        self.assertEqual(transport.started.count('ordinary_workload'), 1)
        self.assert_torn_down()

    def test_connection_loss_during_the_workload_keeps_polling_and_records_progress(self):
        polls = {'ordinary_workload': ['RUNNING', 'unreachable', 'unreachable', 'unreachable', 'unreachable', 'unreachable', 'RUNNING', 0]}
        transport, console, failure = self.execute(polls=polls, progress=['[progress] phase=3/9 status=running', '[local-progress] event=memory'])
        self.assertIsNone(failure, failure)
        timing = json.loads((self.base / 'ordinary_workload_timing.json').read_text())
        self.assertEqual((timing['returncode'], timing['unreachable_polls'], timing['polls']), (0, 5, 8))
        self.assertEqual(json.loads((self.base / 'workload_return.json').read_text())['exit_code'], 0)
        progress = (self.base / 'workload_progress.log').read_text(encoding='utf8').splitlines()
        self.assertEqual(progress, ['[progress] phase=3/9 status=running', '[local-progress] event=memory'])
        self.assertEqual(transport.started.count('ordinary_workload'), 1)
        self.assert_torn_down()

    def test_fresh_directory_passes_because_the_launcher_creates_nothing_under_the_remote_root(self):
        """Run v4: the launcher's mkdir created the remote root that fresh_directory requires absent."""
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        self.assertEqual(json.loads((self.base / 'fresh_directory_timing.json').read_text())['returncode'], 0)
        remote = controller.REMOTE
        launched_under_remote = sorted(p for p in transport.created if (p == remote or p.startswith(remote + '/'))
                                       and p not in {remote, remote + '/project'})
        self.assertEqual(launched_under_remote, [], 'the launcher created a path under the remote root')
        self.assertTrue(any(p == controller.phases_dir(remote) for p in transport.created))
        self.assertIn('ordinary_workload', transport.started)
        self.assert_torn_down()

    def test_fresh_directory_refuses_a_present_remote_root_and_tears_down(self):
        """The other polarity: a leftover remote root must refuse the run before any transfer."""
        transport, console, failure = self.execute(existing=[controller.REMOTE])
        self.assertEqual(failure['message'], 'Execution phase failed: fresh_directory')
        self.assertEqual(json.loads((self.base / 'fresh_directory_timing.json').read_text())['returncode'], 1)
        # Nothing was transferred: the refusal came before the support files moved.
        self.assertFalse(any(a[0] == 'scp' and any('project.tar.gz' in x for x in a) for a, _ in transport.calls))
        self.assertNotIn('ordinary_workload', transport.started)
        self.assert_torn_down()

    def test_remote_work_dying_is_a_failure_and_tears_down(self):
        transport, console, failure = self.execute(polls={'install_pinned_wheels': ['RUNNING', 'DEAD']})
        self.assertEqual(failure['message'], 'Execution phase failed: install_pinned_wheels')
        self.assertNotIn('ordinary_workload', transport.started)
        self.assertFalse((self.base / 'WORKLOAD_LAUNCH_INTENT.json').exists())
        self.assert_torn_down()

    def test_remote_work_outliving_the_phase_deadline_is_a_failure_and_tears_down(self):
        transport, console, failure = self.execute(polls={'install_pinned_wheels': ['RUNNING'] * 100000})
        self.assertEqual(failure['message'], 'Phase deadline exceeded: install_pinned_wheels')
        status = json.loads((self.base / 'install_pinned_wheels_status.json').read_text())
        self.assertEqual(status['remote_work'], 'not finished by the phase deadline')
        self.assertNotIn('ordinary_workload', transport.started)
        self.assert_torn_down()

    def test_real_remote_failure_before_the_workload_tears_down_and_refuses_a_second_launch(self):
        transport, console, failure = self.execute(polls={'archive_integrity': [1]})
        self.assertEqual(failure['message'], 'Execution phase failed: archive_integrity')
        self.assertNotIn('ordinary_workload', transport.started)
        self.assert_torn_down()
        with self.assertRaisesRegex(RuntimeError, 'Authorization consumed'):
            self.execute()
        self.assertEqual(FakeProvider.state['launches'], 1)

    def test_nonzero_workload_exit_is_evidence_not_a_retry(self):
        transport, console, failure = self.execute(polls={'ordinary_workload': [2]})
        self.assertIsNone(failure, failure)
        self.assertEqual(json.loads((self.base / 'workload_return.json').read_text()), dict(exit_code=2, epoch=self.clock_at('workload'), full_run_retried=False))
        self.assertEqual(transport.started.count('ordinary_workload'), 1)
        self.assert_torn_down()

    def clock_at(self, key):
        return json.loads((self.base / 'workload_return.json').read_text())['epoch']

    # ---- the launch allowlist admits one new field and no other --------------------------

    def launch_adapter(self):
        """The real adapter, with the transport removed: every refusal below is the
        allowlist's own, raised before any request could be made."""
        import lambda_experiment_provider as adapter
        instance = adapter.LambdaExperiment.__new__(adapter.LambdaExperiment)
        instance.credential_file = self.base / 'absent-credential'
        return adapter, instance

    def test_launch_allowlist_admits_one_filesystem_and_refuses_every_other_field(self):
        adapter, provider = self.launch_adapter()
        bounded = dict(region_name='us-east-1', instance_type_name='gpu_1x_a10', ssh_key_names=['k'],
                       quantity=1, name='n', image={'id': 'i'})
        with patch.object(adapter.shutil, 'which', lambda *_: None):
            # The bounded body and the bounded body plus exactly one filesystem both
            # pass the allowlist and fail later, at the transport, which is removed.
            for body in (bounded, dict(bounded, file_system_names=['fs-1'])):
                with self.assertRaises(Exception) as caught:
                    provider.request('instance-operations/launch', body)
                self.assertIn('transport', str(caught.exception))
            # Every other shape is refused by the allowlist itself.
            refused = [
                dict(bounded, file_system_names=['a', 'b']),          # two filesystems
                dict(bounded, file_system_names=[]),                  # none, but the key present
                dict(bounded, file_system_names='fs-1'),              # not a list
                dict(bounded, file_system_names=[{'name': 'fs-1'}]),  # not a name
                dict(bounded, user_data='#!/bin/sh'),                 # a new field entirely
                dict(bounded, file_system_names=['fs-1'], user_data='x'),
                dict(bounded, quantity=2),
                dict(bounded, ssh_key_names=['k1', 'k2']),
            ]
            for body in refused:
                with self.assertRaises(Exception) as caught:
                    provider.request('instance-operations/launch', body)
                self.assertNotIn('transport', str(caught.exception), body)
            # A filesystem name is label-validated exactly as every other provider label.
            for bad in ('fs 1/../etc', 'a' * 129, 'fs;rm -rf /', ''):
                with self.assertRaises(Exception) as caught:
                    provider.request('instance-operations/launch', dict(bounded, file_system_names=[bad]))
                self.assertNotIn('transport', str(caught.exception), bad)
        # No endpoint exists that could create, resize, price or delete a filesystem.
        for endpoint in ('file-systems', 'filesystems', 'file-system-operations/create'):
            with self.assertRaisesRegex(Exception, 'provider operation not allowed'):
                provider.request(endpoint)

    def test_asset_copy_declaration_is_written_from_the_bundle_it_will_launch(self):
        import declare_asset_copy
        digest = self.assets_digest()
        declaration = declare_asset_copy.declare(self.base, 'shimmer-assets', '/lambda/nfs/shimmer-assets')
        self.assertEqual(declaration['assets_sha256'], digest)
        self.assertEqual(declaration['copy_path'], '/lambda/nfs/shimmer-assets/assets-' + digest + '.tar')
        self.assertTrue(declaration['operator_authorized'])
        # The controller reads exactly this file and keys the copy by the same digest.
        self.assertEqual(controller.asset_copy_declaration(self.base, digest),
                         dict(filesystem_name='shimmer-assets', mount='/lambda/nfs/shimmer-assets'))
        self.assertEqual(controller.asset_copy_path('/lambda/nfs/shimmer-assets', digest), declaration['copy_path'])
        # Nothing in the writer creates a provider resource: it only writes this file.
        source = Path(declare_asset_copy.__file__).read_text(encoding='utf-8')
        for forbidden in ('request(', 'LambdaExperiment', 'curl', 'subprocess'):
            self.assertNotIn(forbidden, source)

    # ---- the bundle is bound to the controller it was sealed with -------------------------

    def seal_controls(self, names):
        """Seal the named repository files into the bundle's manifest, as the sealer does.

        The names are stored relative to the run root the controller resolves them
        against, which the fixture patches to its tempdir; the real repository files
        are copied there, so execute() hashes actual bytes on disk and a change to
        the repository copy is what the polarity test perturbs."""
        for name in names:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        manifest = json.loads((self.base / 'execution_manifest.json').read_text())
        manifest['local_control_hashes'] = {n: sha(self.root / n) for n in names}
        write(self.base / 'execution_manifest.json', manifest)
        write(self.base / 'seal.json', dict(execution_manifest_sha256=sha(self.base / 'execution_manifest.json')))
        write(self.base / 'assets_transfer_archive.json', dict(path='assets.tar', sha256=sha(self.root / 'assets.tar'),
              manifest_sha256=sha(self.base / 'execution_manifest.json'), bytes=14))

    CONTROLS = ('tools/ordinary_final_cloud.py', 'tools/ordinary_final_bound_cloud.py',
                'tools/lambda_experiment_provider.py', 'tools/ordinary_final_run.py',
                # S2 (H1): what the controller imports to decide and record a launch.
                'tools/loop_budget_guard.py', 'tools/loop/instance_reaper.py', 'tools/loop/keep_awake.py',
                'tools/run_remote_experiment.py')

    def test_controller_binding_the_sealed_controller_launches(self):
        """Polarity one: the controller the bundle was sealed with runs the full sequence."""
        self.seal_controls(self.CONTROLS)
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        self.assertIn('ordinary_workload', transport.started)
        self.assertEqual(FakeProvider.state['launches'], 1)
        self.assert_torn_down()

    def test_controller_binding_a_changed_controller_refuses_before_any_instance(self):
        """Polarity two, the property the operator asked for: a launch under a
        controller other than the sealed one is REFUSED, and refused before the
        provider is touched, not merely recorded in the launch receipt.

        Each bound file is changed in turn (a byte appended to a copy on disk, the
        repository file restored afterwards), so the binding is proven for every
        name it covers rather than for one of them."""
        for name in self.CONTROLS:
            with self.subTest(control=name):
                self.setUp()
                self.seal_controls(self.CONTROLS)
                # The file the controller will hash at launch, changed after sealing.
                path = self.root / name
                path.write_bytes(path.read_bytes() + b'\n# changed after sealing\n')
                with self.assertRaisesRegex(RuntimeError, 'Controller source changed'):
                    self.execute()
                # Refused before anything was created: no provider call, no instance,
                # no key, no launch intent, and no phase started.
                self.assertIsNone(FakeProvider.state)
                self.assertFalse((self.base / 'LAUNCH_INTENT.json').exists())
                self.assertFalse((self.base / 'launch.json').exists())
                self.assertFalse((self.base / 'ssh_registration.json').exists())
                self.assertFalse((self.base / 'launch_preflight.json').exists())

    def test_controller_binding_covers_the_controller_wrapper_and_adapter(self):
        """The sealer binds the controller, the bound wrapper and the provider adapter,
        beside the runtime files it already bound."""
        import prepare_ordinary_final_run as sealer
        source = Path(sealer.__file__).read_text(encoding='utf-8')
        block = source.split('local_control_hashes={n:sha(ROOT/n) for n in (', 1)[1].split(')}', 1)[0]
        for name in ('tools/ordinary_final_cloud.py', 'tools/ordinary_final_bound_cloud.py',
                     'tools/lambda_experiment_provider.py', 'tools/ordinary_final_watchdog.py',
                     'tools/cloud_run_watchdog.py', 'tools/cloud_run_common.py', 'tools/ordinary_final_run.py',
                     'tools/loop_budget_guard.py', 'tools/loop/instance_reaper.py', 'tools/loop/keep_awake.py',
                     'tools/run_remote_experiment.py'):
            self.assertIn(name, block)
        # The verification runs before the first provider call in execute().
        body = Path(controller.__file__).read_text(encoding='utf-8')
        start = body.index('def execute():')
        checked = body.index("'Controller source changed'", start)
        provider_call = body.index('provider=LambdaExperiment(CREDENTIAL)', start)
        self.assertLess(checked, provider_call)

    # ---- the provider-side asset copy: the five local proofs -----------------------------

    def assets_digest(self):
        return json.loads((self.base / 'assets_transfer_archive.json').read_text())['sha256']

    def copy_receipt(self):
        return json.loads((self.base / 'asset_copy_receipt.json').read_text())

    def scp_assets_argv(self, transport):
        return [a for a, _ in transport.calls if a[0] == 'scp' and any(x.endswith('/assets.tar') for x in a)]

    def test_asset_copy_no_declaration_is_byte_identical_to_the_v9_path(self):
        """Proof 3, the half that matters most: without a declaration nothing about
        the launch body or the transfer changes."""
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        self.assertEqual(self.copy_receipt(), dict(declared=False, used=False, seeded=False, suspect=False,
                                                   state=None, filesystem_name=None, path=None))
        self.assertEqual([s for s in transport.started if s.startswith('asset_copy_')], [])
        self.assertNotIn('file_system_names', FakeProvider.state['launch_body'])
        self.assertEqual(sorted(FakeProvider.state['launch_body']),
                         ['image', 'instance_type_name', 'name', 'quantity', 'region_name', 'ssh_key_names'])
        argv = self.scp_assets_argv(transport)
        self.assertEqual(len(argv), 1)
        self.assertEqual(argv[0][0], 'scp')
        self.assertEqual(argv[0][-2:], [str(self.root / 'assets.tar'), 'ubuntu@10.0.0.2:' + controller.REMOTE + '/assets.tar'])
        self.assertTrue(transport.assets_uploaded)
        self.assertIsNone(json.loads((self.base / 'operator_authorization.json').read_text())['asset_copy'])
        self.assert_torn_down()

    def test_asset_copy_match_is_used_and_the_upload_is_skipped(self):
        """Proof 1, state MATCH."""
        digest = self.assets_digest()
        self.declare_copy()
        transport, console, failure = self.execute(mount=dict(present=True, files={digest: digest}))
        self.assertIsNone(failure, failure)
        receipt = self.copy_receipt()
        self.assertEqual((receipt['declared'], receipt['state'], receipt['used'], receipt['seeded'], receipt['suspect']),
                         (True, 'MATCH', True, False, False))
        self.assertEqual(receipt['path'], '/lambda/nfs/fixture/assets-' + digest + '.tar')
        self.assertEqual(self.scp_assets_argv(transport), [])
        self.assertTrue(transport.assets_from_copy)
        self.assertEqual(FakeProvider.state['launch_body']['file_system_names'], ['fixture-fs'])
        started = transport.started
        self.assertIn('asset_copy_probe', started)
        self.assertIn('asset_copy_use', started)
        self.assertNotIn('asset_copy_seed', started)
        # archive_integrity still runs, after the copy is in place, and the run proceeds.
        self.assertLess(started.index('asset_copy_use'), started.index('archive_integrity'))
        self.assertIn('ordinary_workload', started)
        self.assertEqual(json.loads((self.base / 'operator_authorization.json').read_text())['asset_copy'],
                         dict(filesystem_name='fixture-fs', mount='/lambda/nfs/fixture'))
        self.assert_torn_down()

    def test_asset_copy_missing_falls_back_to_the_identical_upload_and_seeds_after_integrity(self):
        """Proofs 1 (MISSING), 3 (the fallback argv is the v9 argv) and 4 (seeding order)."""
        digest = self.assets_digest()
        plain, _, _ = self.execute()

        def normalised(argv_list, root):
            # The two runs live in two tempdirs; every path under the run's own
            # root is the same path relative to it. Nothing else may differ.
            return [[a.replace(str(root), '<ROOT>') for a in argv] for argv in argv_list]
        plain_argv = normalised(self.scp_assets_argv(plain), self.root)
        self.setUp()
        self.declare_copy()
        transport, console, failure = self.execute(mount=dict(present=True, files={}))
        self.assertIsNone(failure, failure)
        self.assertEqual(normalised(self.scp_assets_argv(transport), self.root), plain_argv)  # byte-identical fallback
        receipt = self.copy_receipt()
        self.assertEqual((receipt['state'], receipt['used'], receipt['seeded'], receipt['suspect']), ('MISSING', False, True, False))
        started = transport.started
        self.assertNotIn('asset_copy_use', started)
        self.assertLess(started.index('archive_integrity'), started.index('asset_copy_seed'))
        self.assertEqual(transport.seed_writes, [digest])
        self.assertEqual(transport.mount['files'], {digest: digest})  # seeded under the hash-keyed name
        self.assertIn('ordinary_workload', started)
        self.assert_torn_down()

    def test_asset_copy_mismatch_is_refused_uploaded_and_never_overwritten(self):
        """Proof 1, state MISMATCH: a corrupt copy is suspect, the upload runs, the copy is left alone."""
        digest = self.assets_digest()
        self.declare_copy()
        wrong = 'e' * 64
        transport, console, failure = self.execute(mount=dict(present=True, files={digest: wrong}))
        self.assertIsNone(failure, failure)
        receipt = self.copy_receipt()
        self.assertEqual((receipt['state'], receipt['used'], receipt['seeded'], receipt['suspect']), ('MISMATCH', False, False, True))
        self.assertTrue(transport.assets_uploaded)
        self.assertFalse(transport.assets_from_copy)
        self.assertNotIn('asset_copy_use', transport.started)
        self.assertNotIn('asset_copy_seed', transport.started)
        self.assertEqual(transport.mount['files'], {digest: wrong})  # untouched, for the operator
        self.assertIn('ordinary_workload', transport.started)
        self.assert_torn_down()

    def test_asset_copy_unreachable_mount_falls_back_and_does_not_seed(self):
        """Proof 1, state UNREACHABLE."""
        self.declare_copy()
        transport, console, failure = self.execute(mount=dict(present=False, files={}))
        self.assertIsNone(failure, failure)
        receipt = self.copy_receipt()
        self.assertEqual((receipt['state'], receipt['used'], receipt['seeded']), ('UNREACHABLE', False, False))
        self.assertTrue(transport.assets_uploaded)
        self.assertNotIn('asset_copy_seed', transport.started)
        self.assertEqual(transport.seed_writes, [])
        self.assertIn('ordinary_workload', transport.started)
        self.assert_torn_down()

    def test_asset_copy_under_another_digest_never_matches_a_new_manifest(self):
        """Proof 2: the copy is keyed by the sealed archive's digest, so a rebuilt
        archive finds no copy, uploads, and seeds beside the old one, which stays."""
        digest = self.assets_digest()
        old = 'a1' * 32
        self.declare_copy()
        transport, console, failure = self.execute(mount=dict(present=True, files={old: old}))
        self.assertIsNone(failure, failure)
        receipt = self.copy_receipt()
        self.assertEqual((receipt['state'], receipt['used'], receipt['seeded']), ('MISSING', False, True))
        self.assertTrue(transport.assets_uploaded)
        self.assertEqual(transport.mount['files'], {old: old, digest: digest})
        self.assert_torn_down()

    def test_asset_copy_seed_is_skipped_when_integrity_fails(self):
        """Proof 4: no seed without the instance's own verification of the uploaded bytes."""
        self.declare_copy()
        transport, console, failure = self.execute(polls={'archive_integrity': [1]}, mount=dict(present=True, files={}))
        self.assertEqual(failure['message'], 'Execution phase failed: archive_integrity')
        self.assertTrue(transport.assets_uploaded)
        self.assertNotIn('asset_copy_seed', transport.started)
        self.assertEqual(transport.mount['files'], {})
        self.assertEqual(self.copy_receipt()['seeded'], False)
        self.assert_torn_down()

    def test_asset_copy_declaration_must_be_complete_and_operator_authorized(self):
        write(self.base / 'asset_copy_declaration.json', dict(filesystem_name='fixture-fs', mount='/lambda/nfs/fixture'))
        with self.assertRaisesRegex(RuntimeError, 'Asset copy declaration incomplete'):
            self.execute()
        self.assertEqual(FakeProvider.state, None)  # refused before any provider action

    def test_asset_copy_commands_hash_on_the_instance_and_never_clobber(self):
        digest = 'c' * 64
        probe = controller.asset_copy_probe_command('/lambda/nfs/x', digest)
        for word in ('UNREACHABLE', 'MISSING', 'MATCH', 'MISMATCH'):
            self.assertIn('echo ' + word, probe)
        self.assertIn('sha256sum', probe)
        self.assertIn('/lambda/nfs/x/assets-' + digest + '.tar', probe)
        self.assertEqual(controller.asset_copy_state(0, b'MATCH\n'), 'MATCH')
        self.assertEqual(controller.asset_copy_state(0, b'garbage\n'), 'UNREACHABLE')
        self.assertEqual(controller.asset_copy_state(1, b'MATCH\n'), 'UNREACHABLE')
        seed = controller.asset_copy_seed_command('/lambda/nfs/x', digest, '/home/ubuntu/r')
        self.assertIn('.partial', seed)
        self.assertIn('mv -n', seed)
        # The provider adapter admits exactly one filesystem name and nothing else new.
        import lambda_experiment_provider as adapter
        body = dict(region_name='us-east-1', instance_type_name='gpu_1x_a10', ssh_key_names=['k'], quantity=1,
                    name='n', image={'id': 'i'})
        with patch.object(adapter.shutil, 'which', lambda *_: None):
            probe_adapter = adapter.LambdaExperiment.__new__(adapter.LambdaExperiment)
            probe_adapter.credential_file = self.base / 'absent'
            with self.assertRaisesRegex(Exception, 'exactly one bounded filesystem attach required'):
                probe_adapter.request('instance-operations/launch', dict(body, file_system_names=['a', 'b']))
            with self.assertRaisesRegex(Exception, 'exactly one bounded launch required'):
                probe_adapter.request('instance-operations/launch', dict(body, extra=1))
            with self.assertRaisesRegex(Exception, 'transport'):
                probe_adapter.request('instance-operations/launch', dict(body, file_system_names=['fs-1']))

    def test_generated_commands_run_detached_on_a_real_linux_shell(self):
        """The exact launch and poll strings, through one shell layer as `ssh host cmd` runs them.

        Needs a local Linux shell (WSL Ubuntu); skipped, and recorded as skipped, where absent.
        Twelve launches in a row must all detach and finish with their own exit code, the
        collected output must be the command's own, and a wrapper killed without an exit
        code must read DEAD. Before the launch guards, one launch in four died at once."""
        linux = linux_shell()
        if linux is None:
            self.skipTest('no local Linux shell to exercise the remote commands')
        root = '/tmp/shimmer_detached_' + hashlib.sha256(str(self.base).encode()).hexdigest()[:12]
        phases = controller.phases_dir(root)
        try:
            linux('rm -rf ' + shlex_quote(root) + ' ' + shlex_quote(phases))
            expected = {}
            for i in range(12):
                label = 'probe%d' % i
                code = i % 4
                expected[label] = code
                rc, out = linux(controller.detached_launch_command(root, label, 'sleep 1; echo out-%d; echo err-%d 1>&2; exit %d' % (i, i, code)))
                self.assertEqual(rc, 0, out)
                self.assertTrue(out.strip().splitlines()[-1].isdigit(), out)  # a pid, only after the started marker
            rc, out = linux(controller.detached_launch_command(root, 'long', 'sleep 300'))
            self.assertEqual(rc, 0, out)
            self.assertEqual(controller.poll_outcome(*linux(controller.detached_poll_command(root, 'long'), raw=True))[0], 'running')
            deadline = time_module.time() + 30
            pending = dict(expected)
            while pending and time_module.time() < deadline:
                for label in list(pending):
                    kind, code, _ = controller.poll_outcome(*linux(controller.detached_poll_command(root, label), raw=True))
                    self.assertIn(kind, ('running', 'completed'), (label, kind))
                    if kind == 'completed':
                        self.assertEqual(code, pending.pop(label), label)
                time_module.sleep(0.5)
            self.assertEqual(pending, {}, 'phases not completed on the Linux shell')
            rc, out = linux('cat ' + shlex_quote(phases + '/probe5.out') + ' ' + shlex_quote(phases + '/probe5.err'))
            self.assertEqual(sorted(out.split()), ['err-5', 'out-5'])
            # Nothing was created under the root itself: it stays absent for fresh_directory.
            self.assertEqual(linux('test -e ' + shlex_quote(root) + ' && echo present || echo absent')[1].strip(), 'absent')
            # A progress file that does not exist yet leaves the poll a successful status poll.
            kind, code, progress = controller.poll_outcome(*linux(controller.detached_poll_command(root, 'probe1', phases + '/progress.log'), raw=True))
            self.assertEqual((kind, code, progress), ('completed', 1, []))
            linux('printf "[progress] one\\n[progress] two\\n" > ' + shlex_quote(phases + '/progress.log'))
            kind, code, progress = controller.poll_outcome(*linux(controller.detached_poll_command(root, 'probe1', phases + '/progress.log'), raw=True))
            self.assertEqual((kind, code, progress), ('completed', 1, ['[progress] one', '[progress] two']))
            pid = linux('cat ' + shlex_quote(phases + '/long.pid'))[1].strip()
            linux('kill -9 ' + pid + '; pkill -9 -f "sleep 300"; true')
            time_module.sleep(1)
            self.assertEqual(controller.poll_outcome(*linux(controller.detached_poll_command(root, 'long'), raw=True))[0], 'dead')
        finally:
            linux('rm -rf ' + shlex_quote(root) + ' ' + shlex_quote(phases))

    # ---- the credential is located at use, never at import, never from a written path -----

    def unresolvable(self):
        """Every resolver candidate points at a file that does not exist, and the
        environment variable is unset: the state of a machine with no operator file."""
        absent = [(agent_wrapper.CONFIG_ENV_VAR, self.root / 'absent' / 'a.txt'),
                  ('sibling', self.root / 'absent' / 'b.txt'), ('.env_path pointer', self.root / 'absent' / 'c.txt')]
        environment = {k: v for k, v in os.environ.items() if k != agent_wrapper.CONFIG_ENV_VAR}
        return absent, environment

    def test_credential_resolves_from_shimmer_config_path_at_the_moment_of_use(self):
        """(a) The controller's resolver returns the file SHIMMER_CONFIG_PATH names, and
        that same path, and no other, reaches every provider handle and the watchdog."""
        with patch.dict(os.environ, {agent_wrapper.CONFIG_ENV_VAR: str(self.credential)}):
            self.assertEqual(controller.credential_path(), self.credential)
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        # The launch handle and the independent cleanup handle, both given the resolved path.
        self.assertGreaterEqual(len(FakeProvider.state['credentials']), 2)
        self.assertEqual(set(map(str, FakeProvider.state['credentials'])), {str(self.credential)})
        argv = transport.popen_argv
        self.assertEqual(argv[argv.index('--credential-file') + 1], str(self.credential))
        self.assert_torn_down()

    def test_no_resolvable_credential_refuses_in_one_line_naming_shimmer_config_path(self):
        """(b) With nothing to find, every live reader refuses in one line naming
        SHIMMER_CONFIG_PATH, before any provider handle exists."""
        absent, environment = self.unresolvable()
        with patch.object(agent_wrapper, 'candidate_config_paths', lambda: list(absent)), \
                patch.dict(os.environ, environment, clear=True):
            self.assertIsNone(agent_wrapper.resolve_config_path())
            with self.assertRaises(RuntimeError) as caught:
                controller.credential_path()
            message = str(caught.exception)
            self.assertIn('SHIMMER_CONFIG_PATH', message)
            self.assertNotIn('\n', message)
            self.assertEqual(message, controller.CREDENTIAL_REFUSAL)
            # The controller itself: refused before the provider, an instance or a launch intent.
            with self.assertRaisesRegex(RuntimeError, '^' + re.escape(controller.CREDENTIAL_REFUSAL) + '$'):
                self.execute()
            self.assertIsNone(FakeProvider.state)
            self.assertFalse((self.base / 'LAUNCH_INTENT.json').exists())
            # The status reader reports the refusal as the instance line, and queries nothing.
            import ordinary_final_status as status
            write(self.base / 'launch.json', dict(instance_id=INSTANCE, epoch=1.0, hourly_rate=1.29))
            out = io.StringIO()
            with patch('lambda_experiment_provider.LambdaExperiment', side_effect=AssertionError('provider reached')), \
                    contextlib.redirect_stdout(out):
                status.main(self.base, 'T', True)
            self.assertIn('instance (provider): unknown (' + controller.CREDENTIAL_REFUSAL + ')', out.getvalue())
            # The two preflights refuse at the same line, before any provider handle.
            import ordinary_final_bound_preflight as bound_preflight
            import ordinary_final_v3_preflight as v3_preflight
            write(self.base / 'authorization_binding.json', dict(manifest_sha256=sha(self.base / 'execution_manifest.json')))
            for module, call in ((bound_preflight, lambda: bound_preflight.main(self.base)), (v3_preflight, v3_preflight.main)):
                with self.subTest(reader=module.__name__), \
                        patch.object(module, 'LambdaExperiment', side_effect=AssertionError('provider reached')), \
                        patch.object(v3_preflight, 'BASE', self.base), \
                        patch.object(v3_preflight, 'MANIFEST', sha(self.base / 'execution_manifest.json')):
                    with self.assertRaisesRegex(RuntimeError, '^' + re.escape(controller.CREDENTIAL_REFUSAL) + '$'):
                        call()
            self.assertFalse((self.base / 'authorized_live_preflight.json').exists())

    def test_importing_the_controller_tools_resolves_nothing(self):
        """(c) Loading each live tool runs its module code and nothing locates a
        credential or starts a process: resolution belongs to the moment of use."""
        calls = []
        saved = list(sys.path)

        def recorder(name):
            def record(*args, **kwargs):
                calls.append(name)
                raise AssertionError(name + ' called at import')
            return record
        names = ('ordinary_final_cloud', 'ordinary_final_status', 'ordinary_final_bound_preflight',
                 'ordinary_final_v3_preflight', 'ordinary_final_rehearsal')
        loaded = {}
        try:
            with patch.object(agent_wrapper, 'resolve_config_path', recorder('resolve_config_path')), \
                    patch.object(agent_wrapper, 'candidate_config_paths', recorder('candidate_config_paths')), \
                    patch.object(subprocess, 'run', recorder('subprocess.run')), \
                    patch.object(subprocess, 'Popen', recorder('subprocess.Popen')):
                for name in names:
                    spec = importlib.util.spec_from_file_location('_import_probe_' + name, ROOT / 'tools' / (name + '.py'))
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    loaded[name] = module
        finally:
            sys.path[:] = saved
        self.assertEqual(calls, [])
        self.assertEqual(sorted(loaded), sorted(names))
        for name, module in loaded.items():
            self.assertFalse(hasattr(module, 'CREDENTIAL'), name + ' still fixes a credential path at import')
        self.assertFalse(hasattr(loaded['ordinary_final_rehearsal'], 'LINUX_ROOT'))

    def test_no_key_value_is_ever_printed(self):
        """(e) S1 Part 3: no key is ever printed. A fixture operator file assigns a
        unique sentinel to the variable the loader reads (LAMBDA_API_KEY, by AST), and
        SHIMMER_CONFIG_PATH names it. The REAL adapter loads it on every provider call
        (only curl is replaced), through the controller's whole run, its refusal
        paths, the status reader and both live preflights. The sentinel reaches curl's
        stdin configuration, and appears in no argv, no stdout, no stderr, no console
        line and no file the run writes.

        The loader takes the LAMBDA_API_KEY environment variable when it is given no
        credential file, so the variable is removed for the whole test (restored
        after): otherwise an operator shell that exports it would make any load without
        a credential file return that value, and a neutralised printing loader would
        print it."""
        import uuid
        self.enterContext(patch.dict(os.environ))
        os.environ.pop('LAMBDA_API_KEY', None)
        sentinel = 'shimmer' + uuid.uuid4().hex + 'sentinel'
        self.credential.write_text('LAMBDA_API_KEY = ' + repr(sentinel) + '\n', encoding='utf8')
        curl = FakeCurl()
        out, err = io.StringIO(), io.StringIO()
        console = []
        with curl.installed(), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            # The controller's credential path, end to end with the real adapter.
            with patch.dict(os.environ, {agent_wrapper.CONFIG_ENV_VAR: str(self.credential)}):
                self.assertEqual(controller.credential_path(), self.credential)
            transport, console, failure = self.execute(provider=provider_adapter.LambdaExperiment)
            self.assertIsNone(failure, failure)
            self.assertEqual(curl.launches, 1)
            self.assertEqual(json.loads((self.base / 'cleanup.json').read_text())['inventory_empty'], True)
            argv = transport.popen_argv
            self.assertEqual(argv[argv.index('--credential-file') + 1], str(self.credential))
            # The refusal paths: nothing resolvable, and an operator file the loader refuses.
            absent, environment = self.unresolvable()
            with patch.object(agent_wrapper, 'candidate_config_paths', lambda: list(absent)), \
                    patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(RuntimeError, '^' + re.escape(controller.CREDENTIAL_REFUSAL) + '$'):
                    controller.credential_path()
            refused = self.root / 'operator_provider_access_refused.txt'
            for text in ('LAMBDA_API_KEY = ' + repr(sentinel) + '\n') * 2, 'LAMBDA_API_KEY = ' + repr(sentinel + ' x') + '\n':
                refused.write_text(text, encoding='utf8')
                for call in (lambda: cloud_run_watchdog.load_credential(refused),
                             lambda: provider_adapter.LambdaExperiment(refused).request('images'),
                             lambda: provider_adapter.LambdaExperiment(refused).request('instances')):
                    with self.assertRaises(ValueError) as caught:
                        call()
                    print('refused:', caught.exception)
                    self.assertFalse(sentinel in str(caught.exception), 'sentinel in a refusal message')
            refused.unlink()
            with patch.dict(os.environ, {agent_wrapper.CONFIG_ENV_VAR: str(self.credential)}):
                # The status reader, querying the provider.
                import ordinary_final_status as status
                before = len(curl.argvs)
                tasklist = SimpleNamespace(run=lambda *a, **k: SimpleNamespace(stdout=''))  # no local process query
                with patch.object(status, 'subprocess', tasklist):
                    status.main(self.base, 'T', True)
                self.assertGreater(len(curl.argvs), before)
                self.assertIn('instance (provider): not in inventory', out.getvalue())
                # Both live preflights, each printing its receipt.
                import ordinary_final_bound_preflight as bound_preflight
                import ordinary_final_v3_preflight as v3_preflight
                manifest = read(self.base / 'execution_manifest.json')
                write(self.base / 'execution_manifest.json', dict(manifest, max_hourly_rate=1.29))
                write(self.base / 'authorization_binding.json', dict(manifest_sha256=sha(self.base / 'execution_manifest.json')))
                for call in (lambda: bound_preflight.main(self.base), v3_preflight.main):
                    (self.base / 'authorized_live_preflight.json').unlink(missing_ok=True)
                    with patch.object(v3_preflight, 'BASE', self.base), \
                            patch.object(v3_preflight, 'MANIFEST', sha(self.base / 'execution_manifest.json')):
                        call()
                    self.assertTrue(read(self.base / 'authorized_live_preflight.json')['passed'])
        # The credential really was loaded and used, so its absence below means something.
        # Every assertion is boolean with a fixed message, so a failure never echoes the value.
        self.assertTrue(any(sentinel in (s or '') for s in curl.stdins), 'the adapter never loaded the fixture value')
        self.assertFalse(any(sentinel in a for argv in curl.argvs for a in argv), 'sentinel in a curl argv')
        self.assertGreater(len(out.getvalue()), 0)
        self.assertFalse(sentinel in out.getvalue(), 'sentinel printed to stdout')
        self.assertFalse(sentinel in err.getvalue(), 'sentinel printed to stderr')
        self.assertFalse(sentinel in '\n'.join(console), 'sentinel printed to the controller console')
        written = [p for p in self.root.rglob('*') if p.is_file() and p != self.credential]
        self.assertTrue(written)
        self.assertEqual([p.name for p in written if sentinel.encode() in p.read_bytes()], [],
                         'sentinel written to a run file')

    def test_rehearsal_removes_only_its_own_folder_under_the_linux_home(self):
        """(d) The rehearsal's folder is <Linux home>/shimmer-rehearsal, read at run time,
        and every rm -rf it computes targets that folder or a path below it."""
        import ordinary_final_rehearsal as rehearsal
        commands = []
        home = dict(value='/home/fixture')

        def fake_linux(command, timeout=600, stdin=None):
            commands.append(command)
            return subprocess.CompletedProcess(args=command, returncode=0, stdout=home['value'].encode(), stderr=b'')
        root = '/home/fixture/shimmer-rehearsal'
        with patch.object(rehearsal, 'linux', fake_linux):
            layout = rehearsal.resolve_layout()
            self.assertEqual(commands, ['printf %s "$HOME"'])  # one lookup, through the Linux shell
            self.assertEqual(layout.root, root)
            for path in (layout.remote, layout.phases, layout.mount):
                self.assertTrue(path.startswith(root + '/'), path)
            # The removal the rehearsal issues before each controller run, executed.
            commands.clear()
            with patch.object(controller, 'execute', lambda: None):
                rehearsal.run_controller(self.base, True, layout)
            targets = []
            for command in commands:
                for segment in re.split(r';|&&', command):
                    words = shlex.split(segment)
                    if words[:2] == ['rm', '-rf']:
                        targets.extend(words[2:])
            self.assertEqual(sorted(targets), sorted([layout.remote, layout.phases]))
            for path in (layout.root, layout.remote, layout.phases, layout.mount):
                self.assertEqual(shlex.split(rehearsal.remove_command(layout, path)), ['rm', '-rf', path])
            for target in targets:
                self.assertTrue(target == root or target.startswith(root + '/'), target)
            # A parent, the root, a sibling or an escape is refused.
            for bad in ('/home/fixture', '/home', '/', '', root + '-other', root + '/../x', root + '/./x', root + '//x'):
                with self.assertRaisesRegex(RuntimeError, 'Removal outside the rehearsal folder refused'):
                    rehearsal.remove_command(layout, bad)
            # An empty, root or relative home is refused before any folder is named.
            for value in ('', '/', '//', ' ', 'home/fixture', '/home/../', '/home/fix ture'):
                home['value'] = value
                with self.assertRaisesRegex(RuntimeError, 'Linux home unusable'):
                    rehearsal.resolve_layout()
        # Every rm -rf in the rehearsal is built by remove_command and nowhere else.
        source = Path(rehearsal.__file__).read_text(encoding='utf-8')
        self.assertEqual(source.count("'rm -rf "), 1)

    # ---- S2c items 5 and 6, R4 and R5: the loop launch, the guard and the ledger -----------

    def test_ledger_lines_carry_the_iv3_fields_and_the_name_and_deadline_precede_the_launch(self):
        """S2c item 6, R5: the intent line (loop name, deadline) is in the ledger when the
        launch request is made; launch and termination lines follow; no line carries a field
        outside IV.3. Without a launch plan nothing is launched."""
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        rows = [r for r in ledger_rows(self.ledger) if r['event'] != 'budget_open']
        self.assertEqual([r['event'] for r in rows], ['launch_intent', 'launch', 'termination'])
        at_launch = [r for r in FakeProvider.state['ledger_at_launch'] if r['event'] != 'budget_open']
        self.assertEqual([r['event'] for r in at_launch], ['launch_intent'])
        manifest = read(self.base / 'execution_manifest.json')
        start = instance_reaper.parse_time(at_launch[0]['launch_requested_utc']).timestamp()
        for row in rows:
            self.assertLessEqual(set(row), set(guard.LEDGER_FIELDS))
            self.assertEqual(row['instance_name'], LOOP_NAME)
            self.assertEqual((row['purpose'], row['type'], row['region'], row['price_usd_per_hour']),
                             ('controller-fixture', 'gpu_1x_a10', 'us-east-1', 1.29))
            self.assertEqual(row['cap_usd'], manifest['hard_ceiling_usd'])
            self.assertEqual(instance_reaper.parse_time(row['deadline_utc']).timestamp() if 'deadline_utc' in row else None,
                             start + manifest['hard_ceiling_usd'] / 1.29 * 3600 if 'deadline_utc' in row else None)
        self.assertEqual(rows[1]['instance_id'], INSTANCE)
        self.assertEqual(rows[2]['actual_cost'], round(1.29 * rows[2]['actual_minutes'] / 60, 4))
        self.assert_torn_down()
        # The field check itself (A16): a line, or an appended row, with an undeclared field is
        # refused, and a purpose is a short identifier, never prose.
        with self.assertRaisesRegex(guard.GuardRefusal, 'field outside IV.3'):
            guard.ledger_line('launch', instance_name=LOOP_NAME, document='fixture test text')
        with self.assertRaisesRegex(guard.GuardRefusal, 'field outside IV.3'):
            guard.append(self.root / 'refused.jsonl', dict(event='launch', instance_name=LOOP_NAME, document='x'))
        with self.assertRaisesRegex(guard.GuardRefusal, 'short identifier'):
            guard.ledger_line('launch', instance_name=LOOP_NAME, purpose='Checking the fixture on item 3')
        # No plan, no launch: refused before the provider is touched.
        self.setUp()
        with self.assertRaisesRegex(RuntimeError, 'Loop launch plan required'):
            self.execute(plan={})
        self.assertIsNone(FakeProvider.state)

    def test_budget_and_hard_stop_are_read_from_the_latest_ledger_line(self):
        """D-S9 item 3: the guard's budget and the reaper's hard stop come from the ledgers'
        latest budget_open or budget_change line, never from a code constant. 45 dollars spent
        refuses under a 50 dollar opening line and is allowed once a 70 dollar change follows;
        the reaper leaves a loop instance inside its deadline alone at 55 dollars under that
        change (69 dollar stop) and terminates it once spend reaches 69."""
        now = 1_000_000.0 + 3600
        ledger = self.root / 'ds9' / 'ledger.jsonl'
        open_ledger(ledger)
        write_lines(ledger, [dict(event='launch', instance_id='a' * 32, instance_name='shimmer-loop-old', price_usd_per_hour=1.29,
                                  launch_requested_utc=guard.utc(now - 7200)),
                             dict(event='termination', instance_id='a' * 32, instance_name='shimmer-loop-old', actual_cost=45.0)])
        decide = lambda: guard.check(ledgers=[ledger], forecast_minutes=60, hourly_rate=1.29, storage_forecast_usd=3.9,
                                     now_epoch=now, reserve_minutes=15, reaped=[])
        with self.assertRaisesRegex(guard.GuardRefusal, 'leaves less than the forecast'):
            decide()
        write_lines(ledger, [dict(event='budget_change', time_utc=guard.utc(now - 60), budget_usd=70.0, previous_budget_usd=50.0,
                                  hard_stop_usd=69.0, previous_hard_stop_usd=49.0)])
        decision = decide()
        self.assertEqual(decision['budget_usd'], 70.0)
        self.assertAlmostEqual(decision['cap_usd'], 1.5 * guard.forecast_usd(60, 1.29))
        self.assertEqual(instance_reaper.budget_figures(ledger_rows(ledger)), (70.0, 69.0))
        # An earlier-dated line read later never wins; a change with no hard stop keeps the margin.
        self.assertEqual(instance_reaper.budget_figures([dict(event='budget_change', time_utc=guard.utc(now), budget_usd=60.0),
                                                         dict(event='budget_open', time_utc=guard.utc(now - 10), budget_usd=50.0)]),
                         (60.0, 59.0))
        self.assertEqual(instance_reaper.budget_figures([]), (None, None))
        state = self.root / 'ds9' / 'mock_state.json'
        write(state, dict(instances=[dict(instance_id='b' * 32, name=LOOP_NAME, status='active')]))
        write_lines(ledger, [dict(event='launch', instance_id='b' * 32, instance_name=LOOP_NAME, price_usd_per_hour=1.29,
                                  launch_requested_utc=guard.utc(now), deadline_utc=guard.utc(now + 3600)),
                             dict(event='launch', instance_id='c' * 32, instance_name='shimmer-loop-old2', price_usd_per_hour=1.29,
                                  launch_requested_utc=guard.utc(now - 7200)),
                             dict(event='termination', instance_id='c' * 32, instance_name='shimmer-loop-old2', actual_cost=10.0)])
        provider = instance_reaper.MockProvider(state)
        moment = instance_reaper.parse_time(guard.utc(now + 60))
        status = instance_reaper.reap(provider, [ledger], ledger, now=moment)
        self.assertEqual((status['terminated'], status['hard_stop_usd']), ([], 69.0))
        write_lines(ledger, [dict(event='launch', instance_id='d' * 32, instance_name='shimmer-loop-old3', price_usd_per_hour=1.29,
                                  launch_requested_utc=guard.utc(now - 7200)),
                             dict(event='termination', instance_id='d' * 32, instance_name='shimmer-loop-old3', actual_cost=14.0)])
        status = instance_reaper.reap(provider, [ledger], ledger, now=moment)
        self.assertEqual(status['terminated'], [dict(instance_name=LOOP_NAME, reason='hard_stop_spend_reached')])

    def test_the_reaper_ends_a_launch_the_controller_recorded_once_its_deadline_passes(self):
        """R5: tools/loop/instance_reaper.py, over the lines this controller wrote, leaves the
        instance alone before its deadline and terminates it after, with one ledger line."""
        self.execute()
        rows = [r for r in ledger_rows(self.ledger) if r['event'] in ('launch_intent', 'launch')]
        ledger = self.root / 'reaper' / 'ledger.jsonl'
        open_ledger(ledger)
        write_lines(ledger, rows)
        state = self.root / 'reaper' / 'mock_state.json'
        write(state, dict(instances=[dict(instance_id=INSTANCE, name=LOOP_NAME, status='active', type='gpu_1x_a10',
                                          region='us-east-1')]))
        provider = instance_reaper.MockProvider(state)
        from datetime import timedelta
        deadline = instance_reaper.parse_time(rows[0]['deadline_utc'])
        status = instance_reaper.reap(provider, [ledger], ledger, now=deadline - timedelta(seconds=30))
        self.assertEqual(status['terminated'], [])
        self.assertEqual(read(state)['instances'][0]['status'], 'active')
        status = instance_reaper.reap(provider, [ledger], ledger, now=deadline + timedelta(seconds=1))
        self.assertEqual(status['terminated'], [dict(instance_name=LOOP_NAME, reason='deadline_passed')])
        self.assertEqual(read(state)['instances'][0]['status'], 'terminated')
        self.assertEqual(ledger_rows(ledger)[-1]['event'], 'termination')
        # The reaper's own line carries only declared fields (A16).
        self.assertLessEqual(set(ledger_rows(ledger)[-1]), set(guard.LEDGER_FIELDS))

    def test_budget_guard_refuses_each_iv3_case_and_counts_each_launch_once(self):
        """S2c item 5, R4, A3, A13: each refusal by its own message (another loop instance in a
        ledger or the inventory, the cap formula, the capped time against the forecast and the
        stop reserve, no budget_open line, R_INPUTS.json), one count per launch across both
        ledgers, and the reaper's own ledgers always read beside the ones given."""
        now = 1_000_000.0 + 60
        private, r_ledger = self.root / 'g' / 'private.jsonl', self.root / 'g' / 'R_ledger.jsonl'
        open_ledger(private)
        decide = lambda **k: guard.check(**dict(dict(ledgers=[private, r_ledger], forecast_minutes=60, hourly_rate=1.29,
                                                     storage_forecast_usd=3.9, now_epoch=now, reserve_minutes=15,
                                                     reaped=[]), **k))
        forecast = guard.forecast_usd(60, 1.29)
        self.assertAlmostEqual(decide()['cap_usd'], 1.5 * forecast)
        # One closed 10 dollars launch, in R's ledger and copied into the private one: counted once.
        launch = dict(event='launch', instance_id='c' * 32, instance_name='shimmer-loop-r1', price_usd_per_hour=1.29,
                      launch_requested_utc=guard.utc(now - 7200))
        ended = dict(event='termination', instance_id='c' * 32, instance_name='shimmer-loop-r1', actual_cost=10.0)
        write_lines(r_ledger, [launch, ended])
        write_lines(private, [dict(launch, copied_from='R_ledger'), dict(ended, copied_from='R_ledger')])
        self.assertAlmostEqual(decide()['spend_usd'], 10.0, places=2)
        # Spend near the budget: the cap leaves less than the forecast.
        write_lines(private, [dict(event='launch', instance_id='d' * 32, instance_name='shimmer-loop-big', price_usd_per_hour=1.29,
                                   launch_requested_utc=guard.utc(now - 7200)),
                              dict(event='termination', instance_id='d' * 32, instance_name='shimmer-loop-big', actual_cost=34.5)])
        with self.assertRaisesRegex(guard.GuardRefusal, 'leaves less than the forecast'):
            decide()
        # A capped run time that does not cover the forecast and the stop reserve (A13): a
        # 10 minute forecast caps at 19.5 minutes, short of 10 + 15.
        fresh_spend = self.root / 'g0' / 'ledger.jsonl'
        open_ledger(fresh_spend)
        with self.assertRaisesRegex(guard.GuardRefusal, 'does not cover the forecast'):
            decide(ledgers=[fresh_spend], forecast_minutes=10)
        # No budget_open line anywhere in the ledgers read: refused (A3).
        bare = self.root / 'g0' / 'bare.jsonl'
        bare.write_text('', encoding='utf-8')
        with self.assertRaisesRegex(guard.GuardRefusal, 'No budget_open line'):
            decide(ledgers=[bare])
        # The reaper's own ledgers are read even when another one is given (A3): a spend
        # recorded only in the (fixture) private ledger counts.
        with patch.object(instance_reaper, 'PRIVATE_LEDGER', private):
            self.assertGreater(guard.check(ledgers=[fresh_spend], forecast_minutes=60, hourly_rate=1.29, storage_forecast_usd=0,
                                           now_epoch=now, reserve_minutes=15, reaped=None)['spend_usd'], 40)
            with self.assertRaisesRegex(guard.GuardRefusal, 'not one the reaper reads'):
                guard.require_reaped(fresh_spend)
            guard.require_reaped(private)
        # Another loop instance: an open launch in a ledger, or a loop name in the inventory.
        other = self.root / 'g2' / 'ledger.jsonl'
        open_ledger(other)
        write_lines(other, [dict(event='launch', instance_id='e' * 32, instance_name='shimmer-loop-open', cap_usd=2.0,
                                 price_usd_per_hour=1.29, launch_requested_utc=guard.utc(now - 60))])
        with self.assertRaisesRegex(guard.GuardRefusal, 'Another loop instance'):
            decide(ledgers=[other])
        with self.assertRaisesRegex(guard.GuardRefusal, 'Another loop instance'):
            decide(ledgers=[fresh_spend], provider_names=['shimmer-loop-elsewhere'])
        # R_INPUTS.json: the allocation left, the instance type and R's cap.
        fresh = self.root / 'g3' / 'ledger.jsonl'
        open_ledger(fresh)
        inputs = self.root / 'g3' / 'R_INPUTS.json'
        base = dict(spend_usd=0.0, storage_forecast_usd=3.9, allocation_left_usd=24.0, forecast_usd=forecast, cap_usd=10.0,
                    instance_type='gpu_1x_a10')
        write(inputs, base)
        self.assertTrue(decide(ledgers=[fresh], r_inputs=inputs, instance_type='gpu_1x_a10')['cap_usd'] > 0)
        for change, message in ((dict(allocation_left_usd=1.0), 'exceeds the allocation'),
                                (dict(instance_type='gpu_1x_a100'), 'Instance type differs'),
                                (dict(cap_usd=1.0), 'leaves less than the forecast')):
            write(inputs, dict(base, **change))
            with self.subTest(change=change), self.assertRaisesRegex(guard.GuardRefusal, message):
                decide(ledgers=[fresh], r_inputs=inputs, instance_type='gpu_1x_a10')

    def test_controller_launch_is_refused_by_the_guard_before_any_instance(self):
        """S2c item 5 wired into the launch path: an open loop launch in the ledger refuses
        this launch after the inventory and price reads and before any key or instance."""
        write_lines(self.ledger, [dict(event='launch', instance_id='e' * 32, instance_name='shimmer-loop-open', cap_usd=2.0,
                                       price_usd_per_hour=1.29, launch_requested_utc=guard.utc(1_000_000.0))])
        with self.assertRaisesRegex(guard.GuardRefusal, 'Another loop instance'):
            self.execute()
        self.assertEqual(FakeProvider.state['launches'], 0)
        self.assertEqual(FakeProvider.state['keys'], [])
        self.assertFalse((self.base / 'LAUNCH_INTENT.json').exists())

    def test_the_general_cloud_path_refuses_loop_names_and_ledgers(self):
        """R4: the general cloud tools are not a loop launch path."""
        import deploy_cloud_run
        import run_remote_experiment
        for argv in (['--ledger', 'x.jsonl'], ['--r-inputs', 'R_INPUTS.json'], ['--bundle', 'docs/loop/private/budget_ledger.jsonl']):
            with self.subTest(argv=argv), self.assertRaises(guard.GuardRefusal):
                deploy_cloud_run.main(argv)
        with patch.object(sys, 'argv', ['run_remote_experiment.py', 'execute', '--directory', 'x', '--credential-file', 'y',
                                        '--ledger', 'z']), self.assertRaises(guard.GuardRefusal):
            run_remote_experiment.main()
        target = self.root / 'loop-fixture'
        with self.assertRaises(guard.GuardRefusal):
            run_remote_experiment.prepare(SimpleNamespace(directory=target, credential_file=None))
        self.assertFalse(target.exists())
        named = self.root / 'experiment'
        named.mkdir()
        write(named / 'manifest.json', dict(name='shimmer-loop-fixture'))
        write(named / 'LOCAL_GATES.json', dict(REMOTE_RETRY_LOCAL_GATES_PASS=True))
        with self.assertRaises(guard.GuardRefusal):
            run_remote_experiment.execute(SimpleNamespace(directory=named, credential_file=None))

    # ---- S2c item 4, R3: budget parameters and the instance-type rule ----------------------

    TYPES = [dict(metadata=dict(type='gpu_1x_a10', gpu_type='A10 (24 GB PCIe)', gpu_count=1, cpu=30, ram_gib=200,
                                storage_gib=1400, hourly_rate=1.29), architecture='x86_64', regions=[]),
             dict(metadata=dict(type='gpu_1x_a6000', gpu_type='A6000 (48 GB)', gpu_count=1, cpu=14, ram_gib=46,
                                storage_gib=512, hourly_rate=1.09), architecture='x86_64', regions=['us-west-1']),
             dict(metadata=dict(type='gpu_1x_a100_sxm4', gpu_type='A100 (40 GB SXM4)', gpu_count=1, cpu=30, ram_gib=200,
                                storage_gib=512, hourly_rate=1.99), architecture='x86_64', regions=['us-east-1']),
             dict(metadata=dict(type='gpu_1x_h100_pcie', gpu_type='H100 (80 GB PCIe)', gpu_count=1, cpu=26, ram_gib=200,
                                storage_gib=1000, hourly_rate=2.99), architecture='x86_64', regions=['us-east-1']),
             dict(metadata=dict(type='gpu_1x_t4', gpu_type='T4 (16 GB)', gpu_count=1, cpu=8, ram_gib=32,
                                storage_gib=100, hourly_rate=0.5), architecture='x86_64', regions=['us-east-1'])]

    def test_budget_parameters_come_from_the_manifest_and_the_type_rule(self):
        """S2c item 4, R3: candidates sealed from the live inventory under the type rule; the
        A10 in us-east-1 polled for 30 minutes first; caps and reserves read from the manifest
        by the watchdog and by the general path's deadlines; the hardware check reads the type."""
        candidates = guard.instance_candidates(self.TYPES, 1.29)
        self.assertEqual([c['type'] for c in candidates], ['gpu_1x_a10', 'gpu_1x_a6000', 'gpu_1x_a100_sxm4'])
        clock = FakeClock()
        types = json.loads(json.dumps(self.TYPES))
        chosen, region, rate, polls = guard.select_instance(lambda: types, candidates, 1.29, clock)
        self.assertEqual((chosen['type'], region, rate), ('gpu_1x_a6000', 'us-west-1', 1.09))
        self.assertGreaterEqual(clock.slept, guard.POLL_LIMIT_SECONDS)
        self.assertEqual(polls, guard.POLL_LIMIT_SECONDS // guard.POLL_INTERVAL_SECONDS + 1)
        # A price above the sealed cap or twice the reference is never admitted.
        types[1]['metadata']['hourly_rate'] = 2.70
        chosen, region, rate, _ = guard.select_instance(lambda: types, candidates, 1.29, FakeClock())
        self.assertEqual((chosen['type'], rate), ('gpu_1x_a100_sxm4', 1.99))
        types[2]['metadata']['hourly_rate'] = 2.60
        with self.assertRaisesRegex(guard.GuardRefusal, 'No admissible instance type'):
            guard.select_instance(lambda: types, candidates, 1.29, FakeClock())
        # A10 capacity in us-east-1: chosen at once, no waiting.
        types[0]['regions'] = ['us-east-1']
        clock = FakeClock()
        self.assertEqual(guard.select_instance(lambda: types, candidates, 1.29, clock)[:3], (candidates[0], 'us-east-1', 1.29))
        self.assertEqual(clock.slept, 0)
        # The watchdog's deadlines are the manifest's caps and reserves at the selected rate cap.
        manifest = dict(soft_budget_usd=2.0, hard_ceiling_usd=3.0, instance_candidates=candidates,
                        workload_stop_reserve_seconds=900, termination_reserve_seconds=180)
        permit = dict(active_start_epoch=1000.0, hourly_rate=1.99, instance_type='gpu_1x_a100_sxm4', instance_candidate=candidates[2])
        limits = watchdog_module.manifest_deadlines(manifest, permit)
        self.assertAlmostEqual(limits['soft'], 1000 + 2.0 / 1.99 * 3600)
        self.assertAlmostEqual(limits['ceiling'] - limits['stop'], 900)
        self.assertAlmostEqual(limits['ceiling'] - limits['terminate'], 180)
        with self.assertRaises(RuntimeError):
            watchdog_module.manifest_deadlines(manifest, dict(permit, hourly_rate=2.0))
        general = cloud_run_common.budget_deadlines(1.99, 1000, soft_usd=2, hard_usd=3)
        self.assertAlmostEqual(general['soft_epoch'], 1000 + 2 / 1.99 * 3600)
        self.assertAlmostEqual(general['ceiling_epoch'], 1000 + 3 / 1.99 * 3600)
        # The hardware check admits the selected type's GPU and only it.
        torch = SimpleNamespace(cuda=SimpleNamespace(device_count=lambda: 1, mem_get_info=lambda _: (22 * 2**30, 40 * 10**9),
                                                     get_device_properties=lambda _: SimpleNamespace(name='NVIDIA A100-SXM4-40GB')))
        psutil = SimpleNamespace(cpu_count=lambda: 30, virtual_memory=lambda: SimpleNamespace(total=200 * 2**30, available=150 * 2**30))
        with patch.object(runner.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * 2**30)):
            self.assertEqual(runner.hardware_admission(self.root, torch, psutil, candidates[2])['instance_type'], 'gpu_1x_a100_sxm4')
            with self.assertRaisesRegex(RuntimeError, 'GPU memory admission'):
                runner.hardware_admission(self.root, torch, psutil, candidates[0])

    def test_controller_launches_a_fallback_type_only_inside_the_sealed_cap(self):
        """R3 end to end: no A10 capacity for 30 minutes, then the A100 at its live price; the
        sealed hard cap must still cover the forecast at that price, or nothing launches."""
        types = [dict(self.TYPES[0], regions=[]), self.TYPES[2]]
        FakeProvider.types = types
        self.remanifest(**fixture_budget(types=[dict(self.TYPES[0], regions=['us-east-1']), self.TYPES[2]]))
        with self.assertRaisesRegex(RuntimeError, 'less than the forecast at the live price'):
            self.execute()
        self.assertEqual(FakeProvider.state['launches'], 0)
        self.setUp()
        FakeProvider.types = types
        self.remanifest(**fixture_budget(types=[dict(self.TYPES[0], regions=['us-east-1']), self.TYPES[2]]))
        transport, console, failure = self.execute(plan=fixture_plan(self.ledger, forecast_minutes=100))
        self.assertIsNone(failure, failure)
        body = FakeProvider.state['launch_body']
        self.assertEqual((body['instance_type_name'], body['region_name']), ('gpu_1x_a100_sxm4', 'us-east-1'))
        permit = read(self.base / 'operator_authorization.json')
        self.assertEqual((permit['instance_type'], permit['hourly_rate'], permit['instance_candidate']['type']),
                         ('gpu_1x_a100_sxm4', 1.99, 'gpu_1x_a100_sxm4'))
        self.assertGreaterEqual(self.clock.slept, guard.POLL_LIMIT_SECONDS)
        self.assert_torn_down()

    # ---- S2c item 1: external bundle and output paths ------------------------------------

    def bind(self, bundle):
        manifest = read(bundle / 'execution_manifest.json')
        binding = dict(manifest_sha256=sha(bundle / 'execution_manifest.json'), seal_sha256=sha(bundle / 'seal.json'),
                       preparation_commit='f' * 40, source_commit=manifest['source_commit'],
                       project_sha256=manifest['source_archive_sha256'], assets_sha256=manifest['assets_archive']['sha256'])
        write(bundle / 'authorization_binding.json', binding)
        write(bundle / 'asset_verification.json', dict(passed=True, manifest_sha256=binding['manifest_sha256'],
              archive_sha256=binding['assets_sha256'], default_revision_resolutions=[dict(ref_bytes=40)]))
        write(bundle / 'authorized_live_preflight.json', dict(passed=True, manifest_sha256=binding['manifest_sha256']))
        return binding

    def test_external_bundle_and_output_paths(self):
        """S2c item 1: a bundle outside the repository runs in a fresh folder outside it, its
        asset archive read where it is; without --output-dir the bundle is the run folder."""
        repo = self.root / 'repo'
        repo.mkdir()
        bundle = self.root / 'outside' / 'bundle'
        bundle.mkdir(parents=True)
        (bundle / 'assets.tar').write_bytes(b'assets fixture')
        with patch.object(controller, 'ROOT', repo):
            make_bundle(bundle, bundle / 'assets.tar')
        self.bind(bundle)
        runs = self.root / 'outside' / 'runs'
        plan = fixture_plan(self.ledger)
        transport, console, failure = self.execute(root=repo, base=bundle, call=lambda: bound.execute(bundle, plan, runs))
        self.assertIsNone(failure, failure)
        self.assertEqual(self.ran, (runs / 'bundle').resolve())
        self.assertTrue((self.ran / 'cleanup.json').exists() and (self.ran / 'launch.json').exists())
        self.assertFalse((bundle / 'launch.json').exists() or (bundle / 'cleanup.json').exists())
        self.assertEqual(read(bundle / 'RUN_FOLDER.json')['run_folder'], self.ran.as_posix())
        self.assertFalse((self.ran / 'assets.tar').exists())  # the archive is read where it is, never copied
        self.assertEqual(read(bundle / 'assets_transfer_archive.json')['path'], (bundle / 'assets.tar').resolve().as_posix())
        self.assertEqual(self.scp_assets_argv(transport)[0][-2], str(repo / (bundle / 'assets.tar').resolve().as_posix()))
        self.assertTrue(FakeProvider.state['launch_body']['name'].startswith('shimmer-loop-'))
        # The default: no output folder, the bundle is the run folder, as before.
        self.setUp()
        second = self.root / 'outside2' / 'bundle'
        second.mkdir(parents=True)
        (second / 'assets.tar').write_bytes(b'assets fixture')
        with patch.object(controller, 'ROOT', repo):
            make_bundle(second, second / 'assets.tar')
        self.bind(second)
        transport, console, failure = self.execute(root=repo, base=second,
                                                   call=lambda: bound.execute(second, fixture_plan(self.ledger)))
        self.assertIsNone(failure, failure)
        self.assertEqual(self.ran, second.resolve())
        self.assertTrue((second / 'cleanup.json').exists())

    # ---- S2c item 2, R7: the seal carries the manifest hash ------------------------------

    def test_seal_carries_the_test_manifest_hash_or_says_exposed(self):
        self.assertEqual(sealer.test_seal('exposed', None, None, 'f' * 40),
                         dict(exposure='exposed', test_manifest_sha256='exposed, no manifest'))
        archive = self.root / 'test.tar'
        archive.write_bytes(b'test archive fixture')
        manifest = self.root / 'seal_manifest.json'
        write(manifest, dict(archive_sha256=sha(archive), code_commit='f' * 40, scorer_sha256='c' * 64))
        sealed = sealer.test_seal('sealed', manifest, archive, 'f' * 40)
        self.assertEqual((sealed['exposure'], sealed['test_manifest_sha256'], sealed['test_archive_sha256'], sealed['code_commit']),
                         ('sealed', sha(manifest), sha(archive), 'f' * 40))
        with self.assertRaisesRegex(RuntimeError, 'Code commit differs'):
            sealer.test_seal('sealed', manifest, archive, 'e' * 40)
        archive.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'Test archive differs'):
            sealer.test_seal('sealed', manifest, archive, 'f' * 40)
        with self.assertRaisesRegex(RuntimeError, 'no test manifest'):
            sealer.test_seal('exposed', manifest, None, 'f' * 40)
        # The run record of an exposed run says so in the same words.
        self.execute()
        self.assertEqual(read(self.base / 'run_record.json')['test_manifest_sha256'], 'exposed, no manifest')

    # ---- S2c item 3: the 11.12 report ------------------------------------------------------

    def analysis_folder(self, folder, exposure='exposed', copy_used=False):
        import tarfile as tar_module
        folder.mkdir(parents=True)
        manifest = fixture_manifest(self.base / 'project.tar.gz', self.root / 'assets.tar',
                                    models=[dict(model_id='fixture/producer', revision='1' * 40)],
                                    decoding_policy=dict(local_producer=dict(status='restored')))
        write(folder / 'execution_manifest.json', manifest)
        scope = json.dumps(dict(withheld_audit_agents=['FACT_CHECKER'])).encode()
        with tar_module.open(folder / 'project.tar.gz', 'w:gz') as archive:
            info = tar_module.TarInfo('config/review_scope.json'); info.size = len(scope)
            archive.addfile(info, io.BytesIO(scope))
        member = (folder / 'execution_manifest.json').read_bytes()
        with tar_module.open(folder / 'collected_evidence.tar.gz', 'w:gz') as archive:
            info = tar_module.TarInfo('execution_manifest.json'); info.size = len(member)
            archive.addfile(info, io.BytesIO(member))
        write(folder / 'remote_collection_manifest.json', {'execution_manifest.json': dict(sha256=sha(folder / 'execution_manifest.json'),
                                                                                        bytes=len(member))})
        write(folder / 'collection_integrity.json', dict(sha256=sha(folder / 'collected_evidence.tar.gz')))
        write(folder / 'independent_inventory_confirmation.json', dict(instances=[], temporary_ssh_registration_absent=True,
              local_key_material_absent=True, epoch=1_003_600.0))
        write(folder / 'launch.json', dict(instance_id=INSTANCE, epoch=1_000_000.0, hourly_rate=1.29,
                                           instance_type='gpu_1x_a10', region='us-east-1'))
        write(folder / 'run_record.json', dict(purpose='report fixture', exposure=exposure,
              test_manifest_sha256='d' * 64 if exposure == 'sealed' else 'exposed, no manifest',
              report=dict(test_version='fixture-1', authors=dict(test='role B', key='role B', scorer='role C'))))
        write(folder / 'asset_copy_receipt.json', dict(declared=copy_used, used=copy_used, state='MATCH' if copy_used else None))

    def test_report_states_every_11_12_field(self):
        """S2c item 3: purpose and sealed-or-exposed lines first, every 11.12 field, the
        INST_FINDER value, FACT_CHECKER with both reasons, type and price, MATCH, and the
        role-separation sentence for a sealed run; a field that does not apply says why."""
        import analyze_ordinary_final_run as analysis
        folder = self.root / 'analysis'
        self.analysis_folder(folder)
        with contextlib.redirect_stdout(io.StringIO()):
            analysis.analyze(folder)
        lines = (folder / 'RUN_REPORT.md').read_text(encoding='utf8').splitlines()
        self.assertEqual(lines[:2], ['Purpose: report fixture', 'Exposed test, development only.'])
        text = '\n'.join(lines)
        for label in ('Date and time (UTC)', 'Code commit', 'Test version', 'Test manifest hash', 'Authors (test, key, scorer)',
                      'Scorer version', 'Models and checkpoints', 'Decoding settings', 'Backend and machine',
                      'Instance type and price', 'Cost', 'Location and reason-confirmed recall', 'Attribution',
                      'False positives in every deliverable', 'Clean-twin result', 'Layer that produced each catch',
                      'Catches that depended on a directive', 'Model-text review verdicts', 'Agents withheld or settings changed',
                      'SHIMMER_INST_FINDER', 'Multi-round', 'Asset copy', 'Role separation', 'What the result does not show'):
            self.assertIn('- **' + label + '.**', text)
        self.assertIn('exposed, no manifest', text)
        self.assertIn('- **SHIMMER_INST_FINDER.** on', text)
        for reason in analysis.FACT_CHECKER_REASONS:
            self.assertIn(reason, text)
        for run_id in ('110990c1', '6f896263', 'a6649672', 'LAW-III checks 87 and 127'):
            self.assertIn(run_id, text)
        self.assertIn('gpu_1x_a10 at 1.29 dollars an hour', text)
        self.assertIn('not applicable: an exposed run claims no role separation', text)
        self.assertIn('no MATCH', text)
        status = read(folder / 'FINAL_STATUS.json')
        self.assertEqual(status['report']['Purpose'], 'report fixture')
        self.assertFalse(status['multi_round_executed'])
        sealed = self.root / 'analysis_sealed'
        self.analysis_folder(sealed, exposure='sealed', copy_used=True)
        with contextlib.redirect_stdout(io.StringIO()):
            analysis.analyze(sealed)
        lines = (sealed / 'RUN_REPORT.md').read_text(encoding='utf8').splitlines()
        self.assertEqual(lines[1], 'Sealed test.')
        self.assertIn(analysis.ROLE_SEPARATION, lines[-3] + '\n' + '\n'.join(lines))
        self.assertIn('Role separation: separate sessions and folders on one Windows account; not enforced by the operating '
                      'system (Annex A, 11.2 options not in place; Annex B.11).', '\n'.join(lines))
        self.assertIn('MATCH: the sealed archive was read from the operator-declared copy', '\n'.join(lines))
        self.assertIn('d' * 64, '\n'.join(lines))

    # ---- S2c items 8 and 9: the sealed run ------------------------------------------------

    def git_repo(self):
        repo = self.root / 'repo'
        repo.mkdir()
        git = lambda *a: subprocess.run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
                                         '-c', 'commit.gpgsign=false', *a], cwd=repo, capture_output=True, check=True)
        git('init', '-q')
        (repo / 'readme.txt').write_text('fixture\n', encoding='utf8')
        git('add', 'readme.txt')
        git('commit', '-q', '-m', 'first')
        first = git('rev-parse', 'HEAD').stdout.decode().strip()
        git('tag', 'older')
        (repo / 'second.txt').write_text('fixture\n', encoding='utf8')
        git('add', 'second.txt')
        git('commit', '-q', '-m', 'second')
        git('tag', 'loop-s08-frozen')
        return repo, git('rev-parse', 'HEAD').stdout.decode().strip(), first

    def sealed_bundle(self, commit):
        outside = self.root / 'outside'
        bundle = outside / 'sealed'
        bundle.mkdir(parents=True)
        assets = outside / 'assets.tar'
        assets.write_bytes(b'assets fixture')
        archive = outside / 'test.tar'
        archive.write_bytes(b'sealed test archive fixture')
        manifest = outside / 'seal_manifest.json'
        write(manifest, dict(archive_sha256=sha(archive), code_commit=commit, scorer_sha256='c' * 64))
        make_bundle(bundle, assets, source_commit=commit, protected_test=True, test_archive_sha256=sha(archive))
        reseal(bundle, assets, exposure='sealed', test_manifest_sha256=sha(manifest), test_archive_sha256=sha(archive),
               code_commit=commit)
        write(bundle / 'asset_copy_declaration.json', dict(filesystem_name='fixture-fs', mount='/lambda/nfs/fixture',
              operator_authorized=True, assets_sha256=sha(assets)))
        return bundle, manifest

    @staticmethod
    def tree(root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(Path(root).rglob('*')) if p.is_file()}

    def test_sealed_run_writes_nothing_in_the_repository_but_ledger_lines_and_prints_counts_only(self):
        """S2c item 8: a sealed run never attaches persistent cloud storage, prints counts and
        timings only (B.8), and leaves the repository tree as it was apart from the ledger."""
        repo, commit, _ = self.git_repo()
        ledger = repo / 'docs' / 'loop' / 'private' / 'budget_ledger.jsonl'
        open_ledger(ledger)
        FakeProvider.ledger = ledger
        bundle, manifest = self.sealed_bundle(commit)
        before = self.tree(repo)
        plan = fixture_plan(ledger, test_manifest=manifest, frozen_tag='loop-s08-frozen')
        transport, console, failure = self.execute(root=repo, base=bundle, plan=plan, mount=dict(present=True, files={}))
        self.assertIsNone(failure, failure)
        after = self.tree(repo)
        changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
        self.assertEqual(changed, ['docs/loop/private/budget_ledger.jsonl'])
        self.assertTrue(after[changed[0]].startswith(before[changed[0]]))
        self.assertTrue(console)
        for line in console:
            self.assertRegex(line, r'^phase \d+ at \d+ s$')
        self.assertNotIn('file_system_names', FakeProvider.state['launch_body'])
        self.assertEqual([s for s in transport.started if s.startswith('asset_copy_')], [])
        self.assertFalse(self.copy_receipt_at(bundle)['declared'])
        record = read(bundle / 'run_record.json')
        self.assertEqual((record['exposure'], record['test_manifest_sha256']), ('sealed', sha(manifest)))
        self.assertTrue(transport.assets_uploaded)

    def copy_receipt_at(self, folder):
        return read(folder / 'asset_copy_receipt.json')

    def test_protected_test_guard_holds_for_sealed_runs_only(self):
        """S2c item 9: a sealed run is admitted only when declared sealed, its test manifest
        and bundle hash match the seal, and its code commit is the frozen tag's; an exposed
        run behaves as before (no protected test)."""
        repo, commit, first = self.git_repo()
        bundle, manifest = self.sealed_bundle(commit)
        refusals = [(dict(frozen_tag='older'), 'Code commit differs from the frozen tag'),
                    (dict(frozen_tag='no-such-tag'), 'Frozen tag not found'),
                    (dict(test_manifest=None), 'needs the test manifest and the frozen tag')]
        for change, message in refusals:
            with self.subTest(change=change):
                FakeProvider.state = None
                plan = fixture_plan(self.ledger, **dict(dict(test_manifest=manifest, frozen_tag='loop-s08-frozen'), **change))
                with self.assertRaisesRegex(RuntimeError, message):
                    self.execute(root=repo, base=bundle, plan=plan)
                self.assertIsNone(FakeProvider.state)
        write(manifest, dict(read(manifest), scorer_sha256='e' * 64))
        with self.assertRaisesRegex(RuntimeError, 'Test manifest differs from the seal'):
            self.execute(root=repo, base=bundle, plan=fixture_plan(self.ledger, test_manifest=manifest, frozen_tag='loop-s08-frozen'))
        m, seal = read(bundle / 'execution_manifest.json'), read(bundle / 'seal.json')
        runner.admit_workload(m, seal)
        with self.assertRaisesRegex(RuntimeError, 'Sealed declaration not bound'):
            runner.admit_workload(dict(m, test_archive_sha256='0' * 64), seal)
        with self.assertRaisesRegex(RuntimeError, 'Protected test requires a sealed run'):
            runner.admit_workload(m, dict(seal, exposure='exposed', test_manifest_sha256='exposed, no manifest'))
        exposed = read(self.base / 'execution_manifest.json')
        self.assertEqual(runner.admit_workload(exposed, read(self.base / 'seal.json'))['exposure'], 'exposed')

    # ---- S2b items 1 and 2, S2c item 10: multi-round declared, sealed and valid ------------

    DOCS = {'round_one': 'First text of round one.\n', 'round_two': 'Second text of round two.\n'}

    def live_case(self, **changes):
        value = dict(schema_version=1, case_id='fixture-case', fixture=False, decision_support_mode='trajectory_only',
                     allow_recommendations=False,
                     rounds=[dict(round_id='r1', sequence=1, document_ids=['round_one']),
                             dict(round_id='r2', sequence=2, document_ids=['round_two'])],
                     actors=[dict(actor_id='actor_a')], issues=[dict(issue_id='issue_a')],
                     sources=[dict(source_id='s1', round_id='r1', actor_id='actor_a', issue_id='issue_a',
                                   document_id='round_one', unit_id='u01', char_start=0, char_end=5,
                                   quote=self.DOCS['round_one'][0:5], state='accepted')])
        value.update(changes)
        return value

    def test_live_case_manifest_is_accepted_and_the_fixture_and_malformed_are_refused(self):
        """S2b item 2: the live case manifest (schema 1, the live field set, fixture false,
        spans measured on the bundled text)."""
        checked = runner.validate_live_case_manifest(self.live_case(), self.DOCS)
        self.assertEqual(checked['case_id'], 'fixture-case')
        fixture = json.loads((ROOT / 'benchmark/fixtures/multi_round_fixture.json').read_text(encoding='utf8'))
        with self.assertRaisesRegex(RuntimeError, 'outside the live schema'):
            runner.validate_live_case_manifest(fixture)
        with self.assertRaisesRegex(RuntimeError, 'Fixture case manifest refused'):
            runner.validate_live_case_manifest(fixture['manifest'])
        malformed = [self.live_case(rounds=self.live_case()['rounds'][:1]),
                     self.live_case(rounds=[dict(round_id='r1', sequence=1, document_ids=['round_one'])] * 2),
                     self.live_case(sources=[dict(self.live_case()['sources'][0], quote='Other')]),
                     self.live_case(sources=[dict(self.live_case()['sources'][0], char_end=0)]),
                     dict(self.live_case(), producer_envelope={}),
                     self.live_case(schema_version=2)]
        for value in malformed:
            with self.subTest(value=str(value)[:60]), self.assertRaises(RuntimeError):
                runner.validate_live_case_manifest(value, self.DOCS)
        with self.assertRaisesRegex(RuntimeError, 'Case document missing'):
            runner.validate_live_case_manifest(self.live_case(), {'round_one': self.DOCS['round_one']})

    def multi_round_bundle(self):
        import tarfile as tar_module
        data = io.BytesIO()
        with tar_module.open(fileobj=data, mode='w:gz') as archive:
            # The bound pipeline source travels in the archive: its _load_corpus decides which
            # context files are case documents (A15).
            for name, text in [('input/context/' + k + '.md', v) for k, v in self.DOCS.items()] + [
                    ('input/context/_review_targets.json', '{}'),
                    ('scripts/pipeline.py', (ROOT / 'scripts/pipeline.py').read_text(encoding='utf-8'))]:
                raw = text.encode('utf8')
                info = tar_module.TarInfo(name); info.size = len(raw)
                archive.addfile(info, io.BytesIO(raw))
        (self.base / 'project.tar.gz').write_bytes(data.getvalue())
        write(self.base / 'case_manifest.json', self.live_case())
        digest = sha(self.base / 'case_manifest.json')
        self.remanifest(multi_round=True, argv=runner.MULTI_ROUND_ARGV, support_files={'case_manifest.json': digest},
                        case_manifest_sha256=digest, source_archive_sha256=sha(self.base / 'project.tar.gz'))

    def test_multi_round_is_admitted_when_declared_sealed_and_valid(self):
        """S2b item 1, S2c item 10: the old refusal of every multi-round run is now equality
        with the sealed declaration: declared with its sealed live case manifest and the
        reference_serial flags, it launches; undeclared flags, a missing or changed case
        manifest, or a fixture case are refused."""
        self.multi_round_bundle()
        m, seal = read(self.base / 'execution_manifest.json'), read(self.base / 'seal.json')
        self.assertEqual(runner.admit_workload(m, seal, self.base)['multi_round'], True)
        self.assertIn('reference_serial', runner.argv_for(m))
        self.assertNotIn('--topology-config', runner.argv_for(m))
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        self.assertTrue(read(self.base / 'operator_authorization.json')['multi_round'])
        self.assertIn('ordinary_workload', transport.started)
        self.assert_torn_down()
        with self.assertRaisesRegex(RuntimeError, 'Run flags changed'):
            runner.admit_workload(dict(m, argv=runner.ARGV), seal)
        with self.assertRaisesRegex(RuntimeError, 'without its sealed case manifest'):
            runner.admit_workload(dict(m, support_files={}), seal)
        # Multi-round flags with no declaration: refused, as every undeclared run always was.
        undeclared = dict({k: v for k, v in m.items() if k != 'case_manifest_sha256'}, multi_round=False, support_files={})
        with self.assertRaisesRegex(RuntimeError, 'Run flags changed'):
            runner.admit_workload(undeclared, seal)
        write(self.base / 'case_manifest.json', self.live_case(fixture=True))
        with self.assertRaisesRegex(RuntimeError, 'Case manifest changed'):
            runner.admit_workload(m, seal, self.base)

    # ---- S2c item 11: batches -----------------------------------------------------------

    def batch_bundles(self):
        runner_file = {'ordinary_final_run.py': b'# sealed runner fixture\n', 'install.lock': b'fixture==1.0\n'}
        (self.base / 'ordinary_final_run.py').write_bytes(runner_file['ordinary_final_run.py'])
        (self.base / 'install.lock').write_bytes(runner_file['install.lock'])
        self.remanifest(support_files={n: sha(self.base / n) for n in runner_file})
        bundles = {('i1', 'B3'): self.base}
        for item, arm in (('i1', 'B1'), ('i2', 'B3'), ('i2', 'B1')):
            folder = self.root / ('bundle_%s_%s' % (item, arm))
            with patch.object(controller, 'ROOT', self.root):
                make_bundle(folder, self.root / 'assets.tar', project=('project %s %s' % (item, arm)).encode(),
                            support=runner_file)
            bundles[(item, arm)] = folder
        # Items keep the order they are first named in (the preparer's order); arms are
        # deliberately listed out of order.
        order = [('i1', 'B1'), ('i2', 'B1'), ('i1', 'B3'), ('i2', 'B3')]
        return bundles, [dict(item=i, arm=a, bundle=bundles[(i, a)]) for i, a in order]

    def test_batch_runs_b3_and_b1_item_by_item_and_a_stop_leaves_pairs(self):
        """S2c item 11: several bundles in one instance session, each with its own run folder,
        seal entry, authorization and collected evidence, in the order (i1,B3),(i1,B1),(i2,B3),
        (i2,B1); a stop leaves the finished pair complete."""
        bundles, entries = self.batch_bundles()
        transport, console, failure = self.execute(plan=fixture_plan(self.ledger, batch=entries))
        self.assertIsNone(failure, failure)
        workloads = [s for s in transport.started if s.startswith('batch_workload_')]
        self.assertEqual(workloads, ['batch_workload_0', 'batch_workload_1', 'batch_workload_2', 'batch_workload_3'])
        self.assertNotIn('ordinary_workload', transport.started)
        order = [('i1', 'B3'), ('i1', 'B1'), ('i2', 'B3'), ('i2', 'B1')]
        for k, (item, arm) in enumerate(order):
            folder = self.base / 'batch' / ('%02d_%s_%s' % (k, item, arm))
            entry = read(folder / 'seal_entry.json')
            self.assertEqual((entry['item'], entry['arm'], entry['paired_with']), (item, arm, k + 1 if arm == 'B3' else k - 1))
            self.assertEqual(entry['execution_manifest_sha256'], sha(bundles[(item, arm)] / 'execution_manifest.json'))
            self.assertEqual(read(folder / 'operator_authorization.json')['execution_manifest_sha256'], entry['execution_manifest_sha256'])
            self.assertEqual(read(folder / 'workload_return.json')['exit_code'], 0)
            self.assertEqual(read(folder / 'collection_integrity.json')['sha256'], hashlib.sha256(EVIDENCE).hexdigest())
            self.assertTrue((bundles[(item, arm)] / 'LAUNCH_INTENT.json').exists())
            if k:
                self.assertLess(transport.started.index('batch_park_%d' % k), transport.started.index('batch_workload_%d' % k))
        self.assertEqual(read(self.base / 'batch_manifests.json'),
                         [sha(bundles[o] / 'execution_manifest.json') for o in order])
        self.assert_torn_down()
        # A stop during the third bundle: the first pair is complete, nothing later ran.
        self.setUp()
        bundles, entries = self.batch_bundles()
        transport, console, failure = self.execute(plan=fixture_plan(self.ledger, batch=entries), polls={'batch_integrity_2': [1]})
        self.assertEqual(failure['message'], 'Execution phase failed: batch_integrity')
        done = [p.name for p in sorted((self.base / 'batch').iterdir()) if (p / 'collection_integrity.json').exists()]
        self.assertEqual(done, ['00_i1_B3', '01_i1_B1'])
        self.assertFalse((self.base / 'batch' / '02_i2_B3' / 'workload_return.json').exists())
        self.assert_torn_down()

    # ---- S2c item 13: named extras of the cloud source archive ----------------------------

    def test_named_archive_extras_enter_the_source_archive_or_fail_in_one_line(self):
        names = ['scripts/pipeline.py', 'scripts/foo_checks.py', 'config/x.json', 'benchmark/baselines/bare_model.py',
                 'benchmark/baselines/fixtures/item.json', 'tools/run_local_demo.py', 'tools/other.py', 'README.md']
        self.assertEqual(sealer.archive_names(names, extras=()),
                         ['scripts/pipeline.py', 'config/x.json', 'tools/run_local_demo.py'])
        self.assertEqual(sealer.archive_names(names, extras=('benchmark/baselines/', 'tools/other.py')),
                         ['scripts/pipeline.py', 'config/x.json', 'benchmark/baselines/bare_model.py',
                          'tools/run_local_demo.py', 'tools/other.py'])
        with self.assertRaises(RuntimeError) as caught:
            sealer.archive_names(names, extras=('benchmark/adapters/',))
        self.assertEqual(str(caught.exception), 'Named archive extra absent from the bound commit: benchmark/adapters/')
        self.assertNotIn('\n', str(caught.exception))
        for test_path in ('benchmark/corpora/clinical_reference/', 'input/context/', 'seals/'):
            with self.subTest(path=test_path), self.assertRaisesRegex(RuntimeError, 'external bundle path'):
                sealer.archive_names(names + [test_path + 'x'], extras=(test_path,))
        self.assertEqual(sealer.ARCHIVE_EXTRAS, ())

    # ---- S2c item 14: asset copy only with this bundle's own declaration -----------------

    def test_asset_copy_match_needs_this_bundles_own_declaration_and_the_upload_is_forecast(self):
        self.declare_copy(digest='e' * 64)
        with self.assertRaisesRegex(RuntimeError, 'Asset copy declaration is for another bundle'):
            self.execute(mount=dict(present=True, files={}))
        self.assertIsNone(FakeProvider.state)
        self.setUp()
        with self.assertRaisesRegex(RuntimeError, 'forecast must include the upload'):
            self.execute(plan=fixture_plan(self.ledger, forecast_includes_upload=False))
        self.assertFalse((self.base / 'LAUNCH_INTENT.json').exists())
        self.assertEqual(FakeProvider.state['launches'], 0)
        # With this bundle's declaration a MATCH is used, and the upload need not be forecast.
        self.setUp()
        digest = self.assets_digest()
        self.declare_copy()
        transport, console, failure = self.execute(mount=dict(present=True, files={digest: digest}),
                                                   plan=fixture_plan(self.ledger, forecast_includes_upload=False))
        self.assertIsNone(failure, failure)
        self.assertEqual((self.copy_receipt()['state'], self.copy_receipt()['used']), ('MATCH', True))

    # ---- R11, open item 12: an unratified SHIMMER_INST_FINDER=off is never sealed ----------

    def test_unratified_inst_finder_off_refuses_to_seal(self):
        files = {'scripts/pipeline.py': (ROOT / 'scripts/pipeline.py').read_bytes(),
                 'config/constitution.json': (ROOT / 'config/constitution.json').read_bytes()}
        self.assertEqual(sealer.seal_environment(files, None)['SHIMMER_INST_FINDER'], 'on')
        self.assertEqual(sealer.seal_environment(files, 'on')['SHIMMER_INST_FINDER'], 'on')
        with self.assertRaisesRegex(RuntimeError, 'Refuse to seal SHIMMER_INST_FINDER=off'):
            sealer.seal_environment(files, 'off')
        constitution = json.loads(files['config/constitution.json'])
        constitution['amendments'] = list(constitution.get('amendments') or []) + [dict(
            id='FIXTURE', operator_approved=True, change='INST_FINDER switched off through SHIMMER_INST_FINDER')]
        ratified = dict(files, **{'config/constitution.json': json.dumps(constitution).encode()})
        self.assertEqual(sealer.seal_environment(ratified, 'off')['SHIMMER_INST_FINDER'], 'off')

    # ---- S2 checker round 1 ---------------------------------------------------------------

    # The shape of the private ledger's own opening line, copied field for field (no values
    # read from the real ledger), so the reaper's reading is proven on the format it runs on.
    OPEN_LINE = dict(event='budget_open', time_utc='2026-10-27T03:16:00+00:00', loop_start_utc='2026-10-27T03:16:00+00:00',
                     budget_usd=50.0, storage_usd_per_day=0.13, storage_forecast_days=30, storage_forecast_usd=3.9,
                     allocations_usd=dict(S5=18.0, S8=24.0, smoke=3.0, reserve=5.0), a10_reference_price_usd_per_hour=1.29,
                     a10_price_source='fixture', running_instances_at_open=0, orphans=0, usage_five_hour='unknown',
                     usage_seven_day='unknown')

    def test_ledger_closes_a_launch_by_id_or_name(self):
        """A1: an intent whose launch line was never written is closed by a termination that
        names its instance id or its name; a termination before the request never closes a
        later launch of the same name; the existing line shapes read as before."""
        from datetime import datetime, timezone
        now = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
        intent = dict(event='launch_intent', time_utc='2026-10-27T10:00:00+00:00', launch_requested_utc='2026-10-27T10:00:00+00:00',
                      instance_name='shimmer-loop-a', price_usd_per_hour=1.29, cap_usd=2.0, deadline_utc='2026-10-27T11:30:00+00:00',
                      purpose='fixture')
        ended = dict(event='termination', by='reaper', time_utc='2026-10-27T11:31:00+00:00', instance_id='f' * 32,
                     instance_name='shimmer-loop-a', reason='deadline_passed', actual_minutes=91, actual_cost=1.9565)
        by_name, closed, spend = instance_reaper.ledger_view([self.OPEN_LINE, intent, ended], now)
        self.assertIn('shimmer-loop-a', closed)
        self.assertAlmostEqual(spend - 0.13 * (now - instance_reaper.parse_time(self.OPEN_LINE['loop_start_utc'])).total_seconds() / 86400,
                               1.9565, places=4)
        ledger = self.root / 'a1' / 'ledger.jsonl'
        write_lines(ledger, [self.OPEN_LINE, intent, ended])
        self.assertEqual(guard.ledger_state([ledger], now.timestamp())[1], [])
        # A termination recorded before the request does not close a later launch of that name.
        earlier = dict(ended, time_utc='2026-10-27T09:00:00+00:00')
        by_name, closed, spend = instance_reaper.ledger_view([self.OPEN_LINE, earlier, intent], now)
        self.assertNotIn('shimmer-loop-a', closed)
        # The format already in use: a launch with its id and a termination by id.
        launch = dict(intent, event='launch', instance_id='f' * 32)
        by_name, closed, spend = instance_reaper.ledger_view([self.OPEN_LINE, launch, dict(ended, instance_name=None)], now)
        self.assertIn('f' * 32, closed)
        # The reaper still ends an unclosed intent's instance at its deadline.
        state = self.root / 'a1' / 'state.json'
        write(state, dict(instances=[dict(instance_id='f' * 32, name='shimmer-loop-a', status='active')]))
        open_only = self.root / 'a1' / 'open.jsonl'
        write_lines(open_only, [self.OPEN_LINE, intent])
        status = instance_reaper.reap(instance_reaper.MockProvider(state), [open_only], open_only, now=now)
        self.assertEqual(status['terminated'], [dict(instance_name='shimmer-loop-a', reason='deadline_passed')])
        self.assertEqual(guard.ledger_state([open_only], now.timestamp())[1], [])

    def test_a_launch_recovered_without_its_launch_line_is_closed(self):
        """A1 in the controller: the launch request reaches the provider but its reply is lost.
        The recovery finds the instance by name, writes its launch line, terminates it and
        closes the ledger, so the next launch is not refused as 'another instance running'."""
        class LostReply(FakeProvider):
            def request(self, endpoint, body=None, method=None):
                value = super().request(endpoint, body, method)
                if endpoint == 'instance-operations/launch':
                    raise RuntimeError('reply lost after the launch request')
                return value
        transport, console, failure = self.execute(provider=LostReply)
        self.assertEqual(failure['message'], 'reply lost after the launch request')
        rows = [r for r in ledger_rows(self.ledger) if r['event'] != 'budget_open']
        self.assertEqual([r['event'] for r in rows], ['launch_intent', 'launch', 'termination'])
        self.assertEqual((rows[1]['instance_id'], rows[2]['instance_id']), (INSTANCE, INSTANCE))
        self.assertEqual(guard.ledger_state([self.ledger], self.clock.time())[1], [])
        self.assert_torn_down()

    def test_termination_record_from_either_writer_closes_the_ledger(self):
        """A2: the watchdog's record (confirmed_epoch) or the controller's (epoch) both close
        the ledger and the cleanup runs; the watchdog never overwrites an existing record."""
        real = controller.termination

        def raced(provider, iid, base, start, rate):
            done = real(provider, iid, base, start, rate)
            if done:
                write(Path(base) / 'TERMINATION_VERIFIED.json', dict(instance_id=iid, confirmed_epoch=self.clock.time() + 7,
                                                                    provider='Lambda', status='terminated'))
            return done
        with patch.object(controller, 'termination', raced):
            transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        self.assertFalse((self.base / 'ledger_close_failure.json').exists())
        closing = ledger_rows(self.ledger)[-1]
        self.assertEqual(closing['event'], 'termination')
        self.assertEqual(closing['time_utc'], guard.utc(read(self.base / 'TERMINATION_VERIFIED.json')['confirmed_epoch']))
        self.assert_torn_down()
        # The watchdog writes its record only where none exists.
        folder = self.root / 'watch'
        folder.mkdir()
        manifest = read(self.base / 'execution_manifest.json')
        permit = dict(instance_id=INSTANCE, active_start_epoch=1000.0, hourly_rate=1.29, instance_type='gpu_1x_a10',
                      instance_candidate=manifest['instance_candidates'][0])
        write(folder / 'execution_manifest.json', manifest)
        write(folder / 'TERMINATION_VERIFIED.json', dict(epoch=5.0))
        (folder / 'TERMINATE_REQUEST').touch()
        provider = SimpleNamespace(instance=lambda i: dict(status='terminated'), terminate=lambda i: None)
        watchdog_module.watch(folder, provider, permit, manifest, now=lambda: 2000.0, sleep=lambda s: None)
        self.assertEqual(read(folder / 'TERMINATION_VERIFIED.json'), dict(epoch=5.0))

    def test_a_bundle_is_launched_once_with_or_without_an_output_folder(self):
        """A6: a refusal before the launch intent leaves the bundle launchable (its run folder
        kept, the next attempt in <bundle>.2); once launched in a run folder, the bundle refuses
        a second launch without --output-dir as with it."""
        repo = self.root / 'repo'
        repo.mkdir()
        bundle = self.root / 'outside' / 'bundle'
        bundle.mkdir(parents=True)
        (bundle / 'assets.tar').write_bytes(b'assets fixture')
        with patch.object(controller, 'ROOT', repo):
            make_bundle(bundle, bundle / 'assets.tar')
        self.bind(bundle)
        runs = self.root / 'outside' / 'runs'
        blocked = self.root / 'blocked' / 'ledger.jsonl'
        open_ledger(blocked)
        write_lines(blocked, [dict(event='launch', instance_id='e' * 32, instance_name='shimmer-loop-open', cap_usd=2.0,
                                   price_usd_per_hour=1.29, launch_requested_utc=guard.utc(1_000_000.0))])
        with self.assertRaisesRegex(guard.GuardRefusal, 'Another loop instance'):
            self.execute(root=repo, base=bundle, call=lambda: bound.execute(bundle, fixture_plan(blocked), runs))
        self.assertFalse(bound.consumed(bundle))
        self.assertTrue((runs / 'bundle').exists())
        transport, console, failure = self.execute(root=repo, base=bundle,
                                                   call=lambda: bound.execute(bundle, fixture_plan(self.ledger), runs))
        self.assertIsNone(failure, failure)
        self.assertEqual(self.ran, (runs / 'bundle.2').resolve())
        self.assertEqual(read(bundle / 'RUN_FOLDER.json')['run_folder'], self.ran.as_posix())
        for output in (None, runs):
            with self.subTest(output=output), self.assertRaisesRegex(RuntimeError, 'Authorization already consumed'):
                self.execute(root=repo, base=bundle, call=lambda: bound.execute(bundle, fixture_plan(self.ledger), output))
        self.assertEqual(FakeProvider.state['launches'], 1)

    def test_one_launch_decision_at_a_time(self):
        """A12: a held ledger lock refuses, and is left to its holder; a launch leaves no lock;
        an instance that appears during the type poll is caught by the inventory read again
        just before the guard."""
        lock = Path(str(self.ledger) + '.lock')
        lock.write_text('held', encoding='utf8')
        with self.assertRaisesRegex(guard.GuardRefusal, 'holds the ledger lock'):
            self.execute()
        self.assertEqual((lock.read_text(encoding='utf8'), FakeProvider.state['launches']), ('held', 0))
        lock.unlink()
        self.setUp()
        self.execute()
        self.assertFalse(Path(str(self.ledger) + '.lock').exists())
        self.setUp()

        def appearing(reads):
            FakeProvider.state['instances'].append(('e' * 32, 'shimmer-loop-elsewhere'))
            return [A10_TYPE]
        FakeProvider.types = appearing
        with self.assertRaisesRegex(RuntimeError, 'Provider inventory not empty'):
            self.execute()
        self.assertEqual(FakeProvider.state['launches'], 0)
        self.assertFalse(Path(str(self.ledger) + '.lock').exists())

    def test_batch_reports_one_per_bundle_with_the_session_cost_and_copy(self):
        """C31, A14: analyze_batch writes one report per batch run folder; each states the
        session's asset-copy result and says its cost is the whole session's."""
        session = self.root / 'session'
        for k, (item, arm) in enumerate((('i1', 'B3'), ('i1', 'B1'))):
            folder = session / 'batch' / ('%02d_%s_%s' % (k, item, arm))
            self.analysis_folder(folder, copy_used=True)
            write(folder / 'seal_entry.json', dict(index=k, item=item, arm=arm, bundle=folder.as_posix()))
        with contextlib.redirect_stdout(io.StringIO()):
            folders = analysis.analyze_batch(session)
        self.assertEqual([f.name for f in folders], ['00_i1_B3', '01_i1_B1'])
        for folder in folders:
            text = (folder / 'RUN_REPORT.md').read_text(encoding='utf8')
            self.assertIn('the whole instance session', text)
            self.assertIn('MATCH: the sealed archive was read from the operator-declared copy', text)

    def test_case_documents_follow_the_pipelines_corpus_rules(self):
        """A15: sealing and launch validate the documents the run's own _load_corpus loads:
        top-level files only, `_` files and empty text skipped, stem__ext on a collision, and
        a binary file never crashes validation."""
        members = {'round_one.md': b'First text of round one.\n', 'sub/nested.md': b'nested text', '_meta.md': b'meta',
                   'empty.md': b'', 'dup.md': b'one', 'dup.txt': b'two', 'paper.pdf': b'\x00\xff\xfe not a document'}
        documents = runner.case_corpus_documents(members, (ROOT / 'scripts/pipeline.py').read_bytes())
        self.assertEqual(sorted(k for k in documents if k != 'paper'), ['dup__md', 'dup__txt', 'round_one'])
        self.assertEqual(documents['round_one'], 'First text of round one.\n')
        case = self.live_case(rounds=[dict(round_id='r1', sequence=1, document_ids=['round_one']),
                                      dict(round_id='r2', sequence=2, document_ids=['nested'])])
        with self.assertRaisesRegex(RuntimeError, 'Case document missing'):
            runner.validate_live_case_manifest(case, documents)

    def test_test_archive_names_keep_their_own_prefix(self):
        """A17: only a leading './' is removed from a test archive member's name."""
        import tarfile as tar_module
        def archive(names):
            path = self.root / ('test_%d.tar' % len(names))
            with tar_module.open(path, 'w') as out:
                for name in names:
                    info = tar_module.TarInfo(name); info.size = 1
                    out.addfile(info, io.BytesIO(b'x'))
            return path
        self.assertEqual(sorted(sealer.workload_members(archive(['./context/a.md', './_review_targets.json']))),
                         ['_review_targets.json', 'context/a.md'])
        with self.assertRaisesRegex(RuntimeError, 'outside context/'):
            sealer.workload_members(archive(['./.context/a.md']))

    def test_the_controller_never_writes_an_asset_copy_declaration(self):
        """C34: with no declaration none appears after a launch; with one, its bytes stay as the
        operator wrote them; the controller's source names the file only in its reader."""
        self.execute()
        self.assertFalse((self.base / 'asset_copy_declaration.json').exists())
        self.setUp()
        self.declare_copy()
        before = (self.base / 'asset_copy_declaration.json').read_bytes()
        digest = self.assets_digest()
        self.execute(mount=dict(present=True, files={digest: digest}))
        self.assertEqual((self.base / 'asset_copy_declaration.json').read_bytes(), before)
        source = Path(controller.__file__).read_text(encoding='utf-8')
        reader = source.split('def asset_copy_declaration(', 1)[1].split('\ndef ', 1)[0]
        self.assertEqual(source.count("asset_copy_declaration.json'"), reader.count("asset_copy_declaration.json'"))

    def run_preparation_test(self, name):
        import ordinary_final_preparation_checks as preparation
        return unittest.TextTestRunner(stream=io.StringIO()).run(preparation.PreparationChecks(name)).wasSuccessful()

    def test_flipped_preparation_test_admits_a_declared_multi_round(self):
        """C39: the flipped preparation test (a declared, sealed, valid multi-round Review is
        admitted; undeclared or unsealed ones refused), held by this gate's proof."""
        self.assertTrue(self.run_preparation_test(
            'test_undeclared_or_unsealed_workloads_rejected_and_a_declared_multi_round_admitted'))

    def test_flipped_preparation_test_parses_the_sealed_multi_round_flags(self):
        """C39: the flipped parser test (the sealed multi-round flags parse as a declared
        multi-round Review under reference_serial), held by this gate's proof."""
        self.assertTrue(self.run_preparation_test('test_actual_parser_ordinary_flags'))

    # ---- follow-ups: the rehearsal under the loop launch, and R3 with no cap default ------

    def test_rehearsal_plan_and_manifest_launch_under_the_loop_guard(self):
        """The rehearsal builds a manifest with the IV.3 budget fields and this tree's controller
        binding from a bundle sealed before S2, and a launch plan whose shimmer-loop- launch
        passes the budget guard on its own temporary ledger. Proven by running the real
        controller with that plan, name and manifest against the mocked provider and transport
        (the rehearsal's WSL target is not used)."""
        source = self.root / 'source_bundle'
        work = self.root / 'rehearsal_work'
        source.mkdir()
        work.mkdir()
        for name in ('ordinary_final_run.py', 'ordinary_final_summary.py', 'cloud_run_observer.py', 'topology.json',
                     'install.lock', 'runtime.candidate.lock', 'provider_inventory.json'):
            (source / name).write_text('fixture\n', encoding='utf8')
        (source / 'project.tar.gz').write_bytes(b'project fixture')
        (work / 'assets.tar').write_bytes(b'rehearsal assets fixture')
        old = fixture_manifest(source / 'project.tar.gz', work / 'assets.tar',
                               local_control_hashes={'tools/ordinary_final_cloud.py': '0' * 64})
        for key in ('instance_candidates', 'a10_reference_rate', 'per_run_cap_usd', 'workload_stop_reserve_seconds',
                    'termination_reserve_seconds'):
            old.pop(key)
        write(source / 'execution_manifest.json', old)
        assets = dict(filename='assets.tar', sha256=sha(work / 'assets.tar'), bytes=(work / 'assets.tar').stat().st_size)
        with patch.object(rehearsal, 'SOURCE_BUNDLE', source), patch.object(rehearsal, 'WORK', work):
            base = rehearsal.make_bundle('fixture', assets, [])
        manifest = read(base / 'execution_manifest.json')
        for key in ('instance_candidates', 'a10_reference_rate', 'per_run_cap_usd', 'workload_stop_reserve_seconds',
                    'termination_reserve_seconds', 'soft_budget_usd', 'hard_ceiling_usd'):
            self.assertIn(key, manifest)
        self.assertEqual(manifest['local_control_hashes'], {'tools/ordinary_final_cloud.py': sha(ROOT / 'tools/ordinary_final_cloud.py')})
        name = rehearsal.rehearsal_name()
        self.assertTrue(name.startswith(guard.PREFIX))
        plan = rehearsal.rehearsal_plan(base)
        decision = guard.check(ledgers=[plan['ledger']], forecast_minutes=plan['forecast_minutes'], hourly_rate=1.29,
                               storage_forecast_usd=plan['storage_forecast_usd'], now_epoch=time_module.time(),
                               reserve_minutes=manifest['workload_stop_reserve_seconds'] / 60, reaped=plan['reaped'])
        guard.require_reaped(plan['ledger'], plan['reaped'])
        self.assertGreaterEqual(decision['cap_usd'] + 1e-9, manifest['hard_ceiling_usd'])

        def launch():
            with patch.object(controller, 'INSTANCE_NAME', name), patch.object(controller, 'credential_path', rehearsal.no_credential):
                controller.execute()
        transport, console, failure = self.execute(root=ROOT, base=base, plan=plan, call=launch)
        self.assertIsNone(failure, failure)
        self.assertEqual(FakeProvider.state['launch_body']['name'], name)
        events = [r['event'] for r in ledger_rows(plan['ledger']) if r['event'] != 'budget_open']
        self.assertEqual(events, ['launch_intent', 'launch', 'termination'])
        self.assertEqual(read(base / 'CURRENT_PHASE.json')['phase'], 'terminated_and_cleaned')

    def test_general_path_caps_are_passed_never_defaulted(self):
        """R3 finished: budget_deadlines has no cap default; the general path's watchdog takes
        --soft-usd and --hard-usd (deploy_cloud_run passes the experiment's sealed caps) and its
        deadlines follow them."""
        with self.assertRaises(TypeError):
            cloud_run_common.budget_deadlines(1.99, 1000)
        folder = self.root / 'general'
        folder.mkdir()
        (folder / 'TERMINATE_REQUEST').touch()
        provider = SimpleNamespace(instance=lambda iid: dict(instance_id=iid, status='terminated'), terminate=lambda iid: None)
        argv = ['--arm', '--instance-id', 'a' * 32, '--hourly-rate', '1.99', '--running-epoch', '1000',
                '--directory', str(folder)]
        with patch.object(cloud_run_watchdog, 'load_credential', lambda path=None: 'unused'), \
                patch.object(cloud_run_watchdog, 'LambdaTermination', lambda path=None: provider):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                cloud_run_watchdog.main(argv)
            cloud_run_watchdog.main(argv + ['--soft-usd', '2', '--hard-usd', '3'])
        armed = read(folder / 'WATCHDOG_ARMED.json')
        self.assertAlmostEqual(armed['soft_epoch'], 1000 + 2 / 1.99 * 3600)
        self.assertAlmostEqual(armed['ceiling_epoch'], 1000 + 3 / 1.99 * 3600)
        self.assertTrue((folder / 'TERMINATION_VERIFIED.json').exists())
        # The emergency path terminates with no cap at all.
        emergency = self.root / 'emergency'
        emergency.mkdir()
        cloud_run_watchdog.terminate_now(provider, 'a' * 32, 1.99, 1000, emergency, sleep=lambda s: None, now=lambda: 1001.0)
        self.assertTrue((emergency / 'TERMINATION_VERIFIED.json').exists())
        source = Path(deploy_cloud_run.__file__).read_text(encoding='utf-8')
        self.assertIn("'--soft-usd', str(config['soft_usd']), '--hard-usd', str(config['hard_usd'])", source)
        self.assertNotIn('GENERAL_PATH_CAPS', Path(cloud_run_common.__file__).read_text(encoding='utf-8'))

    # ---- S2c item 7: a detached controller survives its parent; the reaper ends an orphan --

    def test_detached_controller_survives_its_parent_and_the_reaper_ends_an_orphan(self):
        """S2c item 7, with a mocked provider and real processes: (1) the wrapper's detached
        start leaves a controller that finishes the whole run after its parent is killed, and
        holds keep-awake while the instance exists; (2) a controller killed after its launch
        leaves an instance the reaper terminates at the ledger deadline, not before."""
        if os.name != 'nt':
            self.skipTest('the detached start is proven on the Windows operator machine')
        work = self.root / 'detach'
        work.mkdir()
        (work / 'mode.txt').write_text(parent_spawner(), encoding='utf8')
        script = str(Path(__file__).resolve())
        parent = subprocess.Popen([sys.executable, script, '--detach-parent', str(work)], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        child = None
        try:
            child = wait_for(work / 'child.json', 90)['pid']
            parent.kill()
            parent.wait(timeout=30)
            self.assertTrue(process_alive(child), 'the controller ended with its parent')
            (work / 'PARENT_KILLED').write_text('1', encoding='utf8')
            done = wait_for(work / 'child_done.json', 180)
            self.assertTrue(done['cleanup']['inventory_empty'])
            self.assertEqual(done['events'], ['launch_intent', 'launch', 'termination'])
            self.assertTrue(done['keep_awake_held'])
        finally:
            for pid in (child, parent.pid):
                if pid and process_alive(pid):
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
        hang = self.root / 'hang'
        hang.mkdir()
        write(hang / 'mock_state.json', dict(instances=[], keys=[]))
        open_ledger(hang / 'ledger.jsonl')
        orphan = subprocess.Popen([sys.executable, script, '--detached-child-hang', str(hang)], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time_module.time() + 120
            while time_module.time() < deadline and not any(r['event'] == 'launch' for r in ledger_rows(hang / 'ledger.jsonl')):
                time_module.sleep(0.5)
            launch = next(r for r in ledger_rows(hang / 'ledger.jsonl') if r['event'] == 'launch')
        finally:
            orphan.kill()
            orphan.wait(timeout=30)
        self.assertEqual(read(hang / 'mock_state.json')['instances'][0]['status'], 'active')
        from datetime import timedelta
        ends = instance_reaper.parse_time(launch['deadline_utc'])
        common = ['--mock-state', str(hang / 'mock_state.json'), '--ledger', str(hang / 'ledger.jsonl'),
                  '--append-to', str(hang / 'ledger.jsonl'), '--status', str(hang / 'reaper_status.json')]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(instance_reaper.main(common + ['--now', (ends - timedelta(seconds=30)).isoformat()]), 0)
        self.assertEqual(read(hang / 'mock_state.json')['instances'][0]['status'], 'active')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(instance_reaper.main(common + ['--now', (ends + timedelta(seconds=1)).isoformat()]), 0)
        self.assertEqual(read(hang / 'mock_state.json')['instances'][0]['status'], 'terminated')
        last = ledger_rows(hang / 'ledger.jsonl')[-1]
        self.assertEqual((last['event'], last['reason'], last['instance_name']), ('termination', 'deadline_passed', LOOP_NAME))

    # ---- S2 checker round 2 ---------------------------------------------------------------

    @staticmethod
    def docx_with_crlf(text):
        """A real DOCX holding `text`, stored uncompressed with a CR LF pair after its document
        part, so a line-ending conversion of the file's bytes is certain to corrupt it. Without
        python-docx, a stored zip with the same CR LF pair (bytes only)."""
        import zipfile
        try:
            import docx
        except ImportError:
            docx = None
        built = io.BytesIO()
        if docx is not None:
            document = docx.Document()
            document.add_paragraph(text)
            document.save(built)
        else:
            with zipfile.ZipFile(built, 'w') as out:
                out.writestr('word/document.xml', '<w:document/>')
        source = zipfile.ZipFile(io.BytesIO(built.getvalue()))
        stored = io.BytesIO()
        with zipfile.ZipFile(stored, 'w', zipfile.ZIP_STORED) as out:
            for info in source.infolist():
                data = source.read(info.filename)
                out.writestr(info.filename, data + b'\r\n' if info.filename == 'word/document.xml' else data)
        return stored.getvalue(), docx is not None

    def test_binary_workload_members_keep_their_bytes_and_reach_the_case_validation(self):
        """Round 2 item 1: only plain-text and HTML members are LF-normalised. A DOCX or PDF
        holding a CR LF pair comes through byte-identical, from a folder and from an archive;
        the case manifest keeps its own bytes; and the case validation reads the DOCX's text,
        where a converted file would be extracted as empty and silently skipped."""
        import tarfile as tar_module
        docx_bytes, readable = self.docx_with_crlf('First text of round one.')
        self.assertIn(b'\r\n', docx_bytes)
        pdf = b'%PDF-1.4\r\n%\xe2\xe3\xcf\xd3\r\nfixture stream\r\n'
        case = json.dumps(self.live_case(), indent=1).replace('\n', '\r\n').encode()
        given = {'context/round_one.docx': docx_bytes, 'context/round_two.md': b'Second text of round two.\r\n',
                 'context/paper.pdf': pdf, 'context/page.html': b'<p>x</p>\r\n', 'conventions/rules.md': b'Rule.\r\n',
                 '_review_targets.json': b'{"targets": []}\r\n', runner.CASE_MANIFEST: case}
        folder = self.root / 'r2i1' / 'folder'
        for name, data in given.items():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(data)
        archive = self.root / 'r2i1' / 'test.tar'
        with tar_module.open(archive, 'w') as out:
            for name, data in given.items():
                info = tar_module.TarInfo('./' + name)
                info.size = len(data)
                out.addfile(info, io.BytesIO(data))
        for source in (folder, archive):
            with self.subTest(source=source.name):
                members = sealer.workload_members(source)
                self.assertEqual(members['context/round_one.docx'], docx_bytes)
                self.assertEqual(members['context/paper.pdf'], pdf)
                self.assertEqual(members[runner.CASE_MANIFEST], case)
                self.assertEqual(members['context/round_two.md'], b'Second text of round two.\n')
                self.assertEqual(members['context/page.html'], b'<p>x</p>\n')
                self.assertEqual(members['conventions/rules.md'], b'Rule.\n')
                self.assertEqual(members['_review_targets.json'], b'{"targets": []}\n')
        if readable:
            documents = runner.case_corpus_documents(
                {n[len('context/'):]: d for n, d in members.items() if n.startswith('context/')},
                (ROOT / 'scripts/pipeline.py').read_bytes())
            self.assertEqual(documents['round_one'], 'First text of round one.')
            runner.validate_live_case_manifest(json.loads(members[runner.CASE_MANIFEST].decode('utf-8')), documents)

    def test_a_batch_entry_launched_in_a_run_folder_is_consumed(self):
        """Round 2 item 2: a batch entry launched earlier with --output-dir carries only
        RUN_FOLDER.json; it is refused as consumed, as one carrying LAUNCH_INTENT.json is,
        before any provider call."""
        for marker in ('RUN_FOLDER.json', 'LAUNCH_INTENT.json'):
            with self.subTest(marker=marker):
                self.setUp()
                bundles, entries = self.batch_bundles()
                write(bundles[('i2', 'B3')] / marker, dict(run_folder='elsewhere'))
                with self.assertRaisesRegex(RuntimeError, 'Batch bundle already consumed'):
                    self.execute(plan=fixture_plan(self.ledger, batch=entries))
                self.assertIsNone(FakeProvider.state)
                self.assertEqual([r['event'] for r in ledger_rows(self.ledger)], ['budget_open'])

    def test_an_intent_without_an_instance_stops_accruing_and_the_reaper_closes_it(self):
        """Round 2 item 3: an open launch accrues only to its recorded deadline; past it, with
        no instance of its name listed, the reaper closes it with one termination line of
        declared fields (charged to the deadline), after which the guard admits a launch; a
        listed instance past its deadline is still terminated, never merely closed."""
        from datetime import datetime, timedelta, timezone
        now = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
        opening = dict(self.OPEN_LINE, storage_usd_per_day=0.0)
        intent = dict(event='launch_intent', time_utc='2026-10-27T10:00:00+00:00', launch_requested_utc='2026-10-27T10:00:00+00:00',
                      instance_name='shimmer-loop-lost', type='gpu_1x_a10', region='us-east-1', price_usd_per_hour=1.29,
                      cap_usd=2.0, deadline_utc='2026-10-27T11:30:00+00:00', purpose='fixture')
        for later in (now, now + timedelta(days=3)):
            self.assertAlmostEqual(instance_reaper.ledger_view([opening, intent], later)[2], 1.29 * 90 / 60, places=6)
        ledger = self.root / 'r2i3' / 'ledger.jsonl'
        write_lines(ledger, [opening, intent])
        state = self.root / 'r2i3' / 'state.json'
        write(state, dict(instances=[dict(instance_id='b' * 32, name='someone-else', status='active')]))
        provider = instance_reaper.MockProvider(state)
        status = instance_reaper.reap(provider, [ledger], ledger, now=instance_reaper.parse_time('2026-10-27T11:00:00+00:00'))
        self.assertEqual((status['closed_without_instance'], len(ledger_rows(ledger))), ([], 2))
        with self.assertRaisesRegex(guard.GuardRefusal, 'Another loop instance'):
            guard.check(ledgers=[ledger], forecast_minutes=60, hourly_rate=1.29, storage_forecast_usd=0, now_epoch=now.timestamp(),
                        reserve_minutes=15, reaped=[])
        status = instance_reaper.reap(provider, [ledger], ledger, now=now)
        self.assertEqual(status['closed_without_instance'], [dict(instance_name='shimmer-loop-lost', reason='intent_without_instance')])
        self.assertEqual(status['terminated'], [])
        line = ledger_rows(ledger)[-1]
        self.assertLessEqual(set(line), set(guard.LEDGER_FIELDS))
        self.assertEqual((line['event'], line['by'], line['instance_name'], line['actual_minutes'], line['actual_cost']),
                         ('termination', 'reaper', 'shimmer-loop-lost', 90, round(1.29 * 1.5, 4)))
        self.assertEqual(guard.ledger_state([ledger], now.timestamp())[1], [])
        guard.check(ledgers=[ledger], forecast_minutes=60, hourly_rate=1.29, storage_forecast_usd=0, now_epoch=now.timestamp(),
                    reserve_minutes=15, reaped=[])
        status = instance_reaper.reap(provider, [ledger], ledger, now=now + timedelta(minutes=5))
        self.assertEqual((status['closed_without_instance'], len(ledger_rows(ledger))), ([], 3))
        self.assertEqual(read(state)['instances'][0]['status'], 'active')
        # A launch whose instance is already gone is closed the same way.
        gone = dict(intent, event='launch', instance_id='c' * 32, instance_name='shimmer-loop-gone')
        ledger2 = self.root / 'r2i3' / 'gone.jsonl'
        write_lines(ledger2, [opening, gone])
        status = instance_reaper.reap(provider, [ledger2], ledger2, now=now)
        self.assertEqual(status['closed_without_instance'], [dict(instance_name='shimmer-loop-gone', reason='instance_not_listed')])
        self.assertEqual(ledger_rows(ledger2)[-1]['instance_id'], 'c' * 32)
        # A listed instance past its deadline is terminated, and only that line is written.
        write(state, dict(instances=[dict(instance_id='d' * 32, name='shimmer-loop-lost', status='active')]))
        ledger3 = self.root / 'r2i3' / 'listed.jsonl'
        write_lines(ledger3, [opening, intent])
        status = instance_reaper.reap(provider, [ledger3], ledger3, now=now)
        self.assertEqual((status['terminated'], status['closed_without_instance']),
                         ([dict(instance_name='shimmer-loop-lost', reason='deadline_passed')], []))
        self.assertEqual(read(state)['instances'][0]['status'], 'terminated')
        self.assertEqual([r['event'] for r in ledger_rows(ledger3)], ['budget_open', 'launch_intent', 'termination'])

    def test_the_cap_ceiling_is_the_ledgers_hard_stop(self):
        """Round 2 item 4: cap = min(1.5 x forecast, hard stop - spend - running caps - storage),
        the hard stop read from the latest budget line; a line with no hard stop gives the IV.3
        formula with the one-dollar margin."""
        now = 1_000_000.0 + 3600
        ledger = self.root / 'r2i4' / 'ledger.jsonl'
        open_ledger(ledger)
        write_lines(ledger, [dict(event='launch', instance_id='a' * 32, instance_name='shimmer-loop-old', price_usd_per_hour=1.29,
                                  launch_requested_utc=guard.utc(now - 7200)),
                             dict(event='termination', instance_id='a' * 32, instance_name='shimmer-loop-old', actual_cost=55.0),
                             dict(event='budget_change', time_utc=guard.utc(now - 60), budget_usd=70.0, hard_stop_usd=62.0)])
        decide = lambda: guard.check(ledgers=[ledger], forecast_minutes=100, hourly_rate=1.29, storage_forecast_usd=3.9,
                                     now_epoch=now, reserve_minutes=15, reaped=[])
        forecast = guard.forecast_usd(100, 1.29)
        decision = decide()
        self.assertEqual((decision['budget_usd'], decision['hard_stop_usd']), (70.0, 62.0))
        self.assertAlmostEqual(decision['cap_usd'], 62.0 - decision['spend_usd'] - 3.9, places=3)
        self.assertLess(decision['cap_usd'], 1.5 * forecast)
        write_lines(ledger, [dict(event='budget_change', time_utc=guard.utc(now - 30), budget_usd=70.0, hard_stop_usd=60.0)])
        with self.assertRaisesRegex(guard.GuardRefusal, 'leaves less than the forecast'):
            decide()
        write_lines(ledger, [dict(event='budget_change', time_utc=guard.utc(now - 10), budget_usd=70.0)])
        decision = decide()
        self.assertEqual(decision['hard_stop_usd'], 69.0)
        self.assertAlmostEqual(decision['cap_usd'], min(1.5 * forecast, 70.0 - decision['spend_usd'] - 3.9 - 1.0), places=3)
        self.assertAlmostEqual(guard.per_run_cap(2.0, 10.0, 1.0, 3.9, 69.0), min(3.0, 70.0 - 10.0 - 1.0 - 3.9 - 1.0))

    def test_the_guard_refuses_a_budget_line_it_cannot_read(self):
        """Round 2 item 5: a budget_open line with no readable budget_usd is refused by the
        guard, and the reaper reading it has no hard stop, so it ends every loop instance."""
        now = 1_000_000.0 + 60
        for k, unreadable in enumerate((dict(), dict(budget_usd='seventy'), dict(budget_usd=70.0, hard_stop_usd=80.0))):
            with self.subTest(line=unreadable):
                ledger = self.root / 'r2i5' / ('%d.jsonl' % k)
                write_lines(ledger, [dict(dict(event='budget_open', time_utc=guard.utc(1_000_000.0), storage_usd_per_day=0.0,
                                               a10_reference_price_usd_per_hour=1.29), **unreadable)])
                with self.assertRaisesRegex(guard.GuardRefusal, 'No readable budget line'):
                    guard.check(ledgers=[ledger], forecast_minutes=60, hourly_rate=1.29, storage_forecast_usd=0.0, now_epoch=now,
                                reserve_minutes=15, reaped=[])
        state = self.root / 'r2i5' / 'state.json'
        write(state, dict(instances=[dict(instance_id='b' * 32, name=LOOP_NAME, status='active')]))
        status = instance_reaper.reap(instance_reaper.MockProvider(state), [ledger], ledger,
                                      now=instance_reaper.parse_time(guard.utc(now)))
        self.assertEqual(status['terminated'], [dict(instance_name=LOOP_NAME, reason='no_budget_recorded')])

    def test_a_held_lock_is_reported_with_its_age_and_its_pid(self):
        """Round 2 item 6: a launch's lock records its pid and creation time; a held lock is
        refused in one line naming its age, its pid and whether that pid runs, and is left in
        place for the operator."""
        lock = Path(str(self.ledger) + '.lock')
        created = time_module.time() - 3600
        held = json.dumps(dict(pid=os.getpid(), created_epoch=created, time_utc=guard.utc(created)))
        lock.write_text(held, encoding='utf8')
        with self.assertRaises(guard.GuardRefusal) as caught:
            self.execute()
        message = str(caught.exception)
        self.assertNotIn('\n', message)
        self.assertIn('holds the ledger lock', message)
        self.assertTrue(3590 <= int(re.search(r'held (\d+) s', message).group(1)) <= 3700, message)
        self.assertIn('by pid %d (running)' % os.getpid(), message)
        self.assertEqual((lock.read_text(encoding='utf8'), FakeProvider.state['launches']), (held, 0))
        ended = subprocess.Popen([sys.executable, '-c', 'pass'])
        ended.wait()
        lock.write_text(json.dumps(dict(pid=ended.pid, created_epoch=created, time_utc=guard.utc(created))), encoding='utf8')
        with self.assertRaisesRegex(guard.GuardRefusal, r'by pid %d \(not running\)' % ended.pid):
            guard.acquire_lock(self.ledger)
        lock.unlink()
        fresh = guard.acquire_lock(self.ledger)
        value = json.loads(fresh.read_text(encoding='utf8'))
        self.assertEqual(value['pid'], os.getpid())
        self.assertLess(abs(value['created_epoch'] - time_module.time()), 60)
        guard.release_lock(fresh)

    def in_repository_sealed_bundle(self):
        """A sealed bundle INSIDE a fixture repository (the case SEALED-RUN-A refuses), its test
        manifest and archive outside it; returns (repo, bundle, plan)."""
        repo, commit, _ = self.git_repo()
        outside = self.root / 'outside'
        outside.mkdir(parents=True, exist_ok=True)
        archive = outside / 'test.tar'
        archive.write_bytes(b'sealed test archive fixture')
        manifest = outside / 'seal_manifest.json'
        write(manifest, dict(archive_sha256=sha(archive), code_commit=commit, scorer_sha256='c' * 64))
        bundle = repo / 'bundles' / 'sealed'
        bundle.mkdir(parents=True)
        (bundle / 'assets.tar').write_bytes(b'assets fixture')
        with patch.object(controller, 'ROOT', repo):
            make_bundle(bundle, bundle / 'assets.tar', source_commit=commit, protected_test=True, test_archive_sha256=sha(archive))
            reseal(bundle, bundle / 'assets.tar', exposure='sealed', test_manifest_sha256=sha(manifest),
                   test_archive_sha256=sha(archive), code_commit=commit)
        self.bind(bundle)
        return repo, bundle, fixture_plan(self.ledger, test_manifest=manifest, frozen_tag='loop-s08-frozen')

    def test_a_sealed_bundle_inside_the_repository_is_refused_before_any_write(self):
        """Round 2 item 7: with --output-dir, and with --detach, a sealed bundle inside the
        repository is refused before anything is written into it or anywhere else."""
        repo, bundle, plan = self.in_repository_sealed_bundle()
        runs = self.root / 'outside' / 'runs'
        before = self.tree(repo)
        with self.assertRaisesRegex(RuntimeError, 'A sealed bundle must sit outside the repository'):
            self.execute(root=repo, base=bundle, call=lambda: bound.execute(bundle, plan, runs))
        self.assertEqual(self.tree(repo), before)
        self.assertFalse(runs.exists())
        self.assertIsNone(FakeProvider.state)

        def spawned(argv, log):
            raise AssertionError('a detached controller was started')
        argv = ['--bundle', str(bundle), '--output-dir', str(runs), '--ledger', str(self.ledger), '--purpose', 'sealed-fixture',
                '--forecast-minutes', '120', '--storage-forecast-usd', '3.9', '--test-manifest', str(plan['test_manifest']),
                '--frozen-tag', 'loop-s08-frozen', '--detach']
        with patch.object(controller, 'ROOT', repo), patch.object(bound, 'spawn_detached', spawned), \
                self.assertRaisesRegex(RuntimeError, 'A sealed bundle must sit outside the repository'):
            bound.main(argv)
        self.assertEqual(self.tree(repo), before)
        self.assertFalse((bundle / bound.DETACH_LOG).exists() or (bundle / 'controller_process.json').exists())

    def test_the_frozen_tag_resolves_only_a_tag(self):
        """Round 2 item 8: --frozen-tag resolves refs/tags/<name> only, a lightweight or an
        annotated tag peeled to its commit; a commit id, a branch, HEAD or any revision
        expression is refused, and a sealed launch naming one never reaches the provider."""
        repo, commit, first = self.git_repo()
        git = lambda *a: subprocess.run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', *a],
                                        cwd=repo, capture_output=True, check=True).stdout.decode().strip()
        git('tag', '-a', 'annotated-frozen', '-m', 'fixture')
        branch = git('rev-parse', '--abbrev-ref', 'HEAD')
        with patch.object(controller, 'ROOT', repo):
            self.assertEqual(controller.frozen_commit('loop-s08-frozen'), commit)
            self.assertEqual(controller.frozen_commit('annotated-frozen'), commit)
            self.assertEqual(controller.frozen_commit('older'), first)
            for revision in (commit, commit[:12], 'HEAD', branch, 'refs/heads/' + branch, 'loop-s08-frozen~1',
                             'loop-s08-frozen^{commit}', 'older..loop-s08-frozen', '--all', 'no-such-tag'):
                with self.subTest(revision=revision), self.assertRaisesRegex(RuntimeError, 'Frozen tag not found'):
                    controller.frozen_commit(revision)
        bundle, manifest = self.sealed_bundle(commit)
        with self.assertRaisesRegex(RuntimeError, 'Frozen tag not found'):
            self.execute(root=repo, base=bundle, plan=fixture_plan(self.ledger, test_manifest=manifest, frozen_tag=commit))
        self.assertIsNone(FakeProvider.state)

    def test_a_prose_purpose_is_refused_before_any_provider_call(self):
        """Round 2 item 10: the purpose is checked in the launch plan, before any provider call
        and before the bound wrapper writes a run folder; the CLI help says what it is."""
        with self.assertRaisesRegex(guard.GuardRefusal, 'short identifier'):
            self.execute(plan=fixture_plan(self.ledger, purpose='Checking the fixture on item 3'))
        self.assertIsNone(FakeProvider.state)
        self.assertEqual([r['event'] for r in ledger_rows(self.ledger)], ['budget_open'])
        repo = self.root / 'repo'
        repo.mkdir()
        bundle = self.root / 'outside' / 'bundle'
        bundle.mkdir(parents=True)
        (bundle / 'assets.tar').write_bytes(b'assets fixture')
        with patch.object(controller, 'ROOT', repo):
            make_bundle(bundle, bundle / 'assets.tar')
        self.bind(bundle)
        runs = self.root / 'outside' / 'runs'
        with self.assertRaisesRegex(guard.GuardRefusal, 'short identifier'):
            self.execute(root=repo, base=bundle,
                         call=lambda: bound.execute(bundle, fixture_plan(self.ledger, purpose='Why: a test'), runs))
        self.assertFalse(runs.exists())
        self.assertIsNone(FakeProvider.state)
        self.assertIn('a short identifier', ' '.join(bound.parser().format_help().split()))

    def test_the_a10_reference_price_is_the_latest_recorded_on_any_budget_line(self):
        """Round 2 item 11: the type rule's reference is the latest A10 price recorded on a
        budget_open or budget_change line, by its own time, across the ledgers read."""
        start = 1_000_000.0
        ledger = self.root / 'r2i11' / 'ledger.jsonl'
        open_ledger(ledger, start)
        self.assertEqual(guard.a10_reference_rate([ledger]), 1.29)
        change = lambda offset, **k: dict(dict(event='budget_change', time_utc=guard.utc(start + offset), budget_usd=70.0,
                                               hard_stop_usd=69.0), **k)
        write_lines(ledger, [change(600, a10_reference_price_usd_per_hour=1.49)])
        self.assertEqual(guard.a10_reference_rate([ledger]), 1.49)
        write_lines(ledger, [change(1200), change(300, a10_reference_price_usd_per_hour=1.10)])
        self.assertEqual(guard.a10_reference_rate([ledger]), 1.49)
        other = self.root / 'r2i11' / 'R_ledger.jsonl'
        write_lines(other, [change(1800, a10_reference_price_usd_per_hour=1.59)])
        self.assertEqual(guard.a10_reference_rate([ledger, other]), 1.59)
        # The type rule reads it: at twice 1.59 the H100's 2.99 is admitted, at twice 1.29 it was not.
        self.assertEqual([c['type'] for c in guard.instance_candidates(self.TYPES, guard.a10_reference_rate([ledger, other]))],
                         ['gpu_1x_a10', 'gpu_1x_a6000', 'gpu_1x_a100_sxm4', 'gpu_1x_h100_pcie'])


def shlex_quote(value):
    import shlex
    return shlex.quote(value)


def linux_shell():
    """A callable running one command through exactly one Linux shell, or None if unavailable."""
    import shutil
    exe = shutil.which('wsl.exe') or shutil.which('wsl')
    if exe is None:
        return None
    def run(command, raw=False, timeout=60):
        r = subprocess.run([exe, '-d', 'Ubuntu', '-e', 'bash', '-c', command], capture_output=True, timeout=timeout)
        if raw:
            return r.returncode, r.stdout
        return r.returncode, (r.stdout + r.stderr).decode('utf8', 'replace')
    try:
        rc, out = run('echo linux-shell-ready')
    except Exception:
        return None
    return run if rc == 0 and 'linux-shell-ready' in out else None


_ORIGINAL_POLL_OUTCOME = controller.poll_outcome


def neutralized_poll_outcome(returncode, stdout):
    """The pre-correction reading: a connection that fails is the phase's result.

    Calls the original classifier captured at import, never the patched module
    attribute, so the neutralised run exercises the intended reading rather than
    recursing into itself."""
    if returncode != 0:
        return 'dead', None, []
    return _ORIGINAL_POLL_OUTCOME(returncode, stdout)


def v4_phases_dir(remote):
    """The run v4 layout: phase files under the remote root, which fresh_directory requires absent."""
    return remote.rstrip('/') + '/phases'


_ORIGINAL_LOADER = cloud_run_watchdog.load_credential


def printing_load_credential(credential_file=None):
    """A loader that prints the value it loaded: the leak the key test must catch.
    Calls the original captured at import, so the neutralised run loads for real."""
    value = _ORIGINAL_LOADER(credential_file)
    print('loaded provider access value:', value)
    return value


_CONTROLLER_FILES = {'ordinary_final_cloud.py', 'ordinary_final_bound_cloud.py',
                     'lambda_experiment_provider.py', 'ordinary_final_run.py',
                     'loop_budget_guard.py', 'instance_reaper.py', 'keep_awake.py', 'run_remote_experiment.py'}


def read_without_the_controller_binding(path):
    """The pre-binding reading of the manifest: the controller, its wrapper, the
    adapter and the runner are not among the files a bundle is bound to, so a
    launch under a changed controller proceeds.

    Neutralises the BINDING (what the manifest claims to pin) rather than the
    hash function, which a sealed-with-the-same-stand-in manifest would still
    match. Only execute()'s own read is affected; every other read is untouched."""
    value = read(path)
    if isinstance(value, dict) and 'local_control_hashes' in value:
        value = dict(value, local_control_hashes={n: d for n, d in value['local_control_hashes'].items()
                                                  if Path(n).name not in _CONTROLLER_FILES})
    return value


# Imported here, after FakeProvider and INSTANCE exist, because the rehearsal imports them.
import ordinary_final_rehearsal as rehearsal
import analyze_ordinary_final_run as analysis
import deploy_cloud_run
import run_remote_experiment


# ---- S2c item 7: real processes for the detached-controller proof -----------------------

def parent_spawner():
    """How the proof's parent starts the controller: through the wrapper's detached start."""
    return 'detached'


def wait_for(path, seconds):
    end = time_module.time() + seconds
    while time_module.time() < end:
        try:
            return json.loads(Path(path).read_text(encoding='utf8'))
        except (OSError, ValueError):
            time_module.sleep(0.25)
    raise AssertionError('timed out waiting for ' + Path(path).name)


def process_alive(pid):
    out = subprocess.run(['tasklist', '/FI', 'PID eq %d' % int(pid), '/NH'], capture_output=True, text=True)
    return str(pid) in out.stdout


_REAL_KEEP_AWAKE = controller.keep_awake


class FileProvider:
    """A mocked provider whose state is one JSON file, shared with the reaper's MockProvider."""
    path = None

    def __init__(self, credential=None):
        pass

    def load(self):
        return json.loads(Path(FileProvider.path).read_text(encoding='utf8'))

    def store(self, state):
        Path(FileProvider.path).write_text(json.dumps(state, indent=1), encoding='utf8')

    def request(self, endpoint, body=None, method=None):
        s = self.load()
        if endpoint == 'instances':
            return {'data': [dict(instance_id=i['instance_id'], name=i['name']) for i in s['instances']
                             if i['status'] not in ('terminated', 'terminating')]}
        if endpoint == 'instance-types':
            return {'data': [json.loads(json.dumps(A10_TYPE))]}
        if endpoint == 'images':
            return {'data': [dict(IMAGE)]}
        if endpoint == 'ssh-keys' and body is not None:
            s['keys'].append(dict(id=KEY_ID, name=body['name']))
            self.store(s)
            return {'data': [dict(id=KEY_ID, name=body['name'])]}
        if endpoint == 'ssh-keys':
            return {'data': list(s['keys'])}
        if endpoint.startswith('ssh-keys/') and method == 'DELETE':
            s['keys'] = [k for k in s['keys'] if k['id'] != endpoint.split('/')[1]]
            self.store(s)
            return {'data': {}}
        if endpoint == 'instance-operations/launch':
            s['instances'].append(dict(instance_id=INSTANCE, name=body['name'], status='active',
                                       type=body['instance_type_name'], region=body['region_name']))
            self.store(s)
            return {'data': dict(instance_ids=[INSTANCE])}
        raise AssertionError('unexpected provider endpoint ' + endpoint)

    def instance(self, instance_id):
        item = next((i for i in self.load()['instances'] if i['instance_id'] == instance_id), None)
        return dict(instance_id=instance_id, status=item['status'] if item else 'terminated', public_ip='10.0.0.2',
                    hourly_rate=1.29, name='fixture', type='gpu_1x_a10', region='us-east-1')

    def terminate(self, instance_id):
        s = self.load()
        for item in s['instances']:
            if item['instance_id'] == instance_id:
                item['status'] = 'terminated'
        self.store(s)


class HangingTransport(FakeTransport):
    """The instance never answers ssh: the controller blocks after its launch, as one would
    whose session or machine stopped, until something kills it."""
    def run(self, argv, capture_output=True, timeout=None):
        if argv[0] == 'ssh' and argv[-1] == 'true':
            while True:
                time_module.sleep(1)
        return super().run(argv, capture_output, timeout)


def child_fixture(work):
    root = Path(work) / 'run'
    root.mkdir()
    (root / 'assets.tar').write_bytes(b'assets fixture')
    with patch.object(controller, 'ROOT', root):
        make_bundle(root / 'bundle', root / 'assets.tar')
    credential = root / 'operator_provider_access.txt'
    credential.write_text('placeholder, not a key\n', encoding='utf8')
    outputs = {'evidence_hash': (hashlib.sha256(EVIDENCE).hexdigest() + '  collected_evidence.tar.gz\n').encode()}
    return root, root / 'bundle', credential, outputs


def detached_child(work):
    """The controller the proof starts detached: it waits until its parent is gone, then
    runs the whole fixture launch with the real keep-awake helper and reports."""
    work = Path(work)
    end = time_module.time() + 90
    while not (work / 'PARENT_KILLED').exists():
        if time_module.time() > end:
            return
        time_module.sleep(0.2)
    root, base, credential, outputs = child_fixture(work)
    ledger = root / 'ledger.jsonl'
    open_ledger(ledger)
    FakeProvider.state, FakeProvider.ledger = None, ledger
    held = []

    def keep(action):
        value = _REAL_KEEP_AWAKE(action)
        held.append((action, value))
        return value
    run_controller(root, base, fixture_plan(ledger), FakeTransport(base, None, outputs), FakeProvider, FakeClock(),
                   credential, keep=keep)
    write(work / 'child_done.json', dict(cleanup=read(base / 'cleanup.json'),
          events=[r['event'] for r in ledger_rows(ledger) if r['event'] != 'budget_open'],
          keep_awake_held=any(a == 'hold' and v for a, v in held)))


def detach_parent(work):
    """The parent the proof kills: it starts the controller and then only waits."""
    work = Path(work)
    if (work / 'mode.txt').read_text(encoding='utf8').strip() == 'detached':
        pid = bound.spawn_detached([Path(__file__).resolve(), '--detached-child', work], work / 'child.log')
        write(work / 'child.json', dict(pid=pid))
    else:
        # The neutralised start: the controller runs inside this process, so it dies with it.
        write(work / 'child.json', dict(pid=os.getpid()))
        detached_child(work)
    time_module.sleep(600)


def detached_child_hang(work):
    """A controller that launches and then hangs, to be killed: its ledger lines are all the
    reaper has."""
    work = Path(work)
    root, base, credential, outputs = child_fixture(work)
    FileProvider.path = work / 'mock_state.json'
    FakeProvider.ledger = None
    run_controller(root, base, fixture_plan(work / 'ledger.jsonl'), HangingTransport(base, None, outputs), FileProvider,
                   FakeClock(), credential)


# ---- mutants for the S2 proofs -------------------------------------------------------------

_ORIGINAL_LEDGER_LINE = guard.ledger_line
_ORIGINAL_LEDGER_STATE = guard.ledger_state
_ORIGINAL_OFFERED = guard.offered
_ORIGINAL_ADMIT = controller.admit
_ORIGINAL_SCHEDULE = controller.batch_schedule


def ledger_line_with_test_content(event, **fields):
    """A ledger line that also carries content from the run: the leak R5 forbids."""
    return dict(_ORIGINAL_LEDGER_LINE(event, **fields), document='fixture test text')


def double_counting_state(ledgers, now_epoch):
    """Each ledger read on its own: a launch copied from R's ledger counted twice."""
    parts = [_ORIGINAL_LEDGER_STATE([p], now_epoch) for p in ledgers]
    return (sum(p[0] for p in parts), [r for p in parts for r in p[1]], sum(p[2] for p in parts),
            [r for p in parts for r in p[3]])


def guard_that_admits_everything(**kwargs):
    forecast = guard.forecast_usd(kwargs['forecast_minutes'], kwargs['hourly_rate'])
    return dict(forecast_usd=forecast, cap_usd=1e9, capped_minutes=1e9, spend_usd=0.0, running_caps_usd=0.0,
                storage_forecast_usd=0.0)


def offered_at_any_price(entry_by_type, cand, reference, fallback):
    """The type rule without its price limits."""
    return _ORIGINAL_OFFERED(entry_by_type, dict(cand, max_hourly_rate=float('inf')), float('inf'), fallback)


_ORIGINAL_SELECT = guard.select_instance


def select_without_waiting(list_types, candidates, reference_rate, clock, poll_seconds=None, interval=None):
    return _ORIGINAL_SELECT(list_types, candidates, reference_rate, clock, 0)


def admit_as_exposed(m, seal, plan, base):
    """A sealed run treated as exposed: its progress would print phase names."""
    return dict(_ORIGINAL_ADMIT(m, seal, plan, base), exposure='exposed')


def arm_major_schedule(entries):
    """Every B3 first, then every B1: a stop part way leaves no pair."""
    value = sorted(_ORIGINAL_SCHEDULE(entries), key=lambda e: (controller.BATCH_ARMS.index(e['arm']), e['index']))
    return [dict(e, index=k) for k, e in enumerate(value)]


def declaration_for_any_bundle(base, digest):
    """The declaration read without its tie to this bundle's archive digest."""
    path = Path(base) / 'asset_copy_declaration.json'
    if not path.exists():
        return None
    value = read(path)
    return dict(filesystem_name=value['filesystem_name'], mount=value['mount'].rstrip('/'))


_ORIGINAL_LEDGER_VIEW = instance_reaper.ledger_view
_ORIGINAL_DECLARATION = controller.asset_copy_declaration


def ledger_view_by_key_only(rows, now):
    """The reading before A1: a termination closes only the launch keyed by its own id, so an
    intent keyed by its name stays open when its termination carries the id."""
    stripped = [dict(r, instance_name=None) if r.get('event') == 'termination' and r.get('instance_id') else r for r in rows]
    return _ORIGINAL_LEDGER_VIEW(stripped, now)


def declaration_written_when_absent(base, digest):
    """A controller that writes a declaration of its own: what C34 forbids."""
    path = Path(base) / 'asset_copy_declaration.json'
    if not path.exists():
        write(path, dict(filesystem_name='controller-written', mount='/x', operator_authorized=True, assets_sha256=digest))
    return _ORIGINAL_DECLARATION(base, digest)


_ORIGINAL_BUDGET_FIGURES = instance_reaper.budget_figures


def budget_figures_without_the_hard_stop(rows):
    """A reading that drops the budget line's own hard stop: the budget less the margin."""
    budget, _ = _ORIGINAL_BUDGET_FIGURES(rows)
    return budget, None if budget is None else budget - instance_reaper.MARGIN_USD


def frozen_commit_of_any_revision(tag):
    """The reading before round 2 item 8: any revision git resolves to a commit is admitted."""
    result = subprocess.run(['git', 'rev-parse', '--verify', tag + '^{commit}'], cwd=controller.ROOT, capture_output=True,
                            timeout=30)
    if result.returncode != 0:
        raise RuntimeError('Frozen tag not found')
    return result.stdout.decode().strip()


def a10_rate_from_the_opening_line(ledgers):
    """The reading before round 2 item 11: the A10 price from budget_open lines only."""
    rate = None
    for path in ledgers:
        for row in instance_reaper.read_ledger(path):
            if row.get('event') == 'budget_open' and row.get('a10_reference_price_usd_per_hour') is not None:
                rate = row['a10_reference_price_usd_per_hour']
    if rate is None:
        raise guard.GuardRefusal('No recorded A10 reference price in the ledgers given')
    return float(rate)


def archive_names_ignoring_extras(names, extra=(), extras=None):
    return [n for n in names if (n.startswith(sealer.RUNTIME_PREFIXES) or n in sealer.RUNTIME_FILES or n in extra)
            and not (n.endswith('_checks.py') or '/fixtures/' in n)]


# (test, owner, attribute, mutant): the one mechanism each load-bearing test proves.
NEUTRALIZATIONS = [
    ('test_dead_connection_after_remote_completion_is_completed_and_the_run_proceeds', controller, 'poll_outcome', neutralized_poll_outcome),
    ('test_connection_loss_during_the_workload_keeps_polling_and_records_progress', controller, 'poll_outcome', neutralized_poll_outcome),
    ('test_fresh_directory_passes_because_the_launcher_creates_nothing_under_the_remote_root', controller, 'phases_dir', v4_phases_dir),
    # A probe that no longer hashes the copy: a corrupt copy would be used as the sealed archive.
    ('test_asset_copy_mismatch_is_refused_uploaded_and_never_overwritten', controller, 'asset_copy_probe_command',
     lambda mount, digest: 'echo MATCH'),
    # A seal that does not bind the controller: a changed controller launches.
    ('test_controller_binding_a_changed_controller_refuses_before_any_instance', controller, 'read',
     read_without_the_controller_binding),
    # A credential path fixed in the file instead of resolved: SHIMMER_CONFIG_PATH is ignored.
    ('test_credential_resolves_from_shimmer_config_path_at_the_moment_of_use', controller, 'credential_path',
     lambda: Path('fixed-when-written.txt')),
    # The refusal dropped: an unresolvable credential reaches the provider as None.
    ('test_no_resolvable_credential_refuses_in_one_line_naming_shimmer_config_path', controller, 'credential_path',
     lambda: agent_wrapper.resolve_config_path()),
    # A loader that prints what it loaded: the sentinel reaches stdout. Proven through
    # BOTH names the loader is reached by: the watchdog's own, and the adapter's, which
    # imports it by name (lambda_experiment_provider.py, from cloud_run_watchdog import
    # load_credential), so patching the watchdog alone never reaches an adapter call.
    ('test_no_key_value_is_ever_printed', cloud_run_watchdog, 'load_credential', printing_load_credential),
    ('test_no_key_value_is_ever_printed', provider_adapter, 'load_credential', printing_load_credential),
    # A widened removal target: the Linux home itself instead of the rehearsal folder under it.
    ('test_rehearsal_removes_only_its_own_folder_under_the_linux_home', rehearsal, 'rehearsal_root',
     lambda home: home.strip().rstrip('/') or '/'),
    # S2 (loop stage S2b and S2c), one mechanism per proof.
    # S2c item 6, R5: a ledger line carrying run content.
    ('test_ledger_lines_carry_the_iv3_fields_and_the_name_and_deadline_precede_the_launch', guard, 'undeclared',
     lambda fields: set()),
    # S2c item 5, R4: one launch counted twice across the private and R ledgers.
    ('test_budget_guard_refuses_each_iv3_case_and_counts_each_launch_once', guard, 'ledger_state', double_counting_state),
    # S2c item 5: the guard no longer consulted on the launch path.
    ('test_controller_launch_is_refused_by_the_guard_before_any_instance', guard, 'check', guard_that_admits_everything),
    # R4: the general cloud path accepting a loop ledger or name (both of its tools).
    ('test_the_general_cloud_path_refuses_loop_names_and_ledgers', deploy_cloud_run, 'refuse_general_path',
     lambda names=(), argv=(): None),
    ('test_the_general_cloud_path_refuses_loop_names_and_ledgers', run_remote_experiment, 'refuse_general_path',
     lambda names=(), argv=(): None),
    # S2c item 4, R3: the type rule without its price limits.
    ('test_budget_parameters_come_from_the_manifest_and_the_type_rule', guard, 'offered', offered_at_any_price),
    # R3: falling back to another type without first polling the A10 for 30 minutes.
    ('test_controller_launches_a_fallback_type_only_inside_the_sealed_cap', guard, 'select_instance',
     select_without_waiting),
    # S2c item 1: the run written into the bundle whatever the output path.
    ('test_external_bundle_and_output_paths', bound, 'run_folder', lambda bundle, output_dir, sealed: bundle),
    # S2c item 2, R7: a seal without the test manifest's hash.
    ('test_seal_carries_the_test_manifest_hash_or_says_exposed', sealer, 'test_seal',
     lambda exposure, test_manifest, test_archive, source: dict(exposure=exposure)),
    # S2c item 3: the bundle's withholding not read, so FACT_CHECKER's reasons vanish.
    ('test_report_states_every_11_12_field', analysis, 'withheld_agents', lambda bundle: []),
    # S2c item 8: a sealed run handled as exposed (phase names printed, the copy attached).
    ('test_sealed_run_writes_nothing_in_the_repository_but_ledger_lines_and_prints_counts_only', controller, 'admit',
     admit_as_exposed),
    # S2c item 9: the frozen tag no longer resolved.
    ('test_protected_test_guard_holds_for_sealed_runs_only', controller, 'frozen_commit',
     lambda tag: read(Path(controller.BASE) / 'execution_manifest.json')['source_commit']),
    # S2b item 1, S2c item 10: the sealed multi-round flag list forgotten.
    ('test_multi_round_is_admitted_when_declared_sealed_and_valid', runner, 'argv_for', lambda manifest: runner.ARGV),
    # S2b item 2: the multi-round schema rules not applied.
    ('test_live_case_manifest_is_accepted_and_the_fixture_and_malformed_are_refused', runner, '_multi_round_module',
     lambda: SimpleNamespace(validate_manifest=lambda value: value, InvalidState=ValueError)),
    # S2c item 11: arm-major order.
    ('test_batch_runs_b3_and_b1_item_by_item_and_a_stop_leaves_pairs', controller, 'batch_schedule', arm_major_schedule),
    # S2c item 13: named extras ignored.
    ('test_named_archive_extras_enter_the_source_archive_or_fail_in_one_line', sealer, 'archive_names',
     archive_names_ignoring_extras),
    # S2c item 14: a declaration accepted for any bundle.
    ('test_asset_copy_match_needs_this_bundles_own_declaration_and_the_upload_is_forecast', controller,
     'asset_copy_declaration', declaration_for_any_bundle),
    # R11: the ratification test skipped at sealing.
    ('test_unratified_inst_finder_off_refuses_to_seal', sealer, 'inst_finder_setting',
     lambda files, value: dict(refusal=None, setting=value or 'on')),
    # S2 checker round 1.
    ('test_ledger_closes_a_launch_by_id_or_name', instance_reaper, 'ledger_view', ledger_view_by_key_only),
    ('test_termination_record_from_either_writer_closes_the_ledger', controller, 'termination_epoch',
     lambda path: read(path)['epoch']),
    ('test_a_bundle_is_launched_once_with_or_without_an_output_folder', bound, 'consumed',
     lambda bundle: (Path(bundle) / 'LAUNCH_INTENT.json').exists()),
    ('test_one_launch_decision_at_a_time', guard, 'acquire_lock', lambda ledger: None),
    ('test_batch_reports_one_per_bundle_with_the_session_cost_and_copy', analysis, 'analyze', lambda bundle=None: None),
    ('test_case_documents_follow_the_pipelines_corpus_rules', runner, 'case_corpus_documents',
     lambda members, source: {Path(n).stem: d.decode('utf-8') for n, d in members.items()}),
    ('test_the_controller_never_writes_an_asset_copy_declaration', controller, 'asset_copy_declaration',
     declaration_written_when_absent),
    ('test_flipped_preparation_test_admits_a_declared_multi_round', runner, 'argv_for', lambda manifest: runner.ARGV),
    ('test_flipped_preparation_test_parses_the_sealed_multi_round_flags', runner, 'argv_for', lambda manifest: runner.ARGV),
    # Follow-up: the rehearsal manifest without the IV.3 budget fields (its pre-S2 shape).
    ('test_rehearsal_plan_and_manifest_launch_under_the_loop_guard', rehearsal, 'rehearsal_budget', lambda: {}),
    # Follow-up, R3: the general watchdog's deadlines from fixed caps instead of the passed ones.
    ('test_general_path_caps_are_passed_never_defaulted', cloud_run_watchdog, 'budget_deadlines',
     lambda rate, epoch, reserve_seconds=120, *, soft_usd, hard_usd:
         cloud_run_common.budget_deadlines(rate, epoch, reserve_seconds, soft_usd=5, hard_usd=10)),
    # S2c item 7: the controller started inside the parent instead of detached.
    ('test_detached_controller_survives_its_parent_and_the_reaper_ends_an_orphan', sys.modules[__name__], 'parent_spawner',
     lambda: 'inline'),
    # D-S9: the budget and hard stop held at the old code figures instead of the ledger's.
    ('test_budget_and_hard_stop_are_read_from_the_latest_ledger_line', instance_reaper, 'budget_figures',
     lambda rows: (50.0, 49.0)),
    # S2 checker round 2, one mechanism per proof.
    # Item 1: every member's line endings converted, binary ones included.
    ('test_binary_workload_members_keep_their_bytes_and_reach_the_case_validation', sealer, 'text_member',
     lambda name: True),
    # Item 2: a batch entry consumed only by LAUNCH_INTENT.json.
    ('test_a_batch_entry_launched_in_a_run_folder_is_consumed', controller, 'consumed',
     lambda bundle: (Path(bundle) / 'LAUNCH_INTENT.json').exists()),
    # Item 3: the recorded deadline not read, so accrual never stops and nothing is closed.
    ('test_an_intent_without_an_instance_stops_accruing_and_the_reaper_closes_it', instance_reaper, 'recorded_deadline',
     lambda rec: None),
    # Item 4: the cap's ceiling from the budget less the margin, whatever hard stop the line names.
    ('test_the_cap_ceiling_is_the_ledgers_hard_stop', instance_reaper, 'budget_figures', budget_figures_without_the_hard_stop),
    # Item 5: a budget line read as readable whatever it holds.
    ('test_the_guard_refuses_a_budget_line_it_cannot_read', instance_reaper, 'budget_figures', lambda rows: (50.0, 49.0)),
    # Item 6: a held lock reported without its age, pid or the pid's state.
    ('test_a_held_lock_is_reported_with_its_age_and_its_pid', guard, 'lock_holder', lambda lock, now_epoch=None: 'holder unreadable'),
    # Item 7: no refusal of a sealed bundle inside the repository.
    ('test_a_sealed_bundle_inside_the_repository_is_refused_before_any_write', bound, 'refuse_sealed_bundle_in_repository',
     lambda bundle: None),
    # Item 8: any revision admitted as the frozen tag.
    ('test_the_frozen_tag_resolves_only_a_tag', controller, 'frozen_commit', frozen_commit_of_any_revision),
    # Item 10: the purpose not checked until the ledger line.
    ('test_a_prose_purpose_is_refused_before_any_provider_call', guard, 'require_purpose', lambda purpose: purpose),
    # Item 11: the A10 price from the opening line only.
    ('test_the_a10_reference_price_is_the_latest_recorded_on_any_budget_line', guard, 'a10_reference_rate',
     a10_rate_from_the_opening_line),
]


if __name__ == '__main__':
    modes = {'--detach-parent': detach_parent, '--detached-child': detached_child, '--detached-child-hang': detached_child_hang}
    if len(sys.argv) == 3 and sys.argv[1] in modes:
        modes[sys.argv[1]](Path(sys.argv[2]))
    else:
        unittest.main(verbosity=2)
