"""The ready-to-run image (D-S108, D-S109, form B) proven on fixtures, with no provider and no network.

The controller is run end to end against the controller checks' fakes, and every `image_*` phase it
starts is answered by running the REAL `tools/image_layers.py` on a local stand-in for the mount and
the run root: the check hashes real files, the build copies and verifies real files, the env build's
two commands and the bind's mounts are the only things faked (they need Linux and root). Each rule is
proven by neutralise, fail, restore, pass through IMAGE_NEUTRALIZATIONS.

The tests live in ImageChecks, mixed into ordinary_final_controller_checks.ControllerChecks.
"""
import base64
import json
import contextlib
import hashlib
import io
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / 'tools'), str(ROOT / 'scripts')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import image_layers  # noqa: E402
import ordinary_final_cloud as controller  # noqa: E402
from ordinary_final_run import read, sha, write  # noqa: E402
import prepare_ordinary_final_run as sealer  # noqa: E402

MOUNT = '/lambda/nfs/fixture'
REVISION = 'c' * 40
MODEL = 'models--org--fixture-model'
WHEEL = 'pkg-1.0-py3-none-any.whl'
MEMBER_BYTES = {
    'hf_cache/hub/' + MODEL + '/refs/main': REVISION.encode('ascii'),
    'hf_cache/hub/' + MODEL + '/snapshots/' + REVISION + '/config.json': b'{"fixture": true}\n',
    'hf_cache/hub/' + MODEL + '/snapshots/' + REVISION + '/model.safetensors': b'weights ' * 4096,
    'wheels/' + WHEEL: b'wheel fixture bytes',
}
MEMBERS = {name: dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)) for name, data in MEMBER_BYTES.items()}
LOCK = ('pkg==1.0 --hash=sha256:' + MEMBERS['wheels/' + WHEEL]['sha256'] + '\n').encode()


class FakeHost:
    """What the image tool's few external commands do on a real instance, recorded: the env build's
    venv and pip steps, the bind mounts with their read-only remount, findmnt, and the page cache."""
    def __init__(self):
        self.mounts, self.calls, self.umount_refused = {}, [], False

    def run(self, argv, capture_output=True, timeout=None):
        self.calls.append(list(map(str, argv)))
        done = lambda rc=0, out=b'': subprocess.CompletedProcess(argv, rc, out, b'')
        argv = [str(a) for a in argv]
        if argv[1:3] == ['-m', 'venv']:
            build = Path(argv[3])
            (build / 'bin').mkdir(parents=True)
            (build / 'bin/python').write_text('python stand-in\n', encoding='utf8')
            (build / 'pyvenv.cfg').write_text('home = /usr/bin\ncommand = /usr/bin/python3.12 -m venv ' + build.as_posix() + '\n',
                                              encoding='utf8')
            (build / 'lib/python3.12/site-packages/pip').mkdir(parents=True)
            (build / 'lib/python3.12/site-packages/pip/__init__.py').write_text('pip\n', encoding='utf8')
            (build / 'lib/python3.12/site-packages/pip/__pycache__').mkdir()
            # Bytecode carries a time: it must never reach a layer, or a rebuild would differ.
            (build / 'lib/python3.12/site-packages/pip/__pycache__/x.pyc').write_bytes(os.urandom(16))
            return done()
        if argv[1:3] == ['-m', 'pip']:
            assert '--no-compile' in argv and '--require-hashes' in argv and '--no-index' in argv, argv
            site = Path(argv[0]).parents[1] / 'lib/python3.12/site-packages'
            wheels = Path(argv[argv.index('--find-links') + 1])
            (site / 'pkg').mkdir(parents=True)
            (site / 'pkg/__init__.py').write_bytes((wheels / WHEEL).read_bytes())
            return done()
        if argv[:4] == ['sudo', '-n', 'mount', '--bind']:
            self.mounts[argv[5]] = dict(source=argv[4], ro=False)
            return done()
        if argv[:4] == ['sudo', '-n', 'mount', '-o']:
            self.mounts[argv[5]]['ro'] = argv[4] == 'remount,bind,ro'
            return done()
        if argv[:3] == ['sudo', '-n', 'umount']:
            if self.umount_refused or argv[3] not in self.mounts:
                return done(32)
            del self.mounts[argv[3]]
            return done()
        if argv == ['findmnt', '-rn', '-o', 'TARGET']:
            return done(0, ''.join(t + '\n' for t in ['/', *self.mounts]).encode())
        if argv[0] == 'findmnt':
            entry = self.mounts.get(argv[3])
            return done(0 if entry else 1, (b'ro,relatime\n' if entry and entry['ro'] else b'rw,relatime\n'))
        if argv[:2] == ['sudo', '-n']:
            return done()
        if argv[0] in ('docker', 'nvidia-ctk'):
            raise FileNotFoundError(argv[0])
        raise AssertionError('unexpected host command: ' + ' '.join(argv))

    def writable(self, target):
        entry = self.mounts.get(str(target))
        return not (entry and entry['ro'])


def built_env_manifest(spec_without_env, mount):
    """The env build record a first launch brings back, made here by the real build on the same mount
    (a venv records the path it was built at, so its bytes depend on the mount's path), then removed."""
    host = FakeHost()
    scratch = Path(mount) / '_scratch'
    wheels = scratch / 'wheels'
    wheels.mkdir(parents=True)
    (wheels / WHEEL).write_bytes(MEMBER_BYTES['wheels/' + WHEEL])
    (scratch / 'install.lock').write_bytes(LOCK)
    env = next(l for l in spec_without_env['layers'] if l['kind'] == 'env')
    try:
        record = image_layers.build_env(env, mount, wheels, scratch / 'install.lock', run=host.run)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(image_layers.layer_dir(mount, env), ignore_errors=True)
    return record['manifest']


def fixture_spec(mount, env_sealed=True):
    machine = controller_manifest_image()
    lock = hashlib.sha256(LOCK).hexdigest()
    spec = image_layers.spec(MEMBERS, lock, machine, '3.12.3')
    if env_sealed:
        spec = image_layers.spec(MEMBERS, lock, machine, '3.12.3', built_env_manifest(spec, mount))
    return spec


def controller_manifest_image():
    import ordinary_final_controller_checks as cc
    return cc.IMAGE['id']


def place_layers(mount, spec, kinds=('model', 'wheels', 'env')):
    """The filesystem as a verified earlier launch left it: each layer under its key."""
    for layer in spec['layers']:
        if layer['kind'] not in kinds:
            continue
        directory = image_layers.layer_dir(mount, layer)
        if layer['kind'] == 'env':
            host = FakeHost()
            wheels = Path(mount) / '_w'
            wheels.mkdir(parents=True, exist_ok=True)
            (wheels / WHEEL).write_bytes(MEMBER_BYTES['wheels/' + WHEEL])
            lock = Path(mount) / '_lock'
            lock.write_bytes(LOCK)
            # The same build path as the sealed record: a rebuild gives the same bytes.
            image_layers.build_env(layer, mount, wheels, lock, run=host.run)
            shutil.rmtree(wheels)
            lock.unlink()
            continue
        prefix = 'hf_cache/hub/' + layer['name'] + '/' if layer['kind'] == 'model' else 'wheels/'
        for relative in layer['files']:
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(MEMBER_BYTES[prefix + relative])


class ImageChecks:
    """Mixed into ControllerChecks: self.base, self.root, self.execute, self.declare_copy exist."""

    def image_bundle(self, env_sealed=True, measure=False):
        self.image_mount = self.root / 'image_mount'
        self.image_mount.mkdir()
        spec = fixture_spec(self.image_mount, env_sealed)
        spec['measure'] = measure
        spec_bytes = (json.dumps(spec, indent=2, sort_keys=True) + '\n').encode()
        (self.base / 'image_spec.json').write_bytes(spec_bytes)
        (self.base / 'image_layers.py').write_bytes((ROOT / 'tools/image_layers.py').read_bytes())
        (self.base / 'install.lock').write_bytes(LOCK)
        manifest = read(self.base / 'execution_manifest.json')
        support = dict(manifest['support_files'])
        support.update({n: sha(self.base / n) for n in ('image_spec.json', 'image_layers.py', 'install.lock')})
        block = dict(spec='image_spec.json', spec_sha256=hashlib.sha256(spec_bytes).hexdigest(), tool='image_layers.py',
                     python='3.12.3', measure=measure, env_sealed=env_sealed,
                     keys={l['name']: l['key'] for l in spec['layers']})
        self.remanifest(layers=block, support_files=support,
                        assets_archive=dict(manifest['assets_archive'], members=MEMBERS))
        self.declare_copy(mount=MOUNT)
        self.image_spec = spec
        self.image_remote = self.root / 'image_remote'
        self.image_remote.mkdir()
        self.host = FakeHost()
        return spec

    def image_tool(self, transport, label, command):
        """Run the phase's command with the real tool, the instance's paths mapped to the stand-ins."""
        encoded = re.search(r"printf %s '?([A-Za-z0-9+/=]+)'?", command).group(1)
        script = base64.b64decode(encoded).decode()
        argv = shlex.split(script.split('&&', 1)[1])
        assert argv[:3] == ['/usr/bin/python3.12', '-I', 'image_layers.py'], argv
        remote, local = controller.REMOTE, str(self.image_remote)
        args = [a.replace(remote, local).replace(MOUNT, str(self.image_mount)) for a in argv[3:]]
        for name in ('image_spec.json', 'image_layers.py', 'install.lock'):
            if not (self.image_remote / name).exists():
                shutil.copyfile(self.base / name, self.image_remote / name)
        if label in ('image_build', 'image_recheck', 'image_bind') and getattr(self, 'extracted', False):
            self.extract_assets_locally()
        out, cwd = io.StringIO(), os.getcwd()
        os.chdir(self.image_remote)
        try:
            with contextlib.redirect_stdout(out), patch.object(image_layers.subprocess, 'run', self.host.run), \
                    patch.object(image_layers, 'writable', self.host.writable):
                code = image_layers.main(args)
        except image_layers.LayerError:
            code = 3
        finally:
            os.chdir(cwd)
        lines = []
        for line in out.getvalue().splitlines():
            if line.startswith('IMAGE_RESULT '):
                # The stand-in paths read back as the instance's own, as the controller would see them.
                line = 'IMAGE_RESULT ' + json.dumps(self.instance_paths(json.loads(line[len('IMAGE_RESULT '):])))
            lines.append(line)
        transport.outputs[label] = ('\n'.join(lines) + '\n').encode()
        if code:
            transport.polls[label] = [code]

    def instance_paths(self, value):
        if isinstance(value, dict):
            return {k: self.instance_paths(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.instance_paths(v) for v in value]
        if isinstance(value, str):
            for local, remote in ((str(self.image_remote), controller.REMOTE), (str(self.image_mount), MOUNT)):
                if value.startswith(local):
                    return remote + value[len(local):].replace('\\', '/')
        return value

    def extract_assets_locally(self):
        """What extract_payload leaves on the instance after the asset path: the sealed members."""
        for name, data in MEMBER_BYTES.items():
            target = self.image_remote / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)

    def run_image(self, copy_files=True):
        digest = self.assets_digest()
        self.extracted = False
        original = self.image_tool

        def tool(transport, label, command):
            # The asset path ran before a build or a recheck when the probe or the upload ran.
            self.extracted = 'extract_payload' in transport.started and (
                transport.assets_uploaded or transport.assets_from_copy)
            original(transport, label, command)
        return self.execute(mount=dict(present=True, files={digest: digest} if copy_files else {}), image=tool)

    def image_receipt(self):
        return read(self.ran / 'image_receipt.json')

    def pack_run_root(self):
        """What the controller's final collect brings back: every .json file of the run root, as the
        evidence pack takes it (the fakes' archive is a placeholder)."""
        with tarfile.open(self.ran / 'collected_evidence.tar.gz', 'w:gz') as archive:
            for p in sorted(self.image_remote.iterdir()):
                if p.is_file() and p.suffix == '.json':
                    archive.add(p, arcname=p.name, recursive=False)

    # ---- the controller, end to end -----------------------------------------------------------

    def test_image_all_layers_match_start_from_the_image_with_nothing_fetched_or_installed(self):
        spec = self.image_bundle()
        place_layers(self.image_mount, spec)
        transport, console, failure = self.run_image()
        self.assertIsNone(failure, failure)
        receipt = self.image_receipt()
        self.assertEqual(receipt['first_check'], {l['name']: 'MATCH' for l in spec['layers']})
        self.assertFalse(receipt['assets_fetched'])
        self.assertEqual(receipt['env'], 'image')
        started = transport.started
        for absent in ('asset_copy_probe', 'asset_copy_use', 'create_environment', 'install_pinned_wheels', 'image_build'):
            self.assertNotIn(absent, started)
        self.assertFalse(transport.assets_uploaded)
        self.assertLess(started.index('image_check'), started.index('archive_integrity'))
        self.assertLess(started.index('image_bind'), started.index('dependency_closure'))
        self.assertIn('ordinary_workload', started)
        # Every layer bound, each listed read-only by the kernel before the workload.
        bound = {Path(t).relative_to(self.image_remote).as_posix(): e for t, e in self.host.mounts.items()}
        self.assertEqual(sorted(bound), sorted(['hf_cache/hub/' + MODEL, 'wheels', 'venv']))
        self.assertTrue(all(e['ro'] for e in bound.values()))
        self.assert_torn_down()

    def test_image_no_room_on_the_filesystem_refuses_the_build_never_the_run(self):
        self.image_bundle(env_sealed=False)
        lacking = lambda provider, name, needed: dict(enough=False, reason='lacks room', needed_bytes=needed)
        with patch.object(controller, 'asset_copy_room', lacking):
            transport, console, failure = self.run_image()
        self.assertIsNone(failure, failure)
        receipt = self.image_receipt()
        self.assertEqual(receipt['build_refused'], 'lacks room')
        self.assertNotIn('image_build', transport.started)
        self.assertEqual(list(self.image_mount.iterdir()), [])  # nothing written
        self.assertIn('install_pinned_wheels', transport.started)
        self.assert_torn_down()

    def test_image_the_laptop_plan_reads_the_receipts_and_hands_the_env_record_to_the_sealer(self):
        """M1 to M2: the first launch builds the env; its record, read back, seals it in the next bundle,
        whose plan then needs nothing built."""
        import image_layer_plan
        spec = self.image_bundle(env_sealed=False)
        record = self.root / 'image_layers.jsonl'
        before = image_layer_plan.plan(self.base, record)
        self.assertEqual({r['action'] for r in before['layers']}, {'built at the first launch that needs it'})
        transport, console, failure = self.run_image()
        self.assertIsNone(failure, failure)
        rows = image_layer_plan.record_run(self.ran, record, now=0)
        self.assertEqual(sorted((r['name'], r['state']) for r in rows),
                         [(MODEL, 'MATCH'), ('venv', 'UNSEALED'), ('wheels', 'MATCH')])
        out = self.root / 'env_manifest.json'
        self.pack_run_root()
        summary = image_layer_plan.env_manifest(self.ran, out)
        self.assertEqual(summary['key'], spec['layers'][-1]['key'])
        sealed = image_layers.spec(MEMBERS, hashlib.sha256(LOCK).hexdigest(), controller_manifest_image(), '3.12.3',
                                   read(out))
        # The env the first launch built, checked against the record it brought back: MATCH.
        self.assertEqual(image_layers.check(sealed, self.image_mount)['layers']['venv']['state'], 'MATCH')

    def test_image_the_tool_reports_measured_progress_the_reader_reads(self):
        """PROGRESS-A: the check writes done against total in bytes; the tracked reader reads it."""
        import ordinary_final_progress as progress
        mount = self.root / 'unit_mount'
        spec = fixture_spec(mount)
        place_layers(mount, spec)
        (self.root / 'cwd').mkdir()
        write(self.root / 'cwd' / 'spec.json', spec)
        cwd = os.getcwd()
        os.chdir(self.root / 'cwd')
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                image_layers.main(['check', '--spec', 'spec.json', '--mount', str(mount), '--out', 'out.json'])
        finally:
            os.chdir(cwd)
        self.assertIsNone(image_layers.PROGRESS)  # a check called as a function writes nothing
        record = read(self.root / 'cwd' / image_layers.PROGRESS_FILE)
        total = sum(e['bytes'] for l in spec['layers'] for e in l['files'].values())
        self.assertEqual((record['unit'], record['done'], record['total']), ('bytes', total, total))
        line = progress.reading_for(self.root, phase='image_check', elapsed=30,
                                    observations={'image_progress.json': json.dumps(record)})
        self.assertIn('of %.2f GB (100.0%%) measured' % (total / 1e9), line)

    def test_image_missing_layers_take_the_asset_path_then_build_and_check_again(self):
        spec = self.image_bundle(env_sealed=False)
        transport, console, failure = self.run_image()
        self.assertIsNone(failure, failure)
        receipt = self.image_receipt()
        self.assertEqual(set(receipt['first_check'].values()), {'MISSING'})
        self.assertTrue(receipt['assets_fetched'])
        started = transport.started
        self.assertLess(started.index('archive_integrity'), started.index('image_build'))
        self.assertLess(started.index('extract_payload'), started.index('image_build'))
        self.assertLess(started.index('image_build'), started.index('image_recheck'))
        self.assertEqual(receipt['recheck'], {MODEL: 'MATCH', 'wheels': 'MATCH', 'venv': 'UNSEALED'})
        # An unsealed env is never used: the run installs its own, and brings the build record back.
        self.assertEqual(receipt['env'], 'local')
        self.assertIn('install_pinned_wheels', started)
        import image_layer_plan
        built = read(self.ran / 'image_build.json')['result']
        # The controller holds the tool's summary; the full record comes back in the collected evidence.
        self.assertFalse(any('manifest' in r for r in built['records']))
        self.pack_run_root()
        record = image_layer_plan.full_build_record(self.ran, built)['records']
        env = next(r for r in record if r['name'] == 'venv')
        self.assertEqual(env['manifest']['key'], spec['layers'][-1]['key'])
        self.assertEqual(next(r for r in built['records'] if r['name'] == 'venv')['manifest_sha256'],
                         hashlib.sha256(image_layers.canonical(env['manifest'])).hexdigest())
        self.assertFalse(any(name.endswith('.pyc') or '__pycache__' in name for name in env['manifest']['files']))
        # The layers built are exactly the sealed bytes.
        for layer in spec['layers'][:-1]:
            self.assertEqual(image_layers.check(dict(spec, layers=[layer]), self.image_mount)['layers'][layer['name']]['state'], 'MATCH')
        self.assert_torn_down()

    def test_image_a_built_env_rebuilt_from_the_same_wheels_matches_its_sealed_record(self):
        spec = self.image_bundle(env_sealed=True)
        place_layers(self.image_mount, spec, kinds=('model', 'wheels'))
        transport, console, failure = self.run_image()
        self.assertIsNone(failure, failure)
        receipt = self.image_receipt()
        self.assertEqual(receipt['first_check']['venv'], 'MISSING')
        self.assertFalse(receipt['assets_fetched'])  # the env builds from the wheels layer, nothing fetched
        self.assertEqual(receipt['recheck']['venv'], 'MATCH')
        self.assertEqual(receipt['env'], 'image')
        self.assertNotIn('install_pinned_wheels', transport.started)
        self.assert_torn_down()

    def test_image_a_changed_byte_is_mismatch_never_replaced_and_the_assets_are_fetched(self):
        spec = self.image_bundle()
        place_layers(self.image_mount, spec)
        model = next(l for l in spec['layers'] if l['kind'] == 'model')
        weights = image_layers.layer_dir(self.image_mount, model) / 'snapshots' / REVISION / 'model.safetensors'
        corrupt = b'weightS' + MEMBER_BYTES['hf_cache/hub/' + MODEL + '/snapshots/' + REVISION + '/model.safetensors'][7:]
        weights.write_bytes(corrupt)
        transport, console, failure = self.run_image()
        self.assertIsNone(failure, failure)
        receipt = self.image_receipt()
        self.assertEqual(receipt['first_check'][MODEL], 'MISMATCH')
        self.assertTrue(receipt['assets_fetched'])
        self.assertTrue(transport.assets_from_copy or transport.assets_uploaded)
        self.assertNotIn('image_build', transport.started)
        self.assertEqual(weights.read_bytes(), corrupt)  # left for the operator
        self.assertNotIn(str(self.image_remote / 'hf_cache/hub' / MODEL), self.host.mounts)
        self.assertEqual(receipt['env'], 'image')  # the env still matched and is used
        self.assert_torn_down()

    def test_image_an_unreachable_mount_takes_the_asset_path_and_writes_nothing(self):
        self.image_bundle()
        shutil.rmtree(self.image_mount)
        transport, console, failure = self.run_image()
        self.assertIsNone(failure, failure)
        receipt = self.image_receipt()
        self.assertEqual(set(receipt['first_check'].values()), {'UNREACHABLE'})
        self.assertTrue(receipt['assets_fetched'])
        self.assertNotIn('image_build', transport.started)
        self.assertNotIn('image_bind', transport.started)
        self.assertFalse(self.image_mount.exists())
        self.assertIn('install_pinned_wheels', transport.started)
        self.assert_torn_down()

    def test_image_a_failed_bind_falls_back_to_the_asset_path(self):
        spec = self.image_bundle()
        place_layers(self.image_mount, spec)
        real = self.host.run

        def refusing(argv, **kwargs):
            if [str(a) for a in argv][:4] == ['sudo', '-n', 'mount', '-o']:
                return subprocess.CompletedProcess(argv, 32, b'', b'')
            return real(argv, **kwargs)
        self.host.run = refusing
        transport, console, failure = self.run_image()
        self.assertIsNone(failure, failure)
        receipt = self.image_receipt()
        self.assertTrue(receipt.get('bind_failed'))
        self.assertTrue(receipt['assets_fetched'])
        self.assertEqual(receipt['env'], 'local')
        self.assertIn('install_pinned_wheels', transport.started)
        # Nothing is left mounted, the failing target's own read-write bind included, and the
        # controller read the table again before the asset path ran.
        self.assertEqual(self.host.mounts, {})
        self.assertEqual(receipt['release']['left'], [])
        self.assertEqual(receipt['release']['record'], 'image_release.json')
        started = transport.started
        self.assertLess(started.index('image_release'), started.index('asset_copy_probe'))
        self.assert_torn_down()

    def test_image_a_refused_bind_unmounts_what_it_mounted(self):
        """bind() refuses only after unmounting every bind it made, its own partial bind included."""
        host = FakeHost()
        real = host.run
        sources = [self.root / 'unit_layer_a', self.root / 'unit_layer_b']
        targets = [self.root / 'unit_target_a', self.root / 'unit_target_b']
        for source in sources:
            source.mkdir()

        def refuse_second_remount(argv, **kwargs):
            argv = [str(a) for a in argv]
            if argv[:4] == ['sudo', '-n', 'mount', '-o'] and argv[5] == str(targets[1]):
                return subprocess.CompletedProcess(argv, 32, b'', b'')
            return real(argv, **kwargs)
        with patch.object(image_layers, 'writable', host.writable):
            with self.assertRaises(image_layers.LayerError):
                image_layers.bind(list(zip(sources, targets)), run=refuse_second_remount)
        self.assertEqual(host.mounts, {})
        self.assertEqual(image_layers.release(self.root, run=host.run), {'left': []})

    def test_image_a_bind_left_mounted_refuses_the_run(self):
        """A bind the tool cannot undo: the controller reads the table again and refuses the run, so no
        fetch or install writes through a read-write bind into a shared layer."""
        spec = self.image_bundle()
        place_layers(self.image_mount, spec)
        real = self.host.run
        self.host.umount_refused = True

        def refusing(argv, **kwargs):
            if [str(a) for a in argv][:4] == ['sudo', '-n', 'mount', '-o']:
                return subprocess.CompletedProcess(argv, 32, b'', b'')
            return real(argv, **kwargs)
        self.host.run = refusing
        transport, console, failure = self.run_image()
        self.assertEqual(failure['message'], 'Image layers are left mounted under the run root')
        self.assertTrue(self.image_receipt()['release']['left'])
        for absent in ('asset_copy_probe', 'asset_copy_use', 'create_environment', 'install_pinned_wheels',
                       'ordinary_workload'):
            self.assertNotIn(absent, transport.started)
        self.assertFalse(transport.assets_uploaded)
        self.assert_torn_down()

    def image_overrun(self, label, env_sealed=True, kinds=('model', 'wheels', 'env'), stopped=True, refused=None):
        """Run with `label` past its deadline. The stop phase answers after two RUNNING polls, with the
        stopped marker when `stopped`; the polls seen when image_release starts are kept."""
        spec = self.image_bundle(env_sealed=env_sealed)
        place_layers(self.image_mount, spec, kinds=kinds)
        original = self.image_tool
        stop = 'stop_image_phase_' + label
        self.polled_at_release = None

        def tool(transport, phase, command):
            if phase == 'image_release':
                self.polled_at_release = list(transport.polled)
            original(transport, phase, command)
            if phase == label:
                transport.polls[phase] = ['RUNNING'] * 100000
                transport.polls[stop] = ['RUNNING', 'RUNNING', 0]
                transport.outputs[stop] = ((controller.IMAGE_STOPPED_MARKER + '\n') if stopped else '').encode()
        self.image_tool = tool
        transport, console, failure = self.run_image()
        receipt = self.image_receipt()
        self.assertEqual(receipt['timed_out'], [label])
        self.assertIn(stop, transport.started)
        self.assertEqual(receipt['stopped'], {label: stopped})
        if refused is not None:
            self.assertEqual((failure or {}).get('message'), refused)
            self.assert_torn_down()
            return spec, transport, receipt
        self.assertIsNone(failure, failure)
        self.assertTrue(receipt['assets_fetched'] or label == 'image_build')
        self.assertIn('ordinary_workload', transport.started)
        self.assert_torn_down()
        return spec, transport, receipt

    def test_image_a_check_past_its_deadline_is_unreachable_and_takes_the_asset_path(self):
        spec, transport, receipt = self.image_overrun('image_check')
        self.assertEqual(set(receipt['first_check'].values()), {'UNREACHABLE'})
        for absent in ('image_build', 'image_bind'):
            self.assertNotIn(absent, transport.started)
        self.assertIn('install_pinned_wheels', transport.started)

    def test_image_a_build_past_its_deadline_is_not_built_and_nothing_is_checked_again(self):
        spec, transport, receipt = self.image_overrun('image_build', kinds=('model', 'wheels'))
        self.assertEqual(receipt['built'], [dict(name='venv', built=False, reason='phase deadline exceeded')])
        self.assertIsNone(receipt['recheck'])
        self.assertNotIn('image_recheck', transport.started)
        self.assertEqual(receipt['env'], 'local')
        self.assertIn('install_pinned_wheels', transport.started)

    def test_image_a_bind_past_its_deadline_is_released_and_takes_the_asset_path(self):
        spec, transport, receipt = self.image_overrun('image_bind')
        self.assertTrue(receipt['bind_failed'])
        self.assertEqual(self.host.mounts, {})
        self.assertEqual(receipt['env'], 'local')
        self.assertIn('install_pinned_wheels', transport.started)
        # The release started only after the stop's last poll said it ended, its group gone.
        self.assertIsNotNone(self.polled_at_release)
        self.assertIn(('stop_image_phase_image_bind', 0), self.polled_at_release)

    def test_image_an_overrun_bind_not_confirmed_stopped_refuses_the_run(self):
        """A bind process the stop could not confirm gone might still mount after the table is read:
        nothing is released, nothing fetched, the run refused."""
        spec, transport, receipt = self.image_overrun('image_bind', stopped=False,
                                                      refused='The overrun image bind could not be stopped')
        for absent in ('image_release', 'asset_copy_probe', 'install_pinned_wheels', 'ordinary_workload'):
            self.assertNotIn(absent, transport.started)

    def test_image_a_recheck_past_its_deadline_fetches_the_assets_and_loses_no_match(self):
        """A recheck that answered nothing reads UNREACHABLE: the assets are fetched and nothing is
        bound, but no MATCH is said to be lost."""
        spec, transport, receipt = self.image_overrun('image_recheck', kinds=('model', 'wheels'))
        self.assertEqual(set(receipt['recheck'].values()), {'UNREACHABLE'})
        self.assertTrue(receipt['assets_fetched'])
        self.assertFalse(receipt['match_lost_on_recheck'])
        self.assertNotIn('image_bind', transport.started)
        self.assertEqual(receipt['env'], 'local')
        self.assertIn('install_pinned_wheels', transport.started)

    def test_image_a_match_lost_on_recheck_fetches_the_assets(self):
        """need_assets follows the recheck: a model the first check read MATCH and the recheck does not
        is fetched by the asset path, never bound."""
        spec = self.image_bundle(env_sealed=True)
        place_layers(self.image_mount, spec, kinds=('model', 'wheels'))
        model = next(l for l in spec['layers'] if l['kind'] == 'model')
        weights = image_layers.layer_dir(self.image_mount, model) / 'snapshots' / REVISION / 'model.safetensors'
        original = self.image_tool

        def tool(transport, phase, command):
            if phase == 'image_recheck':
                weights.write_bytes(b'W' + weights.read_bytes()[1:])
            original(transport, phase, command)
        self.image_tool = tool
        transport, console, failure = self.run_image()
        self.assertIsNone(failure, failure)
        receipt = self.image_receipt()
        self.assertEqual(receipt['first_check'][MODEL], 'MATCH')
        self.assertEqual(receipt['recheck'][MODEL], 'MISMATCH')
        self.assertTrue(receipt['assets_fetched'] and receipt['match_lost_on_recheck'])
        started = transport.started
        self.assertLess(started.index('image_recheck'), started.index('asset_copy_probe'))
        self.assertTrue(transport.assets_from_copy or transport.assets_uploaded)
        bound = sorted(Path(t).relative_to(self.image_remote).as_posix() for t in self.host.mounts)
        self.assertEqual(bound, ['venv'])
        self.assertEqual(receipt['env'], 'image')
        self.assert_torn_down()

    def test_image_without_layers_no_image_phase_runs(self):
        self.declare_copy()
        transport, console, failure = self.execute(mount=dict(present=True, files={self.assets_digest(): self.assets_digest()}))
        self.assertIsNone(failure, failure)
        self.assertEqual([s for s in transport.started if s.startswith('image_')], [])
        self.assertEqual(read(self.ran / 'image_receipt.json')['used'], False)
        self.assertIn('asset_copy_probe', transport.started)
        self.assertIn('install_pinned_wheels', transport.started)

    def test_image_measure_runs_only_when_sealed(self):
        spec = self.image_bundle(measure=True)
        self.remanifest(layers=dict(read(self.base / 'execution_manifest.json')['layers'], measure=True))
        place_layers(self.image_mount, spec)
        transport, console, failure = self.run_image()
        self.assertIsNone(failure, failure)
        self.assertIn('image_measure', transport.started)
        rows = read(self.ran / 'image_measure.json')['result']['rows']
        self.assertEqual(sorted({(r['set'], r['readers']) for r in rows}),
                         sorted((s, n) for s in ('env', 'models_and_env') for n in (1, 4, 8, 16)))
        self.assertTrue(all(r['caches_dropped'] for r in rows))
        self.assertFalse(read(self.ran / 'image_measure.json')['result']['docker']['measured'])

    # ---- what the controller reads back (M1, 11 November 2026) ---------------------------------

    def test_image_a_build_record_of_megabytes_prints_a_summary_under_the_cap(self):
        """M1's image_build printed its whole record (5,425,078 bytes, every file of every layer) and
        the controller's collect hung on it. The tool prints a summary under its cap; the controller
        reads every state and record it acts on from that summary; the full record, brought back in the
        collected evidence, is accepted only at the digest the summary names."""
        import image_layer_plan
        work = self.root / 'big_build'
        work.mkdir()
        mount = self.root / 'big_mount'
        spec = fixture_spec(mount, env_sealed=False)
        env_key = spec['layers'][-1]['key']
        files = {'lib/python3.12/site-packages/package_%05d/module_%05d.py' % (i, i): dict(sha256='%064x' % i, bytes=i)
                 for i in range(40000)}
        manifest = dict(key=env_key, files=files, symlinks={'bin/python3': '/usr/bin/python3.12'})
        records = [dict(name=MODEL, built=True, reason=None, seconds=1.5),
                   dict(name='wheels', built=True, reason=None, seconds=0.5),
                   dict(name='venv', built=True, reason=None, seconds=300.0, manifest=manifest,
                        manifest_sha256=hashlib.sha256(image_layers.canonical(manifest)).hexdigest())]
        write(work / 'spec.json', spec)
        write(work / 'image_check.json', dict(layers={l['name']: dict(state='MISSING') for l in spec['layers']}))
        out, cwd = io.StringIO(), os.getcwd()
        os.chdir(work)
        try:
            with contextlib.redirect_stdout(out), patch.object(image_layers, 'build', lambda *a, **k: records):
                code = image_layers.main(['build', '--spec', 'spec.json', '--mount', str(mount), '--out', 'image_build.json',
                                          '--states', 'image_check.json', '--wheels', str(work), '--lock', 'install.lock',
                                          '--hub', str(work)])
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0)
        printed = out.getvalue().encode('utf8')
        self.assertGreater((work / 'image_build.json').stat().st_size, 4_000_000)
        self.assertLess(len(printed), image_layers.SUMMARY_CAP_BYTES + 64)
        self.assertLess(len(printed), controller.PHASE_COLLECT_CAP_BYTES)
        result = controller.image_result(printed)
        self.assertIsNotNone(result)
        self.assertNotIn('summary_capped', result)
        self.assertEqual([r['name'] for r in result['records']], [MODEL, 'wheels', 'venv'])
        self.assertFalse(any('manifest' in r for r in result['records']))
        venv = result['records'][-1]
        self.assertEqual((venv['built'], venv['files'], venv['symlinks'], venv['manifest_key']), (True, 40000, 1, env_key))
        self.assertEqual(venv['manifest_sha256'], records[-1]['manifest_sha256'])
        self.assertEqual(result['record_sha256'], hashlib.sha256((work / 'image_build.json').read_bytes()).hexdigest())
        # The laptop: the summary the controller saved, the full record from the collected evidence.
        run = self.root / 'big_run'
        run.mkdir()
        write(run / 'image_build.json', dict(returncode=0, result=result))
        with tarfile.open(run / 'collected_evidence.tar.gz', 'w:gz') as archive:
            archive.add(work / 'image_build.json', arcname='image_build.json', recursive=False)
        got = image_layer_plan.env_manifest(run, self.root / 'big_env_manifest.json')
        self.assertEqual((got['key'], got['files'], got['symlinks']), (env_key, 40000, 1))
        self.assertEqual(read(self.root / 'big_env_manifest.json'), manifest)
        # A record in the evidence that is not the one the summary names is refused.
        changed = json.loads((work / 'image_build.json').read_text(encoding='utf8'))
        changed['records'][-1]['manifest']['files'].popitem()
        (work / 'other.json').write_text(json.dumps(changed), encoding='utf8')
        with tarfile.open(run / 'collected_evidence.tar.gz', 'w:gz') as archive:
            archive.add(work / 'other.json', arcname='image_build.json', recursive=False)
        with self.assertRaises(SystemExit):
            image_layer_plan.env_manifest(run, self.root / 'refused.json')

    def test_image_a_check_summary_carries_every_state_the_controller_reads(self):
        """The check's printed summary, read by the controller's own parsers: one state per layer and
        the receipt's figures, the full rows in the tool's file."""
        mount = self.root / 'unit_mount'
        spec = fixture_spec(mount)
        place_layers(mount, spec)
        (self.root / 'cwd').mkdir()
        write(self.root / 'cwd' / 'spec.json', spec)
        out, cwd = io.StringIO(), os.getcwd()
        os.chdir(self.root / 'cwd')
        try:
            with contextlib.redirect_stdout(out):
                image_layers.main(['check', '--spec', 'spec.json', '--mount', str(mount), '--out', 'image_check.json'])
        finally:
            os.chdir(cwd)
        printed = out.getvalue().encode('utf8')
        self.assertLess(len(printed), image_layers.SUMMARY_CAP_BYTES + 512)
        layers = dict(keys={l['name']: l['key'] for l in spec['layers']})
        self.assertEqual(controller.image_states(0, printed, layers), {l['name']: 'MATCH' for l in spec['layers']})
        result = controller.image_result(printed)
        full = read(self.root / 'cwd' / 'image_check.json')
        self.assertEqual({n: r['state'] for n, r in result['layers'].items()},
                         {n: r['state'] for n, r in full['layers'].items()})
        self.assertEqual(result['bytes_hashed'], full['bytes_hashed'])

    def test_image_a_phase_output_over_the_cap_is_read_in_part_under_dash(self):
        """The collect's real command text, run by dash on a phase whose stdout is 5 MB ending in the
        tool's IMAGE_RESULT line: what comes back is under the pipe's limit, names the file it cut and
        still ends in that line. An output the size of every earlier launch's largest (the wheel
        install, 12,266 bytes) is read whole, with no marker. On Windows the shell is WSL's Ubuntu;
        with no dash the check FAILS, it never skips. The collected text stays on the Linux side and
        only its size and the marked lines come back, so the neutralised command cannot hang the check."""
        dash = dash_runner()
        self.assertIsNotNone(dash, 'no dash to run the collect command (WSL Ubuntu on Windows, dash on Linux)')
        work = '/tmp/shimmer-collect-proof'
        remote = work + '/run'
        phases = controller.phases_dir(remote)
        line = 'IMAGE_RESULT ' + json.dumps(dict(records=[dict(name='venv', built=True)]), sort_keys=True)
        script = [
            'rm -rf ' + work, 'mkdir -p ' + phases,
            "yes 'IMAGE_FILLER a long build record line' | head -c 5000000 > " + phases + '/big.out',
            "printf '\\n%s\\n' " + shlex.quote(line) + ' >> ' + phases + '/big.out',
            "printf 'warning\\n' > " + phases + '/big.err',
            "yes 'Processing ./wheels/x.whl' | head -c 12266 > " + phases + '/small.out',
            ': > ' + phases + '/small.err']
        for label in ('big', 'small'):
            collected = work + '/' + label + '.collected'
            script += ['sh -c ' + shlex.quote(controller.phase_collect_command(remote, label)) + ' > ' + collected + ' 2>&1',
                       'echo "' + label + ' BYTES=$(wc -c < ' + collected + ')"',
                       'grep "^' + controller.PHASE_OUTPUT_CAPPED + ' " ' + collected,
                       'grep "^IMAGE_RESULT " ' + collected]
        script += ['rm -rf ' + work, 'echo PROOF_END']
        got = dash('\n'.join(script) + '\n')
        self.assertIn('PROOF_END', got, got[-2000:])
        sizes = {p: int(n) for p, n in re.findall(r'^(big|small) BYTES=\s*(\d+)', got, re.M)}
        self.assertEqual(set(sizes), {'big', 'small'}, got[-2000:])
        self.assertLess(sizes['big'], 2 * controller.PHASE_COLLECT_CAP_BYTES + 512)
        self.assertLess(sizes['big'], 32 * 1024)
        self.assertEqual(sizes['small'], 12266)
        capped = controller.output_capped(got.encode('utf8'), controller.phase_files(remote, 'big'))
        self.assertEqual([c['file'] for c in capped], [phases + '/big.out'])
        # A marker naming any other path (another phase's, or text the phase printed) is not the collect's.
        self.assertEqual(controller.output_capped(got.encode('utf8'), controller.phase_files(remote, 'small')), [])
        forged = (controller.PHASE_OUTPUT_CAPPED + ' /elsewhere/big.out 99\n').encode()
        self.assertEqual(controller.output_capped(forged, controller.phase_files(remote, 'big')), [])
        self.assertGreater(capped[0]['bytes'], 5_000_000)
        self.assertEqual(controller.image_result(got.encode('utf8')), dict(records=[dict(name='venv', built=True)]))

    def summary_printed(self, command, argv, patched):
        """Run the tool's command with `patched` ({name: replacement}) and return what it printed."""
        work = self.root / ('summary_' + command)
        work.mkdir(exist_ok=True)
        mount = self.root / 'summary_mount'
        write(work / 'spec.json', fixture_spec(mount, env_sealed=False))
        out, cwd = io.StringIO(), os.getcwd()
        os.chdir(work)
        try:
            with contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(out))
                for name, value in patched.items():
                    stack.enter_context(patch.object(image_layers, name, value))
                code = image_layers.main([command, '--spec', 'spec.json', '--mount', str(mount),
                                          '--out', 'image_' + command + '.json', *argv])
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0)
        return out.getvalue().encode('utf8')

    def test_image_a_summary_over_its_cap_falls_back_and_the_controller_reads_it(self):
        """Past the cap the tool prints its minimal form (each state, each record's name, built and
        manifest digest), measured as printed; past that, the record's name and digest alone. The
        controller's own parsers read every form: states from the IMAGE_LAYER lines, the build list,
        and no bound or released list from the last form, which it takes as no answer."""
        mount = self.root / 'summary_mount'
        spec = fixture_spec(mount, env_sealed=False)
        names = [l['name'] for l in spec['layers']]
        manifest = dict(key=spec['layers'][-1]['key'], files={'a.py': dict(sha256='0' * 64, bytes=1)}, symlinks={})
        records = [dict(name=n, built=False, reason='OSError: ' + 'x' * 190, seconds=1.0) for n in names[:-1]]
        records += [dict(name=n + '_%02d' % i, built=False, reason='OSError: ' + 'y' * 190, seconds=1.0)
                    for i in range(40) for n in names[:1]]
        records.append(dict(name='venv', built=True, reason=None, seconds=2.0, manifest=manifest))
        rows = {n: dict(kind='model', key='k' * 64, state='MISMATCH', files=0, bytes=0,
                        difference=dict(unsealed=['u' * 300] * 5, absent=['a' * 300] * 5, changed_links=['l' * 300] * 5))
                for n in names}
        rows.update({'extra_%02d' % i: dict(rows[names[0]]) for i in range(20)})
        check_result = dict(layers=rows, readers=8, bytes_hashed=0, seconds=0.1, bytes_per_second=None)
        write(self.root / 'summary_states.json', dict(layers={n: dict(state='MISSING') for n in names}))
        build_argv = ['--states', str(self.root / 'summary_states.json'), '--wheels', str(self.root), '--lock', 'x',
                      '--hub', str(self.root)]
        full = self.summary_printed('build', build_argv, dict(build=lambda *a, **k: records,
                                                             SUMMARY_CAP_BYTES=10 ** 9))
        compact_bytes = len(full.strip())
        minimal = image_layers.summary_line(dict(image_layers._minimal('build', dict(records=records)),
                                                 summary_capped=True))
        cap = compact_bytes - 200
        self.assertGreater(cap, len(minimal) + 400)   # the head (record name, digest, size) is under 400
        printed = self.summary_printed('build', build_argv, dict(build=lambda *a, **k: records, SUMMARY_CAP_BYTES=cap))
        line = printed.strip()
        self.assertLessEqual(len(line), cap)
        result = controller.image_result(printed)
        self.assertTrue(result['summary_capped'])
        self.assertNotIn('summary_unavailable', result)
        self.assertEqual([r['name'] for r in result['records']], [r['name'] for r in records])
        self.assertEqual({k for r in result['records'] for k in r}, {'name', 'built', 'manifest_sha256'})
        venv = result['records'][-1]
        self.assertEqual((venv['built'], venv['manifest_sha256']),
                         (True, hashlib.sha256(image_layers.canonical(manifest)).hexdigest()))
        # The receipt's built list, as the controller writes it.
        self.assertEqual([x['name'] for x in [{k: v for k, v in x.items() if k != 'manifest'}
                                               for x in (result or {}).get('records', [])]], [r['name'] for r in records])
        # The check: past the cap each state still reaches the controller, from both its readers.
        printed = self.summary_printed('check', [], dict(check=lambda *a, **k: check_result, SUMMARY_CAP_BYTES=2500))
        self.assertLessEqual(len(printed.strip().splitlines()[-1]), 2500)
        result = controller.image_result(printed)
        self.assertTrue(result['summary_capped'])
        self.assertEqual({n: r['state'] for n, r in result['layers'].items()}, {n: 'MISMATCH' for n in rows})
        self.assertEqual(controller.image_states(0, printed, dict(keys={n: 'k' for n in names})),
                         {n: 'MISMATCH' for n in names})
        # Past even the minimal form: the record's name and digest alone, and no list the controller acts on.
        printed = self.summary_printed('build', build_argv, dict(build=lambda *a, **k: records, SUMMARY_CAP_BYTES=400))
        self.assertLessEqual(len(printed.strip()), 400)
        result = controller.image_result(printed)
        self.assertTrue(result['summary_unavailable'])
        self.assertEqual(result['record'], 'image_build.json')
        self.assertEqual((result or {}).get('records', []), [])
        self.assertIsNone(result.get('bound'))
        self.assertFalse(controller.image_released(0, printed))

    # ---- the tool itself ----------------------------------------------------------------------

    def test_image_check_finds_every_kind_of_difference(self):
        mount = self.root / 'unit_mount'
        spec = fixture_spec(mount)
        place_layers(mount, spec)
        self.assertEqual({v['state'] for v in image_layers.check(spec, mount)['layers'].values()}, {'MATCH'})
        model = next(l for l in spec['layers'] if l['kind'] == 'model')
        extra = image_layers.layer_dir(mount, model) / 'snapshots' / REVISION / 'extra.json'
        extra.write_bytes(b'{}')
        self.assertEqual(image_layers.check(spec, mount)['layers'][MODEL]['state'], 'MISMATCH')
        extra.unlink()
        config = image_layers.layer_dir(mount, model) / 'snapshots' / REVISION / 'config.json'
        config.write_bytes(b'{"fixture": True}\n')  # same size, one byte changed
        self.assertEqual(image_layers.check(spec, mount)['layers'][MODEL]['state'], 'MISMATCH')

    def test_image_a_layer_in_place_is_never_replaced(self):
        mount = self.root / 'unit_mount'
        spec = fixture_spec(mount)
        place_layers(mount, spec, kinds=('model',))
        model = next(l for l in spec['layers'] if l['kind'] == 'model')
        marker = image_layers.layer_dir(mount, model) / 'snapshots' / REVISION / 'config.json'
        marker.write_bytes(b'operator copy\n')
        source = self.root / 'unit_source'
        for name, data in MEMBER_BYTES.items():
            if name.startswith('hf_cache/hub/'):
                (source / name[len('hf_cache/hub/'):]).parent.mkdir(parents=True, exist_ok=True)
                (source / name[len('hf_cache/hub/'):]).write_bytes(data)
        partial = image_layers.layer_dir(mount, model).parent / 'racing'
        partial.mkdir()
        (partial / 'x').write_bytes(b'x')
        self.assertFalse(image_layers.place(partial, image_layers.layer_dir(mount, model)))
        self.assertEqual(marker.read_bytes(), b'operator copy\n')
        self.assertFalse(partial.exists())

    def test_image_a_bind_left_writable_is_refused(self):
        host = FakeHost()
        real = host.run

        def no_remount(argv, **kwargs):
            if [str(a) for a in argv][:4] == ['sudo', '-n', 'mount', '-o']:
                return subprocess.CompletedProcess(argv, 0, b'', b'')
            return real(argv, **kwargs)
        source, target = self.root / 'unit_layer', self.root / 'unit_target'
        source.mkdir()
        with patch.object(image_layers, 'writable', host.writable):
            with self.assertRaises(image_layers.LayerError):
                image_layers.bind([(source, target)], run=no_remount)
            self.assertEqual(host.mounts, {})  # the read-write bind it refused is not left behind
            self.assertEqual(image_layers.bind([(source, self.root / 'unit_target2')], run=host.run),
                             [str(self.root / 'unit_target2')])

    def test_image_an_env_build_already_claimed_is_refused_and_left_alone(self):
        """The env build directory is claimed with one os.mkdir: a second launch that makes the folder
        between this build's look and its claim (the race a check then create loses) wins, and this
        build refuses, is recorded not built (so the run falls back), and never touches or deletes the
        other's build."""
        mount = self.root / 'unit_mount'
        spec = fixture_spec(mount)
        env = next(l for l in spec['layers'] if l['kind'] == 'env')
        other = image_layers.env_build_dir(mount, env['key'])
        self.assertFalse(other.exists())
        wheels = self.root / 'unit_wheels'
        wheels.mkdir()
        (wheels / WHEEL).write_bytes(MEMBER_BYTES['wheels/' + WHEEL])
        lock = self.root / 'unit_lock'
        lock.write_bytes(LOCK)
        real_mkdir, raced = os.mkdir, []

        def racing_mkdir(path, *args, **kwargs):
            # The other launch makes the folder just before this build's own mkdir of it.
            if Path(path) == other and not raced:
                raced.append(1)
                real_mkdir(path)
                (other / 'the_other_launch').write_bytes(b'in progress\n')
            return real_mkdir(path, *args, **kwargs)
        with patch.object(os, 'mkdir', racing_mkdir):
            records = image_layers.build(spec, mount, self.root / 'unit_hub', wheels, lock, {'venv': 'MISSING'},
                                         run=FakeHost().run)
        self.assertEqual(raced, [1])
        self.assertEqual(len(records), 1)
        self.assertFalse(records[0]['built'])
        self.assertIn('An env build is in progress or left over', records[0]['reason'])
        self.assertEqual((other / 'the_other_launch').read_bytes(), b'in progress\n')
        self.assertEqual(sorted(p.name for p in other.iterdir()), ['the_other_launch'])
        self.assertFalse(image_layers.layer_dir(mount, env).exists())

    def test_image_a_terminated_build_removes_its_own_folders(self):
        """SIGTERM (the controller stopping an overrun build) reaches the tool's handler, which raises in
        the main thread: the model layer's partial and the env's `.build-<key>` are removed and nothing
        is placed, so a later build of the key is not refused."""
        mount = self.root / 'unit_mount'
        spec = fixture_spec(mount)
        model = next(l for l in spec['layers'] if l['kind'] == 'model')
        env = next(l for l in spec['layers'] if l['kind'] == 'env')
        hub = self.root / 'unit_hub'
        for name, data in MEMBER_BYTES.items():
            if name.startswith('hf_cache/hub/'):
                (hub / name[len('hf_cache/hub/'):]).parent.mkdir(parents=True, exist_ok=True)
                (hub / name[len('hf_cache/hub/'):]).write_bytes(data)
        wheels = self.root / 'unit_wheels'
        wheels.mkdir()
        (wheels / WHEEL).write_bytes(MEMBER_BYTES['wheels/' + WHEEL])
        cwd = self.root / 'unit_cwd'
        cwd.mkdir()
        write(cwd / 'spec.json', spec)
        (cwd / 'install.lock').write_bytes(LOCK)

        def term():
            # What `kill -TERM` does: the installed handler runs in the main thread.
            handler = signal.getsignal(signal.SIGTERM)
            self.assertTrue(callable(handler), 'no SIGTERM handler installed')
            handler(signal.SIGTERM, None)
        real_copy, real_strip = image_layers.shutil.copyfile, image_layers.strip_bytecode

        def copy_then_term(origin, target):
            real_copy(origin, target)
            term()

        def strip_then_term(directory):
            real_strip(directory)
            term()
        before = signal.getsignal(signal.SIGTERM)
        for name in (model['name'], 'venv'):
            write(cwd / 'states.json', dict(layers={name: dict(state='MISSING')}))
            argv = ['build', '--spec', 'spec.json', '--mount', str(mount), '--out', 'out.json', '--states',
                    'states.json', '--hub', str(hub), '--wheels', str(wheels), '--lock', 'install.lock']
            here = os.getcwd()
            os.chdir(cwd)
            try:
                with patch.object(image_layers.subprocess, 'run', FakeHost().run), \
                        patch.object(image_layers.shutil, 'copyfile', copy_then_term), \
                        patch.object(image_layers, 'strip_bytecode', strip_then_term):
                    with self.assertRaises(image_layers.Terminated):
                        with contextlib.redirect_stdout(io.StringIO()):
                            image_layers.main(argv)
            finally:
                os.chdir(here)
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)  # the handler it replaced is back
        model_parent = image_layers.layer_dir(mount, model).parent
        self.assertEqual([p.name for p in model_parent.iterdir() if p.name.startswith('.partial-')], [])
        self.assertFalse(image_layers.layer_dir(mount, model).exists())
        self.assertFalse(image_layers.env_build_dir(mount, env['key']).exists())
        self.assertFalse(image_layers.layer_dir(mount, env).exists())

    def test_image_the_stop_command_ends_a_live_group_under_dash(self):
        """The overrun stop's real command text, run by dash (Ubuntu's /bin/sh, which runs every detached
        phase) against a live setsid process group made as detached_launch_command makes one: a group
        that exits on TERM, one that ignores TERM so KILL is needed, and a missing pid file. The marker
        is printed only when the group is really gone, and never without a pid. dash's kill rejects
        `--` ("Illegal number: -"), so a command written with `kill -0 -- -pgid` reads the group as
        gone at once, sends no signal and prints the marker over a live group. On Windows the shell is
        WSL's Ubuntu; with no dash to run it the check FAILS, it never skips."""
        dash = dash_runner()
        self.assertIsNotNone(dash, 'no dash to run the stop command (WSL Ubuntu on Windows, dash on Linux)')
        self.assertTrue(controller.phase_stopped(0, (controller.IMAGE_STOPPED_MARKER + '\n').encode()))
        self.assertFalse(controller.phase_stopped(0, b''))
        self.assertFalse(controller.phase_stopped(3, (controller.IMAGE_STOPPED_MARKER + '\n').encode()))
        with patch.object(controller, 'IMAGE_STOP_TERM_SECONDS', 3), patch.object(controller, 'IMAGE_STOP_KILL_SECONDS', 3):
            results = {case: dash(stop_proof_script(case)) for case in ('term', 'ignores_term', 'missing')}
        for case, out in results.items():
            self.assertIn('PROOF_END', out, case + ': ' + out)
        for case in ('term', 'ignores_term'):
            out = results[case]
            self.assertIn('GROUP_STARTED', out, case + ': ' + out)
            self.assertIn('AFTER=gone', out, case + ': ' + out)
            self.assertIn('RC=0', out, case + ': ' + out)
            self.assertTrue(controller.phase_stopped(0, out.encode()), case + ': ' + out)
        seconds = {case: int(re.search(r'SECONDS=(\d+)', results[case]).group(1)) for case in ('term', 'ignores_term')}
        self.assertLess(seconds['term'], 3, results['term'])           # gone on TERM, no KILL wait
        self.assertGreaterEqual(seconds['ignores_term'], 3, results['ignores_term'])   # TERM waited out, then KILL
        missing = results['missing']
        self.assertIn('RC=2', missing, missing)
        self.assertFalse(controller.phase_stopped(2, missing.encode()), missing)
        self.assertNotIn(controller.IMAGE_STOPPED_MARKER, missing, missing)

    def test_image_spec_seals_the_archive_members_and_refuses_another_env(self):
        spec = fixture_spec(self.root / 'unit_mount', env_sealed=False)
        model = next(l for l in spec['layers'] if l['kind'] == 'model')
        self.assertEqual({'hf_cache/hub/' + MODEL + '/' + k: v for k, v in model['files'].items()},
                         {k: v for k, v in MEMBERS.items() if k.startswith('hf_cache/')})
        env = spec['layers'][-1]
        self.assertIsNone(env['files'])
        other = dict(built_env_manifest(spec, self.root / 'unit_mount'), key='0' * 64)
        with self.assertRaises(image_layers.LayerError):
            image_layers.spec(MEMBERS, hashlib.sha256(LOCK).hexdigest(), controller_manifest_image(), '3.12.3', other)
        # The env key moves with the lock, the machine image, the Python version and the tool.
        lock = hashlib.sha256(LOCK).hexdigest()
        keys = {image_layers.env_key(lock, 'img', '3.12.3', 't'), image_layers.env_key('0' * 64, 'img', '3.12.3', 't'),
                image_layers.env_key(lock, 'other', '3.12.3', 't'), image_layers.env_key(lock, 'img', '3.12.4', 't'),
                image_layers.env_key(lock, 'img', '3.12.3', 'u')}
        self.assertEqual(len(keys), 5)

    def test_image_sealer_block_names_the_spec_and_the_tool_it_writes(self):
        assets = dict(members=MEMBERS)
        block, files = sealer.image_layer_fields(assets, hashlib.sha256(LOCK).hexdigest(),
                                                 dict(id=controller_manifest_image()), dict(env_manifest=None, measure=False))
        self.assertEqual(sorted(files), ['image_layers.py', 'image_spec.json'])
        self.assertEqual(block['spec_sha256'], hashlib.sha256(files['image_spec.json']).hexdigest())
        self.assertEqual(block['tool_sha256'], hashlib.sha256(files['image_layers.py']).hexdigest())
        self.assertFalse(block['env_sealed'])
        self.assertEqual(sorted(block['keys']), sorted([MODEL, 'wheels', 'venv']))
        self.assertEqual(block['python'], read(ROOT / 'tools/cloud_run/runtime.json')['python'])


def dash_runner():
    """A callable running one script through dash, or None: WSL's Ubuntu on Windows, dash itself
    elsewhere. Every start passes cloud_run_common.no_window (HIDDEN-A)."""
    from cloud_run_common import no_window
    if os.name == 'nt':
        exe = shutil.which('wsl.exe') or shutil.which('wsl')
        argv = [exe, '-d', 'Ubuntu', '--', 'dash', '-s'] if exe else None
    else:
        exe = shutil.which('dash')
        argv = [exe, '-s'] if exe else None
    if argv is None:
        return None

    def run(script, timeout=120):
        r = subprocess.run(argv, input=script.encode('utf8'), capture_output=True, timeout=timeout,
                           creationflags=no_window(0))
        return (r.stdout + r.stderr).decode('utf8', 'replace')
    try:
        ready = run('echo dash-ready\n', timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return run if 'dash-ready' in ready else None


def stop_proof_script(case):
    """A dash script: a live setsid group made the way detached_launch_command makes one (its pid in
    the phase's pid file), then the controller's stop command text as written, then a reading of the
    group after it returns."""
    remote = '/tmp/shimmer-stop-proof-' + case + '/run'
    stop = controller.stop_phase_command(remote, 'image_bind')
    body = {'term': 'while :; do sleep 0.2; done', 'ignores_term': 'trap "" TERM; while :; do sleep 0.2; done'}.get(case)
    lines = ['R=/tmp/shimmer-stop-proof-' + case, 'rm -rf "$R"', 'mkdir -p "$R/run-phases"', 'g=']
    if body is not None:
        lines += ["(setsid sh -c '" + body.replace("'", "'\\''") + "' > /dev/null 2>&1 < /dev/null & echo $! > \"$R/run-phases/image_bind.pid\")",
                  'g="$(cat "$R/run-phases/image_bind.pid")"',
                  'i=0; while [ $i -lt 50 ] && ! kill -0 -"$g" 2>/dev/null; do sleep 0.1; i=$((i+1)); done',
                  'kill -0 -"$g" 2>/dev/null && echo GROUP_STARTED']
    lines += ['start=$(date +%s)',
              'out=$( { ' + stop + '; } 2>&1 ); rc=$?',
              'echo SECONDS=$(( $(date +%s) - start ))',
              'if [ -n "$g" ] && kill -0 -"$g" 2>/dev/null; then echo AFTER=alive; kill -KILL -"$g" 2>/dev/null; else echo AFTER=gone; fi',
              'echo RC=$rc', 'echo OUT:', 'echo "$out"', 'rm -rf "$R"', 'echo PROOF_END']
    return '\n'.join(lines) + '\n'


_REAL_STOP_PHASE_COMMAND = controller.stop_phase_command


def stop_with_double_dash(remote, label):
    """The command as first written: `kill ... -- -pgid`, which dash rejects."""
    return _REAL_STOP_PHASE_COMMAND(remote, label).replace(' -"$g"', ' -- -"$g"')


_REAL_CHECK = image_layers.check
_REAL_PLACE = image_layers.place


def check_that_never_hashes(layer_spec, mount, readers=8):
    """A check that only looks at which directories exist."""
    out = {}
    for layer in layer_spec['layers']:
        present = image_layers.layer_dir(mount, layer).is_dir()
        out[layer['name']] = dict(kind=layer['kind'], key=layer['key'], files=0, bytes=0, difference=None,
                                  state='MATCH' if present and layer['files'] is not None else
                                  'UNSEALED' if present else 'MISSING')
    return dict(layers=out, readers=readers, bytes_hashed=0, seconds=0, bytes_per_second=None)


def place_over(partial, final):
    """A placement that replaces what is there."""
    if final.exists():
        shutil.rmtree(final)
    os.rename(partial, final)
    return True


def bind_without_proof(pairs, run=subprocess.run):
    done = []
    for source, target in pairs:
        Path(target).mkdir(parents=True, exist_ok=True)
        run(['sudo', '-n', 'mount', '--bind', str(source), str(target)], capture_output=True, timeout=60)
        done.append(str(target))
    return done


def summary_as_the_full_record(command, result, record):
    """The tool as M1 ran it: the whole record printed for the controller."""
    return result


def summary_without_states(command, result, record):
    """A summary that names each layer but not its state."""
    out = _REAL_SUMMARY(command, result, record)
    if 'layers' in out:
        out['layers'] = {n: {k: v for k, v in r.items() if k != 'state'} for n, r in out['layers'].items()}
    return out


def minimal_as_compact(command, result):
    """No minimal form: past the cap the compact form again, so only the record's name survives."""
    return _REAL_COMPACT(command, result)


_REAL_SUMMARY = image_layers.summary
_REAL_COMPACT = image_layers._compact


def collect_by_cat(remote, label):
    """The collect as M1 ran it: both files read whole over the pipe."""
    base = controller.phases_dir(remote) + '/' + label
    return 'cat ' + shlex.quote(base + '.out') + ' ' + shlex.quote(base + '.err')


IMAGE_NEUTRALIZATIONS = [
    # The tool prints a summary under its cap, never the full record.
    ('test_image_a_build_record_of_megabytes_prints_a_summary_under_the_cap', image_layers, 'summary',
     summary_as_the_full_record),
    # The collect reads at most its cap of each phase file, and says which file it cut.
    # The check's summary carries each layer's state.
    ('test_image_a_check_summary_carries_every_state_the_controller_reads', image_layers, 'summary',
     summary_without_states),
    # Past the cap the minimal form keeps every state and record the controller reads.
    ('test_image_a_summary_over_its_cap_falls_back_and_the_controller_reads_it', image_layers, '_minimal',
     minimal_as_compact),
    ('test_image_a_phase_output_over_the_cap_is_read_in_part_under_dash', controller, 'phase_collect_command',
     collect_by_cat),
    # The check hashes every file: one that only sees directories reads a corrupted layer as MATCH.
    ('test_image_a_changed_byte_is_mismatch_never_replaced_and_the_assets_are_fetched', image_layers, 'check',
     check_that_never_hashes),
    ('test_image_check_finds_every_kind_of_difference', image_layers, 'check', check_that_never_hashes),
    # A layer in place is never replaced.
    ('test_image_a_layer_in_place_is_never_replaced', image_layers, 'place', place_over),
    # A bind is read-only, proven by the kernel's listing and a refused write.
    ('test_image_a_bind_left_writable_is_refused', image_layers, 'bind', bind_without_proof),
    # A layer the tool did not name is UNREACHABLE, never assumed to match.
    ('test_image_an_unreachable_mount_takes_the_asset_path_and_writes_nothing', controller, 'image_states',
     lambda returncode, stdout, layers: {name: 'MATCH' for name in layers['keys']}),
    # A MISSING layer is built after the asset path, then checked again.
    ('test_image_missing_layers_take_the_asset_path_then_build_and_check_again', controller, 'image_build_needed',
     lambda states: False),
    # Bytecode never reaches the env layer, so a rebuild matches its sealed record.
    ('test_image_a_built_env_rebuilt_from_the_same_wheels_matches_its_sealed_record', image_layers, 'strip_bytecode',
     lambda directory: None),
    # A refused bind unmounts what it mounted, its own partial bind included.
    ('test_image_a_refused_bind_unmounts_what_it_mounted', image_layers, 'unmount', lambda targets, run: []),
    ('test_image_a_failed_bind_falls_back_to_the_asset_path', image_layers, 'unmount', lambda targets, run: []),
    ('test_image_a_bind_left_writable_is_refused', image_layers, 'unmount', lambda targets, run: []),
    # The controller takes the asset path only when the mount table shows nothing left under the run root.
    ('test_image_a_bind_left_mounted_refuses_the_run', controller, 'image_released', lambda returncode, stdout: True),
    # An image phase past its deadline is read as no answer and the asset path taken, never a failure.
    ('test_image_a_check_past_its_deadline_is_unreachable_and_takes_the_asset_path', controller, 'phase_timed_out',
     lambda exc, label: False),
    ('test_image_a_build_past_its_deadline_is_not_built_and_nothing_is_checked_again', controller, 'phase_timed_out',
     lambda exc, label: False),
    ('test_image_a_bind_past_its_deadline_is_released_and_takes_the_asset_path', controller, 'phase_timed_out',
     lambda exc, label: False),
    # need_assets follows the recheck, not only the first check.
    ('test_image_a_match_lost_on_recheck_fetches_the_assets', controller, 'image_assets_needed',
     lambda states, layers: not layers),
    # The env build directory is claimed atomically; a claim that accepts an existing one builds into it.
    ('test_image_an_env_build_already_claimed_is_refused_and_left_alone', image_layers, 'claim',
     lambda build: Path(build).mkdir(parents=True, exist_ok=True)),
    # dash's kill rejects `--`: the stop written with `-- -pgid` prints its marker over a live group.
    ('test_image_the_stop_command_ends_a_live_group_under_dash', controller, 'stop_phase_command',
     stop_with_double_dash),
    # A TERM runs the tool's cleanup: a handler that ignores it lets the build finish into place.
    ('test_image_a_terminated_build_removes_its_own_folders', image_layers, 'on_term', lambda signum, frame: None),
    # The release waits for the overrun bind's stop to confirm its group is gone.
    ('test_image_an_overrun_bind_not_confirmed_stopped_refuses_the_run', controller, 'phase_stopped',
     lambda returncode, stdout: True),
    # A recheck past its deadline is read as no answer and the assets are fetched, never a failure.
    ('test_image_a_recheck_past_its_deadline_fetches_the_assets_and_loses_no_match', controller, 'phase_timed_out',
     lambda exc, label: False),
]
