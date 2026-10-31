"""Writes category_list.txt beside this file: a hand-written synthetic category list laid
out as the release's CUAD_v1_README.txt lays out its own (a `CATEGORY LIST` line, then per
category a row number, `Category:`, `Description:`, `Answer Format:` and `Group:` lines,
tab-indented, the list closed by a line of `=`). No text of the release is copied: every
description here is written by hand for the checks. Row 17 spells its name out in full,
as the release does, and row 2's description runs over two lines.

    py -3.12 benchmark/adapters/cuad_claim/fixtures/make_category_list.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from cuad.adapter import CATEGORIES  # noqa: E402

FULL_NAMES = {17: "Right of First Refusal or Offer (ROFR/ROFO/ROFN)"}
DESCRIPTIONS = {1: "The title the synthetic contract gives itself",
                2: "The persons or firms that sign the synthetic contract,\n\tnamed as the contract names them",
                8: "Which jurisdiction's law the synthetic contract chooses",
                16: "May a party end the synthetic contract without a breach by the other?",
                39: "Must a party keep a policy of insurance in force?"}


def text():
    lines = ["SYNTHETIC CATEGORY LIST FOR THE CHECKS", "", "=" * 49, "CATEGORY LIST", "",
             "\tCategory (incl. context and answer)", "\tDescription", "\tAnswer Format", "\tGroup"]
    for index, name in enumerate(CATEGORIES, start=1):
        description = DESCRIPTIONS.get(index, "Synthetic description of row %d, written by hand" % index)
        lines += ["\t%d" % index, "\tCategory:\t" + FULL_NAMES.get(index, name),
                  "\tDescription: \t" + description, "\tAnswer Format: \tYes/No", "\tGroup:\t\t-"]
    lines += ["", "=" * 49, "SOURCE OF CONTRACTS", "", "Synthetic.", ""]
    return "\n".join(lines)


def main():
    with open(HERE / "category_list.txt", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text())


if __name__ == "__main__":
    main()
