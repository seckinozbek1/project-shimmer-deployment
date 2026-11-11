"""The development scoring mode `detection_dev` (docs/loop/DECISIONS.md D-194; Annex D
D-S26 item 1). Development only: it is not the preregistration's reading, and the two
modes of docs/benchmarks/SCORING_MODES.md (`v2_primary`, `benchmark`) are untouched by it.

It asks one question of a run: which labels rest on a claim the run kept, and what does
the document's set of kept claims settle at the level of the document.

Records are read exactly as `v2_primary` reads them (common/mapping.py: the one record
reader, supersession, a judged absence counted once by Python's stamped copy, a record
belonging to an item by its source_rule_id, prior relations dropped with their fault,
Python's figure-audit records attributed by shared words set aside in a several-rule
bundle); advice is not mapped through the rule-id map. The document's units are the run's
own unit list, `units[].unit_id` of its pairing map (for a document read in segments, each
segment's, translated as its records are).

Unit states. For an item's rule each unit gets the set of states its kept records give:
  holds      an ok record that is not a refusal
  violates   an irregular record that is not a refusal, relation not an absence relation
  lacks      an irregular record that is not a refusal, relation an absence relation
  uncertain  a record carrying the UNCERTAIN marker
A unit is cleanly in a state when its set is exactly that state; two or more states make it
conflicting, cleanly in none. A pairing-map refusal entry (an answer Python refused) is no
kept claim and gives no state. A record whose unit id names no unit of the list is unplaced:
it gives no state and decides nothing (counted).

Document level, by the reading each adapter declares on its Spec (`detection`):
  exists     (CUAD: "in at least one passage") CLEAR when some unit cleanly holds; FLAG only
             when every unit of the list cleanly lacks
  each       (ContraDoc: a rule of every passage) FLAG when some unit cleanly violates;
             CLEAR only when every unit cleanly holds
  three_way  (ContractNLI, SciTab) FLAG when some unit cleanly violates and none holds,
             CLEAR when some unit cleanly holds and none violates, both a conflict (ABSTAIN);
             UNDECIDED (not mentioned, not enough info) only when no unit holds or violates
             and every unit's states are within lacks and uncertain
The cell step's decisions (D-472). A rule declaring `[compare: cells]` writes a record only for a
settled "not met" (CELLS-A); what it decided otherwise stands in the pairing map's `cell_claims`
row alone. Each decision of the item's rule there is a kept claim of its unit: settled as the
declared holding answer gives `holds`, not settled gives `uncertain`, and a settled "not met" gives
nothing by itself (its record does, when Python kept it). So a claim the judge could not settle is
never CLEAR: under three_way it is UNDECIDED when every unit is unsettled, else not established;
and a claim with no decision and no kept record is silence. A claim is CLEAR only when no unit
carries a settled "not met" decision, whether Python kept its record or refused it (D-478): with
one, a reading that would be CLEAR is a conflict, ABSTAIN. Python's-records-alone (S-8) reads no
decision: a decision is the model's.

Anything else is ABSTAIN: `dev_not_established` (kept claims that settle no class),
`dev_conflict`, or `dev_silence` when the item has no kept claim at all. A silence row is
never a detection: it is ABSTAIN, and the label v2_primary would give it is kept on the row
(`silence_label`) and reported apart by `report`.

Standard library only; nothing from the repository is imported (the adapters are portable).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import mapping, metrics, records

DETECTION_DEV = "detection_dev"
SCORING_MODES = mapping.SCORING_MODES + (DETECTION_DEV,)
# The pipeline's absence relations (scripts/finding_record.ABSENCE_RELATIONS), held equal by
# the adapter checks' `detection` group; copied because the adapters import nothing from the
# repository.
ABSENCE_RELATIONS = ("missing_field", "licence_missing")
HOLDS, VIOLATES, LACKS, UNCERTAIN = "holds", "violates", "lacks", "uncertain"
# The cell step's row in the pairing map (scripts/cell_selection.py `_row`, written by the pipeline
# under `cell_claims`, one row a rule, `decisions` one per unit asked) and the label of its holding
# answer (config/cell_selection.json), held equal by the adapter checks' `detection` group; copied
# because the adapters import nothing from the repository.
CELL_CLAIMS_KEY, CELL_DECISIONS_KEY, CELL_HOLDS_LABEL = "cell_claims", "decisions", "holds"
STATES = (HOLDS, VIOLATES, LACKS, UNCERTAIN)
EXISTS, EACH, THREE_WAY = "exists", "each", "three_way"
SOME, EVERY = "some", "every"
# The document-level reading of each declared kind, in order: (class, quantifier, the states
# a unit may have). SOME: at least one unit is cleanly in the one state named. EVERY: the unit
# list is known and not empty and every unit's state set is non-empty and within the states
# named. The first entry that holds decides; CONFLICTS are tested before them.
READING_RULES = {
    EXISTS: ((mapping.CLEAR, SOME, (HOLDS,)), (mapping.FLAG, EVERY, (LACKS,))),
    EACH: ((mapping.FLAG, SOME, (VIOLATES,)), (mapping.CLEAR, EVERY, (HOLDS,))),
    THREE_WAY: ((mapping.FLAG, SOME, (VIOLATES,)), (mapping.CLEAR, SOME, (HOLDS,)),
                (mapping.UNDECIDED, EVERY, (LACKS, UNCERTAIN))),
}
CONFLICTS = {THREE_WAY: (HOLDS, VIOLATES)}
BASIS = {(mapping.CLEAR, SOME): "dev_held_in_a_unit", (mapping.FLAG, SOME): "dev_violated_in_a_unit",
         (mapping.FLAG, EVERY): "dev_lacking_in_every_unit", (mapping.CLEAR, EVERY): "dev_held_in_every_unit",
         (mapping.UNDECIDED, EVERY): "dev_unsettled_in_every_unit"}
NOT_ESTABLISHED, CONFLICT, SILENCE = "dev_not_established", "dev_conflict", "dev_silence"
KEPT_CLAIM, SILENT, ANSWER, NO_ANSWER, EXCLUDED = "kept_claim", "silence", "answer", "no_answer", "excluded"
ANALYSES = ("primary", "S-6", "S-7", "S-8")
NOTE = ("detection_dev (D-194): development scoring; a label rests on a kept claim or is "
        "ABSTAIN; silence is never a detection and is reported apart; not the preregistration")


def reading_of(spec) -> str:
    """The reading the adapter declares, or a refusal: the mode never guesses one."""
    reading = getattr(spec, "detection", None)
    if reading is None:
        raise mapping.Refused("%s declares no document-level reading, so detection_dev is refused "
                              "for it (D-194)" % spec.name)
    if reading not in READING_RULES:
        raise ValueError("unknown detection reading %r (one of %s)" % (reading, ", ".join(READING_RULES)))
    return reading


# ---------------------------------------------------------------------------
# the run's own unit list


def _pairing_entry(run_dir, document_id):
    path = Path(run_dir).joinpath(*mapping.PAIRING_MAP_FILE)
    if not path.is_file():
        return None
    try:
        pairing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(pairing, dict):
        return None
    mine = pairing.get(document_id)
    return mine if isinstance(mine, dict) else pairing


def _units_of(entry):
    units = entry.get("units") if isinstance(entry, dict) else None
    if not isinstance(units, list):
        return None
    out = [str(u["unit_id"]) for u in units if isinstance(u, dict) and u.get("unit_id")]
    return out or None


def unit_list(run_dir, document_id, segment_records=None):
    """The document's unit ids as its run's pairing map lists them, in order, or None when
    the map, the document's entry or its unit list is missing or empty. For a document read
    in segments, every segment's list, each unit id translated to the document's
    (common/segments.py `unit_map`); None if any segment has none."""
    if not segment_records:
        return _units_of(_pairing_entry(run_dir, document_id))
    from . import segments as segment_rule
    out = []
    for record in segment_records:
        units = _units_of(_pairing_entry(run_dir, record["segment_id"]))
        if units is None:
            return None
        translate = {k.casefold(): v for k, v in segment_rule.unit_map(record).items()}
        out.extend(translate.get(u.casefold(), u) for u in units)
    return out


def cell_decisions(run_dir, document_id) -> list:
    """The cell step's decisions for one document, as its run's pairing map holds them:
    [{rule_id, unit_id, settled, decided}], the rule named as the row names it (the registry
    id, matched to an item by mapping.names_rule). A row or decision of another shape is left out."""
    entry = _pairing_entry(run_dir, document_id)
    out = []
    for row in (entry.get(CELL_CLAIMS_KEY) if isinstance(entry, dict) else None) or []:
        if not isinstance(row, dict) or not row.get("rule_id"):
            continue
        for decision in row.get(CELL_DECISIONS_KEY) or []:
            if (isinstance(decision, dict) and decision.get("unit_id")
                    and isinstance(decision.get("settled"), bool)):
                out.append({"rule_id": row["rule_id"], "unit_id": str(decision["unit_id"]),
                            "settled": decision["settled"], "decided": decision.get("decided")})
    return out


def cell_state(decision):
    """The state one cell decision gives its unit (D-472): `uncertain` when it was not settled,
    `holds` when settled as the holding answer, None otherwise (a settled "not met" speaks
    through its record alone)."""
    if not decision["settled"]:
        return UNCERTAIN
    return HOLDS if decision["decided"] == CELL_HOLDS_LABEL else None


def cell_claims(rule_id, run) -> list:
    """[(unit id, state)] of the item's rule from the run's cell decisions."""
    rid = mapping._fold(rule_id)
    out = []
    for decision in run.get("cell_decisions") or []:
        if mapping.names_rule(decision, rid, run) and cell_state(decision):
            out.append((decision["unit_id"], cell_state(decision)))
    return out


def cell_not_met(rule_id, run) -> list:
    """The units whose cell decision of the item's rule was settled as anything but the holding
    answer, whatever became of its record (D-478)."""
    rid = mapping._fold(rule_id)
    return sorted({d["unit_id"] for d in run.get("cell_decisions") or []
                   if mapping.names_rule(d, rid, run) and d["settled"] and d["decided"] != CELL_HOLDS_LABEL})


# ---------------------------------------------------------------------------
# one item


def record_state(record):
    """The state one kept record gives its unit, or None for a verdict that is no verdict."""
    if mapping.is_refusal(record):
        return UNCERTAIN
    verdict = mapping.verdict(record)
    if verdict == "ok":
        return HOLDS
    if verdict == "irregular":
        return LACKS if str(record.get("relation") or "") in ABSENCE_RELATIONS else VIOLATES
    return None


def kept_records(spec, rule_id, run, rule_count, attribute_figure_audit=False) -> tuple:
    """(records of the item's rule as v2_primary keeps them, faults): prior relations dropped
    and figure-audit records attributed by shared words set aside, exactly as
    mapping.classify does."""
    rid = mapping._fold(rule_id)
    mine = [r for r in run["records"] if mapping._fold(r.get("source_rule_id")) == rid]
    faults = []
    prior = [r for r in mine if r.get("relation") in mapping.PRIOR_RELATIONS]
    if prior:
        faults.append("prior_relation_ignored:%d" % len(prior))
    mine = [r for r in mine if r.get("relation") not in mapping.PRIOR_RELATIONS]
    if mapping.set_aside(spec, rule_count) and not attribute_figure_audit:
        mine = [r for r in mine if not mapping.attributed_by_words(r)]
    unknown = [r for r in mine if record_state(r) is None]
    if unknown:
        faults.append("record_verdict_unrecognised:%d" % len(unknown))
    return mine, faults


def unit_states(claims, units) -> tuple:
    """({folded unit id: set of states}, unplaced claims): every unit of the list, those
    with no kept claim holding the empty set. `units` None gives ({}, every claim unplaced)."""
    states = {u.casefold(): set() for u in units or ()}
    unplaced = 0
    for record in claims:
        unit = str(record.get("unit_id") or "").casefold()
        if unit and unit in states:
            states[unit].add(record_state(record))
        else:
            unplaced += 1
    return states, unplaced


def some_unit(states, wanted) -> list:
    """The units cleanly in the one state of `wanted`."""
    return sorted(u for u, s in states.items() if s == set(wanted))


def every_unit(states, allowed) -> list:
    """Every unit, when the list is not empty and every unit's states are non-empty and
    within `allowed`; else none."""
    if not states or not all(s and s <= set(allowed) for s in states.values()):
        return []
    return sorted(states)


QUANTIFIERS = {SOME: some_unit, EVERY: every_unit}


def decide(reading, states) -> tuple:
    """(class or None, basis, the deciding units) at document level (module docstring)."""
    conflict = CONFLICTS.get(reading)
    if conflict and all(QUANTIFIERS[SOME](states, (s,)) for s in conflict):
        return None, CONFLICT, []
    for cls, quantifier, allowed in READING_RULES[reading]:
        units = QUANTIFIERS[quantifier](states, allowed)
        if units:
            return cls, BASIS[(cls, quantifier)], units
    return None, NOT_ESTABLISHED, []


def silence_result(v2_primary) -> tuple:
    """(class, basis) of an item with no kept claim: ABSTAIN, never a detection, whatever
    v2_primary would give it (the D-066 basis kept where it applies)."""
    if v2_primary.get("basis") == "item_calls_failed":
        return mapping.ABSTAIN, "item_calls_failed"
    return mapping.ABSTAIN, SILENCE


def classify(spec, rule_id, run, units, rule_count=1, reading=None) -> dict:
    """One item under detection_dev: class, basis, decided_by, the deciding units and
    records, the unit-state counts, and the v2_primary class beside it."""
    reading = reading or reading_of(spec)
    shipped = mapping.classify(spec, rule_id, run, rule_count)
    out = {"v2_primary_class": shipped["class"], "v2_primary_basis": shipped["basis"],
           "cited_unit_ids": [], "layer": "", "faults": list(shipped["faults"]),
           "silence_label": None, "detection": None}
    if run["failure"]:
        return dict(out, **{"class": mapping.ABSTAIN, "basis": "run_failure", "decided_by": EXCLUDED})
    kept, faults = kept_records(spec, rule_id, run, rule_count)
    out["faults"] = faults
    claims = [r for r in kept if record_state(r) is not None]
    states, unplaced = unit_states(claims, units)
    cells = cell_claims(rule_id, run)
    for unit, state in cells:
        if unit.casefold() in states:
            states[unit.casefold()].add(state)
        else:
            unplaced += 1
    rid = mapping._fold(rule_id)
    out["detection"] = {
        "units": None if units is None else len(states),
        "units_with_claims": sum(1 for s in states.values() if s),
        "units_conflicting": sum(1 for s in states.values() if len(s) > 1),
        "clean": {s: len(some_unit(states, (s,))) for s in STATES},
        "kept_records": len(kept), "claims": len(claims) + len(cells), "unplaced_claims": unplaced,
        "cell_decisions": len(cells), "cell_unsettled": sum(1 for _u, s in cells if s == UNCERTAIN),
        "cell_not_met": len(cell_not_met(rule_id, run)),
        "refused_answers": sum(1 for e in run["pairing_refusals"] if mapping.names_rule(e, rid, run))}
    if not kept and not cells:     # D-194 (a): any kept record of the rule makes the row kept_claim (D-472: or a cell decision)
        cls, basis = silence_result(shipped)
        return dict(out, **{"class": cls, "basis": basis, "decided_by": SILENT,
                            "silence_label": spec.label(shipped["class"])})
    cls, basis, deciding_units = decide(reading, states)
    if cls == mapping.CLEAR and cell_not_met(rule_id, run):     # D-478: never CLEAR beside a settled "not met"
        cls, basis, deciding_units = None, CONFLICT, []
    if cls is None:
        return dict(out, **{"class": mapping.ABSTAIN, "basis": basis, "decided_by": KEPT_CLAIM})
    wanted = set(deciding_units)
    deciding = [r for r in claims if str(r.get("unit_id") or "").casefold() in wanted]
    out["cited_unit_ids"] = sorted(wanted) if cls == mapping.FLAG else []
    out["layer"] = mapping._layer(deciding)
    return dict(out, **{"class": cls, "basis": basis, "decided_by": KEPT_CLAIM})


# ---------------------------------------------------------------------------
# one arm


def _dev_row(spec, row, result) -> dict:
    row = {k: v for k, v in row.items() if k not in ("s3", "s5", "s8")}
    row.update({"class": result["class"], "label": spec.label(result["class"]),
                "basis": result["basis"], "cited_unit_ids": result["cited_unit_ids"],
                "layer": result["layer"], "faults": result["faults"],
                "decided_by": result["decided_by"], "v2_primary_class": result["v2_primary_class"],
                "v2_primary_basis": result["v2_primary_basis"],
                "silence_label": result["silence_label"], "detection": result["detection"]})
    return row


SUB_FIELDS = ("class", "basis", "cited_unit_ids", "layer", "decided_by", "silence_label",
              "v2_primary_class", "v2_primary_basis", "detection")


def _sub(result) -> dict:
    """An analysis' own fields of a row (S-8): its class and how it was decided, and its own
    v2_primary class, basis and unit-state counts, never the primary's."""
    return {k: result[k] for k in SUB_FIELDS}


def _excluded(row) -> dict:
    row = dict(row, decided_by=EXCLUDED, silence_label=None, v2_primary_class=row["class"],
               v2_primary_basis=row["basis"], detection=None)
    if "s8" in row:
        row["s8"] = dict(row["s8"], decided_by=EXCLUDED, silence_label=None,
                         v2_primary_class=row["s8"]["class"], v2_primary_basis=row["s8"]["basis"],
                         detection=None)
    row.pop("s3", None)
    row.pop("s5", None)
    return row


def label_pipeline_arm(spec, items, runs_root, arm="B3", run_dirs=None, segments=None) -> dict:
    """B2, B3 and B4 under detection_dev. The v2_primary labels are computed first, unchanged
    (mapping.label_pipeline_arm): every exclusion, the run-failure line and every document row
    are theirs. Each item of a document that is not excluded is then labelled by `classify`
    from the same run, and its S-8 by the same rule on Python's records alone."""
    reading = reading_of(spec)
    base = mapping.label_pipeline_arm(spec, items, runs_root, arm, run_dirs,
                                      scoring=mapping.SCORING_V2_PRIMARY, segments=segments)
    by_id = {r["item_id"]: r for r in base["labels"]}
    rows, documents = [], []
    source = mapping.RECORD_SOURCE.get(arm, records.REVIEW_DATA)
    doc_rows = {d["document_id"]: d for d in base["documents"]}
    for doc_id, doc_items in mapping.by_document(items).items():
        document = dict(doc_rows[doc_id])
        excluded = document.get("over_context_excluded") or document.get("setup_failure_excluded")
        if excluded:
            rows.extend(_excluded(by_id[i["item_id"]]) for i in doc_items)
            document["detection_units"] = None
            documents.append(document)
            continue
        run_dir = Path(run_dirs[doc_id]) if run_dirs is not None else Path(runs_root) / doc_id
        segmented = (segments or {}).get(doc_id) if arm in mapping.SEGMENT_ARMS else None
        run = (mapping.read_segmented_run(run_dir, doc_id, segmented, source) if segmented
               else mapping.read_run(run_dir, doc_id, source))
        units = unit_list(run_dir, doc_id, segmented)
        if not segmented:
            run["cell_decisions"] = cell_decisions(run_dir, doc_id)
        count = len({mapping._fold(i["rule_id"]) for i in doc_items})
        python_run = (dict(mapping.python_only_view(run), cell_decisions=[])
                      if arm in mapping.S8_ARMS else None)
        for item in doc_items:
            primary = classify(spec, item["rule_id"], run, units, count, reading)
            row = _dev_row(spec, by_id[item["item_id"]], primary)
            if python_run is not None:
                row["s8"] = _sub(classify(spec, item["rule_id"], python_run, units, count, reading))
            rows.append(row)
        document["detection_units"] = None if units is None else len(units)
        documents.append(document)
    return _result(spec, arm, rows, documents, reading)


def label_b1(spec, items, runs_root, run_dirs=None) -> dict:
    """B1: its labels are its own answers, unchanged; each row says so (`answer`), a parse
    failure `no_answer`, a setup failure `excluded`."""
    reading = reading_of(spec)
    base = mapping.label_b1(spec, items, runs_root, run_dirs)
    rows = []
    for row in base["labels"]:
        decided = (EXCLUDED if row["basis"] == mapping.SETUP_FAILURE_BASIS
                   else NO_ANSWER if row["class"] == mapping.ABSTAIN else ANSWER)
        rows.append(dict(row, decided_by=decided, v2_primary_class=row["class"],
                         v2_primary_basis=row["basis"], silence_label=None, detection=None))
    return _result(spec, "B1", rows, base["documents"], reading)


def label_b0(spec, items) -> dict:
    """B0: no finding on any item, so every item is silence: ABSTAIN, its v2_primary label
    (CLEAR) kept as the silence label."""
    reading = reading_of(spec)
    base = mapping.label_b0(spec, items)
    rows = []
    for row in base["labels"]:
        cls, basis = silence_result(row)
        rows.append(dict(row, **{"class": cls, "label": spec.label(cls), "basis": basis,
                                 "decided_by": SILENT, "v2_primary_class": row["class"],
                                 "v2_primary_basis": row["basis"],
                                 "silence_label": spec.label(row["class"]), "detection": None}))
    return _result(spec, "B0", rows, base["documents"], reading)


def dev_counts(rows) -> dict:
    """How the rows were decided, counted (the labels file's counts carry them)."""
    by = {}
    for r in rows:
        key = r.get("decided_by") or ""
        by[key] = by.get(key, 0) + 1
    return {"decided_by": dict(sorted(by.items())),
            "kept_claim_labels": sum(1 for r in rows if r.get("decided_by") == KEPT_CLAIM
                                     and r["class"] != mapping.ABSTAIN),
            "kept_claim_not_established": sum(1 for r in rows if r["basis"] == NOT_ESTABLISHED),
            "kept_claim_conflict": sum(1 for r in rows if r["basis"] == CONFLICT),
            "silence_rows": sum(1 for r in rows if r.get("decided_by") == SILENT)}


# The counts of mapping._labels that describe the v2_primary DECISION of an item (its basis
# or the flags v2_primary's lines set on its row), not this mode's: under detection_dev they
# are moved out of counts and given, recomputed on the rows' v2_primary class and basis,
# under v2_primary_counts (D-195 item 6). Every other count reads the rows as labelled here.
V2_PRIMARY_DECISION_COUNTS = (
    "silent", "refusals", "items_with_figure_audit_set_aside", "items_with_refusal_and_ok",
    "items_with_irregular_and_ok", "items_decided_by_ok_over_refusal",
    "items_decided_by_partial_delivery_record", "items_flagged_by_band",
    "item_calls_failed_not_applied", "missing_field_and_other_relation",
    "judged_irregular_without_relation")


def row_v2_field(row, field):
    """A row's `class` or `basis` under v2_primary. A row saved before issue #134 names them
    `as_shipped_*`: a view rebuilt from a saved file must read them, not fall back silently to
    the row's detection_dev value, which moved 16 saved B3 counts when it did."""
    return row.get("v2_primary_" + field, row.get("as_shipped_" + field, row[field]))


def counts_view(spec, out) -> dict:
    """mapping._labels' hook for this mode, applied wherever a labels result is (re)built
    (the primary, every sensitivity analysis, a restricted or scored view): counts keeps the
    counts that read this mode's rows and adds detection_dev; the v2_primary decision's
    counts go under v2_primary_counts."""
    rows = out["labels"]
    shipped_rows = []
    for r in rows:
        cls = row_v2_field(r, "class")
        shipped_rows.append(dict(r, **{"class": cls, "label": spec.label(cls),
                                       "basis": row_v2_field(r, "basis")}))
    shipped = mapping._labels(spec, out["arm"], shipped_rows, out["documents"], out["analysis"],
                              mapping.SCORING_V2_PRIMARY)["counts"]
    counts = {k: v for k, v in out["counts"].items() if k not in V2_PRIMARY_DECISION_COUNTS}
    counts["detection_dev"] = dev_counts(rows)
    out["counts"] = counts
    out["v2_primary_counts"] = shipped
    return out


mapping.COUNTS_HOOKS[DETECTION_DEV] = counts_view


def _result(spec, arm, rows, documents, reading, analysis="primary") -> dict:
    out = mapping._labels(spec, arm, rows, documents, analysis, DETECTION_DEV)
    out["detection_reading"] = reading
    out["note"] = NOTE
    return out


def check_development(items_path) -> list:
    """D-195 item 7: development only. The documents' sides from the parts record the build
    wrote beside the item table; refused when that record is missing or unreadable, or when
    any document's side is not development."""
    from . import bundle, ids
    path = Path(items_path).parent / bundle.PARTS_RECORD_NAME
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise mapping.Refused("detection_dev is development only and needs the parts record beside "
                              "the item table to show it (%s)" % path.name)
    sides = sorted({str(d.get("side")) for d in record.get("documents") or [] if isinstance(d, dict)})
    if not sides or sides != [ids.DEVELOPMENT]:
        raise mapping.Refused("detection_dev is development only; the build's documents are on: %s"
                              % ", ".join(sides or ["no side"]))
    return sides


def check_paired(mine, other) -> None:
    """D-194: a detection_dev labels file is paired only with another, whatever the arms."""
    both = {mapping.scoring_of(mine), mapping.scoring_of(other)}
    if DETECTION_DEV in both and len(both) > 1:
        raise ValueError("a detection_dev labels file is paired only with another detection_dev "
                         "labels file (%s)" % ", ".join(sorted(both)))


def label(adapter, items_path, arm, runs_root=None) -> dict:
    """Every analysis detection_dev writes for one arm: the primary, S-6, S-7 and S-8. Refused
    for a benchmark with no declared reading and for a build that is not development only."""
    from . import cli
    spec = adapter.SPEC
    reading_of(spec)
    check_development(items_path)
    items = mapping.read_items(items_path)
    foreign = sorted({str(i.get("benchmark")) for i in items} - {adapter.BENCHMARK})
    if foreign:
        raise ValueError("items of another benchmark: " + ", ".join(foreign))
    if arm == "B0":
        primary = label_b0(spec, items)
    elif arm == "B1":
        primary = label_b1(spec, items, runs_root)
    elif arm in mapping.ARMS:
        if arm in mapping.PIPELINE_ARMS and not mapping.BUS_READER_ADOPTED:
            raise mapping.Refused("arm %s is refused: the bus reading is not adopted" % arm)
        primary = label_pipeline_arm(spec, items, runs_root, arm, segments=cli.segments_beside(items_path))
    else:
        raise ValueError("unknown arm " + repr(arm))
    out = {"primary": primary}
    for name, fn in (("S-6", mapping.sensitivity_s6), ("S-7", mapping.sensitivity_s7),
                     ("S-8", mapping.sensitivity_s8)):
        result = fn(spec, primary)
        result["detection_reading"], result["note"] = primary["detection_reading"], result.get("note") or NOTE
        out[name] = result
    return out


# ---------------------------------------------------------------------------
# scoring: silence reported apart


def report(labels: dict, bundles_dir) -> dict:
    """Beside the measures (which score a silence row ABSTAIN, so never as a detection): the
    labels from kept claims by label, with how many equal the gold, and the silence rows by
    gold label, with how many of their silence labels equal the gold. Never added to any
    measure."""
    answers, _documents = metrics.read_gold(bundles_dir)
    kept, silent = {}, {}
    matched_silence = 0
    for row in labels["labels"]:
        gold = answers[row["item_id"]]["gold"]
        if row.get("decided_by") in (KEPT_CLAIM, ANSWER) and row["class"] != mapping.ABSTAIN:
            slot = kept.setdefault(row["label"], {"items": 0, "equal_to_gold": 0})
            slot["items"] += 1
            slot["equal_to_gold"] += int(row["label"] == gold)
        elif row.get("decided_by") == SILENT:
            silent[gold] = silent.get(gold, 0) + 1
            matched_silence += int(row.get("silence_label") == gold)
    return {"scoring": DETECTION_DEV, "reading": labels.get("detection_reading"),
            # B2, B3, B4: labels from kept claims; B1: labels from its own answers
            "labels_from_claims": dict(sorted(kept.items())),
            "silence": {"rows": sum(silent.values()), "by_gold": dict(sorted(silent.items())),
                        "silence_label_equal_to_gold": matched_silence,
                        "note": "silence rows are ABSTAIN in every measure; never counted as a detection"},
            "decided_by": dev_counts(labels["labels"])["decided_by"]}
