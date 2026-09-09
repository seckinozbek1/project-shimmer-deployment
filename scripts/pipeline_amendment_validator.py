"""Citation-format enforcement for AMENDMENT_DRAFTER output.

Original rule (Part XVIII Section D): every amendment.comment must contain
at least one CONV-* and one REF-*. Location must be a REF-* in the
operational document.

Part XXIII (Absence Detection) carve-out: absence findings, by definition,
have no REF-* in the reviewed document because the provision is missing.
The validator now accepts the sentinel string "document-level" as a valid
`location` for such findings. The comment-citation rule (>=1 CONV-* and
>=1 REF-*) is unchanged — absence findings cite REF-* entries from the
context documents that establish the norm.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_CONV_PATTERN = re.compile(r"\bCONV-\d{3,}\b")
# INFRA-042: tightened with (?<!WEB-) so a WEB-REF-NNNN id is never matched as a corpus REF.
_REF_PATTERN = re.compile(r"(?<!WEB-)\bREF-\d{4,}\b")
_WEBREF_PATTERN = re.compile(r"\bWEB-REF-\d{4,}\b")
_DOCUMENT_LEVEL_SENTINEL = "document-level"

_ROOT = Path(__file__).resolve().parent.parent
_REQUIRED_CACHE: tuple[str, ...] | None = None
_FIELD_FORMS_CACHE: dict | None = None


def _amendment_drafter_required_fields() -> tuple[str, ...]:
    """The single source of truth for what an amendment must carry: AMENDMENT_DRAFTER's
    own contract (config/agent_contracts.json `required`), never a second, hand-
    maintained copy in this module. Before this, validate_amendment carried its own
    hardcoded tuple that demanded `severity` -- never in the real contract's `required`
    list; it is a declared OPTIONAL field whose value-enum description happens to use
    the word "required" as one of its three possible VALUES ("required | recommended |
    advisory"), which is almost certainly where the drift started -- and never checked
    `original_text` or `ref_ids`, both genuinely required by the contract. Read once per
    process and cached: config/agent_contracts.json is static repo configuration for the
    life of a run, not something that changes mid-process."""
    global _REQUIRED_CACHE
    if _REQUIRED_CACHE is not None:
        return _REQUIRED_CACHE
    contracts = json.loads((_ROOT / "config" / "agent_contracts.json").read_text(encoding="utf-8"))
    required = contracts["contracts"]["AMENDMENT_DRAFTER"]["required"]
    _REQUIRED_CACHE = tuple(required)
    return _REQUIRED_CACHE


def validate_amendment_comment(comment: str, *, registry_empty: bool = False) -> bool:
    """Return True iff the comment is adequately grounded.

    Non-empty registry (the default): the rule holds UNCHANGED, at least one CONV-* AND one REF-*.
    Empty registry (INFRA-042 carve-out, conventions list empty or absent): a CONV-* is unsatisfiable
    because none exist, so the comment grounds on at least one REF-* OR at least one WEB-REF-*; the
    CONV-* requirement is relaxed in this state ONLY."""
    if not isinstance(comment, str):
        return False
    has_ref = bool(_REF_PATTERN.search(comment))
    has_webref = bool(_WEBREF_PATTERN.search(comment))
    if registry_empty:
        return has_ref or has_webref
    return bool(_CONV_PATTERN.search(comment)) and has_ref


def _is_valid_location(location: Any) -> bool:
    """Per Part XXIII: location is valid if it is either a REF-* form OR the
    sentinel string 'document-level' (used for absence findings that have
    no natural anchor in the reviewed document)."""
    if not location:
        return False
    s = str(location)
    if s == _DOCUMENT_LEVEL_SENTINEL:
        return True
    return bool(_REF_PATTERN.fullmatch(s))


def _amendment_drafter_field_forms() -> dict:
    """Which amendment field carries which citation form, read from
    AMENDMENT_DRAFTER's own contract (`field_forms`) rather than decided here.

    structure H2b. The two properties that fail in practice, location being a
    REF-* id or the document-level sentinel and comment carrying both a CONV-*
    and a REF-*, used to be known ONLY here, after the fact. They are now
    declared in config/agent_contracts.json beside `required`, so the prompt can
    state them to the model and this module can enforce them from the same
    declaration. An absent or malformed block falls back to the historical
    mapping, so deleting it restores the previous behaviour exactly.

    Cached per process for the same reason as _amendment_drafter_required_fields:
    the contract is static repo configuration for the life of a run."""
    global _FIELD_FORMS_CACHE
    if _FIELD_FORMS_CACHE is not None:
        return _FIELD_FORMS_CACHE
    forms = {}
    try:
        contracts = json.loads((_ROOT / "config" / "agent_contracts.json").read_text(encoding="utf-8"))
        declared = contracts["contracts"]["AMENDMENT_DRAFTER"].get("field_forms") or {}
        for field, spec in declared.items():
            form = spec.get("form") if isinstance(spec, dict) else spec
            if form in _FORM_CHECKS:
                forms[field] = form
    except Exception:
        forms = {}
    _FIELD_FORMS_CACHE = forms or dict(_HISTORICAL_FIELD_FORMS)
    return _FIELD_FORMS_CACHE


def _check_ref_id_or_document_level(field, value, registry_empty):
    if not value:
        return None  # absence is the required-list's business, not the form's
    if _is_valid_location(value):
        return None
    return f"{field} must be REF-* form or 'document-level' sentinel, got {value!r}"


def _check_conv_id(field, value, registry_empty):
    if not value:
        return None
    if _CONV_PATTERN.fullmatch(str(value)):
        return None
    return f"{field} must be CONV-* form, got {value!r}"


def _check_cites_conv_and_ref(field, value, registry_empty):
    # Checked even when empty: an amendment with no comment is ungrounded.
    if validate_amendment_comment(value or "", registry_empty=registry_empty):
        return None
    if registry_empty:
        return f"amendment.{field} must contain >=1 REF-* or >=1 WEB-REF-* (empty registry)"
    return f"amendment.{field} must contain >=1 CONV-* and >=1 REF-*"


_FORM_CHECKS = {
    "REF_ID_OR_DOCUMENT_LEVEL": _check_ref_id_or_document_level,
    "CONV_ID": _check_conv_id,
    "CITES_CONV_AND_REF": _check_cites_conv_and_ref,
}

# The mapping this module carried before it was declared in the contract. Used
# only if the contract's block is missing or unreadable, so behaviour degrades to
# exactly what it was rather than to no checking at all.
_HISTORICAL_FIELD_FORMS = {
    "location": "REF_ID_OR_DOCUMENT_LEVEL",
    "convention_ref": "CONV_ID",
    "comment": "CITES_CONV_AND_REF",
}


def validate_amendment(amendment: dict, *, registry_empty: bool = False) -> tuple[bool, list[str]]:
    """Validate a single amendment object. Returns (ok, errors).

    Required fields come from AMENDMENT_DRAFTER's own contract
    (_amendment_drafter_required_fields), not a copy hand-maintained here.

    INFRA-042 empty-registry carve-out: when registry_empty, convention_ref is NOT required (no
    convention exists to cite), and the comment grounds on a REF-* OR a WEB-REF-*. The other
    contract-required fields are unchanged. When conventions exist, the contract's list holds
    unchanged."""
    errors: list[str] = []
    if not isinstance(amendment, dict):
        return False, ["amendment is not an object"]
    required = _amendment_drafter_required_fields()
    if registry_empty:
        # INFRA-042: no convention exists to cite, so convention_ref cannot be required.
        # The only carve-out this validator has ever had; preserved exactly, on top of
        # the contract's own list rather than inside a second hand-maintained tuple.
        required = tuple(f for f in required if f != "convention_ref")
    for fname in required:
        if not amendment.get(fname):
            errors.append(f"missing required field: {fname}")
    # structure H2b: which field carries which citation form is declared in the
    # contract (field_forms) and applied here, in the contract's own order. The
    # checks and their messages are unchanged; only the mapping moved out of this
    # module and next to `required`, so the prompt can state the same rules.
    for field, form in _amendment_drafter_field_forms().items():
        problem = _FORM_CHECKS[form](field, amendment.get(field), registry_empty)
        if problem:
            errors.append(problem)
    return (not errors, errors)


def validate_amendment_payload(payload: dict, *, registry_empty: bool = False) -> tuple[bool, list[str]]:
    """Validate the full AMENDMENT_DRAFTER output. `registry_empty` threads the INFRA-042 carve-out."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return False, ["payload not an object"]
    if not payload.get("document_id"):
        errors.append("missing document_id")
    amendments = payload.get("amendments")
    if not isinstance(amendments, list):
        errors.append("amendments not a list")
        return False, errors
    for i, a in enumerate(amendments):
        ok, errs = validate_amendment(a, registry_empty=registry_empty)
        if not ok:
            errors.extend(f"amendment[{i}]: {e}" for e in errs)
    return (not errors, errors)
