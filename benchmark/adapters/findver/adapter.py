"""FinDVer adapter (preregistration sections 1, 3, 5.2, 5.5, 5.6).

One item per claim; the document is the filing (`report`). Its paragraphs and tables
are written in context-index order, one part each, a table as SciTab's is. One rule per
claim (CONV-<opaque item id>). The split is official: testmini is development, test
the holdout pool minus any item whose report also appears in testmini. FLAG = refuted,
CLEAR = entailed; a refusal maps to ABSTAIN (the benchmark has no refusal class).

Developed on hand-written synthetic items only (D-019): no FinDVer data was opened.

Usage: as the ContraDoc adapter (build, label, score), and
    py -3.12 benchmark/adapters/findver/adapter.py split --input <file> --official development|holdout [--testmini <file>]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from common import bundle, cli, ids, mapping, metrics  # noqa: E402

BENCHMARK = "findver"
RULE_NAME = "Claim"
RULE_TEMPLATE = "Claim about the filing: {claim} The claim must agree with the passages of the filing."

# --- source schema --------------------------------------------------------------------
ITEM_ID_FIELD = "example_id"        # documented (SELECTION.md)
REPORT_FIELD = "report"             # documented: the document id
CLAIM_FIELD = "claim"               # PROVISIONAL
LABEL_FIELD = "label"               # PROVISIONAL
GOLD_VALUES = {"entailed": "entailed", "refuted": "refuted"}   # PROVISIONAL stored values
CONTEXT_FIELD = "context"           # PROVISIONAL: the filing's entries in index order; a
                                    # string is a paragraph, a list of rows (header first,
                                    # each a list of cells) is a table
CONTEXT_INDEX_BASE = 0              # PROVISIONAL: the first context index (0 or 1)
EVIDENCE_FIELD = "relevant_context" # PROVISIONAL: the item's context indices
SUBSET_FIELD = "subset"             # PROVISIONAL: FDV-IE, FDV-MATH, FDV-KNOW
# PROVISIONAL: the file holds a JSON list of claim records.
# The issuer (CIK or ticker) for the sensitivity bootstrap is not derived: how to read it
# from `report` is not documented outside the data (section 4, PROVISIONAL).
# ---------------------------------------------------------------------------------------
SPLIT_OPTIONS = (("--official", "development or holdout: the official split the input file is"),
                 ("--testmini", "the testmini file; reports it holds are removed from a holdout file"))

SPEC = mapping.Spec(
    BENCHMARK,
    labels={mapping.FLAG: "refuted", mapping.CLEAR: "entailed", mapping.UNDECIDED: None},
    b1_labels={"refuted": mapping.FLAG, "entailed": mapping.CLEAR, "undecided": mapping.UNDECIDED},
    s2=True)


def read_source(path) -> list:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ValueError("expected a list of claim records")
    return records


def entry_text(entry):
    """(part text, kind, words) for one context entry."""
    if isinstance(entry, str):
        return entry, "paragraph", ids.word_count(entry)
    if isinstance(entry, list) and entry and all(isinstance(row, list) for row in entry):
        return bundle.render_table(entry[0], entry[1:]), "table", bundle.table_words(entry[0], entry[1:])
    raise ValueError("a context entry is neither a paragraph nor a table")


def _reports(records):
    reports = {}
    for r in records:
        reports.setdefault(ids.key_string(r[REPORT_FIELD]), []).append(r)
    for key, claims in reports.items():
        first = json.dumps(claims[0][CONTEXT_FIELD], sort_keys=True)
        if any(json.dumps(c[CONTEXT_FIELD], sort_keys=True) != first for c in claims[1:]):
            raise ValueError("claims of report %s carry different filings" % key)
    return reports


def _gold(record) -> str:
    value = record.get(LABEL_FIELD)
    if value not in GOLD_VALUES:
        raise ValueError("unrecognised %s value %r for %s" % (LABEL_FIELD, value, record.get(ITEM_ID_FIELD)))
    return GOLD_VALUES[value]


def documents(records) -> list:
    claim_ids = [ids.key_string(r[ITEM_ID_FIELD]) for r in records]
    if len(set(claim_ids)) != len(claim_ids):
        raise ValueError("duplicate example id")
    out = []
    for report, claims in sorted(_reports(records).items()):
        context = claims[0][CONTEXT_FIELD]
        parts, words = [], 0
        for offset, entry in enumerate(context):
            text, kind, count = entry_text(entry)
            words += count
            parts.append({"text": text, "source": {"context_index": offset + CONTEXT_INDEX_BASE,
                                                   "kind": kind}})
        rules, items = [], []
        for claim in claims:
            item_id = ids.opaque_item_id(BENCHMARK, claim[ITEM_ID_FIELD])
            rid = bundle.RULE_ID_PREFIX + item_id
            evidence = []
            for index in claim.get(EVIDENCE_FIELD) or []:
                part = int(index) - CONTEXT_INDEX_BASE + 1
                if not 1 <= part <= len(parts):
                    raise ValueError("context index %r out of range for %s" % (index, claim[ITEM_ID_FIELD]))
                evidence.append(part)
            gold = _gold(claim)
            rules.append({"rule_id": rid, "name": RULE_NAME,
                          "text": RULE_TEMPLATE.format(claim=bundle.one_space(claim[CLAIM_FIELD]))})
            items.append({"item_id": item_id, "source_item_id": claim[ITEM_ID_FIELD], "rule_id": rid,
                          "gold": gold, "evidence_parts": evidence,
                          "location_measurable": bool(evidence) and gold == SPEC.labels[mapping.FLAG],
                          "extra": {"subset": claim.get(SUBSET_FIELD)}})
        out.append({"document_id": ids.opaque_document_id(BENCHMARK, claims[0][REPORT_FIELD]),
                    "source_document_id": claims[0][REPORT_FIELD], "split_key": claims[0][REPORT_FIELD],
                    "cluster": claims[0][REPORT_FIELD], "source_words": words, "parts": parts,
                    "rules": rules, "items": items, "hash_split": False, "side": "official",
                    "record_extra": {"context_index_base": CONTEXT_INDEX_BASE}})
    return out


def split_rows(records, args=None) -> list:
    """The official side of every report; with --testmini, a holdout report that also
    appears in testmini is removed with all its items."""
    side = getattr(args, "official", None)
    if side not in (ids.DEVELOPMENT, ids.HOLDOUT):
        raise ValueError("--official development|holdout is required for FinDVer")
    overlap = set()
    if getattr(args, "testmini", None):
        overlap = {ids.key_string(r[REPORT_FIELD]) for r in read_source(args.testmini)}
    rows = []
    for report, claims in sorted(_reports(records).items()):
        removed = side == ids.HOLDOUT and report in overlap
        rows.append({"source_document_id": report, "split_key": report,
                     "side": "removed_overlap" if removed else side, "items": len(claims)})
    return rows


def headline(pairs, rows, answers, unit_text=None) -> dict:
    """Accuracy over all items, ABSTAIN counted wrong (headline); coverage and accuracy on
    answered items; the same per subset (secondary, no tests)."""
    by_subset = {}
    for pair, row in zip(pairs, rows):
        by_subset.setdefault(str(answers[row["item_id"]].get("subset")), []).append(pair)
    return {"accuracy": metrics.accuracy(pairs), "coverage": metrics.coverage(pairs),
            "per_subset": {name: {"accuracy": metrics.accuracy(p), "coverage": metrics.coverage(p)}
                           for name, p in sorted(by_subset.items())}}


if __name__ == "__main__":
    sys.exit(cli.main(sys.modules[__name__]))
