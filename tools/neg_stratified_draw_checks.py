#!/usr/bin/env python3
"""Check 644 (lane neg-stratified-draw): the synthetic sets' declared stratified draw by party structure
(D-711 items 2 and 3, D-715 item 1, the 20:32 party-structure instruction, D-732; config/neg_synth.json
`split.strata_rule`, tools/neg_synth.py `check_strata`, `stratum_of`, `select_strata`).

Six proofs, each neutralise, fail, restore, pass (scripts/effect_proof.py):

1. stratified cards hold their stratum: every card of the declared top-up set `validation_strata`, drawn on a
   fixture base, has the party structure the scorer computes from its parties equal to its seed's stratum, the
   strata are drawn equally, and each stratum holds both record kinds about half and half;
2. a set without strata draws as before: its parties follow the former rule (the number from `parties`, each
   kind from `coalition_share`, on the seed's structure stream) and its card records no stratum;
3. `select_strata` keeps per structure the first declared count in seed order that no screen dropped, never
   borrows from another structure, and names the shortfall by structure;
4. the split refuses a malformed stratified set (a top-up of an undeclared or stratified set, of another
   purpose, without strata; a structure the scorer does not know; a target other than the sum; fewer than two
   seeds per kept item), keeps exactly one plain validation set, and its ranges stay disjoint;
5. the command line: `draw --set validation_strata` writes stratified cards into the set's card folder (found
   from the set name, D-716), `coverage --set validation_strata` passes on them, and `set-check` counts the
   built items by structure and record kind, counts only;
6. a fix's own fresh sets (D-789, `fix`, `check_fix`; lane neg-c4-measure-prep): the declared C4 validation and
   pilot sets pass the split without being counted as its one validation set or a pilot, a second validation set
   of one fix, a fix set without its decision, with a malformed id, of the development purpose, topping up or
   topped up is refused, their names are of the label pass's set-name form, and c4val_1's cards hold all four
   declared structures.

No model, no network, no real item: the seed base is a fixture, every file goes to a temporary folder outside
the repository.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_synth as ns  # noqa: E402
import neg_synth_checks as nsc  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

CFG = ns.load_config()
SET = "validation_strata"
BASE = 2 ** 41 + 6440
sna = ns.sna


def _strata_set(cfg=CFG):
    return ns.split_set(cfg, SET)


def _cards(cfg, name, base, limit=None):
    s = ns.split_set(cfg, name)
    out = []
    for seed in ns.seeds_for(cfg, name, base)[:limit]:
        try:
            out.append(ns.sample_card(seed, cfg, version="fixture", stratum=ns.stratum_of(seed, s)))
        except ns.SeedRefused:
            pass
    return out


# 1 ---------------------------------------------------------------------------


def _observe_strata():
    s = _strata_set()
    try:
        cards = _cards(CFG, SET, BASE, limit=60)
    except ValueError:
        return {"refused": True}
    held = Counter(sna.structure_of(c["structure"]["parties"]) for c in cards)
    kinds = {st: Counter(c["structure"]["record_kind"] for c in cards if c.get("stratum") == st)
             for st in ns.strata_order(s)}
    return {"each_card_in_its_stratum": all(c.get("stratum") == ns.stratum_of(c["seed"], s) ==
                                            sna.structure_of(c["structure"]["parties"]) for c in cards),
            "strata_drawn": sorted(held), "equal": len(set(held.values())) == 1,
            "both_kinds_each": all(min(k.get(x, 0) for x in sna.RECORD_KINDS) >= 5 for k in kinds.values())}


def proof_strata():
    expected = {"each_card_in_its_stratum": True, "strata_drawn": sorted(_strata_set()["strata"]),
                "equal": True, "both_kinds_each": True}
    plain = ns.party_kinds
    return ("stratified_cards_hold_their_stratum", _observe_strata, expected,
            lambda: patch.object(ns, "party_kinds", lambda rng, d, structure=None: plain(rng, d, None)))


# 2 ---------------------------------------------------------------------------


def _former_kinds(seed, cfg):
    """The former party draw, written out: round k, then the number of parties, then each kind."""
    rng = ns._rng(seed, "structure")
    d = cfg["distributions"]
    ns._pick(rng, d["round_k"])
    n = int(ns._pick(rng, d["parties"]))
    return ["coalition" if rng.random() < d["coalition_share"] else "single" for _ in range(n)]


def _observe_plain():
    s = ns.split_set(CFG, "validation")
    seeds = ns.seeds_for(CFG, "validation", BASE)[:40]
    same = all([p["kind"] for p in ns.draw_structure(x, CFG, ns.stratum_of(x, s))["parties"]] ==
               _former_kinds(x, CFG) for x in seeds)
    card = ns.sample_card(seeds[0], CFG, version="fixture", stratum=ns.stratum_of(seeds[0], s))
    return {"former_rule": same, "no_stratum": "stratum" not in card and ns.stratum_of(seeds[0], s) is None}


def proof_plain():
    expected = {"former_rule": True, "no_stratum": True}
    return ("a_set_without_strata_draws_as_before", _observe_plain, expected,
            lambda: patch.object(ns, "stratum_of", lambda seed, s: sna.THREE_OR_MORE))


# 3 ---------------------------------------------------------------------------


def _observe_select():
    cards = _cards(CFG, SET, BASE, limit=30)
    by = {st: [c for c in sorted(cards, key=lambda c: c["seed"]) if c["stratum"] == st]
          for st in ns.strata_order(_strata_set())}
    strata = {sna.TWO_SINGLES: 2, sna.TEAMS: 3, sna.ONE_VS_COALITION: 20}
    dropped = {by[sna.TWO_SINGLES][0]["item_id"]}
    with tempfile.TemporaryDirectory() as tmp:
        for c in cards:
            folder = Path(tmp) / "build" / c["item_id"]
            folder.mkdir(parents=True)
            (folder / "build.json").write_text("{}", encoding="utf-8")
        out = ns.select_strata(cards, tmp, strata, dropped)
    want_kept = ({c["item_id"] for c in by[sna.TWO_SINGLES][1:3]} | {c["item_id"] for c in by[sna.TEAMS][:3]}
                 | {c["item_id"] for c in by[sna.ONE_VS_COALITION]})
    return {"kept_first_in_seed_order": set(out["kept"]) == want_kept,
            "seed_order": out["kept"] == [c["item_id"] for c in sorted(cards, key=lambda c: c["seed"])
                                          if c["item_id"] in want_kept],
            "structures": out["structures"],
            "short_by_structure": out["short_by_structure"], "dropped": out["dropped"]}


def proof_select():
    n_one = 10  # the fixture's 30 seeds give 10 per stratum, so one_vs_coalition is short of 20 by 10
    expected = {"kept_first_in_seed_order": True, "seed_order": True,
                "structures": {sna.TWO_SINGLES: 2, sna.TEAMS: 3, sna.ONE_VS_COALITION: n_one},
                "short_by_structure": {sna.ONE_VS_COALITION: 20 - n_one}, "dropped": 1}
    plain = ns.select

    def borrowing(cards, set_dir, strata, dropped=()):
        out = plain(cards, set_dir, sum(strata.values()), dropped)
        return dict(out, structures={}, short_by_structure={})

    return ("select_keeps_each_structure_its_count", _observe_select, expected,
            lambda: patch.object(ns, "select_strata", borrowing))


# 4 ---------------------------------------------------------------------------


def _with_set(**change):
    cfg = copy.deepcopy(CFG)
    for s in cfg["split"]["sets"]:
        if s["name"] == SET:
            s.update(change)
            for k, v in list(s.items()):
                if v is None:
                    del s[k]
    return cfg


def _refused(cfg):
    try:
        ns.check_split(cfg)
    except ValueError:
        return True
    return False


def _observe_split():
    second_validation = copy.deepcopy(CFG)
    second_validation["split"]["sets"].append({"name": "validation_b", "purpose": "validation", "target": 10,
                                               "drawn": 20, "offset": 15000})
    overlap = _with_set(offset=10040)
    return {"declared_plan": not _refused(CFG),
            "undeclared_base": _refused(_with_set(tops_up="no_such_set")),
            "stratified_base": _refused(_with_set(tops_up=SET)),
            "other_purpose": _refused(_with_set(tops_up="dev_1")),
            "top_up_without_strata": _refused(_with_set(strata=None)),
            "unknown_structure": _refused(_with_set(strata={"bilateral": 10, "teams": 10, "two_singles": 10})),
            "target_not_sum": _refused(_with_set(target=29)),
            "too_few_seeds": _refused(_with_set(drawn=50)),
            "second_plain_validation": _refused(second_validation),
            "overlap": _refused(overlap)}


def proof_split():
    expected = {k: True for k in ("declared_plan", "undeclared_base", "stratified_base", "other_purpose",
                                  "top_up_without_strata", "unknown_structure", "target_not_sum", "too_few_seeds",
                                  "second_plain_validation", "overlap")}
    return ("the_split_refuses_a_malformed_stratified_set", _observe_split, expected,
            lambda: patch.object(ns, "check_strata", lambda s, by_name: None))


# 5 ---------------------------------------------------------------------------


def _small_cfg():
    return _with_set(target=6, drawn=12, strata={sna.TWO_SINGLES: 2, sna.TEAMS: 2, sna.ONE_VS_COALITION: 2})


def _observe_cli():
    small = _small_cfg()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "SEED_BASE.json"
        base.write_text(json.dumps({"schema": ns.SEED_BASE_SCHEMA, "base": BASE}), encoding="utf-8")
        env = {small["card_folder"]["root_env"]: tmp}
        outs = {}
        with patch.object(ns, "load_config", lambda path=None: small), patch.dict(os.environ, env):
            for cmd in (["draw", "--set", SET, "--seed-base", str(base), "--briefs", str(Path(tmp) / "briefs")],
                        ["coverage", "--set", SET]):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = ns.main(cmd)
                outs[cmd[0]] = (code, buf.getvalue())
            folder = ns.card_folder(small, SET)
            cards = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.card.json"))]
            set_dir = Path(tmp) / "sets" / SET
            for c in cards:
                problems, build = ns.validate(c, nsc.fixture_reply(c), small)
                if not problems:
                    ns.write_item(set_dir, c, build, small)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                outs["set-check"] = (ns.main(["set-check", "--set-dir", str(set_dir)]), "")
            built = json.loads(buf.getvalue().splitlines()[1].split(": ", 1)[1])
        cov = json.loads(outs["coverage"][1].splitlines()[0])
        return {"draw_exit": outs["draw"][0], "coverage_exit": outs["coverage"][0], "cards": len(cards),
                "stratum_recorded": all(c.get("stratum") == sna.structure_of(c["structure"]["parties"])
                                        for c in cards),
                "structures": cov["structure"], "set_check_exit": outs["set-check"][0], "built": built,
                "no_seed_printed": str(BASE) not in outs["draw"][1] + outs["coverage"][1]}


def proof_cli():
    half = {k: 2 for k in sna.RECORD_KINDS}
    expected = {"draw_exit": 0, "coverage_exit": 0, "cards": 12, "stratum_recorded": True,
                "structures": {sna.TWO_SINGLES: 4, sna.TEAMS: 4, sna.ONE_VS_COALITION: 4}, "set_check_exit": 0,
                "built": {sna.TWO_SINGLES: half, sna.TEAMS: half, sna.ONE_VS_COALITION: half},
                "no_seed_printed": True}
    return ("draw_and_coverage_read_the_strata_from_the_set_name", _observe_cli, expected,
            lambda: patch.object(ns, "stratum_of", lambda seed, s: None))


# 6 ---------------------------------------------------------------------------
# D-789 (lane neg-c4-measure-prep): a fix's own fresh validation and pilot sets (`fix`, ns.check_fix).

FIX_SETS = ("c4val_1", "c4pilot_1")


def _with_fix_set(name, **change):
    cfg = copy.deepcopy(CFG)
    for s in cfg["split"]["sets"]:
        if s["name"] == name:
            s.update(change)
            for k, v in list(s.items()):
                if v is None:
                    del s[k]
    return cfg


def _observe_fix():
    second = copy.deepcopy(CFG)
    second["split"]["sets"].append({"name": "c4val_2", "purpose": "validation", "fix": "C4", "fix_decision": "D-789",
                                    "target": 10, "drawn": 20, "offset": 13000})
    top_up_of_fix = _with_set(tops_up="c4val_1")
    declared = {s["name"]: s for s in CFG["split"]["sets"]}
    try:
        s = ns.split_set(CFG, "c4val_1")
        strata_each = sorted(Counter(c.get("stratum") for c in _cards(CFG, "c4val_1", BASE, limit=40))) == \
            sorted(ns.strata_order(s))
    except ValueError:
        strata_each = False
    return {"declared_plan": not _refused(CFG),
            "fix_sets_declared": all(declared.get(n, {}).get("fix") == "C4" for n in FIX_SETS),
            "not_the_one_validation_set": _refused(_with_fix_set("c4val_1", fix=None, fix_decision=None,
                                                                 strata=None, target=40, drawn=80)),
            "second_fix_validation": _refused(second),
            "fix_without_decision": _refused(_with_fix_set("c4pilot_1", fix_decision=None)),
            "fix_bad_id": _refused(_with_fix_set("c4pilot_1", fix="c4")),
            "fix_development": _refused(_with_fix_set("c4pilot_1", purpose="development")),
            "fix_tops_up": _refused(_with_fix_set("c4pilot_1", tops_up="pilot_1")),
            "topped_up_fix": _refused(top_up_of_fix),
            "label_pass_names": all(ns_label_name(n) for n in FIX_SETS),
            "strata_each": strata_each}


def ns_label_name(name):
    """The label pass reads a sheets file only for a set name of its form (neg_synth_label_pass.SET_NAME)."""
    import re
    text = (ROOT / "benchmark" / "baselines" / "neg_synth_label_pass.py").read_text(encoding="utf-8")
    form = re.search(r'SET_NAME = re\.compile\(r"([^"]+)"\)', text).group(1)
    return bool(re.match(form, name))


def proof_fix():
    expected = {k: True for k in ("declared_plan", "fix_sets_declared", "not_the_one_validation_set",
                                  "second_fix_validation", "fix_without_decision", "fix_bad_id", "fix_development",
                                  "fix_tops_up", "topped_up_fix", "label_pass_names", "strata_each")}
    return ("a_fix_declares_its_own_fresh_sets", _observe_fix, expected,
            lambda: patch.object(ns, "check_fix", lambda s: None))


PROOFS = (proof_strata, proof_plain, proof_select, proof_split, proof_cli, proof_fix)


def run_check():
    proofs = [p() for p in PROOFS]
    for name, observe, expected, neutralise in proofs:
        prove_effect(name=name, validate=lambda: True, observe=observe,
                     check=lambda observe=observe, expected=expected, name=name: (
                         "PASS" if observe() == expected else "FAIL", name),
                     neutralise=neutralise)
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, no model and no item: stratified cards hold "
                    "their stratum, a plain set draws as before, select keeps each structure its count, the split "
                    "refuses a malformed stratified set, draw and coverage read the strata from the set name, a fix "
                    "declares its own fresh sets" % len(proofs))


if __name__ == "__main__":
    print(run_check())
