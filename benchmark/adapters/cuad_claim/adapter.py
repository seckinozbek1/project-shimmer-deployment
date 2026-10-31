"""CUAD v1 as a claim check (Annex D, D-S13 item 8; overrules D-105). DRAFT for
preregistration version 3: no S8 run reads it until that version is frozen.

CUAD asks where a clause of a category is; Shimmer checks claims. Under the CUAD adapter
beside this one (`cuad/adapter.py`, preregistration section 5.5) the rule says the
document "must contain" a clause of the category, so its absent class is reached only by
a model's absence claim, and Python refuses every absence claim that quotes nothing
(`paired_review.judged_item_refusal`): on development contract `527255a5c970` (L10) all
410 judging answers were refused that way (D-105). This adapter turns each CUAD label
into a claim whose refutation is a quote:

  Claim about the document: no passage of the document holds a clause of this category:
  {name}. What the category covers: {description} A passage that holds such a clause
  shows the claim is false, and a finding quotes the clause from it.

`{name}` is the paper's category name (section 5.5's table); `{description}` is the
release's description of that row, each run of whitespace one space, with a full stop
added when it does not end with `.`, `?` or `!`.

- A present category makes the claim false. A reviewer refutes it on the unit that holds
  the clause, and its finding quotes the clause; Python keeps the finding only when the
  quote is text of that unit (`quote_not_in_unit`). So the clause text is the quote, and
  the quote requirement sits on the system's side, never in the bundle.
- An absent category makes the claim true: no unit holds such a clause, and no record, an
  ok record, or silence says so. Nothing has to be quoted to reach it.
- The claim is universal ("no passage"), so section 5.1's order (an irregular record on
  any unit wins) gives exactly "present when any unit holds the clause". A positive
  existential claim ("some passage holds") would be refuted by every unit that does not
  hold the clause, and line 2 would then make nearly every item absent.

FLAG = present (any irregular record for the rule that is not a refusal, whatever its
relation, once section 5.1 has set aside Python's figure-audit records), CLEAR = absent
(an ok record or silence), UNDECIDED = ABSTAIN; S-2 applies. Gold: present when the
category's QA entry has a non-empty `answers` list (`cuad/adapter.py`'s reading,
confirmed on the B-dev development items). The answer spans mark the evidence units by
their character offsets (confirmed on the development items: every offset locates its
text), so location is measured on present items.

No gold in the bundle. The rule set is the same 41 rules for every contract, written
from the category list alone (name and description), so it carries nothing about any
contract; the document is the contract text as the CUAD adapter writes it; the gold sits
only in `answer_key.json`, which only the scorer reads and `tools/stage_workload.py`
never stages. A build is gold-invariant: emptying every `answers` list changes no file
but `answer_key.json` (held by `scripts/adapter_checks.py`, group `cuadclaim`).

The category list is read at build time from the release's own `CUAD_v1_README.txt`
(`--categories`), never copied into this repository (third-party text, Annex B.10); a
build that declares its side outside `--development` accepts only the file whose SHA-256
the B-dev manifest records.

Measured limitation (development, gold-free, Shimmer's own pairing map): a rule pairs
only with the units that carry every document label its text names (input format section
4). Every claim names `Passage`, so it pairs with every unit, except where its category
name or description also names a label the contract writes: 109 of the 3,936 development
(contract, claim) pairs, most of them row 32 ("Source Code Escrow" names the `Source:`
lines of 42 contracts) and rows 1, 3, 4 and 5 (`Name:` and `Date:` lines). There B3 asks
only the units carrying that label, so a clause elsewhere is silence, read as absent. The
CUAD adapter's rules name the same labels. B1 reads the whole document and is not affected.
Ids: benchmark name `cuad_claim`, so its opaque document and item ids never coincide
with the CUAD adapter's (`527255a5c970` there is another id here). Sides, the duplicate
merge, the parts and the split key are the CUAD adapter's.

Usage: as every adapter (build, split, bands, label, score), with `--categories` on
build and bands.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from common import bundle, cli, ids, mapping  # noqa: E402
from cuad import adapter as cuad  # noqa: E402  the one reading of the CUAD release

BENCHMARK = "cuad_claim"
RULE_NAME = "Claim"
RULE_TEMPLATE = ("Claim about the document: no passage of the document holds a clause of this "
                 "category: {name}. What the category covers: {description} A passage that holds "
                 "such a clause shows the claim is false, and a finding quotes the clause from it.")
# The SHA-256 of CUAD_v1_README.txt as the B-dev manifest records it
# (external/cuad/MANIFEST.json, files_passed_on_sha256): the one category list a
# non-development build accepts.
CATEGORY_LIST_SHA256 = "d0d1af57cff6d185ed9841566b2f069efffb7ee6ee7b1b49192e94d0a9fe3842"
CATEGORY_LIST_HEADING = "CATEGORY LIST"
BUILD_OPTIONS = (("--categories", "the release's CUAD_v1_README.txt: its category list gives "
                                  "every claim's description (required)"),)

SPEC = mapping.Spec(
    BENCHMARK,
    labels={mapping.FLAG: "present", mapping.CLEAR: "absent", mapping.UNDECIDED: None},
    # B1 asks the preregistered question of B's synthetic tests (section 5.4, revision
    # 4): whether any passage breaks the rule. Violated is present, holds is absent.
    b1_labels={"violated": mapping.FLAG, "holds": mapping.CLEAR, "undecided": mapping.UNDECIDED},
    absence_flag=False, s2=True, unit_evidence=True)


def rule_id(index: int) -> str:
    return "CONV-CUADC-%02d" % index


def read_category_list(path) -> dict:
    """{row: {"name", "description"}} from the release's category list: the lines after
    `CATEGORY LIST` up to the next line of `=`; each `Category:` line opens an entry, and
    the `Description:` line with any lines that follow it up to the next keyed line is its
    description. Row k is the k-th entry; its name must hold the paper's name for row k
    (row 17 spells it out in full), else the list is refused."""
    lines = Path(path).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    try:
        start = next(k for k, line in enumerate(lines) if line.strip() == CATEGORY_LIST_HEADING)
    except StopIteration:
        raise ValueError("no %s in %s" % (CATEGORY_LIST_HEADING, path)) from None
    entries, field = [], None
    for line in lines[start + 1:]:
        text = line.strip()
        if text and set(text) == {"="}:
            break
        key, _, rest = text.partition(":")
        if key in ("Category", "Description", "Answer Format", "Group"):
            field = key
            if key == "Category":
                entries.append({"name": rest.strip(), "description": []})
            elif key == "Description" and entries:
                entries[-1]["description"].append(rest.strip())
            continue
        if field == "Description" and text and not text.isdigit() and entries:
            entries[-1]["description"].append(text)
    if len(entries) != len(cuad.CATEGORIES):
        raise ValueError("the category list has %d entries (%d expected)" % (len(entries), len(cuad.CATEGORIES)))
    out = {}
    for index, entry in enumerate(entries, start=1):
        name = cuad.CATEGORIES[index - 1]
        if name.casefold() not in entry["name"].casefold():
            raise ValueError("category list row %d is %r, not %r" % (index, entry["name"], name))
        description = bundle.one_space(" ".join(entry["description"])).strip()
        if not description:
            raise ValueError("category list row %d has no description" % index)
        out[index] = {"name": name, "description": description}
    return out


def as_sentence(text: str) -> str:
    """A description as one sentence: a full stop is added when it does not already end
    with `.`, `?` or `!` (the release's descriptions end either way)."""
    return text if text.endswith((".", "?", "!")) else text + "."


def rule_text(index: int, categories: dict) -> str:
    return RULE_TEMPLATE.format(name=cuad.CATEGORIES[index - 1],
                                description=as_sentence(categories[index]["description"]))


def rules(categories: dict) -> list:
    """The 41 rules, the same for every contract."""
    return [{"rule_id": rule_id(index), "name": RULE_NAME, "text": rule_text(index, categories)}
            for index in range(1, len(cuad.CATEGORIES) + 1)]


def _categories(options) -> tuple:
    """(rows, provenance) from --categories. A build that declares its side outside
    --development takes only the release's file; `bands`, which declares no side and
    writes no rule, reads any list of the release's form."""
    options = options or {}
    path = options.get("categories")
    if not path:
        raise ValueError("--categories <CUAD_v1_README.txt> is required: every claim's "
                         "description is read from the release's category list")
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    release = digest == CATEGORY_LIST_SHA256
    if not release and not options.get("development") and options.get("side") is not None:
        raise ValueError("the category list is not the release's CUAD_v1_README.txt "
                         "(SHA-256 %s, expected %s)" % (digest, CATEGORY_LIST_SHA256))
    return read_category_list(path), {"category_list_sha256": digest, "category_list_release": release}


def evidence_parts(context: str, spans, answers) -> list:
    """The 1-based parts an answer's character range overlaps. An offset that does not
    locate its text is refused (every development offset locates it)."""
    found = set()
    for answer in answers:
        start = int(answer["answer_start"])
        end = start + len(answer["text"])
        if context[start:end] != answer["text"]:
            raise ValueError("an answer offset does not locate its text")
        found.update(k for k, (s, e) in enumerate(spans, start=1) if s < end and start < e)
    return sorted(found)


def documents(records, options=None) -> list:
    categories, provenance = _categories(options)
    rule_set = rules(categories)
    kept, merged_count = cuad.merged(records)
    out = []
    for contract in kept:
        text = contract["context"]
        sid = ids.text_identity(text)
        spans = bundle.blank_line_paragraphs(text)
        items = []
        for index in range(1, len(cuad.CATEGORIES) + 1):
            qa = cuad._qa(contract, index)
            answers = qa[cuad.ANSWERS_FIELD]
            marked = evidence_parts(text, spans, answers)
            items.append({
                "item_id": ids.opaque_item_id(BENCHMARK, qa[cuad.QA_ID_FIELD]),
                "source_item_id": qa[cuad.QA_ID_FIELD], "rule_id": rule_id(index),
                "gold": "present" if answers else "absent",
                "location_measurable": bool(marked), "evidence_parts": marked,
                "extra": {"category_row": cuad.row_name(index)}})
        out.append({
            "document_id": ids.opaque_document_id(BENCHMARK, sid), "source_document_id": sid,
            "split_key": sid, "cluster": sid, "side": ids.split_side(sid),
            "parts": [{"text": text[s:e], "words": ids.word_count(text[s:e]),
                       "source": {"start": s, "end": e}} for s, e in spans],
            "rules": [dict(r) for r in rule_set], "items": items,
            "record_extra": dict({"merged_duplicates_in_input": merged_count}, **provenance)})
    return out


read_source = cuad.read_source
split_rows = cuad.split_rows


def headline(pairs, rows, answers, unit_text=None) -> dict:
    """The CUAD adapter's measures on the claim form: macro-F1 over present and absent,
    all items pooled (headline), precision and recall for present, and per category."""
    out = cuad.headline(pairs, rows, answers, unit_text)
    measure = "macro-F1 over present and absent, pooled, claim form (not CUAD's official AUPR)"
    out["headline_measure"] = out["measure"] = measure
    return out


if __name__ == "__main__":
    sys.exit(cli.main(sys.modules[__name__]))
