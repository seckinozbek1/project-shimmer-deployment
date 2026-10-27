"""A later round re-runs only what changed (S2b item 3, the operator's rule).

A multi-round case declares its rounds in order, each with its documents. Python
reviews each round's documents with the same structural machinery as the paired
review (pairing_map for which rules could apply to which units, paired_review for
the arithmetic), round by round in sequence order. A unit whose computation inputs
are unchanged since an earlier round is NOT recomputed: its findings are taken from
the earliest round that computed them, rebased onto this round's unit id, and the
reuse is recorded. Only a changed unit's pairs reach paired_review.plan_calls.

What "unchanged" means is decided by a signature over everything the computation
reads for that unit and nothing else: the unit's own text, the full declared rules
paired to it, the document's field vocabulary and the units of measure the document
writes. A change anywhere in that set (a figure, a rule, a label that changes the
vocabulary) recomputes the unit. Unit ids are not part of the signature, so a unit
that moved position between rounds is still recognised; its reused records carry
the new id.

This is Python only. A plan that needs a model (a judged absence, a pair where
nothing is computable) is recorded as `needs_model` and not asked here: the case
phase's model calls are PROCESSOR and VERIFIER on the case evidence, nothing else.

Written to <run>/audit/round_reuse.json. No model, no network, no file outside the
run folder.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import finding_record
import paired_review
import pairing_map
import reference_tables

SCHEMA_VERSION = 1
RECORD_NAME = "round_reuse.json"
# Plans Python settles by itself; the others need a model and are recorded only.
PYTHON_PLAN_KINDS = ("computed", "band", "duration", "absence_computed")


def record_path(ctx):
    return Path(ctx.audit_dir()) / RECORD_NAME


def unit_signature(unit_text, rules, vocabulary, known_units):
    """sha256 over everything the unit's computation reads, and nothing else."""
    payload = {"unit": unit_text,
               "rules": sorted((json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rules)),
               "vocabulary": sorted(" ".join(label) for label in vocabulary),
               "known_units": sorted(str(u) for u in known_units)}
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _findings_for_plans(plans):
    """Typed findings minted from Python-settled plans; the rest listed as needs_model."""
    by_unit, needs_model = {}, []
    for plan in plans:
        unit, rule = plan["unit"], plan["rule"]
        if plan.get("kind") not in PYTHON_PLAN_KINDS:
            needs_model.append({"unit_id": unit["unit_id"], "rule_id": rule.get("id"),
                                "kind": plan.get("kind")})
            continue
        checks = plan["checks"] if plan.get("kind") == "absence_computed" else \
            paired_review.disagreements(plan["checks"])
        for check in checks:
            item = paired_review.finding_from_check(unit_id=unit["unit_id"], rule=rule, check=check)
            if plan.get("kind") == "absence_computed":
                item["absence_path"] = "computed"
            item["provenance"] = "computed"
            by_unit.setdefault(unit["unit_id"], []).append(item)
    return by_unit, needs_model


def _rebase(items, unit_id):
    """A reused unit's records under this round's unit id (the sentence too)."""
    out = []
    for item in items:
        moved = deepcopy(item)
        old = moved.get("unit_id")
        moved["unit_id"] = unit_id
        if old and old != unit_id and isinstance(moved.get("explanation"), str):
            moved["explanation"] = paired_review.computed_sentence(moved)
        out.append(moved)
    return out


def review_document(document, rules, earlier, *, round_id):
    """One round's document. `earlier` maps signature -> the record that first
    computed it, and is extended here. Returns (unit rows, findings, plan count)."""
    text = document.get("text", "")
    rules_by_id = {r["id"]: r for r in rules if isinstance(r, dict) and r.get("id")}
    pairing = pairing_map.build_pairing_map(text, rules, document_id=document["id"])
    units = {u["unit_id"]: u for u in pairing_map.split_units(text, document_id=document["id"])}
    vocabulary = set()
    for unit in units.values():
        vocabulary |= pairing_map.unit_fields(unit.get("text", ""))
    known_units = reference_tables.document_unit_tokens(text)
    pairs, _ = paired_review.pairs_from_map(pairing)
    pairs_by_unit = {}
    for unit_id, rule_id in pairs:
        pairs_by_unit.setdefault(unit_id, []).append(rule_id)
    rows, findings, changed_pairs = [], [], []
    signatures = {}
    for unit_id, unit in units.items():
        paired_rules = [rules_by_id[r] for r in pairs_by_unit.get(unit_id, []) if r in rules_by_id]
        signature = unit_signature(unit.get("text", ""), paired_rules, vocabulary, known_units)
        signatures[unit_id] = signature
        source = earlier.get(signature)
        if source is not None:
            reused = _rebase(source["findings"], unit_id)
            rows.append({"unit_id": unit_id, "signature": signature, "status": "reused",
                         "reused_from": {k: source[k] for k in ("round_id", "document_id", "unit_id")},
                         "pairs": len(pairs_by_unit.get(unit_id, [])), "pairs_computed": 0,
                         "findings": len(reused), "needs_model": source["needs_model"]})
            findings.extend(reused)
            continue
        changed_pairs.extend((unit_id, r) for r in pairs_by_unit.get(unit_id, []))
        rows.append({"unit_id": unit_id, "signature": signature, "status": "computed",
                     "pairs": len(pairs_by_unit.get(unit_id, [])),
                     "pairs_computed": len(pairs_by_unit.get(unit_id, []))})
    plans = paired_review.plan_calls(
        units, changed_pairs, rules_by_id, vocabulary,
        needed_fields_for=lambda rule_text: pairing_map.needed_fields(rule_text, vocabulary),
        known_units=known_units)
    by_unit, needs_model = _findings_for_plans(plans)
    for row in rows:
        if row["status"] != "computed":
            continue
        made = by_unit.get(row["unit_id"], [])
        asks = [n for n in needs_model if n["unit_id"] == row["unit_id"]]
        row["findings"] = len(made)
        row["needs_model"] = asks
        findings.extend(made)
        earlier.setdefault(row["signature"], {"round_id": round_id, "document_id": document["id"],
                                              "unit_id": row["unit_id"], "findings": made,
                                              "needs_model": asks})
    return rows, findings, len(changed_pairs)


def review_rounds(ctx, manifest, documents, *, convention_registry=None):
    """Every declared round, in sequence order; writes and returns the record."""
    record = {"schema_version": SCHEMA_VERSION, "case_id": manifest.get("case_id"),
              "rule": "a later round re-runs only what changed; an unchanged unit's "
                      "computed findings are reused from the round that computed them",
              "rounds": []}
    if convention_registry is None:
        try:
            import convention_parser
            convention_registry = convention_parser.parse_conventions(Path(ctx.project_root)).as_dict()
        except Exception as exc:  # recorded, never fatal to the case phase (type only)
            record["availability"] = "unavailable"
            record["reason"] = "convention registry not readable: %s" % type(exc).__name__
            _write(ctx, record)
            return record
    rules = [r for r in (convention_registry or {}).get("conventions", []) if isinstance(r, dict)]
    record["availability"] = "recorded" if rules else "no_conventions"
    docs = {d.get("id"): d for d in documents or [] if isinstance(d, dict)}
    earlier = {}
    for rnd in sorted(manifest.get("rounds") or [], key=lambda r: r["sequence"]):
        entry = {"round_id": rnd["round_id"], "sequence": rnd["sequence"], "documents": []}
        for doc_id in rnd.get("document_ids") or []:
            doc = docs.get(doc_id)
            if doc is None:
                entry["documents"].append({"document_id": doc_id, "availability": "missing_document"})
                continue
            rows, found, pairs_computed = review_document(doc, rules, earlier, round_id=rnd["round_id"])
            entry["documents"].append({
                "document_id": doc_id, "units": rows, "pairs_computed": pairs_computed,
                "units_reused": sum(1 for r in rows if r["status"] == "reused"),
                "units_computed": sum(1 for r in rows if r["status"] == "computed"),
                "findings": [f for f in found if finding_record.is_finding(f)]})
        record["rounds"].append(entry)
    _write(ctx, record)
    return record


def _write(ctx, record):
    path = record_path(ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def read(run_dir):
    path = Path(run_dir) / "audit" / RECORD_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
