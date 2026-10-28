"""Writes synthetic_items.json beside this file: three hand-written synthetic contracts in
the CUAD v1 schema (confirmed on the B-dev development items), each with one QA entry per
category (41), the QA id ending in the category as the release spells it. The contract
texts and the categories each one answers are written here by hand; only the 41 QA
entries per contract are expanded by the loop below. The third contract repeats the
first's text under a title that sorts first, so the duplicate merge keeps it.

    py -3.12 benchmark/adapters/cuad/fixtures/make_synthetic_items.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from cuad.adapter import CATEGORIES, data_spelling  # noqa: E402

ALPHA = ("SUPPLY AGREEMENT\n\nThis agreement is made between Alpha Works and Beta Stores.\n\n"
         "This agreement is governed by the laws of the State of Nowhere.\n\n"
         "## Section heading written with hashes\n\n"
         "Either party may end this agreement on thirty days notice.")
BETA = ("SERVICE AGREEMENT\n\nThe provider shall perform the services with care.\n\n"
        "The provider shall keep insurance in force.")
ALPHA_PRESENT = {"Document Name": "SUPPLY AGREEMENT", "Parties": "Alpha Works and Beta Stores",
                 "Governing Law": "governed by the laws of the State of Nowhere",
                 "Termination for Convenience": "Either party may end this agreement on thirty days notice."}
BETA_PRESENT = {"Document Name": "SERVICE AGREEMENT", "Insurance": "keep insurance in force"}


def entry(title, context, present):
    qas = []
    for index, name in enumerate(CATEGORIES, start=1):
        answers = ([{"text": present[name], "answer_start": context.index(present[name])}]
                   if name in present else [])
        # The QA id carries the category as the release spells it (confirmed on the B-dev
        # development items), which differs from the paper's name for 15 rows.
        spelling = data_spelling(index)
        qas.append({"id": title + "__" + spelling,
                    "question": "Highlight the parts (if any) of this contract related to \"%s\"." % spelling,
                    "answers": answers, "is_impossible": not answers})
    return {"title": title, "paragraphs": [{"context": context, "qas": qas}]}


def main():
    data = {"version": "synthetic", "data": [
        entry("SYN-ALPHA-SUPPLY", ALPHA, ALPHA_PRESENT),
        entry("SYN-BETA-SERVICE", BETA, BETA_PRESENT),
        entry("SYN-AARDVARK-COPY", ALPHA, ALPHA_PRESENT)]}
    with open(HERE / "synthetic_items.json", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
