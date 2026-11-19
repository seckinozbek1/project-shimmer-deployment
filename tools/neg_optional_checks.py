#!/usr/bin/env python3
"""Checks 539 to 543 (lane/neg-optional, Seckin 19 November 2026 01:23): the optional negotiation ideas of D-756,
each behind its own switch in `advice.methods.stepwise` of benchmark/baselines/neg_advisor_prompt.json, off as
shipped (neg_advisor.optional_switches).

539, P2 `fate_forecast`: one fate choice per proposal after its stance, marked inferred, under one declared
    precedence rule (stance kept, or the stance set from the fate), the conflict field never written by it.
540, C2 `conflict_question: two_checks`: each position's stance asked as two yes/no checks, oppose by yes then no,
    the oppose margin the smaller of the two.
541, P6 `quote_grounding`: an oppose grounded by choosing one of the position's own sentences by number, 0 sending
    it back, a refused choice kept ungrounded and counted, never ending the chain.
542, P5 `auditor_band`: a persona position inside the declared margin band, grounded by a chosen sentence, asked
    of the second family through the derived audit prompts; its `supported` alone flips the proposal.
543, C3 `conditional_accept`: a fourth stance answer counted as its declared stance (D-748), marked on the piece.

Each proof also shows that the switch off (or not declared at all) leaves the chain's questions and reply as
they were. No model, no key, no real item, nothing launched: a scripted `ask` on the invented fixture item of
tools/neg_advisor_checks.py. Every proof is run as built (passes), neutralised (must fail), restored and run
again (passes).
"""
from __future__ import annotations

import contextlib
import copy
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools"),
           str(ROOT / "benchmark" / "adapters")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_advisor as na  # noqa: E402
import neg_advisor_checks as nb  # noqa: E402
import reasoning_methods_checks as rmc  # noqa: E402
import reread_replies as rr  # noqa: E402

caught, with_source = rmc.caught, rmc.with_source
NEW_KEYS = tuple(na.OPTIONAL_DEFAULTS)
STANCE_OF = {p["id"]: p["stance"] for p in nb.BUILD["positions"]}


def _item():
    with nb.setdir() as root:
        return copy.deepcopy(na.read_items(root)[nb.BUILD["item_id"]])


def _config(bare=False, **switches):
    value = copy.deepcopy(na.load_config())
    for g in value["models"]:
        if g["group"] == "system_advice":
            g["method"] = na.STEPWISE
    block = value["advice"]["methods"][na.STEPWISE]
    if bare:
        for k in NEW_KEYS:
            block.pop(k, None)
    block.update(switches)
    return na.check_decoding(value)


def _probs(answers, label):
    return {a: 0.9 if a == label else 0.1 / (len(answers) - 1) for a in answers}


def chain(config, item, script=None, probs=None, stance_context=None):
    """The fixture item's stepwise advice under `config`, every answer scripted: (reply, steps, asked), `asked`
    the (step, position id, answers offered) of each question in order."""
    script, probs, asked = dict(script or {}), dict(probs or {}), []

    def ask(step, user, answers):
        pos = next((p for p in item["positions"] if p["quote"] in user), None)
        key = (step, pos["id"] if pos else None)
        asked.append((step, key[1], tuple(answers) if answers else None))
        if not answers:
            if step == "changes":
                return next(p["text"] for a in item["articles"] for p in a["proposals"] if p["text"] in user)
            return "A middle ground wording for the fixture"
        if key in script:
            label = script[key]
        elif step in script:
            label = script[step]
        elif step == "stance":
            label = STANCE_OF[pos["id"]]
        elif step == "touches":
            label = "yes"
        elif step == "holds":
            label = "no" if STANCE_OF[pos["id"]] == "oppose" else "yes"
        elif step == "quote":
            label = "1"
        else:
            label = "no"
        p = probs.get(key) or (_probs(answers, label) if label in answers else _probs(answers, answers[0]))
        return label, p

    reply, steps = na.stepwise_advice(config, item, ask, stance_context=stance_context)
    return reply, steps, asked


def _view(reply, *keys):
    return {pid: tuple(e.get(k) for k in ("conflict", "stance") + keys) for pid, e in sorted(reply["proposals"].items())}


def _off_same(**off):
    """The switch declared off, and not declared at all: the same questions and the same reply."""
    item = _item()
    a, b = chain(_config(**off), item), chain(_config(bare=True), item)
    return a[0] == b[0] and a[2] == b[2] and [s for s in a[1]] == [s for s in b[1]]


BASE = {"P-A1-1": ("no_conflict", "accept"), "P-A1-2": ("not_stated", "accept"), "P-A2-1": ("conflict", "reject")}


# ---------------------------------------------------------------------------
# 539 P2 fate forecast


def observe_fate_forecast():
    item = _item()
    kept, _s, asked = chain(_config(fate_forecast=True, fate_precedence="stance"), item, {"fate": "removed"})
    by_fate, _s2, _a2 = chain(_config(fate_forecast=True, fate_precedence="fate"), item, {"fate": "kept"})
    bad = _config()
    bad["advice"]["methods"][na.STEPWISE].update(fate_forecast=True, fate_precedence=None)
    return {"stance_rule": _view(kept, "fate", "fate_basis"),
            "fate_asked": [s for s, _p, _a in asked].count("fate"),
            "fate_answers": sorted({a for s, _p, a in asked if s == "fate"}),
            "fate_rule": _view(by_fate, "fate", "stance_from_fate"),
            "off_same": _off_same(fate_forecast=False),
            "no_precedence": caught(lambda: na.check_decoding(bad))}


def expected_fate_forecast():
    # The fate never writes the conflict field: under the fate rule P-A2-1 stays a conflict, its stance accept.
    return {"stance_rule": {k: v + ("removed", "inferred") for k, v in BASE.items()},
            "fate_asked": 3, "fate_answers": [("kept", "changed", "removed")],
            "fate_rule": {"P-A1-1": ("no_conflict", "accept", "kept", None),
                          "P-A1-2": ("not_stated", "accept", "kept", None),
                          "P-A2-1": ("conflict", "accept", "kept", {"was": "reject"})},
            "off_same": True, "no_precedence": "raised ValueError"}


def neutralise_fate_forecast():
    return with_source(na, "stepwise_advice", 'if block["fate_precedence"] == "fate":', 'if False:')


# ---------------------------------------------------------------------------
# 540 C2 two yes/no checks


def observe_two_checks():
    item = _item()
    reply, _s, asked = chain(_config(conflict_question=na.TWO_CHECKS), item)
    stances = {pid: {k: (v["stance"], v["checks"]["touches"], v["checks"]["holds"], round(v["oppose_margin"], 6))
                     for k, v in sorted(e.get("position_stances", {}).items())}
               for pid, e in sorted(reply["proposals"].items()) if e.get("position_stances")}
    both = _config()
    both["advice"]["methods"][na.STEPWISE].update(conflict_question=na.TWO_CHECKS,
                                                   conditional_accept={"label": "conditional", "counts_as": "accept"})
    return {"pieces": _view(reply), "asked": sorted({s for s, _p, _a in asked}),
            "stance_asked": sum(1 for s, _p, _a in asked if s == "stance"), "stances": stances,
            "off_same": _off_same(conflict_question=na.STANCE_QUESTION),
            "with_conditional": caught(lambda: na.check_decoding(both))}


def expected_two_checks():
    m = round(0.9 - 0.1, 6)
    return {"pieces": BASE, "asked": ["changes", "holds", "open_point", "red_line", "touches"], "stance_asked": 0,
            "stances": {"P-A1-1": {"POS-1": ("accept", "yes", "yes", -m), "POS-3": ("accept", "yes", "yes", -m),
                                   "POS-5": ("oppose", "yes", "no", m)},
                        "P-A2-1": {"POS-2": ("oppose", "yes", "no", m), "POS-4": ("oppose", "yes", "no", m),
                                   "POS-6": ("accept", "yes", "yes", -m)}},
            "off_same": True, "with_conditional": "raised ValueError"}


def neutralise_two_checks():
    return with_source(na, "stepwise_advice", '("yes", "no") else block["two_checks_otherwise"]',
                       '("yes", "yes") else block["two_checks_otherwise"]')


# ---------------------------------------------------------------------------
# 541 P6 quote grounding


def _quotes(reply):
    return {k: (v["stance"], v.get("quote"), v.get("sent_back", False))
            for e in reply["proposals"].values() for k, v in sorted((e.get("position_stances") or {}).items())
            if "quote" in v}


def observe_quote_grounding():
    item = _item()
    on = _config(quote_grounding=True)
    grounded, _s, asked = chain(on, item, {("quote", "POS-4"): "0"})
    sent_back, _s2, _a2 = chain(on, item, {("quote", "POS-2"): "0"})
    refused, steps, asked3 = chain(on, item, {("quote", "POS-5"): "7"})
    return {"grounded": _quotes(grounded), "pieces": _view(grounded),
            "offered": sorted({a for s, _p, a in asked if s == "quote"}),
            "persona_sent_back": (_view(sent_back)["P-A2-1"], _quotes(sent_back)["POS-2"]),
            "refused": (_quotes(refused)["POS-5"], [s["refused"] for s in steps if s["step"] == "quote"],
                        [s for s, _p, _a in asked3].count("open_point")),
            "sentences": na.position_sentences("We cannot accept this. It is too costly for us."),
            "off_same": _off_same(quote_grounding=False)}


def expected_quote_grounding():
    s2, s5 = "We cannot accept mandatory contributions.", "A fixed time is not workable for us."
    return {"grounded": {"POS-2": ("oppose", {"chosen": 1, "sentence": s2}, False),
                         "POS-4": ("accept", {"chosen": 0}, True),
                         "POS-5": ("oppose", {"chosen": 1, "sentence": s5}, False)},
            "pieces": BASE, "offered": [("0", "1")],
            # The persona's only oppose sent back: no conflict from it (the red line answered no).
            "persona_sent_back": (("no_conflict", "accept"), ("accept", {"chosen": 0}, True)),
            # A refused choice keeps the oppose ungrounded and the chain goes on to every open point.
            "refused": (("oppose", {"chosen": None, "reason": "refused"}, False), ["not_declared", None, None], 3),
            "sentences": ["We cannot accept this.", "It is too costly for us."], "off_same": True}


def neutralise_quote_grounding():
    return with_source(na, "stepwise_advice", 'got = entry["stance"] = block["quote_none_stance"]', 'pass')


# ---------------------------------------------------------------------------
# 542 P5 second-family auditor on a margin band


def _flip_through_readers(config, item, reply, label):
    prompt = {"prompt_id": "a-fx", "group": "system_advice", "form": "advice", "item_id": item["item_id"],
              "item": item}
    derived = na.audit_prompts(config, prompt, None, reply)
    said = {d["prompt_id"]: (d["user_sha256"], label if d.get("kind") == na.CONFLICT_AUDIT else "supported")
            for d in derived}
    value = {"config": config, "prompts": [prompt]}
    first = na.answers_from_texts(value, {}, measured_audits=said, composed={"a-fx": (reply, [])})["rows"][0]
    again = rr.advisor_rows(value, {}, measured_audits=said, composed={"a-fx": (reply, [])})["rows"][0]
    return ([(d["proposal_id"], d.get("position_id")) for d in derived if d.get("kind") == na.CONFLICT_AUDIT],
            _view(first["reply"])["P-A2-1"], first.get("auditor_flip"), first["reply"] == again["reply"],
            sorted(first["audit"]))


def observe_auditor_band():
    item = _item()
    on = _config(quote_grounding=True, auditor_band=[-0.3, 0.0])
    close = {("stance", "POS-2"): {"support": 0.1, "oppose": 0.4, "accept": 0.5}}
    far = {("stance", "POS-2"): {"support": 0.1, "oppose": 0.2, "accept": 0.7}}
    reply, _s, _a = chain(on, item, {("stance", "POS-2"): "accept"}, close)
    outside, _s2, _a2 = chain(on, item, {("stance", "POS-2"): "accept"}, far)
    bad = _config()
    bad["advice"]["methods"][na.STEPWISE].update(auditor_band=[-0.3, 0.0])
    return {"candidates": reply["proposals"]["P-A2-1"].get("auditor_candidates"),
            "before": _view(reply)["P-A2-1"],
            "supported": _flip_through_readers(on, item, reply, "supported"),
            "unsupported": _flip_through_readers(on, item, reply, "unsupported"),
            "outside_band": outside["proposals"]["P-A2-1"].get("auditor_candidates"),
            "without_quote": caught(lambda: na.check_decoding(bad)),
            "off_same": _off_same(auditor_band=None)}


def expected_auditor_band():
    asked = [("P-A2-1", "POS-2")]
    pieces = ["P-A1-1", "P-A1-2", "P-A2-1"]
    return {"candidates": [{"position": "POS-2", "party": "ALPHA", "sentence": "We cannot accept mandatory contributions.",
                            "oppose_margin": 0.4 - 0.5}],
            "before": ("no_conflict", "accept"),
            "supported": (asked, ("conflict", "reject"), {"asked": 1, "flipped": 1}, True, pieces),
            "unsupported": (asked, ("no_conflict", "accept"), {"asked": 1, "not_supported": 1}, True, pieces),
            "outside_band": None, "without_quote": "raised ValueError", "off_same": True}


def neutralise_auditor_band():
    return with_source(na, "auditor_flip", 'elif label != "supported":', 'elif False:')


# ---------------------------------------------------------------------------
# 543 C3 conditional acceptance


def observe_conditional_accept():
    item = _item()
    on = _config(conditional_accept={"label": "conditional", "counts_as": "accept"})
    reply, _s, asked = chain(on, item, {("stance", "POS-2"): "conditional"})
    kept = reply["proposals"]["P-A2-1"]["position_stances"]["POS-2"]
    bad = _config()
    bad["advice"]["methods"][na.STEPWISE].update(conditional_accept={"label": "oppose", "counts_as": "accept"})
    return {"offered": sorted({a for s, _p, a in asked if s == "stance"}),
            "pos2": (kept["stance"], kept.get("answered")), "pieces": _view(reply),
            "label_taken": caught(lambda: na.check_decoding(bad)),
            "trimmed": caught(lambda: chain(on, item, stance_context=na.TRIMMED_CONTEXT)),
            "off_same": _off_same(conditional_accept=None)}


def expected_conditional_accept():
    # Counted as accept (D-748), the persona's conditional acceptance raises no conflict (its red line answered no).
    return {"offered": [("support", "oppose", "accept", "conditional")], "pos2": ("accept", "conditional"),
            "pieces": dict(BASE, **{"P-A2-1": ("no_conflict", "accept")}),
            "label_taken": "raised ValueError", "trimmed": "raised ValueError", "off_same": True}


def neutralise_conditional_accept():
    return with_source(na, "stepwise_advice", 'entry.update(stance=cond["counts_as"], answered=got)',
                       'entry.update(answered=got)')


GROUPS = {"539": ("fate_forecast",), "540": ("two_checks",), "541": ("quote_grounding",),
          "542": ("auditor_band",), "543": ("conditional_accept",)}
WHAT = {"539": "P2: one fate choice per proposal, marked inferred, under one declared precedence rule, never writing "
               "the conflict field; off unchanged",
        "540": "C2: the stance asked as two yes/no checks, oppose by yes then no, margin the smaller; off unchanged",
        "541": "P6: an oppose grounded by a numbered sentence choice, 0 sending it back, a refusal kept and counted; "
               "off unchanged",
        "542": "P5: a persona position in the declared margin band, grounded, asked of the second family; only its "
               "supported flips the proposal, in both readers; off unchanged",
        "543": "C3: a fourth stance answer counted as its declared stance (D-748) and marked; off unchanged"}


def run_group(number):
    done = []
    for name in GROUPS[number]:
        space = globals()
        observe, expected, neutralise = space["observe_" + name], space["expected_" + name], space["neutralise_" + name]
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                first = observe()
                with neutralise():
                    broken = caught(observe)
                again = observe()
        except Exception as exc:
            return "FAIL", "%s: %s %s" % (name, type(exc).__name__, str(exc)[:300])
        if first != expected():
            return "FAIL", "%s as built: %s" % (name, str(first)[:900])
        if broken == expected():
            return "FAIL", "%s still passes when neutralised" % name
        if again != expected():
            return "FAIL", "%s after restore: %s" % (name, str(again)[:400])
        done.append(name)
    return "PASS", "%d proof, neutralise, fail, restore, pass, no model: %s (%s)" % (
        len(done), WHAT[number], ", ".join(done))


if __name__ == "__main__":
    for n in (sys.argv[1:] or sorted(GROUPS)):
        status, detail = run_group(n)
        print(n, status, detail)
