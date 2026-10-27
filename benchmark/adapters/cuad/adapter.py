"""CUAD v1 adapter (preregistration sections 1, 3, 5.2, 5.5, 5.6). PROVISIONAL as a whole
until its schema is confirmed (section 9 of the preregistration).

One item per contract and category (41 per contract), one rule per category
(CONV-CUAD-NN for row cuad-NN). The document is the contract's `context` string, one
part per blank-line paragraph. A contract is identified by the SHA-256 of its text,
which is also its split key; contracts with identical text are merged first, keeping
the copy whose title sorts first. FLAG is absence: gold absent when the category's QA
entry has an empty answers list.

Developed on hand-written synthetic items only (D-019): no CUAD data was opened.

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

BENCHMARK = "cuad"
RULE_NAME = "Category"
RULE_TEMPLATE = "The document must contain, in at least one passage, a clause of this category: {name}. {description}"

# --- source schema: every name PROVISIONAL (SQuAD-style CUAD_v1.json, not confirmed) ---
DATA_FIELD = "data"               # PROVISIONAL
TITLE_FIELD = "title"             # PROVISIONAL: the copy's source id when texts are merged
PARAGRAPHS_FIELD = "paragraphs"   # PROVISIONAL: exactly one entry per contract
CONTEXT_FIELD = "context"         # named by the preregistration, PROVISIONAL
QAS_FIELD = "qas"                 # PROVISIONAL
QA_ID_FIELD = "id"                # PROVISIONAL: ends in `__<Category>`
ANSWERS_FIELD = "answers"         # named by the preregistration, PROVISIONAL
QA_ID_SEPARATOR = "__"
# ---------------------------------------------------------------------------------------

# Category names from the CUAD paper's list (preregistration section 5.5), in its order.
CATEGORIES = (
    "Document Name", "Parties", "Agreement Date", "Effective Date", "Expiration Date",
    "Renewal Term", "Notice to Terminate Renewal", "Governing Law", "Most Favored Nation",
    "Non-Compete", "Exclusivity", "No-Solicit of Customers", "Competitive Restriction Exception",
    "No-Solicit of Employees", "Non-Disparagement", "Termination for Convenience",
    "ROFR/ROFO/ROFN", "Change of Control", "Anti-Assignment", "Revenue/Profit Sharing",
    "Price Restriction", "Minimum Commitment", "Volume Restriction", "IP Ownership Assignment",
    "Joint IP Ownership", "License Grant", "Non-Transferable License",
    "Affiliate IP License-Licensor", "Affiliate IP License-Licensee",
    "Unlimited/All-You-Can-Eat License", "Irrevocable or Perpetual License",
    "Source Code Escrow", "Post-Termination Services", "Audit Rights", "Uncapped Liability",
    "Cap on Liability", "Liquidated Damages", "Warranty Duration", "Insurance",
    "Covenant Not to Sue", "Third Party Beneficiary",
)
# PROVISIONAL: the spelling of a category in the data's QA ids where it differs from the
# name above, by row ("cuad-NN": "spelling"). Recorded at freeze; empty until confirmed.
DATA_SPELLING = {}
# PROVISIONAL: the descriptions of the category list distributed with CUAD v1, copied
# verbatim at freeze, by row. Empty until then: the template uses the name alone.
DESCRIPTIONS = {}

SPEC = mapping.Spec(
    BENCHMARK,
    labels={mapping.FLAG: "absent", mapping.CLEAR: "present", mapping.UNDECIDED: None},
    b1_labels={"absent": mapping.FLAG, "present": mapping.CLEAR, "undecided": mapping.UNDECIDED},
    absence_flag=True, s2=True)


def row_name(index: int) -> str:
    return "cuad-%02d" % index


def rule_id(index: int) -> str:
    return "CONV-CUAD-%02d" % index


def rule_text(index: int) -> str:
    description = bundle.one_space(DESCRIPTIONS.get(row_name(index), ""))
    return RULE_TEMPLATE.format(name=CATEGORIES[index - 1], description=description).rstrip()


def read_source(path) -> list:
    """[(title, context, qas)] per contract entry, in file order."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for entry in data[DATA_FIELD]:
        paragraphs = entry[PARAGRAPHS_FIELD]
        if len(paragraphs) != 1:
            raise ValueError("a contract entry with %d paragraphs (one expected): %s"
                             % (len(paragraphs), entry.get(TITLE_FIELD)))
        out.append({"title": entry[TITLE_FIELD], "context": paragraphs[0][CONTEXT_FIELD],
                    "qas": paragraphs[0][QAS_FIELD]})
    return out


def merged(records):
    """(kept contracts, merged count): identical texts merged, the copy whose title
    sorts first kept."""
    by_text = {}
    for r in records:
        by_text.setdefault(ids.text_identity(r["context"]), []).append(r)
    kept = [min(group, key=lambda r: ids.key_string(r["title"])) for group in by_text.values()]
    return kept, len(records) - len(kept)


def _qa(contract, index):
    spelling = DATA_SPELLING.get(row_name(index), CATEGORIES[index - 1])
    hits = [q for q in contract["qas"] if str(q[QA_ID_FIELD]).endswith(QA_ID_SEPARATOR + spelling)]
    if len(hits) != 1:
        raise ValueError("%d QA entries for category %r in %s (one expected)"
                         % (len(hits), spelling, contract["title"]))
    return hits[0]


def documents(records, options=None) -> list:
    kept, merged_count = merged(records)
    out = []
    for contract in kept:
        text = contract["context"]
        sid = ids.text_identity(text)
        doc_id = ids.opaque_document_id(BENCHMARK, sid)
        rules, items = [], []
        for index in range(1, len(CATEGORIES) + 1):
            qa = _qa(contract, index)
            rules.append({"rule_id": rule_id(index), "name": RULE_NAME, "text": rule_text(index)})
            items.append({
                "item_id": ids.opaque_item_id(BENCHMARK, qa[QA_ID_FIELD]),
                "source_item_id": qa[QA_ID_FIELD], "rule_id": rule_id(index),
                "gold": "present" if qa[ANSWERS_FIELD] else "absent",
                "location_measurable": False,
                "extra": {"category_row": row_name(index)}})
        out.append({
            "document_id": doc_id, "source_document_id": sid, "split_key": sid, "cluster": sid,
            "side": ids.split_side(sid),
            "parts": [{"text": text[s:e], "words": ids.word_count(text[s:e]),
                       "source": {"start": s, "end": e}}
                      for s, e in bundle.blank_line_paragraphs(text)],
            "rules": rules, "items": items,
            "record_extra": {"merged_duplicates_in_input": merged_count}})
    return out


def split_rows(records, _args=None) -> list:
    kept, merged_count = merged(records)
    rows = [{"source_document_id": ids.text_identity(c["context"]),
             "split_key": ids.text_identity(c["context"]),
             "side": ids.split_side(ids.text_identity(c["context"])),
             "merged_duplicates_in_input": merged_count} for c in kept]
    return sorted(rows, key=lambda r: r["source_document_id"])


def headline(pairs, rows, answers, unit_text=None) -> dict:
    """Macro-F1 over present and absent, all items pooled (headline, not the official
    AUPR); precision and recall for present at the single operating point; secondary:
    the mean over categories of per-category macro-F1, and per-category F1."""
    classes = ("present", "absent")
    pooled = metrics.macro_f1(pairs, classes)
    by_category = {}
    for (pred, gold), row in zip(pairs, rows):
        by_category.setdefault(answers[row["item_id"]]["category_row"], []).append((pred, gold))
    per_category = {cat: metrics.macro_f1(p, classes) for cat, p in sorted(by_category.items())}
    zero = [0]
    mean = metrics._ratio(sum(v["macro_f1"] for v in per_category.values()), len(per_category), zero)
    return {"measure": "macro-F1 over present and absent, pooled (not the official AUPR)",
            "macro_f1": pooled["macro_f1"], "per_class": pooled["per_class"],
            "zero_denominators": pooled["zero_denominators"],
            "present": metrics.class_scores(pairs, "present"),
            "secondary_mean_category_macro_f1": mean,
            "secondary_zero_denominators": zero[0] + sum(v["zero_denominators"] for v in per_category.values()),
            "per_category": {cat: {"macro_f1": v["macro_f1"],
                                   "f1": {s["class"]: s["f1"] for s in v["per_class"]}}
                             for cat, v in per_category.items()}}


if __name__ == "__main__":
    sys.exit(cli.main(sys.modules[__name__]))
