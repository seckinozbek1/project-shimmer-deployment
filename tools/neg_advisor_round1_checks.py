#!/usr/bin/env python3
"""Check 450 (lane neg-round1, standing order 102, D-707): the negotiation advisor system's Python step and the
advice schema's one entry per proposal, proven on the invented fixture of tools/neg_advisor_checks.py, no model
and no item.

1. Conflict: a proposal with no applicable persona position (the plan's `applicable`) is not_stated, filled as
   Python's piece or set with the model's answer kept beside it; where a position applies, a model's not_stated
   is refused and kept; conflict against no_conflict is left to the model. The function takes no key, and the
   item's positions carry no stance, so nothing is read from a quote's words (WORDS-A).
2. State: dropped for a previous-round article no longer in the round; the structural state where binding is
   impossible; where binding is possible the model's binding or structural answer stands, any other refused.
3. Alignment: a party listed on an article where it or the persona holds no applicable position is taken off.
4. Python's own pieces are never audited, checked, or counted as the model's in the trail, M8 or M10.
5. The report applies the step to the system arm only; M1's two diagnostic parts (M1s, M1m) by structure.
6. The advice schema: one entry per proposal in the excerpt's order with its own id, at most REASONS_MAX
   reasons; the grammar's tuple and max_items nodes.
Each proof neutralised, failed, restored and passed (scripts/effect_proof.py). The schema's decoding under a
stand-in model (tools/neg_advisor_checks.py test_18i) imports torch and runs with the full gate on Lambda.
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
import schema_decoding as sd  # noqa: E402
import neg_advisor_checks as base  # noqa: E402

sc = base.sc
GAMMA = dict(copy.deepcopy(base.BUILD), parties=base.BUILD["parties"] + [{"id": "GAMMA", "kind": "single"}])


def parsed(item, value):
    return na.parse_advice(json.dumps(value), item)


class Round1Checks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        Round1Checks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    def test_01_conflict_from_the_positions(self):
        item, key = base.built()
        self.assertFalse(any("stance" in p for p in item["positions"]))   # the item never carries a stance
        reply = parsed(item, {"proposals": [
            {"id": "P-A1-1", "conflict": "no_conflict", "stance": "accept", "reasons": ["POS-1"]},
            {"id": "P-A2-1", "conflict": "not_stated", "stance": "accept", "reasons": []}],
            "trades": [], "approach": [], "alignment": [], "state": []})
        other = parsed(item, dict(base.GOOD_REPLY, proposals=[
            dict(base.GOOD_REPLY["proposals"][1], conflict="conflict")]))

        def observe():
            out, counts = sc.system_python(item, reply)
            out2, _c = sc.system_python(item, other)
            return ({pid: (e.get("conflict"), e.get("conflict_model"), e.get("written_by"), e.get("conflict_refused"))
                     for pid, e in sorted(out["proposals"].items())},
                    out2["proposals"]["P-A1-2"].get("conflict"), out2["proposals"]["P-A1-2"].get("conflict_model"),
                    counts["conflict_filled"], counts["conflict_refused"])
        want = ({"P-A1-1": ("no_conflict", None, None, None), "P-A1-2": ("not_stated", None, "python", None),
                 "P-A2-1": (None, "not_stated", None, "positions_on_record")}, "not_stated", "conflict", 1, 1)
        self.assertEqual(observe(), want)
        # What Python set agrees with the key's own label, which it never read.
        self.assertEqual(key["proposals"]["P-A1-2"]["conflict"], "not_stated")
        self.prove("conflict_not_stated_only_without_a_position", observe, want,
                   lambda: patch.object(sc, "applicable", lambda *a, **k: []))

    def test_02_state_by_structure(self):
        item, key = base.built()
        reply = parsed(item, dict(base.GOOD_REPLY, state=[{"article": "A1", "state": "closed"},
                                                          {"article": "A2", "state": "closed"}]))

        def observe():
            out, counts = sc.system_python(item, reply)
            return out["state"], out.get("state_model"), counts["state_refused"], counts["state_set"], counts["state_filled"]
        # A1: the persona's round-1 position makes binding possible, so the model's "closed" (neither binding nor
        # the structural bracketed) is refused, not replaced; A2: binding impossible, bracketed; A3 closed; A9
        # dropped from the indexes.
        want = ({"A2": "bracketed", "A3": "closed", "A9": "dropped"}, {"A1": "closed", "A2": "closed"}, 1, 1, 2)
        self.assertEqual(observe(), want)
        self.assertEqual({a: key["articles"][a]["state"] for a in ("A2", "A3", "A9")},
                         {"A2": "bracketed", "A3": "closed", "A9": "dropped"})
        self.prove("state_binding_left_to_the_model", observe, want,
                   lambda: patch.object(sc, "binding_possible", lambda item, aid: False))

    def test_03_alignment_needs_positions_on_both_sides(self):
        item, key = sc.build_item(copy.deepcopy(GAMMA))
        reply = parsed(item, dict(base.GOOD_REPLY, alignment=[
            {"article": "A1", "aligned": ["BETA", "GAMMA"], "opposed": ["GROUP1"]}]))

        def observe():
            out, counts = sc.system_python(item, reply)
            return out["alignment"], counts["alignment_refused"]
        want = ({"A1": {"aligned": ["BETA"], "opposed": ["GROUP1"]}}, 1)
        self.assertEqual(observe(), want)
        self.assertEqual(key["alignment"]["A1"]["GAMMA"], "not_stated")
        self.prove("alignment_party_without_positions_taken_off", observe, want,
                   lambda: patch.object(sc, "applicable", lambda *a, **k: ["a position"]))

    def test_04_python_pieces_are_not_advice(self):
        item, key = base.built()
        reply = parsed(item, dict(base.GOOD_REPLY, proposals=[base.GOOD_REPLY["proposals"][0]]))
        out, _c = sc.system_python(item, reply)

        def observe():
            kept, trail = sc.withhold(item, out, {"P-A1-1": "supported"})
            parts = sc.item_parts(item, key, kept, given=reply)
            return (sorted(kept["proposals"]), trail["given"], trail["kept"], trail["audit_missing"],
                    sorted(sc.checks(item, key, out, mode="key")), parts["M8"]["pieces"],
                    dict(parts["M10m"]))
        want = (["P-A1-1", "P-A1-2"], 1, 1, 0, ["P-A1-1"], 1, {"no_piece": 2})
        self.assertEqual(observe(), want)
        self.prove("python_pieces_never_audited_or_checked", observe, want,
                   lambda: patch.object(sc, "PYTHON", "not python"))

    def test_05_report_applies_the_step_to_the_system_only(self):
        item, key = base.built()
        reply = parsed(item, dict(base.GOOD_REPLY, proposals=[base.GOOD_REPLY["proposals"][0]]))
        iid = item["item_id"]
        answers = {"rows": [{"item_id": iid, "form": "advice", "group": g, "reply": reply, "audit": {}, "drops": {}}
                            for g in ("b1", "system_advice")]}

        def observe():
            rep = sc.report({iid: item}, {iid: key}, {"B1": (answers, "b1"), "system": (answers, "system_advice")},
                            resamples=50)
            per = rep["_per_item"]
            m1 = lambda arm, f: per[arm][iid].get(f, {})
            return (m1("system", "M1s"), m1("B1", "M1s"), m1("system", "M1m"), rep["system_python"].get("conflict_filled", 0))
        want = ({"('not_stated', 'not_stated')": 1}, {"('not_stated', 'no_answer')": 1},
                {"('no_conflict', 'no_conflict')": 1, "('conflict', 'no_answer')": 1}, 1)
        self.assertEqual(observe(), want)
        self.prove("report_system_arm_python_step", observe, want,
                   lambda: patch.object(sc, "system_python", lambda item, reply: (reply, Counter())))

    def test_06_one_entry_per_proposal(self):
        item, _key = base.built()
        good = json.dumps(base.GOOD_REPLY)
        props = base.GOOD_REPLY["proposals"]
        missing = json.dumps(dict(base.GOOD_REPLY, proposals=props[:2]))
        reordered = json.dumps(dict(base.GOOD_REPLY, proposals=[props[1], props[0], props[2]]))
        repeated = json.dumps(dict(base.GOOD_REPLY, proposals=props + [props[2]]))
        long_reasons = json.dumps(dict(base.GOOD_REPLY, proposals=[
            dict(props[0], reasons=["POS-%d" % (1 + n % 6) for n in range(na.REASONS_MAX + 1)])] + props[1:]))
        observe = lambda: [sd.accepts(na.advice_schema(item), t) for t in (good, missing, reordered, repeated, long_reasons)]
        want = [True, False, False, False, False]
        self.assertEqual(observe(), want)
        real = na.advice_schema

        def free_list(it):
            schema = real(it)
            node = dict(schema["keys"][0][1]["items"][0])
            node["keys"] = [["id", {"type": "enum", "values": sorted(na.item_ids(it)[2])}, True]] + node["keys"][1:]
            schema["keys"][0] = ["proposals", {"type": "array", "items": node}, True]
            return schema
        self.prove("advice_schema_one_entry_per_proposal", observe, want,
                   lambda: patch.object(na, "advice_schema", free_list))
        grammar = lambda: [sd.accepts({"type": "tuple", "items": [{"type": "enum", "values": ["a"]},
                                                                  {"type": "enum", "values": ["b"]}]}, t)
                           for t in ('["a","b"]', '["a"]', '["b","a"]', '["a","b","b"]', '[]')] + \
                          [sd.accepts({"type": "array", "items": {"type": "enum", "values": ["a"]}, "max_items": 2}, t)
                           for t in ('["a","a"]', '["a","a","a"]', '[]')] + \
                          [sd.accepts({"type": "tuple", "items": []}, "[]")]
        want_g = [True, False, False, False, False, True, False, True, True]
        self.assertEqual(grammar(), want_g)
        self.prove("grammar_tuple_and_max_items", grammar, want_g,
                   lambda: patch.object(sd.SchemaGrammar, "_index", lambda self, node: _loose_index(self, node)))


def _loose_index(grammar, node):
    """The neutralisation of test_06's grammar proof: a tuple compiled as a free array of its first item and
    max_items dropped, the grammar before this lane."""
    n = len(grammar.nodes)
    grammar.nodes.append(None)
    kind = node["type"]
    if kind == "object":
        compiled = {"type": "object", "keys": [(name, _loose_index(grammar, c), bool(r)) for name, c, r in node["keys"]]}
    elif kind == "tuple":
        compiled = {"type": "array", "items": _loose_index(grammar, node["items"][0] if node["items"]
                                                           else {"type": "enum", "values": ["x"]}), "max_items": None}
    elif kind == "array":
        compiled = {"type": "array", "items": _loose_index(grammar, node["items"]), "max_items": None}
    else:
        compiled = dict(node)
    grammar.nodes[n] = compiled
    return n


def check():
    Round1Checks.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(Round1Checks).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, no model and no item: the system's Python step "
                    "sets not_stated only where no persona position applies and refuses a not_stated where one does, "
                    "the structural state with binding left to the model, alignment only with positions on both sides, "
                    "Python's pieces never audited, checked or counted as advice, the step on the system arm alone with "
                    "M1's two parts, and the advice schema's one entry per proposal with its reasons capped"
                    % len(Round1Checks.evidence))


def main():
    status, detail = check()
    for proof in Round1Checks.evidence:
        print(proof["name"], proof["status"])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
