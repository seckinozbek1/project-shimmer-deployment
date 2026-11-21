"""Chance test beside every reported figure (D-872, Seckin 21 November 2026 02:48, G-20261121-0248).

A label-permutation test, written before any result is seen: the system's labels are shuffled against the gold
labels N times (at least 10,000, fixed seed), the measure is recomputed each time, and the p value is the share of
shuffles that reach the observed figure, (1 + count) / (N + 1). Where a second arm (B1) is given on the same items, a
paired sign-flip permutation test on the per-item differences gives the difference and its p value as well.

    py -3.12 -X utf8 tools/chance_test.py --rows ROWS.json --measure accuracy|macro_f1 [--classes A,B,C]
        [--b1 B1_ROWS.json] [--shuffles 10000] [--seed 20261121] [--out RESULT.json]

ROWS is a JSON list of {item_id, label, gold} (the scorer's own rows; built by the role that holds the keys, never
by the lead). For macro_f1, --classes names the declared classes (an empty class still counts, as the scorer
declares it). Prints the figure, N, the seed and the p values only; no item id, label or gold.
"""
import argparse
import json
import random
from pathlib import Path

SEED = 20261121
SHUFFLES = 10000


def accuracy(pred, gold):
    return sum(p == g for p, g in zip(pred, gold)) / len(gold)


def macro_f1(pred, gold, classes):
    total = 0.0
    for c in classes:
        tp = sum(p == c and g == c for p, g in zip(pred, gold))
        fp = sum(p == c and g != c for p, g in zip(pred, gold))
        fn = sum(p != c and g == c for p, g in zip(pred, gold))
        total += (2 * tp / (2 * tp + fp + fn)) if (tp + fp + fn) else 0.0
    return total / len(classes)


def measure_fn(name, classes):
    if name == 'accuracy':
        return accuracy
    if name == 'macro_f1':
        if not classes:
            raise SystemExit('macro_f1 needs --classes: stop')
        return lambda p, g: macro_f1(p, g, classes)
    raise SystemExit('unknown measure %r: stop' % name)


def permutation_p(pred, gold, fn, shuffles, seed):
    """(observed, p) of a label-shuffle permutation test: gold fixed, the predictions shuffled."""
    rng = random.Random(seed)
    observed = fn(pred, gold)
    shuffled = list(pred)
    hits = 0
    for _ in range(shuffles):
        rng.shuffle(shuffled)
        hits += fn(shuffled, gold) >= observed - 1e-12
    return observed, (1 + hits) / (shuffles + 1)


def paired_p(pred, other, gold, fn, shuffles, seed):
    """(difference, p) of a paired sign-flip test: per item, the two arms' predictions swapped with chance 1/2."""
    rng = random.Random(seed + 1)
    observed = fn(pred, gold) - fn(other, gold)
    hits = 0
    for _ in range(shuffles):
        a, b = [], []
        for x, y in zip(pred, other):
            if rng.random() < 0.5:
                x, y = y, x
            a.append(x)
            b.append(y)
        hits += abs(fn(a, gold) - fn(b, gold)) >= abs(observed) - 1e-12
    return observed, (1 + hits) / (shuffles + 1)


def load_rows(path):
    rows = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(rows, list) or not rows or not all({'item_id', 'label', 'gold'} <= set(r) for r in rows):
        raise SystemExit('%s: not a list of {item_id, label, gold}: stop' % Path(path).name)
    return {r['item_id']: r for r in rows}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--rows', required=True)
    p.add_argument('--measure', required=True)
    p.add_argument('--classes')
    p.add_argument('--b1')
    p.add_argument('--shuffles', type=int, default=SHUFFLES)
    p.add_argument('--seed', type=int, default=SEED)
    p.add_argument('--out')
    a = p.parse_args(argv)
    if a.shuffles < SHUFFLES:
        raise SystemExit('at least %d shuffles (D-872): stop' % SHUFFLES)
    classes = [c for c in (a.classes or '').split(',') if c]
    fn = measure_fn(a.measure, classes)
    rows = load_rows(a.rows)
    ids = sorted(rows)
    pred, gold = [rows[i]['label'] for i in ids], [rows[i]['gold'] for i in ids]
    observed, p_value = permutation_p(pred, gold, fn, a.shuffles, a.seed)
    out = {'measure': a.measure, 'classes': classes, 'items': len(ids), 'figure': round(observed, 6),
           'shuffles': a.shuffles, 'seed': a.seed, 'permutation_p': round(p_value, 6),
           'test': 'label-shuffle permutation, gold fixed, p = (1 + hits) / (N + 1), D-872'}
    if a.b1:
        b1 = load_rows(a.b1)
        if sorted(b1) != ids:
            raise SystemExit('B1 rows are not the same items: stop')
        other = [b1[i]['label'] for i in ids]
        diff, pp = paired_p(pred, other, gold, fn, a.shuffles, a.seed)
        out.update({'b1_figure': round(fn(other, gold), 6), 'difference_vs_b1': round(diff, 6),
                    'paired_p': round(pp, 6), 'paired_test': 'sign-flip permutation on the same items, two-sided'})
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
