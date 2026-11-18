#!/usr/bin/env python3
"""A one-off asset build on Lambda (D-736, D-739): one declared model fetched at a pinned revision into a new sealed
asset archive that lives on the Lambda persistent file system only.

Seckin approved (D-736) one step whose instance may reach the network, only to fetch the one model a declaration
names (tools/cloud_run/asset_build_<name>.json: the repository, its 40-hex revision, every file with its size and its
hub pin, the LFS SHA-256 or the git blob SHA-1), into an archive built from the reuse bundle's own archive plus
that model. No project data, prompt, key or record travels: the request carries the declaration, the reuse
bundle's manifest, the runner files and digests of the read copies only. Every other step and every run keeps
the network denied (NO-WEB-LOCAL-A). D-739: the archive and the model stay on the file system; the laptop keeps
the manifest (the archive's file list and SHA-256) and never the bytes.

On the laptop:
    request   --source COMMIT --declaration tools/cloud_run/asset_build_olmo2_labeller.json --reuse <reuse bundle>
              --inputs <folder with provider_inventory.json> --ledger <ledger> --forecast-minutes N
              --storage-forecast-usd X --instance-types gpu_1x_a10 [--uncompared] [--step-approval-usd U
              --step-approval-source D-NNN] --out <new request folder>
        launched by tools/ordinary_final_bound_cloud.py --request <folder>, as a seal request is (the guard,
        the ledger and the reaper; the provider-side copy of the reuse archive, MATCH or nothing).
    admit     --run <fetched run folder or its evidence> --reuse <reuse bundle> --declaration <file>
              --out <new manifest-only reuse bundle>
        the reuse bundle the next seals name: the reuse manifest with the new archive's digest, size and members,
        the model added, `held_on: filesystem`; no archive file.

On the instance (`build`, called by tools/ordinary_final_run.py for this record kind only): the reuse archive is the
provider-side copy the controller placed and hashed (assets.tar); the network is opened to the declaration's hub
host suffixes alone (name lookups for any other host and connections to any address not looked up that way are
refused and recorded), each declared file fetched with no token and checked against its size and pin, the network
then denied for the rest of the run (cloud_run_observer.deny_network), the new archive written (the reuse archive
byte for byte, then the model's refs and snapshot members, as build_assets writes them), hashed, and placed on the
file system under its hash-keyed name only when no file holds that name (never overwritten). The receipt holds
digests and sizes only.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import socket
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DECLARATION_SCHEMA = 'asset-build-declaration-v1'
REQUEST_SCHEMA = 'asset-build-request-v1'
RECEIPT_SCHEMA = 'asset-build-receipt-v1'
RECORD_KIND = 'asset_build_launch_record'
REQUEST_FILE = 'seal_request.json'          # the name the bound wrapper's request readers open
DECLARATION_FILE = 'asset_build_declaration.json'
REUSE_MANIFEST = 'reuse_manifest.json'
RECEIPT = 'asset_build_receipt.json'
HELD_ON_FILESYSTEM = 'filesystem'
HELD_MANIFEST = 'HELD_ON_FILESYSTEM.json'          # the local manifest of what stays on the file system
HELD_MANIFEST_SCHEMA = 'held-on-filesystem-v1'
SUPPORT = {'ordinary_final_run.py': 'tools/ordinary_final_run.py',
           'ordinary_final_summary.py': 'tools/ordinary_final_summary.py',
           'cloud_run_observer.py': 'tools/cloud_run_observer.py',
           'asset_build.py': 'tools/asset_build.py'}
DECLARATION_KEYS = {'schema', 'decision', 'purpose', 'model', 'allowed_host_suffixes', 'base_assets_sha256'}
HEX40, HEX64 = re.compile(r'[0-9a-f]{40}'), re.compile(r'[0-9a-f]{64}')
DECISION = re.compile(r'D-[0-9]+')
BLOCK = 8 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(BLOCK), b''):
            h.update(block)
    return h.hexdigest()


def git_blob_sha1(path):
    h = hashlib.sha1()
    h.update(b'blob %d\0' % Path(path).stat().st_size)
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(BLOCK), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=1, sort_keys=True), encoding='utf-8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


# ---------------------------------------------------------------------------
# the declaration: exactly one model


def check_declaration(value):
    """The declaration, or RuntimeError: one model, a bare 40-hex revision, every file with its size and exactly
    one hub pin, hub host suffixes only, the reuse archive's digest and the decision that allows the step."""
    require(isinstance(value, dict) and value.get('schema') == DECLARATION_SCHEMA, 'Not an asset-build declaration')
    require(set(value) == DECLARATION_KEYS, 'An asset-build declaration holds exactly %s' % sorted(DECLARATION_KEYS))
    require(isinstance(value['decision'], str) and DECISION.fullmatch(value['decision']), 'The declaration names its decision')
    model = value['model']
    require(isinstance(model, dict) and set(model) == {'model_id', 'revision', 'files'}, 'The declaration names one model')
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.\-]*/[A-Za-z0-9][A-Za-z0-9_.\-]*', str(model['model_id'])),
            'A model id is owner/name')
    require(isinstance(model['revision'], str) and HEX40.fullmatch(model['revision']), 'A revision is 40 hex digits')
    files = model['files']
    require(isinstance(files, dict) and files and 'config.json' in files, 'The model declares its files, config.json among them')
    for name, entry in files.items():
        require(re.fullmatch(r'[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)*', name) and '..' not in name.split('/'),
                'A file name is a plain relative path')
        pins = [k for k in ('lfs_sha256', 'git_sha1') if k in entry]
        require(set(entry) == {'bytes'} | set(pins) and len(pins) == 1 and isinstance(entry['bytes'], int)
                and entry['bytes'] > 0, 'Each file has its size and exactly one hub pin')
        require((HEX64 if pins[0] == 'lfs_sha256' else HEX40).fullmatch(entry[pins[0]]), 'A pin is a hex digest')
    hosts = value['allowed_host_suffixes']
    require(isinstance(hosts, list) and hosts and all(isinstance(h, str) and re.fullmatch(r'[a-z0-9.\-]+\.[a-z]+', h)
                                                      for h in hosts), 'The allowed hosts are domain suffixes')
    require(isinstance(value['base_assets_sha256'], str) and HEX64.fullmatch(value['base_assets_sha256']),
            'The declaration names the reuse archive it builds on')
    return value


def load_declaration(path):
    return check_declaration(read(path))


# ---------------------------------------------------------------------------
# the network: the hub's hosts for the fetch, nothing else, then denied


def host_allowed(host, suffixes):
    host = str(host or '').lower().rstrip('.')
    return any(host == s or host.endswith('.' + s) for s in suffixes)


class HubOnly:
    """Name lookups only for the declared suffixes, connections only to the addresses those lookups gave (and
    numeric loopback). Every allowed and refused attempt is recorded by host or kind, never by payload."""

    # The socket methods held to the looked-up addresses (sendto as deny_network patches it: a datagram carries
    # its own address, so it is held like a connection).
    GUARDED = ('connect', 'connect_ex', 'sendto')

    def __init__(self, suffixes, rec):
        self.suffixes, self.rec, self.addresses = list(suffixes), rec, set()
        self.allowed, self.refused = set(), 0

    def install(self):
        self.originals = (socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex, socket.create_connection,
                          socket.socket.sendto)
        original_lookup, original_connect, original_connect_ex, _, original_sendto = self.originals
        guard = self

        def lookup(host, *args, **kwargs):
            if not host_allowed(host, guard.suffixes):
                guard.refused += 1
                guard.rec.event('network_refused', network_kind='dns', host_allowed=False)
                raise RuntimeError('Asset build: only the declared hub hosts may be reached')
            out = original_lookup(host, *args, **kwargs)
            guard.addresses.update(a[4][0] for a in out)
            guard.allowed.add(str(host).lower())
            guard.rec.event('network_allowed', network_kind='dns', host=str(host).lower())
            return out

        def checked(original, kind):
            def connect(sock, address):
                ip = address[0] if isinstance(address, tuple) else None
                if ip in ('127.0.0.1', '::1') or ip in guard.addresses:
                    return original(sock, address)
                guard.refused += 1
                guard.rec.event('network_refused', network_kind=kind, host_allowed=False)
                raise RuntimeError('Asset build: a connection to an address no declared host gave')
            return connect

        def sendto(sock, data, *args):
            address = args[-1] if args else None
            ip = address[0] if isinstance(address, tuple) else None
            if ip in ('127.0.0.1', '::1') or ip in guard.addresses:
                return original_sendto(sock, data, *args)
            guard.refused += 1
            guard.rec.event('network_refused', network_kind='socket_sendto', host_allowed=False)
            raise RuntimeError('Asset build: a datagram to an address no declared host gave')

        socket.getaddrinfo = lookup
        if 'connect' in self.GUARDED:
            socket.socket.connect = checked(original_connect, 'socket_connect')
        if 'connect_ex' in self.GUARDED:
            socket.socket.connect_ex = checked(original_connect_ex, 'socket_connect_ex')
        if 'sendto' in self.GUARDED:
            socket.socket.sendto = sendto
        return self

    def restore(self):
        (socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex, socket.create_connection,
         socket.socket.sendto) = self.originals


# ---------------------------------------------------------------------------
# the fetch, checked against every pin


# The fetch's environment. HF_HUB_DISABLE_XET: the sealed runtime pins hf-xet, whose native client opens its own
# sockets outside Python and so outside HubOnly; with it disabled every byte goes through Python's sockets (requests),
# where HubOnly holds each lookup and connection.
FETCH_ENV = {'HF_HUB_OFFLINE': '0', 'HF_HUB_DISABLE_XET': '1'}


def hub_download(model_id, filename, revision, cache_dir):
    """One file at the pinned revision, with no token and no xet transfer (the sealed huggingface_hub, on the
    instance only)."""
    os.environ.update(FETCH_ENV)
    os.environ.pop('HF_TOKEN', None)
    import huggingface_hub
    import huggingface_hub.constants as constants
    constants.HF_HUB_OFFLINE = False
    if FETCH_ENV.get('HF_HUB_DISABLE_XET') == '1':
        # Newer hubs read HF_HUB_DISABLE_XET; the sealed 0.30.2 chooses xet only when hf_xet is importable
        # (file_download.is_xet_available), so that answer is made False for this process as well.
        constants.HF_HUB_DISABLE_XET = True
        import huggingface_hub.file_download as file_download
        from huggingface_hub.utils import _runtime
        _runtime._package_versions['hf_xet'] = 'N/A'
        file_download.is_xet_available = lambda: False
    return huggingface_hub.hf_hub_download(model_id, filename=filename, revision=revision, cache_dir=str(cache_dir),
                                           token=False)


def fetch(declaration, staging, download=hub_download):
    """{name: path} and {name: {sha256, bytes}} of every declared file, each held to its size and hub pin."""
    model = declaration['model']
    paths, entries = {}, {}
    for name, pin in sorted(model['files'].items()):
        path = Path(download(model['model_id'], name, model['revision'], Path(staging)))
        require(path.is_file() and path.stat().st_size == pin['bytes'], 'A fetched file has another size: ' + name)
        digest = sha(path)
        if 'lfs_sha256' in pin:
            require(digest == pin['lfs_sha256'], 'A fetched file differs from its LFS pin: ' + name)
        else:
            require(git_blob_sha1(path) == pin['git_sha1'], 'A fetched file differs from its git pin: ' + name)
        paths[name], entries[name] = path, dict(sha256=digest, bytes=pin['bytes'])
    return paths, entries


# ---------------------------------------------------------------------------
# the archive: the reuse archive byte for byte, then the model's members as build_assets writes them


def model_item(declaration, entries):
    model = declaration['model']
    ref = model['revision'].encode('ascii')
    return dict(model_id=model['model_id'], revision=model['revision'], files=entries,
                cache_ref=dict(bytes=len(ref), sha256=hashlib.sha256(ref).hexdigest()))


def new_members(item):
    prefix = 'hf_cache/hub/models--' + item['model_id'].replace('/', '--')
    out = {prefix + '/refs/main': item['cache_ref']}
    for name, entry in sorted(item['files'].items()):
        out[prefix + '/snapshots/' + item['revision'] + '/' + name] = entry
    return out


def build_archive(base_tar, item, paths, out_tar):
    """The new archive at `out_tar` (never over an existing file): {sha256, bytes, added}."""
    out_tar = Path(out_tar)
    require(not out_tar.exists(), 'Refuse to replace an existing asset archive')
    shutil.copyfile(base_tar, out_tar)
    added = new_members(item)
    prefix = 'hf_cache/hub/models--' + item['model_id'].replace('/', '--')
    with tarfile.open(out_tar, 'a', format=tarfile.PAX_FORMAT) as archive:
        existing = set(archive.getnames())
        require(not (set(added) & existing), 'The reuse archive already holds a member of the model')
        ref = item['revision'].encode('ascii')
        info = tarfile.TarInfo(prefix + '/refs/main')
        info.size = len(ref)
        archive.addfile(info, io.BytesIO(ref))
        for name in sorted(item['files']):
            info = tarfile.TarInfo(prefix + '/snapshots/' + item['revision'] + '/' + name)
            info.size = Path(paths[name]).stat().st_size
            with open(paths[name], 'rb') as stream:
                archive.addfile(info, stream)
    return dict(sha256=sha(out_tar), bytes=out_tar.stat().st_size, added=added)


def place(out_tar, mount, digest):
    """The archive under its hash-keyed name on the file system: written once, never overwritten; a file that already
    holds the name is accepted only when it hashes to the same digest."""
    target = Path(mount) / ('assets-%s.tar' % digest)
    if target.exists():
        require(sha(target) == digest, 'A file on the file system holds this digest\'s name with other bytes')
        return dict(path=str(target), placed=False, already_there=True)
    partial = Path(str(target) + '.partial')
    require(not partial.exists(), 'A partial copy is on the file system: the operator looks at it first')
    shutil.copyfile(out_tar, partial)
    require(sha(partial) == digest, 'The copy on the file system does not hash to the archive digest')
    require(not target.exists(), 'Another writer placed this digest meanwhile')
    os.rename(partial, target)
    return dict(path=str(target), placed=True, already_there=False)


def build(base, evidence, rec, deny, mount, download=hub_download):
    """The instance's whole step (tools/ordinary_final_run.execute_asset_build after every guard): returns the
    receipt, also written into the evidence."""
    base, evidence = Path(base), Path(evidence)
    declaration = load_declaration(base / DECLARATION_FILE)
    manifest = read(base / 'execution_manifest.json')
    require(manifest['assets_archive']['sha256'] == declaration['base_assets_sha256'],
            'The reuse archive is not the one the declaration builds on')
    require(sha(base / 'assets.tar') == declaration['base_assets_sha256'], 'The reuse archive here is not the declared one')
    network = HubOnly(declaration['allowed_host_suffixes'], rec).install()
    try:
        paths, entries = fetch(declaration, base / 'asset_build_staging', download)
    finally:
        network.restore()
        deny(rec)               # the rest of the run: no network at all
    item = model_item(declaration, entries)
    built = build_archive(base / 'assets.tar', item, paths, base / 'assets_built.tar')
    placed = place(base / 'assets_built.tar', mount, built['sha256'])
    receipt = dict(schema=RECEIPT_SCHEMA, decision=declaration['decision'],
                   declaration_sha256=sha(base / DECLARATION_FILE), base_assets_sha256=declaration['base_assets_sha256'],
                   archive=dict(sha256=built['sha256'], bytes=built['bytes']), model=item, added_members=built['added'],
                   filesystem=dict(placed), network=dict(hosts_looked_up=sorted(network.allowed),
                                                         refused=network.refused),
                   built_epoch=round(time.time(), 3))
    write(evidence / RECEIPT, receipt)
    return receipt


# ---------------------------------------------------------------------------
# on the laptop: the request, its launch record, and the manifest-only reuse bundle


def is_request(folder):
    try:
        return read(Path(folder) / REQUEST_FILE).get('schema') == REQUEST_SCHEMA
    except (OSError, ValueError):
        return False


def write_request(out, source, declaration_path, reuse_bundle, inputs, budget, now=None, prep=None,
                  private=None, r_ledger=None, refusals=None, reread=None):
    """The request folder `out` (new): the declaration, the reuse manifest, the install lock, the runner files read
    from the commit, and the request (digests of the read copies, the standing-orders attestation, the budget, the
    image, the controller binding, every file's digest). No asset archive, no project, no record."""
    import prepare_ordinary_final_run as default_prep
    import instance_reaper
    import loop_budget_guard as guard
    import seal_route
    prep = prep or default_prep
    out = Path(out)
    require(not out.exists(), 'An asset-build request is written into a new folder')
    declaration = load_declaration(declaration_path)
    reuse_manifest = read(Path(reuse_bundle) / 'execution_manifest.json')
    seal_route.refuse_launch_record(reuse_manifest, 'the reuse bundle of an asset build')
    require(reuse_manifest['assets_archive']['sha256'] == declaration['base_assets_sha256'],
            'The reuse bundle\'s archive is not the one the declaration builds on')
    require(declaration['model']['model_id'] not in {m['model_id'] for m in reuse_manifest['models']},
            'The reuse archive already carries the declared model')
    ledgers = list((budget or {}).get('ledgers') or []) + [
        Path(private or instance_reaper.main_private()) / 'budget_ledger.jsonl', Path(r_ledger or instance_reaper.R_LEDGER)]
    provider, _ = seal_route.fresh_inventory(inputs, ledgers, reread)
    copies, taken = seal_route.read_copies(private or instance_reaper.main_private(), r_ledger or instance_reaper.R_LEDGER, now)
    found = refusals if refusals is not None else [list(f) for f in guard.standing_orders_failures(guard.standing_orders_root())]
    commit = prep.git(prep.ROOT, 'rev-parse', source).decode('ascii').strip()
    out.mkdir(parents=True)
    shutil.copyfile(declaration_path, out / DECLARATION_FILE)
    (out / REUSE_MANIFEST).write_bytes((Path(reuse_bundle) / 'execution_manifest.json').read_bytes())
    shutil.copyfile(Path(reuse_bundle) / 'install.lock', out / 'install.lock')
    for name, path in SUPPORT.items():
        (out / name).write_bytes(prep.git(prep.ROOT, 'show', '%s:%s' % (commit, path)))
    job = dict(read_copies={k: {f: v[f] for f in ('path', 'sha256', 'bytes')} for k, v in copies.items()},
               taken_epoch=round(taken, 3), attestation=seal_route.attestation(found, taken),
               declaration_sha256=sha(out / DECLARATION_FILE))
    request = dict(schema=REQUEST_SCHEMA, commit=commit, job=job, asset_build=request_block(declaration),
                   budget=prep.budget_fields(provider, budget, time.time() if now is None else now, arm='S'),
                   image=default_prep.region_image(provider['images'], guard.PREFERRED_REGION),
                   wheelhouse=reuse_manifest.get('wheels') or {},
                   local_control_hashes={n: sha(prep.ROOT / n) for n in prep.CONTROL_FILES},
                   files={p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    write(out / REQUEST_FILE, request)
    return request


# The request's asset_build block, every field held to the declaration it carries (the model, its revision, the
# reuse archive it builds on and the decision).
REQUEST_BLOCK_FIELDS = ('decision', 'model_id', 'revision', 'base_assets_sha256')


def request_block(declaration):
    return dict(decision=declaration['decision'], model_id=declaration['model']['model_id'],
                revision=declaration['model']['revision'], base_assets_sha256=declaration['base_assets_sha256'])


def request_error(folder, controller_root):
    """None when the asset-build request in `folder` may be launched by the controller at `controller_root`, else
    its one-line reason (the seal request's rules: no archive or sealed file, every file at its digest and nothing
    else, the controller's own files at the request's binding, the attestation's refusals empty), and the
    declaration valid and the one the request names."""
    import seal_route
    folder = Path(folder)
    try:
        request = read(folder / REQUEST_FILE)
    except (OSError, ValueError):
        return 'The asset-build request cannot be read'
    if request.get('schema') != REQUEST_SCHEMA:
        return 'Not an asset-build request'
    present = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()} - {REQUEST_FILE}
    refused = sorted(n for n in present if Path(n).name in seal_route.REQUEST_REFUSED_NAMES)
    if refused:
        return 'An asset-build request carries no archive or sealed file: ' + ', '.join(refused)
    if present != set(request.get('files') or {}):
        return 'The asset-build request holds other files than it names'
    changed = sorted(n for n, digest in request['files'].items() if sha(folder / n) != digest)
    if changed:
        return 'A file of the asset-build request changed: ' + ', '.join(changed[:3])
    moved = sorted(n for n, digest in (request.get('local_control_hashes') or {}).items()
                   if not (Path(controller_root) / n).is_file() or sha(Path(controller_root) / n) != digest)
    if moved or not request.get('local_control_hashes'):
        return 'Controller source changed: ' + ', '.join(moved[:3])
    if (request.get('job') or {}).get('attestation', {}).get('refusals'):
        return 'The asset-build request attests a standing order that does not hold'
    try:
        declaration = load_declaration(folder / DECLARATION_FILE)
    except RuntimeError as exc:
        return str(exc)
    block, want = request.get('asset_build') or {}, request_block(declaration)
    if request['job'].get('declaration_sha256') != sha(folder / DECLARATION_FILE) or \
            any(block.get(k) != want[k] for k in REQUEST_BLOCK_FIELDS):
        return 'The asset-build request names another declaration'
    return None


COPY_DECLARATION = 'asset_copy_declaration.json'


def copy_declaration_sealed(out, manifest, seal):
    """18 Nov 18:01 (the second build stopped on the instance: no asset_copy_declaration.json there): the build reads
    the file system's mount from the asset-copy declaration on the instance, and the controller sends a record's
    support files only. The declaration is made one of them, at its digest, and the manifest and its seal written
    again, so it travels with the record and is checked there like every other support file."""
    manifest = dict(manifest, support_files=dict(manifest['support_files'],
                                                 **{COPY_DECLARATION: sha(Path(out) / COPY_DECLARATION)}))
    write(Path(out) / 'execution_manifest.json', manifest)
    seal = dict(seal, execution_manifest_sha256=sha(Path(out) / 'execution_manifest.json'))
    write(Path(out) / 'seal.json', seal)
    return manifest, seal


def launch_record(request_folder, out, controller_root, now=None):
    """The launch record of an asset-build request (as seal_route.launch_record derives a seal request's): every
    request file linked in, execution_manifest.json of kind RECORD_KIND (arm S, no project, no laptop archive: the
    reuse archive comes from the provider-side copy, MATCH or nothing), seal.json, the asset-copy declaration, the
    receipt deferring the asset check to the instance, the binding and the local check."""
    import seal_route
    request_folder, out = Path(request_folder), Path(out)
    problem = request_error(request_folder, controller_root)
    require(problem is None, problem or '')
    request = read(request_folder / REQUEST_FILE)
    require(not out.exists(), 'A launch record is written into a new run folder')
    out.mkdir(parents=True)
    for name in list(request['files']) + [REQUEST_FILE]:
        try:
            os.link(request_folder / name, out / name)
        except OSError:
            shutil.copyfile(request_folder / name, out / name)
    reuse = read(out / REUSE_MANIFEST)
    manifest = {k: reuse[k] for k in seal_route.RECORD_FROM_REUSE if k in reuse}
    manifest.update(request['budget'])
    manifest.update(dict(kind=RECORD_KIND, request_sha256=sha(out / REQUEST_FILE), arm='S', argv=['seal-job'],
                         model_mode='final', max_runs=1, multi_round=False, protected_test=False,
                         source_commit=request['commit'], asset_build=request['asset_build'], image=request['image'],
                         local_control_hashes=request['local_control_hashes'],
                         support_files=dict(request['files'], **{REQUEST_FILE: sha(out / REQUEST_FILE)}),
                         source_archive_sha256=None, project_files={}, provider='Lambda',
                         workload=dict(answer_key_transferred=False, file_count=0, files={}, name='asset-build',
                                       review_targets=None),
                         classification='PREPARED_NOT_AUTHORIZED'))
    manifest['instance'] = next(iter(request['budget'].get('instance_candidates') or [{}]))
    write(out / 'execution_manifest.json', manifest)
    seal = dict(execution_manifest_sha256=sha(out / 'execution_manifest.json'), source_commit=request['commit'],
                operator_authorized=False, classification='PREPARED_NOT_AUTHORIZED', exposure='exposed',
                kind=RECORD_KIND, request_sha256=manifest['request_sha256'])
    write(out / 'seal.json', seal)
    import declare_asset_copy
    declare_asset_copy.declare(out, declare_asset_copy.LOOP_FILESYSTEM_NAME, declare_asset_copy.LOOP_MOUNT)
    manifest, seal = copy_declaration_sealed(out, manifest, seal)
    seal_route.deferred_job_receipt(out)
    write(out / 'authorization_binding.json', dict(
        manifest_sha256=sha(out / 'execution_manifest.json'), seal_sha256=sha(out / 'seal.json'),
        preparation_commit=request['commit'], source_commit=request['commit'], project_sha256=None,
        assets_sha256=manifest['assets_archive']['sha256'], kind=RECORD_KIND, request_sha256=manifest['request_sha256']))
    write(out / 'AUTHORIZED_LOCAL_REVERIFICATION.json', dict(
        passed=True, manifest_sha256=sha(out / 'execution_manifest.json'),
        checked_by='asset_build.request_error: every request file at its digest, the controller binding, no archive',
        time_epoch=round(time.time() if now is None else now, 3)))
    return manifest, seal


def find_receipt(run):
    """The one asset-build receipt in a fetched run folder or evidence (a folder or collected_evidence.tar.gz)."""
    run = Path(run)
    archives = sorted(run.rglob('collected_evidence.tar.gz')) if run.is_dir() else [run]
    found = [read(p) for p in sorted(run.rglob(RECEIPT))] if run.is_dir() else []
    for path in archives:
        if path.is_file() and path.name.endswith('.tar.gz'):
            with tarfile.open(path, 'r:gz') as tar:
                for m in tar.getmembers():
                    if m.isfile() and m.name.endswith('/' + RECEIPT):
                        found.append(json.loads(tar.extractfile(m).read()))
    distinct = {json.dumps(r, sort_keys=True): r for r in found}
    require(len(distinct) == 1, 'The run holds %d asset-build receipts, not one' % len(distinct))
    return next(iter(distinct.values()))


def receipt_refusal(receipt, reuse, declaration_path):
    """None when the receipt is of this declaration, builds on this reuse archive, carries exactly the declared model
    (its revision, files, sizes and LFS digests) and its members, placed under its digest; else the reason."""
    declaration = load_declaration(declaration_path)
    if receipt.get('schema') != RECEIPT_SCHEMA or receipt.get('declaration_sha256') != sha(declaration_path):
        return 'The receipt is of another declaration'
    if not reuse['assets_archive']['sha256'] == receipt['base_assets_sha256'] == declaration['base_assets_sha256']:
        return 'The receipt builds on another reuse archive'
    item, want = receipt['model'], declaration['model']
    if not (item['model_id'] == want['model_id'] and item['revision'] == want['revision']
            and sorted(item['files']) == sorted(want['files'])
            and all(item['files'][n]['bytes'] == want['files'][n]['bytes'] for n in item['files'])
            and all(item['files'][n]['sha256'] == p['lfs_sha256'] for n, p in want['files'].items() if 'lfs_sha256' in p)):
        return "The receipt's model is not the declared one"
    if receipt['added_members'] != new_members(item):
        return "The receipt's added members are not the model's"
    if not receipt['filesystem'].get('path', '').endswith('assets-%s.tar' % receipt['archive']['sha256']):
        return 'The archive was not placed under its digest'
    return None


def admit(receipt, reuse_bundle, declaration_path, out):
    """The manifest-only reuse bundle at `out` (new): the reuse manifest with the new archive's digest, size and
    members (the reuse archive's plus the model's), the model added, and `held_on: filesystem`; install.lock;
    and this receipt. No archive file: the laptop keeps the file list and the SHA-256 (D-739)."""
    reuse = read(Path(reuse_bundle) / 'execution_manifest.json')
    problem = receipt_refusal(receipt, reuse, declaration_path)
    require(problem is None, problem or '')
    item = receipt['model']
    members = dict(reuse['assets_archive']['members'])
    require(not (set(members) & set(receipt['added_members'])), 'A member of the model was already in the reuse archive')
    members.update(receipt['added_members'])
    manifest = dict(reuse)
    manifest['models'] = list(reuse['models']) + [item]
    manifest['assets_archive'] = dict(filename='assets.tar', bytes=receipt['archive']['bytes'],
                                      sha256=receipt['archive']['sha256'], members=members,
                                      held_on=HELD_ON_FILESYSTEM, built_from=receipt['base_assets_sha256'],
                                      built_by=dict(decision=receipt['decision'],
                                                    declaration_sha256=receipt['declaration_sha256']))
    out = Path(out)
    require(not out.exists(), 'The reuse bundle is written into a new folder')
    out.mkdir(parents=True)
    write(out / 'execution_manifest.json', manifest)
    shutil.copyfile(Path(reuse_bundle) / 'install.lock', out / 'install.lock')
    write(out / RECEIPT, receipt)
    # Seckin 16:11: only what the next local step needs comes back; what stays on the Lambda file system is named
    # here by path, size and SHA-256, and every laptop-side check works on these and the receipt, never the bytes.
    write(out / HELD_MANIFEST, dict(schema=HELD_MANIFEST_SCHEMA, decision='D-739',
                                    held=[dict(kind='asset_archive', path=receipt['filesystem']['path'],
                                               bytes=receipt['archive']['bytes'], sha256=receipt['archive']['sha256'])],
                                    brought_back=sorted(['execution_manifest.json', 'install.lock', RECEIPT])))
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('request')
    for flag in ('--source', '--declaration', '--reuse', '--inputs', '--ledger', '--out'):
        r.add_argument(flag, required=True)
    r.add_argument('--forecast-minutes', type=float, required=True)
    r.add_argument('--storage-forecast-usd', type=float, required=True)
    r.add_argument('--instance-types', default=None)
    r.add_argument('--uncompared', action='store_true')
    r.add_argument('--step-approval-usd', type=float, default=None)
    r.add_argument('--step-approval-source', default=None)
    a = sub.add_parser('admit')
    for flag in ('--run', '--reuse', '--declaration', '--out'):
        a.add_argument(flag, required=True)
    args = ap.parse_args(argv)
    sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools' / 'loop'), str(ROOT / 'scripts')]
    if args.cmd == 'request':
        import seal_route_driver
        budget = seal_route_driver.request_budget([args.ledger], args.forecast_minutes, args.storage_forecast_usd,
                                                  args.instance_types, args.uncompared)   # the comma list, split there
        if args.step_approval_usd is not None:
            budget['step_approval'] = dict(usd=args.step_approval_usd, source=args.step_approval_source)
        request = write_request(args.out, args.source, args.declaration, args.reuse, args.inputs, budget)
        print(json.dumps({'model_id': request['asset_build']['model_id'], 'files': len(request['files']),
                          'cap_usd': request['budget'].get('per_run_cap_usd')}, sort_keys=True))
        return 0
    manifest = admit(find_receipt(args.run), args.reuse, args.declaration, args.out)
    print(json.dumps({'archive_sha256': manifest['assets_archive']['sha256'], 'bytes': manifest['assets_archive']['bytes'],
                      'models': len(manifest['models']), 'held_on': HELD_ON_FILESYSTEM}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
