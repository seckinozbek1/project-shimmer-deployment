#!/usr/bin/env python3
"""Check 687 (lane/neg-round2-d798, D-843; docs/loop/stages/NEG_ROUND2_D798.md): the D-798 validation pool split into
parts by the seeded rule of config/neg_synth.json `split.parts_rule`, frozen before any run.

On invented cards and build folders (no item, no key, no role folder, no model):

1. balanced: a pool shaped like validation_strata plus validation (three large structures and a small fourth) gives
   max(4, pool // 35) parts; every part but the spare holds at least 5 of each structure it holds, part 1 holds every
   structure that can be held, record kinds within one of each other per structure across the parts holding it, part
   sizes within a few items; the same pool gives the same digests, another seed other members.
2. small_to_spare: a structure with fewer than 5 items goes to the spare part alone and is named.
3. select_all: a pool set keeps every built item no screen dropped, with no target cap; a set outside the pool keeps
   its declared strata as before.
4. rule_checked: the shipped rule reads; a missing key, three parts, an undeclared pool set are refused.
5. label_name: the label pass's set-name form takes validation, validation_strata and c4val_1, refuses an upper-case
   name, a hyphen and a leading underscore.
6. cli: `split-parts` end to end on fixture cards: the parts file holds ids, the counts file none; a pool missing a
   set and a kept file that is not a whole-pool selection are refused.

Run as built (passes), neutralised twice (the per-structure floor not applied; dropped items kept), each must fail,
restored and run again (passes).
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
for _p in (str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_optional_checks as noc  # noqa: E402
import neg_synth as ns  # noqa: E402
import neg_synth_label_pass as lp  # noqa: E402

with_source = noc.with_source


def caught(function):
    try:
        return function()
    except (Exception, SystemExit) as exc:     # a refusal or a neutralised run's error is its observation
        return "raised " + type(exc).__name__
PARTIES = {"two_singles": [{"id": "A", "kind": "single"}, {"id": "B", "kind": "single"}],
           "teams": [{"id": "A", "kind": "coalition"}, {"id": "B", "kind": "coalition"}],
           "one_vs_coalition": [{"id": "A", "kind": "single"}, {"id": "B", "kind": "coalition"}],
           "three_or_more": [{"id": "A", "kind": "single"}, {"id": "B", "kind": "single"}, {"id": "C", "kind": "single"}]}
KINDS = ("complete", "missing_notes")


def _cfg():
    return json.loads((ROOT / "config" / "neg_synth.json").read_text(encoding="utf-8"))


def _rule(**change):
    return dict(ns.parts_rule(_cfg()), **change)


def _iid(n):
    return "syn-%016x" % n


def _entries(shape):
    out, n = [], 1
    for st, count in shape.items():
        for j in range(count):
            out.append({"item_id": _iid(n), "set": "validation_strata" if st != "three_or_more" else "validation",
                        "structure": st, "record_kind": KINDS[j % 2]})
            n += 1
    return out


SHAPE = {"two_singles": 37, "teams": 32, "one_vs_coalition": 35, "three_or_more": 12}


def observe_balanced():
    rule = _rule()
    a, b = ns.split_parts(_entries(SHAPE), rule), ns.split_parts(_entries(SHAPE), rule)
    other = ns.split_parts(_entries(SHAPE), _rule(seed=rule["seed"] + 1))
    parts = a["parts"]
    floor_ok = all(v >= 5 for p in parts[:-1] for v in p["structures"].values())
    kinds_ok = True
    for st in SHAPE:
        holding = [p for p in parts if st in p["structures"]]
        for k in KINDS:
            vals = [p["cells"].get("%s/%s" % (st, k), 0) for p in holding]
            kinds_ok = kinds_ok and max(vals) - min(vals) <= 1
    sizes = [p["count"] for p in parts]
    digests_ok = all(p["sha256"] == hashlib.sha256("\n".join(p["items"]).encode("utf-8")).hexdigest() for p in parts)
    return {"parts": len(parts), "pool": a["pool"], "all_items": sorted(i for p in parts for i in p["items"]) ==
            sorted(e["item_id"] for e in _entries(SHAPE)), "floor": floor_ok, "kinds": kinds_ok,
            "part1_structures": sorted(parts[0]["structures"]), "spread": max(sizes) - min(sizes) <= 8,
            "same": [p["sha256"] for p in a["parts"]] == [p["sha256"] for p in b["parts"]],
            "seed_moves": [p["sha256"] for p in a["parts"]] != [p["sha256"] for p in other["parts"]],
            "digests": digests_ok, "uses": [p["use"] for p in parts][:1] + [parts[-1]["use"]]}


def expected_balanced():
    rule = _rule()
    return {"parts": 4, "pool": 116, "all_items": True, "floor": True, "kinds": True,
            "part1_structures": sorted(SHAPE), "spread": True, "same": True, "seed_moves": True, "digests": True,
            "uses": [rule["uses"]["1"], rule["uses"]["spare"]]}


def observe_small_to_spare():
    shape = {"two_singles": 30, "teams": 30, "one_vs_coalition": 30, "three_or_more": 4}
    out = ns.split_parts(_entries(shape), _rule())
    return {"spare_only": out["spare_only"], "where": [p["part"] for p in out["parts"] if "three_or_more" in p["structures"]],
            "floor": all(v >= 5 for p in out["parts"][:-1] for v in p["structures"].values())}


def expected_small_to_spare():
    return {"spare_only": {"three_or_more": 4}, "where": [4], "floor": True}


def _card(n, st, kind, set_name, seed):
    return {"item_id": _iid(n), "set": set_name, "seed": seed,
            "structure": {"parties": PARTIES[st], "record_kind": kind}}


def _fixture(folder, set_name, shape, start=1):
    keys, set_dir = Path(folder) / ("keys_" + set_name), Path(folder) / ("set_" + set_name)
    keys.mkdir()
    n, cards = start, []
    for st, count in shape.items():
        for j in range(count):
            c = _card(n, st, KINDS[j % 2], set_name, 1000 + n)
            (keys / (c["item_id"] + ".card.json")).write_text(json.dumps(c), encoding="utf-8")
            (set_dir / "build" / c["item_id"]).mkdir(parents=True)
            (set_dir / "build" / c["item_id"] / "build.json").write_text("{}", encoding="utf-8")
            cards.append(c)
            n += 1
    return keys, set_dir, cards


def observe_select_all():
    with tempfile.TemporaryDirectory() as folder:
        _k, set_dir, cards = _fixture(folder, "validation_strata", {"two_singles": 15, "teams": 12, "one_vs_coalition": 11})
        dropped = [cards[0]["item_id"], cards[20]["item_id"]]
        out = ns.select_all(cards, set_dir, dropped)
        strata = ns.select_strata(cards, set_dir, {"two_singles": 10, "teams": 10, "one_vs_coalition": 10}, dropped)
        return {"kept": len(out["kept"]), "short": out["short"], "dropped_out": not set(dropped) & set(out["kept"]),
                "all_kept": out["all_kept"], "strata_kept": len(strata["kept"])}


def expected_select_all():
    return {"kept": 36, "short": 0, "dropped_out": True, "all_kept": True, "strata_kept": 30}


def observe_rule_checked():
    good = ns.parts_rule(_cfg())

    def bad(**change):
        cfg = _cfg()
        cfg["split"]["parts_rule"].update(change)
        return caught(lambda: ns.parts_rule(cfg))

    def missing():
        cfg = _cfg()
        cfg["split"]["parts_rule"].pop("seed")
        return caught(lambda: ns.parts_rule(cfg))
    return {"pool": good["pool"], "parts_min": good["parts_min"], "missing": missing(), "three": bad(parts_min=3),
            "undeclared": bad(pool=["validation", "nowhere_1"]), "repeat": bad(pool=["validation", "validation"])}


def expected_rule_checked():
    raised = "raised ValueError"
    return {"pool": ["validation", "validation_strata"], "parts_min": 4, "missing": raised, "three": raised,
            "undeclared": raised, "repeat": raised}


def observe_label_name():
    return {n: bool(lp.SET_NAME.match(n)) for n in ("validation", "validation_strata", "c4val_1", "Validation",
                                                     "valid-ation", "_validation")}


def expected_label_name():
    return {"validation": True, "validation_strata": True, "c4val_1": True, "Validation": False,
            "valid-ation": False, "_validation": False}


def observe_cli():
    with tempfile.TemporaryDirectory() as folder:
        ka, sa, ca = _fixture(folder, "validation_strata", {"two_singles": 30, "teams": 28, "one_vs_coalition": 29})
        kb, sb, cb = _fixture(folder, "validation", {"two_singles": 10, "three_or_more": 11}, start=500)
        sel = {}
        for name, cards, set_dir in (("validation_strata", ca, sa), ("validation", cb, sb)):
            sel[name] = Path(folder) / ("kept_%s.json" % name)
            sel[name].write_text(json.dumps(ns.select_all(cards, set_dir, [cards[1]["item_id"]])), encoding="utf-8")
        out, counts = Path(folder) / "parts.json", Path(folder) / "parts_counts.json"
        argv = ["split-parts", "--select"] + ["%s=%s" % kv for kv in sel.items()] + \
               ["--keys", "validation_strata=%s" % ka, "validation=%s" % kb, "--out", str(out), "--counts-out", str(counts)]
        with contextlib.redirect_stdout(io.StringIO()):
            code = ns.main(argv)
        parts, cnt = json.loads(out.read_text(encoding="utf-8")), counts.read_text(encoding="utf-8")
        one_set = caught(lambda: ns.main(["split-parts", "--select", "validation=%s" % sel["validation"], "--keys",
                                          "validation=%s" % kb, "--out", str(out), "--counts-out", str(counts)]))
        strata_file = Path(folder) / "kept_strata.json"
        strata_file.write_text(json.dumps(ns.select_strata(ca, sa, {"two_singles": 10, "teams": 10,
                                                                     "one_vs_coalition": 10})), encoding="utf-8")
        not_whole = caught(lambda: ns.main(["split-parts", "--select", "validation_strata=%s" % strata_file,
                                            "validation=%s" % sel["validation"], "--keys", "validation_strata=%s" % ka,
                                            "validation=%s" % kb, "--out", str(out), "--counts-out", str(counts)]))
        return {"code": code, "pool": parts["pool"], "parts": len(parts["parts"]),
                "ids_in_parts": all(p["items"] for p in parts["parts"]),
                "no_ids_in_counts": "syn-" not in cnt, "one_set": one_set, "not_whole": not_whole}


def expected_cli():
    return {"code": 0, "pool": 106, "parts": 4, "ids_in_parts": True, "no_ids_in_counts": True,
            "one_set": "raised SystemExit", "not_whole": "raised SystemExit"}


PROOFS = ("balanced", "small_to_spare", "select_all", "rule_checked", "label_name", "cli")
NEUTRALISATIONS = {
    "floor": ((ns, "split_parts", 'k = min(n_parts, len(items) // rule["min_per_structure"])', "k = n_parts"),
              ("balanced", "small_to_spare")),
    "dropped": ((ns, "select_all", 'kept = [c["item_id"] for c in order if c["item_id"] not in drop]',
                 'kept = [c["item_id"] for c in order]'), ("select_all",)),
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
    return "PASS", ("%d proofs, %d neutralisations, fail, restore, pass, no model and no item: D-843 parts; max(4, "
                    "pool // 35) parts, each structure on as many parts as hold 5 of it, record kinds and sizes "
                    "balanced, digests per part, the same pool the same parts and another seed other members, a "
                    "small structure to the spare; a pool set keeps every item no screen dropped; the rule checked; "
                    "the label pass takes the D-798 names; split-parts writes ids for role N and counts for the lead "
                    "(%s)" % (len(PROOFS), len(NEUTRALISATIONS), ", ".join(PROOFS)))


if __name__ == "__main__":
    status, detail = run()
    print("687", status, detail)
