"""Write the demo's fixture: run folders of the shape a real run leaves, for two INVENTED cases.

D-S48: the demo is built from the two worked cases' saved results, which do not exist yet. Until
they do, `tools/build_demo.py` is proven on this fixture. Nothing here is from benchmark/ or
external/: both cases are invented in this file, the "public" one only standing in for the real
public UN text so the builder can be shown a case of each kind.

What is real and what is written by hand:

- the multi-round folders are written by the case phase itself (multi_round_phase.execute with the
  pipeline's own wrapper factory and the stand-in backends of check 276, as
  multi_round_rounds_checks.mocked_multi_round_run does): round_reuse.json, multi_round.json,
  version_changes.json and .md, case_questions.json and case_positions.md are the writers' own;
- the movement answers and the suggestion are PRE-AUTHORED STUBS, not model output;
- the ordinary review folders' review_data.json, review_findings.md and tracked_changes.docx are
  written by amendment_render.write_amendment_deliverables from a hand-written master, and
  document_summary.md is hand-written, marked so in its first line.

Run once and commit the result; the demo checks never regenerate it:

    py -3.12 -X utf8 tools/demo_fixture.py --out scripts/fixtures/demo
"""
import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

KEEP_AUDIT = ("multi_round.json", "round_reuse.json", "version_changes.json", "case_questions.json")

RULES = [{"id": "CONV-001", "category": "conv-a01", "severity": "required",
          "rule": "A share must lie between 10 units and 60 units."}]


def accord(round_no, share, review):
    return ("# Fictional water sharing accord, round %d\n\n"
            "## Article 1 Purpose\n\nThe two parties agree to share the water of the river fairly.\n\n"
            "## Article 2 Annual share\n\nShare: %d units\n\n"
            "## Article 3 Review\n\nThe parties review this accord every %s years.\n" % (round_no, share, review))


def note(party, round_no, share):
    return ("# Note of %s, round %d\n\n## Share\n\n%s asks for a share of %d units.\n"
            % (party, round_no, party, share))


def resolution(version, verb, date):
    return ("# Invented draft resolution on a day for clean rivers, version %d\n\n"
            "## Preambular paragraph 1\n\nRecalling the importance of clean rivers for all people,\n\n"
            "## Operative paragraph 1\n\nDecides to proclaim %s as an international day for clean rivers;\n\n"
            "## Operative paragraph 2\n\n%s all Member States to observe the day;\n" % (version, date, verb))


def sponsor_note(version, sentence):
    return "# Statement of the main sponsor, version %d\n\n## Observance\n\n%s\n" % (version, sentence)


SYNTHETIC = {
    "case_id": "demo_water_accord", "kind": "synthetic",
    "documents": {
        "accord_round_1": accord(1, 61, "five"), "accord_round_2": accord(2, 55, "three"),
        "accord_round_3": accord(3, 62, "three"),
        "note_north_round_1": note("Party North", 1, 61), "note_north_round_2": note("Party North", 2, 58),
        "note_north_round_3": note("Party North", 3, 62),
        "note_south_round_1": note("Party South", 1, 40), "note_south_round_2": note("Party South", 2, 45),
        "note_south_round_3": note("Party South", 3, 50)},
    "rounds": [("r1", ["accord_round_1", "note_north_round_1", "note_south_round_1"]),
               ("r2", ["accord_round_2", "note_north_round_2", "note_south_round_2"]),
               ("r3", ["accord_round_3", "note_north_round_3", "note_south_round_3"])],
    "actors": [{"actor_id": "party_north", "supported": True}, {"actor_id": "party_south"}],
    "issues": [{"issue_id": "annual_share", "open": True, "text_units": ["article-2-annual-share"]}],
    "positions": [("party_north", "annual_share", "note_north_round_%d", "asks for a share of"),
                  ("party_south", "annual_share", "note_south_round_%d", "asks for a share of")],
    # PRE-AUTHORED STUB ANSWERS, NOT MODEL OUTPUT, keyed by (actor, round after).
    "answers": {("party_north", "r2"): "toward", ("party_north", "r3"): "away",
                ("party_south", "r2"): "toward", ("party_south", "r3"): "toward"},
    "suggestion": {"suggested_wording": "Share: 58 units, reviewed every three years.",
                   "why": "It keeps the figure Party North stated in round 2 and the review period both texts hold.",
                   "cites": ["P3", "P4"]},
    "review": {"target": "accord_round_3", "prior": "accord_round_2"},
}

PUBLIC = {
    "case_id": "demo_clean_rivers_resolution", "kind": "public",
    "documents": {
        "resolution_v1": resolution(1, "Urges", "15 March"), "resolution_v2": resolution(2, "Invites", "7 June"),
        "sponsor_v1": sponsor_note(1, "The main sponsor wants Member States to be urged to observe the day."),
        "sponsor_v2": sponsor_note(2, "The main sponsor now accepts that Member States are invited to observe the day.")},
    "rounds": [("r1", ["resolution_v1", "sponsor_v1"]), ("r2", ["resolution_v2", "sponsor_v2"])],
    "actors": [{"actor_id": "main_sponsor"}],
    "issues": [{"issue_id": "observance"}],
    "positions": [("main_sponsor", "observance", "sponsor_v%d", "The main sponsor")],
    "answers": {},
    "suggestion": None,
    "review": {"target": "resolution_v2", "prior": "resolution_v1"},
}


def _manifest(case):
    import pairing_map
    docs = case["documents"]
    sources = []
    for n, (round_id, _) in enumerate(case["rounds"], start=1):
        for actor, issue, pattern, start_words in case["positions"]:
            doc_id = pattern % n
            text = docs[doc_id]
            found = text.index(start_words)
            start = text.rfind("\n", 0, found) + 1
            end = text.index("\n", found)
            unit = next(u for u in pairing_map.split_units(text, document_id=doc_id)
                        if text[start:end] in u["text"])
            sources.append({"source_id": "s_%s_%s" % (actor, round_id), "round_id": round_id, "actor_id": actor,
                            "issue_id": issue, "document_id": doc_id, "unit_id": unit["unit_id"],
                            "char_start": start, "char_end": end, "quote": text[start:end], "state": "accepted"})
    return {"schema_version": 1, "case_id": case["case_id"], "fixture": False,
            "rounds": [{"round_id": r, "sequence": i, "document_ids": ids}
                       for i, (r, ids) in enumerate(case["rounds"], start=1)],
            "actors": case["actors"], "issues": case["issues"], "sources": sources}


def _decide(case):
    def decide(question):
        answer = case["answers"].get((question["actor_id"], question["round_after"]))
        if answer is None:
            return None
        return {"answer": answer, "confidence": 0.9, "settled": True, "model": "stub-not-a-model"}
    return decide


def _suggest(case):
    def suggest(question):
        return None if case["suggestion"] is None else dict(case["suggestion"], model="stub-not-a-model")
    return suggest


def rounds_run(case, out_root):
    """The case phase, as mocked_multi_round_run runs it, on this case."""
    import multi_round as mr
    import multi_round_phase
    import pipeline as pl
    from harness.run_agent import build_orchestrator
    from reference_builder import ReferenceIndex
    from reply_records_checks import backends
    registry = dict(json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"])
    orch = build_orchestrator(root=ROOT, out_root=Path(out_root), registry=registry)
    ctx = orch.run_context
    docs = [{"id": k, "name": k + ".md", "text": v} for k, v in sorted(case["documents"].items())]
    record = mr.begin(ctx, _manifest(case))
    refs = ReferenceIndex.open(ROOT, index_path=ctx.reference_index_path())
    with backends(local=[], seen=None), contextlib.redirect_stderr(io.StringIO()):
        code = multi_round_phase.execute(ctx, record, docs, refs, lambda name: pl._build_wrapper(name, orch, {}),
                                         sensitive=False, convention_registry={"conventions": RULES},
                                         decide=_decide(case), suggest=_suggest(case))
    if code != 0:
        raise SystemExit("the case phase returned %s" % code)
    return Path(ctx.run_dir)


def review_master(case):
    """A hand-written master in the shape amendment_render writes: one amendment built from a
    computed finding, one model finding not promoted."""
    target = case["review"]["target"]
    if case["kind"] == "synthetic":
        amendment = {"convention_ref": "CONV-001", "source_convention_ref": "conv-a01",
                     "location": "u02-article-2-annual-share", "action": "flag",
                     "original_text": "Share: 62 units",
                     "comment": "In Article 2 Annual share, the share is 62 units, above the allowed range of "
                                "10 units to 60 units (rule CONV-001).",
                     "ref_ids": ["REF-0001"], "derived_from": "computed_finding",
                     "finding_unit_id": "u02-article-2-annual-share", "finding_rule_id": "CONV-001",
                     "finding_relation": "above_band", "finding_field_label": "share",
                     "finding_value_a": 62.0, "finding_unit_a": "units", "finding_value_b": 60.0,
                     "finding_unit_b": "units", "severity": "required"}
        model = {"agent": "PRACTICE_AUDITOR", "rule_id": "CONV-001", "source_rule_id": "conv-a01",
                 "unit_id": "u03-article-3-review", "relation": "missing_field", "field_label": "review",
                 "source_refs": ["REF-0002"],
                 "explanation": "The review article does not say who calls the review.",
                 "model_claimed_verdict": "irregular", "written_by": "model", "promoted": False,
                 "checked_by_python": False, "reader_notes": []}
        return {"document_id": target, "amendments": [amendment], "_validator_errors": [],
                "model_findings_not_promoted": [model]}
    model = {"agent": "PRACTICE_AUDITOR", "rule_id": "CONV-001", "source_rule_id": "conv-a01",
             "unit_id": "u03-operative-paragraph-2", "relation": "missing_field", "field_label": "observance",
             "source_refs": ["REF-0003"],
             "explanation": "The paragraph no longer says how the day is to be observed.",
             "model_claimed_verdict": "irregular", "written_by": "model", "promoted": False,
             "checked_by_python": False, "reader_notes": []}
    return {"document_id": target, "amendments": [], "_validator_errors": [],
            "model_findings_not_promoted": [model]}


def _result(entry, passed):
    """evidence/result.json as the runner writes it, beside the run folder. The synthetic case's
    ordinary review is written as FAILED, with a set-aside reply's header, so the demo's statement of
    a failure is proven; the body of that reply is withheld here, as the demo never reads it."""
    reasons = [] if passed else ["semantic_incomplete", "required_contract_failure"]
    (entry / "result.json").write_text(json.dumps({
        "collection_and_teardown_pending": True, "execution_integrity_passed": passed,
        "failed_backend_attempts": 0, "pipeline_exit_code": 0, "quality_claim": None,
        "reasons": reasons}, indent=2) + "\n", encoding="utf-8", newline="\n")
    (entry / "run" / "audit").mkdir(parents=True, exist_ok=True)
    (entry / "run" / "audit" / "run_completion.json").write_text(json.dumps({
        "schema_version": 1, "state": "completed" if passed else "stopped", "reached_end": True,
        "exit_code": 0, "semantic_complete": passed}, indent=2) + "\n", encoding="utf-8", newline="\n")
    if not passed:
        folder = entry / "run" / "audit" / "contract_violations"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "VERIFIER_20261108T000000_task-000001.txt").write_text(
            "# Contract violation raw output\n# agent: VERIFIER\n# timestamp: 2026-11-08T00:00:00+00:00\n"
            "# missing_fields: ['not a canonical envelope {agent:str, doc_id:str, items:list}']\n"
            "# raw_text_bytes: 13263\n# sensitive: False\n# ---\n[the fixture withholds the reply]\n",
            encoding="utf-8", newline="\n")


def review_run(case, folder):
    import amendment_render
    target = case["review"]["target"]
    folder = folder / "run"
    deliv = folder / "deliverables"
    deliv.mkdir(parents=True)
    (folder / "status.json").write_text(json.dumps({"status": "completed", "task": "review",
                                                    "output_language": "en"}, indent=2) + "\n", encoding="utf-8")
    amendment_render.write_amendment_deliverables(review_master(case), deliv_dir=deliv, doc_id=target,
                                                  document_name=target + ".md",
                                                  body_text=case["documents"][target])
    (deliv / target / "document_summary.md").write_text(
        "<!-- Demo fixture: hand-written, not written by the summary generator. -->\n"
        "# %s: document summary\n\nReviewed against %s, the earlier version.\n"
        % (target, case["review"]["prior"]), encoding="utf-8", newline="\n")


def write(out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for case in (SYNTHETIC, PUBLIC):
        name = case["case_id"]
        docs = out / "documents" / name
        docs.mkdir(parents=True)
        for doc_id, text in sorted(case["documents"].items()):
            (docs / (doc_id + ".md")).write_text(text, encoding="utf-8", newline="\n")
        with tempfile.TemporaryDirectory(prefix="shimmer_demo_fixture_") as td:
            run = rounds_run(case, td)
            entry = out / "runs" / (name + "_rounds")
            dest = entry / "run"
            (dest / "audit").mkdir(parents=True)
            _result(entry, passed=True)
            for audit in KEEP_AUDIT:
                if (run / "audit" / audit).is_file():
                    shutil.copy2(run / "audit" / audit, dest / "audit" / audit)
            if (run / "deliverables").is_dir():
                shutil.copytree(run / "deliverables", dest / "deliverables")
        review_run(case, out / "runs" / (name + "_review"))
        _result(out / "runs" / (name + "_review"), passed=case["kind"] != "synthetic")
    print("wrote", out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    write(parser.parse_args().out)
