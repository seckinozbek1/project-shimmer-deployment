"""Proofs for the layered .docx reader and the layer record (issue #280, D-666; issue #281 gap
14, D-667). Gate checks 400 to 404 run one group each.

Every fixture is a .docx package built here by hand (zipfile and the WordprocessingML XML), so
no optional library builds it; python-docx reads its main text, as in a run. The words are
invented and carry no domain. Each proof is the project's pattern (scripts/effect_proof.py):
observe, neutralise the behaviour, the check fails, restore, the check passes again.

  A (400) tracked insertions and deletions are read apart with author and date, and the main
          text is the accepted text. Neutralised: no tracked-change element is read.
  B (401) comments are read with author, date and the text they span; footnotes and endnotes
          apart, Word's separators left out. Neutralised: the comments part, then the note
          parts, are not read.
  C (402) a content control, a text box, a nested table and a header are counted as present
          and not read, named in the record's `lost`, and none of their text is in the main
          text. Neutralised: the skipped parts are not counted.
  D (403) a column where a merged cell repeats its value is not summed: the bound paired
          review's plan_calls computes no sum over it and records the refusal. Neutralised: the
          reader writes no line after the table, and the repeated value is summed twice.
  E (404) the bound pipeline's _load_corpus, executed as the sealer executes it, prints every
          document's layer record, and write_deliverables_run_summary writes it into
          _run_summary.md. Neutralised: the printout, then the summary section.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import document_layers  # noqa: E402
import docx_layers  # noqa: E402
import text_extract  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = ('xmlns:w="%s" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
      'xmlns:v="urn:schemas-microsoft-com:vml" '
      'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"' % W_NS)
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PARTS = {  # part name: (relationship type, content type)
    "comments.xml": ("comments", "comments"),
    "footnotes.xml": ("footnotes", "footnotes"),
    "endnotes.xml": ("endnotes", "endnotes"),
    "header1.xml": ("header", "header"),
}


def _p(inner):
    return "<w:p>%s</w:p>" % inner


def _r(text, tag="t"):
    return '<w:r><w:%s xml:space="preserve">%s</w:%s></w:r>' % (tag, text, tag)


def _cell(inner, props=""):
    return "<w:tc><w:tcPr>%s</w:tcPr>%s</w:tc>" % (props, inner)


def build_docx(path, body, *, parts=None):
    """A minimal .docx package: document.xml with `body`, and each extra part given."""
    parts = parts or {}
    overrides = "".join(
        '<Override PartName="/word/%s" ContentType="application/vnd.openxmlformats-officedocument.'
        'wordprocessingml.%s+xml"/>' % (name, PARTS[name][1]) for name in parts)
    rels = "".join('<Relationship Id="rId%d" Type="%s/%s" Target="%s"/>' % (i + 1, REL, PARTS[name][0], name)
                   for i, name in enumerate(parts))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/content-types"><Default Extension="rels" ContentType="application/'
                   'vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" '
                   'ContentType="application/xml"/><Override PartName="/word/document.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.'
                   'document.main+xml"/>%s</Types>' % overrides)
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="'
                   '%s/officeDocument" Target="word/document.xml"/></Relationships>' % REL)
        z.writestr("word/_rels/document.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/relationships">%s</Relationships>' % rels)
        z.writestr("word/document.xml",
                   '<?xml version="1.0" encoding="UTF-8"?><w:document %s><w:body>%s</w:body>'
                   '</w:document>' % (NS, body))
        for name, xml in parts.items():
            z.writestr("word/" + name, '<?xml version="1.0" encoding="UTF-8"?>' + xml)
    return path


# ---------------------------------------------------------------------------
# fixtures

TRACKED_BODY = (
    _p(_r("The first line stays.") +
       '<w:ins w:id="1" w:author="Writer One" w:date="2026-01-02T10:00:00Z">%s</w:ins>' % _r(" Added words.") +
       '<w:del w:id="2" w:author="Writer Two" w:date="2026-01-03T11:00:00Z">%s</w:del>'
       % _r(" Removed words.", "delText")) +
    _p('<w:moveTo w:id="3" w:author="Writer One" w:date="2026-01-04T12:00:00Z">%s</w:moveTo>' % _r("Moved here.")) +
    _p('<w:moveFrom w:id="4" w:author="Writer One" w:date="2026-01-04T12:00:00Z">%s</w:moveFrom>'
       % _r("Moved here.", "delText")))

NOTES_BODY = (
    _p(_r("Before. ") + '<w:commentRangeStart w:id="7"/>' + _r("the spanned words") +
       '<w:commentRangeEnd w:id="7"/>' + _r(" after.") +
       '<w:r><w:commentReference w:id="7"/></w:r>' +
       '<w:r><w:footnoteReference w:id="2"/></w:r><w:r><w:endnoteReference w:id="3"/></w:r>') +
    _p('<w:r><w:commentReference w:id="8"/></w:r>' + _r("A point comment sits here.")))
NOTES_PARTS = {
    "comments.xml": ('<w:comments %s><w:comment w:id="7" w:author="Reader One" w:date="2026-02-01T09:00:00Z">'
                     '%s</w:comment><w:comment w:id="8" w:author="Reader Two" w:date="2026-02-02T09:00:00Z">'
                     '%s</w:comment></w:comments>' % (NS, _p(_r("Please check this.")), _p(_r("A second note.")))),
    "footnotes.xml": ('<w:footnotes %s><w:footnote w:type="separator" w:id="-1">%s</w:footnote>'
                      '<w:footnote w:type="continuationSeparator" w:id="0">%s</w:footnote>'
                      '<w:footnote w:id="2">%s</w:footnote></w:footnotes>'
                      % (NS, _p("<w:r><w:separator/></w:r>"), _p("<w:r><w:continuationSeparator/></w:r>"),
                         _p(_r("The foot note text.")))),
    "endnotes.xml": ('<w:endnotes %s><w:endnote w:type="separator" w:id="-1">%s</w:endnote>'
                     '<w:endnote w:id="3">%s</w:endnote></w:endnotes>'
                     % (NS, _p("<w:r><w:separator/></w:r>"), _p(_r("The end note text.")))),
}

HIDDEN = ("Inside a control", "Inside a box", "Inside an inner table", "Page top words")
SKIPPED_BODY = (
    _p(_r("Visible paragraph.")) +
    "<w:sdt><w:sdtPr/><w:sdtContent>%s</w:sdtContent></w:sdt>" % _p(_r(HIDDEN[0])) +
    _p('<w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><wps:txbx><w:txbxContent>%s'
       '</w:txbxContent></wps:txbx></w:drawing></mc:Choice><mc:Fallback><w:pict><v:textbox>'
       '<w:txbxContent>%s</w:txbxContent></v:textbox></w:pict></mc:Fallback></mc:AlternateContent></w:r>'
       % (_p(_r(HIDDEN[1])), _p(_r(HIDDEN[1])))) +
    "<w:tbl><w:tblGrid><w:gridCol/></w:tblGrid><w:tr>%s</w:tr></w:tbl>"
    % _cell("<w:tbl><w:tblGrid><w:gridCol/></w:tblGrid><w:tr>%s</w:tr></w:tbl>%s"
            % (_cell(_p(_r(HIDDEN[2]))), _p(_r("Outer cell"))))
)
SKIPPED_PARTS = {"header1.xml": "<w:hdr %s>%s</w:hdr>" % (NS, _p(_r(HIDDEN[3])))}

MERGED_BODY = (
    _p(_r("Total weight: 5 kg")) +
    "<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
    "<w:tr>%s%s</w:tr>" % (_cell(_p(_r("Item"))), _cell(_p(_r("Weight (kg)")))) +
    "<w:tr>%s%s</w:tr>" % (_cell(_p(_r("A"))), _cell(_p(_r("2")), '<w:vMerge w:val="restart"/>')) +
    "<w:tr>%s%s</w:tr>" % (_cell(_p(_r("B"))), _cell(_p(""), "<w:vMerge/>")) +
    "<w:tr>%s%s</w:tr>" % (_cell(_p(_r("C"))), _cell(_p(_r("3")))) +
    "</w:tbl>")
MERGED_RULE = {"CONV-T01": {"rule": "The total weight must equal the sum of the weight column."}}


@contextlib.contextmanager
def _fixture(body, parts=None, name="fixture.docx"):
    with tempfile.TemporaryDirectory(prefix="shimmer_layers_") as d:
        yield build_docx(Path(d) / name, body, parts=parts)


# ---------------------------------------------------------------------------
# observations

def observe_tracked():
    with _fixture(TRACKED_BODY) as path:
        layers = docx_layers.read_layers(path)
    return {"main": layers["main"],
            "insertions": [[r["text"], r["author"], r["date"], r["kind"]] for r in layers["insertions"]],
            "deletions": [[r["text"], r["author"], r["date"], r["kind"]] for r in layers["deletions"]],
            "rows": {r["name"]: [r["count"], r["authors"]] for r in layers["record"]["layers"]
                     if r["name"] in (docx_layers.INSERTIONS, docx_layers.DELETIONS)}}


TRACKED = {
    "main": "The first line stays. Added words.\n\nMoved here.",
    "insertions": [[" Added words.".strip(), "Writer One", "2026-01-02T10:00:00Z", "insertion"],
                   ["Moved here.", "Writer One", "2026-01-04T12:00:00Z", "moved to"]],
    "deletions": [["Removed words.", "Writer Two", "2026-01-03T11:00:00Z", "deletion"],
                  ["Moved here.", "Writer One", "2026-01-04T12:00:00Z", "moved from"]],
    "rows": {docx_layers.INSERTIONS: [2, 1], docx_layers.DELETIONS: [2, 2]},
}


def observe_notes():
    with _fixture(NOTES_BODY, NOTES_PARTS) as path:
        layers = docx_layers.read_layers(path)
    return {"comments": [[c["id"], c["author"], c["date"], c["text"], c["anchor"]] for c in layers["comments"]],
            "footnotes": [[n["id"], n["text"]] for n in layers["footnotes"]],
            "endnotes": [[n["id"], n["text"]] for n in layers["endnotes"]],
            "main_has_note_text": any(s in layers["main"] for s in ("Please check", "foot note", "end note"))}


NOTES = {
    "comments": [["7", "Reader One", "2026-02-01T09:00:00Z", "Please check this.", "the spanned words"],
                 ["8", "Reader Two", "2026-02-02T09:00:00Z", "A second note.", ""]],
    "footnotes": [["2", "The foot note text."]],
    "endnotes": [["3", "The end note text."]],
    "main_has_note_text": False,
}


def observe_skipped():
    with _fixture(SKIPPED_BODY, SKIPPED_PARTS) as path:
        layers = docx_layers.read_layers(path)
    rec = layers["record"]
    return {"not_read": {r["name"]: r["count"] for r in rec["layers"] if not r["read"]},
            "lost": rec["lost"],
            "hidden_in_main": [h for h in HIDDEN if h in layers["main"]],
            "shape": document_layers.is_record(rec)}


SKIPPED = {
    "not_read": {docx_layers.CONTENT_CONTROLS: 1, docx_layers.TEXT_BOXES: 1,
                 docx_layers.NESTED_TABLES: 1, docx_layers.HEADERS_FOOTERS: 1},
    "lost": [docx_layers.CONTENT_CONTROLS, docx_layers.TEXT_BOXES, docx_layers.NESTED_TABLES,
             docx_layers.HEADERS_FOOTERS],
    "hidden_in_main": [],
    "shape": True,
}


def observe_merged():
    import paired_review
    with _fixture(MERGED_BODY) as path:
        layers = docx_layers.read_layers(path)
    unit = {"id": "u01", "text": layers["main"]}
    refusals = []
    plans = paired_review.plan_calls({"u01": unit}, [("u01", "CONV-T01")], MERGED_RULE, None,
                                     relation_refusal_sink=refusals)
    sums = sorted({(c["computed"], c["stated"]) for p in plans for c in p.get("checks", [])
                   if c.get("relation") == "sum_mismatch"})
    merged_row = [r["count"] for r in layers["record"]["layers"] if r["name"] == docx_layers.MERGED_CELLS]
    return {"sums": [list(s) for s in sums], "refusals": refusals, "merged_row": merged_row}


MERGED = {"sums": [], "merged_row": [1],
          "refusals": [{"unit_id": "u01", "rule_id": "", "relation": "sum_mismatch",
                        "reason": "sum_over_merged_cells", "field": "weight"}]}


def _bound_function(name, scope):
    source = (ROOT / "scripts" / "pipeline.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "bound_pipeline_" + name, "exec"), scope)
    return scope[name]


def observe_printed():
    """_load_corpus executed with the scope the sealer gives it (tools/ordinary_final_run.py)."""
    load = _bound_function("_load_corpus", dict(Path=Path, text_extract=text_extract))
    err = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="shimmer_layers_load_") as d:
        build_docx(Path(d) / "tracked.docx", TRACKED_BODY)
        (Path(d) / "plain.md").write_text("# Plain\n\nText.\n", encoding="utf-8")
        with contextlib.redirect_stderr(err):
            docs = load(Path(d))
    lines = [ln.strip() for ln in err.getvalue().splitlines() if ln.strip()]
    return {"headers": [ln for ln in lines if ln.startswith("[text_extract] layers of")],
            "insertion_line": any(ln.startswith("- %s: read, 2 found, 1 author(s)" % docx_layers.INSERTIONS)
                                  for ln in lines),
            "records": {d["name"]: document_layers.is_record(d.get("layer_record")) for d in docs}}


# A plain-text file carries the text reader's own record (format "text", lane/reader-pdf-html).
PRINTED = {"headers": ["[text_extract] layers of plain.md (text):",
                       "[text_extract] layers of tracked.docx (docx):"],
           "insertion_line": True, "records": {"plain.md": True, "tracked.docx": True}}


def observe_summary():
    import absence_prediction
    import localization
    import run_context
    write = _bound_function("write_deliverables_run_summary", dict(
        localization=localization, Path=Path, datetime=datetime, timezone=timezone, json=json,
        absence_prediction=absence_prediction, run_context_mod=run_context))
    with tempfile.TemporaryDirectory(prefix="shimmer_layers_summary_") as d:
        path = build_docx(Path(d) / "skipped.docx", SKIPPED_BODY, parts=SKIPPED_PARTS)
        doc = {"id": "skipped", "name": "skipped.docx", "layer_record": text_extract.layer_record(path)}
        out = {}
        for language in ("en", "tr"):
            text = write(Path(d) / language / "deliverables", [doc], {}, total_cost_usd=0.0,
                         task="review", output_language=language).read_text(encoding="utf-8")
            section = text.split(localization.text("## Layers read", language), 1)
            out[language] = [ln.strip() for ln in section[1].strip().splitlines()[:3]] if len(section) == 2 else []
    return out


SUMMARY = {"en": ["- skipped.docx (docx):", "- main text: read, 2 found", "- tracked insertions: read, 0 found"],
           "tr": ["- skipped.docx (docx):", "- ana metin: okundu, 2 adet", "- izlenen eklemeler: okundu, 0 adet"]}


# ---------------------------------------------------------------------------
# neutralisations

def tracked_not_read():
    stack = contextlib.ExitStack()
    stack.enter_context(patch.object(docx_layers, "INSERTION_TAGS", {}))
    stack.enter_context(patch.object(docx_layers, "DELETION_TAGS", {}))
    return stack


def comments_not_read():
    return patch.object(docx_layers, "COMMENTS_PART", "word/absent.xml")


def notes_not_read():
    stack = contextlib.ExitStack()
    stack.enter_context(patch.object(docx_layers, "FOOTNOTES_PART", "word/absent.xml"))
    stack.enter_context(patch.object(docx_layers, "ENDNOTES_PART", "word/absent.xml"))
    return stack


def skipped_not_counted():
    return patch.object(docx_layers, "SKIPPED", ())


def merged_not_marked():
    return patch.object(document_layers, "merged_note", lambda columns: "")


def record_not_printed():
    return patch.object(text_extract, "print_layer_record", lambda name, record, file=None: None)


def summary_section_dropped():
    return patch.object(document_layers, "summary_lines", lambda docs: [])


# ---------------------------------------------------------------------------

class DocumentLayersChecks(unittest.TestCase):
    evidence = []
    group = None

    def prove(self, name, observe, expected, neutralise):
        result = prove_effect(name=name, validate=lambda: True, observe=observe,
                              check=lambda: ("PASS" if observe() == expected else "FAIL", name),
                              neutralise=neutralise)
        DocumentLayersChecks.evidence.append(result)

    def test_A_tracked_changes_apart_with_author_and_date(self):
        self.prove("docx_tracked_changes_apart", observe_tracked, TRACKED, tracked_not_read)

    def test_B_comments_with_anchor(self):
        self.prove("docx_comments_with_author_and_anchor", observe_notes, NOTES, comments_not_read)

    def test_B_footnotes_and_endnotes(self):
        self.prove("docx_footnotes_and_endnotes", observe_notes, NOTES, notes_not_read)

    def test_C_skipped_parts_counted(self):
        self.prove("docx_skipped_parts_counted", observe_skipped, SKIPPED, skipped_not_counted)

    def test_D_sum_over_merged_cells_refused(self):
        self.prove("docx_merged_cells_sum_refused", observe_merged, MERGED, merged_not_marked)

    def test_E_record_printed_by_load_corpus(self):
        self.prove("layer_record_printed", observe_printed, PRINTED, record_not_printed)

    def test_E_record_in_run_summary(self):
        self.prove("layer_record_in_run_summary", observe_summary, SUMMARY, summary_section_dropped)


GROUPS = {"A": ("test_A_",), "B": ("test_B_",), "C": ("test_C_",), "D": ("test_D_",), "E": ("test_E_",)}
DETAILS = {
    "A": "tracked insertions and deletions (moves too) read apart with author and date; main text accepted",
    "B": "comments with author, date and the text they span; footnotes and endnotes apart, separators out",
    "C": "a content control, a text box, a nested table and a header counted as present and not read, "
         "named in lost, none of their text in the main text",
    "D": "a column where a merged cell repeats its value is not summed by plan_calls and the refusal "
         "is recorded",
    "E": "the bound _load_corpus prints every document's layer record and the run summary writes it, "
         "in English and Turkish",
}


def run_check(letter):
    DocumentLayersChecks.evidence = []
    loader = unittest.defaultTestLoader
    names = [n for n in loader.getTestCaseNames(DocumentLayersChecks) if n.startswith(GROUPS[letter])]
    suite = unittest.TestSuite(DocumentLayersChecks(n) for n in names)
    result = unittest.TestResult()
    with contextlib.redirect_stdout(io.StringIO()):
        suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:200]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", "%d proof(s), each neutralise, fail, restore, pass: %s" % (result.testsRun, DETAILS[letter])


def main(argv=None):
    letters = (argv or sys.argv[1:]) or sorted(GROUPS)
    worst = 0
    for letter in letters:
        status, detail = run_check(letter)
        print(letter, status, detail)
        for proof in DocumentLayersChecks.evidence:
            print("  ", proof["name"], proof["status"])
            print("     mutated:", json.dumps(proof["mutated"], sort_keys=True)[:300])
        worst = worst or (status != "PASS")
    return int(worst)


if __name__ == "__main__":
    raise SystemExit(main())
