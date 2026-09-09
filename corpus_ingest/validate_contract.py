#!/usr/bin/env python3
"""Corpus ingestion contract validator (Item 1).

Checks a target directory (default: the repo's input/context/) for conformance to
CONTRACT.md. Structure and metadata only: ZERO language-specific literals (no
Arabic, no English stopwords), matching the framework's language-purge discipline.

Each check produces a NAMED failure so the gate and the operator can see exactly
what broke:

  sidecar_present          _corpus_ingest.json exists and parses as JSON
  sidecar_shape            top level has ingest_run_id(str), generated_at(str), cases(list)
  entry_fields             each entry has all required fields with correct types
  role_is_grounding        role == "context_grounding" for every entry
  file_exists              each entry.file exists in the target dir and ends in .md
  filename_ascii_safe      each .md filename stem matches ^[A-Za-z0-9_-]+$
  filename_has_year        each .md filename carries a 4-digit year per the repo
                           date pattern (scripts/document_dating._FILENAME_PATTERNS)
  date_year_matches_filename  entry.date's year equals the year in entry.file
  date_iso                 entry.date parses as a real YYYY-MM-DD calendar date
  source_verification_valid   status in {verified,unverified,failed}; verified -> non-empty url
  body_nonempty_utf8       each .md reads as UTF-8 and is non-empty after strip
  bijection_missing_file   hard-fail if any sidecar entry names a .md that is absent

A .md present in the target but not listed in the sidecar is a SOFT WARNING only
(bijection_unlisted_md): the operator may keep other corpus files alongside.

Exit 0 on pass, non-zero on any hard failure.

Run convention (see CLAUDE.md): py -3.9 corpus_ingest/validate_contract.py [--target DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date as _date
from pathlib import Path

# Reuse the repo's ACTUAL filename date pattern (the cascade's tier-1 source),
# never a local guess. This file lives at <repo>/corpus_ingest/validate_contract.py;
# scripts/ is a sibling. With scripts/ on the path, document_dating.date_from_filename
# applies the same _FILENAME_PATTERNS the pipeline uses.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

try:
    from document_dating import date_from_filename as _date_from_filename
except Exception:  # standalone fallback when scripts/ is unavailable
    _date_from_filename = None

SIDECAR_NAME = "_corpus_ingest.json"
GROUNDING_ROLE = "context_grounding"
ASCII_STEM_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
VALID_STATUSES = {"verified", "unverified", "failed"}

# Required top-level entry fields and their JSON types. source_verification is an
# object and is checked separately.
REQUIRED_ENTRY_FIELDS = {
    "file": str, "case_id": str, "title": str, "citation": str,
    "jurisdiction": str, "date": str, "language": str, "role": str,
}

# Mirrors document_dating._FILENAME_PATTERNS year forms; used only if the import
# above fails (out-of-repo standalone use). The in-repo gate path always uses the
# real function, so no guess is hardcoded on the live path.
_FALLBACK_YEAR_RE = re.compile(
    r"(?P<ymd>\d{4})[-_.]\d{2}[-_.]\d{2}"
    r"|(?P<ym>\d{4})[-_.]\d{2}(?!\d)"
    r"|\b(?P<bare>(?:19|20)\d{2})\b"
)


def _filename_year(name):
    """The 4-digit year the repo's date cascade reads from this filename, or None.

    Uses document_dating.date_from_filename (the ACTUAL _FILENAME_PATTERNS) when
    importable; falls back to a mirror regex only when scripts/ is unavailable."""
    if _date_from_filename is not None:
        iso = _date_from_filename(name)
        return int(iso[:4]) if iso else None
    stem = Path(name).stem
    m = _FALLBACK_YEAR_RE.search(stem)
    if not m:
        return None
    grp = m.group("ymd") or m.group("ym") or m.group("bare")
    return int(grp)


def validate_target(target_dir):
    """Validate one directory. Returns (n_cases, violations, warnings) where
    violations and warnings are lists of (check_name, detail) tuples. A non-empty
    violations list means a hard failure."""
    target = Path(target_dir)
    violations = []
    warnings = []

    def fail(name, detail):
        violations.append((name, detail))

    def warn(name, detail):
        warnings.append((name, detail))

    sidecar = target / SIDECAR_NAME

    # sidecar_present
    if not sidecar.is_file():
        fail("sidecar_present", f"{SIDECAR_NAME} not found in {target}")
        return 0, violations, warnings
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception as e:
        fail("sidecar_present", f"{SIDECAR_NAME} did not parse as JSON: {type(e).__name__}: {e}")
        return 0, violations, warnings

    # sidecar_shape
    if not isinstance(data, dict):
        fail("sidecar_shape", "top level is not a JSON object")
        return 0, violations, warnings
    if not isinstance(data.get("ingest_run_id"), str):
        fail("sidecar_shape", "ingest_run_id missing or not a string")
    if not isinstance(data.get("generated_at"), str):
        fail("sidecar_shape", "generated_at missing or not a string")
    cases = data.get("cases")
    if not isinstance(cases, list):
        fail("sidecar_shape", "cases missing or not a list")
        return 0, violations, warnings

    n_cases = len(cases)
    listed_files = set()

    for idx, entry in enumerate(cases):
        label = f"cases[{idx}]"
        if not isinstance(entry, dict):
            fail("entry_fields", f"{label} is not an object")
            continue

        case_label = entry["case_id"] if isinstance(entry.get("case_id"), str) else label

        # entry_fields (scalar fields)
        for field, typ in REQUIRED_ENTRY_FIELDS.items():
            if field not in entry:
                fail("entry_fields", f"{label} missing field '{field}'")
            elif not isinstance(entry[field], typ):
                fail("entry_fields", f"{label}.{field} should be {typ.__name__}")
        # entry_fields (source_verification object)
        sv = entry.get("source_verification")
        if not isinstance(sv, dict):
            fail("entry_fields", f"{label}.source_verification missing or not an object")
        else:
            if not isinstance(sv.get("status"), str):
                fail("entry_fields", f"{label}.source_verification.status missing or not a string")
            if not isinstance(sv.get("url"), str):
                fail("entry_fields", f"{label}.source_verification.url missing or not a string")

        # role_is_grounding
        if entry.get("role") != GROUNDING_ROLE:
            fail("role_is_grounding",
                 f"{case_label}: role is {entry.get('role')!r}, must be {GROUNDING_ROLE!r}")

        fname = entry.get("file")
        fyear = None
        if isinstance(fname, str):
            listed_files.add(fname)
            stem = Path(fname).stem

            # filename_ascii_safe
            if not ASCII_STEM_RE.match(stem):
                fail("filename_ascii_safe",
                     f"{case_label}: filename stem {stem!r} is not ASCII-safe (^[A-Za-z0-9_-]+$)")

            # filename_has_year
            fyear = _filename_year(fname)
            if fyear is None:
                fail("filename_has_year",
                     f"{case_label}: filename {fname!r} carries no 4-digit year per the repo date pattern")

            # file_exists (extension + presence)
            md_path = target / fname
            if not fname.endswith(".md"):
                fail("file_exists", f"{case_label}: file {fname!r} does not end in .md")
            if not md_path.is_file():
                fail("file_exists", f"{case_label}: file {fname!r} not found in {target}")
                fail("bijection_missing_file",
                     f"{case_label}: sidecar names {fname!r} but no such .md exists")
            else:
                # body_nonempty_utf8
                body = None
                try:
                    body = md_path.read_text(encoding="utf-8")
                except UnicodeDecodeError as e:
                    fail("body_nonempty_utf8", f"{fname}: not valid UTF-8: {e}")
                if body is not None and not body.strip():
                    fail("body_nonempty_utf8", f"{fname}: body is empty after strip")

        # date_iso + date_year_matches_filename
        date_val = entry.get("date")
        if isinstance(date_val, str):
            m = ISO_DATE_RE.match(date_val)
            if not m:
                fail("date_iso", f"{case_label}: date {date_val!r} is not YYYY-MM-DD")
            else:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                try:
                    _date(y, mo, d)
                except ValueError:
                    fail("date_iso", f"{case_label}: date {date_val!r} is not a real calendar date")
                if fyear is not None and y != fyear:
                    fail("date_year_matches_filename",
                         f"{case_label}: date year {y} != filename year {fyear}")

        # source_verification_valid
        if isinstance(sv, dict):
            status = sv.get("status")
            url = sv.get("url")
            if status not in VALID_STATUSES:
                fail("source_verification_valid",
                     f"{case_label}: status {status!r} not in {sorted(VALID_STATUSES)}")
            if status == "verified" and not (isinstance(url, str) and url.strip()):
                fail("source_verification_valid",
                     f"{case_label}: status 'verified' requires a non-empty url")

    # bijection soft warning: a present .md not listed in the sidecar. The sidecar
    # itself starts with `_` (so it is not a .md) and .gitkeep is not a .md.
    present_md = {p.name for p in target.iterdir() if p.is_file() and p.suffix == ".md"}
    for md in sorted(present_md - listed_files):
        warn("bijection_unlisted_md",
             f"{md}: present in {target} but not listed in the sidecar (soft warning)")

    return n_cases, violations, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate corpus ingestion-contract conformance of a directory.")
    parser.add_argument(
        "--target", default=str(_REPO_ROOT / "input" / "context"),
        help="Directory to validate (default: the repo's input/context/).")
    args = parser.parse_args(argv)

    n_cases, violations, warnings = validate_target(args.target)

    print(f"[corpus-ingest-contract] target: {args.target}")
    print(f"[corpus-ingest-contract] cases checked: {n_cases}")
    for name, detail in warnings:
        print(f"[corpus-ingest-contract] WARN  {name}: {detail}")
    if not violations:
        print("[corpus-ingest-contract] PASS")
        return 0
    print(f"[corpus-ingest-contract] FAIL: {len(violations)} violation(s)")
    for name, detail in violations:
        print(f"[corpus-ingest-contract] VIOLATION  {name}: {detail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
