"""What changed between two versions of a document, and references that lead nowhere. No model.

A multi-round run computed findings per round and said nothing about the versions themselves:
its change records are the two-version review's, and those cover label-line figures only, so a
changed sentence or table cell had no record anywhere. This module reads two versions with the
project's own readers (pairing_map.split_units, passage_pairs.document_passages, the
paired_review.prior_* functions) and records, per unit:

- sentences added, removed and changed, each citing the version or versions that hold it. A
  sentence that stands in both versions, wherever it stands, is no change. Two leftover sentences
  are one changed sentence when their words are alike (`min_sentence_similarity`), and a tie is
  refused: both are then reported as they are, removed and added;
- labelled text values added, removed and changed;
- table cells and rows, compared by the row's first cell and the column's header;
- labelled figures, from the paired_review functions the two-version review uses.

It also checks each document's numbered references structurally. Every pattern is the operator's,
in `numbered_references` of config/relation_patterns.json, and none is here. A number the document
lacks fits no relation of the Finding record, so it is a computed note in this file and never a
finding (adding a relation is governed).

Nothing here interprets a change: it says what differs, never whether it matters or who gained.
`render` is the one renderer. `write` puts the record in audit/version_changes.json and one
`version_changes.md` in each later version's deliverables folder.
"""
import difflib
import json
from pathlib import Path
import re

import paired_review
import pairing_map
import passage_pairs
import reference_tables
from relation_extract import DEFAULT_PATTERNS_PATH
from reviewed_document import _escape
from run_context import DELIVERABLE_FILENAMES

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "version_changes.json"
RECORD_NAME = "version_changes.json"
DELIVERABLE_KEY = "version_changes"
COMPUTED_MARK = "Computed in code from the two versions. No model read them or wrote any of this."
NOTE_MARK = "A computed note, not a finding: no relation of the Finding record states this."
UNCHANGED = "unchanged_from_prior"
_TIE = 1e-9


def load_config(path=CONFIG_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _slug(unit_id):
    return str(unit_id).split("-", 1)[1] if "-" in str(unit_id) else ""


def _units(document):
    return pairing_map.split_units(document.get("text", ""), document_id=document.get("id", ""))


def _is_label_line(text):
    return bool(pairing_map._LABEL_LINE.match(text))


def _sentences(units):
    return [p for p in passage_pairs.document_passages(units) if not _is_label_line(p["text"])]


def _cite(document, passage):
    return {"document_id": document.get("id"), "unit_id": passage["unit_id"], "text": passage["text"]}


def _similar(a, b):
    return difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False).ratio()


def _paired(removed, added, threshold):
    """[(earlier index, later index)]: the most alike first; a tie is refused, so neither side
    of it is paired. Python does not choose between two equally likely partners."""
    scored = sorted(((_similar(a["text"], b["text"]), i, j)
                     for i, a in enumerate(removed) for j, b in enumerate(added)), key=lambda s: (-s[0], s[1], s[2]))
    scored = [s for s in scored if s[0] >= threshold]
    pairs, used_a, used_b, refused_a, refused_b = [], set(), set(), set(), set()
    for score, i, j in scored:
        if i in used_a | refused_a or j in used_b | refused_b:
            continue
        rivals = [s for s in scored if abs(s[0] - score) < _TIE and (s[1], s[2]) != (i, j)
                  and (s[1] == i or s[2] == j) and s[1] not in used_a and s[2] not in used_b]
        if rivals:
            refused_a.add(i)
            refused_b.add(j)
            continue
        pairs.append((i, j))
        used_a.add(i)
        used_b.add(j)
    return pairs


def sentence_changes(before, after, config):
    """[{change, unit_id, before?, after?}] between two documents."""
    old, new = _sentences(_units(before)), _sentences(_units(after))
    standing = {}
    for p in new:
        standing[p["text"]] = standing.get(p["text"], 0) + 1
    removed = []
    for p in old:
        if standing.get(p["text"], 0) > 0:
            standing[p["text"]] -= 1
        else:
            removed.append(p)
    held = {}
    for p in old:
        held[p["text"]] = held.get(p["text"], 0) + 1
    added = []
    for p in new:
        if held.get(p["text"], 0) > 0:
            held[p["text"]] -= 1
        else:
            added.append(p)
    pairs = _paired(removed, added, config["min_sentence_similarity"])
    out = [{"change": "changed", "unit_id": added[j]["unit_id"],
            "before": _cite(before, removed[i]), "after": _cite(after, added[j])} for i, j in pairs]
    gone, come = {i for i, _ in pairs}, {j for _, j in pairs}
    out += [{"change": "removed", "unit_id": p["unit_id"], "before": _cite(before, p)}
            for i, p in enumerate(removed) if i not in gone]
    out += [{"change": "added", "unit_id": p["unit_id"], "after": _cite(after, p)}
            for j, p in enumerate(added) if j not in come]
    return out


def _labels(text):
    """{normalised label: (label as written, value as written)}, the last statement of each."""
    out = {}
    for line in str(text or "").splitlines():
        hit = pairing_map._LABEL_LINE.match(line)
        if hit:
            norm = pairing_map._norm_label(hit.group(1))
            if norm:
                out[norm] = (hit.group(1).strip(), hit.group(2).strip())
    return out


def _tables(text):
    """[(header cells, body rows)] of a unit's tables, as written."""
    out = []
    for block in pairing_map._table_blocks(text or ""):
        if len(block) < 2 or not pairing_map._TABLE_SEP.match(block[1]):
            continue
        cells = [[c.strip() for c in line.strip().strip("|").split("|")] for line in block]
        out.append((cells[0], cells[2:]))
    return out


def _table_changes(before_unit, after_unit):
    """Cells and rows of the unit's tables, table by table in order, row by its first cell."""
    out, refused = [], []
    for (head_a, rows_a), (head_b, rows_b) in zip(_tables(before_unit["text"]), _tables(after_unit["text"])):
        keys_a, keys_b = [r[0] for r in rows_a], [r[0] for r in rows_b]
        if len(set(keys_a)) != len(keys_a) or len(set(keys_b)) != len(keys_b) or head_a != head_b:
            refused.append({"unit_id": after_unit["unit_id"],
                            "reason": "a repeated first cell or a changed header: the rows are not compared"})
            continue
        old, new = dict(zip(keys_a, rows_a)), dict(zip(keys_b, rows_b))
        for key in keys_a:
            if key not in new:
                out.append({"change": "row_removed", "unit_id": after_unit["unit_id"], "row": key,
                            "before": " | ".join(old[key])})
                continue
            for column, a, b in zip(head_a, old[key], new[key]):
                if a != b:
                    out.append({"change": "cell_changed", "unit_id": after_unit["unit_id"], "row": key,
                                "column": column, "before": a, "after": b})
        out += [{"change": "row_added", "unit_id": after_unit["unit_id"], "row": key,
                 "after": " | ".join(new[key])} for key in keys_b if key not in old]
    return out, refused


def _text_field_changes(before_unit, after_unit, figures):
    """Label lines with a text value. A label holding a figure on both sides is `figures`'s."""
    old, new = _labels(before_unit["text"]), _labels(after_unit["text"])
    out = []
    for norm in sorted(set(old) | set(new)):
        if norm in figures:
            continue
        a, b = old.get(norm), new.get(norm)
        if a and b and a[1] != b[1]:
            out.append({"change": "value_changed", "unit_id": after_unit["unit_id"], "label": b[0],
                        "before": a[1], "after": b[1]})
        elif a and not b:
            out.append({"change": "label_removed", "unit_id": after_unit["unit_id"], "label": a[0], "before": a[1]})
        elif b and not a:
            out.append({"change": "label_added", "unit_id": after_unit["unit_id"], "label": b[0], "after": b[1]})
    return out


def _figure_changes(before, after):
    """The two-version review's comparison of labelled figures, its unchanged records left out.
    Citations are the earlier document's paragraph, since a case's reference index holds its
    declared sources only. Returns (records, refusals, labels compared)."""
    text_a, text_b = before.get("text", ""), after.get("text", "")
    known = set(reference_tables.document_unit_tokens(text_a)) | set(reference_tables.document_unit_tokens(text_b))
    index = paired_review.prior_index(text_a, lambda i: "%s#%d" % (before.get("id"), i), known_units=known)
    units = _units(after)
    present = set()
    for unit in units:
        present |= pairing_map.unit_fields(unit.get("text", ""))
        present |= paired_review.table_row_labels(unit.get("text", ""), known)
    records, refusals, compared = [], [], set()
    for unit in units:
        scalars, _, _ = paired_review.extract_fields(unit.get("text", ""), known_units=known)
        slug = _slug(unit["unit_id"])
        hits, refused = paired_review.prior_lookup(index, scalars, slug)
        checks, refused2 = paired_review.prior_checks(scalars, hits, {})
        absent, refused3 = paired_review.absent_checks(index, present, slug, scalars=scalars, hits=hits)
        compared |= set(hits)
        for check in checks + absent:
            compared.add(tuple(check["stated_field"].split()))
            if check["relation"] != UNCHANGED:
                records.append({"relation": check["relation"], "unit_id": unit["unit_id"],
                                "label": check["stated_field"], "now": check.get("computed"),
                                "earlier": check.get("stated"), "measure": check.get("stated_unit", ""),
                                "earlier_cited": check.get("ref_id", "")})
        for row in refused + refused2 + refused3:
            label = tuple(str(row.get("label", "")).split())
            compared.add(label)
            # A date or an identifier holds a number with no measure: nothing to compare, and
            # its text change, if any, is a field change.
            if label in scalars and not scalars[label][1]:
                compared.discard(label)
                continue
            refusals.append({"unit_id": unit["unit_id"], "label": row.get("label", ""),
                             "reason_kind": row.get("reason_kind", ""), "reason": row.get("reason", "")})
    return records, refusals, compared


def document_changes(before, after, config):
    """Everything that differs between two versions of one document."""
    units_a = {_slug(u["unit_id"]): u for u in _units(before)}
    units_b = _units(after)
    figures, refusals, compared = _figure_changes(before, after)
    fields, cells, refused = [], [], []
    for unit in units_b:
        earlier = units_a.get(_slug(unit["unit_id"]))
        if earlier is None:
            continue
        fields += _text_field_changes(earlier, unit, compared)
        made, not_compared = _table_changes(earlier, unit)
        cells += made
        refused += not_compared
    here = {_slug(u["unit_id"]) for u in units_b}
    return {"before": before.get("id"), "after": after.get("id"),
            "sentences": sentence_changes(before, after, config), "fields": fields, "cells": cells,
            "cells_not_compared": refused, "figures": figures, "figure_refusals": refusals,
            "units_added": [u["unit_id"] for u in units_b if _slug(u["unit_id"]) not in units_a],
            "units_removed": [u["unit_id"] for s, u in units_a.items() if s not in here]}


def pair_documents(earlier, later, config):
    """[(earlier document, later document)]: versions of one document, told apart by the headings
    they share, one earlier for each later. A tie, or too few shared headings, pairs nothing:
    a case manifest does not say which documents are versions of each other."""
    def slugs(document):
        return {_slug(u["unit_id"]) for u in _units(document)}
    pairs, taken = [], set()
    for doc in later:
        mine = slugs(doc)
        scored = sorted(((len(mine & slugs(e)) / max(len(mine | slugs(e)), 1), e.get("id")) for e in earlier
                         if e.get("id") not in taken), reverse=True)
        if not scored or scored[0][0] < config["min_shared_headings"]:
            continue
        if len(scored) > 1 and abs(scored[0][0] - scored[1][0]) < _TIE:
            continue
        taken.add(scored[0][1])
        pairs.append((next(e for e in earlier if e.get("id") == scored[0][1]), doc))
    return pairs


# ---- numbered references -----------------------------------------------------------------------

def load_reference_patterns(path=DEFAULT_PATTERNS_PATH):
    """{targets, paragraphs, references}, compiled, or None when the operator declares none."""
    spec = json.loads(Path(path).read_text(encoding="utf-8")).get("numbered_references")
    if not spec or not spec.get("references") or not spec.get("targets"):
        return None
    flags = re.IGNORECASE | re.MULTILINE

    def compiled(rows):
        return [dict(row, compiled=re.compile(row["regex"], flags)) for row in rows]
    paragraphs = spec.get("paragraphs") or {}
    return {"targets": compiled(spec["targets"]), "references": compiled(spec["references"]),
            "paragraph": re.compile(paragraphs["regex"], flags) if paragraphs.get("regex") else None,
            "paragraph_group": paragraphs.get("number_group", 1),
            "deleted": re.compile(paragraphs["deleted_regex"], flags) if paragraphs.get("deleted_regex") else None}


def _heading(unit):
    return (unit.get("text") or "").split("\n", 1)[0].lstrip("#").strip()


def _declared_targets(units, patterns):
    """{(kind, number): {number: deleted?}}: the numbered units a document has, with their
    numbered paragraphs. The number is kept as written; the kind is folded to one case."""
    out = {}
    for unit in units:
        for target in patterns["targets"]:
            hit = target["compiled"].search(_heading(unit))
            if not hit:
                continue
            paragraphs = {}
            if patterns["paragraph"] is not None:
                for line in unit.get("text", "").splitlines():
                    found = patterns["paragraph"].match(line.strip())
                    if found:
                        deleted = patterns["deleted"] is not None and bool(patterns["deleted"].match(line.strip()))
                        paragraphs[found.group(patterns["paragraph_group"])] = deleted
            out[(hit.group(target["kind_group"]).lower(), hit.group(target["number_group"]))] = paragraphs
            break
    return out


def broken_references(document, patterns):
    """[{unit_id, reference, reason}]: references to a numbered unit or paragraph the document
    does not have. A document that declares no numbered unit is not checked."""
    if patterns is None:
        return []
    units = _units(document)
    declared = _declared_targets(units, patterns)
    if not declared:
        return []
    out = []
    for unit in units:
        body = (unit.get("text") or "").split("\n", 1)[-1]
        taken = []
        for pattern in patterns["references"]:
            for hit in pattern["compiled"].finditer(body):
                if any(a <= hit.start() and hit.end() <= b for a, b in taken):
                    continue
                taken.append(hit.span())
                key = (hit.group(pattern["kind_group"]).lower(), hit.group(pattern["number_group"]))
                group = pattern.get("paragraph_group")
                reason = None
                if key not in declared:
                    reason = "no_such_unit"
                elif group and hit.group(group) not in declared[key]:
                    reason = "no_such_paragraph"
                elif group and declared[key][hit.group(group)]:
                    reason = "paragraph_deleted"
                if reason:
                    out.append({"unit_id": unit["unit_id"], "reference": hit.group(0), "reason": reason,
                                "pattern": pattern["name"], "written_by": "python", "provenance": "computed"})
    return out


# ---- the case --------------------------------------------------------------------------------

def case_changes(manifest, documents, config=None, patterns=None):
    """The record: each consecutive pair of rounds, and every document's references."""
    config = config or load_config()
    patterns = load_reference_patterns() if patterns is None else patterns
    docs = {d.get("id"): d for d in documents or [] if isinstance(d, dict)}
    rounds = sorted(manifest.get("rounds") or [], key=lambda r: r["sequence"])
    record = {"schema_version": 1, "case_id": manifest.get("case_id"), "written_by": "python",
              "provenance": "computed", "comparisons": [], "references": []}
    for earlier, later in zip(rounds, rounds[1:]):
        held_a = [docs[i] for i in earlier.get("document_ids") or [] if i in docs]
        held_b = [docs[i] for i in later.get("document_ids") or [] if i in docs]
        pairs = pair_documents(held_a, held_b, config)
        paired = {after.get("id") for _, after in pairs}
        for before, after in pairs:
            record["comparisons"].append(dict(document_changes(before, after, config),
                                              round_before=earlier["round_id"], round_after=later["round_id"]))
        record.setdefault("not_compared", []).extend(
            {"round_id": later["round_id"], "document_id": d.get("id")} for d in held_b if d.get("id") not in paired)
    for rnd in rounds:
        for doc_id in rnd.get("document_ids") or []:
            if doc_id in docs:
                record["references"] += [dict(n, round_id=rnd["round_id"], document_id=doc_id)
                                         for n in broken_references(docs[doc_id], patterns)]
    return record


def _line(text):
    return _escape(str(text).replace("\n", " "))


def _figure_text(value, measure):
    return "no figure" if value is None else "%g %s" % (value, measure)


def render(comparison, references):
    """The one renderer: one comparison and the later document's references, as Markdown."""
    after, before = comparison["after"], comparison["before"]
    rows = {}

    def put(unit_id, line):
        rows.setdefault(unit_id, []).append(line)

    for s in comparison["sentences"]:
        if s["change"] == "changed":
            put(s["unit_id"], "- Sentence changed. Was (%s, %s): %s\n  Now (%s, %s): %s" % (
                s["before"]["document_id"], s["before"]["unit_id"], _line(s["before"]["text"]),
                s["after"]["document_id"], s["after"]["unit_id"], _line(s["after"]["text"])))
        elif s["change"] == "removed":
            put(s["unit_id"], "- Sentence removed (%s, %s): %s" % (
                s["before"]["document_id"], s["before"]["unit_id"], _line(s["before"]["text"])))
        else:
            put(s["unit_id"], "- Sentence added (%s, %s): %s" % (
                s["after"]["document_id"], s["after"]["unit_id"], _line(s["after"]["text"])))
    for f in comparison["fields"]:
        put(f["unit_id"], "- %s: %s" % (_line(f["label"]), {
            "value_changed": "was %s, now %s" % (_line(f.get("before")), _line(f.get("after"))),
            "label_removed": "no longer stated (was %s)" % _line(f.get("before")),
            "label_added": "newly stated (%s)" % _line(f.get("after"))}[f["change"]]))
    for c in comparison["cells"]:
        put(c["unit_id"], "- Table row %s: %s" % (_line(c["row"]), {
            "cell_changed": "%s was %s, now %s" % (_line(c.get("column")), _line(c.get("before")), _line(c.get("after"))),
            "row_removed": "row removed (was %s)" % _line(c.get("before")),
            "row_added": "row added (%s)" % _line(c.get("after"))}[c["change"]]))
    for r in comparison["figures"]:
        put(r["unit_id"], "- Figure, %s: %s (%s), was %s, now %s" % (
            _line(r["label"]), r["relation"], _line(r["earlier_cited"]),
            _figure_text(r["earlier"], r["measure"]), _figure_text(r["now"], r["measure"])))
    for r in comparison["figure_refusals"]:
        put(r["unit_id"], "- Figure not compared, %s: %s" % (_line(r["label"]), _line(r["reason"])))
    for c in comparison["cells_not_compared"]:
        put(c["unit_id"], "- Table not compared: %s" % _line(c["reason"]))
    out = ["# Changes from %s to %s" % (before, after), COMPUTED_MARK,
           "Rounds %s to %s. Units with a change: %d. Units added: %d. Units removed: %d." % (
               comparison.get("round_before"), comparison.get("round_after"), len(rows),
               len(comparison["units_added"]), len(comparison["units_removed"]))]
    for unit_id in comparison["units_added"]:
        out.append("Unit added: %s" % unit_id)
    for unit_id in comparison["units_removed"]:
        out.append("Unit removed: %s" % unit_id)
    for unit_id in sorted(rows):
        out += ["## %s" % unit_id, "\n".join(rows[unit_id])]
    mine = [n for n in references if n.get("document_id") == after]
    out.append("## References that lead nowhere")
    out.append(NOTE_MARK)
    out.append("\n".join("- %s: %s (%s)" % (n["unit_id"], _line(n["reference"]), n["reason"]) for n in mine)
               if mine else "None found by the declared patterns.")
    return "\n\n".join(out) + "\n"


def write(ctx, record):
    """audit/version_changes.json and one deliverable per later version. Returns their paths."""
    audit = ctx.audit_dir() / RECORD_NAME
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written = []
    for comparison in record["comparisons"]:
        folder = ctx.doc_deliverables_dir(comparison["after"])
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / DELIVERABLE_FILENAMES[DELIVERABLE_KEY]
        path.write_text(render(comparison, record["references"]), encoding="utf-8", newline="\n")
        written.append(path)
    return written
