"""The measures of preregistration section 3, with section 4's ABSTAIN and zero-division
rules. A measure here is never comparable with a published number computed on another
metric or split, and every result says so.

ABSTAIN in every precision, recall or F1 is a prediction of a class that matches no
gold label: a false negative for the item's gold class and a false positive for no
class. A zero denominator gives 0 (scikit-learn's zero_division=0) and is counted.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import bundle, mapping

ABSTAIN = mapping.ABSTAIN
NOT_COMPARABLE = ("Not comparable with published numbers: computed on this preregistration's "
                  "split, sample and mapping, and where marked on a measure other than the "
                  "official one.")


def _ratio(num, den, zero):
    if den == 0:
        zero[0] += 1
        return 0.0
    return num / den


def class_scores(pairs, cls) -> dict:
    """Precision, recall and F1 of one class over (predicted, gold) label pairs. F1 is
    2tp / (2tp + fp + fn), as scikit-learn computes it, so its denominator is zero only
    when tp, fp and fn are all zero."""
    zero = [0]
    tp = sum(1 for p, g in pairs if p == cls and g == cls)
    fp = sum(1 for p, g in pairs if p == cls and g != cls)
    fn = sum(1 for p, g in pairs if g == cls and p != cls)
    precision = _ratio(tp, tp + fp, zero)
    recall = _ratio(tp, tp + fn, zero)
    f1 = _ratio(2 * tp, 2 * tp + fp + fn, zero)
    return {"class": cls, "tp": tp, "fp": fp, "fn": fn, "precision": precision,
            "recall": recall, "f1": f1, "zero_denominators": zero[0]}


def macro_f1(pairs, classes) -> dict:
    per = [class_scores(pairs, c) for c in classes]
    return {"macro_f1": sum(s["f1"] for s in per) / len(per) if per else 0.0,
            "per_class": per, "zero_denominators": sum(s["zero_denominators"] for s in per)}


def accuracy(pairs) -> dict:
    """ABSTAIN counted wrong."""
    zero = [0]
    value = _ratio(sum(1 for p, g in pairs if p == g and p != ABSTAIN), len(pairs), zero)
    return {"accuracy": value, "n": len(pairs), "zero_denominators": zero[0]}


def coverage(pairs) -> dict:
    zero = [0]
    answered = [(p, g) for p, g in pairs if p != ABSTAIN]
    return {"coverage": _ratio(len(answered), len(pairs), zero), "answered": len(answered),
            "accuracy_on_answered": _ratio(sum(1 for p, g in answered if p == g), len(answered), zero),
            "zero_denominators": zero[0]}


def confusion(pairs, classes) -> dict:
    """{gold: {predicted: count}}, ABSTAIN as a predicted column."""
    columns = list(classes) + [ABSTAIN]
    table = {g: {p: 0 for p in columns} for g in classes}
    for p, g in pairs:
        table.setdefault(g, {c: 0 for c in columns})
        table[g][p if p in columns else ABSTAIN] += 1
    return table


# ---------------------------------------------------------------------------
# one arm, all measures


def read_gold(bundles_dir) -> tuple:
    """(answer rows by item id, parts record by document id) from a build folder."""
    root = Path(bundles_dir)
    parts = json.loads((root / bundle.PARTS_RECORD_NAME).read_text(encoding="utf-8"))
    answers, documents = {}, {}
    for record in parts["documents"]:
        documents[record["document_id"]] = record
        key = json.loads((root / record["document_id"] / bundle.ANSWER_NAME).read_text(encoding="utf-8"))
        for row in key["items"]:
            answers[row["item_id"]] = dict(row, document_id=record["document_id"])
    return answers, documents


def _units(bundles_dir, document_id):
    path = Path(bundles_dir) / document_id / bundle.CONTEXT_DIR / (document_id + ".md")
    return {uid: text for uid, _h, _l, text in bundle.read_units(path.read_text(encoding="utf-8"))}


def score_arm(spec, labels: dict, bundles_dir, headline) -> dict:
    """Every measure for one arm's labels. `headline(pairs, rows, answers, unit_text)`
    returns the benchmark's own metric block (section 3.1); unit_text(document id, unit
    id) is the unit's text as written in the bundle."""
    answers, documents = read_gold(bundles_dir)
    rows = labels["labels"]
    missing = [r["item_id"] for r in rows if r["item_id"] not in answers]
    if missing:
        raise ValueError("labels for items with no gold: " + ", ".join(missing[:5]))
    labelled_docs = {r["document_id"] for r in rows}
    labelled = {r["item_id"] for r in rows}
    unlabelled = sorted(i for i, a in answers.items()
                        if a["document_id"] in labelled_docs and i not in labelled)
    if unlabelled:
        raise ValueError("gold items of a labelled document have no label: " + ", ".join(unlabelled[:5]))
    pairs = [(r["label"], answers[r["item_id"]]["gold"]) for r in rows]
    flag, clear = spec.labels[mapping.FLAG], spec.labels[mapping.CLEAR]
    gold_flag = [r for r in rows if answers[r["item_id"]]["gold"] == flag]
    catches = [r for r in gold_flag if r["class"] == mapping.FLAG]
    measurable = [r for r in gold_flag if answers[r["item_id"]]["location_measurable"]]
    unit_cache = {}

    def located(row):
        """B2, B3, B4: a deciding record cites a unit holding the evidence (unit ids
        compared without regard to case). B1: any one sentence of its `evidence` string
        (split by the section 1 sentence rule) lies, whitespace-normalised, in a unit
        holding the evidence."""
        evidence = {u.casefold() for u in answers[row["item_id"]]["evidence_unit_ids"]}
        if row["class"] != mapping.FLAG or not evidence:
            return False
        if row["arm"] != "B1":
            return bool(evidence & {u.casefold() for u in row["cited_unit_ids"]})
        quoted = bundle.sentences(row.get("evidence") or "")
        return any(s in bundle.normalise_space(unit_text(row["document_id"], u))
                   for s in quoted for u in evidence)

    def unit_text(document_id, uid):
        units = unit_cache.setdefault(document_id, {
            k.casefold(): v for k, v in _units(bundles_dir, document_id).items()})
        return units.get(uid.casefold(), "")

    zero = [0]
    if measurable:
        location = {"measure": "location recall over FLAG items whose evidence is marked",
                    "value": _ratio(
            sum(1 for r in measurable if located(r)), len(measurable), zero),
            "flag_items_measurable": len(measurable)}
    else:
        location = {"measure": "recall on FLAG (location not measurable)", "value": _ratio(
            len(catches), len(gold_flag), zero), "flag_items_measurable": 0}
    location["zero_denominators"] = zero[0]
    used_docs = sorted({r["document_id"] for r in rows})
    unattached = [d["unattached"] for d in labels.get("documents", []) if d.get("unattached")]
    per_deliverable = {}
    for u in unattached:
        for name, count in u["per_deliverable"].items():
            if count is not None:
                per_deliverable[name] = per_deliverable.get(name, 0) + count
    return {
        "benchmark": spec.name, "arm": labels["arm"], "analysis": labels.get("analysis", "primary"),
        "comparability": NOT_COMPARABLE,
        "decisions": len(rows), "documents": len(used_docs),
        "clusters": len({documents[d]["cluster"] for d in used_docs if d in documents}),
        "headline": headline(pairs, rows, answers, unit_text),
        "coverage": coverage(pairs),
        "location": location,
        "false_positives": {"item_level": sum(
            1 for r in rows if r["class"] == mapping.FLAG and answers[r["item_id"]]["gold"] == clear),
            "unattached_findings": sum(u["count"] for u in unattached),
            "unattached_per_deliverable": dict(sorted(per_deliverable.items()))},
        "refusals": {"items_from_refusal": labels["counts"]["refusals"],
                     "run_failure_documents": labels["counts"]["run_failure_documents"]},
        "catch_layer": {k: sum(1 for r in catches if r["layer"] == k)
                        for k in ("computed", "judged", "both")},
        "counts": labels["counts"],
        "cut_documents": sum(1 for d in used_docs if documents.get(d, {}).get("cut", {}).get("cut")),
    }
