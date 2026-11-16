"""PROCESSOR DEV scored against gold (#217, D-625): the frozen DEV scorer of checkpoint 168, for the
producer role, vendored here because the sealed project archive carries no tuning/ folder.

The functions are tuning/second_domain_agnostic_v2/runtime.py's `score` (producer branch), `pr`, `f1`,
`values`, `refused`, `contract` and `spans`, with benchmark/task_semantics/core.py's `strict_json`, line
for line; compact_contracts.producer and bounded_extraction.Span are the project's own. A check holds
this copy equal to the frozen per-row metrics of full_dev_scored.json on all 84 rows
(vllm_replay_checks.py, GoldScoreProof).

The bar (docs/loop/stages/VLLM_GOLD_SCORING_PLAN.md, written before any figure): macro-F1 = the mean
of the evidence, claims, typed-gap and typed-uncertainty F1s over the scored rows; vLLM's at most 1 point
below the current engine's at the paired bootstrap lower bound (one-sided 5 percent, clusters by document
family); contract validity not lower; DEV items in valid replies not fewer.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

F1_KEYS = ("evidence", "claims", "typed_gaps", "typed_uncertainty")
BOOTSTRAP = 2000
MARGIN = 0.01


def strict_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def refused(obj):
    return obj == dict(items=[], status='refused')


def spans(row):
    import bounded_extraction as ex
    return tuple(ex.Span(s['alias'], int(s['alias'][1:], 16), int(s['alias'][1:], 16) + len(s['text']), '', None, s['text'])
                 for s in row['input']['source_spans'])


def contract(row, obj):
    import compact_contracts as cc
    if refused(obj):
        return True
    try:
        cc.producer(obj, spans(row), row['example_id'])
        return True
    except (TypeError, ValueError, KeyError):
        return False


def pr(pred, gold):
    p, g = set(pred), set(gold)
    tp = len(p & g)
    return dict(tp=tp, fp=len(p - g), fn=len(g - p))


def f1(c):
    d = 2 * c['tp'] + c['fp'] + c['fn']
    return 2 * c['tp'] / d if d else 1.


def values(obj, key):
    return [(i.get('span', '') if isinstance(i.get('span', ''), str) else '<invalid>', v)
            for i in obj.get('items', []) for v in (i.get(key, []) if isinstance(i.get(key, []), list) else []) if isinstance(v, str)]


def score(row, raw, truncated=False):
    """The frozen producer score of one DEV row's reply (runtime.score, producer branch)."""
    import re
    try:
        obj = strict_json(raw)
    except (ValueError, TypeError):
        obj = {}
    valid = not truncated and contract(row, obj)
    if not isinstance(obj, dict) or not isinstance(obj.get('items', []), list) or any(not isinstance(i, dict) for i in obj.get('items', [])):
        obj = {}
    gold = row['canonical_target']
    ref = refused(obj)
    expected = refused(gold)
    result = dict(example_id=row['example_id'], family=row['document_family'], leakage_group=row['leakage_group'],
                  role=row['role'], contract_valid=valid, expected_refusal=expected, predicted_refusal=ref,
                  refusal_correct=ref == expected)
    p, g = values(obj, 'refs'), values(gold, 'refs')
    result['evidence'] = pr(p, g)
    result['catastrophic'] = dict(invented_evidence=bool({v for _, v in p} - set(row['input']['supplied_refs'])),
                                  invented_rule=bool(set(re.findall(r'CONV-[A-Za-z0-9-]+', raw)) - set(row['input']['routed_rules'])),
                                  confident_wrong_match_divergence=False, truncation=bool(truncated),
                                  producer_source_copy=False, governance_violations=False)
    for key, name in [('claims', 'claims'), ('questions', 'typed_gaps'), ('uncertainty', 'typed_uncertainty')]:
        result[name] = pr(values(obj, key), values(gold, key))
    result['semantic_completeness'] = valid and ref == expected and all(
        result[k]['fp'] == result[k]['fn'] == 0 for k in ('claims', 'typed_gaps', 'typed_uncertainty', 'evidence'))
    texts = [s['text'] for s in row['input']['source_spans']]
    result['catastrophic']['producer_source_copy'] = any(len(s) > 80 and s in raw for s in texts)
    result['accepted_outcome'] = result['semantic_completeness']
    return result


def gold_row(row):
    """What a DEV prompt carries to the instance for scoring: the row's identity, its families, the
    input fields the scorer reads and its canonical target (development tuning data, not a key)."""
    return {"example_id": row["example_id"], "document_family": row["document_family"],
            "leakage_group": row["leakage_group"], "role": row["role"], "canonical_target": row["canonical_target"],
            "input": {k: row["input"][k] for k in ("source_spans", "supplied_refs", "routed_rules")}}


def macro(scores):
    """The bar's macro-F1: the mean of the four F1s over pooled counts."""
    return sum(f1({k: sum(s[key][k] for s in scores) for k in ("tp", "fp", "fn")}) for key in F1_KEYS) / len(F1_KEYS)


def aggregate(scores):
    n = len(scores)
    out = {"rows": n, "contract_validity": sum(s["contract_valid"] for s in scores) / n if n else None,
           "refusal_correct": sum(s["refusal_correct"] for s in scores), "macro_f1": macro(scores) if n else None}
    for key in F1_KEYS:
        out[key + "_f1"] = f1({k: sum(s[key][k] for s in scores) for k in ("tp", "fp", "fn")}) if n else None
    return out


def paired_bar(current, other, seed=0, n=BOOTSTRAP, level=0.05):
    """The paired cluster bootstrap of macro-F1(other) - macro-F1(current), clusters by document family:
    the point difference, its one-sided lower bound, and whether the bar holds (lower bound >= -MARGIN)."""
    families = sorted({s["family"] for s in current})
    by_family = {f: ([s for s in current if s["family"] == f], [s for s in other if s["family"] == f]) for f in families}
    point = macro(other) - macro(current)
    rng, diffs = random.Random(seed), []
    for _ in range(n):
        picks = [families[rng.randrange(len(families))] for _ in families]
        a = [s for f in picks for s in by_family[f][0]]
        b = [s for f in picks for s in by_family[f][1]]
        diffs.append(macro(b) - macro(a))
    diffs.sort()
    lower = diffs[int(level * n)]
    return {"point": round(point, 4), "lower_bound": round(lower, 4), "margin": MARGIN, "families": len(families),
            "holds": lower >= -MARGIN}
