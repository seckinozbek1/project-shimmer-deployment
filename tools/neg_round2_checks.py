#!/usr/bin/env python3
"""Check 652 (lane/neg-round2-candidate, D-814 round 2; docs/loop/stages/NEG_ROUND2_CANDIDATE.md): R2, the limit
read of benchmark/baselines/neg_advisor.py, behind `advice.methods.stepwise.limit_read` in
benchmark/baselines/neg_advisor_prompt.json (false as shipped).

The chain's second route to a conflict, a crossed red line, is asked only of positions the build marks red lines;
no pilot item marks one, so in the saved step records it was never asked and conflict had one route, the stance
step (C4 changes that step's question; R2 adds the second route beside it). The proofs, on the invented fixture
item of tools/neg_advisor_checks.py with a scripted model (no model, no key, no real item, nothing launched):

1. cascade_closed: the shipped stance question, a model that never answers oppose, no red line marked (the runs'
   shape), limit_read on: the persona's positions are read once each before any proposal, the read showing no
   proposal; the one read as a limit is asked limit_cross on its proposal, and a yes makes it conflict and reject,
   marked limit_hit and limit_basis inferred, apart from red_line_hit.
2. no_crossing: a limit the proposal does not cross, and positions all read as wishes, give no conflict; a wish is
   never asked limit_cross.
3. declared_kept: a marked red line is asked by the declared red_line step as before and never read again.
4. with_c4: composed with conflict_question compare (C4) under both orders: a conflict through either route, the
   compare question still asked of every touched position.
5. refused_read: an undeclared answer to the read is refused and counted, the position is no limit, the chain goes on.
6. replay: the same reply composed again from saved step records by neg_advisor.recompose_stepwise, no model.
7. p3_holds: tools/score_neg_advisor.margin_conflict_reply (P3) keeps a crossed limit's conflict at any threshold.
8. refusals: a non-boolean switch, two or no limit answers, a label that is yes, no or a stance, an upper-case label,
   a read template showing a proposal or missing a slot or a label, a crossing template missing the quote or
   showing {changes}, each refused; the switch off (or not declared) asks and composes exactly as before.

Run as built (passes), neutralised twice (the crossing not counted as a conflict in the chain; P3 not reading
limit_hit), each must fail, restored and run again (passes).
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
import score_neg_advisor as sna  # noqa: E402

caught, with_source = noc.caught, noc.with_source
LIMITS = ("firm", "wish")
BASE_PIECES = {"P-A1-1": ("no_conflict", "accept"), "P-A1-2": ("not_stated", "accept"),
               "P-A2-1": ("no_conflict", "accept")}


def _item(red_lines=False):
    item = noc._item()
    if not red_lines:
        item["persona"]["red_lines"] = []
        item["persona"].pop("red_line_sources", None)
    return item


def _config(**switches):
    return noc._config(**dict({"limit_read": True}, **switches))


def _script(read=None, cross="yes", compare=None):
    """A scripted model: the stance step never answers oppose (the runs' shape); the read answers `read[position]`
    (wish when not named); limit_cross answers `cross`; compare answers `compare(position)`; any other yes/no no."""
    read = dict(read or {})

    def script(step, pos):
        if step == "stance":
            return "support" if noc.STANCE_OF[pos["id"]] == "support" else "accept"
        if step == na.LIMIT_READ:
            return read.get(pos["id"], "wish")
        if step == na.LIMIT_CROSS:
            return cross
        if step == "compare":
            return compare(pos) if compare else "aside"
        return "no"
    return script


def _ask(item, script, asked):
    def ask(step, user, answers):
        pos = next((p for p in item["positions"] if p["quote"] in user), None)
        asked.append((step, pos["id"] if pos else None, tuple(answers) if answers else None, user))
        if not answers:
            if step == "changes":
                return next(p["text"] for a in item["articles"] for p in a["proposals"] if p["text"] in user)
            return "A middle ground wording for the fixture"
        label = script(step, pos)
        return label, noc._probs(answers, label)
    return ask


def _run(config, item, script):
    asked = []
    reply, steps = na.stepwise_advice(config, item, _ask(item, script, asked))
    return reply, steps, asked


def _summary(reply):
    return {pid: (e.get("conflict"), e.get("stance")) for pid, e in sorted(reply["proposals"].items())}


def _asked(asked, step):
    return [p for s, p, _a, _u in asked if s == step]


def _limit_fields(reply):
    return {pid: tuple(e.get(k) for k in ("limit_hit", "limit_lines", "limit_basis", "red_line_hit"))
            for pid, e in sorted(reply["proposals"].items()) if "limit_hit" in e or "red_line_hit" in e}


def observe_cascade_closed():
    item = _item()
    reply, _s, asked = _run(_config(), item, _script(read={"POS-2": "firm"}))
    texts = [p["text"] for a in item["articles"] for p in a["proposals"]]
    reads = [u for s, _p, _a, u in asked if s == na.LIMIT_READ]
    return {"pieces": _summary(reply), "read": _asked(asked, na.LIMIT_READ),
            "read_first": [s for s, *_ in asked][:2], "read_offered": sorted({a for s, _p, a, _u in asked
                                                                             if s == na.LIMIT_READ}),
            "read_shows_proposal": any(t in u for t in texts for u in reads),
            "cross": _asked(asked, na.LIMIT_CROSS), "red_line": _asked(asked, "red_line"),
            "fields": _limit_fields(reply),
            "reads": {k: (v["answered"], v["limit"], v["basis"]) for k, v in sorted(reply["limit_reads"].items())}}


def expected_cascade_closed():
    return {"pieces": dict(BASE_PIECES, **{"P-A2-1": ("conflict", "reject")}), "read": ["POS-1", "POS-2"],
            "read_first": [na.LIMIT_READ, na.LIMIT_READ], "read_offered": [LIMITS], "read_shows_proposal": False,
            "cross": ["POS-2"], "red_line": [], "fields": {"P-A2-1": (True, ["POS-2"], na.INFERRED, None)},
            "reads": {"POS-1": ("wish", False, na.INFERRED), "POS-2": ("firm", True, na.INFERRED)}}


def observe_no_crossing():
    a, _s, asked_a = _run(_config(), _item(), _script(read={"POS-1": "firm", "POS-2": "firm"}, cross="no"))
    b, _s, asked_b = _run(_config(), _item(), _script())
    return {"not_crossed": _summary(a), "not_crossed_fields": _limit_fields(a), "cross_asked": _asked(asked_a, na.LIMIT_CROSS),
            "wishes": _summary(b), "wishes_cross_asked": _asked(asked_b, na.LIMIT_CROSS)}


def expected_no_crossing():
    return {"not_crossed": BASE_PIECES,
            "not_crossed_fields": {"P-A1-1": (False, [], na.INFERRED, None), "P-A2-1": (False, [], na.INFERRED, None)},
            "cross_asked": ["POS-1", "POS-2"], "wishes": BASE_PIECES, "wishes_cross_asked": []}


def observe_declared_kept():
    item = _item(red_lines=True)

    def script(step, pos):
        return "yes" if step == "red_line" else _script(read={"POS-1": "firm", "POS-2": "firm"}, cross="no")(step, pos)
    reply, _s, asked = _run(_config(), item, script)
    return {"pieces": _summary(reply), "read": _asked(asked, na.LIMIT_READ), "red_line": _asked(asked, "red_line"),
            "cross": _asked(asked, na.LIMIT_CROSS), "fields": _limit_fields(reply)}


def expected_declared_kept():
    return {"pieces": dict(BASE_PIECES, **{"P-A2-1": ("conflict", "reject")}), "read": ["POS-1"],
            "red_line": ["POS-2"], "cross": ["POS-1"],
            "fields": {"P-A1-1": (False, [], na.INFERRED, None), "P-A2-1": (None, None, None, True)}}


def _against(pos):
    return "against" if noc.STANCE_OF[pos["id"]] == "oppose" else "fits"


def observe_with_c4():
    out = {}
    for order in (na.GENERATED_FIRST, na.CHOICE_FIRST):
        config = _config(conflict_question=na.COMPARE, order=order)
        limit, _s, asked = _run(config, _item(), _script(read={"POS-2": "firm"}))
        compare, _s2, asked2 = _run(config, _item(), _script(compare=_against))
        out[order] = {"limit_route": _summary(limit), "compare_asked": len(_asked(asked, "compare")),
                      "stance_asked": len(_asked(asked, "stance")), "compare_route": _summary(compare),
                      "compare_route_cross": _asked(asked2, na.LIMIT_CROSS)}
    return out


def expected_with_c4():
    one = {"limit_route": dict(BASE_PIECES, **{"P-A2-1": ("conflict", "reject")}), "compare_asked": 6,
           "stance_asked": 0, "compare_route": dict(BASE_PIECES, **{"P-A2-1": ("conflict", "reject")}),
           "compare_route_cross": []}
    return {na.GENERATED_FIRST: one, na.CHOICE_FIRST: one}


def observe_refused_read():
    reply, steps, asked = _run(_config(), _item(), _script(read={"POS-2": "maybe"}))
    return {"pieces": _summary(reply), "refused": [(s["step"], s.get("position"), s["refused"]) for s in steps
                                                   if s["refused"]],
            "pos2": (reply["limit_reads"]["POS-2"]["answered"], reply["limit_reads"]["POS-2"]["limit"]),
            "cross": _asked(asked, na.LIMIT_CROSS), "open_points": len(_asked(asked, "open_point"))}


def expected_refused_read():
    return {"pieces": BASE_PIECES, "refused": [(na.LIMIT_READ, "POS-2", "not_declared")], "pos2": (None, False),
            "cross": [], "open_points": 3}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def observe_replay():
    """The chain's steps saved as reply records (a choice step's decision, a generated step's text), then composed
    again by recompose_stepwise with no model: the same reply, under R2 and C4 together."""
    config, item = _config(conflict_question=na.COMPARE), _item()
    rows, records, asked = [], {}, []
    inner = _ask(item, _script(read={"POS-2": "firm"}), asked)

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
    return {"same": again == live, "pieces": _summary(again), "reads": sorted(again.get("limit_reads") or {})}


def expected_replay():
    return {"same": True, "pieces": dict(BASE_PIECES, **{"P-A2-1": ("conflict", "reject")}),
            "reads": ["POS-1", "POS-2"]}


def observe_p3_holds():
    item = _item()
    reply, _s, _a = _run(_config(), item, _script(read={"POS-2": "firm"}))
    out, counts = sna.margin_conflict_reply(item, reply, 0.5)
    return {"pieces": _summary(out), "counts": dict(sorted(counts.items()))}


def expected_p3_holds():
    return {"pieces": dict(BASE_PIECES, **{"P-A2-1": ("conflict", "reject")}), "counts": {"decided": 2}}


def _bad(**change):
    value = _config()
    value["advice"]["methods"][na.STEPWISE].update(change)
    return lambda: na.check_decoding(value)


def observe_refusals():
    answers = [{"label": "firm", "limit": True}, {"label": "wish", "limit": False}]

    def changed(index, **field):
        out = copy.deepcopy(answers)
        out[index].update(field)
        return out
    block = na.load_config()["advice"]["methods"][na.STEPWISE]
    return {"declared_ok": caught(lambda: na.limit_answers(_config()["advice"]["methods"][na.STEPWISE])),
            "shipped_off": (block["limit_read"], na.optional_switches(block)["limit_read"]),
            "not_bool": caught(_bad(limit_read="yes")),
            "two_limits": caught(_bad(limit_answers=changed(1, limit=True))),
            "no_limit": caught(_bad(limit_answers=changed(0, limit=False))),
            "limit_not_bool": caught(_bad(limit_answers=changed(0, limit="true"))),
            "label_yes": caught(_bad(limit_answers=changed(1, label="no"))),
            "label_stance": caught(_bad(limit_answers=changed(1, label="accept"))),
            "label_upper": caught(_bad(limit_answers=changed(1, label="Wish"))),
            "one_answer": caught(_bad(limit_answers=answers[:1])),
            "read_shows_proposal": caught(_bad(limit=block["limit"] + "\n{proposal}")),
            "read_no_round": caught(_bad(limit=block["limit"].replace("{position_round}", "an earlier round"))),
            "read_unnamed_label": caught(_bad(limit=block["limit"].replace("wish", "hope"))),
            "cross_no_quote": caught(_bad(limit_cross=block["limit_cross"].replace("{quote}", "the line"))),
            "cross_changes": caught(_bad(limit_cross=block["limit_cross"] + "\n{changes}")),
            "off_same": noc._off_same(limit_read=False)}


def expected_refusals():
    raised = "raised ValueError"
    return {"declared_ok": (LIMITS, {"firm": True, "wish": False}), "shipped_off": (False, False),
            "not_bool": raised, "two_limits": raised, "no_limit": raised, "limit_not_bool": raised,
            "label_yes": raised, "label_stance": raised, "label_upper": raised, "one_answer": raised,
            "read_shows_proposal": raised, "read_no_round": raised, "read_unnamed_label": raised,
            "cross_no_quote": raised, "cross_changes": raised, "off_same": True}


PROOFS = ("cascade_closed", "no_crossing", "declared_kept", "with_c4", "refused_read", "replay", "p3_holds",
          "refusals")
NEUTRALISATIONS = {
    # The crossing no longer counted as a conflict in the chain.
    "chain": ((na, "stepwise_advice", '"conflict" if hit or crossed or \\', '"conflict" if hit or \\'),
              ("cascade_closed", "with_c4", "replay")),
    # P3 no longer reading limit_hit.
    "p3": ((sna, "margin_conflict_reply", 'piece.get("red_line_hit") or piece.get("limit_hit") or',
            'piece.get("red_line_hit") or'), ("p3_holds",)),
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
    return "PASS", ("%d proofs, %d neutralisations, fail, restore, pass, no model: R2 limit read; with no red line "
                    "marked and a stance step that never says oppose, a read limit the proposal crosses gives "
                    "conflict and reject, marked inferred; no crossing and wishes give none; a marked red line is "
                    "kept and never read; composes with C4 under both orders; a refused read is no limit; replayed "
                    "the same; P3 keeps the crossing; refusals held; off unchanged (%s)"
                    % (len(PROOFS), len(NEUTRALISATIONS), ", ".join(PROOFS)))


if __name__ == "__main__":
    status, detail = run()
    print("652", status, detail)
