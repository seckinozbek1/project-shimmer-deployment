"""Mocked controller checks: detached remote phases survive a dead client connection.

Every provider action, ssh, scp, ssh-keygen, the watchdog process and the clock are
replaced. The real controller execute() runs end to end against them, so the
phase sequence, the detached-phase polling, the failure teardown and the cleanup
are the controller's own code paths. No credential is read, no network is used,
no instance exists. Run v3 (2026-09-18) is the case under test: a phase whose
remote work completes while the connection carrying it dies must be recognised
as completed, never failed, and the workload must then run.
"""
import base64
import contextlib
import hashlib
import io
import json
import re
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
import ordinary_final_cloud as controller
from ordinary_final_run import write, sha

INSTANCE = 'a' * 32
KEY_ID = 'b' * 32
IMAGE = dict(id='9211995d-2377-4ea8-94d2-18eea01ec3f6', family='gpu-base-24-04', version='24.4.4-2141',
             architecture='x86_64', region='us-east-1')
EVIDENCE = b'collected evidence fixture'


class FakeClock:
    """time() advances only through sleep(); sleep refreshes the watchdog heartbeat like the live watchdog."""
    def __init__(self, base):
        self.now, self.base, self.slept = 1_000_000.0, base, 0.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(0.0, float(seconds))
        self.slept += max(0.0, float(seconds))
        armed = self.base / 'WATCHDOG_ARMED.json'
        if armed.exists():
            row = json.loads(armed.read_text(encoding='utf8'))
            row['heartbeat_epoch'] = self.now
            armed.write_text(json.dumps(row), encoding='utf8')


class FakeProvider:
    """Allowlisted provider surface with shared state across instances, as the live adapter behaves."""
    state = None

    def __init__(self, credential=None):
        if FakeProvider.state is None:
            FakeProvider.state = dict(instances=[], keys=[], launches=0, terminate_calls=0, status={})
        self.s = FakeProvider.state

    def request(self, endpoint, body=None, method=None):
        s = self.s
        if endpoint == 'instances':
            return {'data': [dict(instance_id=i, name=n) for i, n in s['instances']]}
        if endpoint == 'instance-types':
            return {'data': [dict(metadata=dict(type='gpu_1x_a10', gpu_type='A10 (24 GB PCIe)', gpu_count=1, cpu=30,
                                                ram_gib=200, storage_gib=1400, hourly_rate=1.29),
                                  architecture='x86_64', regions=['us-east-1', 'us-west-1'])]}
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
            s['instances'].append((INSTANCE, body['name']))
            s['status'][INSTANCE] = 'active'
            return {'data': dict(instance_ids=[INSTANCE])}
        raise AssertionError('unexpected provider endpoint ' + endpoint)

    def instance(self, instance_id):
        status = self.s['status'].get(instance_id, 'terminated')
        return dict(instance_id=instance_id, status=status, public_ip='10.0.0.2', hourly_rate=1.29,
                    name='fixture', type='gpu_1x_a10', region='us-east-1')

    def terminate(self, instance_id):
        self.s['terminate_calls'] += 1
        self.s['status'][instance_id] = 'terminated'
        self.s['instances'] = [x for x in self.s['instances'] if x[0] != instance_id]


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
                (self.base / 'collected_evidence.tar.gz').write_bytes(EVIDENCE)
                (self.base / 'remote_collection_manifest.json').write_text('{}', encoding='utf8')
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
        write(self.base / 'WATCHDOG_ARMED.json', dict(instance_id=INSTANCE, pid=777, heartbeat_epoch=controller.time.time(),
                                                      execution_manifest_sha256=sha(self.base / 'execution_manifest.json')))
        return SimpleNamespace(pid=777, poll=lambda: None)


class ControllerChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / 'bundle'
        self.base.mkdir()
        (self.base / 'project.tar.gz').write_bytes(b'project fixture')
        (self.root / 'assets.tar').write_bytes(b'assets fixture')
        write(self.base / 'execution_manifest.json', dict(source_commit='f' * 40, image=IMAGE, support_files={},
              local_control_hashes={}, source_archive_sha256=sha(self.base / 'project.tar.gz')))
        write(self.base / 'seal.json', dict(execution_manifest_sha256=sha(self.base / 'execution_manifest.json')))
        write(self.base / 'AUTHORIZED_LOCAL_REVERIFICATION.json', dict(passed=True))
        write(self.base / 'assets_transfer_archive.json', dict(path='assets.tar', sha256=sha(self.root / 'assets.tar'),
              manifest_sha256=sha(self.base / 'execution_manifest.json'), bytes=14))
        FakeProvider.state = None
        self.clock = FakeClock(self.base)

    def declare_copy(self, mount='/lambda/nfs/fixture'):
        write(self.base / 'asset_copy_declaration.json', dict(filesystem_name='fixture-fs', mount=mount, operator_authorized=True))

    def execute(self, polls=None, outputs=None, progress=None, existing=(), mount=None):
        """Run the real controller against the fakes; return (transport, console, failure or None)."""
        outputs = dict(outputs or {})
        outputs.setdefault('evidence_hash', (hashlib.sha256(EVIDENCE).hexdigest() + '  collected_evidence.tar.gz\n').encode())
        transport = FakeTransport(self.base, polls, outputs, progress, existing, mount)
        fake_subprocess = SimpleNamespace(run=transport.run, Popen=transport.popen, TimeoutExpired=subprocess.TimeoutExpired,
                                          CompletedProcess=subprocess.CompletedProcess, DEVNULL=subprocess.DEVNULL,
                                          DETACHED_PROCESS=8, CREATE_NEW_PROCESS_GROUP=512, CREATE_NO_WINDOW=0)
        console = io.StringIO()
        with patch.object(controller, 'ROOT', self.root), patch.object(controller, 'BASE', self.base), \
                patch.object(controller, 'MANIFEST', sha(self.base / 'execution_manifest.json')), \
                patch.object(controller, 'SEAL', sha(self.base / 'seal.json')), \
                patch.object(controller, 'LambdaExperiment', FakeProvider), \
                patch.object(controller, 'subprocess', fake_subprocess), \
                patch.object(controller, 'time', self.clock), \
                contextlib.redirect_stdout(console):
            controller.execute()
        failure = self.base / 'controller_failure.json'
        return transport, console.getvalue().splitlines(), (json.loads(failure.read_text()) if failure.exists() else None)

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


# (test, owner, attribute, mutant): the one mechanism each load-bearing test proves.
NEUTRALIZATIONS = [
    ('test_dead_connection_after_remote_completion_is_completed_and_the_run_proceeds', controller, 'poll_outcome', neutralized_poll_outcome),
    ('test_connection_loss_during_the_workload_keeps_polling_and_records_progress', controller, 'poll_outcome', neutralized_poll_outcome),
    ('test_fresh_directory_passes_because_the_launcher_creates_nothing_under_the_remote_root', controller, 'phases_dir', v4_phases_dir),
    # A probe that no longer hashes the copy: a corrupt copy would be used as the sealed archive.
    ('test_asset_copy_mismatch_is_refused_uploaded_and_never_overwritten', controller, 'asset_copy_probe_command',
     lambda mount, digest: 'echo MATCH'),
]


if __name__ == '__main__':
    unittest.main(verbosity=2)
