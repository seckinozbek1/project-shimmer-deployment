"""A ready-to-run image on the provider filesystem, as layers used in place (D-S108, D-S109, form B).

The sealed bundle is unchanged: `assets.tar`, its digest and every member's sha256 stay in the
manifest. The image is a second way to put the SAME bytes on the instance, used only when the
instance proves, file by file, that what the mount holds is what the manifest seals.

Layers live under `<mount>/image/<kind>/<key>/`, each written once beside its final name and moved
into place with a rename that never replaces an existing layer, and never edited after:

- `model`: one per model, the tree `assets.tar` holds under `hf_cache/hub/models--<org>--<name>/`
  (`refs/main` and `snapshots/<revision>/...`). Its files are the manifest's own member list.
- `wheels`: the sealed wheels, the members under `wheels/`.
- `env`: a venv built ON THE MOUNT at `<mount>/image/env/.build-<key>` and renamed to its key, with
  the controller's own pinned install command (`--no-index --require-hashes`) plus `--no-compile`,
  and every `__pycache__` removed, so a rebuild from the same wheels gives the same bytes. Its key
  binds `install.lock`, the machine image id, the Python version and this file's own digest; its
  file list is written by the build and sealed into a later bundle (`--image-env-manifest`).

A layer's state on the instance is one of LAYER_STATES. Only MATCH is ever used. This module is
stdlib only and runs on the instance as a sealed support file (`/usr/bin/python3.12 -I`); the
sealer imports it on the laptop to write the spec. It never calls a provider.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

SCHEMA = 1
LAYER_STATES = ('MATCH', 'MISSING', 'MISMATCH', 'UNREACHABLE', 'UNSEALED')
KINDS = ('model', 'wheels', 'env')
ROOT_NAME = 'image'
CHUNK = 8 << 20
HUB_PREFIX = 'hf_cache/hub/'
WHEELS_PREFIX = 'wheels/'
# What a command prints for the controller, at most: the controller reads a phase's output back over
# ssh, and an answer over about 32 KB read through a pipe never completed on the laptop (LIVE-VIEW-A;
# M1, 11 November 2026: a 5.4 MB build record hung the collect). The full record is the --out file.
SUMMARY_CAP_BYTES = 8192


class LayerError(RuntimeError):
    pass


class Terminated(BaseException):
    """SIGTERM, raised in the main thread so every `except BaseException` cleanup runs: the build's own
    partial and `.build-<key>` folders are removed and a bind's own mounts undone. Without it a TERM
    (the controller stopping an overrun phase) kills the tool on the spot and leaves them on the shared
    filesystem, where every later build of that key refuses."""


def on_term(signum, frame):
    raise Terminated('SIGTERM')


def install_term_handler():
    """Install on_term for SIGTERM; returns the handler it replaced (None off the main thread)."""
    try:
        return signal.signal(signal.SIGTERM, on_term)
    except ValueError:
        return None


def require(condition, message):
    if not condition:
        raise LayerError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def tool_sha256():
    """This file's own digest, LF-normalised so the laptop and the instance agree."""
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


# ---- the spec, written by the sealer from the manifest ------------------------------------------

def model_layers(members):
    """One layer per model directory, its files exactly the sealed members under it."""
    groups = {}
    for name, entry in members.items():
        if not name.startswith(HUB_PREFIX):
            continue
        directory, _, relative = name[len(HUB_PREFIX):].partition('/')
        require(directory.startswith('models--') and relative, 'Unexpected cache member: ' + name)
        groups.setdefault(directory, {})[relative] = dict(sha256=entry['sha256'], bytes=entry['bytes'])
    layers = []
    for directory in sorted(groups):
        files = groups[directory]
        layers.append(dict(kind='model', name=directory, files=files,
                           key=digest(dict(kind='model', name=directory, files=files))))
    return layers


def wheels_layer(members):
    files = {name[len(WHEELS_PREFIX):]: dict(sha256=e['sha256'], bytes=e['bytes'])
             for name, e in members.items() if name.startswith(WHEELS_PREFIX)}
    require(files, 'No sealed wheels')
    return dict(kind='wheels', name='wheels', files=files, key=digest(dict(kind='wheels', files=files)))


def env_key(install_lock_sha256, machine_image_id, python_version, tool=None):
    return digest(dict(kind='env', install_lock_sha256=install_lock_sha256, machine_image_id=machine_image_id,
                       python=python_version, tool_sha256=tool or tool_sha256()))


def spec(members, install_lock_sha256, machine_image_id, python_version, env_manifest=None, measure=False):
    """The layer spec a bundle seals. `env_manifest` is the build record of an env layer (its key
    must be this bundle's env key), or None: then the env layer is UNSEALED and is never used,
    though a launch may build it and bring its record back."""
    key = env_key(install_lock_sha256, machine_image_id, python_version)
    env = dict(kind='env', name='venv', key=key, files=None, symlinks=None)
    if env_manifest is not None:
        require(env_manifest.get('key') == key, 'The env manifest is for another env key')
        require(isinstance(env_manifest.get('files'), dict) and isinstance(env_manifest.get('symlinks'), dict),
                'The env manifest lists files and symlinks')
        env.update(files=env_manifest['files'], symlinks=env_manifest['symlinks'])
    return dict(schema=SCHEMA, root=ROOT_NAME, tool_sha256=tool_sha256(), measure=bool(measure),
                layers=model_layers(members) + [wheels_layer(members), env])


def layer_dir(mount, layer):
    return Path(mount) / ROOT_NAME / layer['kind'] / layer['key']


def env_build_dir(mount, key):
    return Path(mount) / ROOT_NAME / 'env' / ('.build-' + key)


# ---- what a directory holds ---------------------------------------------------------------------

def tree(directory):
    """(regular files {relative: bytes}, symlinks {relative: target}, anything else [relative])."""
    directory = Path(directory)
    files, links, other = {}, {}, []
    for top, dirs, names in os.walk(directory, followlinks=False):
        for name in list(dirs):
            path = Path(top) / name
            if path.is_symlink():
                links[path.relative_to(directory).as_posix()] = os.readlink(path)
                dirs.remove(name)
        for name in names:
            path = Path(top) / name
            relative = path.relative_to(directory).as_posix()
            if path.is_symlink():
                links[relative] = os.readlink(path)
            elif path.is_file():
                files[relative] = path.stat().st_size
            else:
                other.append(relative)
    return files, links, other


def hash_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        while True:
            block = stream.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


class Progress:
    """PROGRESS-A: the tool's own measured progress, one small JSON file in the run root that the
    progress reader reads over ssh (done against total, in a named unit, with the time). Written at
    most every two seconds, atomically. Only the command line turns it on (`PROGRESS`), so a check
    called as a function writes nothing."""
    def __init__(self, path):
        self.path, self.last, self.stage, self.stage_started = Path(path), 0.0, None, time.time()

    def write(self, stage, unit, done, total, force=False):
        now = time.time()
        if stage != self.stage:
            self.stage, self.stage_started, force = stage, now, True
        if not force and now - self.last < 2:
            return
        self.last = now
        tmp = self.path.with_name(self.path.name + '.tmp')
        tmp.write_text(json.dumps(dict(stage=stage, unit=unit, done=done, total=total,
                                       stage_started=self.stage_started, epoch=now)), encoding='utf8')
        os.replace(tmp, self.path)


PROGRESS_FILE = 'image_progress.json'
PROGRESS = None


def report(stage, unit, done, total, force=False):
    if PROGRESS is not None:
        PROGRESS.write(stage, unit, done, total, force)


def hash_many(paths, readers, stage='hash'):
    """{path: sha256}, read by `readers` threads, largest first (hashlib releases the GIL)."""
    paths = sorted(paths, key=lambda p: -os.path.getsize(p))
    total, done, out = sum(os.path.getsize(p) for p in paths), 0, {}
    report(stage, 'bytes', 0, total, True)
    if readers <= 1:
        for p in paths:
            out[p] = hash_file(p)
            done += os.path.getsize(p)
            report(stage, 'bytes', done, total)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=readers) as pool:
            futures = {pool.submit(hash_file, p): p for p in paths}
            for future in concurrent.futures.as_completed(futures):
                out[futures[future]] = future.result()
                done += os.path.getsize(futures[future])
                report(stage, 'bytes', done, total)
    report(stage, 'bytes', done, total, True)
    return out


def manifest_of(directory, key):
    files, links, other = tree(directory)
    require(not other, 'Not a file or a symlink: ' + ', '.join(sorted(other)[:3]))
    digests = hash_many([str(Path(directory) / f) for f in files], 8)
    return dict(key=key, files={f: dict(sha256=digests[str(Path(directory) / f)], bytes=n) for f, n in sorted(files.items())},
                symlinks=dict(sorted(links.items())))


# ---- the check, on the instance, before any workload step ----------------------------------------

def check(layer_spec, mount, readers=8):
    """Every layer's state against the sealed digests, and the bytes and seconds it took."""
    begin = time.time()
    mount = Path(mount)
    reachable = mount.is_dir() and os.access(mount, os.R_OK | os.X_OK)
    out, jobs = {}, {}
    for layer in layer_spec['layers']:
        row = dict(kind=layer['kind'], key=layer['key'], state=None, files=0, bytes=0, difference=None)
        out[layer['name']] = row
        directory = layer_dir(mount, layer)
        if not reachable:
            row['state'] = 'UNREACHABLE'
            continue
        if not directory.is_dir():
            row['state'] = 'MISSING'
            continue
        if layer['files'] is None:
            row['state'] = 'UNSEALED'
            continue
        files, links, other = tree(directory)
        sealed_links = layer.get('symlinks') or {}
        if other or set(files) != set(layer['files']) or links != sealed_links:
            extra = sorted(set(files) - set(layer['files'])) + sorted(set(links) ^ set(sealed_links)) + sorted(other)
            missing = sorted(set(layer['files']) - set(files))
            row.update(state='MISMATCH', difference=dict(unsealed=extra[:5], absent=missing[:5],
                                                         changed_links=[k for k in sealed_links if links.get(k) != sealed_links[k]][:5]))
            continue
        sizes = [f for f, n in files.items() if n != layer['files'][f]['bytes']]
        if sizes:
            row.update(state='MISMATCH', difference=dict(size=sizes[:5]))
            continue
        jobs[layer['name']] = {str(directory / f): f for f in files}
    paths = [p for job in jobs.values() for p in job]
    digests = hash_many(paths, readers) if paths else {}
    total = 0
    for name, job in jobs.items():
        layer = next(l for l in layer_spec['layers'] if l['name'] == name)
        wrong = sorted(rel for p, rel in job.items() if digests[p] != layer['files'][rel]['sha256'])
        size = sum(layer['files'][rel]['bytes'] for rel in job.values())
        total += size
        out[name].update(files=len(job), bytes=size)
        out[name]['state'] = 'MISMATCH' if wrong else 'MATCH'
        if wrong:
            out[name]['difference'] = dict(hash=wrong[:5])
    seconds = time.time() - begin
    return dict(layers=out, readers=readers, bytes_hashed=total, seconds=round(seconds, 3),
                bytes_per_second=round(total / seconds) if seconds > 0 and total else None)


# ---- the build, on the instance, only for a layer that is MISSING --------------------------------

def place(partial, final):
    """Move a finished layer into place; an existing layer is never replaced (D-S109, ASSET-COPY-A)."""
    final.parent.mkdir(parents=True, exist_ok=True)
    if final.exists():
        shutil.rmtree(partial)
        return False
    os.rename(partial, final)
    return True


def build_copied(layer, mount, source):
    """A model or wheels layer from the instance's own verified extraction under `source`."""
    final = layer_dir(mount, layer)
    if final.exists():
        return dict(name=layer['name'], built=False, reason='present')
    partial = final.parent / ('.partial-%s-%d' % (layer['key'], os.getpid()))
    require(not partial.exists(), 'A partial layer is left over: ' + partial.name)
    begin = time.time()
    total, done = sum(e['bytes'] for e in layer['files'].values()), 0
    try:
        for relative, entry in sorted(layer['files'].items()):
            origin = Path(source) / relative
            require(origin.is_file() and not origin.is_symlink(), 'Build source missing: ' + relative)
            target = partial / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
            require(hash_file(target) == entry['sha256'], 'Built file differs from the seal: ' + relative)
            done += entry['bytes']
            report('build ' + layer['name'], 'bytes', done, total)
        placed = place(partial, final)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return dict(name=layer['name'], built=placed, reason=None if placed else 'present', seconds=round(time.time() - begin, 3))


def env_commands(build, wheels, lock, python):
    return [[python, '-m', 'venv', str(build)],
            [str(Path(build) / 'bin/python'), '-m', 'pip', '--disable-pip-version-check', 'install', '--no-index',
             '--no-compile', '--find-links', str(wheels), '--require-hashes', '-r', str(lock)]]


def strip_bytecode(directory):
    for top, dirs, names in os.walk(directory):
        for name in list(dirs):
            if name == '__pycache__':
                shutil.rmtree(Path(top) / name)
                dirs.remove(name)
        for name in names:
            if name.endswith('.pyc'):
                os.remove(Path(top) / name)


def claim(build):
    """Claim the env build directory with one os.mkdir: exactly one caller can make it. One that finds
    it made (another launch's build in progress, or one left over) refuses before anything of its own
    exists to clean up, so the cleanup in build_env never removes a build this call did not make."""
    Path(build).parent.mkdir(parents=True, exist_ok=True)
    try:
        os.mkdir(build)
    except FileExistsError:
        raise LayerError('An env build is in progress or left over: ' + Path(build).name) from None


def build_env(layer, mount, wheels, lock, python='/usr/bin/python3.12', run=None):
    """The env layer, built at its fixed build path on the mount, then renamed to its key. Returns
    the build record, which carries the manifest a later bundle seals."""
    run = run or subprocess.run
    final = layer_dir(mount, layer)
    if final.exists():
        return dict(name=layer['name'], built=False, reason='present')
    build = env_build_dir(mount, layer['key'])
    # The claim is the build directory itself, made in one atomic call: a second launch building the
    # same key at the same time refuses here and never touches (or deletes) the first one's build.
    claim(build)
    begin = time.time()
    pinned = sum(1 for line in Path(lock).read_text(encoding='utf8').splitlines() if '==' in line)
    site = build / 'lib' / 'python3.12' / 'site-packages'
    try:
        for argv in env_commands(build, wheels, lock, python):
            results = []
            worker = threading.Thread(target=lambda a=argv: results.append(run(a, capture_output=True, timeout=3600)),
                                      daemon=True)
            worker.start()
            while worker.is_alive():
                # Installed distributions measured against the pinned requirements, as the wheel reader does.
                installed = len(list(site.glob('*.dist-info'))) if site.is_dir() else 0
                report('build env', 'installed distributions', installed, pinned)
                worker.join(2)
            require(results and results[0].returncode == 0,
                    'Env build step failed: ' + Path(argv[0]).name + ' ' + argv[2])
        strip_bytecode(build)
        manifest = manifest_of(build, layer['key'])
        placed = place(build, final)
    except BaseException:
        shutil.rmtree(build, ignore_errors=True)
        raise
    return dict(name=layer['name'], built=placed, reason=None if placed else 'present',
                seconds=round(time.time() - begin, 3), manifest=manifest,
                manifest_sha256=hashlib.sha256(canonical(manifest)).hexdigest())


def build(layer_spec, mount, hub, wheels, lock, states, python='/usr/bin/python3.12', run=None):
    """Build every layer whose state is MISSING; nothing else is touched. A MISMATCH layer is never
    replaced by a run (it stays for the operator), an UNREACHABLE mount is never written."""
    records = []
    for layer in layer_spec['layers']:
        if states.get(layer['name']) != 'MISSING':
            continue
        try:
            if layer['kind'] == 'model':
                records.append(build_copied(layer, mount, Path(hub) / layer['name']))
            elif layer['kind'] == 'wheels':
                records.append(build_copied(layer, mount, wheels))
            else:
                records.append(build_env(layer, mount, wheels, lock, python, run))
        except (LayerError, OSError, subprocess.SubprocessError) as exc:
            records.append(dict(name=layer['name'], built=False, reason=type(exc).__name__ + ': ' + str(exc)[:200]))
    unsealed = [layer for layer in layer_spec['layers'] if layer['kind'] == 'env' and layer['files'] is None
                and states.get(layer['name']) == 'UNSEALED']
    for layer in unsealed:
        # An env layer present but not yet sealed: its record is read again, so a later bundle can seal it.
        records.append(dict(name=layer['name'], built=False, reason='present, unsealed',
                            manifest=manifest_of(layer_dir(mount, layer), layer['key'])))
    return records


# ---- the binding: read-only, so nothing a run writes reaches a shared layer -----------------------

def bind_targets(layer_spec, mount, remote, states):
    """(source, target) for every MATCH layer: models under the run's hub, wheels and the venv."""
    pairs = []
    for layer in layer_spec['layers']:
        if states.get(layer['name']) != 'MATCH':
            continue
        target = {'model': Path(remote) / HUB_PREFIX / layer['name'], 'wheels': Path(remote) / 'wheels',
                  'env': Path(remote) / 'venv'}[layer['kind']]
        pairs.append((layer_dir(mount, layer), target))
    return pairs


def writable(target):
    """True when a file can be created under `target` (it is then removed)."""
    probe = Path(target) / '.shimmer-write-probe'
    try:
        probe.write_bytes(b'')
    except OSError:
        return False
    probe.unlink()
    return True


def mounted_under(remote, run):
    """Every mount point at or under `remote`, deepest first, read from the kernel's own table."""
    r = run(['findmnt', '-rn', '-o', 'TARGET'], capture_output=True, timeout=60)
    require(r.returncode == 0, 'The mount table could not be read')
    root, out = Path(remote), []
    for line in (r.stdout or b'').decode('utf8', 'replace').splitlines():
        target = line.strip()
        if target and (Path(target) == root or root in Path(target).parents):
            out.append(target)
    return sorted(out, key=lambda t: -len(Path(t).parts))


def unmount(targets, run):
    """Unmount each target, the last mounted first; returns the targets that would not unmount."""
    left = []
    for target in reversed([str(t) for t in targets]):
        r = run(['sudo', '-n', 'umount', target], capture_output=True, timeout=60)
        if r.returncode != 0:
            left.append(target)
    return left


def release(remote, run=None):
    """Unmount whatever is mounted under the run root, then read the table again: what is left."""
    run = run or subprocess.run
    unmount(list(reversed(mounted_under(remote, run))), run)
    return dict(left=mounted_under(remote, run))


def bind(pairs, run=None):
    """Bind each layer read-only and prove it twice: the kernel lists the mount `ro`, and a write
    under it fails. Anything else refuses, so nothing a run writes can reach a shared layer. Before it
    refuses it unmounts every bind this call made, its own partial (read-write) bind included, so the
    asset path the controller then takes never writes through a bind into a shared layer."""
    run = run or subprocess.run
    done, mounted = [], []
    try:
        for source, target in pairs:
            target = Path(target)
            require(not target.exists() or (target.is_dir() and not any(target.iterdir())),
                    'Bind target is not empty: ' + str(target))
            target.mkdir(parents=True, exist_ok=True)
            for n, argv in enumerate((['sudo', '-n', 'mount', '--bind', str(source), str(target)],
                                      ['sudo', '-n', 'mount', '-o', 'remount,bind,ro', str(target)])):
                r = run(argv, capture_output=True, timeout=60)
                require(r.returncode == 0, 'Bind failed: ' + ' '.join(argv[2:4]) + ' ' + str(target))
                if n == 0:
                    mounted.append(str(target))
            r = run(['findmnt', '-no', 'OPTIONS', str(target)], capture_output=True, timeout=60)
            options = (r.stdout or b'').decode('utf8', 'replace').strip().split(',')
            require(r.returncode == 0 and 'ro' in options, 'Bound layer is not listed read-only: ' + str(target))
            require(not writable(target), 'Bound layer is writable: ' + str(target))
            done.append(str(target))
    except BaseException as exc:
        left = unmount(mounted, run)
        if left and isinstance(exc, LayerError):
            raise LayerError(str(exc) + '; left mounted: ' + ', '.join(left)) from None
        raise
    return done


# ---- the measurement (M1): read rate by readers, cold ---------------------------------------------

def drop_caches(run=None):
    run = run or subprocess.run
    r = run(['sudo', '-n', 'sh', '-c', 'sync; echo 3 > /proc/sys/vm/drop_caches'], capture_output=True, timeout=300)
    return r.returncode == 0


def measure(layer_spec, mount, readers=(1, 4, 8, 16), run=None):
    """Read every file of every present layer cold (the page cache dropped first) with each reader
    count: the read rate the check would see, sealed or not. Two sets: the models and the env (what a
    launch reads), and the env alone (many small files)."""
    run = run or subprocess.run
    present = [l for l in layer_spec['layers'] if layer_dir(mount, l).is_dir() and l['kind'] != 'wheels']
    sets = {'models_and_env': present, 'env': [l for l in present if l['kind'] == 'env']}
    rows = []
    for label, layers in sets.items():
        paths = [str(layer_dir(mount, l) / f) for l in layers for f in tree(layer_dir(mount, l))[0]]
        if not paths:
            continue
        size = sum(os.path.getsize(p) for p in paths)
        for n in readers:
            dropped = drop_caches(run)
            begin = time.time()
            hash_many(paths, n, stage='measure %s, %d readers' % (label, n))
            seconds = time.time() - begin
            rows.append(dict(set=label, layers=[l['name'] for l in layers], readers=n, caches_dropped=dropped,
                             files=len(paths), bytes=size, seconds=round(seconds, 3),
                             bytes_per_second=round(size / seconds) if seconds > 0 else None))
    return rows


def measure_docker(layer_spec, mount, run=None):
    """Form A on the same env bytes: the env layer imported as a Docker image, saved to the mount,
    then loaded cold and started with the GPU. Docker's own layer digest is checked on load. The
    saved tar is this measurement's own file and is removed after it. Returns why not, without Docker."""
    run = run or subprocess.run
    def call(argv, timeout=3600):
        begin = time.time()
        try:
            r = run(argv, capture_output=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            return dict(ok=False, seconds=round(time.time() - begin, 3), error=type(exc).__name__)
        return dict(ok=r.returncode == 0, seconds=round(time.time() - begin, 3),
                    out=(r.stdout or b'')[-400:].decode('utf8', 'replace'))
    present = dict(docker=call(['docker', '--version'], 60), toolkit=call(['nvidia-ctk', '--version'], 60))
    env = next((l for l in layer_spec['layers'] if l['kind'] == 'env'), None)
    if not present['docker']['ok'] or env is None or not layer_dir(mount, env).is_dir():
        return dict(present, measured=False, reason='no docker' if not present['docker']['ok'] else 'no env layer')
    tag = 'shimmer-env:' + env['key'][:16]
    saved = Path(mount) / ROOT_NAME / 'docker' / (env['key'] + '.measure.tar')
    saved.parent.mkdir(parents=True, exist_ok=True)
    steps = dict(present)
    steps['import'] = call(['sudo', '-n', 'sh', '-c', 'tar -C ' + str(layer_dir(mount, env)) + ' -c . | docker import - ' + tag])
    steps['save'] = call(['sudo', '-n', 'docker', 'save', '-o', str(saved), tag])
    steps['remove_image'] = call(['sudo', '-n', 'docker', 'rmi', tag], 300)
    steps['caches_dropped'] = drop_caches(run)
    steps['load_cold'] = call(['sudo', '-n', 'docker', 'load', '-i', str(saved)])
    steps['run_gpu'] = call(['sudo', '-n', 'docker', 'run', '--rm', '--gpus', 'all', tag, 'nvidia-smi', '-L'], 600)
    steps['saved_bytes'] = saved.stat().st_size if saved.exists() else None
    steps['removed_saved_tar'] = call(['sudo', '-n', 'rm', '-f', str(saved)], 300)['ok']
    return dict(steps, measured=True)


# ---- what the controller reads back -------------------------------------------------------------

def _names(values, n=2, width=160):
    return [str(v)[:width] for v in list(values)[:n]]


def _build_row(record):
    """One build record without its manifest: the manifest's digest and counts stand for it."""
    manifest = record.get('manifest')
    row = dict(name=record.get('name'), built=record.get('built'), reason=record.get('reason'),
               seconds=record.get('seconds'))
    if isinstance(manifest, dict):
        row.update(manifest_sha256=record.get('manifest_sha256') or hashlib.sha256(canonical(manifest)).hexdigest(),
                   manifest_key=manifest.get('key'), files=len(manifest.get('files') or {}),
                   symlinks=len(manifest.get('symlinks') or {}))
    return row


def _compact(command, result):
    if command == 'check':
        layers = {}
        for name, row in result['layers'].items():
            difference = row.get('difference')
            layers[name] = dict(kind=row.get('kind'), key=row.get('key'), state=row.get('state'), files=row.get('files'),
                                bytes=row.get('bytes'),
                                difference={k: _names(v) for k, v in difference.items()} if difference else None)
        return dict(layers=layers, readers=result.get('readers'), bytes_hashed=result.get('bytes_hashed'),
                    seconds=result.get('seconds'), bytes_per_second=result.get('bytes_per_second'))
    if command == 'build':
        return dict(records=[_build_row(r) for r in result['records']])
    if command == 'measure':
        rows = [{k: r.get(k) for k in ('set', 'readers', 'caches_dropped', 'files', 'bytes', 'seconds', 'bytes_per_second')}
                for r in result.get('rows', [])]
        docker = result.get('docker') or {}
        return dict(rows=rows, docker=dict(measured=docker.get('measured'), reason=docker.get('reason'),
                                           saved_bytes=docker.get('saved_bytes')))
    return dict(result)   # bind: the targets bound; release: what is left mounted. Short lists.


def _minimal(command, result):
    """Past the cap, what the controller cannot do without: each state, each record, the two lists."""
    if command == 'check':
        return dict(layers={n: dict(state=r.get('state')) for n, r in result['layers'].items()})
    if command == 'build':
        return dict(records=[{k: v for k, v in _build_row(r).items() if k in ('name', 'built', 'manifest_sha256')}
                             for r in result['records']])
    if command == 'measure':
        return dict(rows=[], docker=dict(measured=(result.get('docker') or {}).get('measured')))
    return {k: v for k, v in result.items() if k in ('bound', 'left')}


def summary(command, result, record):
    """What the controller reads back over the phase's output, under SUMMARY_CAP_BYTES: never the full
    record. A build record lists every file of every layer (5,425,078 bytes in M1, whose collect then
    hung); it is `record`, in the run root, named here with its digest, so the copy the evidence pack
    brings back is checked against it (`image_layer_plan.py env-manifest`)."""
    data = Path(record).read_bytes()
    head = dict(command=command, record=Path(record).name, record_sha256=hashlib.sha256(data).hexdigest(),
                record_bytes=len(data))
    out = dict(head, **_compact(command, result))
    if len(summary_line(out)) > SUMMARY_CAP_BYTES:
        out = dict(head, summary_capped=True, **_minimal(command, result))
    if len(summary_line(out)) > SUMMARY_CAP_BYTES:
        # Still over: only the record's name and digest. The controller then reads no state, record or
        # list from it, which each of its parsers takes as no answer (the asset path, never a MATCH).
        out = dict(head, summary_capped=True, summary_unavailable=True)
    return out


def summary_line(value):
    """The one line printed for the controller, measured as printed: the marker and the canonical JSON."""
    return b'IMAGE_RESULT ' + canonical(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('check', 'build', 'bind', 'release', 'measure'):
        p = sub.add_parser(name)
        p.add_argument('--spec', type=Path, required=True)
        p.add_argument('--mount', type=Path, required=True)
        p.add_argument('--out', type=Path, required=True)
        p.add_argument('--readers', type=int, default=8)
        p.add_argument('--states', type=Path, default=None, help='build, bind: the check result to act on')
        p.add_argument('--remote', type=Path, default=None, help='bind, release: the run root')
        p.add_argument('--hub', type=Path, default=None, help='build: the verified hf_cache/hub')
        p.add_argument('--wheels', type=Path, default=None,
                       help='build: the verified wheels (default: the wheels layer, which must read MATCH)')
        p.add_argument('--lock', type=Path, default=None, help='build: install.lock')
        p.add_argument('--only', default=None, help='bind: the layer names to bind, comma separated')
    args = parser.parse_args(argv)
    global PROGRESS
    PROGRESS = Progress(Path.cwd() / PROGRESS_FILE)
    previous = install_term_handler()
    try:
        return run_command(args)
    finally:
        PROGRESS = None
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


def run_command(args):
    layer_spec = json.loads(args.spec.read_text(encoding='utf8'))
    require(layer_spec.get('schema') == SCHEMA, 'Unknown layer spec schema')
    states = None
    if args.states is not None:
        states = {k: v['state'] for k, v in json.loads(args.states.read_text(encoding='utf8'))['layers'].items()}
    if args.command == 'check':
        result = check(layer_spec, args.mount, args.readers)
        for name, row in result['layers'].items():
            print('IMAGE_LAYER', name, row['state'], flush=True)
    elif args.command == 'build':
        wheels = args.wheels
        if wheels is None:
            layer = next(l for l in layer_spec['layers'] if l['kind'] == 'wheels')
            require(states.get(layer['name']) == 'MATCH', 'No verified wheels to build from')
            wheels = layer_dir(args.mount, layer)
        result = dict(records=build(layer_spec, args.mount, args.hub, wheels, args.lock, states))
    elif args.command == 'bind':
        only = set(args.only.split(',')) if args.only else set(states)
        chosen = {k: v for k, v in states.items() if k in only}
        result = dict(bound=bind(bind_targets(layer_spec, args.mount, args.remote, chosen)))
    elif args.command == 'release':
        result = release(args.remote)
    else:
        result = dict(rows=measure(layer_spec, args.mount), docker=measure_docker(layer_spec, args.mount))
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf8')
    # One line the controller reads back over the phase's output: a summary under SUMMARY_CAP_BYTES. The
    # full record (the build record carries the env manifest) is the --out file, which the evidence
    # pack collects from the run root.
    print(summary_line(summary(args.command, result, args.out)).decode('utf8'), flush=True)
    # A release that leaves a mount under the run root exits nonzero; the controller then refuses the run.
    return 4 if args.command == 'release' and result['left'] else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except LayerError as exc:
        print('IMAGE_REFUSED', exc, file=sys.stderr, flush=True)
        raise SystemExit(3)
    except Terminated:
        print('IMAGE_TERMINATED its own build, partial and binds removed', file=sys.stderr, flush=True)
        raise SystemExit(143)
