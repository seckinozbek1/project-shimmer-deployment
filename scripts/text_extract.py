"""Shared document text extraction (Pass C / INFRA-027).

One place that turns a file path into plain text for the whole pipeline, so the
corpus loader, embedding store, convention parser, date cascade, and adaptive
spawn all accept the SAME input-format family:

    .pdf  .docx  .html/.htm  .txt  .md  .rst  .log  .json

Heavy/optional libraries (pypdf, python-docx) are imported lazily: a missing
optional library degrades gracefully with a clear one-line warning and an empty
string, never a crash. HTML is read with the standard library's parser
(scripts/html_layers.py), so no library can be missing for it. Unsupported
extensions are a distinct signal (`is_supported` / `UnsupportedFormatError`) so
every caller WARNs and skips rather than silently dropping a file.

Each PDF, HTML and plain-text reading keeps a layer record (scripts/document_layers.py,
`layer_record(path)`, the last reading's by `last_layer_record`): the layers read and the ones lost (PDF annotations and the
structure not recovered, scripts/pdf_layers.py; HTML insertions, deletions, headings
and tables; a file not valid UTF-8 above the share declared in
config/document_reader.json). A record with anything lost is also a WARN line.
"""

from __future__ import annotations

import sys
from pathlib import Path

PLAINTEXT_EXTENSIONS = (".txt", ".md", ".rst", ".log", ".json")
PDF_EXTENSIONS = (".pdf",)
DOCX_EXTENSIONS = (".docx",)
HTML_EXTENSIONS = (".html", ".htm")
SUPPORTED_EXTENSIONS = (
    PLAINTEXT_EXTENSIONS + PDF_EXTENSIONS + DOCX_EXTENSIONS + HTML_EXTENSIONS
)


class UnsupportedFormatError(ValueError):
    """Raised by extract_text/extract_pages for an unrecognized extension."""


def is_supported(path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def is_corpus_file(path) -> bool:
    """A loadable corpus document: a supported extension whose name does NOT start
    with `_`. The `_`-prefix marks metadata (sidecars, manifests like
    `_corpus_ingest.json` or `_download_manifest.json`), never a corpus document. One
    predicate, applied at every corpus-intake site, so the loaders cannot disagree."""
    p = Path(path)
    return is_supported(p) and not p.name.startswith("_")


def warn_unsupported(path, *, where: str = "input") -> None:
    p = Path(path)
    print(
        f"[text_extract] WARN: unsupported file type "
        f"{(p.suffix.lower() or '(none)')!r} for {p.name!r} in {where}; skipping. "
        f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
        file=sys.stderr, flush=True,
    )


def _warn_missing_lib(lib: str, path) -> None:
    print(
        f"[text_extract] WARN: optional library {lib!r} is not installed; cannot "
        f"read {Path(path).name!r}. Install it (see requirements.txt) to enable "
        f"this format. Skipping for now.",
        file=sys.stderr, flush=True,
    )


def _warn_read_error(kind: str, path, err: Exception) -> None:
    print(f"[text_extract] WARN: could not read {kind} {Path(path).name!r}: {err}",
          file=sys.stderr, flush=True)


# The layer record of the last reading of each file (scripts/document_layers.py, #280): what was
# read and what was lost, kept by path so a caller that read a file can say so in its run.
_LAYER_RECORDS: dict = {}


def last_layer_record(path):
    """The layer record of this file's last reading (kept by every reader, a .docx's by
    `extract_layers`), or None when it has not been read. `layer_record` reads the file again."""
    return _LAYER_RECORDS.get(str(Path(path).resolve()))


def _keep_record(path, record) -> None:
    _LAYER_RECORDS[str(Path(path).resolve())] = record
    if record["lost"]:
        print(f"[text_extract] WARN: {Path(path).name!r} ({record['format']}): not read: "
              f"{', '.join(record['lost'])}", file=sys.stderr, flush=True)


# The reader's declared settings (#281 gaps 12, and the HTML track-change markup), read when used.
READER_SETTINGS = Path(__file__).resolve().parents[1] / "config" / "document_reader.json"
ENCODING = "encoding"
NOTE_ENCODING = "the file is not valid UTF-8, so characters were replaced and its text may be garbled"
NOTE_NO_THRESHOLD = "no replacement-character threshold is declared, so the encoding was not checked"


def _reader_settings() -> dict:
    import json
    try:
        return json.loads(READER_SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _encoding_layers(text) -> list:
    """Gap 12: a file read as UTF-8 whose replaced characters pass the declared share is lost."""
    share = _reader_settings().get("replacement_character_share_above")
    replaced = text.count("�")
    if not isinstance(share, (int, float)) or isinstance(share, bool):
        return [{"name": ENCODING, "read": False, "count": replaced, "authors": 0, "note": NOTE_NO_THRESHOLD}]
    if replaced and replaced / max(len(text), 1) > share:
        return [{"name": ENCODING, "read": False, "count": replaced, "authors": 0, "note": NOTE_ENCODING}]
    return []


def _extract_pdf_pages(path):
    import pdf_layers
    reading = pdf_layers.read(path)
    if reading.missing_library:
        _warn_missing_lib(reading.missing_library, path)
    elif reading.error is not None:
        _warn_read_error("PDF", path, reading.error)
    _keep_record(path, reading.record)
    return reading.pages


# A .docx is read as it would stand with every tracked change accepted. python-docx's own
# `.text` takes only a paragraph's direct w:r and w:hyperlink children, so text inside w:ins
# or w:moveTo was lost with no warning. Text inside w:del or w:moveFrom stays out, and so does
# an insertion later deleted (w:ins/w:del). A paragraph whose mark is deleted joins the next.
_ACCEPTED_CONTENT = ("w:r | w:hyperlink | w:ins/w:r | w:ins/w:hyperlink"
                     " | w:moveTo/w:r | w:moveTo/w:hyperlink")
_REMOVED_MARK = "w:pPr/w:rPr/w:del | w:pPr/w:rPr/w:moveFrom"
_REMOVED_ROW = "w:trPr/w:del"


# The reading keeps the document's structure in the form the rest of the pipeline reads
# (docs/INPUT_FORMAT.md section 2): a heading as `#` lines, paragraphs apart by a blank line, a
# table as `|` rows where it stands. Without it a whole .docx was one unit and its tables gave
# no figures. A heading is read from its OUTLINE LEVEL, on the paragraph or through its style's
# chain, never from a style's name, so it holds in every language. Word's levels run 0 to 8, and
# 9 is body text.
_OUTLINE_LEVEL = "w:pPr/w:outlineLvl/@w:val"
_BODY_LEVEL = 9
_MAX_STYLE_CHAIN = 16
_PARAGRAPH_GAP = "\n\n"


def _outline_level(paragraph):
    """The paragraph's outline level, or None for body text."""
    found = paragraph._p.xpath(_OUTLINE_LEVEL)
    style = paragraph.style
    for _ in range(_MAX_STYLE_CHAIN):
        if found or style is None:
            break
        found = style.element.xpath(_OUTLINE_LEVEL)
        style = style.base_style
    level = int(found[0]) if found else _BODY_LEVEL
    return level if level < _BODY_LEVEL else None


def _accepted_paragraphs(paragraphs) -> list:
    """[(paragraph, text)] as they stand accepted. A joined text keeps the paragraph whose mark
    survives, as Word does."""
    out, joined, last = [], "", None
    for paragraph in paragraphs:
        last = paragraph
        text = joined + "".join(e.text for e in paragraph._p.xpath(_ACCEPTED_CONTENT))
        joined = ""
        if paragraph._p.xpath(_REMOVED_MARK):
            joined = text
        else:
            out.append((paragraph, text))
    if joined:
        out.append((last, joined))
    return out


def _merged_positions(row) -> set:
    """The positions in python-docx's `row.cells` where a merged cell repeats its value: every
    position of a cell continuing a vertical merge, and every position after the first of a
    cell spanning columns. python-docx gives such a cell's text at each position, so a column
    sum over it counted one value more than once (issue #281 gap 14)."""
    out, position = set(), 0
    for tc in row._tr.tc_lst:
        span = tc.grid_span
        out.update(range(position, position + span) if tc.vMerge == "continue"
                   else range(position + 1, position + span))
        position += span
    return out


def _standing_rows(table):
    return [row for row in table.rows if not row._tr.xpath(_REMOVED_ROW)]


def _table_block(table) -> str:
    """A table as `|` rows, its first standing row the header. A row is one line, so a cell's
    paragraphs join with a space. A table with merged cells is followed by one line naming the
    columns where a merged cell repeats its value (document_layers.merged_note), so no sum is
    taken over them."""
    import document_layers
    rows, merged = [], set()
    for row in _standing_rows(table):
        cells = [" ".join(t for _, t in _accepted_paragraphs(cell.paragraphs)).replace("\n", " ")
                 for cell in row.cells]
        merged |= {p + 1 for p in _merged_positions(row) if p < len(cells)}
        rows.append("| %s |" % " | ".join(cells))
        if len(rows) == 1:
            rows.append("|%s|" % "|".join("---" for _ in cells))
    note = document_layers.merged_note(merged)
    return "\n".join(rows + ([note] if note and rows else []))


def docx_merged_cell_count(path) -> int:
    """How many cell positions repeat a merged cell's value in the tables the main text shows
    (the top-level tables, rows not deleted). 0 when the file cannot be read."""
    try:
        import docx
        document = docx.Document(str(path))
        return sum(len(_merged_positions(row)) for table in document.tables
                   for row in _standing_rows(table))
    except Exception:
        return 0


def _heading_marks(level, shift) -> str:
    return "#" * min(level + 1 + shift, 6) + " "


def _extract_docx(path) -> str:
    try:
        import docx  # python-docx
        from docx.table import Table
    except ImportError:
        _warn_missing_lib("python-docx", path)
        return ""
    try:
        document = docx.Document(str(path))
        blocks, waiting = [], []

        def flush():
            blocks.extend((text, _outline_level(p)) for p, text in _accepted_paragraphs(waiting))
            waiting.clear()

        for item in document.iter_inner_content():
            if isinstance(item, Table):
                flush()
                blocks.append((_table_block(item), None))
            else:
                waiting.append(item)
        flush()
        blocks = [(text, level) for text, level in blocks if text.strip()]
        # A level-1 heading is the title, and a later one starts no unit (INPUT_FORMAT section
        # 2), so a top level used more than once is a section level and every heading moves down
        # one. Measured: a document of Heading 1 sections otherwise stays one unit.
        shift = 1 if sum(level == 0 for _, level in blocks) > 1 else 0
        return _PARAGRAPH_GAP.join(
            text if level is None else _heading_marks(level, shift) + text.replace("\n", " ")
            for text, level in blocks)
    except Exception as e:
        _warn_read_error("DOCX", path, e)
        return ""


# A text file may open with a UTF-8 byte-order mark. Read as plain utf-8 the mark stays in
# the text as a character, so a first heading no longer reads as a heading and a
# conventions file yields no rules, silently.
TEXT_ENCODING = "utf-8-sig"


def _unread_record(fmt) -> dict:
    return {"format": fmt, "layers": [{"name": "main text", "read": False, "count": 0, "authors": 0,
                                       "note": "the file could not be read"}], "lost": ["main text"]}


def _with_encoding(record, text) -> dict:
    extra = _encoding_layers(text)
    record["layers"] += extra
    record["lost"] += [layer["name"] for layer in extra]
    return record


def _extract_html(path) -> str:
    """HTML read with the standard library's parser (scripts/html_layers.py): headings and
    tables mapped to the unit structure, insertions and deletions told apart (#280, #281 gap 1)."""
    try:
        raw = Path(path).read_text(encoding=TEXT_ENCODING, errors="replace")
    except Exception as e:
        _warn_read_error("HTML", path, e)
        _keep_record(path, _unread_record("html"))
        return ""
    import html_layers
    try:
        reading = html_layers.read_text(raw, _reader_settings().get("html_track_changes") or {})
    except Exception as e:
        _warn_read_error("HTML", path, e)
        _keep_record(path, _unread_record("html"))
        return ""
    _keep_record(path, _with_encoding(reading.record, raw))
    return reading.text


def _extract_plaintext(path) -> str:
    try:
        text = Path(path).read_text(encoding=TEXT_ENCODING, errors="replace")
    except Exception as e:
        _warn_read_error("text", path, e)
        _keep_record(path, _unread_record("text"))
        return ""
    _keep_record(path, _with_encoding(
        {"format": "text", "layers": [{"name": "main text", "read": True, "count": len(text), "authors": 0,
                                       "note": ""}], "lost": []}, text))
    return text


def extract_text(path) -> str:
    """Return the file's plain text. Returns '' if empty/unreadable or an
    optional library is missing. Raises UnsupportedFormatError for an
    unrecognized extension (callers should pre-filter with is_supported)."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in PLAINTEXT_EXTENSIONS:
        return _extract_plaintext(p)
    if ext in PDF_EXTENSIONS:
        return "\n".join(t for _, t in _extract_pdf_pages(p))
    if ext in DOCX_EXTENSIONS:
        return _extract_docx(p)
    if ext in HTML_EXTENSIONS:
        return _extract_html(p)
    raise UnsupportedFormatError(ext or "(no extension)")


def extract_layers(path) -> dict:
    """Every layer of the file, each apart, with its layer record (issue #280). A .docx is read
    layer by layer (docx_layers); every other format gives its main text only, and its record
    says that no other layer was looked for. Raises UnsupportedFormatError like extract_text."""
    p = Path(path)
    if p.suffix.lower() in DOCX_EXTENSIONS:
        import docx_layers
        layers = docx_layers.read_layers(p)
        _LAYER_RECORDS[str(p.resolve())] = layers["record"]
        return layers
    import document_layers
    _LAYER_RECORDS.pop(str(p.resolve()), None)
    main = extract_text(p)
    # A PDF, HTML or plain-text reading keeps its own record (pdf_layers, html_layers, the
    # encoding layer); a reader that keeps none gives the main text only, and says so.
    kept = last_layer_record(p)
    if kept is not None:
        return {"main": main, "record": kept}
    fmt = p.suffix.lower().lstrip(".") or "(none)"
    note = "" if p.suffix.lower() in PLAINTEXT_EXTENSIONS else "no other layer is looked for in this format"
    return {"main": main, "record": document_layers.record(fmt, [document_layers.layer(
        "main text", read=True, count=sum(1 for b in main.split("\n\n") if b.strip()), note=note)])}


def layer_record(path) -> dict:
    """The layer record of the file (document_layers), from a fresh reading."""
    return extract_layers(path)["record"]


def print_layer_record(name, record, *, file=None) -> None:
    """The run's printout of one document's layer record, on stderr beside the reader's other
    warnings."""
    import document_layers
    out = sys.stderr if file is None else file
    print(f"[text_extract] layers of {name} ({record['format']}):", file=out, flush=True)
    for line in document_layers.layer_record_lines(record):
        print("  " + line, file=out, flush=True)


def extract_pages(path):
    """Return [(page_no, text), ...]. PDFs yield their real pages; every other
    supported format yields a single (1, full_text) entry. Empty/unreadable
    files yield []. Raises UnsupportedFormatError for an unrecognized extension."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in PDF_EXTENSIONS:
        return [(n, t) for n, t in _extract_pdf_pages(p) if t]
    if ext in SUPPORTED_EXTENSIONS:
        text = extract_text(p)
        return [(1, text)] if text.strip() else []
    raise UnsupportedFormatError(ext or "(no extension)")
