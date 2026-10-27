"""SciTab adapter (preregistration sections 1, 3, 5.2, 5.5, 5.6).

One item per claim; the document is the table with its caption (`table_id`), one part:
the caption line, a blank line, then the table as a pipe-delimited Markdown table. One
rule per claim (CONV-<opaque item id>). The split key is `paper_id`, so every table of
a paper falls on the same side. FLAG = refutes, UNDECIDED = not enough info, CLEAR =
supports; a run failure is ABSTAIN, never not enough info.

Written on hand-written synthetic items (D-019), then confirmed on the B-dev development
items (S4c item 4). Where the claims of one table store different cells (one development
table does), the document is the table as its first claim in file order stores it, and
parts.json lists the claims whose table differs under `table_variants`.

Usage: as the ContraDoc adapter (build, split, label, score).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from common import bundle, cli, ids, mapping, metrics  # noqa: E402

BENCHMARK = "scitab"
RULE_NAME = "Claim"
RULE_TEMPLATE = ("Claim about the table in this passage: {claim} The claim must agree with the "
                 "table and its caption. If the table and caption do not settle the claim, emit "
                 "UNCERTAIN.")

# --- source schema --------------------------------------------------------------------
# Confirmed on the B-dev development items (95 claims, 29 tables), unless marked otherwise.
# The file is a JSON list of claim records, every value below a string except the table.
ID_FIELD = "id"                         # documented; a string, unique per claim
TABLE_ID_FIELD = "table_id"             # documented; a string
PAPER_ID_FIELD = "paper_id"             # documented; a string, one per table
LABEL_FIELD = "label"                   # documented
GOLD_VALUES = {"supports": "supports", "refutes": "refutes",          # confirmed spellings
               "not enough info": "not enough info"}   # PROVISIONAL: no development claim
                                        # carries this class, so its spelling is unconfirmed
CLAIM_FIELD = "claim"                   # confirmed
CAPTION_FIELD = "table_caption"         # confirmed: one line in every record
HEADER_FIELD = "table_column_names"     # confirmed: the header row, a list of strings
ROWS_FIELD = "table_content_values"     # confirmed: the body rows, lists of strings as wide
                                        # as the header
# The tables the SciTab paper prints as in-context examples are excluded from the holdout
# pool (section 1, D-039 item 15): role B identifies them by caption and passes their
# `table_id`s with --exclude (common/cli.py); no table id is written here.
# ---------------------------------------------------------------------------------------

SPEC = mapping.Spec(
    BENCHMARK,
    labels={mapping.FLAG: "refutes", mapping.CLEAR: "supports",
            mapping.UNDECIDED: "not enough info"},
    b1_labels={"refutes": mapping.FLAG, "supports": mapping.CLEAR,
               "not enough info": mapping.UNDECIDED},
    s2=False)
CLASSES = ("supports", "refutes", "not enough info")


def read_source(path) -> list:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ValueError("expected a list of claim records")
    return records


def caption_line(caption) -> str:
    """The caption as one line: each line break written as a space, nothing else changed."""
    text = "" if caption is None else str(caption)
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def part_text(record) -> str:
    return caption_line(record[CAPTION_FIELD]) + "\n\n" + bundle.render_table(
        record[HEADER_FIELD], record[ROWS_FIELD])


TABLE_FIELDS = (CAPTION_FIELD, HEADER_FIELD, ROWS_FIELD)


def _tables(records):
    """{table id: its claims in file order}. Claims of one table that name different papers
    are refused (the paper is the split key). Claims that carry a different caption, header
    or cells are kept: the document is the table as the table's first claim in file order
    stores it (B-dev counted words the same way), and `table_variants` lists the others."""
    tables = {}
    for r in records:
        tables.setdefault(ids.key_string(r[TABLE_ID_FIELD]), []).append(r)
    for key, claims in tables.items():
        if any(other[PAPER_ID_FIELD] != claims[0][PAPER_ID_FIELD] for other in claims[1:]):
            raise ValueError("claims of table %s disagree on %s" % (key, PAPER_ID_FIELD))
    return tables


def table_variants(claims) -> list:
    """[{claim id, fields}] for every claim whose stored table differs from the first
    claim's, with the fields that differ."""
    first = claims[0]
    out = []
    for other in claims[1:]:
        fields = [f for f in TABLE_FIELDS if other[f] != first[f]]
        if fields:
            out.append({"source_item_id": other[ID_FIELD], "fields": fields})
    return out


def _gold(record) -> str:
    value = record.get(LABEL_FIELD)
    if value not in GOLD_VALUES:
        raise ValueError("unrecognised %s value %r for claim %s" % (LABEL_FIELD, value, record.get(ID_FIELD)))
    return GOLD_VALUES[value]


def documents(records, options=None) -> list:
    claim_ids = [ids.key_string(r[ID_FIELD]) for r in records]
    if len(set(claim_ids)) != len(claim_ids):
        raise ValueError("duplicate claim id")
    out = []
    for table_key, claims in sorted(_tables(records).items()):
        first = claims[0]
        rules, items = [], []
        for claim in claims:
            item_id = ids.opaque_item_id(BENCHMARK, claim[ID_FIELD])
            rid = bundle.RULE_ID_PREFIX + item_id
            rules.append({"rule_id": rid, "name": RULE_NAME,
                          "text": RULE_TEMPLATE.format(claim=bundle.one_space(claim[CLAIM_FIELD]))})
            items.append({"item_id": item_id, "source_item_id": claim[ID_FIELD], "rule_id": rid,
                          "gold": _gold(claim), "location_measurable": False})
        out.append({
            "document_id": ids.opaque_document_id(BENCHMARK, first[TABLE_ID_FIELD]),
            "source_document_id": first[TABLE_ID_FIELD],
            "split_key": first[PAPER_ID_FIELD], "cluster": first[PAPER_ID_FIELD],
            "side": ids.split_side(first[PAPER_ID_FIELD]),
            "parts": [{"text": part_text(first), "source": {"part": "caption and table"},
                       "words": ids.word_count(caption_line(first[CAPTION_FIELD]))
                       + bundle.table_words(first[HEADER_FIELD], first[ROWS_FIELD])}],
            "rules": rules, "items": items,
            "record_extra": {"table_from_claim": first[ID_FIELD],
                             "table_variants": table_variants(claims)}})
    return out


def split_rows(records, _args=None) -> list:
    rows = [{"source_document_id": claims[0][TABLE_ID_FIELD],
             "split_key": ids.key_string(claims[0][PAPER_ID_FIELD]),
             "side": ids.split_side(claims[0][PAPER_ID_FIELD])}
            for claims in _tables(records).values()]
    return sorted(rows, key=lambda r: ids.key_string(r["source_document_id"]))


def headline(pairs, rows=None, answers=None, unit_text=None) -> dict:
    """Macro-F1 over supports, refutes, not enough info, and the 3 by 3 confusion matrix
    (with ABSTAIN as a predicted column)."""
    result = metrics.macro_f1(pairs, CLASSES)
    return {"headline_measure": "macro-F1 over supports, refutes, not enough info",
            "headline_value": result["macro_f1"],
            "measure": "macro-F1 over supports, refutes, not enough info",
            "macro_f1": result["macro_f1"], "per_class": result["per_class"],
            "zero_denominators": result["zero_denominators"],
            "confusion": metrics.confusion(pairs, CLASSES)}


if __name__ == "__main__":
    sys.exit(cli.main(sys.modules[__name__]))
