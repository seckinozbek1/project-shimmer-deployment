#!/usr/bin/env python3
"""Check 651 (lane/neg-conflict-fix, D-806; docs/loop/stages/NEG_CONFLICT_FIX_REPORT.md): C4, the conflict question
`compare` of benchmark/baselines/neg_advisor.py, behind `advice.methods.stepwise.conflict_question` in
benchmark/baselines/neg_advisor_prompt.json (`stance` as shipped).

The saved replies of the M-step and improved runs show the stance step never answering oppose (0 of 1,453), and no
item declaring a persona red line, so the chain never composed a conflict and reject-on-conflict never fired. The
proofs, on the invented fixture item of tools/neg_advisor_checks.py with a scripted model (no model, no key, no real
item, nothing launched):

1. cascade: the shipped stance question, a model that never answers oppose and no red line declared (the runs'
   shape) gives no conflict and no reject on any proposal, though the persona holds an opposing position.
2. oppose-shaped: under `compare`, the persona's position answered `against` makes its proposal a conflict and the
   stance reject; the compare question is asked of every touched position in place of the stance question, over
   the declared answers, both rounds and the quote shown, the margin toward `against` kept.
3. neutral: under `compare`, every position answered `aside` (or `fits`) gives no conflict anywhere.
4. replay: the same reply composed again from saved step records by neg_advisor.recompose_stepwise (the reader the
   scorer's answers path uses), no model.
5. refusals: the trimmed arm, conditional_accept, two answers counting as oppose, a label that is a declared stance,
   a template that does not name a label, each refused; the switch off (or not declared) asks and composes exactly
   as before.

Run as built (passes), neutralised (the compare answer no longer counted as its declared stance: must fail),
restored and run again (passes).
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

caught, with_source = noc.caught, noc.with_source
ANSWERS = ("against", "fits", "aside")


def _item(red_lines=True):
    item = noc._item()
    if not red_lines:
        item["persona"]["red_lines"] = []
        item["persona"].pop("red_line_sources", None)
    return item


def _ask(item, script, asked):
    """A scripted model: `script(step, position)` gives the label of a choice step; the scripted probabilities put
    0.9 on it. Generated steps copy the proposal (changes) or write a fixed wording."""

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


def _never_oppose(step, pos):
    # The runs' shape: the stance step's top answer is accept or support, never oppose; every yes/no is no.
    if step == "stance":
        return "support" if noc.STANCE_OF[pos["id"]] == "support" else "accept"
    return "no"


def _oppose_shaped(step, pos):
    # A position the fixture build maps as oppose is answered against; the others fits; every yes/no is no.
    if step == "compare":
        return "against" if noc.STANCE_OF[pos["id"]] == "oppose" else "fits"
    return "no"


def _neutral(step, pos):
    return "aside" if step == "compare" else "no"


def _run(config, item, script):
    asked = []
    reply, steps = na.stepwise_advice(config, item, _ask(item, script, asked))
    return reply, steps, asked


def _summary(reply):
    return {pid: (e.get("conflict"), e.get("stance")) for pid, e in sorted(reply["proposals"].items())}


def observe_cascade():
    reply, _s, asked = _run(noc._config(), _item(red_lines=False), _never_oppose)
    return {"pieces": _summary(reply), "red_line_asked": [s for s, *_ in asked].count("red_line"),
            "conflicts": sum(1 for e in reply["proposals"].values() if e.get("conflict") == "conflict")}


def expected_cascade():
    return {"pieces": {"P-A1-1": ("no_conflict", "accept"), "P-A1-2": ("not_stated", "accept"),
                       "P-A2-1": ("no_conflict", "accept")}, "red_line_asked": 0, "conflicts": 0}


def _compare_config():
    return noc._config(conflict_question=na.COMPARE)


def observe_oppose_shaped():
    item = _item(red_lines=False)
    reply, _s, asked = _run(_compare_config(), item, _oppose_shaped)
    compare = [(p, a) for s, p, a, _u in asked if s == "compare"]
    shown = next(u for s, p, _a, u in asked if s == "compare" and p == "POS-2")
    kept = reply["proposals"]["P-A2-1"]["position_stances"]["POS-2"]
    return {"pieces": _summary(reply), "stance_asked": [s for s, *_ in asked].count("stance"),
            "compare_asked": sorted(p for p, _a in compare), "offered": sorted({a for _p, a in compare}),
            "rounds_shown": ("(Finance), round 2:" in shown, "on record in round 2:" in shown, "We cannot accept mandatory" in shown),
            "pos2": (kept["stance"], kept["answered"], round(kept["oppose_margin"], 6)),
            "pos1": (lambda v: (v["stance"], v["answered"], round(v["oppose_margin"], 6)))(
                reply["proposals"]["P-A1-1"]["position_stances"]["POS-1"])}


def expected_oppose_shaped():
    m = round(0.9 - 0.05, 6)
    return {"pieces": {"P-A1-1": ("no_conflict", "accept"), "P-A1-2": ("not_stated", "accept"),
                       "P-A2-1": ("conflict", "reject")},
            "stance_asked": 0, "compare_asked": ["POS-1", "POS-2", "POS-3", "POS-4", "POS-5", "POS-6"],
            "offered": [ANSWERS], "rounds_shown": (True, True, True),
            "pos2": ("oppose", "against", m), "pos1": ("support", "fits", round(0.05 - 0.9, 6))}


def observe_neutral():
    reply, _s, _a = _run(_compare_config(), _item(red_lines=False), _neutral)
    stances = sorted({v["stance"] for e in reply["proposals"].values() for v in (e.get("position_stances") or {}).values()})
    return {"pieces": _summary(reply), "stances": stances}


def expected_neutral():
    return {"pieces": {"P-A1-1": ("no_conflict", "accept"), "P-A1-2": ("not_stated", "accept"),
                       "P-A2-1": ("no_conflict", "accept")}, "stances": ["accept"]}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def observe_replay():
    """The chain's steps saved as reply records (a choice step's decision, a generated step's text), then composed
    again by recompose_stepwise with no model: the same reply."""
    config, item = _compare_config(), _item(red_lines=False)
    rows, records, asked = [], {}, []
    inner = _ask(item, _oppose_shaped, asked)

    def ask(step, user, answers):
        said = inner(step, user, answers)
        call = "c%03d" % (len(rows) + 1)
        rows.append({"step": step, "user_sha256": _sha(user), "call_id": call})
        if answers:
            label, probs = said
            records[call] = {"backend_ok": True, "decision": {"answers": [{"label": a, "probability": probs[a]}
                                                                           for a in answers]}}
        else:
            records[call] = {"backend_ok": True, "reply": {"text": said}}
        return said

    live, _steps = na.stepwise_advice(config, item, ask)
    prompt = {"prompt_id": "a-fx", "item": item}
    again, _s2 = na.recompose_stepwise(config, prompt, rows, records)
    return {"same": again == live, "pieces": _summary(again)}


def expected_replay():
    return {"same": True, "pieces": expected_oppose_shaped()["pieces"]}


def _bad(**change):
    value = _compare_config()
    value["advice"]["methods"][na.STEPWISE].update(change)
    return lambda: na.check_decoding(value)


def observe_refusals():
    item = _item()
    answers = [{"label": "against", "counts_as": "oppose"}, {"label": "fits", "counts_as": "support"},
               {"label": "aside", "counts_as": "accept"}]
    two = copy.deepcopy(answers)
    two[2]["counts_as"] = "oppose"
    stance_label = copy.deepcopy(answers)
    stance_label[1]["label"] = "support"
    block = na.load_config()["advice"]["methods"][na.STEPWISE]
    unnamed = block["compare"].replace("aside", "untouched")
    return {"declared_ok": caught(lambda: na.compare_answers(_compare_config()["advice"]["methods"][na.STEPWISE])),
            "trimmed": caught(lambda: na.stepwise_advice(_compare_config(), item, _ask(item, _neutral, []),
                                                         stance_context=na.TRIMMED_CONTEXT)),
            "conditional": caught(_bad(conditional_accept={"label": "conditional", "counts_as": "accept"})),
            "two_oppose": caught(_bad(compare_answers=two)),
            "stance_label": caught(_bad(compare_answers=stance_label)),
            "unnamed_label": caught(_bad(compare=unnamed)),
            "off_same": noc._off_same(conflict_question=na.STANCE_QUESTION)}


def expected_refusals():
    return {"declared_ok": (ANSWERS, {"against": "oppose", "fits": "support", "aside": "accept"}, "against"),
            "trimmed": "raised ValueError", "conditional": "raised ValueError", "two_oppose": "raised ValueError",
            "stance_label": "raised ValueError", "unnamed_label": "raised ValueError", "off_same": True}


PROOFS = ("cascade", "oppose_shaped", "neutral", "replay", "refusals")
NEUTRALISED = ("oppose_shaped", "replay")


def neutralise():
    """The compare answer no longer counted as its declared stance: every answer read as accept."""
    return with_source(na, "stepwise_advice", "return counts_as[got], None, {", 'return "accept", None, {')


def run():
    space = globals()
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            first = {n: space["observe_" + n]() for n in PROOFS}
            with neutralise():
                broken = {n: caught(space["observe_" + n]) for n in NEUTRALISED}
            again = {n: space["observe_" + n]() for n in PROOFS}
    except Exception as exc:
        return "FAIL", "%s %s" % (type(exc).__name__, str(exc)[:300])
    expected = {n: space["expected_" + n]() for n in PROOFS}
    for n in PROOFS:
        if first[n] != expected[n]:
            return "FAIL", "%s as built: %s" % (n, str(first[n])[:900])
        if again[n] != expected[n]:
            return "FAIL", "%s after restore: %s" % (n, str(again[n])[:400])
    for n in NEUTRALISED:
        if broken[n] == expected[n]:
            return "FAIL", "%s still passes when neutralised" % n
    return "PASS", ("%d proofs, neutralise, fail, restore, pass, no model: C4 compare; the runs' shape gives no "
                    "conflict (cascade); an against answer on the persona's position gives conflict and reject, "
                    "a neutral one none; replayed from saved records the same; refusals held; off unchanged (%s)"
                    % (len(PROOFS), ", ".join(PROOFS)))


if __name__ == "__main__":
    status, detail = run()
    print("651", status, detail)
