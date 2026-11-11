"""Gate check 325, D-S45 attempt 1 (benchmark/baselines/either_test.py). No model, no real key: an
invented fresh set, an invented key and canned replies, in a temporary folder. Each proof is
neutralise, fail, restore, pass.

1. the bar's figures are the code's, alpha .05 one-sided among them, and another is refused;
2. the candidate flags when either flags, keeps the judge's class otherwise, B1's where it abstains;
3. the comparator is the better B1 group, a tie to the reasoning group, past the floor none;
4. keep needs the one-sided sign test at .05, precision at least the comparator's, the chance
   tail and the flagged share;
5. one prompts file holds the choice pairs of the base judge and both B1 groups' prompts, which the
   replay's loader admits; a read scores through the scorer, and is read once.
"""
import importlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "adapters")):
    if path not in sys.path:
        sys.path.insert(0, path)

import choice_decision as cd  # noqa: E402
import choice_decision_checks as cdc  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

et = importlib.import_module("either_test")
cr = importlib.import_module("choice_read")
doc_judge = importlib.import_module("doc_judge")
pair_judge = importlib.import_module("pair_judge")
patched, with_source, caught = cdc.patched, cdc.with_source, cdc.caught
GOLD = {"f0": True, "f1": True, "f2": False, "f3": False, "f4": True, "f5": False}
TEXT = {True: "The quay of number %d was sold to the city in the year 1901.\n\nThe quay of number %d has never been sold to the city at all.\n",
        False: "The bakery of number %d sells bread to the town each day.\n\nThe bakery of number %d stands near the town market.\n"}


def row(item, cls, document="d"):
    return {"document_id": document, "item_id": item, "cls": cls, "source": "x"}


def observe_either():
    judge = [row("a", "FLAG"), row("b", "CLEAR"), row("c", "ABSTAIN"), row("d", "CLEAR")]
    b1 = [row("a", "CLEAR"), row("b", "FLAG"), row("c", "CLEAR"), row("d", "UNDECIDED")]
    return [r["cls"] for r in et.either(judge, b1)]


def expected_either():
    return ["FLAG", "FLAG", "CLEAR", "CLEAR"]


def figure(accuracy, abstain=0, items=60):
    return {"accuracy": accuracy, "abstain": abstain, "items": items}


def observe_comparator():
    return {"tie": et.comparator({"judge_direct": figure(.6), "judge_reason": figure(.6)}),
            "higher": et.comparator({"judge_direct": figure(.7), "judge_reason": figure(.6)}),
            "floor": et.comparator({"judge_direct": figure(.7, abstain=10), "judge_reason": figure(.6)}),
            "none": et.comparator({"judge_direct": figure(.7, abstain=10), "judge_reason": figure(.6, abstain=10)})}


def expected_comparator():
    return {"tie": "judge_reason", "higher": "judge_direct", "floor": "judge_reason", "none": None}


CANDIDATE = {"flagged": 20, "right": 18, "false": 2, "precision": .9, "chance_tail": .001, "items": 62}
OTHER = {"flagged": 8, "right": 6, "false": 2, "precision": .75}


def observe_tests():
    keep = lambda c=CANDIDATE, o=OTHER, w=6, l=0: (lambda t: "keep" if all(t.values()) else sorted(k for k, v in t.items() if not v))(et.tests(c, o, w, l))
    return {"keep": keep(), "five of five": keep(w=5), "more losses": keep(w=2, l=6), "precision": keep(c=dict(CANDIDATE, right=14, false=6, precision=.7)),
            "chance": keep(c=dict(CANDIDATE, chance_tail=.06)), "flagged": keep(c=dict(CANDIDATE, flagged=55, right=50, false=5)),
            "no comparator flag": keep(o=dict(OTHER, flagged=0, right=0, false=0, precision=None))}


def expected_tests():
    return {"keep": "keep", "five of five": "keep", "more losses": ["sign_test"], "precision": ["precision"], "chance": ["chance"], "flagged": ["flagged"],
            "no comparator flag": ["precision"]}


class Canned(cdc.ChoiceBackend):
    """Choice prompts by logits (contradict where the text says never), B1 by J1's reply form."""

    def choose(self, system, user, answers):
        question = cd.bind(cd.declare(user, answers), cdc.encode)
        row = cdc.logits(Y=12.0) if "never been sold" in user else cdc.logits(N=12.0)
        decision = dict(cd.decide(lambda p: row, question, None), logits_dtype="torch.float32", model_logits_dtype="torch.float16")
        return {"decision": decision, "payload": user, "form": "rendered_prompt", "attention": {}, "prefill": {"prefill_seconds": .01, "chunks": 0}}

    def generate(self, system, user, max_new_tokens):
        item = user.split("item_id")[-1].split('"')[2] if '"item_id"' in user else None
        spec = doc_judge._adapter("contradoc").SPEC
        label = doc_judge.label_name(spec, "FLAG" if "never been sold" in user else "CLEAR")
        text = json.dumps({"item_id": CURRENT["items"].get(user, item), "label": label, "evidence": "e", "reason": "r"})
        return {"text": text, "payload": user, "form": "rendered_prompt", "output_tokens": 20, "prefill": {"prefill_seconds": .01, "chunks": 0}}


CURRENT = {"items": {}}


def sample(folder):
    """(prompts, workloads, keys, ids, items) of an invented fresh set of six documents."""
    folder = Path(folder)
    works, keys, rows = [], [], []
    spec = doc_judge._adapter("contradoc").SPEC
    for n, (name, gold) in enumerate(GOLD.items()):
        work, _ = cdc._workload(folder, name, TEXT[gold] % (n, n), {"CONV-CDOC-01": "No passage may state what another rules out."})
        works.append(work)
        rows.append({"document_id": name, "item_id": "i-" + name, "rule_id": "CONV-CDOC-01", "benchmark": "contradoc", "source_document_id": "src-" + name})
        key = folder / (name + "_key.json")
        key.write_text(json.dumps({"benchmark": "contradoc", "document": name + ".md", "items": [
            {"item_id": "i-" + name, "rule_id": "CONV-CDOC-01", "gold": spec.labels["FLAG" if gold else "CLEAR"], "evidence_sentence": ""}]}), encoding="utf-8")
        keys.append(str(key))
    items = folder / "items.json"
    items.write_text(json.dumps({"benchmark": "contradoc", "items": rows}), encoding="utf-8")
    ids = folder / "ids.json"
    ids.write_text(json.dumps({"documents": sorted("src-" + n for n in GOLD)}), encoding="utf-8")
    prompts = folder / "prompts.json"
    with patched(pair_judge, "_words_allowed", True):
        value = et.build(works, items, prompts, embed=lambda passages: None)
    CURRENT["items"] = {p["user"]: p["item_id"] for p in value["prompts"] if p.get("form") == doc_judge.B1_FORM}
    return value, prompts, keys, ids, items


def observe_end_to_end():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        value, prompts, keys, ids, items = sample(folder)
        run = folder / "run"
        doc_judge.run(prompts, run, backend_factory=lambda reader, context: Canned(reader), reader_for=lambda group, allowance: dict(cdc.READER))
        bar = folder / "bar.json"
        cr.write_once(bar, et.bar_value(prompts, keys, ids, items))
        with patched(cr, "repository_root", lambda: folder / "repository"):
            result = et.read(bar, prompts, run, keys, ids, items, folder / "out")
            again = caught(lambda: et.read(bar, prompts, run, keys, ids, items, folder / "out2") and "read")
        forms = {}
        for p in value["prompts"]:
            forms[(p.get("form"), p["group"])] = forms.get((p.get("form"), p["group"]), 0) + 1
        return {"forms": sorted("%s %s %d" % (f, g, n) for (f, g), n in forms.items()), "result": result["result"], "comparator": result["comparator"],
                "candidate right": result["candidate"]["right"], "readable": result["readable"], "again": again, "reads": result["reads"]}


def expected_end_to_end():
    return {"forms": ["b1 judge_direct 6", "b1 judge_reason 6", "choice choice_direct 12"], "result": "drop", "comparator": "judge_reason",
            "candidate right": 3, "readable": {"choice_prompts": 1.0, "b1_prompts": 1.0}, "again": "ValueError: this test has been read: it is read once", "reads": 1}


def observe_bar():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        _, prompts, keys, ids, items = sample(folder)
        good = et.bar_value(prompts, keys, ids, items)
        out = {}
        for name, change in (("alpha", {"figures": dict(et.FIGURES, alpha_one_sided=.0125)}), ("ids", {"ids_sha256": "x"}), ("keys", {"keys_sha256": "x"})):
            path = folder / ("bar_" + name + ".json")
            path.write_text(json.dumps(dict(good, **change)), encoding="utf-8")
            out[name] = caught(lambda: et.open_bar(path, prompts, keys, ids, items) and "read")
        path = folder / "good.json"
        path.write_text(json.dumps(good), encoding="utf-8")
        out["good"] = caught(lambda: bool(et.open_bar(path, prompts, keys, ids, items)))
        out["a key twice"] = caught(lambda: et.universe(keys + keys[:1], ids, items) and "read")
        return out


def expected_bar():
    return {"alpha": "ValueError: the bar states other figures than the code's", "ids": "ValueError: the bar names other inputs: ids_sha256",
            "keys": "ValueError: the bar names other inputs: keys_sha256", "good": True, "a key twice": "ValueError: a key is given twice"}


def run_checks():
    proofs = [
        ("the bar's figures", observe_bar, expected_bar, lambda: with_source(et, "open_bar", 'or bar.get("figures") != FIGURES', "")),
        ("the bar's inputs", observe_bar, expected_bar, lambda: with_source(et, "open_bar", "if bar.get(name) != got:", "if False:")),
        ("either flags", observe_either, expected_either, lambda: with_source(et, "either", "if cr.FLAG in (j[\"cls\"], b[\"cls\"])", "if j[\"cls\"] == cr.FLAG")),
        ("the comparator", observe_comparator, expected_comparator, lambda: with_source(et, "comparator", 'g == "judge_reason"', 'g != "judge_reason"')),
        ("the comparator's floor", observe_comparator, expected_comparator, lambda: with_source(
            et, "comparator", 'if figures[g]["abstain"] <= doc_judge.BAR_MAX_B1_ABSTAIN * figures[g]["items"]', "")),
        ("the sign test at .05", observe_tests, expected_tests, lambda: patched(et, "FIGURES", dict(et.FIGURES, alpha_one_sided=.0125))),
        ("precision", observe_tests, expected_tests, lambda: with_source(et, "tests", 'candidate["right"] * other["flagged"] >= other["right"] * candidate["flagged"]', "True")),
        ("the chance tail", observe_tests, expected_tests, lambda: patched(et, "FIGURES", dict(et.FIGURES, chance_at_most=1.0))),
        ("the flagged share", observe_tests, expected_tests, lambda: patched(et, "FIGURES", dict(et.FIGURES, flagged_share_at_most=1.0))),
        ("one file, read once", observe_end_to_end, expected_end_to_end, lambda: patched(cr, "reads_of", lambda path, key: 0)),
    ]
    results = []
    for name, observe, expected, neutralise in proofs:
        results.append(prove_effect(name=name, validate=lambda: et.CONFIG_PATH.is_file(), observe=observe,
                                    check=lambda: ("PASS" if observe() == expected() else "FAIL", name), neutralise=neutralise))
    return "PASS", ("%d proofs on an invented fresh set and canned replies, no model and no real key: the bar's figures and inputs, the "
                    "candidate's rule, the comparator, every item of keep, and one prompts file read once through the scorer") % len(results)


if __name__ == "__main__":
    print(run_checks())
