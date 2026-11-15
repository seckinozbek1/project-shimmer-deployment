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
import re
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


class AuxEnvChecks:
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

AUX_NEUTRALIZATIONS = [
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
