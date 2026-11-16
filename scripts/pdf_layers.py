"""The PDF reader's layers (#280 PDF part, #281 gaps 1 and 13).

A PDF is read page by page with pypdf, as before: the main text is each page's text layer.
Beside it this reader takes in the page annotations a reviewer leaves (sticky notes, free text,
highlights, underlines, strike-outs and the like) with their author (`/T`), note (`/Contents`)
and date (`/M`, else `/CreationDate`), and says in the layer record (scripts/document_layers.py)
what it could not take in:

- the main text, when pypdf is not installed, the file cannot be opened, or no page has a text
  layer (a scan: no text is recognised from images);
- the pages that have no text layer, when others do;
- the words under a highlight, underline, strike-out or squiggle: pypdf gives the marked area,
  not its words, so only the mark's note and author are read;
- the structure, when the page's text positions cannot be read (a reader with no text visitor,
  or no `pdf_layout` settings declared in config/document_reader.json): its text is then split
  as plain text (one unit unless the text itself has `#` lines).

D-668: when the positions are read, the layout is recovered from them (scripts/pdf_layout.py):
columns read one after another, running headers and footers set apart (kept in `items`, layer
`running`), tables written as `|` rows and headings as `#` lines by their size. Text set at an
angle and a table whose rows do not line up are kept as plain text and counted lost.

Pop-up windows, links and form fields are not reviewer marks and are not counted. Nothing here
decides anything; the record carries counts and fixed notes only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

FORMAT = "pdf"
NOT_MARKS = ("Popup", "Link", "Widget")
COVERING_MARKS = ("Highlight", "Underline", "StrikeOut", "Squiggly")

NOTE_LIBRARY = "the library pypdf is not installed"
NOTE_UNREADABLE = "the file could not be opened"
NOTE_NO_TEXT_LAYER = "no page has a text layer; the file may be a scan, and no text is recognised from images"
NOTE_PAGES = "these pages have no text layer; they may be scans, and no text is recognised from images"
NOTE_COVERED = "the words under a highlight are not recovered; its note and author are in the annotations"
NOTE_STRUCTURE = "structure not recovered: headings and tables are not read from a PDF, so its text is split as plain text"
NOTE_NO_SETTINGS = ("structure not recovered: no pdf_layout settings are declared in config/document_reader.json, "
                    "so its text is split as plain text")
NOTE_LAYOUT = "read from where the text is drawn: columns, running headers and footers, tables and headings by size"
NOTE_RUNNING = "set apart from the main text: lines repeated in the top or bottom margin of several pages"
NOTE_ROTATED = "text set at an angle is kept after its page's other text; its place in the reading order is not recovered"
NOTE_UNEVEN = "rows whose cells do not line up are kept as plain lines; the table is not recovered"

MAIN, PAGES, ANNOTATIONS, COVERED, STRUCTURE = (
    "main text", "pages without a text layer", "annotations", "highlighted passages", "structure")
LAYOUT, RUNNING, ROTATED, UNEVEN = ("layout", "running headers and footers", "text at an angle",
                                    "tables not recovered")


@dataclass
class Reading:
    pages: list = field(default_factory=list)      # [(page_no, text)] as text_extract returns them
    record: dict = field(default_factory=dict)
    items: list = field(default_factory=list)      # [{"layer", "page", "kind", "author", "note", "date"}]
    missing_library: str = ""
    error: Exception | None = None


def _layer(name, read, count=0, authors=0, note=""):
    return {"name": name, "read": read, "count": count, "authors": authors, "note": note}


def _record(layers):
    return {"format": FORMAT, "layers": layers, "lost": [l["name"] for l in layers if not l["read"]]}


def structure_layers():
    """#281 gap 1: a PDF's structure is never recovered, and the record says so."""
    return [_layer(STRUCTURE, False, note=NOTE_STRUCTURE)]


def _unread(note):
    return _record([_layer(MAIN, False, note=note), _layer(ANNOTATIONS, False, note=note)] + structure_layers())


def _object(value):
    """pypdf hands indirect references; a plain dict (a fixture) is its own object."""
    return value.get_object() if hasattr(value, "get_object") else value


def _string(value) -> str:
    value = _object(value)
    return "" if value is None else str(value)


def _annotations(page, page_no):
    found = []
    try:
        annots = _object(page.get("/Annots"))
    except Exception:
        annots = None
    for ref in annots or []:
        annot = _object(ref)
        try:
            kind = _string(annot.get("/Subtype")).lstrip("/")
        except Exception:
            continue
        if not kind or kind in NOT_MARKS:
            continue
        found.append({"layer": "annotation", "page": page_no, "kind": kind,
                      "author": _string(annot.get("/T")), "note": _string(annot.get("/Contents")),
                      "date": _string(annot.get("/M")) or _string(annot.get("/CreationDate"))})
    return found


def layout_settings():
    """config/document_reader.json `pdf_layout`, checked (pdf_layout.settings), or None."""
    import pdf_layout
    import text_extract
    return pdf_layout.settings(text_extract._reader_settings().get("pdf_layout"))


def _size_of(page):
    """(width, height) of the page's media box, or None."""
    try:
        box = page.mediabox
        return float(box.width), float(box.height)
    except Exception:
        pass
    try:
        box = [float(v) for v in _object(page.get("/MediaBox"))]
        return box[2] - box[0], box[3] - box[1]
    except Exception:
        return None


def fragments(page):
    """(text, positioned page or None): the page's text, and where each piece of it is drawn, from
    pypdf's text visitors (`visitor_text(text, cm, tm, font, size)` for the text and size,
    `visitor_operand_before` for the matrix at each show operator). None when the reader has no
    visitor or the page no media box: then no layout is recovered from that page."""
    found, pending = [], []
    shows = (b"Tj", b"TJ", b"'", b'"', "Tj", "TJ", "'", '"')

    def before(operator, _operands, cm, tm):
        # pypdf hands its text visitor a piece only when it flushes (at ET or a new line), and a
        # piece on the same line as the one before comes with a stale matrix; the matrix at the
        # first show operator since the last flush is where the piece is drawn
        if operator in shows and not pending:
            pending.append((list(cm), list(tm)))

    def visit(text, cm, tm, _font, size):
        if not text or not text.strip():
            return
        if pending:
            cm, tm = pending.pop()
        try:
            a, b, c, d, e, f = (float(v) for v in tm)
            ca, cb, cc, cd, ce, cf = (float(v) for v in cm)
        except Exception:
            return
        x = e * ca + f * cc + ce
        y = e * cb + f * cd + cf
        scale = (a * a + b * b) ** 0.5 * (ca * ca + cb * cb) ** 0.5
        found.append({"x": x, "y": y, "size": float(size or 0) * (scale or 1.0), "text": text,
                      "rotated": abs(b) > 1e-6 or abs(c) > 1e-6 or abs(cb) > 1e-6 or abs(cc) > 1e-6})

    try:
        text = page.extract_text(visitor_text=visit, visitor_operand_before=before) or ""
    except TypeError:
        return _plain_text(page), None
    except Exception:
        return "", None
    box = _size_of(page)
    # every character of the page text must have come with a position, or none is laid out:
    # the layout never drops what the plain reading holds
    if box is None or _letters("".join(f["text"] for f in found)) < _letters(text):
        return text, None
    for f in found:
        if f["size"] <= 0:
            f["size"] = 1.0
    return text, {"width": box[0], "height": box[1], "fragments": found}


def _letters(text):
    return sum(1 for ch in text if not ch.isspace())


def _plain_text(page):
    try:
        return page.extract_text() or ""
    except Exception:
        return ""


def read_reader(reader) -> Reading:
    """The layers of an open reader: anything with `.pages`, each page dict-like with
    `extract_text()`, as a pypdf.PdfReader is. With pypdf's text visitor and the declared
    `pdf_layout` settings, the layout is recovered from the text positions (D-668)."""
    pages, items, blank, positioned = [], [], 0, []
    for i, page in enumerate(reader.pages):
        text, placed = fragments(page)
        if not text.strip():
            blank += 1
        pages.append((i + 1, text))
        positioned.append(placed)
        items += _annotations(page, i + 1)
    structure, pages, running = _layout(pages, positioned)
    chars = sum(len(t) for _, t in pages)
    if pages and blank == len(pages):
        layers = [_layer(MAIN, False, note=NOTE_NO_TEXT_LAYER)]
    else:
        layers = [_layer(MAIN, True, chars)]
        if blank:
            layers.append(_layer(PAGES, False, blank, note=NOTE_PAGES))
    layers.append(_layer(ANNOTATIONS, True, len(items), len({a["author"] for a in items if a["author"]})))
    covering = [a for a in items if a["kind"] in COVERING_MARKS]
    if covering:
        layers.append(_layer(COVERED, False, len(covering),
                             len({a["author"] for a in covering if a["author"]}), NOTE_COVERED))
    layers += structure
    return Reading(pages=pages, record=_record(layers), items=items + running)


def _layout(pages, positioned):
    """(structure layers, pages, running items): the layout recovered when every page with text
    has its positions and the settings are declared; else the plain pages and the structure lost."""
    with_text = [placed for (_, text), placed in zip(pages, positioned) if text.strip()]
    if not with_text or any(p is None for p in with_text):
        return structure_layers(), pages, []
    s = layout_settings()
    if s is None:
        return [_layer(STRUCTURE, False, note=NOTE_NO_SETTINGS)], pages, []
    import pdf_layout
    blank = {"width": 1.0, "height": 1.0, "fragments": []}
    laid = pdf_layout.lay_out([p or blank for p in positioned], s)
    pages = [(n, laid["pages"][i] if positioned[i] is not None else text) for i, (n, text) in enumerate(pages)]
    found, lost = laid["found"], laid["lost"]
    layers = [_layer(LAYOUT, True, sum(1 for p in positioned if p is not None), note=NOTE_LAYOUT),
              _layer("columns", True, found["columns"]), _layer("headings", True, found["headings"]),
              _layer("tables", True, found["tables"]), _layer(RUNNING, True, found["running"], note=NOTE_RUNNING)]
    if lost["rotated"]:
        layers.append(_layer(ROTATED, False, lost["rotated"], note=NOTE_ROTATED))
    if lost["tables"]:
        layers.append(_layer(UNEVEN, False, lost["tables"], note=NOTE_UNEVEN))
    running = [{"layer": "running", "page": n, "kind": band, "author": "", "note": text, "date": ""}
               for n, band, text in laid["running"]]
    return layers, pages, running


def read(path, open_reader=None) -> Reading:
    """Read a PDF file. `open_reader(path)` defaults to pypdf.PdfReader; without pypdf the reading
    is empty and its record says so."""
    if open_reader is None:
        try:
            import pypdf
        except ImportError:
            return Reading(record=_unread(NOTE_LIBRARY), missing_library="pypdf")
        open_reader = lambda p: pypdf.PdfReader(str(p))  # noqa: E731
    try:
        return read_reader(open_reader(path))
    except Exception as e:
        return Reading(record=_unread(NOTE_UNREADABLE), error=e)
