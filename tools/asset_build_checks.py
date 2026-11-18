#!/usr/bin/env python3
"""Checks 525 to 528 (lane/v-synlab-launch; D-736, D-739): the one-off asset build with the network opened to the
declared hub hosts for its fetch alone, and the asset archive held on the Lambda file system only.

525 the declaration and the network: a declaration names exactly one model at a 40-hex revision, every file with
    its size and one hub pin, hub host suffixes and the reuse archive it builds on (anything else refused); during
    the fetch a name lookup for any other host, and a connection to an address no declared host gave, are refused
    and recorded, the declared hosts allowed; after the fetch the run's network is denied.
526 the build: every fetched file held to its size and pin (a differing file refuses the build); the new archive is
    the reuse archive byte for byte plus the model's refs and snapshot members as build_assets writes them, hashed,
    placed on the file system under its digest once and never over a file holding that name with other bytes;
    the receipt holds digests and sizes only; the laptop's admission writes a manifest-only reuse bundle (no
    archive, `held_on: filesystem`, the members and the model added) and refuses a receipt of another
    declaration; the sealer takes the model only with the explicit declaration.
527 an archive held on the filesystem only, in the real controller against the fakes (D-739, Seckin 15:22): with
    the copy MATCHing the laptop-held SHA-256 it is used and hashed again on the instance before the workload;
    MISSING and a copy whose hash differs stop the run with no upload, no seed and no workload; an archive that
    fails the instance's own hash stops the run; no declared copy refuses before any instance exists.
528 the records and the laptop's admission: the asset build's launch record passes the runner's workload
    admission and is refused as a sealed bundle; its request is refused for a changed or extra file; a returned
    bundle whose archive is held on the filesystem is admitted without a laptop archive, and one claiming another
    archive than its reuse bundle is refused.

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes). No network, no
provider, no model: fake lookups and connections, fixture archives of a few bytes in temporary folders, and the
controller checks' own fake provider and transport.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import socket
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / 'tools'), str(ROOT / 'tools' / 'loop'), str(ROOT / 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import asset_build as ab  # noqa: E402

SHIPPED = ROOT / 'tools' / 'cloud_run' / 'asset_build_olmo2_labeller.json'


def _attempt(fn):
    try:
        fn()
        return 'built'
    except (RuntimeError, ValueError):
        return 'refused'


class Rec:
    def __init__(self):
        self.events = []

    def event(self, name, **fields):
        self.events.append(dict(fields, event=name))


# ---------------------------------------------------------------------------
# fixtures: a reuse archive and a declared model of a few bytes


FILES = {'config.json': b'{"model_type": "olmo2"}', 'README.md': b'---\nlicense: apache-2.0\n---\n',
         'model.safetensors': b'weights fixture ' * 64}


def _git_sha1(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def fixture(tmp):
    tmp = Path(tmp)
    base_tar = tmp / 'base' / 'assets.tar'
    base_tar.parent.mkdir(parents=True)
    members = {}
    with tarfile.open(base_tar, 'w', format=tarfile.PAX_FORMAT) as archive:
        for name, data in (('hf_cache/hub/models--x--y/refs/main', b'a' * 40), ('wheels/w.whl', b'wheel fixture')):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
            members[name] = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    files = {n: dict(bytes=len(d), **({'lfs_sha256': hashlib.sha256(d).hexdigest()} if n.endswith('.safetensors')
                                      else {'git_sha1': _git_sha1(d)})) for n, d in FILES.items()}
    declaration = dict(schema=ab.DECLARATION_SCHEMA, decision='D-736', purpose='fixture',
                       model=dict(model_id='allenai/OLMo-fixture', revision='b' * 40, files=files),
                       allowed_host_suffixes=['huggingface.co', 'hf.co'], base_assets_sha256=ab.sha(base_tar))
    return base_tar, members, declaration


def fake_download(contents=None):
    contents = dict(FILES, **(contents or {}))

    def download(model_id, filename, revision, cache_dir):
        path = Path(cache_dir) / revision / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents[filename])
        return path
    return download


# ---------------------------------------------------------------------------
# 525


def observe_declaration():
    with tempfile.TemporaryDirectory() as tmp:
        _base, _members, d = fixture(tmp)
        two = copy.deepcopy(d)
        two['models'] = [two['model']]
        nopin = copy.deepcopy(d)
        nopin['model']['files']['config.json'] = {'bytes': 10}
        bothpins = copy.deepcopy(d)
        bothpins['model']['files']['config.json']['lfs_sha256'] = '0' * 64
        short = copy.deepcopy(d)
        short['model']['revision'] = 'main'
        host = copy.deepcopy(d)
        host['allowed_host_suffixes'] = ['*']
        undecided = copy.deepcopy(d)
        undecided['decision'] = 'Seckin said so'
        return {'fixture': _attempt(lambda: ab.check_declaration(d)), 'shipped': _attempt(lambda: ab.load_declaration(SHIPPED)),
                'two_models': _attempt(lambda: ab.check_declaration(two)), 'no_pin': _attempt(lambda: ab.check_declaration(nopin)),
                'two_pins': _attempt(lambda: ab.check_declaration(bothpins)), 'branch': _attempt(lambda: ab.check_declaration(short)),
                'any_host': _attempt(lambda: ab.check_declaration(host)),
                'no_decision': _attempt(lambda: ab.check_declaration(undecided))}


def expected_declaration():
    return {'fixture': 'built', 'shipped': 'built', 'two_models': 'refused', 'no_pin': 'refused', 'two_pins': 'refused',
            'branch': 'refused', 'any_host': 'refused', 'no_decision': 'refused'}


def neutralise_declaration():
    return patch.object(ab, 'check_declaration', lambda value: value)


def observe_hub_only():
    looked = []

    def fake_lookup(host, *a, **k):
        looked.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.9.8.7', 443))]
    connected = []

    def fake_connect(sock, address):
        connected.append(address[0])
        return None
    rec = Rec()
    with patch.object(socket, 'getaddrinfo', fake_lookup), patch.object(socket.socket, 'connect', fake_connect), \
            patch.object(socket.socket, 'connect_ex', fake_connect):
        guard = ab.HubOnly(['huggingface.co', 'hf.co'], rec).install()
        try:
            out = {'hub': _attempt(lambda: socket.getaddrinfo('huggingface.co', 443)),
                   'cdn': _attempt(lambda: socket.getaddrinfo('cdn-lfs-us-1.hf.co', 443)),
                   'other': _attempt(lambda: socket.getaddrinfo('example.org', 443)),
                   'lookalike': _attempt(lambda: socket.getaddrinfo('huggingface.co.example.org', 443)),
                   'suffix_trick': _attempt(lambda: socket.getaddrinfo('evilhf.co', 443))}
            sock = socket.socket.__new__(socket.socket)
            out['to_looked_up'] = _attempt(lambda: socket.socket.connect(sock, ('10.9.8.7', 443)))
            out['to_other_address'] = _attempt(lambda: socket.socket.connect(sock, ('203.0.113.5', 443)))
        finally:
            guard.restore()
        out['restored'] = socket.getaddrinfo is fake_lookup
    out['refused_recorded'] = sum(e['event'] == 'network_refused' for e in rec.events)
    out['other_looked_up'] = 'example.org' in looked
    return out


def expected_hub_only():
    return {'hub': 'built', 'cdn': 'built', 'other': 'refused', 'lookalike': 'refused', 'suffix_trick': 'refused',
            'to_looked_up': 'built', 'to_other_address': 'refused', 'restored': True, 'refused_recorded': 4,
            'other_looked_up': False}


def neutralise_hub_only():
    return patch.object(ab, 'host_allowed', lambda host, suffixes: True)


def observe_no_xet():
    """The real hub_download against the installed huggingface_hub, its one network call replaced: at that call
    the hub must see xet off (the env switch and the 0.30.2 availability answer) and no token."""
    import huggingface_hub
    import huggingface_hub.file_download as fd
    from huggingface_hub.utils import _runtime
    seen = {}

    def fake(model_id, filename, revision, cache_dir, token):
        seen.update(xet_env=os.environ.get('HF_HUB_DISABLE_XET'), xet_available=fd.is_xet_available(),
                    token=token, offline=os.environ.get('HF_HUB_OFFLINE'))
        return 'path'
    import huggingface_hub.constants as constants
    keep = dict(os.environ)
    with patch.object(huggingface_hub, 'hf_hub_download', fake), \
            patch.object(fd, 'is_xet_available', fd.is_xet_available), \
            patch.object(constants, 'HF_HUB_OFFLINE', constants.HF_HUB_OFFLINE), \
            patch.object(constants, 'HF_HUB_DISABLE_XET', False, create=True), \
            patch.dict(_runtime._package_versions, dict(_runtime._package_versions, hf_xet='1.6.0')):
        fd.is_xet_available = lambda: True          # as on the instance, where hf-xet is installed
        try:
            ab.hub_download('a/b', 'config.json', 'c' * 40, tempfile.gettempdir())
        finally:
            os.environ.clear()
            os.environ.update(keep)
    return seen


def expected_no_xet():
    return {'xet_env': '1', 'xet_available': False, 'token': False, 'offline': '0'}


def neutralise_no_xet():
    return patch.object(ab, 'FETCH_ENV', {'HF_HUB_OFFLINE': '0'})


def observe_no_sendto():
    sent = []
    rec = Rec()
    with patch.object(socket.socket, 'sendto', lambda sock, data, *a: sent.append(a[-1]) or len(data)):
        guard = ab.HubOnly(['huggingface.co'], rec).install()
        try:
            sock = socket.socket.__new__(socket.socket)
            out = {'datagram_out': _attempt(lambda: socket.socket.sendto(sock, b'x', ('198.51.100.7', 53))),
                   'loopback': _attempt(lambda: socket.socket.sendto(sock, b'x', ('127.0.0.1', 9)))}
        finally:
            guard.restore()
    out['sent'] = [a[0] for a in sent]
    out['recorded'] = [e.get('network_kind') for e in rec.events if e['event'] == 'network_refused']
    return out


def expected_no_sendto():
    return {'datagram_out': 'refused', 'loopback': 'built', 'sent': ['127.0.0.1'], 'recorded': ['socket_sendto']}


def neutralise_no_sendto():
    return patch.object(ab.HubOnly, 'GUARDED', ('connect', 'connect_ex'))


# ---------------------------------------------------------------------------
# 526


def _build(tmp, download=None, mount=None, deny=None):
    base_tar, members, d = fixture(tmp)
    base = Path(tmp) / 'run'
    base.mkdir()
    (base / 'assets.tar').write_bytes(base_tar.read_bytes())
    ab.write(base / ab.DECLARATION_FILE, d)
    ab.write(base / 'execution_manifest.json', dict(assets_archive=dict(sha256=d['base_assets_sha256'])))
    mount = Path(mount or Path(tmp) / 'nfs')
    mount.mkdir(exist_ok=True)
    rec = Rec()
    order = []
    receipt = ab.build(base, base / 'evidence', rec, deny or (lambda r: order.append('denied')), mount,
                       download=download or fake_download())
    return receipt, members, d, base, mount, order


def observe_build():
    with tempfile.TemporaryDirectory() as tmp:
        receipt, members, d, base, mount, order = _build(tmp)
        placed = Path(receipt['filesystem']['path'])
        with tarfile.open(placed) as archive:
            names = archive.getnames()
            ref = archive.extractfile('hf_cache/hub/models--allenai--OLMo-fixture/refs/main').read()
        out = {'placed_name': placed.name == 'assets-%s.tar' % receipt['archive']['sha256'],
               'hash': ab.sha(placed) == receipt['archive']['sha256'],
               'base_first': open(placed, 'rb').read(512) == open(base / 'assets.tar', 'rb').read(512),
               'members': sorted(names) == sorted(set(members) | set(receipt['added_members'])),
               'ref_40': ref == b'b' * 40, 'denied_after_fetch': order == ['denied'],
               'receipt_digests_only': not any(isinstance(v, str) and 'weights fixture' in v
                                               for v in json.dumps(receipt).split('"'))}
        # placed once: a second build of the same bytes finds its own file; other bytes under that name refuse
        again = Path(tmp) / 'again'
        again.mkdir()
        r2, *_ = _build(again, mount=mount)
        out['second_build_finds_it'] = r2['filesystem'] == dict(path=str(placed), placed=False, already_there=True)
    with tempfile.TemporaryDirectory() as tmp:
        out['tampered_file'] = _attempt(lambda: _build(tmp, download=fake_download({'model.safetensors': b'x' * 1024})))
    with tempfile.TemporaryDirectory() as tmp:
        receipt, *_ = _build(tmp)
        digest = receipt['archive']['sha256']
        clash = Path(tmp) / 'clash'
        clash.mkdir()
        nfs = Path(tmp) / 'nfs2'
        nfs.mkdir()
        (nfs / ('assets-%s.tar' % digest)).write_bytes(b'other bytes')
        out['other_bytes_under_name'] = _attempt(lambda: _build(clash, mount=nfs))
        out['untouched'] = (nfs / ('assets-%s.tar' % digest)).read_bytes() == b'other bytes'
    return out


def expected_build():
    return {'placed_name': True, 'hash': True, 'base_first': True, 'members': True, 'ref_40': True,
            'denied_after_fetch': True, 'receipt_digests_only': True, 'second_build_finds_it': True,
            'tampered_file': 'refused', 'other_bytes_under_name': 'refused', 'untouched': True}


def neutralise_build():
    real = ab.fetch

    def unchecked(declaration, staging, download=ab.hub_download):
        model = declaration['model']
        paths, entries = {}, {}
        for name in sorted(model['files']):
            path = Path(download(model['model_id'], name, model['revision'], Path(staging)))
            paths[name], entries[name] = path, dict(sha256=ab.sha(path), bytes=path.stat().st_size)
        return paths, entries
    del real
    return patch.object(ab, 'fetch', unchecked)


def _reuse_bundle(folder, base_tar, members):
    folder.mkdir(parents=True)
    ab.write(folder / 'execution_manifest.json', dict(
        assets_archive=dict(filename='assets.tar', sha256=ab.sha(base_tar), bytes=base_tar.stat().st_size, members=members),
        models=[dict(model_id='x/y', revision='a' * 40, files={})], environment={'HF_HUB_OFFLINE': '1'}))
    (folder / 'install.lock').write_text('x==1 --hash=sha256:' + '0' * 64 + '\n', encoding='utf-8')
    return folder


def observe_admit():
    import prepare_ordinary_final_run as prep
    with tempfile.TemporaryDirectory() as tmp:
        receipt, members, d, base, mount, _ = _build(tmp)
        base_tar = Path(tmp) / 'base' / 'assets.tar'
        reuse = _reuse_bundle(Path(tmp) / 'reuse', base_tar, members)
        decl = base / ab.DECLARATION_FILE
        # Seckin 16:11: the admission works on the receipt and the hashes alone; no archive is on the laptop side.
        placed = Path(receipt['filesystem']['path'])
        placed.rename(placed.with_name('moved_away.bin'))
        base_tar.rename(base_tar.with_name('moved_away.bin'))
        manifest = ab.admit(receipt, reuse, decl, Path(tmp) / 'held_reuse')
        held = ab.read(Path(tmp) / 'held_reuse' / ab.HELD_MANIFEST)
        local = [(h['kind'], h['path'] == receipt['filesystem']['path'], h['bytes'] == receipt['archive']['bytes'],
                  h['sha256'] == receipt['archive']['sha256']) for h in held['held']]
        other = copy.deepcopy(d)
        other['purpose'] = 'another declaration'
        ab.write(Path(tmp) / 'other.json', other)
        with_flag = prep.sealed_candidates(Path(tmp) / 'no_candidates.json', decl)
        without = prep.sealed_candidates(Path(tmp) / 'no_candidates.json', None)
        return {'no_archive': not (Path(tmp) / 'held_reuse' / 'assets.tar').exists(),
                'held_on': manifest['assets_archive']['held_on'], 'digest': manifest['assets_archive']['sha256'] == receipt['archive']['sha256'],
                'members': manifest['assets_archive']['members'] == dict(members, **receipt['added_members']),
                'model_added': [m['model_id'] for m in manifest['models']] == ['x/y', 'allenai/OLMo-fixture'],
                'other_declaration': _attempt(lambda: ab.admit(receipt, reuse, Path(tmp) / 'other.json', Path(tmp) / 'o')),
                'sealer_with_flag': sorted(with_flag), 'sealer_without': sorted(without),
                'local_manifest': local, 'brought_back': held['brought_back']}


def expected_admit():
    return {'no_archive': True, 'held_on': 'filesystem', 'digest': True, 'members': True, 'model_added': True,
            'other_declaration': 'refused', 'sealer_with_flag': ['allenai/OLMo-fixture'], 'sealer_without': [],
            'local_manifest': [('asset_archive', True, True, True)],
            'brought_back': ['asset_build_receipt.json', 'execution_manifest.json', 'install.lock']}


def neutralise_admit():
    return patch.object(ab, 'receipt_refusal', lambda receipt, reuse, declaration_path: None)


# ---------------------------------------------------------------------------
# 527: the real controller against the controller checks' fakes


def _held_case(name):
    import ordinary_final_controller_checks as occ

    class Held(occ.ControllerChecks):
        def make_held(self):
            digest = self.assets_digest()
            manifest = occ.read(self.base / 'execution_manifest.json')
            self.remanifest(assets_archive=dict(manifest['assets_archive'], held_on='filesystem'))
            occ.write(self.base / 'assets_transfer_archive.json', dict(
                path=None, sha256=digest, bytes=(self.root / 'assets.tar').stat().st_size,
                manifest_sha256=occ.sha(self.base / 'execution_manifest.json')))
            return digest

        def run_case(self, case):
            # 'ordinary': the same copy MISSING on a bundle not held on the filesystem keeps the v9 upload and the
            # run goes on (nothing else in the controller may read it as held).
            digest = self.assets_digest() if case == 'ordinary' else self.make_held()
            if case != 'undeclared':
                self.declare_copy()
            mount = {'match': dict(present=True, files={digest: digest}),
                     'integrity': dict(present=True, files={digest: digest}),
                     'missing': dict(present=True, files={}), 'mismatch': dict(present=True, files={digest: 'e' * 64}),
                     'undeclared': dict(present=True, files={digest: digest}),
                     'ordinary': dict(present=True, files={})}[case]
            polls = {'archive_integrity': [1]} if case == 'integrity' else None
            try:
                transport, _console, failure = self.execute(mount=mount, polls=polls)
            except RuntimeError as exc:      # refused before any instance exists
                transport, failure = None, dict(message=str(exc))
            started = getattr(transport, 'started', [])
            return {'failed': failure is not None,
                    'reason': (failure or {}).get('message', '')[:60],
                    'uploaded': bool(getattr(transport, 'assets_uploaded', False)),
                    'from_copy': bool(getattr(transport, 'assets_from_copy', False)),
                    'seeded': 'asset_copy_seed' in started, 'workload': 'ordinary_workload' in started,
                    'integrity_checked': 'archive_integrity' in started,
                    'launched': bool((occ.FakeProvider.state or {}).get('launches'))}

        def runTest(self):
            pass
    case = Held()
    case.setUp()
    try:
        return case.run_case(name)
    finally:
        case.doCleanups()


def observe_held():
    with contextlib.redirect_stdout(_sink()), contextlib.redirect_stderr(_sink()):
        out = {c: _held_case(c) for c in ('match', 'missing', 'mismatch', 'integrity', 'undeclared', 'ordinary')}
    ordinary = out.pop('ordinary')
    return {c: {k: v for k, v in r.items() if k != 'reason'} for c, r in out.items()} | {
        'ordinary': {k: ordinary[k] for k in ('failed', 'uploaded', 'from_copy', 'workload')},
        'missing_reason': out['missing']['reason'].startswith('An archive held on the filesystem only'),
        'mismatch_reason': out['mismatch']['reason'].startswith('An archive held on the filesystem only'),
        'undeclared_reason': out['undeclared']['reason'].startswith('An archive held on the filesystem only')}


def expected_held():
    stop = dict(failed=True, uploaded=False, from_copy=False, seeded=False, workload=False)
    return {'match': dict(failed=False, uploaded=False, from_copy=True, seeded=False, workload=True,
                          integrity_checked=True, launched=True),
            'missing': dict(stop, integrity_checked=False, launched=True),
            'mismatch': dict(stop, integrity_checked=False, launched=True),
            'integrity': dict(stop, from_copy=True, integrity_checked=True, launched=True),
            'undeclared': dict(stop, integrity_checked=False, launched=False),
            'ordinary': dict(failed=False, uploaded=True, from_copy=False, workload=True),
            'missing_reason': True, 'mismatch_reason': True, 'undeclared_reason': True}


def neutralise_held():
    """Only the held branch of record_upload_refusal removed: a held archive's unused copy is then not refused
    there, and the run goes on toward an upload of an archive the laptop does not have."""
    import ordinary_final_cloud as cloud
    real = cloud.record_upload_refusal
    return patch.object(cloud, 'record_upload_refusal', lambda record, used, state, held=False: real(record, used, state))


def observe_bound():
    """tools/asset_build.py is a controller file: sealed with the others, a byte changed after sealing refuses the
    launch before any provider call (the real controller against the controller checks' fakes)."""
    import ordinary_final_controller_checks as occ
    import prepare_ordinary_final_run as sealer
    out = {}
    for changed in (False, True):
        class Bound(occ.ControllerChecks):
            def runTest(self):
                pass
        case = Bound()
        case.setUp()
        try:
            case.seal_controls(sealer.CONTROL_FILES)
            target = case.root / 'tools' / 'asset_build.py'
            if changed and target.is_file():
                target.write_bytes(target.read_bytes() + b'\n# changed after sealing\n')
            try:
                _t, _c, failure = case.execute()
                out[changed] = 'launched' if failure is None else 'failed'
            except RuntimeError as exc:
                out[changed] = ('refused before any instance' if 'Controller source changed' in str(exc)
                                and occ.FakeProvider.state is None else 'raised')
        finally:
            case.doCleanups()
    return {'listed': 'tools/asset_build.py' in sealer.CONTROL_FILES, 'sealed': out[False], 'changed': out[True]}


def expected_bound():
    return {'listed': True, 'sealed': 'launched', 'changed': 'refused before any instance'}


def neutralise_bound():
    import prepare_ordinary_final_run as sealer
    return patch.object(sealer, 'CONTROL_FILES', tuple(n for n in sealer.CONTROL_FILES if n != 'tools/asset_build.py'))


# ---------------------------------------------------------------------------
# 528


def _request_folder(tmp, d):
    folder = Path(tmp) / 'request'
    folder.mkdir()
    ab.write(folder / ab.DECLARATION_FILE, d)
    ab.write(folder / ab.REUSE_MANIFEST, dict(
        assets_archive=dict(filename='assets.tar', sha256=d['base_assets_sha256'], bytes=10, members={}),
        models=[], environment={'HF_HUB_OFFLINE': '1'}))
    (folder / 'install.lock').write_text('x\n', encoding='utf-8')
    for name in ab.SUPPORT:
        (folder / name).write_text('# fixture ' + name + '\n', encoding='utf-8')
    control = Path(tmp) / 'controller'
    (control / 'tools').mkdir(parents=True)
    (control / 'tools' / 'c.py').write_text('# controller fixture\n', encoding='utf-8')
    request = dict(schema=ab.REQUEST_SCHEMA, commit='c' * 40,
                   job=dict(read_copies={}, taken_epoch=1.0, attestation=dict(refusals=[]),
                            declaration_sha256=ab.sha(folder / ab.DECLARATION_FILE)),
                   asset_build=dict(decision='D-736', model_id=d['model']['model_id'], revision=d['model']['revision'],
                                    base_assets_sha256=d['base_assets_sha256']),
                   budget=dict(instance_candidates=[dict(type='gpu_1x_a10')], hard_ceiling_usd=2.0, soft_budget_usd=1.0,
                               per_run_cap_usd=2.0),
                   image='img', wheelhouse={}, local_control_hashes={'tools/c.py': ab.sha(control / 'tools' / 'c.py')},
                   files={p.name: ab.sha(p) for p in sorted(folder.iterdir())})
    ab.write(folder / ab.REQUEST_FILE, request)
    return folder, control


def observe_records():
    import ordinary_final_run as run
    import seal_route
    with tempfile.TemporaryDirectory() as tmp:
        _b, members, d = fixture(tmp)
        folder, control = _request_folder(tmp, d)
        out = {'request_ok': ab.request_error(folder, control) is None,
               'is_request': ab.is_request(folder),
               'routed_by_seal_route': seal_route.request_error(folder, control) is None}
        manifest, seal = ab.launch_record(folder, Path(tmp) / 'record', control)
        out['admitted_by_runner'] = _attempt(lambda: run.admit_workload(manifest, seal, Path(tmp) / 'record'))
        out['refused_as_bundle'] = _attempt(lambda: seal_route.refuse_launch_record(manifest, 'a --bundle'))
        out['record_named'] = seal_route.record_error(Path(tmp) / 'record', folder) is None
        (folder / 'assets.tar').write_bytes(b'not allowed')
        out['archive_in_request'] = ab.request_error(folder, control) is not None
    with tempfile.TemporaryDirectory() as tmp:
        _b, members, d = fixture(tmp)
        folder, control = _request_folder(tmp, d)
        (folder / 'asset_build.py').write_text('# changed\n', encoding='utf-8')
        out['changed_file'] = ab.request_error(folder, control) is not None
    # a returned bundle held on the filesystem: admitted with no laptop archive; another archive refused
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        reuse = tmp / 'reuse'
        reuse.mkdir()
        held = dict(filename='assets.tar', sha256='d' * 64, bytes=36, members={'m': dict(sha256='e' * 64, bytes=1)},
                    held_on='filesystem')
        ab.write(reuse / 'execution_manifest.json', dict(assets_archive=held))
        bundle = tmp / 'bundle'
        bundle.mkdir()
        ab.write(bundle / 'execution_manifest.json', dict(assets_archive=dict(held, reused_from='x'), source_archive_sha256='f' * 64))
        ab.write(bundle / seal_route.PROJECT_IN_STORE, dict(sha256='f' * 64, store_name='project-f.tar.gz'))
        row = seal_route.admit_returned(bundle, reuse, link=lambda a, b: (_ for _ in ()).throw(AssertionError('no link')))
        out['held_admitted'] = (row['assets_linked'], row.get('assets_held_on'), (bundle / 'assets.tar').exists())
        other = tmp / 'bundle2'
        other.mkdir()
        ab.write(other / 'execution_manifest.json', dict(assets_archive=dict(held, sha256='0' * 64), source_archive_sha256='f' * 64))
        ab.write(other / seal_route.PROJECT_IN_STORE, dict(sha256='f' * 64, store_name='p'))
        out['other_archive'] = _attempt(lambda: seal_route.admit_returned(other, reuse))
    return out


def expected_records():
    return {'request_ok': True, 'is_request': True, 'routed_by_seal_route': True, 'admitted_by_runner': 'built',
            'refused_as_bundle': 'refused', 'record_named': True, 'archive_in_request': True, 'changed_file': True,
            'held_admitted': (False, 'filesystem', False), 'other_archive': 'refused'}


def observe_request_block():
    """Every field of the request's asset_build block is held to its declaration: another revision, another reuse
    archive or another decision beside the same model id is refused."""
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        _b, members, d = fixture(tmp)
        folder, control = _request_folder(tmp, d)
        request = ab.read(folder / ab.REQUEST_FILE)
        out['as_written'] = ab.request_error(folder, control) is None
        for field, value in (('revision', 'f' * 40), ('base_assets_sha256', '0' * 64), ('decision', 'D-999')):
            ab.write(folder / ab.REQUEST_FILE, dict(request, asset_build=dict(request['asset_build'], **{field: value})))
            out[field] = ab.request_error(folder, control)
        ab.write(folder / ab.REQUEST_FILE, request)
    return out


def expected_request_block():
    refused = 'The asset-build request names another declaration'
    return {'as_written': True, 'revision': refused, 'base_assets_sha256': refused, 'decision': refused}


def neutralise_request_block():
    return patch.object(ab, 'REQUEST_BLOCK_FIELDS', ('model_id',))


def observe_payload():
    """The controller's extract command, run by a real tar on a small archive shaped as the reuse archive: an asset
    build unpacks the wheels alone, a seal request everything."""
    import shutil
    import subprocess
    import ordinary_final_cloud as cloud
    from cloud_run_common import no_window
    tar_exe = shutil.which('tar')
    if tar_exe is None:
        return 'no tar on this machine'
    out = {}
    for kind in (cloud.ASSET_BUILD_KIND, cloud.LAUNCH_RECORD_KIND):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with tarfile.open(tmp / 'assets.tar', 'w', format=tarfile.PAX_FORMAT) as tar:
                for name in ('hf_cache/hub/models--a--b/blobs/x', 'wheels/w-1.0-py3-none-any.whl'):
                    data = b'fixture ' + name.encode()
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
            command = cloud.payload_extract_command({'kind': kind}).split()
            done = subprocess.run([tar_exe] + command[1:], cwd=str(tmp), capture_output=True,
                                  creationflags=no_window())
            out[kind] = (done.returncode, sorted(p.relative_to(tmp).as_posix() for p in tmp.rglob('*')
                                                 if p.is_file() and p.name != 'assets.tar'))
    return out


def expected_payload():
    import ordinary_final_cloud as cloud
    return {cloud.ASSET_BUILD_KIND: (0, ['wheels/w-1.0-py3-none-any.whl']),
            cloud.LAUNCH_RECORD_KIND: (0, ['hf_cache/hub/models--a--b/blobs/x', 'wheels/w-1.0-py3-none-any.whl'])}


def neutralise_payload():
    import ordinary_final_cloud as cloud
    return patch.object(cloud, 'payload_extract_command', lambda manifest: 'tar -xf assets.tar')


def observe_request_cli():
    """The `request` command line as launch.py types it (18 Nov 17:16: it passed a list where request_budget splits
    a comma string): the budget reaches write_request with the declared types as a list and the cap rule's fields."""
    seen = {}

    def capture(out, source, declaration, reuse, inputs, budget):
        seen.update(types=budget['instance_types'], uncompared=budget['uncompared'], minutes=budget['forecast_minutes'])
        return {'asset_build': {'model_id': 'm'}, 'files': {}, 'budget': {'per_run_cap_usd': 1.0}}
    with patch.object(ab, 'write_request', capture), contextlib.redirect_stdout(_sink()):
        code = _caught(lambda: ab.main(['request', '--source', 'HEAD', '--declaration', 'd', '--reuse', 'r', '--inputs', 'i',
                                        '--ledger', 'l', '--out', 'o', '--forecast-minutes', '60',
                                        '--storage-forecast-usd', '0.5', '--instance-types', 'gpu_1x_a10,gpu_1x_a100',
                                        '--uncompared']))
    return {'exit': code, **seen}


def expected_request_cli():
    return {'exit': 0, 'types': ['gpu_1x_a10', 'gpu_1x_a100'], 'uncompared': True, 'minutes': 60.0}


def neutralise_request_cli():
    import seal_route_driver
    real = seal_route_driver.request_budget
    return patch.object(seal_route_driver, 'request_budget',
                        lambda ledgers, minutes, storage, types=None, uncompared=False: real(ledgers, minutes, storage, None,
                                                                                            uncompared))


def observe_declaration_travels():
    """18 Nov 18:01, the second asset build: the runner on the instance read asset_copy_declaration.json for the
    file system's mount, and the controller had not sent it (a record's support files only reach the instance;
    the declaration was written after them). Reproduced here: the real launch record, the files the real controller
    sends (transferred_support), copied alone into an empty folder as the instance holds them, then the runner's
    own admission and its read of the mount there."""
    import ordinary_final_cloud as cloud
    import ordinary_final_run as run
    with tempfile.TemporaryDirectory() as tmp:
        _b, _members, d = fixture(tmp)
        folder, control = _request_folder(tmp, d)
        record = Path(tmp) / 'record'
        manifest, seal = ab.launch_record(folder, record, control)
        ab.write(record / 'operator_authorization.json', {})
        instance = Path(tmp) / 'instance'
        instance.mkdir()
        sent = cloud.transferred_support(manifest, True)
        for name in sent:
            (instance / name).write_bytes((record / name).read_bytes())
        on_instance = run.read(instance / 'execution_manifest.json')
        held = all(run.sha(instance / n) == dg for n, dg in on_instance['support_files'].items())
        mount = _caught(lambda: run.read(instance / ab.COPY_DECLARATION)['mount'])
        return {'sent': ab.COPY_DECLARATION in sent, 'mount_on_instance': mount,
                'support_held': held, 'seal_holds': run.read(instance / 'seal.json')['execution_manifest_sha256']
                == run.sha(instance / 'execution_manifest.json'),
                'admitted_by_runner': _attempt(lambda: run.admit_workload(on_instance, run.read(instance / 'seal.json'),
                                                                         instance))}


def expected_declaration_travels():
    import declare_asset_copy
    return {'sent': True, 'mount_on_instance': declare_asset_copy.LOOP_MOUNT.rstrip('/'), 'support_held': True,
            'seal_holds': True, 'admitted_by_runner': 'built'}


def neutralise_declaration_travels():
    """As built on 18 Nov until the fix: the declaration written beside the record and never made a support file."""
    return patch.object(ab, 'copy_declaration_sealed', lambda out, manifest, seal: (manifest, seal))


def neutralise_records():
    import seal_route
    return patch.object(seal_route, 'RECORD_KINDS', (seal_route.LAUNCH_RECORD_KIND,))


PROOFS = {'525': ('declaration', 'hub_only', 'no_xet', 'no_sendto'), '526': ('build', 'admit'), '527': ('held', 'bound'), '528': ('records', 'request_block', 'payload', 'request_cli', 'declaration_travels')}
WHAT = {'525': 'one declared model and the hub hosts alone, during the fetch only',
        '526': 'the archive built from the reuse archive plus the pinned model, placed once under its digest, admitted '
               'as a manifest-only reuse bundle',
        '527': 'an archive held on the filesystem only: MATCH used and hashed again, MISSING or a differing hash stops',
        '528': 'the asset build record admitted by the runner, never a bundle; held bundles admitted with no archive'}


def _sink():
    """A text stream with a byte buffer (the controller writes some lines through sys.stdout.buffer)."""
    return io.TextIOWrapper(io.BytesIO(), encoding='utf-8')


def _caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a neutralised proof may raise; that is its failure
        return 'raised %s: %s' % (type(exc).__name__, str(exc)[:120])


def run_group(number):
    done = []
    for name in PROOFS[number]:
        space = globals()
        observe, expected, neutralise = space['observe_' + name], space['expected_' + name], space['neutralise_' + name]
        try:
            with contextlib.redirect_stderr(_sink()):
                first = observe()
                with neutralise():
                    broken = _caught(observe)
                again = observe()
        except Exception as exc:
            return 'FAIL', '%s: %s %s' % (name, type(exc).__name__, str(exc)[:300])
        if first != expected():
            return 'FAIL', '%s as built: %s' % (name, str(first)[:700])
        if broken == expected():
            return 'FAIL', '%s still passes when neutralised' % name
        if again != expected():
            return 'FAIL', '%s after restore: %s' % (name, str(again)[:400])
        done.append(name)
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass, no network: %s (%s)' % (
        len(done), WHAT[number], ', '.join(done))


if __name__ == '__main__':
    results = [(g,) + run_group(g) for g in (sys.argv[1:] or sorted(PROOFS))]
    for g, status, detail in results:
        print(g, status, detail)
    raise SystemExit(0 if all(s == 'PASS' for _g, s, _d in results) else 1)
