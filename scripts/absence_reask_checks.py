"""Check 253's run-outcome reconciliation with D-652 fix 4's one re-ask, as a single-check file
(light: one declared fixture run, no model, no network, a temporary run folder):

    py -3.12 -X utf8 scripts/absence_reask_checks.py

The audit's forecast (absence_prediction) counts PLANS: 14 judged and 7 computed, each plan's first
answer only (pipeline calls prediction.outcome only when `reask is None`), so its counts and the
saved first refusals do not change. The re-ask is an extra CALL after the first answers, on a plan
whose first answer was refused for a missing quote or figures on a unit with no pipe table
(paired_review.reask_eligible, REASK_REASONS). So the dispatch the run really makes is
    calls      = first questions + re-asks
    bus_judged = kept first answers + kept second answers.
The fixture's replies cycle through four variants by CALL number (0 declared and quoted, 1 no
quote, 2 a quote the unit lacks, 3 a field the unit carries), and the re-asks of a document are
dispatched after that document's first answers, before the next document's: document "first" has 5
judged plans (calls 1 to 5, variants 0,1,2,3,0: kept 2, refused no quote at call 2, quote lacking at
3, field carried at 4), one re-ask (call 6, variant 1, refused again); document "second" has 9
(calls 7 to 15, variants 2,3,0,1,2,3,0,1,2: kept 2 at calls 9 and 13, no quote at 10 and 14, quote
lacking at 7, 11 and 15, field carried at 8 and 12), two re-asks (calls 16 and 17, variants 3 and 0:
the first refused again, the second kept). So: 17 calls = 14 first questions + 3 re-asks, 1 kept
re-ask, 5 judged items on the bus (4 + 1), the 10 first refusals saved unchanged (no quote 3, quote
lacking 4, field carried 3), the forecast counts unchanged. Before the re-ask the same cycle gave
14 calls and refusals 4, 3 and 3 (check 253's old numbers).
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import absence_prediction_fixture as fixture  # noqa: E402

FIRST_QUESTIONS = 14
NO_QUOTE = "absence claim supplies no quote"


def reconcile(measured):
    """None when the run's calls, bus and saved refusals reconcile with the forecast and the one
    re-ask; otherwise what disagrees. The counts are derived from the run's own record (each re-ask
    is one saved row), then held to the numbers the fixture's four-variant cycle gives."""
    report = measured["report"] or {}
    counts = report.get("counts", {})
    prediction = report.get("prediction", {})
    if (prediction.get("expected_judged_plans") != 14 or prediction.get("expected_computed_plans") != 7
            or report.get("count_comparison") != "matches" or report.get("status") != "PASS"):
        return "the run lost the historical forecast or did not check the declared cohort"
    wanted = {"judged_plans": 14, "computed_plans": 7, "computed_completed": 7, "returned": 14,
              "successful": 14, "claims": 14, "quoted": 4, "refused": 10, "violations": 0}
    if any(counts.get(key) != value for key, value in wanted.items()):
        return "actual quote/refusal/computed outcomes do not reconcile"
    reasons = measured["refusal_reasons"]
    if (reasons.count(NO_QUOTE) != 3 or reasons.count("quotes text that does not appear in this unit") != 4
            or reasons.count("claims a field absent that this unit carries") != 3):
        return "the saved first-refusal reasons misstate why an absence claim was refused"
    reasked = measured["reasked"]
    if (reasked != reasons.count(NO_QUOTE) or measured["reasked_reasons"] != [NO_QUOTE] * reasked
            or reasked != 3 or measured["reasked_kept"] != 1):
        return "the re-asks are not the first refusals for a missing quote (got %s, kept %s)" % (
            reasked, measured["reasked_kept"])
    if (measured["calls"] != FIRST_QUESTIONS + reasked
            or measured["bus_judged"] != counts["quoted"] + measured["reasked_kept"]
            or measured["bus_computed"] != 7 or measured["saved_refused"] != 10
            or not measured["pending_before_every_reply"]):
        return "the audit disagrees with real dispatch, bus, refusal map or pending work"
    return None


CASES = (("empty", "not_exercised"), ("other", "not_exercised"), ("failed", "incomplete"),
         ("no_consumer", "incomplete"), ("interrupted", "incomplete"), ("changed", "PASS"),
         ("wide", "not_applicable"))


def cases_problem(measure):
    """None when each outcome of check 253's other cases is distinguished (the re-ask changes no
    status); `measure(case)` is the fixture."""
    for case, status in CASES:
        result = measure(case)
        rep = result["report"] or {}
        if rep.get("status") != status or not result["historical_missing"]:
            return "%s was falsely credited or historical absence was backfilled" % case
        if case == "changed" and rep.get("count_comparison") != "differs":
            return "a changed cohort was forced into the old fourteen-question forecast"
        if case == "interrupted" and (not result["interrupted"] or rep.get("documents_complete")):
            return "unfinished review was recorded as completed"
    return None


def check():
    measured = fixture.measure()
    problem = reconcile(measured) or cases_problem(fixture.measure)
    if problem:
        return "FAIL", problem
    import paired_review
    with patch.object(paired_review, "reask_eligible", lambda *a, **k: False):
        unreasked = fixture.measure()
    if unreasked["reasked"] != 0 or reconcile(unreasked) is None:
        return "FAIL", "with no re-ask the reconciliation still passes: the proof does not see the re-ask"
    return "PASS", ("%d calls = %d first questions + %d re-asks (%d kept), bus judged %d, first refusals %d "
                    "unchanged, forecast counts unchanged; without the re-ask the proof fails" % (
                        measured["calls"], FIRST_QUESTIONS, measured["reasked"], measured["reasked_kept"],
                        measured["bus_judged"], measured["saved_refused"]))


if __name__ == "__main__":
    print(json.dumps(check()))
