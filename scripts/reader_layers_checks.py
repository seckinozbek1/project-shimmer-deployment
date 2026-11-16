"""Gate checks 405 to 408: the PDF and HTML reader layers (#280), structure not recovered (#281 gap 1),
the replacement-character warning (gap 12) and the empty-input record (gap 13).

Every proof runs the real reader on a fixture built here and is proven by neutralise, fail, restore,
pass (scripts/effect_proof.py). The PDF proofs read through a stand-in for pypdf's reader (a page is
a dict with `extract_text`, its `/Annots` a list of dicts, as pypdf's objects are), so they need no
library; one more proof reads a PDF file built here with the real pypdf and is SKIPPED, saying so,
when pypdf is not installed. Fixtures carry no domain vocabulary.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import document_layers  # noqa: E402
import html_layers  # noqa: E402
import pdf_layers  # noqa: E402
import reader_report  # noqa: E402
import text_extract  # noqa: E402
from effect_proof import ProofFailure, prove_effect  # noqa: E402


def _verdict(ok, detail=""):
    return ("PASS", detail) if ok else ("FAIL", detail)


def _layer(record, name):
    return next((l for l in record["layers"] if l["name"] == name), None)


@contextlib.contextmanager
def _quiet():
    with contextlib.redirect_stderr(io.StringIO()) as err:
        yield err


# ---------- PDF fixtures --------------------------------------------------------------------------

class _Page(dict):
    def __init__(self, text, annots=()):
        super().__init__({"/Annots": list(annots)} if annots else {})
        self._text = text

    def extract_text(self):
        return self._text


class _Reader:
    def __init__(self, pages):
        self.pages = pages


def _annot(kind, author="", note="", date=""):
    out = {"/Subtype": "/" + kind}
    if author:
        out["/T"] = author
    if note:
        out["/Contents"] = note
    if date:
        out["/M"] = date
    return out


MARKED = _Reader([
    _Page("Item one\nQuantity: 4", [_annot("Highlight", "Reviewer A", "check this figure", "D:20261116"),
                                     _annot("Popup"), _annot("Link")]),
    _Page("Item two\nQuantity: 5", [_annot("Text", "Reviewer B", "a margin note"),
                                     _annot("StrikeOut", "Reviewer A")]),
])
SCANNED = _Reader([_Page(""), _Page("   ")])
PART_SCANNED = _Reader([_Page("Item one"), _Page("")])


def _pdf_string(text):
    return "(" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def build_pdf(pages) -> bytes:
    """A PDF file: pages is [(text or None, [(kind, author, note)])]; text None is a page with no
    text layer. Written by hand so the fixture needs no PDF library."""
    objects = {1: "<< /Type /Catalog /Pages 2 0 R >>", 3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
    kids, n = [], 4
    for text, annots in pages:
        page_no, content_no, n = n, n + 1, n + 2
        refs = []
        for kind, author, note in annots:
            objects[n] = ("<< /Type /Annot /Subtype /%s /Rect [72 700 172 720] /T %s /Contents %s /M (D:20261116120000) >>"
                          % (kind, _pdf_string(author), _pdf_string(note)))
            refs.append("%d 0 R" % n)
            n += 1
        stream = ("BT /F1 12 Tf 72 740 Td %s Tj ET" % _pdf_string(text)) if text is not None else "q Q"
        objects[content_no] = "<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        objects[page_no] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >>"
                            " /Contents %d 0 R%s >>" % (content_no, (" /Annots [%s]" % " ".join(refs)) if refs else ""))
        kids.append("%d 0 R" % page_no)
    objects[2] = "<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(kids), len(kids))
    out, offsets = bytearray(b"%PDF-1.4\n"), {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += ("%d 0 obj\n%s\nendobj\n" % (number, objects[number])).encode("latin-1")
    xref = len(out)
    size = max(objects) + 1
    out += ("xref\n0 %d\n0000000000 65535 f \n" % size).encode("latin-1")
    for number in range(1, size):
        out += ("%010d 00000 n \n" % offsets[number]).encode("latin-1")
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)).encode("latin-1")
    return bytes(out)


# ---------- 405: PDF annotations with author, scans, a missing library, structure ----------------

def _observe_marked():
    reading = pdf_layers.read_reader(MARKED)
    return {"record": reading.record, "items": [[i["kind"], i["author"], i["note"], i["page"]] for i in reading.items]}


def _check_marked():
    o = _observe_marked()
    ann = _layer(o["record"], pdf_layers.ANNOTATIONS)
    covered = _layer(o["record"], pdf_layers.COVERED)
    ok = (ann is not None and ann["read"] and ann["count"] == 3 and ann["authors"] == 2
          and ["Highlight", "Reviewer A", "check this figure", 1] in o["items"]
          and ["Text", "Reviewer B", "a margin note", 2] in o["items"]
          and not any(i[0] in ("Popup", "Link") for i in o["items"])
          and covered is not None and covered["count"] == 2 and pdf_layers.COVERED in o["record"]["lost"])
    return _verdict(ok, "annotations read with author and note; highlighted words lost")


def _observe_scanned():
    full = pdf_layers.read_reader(SCANNED).record
    part = pdf_layers.read_reader(PART_SCANNED).record
    return {"full": full, "part": part}


def _check_scanned():
    o = _observe_scanned()
    main = _layer(o["full"], pdf_layers.MAIN)
    pages = _layer(o["part"], pdf_layers.PAGES)
    ok = (main is not None and not main["read"] and main["note"] == pdf_layers.NOTE_NO_TEXT_LAYER
          and pdf_layers.MAIN in o["full"]["lost"]
          and pages is not None and pages["count"] == 1 and pdf_layers.PAGES in o["part"]["lost"]
          and _layer(o["part"], pdf_layers.MAIN)["read"])
    return _verdict(ok, "a scan has no main text; a page with no text layer is lost")


def _observe_missing_library():
    with patch.dict(sys.modules, {"pypdf": None}), _quiet() as err:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.pdf"
            path.write_bytes(b"%PDF-1.4\n")
            pages = text_extract.extract_pages(path)
            record = text_extract.layer_record(path)
    return {"pages": pages, "record": record, "warned": "pypdf" in err.getvalue()}


def _check_missing_library():
    o = _observe_missing_library()
    main = _layer(o["record"] or {"layers": []}, pdf_layers.MAIN)
    ok = (o["pages"] == [] and main is not None and not main["read"] and main["note"] == pdf_layers.NOTE_LIBRARY
          and pdf_layers.MAIN in o["record"]["lost"] and pdf_layers.ANNOTATIONS in o["record"]["lost"] and o["warned"])
    return _verdict(ok, "a missing pypdf is recorded as main text and annotations lost")


def _observe_pdf_structure():
    return pdf_layers.read_reader(MARKED).record


def _check_pdf_structure():
    record = _observe_pdf_structure()
    layer = _layer(record, pdf_layers.STRUCTURE)
    return _verdict(layer is not None and not layer["read"] and layer["note"].startswith("structure not recovered")
                    and pdf_layers.STRUCTURE in record["lost"], "PDF structure not recovered, visibly")


def _old_reader(reader):
    pages = [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
    return pdf_layers.Reading(pages=pages, record={"format": "pdf", "layers": [
        {"name": pdf_layers.MAIN, "read": True, "count": sum(len(t) for _, t in pages), "authors": 0, "note": ""}],
        "lost": []})


def _real_pdf():
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        marked, scan = Path(tmp) / "marked.pdf", Path(tmp) / "scan.pdf"
        marked.write_bytes(build_pdf([("Item one", [("Text", "Reviewer A", "a note"), ("Highlight", "Reviewer B", "")])]))
        scan.write_bytes(build_pdf([(None, [])]))
        with _quiet():
            text = text_extract.extract_text(marked)
            reading = pdf_layers.read(marked)
            scan_text = text_extract.extract_text(scan)
            scan_record = text_extract.layer_record(scan)
    return {"text": text, "items": [[i["kind"], i["author"], i["note"]] for i in reading.items],
            "scan_text": scan_text, "scan_lost": scan_record["lost"]}


def _check_real_pdf():
    o = _real_pdf()
    ok = ("Item one" in o["text"] and ["Text", "Reviewer A", "a note"] in o["items"]
          and ["Highlight", "Reviewer B", ""] in o["items"] and not o["scan_text"].strip()
          and pdf_layers.MAIN in o["scan_lost"])
    return _verdict(ok, "a real PDF's annotations and a page with no text layer")


def check_405():
    proofs = [
        ("pdf annotations with author", _observe_marked, _check_marked,
         lambda: patch.object(pdf_layers, "_annotations", lambda page, page_no: [])),
        ("pdf scan, no text layer", _observe_scanned, _check_scanned,
         lambda: patch.object(pdf_layers, "read_reader", _old_reader)),
        ("pypdf missing", _observe_missing_library, _check_missing_library,
         lambda: patch.object(pdf_layers, "_unread", lambda note: {"format": "pdf", "layers": [], "lost": []})),
        ("pdf structure not recovered", _observe_pdf_structure, _check_pdf_structure,
         lambda: patch.object(pdf_layers, "structure_layers", lambda: [])),
    ]
    skipped = ""
    try:
        import pypdf  # noqa: F401
        proofs.append(("real pdf file", _real_pdf, _check_real_pdf,
                       lambda: patch.object(pdf_layers, "read_reader", _old_reader)))
    except ImportError:
        skipped = "; the real-file proof is SKIPPED: pypdf is not installed here"
    return _run(proofs, "PDF annotations read with author and note, a scan, a missing pypdf and the structure "
                        "recorded as lost" + skipped)


# ---------- 406: HTML insertions and deletions, headings and tables, structure ------------------

MARKS = {"insert_elements": ["ins"], "delete_elements": ["del"], "insert_classes": ["ice-ins"],
         "delete_classes": ["ice-del"], "author_attributes": ["data-author", "data-username"],
         "date_attributes": ["datetime", "data-time"]}

TRACKED = """<html><head><title>Ignored title</title><script>var x = 1;</script></head><body>
<h1>Price list</h1>
<p>Issued by: Desk one</p>
<h2>Item one</h2>
<p>Quantity: <ins data-author="Writer A" datetime="2026-11-01">4</ins><del data-author="Writer B">5</del> box</p>
<p>Note line: <span class="ice-del" data-username="Writer C" data-time="1700000000">old words</span>
<span class="ice-ins" data-username="Writer C">new words</span></p>
<h2>Item two</h2>
<table><tr><th>Line</th><th>Total</th></tr><tr><td>first</td><td>12</td></tr><tr><td>second</td><td>13</td></tr></table>
</body></html>"""


def _observe_tracked():
    reading = html_layers.read_text(TRACKED, MARKS)
    return {"text": reading.text, "record": reading.record,
            "items": [[i["layer"], i["text"], i["author"], i["date"]] for i in reading.items]}


def _check_tracked():
    o = _observe_tracked()
    ins, dels = _layer(o["record"], html_layers.INSERTIONS), _layer(o["record"], html_layers.DELETIONS)
    ok = ("Quantity: 4 box" in o["text"] and "5" not in o["text"].split("Quantity:")[1].split("\n")[0]
          and "new words" in o["text"] and "old words" not in o["text"]
          and ["insertion", "4", "Writer A", "2026-11-01"] in o["items"]
          and ["deletion", "5", "Writer B", ""] in o["items"]
          and ["deletion", "old words", "Writer C", "1700000000"] in o["items"]
          and ins["count"] == 2 and ins["authors"] == 2 and dels["count"] == 2 and dels["authors"] == 2)
    return _verdict(ok, "insertions in, deletions out, each apart with author and date")


def _observe_units():
    import pairing_map
    text = html_layers.read_text(TRACKED, MARKS).text
    return {"text": text, "units": [u["unit_id"] for u in pairing_map.split_units(text, document_id="d")]}


def _check_units():
    o = _observe_units()
    ok = (o["text"].startswith("# Price list") and "\n## Item one\n" in o["text"]
          and "| Line | Total |\n|---|---|\n| first | 12 |\n| second | 13 |" in o["text"]
          and "var x" not in o["text"] and "Ignored title" not in o["text"]
          and [u for u in o["units"] if not u.startswith("u00")] == ["u01-item-one", "u02-item-two"])
    return _verdict(ok, "headings and a table mapped to the unit structure")


def _observe_html_structure():
    flat = html_layers.read_text("<html><body><p>One paragraph.</p><p>Two.</p></body></html>", MARKS).record
    nested = html_layers.read_text("<table><tr><td>a<table><tr><td>b</td></tr></table></td></tr></table>", MARKS)
    return {"flat": flat, "nested": nested.record, "nested_text": nested.text,
            "headed": html_layers.read_text(TRACKED, MARKS).record}


def _check_html_structure():
    o = _observe_html_structure()
    layer = _layer(o["flat"], html_layers.STRUCTURE)
    nested = _layer(o["nested"], html_layers.NESTED)
    ok = (layer is not None and not layer["read"] and layer["note"].startswith("structure not recovered")
          and html_layers.STRUCTURE in o["flat"]["lost"] and html_layers.STRUCTURE not in o["headed"]["lost"]
          and nested is not None and nested["count"] == 1 and "a b" in o["nested_text"])
    return _verdict(ok, "no heading and no table: structure not recovered; a nested table flattened and counted")


def check_406():
    return _run([
        ("html insertions and deletions", _observe_tracked, _check_tracked,
         lambda: patch.object(html_layers._Reader, "_role", lambda self, tag, attrs: "skip" if tag in html_layers.SKIPPED else "")),
        ("html headings mapped", _observe_units, _check_units,
         lambda: patch.object(html_layers, "HEADINGS", {})),
        ("html tables mapped", _observe_units, _check_units,
         lambda: patch.object(html_layers, "_table_text", lambda rows: " ".join(" ".join(r) for r in rows))),
        ("html structure not recovered", _observe_html_structure, _check_html_structure,
         lambda: patch.object(html_layers, "structure_layers", lambda headings, tables: [])),
    ], "HTML insertions and deletions told apart with author and date, headings and tables as units, "
       "structure not recovered and nested tables recorded")


# ---------- 407: a file not valid UTF-8 is warned above the declared share ----------------------

def _observe_encoding(settings=None):
    with tempfile.TemporaryDirectory() as tmp:
        bad, good, html = Path(tmp) / "latin.txt", Path(tmp) / "clean.txt", Path(tmp) / "latin.html"
        bad.write_bytes(("café crème " * 40).encode("latin-1"))
        good.write_text("plain text " * 40, encoding="utf-8")
        html.write_bytes(("<p>café " * 40 + "</p>").encode("latin-1"))
        config = Path(tmp) / "document_reader.json"
        if settings is not None:
            config.write_text(json.dumps(settings), encoding="utf-8")
        target = config if settings is not None else text_extract.READER_SETTINGS
        with patch.object(text_extract, "READER_SETTINGS", target), _quiet() as err:
            for path in (bad, good, html):
                text_extract.extract_text(path)
            out = {p.name: text_extract.layer_record(p)["lost"] for p in (bad, good, html)}
        out["warned"] = "'latin.txt' (text): not read: encoding" in err.getvalue()
    return out


def _observe_encoding_all():
    return {"declared": _observe_encoding(),
            "high": _observe_encoding({"replacement_character_share_above": 0.9}),
            "undeclared": _observe_encoding({})}


def _check_encoding():
    o = _observe_encoding_all()
    shipped = json.loads(text_extract.READER_SETTINGS.read_text(encoding="utf-8"))
    ok = (isinstance(shipped.get("replacement_character_share_above"), (int, float))
          and o["declared"]["latin.txt"] == ["encoding"] and o["declared"]["clean.txt"] == []
          and o["declared"]["latin.html"][-1:] == ["encoding"] and o["declared"]["warned"]
          and o["high"]["latin.txt"] == [] and o["undeclared"]["latin.txt"] == ["encoding"]
          and o["undeclared"]["clean.txt"] == ["encoding"])
    return _verdict(ok, "replacement share above the declared threshold is warned and recorded")


def check_407():
    return _run([("replacement characters", _observe_encoding_all, _check_encoding,
                  lambda: patch.object(text_extract, "_encoding_layers", lambda text: []))],
                "a text or HTML file not valid UTF-8 is warned and recorded above the share declared in "
                "config/document_reader.json; with no threshold declared it says the encoding was not checked")


# ---------- 408: an empty input is recorded in the run and in the report ------------------------

def _observe_empty():
    import pipeline
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        corpus = tmp / "operational"
        corpus.mkdir()
        (corpus / "scan.pdf").write_bytes(b"%PDF-1.4\n")
        (corpus / "blank.txt").write_text("  \n", encoding="utf-8")
        (corpus / "good.html").write_text("<h1>Title</h1><h2>Item one</h2><p>Quantity: 4</p>", encoding="utf-8")
        real_read = pdf_layers.read
        reader_report._SEEN.clear()
        with patch.object(pdf_layers, "read", lambda path, open_reader=None: real_read(path, lambda p: SCANNED)), \
                _quiet() as err:
            docs = pipeline._load_corpus(corpus)
            audit = reader_report.write(tmp / "run" / "audit")
            summaries = {}
            for language in ("en", "tr"):
                path = pipeline.write_deliverables_run_summary(
                    tmp / "run" / "deliverables", docs, {}, total_cost_usd=0.0, task="review", output_language=language)
                # The generated time differs on every call, so it is no part of the observation.
                summaries[language] = "\n".join(line for line in Path(path).read_text(encoding="utf-8").splitlines()
                                                if not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:", line))
    return {"docs": [d["name"] for d in docs], "warned": err.getvalue().count("EMPTY INPUT"),
            "empty": [[r["name"], r["reason"]] for r in audit["empty_inputs"]],
            "documents": [r["name"] for r in audit["documents"]],
            "summary": summaries["en"], "summary_tr": summaries["tr"]}


def _check_empty():
    o = _observe_empty()
    en, tr = o["summary"], o["summary_tr"]
    ok = (o["docs"] == ["good.html"] and o["warned"] == 2
          and ["scan.pdf", pdf_layers.NOTE_NO_TEXT_LAYER] in o["empty"]
          and ["blank.txt", reader_report.NO_TEXT] in o["empty"] and o["documents"] == ["good.html"]
          and "## Empty input" in en
          and "- scan.pdf (operational): empty input, not reviewed; " + pdf_layers.NOTE_NO_TEXT_LAYER in en
          and "## What the reader read" in en and "### good.html (operational)" in en
          and "- headings: read, 2 found, 0 author(s)" in en
          and "empty input" not in tr and "boş girdi" in tr and "not read" not in tr and "okundu" in tr)
    return _verdict(ok, "an empty input is warned, written to audit/reader_layers.json and to _run_summary.md")


def check_408():
    return _run([("empty input", _observe_empty, _check_empty,
                  lambda: patch.object(reader_report, "note", lambda where, path, text: None))],
                "a scan with no text layer and a blank file are EMPTY INPUT in the run (a WARN line, "
                "audit/reader_layers.json) and in _run_summary.md, in English and Turkish; read documents "
                "carry their layer record")


# ---------- runner --------------------------------------------------------------------------------

def _run(proofs, detail):
    for name, observe, check, neutralise in proofs:
        try:
            prove_effect(name=name, validate=lambda: True, observe=observe, check=check, neutralise=neutralise)
        except ProofFailure as e:
            return "FAIL", "%s: %s" % (name, e.category)
    return "PASS", "%d proof(s): %s" % (len(proofs), detail)


def check():
    return [check_405(), check_406(), check_407(), check_408()]


if __name__ == "__main__":
    for number, (status, detail) in zip((405, 406, 407, 408), check()):
        print(number, status, detail)
