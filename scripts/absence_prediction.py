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


@localization.presentation
def summary_lines(report):
    if not report:
        return []
    counts, expected = report["counts"], report["prediction"]
    return ["", localization.text('## Absence quote prediction'), "",
            f'{localization.text('Quote-or-refusal check: **')}{report['status']}**. {counts['claims']}{localization.text(' judged absence claim(s): ')}{counts['quoted']}{localization.text(' quoted, ')}{counts['refused']}{localization.text(' refused, ')}{counts['violations']}{localization.text(' violation(s).')}',
            f'{localization.text('Judged questions: ')}{counts['judged_plans']}{localization.text(' planned, ')}{counts['returned']}{localization.text(' returned, ')}{counts['successful']}{localization.text(' successful, ')}{counts['no_consumer']}{localization.text(' without a consumer, ')}{counts['empty_answers']}{localization.text(' empty successful answer(s).')}',
            f'{localization.text('Historical forecast: ')}{expected['expected_judged_plans']}{localization.text(' judged and ')}{expected['expected_computed_plans']}{localization.text(' computed plans; observed counts ')}{report['count_comparison']}{localization.text('. Computed: ')}{counts['computed_plans']}{localization.text(' planned, ')}{counts['computed_completed']}{localization.text(' completed, no quote required.')}',
            localization.text('PASS checks emitted claims only. Empty or non-absence answers do not confirm the forecast of fourteen claims. A matching count does not establish the same cohort.'),
            localization.text('Quotes establish text presence, not that an absence conclusion is true. See [the run audit](../audit/absence_quote_prediction.json) for per-question outcomes.')]
