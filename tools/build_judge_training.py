"""The judge's training rows (T, D-S42 item 2): public training sets in C's decision format.

    py -3.12 -X utf8 tools/build_judge_training.py --train-root external/train \
        --contradoc-dev D --scitab-dev S --out external/train/built [--judge-source DIR]

Each row is one user turn, exactly as C sends it, and one fixed answer as its target: the question
is rendered by doc_judge.render_choice from the forms of choice_judge_prompt.json, and a table's
evidence is chosen by doc_judge.select_cells (scripts/cell_selection.py and its config), read from
`--judge-source` (this repository once the lane holding them is merged). Neither is copied here.
Both are pinned: FORMS_SHA256 and SELECTOR_SHA256 are the digests the rows were built against, and a
build refuses when C's forms or selector differ, so a changed template cannot leave stale rows
looking current. The selector's digest covers what a selection runs and nothing else: the syntax
trees of select_cells and of every module-level definition it reaches in cell_selection.py and the
modules that file names (pairing_map's tokeniser among them), and config/cell_selection.json. An
edit elsewhere in those files moves nothing; an edit to anything a selection runs refuses. A claim the selector refuses (a tie or no table) is no row, and is counted.

Two mixes come out of one read, to the same rows budget. `dev_mix` is measured only: it carries the
rows under share-alike terms (VitaminC, MultiNLI's fiction), and the operator ruled that an
adapter trained on it is never published. `permissive_mix` leaves those out and is the product
candidate; it has no pair Unclear, since only VitaminC gives one. Every row states `share_alike`.

Deterministic: every selection is an order of SHA-256 digests of (seed, set, id), and two builds
of the same inputs are byte-identical. The held-out split is cut by GROUP within a FAMILY before
anything is selected: a set derived from another shares its split, so no case, page, table or
premise sits on both sides. A row above MAX_TOKENS is dropped and counted, because the memory
arithmetic of TRAIN_JUDGE_DATA.md holds only up to there.

Padding is a declared augmentation: a share of pair rows, chosen with no reference to the label, is
set inside sentences of its own set, to a word count drawn from one distribution for every class.
Length and padding must carry no signal, and drawing alike does not ensure that when sources differ
in length, so `stratify` then keeps, in every cell of (padded, length band), the same share of each
answer. The manifest reports those shares per cell. WiCE is not used for this reason: it has no
contradiction class, so its long web pages would teach that a long page is never a Yes.

Attempt 2 (D-S52, D-S56; `--attempt 2`). T's held-out accuracy saturated by its midpoint while the
benchmarks barely moved (D-294), so the change is the FORM of the pair rows, not more updates: C's
pair step shows a model two sentences of ONE document that its proposer ranks as alike, and nearly
all such pairs are compatible. Attempt 2's pair rows are made the same way, from C4 web documents
(`c4_en_train_00000.json.gz`) through C's own `passage_pairs.passages` and `propose`, on its
rare-word ranking (the path it takes without the embedding model): the top pair of a document is a
No (`c4_alike`); a proposed pair whose sentences both write one figure has that figure changed in
the second by Python, a Yes (`c4_figure_changed`), and stands beside its unchanged twin, a No
(`c4_figure_twin`), so only the figure tells them apart. Which figure means the same fact is not
read: two sentences may write one number about different things, so some changed pairs do not
contradict, and nobody checked. NLI sentence contradictions stay as a minority, there is no
padding, the claim rows are attempt 1's, and the mix is the permissive one only. The domain mix is
the documents' host names as counted, in the manifest; none is named here.

Overlap: any text sharing a SHINGLE-word run with the development texts of ContraDoc or SciTab, or
a page named like a ContraDoc article, is removed before selection, and the counts are written.
The two development files are read for their text fields only, never a label. They are never rows.
"""
import argparse
import ast
import csv
import hashlib
import inspect
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "judge-training-rows-v2"
SEED = 7
MAX_TOKENS = 2048
CHAT_OVERHEAD_TOKENS = 8      # the chat template's own turn markers, around the user text
SHINGLE = 8
HELD_OUT_SHARE = 0.05
PAD_SHARE = 0.3               # pair rows padded, chosen with no reference to the label
PAD_WORDS = (30, 600)         # words added around each passage, log-uniform, one range for every class
OVERSAMPLE = 4                # candidates drawn per plan row, so stratify has rows to keep
BANDS = (128, 192, 256, 384, 768, 1024, 1536, MAX_TOKENS)
FORMS_SHA256 = "f4271698110e5ecdb85e8192d7cad18dc3ba67d2199a0474420a8b7be784fd8f"
SELECTOR_SHA256 = "304698aac36520dad886a286ce17923035ce0b5bc32a2fb524fa4f5f2458ac70"
# Each attempt's pins. Attempt 2 and 2b take judge-agent's claim form (D-S55, D-S56): a `{tools}`
# slot that `judge_agent.claim_tools` fills, so `claim_tools` is pinned beside the selector.
FORMS_PINS = {1: FORMS_SHA256, 2: "eee5a79401f069da14ff6ad85582646ca1a09b8a81c727706149ab7ba9d9be99", 3: "eee5a79401f069da14ff6ad85582646ca1a09b8a81c727706149ab7ba9d9be99"}
SELECTOR_PINS = {1: SELECTOR_SHA256, 2: "7e2f4e455c7e8697ae2362069b6d50249eea7285940cbc45e80df3395f5b38f4", 3: "7e2f4e455c7e8697ae2362069b6d50249eea7285940cbc45e80df3395f5b38f4"}
# The tools a claim is shown, as the JUDGE contract judge-agent drafted declares them (INFRA-049, not
# yet ratified, so the shipped contracts give no FIGURES block and the shipped prompt differs on
# every claim that writes a figure until it is).
CLAIM_TOOLS_CONTRACT = {"JUDGE": {"judge": {"tasks": {"cell_claim": {"tools": ["find_cells", "locate_figures", "check_quote"]}}}}}
SELECTION_ROOTS = ("select", "tables", "_rank", "_matched", "load_config")   # what the builder calls

# A set derived from another splits with it.
FAMILY = {"vitaminc_same_page": "vitaminc", "tabfact_rows_removed": "tabfact", "c4_alike": "c4", "c4_figure_changed": "c4",
          "c4_figure_twin": "c4"}
# Plan lines: (set, source label, answer, pairs or claims wanted). Pairs double in both orders.
PLANS = {
    "dev_mix": {
        "pair": (("vitaminc", "REFUTES", "contradicts", 400), ("multinli", "contradiction", "contradicts", 300),
                 ("wanli", "contradiction", "contradicts", 300),
                 ("vitaminc", "SUPPORTS", "does not", 350), ("multinli", "entailment", "does not", 250),
                 ("multinli", "neutral", "does not", 250), ("wanli", "entailment", "does not", 200),
                 ("wanli", "neutral", "does not", 250), ("vitaminc_same_page", "other_case", "does not", 200),
                 ("vitaminc", "NOT ENOUGH INFO", "cannot tell", 500)),
        "claim": (("tabfact", "holds", "holds", 2000), ("tabfact", "refuted", "not met", 2000),
                  ("tabfact_rows_removed", "either", "cannot be settled", 1500)),
    },
    "permissive_mix": {
        "pair": (("multinli", "contradiction", "contradicts", 600), ("wanli", "contradiction", "contradicts", 600),
                 ("multinli", "entailment", "does not", 500), ("multinli", "neutral", "does not", 500),
                 ("wanli", "entailment", "does not", 400), ("wanli", "neutral", "does not", 400)),
        "claim": (("tabfact", "holds", "holds", 2000), ("tabfact", "refuted", "not met", 2000),
                  ("tabfact_rows_removed", "either", "cannot be settled", 1500)),
    },
}
ATTEMPT_PLANS = {
    1: PLANS,
    2: {"permissive_mix": {
        "pair": (("c4_alike", "alike", "does not", 2900), ("c4_figure_changed", "figure_changed", "contradicts", 600),
                 ("c4_figure_twin", "figure_twin", "does not", 600),
                 ("multinli", "contradiction", "contradicts", 200), ("wanli", "contradiction", "contradicts", 200),
                 ("multinli", "entailment", "does not", 150), ("multinli", "neutral", "does not", 150),
                 ("wanli", "entailment", "does not", 100), ("wanli", "neutral", "does not", 100)),
        "claim": (("tabfact", "holds", "holds", 2000), ("tabfact", "refuted", "not met", 2000),
                  ("tabfact_rows_removed", "either", "cannot be settled", 1500)),
    }},
}
# Attempt 2b (D-S62 item 5): at most a quarter of the mix from the benchmarks' own source families.
# TabFact is Wikipedia tables and MultiNLI's slate genre an online magazine, so the claims are cut
# to about 1,500 rows and that genre is left out; the pair plan is attempt 2's.
ATTEMPT_PLANS[3] = {"permissive_mix": {
    "pair": ATTEMPT_PLANS[2]["permissive_mix"]["pair"],
    "claim": (("tabfact", "holds", "holds", 545), ("tabfact", "refuted", "not met", 545),
              ("tabfact_rows_removed", "either", "cannot be settled", 410)),
}}
# Attempt 2c (lead, 8 Nov 14:28): most claim rows from tables outside the benchmarks' families. TAT-QA
# (financial-report tables, CC BY 4.0) gives claims made by Python from its own questions: a question
# the table answers with its gold answer holds; the same with one digit of that answer changed is not
# met; a question only its text answers cannot be settled by the cells. TabFact stays at attempt 2b's
# 1,500 rows. The claim reads "question answer", which is not how SciTab writes a claim.
ATTEMPT_PLANS[4] = {"permissive_mix": {
    "pair": ATTEMPT_PLANS[2]["permissive_mix"]["pair"],
    "claim": ATTEMPT_PLANS[3]["permissive_mix"]["claim"]
    + (("tatqa", "table_answer", "holds", 1500), ("tatqa_changed", "table_answer_changed", "not met", 1500),
       ("tatqa", "text_answer", "cannot be settled", 1200)),
}}
FAMILY.update(tatqa="tatqa", tatqa_changed="tatqa")
ATTEMPT_PAD_SHARE = {1: PAD_SHARE, 2: 0.0, 3: 0.0, 4: 0.0}
ATTEMPT_LEFT_OUT_GENRES = {1: (), 2: (), 3: ("slate",), 4: ("slate",)}   # MultiNLI genres, as the data names them
TATQA_FILE = "tatqa_dataset_train.json"
FORMS_PINS[4], SELECTOR_PINS[4] = FORMS_PINS[2], SELECTOR_PINS[2]
# Attempt 2d (lead, D-313: TAT-QA counts against FinDVer's family). Every table source left is in
# some benchmark's family, so the claims stay under the quarter as attempt 2b's do (about 1,850 rows
# at most beside attempt 2's pairs), split between Wikipedia and financial-report tables so the table
# rows span two kinds of document. Cannot be settled comes from TabFact's rows removed: TAT-QA's
# text-only answers rarely write a figure (7 found in attempt 2c).
ATTEMPT_PLANS[5] = {"permissive_mix": {
    "pair": ATTEMPT_PLANS[2]["permissive_mix"]["pair"],
    "claim": (("tabfact", "holds", "holds", 300), ("tabfact", "refuted", "not met", 300),
              ("tabfact_rows_removed", "either", "cannot be settled", 500),
              ("tatqa", "table_answer", "holds", 375), ("tatqa_changed", "table_answer_changed", "not met", 375)),
}}
FORMS_PINS[5], SELECTOR_PINS[5] = FORMS_PINS[2], SELECTOR_PINS[2]
ATTEMPT_PAD_SHARE[5] = 0.0
ATTEMPT_LEFT_OUT_GENRES[5] = ("slate",)
# Attempt 2e: 2d's claims at three quarters. 2d's family share was 24.2 percent at the C4 sample's
# point (14 percent of its hosts) and 25.8 at one sample error above it: too near the quarter.
ATTEMPT_PLANS[6] = {"permissive_mix": {
    "pair": ATTEMPT_PLANS[2]["permissive_mix"]["pair"],
    "claim": (("tabfact", "holds", "holds", 225), ("tabfact", "refuted", "not met", 225),
              ("tabfact_rows_removed", "either", "cannot be settled", 375),
              ("tatqa", "table_answer", "holds", 280), ("tatqa_changed", "table_answer_changed", "not met", 280)),
}}
FORMS_PINS[6], SELECTOR_PINS[6] = FORMS_PINS[2], SELECTOR_PINS[2]
ATTEMPT_PAD_SHARE[6] = 0.0
ATTEMPT_LEFT_OUT_GENRES[6] = ("slate",)
C4_FILE = "c4_en_train_00000.json.gz"
C4_DOCUMENT_SHARE = 0.03          # documents read, by digest of their address, before anything is kept
C4_PASSAGES = (6, 120)            # a document with fewer or more sentences is not read
C4_PROPOSALS = 10                 # proposals read per document, best first
MULTINLI_LABELS = {0: "entailment", 1: "neutral", 2: "contradiction"}


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def rank(seed, *parts):
    return sha("|".join([str(seed), *map(str, parts)]))


def share_of(seed, *parts):
    return int(rank(seed, *parts)[:8], 16) / 0xFFFFFFFF


def held_out(seed, name, group):
    """True when `group` of set `name` belongs to the held-out side, whatever is selected later."""
    return share_of(seed, "split", FAMILY.get(name, name), group) < HELD_OUT_SHARE


def words(text):
    return re.findall(r"\w+", str(text).lower())


def shingles(text):
    w = words(text)
    return {" ".join(w[i:i + SHINGLE]) for i in range(len(w) - SHINGLE + 1)}


class Overlap:
    """The development texts' shingles and ContraDoc's article titles, and the counts of what hit."""

    def __init__(self, contradoc_path, scitab_path):
        self.shingles, self.titles = set(), set()
        contradoc = json.loads(Path(contradoc_path).read_text(encoding="utf-8"))
        documents = [d["text"] for group in contradoc.values() for d in group.values()]
        for text in documents:
            self.shingles |= shingles(text)
            title = re.match(r"\s*=\s*(.+?)\s*=", text)
            if title:
                self.titles.add(" ".join(words(title.group(1))))
        scitab = json.loads(Path(scitab_path).read_text(encoding="utf-8"))
        for record in scitab:
            self.shingles |= shingles(record["table_caption"]) | shingles(record["claim"])
            for row in [record["table_column_names"], *record["table_content_values"]]:
                self.shingles |= shingles(" ".join(str(c) for c in row))
        self.counts = Counter()
        self.seen = Counter()
        self.development = {"contradoc_documents": len(documents), "scitab_records": len(scitab),
                            "shingles": len(self.shingles), "titles": len(self.titles)}

    def keep(self, name, texts, title=None):
        """False, and counted, when any text shares a run with development or `title` names an article."""
        self.seen[name] += 1
        if title is not None and " ".join(words(title)) in self.titles:
            self.counts[name + ":title"] += 1
            return False
        for text in texts:
            w = words(text)
            for i in range(len(w) - SHINGLE + 1):
                if " ".join(w[i:i + SHINGLE]) in self.shingles:
                    self.counts[name + ":text"] += 1
                    return False
        return True

    def report(self):
        return {n: {"read": self.seen[n], "removed_text": self.counts[n + ":text"], "removed_title": self.counts[n + ":title"]}
                for n in sorted(self.seen)}


def _jsonl(path):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def sentences_of(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", str(text)) if s.strip()]


MULTINLI_COLUMNS = ["promptID", "pairID", "premise", "hypothesis", "label", "genre"]


def multinli_parquet(raw):
    """MultiNLI's train rows as the fetched parquet holds them: the reader every real build uses."""
    import pyarrow.parquet as pq
    return pq.read_table(Path(raw) / "multinli_train.parquet", columns=MULTINLI_COLUMNS).to_pylist()


def read_pairs(root, overlap, multinli_rows=multinli_parquet, sets=None, left_out_genres=()):
    """Every usable pair: {set, id, group, label, a, b, share_alike}, with a the evidence side.
    `multinli_rows(raw)` gives MultiNLI's rows; the checks plant them without a parquet reader."""
    raw = Path(root) / "raw"
    out = []
    for row in multinli_rows(raw):
        if row["genre"] in left_out_genres:
            continue
        if row["label"] in MULTINLI_LABELS and overlap.keep("multinli", (row["premise"], row["hypothesis"])):
            out.append({"set": "multinli", "id": row["pairID"], "group": row["promptID"], "label": MULTINLI_LABELS[row["label"]],
                        "a": row["premise"], "b": row["hypothesis"], "share_alike": row["genre"] == "fiction"})
    for row in _jsonl(raw / "wanli_train.jsonl"):
        if overlap.keep("wanli", (row["premise"], row["hypothesis"])):
            out.append({"set": "wanli", "id": row["id"], "group": row["pairID"], "label": row["gold"], "a": row["premise"],
                        "b": row["hypothesis"], "share_alike": False})
    for row in (_jsonl(raw / "vitaminc_train.jsonl") if sets is None or "vitaminc" in sets else ()):
        if overlap.keep("vitaminc", (row["evidence"], row["claim"]), title=row["page"].replace("_", " ")):
            out.append({"set": "vitaminc", "id": row["unique_id"], "group": row["page"], "label": row["label"], "a": row["evidence"],
                        "b": row["claim"], "case": row["case_id"], "share_alike": True})
    return out


_FIGURE_TOKEN = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*(?![\w])")


def changed_figure(text, figure, seed, key):
    """`text` with its first `figure` written with one digit changed: the last non-zero digit (or the
    last digit, all being zero) moves by 1 to 3, chosen by digest, so the new value has the figure's
    own shape and size and is never an absurd one. None when no such change exists."""
    digits = [k for k, c in enumerate(figure) if c.isdigit()]
    nonzero = [k for k in digits if figure[k] != "0"]
    at = (nonzero or digits)[-1]
    old = int(figure[at])
    step = 1 + int(rank(seed, "figure_step", key)[:4], 16) % 3
    up = share_of(seed, "figure_up", key) < 0.5
    new_digit = old + step if (up and old + step <= 9) or old - step < 0 else old - step
    if at == digits[0] and new_digit == 0 and len(digits) > 1 and figure[at + 1:at + 2].isdigit():
        new_digit = old + step if old + step <= 9 else old - step
    if not 0 <= new_digit <= 9 or new_digit == old:
        return None
    new = figure[:at] + str(new_digit) + figure[at + 1:]
    found = re.search(r"(?<![\w.,])" + re.escape(figure) + r"(?![\w])", text)
    return None if found is None else text[:found.start()] + new + text[found.end():]


def read_documents(root, overlap, passage_pairs, seed, counts):
    """Attempt 2's same-document pairs from C4 (see the module text); `counts` gets the host names."""
    import gzip
    from urllib.parse import urlparse
    out = []
    with gzip.open(Path(root) / "raw" / C4_FILE, "rt", encoding="utf-8") as handle:
        for line in handle:
            doc = json.loads(line)
            url = doc.get("url") or ""
            if share_of(seed, "c4", url) >= C4_DOCUMENT_SHARE:
                continue
            items = passage_pairs.passages(doc["text"])
            if not C4_PASSAGES[0] <= len(items) <= C4_PASSAGES[1]:
                continue
            if not overlap.keep("c4", (doc["text"],)):
                continue
            counts[urlparse(url).hostname or ""] += 1
            proposals = passage_pairs.propose(items, C4_PROPOSALS)
            if not proposals:
                continue
            top = proposals[0]
            out.append({"set": "c4_alike", "id": url, "group": url, "label": "alike", "share_alike": False,
                        "a": items[top["a"]]["text"], "b": items[top["b"]]["text"]})
            for pair in proposals:
                a, b = items[pair["a"]]["text"], items[pair["b"]]["text"]
                shared = sorted(set(_FIGURE_TOKEN.findall(a)) & set(_FIGURE_TOKEN.findall(b)), key=lambda f: rank(seed, "pick_figure", url, f))
                changed = changed_figure(b, shared[0], seed, url) if shared else None
                if changed:
                    key = "%s#%d-%d" % (url, pair["a"], pair["b"])
                    out.append({"set": "c4_figure_changed", "id": key, "group": url, "label": "figure_changed", "share_alike": False,
                                "a": a, "b": changed})
                    out.append({"set": "c4_figure_twin", "id": key, "group": url, "label": "figure_twin", "share_alike": False,
                                "a": a, "b": b})
                    break
    return out


def same_page_pairs(pairs, seed):
    """Two evidence sentences of one page from different cases: about the page, about different
    things, and both written in the article. The prompt says such passages do not contradict."""
    by_page = {}
    for row in pairs:
        if row["set"] == "vitaminc" and row["label"] == "SUPPORTS":
            by_page.setdefault(row["group"], {}).setdefault(row["case"], row)
    out = []
    for page, cases in by_page.items():
        ordered = sorted(cases, key=lambda c: rank(seed, "same_page", page, c))
        if len(ordered) >= 2 and cases[ordered[0]]["a"] != cases[ordered[1]]["a"]:
            first, second = cases[ordered[0]], cases[ordered[1]]
            out.append({"set": "vitaminc_same_page", "id": ordered[0] + "+" + ordered[1], "group": page, "label": "other_case",
                        "a": first["a"], "b": second["a"], "share_alike": True})
    return out


def table_text(caption, header, rows, render):
    return str(caption).replace("\n", " ") + "\n\n" + render(header, rows)


def _tabfact_tables(root):
    folder = Path(root) / "tabfact"
    train = set(json.loads((folder / "train_id.json").read_text(encoding="utf-8")))
    for name in ("r1_training_all.json", "r2_training_all.json"):
        for table, value in json.loads((folder / name).read_text(encoding="utf-8")).items():
            if table in train and (folder / "csv" / table).is_file():
                yield table, value


def named_rows(cell_selection, text, claim):
    """The rows of a one-table `text` that the claim names, as the selector ranks them. Not the rows
    it shows: it fills a selection with rows the claim does not name."""
    found = cell_selection.tables(text)
    if len(found) != 1:
        return set()
    rows = cell_selection._rank(found[0], claim)[0]
    return {i for i, score in enumerate(rows) if cell_selection._matched(score)}


def read_claims(root, overlap, select, render, cell_selection, refused):
    """Every usable claim: {set, id, group, label, cells, claim}. The evidence is `select`'s, so it is
    the shape C shows. `tabfact_rows_removed`: the rows a claim names are taken out of its table, so
    the cells no longer settle it; a claim naming no row, or every row but one, yields none."""
    out = []
    folder = Path(root) / "tabfact"

    def selected(text, claim):
        try:
            return select(text, claim)
        except ValueError as exc:
            refused[str(exc)] += 1
            return None
    for table, (statements, labels, caption) in _tabfact_tables(root):
        with open(folder / "csv" / table, encoding="utf-8", newline="") as handle:
            grid = [row for row in csv.reader(handle, delimiter="#", quoting=csv.QUOTE_NONE)]
        if len(grid) < 3 or len({len(r) for r in grid}) != 1:
            continue
        header, body = grid[0], grid[1:]
        text = table_text(caption, header, body, render)
        if not overlap.keep("tabfact_table", (caption, " ".join(" ".join(r) for r in grid))):
            continue
        for number, (claim, label) in enumerate(zip(statements, labels)):
            if not overlap.keep("tabfact", (claim,)):
                continue
            key = "%s#%d" % (table, number)
            chosen = selected(text, claim)
            if chosen is None:
                continue
            out.append({"set": "tabfact", "id": key, "group": table, "label": "holds" if label == 1 else "refuted",
                        "cells": chosen["cells"], "claim": claim, "share_alike": False})
            named = named_rows(cell_selection, text, claim)
            left = [row for i, row in enumerate(body) if i not in named]
            if named and len(left) >= 2:
                reduced = selected(table_text(caption, header, left, render), claim)
                if reduced is not None:
                    out.append({"set": "tabfact_rows_removed", "id": key, "group": table, "label": "either",
                                "cells": reduced["cells"], "claim": claim, "share_alike": False})
    return out


def read_tatqa(root, overlap, select, render, refused, seed):
    """Attempt 2c's TAT-QA claims (see ATTEMPT_PLANS[4]). Only a single answer that writes a figure is
    used, so the changed answer is a real figure of the same shape; multi-span answers are not."""
    out = []
    path = Path(root) / "raw" / TATQA_FILE
    for entry in json.loads(path.read_text(encoding="utf-8")):
        grid = [[str(c) for c in row] for row in entry["table"]["table"]]
        if len(grid) < 3 or len({len(r) for r in grid}) != 1:
            continue
        uid = entry["table"]["uid"]
        if not overlap.keep("tatqa_table", (" ".join(" ".join(r) for r in grid),)):
            continue
        text = table_text("", grid[0], grid[1:], render)
        for question in entry["questions"]:
            answer = question["answer"]
            if isinstance(answer, list) or question["answer_type"] == "multi-span":
                continue
            answer = str(answer).strip()
            figures = _FIGURE_TOKEN.findall(answer)
            if not figures or question["answer_from"] not in ("table", "text"):
                continue
            claim = " ".join(part for part in (question["question"].strip(), answer, str(question.get("scale") or "").strip()) if part)
            if not overlap.keep("tatqa", (claim,)):
                continue
            try:
                chosen = select(text, claim)
            except ValueError as exc:
                refused["tatqa: " + str(exc)] += 1
                continue
            key = "%s#%s" % (uid, question["uid"])
            if question["answer_from"] == "text":
                out.append({"set": "tatqa", "id": key, "group": uid, "label": "text_answer", "cells": chosen["cells"], "claim": claim,
                            "share_alike": False})
                continue
            out.append({"set": "tatqa", "id": key, "group": uid, "label": "table_answer", "cells": chosen["cells"], "claim": claim,
                        "share_alike": False})
            changed_answer = changed_figure(answer, figures[-1], seed, key)
            if changed_answer is None:
                continue
            changed = claim.replace(answer, changed_answer, 1)
            try:
                chosen = select(text, changed)
            except ValueError as exc:
                refused["tatqa: " + str(exc)] += 1
                continue
            out.append({"set": "tatqa_changed", "id": key, "group": uid, "label": "table_answer_changed", "cells": chosen["cells"],
                        "claim": changed, "share_alike": False})
    return out


def padded(row, pool, seed):
    """`row` with each passage set inside sentences of other rows of its own set. The drawn word
    count depends on the row's id alone. The sentence that carried the label stays whole."""
    rng = random.Random(rank(seed, "pad", row["set"], row["id"]))
    low, high = PAD_WORDS

    def around(text):
        want = low * (high / low) ** rng.random()
        before, after, have = [], [], 0
        while have < want:
            sentence = pool[rng.randrange(len(pool))]
            (before if rng.random() < .5 else after).append(sentence)
            have += len(sentence.split())
        return " ".join(before + [text] + after)
    return dict(row, a=around(row["a"]), b=around(row["b"]), padded=True)


def band_of(tokens):
    for edge in BANDS:
        if tokens <= edge:
            return edge
    return None


def stratify(rows, seed, wanted):
    """`rows`, each with `answer`, `tokens` and `padded`, cut so that every cell of (padded, length
    band) holds the answers in the shares of `wanted` ({answer: count}), at most those counts in
    all. A cell too small to hold every answer holds none. Rows go in digest order."""
    total = sum(wanted.values())
    shares = {a: n / total for a, n in wanted.items()}
    cells = {}
    for row in rows:
        cells.setdefault((row["padded"], band_of(row["tokens"])), {}).setdefault(row["answer"], []).append(row)
    capacity = {cell: min(len(by.get(a, ())) / s for a, s in shares.items()) for cell, by in cells.items()}
    factor = min(1., total / max(sum(capacity.values()), 1))
    kept = []
    for cell, by in sorted(cells.items(), key=lambda item: str(item[0])):
        quota = {answer: int(capacity[cell] * factor * share) for answer, share in shares.items()}
        if min(quota.values()) == 0:
            continue
        for answer, count in quota.items():
            ordered = sorted(by[answer], key=lambda r: rank(seed, "keep", r["set"], r["id"]))
            kept += ordered[:count]
    return kept


def candidates(rows, plan, seed, side):
    """Per plan line, `count` x OVERSAMPLE rows of that (set, label) in digest order, on one side of
    the split, each with its answer. Held-out lines are scaled by the held-out share."""
    buckets = {}
    for row in rows:
        if held_out(seed, row["set"], row["group"]) == (side == "held_out"):
            buckets.setdefault((row["set"], row["label"]), []).append(row)
    picked, short, wanted = [], {}, Counter()
    for name, label, answer, count in plan:
        want = count if side == "train" else max(1, round(count * HELD_OUT_SHARE / (1 - HELD_OUT_SHARE)))
        wanted[answer] += want
        bucket = sorted(buckets.get((name, label), ()), key=lambda r: rank(seed, "pick", r["set"], r["id"]))
        taken = bucket[:want * OVERSAMPLE]
        if len(taken) < want:
            short["%s/%s" % (name, label)] = {"wanted": want, "found": len(taken)}
        picked += [dict(r, answer=answer) for r in taken]
    return picked, short, dict(wanted)


def surface_of(form, answer):
    for item in form["answers"]:
        if item["label"] == answer:
            return item["surface"]
    raise ValueError("no answer %r in the form" % answer)


def priced_pairs(chosen, config, render_choice, seed, pools, count, pad_share=PAD_SHARE):
    """Pairs, a share padded with no reference to the label, each with its token count."""
    out = []
    for row in chosen:
        made = dict(row, padded=False)
        if share_of(seed, "padded", row["set"], row["id"]) < pad_share:
            made = padded(row, pools[row["set"]], seed)
        user = render_choice(config, "pair", {"passage_a": made["a"], "passage_b": made["b"]})
        out.append(dict(made, tokens=count(user) + CHAT_OVERHEAD_TOKENS))
    return out


def pair_rows(kept, config, render_choice):
    form = config["choice"]["forms"]["pair"]
    out = []
    for row in kept:
        for order, first, second in (("ab", row["a"], row["b"]), ("ba", row["b"], row["a"])):
            out.append({"form": "pair", "set": row["set"], "source_id": row["id"], "group": row["group"], "source_label": row["label"],
                        "order": order, "padded": row["padded"], "share_alike": row["share_alike"], "answer": row["answer"],
                        "surface": surface_of(form, row["answer"]), "tokens": row["tokens"],
                        "user": render_choice(config, "pair", {"passage_a": first, "passage_b": second})})
    return out


def priced_claims(chosen, config, render_choice, count, judge_agent=None):
    out = []
    for row in chosen:
        slots = {"cells": row["cells"], "claim": row["claim"]}
        if judge_agent is not None:
            slots["tools"] = judge_agent.claim_tools(row["cells"], row["claim"], CLAIM_TOOLS_CONTRACT)
        user = render_choice(config, "claim", slots)
        out.append(dict(row, user=user, padded=False, tokens=count(user) + CHAT_OVERHEAD_TOKENS))
    return out


def claim_rows(kept, config):
    form = config["choice"]["forms"]["claim"]
    return [{"form": "claim", "set": r["set"], "source_id": r["id"], "group": r["group"], "source_label": r["label"], "order": None,
             "padded": False, "share_alike": r["share_alike"], "answer": r["answer"], "surface": surface_of(form, r["answer"]),
             "tokens": r["tokens"], "user": r["user"]} for r in kept]


def under_cap(rows):
    kept = [r for r in rows if r["tokens"] <= MAX_TOKENS]
    return kept, len(rows) - len(kept)


def ordered(rows, side, seed):
    rows = sorted(rows, key=lambda r: rank(seed, "order", r["form"], r["set"], r["source_id"], r["order"]))
    for number, row in enumerate(rows, 1):
        row["row_id"] = "%s%06d" % ("h" if side == "held_out" else "t", number)
    return rows


def band_shares(rows):
    """Per form and cell of (padded, band): the rows and each answer's share, as the check to read."""
    cells = {}
    for row in rows:
        key = "%s padded=%s band<=%s" % (row["form"], row["padded"], band_of(row["tokens"]))
        cells.setdefault(key, Counter())[row["answer"]] += 1
    return {k: {"rows": sum(c.values()), "shares": {a: round(n / sum(c.values()), 4) for a, n in sorted(c.items())}}
            for k, c in sorted(cells.items())}


def summary(rows):
    tokens = sorted(r["tokens"] for r in rows)
    return {"rows": len(rows), "tokens": sum(tokens), "mean_tokens": round(sum(tokens) / len(tokens), 1) if tokens else 0,
            "p95_tokens": tokens[int(len(tokens) * .95)] if tokens else 0, "max_tokens": tokens[-1] if tokens else 0,
            "by_answer": dict(sorted(Counter("%s/%s" % (r["form"], r["answer"]) for r in rows).items())),
            "by_set": dict(sorted(Counter("%s/%s" % (r["set"], r["answer"]) for r in rows).items())),
            "padded": sum(r["padded"] for r in rows), "share_alike_rows": sum(r["share_alike"] for r in rows),
            "share_alike_by_set": dict(sorted(Counter(r["set"] for r in rows if r["share_alike"]).items())),
            "band_shares": band_shares(rows)}


def forms_digest(config):
    return sha(json.dumps(config["choice"]["forms"], sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def _definitions(tree):
    """Each module-level name of `tree` with the statement that binds it."""
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        out[name.id] = node
    return out


def reached(paths, roots):
    """{(module, name): dumped syntax tree} of the definitions `roots` reach: a name a reached body
    loads that its module defines, and `module.name` for a module of `paths` ({module: file}). Only
    what runs, so comments, layout and unreached code leave it unchanged."""
    trees = {m: _definitions(ast.parse(Path(f).read_text(encoding="utf-8"))) for m, f in paths.items()}
    seen, todo = {}, list(roots)
    while todo:
        module, name = todo.pop()
        node = trees[module].get(name)
        if node is None or (module, name) in seen:
            continue
        seen[(module, name)] = ast.dump(node, include_attributes=False)
        for inner in ast.walk(node):
            if isinstance(inner, ast.Name) and inner.id in trees[module]:
                todo.append((module, inner.id))
            elif isinstance(inner, ast.Attribute) and isinstance(inner.value, ast.Name) and inner.value.id in trees:
                todo.append((inner.value.id, inner.attr))
    return seen


def selector_digest(doc_judge, cell_selection, reach=None, judge_agent=None):
    """The digest of what a selection runs (see the module text), and the claim tools when given."""
    import pairing_map
    paths = {"doc_judge": doc_judge.__file__, "cell_selection": cell_selection.__file__, "pairing_map": pairing_map.__file__}
    roots = [("doc_judge", "select_cells")] + [("cell_selection", name) for name in SELECTION_ROOTS]
    if judge_agent is not None:
        paths["judge_agent"] = judge_agent.__file__
        roots.append(("judge_agent", "claim_tools"))
    parts = sorted("%s.%s %s" % (m, n, d) for (m, n), d in (reach or reached)(paths, roots).items())
    config = json.loads(Path(cell_selection.CONFIG_PATH).read_text(encoding="utf-8"))
    return sha("\n".join(parts) + "\n" + json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def load_judge(source):
    """doc_judge, the bundle renderer and the prompt config, from `source`."""
    source = Path(source).resolve()
    sys.path[:0] = [str(source), str(source / "benchmark" / "baselines"), str(source / "scripts"), str(source / "tools")]
    from benchmark.adapters.common import bundle
    import cell_selection
    import doc_judge
    path = source / "benchmark" / "baselines" / "choice_judge_prompt.json"
    config = doc_judge.check_config(json.loads(path.read_text(encoding="utf-8")))
    judge_agent = None
    if "{tools}" in config["choice"]["forms"]["claim"]["template"]:
        import judge_agent
    return doc_judge, cell_selection, bundle.render_table, config, judge_agent


def pinned(doc_judge, cell_selection, config, forms=None, selector=None, attempt=1, judge_agent=None):
    """Refuses when C's forms or selector are not the ones this attempt's rows are built against."""
    found = forms_digest(config), selector_digest(doc_judge, cell_selection, judge_agent=judge_agent)
    if found[0] != (forms or FORMS_PINS[attempt]):
        raise ValueError("C's forms are not the pinned ones: " + found[0])
    if found[1] != (selector or SELECTOR_PINS[attempt]):
        raise ValueError("C's selector is not the pinned one: " + found[1])
    return {"forms_sha256": found[0], "selector_sha256": found[1]}


def source_pins(judge_source, attempt):
    """The forms and selector digests `judge_source` gives under `attempt`: what a pin is set to."""
    doc_judge, cell_selection, _render, config, judge_agent = load_judge(judge_source)
    return forms_digest(config), selector_digest(doc_judge, cell_selection, judge_agent=judge_agent)


def write_rows(path, rows):
    data = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for r in rows).encode("utf-8")
    Path(path).write_bytes(data)
    return sha(data)


def build_side(pairs, claims, plans, config, render_choice, seed, side, pools, count, pad_share=PAD_SHARE, judge_agent=None):
    pair_chosen, short_pairs, pair_wanted = candidates(pairs, plans["pair"], seed, side)
    claim_chosen, short_claims, claim_wanted = candidates(claims, plans["claim"], seed, side)
    priced, dropped_pairs = under_cap(priced_pairs(pair_chosen, config, render_choice, seed, pools, count, pad_share))
    claimed, dropped_claims = under_cap(priced_claims(claim_chosen, config, render_choice, count, judge_agent))
    rows = pair_rows(stratify(priced, seed, pair_wanted), config, render_choice) + claim_rows(stratify(claimed, seed, claim_wanted), config)
    return ordered(rows, side, seed), dropped_pairs + dropped_claims, dict(short_pairs, **short_claims)


def build(train_root, contradoc_dev, scitab_dev, out, judge_source=ROOT, seed=SEED, count=None, forms=None, selector=None,
          multinli_rows=multinli_parquet, attempt=1):
    doc_judge, cell_selection, render, config, judge_agent = load_judge(judge_source)
    pins = pinned(doc_judge, cell_selection, config, forms, selector, attempt, judge_agent)
    if count is None:
        from tokenizers import Tokenizer
        tokenizer = Tokenizer.from_file(str(Path(train_root) / "raw" / "phi4_tokenizer.json"))

        def count(text):
            return len(tokenizer.encode(text, add_special_tokens=False).ids)
    overlap = Overlap(contradoc_dev, scitab_dev)
    plans_of = ATTEMPT_PLANS[attempt]
    sets = {line[0] for plans in plans_of.values() for line in plans["pair"]}
    pairs = read_pairs(train_root, overlap, multinli_rows, sets, ATTEMPT_LEFT_OUT_GENRES[attempt])
    pairs += same_page_pairs(pairs, seed)
    hosts = Counter()
    if sets & {"c4_alike", "c4_figure_changed", "c4_figure_twin"}:
        import passage_pairs
        pairs += read_documents(train_root, overlap, passage_pairs, seed, hosts)
    refused = Counter()
    claims = read_claims(train_root, overlap, doc_judge.select_cells, render, cell_selection, refused)
    claim_sets = {line[0] for plans in plans_of.values() for line in plans["claim"]}
    if claim_sets & {"tatqa", "tatqa_changed"}:
        claims += read_tatqa(train_root, overlap, doc_judge.select_cells, render, refused, seed)
    pools = {}
    for row in pairs:
        if row["set"] in ("multinli", "wanli", "vitaminc") and not row["share_alike"] or row["set"] == "vitaminc":
            pool = pools.setdefault(row["set"], [])
            if len(pool) < 40000:
                pool.extend(sentences_of(row["a"]))
    pools["vitaminc_same_page"] = pools.get("vitaminc", [])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = dict(pins, schema=SCHEMA, seed=seed, max_tokens=MAX_TOKENS, held_out_share=HELD_OUT_SHARE, pad_share=PAD_SHARE, pad_words=PAD_WORDS,
                    bands=BANDS, shingle_words=SHINGLE, tool_sha256=sha(Path(__file__).read_bytes()),
                    development_read=overlap.development, overlap=overlap.report(), selection_refused=dict(sorted(refused.items())), mixes={},
                    attempt=attempt, pad_share_used=ATTEMPT_PAD_SHARE[attempt],
                    claim_tools_contract=CLAIM_TOOLS_CONTRACT if judge_agent is not None else None,
                    domain_mix={"documents": sum(hosts.values()), "hosts": len(hosts),
                                "top_hosts": [[h, n] for h, n in sorted(hosts.items(), key=lambda kv: (-kv[1], kv[0]))[:100]],
                                "documents_on_hosts_with_one_document": sum(1 for n in hosts.values() if n == 1)})
    for mix, plans in plans_of.items():
        usable = pairs if mix == "dev_mix" else [p for p in pairs if not p["share_alike"]]
        sides = {}
        written = {}
        for side in ("train", "held_out"):
            rows, dropped, short = build_side(usable, claims, plans, config, doc_judge.render_choice, seed, side, pools, count,
                                              ATTEMPT_PAD_SHARE[attempt], judge_agent)
            name = "judge_%s_%s.jsonl" % (mix, side)
            sides[side] = dict(summary(rows), file=name, sha256=write_rows(out / name, rows), dropped_over_cap=dropped, plan_short=short)
            written[side] = rows
        family = lambda r: (FAMILY.get(r["set"], r["set"]), r["group"])
        if {family(r) for r in written["train"]} & {family(r) for r in written["held_out"]}:
            raise ValueError("a group sits on both sides of the split")
        if mix == "permissive_mix" and any(r["share_alike"] for side in written.values() for r in side):
            raise ValueError("a share-alike row reached the permissive mix")
        manifest["mixes"][mix] = sides
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--train-root", required=True)
    parser.add_argument("--contradoc-dev", required=True)
    parser.add_argument("--scitab-dev", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--judge-source", default=str(ROOT))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--attempt", type=int, choices=sorted(ATTEMPT_PLANS), default=1)
    args = parser.parse_args(argv)
    manifest = build(args.train_root, args.contradoc_dev, args.scitab_dev, args.out, args.judge_source, args.seed, attempt=args.attempt)
    print(json.dumps({"overlap": manifest["overlap"], "selection_refused": manifest["selection_refused"], "mixes": {m: {s: {k: v for k, v in d.items() if k != "band_shares"} for s, d in x.items()}
                                                                  for m, x in manifest["mixes"].items()}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
