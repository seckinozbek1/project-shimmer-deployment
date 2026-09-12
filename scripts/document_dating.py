"""Document dating cascade (genesis Part XXIV).

Resolves a publication date for each document via the cascade. Operator signal
first, then what the document says about itself, then the container. Every tier
is LOCAL: nothing about a document leaves the machine to date it.

  1. Filename date (operator-provided signal, authoritative). The FULL date is
     read first (YYYY-MM-DD, then YYYY-MM), then a bare year.
  2. Content: the full date the document states, then a numeric year scan.
     Supports both Western Arabic numerals (0-9) and Eastern Arabic numerals
     (٠-٩, U+0660-U+0669). Not truncated.
  3. PDF metadata creation/modification date (container-derived, low
     confidence because metadata is often a re-export artifact).

There is no web tier. It was removed, not made conditional: it decided which
documents got reviewed from a network result that can differ between runs over
the same bytes, and it sent the document's title off the machine.

An unresolved date is LOUD. It costs the document its place in the review set,
so it is named in the run record, served by a route, and shown in the console,
rather than being a silent disappearance.

Each record carries:
  date              : ISO date string or None
  date_source       : "filename" | "content" | "metadata" | "unresolved"
  date_confidence   : "high" (filename/content) | "low" (metadata/web) |
                      "uncertain" (multiple conflicting candidates)
  date_candidates   : list of all years found across all sources, populated
                      only when date_confidence == "uncertain"

Stores results in durable/learnings/document_dates.json (protected; INFRA-030).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import text_extract


_FILENAME_PATTERNS = [
    re.compile(r"(\d{4})[-_.](\d{2})[-_.](\d{2})"),  # YYYY-MM-DD / YYYY_MM_DD
    re.compile(r"(\d{4})[-_.](\d{2})\b"),             # YYYY-MM / YYYY_MM
    re.compile(r"\b(20\d{2})\b"),                     # bare year (2000-2099)
    re.compile(r"\b(19\d{2})\b"),                     # bare year (1900-1999)
]


_TEXT_DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
               r"September|October|November|December)\s+(\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(January|February|March|April|May|June|July|August|"
               r"September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b"),
    re.compile(r"\b(\d{4})\b"),  # last-resort bare year
]


_MONTHS = {m: i + 1 for i, m in enumerate([
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
])}


def _iso(year: int, month: int = 1, day: int = 1) -> str:
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return datetime(year, 1, 1).strftime("%Y-%m-%d")


def date_from_filename(filename: str) -> str | None:
    name = Path(filename).stem
    for i, pat in enumerate(_FILENAME_PATTERNS):
        m = pat.search(name)
        if m:
            try:
                if i == 0:
                    return _iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if i == 1:
                    return _iso(int(m.group(1)), int(m.group(2)))
                return _iso(int(m.group(1)))
            except ValueError:
                continue
    return None


def date_from_pdf_metadata(path: Path) -> tuple[str | None, str | None]:
    """Returns (iso_date, title_hint) using pypdf metadata."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        meta = reader.metadata or {}
    except Exception:
        return None, None
    title_hint = None
    try:
        title_hint = (meta.get("/Title") or "").strip() or None
    except Exception:
        title_hint = None
    raw = meta.get("/CreationDate") or meta.get("/ModDate")
    if not raw:
        return None, title_hint
    raw = str(raw)
    if raw.startswith("D:") and len(raw) >= 10:
        try:
            return _iso(int(raw[2:6]), int(raw[6:8]), int(raw[8:10])), title_hint
        except ValueError:
            return None, title_hint
    return None, title_hint


def date_from_text(text: str) -> str | None:
    """First full date the text states, in any of the supported shapes.

    Not truncated: the 3000-character cut this used to apply is what hid the
    device log's own dates (character 4179) from the cascade.
    """
    text = text or ""
    for i, pat in enumerate(_TEXT_DATE_PATTERNS):
        m = pat.search(text)
        if not m:
            continue
        try:
            if i == 0:
                return _iso(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
            if i == 1:
                return _iso(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
            if i == 2:
                return _iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if i == 3:
                return _iso(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            return _iso(int(m.group(1)))
        except (ValueError, KeyError):
            continue
    return None


def date_from_web(title_hint: str | None, *, search_router=None, sensitive=False) -> str | None:
    """REMOVED as a cascade tier. Always returns None, and never searches.

    This was the last-resort tier: a network search for the document title's
    publication date. It was removed rather than made conditional, for two
    reasons that are independent of each other.

    First, it decided REVIEW MEMBERSHIP from a network result. A document with
    no resolvable date falls out of the operational set (review_scope.apply_cutoff
    keeps only dates at or after the cutoff, and an unresolved date is not one),
    so whether a document was reviewed at all could differ between two runs over
    the same bytes, depending on what a search engine returned. A measurement
    whose population is decided off-machine is not a measurement.

    Second, the title IS document content. Sending it to a search engine is the
    document leaving the machine, which LAW-IV does not permit. Suppressing the
    call under sensitive mode (the old INFRA-041 P2 chokepoint-4 behaviour) left
    the egress in place for every other run.

    The function is kept as a hard None so that any caller still reaching for it
    gets the safe answer rather than an AttributeError, and so the gate can prove
    no search happens under any mode. Nothing in the cascade calls it.
    """
    return None


def read_first_page(path: Path) -> str:
    """First-page text for the content date scan, across the shared format
    family. PDFs use page 1; every other supported format uses the start of its
    extracted text (the cascade scans only the first ~3000 chars). Unsupported
    or unreadable -> '' (the cascade falls back to filename / metadata / web)."""
    p = Path(path)
    if not text_extract.is_supported(p):
        return ""
    if p.suffix.lower() == ".pdf":
        pages = text_extract.extract_pages(p)
        return pages[0][1] if pages else ""
    return text_extract.extract_text(p)


# Eastern Arabic / Arabic-Indic numeral translation table. Per Part XXIV the
# implementation must recognize ٠-٩ in addition to 0-9 when scanning a
# document's first page for its self-stated year.
_EASTERN_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_YEAR_PATTERN = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_YEAR_RANGE = range(1990, 2031)


def _year_from_filename(filename: str) -> str | None:
    """Genesis Part XXIV: filename year is the operator-provided signal,
    authoritative when present. Any 4-digit numeric sequence in the slug
    that falls in the valid range counts."""
    stem = Path(filename).stem
    stem_translated = stem.translate(_EASTERN_ARABIC_DIGITS)
    candidates = []
    for m in _YEAR_PATTERN.finditer(stem_translated):
        y = int(m.group(1))
        if y in _YEAR_RANGE:
            candidates.append(y)
    if not candidates:
        return None
    # Prefer the most recent year in the slug — operator slugs often include
    # historical references, but the trailing year typically marks the doc.
    return _iso(max(candidates))


def _years_from_first_page(text: str) -> list[int]:
    """Genesis Part XXIV: years are numeric, not linguistic. Extract every
    four-digit sequence (Western or Eastern Arabic) in the valid range from
    the extracted text. Returns the candidate list in document order with
    duplicates preserved so the caller can pick the most recent / vote.

    The scan used to stop at 3000 characters, which silently defeated it on
    real documents: the device log states its own dates at character 4179 and
    its clean twin at 3701, both past the cut, so a document that names its
    dates in a format this module already parses resolved as UNDATED and fell
    out of the review set. The same dates are read by the duration arithmetic
    elsewhere in the pipeline. The caller decides how much text to hand over
    (read_first_page still reads page 1 of a PDF); this function reads what it
    is given."""
    if not text:
        return []
    head = text.translate(_EASTERN_ARABIC_DIGITS)
    out = []
    for m in _YEAR_PATTERN.finditer(head):
        y = int(m.group(1))
        if y in _YEAR_RANGE:
            out.append(y)
    return out


def resolve_dates(documents: list[Path], *, search_router=None, sensitive=False) -> list[dict]:
    """Run the cascade for each document path per Part XXIV.

    The cascade is now ENTIRELY LOCAL. `search_router` and `sensitive` are
    accepted and ignored: they fed the removed network last-resort tier (see
    this module's docstring). They are kept in the signature so existing
    callers, including pipeline.main, keep working unchanged.

    Returns records with: filename, date, date_source, date_confidence,
    date_candidates (only on uncertain), title.

    Cascade order:
      1. filename, full date first (YYYY-MM-DD, then YYYY-MM), then year only
      2. content, the full date the document states, then a bare-year scan
      3. metadata (container signal, low confidence)

    There is no fourth tier. A document nothing local can date is recorded
    date=None, date_source="unresolved", and that is a REPORTED outcome, not a
    silent one: an unresolved date makes the document fail the review cutoff
    (review_scope.apply_cutoff keeps dates at or after the cutoff, and None is
    not one), so it would otherwise drop out of the review set with nothing
    said. unresolved_documents() names them and the pipeline warns.

    Uncertain rule: when the scan finds multiple candidate years that conflict
    (e.g. a 2019 document referencing 2024 events), the cascade prefers the
    filename; otherwise it records all candidates, picks the most recent, and
    marks confidence="uncertain" so downstream consumers know to be skeptical.
    """
    out: list[dict] = []
    for path in documents:
        # Source 0: PDF metadata (still queried — needed for the title hint
        # and as fallback — but no longer trusted for the date).
        _meta_date, title = date_from_pdf_metadata(path)

        # Source 1: the filename date. The FULL date pattern is tried first
        # (YYYY-MM-DD, then YYYY-MM), and only then the year-only reader. The
        # cascade used to call the year-only reader alone, so four negotiation
        # documents whose names state September and October 2024 were all dated
        # 2024-01-01: the month and day the operator wrote were discarded, and
        # no downstream consumer could recover them (_sort_by_date could not
        # even order the four). date_from_filename was already correct and was
        # simply never called from here.
        filename_full_iso = date_from_filename(path.name)
        filename_year_iso = _year_from_filename(path.name)
        if filename_full_iso and filename_year_iso and \
                filename_full_iso[:4] == filename_year_iso[:4]:
            # Same year, but the full parse carries month and day: prefer it.
            filename_iso = filename_full_iso
        else:
            # _year_from_filename prefers the MOST RECENT year in a slug that
            # carries several; date_from_filename takes the first match. When
            # they disagree on the year, the year-only reader's choice stands.
            filename_iso = filename_year_iso or filename_full_iso
        filename_year = int(filename_iso[:4]) if filename_iso else None

        # Source 2: content. The full date the document STATES is tried first,
        # then the bare-year scan. Neither is truncated any more.
        first_page_text = read_first_page(path)
        content_full_iso = date_from_text(first_page_text)
        content_years = _years_from_first_page(first_page_text)
        content_unique = sorted(set(content_years), reverse=True)

        date: str | None = None
        source: str | None = None
        confidence: str | None = None
        candidates: list[int] = []

        if filename_iso:
            date = filename_iso
            source = "filename"
            confidence = "high"
            # Verify the filename year against content: if content has years
            # but none match the filename, flag as uncertain.
            if content_unique and filename_year not in content_unique:
                confidence = "uncertain"
                candidates = sorted(
                    set([filename_year] + content_unique), reverse=True
                )
        elif content_full_iso and int(content_full_iso[:4]) in _YEAR_RANGE:
            # The document states a full date. Trust it over a bare-year scan
            # of the same text: it is the same source, read more precisely.
            date = content_full_iso
            source = "content"
            confidence = "high" if len(content_unique) <= 1 else "uncertain"
            if len(content_unique) > 1:
                candidates = content_unique
        elif content_unique:
            if len(content_unique) == 1:
                date = _iso(content_unique[0])
                source = "content"
                confidence = "high"
            else:
                date = _iso(content_unique[0])  # most recent
                source = "content"
                confidence = "uncertain"
                candidates = content_unique
        elif _meta_date:
            # Source 3: container metadata (low confidence per Part XXIV).
            date = _meta_date
            source = "metadata"
            confidence = "low"
        # There is no fourth tier. The network search that used to sit here
        # decided review membership from a result that can differ between runs,
        # and sent the document's title off the machine (see this module's
        # docstring). A document nothing local can date stays UNRESOLVED, and
        # says so loudly rather than vanishing from the review set.

        record: dict = {
            "filename": path.name,
            "date": date,
            "date_source": source or "unresolved",
            "date_confidence": confidence or "unresolved",
            "title": title,
        }
        if confidence == "uncertain" and candidates:
            record["date_candidates"] = [_iso(y) for y in candidates]
        out.append(record)
    return out


# PAYLOAD-FREE BY CONSTRUCTION (INFRA-041 P3): the persisted document_dates store carries
# ONLY these structural fields. title (from content/metadata), abs_path (operator-machine
# path), and validation_note (a verbatim first-page excerpt) are operator content / machine
# paths and are DROPPED on write -- regardless of what transient fields the in-memory record
# carries (abs_path stays in memory for the run's file-copy step; it just never persists).
_DATE_STORE_SAFE_FIELDS = ("filename", "date", "date_source", "date_confidence",
                           "date_candidates", "content_validated")


def unresolved_documents(dated_documents) -> list:
    """The documents nothing local could date, as {filename, date_source}.

    This is the surface that makes a silent drop loud. An unresolved date is
    not a cosmetic gap: review_scope.apply_cutoff keeps only documents dated at
    or after the cutoff, and a None date is never at or after anything, so an
    undated document leaves the review set entirely. Before this, that happened
    with nothing written anywhere, and the run's output was indistinguishable
    from a run where the document was reviewed and produced no findings.

    Structural only (a filename and a source label), so it is safe to persist,
    serve and render next to the payload-free date store."""
    out = []
    for rec in dated_documents or []:
        if not rec.get("date"):
            out.append({"filename": rec.get("filename"),
                        "date_source": rec.get("date_source") or "unresolved"})
    return out


def write_undated_report(run_context, dated_documents, operational_filenames) -> Path:
    """Write <run>/audit/undated_documents.json, the run's record of documents
    that could not be dated and what that cost them.

    Same directory and write idiom as convention_assignment.write_assignment
    and pairing_map.write_pairing_map: once per run, at BOOT, never rewritten.

    `excluded` is the load-bearing list: an undated document that a manifest
    still put under review is not a silent drop, while one that is undated AND
    absent from the operational set was never reviewed at all. That is the
    distinction a reader cannot otherwise make, because a document that was
    never reviewed and a document that was reviewed and produced nothing look
    identical in the deliverables."""
    audit_dir = Path(run_context.audit_dir())
    audit_dir.mkdir(parents=True, exist_ok=True)
    undated = unresolved_documents(dated_documents)
    op = set(operational_filenames or ())
    report = {
        "undated": undated,
        "excluded": [u for u in undated if u["filename"] not in op],
        "reviewed_anyway": [u for u in undated if u["filename"] in op],
        "note": ("A document with no resolvable date fails the review cutoff and is "
                 "not reviewed. Name it in input/context/_review_targets.json, or set "
                 "cutoff_type to 'all' in config/review_scope.json. The date is never "
                 "guessed from the network."),
    }
    path = audit_dir / "undated_documents.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _safe_date_record(rec: dict) -> dict:
    return {k: rec[k] for k in _DATE_STORE_SAFE_FIELDS if k in rec}


def write_dates(project_root: Path, dated_documents: list[dict]) -> Path:
    import durable_paths
    path = durable_paths.document_dates_path(project_root)  # protected durable learning (INFRA-030)
    payload = {"schema_version": "1.0.0", "generated_at": datetime.utcnow().isoformat() + "Z",
               "documents": [_safe_date_record(r) for r in dated_documents]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_dates(project_root: Path) -> list[dict]:
    import durable_paths
    path = durable_paths.document_dates_path(project_root)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("documents", [])
    except json.JSONDecodeError:
        return []
