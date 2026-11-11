#!/usr/bin/env python3
"""Where expected findings are lost: one loss table over many scored runs.

Recall and F1 cannot be raised by guessing where the misses happen. This tool takes
(run, answer key) pairs, scores each run with tools/score_corpus.py (the only reader
of a key), and puts every expected finding the run did not produce, or produced for
the wrong reason, into one loss class:

  EVIDENCE_PRESENT_IN_MODEL_PAYLOAD, EVIDENCE_PRESENT_UPSTREAM_BUT_NOT_IN_PAYLOAD,
  EVIDENCE_ABSENT_FROM_CORPUS, UNKNOWN
      a missed entry, classified by scripts/fn_evidence.py from the run's saved
      artifacts; UNKNOWN always carries the reason it could not be decided
  SUSPENDED_FOR_UNIT
      missed, and the run's pairing map records the rule withdrawn for that unit by
      its own [unless: ...] condition (the scorer's review state), so the key and the
      rule's condition disagree
  LOCATED_WRONG_REASON
      located on the right unit and relation, but no finding states the key's claim
  LOCATED_REASON_UNVERIFIABLE
      located, the key states a claim, and the artifact that located it carries no
      typed reason
  RUN_EXCLUDED_OR_FAILED
      an adapter benchmark item the adapter's own labeller excluded (a call over the
      model's context, a setup failure) or whose run failed

An adapter item with no evidence unit is told apart by the fields
benchmark/adapters/common/bundle.py writes on it into the key:
  - `evidence_beyond_cut`: UNKNOWN (evidence_cut_undecided), never "absent from the
    corpus". The key does not say whether a marked part was kept only up to mid-text
    (bundle.py drops an index into a part not kept whole, so the unit is in the run and
    the evidence may sit in its kept head), nor whether another marked text matched no
    part at all, so the evidence may still be in the document the run read.
  - `location_measurable` absent: UNKNOWN (item_location_unstated); the key cannot tell
    a whole-document item from one whose evidence matched no part.
  - `location_measurable` true: the gold marks a location that matched no part, UNKNOWN
    (item_evidence_unmatched).
  - `location_measurable` false and nothing cut: the gold marks no location at all, a
    property of the whole document such as something it is said to lack. A
    DOCUMENT-LEVEL item, read over every unit of its own document in the run's pairing
    map; its class is the WEAKEST any unit reached, because its evidence is the whole
    document and so reached a payload only if every unit did, and its sub-cause is read
    over the units of that weakest class only. A run with no pairing map leaves it
    UNKNOWN (no_pairing_map), one whose map lists no unit of the item's document UNKNOWN
    (item_without_evidence_unit), and one whose key marks another item's evidence beyond
    the cut, which shows its document was cut, UNKNOWN (document_level_on_cut_document).
LIMIT: an item that marks no location has no `evidence_beyond_cut` of its own, and the
bundle's parts record (which says whether a document was cut) is neither in the run nor
in the key. So a cut that removed the evidence of such an item is invisible unless
another item of the same key was marked beyond the cut: a document-level item on a cut
document whose other items say nothing of the cut is read over its units as if whole.
On a benchmark whose items never mark a location (CUAD and SciTab today) no item can
carry the mark, so a cut is never seen there at all.

Each loss also gets a SUB-CAUSE read from the same saved artifacts (the pairing map's
pair status and reason, its not_judged, absence and judging_calls lists, the call
evidence, the reply outcomes) and the code sites that decide it, resolved to file and
line in this checkout at the time of the run, so the table says which lines would
need changing. A site that no longer resolves is printed as NOT FOUND, never guessed.

What it reads, per pair:
  a run folder (holding logs/ and audit/), a cloud session or batch entry folder
  (downloaded/evidence/run, or its collected_evidence.tar.gz), or a
  collected_evidence.tar.gz itself. An archive is unpacked into a temporary folder,
  members under evidence/ only, regular files only, no absolute or parent paths; a
  model reply record (audit/model_replies/) is written with its status and context
  counts only (REPLY_RECORD_FIELDS), never its payload or reply text. A B1 entry
  (evidence/b1, no pipeline run folder) is reported as not scored, with the reason.

It never opens a key itself (the scorer does, through score_corpus.score's result),
never calls a model and never uses the network. Standard library only.

    py -3.12 -X utf8 tools/miss_diagnosis.py --out-dir OUT \\
        --pair <run folder | session folder | collected_evidence.tar.gz> <answer_key.json> [--pair ...]
    py -3.12 -X utf8 tools/miss_diagnosis.py --out-dir OUT --pairs pairs.json
        (pairs.json: [{"run": ..., "key": ..., "family": optional label}, ...])
    py -3.12 -X utf8 tools/miss_diagnosis.py --out-dir OUT --session <session folder> --key-root <folder>
        (every batch/<NN>_<item>_<arm>/ entry holding collection_integrity.json, its key at
         <key-root>/<item>/answer_key.json)

Writes OUT/miss_diagnosis.json, OUT/miss_diagnosis.md and the scorer's own printout per
run under OUT/scorer/, and prints the Markdown table. OUT must lie outside the
repository or under its output/ folder: the scorer's printout carries the key's figures.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT / "scripts"), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import call_evidence  # noqa: E402
import fn_evidence  # noqa: E402

SCHEMA_VERSION = 1

SUSPENDED = "SUSPENDED_FOR_UNIT"
WRONG_REASON = "LOCATED_WRONG_REASON"
UNVERIFIABLE = "LOCATED_REASON_UNVERIFIABLE"
EXCLUDED = "RUN_EXCLUDED_OR_FAILED"
LOSS_CLASSES = fn_evidence.CLASSES + (SUSPENDED, WRONG_REASON, UNVERIFIABLE, EXCLUDED)
# fn_evidence's order of strength, for an item whose evidence spans several units: the
# strongest class any of them reached is the item's class.
_STRENGTH = (fn_evidence.PRESENT_IN_PAYLOAD, fn_evidence.PRESENT_UPSTREAM,
             fn_evidence.ABSENT_FROM_CORPUS, fn_evidence.UNKNOWN)

# Sub-cause -> the code that decides it: (file, a line's exact text fragment). Resolved
# to file:line in this checkout by `site`; a fragment that no longer occurs is reported
# NOT FOUND. Never a line number typed here.
SITES = {
    "never_paired_missing_field": [
        ("scripts/pairing_map.py", '"reason": "unit lacks " + ", ".join'),
        ("scripts/pairing_map.py", "def needed_fields("),
        ("scripts/pairing_map.py", "def unit_fields(")],
    "never_paired_scope_field": [
        ("scripts/pairing_map.py", '"reason": "unit lacks the declared scope field "'),
        ("scripts/pairing_map.py", "def scope_declaration(")],
    "never_paired_scope_value": [
        ("scripts/pairing_map.py", "does not carry the value the rule's scope declares"),
        ("scripts/pairing_map.py", "def unit_field_values(")],
    "never_paired_undecided": [
        ("scripts/pairing_map.py", "ambiguous.append(rid)"),
        ("scripts/pairing_map.py", "def needed_fields(")],
    "no_pairing_entry": [("scripts/pairing_map.py", "def pair_units(")],
    "paired_not_judged": [
        ("scripts/pipeline.py", "def _not_judged_reason("),
        ("scripts/pipeline.py", "def _paired_judging_agent("),
        ("scripts/convention_assignment.py", "def assign_conventions(")],
    "paired_absence_computed": [
        ("scripts/paired_review.py", "def plan_calls("),
        ("scripts/paired_review.py", "def absent_checks(")],
    "paired_judging_call_not_recorded": [("scripts/agent_wrapper.py", "call_evidence.record(")],
    "paired_computed_no_irregularity": [
        ("scripts/paired_review.py", "def compute_checks("),
        ("scripts/paired_review.py", "def plan_calls(")],
    "relation_python_never_writes": [
        ("scripts/finding_record.py", "def relations("),
        ("tools/score_corpus.py", "NEVER_WRITTEN_RELATIONS = ("),
        ("tools/miss_diagnosis.py", "def written_after_run(")],
    "near_miss_other_relation": [
        ("scripts/paired_review.py", "def compute_checks("),
        ("scripts/finding_record.py", "def is_finding(")],
    "exposed_reply_failed": [
        ("scripts/agent_wrapper.py", "def parse_contract_output("),
        ("scripts/agent_wrapper.py", "def _contract_missing("),
        ("scripts/paired_review.py", "def judging_call_record(")],
    "exposed_uncomputable_nothing_kept": [
        ("scripts/paired_review.py", "def stamp_from_plan("),
        ("scripts/paired_review.py", "def judged_item_refusal(")],
    "exposed_uncomputable_refused": [
        ("scripts/paired_review.py", "def judged_item_refusal("),
        ("scripts/paired_review.py", "def refuses_judged_absence("),
        ("scripts/pipeline.py", "refused_uncomputable.append({")],
    "exposed_absence_refused": [("scripts/paired_review.py", "def judged_item_refusal(")],
    "exposed_python_found_no_disagreement": [("scripts/paired_review.py", "def compute_checks(")],
    "exposed_whole_document_only": [("scripts/pipeline.py", "async def phase_5_5_convention_review(")],
    "exposed_reply_kept_no_matching_finding": [
        ("scripts/pipeline.py", "async def _paired_convention_review("),
        ("scripts/paired_review.py", "def plan_calls(")],
    "unit_not_in_document": [("scripts/pairing_map.py", "def split_units(")],
    "rule_not_loaded": [("scripts/convention_parser.py", "def _parse_text_lines(")],
    "rule_unmappable": [("scripts/finding_record.py", "def source_rule_id_for(")],
    "no_pairing_map": [("scripts/pairing_map.py", "def write_pairing_map(")],
    "run_predates_call_evidence": [("scripts/agent_wrapper.py", "call_evidence.record(")],
    "suspended_by_condition": [
        ("scripts/pipeline.py", 'pairing["suspended"] = ['),
        ("scripts/convention_parser.py", "def _unless_entries(")],
    "wrong_reason_relation": [("scripts/paired_review.py", "def compute_checks(")],
    "wrong_reason_field_label": [("scripts/pairing_map.py", "def header_label("),
                                 ("scripts/paired_review.py", "def compute_checks(")],
    "wrong_reason_figures": [("scripts/paired_review.py", "def compute_checks(")],
    "reason_untyped_amendment": [("scripts/paired_review.py", "def ensure_amendments_for_findings(")],
    "multi_round_unscoped": [("scripts/fn_evidence.py", "def resolve_units(")],
    "round_row_not_unit_rule": [("scripts/fn_evidence.py", "def classify(")],
    "item_without_evidence_unit": [("benchmark/adapters/common/bundle.py", "def _evidence_units("),
                                   ("tools/miss_diagnosis.py", "def document_units(")],
    "item_evidence_unmatched": [("benchmark/adapters/common/bundle.py", "def _evidence_units("),
                                ("benchmark/adapters/common/bundle.py", '"location_measurable": bool(')],
    "item_location_unstated": [("benchmark/adapters/common/bundle.py", '"location_measurable": bool('),
                               ("tools/score_corpus.py", '"location_measurable": i.get("location_measurable")')],
    "evidence_cut_undecided": [("benchmark/adapters/common/bundle.py", '"evidence_beyond_cut": len(everywhere)'),
                               ("benchmark/adapters/common/bundle.py", "def _evidence_units("),
                               ("benchmark/adapters/common/cut.py", "def cut_parts(")],
    "document_level_on_cut_document": [
        ("benchmark/adapters/common/bundle.py", '"evidence_beyond_cut": len(everywhere)'),
        ("tools/score_corpus.py", '"evidence_beyond_cut": bool(i.get("evidence_beyond_cut"))'),
        ("tools/miss_diagnosis.py", "def cut_document(")],
    "excluded_over_context": [("benchmark/adapters/common/mapping.py", "def read_over_context(")],
    "excluded_setup_failure": [("benchmark/adapters/common/mapping.py", "def read_b3_setup_failure(")],
    "run_failed": [("benchmark/adapters/common/mapping.py", "def read_completion(")],
    "unknown_other": [("scripts/fn_evidence.py", "def classify(")],
}


def site(path, fragment):
    """'path:line' of the first line of `path` (repository relative) holding `fragment`."""
    try:
        lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return "%s: NOT FOUND (file missing)" % path
    for n, line in enumerate(lines, 1):
        if fragment in line:
            return "%s:%d" % (path, n)
    return "%s: NOT FOUND (%s)" % (path, fragment)


def sites_for(sub_cause):
    return [site(p, f) for p, f in SITES.get(sub_cause, SITES["unknown_other"])]


# ---------------------------------------------------------------------------
# finding the run folder


# The fields of a model reply record (audit/model_replies/<NNNNNN>_<call id>.json) that
# a reader of this tool's inputs uses: the benchmark adapters' over-context and setup
# failure readers (benchmark/adapters/common/mapping.py read_over_context,
# read_b3_setup_failure). The payload and reply text are never unpacked.
REPLY_RECORD_FIELDS = ("schema_version", "sequence", "call_id", "agent", "backend", "phase",
                       "doc_id", "backend_ok", "error_category", "context")


def _is_reply_record(parts):
    return "model_replies" in parts and parts[-1].endswith(".json")


def _safe_members(archive):
    """Members to unpack: regular files and folders under evidence/, no absolute or
    parent path. A model reply record is listed too, and `unpack` writes only its
    REPLY_RECORD_FIELDS."""
    out = []
    for m in archive.getmembers():
        name = PurePosixPath(m.name)
        if name.is_absolute() or ".." in name.parts or not name.parts or name.parts[0] != "evidence":
            continue
        if not (m.isfile() or m.isdir()):
            continue
        out.append(m)
    return out


def unpack(archive_path, into):
    into.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:*") as archive:
        members = _safe_members(archive)
        plain = [m for m in members if not (m.isfile() and _is_reply_record(PurePosixPath(m.name).parts))]
        try:
            archive.extractall(into, members=plain, filter="data")
        except TypeError:  # an interpreter without extraction filters
            archive.extractall(into, members=plain)
        for m in members:
            if m in plain:
                continue
            try:
                record = json.loads(archive.extractfile(m).read().decode("utf-8"))
            except (OSError, ValueError, AttributeError):
                record = None
            target = into.joinpath(*PurePosixPath(m.name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            kept = ({k: record[k] for k in REPLY_RECORD_FIELDS if k in record}
                    if isinstance(record, dict) else "unreadable reply record")
            target.write_text(json.dumps(kept), encoding="utf-8")
    return into


def _is_run_folder(path):
    return (path / "logs" / "agent_bus.jsonl").is_file() or (path / "audit").is_dir()


def _run_in_evidence(evidence):
    """The pipeline's run folder inside an `evidence/` folder: evidence/run, else the
    one folder holding audit/run_completion.json or logs/agent_bus.jsonl."""
    if _is_run_folder(evidence / "run"):
        return evidence / "run", None
    found = sorted({p.parent.parent for pat in ("audit/run_completion.json", "logs/agent_bus.jsonl")
                    for p in evidence.rglob(pat)})
    if len(found) == 1:
        return found[0], None
    if len(found) > 1:
        return None, "%d run folders under %s; name one" % (len(found), evidence)
    if (evidence / "b1").is_dir():
        return None, ("B1 arm: the bare-model baseline writes no pipeline run folder "
                      "(evidence/b1); its items are labelled by benchmark/adapters/<name>/adapter.py "
                      "label --arm B1")
    return None, "no pipeline run folder under %s" % evidence


def _entry_identity(folder):
    """(item, arm) from a batch entry's seal_entry.json, else the manifest's arm."""
    for name in ("seal_entry.json", "execution_manifest.json"):
        p = folder / name
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                return data.get("item"), data.get("arm") or ("B3" if name == "execution_manifest.json" else None)
    return None, None


def resolve_run(given, workdir):
    """{run_dir or None, how, reason, item, arm} for one run argument."""
    path = Path(given)
    out = {"run_dir": None, "how": "", "reason": "", "item": None, "arm": None}
    if path.is_file() and path.name.endswith(".tar.gz"):
        out["item"], out["arm"] = _entry_identity(path.parent)
        root = unpack(path, workdir)
        out["how"] = "archive"
        out["run_dir"], out["reason"] = _run_in_evidence(root / "evidence")
        return out
    if not path.is_dir():
        out["reason"] = "not a folder or a .tar.gz archive: %s" % path
        return out
    out["item"], out["arm"] = _entry_identity(path)
    if _is_run_folder(path):
        out["run_dir"], out["how"] = path, "run folder"
    elif (path / "downloaded" / "evidence").is_dir():
        out["how"] = "downloaded"
        out["run_dir"], out["reason"] = _run_in_evidence(path / "downloaded" / "evidence")
    elif (path / "collected_evidence.tar.gz").is_file():
        root = unpack(path / "collected_evidence.tar.gz", workdir)
        out["how"] = "archive"
        out["run_dir"], out["reason"] = _run_in_evidence(root / "evidence")
    else:
        out["reason"] = "no run folder, downloaded/evidence or collected_evidence.tar.gz in %s" % path
    return out


# ---------------------------------------------------------------------------
# scoring, through the scorer only


def score_through_scorer(run_dir, key_path):
    """score_corpus.score on one run, its printout captured: (result, printout, refusal)."""
    import score_corpus
    result, buf = {}, io.StringIO()
    saved = list(sys.path)
    try:
        with contextlib.redirect_stdout(buf):
            score_corpus.score(str(key_path), str(run_dir), key_path=str(key_path), result=result)
        return result, buf.getvalue(), None
    except SystemExit as exc:
        return result, buf.getvalue(), str(exc.code)
    finally:
        sys.path[:] = saved


# ---------------------------------------------------------------------------
# sub-causes, from saved artifacts only


def _jsonl(path):
    out = []
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def load_artifacts(run_dir):
    arts = fn_evidence.load_run_artifacts(run_dir)
    outcomes = {}
    for row in _jsonl(Path(run_dir) / "audit" / "model_replies" / "outcomes.jsonl"):
        if row.get("call_id"):
            outcomes[row["call_id"]] = row.get("outcome")  # a later line replaces an earlier one
    arts["reply_outcomes"] = outcomes
    return arts


def written_after_run(arts, relation):
    """RELATIONS-A: a relation constitution amendment INFRA-045 appended to the Finding
    record, on a run made before it. Every paired review since INFRA-045 writes
    `relation_refusals` (empty or not) into each document of its pairing map, so a run
    whose pairing map has documents and none carries it was made by code that could not
    write the relation. A run with no pairing map tells nothing and is not read as older."""
    import relation_checks
    if relation not in relation_checks.RELATIONS:
        return False
    docs = [e for e in (arts.get("pairing") or {}).values() if isinstance(e, dict)]
    return bool(docs) and not any("relation_refusals" in e for e in docs)


def _doc_lists(arts, key):
    for _doc, entry in (arts.get("pairing") or {}).items():
        for row in (entry.get(key) if isinstance(entry, dict) else None) or []:
            if isinstance(row, dict):
                yield row


def _reason_kind(why):
    why = str(why or "")
    if why.startswith("relation"):
        return "wrong_reason_relation", "the located finding states another relation"
    if why.startswith("field"):
        return "wrong_reason_field_label", "the located finding names another field label"
    if why.startswith("figures"):
        return "wrong_reason_figures", "the located finding states other figures"
    return "wrong_reason_figures", "no located finding states the key's reason"


def refused_calls(unkept):
    """The uncomputable judging rows that kept nothing and report refusing at least one
    answer (`judged_refused`): a row that refused nothing left nothing to refuse."""
    out = []
    for j in unkept:
        try:
            if int(j.get("judged_refused") or 0) > 0:
                out.append(j)
        except (TypeError, ValueError):
            continue
    return out


def uncomputable_refusals(arts, rule_id, unit_ids):
    """{reason: count} of the pairing map's `uncomputable_refused` rows for this rule on
    these units only. A refusal row carries no call id, so this is the refusals on the
    call's unit and rule, not on the call itself."""
    refused = {}
    for row in _doc_lists(arts, "uncomputable_refused"):
        if row.get("rule_id") == rule_id and row.get("unit_id") in unit_ids:
            why = str(row.get("reason") or "no reason recorded")
            refused[why] = refused.get(why, 0) + 1
    return refused


def refine(cls, ev, arts, relations_on_unit, key_relation):
    """(sub_cause, detail) for one missed entry, from the artifacts fn_evidence read."""
    units = list(ev.get("unit_ids") or [])
    rid = ev.get("registry_rule_id")
    basis = list(ev.get("basis") or [])
    others = [r for r in relations_on_unit if r and r != key_relation]
    if cls == fn_evidence.ABSENT_FROM_CORPUS:
        if not units:
            return "unit_not_in_document", "the key's unit is not a unit of the parsed document"
        return "rule_not_loaded", "the run never loaded the rule"
    if cls == fn_evidence.UNKNOWN:
        text = " ".join(basis)
        if "no audit/pairing_map.json" in text:
            return "no_pairing_map", "the run saved no pairing map"
        if "maps to no registry id" in text:
            return "rule_unmappable", "no saved artifact maps the key's rule to a registry id"
        if "predates the recording" in text or "not on record" in text:
            return "run_predates_call_evidence", "a pair was planned and the run saved no call evidence"
        return "unknown_other", basis[-1] if basis else "not decidable from saved artifacts"
    if others:
        return "near_miss_other_relation", ("a finding on the unit carries %s, the key states %s"
                                            % (", ".join(others), key_relation or "no relation"))
    calls = []
    for uid in units:
        calls.extend(call_evidence.calls_exposing(arts.get("evidence") or [], rule_id=rid, unit_id=uid))
    judging = [j for j in _doc_lists(arts, "judging_calls")
               if j.get("rule_id") == rid and j.get("unit_id") in units]
    if cls == fn_evidence.PRESENT_IN_PAYLOAD:
        ids = {c.get("call_id") for c in calls}
        outcomes = {arts["reply_outcomes"].get(i) for i in ids}
        jout = {j.get("outcome") for j in judging if j.get("call_id") in ids or not j.get("call_id")}
        if "reply_failed" in jout or outcomes & {"backend_failure", "contract_violation"}:
            return "exposed_reply_failed", "the call failed or its reply broke the contract"
        if any(j.get("plan_kind") == "absence_judged" and j.get("absence_refused") for j in judging):
            return "exposed_absence_refused", "a judged absence was answered and Python refused the answer"
        unkept = [j for j in judging if j.get("plan_kind") == "uncomputable" and not j.get("judged_listed")]
        if unkept:
            # decided from the same judging row: a call that kept nothing AND reports refusing
            # answers; its reasons are the refusals recorded on that call's unit and rule (a
            # refusal row carries no call id, so it is not joined to the call itself)
            refused = uncomputable_refusals(arts, rid, {j.get("unit_id") for j in refused_calls(unkept)})
            if refused:
                return "exposed_uncomputable_refused", (
                    "Python could compute nothing for the pair, the model answered, and Python refused "
                    "the answer (refusals recorded on that call's unit and rule: %s)" % "; ".join("%s: %d" % (w, n) for w, n in sorted(refused.items())))
            return "exposed_uncomputable_nothing_kept", ("Python could compute nothing for the pair and "
                                                         "the model's answer left no kept record")
        if "no_finding_to_attach" in jout:
            return "exposed_python_found_no_disagreement", ("Python computed the pair, found no "
                                                            "disagreement, and the note had nothing to attach to")
        if calls and all(c.get("unit_id") is None for c in calls):
            return "exposed_whole_document_only", "shown only inside an unclipped whole-document call"
        return "exposed_reply_kept_no_matching_finding", ("the unit and rule reached a call whose reply "
                                                          "carried no finding with the key's relation")
    # PRESENT_UPSTREAM: the pair status the pairing map recorded
    statuses = [fn_evidence._pair_status(arts, uid, rid) for uid in units]
    kinds = [k for k, _r in statuses]
    if "paired" in kinds:
        if any(r.get("rule_id") == rid and r.get("unit_id") in units for r in _doc_lists(arts, "not_judged")):
            row = next(r for r in _doc_lists(arts, "not_judged")
                       if r.get("rule_id") == rid and r.get("unit_id") in units)
            return "paired_not_judged", "paired, no agent could take it: %s" % (row.get("reason") or row.get("status"))
        if any(a.get("rule_id") == rid and a.get("unit_id") in units and a.get("path") == "computed"
               for a in _doc_lists(arts, "absence")):
            return "paired_absence_computed", "paired, Python decided the declared absence and found none"
        if judging:
            return "paired_judging_call_not_recorded", ("the pairing map records a judging call for the "
                                                        "pair and logs/call_evidence.jsonl records none")
        import score_corpus
        if key_relation and score_corpus.unwritten_relations([{"relation": key_relation}]):
            return "relation_python_never_writes", ("paired and never put to a model, and the key's "
                                                    "relation %s is not one the Finding record declares, "
                                                    "so Python cannot write it" % key_relation)
        if key_relation and written_after_run(arts, key_relation):
            return "relation_python_never_writes", ("paired and never put to a model, and the key's "
                                                    "relation %s was not one the Finding record declared "
                                                    "when this run was made (INFRA-045 appended it later), "
                                                    "so Python could not write it" % key_relation)
        return "paired_computed_no_irregularity", ("paired, Python computed it, found no irregularity, "
                                                   "and planned no model call")
    for k, reason in statuses:
        if k == "rejected":
            if reason.startswith("unit lacks the declared scope field"):
                return "never_paired_scope_field", reason
            if "does not carry the value the rule's scope declares" in reason:
                return "never_paired_scope_value", reason
            return "never_paired_missing_field", reason
    if "undecided" in kinds:
        return "never_paired_undecided", "the rule names no field label of the document"
    return "no_pairing_entry", "the pairing map holds no entry for the unit and rule"


# ---------------------------------------------------------------------------
# document-level adapter items

# The `unit` a document-level item's loss row names: it is read over every unit.
DOCUMENT_LEVEL = "document"


def document_level(item):
    """Whether an adapter item with no evidence unit is a property of the whole document:
    its gold marks no location (`location_measurable` false, as bundle.py writes it) and
    none of its evidence was cut. An item whose evidence fell beyond the cut, or whose
    marked evidence matched no part, also has no evidence unit and is not one."""
    return item.get("location_measurable") is False and not item.get("evidence_beyond_cut")


def cut_document(bench):
    """Whether the key shows its document was cut: some item of it is marked
    `evidence_beyond_cut`. An item that marks no location cannot be marked so itself."""
    return any(i.get("evidence_beyond_cut") for i in (bench or {}).get("items") or [])


def document_units(arts, document_id):
    """Every unit id the run's pairing map lists for `document_id` (the map's key or its
    entry's document_id), in its order, each once. A document-level item is a property of
    its whole document, so these are the units it is read over; [] when the run saved no
    pairing map or the map lists no unit of that document."""
    out = []
    for doc, entry in ((arts or {}).get("pairing") or {}).items():
        if not isinstance(entry, dict) or document_id not in (doc, entry.get("document_id")):
            continue
        for u in entry.get("units") or []:
            uid = u.get("unit_id") if isinstance(u, dict) else None
            if isinstance(uid, str) and uid and uid not in out:
                out.append(uid)
    return out


def document_level_class(rule, units, arts):
    """fn_evidence's class of a document-level item: every unit classified under the item's
    rule, and the WEAKEST class any unit reached is the item's. Its evidence is the whole
    document, so it reached a model's payload only if every unit did (the opposite of a
    located item, whose strongest unit decides). The basis counts the units per class and
    keeps the first weakest unit's own basis. `unit_ids` are the units of the weakest class
    only, so a sub-cause is read over them and never over a unit that reached further;
    `units_read` are all of them."""
    rows = [fn_evidence.classify({"unit": uid, "rule": rule}, arts) for uid in units]
    weakest = max(rows, key=lambda ev: _STRENGTH.index(ev["class"]))
    counts = {}
    for ev in rows:
        counts[ev["class"]] = counts.get(ev["class"], 0) + 1
    basis = ["document-level item: %d units read, %s; the weakest class is the item's"
             % (len(units), ", ".join("%s %d" % (c, counts[c]) for c in _STRENGTH if c in counts))]
    return {"class": weakest["class"], "units_read": list(units),
            "unit_ids": [uid for uid, ev in zip(units, rows) if ev["class"] == weakest["class"]],
            "registry_rule_id": next((ev["registry_rule_id"] for ev in rows if ev.get("registry_rule_id")), None),
            "basis": basis + list(weakest.get("basis") or [])}


# ---------------------------------------------------------------------------
# one run's losses


def cut_item_loss():
    """(class, sub-cause, detail) of an item with no evidence unit marked beyond the cut.
    Never EVIDENCE_ABSENT_FROM_CORPUS: bundle.py drops an index into a part kept only up
    to mid-text (cut.cut_parts keeps the first part so when even it does not fit), and a
    marked text that matched no part leaves the same record, so the key cannot say the
    evidence is outside the document the run read."""
    return (fn_evidence.UNKNOWN, "evidence_cut_undecided",
            "the key marks the item's evidence beyond the cut and names no unit, but does not "
            "record whether a marked part was kept only up to mid-text or a marked text matched "
            "no part, so the evidence may still be in the document the run read")


def unstated_location_loss():
    """(sub-cause, detail) of an item with no evidence unit whose key does not state
    `location_measurable`."""
    return ("item_location_unstated", "the key does not say whether the gold marks a location, so a "
            "whole-document item cannot be told from one whose evidence matched no part")


def no_map_loss():
    """(sub-cause, detail) of a document-level item on a run that saved no pairing map."""
    return "no_pairing_map", "the run saved no pairing map, so the document's units are not on record"


def _entry_view(e):
    keep = ("unit", "rule", "relation", "kind", "round_id", "document_id", "field_label", "item_id")
    return {k: e[k] for k in keep if isinstance(e, dict) and e.get(k) not in (None, "")}


def losses_for_run(result, run_dir):
    """(losses, caught) for one scored run, from the scorer's result and the run's artifacts."""
    losses, caught = [], {"location": 0, "reason_confirmed": 0}
    path = result.get("path")
    arts = load_artifacts(run_dir) if path == "ordinary" else None

    def add(entry, cls, sub, detail, basis=()):
        losses.append({"entry": _entry_view(entry), "loss_class": cls, "sub_cause": sub,
                       "detail": detail, "basis": list(basis), "cause_sites": sites_for(sub)})

    for row in result.get("entries") or []:
        e = row.get("entry") or {}
        if row.get("found"):
            caught["location"] += 1
            ok = row.get("reason_ok")
            if ok is True:
                caught["reason_confirmed"] += 1
            elif ok is False:
                sub, detail = _reason_kind(row.get("reason_why"))
                add(e, WRONG_REASON, sub, detail)
            elif isinstance(e, dict) and e.get("claim"):
                add(e, UNVERIFIABLE, "reason_untyped_amendment",
                    "located through an amendment that carries no typed reason")
            continue
        if path == "rounds":
            add(e, fn_evidence.UNKNOWN, "round_row_not_unit_rule",
                "a round-comparison row (%s) names a field label and relation, not a unit and rule; "
                "fn_evidence classifies (unit, rule) pairs" % row.get("status"))
            continue
        if path == "multi_round":
            add(e, fn_evidence.UNKNOWN, "multi_round_unscoped",
                "a multi-round entry is scoped by round and document; fn_evidence resolves a unit "
                "with neither, so a class from it would not be evidence")
            continue
        if row.get("review_state") == "suspended":
            add(e, SUSPENDED, "suspended_by_condition",
                "the rule's own condition withdrew it for this unit (audit/pairing_map.json suspended)")
            continue
        ev = row.get("evidence") or {}
        cls = ev.get("class") or fn_evidence.UNKNOWN
        sub, detail = refine(cls, ev, arts, row.get("relations_on_unit") or [], str(e.get("relation") or ""))
        add(e, cls, sub, detail, ev.get("basis") or [])
    bench = result.get("benchmark_items")
    false_alarms = 0
    if isinstance(bench, dict) and bench.get("availability") == "labelled":
        arts = arts or load_artifacts(run_dir)
        flag = bench.get("flag")
        for item in bench.get("items") or []:
            entry = {"item_id": item["item_id"], "rule": item["rule_id"]}
            if item.get("gold_class") != flag:
                false_alarms += item.get("b3_class") == flag and item.get("gold_class") == bench.get("clear")
                continue
            if item.get("b3_class") == flag:
                caught["location"] += 1
                caught["reason_confirmed"] += 1
                continue
            basis = str(item.get("basis") or "")
            if basis in (bench.get("excluded_bases") or []) or bench.get("run_failure"):
                sub = ("excluded_over_context" if basis == bench.get("over_context_basis") else
                       "excluded_setup_failure" if basis == bench.get("setup_failure_basis") else
                       "run_failed")
                add(entry, EXCLUDED, sub, "adapter basis %s%s" % (
                    basis, ("; run failure: " + ", ".join(bench.get("failure_reasons") or []))
                    if bench.get("run_failure") else ""))
                continue
            units = item.get("evidence_unit_ids") or []
            if not units:
                if not document_level(item):
                    if item.get("evidence_beyond_cut"):
                        cls, sub, detail = cut_item_loss()
                        add(entry, cls, sub, "%s (adapter basis %s)" % (detail, basis))
                    elif item.get("location_measurable") is None:
                        add(entry, fn_evidence.UNKNOWN, *unstated_location_loss())
                    else:
                        add(entry, fn_evidence.UNKNOWN, "item_evidence_unmatched",
                            "the gold marks evidence and none of it matched a part of the document "
                            "as built")
                    continue
                if (arts or {}).get("pairing") is None:
                    add(entry, fn_evidence.UNKNOWN, *no_map_loss())
                    continue
                if cut_document(bench):
                    add(entry, fn_evidence.UNKNOWN, "document_level_on_cut_document",
                        "a document-level item, and another item of the key is marked beyond the cut, "
                        "so its document was cut and its evidence may lie in what was removed "
                        "(adapter basis %s)" % basis)
                    continue
                units = document_units(arts, bench.get("document_id"))
                if not units:
                    add(entry, fn_evidence.UNKNOWN, "item_without_evidence_unit",
                        "a document-level item, and the run's pairing map lists no unit of its "
                        "document to read it over")
                    continue
                ev = document_level_class(item["rule_id"], units, arts)
                sub, detail = refine(ev["class"], ev, arts, [], "")
                add(dict(entry, unit=DOCUMENT_LEVEL), ev["class"], sub,
                    "document-level item read over all %d units (%d of the weakest class): %s "
                    "(adapter basis %s)" % (len(units), len(ev["unit_ids"]), detail, basis), ev["basis"])
                continue
            best = None
            for uid in units:
                ev = fn_evidence.classify({"unit": uid, "rule": item["rule_id"]}, arts)
                if best is None or _STRENGTH.index(ev["class"]) < _STRENGTH.index(best["class"]):
                    best = ev
            sub, detail = refine(best["class"], best, arts, [], "")
            add(dict(entry, unit=",".join(units)), best["class"], sub,
                "%s (adapter basis %s)" % (detail, basis), best["basis"])
    return losses, caught, false_alarms


# ---------------------------------------------------------------------------
# the table


def _count(rows, field="loss_class"):
    out = {}
    for r in rows:
        out[r[field]] = out.get(r[field], 0) + 1
    return out


def aggregate(runs, losses):
    overall = {c: 0 for c in LOSS_CLASSES}
    overall.update(_count(losses))
    by_family = {}
    for r in losses:
        fam = by_family.setdefault(r["family"], {c: 0 for c in LOSS_CLASSES})
        fam[r["loss_class"]] += 1
    groups = {}
    for r in losses:
        g = groups.setdefault((r["loss_class"], r["sub_cause"], r["detail"]),
                              {"loss_class": r["loss_class"], "sub_cause": r["sub_cause"],
                               "detail": r["detail"], "count": 0, "families": [], "relations": {},
                               "kinds": {}, "examples": [], "cause_sites": r["cause_sites"]})
        g["count"] += 1
        for field, into in (("relation", "relations"), ("kind", "kinds")):
            value = r["entry"].get(field)
            if value:
                g[into][value] = g[into].get(value, 0) + 1
        if r["family"] not in g["families"]:
            g["families"].append(r["family"])
        if len(g["examples"]) < 5:
            g["examples"].append({"run": r["run"], **r["entry"]})
    top = sorted(groups.values(), key=lambda g: (-g["count"], g["loss_class"], g["sub_cause"], g["detail"]))
    expected = sum(int(r.get("expected") or 0) for r in runs if r.get("scored"))
    return {"overall": overall, "by_family": dict(sorted(by_family.items())),
            "by_sub_cause": dict(sorted(_count(losses, "sub_cause").items())),
            "expected_entries_scored": expected, "losses": len(losses), "top_causes": top}


def render_markdown(report, top_n=15):
    a = report["aggregate"]
    out = ["# Miss diagnosis", "",
           "Every expected finding a scored run did not produce, or produced for the wrong reason, "
           "in one loss class. Read from saved artifacts through tools/score_corpus.py; no model "
           "was called.", "",
           "Runs: %d given, %d scored. Expected entries scored: %d. Losses: %d."
           % (len(report["runs"]), sum(1 for r in report["runs"] if r["scored"]),
              a["expected_entries_scored"], a["losses"]), ""]
    out += ["## Runs", "", "| run | family | arm | path | expected | caught (location) | caught (reason) "
            "| losses | false positives | note |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in report["runs"]:
        out.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["label"], r["family"], r.get("arm") or "", r.get("path") or "", r.get("expected", ""),
            r.get("caught_location", ""), r.get("caught_reason_confirmed", ""), r.get("losses", ""),
            r.get("false_positives", ""), (r.get("note") or "").replace("|", "/")))
    fams = list(a["by_family"])
    out += ["", "## Loss classes", "", "| loss class | all | " + " | ".join(fams) + " |",
            "|---|---|" + "---|" * len(fams)]
    for c in LOSS_CLASSES:
        out.append("| %s | %d | %s |" % (c, a["overall"].get(c, 0),
                                       " | ".join(str(a["by_family"][f].get(c, 0)) for f in fams)))
    out += ["", "## Top causes", "", "| count | loss class | sub-cause | detail | families | planted kinds "
            "| code sites |", "|---|---|---|---|---|---|---|"]
    for g in a["top_causes"][:top_n]:
        kinds = ", ".join("%s %d" % (k, n) for k, n in sorted(g["kinds"].items(), key=lambda kv: (-kv[1], kv[0])))
        out.append("| %d | %s | %s | %s | %s | %s | %s |" % (
            g["count"], g["loss_class"], g["sub_cause"], g["detail"].replace("|", "/"),
            ", ".join(g["families"]), kinds.replace("|", "/"), "<br>".join(g["cause_sites"])))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# driver


def _refuse_out_dir(out_dir):
    out = Path(out_dir).resolve()
    try:
        rel = out.relative_to(ROOT)
    except ValueError:
        return None
    if rel.parts and rel.parts[0] == "output":
        return None
    return ("--out-dir %s is inside the repository: the scorer's printout carries the key's "
            "figures. Use a folder outside it or under output/" % out)


def pairs_from_session(session, key_root):
    pairs = []
    for entry in sorted((Path(session) / "batch").glob("*")):
        if not (entry / "collection_integrity.json").is_file():
            continue
        item, arm = _entry_identity(entry)
        key = Path(key_root) / str(item) / "answer_key.json" if item else None
        pairs.append({"run": str(entry), "key": str(key) if key else "", "label": entry.name,
                      "arm": arm, "item": item})
    if not pairs:
        raise SystemExit("no collected batch entry (batch/*/collection_integrity.json) in %s; "
                         "use --pair for a single run" % session)
    return pairs


def diagnose(pairs, out_dir):
    out_dir = Path(out_dir)
    (out_dir / "scorer").mkdir(parents=True, exist_ok=True)
    runs, losses = [], []
    with tempfile.TemporaryDirectory(prefix="shimmer_miss_diagnosis_") as td:
        for n, pair in enumerate(pairs):
            label = pair.get("label") or "%02d_%s" % (n, Path(pair["run"]).name)
            row = {"label": label, "run_input": str(pair["run"]), "key": str(pair.get("key") or ""),
                   "family": pair.get("family") or "", "scored": False}
            found = resolve_run(pair["run"], Path(td) / ("%02d" % n))
            row.update(how=found["how"], arm=pair.get("arm") or found["arm"],
                       item=pair.get("item") or found["item"])
            if found["run_dir"] is None:
                row["note"] = "not scored: " + found["reason"]
            elif not pair.get("key") or not Path(pair["key"]).is_file():
                row["note"] = "not scored: no answer key at %s" % (pair.get("key") or "(none given)")
            else:
                result, printout, refusal = score_through_scorer(found["run_dir"], pair["key"])
                (out_dir / "scorer" / (label + ".txt")).write_text(printout + (
                    "\nREFUSED: %s\n" % refusal if refusal else ""), encoding="utf-8")
                if refusal:
                    row["note"] = "not scored: the scorer refused: %s" % refusal
                else:
                    run_losses, caught, false_alarms = losses_for_run(result, found["run_dir"])
                    row["family"] = row["family"] or result.get("family") or "unlabelled"
                    bench = result.get("benchmark_items") or {}
                    expected = (len(result.get("entries") or []) + sum(
                        1 for i in bench.get("items") or [] if i.get("gold_class") == bench.get("flag")))
                    checkable = bool(result.get("claims_stated")) or bool(bench.get("items"))
                    row.update(scored=True, path=result.get("path"), expected=expected,
                               caught_location=caught["location"],
                               caught_reason_confirmed=caught["reason_confirmed"] if checkable
                               else "n/a (the key states no claim)",
                               losses=len(run_losses),
                               false_positives=int(result.get("false_positives") or 0) + false_alarms,
                               distractor_hits=result.get("distractor_hits"))
                    if isinstance(bench, dict) and bench.get("availability") not in (None, "labelled"):
                        row["note"] = "benchmark items not labelled: %s" % bench["availability"]
                    elif bench:
                        row["note"] = "benchmark items read from the %s" % bench.get("read")
                    for loss in run_losses:
                        losses.append(dict(loss, run=label, family=row["family"]))
            row["family"] = row["family"] or "unlabelled"
            runs.append(row)
    report = {"schema_version": SCHEMA_VERSION, "tool": "tools/miss_diagnosis.py",
              "loss_classes": list(LOSS_CLASSES), "runs": runs, "losses": losses,
              "aggregate": aggregate(runs, losses)}
    (out_dir / "miss_diagnosis.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")
    md = render_markdown(report)
    (out_dir / "miss_diagnosis.md").write_text(md, encoding="utf-8")
    return report, md


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pair", nargs=2, action="append", metavar=("RUN", "KEY"), default=[],
                    help="a run folder, session or batch entry folder, or collected_evidence.tar.gz, "
                         "and its answer key")
    ap.add_argument("--pairs", help="a JSON list of {run, key, family?}")
    ap.add_argument("--session", help="a cloud session folder whose batch/ entries are scored")
    ap.add_argument("--key-root", help="with --session: the key of item X is <key-root>/X/answer_key.json")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    refusal = _refuse_out_dir(a.out_dir)
    if refusal:
        ap.error(refusal)
    if (a.session is None) != (a.key_root is None):
        ap.error("--session and --key-root are given together")
    pairs = [{"run": r, "key": k} for r, k in a.pair]
    if a.pairs:
        data = json.loads(Path(a.pairs).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            ap.error("--pairs must hold a JSON list")
        pairs += [dict(p) for p in data if isinstance(p, dict) and p.get("run")]
    if a.session:
        pairs += pairs_from_session(a.session, a.key_root)
    if not pairs:
        ap.error("nothing to diagnose: give --pair, --pairs or --session")
    _report, md = diagnose(pairs, a.out_dir)
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
