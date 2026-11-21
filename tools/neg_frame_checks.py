#!/usr/bin/env python3
"""Check 688 (lane/neg-round2-d798, D-845, D-846; docs/loop/stages/NEG_ROUND2_D798.md): three switches of
`advice.methods.stepwise` in benchmark/baselines/neg_advisor_prompt.json, false as shipped, composing with C4, R3 and
R3b:

- #310 `party_frame`: a frame before every question naming the advised party, its positions on record, the other
  parties' positions on the article and the rounds so far (who put positions in which round, what is agreed, what
  fell from the previous round's text, the advised party's trades on record), from the item's declarations alone.
- #311 `reason_field`: a generated step after each stance, two lines (mechanism, effect) read by their heads into the
  piece's `reason`; a malformed reply is refused with its reason (no_mechanism, no_effect), only that field dropped.
- #3 `trade_read`: each declared trade of the advised party with both proposals on the table read once, keep or drop;
  a kept trade is offered again in the reply's `trades`.

The proofs, on the invented fixture item of tools/neg_advisor_checks.py with a scripted model (no model, no key):
1. frame: every question carries the frame; it names the party, its own positions, only the article's other
   positions, the rounds, the agreed and fallen articles and the trade; another persona gets other questions.
2. reason: one reason step per proposal with a stance, read into mechanism and effect; a reply without an effect line
   is refused no_effect and the stance kept.
3. trade: one read for the one trade on the table; keep offers it, drop does not, an undeclared answer is refused.
4. compose: all switches with C4, R3 and R3b under choice_first; recompose_stepwise gives the same reply.
5. refusals: non-boolean switches, a frame template without {history}, a reason template without an Effect: line, two
   keeping trade answers, a trade label yes, a trade template not naming a label, each refused; each switch off (or
   not declared) asks and composes exactly as before.

Run as built (passes), neutralised three times (the frame not put before a question; the reason's effect line not
read; a kept trade not offered), each must fail, restored and run again (passes).
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools"),
           str(ROOT / "benchmark" / "adapters")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_advisor as na  # noqa: E402
import neg_optional_checks as noc  # noqa: E402
import neg_round2_m4m10_checks as r2  # noqa: E402

caught, with_source = noc.caught, noc.with_source
REASON_OK = "Mechanism: it sets one fixed reporting time.\nEffect: the party you advise reports sooner."
REASON_BAD = "Mechanism: it sets one fixed reporting time."
START = "A proposal on the table"


def _config(**switches):
    return r2._config(**dict({"room_fate": True, "changes_id_echo": True}, **switches))


def _ask(item, asked, reason=REASON_OK, trade="keep"):
    inner_asked = []
    inner = r2._ask(item, inner_asked, changes=lambda i, t: "%s: %s" % (i, t))

    def ask(step, user, answers):
        asked.append((step, user))
        if step == na.REASON:
            return reason
        if step == na.TRADE_READ:
            return trade, noc._probs(answers, trade if trade in answers else answers[0])
        at = user.find(START)
        return inner(step, user[at:] if at >= 0 else user, answers)
    return ask


def _run(config, item=None, **script):
    item, asked = item or r2._item(), []
    reply, steps = na.stepwise_advice(config, item, _ask(item, asked, **script))
    return reply, steps, asked


def observe_frame():
    item = r2._item()
    reply, _s, asked = _run(_config(party_frame=True), item)
    users = [u for _s2, u in asked]
    compare_a1 = next(u for s, u in asked if s == "compare" and "fixed reporting time" in u.split(START)[1])
    other = copy.deepcopy(item)
    other["persona"] = dict(other["persona"], id="BETA")
    _r, _s3, asked_b = _run(_config(party_frame=True), other)
    return {"all_framed": all(u.startswith("You advise ALPHA (single)") for u in users),
            "own": all(q in compare_a1.split(START)[0] for q in ("We support reporting within a fixed time.",
                                                                  "We cannot accept mandatory contributions.")),
            "others_on_article": ("A fixed time is not workable for us." in compare_a1.split(START)[0],
                                  "Contributions must stay voluntary." in compare_a1.split(START)[0]),
            "history": [ln for ln in compare_a1.split(START)[0].split("THE ROUNDS SO FAR:")[1].split("\n") if ln.strip()],
            "persona_matters": [u for _s4, u in asked_b] != users, "pieces": r2._summary(reply)}


def expected_frame():
    return {"all_framed": True, "own": True, "others_on_article": (True, False),
            "history": ["- round 1: positions by ALPHA", "- round 2: positions by BETA, GROUP1",
                        "- agreed in this round's text: A3",
                        "- in the previous round's text, no longer in this one: A9",
                        "- trade on record by the party you advise, round 1: gave P-A1-1, expects P-A2-1"],
            "persona_matters": True, "pieces": r2.ROOM_PIECES}


def observe_reason():
    reply, steps, asked = _run(_config(reason_field=True))
    bad, bad_steps, _a = _run(_config(reason_field=True), reason=REASON_BAD)
    return {"asked": sum(1 for s, _u in asked if s == na.REASON),
            "read": {p: e.get(na.REASON) for p, e in sorted(reply["proposals"].items())}["P-A1-1"],
            "bad_refused": sorted({s["refused"] for s in bad_steps if s["step"] == na.REASON and s["refused"]}),
            "bad_kept_stance": r2._summary(bad), "bad_no_field": not any(na.REASON in e for e in bad["proposals"].values())}


def expected_reason():
    return {"asked": 3, "read": {"mechanism": "it sets one fixed reporting time.",
                                 "effect": "the party you advise reports sooner."},
            "bad_refused": ["no_effect"], "bad_kept_stance": r2.ROOM_PIECES, "bad_no_field": True}


def observe_trade():
    keep, _s, asked = _run(_config(trade_read=True))
    drop, _s2, _a2 = _run(_config(trade_read=True), trade="drop")
    odd, odd_steps, _a3 = _run(_config(trade_read=True), trade="maybe")
    item = r2._item()
    item["trades_on_record"] = [dict(item["trades_on_record"][0], get="P-A9-1")]
    none, _s4, asked_none = _run(_config(trade_read=True), item)
    return {"asked": sum(1 for s, _u in asked if s == na.TRADE_READ), "keep": keep["trades"],
            "reads": {k: (v["answered"], v["basis"]) for k, v in keep["trade_reads"].items()},
            "drop": drop["trades"], "odd": (odd["trades"], [s["refused"] for s in odd_steps if s["refused"]]),
            "off_table": sum(1 for s, _u in asked_none if s == na.TRADE_READ)}


def expected_trade():
    return {"asked": 1, "keep": [{"give": "P-A1-1", "get": "P-A2-1"}], "reads": {"T-1": ("keep", na.INFERRED)},
            "drop": [], "odd": ([], ["not_declared"]), "off_table": 0}

def observe_mandate():
    item = noc._item()          # the fixture's persona marks POS-2 a red line, from the document
    item["persona"]["operator_red_lines"] = [{"id": "OP-1", "text": "No obligation without a review clause."}]
    asked = []
    inner = _ask(item, asked)
    a1_2 = next(p["text"] for a in item["articles"] for p in a["proposals"] if p["id"] == "P-A1-2")

    def ask(step, user, answers):
        question = user.split(START, 1)[-1]
        if step == "red_line" and "No obligation without a review clause." in question and a1_2 in question:
            asked.append((step, user))
            return "yes", noc._probs(answers, "yes")
        return inner(step, user, answers)
    reply, _steps = na.stepwise_advice(_config(mandate_split=True), item, ask)
    users = [u for _s, u in asked]
    head = users[0].split(START)[0]
    red_part, bargain_part = head.split("ITS POINTS IT CAN BARGAIN")
    return {"all_led": all(u.startswith("THE MANDATE OF ALPHA (single)") for u in users),
            "red": ("We cannot accept mandatory contributions." in red_part,
                    "(given by the operator) No obligation without a review clause." in red_part,
                    "We support reporting within a fixed time." in red_part),
            "bargain": ("We support reporting within a fixed time." in bargain_part,
                        "We cannot accept mandatory contributions." in bargain_part),
            "operator_asked": sum(1 for s, u in asked if s == "red_line" and "No obligation without" in u.split(START)[-1]),
            "a1_2": (reply["proposals"]["P-A1-2"].get("conflict"), reply["proposals"]["P-A1-2"].get("operator_lines_hit")),
            "lines": [(r["id"], r["source"]) for r in na.party_red_lines(item)],
            "a1_2_text_seen": a1_2 in "".join(users)}


def expected_mandate():
    return {"all_led": True, "red": (True, True, False), "bargain": (True, False), "operator_asked": 3,
            "a1_2": ("conflict", ["OP-1"]),
            "lines": [("POS-2", "from the document"), ("OP-1", na.OPERATOR_SOURCE)], "a1_2_text_seen": True}


def observe_operator_file():
    import json
    import tempfile
    import neg_advisor_checks as nb
    with nb.setdir() as root, tempfile.TemporaryDirectory() as folder:
        cfg = copy.deepcopy(na.load_config())
        for g in cfg["models"]:
            if g["group"] == "system_advice":
                g["method"] = na.STEPWISE
        c = Path(folder) / "c.json"
        c.write_text(json.dumps(cfg), encoding="utf-8")
        src, out, op = Path(folder) / "s.json", Path(folder) / "o.json", Path(folder) / "op.json"
        na.build(root, "advice", ["system_advice"], src, config_path=c)
        item_id = json.loads(src.read_text(encoding="utf-8"))["prompts"][0]["item_id"]
        op.write_text(json.dumps({"schema": na.OPERATOR_SCHEMA, "items": {item_id: [{"id": "OP-1", "text": "A line."}]}}),
                      encoding="utf-8")
        value = na.rebuild(src, out, config_path=c, operator_path=op)
        bad = Path(folder) / "bad.json"
        bad.write_text(json.dumps({"schema": na.OPERATOR_SCHEMA, "items": {item_id: [{"id": "OP-1"}]}}), encoding="utf-8")
        return {"carried": value["prompts"][0]["item"]["persona"].get("operator_red_lines"),
                "digest": "operator_red_lines_sha256" in value,
                "bad": caught(lambda: na.rebuild(src, out, config_path=c, operator_path=bad))}


def expected_operator_file():
    return {"carried": [{"id": "OP-1", "text": "A line."}], "digest": True, "bad": "raised ValueError"}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def observe_compose():
    config, item = _config(party_frame=True, reason_field=True, trade_read=True), r2._item()
    rows, records, asked = [], {}, []
    inner = _ask(item, asked)

    def ask(step, user, answers):
        said = inner(step, user, answers)
        call = "c%03d" % (len(rows) + 1)
        rows.append({"step": step, "user_sha256": _sha(user), "call_id": call})
        if answers:
            _label, probs = said
            records[call] = {"backend_ok": True, "decision": {"answers": [{"label": a, "probability": probs[a]}
                                                                           for a in answers]}}
        else:
            records[call] = {"backend_ok": True, "reply": {"text": said}}
        return said

    live, _steps = na.stepwise_advice(config, item, ask)
    again, _s2 = na.recompose_stepwise(config, {"prompt_id": "a-fx", "item": item}, rows, records)
    return {"same": again == live, "pieces": r2._summary(again), "trades": len(again["trades"]),
            "reasons": sum(1 for e in again["proposals"].values() if na.REASON in e),
            "changes": sum(1 for e in again["proposals"].values() if "changes" in e)}


def expected_compose():
    return {"same": True, "pieces": r2.ROOM_PIECES, "trades": 1, "reasons": 3, "changes": 3}


def _bad(**change):
    value = _config(party_frame=True, reason_field=True, trade_read=True)
    value["advice"]["methods"][na.STEPWISE].update(change)
    return lambda: na.check_decoding(value)


def observe_refusals():
    block = na.load_config()["advice"]["methods"][na.STEPWISE]
    two_keep = copy.deepcopy(block["trade_answers"])
    two_keep[1]["keeps"] = True
    label_yes = copy.deepcopy(block["trade_answers"])
    label_yes[1]["label"] = "yes"
    return {"shipped_off": tuple(block[k] for k in ("party_frame", "reason_field", "trade_read", "mandate_split")),
            "mandate_no_red": caught(_bad(mandate_split=True, mandate_split_text=block["mandate_split_text"].replace("{red_lines}", "-"))),
            "frame_not_bool": caught(_bad(party_frame="on")), "reason_not_bool": caught(_bad(reason_field=1)),
            "trade_not_bool": caught(_bad(trade_read="yes")),
            "frame_no_history": caught(_bad(party_frame_text=block["party_frame_text"].replace("{history}", "-"))),
            "frame_no_none": caught(_bad(party_frame_none="")),
            "reason_no_effect": caught(_bad(reason_text=block["reason_text"].replace("Effect:", "Then"))),
            "two_keep": caught(_bad(trade_answers=two_keep)), "label_yes": caught(_bad(trade_answers=label_yes)),
            "trade_unnamed": caught(_bad(trade_text=block["trade_text"].replace("drop", "leave"))),
            "off_same": (noc._off_same(party_frame=False), noc._off_same(reason_field=False),
                         noc._off_same(trade_read=False), noc._off_same(mandate_split=False))}


def expected_refusals():
    raised = "raised ValueError"
    return {"shipped_off": (False, False, False, False), "mandate_no_red": raised, "frame_not_bool": raised, "reason_not_bool": raised,
            "trade_not_bool": raised, "frame_no_history": raised, "frame_no_none": raised, "reason_no_effect": raised,
            "two_keep": raised, "label_yes": raised, "trade_unnamed": raised, "off_same": (True, True, True, True)}


PROOFS = ("frame", "reason", "trade", "mandate", "operator_file", "compose", "refusals")
NEUTRALISATIONS = {
    "frame": ((na, "stepwise_advice", "said = ask(step, lead[0] + frame_now[0] + user, answers)",
               "said = ask(step, lead[0] + user, answers)"), ("frame",)),
    "reason": ((na, "_step_check", 'if sep and key in REASON_PARTS and rest.strip(" *") and key not in read:',
                'if sep and key == "mechanism" and rest.strip(" *") and key not in read:'), ("reason", "compose")),
    "trade": ((na, "stepwise_advice", 'trades.append({"give": t["give"], "get": t["get"]})', "pass"),
              ("trade", "compose")),
    "operator": ((na, "stepwise_advice", 'piece.setdefault("operator_lines_hit", []).append(op["id"])', "pass"),
                 ("mandate",)),
}


def run():
    space = globals()
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            first = {n: space["observe_" + n]() for n in PROOFS}
            broken = {}
            for name, (patch, proofs) in NEUTRALISATIONS.items():
                with with_source(*patch):
                    broken[name] = {n: caught(space["observe_" + n]) for n in proofs}
            again = {n: space["observe_" + n]() for n in PROOFS}
    except Exception as exc:
        return "FAIL", "%s %s" % (type(exc).__name__, str(exc)[:300])
    expected = {n: space["expected_" + n]() for n in PROOFS}
    for n in PROOFS:
        if first[n] != expected[n]:
            return "FAIL", "%s as built: %s" % (n, str(first[n])[:900])
        if again[n] != expected[n]:
            return "FAIL", "%s after restore: %s" % (n, str(again[n])[:400])
    for name, (_patch, proofs) in NEUTRALISATIONS.items():
        for n in proofs:
            if broken[name][n] == expected[n]:
                return "FAIL", "%s still passes when %s is neutralised" % (n, name)
    return "PASS", ("%d proofs, %d neutralisations, fail, restore, pass, no model: #310 the party frame names the "
                    "advised party, its positions, the article's other positions and the rounds (agreed, fallen, "
                    "trades) before every question, another persona other questions; #311 the reason field read "
                    "into mechanism and effect, a malformed one refused no_effect with the stance kept; #3 a declared "
                    "trade read keep or drop, a kept one offered; D-848 the mandate up front (red lines with their sources apart from bargainable points), an operator red line asked of every proposal and its yes a conflict, the operator file carried by rebuild; all with C4, R3 and R3b replayed the same; "
                    "refusals held; off unchanged (%s)" % (len(PROOFS), len(NEUTRALISATIONS), ", ".join(PROOFS)))


if __name__ == "__main__":
    status, detail = run()
    print("688", status, detail)
