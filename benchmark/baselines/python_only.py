"""B2, the Python-only arm: Shimmer's computing layer on one test bundle, no model call.

An evaluation tool, not a review. It reads a bundle laid out as docs/INPUT_FORMAT.md
describes (``context/`` with ``_review_targets.json``, ``conventions/``), runs the
same computing modules the pipeline's paired review runs, in the same order, and
stops wherever the pipeline would ask a model:

  convention_parser.parse_conventions   the registry, from a temporary copy of the
                                        bundle's conventions (the parser reads
                                        <root>/input/conventions only)
  reference_builder.ReferenceIndex      the reference passages, in memory, never saved
  convention_assignment                 which reviewer judges each rule (BOOT step)
  pairing_map.build_pairing_map         units, pairs, unmatched-unit findings
  reference_tables                      bands from reference tables, duration bounds
  paired_review.plan_calls              the plans, with Python's own comparisons
  paired_review.finding_from_check      the typed Finding records Python mints
  paired_review.ensure_amendments_for_findings, suppress_contradicted_amendments
                                        the amendments, built from those records only

What the pipeline would send to a model is NOT asked: a judged-absence plan and a
plan with nothing computable produce no record here and are listed in the pairing
map under ``ablation_not_asked``. A computed, band or duration plan yields the same
typed records the pipeline mints from Python's numbers (the model there supplies
only the explanation sentence, so the records here carry Python's default sentence).
The earlier-version comparison (a manifest ``prior``) is not run and is reported.

Every file written says on its first line (Markdown) or in its first key (JSON)
that it is an ablation, not a review. Nothing is written under the repository's
output/ unless --out names it.

Usage:
    py -3.12 benchmark/baselines/python_only.py --bundle <bundle> --out <dir>
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import agent_wrapper  # noqa: E402  make_envelope only; imports no model library
import amendment_render  # noqa: E402
import convention_assignment  # noqa: E402
import convention_parser  # noqa: E402
import finding_record  # noqa: E402
import paired_review  # noqa: E402
import pairing_map  # noqa: E402
import reference_tables  # noqa: E402
import role_resolution  # noqa: E402
import text_extract  # noqa: E402
from pipeline_amendment_validator import validate_amendment_payload  # noqa: E402
from reference_builder import ReferenceIndex  # noqa: E402
from run_context import DELIVERABLE_FILENAMES  # noqa: E402

ARM = "B2"
ABLATION_TEXT = ("ABLATION B2 (Python only): Shimmer's computing layer with no model call. "
                 "This is not a review.")
# The pipeline's own paired-mode default reviewers (pipeline.CONVENTION_REVIEW_AGENTS).
# Read here as data: importing the pipeline would load its whole run machinery.
CONVENTION_REVIEW_AGENTS = ("PRACTICE_AUDITOR", "STYLE_GUARDIAN")
COMPUTED_KINDS = ("computed", "band", "duration")
NOT_ASKED_KINDS = ("absence_judged", "uncomputable")


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# the bundle


def load_corpus(directory):
    """pipeline._load_corpus, the same rules: `_` files skipped, supported types only,
    empty texts dropped, the stem as id unless two files share it."""
    directory = Path(directory)
    loaded, stems = [], {}
    if not directory.is_dir():
        return []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name.startswith("_"):
            continue
        if not text_extract.is_corpus_file(path):
            text_extract.warn_unsupported(path, where=directory.name)
            continue
        text = text_extract.extract_text(path)
        if not text.strip():
            continue
        loaded.append((path, text))
        stems[path.stem] = stems.get(path.stem, 0) + 1
    docs = []
    for path, text in loaded:
        doc_id = path.stem if stems[path.stem] <= 1 else f"{path.stem}__{path.suffix.lstrip('.').lower()}"
        docs.append({"id": doc_id, "name": path.name, "text": text, "path": str(path)})
    return docs


def parse_registry(conventions_dir):
    """The convention registry exactly as convention_parser builds it at BOOT, read from
    a temporary copy (the parser only reads <root>/input/conventions)."""
    with tempfile.TemporaryDirectory(prefix="b_conv_") as tmp:
        target = Path(tmp) / "input" / "conventions"
        target.mkdir(parents=True)
        source = Path(conventions_dir)
        if source.is_dir():
            for path in sorted(source.iterdir()):
                if path.is_file():
                    shutil.copy2(path, target / path.name)
        return convention_parser.parse_conventions(Path(tmp)).as_dict()


def load_bundle(bundle):
    """{context_docs, targets, grounding, prior, registry} for one bundle. A bundle must
    name its document under review in its manifest: the date cutoff the pipeline falls
    back to is repository-wide and is not reproduced here."""
    bundle = Path(bundle)
    context_dir = bundle / "context"
    manifest = role_resolution.read_manifest(context_dir)
    targets = role_resolution.manifest_targets(manifest)
    if not targets:
        raise ValueError("the bundle's context/_review_targets.json names no target")
    context_docs = load_corpus(context_dir)
    names = {d["name"] for d in context_docs}
    missing = sorted(t for t in targets if t not in names)
    if missing:
        raise ValueError("a manifest target is not a readable document in context/: "
                         + ", ".join(missing))
    return {
        "bundle": str(bundle),
        "context_docs": context_docs,
        "targets": [d for d in context_docs if d["name"] in targets],
        "grounding": sorted(role_resolution.manifest_grounding(manifest)),
        "prior": sorted(role_resolution.manifest_prior(manifest)),
        "registry": parse_registry(bundle / "conventions"),
    }


def reference_index(context_docs, op_docs, registry):
    """pipeline._build_reference_index, held in memory: the index file path points into
    a directory that does not exist and save() is never called."""
    idx = ReferenceIndex.open(Path(tempfile.gettempdir()),
                              index_path=Path(tempfile.gettempdir()) / "b2_unsaved" / "index.json")
    for d in context_docs:
        idx.index_document(input_type="context", document_id=d["id"], document_name=d["name"],
                           text=d["text"], max_paragraphs=120)
    for d in op_docs:
        idx.index_document(input_type="operational", document_id=d["id"], document_name=d["name"],
                           text=d["text"], max_paragraphs=200)
    for c in registry.get("conventions", []):
        idx.add(input_type="convention", document_id=c.get("source_file", "conventions"),
                document_name=c.get("source_file", "conventions"),
                location={"page": 1, "paragraph": c.get("id", "?"), "sentence": 1,
                          "char_start": 0, "char_end": 0},
                text_excerpt=c.get("rule", "")[:200])
    return idx


def assignment_for(registry, root=ROOT):
    """The BOOT convention assignment over the tracked agent registry (read only)."""
    agents = json.loads((Path(root) / "config" / "agent_registry.json").read_text(
        encoding="utf-8"))["agents"]
    result = convention_assignment.assign_conventions(registry.get("conventions", []), agents)
    for rid, row in result.get("by_rule", {}).items():
        row["source_rule_id"] = finding_record.source_rule_id_for(rid, registry)
    return result


# ---------------------------------------------------------------------------
# routing, as pipeline._paired_judging_agent and _reattribute_computed_plan decide it


def judging_agent(rule, assignment):
    if assignment is None:
        return CONVENTION_REVIEW_AGENTS[0]
    row = (assignment.get("by_rule") or {}).get(rule.get("id"))
    if row is None or row.get("status") == "untagged":
        return CONVENTION_REVIEW_AGENTS[0]
    for name in row.get("consumer_agents") or []:
        if name in CONVENTION_REVIEW_AGENTS:
            return name
    return None


def not_judged_reason(rule, assignment):
    row = ((assignment or {}).get("by_rule") or {}).get(rule.get("id")) or {}
    consumers = list(row.get("consumer_agents") or [])
    status = row.get("status") or "unknown"
    if consumers:
        return ("no convention-review consumer: assigned to %s only (status %s)"
                % (", ".join(consumers), status)), consumers, status
    return ("no convention-review consumer: matched no agent that can act on it "
            "(status %s)" % status), consumers, status


def reattribute(plan, pairing, rules_by_id, assignment):
    unit_id = plan["unit"]["unit_id"]
    entry = next((u for u in pairing.get("units", []) if u.get("unit_id") == unit_id), None)
    candidates = [rules_by_id.get(p.get("rule_id")) for p in (entry or {}).get("paired", [])]
    candidates = [r for r in candidates if r and r.get("id") != plan["rule"].get("id")
                  and judging_agent(r, assignment) is not None and not (r.get("unless") or [])]
    if not candidates:
        return None
    field = str((plan.get("checks") or [{}])[0].get("stated_field") or "").lower()
    words = {w for w in field.split() if w}
    for r in candidates:
        if words and words <= set(str(r.get("rule", "")).lower().split()):
            return r
    return candidates[0]


# ---------------------------------------------------------------------------
# one document


def review_document(doc, registry, context_refs, refs_excerpt, assignment, *, pairs_per_unit=None):
    """The computing half of pipeline._paired_convention_review. Returns
    (pairing, envelopes): the pairing map with the same bookkeeping keys and the
    per-agent envelopes of the records Python minted."""
    conventions = registry.get("conventions", [])
    rules_by_id = {c["id"]: c for c in conventions}
    pairing = pairing_map.build_pairing_map(doc["text"], conventions, document_id=doc["id"],
                                            convention_registry=registry)
    unit_text = {u["unit_id"]: u for u in pairing_map.split_units(doc["text"], document_id=doc["id"])}
    vocabulary = set()
    for unit in unit_text.values():
        vocabulary |= pairing_map.unit_fields(unit.get("text", ""))
    pairs, dropped = paired_review.pairs_from_map(pairing, cap_per_unit=pairs_per_unit)
    known_units = reference_tables.document_unit_tokens(doc["text"])
    ref_tables = reference_tables.tables_from_entries(context_refs, exclude_document_id=doc["id"],
                                                      known_units=known_units)

    def bands_for(text, rule):
        return reference_tables.bands_for_unit(ref_tables, text, rule.get("rule", ""))

    def duration_bound_for(rule):
        entries = list(context_refs) + [
            {"ref_id": doc["id"], "document_id": doc["id"], "text_excerpt": doc["text"]}]
        return reference_tables.scalar_bound_from_entries(entries, rule.get("rule", ""))

    for entry in pairing.get("units", []):
        unit = unit_text.get(entry["unit_id"])
        if unit is not None:
            entry["band_conditions"] = reference_tables.band_conditions_for_unit(
                ref_tables, unit.get("text", ""), conventions, vocabulary=vocabulary)

    suspensions = []
    plans = paired_review.plan_calls(
        unit_text, pairs, rules_by_id, vocabulary,
        needed_fields_for=lambda text: pairing_map.needed_fields(text, vocabulary),
        reference_bands_for=bands_for, known_units=known_units,
        duration_bound_for=duration_bound_for, suspension_sink=suspensions)

    by_agent, not_judged, reattributed, absence, not_asked = {}, [], [], [], []
    refs = [r.get("ref_id") for r in (refs_excerpt or [])[:3] if r.get("ref_id")]
    for plan in plans:
        unit, rule, checks = plan["unit"], plan["rule"], plan["checks"]
        agent = judging_agent(rule, assignment)
        if agent is None and plan.get("kind") == "computed":
            alt = reattribute(plan, pairing, rules_by_id, assignment)
            if alt is not None:
                reattributed.append({"unit_id": unit["unit_id"], "from_rule_id": rule["id"],
                                     "to_rule_id": alt["id"], "kind": plan.get("kind")})
                rule = plan["rule"] = alt
                agent = judging_agent(rule, assignment)
        if agent is None:
            reason, consumers, status = not_judged_reason(rule, assignment)
            not_judged.append({"unit_id": unit["unit_id"], "rule_id": rule["id"],
                               "kind": plan.get("kind"), "reason": reason,
                               "consumer_agents": consumers, "status": status})
            continue
        source_rule_id = finding_record.source_rule_id_for(rule["id"], registry)
        kind = plan.get("kind")
        if kind == "absence_computed":
            item = paired_review.finding_from_check(unit_id=unit["unit_id"], rule=rule,
                                                    check=checks[0], source_rule_id=source_rule_id,
                                                    refs=refs)
            item["absence_path"] = "computed"
            by_agent.setdefault(agent, []).append(item)
            absence.append({"unit_id": unit["unit_id"], "rule_id": rule["id"],
                            "field": checks[0].get("stated_field"), "path": "computed"})
        elif kind in COMPUTED_KINDS:
            for check in paired_review.disagreements(checks):
                by_agent.setdefault(agent, []).append(paired_review.finding_from_check(
                    unit_id=unit["unit_id"], rule=rule, check=check,
                    source_rule_id=source_rule_id, refs=refs))
        else:
            not_asked.append({"unit_id": unit["unit_id"], "rule_id": rule["id"],
                              "source_rule_id": source_rule_id, "kind": kind,
                              "reason": "the pipeline asks a model here; this ablation does not"})

    for finding in pairing.get("missing_field_findings", []):
        rule = rules_by_id.get(finding.get("rule_id")) or {"id": finding.get("rule_id")}
        agent = judging_agent(rule, assignment)
        if agent is None:
            reason, consumers, status = not_judged_reason(rule, assignment)
            not_judged.append({"unit_id": finding.get("unit_id"), "rule_id": rule.get("id"),
                               "kind": "missing_field", "reason": reason,
                               "consumer_agents": consumers, "status": status})
            continue
        by_agent.setdefault(agent, []).append(finding)

    pairing["not_judged"] = not_judged
    pairing["not_judged_count"] = len(not_judged)
    pairing["reattributed"] = reattributed
    pairing["absence"] = absence
    pairing["absence_computed_count"] = len(absence)
    pairing["absence_judged_count"] = 0
    pairing["absence_refused"] = []
    pairing["absence_refused_count"] = 0
    pairing["calls_made"] = 0
    pairing["dropped_by_cap"] = len(dropped)
    pairing["ablation_not_asked"] = not_asked
    pairing["ablation_not_asked_count"] = len(not_asked)
    if suspensions:
        pairing["suspended"] = [
            {"unit_id": s["unit_id"], "rule_id": s["rule_id"],
             "source_rule_id": finding_record.source_rule_id_for(s["rule_id"], registry),
             "detail": s["detail"]} for s in suspensions]
        pairing["suspended_count"] = len(suspensions)
    envelopes = [agent_wrapper.make_envelope(agent, str(doc["id"]), paired_review.dedupe(items))
                 for agent, items in by_agent.items()]
    return pairing, envelopes


def amendments_for(doc, findings, registry):
    """Phase 6's promotion, from the computed records only (pipeline.phase_6_synthesis)."""
    unit_texts = paired_review.unit_texts_for(doc["text"], doc["id"])
    rules_by_id = {str(r.get("id")): r for r in registry.get("conventions", []) if r.get("id")}
    refusals = []
    promotable = [f for f in findings if finding_record.is_finding(f)]
    amendments, _added = paired_review.ensure_amendments_for_findings(
        [], promotable, unit_texts=unit_texts, refusal_sink=refusals, rules_by_id=rules_by_id)
    vocabulary = set()
    for unit in unit_texts.values():
        vocabulary |= pairing_map.unit_fields(unit.get("text", ""))
    amendments, _refused = paired_review.suppress_contradicted_amendments(
        amendments, unit_texts, rules_by_id, vocabulary)
    return amendments, refusals


def _category_for(registry):
    def lookup(conv_id):
        for c in registry.get("conventions", []):
            if c.get("id") == conv_id:
                return c.get("category")
        return None
    return lookup


# ---------------------------------------------------------------------------
# the run


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(bundle, out, *, pairs_per_unit=None, root=ROOT):
    """Run B2 on one bundle into `out`. Returns the summary written to FINAL_STATUS.json."""
    out = Path(out)
    data = load_bundle(bundle)
    registry = data["registry"]
    idx = reference_index(data["context_docs"], data["targets"], registry)
    context_refs = [e.as_dict() for e in idx.entries if e.input_type == "context"]
    assignment = assignment_for(registry, root)
    pairing_file = {"ablation": ABLATION_TEXT}
    documents = {}
    for doc in data["targets"]:
        refs_excerpt = [e.as_dict() for e in idx.find_by_document(doc["id"])[:30]]
        pairing, envelopes = review_document(doc, registry, context_refs, refs_excerpt, assignment,
                                             pairs_per_unit=pairs_per_unit)
        findings = [item for env in envelopes for item in env["items"]]
        amendments, refusals = amendments_for(doc, findings, registry)
        master = {"document_id": doc["id"], "amendments": amendments, "prior_comparisons": [],
                  "prior_refusals": [], "prior_orphans": []}
        _ok, errors = validate_amendment_payload(
            master, registry_empty=not registry.get("conventions"))
        master["_validator_errors"] = errors
        review_data = {"ablation": ABLATION_TEXT, **master, "findings": findings}
        doc_dir = out / "deliverables" / doc["id"]
        _write_json(doc_dir / DELIVERABLE_FILENAMES["amendments_json"], review_data)
        md = amendment_render.render_amendments_md(master, document_name=doc["name"],
                                                   category_for_conv=_category_for(registry),
                                                   output_language="en")
        (doc_dir / DELIVERABLE_FILENAMES["amendments_md"]).write_text(
            ABLATION_TEXT + "\n\n" + md + "\n", encoding="utf-8")
        pairing_file[str(doc["id"])] = pairing
        documents[doc["id"]] = {
            "findings": len(findings),
            "irregular": sum(1 for f in findings
                             if str(f.get("record_verdict") or "").lower() == "irregular"),
            "amendments": len(amendments), "amendment_refusals": len(refusals),
            "not_asked": pairing["ablation_not_asked_count"],
            "not_judged": pairing["not_judged_count"], "model_calls": 0}
    _write_json(out / "audit" / "pairing_map.json", pairing_file)
    status = {"ablation": ABLATION_TEXT, "arm": ARM, "state": "completed", "finished_at": _now(),
              "bundle": Path(bundle).name, "model_calls": 0, "documents": documents,
              "not_reproduced": {
                  "prior_comparison": bool(data["prior"]),
                  "deliverables_not_written": [DELIVERABLE_FILENAMES[k] for k in (
                      "context_summary", "operative_summary", "amendments_docx",
                      "per_agent_deliverable")],
                  "refs_excerpt": "the document's own first 30 index entries "
                                  "(the pipeline's fallback when no embedding store is open)"}}
    _write_json(out / "FINAL_STATUS.json", status)
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bundle", required=True, help="the test bundle folder")
    parser.add_argument("--out", required=True, help="the output folder (created)")
    parser.add_argument("--pairs-per-unit", type=int, default=None,
                        help="the pipeline's paired-mode cap (default: no cap, as the pipeline)")
    args = parser.parse_args(argv)
    status = run(args.bundle, args.out, pairs_per_unit=args.pairs_per_unit)
    print(json.dumps({k: status[k] for k in ("arm", "state", "model_calls", "documents")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
