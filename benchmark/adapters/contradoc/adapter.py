"""ContraDoc adapter (preregistration sections 1, 3, 5.2, 5.5, 5.6).

One item per document, one rule for every document (CONV-CDOC-01). The document is the
`text` field verbatim, one part per blank-line paragraph, no sentence splitter. The
split key is the near-duplicate group's key (section 1): documents sharing 80 percent
or more of their sentences are grouped, and the group's key is its smallest `unique id`.

Groups are computed ONCE, on the whole input B-dev receives, by `split --out <file>`;
that file is frozen and its SHA-256 recorded. `build --assignment <file>` reads each
document's group and side from it (a document it does not list is refused), so a build
from a sample never regroups. Only `build --development` may compute groups over its own
input, and parts.json records which was done.

Written on hand-written synthetic items (D-019); the source schema below was then
confirmed on the B-dev development items (S4c item 4). `--assignment` also reads the
split file B-dev wrote with its own implementation of section 1.

Usage:
    py -3.12 benchmark/adapters/contradoc/adapter.py build --input <file> --out <folder>
    py -3.12 benchmark/adapters/contradoc/adapter.py split --input <file>
    py -3.12 benchmark/adapters/contradoc/adapter.py label --items <items.json> --arm B3 --runs <folder> --out <labels.json>
    py -3.12 benchmark/adapters/contradoc/adapter.py score --labels <labels.json> --bundles <folder> --out <metrics.json>
"""
from __future__ import annotations

import json
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
# Confirmed on the B-dev development items (184 documents), unless marked otherwise.
DOCUMENT_ID_FIELD = "unique id"   # documented; stored as a string in every record
TEXT_FIELD = "text"               # confirmed: a string in every record
# The file is a JSON object of two containers, each an object {unique id: record}; the
# container gives the gold label (there is no label field in any record). The key of each
# record equals its `unique id`.
GOLD_CONTAINERS = {"pos": "contradictory", "neg": "not contradictory"}   # confirmed
EVIDENCE_FIELD = "evidence"       # confirmed: one string, in every `pos` record, none in `neg`
REFERENCE_FIELD = "ref sentences" # confirmed: a string or a list of strings, absent in some
                                  # `pos` records and in every `neg` record
# ---------------------------------------------------------------------------------------

SPEC = mapping.Spec(
    BENCHMARK,
    labels={mapping.FLAG: "contradictory", mapping.CLEAR: "not contradictory",
            mapping.UNDECIDED: None},
    b1_labels={"contradictory": mapping.FLAG, "not_contradictory": mapping.CLEAR,
               "undecided": mapping.UNDECIDED},
    s2=True)


CONTAINER_KEY = "__container__"   # the adapter's own note on each record read, never a source field


def read_source(path) -> list:
    """Every record of both containers, in file order, each a copy carrying the name of
    its container under CONTAINER_KEY. Refuses another shape, a record whose key is not its
    `unique id`, and an id found in both containers."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data or set(data) - set(GOLD_CONTAINERS):
        raise ValueError("expected an object whose keys are %s" % " and ".join(sorted(GOLD_CONTAINERS)))
    records, seen = [], set()
    for container in data:
        entries = data[container]
        if not isinstance(entries, dict) or not all(isinstance(r, dict) for r in entries.values()):
            raise ValueError("the %r container is not an object of records" % container)
        for key, record in entries.items():
            if CONTAINER_KEY in record:
                raise ValueError("a record carries the adapter's own key " + CONTAINER_KEY)
            if ids.key_string(record.get(DOCUMENT_ID_FIELD)) != key:
                raise ValueError("record %r carries %s %r" % (key, DOCUMENT_ID_FIELD, record.get(DOCUMENT_ID_FIELD)))
            if key in seen:
                raise ValueError("unique id %s is in both containers" % key)
            seen.add(key)
            records.append(dict(record, **{CONTAINER_KEY: container}))
    return records


def sentences(text: str) -> set:
    """The section 1 sentence rule (common/bundle.py), as a set."""
    return set(bundle.sentences(text))


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
    return GOLD_CONTAINERS[record[CONTAINER_KEY]]


def _texts(value) -> list:
    """A field held as a string or as a list of strings, as a list (empty when absent)."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return list(value)
    raise ValueError("expected a string or a list of strings, not " + type(value).__name__)


def read_assignment(path) -> dict:
    """{key string of a unique id: (group key, side)} from a frozen split file: the one
    `split --out` writes (`documents`, a list of rows), or the one B-dev wrote with its own
    implementation of section 1 (`assignments`, {unique id: {group, side}}). Either way a
    side that is not the hash rule on its group key is refused."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or str(data.get("benchmark", "")).lower() != BENCHMARK:
        raise ValueError("the assignment file is not a ContraDoc split file")
    if isinstance(data.get("documents"), list):
        rows = {ids.key_string(r["source_document_id"]): (r["split_key"], r["side"])
                for r in data["documents"]}
    elif isinstance(data.get("assignments"), dict):
        rows = {ids.key_string(sid): (r["group"], r["side"]) for sid, r in data["assignments"].items()}
    else:
        raise ValueError("the assignment file holds neither `documents` nor `assignments`")
    wrong = sorted(sid for sid, (group, side) in rows.items() if ids.split_side(group) != side)
    if wrong:
        raise ValueError("assignment sides that are not the hash rule on their group key: "
                         + ", ".join(wrong[:10]))
    return rows


def documents(records, options=None) -> list:
    options = options or {}
    seen = set()
    for r in records:
        key = ids.key_string(r[DOCUMENT_ID_FIELD])
        if key in seen:
            raise ValueError("duplicate unique id " + key)
        seen.add(key)
    if options.get("assignment"):
        assigned = read_assignment(options["assignment"])
        missing = sorted(k for k in seen if k not in assigned)
        if missing:
            raise ValueError("documents the assignment file does not list: " + ", ".join(missing[:10]))
        groups_from = "assignment"
    elif options.get("development"):
        group_of = groups(records)
        assigned = {k: (ids.key_string(g), ids.split_side(g)) for k, g in group_of.items()}
        groups_from = "input (development build)"
    else:
        raise ValueError("ContraDoc needs --assignment (the frozen split file) outside --development")
    out = []
    for r in records:
        sid, text = r[DOCUMENT_ID_FIELD], r[TEXT_FIELD]
        gold = _gold(r)
        evidence = _texts(r.get(EVIDENCE_FIELD))
        references = _texts(r.get(REFERENCE_FIELD))
        flag = gold == SPEC.labels[mapping.FLAG]
        doc_id = ids.opaque_document_id(BENCHMARK, sid)
        item_id = ids.opaque_item_id(BENCHMARK, sid)
        group, side = assigned[ids.key_string(sid)]
        out.append({
            "document_id": doc_id, "source_document_id": sid,
            "split_key": group, "side": side, "cluster": group,
            "record_extra": {"groups_from": groups_from},
            "parts": [{"text": text[s:e], "words": ids.word_count(text[s:e]),
                       "source": {"start": s, "end": e}}
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
