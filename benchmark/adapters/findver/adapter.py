"""FinDVer adapter (preregistration sections 1, 3, 5.2, 5.5, 5.6).

One item per claim; the document is the filing (`report`). Its paragraphs and tables
are written in context-index order, one part each, a table as SciTab's is. One rule per
claim (CONV-<opaque item id>). The split is official: testmini is development, test
the holdout pool minus any item whose report also appears in testmini. FLAG = refuted,
CLEAR = entailed; a refusal maps to ABSTAIN (the benchmark has no refusal class).

Written on hand-written synthetic items (D-019), then confirmed on the B-dev development
items (S4c item 4). The release keeps claims and filings apart: the items file
(`data/testmini.json`, `data/test.json`) is a list of claims, each naming its filing by
file name in `report`, and the filing is `financial_reports/<report>`, an object whose
`context` is the list of its entries. `build --reports <folder>` names the filings'
folder; by default it is `financial_reports` beside the items file's folder, as the
release lays it out.

Usage: as the ContraDoc adapter (build, label, score), and
    py -3.12 benchmark/adapters/findver/adapter.py split --input <file> --official development|holdout [--testmini <file>]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from common import bundle, cli, cut, ids, mapping, metrics  # noqa: E402

BENCHMARK = "findver"
RULE_NAME = "Claim"
RULE_TEMPLATE = "Claim about the filing: {claim} The claim must agree with the passages of the filing."

# --- source schema --------------------------------------------------------------------
# Confirmed on the B-dev development items (testmini: 700 claims, 255 filings).
# The items file: a JSON list of claim records.
ITEM_ID_FIELD = "example_id"        # documented; a string, unique
REPORT_FIELD = "report"             # documented: the document id, the filing's file name
CLAIM_FIELD = "statement"           # confirmed: the claim text
LABEL_FIELD = "entailment_label"    # confirmed: a boolean in every record
GOLD_VALUES = {True: "entailed", False: "refuted"}   # confirmed: true is entailed
EVIDENCE_FIELD = "relevant_context" # confirmed: a list of integer context ids, never empty
SUBSET_FIELD = "subset"             # confirmed: `ie`, `numeric` or `knowledge` (the paper's
                                    # FDV-IE, FDV-MATH, FDV-KNOW)
SPLIT_FIELD = "split"               # confirmed: the official split each record belongs to
OFFICIAL_SPLITS = {"testmini": ids.DEVELOPMENT, "test": ids.HOLDOUT}
# A filing: a JSON object; `context` lists its entries in id order.
CONTEXT_FIELD = "context"           # confirmed
ENTRY_ID_FIELD = "id"               # confirmed: an integer, contiguous from the base
ENTRY_TEXT_FIELD = "context"        # confirmed: a string, a table's rows written as pipe rows
ENTRY_KIND_FIELD = "type"           # confirmed: `paragraph` or `table`
TABLE_KIND = "table"
CONTEXT_INDEX_BASE = 0              # confirmed: every filing's ids start at 0
URL_FIELD = "url"                   # confirmed: the filing's EDGAR address
REPORTS_FOLDER = "financial_reports"   # the release's folder of filings, beside `data/`
# The issuer for the sensitivity bootstrap (section 4) is recorded per filing as
# `issuer_cik`, the integer after `/edgar/data/` in the filing's `url` (present in every
# development filing); the ticker in `report` is not used, because one issuer files under
# more than one ticker.
_CIK = re.compile(r"/edgar/data/(\d+)/")
# ---------------------------------------------------------------------------------------
SPLIT_OPTIONS = (("--official", "development or holdout: the official split the input file is"),
                 ("--testmini", "the testmini file; reports it holds are removed from a holdout file"))
BUILD_OPTIONS = (("--reports", "the folder of filings (default: financial_reports beside the "
                               "items file's folder, as the release lays it out)"),)

SPEC = mapping.Spec(
    BENCHMARK,
    labels={mapping.FLAG: "refuted", mapping.CLEAR: "entailed", mapping.UNDECIDED: None},
    b1_labels={"refuted": mapping.FLAG, "entailed": mapping.CLEAR, "undecided": mapping.UNDECIDED},
    s2=True)


def read_source(path) -> list:
    """The claim records of an items file. A filing's text is read by `read_filing`."""
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ValueError("expected a list of claim records")
    return records


def reports_folder(input_path, given=None) -> Path:
    return Path(given) if given else Path(input_path).resolve().parent.parent / REPORTS_FOLDER


def read_filing(folder, report) -> tuple:
    """(entries, SHA-256 of the file, url) of one filing. Refuses a name that leaves the
    folder, entries out of id order, and an entry that is not a string."""
    name = ids.key_string(report)
    if Path(name).name != name or name in ("", ".", ".."):
        raise ValueError("a report name is a file name: " + repr(name))
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError("no filing %s in the reports folder" % name)
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    entries = data.get(CONTEXT_FIELD) if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("filing %s has no %r list" % (name, CONTEXT_FIELD))
    for offset, entry in enumerate(entries):
        if not isinstance(entry, dict) or entry.get(ENTRY_ID_FIELD) != offset + CONTEXT_INDEX_BASE:
            raise ValueError("filing %s: entry %d does not carry id %d" % (name, offset, offset + CONTEXT_INDEX_BASE))
        if not isinstance(entry.get(ENTRY_TEXT_FIELD), str):
            raise ValueError("filing %s: entry %d has no text" % (name, offset))
    return entries, hashlib.sha256(raw).hexdigest(), data.get(URL_FIELD)


def _pipe_row(line: str) -> bool:
    return line.lstrip().startswith("|")


def _separator(line: str) -> bool:
    return bool(re.fullmatch(r"\s*\|(\s*:?-+:?\s*\|)+\s*", line))


def table_text(text: str) -> str:
    """A table entry written as SciTab's table is (section 5.6): the release stores the
    rows as pipe rows with no separator row, between lines of text. In each run of pipe
    rows the first row is the header and a separator row as wide as it is written after
    it, unless one is there; every other line is kept as given."""
    lines = text.split("\n")
    out = []
    for k, line in enumerate(lines):
        out.append(line)
        starts_run = _pipe_row(line) and (k == 0 or not _pipe_row(lines[k - 1]))
        if starts_run and not _separator(line):
            following = lines[k + 1] if k + 1 < len(lines) else ""
            if not _separator(following):
                width = max(1, line.strip().strip("|").count("|") + 1)
                out.append("|" + "---|" * width)
    return "\n".join(out)


def entry_text(entry):
    """(part text, kind, words) for one context entry. A table's words are its cell words
    (pipes not counted), as the cut rule counts them (section 5.3)."""
    text, kind = entry[ENTRY_TEXT_FIELD], entry.get(ENTRY_KIND_FIELD)
    if kind == TABLE_KIND:
        return table_text(text), "table", cut.words(text)
    return text, "paragraph", ids.word_count(text)


def _reports(records):
    reports = {}
    for r in records:
        reports.setdefault(ids.key_string(r[REPORT_FIELD]), []).append(r)
    return reports


def _gold(record) -> str:
    value = record.get(LABEL_FIELD)
    if not isinstance(value, bool):
        raise ValueError("%s is not a boolean for %s: %r" % (LABEL_FIELD, record.get(ITEM_ID_FIELD), value))
    return GOLD_VALUES[value]


def documents(records, options=None) -> list:
    """The filings. The side is the declared official split; with --testmini on a
    holdout build, a report that also appears in testmini is refused (section 1). An item
    whose own `split` names the other official split is refused."""
    options = options or {}
    side = options.get("side") or "official (undeclared, development build)"
    if options.get("testmini") and side == ids.HOLDOUT:
        overlap = {ids.key_string(r[REPORT_FIELD]) for r in read_source(options["testmini"])}
        found = sorted({ids.key_string(r[REPORT_FIELD]) for r in records} & overlap)
        if found:
            raise ValueError("holdout reports that also appear in testmini: " + ", ".join(found[:10]))
    elif side == ids.HOLDOUT and not options.get("development"):
        raise ValueError("a FinDVer holdout build needs --testmini (section 1 removes overlapping reports)")
    if side in (ids.DEVELOPMENT, ids.HOLDOUT):
        wrong = sorted(ids.key_string(r[ITEM_ID_FIELD]) for r in records
                       if OFFICIAL_SPLITS.get(r.get(SPLIT_FIELD)) != side)
        if wrong:
            raise ValueError("items whose official split is not the declared side %s: %s"
                             % (side, ", ".join(wrong[:10])))
    claim_ids = [ids.key_string(r[ITEM_ID_FIELD]) for r in records]
    if len(set(claim_ids)) != len(claim_ids):
        raise ValueError("duplicate example id")
    folder = reports_folder(options.get("input_path", "."), options.get("reports"))
    out = []
    for report, claims in sorted(_reports(records).items()):
        entries, digest, url = read_filing(folder, report)
        parts = []
        for offset, entry in enumerate(entries):
            text, kind, count = entry_text(entry)
            parts.append({"text": text, "words": count,
                          "source": {"context_index": offset + CONTEXT_INDEX_BASE, "kind": kind}})
        rules, items = [], []
        for claim in claims:
            item_id = ids.opaque_item_id(BENCHMARK, claim[ITEM_ID_FIELD])
            rid = bundle.RULE_ID_PREFIX + item_id
            evidence = []
            for index in claim.get(EVIDENCE_FIELD) or []:
                if not isinstance(index, int) or isinstance(index, bool):
                    raise ValueError("context index %r is not an integer for %s" % (index, claim[ITEM_ID_FIELD]))
                part = index - CONTEXT_INDEX_BASE + 1
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
        cik = _CIK.search(url) if isinstance(url, str) else None
        out.append({"document_id": ids.opaque_document_id(BENCHMARK, claims[0][REPORT_FIELD]),
                    "source_document_id": claims[0][REPORT_FIELD], "split_key": claims[0][REPORT_FIELD],
                    "cluster": claims[0][REPORT_FIELD], "parts": parts,
                    "rules": rules, "items": items, "side": side,
                    "record_extra": {"context_index_base": CONTEXT_INDEX_BASE,
                                     "report_sha256": digest,
                                     "issuer_cik": int(cik.group(1)) if cik else None}})
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
