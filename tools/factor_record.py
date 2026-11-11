"""Factor records and attribution (D-S82): every change in a figure is attributed to its cause.

1. `record(manifest, launch, seal)` writes, from a run's own sealed records, the factors a result
   rests on: arm, machine type, models, checkpoint, training recipe, calibration, prompt or context,
   decoding, item set, scorer, seed and the rest of the code. Each factor is a short digest of
   what it reads, with the source named; a factor nothing records is `None` ("not recorded").
   The project files each factor reads are declared in `config/factor_record.json`, never here.
2. `compare(a, b)` names the factors that differ between two records. A factor not recorded on
   either side counts as the same (nothing to tell them apart); recorded on one side only, it
   differs.
3. `attribute(change, comparison, isolating)` splits a change: the whole of it to a factor only
   when that factor alone differs; otherwise only the parts that an isolating comparison
   measures (one that differs in that factor alone, on the same metric), and the remainder joint
   over the factors left. With no isolating comparison, the change is joint and is not split.
4. `machine_effect(a10, other)` reads the fixed reference set run on the A10 and on a new machine
   type (the two records must differ in the machine alone and carry the declared reference set):
   the time factor, and whether any score moved, reported as a hardware effect, never a system
   gain.
5. `render_table(...)` writes the short report table per headline result.

The CLI `record` writes a run folder's record; `compare` writes the attribution for two run
folders (and any isolating pairs) on one metric. Python writes every record, never a hand.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'factor_record.json'
NOT_RECORDED = None


def declaration(path=None):
    return json.loads(Path(path or CONFIG).read_text(encoding='utf-8'))


def digest(value):
    """A short, stable digest of a JSON value (sorted keys, compact)."""
    text = json.dumps(value, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def _claims(path, declared):
    return any(path == entry or (entry.endswith('/') and path.startswith(entry)) for entry in declared)


def assign_files(project_files, declared):
    """Each project file to the first factor (in declaration order) whose path or prefix claims
    it; every file left is the factor `code`."""
    out = {name: {} for name in declared}
    out['code'] = {}
    for path, sha in sorted(project_files.items()):
        owner = next((name for name, entries in declared.items() if _claims(path, entries)), 'code')
        out[owner][path] = sha
    return out


def _value(parts, source):
    """One factor: None when nothing is recorded, else its digest and where it was read."""
    present = {k: v for k, v in parts.items() if v not in (None, {}, [], '')}
    if not present:
        return dict(value=NOT_RECORDED, source='not recorded')
    return dict(value=digest(present), source=source, parts=sorted(present))


def record(manifest, launch=None, seal=None, config=None):
    """The factor record of one result, from its sealed manifest, its launch record and its seal."""
    spec = declaration(config)
    launch = launch or {}
    seal = seal or {}
    files = assign_files(manifest.get('project_files') or {}, spec['files'])
    b1 = manifest.get('b1') or {}
    passes = b1.get('checkpoints') or []
    environment = manifest.get('environment') or {}
    workload = manifest.get('workload') or {}
    machine = launch.get('instance_type') or (launch.get('instance_candidate') or {}).get('type')
    factors = {
        'arm': dict(value=manifest.get('arm') or 'B3', source='manifest arm (none means B3)'),
        'machine_type': (dict(value=machine, source='launch record') if machine else
                         dict(value=NOT_RECORDED, source='not recorded (no launch record)')),
        'model': _value({'models': [dict(model_id=m.get('model_id'), revision=m.get('revision'),
                                         files=digest(m.get('files') or {})) for m in manifest.get('models') or []]},
                        'manifest models (id, revision, file digests)'),
        'checkpoint': _value({'files': files.get('checkpoint'),
                              'b1': [dict(name=p.get('name'), checkpoint=p.get('checkpoint')) for p in passes]},
                             'declared checkpoint files and the B1 passes\' checkpoints'),
        'training_recipe': _value({'files': files.get('training_recipe'),
                                   'sealed': manifest.get('training_recipe_sha256')},
                                  'declared recipe files and the manifest\'s training_recipe_sha256'),
        'calibration': _value({'files': files.get('calibration')}, 'declared calibration files'),
        'prompt_or_context': _value({'files': files.get('prompt_or_context')}, 'declared prompt files'),
        'decoding': _value({'policy': manifest.get('decoding_policy'), 'files': files.get('decoding'),
                            'environment': {k: environment[k] for k in spec.get('decoding_environment', [])
                                            if k in environment},
                            'b1_args': [p.get('args') for p in passes]},
                           'manifest decoding policy, declared decoding files, settings and B1 arguments'),
        'item_set': _value({'workload': workload.get('files'), 'b1_items': b1.get('items_sha256'),
                            'case_manifest': manifest.get('case_manifest_sha256'),
                            'test_manifest': seal.get('test_manifest_sha256')},
                           'workload digests, B1 items, case manifest and sealed test manifest'),
        'scorer': _value({'files': files.get('scorer')}, 'declared scorer files'),
        'seed': (dict(value=str(manifest['seed']), source='manifest seed') if manifest.get('seed') is not None else
                 dict(value=NOT_RECORDED, source='not recorded (deterministic decoding names no seed)')),
        'code': _value({'files': files.get('code')}, 'every other project file'),
    }
    missing = [name for name in spec['factors'] if name not in factors]
    if missing:
        raise ValueError('Declared factors this reader does not read: %s' % ', '.join(missing))
    return dict(schema=spec['schema'], source_commit=manifest.get('source_commit'),
                factors={name: factors[name] for name in spec['factors']})


def differs(a, b):
    """Two values of one factor differ unless both are equal (both unrecorded counts as equal)."""
    return a.get('value') != b.get('value')


def compare(a, b, config=None):
    """The factors that differ between two records, in declaration order, the two machines, and
    whether the pair is a reference-set pair (D-S82 item 3): the machine alone differs, one side
    is the reference machine and both run a declared reference item."""
    names = list(a['factors'])
    if names != list(b['factors']):
        raise ValueError('The two records declare different factors')
    diff = [n for n in names if differs(a['factors'][n], b['factors'][n])]
    machines = [a['factors']['machine_type']['value'], b['factors']['machine_type']['value']]
    reference = declaration(config)['reference_set']
    pair = (diff == ['machine_type'] and reference.get('machine') in machines and reference_item(a, config) is not None)
    return dict(differs=diff, same=[n for n in names if n not in diff],
                unrecorded_on_both=[n for n in names if n not in diff and a['factors'][n].get('value') is None],
                machines=machines, reference_pair=pair)


def require_machine_pair(comparison, isolating=(), config=None):
    """D-S95 item 5, D-389 ruling 2: figures are compared on one machine type, always. A
    comparison across machine types is refused, whatever pairs are given: the reference-set pair
    (the reference set on a type and on the A10) attributes a time factor and is the one
    cross-type comparison admitted; it never licenses comparing figures across types."""
    if 'machine_type' not in comparison['differs'] or comparison.get('reference_pair'):
        return
    raise ValueError('A comparison across machine types is refused: arms and results compared with each other run '
                     'on one machine type (D-S95 item 5); only the D-S82 reference-set pair compares two types, for '
                     'its time factor (machines: %s)' % ', '.join(str(m) for m in comparison['machines']))


def attribute(change, comparison, isolating=(), metric=None):
    """Split `change` (b minus a, on `metric`) over the factors that differ (D-S82 items 2 and 4).

    `isolating` is a list of dict(metric, change, comparison, label): another pair of results. A
    pair is used for factor F only when it differs in F alone and is on the same metric; any
    other is listed as refused with its reason."""
    require_machine_pair(comparison, isolating)
    diff = list(comparison['differs'])
    rows, refused = [], []
    if not diff:
        return dict(metric=metric, change=change, rows=[dict(part='no factor differs', factors=[], change=change,
                                                            basis='the two records are the same; the change is not '
                                                                  'explained by any recorded factor')], refused=[])
    if len(diff) == 1:
        return dict(metric=metric, change=change, rows=[dict(part=diff[0], factors=diff, change=change,
                                                            basis='the only factor that differs')], refused=[])
    used = set()
    for pair in isolating:
        own = list(pair['comparison']['differs'])
        if pair.get('metric') != metric:
            refused.append(dict(label=pair.get('label'), reason='another metric'))
        elif len(own) != 1:
            refused.append(dict(label=pair.get('label'), reason='differs in %d factors, not one' % len(own)))
        elif own[0] not in diff:
            refused.append(dict(label=pair.get('label'), reason='isolates %s, which this change does not involve' % own[0]))
        elif own[0] in used:
            refused.append(dict(label=pair.get('label'), reason='%s is already isolated' % own[0]))
        else:
            used.add(own[0])
            rows.append(dict(part=own[0], factors=[own[0]], change=pair['change'],
                             basis='isolating run %s' % pair.get('label')))
    remainder = change - sum(r['change'] for r in rows)
    left = [n for n in diff if n not in used]
    rows.append(dict(part='joint', factors=left or sorted(used), change=remainder,
                     basis=('changed together; not split' if not rows else
                            'what the isolated parts leave' + ('' if left else ' (their interaction)'))))
    return dict(metric=metric, change=change, rows=rows, refused=refused)


def _pair_items(pairs, config=None):
    """The checked items of one machine's reference pair: every declared reference item exactly once,
    each with its A10 and new-type run folders, their records' digests, their one commit and the
    machine_effect result recomputed from the folders' own records."""
    reference = declaration(config)['reference_set']
    declared = [item['item'] for item in reference.get('items') or []]
    names = [pair.get('item') for pair in pairs]
    if sorted(names) != sorted(declared) or len(names) != len(set(names)):
        raise ValueError('A reference pair covers every declared reference item once: %s, given %s'
                         % (', '.join(declared), ', '.join(map(str, names))))
    return reference


def measured_entry(pairs, config=None):
    """D-382 item 1, D-401 item 3: the `gpu_speed_order.json` `measured` entry for one machine type,
    made from its reference pair: for each of the three reference items, the run folder on the A10
    and on the new type, both records' digests, their one commit and the machine_effect result. Any
    item that moved a score keeps the type out (a hardware effect, not a speed). Exact score
    equality may never hold across GPU generations; then the type stays out. The entry's factor is
    the median of the three items' factors."""
    import statistics
    reference = _pair_items(pairs, config)
    items, commits, machines = [], set(), set()
    for pair in sorted(pairs, key=lambda pair: pair['item']):
        effect = pair['effect']
        if effect.get('scores_moved'):
            raise ValueError('A machine effect that moved a score keeps the type out: %s on %s (%s)'
                             % (pair['item'], effect.get('machine'), ', '.join(effect['scores_moved'])))
        a10, other = folder_record(pair['a10_folder'], config), folder_record(pair['other_folder'], config)
        commits.update({a10['source_commit'], other['source_commit']})
        machines.add(effect['machine'])
        items.append(dict(item=pair['item'], a10_folder=str(pair['a10_folder']), other_folder=str(pair['other_folder']),
                          a10_record_digest=digest(a10), other_record_digest=digest(other),
                          time_factor=effect['time_factor'], effect=effect, effect_digest=digest(effect)))
    if len(commits) != 1 or len(machines) != 1:
        raise ValueError('A reference pair runs one machine type beside the A10 at one commit')
    return dict(time_factor=statistics.median(i['time_factor'] for i in items), rule='median of the three items',
                reference_set=reference['name'], commit=commits.pop(), scores_moved=False, items=items)


def _need(condition):
    if not condition:
        raise ValueError('not checked')


def check_measured(spec, config=None):
    """D-382 item 1, D-401 item 3, at sealing: every `measured` entry is keyed by its machine type and
    is its reference pair as `measured_entry` makes it, read again now from both runs' folders: every
    reference item once, each item's two records' digests and its result's, the two records differing
    in the machine alone on that item, one commit, no moved score, and the median as the factor."""
    import statistics
    for machine, entry in (spec.get('measured') or {}).items():
        try:
            items = entry['items']
            _pair_items(items, config)
            reference = declaration(config)['reference_set']
            for item in items:
                a10, other = folder_record(item['a10_folder'], config), folder_record(item['other_folder'], config)
                effect = item['effect']
                _need(digest(a10) == item['a10_record_digest'] and digest(other) == item['other_record_digest'])
                _need(item['effect_digest'] == digest(effect) and effect['machine'] == machine)
                _need(other['factors']['machine_type']['value'] == machine)
                _need(compare(a10, other, config)['reference_pair'])
                _need(reference_item(a10, config)['item'] == item['item'])
                _need(a10['source_commit'] == other['source_commit'] == entry['commit'])
                _need(not effect.get('scores_moved') and item['time_factor'] == effect['time_factor'])
            _need(machine.startswith('gpu_') and entry['scores_moved'] is False)
            _need(entry['reference_set'] == reference['name'])
            _need(entry['time_factor'] == statistics.median(item['time_factor'] for item in items) > 0)
        except (KeyError, TypeError, ValueError):
            raise ValueError('The measured entry for %s is not a checked reference-set pair' % machine)
    return True


def selected_type(folder):
    """The machine type a run folder's controller selected (launch_preflight.json, else launch.json)."""
    folder = Path(folder)
    for path in (folder / 'launch_preflight.json', folder.parent.parent / 'launch_preflight.json'):
        value = _read(path)
        if value and (value.get('selected') or {}).get('type'):
            return value['selected']['type']
    launch = _read(folder / 'launch.json') or _read(folder.parent.parent / 'launch.json') or {}
    return launch.get('instance_type')


def require_same_type(folders):
    """D-382 item 2: the arms of one figure ran on one machine type, else the figure is refused."""
    types = {str(f): selected_type(f) for f in folders}
    if None in types.values() or len(set(types.values())) != 1:
        raise ValueError('The arms of a figure ran on different or unrecorded machine types: %s'
                         % ', '.join('%s %s' % (Path(f).name, t) for f, t in types.items()))
    return next(iter(types.values()))


def reference_workload(files, config=None):
    """The declared reference item whose sealed workload is exactly `files` (name to digest), or None."""
    items = declaration(config)['reference_set'].get('items') or []
    return next((item for item in items if item.get('workload_files') == dict(files or {})), None)


def reference_item(record, config=None):
    """The declared reference item a record runs, or None (D-S82 item 3)."""
    reference = declaration(config)['reference_set']
    value = record['factors']['item_set']['value']
    return next((item for item in reference.get('items') or [] if item.get('item_set') == value), None)


def machine_effect(a10, other, seconds_other, scores_a10, scores_other, seconds_a10=None, config=None):
    """D-S82 item 3: one item of the fixed reference set on the A10 and on another machine type.
    The two records must differ in the machine alone and run a declared reference item; the A10's
    seconds default to the declared figure for that item."""
    reference = declaration(config)['reference_set']
    if not reference.get('items'):
        raise ValueError('No fixed reference set declared (config/factor_record.json reference_set.items)')
    comparison = compare(a10, other)
    if comparison['differs'] != ['machine_type']:
        raise ValueError('A machine effect needs two records that differ in the machine alone; these differ in: %s'
                         % ', '.join(comparison['differs'] or ['nothing']))
    item = reference_item(a10, config)
    if item is None:
        raise ValueError('The runs are not on the declared reference set')
    if a10['factors']['machine_type']['value'] != reference.get('machine'):
        raise ValueError('The first record is not on the reference machine %s' % reference.get('machine'))
    seconds_a10 = item['a10_seconds'] if seconds_a10 is None else seconds_a10
    moved = sorted(k for k in set(scores_a10) | set(scores_other) if scores_a10.get(k) != scores_other.get(k))
    return dict(machine=other['factors']['machine_type']['value'], reference_set=reference['name'],
                item=item['item'], seconds_a10=seconds_a10, seconds_other=seconds_other,
                time_factor=round(seconds_a10 / seconds_other, 4) if seconds_other else None,
                scores_moved=moved,
                verdict=('hardware effect: scores moved under the same configuration' if moved else
                         'no score moved; only time changed'))

def _number(value):
    return ('%+.4g' % value) if isinstance(value, (int, float)) else str(value)


def render_table(result, attribution):
    """The short table per headline result (D-S82 item 4)."""
    lines = ['%s, %s: change %s' % (result, attribution.get('metric'), _number(attribution['change'])), '',
             '| Part | Factors | Change | Basis |', '|---|---|---|---|']
    for row in attribution['rows']:
        lines.append('| %s | %s | %s | %s |' % (row['part'], ', '.join(row['factors']) or 'none',
                                                _number(row['change']), row['basis']))
    for item in attribution.get('refused', []):
        lines.append('')
        lines.append('Isolating run %s not used: %s.' % (item['label'], item['reason']))
    return '\n'.join(lines)


def summary_line(rec):
    """One line for a run report: each factor's value, or not recorded."""
    return '; '.join('%s %s' % (name, f['value'] if f['value'] is not None else 'not recorded')
                     for name, f in rec['factors'].items())


def _read(path):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def folder_record(folder, config=None):
    """The record of a run folder (a batch entry's launch record is its session's)."""
    folder = Path(folder)
    manifest = _read(folder / 'execution_manifest.json')
    if manifest is None:
        raise ValueError('No execution_manifest.json in %s' % folder)
    launch = _read(folder / 'launch.json') or _read(folder.parent.parent / 'launch.json') or {}
    return record(manifest, launch, _read(folder / 'seal.json'), config)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    one = sub.add_parser('record', help='write the factor record of a run folder')
    one.add_argument('--run', required=True)
    one.add_argument('--out')
    two = sub.add_parser('compare', help='attribute a change between two run folders')
    two.add_argument('--a', required=True)
    two.add_argument('--b', required=True)
    two.add_argument('--metric', required=True)
    two.add_argument('--value-a', type=float, required=True)
    two.add_argument('--value-b', type=float, required=True)
    two.add_argument('--isolating', action='append', default=[],
                     help='LABEL=RUN_A,RUN_B,VALUE_A,VALUE_B: a pair on the same metric')
    two.add_argument('--result', default='result')
    two.add_argument('--out')
    arms = sub.add_parser('arms', help='refuse a figure whose arms ran on different machine types')
    arms.add_argument('--run', action='append', required=True)
    args = parser.parse_args(argv)
    if args.command == 'arms':
        print(require_same_type(args.run))
        return 0
    if args.command == 'record':
        out = folder_record(args.run)
        text = json.dumps(out, indent=1, sort_keys=True)
    else:
        a, b = folder_record(args.a), folder_record(args.b)
        pairs = []
        for item in args.isolating:
            label, rest = item.split('=', 1)
            run_a, run_b, value_a, value_b = rest.split(',')
            pairs.append(dict(label=label, metric=args.metric, change=float(value_b) - float(value_a),
                              comparison=compare(folder_record(run_a), folder_record(run_b))))
        out = attribute(args.value_b - args.value_a, compare(a, b), pairs, metric=args.metric)
        out['table'] = render_table(args.result, out)
        text = json.dumps(out, indent=1, sort_keys=True)
    if getattr(args, 'out', None):
        Path(args.out).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
