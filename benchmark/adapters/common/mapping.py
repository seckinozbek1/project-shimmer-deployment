"""Run output to label: preregistration sections 5.1 and 5.2, with S-1, S-2, S-3, S-5 to S-8.

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
     the item's rule and every one has outcome reply_failed (a judging call names the
     registry id, matched to the item's operator id through the run's own
     audit/convention_assignment.json, adopted under open point 12.11, D-078; with that
     map missing, unreadable or not one to one the exception is not applied on the
     document and the row says why)

Before any line, section 5.3 (D-058 condition v; open point 12.14, D-078): a B3 document
whose run made at least one model call over its model's context (a reply record under
audit/model_replies/ whose `context.over_context` is true, as scripts/reply_records.py
writes it) is excluded from B3: every item of it carries basis over_context_excluded, is
listed and counted, and is never scored; sensitivity S-7 scores those items ABSTAIN.
A pairing-map refusal names its rule by the registry id too, and is matched the same way.

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
every item of a semantically incomplete document ABSTAIN, for every pipeline arm. S-7
(section 5.3, D-078) makes every item of a B3 document excluded for a call over its
model's context ABSTAIN; every other analysis leaves those items out. S-8 (DEV-012) scores
B3 and B4 as if every record a model wrote were absent: of the document's records only
those stamped `written_by` exactly `python` are kept (an unstamped record is a model's,
section 3 item 6), and each item is labelled by the same lines on what remains, so an
item a model-written record decided takes the next line, else silence; the run-failure
line, the D-066 rules, the over-context exclusion, the setup-failure rule, the rule-id map
and the pairing-map refusal entries (Python's own map, not records) are unchanged; the
unattached findings under S-8 are Python's alone. For B0, B1 and B2, S-8 equals the
primary analysis, and its output says so (preregistration section 4, word for word).

One setup-failure rule for B1 and B3 alike (D-084, DEV-014): a B1 document whose output
folder holds `b1_setup_failure.json` (bare_model.py writes it when a call runs out of
memory, its attention kernel is refused, or a prompt plus the output allowance exceeds the
model's context), and a B3 document whose run has a reply record of a call that failed out
of memory or on a refused kernel (`backend_ok` false, `error_category` `out_of_memory` or
`attention_kernel_refused`, as agent_wrapper writes it), had a setup failure: every item of
it is ABSTAIN with basis setup_failure, counted apart (never an abstention), left out of
that arm's scoring in every analysis but S-7, which scores it ABSTAIN; a paired comparison
drops a document either arm had a setup failure on. B3's call over the model's context
keeps its own basis, over_context_excluded, and the same treatment.

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

# D-066, the item-level exception: a judging call's outcome when the call failed, and where
# the run maps a registry id (CONV-001, the id a judging call and a pairing-map refusal
# name) to the operator's own id (the item's rule id): the run's own record
# (docs/OUTPUT_FORMAT.md section 8.2), `by_rule` -> `source_rule_id`. Adopted: open point
# 12.11 of the preregistration, settled by the lead (D-078). The map is used on a document
# only when it is readable and one to one; otherwise the exception is not applied there,
# the row says why, and the document is counted (`documents_rule_map_unusable`).
JUDGING_CALL_FAILED = "reply_failed"
RULE_ID_MAP_FILE = ("audit", "convention_assignment.json")
RULE_ID_MAP_ADOPTED = True                                    # open point 12.11, D-078
RULE_MAP_OK, RULE_MAP_MISSING = "ok", "missing"
RULE_MAP_UNREADABLE, RULE_MAP_NOT_ONE_TO_ONE = "unreadable", "not_one_to_one"
# Section 5.3 (D-058 condition v) and open point 12.14 (D-078): a B3 document whose run made
# a model call over its model's context is excluded from B3. The call is read from its reply
# record exactly as scripts/reply_records.py writes it: `<run>/audit/model_replies/*.json`,
# the field `context`, its key `over_context` true (a boolean, compared with `is True`;
# scripts/final_models.context_record writes None where the model states no context).
REPLY_RECORDS_DIR = ("audit", "model_replies")
REPLY_CONTEXT_FIELD = "context"
OVER_CONTEXT_FIELD = "over_context"
OVER_CONTEXT_ARMS = ("B3",)   # section 5.3 names B3 (B4 is not run where B3's text does not fit)
OVER_CONTEXT_BASIS = "over_context_excluded"
S7_BASIS = "s7_over_context_abstain"
# DEV-012, sensitivity S-8: the arms it changes; for every other arm S-8 equals the primary.
S8_ARMS = PIPELINE_ARMS
S8_NOTE_APPLIED = ("S-8: scored as if every record written by a model were absent (only records "
                   "stamped written_by exactly 'python' kept; an unstamped record is a model's); "
                   "every other rule unchanged")
S8_NOTE_EQUAL = "S-8 equals the primary analysis for this arm (S-8 changes B3 and B4 only)"
# D-084, DEV-014: one setup-failure rule for B1 and B3. B1's own record of a call that stopped
# its run (benchmark/baselines/bare_model.py SETUP_FAILURE_FILE, beside labels/), and B3's
# reply record of a generate call that failed for want of memory or of its pinned kernel
# (scripts/final_models.py GenerationOutOfMemory.kind, AttentionKernelRefused.kind, written by
# agent_wrapper as `error_category` with `backend_ok` false).
SETUP_FAILURE_ARMS = ("B1", "B3")
B1_SETUP_FAILURE_FILE = "b1_setup_failure.json"
B3_SETUP_FAILURE_KINDS = ("out_of_memory", "attention_kernel_refused")
SETUP_FAILURE_BASIS = "setup_failure"
S7_SETUP_BASIS = "s7_setup_failure_abstain"
EXCLUDED_BASES = (OVER_CONTEXT_BASIS, SETUP_FAILURE_BASIS)


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
    figure-audit rule of section 5.1 has no per-benchmark switch: it is one rule for all
    five benchmarks. `attribute_as_named` is for B's synthetic tests alone (section 13):
    their rules are written so that a figure-audit record goes to the rule the key names
    (docs/INPUT_FORMAT.md section 9), so every record decides the item of the rule it names
    and nothing is set aside (S-3 then equals the primary)."""

    def __init__(self, name, labels, b1_labels, absence_flag=False, s2=True,
                 unit_evidence=False, attribute_as_named=False):
        self.attribute_as_named = attribute_as_named
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


def read_rule_map(run_dir) -> tuple:
    """(map, status): the run's own registry id to operator id map, keys and values folded
    for comparison, and whether it can be used. Status `missing` (no file), `unreadable`
    (not JSON, or no `by_rule` object), `not_one_to_one` (two registry ids, compared without
    regard to case, name one operator id, or one registry id is listed twice) or `ok`. The
    map is {} unless the status is `ok` (open point 12.11, D-078)."""
    path = Path(run_dir).joinpath(*RULE_ID_MAP_FILE)
    if not path.is_file():
        return {}, RULE_MAP_MISSING
    data, _ = _read_json(path)
    by_rule = data.get("by_rule") if isinstance(data, dict) else None
    if not isinstance(by_rule, dict):
        return {}, RULE_MAP_UNREADABLE
    pairs = [(_fold(k), _fold(v.get("source_rule_id"))) for k, v in by_rule.items()
             if isinstance(v, dict) and v.get("source_rule_id")]
    keys = [k for k, _v in pairs]
    values = [v for _k, v in pairs]
    if len(set(keys)) != len(keys) or len(set(values)) != len(values):
        return {}, RULE_MAP_NOT_ONE_TO_ONE
    return dict(pairs), RULE_MAP_OK


def read_over_context(run_dir) -> dict:
    """Section 5.3 (D-058 condition v; open point 12.14): the run's model calls over their
    model's context, read from every reply record under audit/model_replies/ (one JSON file
    per call, scripts/reply_records.py). Counts only: the reply records read, those that
    carry a `context` object, those whose `context.over_context` is true, those by agent,
    and the files that could not be read (an adapter fault, never a silent zero)."""
    folder = Path(run_dir).joinpath(*REPLY_RECORDS_DIR)
    out = {"reply_records": 0, "records_with_context": 0, "over_context_calls": 0,
           "over_context_by_agent": {}, "unreadable_records": 0}
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.json")):
        record, _error = _read_json(path)
        if not isinstance(record, dict):
            out["unreadable_records"] += 1
            continue
        out["reply_records"] += 1
        context = record.get(REPLY_CONTEXT_FIELD)
        if not isinstance(context, dict):
            continue
        out["records_with_context"] += 1
        if context.get(OVER_CONTEXT_FIELD) is True:
            out["over_context_calls"] += 1
            agent = str(record.get("agent") or "")
            out["over_context_by_agent"][agent] = out["over_context_by_agent"].get(agent, 0) + 1
    out["over_context_by_agent"] = dict(sorted(out["over_context_by_agent"].items()))
    return out


def read_b3_setup_failure(run_dir):
    """D-084, DEV-014: the B3 run's calls that failed out of memory or on a refused attention
    kernel, read from its reply records (`backend_ok` false and `error_category` one of
    B3_SETUP_FAILURE_KINDS). None when there is none; else {calls, by_kind, by_agent}."""
    folder = Path(run_dir).joinpath(*REPLY_RECORDS_DIR)
    if not folder.is_dir():
        return None
    by_kind, by_agent = {}, {}
    for path in sorted(folder.glob("*.json")):
        record, _error = _read_json(path)
        if not isinstance(record, dict) or record.get("backend_ok") is not False:
            continue
        kind = str(record.get("error_category") or "")
        if kind not in B3_SETUP_FAILURE_KINDS:
            continue
        by_kind[kind] = by_kind.get(kind, 0) + 1
        agent = str(record.get("agent") or "")
        by_agent[agent] = by_agent.get(agent, 0) + 1
    if not by_kind:
        return None
    return {"calls": sum(by_kind.values()), "by_kind": dict(sorted(by_kind.items())),
            "by_agent": dict(sorted(by_agent.items()))}


def read_b1_setup_failure(b1_dir):
    """D-084, DEV-014: B1's own record of a call that stopped its run on this document
    (`<b1 output>/b1_setup_failure.json`), or None. An unreadable file is still a setup
    failure (kind `unreadable_record`): the run stopped and said so."""
    path = Path(b1_dir) / B1_SETUP_FAILURE_FILE
    if not path.is_file():
        return None
    record, _error = _read_json(path)
    if not isinstance(record, dict):
        return {"kind": "unreadable_record", "item_id": None}
    return {"kind": str(record.get("kind") or ""), "item_id": record.get("item_id")}


def read_run(run_dir, document_id, source=records.REVIEW_DATA) -> dict:
    """{failure, failure_reasons, records, raw_judged_absence, pairing_refusals, faults,
    source, semantic_incomplete, judging_calls, rule_map, rule_map_status, completeness} for one document's
    run, its typed records read by the one record reader (common/records.py) from
    `source`: `review_data` (B2) or `bus` (B3, B4). A run failure (section 0) is a
    completion record that is absent, invalid or not `completed`, or a record source that
    is missing or unreadable (review_data.json for B2, the bus for B3), except (D-066) a
    run that reached its end with exit code 0 and semantic_complete false."""
    run = Path(run_dir)
    rule_map, rule_map_status = read_rule_map(run)
    out = {"failure": False, "failure_reasons": [], "records": [], "pairing_refusals": [],
           "faults": [], "raw_judged_absence": [], "source": source, "semantic_incomplete": False,
           "judging_calls": [], "rule_map": rule_map, "rule_map_status": rule_map_status}
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


SEGMENT_ARMS = ("B3", "B4")   # the arms that read a long document in segments (common/segments.py)
SEGMENT_FAULT = "segment_unit_not_in_segment"


def read_segmented_run(run_dir, document_id, segment_records, source=records.BUS) -> dict:
    """One document's run when B3 read it in segments (common/segments.py, D-S13 item 7): one
    run folder whose targets are the segment documents. Each segment is read by `read_run`
    under its own document id and the results are pooled into one run, as if the document
    had been one: the records of every segment, each record's `unit_id` translated from the
    segment's unit id to the document's (a unit id no segment part carries is kept as it is,
    and counted as a fault), the pairing-map refusal entries and judging calls of every
    segment, a failure if the run failed (completion and rule map are the run's own, read
    once per segment and equal), semantically incomplete if any segment is, and the
    completeness counts summed. `segments` lists each segment's own reading."""
    from . import segments as segment_rule
    parts = []
    for record in segment_records:
        sid = record["segment_id"]
        run = read_run(run_dir, sid, source)
        translate = {k.casefold(): v for k, v in segment_rule.unit_map(record).items()}
        unknown = 0
        pooled = []
        for r in run["records"]:
            unit = r.get("unit_id")
            if unit and str(unit).casefold() in translate:
                r = dict(r, unit_id=translate[str(unit).casefold()], segment_unit_id=unit)
            elif unit:
                unknown += 1
            pooled.append(r)
        if unknown:
            run["faults"].append("%s:%s:%d" % (SEGMENT_FAULT, sid, unknown))
        parts.append((sid, dict(run, records=pooled)))
    first = parts[0][1]
    out = dict(first, records=[], pairing_refusals=[], judging_calls=[], raw_judged_absence=[],
               faults=[], failure_reasons=list(first["failure_reasons"]))
    for sid, run in parts:
        out["records"].extend(run["records"])
        out["pairing_refusals"].extend(run["pairing_refusals"])
        out["judging_calls"].extend(run["judging_calls"])
        out["raw_judged_absence"].extend(run["raw_judged_absence"])
        out["faults"].extend("%s: %s" % (sid, f) for f in run["faults"])
        for reason in run["failure_reasons"]:
            if reason not in out["failure_reasons"]:
                out["failure_reasons"].append(reason)
        out["semantic_incomplete"] = out["semantic_incomplete"] or run["semantic_incomplete"]
    out["failure"] = bool(out["failure_reasons"])
    out["completeness"] = _pooled_completeness([run["completeness"] for _sid, run in parts])
    out["segments"] = [{"segment_id": sid, "failure": run["failure"], "records": len(run["records"]),
                        "semantic_incomplete": run["semantic_incomplete"]} for sid, run in parts]
    out["segment_runs"] = parts
    return out


# completeness values `completeness` reads for the whole run, not per document: one
# segment's reading is the run's
RUN_WIDE_COMPLETENESS = ("semantic_complete", "partial_delivery_pairs")


def _pooled_completeness(rows) -> dict:
    """One document's completeness from its segments': the run-wide values as read once,
    the per-document counts summed, a per-document flag true if any segment's is (None
    wherever a segment's reading is None)."""
    out = {}
    for key in rows[0]:
        values = [r.get(key) for r in rows]
        if key in RUN_WIDE_COMPLETENESS:
            out[key] = values[0]
        elif any(v is None for v in values):
            out[key] = None
        elif all(isinstance(v, bool) for v in values):
            out[key] = any(values)
        else:
            out[key] = sum(values)
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
    when the bundle has more than one rule (section 5.1), on every benchmark alike; never
    on B's synthetic tests (`attribute_as_named`, section 13)."""
    return int(rule_count) > 1 and not getattr(spec, "attribute_as_named", False)


def python_only_view(run: dict) -> dict:
    """S-8 (DEV-012): the run as if every record a model wrote were absent. Only the
    records stamped `written_by` exactly `python` are kept (is_computed); a record with any
    other stamp or none is dropped. Everything else the run carries (the failure, the
    pairing-map refusal entries and judging calls, the rule-id map, completeness) is kept,
    so the lines of section 5.1 apply unchanged to what remains."""
    view = dict(run, records=[r for r in run["records"] if is_computed(r)])
    if "segment_runs" in run:       # a document B3 read in segments: each segment's own view
        view["segment_runs"] = [(sid, python_only_view(part)) for sid, part in run["segment_runs"]]
    return view


def _layer(records) -> str:
    kinds = {"computed" if is_computed(r) else "judged" for r in records}
    return kinds.pop() if len(kinds) == 1 else ("both" if kinds else "")


# ---------------------------------------------------------------------------
# the mapping


def item_calls_failed(rule_id: str, run: dict):
    """D-066: (applies, reason). True when the run's pairing map records at least one
    judging call for the item's rule and every one has outcome reply_failed. A judging call
    names the registry id, so it is matched to the item's operator id through the run's own
    map (open point 12.11, adopted by D-078). Where the run's map is missing the reason is
    `not_applied_no_rule_map`; unreadable or not one to one, `not_applied_rule_map_<status>`;
    with the switch off, `not_applied_rule_map_unsettled`, with `:would_apply` where it
    would have applied."""
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
        status = run.get("rule_map_status") or RULE_MAP_MISSING
        return False, ("not_applied_no_rule_map" if status in (RULE_MAP_MISSING, RULE_MAP_OK)
                       else "not_applied_rule_map_" + status)
    return (True, "applied") if all_failed else (False, None)


def names_rule(entry: dict, rid: str, run: dict) -> bool:
    """Whether a pairing-map entry names the item's rule (`rid`, folded): by an operator id
    it carries itself (PAIRING_RULE_FIELDS), or, with the map adopted (open point 12.11,
    D-078), by a registry id the run's own map takes to that operator id."""
    named = [_fold(entry.get(f)) for f in PAIRING_RULE_FIELDS if entry.get(f)]
    if rid in named:
        return True
    if not RULE_ID_MAP_ADOPTED:
        return False
    rule_map = run.get("rule_map") or {}
    return any(rule_map.get(n) == rid for n in named)


def _from_partial_delivery(run, deciding) -> bool:
    """D-066: a deciding record posted by an agent that reads the PROCESSOR's delivery, in a
    run whose delivery was partial."""
    if not (run.get("completeness") or {}).get("processor_delivery_partial"):
        return False
    return any(str(r.get(records.ENVELOPE_AGENT_FIELD) or r.get("agent") or "") in DRAFT_READERS
               for r in deciding)


def deciding_view(records) -> list:
    """The fields of the records that decided a FLAG which a location and reason check
    reads (B's synthetic tests, section 13): record id, unit, relation, field label,
    the two figures and the written_by stamp."""
    return [{"record_id": r.get(RECORD_ID_FIELD), "unit_id": r.get("unit_id"),
             "relation": r.get("relation"),
             "field_label": r.get("field_label") or r.get("stated_field"),
             "value_a": r.get("value_a"), "value_b": r.get("value_b"),
             "written_by": r.get(WRITTEN_BY_FIELD)} for r in records]


def classify(spec: Spec, rule_id: str, run: dict, rule_count: int = 1,
             attribute_figure_audit: bool = False, refusal_first: bool = False,
             detail: bool = False) -> dict:
    """The class of one item from one document's run (sections 5.1, 5.2). `rule_count` is
    the number of rules in the item's bundle; with more than one, Python's figure-audit
    records attributed by shared words decide nothing unless `attribute_figure_audit`
    (sensitivity S-3). `refusal_first` is sensitivity S-5: a refusal before an ok record.
    D-066: an item no record decides is ABSTAIN (`item_calls_failed`) instead of silent
    when every judging call for its rule failed (item_calls_failed above). `detail` adds
    `deciding_records` (deciding_view) to a FLAG, for B's synthetic tests (section 13)."""
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
        e for e in run["pairing_refusals"] if names_rule(e, rid, run)]
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
        if detail:
            row["deciding_records"] = deciding_view(deciding) if cls == FLAG else []
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


def unattached_of(run: dict, rule_ids, run_dir, document_id, set_aside_figure_audit=False) -> dict:
    """`unattached` for a document's run; for a document B3 read in segments, summed over
    its segments, each counted on its own records and its own deliverables."""
    if "segment_runs" not in run:
        return unattached(run, rule_ids, run_dir, document_id, set_aside_figure_audit)
    rows = [unattached(part, rule_ids, run_dir, sid, set_aside_figure_audit)
            for sid, part in run["segment_runs"]]
    per_file = {}
    for name in DELIVERABLE_FILES:
        shown = [r["per_deliverable"].get(name) for r in rows]
        per_file[name] = None if all(v is None for v in shown) else sum(v or 0 for v in shown)
    return {"count": sum(r["count"] for r in rows),
            "without_record_id": sum(r["without_record_id"] for r in rows),
            "figure_audit": sum(r["figure_audit"] for r in rows), "per_deliverable": per_file}


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


def label_pipeline_arm(spec: Spec, items, runs_root, arm="B3", run_dirs=None,
                       detail=False, segments=None) -> dict:
    """B3, B2 (and B4): `<runs_root>/<document id>/` is that document's run folder (or
    `run_dirs[document id]` where a map is given, B's synthetic tests), its
    typed records read from RECORD_SOURCE[arm] by the one record reader. Each
    row also carries its sensitivity S-3 class (figure-audit records attributed) and its
    S-5 class (a refusal before an ok record). For B3 (OVER_CONTEXT_ARMS) a document whose
    run made a model call over its model's context is excluded (section 5.3, open point
    12.14): every item of it carries basis over_context_excluded in every analysis but S-7,
    which scores it ABSTAIN. For B3 (SETUP_FAILURE_ARMS) a document whose run had a call fail
    out of memory or on a refused kernel is a setup failure (D-084): basis setup_failure,
    the same treatment. `detail` adds each FLAG's deciding records (section 13).
    `segments` ({document id: its segment records from parts.json}) names the documents
    B3 read in segments (SEGMENT_ARMS, common/segments.py): their run is read by
    `read_segmented_run`, and a call over the context or a setup failure in any segment
    excludes the whole document."""
    rows, documents = [], []
    source = RECORD_SOURCE.get(arm, records.REVIEW_DATA)
    for doc_id, doc_items in by_document(items).items():
        run_dir = Path(run_dirs[doc_id]) if run_dirs is not None else Path(runs_root) / doc_id
        segmented = (segments or {}).get(doc_id) if arm in SEGMENT_ARMS else None
        run = (read_segmented_run(run_dir, doc_id, segmented, source) if segmented
               else read_run(run_dir, doc_id, source))
        over = read_over_context(run_dir) if arm in OVER_CONTEXT_ARMS else None
        setup = read_b3_setup_failure(run_dir) if arm in SETUP_FAILURE_ARMS else None
        over_excluded = bool(over and over["over_context_calls"])
        setup_excluded = bool(setup) and not over_excluded
        faults = list(run["faults"])
        if over and over["unreadable_records"]:
            faults.append("reply_record_unreadable:%d" % over["unreadable_records"])
        rules = [i["rule_id"] for i in doc_items]
        count = len({_fold(r) for r in rules})
        # S-8 (DEV-012): B3 and B4 also labelled with every model-written record absent
        python_run = python_only_view(run) if arm in S8_ARMS else None
        for item in doc_items:
            if over_excluded or setup_excluded:
                gone = {"class": ABSTAIN,
                        "basis": OVER_CONTEXT_BASIS if over_excluded else SETUP_FAILURE_BASIS}
                row = dict(_row(spec, item, arm, gone), s3=dict(gone, cited_unit_ids=[], layer=""),
                           s5=dict(gone, cited_unit_ids=[], layer=""))
                if python_run is not None:
                    row["s8"] = dict(gone, cited_unit_ids=[], layer="")
                if detail:
                    row["deciding_records"] = []
                    for key in ("s3", "s5", "s8"):
                        if key in row:
                            row[key]["deciding_records"] = []
                rows.append(row)
                continue
            primary = classify(spec, item["rule_id"], run, count, detail=detail)
            row = _row(spec, item, arm, primary)
            if detail:
                row["deciding_records"] = primary.get("deciding_records", [])
            variants = [("s3", run, {"attribute_figure_audit": True}),
                        ("s5", run, {"refusal_first": True})]
            if python_run is not None:
                variants.append(("s8", python_run, {}))
            for key, source_run, options in variants:
                other = classify(spec, item["rule_id"], source_run, count, detail=detail, **options)
                row[key] = {"class": other["class"], "basis": other["basis"],
                            "cited_unit_ids": other["cited_unit_ids"], "layer": other["layer"]}
                if detail:
                    row[key]["deciding_records"] = other.get("deciding_records", [])
            rows.append(row)
        aside = set_aside(spec, count)
        documents.append({"document_id": doc_id, "run_failure": run["failure"],
                          "failure_reasons": run["failure_reasons"], "faults": faults,
                          "record_source": source,
                          # section 5.3, open point 12.14: None where the arm is not checked
                          "over_context": over, "over_context_excluded": over_excluded,
                          # D-084, DEV-014: None where the arm is not checked or none failed
                          "setup_failure": setup, "setup_failure_excluded": setup_excluded,
                          "items": len(doc_items),
                          # D-066: completeness, per document and arm; decides no label
                          "semantic_incomplete": run["semantic_incomplete"],
                          "completeness": run["completeness"],
                          "rule_map_adopted": RULE_ID_MAP_ADOPTED,
                          "rule_map_status": run["rule_map_status"],
                          # a judged absence's raw model copy: listed, never counted
                          "raw_judged_absence_records": len(run["raw_judged_absence"]),
                          "rules": count, "figure_audit_set_aside": aside,
                          "unattached": unattached_of(run, rules, run_dir, doc_id, aside),
                          "unattached_s3": unattached_of(run, rules, run_dir, doc_id, False),
                          # S-8: the unattached findings Python wrote (None where S-8 changes nothing)
                          "unattached_s8": (unattached_of(python_run, rules, run_dir, doc_id, aside)
                                            if python_run is not None else None),
                          "relations": relation_counts(run, rules),
                          "missing_field_by_layer": None if run["failure"] else missing_field_layers(run, rules)})
        if segmented:
            documents[-1]["b3_segments"] = run["segments"]
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


def label_b1(spec: Spec, items, runs_root, run_dirs=None) -> dict:
    """B1: `<runs_root>/<document id>/labels/<item id>.json` (or under `run_dirs[document
    id]`), written by bare_model.py. A document whose B1 output holds its setup-failure
    record (D-084, DEV-014) is a setup failure: every item ABSTAIN with basis setup_failure,
    counted apart and left out of B1's scoring in every analysis but S-7."""
    rows, documents = [], []
    for doc_id, doc_items in by_document(items).items():
        base = Path(run_dirs[doc_id]) if run_dirs is not None else Path(runs_root) / doc_id
        folder = base / B1_LABELS_DIR
        setup = read_b1_setup_failure(base) if "B1" in SETUP_FAILURE_ARMS else None
        for item in doc_items:
            if setup is not None:
                rows.append(_row(spec, item, "B1", {"class": ABSTAIN, "basis": SETUP_FAILURE_BASIS}))
                continue
            path = folder / (str(item["item_id"]) + ".json")
            record, _ = _read_json(path) if path.is_file() else (None, "missing")
            rows.append(_row(spec, item, "B1", b1_class(spec, record)))
        documents.append({"document_id": doc_id, "run_failure": False, "failure_reasons": [],
                          "faults": [], "unattached": None, "relations": {},
                          "items": len(doc_items), "setup_failure": setup,
                          "setup_failure_excluded": setup is not None})
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
        # an item excluded for a call over the model's context or for a setup failure is not
        # scored, so not an abstention
        "abstain": sum(1 for r in rows if r["label"] == ABSTAIN and r["basis"] not in EXCLUDED_BASES),
        # section 5.3, open point 12.14 (D-078)
        "over_context_excluded_documents": sum(1 for d in documents if d.get("over_context_excluded")),
        "items_over_context_excluded": sum(1 for r in rows if r["basis"] == OVER_CONTEXT_BASIS),
        "items_s7_over_context_abstain": sum(1 for r in rows if r["basis"] == S7_BASIS),
        # D-084, DEV-014: setup failures, B1 and B3 alike, counted apart
        "setup_failure_documents": sum(1 for d in documents if d.get("setup_failure_excluded")),
        "items_setup_failure": sum(1 for r in rows if r["basis"] == SETUP_FAILURE_BASIS),
        "items_s7_setup_failure_abstain": sum(1 for r in rows if r["basis"] == S7_SETUP_BASIS),
        "documents_rule_map_unusable": sum(1 for d in documents
                                           if d.get("rule_map_status") not in (None, RULE_MAP_OK)),
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
    excluded = [d for d in documents if d.get("over_context_excluded")]
    over_context = {
        "checked": arm in OVER_CONTEXT_ARMS,
        "documents": len(excluded),
        "items": sum(int(d.get("items") or 0) for d in excluded),
        "excluded_documents": [{"document_id": d["document_id"], "items": d.get("items"),
                                "over_context_calls": (d.get("over_context") or {}).get("over_context_calls"),
                                "over_context_by_agent": (d.get("over_context") or {}).get("over_context_by_agent")}
                               for d in excluded]}
    failed = [d for d in documents if d.get("setup_failure_excluded")]
    setup_failure = {
        "checked": arm in SETUP_FAILURE_ARMS,
        "documents": len(failed),
        "items": sum(int(d.get("items") or 0) for d in failed),
        "failed_documents": [{"document_id": d["document_id"], "items": d.get("items"),
                              "setup_failure": d.get("setup_failure")} for d in failed]}
    return {"benchmark": spec.name, "arm": arm, "analysis": analysis, "counts": counts,
            "over_context": over_context, "setup_failure": setup_failure, "labels": rows,
            "documents": documents}


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


def sensitivity_s8(spec: Spec, result: dict) -> dict:
    """S-8 (DEV-012): B3 and B4 scored as if every record written by a model were absent:
    an item a model-written record decides takes the next record in section 5.1's order,
    else silence (python_only_view, then the same lines). The unattached findings are
    Python's alone. B0, B1 and B2 rows are unchanged, so S-8 equals their primary analysis,
    and the result says which (`s8_applies`, `note`)."""
    applies = result["arm"] in S8_ARMS
    documents = [dict(d, unattached=d["unattached_s8"]) if applies and d.get("unattached_s8") is not None
                 else d for d in result["documents"]]
    out = _alternative(spec, result, "s8", "S-8", documents)
    out["s8_applies"] = applies
    out["note"] = S8_NOTE_APPLIED if applies else S8_NOTE_EQUAL
    return out


def sensitivity_s6(spec: Spec, result: dict) -> dict:
    """S-6 (D-066): every item of a semantically incomplete document ABSTAIN, for every
    pipeline arm; B0 and B1 rows, and every complete document, unchanged. The primary
    comparison restricted to complete documents reads `semantic_incomplete` per document."""
    incomplete = {d["document_id"] for d in result["documents"] if d.get("semantic_incomplete")}
    return _relabel(spec, result, "S-6", lambda r: (ABSTAIN, "s6_semantic_incomplete")
                    if r["arm"] in PIPELINE_ARMS + ("B2",) and r["document_id"] in incomplete
                    and r["basis"] not in EXCLUDED_BASES else None)


_S7_BASES = {OVER_CONTEXT_BASIS: S7_BASIS, SETUP_FAILURE_BASIS: S7_SETUP_BASIS}


def sensitivity_s7(spec: Spec, result: dict) -> dict:
    """S-7 (section 5.3, open point 12.14, D-078; D-084): every item of a B3 document excluded
    for a model call over its model's context, and every item of a B1 or B3 document with a
    setup failure, is scored ABSTAIN, so the arm is reported on all documents; every other
    item, and every other arm, unchanged."""
    return _relabel(spec, result, "S-7", lambda r: (ABSTAIN, _S7_BASES[r["basis"]])
                    if r["basis"] in _S7_BASES else None)


def over_context_excluded(result: dict) -> set:
    """The documents of one arm's labels excluded for a call over the model's context."""
    return {d["document_id"] for d in result.get("documents") or [] if d.get("over_context_excluded")}


def setup_failure_excluded(result: dict) -> set:
    """D-084, DEV-014: the documents of one arm's labels left out for a setup failure."""
    return {d["document_id"] for d in result.get("documents") or [] if d.get("setup_failure_excluded")}


def excluded_documents(result: dict) -> set:
    """Every document one arm's scoring leaves out (every analysis but S-7): a call over the
    model's context (B3) and a setup failure (B1, B3)."""
    return over_context_excluded(result) | setup_failure_excluded(result)


def restrict(spec: Spec, result: dict, gone, analysis=None) -> dict:
    """One arm's labels without the documents in `gone` (rows and document rows), counts
    recomputed; the documents left out are listed."""
    gone = set(gone)
    rows = [r for r in result["labels"] if r["document_id"] not in gone]
    documents = [d for d in result.get("documents") or [] if d["document_id"] not in gone]
    out = _labels(spec, result["arm"], rows, documents, analysis or result.get("analysis", "primary"))
    for key in ("left_out_items",):
        if key in result:
            out[key] = result[key]
    out["documents_left_out"] = sorted(gone & {r["document_id"] for r in result["labels"]})
    return out


def scored_view(spec: Spec, result: dict) -> dict:
    """What is scored of one analysis: every analysis but S-7 leaves out the items of a
    document excluded for a call over the model's context (section 5.3) or for a setup
    failure (D-084); S-7 keeps them, as ABSTAIN."""
    if result.get("analysis") == "S-7":
        return result
    gone = excluded_documents(result)
    return restrict(spec, result, gone) if gone else result


def read_items(path) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("items") if isinstance(data, dict) else data
    for row in rows:
        for key in ("item_id", "document_id", "rule_id"):
            if not row.get(key):
                raise ValueError("an item lacks " + key)
    return rows

