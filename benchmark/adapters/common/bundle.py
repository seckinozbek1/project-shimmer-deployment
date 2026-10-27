"""The one bundle writer: preregistration section 5.6 and 5.5 in the input format
`input-format-v1-draft` (docs/INPUT_FORMAT.md on loop/s03).

Everything the input format decides lives in this module, so a later version of the
format changes one file. A bundle, for one document:

  <out>/<opaque document id>/
    context/<opaque document id>.md     `# D-<id>`, then one `## P-NNNNN` unit per part
    context/_review_targets.json        the target alone, empty grounding and prior
    conventions/rules.md                `# Review rules`, one heading and paragraph per rule
    answer_key.json                     gold, read only by the scorer (section 9)
  <out>/items.json                      the item table, beside the bundles, no gold
  <out>/parts.json                      unit id per part and the source span or index

Nothing inside a bundle carries a source id. Build output is byte-identical for the
same input: no clock, no randomness, a fixed order and LF line endings everywhere.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import cut as cut_rule
from . import ids

INPUT_FORMAT_VERSION = "input-format-v1-draft"
TITLE_PREFIX = "# D-"
PART_HEADING = "## P-%05d"
PART_LABEL_LINE = "Passage: part"
RULES_TITLE = "# Review rules"
RULE_TAGS = "[required] [conformance]"
RULE_ID_PREFIX = "CONV-"
TASK_LINE = "Review the document against the conventions."
CONTEXT_DIR = "context"
CONVENTIONS_DIR = "conventions"
MANIFEST_NAME = "_review_targets.json"
RULES_NAME = "rules.md"
ANSWER_NAME = "answer_key.json"
ITEM_TABLE_NAME = "items.json"
PARTS_RECORD_NAME = "parts.json"
_SLUG_RUN = re.compile(r"[^a-z0-9]+")
_WHITESPACE_RUN = re.compile(r"\s+")
_RULE_ID = re.compile(r"CONV-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")


# ---------------------------------------------------------------------------
# text helpers


def one_space(text: str) -> str:
    """Each run of whitespace replaced by one space and nothing else changed (5.5)."""
    return _WHITESPACE_RUN.sub(" ", text)


def normalise_space(text: str) -> str:
    """Whitespace-normalised form used for containment (sections 3.1, 3.2): runs of
    whitespace to one space, trimmed."""
    return " ".join(text.split())


def blank_line_paragraphs(text: str):
    """[(start, end)] character spans of the blank-line paragraphs of `text`. A line is
    blank when it holds only whitespace. Lines are split at LF only."""
    spans, start, end, pos = [], None, None, 0
    for line in text.split("\n"):
        line_end = pos + len(line)
        if line.strip() == "":
            if start is not None:
                spans.append((start, end))
                start = None
        else:
            if start is None:
                start = pos
            end = line_end
        pos = line_end + 1
    if start is not None:
        spans.append((start, end))
    return spans


def table_cell(value) -> str:
    """A cell's text as given, `|` written as `\\|`; a line break would end the row, so
    each one is written as a space."""
    text = "" if value is None else str(value)
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return text.replace("|", "\\|")


def render_table(header, rows) -> str:
    """A pipe-delimited Markdown table: header row, separator row, body rows."""
    if not header:
        raise ValueError("a table needs a header row")
    width = len(header)
    lines = ["| " + " | ".join(table_cell(c) for c in header) + " |",
             "|" + "---|" * width]
    for row in rows:
        lines.append("| " + " | ".join(table_cell(c) for c in row) + " |")
    return "\n".join(lines)


def table_words(header, rows) -> int:
    return sum(ids.word_count("" if c is None else str(c)) for row in [header, *rows] for c in row)


def escape_line(line: str) -> str:
    """A source line whose first non-blank character is `#` gets a backslash before that
    `#`, so it never starts a unit."""
    stripped = line.lstrip(" \t")
    if stripped.startswith("#"):
        cut_at = len(line) - len(stripped)
        return line[:cut_at] + "\\" + stripped
    return line


def unescape_line(line: str) -> str:
    stripped = line.lstrip(" \t")
    if stripped.startswith("\\#"):
        cut_at = len(line) - len(stripped)
        return line[:cut_at] + stripped[1:]
    return line


def part_lines(text: str):
    """The part's lines as written: CR before LF dropped, leading and trailing blank
    lines dropped, every line escaped."""
    lines = [l[:-1] if l.endswith("\r") else l for l in text.split("\n")]
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()
    return [escape_line(l) for l in lines]


# ---------------------------------------------------------------------------
# units


def slug(heading: str) -> str:
    value = _SLUG_RUN.sub("-", heading.lower()).strip("-")[:40]
    return value or "unit"


def heading_text(k: int) -> str:
    return (PART_HEADING % k)[3:]


def unit_id(k: int) -> str:
    """The unit id the input format gives the k-th `## P-NNNNN` heading (section 2).
    PROVISIONAL above 99 parts: the format says two digits from 01, and whether a
    position above 99 keeps its id is open (preregistration section 12, item 4)."""
    return "u%02d-%s" % (k, slug(heading_text(k)))


def render_document(document_id: str, part_texts) -> str:
    blocks = [TITLE_PREFIX + document_id]
    for k, text in enumerate(part_texts, start=1):
        body = part_lines(text)
        block = PART_HEADING % k + "\n\n" + PART_LABEL_LINE
        if body:
            block += "\n\n" + "\n".join(body)
        blocks.append(block)
    return "\n\n".join(blocks) + "\n"


def read_units(document_text: str):
    """[(unit_id, heading line, label line, text)] read back from a written document:
    the structural reading the gate check and the scorer use. Text is unescaped."""
    units, current = [], None
    position = 0
    for line in document_text.split("\n"):
        if re.match(r"^#{2,6} ", line):
            position += 1
            current = [unit_id(position), line, []]
            units.append(current)
        elif current is not None:
            current[2].append(unescape_line(line))
    out = []
    for uid, heading, lines in units:
        while lines and lines[0].strip() == "":
            lines.pop(0)
        label = lines.pop(0) if lines else ""
        out.append((uid, heading, label, "\n".join(lines).strip("\n")))
    return out


# ---------------------------------------------------------------------------
# conventions, manifest, answer key


def check_rule(rule) -> None:
    rid, text = rule["rule_id"], rule["text"]
    match = _RULE_ID.match(rid)
    if not rid.startswith(RULE_ID_PREFIX) or not match or match.group(0) != rid:
        raise ValueError("not an operator rule id: " + repr(rid))
    if "\n" in text or "\r" in text:
        raise ValueError("a rule text is one paragraph on one line: " + rid)
    if not rule["name"] or any(ch in rule["name"] for ch in "[]\n"):
        raise ValueError("a rule name is plain words: " + rid)


def render_rules(rules) -> str:
    out = [RULES_TITLE, ""]
    for rule in sorted(rules, key=lambda r: r["rule_id"]):
        check_rule(rule)
        out += ["## %s %s %s" % (rule["rule_id"], rule["name"], RULE_TAGS), "", rule["text"], ""]
    return "\n".join(out) + "\n"


def manifest(document_file: str) -> dict:
    return {"targets": [document_file], "grounding": [], "prior": [],
            "source": "operator", "resolved_at": ""}


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


# ---------------------------------------------------------------------------
# the writer


def _evidence_units(item, part_texts, unit_ids):
    """Units holding the item's evidence: by part index, or by whitespace-normalised
    containment of each evidence text in a part's source text."""
    found = set()
    for index in item.get("evidence_parts") or ():
        if 1 <= index <= len(unit_ids):
            found.add(unit_ids[index - 1])
    for sentence in item.get("evidence_texts") or ():
        needle = normalise_space(sentence)
        if not needle:
            continue
        for uid, text in zip(unit_ids, part_texts):
            if needle in normalise_space(text):
                found.add(uid)
    return sorted(found)


def build_document(benchmark: str, doc: dict, cut=None):
    """(document text, parts record, answer rows) for one document. `doc` carries
    document_id, source_document_id, split_key, cluster, source_words, parts
    ([{text, source}]), rules ([{rule_id, name, text}]) and items ([{item_id,
    source_item_id, rule_id, gold, location_measurable, evidence_parts or
    evidence_texts, extra}])."""
    rule_ids = [r["rule_id"] for r in doc["rules"]]
    item_rules = [i["rule_id"] for i in doc["items"]]
    if len(set(rule_ids)) != len(rule_ids) or sorted(rule_ids) != sorted(item_rules):
        raise ValueError("one rule per item and one item per rule: " + doc["document_id"])
    if not doc["parts"]:
        raise ValueError("a document with no part cannot be bundled: " + doc["document_id"])
    source_texts = [p["text"] for p in doc["parts"]]
    texts = list(source_texts)
    info = cut_rule.not_cut(texts)
    if cut is not None:
        budget, count = cut
        texts, info = cut_rule.cut_parts(
            texts, budget, count, lambda kept: render_document(doc["document_id"], kept))
    all_ids = [unit_id(k) for k in range(1, len(source_texts) + 1)]
    unit_ids = all_ids[:len(texts)]
    text = render_document(doc["document_id"], texts)
    answers = []
    for item in sorted(doc["items"], key=lambda i: i["item_id"]):
        everywhere = _evidence_units(item, source_texts, all_ids)
        evidence = [u for u in everywhere if u in unit_ids]
        answers.append(dict({
            "item_id": item["item_id"], "rule_id": item["rule_id"], "gold": item["gold"],
            "location_measurable": bool(item.get("location_measurable")),
            "evidence_unit_ids": evidence,
            "evidence_beyond_cut": len(everywhere) > len(evidence),
        }, **(item.get("extra") or {})))
    parts = [{"part": k, "unit_id": unit_ids[k - 1], "source": doc["parts"][k - 1]["source"]}
             for k in range(1, len(texts) + 1)]
    dropped = [{"part": k, "source": doc["parts"][k - 1]["source"]}
               for k in range(len(texts) + 1, len(doc["parts"]) + 1)]
    record = {
        "document_id": doc["document_id"],
        "source_document_id": doc["source_document_id"],
        "split_key": ids.key_string(doc["split_key"]),
        "side": ids.split_side(doc["split_key"]) if doc.get("hash_split", True) else doc.get("side"),
        "cluster": ids.key_string(doc["cluster"]),
        "source_words": doc["source_words"],
        "length_band": ids.length_band(doc["source_words"]),
        "cut": info,
        "parts": parts,
        "parts_beyond_cut": dropped,
        "items": [a["item_id"] for a in answers],
    }
    record.update(doc.get("record_extra") or {})
    return text, record, answers


def write_bundles(out_dir, benchmark: str, documents, cut=None) -> dict:
    """Write one bundle per document under `out_dir`, the item table and the parts
    record beside them. Refuses a non-empty `out_dir`. Returns the summary."""
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("the output folder is not empty: " + str(out))
    seen_docs, seen_items, table, records = set(), set(), [], []
    for doc in sorted(documents, key=lambda d: d["document_id"]):
        doc_id = doc["document_id"]
        if doc_id in seen_docs:
            raise ValueError("two documents share the opaque id " + doc_id)
        seen_docs.add(doc_id)
        text, record, answers = build_document(benchmark, doc, cut)
        name = doc_id + ".md"
        bundle = out / doc_id
        write_text(bundle / CONTEXT_DIR / name, text)
        write_json(bundle / CONTEXT_DIR / MANIFEST_NAME, manifest(name))
        write_text(bundle / CONVENTIONS_DIR / RULES_NAME, render_rules(doc["rules"]))
        write_json(bundle / ANSWER_NAME, {
            "document": name, "task_given_to_the_pipeline": TASK_LINE, "twin_of": "",
            "planted": [], "clean": [], "benchmark": benchmark,
            "input_format": INPUT_FORMAT_VERSION, "items": answers})
        for item in sorted(doc["items"], key=lambda i: i["item_id"]):
            if item["item_id"] in seen_items:
                raise ValueError("two items share the opaque id " + item["item_id"])
            seen_items.add(item["item_id"])
            table.append({"item_id": item["item_id"], "document_id": doc_id,
                          "rule_id": item["rule_id"], "benchmark": benchmark,
                          "source_item_id": ids.key_string(item["source_item_id"]),
                          "source_document_id": ids.key_string(doc["source_document_id"])})
        records.append(record)
    write_json(out / ITEM_TABLE_NAME, {"benchmark": benchmark, "items": table})
    write_json(out / PARTS_RECORD_NAME, {"benchmark": benchmark,
                                         "input_format": INPUT_FORMAT_VERSION,
                                         "documents": records})
    return {"benchmark": benchmark, "documents": len(records), "items": len(table),
            "cut_documents": sum(1 for r in records if r["cut"]["cut"])}
