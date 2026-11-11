"""Gate check 290 (loop stage S5, D-068): a model's answer on a paired plan Python could
compute nothing for is kept as a typed, model-written Finding record.

The defect class: where Python's checks produce no comparison for a unit and a rule (no
figure, band or declared field to compute from), the paired review asked a model and then
discarded its answer, so a rule that only reading can decide had no answer in the run at
all. D-068 keeps that answer under the rules a judged absence already follows:

- stamped by Python: the unit and the rule are the plan's, never the reply's (a rule id the
  reply names is replaced), the item id and revision are Python's;
- the same refusals: an answer quoting text the unit does not contain, and an absence claim
  with no quote, naming no field or naming a field the unit carries, are refused and listed
  in the pairing map (`uncomputable_refused`), never posted;
- a failed or refused reply keeps nothing and its reason is recorded;
- written by a model: posted with the model's backend and model (never `paired`/`python`),
  so every reader stamps it `model`; shown marked "Written by a model. Not promoted to an
  amendment. Not checked by Python."; never promoted to an amendment (the promoter reads
  only Python's records, check 269);
- the raw reply stays advisory (its items withheld from its own post), so a kept answer
  reaches the bus once, in Python's stamped copy (`stamped_by: python`,
  `judged_path: uncomputable`).

Every proof runs the real phase 5.5 paired review and the real phase 6 on a mocked run
(honest_output_checks.mocked_run): no model, provider, network or GPU. The replies are
PRE-AUTHORED, NOT MODEL OUTPUT. Each property is proven by neutralise, fail, restore, pass.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import finding_record
import honest_output_checks as hoc
import localization
import paired_review as pr
import reply_records
import summary_generators

ROOT = Path(__file__).resolve().parent.parent

RULE_ID, SOURCE_RULE_ID = "CONV-004", "CONV-H04"
RULES = hoc.RULES + [{"id": RULE_ID, "category": "conv-h04", "severity": "required",
                      "rule": "Every remark must say whether the seal was intact."}]
DELTA_TEXT = "Remark: the seal was broken on arrival."
TEXT = hoc.DOC_TEXT + "\n## Entry Delta\n\n" + DELTA_TEXT + "\n"
BACKEND, MODEL = "local_auditor", "fixture-auditor"
KEPT_QUOTE = "the seal was broken on arrival"
# The promoter's own input selection, held here so a neutralisation of the pipeline's
# copy is seen in the amendments the run wrote, not in this reading.
_PROMOTER = pr.computed_finding_items


def authored_items():
    """PRE-AUTHORED, NOT MODEL OUTPUT. One answer to keep (it names another rule and
    another unit, which Python replaces), one quoting text the unit does not contain, one
    absence claim with no quote, and one item without the Finding record's shape."""
    return [
        {"kind": "finding", "relation": "missing_field", "record_verdict": "irregular",
         "rule_id": "CONV-999", "procedure_id": "CONV-777", "source_rule_id": "CONV-ZZZ",
         "unit_id": "u09-somewhere-else", "stated_field": "seal state", "quote": KEPT_QUOTE,
         "explanation": "The remark says the seal was broken, not whether it was intact."},
        {"kind": "finding", "relation": "sum_mismatch", "record_verdict": "irregular",
         "quote": "the seal was intact", "explanation": "Quotes words the unit does not hold."},
        {"kind": "finding", "relation": "missing_field", "record_verdict": "ok",
         "stated_field": "seal state", "explanation": "An absence claim with no quote."},
        {"explanation": "A sentence and nothing else."},
    ]


def _reply(kind, call_id):
    items = authored_items()
    if kind == "kept":
        return {"ok": True, "backend": BACKEND, "model": MODEL, "call_id": call_id, "raw_text": "",
                "item_count": len(items), "parsed": {"agent": "PRACTICE_AUDITOR", "items": items}}
    if kind == "refused_on_the_wire":
        return {"ok": True, "backend": BACKEND, "model": MODEL, "call_id": call_id, "item_count": len(items),
                "raw_text": json.dumps({"status": "refused", "items": items}),
                "parsed": {"agent": "PRACTICE_AUDITOR", "items": items}}
    if kind == "failed":
        return {"ok": False, "backend": BACKEND, "model": MODEL, "call_id": call_id, "raw_text": "",
                "error": "contract_violation", "parsed": {"items": items}}
    return {"ok": True, "backend": BACKEND, "model": MODEL, "call_id": call_id, "raw_text": "",
            "parsed": {"status": "refused", "items": items}}


def run(kind="kept"):
    """One mocked run whose only uncomputable plan on CONV-004 gets the authored reply."""
    seen = {}

    def other(payload, call_id, kwargs):
        if payload.get("rule_id") != RULE_ID:
            return None
        seen["advisory"] = kwargs.get("items_are_advisory")
        seen["comparisons"] = payload.get("computed_comparisons")
        return _reply(kind, call_id)

    td = tempfile.mkdtemp(prefix="shimmer_d068_")
    out = hoc.mocked_run(td, style_guardian=False, text=TEXT, rules=RULES, other_reply=other)
    out["seen"], out["tmp"] = seen, td
    return out


def _bus(run_dir):
    path = Path(run_dir) / "logs" / "agent_bus.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _delta_unit(doc_id):
    return next(u for u in pr.unit_texts_for(TEXT, doc_id) if "entry-delta" in u)


def observe(kind="kept"):
    """Everything the proofs read, from the saved run (no verdict here)."""
    r = run(kind)
    try:
        return _observe(r)
    finally:
        shutil.rmtree(r["tmp"], ignore_errors=True)


def _observe(r):
    run_dir, doc_id = r["run_dir"], r["doc"]["id"]
    unit = _delta_unit(doc_id)
    pairing = json.loads((Path(run_dir) / "audit" / "pairing_map.json").read_text(encoding="utf-8"))[doc_id]
    posts = [m["body"] for m in _bus(run_dir)
             if (m.get("body") or {}).get(pr.JUDGED_PATH_FIELD) == pr.JUDGED_PATH_UNCOMPUTABLE]
    items = [i for b in posts for i in (b.get("payload") or {}).get("items") or []]
    calls = [c for c in pairing.get("judging_calls") or [] if c.get("rule_id") == RULE_ID]
    master = json.loads(r["files"]["review_data.json"].read_text(encoding="utf-8"))
    summary = r["files"]["document_summary.md"].read_text(encoding="utf-8")
    # the promoter's own input selection, applied to the posts as phase 6 receives them
    promotable = _PROMOTER([{"ok": True, "doc_id": doc_id, "backend": b.get("backend"),
                                             "model": b.get("model"), "parsed": b.get("payload")}
                                            for b in posts], doc_id=doc_id)
    scorer = None
    reader = ROOT / "benchmark" / "adapters" / "common" / "records.py"
    if reader.is_file():
        sys.path.insert(0, str(ROOT / "benchmark"))
        try:
            from adapters.common import records as scorer_records
            scorer = [(x.get("unit_id"), x.get("source_rule_id"), x.get("written_by"))
                      for x in scorer_records.read_bus(run_dir, doc_id)["records"]
                      if x.get("source_rule_id") == SOURCE_RULE_ID]
        finally:
            sys.path.remove(str(ROOT / "benchmark"))
    return {
        "unit": unit, "advisory": r["seen"].get("advisory"), "comparisons": r["seen"].get("comparisons"),
        "posts": [(b.get("backend"), b.get("model"), b.get("stamped_by"),
                   finding_record.written_by(b.get("backend"), b.get("model"))) for b in posts],
        "items": [(i.get("unit_id"), i.get("rule_id"), i.get("source_rule_id"), i.get("procedure_id"),
                   i.get("item_id"), i.get(pr.JUDGED_PATH_FIELD), i.get("absence_path"), i.get("quote"))
                  for i in items],
        "calls": [(c.get("outcome"), c.get("judged_listed"), c.get("judged_refused")) for c in calls],
        "judged": [(e.get("unit_id"), e.get("items"), e.get("refused"), e.get("not_finding_shaped"),
                    e.get("not_kept_reason")) for e in pairing.get("uncomputable_judged") or []
                   if e.get("rule_id") == RULE_ID],
        "refused": sorted(e.get("reason") for e in pairing.get("uncomputable_refused") or []),
        "kept_count": pairing.get("uncomputable_kept_count"),
        "promotable": len(promotable),
        "amendments": [(a.get("finding_unit_id"), a.get("finding_rule_id")) for a in master.get("amendments", [])
                       if a.get("finding_rule_id") == RULE_ID or a.get("finding_unit_id") == unit],
        "not_promoted": [(f.get("unit_id"), f.get("rule_id"), f.get("checked_by_python"), f.get("promoted"),
                          f.get("model_claimed_verdict"))
                         for f in master.get("model_findings_not_promoted", []) if f.get("rule_id") == RULE_ID],
        "summary_marked": [finding_record.MODEL_FINDING_MARK in ln for ln in summary.splitlines() if unit in ln],
        "scorer": scorer,
        "outcomes": _outcomes(run_dir),
    }


def _outcomes(run_dir):
    """The outcome rows this path wrote, and whether the call ends as not promoted."""
    folder = Path(run_dir) / "audit" / "model_replies"
    file = folder / reply_records.OUTCOMES_NAME
    rows = [json.loads(l) for l in file.read_text(encoding="utf-8").splitlines() if l.strip()] if file.is_file() else []
    mine = [r for r in rows if r.get("source") == "paired_uncomputable"]
    return [(r.get("outcome"), r.get("findings_withheld"), reply_records.outcome_of(folder, r.get("call_id")))
            for r in mine]


def body_kept():
    o = observe("kept")
    unit = o["unit"]
    want_item = (unit, RULE_ID, SOURCE_RULE_ID, None, "PRACTICE_AUDITOR:finding:%s:%s:0" % (unit, RULE_ID),
                 pr.JUDGED_PATH_UNCOMPUTABLE, None, KEPT_QUOTE)
    problems = []
    if o["advisory"] is not True or o["comparisons"] != []:
        problems.append("the uncomputable call is not advisory on its own post: %s" % ((o["advisory"], o["comparisons"]),))
    if o["posts"] != [(BACKEND, MODEL, "python", finding_record.WRITTEN_BY_MODEL)]:
        problems.append("posts: %s" % o["posts"])
    if o["items"] != [want_item]:
        problems.append("items: %s" % o["items"])
    if o["calls"] != [("judged_uncomputable", 1, 2)]:
        problems.append("judging calls: %s" % o["calls"])
    if o["judged"] != [(unit, 1, 2, 1, None)] or o["kept_count"] != 1:
        problems.append("pairing map: %s %s" % (o["judged"], o["kept_count"]))
    if o["refused"] != ["absence claim supplies no quote", "quotes text that does not appear in this unit"]:
        problems.append("refusals: %s" % o["refused"])
    if o["promotable"] or o["amendments"]:
        problems.append("promoted: %s %s" % (o["promotable"], o["amendments"]))
    if o["not_promoted"] != [(unit, RULE_ID, False, False, "irregular")]:
        problems.append("model_findings_not_promoted: %s" % o["not_promoted"])
    if not o["summary_marked"] or not all(o["summary_marked"]):
        problems.append("document_summary.md marks: %s" % o["summary_marked"])
    if o["outcomes"] != [("not_promoted", 1, "not_promoted")]:
        problems.append("reply outcome: %s" % o["outcomes"])
    if o["scorer"] is not None and o["scorer"] != [(unit, SOURCE_RULE_ID, "model")]:
        problems.append("the adapters' record reader sees: %s" % o["scorer"])
    return ("FAIL", "; ".join(problems)) if problems else (
        "PASS", "kept once as a model's record on the plan's unit and rule, two answers refused, one "
                "non-record counted, marked, not promoted%s" % ("" if o["scorer"] is None else
                                                               ", read by the adapters as written by model"))


def body_not_kept():
    problems = []
    for kind, reason in (("failed", "reply_failed"), ("refused", "reply_refused"),
                         ("refused_on_the_wire", "reply_refused")):
        o = observe(kind)
        if o["posts"] or o["items"] or o["not_promoted"]:
            problems.append("%s: records kept %s %s" % (kind, o["items"], o["not_promoted"]))
        want_outcome = "reply_failed" if kind == "failed" else "judged_uncomputable"
        if o["calls"] != [(want_outcome, 0, 0)]:
            problems.append("%s: calls %s" % (kind, o["calls"]))
        if o["judged"] != [(o["unit"], 0, 0, 0, reason)]:
            problems.append("%s: pairing map %s" % (kind, o["judged"]))
        if o["outcomes"]:
            problems.append("%s: an outcome for nothing kept: %s" % (kind, o["outcomes"]))
    return ("FAIL", "; ".join(problems)) if problems else (
        "PASS", "a failed and a refused reply keep nothing and record why")


def _without_source(real, dropped):
    def write(run_context, call_id, outcome, *, source, **detail):
        return None if source == dropped else real(run_context, call_id, outcome, source=source, **detail)
    return write


def body_absence_rule():
    """Open item 29 (2): a judged absence is attributed to the plan's rule, as a D-068 answer is."""
    import pipeline
    named = dict(authored_items()[0])
    reply = {"parsed": {"items": [named]}}
    got = pipeline._stamped_judged_items(reply, "PRACTICE_AUDITOR", "u01-x", RULE_ID, SOURCE_RULE_ID)
    bare = pipeline._stamped_judged_items(reply, "PRACTICE_AUDITOR", "u01-x", RULE_ID, "")
    # D-268: dedupe keys on the rule. Two plans on one unit stay two records; two claims one
    # reply made under two rule ids, on one plan, are one.
    elsewhere = pipeline._stamped_judged_items(reply, "PRACTICE_AUDITOR", "u01-x", "CONV-005", "")
    twin = {"parsed": {"items": [named, dict(named, rule_id="CONV-888", stated_field="another field")]}}
    one_plan = pipeline._stamped_judged_items(twin, "PRACTICE_AUDITOR", "u01-x", RULE_ID, SOURCE_RULE_ID)
    ok = (len(got) == 1 and got[0].get("rule_id") == RULE_ID and got[0].get("source_rule_id") == SOURCE_RULE_ID
          and got[0].get("procedure_id") is None and got[0].get("absence_path") == "judged"
          and got[0].get("unit_id") == "u01-x" and "source_rule_id" not in bare[0]
          and len(pr.dedupe(got + elsewhere)) == 2 and len(one_plan) == 2 and len(pr.dedupe(one_plan)) == 1)
    return ("PASS", "a judged absence carries the plan's rule, never one the reply names") if ok else ("FAIL", str(got))


def body_call_counts():
    """Open item 29 (1): a call on an uncomputable plan is not a call that could carry a note."""
    calls = [{"plan_kind": pr.JUDGED_ABSENCE_PLAN}, {"plan_kind": "uncomputable"}, {"plan_kind": "compared"}]
    counts = pr.judging_call_counts(calls)
    text = summary_generators.calls_and_notes_text(calls, 0)
    words = summary_generators.UNCOMPUTABLE_CALLS_TEXT.format(uncomputable_calls=1)
    none = summary_generators.calls_and_notes_text(calls[:1], 0)
    told = summary_generators.context_findings_sentence(1, summary_generators.findings_provenance([], calls), "doc")
    ok = (counts == {"calls": 3, "note_calls": 1, "absence_calls": 1, "uncomputable_calls": 1, "pair_calls": 0, "cell_calls": 0}
          and words in text and "could not compute" not in none and words in told
          and localization.message(summary_generators.UNCOMPUTABLE_CALLS_TEXT, "tr")
          != summary_generators.UNCOMPUTABLE_CALLS_TEXT)
    return ("PASS", "calls on an uncomputable plan are counted apart, and said only when there are any") if ok else (
        "FAIL", "%s %s" % (counts, text))


def body_summaries_in_turkish():
    """Open item 29 (1): the clause is rendered in both summaries of a Turkish run."""
    seen = {}

    def other(payload, call_id, kwargs):
        return _reply("kept", call_id) if payload.get("rule_id") == RULE_ID else None
    with tempfile.TemporaryDirectory(prefix="shimmer_d268_tr_", ignore_cleanup_errors=True) as td:
        run_out = hoc.mocked_run(td, style_guardian=False, text=TEXT, rules=RULES, other_reply=other, language="tr")
        for name in ("document_summary.md", "grounding_summary.md"):
            seen[name] = run_out["files"][name].read_text(encoding="utf-8")
    bad = [n for n, t in seen.items() if "hiç not istenmeyen çağrılar" not in t or "could not compute" in t]
    return ("FAIL", "not rendered in %s" % bad) if bad else ("PASS", "the clause is Turkish in both summaries")


def _neutralisations():
    return [
        ("the clause has no Turkish row", body_summaries_in_turkish,
         lambda: patch.object(summary_generators, "UNCOMPUTABLE_CALLS_TEXT",
                              "calls Python could not compute: {uncomputable_calls}")),
        ("a refusal on the wire read as an answer", body_not_kept,
         lambda: patch.object(reply_records, "is_refusal",
                              lambda parsed, raw: isinstance(parsed, dict) and parsed.get("status") == "refused")),
        ("D-068 branch not taken", body_kept, lambda: patch.object(pr, "UNCOMPUTABLE_PLAN", "never_planned")),
        ("rule taken from the reply", body_kept, lambda: patch.object(pr, "plan_rule", lambda item, **k: item)),
        ("a judged absence keeps the reply's rule", body_absence_rule,
         lambda: patch.object(pr, "plan_rule", lambda item, **k: item)),
        ("uncomputable calls counted as note calls", body_call_counts,
         lambda: patch.object(pr, "UNCOMPUTABLE_PLAN", "never_planned")),
        ("the outcome stays advisory", body_kept,
         lambda: patch.object(reply_records, "write_outcome",
                              _without_source(reply_records.write_outcome, "paired_uncomputable"))),
        ("refusals skipped", body_kept, lambda: patch.object(pr, "judged_item_refusal", lambda *a, **k: None)),
        ("promoter reads model records", body_kept,
         lambda: patch.object(pr, "computed_finding_items",
                              lambda results, agent=None, **k: [i for r in results or [] if r.get("ok")
                                                                for i in ((r.get("parsed") or {}).get("items") or [])
                                                                if finding_record.is_finding(i)])),
        ("failed reply read", body_not_kept, lambda: patch.object(pr, "reply_kept_reason", lambda r: None)),
    ]


def check():
    shipped = [body_kept(), body_not_kept(), body_absence_rule(), body_call_counts(), body_summaries_in_turkish()]
    if any(v != "PASS" for v, _ in shipped):
        return "FAIL", "shipped: " + "; ".join(d for v, d in shipped if v != "PASS")
    for name, body, neutralise in _neutralisations():
        with neutralise():
            verdict, detail = body()
        if verdict != "FAIL":
            return "FAIL", "neutralised (%s) still passed: %s" % (name, detail)
    restored = [body_kept(), body_not_kept(), body_absence_rule(), body_call_counts(), body_summaries_in_turkish()]
    if any(v != "PASS" for v, _ in restored):
        return "FAIL", "after restore: " + "; ".join(d for v, d in restored if v != "PASS")
    return "PASS", "%s; %s; %d neutralisations fail, restore passes" % (
        shipped[0][1], shipped[1][1], len(_neutralisations()))


if __name__ == "__main__":
    print(check())
