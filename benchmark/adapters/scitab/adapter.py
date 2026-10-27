"""SciTab adapter (preregistration sections 1, 3, 5.2, 5.5, 5.6).

One item per claim; the document is the table with its caption (`table_id`), one part:
the caption line, a blank line, then the table as a pipe-delimited Markdown table. One
rule per claim (CONV-<opaque item id>). The split key is `paper_id`, so every table of
a paper falls on the same side. FLAG = refutes, UNDECIDED = not enough info, CLEAR =
supports; a run failure is ABSTAIN, never not enough info.

Developed on hand-written synthetic items only (D-019): no SciTab data was opened.

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
ID_FIELD = "id"                         # documented (SELECTION.md): the claim
TABLE_ID_FIELD = "table_id"             # documented
PAPER_ID_FIELD = "paper_id"             # documented
LABEL_FIELD = "label"                   # documented
GOLD_VALUES = {"supports": "supports", "refutes": "refutes",          # PROVISIONAL spellings
               "not enough info": "not enough info"}
CLAIM_FIELD = "claim"                   # PROVISIONAL
CAPTION_FIELD = "table_caption"         # PROVISIONAL
HEADER_FIELD = "table_column_names"     # PROVISIONAL: the header row, a list of cells
ROWS_FIELD = "table_content_values"     # PROVISIONAL: the body rows, a list of lists of cells
# PROVISIONAL: the file holds a JSON list of claim records.
# The 25 demonstration claims (5 tables) are excluded from both sets; their table ids are
# pending B-dev (section 1). Empty: no item is excluded.
DEMONSTRATION_TABLE_IDS = ()
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
    return [r for r in records if r[TABLE_ID_FIELD] not in DEMONSTRATION_TABLE_IDS]


def caption_line(caption) -> str:
    """The caption as one line: each line break written as a space, nothing else changed."""
    text = "" if caption is None else str(caption)
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def part_text(record) -> str:
    return caption_line(record[CAPTION_FIELD]) + "\n\n" + bundle.render_table(
        record[HEADER_FIELD], record[ROWS_FIELD])


def _tables(records):
    tables = {}
    for r in records:
        tables.setdefault(ids.key_string(r[TABLE_ID_FIELD]), []).append(r)
    for key, claims in tables.items():
        first = claims[0]
        for other in claims[1:]:
            for field in (PAPER_ID_FIELD, CAPTION_FIELD, HEADER_FIELD, ROWS_FIELD):
                if other[field] != first[field]:
                    raise ValueError("claims of table %s disagree on %s" % (key, field))
    return tables


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
            "rules": rules, "items": items})
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
    return {"measure": "macro-F1 over supports, refutes, not enough info",
            "macro_f1": result["macro_f1"], "per_class": result["per_class"],
            "zero_denominators": result["zero_denominators"],
            "confusion": metrics.confusion(pairs, CLASSES)}


if __name__ == "__main__":
    sys.exit(cli.main(sys.modules[__name__]))
