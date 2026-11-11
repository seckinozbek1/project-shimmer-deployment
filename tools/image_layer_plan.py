"""The ready-to-run image's layers on the laptop side (D-S108 item 2, D-S109 items 2 and 3): what a
sealed bundle needs, what the filesystem is recorded to hold, and the env build record a launch
brought back. It never calls a provider and never writes to the filesystem; the filesystem is
reachable only from an instance, so it is updated at the start of the first launch that needs it.

  plan --bundle B [--record R]       the bundle's layers against the record: present, to build
  record --run RUN [--record R]      append what one launch's receipts say the filesystem holds
  env-manifest --run RUN --out F     the env layer's build record, for the sealer's --image-env-manifest

The record (default docs/loop/private/image_layers.jsonl) is written only from instance receipts:
a layer is recorded present only when a check in that launch read it MATCH or UNSEALED there.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/loop/private/image_layers.jsonl'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def rows(record):
    record = Path(record)
    if not record.is_file():
        return []
    return [json.loads(line) for line in record.read_text(encoding='utf8').splitlines() if line.strip()]


def held(record):
    """{key: latest row} for each layer key the record names, the latest row winning."""
    out = {}
    for row in rows(record):
        out[row['key']] = row
    return out


def plan(bundle, record=RECORD):
    """Each layer the bundle seals, with whether the record holds it at that key."""
    manifest = read(Path(bundle) / 'execution_manifest.json')
    block = manifest.get('layers')
    if not block:
        return dict(layers=None, reason='the bundle seals no image layers')
    known = held(record)
    out = []
    for name, key in sorted(block['keys'].items()):
        row = known.get(key)
        state = row['state'] if row else None
        out.append(dict(name=name, key=key, recorded=state,
                        action='none' if state == 'MATCH' else 'seal its build record' if state == 'UNSEALED'
                        else 'not used: suspect, for the lead' if state == 'MISMATCH'
                        else 'built at the first launch that needs it'))
    return dict(layers=out, env_sealed=block['env_sealed'])


def record_run(run, record=RECORD, now=None):
    """Append one row per layer the launch's last check read, from its receipt alone."""
    run = Path(run)
    receipt = read(run / 'image_receipt.json')
    manifest = read(run / 'execution_manifest.json')
    states = receipt.get('recheck') or receipt.get('first_check')
    if not states:
        return []
    when = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now if now is not None else time.time()))
    new = [dict(key=manifest['layers']['keys'][name], name=name, state=state, time_utc=when,
                run=run.as_posix(), source='image_receipt.json')
           for name, state in sorted(states.items()) if state in ('MATCH', 'UNSEALED', 'MISMATCH')]
    Path(record).parent.mkdir(parents=True, exist_ok=True)
    with Path(record).open('a', encoding='utf8') as stream:
        for row in new:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    return new


def canonical(value):
    """image_layers.canonical: the bytes a manifest digest is taken over."""
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf8')


def full_build_record(run, summary):
    """The image tool's full build record from the run's collected_evidence.tar.gz (the evidence pack
    takes every .json file of the run root), read as bytes, never extracted, at the summary's digest."""
    name, digest = summary.get('record'), summary.get('record_sha256')
    if not name or not digest:
        raise SystemExit('The build summary names no record')
    archive = Path(run) / 'collected_evidence.tar.gz'
    if not archive.is_file():
        raise SystemExit('No collected evidence in ' + str(run))
    with tarfile.open(archive, 'r:gz') as tar:
        try:
            member = tar.getmember(name)
        except KeyError:
            raise SystemExit('The collected evidence holds no ' + name) from None
        stream = tar.extractfile(member) if member.isfile() else None
        if stream is None:
            raise SystemExit(name + ' in the collected evidence is not a file')
        data = stream.read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise SystemExit(name + ' in the collected evidence is not the record the summary names')
    return json.loads(data.decode('utf8'))


def env_manifest(run, out):
    """The env build record a launch brought back, written for the sealer. The controller's
    image_build.json holds the tool's summary (no manifest: the full record is megabytes, and the
    phase's output is read back over a pipe); the full record is the tool's own file in the run root,
    read from the session's collected evidence and accepted only at the digest the summary names, its
    env manifest only at the manifest digest the summary names. A summary with no record digest (a
    controller before 9c4478b1 saved the whole record) or no manifest digest for the env record is
    refused, never read some other way."""
    summary = read(Path(run) / 'image_build.json')['result']
    if not isinstance(summary, dict) or not summary.get('record_sha256'):
        raise SystemExit('The build summary in ' + str(run) + ' names no record digest')
    if any(r.get('manifest') for r in summary.get('records') or []):
        raise SystemExit('The build summary in ' + str(run) + ' carries a manifest: not a summary')
    built = full_build_record(run, summary)['records']
    env = [r for r in built if r.get('manifest')]
    if len(env) != 1:
        raise SystemExit('No single env build record in ' + str(run))
    manifest = env[0]['manifest']
    named = [r.get('manifest_sha256') for r in summary['records'] if r.get('name') == env[0].get('name')]
    if len(named) != 1 or not named[0]:
        raise SystemExit('The build summary names no manifest digest for ' + str(env[0].get('name')))
    if named[0] != hashlib.sha256(canonical(manifest)).hexdigest():
        raise SystemExit('The env manifest is not the one the build summary names')
    Path(out).write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf8')
    return dict(key=manifest['key'], files=len(manifest['files']), symlinks=len(manifest['symlinks']),
                bytes=sum(e['bytes'] for e in manifest['files'].values()),
                sha256=hashlib.sha256(Path(out).read_bytes()).hexdigest())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--record', type=Path, default=RECORD)
    p = sub.add_parser('record')
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--record', type=Path, default=RECORD)
    p = sub.add_parser('env-manifest')
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'plan':
        result = plan(args.bundle, args.record)
    elif args.command == 'record':
        result = record_run(args.run, args.record)
    else:
        result = env_manifest(args.run, args.out)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
