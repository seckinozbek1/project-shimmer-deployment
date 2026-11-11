"""Shared document text extraction (Pass C / INFRA-027).

One place that turns a file path into plain text for the whole pipeline, so the
corpus loader, embedding store, convention parser, date cascade, and adaptive
spawn all accept the SAME input-format family:

    .pdf  .docx  .html/.htm  .txt  .md  .rst  .log  .json

Heavy/optional libraries (pypdf, python-docx, beautifulsoup4) are imported
lazily: a missing optional library degrades gracefully with a clear one-line
warning and an empty string, never a crash. Unsupported extensions are a
distinct signal (`is_supported` / `UnsupportedFormatError`) so every caller
WARNs and skips rather than silently dropping a file.
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


def _extract_pdf_pages(path):
    try:
        import pypdf
    except ImportError:
        _warn_missing_lib("pypdf", path)
        return []
    try:
        reader = pypdf.PdfReader(str(path))
        return [(i + 1, (pg.extract_text() or "")) for i, pg in enumerate(reader.pages)]
    except Exception as e:
        _warn_read_error("PDF", path, e)
        return []


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


def _table_block(table) -> str:
    """A table as `|` rows, its first standing row the header. A row is one line, so a cell's
    paragraphs join with a space."""
    rows = []
    for row in table.rows:
        if row._tr.xpath(_REMOVED_ROW):
            continue
        cells = [" ".join(t for _, t in _accepted_paragraphs(cell.paragraphs)).replace("\n", " ")
                 for cell in row.cells]
        rows.append("| %s |" % " | ".join(cells))
        if len(rows) == 1:
            rows.append("|%s|" % "|".join("---" for _ in cells))
    return "\n".join(rows)


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


def _extract_html(path) -> str:
    try:
        raw = Path(path).read_text(encoding=TEXT_ENCODING, errors="replace")
    except Exception as e:
        _warn_read_error("HTML", path, e)
        return ""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        _warn_missing_lib("beautifulsoup4", path)
        return ""
    try:
        soup = BeautifulSoup(raw, "html.parser")  # builtin parser; no lxml needed
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n")
    except Exception as e:
        _warn_read_error("HTML", path, e)
        return ""


def _extract_plaintext(path) -> str:
    try:
        return Path(path).read_text(encoding=TEXT_ENCODING, errors="replace")
    except Exception as e:
        _warn_read_error("text", path, e)
        return ""


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
