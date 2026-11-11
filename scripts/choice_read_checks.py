"""Gate check 325, the reader: docs/loop/stages/C_BAR.md in code (benchmark/baselines/choice_read.py).
No model, no real key, no score: invented decisions, an invented key and invented B1 labels, in a
temporary folder. Each proof is neutralise, fail, restore, pass.

1. the split is by the salted hash, once, and an odd document goes to half A;
2. a tie or a failed call reaches no label, on a pair or a claim, at any threshold; a claim with no
   prompt is ABSTAIN, and every row keeps its `source`;
3. a pair is flagged only when both orders stand on contradicts; a document is CLEAR only with
   enough pairs readable, else ABSTAIN, and ABSTAIN counts wrong;
4. the threshold is the best qualifying value, a tie the higher, none a drop, and the mass test
   closes half B first;
5. the verdict needs every item, the no-threshold macro-F1 among them, `placed_share` and the
   Python-only control; void comes first;
6. the comparator is the better B1 group, a tie the reasoning one, past the abstain floor none;
7. the sign test is exact, and a trained pass binds by prompt_id and user_sha256;
8. the bar refuses another figure and any other input;
9. read-a opens no half-B decision, and reports gold and reach through the scorer; split-report
   gives the same counts from the bar's inputs alone, with no pass, before anything is read;
10. read-b refuses with neither or both of the recipe and --base-alone, reads half B once, by the
    file the bar names, whatever folder it is pointed at, and appends nothing when nothing opens;
11. a frozen recipe needs the second bar, of this bar, naming that recipe and these checkpoints;
    `bar` and `bar-b` write files read-a and read-b accept, and never overwrite one;
12. a closed base beside a trained model stands at its best half A threshold with no gate, a tie
    the higher, a value flagging nothing no choice, and when none flags the result says so;
13. the base has no adapter and a trained pass has one, with its digest, both carried; two trained
    candidates are read together under one recipe, each with its checkpoints, the permissive mix
    beside dev_mix with the sign test, and `clearly_worse` by the rule written before any number;
14. read-b reads only the passes half A read, by their digests;
15. a left-out claim's prompt counts nowhere; SciTab with under 5 B1 flags has no precision gate;
16. half A reports ties and the readable shares, and under the void lines half B stays closed;
17. an order_control prompt reaches no label, threshold or verdict, and read-a reports the shift;
18. a read of half B is keyed on what half B is: a respaced items file is refused by its pin, a key
    given twice is refused, and a bar written again over the same half B is the same read; a
    pass's steps are its adapter's update, the second bar's checkpoints the training's updates, and
    the recipe digest is judge_train's own, from the two recipe files; with every candidate closed
    nothing is read; git must name the common folder; read-a says a non-float32 pass will be refused.
"""
import contextlib
import importlib
import io
import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "adapters")):
    if path not in sys.path:
        sys.path.insert(0, path)

import choice_decision as cd  # noqa: E402
import choice_decision_checks as cdc  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

# benchmark/baselines is no package and not under scripts/, so these are loaded by name (check 118).
choice_judge = importlib.import_module("choice_judge")
cr = importlib.import_module("choice_read")
doc_judge = importlib.import_module("doc_judge")
pair_judge = importlib.import_module("pair_judge")

patched, with_source, caught = cdc.patched, cdc.with_source, cdc.caught
FORMS = json.loads(choice_judge.CONFIG_PATH.read_text(encoding="utf-8"))["choice"]["forms"]


def decision(kind, top, confidence, tie=False):
    """An invented saved decision: `top` by label, the rest sharing what is left."""
    labels = [a["label"] for a in FORMS[kind]["answers"]]
    shares = {label: (1 - confidence) / 2 for label in labels}
    shares[top] = confidence
    if tie:
        shares = {labels[0]: .45, labels[1]: .45, labels[2]: .1}
    rows = [{"label": k, "surface": "x", "token_id": n, "probability": v} for n, (k, v) in enumerate(shares.items())]
    return cd.settle({"schema": cd.SCHEMA, "answers": rows, "declared_mass": .9}, None)


def call(pair=(0, 1), made=None, order="ab", document="d", kind="pair"):
    return {"prompt_id": "p", "user_sha256": "s", "choice": kind, "benchmark": "contradoc", "document_id": document, "item_id": "i", "rule_id": "r",
            "pair": list(pair), "order": order, "selection": None, "seconds": .1, "decision": made}


YES, NO = decision("pair", "contradicts", .9), decision("pair", "does not", .9)
LOW, TIED = decision("pair", "contradicts", .55), decision("pair", "contradicts", .5, tie=True)


def pair_rows(*orders):
    return [call(pair=(n, n + 1), made=m, order=o) for n, two in enumerate(orders) for m, o in zip(two, ("ab", "ba"))]


def doc(*orders, threshold=.8):
    row = cr.read_document("d", "i", pair_rows(*orders), FORMS, threshold)
    return row["cls"], row["source"]


def observe_split():
    a, b = cr.halves(["d%d" % n for n in range(7)])
    return {"sizes": (len(a), len(b)), "a": sorted(a), "same": cr.halves(["d%d" % n for n in reversed(range(7))]) == (a, b)}


def expected_split():
    return {"sizes": (4, 3), "a": ["d0", "d2", "d3", "d5"], "same": True}


def observe_no_tie_label():
    claim_tie = decision("claim", "holds", .5, tie=True)
    claim = lambda made, t=.8: (lambda r: (r["cls"], r["source"]))(cr.read_claim("d", "i", dict(call(made=made, kind="claim")), FORMS, t))
    return {"pair tie": doc((TIED, YES)), "pair tie, none below": doc((TIED, YES), threshold=0), "pair failed": doc((None, YES)),
            "beside a flag": doc((TIED, YES), (YES, YES)), "claim tie": claim(claim_tie), "claim tie at 0": claim(claim_tie, 0),
            "claim failed": claim(None), "no prompt": (lambda r: (r["cls"], r["source"]))(cr.read_claim("d", "i", None, FORMS, .8))}


def expected_no_tie_label():
    return {"pair tie": ("ABSTAIN", "tie"), "pair tie, none below": ("ABSTAIN", "tie"), "pair failed": ("ABSTAIN", "failed"),
            "beside a flag": ("FLAG", "top_answer"), "claim tie": ("ABSTAIN", "tie"), "claim tie at 0": ("ABSTAIN", "tie"),
            "claim failed": ("ABSTAIN", "failed"), "no prompt": ("ABSTAIN", "refusal")}


def _state_ignoring_ties(row):
    return cr.FAILED if row["decision"] is None else cr.READ


@contextlib.contextmanager
def _tie_read_as_its_first_answer():
    """A tie taken for its declaration's first answer: what breaking it by order would do."""
    first = lambda row, forms, threshold: (cr.answer_class(forms, row["choice"], row["decision"]["answers"][0]["label"]), True)
    with patched(cr, "state", _state_ignoring_ties), patched(cr, "read_at", lambda row, forms, threshold: first(row, forms, threshold)
                                                             if row["decision"]["why"] == cd.TIE else REAL_READ_AT(row, forms, threshold)):
        yield


REAL_READ_AT, REAL_HALVES = cr.read_at, cr.halves


def observe_reading():
    claim = lambda made: (lambda r: (r["cls"], r["source"]))(cr.read_claim("d", "i", call(made=made, kind="claim"), FORMS, .8))
    twenty = [(NO, NO)] * 19
    return {"both": doc((YES, YES)), "split": doc((YES, NO)), "below": doc((YES, LOW)), "cannot tell": doc((decision("pair", "cannot tell", .9),) * 2),
            "one unreadable of twenty": doc(*twenty, (TIED, NO)), "two of twenty": doc(*twenty[:18], (TIED, NO), (TIED, NO)),
            "claim holds": claim(decision("claim", "holds", .9)), "claim not met": claim(decision("claim", "not met", .9)),
            "claim low": claim(decision("claim", "not met", .6))}


def expected_reading():
    return {"both": ("FLAG", "top_answer"), "split": ("CLEAR", "top_answer"), "below": ("CLEAR", "threshold"), "cannot tell": ("CLEAR", "top_answer"),
            "one unreadable of twenty": ("CLEAR", "top_answer"), "two of twenty": ("ABSTAIN", "tie"),
            "claim holds": ("CLEAR", "top_answer"), "claim not met": ("FLAG", "top_answer"), "claim low": ("UNDECIDED", "threshold")}


ROW = {"items": 30, "right": 8, "false": 1, "flagged": 9, "net": 7, "accuracy": .7, "macro_f1": .6, "precision": 8 / 9, "chance_tail": .001}
TOP_ROW = dict(ROW, macro_f1=.58)
B1 = {"items": 30, "right": 4, "false": 2, "flagged": 6, "net": 2, "accuracy": .6, "macro_f1": .5, "precision": 4 / 6}
PLACE = {"placed": 4, "flagged_with_two_marks": 6}
PYTHON = {"net": 1}


def verdicts(benchmark, row=ROW, top=TOP_ROW, b1=B1, place=PLACE, python=PYTHON):
    checks = cr.tests(benchmark, row, top, b1, place, python)
    return "keep" if all(checks.values()) else [k for k, v in checks.items() if not v]


def observe_verdict():
    return {"contradoc": verdicts("contradoc"), "scitab": verdicts("scitab"),
            "accuracy level": verdicts("contradoc", row=dict(ROW, accuracy=.6)), "net below": verdicts("contradoc", row=dict(ROW, net=1)),
            "macro level": verdicts("scitab", row=dict(ROW, macro_f1=.5)), "top answers level": verdicts("scitab", top=dict(ROW, macro_f1=.5)),
            "flags": verdicts("scitab", row=dict(ROW, flagged=25)), "chance": verdicts("scitab", row=dict(ROW, chance_tail=.02)),
            "precision": verdicts("scitab", row=dict(ROW, precision=.5, ), b1=dict(B1, flagged=6)),
            "no gate under 5": (verdicts("scitab", row=dict(ROW, precision=.1), b1=dict(B1, flagged=4)), cr.precision_gate("scitab", dict(B1, flagged=4))),
            "contradoc precision": verdicts("contradoc", row=dict(ROW, precision=.74)),
            "no false alarm": verdicts("scitab", b1=dict(B1, false=0, precision=1.0), row=dict(ROW, precision=1.0)),
            "placed": verdicts("contradoc", place=dict(PLACE, placed=2, flagged_with_two_marks=4)), "share": verdicts("contradoc", place=dict(PLACE, placed=3, flagged_with_two_marks=7)),
            "python": verdicts("contradoc", python={"net": 7})}


def expected_verdict():
    return {"contradoc": "keep", "scitab": "keep", "accuracy level": ["above_b1"], "net below": ["above_b1", "above_python"], "macro level": ["above_b1"],
            "top answers level": ["above_b1"], "flags": ["flagged"], "chance": ["chance"], "precision": ["precision"], "no gate under 5": ("keep", "none: B1 raised under 5 flags on the half"), "contradoc precision": ["precision"],
            "no false alarm": ["precision"], "placed": ["placed"], "share": ["placed_share"], "python": ["above_python"]}


def observe_void():
    read = [call(made=YES)] * 96 + [call(made=None)] * 4
    low = [call(made=YES)] * 94 + [call(made=None)] * 6
    spread = [call(made=YES, document="d%d" % n) for n in range(20)] + [call(made=None, document="d%d" % n) for n in range(3)]
    docs = {"d%d" % n: [] for n in range(20)}
    return {"clean": cr.is_void([call(made=YES)] * 100, {"d": []})[0], "a document not whole": cr.is_void(read, {"d": []})[0],
            "readable under": cr.is_void(low, {"d": []})[0], "documents under": cr.is_void(spread, docs)[0],
            "refused claims count": cr.is_void([call(made=YES)] * 94, {"d": []}, {"i%d" % n: "d" for n in range(6)})[1],
            "found": cr.refused_prompts("scitab", [dict(call(made=YES), item_id="i1")], {"d": [{"item_id": "i1"}, {"item_id": "i2"}]})}


def expected_void():
    return {"clean": False, "a document not whole": True, "readable under": True, "documents under": True,
            "refused claims count": .94, "found": {"i2": "d"}}


def observe_threshold():
    by_value = {.5: dict(ROW, accuracy=.6), .6: dict(ROW, accuracy=.7, net=3), .7: dict(ROW, accuracy=.7, net=3), .8: dict(ROW, accuracy=.7, net=5),
                .9: dict(ROW, accuracy=.9, flagged=29), .95: dict(ROW, accuracy=.95, precision=.1), .99: dict(ROW, accuracy=.99, flagged=0), .999: dict(ROW, accuracy=.5)}
    pick = lambda table, b="contradoc": _choose(table, b)
    return {"best": pick(by_value), "scitab tie": pick({v: dict(ROW, macro_f1=.6) for v in cr.FIGURES["thresholds"]}, "scitab"),
            "none": pick({v: dict(ROW, flagged=0) for v in cr.FIGURES["thresholds"]})}


def _choose(table, benchmark):
    with patched(cr, "score", lambda rows, keys, out, left, tag: (None, table[rows])), patched(cr, "view", lambda b, d, r, f, t: t):
        return cr.choose_threshold(benchmark, {}, [], FORMS, [], ".", set(), B1, "t")[0]


def expected_threshold():
    return {"best": .8, "scitab tie": .999, "none": None}


def observe_comparator():
    rows = {"judge_direct": dict(B1, accuracy=.6, abstain=0), "judge_reason": dict(B1, accuracy=.6, abstain=0)}

    def compare(table):
        with patched(cr, "figures", lambda scored, setting: scored), patched(cr, "b1_rows", lambda group, *a: table[group]):
            found, _ = cr.comparator("contradoc", {}, {}, ".", set())
        return found and found["group"]
    return {"tie": compare(rows), "better": compare(dict(rows, judge_direct=dict(B1, accuracy=.7, abstain=0))),
            "past the floor": compare(dict(rows, judge_direct=dict(B1, accuracy=.7, abstain=9))),
            "none": compare({g: dict(B1, abstain=9) for g in rows})}


def expected_comparator():
    return {"tie": "judge_reason", "better": "judge_direct", "past the floor": "judge_reason", "none": None}


def observe_sign():
    return [cr.sign_test(6, 0), cr.sign_test(7, 1), cr.sign_test(5, 5), cr.sign_test(0, 0)]


def expected_sign():
    return [.015625, .035156, .623047, 1.0]


def observe_binding():
    base = [dict(call(made=YES), prompt_id="a", user_sha256="1"), dict(call(made=YES), prompt_id="b", user_sha256="2")]
    return {"same": caught(lambda: cr.bound(base, list(reversed(base))) or "bound"),
            "other words": caught(lambda: cr.bound(base, [base[0], dict(base[1], user_sha256="3")]) or "bound"),
            "missing": caught(lambda: cr.bound(base, base[:1]) or "bound")}


def expected_binding():
    refused = "ValueError: the pass does not bind to the base by prompt_id and user_sha256"
    return {"same": "bound", "other words": refused, "missing": refused}


# The whole read, on an invented sample: two gold and two clear documents in each half.

PAIR = "The quay of number %d was sold to the city in the year 1901.\n\nThe quay of number %d has never been sold to the city at all.\n"
CLEAR_PAIR = "The bakery of number %d sells bread to the town each day.\n\nThe bakery of number %d stands near the town market.\n"
TABLE = "Table %d: Scores.\n\n| Model | Acc |\n|---|---|\n| Alpha model | 71 |\n| Beta model | 80 |\n"
CLAIM_TRUE, CLAIM_FALSE = "Alpha model scores lower here.", "Beta model scores lower here."


def recipe_fixture(trainer):
    """A dev_mix recipe judge_train.read_file admits: its own checks' fixture."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("judge_training_checks_fixture", ROOT / "tools" / "judge_training_checks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fixture(trainer)


class Sample:
    """An invented sample and a pass of it. `backend` answers by the words a prompt holds."""

    def __init__(self, folder, permuted=False):
        self.folder = Path(folder)
        CURRENT["folder"] = self.folder
        self.keys, self.b1 = [], self.folder / "b1"
        pair_docs, table_docs = ["p%d" % n for n in range(8)], ["t%d" % n for n in range(5)]
        a, b = REAL_HALVES(pair_docs)
        gold = set(sorted(a)[:2]) | set(sorted(b)[:2])
        self.half_b = sorted(b)
        pair_built, claim_built = [], []
        for n, name in enumerate(pair_docs):
            text = (PAIR if name in gold else CLEAR_PAIR) % (n, n)
            work = cdc._workload(self.folder, name, text, {"CONV-" + name: "No passage may state what another rules out."})
            pair_built.append(work)
            self._key(name, "contradoc", [("i-CONV-" + name, "CONV-" + name, "contradictory" if name in gold else "not contradictory")])
        for n, name in enumerate(table_docs):
            rules = {"CONV-%s-t" % name: cdc._rule(CLAIM_TRUE), "CONV-%s-f" % name: cdc._rule(CLAIM_FALSE)}
            claim_built.append(cdc._workload(self.folder, name, TABLE % n, rules, "scitab"))
            self._key(name, "scitab", [("i-CONV-%s-t" % name, "CONV-%s-t" % name, "supports"), ("i-CONV-%s-f" % name, "CONV-%s-f" % name, "refutes")])
        self.prompts = self.folder / "prompts.json"
        with patched(pair_judge, "_words_allowed", True):
            self.value = choice_judge.build(self.prompts, pair_workloads=[w for w, _ in pair_built], pair_items=[i for _, i in pair_built],
                                            claim_workloads=[w for w, _ in claim_built], claim_items=[i for _, i in claim_built], embed=lambda items: None,
                                            permuted_half_a=permuted)
        self.items = self.folder / "g1.json"
        ids = {"contradoc": [], "scitab": []}
        for key in self.keys:
            value = json.loads(Path(key).read_text(encoding="utf-8"))
            ids[value["benchmark"]] += [i["item_id"] for i in value["items"]]
        self.items.write_text(json.dumps(dict(ids, left_out=[])), encoding="utf-8")
        CURRENT["pin"] = doc_judge._lf_sha(self.items)
        self.source = self.folder / "source.json"
        self.source.write_text("{}", encoding="utf-8")
        self.bar = self.folder / "bar.json"
        self.write_bar()

    def _key(self, name, benchmark, items):
        path = self.folder / (name + "_key.json")
        path.write_text(json.dumps({"benchmark": benchmark, "document": name + ".md", "items": [
            {"item_id": i, "rule_id": r, "gold": g, "evidence_sentence": ""} for i, r, g in items]}), encoding="utf-8")
        self.keys.append(str(path))
        spec = doc_judge._adapter(benchmark).SPEC
        for group in cr.COMPARATORS:
            for i, r, _ in items:
                folder = self.b1 / (group + "_b1") / name / "labels"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (i + ".json")).write_text(json.dumps({
                    "arm": "B1", "schema": "b1-label-v2", "item_id": i, "document_id": name, "rule_id": r, "benchmark": benchmark,
                    "label": doc_judge.label_name(spec, "CLEAR"), "abstain": False, "evidence": None, "reason": None}), encoding="utf-8")

    def write_bar(self, **changes):
        self.reads = self.folder / "repository" / cr.READS_FILE
        with patched(doc_judge, "BAR_ITEMS_SHA256", CURRENT["pin"]):
            bar = cr.bar_value([self.prompts], self.keys, self.b1, self.source, self.items)
        self.bar.write_text(json.dumps(dict(bar, **changes)), encoding="utf-8")

    def trained(self, base_rule, dev_rule, permissive_rule):
        """(passes, provenance, recipe files, frozen recipe) of a base and both mixes, each mix one
        checkpoint at update 100. The recipe files are judge_train's own, built by its checks' fixture."""
        runs = {"base": self.run("base_run", base_rule), "dev_mix": self.run("dev_run", dev_rule, adapter="c" * 64),
                "permissive_mix": self.run("permissive_run", permissive_rule, adapter="d" * 64)}
        passes = self.args(*runs.items())[0]
        trainer = cr.judge_train()
        dev = recipe_fixture(trainer)
        permissive = dict(dev, publication=trainer.PUBLICATION["permissive_mix"],
                          rows=[dict(r, user=r["user"] + " p") for r in dev["rows"]])
        permissive["rows_sha256"] = trainer._sha(trainer._canonical_rows(permissive["rows"]))
        permissive["recipe_sha256"] = trainer.recipe_digest(permissive)
        provenance, files = {}, {}
        for name, adapter, recipe in (("dev_mix", "c" * 64, dev), ("permissive_mix", "d" * 64, permissive)):
            passes[name][0]["steps"] = 100
            files[name] = str(self.folder / ("%s_recipe.json" % name))
            Path(files[name]).write_text(json.dumps(recipe), encoding="utf-8")
            path = self.folder / ("%s_result.json" % name)
            path.write_text(json.dumps({"publication": {"mix": name}, "recipe_sha256": recipe["recipe_sha256"],
                                        "adapters": [{"weights_sha256": adapter, "update": 100}]}), encoding="utf-8")
            provenance[name] = str(path)
        return passes, provenance, files, trainer.pair_digest(dev, permissive)


    def run(self, name, row, adapter=None, dtype="torch.float32"):
        """A pass of the prompts, `row(user)` giving each prompt's logits; `adapter` a digest."""
        out = self.folder / name

        class Backend(cdc.ChoiceBackend):
            def prepare(inner):
                loaded = cdc.ChoiceBackend.prepare(inner)
                return dict(loaded, checkpoint=dict(loaded["checkpoint"], adapter_applied=True, adapter_sha256=adapter)) if adapter else loaded

            def choose(inner, system, user, answers):
                question = cd.bind(cd.declare(user, answers), cdc.encode)
                made = dict(cd.decide(lambda p: row(user), question, None), logits_dtype=dtype, model_logits_dtype="torch.float16")
                return {"decision": made, "payload": user, "form": "rendered_prompt", "attention": {}, "prefill": {"prefill_seconds": .01, "chunks": 0}}
        doc_judge.run(self.prompts, out, backend_factory=lambda reader, context: Backend(reader), reader_for=lambda g, a: dict(cdc.READER))
        return str(out)

    def args(self, *runs):
        return ({n: [{"steps": None, "files": [(str(self.prompts), r)]}] for n, r in runs}, self.keys, str(self.b1), str(self.source), str(self.items))


def right_answers(user):
    """Yes on what contradicts and on what holds, No on the rest, firmly."""
    if "PASSAGE A" in user:
        return cdc.logits(Y=12.0) if "never been sold" in user else cdc.logits(N=12.0)
    return cdc.logits(Y=12.0) if CLAIM_TRUE in user else cdc.logits(N=12.0)


@contextlib.contextmanager
def sample_marks():
    """The source's marks, and the repository root of the sample whose bar was written last."""
    sc = doc_judge._score_corpus()
    with patched(sc, "marked_passages", lambda key, item, texts, source=None: {"marked": [0], "partner": [1], "references": 1}), \
            patched(cr, "repository_root", lambda: CURRENT["folder"] / "repository"), patched(doc_judge, "BAR_ITEMS_SHA256", CURRENT.get("pin")):
        yield


CURRENT = {"folder": Path(".")}


def _read_a(s, folder, run):
    with sample_marks():
        return cr.read_a(str(s.bar), s.args(("base", run))[0], s.keys, str(s.b1), str(s.source), str(s.items), Path(folder))


def observe_read_a():
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        result = _read_a(s, s.folder / "a", s.run("run", right_answers))
    cell = result["candidates"]["base"]
    return {"counts": result["counts"], "states": {b: cell[b]["state"] for b in cell}, "thresholds": {b: cell[b].get("threshold") for b in cell},
            "right": {b: cell[b].get("figures", {}).get("right") for b in cell}, "half": result["half"]}


def expected_read_a():
    return {"counts": {"contradoc": {"A": {"gold": 2, "reachable": 2, "documents": 4}, "B": {"gold": 2, "reachable": 2, "documents": 4}},
                       "scitab": {"A": {"gold": 3, "reachable": None, "documents": 3}, "B": {"gold": 2, "reachable": None, "documents": 2}}},
            "states": {"contradoc": "ready", "scitab": "ready"}, "thresholds": {"contradoc": .999, "scitab": .999},
            "right": {"contradoc": 2, "scitab": 3}, "half": "A"}


def observe_split_report():
    """The counts before any pass exists: the prompts, the keys through the scorer, nothing read."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        with sample_marks():
            report = cr.split_report(str(s.bar), [str(s.prompts)], s.keys, str(s.b1), str(s.source), str(s.items), s.folder / "split.json")
            again = caught(lambda: cr.split_report(str(s.bar), [str(s.prompts)], s.keys, str(s.b1), str(s.source), str(s.items), s.folder / "split.json"))
        passes = [p for p in s.folder.iterdir() if p.is_dir() and (p / doc_judge.MEASUREMENT_FILE).exists()]
    return {"counts": report["counts"], "half a": {b: len(d) for b, d in report["half_a_documents"].items()}, "again": again, "passes": len(passes)}


def expected_split_report():
    return {"counts": expected_read_a()["counts"], "half a": {"contradoc": 4, "scitab": 3},
            "again": "ValueError: this file already exists: a report is written once", "passes": 0}


def observe_half_b_closed():
    """Half B's decisions flipped: read-a's whole result is the same, its passes' digests aside."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        flip = lambda user: cdc.logits(N=12.0) if any("number %s " % name[1:] in user for name in s.half_b) else right_answers(user)
        one = _read_a(s, s.folder / "a", s.run("run", right_answers))
        two = _read_a(s, s.folder / "b", s.run("flipped", flip))
    return _without_identity(one) == _without_identity(two)


def _without_identity(value):
    if isinstance(value, dict):
        return {k: _without_identity(v) for k, v in value.items() if k != "identity"}
    return [_without_identity(v) for v in value] if isinstance(value, list) else value


def _all_in_a(document_ids):
    return set(document_ids), set()


def observe_mass():
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        thin = lambda user: [v + (9.0 if n == ord("q") else 0) for n, v in enumerate(right_answers(user))] if False else [
            20.0 if n == ord("q") else v for n, v in enumerate(right_answers(user))]
        result = _read_a(s, s.folder / "a", s.run("run", thin))
    cell = result["candidates"]["base"]["contradoc"]
    return {"state": cell["state"], "share": cell["mass_share_under_floor"], "threshold": cell.get("threshold")}


def expected_mass():
    return {"state": "void", "share": 1.0, "threshold": None}


def observe_bar():
    out = {}
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        run = s.run("run", right_answers)
        for name, change in (("keys", {"keys_sha256": "x"}), ("labels", {"b1_labels_sha256": "x"}), ("source", {"source_sha256": "x"}), ("items", {"items_sha256": "x"}),
                             ("prompts", {"prompts_sha256": ["x"]}), ("figure", {"figures": dict(cr.FIGURES, chance_at_most=.05)})):
            s.write_bar(**change)
            out[name] = caught(lambda: _read_a(s, s.folder / ("o" + name), run) and "read")
    return out


def expected_bar():
    named = "ValueError: the bar names other inputs: "
    return {"keys": named + "keys_sha256", "labels": named + "b1_labels_sha256", "source": named + "source_sha256", "items": named + "items_sha256",
            "prompts": named + "prompts_sha256", "figure": "ValueError: the bar states other figures than the code's"}


def bar_b(s, name="bar_b.json", **changes):
    """The second bar of `s`, its recipe "a" * 64 and its checkpoints none unless changed."""
    path = s.folder / name
    path.write_text(json.dumps(dict({"schema": cr.BAR_B_SCHEMA, "bar_sha256": cr._sha(s.bar), "recipe_sha256": "a" * 64,
                                     "checkpoint_steps": {"dev_mix": [100], "permissive_mix": [100]}}, **changes)), encoding="utf-8")
    return path


def _read_b(s, first, run, out, **kwargs):
    passes, keys, b1, source, items = s.args(("base", run))
    with sample_marks():
        return cr.read_b(str(s.bar), str(first), passes, keys, b1, source, items, s.folder / out, **kwargs)


ONCE = "ValueError: half B of these inputs has been read: it is read once"


def observe_read_b():
    try:
        return _observe_read_b()
    except ValueError as exc:
        return "refused: " + str(exc)


def _observe_read_b():
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        run = s.run("run", right_answers)
        _read_a(s, s.folder / "a", run)
        first, reads = s.folder / "a" / cr.RESULT_A, s.reads
        out = {"neither": caught(lambda: _read_b(s, first, run, "b0")),
               "both": caught(lambda: _read_b(s, first, run, "b0", frozen_recipe="a" * 64, base_alone=True)),
               "not a digest": caught(lambda: _read_b(s, first, run, "b0", frozen_recipe="soon")),
               "base only, a recipe": caught(lambda: _read_b(s, first, run, "b0", frozen_recipe="a" * 64, bar_b_path=bar_b(s)) and "read"),
               "file before": reads.exists()}
        one = _read_b(s, first, run, "b1", base_alone=True)
        used = caught(lambda: _read_b(s, first, run, "b1", base_alone=True))
        two = caught(lambda: _read_b(s, first, run, "b2", base_alone=True) and "read twice")
        s.write_bar(written="again, under another digest")
        _read_a(s, s.folder / "a2", run)
        closed = caught(lambda: _read_b(s, s.folder / "a2" / cr.RESULT_A, run, "b3", base_alone=True) and "read twice")
        cell = one["candidates"]["base"]["contradoc"]
        return dict(out, first=one["half_b_reads"], used=used, second=two, closed=closed,
                    lines=len(reads.read_text(encoding="utf-8").splitlines()) if reads.exists() else 0,
                    alone=(one["base_alone"], one["base_alone_statement"] is not None), right=cell["figures"]["right"], tested=sorted(cell["tests"]), dtype=cell["reported"]["logits_dtype"],
                    on_mark=cell["places"]["pairs_on_mark"], control=sorted(cell["python_control"]), top=one["candidates"]["base"]["scitab"]["top_answer_macro_f1"] is not None)


def expected_read_b():
    needed = "ValueError: half B needs T's frozen recipe digest or --base-alone, one of them"
    return {"neither": needed, "both": needed, "not a digest": "ValueError: the frozen recipe is named by its SHA-256",
            "base only, a recipe": "ValueError: a frozen recipe reads both trained mixes, dev_mix and permissive_mix, beside the base",
            "file before": False, "first": 1,
            "used": "ValueError: this folder already holds a result", "second": ONCE, "closed": ONCE, "lines": 1, "alone": (True, True), "right": 2,
            "tested": ["above_b1", "above_python", "chance", "flagged", "placed", "placed_share", "precision"], "dtype": ["torch.float32"],
            "on_mark": 2, "control": ["false", "flagged", "net", "right"], "top": True}


def observe_bar_b():
    """The recipe, both mixes and their checkpoints are compared."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        passes = {"base": [], "dev_mix": [{"steps": 100}], "permissive_mix": [{"steps": 100}]}
        attempt = lambda path, recipe="a" * 64: caught(lambda: cr.open_bar_b(path, cr._sha(s.bar), recipe, passes) and "read")
        reads = s.reads
        out = {"none": attempt(None), "another bar": attempt(bar_b(s, bar_sha256="0" * 64)), "another recipe": attempt(bar_b(s), "b" * 64),
               "other schema": attempt(bar_b(s, schema="x")), "one mix": attempt(bar_b(s, checkpoint_steps={"dev_mix": [100]})),
               "five checkpoints": attempt(bar_b(s, checkpoint_steps={"dev_mix": [1, 2, 3, 4, 100], "permissive_mix": [100]})),
               "the command, five": caught(lambda: cr.bar_b_value(s.bar, "a" * 64, ["dev_mix:%d" % n for n in range(1, 6)] + ["permissive_mix:1"]) and "written")}
        out["other steps"] = caught(lambda: cr.open_bar_b(bar_b(s, checkpoint_steps={"dev_mix": [100], "permissive_mix": [100]}), cr._sha(s.bar), "a" * 64,
                                                          {"base": [], "dev_mix": [{"steps": 200}], "permissive_mix": [{"steps": 100}]}) and "read")
        out["same steps"] = caught(lambda: cr.open_bar_b(bar_b(s, checkpoint_steps={"dev_mix": [100, 200], "permissive_mix": [50]}), cr._sha(s.bar), "a" * 64,
                                                         {"base": [], "dev_mix": [{"steps": 100}, {"steps": 200}], "permissive_mix": [{"steps": 50}]}) and "read")
        out["another candidate's steps"] = caught(lambda: cr.open_bar_b(bar_b(s, checkpoint_steps={"dev_mix": [100], "permissive_mix": [100]}), cr._sha(s.bar), "a" * 64,
                                                                        {"base": [], "dev_mix": [{"steps": 100}], "permissive_mix": [{"steps": 200}]}) and "read")
        out["counted"] = reads.exists()
        return out


def expected_bar_b():
    return {"none": "ValueError: a frozen recipe needs the second bar file", "another bar": "ValueError: the second bar is not of this bar",
            "another recipe": "ValueError: the second bar names another recipe", "other schema": "ValueError: the second bar is not of this bar",
            "other steps": "ValueError: the second bar names other checkpoints", "same steps": "read",
            "another candidate's steps": "ValueError: the second bar names other checkpoints", "counted": False,
            "one mix": "ValueError: the second bar names both trained mixes, dev_mix and permissive_mix, and no other",
            "five checkpoints": "ValueError: a mix has one to 4 checkpoints, the last and at most three earlier",
            "the command, five": "ValueError: a mix has one to 4 checkpoints, the last and at most three earlier"}


def observe_bar_commands():
    """The written bars are the ones the reader opens, from the command line, each written once."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        run = s.run("run", right_answers)
        bar, second = s.folder / "written.json", s.folder / "written_b.json"
        args = ["bar", "--prompts", str(s.prompts), "--b1", str(s.b1), "--source", str(s.source), "--items", str(s.items), "--out", str(bar)]
        for key in s.keys:
            args += ["--key", key]
        with contextlib.redirect_stdout(io.StringIO()), sample_marks():
            code = cr.main(args)
            again = caught(lambda: cr.main(args))
            code_b = cr.main(["bar-b", "--bar", str(bar), "--recipe", "a" * 64, "--steps", "dev_mix:200", "--steps", "dev_mix:100",
                              "--steps", "permissive_mix:100", "--out", str(second)])
        passes = s.args(("base", run), ("dev_mix", run), ("permissive_mix", run))[0]
        passes["dev_mix"][0]["steps"] = passes["permissive_mix"][0]["steps"] = 100
        passes["dev_mix"].append({"steps": 200, "files": passes["dev_mix"][0]["files"]})
        return {"codes": (code, code_b), "again": again,
                "opens": caught(lambda: bool(cr.open_bar(str(bar), passes, s.keys, str(s.b1), str(s.source), str(s.items)))),
                "second": caught(lambda: bool(cr.open_bar_b(second, cr._sha(bar), "a" * 64, passes))),
                "bad recipe": caught(lambda: cr.bar_b_value(bar, "soon", []))}


def expected_bar_commands():
    return {"codes": (0, 0), "again": "ValueError: this file already exists: a bar is written once", "opens": True, "second": True,
            "bad recipe": "ValueError: the frozen recipe is named by its SHA-256"}


def observe_identity():
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        plain, tuned = s.run("plain", right_answers), s.run("tuned", right_answers, adapter="c" * 64)
        entry = lambda run: {"steps": None, "files": [(str(s.prompts), run)]}
        carried = cr.load("trained", entry(tuned))["identity"][0]["models"]
        return {"base": caught(lambda: bool(cr.load("base", entry(plain)))), "base with adapter": caught(lambda: bool(cr.load("base", entry(tuned)))),
                "trained none": caught(lambda: bool(cr.load("trained", entry(plain)))), "carried": [m["adapter_sha256"] for m in carried.values()]}


def expected_identity():
    return {"base": True, "base with adapter": "ValueError: the base pass had an adapter applied",
            "trained none": "ValueError: a trained pass has no adapter with a digest", "carried": ["c" * 64]}


def observe_same_pass():
    """Half A read one pass; read-b is given another of the same name and steps."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        run = s.run("run", right_answers)
        _read_a(s, s.folder / "a", run)
        path = Path(run) / doc_judge.MEASUREMENT_FILE
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        return {"read": caught(lambda: _read_b(s, s.folder / "a" / cr.RESULT_A, run, "b", base_alone=True) and "read"), "counted": s.reads.exists()}


def expected_same_pass():
    return {"read": "ValueError: half A computed again differs from read-a's file: base on contradoc", "counted": False}


def observe_universe():
    """A left-out claim's prompt is in no count: its failure moves no share."""
    rows = [dict(call(made=YES, kind="claim"), item_id="in", document_id="d"), dict(call(made=None, kind="claim"), item_id="out", document_id="d")]
    documents = {"d": [{"item_id": "in"}]}
    mine = cr.within(rows, "scitab", documents)
    return {"items": [r["item_id"] for r in mine], "void": cr.is_void(mine, documents)[1:]}


def expected_universe():
    return {"items": ["in"], "void": (1.0, 1.0)}


def observe_half_a_lines():
    """Ties past the void lines on half A: reported, void, half B closed, and no threshold read."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        result = _read_a(s, s.folder / "a", s.run("run", lambda user: cdc.logits(Y=5.0, N=5.0)))
    cell = result["candidates"]["base"]["contradoc"]
    return {"state": cell["state"], "why": cell["why"], "readable": cell["prompts_readable"], "whole": cell["documents_whole"], "ties": cell["ties"] == cell["prompts"],
            "threshold": cell.get("threshold")}


def expected_half_a_lines():
    return {"state": "void", "why": "half A is under the void lines; half B stays closed", "readable": 0.0, "whole": 0.0, "ties": True, "threshold": None}


def observe_controls_enter_nothing():
    """Every control answers the opposite: read-a's figures stand, and only the shift reports it."""
    moved = lambda user: "one word.\nNo:" in user
    with tempfile.TemporaryDirectory() as folder:
        plain = Sample(folder)
        one = _read_a(plain, plain.folder / "a", plain.run("run", right_answers))
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder, permuted=True)
        contrary = lambda user: cdc.logits(N=12.0) if moved(user) and right_answers(user)[ord("Y")] else cdc.logits(Y=12.0) if moved(user) else right_answers(user)
        two = _read_a(s, s.folder / "a", s.run("run", contrary))
    cells = two["candidates"]["base"]
    strip = lambda result: {b: {k: v for k, v in c.items() if k in ("state", "threshold", "figures", "prompts", "mass_share_under_floor", "ties")}
                            for b, c in result["candidates"]["base"].items()}
    return {"same": strip(one) == strip(two), "shift": {b: (c["order_control"]["top_answer_changed_share"], c["order_control"]["compared"] > 0) for b, c in cells.items()}}


def expected_controls_enter_nothing():
    return {"same": True, "shift": {"contradoc": (1.0, True), "scitab": (1.0, True)}}


def observe_order_shift():
    """Two calls read both ways, one moved; a control reaches no view of the rows."""
    plain = [dict(call(made=YES), item_id="i"), dict(call(pair=(1, 2), made=NO), item_id="i")]
    controls = [dict(call(made=NO), item_id="i"), dict(call(pair=(1, 2), made=NO), item_id="i"), dict(call(pair=(2, 3), made=YES), item_id="i")]
    documents = {"d": [{"item_id": "i"}]}
    shift = cr.order_shift(plain, controls, FORMS, "contradoc", documents)
    return {"shift": shift, "view": cr.view("contradoc", documents, plain, FORMS, .8)[0]["pairs"]}


def expected_order_shift():
    return {"shift": {"form": "pair", "controls": 3, "compared": 2, "top_answer_changed": 1, "top_answer_changed_share": .5, "mean_flag_probability_shift": .425},
            "view": []}


def _mix(result, figure=None, right=0):
    """A candidate as clearly_worse reads it: `right` of ten rows right, or no read when closed."""
    read = None if figure is None else {"figures": {"macro_f1": figure}, "scored": [{"item_id": "i%d" % n, "cls": "a" if n < right else "b", "gold": "a"} for n in range(10)]}
    return {"result": result, "read": read}


def observe_clearly_worse():
    worse = cr.clearly_worse
    return {"keep lost": worse("contradoc", _mix("drop", .5, 9), _mix("keep", .5, 9)), "keep lost, closed": worse("scitab", _mix("drop"), _mix("keep", .5, 9)),
            "both keep": worse("contradoc", _mix("keep", .5, 9), _mix("keep", .5, 9)), "two documents": worse("contradoc", _mix("keep", .5, 7), _mix("keep", .5, 9)),
            "three documents": worse("contradoc", _mix("keep", .5, 6), _mix("keep", .5, 9)), "under .05": worse("scitab", _mix("keep", .46, 9), _mix("keep", .5, 9)),
            ".05": worse("scitab", _mix("keep", .4, 9), _mix("keep", .5, 9)), "above": worse("contradoc", _mix("keep", .5, 9), _mix("keep", .5, 2)),
            "neither read": worse("scitab", _mix("drop"), _mix("drop"))}


def expected_clearly_worse():
    return {"keep lost": True, "keep lost, closed": True, "both keep": False, "two documents": False, "three documents": True, "under .05": False, ".05": True,
            "above": False, "neither read": False}


def observe_mix_comparison():
    """Both read: the sign test both ways on the items only one gets right, beside the rule."""
    permissive = _mix("keep", .5, 2)
    dev = _mix("keep", .6, 9)
    row = cr.mix_comparison("scitab", permissive, dev)
    return {k: row[k] for k in ("permissive_mix", "dev_mix", "clearly_worse", "permissive_only_right", "dev_only_right", "sign_test_dev_above", "sign_test_permissive_above")}


def expected_mix_comparison():
    return {"permissive_mix": "keep", "dev_mix": "keep", "clearly_worse": True, "permissive_only_right": 0, "dev_only_right": 7,
            "sign_test_dev_above": .007812, "sign_test_permissive_above": 1.0}


def RECIPES():
    return [64, 64]


def observe_two_mixes():
    """Both trained candidates in the one read, the permissive mix beside dev_mix."""
    wrong_on = lambda name: (lambda user: cdc.logits(N=12.0) if name in user else right_answers(user))
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        passes, provenance, files, recipe = s.trained(right_answers, right_answers, lambda user: cdc.logits(N=12.0) if "PASSAGE A" in user else right_answers(user))
        _, keys, b1, source, items = s.args(("base", "x"))
        with sample_marks():
            cr.read_a(str(s.bar), passes, keys, b1, source, items, s.folder / "a")
            result = cr.read_b(str(s.bar), str(s.folder / "a" / cr.RESULT_A), passes, keys, b1, source, items, s.folder / "b", frozen_recipe=recipe,
                               trained_on="invented training sets", in_training_data="no", bar_b_path=bar_b(s, recipe_sha256=recipe), provenance=provenance,
                               recipe_files=files)
    row = result["permissive_beside_dev"]["contradoc"]
    return {"candidates": sorted(result["candidates"]), "reads": result["half_b_reads"], "rule": {b: r["clearly_worse"] for b, r in result["permissive_beside_dev"].items()},
            "shown": sorted(k for k in row if k in ("permissive_mix", "dev_mix", "clearly_worse")),
            "dev above the permissive": (row.get("dev_only_right"), row.get("sign_test_dev_above"))}


def expected_two_mixes():
    return {"candidates": ["base", "dev_mix", "permissive_mix"], "reads": 1, "rule": {"contradoc": False, "scitab": False},
            "shown": ["clearly_worse", "dev_mix", "permissive_mix"], "dev above the permissive": (None, None)}


def observe_provenance():
    """A recipe that is not the two mixes', a provenance of another mix, an adapter its training did
    not save: each refused before the reads file is touched."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        passes, provenance, files, recipe = s.trained(right_answers, right_answers, right_answers)
        attempt = lambda frozen=recipe, given=provenance, recipes=files, at=passes: caught(lambda: cr.checked_provenance(at, given, frozen, recipes) and "read")
        swapped = dict(provenance, dev_mix=provenance["permissive_mix"])
        dev_result = json.loads(Path(provenance["dev_mix"]).read_text(encoding="utf-8"))

        def written(name, **changes):
            path = s.folder / name
            path.write_text(json.dumps(dict(dev_result, **changes)), encoding="utf-8")
            return dict(provenance, dev_mix=str(path))
        later = {n: [dict(e, steps=200 if n == "dev_mix" else e["steps"]) for e in entries] for n, entries in passes.items()}
        return {"right": attempt(), "another recipe": attempt("a" * 64), "another mix's file": attempt(given=swapped),
                "unsaved adapter": attempt(given=written("unsaved.json", adapters=[{"weights_sha256": "0" * 64, "update": 100}])),
                "result's recipe": attempt(given=written("copied.json", recipe_sha256="0" * 64)),
                "steps not its update": attempt(at=later), "recipe files swapped": attempt(recipes={"dev_mix": files["permissive_mix"], "permissive_mix": files["dev_mix"]}),
                "one file": attempt(given={"dev_mix": provenance["dev_mix"]}), "counted": s.reads.exists()}


def expected_provenance():
    return {"right": "read", "another recipe": "ValueError: the frozen recipe is not the two mixes' recipe",
            "another mix's file": "ValueError: the provenance of dev_mix is not that mix's training result",
            "unsaved adapter": "ValueError: a pass of dev_mix applied an adapter its training did not save",
            "result's recipe": "ValueError: the training result of dev_mix names another recipe than its recipe file",
            "steps not its update": "ValueError: a pass of dev_mix names other steps than its adapter's update",
            "recipe files swapped": "ValueError: one dev_mix file and one permissive_mix file",
            "one file": "ValueError: each trained mix needs its training provenance (result.json) and its recipe file", "counted": False}


def observe_half_a_again():
    """read-a's file changed after it was written: read-b computes half A again and refuses."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        run = s.run("run", right_answers)
        _read_a(s, s.folder / "a", run)
        path = s.folder / "a" / cr.RESULT_A
        value = json.loads(path.read_text(encoding="utf-8"))
        value["candidates"]["base"]["contradoc"]["threshold"] = .5
        path.write_text(json.dumps(value), encoding="utf-8")
        return {"read": caught(lambda: _read_b(s, path, run, "b", base_alone=True) and "read"), "counted": s.reads.exists()}


def expected_half_a_again():
    return {"read": "ValueError: half A computed again differs from read-a's file: base on contradoc", "counted": False}


def observe_float32():
    """A pass whose logits were not float32 is refused before half B is opened."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        run = s.run("run", right_answers, dtype="torch.float16")
        result = _read_a(s, s.folder / "a", run)
        cell = result["candidates"]["base"]["contradoc"]
        return {"reported": (cell["logits_dtype"], cell["model_logits_dtype"], cell["read_b"]), "read": caught(lambda: _read_b(s, s.folder / "a" / cr.RESULT_A, run, "b", base_alone=True) and "read"),
                "counted": s.reads.exists()}


def expected_float32():
    return {"reported": (["torch.float16"], ["torch.float16"], "refused: decisions not read from float32 logits"), "read": "ValueError: a pass of base holds decisions not read from float32 logits", "counted": False}


def observe_lock():
    """A read started while another holds the lock is refused, and nothing is appended."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        run = s.run("run", right_answers)
        _read_a(s, s.folder / "a", run)
        lock = Path(str(s.reads) + ".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("{}", encoding="utf-8")
        held = caught(lambda: _read_b(s, s.folder / "a" / cr.RESULT_A, run, "b", base_alone=True) and "read")
        lock.unlink()
        after = caught(lambda: _read_b(s, s.folder / "a" / cr.RESULT_A, run, "c", base_alone=True)["half_b_reads"])
        return {"held": held.split(": C:")[0].split(": /")[0], "after": after, "lock left": lock.exists()}


def expected_lock():
    return {"held": "ValueError: the reads file is locked by another read", "after": 1, "lock left": False}


def observe_rules_m():
    """ContraDoc's no-false-alarm rule rests on B1's whole-sample record, which has false alarms;
    SciTab keeps the half's. A failed call holds no mass. The mark of a token above the answers."""
    clean_b1 = dict(B1, false=0, precision=1.0, flagged=6)
    row = dict(ROW, precision=.8, false=1)
    decision = {"answers": [{"probability": .6}, {"probability": .4}], "declared_mass": .5, "undeclared_top": {"probability": .4}}
    return {"contradoc": cr.precision_holds("contradoc", row, clean_b1), "scitab": cr.precision_holds("scitab", row, clean_b1),
            "failed call": cr.mass_share([call(made=None), call(made=YES)]), "above": cr.above_top({"decision": decision}),
            "below": cr.above_top({"decision": dict(decision, undeclared_top={"probability": .2})})}


def expected_rules_m():
    return {"contradoc": True, "scitab": False, "failed call": .5, "above": True, "below": False}


def observe_one_split():
    """The split choice_judge uses is the reader's, for its order controls and its decisions."""
    documents = {"d%d" % n: {"benchmark": "contradoc"} for n in range(6)} | {"t%d" % n: {"benchmark": "scitab"} for n in range(3)}
    whole = cr.split(documents)
    return {"contradoc": sorted(whole["contradoc"][0]) == sorted(cr.halves(["d%d" % n for n in range(6)])[0]),
            "scitab": sorted(whole["scitab"][0]) == sorted(cr.halves(["t0", "t1", "t2"])[0]), "sizes": [len(whole[b][0]) for b in ("contradoc", "scitab")]}


def expected_one_split():
    return {"contradoc": True, "scitab": True, "sizes": [3, 2]}


def observe_half_b_key():
    """The read key is what half B is: a stray label file, a respaced key and a bar written again
    leave it; a half B label's content moves it."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        run = s.run("run", right_answers)
        passes, keys, b1, source, items = s.args(("base", run))
        key = lambda: cr.half_b_key(cr.context(str(s.bar), passes, keys, b1, source, items, s.folder / "o"))
        with sample_marks():
            first = key()
            stray = s.b1 / "judge_direct_b1" / "stray.json"
            stray.write_text("{}", encoding="utf-8")
            half_b = {d for _, b in cr.split({d: {"benchmark": v["benchmark"]} for d, v in json.loads(s.prompts.read_text(encoding="utf-8"))["documents"].items()}).values() for d in b}
            spaced = next(Path(k) for k in s.keys if Path(k).name[:-len("_key.json")] in half_b)
            spaced.write_text(json.dumps(json.loads(spaced.read_text(encoding="utf-8")), indent=3), encoding="utf-8")
            s.write_bar(written="again")
            same = key() == first
            label = next(s.b1.rglob("labels/*.json"))
            in_half_b = label.parent.parent.name in cr.split({d: {"benchmark": v["benchmark"]} for d, v in json.loads(s.prompts.read_text(encoding="utf-8"))["documents"].items()})[
                json.loads(s.prompts.read_text(encoding="utf-8"))["documents"][label.parent.parent.name]["benchmark"]][1]
            moved = None
            for path in s.b1.rglob("labels/*.json"):
                document = path.parent.parent.name
                if any(document in b for _, b in cr.split({d: {"benchmark": v["benchmark"]} for d, v in json.loads(s.prompts.read_text(encoding="utf-8"))["documents"].items()}).values()):
                    path.write_text(json.dumps(dict(json.loads(path.read_text(encoding="utf-8")), label="moved")), encoding="utf-8")
                    s.write_bar(written="after a label moved")
                    moved = key() != first
                    break
        return {"same half B": same, "a half B label moved": moved, "checked": isinstance(in_half_b, bool), "respaced in half B": spaced.name[:-len("_key.json")] in half_b}


def expected_half_b_key():
    return {"same half B": True, "a half B label moved": True, "checked": True, "respaced in half B": True}


def observe_pins():
    """A respaced items file fails its pin; a key twice, or two keys of one document, is refused."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        spaced = s.folder / "g1_spaced.json"
        spaced.write_text(s.items.read_text(encoding="utf-8") + " ", encoding="utf-8")
        copy = s.folder / "copy_key.json"
        copy.write_text(Path(s.keys[0]).read_text(encoding="utf-8"), encoding="utf-8")
        with sample_marks():
            return {"pinned": bool(cr.universe(s.keys, s.items)), "spaced": caught(lambda: cr.universe(s.keys, spaced) and "read"),
                    "twice": caught(lambda: cr.universe(s.keys + s.keys[:1], s.items) and "read"),
                    "one document twice": caught(lambda: cr.universe(s.keys + [str(copy)], s.items) and "read")}


def expected_pins():
    return {"pinned": True, "spaced": "ValueError: the items file is not the pinned one (doc_judge.BAR_ITEMS_SHA256)",
            "twice": "ValueError: a key is given twice", "one document twice": "ValueError: two keys name document " + "p0"}


def observe_updates_in_bar_b():
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        passes = {"base": [], "dev_mix": [{"steps": 100}], "permissive_mix": [{"steps": 100}]}
        recipes = {"dev_mix": {"updates": [100]}, "permissive_mix": {"updates": [50, 100]}}
        return {"other updates": caught(lambda: cr.open_bar_b(bar_b(s), cr._sha(s.bar), "a" * 64, passes, recipes) and "read"),
                "the updates": caught(lambda: cr.open_bar_b(bar_b(s), cr._sha(s.bar), "a" * 64, passes, dict(recipes, permissive_mix={"updates": [100]})) and "read")}


def expected_updates_in_bar_b():
    return {"other updates": "ValueError: the second bar's checkpoints of permissive_mix are not the updates its training saved", "the updates": "read"}


def observe_git_root():
    import subprocess as sp
    failed = lambda *a, **k: types.SimpleNamespace(returncode=128, stdout="")
    named = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="C:/somewhere/.git\n")
    with patched(sp, "run", failed):
        refused = caught(lambda: str(cr.repository_root()))
    with patched(sp, "run", named):
        root = cr.repository_root().as_posix()
    return {"refused": refused, "named": root}


def expected_git_root():
    return {"refused": "ValueError: git cannot name the repository's common folder: half B's reads have nowhere fixed to be counted", "named": "C:/somewhere"}


def observe_clear_unreadable():
    """CLEAR stands at 95 percent of pairs readable, as C_BAR says; the CLEAR documents holding an
    unreadable pair are counted beside the verdict."""
    rows = [(NO, NO)] * 19 + [(TIED, NO)]
    row = cr.read_document("d", "i", pair_rows(*rows), FORMS, .8)
    view_rows = [row, dict(row, unreadable_pairs=0), dict(row, cls="FLAG")]
    return {"read": (row["cls"], row["unreadable_pairs"]), "counted": cr.reported("contradoc", [], view_rows, [], FORMS, .8)["clear_with_an_unreadable_pair"]}


def expected_clear_unreadable():
    return {"read": ("CLEAR", 1), "counted": 1}


def observe_ungated():
    def pick(table, benchmark="contradoc"):
        with patched(cr, "score", lambda rows, keys, out, left, tag: (None, table[rows])), patched(cr, "view", lambda b, d, r, f, t: t):
            return cr.ungated_threshold(benchmark, {}, [], FORMS, [], ".", set(), "t")
    values = cr.FIGURES["thresholds"]
    gated_out = {v: dict(ROW, accuracy=.5, flagged=30) for v in values}
    gated_out[.7] = dict(ROW, accuracy=.8, flagged=30, precision=.1)
    gated_out[.999] = dict(ROW, accuracy=.95, flagged=0)
    return {"best with no gate": pick(gated_out), "a tie the higher": pick({v: dict(ROW, macro_f1=.6) for v in values}, "scitab"),
            "flags nothing": pick({v: dict(ROW, flagged=0) for v in values})}


def expected_ungated():
    return {"best with no gate": (.7, False), "a tie the higher": (.999, False), "flags nothing": (.999, True)}


def observe_nothing_opens():
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        thin = lambda user: [20.0 if n == ord("q") else v for n, v in enumerate(right_answers(user))]
        run = s.run("run", thin)
        _read_a(s, s.folder / "a", run)
        result = caught(lambda: _read_b(s, s.folder / "a" / cr.RESULT_A, run, "b", base_alone=True) and "read")
        return {"read": result, "file": s.reads.exists()}


def expected_nothing_opens():
    return {"read": "ValueError: every candidate is closed on half A: there is nothing to read, and half B is not spent", "file": False}


def observe_trained():
    """A trained pass beside the base: bound, its verdict adds item 1 against the base and the sign test."""
    with tempfile.TemporaryDirectory() as folder:
        s = Sample(folder)
        passes, provenance, files, recipe = s.trained(lambda user: cdc.logits(N=12.0) if "PASSAGE A" in user else right_answers(user), right_answers, right_answers)
        _, keys, b1, source, items = s.args(("base", "x"))
        second = bar_b(s, recipe_sha256=recipe)
        with sample_marks():
            cr.read_a(str(s.bar), passes, keys, b1, source, items, s.folder / "a")
            refused = caught(lambda: cr.read_b(str(s.bar), str(s.folder / "a" / cr.RESULT_A), passes, keys, b1, source, items, s.folder / "b0",
                                               frozen_recipe=recipe, bar_b_path=second, provenance=provenance, recipe_files=files))
            result = cr.read_b(str(s.bar), str(s.folder / "a" / cr.RESULT_A), passes, keys, b1, source, items, s.folder / "b",
                               frozen_recipe=recipe, trained_on="invented training sets", in_training_data="no", bar_b_path=second, provenance=provenance,
                               recipe_files=files)
    cell = result["candidates"]["dev_mix"]["contradoc"]
    closed = result["candidates"]["base"]["contradoc"]
    return {"refused": refused, "base": closed["result"], "base figure": closed["figures_for_comparison"]["right"],
            "closed base": (closed["compared_at"], closed["flags_nothing"]), "no base verdict": (closed["half_b_verdict"], bool(closed["note"])),
            "recipes": sorted(v["updates"] == [100] and len(v["recipe"]) for v in result["recipes"].values()),
            "above base": cell["tests"]["above_base"], "against": cell["against_base"], "trained_on": result["trained_on"], "reads": result["half_b_reads"],
            "stated": result["benchmarks_in_training_data"]}


def expected_trained():
    return {"refused": "ValueError: a trained candidate's result states what it was trained on and whether the benchmarks were in it", "base": "drop", "base figure": 0,
            "closed base": (.999, True), "no base verdict": (None, True), "recipes": RECIPES(), "above base": True,
            "against": {"wins": 2, "losses": 0, "sign_test": .25, "training_helped": False}, "trained_on": "invented training sets", "reads": 1, "stated": False}


def _flag_on_any_order(rows, forms, threshold):
    pairs = {}
    for r in rows:
        pairs.setdefault(tuple(r["pair"]), []).append(r)
    flagged = {p for p, calls in pairs.items() if any(cr.state(c) == cr.READ and cr.read_at(c, forms, threshold) == ("FLAG", True) for c in calls)}
    return flagged, set(), len(pairs), len(pairs)


def _no_scorer_gold(key_path, labels_dir, arm="B1"):
    labelled = REAL_LABELS(key_path, labels_dir, arm=arm)
    return dict(labelled, items=[dict(i, gold_class="CLEAR") for i in labelled["items"]])


REAL_LABELS = doc_judge._score_corpus().benchmark_labels


@contextlib.contextmanager
def _both_unchecked():
    with patched(cr, "same_passes", lambda passes, first: None), patched(cr, "same_half_a", lambda first, again: None):
        yield


def run_checks():
    sc = doc_judge._score_corpus()
    proofs = [
        ("the split", observe_split, expected_split, lambda: patched(cr, "FIGURES", dict(cr.FIGURES, salt="another:"))),
        ("a tie is no label", observe_no_tie_label, expected_no_tie_label, _tie_read_as_its_first_answer),
        ("a failed call is no label", observe_no_tie_label, expected_no_tie_label, lambda: with_source(
            cr, "read_claim", '"cls": ABSTAIN, "source": state(row)', '"cls": CLEAR, "source": state(row)')),
        ("both orders", observe_reading, expected_reading, lambda: patched(cr, "pair_flags", _flag_on_any_order)),
        ("enough pairs readable", observe_reading, expected_reading, lambda: patched(cr, "FIGURES", dict(cr.FIGURES, document_readable_at_least=.5))),
        ("the verdict", observe_verdict, expected_verdict, lambda: patched(cr, "tests", lambda *a: {"all": True})),
        ("the top answers' macro-F1", observe_verdict, expected_verdict, lambda: with_source(
            cr, "above", 'and top_row["macro_f1"] > (other_top or other)["macro_f1"]', "")),
        ("placed share", observe_verdict, expected_verdict, lambda: with_source(
            cr, "tests", 'placed_share=2 * place_row["placed"] >= place_row["flagged_with_two_marks"]', "placed_share=True")),
        ("the control", observe_verdict, expected_verdict, lambda: with_source(cr, "tests", 'above_python=row["net"] > python["net"]', "above_python=True")),
        ("void first", observe_void, expected_void, lambda: patched(cr, "FIGURES", dict(cr.FIGURES, prompts_readable_at_least=0, whole_documents_at_least=0))),
        ("the threshold", observe_threshold, expected_threshold, lambda: with_source(cr, "choose_threshold", "if best is None or rank > best[0]:", "if best is None or rank >= best[0]:")),
        ("a qualifying threshold", observe_threshold, expected_threshold, lambda: with_source(
            cr, "choose_threshold", 'if not (row["flagged"] >= 1 and flag_share_holds(row) and precision_holds(benchmark, row, b1)):', "if False:")),
        ("the comparator", observe_comparator, expected_comparator, lambda: with_source(cr, "comparator", 'g == REASONING', 'g != REASONING')),
        ("the abstain floor", observe_comparator, expected_comparator, lambda: with_source(
            cr, "comparator", 'if rows[g]["abstain"] <= doc_judge.BAR_MAX_B1_ABSTAIN * rows[g]["items"]', "")),
        ("the sign test", observe_sign, expected_sign, lambda: with_source(cr, "sign_test", "range(wins, n + 1)", "range(wins + 1, n + 1)")),
        ("binding", observe_binding, expected_binding, lambda: patched(cr, "bound", lambda base, rows: None)),
        ("read-a through the scorer", observe_read_a, expected_read_a, lambda: patched(sc, "item_is_flag", lambda key, item: False)),
        ("the split report", observe_split_report, expected_split_report, lambda: patched(doc_judge._score_corpus(), "item_is_flag", lambda key, item: False)),
        ("the split report's bar", observe_split_report, expected_split_report, lambda: patched(cr, "reach", lambda *a: {"gold": 0})),
        ("half B stays closed", observe_half_b_closed, lambda: True, lambda: patched(cr, "halves", _all_in_a)),
        ("the mass test", observe_mass, expected_mass, lambda: patched(cr, "FIGURES", dict(cr.FIGURES, mass_share_at_most=1.0))),
        ("the bar", observe_bar, expected_bar, lambda: with_source(cr, "open_bar", "if bar.get(name) != got:", "if False:")),
        ("the bar's figures", observe_bar, expected_bar, lambda: with_source(cr, "open_bar", 'or bar.get("figures") != FIGURES', "")),
        ("recipe or stated reason", observe_read_b, expected_read_b, lambda: with_source(cr, "read_b", "if bool(frozen_recipe) == bool(base_alone):", "if False:")),
        ("every read counted", observe_read_b, expected_read_b, lambda: patched(cr, "count_read", lambda path, inputs, row, opened: 1)),
        ("the bar written", observe_bar_commands, expected_bar_commands, lambda: with_source(
            cr, "bar_value", '"b1_labels_sha256": labels_digest(b1_root)', '"b1_labels_sha256": "x"')),
        ("a bar written once", observe_bar_commands, expected_bar_commands, lambda: with_source(cr, "write_once", "if Path(path).exists():", "if False:")),
        ("the base and a trained pass", observe_identity, expected_identity, lambda: patched(cr, "pass_identity", lambda name, prompts, measurement: {"models": {"g": {"adapter_sha256": None}}})),
        ("the passes half A read", observe_same_pass, expected_same_pass, lambda: _both_unchecked()),
        ("the universe's items", observe_universe, expected_universe, lambda: with_source(cr, "within", ' and r["item_id"] in items', "")),
        ("the void lines on half A", observe_half_a_lines, expected_half_a_lines, lambda: patched(cr, "FIGURES", dict(cr.FIGURES, prompts_readable_at_least=0, whole_documents_at_least=0))),
        ("a control enters nothing", observe_controls_enter_nothing, expected_controls_enter_nothing, lambda: with_source(
            cr, "load", '(controls if p.get("order_control") else rows).append(kept)', "rows.append(kept)")),
        ("the order control", observe_order_shift, expected_order_shift, lambda: with_source(cr, "order_shift", 'moved += row["decision"]["top"] != control["decision"]["top"]', "moved += 0")),
        ("read once, by what half B is", observe_read_b, expected_read_b, lambda: patched(cr, "half_b_key", lambda ctx: ctx["bar_sha256"])),
        ("read once, by the file in code", observe_read_b, expected_read_b, lambda: patched(cr, "reads_of", lambda path, inputs: 0)),
        ("clearly worse: a keep lost", observe_clearly_worse, expected_clearly_worse, lambda: with_source(
            cr, "clearly_worse", 'if dev["result"] == "keep" and permissive["result"] != "keep":', "if False:")),
        ("clearly worse: documents", observe_clearly_worse, expected_clearly_worse, lambda: patched(cr, "FIGURES", dict(cr.FIGURES, clearly_worse_documents=4))),
        ("clearly worse: macro-F1", observe_clearly_worse, expected_clearly_worse, lambda: patched(cr, "FIGURES", dict(cr.FIGURES, clearly_worse_macro_f1=.2))),
        ("the sign test between the mixes", observe_mix_comparison, expected_mix_comparison, lambda: with_source(
            cr, "mix_comparison", "wins, losses = discordant(permissive", "losses, wins = discordant(permissive")),
        ("the two mixes", observe_two_mixes, expected_two_mixes, lambda: patched(cr, "mix_comparison", lambda benchmark, permissive, dev: {"clearly_worse": None})),
        ("the second bar", observe_bar_b, expected_bar_b, lambda: patched(cr, "open_bar_b", lambda *a: None)),
        ("both mixes in the second bar", observe_bar_b, expected_bar_b, lambda: patched(cr, "checked_steps", lambda fixed: fixed)),
        ("the provenance", observe_provenance, expected_provenance, lambda: patched(cr, "checked_provenance", lambda passes, given, frozen, recipes: {})),
        ("the provenance's recipe", observe_provenance, expected_provenance, lambda: with_source(
            cr, "checked_provenance", "if trainer.pair_digest(recipes[DEV_MIX], recipes[PERMISSIVE_MIX]) != frozen_recipe:", "if False:")),
        ("the provenance's adapters", observe_provenance, expected_provenance, lambda: with_source(
            cr, "checked_provenance", 'if model["adapter_sha256"] not in updates:', "if False:")),
        ("the result's recipe recomputed", observe_provenance, expected_provenance, lambda: with_source(
            cr, "checked_provenance", 'if value.get("recipe_sha256") != trainer.recipe_digest(recipes[name]):', "if False:")),
        ("steps are the adapter's update", observe_provenance, expected_provenance, lambda: with_source(
            cr, "checked_provenance", 'if entry["steps"] != updates.get(model["adapter_sha256"]):', "if False:")),
        ("the read key is half B", observe_half_b_key, expected_half_b_key, lambda: with_source(cr, "half_b_key", '_content(Path(ctx["b1"]) / (g + "_b1") / d / "labels" / (i + ".json"))', "None")),
        ("the read key by content", observe_half_b_key, expected_half_b_key, lambda: patched(doc_judge._score_corpus(), "key_content_digest", lambda path: cr._sha(path))),
        ("the items file pinned", observe_pins, expected_pins, lambda: patched(doc_judge, "_pinned", lambda path: True)),
        ("a key given twice", observe_pins, expected_pins, lambda: with_source(cr, "universe", 'if len({str(Path(k).resolve()) for k in keys}) != len(keys):', "if False:")),
        ("two keys of one document", observe_pins, expected_pins, lambda: with_source(cr, "universe", 'if table["document_id"] in seen_documents:', "if False:")),
        ("the second bar holds the updates", observe_updates_in_bar_b, expected_updates_in_bar_b, lambda: with_source(
            cr, "open_bar_b", 'if set(fixed.get(name) or []) != set(trained["updates"]):', "if False:")),
        ("git names the root, or no read", observe_git_root, expected_git_root, lambda: with_source(
            cr, "repository_root", 'raise ValueError("git cannot name the repository\'s common folder: half B\'s reads have nowhere fixed to be counted")', "return ROOT")),
        ("nothing open, nothing read", observe_nothing_opens, expected_nothing_opens, lambda: with_source(
            cr, "_read_b_locked", 'if not any(c["state"] == "ready" for cells in first["candidates"].values() for c in cells.values()):', "if False:")),
        ("CLEAR with an unreadable pair counted", observe_clear_unreadable, expected_clear_unreadable, lambda: with_source(
            cr, "reported", '"clear_with_an_unreadable_pair": sum(1 for r in view_rows if r["cls"] == CLEAR and r.get("unreadable_pairs")),', '"clear_with_an_unreadable_pair": 0,')),
        ("half A computed again", observe_half_a_again, expected_half_a_again, lambda: patched(cr, "same_half_a", lambda first, again: None)),
        ("float32 or refused", observe_float32, expected_float32, lambda: patched(cr, "float32_only", lambda passes: None)),
        ("the lock", observe_lock, expected_lock, lambda: patched(cr, "ReadsLock", lambda path: contextlib.nullcontext())),
        ("the rules of round 2", observe_rules_m, expected_rules_m, lambda: with_source(cr, "precision_holds", "if whole_false == 0 and row[\"false\"]:", "if row[\"false\"]:")),
        ("a failed call holds no mass", observe_rules_m, expected_rules_m, lambda: with_source(cr, "mass_share", 'if not r["decision"] or r["decision"]["declared_mass"]', 'if r["decision"] and r["decision"]["declared_mass"]')),
        ("one split", observe_one_split, expected_one_split, lambda: patched(cr, "halves", lambda ids: (set(ids), set()))),
        ("the second bar's recipe", observe_bar_b, expected_bar_b, lambda: with_source(cr, "open_bar_b", 'if bar_b.get("recipe_sha256") != frozen_recipe:', "if False:")),
        ("the second bar's checkpoints", observe_bar_b, expected_bar_b, lambda: with_source(
            cr, "open_bar_b", 'if name != BASE and {entry["steps"] for entry in entries} != set(fixed.get(name) or []):', "if False:")),
        ("a closed base: no gate", observe_ungated, expected_ungated, lambda: with_source(
            cr, "ungated_threshold", 'flagging = [(value, row) for value, row in table if row["flagged"]]',
            'flagging = [(value, row) for value, row in table if row["flagged"] and flag_share_holds(row)]')),
        ("a closed base: flags nothing", observe_ungated, expected_ungated, lambda: with_source(cr, "ungated_threshold", "return best[0], not flagging", "return best[0], False")),
        ("a closed base in the result", observe_trained, expected_trained, lambda: with_source(
            cr, "_read_b_locked", 'value = chosen["threshold"] if ready else chosen["ungated_threshold"]', 'value = chosen["threshold"] if ready else FIGURES["thresholds"][0]')),
        ("a trained model beside the base", observe_trained, expected_trained, lambda: with_source(cr, "verdict", 'checks["above_base"] = above(', 'checks["above_base"] = not above(')),
        ("gold through the scorer", observe_read_a, expected_read_a, lambda: patched(sc, "benchmark_labels", _no_scorer_gold)),
    ]
    results = []
    for name, observe, expected, neutralise in proofs:
        results.append(prove_effect(name=name, validate=lambda: choice_judge.CONFIG_PATH.is_file(), observe=observe,
                                    check=lambda: ("PASS" if observe() == expected() else "FAIL", name), neutralise=neutralise))
    return "PASS", ("%d proofs on invented decisions, an invented key and invented B1 labels, no real key read and no score produced: the split, a tie and "
                    "a failed call no label, both orders, the threshold, the mass test, every item of the verdict, the comparator, the sign test, the "
                    "binding, the bar's refusals, half B closed to read-a, and every read of it counted") % len(results)


if __name__ == "__main__":
    print(run_checks())
