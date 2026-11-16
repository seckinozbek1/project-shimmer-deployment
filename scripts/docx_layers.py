"""The layers of a .docx, each returned apart (issue #280, D-666; issue #281 gap 14, D-667).

`text_extract` reads a .docx as it would stand with every tracked change accepted: deletions
dropped, insertions kept, and no author or date for either. Comments, footnotes and endnotes
were not read at all, and a content control, a text box or a table inside a table was dropped
without a trace. This module reads the package parts directly (zipfile and ElementTree, no
optional library) and returns:

    main        the accepted text, from text_extract (the one reader of the main text)
    insertions  [{"text", "author", "date", "kind"}]  tracked insertions and moved-to text
    deletions   [{"text", "author", "date", "kind"}]  tracked deletions and moved-from text
    comments    [{"id", "text", "author", "date", "anchor"}]  anchor: the text the comment
                spans in the body (empty when it marks a point)
    footnotes   [{"id", "text"}]   separators excluded
    endnotes    [{"id", "text"}]
    skipped     {"content controls", "text boxes", "nested tables", "headers and footers"}
                counts of parts present and NOT read; each is named in the record's `lost`
    merged      count of table cell positions where a merged cell repeats its value
    record      the layer record (document_layers)

Content controls, text boxes, nested tables, headers and footers are counted, not read: their
full reading is listed for v1.1 (issue #281 item 14). A count never includes text.
"""
from __future__ import annotations

import zipfile
from xml.etree import ElementTree as ET

import document_layers

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
DOCUMENT_PART = "word/document.xml"
COMMENTS_PART = "word/comments.xml"
FOOTNOTES_PART = "word/footnotes.xml"
ENDNOTES_PART = "word/endnotes.xml"
# A footnote or endnote of one of these types is Word's own separator line, not a note.
_SEPARATOR_TYPES = {"separator", "continuationSeparator", "continuationNotice"}

# The layer names, as the record and the run summary show them.
MAIN = "main text"
INSERTIONS = "tracked insertions"
DELETIONS = "tracked deletions"
COMMENTS = "comments"
FOOTNOTES = "footnotes"
ENDNOTES = "endnotes"
CONTENT_CONTROLS = "content controls"
TEXT_BOXES = "text boxes"
NESTED_TABLES = "nested tables"
HEADERS_FOOTERS = "headers and footers"
MERGED_CELLS = "merged table cells"
MERGED_NOTE = "a sum over a column with merged cells is refused"
SKIPPED = (CONTENT_CONTROLS, TEXT_BOXES, NESTED_TABLES, HEADERS_FOOTERS)

# The tracked-change elements read as each layer, with the kind each is recorded as.
INSERTION_TAGS = {"ins": "insertion", "moveTo": "moved to"}
DELETION_TAGS = {"del": "deletion", "moveFrom": "moved from"}


def _w(tag):
    return "{%s}%s" % (W, tag)


def _attr(el, name):
    return el.get(_w(name)) or ""


def _local(el):
    return el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""


def _run_text(el, *, deleted=False):
    """The text under `el` in document order: w:t (w:delText for deleted text), a break as a
    line end; paragraphs apart by a line end."""
    want = "delText" if deleted else "t"
    parts = []
    for node in el.iter():
        name = _local(node)
        if name == want and node.text:
            parts.append(node.text)
        elif name in ("br", "cr"):
            parts.append("\n")
        elif name == "p" and parts and not parts[-1].endswith("\n"):
            parts.append("\n")
    return "".join(parts).strip()


def _read_part(archive, name):
    try:
        return ET.fromstring(archive.read(name))
    except KeyError:
        return None


def _tracked(body, tags, *, deleted):
    out = []
    for name, kind in tags.items():
        for el in body.iter(_w(name)):
            text = _run_text(el, deleted=deleted)
            if not text:
                continue  # a paragraph-mark or a row change carries no text
            out.append({"text": text, "author": _attr(el, "author"), "date": _attr(el, "date"),
                        "kind": kind})
    return out


def _anchors(body):
    """{comment id: the body text between its range start and end}, deleted text left out."""
    open_ids, anchors = [], {}

    def walk(el, deleted):
        name = _local(el)
        if name == "commentRangeStart":
            cid = _attr(el, "id")
            open_ids.append(cid)
            anchors.setdefault(cid, [])
        elif name == "commentRangeEnd":
            cid = _attr(el, "id")
            if cid in open_ids:
                open_ids.remove(cid)
        elif name == "t" and el.text and not deleted:
            for cid in open_ids:
                anchors[cid].append(el.text)
        for child in el:
            walk(child, deleted or name in DELETION_TAGS)

    walk(body, False)
    return {cid: "".join(parts).strip() for cid, parts in anchors.items()}


def _comments(archive, body):
    root = _read_part(archive, COMMENTS_PART)
    if root is None:
        return []
    anchors = _anchors(body)
    return [{"id": _attr(c, "id"), "text": _run_text(c), "author": _attr(c, "author"),
             "date": _attr(c, "date"), "anchor": anchors.get(_attr(c, "id"), "")}
            for c in root.iter(_w("comment"))]


def _notes(archive, part, tag):
    root = _read_part(archive, part)
    if root is None:
        return []
    return [{"id": _attr(n, "id"), "text": _run_text(n)}
            for n in root.iter(_w(tag)) if _attr(n, "type") not in _SEPARATOR_TYPES]


def _skipped(archive, body):
    """Counts of the parts the main-text reader does not take in."""
    counts = dict.fromkeys(SKIPPED, 0)

    def walk(el, in_cell, in_fallback):
        name = _local(el)
        if name == "sdt" and _run_text(el):
            counts[CONTENT_CONTROLS] += 1
        elif name == "txbxContent" and not in_fallback:
            # Word writes a text box twice, as DrawingML and as its VML fallback: count one.
            counts[TEXT_BOXES] += 1
        elif name == "tbl" and in_cell:
            counts[NESTED_TABLES] += 1
        for child in el:
            walk(child, in_cell or name == "tc", in_fallback or el.tag == "{%s}Fallback" % MC)

    walk(body, False, False)
    for name in archive.namelist():
        if name.startswith(("word/header", "word/footer")) and name.endswith(".xml"):
            part = _read_part(archive, name)
            if part is not None and _run_text(part):
                counts[HEADERS_FOOTERS] += 1
    return counts


def _merged_count(path):
    """Cell positions where a merged cell repeats its value, in the tables the main text shows."""
    import text_extract
    return text_extract.docx_merged_cell_count(path)


def read_layers(path):
    """Every layer of the .docx at `path`, each apart, with its layer record. A file that is not
    a readable package gives empty layers and a record that says so."""
    import text_extract
    main = text_extract.extract_text(path)
    try:
        with zipfile.ZipFile(str(path)) as archive:
            document = _read_part(archive, DOCUMENT_PART)
            if document is None:
                raise KeyError(DOCUMENT_PART)
            body = document.find(_w("body"))
            body = document if body is None else body
            layers = {"insertions": _tracked(body, INSERTION_TAGS, deleted=False),
                      "deletions": _tracked(body, DELETION_TAGS, deleted=True),
                      "comments": _comments(archive, body),
                      "footnotes": _notes(archive, FOOTNOTES_PART, "footnote"),
                      "endnotes": _notes(archive, ENDNOTES_PART, "endnote"),
                      "skipped": _skipped(archive, body)}
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError):
        return {"main": main, "insertions": [], "deletions": [], "comments": [], "footnotes": [],
                "endnotes": [], "skipped": {}, "merged": 0,
                "record": document_layers.record("docx", [
                    document_layers.layer(MAIN, read=bool(main.strip()), count=_blocks(main),
                                          note="" if main.strip() else "the package could not be read")])}
    layers["main"] = main
    layers["merged"] = _merged_count(path)
    layers["record"] = layer_record(layers)
    return layers


def _blocks(text):
    return sum(1 for block in (text or "").split("\n\n") if block.strip())


def _authors(rows):
    return len({r.get("author") for r in rows if r.get("author")})


def layer_record(layers):
    """The layer record built from the layers read."""
    rows = [document_layers.layer(MAIN, read=True, count=_blocks(layers["main"]))]
    for name, key in ((INSERTIONS, "insertions"), (DELETIONS, "deletions"), (COMMENTS, "comments")):
        rows.append(document_layers.layer(name, read=True, count=len(layers[key]),
                                          authors=_authors(layers[key])))
    rows.append(document_layers.layer(FOOTNOTES, read=True, count=len(layers["footnotes"])))
    rows.append(document_layers.layer(ENDNOTES, read=True, count=len(layers["endnotes"])))
    if layers.get("merged"):
        rows.append(document_layers.layer(MERGED_CELLS, read=True, count=layers["merged"],
                                          note=MERGED_NOTE))
    for name in SKIPPED:
        rows.append(document_layers.layer(name, read=False, count=layers["skipped"].get(name, 0)))
    return document_layers.record("docx", rows)
