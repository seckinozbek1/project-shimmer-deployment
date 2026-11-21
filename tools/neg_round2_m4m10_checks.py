#!/usr/bin/env python3
"""Check 686 (lane/neg-round2-m4-m10, D-840; docs/loop/stages/NEG_ROUND2_M4_M10.md): round 2's two switches in
`advice.methods.stepwise` of benchmark/baselines/neg_advisor_prompt.json, both false as shipped.

- R3 `room_fate` (bar lines 2 and 3, M10 and M4): the chain's stance was counter whenever the open point step said
  yes, else reject on a conflict, else accept, and the open point step is shown the proposal's text alone. R3 drops
  that step and asks one CHOICE-A question per proposal, shown the other proposals on its article and every touched
  position with the label the chain's own step answered for it; the answer sets the stance by the declared pairs.
- R3b `changes_id_echo` (bar line 5, the drop share): a `changes` line that starts with exactly the proposal id the
  prompt showed and a colon is read without it; the rest is checked word for word as before.

The proofs, on the invented fixture item of tools/neg_advisor_checks.py with a scripted model (no model, no key, no
real item, nothing launched):

1. blind_open_point: the C4 chain as run (compare, choice_first), open point yes: every proposal is a counter, the
   conflict on P-A2-1 included, and the open point question shows no position and no other proposal.
2. room_fate: R3 on: the open point is never asked; one room fate per proposal, showing the other proposals of the
   article and each touched position with its compare label; kept, changed and removed set accept, counter and
   reject; the conflict field is the compare step's; the wording is asked for the counter alone; marked inferred.
3. both_orders: the same stances under generated_first.
4. refused_fate: an undeclared room answer leaves that proposal without a stance, counted, and the chain goes on.
5. id_echo: a changes line with the shown id in front is refused off and read without the id on (marked id_echo); a
   wrong id and a paraphrase are refused either way.
6. replay: the same reply composed again from saved step records by neg_advisor.recompose_stepwise, both switches on.
7. rebuild: a prompts file built from the fixture set, rebuilt under a switch copy: the same prompt ids and items, the
   new config digest, load_prompts passes, rebuilt_from is the source's SHA-256; an output inside the repository is
   refused.
8. refusals: non-boolean switches, room_fate with fate_forecast, two answers setting one stance, a stance label, an
   upper-case label, a missing alone or none text, a template missing {alternatives}, naming no label or showing
   {changes}, each refused; both switches off (or not declared) ask and compose exactly as before.

Round 3 (D-863, D-864; docs/loop/stages/NEG_ROUND3.md): a fourth room fate answer setting counter (`open`, still in
dispute) and the switch `room_unanchored` (false as shipped), which shows each touched position without its "read:"
label.

9. r2_unchanged: room_unanchored declared false and not declared at all ask, step and compose the same (round 2).
10. open_counter: with kept, changed, removed and open declared, an open proposal is a counter with its wording asked,
   under both orders; the loader returns the four answers.
11. unanchored: room_unanchored true shows every touched position and no "read:" label; the other steps and the
   stances unchanged.
12. r3_refusals: a duplicate label, an undeclared stance, an answer with no stance, a fourth answer setting accept or
   reject, a fifth answer, a template not naming the fourth label, a non-boolean switch and the switch without
   room_fate, each refused; shipped off.

Run as built (passes), neutralised seven times (the room answer's stance not used; the id not taken off; the fourth
answer refused; an undeclared stance admitted; a duplicate label admitted; the labels kept when unanchored; the labels
dropped when anchored), each must fail, restored and run again (passes).
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools"),
           str(ROOT / "benchmark" / "adapters")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_advisor as na  # noqa: E402
import neg_advisor_checks as nb  # noqa: E402
import neg_optional_checks as noc  # noqa: E402

caught, with_source = noc.caught, noc.with_source
FATES = {"P-A1-1": "kept", "P-A1-2": "changed", "P-A2-1": "removed"}


def _item():
    item = noc._item()
    item["persona"]["red_lines"] = []
    item["persona"].pop("red_line_sources", None)
    return item


def _config(**switches):
    return noc._config(**dict({"conflict_question": na.COMPARE, "order": na.CHOICE_FIRST}, **switches))


def _texts(item):
    return {p["text"]: p["id"] for a in item["articles"] for p in a["proposals"]}


def _ask(item, asked, fates=None, open_point="yes", changes=None):
    """A scripted model: compare `against` on positions the fixture marks oppose, else `fits`; the open point
    `open_point`; the room fate `fates[proposal]`; the changes line `changes(id, text)` (the text itself when None)."""
    texts, fates = _texts(item), dict(fates or FATES)

    def ask(step, user, answers):
        pid = next((i for t, i in texts.items() if user.split("\n")[1:2] == [t] or
                    ("%s: %s" % (i, t)) in user), None)
        pos = next((p for p in item["positions"] if p["quote"] in user), None)
        asked.append((step, pid, pos["id"] if pos and step != na.ROOM_FATE else None, user))
        if not answers:
            if step == "changes":
                text = next(t for t in texts if t in user)
                return changes(texts[text], text) if changes else text
            return "A middle ground wording for the fixture"
        if step == "compare":
            label = "against" if noc.STANCE_OF[pos["id"]] == "oppose" else "fits"
        elif step == "open_point":
            label = open_point
        elif step == na.ROOM_FATE:
            label = fates[pid]
        else:
            label = "no"
        return label, noc._probs(answers, label if label in answers else answers[0])
    return ask


def _run(config, item=None, **script):
    item, asked = item or _item(), []
    reply, steps = na.stepwise_advice(config, item, _ask(item, asked, **script))
    return reply, steps, asked


def _summary(reply):
    return {pid: (e.get("conflict"), e.get("stance")) for pid, e in sorted(reply["proposals"].items())}


def _of(asked, step):
    return [(p, q) for s, p, q, _u in asked if s == step]


def observe_blind_open_point():
    item = _item()
    reply, _s, asked = _run(_config(), item)
    users = [u for s, _p, _q, u in asked if s == "open_point"]
    texts = list(_texts(item))
    return {"pieces": _summary(reply), "open_points": len(users),
            "shows_a_position": any(p["quote"] in u for p in item["positions"] for u in users),
            "shows_another_proposal": any(sum(t in u for t in texts) > 1 for u in users)}


def expected_blind_open_point():
    return {"pieces": {"P-A1-1": ("no_conflict", "counter"), "P-A1-2": ("not_stated", "counter"),
                       "P-A2-1": ("conflict", "counter")},
            "open_points": 3, "shows_a_position": False, "shows_another_proposal": False}


ROOM_PIECES = {"P-A1-1": ("no_conflict", "accept"), "P-A1-2": ("not_stated", "counter"),
               "P-A2-1": ("conflict", "reject")}


def observe_room_fate():
    item = _item()
    reply, _s, asked = _run(_config(room_fate=True), item)
    users = {p: u for s, p, _q, u in asked if s == na.ROOM_FATE}
    block = _config()["advice"]["methods"][na.STEPWISE]
    return {"pieces": _summary(reply), "open_points": len(_of(asked, "open_point")),
            "room_asked": sorted(users), "offered": sorted({tuple(a) for a in [("kept", "changed", "removed")]}),
            "a1_1_shows_a1_2": _texts_of(item, "P-A1-2") in users["P-A1-1"],
            "a1_1_reads": [line.strip() for line in users["P-A1-1"].split("\n") if line.strip().startswith("read:")],
            "a2_1_alone": block["room_fate_alone"] in users["P-A2-1"],
            "a1_2_none": block["room_fate_none"] in users["P-A1-2"],
            "wording_for": [p for p, _q in _of(asked, "wording")],
            "marks": {p: (e.get(na.ROOM_FATE) or {}).get("basis") for p, e in sorted(reply["proposals"].items())},
            "answered": {p: (e.get(na.ROOM_FATE) or {}).get("answered") for p, e in sorted(reply["proposals"].items())}}


def _texts_of(item, pid):
    return next(t for t, i in _texts(item).items() if i == pid)


def expected_room_fate():
    return {"pieces": ROOM_PIECES, "open_points": 0, "room_asked": ["P-A1-1", "P-A1-2", "P-A2-1"],
            "offered": [("kept", "changed", "removed")], "a1_1_shows_a1_2": True,
            "a1_1_reads": ["read: fits", "read: fits", "read: against"], "a2_1_alone": True, "a1_2_none": True,
            "wording_for": ["P-A1-2"], "marks": {p: na.INFERRED for p in ROOM_PIECES},
            "answered": dict(FATES)}


def observe_both_orders():
    out = {}
    for order in (na.GENERATED_FIRST, na.CHOICE_FIRST):
        reply, _s, asked = _run(_config(room_fate=True, order=order))
        out[order] = {"pieces": _summary(reply), "open_points": len(_of(asked, "open_point")),
                      "room": len(_of(asked, na.ROOM_FATE))}
    return out


def expected_both_orders():
    one = {"pieces": ROOM_PIECES, "open_points": 0, "room": 3}
    return {na.GENERATED_FIRST: one, na.CHOICE_FIRST: one}


def observe_refused_fate():
    reply, steps, _a = _run(_config(room_fate=True), fates=dict(FATES, **{"P-A1-1": "maybe"}))
    return {"pieces": _summary(reply), "refused": [(s["step"], s["proposal"], s["refused"]) for s in steps
                                                   if s["refused"]]}


def expected_refused_fate():
    return {"pieces": dict(ROOM_PIECES, **{"P-A1-1": ("no_conflict", None)}),
            "refused": [(na.ROOM_FATE, "P-A1-1", "not_declared")]}


def observe_id_echo():
    out = {}
    forms = {"echo": lambda i, t: "%s: %s" % (i, t), "wrong_id": lambda i, t: "P-A9-9: %s" % t,
             "paraphrase": lambda i, t: "It changes what the parties must do about this matter."}
    for on in (False, True):
        for name, form in forms.items():
            reply, steps, _a = _run(_config(changes_id_echo=on), changes=form)
            out["%s_%s" % (name, "on" if on else "off")] = {
                "refused": sorted({s["refused"] for s in steps if s["step"] == "changes" and s["refused"]}),
                "kept": sum(1 for e in reply["proposals"].values() if e.get("changes") in _texts(_item())),
                "marked": sum(1 for s in steps if s.get("id_echo"))}
    return out


def expected_id_echo():
    refused = {"refused": ["not_in_the_proposal"], "kept": 0, "marked": 0}
    return {"echo_off": refused, "wrong_id_off": refused, "paraphrase_off": refused,
            "echo_on": {"refused": [], "kept": 3, "marked": 3}, "wrong_id_on": refused, "paraphrase_on": refused}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def observe_replay():
    config, item = _config(room_fate=True, changes_id_echo=True), _item()
    rows, records, asked = [], {}, []
    inner = _ask(item, asked, changes=lambda i, t: "%s: %s" % (i, t))

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
    return {"same": again == live, "pieces": _summary(again),
            "changes": sum(1 for e in again["proposals"].values() if "changes" in e)}


def expected_replay():
    return {"same": True, "pieces": ROOM_PIECES, "changes": 3}


def observe_rebuild():
    with nb.setdir() as root, tempfile.TemporaryDirectory() as folder:
        shipped = copy.deepcopy(na.load_config())
        for g in shipped["models"]:
            if g["group"] == "system_advice":
                g["method"] = na.STEPWISE
        base_cfg, r2_cfg = Path(folder) / "c4.json", Path(folder) / "r2.json"
        c4 = copy.deepcopy(shipped)
        c4["advice"]["methods"][na.STEPWISE].update(conflict_question=na.COMPARE, order=na.CHOICE_FIRST)
        r2 = copy.deepcopy(c4)
        r2["advice"]["methods"][na.STEPWISE].update(room_fate=True, changes_id_echo=True)
        base_cfg.write_text(json.dumps(c4), encoding="utf-8")
        r2_cfg.write_text(json.dumps(r2), encoding="utf-8")
        src, out = Path(folder) / "src.json", Path(folder) / "r2_prompts.json"
        na.build(root, "advice", ["b1", "system_advice"], src, config_path=base_cfg)
        value = na.rebuild(src, out, config_path=r2_cfg)
        before = json.loads(src.read_text(encoding="utf-8"))
        inside = caught(lambda: na.rebuild(src, ROOT / "output" / "r2_never.json", config_path=r2_cfg))
        return {"ids": [p["prompt_id"] for p in value["prompts"]] == [p["prompt_id"] for p in before["prompts"]],
                "items": [p["item"] for p in value["prompts"]] == [p["item"] for p in before["prompts"]],
                "digest_new": value["config_sha256"] != before["config_sha256"],
                "switches": (value["config"]["advice"]["methods"][na.STEPWISE]["room_fate"],
                             value["config"]["advice"]["methods"][na.STEPWISE]["changes_id_echo"]),
                "loads": len(na.load_prompts(out)), "from": value["rebuilt_from"] == hashlib.sha256(
                    src.read_bytes()).hexdigest(), "inside_refused": inside}


def expected_rebuild():
    return {"ids": True, "items": True, "digest_new": True, "switches": (True, True), "loads": 2, "from": True,
            "inside_refused": "raised ValueError"}


def _bad(**change):
    value = _config(room_fate=True)
    value["advice"]["methods"][na.STEPWISE].update(change)
    return lambda: na.check_decoding(value)


def observe_refusals():
    block = na.load_config()["advice"]["methods"][na.STEPWISE]
    answers = block["room_fate_answers"]

    def changed(index, **field):
        out = copy.deepcopy(answers)
        out[index].update(field)
        return out
    t = block["room_fate_text"]
    return {"declared_ok": caught(lambda: na.room_fate_answers(block)),
            "shipped_off": (block["room_fate"], block["changes_id_echo"],
                            na.optional_switches(block)["room_fate"], na.optional_switches(block)["changes_id_echo"]),
            "room_not_bool": caught(_bad(room_fate="yes")),
            "echo_not_bool": caught(_bad(changes_id_echo=1)),
            "with_fate_forecast": caught(_bad(fate_forecast=True)),
            "one_stance_twice": caught(_bad(room_fate_answers=changed(2, stance="accept"))),
            "stance_label": caught(_bad(room_fate_answers=changed(2, label="reject"))),
            "upper_label": caught(_bad(room_fate_answers=changed(0, label="Kept"))),
            "two_answers": caught(_bad(room_fate_answers=answers[:2])),
            "no_alone": caught(_bad(room_fate_alone="")),
            "no_none": caught(_bad(room_fate_none=None)),
            "no_alternatives": caught(_bad(room_fate_text=t.replace("{alternatives}", "the others"))),
            "unnamed_label": caught(_bad(room_fate_text=t.replace("removed", "dropped"))),
            "shows_changes": caught(_bad(room_fate_text=t + "\n{changes}")),
            "off_same": noc._off_same(room_fate=False, changes_id_echo=False)}


def expected_refusals():
    raised = "raised ValueError"
    return {"declared_ok": (("kept", "changed", "removed"), {"kept": "accept", "changed": "counter",
                                                             "removed": "reject"}),
            "shipped_off": (False, False, False, False), "room_not_bool": raised, "echo_not_bool": raised,
            "with_fate_forecast": raised, "one_stance_twice": raised, "stance_label": raised, "upper_label": raised,
            "two_answers": raised, "no_alone": raised, "no_none": raised, "no_alternatives": raised,
            "unnamed_label": raised, "shows_changes": raised, "off_same": True}


# ---------------------------------------------------------------------------
# Round 3 (D-863, D-864; docs/loop/stages/NEG_ROUND3.md): a fourth room fate answer setting counter, and
# room_unanchored, which shows each touched position in {room} without its "read:" label.

OPEN_ANSWERS = [{"label": "kept", "stance": "accept"}, {"label": "changed", "stance": "counter"},
                {"label": "removed", "stance": "reject"}, {"label": "open", "stance": "counter"}]


def _r3_text(text):
    return text.replace("kept, changed, removed.", "kept, changed, removed, open.")


def _r3(**switches):
    t = _config()["advice"]["methods"][na.STEPWISE]["room_fate_text"]
    return _config(**dict({"room_fate": True, "room_fate_answers": OPEN_ANSWERS,
                           "room_fate_text": _r3_text(t)}, **switches))


def _room_users(asked):
    return {p: u for s, p, _q, u in asked if s == na.ROOM_FATE}


def observe_r2_unchanged():
    """room_unanchored declared false and not declared at all: the same questions, steps and reply (round 2)."""
    item = _item()
    off = _run(_config(room_fate=True, changes_id_echo=True, room_unanchored=False), item)
    bare_cfg = _config(room_fate=True, changes_id_echo=True)
    bare_cfg["advice"]["methods"][na.STEPWISE].pop("room_unanchored", None)
    bare = _run(bare_cfg, item)
    return {"same_reply": off[0] == bare[0], "same_steps": off[1] == bare[1],
            "same_users": [u for *_x, u in off[2]] == [u for *_x, u in bare[2]],
            "reads": sum(u.count("\n  read: ") for u in _room_users(off[2]).values()),
            "pieces": _summary(off[0])}


def expected_r2_unchanged():
    return {"same_reply": True, "same_steps": True, "same_users": True, "reads": 6, "pieces": ROOM_PIECES}


def observe_open_counter():
    """A fourth answer `open` setting counter: an open proposal is a counter, its wording asked; the others as declared."""
    fates = dict(FATES, **{"P-A1-1": "open"})
    out = {}
    for order in (na.CHOICE_FIRST, na.GENERATED_FIRST):
        reply, _s, asked = _run(_r3(order=order), fates=fates)
        out[order] = {"pieces": _summary(reply), "wording_for": [p for p, _q in _of(asked, "wording")],
                      "answered": {p: (e.get(na.ROOM_FATE) or {}).get("answered")
                                   for p, e in sorted(reply["proposals"].items())}}
    block = _r3()["advice"]["methods"][na.STEPWISE]
    out["declared"] = na.room_fate_answers(block)
    return out


def expected_open_counter():
    one = {"pieces": dict(ROOM_PIECES, **{"P-A1-1": ("no_conflict", "counter")}),
           "wording_for": ["P-A1-1", "P-A1-2"], "answered": dict(FATES, **{"P-A1-1": "open"})}
    return {na.CHOICE_FIRST: one, na.GENERATED_FIRST: one,
            "declared": (("kept", "changed", "removed", "open"),
                         {"kept": "accept", "changed": "counter", "removed": "reject", "open": "counter"})}


def observe_unanchored():
    """room_unanchored true: every touched position still shown, no "read:" label; the stances as answered."""
    item = _item()
    on = _run(_r3(room_unanchored=True), item)
    off = _run(_r3(room_unanchored=False), item)
    users_on, users_off = _room_users(on[2]), _room_users(off[2])
    quotes = [p["quote"] for p in item["positions"]]
    return {"reads_on": sum(u.count("read:") for u in users_on.values()),
            "reads_off": sum(u.count("read:") for u in users_off.values()),
            "same_positions": all((q in users_on[p]) == (q in users_off[p]) for p in users_on for q in quotes),
            "a1_1_lines": [line.strip()[:2] for line in users_on["P-A1-1"].split("\n")
                           if any(q in line for q in quotes)],
            "pieces": _summary(on[0]), "other_steps_same": [s for s in on[2] if s[0] != na.ROOM_FATE] ==
            [s for s in off[2] if s[0] != na.ROOM_FATE]}


def expected_unanchored():
    return {"reads_on": 0, "reads_off": 6, "same_positions": True, "a1_1_lines": ["- ", "- ", "- "],
            "pieces": ROOM_PIECES, "other_steps_same": True}


def observe_r3_refusals():
    def answers(*extra, drop=None):
        out = [dict(a) for a in OPEN_ANSWERS if a["label"] != drop]
        return out + [dict(e) for e in extra]

    def bad(**change):
        return caught(lambda: na.check_decoding(_r3(**change)))
    return {"four_ok": caught(lambda: na.check_decoding(_r3())) == _r3(),
            "duplicate_label": bad(room_fate_answers=answers({"label": "changed", "stance": "counter"}, drop="open")),
            "unknown_stance": bad(room_fate_answers=answers({"label": "open", "stance": "maybe"}, drop="open")),
            "no_stance": bad(room_fate_answers=answers({"label": "open"}, drop="open")),
            "fourth_accept": bad(room_fate_answers=answers({"label": "open", "stance": "accept"}, drop="open")),
            "fourth_reject": bad(room_fate_answers=answers({"label": "open", "stance": "reject"}, drop="open")),
            "fifth_counter": bad(room_fate_answers=answers({"label": "moved", "stance": "counter"})),
            "open_unnamed": bad(room_fate_text=_config()["advice"]["methods"][na.STEPWISE]["room_fate_text"]),
            "unanchored_not_bool": bad(room_unanchored="true"),
            "unanchored_without_room": caught(lambda: na.check_decoding(_config(room_unanchored=True))),
            "shipped_unanchored": na.optional_switches(na.load_config()["advice"]["methods"][na.STEPWISE])[
                "room_unanchored"]}


def expected_r3_refusals():
    raised = "raised ValueError"
    return {"four_ok": True, "duplicate_label": raised, "unknown_stance": raised, "no_stance": raised,
            "fourth_accept": raised, "fourth_reject": raised, "fifth_counter": raised, "open_unnamed": raised,
            "unanchored_not_bool": raised, "unanchored_without_room": raised, "shipped_unanchored": False}


PROOFS = ("blind_open_point", "room_fate", "both_orders", "refused_fate", "id_echo", "replay", "rebuild", "refusals",
          "r2_unchanged", "open_counter", "unanchored", "r3_refusals")
NEUTRALISATIONS = {
    # The room answer's stance no longer used: every answered proposal reads accept.
    "room": ((na, "stepwise_advice", "return sets[got]", 'return "accept"'),
             ("room_fate", "both_orders", "refused_fate", "replay")),
    # The shown id no longer taken off a changes line.
    "echo": ((na, "_step_check", 'said = said[len(proposal["id"]) + 1:].strip()', "pass"), ("id_echo",)),
    # Round 3: the fourth answer setting counter refused again (the loader back to one answer per stance).
    "open": ((na, "room_fate_answers", "allowed = (sorted(STANCES), sorted(STANCES + (ROOM_FATE_SHARED,)))",
              "allowed = (sorted(STANCES),)"), ("open_counter", "unanchored", "r3_refusals")),
    # Round 3: an answer setting no declared stance no longer refused.
    "strict": ((na, "room_fate_answers", "or any(s not in STANCES for s in set_by):", "or False:"), ("r3_refusals",)),
    # Round 3: two answers with one label no longer refused.
    "unique": ((na, "room_fate_answers", "if len(set(labels)) != len(labels) or any(", "if any("), ("r3_refusals",)),
    # Round 3: the read labels shown although room_unanchored is true.
    "unanchored": ((na, "stepwise_advice", 'read.append(line if opt["room_unanchored"] else',
                    'read.append(line if False else'), ("unanchored",)),
    # Round 3: the read labels dropped although room_unanchored is false (round 2 changed).
    "anchored_off": ((na, "stepwise_advice", 'read.append(line if opt["room_unanchored"] else',
                      'read.append(line if True else'), ("r2_unchanged", "room_fate")),
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
    return "PASS", ("%d proofs, %d neutralisations, fail, restore, pass, no model: R3 room fate; the C4 chain's blind "
                    "open point makes every proposal a counter, a conflict included; with room_fate the open point "
                    "is not asked, the room fate shows the other proposals and each touched position's label, and "
                    "kept, changed, removed set accept, counter, reject under both orders, the conflict unchanged; a "
                    "refused fate leaves no stance; R3b reads a changes line without the shown id, a wrong id or a "
                    "paraphrase refused; replayed the same; rebuilt prompts keep ids and items; refusals held; off "
                    "unchanged; round 3: an open answer sets counter, room_unanchored drops the read labels, round 2 "
                    "asks the same with it off, duplicate or undeclared answers refused (%s)"
                    % (len(PROOFS), len(NEUTRALISATIONS), ", ".join(PROOFS)))


if __name__ == "__main__":
    status, detail = run()
    print("686", status, detail)
