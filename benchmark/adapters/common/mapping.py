"""Run output to label: preregistration sections 5.1 and 5.2, with S-1, S-2, S-3, S-5 and S-6.

An item is a claim about the whole document judged unit by unit, so a settled answer on
any unit beats a refusal on another (decision D-039 item 1). For each item, the first
matching line wins:
  1. run failure                                   -> ABSTAIN (every item of the document)
     (D-066: a run that reached its end with exit code 0 and semantic_complete false is
     not a run failure; its items are labelled by lines 2 to 5)
  2. an irregular record that is not a refusal,    -> FLAG (CUAD: FLAG only when one has
     on any unit                                      relation missing_field, else CLEAR)
  3. an ok record that is not a refusal,           -> CLEAR
     on any unit
  4. a refusal                                     -> UNDECIDED
  5. no record at all (silent)                     -> CLEAR, except (D-066) ABSTAIN with
     basis item_calls_failed when the pairing map records at least one judging call for
     the item's rule and every one has outcome reply_failed (applied only once the
     registry id to operator id map is adopted, open point 12.11; until then the row
     says why it was not applied)

The records are read by the one record reader (common/records.py): B2's from
review_data.json, B3's and B4's from the run's bus, stamped written_by from the line that
carried them, a judged absence counted once by Python's stamped copy, superseded within one
agent and document by the highest `revision` (INFRA-037). A record belongs to an item when
its source_rule_id equals the item's rule id, compared without regard to case. A figure-audit record is one
whose relation is missing_field, below_band, above_band, sum_mismatch or
product_mismatch AND whose written_by stamp is exactly `python` (section 0), one
definition for every benchmark. A band record (below_band, above_band) belongs to the
rule that produced it and decides that rule's item like any other record. Python's
missing_field, sum_mismatch and product_mismatch records are attributed among the
paired rules by shared words, so in a bundle with several rules they decide no item and
are counted as unattached (section 5.1); S-3 attributes them as the record says. A
model-written record always decides the item of the rule it was posted for. UNDECIDED
becomes the benchmark's undecided label where it has one (SciTab: not enough info;
ContractNLI: not mentioned) and ABSTAIN elsewhere. S-5 applies the earlier order, a
refusal before an ok record, to every pipeline arm (section 5.1). S-6 (D-066) makes
every item of a semantically incomplete document ABSTAIN, for every pipeline arm.

Completeness is reported per document and arm (D-066): semantic_complete, the PROCESSOR
calls accepted against made, whether the PROCESSOR delivery was partial, the auditor pairs
made from a partial delivery, and per item whether a record of a partial delivery decided
it. These counts decide no label.

Where the run output's exact names are not settled yet they are named constants here,
marked PROVISIONAL, in one place (preregistration section 12, items 1 and 9).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from . import records

FLAG, CLEAR, UNDECIDED, ABSTAIN = "FLAG", "CLEAR", "UNDECIDED", "ABSTAIN"
ARMS = ("B0", "B1", "B2", "B3", "B4")
PIPELINE_ARMS = ("B3", "B4")

# --- PROVISIONAL: run output names (section 12 items 1 and 9) -------------------------
# Every name in this block is PROVISIONAL until docs/OUTPUT_FORMAT.md settles it (its draft,
# output-format-v1-draft, is on branch loop/s03 since 5fca716; preregistration section 12
# item 9 records where it and this block differ). The completion record is the pipeline's own (scripts/run_completion.py),
# read with the same validity rules as its read(); B2 writes the same record.
TYPED_RECORDS_KEY = records.TYPED_RECORDS_KEY   # B2's key in review_data.json
REVIEW_DATA_FILE = records.REVIEW_DATA_FILE     # PROVISIONAL
DELIVERABLES_DIR = records.DELIVERABLES_DIR     # PROVISIONAL: <run>/deliverables/<document id>/
# Where each arm's typed records are read (common/records.py; loop plan S5, R22): B2 writes
# them under `findings` in review_data.json; the pipeline posts them on its bus, which is
# what B3 and B4 are read from (Python's included; a judged absence counted once, by
# Python's stamped copy). The bus reading is a changed evaluation measure (decision DS5-8):
# it takes effect only once a checker has attacked it and the lead has recorded it, and
# until then the label command refuses B3 and B4. Recorded: the plan checker's attack on
# DS5-8 and the reading it recommended (R22) are in docs/loop/DECISIONS.md D-055, and D-056
# sets this True so B3 labels are read from the bus from L2 on; the final preregistration
# checker attacks section 5.1 again before freeze.
RECORD_SOURCE = {"B2": records.REVIEW_DATA, "B3": records.BUS, "B4": records.BUS}
BUS_READER_ADOPTED = True
COMPLETION_FILE = ("audit", "run_completion.json")    # PROVISIONAL: the pipeline's completion record
COMPLETION_SCHEMA_VERSION = 1             # PROVISIONAL
COMPLETION_STATES = ("running", "completed", "stopped", "interrupted", "failed")
PAIRING_MAP_FILE = ("audit", "pairing_map.json")      # PROVISIONAL
PAIRING_REFUSAL_LISTS = ("absence_refused",)          # PROVISIONAL: refusal entries in the map
PAIRING_RULE_FIELDS = ("source_rule_id", "rule_id")   # PROVISIONAL: how an entry names its rule
UNCERTAIN_FIELD = "confidence"            # PROVISIONAL: the UNCERTAIN marker, tested as the
UNCERTAIN_VALUE = "UNCERTAIN"             # verifiability gate tests it: a truthy `uncertain`,
UNCERTAIN_FLAG_FIELD = "uncertain"        # or `confidence` equal to UNCERTAIN once uppercased
RECORD_ID_FIELD = "item_id"               # PROVISIONAL: the record id (supersession, section 3.4)
REVISION_FIELD = "revision"               # PROVISIONAL: INFRA-037 revision number
WRITTEN_BY_FIELD = "written_by"           # WRITTEN-BY-A (the pipeline on branch loop/s02):
WRITTEN_BY_PYTHON = "python"              # "python" or "model", decided from the post that
                                          # carried the record; B2 writes the same stamp.
                                          # Compared exactly; a record with no stamp is a
                                          # model's (judged), as WRITTEN-BY-A reads it.
B1_LABELS_DIR = "labels"                  # bare_model.py: <out>/labels/<item id>.json
DELIVERABLE_FILES = ("review_data.json", "review_findings.md", "tracked_changes.docx",
                     "document_summary.md")
# D-066, the item-level exception: a judging call's outcome when the call failed, and where
# the run maps a registry id (CONV-001, the id a judging call names) to the operator's own
# id (the item's rule id). The map is the run's own record (docs/OUTPUT_FORMAT.md section
# 8.2), but which map section 5.1 reads is open point 12.11 of the preregistration; until
# the lead adopts it, the exception is computed, reported as not applied, and changes no label.
JUDGING_CALL_FAILED = "reply_failed"
RULE_ID_MAP_FILE = ("audit", "convention_assignment.json")   # PROVISIONAL
RULE_ID_MAP_ADOPTED = False                                   # open point 12.11
# D-066, completeness: payload-free telemetry the run writes (docs/OUTPUT_FORMAT.md section
# 12: files a scorer must not depend on). Read for the completeness report only; no label
# depends on them.
GENERATION_OBSERVATION_FILE = ("logs", "generation_observation.jsonl")   # PROVISIONAL
MODEL_TELEMETRY_FILE = ("logs", "model_telemetry.jsonl")                 # PROVISIONAL
PRODUCER_AGENT = "PROCESSOR"                                              # PROVISIONAL
# The agents whose records rest on the PROCESSOR's delivery: the producer itself and the
# two phase-5 auditors that read its draft (CLAUDE.md, VERIFIER-A).
DRAFT_READERS = ("PROCESSOR", "VERIFIER", "FACT_CHECKER")                 # PROVISIONAL
# ---------------------------------------------------------------------------------------


class Refused(Exception):
    """A labelling step the preregistration does not allow yet."""


MISSING_FIELD = "missing_field"
# The figure audit's relations (docs/INPUT_FORMAT.md section 7). A figure-audit record is a
# record of one of these relations stamped `written_by: python` (section 0); a model-written
# record of the same relation is not one. Python attributes a band record to the rule that
# produced it, and every other figure-audit record among the paired rules by the words a
# rule's text shares with the record's labels, a tie or no shared word going to the first
# rule in reading order (hash order of the opaque ids) (docs/INPUT_FORMAT.md section 9).
# Only that word-based attribution is not a check of the item's claim, so only those
# records decide no item in a several-rule bundle (section 5.1).
FIGURE_AUDIT_RELATIONS = ("missing_field", "below_band", "above_band", "sum_mismatch",
                          "product_mismatch")
BAND_RELATIONS = ("below_band", "above_band")
PRIOR_RELATIONS = ("changed_from_prior", "unchanged_from_prior", "moved_toward", "moved_away",
                   "absent_since_prior")


class Spec:
    """One benchmark's label names. `labels` maps FLAG, CLEAR and UNDECIDED to the
    benchmark's label (None for UNDECIDED means ABSTAIN); `b1_labels` maps each B1
    label name to its class; `absence_flag` is CUAD's missing_field rule; `s2` says
    whether sensitivity analysis S-2 applies; `unit_evidence` whether the benchmark marks
    its evidence as parts (by index), which decides how B1 is located (section 3.2). The
    figure-audit rule of section 5.1 has no per-benchmark switch: it is one rule for all."""

    def __init__(self, name, labels, b1_labels, absence_flag=False, s2=True,
                 unit_evidence=False):
        self.name = name
        self.labels = dict(labels)
        self.b1_labels = {normalise_b1_label(k): v for k, v in b1_labels.items()}
        self.absence_flag = absence_flag
        self.s2 = s2
        self.unit_evidence = unit_evidence

    def label(self, cls: str) -> str:
        if cls == ABSTAIN:
            return ABSTAIN
        value = self.labels.get(cls)
        return ABSTAIN if value is None else value

    def gold_class(self, gold: str) -> str:
        for cls in (FLAG, CLEAR, UNDECIDED):
            if self.labels.get(cls) == gold:
                return cls
        raise ValueError("%s: gold label %r is not a label of this benchmark" % (self.name, gold))


def normalise_b1_label(value) -> str:
    """Section 5.4's parser: lowercase, trim, drop a trailing `(undecided)` and anything
    from the first `:` on, trim again, `_` to a space."""
    text = str(value).lower().strip()
    if text.endswith("(undecided)"):
        text = text[:-len("(undecided)")]
    text = text.split(":", 1)[0].strip()
    return text.replace("_", " ")


# ---------------------------------------------------------------------------
# reading one run


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        return None, type(exc).__name__


review_data_path = records.review_data_path


def read_completion(run_dir):
    """The run's completion record, or None when it is absent, old or malformed: the
    validity rules of scripts/run_completion.read(), reimplemented here so the adapters
    import nothing from the repository. A `completed` record counts only with
    reached_end true, an integer exit_code of 0 and a finished_at timestamp."""
    path = Path(run_dir).joinpath(*COMPLETION_FILE)
    record, _ = _read_json(path) if path.is_file() else (None, "missing")
    if not isinstance(record, dict) or record.get("schema_version") != COMPLETION_SCHEMA_VERSION:
        return None
    state = record.get("state")
    if not isinstance(state, str) or state not in COMPLETION_STATES:
        return None
    if state == "completed" and (record.get("reached_end") is not True
                                 or type(record.get("exit_code")) is not int
                                 or record["exit_code"] != 0
                                 or not isinstance(record.get("finished_at"), str)
                                 or not record["finished_at"]):
        return None
    return record


def semantically_incomplete_end(completion) -> bool:
    """D-066: a valid completion record of a run that reached its end with exit code 0 and
    marks its semantic work incomplete (state `stopped`, `reached_end` true, an integer
    `exit_code` of 0, a `finished_at` timestamp, `semantic_complete` false). Such a run is
    not a run failure."""
    return (isinstance(completion, dict) and completion.get("state") == "stopped"
            and completion.get("reached_end") is True and type(completion.get("exit_code")) is int
            and completion["exit_code"] == 0 and isinstance(completion.get("finished_at"), str)
            and bool(completion["finished_at"]) and completion.get("semantic_complete") is False)


def _jsonl(path: Path):
    """The objects of a JSON Lines file, or None when it is absent or unreadable."""
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return None
    out = []
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else None
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def completeness(run_dir, document_id, completion) -> dict:
    """D-066: how complete one document's run is, read from the run's own records. Counts
    only; no label depends on it. A value the run did not record is None."""
    run = Path(run_dir)
    out = {"semantic_complete": None if completion is None else completion.get("semantic_complete") is not False,
           "processor_calls_made": None, "processor_calls_accepted": None,
           "processor_delivery_partial": None, "partial_delivery_pairs": None}
    observed = _jsonl(run.joinpath(*GENERATION_OBSERVATION_FILE))
    if observed is not None:
        mine = [r for r in observed if str(r.get("doc_id") or document_id) == str(document_id)]
        calls = [r for r in mine if r.get("agent") == PRODUCER_AGENT and "event" not in r]
        out["processor_calls_made"] = len(calls)
        out["processor_calls_accepted"] = sum(1 for r in calls if r.get("accepted_semantic_output") is True)
        merges = [r for r in mine if r.get("event") == "extraction_merge"]
        out["processor_delivery_partial"] = any(r.get("complete") is False and bool(r.get("missing_partitions"))
                                                and int(r.get("item_count") or 0) > 0 for r in merges)
    telemetry = _jsonl(run.joinpath(*MODEL_TELEMETRY_FILE))
    if telemetry is not None:
        out["partial_delivery_pairs"] = sum(1 for r in telemetry if r.get("event") == "auditor_pair"
                                            and r.get("delivery") == "partial")
    return out


def read_rule_map(run_dir) -> dict:
    """The run's own registry id to operator id map ({} when absent or unreadable), keys
    and values folded for comparison."""
    path = Path(run_dir).joinpath(*RULE_ID_MAP_FILE)
    data, _ = _read_json(path) if path.is_file() else (None, "missing")
    by_rule = data.get("by_rule") if isinstance(data, dict) else None
    if not isinstance(by_rule, dict):
        return {}
    return {_fold(k): _fold(v.get("source_rule_id")) for k, v in by_rule.items()
            if isinstance(v, dict) and v.get("source_rule_id")}


def read_run(run_dir, document_id, source=records.REVIEW_DATA) -> dict:
    """{failure, failure_reasons, records, raw_judged_absence, pairing_refusals, faults,
    source, semantic_incomplete, judging_calls, rule_map, completeness} for one document's
    run, its typed records read by the one record reader (common/records.py) from
    `source`: `review_data` (B2) or `bus` (B3, B4). A run failure (section 0) is a
    completion record that is absent, invalid or not `completed`, or a record source that
    is missing or unreadable (review_data.json for B2, the bus for B3), except (D-066) a
    run that reached its end with exit code 0 and semantic_complete false."""
    run = Path(run_dir)
    out = {"failure": False, "failure_reasons": [], "records": [], "pairing_refusals": [],
           "faults": [], "raw_judged_absence": [], "source": source, "semantic_incomplete": False,
           "judging_calls": [], "rule_map": read_rule_map(run)}
    completion = read_completion(run)
    if completion is None:
        out["failure_reasons"].append("completion_record_missing_or_invalid")
    elif semantically_incomplete_end(completion):
        out["semantic_incomplete"] = True
    elif completion["state"] != "completed":
        out["failure_reasons"].append("completion_state:" + completion["state"])
    out["completeness"] = completeness(run, document_id, completion)
    read = records.read_records(run, document_id, source)
    out["failure_reasons"].extend(read["failure_reasons"])
    out["faults"].extend(read["faults"])
    out["records"] = read["records"]
    out["raw_judged_absence"] = read["raw_judged_absence"]
    out["failure"] = bool(out["failure_reasons"])
    pairing_path = run.joinpath(*PAIRING_MAP_FILE)
    if pairing_path.is_file():
        pairing, _error = _read_json(pairing_path)
        if isinstance(pairing, dict):
            mine = pairing.get(document_id)
            mine = mine if isinstance(mine, dict) else pairing
            for key in PAIRING_REFUSAL_LISTS:
                for entry in mine.get(key) or []:
                    if isinstance(entry, dict):
                        out["pairing_refusals"].append(entry)
            out["judging_calls"] = [c for c in mine.get("judging_calls") or [] if isinstance(c, dict)]
        else:
            out["faults"].append("pairing_map_unreadable")
    return out


def _fold(value) -> str:
    return str(value if value is not None else "").casefold()


def verdict(record) -> str:
    return _fold(record.get("record_verdict")).strip()


def is_refusal(record) -> bool:
    """The verifiability gate's own test (scripts/verifiability_gate.py)."""
    return (bool(record.get(UNCERTAIN_FLAG_FIELD))
            or str(record.get(UNCERTAIN_FIELD, "")).upper() == UNCERTAIN_VALUE)


def is_computed(record) -> bool:
    """Python's own record (section 3.6): stamped exactly `written_by: python`. Any other
    stamp, and no stamp at all, is a model's, whatever other field the record carries
    (WRITTEN-BY-A on branch loop/s02)."""
    return record.get(WRITTEN_BY_FIELD) == WRITTEN_BY_PYTHON


def is_figure_audit(record) -> bool:
    """Section 0: a figure-audit relation AND Python's own stamp, compared exactly."""
    return str(record.get("relation") or "") in FIGURE_AUDIT_RELATIONS and is_computed(record)


def attributed_by_words(record) -> bool:
    """A figure-audit record Python attributes among the paired rules by shared words
    (missing_field, sum_mismatch, product_mismatch); a band record is not one: it belongs
    to the rule that produced it."""
    return is_figure_audit(record) and str(record.get("relation") or "") not in BAND_RELATIONS


def set_aside(spec: Spec, rule_count: int) -> bool:
    """Whether the records `attributed_by_words` decide no item in this document: exactly
    when the bundle has more than one rule (section 5.1), on every benchmark alike."""
    return int(rule_count) > 1


def _layer(records) -> str:
    kinds = {"computed" if is_computed(r) else "judged" for r in records}
    return kinds.pop() if len(kinds) == 1 else ("both" if kinds else "")


# ---------------------------------------------------------------------------
# the mapping


def item_calls_failed(rule_id: str, run: dict):
    """D-066: (applies, reason). True when the run's pairing map records at least one
    judging call for the item's rule and every one has outcome reply_failed. A judging call
    names the registry id, so it is matched to the item's operator id through the run's own
    map; while that map is not adopted (open point 12.11) the answer is False with the
    reason, and the reason says whether it would have applied."""
    calls = run.get("judging_calls") or []
    if not calls:
        return False, None
    rid = _fold(rule_id)
    rule_map = run.get("rule_map") or {}
    mine = [c for c in calls if rule_map.get(_fold(c.get("rule_id"))) == rid]
    all_failed = bool(mine) and all(c.get("outcome") == JUDGING_CALL_FAILED for c in mine)
    if not RULE_ID_MAP_ADOPTED:
        return False, ("not_applied_rule_map_unsettled:would_apply" if all_failed
                       else "not_applied_rule_map_unsettled")
    if not rule_map:
        return False, "not_applied_no_rule_map"
    return (True, "applied") if all_failed else (False, None)


def _from_partial_delivery(run, deciding) -> bool:
    """D-066: a deciding record posted by an agent that reads the PROCESSOR's delivery, in a
    run whose delivery was partial."""
    if not (run.get("completeness") or {}).get("processor_delivery_partial"):
        return False
    return any(str(r.get(records.ENVELOPE_AGENT_FIELD) or r.get("agent") or "") in DRAFT_READERS
               for r in deciding)


def classify(spec: Spec, rule_id: str, run: dict, rule_count: int = 1,
             attribute_figure_audit: bool = False, refusal_first: bool = False) -> dict:
    """The class of one item from one document's run (sections 5.1, 5.2). `rule_count` is
    the number of rules in the item's bundle; with more than one, Python's figure-audit
    records attributed by shared words decide nothing unless `attribute_figure_audit`
    (sensitivity S-3). `refusal_first` is sensitivity S-5: a refusal before an ok record.
    D-066: an item no record decides is ABSTAIN (`item_calls_failed`) instead of silent
    when every judging call for its rule failed (item_calls_failed above)."""
    rid = _fold(rule_id)
    mine = [r for r in run["records"] if _fold(r.get("source_rule_id")) == rid]
    faults = []
    prior = [r for r in mine if r.get("relation") in PRIOR_RELATIONS]
    if prior:
        faults.append("prior_relation_ignored:%d" % len(prior))
    mine = [r for r in mine if r.get("relation") not in PRIOR_RELATIONS]
    set_apart = 0
    if set_aside(spec, rule_count) and not attribute_figure_audit:
        set_apart = sum(1 for r in mine if attributed_by_words(r))
        mine = [r for r in mine if not attributed_by_words(r)]
    irregular = [r for r in mine if verdict(r) == "irregular" and not is_refusal(r)]
    refusals = [r for r in mine if is_refusal(r)] + [
        e for e in run["pairing_refusals"]
        if any(_fold(e.get(f)) == rid for f in PAIRING_RULE_FIELDS if e.get(f))]
    oks = [r for r in mine if verdict(r) == "ok" and not is_refusal(r)]
    unknown = [r for r in mine if verdict(r) not in ("ok", "irregular") and not is_refusal(r)]
    if unknown:
        faults.append("record_verdict_unrecognised:%d" % len(unknown))
    row = {"cited_unit_ids": [], "layer": "", "faults": faults,
           "missing_field_and_other": False, "judged_without_relation": 0,
           "figure_audit_set_aside": set_apart,
           # per-unit records that disagree (section 12 item 2): reported, never a label
           "refusal_and_ok": bool(refusals) and bool(oks),
           "irregular_and_ok": bool(irregular) and bool(oks),
           "ok_over_refusal": False, "item_calls_failed": None,
           "decided_by_partial_delivery_record": False, "flagged_by_band": False}
    if run["failure"]:
        return dict(row, **{"class": ABSTAIN, "basis": "run_failure"})
    applies, reason = item_calls_failed(rule_id, run)
    row["item_calls_failed"] = reason
    # counted only once the run has not failed: a failed run decides nothing by an ok
    row["ok_over_refusal"] = not irregular and bool(refusals) and bool(oks)
    if irregular:
        relations = {str(r.get("relation") or "") for r in irregular}
        row["judged_without_relation"] = sum(
            1 for r in irregular if not r.get("relation") and not is_computed(r))
        deciding = irregular
        cls, basis = FLAG, "irregular"
        if spec.absence_flag:
            absent = [r for r in irregular if r.get("relation") == MISSING_FIELD]
            row["missing_field_and_other"] = bool(absent) and bool(relations - {MISSING_FIELD})
            if absent:
                deciding, basis = absent, "irregular_missing_field"
            else:
                cls, basis = CLEAR, "irregular_other_relation"
        row["cited_unit_ids"] = sorted({str(r.get("unit_id")).casefold()
                                        for r in deciding if r.get("unit_id")})
        row["layer"] = _layer(deciding)
        row["decided_by_partial_delivery_record"] = _from_partial_delivery(run, deciding)
        # section 12 item 3: a FLAG decided by a band record (a band read from the rule's text)
        row["flagged_by_band"] = cls == FLAG and any(str(r.get("relation") or "") in BAND_RELATIONS
                                                     for r in deciding)
        return dict(row, **{"class": cls, "basis": basis})
    # a settled answer on any unit beats a refusal on another (D-039 item 1); S-5 keeps
    # the earlier order, a refusal on any unit before an ok record
    if refusal_first and refusals:
        row["decided_by_partial_delivery_record"] = _from_partial_delivery(run, refusals)
        return dict(row, **{"class": UNDECIDED, "basis": "refusal"})
    if oks:
        row["decided_by_partial_delivery_record"] = _from_partial_delivery(run, oks)
        return dict(row, **{"class": CLEAR, "basis": "ok"})
    if refusals:
        row["decided_by_partial_delivery_record"] = _from_partial_delivery(run, refusals)
        return dict(row, **{"class": UNDECIDED, "basis": "refusal"})
    if unknown:
        return dict(row, **{"class": CLEAR, "basis": "unrecognised_record"})
    if applies:
        return dict(row, **{"class": ABSTAIN, "basis": "item_calls_failed"})
    return dict(row, **{"class": CLEAR, "basis": "silent"})


def _record_ids(records):
    return [str(r[RECORD_ID_FIELD]) for r in records if r.get(RECORD_ID_FIELD)]


def _deliverable_text(path: Path) -> str:
    if path.suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                return "\n".join(archive.read(n).decode("utf-8", "replace")
                                 for n in archive.namelist() if n.endswith(".xml"))
        except (OSError, zipfile.BadZipFile):
            return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def unattached(run: dict, rule_ids, run_dir, document_id, set_aside_figure_audit=False) -> dict:
    """Irregular records whose source_rule_id matches no item, counted once by record id
    in review_data.json, and how many of those ids each deliverable shows (3.4). With
    `set_aside_figure_audit` (a several-rule bundle, section 5.1), the irregular
    figure-audit records attributed by shared words and tied to an item count here too;
    `figure_audit` says how many."""
    wanted = {_fold(r) for r in rule_ids}
    irregular = [r for r in run["records"] if verdict(r) == "irregular" and not is_refusal(r)]
    stray = [r for r in irregular if _fold(r.get("source_rule_id")) not in wanted]
    figure = [r for r in irregular if set_aside_figure_audit and attributed_by_words(r)
              and _fold(r.get("source_rule_id")) in wanted]
    stray = stray + figure
    with_id = sorted(set(_record_ids(stray)))
    per_file = {}
    folder = Path(run_dir) / DELIVERABLES_DIR / document_id
    for name in DELIVERABLE_FILES:
        path = folder / name
        if path.is_file():
            text = _deliverable_text(path)
            per_file[name] = sum(1 for i in with_id if i in text)
        else:
            per_file[name] = None
    return {"count": len(with_id) + sum(1 for r in stray if not r.get(RECORD_ID_FIELD)),
            "without_record_id": sum(1 for r in stray if not r.get(RECORD_ID_FIELD)),
            "figure_audit": len(set(_record_ids(figure)))
            + sum(1 for r in figure if not r.get(RECORD_ID_FIELD)),
            "per_deliverable": per_file}


def relation_counts(run: dict, rule_ids) -> dict:
    """Irregular, non-refusal records tied to an item, by relation (for section 12 item 7)."""
    wanted = {_fold(r) for r in rule_ids}
    counts = {}
    for r in run["records"]:
        if verdict(r) == "irregular" and not is_refusal(r) and _fold(r.get("source_rule_id")) in wanted:
            key = str(r.get("relation") or "")
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def missing_field_layers(run: dict, rule_ids) -> dict:
    """Irregular, non-refusal missing_field records tied to an item, by layer (computed,
    judged): reported per arm for CUAD (section 12 item 7)."""
    wanted = {_fold(r) for r in rule_ids}
    counts = {"computed": 0, "judged": 0}
    for r in run["records"]:
        if (verdict(r) == "irregular" and not is_refusal(r) and r.get("relation") == MISSING_FIELD
                and _fold(r.get("source_rule_id")) in wanted):
            counts["computed" if is_computed(r) else "judged"] += 1
    return counts


def _row(spec, item, arm, result):
    return {"item_id": item["item_id"], "document_id": item["document_id"],
            "rule_id": item["rule_id"], "arm": arm, "class": result["class"],
            "label": spec.label(result["class"]), "basis": result["basis"],
            "cited_unit_ids": result.get("cited_unit_ids", []), "layer": result.get("layer", ""),
            "evidence": result.get("evidence"), "faults": result.get("faults", []),
            "missing_field_and_other": result.get("missing_field_and_other", False),
            "judged_without_relation": result.get("judged_without_relation", 0),
            "figure_audit_set_aside": result.get("figure_audit_set_aside", 0),
            "refusal_and_ok": result.get("refusal_and_ok", False),
            "irregular_and_ok": result.get("irregular_and_ok", False),
            "ok_over_refusal": result.get("ok_over_refusal", False),
            "item_calls_failed": result.get("item_calls_failed"),
            "decided_by_partial_delivery_record": result.get("decided_by_partial_delivery_record", False),
            "flagged_by_band": result.get("flagged_by_band", False)}


def by_document(items):
    docs = {}
    for item in sorted(items, key=lambda i: (str(i["document_id"]), str(i["item_id"]))):
        docs.setdefault(str(item["document_id"]), []).append(item)
    return docs


def label_pipeline_arm(spec: Spec, items, runs_root, arm="B3") -> dict:
    """B3, B2 (and B4): `<runs_root>/<document id>/` is that document's run folder, its
    typed records read from RECORD_SOURCE[arm] by the one record reader. Each
    row also carries its sensitivity S-3 class (figure-audit records attributed) and its
    S-5 class (a refusal before an ok record)."""
    rows, documents = [], []
    source = RECORD_SOURCE.get(arm, records.REVIEW_DATA)
    for doc_id, doc_items in by_document(items).items():
        run_dir = Path(runs_root) / doc_id
        run = read_run(run_dir, doc_id, source)
        rules = [i["rule_id"] for i in doc_items]
        count = len({_fold(r) for r in rules})
        for item in doc_items:
            row = _row(spec, item, arm, classify(spec, item["rule_id"], run, count))
            for key, options in (("s3", {"attribute_figure_audit": True}),
                                 ("s5", {"refusal_first": True})):
                other = classify(spec, item["rule_id"], run, count, **options)
                row[key] = {"class": other["class"], "basis": other["basis"],
                            "cited_unit_ids": other["cited_unit_ids"], "layer": other["layer"]}
            rows.append(row)
        aside = set_aside(spec, count)
        documents.append({"document_id": doc_id, "run_failure": run["failure"],
                          "failure_reasons": run["failure_reasons"], "faults": run["faults"],
                          "record_source": source,
                          # D-066: completeness, per document and arm; decides no label
                          "semantic_incomplete": run["semantic_incomplete"],
                          "completeness": run["completeness"],
                          "rule_map_adopted": RULE_ID_MAP_ADOPTED,
                          # a judged absence's raw model copy: listed, never counted
                          "raw_judged_absence_records": len(run["raw_judged_absence"]),
                          "rules": count, "figure_audit_set_aside": aside,
                          "unattached": unattached(run, rules, run_dir, doc_id, aside),
                          "unattached_s3": unattached(run, rules, run_dir, doc_id, False),
                          "relations": relation_counts(run, rules),
                          "missing_field_by_layer": None if run["failure"] else missing_field_layers(run, rules)})
    return _labels(spec, arm, rows, documents)


def b1_class(spec: Spec, record) -> dict:
    """One B1 label file (bare_model.py) to a class: a missing file, a failed call, an
    abstention or a label that is no label name is a parse failure, ABSTAIN."""
    if not isinstance(record, dict) or record.get("abstain") or record.get("label") in (None, ""):
        return {"class": ABSTAIN, "basis": "b1_parse_failure",
                "evidence": record.get("evidence") if isinstance(record, dict) else None}
    cls = spec.b1_labels.get(normalise_b1_label(record["label"]))
    if cls is None:
        return {"class": ABSTAIN, "basis": "b1_parse_failure", "evidence": record.get("evidence")}
    return {"class": cls, "basis": "b1_label", "evidence": record.get("evidence")}


def label_b1(spec: Spec, items, runs_root) -> dict:
    """B1: `<runs_root>/<document id>/labels/<item id>.json`, written by bare_model.py."""
    rows, documents = [], []
    for doc_id, doc_items in by_document(items).items():
        folder = Path(runs_root) / doc_id / B1_LABELS_DIR
        for item in doc_items:
            path = folder / (str(item["item_id"]) + ".json")
            record, _ = _read_json(path) if path.is_file() else (None, "missing")
            rows.append(_row(spec, item, "B1", b1_class(spec, record)))
        documents.append({"document_id": doc_id, "run_failure": False, "failure_reasons": [],
                          "faults": [], "unattached": None, "relations": {}})
    return _labels(spec, "B1", rows, documents)


def label_b0(spec: Spec, items) -> dict:
    """B0: no finding on every item, so every item is CLEAR (section 4)."""
    rows = [_row(spec, item, "B0", {"class": CLEAR, "basis": "b0"})
            for doc_items in by_document(items).values() for item in doc_items]
    return _labels(spec, "B0", rows, [])


def _labels(spec, arm, rows, documents, analysis="primary") -> dict:
    counts = {
        "items": len(rows),
        "silent": sum(1 for r in rows if r["basis"] == "silent"),
        "undecided": sum(1 for r in rows if r["class"] == UNDECIDED),
        "refusals": sum(1 for r in rows if r["basis"] == "refusal"),
        "b1_parse_failures": sum(1 for r in rows if r["basis"] == "b1_parse_failure"),
        "run_failure_documents": sum(1 for d in documents if d["run_failure"]),
        "abstain": sum(1 for r in rows if r["label"] == ABSTAIN),
        "item_faults": sum(1 for r in rows if r["faults"]),
        "document_faults": sum(1 for d in documents if d["faults"]),
        "items_with_figure_audit_set_aside": sum(1 for r in rows if r.get("figure_audit_set_aside")),
        "items_with_refusal_and_ok": sum(1 for r in rows if r.get("refusal_and_ok")),
        "items_with_irregular_and_ok": sum(1 for r in rows if r.get("irregular_and_ok")),
        "items_decided_by_ok_over_refusal": sum(1 for r in rows if r.get("ok_over_refusal")),
        "unattached_figure_audit": sum((d.get("unattached") or {}).get("figure_audit", 0)
                                       for d in documents),
        "raw_judged_absence_records": sum(d.get("raw_judged_absence_records", 0) for d in documents),
        # D-066
        "semantic_incomplete_documents": sum(1 for d in documents if d.get("semantic_incomplete")),
        "items_in_semantic_incomplete_documents": sum(
            1 for r in rows if r["document_id"] in {d["document_id"] for d in documents
                                                    if d.get("semantic_incomplete")}),
        "item_calls_failed": sum(1 for r in rows if r["basis"] == "item_calls_failed"),
        "item_calls_failed_not_applied": sum(1 for r in rows
                                             if str(r.get("item_calls_failed") or "").endswith(":would_apply")),
        "items_decided_by_partial_delivery_record": sum(1 for r in rows
                                                        if r.get("decided_by_partial_delivery_record")),
        # section 12 item 3
        "items_flagged_by_band": sum(1 for r in rows if r.get("flagged_by_band") and r["class"] == FLAG),
    }
    if spec.absence_flag:
        counts["missing_field_and_other_relation"] = sum(1 for r in rows if r["missing_field_and_other"])
        counts["judged_irregular_without_relation"] = sum(r["judged_without_relation"] for r in rows)
        counts["missing_field_by_layer"] = {layer: sum((d.get("missing_field_by_layer") or {}).get(layer, 0)
                                                       for d in documents)
                                            for layer in ("computed", "judged")}
    return {"benchmark": spec.name, "arm": arm, "analysis": analysis, "counts": counts,
            "labels": rows, "documents": documents}


def _relabel(spec, result, analysis, change):
    rows = []
    for row in result["labels"]:
        row = dict(row)
        new = change(row)
        if new is not None:
            row["class"], row["basis"] = new
            row["label"] = spec.label(row["class"])
        rows.append(row)
    return _labels(spec, result["arm"], rows, result["documents"], analysis)


def sensitivity_s1(spec: Spec, result: dict) -> dict:
    """S-1: B1 parse failures map to CLEAR, as B3's silence does. Other arms unchanged."""
    return _relabel(spec, result, "S-1", lambda r: (CLEAR, "s1_parse_failure_as_clear")
                    if r["arm"] == "B1" and r["basis"] == "b1_parse_failure" else None)


def sensitivity_s2(spec: Spec, result: dict) -> dict:
    """S-2: on ContraDoc, CUAD and FinDVer, UNDECIDED from every arm maps to CLEAR."""
    return _relabel(spec, result, "S-2", lambda r: (CLEAR, "s2_undecided_as_clear")
                    if spec.s2 and r["class"] == UNDECIDED else None)


def _alternative(spec, result, key, analysis, documents):
    rows = []
    for row in result["labels"]:
        row = dict(row)
        other = row.get(key)
        if other is not None:
            row.update(other)
            row["label"] = spec.label(row["class"])
        rows.append(row)
    return _labels(spec, result["arm"], rows, documents, analysis)


def sensitivity_s3(spec: Spec, result: dict) -> dict:
    """S-3: Python's figure-audit records attributed by shared words in a several-rule
    bundle are attributed to the rule they name, as a one-rule bundle's are. B0 and B1
    rows are unchanged."""
    documents = [dict(d, unattached=d.get("unattached_s3", d.get("unattached")))
                 for d in result["documents"]]
    return _alternative(spec, result, "s3", "S-3", documents)


def sensitivity_s5(spec: Spec, result: dict) -> dict:
    """S-5: the earlier order of section 5.1, a refusal on any unit before an ok record
    (irregular still first), for every pipeline arm; B0 and B1 rows are unchanged."""
    return _alternative(spec, result, "s5", "S-5", result["documents"])


def sensitivity_s6(spec: Spec, result: dict) -> dict:
    """S-6 (D-066): every item of a semantically incomplete document ABSTAIN, for every
    pipeline arm; B0 and B1 rows, and every complete document, unchanged. The primary
    comparison restricted to complete documents reads `semantic_incomplete` per document."""
    incomplete = {d["document_id"] for d in result["documents"] if d.get("semantic_incomplete")}
    return _relabel(spec, result, "S-6", lambda r: (ABSTAIN, "s6_semantic_incomplete")
                    if r["arm"] in PIPELINE_ARMS + ("B2",) and r["document_id"] in incomplete else None)


def read_items(path) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("items") if isinstance(data, dict) else data
    for row in rows:
        for key in ("item_id", "document_id", "rule_id"):
            if not row.get(key):
                raise ValueError("an item lacks " + key)
    return rows

