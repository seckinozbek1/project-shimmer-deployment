"""Read-only Producer output diagnostics. Never generates or selects a model."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import mean, median
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FROZEN = ROOT / 'tuning/second_domain_agnostic_v2'
PILOT = ROOT / 'docs/fix/second_tuning_canonical_pilot'
sys.path.insert(0, str(FROZEN))
import runtime as frozen

FIELDS = {'claims': 'claims', 'questions': 'typed_gaps',
          'uncertainty': 'typed_uncertainty', 'refs': 'evidence'}


def percentile(values, q):
    """Linear interpolation at (n-1)*q, including small samples explicitly."""
    a = sorted(values)
    if not a:
        return None
    position = (len(a) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(a) - 1)
    return a[lo] + (a[hi] - a[lo]) * (position - lo)


def distribution(values):
    a = list(values)
    return dict(n=len(a), min=min(a) if a else None,
                median=median(a) if a else None, mean=mean(a) if a else None,
                p10=percentile(a, .10), p90=percentile(a, .90),
                p95=percentile(a, .95), p99=percentile(a, .99),
                max=max(a) if a else None,
                tail_quantiles_caution=len(a) < 20)


def decorations(raw):
    """Describe JSON boundaries without repairing or scoring a repaired string."""
    result = dict(code_fence='```' in raw, commentary_before_json=False,
                  commentary_after_json=False, json_followed_by_prose=False,
                  json_followed_by_second_json=False)
    decoder = json.JSONDecoder()
    text = raw.strip()
    for index, char in enumerate(text):
        if char not in '{[':
            continue
        try:
            obj, end = decoder.raw_decode(text, index)
        except ValueError:
            continue
        if not isinstance(obj, (dict, list)):
            continue
        result['commentary_before_json'] = bool(text[:index].strip())
        trailing = text[end:].strip()
        if trailing:
            try:
                _, end2 = decoder.raw_decode(trailing)
            except ValueError:
                result['json_followed_by_prose'] = True
                result['commentary_after_json'] = True
            else:
                result['json_followed_by_second_json'] = True
                result['commentary_after_json'] = bool(trailing[end2:].strip())
        break
    return result


def canonical_atom(field, value):
    # Only exact JSON-object normalization of typed strings; no paraphrase/fuzzy matching.
    prefix = {'questions': 'Gap: ', 'uncertainty': 'Uncertainty: '}.get(field)
    if prefix and isinstance(value, str) and value.startswith(prefix):
        try:
            obj = frozen.core.strict_json(value[len(prefix):])
        except (ValueError, TypeError):
            return value
        if isinstance(obj, dict) and set(obj) == {'category', 'subject', 'attribute', 'ordinal', 'relation', 'state', 'scope', 'unit'}:
            return prefix + json.dumps(obj, sort_keys=True, separators=(',', ':'))
    return value


def atoms(obj):
    values = {key: [] for key in FIELDS}
    if not isinstance(obj, dict) or not isinstance(obj.get('items', []), list):
        return values
    for item in obj.get('items', []):
        if not isinstance(item, dict):
            continue
        span = item.get('span', '')
        for key in FIELDS:
            a = item.get(key, [])
            if isinstance(a, list):
                values[key].extend((str(span), v) for v in a if isinstance(v, str))
    return values


def duplicates(obj):
    result = {}
    for key, values in atoms(obj).items():
        exact = len(values) - len(set(values))
        canon = {(span, canonical_atom(key, value)) for span, value in values}
        total = len(values) - len(canon)
        result[key] = dict(exact=exact, canonical_total=total,
                           canonical_additional=total - exact)
    return result


def efficiency(score, tokens):
    if tokens <= 0:
        raise ValueError('A generated-token denominator must be positive')
    counts = {name: score[name]['tp'] for name in FIELDS.values()}
    counts['all'] = sum(counts.values())
    return dict(correct_atoms=counts, per_output_token={k: v / tokens for k, v in counts.items()},
                accepted=score['contract_valid'] and score['accepted_outcome'],
                required_atoms=sum(score[k]['tp'] + score[k]['fn'] for k in FIELDS.values()))


def describe(item, row, cap):
    ids = item['output_token_ids']
    raw = item['raw_output']
    score = frozen.score(row, raw, item['stop_reason'] != 'eos')
    try:
        obj = frozen.core.strict_json(raw)
    except (ValueError, TypeError):
        obj = None
    counts = {k: len(v) for k, v in atoms(obj).items()}
    return dict(example_id=item['example_id'], tokens=len(ids),
                eos_before_cap=item['stop_reason'] == 'eos' and len(ids) < cap,
                cap_contact=len(ids) >= cap, eos=item['stop_reason'] == 'eos',
                refused=frozen.refused(obj), contract_valid=score['contract_valid'],
                semantically_complete=score['semantic_completeness'], accepted=score['accepted_outcome'],
                atom_counts=counts, duplicate_atoms=duplicates(obj), decorations=decorations(raw),
                efficiency=efficiency(score, len(ids)))


def summarize(rows, label):
    accepted = [x for x in rows if x['accepted'] and x['contract_valid']]
    nonempty_accepted = [x for x in accepted if x['efficiency']['required_atoms'] > 0]
    return dict(scope=label, count=len(rows), output_tokens=distribution(x['tokens'] for x in rows),
                eos_before_cap_count=sum(x['eos_before_cap'] for x in rows),
                eos_before_cap_rate=sum(x['eos_before_cap'] for x in rows) / len(rows),
                cap_contact_count=sum(x['cap_contact'] for x in rows),
                cap_contact_rate=sum(x['cap_contact'] for x in rows) / len(rows),
                contract_valid_count=sum(x['contract_valid'] for x in rows),
                semantically_complete_count=sum(x['semantically_complete'] for x in rows),
                accepted_count=len(accepted), refused_count=sum(x['refused'] for x in rows),
                refusal_tokens=distribution(x['tokens'] for x in rows if x['refused']),
                non_refusal_tokens=distribution(x['tokens'] for x in rows if not x['refused']),
                accepted_output_token_cost=distribution(x['tokens'] for x in accepted),
                accepted_nonempty_output_token_cost=distribution(x['tokens'] for x in nonempty_accepted),
                decorations={k: dict(count=sum(x['decorations'][k] for x in rows), rate=sum(x['decorations'][k] for x in rows) / len(rows)) for k in rows[0]['decorations']},
                duplicates={k: dict(exact=sum(x['duplicate_atoms'][k]['exact'] for x in rows),
                                    canonical_total=sum(x['duplicate_atoms'][k]['canonical_total'] for x in rows),
                                    canonical_additional=sum(x['duplicate_atoms'][k]['canonical_additional'] for x in rows),
                                    output_count=sum(x['duplicate_atoms'][k]['canonical_total'] > 0 for x in rows),
                                    output_rate=sum(x['duplicate_atoms'][k]['canonical_total'] > 0 for x in rows) / len(rows)) for k in FIELDS},
                duplicate_output_count=sum(any(v['canonical_total'] for v in x['duplicate_atoms'].values()) for x in rows),
                duplicate_output_rate=sum(any(v['canonical_total'] for v in x['duplicate_atoms'].values()) for x in rows) / len(rows),
                efficiency={k: distribution(x['efficiency']['per_output_token'][k] for x in rows) for k in ('all', *FIELDS.values())},
                accepted_nonempty_efficiency=distribution(x['efficiency']['per_output_token']['all'] for x in nonempty_accepted))


def pair_rows(first, second):
    left = {x['example_id']: x for x in first}
    pairs = []
    for b in second:
        a = left[b['example_id']]
        pairs.append(dict(scope='PARTIAL_PREFIX_ONLY', example_id=b['example_id'],
                          before_tokens=a['tokens'], after_tokens=b['tokens'],
                          difference=b['tokens'] - a['tokens'], ratio=b['tokens'] / a['tokens'],
                          refusal_transition=f"{a['refused']}->{b['refused']}",
                          before_eos=a['eos'], after_eos=b['eos'],
                          before_atoms=a['atom_counts'], after_atoms=b['atom_counts'],
                          before_decorations=a['decorations'], after_decorations=b['decorations'],
                          before_duplicates=a['duplicate_atoms'], after_duplicates=b['duplicate_atoms']))
    return dict(scope='PARTIAL_PREFIX_ONLY', count=len(pairs),
                before_tokens=distribution(x['before_tokens'] for x in pairs),
                after_tokens=distribution(x['after_tokens'] for x in pairs),
                differences=distribution(x['difference'] for x in pairs),
                ratios=distribution(x['ratio'] for x in pairs),
                ratio_of_token_totals=sum(x['after_tokens'] for x in pairs) / sum(x['before_tokens'] for x in pairs),
                refusal_transitions=dict(Counter(x['refusal_transition'] for x in pairs)),
                growth_by_transition={key: dict(count=sum(x['refusal_transition'] == key for x in pairs),
                                               total_token_difference=sum(x['difference'] for x in pairs if x['refusal_transition'] == key)) for key in sorted({x['refusal_transition'] for x in pairs})},
                atom_totals={key: dict(before=sum(x['before_atoms'][key] for x in pairs), after=sum(x['after_atoms'][key] for x in pairs)) for key in FIELDS},
                pairs=pairs)


def throughput():
    first = ROOT / 'docs/fix/first_real_tuning_20260916/downloaded/runs/first-domain-agnostic-tuning-v1/producer'
    result = {}
    for path in sorted(first.glob('dev-*.json')):
        a = frozen.read(path)
        result['run1_' + path.stem] = dict(count=len(a), tokens=sum(x['output_tokens'] for x in a), seconds=sum(x['latency_seconds'] for x in a))
    result['run1_combined'] = {k: sum(v[k] for v in result.values()) for k in ('count', 'tokens', 'seconds')}
    events = frozen.read(PILOT / 'downloaded/evidence/producer_events.json')
    for step in (60, 120):
        a = [x for x in events if x['kind'] == 'generation' and x['step'] == step]
        result['pilot_' + str(step)] = dict(count=len(a), tokens=sum(x['tokens'] for x in a), seconds=sum(x['seconds'] for x in a), scope='COMPLETE_DEV' if step == 60 else 'PARTIAL_PREFIX_ONLY')
    bounded = frozen.read(ROOT / 'docs/fix/remote_short_burst_secure_20260915/evidence/probe/probe.json')
    for x in bounded['calls']:
        if x['role'] == 'active_producer':
            result['bounded_' + x['label']] = dict(count=1, tokens=x['usage']['output_tokens'], seconds=x['usage']['generation_seconds'])
    for v in result.values():
        v['prefill_inclusive_output_tokens_per_second'] = v['tokens'] / v['seconds']
        v['decode_only_throughput_available'] = False
    return result


def historical_trace_callback():
    """Exact callback AST for reference/control; no frozen train execution."""
    source = ROOT / 'tools/second_tuning_remote.py'
    module = ast.parse(source.read_text())
    train = next(x for x in module.body if isinstance(x, ast.FunctionDef) and x.name == 'train')
    trace = next(x for x in train.body if isinstance(x, ast.FunctionDef) and x.name == 'trace')
    factory = ast.parse('def make_trace():\n recorded_parameters=False\n last_loss_step=0\n').body[0]
    factory.body += [trace, ast.Return(value=ast.Name(id='trace', ctx=ast.Load()))]
    compiled = ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[]))
    namespace = dict(BASE=FROZEN, install=lambda frame: None, event=lambda *a, **k: None)
    exec(compile(compiled, '<historical-trace-effect-proof>', 'exec'), namespace)
    callback = namespace['make_trace']()
    return callback, hashlib.sha256(ast.dump(trace).encode()).hexdigest()


def telemetry_summary():
    base = PILOT / 'downloaded/evidence'
    events = frozen.read(base / 'producer_events.json')
    samples = [json.loads(x) for x in (base / 'producer_telemetry.jsonl').read_text().splitlines()]
    output = {}
    for step in (60, 120):
        intervals = [(x['epoch'] - x['seconds'], x['epoch']) for x in events if x['kind'] == 'generation' and x['step'] == step]
        selected = [s for s in samples if any(a <= s['epoch'] <= b for a, b in intervals)]
        gpu = [float(x['gpu'].split(',')[0]) for x in selected if x.get('gpu')]
        cpu = [x['cpu_percent'] for x in selected]
        output[str(step)] = dict(scope='COMPLETE_DEV' if step == 60 else 'PARTIAL_PREFIX_ONLY', samples=len(selected),
                                 gpu_util_median=median(gpu), gpu_util_mean=mean(gpu), cpu_percent_median=median(cpu), cpu_percent_mean=mean(cpu))
    return output


def observer_probe():
    """CPU-only effect proof; never a model/GPU benchmark or GPU speedup estimate."""
    callback, callback_hash = historical_trace_callback()
    def leaf(x):
        return (x * 13 + 7) % 104729
    def workload():
        total = 0
        for i in range(30000):
            total += leaf(i)
        return total
    measurements = {'untraced': [], 'historical_trace': []}
    outputs = []
    for trial in range(5):
        for name in (('untraced', 'historical_trace') if trial % 2 == 0 else ('historical_trace', 'untraced')):
            previous = sys.gettrace()
            if previous is not None:
                raise RuntimeError('Probe requires an untraced process')
            try:
                sys.settrace(callback if name == 'historical_trace' else None)
                start = time.perf_counter()
                outputs.append(workload())
                measurements[name].append(time.perf_counter() - start)
            finally:
                sys.settrace(previous)
    assert len(set(outputs)) == 1
    return dict(scope='CPU_SYNTHETIC_ONLY_NO_MODEL', calls_per_trial=30001, repeats=5,
                timings_seconds=measurements,
                median_slowdown_ratio=median(measurements['historical_trace']) / median(measurements['untraced']),
                exact_callback_ast_sha256=callback_hash,
                global_callback_enters_non_target_frames=True, equal_workload_results=True,
                historical_gpu_causal_fraction='NOT_MEASURED')


def main():
    spec = frozen.read(FROZEN / 'producer/experiment.json')
    ids = frozen.read(FROZEN / 'splits.json')['canonical']['validation']
    rows = {x['example_id']: x for x in frozen.read(FROZEN / 'dataset.json') if x['role'] == 'producer'}
    ids = [i for i in ids if i in rows]
    raw = [json.loads(line) for line in (PILOT / 'downloaded/evidence/producer_raw_dev.jsonl').read_text().splitlines()]
    groups = {}
    for step, expected in ((60, 60), (120, 42)):
        items = [x for x in raw if x['step'] == step]
        assert len(items) == expected and [x['example_id'] for x in items] == ids[:expected]
        groups[step] = [describe(x, rows[x['example_id']], spec['generation']['max_new_tokens']) for x in items]
        for item in groups[step]:
            item['scope'] = 'COMPLETE_DEV' if step == 60 else 'PARTIAL_PREFIX_ONLY'
    # Deliberately no frozen.aggregate, select_checkpoint, or historical file writes.
    result = dict(checkpoint60=summarize(groups[60], 'COMPLETE_DEV'),
                  checkpoint120_PARTIAL_PREFIX_ONLY=summarize(groups[120], 'PARTIAL_PREFIX_ONLY'),
                  paired_PARTIAL_PREFIX_ONLY=pair_rows(groups[60], groups[120]),
                  rows60=groups[60], rows120_PARTIAL_PREFIX_ONLY=groups[120],
                  historical_throughput=throughput(), observer_effect=observer_probe(),
                  telemetry_during_saved_generation_intervals=telemetry_summary(),
                  warning_counts_unphased=dict(Counter(line.split('UserWarning: ', 1)[1] for line in (PILOT / 'producer_training.log').read_text(errors='replace').splitlines() if 'UserWarning: ' in line)),
                  efficiency_definition='Exact frozen (span, value) true-positive sets for claims, typed gaps, uncertainty and evidence, divided by saved generated token count including EOS. Refusal/status/empty correctness contributes no invented content atom; acceptance reported separately.',
                  quantile_definition='Linear interpolation at (n-1)*q; tails with n<20 explicitly marked unstable',
                  no_checkpoint120_selection_or_complete_population_metrics=True)
    frozen.write(HERE / 'audit_results.json', result)
    print(json.dumps({k: v for k, v in result.items() if k in ('checkpoint60', 'checkpoint120_PARTIAL_PREFIX_ONLY', 'observer_effect')}, indent=2))


if __name__ == '__main__':
    main()
