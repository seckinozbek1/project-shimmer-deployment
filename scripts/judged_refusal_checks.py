"""The live path behind gate checks 229 and 233: every phase 5.5 path that can keep a
model's judged answer runs the quote check and the absence-claim refusals.

Since D-068 (commit d18cf93) both judged paths in `pipeline.phase_5_5_convention_review`
(a judged absence, and a plan Python could compute nothing for) refuse through ONE helper,
`paired_review.judged_item_refusal`, which calls `paired_review.refuses_judged_absence` (an
absence claim with no quote, naming no field, or naming a field the unit carries) and
`paired_review.quote_not_in_unit` (a quote the unit does not contain). The two checks used
to inspect `pipeline.py` for the name `quote_not_in_unit` and to edit the real
`paired_review.py` at the first textual copy of the no-quote line, so the move broke both
while the rules still held. They now read what the REAL phase 5.5 refused and kept.

Each observation runs the real phase 5.5 paired review on a mocked run
(`honest_output_checks.mocked_run`): no model, provider, network or GPU. The replies are
PRE-AUTHORED, NOT MODEL OUTPUT. Everything is written under a tempdir and removed.
"""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path

import honest_output_checks as hoc
import paired_review as pr
import uncomputable_judgment_checks as ujc

ROOT = Path(__file__).resolve().parent.parent

QUOTE_REASON = "quotes text that does not appear in this unit"
NO_QUOTE_REASON = "absence claim supplies no quote"
# The judged-absence fixture: a rule scoped on `reading` with no declared requirement,
# so each unit carrying a reading is one judged-absence question.
ABSENCE_RULES = hoc.RULES + [hoc.JUDGED_RULE]
ABSENCE_UNIT = "entry-gamma"
ABSENCE_KEPT_QUOTE = "Reading: 12 units"


def _claim(quote=None, rule_id=None):
    """PRE-AUTHORED, NOT MODEL OUTPUT: an absence claim naming a field the unit lacks."""
    item = {"kind": "finding", "record_verdict": "irregular", "relation": "missing_field",
            "stated_field": "countersignature", "explanation": "The entry carries no countersignature."}
    if rule_id:
        item["rule_id"] = rule_id
    if quote is not None:
        item["quote"] = quote
    return item


def _authored(kept_quote, rule_id):
    """One claim to keep, one quoting words the unit does not contain, one with no quote
    and one with a blank quote."""
    return [_claim(kept_quote, rule_id), _claim("the countersignature is not stated", rule_id),
            _claim(None, rule_id), _claim("   ", rule_id)]


def _absence_reply(payload, call_id):
    base = {"ok": True, "backend": "local_auditor", "model": "fixture-auditor", "call_id": call_id,
            "raw_text": ""}
    items = (_authored(ABSENCE_KEPT_QUOTE, hoc.JUDGED_RULE["id"])
             if ABSENCE_UNIT in str(payload.get("unit_id") or "") else [])
    return dict(base, item_count=len(items), parsed={"agent": "PRACTICE_AUDITOR", "items": items})


def _uncomputable_reply(payload, call_id, kwargs):
    if payload.get("rule_id") != ujc.RULE_ID:
        return None
    items = _authored(ujc.KEPT_QUOTE, None)
    return {"ok": True, "backend": ujc.BACKEND, "model": ujc.MODEL, "call_id": call_id, "raw_text": "",
            "item_count": len(items), "parsed": {"agent": "PRACTICE_AUDITOR", "items": items}}


def _pairing(run):
    path = Path(run["run_dir"]) / "audit" / "pairing_map.json"
    return json.loads(path.read_text(encoding="utf-8"))[run["doc"]["id"]]


def observe():
    """What the real phase 5.5 refused and kept on both judged paths (no verdict here)."""
    td = tempfile.mkdtemp(prefix="shimmer_judged_refusal_")
    try:
        for name in ("absence", "uncomputable"):
            (Path(td) / name).mkdir()
        run = hoc.mocked_run(Path(td) / "absence", style_guardian=False, rules=ABSENCE_RULES,
                             absence_reply=_absence_reply)
        pairing = _pairing(run)
        absence = {
            "refused": sorted(e.get("reason") for e in pairing.get("absence_refused") or []
                              if ABSENCE_UNIT in str(e.get("unit_id"))),
            "kept": sum(int(e.get("items") or 0) for e in pairing.get("absence") or []
                        if e.get("path") == "judged" and ABSENCE_UNIT in str(e.get("unit_id"))),
        }
        run = hoc.mocked_run(Path(td) / "uncomputable", style_guardian=False, text=ujc.TEXT,
                             rules=ujc.RULES, other_reply=_uncomputable_reply)
        pairing = _pairing(run)
        uncomputable = {
            "refused": sorted(e.get("reason") for e in pairing.get("uncomputable_refused") or []
                              if e.get("rule_id") == ujc.RULE_ID),
            "kept": sum(int(e.get("items") or 0) for e in pairing.get("uncomputable_judged") or []
                        if e.get("rule_id") == ujc.RULE_ID),
        }
        return {"absence_judged": absence, "uncomputable": uncomputable}
    finally:
        shutil.rmtree(td, ignore_errors=True)


def verdict(observed, reason):
    """FAIL unless, on BOTH judged paths, `reason` is among the refusals and exactly the
    one claim that quotes the unit and names a field it lacks is kept. The full expected
    refusal list is checked too, so a refusal that moves to another reason is seen."""
    want = sorted([QUOTE_REASON, NO_QUOTE_REASON, NO_QUOTE_REASON])
    problems = []
    for path, got in sorted(observed.items()):
        if reason not in got["refused"]:
            problems.append("%s: no refusal '%s' (refused %s)" % (path, reason, got["refused"]))
        elif got["refused"] != want or got["kept"] != 1:
            problems.append("%s: refused %s, kept %d; expected %s, kept 1"
                            % (path, got["refused"], got["kept"], want))
    return ("FAIL", "; ".join(problems)) if problems else (
        "PASS", "on the judged-absence path and the uncomputable path alike, the claim quoting "
                "words the unit lacks and both claims with no quote are refused and the one "
                "quoted claim is kept")


NO_QUOTE_LINE = 'if not str(item.get("quote") or "").strip():'


def refuses_judged_absence_without_quote_test():
    """`paired_review.refuses_judged_absence` compiled from the REAL source file with its
    no-quote test replaced by `if False:`, located by the function's own AST span so no other
    copy of that line in the file is touched. The file is read, never written. None when the
    function or the line cannot be found, which the caller reports as a failure."""
    source = (ROOT / "scripts" / "paired_review.py").read_text(encoding="utf-8")
    node = next((n for n in ast.parse(source).body
                 if isinstance(n, ast.FunctionDef) and n.name == "refuses_judged_absence"), None)
    if node is None:
        return None
    lines = source.splitlines(keepends=True)
    func = "".join(lines[node.lineno - 1:node.end_lineno])
    if NO_QUOTE_LINE not in func:
        return None
    scope = dict(vars(pr))
    exec(compile(func.replace(NO_QUOTE_LINE, "if False:", 1), "neutralised_paired_review", "exec"), scope)
    return scope["refuses_judged_absence"]
