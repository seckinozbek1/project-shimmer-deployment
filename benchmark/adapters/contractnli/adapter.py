"""ContractNLI adapter (preregistration sections 1, 3, 5.2, 5.5, 5.6; decision D-S3).

One item per document and hypothesis (17 fixed hypotheses per non-disclosure agreement),
one rule per hypothesis (CONV-CNLI-<hypothesis key>), the hypothesis text the only slot.
The document is the agreement's text, one part per blank-line paragraph. The split is
official: the dev split is development, the test split the holdout pool, the train split
is not used. FLAG = Contradiction, UNDECIDED = NotMentioned (a refusal: the agreement
does not settle the hypothesis), CLEAR = Entailment (an ok record or silence); a run
failure is ABSTAIN, never NotMentioned.

Written on hand-written synthetic items (H17), then confirmed on the B-dev development
items (S4c item 4). The operator accepted the download terms (D-S3); only role B
downloads. On the development items no agreement's text holds a blank line, so each
agreement is one part under the section 5.6 rule.

Usage: as the ContraDoc adapter (build, label, score), and
    py -3.12 benchmark/adapters/contractnli/adapter.py split --input <file> --official development|holdout
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

BENCHMARK = "contractnli"
RULE_NAME = "Hypothesis"
RULE_TEMPLATE = ("Hypothesis about the agreement: {hypothesis} The hypothesis must agree with the "
                 "passages of the agreement. If the agreement does not settle the hypothesis, emit "
                 "UNCERTAIN.")

# --- source schema: the release's JSON, confirmed on the B-dev development items -------
# (dev.json: 61 agreements, 17 hypotheses, 1,037 items.)
DOCUMENTS_FIELD = "documents"           # confirmed: the list of agreements
DOCUMENT_ID_FIELD = "id"                # confirmed: an integer, unique across the splits
TEXT_FIELD = "text"                     # confirmed: the agreement's text
SPANS_FIELD = "spans"                   # confirmed: [[start, end], ...] character spans that
                                        # segment the text; none crosses a line break
ANNOTATION_SETS_FIELD = "annotation_sets"   # confirmed: one set per agreement; the first is used
ANNOTATIONS_FIELD = "annotations"       # confirmed: {hypothesis key: {choice, spans}}, all 17 keys
CHOICE_FIELD = "choice"                 # confirmed
EVIDENCE_FIELD = "spans"                # confirmed: integer indices into the document's spans,
                                        # present on every Contradiction, empty on NotMentioned
LABELS_FIELD = "labels"                 # confirmed: {hypothesis key: {short_description, hypothesis}}
HYPOTHESIS_FIELD = "hypothesis"         # confirmed
GOLD_VALUES = {"Entailment": "entailment", "Contradiction": "contradiction",   # confirmed
               "NotMentioned": "not mentioned"}
# The hypothesis keys are `nda-1` ... `nda-20` (17 of them), so rule ids read CONV-CNLI-NDA-1.
# ---------------------------------------------------------------------------------------
SPLIT_OPTIONS = (("--official", "development (the dev split) or holdout (the test split)"),)

SPEC = mapping.Spec(
    BENCHMARK,
    labels={mapping.FLAG: "contradiction", mapping.CLEAR: "entailment",
            mapping.UNDECIDED: "not mentioned"},
    b1_labels={"contradiction": mapping.FLAG, "entailment": mapping.CLEAR,
               "not mentioned": mapping.UNDECIDED},
    s2=False)
CLASSES = ("entailment", "contradiction", "not mentioned")


def read_source(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or DOCUMENTS_FIELD not in data or LABELS_FIELD not in data:
        raise ValueError("expected an object with %r and %r" % (DOCUMENTS_FIELD, LABELS_FIELD))
    return data


def rule_id(key) -> str:
    """CONV-CNLI- followed by the hypothesis key, upper-cased, every run of characters other
    than letters and digits written as one `-`."""
    return "CONV-CNLI-" + re.sub(r"[^A-Za-z0-9]+", "-", str(key)).strip("-").upper()


def documents(data, options=None) -> list:
    """The agreements. The side is the declared official split (section 1)."""
    options = options or {}
    side = options.get("side") or "official (undeclared, development build)"
    hypotheses = data[LABELS_FIELD]
    keys = sorted(hypotheses)
    if len({rule_id(k) for k in keys}) != len(keys):
        raise ValueError("two hypothesis keys make the same rule id")
    seen, out = set(), []
    for record in data[DOCUMENTS_FIELD]:
        sid = record[DOCUMENT_ID_FIELD]
        if ids.key_string(sid) in seen:
            raise ValueError("duplicate document id " + ids.key_string(sid))
        seen.add(ids.key_string(sid))
        text = record[TEXT_FIELD]
        paragraphs = bundle.blank_line_paragraphs(text)
        annotations = record[ANNOTATION_SETS_FIELD][0][ANNOTATIONS_FIELD]
        spans = record.get(SPANS_FIELD) or []
        rules, items = [], []
        for key in keys:
            if key not in annotations:
                raise ValueError("document %s has no annotation for %s" % (ids.key_string(sid), key))
            note = annotations[key]
            if note.get(CHOICE_FIELD) not in GOLD_VALUES:
                raise ValueError("unrecognised choice %r for %s" % (note.get(CHOICE_FIELD), key))
            gold = GOLD_VALUES[note[CHOICE_FIELD]]
            evidence = []
            for index in note.get(EVIDENCE_FIELD) or []:
                start, end = spans[int(index)]
                evidence += [k for k, (s, e) in enumerate(paragraphs, start=1)
                             if s < end and start < e and k not in evidence]
            rid = rule_id(key)
            rules.append({"rule_id": rid, "name": RULE_NAME, "text": RULE_TEMPLATE.format(
                hypothesis=bundle.one_space(hypotheses[key][HYPOTHESIS_FIELD]))})
            items.append({"item_id": ids.opaque_item_id(BENCHMARK, "%s:%s" % (ids.key_string(sid), key)),
                          "source_item_id": "%s:%s" % (ids.key_string(sid), key), "rule_id": rid,
                          "gold": gold, "evidence_parts": sorted(evidence),
                          "location_measurable": bool(evidence) and gold == SPEC.labels[mapping.FLAG],
                          "extra": {"hypothesis_key": key}})
        out.append({
            "document_id": ids.opaque_document_id(BENCHMARK, sid), "source_document_id": sid,
            "split_key": sid, "cluster": sid, "side": side,
            "parts": [{"text": text[s:e], "words": ids.word_count(text[s:e]),
                       "source": {"start": s, "end": e}} for s, e in paragraphs],
            "rules": rules, "items": items})
    return out


def split_rows(data, args=None) -> list:
    """The official side of every agreement: the dev split is development, the test split
    the holdout pool (section 1)."""
    side = getattr(args, "official", None)
    if side not in (ids.DEVELOPMENT, ids.HOLDOUT):
        raise ValueError("--official development|holdout is required for ContractNLI")
    return sorted(({"source_document_id": r[DOCUMENT_ID_FIELD],
                    "split_key": ids.key_string(r[DOCUMENT_ID_FIELD]), "side": side}
                   for r in data[DOCUMENTS_FIELD]), key=lambda r: r["split_key"])


def headline(pairs, rows=None, answers=None, unit_text=None) -> dict:
    """Accuracy over all items, ABSTAIN counted wrong, and F1 for Contradiction and for
    Entailment (the paper's measures); the 3 by 3 confusion matrix beside them."""
    return {"accuracy": metrics.accuracy(pairs),
            "contradiction": metrics.class_scores(pairs, "contradiction"),
            "entailment": metrics.class_scores(pairs, "entailment"),
            "confusion": metrics.confusion(pairs, CLASSES)}


if __name__ == "__main__":
    sys.exit(cli.main(sys.modules[__name__]))
