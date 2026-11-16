"""The auxiliary environment (#217, D-601) proven on the controller checks' fakes, no provider, no network.

A sealed `aux_env` block makes the controller run three phases after the run's own wheels: every
wheel of the sealed lock fetched onto the instance and held to its sha256 by pip, a second venv, and
an offline install from that folder held to the same hashes. A sealed run, or a lock the seal does
not carry under the digest the block names, is refused; a manifest without the block runs no such
phase. Each rule is proven by neutralise, fail, restore, pass through AUX_NEUTRALIZATIONS.
The tests live in AuxEnvChecks, mixed into ordinary_final_controller_checks.ControllerChecks.
"""
import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / 'tools'), str(ROOT / 'scripts')):
    if _path not in sys.path:
        sys.path.insert(0, _path)
import ordinary_final_cloud as controller  # noqa: E402
from ordinary_final_run import read  # noqa: E402

AUX_LOCK = b'pkg==1.0 \\\n    --hash=sha256:' + b'a' * 64 + b'\n'
AUX_PHASES = ('aux_env_fetch', 'aux_env_create', 'aux_env_install')


def phase_script(transport, label):
    """The command a started phase ran, decoded as the instance receives it."""
    for argv, _ in transport.calls:
        command = argv[-1]
        if 'setsid nohup' in command and '/%s.pid' % label in command:
            found = re.search(r"printf %s '?([A-Za-z0-9+/=]+)'?", command)
            return base64.b64decode(found.group(1)).decode() if found else command
    return None


def hanging_collects(hangs):
    """A FakeTransport whose output collect of each named phase hangs that many times (D-619)."""
    from ordinary_final_controller_checks import FakeTransport

    class Hanging(FakeTransport):
        def run(self, argv, capture_output=True, timeout=None, creationflags=None):
            command = argv[-1] if argv and argv[0] == 'ssh' else ''
            if controller.PHASE_OUTPUT_CAPPED in command and '.out' in command:
                label = re.search(r'/([A-Za-z0-9_]+)\.out', command).group(1)
                if hangs.get(label, 0) > 0:
                    hangs[label] -= 1
                    self.calls.append((list(argv), timeout))
                    raise subprocess.TimeoutExpired(argv, timeout)
            return super().run(argv, capture_output, timeout, creationflags)
    return Hanging


def collects(transport, label):
    """The output collects the controller made of one phase (its capped read of the phase's .out)."""
    return sum(1 for argv, _ in transport.calls
               if argv and argv[0] == 'ssh' and controller.PHASE_OUTPUT_CAPPED in argv[-1] and label + '.out' in argv[-1])


class AuxEnvChecks:
    def test_a_batch_keeps_venv_aux_and_its_wheels_between_entries(self):
        """D-630: park_command, run in a real shell on a stand-in run root, moves an entry's files aside
        and keeps the shared environment, venv_aux and wheels_aux among it."""
        import shutil
        import tempfile
        bash = shutil.which('bash')
        if bash is None:
            self.skipTest('no bash')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'run'
            for name in ('hf_cache', 'wheels', 'venv', 'venv_aux', 'wheels_aux', 'project', 'evidence'):
                (root / name).mkdir(parents=True)
            for name in ('assets.tar', 'execution_manifest.json'):
                (root / name).write_text('x')
            done = subprocess.run([bash, '-c', controller.park_command(root.as_posix(), 0)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ['assets.tar', 'hf_cache', 'project', 'venv', 'venv_aux', 'wheels', 'wheels_aux'])
            self.assertEqual(sorted(p.name for p in (Path(d) / 'run-batch' / '0').iterdir()),
                             ['evidence', 'execution_manifest.json', 'project'])

    def execute_hanging(self, hangs, polls=None):
        from ordinary_final_controller_checks import EVIDENCE, FakeProvider, fixture_plan, run_controller
        outputs = {'evidence_hash': (hashlib.sha256(EVIDENCE).hexdigest() + '  collected_evidence.tar.gz' + chr(10)).encode()}
        transport = hanging_collects(dict(hangs))(self.base, polls, outputs)
        transport, console, ran = run_controller(self.root, self.base, fixture_plan(self.ledger), transport, FakeProvider,
                                                 self.clock, self.credential)
        failure = ran / 'controller_failure.json'
        return transport, (json.loads(failure.read_text()) if failure.exists() else None)

    def test_d619_a_completed_phase_whose_collect_hangs_every_time_is_recorded_and_the_run_goes_on(self):
        """aux_env_install completed with exit 0, then its collect hangs on every attempt: recorded, not a stop."""
        self.seal_aux()
        transport, failure = self.execute_hanging({'aux_env_install': controller.COLLECT_ATTEMPTS})
        self.assertIsNone(failure, failure)
        timing = json.loads((self.base / 'aux_env_install_timing.json').read_text())
        self.assertEqual((timing['output_collect_timed_out'], timing['exit_code'], timing['collect_attempts']),
                         (True, 0, controller.COLLECT_ATTEMPTS))
        self.assertIn('ordinary_workload', transport.started)
        self.assert_torn_down()

    def test_d619_a_collect_that_hangs_once_is_retried(self):
        self.seal_aux()
        transport, failure = self.execute_hanging({'aux_env_fetch': 1})
        self.assertIsNone(failure, failure)
        timing = json.loads((self.base / 'aux_env_fetch_timing.json').read_text())
        self.assertEqual(timing['collect_attempts'], 2)
        self.assertNotIn('output_collect_timed_out', timing)

    def test_d619_a_nonzero_phase_whose_collect_hangs_stops_as_before(self):
        """Exit code 1, then a hanging collect: one attempt, the old stop."""
        self.seal_aux()
        transport, failure = self.execute_hanging({'aux_env_fetch': controller.COLLECT_ATTEMPTS}, polls={'aux_env_fetch': [1]})
        self.assertEqual(failure['message'], controller.TRANSPORT_DEADLINE)
        self.assertEqual(collects(transport, 'aux_env_fetch'), 1)
        self.assertNotIn('ordinary_workload', transport.started)

    def test_d619_a_final_pack_evidence_collect_that_hangs_still_yields_the_evidence(self):
        """pack_evidence's output only feeds the disk record: its hang on every attempt is recorded and the
        evidence is still hashed, downloaded and verified."""
        transport, failure = self.execute_hanging({'pack_evidence': controller.COLLECT_ATTEMPTS})
        self.assertIsNone(failure, failure)
        self.assertEqual(collects(transport, 'pack_evidence'), controller.COLLECT_ATTEMPTS)
        self.assertTrue((self.base / 'collection_integrity.json').exists())
        timing = json.loads((self.base / 'pack_evidence_timing.json').read_text())
        self.assertTrue(timing['output_collect_timed_out'])

    def test_d619_no_retry_once_a_salvage_request_is_seen(self):
        """Under a salvage request a hanging collect is tried once, so the salvage answer keeps its time."""
        calls = []

        def hang():
            calls.append(1)
            raise RuntimeError(controller.TRANSPORT_DEADLINE)
        result, attempts, timed_out = controller.collect_completed(
            hang, dict(remote_work='completed', exit_code=0), 'aux_env_install', True)
        self.assertEqual((len(calls), attempts, timed_out), (1, 1, True))
        calls.clear()
        controller.collect_completed(hang, dict(remote_work='completed', exit_code=0), 'aux_env_install', False)
        self.assertEqual(len(calls), controller.COLLECT_ATTEMPTS)

    def test_d619_the_controller_passes_the_salvage_state_to_the_collect(self):
        """The call site hands collect_completed whether a salvage request is set (salvage['epoch'])."""
        import inspect
        source = inspect.getsource(controller.execute)
        self.assertIn("status,label,salvage_pending(salvage,name))", source)

    def test_d619_a_request_that_arrives_during_pack_evidence_stops_its_retries(self):
        """salvage_stop never reads for the exempt final collection, so the request is read at the collect:
        a request appearing during pack_evidence leaves its hanging collect one attempt."""
        from unittest.mock import patch
        holder = {}
        original = controller.salvage_requested

        def requested(name):
            transport = holder.get('transport')
            if transport is not None and 'pack_evidence' in transport.started:
                return dict(episode='fixture', time_utc='2026-11-14T00:00:00Z')
            return original(name)
        from ordinary_final_controller_checks import EVIDENCE, FakeProvider, fixture_plan, run_controller
        outputs = {'evidence_hash': (hashlib.sha256(EVIDENCE).hexdigest() + '  collected_evidence.tar.gz' + chr(10)).encode()}
        transport = hanging_collects({'pack_evidence': controller.COLLECT_ATTEMPTS})(self.base, None, outputs)
        holder['transport'] = transport
        with patch.object(controller, 'salvage_requested', requested):
            run_controller(self.root, self.base, fixture_plan(self.ledger), transport, FakeProvider, self.clock, self.credential)
        self.assertEqual(collects(transport, 'pack_evidence'), 1)

    def test_d619_a_phase_whose_output_is_read_still_stops(self):
        """evidence_hash's output is the digest the controller checks: retried, then the evidence collection
        stops as before (no archive downloaded, never an empty digest taken)."""
        transport, failure = self.execute_hanging({'evidence_hash': controller.COLLECT_ATTEMPTS})
        self.assertEqual(collects(transport, 'evidence_hash'), controller.COLLECT_ATTEMPTS)
        self.assertFalse((self.base / 'collection_integrity.json').exists())
        self.assertFalse((self.base / 'evidence_hash_timing.json').exists())

    def seal_aux(self, digest=None):
        (self.base / 'aux_env.lock').write_bytes(AUX_LOCK)
        manifest = read(self.base / 'execution_manifest.json')
        support = dict(manifest['support_files'], **{'aux_env.lock': hashlib.sha256(AUX_LOCK).hexdigest()})
        self.remanifest(support_files=support, aux_env=dict(lock='aux_env.lock', purpose='vllm_replay',
                                                            lock_sha256=digest or support['aux_env.lock']))

    def test_aux_env_phases_run_from_the_sealed_lock_only(self):
        self.seal_aux()
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        started = transport.started
        self.assertEqual([p for p in started if p.startswith('aux_env_')], list(AUX_PHASES))
        self.assertLess(started.index('install_pinned_wheels'), started.index('aux_env_fetch'))
        fetch, install = phase_script(transport, 'aux_env_fetch'), phase_script(transport, 'aux_env_install')
        for script in (fetch, install):
            self.assertIn('--require-hashes', script)
            self.assertIn('--no-deps', script)
            self.assertIn('-r aux_env.lock', script)
        self.assertIn('--only-binary=:all:', fetch)
        self.assertIn('--no-index', install)
        self.assertIn('venv_aux/bin/python', install)
        self.assert_torn_down()

    def test_an_aux_env_is_refused_on_a_sealed_run_or_another_lock(self):
        manifest = dict(support_files={'aux_env.lock': 'f' * 64},
                        aux_env=dict(lock='aux_env.lock', lock_sha256='f' * 64))
        self.assertTrue(controller.aux_env_admitted(manifest, False))
        self.assertFalse(controller.aux_env_admitted(manifest, True))
        self.assertFalse(controller.aux_env_admitted(dict(manifest, aux_env=dict(lock='aux_env.lock', lock_sha256='0' * 64)), False))
        self.assertFalse(controller.aux_env_admitted(dict(manifest, support_files={}), False))

    def test_an_aux_env_whose_digest_is_not_the_sealed_lock_stops_before_any_provider_call(self):
        """Refused before the first provider call: no instance, no key, no launch intent, no ssh."""
        from ordinary_final_controller_checks import FakeProvider
        self.seal_aux(digest='0' * 64)
        with self.assertRaisesRegex(RuntimeError, controller.AUX_REFUSAL):
            self.execute()
        self.assertEqual(FakeProvider.state, None)  # refused before any provider action
        self.assertFalse((self.base / 'LAUNCH_INTENT.json').exists())
        self.assertFalse((self.base / 'RUN_FOLDER.json').exists())

    def test_no_aux_env_runs_no_aux_phase(self):
        """A manifest with no block: no auxiliary refusal and no auxiliary phase, as before #217."""
        try:
            transport, console, failure = self.execute()
            refused = None
        except RuntimeError as exc:
            transport, failure, refused = None, None, str(exc)
        self.assertIsNone(refused, 'a manifest with no auxiliary block was treated as having one')
        self.assertIsNone(failure, failure)
        self.assertFalse([p for p in transport.started if p.startswith('aux_env_')])


def commands_without(flag):
    def commands(aux, exe, remote_root):
        return [(label, command.replace(' ' + flag, ''), timeout)
                for label, command, timeout in ORIGINAL_COMMANDS(aux, exe, remote_root)]
    return commands


ORIGINAL_COMMANDS = controller.aux_env_commands

def collect_once(collect, status, label, salvaging=False):
    """The rule before D-619: one collect, its hang a stop."""
    return collect(), 1, False


def collect_any_code(collect, status, label, salvaging=False):
    """A rule that ignores the exit code: any completed phase retried and tolerated."""
    return ORIGINAL_COLLECT(collect, dict(status, exit_code=0), label, salvaging)


ORIGINAL_COLLECT = controller.collect_completed
ORIGINAL_OUTPUT_READ = controller.output_read

AUX_NEUTRALIZATIONS = [
    # D-630: a park that moves venv_aux away leaves the next entry's route without its server.
    ('test_a_batch_keeps_venv_aux_and_its_wheels_between_entries', controller, 'PARKED_KEEP',
     ('hf_cache', 'wheels', 'venv', 'assets.tar')),
    # D-619: a completed phase's hanging collect is retried, then recorded, not a stop.
    ('test_d619_a_completed_phase_whose_collect_hangs_every_time_is_recorded_and_the_run_goes_on', controller,
     'collect_completed', collect_once),
    ('test_d619_a_collect_that_hangs_once_is_retried', controller, 'collect_completed', collect_once),
    # Only an exit code of 0 earns the retry; a phase whose output is read still stops.
    ('test_d619_a_nonzero_phase_whose_collect_hangs_stops_as_before', controller, 'collect_completed', collect_any_code),
    ('test_d619_a_phase_whose_output_is_read_still_stops', controller, 'output_read', lambda label: False),
    # pack_evidence is not a parsed phase: listed again, its hang loses the evidence.
    ('test_d619_a_final_pack_evidence_collect_that_hangs_still_yields_the_evidence', controller, 'output_read',
     lambda label: label.endswith('pack_evidence') or ORIGINAL_OUTPUT_READ(label)),
    # A request first seen during the exempt final collection still skips the retries.
    ('test_d619_a_request_that_arrives_during_pack_evidence_stops_its_retries', controller, 'salvage_pending',
     lambda seen, name: seen.get('epoch') is not None),
    # A salvage request skips the retries.
    ('test_d619_no_retry_once_a_salvage_request_is_seen', controller, 'collect_completed',
     lambda collect, status, label, salvaging=False: ORIGINAL_COLLECT(collect, status, label, False)),
    # Every wheel is held to the lock's sha256, fetched and installed.
    ('test_aux_env_phases_run_from_the_sealed_lock_only', controller, 'aux_env_commands', commands_without('--require-hashes')),
    ('test_aux_env_phases_run_from_the_sealed_lock_only', controller, 'aux_env_commands', commands_without('--no-index')),
    ('test_aux_env_phases_run_from_the_sealed_lock_only', controller, 'aux_env_commands', commands_without('--only-binary=:all:')),
    ('test_aux_env_phases_run_from_the_sealed_lock_only', controller, 'aux_env_commands', commands_without('--no-deps')),
    # No block, no auxiliary phase.
    ('test_no_aux_env_runs_no_aux_phase', controller, 'aux_env_block',
     lambda manifest: dict(lock='aux_env.lock', lock_sha256='0' * 64)),
    # A sealed run, or a lock under another digest, never gets the environment.
    ('test_an_aux_env_is_refused_on_a_sealed_run_or_another_lock', controller, 'aux_env_admitted',
     lambda manifest, sealed: True),
    ('test_an_aux_env_whose_digest_is_not_the_sealed_lock_stops_before_any_provider_call', controller, 'aux_env_admitted',
     lambda manifest, sealed: True),
]
