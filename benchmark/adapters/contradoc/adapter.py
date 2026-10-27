"""ContraDoc adapter (preregistration sections 1, 3, 5.2, 5.5, 5.6).

One item per document, one rule for every document (CONV-CDOC-01). The document is the
`text` field verbatim, one part per blank-line paragraph, no sentence splitter. The
split key is the near-duplicate group's key (section 1): documents sharing 80 percent
or more of their sentences are grouped, and the group's key is its smallest `unique id`.

Developed on hand-written synthetic items only (D-019): no ContraDoc data was opened.

Usage:
    py -3.12 benchmark/adapters/contradoc/adapter.py build --input <file> --out <folder>
    py -3.12 benchmark/adapters/contradoc/adapter.py split --input <file>
    py -3.12 benchmark/adapters/contradoc/adapter.py label --items <items.json> --arm B3 --runs <folder> --out <labels.json>
    py -3.12 benchmark/adapters/contradoc/adapter.py score --labels <labels.json> --bundles <folder> --out <metrics.json>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from common import bundle, cli, ids, mapping, metrics  # noqa: E402

BENCHMARK = "contradoc"
RULE_ID = "CONV-CDOC-01"
RULE_NAME = "Consistency"
RULE_TEXT = ("No passage of the document may contain a statement that cannot be true together "
             "with another statement in the same passage or in another passage of the document.")
GROUP_SHARE = 0.8

# --- source schema --------------------------------------------------------------------
DOCUMENT_ID_FIELD = "unique id"   # documented (SELECTION.md)
TEXT_FIELD = "text"               # named by the preregistration (section 5.6)
LABEL_FIELD = "label"             # PROVISIONAL: not documented outside the data
GOLD_VALUES = {"contradictory": "contradictory",           # PROVISIONAL: stored values
               "not contradictory": "not contradictory"}
EVIDENCE_FIELD = "evidence"       # PROVISIONAL: the marked evidence sentence
REFERENCE_FIELD = "reference"     # PROVISIONAL: the marked reference sentence or sentences
# PROVISIONAL: the file holds a JSON list of records, or a JSON object whose values are records.
# ---------------------------------------------------------------------------------------

SPEC = mapping.Spec(
    BENCHMARK,
    labels={mapping.FLAG: "contradictory", mapping.CLEAR: "not contradictory",
            mapping.UNDECIDED: None},
    b1_labels={"contradictory": mapping.FLAG, "not_contradictory": mapping.CLEAR,
               "undecided": mapping.UNDECIDED},
    s2=True)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def read_source(path) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = list(data.values()) if isinstance(data, dict) else data
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ValueError("expected a list of records or an object of records")
    return records


def sentences(text: str) -> set:
    """Runs of text ended by `.`, `!` or `?` followed by whitespace, or by the end of the
    text, each compared after collapsing whitespace."""
    return {s for s in (" ".join(p.split()) for p in _SENTENCE_END.split(text)) if s}


def _smallest(values):
    if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return min(values)
    return min(values, key=ids.key_string)


def groups(records) -> dict:
    """{key string of a unique id: group key} by the near-duplicate rule: share = shared
    distinct sentences over the distinct sentences of the document with fewer of them;
    linked at 0.8 or more; groups are connected components; key = smallest unique id."""
    sids = [r[DOCUMENT_ID_FIELD] for r in records]
    sets = [sentences(r[TEXT_FIELD]) for r in records]
    parent = list(range(len(records)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            shorter = min(len(sets[i]), len(sets[j]))
            if shorter and len(sets[i] & sets[j]) / shorter >= GROUP_SHARE:
                parent[find(i)] = find(j)
    members = {}
    for i in range(len(records)):
        members.setdefault(find(i), []).append(sids[i])
    out = {}
    for group in members.values():
        key = _smallest(group)
        for sid in group:
            out[ids.key_string(sid)] = key
    return out


def _gold(record) -> str:
    value = record.get(LABEL_FIELD)
    if value not in GOLD_VALUES:
        raise ValueError("unrecognised %s value %r for %s" % (LABEL_FIELD, value, record.get(DOCUMENT_ID_FIELD)))
    return GOLD_VALUES[value]


def _texts(value) -> list:
    if value is None:
        return []
    return [value] if isinstance(value, str) else [str(v) for v in value]


def documents(records) -> list:
    seen = set()
    for r in records:
        key = ids.key_string(r[DOCUMENT_ID_FIELD])
        if key in seen:
            raise ValueError("duplicate unique id " + key)
        seen.add(key)
    group_of = groups(records)
    out = []
    for r in records:
        sid, text = r[DOCUMENT_ID_FIELD], r[TEXT_FIELD]
        gold = _gold(r)
        evidence = _texts(r.get(EVIDENCE_FIELD))
        references = _texts(r.get(REFERENCE_FIELD))
        flag = gold == SPEC.labels[mapping.FLAG]
        doc_id = ids.opaque_document_id(BENCHMARK, sid)
        item_id = ids.opaque_item_id(BENCHMARK, sid)
        group = group_of[ids.key_string(sid)]
        out.append({
            "document_id": doc_id, "source_document_id": sid,
            "split_key": group, "cluster": group, "source_words": ids.word_count(text),
            "parts": [{"text": text[s:e], "source": {"start": s, "end": e}}
                      for s, e in bundle.blank_line_paragraphs(text)],
            "rules": [{"rule_id": RULE_ID, "name": RULE_NAME, "text": RULE_TEXT}],
            "items": [{
                "item_id": item_id, "source_item_id": sid, "rule_id": RULE_ID, "gold": gold,
                "location_measurable": bool(flag and (evidence or references)),
                "evidence_texts": (evidence + references) if flag else [],
                "extra": {"evidence_sentence": bundle.normalise_space(" ".join(evidence)) if flag else ""},
            }],
        })
    return out


def split_rows(records, _args=None) -> list:
    group_of = groups(records)
    rows = []
    for r in records:
        key = group_of[ids.key_string(r[DOCUMENT_ID_FIELD])]
        rows.append({"source_document_id": r[DOCUMENT_ID_FIELD], "split_key": ids.key_string(key),
                     "side": ids.split_side(key)})
    return sorted(rows, key=lambda x: ids.key_string(x["source_document_id"]))


def headline(pairs, rows, answers, unit_text) -> dict:
    """Judgement accuracy (headline), precision, recall and F1 for contradictory, and the
    replacement for Evidence Hit Rate (not the official measure)."""
    flag = SPEC.labels[mapping.FLAG]
    hits, marked = 0, 0
    for row in rows:
        answer = answers[row["item_id"]]
        needle = answer.get("evidence_sentence") or ""
        if answer["gold"] != flag or not needle:
            continue
        marked += 1
        if row["class"] != mapping.FLAG:
            continue
        if row["arm"] == "B1":
            hits += needle in bundle.normalise_space(row.get("evidence") or "")
        else:
            hits += any(needle in bundle.normalise_space(unit_text(row["document_id"], u))
                        for u in row["cited_unit_ids"])
    zero = [0]
    return {"accuracy": metrics.accuracy(pairs),
            "contradictory": metrics.class_scores(pairs, flag),
            "evidence_containment": {
                "measure": "exact containment of the marked evidence sentence, whitespace-"
                           "normalised (not the official Evidence Hit Rate)",
                "value": metrics._ratio(hits, marked, zero), "marked": marked,
                "zero_denominators": zero[0]}}


if __name__ == "__main__":
    sys.exit(cli.main(sys.modules[__name__]))
