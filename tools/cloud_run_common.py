"""Offline sealing and safe metadata primitives; no provider/model imports."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import tarfile
from pathlib import Path, PurePosixPath


class InvalidPreparation(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise InvalidPreparation(reason)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def write_json(path, value):
    Path(path).write_bytes(json_bytes(value))


# Report locations only. Prefix fragments in scanner source are not secrets.
KEY = re.compile(r'sk-(?:ant-|proj-)[A-Za-z0-9_-]{12,}|sk-[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{35}')
AUTH = re.compile(r'''["']?(?:\w*_)?(?:api_key|access_token|jupyter_token|notebook_token|secret|token|password|credential)["']?\s*[:=]\s*["']([^"'\r\n]+)["']''', re.I)
URL_SECRET = re.compile(r'https?://[^\s"\x27]*[?&](?:token|key|signature|x-amz-signature|access_token)=', re.I)
PLACEHOLDERS = {'TEST_CREDENTIAL_PLACEHOLDER', 'YOUR_KEY_HERE', 'YOUR_API_KEY_HERE', '<redacted>', '[REDACTED]', ''}


def credential_locations(data, name):
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return []
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        match = AUTH.search(line)
        value = match.group(1) if match else ''
        # A literal authentication value is suspect; identifiers/hashes only
        # qualify for exclusion when NOT assigned to an authentication field.
        assigned = bool(value and value not in PLACEHOLDERS and
                        not value.lower().startswith(('your_', 'your-', '<', '${')) and
                        not (re.fullmatch(r'[A-Z_]+', value) and '_YOUR_' in value) and
                        re.fullmatch(r'[A-Za-z0-9_./+=:-]{16,}', value))
        if KEY.search(line) or URL_SECRET.search(line) or assigned or ('-----BEGIN ' + 'PRIVATE KEY-----') in line or ('-----BEGIN ' + 'OPENSSH PRIVATE KEY-----') in line:
            hits.append({'file': name, 'line': number})
    return hits


TEXT_FIELDS = {'instance_id', 'name', 'type', 'gpu_type', 'region', 'status', 'boot_timestamp'}
NUMBER_FIELDS = {'gpu_count', 'hourly_rate', 'cpu', 'ram_gib', 'storage_gib'}
METADATA_FIELDS = TEXT_FIELDS | NUMBER_FIELDS | {'public_ip'}


def safe_metadata(raw):
    """Only flat, typed, bounded fields survive. Never retain raw responses."""
    require(isinstance(raw, dict), 'metadata must be an object')
    result = {}
    for key in sorted(METADATA_FIELDS & raw.keys()):
        value = raw[key]
        if key in NUMBER_FIELDS:
            require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                    'invalid numeric metadata: ' + key)
        elif key == 'public_ip':
            require(isinstance(value, str), 'invalid public IP')
            ipaddress.ip_address(value)
        else:
            require(isinstance(value, str) and len(value) <= 128 and
                    re.fullmatch(r'[A-Za-z0-9 _.:+(),-]+', value), 'invalid metadata: ' + key)
            require(not KEY.search(value), 'credential in metadata: ' + key)
            require(not re.search(r'token|secret|password|credential|cookie|signature', value, re.I),
                    'credential marker in metadata: ' + key)
        result[key] = value
    return result


def provider_instance(raw):
    """Project the provider shape before it crosses the transport boundary."""
    try:
        kind = raw.get('instance_type', {})
        specs = kind.get('specs', {})
        value = dict(instance_id=raw['id'], name=raw.get('name'), type=kind.get('name'),
            gpu_type=kind.get('gpu_description'), gpu_count=specs.get('gpus'),
            region=raw.get('region', {}).get('name'), status=raw.get('status'),
            public_ip=raw.get('ip'), hourly_rate=kind.get('price_cents_per_hour', 0)/100,
            cpu=specs.get('vcpus'), ram_gib=specs.get('memory_gib'), storage_gib=specs.get('storage_gib'))
        return safe_metadata({k:v for k,v in value.items() if v is not None})
    except Exception:
        raise InvalidPreparation('invalid provider instance metadata') from None


def safe_name(name):
    path = PurePosixPath(name)
    return (bool(name) and not path.is_absolute() and '\\' not in name and ':' not in name
            and all(part not in ('', '.', '..') for part in name.split('/')))


def verify_files(root, manifest, exact=True):
    root = Path(root)
    for name, expected in manifest.items():
        require(safe_name(name), 'unsafe manifest path')
        path = root / name
        require(path.resolve().is_relative_to(root.resolve()), 'member escapes bundle root')
        require(not path.is_symlink() and path.is_file(), 'missing/semlink bundle member: ' + name)
        require(digest(path) == expected, 'hash mismatch: ' + name)
    if exact:
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
        require(actual == set(manifest), 'unexpected bundle members')


def verify_bundle(root):
    root = Path(root)
    ready = json.loads((root / 'READY_TO_PROVISION.json').read_text())
    require(ready.get('ready_to_provision') is True, 'bundle not ready')
    seal_path = root / 'bundle_manifest.json'
    require(digest(seal_path) == ready['bundle_manifest_sha256'], 'seal changed')
    manifest = json.loads(seal_path.read_text())
    require(all(safe_name(k) for k in manifest), 'unsafe bundle member')
    verify_files(root, manifest, exact=False)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    require(actual == set(manifest) | {'bundle_manifest.json', 'READY_TO_PROVISION.json'},
            'unsealed bundle members')
    return ready


def extract_source(archive, destination, expected):
    """Reject traversal, links, duplicates, extras and hash drift before use."""
    destination = Path(destination)
    require(not destination.is_symlink() and (not destination.exists() or not any(destination.iterdir())),
            'source destination must be new or empty')
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        require(len(names) == len(set(names)) and set(names) == set(expected), 'archive inventory mismatch')
        for m in members:
            require(m.isfile() and safe_name(m.name), 'unsafe source archive')
            data = tar.extractfile(m).read()
            require(hashlib.sha256(data).hexdigest() == expected[m.name], 'source hash mismatch: ' + m.name)
        for m in members:
            path = Path(destination) / m.name
            path.parent.mkdir(parents=True, exist_ok=True)
            require(not path.exists(), 'source extraction would overwrite')
            path.write_bytes(tar.extractfile(m).read())


def budget_deadlines(hourly_rate, running_epoch, reserve_seconds=120):
    require(type(hourly_rate) in (int, float) and math.isfinite(hourly_rate) and hourly_rate > 0,
            'positive operator hourly rate required')
    require(math.isfinite(running_epoch) and running_epoch > 0, 'billing start required')
    require(0 < reserve_seconds < 5 / hourly_rate * 3600, 'invalid termination reserve')
    return {'soft_epoch': running_epoch + 5 / hourly_rate * 3600,
            'terminate_epoch': running_epoch + 10 / hourly_rate * 3600 - reserve_seconds,
            'ceiling_epoch': running_epoch + 10 / hourly_rate * 3600}
