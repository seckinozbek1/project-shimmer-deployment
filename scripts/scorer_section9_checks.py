"""Gate check: the scorer reads the three key parts D-042 added (loop S5, open item 17).

docs/INPUT_FORMAT.md section 9 gives an answer key three parts tools/score_corpus.py did
not read: `expected_refusals` (a renamed term the system should refuse, with its refusal
kind, or match as a rename), the multi-round key (planted and clean entries scoped by
round and document), and the four relations Python never writes (unit_mismatch,
rate_mismatch, copy_mismatch, carry_mismatch). The scorer counted a matched rename's
record as a false positive, could not score a multi-round run at all, and dropped every
record carrying one of the four relations before matching (finding_record.is_finding
does not read them), so such an entry could only ever be missed.

Every case EXECUTES the scorer's main() on synthetic run folders written into temporary
folders:

1. expected refusals: a negotiation-style key with seven renamed terms (refused with the
   expected kind; refused with another kind; refused where none is expected and matched
   as a rename by Python; a fabricated withdrawal; matched only by a model-written
   computed record, which satisfies nothing and stays a false positive; refused under
   another unit; orphaned) and a run whose review_data.json and bus hold exactly those
   records, with one stray refusal of an unlisted label;
2. a multi-round run: its bus lines are written by multi_round_rounds.post_findings itself
   (the real posting code, through a recording wrapper), from a two-round record holding
   a planted flaw, a flaw found with the wrong figures, a flaw found only in another
   round, a model-written item on the multi_round channel, a clean distractor and a
   finding on an unkeyed unit, beside audit/multi_round.json and a completion record;
   and three key forms: a key with no multi-round entries on that run (refused), a key
   whose top-level clean entries alone carry round_id (scored), and that key on an
   ordinary run (refused, input format section 12 item 4);
3. the relations Python never writes: a single-version key with one entry located by a
   model-written record whose reason matches, one whose only record sits on a Python post
   with an amendment of another relation on its unit, and one with nothing. Since
   constitution amendment INFRA-045 (RELATIONS-A, 2026-10-31) the Finding record declares
   all four, so this case scores the fixture under the record as it was before it (the
   section is about a record that does not declare a key's relation), and scores it again
   under the current record, where the four are ordinary relations: Python's record and a
   model's locate their entries, and no section is printed;
4. judged absences (issue #32, D-184): a judged-absence call whose raw reply carries two
   answers, one kept (Python's stamped copy also on the bus) and one refused, with a flaw
   planted on each answer's unit: only the stamped copy is read (one typed finding, the
   refused answer locating nothing), and the raw records and the refused answer are counted
   apart.

Each is proven by neutralise, fail, restore, pass (scripts/effect_proof.py). No model, no
pipeline run, no provider, no network.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCORER = ROOT / "tools" / "score_corpus.py"

for _path in (str(ROOT / "scripts"), str(ROOT / "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from effect_proof import prove_effect  # noqa: E402
import finding_record  # noqa: E402
import fn_evidence  # noqa: E402,F401
import multi_round_rounds  # noqa: E402


def _scorer():
    import score_corpus
    return score_corpus


def run_scorer(argv):
    """main() on argv: (exit status or refusal text, printed lines)."""
    sc = _scorer()
    out = io.StringIO()
    saved_path = list(sys.path)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            status = sc.main(argv)
    except SystemExit as exc:
        status = "refused: %s" % (exc.code if isinstance(exc.code, str) else "usage")
    finally:
        sys.path[:] = saved_path
    return status, out.getvalue().splitlines()


def _lines(lines, *starts):
    return [ln.rstrip() for ln in lines if ln.startswith(starts)]


def _bus_line(channel, backend, model, doc_id, items):
    return json.dumps({"sender": "fixture", "channel": channel, "body": {
        "event": "AGENT_OUTPUT", "backend": backend, "model": model,
        "payload": {"agent": "fixture", "doc_id": doc_id, "items": items}}})


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _record(relation, unit, **fields):
    rec = {"relation": relation, "record_verdict": fields.pop("verdict", "irregular"),
           "unit_id": unit, "rule_id": fields.pop("rule_id", "CONV-001")}
    rec.update(fields)
    return rec


# ---- 1. expected refusals --------------------------------------------------------------

def _row(label, later, unit_id, kind, a, b, unit):
    return {"field_label": label, "later_field_label": later, "unit_id": unit_id,
            "reason_kind": kind, "value_a": a, "value_b": b, "unit": unit}


def refusal_fixture(root):
    """A negotiation-style key with seven renamed terms and a run that refuses, matches,
    fabricates and orphans them as the rows' comments say."""
    key = {"document": "terms_x.md", "task_given_to_the_pipeline": "fixture",
           "prior_records": [{"field_label": "deposit amount", "relation": "unchanged_from_prior",
                              "value_a": 100, "value_b": 100, "unit": "EUR"}],
           "band_irregularities": [],
           "expected_refusals": [
               # refused on its unit with the expected kind
               _row("rebate threshold", "rebate trigger", "u06-clause-swift", "possible_rename", 61, 61, "EUR"),
               # refused on its unit with another kind
               _row("audit interval", "inspection interval", "u08-clause-jay", "possible_successor", 3, 5, "months"),
               # no refusal expected: refused anyway, and matched as a rename by Python
               _row("payment term", "settlement term", "u04-clause-tern", None, 29, 21, "days"),
               # a fabricated withdrawal (Python's absent_since_prior on the earlier label)
               _row("storage fee", "warehouse fee", "u09-clause-wren", "possible_rename", 7, 7, "EUR"),
               # matched as a rename only by a model-written computed record
               _row("freight rate", "carriage rate", "u10-clause-owl", "possible_rename", 12, 10, "%"),
               # refused, but under another unit
               _row("handling fee", "packing fee", "u11-clause-rook", "possible_rename", 4, 4, "EUR"),
               # orphaned, never refused
               _row("insurance cap", "cover cap", "u13-clause-kestrel", "possible_successor", 9, 5, "EUR")]}
    _write(root / "key" / "answer_key.json", json.dumps(key))
    run = root / "run"
    change = [
        _record("unchanged_from_prior", "u01-clause-a", verdict="ok", provenance="computed",
                field_label="deposit amount", value_a=100, value_b=100, unit_a="EUR", unit_b="EUR"),
        _record("changed_from_prior", "u02-clause-grebe", verdict="ok", provenance="computed",
                field_label="settlement term", value_a=29, value_b=21, unit_a="days", unit_b="days"),
        _record("absent_since_prior", "u09-clause-wren", verdict="ok", provenance="computed",
                field_label="storage fee", value_a=None, value_b=7, unit_b="EUR")]
    model_change = [
        _record("changed_from_prior", "u10-clause-owl", verdict="ok", provenance="computed",
                field_label="carriage rate", value_a=12, value_b=10, unit_a="%", unit_b="%")]
    _write(run / "logs" / "agent_bus.jsonl", "\n".join([
        _bus_line("main", "computed", "python", "terms_x", change),
        _bus_line("main", "cloud", "fixture-model", "terms_x", model_change)]) + "\n")
    _write(run / "deliverables" / "terms_x" / "review_data.json", json.dumps({
        "amendments": [], "prior_comparisons": change,
        "prior_refusals": [
            {"unit_id": "u06-clause-swift", "label": "rebate threshold", "reason": "r",
             "reason_kind": "possible_rename"},
            {"unit_id": "u08-clause-jay", "label": "audit interval", "reason": "r",
             "reason_kind": "possible_rename"},
            {"unit_id": "u04-clause-tern", "label": "payment term", "reason": "r",
             "reason_kind": "possible_successor"},
            {"unit_id": "u12-clause-crane", "label": "handling fee", "reason": "r",
             "reason_kind": "possible_rename"},
            {"unit_id": "u05-clause-kite", "label": "loading charge", "reason": "r",
             "reason_kind": "possible_successor"}],
        "prior_orphans": [{"label": "insurance cap", "unit_slug": "clause-kestrel", "reason": "r",
                           "reason_kind": "orphan"}]}))
    return root / "key" / "answer_key.json", run


def observe_refusals():
    with tempfile.TemporaryDirectory(prefix="shimmer_scorer_refusals_") as td:
        key, run = refusal_fixture(Path(td))
        status, lines = run_scorer(["--key", str(key), "--run", str(run)])
        table = [ln[ln.index(" u") + 1:].rstrip() for ln in lines
                 if ln.startswith("  ") and not ln.startswith("   ") and "-clause-" in ln]
        return {"status": status,
                "lines": _lines(lines, "expected refusals", "  by expected kind", "  renames matched",
                                "false positives", "stray refusals", "recall, exact"),
                "table": table}


REFUSALS = {
    "status": 0,
    "lines": [
        "recall, exact     : 1/1   (label + relation + figures)",
        "false positives   : 2   (a record for a label or relation the key does not give)",
        "stray refusals    : 1   (refusals or orphans for labels the key does not list)",
        "expected refusals : 3/7 satisfied (1 refused with the expected kind, 1 refused with "
        "another kind, 1 matched renames); 1 fabricated withdrawal(s) (absent_since_prior on a "
        "renamed term's earlier label, counted in false positives); not satisfying: 1 refused "
        "where none is expected, 1 refused on another unit, 1 orphaned",
        "  by expected kind  : possible_rename 1/4 satisfied, 1 refused with that kind; "
        "possible_successor 1/2 satisfied, 0 refused with that kind; null 1/1 satisfied (no "
        "refusal expected; only a matched rename satisfies)",
        "  renames matched by a model's record only : 1   (%s; satisfy no row and stay false "
        "positives)" % finding_record.MODEL_FINDING_MARK],
    "table": [
        "u06-clause-swift       possible_rename              refused, possible_rename as expected",
        "u08-clause-jay         possible_successor           refused as possible_rename, OTHER KIND (key: possible_successor)",
        "u04-clause-tern        null                         refused as possible_successor, key expects none; matched rename",
        "u09-clause-wren        possible_rename              FABRICATED WITHDRAWAL",
        "u10-clause-owl         possible_rename              rename matched by a model's record only (not counted)",
        "u11-clause-rook        possible_rename              refused on another unit (u12-clause-crane)",
        "u13-clause-kestrel     possible_successor           orphaned"]}


def refusals_ignored():
    """The key part read as before: no row, no matched rename, no listed label."""
    return patch.object(_scorer(), "read_expected_refusals", lambda *a, **k: ([], []))


def refusal_kind_not_compared():
    """Any refusal counted as the expected kind."""
    sc = _scorer()
    real = sc.read_expected_refusals

    def any_kind(*a, **k):
        results, matched = real(*a, **k)
        for x in results:
            x["kind_ok"] = x["by_refusal"]
        return results, matched
    return patch.object(sc, "read_expected_refusals", any_kind)


def model_rename_counted():
    """A change record matched as a rename whoever wrote it."""
    return patch.object(_scorer(), "python_written", lambda record: True)


def matched_renames_left_in_false_positives():
    """Every row scored as before, but no matched rename removed from false positives."""
    sc = _scorer()
    real = sc.read_expected_refusals
    return patch.object(sc, "read_expected_refusals", lambda *a, **k: (real(*a, **k)[0], []))


def listed_labels_left_stray():
    """Refusals and orphans of listed labels counted as stray refusals."""
    return patch.object(_scorer(), "listed_labels", lambda results, norm_label: set())


# ---- 2. multi-round --------------------------------------------------------------------

class _RecordingWrapper:
    def __init__(self):
        self.lines = []

    def post_to_bus(self, **kwargs):
        self.lines.append(json.dumps({"sender": "PRACTICE_AUDITOR", **kwargs}, default=str))


def multi_round_fixture(root):
    """A two-round run posted by multi_round_rounds.post_findings, and its key."""
    def finding(relation, unit, label, a, b, verdict="irregular"):
        return _record(relation, unit, verdict=verdict, provenance="computed",
                       field_label=label, value_a=a, value_b=b)
    record = {"rounds": [
        {"round_id": "r1", "sequence": 1, "documents": [{"document_id": "doc_a", "findings": [
            finding("above_band", "u01-clause-linnet", "exit charge", 6861, 5000),
            finding("above_band", "u05-clause-jay", "notice period", 98, 60),
            finding("above_band", "u03-clause-nuthatch", "late charge", 9, 5)]}]},
        {"round_id": "r2", "sequence": 2, "documents": [{"document_id": "doc_b", "findings": [
            finding("sum_mismatch", "u01-clause-linnet", "sum line total", 80, 82),
            finding("above_band", "u04-clause-petrel", "liability limit", 66079, 50000)]}]}]}
    wrapper = _RecordingWrapper()
    multi_round_rounds.post_findings(record, wrapper)
    lines = wrapper.lines + [
        # The r1 flaw posted on the ordinary channel: never a round finding.
        _bus_line("main", "paired", "python", "doc_b", [
            finding("above_band", "u02-clause-thrush", "annual fee", 4.6, 4)]),
        # A model's item on the multi_round channel: counted apart, never located.
        _bus_line("multi_round", "cloud", "fixture-model", "doc_b", [
            dict(finding("above_band", "u02-clause-thrush", "annual fee", 4.6, 4), round_id="r2")])]
    run = root / "run"
    _write(run / "logs" / "agent_bus.jsonl", "\n".join(lines) + "\n")
    _write(run / "audit" / "multi_round.json", json.dumps({
        "outcome": "reviewed", "activation": {"activated": True},
        "round_review": {"availability": "recorded"}}))
    _write(run / "audit" / "run_completion.json", json.dumps({
        "schema_version": 1, "state": "completed", "reached_end": True, "exit_code": 0,
        "finished_at": "2026-10-30T00:00:00Z"}))
    (run / "deliverables").mkdir(parents=True)
    claim = lambda rel, label, a, b: {"relation": rel, "field_label": label, "value_a": a, "value_b": b}
    key = {"document": "doc_b.md", "task_given_to_the_pipeline": "fixture",
           "prior_records": [], "band_irregularities": [],
           "multi_round": {
               "planted": [
                   {"round_id": "r1", "document_id": "doc_a", "unit": "u01-clause-linnet",
                    "rule": "CONV-TP", "relation": "above_band", "kind": "breach",
                    "claim": claim("above_band", "exit charge", 6861, 5000)},
                   {"round_id": "r2", "document_id": "doc_b", "unit": "u01-clause-linnet",
                    "rule": "CONV-TS", "relation": "sum_mismatch", "kind": "sum",
                    "claim": claim("sum_mismatch", "sum line total", 80, 81)},
                   {"round_id": "r2", "document_id": "doc_b", "unit": "u02-clause-thrush",
                    "rule": "CONV-TQ", "relation": "above_band", "kind": "breach",
                    "claim": claim("above_band", "annual fee", 4.6, 4)},
                   {"round_id": "r2", "document_id": "doc_b", "unit": "u05-clause-jay",
                    "rule": "CONV-TI", "relation": "above_band", "kind": "breach",
                    "claim": claim("above_band", "notice period", 98, 60)}],
               "clean": [{"round_id": "r1", "document_id": "doc_a", "unit": "u03-clause-nuthatch"}]}}
    _write(root / "key" / "answer_key.json", json.dumps(key))
    return root / "key" / "answer_key.json", run


def observe_multi_round():
    with tempfile.TemporaryDirectory(prefix="shimmer_scorer_rounds_") as td:
        key, run = multi_round_fixture(Path(td))
        status, lines = run_scorer(["--key", str(key), "--run", str(run)])
        return {"status": status,
                "lines": _lines(lines, "multi-round run", "round findings", "recall", "  RIGHT PLACE",
                                "  recall,", "false positives", "distractor hits", "attribution")}


MULTI_ROUND = {
    "status": 0,
    "lines": [
        "multi-round run : HEALTHY: outcome=reviewed, activated=True, round review=recorded, completion=completed",
        "round findings  : 5 on bus channel multi_round written by python; 1 written by a model, not counted",
        "recall          : 2/4   (every planted entry of every round, LOCATION ONLY: round, document, unit and relation)",
        "  RIGHT PLACE, WRONG REASON : 1   (located in the right round, document, unit and relation, "
        "but the finding does not state the key's own reason)",
        "  recall, reason confirmed  : 1/4   (THIS is the figure that says a defect was actually detected)",
        "  recall, round r1          : 1/1",
        "  recall, round r2          : 1/3",
        "  recall, breach               : 1/3",
        "  recall, sum                  : 1/1",
        "false positives : 3   (irregular round findings on a round, document and unit no planted entry names)",
        "distractor hits : 1",
        "attribution     : not checked (round findings carry the registry id only; the case's "
        "conventions are needed to number the rules, input format section 9)"]}


def scope_without_round():
    """A round finding matched on its unit alone, whatever its round and document."""
    sc = _scorer()
    return patch.object(sc, "round_scope", lambda entry, finding: str(entry.get("unit")).lower()
                        in sc._lower(finding.get("unit_id")))


def model_round_items_counted():
    """Every item on the multi_round channel read as Python's."""
    sc = _scorer()
    real = sc.load_round_findings
    return patch.object(sc, "load_round_findings",
                        lambda run_dir: [dict(f, _written_by="python") for f in real(run_dir)])


def multi_round_run_not_detected():
    """The run's audit/multi_round.json not read: the run scored as an ordinary review."""
    return patch.object(_scorer(), "is_multi_round_run", lambda run_dir: False)


def observe_key_forms():
    """Three key forms against the multi-round run and an ordinary run:
    a key with no multi-round entries on the multi-round run (refused); a key that is not
    negotiation-style, its top-level entries scoped by round and only its clean entries
    present (a twin with no planted flaw; scored); the same key on an ordinary run (refused,
    section 12 item 4)."""
    with tempfile.TemporaryDirectory(prefix="shimmer_scorer_forms_") as td:
        root = Path(td)
        _key_path, run = multi_round_fixture(root / "mr")
        _rkey, ordinary = refusal_fixture(root / "ord")
        plain = root / "plain.json"
        _write(plain, json.dumps({"document": "doc_b.md", "task_given_to_the_pipeline": "fixture",
                                  "prior_records": [], "band_irregularities": []}))
        twin = root / "twin.json"
        _write(twin, json.dumps({"document": "doc_b.md", "task_given_to_the_pipeline": "fixture",
                                 "planted": [],
                                 "clean": [{"round_id": "r1", "document_id": "doc_a",
                                            "unit": "u03-clause-nuthatch"}]}))
        none_status, _ = run_scorer(["--key", str(plain), "--run", str(run)])
        twin_status, twin_lines = run_scorer(["--key", str(twin), "--run", str(run)])
        ord_status, _ = run_scorer(["--key", str(twin), "--run", str(ordinary)])
        return {"no_entries": str(none_status).startswith("refused: ")
                and "has no multi-round entries" in str(none_status),
                "top_level": [twin_status] + _lines(twin_lines, "recall          :", "false positives",
                                                    "distractor hits"),
                "ordinary": str(ord_status).startswith("refused: ")
                and "section 12, item 4" in str(ord_status)}


KEY_FORMS = {
    "no_entries": True,
    "top_level": [0, "recall          : 0/0   (every planted entry of every round, LOCATION ONLY: "
                     "round, document, unit and relation)",
                  "false positives : 5   (irregular round findings on a round, document and unit no "
                  "planted entry names)",
                  "distractor hits : 1"],
    "ordinary": True}


def entries_absent_scored_as_empty():
    """A multi-round run whose key has no multi-round entries scored as if it had none."""
    sc = _scorer()
    real = sc.multi_round_entries
    return patch.object(sc, "multi_round_entries", lambda key: real(key) or ([], []))


def top_level_form_from_planted_only():
    """The top-level form detected from planted entries alone, as first written: a twin
    with no planted flaw is not read as a multi-round key."""
    return patch.object(_scorer(), "round_scoped_key", lambda key: any(
        isinstance(p, dict) and "round_id" in p for p in key.get("planted") or []))


def round_scoped_key_scored_on_an_ordinary_run():
    """Round-scoped entries scored on an ordinary run, as the first version did with a NOTE."""
    return patch.object(_scorer(), "refuse_round_scoped_on_ordinary", lambda key, run_dir: None)


# ---- 3. relations Python never writes ----------------------------------------------------

def unwritten_fixture(root):
    key = {"document": "sheet_x.md", "task_given_to_the_pipeline": "fixture",
           "planted": [
               {"unit": "u03-sample-beech", "rule": "CONV-SE", "relation": "unit_mismatch",
                "kind": "unit_mismatch",
                "claim": {"relation": "unit_mismatch", "field_label": "total volume",
                          "value_a": 0.0288, "value_b": 28.8, "unit_a": "L", "unit_b": "mL"}},
               {"unit": "u04-consignment-finch", "rule": "CONV-DG", "relation": "rate_mismatch",
                "kind": "ratio_mismatch",
                "claim": {"relation": "rate_mismatch", "field_label": "freight share",
                          "value_a": 4, "value_b": 6}},
               {"unit": "u07-count-locust", "rule": "CONV-LA", "relation": "carry_mismatch",
                "kind": "carry_mismatch",
                "claim": {"relation": "carry_mismatch", "field_label": "quantity row1",
                          "value_a": 40, "value_b": 44}}],
           "clean": []}
    _write(root / "key" / "answer_key.json", json.dumps(key))
    run = root / "run"
    _write(run / "logs" / "agent_bus.jsonl", "\n".join([
        _bus_line("main", "cloud", "fixture-model", "sheet_x", [
            _record("unit_mismatch", "u03-sample-beech", rule_id="CONV-005",
                    field_label="total volume", value_a=0.0288, value_b=28.8)]),
        _bus_line("main", "paired", "python", "sheet_x", [
            _record("rate_mismatch", "u04-consignment-finch", rule_id="CONV-002",
                    field_label="freight share", value_a=4, value_b=6)])]) + "\n")
    _write(run / "deliverables" / "sheet_x" / "review_data.json", json.dumps({"amendments": [
        {"finding_unit_id": "u04-consignment-finch", "source_convention_ref": "CONV-DG",
         "convention_ref": "CONV-002", "finding_relation": "sum_mismatch",
         "finding_field_label": "sum line total", "finding_value_a": 80, "finding_value_b": 82,
         "comment": "fixture"}]}))
    return root / "key" / "answer_key.json", run


def record_before_infra_045():
    """The Finding record as it was before INFRA-045 (RELATIONS-A) appended the four
    relations: the section for relations Python never writes is about a record that does
    not declare them, and since INFRA-045 the current one declares all four."""
    import relation_checks
    before = tuple(r for r in finding_record.relations() if r not in relation_checks.RELATIONS)
    return patch.object(finding_record, "relations", lambda: before)


def _observe_unwritten_lines():
    with tempfile.TemporaryDirectory(prefix="shimmer_scorer_unwritten_") as td:
        key, run = unwritten_fixture(Path(td))
        status, lines = run_scorer(["--key", str(key), "--run", str(run)])
        start = next((i for i, ln in enumerate(lines) if ln.startswith("relations Python never")), None)
        section = [ln.rstrip() for ln in lines[start:start + 10]] if start is not None else []
        section = [ln for ln in section if ln.startswith(("relations Python", "  "))]
        return {"status": status, "recall": _lines(lines, "recall          :"),
                "found": _lines(lines, "relations found", "model-only relations"), "section": section}


def observe_unwritten():
    """The fixture scored under a record that does not declare the four relations."""
    with record_before_infra_045():
        return _observe_unwritten_lines()


def observe_unwritten_current():
    """The same fixture scored under the current record (INFRA-045): the four are ordinary
    relations, located by any record on the bus, and no section is printed for them."""
    return _observe_unwritten_lines()


UNWRITTEN = {
    "status": 0,
    "recall": ["recall          : 1/3   (every planted entry, LOCATION ONLY)"],
    "found": [],
    "section": [
        "relations Python never writes : 3 planted entries (carry_mismatch=1, rate_mismatch=1, "
        "unit_mismatch=1); never counted as a Python catch",
        "  located by a model's record : 1   (%s)" % finding_record.MODEL_FINDING_MARK,
        "  reason confirmed by a model's record : 1",
        "  located by an amendment only : 1   (an amendment on the unit under the entry's rule, "
        "built from a finding of another relation: not this flaw's relation)",
        "  not located   : 1",
        "  on a Python post : 1 record(s)   (Python writes no such relation; counted nowhere)",
        "      u03-sample-beech CONV-SE   unit_mismatch  located by a model's record (1), reason confirmed",
        "      u04-consignment-finch CONV-DG   rate_mismatch  located by an amendment only",
        "      u07-count-locust CONV-LA   carry_mismatch not located"]}


# Since INFRA-045 the four relations are the record's own: Python's record locates its
# entry and a model's locates its entry as for any relation, and no section is printed.
UNWRITTEN_CURRENT = {
    "status": 0,
    "recall": ["recall          : 2/3   (every planted entry, LOCATION ONLY)"],
    "found": ["relations found : rate_mismatch=1, unit_mismatch=1"],
    "section": []}


def unwritten_records_dropped():
    """The records read through the Finding-record filter, as _load_bus_findings reads:
    an undeclared relation never reaches the section."""
    sc = _scorer()
    return patch.object(sc, "load_unwritten_records",
                        lambda run_dir, relations: [])


def python_post_counted():
    """A record on a Python post counted as a located record."""
    sc = _scorer()
    real = sc.load_unwritten_records
    return patch.object(sc, "load_unwritten_records",
                        lambda run_dir, relations: [dict(r, _written_by="model")
                                                    for r in real(run_dir, relations)])


# ---- 4. judged absences (issue #32, D-184) ----------------------------------------------

def judged_absence_fixture(root):
    """A judged-absence call whose raw reply carries two absence answers: Python kept one
    (its stamped copy is on the bus too) and refused the other. The key plants a flaw on each
    answer's unit."""
    key = {"document": "sheet_y.md", "task_given_to_the_pipeline": "fixture",
           "planted": [{"unit": "u02-sample-alder", "rule": "CONV-SA", "relation": "missing_field",
                        "kind": "absence"},
                       {"unit": "u05-sample-birch", "rule": "CONV-SA", "relation": "missing_field",
                        "kind": "absence"}],
           "clean": []}
    _write(root / "key" / "answer_key.json", json.dumps(key))
    kept = _record("missing_field", "u02-sample-alder", rule_id="CONV-003", field_label="calibration date")
    refused = _record("missing_field", "u05-sample-birch", rule_id="CONV-003", field_label="calibration date")

    def post(items, **body):
        return json.dumps({"sender": "PRACTICE_AUDITOR", "channel": "main", "body": dict({
            "event": "AGENT_OUTPUT", "backend": "local_auditor", "model": "fixture-model",
            "payload": {"agent": "PRACTICE_AUDITOR", "doc_id": "sheet_y", "items": items}}, **body)})
    run = root / "run"
    _write(run / "logs" / "agent_bus.jsonl", "\n".join([
        post([dict(kept), dict(refused)], call_id="call-absence-1"),
        post([dict(kept, unit_id="u02-sample-alder")], stamped_by="python", absence_path="judged")]) + "\n")
    _write(run / "audit" / "pairing_map.json", json.dumps({"sheet_y": {
        "judging_calls": [{"call_id": "call-absence-1", "agent": "PRACTICE_AUDITOR", "unit_id": "u05-sample-birch",
                           "rule_id": "CONV-003", "plan_kind": "absence_judged", "absence_listed": 1,
                           "absence_refused": 1, "outcome": "judged_absence"}],
        "absence_refused": [{"unit_id": "u05-sample-birch", "rule_id": "CONV-003", "reason": "quote not in the unit"}]}}))
    return root / "key" / "answer_key.json", run


def observe_judged_absences():
    with tempfile.TemporaryDirectory(prefix="shimmer_scorer_absence_") as td:
        key, run = judged_absence_fixture(Path(td))
        status, lines = run_scorer(["--key", str(key), "--run", str(run)])
        return {"status": status, "lines": _lines(lines, "amendments", "judged absences", "recall          :")}


JUDGED_ABSENCES = {
    "status": 0,
    "lines": [
        "amendments      : 0   (typed findings on the bus: 1)",
        "judged absences : 1 call(s); only Python's stamped copy is counted; 2 record(s) in the models' raw "
        "replies not counted; 1 answer(s) Python refused, counted apart, locating nothing",
        "recall          : 1/2   (every planted entry, LOCATION ONLY)"]}


def raw_judged_absence_read():
    """The model's raw judged-absence reply read like any post, as before: the kept answer
    counted twice and the refused one locating its flaw."""
    return patch.object(_scorer(), "is_raw_judged_absence", lambda body, calls: False)


def judged_absences_not_counted_apart():
    """The raw replies' records and the refused answers not reported."""
    return patch.object(_scorer(), "_print_judged_absences", lambda run_dir: None)


class ScorerSection9Checks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        result = prove_effect(name=name, validate=lambda: SCORER.is_file(), observe=observe,
                              check=lambda: ("PASS" if observe() == expected else "FAIL", name),
                              neutralise=neutralise)
        ScorerSection9Checks.evidence.append(result)

    def test_expected_refusals_are_read(self):
        """Neutralised: the key part ignored, as before."""
        self.prove("expected_refusals_read", observe_refusals, REFUSALS, refusals_ignored)

    def test_a_refusal_of_another_kind_is_reported_as_such(self):
        """Neutralised: any refusal counted as the expected kind."""
        self.prove("refusal_kind_compared", observe_refusals, REFUSALS, refusal_kind_not_compared)

    def test_a_round_finding_counts_only_in_its_own_round_and_document(self):
        """Neutralised: matched on the unit alone."""
        self.prove("round_scope", observe_multi_round, MULTI_ROUND, scope_without_round)

    def test_only_python_round_findings_count(self):
        """Neutralised: a model's item on the multi_round channel read as Python's."""
        self.prove("round_findings_python_only", observe_multi_round, MULTI_ROUND,
                   model_round_items_counted)

    def test_a_multi_round_run_is_scored_as_one(self):
        """Neutralised: audit/multi_round.json not read."""
        self.prove("multi_round_run_detected", observe_multi_round, MULTI_ROUND,
                   multi_round_run_not_detected)

    def test_a_rename_matched_only_by_a_model_record_satisfies_nothing(self):
        """Neutralised: a change record matched as a rename whoever wrote it."""
        self.prove("rename_python_only", observe_refusals, REFUSALS, model_rename_counted)

    def test_a_matched_rename_leaves_the_false_positives(self):
        """Neutralised: matched renames left in the false positives."""
        self.prove("rename_not_false_positive", observe_refusals, REFUSALS,
                   matched_renames_left_in_false_positives)

    def test_a_listed_label_is_not_a_stray_refusal(self):
        """Neutralised: refusals and orphans of listed labels counted as stray."""
        self.prove("listed_not_stray", observe_refusals, REFUSALS, listed_labels_left_stray)

    def test_a_multi_round_run_whose_key_has_no_entries_is_refused(self):
        """Neutralised: scored as if the key had empty entries."""
        self.prove("no_entries_refused", observe_key_forms, KEY_FORMS, entries_absent_scored_as_empty)

    def test_the_top_level_form_is_read_from_clean_entries_too(self):
        """Neutralised: the top-level form detected from planted entries alone."""
        self.prove("top_level_form", observe_key_forms, KEY_FORMS, top_level_form_from_planted_only)

    def test_a_round_scoped_key_on_an_ordinary_run_is_refused(self):
        """Neutralised: scored on the ordinary run."""
        self.prove("round_scoped_on_ordinary_refused", observe_key_forms, KEY_FORMS,
                   round_scoped_key_scored_on_an_ordinary_run)

    def test_a_relation_python_never_writes_is_located_by_a_model_record(self):
        """Neutralised: the records dropped by the Finding-record filter."""
        self.prove("unwritten_relation_read", observe_unwritten, UNWRITTEN, unwritten_records_dropped)

    def test_a_record_on_a_python_post_is_never_counted(self):
        """Neutralised: a record on a Python post counted as located."""
        self.prove("unwritten_never_python", observe_unwritten, UNWRITTEN, python_post_counted)

    def test_the_relations_infra_045_appended_are_scored_like_any_other(self):
        """Neutralised: scored under the record as it was before INFRA-045."""
        self.prove("infra_045_relations_scored", observe_unwritten_current, UNWRITTEN_CURRENT,
                   record_before_infra_045)

    def test_a_judged_absence_is_read_from_pythons_stamped_copy_only(self):
        """Neutralised: the raw reply read too (issue #32)."""
        self.prove("judged_absence_stamped_only", observe_judged_absences, JUDGED_ABSENCES,
                   raw_judged_absence_read)

    def test_refused_judged_answers_are_counted_apart(self):
        """Neutralised: the raw records and refused answers not reported (issue #32)."""
        self.prove("judged_absence_counted_apart", observe_judged_absences, JUDGED_ABSENCES,
                   judged_absences_not_counted_apart)


def check():
    ScorerSection9Checks.evidence = []
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ScorerSection9Checks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:160]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: expected_refusals scored by "
                    "kind (a refusal of another kind reported as such, a matched rename no false "
                    "positive, a model-matched rename satisfying nothing, a listed label never stray, "
                    "a fabricated withdrawal named); a multi-round run posted by "
                    "multi_round_rounds.post_findings scored per round and document from Python's "
                    "round findings only, a key without multi-round entries refused there and a "
                    "round-scoped key refused on an ordinary run; under the record before INFRA-045 "
                    "a relation Python never writes located only by a model-written record, "
                    "marked, never by a Python post, and under the current record the four "
                    "relations scored like any other; a judged absence read "
                    "from Python's stamped copy only, its raw records and refused answers counted "
                    "apart" % result.testsRun)


def main():
    status, detail = check()
    for proof in ScorerSection9Checks.evidence:
        print(proof["name"], proof["status"])
        print("  before:  ", json.dumps(proof["before"], sort_keys=True)[:600])
        print("  mutated: ", json.dumps(proof["mutated"], sort_keys=True)[:600])
        print("  restored:", json.dumps(proof["restored"], sort_keys=True)[:600])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
