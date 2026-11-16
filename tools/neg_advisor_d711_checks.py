#!/usr/bin/env python3
"""Checks 466 to 468 (lane neg-round1, second task): D-711 (never invent; both record kinds), D-712 (a floor on
the class that matters) and D-713 (two reasoning methods, declared and off by default), proven on the invented
fixture of tools/neg_advisor_checks.py with a fake generate, no model and no item.

466, D-711: an entry may say `basis: inferred` only with a line of five words or more found in the item's text,
    else Python refuses it; an inferred claim on a proposal or party with no position on record is set aside
    (visible, never scored) and the answer is not_stated; an on-record claim with no position is counted; the
    scoring reader reads the basis by its form. A build declares `record_kind` (complete or missing_notes) and a
    masked party only on a missing_notes item; every bar figure is reported per kind; a bar reading is refused
    for a set without both kinds or with an item of undeclared kind.
467, D-712: the class floors (conflict F1 under M1 and M1m, movable F1 under M10, the hit rate in each fate
    under M4), each at 0.60, are reported and a bar line with its figures met but a floor missed is not met.
468, D-713: `method` is declared on the system's advice group only (B1 plain); reason_first puts a rationale
    before the labels, which the readers keep apart and no figure reads; stepwise asks its chain through an
    injected `ask`, each answer checked by Python before the next, and composes conflict, stance and
    alignment by the plan's rules.
Each proof neutralised, failed, restored and passed (scripts/effect_proof.py).
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from effect_proof import prove_effect  # noqa: E402
import neg_advisor as na  # noqa: E402
import reread_replies as rr  # noqa: E402
import schema_decoding as sd  # noqa: E402
import neg_advisor_checks as base  # noqa: E402

sc = base.sc
A1_LINE = "Each party shall report all outbreak data"            # in A1's first proposal, 7 words
GAMMA = dict(copy.deepcopy(base.BUILD), parties=base.BUILD["parties"] + [{"id": "GAMMA", "kind": "single"}])


def parsed(item, value):
    return na.parse_advice(json.dumps(value), item)


class _Proofs(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        type(self).evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))


class BasisChecks(_Proofs):
    evidence = []

    def test_01_inferred_needs_its_line(self):
        item, _key = base.built()
        entry = {"id": "P-A1-2", "conflict": "conflict", "stance": "reject", "reasons": [], "basis": "inferred"}
        replies = {"found": dict(entry, basis_quote=A1_LINE), "missing": entry,
                   "short": dict(entry, basis_quote="Each party shall"),
                   "absent": dict(entry, basis_quote="Each party shall never report anything at all")}

        def observe():
            out = {}
            for name, e in replies.items():
                got, counts = sc.system_python(item, parsed(item, dict(base.GOOD_REPLY, proposals=[e])))
                piece = got["proposals"]["P-A1-2"]
                out[name] = (piece.get("conflict"), piece.get("inferred_refused"), (piece.get("inferred") or {}).get("conflict"),
                             counts["inferred_kept"], counts["inferred_refused"], counts["on_record"])
            return out
        # P-A1-2 has no persona position: an inferred conflict with its line is set aside, never scored; without
        # a found line it is refused; the answer is not_stated either way (D-711 item 1).
        want = {"found": ("not_stated", None, "conflict", 1, 0, 0),
                "missing": ("not_stated", "no_line", None, 0, 1, 0),
                "short": ("not_stated", "line_too_short", None, 0, 1, 0),
                "absent": ("not_stated", "line_not_found", None, 0, 1, 0)}
        self.assertEqual(observe(), want)
        self.prove("inferred_needs_a_found_line", observe, want,
                   lambda: patch.object(sc, "basis_refusal", lambda item, quote: None))

    def test_02_on_record_without_position_counted(self):
        item, _key = base.built()
        reply = parsed(item, dict(base.GOOD_REPLY, proposals=[
            {"id": "P-A1-2", "conflict": "no_conflict", "stance": "accept", "reasons": []},
            {"id": "P-A1-1", "conflict": "no_conflict", "stance": "accept", "reasons": ["POS-1"],
             "basis": "inferred", "basis_quote": A1_LINE}]))

        def observe():
            got, counts = sc.system_python(item, reply)
            return (got["proposals"]["P-A1-2"]["conflict"], got["proposals"]["P-A1-1"]["conflict"],
                    counts["on_record"], counts["on_record_without_position"], counts["inferred_kept"])
        # The inferred piece on a proposal with a position keeps its answer but is counted inferred, never on record.
        want = ("not_stated", "no_conflict", 1, 1, 1)
        self.assertEqual(observe(), want)
        self.prove("on_record_and_inferred_counted_apart", observe, want,
                   lambda: patch.object(na, "INFERRED", "something else"))

    def test_03_alignment_inferred(self):
        item, _key = sc.build_item(copy.deepcopy(GAMMA))
        found = parsed(item, dict(base.GOOD_REPLY, alignment=[
            {"article": "A1", "aligned": ["BETA", "GAMMA"], "opposed": [], "basis": "inferred", "basis_quote": A1_LINE}]))
        lost = parsed(item, dict(base.GOOD_REPLY, alignment=[
            {"article": "A1", "aligned": ["BETA", "GAMMA"], "opposed": [], "basis": "inferred"}]))

        def observe():
            a, ca = sc.system_python(item, found)
            b, cb = sc.system_python(item, lost)
            return (a["alignment"]["A1"]["aligned"], a["alignment"]["A1"].get("inferred"), ca["alignment_inferred_set_aside"],
                    b["alignment"]["A1"]["aligned"], b["alignment"]["A1"].get("inferred_refused"), cb["alignment_inferred_refused"])
        want = (["BETA"], [{"party": "GAMMA", "side": "aligned"}], 1, [], "no_line", 1)
        self.assertEqual(observe(), want)
        self.prove("alignment_inferred_set_aside_or_refused", observe, want,
                   lambda: patch.object(sc, "basis_refusal", lambda item, quote: None))

    def test_04_reader_reads_the_basis_by_form(self):
        item, _key = base.built()
        value = dict(base.GOOD_REPLY, proposals=[dict(base.GOOD_REPLY["proposals"][0], basis="Inferred",
                                                      basis_quote="  " + A1_LINE + " "),
                                                 dict(base.GOOD_REPLY["proposals"][1], basis="guessed")])
        observe = lambda: (lambda r: (r[0]["proposals"]["P-A1-1"].get("basis"), r[0]["proposals"]["P-A1-1"].get("basis_quote"),
                                      r[0]["proposals"]["P-A1-2"].get("basis"), r[1].get("proposals.basis")))(
            rr.advice(json.dumps(value), item))
        want = ("inferred", A1_LINE, None, {"not_declared": 1})
        self.assertEqual(observe(), want)
        self.prove("reader_reads_basis_by_form", observe, want,
                   lambda: patch.object(rr, "_basis", lambda e, entry, field, drops: None))

    def test_05_record_kind_declared_and_masked(self):
        def outcome(**extra):
            try:
                item, key = sc.build_item(dict(copy.deepcopy(base.BUILD), **extra))
            except ValueError as e:
                return "refused: " + str(e).split(": ", 1)[1][:24]
            return (item.get("record_kind"), key.get("record_kind"), key.get("masked_party"), "masked_party" in item,
                    "missing_notes" in na.render_advice(na.load_config(), item))
        observe = lambda: [outcome(), outcome(record_kind="complete"), outcome(record_kind="missing_notes", masked_party="BETA"),
                           outcome(record_kind="partial"), outcome(record_kind="complete", masked_party="BETA"),
                           outcome(record_kind="missing_notes", masked_party="NOBODY")]
        want = [(None, None, None, False, False), ("complete", "complete", None, False, False),
                ("missing_notes", "missing_notes", "BETA", False, False), "refused: record_kind is one of co",
                "refused: a masked party is one of", "refused: a masked party is one of"]
        self.assertEqual(observe(), want)
        self.prove("record_kind_and_masked_party_declared", observe, want,
                   lambda: patch.object(sc, "RECORD_KINDS", ("complete", "missing_notes", "partial")))

    def test_06_bar_reading_needs_both_kinds(self):
        complete = dict(copy.deepcopy(base.BUILD), record_kind="complete")
        # Two parties on the missing-notes item, so the set holds two party structures (Seckin 20:32, check 490).
        missing = dict(copy.deepcopy(base.BUILD), item_id="fx-k2-beta", record_kind="missing_notes", masked_party="BETA",
                       parties=base.BUILD["parties"][:2])
        # D-715 item 1: each structure holds MIN_ITEMS_PER_STRUCTURE headline items, or the reading is refused.
        copies = [dict(copy.deepcopy(b), item_id="%s-%d" % (b["item_id"], n)) if n else b
                  for b in (complete, missing) for n in range(sc.MIN_ITEMS_PER_STRUCTURE)]
        built = [sc.build_item(b) for b in copies]
        items = {i["item_id"]: i for i, _k in built}
        keys = {k["item_id"]: k for _i, k in built}
        rows = [{"item_id": i, "form": "advice", "group": g, "reply": parsed(items[i], base.GOOD_REPLY),
                 "audit": {}, "drops": {}} for i in items for g in ("b1", "system_advice")]
        answers = {"rows": rows}

        def observe():
            both = sc.report(items, keys, {"B1": (answers, "b1"), "system": (answers, "system_advice")}, resamples=50)
            one_keys = {"fx-k2-alpha": keys["fx-k2-alpha"]}
            one = sc.report({"fx-k2-alpha": items["fx-k2-alpha"]}, one_keys,
                            {"B1": (answers, "b1"), "system": (answers, "system_advice")}, resamples=50)
            return (sorted(both["by_record_kind"]["system"]), both["neg_bar"].get("refused"), both["neg_bar"]["passed"],
                    sorted(both["neg_bar"].get("kinds") or {}), (one["neg_bar"].get("refused") or "")[:40])
        # Five copies a structure (D-715 item 1): the fixture's good reply on them now meets every line, so it passes.
        want = (["complete", "missing_notes"], None, True, ["complete", "missing_notes"],
                "the set does not hold both record kinds ")
        self.assertEqual(observe(), want)
        self.prove("bar_read_on_both_kinds_or_refused", observe, want,
                   lambda: patch.object(sc, "record_kind", lambda key: "complete"))


class FloorChecks(_Proofs):
    evidence = []

    def test_01_a_floor_missed_fails_its_line(self):
        FLOORS = list(sc.CLASS_FLOORS)
        def block(conflict_f1):
            figs = {f: {"estimate": 0.9, "lower": 0.5} for f in sc.BAR_FIGURES}
            figs["M8"] = {"estimate": 1.0, "lower": 1.0}
            floors = [{"line": line, "figure": fig, "class": cls, "value": 0.9, "rows": 10, "floor": 0.6, "met": True}
                      for line, fig, cls in FLOORS]
            floors[0] = dict(floors[0], value=conflict_f1, met=conflict_f1 >= 0.6)
            return {"items": 6, "figures": figs, "floors": floors, "drops": {"share": 0.0}}
        # D-715 item 1: enough items of each structure, and every structure and overall meeting its lines.
        keys = {"%s%d" % (s, n): {"part": "P", "record_kind": kind, "structure": s}
                for s, kind in (("two_singles", "complete"), ("three_or_more", "missing_notes"))
                for n in range(sc.MIN_ITEMS_PER_STRUCTURE)}
        good = {s: block(0.9) for s in ("two_singles", "three_or_more", "overall")}

        def observe():
            low = sc.neg_bar_reading(keys, {"complete": block(0.0), "missing_notes": block(0.9)}, good)
            high = sc.neg_bar_reading(keys, {"complete": block(0.9), "missing_notes": block(0.9)}, good)
            line1 = next(v for k, v in low["kinds"]["complete"].items() if k.endswith("1"))
            return low["passed"], line1["figures_met"], line1["floors_missed"], high["passed"]
        want = (False, True, ["M1:conflict"], True)
        self.assertEqual(observe(), want)
        # Neutralised: the floors are no longer tied to their lines (each line is read with no floor of its own).
        self.prove("a_missed_floor_fails_its_line", observe, want, lambda: patch.object(
            sc, "NEG_BAR_LINES", tuple(("L" + line, needs) for line, needs in sc.NEG_BAR_LINES)))

    def test_02_floors_from_the_rows(self):
        item, key = base.built()
        # every proposal answered no_conflict and accept: M1 passes two of three classes, the conflict class not
        reply = parsed(item, dict(base.GOOD_REPLY, proposals=[dict(p, conflict="no_conflict", stance="accept")
                                                              for p in base.GOOD_REPLY["proposals"]]))
        parts = {item["item_id"]: sc.item_parts(item, key, reply)}

        def observe():
            return [(f["figure"], f["class"], None if f["value"] is None else round(f["value"], 3), f["met"])
                    for f in sc.class_floors(parts, [item["item_id"]])]
        want = [("M1", "conflict", 0.0, False), ("M1m", "conflict", 0.0, False), ("M10", "movable", 0.0, False),
                ("M4f", "kept", 1.0, True), ("M4f", "changed", 0.0, False), ("M4f", "removed", 0.0, False)]
        self.assertEqual(observe(), want)
        self.prove("floors_read_from_the_rows", observe, want, lambda: patch.object(sc, "CLASS_FLOOR", 0.0))


def fake_ask(script):
    """A fake generate for the step-wise chain: the fixture's own stances by quote, the proposal's own words for
    `changes`, and the scripted answers for red line, open point and wording, every question recorded."""
    stance_of = {p["quote"]: p["stance"] for p in base.BUILD["positions"]}
    asked = []

    def ask(step, user, answers):
        asked.append(step)
        if step == "changes":
            return script.get("changes") or " ".join(user.splitlines()[1].split(": ", 1)[1].split()[:6])
        if step == "stance":
            return script.get("stance") or next(s for q, s in stance_of.items() if q in user)
        if step == "open_point":
            return "yes" if "share outbreak data" in user else "no"
        return script.get(step, "Each party shall report outbreak data within a period it sets")
    ask.asked = asked
    return ask


class MethodChecks(_Proofs):
    evidence = []

    def test_01_method_declared_on_the_system_only(self):
        config = na.load_config()

        def declare(group, method):
            c = copy.deepcopy(config)
            for g in c["models"]:
                if g["group"] == group:
                    g["method"] = method
            try:
                na.check_decoding(c)
            except ValueError:
                return "refused"
            return na.method_of(c, group)
        observe = lambda: [declare("system_advice", "reason_first"), declare("system_advice", "stepwise"),
                           declare("b1", "reason_first"), declare("system_advice", "think_hard"), na.method_of(config, "system_advice")]
        want = ["reason_first", "stepwise", "refused", "refused", "plain"]
        self.assertEqual(observe(), want)
        self.prove("method_on_the_system_group_only", observe, want, lambda: patch.object(na, "METHOD_GROUP", "b1"))
        # A prompts file built with the method declared carries it on the system's prompts alone and loads, each
        # prompt held to its own rendering (load_prompts renders with the group's declared method).
        import tempfile
        declared = copy.deepcopy(config)
        for g in declared["models"]:
            if g["group"] == "system_advice":
                g["method"] = na.REASON_FIRST

        def built_and_loaded():
            with base.setdir() as root, tempfile.TemporaryDirectory(prefix="negm_") as td:
                path = Path(td) / "config.json"
                path.write_text(json.dumps(declared), encoding="utf-8")
                out = Path(td) / "prompts.json"
                na.build(root, "advice", ["b1", "system_advice"], out, config_path=path)
                try:
                    loaded = na.load_prompts(out)
                except ValueError as e:
                    return "refused: " + str(e)[:30]
                prompts = loaded["prompts"] if isinstance(loaded, dict) else loaded
                return sorted((p["group"], p.get("method"), "rationale" in p["user"]) for p in prompts)
        want_b = [("b1", None, False), ("system_advice", "reason_first", True)]
        self.assertEqual(built_and_loaded(), want_b)
        self.prove("method_prompts_held_to_their_rendering", built_and_loaded, want_b,
                   lambda: patch.object(na, "method_of", lambda config, group: na.PLAIN))

    def test_02_reason_first_kept_apart(self):
        item, key = base.built()
        config = na.load_config()
        props = base.GOOD_REPLY["proposals"]
        with_rationale = lambda words: dict(base.GOOD_REPLY, proposals=[
            dict([("id", p["id"]), ("rationale", words)] + [(k, v) for k, v in p.items() if k != "id"]) for p in props])
        fake_generate = lambda words: json.dumps(with_rationale(words))   # the model's text under reason_first

        def observe():
            schema = na.advice_schema(item, na.REASON_FIRST)
            text_a, text_b = fake_generate("It narrows the reporting time."), fake_generate("Something else entirely.")
            read_a, read_b = rr.advice(text_a, item)[0], rr.advice(text_b, item)[0]
            parts = lambda r: {f: dict(c) for f, c in sc.item_parts(item, key, r).items()}
            return (sd.accepts(schema, text_a), sd.accepts(schema, json.dumps(base.GOOD_REPLY)),
                    read_a["proposals"]["P-A1-1"]["rationale"], parts(read_a) == parts(read_b) == parts(parsed(item, base.GOOD_REPLY)),
                    "rationale" in na.render_advice(config, item, na.REASON_FIRST), "rationale" in na.render_advice(config, item))
        want = (True, False, "It narrows the reporting time.", True, True, False)
        self.assertEqual(observe(), want)
        self.prove("reason_first_rationale_before_labels_never_scored", observe, want,
                   lambda: patch.object(na, "RATIONALE_MAX_CHARS", 5))

    def test_03_stepwise_chain_checked_step_by_step(self):
        item, key = base.built()
        config = na.load_config()

        def observe():
            ask = fake_ask({"red_line": "yes"})
            reply, steps = na.stepwise_advice(config, item, ask)
            got = {pid: (e.get("conflict"), e.get("stance"), bool(e.get("wording"))) for pid, e in sorted(reply["proposals"].items())}
            bad, bad_steps = na.stepwise_advice(config, item, fake_ask({"changes": "words that are not in it at all"}))
            maybe, _s = na.stepwise_advice(config, item, fake_ask({"stance": "maybe"}))
            return (got, reply["alignment"], sorted(Counter(ask.asked).items()),
                    {k: (e.get("conflict"), e.get("stance")) for k, e in bad["proposals"].items()},
                    sorted({s["refused"] for s in bad_steps if s["refused"]}),
                    {k: e.get("conflict") for k, e in maybe["proposals"].items()})
        # The conflict Python composes from the checked stances equals the key's labels, which it never read.
        want = ({"P-A1-1": ("no_conflict", "accept", False), "P-A1-2": ("not_stated", "counter", True),
                 "P-A2-1": ("conflict", "reject", False)},
                {"A1": {"aligned": ["BETA"], "opposed": ["GROUP1"]}, "A2": {"aligned": ["BETA"], "opposed": ["GROUP1"]},
                 "A3": {"aligned": [], "opposed": []}},
                [("changes", 3), ("open_point", 3), ("red_line", 1), ("stance", 6), ("wording", 1)],
                {"P-A1-1": (None, None), "P-A1-2": (None, None), "P-A2-1": (None, None)}, ["not_in_the_proposal"],
                {"P-A1-1": None, "P-A1-2": "not_stated", "P-A2-1": None})
        self.assertEqual(observe(), want)
        self.assertEqual({p: key["proposals"][p]["conflict"] for p in key["proposals"]},
                         {p: c for p, (c, _s, _w) in want[0].items()})
        self.prove("stepwise_each_answer_checked_before_the_next", observe, want,
                   lambda: patch.object(na, "_step_check", lambda step, answer, item, proposal, position=None: (answer, None)))


def _run(cls, what):
    cls.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(cls).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", "%d proofs, each neutralise, fail, restore, pass, no model and no item: %s" % (len(cls.evidence), what)


def check_basis_and_kinds():
    return _run(BasisChecks, "an inferred entry stands only with a found line of five words or more and is never on "
                             "record, an inferred claim with no position set aside and the answer not_stated, on-record "
                             "claims with no position counted, the basis read by its form, record_kind and the masked "
                             "party declared at build, every bar figure per kind, a bar reading refused without both kinds")


def check_class_floors():
    return _run(FloorChecks, "the conflict, movable and per-fate floors at 0.60 reported from the rows, and a bar line "
                             "whose figures pass but whose floor is missed not met")


def check_methods():
    return _run(MethodChecks, "a method declared on the system's advice group alone, reason_first's rationale before the "
                              "labels kept apart and never scored, the step-wise chain through a fake generate with each "
                              "answer checked before the next and conflict, stance and alignment composed by Python")


def main():
    code = 0
    for name, fn in (("466", check_basis_and_kinds), ("467", check_class_floors), ("468", check_methods)):
        status, detail = fn()
        print(name, status, detail)
        code |= status != "PASS"
    return code


if __name__ == "__main__":
    raise SystemExit(main())
