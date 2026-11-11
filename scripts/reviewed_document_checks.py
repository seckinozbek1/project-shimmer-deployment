"""Gate check 320: reviewed_document.md is the reviewed document (open item 19, part 2).

The file used to be each agent's raw reply (now the agent record, agent_record.md). It is
now the document under review, in its own words and order, with each finding at the unit
it concerns, and a header saying what was asked, how many findings of each kind there are
and what was not checked. The first group of proofs runs the REAL phase-6 writer on the mocked runs of
scripts/honest_output_checks.py (the real paired review, the real synthesis, no model,
provider, network or GPU) and reads the files it wrote:

- the document's own text is in the file, whole and in order;
- each amendment and each model finding is shown under its own unit, in English and tr,
  and each of Python's other findings, each answer Python refused and each rule left
  unchecked in English;
- every model-written finding carries the mark on the line that states it, and no line
  that states a Python finding does (HONEST-OUTPUT-A);
- the header's counts equal review_data.json (amendments, model findings), the document
  summary (Python's findings) and the pairing map (refusals, rules left unchecked);
- the tr file carries no English template text;
- the redaction scrub reaches the file (it holds the document's whole text).

The renderer is also called directly on fixtures of its own (the review fixes of
D-S26 item 3, and PATCH_2 review round 3): a model's sentence is never cut, so a span
across the old cut is scrubbed, and neither the operative nor the grounding summary
cuts one either; a document line written like a finding block (a quoting `>` at a line
start or after a list marker, bold markers, raw HTML, a backslash before any of them)
is not shown as one, and neither is a model's or an agent's own text; a wide review,
whose pairing record lacks the paired review's lists, and a review with no pairing
record state their refusal and unchecked counts as not recorded, and a paired review
states them; amendments are counted apart by who built them; an amendment joins its
finding when one carries a figure as an int and the other as a float or a numeric
string; a table split by row shows each row's finding under its row; a unit whose text
cannot be located is named in a section that says so; a unit is never placed inside a
longer line or past the next unit; the document's code blocks and code spans are shown
as written (an indented line in a list item is not code, a freed backtick cannot open a
span, a span across a pipe is not taken); a model's note and a model finding's reader
line are escaped; the grounding summary shows each passage whole from its document, or
no text where only a clipped excerpt is on record; lines split only where CommonMark
splits them; and main gives phase 6 the context texts keyed as the index keys them.

The redaction runs only when the sensitivity layer is active (D-214 rebuilt its scrub side
after the fifth review of D-212). Phase 9 then renders this file again from scrubbed
inputs (`reviewed_document.write_from_scrubbed`), the way the master's deliverables are, so a
span is gone before the renderer escapes anything or sets a finding into the text. Proven through the redaction's own steps in their order (`_through_redaction`), through the
real stage (`_stage`, `run_redaction_phase`, the redactor authored, no model) and once with
the master's own renders (`observe_rerender`), or on the scrub's functions directly: a
span the renderer would escape or split never reaches it; the run's language and every count
are kept; spans are matched in one pass; a span holding a backslash is removed from a code
block; a unit id carrying a span is derived again, whatever the heading's form; a figure goes
in the record's own form too; a line break in a record's JSON hides nothing; the matcher
reads a span with or without the configured Arabic article and vowel marks, in either
Unicode form, across invisible characters; a model cannot choose the replacement; a span cannot change an
enumerated field; every span in the run reaches every document that reaches the scrub; a
held document's files are scrubbed with what is known, and what is unknown is reported; a
context passage's authorised shapes are found; only a document's own spans must be located;
and a document with none reports NONE, or that it held only other documents' spans. The
survivor grep stays as the net: a span split or escaped in a file not rendered from scrubbed
inputs BLOCKS.

Each mechanism is proven by neutralise, fail, restore, pass (effect_proof), but for two plain
tests (the render's raise, the board's place) and some asserted on the real functions without
a neutralisation of their own: the stage's guards in `check_stage_guards` (an unreadable
master, a held survivor, a render that raises, a changed unit count), a number as a span,
and the tr rows of the refusal reasons.

    py -3.12 -X utf8 scripts/reviewed_document_checks.py
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import finding_record
import honest_output_checks as hoc
import localization as loc
import paired_review as pr
import pairing_map
import reviewed_document as rd
import run_context

# Held here, so a neutralisation that changes the module's copy cannot change the test.
MARK = finding_record.MODEL_FINDING_MARK
PYTHON_MARKS = (finding_record.COMPUTED_FINDING_MARK, finding_record.CHECKED_ABSENCE_MARK)
REVIEWED = run_context.DELIVERABLE_FILENAMES["reviewed_document"]
RECORD = run_context.DELIVERABLE_FILENAMES["per_agent_deliverable"]
SUMMARY = run_context.DELIVERABLE_FILENAMES["operative_summary"]
MASTER = run_context.DELIVERABLE_FILENAMES["amendments_json"]
# Every English template the file writes; none of them may reach a tr reader.
TEMPLATES = [v for k, v in vars(rd).items() if k.isupper() and isinstance(v, str)] + \
    list(rd.NO_AMENDMENT_REASONS.values()) + list(rd.REFUSAL_REASONS.values())


def _squash(text):
    return "".join(str(text or "").split())


def _flat(text):
    return " ".join(str(text or "").split())


def _unescape(text):
    """The document's own text as written: the renderer escapes every backslash, `>`
    and `<`, and the bold markers, so none of it can look like a finding block."""
    return re.sub(r"\\([!-/:-@\[-`{-~])", r"\1", str(text or ""))


# A character Markdown reads as markup: one not preceded by an odd run of backslashes.
_RAW = r"(?<!\\)(?:\\\\)*"
_LIST_MARKER = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])\s+")


def _renders_quoted(line):
    """True when the line opens a quotation, at its start or after list markers."""
    rest = line
    while True:
        stripped = _LIST_MARKER.sub("", rest, count=1)
        if stripped == rest:
            break
        rest = stripped
    return rest.lstrip(" ").startswith(">") and len(rest) - len(rest.lstrip(" ")) <= 3


def _count(text, template, **fixed):
    """The number a header line states, read back through its own template."""
    pattern = re.escape(template.format(n="\0", **fixed)).replace("\x00", r"(\d+)")
    match = re.search("^" + pattern + "$", text, re.M)
    return int(match[1]) if match else None


def _layout(run, language):
    """What one reviewed document shows, read off the files the run wrote."""
    doc = run["doc"]
    doc_dir = run["run_dir"] / "deliverables" / doc["id"]
    text = hoc._read(doc_dir / REVIEWED)
    master = json.loads(hoc._read(doc_dir / MASTER))
    pairing = json.loads(hoc._read(run["run_dir"] / "audit" / "pairing_map.json")).get(doc["id"]) or {}
    t = lambda s, **v: loc.text(s, language, **v)
    head, _, body = text.partition("\n---\n\n" + t(rd.DOCUMENT_HEADING) + "\n\n")
    body, _, unplaced = body.partition("\n---\n\n" + t(rd.UNPLACED_HEADING) + "\n")
    body, _, unlocated = body.partition("\n---\n\n" + t(rd.UNLOCATED_HEADING) + "\n")
    units = sorted(pr.unit_texts_for(doc["text"], doc["id"]).values(), key=lambda u: u["index"])
    starts, cursor = [], 0
    for u in units:
        at = body.find(u["text"], cursor)
        starts.append(at)
        cursor = at + len(u["text"]) if at >= 0 else cursor
    segment = {}
    for i, u in enumerate(units):
        if starts[i] >= 0:
            end = next((s for s in starts[i + 1:] if s >= 0), len(body))
            segment[u["unit_id"]] = body[starts[i] + len(u["text"]):end]
    lines = text.splitlines()
    model = master.get("model_findings_not_promoted") or []
    amendments = master.get("amendments") or []
    model_lines = {f.get("unit_id"): finding_record.reader_line(f, output_language=language) for f in model}
    mark, pmarks = t(MARK), [t(m) for m in PYTHON_MARKS]
    refused = [e for k in ("absence_refused", "uncomputable_refused") for e in pairing.get(k) or []]
    # Read here from the pairing map's own lists, not through the renderer's reader.
    unchecked = (list(pairing.get("not_judged") or []) + list(pairing.get("suspended") or [])
                 + [c for c in pairing.get("judging_calls") or [] if c.get("outcome") == "reply_failed"
                    and c.get("plan_kind") in (pr.JUDGED_ABSENCE_PLAN, pr.UNCOMPUTABLE_PLAN)])
    names = {"findings": run_context.DELIVERABLE_FILENAMES["amendments_md"],
             "docx": run_context.DELIVERABLE_FILENAMES["amendments_docx"]}
    summary = hoc._read(doc_dir / SUMMARY)

    def at_unit(unit_id, needle, label):
        """The needle is stated under its own unit, on a line opened by the label."""
        return any(ln.startswith("> **" + label) and needle in ln
                   for ln in (segment.get(unit_id) or "").splitlines())

    out = {
        # the document's own text, whole and in order, apart from the quoted blocks
        "text_in_order": _squash(_unescape("\n".join(ln for ln in body.splitlines() if not ln.startswith(">"))))
                         == _squash(doc["text"]),
        "units_in_order": all(s >= 0 for s in starts) and starts == sorted(starts),
        "unplaced_section": bool(unplaced.strip()) or bool(unlocated.strip()),
        # each item at its own unit, opened by its own label
        "amendments_at_unit": sorted(
            (a.get("finding_unit_id"), any(at_unit(a.get("finding_unit_id"), loc.message(_flat(a["comment"]), language), m)
                                           for m in pmarks))
            for a in amendments),
        "model_at_unit": sorted((f.get("unit_id"), at_unit(f.get("unit_id"), model_lines[f.get("unit_id")], mark))
                                for f in model),
        "refused_at_unit": sorted((e.get("unit_id"), e.get("rule_id"),
                                   sum(ln.startswith("> **" + t(rd.REFUSED_LABEL)) and e.get("rule_id") in ln
                                       for ln in (segment.get(e.get("unit_id")) or "").splitlines()))
                                  for e in refused),
        "unchecked_at_unit": sorted((e.get("unit_id"), e.get("rule_id"),
                                     at_unit(e.get("unit_id"), e.get("rule_id"), t(rd.NOT_CHECKED_LABEL)))
                                    for e in unchecked if e.get("unit_id")),
        "python_without_amendment": sorted(uid for uid, seg in segment.items()
                                           for ln in seg.splitlines() if ln.startswith(t(rd.NO_AMENDMENT), 2)),
        # the mark: on every line that states a model finding, on no line that states Python's
        "model_mark_lines": sum(mark in ln for ln in lines),
        "model_lines_unmarked": sum(1 for ln in lines for s in model_lines.values() if s in ln and mark not in ln),
        "python_lines_marked": sum(1 for ln in lines if mark in ln and any(p in ln for p in pmarks)),
        # the header's counts against the master, the document summary and the pairing map
        "counts": {"amendments": [(_count(text, t(rd.COUNT_AMENDMENTS), **names) or 0)
                                  + (_count(text, t(rd.COUNT_AMENDMENTS_OTHER), **names) or 0), len(amendments),
                                  sum(ln.startswith("> " + t(rd.SUGGESTED)) for ln in lines)],
                   "amendments_computed": [_count(text, t(rd.COUNT_AMENDMENTS), **names),
                                           sum(a.get("derived_from") == "computed_finding" for a in amendments)],
                   "model": [_count(text, t(rd.COUNT_MODEL)), len(model)],
                   "refused": [_count(text, t(rd.COUNT_REFUSED)), len(refused)],
                   "not_checked": [_count(text, t(rd.COUNT_NOT_CHECKED)), len(unchecked)],
                   "figures": _count(text, t(rd.COUNT_FIGURES)), "checked": _count(text, t(rd.COUNT_CHECKED))},
        "summary_counts": [_count(summary, t("- findings computed by Python from the document's figures: ") + "{n}"),
                           _count(summary, t("- required fields Python checked in code and found absent: ") + "{n}")],
        "header_names_record": RECORD in head and "```json" not in text,
        "dashes": text.count(chr(0x2014)) + text.count(chr(0x2013)),
    }
    if language == "tr":
        out["english_left"] = sorted({piece for s in TEMPLATES for piece in re.split(r"\{\w+\}", s)
                                      if len(piece.strip()) > 12 and piece.strip() in text})
    return out


def observe():
    """Three mocked runs (the S2a run in English and tr, and the judged-absence run in
    English: refusals, a failed judged-absence call, a second finding on one rule)."""
    with tempfile.TemporaryDirectory(prefix="shimmer_reviewed_document_") as td:
        en = hoc.mocked_run(Path(td) / "en")
        tr = hoc.mocked_run(Path(td) / "tr", language="tr")
        judged = hoc.mocked_run(Path(td) / "judged", style_guardian=False, text=hoc.TWO_TOTALS_TEXT,
                                rules=hoc.RULES + [hoc.JUDGED_RULE], absence_reply=hoc.judged_absence_reply,
                                plan_calls=hoc.one_call_for_both_beta_totals)
        return {"en": _layout(en, "en"), "tr": _layout(tr, "tr"), "judged": _layout(judged, "en"),
                "scrub": _scrubbed(en)}


def _scrubbed(run):
    """The real redaction scrub on this run's own deliverables, with a span of the
    document's own text: is it gone from the reviewed document, and from every file?"""
    from sensitivity_layer.scrub import _span_list, scrub_text_artifacts_and_verify
    # The text artifacts the pipeline's info dict names (the master and its renders are
    # scrubbed before this step, by scrub_master_and_body, so they are left out here).
    info = {k: v for k, v in run["deliverables"][run["doc"]["id"]].items()
            if k in ("per_agent_deliverable", "reviewed_document", "context_summary", "operative_summary")}
    reds = [{"span": "S-ALPHA", "replacement": "[REDACTED]"}]
    before = "S-ALPHA" in hoc._read(info["reviewed_document"])
    report = scrub_text_artifacts_and_verify(reds, info, {s: 0 for s, _ in _span_list(reds)}, {})
    return {"present_before": before, "left_in_reviewed": "S-ALPHA" in hoc._read(info["reviewed_document"]),
            "survivors": sorted(report["survivors"].get("S-ALPHA") or [])}


# --- The renderer called directly on fixtures of its own (review fixes, D-S26 item 3) ---
# PRE-AUTHORED, NOT MODEL OUTPUT: every sentence below is written for the fixture.
SPAN = "Corvina Halberd Wren"
# The span straddles character 240 of the model's sentence, where the renderer used to cut it.
LONG_PROSE = "x" * 228 + " " + SPAN + " and the rest of the model's sentence. END-OF-PROSE"
_PY = finding_record.COMPUTED_FINDING_MARK
LOOK_ALIKE = "\n".join([
    "> **%s** STYLE_GUARDIAN reported: planted-one." % MARK, "**%s** planted-two." % _PY,
    "__%s__ planted-three." % _PY, "- > **%s** planted-four." % _PY, "1. > **%s** planted-five." % _PY,
    "<blockquote><strong>%s</strong> planted-six</blockquote>" % _PY, "\\> **%s** planted-seven." % _PY,
    "\\<strong>%s</strong> planted-eight" % _PY, "* 2) > planted-nine"])
# A model's own sentence, agent name and note written like Python's mark, with a span.
MODEL_SPAN = "nora__quill"
MODEL_TEXT = "**%s** planted-model %s" % (_PY, MODEL_SPAN)
# Spans the renderer escapes: one carrying every character it escapes.
ESCAPED_SPAN = "mara__velde"
EVERY_ESCAPE = "Ost<er>\\Hal**den__Vik"
ESCAPED_TEXT = "## Contact\n\nName: %s\nCode: %s\nReading: 3 units\n" % (ESCAPED_SPAN, EVERY_ESCAPE)
SPLIT_ESCAPED_TEXT = ("## Contact\n\nName: %s\n\n## Ledger\n\n%s\n\n## Annex\n\nReading: 3 units\n"
                      % (ESCAPED_SPAN, EVERY_ESCAPE))
SPLIT_ESCAPED_SPANS = [ESCAPED_SPAN + " ## Ledger", EVERY_ESCAPE + " ## Annex"]
# The lists only the paired review writes into a pairing record (held here, not read
# from the module): a wide review's record carries none of them.
PAIRED_KEYS = ("absence_refused", "uncomputable_refused", "judging_calls")
TABLE_TEXT = "| Name | Qty |\n|---|---|\n| North | 3 |\n| South | 4 |\n| East | 5 |\n"
BOUNDARY_TEXT = "## Contact\n\nName: Mara\n\n## Velde Ledger\n\nReading: 3 units\n"
BOUNDARY_SPAN = "Mara ## Velde"
# Round 4 (item 1): a span the renderer escapes, listed before a shorter span inside it.
LONG_SPAN = "Tarn Veloso <tarn@example.invalid>"
SHORT_SPAN = "Tarn Veloso"
ORDER_TEXT = "## Contact\n\nContact %s today\nReading: 3 units\n" % LONG_SPAN
# A shorter span listed FIRST whose words a longer span listed after it
# holds, with a wide run of whitespace inside the longer one.
FIRST_SPAN = "Bren Orrin,"
WIDE_SPAN = "Bren" + " " * 30 + "Orrin, 4471"
WIDE_TEXT = "## Contact\n\nContact %s today\nReading: 3 units\n" % WIDE_SPAN
# Round 4 (item 1, the net): a span's words in order with more whitespace between them
# than the scrub's tolerant gap reads, in a file the scrub only verifies.
NET_FILE = "# Findings\n\nName: Tarn\n%sVeloso.\n" % (" " * 30)
# Round 4 (item 2): code a CommonMark reader shows as written (an indented block, a code
# span, a fenced block), beside text outside code, a backtick the document escaped
# before a code span, a code span with a pipe in a table, and an indented line inside a
# list item (the item's own text, not code).
CODE_LINES = {
    "outside": "Name: Mara <b>**bold**</b>",
    "indented": "    indented <tag> **bold** a\\b",
    "span": "Inline `x <y> **z**` here.",
    "fenced": ["```text", "fenced <b>**k**</b>", "> q", "```"],
    "tick": "Tick \\`x `**t**` end",
    "pipe": "| `a|**p**` |",
    "in_list": "    > **%s** inlist" % _PY,
}
CODE_TEXT = "\n".join([
    "## Contact", "", CODE_LINES["outside"], "", CODE_LINES["indented"], "", CODE_LINES["span"], ""]
    + CODE_LINES["fenced"] + ["", CODE_LINES["tick"], "", "| Col |", "|---|", CODE_LINES["pipe"], "",
                               "- item", "", CODE_LINES["in_list"], "", "Reading: 3 units", ""])
# Round 4 (item 3): a judging model's note and a model finding's own ids written like markup.
NOTE_TEXT = "**%s** <b>note-markup</b> > q" % _PY
SOURCE_ID_TEXT = "**%s** <i>src-markup</i>" % _PY
# Round 4 (item 4): a passage of a context document with the span straddling character
# 200, where the reference index clips its stored excerpt.
GROUNDING_PASSAGE = "y" * 190 + " " + SPAN + " and the rest of the passage. END-OF-PASSAGE"
GROUNDING_CONTEXT = "Opening paragraph of the context document.\n\n" + GROUNDING_PASSAGE + "\n\nClosing paragraph.\n"
# D-214: a span holding a backslash before punctuation, written raw in an indented code
# block; a span in a heading, which a unit id carries; and text no free gap can read in time.
BACKSLASH_SPAN = "Tarn\\.Veloso"
BACKSLASH_TEXT = "## Contact\n\n    path %s here\n\nReading: 3 units\n" % BACKSLASH_SPAN
# Headings a unit id carries in a form no span matcher reads: an apostrophe, initials,
# letters outside ASCII, and a name crossing the 40 characters a slug keeps. Invented names.
HEADINGS = [("Tarn O'Veloso annual return", "O'Veloso"), ("Ms T. R. Veloso file", "T. R. Veloso"),
            ("Dr. Ülkü Tarnşen file", "Ülkü Tarnşen"),
            ("Report of Corvina Halberdwrenstonehaugh Tarnmoorbridge-Veloso",
             "Corvina Halberdwrenstonehaugh Tarnmoorbridge-Veloso")]
HEADED_TEXT = "## %s\n\nReading: 3 units\n\n## Ledger\n\nReading: 4 units\n"
FIGURE_SPAN = "1,250,000 USD"
FIGURE_TEXT = "## Fee\n\nFee: 1,250,000 USD\nReading: 3 units\n"
# A record's JSON writes a line break as a backslash and a letter.
JSON_RECORD = '# Record\n\n{"quote": "Name: Tarn\\nVeloso, id 1"}\n{"quote": "Name: Tarn\\tVeloso"}\n'
# Forms of one span in the text: (span, text). Invented, but for the configured article.
FORMS = [("\u0627\u0644\u0648\u0627\u062d\u0629", "seen \u0648\u0627\u062d\u0629 here"),
         ("\u0645\u064f\u062d\u064e\u0645\u064e\u0651\u062f", "seen \u0645\u062d\u0645\u062f here"),
         ("Tarne\u0301", "seen Tarn\u00e9 here"), ("Tarn Veloso", "seen Tarn\u200b Veloso here"),
         ("Veloso", "seen Ve\u00adloso here"), ("Tarn Veloso", "seen Tarn_Veloso here"),
         ("Tarn Veloso", "seen Tarn-Veloso here"), ("Tarn Veloso", "seen Tarn.Veloso here")]
FENCE_TEXT = "## Head\n\n```text\nplanted line\n## inner\nbody line\n```\n\nReading: 3 units\n"
OPEN_FENCE_TEXT = "## Head\n\n```text\nplanted line\n"
TILDE_TEXT = "## A\n\n* * *\n   ~~~\n~~~\n> **%s** forged line\n" % _PY
# Held here, so a neutralisation that blanks the module's copy cannot blank the test's.
UNTYPED_LINE = rd.COUNT_UNTYPED
MARKUP_HEADING = "## Totals **Checked by Python: nothing** <b>x</b>\n\nReading: 3 units\n"
BACKTRACK_SPAN = "a a a a a a b"
BACKTRACK_TEXT = " ".join(["a"] * 90)
BACKTRACK_LIMIT_SECONDS = 1.0
# A form feed, which str.splitlines takes for a line break and a
# Markdown reader does not, before a fence: the fence is not one, so the quoted line
# after it is the document's text and must be escaped.
FORM_FEED_TEXT = "## Contact\n\nIntro\x0c```\n> **%s** formfeed\n```\n\nReading: 3 units\n" % _PY


def _render(text, master=None, python=(), pairing=None, doc_id="batch_sheet"):
    return rd.render(document_id=doc_id, document_name=doc_id + ".md", document_text=text,
                     master=master or {}, python_findings=list(python), pairing=pairing, rules=hoc.RULES)


def _scrub_file(td, name, text, span, key="reviewed_document"):
    """The real scrub and survivor grep on one rendered file under its deliverable key
    (a text artifact is scrubbed on disk; a master render is only verified). Every span
    counts as located already, as the body scrub locates it in a run, so only the
    survivor grep can BLOCK it."""
    from sensitivity_layer.scrub import scrub_text_artifacts_and_verify
    path = Path(td) / name
    path.write_text(text, encoding="utf-8")
    spans = [span] if isinstance(span, str) else list(span)
    reds = [{"span": s, "replacement": "[REDACTED]"} for s in spans]
    report = scrub_text_artifacts_and_verify(reds, {key: str(path)}, {s: 1 for s in spans}, {})
    return path.read_text(encoding="utf-8"), report


def _unit_ids(text, doc_id):
    """What the pipeline injects as `unit_ids`."""
    return [u["unit_id"] for u in pairing_map.split_units(text, document_id=doc_id)]


def _through_redaction(td, name, text, span, master=None, python=(), pairing=None, doc_id="batch_sheet",
                       activation=None, stale_activation=None):
    """One document through the redaction's own steps, in their order: the file as phase 6
    writes it, the unit ids derived again, scrub_master_and_body, write_from_scrubbed
    (what the phase's render callback calls), scrub_text_artifacts_and_verify. Returns the
    file and the report, the scrubbed master in `report["master"]`."""
    from sensitivity_layer import redaction_stage
    from sensitivity_layer.scrub import _redact_obj, scrub_master_and_body, scrub_text_artifacts_and_verify
    spans = [span] if isinstance(span, str) else list(span)
    own = [{"span": s, "replacement": "[REDACTED]"} for s in spans]
    reds = redaction_stage._neutral_unit_ids({"id": doc_id, "text": text}, own, _unit_ids) + own
    inputs = dict(document_id=doc_id, document_name=doc_id + ".md", document_text=text, master=master or {},
                  python_findings=list(python), pairing=pairing, rules=hoc.RULES, activation=stale_activation)
    path = Path(td) / name
    path.write_text(rd.render(**inputs), encoding="utf-8")
    info = {"reviewed_document": str(path), "reviewed_render_inputs": inputs}
    scrubbed, body, located, by_artifact = scrub_master_and_body(master or {}, reds, text, own=own)
    rd.write_from_scrubbed(info, scrubbed, body, lambda obj: _redact_obj(obj, reds)[0], activation=activation)
    report = scrub_text_artifacts_and_verify(reds, info, located, by_artifact)
    report["master"] = scrubbed
    return path.read_text(encoding="utf-8"), report


def _left(text, span):
    """Whether any word of the span is still in the text, as written or unescaped."""
    return any(w in t for t in (text, _unescape(text)) for w in re.split(r"\W+", span) if len(w) > 2)


def _grounding_refs(td, source):
    """The context document indexed as main() indexes it (the real index_document), its
    entries given whole passages from `source` ({document id: text}) as phase 6 does."""
    import reference_builder as rb
    index = rb.ReferenceIndex(project_root=Path(td), index_path=Path(td) / "refs.json")
    index.index_document(input_type="context", document_id="context_long", document_name="context_long.md",
                         text=GROUNDING_CONTEXT)
    refs = [e.as_dict() for e in index.entries]
    return rb.with_whole_passages(refs, source), refs


def _summaries(td):
    """The operative summary (stamped and unstamped) with a sentence and a rule whose span
    straddles character 240, and the grounding summary with a passage whose span
    straddles character 200 (where the index clips its stored excerpt), shown from the
    document's own text and, with no text given, from the stored excerpt alone; each
    scrubbed on disk."""
    import summary_generators as sg
    whole, stored = _grounding_refs(td, {"context_long": GROUNDING_CONTEXT})
    unrecovered, _ = _grounding_refs(td, {})
    python = dict(hoc.computed_findings()[0], written_by=finding_record.WRITTEN_BY_PYTHON, category="conv-h01",
                  explanation=LONG_PROSE, explanation_by=finding_record.WRITTEN_BY_MODEL)
    model = dict(hoc.model_finding(), written_by=finding_record.WRITTEN_BY_MODEL, category="conv-h01",
                 explanation=LONG_PROSE)
    rule = {"id": "CONV-001", "category": "conv-h01", "severity": "required", "rule": LONG_PROSE}
    texts = {
        "operative_stamped": sg.render_operative_summary(
            document_id="batch_sheet", document_name="batch_sheet.md",
            conventions_by_category={"conv-h01": [rule]}, findings=[python, model]),
        "operative_unstamped": sg.render_operative_summary(
            document_id="batch_sheet", document_name="batch_sheet.md", conventions_by_category={"conv-h01": [rule]},
            findings=[{"verdict": "VIOLATION", "conv_id": "CONV-001", "category": "conv-h01", "reasoning": LONG_PROSE},
                      dict(hoc.computed_findings()[0], category="conv-h01", explanation=LONG_PROSE)]),
        "grounding": sg.render_context_summary(
            document_id="batch_sheet", document_name="batch_sheet.md", topics=["conv-h01"], context_refs=whole),
        "grounding_unrecovered": sg.render_context_summary(
            document_id="batch_sheet", document_name="batch_sheet.md", topics=["conv-h01"],
            context_refs=unrecovered),
    }
    out = {}
    for name, text in texts.items():
        key = "context_summary" if name.startswith("grounding") else "operative_summary"
        scrubbed, report = _scrub_file(td, name + ".md", text, SPAN, key=key)
        out[name] = {"shown": text.count(SPAN) > 0, "piece_left": _left(scrubbed, SPAN),
                     "survivors": sorted(report["survivors"])}
    # The index's own record is unchanged: its stored excerpt is still clipped at 200.
    import reference_builder as rb
    passage = next(r for r in stored if r["location"]["paragraph"] == 2)
    out["index_unchanged"] = [passage["text_excerpt"] == GROUNDING_PASSAGE[:rb.PROSE_EXCERPT_CHARS],
                              "passage" not in passage]
    out["not_shown_said"] = sg.PASSAGE_NOT_SHOWN in texts["grounding_unrecovered"]
    return out


_PUNCT = re.compile(r"[!-/:-@\[-`{-~]")


def _commonmark_raw(line):
    """The characters of one rendered line a CommonMark reader reads as markup: not
    escaped (a backslash before ASCII punctuation escapes it) and not inside a code
    span (a backtick run opens one, closed by the next run of the same length; a run
    with none is plain text). Others become NUL. Written from the CommonMark rules,
    independently of the renderer."""
    out, i = [], 0
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line) and _PUNCT.match(line[i + 1]):
            out += ["\0", "\0"]
            i += 2
            continue
        if line[i] == "`":
            j = i
            while j < len(line) and line[j] == "`":
                j += 1
            close = re.compile(r"(?<!`)%s(?!`)" % ("`" * (j - i))).search(line, j)
            end = close.end() if close else j
            out += ["\0"] * (end - i)
            i = end
            continue
        out.append(line[i])
        i += 1
    return "".join(out)


def _code_display(rendered):
    """What a CommonMark reader shows of the round-4 code fixture, read off the rendered
    file by the rules (written from CommonMark, not from the renderer): an indented
    code block shows a line of four or more columns after a blank line (outside a list)
    as written less four columns; a fenced block shows the lines between its fences
    as written; a code span shows its content as written; any other text shows each
    character with its escapes undone, and reads markup where it is raw
    (`_commonmark_raw`)."""
    from sensitivity_layer.scrub import _unescaped
    lines = rendered.splitlines()
    name = next((ln for ln in lines if ln.startswith("Name: Mara")), "")

    def at(line):
        return lines.index(line) if line in lines else -1
    fence = at(CODE_LINES["fenced"][0])
    indented = at(CODE_LINES["indented"])
    span_line = at(CODE_LINES["span"])
    tick = next((ln for ln in lines if "Tick" in ln), "")
    pipe = next((ln for ln in lines if "a|" in ln), "")
    in_list = next((ln for ln in lines if "inlist" in ln), "")
    return {
        # Shown as written, less its four columns, only as an indented code block: a
        # blank line before it, and no list item open above it.
        "indented": indented > 0 and lines[indented - 1] == "",
        "fenced": fence >= 0 and lines[fence:fence + 4] == CODE_LINES["fenced"],
        # The code span's content as written, its delimiters raw.
        "span": span_line >= 0 and _commonmark_raw(lines[span_line]).count("`") == 0,
        # Text outside code: every character as the document wrote it, no markup raw.
        "outside": _unescape(name) == CODE_LINES["outside"] and not re.search(r"\*\*|<|>", _commonmark_raw(name)),
        "tick_raw_markup": bool(re.search(r"\*\*|__|<", _commonmark_raw(tick))),
        # A table cell ends at a pipe before a code span is read (GitHub-flavoured), so
        # nothing on the row may be raw markup, inside backticks or not.
        "pipe_raw_markup": bool(re.search(_RAW + r"(\*\*|<)", pipe)),
        "in_list_raw_markup": bool(re.search(_RAW + r"(\*\*|>)", in_list)),
        # The survivor grep's view (`scrub._unescaped`) reads every line as the document wrote it.
        "reader_view": all(ln in _unescaped(rendered).splitlines() for ln in CODE_TEXT.splitlines() if ln.strip()),
    }


def _raw_after_quote(line, pattern):
    """How many matches of `pattern` stand raw on a quoted line, after its `> `."""
    return len(re.findall(_RAW + pattern, line[2:] if line.startswith("> ") else line))


def _one_at_a_time(text, reds):
    """The scrub with one span at a time in list order (a neutralisation)."""
    from sensitivity_layer import scrub
    counts = {}
    for span, repl in scrub._span_list(reds):
        text, n = scrub._sub_span(text, span, repl)
        counts[span] = counts.get(span, 0) + n
    return text, counts


def _replacement_as_given(reds):
    """The span list as it was (a neutralisation): the item's own replacement."""
    return [(str(r.get("span") or "").strip(), r.get("replacement") or "[REDACTED]") for r in reds if r.get("span")]


def _matched_on_unescaped_text(real):
    """The scrub matching on the file with its escapes undone (a neutralisation: the
    design of d298239, where a raw backslash in a code block was not read)."""
    from sensitivity_layer import scrub
    return lambda text, reds: real(scrub._unescaped(text), reds)


def _unescaped_python_block(f, reason, units, rule_texts):
    """A Python finding's sentence left unescaped (a neutralisation)."""
    return ["**%s** %s" % (finding_record.provenance_mark(f), rd._sentence_for(f, units, rule_texts))]


def _free_gap_regex(span):
    """The tolerant matcher with a free connective gap, as it was before D-214 (a
    neutralisation): the gap can swallow whole tokens, so the match backtracks."""
    from sensitivity_layer import scrub
    nc = scrub._norm_classes()
    toks = [re.escape(tok) for tok in str(span or "").split()]
    return re.compile((r"[\s%s,/]{0,24}" % nc.get("script_class")).join(toks), re.IGNORECASE)


def _blocks_after(text, line):
    """The quoted lines that follow `line` (a whole line of the file) up to the next
    line of the document's own text."""
    lines = text.splitlines()
    if line not in lines:
        return []
    out = []
    for ln in lines[lines.index(line) + 1:]:
        if ln.startswith(">"):
            out.append(ln)
        elif ln.strip():
            break
    return out


def observe_direct():
    """The renderer on fixtures of its own: a model sentence longer than the old cut
    with a span across it, a document carrying lines written like finding blocks, a
    wide review (a record without the paired lists), an amendment joined to its finding across an int
    and float figure beside one taken from an agent, a document that is one table, a
    unit whose text cannot be located, two placements that would skip or split, and a
    span across a unit boundary."""
    out = {}
    units = pr.unit_texts_for(hoc.DOC_TEXT, "batch_sheet")
    alpha, beta = hoc._unit(units, "entry-alpha"), hoc._unit(units, "entry-beta")
    with tempfile.TemporaryDirectory(prefix="shimmer_reviewed_direct_") as td:
        # 1: the model's sentence is whole, so the scrub removes the whole span.
        model = dict(hoc.model_finding(), explanation=LONG_PROSE)
        text, report = _through_redaction(td, "cut.md", hoc.DOC_TEXT, SPAN, {"model_findings_not_promoted": [model]},
                                          pairing={})
        out["prose"] = {"whole": "END-OF-PROSE" in text, "span_piece_left": any(
            w in text for w in SPAN.split()), "survivors": sorted(report["survivors"])}
        # 2: the document's own lines written like a finding block are not shown as one.
        planted = hoc.DOC_TEXT.replace("Reading: 61 units", "Reading: 61 units\n" + LOOK_ALIKE)
        text = _render(planted, pairing={})
        planted_lines = [ln for ln in text.splitlines() if "planted" in ln]
        out["look_alike"] = {
            "lines": len(planted_lines),
            "quoted": sum(1 for ln in planted_lines if _renders_quoted(ln)),
            "bold": sum(1 for ln in planted_lines if re.search(_RAW + r"(\*\*|__)", ln)),
            "html": sum(1 for ln in planted_lines if re.search(_RAW + "<", ln)),
            "text_kept": all(_squash(ln) in _squash(_unescape(text)) for ln in LOOK_ALIKE.splitlines())}
        # 2 (round 3): a model's own sentence, agent name and note, written like Python's
        # mark, are not shown as it; the span in the sentence is still scrubbed.
        model = dict(hoc.model_finding(), agent="**%s**" % _PY, explanation=MODEL_TEXT,
                     reader_notes=["__%s__ planted-note" % _PY])
        text, report = _through_redaction(td, "model_text.md", hoc.DOC_TEXT, MODEL_SPAN,
                                          {"model_findings_not_promoted": [model]}, pairing={})
        out["model_text"] = {
            "python_mark_bold": sum(1 for ln in text.splitlines() if re.search(_RAW + r"(\*\*|__)" + re.escape(_PY), ln)),
            "kept": "planted-model" in text and "planted-note" in text,
            "span_left": _left(text, MODEL_SPAN), "survivors": sorted(report["survivors"])}
        # 3: a review whose pairing record lacks the paired review's lists (a wide review,
        # whose record is the map pairing_map builds, with the rules it showed no agent)
        # and one with no record state neither count; a paired review's record states both.
        import pairing_map
        wide = pairing_map.build_pairing_map(hoc.DOC_TEXT, hoc.RULES, document_id="batch_sheet")
        wide["not_judged"] = [{"unit_id": None, "rule_id": "CONV-003", "kind": "wide", "reason": "not_assigned",
                               "consumer_agents": [], "status": "not_judged"}]
        paired = {"not_judged": [], "judging_calls": [], "absence_refused": [], "uncomputable_refused": []}
        out["wide"] = {"wide_record_has_paired_keys": [k for k in PAIRED_KEYS if k in wide]}
        for name, pairing in (("wide", wide), ("none", None), ("paired", paired)):
            text = _render(hoc.DOC_TEXT, pairing=pairing)
            out["wide"][name] = {
                "unrecorded": [loc.text(rd.COUNT_REFUSED_UNRECORDED) in text,
                               loc.text(rd.COUNT_NOT_CHECKED_UNRECORDED) in text],
                "numeric": [_count(text, rd.COUNT_REFUSED), _count(text, rd.COUNT_NOT_CHECKED)],
                "nothing_left": loc.text(rd.NOTHING_LEFT) in text, "no_call_record": loc.text(rd.NO_CALL_RECORD) in text,
                "rule_not_given": "- Rule CONV-003: " in text}
        # 4 and 6: an amendment built from Python's finding whose figures it carries as an
        # int and a numeric string, and an amendment taken from an agent's record.
        finding = dict(hoc.computed_findings()[0], written_by=finding_record.WRITTEN_BY_PYTHON)
        computed = {"derived_from": "computed_finding", "finding_unit_id": finding["unit_id"],
                    "finding_rule_id": finding_record.resolved_rule_id(finding),
                    "finding_relation": finding["relation"], "finding_value_a": int(finding["value_a"]),
                    "finding_value_b": "%d" % finding["value_b"], "comment": "Python's comment."}
        agent = {"derived_from": "model_finding", "finding_unit_id": beta, "convention_ref": "CONV-002",
                 "agent": "PRACTICE_AUDITOR", "comment": "The agent's comment."}
        names = {"findings": run_context.DELIVERABLE_FILENAMES["amendments_md"],
                 "docx": run_context.DELIVERABLE_FILENAMES["amendments_docx"]}
        text = _render(hoc.DOC_TEXT, {"amendments": [computed, agent]}, [finding], pairing={})
        out["amendments"] = {"header": [_count(text, rd.COUNT_AMENDMENTS, **names),
                                        _count(text, rd.COUNT_AMENDMENTS_OTHER, **names)],
                             "no_amendment_lines": sum(ln.startswith("> " + rd.NO_AMENDMENT) for ln in text.splitlines()),
                             "python_marked_lines": sum(finding_record.COMPUTED_FINDING_MARK in ln
                                                        for ln in text.splitlines())}
        # 5: a document that is one table, split by row: each row's finding under its row.
        rows = sorted(pr.unit_texts_for(TABLE_TEXT, "ledger").values(), key=lambda u: u["index"])
        row_findings = [dict(hoc.model_finding(), unit_id=u["unit_id"], explanation="row note %d" % n)
                        for n, u in enumerate(rows, 1)]
        text = _render(TABLE_TEXT, {"model_findings_not_promoted": row_findings}, pairing={}, doc_id="ledger")
        out["table"] = [any("row note %d" % n in ln for ln in _blocks_after(text, u["text"].splitlines()[-1]))
                        for n, u in enumerate(rows, 1)] + [rd.UNLOCATED_HEADING in text]
        # 5: a unit whose text cannot be located is shown under its own name, in a section
        # that says so, never as a part the document does not have.
        with patch.object(rd, "_anchor", lambda text, body, cursor: (-1, -1)):
            text = _render(hoc.DOC_TEXT, {"model_findings_not_promoted": [hoc.model_finding()]}, pairing={})
        out["unlocated"] = [rd.UNLOCATED_HEADING in text, rd.UNPLACED_HEADING in text,
                            rd.UNLOCATED_PART.format(unit=alpha) in text]
        # 5: a last line that stands only inside a longer line is not a place, and a unit
        # found past the next unit's place is not placed there.
        out["placement"] = {
            "mid_line": sorted(rd._place("the short one\n", [{"unit_id": "u1", "text": "missing\nshort"}])[1]),
            "skip": sorted(rd._place("the long one\nshort\n", [{"unit_id": "u1", "text": "missing\nshort"},
                                                               {"unit_id": "u2", "text": "the long one\nshort"}])[1])}
        # The net: a span across a unit boundary in a file NOT rendered from scrubbed
        # inputs is split by the block shown there; the survivor grep reads the running
        # text and BLOCKS it.
        _, report = _scrub_file(td, "boundary.md", _render(BOUNDARY_TEXT, pairing={}, doc_id="contact"),
                                BOUNDARY_SPAN)
        out["boundary"] = sorted(report["survivors"])
        # Rendered from scrubbed inputs, the same span never reaches the renderer.
        text, report = _through_redaction(td, "boundary_clean.md", BOUNDARY_TEXT, BOUNDARY_SPAN, pairing={},
                                          doc_id="contact")
        out["boundary_clean"] = {"left": _left(text, BOUNDARY_SPAN), "survivors": sorted(report["survivors"])}
        # The same net, for spans the renderer escaped (one carrying every character it
        # escapes): the survivor grep undoes every escape, so they BLOCK.
        _, report = _scrub_file(td, "boundary_escaped.md", _render(SPLIT_ESCAPED_TEXT, pairing={}, doc_id="contact"),
                                SPLIT_ESCAPED_SPANS)
        out["boundary_escaped"] = sorted(report["survivors"])
        # A span the renderer would escape is gone before it renders, so nothing BLOCKS.
        text, report = _through_redaction(td, "escaped.md", ESCAPED_TEXT, [ESCAPED_SPAN, EVERY_ESCAPE], pairing={},
                                          doc_id="contact")
        out["escaped_replaced"] = {"rendered_escaped": ESCAPED_SPAN not in _render(ESCAPED_TEXT, pairing={},
                                                                                   doc_id="contact"),
                                   "left": [_left(text, s) for s in (ESCAPED_SPAN, EVERY_ESCAPE)],
                                   "survivors": sorted(report["survivors"])}
        # 6 (round 3): a span escaped inside a quoted line, in a file the scrub does not
        # rewrite (a master render, verified only), BLOCKS.
        _, report = _scrub_file(td, "quoted_escaped.md", "# Findings\n\n> **Note** about mara\\_\\_velde.\n",
                                ESCAPED_SPAN, key="amendments_md")
        out["quoted_escaped"] = sorted(report["survivors"])
        # 4 (round 3): the summaries cut nothing, so the span across the old cut is scrubbed.
        out["summaries"] = _summaries(td)
        # A longer span listed before a shorter span inside it, and a shorter span listed
        # first whose words a longer span holds: one matching pass replaces each whole.
        from sensitivity_layer import scrub
        _, counts = scrub._redact_text(ORDER_TEXT, [{"span": LONG_SPAN}, {"span": SHORT_SPAN}])
        text, report = _through_redaction(td, "order.md", ORDER_TEXT, [LONG_SPAN, SHORT_SPAN], pairing={},
                                          doc_id="contact")
        out["order"] = {"rendered_escaped": LONG_SPAN not in _render(ORDER_TEXT, pairing={}, doc_id="contact"),
                        "counts": [counts.get(LONG_SPAN), counts.get(SHORT_SPAN)],
                        "left": _left(text, LONG_SPAN), "survivors": sorted(report["survivors"])}
        _, counts = scrub._redact_text(WIDE_TEXT, [{"span": FIRST_SPAN}, {"span": WIDE_SPAN}])
        text, report = _through_redaction(td, "wide.md", WIDE_TEXT, [FIRST_SPAN, WIDE_SPAN], pairing={},
                                          doc_id="contact")
        out["wide_order"] = {"counts": [counts.get(FIRST_SPAN), counts.get(WIDE_SPAN)],
                             "token_left": any(w in text for w in ("Bren", "Orrin", "4471")),
                             "survivors": sorted(report["survivors"])}
        # A span holding a backslash before punctuation, raw in a code block, is removed.
        text, report = _through_redaction(td, "backslash.md", BACKSLASH_TEXT, BACKSLASH_SPAN, pairing={},
                                          doc_id="contact")
        out["backslash"] = {"left": "Veloso" in text, "survivors": sorted(report["survivors"])}
        # A span in a heading: the unit id carries it, in a form no matcher reads. The id
        # is derived again, so it goes from the master, and the finding stays at its unit.
        out["heading"] = []
        for n, (heading, span) in enumerate(HEADINGS):
            doc = HEADED_TEXT % heading
            unit = sorted(pr.unit_texts_for(doc, "contact").values(), key=lambda u: u["index"])[0]["unit_id"]
            headed = {"model_findings_not_promoted": [dict(hoc.model_finding(), unit_id=unit, explanation="heading note")]}
            text, report = _through_redaction(td, "heading%d.md" % n, doc, span, headed, pairing={}, doc_id="contact")
            note_at = text.find("heading note")
            out["heading"].append({"id_left": unit in text or unit in json.dumps(report["master"]),
                                   "at_unit": 0 <= note_at < text.find("Ledger", text.index(rd.DOCUMENT_HEADING)),
                                   "survivors": sorted(report["survivors"])})
        # A figure reaches a record as a number, and a renderer writes it its own way.
        finding = dict(hoc.computed_findings(text=hoc.DOC_TEXT)[0], written_by=finding_record.WRITTEN_BY_PYTHON,
                       unit_id=sorted(pr.unit_texts_for(FIGURE_TEXT, "contact").values(), key=lambda u: u["index"])[0]["unit_id"],
                       value_a=1250000.0, unit_a="USD", value_b=900000.0, unit_b="USD")
        computed = {"derived_from": "computed_finding", "finding_unit_id": finding["unit_id"],
                    "finding_rule_id": finding_record.resolved_rule_id(finding), "finding_relation": finding["relation"],
                    "finding_value_a": 1250000.0, "finding_unit_a": "USD", "finding_value_b": 900000.0,
                    "comment": "The fee is 1250000.0 USD."}
        text, report = _through_redaction(td, "figure.md", FIGURE_TEXT, FIGURE_SPAN, {"amendments": [computed]},
                                          [finding], pairing={}, doc_id="contact")
        # The comment's own writing is scrubbed, and the form a renderer writes a number in
        # is read, which is what the survivor grep needs to catch it.
        out["figure"] = {"comment_left": "1250000.0 USD" in json.dumps(report["master"].get("amendments")),
                         "written_form_read": scrub._count_span("the fee is 1250000.0 USD", FIGURE_SPAN) > 0,
                         "bare_word_kept": scrub._count_span("the fee is 1250000.0 EUR", FIGURE_SPAN) == 0}
        # A line break in a record's JSON hides nothing.
        text, report = _scrub_file(td, "record.md", JSON_RECORD, "Tarn Veloso", key="per_agent_deliverable")
        out["json_break"] = {"left": "Veloso" in text, "survivors": sorted(report["survivors"])}
        # The matcher reads each form of a span.
        out["forms"] = [scrub._count_span(text, span) > 0 and scrub._count_span(
            scrub._redact_text(text, [{"span": span}])[0], span) == 0 for span, text in FORMS]
        # The model does not choose what replaces a span.
        out["replacement"] = scrub._redact_text("Mr Tarn Veloso paid", [{"span": "Tarn Veloso", "replacement": "T. Veloso"}])[0]
        # A span cannot change what a record is: a word of Python's own mark as a span.
        python = dict(hoc.computed_findings()[0], written_by=finding_record.WRITTEN_BY_PYTHON)
        before = _count(_render(hoc.DOC_TEXT, python=[python], pairing={}), rd.COUNT_FIGURES)
        text, _ = _through_redaction(td, "structural.md", hoc.DOC_TEXT, "Python", python=[python], pairing={})
        out["structural"] = {"before": before, "after": _count(_unescape(text), rd.COUNT_FIGURES.replace("Python", "[REDACTED]"))}
        # A heading is never cut, so a span across the old cut goes whole.
        long_title = "x" * 79 + " Tarn Veloso"
        out["title_whole"] = pr._unit_title({"title": long_title}) == long_title
        # A heading inside a code fence ends the unit before it there, inside the fence:
        # what concerns that unit comes after the fence, or it would be shown as code.
        head = sorted(pr.unit_texts_for(FENCE_TEXT, "contact").values(), key=lambda u: u["index"])[0]["unit_id"]
        lines = _render(FENCE_TEXT, {"model_findings_not_promoted": [dict(hoc.model_finding(), unit_id=head)]},
                        pairing={}, doc_id="contact").splitlines()
        fences = [i for i, ln in enumerate(lines) if ln.startswith("```")]
        marked = [i for i, ln in enumerate(lines) if loc.text(MARK) in ln]
        out["fence"] = {"block_after": bool(fences and marked) and marked[0] > fences[-1], "fences": len(fences)}
        head = sorted(pr.unit_texts_for(OPEN_FENCE_TEXT, "contact").values(), key=lambda u: u["index"])[0]["unit_id"]
        lines = _render(OPEN_FENCE_TEXT, {"model_findings_not_promoted": [dict(hoc.model_finding(), unit_id=head)]},
                        pairing={}, doc_id="contact").splitlines()
        fences = [i for i, ln in enumerate(lines) if ln.startswith("```")]
        marked = [i for i, ln in enumerate(lines) if loc.text(MARK) in ln]
        out["open_fence"] = len(fences) == 2 and bool(marked) and marked[0] > fences[-1]
        # A tilde fence the scanner declines opens nothing in this file.
        lines = _render(TILDE_TEXT, pairing={}, doc_id="contact").splitlines()
        at = next(i for i, ln in enumerate(lines) if "forged line" in ln)
        fences = [i for i, ln in enumerate(lines) if ln == "~~~"]
        # The fence the scanner declined is escaped, so the one it took opens where it says,
        # and the forged line stands inside that block, shown as code.
        out["tilde"] = {"declined_escaped": "   \\~\\~\\~" in lines,
                        "forged_in_code": len(fences) == 2 and fences[0] < at < fences[1]}
        # A model's item with no typed record is counted and pointed to, not lost.
        text = rd.render(document_id="batch_sheet", document_name="batch_sheet.md", document_text=hoc.DOC_TEXT, master={},
                         python_findings=[], pairing={}, rules=hoc.RULES, untyped_items=1)
        out["untyped"] = _count(text, UNTYPED_LINE, record=RECORD)
        # A line break in a model's id stays inside the quotation.
        broken = dict(hoc.model_finding(), rule_id="CONV-001\n\nReading: 16 units")
        lines = _render(hoc.DOC_TEXT, {"model_findings_not_promoted": [broken]}, pairing={}).splitlines()
        out["line_break"] = sum(ln == "Reading: 16 units" or ln.startswith("Reading: 16 units;") for ln in lines)
        # What round 2 changed and nothing else reaches.
        import reference_builder as rb
        import summary_generators as sg
        out["small"] = {"topic_whole": LONG_PROSE in sg.topic_line("c", [{"id": "CONV-1", "rule": LONG_PROSE}]),
                        "header_only_table": rb.excerpt_is_whole("| a |\n|---|\n"),
                        "outcome_kept": scrub._redact_obj({"outcome": "failed", "plan_kind": "failed", "provenance": "failed"},
                                                          [{"span": "failed"}])[1],
                        "number_span": scrub._redact_text("paid 1250000 today", [{"span": 1250000}])[0]}
        # A heading's markup, quoted in a Python finding's sentence, is escaped.
        unit = sorted(pr.unit_texts_for(MARKUP_HEADING, "contact").values(), key=lambda u: u["index"])[0]["unit_id"]
        python = dict(hoc.computed_findings()[0], written_by=finding_record.WRITTEN_BY_PYTHON, unit_id=unit)
        line = next(ln for ln in _render(MARKUP_HEADING, python=[python], pairing={}, doc_id="contact").splitlines()
                    if ln.startswith("> **" + finding_record.COMPUTED_FINDING_MARK))
        out["sentence_escaped"] = len(re.findall(_RAW + r"(\*\*|<)", line.split("**", 2)[2]))
        # The file's agent line is read at phase 9: the redactor ran after phase 6.
        stale = {"agent_states": [{"agent": "REDACTOR", "actual_calls": 0}]}
        fresh = {"agent_states": [{"agent": "REDACTOR", "actual_calls": 1}]}
        text, _ = _through_redaction(td, "agents.md", hoc.DOC_TEXT, "S-ALPHA", pairing={}, activation=fresh,
                                     stale_activation=stale)
        out["agents_fresh"] = "REDACTOR" not in text
        # What was asked is stated.
        text = rd.render(document_id="contact", document_name="contact.md", document_text=hoc.DOC_TEXT, master={},
                         python_findings=[], pairing={}, rules=hoc.RULES, source_files=["rules.md"],
                         objectives="Read the fees.", question="Is the fee right?", activation=stale)
        out["asked"] = ["- The operator's objectives: \"Read the fees.\"" in text,
                        "- The operator's question: Is the fee right?" in text, "read from rules.md" in text,
                        "had made no model call when this file was written: 1 (REDACTOR)" in text,
                        rd.OBJECTIVES_DEFAULT in _render(hoc.DOC_TEXT, pairing={})]
        # Every reason Python gives has the reader's words and a tr row.
        out["reasons_tr"] = [loc.text(v, "tr") != v for v in rd.REFUSAL_REASONS.values()]
        # Matching is bounded on repetitive text.
        started = time.perf_counter()
        scrub._count_span(BACKTRACK_TEXT, BACKTRACK_SPAN)
        out["bounded"] = time.perf_counter() - started < BACKTRACK_LIMIT_SECONDS
        # The net: a span's words in order, further apart than the tolerant gap reads, in
        # a file the scrub only verifies, BLOCK.
        _, report = _scrub_file(td, "net.md", NET_FILE, SHORT_SPAN, key="amendments_md")
        out["net"] = sorted(report["survivors"])
        # Round 4, item 2: the document's code is shown as written; the rest is escaped.
        out["code"] = _code_display(_render(CODE_TEXT, pairing={}, doc_id="contact"))
        # Round 4, item 3: a judging model's note and a model finding's own ids, written
        # like markup, are not shown as markup.
        python = dict(hoc.computed_findings()[0], written_by=finding_record.WRITTEN_BY_PYTHON,
                      explanation=NOTE_TEXT, explanation_by=finding_record.WRITTEN_BY_MODEL,
                      explanation_model="fixture-auditor")
        model = dict(hoc.model_finding(), source_rule_id=SOURCE_ID_TEXT)
        lines = _render(hoc.DOC_TEXT, {"model_findings_not_promoted": [model]}, [python], pairing={}).splitlines()
        note = next((ln for ln in lines if "note-markup" in ln), "")
        reader = next((ln for ln in lines if "src-markup" in ln), "")
        out["notes"] = {"note_raw": [_raw_after_quote(note, p) for p in (r"\*\*", "<", ">")],
                        "reader_raw": [_raw_after_quote(reader, p) for p in (r"\*\*", "<", ">")],
                        "kept": [bool(note), bool(reader)]}
        # Lines split only where CommonMark splits them.
        line = next((ln for ln in _render(FORM_FEED_TEXT, pairing={}, doc_id="contact").splitlines()
                     if "formfeed" in ln and not ln.startswith("Intro")), "")
        out["form_feed"] = {"kept": bool(line), "quoted": _renders_quoted(line),
                            "raw_bold": bool(re.search(_RAW + r"\*\*", line))}
    return out


def check_direct():
    o = observe_direct()
    unrecorded = {"unrecorded": [True, True], "numeric": [None, None], "nothing_left": False}
    summary = {"shown": True, "piece_left": False, "survivors": []}
    want = {"prose": {"whole": True, "span_piece_left": False, "survivors": []},
            "look_alike": {"lines": 9, "quoted": 0, "bold": 0, "html": 0, "text_kept": True},
            "model_text": {"python_mark_bold": 0, "kept": True, "span_left": False, "survivors": []},
            "wide": {"wide_record_has_paired_keys": [],
                     "wide": dict(unrecorded, no_call_record=True, rule_not_given=True),
                     "none": dict(unrecorded, no_call_record=False, rule_not_given=False),
                     "paired": {"unrecorded": [False, False], "numeric": [0, 0], "nothing_left": True,
                                "no_call_record": False, "rule_not_given": False}},
            "amendments": {"header": [1, 1], "no_amendment_lines": 0, "python_marked_lines": 1},
            "table": [True, True, True, False],
            "unlocated": [True, False, True],
            "placement": {"mid_line": [], "skip": ["u2"]},
            "boundary": [BOUNDARY_SPAN],
            "boundary_clean": {"left": False, "survivors": []},
            "backslash": {"left": False, "survivors": []},
            "heading": [{"id_left": False, "at_unit": True, "survivors": []}] * len(HEADINGS),
            "figure": {"comment_left": False, "written_form_read": True, "bare_word_kept": True},
            "json_break": {"left": False, "survivors": []},
            "forms": [True] * len(FORMS),
            "replacement": "Mr [REDACTED] paid",
            "structural": {"before": 1, "after": 1},
            "title_whole": True,
            "fence": {"block_after": True, "fences": 2},
            "open_fence": True,
            "tilde": {"declined_escaped": True, "forged_in_code": True},
            "untyped": 1,
            "line_break": 0,
            "small": {"topic_whole": True, "header_only_table": False, "outcome_kept": 0,
                      "number_span": "paid [REDACTED] today"},
            "sentence_escaped": 0,
            "agents_fresh": True,
            "asked": [True, True, True, True, True],
            "reasons_tr": [True] * len(rd.REFUSAL_REASONS),
            "bounded": True,
            "boundary_escaped": sorted(SPLIT_ESCAPED_SPANS),
            "escaped_replaced": {"rendered_escaped": True, "left": [False, False], "survivors": []},
            "quoted_escaped": [ESCAPED_SPAN],
            "summaries": {"operative_stamped": summary, "operative_unstamped": summary, "grounding": summary,
                          "grounding_unrecovered": {"shown": False, "piece_left": False, "survivors": []},
                          "index_unchanged": [True, True], "not_shown_said": True},
            "order": {"rendered_escaped": True, "counts": [1, 1], "left": False, "survivors": []},
            "wide_order": {"counts": [1, 1], "token_left": False, "survivors": []},
            "net": [SHORT_SPAN],
            "code": {"indented": True, "fenced": True, "span": True, "outside": True, "tick_raw_markup": False,
                     "pipe_raw_markup": False, "in_list_raw_markup": False, "reader_view": True},
            "notes": {"note_raw": [0, 0, 0], "reader_raw": [2, 0, 0], "kept": [True, True]},
            "form_feed": {"kept": True, "quoted": False, "raw_bold": False}}
    bad = [k for k, v in want.items() if o.get(k) != v]
    return ("FAIL" if bad else "PASS", "reviewed document, direct fixtures: %s" % (bad or "every review fix holds"))


def check():
    o = observe()
    bad = []
    a, b, c = (hoc._unit(pr.unit_texts_for(hoc.DOC_TEXT, "batch_sheet"), s)
               for s in ("entry-alpha", "entry-beta", "entry-gamma"))
    expect = {
        "en": {"amendments_at_unit": sorted([(a, True), (b, True), (c, True)]), "model_at_unit": [(a, True)],
               "refused_at_unit": [], "unchecked_at_unit": [], "python_without_amendment": [],
               "model_mark_lines": 1},
        "tr": {"amendments_at_unit": sorted([(a, True), (b, True), (c, True)]), "model_at_unit": [(a, True)],
               "refused_at_unit": [], "unchecked_at_unit": [], "python_without_amendment": [],
               "model_mark_lines": 1, "english_left": []},
        "judged": {"amendments_at_unit": sorted([(a, True), (b, True), (c, True)]), "model_at_unit": [(c, True)],
                   "refused_at_unit": [(b, "CONV-004", 2), (b, "CONV-004", 2), (c, "CONV-004", 1)],
                   "unchecked_at_unit": [(a, "CONV-004", True)], "python_without_amendment": [b],
                   "model_mark_lines": 1},
    }
    for run, want in expect.items():
        got = o[run]
        bad += ["%s.%s" % (run, k) for k, v in want.items() if got.get(k) != v]
        bad += ["%s.%s" % (run, k) for k in ("text_in_order", "units_in_order", "header_names_record") if not got[k]]
        bad += ["%s.%s" % (run, k) for k in ("unplaced_section", "model_lines_unmarked", "python_lines_marked", "dashes")
                if got[k]]
        counts = got["counts"]
        bad += ["%s.counts.%s" % (run, k) for k in ("amendments", "amendments_computed", "model", "refused",
                                                     "not_checked")
                if len(set(counts[k])) != 1]
        if [counts["figures"], counts["checked"]] != got["summary_counts"] or None in got["summary_counts"]:
            bad.append("%s.counts.python" % run)
    if o["scrub"] != {"present_before": True, "left_in_reviewed": False, "survivors": []}:
        bad.append("scrub")
    return ("FAIL" if bad else "PASS", "reviewed document: %s" % (bad or "the document in order, every finding "
                                                                   "at its unit, marked, counted as the master"))


class _CatalogWithoutReviewedRows:
    """The catalog with the reviewed document's tr rows removed (the neutralisation)."""

    def __enter__(self):
        saved = loc.catalog()
        stripped = {k: v for k, v in saved.items() if k not in set(TEMPLATES)}
        self.patch = patch.object(loc, "catalog", lambda: stripped)
        self.patch.__enter__()
        return self

    def __exit__(self, *exc):
        return self.patch.__exit__(*exc)


@contextlib.contextmanager
def _both(*patches):
    """Several neutralisations held together, each restored on exit."""
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield


def _unmarked(real):
    """The model block with its mark left off (a renderer that forgot it)."""
    return lambda f: [ln.replace("**%s** " % loc.text(MARK), "") for ln in real(f)]


class ReviewedDocumentChecks(unittest.TestCase):
    def prove(self, name, neutralise):
        from effect_proof import prove_effect
        validate = lambda: all(finding_record.is_finding(f) for f in hoc.computed_findings() + [hoc.model_finding()])
        prove_effect(name=name, validate=validate, observe=observe, check=check, neutralise=neutralise)

    def test_findings_sit_at_their_unit(self):
        self.prove("findings_at_unit", lambda: patch.object(rd, "_place", lambda text, units: ([("text", text)], set())))

    def test_the_document_text_is_shown_in_order(self):
        real = rd._place
        self.prove("text_in_order", lambda: patch.object(
            rd, "_place", lambda text, units: ([f for f in real(text, units)[0] if f[0] == "unit"], real(text, units)[1])))

    def test_every_model_finding_is_marked(self):
        self.prove("model_mark", lambda: patch.object(rd, "_model_block", _unmarked(rd._model_block)))

    def test_counts_are_the_masters(self):
        self.prove("master_counts", lambda: patch.object(rd, "master_lists", lambda master: ([], [])))

    def test_refusals_are_stated(self):
        self.prove("refusals", lambda: patch.object(rd, "refused_entries", lambda pairing: []))

    def test_what_was_not_checked_is_stated(self):
        self.prove("not_checked", lambda: patch.object(rd, "not_checked_entries", lambda pairing: []))

    def test_turkish_rendering(self):
        self.prove("tr_rows", _CatalogWithoutReviewedRows)

    def test_the_redaction_scrub_reaches_it(self):
        from sensitivity_layer import scrub
        self.prove("scrub", lambda: patch.object(scrub, "TEXT_ARTIFACT_KEYS", tuple(
            k for k in scrub.TEXT_ARTIFACT_KEYS if k != "reviewed_document")))

    # The review fixes (D-S26 item 3), each on the direct fixtures.
    def prove_direct(self, name, neutralise):
        from effect_proof import prove_effect
        validate = lambda: (finding_record.is_finding(hoc.model_finding())
                            and all(finding_record.is_finding(f) for f in hoc.computed_findings()))
        prove_effect(name=name, validate=validate, observe=observe_direct, check=check_direct, neutralise=neutralise)

    def test_the_model_sentence_is_never_cut(self):
        self.prove_direct("prose_whole", lambda: patch.object(
            rd, "_model_prose", lambda f: rd._flat(f.get("explanation") or f.get("reasoning"))[:240]))

    def test_the_documents_text_cannot_look_like_a_finding(self):
        self.prove_direct("look_alike", lambda: patch.object(rd, "_doc_text", lambda fragment, offset, code: fragment))

    def test_a_wide_review_states_no_pairing_counts(self):
        self.prove_direct("wide_counts", lambda: patch.object(rd, "_pairing_counts", lambda pairing, refused, unchecked: [
            loc.text(rd.COUNT_REFUSED, n=len(refused)), loc.text(rd.COUNT_NOT_CHECKED, n=len(unchecked))]))

    def test_the_counts_follow_the_recorded_lists_not_the_record(self):
        # Round 3: keyed on a pairing record existing (the old test), a wide review's
        # record, which lacks the paired review's lists, would state firm zeros.
        self.prove_direct("recorded_keys", lambda: patch.object(rd, "_recorded", lambda pairing, keys: pairing is not None))

    def test_a_models_own_text_cannot_look_like_pythons(self):
        self.prove_direct("model_text_escaped", lambda: patch.object(rd, "_free_text", rd._flat))

    def test_the_summaries_cut_nothing(self):
        import summary_generators as sg
        self.prove_direct("summaries_whole", lambda: patch.object(sg, "_whole", lambda text: str(text or "")[:240]))

    def test_an_unlocated_part_is_not_a_part_the_document_lacks(self):
        self.prove_direct("unlocated_apart", lambda: patch.object(
            rd, "_where", lambda unit_id, placed, units: unit_id if unit_id in placed else None))

    def test_the_survivor_grep_undoes_every_escape(self):
        # Quoted lines are still removed; only the unescape is gone.
        from sensitivity_layer import scrub
        self.prove_direct("unescape", lambda: patch.object(scrub, "_MARKDOWN_ESCAPE", re.compile(r"(?!)(.)")))

    def test_the_file_is_rendered_from_scrubbed_inputs(self):
        # Left as phase 6 wrote it, a span it escaped or split BLOCKS (or is left).
        self.prove_direct("from_scrubbed", lambda: patch.object(rd, "write_from_scrubbed", lambda *args, **kwargs: None))

    def test_an_escaped_span_in_a_quoted_line_blocks(self):
        from sensitivity_layer import scrub
        self.prove_direct("escaped_quoted", lambda: _both(
            patch.object(scrub, "_running_views", lambda text: [scrub._reader_view(text)])))

    def test_amendments_are_counted_by_who_built_them(self):
        self.prove_direct("amendment_counts", lambda: patch.object(
            rd, "amendment_counts", lambda amendments: (len(amendments), 0)))

    def test_an_amendment_joins_its_finding_across_number_types(self):
        self.prove_direct("figure_join", lambda: patch.object(rd, "_figure", repr))

    def test_table_rows_are_placed_by_their_own_line(self):
        self.prove_direct("row_fallback", lambda: patch.object(rd, "_last_line_at", lambda text, line, cursor: -1))

    def test_a_line_inside_a_longer_line_is_no_place(self):
        self.prove_direct("whole_line", lambda: patch.object(
            rd, "_last_line_at", lambda text, line, cursor: text.find(line, cursor)))

    def test_no_unit_is_skipped(self):
        self.prove_direct("no_skip", lambda: patch.object(rd, "_skips_a_unit", lambda *args: False))

    def test_a_span_split_at_a_unit_boundary_blocks(self):
        from sensitivity_layer import scrub
        self.prove_direct("split_span", lambda: patch.object(scrub, "_reader_view", lambda text: text))

    def test_one_span_at_a_time_cannot_split_a_later_span(self):
        from sensitivity_layer import scrub
        self.prove_direct("span_order_one_at_a_time", lambda: patch.object(scrub, "_redact_text", _one_at_a_time))

    def test_a_spans_words_far_apart_block(self):
        from sensitivity_layer import scrub
        self.prove_direct("exact_form", lambda: patch.object(
            scrub, "_span_forms", lambda span: [scrub._redaction_span_regex(span)]))

    def test_a_raw_backslash_in_a_code_block_is_removed(self):
        from sensitivity_layer import scrub
        self.prove_direct("backslash", lambda: patch.object(
            scrub, "_scrub_one_pass", _matched_on_unescaped_text(scrub._scrub_one_pass)))

    def test_a_unit_id_is_derived_again_whatever_the_headings_form(self):
        from sensitivity_layer import redaction_stage
        self.prove_direct("neutral_ids", lambda: patch.object(
            redaction_stage, "_neutral_unit_ids", lambda doc, spans, ids: []))

    def test_a_figure_goes_in_the_records_form_too(self):
        from sensitivity_layer import scrub
        self.prove_direct("figure_form", lambda: patch.object(scrub, "_figure_form_regex", lambda span: None))

    def test_a_json_line_break_hides_nothing(self):
        from sensitivity_layer import scrub
        self.prove_direct("json_break", lambda: patch.object(scrub, "_SEPARATORS", ",/\\-_."))

    def test_the_matcher_reads_each_form_of_a_span(self):
        from sensitivity_layer import scrub
        self.prove_direct("span_forms", lambda: patch.object(
            scrub, "_span_forms", lambda span: [scrub._exact_form_regex(span)]))

    def test_the_model_does_not_choose_the_replacement(self):
        from sensitivity_layer import scrub
        self.prove_direct("replacement", lambda: patch.object(scrub, "_span_list", _replacement_as_given))

    def test_a_span_cannot_change_an_enumerated_field(self):
        from sensitivity_layer import scrub
        self.prove_direct("structural", lambda: patch.object(scrub, "_STRUCTURAL_FIELDS", frozenset()))

    def test_a_heading_is_never_cut(self):
        self.prove_direct("title_whole", lambda: patch.object(pr, "_unit_title", lambda unit: unit["title"][:80]))

    def test_a_block_is_never_set_inside_code(self):
        self.prove_direct("in_code", lambda: patch.object(rd, "_in_code", lambda offset, code, text: False))

    def test_an_open_fence_is_closed_after_the_document(self):
        self.prove_direct("open_fence", lambda: patch.object(rd, "_open_fence", lambda text: None))

    def test_a_tilde_opens_no_fence(self):
        self.prove_direct("tilde", lambda: patch.object(rd, "_escape_outside_code", lambda text: rd._escape(text).replace("`", "\\`")))

    def test_an_untyped_model_item_is_counted(self):
        self.prove_direct("untyped", lambda: patch.object(rd, "COUNT_UNTYPED", ""))

    def test_a_line_break_stays_in_the_quotation(self):
        self.prove_direct("line_break", lambda: patch.object(rd, "_reader_text", lambda f: rd._escape(finding_record.reader_line(f))))

    def test_a_python_sentence_is_escaped(self):
        self.prove_direct("sentence_escaped", lambda: patch.object(rd, "_python_block", _unescaped_python_block))

    def test_the_agent_line_is_read_at_phase_9(self):
        real = rd.write_from_scrubbed
        self.prove_direct("agents_fresh", lambda: patch.object(
            rd, "write_from_scrubbed", lambda info, master, text, scrub, activation=None: real(info, master, text, scrub)))

    def test_what_was_asked_is_stated(self):
        self.prove_direct("asked", lambda: patch.object(rd, "OBJECTIVES_OWN", ""))

    def test_a_finding_that_is_not_shown_raises(self):
        with patch.object(rd, "_where", lambda unit_id, placed, units: "nowhere"):
            with self.assertRaises(RuntimeError):
                _render(hoc.DOC_TEXT, {"model_findings_not_promoted": [hoc.model_finding()]}, pairing={})

    def test_the_board_lands_in_the_agent_record(self):
        import pipeline
        with tempfile.TemporaryDirectory(prefix="shimmer_board_") as td:
            record, reviewed = Path(td) / RECORD, Path(td) / REVIEWED
            record.write_text("# record\n", encoding="utf-8")
            reviewed.write_text("# reviewed\n", encoding="utf-8")
            pipeline._append_board_to_deliverable({"per_agent_deliverable": str(record),
                                                   "reviewed_document": str(reviewed)}, [{
                "ref": "REF-0001", "governing": {"verdict": "NOTE", "rank": "lead", "rationale": "board-note"},
                "superseded": []}])
            self.assertIn("board-note", record.read_text(encoding="utf-8"))
            self.assertNotIn("board-note", reviewed.read_text(encoding="utf-8"))

    def test_matching_is_bounded_on_repetitive_text(self):
        from sensitivity_layer import scrub
        self.prove_direct("bounded_gap", lambda: patch.object(scrub, "_redaction_span_regex", _free_gap_regex))

    def test_code_blocks_are_shown_as_written(self):
        self.prove_direct("code_blocks", lambda: patch.object(rd, "_code_lines", lambda text: []))

    def test_code_spans_are_shown_as_written(self):
        self.prove_direct("code_spans", lambda: patch.object(rd, "_code_spans", lambda line: []))

    def test_an_indented_line_in_a_list_is_not_code(self):
        self.prove_direct("list_context", lambda: patch.object(rd, "_LIST_ITEM", re.compile(r"(?!)")))

    def test_a_freed_backtick_cannot_open_a_code_span(self):
        self.prove_direct("backtick_escape", lambda: patch.object(rd, "_escape_outside_code", rd._escape))

    def test_a_code_span_with_a_pipe_is_not_taken(self):
        self.prove_direct("span_breakers", lambda: patch.object(rd, "_SPAN_BREAKERS", ""))

    def test_a_models_note_is_escaped(self):
        self.prove_direct("model_note", lambda: patch.object(rd, "_model_note", lambda note: note))

    def test_a_reader_line_is_escaped(self):
        self.prove_direct("reader_line", lambda: patch.object(rd, "_reader_text", finding_record.reader_line))

    def test_the_grounding_summary_shows_passages_whole(self):
        import summary_generators as sg
        self.prove_direct("grounding_whole", lambda: patch.object(sg, "_passage_text",
                                                                  lambda ref: ref.get("text_excerpt")))

    def test_a_clipped_excerpt_is_not_shown(self):
        import reference_builder as rb
        self.prove_direct("clipped_not_shown", lambda: patch.object(rb, "excerpt_is_whole", lambda text: True))

    def test_phase_6_gives_the_grounding_summary_whole_passages(self):
        import reference_builder as rb
        from effect_proof import prove_effect
        prove_effect(name="grounding_phase_6", validate=lambda: rb.excerpt(GROUNDING_PASSAGE) != GROUNDING_PASSAGE,
                     observe=observe_grounding, check=check_grounding,
                     neutralise=lambda: patch.object(rb, "with_whole_passages", lambda refs, texts: list(refs)))

    def test_lines_split_only_where_commonmark_splits(self):
        self.prove_direct("commonmark_lines", lambda: patch.object(
            rd, "_lines", lambda text: text.splitlines(keepends=True)))

    def prove_stage(self, name, observe_stage, check_stage, neutralise):
        from effect_proof import prove_effect
        prove_effect(name=name, validate=lambda: SPAN in UNION_B_TEXT and SPAN not in UNION_A_TEXT,
                     observe=observe_stage, check=check_stage, neutralise=neutralise)

    def test_every_document_is_scrubbed_with_the_runs_spans(self):
        from sensitivity_layer import redaction_stage
        self.prove_stage("union_spans", observe_union, check_union,
                         lambda: patch.object(redaction_stage, "_run_spans", lambda *lists: []))

    def test_a_document_locates_only_its_own_spans(self):
        from sensitivity_layer import redaction_stage
        real = redaction_stage.scrub_master_and_body
        self.prove_stage("own_spans", observe_union, check_union, lambda: patch.object(
            redaction_stage, "scrub_master_and_body", lambda master, reds, text, own=None: real(master, reds, text)))

    def test_every_written_form_of_a_span_reaches_every_document(self):
        from sensitivity_layer import redaction_stage, scrub
        # The tolerant form alone now reads the article, so it is held off too.
        self.prove_stage("written_forms", observe_forms, check_forms, lambda: _both(
            patch.object(redaction_stage, "_run_spans", redaction_stage._merge_redaction_proposals),
            patch.object(scrub, "_redaction_span_regex", lambda span: None)))

    def test_a_held_documents_deterministic_spans_join_the_run(self):
        from sensitivity_layer import redaction_stage
        real = redaction_stage._run_spans
        self.prove_stage("held_spans", observe_held, check_held, lambda: patch.object(
            redaction_stage, "_run_spans", lambda *lists: real(*[
                [i for i in items if i.get("span") != HELD_SPAN] for items in lists])))

    def test_what_is_unknown_from_a_held_document_is_reported(self):
        from sensitivity_layer import redaction_stage
        self.prove_stage("unknown_reported", observe_held, check_held, lambda: patch.object(
            redaction_stage, "_unknown_documents", lambda docs, read: []))

    def test_what_is_unknown_is_said_on_a_none_report(self):
        from sensitivity_layer import redaction_stage
        self.prove_stage("unknown_on_none", observe_held_none, check_held_none, lambda: patch.object(
            redaction_stage, "_unknown_documents", lambda docs, read: []))

    def test_a_document_says_when_it_held_only_others_spans(self):
        from sensitivity_layer import redaction_stage
        self.prove_stage("only_others", observe_union, check_union, lambda: patch.object(
            redaction_stage, "_only_others", lambda redactions: False))

    def test_a_model_cannot_set_a_neutral_id(self):
        from sensitivity_layer import redaction_stage
        real = redaction_stage._run_spans

        def keeps_items(*lists):
            return [i for items in lists for i in items or [] if isinstance(i, dict) and i.get("span")]
        self.prove_stage("model_neutral_id", observe_stage_guards, check_stage_guards, lambda: patch.object(
            redaction_stage, "_run_spans", keeps_items))

    def test_each_document_uses_its_own_unit_ids(self):
        from sensitivity_layer import redaction_stage
        real = redaction_stage._neutral_unit_ids

        def everyone(doc, spans, ids):
            return real({"id": "doc_a", "text": "## Bren\n\nReading: 3 units\n"}, spans, ids) + real(doc, spans, ids)
        self.prove_stage("own_ids", observe_stage_guards, check_stage_guards, lambda: patch.object(
            redaction_stage, "_neutral_unit_ids", everyone))

    def test_the_memo_ships_as_phase_9_scrubbed_it(self):
        self.prove_stage("memo", observe_memo, check_memo, lambda: patch.object(
            rd, "ship_memo", lambda source, dest, info: Path(dest).write_text(
                Path(source).read_text(encoding="utf-8"), encoding="utf-8")))

    def test_a_context_passages_shapes_are_found(self):
        from sensitivity_layer import redaction_stage
        self.prove_stage("grounding_detected", observe_context, check_context, lambda: patch.object(
            redaction_stage, "_detected_in_grounding", lambda info, rules: []))

    def test_a_run_with_no_span_renders_nothing(self):
        from sensitivity_layer import redaction_stage
        self.prove_stage("no_span_at_all", observe_no_span, check_no_span, lambda: patch.object(
            redaction_stage, "_no_span_at_all", lambda redactions, spans: False))

    def test_a_document_holding_only_anothers_span_is_not_none(self):
        from sensitivity_layer import redaction_stage
        self.prove_stage("others_in_body", observe_union, check_union, lambda: patch.object(
            redaction_stage, "_held_no_other_span", lambda redactions, rep, body, doc: not redactions and not rep["total_subs"]))

    def test_the_stage_renders_the_file_from_scrubbed_inputs_in_the_runs_language(self):
        self.prove_stage("rerender", observe_rerender, check_rerender,
                         lambda: patch.object(rd, "write_from_scrubbed", lambda *args, **kwargs: None))

    def test_the_run_language_reaches_phase_9(self):
        real = rd.write_from_scrubbed

        def english(info, master, text, scrub, activation=None):
            real(dict(info, reviewed_render_inputs=dict(info["reviewed_render_inputs"], output_language=None)),
                 master, text, scrub, activation=activation)
        self.prove_stage("rerender_language", observe_rerender, check_rerender,
                         lambda: patch.object(rd, "write_from_scrubbed", english))

    def test_phase_9_renders_the_reviewed_document_again(self):
        from effect_proof import prove_effect
        this = sys.modules[__name__]
        src = _pipeline_source()
        dropped = src.replace("reviewed_document_mod.write_from_scrubbed(info, scrubbed_master, body_text, scrub, "
                              "activation=activation)", "pass")
        prove_effect(name="phase_9_wiring", validate=lambda: dropped != src,
                     observe=observe_phase_9_wiring, check=check_phase_9_wiring,
                     neutralise=lambda: patch.object(this, "_pipeline_source", lambda: dropped))

    def test_phase_6_is_given_the_context_texts(self):
        from effect_proof import prove_effect
        this = sys.modules[__name__]
        src = _pipeline_source()
        dropped = src.replace(',\n            context_texts={d["id"]: d["text"] for d in ctx_docs}', "").replace(
            ',\r\n            context_texts={d["id"]: d["text"] for d in ctx_docs}', "")
        prove_effect(name="phase_6_wiring", validate=lambda: dropped != src,
                     observe=observe_wiring, check=check_wiring,
                     neutralise=lambda: patch.object(this, "_pipeline_source", lambda: dropped))


def observe_grounding():
    """The real phase 6 on a mocked run whose context document has a passage longer than
    the index's clip, with a span straddling character 200: is the passage in
    grounding_summary.md whole, and is the span scrubbed whole on disk?"""
    from sensitivity_layer.scrub import scrub_text_artifacts_and_verify
    with tempfile.TemporaryDirectory(prefix="shimmer_reviewed_grounding_") as td:
        run = hoc.mocked_run(Path(td) / "run", context_text=GROUNDING_CONTEXT)
        info = {k: v for k, v in run["deliverables"][run["doc"]["id"]].items() if k == "context_summary"}
        before = hoc._read(info["context_summary"])
        recorded = run["deliverables"][run["doc"]["id"]].get("grounding_passages") or []
        untyped_recorded = "untyped_items" in run["deliverables"][run["doc"]["id"]]["reviewed_render_inputs"]
        reds = [{"span": SPAN, "replacement": "[REDACTED]"}]
        report = scrub_text_artifacts_and_verify(reds, info, {SPAN: 1}, {})
        after = hoc._read(info["context_summary"])
        return {"whole": GROUNDING_PASSAGE in before, "piece_left": _left(after, SPAN),
                "recorded": GROUNDING_PASSAGE in recorded and untyped_recorded, "survivors": sorted(report["survivors"])}


def check_grounding():
    o = observe_grounding()
    ok = o == {"whole": True, "piece_left": False, "recorded": True, "survivors": []}
    return ("PASS" if ok else "FAIL", "grounding summary from phase 6: %s" % ("each passage whole" if ok else o))


# Documents under review in one sensitive run. Document B's own span stands past character
# 200 of a paragraph of B; a context document holds the same text, and document A's grounding
# summary cites that passage whole (`_quoting_summary` indexes the text as context, the only
# way a summary quotes anything). Document C neither holds nor quotes it. PRE-AUTHORED, NOT
# MODEL OUTPUT.
UNION_A_TEXT = "## Entry\n\nReading: 3 units\n"
UNION_B_TEXT = "## Entry\n\n" + GROUNDING_PASSAGE + "\n\nReading: 4 units\n"
UNION_C_TEXT = "## Entry\n\nReading: 5 units\n"
UNION_RULES = {"conventions": [{"id": "CONV-X", "category": "conv-confidentiality", "action": "flag",
                                "rule": "must not contain an individual's identity number"}]}
# One word in two written forms the proposals' normalised key takes for one: the configured
# definite article (language_redaction_cues.json) before it, and not.
BARE_FORM = "\u0648\u0627\u062d\u0629"
ARTICLE_FORM = "\u0627\u0644" + BARE_FORM
# A grouped-digit identifier the deterministic detector finds in a held document.
HELD_SPAN = "4471-2290-8836"
HELD_TEXT = "## Entry\n\nThe holder is registered under %s in the ledger.\n\nReading: 4 units\n" % HELD_SPAN


class _Bus:
    def __init__(self):
        self.events = []
        self.bodies = []

    def _post_orchestrator(self, **kwargs):
        self.events.append((kwargs.get("body") or {}).get("event"))
        self.bodies.append(kwargs.get("body") or {})


class _Redactor:
    """The REDACTOR's reply, authored: {document id: spans}; a document mapped to None
    answers with a reply that fails its contract (the deliverable is held)."""
    def __init__(self, spans, extra=None):
        self.spans = spans
        self.extra = extra or {}

    def run_task(self, *, work_payload, **kwargs):
        doc_id = work_payload["document_id"]
        spans = self.spans.get(doc_id, [])
        if spans is None:
            return {"ok": False, "error": "contract_violation", "contract_missing": ["json parse failure"]}
        items = [dict({"kind": "redaction", "span": s, "category": "confidentiality", "replacement": "[REDACTED]",
                       "method": "REDACT", "rule_id": "CONV-X"}, **self.extra) for s in spans]
        return {"ok": True, "parsed": {"agent": "REDACTOR", "doc_id": doc_id, "items": items}}


def _stage(td, docs, spans, summaries, passages=None, masters=None, broken=(), findings_md=None, unit_ids=None,
           render=None, extra=None):
    """The real redaction stage over `docs`, each with an empty master, the grounding
    summary text `summaries` gives it and the passages `passages` says it shows. Returns
    the stage's summary and {doc: summary text}."""
    from sensitivity_layer.redaction_stage import run_redaction_phase
    deliverables = {}
    for d in docs:
        folder = Path(td) / d["id"]
        folder.mkdir()
        master = json.dumps((masters or {}).get(d["id"]) or {"amendments": []})
        (folder / "review_data.json").write_text("{not json" if d["id"] in broken else master, encoding="utf-8")
        deliverables[d["id"]] = {"amendments_json": str(folder / "review_data.json")}
        if d["id"] in (findings_md or {}):
            (folder / "review_findings.md").write_text(findings_md[d["id"]], encoding="utf-8")
            deliverables[d["id"]]["amendments_md"] = str(folder / "review_findings.md")
        if d["id"] in summaries:
            grounding = folder / "grounding_summary.md"
            grounding.write_text(summaries[d["id"]], encoding="utf-8")
            deliverables[d["id"]]["context_summary"] = str(grounding)
        deliverables[d["id"]]["grounding_passages"] = (passages or {}).get(d["id"], [])
    bus, renders, rendered = _Bus(), [], {}
    with contextlib.redirect_stderr(io.StringIO()):
        summary = run_redaction_phase(bus, docs, deliverables, None, UNION_RULES,
                                      build_wrapper=lambda name: _Redactor(spans, extra),
                                      render_deliverable=render or (lambda *args: (
                                          renders.append(args[2]["id"]), rendered.__setitem__(args[2]["id"], args[0]))),
                                      unit_ids=unit_ids)
    summary["_bus"], summary["_renders"], summary["_masters"] = bus, renders, rendered
    return summary, {k: (Path(td) / k / "grounding_summary.md").read_text(encoding="utf-8") for k in summaries}


def _states(summary):
    return {k: v.get("state") for k, v in sorted(summary.items()) if not k.startswith("_")}


def _quoting_summary(td, docs, cited_id):
    """A's grounding summary, citing whole a context document's copy of the text of `cited_id`."""
    import summary_generators as sg
    import reference_builder as rb
    index = rb.ReferenceIndex(project_root=Path(td), index_path=Path(td) / "refs.json")
    for d in docs:
        index.index_document(input_type="context", document_id=d["id"], document_name=d["name"], text=d["text"])
    cited = [e.as_dict() for e in index.entries if e.document_id == cited_id]
    return sg.render_context_summary(document_id="doc_a", document_name="doc_a.md", context_refs=rb.with_whole_passages(
        cited, {d["id"]: d["text"] for d in docs}))


def observe_union():
    """The real stage over four documents: is B's span gone from A's grounding summary, and
    what does the stage report for each? D holds B's span in its body alone."""
    docs = [{"id": "doc_a", "name": "doc_a.md", "text": UNION_A_TEXT},
            {"id": "doc_b", "name": "doc_b.md", "text": UNION_B_TEXT},
            {"id": "doc_c", "name": "doc_c.md", "text": UNION_C_TEXT},
            {"id": "doc_d", "name": "doc_d.md", "text": "## Entry\n\nNamed: %s here\n" % SPAN}]
    with tempfile.TemporaryDirectory(prefix="shimmer_union_scrub_") as td:
        quoted = _quoting_summary(td, docs[:3], "doc_b")
        summary, after = _stage(td, docs, {"doc_b": [SPAN]}, {"doc_a": quoted})
        return {"shown_before": SPAN in quoted, "left_in_a": _left(after["doc_a"], SPAN), "states": _states(summary),
                "only_others": [summary[d].get("only_other_documents_spans") for d in ("doc_a", "doc_d")],
                "only_others_posted": [b.get("only_other_documents_spans") for b in summary["_bus"].bodies
                                       if b.get("event") == "REDACTION_APPLIED" and b.get("document_id") == "doc_a"],
                "a_substitutions": summary["doc_a"].get("substitutions")}


def check_union():
    o = observe_union()
    ok = (o["shown_before"] and not o["left_in_a"] and o["only_others"] == [True, True]
          and o["only_others_posted"] == [True] and o["a_substitutions"] == 1
          and o["states"] == {"doc_a": "APPLIED", "doc_b": "APPLIED", "doc_c": "NONE", "doc_d": "APPLIED"})
    return ("PASS" if ok else "FAIL", "the run's spans: %s" % ("B's span scrubbed from A and D, C NONE" if ok else o))


def observe_no_span():
    """No span anywhere: every document NONE, and nothing rendered again."""
    docs = [{"id": "doc_a", "name": "doc_a.md", "text": UNION_A_TEXT}]
    with tempfile.TemporaryDirectory(prefix="shimmer_no_span_") as td:
        summary, _ = _stage(td, docs, {}, {})
        return {"states": _states(summary), "renders": summary["_renders"]}


def check_no_span():
    o = observe_no_span()
    ok = o == {"states": {"doc_a": "NONE"}, "renders": []}
    return ("PASS" if ok else "FAIL", "no span: %s" % ("NONE, nothing rendered" if ok else o))


def observe_forms():
    """Two documents writing one word in two forms the proposals' key takes for one, each
    summary quoting both: is each form gone from both?"""
    docs = [{"id": "doc_a", "name": "doc_a.md", "text": "## Entry\n\nName: %s here\n" % ARTICLE_FORM},
            {"id": "doc_b", "name": "doc_b.md", "text": "## Entry\n\nName: %s here\n" % BARE_FORM}]
    quoting = "Quoted: %s and %s.\n" % (ARTICLE_FORM, BARE_FORM)
    with tempfile.TemporaryDirectory(prefix="shimmer_forms_scrub_") as td:
        summary, after = _stage(td, docs, {"doc_a": [ARTICLE_FORM], "doc_b": [BARE_FORM]},
                                {"doc_a": quoting, "doc_b": quoting})
        return {"states": _states(summary), "left": [BARE_FORM in text for _, text in sorted(after.items())]}


def check_forms():
    o = observe_forms()
    ok = o == {"states": {"doc_a": "APPLIED", "doc_b": "APPLIED"}, "left": [False, False]}
    return ("PASS" if ok else "FAIL", "written forms: %s" % ("each form scrubbed everywhere" if ok else o))


def observe_held():
    """A document whose redactor reply fails its contract, with its text also in context: do
    its deterministic spans reach the summary quoting that text and its own files, and is the gap
    reported, on the bus as well as in the report?"""
    docs = [{"id": "doc_a", "name": "doc_a.md", "text": UNION_A_TEXT},
            {"id": "doc_b", "name": "doc_b.md", "text": HELD_TEXT}]
    with tempfile.TemporaryDirectory(prefix="shimmer_held_scrub_") as td:
        quoted = _quoting_summary(td, docs, "doc_b")
        summary, after = _stage(td, docs, {"doc_b": None}, {"doc_a": quoted, "doc_b": "Own: %s.\n" % HELD_SPAN})
        posted = [b.get("spans_unknown_from") for b in summary["_bus"].bodies if b.get("document_id") == "doc_a"
                  and b.get("event") == "REDACTION_APPLIED"]
        return {"shown_before": HELD_SPAN in quoted, "left_in_a": HELD_SPAN in after["doc_a"],
                "left_in_b": HELD_SPAN in after["doc_b"], "states": _states(summary),
                "unknown": summary["doc_a"].get("spans_unknown_from"), "posted": posted,
                "known_applied": summary["doc_b"].get("known_spans_applied")}


def check_held():
    o = observe_held()
    ok = o == {"shown_before": True, "left_in_a": False, "left_in_b": False, "unknown": ["doc_b"],
               "posted": [["doc_b"]], "known_applied": True,
               "states": {"doc_a": "APPLIED", "doc_b": "HELD_WARNING"}}
    return ("PASS" if ok else "FAIL", "a held document: %s" % ("known spans applied, the gap said" if ok else o))


def observe_held_none():
    """A held document with no known span. A document with nothing to scrub reports NONE, so
    the gap has to be said there too: with no span anywhere in the run, and with another
    document's span in the run that it does not hold."""
    held = {"id": "doc_h", "name": "doc_h.md", "text": UNION_C_TEXT}
    quiet = {"id": "doc_a", "name": "doc_a.md", "text": UNION_A_TEXT}
    other = {"id": "doc_b", "name": "doc_b.md", "text": UNION_B_TEXT}
    out = {}
    for name, docs, spans in (("no_span", [quiet, held], {"doc_h": None}),
                              ("a_span_elsewhere", [quiet, other, held], {"doc_h": None, "doc_b": [SPAN]})):
        with tempfile.TemporaryDirectory(prefix="shimmer_held_none_") as td:
            summary, _ = _stage(td, docs, spans, {})
            posted = [b.get("spans_unknown_from") for b in summary["_bus"].bodies
                      if b.get("event") == "REDACTION_NONE" and b.get("document_id") == "doc_a"]
            out[name] = {"state": summary["doc_a"].get("state"), "unknown": summary["doc_a"].get("spans_unknown_from"),
                         "posted": posted}
    return out


def check_held_none():
    o = observe_held_none()
    want = {"state": "NONE", "unknown": ["doc_h"], "posted": [["doc_h"]]}
    ok = o == {"no_span": want, "a_span_elsewhere": want}
    return ("PASS" if ok else "FAIL", "NONE with a held document: %s" % ("the gap is said" if ok else o))


def observe_stage_guards():
    """The stage against what round 2 of the review found: a model's own `neutral_id`, a
    master that cannot be read, a known span surviving in a held document, a render that
    raises, and two documents whose ids overlap."""
    doc = {"id": "doc_a", "name": "doc_a.md", "text": "## Entry\n\nPaid by Tarn Veloso today.\n"}
    out = {}
    with tempfile.TemporaryDirectory(prefix="shimmer_guard_") as td:
        _, after = _stage(td, [doc], {"doc_a": ["Tarn Veloso"]}, {"doc_a": "Paid by Tarn Veloso today.\n"},
                          extra={"neutral_id": "T. Veloso of Nowhere"})
        out["model_neutral_id"] = "T. Veloso of Nowhere" in after["doc_a"]
    with tempfile.TemporaryDirectory(prefix="shimmer_guard_") as td:
        summary, after = _stage(td, [doc], {"doc_a": ["Tarn Veloso"]}, {"doc_a": "Quoted %s.\n" % HELD_SPAN},
                                broken=("doc_a",), passages={"doc_a": ["Quoted %s." % HELD_SPAN]})
        out["unreadable"] = {"state": summary["doc_a"].get("state"), "left": HELD_SPAN in after["doc_a"]}
    with tempfile.TemporaryDirectory(prefix="shimmer_guard_") as td:
        held = {"id": "doc_b", "name": "doc_b.md", "text": HELD_TEXT}
        summary, _ = _stage(td, [held], {"doc_b": None}, {}, findings_md={"doc_b": "Kept: %s.\n" % HELD_SPAN})
        out["held_survivor"] = summary["doc_b"].get("state")

    def raises(master, body, d, info, scrub):
        if d["id"] in ("doc_a", "doc_b"):
            raise ValueError("render")
    with tempfile.TemporaryDirectory(prefix="shimmer_guard_") as td:
        later = {"id": "doc_c", "name": "doc_c.md", "text": UNION_C_TEXT}
        summary, after = _stage(td, [doc, later], {"doc_a": ["Tarn Veloso"]}, {"doc_a": "Named: Tarn Veloso.\n"}, render=raises,
                                findings_md={"doc_a": "Kept: Tarn Veloso.\n"})
        findings = (Path(td) / "doc_a" / "review_findings.md").read_text(encoding="utf-8")
        out["render_raises"] = [summary["doc_a"].get("state"), summary["doc_c"].get("state"), "Veloso" in after["doc_a"],
                                "Veloso" in findings]
    with tempfile.TemporaryDirectory(prefix="shimmer_guard_") as td:
        summary, _ = _stage(td, [{"id": "doc_b", "name": "doc_b.md", "text": HELD_TEXT},
                                 {"id": "doc_c", "name": "doc_c.md", "text": UNION_C_TEXT}],
                            {"doc_b": None}, {}, render=raises)
        out["held_render_raises"] = [summary["doc_b"].get("state"), summary["doc_c"].get("state"),
                                     summary["doc_b"].get("spans_unknown_from")]
    from sensitivity_layer import redaction_stage
    merged = {"id": "doc_a", "text": "## Bren\n\n## Orrin\n\nReading: 3 units\n"}
    out["count_changes"] = sorted(i["neutral_id"] for i in redaction_stage._neutral_unit_ids(
        merged, [{"span": "Bren ## Orrin"}], _unit_ids))
    first = {"id": "doc_a", "name": "doc_a.md", "text": "## Bren\n\nReading: 3 units\n"}
    second = {"id": "doc_b", "name": "doc_b.md", "text": "## Bren Holdings\n\nReading: 4 units\n"}
    with tempfile.TemporaryDirectory(prefix="shimmer_guard_") as td:
        summary, _ = _stage(td, [first, second], {"doc_a": ["Bren"], "doc_b": ["Bren"]}, {}, unit_ids=_unit_ids,
                            masters={"doc_b": {"amendments": [{"finding_unit_id": "u01-bren-holdings"}]}})
        out["own_ids"] = summary["_masters"]["doc_b"]["amendments"][0]["finding_unit_id"]
    return out


def check_stage_guards():
    o = observe_stage_guards()
    ok = o == {"model_neutral_id": False, "unreadable": {"state": "BLOCKED", "left": False}, "held_survivor": "BLOCKED",
               "render_raises": ["BLOCKED", "NONE", False, False], "own_ids": "u01-redacted-holdings",
               "held_render_raises": ["BLOCKED", "NONE", ["doc_b"]],
               "count_changes": ["u01-no-longer-a-part", "u02-no-longer-a-part"]}
    return ("PASS" if ok else "FAIL", "stage guards: %s" % ("each holds" if ok else o))


def observe_memo():
    """The memo a draft run ships: as phase 9 scrubbed it, and as written with no scrub."""
    with tempfile.TemporaryDirectory(prefix="shimmer_memo_") as td:
        source, dest = Path(td) / "source.md", Path(td) / "memo.md"
        source.write_text("Named: %s\n" % SPAN, encoding="utf-8")
        rd.ship_memo(source, dest, {"scrubbed_body": "Named: [REDACTED]\n"})
        scrubbed = dest.read_text(encoding="utf-8")
        rd.ship_memo(source, dest, {})
        return {"scrubbed": SPAN in scrubbed, "plain": SPAN in dest.read_text(encoding="utf-8")}


def check_memo():
    o = observe_memo()
    ok = o == {"scrubbed": False, "plain": True}
    return ("PASS" if ok else "FAIL", "the memo: %s" % ("ships scrubbed when it was" if ok else o))


def observe_context():
    """An authorised shape past the old clip of a context passage no document holds."""
    docs = [{"id": "doc_a", "name": "doc_a.md", "text": UNION_A_TEXT}]
    passage = "%s %s." % ("y" * 300, HELD_SPAN)
    # The header's date is the shape of an identifier too: only the passages are read.
    quoted = '- generated: 2026-11-04T10:00:00\n- **[REF-0001]** context.md: "%s"\n' % passage
    with tempfile.TemporaryDirectory(prefix="shimmer_context_scrub_") as td:
        summary, after = _stage(td, docs, {"doc_a": []}, {"doc_a": quoted}, passages={"doc_a": [passage]})
        return {"left": HELD_SPAN in after["doc_a"], "date_kept": "2026-11-04" in after["doc_a"],
                "states": _states(summary)}


def check_context():
    o = observe_context()
    ok = o == {"left": False, "date_kept": True, "states": {"doc_a": "APPLIED"}}
    return ("PASS" if ok else "FAIL", "a context passage: %s" % ("its shape is found" if ok else o))


def observe_rerender():
    """The real phase 6 then the real stage with the master's own renders, in English and
    tr, with a span the renderer escapes (so the on-disk scrub, which reads the file as
    written, cannot reach it): is the file rendered again with the span gone, in the run's
    language, every count kept, and does the survivor grep pass on every deliverable?"""
    import amendment_render
    from sensitivity_layer.redaction_stage import run_redaction_phase
    out = {}
    with tempfile.TemporaryDirectory(prefix="shimmer_reviewed_rerender_") as td:
        for language in ("en", "tr"):
            run = hoc.mocked_run(Path(td) / language, language=language, text=hoc.DOC_TEXT.replace(
                "Reading: 61 units", "Contact: %s\nReading: 61 units" % ESCAPED_SPAN, 1))
            doc = run["doc"]
            info = run["deliverables"][doc["id"]]
            before = hoc._read(info["reviewed_document"])
            t = lambda s, **v: loc.text(s, language, **v)

            def counts(text):
                names = {"findings": run_context.DELIVERABLE_FILENAMES["amendments_md"],
                         "docx": run_context.DELIVERABLE_FILENAMES["amendments_docx"]}
                return [_count(text, t(rd.COUNT_FIGURES)), _count(text, t(rd.COUNT_CHECKED)), _count(text, t(rd.COUNT_MODEL)),
                        _count(text, t(rd.COUNT_AMENDMENTS), **names), _count(text, t(rd.COUNT_AMENDMENTS_OTHER), **names),
                        _count(text, t(rd.COUNT_REFUSED)), _count(text, t(rd.COUNT_NOT_CHECKED)), text.count(t(MARK))]

            def render(master, body, d, i, scrub):
                amendment_render.write_amendment_deliverables(
                    master, deliv_dir=run["run_dir"] / "deliverables", doc_id=d["id"], document_name=d["name"],
                    body_text=body, category_for_conv=lambda c: "conv-h01")
                rd.write_from_scrubbed(i, master, body, scrub)
            with contextlib.redirect_stderr(io.StringIO()):
                summary = run_redaction_phase(_Bus(), [doc], {doc["id"]: info}, None, UNION_RULES,
                                              build_wrapper=lambda name: _Redactor({doc["id"]: [ESCAPED_SPAN]}),
                                              render_deliverable=render, unit_ids=_unit_ids)
            after = hoc._read(info["reviewed_document"])
            out[language] = {"state": summary[doc["id"]].get("state"),
                             "escaped_before": ESCAPED_SPAN not in before and ESCAPED_SPAN in _unescape(before),
                             "left": ESCAPED_SPAN in _unescape(after),
                             "marker": "[REDACTED]" in _unescape(after),
                             "counts_kept": counts(before) == counts(after) and None not in counts(after),
                             "language_kept": t(rd.DOCUMENT_HEADING) in after}
    return out


def check_rerender():
    o = observe_rerender()
    want = {"state": "APPLIED", "escaped_before": True, "left": False, "marker": True,
            "counts_kept": True, "language_kept": True}
    ok = o == {"en": want, "tr": want}
    return ("PASS" if ok else "FAIL", "rendered from scrubbed inputs: %s" % ("in both languages" if ok else o))


def _pipeline_source():
    return (Path(__file__).resolve().parent / "pipeline.py").read_text(encoding="utf-8")


def observe_wiring():
    """Structural: does main pass phase_6_synthesis the context
    documents' texts, keyed by the id _build_reference_index indexes them under?"""
    import ast
    tree = ast.parse(_pipeline_source())
    funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def key_of(node):
        return [ast.unparse(node.value), node.slice.value] if (
            isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)) else None
    call = next((n for n in ast.walk(funcs["main"]) if isinstance(n, ast.Call)
                 and ast.unparse(n.func) == "phase_6_synthesis"), None)
    given = next((k.value for k in (call.keywords if call else []) if k.arg == "context_texts"), None)
    texts = None
    if isinstance(given, ast.DictComp) and len(given.generators) == 1:
        gen = given.generators[0]
        texts = {"iter": ast.unparse(gen.iter), "key": key_of(given.key), "value": key_of(given.value),
                 "target": ast.unparse(gen.target)}
    index_ids = sorted({tuple(key_of(k.value)) for n in ast.walk(funcs["_build_reference_index"])
                        if isinstance(n, ast.For) and ast.unparse(n.iter) == "ctx_docs"
                        for c in ast.walk(n) if isinstance(c, ast.Call) for k in c.keywords
                        if k.arg == "document_id" and key_of(k.value)})
    index_call = any(isinstance(n, ast.Call) and ast.unparse(n.func) == "_build_reference_index"
                     and n.args[1:2] and ast.unparse(n.args[1]) == "ctx_docs" for n in ast.walk(funcs["main"]))
    return {"texts": texts, "index_ids": [list(i) for i in index_ids], "index_from_ctx_docs": index_call}


def check_wiring():
    o = observe_wiring()
    t = o["texts"] or {}
    target = t.get("target")
    # The same id field indexes a context document and keys its text for phase 6.
    ok = (t.get("iter") == "ctx_docs" and t.get("value") == [target, "text"] and o["index_from_ctx_docs"]
          and len(o["index_ids"]) == 1 and t.get("key") == [target, o["index_ids"][0][1]])
    return ("PASS" if ok else "FAIL", "phase 6 wiring: %s" % ("context_texts from ctx_docs by id" if ok else o))


def observe_phase_9_wiring():
    """Structural: does the redaction phase's render callback in main render the file again?"""
    import ast
    tree = ast.parse(_pipeline_source())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    callback = next((n for n in ast.walk(main) if isinstance(n, ast.FunctionDef)
                     and n.name == "_render_redaction_deliverable"), None)
    calls = [ast.unparse(n.func) for n in ast.walk(callback) if isinstance(n, ast.Call)] if callback else []
    memo = [ast.unparse(n.func) for n in ast.walk(main) if isinstance(n, ast.Call)]
    return {"calls": "reviewed_document_mod.write_from_scrubbed" in calls,
            "memo": "reviewed_document_mod.ship_memo" in memo}


def check_phase_9_wiring():
    o = observe_phase_9_wiring()
    ok = o["calls"] and o["memo"]
    return ("PASS" if ok else "FAIL", "phase 9 wiring: %s" % ("callback renders it again, memo shipped" if ok else o))


def run_checks():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReviewedDocumentChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:160]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d tests, most proven by neutralise, fail, restore, pass, the rest plain tests or asserted (see "
                    "the module docstring): the document's own text whole and in "
                    "order, every amendment, Python finding, model finding, refusal and unchecked rule at its "
                    "unit, the mark on every model finding and on no Python finding, the header's counts equal "
                    "to review_data.json, the document summary and the pairing map, no English left in tr, and "
                    "the redaction scrub reaching the file, and the review fixes on direct fixtures (no cut model "
                    "sentence or summary text, no look-alike finding block from the document or a model, "
                    "pairing counts only where their lists were recorded, amendments counted apart, the figure "
                    "join, table rows, unlocated parts, no skip, code shown as written, notes and reader lines "
                    "escaped, grounding passages whole, CommonMark lines, phase 6 wiring; the redaction: rendered "
                    "again from scrubbed inputs in the run's language with every count kept, one matching pass, unit "
                    "ids derived again, a figure in its record's form, every form of a span, no model-chosen "
                    "replacement, enumerated fields kept, a held document's known spans, a context passage's "
                    "shapes, only a document's own spans located, and the survivor grep's nets)"
                    % result.testsRun)


if __name__ == "__main__":
    status, detail = run_checks()
    print(status, detail)
    sys.exit(0 if status == "PASS" else 1)
