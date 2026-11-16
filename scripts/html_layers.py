"""The HTML reader's layers (#280 HTML part, #281 gap 1).

An HTML file is read with the standard library's parser (no optional library to be missing)
into the form the rest of the pipeline reads (docs/INPUT_FORMAT.md section 2): an `<h1>` to
`<h6>` heading as a `#` line, block elements as paragraphs apart by a blank line, a `<br>` as a
line break, a list item as a `- ` line, and a table as `|` rows where it stands, its first row
the header. As for a .docx, a level-1 heading used more than once is a section level, so every
heading moves down one; a `<title>` is the document's title only when the body has no `<h1>`.
Scripts, styles and the head's other content are not text.

Insertions and deletions are told apart from the main text, by the markup declared in
config/document_reader.json (`<ins>` and `<del>`, and class tokens of common track-change
editors) with an author and a date read from the declared attributes where present. The main
text stands as with every change accepted, as a .docx is read: an insertion's words are in it,
a deletion's are not. Each change is also returned apart (`items`) with its author and date.

The layer record (scripts/document_layers.py) counts the main text's characters, the
insertions, the deletions, the headings and the tables; a table inside a table cell is
flattened into that cell's text and counted as lost; and a document with no heading and no
table says its structure was not recovered, since it is then one unit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

FORMAT = "html"
BLOCKS = frozenset(("p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "blockquote",
                    "pre", "section", "article", "header", "footer", "ul", "ol", "dl", "dt", "dd", "hr",
                    "figure", "figcaption", "address", "main", "nav", "aside", "form", "fieldset", "body",
                    "caption", "details", "summary"))
VOID = frozenset(("br", "img", "hr", "meta", "link", "input", "area", "base", "col", "embed", "param",
                  "source", "track", "wbr"))
SKIPPED = frozenset(("script", "style", "head", "template", "noscript"))
HEADINGS = {"h%d" % n: n for n in range(1, 7)}
_SPACE = re.compile(r"\s+")

MARK_KEYS = ("insert_elements", "delete_elements", "insert_classes", "delete_classes",
             "author_attributes", "date_attributes")

NOTE_UNDECLARED = "no track-change markup is declared, so changes were not told apart from the main text"
NOTE_INSERTIONS ="kept in the main text, as with every change accepted"
NOTE_DELETIONS = "left out of the main text, as with every change accepted"
NOTE_NESTED = "a table inside a table cell is flattened into that cell's text"
NOTE_STRUCTURE = "structure not recovered: no heading or table element was found, so the document is one unit"

MAIN, INSERTIONS, DELETIONS, HEADINGS_LAYER, TABLES, NESTED, STRUCTURE = (
    "main text", "insertions", "deletions", "headings", "tables", "nested tables", "structure")


@dataclass
class Reading:
    text: str = ""
    record: dict = field(default_factory=dict)
    items: list = field(default_factory=list)   # [{"layer": "insertion"|"deletion", "text", "author", "date"}]


class _Reader(HTMLParser):
    def __init__(self, marks):
        super().__init__(convert_charrefs=True)
        self.marks = {key: tuple(marks.get(key) or ()) for key in MARK_KEYS}
        self.blocks = []          # (kind, value): ("p", text) | ("h", (level, text)) | ("table", rows)
        self.buf = []             # the current paragraph's pieces
        self.stack = []           # [(tag, role)] role: "ins" | "del" | "skip" | "pre" | ""
        self.changes = []         # open change items, innermost last
        self.items = []
        self.tables = []          # open tables: {"rows": [[cell]], "row": [..] | None, "cell": [..] | None}
        self.heading = None       # open heading level
        self.title = []
        self.in_title = False
        self.nested = 0
        self.table_count = 0

    # -- state ---------------------------------------------------------------------------------
    def _deleting(self):
        return any(role == "del" for _, role in self.stack)

    def _skipping(self):
        return any(role == "skip" for _, role in self.stack)

    def _pre(self):
        return any(role == "pre" for _, role in self.stack)

    def _sink(self):
        if self.tables and self.tables[0]["cell"] is not None:
            return self.tables[0]["cell"]
        return self.buf

    def _flush(self):
        if self.tables:
            return
        text = "".join(self.buf)
        self.buf = []
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(line for line in lines if line)
        if not text:
            return
        if self.heading is not None:
            self.blocks.append(("h", (self.heading, text.replace("\n", " "))))
        else:
            self.blocks.append(("p", text))

    def _role(self, tag, attrs):
        if tag in SKIPPED:
            return "skip"
        classes = set((attrs.get("class") or "").split())
        if tag in self.marks["insert_elements"] or classes & set(self.marks["insert_classes"]):
            return "ins"
        if tag in self.marks["delete_elements"] or classes & set(self.marks["delete_classes"]):
            return "del"
        return "pre" if tag == "pre" else ""

    def _first(self, attrs, names):
        return next((attrs[n].strip() for n in names if (attrs.get(n) or "").strip()), "")

    # -- parser callbacks ----------------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        attrs = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self.in_title = True
            return
        if self._skipping():
            if tag not in VOID:
                self.stack.append((tag, "skip"))
            return
        if tag == "br":
            self._sink().append("\n")
            return
        if tag == "table":
            if self.tables:
                self.nested += 1
                self.tables.append({"rows": [], "row": None, "cell": None, "nested": True})
            else:
                self._flush()
                self.table_count += 1
                self.tables.append({"rows": [], "row": None, "cell": None, "nested": False})
        elif self.tables and len(self.tables) == 1 and tag == "tr":
            self.tables[0]["row"] = []
        elif self.tables and len(self.tables) == 1 and tag in ("td", "th"):
            if self.tables[0]["row"] is None:
                self.tables[0]["row"] = []
            self.tables[0]["cell"] = []
        elif self.tables and (tag in ("td", "th", "tr") or tag in BLOCKS):
            self._sink().append(" ")
        elif tag in BLOCKS:
            self._flush()
            if tag in HEADINGS:
                self.heading = HEADINGS[tag]
            if tag == "li":
                self.buf.append("- ")
        if tag in VOID:
            return
        role = self._role(tag, attrs)
        self.stack.append((tag, role))
        if role in ("ins", "del"):
            self.changes.append({"layer": "insertion" if role == "ins" else "deletion", "text": [],
                                 "author": self._first(attrs, self.marks["author_attributes"]),
                                 "date": self._first(attrs, self.marks["date_attributes"])})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
            return
        if not any(t == tag for t, _ in self.stack):
            return   # a stray end tag closes nothing
        while self.stack:
            open_tag, role = self.stack.pop()
            if role in ("ins", "del") and self.changes:
                change = self.changes.pop()
                change["text"] = _SPACE.sub(" ", "".join(change["text"])).strip()
                self.items.append(change)
            if open_tag == tag:
                break
        if self._skipping():
            return
        if tag == "table" and self.tables:
            self._end_table()
        elif self.tables and len(self.tables) == 1 and tag in ("td", "th"):
            self._close_cell(self.tables[0])
        elif self.tables and len(self.tables) == 1 and tag == "tr":
            table = self.tables[0]
            self._close_cell(table)
            if table["row"]:
                table["rows"].append(table["row"])
            table["row"] = None
        elif tag in BLOCKS and not self.tables:
            self._flush()
            if tag in HEADINGS:
                self.heading = None

    def _end_table(self):
        table = self.tables.pop()
        if not self.tables:
            self._close_cell(table)
            if table["row"]:
                table["rows"].append(table["row"])
            if table["rows"]:
                self.blocks.append(("table", table["rows"]))

    def _close_cell(self, table):
        if table["cell"] is not None:
            if table["row"] is None:
                table["row"] = []
            table["row"].append(_SPACE.sub(" ", "".join(table["cell"])).strip())
            table["cell"] = None

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
            return
        if self._skipping():
            return
        text = data if self._pre() else _SPACE.sub(" ", data)
        for change in self.changes:
            change["text"].append(text)
        if not self._deleting():
            self._sink().append(text)

    def close(self):
        super().close()
        while self.stack:
            self.handle_endtag(self.stack[-1][0])
        while self.tables:
            self._end_table()
        self._flush()


def _table_text(rows):
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| %s |" % " | ".join(rows[0]), "|%s|" % "|".join("---" for _ in rows[0])]
    return "\n".join(out + ["| %s |" % " | ".join(r) for r in rows[1:]])


def _layer(name, read, count=0, authors=0, note=""):
    return {"name": name, "read": read, "count": count, "authors": authors, "note": note}


def structure_layers(headings, tables):
    """#281 gap 1: with no heading and no table the document is one unit, and the record says so."""
    return [] if headings or tables else [_layer(STRUCTURE, False, note=NOTE_STRUCTURE)]


def _authors(items):
    return len({i["author"] for i in items if i["author"]})


def read_text(raw: str, marks: dict) -> Reading:
    """Read HTML source text. `marks` is config/document_reader.json's `html_track_changes`."""
    reader = _Reader(marks)
    reader.feed(raw)
    reader.close()
    blocks = reader.blocks
    title = _SPACE.sub(" ", "".join(reader.title)).strip()
    h1 = sum(1 for kind, value in blocks if kind == "h" and value[0] == 1)
    if title and not h1:
        blocks = [("h", (1, title))] + blocks
    shift = 1 if h1 > 1 else 0
    parts = []
    for kind, value in blocks:
        if kind == "h":
            parts.append("#" * min(value[0] + shift, 6) + " " + value[1])
        elif kind == "table":
            parts.append(_table_text(value))
        else:
            parts.append(value)
    text = "\n\n".join(parts)
    ins = [i for i in reader.items if i["layer"] == "insertion"]
    dels = [i for i in reader.items if i["layer"] == "deletion"]
    headings = sum(1 for kind, _ in blocks if kind == "h")
    declared = reader.marks
    layers = [_layer(MAIN, True, len(text))]
    if declared["insert_elements"] or declared["insert_classes"]:
        layers.append(_layer(INSERTIONS, True, len(ins), _authors(ins), NOTE_INSERTIONS if ins else ""))
    else:
        layers.append(_layer(INSERTIONS, False, note=NOTE_UNDECLARED))
    if declared["delete_elements"] or declared["delete_classes"]:
        layers.append(_layer(DELETIONS, True, len(dels), _authors(dels), NOTE_DELETIONS if dels else ""))
    else:
        layers.append(_layer(DELETIONS, False, note=NOTE_UNDECLARED))
    layers += [_layer(HEADINGS_LAYER, True, headings),
              _layer(TABLES, True, reader.table_count)]
    if reader.nested:
        layers.append(_layer(NESTED, False, reader.nested, note=NOTE_NESTED))
    layers += structure_layers(headings, reader.table_count)
    record = {"format": FORMAT, "layers": layers, "lost": [l["name"] for l in layers if not l["read"]]}
    return Reading(text=text, record=record, items=reader.items)
