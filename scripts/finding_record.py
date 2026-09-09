"""The typed inter-agent Finding record.

Operator principle, fixed: agents do not communicate with each other in natural
language. Prose is for the human reader only. An agent that wants to tell another
agent something states it in fields; the sentence it writes for a person travels
alongside as `explanation` and is never read by another agent.

The record is one canonical-envelope item (INFRA-037), so it is strictly FLAT:
every value is a scalar or an array of scalars. A measured quantity is therefore
two fields, a number and its unit string, not a nested object.

    rule_id         a CONV-* id that exists in the convention registry
    source_rule_id  the operator's own id for that rule, e.g. CONV-A02, carried
                    so a finding can be attributed back to the rule as the
                    operator wrote it rather than as the registry renumbered it
    unit_id         the declaration, article, provision or section the finding is
                    about, as the id the pipeline assigned when it split the document
    value_a/unit_a  the figure the document states, and its unit
    value_b/unit_b  the figure it is being compared against, and its unit
    relation        one of RELATIONS, what kind of disagreement this is
    record_verdict  ok or irregular. Deliberately NOT `verdict`: every agent
                    already declares a `verdict` field with its own values, and
                    the verifiability gate fires on exactly those values
                    (GROUNDED, ALIGNED, COMPLIANT, VIOLATION, ANTI_PATTERN,
                    CONFIRMED). A record that overwrote `verdict` with
                    ok/irregular would silently stop that gate firing.
    source_refs     REF-* (or WEB-REF-*) ids the finding rests on
    explanation     prose, human-facing, never consumed by another agent

Optional fields appended by INFRA-044 (none required), for a record that compares
a field with the same field in an operator-declared EARLIER VERSION of the document:

    field_label           the document's own label for the field, as words
    delta                 value_a minus value_b, same unit only
    band_distance_change  distance to the orienting band now minus then; negative
                          is toward the band the rule states
    provenance            "computed" when Python minted the record from figures it
                          read itself; absent when an agent wrote it

The five prior-version relations (changed_from_prior, unchanged_from_prior,
moved_toward, moved_away, absent_since_prior) are appended after the existing ones.
Every record carrying one is ok-verdict by construction, reaches the bus, GET
/findings, document_summary.md, review_findings.md and review_data.json, and is
never an amendment: movement, sameness and absence are information, not an
irregularity. absent_since_prior carries the earlier figure as value_b and no value_a.

The schema lives in config/agent_contracts.json under `finding_record`; this
module reads it rather than carrying a second copy, the same discipline
pipeline_amendment_validator follows for `required` and `field_forms`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_CACHE: dict | None = None

_CONV_PATTERN = re.compile(r"\bCONV-[A-Za-z0-9-]+\b")
_REF_PATTERN = re.compile(r"(?<!WEB-)\bREF-\d{4,}\b")
_WEBREF_PATTERN = re.compile(r"\bWEB-REF-\d{4,}\b")

# The fields an agent writes for a PERSON. They are stripped out of any payload
# that travels from one agent to another, which is the whole point of the record:
# a downstream agent reads value_a, relation and verdict, never a sentence about
# them. `explanation` is on the list by design; it is the record's own prose field.
REASONING_FIELDS = (
    "explanation", "reasoning", "rationale", "recommendation", "comment",
    "justification", "notes", "narrative", "summary",
)

# Fallback used only when the contract declares nothing, so deleting the block
# degrades to the shape this module documents rather than to no validation.
_FALLBACK = {
    "fields": ["rule_id", "source_rule_id", "unit_id", "value_a", "unit_a",
               "value_b", "unit_b", "relation", "record_verdict", "source_refs",
               "explanation", "field_label", "delta", "band_distance_change",
               "provenance"],
    "required": ["rule_id", "unit_id", "relation", "record_verdict"],
    "relations": ["sum_mismatch", "above_band", "below_band", "missing_field",
                  "product_mismatch", "ratio_out_of_range", "date_window",
                  "licence_missing", "changed_from_prior", "unchanged_from_prior",
                  "moved_toward", "moved_away", "absent_since_prior"],
    "verdicts": ["ok", "irregular"],
}


def schema() -> dict:
    """The Finding record schema, read from config/agent_contracts.json."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    declared = {}
    try:
        contracts = json.loads(
            (_ROOT / "config" / "agent_contracts.json").read_text(encoding="utf-8"))
        declared = contracts.get("finding_record") or {}
    except Exception:
        declared = {}
    merged = dict(_FALLBACK)
    # Every key the contract declares is carried, not only the ones the fallback
    # knows about: `says` (the sentence per field, which the prompt renders) has no
    # fallback and would otherwise be silently dropped.
    for key, value in (declared or {}).items():
        if value:
            merged[key] = value
    for key in _FALLBACK:
        merged.setdefault(key, _FALLBACK[key])
    _SCHEMA_CACHE = merged
    return _SCHEMA_CACHE


def relations() -> tuple:
    return tuple(schema()["relations"])


def is_finding(item) -> bool:
    """True when an item is shaped like a Finding record.

    Deliberately structural, not a guess about intent: an item counts when it
    carries a relation from the declared set and a verdict field. An agent's other
    items (an extraction, a redaction, an editorial observation) are untouched.
    """
    if not isinstance(item, dict):
        return False
    return item.get("relation") in relations() and "record_verdict" in item


def validate_finding(item, *, registry_ids=None) -> tuple[bool, list]:
    """Validate one Finding record. Returns (ok, errors).

    registry_ids, when given, is the set of CONV-* ids that actually exist. A
    finding citing a rule that is not in the registry is rejected: an id the
    operator never wrote is not a convention, it is an invention, and an
    invented id is worse than no id because it reads as grounded.
    """
    errors = []
    if not isinstance(item, dict):
        return False, ["finding is not an object"]
    sch = schema()
    for field in sch["required"]:
        if item.get(field) in (None, ""):
            errors.append(f"missing required field: {field}")
    rule_id = item.get("rule_id")
    if rule_id and not _CONV_PATTERN.fullmatch(str(rule_id)):
        errors.append(f"rule_id must be CONV-* form, got {rule_id!r}")
    elif rule_id and registry_ids is not None and str(rule_id) not in set(registry_ids):
        errors.append(f"rule_id {rule_id!r} is not in the convention registry")
    relation = item.get("relation")
    if relation is not None and relation not in relations():
        errors.append(f"relation must be one of {list(relations())}, got {relation!r}")
    verdict = item.get("record_verdict")
    if verdict is not None and str(verdict).lower() not in sch["verdicts"]:
        errors.append(f"record_verdict must be one of {sch['verdicts']}, "
                      f"got {verdict!r}")
    for pair in (("value_a", "unit_a"), ("value_b", "unit_b")):
        value, unit = item.get(pair[0]), item.get(pair[1])
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{pair[0]} must be a number, got {value!r}")
        if unit in (None, ""):
            errors.append(f"{pair[0]} is given without {pair[1]}: a figure with no unit "
                          f"cannot be compared")
    refs = item.get("source_refs")
    if refs is not None:
        if not isinstance(refs, list):
            errors.append("source_refs must be an array of REF-* strings")
        else:
            for r in refs:
                if not (_REF_PATTERN.fullmatch(str(r)) or _WEBREF_PATTERN.fullmatch(str(r))):
                    errors.append(f"source_refs entry {r!r} is not a REF-* or WEB-REF-* id")
    return (not errors, errors)


def strip_reasoning(items):
    """Project items for an INTER-AGENT payload: every prose field removed.

    This is the operator principle made mechanical. What survives is what another
    agent can act on: ids, figures, units, relations, verdicts, citations. What
    goes is every sentence, including the record's own `explanation`, which exists
    for the person reading the deliverable and for nobody else.
    """
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            out.append(item)
            continue
        out.append({k: v for k, v in item.items() if k not in REASONING_FIELDS})
    return out


def typed_line(item) -> str:
    """One compact line for a Finding record, for rendering earlier findings into
    a prompt as typed lines rather than as narrative."""
    if not isinstance(item, dict):
        return str(item)
    parts = []
    rule = item.get("rule_id") or item.get("conv_id")
    if rule:
        src = item.get("source_rule_id")
        parts.append(f"{rule}({src})" if src and src != rule else str(rule))
    if item.get("unit_id"):
        parts.append(f"unit={item['unit_id']}")
    if item.get("relation"):
        parts.append(str(item["relation"]))
    if item.get("value_a") is not None:
        parts.append(f"a={item['value_a']}{item.get('unit_a') or ''}")
    if item.get("value_b") is not None:
        parts.append(f"b={item['value_b']}{item.get('unit_b') or ''}")
    if item.get("record_verdict"):
        parts.append(f"verdict={item['record_verdict']}")
    elif item.get("verdict"):
        parts.append(f"verdict={item['verdict']}")
    refs = item.get("source_refs") or item.get("ref_ids")
    if isinstance(refs, list) and refs:
        parts.append("refs=" + ",".join(str(r) for r in refs[:4]))
    return " ".join(parts) if parts else ""


def render_typed_lines(items, *, limit=None) -> str:
    """Typed lines for every Finding record in `items`, newest first is the
    caller's business. Non-finding items are skipped rather than narrated."""
    lines = []
    for item in items or []:
        if is_finding(item):
            line = typed_line(item)
            if line:
                lines.append(line)
        if limit is not None and len(lines) >= limit:
            break
    return "\n".join(lines)


def source_rule_id_for(rule_id, convention_registry) -> str:
    """The operator's own id for a registry rule, e.g. CONV-A02 for CONV-007.

    The convention parser mints sequential CONV-NNN ids because that is the only
    form pipeline_amendment_validator accepts, and it keeps the operator's own
    heading in the rule's `category` field. So the operator's id is not lost, only
    lower-cased and moved. Recovering it here is what makes a finding attributable
    to the rule as the operator wrote it. Returns "" when the category is not an
    id-shaped string.
    """
    if not rule_id or not isinstance(convention_registry, dict):
        return ""
    for c in convention_registry.get("conventions") or []:
        if c.get("id") != rule_id:
            continue
        category = str(c.get("category") or "")
        candidate = category.upper()
        return candidate if _CONV_PATTERN.fullmatch(candidate) else ""
    return ""


def index_findings(findings):
    """Two indexes over Finding records: by (unit_id, rule_id) and by rule_id."""
    by_pair, by_rule = {}, {}
    for item in findings or []:
        if not is_finding(item):
            continue
        rule = str(item.get("rule_id") or "")
        unit = str(item.get("unit_id") or "")
        if rule:
            by_rule.setdefault(rule, []).append(item)
        if rule and unit:
            by_pair[(unit, rule)] = item
    return by_pair, by_rule


def apply_typed_fields(amendments, findings):
    """Copy an amendment's traceable fields FROM the Finding record it rests on.

    An amendment's location, convention_ref and ref_ids are the three fields that
    make it traceable, and they were being written by the model as prose-derived
    guesses: H2's A/B found two of three amendments putting something in
    `location` that is not a REF-* id at all. Where the amendment names the
    finding it came from, those three fields are now COPIED from that finding's
    typed fields instead of re-derived.

    Matching, in order: the amendment's own finding_unit_id + finding_rule_id;
    failing that, its convention_ref when exactly ONE upstream finding carries
    that rule_id. Ambiguity is left alone rather than guessed at. An amendment
    with no identifiable source finding is returned untouched, so this can only
    ever replace a guess with a typed value, never invent one.

    Returns (amendments, count_copied). The input list is not mutated.
    """
    by_pair, by_rule = index_findings(findings)
    out, copied = [], 0
    for amendment in amendments or []:
        if not isinstance(amendment, dict):
            out.append(amendment)
            continue
        source = None
        unit = amendment.get("finding_unit_id")
        rule = amendment.get("finding_rule_id")
        if unit and rule:
            source = by_pair.get((str(unit), str(rule)))
        if source is None:
            conv = amendment.get("convention_ref")
            candidates = by_rule.get(str(conv or ""), [])
            if len(candidates) == 1:
                source = candidates[0]
        if source is None:
            out.append(amendment)
            continue
        amended = dict(amendment)
        amended["convention_ref"] = source["rule_id"]
        if source.get("source_rule_id"):
            amended["source_convention_ref"] = source["source_rule_id"]
        refs = [str(r) for r in (source.get("source_refs") or []) if r]
        if refs:
            amended["location"] = refs[0]
            amended["ref_ids"] = refs
        amended["derived_from"] = "finding_record"
        out.append(amended)
        copied += 1
    return out, copied


# ---------------------------------------------------------------------------
# INFRA-044: the same field in an earlier version of the document

# The relations INFRA-044 appended: a field of the document compared with the same
# field in the operator-declared earlier version. Every record with one of these
# is ok-verdict, minted in Python, and never an amendment.
PRIOR_RELATIONS = ("changed_from_prior", "unchanged_from_prior", "moved_toward",
                   "moved_away", "absent_since_prior")
OUTSIDE_BAND_RELATIONS = ("above_band", "below_band")

_PRIOR_SECTIONS = (
    ("moved_toward", "Moved toward the mandate"),
    ("moved_away", "Moved away from the mandate"),
    ("changed_from_prior", "Changed, no band to orient the move"),
    ("unchanged_from_prior", "Unchanged"),
    ("absent_since_prior", "Absent since the earlier version"),
)


def _fmt(value):
    if value is None:
        return "?"
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def prior_record_line(item) -> str:
    """One bullet for a prior-version record: the earlier figure, the figure now,
    the delta, the band distance change when one orients it, the rule (with the
    operator's own id when it differs) and the citations."""
    rule = item.get("rule_id") or "?"
    src = item.get("source_rule_id")
    tag = f"{rule}({src})" if src and src != rule else rule
    refs = ",".join(str(r) for r in (item.get("source_refs") or [])[:4])
    unit_b = item.get("unit_b") or ""
    unit_a = item.get("unit_a") or ""
    if item.get("relation") == "absent_since_prior":
        figures = f"{_fmt(item.get('value_b'))}{unit_b} -> (not stated)"
    else:
        figures = f"{_fmt(item.get('value_b'))}{unit_b} -> {_fmt(item.get('value_a'))}{unit_a}"
        if item.get("delta") is not None:
            figures += f" (delta {item['delta']:+g})"
    extra = ""
    if item.get("band_distance_change") is not None:
        extra = f" band distance {item['band_distance_change']:+g}"
    return (f"- {item.get('unit_id', '?')} {item.get('field_label', '')}: {figures}{extra} "
            f"[{tag}] refs={refs}")


def render_prior_comparison(findings, *, refusals=(), orphans=(), outside=(),
                            heading="## Compared with the earlier version") -> list:
    """The comparison section, as lines, for document_summary.md and
    review_findings.md alike (one renderer, so the two cannot disagree).

    Renders only records Python minted (provenance "computed"): a model in wide
    mode may emit one of these relations with figures of its own, and those stay
    among the ordinary findings under their category, never in this section.
    Returns [] when there is nothing to say, so a run with no earlier version
    declared renders byte-identically to before. No heading here may contain the
    token "Amendment ", which amendment_render's drift guard counts.
    """
    prior = [f for f in findings or []
             if f.get("relation") in PRIOR_RELATIONS and f.get("provenance") == "computed"]
    refusals, orphans, outside = list(refusals or []), list(orphans or []), list(outside or [])
    if not prior and not refusals and not orphans and not outside:
        return []
    lines = [heading, ""]
    for relation, title in _PRIOR_SECTIONS:
        rows = [f for f in prior if f.get("relation") == relation]
        lines.append(f"### {title}")
        lines.append("")
        if rows:
            lines.extend(prior_record_line(f) for f in rows)
        else:
            lines.append("- (none)")
        lines.append("")
    if outside:
        lines.append("### Outside a stated band now")
        lines.append("")
        lines.extend(f"- {typed_line(f)}" for f in outside)
        lines.append("")
    if refusals or orphans:
        lines.append("### Not comparable")
        lines.append("")
        for r in refusals:
            lines.append(f"- {r.get('unit_id', '?')} {r.get('label', '')}: {r.get('reason', '')}")
        for o in orphans:
            lines.append(f"- (earlier heading {o.get('unit_slug') or '?'}) {o.get('label', '')}: "
                         f"{o.get('reason', '')}")
        lines.append("")
    return lines
