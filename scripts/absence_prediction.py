"""Check the forward absence-quote forecast on actual paired-review outcomes.

The audit stores identifiers and counts, never source text or quote contents.
It does not change routing, findings, or the forward-only quote requirement.
"""
from __future__ import annotations

import localization
import json
from pathlib import Path


ARTIFACT = "absence_quote_prediction.json"


def _valid_quote(item, unit_text):
    quote = " ".join(str(item.get("quote") or "").split()).lower()
    text = " ".join(str(unit_text or "").split()).lower()
    return bool(quote and text and quote in text)


class AbsencePrediction:
    def __init__(self, run_context, documents, mode, config_path):
        expected = json.loads(Path(config_path).read_text(encoding="utf-8"))["absence_quotes"]
        for field in ("expected_judged_plans", "expected_computed_plans"):
            if type(expected.get(field)) is not int or expected[field] < 0:
                raise ValueError("invalid absence prediction count")
        self.path = Path(run_context.audit_dir()) / ARTIFACT
        self.report = {"prediction": expected, "review_mode": mode,
                       "documents": {str(d["id"]): {"state": "pending", "plans": []}
                                     for d in documents}}
        self._save()

    def planned(self, document_id, plans):
        self.report["documents"][str(document_id)] = {
            "state": "running",
            "plans": [{"index": i, "unit_id": p["unit"]["unit_id"],
                       "rule_id": p["rule"]["id"], "kind": p["kind"], "state": "pending"}
                      for i, p in enumerate(plans)
                      if p.get("kind") in ("absence_judged", "absence_computed")]}
        self._save()

    def outcome(self, document_id, index, state, *, raw=(), kept=(), refused=(),
                unit_text="", response_ok=None):
        plans = self.report["documents"][str(document_id)]["plans"]
        row = next((p for p in plans if p["index"] == index), None)
        if row is None:
            return
        row["state"] = state
        if row["kind"] == "absence_judged" and state == "returned":
            claims = [i for i in raw if i.get("relation") == "missing_field"]
            accepted = [i for i in kept if i.get("relation") == "missing_field"]
            denied = [i for i in refused if i.get("relation") == "missing_field" and i.get("reason")]
            quoted = sum(_valid_quote(i, unit_text) for i in accepted)
            row.update(response_ok=response_ok is True, claims=len(claims),
                       quoted=quoted, refused=len(denied),
                       violations=(len(accepted) - quoted) +
                                  abs(len(claims) - len(accepted) - len(denied)),
                       other_items=len(raw) - len(claims))
        self._save()

    def finished(self, document_id):
        self.report["documents"][str(document_id)]["state"] = "finished"
        self._save()

    def _save(self):
        docs = list(self.report["documents"].values())
        plans = [p for d in docs for p in d["plans"]]
        judged = [p for p in plans if p["kind"] == "absence_judged"]
        computed = [p for p in plans if p["kind"] == "absence_computed"]
        counts = {key: sum(p.get(key, 0) for p in judged)
                  for key in ("claims", "quoted", "refused", "violations", "other_items")}
        counts.update(judged_plans=len(judged), computed_plans=len(computed),
                      computed_completed=sum(p["state"] == "computed" for p in computed),
                      returned=sum(p["state"] == "returned" for p in judged),
                      successful=sum(p.get("response_ok") is True for p in judged),
                      no_consumer=sum(p["state"] == "no_consumer" for p in judged),
                      empty_answers=sum(p.get("response_ok") is True and not p.get("claims")
                                        and not p.get("other_items") for p in judged))
        complete = all(d["state"] == "finished" for d in docs)
        if self.report["review_mode"] != "paired":
            status = "not_applicable"
        elif counts["violations"]:
            status = "FAIL"
        elif not complete or counts["successful"] != len(judged):
            status = "incomplete"
        elif not counts["claims"]:
            status = "not_exercised"
        else:
            status = "PASS"
        expected = self.report["prediction"]
        self.report.update(status=status, counts=counts, documents_complete=complete,
                           count_comparison=("pending" if not complete else
                               "matches" if len(judged) == expected["expected_judged_plans"]
                               and len(computed) == expected["expected_computed_plans"] else "differs"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)


def read_report(run_dir):
    path = Path(run_dir) / "audit" / ARTIFACT
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# Reader check round 3 (item 8): each result of the quote check in one plain
# sentence. The status codes stay exactly as recorded in the audit file; only the
# words a reader sees change ("**PASS**" stays the word check 253 reads).
STATUS_SENTENCES = {
    "PASS": "Result: **PASS**. Every absence a model claimed quoted the unit's own words or was refused.",
    "FAIL": "Result: **FAIL**. At least one absence a model claimed was kept without a quote from the unit.",
    "not_exercised": "Result: **not exercised**. No model claimed a field absent, so there was no quote to check.",
    "incomplete": "Result: **incomplete**. Not every question about an absent field was answered, so the check is not settled.",
    "not_applicable": "Result: **not applicable**. This run did not use the paired review, where these questions are asked.",
}
COMPARISON_WORDS = {"matches": "so the counts match", "differs": "so the counts differ",
                    "pending": "and the counts are not final yet"}


@localization.presentation
def summary_lines(report):
    if not report:
        return []
    counts, expected = report["counts"], report["prediction"]
    t = localization.text
    status = str(report.get("status"))
    return ["", t('## Absence quote check'), "",
            t(STATUS_SENTENCES[status]) if status in STATUS_SENTENCES else f"**{status}**",
            t("Absence claims a model made: {claims}; {quoted} quoted the unit, {refused} were refused, "
              "{violations} were kept without a quote.", claims=counts['claims'], quoted=counts['quoted'],
              refused=counts['refused'], violations=counts['violations']),
            t("Questions a model was asked about an absent field: {planned} planned, {returned} answered, "
              "{successful} answered successfully, {no_consumer} with no agent to ask, {empty} answered "
              "with nothing.", planned=counts['judged_plans'], returned=counts['returned'],
              successful=counts['successful'], no_consumer=counts['no_consumer'], empty=counts['empty_answers']),
            t("Absences Python checked itself: {planned} planned, {completed} completed (these need no quote).",
              planned=counts['computed_plans'], completed=counts['computed_completed']),
            t("The earlier runs this check was set up from planned {judged} judged and {computed} computed "
              "absence questions; this run planned {now_judged} and {now_computed}, {comparison}. "
              "These are counts of questions, not of claims, and a matching count does not show the same "
              "questions were asked.", judged=expected['expected_judged_plans'],
              computed=expected['expected_computed_plans'], now_judged=counts['judged_plans'],
              now_computed=counts['computed_plans'],
              comparison=t(COMPARISON_WORDS.get(report.get('count_comparison'), str(report.get('count_comparison'))))),
            t('A quote shows the words are in the unit; it does not show the absence conclusion is right. '
              'Per-question outcomes are in [the run audit](../audit/absence_quote_prediction.json).')]
