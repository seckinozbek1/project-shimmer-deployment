"""Proofs of the D-S92 gate set's code: the declared class setting (D-380), the shared leakage check
(D-S100, D-S102 item 3) and the seeded draw (docs/loop/stages/GATE_SET.md). No model, no real key,
no benchmark file: invented pairs, rows, records and an injected embedder, in a temporary folder.
Each proof is neutralise, fail, restore, pass.

1. SciTab's headline is macro-F1 over the DECLARED setting's classes: 2-class on a 2-class set is
   not the fixed-three figure, and 3-class on a sample with no not-enough-info gold is not the
   gold-present figure (both ways); an undecided answer on a 2-class item is a miss for its gold
   class; no setting, or a gold class outside it, is refused; the CLI requires the setting for
   SciTab and refuses one elsewhere.
2. judge_read.macro_f1 and choice_read.figures the same, both ways, with G1's declaration
   (2-class for both benchmarks) carried in every figure. ContraDoc's R-acc(pos) is over every
   marked positive and EHR over the true positives alone, both stated stricter than BERTScore
   above .98, and a figure from cited units (B3) is labelled unit-level, not the paper's EHR.
3. leakage: an exact copy (case and spacing aside), one shared 8-word run, a cosine at the
   threshold and a listed group each exclude, and a whole group goes with any member; a run of
   digits only, seven shared words and a cosine below the threshold do not; the result holds no
   candidate text; fingerprints with vectors refuse a check without the embedder; archives and
   JSON lines are read; a string under eight words is no record; a judge mix is read under
   `#rows,held_out` only (its questions left out), and any other set is checked through
   `--candidates`, a malformed file or two inputs refused.
4. the draw: the claim set and the quick subset are disjoint, in salted-hash order, one document a
   group (ContraDoc) or whole papers to both minima (SciTab); too few is refused, never filled;
   a leakage result without the cosine rule, or with other thresholds, is refused.
5. the class setting: 3-class at 30 not-enough-info claims and 15 percent, 2-class below either.
6. the gate's figures (gate_score.py): one paired cluster bootstrap (two identical arms differ by
   exactly zero), bar (a) at 10 points with the interval above zero, bar (b) at 5 points below the
   cloud reference, SciTab resampled by table in its declared setting, the same items in every arm.
"""
from __future__ import annotations

import contextlib
import gzip
import hashlib
import importlib
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "adapters")):
    if path not in sys.path:
        sys.path.insert(0, path)

from effect_proof import prove_effect  # noqa: E402
from common import cli, gate_leakage as leakage, metrics  # noqa: E402

scitab = importlib.import_module("scitab.adapter")
contradoc = importlib.import_module("contradoc.adapter")
judge_read = importlib.import_module("judge_read")
choice_read = importlib.import_module("choice_read")
gate_set = importlib.import_module("gate_set")
gate_score = importlib.import_module("gate_score")

S, R, N, A = "supports", "refutes", "not enough info", metrics.ABSTAIN
FLAG, CLEAR, UNDECIDED = "FLAG", "CLEAR", "UNDECIDED"


def patched(obj, name, value):
    return mock.patch.object(obj, name, value)


def caught(fn):
    try:
        fn()
    except ValueError as exc:
        return "refused: " + str(exc).split(":")[0]
    return "accepted"


# ---- 1 and 2: the declared class setting ------------------------------------------------------

TWO_CLASS = [(S, S), (S, S), (R, S), (N, S), (R, R), (S, R), (A, R)]
# supports tp2 fp1 fn2 -> 4/7; refutes tp1 fp1 fn2 -> 2/5; 2-class macro (4/7 + 2/5) / 2 = 34/70
THREE_SAMPLE = [(S, S), (R, S), (N, S), (R, R), (N, R)]
# no not-enough-info gold: 3-class adds its F1 0 (two false positives), gold present would not


def observe_scitab():
    return {"2-class": round(scitab.headline(TWO_CLASS, setting="2-class")["macro_f1"], 6),
            "3-class sample": round(scitab.headline(THREE_SAMPLE, setting="3-class")["macro_f1"], 6),
            "undecided is a miss": [(c["class"], c["fp"], c["fn"]) for c in
                                    scitab.headline([(N, S), (R, R)], setting="2-class")["per_class"]],
            "no setting": caught(lambda: scitab.headline(TWO_CLASS)),
            "gold outside": caught(lambda: scitab.headline([(S, N)], setting="2-class")),
            "cli scitab": caught(lambda: cli.headline_of(scitab)),
            "cli contradoc": caught(lambda: cli.headline_of(contradoc, "2-class")),
            "measure": scitab.headline(TWO_CLASS, setting="2-class")["headline_measure"]}


def expected_scitab():
    # THREE_SAMPLE: supports tp1 fp0 fn2 -> 1/2; refutes tp1 fp1 fn1 -> 1/2; not enough info tp0 fp2 -> 0
    return {"2-class": round((4 / 7 + 2 / 5) / 2, 6),
            "3-class sample": round((1 / 2 + 1 / 2 + 0.0) / 3, 6),
            "undecided is a miss": [(S, 0, 1), (R, 0, 0)],
            "no setting": "refused: SciTab's class setting is declared per item set (D-380)",
            "gold outside": "refused: the set is declared 2-class but holds gold not enough info",
            "cli scitab": "refused: scitab's class setting is declared per item set (D-380)",
            "cli contradoc": "refused: contradoc declares no class setting",
            "measure": "2-class macro-F1 over supports, refutes (declared, D-380)"}


def _scitab_forced_three():
    real = scitab.headline

    def headline(pairs, rows=None, answers=None, unit_text=None, *, setting=None):
        return real(pairs, rows, answers, unit_text, setting="3-class")
    return patched(scitab, "headline", headline)


def _scitab_gold_present():
    real = scitab.headline

    def headline(pairs, rows=None, answers=None, unit_text=None, *, setting=None):
        out = real(pairs, rows, answers, unit_text, setting=setting)
        classes = sorted({g for _p, g in pairs})
        out["macro_f1"] = metrics.macro_f1(pairs, classes)["macro_f1"]
        return out
    return patched(scitab, "headline", headline)


def _rows(pairs, benchmark="scitab"):
    m = {S: CLEAR, R: FLAG, N: UNDECIDED, A: A}
    return [{"document_id": "d%d" % i, "item_id": "i%d" % i, "benchmark": benchmark, "cls": m[p], "gold": m[g],
             "source": "x", "was_refused": False, "written_cls": m[p]} for i, (p, g) in enumerate(pairs)]


def observe_judge_read():
    two = _rows(TWO_CLASS)
    sample = _rows(THREE_SAMPLE)
    fig = choice_read.figures(two, judge_read.class_setting(judge_read.G1_SETTINGS, "scitab"))
    return {"2-class": judge_read.macro_f1(two, "2-class"), "3-class sample": judge_read.macro_f1(sample, "3-class"),
            "no setting": caught(lambda: judge_read.macro_f1(two, None)),
            "gold outside": caught(lambda: judge_read.macro_f1(_rows([(S, N)]), "2-class")),
            "figures": judge_read.figures(two, judge_read.G1_SETTINGS)["scitab"]["class_setting"],
            "figures need a setting": caught(lambda: judge_read.figures(two, {})),
            "choice_read": (fig["class_setting"], fig["macro_f1"], sorted(fig["class_f1"])),
            "G1": judge_read.G1_SETTINGS}


def expected_judge_read():
    head2 = round(scitab.headline(TWO_CLASS, setting="2-class")["macro_f1"], 6)
    head3 = round(scitab.headline(THREE_SAMPLE, setting="3-class")["macro_f1"], 6)
    return {"2-class": head2, "3-class sample": head3,
            "no setting": "refused: the class setting is declared per item set (D-380)",
            "gold outside": "refused: the set is declared 2-class but holds gold UNDECIDED",
            "figures": "2-class", "figures need a setting": "refused: no declared class setting for scitab (D-380)",
            "choice_read": ("2-class", head2, [CLEAR, FLAG]), "G1": {"scitab": "2-class", "contradoc": "2-class"}}


def _judge_forced_three():
    real = judge_read.macro_f1
    return patched(judge_read, "macro_f1", lambda rows, setting: real(rows, "3-class"))


def _judge_gold_present():
    def macro(rows, setting):
        pairs = [(r["cls"], r["gold"]) for r in rows]
        classes = sorted({r["gold"] for r in rows})
        return round(sum(metrics.class_scores(pairs, c)["f1"] for c in classes) / len(classes), 6)
    return patched(judge_read, "macro_f1", macro)


# ---- 2b: ContraDoc's evidence measures (D-376) ---------------------------------------------------

def _contradoc_case(arm):
    pos, neg = contradoc.SPEC.labels[FLAG], contradoc.SPEC.labels[CLEAR]
    needle = "It is midnight."
    answers = {"p1": {"gold": pos, "evidence_sentence": needle, "document_units": 2},
               "p2": {"gold": pos, "evidence_sentence": needle, "document_units": 2},
               "p3": {"gold": pos, "evidence_sentence": needle, "document_units": 1},
               "n1": {"gold": neg, "evidence_sentence": "", "document_units": 2}}
    rows = [{"item_id": "p1", "document_id": "d1", "arm": arm, "class": FLAG, "cited_unit_ids": ["u1"], "evidence": needle},
            {"item_id": "p2", "document_id": "d2", "arm": arm, "class": FLAG, "cited_unit_ids": ["u2"], "evidence": "Noon."},
            {"item_id": "p3", "document_id": "d3", "arm": arm, "class": CLEAR, "cited_unit_ids": [], "evidence": None},
            {"item_id": "n1", "document_id": "d4", "arm": arm, "class": CLEAR, "cited_unit_ids": [], "evidence": None}]
    texts = {("d1", "u1"): "Noon. " + needle, ("d2", "u2"): "Noon."}
    pairs = [(contradoc.SPEC.label(r["class"]), answers[r["item_id"]]["gold"]) for r in rows]
    return contradoc.headline(pairs, rows, answers, lambda d, u: texts.get((d, u), ""))


def observe_contradoc():
    out = {}
    for arm in ("B1", "B3"):
        h = _contradoc_case(arm)
        out[arm] = {k: (h[k]["value"], h[k].get("marked", h[k].get("true_positives")), h[k]["level"])
                    for k in ("r_acc_pos", "r_acc_pos_multi_unit", "ehr_true_positives", "ehr_true_positives_multi_unit")}
        out[arm]["accuracy"] = h["headline_value"]
        out[arm]["stricter"] = "stricter than the paper's BERTScore above .98" in h["r_acc_pos"]["measure"]
    return out


def expected_contradoc():
    def one(level):
        # three marked positives (p1 hit, p2 miss, p3 not flagged); two true positives (p1, p2)
        return {"r_acc_pos": (1 / 3, 3, level), "r_acc_pos_multi_unit": (1 / 2, 2, level),
                "ehr_true_positives": (1 / 2, 2, level), "ehr_true_positives_multi_unit": (1 / 2, 2, level),
                "accuracy": 3 / 4, "stricter": True}
    return {"B1": one("quoted evidence"), "B3": one("unit-level, not the paper's EHR")}


def _ehr_over_every_positive():
    real = contradoc.headline

    def headline(pairs, rows, answers, unit_text):
        out = real(pairs, rows, answers, unit_text)
        for k, r in (("ehr_true_positives", "r_acc_pos"), ("ehr_true_positives_multi_unit", "r_acc_pos_multi_unit")):
            out[k] = dict(out[k], value=out[r]["value"], true_positives=out[r]["marked"])
        return out
    return patched(contradoc, "headline", headline)


# ---- 3: leakage ---------------------------------------------------------------------------------

PART_DOC = "The council approved the harbour plan on Tuesday after a long debate about funding and the new road"
OTHER = "A wholly different text about mountains rivers and the weather that nobody has written before today here"


def _embedder(table):
    """Vectors by text: a text's vector is looked up by its first word, unit length guaranteed by the tool."""
    def embed(texts):
        return [table.get(str(t).split()[0].casefold() if str(t).split() else "", [0.0, 0.0, 1.0]) for t in texts]
    return embed


def _write_parts(folder):
    folder = Path(folder)
    (folder / "a.json").write_text(json.dumps({"rows": [{"text": PART_DOC}, {"short": "too short to be a record"}]}), encoding="utf-8")
    (folder / "b.jsonl").write_text(json.dumps({"t": "one two three four five six seven eight nine"}) + "\n", encoding="utf-8")
    member = json.dumps(["figures were 1 2 3 4 5 6 7 8 9 10 in the table today and more"]).encode("utf-8")
    with tarfile.open(folder / "c.tar.gz", "w:gz") as tar:
        info = tarfile.TarInfo("inner/rows.json")
        info.size = len(member)
        tar.addfile(info, io.BytesIO(member))
    return [("judge", str(folder / "a.json")), ("producer", str(folder / "b.jsonl")), ("auditor", str(folder / "c.tar.gz"))]


def _candidates():
    words = PART_DOC.split()
    return [
        {"id": "exact", "group": "g1", "texts": ["  " + PART_DOC.upper() + " "]},
        {"id": "run", "group": "g2", "texts": ["zzz " + " ".join(words[3:11]) + " qqq"]},
        {"id": "seven", "group": "g3", "texts": ["zzz " + " ".join(words[3:10]) + " qqq yyy"]},
        {"id": "digits", "group": "g4", "texts": ["x 1 2 3 4 5 6 7 8 9 10 y"]},
        {"id": "near", "group": "g5", "texts": ["near " + OTHER]},
        {"id": "far", "group": "g6", "texts": ["far " + OTHER]},
        {"id": "listed", "group": "g7", "texts": ["clean " + OTHER]},
        {"id": "mate", "group": "g2", "texts": ["clean " + OTHER]},
        {"id": "keep", "group": "g8", "texts": ["clean " + OTHER]},
    ]


VECTORS = {"the": [1.0, 0.0, 0.0], "one": [0.0, 1.0, 0.0], "figures": [0.0, -1.0, 0.0], "near": [0.93, (1 - 0.93 ** 2) ** 0.5, 0.0],
           "far": [0.91, (1 - 0.91 ** 2) ** 0.5, 0.0], "clean": [0.0, 0.0, 1.0], "zzz": [0.0, 0.0, 1.0],
           "x": [0.0, 0.0, 1.0], "": [0.0, 0.0, 1.0]}


def observe_leakage():
    with tempfile.TemporaryDirectory() as tmp:
        parts = _write_parts(tmp)
        embed = _embedder(VECTORS)
        data = leakage.fingerprint(parts, embed)
        out = Path(tmp) / "fp.json.gz"
        leakage.write(data, out)
        data = leakage.read(out)
        result = leakage.check(data, _candidates(), embed, exclude_groups=["g7"])
        text = json.dumps(result)
        return {"records": data["records"], "excluded": result["excluded_ids"],
                "groups out": result["excluded_group_keys"], "kept": result["kept_group_keys"],
                "no text": not any(w in text for w in ("council", "harbour", "mountains", "figures were")),
                "no embedder": caught(lambda: leakage.check(data, _candidates())),
                "by part": result["candidates_by_part"]}


def expected_leakage():
    return {"records": {"auditor": 1, "judge": 1, "producer": 1},
            "excluded": {"exact": ["cosine", "exact", "runs"], "listed": ["source"], "near": ["cosine"], "run": ["runs"]},
            "groups out": ["g1", "g2", "g5", "g7"], "kept": ["g3", "g4", "g6", "g8"], "no text": True,
            "no embedder": "refused: the fingerprints carry vectors", "by part": {"judge": 3}}


MIX_ROW = "Every resident of the valley signed the petition before the new school opened its doors"
MIX_QUESTION = "A read development prompt that is not a training row and must stay out of the mix part"


def observe_mix_and_any_set():
    """A judge mix read by `#rows,held_out` (its `questions` left out), and another set's candidates
    checked through the CLI with --candidates, counts and ids only."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        session = {"schema": "judge-training-v1", "questions": [{"user": MIX_QUESTION}],
                   "recipes": [{"name": "mix", "rows": [{"user": MIX_ROW, "answer": "holds"}],
                                "held_out": [{"user": MIX_ROW + " again"}]}]}
        (tmp / "session.json").write_text(json.dumps(session), encoding="utf-8")
        data = leakage.fingerprint([("mix", str(tmp / "session.json"), ["rows", "held_out"])])
        leakage.write(data, tmp / "fp.json.gz")
        cands = [{"id": "q1", "group": "g1", "texts": [MIX_ROW]}, {"id": "q2", "group": "g2", "texts": [MIX_QUESTION]},
                 {"id": "q3", "group": "g3", "texts": ["Nothing here is shared with any part at all today"]}]
        (tmp / "cands.json").write_text(json.dumps(cands), encoding="utf-8")
        (tmp / "none.json").write_text(json.dumps({"group_keys": []}), encoding="utf-8")
        (tmp / "step.json").write_text(json.dumps({"threshold_by_rule": leakage.COSINE}), encoding="utf-8")
        ex = ["--exclude-groups", str(tmp / "none.json"), "--cosine-step", str(tmp / "step.json")]
        out = tmp / "result.json"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = leakage.main(["check", "--fingerprints", str(tmp / "fp.json.gz"), "--candidates", str(tmp / "cands.json"), "--out", str(out), *ex])
            both = leakage.main(["check", "--fingerprints", str(tmp / "fp.json.gz"), "--candidates", str(tmp / "cands.json"),
                                 "--benchmark", "scitab", "--input", "x", "--out", str(tmp / "r2.json"), *ex])
            (tmp / "bad.json").write_text(json.dumps([{"id": "x", "texts": "not a list"}]), encoding="utf-8")
            bad = leakage.main(["check", "--fingerprints", str(tmp / "fp.json.gz"), "--candidates", str(tmp / "bad.json"), "--out", str(tmp / "r3.json"), *ex])
        result = json.loads(out.read_text(encoding="utf-8"))
        return {"mix records": data["records"], "exit": code, "excluded": result["excluded_ids"], "kept": result["kept_group_keys"],
                "both refused": both, "bad refused": bad}


def expected_mix_and_any_set():
    return {"mix records": {"mix": 2}, "exit": 0, "excluded": {"q1": ["exact", "runs"]}, "kept": ["g2", "g3"],
            "both refused": 2, "bad refused": 2}


# ---- 4 and 5: the draw and the class setting ------------------------------------------------

EXPECTED = {"fingerprints_sha256": "f" * 64, "exclude_ids_sha256": "e" * 64, "cosine_step_sha256": "s" * 64}


def _leak(kept, cosine="applied", thresholds=None, exclusion="e" * 64, parts=None, input_sha256="i" * 64, fingerprints="f" * 64,
          stray=None, stray_path="C:/r/somewhere/else.json"):
    files = {part: [{"file": "C:/r/" + gate_set.PART_PATHS[part][0] + "x.json", "sha256": "0" * 64}] for part in gate_set.REQUIRED_PARTS}
    if stray:
        files[stray] = [{"file": stray_path, "sha256": "0" * 64}]
    return {"format": leakage.FORMAT, "thresholds": thresholds or leakage.THRESHOLDS, "cosine_rule": cosine, "fingerprint_files": files,
            "kept_group_keys": sorted(kept), "fingerprint_parts": list(gate_set.REQUIRED_PARTS if parts is None else parts),
            "provenance": {"exclude_ids_sha256": exclusion, "input_sha256": input_sha256, "fingerprints_sha256": fingerprints,
                           "cosine_step_sha256": "s" * 64}}


def observe_draw():
    cands = [{"id": "%d-%d" % (g, m), "group": "G%03d" % g, "texts": []} for g in range(12) for m in range(1 + g % 3)]
    kept = {"G%03d" % g for g in range(12) if g != 5}
    cd = gate_set.draw_contradoc(cands, _leak(kept), n_quick=3, n_claim=6, input_sha256="i" * 64)
    claim, quick = [r["group"] for r in cd["claim"]], [r["group"] for r in cd["quick"]]
    papers = [{"id": "c%d-%d-%d" % (p, t, k), "group": "P%02d" % p, "table": "T%d-%d" % (p, t), "texts": []}
              for p in range(10) for t in range(1 + p % 2) for k in range(3)]
    st = gate_set.draw_scitab(papers, _leak({"P%02d" % p for p in range(10)}), {"tables": 2, "claims": 6}, 18,
                              v3_tables=3)
    sp = sorted({r["paper"] for r in st["claim"]})
    sq = sorted({r["paper"] for r in st["quick"]})
    return {"contradoc claim": claim, "contradoc quick": quick,
            "one a group": [r["document"] for r in cd["claim"]],
            "disjoint": not set(claim) & set(quick) and not set(sp) & set(sq),
            "a claim set of its fixed size": len(claim) == 6,
            "scitab claim": sp, "scitab quick": sq, "v3 held back": st["v3_sealed_papers"],
            "v3 apart": not set(st["v3_sealed_papers"]) & (set(sp) | set(sq)),
            "scitab sizes": (len(st["claim"]), sum(len(r["claims"]) for r in st["claim"])),
            "too few": caught(lambda: gate_set.draw_contradoc(cands, _leak(kept), n_quick=3, n_claim=10)),
            "no cosine": caught(lambda: gate_set.draw_contradoc(cands, _leak(kept, cosine="no vectors"), 3, 6)),
            "other thresholds": caught(lambda: gate_set.draw_contradoc(cands, _leak(kept, thresholds={"cosine": .5}), 3, 6)),
            "no exclusion file": caught(lambda: gate_set.draw_contradoc(cands, _leak(kept, exclusion=None), 3, 6)),
            "another input": caught(lambda: gate_set.draw_contradoc(cands, _leak(kept), 3, 6, input_sha256="o" * 64)),
            "a part missing": caught(lambda: gate_set.draw_contradoc(cands, _leak(kept, parts=["judge"]), 3, 6)),
            "other fingerprints": caught(lambda: gate_set.draw_contradoc(cands, _leak(kept, fingerprints="g" * 64), 3, 6, expected=EXPECTED)),
            "a part from another path": caught(lambda: gate_set.draw_contradoc(cands, _leak(kept, stray="verifier"), 3, 6)),
            "a part's path as a substring only": caught(lambda: gate_set.draw_contradoc(
                cands, _leak(kept, stray="verifier", stray_path="C:/r/notexternal/s05/VER/x.json"), 3, 6)),
            "another part's folder as development": caught(lambda: gate_set.draw_contradoc(
                cands, _leak(kept, stray="development", stray_path="C:/r/external/s05/T/t_session.json"), 3, 6)),
            "the expected ones": len(gate_set.draw_contradoc(cands, _leak(kept), 3, 6, expected=EXPECTED)["claim"])}


CLAIM_SALT, QUICK_SALT = "20261109-D-S92:", "20261109-gate-quick:"   # GATE_SET.md, written before the draw


def _order(keys, salt):
    import hashlib
    return sorted(keys, key=lambda k: (hashlib.sha256((salt + k).encode("utf-8")).hexdigest(), k))


def expected_draw():
    kept = ["G%03d" % g for g in range(12) if g != 5]
    quick = _order(kept, QUICK_SALT)[:3]
    claim = _order(set(kept) - set(quick), CLAIM_SALT)[:6]
    members = {"G%03d" % g: ["%d-%d" % (g, m) for m in range(1 + g % 3)] for g in range(12)}
    papers = ["P%02d" % p for p in range(10)]
    tables = {p: 1 + int(p[1:]) % 2 for p in papers}
    held, h = [], 0
    for p in _order(papers, "20261109-v3-sealed:"):
        if h >= 3:
            break
        held.append(p)
        h += tables[p]
    rest = [p for p in papers if p not in held]
    sq, u = [], 0
    for p in _order(rest, QUICK_SALT):
        if u >= 2 and 3 * u >= 6:
            break
        sq.append(p)
        u += tables[p]
    sp, t = [], 0
    for p in _order(set(rest) - set(sq), CLAIM_SALT):
        if 3 * t >= 18:
            break
        sp.append(p)
        t += tables[p]
    sp = sorted(sp)
    missing = ", ".join(sorted(set(gate_set.REQUIRED_PARTS) - {"judge"}))
    return {"contradoc claim": claim, "contradoc quick": quick,
            "one a group": [_order(members[g], CLAIM_SALT)[0] for g in claim], "disjoint": True, "a claim set of its fixed size": True,
            "scitab claim": sp, "scitab quick": sorted(sq), "v3 held back": sorted(held), "v3 apart": True, "scitab sizes": (t, 3 * t),
            "too few": "refused: 11 groups kept; the quick subset needs 3 and the claim set 10",
            "no cosine": "refused: the leakage result did not apply the cosine rule",
            "other thresholds": "refused: the leakage result was made with another format or other thresholds",
            "no exclusion file": "refused: the leakage result names no exclusion file",
            "another input": "refused: the leakage result was made on another input than this draw's",
            "a part missing": "refused: the fingerprints lack parts",
            "other fingerprints": "refused: the leakage result's fingerprints_sha256 is not the one this draw expects",
            "a part from another path": "refused: part verifier was fingerprinted from other paths than section 9 names",
            "a part's path as a substring only": "refused: part verifier was fingerprinted from other paths than section 9 names",
            "another part's folder as development": "refused: part development was fingerprinted from other paths than section 9 names",
            "the expected ones": len(claim)}


def observe_setting():
    return [gate_set.class_setting({S: 100, R: 70, N: 30})["setting"], gate_set.class_setting({S: 100, R: 71, N: 29})["setting"],
            gate_set.class_setting({S: 100, R: 71, N: 30})["setting"], gate_set.class_setting({S: 50, R: 50})["setting"],
            gate_set.class_setting({S: 100, R: 71, N: 29})["not_enough_info_left_out"],
            caught(lambda: gate_set.class_setting({"neutral": 3}))]


def expected_setting():
    return ["3-class", "2-class", "2-class", "2-class", 29, "refused: counts are {supports, refutes, not enough info"]


def observe_v3():
    """v3's share counts usable tables only (a demonstration table not counted) and lists the held
    papers the leakage check flagged."""
    papers = [{"id": "v%d-%d" % (p, t), "group": "Q%02d" % p, "table": "U%d-%d" % (p, t), "texts": []} for p in range(12) for t in range(2)]
    order = _order(["Q%02d" % p for p in range(12)], "20261109-v3-sealed:")
    demonstration = ["U%d-0" % int(order[0][1:])]
    held = gate_set.hold_back_v3(papers, 4, demonstration)
    plain = gate_set.hold_back_v3(papers, 4)
    kept = {"Q%02d" % p for p in range(12)} - {order[0]}
    out = gate_set.draw_scitab(papers, _leak(kept), {"tables": 2, "claims": 2}, 2, v3_tables=4,
                               demonstration=demonstration)
    return {"held": held, "plain": plain, "flagged": out["v3_papers_the_check_flagged"]}


def expected_v3():
    order = _order(["Q%02d" % p for p in range(12)], "20261109-v3-sealed:")
    return {"held": order[:3], "plain": order[:2], "flagged": [order[0]]}


def observe_freeze():
    """The freeze writes the claim set and the quick subset as two separate files, ids only, with the
    scorer's opaque ids; under 2-class the not-enough-info claims leave both, a table left empty leaves;
    the two sets share no ContraDoc group and no SciTab paper."""
    from common import ids as common_ids
    cd = {"claim": [{"group": "g1", "document": "d1"}], "quick": [{"group": "g2", "document": "d2"}]}
    st = {"claim": [{"paper": "p1", "table": "t1", "claims": ["c1", "c2"]}, {"paper": "p3", "table": "t3", "claims": ["c5"]}],
          "quick": [{"paper": "p2", "table": "t2", "claims": ["c3", "c4"]}]}
    # the class-setting result as class_setting writes it on the drawn claim set (D-380, D-458: c1
    # supports, c2 and c5 not enough info), with role B's ids of both sets added (c4 is the quick subset's)
    two = dict(gate_set.class_setting({S: 1, N: 2}), not_enough_info_ids=["c2", "c5", "c4"])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "cd.json").write_text(json.dumps(cd), encoding="utf-8")
        (tmp / "st.json").write_text(json.dumps(st), encoding="utf-8")
        (tmp / "setting.json").write_text(json.dumps(two), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            code = gate_set.main(["freeze", "--contradoc-ids", str(tmp / "cd.json"), "--scitab-ids", str(tmp / "st.json"),
                                  "--class-setting", str(tmp / "setting.json"), "--out-dir", str(tmp)])
        if code != 0:
            return {"code": code}
        files = sorted(q.name for q in tmp.glob("*_set_ids.json"))
        claim = json.loads((tmp / "claim_set_ids.json").read_text(encoding="utf-8"))
        quick = json.loads((tmp / "quick_set_ids.json").read_text(encoding="utf-8"))
    three = {"setting": "3-class", "not_enough_info_ids": []}
    st3 = st
    stray = caught(lambda: gate_set.freeze(cd, st, dict(two, not_enough_info_ids=["c2", "c5", "zz"])))
    return {"code": code, "files": files, "setting": claim["scitab_class_setting"],
            "claim scitab": [(r["table"], r["claims"]) for r in claim["scitab"]], "quick scitab": [(r["table"], r["claims"]) for r in quick["scitab"]],
            "left out": (claim["not_enough_info_left_out"], quick["not_enough_info_left_out"]),
            "opaque": claim["contradoc"][0]["item_id"] == common_ids.opaque_item_id("contradoc", "d1"),
            "shared group": caught(lambda: gate_set.freeze({"claim": cd["claim"], "quick": cd["claim"]}, st3, three)),
            "shared paper": caught(lambda: gate_set.freeze(cd, {"claim": st["claim"], "quick": st["claim"]}, three)),
            "3-class with ids": caught(lambda: gate_set.freeze(cd, st3, dict(three, not_enough_info_ids=["c2"]))),
            "no setting": caught(lambda: gate_set.freeze(cd, st, {})),
            "an id in neither set": stray, "scored and drawn": (claim["scored_claims"], claim["drawn_claims"]),
            "the claim count only": caught(lambda: gate_set.freeze(cd, st, dict(two, not_enough_info_ids=["c2", "c4"])))}


def expected_freeze():
    return {"code": 0, "files": ["claim_set_ids.json", "quick_set_ids.json"], "setting": "2-class",
            "claim scitab": [("t1", ["c1"])], "quick scitab": [("t2", ["c3"])], "left out": (["c2", "c5"], ["c4"]), "opaque": True,
            "shared group": "refused: the claim set and the quick subset share a document group",
            "shared paper": "refused: the claim set and the quick subset share a paper",
            "3-class with ids": "refused: a 3-class set keeps its not-enough-info claims",
            "no setting": "refused: the freeze needs SciTab's declared class setting",
            "an id in neither set": "refused: not-enough-info ids that are in neither set", "scored and drawn": (1, 3),
            "the claim count only": "refused: the claim set's not-enough-info ids are not as many as the class-setting result counted"}


@contextlib.contextmanager
def _all(*contexts):
    """Several neutralisations at once: the guard's digest test and the exclusion list's own pin are two
    layers of one rule."""
    with contextlib.ExitStack() as stack:
        for c in contexts:
            stack.enter_context(c)
        yield


@contextlib.contextmanager
def _patches(*triples):
    with contextlib.ExitStack() as stack:
        for obj, name, value in triples:
            stack.enter_context(patched(obj, name, value))
        yield


def observe_sizes():
    """D-454, D-458: the claim set takes whole groups or papers in claim-salt order until it reaches its
    size and stops at the first that does; SciTab's size is 352 whatever the class setting, counted as
    drawn; the draw never reads a label (gold attached to the candidates changes nothing); a pool that
    cannot reach the size is refused."""
    papers = [{"id": "s%d-%d-%d" % (p, t, k), "group": "R%02d" % p, "table": "W%d-%d" % (p, t), "texts": []}
              for p in range(10) for t in range(1 + p % 2) for k in range(3)]
    leak = _leak({"R%02d" % p for p in range(10)})
    plain = gate_set.draw_scitab(papers, leak, {"tables": 1, "claims": 1}, 9, v3_tables=0)
    labelled = [dict(c, label=("not enough info" if i % 3 == 0 else "supports")) for i, c in enumerate(papers)]
    relabelled = [dict(c, label=("not enough info" if i % 3 == 1 else "refutes")) for i, c in enumerate(papers)]
    with patched(gate_set, "SCITAB_CLAIM_CLAIMS", 13):
        default = gate_set.draw_scitab(papers, leak, {"tables": 1, "claims": 1}, v3_tables=0)
        blind = [gate_set.draw_scitab(c, leak, {"tables": 1, "claims": 1}, v3_tables=0)["claim"] for c in (labelled, relabelled)]
    groups = [{"id": "%d" % g, "group": "H%02d" % g, "texts": []} for g in range(8)]
    cd = gate_set.draw_contradoc(groups, _leak({"H%02d" % g for g in range(8)}), n_quick=2, n_claim=5)
    return {"plain": [r["paper"] for r in plain["claim"]], "plain drawn": plain["claims_drawn"],
            "the default size": (sorted({r["paper"] for r in default["claim"]}), default["claims_drawn"]),
            "labels change nothing": blind[0] == blind[1] == default["claim"],
            "the size": gate_set.SCITAB_CLAIM_CLAIMS,
            "candidates carry no label": sorted({k for c in leakage.candidates_scitab([{"id": "c", "paper_id": "p", "table_id": "t",
                                                 "claim": "x", "label": "supports", "table_caption": "y",
                                                 "table_column_names": ["a"], "table_content_values": [["1"]]}]) for k in c}),
            "contradoc": [r["group"] for r in cd["claim"]],
            "too small a pool": caught(lambda: gate_set.draw_scitab(papers, leak, {"tables": 1, "claims": 1}, 100, v3_tables=0)),
            "too few groups": caught(lambda: gate_set.draw_contradoc(groups, _leak({"H%02d" % g for g in range(8)}), n_quick=2, n_claim=7))}


def expected_sizes():
    tables = {"R%02d" % p: 1 + p % 2 for p in range(10)}
    quick = _order(list(tables), QUICK_SALT)[:1]

    def take(size):
        chosen, n = [], 0
        for p in _order(set(tables) - set(quick), CLAIM_SALT):
            if n >= size:
                break
            chosen.append(p)
            n += 3 * tables[p]
        return [(p, t) for p in chosen for t in range(tables[p])], n
    plain, plain_n = take(9)
    two, two_n = take(13)
    del two
    order_cd = _order(["H%02d" % g for g in range(8)], QUICK_SALT)
    return {"plain": [p for p, _t in plain], "plain drawn": plain_n,
            "the default size": (sorted({p for p, _t in take(13)[0]}), two_n),
            "labels change nothing": True, "the size": 352, "candidates carry no label": ["group", "id", "table", "texts"],
            "contradoc": _order(set(order_cd[2:]), CLAIM_SALT)[:5],
            "too small a pool": "refused: the kept papers give a quick subset of 2 tables and 6 claims and a claim set of 13 and 39; {'tables'",
            "too few groups": "refused: 8 groups kept; the quick subset needs 2 and the claim set 7"}


def _label_reading_draw():
    """A draw that drops the candidates labelled not enough info, as a label-reading draw would."""
    real = gate_set.draw_scitab

    def draw(candidates, *args, **kwargs):
        return real([c for c in candidates if c.get("label") != "not enough info"], *args, **kwargs)
    return patched(gate_set, "draw_scitab", draw)


def _ignore_group_mates():
    """A group excluded only when every member is, so a clean group-mate keeps it."""
    real = leakage.check

    def check(data, candidates, embed=None, exclude_groups=(), provenance=None):
        out = real(data, candidates, embed, exclude_groups, provenance)
        members = {}
        for c in candidates:
            members.setdefault(c["group"], []).append(c["id"])
        out["excluded_group_keys"] = sorted(g for g, m in members.items() if all(i in out["excluded_ids"] for i in m))
        out["kept_group_keys"] = sorted(set(members) - set(out["excluded_group_keys"]))
        return out
    return patched(leakage, "check", check)


def observe_exclude():
    """Rule 4's list from ids only: every development document and group key of each assignment file,
    every fresh id, every SciTab development paper and table, and no claim text."""
    from common import ids as common_ids
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rows = {"101": "101", "102": "101", "205": "205"}
        assignment = {"benchmark": "contradoc", "assignments": {d: {"group": g, "side": common_ids.split_side(g)} for d, g in rows.items()}}
        (tmp / "split.json").write_text(json.dumps(assignment), encoding="utf-8")
        (tmp / "fresh.json").write_text(json.dumps({"documents": ["9001"]}), encoding="utf-8")
        claims = [{"id": "c1", "paper_id": "p1", "table_id": "t1", "claim": "A claim the list never holds.", "label": "supports"}]
        (tmp / "scitab.json").write_text(json.dumps(claims), encoding="utf-8")
        pin = hashlib.sha256((tmp / "fresh.json").read_bytes()).hexdigest()
        with patched(leakage, "FRESH_IDS_SHA256", pin):
            value = gate_set.exclude_ids([str(tmp / "split.json")], str(tmp / "fresh.json"), str(tmp / "scitab.json"))
        other = caught(lambda: gate_set.exclude_ids([str(tmp / "split.json")], str(tmp / "fresh.json"), str(tmp / "scitab.json")))
        return {"keys": value["group_keys"], "counts": value["counts"], "no text": "claim" not in json.dumps(value["group_keys"]),
                "provenance": value["fresh_ids_provenance"]["sha256"] == pin, "an unpinned ids file anywhere": other}


def expected_exclude():
    return {"keys": ["101", "102", "205", "9001", "p1", "t1"],
            "counts": {"split.json": 3, "fresh": 1, "scitab_papers": 1, "scitab_tables": 1}, "no text": True,
            "provenance": True, "an unpinned ids file anywhere": "refused: the fresh ids file is not the pinned one (ec2498fd...)"}


def _claim_from_every_group():
    """The claim set drawn from every kept group, the quick subset's included."""
    real = gate_set.draw_contradoc

    def draw(candidates, leak, n_quick=gate_set.CONTRADOC_QUICK_GROUPS, n_claim=gate_set.CONTRADOC_CLAIM_GROUPS, input_sha256=None,
             required_parts=gate_set.REQUIRED_PARTS, expected=None):
        out = real(candidates, leak, n_quick, n_claim, input_sha256, required_parts, expected)
        groups = sorted({c["group"] for c in candidates if c["group"] in set(leak["kept_group_keys"])})
        out["claim"] = [{"group": g, "document": "x"} for g in gate_set.order(groups, gate_set.SALT_CLAIM)]
        return out
    return patched(gate_set, "draw_contradoc", draw)


# ---- 3b: what the fingerprints read, skip and refuse; one text form; short texts; step 2 --------

def observe_reading():
    """Text files and zip members are read; a binary file is skipped and listed; a key file is listed
    unread; an unknown archive and the fresh set's folder are refused; a short string is held by its
    exact hash, so a short candidate equal to it is excluded; both sides embed one text form; the
    result carries what it ran on."""
    import zipfile
    seen = []

    def embed(texts):
        seen.extend(texts)
        return [[1.0, 0.0] for _t in texts]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        part = tmp / "part"
        (part / "keys").mkdir(parents=True)
        (part / "notes.md").write_text("A Paragraph Of Notes That Holds Well Over Eight Words In All\n\nshort", encoding="utf-8")
        (part / "rows.csv").write_text("one line of a table that has nine words in it", encoding="utf-8")
        (part / "weights.bin").write_bytes(b"\x00\x01")
        (part / "assets.tar").write_bytes(b"not opened")
        (part / "keys" / "answer_key.json").write_text("{}", encoding="utf-8")
        with zipfile.ZipFile(part / "bundle.zip", "w") as z:
            z.writestr("inner/data.json", json.dumps({"x": "Four words only here", "y": "A zipped record with more than eight words inside it"}))
        try:
            data = leakage.fingerprint([("p", str(part))], embed)
        except ValueError as exc:
            return {"fingerprint refused": str(exc).split(":")[0]}
        counted = leakage.count([("p", str(part))])["p"]
        (tmp / "bad").mkdir()
        (tmp / "bad" / "old.tar.bz2").write_bytes(b"x")
        bad = caught(lambda: leakage.fingerprint([("q", str(tmp / "bad"))]))
        fresh = tmp / "external" / "s05" / "D-S56"
        fresh.mkdir(parents=True)
        (fresh / "items.json").write_text(json.dumps(["a fresh text of more than eight words never to be read"]), encoding="utf-8")
        never = caught(lambda: leakage.fingerprint([("r", str(fresh))]))
        cands = [{"id": "s", "group": "g1", "texts": ["four WORDS only here"]},
                 {"id": "c", "group": "g2", "texts": ["A Paragraph   Of Notes That Holds Well Over Eight Words In All"]}]
        seen.clear()
        result = leakage.check(data, cands, embed, ["none"], {"exclude_ids_sha256": "e", "input_sha256": "i"})
    reasons = {r["reason"] for r in data["skipped"]["p"]}
    return {"records": data["records"]["p"], "short": data["short_records"]["p"], "counted": (counted["records"], counted["short_records"]),
            "skipped": sorted(Path(r["file"]).name for r in data["skipped"]["p"]), "reasons": sorted(reasons),
            "unknown archive": bad.split(":")[0], "fresh folder": never.split(":")[0] if isinstance(never, str) else "read",
            "short candidate": result["excluded_ids"].get("s"), "one form": "A Paragraph Of Notes That Holds Well Over Eight Words In All" in seen,
            "short texts": result["short_texts"], "provenance": result["provenance"], "parts": result["fingerprint_parts"]}


def expected_reading():
    return {"records": 3, "short": 1, "counted": (3, 1), "skipped": ["answer_key.json", "assets.tar", "weights.bin"],
            "reasons": ["key file, not read", "model assets, not read", "not a format the check reads"], "unknown archive": "refused",
            "fresh folder": "refused", "short candidate": ["cosine", "exact"], "one form": True, "short texts": 1,
            "provenance": {"exclude_ids_sha256": "e", "input_sha256": "i"}, "parts": ["p"]}


def observe_step2():
    """Step 2's rule: the lowest of .92 and the two 5th percentiles, rounded down to .01, never raised."""
    vectors = {"a1": [1.0, 0.0], "a2": [0.95, (1 - 0.95 ** 2) ** 0.5], "b1": [0.0, 1.0], "b2": [0.1, (1 - 0.01) ** 0.5],
               "pa1": [0.89, (1 - 0.89 ** 2) ** 0.5], "pb1": [0.2, (1 - 0.04) ** 0.5]}

    def embed(texts):
        return [vectors[t.split()[0]] for t in texts]
    docs = {"a1": "a1 text", "a2": "a2 text", "b1": "b1 text", "b2": "b2 text"}
    groups = {"a1": "A", "a2": "A", "b1": "B", "b2": "B"}
    low = leakage.cosine_step(docs, groups, [("a1", "pa1 prompt"), ("b1", "pb1 prompt")], embed)
    high = leakage.cosine_step(docs, groups, [], lambda texts: [[1.0, 0.0] for _t in texts])
    return {"lowered": (low["threshold_by_rule"], low["lowered"]), "never raised": high["threshold_by_rule"], "pairs": low["document_prompt_pairs"]}


def expected_step2():
    return {"lowered": (0.89, True), "never raised": 0.92, "pairs": 2}


# ---- 6: the gate's figures (gate_score.py) ------------------------------------------------------

def _gate_rows(n, right, benchmark="contradoc", per_cluster=1, flip_from=0):
    """n items; the first `right` labelled as their gold, the rest the other class."""
    pos, neg = (contradoc.SPEC.labels[FLAG], contradoc.SPEC.labels[CLEAR]) if benchmark == "contradoc" else (R, S)
    rows = []
    for i in range(n):
        gold = pos if i % 2 else neg
        label = gold if (i - flip_from) % n < right else (neg if gold == pos else pos)
        rows.append({"item_id": "i%03d" % i, "cluster": "c%03d" % (i // per_cluster), "label": label, "gold": gold})
    return rows


DECISIONS_TEXT = """## D-8. A change\n\n- **Quick-subset evidence.** the quick subset's read of a day, its row.\n\n## D-9. Another\n\n- The claim set's figures.\n"""


def observe_gate_score():
    same = gate_score.compute("contradoc", {"system": _gate_rows(40, 30), "b1": _gate_rows(40, 30)}, draws=300)
    strong = gate_score.compute("contradoc", {"system": _gate_rows(60, 54), "b1": _gate_rows(60, 36)}, draws=300)
    weak = gate_score.compute("contradoc", {"system": _gate_rows(10, 6), "b1": _gate_rows(10, 5)}, draws=300)
    cloud5 = gate_score.compute("contradoc", {"system": _gate_rows(100, 70), "b1": _gate_rows(100, 50),
                                              "cloud": _gate_rows(100, 75)}, draws=200)["against_cloud"]["bar_b"]
    cloud6 = gate_score.compute("contradoc", {"system": _gate_rows(100, 70), "b1": _gate_rows(100, 50),
                                              "cloud": _gate_rows(100, 76)}, draws=200)["against_cloud"]["bar_b"]
    sci = gate_score.compute("scitab", {"system": _gate_rows(24, 20, "scitab", 4), "b1": _gate_rows(24, 12, "scitab", 4)},
                             setting="2-class", draws=200)
    pairs = [(r["label"], r["gold"]) for r in _gate_rows(24, 20, "scitab", 4)]
    other = _gate_rows(40, 30)
    other[0] = dict(other[0], item_id="zzz")
    return {"same": (same["above_b1"]["value"], same["above_b1"]["interval"], same["above_b1"]["bar_a"]),
            "strong": (strong["above_b1"]["value"], strong["above_b1"]["bar_a"], strong["above_b1"]["gain_called"]),
            "weak": (weak["above_b1"]["value"], weak["above_b1"]["bar_a"], weak["above_b1"]["gain_called"]),
            "cloud 5 below": cloud5, "cloud 6 below": cloud6, "no cloud": strong["against_cloud"]["bar_b"],
            "scitab": (sci["arms"]["system"]["value"] == round(scitab.headline(pairs, setting="2-class")["macro_f1"], 6),
                       sci["clusters"], sci["cluster"], sci["measure"]),
            "scitab needs a setting": caught(lambda: gate_score.compute("scitab", {"system": _gate_rows(4, 4, "scitab"), "b1": _gate_rows(4, 4, "scitab")})),
            "same items": caught(lambda: gate_score.compute("contradoc", {"system": _gate_rows(40, 30), "b1": other})),
            "levels": [gate_score.level(None), gate_score.level(1), gate_score.level(2)],
            "read zero": caught(lambda: gate_score.level(0)),
            "draws at the fifth read": gate_score.draws_for(gate_score.level(5)), **_gate_reads()}


CLAIM, QUICK = "c" * 64, "q" * 64


def _gate_reads():
    """figures bound to the frozen set FILE: its digest one of the two pins, the arms scoring exactly its
    items; the quick subset a steering read; the claim set at the level of its k-th committed
    gate-claim-set row, k counted, never supplied; a second needs the marker decision. Freeze lines and
    steering rows are not counted, a row without the full digest refuses, an upper-case digest counts."""
    arms = {"system": _gate_rows(10, 6), "b1": _gate_rows(10, 5)}
    claim_value = {"contradoc": [{"item_id": "i%03d" % i, "document_id": "c%03d" % i} for i in range(10)]}
    quick_value = {"contradoc": [{"item_id": "q%03d" % i, "document_id": "k%03d" % i} for i in range(10)]}
    with tempfile.TemporaryDirectory() as tmp:
        claim_file, quick_file = Path(tmp) / "claim_set_ids.json", Path(tmp) / "quick_set_ids.json"
        claim_file.write_text(json.dumps(claim_value), encoding="utf-8")
        quick_file.write_text(json.dumps(quick_value), encoding="utf-8")
        claim = hashlib.sha256(claim_file.read_bytes()).hexdigest()
        quick = hashlib.sha256(quick_file.read_bytes()).hexdigest()
        head = "| Part | k | Alpha | Attempt | Held-out material (file, digest) | Tuning | Written | Result |\n|---|---|---|---|---|---|---|---|\n"

        def row(part, k, digest):
            return "| %s | %s | 0.025 | 1 | claim_set_ids.json %s | x | 2026-11-10 | |\n" % (part, k, digest)

        def run(openings, set_file=claim_file, decision=None):
            files = {gate_score.OPENINGS: openings, gate_score.DECISIONS: DECISIONS_TEXT}
            with patched(gate_score, "CLAIM_SET_SHA256", claim), patched(gate_score, "QUICK_SET_SHA256", quick), \
                    patched(gate_score, "_loop_text", lambda path: files[path]), patched(gate_score, "BOOTSTRAP_DRAWS", 50):
                try:
                    got = gate_score.figures("contradoc", arms, set_file, decision=decision)
                except ValueError as exc:
                    return "refused: " + str(exc).split(":")[0]
            return got["read"], got["level"]
        noise = "Frozen: the gate set, claim set %s, written into section 10.\n" % claim + row("gate-quick-subset", 1, claim)
        one = head + noise + row("gate-claim-set", 1, claim)
        two = one + row("gate-claim-set", 2, claim)
        other = Path(tmp) / "other.json"
        other.write_text(json.dumps(dict(claim_value, extra=1)), encoding="utf-8")
        return {"quick file, claim rows": run("", quick_file), "claim, no opening": run(""), "claim, only noise": run(head + noise),
                "claim, a prefix-only row": run(head + row("gate-claim-set", 1, claim[:12])),
                "claim, upper case": run(head + row("gate-claim-set", 1, claim.upper())),
                "claim, first": run(one), "claim, second, no decision": run(two, decision="D-9"),
                "claim, second, a decision": run(two, decision="D-8"),
                "claim, rows out of order": run(head + row("gate-claim-set", 2, claim)),
                "another file": run(one, other), "no file": run(one, None)}


def expected_gate_score():
    return {"same": (0.0, [0.0, 0.0], False), "strong": (0.3, True, True), "weak": (0.1, False, False),
            "cloud 5 below": True, "cloud 6 below": False, "no cloud": None,
            "scitab": (True, 6, "table", "2-class macro-F1 (declared, D-380)"),
            "scitab needs a setting": "refused: SciTab's class setting is declared per item set (D-380)",
            "same items": "refused: arm system does not score the same items as arm b1",
            "levels": [0.95, 0.975, 0.9875], "read zero": "refused: a claim read is numbered from 1 (its opening in HELDOUT_OPENINGS.md)",
            "draws at the fifth read": 25600,
            "quick file, claim rows": "refused: arm system does not score exactly the items of the set file it names",
            "claim, a prefix-only row": "refused: a gate-claim-set row gives no full digest",
            "claim, upper case": ("claim read 1", 0.975),
            "claim, no opening": "refused: no opening for this claim read is committed in docs/loop/HELDOUT_OPENINGS.md",
            "claim, only noise": "refused: no opening for this claim read is committed in docs/loop/HELDOUT_OPENINGS.md",
            "claim, rows out of order": "refused: the claim set's opening rows are not numbered in order",
            "claim, first": ("claim read 1", 0.975),
            "claim, second, no decision": "refused: a claim read after the first needs a committed decision naming its quick-subset evidence (D-422)",
            "claim, second, a decision": ("claim read 2", 0.9875),
            "another file": "refused: not the frozen gate set's claim set or quick subset", "no file": "refused: not the frozen gate set's claim set or quick subset"}


def _with_source(module, name, old, new):
    import inspect
    import textwrap
    src = textwrap.dedent(inspect.getsource(getattr(module, name)))
    assert src.count(old) == 1, (name, old)
    namespace = dict(vars(module))
    exec(compile(src.replace(old, new), module.__file__, "exec"), namespace)
    import types
    made = namespace[name]
    # the neutralised function reads the module's live globals, so a patch made later is seen
    live = types.FunctionType(made.__code__, vars(module), made.__name__, made.__defaults__, made.__closure__)
    live.__kwdefaults__ = made.__kwdefaults__
    return patched(module, name, live)


def _unpaired():
    return _with_source(gate_score, "compute", "            samples[n].append(measure(benchmark, [p for c in pick for p in by_cluster[n][c]], setting))",
                        "            own = [clusters[rng.randrange(len(clusters))] for _c in clusters]\n"
                        "            samples[n].append(measure(benchmark, [p for c in own for p in by_cluster[n][c]], setting))")


def observe_guard():
    """Every command of both tools refuses a path under the fresh set's folder, and an archive member
    named under it; the check refuses step 2's record when its threshold is not COSINE."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fresh = tmp / "external" / "s05" / "D-S56"
        fresh.mkdir(parents=True)
        f = str(fresh / "x.json")
        Path(f).write_text("[]", encoding="utf-8")
        ok = str(tmp / "ok.json")
        Path(ok).write_text("[]", encoding="utf-8")
        member = json.dumps(["a text of more than eight words held in the archive here"]).encode("utf-8")
        with tarfile.open(tmp / "a.tar.gz", "w:gz") as tar:
            info = tarfile.TarInfo("external/s05/D-S56/inner.json")
            info.size = len(member)
            tar.addfile(info, io.BytesIO(member))
        quiet = contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO())
        with quiet[0], quiet[1]:
            def code(fn):
                try:
                    return fn()
                except Exception:
                    return "error past the guard"
            codes = {
                "fingerprint": code(lambda: leakage.main(["fingerprint", "--part", "p=" + f, "--out", str(tmp / "o.gz")])),
                "check": code(lambda: leakage.main(["check", "--fingerprints", ok, "--candidates", ok, "--exclude-groups", f,
                                       "--cosine-step", ok, "--out", str(tmp / "o.json")])),
                "cosine-step": code(lambda: leakage.main(["cosine-step", "--dev", f, "--assignment", ok, "--prompts", ok, "--items", ok,
                                             "--out", str(tmp / "o.json")])),
                "exclude-ids": code(lambda: gate_set.main(["exclude-ids", "--contradoc-assignment", ok, "--fresh-ids", f,
                                              "--scitab-development", ok, "--out", str(tmp / "o.json")])),
                "draw": code(lambda: gate_set.main(["draw-scitab", "--leakage", ok, "--input", f, "--out", str(tmp / "o.json"),
                                       "--fingerprints-sha256", "f", "--exclude-ids-sha256", "e", "--cosine-step-sha256", "s",
                                       "--demonstration-tables", ok]))}
        member_refused = caught(lambda: leakage.fingerprint([("p", str(tmp / "a.tar.gz"))])).split(":")[0]
        with tarfile.open(tmp / "b.tar.gz", "w:gz") as tar:
            info = tarfile.TarInfo("D-S56/fresh.json")
            info.size = len(member)
            tar.addfile(info, io.BytesIO(member))
        short_member = caught(lambda: leakage.fingerprint([("p", str(tmp / "b.tar.gz"))])).split(":")[0]
        data = leakage.fingerprint([("p", str(tmp / "ok.json"))]) if False else None
        del data
        ids_file = tmp / "external" / "s05" / "D-S56" / "contradoc_fresh100_ids.json"
        ids_file.write_text(json.dumps({"documents": ["9001"]}), encoding="utf-8")
        (tmp / "split.json").write_text(json.dumps({"benchmark": "contradoc", "assignments": {}}), encoding="utf-8")
        (tmp / "sci.json").write_text(json.dumps([{"id": "c", "paper_id": "p", "table_id": "t", "claim": "x", "label": "supports"}]),
                                      encoding="utf-8")
        with patched(leakage, "FRESH_IDS_SHA256", hashlib.sha256(ids_file.read_bytes()).hexdigest()), quiet[0], quiet[1]:
            admitted = gate_set.main(["exclude-ids", "--contradoc-assignment", str(tmp / "split.json"), "--fresh-ids", str(ids_file),
                                      "--scitab-development", str(tmp / "sci.json"), "--out", str(tmp / "ex.json")])
            fingerprinted = code(lambda: leakage.main(["fingerprint", "--part", "p=" + str(ids_file), "--out", str(tmp / "o2.gz")]))
        provenance = json.loads((tmp / "ex.json").read_text(encoding="utf-8")).get("fresh_ids_provenance", {}).get("path") if admitted == 0 else None
        ids_file.write_text(json.dumps({"documents": ["9002"]}), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            changed = gate_set.main(["exclude-ids", "--contradoc-assignment", str(tmp / "split.json"), "--fresh-ids", str(ids_file),
                                     "--scitab-development", str(tmp / "sci.json"), "--out", str(tmp / "ex2.json")])
        (tmp / "step_high.json").write_text(json.dumps({"threshold_by_rule": 0.95}), encoding="utf-8")
        (tmp / "step_low.json").write_text(json.dumps({"threshold_by_rule": 0.5}), encoding="utf-8")
        fp = tmp / "fp.json.gz"
        (tmp / "rows.json").write_text(json.dumps(["a record of more than eight words for the fingerprint file"]), encoding="utf-8")
        leakage.write(leakage.fingerprint([("p", str(tmp / "rows.json"))]), fp)
        (tmp / "none.json").write_text(json.dumps({"group_keys": []}), encoding="utf-8")
        cands = tmp / "cands.json"
        cands.write_text(json.dumps([{"id": "a", "group": "g", "texts": ["nothing"]}]), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            high = leakage.main(["check", "--fingerprints", str(fp), "--candidates", str(cands), "--exclude-groups", str(tmp / "none.json"),
                                 "--cosine-step", str(tmp / "step_high.json"), "--out", str(tmp / "r1.json")])
            low = leakage.main(["check", "--fingerprints", str(fp), "--candidates", str(cands), "--exclude-groups", str(tmp / "none.json"),
                                "--cosine-step", str(tmp / "step_low.json"), "--out", str(tmp / "r2.json")])
        used = json.loads((tmp / "r2.json").read_text(encoding="utf-8")).get("cosine_threshold") if low == 0 else None
        return {"codes": codes, "member": member_refused, "member under D-S56 alone": short_member,
                "ids file for exclude-ids": (admitted, provenance),
                "ids file for anything else": fingerprinted, "ids file changed": changed,
                "step 2 above the ceiling": high, "step 2's threshold used": used}


def expected_guard():
    return {"codes": {"fingerprint": 2, "check": 2, "cosine-step": 2, "exclude-ids": 2, "draw": 2}, "member": "refused",
            "member under D-S56 alone": "refused",
            "ids file for exclude-ids": (0, "external/s05/D-S56/contradoc_fresh100_ids.json"), "ids file for anything else": 2,
            "ids file changed": 2, "step 2 above the ceiling": 2, "step 2's threshold used": 0.5}


def observe_cover():
    """A fingerprint over external/s05 is refused while any of its entries but D-S56 and GATE belongs to
    no part; covered whole, it runs."""
    with tempfile.TemporaryDirectory() as tmp:
        s05 = Path(tmp) / "external" / "s05"
        for name in ("A", "B", "D-S56", "GATE"):
            (s05 / name).mkdir(parents=True)
            (s05 / name / "x.json").write_text(json.dumps(["a record of more than eight words in this file here"]), encoding="utf-8")
        refused = caught(lambda: leakage.fingerprint([("p", str(s05 / "A"))])).split(":")[0]
        listed = leakage.uncovered([str(s05 / "A")])
        ran = leakage.fingerprint([("p", str(s05 / "A")), ("q", str(s05 / "B"))])["records"]
    return {"refused": refused, "listed": listed, "covered": ran, "savings in development": any(
        q == "external/s05/SAVINGS_PROOF/" for q in gate_set.PART_PATHS["development"])}


def expected_cover():
    return {"refused": "refused", "listed": ["external/s05/B"], "covered": {"p": 1, "q": 1}, "savings in development": True}


def run_checks():
    proofs = [
        ("SciTab: 2-class is not the fixed three", observe_scitab, expected_scitab, _scitab_forced_three),
        ("SciTab: 3-class is not the gold present", observe_scitab, expected_scitab, _scitab_gold_present),
        ("SciTab: the setting is required", observe_scitab, expected_scitab, lambda: patched(scitab, "CLASS_SETTINGS", {**scitab.CLASS_SETTINGS, None: scitab.CLASSES})),
        ("SciTab: the CLI requires it", observe_scitab, expected_scitab, lambda: patched(cli, "headline_of", lambda adapter, class_setting=None: adapter.headline)),
        ("judge_read: 2-class is not the fixed three", observe_judge_read, expected_judge_read, _judge_forced_three),
        ("judge_read: 3-class is not the gold present", observe_judge_read, expected_judge_read, _judge_gold_present),
        ("judge_read: G1's declaration", observe_judge_read, expected_judge_read, lambda: patched(judge_read, "G1_SETTINGS", {"scitab": "3-class", "contradoc": "2-class"})),
        ("ContraDoc: EHR over true positives", observe_contradoc, expected_contradoc, _ehr_over_every_positive),
        ("ContraDoc: B3 labelled unit-level", observe_contradoc, expected_contradoc, lambda: patched(contradoc, "UNIT_LEVEL", "quoted evidence")),
        ("leakage: one shared run", observe_leakage, expected_leakage, lambda: patched(leakage, "RUNS_MIN", 2)),
        ("leakage: digit runs", observe_leakage, expected_leakage, lambda: patched(leakage, "runs", lambda text: leakage.overlap.shingle_hashes(text))),
        ("leakage: the cosine threshold", observe_leakage, expected_leakage, lambda: _with_source(
            leakage, "check", "        if dot is not None and dot >= cosine:", "        if dot is not None and dot >= cosine + 0.03:")),
        ("leakage: exact after normalising", observe_leakage, expected_leakage, lambda: patched(leakage, "normalise", lambda text: str(text))),
        ("leakage: a whole group", observe_leakage, expected_leakage, _ignore_group_mates),
        ("leakage: records of eight words", observe_leakage, expected_leakage, lambda: patched(leakage, "MIN_WORDS", 3)),
        ("leakage: a mix's rows only", observe_mix_and_any_set, expected_mix_and_any_set,
         lambda: patched(leakage, "_under", lambda value, keys: iter([value]))),
        ("leakage: any set's candidates", observe_mix_and_any_set, expected_mix_and_any_set,
         lambda: patched(leakage, "read_candidates", lambda path: [])),
        ("draw: the salted order", observe_draw, expected_draw, lambda: patched(gate_set, "SALT_CLAIM", "another:")),
        ("draw: disjoint sets", observe_draw, expected_draw, _claim_from_every_group),
        ("sizes: the draw stops at the first paper that reaches it", observe_sizes, expected_sizes, lambda: _with_source(
            gate_set, "draw_scitab", "        if size(claim)[1] >= n_claims:", "        if size(claim)[1] >= n_claims + 3:")),
        ("sizes: 352 whatever the setting", observe_sizes, expected_sizes, lambda: patched(gate_set, "SCITAB_CLAIM_CLAIMS", 250)),
        ("sizes: the draw never reads a label", observe_sizes, expected_sizes, _label_reading_draw),
        ("sizes: a pool below the size refused", observe_sizes, expected_sizes, lambda: _with_source(
            gate_set, "draw_contradoc", "    if len(quick) < n_quick or len(claim) < n_claim:", "    if False:")),
        ("draw: v3's SciTab share held back", observe_draw, expected_draw, lambda: _with_source(
            gate_set, "draw_scitab", "    papers = {p: v for p, v in papers.items() if p not in set(held)}\n", "")),
        ("draw: v3's share by its own salt", observe_draw, expected_draw, lambda: patched(gate_set, "SALT_V3_SEALED", "another:")),
        ("draw: rule 4 ran", observe_draw, expected_draw, lambda: _with_source(
            gate_set, "_kept", '    if not provenance.get("exclude_ids_sha256"):', "    if False:")),
        ("draw: on this input", observe_draw, expected_draw, lambda: _with_source(
            gate_set, "_kept", '    if input_sha256 is not None and provenance.get("input_sha256") != input_sha256:', "    if False:")),
        ("draw: every part fingerprinted", observe_draw, expected_draw, lambda: _with_source(
            gate_set, "_kept", "    if missing:", "    if False:")),
        ("reading: skipped files listed", observe_reading, expected_reading, lambda: _with_source(
            leakage, "_entries", '        skipped.append({"file": label, "sha256": hashlib.sha256(raw).hexdigest(), "reason": "not a format the check reads"})', "        pass")),
        ("reading: model assets never opened", observe_reading, expected_reading, lambda: patched(leakage, "ASSET_NAMES", ())),
        ("reading: an unknown archive refused", observe_reading, expected_reading, lambda: patched(leakage, "REFUSED_ARCHIVES", ())),
        ("reading: the fresh folder refused", observe_reading, expected_reading, lambda: _patches((leakage, "NEVER", ()), (leakage, "NEVER_COMPONENTS", set()))),
        ("every external/s05 folder in a part", observe_cover, expected_cover, lambda: patched(leakage, "uncovered", lambda paths: [])),
        ("the guard on every command", observe_guard, expected_guard, lambda: patched(leakage, "guard_args", lambda args: None)),
        ("the guard on archive members", observe_guard, expected_guard, lambda: _with_source(
            leakage, "_entries", "    guard(label)\n", "")),
        ("step 2's threshold read from its record", observe_guard, expected_guard, lambda: _with_source(
            leakage, "main", "                       cosine=threshold)", "                       cosine=COSINE)")),
        ("step 2 never above the ceiling", observe_guard, expected_guard, lambda: _with_source(
            leakage, "check", "    if not (isinstance(cosine, (int, float)) and 0 < cosine <= COSINE):", "    if False:")),
        ("the ids file admitted by its digest only", observe_guard, expected_guard, lambda: _all(
            _with_source(leakage, "guard", "            and hashlib.sha256(Path(str(path)).read_bytes()).hexdigest() == FRESH_IDS_SHA256:", ":"),
            _with_source(gate_set, "exclude_ids", "    if _digest(fresh_ids) != leakage.FRESH_IDS_SHA256:", "    if False:"))),
        ("draw: parts by path prefix, not substring", observe_draw, expected_draw, lambda: patched(
            gate_set, "under", lambda label, prefix: prefix in label)),
        ("rule 4's list: the fresh ids pinned anywhere", observe_exclude, expected_exclude, lambda: _with_source(
            gate_set, "exclude_ids", "    if _digest(fresh_ids) != leakage.FRESH_IDS_SHA256:", "    if False:")),
        ("draw: parts by their paths", observe_draw, expected_draw, lambda: _with_source(
            gate_set, "_kept", "            raise ValueError(\"part %s was fingerprinted from other paths than section 9 names\" % part)", "            pass")),
        ("v3: demonstration tables not counted", observe_v3, expected_v3, lambda: _with_source(
            gate_set, "hold_back_v3", "        if c[\"table\"] not in demonstration:\n    ", "        if True:\n    ")),
        ("v3: the flagged papers listed", observe_v3, expected_v3, lambda: _with_source(
            gate_set, "draw_scitab", '"v3_papers_the_check_flagged": sorted(set(held) - kept),', '"v3_papers_the_check_flagged": [],')),
        ("reading: short records by exact hash", observe_reading, expected_reading, lambda: patched(leakage, "SHORT_MIN_WORDS", leakage.MIN_WORDS)),
        ("reading: one text form", observe_reading, expected_reading, lambda: patched(leakage, "embed_form", leakage.normalise)),
        ("step 2: the rule", observe_step2, expected_step2, lambda: _with_source(
            leakage, "cosine_step", "    low = min([COSINE] + [v for v in (p_within, p_prompt) if v is not None])", "    low = COSINE")),
        ("step 2: never raised", observe_step2, expected_step2, lambda: _with_source(
            leakage, "cosine_step", "    low = min([COSINE] + [v for v in (p_within, p_prompt) if v is not None])",
            "    low = max([v for v in (p_within, p_prompt) if v is not None] or [COSINE])")),
        ("the gate: one claim read without a decision", observe_gate_score, expected_gate_score, lambda: patched(
            gate_score, "decision_names_quick_evidence", lambda decision: True)),
        ("the gate: only claim-set rows with the full digest", observe_gate_score, expected_gate_score, lambda: _with_source(
            gate_score, "claim_read_number", "        if len(cells) < 2 or cells[0] != CLAIM_PART:", "        if len(cells) < 2:")),
        ("the guard on a D-S56 component alone", observe_guard, expected_guard, lambda: patched(leakage, "NEVER_COMPONENTS", set())),
        ("the freeze: no shared group", observe_freeze, expected_freeze, lambda: _with_source(
            gate_set, "freeze", '        raise ValueError("the claim set and the quick subset share a document group")', "        pass")),
        ("the freeze: the claim set's count", observe_freeze, expected_freeze, lambda: _with_source(
            gate_set, "freeze", "    if declared == \"2-class\" and len(nei & claim_ids) != setting.get(\"not_enough_info_left_out\", 0):",
            "    if declared == \"2-class\" and len(nei) != setting.get(\"not_enough_info_left_out\", 0):")),
        ("the freeze: no shared paper", observe_freeze, expected_freeze, lambda: _with_source(
            gate_set, "freeze", '        raise ValueError("the claim set and the quick subset share a paper")', "        pass")),
        ("the freeze: not-enough-info claims leave under 2-class", observe_freeze, expected_freeze, lambda: _with_source(
            gate_set, "freeze", "            claims = [c for c in r[\"claims\"] if common_ids.key_string(c) not in nei]",
            "            claims = list(r[\"claims\"])")),
        ("the gate: arms scored against the set file", observe_gate_score, expected_gate_score, lambda: _with_source(
            gate_score, "figures", "        if scored != listed:", "        if False:")),
        ("the gate: a row without the full digest refuses", observe_gate_score, expected_gate_score, lambda: _with_source(
            gate_score, "claim_read_number", "        if not tokens:", "        if False:")),
        ("the gate: case folded before matching", observe_gate_score, expected_gate_score, lambda: _with_source(
            gate_score, "claim_read_number", '" ".join(cells[2:]).lower())', '" ".join(cells[2:]))')),
        ("the gate: k counted from the openings", observe_gate_score, expected_gate_score, lambda: patched(
            gate_score, "claim_read_number", lambda set_sha256: 1)),
        ("the gate: only the frozen set", observe_gate_score, expected_gate_score, lambda: _with_source(
            gate_score, "figures", "    if not set_sha256 or set_sha256 not in {CLAIM_SET_SHA256, QUICK_SET_SHA256} - {None}:", "    if False:")),
        ("the gate: draws at deep levels", observe_gate_score, expected_gate_score, lambda: patched(gate_score, "TAIL_DRAWS", 1)),
        ("draw: the quick salt", observe_draw, expected_draw, lambda: patched(gate_set, "SALT_QUICK", "another:")),
        ("draw: the cosine rule required", observe_draw, expected_draw, lambda: patched(gate_set, "_kept", lambda leak, input_sha256=None, required_parts=None, expected=None: set(leak["kept_group_keys"]))),
        ("the gate: a paired bootstrap", observe_gate_score, expected_gate_score, _unpaired),
        ("the gate: bar (a) needs the interval", observe_gate_score, expected_gate_score, lambda: _with_source(
            gate_score, "compute", '"bar_a": round(a_point, 9) >= BAR_ABOVE_B1 and a_int[0] > 0,', '"bar_a": round(a_point, 9) >= BAR_ABOVE_B1,')),
        ("the gate: bar (a)'s 10 points", observe_gate_score, expected_gate_score, lambda: patched(gate_score, "BAR_ABOVE_B1", 0.35)),
        ("the gate: alpha halves each claim read", observe_gate_score, expected_gate_score, lambda: patched(gate_score, "level", lambda claim_read=None: 0.95)),
        ("the gate: bar (b)'s 5 points", observe_gate_score, expected_gate_score, lambda: patched(gate_score, "BAR_BELOW_CLOUD", 0.06)),
        ("the gate: SciTab by tables", observe_gate_score, expected_gate_score, lambda: _with_source(
            gate_score, "compute", 'by_cluster[n].setdefault(r["cluster"], [])', 'by_cluster[n].setdefault(r["item_id"], [])')),
        ("rule 4's list: SciTab's papers and tables", observe_exclude, expected_exclude, lambda: _with_source(
            gate_set, "exclude_ids", "    keys |= papers | tables\n", "")),
        ("rule 4's list: the fresh ids", observe_exclude, expected_exclude, lambda: _with_source(
            gate_set, "exclude_ids", "    keys |= {ids.key_string(d) for d in fresh}\n", "")),
        ("class setting: the share", observe_setting, expected_setting, lambda: patched(gate_set, "NEI_MIN_SHARE", 0.10)),
        ("class setting: the count", observe_setting, expected_setting, lambda: patched(gate_set, "NEI_MIN_CLAIMS", 31)),
    ]
    results = []
    for name, observe, expected, neutralise in proofs:
        results.append(prove_effect(name=name, validate=lambda: gate_set.SALT_CLAIM == "20261109-D-S92:", observe=observe,
                                    check=lambda o=observe, e=expected, n=name: ("PASS" if o() == e() else "FAIL", n),
                                    neutralise=neutralise))
    return "PASS", ("%d proofs on invented pairs, rows, records and an injected embedder, no benchmark file and no key read: the "
                    "declared class setting both ways in the SciTab headline, the CLI, judge_read and choice_read; ContraDoc's R-acc(pos) and EHR over true positives; the four leakage "
                    "rules, whole groups and no text out; the seeded draw, disjoint and refused when short; the class-setting rule; the gate's paired bootstrap and both bars") % len(results)


if __name__ == "__main__":
    print(run_checks())
