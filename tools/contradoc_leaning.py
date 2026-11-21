"""ContraDoc's low-confidence leaning line (D-907, issue #289; TABLE-AUTHORITY-A's rule carried to ContraDoc, D-670
item 2), read from saved run folders only: no model, no provider, nothing written to a run. Development records only
until the next freeze (D-902).

    py -3.12 -X utf8 tools/contradoc_leaning.py --pairs PAIRS.json [--threshold T] [--out OUT.json]
    py -3.12 -X utf8 tools/contradoc_leaning.py --self-test

PAIRS.json is [{"key": <a bundle's answer_key.json>, "run": <its run folder, holding audit/pairing_map.json>}], the
form tools/scitab_leaning_whatif.py reads. The key is read only by tools/score_corpus.benchmark_items, the adapter's
own labeller; this tool prints figures and counts only, never an item id, a gold label or any text.

The passage pair step (scripts/passage_pairs.py, `decision` form, D-887) asks every pair in both orders and saves each
order's decision in the pairing map (`passage_pairs[].decisions`, one row an order: `passages`, `settled`, `decided`,
`why`, `answers`). An order reads as its settled answer's declared class (config/passage_pairs.json: contradicts FLAG,
does not CLEAR, cannot tell UNDECIDED), UNDECIDED when it is not settled, FAILED when its call left no row. With
`--threshold` each order is settled again from its saved probabilities by choice_decision.settle (D-887's post hoc
reading); without it, as the run settled it.

A pair whose two orders are both FLAG is a detection; both CLEAR, clear; anything else (one UNDECIDED, the two
disagreeing, an order missing) is a LEANING, low confidence, counted by its kind (its two classes, sorted). THE
LEANING RULE (TABLE-AUTHORITY-A's, as SciTab counts a leaning: by the verdict the model's own top probability names):
a leaning counts as the direction of its stronger order. An order carries a direction when it is settled FLAG or
CLEAR, or unsettled below the threshold with "contradicts" or "does not" on top; a tie, no threshold, "cannot tell"
on top and a failed order carry none. The stronger order is the one of the higher top probability; two orders of
equal probability and opposite directions, or none with a direction, give no direction.

Three lines, each labelled:
  headline          the adapter's v2_primary label of every item (benchmark_items), its judgement accuracy and
                    contradictory precision, recall and F1. Nothing below reads into it: it is the same bytes with
                    or without the pair reading (check 696).
  post_hoc_threshold  only with --threshold: D-887's reading, a document is contradictory when its v2_primary label
                    is or one of its pairs is a detection at T; else its v2_primary label stands. No leaning.
  with_leanings     beside the line above it (the headline without --threshold), never instead: a document one of
                    whose leanings has the direction FLAG is contradictory, marked low confidence; a CLEAR leaning
                    changes nothing, the base label already reading not contradictory or undecided as it stands.
Counts: pairs by reading, leanings by kind and by direction, documents by reading (detection, leaning only, all
clear, no pairs), items moved by leanings and how many of those are right.

tools/coverage_check.py reads the same pairs (`document_reading`): a document whose pairs hold a leaning and no
detection is `leaning_only`, never the system's own answer in the headline's coverage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tools", ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import choice_decision  # noqa: E402

PAIRING_MAP = ("audit", "pairing_map.json")
PAIR_ROWS, DECISIONS = "passage_pairs", "decisions"
CONFIG_PATH = ROOT / "config" / "passage_pairs.json"
FLAG, CLEAR, UNDECIDED, FAILED = "FLAG", "CLEAR", "UNDECIDED", "FAILED"
DIRECTIONS = (FLAG, CLEAR)
DETECTION, CLEAR_PAIR, LEANING = "detection", "clear", "leaning"
NO_DIRECTION = "none"
DOC_DETECTION, DOC_LEANING_ONLY, DOC_ALL_CLEAR, DOC_NO_PAIRS = "detection", "leaning_only", "all_clear", "no_pairs"
BENCHMARK = "contradoc"
LEANING_RULE = ("a pair whose two orders are not both FLAG and not both CLEAR is a low-confidence leaning, counted as "
                "the direction of its stronger order (the order of the higher top probability among those settled FLAG "
                "or CLEAR or unsettled below the threshold with a verdict on top; a tie, no threshold, cannot tell on "
                "top and a failed order carry none); a FLAG leaning makes its document contradictory, low confidence; "
                "a CLEAR leaning changes nothing")
HEADLINE_LINE = "headline: v2_primary, the adapter's own labeller, unchanged by the leaning reading"
POST_HOC_LINE = "post hoc threshold (D-887): v2_primary or a pair both orders FLAG at the threshold; no leaning"
LEANING_LINE = "WITH LEANINGS, low confidence (D-907): beside the line above, never instead"


def answer_classes(path=CONFIG_PATH):
    """{declared answer label: class} of the pair question's decision form."""
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    return {a["label"]: a["class"] for a in config["decision"]["answers"]}


def _ranked(answers):
    return sorted(((str(k), float(v)) for k, v in answers.items()), key=lambda kv: -kv[1])


def order_reading(row, classes, threshold=None):
    """(class, direction or None, top probability) of one order's saved decision row. `threshold` given: settled
    again from the saved probabilities (choice_decision.settle); None: as the run settled it."""
    answers = row.get("answers") if isinstance(row, dict) else None
    if not isinstance(answers, dict) or len(answers) < 2:
        return FAILED, None, 0.0
    ranked = _ranked(answers)
    if threshold is not None:
        made = choice_decision.settle({"answers": [{"label": k, "probability": v} for k, v in ranked]}, threshold)
        settled, decided, why = made["settled"], made["decided"], made["why"]
    else:
        settled, decided, why = row.get("settled") is True, row.get("decided"), row.get("why")
    top_label, top = ranked[0]
    if settled:
        cls = classes.get(decided, UNDECIDED)
        return cls, (cls if cls in DIRECTIONS else None), top
    tie = ranked[0][1] == ranked[1][1]
    leans = why == choice_decision.BELOW_THRESHOLD and not tie and classes.get(top_label) in DIRECTIONS
    return UNDECIDED, (classes[top_label] if leans else None), top


def pairs_of(entry):
    """[[order row, ...]] of a document's pairing-map entry, one list a pair (its passages in either order). ContraDoc
    holds one rule a document: rows of more than one rule refuse."""
    rows = [r for r in (entry.get(PAIR_ROWS) if isinstance(entry, dict) else None) or [] if isinstance(r, dict)]
    rules = {str(r.get("rule_id")) for r in rows}
    if len(rules) > 1:
        raise ValueError("passage pair rows of %d rules in one document; ContraDoc holds one" % len(rules))
    pairs = {}
    for row in rows:
        for d in row.get(DECISIONS) or []:
            if isinstance(d, dict) and isinstance(d.get("passages"), list) and len(d["passages"]) == 2:
                pairs.setdefault(tuple(sorted(d["passages"])), []).append(d)
    return list(pairs.values())


def pair_reading(orders, classes, threshold=None):
    """(reading, kind, direction) of one pair: detection, clear or leaning; a leaning's kind is its two classes,
    sorted (a missing order FAILED), and its direction the stronger order's (module docstring)."""
    read = [order_reading(o, classes, threshold) for o in orders[:2]]
    read += [(FAILED, None, 0.0)] * (2 - len(read))
    names = [c for c, _d, _p in read]
    if names == [FLAG, FLAG]:
        return DETECTION, None, FLAG
    if names == [CLEAR, CLEAR]:
        return CLEAR_PAIR, None, CLEAR
    kind = "/".join(sorted(names))
    directed = [(p, d) for _c, d, p in read if d]
    if not directed:
        return LEANING, kind, None
    best = max(p for p, _d in directed)
    tops = {d for p, d in directed if p == best}
    return LEANING, kind, (tops.pop() if len(tops) == 1 else None)


def read_entry(entry, classes, threshold=None):
    """A document's pairs read: {pairs, detections, clear, leanings_by_kind, leanings_by_direction, document}."""
    out = {"pairs": 0, "detections": 0, "clear": 0, "leanings_by_kind": {}, "leanings_by_direction": {}}
    for orders in pairs_of(entry):
        reading, kind, direction = pair_reading(orders, classes, threshold)
        out["pairs"] += 1
        if reading == DETECTION:
            out["detections"] += 1
        elif reading == CLEAR_PAIR:
            out["clear"] += 1
        else:
            out["leanings_by_kind"][kind] = out["leanings_by_kind"].get(kind, 0) + 1
            key = direction or NO_DIRECTION
            out["leanings_by_direction"][key] = out["leanings_by_direction"].get(key, 0) + 1
    leanings = sum(out["leanings_by_kind"].values())
    out["document"] = (DOC_NO_PAIRS if not out["pairs"] else DOC_DETECTION if out["detections"]
                       else DOC_LEANING_ONLY if leanings else DOC_ALL_CLEAR)
    return out


def pairing_entry(run_dir, document_id):
    """The document's entry of a run folder's pairing map, or None."""
    path = Path(run_dir).joinpath(*PAIRING_MAP)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    entry = data.get(str(document_id))
    if isinstance(entry, dict):
        return entry
    return data if PAIR_ROWS in data else (next(iter(data.values())) if len(data) == 1 else None)


def document_reading(run_dir, document_id, classes=None, threshold=None):
    """read_entry of a run folder's document, or None when its pairing map holds no entry."""
    entry = pairing_entry(run_dir, document_id)
    return None if entry is None else read_entry(entry, classes or answer_classes(), threshold)


def _adapter():
    import score_corpus
    return score_corpus._adapter_for(BENCHMARK)


def headline_items(pairs):
    """[(document index, item row)] of every key's items as the adapter's v2_primary labeller gives them."""
    import score_corpus
    out = []
    for n, pair in enumerate(pairs):
        key = json.loads(Path(pair["key"]).read_text(encoding="utf-8"))
        if str(key.get("benchmark")) != BENCHMARK:
            raise SystemExit("a key is not a ContraDoc key")
        got = score_corpus.benchmark_items(key, Path(pair["run"]))
        if got.get("availability") != "labelled":
            raise SystemExit("a run was not labelled by the adapter")
        out.extend((n, row) for row in got["items"] if row.get("gold_class"))
    return out


def figures(rows, field):
    """The adapter's own measures over (label, gold label): judgement accuracy, ABSTAIN counted wrong, and
    contradictory precision, recall and F1."""
    adapter = _adapter()
    spec, metrics = adapter.SPEC, adapter.metrics
    pairs = [(spec.label(r[field]), spec.label(r["gold_class"])) for r in rows]
    scores = metrics.class_scores(pairs, spec.labels[FLAG])
    return {"items": len(pairs), "accuracy": metrics.accuracy(pairs)["accuracy"],
            "contradictory": {k: scores[k] for k in ("precision", "recall", "f1", "tp", "fp", "fn")}}


def headline_line(items):
    """The headline: the v2_primary rows alone, nothing of the pair reading."""
    return dict(figures([r for _n, r in items], "b3_class"), line=HEADLINE_LINE,
                measure="judgement accuracy, ABSTAIN counted wrong")


def with_leanings(base, reading):
    """The class with leanings of one item: FLAG when a leaning of its document has the direction FLAG and its base
    is not FLAG already; else its base."""
    if base != FLAG and reading and reading["leanings_by_direction"].get(FLAG):
        return FLAG
    return base


def at_threshold(base, reading):
    return FLAG if reading and reading["detections"] else base


def _add(total, part):
    for k, v in part.items():
        total[k] = total.get(k, 0) + v


def score(pairs, threshold=None):
    """Every line and count of the module docstring, figures and counts only."""
    classes = answer_classes()
    items = headline_items(pairs)
    headline = headline_line(items)
    readings, documents, totals = {}, {}, {"pairs": 0, "detections": 0, "clear": 0}
    kinds, directions = {}, {}
    for n, pair in enumerate(pairs):
        key = json.loads(Path(pair["key"]).read_text(encoding="utf-8"))
        doc_id = str(key.get("document") or "").rsplit(".", 1)[0]
        reading = document_reading(pair["run"], doc_id, classes, threshold)
        readings[n] = reading
        name = reading["document"] if reading else DOC_NO_PAIRS
        documents[name] = documents.get(name, 0) + 1
        if reading:
            for k in totals:
                totals[k] += reading[k]
            _add(kinds, reading["leanings_by_kind"])
            _add(directions, reading["leanings_by_direction"])
    rows = []
    for n, r in items:
        base = at_threshold(r["b3_class"], readings[n]) if threshold is not None else r["b3_class"]
        rows.append(dict(r, base_class=base, leaning_class=with_leanings(base, readings[n])))
    moved = [r for r in rows if r["leaning_class"] != r["base_class"]]
    out = {"label": "ContraDoc development reading from saved records, not a system run (D-907, TABLE-AUTHORITY-A)",
           "documents": len(pairs), "threshold": threshold, "headline": headline,
           "with_leanings": dict(figures(rows, "leaning_class"), line=LEANING_LINE, rule=LEANING_RULE,
                                 low_confidence_items=len(moved),
                                 moved_and_right=sum(1 for r in moved if r["leaning_class"] == r["gold_class"])),
           "pairs": dict(totals, leanings=sum(kinds.values()), leanings_by_kind=dict(sorted(kinds.items())),
                         leanings_by_direction=dict(sorted(directions.items()))),
           "documents_by_reading": dict(sorted(documents.items()))}
    if threshold is not None:
        out["post_hoc_threshold"] = dict(figures(rows, "base_class"), line=POST_HOC_LINE)
    return out


def lines(result):
    """The two labelled lines (three with a threshold), figures and counts only."""
    h, w, p = result["headline"], result["with_leanings"], result["pairs"]
    out = ["HEADLINE (v2_primary, unchanged): accuracy %.4f, contradictory F1 %.4f, %d items"
           % (h["accuracy"], h["contradictory"]["f1"], h["items"])]
    if "post_hoc_threshold" in result:
        t = result["post_hoc_threshold"]
        out.append("POST HOC THRESHOLD %s (D-887, no leaning): accuracy %.4f, contradictory F1 %.4f"
                   % (result["threshold"], t["accuracy"], t["contradictory"]["f1"]))
    out.append("WITH LEANINGS (low confidence, labelled; beside, never instead): accuracy %.4f, contradictory F1 %.4f; "
               "%d items moved, %d of them right; leanings %d by kind %s, by direction %s"
               % (w["accuracy"], w["contradictory"]["f1"], w["low_confidence_items"], w["moved_and_right"],
                  p["leanings"], json.dumps(p["leanings_by_kind"], sort_keys=True),
                  json.dumps(p["leanings_by_direction"], sort_keys=True)))
    return out


def self_test():
    """The pair rule on invented decision rows, no key."""
    classes = {"contradicts": FLAG, "does not": CLEAR, "cannot tell": UNDECIDED}

    def row(top, p, settled=True, why=None, passages=(0, 1)):
        rest = (1 - p) / 2
        return {"passages": list(passages), "settled": settled, "decided": top if settled else "cannot be settled",
                "why": why, "answers": {a: (p if a == top else rest) for a in classes}}
    below = choice_decision.BELOW_THRESHOLD
    flag, clear, unclear = row("contradicts", .9), row("does not", .9), row("cannot tell", .8)
    assert pair_reading([flag, flag], classes) == (DETECTION, None, FLAG)
    assert pair_reading([clear, clear], classes) == (CLEAR_PAIR, None, CLEAR)
    assert pair_reading([flag, unclear], classes) == (LEANING, "FLAG/UNDECIDED", FLAG)
    assert pair_reading([flag, row("does not", .95)], classes) == (LEANING, "CLEAR/FLAG", CLEAR), "the stronger order"
    assert pair_reading([row("contradicts", .5, False, below), clear], classes)[2] == CLEAR
    assert pair_reading([row("contradicts", .5, False, below), unclear], classes)[2] == FLAG, "below the threshold leans"
    assert pair_reading([row("contradicts", .5, False, "no_threshold"), unclear], classes)[2] is None, "no threshold"
    assert pair_reading([flag], classes) == (LEANING, "FAILED/FLAG", FLAG), "a missing order"
    assert pair_reading([row("contradicts", .5, False, "no_threshold")] * 2, classes, .4) == (DETECTION, None, FLAG)
    assert pair_reading([row("contradicts", .5, False, "no_threshold")] * 2, classes, .6)[0] == LEANING
    entry = {PAIR_ROWS: [{"rule_id": "R", DECISIONS: [flag, dict(unclear, passages=[1, 0]), clear, clear]}]}
    got = read_entry(entry, classes)
    assert got["document"] == DOC_LEANING_ONLY and got["leanings_by_direction"] == {FLAG: 1}, got
    return "self-test passed"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pairs", type=Path, help="[{key, run}] of the development documents")
    ap.add_argument("--threshold", type=float, help="D-887's post hoc threshold, applied to the saved probabilities")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        print(self_test())
        return 0
    if not args.pairs:
        ap.error("--pairs is required")
    result = score(json.loads(args.pairs.read_text(encoding="utf-8")), args.threshold)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
