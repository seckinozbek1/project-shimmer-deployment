"""The persistent Lambda working store (standing order 99, D-703 item 4): a DRY RUN plan only.

Order 99 says the working data lives on the persistent Lambda file system (`shimmer-filesystem`). This tool
plans that move and prices it; it never launches, copies, uploads or deletes anything, and it has no
execute switch. It reads `config/working_store.json` and walks the declared laptop roots of the main
checkout (today `external/`) with the backup coverage's own walker (`backup_coverage.walk`: never through a
link, hard links counted once). Each file is placed in one of three classes:

  stays local  a declared rule keeps it on the laptop: a name holding `answer_key` (matched by name, never
               opened), role B's held-out items, the scorer's keys, credential-like names (D-676 item 3,
               BACKUP-NEVER-LAPSE-A). These are never in any upload line, whatever else is declared.
  on the store an asset archive whose recorded digest (the sibling `asset_verification.json`) is one the
               file system already holds (ASSET-COPY-A): every us-east-1 launch reads it there.
  candidate    everything else: what a move would send.

Two steps are priced with `tools/loop/step_cost.py` (prices from the provider inventory and the storage
record, never typed in), each with two figures:
  move         one launch with the file system attached that receives every candidate part. Without the
               saving measures it would send the on-store archives again as well; with asset_copy it sends the
               candidates only. Storage is the candidates' GiB for `hold_hours`.
  per part     for each part in `lambda_reads` (a part Lambda jobs read again and again): without, the part
               is sent with every launch that reads it; with warm_file_system, it is read from the store and
               held there (its storage added).

It prints the commands a move would run (one `tar | ssh` per part into `<mount>/<store_dir>/<part>.tar` under
a `.partial` name, then `mv -n`), as text only; running them needs a guarded launch in the manner of
`tools/loop/fs_listing.py`, which does not exist (OPEN_ITEMS).

    py -3.12 -X utf8 tools/loop/working_store.py [--inventory P] [--json out.json]

Proofs: tools/loop/working_store_checks.py (check 504).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import backup_coverage as bc  # noqa: E402  (the one walker of the main checkout's data)
import shared_paths  # noqa: E402
import step_cost as sc  # noqa: E402

CONFIG = ROOT / 'config' / 'working_store.json'
GIB = 2 ** 30
MB = 10 ** 6
KINDS = ('name_contains', 'path_prefix', 'credential_name')


class WorkingStoreError(Exception):
    """A declaration this planner refuses."""


def refuse(condition, message):
    if not condition:
        raise WorkingStoreError(message)


def read_config(path=None):
    try:
        value = json.loads(Path(CONFIG if path is None else path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise WorkingStoreError('The working store declaration cannot be read') from None
    refuse(isinstance(value, dict) and isinstance(value.get('roots'), list) and value['roots'],
           'The declaration names its laptop roots')
    rules = value.get('stay_local')
    refuse(isinstance(rules, list) and rules, 'The declaration names what stays local')
    for rule in rules:
        refuse(isinstance(rule, dict) and rule.get('kind') in KINDS and rule.get('match') and rule.get('why'),
               'Each stay-local rule has a kind (%s), a match and a why' % ', '.join(KINDS))
    for key in ('upload', 'launch', 'filesystem', 'on_store'):
        refuse(isinstance(value.get(key), dict), 'The declaration has its %s block' % key)
    refuse(value['upload'].get('mb_per_second', 0) > 0 and value['upload'].get('source'),
           'The upload rate is a measurement with its source')
    return value


def stays_local(logical, rules):
    """The why of the first stay-local rule that matches this path, or None."""
    name = logical.rsplit('/', 1)[-1]
    for rule in rules:
        kind, match = rule['kind'], rule['match']
        if kind == 'name_contains' and match.lower() in name.lower():
            return rule['why']
        if kind == 'path_prefix' and (logical == match or logical.startswith(match.rstrip('/') + '/')):
            return rule['why']
        if kind == 'credential_name' and bc.credential_name(name):
            return rule['why']
    return None


def on_store(disk, logical, block):
    """True for an asset archive whose recorded digest the file system already holds."""
    if logical.rsplit('/', 1)[-1] != block.get('archive_name'):
        return False
    record = Path(disk).parent / block.get('digest_record', '')
    try:
        digest = json.loads(record.read_text(encoding='utf-8')).get(block.get('digest_field'))
    except (OSError, ValueError, AttributeError):
        return False
    return digest in {d.get('sha256') for d in block.get('digests') or []}


def classify(main, config, walker=None):
    """{part: {files, candidate_bytes, on_store_bytes, local_bytes, local_files, why}} over the declared roots."""
    walker = walker or bc.walk
    parts, seen = {}, set()
    rules = config['stay_local']
    for root in config['roots']:
        files, _links, _skipped = walker(main, within=root)
        for logical in sorted(files):
            disk, size, _mtime, _changed, inode = files[logical]
            if inode in seen and inode != (0, 0):
                continue
            seen.add(inode)
            part = bc.part_of(logical)
            row = parts.setdefault(part, dict(files=0, candidate_bytes=0, on_store_bytes=0, local_bytes=0,
                                              local_files=0, why=set(), candidates=[]))
            row['files'] += 1
            why = stays_local(logical, rules)
            if why:
                row['local_bytes'] += size
                row['local_files'] += 1
                row['why'].add(why)
            elif on_store(disk, logical, config['on_store']):
                row['on_store_bytes'] += size
            else:
                row['candidate_bytes'] += size
                row['candidates'].append(logical)
    for row in parts.values():
        row['why'] = sorted(row['why'])
    return parts


def upload_minutes(nbytes, config):
    return nbytes / (config['upload']['mb_per_second'] * MB) / 60


def move_step(parts, config):
    """The move: one launch receiving every candidate part (with), or the on-store archives again too (without)."""
    candidate = sum(r['candidate_bytes'] for r in parts.values())
    stored = sum(r['on_store_bytes'] for r in parts.values())
    launch = config['launch']
    return dict(step='working store move', instance_type=launch['instance_type'], launches=1,
                minutes=dict(boot=launch['boot_minutes'], upload=round(upload_minutes(candidate + stored, config), 2),
                             **{'return': launch['return_minutes']}),
                storage=dict(gib=round(candidate / GIB, 3), hours=config['hold_hours']),
                measures=[dict(name='asset_copy', keeps_minutes=round(upload_minutes(candidate, config), 2),
                               source='the asset archives already on the file system are not sent again '
                                      '(ASSET-COPY-A; %s)' % config['upload']['source'])])


def read_step(parts, entry, config):
    """A part Lambda jobs read `launches` times: sent with each (without) or held on the store (with)."""
    refuse(entry.get('part') in parts, 'lambda_reads names a part the walk did not find: %r' % entry.get('part'))
    refuse(isinstance(entry.get('launches'), int) and entry['launches'] >= 1 and entry.get('source'),
           'lambda_reads gives launches and a source')
    row = parts[entry['part']]
    refuse(row['candidate_bytes'] > 0, 'lambda_reads names a part with nothing that may leave the laptop')
    gib = round(row['candidate_bytes'] / GIB, 3)
    return dict(step='read %s' % entry['part'], instance_type=config['launch']['instance_type'],
                launches=entry['launches'], minutes=dict(seed=round(upload_minutes(row['candidate_bytes'], config), 2)),
                measures=[dict(name='warm_file_system', keeps_minutes=0,
                               adds_storage=dict(gib=gib, hours=config['hold_hours']), source=entry['source'])])


def commands(parts, config):
    """The commands a move would run, as text: one per part with candidates, each reading the part's own file
    list (`<part>.list`, the candidates in the plan's JSON), so a stay-local file is never named in it."""
    fs = config['filesystem']
    out = []
    for part in sorted(parts):
        if not parts[part]['candidate_bytes']:
            continue
        name = part.replace('/', '__')
        target = '%s/%s/%s.tar' % (fs['mount'], fs['store_dir'], name)
        out.append('tar -cf - -T %s | ssh <instance> %s' % (shlex.quote(name + '.list'), shlex.quote(
            'cat > %s.partial && mv -n %s.partial %s' % (target, target, target))))
    return out


def plan(main, config, inventory, record, limits=None, walker=None):
    parts = classify(main, config, walker)
    move = sc.estimate(sc.read_step(move_step(parts, config)), inventory, record, limits)
    reads = [sc.estimate(sc.read_step(read_step(parts, e, config)), inventory, record, limits)
             for e in config.get('lambda_reads') or []]
    for row in parts.values():   # a stay-local file is never in an upload list, whatever else is declared
        refuse(not any(stays_local(c, config['stay_local']) for c in row['candidates']),
               'A stay-local file reached an upload list')
    return dict(parts=parts, move=move, reads=reads, commands=commands(parts, config))


def report(result):
    out = ['Working store plan (dry run: nothing is launched, copied or deleted)']
    total = {k: sum(r[k] for r in result['parts'].values()) for k in ('candidate_bytes', 'on_store_bytes', 'local_bytes')}
    out.append('  %-34s %8s %10s %10s %10s' % ('part', 'files', 'send GiB', 'store GiB', 'local GiB'))
    for part in sorted(result['parts']):
        r = result['parts'][part]
        out.append('  %-34s %8d %10.2f %10.2f %10.2f' % (part, r['files'], r['candidate_bytes'] / GIB,
                                                       r['on_store_bytes'] / GIB, r['local_bytes'] / GIB))
    out.append('  %-34s %8s %10.2f %10.2f %10.2f' % ('total', '', total['candidate_bytes'] / GIB,
                                                   total['on_store_bytes'] / GIB, total['local_bytes'] / GIB))
    reasons = sorted({w for r in result['parts'].values() for w in r['why']})
    out.extend('  stays local: ' + w for w in reasons)
    out.extend(sc.lines(result['move']))
    for read in result['reads']:
        out.extend(sc.lines(read))
    if not result['reads']:
        out.append('  No part is declared as read again and again by Lambda jobs (lambda_reads is empty).')
    out.append('  %d upload command(s) a move would run (text only; no launch path exists for them)' % len(result['commands']))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--config', type=Path, default=None)
    parser.add_argument('--inventory', type=Path, default=None)
    parser.add_argument('--storage-record', type=Path, default=None)
    parser.add_argument('--json', type=Path, default=None, help='the plan, with the commands, as JSON')
    args = parser.parse_args(argv)
    try:
        config = read_config(args.config)
        main_root = shared_paths.main_checkout()
        inventory = sc.read_json(args.inventory or sc.newest_inventory(sc.inventory_candidates(main_root)),
                                 'provider inventory')
        record = sc.read_json(args.storage_record or main_root.joinpath(*shared_paths.PRIVATE, sc.STORAGE_RECORD),
                              'storage record')
        result = plan(main_root, config, inventory, record)
    except (WorkingStoreError, sc.StepCostError, shared_paths.MainCheckoutError) as exc:
        print('Working store plan refused: %s' % exc, flush=True)
        return 2
    print('\n'.join(report(result)), flush=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=1, sort_keys=True, default=list) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
