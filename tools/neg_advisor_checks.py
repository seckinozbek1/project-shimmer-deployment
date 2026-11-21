#!/usr/bin/env python3
"""Proofs for the negotiation advisor's scorer and forms (D-605, #262; NEG_ADVISOR_PLAN.md). No model, no
machine and no item: every proof runs on fixtures written here, invented, about no real negotiation.

1. A proposal's fate is kept, changed, removed or open by the 5-gram shares the plan fixes.
2. A party's proposal-specific positions take precedence over its article-level ones (conflict).
3. An article's state: binding before new, dropped from the two indexes, closed for agreed text.
4. Alignment is compared proposal by proposal; the approach targets and the configuration follow.
5. A missing or unparsed answer is no_answer, always a miss; Macro-F1 is over the key's classes only.
6. The system withholds a piece the audit calls unsupported or a check refuses, and keeps its trail.
7. Inside the system the checks never read the key: they read the reply's own state.
8. C-mandate refuses accepting a red-line conflict unless a trade gives it.
9. A claim is shown only when the BCa and jackknife bounds and the permutation p agree.
10. A1 is a claim only when its power record says so; otherwise never shown.
11. The scorer refuses without a committed opening line naming the set and configuration; a third opening only
    for the one set D-710 names (the old pilot of the opening ledger), never a fourth.
12. A prompts file holds every prompt to its rendering.
13. The system's audit prompts are derived from its advice, and answers hold each to the pass's SHA-256.
14. The run gives every piece of the system's advice its audit, with a stub backend.
15. The replay pass hands an advisor prompts file to its module.
16. A per-item file is refused inside the repository.
17. The games are scored by construction: Pareto over the whole option space, feasibility with the veto.
18. The judge's prompts carry no arm and no citation id; its entry ids are opaque.
19. The power simulation is lower for a system no better than B1.
20. The judge and the validator load Phi-4 (JUDGE's registry model), not the system auditor's Phi-3.5.
21. The cloud subset is the plan's seeded stratified draw, every part with a place, reading no label; the
    cloud arm is read on it alone, B1 and the system beside it on the same subset; the freeze names its SHA-256.
22. Bar line 4 and M9's validation follow the recorded kappas against the 0.60 floor.
23. The configuration binds the judge's prompts, the cloud subset and every checkpoint digest.
24. A cell under 5 items is its count alone; per-item rows only in the set folder; no form writes in the
    repository.
25. M9 counts a withheld counter only where the judge would have graded it.
26. Bar line 1: at least 10 points over B1 and the interval's lower bound above zero.
27. An item over the 24,000-token budget refuses the build before anything is written.
28. Every item carries its terms of use and attribution; SOURCE.md is in the frozen set's digest.
29. Each opening's power record carries that opening's alpha (0.025, then 0.0125, then 0.00625 for D-710's third
    opening of the old pilot alone, an indicator whatever its power).
30. score refuses a judge or validator pass that did not load JUDGE's registry model (Phi-3.5 in either).
31. validate-read binds its prompts and Phi-4, counts every position and refuses a missing answer row;
    score binds the validator's digest.
32. score's three cloud-subset refusals: bound, the plan's draw, answered exactly.
33. D-617: the validate form lists the article ids and asks for exactly one; a heading is not an id; an exact
    id is read; proposal and stance are asked byte for byte as in round 1; round 1's form still reads.
34. D-618: the freeze command passes the corpus list's accept-skipped kinds, as freeze_negotiation_set does.
35. The freeze's embedding on a rented machine: export, embed_records, and --vectors equal to the in-process
    freeze byte for byte (FREEZE.json and the cloud subset).
36. AM-1 (D-662): a single-class checker field at the bar only at 100 percent raw agreement, labelled; M9 alike.
37. AM-2 (D-665): red lines declared and held (from the fate), each arm's agreement with held, the source field.
38. The power record's code digest is of the scorer's LF bytes (#262 gap 2).
39. main() driven through freeze --export-records and --vectors equals the in-process freeze (#262 gap 3).
40. A frozen set is never built again; its keys are read as they are (D-693).
41. An unagreed article numbering two or more options with no bracket is refused visibly, never split by guess
    (#281 gap 8).
42. AM-3: M10, open-point detection, indicator only: movable (open, changed) or settled (kept, removed) from
    the key's fate, movable on a counter and settled on an accept or reject, no stance a miss counted by its
    reason, Macro-F1 over the two classes with M1's interval per arm, the system-minus-B1 difference, never
    in the claims or the bar.

Each proof follows scripts/effect_proof.py: neutralise, fail, restore, pass. A neutralisation changes the
property itself (a declared constant, the data the rule reads, or the form as first written), never the
function under test.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from collections import Counter
import io
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from effect_proof import prove_effect  # noqa: E402
import neg_advisor as na  # noqa: E402
import reread_replies as rr  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sc = _load("score_neg_advisor", ROOT / "tools" / "score_neg_advisor.py")

A1_TEXT = ("The parties shall cooperate on surveillance.\n\n"
           "[Each party shall report all outbreak data within seventy two hours of detection] "
           "[Each party should share outbreak data when it judges appropriate]")
A1_NEXT = "The parties shall cooperate on surveillance. Each party shall report all outbreak data within seventy two hours of detection."
A2_TEXT = "A fund is established.\n\n[Contributions shall be mandatory for developed parties and assessed annually]"
A2_NEXT = "A fund is established. Contributions shall be mandatory for developed parties and reviewed every five years."
A3_TEXT = "For the purposes of this agreement the terms used have their ordinary meaning."

BUILD = {
    "schema": "neg-advisor-build-v1", "item_id": "fx-k2-alpha", "part": "P", "process": "fixture process",
    "round": 2, "synthetic": False, "post_cutoff": False,
    na.TERMS_FIELD: "fixture terms of use, invented", "attribution": "fixture attribution, invented",
    "persona": {"id": "ALPHA", "kind": "single"}, "red_lines": ["POS-2"],
    "parties": [{"id": "ALPHA", "kind": "single"}, {"id": "BETA", "kind": "single"}, {"id": "GROUP1", "kind": "coalition"}],
    "articles": [{"id": "A1", "title": "Surveillance", "text": A1_TEXT},
                 {"id": "A2", "title": "Finance", "text": A2_TEXT},
                 {"id": "A3", "title": "Definitions", "text": A3_TEXT, "agreed": True}],
    "round_index": [{"id": "A1", "title": "Surveillance"}, {"id": "A2", "title": "Finance"},
                    {"id": "A3", "title": "Definitions"}],
    "previous_index": [{"id": "A1", "title": "Surveillance"}, {"id": "A2", "title": "Finance"},
                       {"id": "A3", "title": "Definitions"}, {"id": "A9", "title": "Old annex"}],
    "next_articles": {"A1": A1_NEXT, "A2": A2_NEXT, "A3": A3_TEXT},
    "positions": [
        {"id": "POS-1", "party": "ALPHA", "round": 1, "article": "A1", "proposal": 1, "stance": "support",
         "quote": "We support reporting within a fixed time.", "source": "fixture 1"},
        {"id": "POS-2", "party": "ALPHA", "round": 2, "article": "A2", "proposal": None, "stance": "oppose",
         "quote": "We cannot accept mandatory contributions.", "source": "fixture 2"},
        {"id": "POS-3", "party": "BETA", "round": 2, "article": "A1", "proposal": 1, "stance": "support",
         "quote": "A fixed reporting time is essential.", "source": "fixture 3"},
        {"id": "POS-4", "party": "BETA", "round": 2, "article": "A2", "proposal": None, "stance": "oppose",
         "quote": "Contributions must stay voluntary.", "source": "fixture 4"},
        {"id": "POS-5", "party": "GROUP1", "round": 2, "article": "A1", "proposal": 1, "stance": "oppose",
         "quote": "A fixed time is not workable for us.", "source": "fixture 5"},
        {"id": "POS-6", "party": "GROUP1", "round": 1, "article": "A2", "proposal": None, "stance": "support",
         "quote": "Assessed contributions are the only predictable source.", "source": "fixture 6"}],
    "trades_on_record": [{"id": "T-1", "give": ["A1", 1], "get": ["A2", 1], "round": 1}],
}

GAME = {
    "schema": "neg-advisor-build-v1", "item_id": "fx-game", "part": "G", "process": "fixture game", "round": 1,
    na.TERMS_FIELD: "fixture terms of use, invented", "attribution": "fixture attribution, invented",
    "persona": {"id": "P1", "kind": "single"},
    "parties": [{"id": "P1", "kind": "single"}, {"id": "P2", "kind": "single"}, {"id": "P3", "kind": "single"}],
    "game": {"issues": [{"id": "I1", "options": ["a", "b"]}, {"id": "I2", "options": ["x", "y"]}],
             "tables": {"P1": {"I1": {"a": 10, "b": 0}, "I2": {"x": 2, "y": 0}},
                        "P2": {"I1": {"a": 0, "b": 5}, "I2": {"x": 5, "y": 0}},
                        "P3": {"I1": {"a": 3, "b": 3}, "I2": {"x": 3, "y": 4}}},
             "thresholds": {"P1": 5, "P2": 4, "P3": 5}, "required": 2, "veto": ["P1"],
             "last_deal": {"I1": "b", "I2": "y"}},
}

GOOD_REPLY = {
    "proposals": [
        {"id": "P-A1-1", "conflict": "no_conflict", "stance": "accept", "reasons": ["POS-1"]},
        {"id": "P-A1-2", "conflict": "not_stated", "stance": "reject", "reasons": ["PAR-2"]},
        {"id": "P-A2-1", "conflict": "conflict", "stance": "counter",
         "wording": "Contributions shall be mandatory for developed parties and reviewed every five years",
         "reasons": ["POS-2", "PAR-4"]}],
    "trades": [{"give": "P-A1-1", "get": "P-A2-1"}],
    "approach": ["BETA"],
    "alignment": [{"article": "A1", "aligned": ["BETA"], "opposed": ["GROUP1"]},
                  {"article": "A2", "aligned": ["BETA"], "opposed": ["GROUP1"]}],
    "state": [{"article": "A1", "state": "bracketed"}, {"article": "A2", "state": "bracketed"},
              {"article": "A3", "state": "closed"}, {"article": "A9", "state": "dropped"}],
}


def WORDS(user):
    """A stand-in token count for the fixtures: whitespace words. The real count is Qwen's own tokenizer
    (neg_advisor.token_counter); it is not loaded here because importing transformers and the tokenizer
    takes about 53 s on the laptop (measured 13 November 2026) and the gate's machine may not cache it. Stated
    limit: the proofs show the budget rule, not the tokenizer's count."""
    return len(user.split())


# The validate template as committed at ad9a5c8a (form version 1, round 1's), and its SHA-256 there.
VALIDATE_V1_SHA256 = "ab63a780e232d04392e0946030273198dbadd3f533b4ddd849f6181ca9820aad"
VALIDATE_V1_TEMPLATE = 'A position quote from a negotiation record has been mapped to an article of the negotiating text.\n\nTHE ARTICLES:\n{articles}\n\nTHE QUOTE, by {party}, round {round}:\n{quote}\n\nTHE MAPPING TO CHECK: article {article}, proposal {proposal}, stance {stance}.\n\nReply with one JSON object and nothing else: {"article": the article id the quote is about, "proposal": the proposal\'s number within that article or null for the whole article, "stance": "support" or "oppose" or "accept"}.'
# ad9a5c8a's validate_read on test_33's round-1 answers: (kappa to 12 places, agreement).
ROUND1_PINNED = (0.6, 4)


PHI4 = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]["JUDGE"]["model"]


def built(b=BUILD):
    return sc.build_item(copy.deepcopy(b))


def reply_of(item, value=GOOD_REPLY):
    return na.parse_advice(json.dumps(value), item)


@contextmanager
def setdir(builds=(BUILD,)):
    with tempfile.TemporaryDirectory(prefix="negadv_") as td:
        root = Path(td) / "set"
        for b in builds:
            (root / "build" / b["item_id"]).mkdir(parents=True)
            (root / "build" / b["item_id"] / "build.json").write_text(json.dumps(b), encoding="utf-8")
            (root / "build" / b["item_id"] / "SOURCE.md").write_text("fixture source, invented" + chr(10), encoding="utf-8")
        sc.build_set(root, count=WORDS)
        yield root


class FakeBackend:
    def __init__(self, reader, context):
        self.reader, self.context = reader, context

    def prepare(self):
        return {"model_id": "fake/" + self.reader["agent"], "digest": "0" * 64}

    def max_context(self):
        return 32768

    def count_prompt(self, _system, user):
        return len(user.split())

    def generate(self, _system, user, _n):
        if user.startswith("A negotiation advisor gave"):
            return {"text": "unsupported" if "P-A1-2" in user else "supported"}
        return {"text": json.dumps(GOOD_REPLY)}

    def generate_constrained(self, _system, user, n, schema, source):
        # D-672: the schema groups' path; the stand-in writes the reply the schema admits.
        out = self.generate(_system, user, n)
        return dict(out, constraint={"name": "json-schema-contract", "source": source, "interventions": 0})

    def choose(self, _system, user, answers):
        # D-672: the choice groups' path; the stand-in's probabilities put 0.9 on the answer it means.
        wanted = "unsupported" if "P-A1-2" in user else "supported" if user.startswith("A negotiation advisor gave") else "2"
        rows = [{"label": a["label"], "surface": a["surface"], "token_id": k,
                 "probability": 0.9 if a["label"] == wanted else 0.1 / (len(answers) - 1)} for k, a in enumerate(answers)]
        return {"decision": {"schema": "choice-decision-v1", "answers": rows, "declared_mass": 1.0}}


def fake_reader(group, allowance):
    return {"backend": group["backend"], "agent": group["agent"], "model_id": "fake/" + group["agent"],
            "decoding": {"status": "fixture", "source": "fixture", "sha256": "0" * 64, "kwargs": {}},
            "max_new_tokens": allowance}


class _AnyLine:
    """A stand-in opening pattern that finds an opening line for k=1, set a*64, config c*64 in any text."""
    def finditer(self, _text):
        class M:
            def group(self, n):
                return {1: "1", 2: "a" * 64, 3: "c" * 64}[n]
        return [M()]


@contextmanager
def _game_option(game, issue, option, scores):
    """A game with one more option on an issue, scored per party: restored on exit."""
    saved = copy.deepcopy(game)
    try:
        next(i for i in game["issues"] if i["id"] == issue)["options"].append(option)
        for party, value in scores.items():
            game["tables"][party][issue][option] = value
        yield
    finally:
        game.clear()
        game.update(saved)


@contextmanager
def _replace(values, index, value):
    """A list with one entry replaced, restored on exit."""
    saved = values[index]
    values[index] = value
    try:
        yield
    finally:
        values[index] = saved


@contextmanager
def _extend(values, more):
    """A list with more entries, restored on exit."""
    saved = list(values)
    values.extend(more)
    try:
        yield
    finally:
        values[:] = saved

class NegAdvisorChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        NegAdvisorChecks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    def test_01_fate(self):
        observe = lambda: {p: r["fate"] for p, r in built()[1]["proposals"].items()}
        self.assertEqual(observe(), {"P-A1-1": "kept", "P-A1-2": "removed", "P-A2-1": "changed"})
        self.assertEqual(sc.fate("[option one stays open in the next text]", "Text [option one stays open in the next text]"), "open")
        self.prove("fate_by_the_plans_shares", observe, observe(), lambda: patch.object(sc, "KEPT_SHARE", 0.5))

    def test_02_conflict_precedence(self):
        observe = lambda: {p: (r["conflict"], r["red_line"], r["advanced"], r["supported_earlier"])
                           for p, r in built()[1]["proposals"].items()}
        self.assertEqual(observe(), {"P-A1-1": ("no_conflict", False, "advanced", True),
                                     "P-A1-2": ("not_stated", False, None, False),
                                     "P-A2-1": ("conflict", True, None, False)})
        real = sc.applicable
        self.prove("proposal_positions_first", observe, observe(),
                   lambda: patch.object(sc, "applicable", lambda ps, party, art, n: [p for p in ps if p["party"] == party and p["article"] == art]))
        del real

    def test_03_state(self):
        b = copy.deepcopy(BUILD)
        b["positions"].append({"id": "POS-7", "party": "ALPHA", "round": 1, "article": "A3", "proposal": None,
                               "stance": "accept", "quote": "We accept the definitions.", "source": "fixture 7"})
        observe = lambda: {a: r["state"] for a, r in sc.build_item(copy.deepcopy(b))[1]["articles"].items()}
        self.assertEqual(observe(), {"A1": "bracketed", "A2": "bracketed", "A3": "binding", "A9": "dropped"})
        real = sc.state_label
        self.prove("binding_before_the_rest", observe, observe(),
                   lambda: patch.object(sc, "state_label", lambda aid, k, prev, agreed, has, ps, persona:
                                        real(aid, k, prev, agreed, has, [], persona)))

    def test_04_alignment_configuration(self):
        observe = lambda: (built()[1]["alignment"], built()[1]["approach_targets"], built()[1]["configuration"])
        self.assertEqual(observe(), ({"A1": {"BETA": "aligned", "GROUP1": "opposed"},
                                      "A2": {"BETA": "aligned", "GROUP1": "opposed"},
                                      "A3": {"BETA": "not_stated", "GROUP1": "not_stated"}}, ["BETA"], "one_vs_group"))
        self.prove("alignment_by_proposal", observe, observe(),
                   lambda: patch.object(sc, "_sign", lambda stances: 1 if stances else 0))
        b = copy.deepcopy(BUILD)
        b["positions"][3]["stance"] = "support"   # BETA now opposes the persona on A2
        b["positions"][5]["stance"] = "oppose"    # GROUP1 now aligns on A2
        shifted = lambda: sc.build_item(copy.deepcopy(b))[1]["configuration"]
        self.assertEqual(shifted(), "shifting")
        self.prove("shifting_alignment_computed", shifted, "shifting", lambda: patch.object(sc, "SHIFT_JACCARD", 0.0))

    def test_05_no_answer_and_macro_f1(self):
        item, key = built()
        partial = copy.deepcopy(GOOD_REPLY)
        partial["proposals"] = partial["proposals"][:1]
        observe = lambda: round(sc.macro_f1(sc.item_parts(item, key, reply_of(item, partial))["M1"]), 6)
        # key classes: no_conflict (hit), not_stated (no_answer), conflict (no_answer): (1 + 0 + 0) / 3
        self.assertEqual(observe(), round(1 / 3, 6))
        self.assertEqual(sc.macro_f1(sc.item_parts(item, key, None)["M1"]), 0.0)
        # Neutralised: a missing answer read as a key class (here `conflict`) instead of no_answer.
        self.prove("missing_is_no_answer_always_wrong", observe, observe(), lambda: patch.object(sc, "NO_ANSWER", "conflict"))

    def test_06_withholding(self):
        item, _key = built()
        audit = {"P-A1-1": "supported", "P-A1-2": "unsupported", "P-A2-1": "supported"}
        observe = lambda: (sorted(sc.withhold(item, reply_of(item), audit)[0]["proposals"]),
                           sc.withhold(item, reply_of(item), audit)[1]["audit_unsupported"])
        self.assertEqual(observe(), (["P-A1-1", "P-A2-1"], 1))
        # Neutralised: the withholding answer is another one than the audit's `unsupported`.
        self.prove("unsupported_advice_withheld", observe, observe(),
                   lambda: patch.object(sc, "WITHHELD_AUDIT", "cannot_tell"))
        # D-878 (AM-4): marked keeps the audit-unsupported piece as written, marked, and counts it.
        marked = lambda: (sorted(sc.withhold(item, reply_of(item), audit, marked=True)[0]["proposals"]),
                          sc.withhold(item, reply_of(item), audit, marked=True)[0]["proposals"]["P-A1-2"].get("audit"),
                          sc.withhold(item, reply_of(item), audit, marked=True)[1].get("audit_marked"))
        self.assertEqual(marked(), (["P-A1-1", "P-A1-2", "P-A2-1"], "unsupported", 1))
        self.assertFalse(sc.audit_marked_on({}))
        self.assertTrue(sc.audit_marked_on({sc.AUDIT_KEEP_KEY: True}))
        value = copy.deepcopy(GOOD_REPLY)
        value["state"][1]["state"] = "closed"     # the reply's own state: its counter on A2 fails C-closed
        refused = lambda: (sorted(sc.withhold(item, reply_of(item, value), {})[0]["proposals"]),
                           sc.withhold(item, reply_of(item, value), {})[1]["C-closed"])
        self.assertEqual(refused(), (["P-A1-1", "P-A1-2"], 1))
        self.prove("refused_advice_withheld", refused, refused(),
                   lambda: patch.dict(value["state"][1], {"state": "bracketed"}))

    def test_07_system_mode_reads_no_key(self):
        item, key = built()
        value = copy.deepcopy(GOOD_REPLY)
        value["state"][1]["state"] = "closed"     # the reply itself calls A2 closed, the key says bracketed
        r = reply_of(item, value)
        # The real key is handed to both modes: the system mode must read the reply's state, not the key's.
        observe = lambda: (sc.checks(item, key, r, mode="system")["P-A2-1"]["C-closed"],
                           sc.checks(item, key, r, mode="key")["P-A2-1"]["C-closed"])
        self.assertEqual(observe(), (False, True))
        # Neutralised: the system mode is no longer one of the modes that never read the key.
        self.prove("system_checks_never_read_the_key", observe, observe(), lambda: patch.object(sc, "KEYLESS_MODES", ()))

    def test_08_mandate(self):
        item, key = built()
        value = copy.deepcopy(GOOD_REPLY)
        value["proposals"][2] = {"id": "P-A2-1", "conflict": "conflict", "stance": "accept", "reasons": ["POS-2"]}
        value["trades"] = []
        observe = lambda: (sc.checks(item, key, reply_of(item, value), mode="key")["P-A2-1"]["C-mandate"],
                           sc.checks(item, key, reply_of(item, dict(value, trades=[{"give": "P-A2-1", "get": "P-A1-1"}])),
                                     mode="key")["P-A2-1"]["C-mandate"])
        self.assertEqual(observe(), (False, True))
        real_key = copy.deepcopy(key)
        real_key["proposals"]["P-A2-1"]["red_line"] = False
        self.prove("red_line_accept_refused", observe, observe(),
                   lambda: patch.dict(key["proposals"], {"P-A2-1": real_key["proposals"]["P-A2-1"]}))

    def test_09_claim_needs_all_three(self):
        def parts(hit, n, items):
            return [Counter({("x", "x"): hit, ("x", "y"): n - hit, ("y", "y"): hit, ("y", "x"): n - hit}) for _ in range(items)]
        strong, weak = parts(9, 10, 12), parts(5, 10, 12)
        observe = lambda: sc.test_claim("M1", strong, weak, 1, resamples=400)["shown"]
        self.assertTrue(observe())
        self.assertFalse(sc.test_claim("M1", weak, weak, 1, resamples=400)["shown"])
        self.prove("claim_needs_the_permutation_too", observe, True,
                   lambda: patch.object(sc.sn, "permutation_p", lambda *a, **k: 1.0))

    def test_10_a1_needs_its_power(self):
        item, key = built()
        b2 = copy.deepcopy(BUILD)
        b2["item_id"] = "fx-k2-beta"
        items = {"fx-k2-alpha": item, "fx-k2-beta": sc.build_item(b2)[0]}
        keys = {"fx-k2-alpha": key, "fx-k2-beta": sc.build_item(b2)[1]}
        good = {"rows": [{"form": "advice", "group": "system_advice", "item_id": i, "reply": reply_of(items[i]),
                          "audit": {}} for i in items]}
        bad = {"rows": [{"form": "advice", "group": "b1", "item_id": i, "reply": None} for i in items]}
        low = {"power_by_icc": {"0.2": 0.3, "0.5": 0.2}}
        observe = lambda: sc.report(items, keys, {"system": (good, "system_advice"), "B1": (bad, "b1")},
                                    power=low, resamples=50)["claims"]["A1"]["status"]
        self.assertEqual(observe(), "indicator")
        self.prove("a1_indicator_below_its_power", observe, "indicator",
                   lambda: patch.object(sc, "claim_status", lambda record: "claim"))

    def scoring_inputs(self, keys):
        """A refuse() call's inputs that pass, built on the fixture keys."""
        subset = json.dumps(sc.cloud_subset(keys)).encode("utf-8")
        subset_sha = sc.hashlib.sha256(subset).hexdigest()
        freeze = {"set_sha256": "a" * 64, "dry_run": False, "embedding": {"model": "m"}, "cloud_subset_sha256": subset_sha}
        power_text = json.dumps({"set_sha256": "a" * 64, "sims": 1000, "k": 1, "alpha": 0.025, "code_sha256": sc.code_sha256()})
        digests = {g: sc._sha("checkpoint " + g) for g in ("b1", "system_advice", "system_audit", "judge", "validate")}
        conf = {f: "x" for f in sc.CONFIG_FIELDS}
        conf.update(power_record_sha256=sc._sha(power_text), b1_prompts_sha256="b", system_prompts_sha256="s",
                    cloud_prompts_sha256="c", judge_prompts_sha256="j", validate_prompts_sha256="v",
                    cloud_subset_sha256=subset_sha, checkpoint_digests=digests)
        # Real-shaped model ids, as the passes record them (the producer's base, the active auditor, Phi-4).
        ids = {"b1": "unsloth/Qwen2.5-7B-Instruct-bnb-4bit", "system_advice": "unsloth/Qwen2.5-7B-Instruct-bnb-4bit",
               "system_audit": "unsloth/Phi-3.5-mini-instruct-bnb-4bit", "judge": PHI4, "validate": PHI4}
        model = lambda g: {g: {"model_id": ids[g], "digest": digests[g]}}
        items = json.loads(subset)["items"]
        v = {"schema": rr.ADVISOR_SCHEMA}
        arms = {"B1": dict(v, prompts_sha256="b", models=model("b1")),
                "system": dict(v, prompts_sha256="s", models=dict(model("system_advice"), **model("system_audit"))),
                "cloud": dict(v, prompts_sha256="c", subset_sha256=subset_sha, rows=[{"item_id": i} for i in items])}
        judge = dict(v, prompts_sha256="j", models=model("judge"))
        validation = {"kappa": 0.8, "prompts_sha256": "v", "models": model("validate")}
        line = "neg-advisor opening k=1 set=%s config=%s" % ("a" * 64, "c" * 64)
        return dict(freeze=freeze, configuration=conf, configuration_sha256="c" * 64, k=1, power=json.loads(power_text),
                    power_text=power_text, arms=arms, judge=judge, subset_bytes=subset, keys=keys, openings_text=line,
                    validation=validation)

    def test_11_refusals(self):
        kw = self.scoring_inputs({"fx-k2-alpha": built()[1]})
        self.assertIsNone(sc.refuse(**kw))
        observe = lambda: sc.refuse(**dict(kw, openings_text="no line here"))
        self.assertEqual(observe(), "no committed opening line names k=1, this set and this configuration")
        self.assertIsNotNone(sc.refuse(**dict(kw, arms=dict(kw["arms"], cloud=dict(kw["arms"]["cloud"], prompts_sha256="z")))))
        # Neutralised: the opening line's own form loosened so that any text names the opening.
        self.prove("no_score_without_an_opening", observe, observe(),
                   lambda: patch.object(sc, "_OPENING", _AnyLine()))
        # D-710: the one set with a third opening is the old pilot, the set of the ledger's first neg-advisor line.
        ledger = (ROOT / "docs" / "loop" / "HELDOUT_OPENINGS.md").read_text(encoding="utf-8")
        pilot = next(m.group(2) for m in sc._OPENING.finditer(ledger) if m.group(1) == "1")
        self.assertEqual(sc.EXTRA_OPENINGS, {pilot: 3})
        p3, p4 = self.pilot_inputs(kw, 3), self.pilot_inputs(kw, 4)
        openings = lambda: (sc.refuse(**dict(kw, k=3)), sc.refuse(**p3), sc.refuse(**p4))
        want = ("opening 3: at most 2 openings for this set", None, "opening 4: at most 3 openings for this set")
        self.assertEqual(openings(), want)
        # Neutralised: the third opening granted to every set (any other set's k=3 then passes the cap).
        self.prove("third_opening_for_the_pilot_alone", openings, want,
                   lambda: patch.object(sc, "MAX_OPENINGS", 3))
        # Neutralised: the pilot's grant withdrawn (its k=3 then refused).
        self.prove("third_opening_granted_to_the_pilot", openings, want,
                   lambda: patch.dict(sc.EXTRA_OPENINGS, clear=True))

    def pilot_inputs(self, kw, k):
        """refuse() inputs on D-710's pilot set at opening k: its freeze, its power record at opening k's alpha,
        the configuration binding that record, and its committed opening line."""
        pilot = next(iter(sc.EXTRA_OPENINGS))
        text = json.dumps(dict(json.loads(kw["power_text"]), set_sha256=pilot, k=k, alpha=sc.opening_alpha(k)))
        return dict(kw, k=k, freeze=dict(kw["freeze"], set_sha256=pilot), power=json.loads(text), power_text=text,
                    configuration=dict(kw["configuration"], power_record_sha256=sc._sha(text)),
                    openings_text="neg-advisor opening k=%d set=%s config=%s" % (k, pilot, "c" * 64))

    def test_12_prompts_held_to_rendering(self):
        with setdir() as root, tempfile.TemporaryDirectory() as td:
            path = Path(td) / "p.json"
            na.build(root, "advice", ["b1", "system_advice"], path)
            value = json.loads(path.read_text(encoding="utf-8"))
            value["prompts"][0]["item"]["persona"]["id"] = "SOMEONE_ELSE"
            tampered = Path(td) / "t.json"
            tampered.write_text(json.dumps(value), encoding="utf-8")

            def observe():
                try:
                    na.load_prompts(tampered)
                    return "loaded"
                except ValueError as exc:
                    return str(exc).split(":")[0]
            self.assertEqual(observe(), "a prompt is not its template's rendering")
            # Neutralised: the stored user turn and its digest are no longer held to the rendering.
            self.prove("prompt_held_to_its_rendering", observe, observe(),
                       lambda: patch.object(na, "HELD_FIELDS", ("system", "max_new_tokens")))

    def test_13_audit_derived_and_held(self):
        with setdir() as root, tempfile.TemporaryDirectory() as td:
            path = Path(td) / "p.json"
            value = na.build(root, "advice", ["system_advice"], path)
            p = value["prompts"][0]
            text = json.dumps(GOOD_REPLY)
            derived = na.audit_prompts(value["config"], p, text)
            self.assertEqual([d["proposal_id"] for d in derived], ["P-A1-1", "P-A1-2", "P-A2-1"])
            measured = {d["prompt_id"]: ("0" * 64 if d["proposal_id"] == "P-A1-2" else d["user_sha256"], "supported")
                        for d in derived}

            def observe():
                try:
                    na.answers_from_texts(value, {p["prompt_id"]: text}, measured_audits=measured)
                    return "accepted"
                except ValueError:
                    return "refused"
            self.assertEqual(observe(), "refused")
            real = na.audit_prompts
            self.prove("audit_prompt_held_to_its_sha", observe, "refused",
                       lambda: patch.object(na, "audit_prompts", lambda config, prompt, text: [
                           dict(d, user_sha256=measured[d["prompt_id"]][0]) for d in real(config, prompt, text)]))

    def test_14_run_audits_every_piece(self):
        with setdir() as root, tempfile.TemporaryDirectory() as td:
            path = Path(td) / "p.json"
            na.build(root, "advice", ["b1", "system_advice"], path)

            def observe():
                with tempfile.TemporaryDirectory() as out:
                    result = na.run(path, Path(out) / "pass", backend_factory=FakeBackend, reader_for=fake_reader, run_id="fx")
                    ans = na.answers(path, Path(out) / "pass")
                    audit = next(r for r in ans["rows"] if r["group"] == "system_advice")["audit"]
                    return result["derived"], audit
            self.assertEqual(observe(), (3, {"P-A1-1": "supported", "P-A1-2": "unsupported", "P-A2-1": "supported"}))
            self.prove("every_piece_audited", observe, observe(),
                       lambda: patch.object(na, "audit_prompts", lambda config, prompt, text: []))

    def test_15_replay_hook(self):
        rp = _load("replay_prompts", ROOT / "benchmark" / "baselines" / "replay_prompts.py")
        with setdir() as root, tempfile.TemporaryDirectory() as td:
            path = Path(td) / "p.json"
            na.build(root, "advice", ["b1"], path)

            def observe():
                try:
                    return len(rp.load_prompts(path))
                except ValueError:
                    return "refused"
            self.assertEqual(observe(), 1)
            self.prove("replay_hands_the_file_to_its_module", observe, 1,
                       lambda: patch.object(rp, "is_neg_advisor", lambda p: False))

    def test_16_per_item_outside(self):
        def observe():
            try:
                sc.outside_repository(ROOT / "output" / "per_item.json")
                return "accepted"
            except ValueError:
                return "refused"
        self.assertEqual(observe(), "refused")
        self.prove("per_item_rows_never_in_the_repository", observe, "refused",
                   lambda: patch.object(sc, "ROOT", Path(tempfile.gettempdir()) / "negadv_elsewhere"))

    def test_17_games(self):
        item, key = sc.build_item(copy.deepcopy(GAME))
        game = key["game"]
        observe = lambda: dict(sc.game_part(game, "P1", {"deal": {"I1": "a", "I2": "x"},
                                                         "trades": [{"give": "I2", "get": "I1"}]}))
        # P1 scores 12 (>= 5), P2 5 (>= 4), P3 6 (>= 5): feasible with the veto P1; nothing dominates it;
        # the trade gives the lighter issue for the heavier; 12 beats the last deal's 0.
        self.assertEqual(observe(), {"items": 1, "G1": 1, "G2": 1, "G4": 1, "trades": 1, "G3": 1})
        self.assertEqual(set(item["game"]["persona_table"]), {"I1", "I2"})
        self.assertNotIn("P2", json.dumps(item["game"]))
        # Pareto over the whole option space: an option that is better for every party dominates the deal.
        better = {"P1": 9, "P2": 9, "P3": 9}
        self.prove("pareto_over_the_whole_option_space", observe, observe(), lambda: _game_option(game, "I2", "z", better))
        # Feasibility needs the veto parties: with P2 a veto party, a deal P2 rejects is not feasible.
        vetoed = dict(game, veto=["P2"])
        veto = lambda: sc.game_part(vetoed, "P1", {"deal": {"I1": "a", "I2": "y"}, "trades": []})["G1"]
        self.assertEqual(veto(), 0)
        self.prove("feasible_needs_the_veto_parties", veto, 0, lambda: patch.dict(vetoed, {"veto": []}))
        # A game reply (deal and trades, no proposals) passes the withholding as it is: judge-prompts and
        # score call withhold on every system reply (role N session 18 met KeyError 'proposals' here).
        game_reply = {"deal": {"I1": "a", "I2": "x"}, "trades": [{"give": "I2", "get": "I1"}]}

        def kept_game():
            try:
                kept, trail = sc.withhold(item, game_reply, {})
            except KeyError as exc:
                return f"KeyError {exc}"
            return kept is game_reply, trail["given"]
        self.assertEqual(kept_game(), (True, 0))
        # Neutralised: the item read as no game takes the proposals path and fails on the game reply.
        self.prove("game_reply_passes_withholding", kept_game, (True, 0), lambda: patch.dict(item, {"game": None}))

    def test_18_judge_blind(self):
        item, key = built()
        value = copy.deepcopy(GOOD_REPLY)
        value["proposals"][2]["wording"] += " as POS-2 and PAR-4 ask, unlike P-A1-2"
        replies = {"system": {"fx-k2-alpha": reply_of(item, value)}, "B1": {"fx-k2-alpha": reply_of(item, value)}}
        config = na.load_config()
        entries = lambda: na.judge_entries({"fx-k2-alpha": item}, {"fx-k2-alpha": key}, replies, na.mandate_text)
        self.assertEqual(len(entries()), 2)
        self.assertFalse(any(arm in na.render_judge(config, e) for e in entries() for arm in ("system", "B1", "cloud")))
        cites = lambda: sorted({bool(re.search(r"\b(?:PAR|POS)-\d|P-A\d", na.render_judge(config, e))) for e in entries()})
        self.assertEqual(cites(), [False])
        # Neutralised: the citation-id pattern matches nothing, so the counter's cited ids reach the judge.
        self.prove("judge_sees_no_citation_id", cites, [False], lambda: patch.object(na, "CITATION_ID", re.compile(r"(?!)")))
        opaque = lambda: sorted({e["entry_id"].startswith(e["arm"]) for e in entries()})
        self.assertEqual(opaque(), [False])
        # Neutralised: the entry id no longer hashed, so it spells the arm.
        self.prove("judge_entry_ids_opaque", opaque, [False], lambda: patch.object(na, "_sha", lambda text: text))

    def test_18b_judge_grade_is_the_leading_digit(self):
        # Role N session 19 (15 Nov): all 12 Phi-4 replies opened with the grade digit and went on with text.
        cases = {"2": 2, " 1" + chr(10): 1, "0": 0, "2 The counter keeps": 2, "1.": 1, "0, because": 0,
                 "12": None, "3": None, "Grade: 2": None, "": None, None: None}
        read = lambda: {repr(k): na.parse_judge(k) for k in cases}
        want = {repr(k): v for k, v in cases.items()}
        self.assertEqual(read(), want)
        # Neutralised: the old rule, a bare digit only, grades nothing that goes on after the digit.
        bare = lambda text: (int(text.strip()) if isinstance(text, str) and text.strip() in ("0", "1", "2") else None)
        self.prove("judge_grade_is_the_leading_digit", read, want, lambda: patch.object(na, "parse_judge", bare))

    def test_18c_numeric_article_id_is_read_as_its_text(self):
        # Role N session 23 (15 Nov): the system wrote 7 article ids as JSON numbers equal to a known id; the
        # parser compared them with the string ids and dropped them. A number is read as its text, as `_ids` does.
        item, _key = built()
        item["articles"][0]["id"] = "7"
        # #262 gap 1: a numeric proposal id too, so the proposal path cannot be reverted alone unseen.
        item["articles"][1]["proposals"][0]["id"] = "12"
        value = {"proposals": [{"id": 12, "conflict": "conflict", "stance": "reject", "reasons": []},
                               {"id": True, "conflict": "conflict", "stance": "reject", "reasons": []}],
                 "trades": [], "approach": [],
                 "alignment": [{"article": 7, "aligned": [], "opposed": []}],
                 "state": [{"article": 7, "state": "bracketed"}, {"article": True, "state": "closed"},
                           {"article": 7.0, "state": "closed"}]}
        read = lambda: (lambda r: (r["state"], sorted(r["alignment"]), sorted(r["proposals"]),
                                   r["proposals"].get("12", {}).get("stance")))(na.parse_advice(json.dumps(value), item))
        want = ({"7": "bracketed"}, ["7"], ["12"], "reject")
        self.assertEqual(read(), want)
        # Neutralised: the old rule, an id compared as it came, drops the numeric article.
        self.prove("numeric_article_id_is_read_as_its_text", read, want,
                   lambda: patch.object(na, "_one_id", lambda v: v))

    def test_18d_no_answer_dropped_for_its_form(self):
        # D-663 (standing order 82): the good reply written in the forms a model writes (a fence, case, spaces,
        # quotes, emphasis, a trailing point, a list of one, one value for a list), after an example object,
        # is read by the score-time re-reader (tools/reread_replies.py) as the run's parser reads the good reply;
        # the example object before it is counted several_objects_last_read, not read (the LAST object, lead 18:57).
        item, _key = built()
        form = {"proposals": [
                    {"id": " p-a1-1 ", "conflict": "No_Conflict.", "stance": "**Accept**", "reasons": "POS-1"},
                    {"id": ["P-A1-2"], "conflict": '"not stated"', "stance": "REJECT", "reasons": ["par-2"]},
                    dict(GOOD_REPLY["proposals"][2], stance="Counter,")],
                "trades": [{"give": "P-A1-1", "get": "P-A2-1"}], "approach": "beta",
                "alignment": [{"article": "a1", "aligned": "BETA", "opposed": ["group1"]},
                              {"article": "A2.", "aligned": ["BETA"], "opposed": "GROUP1"}],
                "state": [{"article": "A1", "state": "Bracketed"}, {"article": " A2", "state": "BRACKETED"},
                          {"article": "A3", "state": "'closed'"}, {"article": "a9", "state": ["dropped"]}]}
        text = 'For example {"proposals": []}. My answer:\n```json\n' + json.dumps(form) + "\n```"
        fields = ("proposals", "trades", "approach", "alignment", "state")
        read = lambda: {f: rr.advice(text, item)[0][f] for f in fields}
        want = {f: na.parse_advice(json.dumps(GOOD_REPLY), item)[f] for f in fields}
        self.assertEqual(read(), want)
        self.assertEqual(rr.advice(text, item)[1], {"reply": {"several_objects_last_read": 1}})
        # Neutralised: each field compared as it came, the old exact rule.
        self.prove("advice_read_whatever_its_form", read, want,
                   lambda: patch.object(rr, "_read", lambda v, declared, field, drops: v if isinstance(v, str) and v in declared else None))
        # Neutralised: the first object read, as the run's parser does: the example, not the answer.
        self.prove("advice_read_from_the_last_object", read, want,
                   lambda: patch.object(rr.af, "last_object", lambda t: (json.loads(t[t.index("{"):t.index("}") + 1]), None, False)))
        # An integer reason is the one known id ending in that number; two such ids refuse it as ambiguous.
        self.assertEqual([rr._cited(4, {"PAR-4", "POS-1"}), rr._cited("4", {"PAR-4", "POS-4"}), rr._cited(9, {"PAR-4"})],
                         [("PAR-4", None), (None, "ambiguous"), (None, "not_declared")])

    def test_18f_answers_read_again_from_saved_replies(self):
        # The answers file a score reads: the system's advice read again, its audits matched to the prompts the
        # run derived and held to their SHA-256; a piece the run's strict parser never put to the auditor is
        # counted not_asked; every row carries its drops, and the schema is the re-reader's.
        with setdir() as root, tempfile.TemporaryDirectory() as td:
            path = Path(td) / "p.json"
            value = na.build(root, "advice", ["system_advice"], path)
            value["_sha256"] = "s" * 64
            p = value["prompts"][0]
            form = dict(GOOD_REPLY, proposals=[dict(GOOD_REPLY["proposals"][0], stance="Accept"),
                                               GOOD_REPLY["proposals"][1], GOOD_REPLY["proposals"][2]])
            text = json.dumps(form)
            derived = na.audit_prompts(value["config"], p, text)
            measured = {d["prompt_id"]: (d["user_sha256"], "Supported, as the text says") for d in derived}
            observe = lambda: (lambda r: (r["schema"], r["rows"][0]["audit"], r["rows"][0]["drops"],
                                          r["rows"][0]["reply"]["proposals"]["P-A1-1"]["stance"]))(
                rr.advisor_rows(value, {p["prompt_id"]: text}, measured_audits=measured))
            want = (rr.ADVISOR_SCHEMA, {"P-A1-2": "supported", "P-A2-1": "supported"}, {"audit": {"not_asked": 1}}, "accept")
            self.assertEqual(observe(), want)
            self.prove("advisor_answers_read_again_with_audits_matched", observe, want,
                       lambda: patch.object(rr, "audit", lambda text, config: na.parse_audit(text, config) and (na.parse_audit(text, config), None) or (None, "not_declared")))

    def test_18g_each_group_answers_its_declared_way(self):
        # D-672 (a)(b): the judge and the system auditor decide by fixed choices, the system's advice and the
        # validator generate under the schema constraint, B1 generates freely (no declaration on its group).
        config = na.load_config()

        class Recorder:
            def __init__(self):
                self.used = []
            def generate(self, _s, user, n):
                self.used.append("generate")
                return {"text": "{}"}
            def generate_constrained(self, _s, user, n, schema, source):
                self.used.append("schema")
                return {"text": "{}"}
            def choose(self, _s, user, answers):
                self.used.append("choice")
                return {"decision": {}}
        item, _key = built()
        prompts = [dict(g, prompt_id="x", form={"b1": "advice", "system_advice": "advice", "system_audit": "audit",
                                                "judge": "judge", "validate": "validate"}[g["group"]],
                        item=item, user="u", max_new_tokens=4) for g in config["models"]]

        def observe():
            r = Recorder()
            for p in prompts:
                na.call(r, p, config)
            return dict(zip([p["group"] for p in prompts], r.used))
        want = {"b1": "generate", "system_advice": "schema", "system_audit": "choice", "judge": "choice", "validate": "schema"}
        self.assertEqual(observe(), want)
        self.prove("judge_and_auditor_decide_by_choice", observe, want,
                   lambda: patch.object(na, "DECIDE_BY_CHOICE", "no such way"))
        self.prove("advice_and_validator_under_the_schema", observe, want,
                   lambda: patch.object(na, "SCHEMA_CONSTRAINT", "no such way"))
        # Neither may be declared on B1 or anywhere else.
        for bad in ({"decide_by": "choice"}, {"constraint": "schema"}):
            wrong = json.loads(json.dumps(config))
            wrong["models"][0].update(bad)
            with self.assertRaises(ValueError):
                na.check_decoding(wrong)

    def test_18h_choice_decisions_are_read_as_their_label(self):
        # The pass saves each choice as a decision with no reply text; the answers (the run's reader and the
        # score-time re-reader) read it as the label it settles on under the form's declared threshold.
        with setdir() as root, tempfile.TemporaryDirectory() as td:
            path = Path(td) / "p.json"
            na.build(root, "advice", ["system_advice"], path)

            def observe():
                with tempfile.TemporaryDirectory() as out:
                    result = na.run(path, Path(out) / "pass", backend_factory=FakeBackend, reader_for=fake_reader, run_id="fx")
                    import reply_records
                    records = reply_records.records(Path(out) / "pass" / "audit" / "model_replies")
                    shapes = sorted({(r.get("reply") is None, isinstance(r.get("decision"), dict),
                                      isinstance(r.get("decoding_constraint"), dict)) for r in records})
                    mine = na.answers(path, Path(out) / "pass")
                    again = rr.advisor_answers(path, Path(out) / "pass")
                    audit = lambda a: next(r for r in a["rows"] if r["group"] == "system_advice")["audit"]
                    return ([(r["form"], r["decided"], r["constrained"]) for r in result["rows"]][:2], shapes,
                            audit(mine), audit(again))
            want = ([("advice", False, True), ("audit", True, False)], [(False, False, True), (True, True, False)],
                    {"P-A1-1": "supported", "P-A1-2": "unsupported", "P-A2-1": "supported"},
                    {"P-A1-1": "supported", "P-A1-2": "unsupported", "P-A2-1": "supported"})
            self.assertEqual(observe(), want)
            self.prove("choice_decisions_read_as_their_label", observe, want,
                       lambda: patch.object(na, "recorded_text", lambda record, config, form: None))
        # A tie settles nothing: the reader gets the choice module's unsettled word, which no form reads.
        tie = {"answers": [{"label": "0", "probability": 0.5}, {"label": "1", "probability": 0.5}, {"label": "2", "probability": 0.0}]}
        said = na.recorded_text({"backend_ok": True, "decision": tie}, na.load_config(), "judge")
        self.assertEqual((rr.judge(said)[0], na.parse_judge(said)), (None, None))

    def test_18i_the_schema_constraint(self):
        # The advice schema admits the plan's reply with the item's own ids and refuses an unknown id, a label
        # in another case, a fence and text after the object; under the constraint a stand-in model that
        # writes "Accept" is held to "accept" (DECODING-B: the processor masks, counts and never chooses).
        import contract_decoding_checks as base
        import schema_decoding as sd
        item, _key = built()
        good = json.dumps(GOOD_REPLY)
        bad = [good.replace('"P-A1-1"', '"P-Z9-9"', 1), good.replace('"accept"', '"Accept"', 1),
               "```json\n" + good + "\n```", good + " done"]
        observe = lambda: (sd.accepts(na.advice_schema(item), good), [sd.accepts(na.advice_schema(item), t) for t in bad],
                           sd.accepts(na.validate_schema(item), '{"article": "A2", "proposal": null, "stance": "oppose"}'),
                           sd.accepts(na.validate_schema(item), '{"article": "Article 2", "proposal": 1, "stance": "oppose"}'))
        want = (True, [False, False, False, False], True, False)
        self.assertEqual(observe(), want)
        real = na.advice_schema
        loose = lambda it: json.loads(json.dumps(real(it)).replace(
            '"type": "enum", "values": ["accept", "counter", "reject"]', '"type": "string", "max_chars": 20'))
        self.prove("the_schema_holds_ids_and_labels", observe, want, lambda: patch.object(na, "advice_schema", loose))
        reply = dict(GOOD_REPLY, proposals=[dict(p, stance=p["stance"].capitalize()) for p in GOOD_REPLY["proposals"]])
        intended, fallback = json.dumps(reply), good
        tok = base.FixtureTokenizer()

        def decode(constrained):
            model = base.StandInModel(tok, intended, fallback)
            prompt = tok("<prompt>")["input_ids"]
            extra, record = {}, None
            if constrained:
                built_c = sd.constraint("advice", na.advice_schema(item), tok, prompt.shape[1], [base.EOS], "fixture")
                extra, record = built_c.generate_kwargs(), built_c.record
            out = model.generate(prompt, 2400, eos_token_id=[base.EOS], **extra)
            text = tok.decode(out[0, prompt.shape[1]:].tolist())
            parsed = na.parse_advice(text, item)
            return (sorted(e.get("stance", "dropped") for e in (parsed or {}).get("proposals", {}).values()),
                    (record or {}).get("interventions", 0) > 0)
        observe_decode = lambda: (decode(False), decode(True))
        want_decode = ((["dropped", "dropped", "dropped"], False), (["accept", "counter", "reject"], True))
        self.assertEqual(observe_decode(), want_decode)
        self.prove("the_constraint_holds_the_model_to_the_schema", observe_decode, want_decode,
                   lambda: patch.object(sd.SchemaGrammar, "step", lambda self, state, ch: state if state not in (None, sd.DONE) else None))

    def test_18e_still_dropped_is_counted_by_reason(self):
        # What is still not read is counted by field and reason in the row and in the score report.
        item, _key = built()
        value = dict(GOOD_REPLY, state=[{"article": "A1", "state": "shut"}, {"article": "A1", "state": ["closed", "new"]},
                                        "closed"],
                     proposals=GOOD_REPLY["proposals"] + [{"id": "P-ZZ-9"}, {"id": "p-a1-1", "stance": "accept"}])
        read = lambda: rr.advice(json.dumps(value), item)[1]
        want = {"proposals.id": {"duplicate": 1, "not_declared": 1}, "state": {"not_an_object": 1},
                "state.state": {"list_not_one": 1, "not_declared": 1}}
        self.assertEqual(read(), want)
        # One bad entry costs only itself: the good proposals keep their reasons.
        self.assertEqual(rr.advice(json.dumps(value), item)[0]["proposals"]["P-A1-1"]["reasons"], ["POS-1"])
        self.prove("advice_drops_counted_by_reason", read, want,
                   lambda: patch.object(rr.af.Drops, "add", lambda self, field, reason: None))
        # The judge, the audit and the validator: the form taken off, a leading field label and what goes on
        # after a leading answer read past, the rest counted by reason.
        config = na.load_config()
        forms = lambda: ([rr.judge(t) for t in ('"2"', "**1**", "```\n0\n```", "Grade: 2", "12", "")],
                         [rr.audit(t, config) for t in ('"Supported."', "**Not supported**", "Cannot_Tell",
                                                        "Supported, because the text says so", "supportedly", "maybe")],
                         [rr.validate(t) for t in ('{"article": 7, "proposal": "1", "stance": "Support."}',
                                                   '{"article": ["A2"], "proposal": "none", "stance": "OPPOSE"}',
                                                   '{"article": "A2", "proposal": 1.5, "stance": "oppose"}', "no object")])
        want_forms = ([(2, None), (1, None), (0, None), (2, None), (None, "not_declared"), (None, "empty")],
                      [("supported", None), ("unsupported", None), ("cannot_tell", None), ("supported", None),
                       (None, "not_declared"), (None, "not_declared")],
                      [({"article": "7", "proposal": 1, "stance": "support"}, None),
                       ({"article": "A2", "proposal": None, "stance": "oppose"}, None), (None, "not_text"),
                       (None, "no_json_object")])
        self.assertEqual(forms(), want_forms)
        self.prove("judge_audit_validator_read_whatever_their_form", forms, want_forms,
                   lambda: patch.object(rr.af, "bare", lambda text: text))
        # The run's own parsers (bound, unchanged) still drop these forms: the re-reader is where they are read.
        self.assertEqual([na.parse_judge("Grade: 2"), na.parse_audit("Supported, because", config)], [None, None])
        # The score report carries the drops of every arm, and answers not read by the re-reader are refused.
        rows = {"rows": [{"group": "b1", "drops": want}, {"group": "b1", "drops": {"reply": {"empty": 1}}},
                         {"group": "system_advice", "drops": {}}]}
        self.assertEqual(rr.drop_counts(rows, "b1"), dict(want, reply={"empty": 1}))
        kw = self.scoring_inputs({"fx-k2-alpha": built()[1]})
        old = lambda: sc.refuse(**dict(kw, arms=dict(kw["arms"], B1=dict(kw["arms"]["B1"], schema=na.ANSWERS_SCHEMA))))
        self.assertTrue(str(old()).startswith("the B1 answers are not read by tools/reread_replies.py"), old())
        self.prove("answers_not_read_again_refused",
                   lambda: str(old()).startswith("the B1 answers are not read by tools/reread_replies.py"), True,
                   lambda: patch.object(sc.rr, "ADVISOR_SCHEMA", na.ANSWERS_SCHEMA))

    def test_19_power(self):
        sizes, shares = [5] * 12, {"conflict": 0.4, "no_conflict": 0.4, "not_stated": 0.2}
        strong = {"agreement": {"system": 0.97, "B1": 0.35, "cloud": 0.75}, "no_answer": {"system": 0, "B1": 0, "cloud": 0}}
        observe = lambda: sc.simulate_power(sizes, shares, iccs=(0.2,), sims=12, resamples=60, assumed=strong)["0.2"] >= 0.5
        self.assertTrue(observe())
        self.prove("power_lower_for_no_better_system", observe, True,
                   lambda: patch.dict(strong["agreement"], {"system": 0.35}))


    def test_20_judge_loads_phi4(self):
        """The judge and the validator resolve, through the real registry and bare_model.resolve_reader, to
        JUDGE's model (Phi-4), not to the system auditor's (Phi-3.5, VERIFIER's)."""
        def observe():
            groups = {g["group"]: g for g in json.loads(na.CONFIG_PATH.read_text(encoding="utf-8"))["models"]}
            ids = {g: na.reader_of(groups[g], 8)["model_id"] for g in ("judge", "validate", "system_audit")}
            return ids["judge"], ids["validate"], ids["judge"] != ids["system_audit"]
        registry = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
        phi4 = registry["JUDGE"]["model"]
        self.assertIn("phi-4", phi4.lower())
        self.assertEqual(observe(), (phi4, phi4, True))
        with tempfile.TemporaryDirectory() as td:
            raw = json.loads(na.CONFIG_PATH.read_text(encoding="utf-8"))
            for g in raw["models"]:
                g.pop("model", None)
            undeclared = Path(td) / "config.json"
            undeclared.write_text(json.dumps(raw), encoding="utf-8")
            # Neutralised: the form without its declared model, as the lane first wrote it.
            self.prove("judge_and_validator_load_phi4", observe, observe(),
                       lambda: patch.object(na, "CONFIG_PATH", undeclared))
        wrong = dict(next(g for g in na.load_config()["models"] if g["group"] == "judge"), model="some/other-model")
        with self.assertRaises(ValueError):
            na.reader_of(wrong, 8)

    def test_21_cloud_subset(self):
        keys = {}
        # P in one stratum, so H's one item (quota 0.54) loses on remainders to G's two strata (0.62 each).
        for n in range(30):
            keys["p%02d" % n] = {"part": "P", "configuration": "everyone", "round": 1, "conflict_labels_here": "never read"}
        keys["h00"] = {"part": "H", "configuration": "bilateral", "round": 2}
        for n in range(6):
            keys["g%02d" % n] = {"part": "G", "round": 1 + n % 2}
        observe = lambda: (len(sc.cloud_subset(keys)["items"]),
                           sorted({i[0] for i in sc.cloud_subset(keys)["items"]}), sc.cloud_subset(keys)["items"])
        first = observe()
        self.assertEqual(first[:2], (20, ["g", "h", "p"]))
        self.assertEqual(first, observe())                       # seeded: the same draw every time
        # Neutralised: no place reserved for a part (H's one item has a quota of 0.54 and loses on remainders).
        self.prove("every_part_has_a_cloud_place", observe, first, lambda: patch.object(sc, "MIN_PART_PLACES", 0))
        relabelled = {i: dict(k, conflict_labels_here="changed") for i, k in keys.items()}
        self.assertEqual(sc.cloud_subset(relabelled)["items"], first[2])
        # The report reads the cloud arm on the subset alone, B1 and the system beside it on the same subset.
        item, key = built()
        b2 = copy.deepcopy(BUILD)
        b2["item_id"] = "fx-k2-beta"
        items = {"fx-k2-alpha": item, "fx-k2-beta": sc.build_item(b2)[0]}
        two = {"fx-k2-alpha": key, "fx-k2-beta": sc.build_item(b2)[1]}
        rows = lambda group: {"rows": [{"form": "advice", "group": group, "item_id": i, "reply": reply_of(items[i]),
                                        "audit": {}} for i in items]}
        subset = ["fx-k2-alpha"]
        on = lambda: (lambda r: (r["cloud_subset"]["items"], r["figures"]["cloud"]["M1"]["items"],
                                 r["figures_on_cloud_subset"]["B1"]["M1"]["items"], r["figures"]["B1"]["M1"]["items"]))(
            sc.report(items, two, {"B1": (rows("b1"), "b1"), "system": (rows("system_advice"), "system_advice"),
                                   "cloud": (rows("b1"), "b1")}, subset=subset, resamples=20))
        self.assertEqual(on(), (1, 1, 1, 2))
        # Neutralised: the subset holds every item, so the cloud figure is no longer the subset's.
        self.prove("cloud_read_on_its_subset", on, on(), lambda: _extend(subset, ["fx-k2-beta"]))
        with setdir() as root:
            value = sc.freeze(root, [], encode=None)
            on_disk = sc.hashlib.sha256((root / sc.SUBSET_FILE).read_bytes()).hexdigest()
            self.assertEqual(value["cloud_subset_sha256"], on_disk)

    def test_22_bar_line_4_and_m9(self):
        item, key = built()
        rows = {"rows": [{"form": "advice", "group": "b1", "item_id": "fx-k2-alpha", "reply": reply_of(item)}]}
        rep = {"figures": {"system": {"M8g": {"estimate": 0.9}}, "B1": {"M8g": {"estimate": 0.9}}},
               "claims": {"A1": {"difference": 0.2, "bca_lower": 0.05}}, "withheld_rate": 0.1}
        with setdir() as root:
            def write(name, value):
                (root / name).write_text(json.dumps(value), encoding="utf-8")
            write("mapping_validation.json", {"kappa": 0.55})
            write("checker_agreement.json", {"fields": {f: {"kappa": 0.8} for f in sc.SAMPLE_FIELDS}})
            write("grade_agreement.json", {"kappa": 0.5, "judge_prompts_sha256": "j"})

            def observe():
                state = sc.validation_state(root, {"prompts_sha256": "j"})
                m9 = sc.report({"fx-k2-alpha": item}, {"fx-k2-alpha": key}, {"B1": (rows, "b1")}, judge=[],
                               resamples=20, validation=state)["M9_status"]
                return {f: state[f] for f in ("mapping", "checker", "grade")}, sc.bar(rep, validation=state)["cleared"], m9
            self.assertEqual(observe(), ({"mapping": False, "checker": True, "grade": False}, None, "not validated"))
            # Neutralised: the floor lowered below the recorded kappas; the bar is then assessable and M9 validated.
            self.prove("kappa_floor_decides_line_4_and_m9", observe, observe(),
                       lambda: patch.object(sc, "KAPPA_FLOOR", 0.4))
        self.assertTrue(sc.bar(rep, validation={"mapping": True, "checker": True})["cleared"])

    def test_23_configuration_binds(self):
        kw = self.scoring_inputs({"fx-k2-alpha": built()[1]})
        tampered = lambda: (
            sc.refuse(**dict(kw, judge=dict(kw["judge"], prompts_sha256="other"))),
            sc.refuse(**dict(kw, arms=dict(kw["arms"], B1=dict(kw["arms"]["B1"], models={"b1": {"digest": "other"}})))),
            sc.refuse(**dict(kw, configuration={f: v for f, v in kw["configuration"].items() if f != "cloud_subset_sha256"})))
        self.assertEqual(tampered(), ("the judge's answers are not of the configuration's judge prompts",
                                      "the b1 checkpoint loaded is not the configuration's",
                                      "the configuration lacks cloud_subset_sha256"))
        # Neutralised: no checkpoint digest bound.
        self.prove("checkpoint_digests_bound", tampered, tampered(), lambda: patch.object(sc, "DIGEST_GROUPS", ()))
        # Neutralised: the configuration's field list as the lane first wrote it.
        old = ("commit", "b1_prompts_sha256", "system_prompts_sha256", "cloud_prompts_sha256", "cloud_model_id",
               "power_record_sha256", "models")
        self.prove("subset_and_judge_in_the_configuration", tampered, tampered(),
                   lambda: patch.object(sc, "CONFIG_FIELDS", old))

    def test_24_separation(self):
        item, key = built()
        rows = {"rows": [{"form": "advice", "group": "b1", "item_id": "fx-k2-alpha", "reply": reply_of(item)}]}
        observe = lambda: sorted(sc.report({"fx-k2-alpha": item}, {"fx-k2-alpha": key}, {"B1": (rows, "b1")},
                                           resamples=20)["cells"]["B1"]["configuration"]["one_vs_group"]["M1"])
        self.assertEqual(observe(), ["items"])
        # Neutralised: a one-item cell given a figure.
        self.prove("small_cells_counts_only", observe, ["items"], lambda: patch.object(sc, "MIN_CELL", 1))
        with setdir() as root, tempfile.TemporaryDirectory() as elsewhere:
            named = [root]

            def inside():
                try:
                    sc.inside_set(Path(elsewhere) / "rows.json", named[0])
                    return "accepted"
                except ValueError:
                    return "refused"
            self.assertEqual(inside(), "refused")
            self.assertEqual(sc.inside_set(root / "rows.json", root), (root / "rows.json").resolve())
            # Neutralised: the rows' own folder named as the set, so the same path is accepted.
            self.prove("per_item_rows_in_the_set_folder", inside, "refused",
                       lambda: _replace(named, 0, Path(elsewhere)))

            # A stand-in repository in a temporary folder, so nothing is written in the real one.
            standin = Path(elsewhere) / "standin_repository"
            repository = [standin]

            def written():
                with patch.object(na, "ROOT", repository[0]):
                    try:
                        na.build(root, "advice", ["b1"], standin / "output" / "prompts.json")
                        return "accepted"
                    except ValueError:
                        return "refused"
            self.assertEqual(written(), "refused")
            self.assertEqual(sc.ROOT, na.ROOT)
            # Neutralised: the repository the rule guards is another folder than the one written to.
            self.prove("forms_write_nothing_in_the_repository", written, "refused",
                       lambda: _replace(repository, 0, Path(elsewhere) / "not_the_repository"))

    def test_25_m9_withheld_counters(self):
        item, key = built()
        value = copy.deepcopy(GOOD_REPLY)
        value["proposals"][1] = {"id": "P-A1-2", "conflict": "not_stated", "stance": "counter",
                                 "wording": "Each party should share data", "reasons": ["PAR-2"]}
        given = reply_of(item, value)
        kept, _trail = sc.withhold(item, given, {"P-A1-2": "unsupported", "P-A2-1": "unsupported"})
        # Two counters withheld: P-A1-2 (fate removed, never graded) and P-A2-1 (fate changed, graded).
        observe = lambda: sc.withheld_counters(item, key, given, kept)
        self.assertEqual(observe(), 1)
        # Neutralised: the judged fates widened to removed, so a counter the judge never grades scores 0.
        self.prove("m9_counts_judged_counters_only", observe, 1,
                   lambda: patch.object(na, "JUDGED_FATES", ("changed", "kept", "removed")))

    def test_26_bar_line_1(self):
        def line(diff, lower):
            rep = {"figures": {"system": {"M8g": {"estimate": 0.9}}, "B1": {"M8g": {"estimate": 0.9}}},
                   "claims": {"A1": {"difference": diff, "bca_lower": lower, "status": "indicator"}}, "withheld_rate": 0.1}
            return sc.bar(rep, validation={"mapping": True, "checker": True})["lines"]["1"]
        observe = lambda: (line(0.12, 0.02), line(0.12, -0.01), line(0.08, 0.03))
        self.assertEqual(observe(), (True, False, False))
        self.prove("bar_needs_ten_points", observe, observe(), lambda: patch.object(sc, "BAR_MARGIN", 0.05))

    def test_27_token_budget(self):
        b = copy.deepcopy(BUILD)
        b["articles"][2] = dict(b["articles"][2], text="word " * 24500)

        def observe():
            try:
                with setdir((b,)) as root:
                    return "built", (root / "items").exists()
            except ValueError as exc:
                return str(exc).split(":")[0], False
        self.assertEqual(observe(), ("refused", False))
        self.prove("item_over_the_token_budget_refused", observe, observe(),
                   lambda: patch.object(na, "TOKEN_LIMIT", 10 ** 6))

    def test_28_terms_of_use_and_source(self):
        b = copy.deepcopy(BUILD)
        del b[na.TERMS_FIELD]

        def observe():
            try:
                return sc.build_item(copy.deepcopy(b))[0][na.TERMS_FIELD]
            except ValueError as exc:
                return str(exc)
        self.assertEqual(observe(), "a build file lacks %s" % na.TERMS_FIELD)
        self.assertEqual(built()[0][na.TERMS_FIELD], BUILD[na.TERMS_FIELD])
        self.prove("terms_of_use_required_on_every_item", observe, observe(),
                   lambda: patch.object(sc, "REQUIRED_BUILD", tuple(f for f in sc.REQUIRED_BUILD if f != na.TERMS_FIELD)))
        with setdir() as root:
            before = sc.set_digest(root)[1]
            (root / "build" / BUILD["item_id"] / "SOURCE.md").write_text("another source", encoding="utf-8")
            sc.build_set(root, count=WORDS)
            self.assertNotEqual(sc.set_digest(root)[1], before)

    def test_29_power_alpha_per_opening(self):
        kw = self.scoring_inputs({"fx-k2-alpha": built()[1]})
        line2 = "neg-advisor opening k=2 set=%s config=%s" % ("a" * 64, "c" * 64)
        record2 = {"set_sha256": "a" * 64, "sims": 1000, "k": 2, "alpha": 0.0125, "code_sha256": sc.code_sha256()}

        def at(record, k, line):
            text = json.dumps(record)
            conf = dict(kw["configuration"], power_record_sha256=sc._sha(text))
            return sc.refuse(**dict(kw, k=k, openings_text=line, power=record, power_text=text, configuration=conf))
        observe = lambda: (at(kw["power"], 1, kw["openings_text"]) is None, at(kw["power"], 2, line2) is None,
                           at(record2, 2, line2) is None)
        self.assertEqual(observe(), (True, False, True))
        self.prove("opening_2_needs_its_own_alpha", observe, observe(), lambda: patch.dict(record2, {"alpha": 0.025}))
        self.assertEqual((sc.opening_alpha(1), sc.opening_alpha(2), sc.opening_alpha(3)), (0.025, 0.0125, 0.00625))
        # D-710: the pilot's third opening at 0.00625; its record at opening 2's alpha is refused.
        p3 = self.pilot_inputs(kw, 3)
        record3 = dict(p3["power"])

        def third():
            text = json.dumps(record3)
            return sc.refuse(**dict(p3, power=record3, power_text=text,
                                    configuration=dict(p3["configuration"], power_record_sha256=sc._sha(text))))
        self.assertEqual((record3["alpha"], third()), (0.00625, None))
        self.prove("opening_3_needs_its_own_alpha", third, None, lambda: patch.dict(record3, {"alpha": 0.0125}))
        # The third opening is an indicator whatever its power record says (D-710); opening 1 follows its power.
        strong = {"power_by_icc": {"0.2": 0.9, "0.5": 0.9}}
        status = lambda: (sc.opening_claim_status(strong, 1), sc.opening_claim_status(strong, 3))
        self.assertEqual(status(), ("claim", "indicator"))
        self.prove("third_opening_indicator_only", status, ("claim", "indicator"),
                   lambda: patch.object(sc, "MAX_OPENINGS", 3))


    def test_30_judge_model_at_score_time(self):
        kw = self.scoring_inputs({"fx-k2-alpha": built()[1]})
        self.assertIsNone(sc.refuse(**kw))
        phi35 = dict(kw["judge"], models={"judge": dict(kw["judge"]["models"]["judge"],
                                                         model_id="unsloth/Phi-3.5-mini-instruct-bnb-4bit")})
        # A Phi-3.5 judge pass whose digest the configuration also names (the digests come from the same
        # passes, so they alone cannot catch it): refused by the registry's model.
        observe = lambda: sc.refuse(**dict(kw, judge=phi35))
        self.assertEqual(observe(), "the judge pass did not load %s, the registry's model of its agent" % PHI4)
        self.prove("a_phi35_judge_pass_is_refused", observe, observe(), lambda: patch.object(sc, "MODEL_BOUND_GROUPS", ()))
        # A Phi-3.5 validator: mapping_validation.json differs from the passing fixture in its recorded
        # models.validate.model_id alone (digest, prompts and kappa as before).
        validation = copy.deepcopy(kw["validation"])
        validation["models"]["validate"]["model_id"] = "unsloth/Phi-3.5-mini-instruct-bnb-4bit"
        validator = lambda: sc.refuse(**dict(kw, validation=validation))
        self.assertEqual(validator(), "the validate pass did not load %s, the registry's model of its agent" % PHI4)
        self.prove("a_phi35_validator_is_refused_at_score_time", validator, validator(),
                   lambda: patch.object(sc, "MODEL_BOUND_GROUPS",
                                        tuple(g for g in sc.MODEL_BOUND_GROUPS if g != ("validation", "validate"))))

    def test_31_validator_bound(self):
        with setdir() as root:
            positions = sc.build_positions(root)["fx-k2-alpha"]
            row = lambda p: {"form": "validate", "item_id": "fx-k2-alpha", "position_id": p["id"],
                             "mapping": {"article": p["article"], "proposal": p.get("proposal"), "stance": p["stance"]}}
            answers = {"prompts_sha256": "v" * 64, "models": {"validate": {"model_id": PHI4, "digest": "d"}},
                       "rows": [row(p) for p in positions]}
            whole = sc.validate_read(root, answers, "v" * 64)
            self.assertEqual((whole["positions"], whole["agree"], whole["prompts_sha256"]), (6, 6, "v" * 64))

            def outcome(value, sha="v" * 64):
                try:
                    r = sc.validate_read(root, value, sha)
                    return "read %d of %d" % (r["answered"], r["positions"])
                except ValueError as exc:
                    return str(exc).split(":")[1].strip()
            short = dict(answers, rows=answers["rows"][:-1])
            missing = lambda: outcome(short)
            self.assertEqual(missing(), "1 position(s) have no validate answer row")
            self.prove("every_position_needs_an_answer_row", missing, missing(),
                       lambda: patch.object(sc, "VALIDATION_REQUIRES", ("prompts", "model")))
            other = lambda: outcome(answers, "w" * 64)
            self.assertEqual(other(), "the validate answers are not of this validate prompts file")
            self.prove("validate_answers_of_their_prompts", other, other(),
                       lambda: patch.object(sc, "VALIDATION_REQUIRES", ("model", "every_position")))
            phi35 = dict(answers, models={"validate": {"model_id": "unsloth/Phi-3.5-mini-instruct-bnb-4bit", "digest": "d"}})
            wrong = lambda: outcome(phi35)
            self.assertEqual(wrong(), "the validate pass did not load %s" % PHI4)
            self.prove("validate_pass_on_phi4", wrong, wrong(),
                       lambda: patch.object(sc, "VALIDATION_REQUIRES", ("prompts", "every_position")))
        kw = self.scoring_inputs({"fx-k2-alpha": built()[1]})
        unbound = lambda: sc.refuse(**dict(kw, validation=dict(kw["validation"], models={"validate": dict(
            kw["validation"]["models"]["validate"], digest="another")})))
        self.assertEqual(unbound(), "the validate checkpoint loaded is not the configuration's")
        self.prove("validate_digest_in_the_configuration", unbound, unbound(),
                   lambda: patch.object(sc, "DIGEST_GROUPS", tuple(g for g in sc.DIGEST_GROUPS if g[1] != "validate")))

    def test_32_cloud_subset_refusals(self):
        b2 = copy.deepcopy(BUILD)
        b2["item_id"] = "fx-k2-beta"
        keys = {"fx-k2-alpha": built()[1], "fx-k2-beta": sc.build_item(b2)[1]}
        kw = self.scoring_inputs(keys)
        self.assertIsNone(sc.refuse(**kw))
        drawn = json.loads(kw["subset_bytes"])
        without = lambda refusal: patch.object(sc, "SUBSET_REFUSALS", tuple(r for r in sc.SUBSET_REFUSALS if r != refusal))
        # 1. bound: a subset file whose SHA-256 the freeze and the configuration do not name.
        # The same draw in another file, and cloud answers recording that file: only the binding to the
        # freeze and the configuration tells it apart, so with that rule removed the scoring goes on (None).
        other = json.dumps(dict(drawn, note="another file")).encode("utf-8")
        other_sha = sc.hashlib.sha256(other).hexdigest()
        unbound = dict(kw, subset_bytes=other, arms=dict(kw["arms"], cloud=dict(kw["arms"]["cloud"], subset_sha256=other_sha)))
        bound = lambda: sc.refuse(**unbound)
        self.assertEqual(bound(), "the cloud subset is not the freeze's and the configuration's")
        with without("bound"):
            self.assertIsNone(bound())
        self.prove("cloud_subset_bound_to_freeze_and_configuration", bound, bound(), lambda: without("bound"))
        # 2. drawn: a subset named everywhere but not the plan's draw from the frozen keys.
        fewer = json.dumps(dict(drawn, items=drawn["items"][:1])).encode("utf-8")
        sha = sc.hashlib.sha256(fewer).hexdigest()
        named = dict(kw, subset_bytes=fewer, freeze=dict(kw["freeze"], cloud_subset_sha256=sha),
                     configuration=dict(kw["configuration"], cloud_subset_sha256=sha),
                     arms=dict(kw["arms"], cloud=dict(kw["arms"]["cloud"], subset_sha256=sha,
                                                      rows=[{"item_id": drawn["items"][0]}])))
        redrawn = lambda: sc.refuse(**named)
        self.assertEqual(redrawn(), "the cloud subset is not the plan's draw from this set")
        self.prove("cloud_subset_is_the_plans_draw", redrawn, redrawn(), lambda: without("drawn"))
        # 3. answered: cloud answers missing one of the subset's items.
        part = dict(kw, arms=dict(kw["arms"], cloud=dict(kw["arms"]["cloud"], rows=kw["arms"]["cloud"]["rows"][:1])))
        answered = lambda: sc.refuse(**part)
        self.assertEqual(answered(), "the cloud answers are not of the cloud subset's items")
        self.prove("cloud_answers_of_the_subset_exactly", answered, answered(), lambda: without("answered"))


    def validate_v1_config(self, td):
        """The validate form as round 1 ran it: the template committed at ad9a5c8a (VALIDATE_V1_TEMPLATE,
        held to its pinned SHA-256), no form_version."""
        raw = json.loads(na.CONFIG_PATH.read_text(encoding="utf-8"))
        raw["validate"].pop("form_version")
        raw["validate"].pop("form_note")
        raw["validate"]["template"] = VALIDATE_V1_TEMPLATE
        path = Path(td) / "v1.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        return path

    def test_33_validator_answers_an_id(self):
        """D-617: the validate form lists the item's article ids and asks for exactly one; the reader takes
        only an exact id; proposal and stance are asked byte for byte as in round 1; round 1's form still reads."""
        item, _key = built()
        pos = dict(BUILD["positions"][0])
        with tempfile.TemporaryDirectory() as td:
            v1 = self.validate_v1_config(td)
            config_path = [na.CONFIG_PATH]
            listed = lambda: "THE ARTICLE IDS: A1, A2, A3" in na.render_validate(na.load_config(config_path[0]), item, pos)
            self.assertTrue(listed())
            self.prove("validate_prompt_lists_the_ids", listed, True, lambda: _replace(config_path, 0, v1))

            def tail(t):
                return (t[t.index("THE MAPPING TO CHECK"):t.index("\n\nReply")], t[t.index('"proposal":'):])
            # Against the template as committed at ad9a5c8a (a pinned literal), never a rebuilt copy.
            current = lambda: json.loads(Path(config_path[0]).read_text(encoding="utf-8"))["validate"]["template"]
            same = lambda: tail(current()) == tail(VALIDATE_V1_TEMPLATE)
            self.assertTrue(same())
            self.assertEqual(sc._sha(VALIDATE_V1_TEMPLATE), VALIDATE_V1_SHA256)
            stance = Path(td) / "v_stance.json"
            changed = json.loads(na.CONFIG_PATH.read_text(encoding="utf-8"))
            changed["validate"]["template"] = changed["validate"]["template"].replace(
                '"stance": "support" or "oppose" or "accept"', '"stance": "agree" or "disagree"')
            stance.write_text(json.dumps(changed), encoding="utf-8")
            self.prove("proposal_and_stance_byte_identical", same, True, lambda: _replace(config_path, 0, stance))
            with setdir() as root:
                old = na.build(root, "validate", None, Path(td) / "v1_prompts.json", config_path=v1,
                               positions=sc.build_positions(root))
                self.assertEqual((old["validate_form_version"], len(na.load_prompts(Path(td) / "v1_prompts.json"))), (1, 6))
                new = na.build(root, "validate", None, Path(td) / "v2_prompts.json", positions=sc.build_positions(root))
                self.assertEqual(new["validate_form_version"], 2)
                positions = sc.build_positions(root)["fx-k2-alpha"]
                titles = {a["id"]: a["title"] for a in BUILD["articles"]}

                def answers(heading_for=None):
                    rows = [{"form": "validate", "item_id": "fx-k2-alpha", "position_id": p["id"],
                             "mapping": {"article": titles[p["article"]] if p["id"] == heading_for else p["article"],
                                         "proposal": p.get("proposal"), "stance": p["stance"]}} for p in positions]
                    return {"prompts_sha256": "v" * 64, "models": {"validate": {"model_id": PHI4, "digest": "d"}},
                            "rows": rows}
                read = lambda value: (lambda r: (r["agree"], r["article_not_an_id"], r["answered"], r["form_version"]))(
                    sc.validate_read(root, value, "v" * 64, form_version=2))
                heading = lambda: read(answers("POS-1"))
                self.assertEqual(heading(), (5, 1, 6, 2))
                # Neutralised: the list the reader accepts also holds the headings (a reader that maps them).
                self.prove("a_heading_is_not_an_id", heading, heading(),
                           lambda: patch.object(na, "article_ids", lambda it: [a["id"] for a in it["articles"]]
                                                + [a["title"] for a in it["articles"]]))
                exact = lambda: read(answers())
                self.assertEqual(exact(), (6, 0, 6, 2))
                # Neutralised: the reader compares a normalised form of the ids, not the ids as written.
                self.prove("an_exact_id_is_read", exact, exact(),
                           lambda: patch.object(na, "article_ids", lambda it: [a["id"].lower() for a in it["articles"]]))
                # Round 1 re-read under the rule it was recorded under (form_version 1: the answer as written,
                # as ad9a5c8a's reader took it). ROUND1_PINNED is that commit's validate_read on these answers,
                # computed by executing it (14 November 2026).
                round1 = answers("POS-1")
                round1["rows"][2]["mapping"]["article"] = " " + round1["rows"][2]["mapping"]["article"]
                reread = lambda: (lambda r: (round(r["kappa"], 12), r["agree"]))(
                    sc.validate_read(root, round1, "v" * 64, form_version=1))
                self.assertEqual(reread(), ROUND1_PINNED)
                # Neutralised: round 1 read with a rule that maps headings and spacing to ids.
                to_ids = {a["title"]: a["id"] for a in BUILD["articles"]}
                self.prove("round_1_reread_under_its_own_rule", reread, ROUND1_PINNED, lambda: patch.dict(
                    sc.ARTICLE_RULES, {1: lambda said, ids: to_ids.get(said, str(said).strip())}))


    def test_34_freeze_passes_accepted_kinds(self):
        """D-618: the freeze command reads the corpus list as freeze_negotiation_set.main does and passes its
        accept-skipped kinds on, so a listed folder holding a file of an accepted kind is not refused."""
        with setdir() as root, tempfile.TemporaryDirectory() as td:
            corpus = Path(td) / "corpus"
            corpus.mkdir()
            (corpus / "notes.txt").write_text("An invented passage of more than twenty words, about nothing at all, "
                                              "written only for this fixture of the freeze command line.", encoding="utf-8")
            (corpus / "weights.npy").write_bytes(b"\x93NUMPY fixture bytes")
            listed = Path(td) / "corpora.txt"
            listed.write_text("# fixture list\n%s\naccept-skipped: .npy\n" % corpus, encoding="utf-8")
            fz = sc.fz()
            self.assertEqual(sc.corpus_list(listed), ([corpus], [".npy"]))

            def observe():
                try:
                    with redirect_stdout(io.StringIO()):
                        code = sc.main(["freeze", "--set", str(root), "--corpora", str(listed), "--no-embedding"])
                    return code, (root / "FREEZE.dryrun.json").is_file()
                except ValueError as exc:
                    return "refused", str(exc).split(" (")[0]
            self.assertEqual(observe(), (0, True))
            self.assertIsNotNone(fz)
            # Neutralised: the code no longer reads the accept-skipped line as one (its prefix changed), so no
            # kind is passed on. The folder is listed before that line and corpus_passages judges each path in
            # order, so the folder is refused for its .npy file before the unread line, which names no existing
            # path, is reached: the refusal is the kind refusal of the bug, not a missing path.
            dropped = lambda: patch.object(sc, "ACCEPT_PREFIX", "accept-skipped-not-read:")
            self.assertFalse(Path("accept-skipped: .npy").exists())
            with dropped():
                self.assertEqual(observe(), ("refused", "a corpus holds files of a kind neither read nor accepted"))
            self.prove("freeze_passes_the_accepted_kinds", observe, (0, True), dropped)


    def test_35_freeze_vectors_route(self):
        """Seckin 17:19, option (b): the advisor's freeze exports its embedding input, embed_records makes the
        vectors (here its replay run with a stub one-hot embedder) and merges them, and --vectors gives the
        in-process freeze's FREEZE.json and cloud subset byte for byte. Fixtures only."""
        import hashlib
        import shutil
        import numpy as np
        fz = sc.fz()
        er = fz._embed_records()

        def onehot(texts):
            out = np.zeros((len(texts), 1024), dtype=np.float32)
            for i, t in enumerate(texts):
                out[i, int(hashlib.sha256(str(t).encode("utf-8")).hexdigest()[:8], 16) % 1024] = 1.0
            return out
        embedder = lambda texts, batch_size: onehot(texts)
        embedder.dim, embedder.max_seq_length = 1024, 8192

        def observe():
            with setdir() as root, tempfile.TemporaryDirectory(prefix="negadv_route_") as td:
                td = Path(td)
                corpus = td / "corpus.md"
                corpus.write_text("\n\n".join(" ".join("filler%d word%d" % (k, i) for i in range(12)) for k in range(4)),
                                  encoding="utf-8")
                other = td / "copy"
                shutil.copytree(root, other)
                model = {"fixture": "the same model record on both sides"}
                sc.freeze(root, [corpus], encode=fz.formed(onehot), model=model, progress=lambda line: None)
                exported = sc.freeze(other, [corpus], export=td / "export", progress=lambda line: None)
                no_freeze = not (other / "FREEZE.json").exists() and not (other / sc.SUBSET_FILE).exists()
                er.build(td / "export" / "records.jsonl", td / "parts")
                pairs = []
                for n, prompts in enumerate(sorted((td / "parts").glob("part*/replay_prompts.json"))):
                    er.run(prompts, td / ("ev%d" % n), embedder=embedder, run_id="fixture")
                    pairs.append((td / ("ev%d" % n), prompts))
                er.merge(pairs, td / "export" / "laptop", td / "merged", require_complete=True)
                encode = fz.vectors_encoder(td / "merged", td / "export" / "records.jsonl")
                sc.freeze(other, [corpus], encode=encode, model=model, progress=lambda line: None)
                same = all((root / f).read_bytes() == (other / f).read_bytes() for f in ("FREEZE.json", sc.SUBSET_FILE))
                texts = [json.loads(l)["text"] for l in (td / "export" / "records.jsonl").read_text(encoding="utf-8").splitlines()]
                return {"identical": same, "vectors_identical": encode(texts).tobytes() == fz.formed(onehot)(texts).tobytes(),
                        "rows": exported["rows"], "no_freeze_on_export": no_freeze}
        got = observe()
        self.assertEqual((got["identical"], got["vectors_identical"]), (True, True))
        real = er.embed_batched
        # Neutralised: the instance's pass hands each chunk's vectors back in reverse order (a misplaced row).
        self.prove("advisor_freeze_vectors_route_equals_in_process", observe, got,
                   lambda: patch.object(er, "embed_batched", lambda embed, texts, rule=er.BATCH_RULE: real(embed, texts, rule)[::-1].copy()))

    def _filled_sheet(self, root, red_wrong=False):
        """The checker's sheet of the set filled with the key's own labels; the persona's red-line marks from
        the item (`red_wrong`: one mark turned the other way)."""
        sheet = sc.sample_sheet(root)
        keys, items = sc.read_keys(root), na.read_items(root)
        for entry in sheet["items"]:
            key, item, fill = keys[entry["item_id"]], items[entry["item_id"]], entry["fill"]
            for pid, row in key["proposals"].items():
                fill["fate"][pid], fill["conflict"][pid] = row["fate"], row["conflict"]
            for aid, row in key["articles"].items():
                fill["state"][aid] = row["state"]
            for aid, cells in key["alignment"].items():
                fill["alignment"][aid] = dict(cells)
            red = set(item["persona"].get("red_lines") or [])
            for n, pos in enumerate(sorted(fill["red_line"])):
                mark = "red_line" if pos in red else "not_red_line"
                fill["red_line"][pos] = ("red_line" if mark == "not_red_line" else "not_red_line") if red_wrong and n == 0 else mark
        return sheet

    def test_36_single_class_field(self):
        """AM-1 (D-662): a checker field where the key gives one class (the pilot's red_line, 36 of 36 not a
        red line) has no defined kappa; at 100 percent raw agreement it is at the bar, labelled; below 100
        percent it is below. M9's validation alike (the checker's grades the reference)."""
        no_red = dict(copy.deepcopy(BUILD), red_lines=[])

        def observe(red_wrong=False):
            with setdir((no_red,)) as root:
                (root / "checker_agreement.json").write_text(json.dumps(sc.sample_read(root, self._filled_sheet(root, red_wrong))),
                                                             encoding="utf-8")
                (root / "mapping_validation.json").write_text(json.dumps({"kappa": 0.9}), encoding="utf-8")
                # M9 below 100 percent on a single class: the checker gives 2 on all 10, the judge 1 on one.
                sheet = {"entries": [{"entry_id": "e%d" % n, "grade": 2} for n in range(10)]}
                judge = {"prompts_sha256": "j", "rows": [{"form": "judge", "entry_id": "e%d" % n, "grade": 2 if n else 1}
                                                         for n in range(10)]}
                (root / "grade_agreement.json").write_text(json.dumps(sc.grade_read(sheet, judge)), encoding="utf-8")
                state = sc.validation_state(root, judge)
                field = state["fields"]["checker:red_line"]
                rep = {"figures": {"system": {"M8g": {"estimate": 0.9}}, "B1": {"M8g": {"estimate": 0.9}}},
                       "claims": {"A1": {"difference": 0.2, "bca_lower": 0.05}}, "withheld_rate": 0.1}
                return (state["checker"], field.get("label"), field["raw_agreement"], state["grade"],
                        sc.bar(rep, validation=state)["cleared"], sc.bar(rep, validation=state)["single_class_fields"])
        full = observe()
        self.assertEqual(full, (True, sc.SINGLE_CLASS_LABEL, 1.0, False, True, ["checker:red_line"]))
        # Neutralised: the old rule, no single-class field ever at the bar (100 percent made unreachable).
        self.prove("single_class_field_at_100_percent_at_the_bar", observe, full,
                   lambda: patch.object(sc, "SINGLE_CLASS_FULL", 1.01))
        below = lambda: (lambda r: r[:3] + r[4:5])(observe(red_wrong=True))
        self.assertEqual(below(), (False, sc.SINGLE_CLASS_LABEL, 0.5, None))
        # Neutralised: a single-class field at the bar below 100 percent.
        self.prove("single_class_field_below_100_percent_below_the_bar", below, below(),
                   lambda: patch.object(sc, "SINGLE_CLASS_FULL", 0.5))
        # M9: the checker and the judge both give grade 2 on every sampled entry: at the bar, labelled.
        grade = lambda: (lambda s: (s["grade"], s["fields"]["grade"].get("label")))(
            self._grade_state(("2", "2")))
        self.assertEqual(grade(), (True, sc.SINGLE_CLASS_LABEL))
        self.prove("m9_single_class_grade_at_100_percent_validated", grade, grade(),
                   lambda: patch.object(sc, "SINGLE_CLASS_FULL", 1.01))
        # A record written before AM-1 (no single-class fields, kappa undefined) stays below the bar.
        self.assertFalse(sc.at_bar({"rows": 36, "kappa": None}))

    def _grade_state(self, grades):
        with tempfile.TemporaryDirectory() as td:
            sheet = {"entries": [{"entry_id": "e%d" % n, "grade": int(grades[0])} for n in range(10)]}
            judge = {"prompts_sha256": "j", "rows": [{"form": "judge", "entry_id": "e%d" % n, "grade": int(grades[1])}
                                                     for n in range(10)]}
            (Path(td) / "grade_agreement.json").write_text(json.dumps(sc.grade_read(sheet, judge)), encoding="utf-8")
            return sc.validation_state(td, judge)

    def test_37_red_lines_declared_and_held(self):
        """AM-2 (D-665, D-693): a declared red line held when its proposal was removed from the next text, not
        held when it passed (kept or changed), open (its own count, never folded into held) when still
        bracketed, from the key's fate; each arm's agreement with held on the red lines it extracted (reject or
        counter holds the line); a piece with no stance counted no_stance and a disagreement (order 82); every
        red line with its source, "from the document" (D-664); a cell under 5 items its count alone."""
        def next_a2(text):
            b = copy.deepcopy(BUILD)
            b["next_articles"]["A2"] = text
            return b
        removed = next_a2("A fund is established.")
        kept = next_a2("A fund is established. Contributions shall be mandatory for developed parties and assessed annually.")
        still_open = next_a2("A fund is established. [Contributions shall be mandatory for developed parties and assessed annually]")
        builds = {"changed": BUILD, "removed": removed, "kept": kept, "open": still_open}
        fields = ("declared", "held", "not_held", "open", "extracted", "on_declared", "on_open", "agree", "no_stance")

        def observe(value=GOOD_REPLY):
            out = {}
            for name, b in builds.items():
                item, key = built(b)
                row = key["proposals"]["P-A2-1"]
                part = sc.red_line_part(item, key, reply_of(item, value))
                out[name] = (row["fate"], sc.red_line_outcome(row), sc.held_red_line(row), sc.red_line_source(row),
                             tuple(part[f] for f in fields))
            return out
        doc = "from the document"
        want = {"changed": ("changed", "not_held", False, doc, (1, 0, 1, 0, 1, 1, 0, 0, 0)),
                "removed": ("removed", "held", True, doc, (1, 1, 0, 0, 1, 1, 0, 1, 0)),
                "kept": ("kept", "not_held", False, doc, (1, 0, 1, 0, 1, 1, 0, 0, 0)),
                "open": ("open", "open", None, doc, (1, 0, 0, 1, 1, 0, 1, 0, 0))}
        self.assertEqual(observe(), want)
        # Neutralised: changed dropped from the let-through fates, so a changed proposal is undetermined.
        self.prove("red_line_changed_is_not_held", observe, want,
                   lambda: patch.object(sc, "LET_THROUGH_FATES", ("kept",)))
        # Neutralised: changed moved into the held fates.
        self.prove("red_line_changed_never_held", observe, want,
                   lambda: patch.object(sc, "HELD_FATES", ("removed", "changed")))
        # Neutralised: open folded into held.
        self.prove("red_line_open_its_own_count", observe, want,
                   lambda: patch.object(sc, "HELD_FATES", ("removed", "open")))
        # Neutralised: the arm's advice read as holding the line when it accepts.
        self.prove("arm_agreement_with_held_by_its_stance", observe, want,
                   lambda: patch.object(sc, "HOLDING_STANCES", ("accept",)))
        # Standing order 82: a piece with no stance is counted no_stance and is a disagreement, never dropped.
        unstated = copy.deepcopy(GOOD_REPLY)
        del unstated["proposals"][2]["stance"]
        bare = lambda: {n: v[4] for n, v in observe(unstated).items() if n in ("changed", "removed")}
        bare_want = {"changed": (1, 0, 1, 0, 1, 1, 0, 0, 1), "removed": (1, 1, 0, 0, 1, 1, 0, 0, 1)}
        self.assertEqual(bare(), bare_want)
        # Neutralised: a missing stance treated as a given one (it then agrees where the line was let through).
        self.prove("no_stance_counted_as_a_disagreement", bare, bare_want,
                   lambda: patch.object(sc, "ANSWERED_STANCES", sc.ANSWERED_STANCES + (None,)))
        # A key built before the source field reads as from the document; an undeclared source is refused.
        row = dict(built()[1]["proposals"]["P-A2-1"])
        self.assertEqual(sc.red_line_source({k: v for k, v in row.items() if k != "red_line_source"}), "from the document")
        with self.assertRaises(ValueError):
            sc.red_line_source(dict(row, red_line_source="the operator"))
        # The report: 5 items with a red line give the record's held share and each arm's agreement; 4 their count.
        def report(n):
            items, keys = {}, {}
            order = (BUILD, removed, kept, still_open)
            for k in range(n):
                b = dict(copy.deepcopy(order[k % 4]), item_id="fx-rl-%d" % k)
                items[b["item_id"]], keys[b["item_id"]] = sc.build_item(b)
            rows = lambda group: {"rows": [{"form": "advice", "group": group, "item_id": i, "reply": reply_of(items[i]),
                                            "audit": {}} for i in items]}
            return sc.report(items, keys, {"B1": (rows("b1"), "b1"), "system": (rows("system_advice"), "system_advice")},
                             resamples=20)["red_lines"]
        five = lambda: (report(5)["record"], report(5)["by_arm"]["B1"])
        got = five()
        self.assertEqual(got[0], {"items": 5, "declared": 5, "held": 1, "not_held": 3, "open": 1, "undetermined": 0,
                                  "held_share": 0.25, "by_source": {"from the document": 5}})
        self.assertEqual((got[1]["on_declared"], got[1]["on_open"], got[1]["agree_with_held"], got[1]["agreement"]),
                         (4, 1, 1, 0.25))
        self.assertEqual(report(4)["record"], {"items": 4})
        self.prove("red_line_cell_under_5_items_its_count_alone", lambda: report(4)["record"], {"items": 4},
                   lambda: patch.object(sc, "MIN_CELL", 4))

    def test_40_frozen_set_never_rebuilt(self):
        """D-693: a set whose freeze is recorded (the pilot) is read as it is: build refuses it, since a rebuild
        would write red_line_source into its keys and change its set_sha256; its keys, built before the field,
        are read by the scorer unchanged."""
        with setdir() as root:
            # The key as the pilot's were built, before the source field.
            path = root / "items" / BUILD["item_id"] / "key.json"
            old = json.loads(path.read_text(encoding="utf-8"))
            for row in old["proposals"].values():
                row.pop("red_line_source")
            path.write_text(json.dumps(old), encoding="utf-8")
            self.assertEqual(sc.read_keys(root)[BUILD["item_id"]]["proposals"]["P-A2-1"].get("red_line_source"), None)
            self.assertEqual(sc.red_line_source(sc.read_keys(root)[BUILD["item_id"]]["proposals"]["P-A2-1"]),
                             "from the document")
            (root / sc.FROZEN_RECORD).write_text(json.dumps({"set_sha256": sc.set_digest(root)[1]}), encoding="utf-8")
            def observe():
                before = sc.set_digest(root)[1]
                try:
                    sc.build_set(root, count=WORDS)
                    return "built", sc.set_digest(root)[1] == before
                except ValueError as exc:
                    return str(exc)[:30], sc.set_digest(root)[1] == before
            want = ("refused: the set is frozen (FR", True)
            self.assertEqual(observe(), want)
            # Neutralised: the guard looks for another record, so the frozen set is built again.
            self.prove("frozen_set_never_rebuilt", observe, want,
                       lambda: patch.object(sc, "FROZEN_RECORD", "FREEZE.not_this.json"))

    def test_41_unbracketed_options_refused(self):
        """#281 gap 8: an unagreed article that numbers two or more options and holds no bracket is refused
        visibly, the item and article named, and the set is not written; it is never read as one proposal nor
        split by guess. One option marker, bracketed options, an agreed article and a word "option" without a
        number build as before."""
        def with_a2(text, agreed=False):
            b = copy.deepcopy(BUILD)
            b["articles"][1] = dict(b["articles"][1], text=text, agreed=agreed)
            return b
        two = with_a2("A fund is established.\n\nOption 1: Contributions shall be mandatory for developed parties.\n"
                      "Option 2: Contributions shall be voluntary and reviewed every five years.")
        inline = with_a2("A fund is established. Alt 1) Contributions are mandatory. Alt 2) Contributions are voluntary.")
        fine = {"one marker": with_a2("A fund is established.\n\nOption 1: Contributions shall be mandatory."),
                "bracketed": with_a2("A fund is established.\n\n[Option 1: Contributions shall be mandatory] "
                                     "[Option 2: Contributions shall be voluntary]"),
                "agreed": with_a2("Option 1: a fund. Option 2: no fund.", agreed=True),
                "prose": with_a2("A fund is established, with the option to contribute and an alternative route.")}

        def observe():
            out = {}
            for name, b in (("two", two), ("inline", inline)):
                with tempfile.TemporaryDirectory(prefix="negadv_opt_") as td:
                    root = Path(td) / "set"
                    (root / "build" / b["item_id"]).mkdir(parents=True)
                    (root / "build" / b["item_id"] / "build.json").write_text(json.dumps(b), encoding="utf-8")
                    (root / "build" / b["item_id"] / "SOURCE.md").write_text("fixture source, invented\n", encoding="utf-8")
                    try:
                        sc.build_set(root, count=WORDS)
                        out[name] = ("built", sorted(p["id"] for a in json.loads(
                            (root / "items" / b["item_id"] / "item.json").read_text(encoding="utf-8"))["articles"]
                            if a["id"] == "A2" for p in a["proposals"]))
                    except ValueError as exc:
                        out[name] = (str(exc).split(" numbers ")[0], (root / "items").exists())
            for name, b in fine.items():
                out[name] = len([p for p in built(b)[0]["articles"][1]["proposals"]])
            return out
        want = {"two": ("refused: fx-k2-alpha: article A2", False), "inline": ("refused: fx-k2-alpha: article A2", False),
                "one marker": 1, "bracketed": 2, "agreed": 0, "prose": 1}
        self.assertEqual(observe(), want)
        # Neutralised: the refusal's floor raised past any article, so both are read as one proposal again.
        self.prove("unbracketed_options_refused_visibly", observe, want,
                   lambda: patch.object(sc, "UNBRACKETED_OPTIONS_MIN", 99))
        # Neutralised: the marker's number not read, so no option is counted.
        self.prove("unbracketed_options_counted_by_number", observe, want,
                   lambda: patch.object(sc, "_NUMBERED_OPTION", re.compile(r"(?!x)x(\d)?(\d)?")))

    def test_38_code_digest_of_lf_bytes(self):
        """#262 gap 2: the power record's code digest is of the scorer's LF bytes, the same on a CRLF checkout
        and in the commit; a record of other code bytes is refused, so the record is made again for this code."""
        lf = sc.Path(sc.__file__).read_bytes().replace(b"\r\n", b"\n")
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "lf.py").write_bytes(lf)
            (Path(td) / "crlf.py").write_bytes(lf.replace(b"\n", b"\r\n"))
            observe = lambda: (sc.code_sha256(Path(td) / "crlf.py") == sc.code_sha256(Path(td) / "lf.py")
                               == sc.hashlib.sha256(lf).hexdigest() == sc.code_sha256())
            self.assertTrue(observe())
            self.prove("code_digest_of_lf_bytes", observe, True, lambda: patch.object(sc, "CODE_EOL", (b"\r\n", b"\r\n")))
            kw = self.scoring_inputs({"fx-k2-alpha": built()[1]})
            stale = dict(kw["power"], code_sha256=sc.hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest())
            text = json.dumps(stale)
            conf = dict(kw["configuration"], power_record_sha256=sc._sha(text))
            self.assertTrue(sc.refuse(**dict(kw, power=stale, power_text=text, configuration=conf)).startswith(
                "the power record is not of this set"))

    def test_39_command_line_route(self):
        """#262 gap 3: main() of score_neg_advisor.py driven with freeze --export-records, then --vectors and
        --records on the merged vectors, gives the in-process freeze's FREEZE.json and cloud subset byte for
        byte; --vectors without --records is refused. (freeze_negotiation_set.py's main: negotiation_measure_checks
        test_19k.)"""
        import hashlib
        import shutil
        import numpy as np
        fz = sc.fz()
        er = fz._embed_records()

        def onehot(texts):
            out = np.zeros((len(texts), 1024), dtype=np.float32)
            for i, t in enumerate(texts):
                out[i, int(hashlib.sha256(str(t).encode("utf-8")).hexdigest()[:8], 16) % 1024] = 1.0
            return out
        embedder = lambda texts, batch_size: onehot(texts)
        embedder.dim, embedder.max_seq_length = 1024, 8192

        def observe():
            with setdir() as root, tempfile.TemporaryDirectory(prefix="negadv_main_") as td:
                td = Path(td)
                corpus = td / "corpus.md"
                corpus.write_text("\n\n".join(" ".join("filler%d word%d" % (k, i) for i in range(12)) for k in range(4)),
                                  encoding="utf-8")
                listed = td / "corpora.txt"
                listed.write_text("# fixture list\n%s\n" % corpus, encoding="utf-8")
                other = td / "copy"
                shutil.copytree(root, other)
                with redirect_stdout(io.StringIO()) as printed:
                    code = sc.main(["freeze", "--set", str(other), "--corpora", str(listed), "--export-records",
                                    str(td / "export")])
                exported = json.loads(printed.getvalue())
                er.build(td / "export" / "records.jsonl", td / "parts")
                pairs = []
                for n, prompts in enumerate(sorted((td / "parts").glob("part*/replay_prompts.json"))):
                    er.run(prompts, td / ("ev%d" % n), embedder=embedder, run_id="fixture")
                    pairs.append((td / ("ev%d" % n), prompts))
                er.merge(pairs, td / "export" / "laptop", td / "merged", require_complete=True)
                with redirect_stdout(io.StringIO()):
                    refused = sc.main(["freeze", "--set", str(other), "--corpora", str(listed), "--vectors", str(td / "merged")])
                    code2 = sc.main(["freeze", "--set", str(other), "--corpora", str(listed), "--vectors", str(td / "merged"),
                                     "--records", str(td / "export" / "records.jsonl")])
                encode = fz.vectors_encoder(td / "merged", td / "export" / "records.jsonl")
                sc.freeze(root, [corpus], encode=fz.formed(onehot), model=encode.route, progress=lambda line: None)
                same = all((root / f).read_bytes() == (other / f).read_bytes() for f in ("FREEZE.json", sc.SUBSET_FILE))
                texts = [json.loads(l)["text"] for l in (td / "export" / "records.jsonl").read_text(encoding="utf-8").splitlines()]
                return {"codes": (code, refused, code2), "rows": exported["rows"] > 0,
                        "forecast": "forecast_minutes" in exported, "identical": same,
                        "vectors_identical": encode(texts).tobytes() == fz.formed(onehot)(texts).tobytes()}
        got = observe()
        self.assertEqual(got, {"codes": (0, 2, 0), "rows": True, "forecast": True, "identical": True,
                               "vectors_identical": True})
        real = er.embed_batched
        # Neutralised: the instance's pass hands each chunk's vectors back in reverse order (a misplaced row).
        self.prove("advisor_main_export_and_vectors_equal_in_process", observe, got,
                   lambda: patch.object(er, "embed_batched", lambda embed, texts, rule=er.BATCH_RULE: real(embed, texts, rule)[::-1].copy()))

    def test_42_m10_open_point_detection(self):
        """AM-3: M10's key class from the fate, the prediction from the stance, a miss by its reason, Macro-F1
        over the two classes (hand-computed), beside M1 per arm with its interval, the system-minus-B1
        difference, and never in the claims or the bar."""
        still_open = copy.deepcopy(BUILD)
        still_open["next_articles"]["A2"] = ("A fund is established. "
                                             "[Contributions shall be mandatory for developed parties and assessed annually]")
        # BUILD's fates: P-A1-1 kept, P-A1-2 removed, P-A2-1 changed; still_open's P-A2-1 open.
        wrong = copy.deepcopy(GOOD_REPLY)
        wrong["proposals"][0]["stance"] = "counter"   # P-A1-1, kept: settled, predicted movable
        del wrong["proposals"][1]["stance"]           # P-A1-2, removed: settled, no stance, a miss

        def observe():
            out = {}
            for name, b, value in (("good", BUILD, GOOD_REPLY), ("wrong", BUILD, wrong), ("open", still_open, GOOD_REPLY)):
                item, key = built(b)
                rows, misses = sc.open_point_part(key, reply_of(item, value))
                out[name] = (sorted("%s>%s:%d" % (k[0], k[1], v) for k, v in rows.items()), dict(misses), sc.macro_f1_two(rows))
            return out
        S, M, N = sc.SETTLED, sc.MOVABLE, sc.NO_ANSWER
        # Hand-computed. wrong: movable tp 1, fp 1, fn 0, F1 2/3; settled tp 0, fp 0, fn 2, F1 0; Macro-F1 1/3.
        want = {"good": (["movable>movable:1", "settled>settled:2"], {}, 1.0),
                "wrong": (["movable>movable:1", "settled>movable:1", "settled>no_answer:1"], {"no_stance": 1},
                          (2 / 3 + 0) / 2),
                "open": (["movable>movable:1", "settled>settled:2"], {}, 1.0)}
        self.assertEqual(observe(), want)
        # Neutralised: changed dropped from the movable fates (P-A2-1 changed is then never scored).
        self.prove("m10_changed_is_movable", observe, want, lambda: patch.object(sc, "MOVABLE_FATES", ("open",)))
        # Neutralised: open dropped from the movable fates.
        self.prove("m10_open_is_movable", observe, want, lambda: patch.object(sc, "MOVABLE_FATES", ("changed",)))
        # Neutralised: kept moved to the movable fates.
        self.prove("m10_kept_is_settled", observe, want,
                   lambda: patch.object(sc, "MOVABLE_FATES", ("open", "changed", "kept")))
        # Neutralised: a counter no longer predicts movable (every counter then a miss by stance_not_declared).
        self.prove("m10_counter_predicts_movable", observe, want, lambda: patch.object(sc, "MOVABLE_STANCES", ()))
        # Neutralised: the figure over the movable class alone (the wrong reply then 2/3, not 1/3).
        self.prove("m10_macro_f1_over_the_two_classes", observe, want, lambda: patch.object(sc, "M10_CLASSES", (M,)))
        # A class neither in the key nor predicted leaves the figure undefined; no reply at all is a miss each.
        self.assertIsNone(sc.macro_f1_two(Counter({(M, M): 2})))
        self.assertEqual(sc.macro_f1_two(Counter({(S, M): 1, (M, M): 1})), (2 / 3 + 0) / 2)
        item, key = built()
        self.assertEqual(sc.open_point_part(key, None), (Counter({(S, N): 2, (M, N): 1}), Counter({"no_reply": 3})))
        # The system's withheld piece is a miss by "withheld", told apart from a piece never given.
        given = reply_of(item)
        kept = dict(given, proposals={p: e for p, e in given["proposals"].items() if p != "P-A1-2"})
        self.assertEqual(sc.open_point_part(key, kept, given)[1], Counter({"withheld": 1}))
        self.assertEqual(sc.open_point_part(key, kept)[1], Counter({"no_piece": 1}))
        # Hand-computed: movable tp 1, F1 1; settled tp 1, fn 1, F1 2/3; Macro-F1 5/6.
        self.assertEqual(sc.macro_f1_two(sc.open_point_part(key, kept, given)[0]), (1.0 + 2 / 3) / 2)

        # The report: 5 headline items, B1 the wrong reply (its stance drops counted beside), the system the good.
        def report(n):
            items, keys = {}, {}
            for k in range(n):
                b = dict(copy.deepcopy(BUILD), item_id="fx-m10-%d" % k)
                items[b["item_id"]], keys[b["item_id"]] = sc.build_item(b)
            rows = lambda group, value, drops: {"rows": [
                {"form": "advice", "group": group, "item_id": i, "reply": reply_of(items[i], value), "audit": {},
                 "drops": drops} for i in items]}
            return sc.report(items, keys, {"B1": (rows("b1", wrong, {"proposals.stance": {"not_declared": 1}}), "b1"),
                                           "system": (rows("system_advice", GOOD_REPLY, {}), "system_advice")},
                             resamples=20)
        rep = report(5)
        block = rep["M10"]
        b1, system = block["by_arm"]["B1"], block["by_arm"]["system"]
        got = (rep["figures"]["B1"]["M10"]["estimate"], rep["figures"]["system"]["M10"]["estimate"],
               b1["figure"] == rep["figures"]["B1"]["M10"], b1["rows"], b1["key"], b1["predicted"], b1["misses"],
               b1["stance_drops"], system["misses"], round(block["system_minus_B1"]["difference"], 12),
               "shown" in block["system_minus_B1"], block["status"], "M10" in rep["claims"])
        want_rep = (1 / 3, 1.0, True, 15, {M: 5, S: 10}, {M: 10, S: 0, N: 5}, {"no_stance": 5},
                    {"not_declared": 5}, {}, round(1.0 - 1 / 3, 12), False, sc.M10_STATUS, False)
        self.assertEqual(got, want_rep)
        self.assertEqual(rep["figures"]["B1"]["M10"]["items"], 5)
        self.assertIn("lower", rep["figures"]["B1"]["M10"])
        # The no-stance miss counted in the report; neutralised: no_stance left out of the declared reasons.
        misses = lambda: report(5)["M10"]["by_arm"]["B1"]["misses"]
        self.prove("m10_no_stance_miss_counted", misses, {"no_stance": 5},
                   lambda: patch.object(sc, "M10_MISSES", tuple(r for r in sc.M10_MISSES if r != "no_stance")))
        # A cell under 5 items is its count alone.
        self.assertEqual(report(4)["M10"]["by_arm"]["B1"], {"items": 4})
        self.prove("m10_cell_under_5_items_its_count_alone", lambda: report(4)["M10"]["by_arm"]["B1"], {"items": 4},
                   lambda: patch.object(sc, "MIN_CELL", 4))
        # Never in the claims or the bar: M10 neutralised leaves both as they were.
        with patch.object(sc, "MOVABLE_STANCES", ()):
            other = report(5)
        self.assertNotEqual(other["figures"]["system"]["M10"]["estimate"], 1.0)
        self.assertEqual((other["claims"], other["bar"]), (rep["claims"], rep["bar"]))


def check():
    NegAdvisorChecks.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(NegAdvisorChecks).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, no model and no item: fate by the plan's 5-gram "
                    "shares, proposal positions first, binding and dropped states, alignment by proposal and the computed "
                    "configuration, no_answer always wrong and Macro-F1 over the key's classes, the system's withholding "
                    "and checks that never read the key, the red-line mandate check, a claim only when BCa, jackknife and "
                    "permutation agree and A1 only with its power, no score without a committed opening, prompts held to "
                    "their rendering, derived audits held to the pass's SHA-256, every piece audited, the replay hook, "
                    "per-item rows outside the repository, games by construction, a blind judge, the power simulation, "
                    "Phi-4 for the judge and validator, the cloud subset (D-606), bar lines 1 and 4 and M9's validation, "
                    "the configuration's bindings, small cells and outputs kept apart, M9's withheld counters, the "
                    "token budget, terms of use and SOURCE.md, each opening's alpha, the judge's and the validator's models at "
                    "score time, the validator's binding, the three cloud-subset refusals, and the validator answering an "
                    "article id (D-617), the freeze passing the accepted kinds (D-618), the freeze's vectors route, "
                    "and (D-663) every saved reply read again whatever its form by tools/reread_replies.py (the last "
                    "object, several counted), what is still dropped counted by field and reason in each row and the "
                    "score report, and answers not read by it refused; and (D-672) the judge and the system auditor decide by "
                    "fixed choices read as their settled label, the system's advice and the validator generate under "
                    "the item's schema constraint, B1 freely; and AM-1 (a single-class field at the bar only at 100 "
                    "percent, M9 alike), AM-2 (red lines declared and held from the fate, each arm's agreement with "
                    "held, open its own count, no stance a disagreement, the source field), the code digest of LF bytes, "
                    "main() through the vectors route and a frozen set never built again, and (#281 gap 8) an "
                    "article numbering options with no bracket refused visibly, never split by guess, and (AM-3) M10 "
                    "open-point detection, movable or settled from the fate and the stance, no stance a miss by its "
                    "reason, Macro-F1 over the two classes beside M1, indicator only, never in the claims or the bar"
                    % len(NegAdvisorChecks.evidence))


def main():
    status, detail = check()
    for proof in NegAdvisorChecks.evidence:
        print(proof["name"], proof["status"])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
