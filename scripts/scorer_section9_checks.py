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

1. expected refusals: a negotiation-style key with four renamed terms (one refused with
   the expected kind, one refused with another kind, one matched as a rename where the
   key expects no refusal, one with a fabricated withdrawal) and a run whose
   review_data.json and bus hold exactly those records;
2. a multi-round run: its bus lines are written by multi_round_rounds.post_findings itself
   (the real posting code, through a recording wrapper), from a two-round record holding
   a planted flaw, a flaw found with the wrong figures, a flaw found only in another
   round, a model-written item on the multi_round channel, a clean distractor and a
   finding on an unkeyed unit, beside audit/multi_round.json and a completion record;
3. the relations Python never writes: a single-version key with one entry located by a
   model-written record whose reason matches, one whose only record sits on a Python post
   with an amendment of another relation on its unit, and one with nothing.

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

def refusal_fixture(root):
    """A negotiation-style key with four renamed terms and a run that refuses, matches and
    fabricates exactly as the module docstring says."""
    key = {"document": "terms_x.md", "task_given_to_the_pipeline": "fixture",
           "prior_records": [{"field_label": "deposit amount", "relation": "unchanged_from_prior",
                              "value_a": 100, "value_b": 100, "unit": "EUR"}],
           "band_irregularities": [],
           "expected_refusals": [
               {"field_label": "rebate threshold", "later_field_label": "rebate trigger",
                "unit_id": "u06-clause-swift", "reason_kind": "possible_rename",
                "value_a": 61, "value_b": 61, "unit": "EUR"},
               {"field_label": "audit interval", "later_field_label": "inspection interval",
                "unit_id": "u08-clause-jay", "reason_kind": "possible_successor",
                "value_a": 3, "value_b": 5, "unit": "months"},
               {"field_label": "payment term", "later_field_label": "settlement term",
                "unit_id": "u04-clause-tern", "reason_kind": None,
                "value_a": 29, "value_b": 21, "unit": "days"},
               {"field_label": "storage fee", "later_field_label": "warehouse fee",
                "unit_id": "u09-clause-wren", "reason_kind": "possible_rename",
                "value_a": 7, "value_b": 7, "unit": "EUR"}]}
    _write(root / "key" / "answer_key.json", json.dumps(key))
    run = root / "run"
    change = [
        _record("unchanged_from_prior", "u01-clause-a", verdict="ok", provenance="computed",
                field_label="deposit amount", value_a=100, value_b=100, unit_a="EUR", unit_b="EUR"),
        _record("changed_from_prior", "u02-clause-grebe", verdict="ok", provenance="computed",
                field_label="settlement term", value_a=29, value_b=21, unit_a="days", unit_b="days"),
        _record("absent_since_prior", "u09-clause-wren", verdict="ok", provenance="computed",
                field_label="storage fee", value_a=None, value_b=7, unit_b="EUR")]
    _write(run / "logs" / "agent_bus.jsonl", _bus_line("main", "computed", "python", "terms_x", change) + "\n")
    _write(run / "deliverables" / "terms_x" / "review_data.json", json.dumps({
        "amendments": [], "prior_comparisons": change,
        "prior_refusals": [
            {"unit_id": "u06-clause-swift", "label": "rebate threshold", "reason": "r",
             "reason_kind": "possible_rename"},
            {"unit_id": "u08-clause-jay", "label": "audit interval", "reason": "r",
             "reason_kind": "possible_rename"},
            {"unit_id": "u05-clause-kite", "label": "loading charge", "reason": "r",
             "reason_kind": "possible_successor"}],
        "prior_orphans": []}))
    return root / "key" / "answer_key.json", run


def observe_refusals():
    with tempfile.TemporaryDirectory(prefix="shimmer_scorer_refusals_") as td:
        key, run = refusal_fixture(Path(td))
        status, lines = run_scorer(["--key", str(key), "--run", str(run)])
        table = [ln[ln.index("u0"):].rstrip() for ln in lines
                 if ln.startswith("  ") and not ln.startswith("   ") and "-clause-" in ln]
        return {"status": status,
                "lines": _lines(lines, "expected refusals", "  by expected kind", "false positives",
                                "stray refusals", "recall, exact"),
                "table": table}


REFUSALS = {
    "status": 0,
    "lines": [
        "recall, exact     : 1/1   (label + relation + figures)",
        "false positives   : 1   (a record for a label or relation the key does not give)",
        "stray refusals    : 1   (refusals or orphans for labels the key does not list)",
        "expected refusals : 3/4 satisfied (1 refused with the expected kind, 1 refused with "
        "another kind, 1 matched renames); 1 fabricated withdrawal(s) (absent_since_prior on a "
        "renamed term's earlier label, counted in false positives)",
        "  by expected kind  : possible_rename 1/2 satisfied, 1 refused with that kind; "
        "possible_successor 1/1 satisfied, 0 refused with that kind; null 1/1 satisfied (no "
        "refusal expected; only a matched rename satisfies)"],
    "table": ["u06-clause-swift       possible_rename              refused, possible_rename as expected",
              "u08-clause-jay         possible_successor           refused as possible_rename, OTHER KIND (key: possible_successor)",
              "u04-clause-tern        null                         matched rename",
              "u09-clause-wren        possible_rename              FABRICATED WITHDRAWAL"]}


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


def observe_unwritten():
    with tempfile.TemporaryDirectory(prefix="shimmer_scorer_unwritten_") as td:
        key, run = unwritten_fixture(Path(td))
        status, lines = run_scorer(["--key", str(key), "--run", str(run)])
        start = next((i for i, ln in enumerate(lines) if ln.startswith("relations Python never")), None)
        section = [ln.rstrip() for ln in lines[start:start + 10]] if start is not None else []
        section = [ln for ln in section if ln.startswith(("relations Python", "  "))]
        return {"status": status, "recall": _lines(lines, "recall          :"),
                "found": _lines(lines, "relations found", "model-only relations"), "section": section}


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

    def test_a_relation_python_never_writes_is_located_by_a_model_record(self):
        """Neutralised: the records dropped by the Finding-record filter."""
        self.prove("unwritten_relation_read", observe_unwritten, UNWRITTEN, unwritten_records_dropped)

    def test_a_record_on_a_python_post_is_never_counted(self):
        """Neutralised: a record on a Python post counted as located."""
        self.prove("unwritten_never_python", observe_unwritten, UNWRITTEN, python_post_counted)


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
                    "positive, a fabricated withdrawal named); a multi-round run posted by "
                    "multi_round_rounds.post_findings scored per round and document from Python's "
                    "round findings only; a relation Python never writes located only by a "
                    "model-written record, marked, never by a Python post" % result.testsRun)


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
