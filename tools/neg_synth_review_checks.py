#!/usr/bin/env python3
"""Checks 522 to 524 (lane/v-synlab-launch; D-736, NEG-SYNTH-A): the labeller's confidence, Seckin's 200 blind
labels, and no few-shot reuse of labels in the labeller's prompt.

522 confidence: on the replay pass each reply field is scored at its deciding token over the declared answers
    (choice_decision's bind and probabilities on the generation's own logits, CHOICE-A, no extra pass): the step
    whose decoded prefix ends with the field's key, two answers sharing a first token refused, never guessed; the
    stance's top probability is the label's confidence, held to its recorded digest and read back by read-pass
    into the confidence file only (never printed).
523 review (D-739): the draw takes the seeded uniform group and then the lowest-confidence group from the rest,
    in a seeded shuffled order, the seed recorded; the batches for the supervisor (10 a batch) give each position
    a short id, its text and every field's answers numbered, and hold no labeller label, probability or group;
    the reader takes the supervisor's answers by option number or text, refuses a number no option has, an id
    outside its batch and an answer to another version of a batch, and writes counts only (agreement on the
    random group, changes on the low group), his label replacing the labeller's on the low group alone.
524 no few-shot: the questions are the same bytes whether or not his answers or reviewed labels lie beside
    the sheets, and a template whose example carries a value, or names a slot render() does not fill from the
    sheet, is refused.

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes). No model, no
browser, no real item: the invented fixtures of tools/neg_synth_checks.py, in temporary folders.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools"), str(ROOT / "scripts"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_synth as ns  # noqa: E402
import neg_synth_label as nsl  # noqa: E402
import neg_synth_label_pass as lp  # noqa: E402
import neg_synth_label_pass_checks as pc  # noqa: E402
import neg_synth_review as nsr  # noqa: E402

CFG = pc.CFG
_SEEDED = random.Random   # the expected draw, taken before any neutralisation
T = nsl.load_template(CFG)


def _attempt(fn):
    try:
        fn()
        return "built"
    except ValueError:
        return "refused"


# ---------------------------------------------------------------------------
# 522


def _char_model(text, favour):
    """A character tokenizer and logits that give the generated next character 4.0, `favour` 2.0, the rest 0."""
    ids = [ord(c) for c in text]

    def logits(k):
        row = [0.0] * 256
        row[ids[k]] = 4.0
        if favour is not None and ord(favour) != ids[k]:
            row[ord(favour)] = 2.0
        return row
    return ids, logits, (lambda t: "".join(chr(i) for i in t)), (lambda s: [ord(c) for c in s])


def observe_deciding_token():
    reply = '{"article": "A1", "wording": "whole", "stance": "oppose", "firm_limit": "no"}'
    ids, logits, decode, encode = _char_model(reply, favour="s")
    answers = {"article": ["A1", "A2"], "wording": ["whole", "1", "2"], "stance": ["support", "oppose", "accept"],
               "firm_limit": ["no", "yes"]}
    d = lp.field_decisions(ids, logits, decode, encode, answers)
    unreached = lp.field_decisions(ids[:20], logits, decode, encode, {"stance": answers["stance"]})
    e4, e2 = math.exp(4), math.exp(2)
    return {"stance_top": d["stance"]["top"], "stance_p": round(d["stance"]["top_probability"], 4),
            "support_p": round(d["stance"]["probabilities"]["support"], 4),
            "article": d["article"].get("refused", "").split(":")[0], "wording_top": d["wording"]["top"],
            "confidence_is_stance": lp.confidence_of(d) == d["stance"]["top_probability"],
            "unreached": unreached["stance"].get("refused"),
            "expected_p": round(e4 / (e4 + e2 + 1), 4), "expected_support": round(e2 / (e4 + e2 + 1), 4)}


def expected_deciding_token():
    e4, e2 = math.exp(4), math.exp(2)
    return {"stance_top": "oppose", "stance_p": round(e4 / (e4 + e2 + 1), 4),
            "support_p": round(e2 / (e4 + e2 + 1), 4), "article": "choice", "wording_top": "whole",
            "confidence_is_stance": True, "unreached": "field_not_reached",
            "expected_p": round(e4 / (e4 + e2 + 1), 4), "expected_support": round(e2 / (e4 + e2 + 1), 4)}


def neutralise_deciding_token():
    # the deciding step moved one token on: the logits read are no longer those that chose the value
    real = lp.field_decisions
    return patch.object(lp, "field_decisions", lambda ids, logits, decode, encode, answers:
                        real(ids, lambda k: logits(k + 1), decode, encode, answers))


def _confidence_for(prompt):
    return 0.35 + (sum(map(ord, prompt)) % 60) / 100.0


def observe_confidence_read_back():
    with tempfile.TemporaryDirectory() as tmp:
        fx = pc.Fixture(tmp)
        prompts_path = Path(tmp) / "work" / "p.json"
        value = pc.build(fx, prompts_path)
        _code, archive, _folder, _ = pc.run_pass(fx, prompts_path, Path(tmp) / "run",
                                                 generate=pc.fake_generate(fx.all_builds(), _confidence_for))
        out = {}
        for name, path in zip(pc.SETS, fx.paths):
            labels, record = nsl.read_pass(prompts_path, path, archive, CFG)
            want = {(p["item_id"], p["position_id"]): round(_confidence_for(p["prompt"]), 6)
                    for p in value["prompts"] if p["set"] == name}
            got = {(i, k): round(v["confidence"], 6) for i, ps in labels["confidence"].items() for k, v in ps.items()}
            out[name] = {"equal": got == want, "read": record["confidence_read"] == len(want)}
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            nsl.main(["read-pass", "--prompts", str(prompts_path), "--sheets", str(fx.paths[0]), "--evidence",
                      str(archive), "--out", str(Path(tmp) / "w" / "l.json"), "--record", str(Path(tmp) / "w" / "r.json"),
                      "--confidence", str(Path(tmp) / "w" / "c.json")])
        out["printed_no_probability"] = "probabilit" not in printed.getvalue() and "0.3" not in printed.getvalue()
        return out


def expected_confidence_read_back():
    return {"dev_1": {"equal": True, "read": True}, "pilot_1": {"equal": True, "read": True},
            "printed_no_probability": True}


def neutralise_confidence_read_back():
    real = nsl.pass_replies

    def dropped(evidence, prompts_path):
        m, replies, decisions = real(evidence, prompts_path)
        return m, replies, {k: {} for k in decisions}
    return patch.object(nsl, "pass_replies", dropped)


# ---------------------------------------------------------------------------
# 523


def _review_fixture(tmp):
    fx = pc.Fixture(tmp)
    sheets = nsr._sheets([str(p) for p in fx.paths])
    labels, confidence = {}, {}
    for name, builds in fx.builds.items():
        labels[name], confidence[name] = {}, {}
        for b in builds:
            labels[name][b["item_id"]], confidence[name][b["item_id"]] = {}, {}
            for n, p in enumerate(b["positions"]):
                if n % 7 != 3:   # a few positions the labeller left unlabelled
                    labels[name][b["item_id"]][p["id"]] = {"article": p["article"], "proposal": p["proposal"],
                                                            "stance": p["stance"], "red_line": False}
                confidence[name][b["item_id"]][p["id"]] = {"confidence": round(0.3 + ((n * 37) % 61) / 100, 3)}
    return fx, sheets, labels, confidence


def observe_draw():
    with tempfile.TemporaryDirectory() as tmp:
        fx, sheets, labels, confidence = _review_fixture(tmp)
        a = nsr.draw(sheets, labels, confidence, seed=7, n_random=5, n_low=10)
        b = nsr.draw(sheets, labels, confidence, seed=7, n_random=5, n_low=10)
        pool = sorted((s, i, p["id"]) for s, items in sheets.items() for i, sh in items.items() for p in sh["positions"])
        want_random = sorted(_SEEDED(7).sample(pool, 5))
        got_random = sorted((r["set"], r["item_id"], r["position_id"]) for r in a["rows"] if r["group"] == "random")
        rest = [k for k in pool if k not in set(want_random)]

        def key(k):
            has = k[2] in labels[k[0]][k[1]]
            c = confidence[k[0]][k[1]][k[2]]["confidence"]
            return (1 if has else 0, c, k)
        want_low = sorted(sorted(rest, key=key)[:10])
        got_low = sorted((r["set"], r["item_id"], r["position_id"]) for r in a["rows"] if r["group"] == "low")
        return {"same_for_seed": a["rows"] == b["rows"], "seed": a["seed"], "random": got_random == want_random,
                "low": got_low == want_low, "ids": [r["review_id"] for r in a["rows"]] == ["P%03d" % n for n in range(1, 16)],
                "shuffled": [r["group"] for r in a["rows"]] != ["random"] * 5 + ["low"] * 10}


def expected_draw():
    return {"same_for_seed": True, "seed": 7, "random": True, "low": True, "ids": True, "shuffled": True}


def neutralise_draw():
    class Unseeded(random.Random):
        def sample(self, population, k):
            return list(population)[:k]
    return patch.object(nsr.random, "Random", Unseeded)


def observe_two_phase():
    """Seckin 16:45: the random group drawn before the labeller (sheets only, seeded, its SHA-256 recorded), written
    in batches; the later draw takes it unchanged, excludes it from the low group and continues the ids, so the
    early batches are the same batches; a changed record is refused."""
    with tempfile.TemporaryDirectory() as tmp:
        fx, sheets, labels, confidence = _review_fixture(tmp)
        first = nsr.draw_random(sheets, seed=5, n_random=6)
        again = nsr.draw_random(sheets, seed=5, n_random=6)
        pool = nsr._pool(sheets)
        want = sorted(_SEEDED(5).sample(pool, 6))
        later = nsr.draw_after(sheets, labels, confidence, first, n_low=8)
        early = [r for r in later["rows"] if r["group"] == "random"]
        low = [(r["set"], r["item_id"], r["position_id"]) for r in later["rows"] if r["group"] == "low"]
        taken = {(r["set"], r["item_id"], r["position_id"]) for r in first["rows"]}
        b_early = nsr.batches(dict(first, rows=nsr.prior_rows(first, sheets)), sheets, T, size=3)
        b_later = nsr.batches(later, sheets, T, size=3)
        tampered = json.loads(json.dumps(first))
        tampered["rows"][0]["position_id"] = tampered["rows"][1]["position_id"]
        return {"reproducible": first["rows"] == again["rows"], "seed": first["seed"],
                "random_is_seeded_sample": sorted((r["set"], r["item_id"], r["position_id"]) for r in first["rows"]) == want,
                "sha_recorded": first["drawn_sha256"] == nsr._keys_sha(first["rows"]),
                "kept_unchanged": early == first["rows"], "low_excludes_random": not (set(low) & taken),
                "low_count": len(low), "ids": [r["review_id"] for r in later["rows"]] == ["P%03d" % n for n in range(1, 15)],
                "early_batches_same": [v["sha256"] for _n, v, _t in b_early] == [v["sha256"] for _n, v, _t in b_later[:2]],
                "tampered": _attempt(lambda: nsr.draw_after(sheets, labels, confidence, tampered, n_low=8))}


def expected_two_phase():
    return {"reproducible": True, "seed": 5, "random_is_seeded_sample": True, "sha_recorded": True,
            "kept_unchanged": True, "low_excludes_random": True, "low_count": 8, "ids": True,
            "early_batches_same": True, "tampered": "refused"}


def neutralise_two_phase():
    """The exclusion removed: the low group may take positions the random group already drew."""
    real_after = nsr.draw_after

    def after_without_exclusion(sheets, labels, confidence, prior, *, n_low=150):
        out = real_after(sheets, labels, confidence, dict(prior, rows=[], drawn_sha256=nsr._keys_sha([])), n_low=n_low)
        return dict(out, rows=nsr.prior_rows(prior, sheets) + out["rows"])
    return patch.object(nsr, "draw_after", after_without_exclusion)


FORBIDDEN_IN_BATCH = ('"group"', '"confidence"', 'probabilit', '"random"', '"low"', '"stance": "', '"proposal"')


def observe_batches():
    with tempfile.TemporaryDirectory() as tmp:
        fx, sheets, labels, confidence = _review_fixture(tmp)
        review = nsr.draw(sheets, labels, confidence, seed=11, n_random=5, n_low=10)
        written = nsr.batches(review, sheets, T, size=4)
        again = nsr.batches(review, sheets, T, size=4)
        ids = [i["id"] for _n, v, _t in written for i in v["items"]]
        blob = json.dumps([v for _n, v, _t in written]) + "".join(t for _n, _v, t in written)
        numbered = all(list(opts) == [str(n) for n in range(1, len(opts) + 1)]
                       for _n, v, _t in written for i in v["items"] for opts in i["options"].values())
        quotes = all(i["quote"] in txt for _n, v, txt in written for i in v["items"])
        return {"sizes": [len(v["items"]) for _n, v, _t in written], "ids": ids == [r["review_id"] for r in review["rows"]],
                "forbidden": [w for w in FORBIDDEN_IN_BATCH if w in blob], "numbered": numbered,
                "text_has_quotes": quotes, "stable": [v for _n, v, _t in written] == [v for _n, v, _t in again]}


def expected_batches():
    return {"sizes": [4, 4, 4, 3], "ids": True, "forbidden": [], "numbered": True, "text_has_quotes": True,
            "stable": True}


def neutralise_batches():
    real = nsr.page_items

    def leaky(review, sheets, t):
        return [dict(item, group=row["group"]) for item, row in zip(real(review, sheets, t), review["rows"])]
    return patch.object(nsr, "page_items", leaky)


def _answers_for(review, labels, written, flip, as_text=False):
    """The supervisor's answer files: the labeller's own label by option number, the stance changed on `flip`."""
    files = []
    for number, value, _txt in written:
        out = {}
        for item in value["items"]:
            row = next(r for r in review["rows"] if r["review_id"] == item["id"])
            olmo = labels[row["set"]][row["item_id"]].get(row["position_id"])
            want = {"article": olmo["article"] if olmo else item["options"]["article"]["1"],
                    "wording": ("whole" if olmo["proposal"] is None else str(olmo["proposal"])) if olmo else "whole",
                    "stance": olmo["stance"] if olmo else "support"}
            if item["id"] in flip:
                want["stance"] = "support" if want["stance"] != "support" else "oppose"
            if "firm_limit" in item["options"]:
                want["firm_limit"] = "no"
            out[item["id"]] = {f: (v if as_text and not v.isdigit() else next(n for n, o in item["options"][f].items() if o == v))
                               for f, v in want.items()}
        files.append({"schema": nsr.ANSWERS_SCHEMA, "batch": number, "batch_sha256": value["sha256"], "answers": out})
    return files


def observe_reader():
    with tempfile.TemporaryDirectory() as tmp:
        fx, sheets, labels, confidence = _review_fixture(tmp)
        review = nsr.draw(sheets, labels, confidence, seed=3, n_random=5, n_low=10)
        written = nsr.batches(review, sheets, T)
        rnd = [r for r in review["rows"] if r["group"] == "random"]
        low = [r for r in review["rows"] if r["group"] == "low"]
        has = lambda r: r["position_id"] in labels[r["set"]][r["item_id"]]
        labelled_low = [r for r in low if has(r)]
        flip = {r["review_id"] for r in labelled_low[:2]} | set([r["review_id"] for r in rnd if has(r)][:1])
        files = _answers_for(review, labels, written, flip)
        counts, merged = nsr.read(review, files, labels, sheets, T)
        by_text, _ = nsr.read(review, _answers_for(review, labels, written, flip, as_text=True), labels, sheets, T)
        target = labelled_low[0]
        replaced = merged[target["set"]][target["item_id"]][target["position_id"]]["stance"] \
            != labels[target["set"]][target["item_id"]][target["position_id"]]["stance"]
        untouched = all(merged[r["set"]][r["item_id"]].get(r["position_id"]) == labels[r["set"]][r["item_id"]].get(r["position_id"])
                        for r in rnd)
        bad_number = copy.deepcopy(files)
        first = next(iter(bad_number[0]["answers"]))
        bad_number[0]["answers"][first]["stance"] = 9
        moved = copy.deepcopy(files)
        moved[1]["answers"][first] = moved[0]["answers"].pop(first)
        old = copy.deepcopy(files)
        old[0]["batch_sha256"] = "0" * 64
        g = counts["groups"]
        flipped_rnd = len(flip & {r["review_id"] for r in rnd})
        text = json.dumps(counts)
        return {"random_agree": g["random"]["agree_all"] == sum(has(r) for r in rnd) - flipped_rnd,
                "low_changed": g["low"]["changed"] == 2 + (len(low) - len(labelled_low)),
                "answered": g["random"]["answered"] + g["low"]["answered"], "by_text_same": by_text["groups"] == g,
                "replaced_on_low": replaced, "random_untouched": untouched,
                "bad_number": _attempt(lambda: nsr.read(review, bad_number, labels, sheets, T)),
                "other_batch": _attempt(lambda: nsr.read(review, moved, labels, sheets, T)),
                "old_batch": _attempt(lambda: nsr.read(review, old, labels, sheets, T)),
                "counts_hold_no_id": not any(r["item_id"] in text or r["review_id"] in text for r in review["rows"])}


def expected_reader():
    return {"random_agree": True, "low_changed": True, "answered": 15, "by_text_same": True, "replaced_on_low": True,
            "random_untouched": True, "bad_number": "refused", "other_batch": "refused", "old_batch": "refused",
            "counts_hold_no_id": True}


def neutralise_reader():
    return patch.object(nsr, "as_label", lambda answer, t: None)


# ---------------------------------------------------------------------------
# 524


_FIXTURE = None


def observe_no_few_shot():
    with tempfile.TemporaryDirectory() as tmp:
        fx = pc.Fixture(tmp)
        first = pc.build(fx, Path(tmp) / "w1" / "p.json")
        # his saved labels and the reviewed labels beside the sheets, as role V's folders would hold them
        global _FIXTURE
        _FIXTURE = Path(tmp)
        (Path(tmp) / "answers_batch_01.json").write_text(json.dumps(
            {"schema": nsr.ANSWERS_SCHEMA, "batch": 1, "answers": {"P001": {"article": 1, "wording": 1, "stance": 2}}}),
            encoding="utf-8")
        (Path(tmp) / "labels_dev_1_reviewed.json").write_text(json.dumps({"x": {"POS-1": {"stance": "oppose"}}}),
                                                              encoding="utf-8")
        second = pc.build(fx, Path(tmp) / "w2" / "p.json")
        shot = copy.deepcopy(T)
        shot["example"] = {"article": "A1", "wording": "whole", "stance": "oppose", "firm_limit": "no"}
        slot = copy.deepcopy(T)
        slot["template"] = slot["template"] + "\n{examples}"
        return {"same_questions": [p["prompt"] for p in first["prompts"]] == [p["prompt"] for p in second["prompts"]],
                "valued_example": _attempt(lambda: nsl.assert_no_shots(shot)),
                "extra_slot": _attempt(lambda: nsl.assert_no_shots(slot)),
                "shipped": _attempt(lambda: nsl.assert_no_shots(copy.deepcopy(T)))}


def expected_no_few_shot():
    return {"same_questions": True, "valued_example": "refused", "extra_slot": "refused", "shipped": "built"}


def neutralise_no_few_shot():
    real = nsl.render

    def shots(sheet, position, t):
        text = real(sheet, position, t)
        found = _FIXTURE / "answers_batch_01.json" if _FIXTURE else None
        return text + ("\nEXAMPLES " + found.read_text(encoding="utf-8") if found and found.is_file() else "")
    stack = contextlib.ExitStack()
    stack.enter_context(patch.object(nsl, "render", shots))
    stack.enter_context(patch.object(nsl, "assert_no_shots", lambda t: t))
    return stack


def observe_stance_definition():
    """D-748 (Seckin 18:50): the stance definitions are the labeller template's declared `stance_definition` (config,
    never code), read with the template at call time, and every rendered question carries them word for word; the
    template's own text names the slot, and they stay a definition: no example is added (D-736 item 4)."""
    t = nsl.load_template(ns.load_config())
    with tempfile.TemporaryDirectory() as tmp:
        fx = pc.Fixture(tmp)
        built = pc.build(fx, Path(tmp) / "w" / "p.json")
    prompts = [p["prompt"] for p in built["prompts"]]
    return {"declared": bool(t.get("stance_definition")) and "D-748" in t.get("stance_definition_decision", ""),
            "slot_in_template": "{stance_definition}" in t["template"],
            "every_question": bool(prompts) and all(t["stance_definition"] in q for q in prompts),
            "still_no_shots": _attempt(lambda: nsl.assert_no_shots(copy.deepcopy(t)))}


def expected_stance_definition():
    return {"declared": True, "slot_in_template": True, "every_question": True, "still_no_shots": "built"}


def neutralise_stance_definition():
    """The definition dropped from the rendered question (the slot filled with nothing)."""
    real = nsl.render
    return patch.object(nsl, "render", lambda sheet, position, t: real(sheet, position, dict(t, stance_definition="")))


PROOFS = {"522": ("deciding_token", "confidence_read_back"), "523": ("draw", "two_phase", "batches", "reader"),
          "524": ("no_few_shot", "stance_definition")}
WHAT = {"522": "the labeller's confidence at the deciding token over the declared answers, read back unprinted",
        "523": "the seeded 50 (drawn first, before the labeller) and lowest-confidence 150 excluding them, blind numbered batches of 10, a counts-only answers reader",
        "524": "no few-shot reuse of labels in the labeller's prompt"}


def _caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a neutralised proof may raise; that is its failure
        return "raised %s" % type(exc).__name__


def run_group(number):
    done = []
    for name in PROOFS[number]:
        space = globals()
        observe, expected, neutralise = space["observe_" + name], space["expected_" + name], space["neutralise_" + name]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                first = observe()
                with neutralise():
                    broken = _caught(observe)
                again = observe()
        except Exception as exc:
            return "FAIL", "%s: %s %s" % (name, type(exc).__name__, str(exc)[:300])
        if first != expected():
            return "FAIL", "%s as built: %s" % (name, str(first)[:600])
        if broken == expected():
            return "FAIL", "%s still passes when neutralised" % name
        if again != expected():
            return "FAIL", "%s after restore: %s" % (name, str(again)[:400])
        done.append(name)
    return "PASS", "%d proofs, each neutralise, fail, restore, pass, no model: %s (%s)" % (
        len(done), WHAT[number], ", ".join(done))


if __name__ == "__main__":
    results = [(g,) + run_group(g) for g in (sys.argv[1:] or sorted(PROOFS))]
    for g, status, detail in results:
        print(g, status, detail)
    raise SystemExit(0 if all(s == "PASS" for _g, s, _d in results) else 1)
