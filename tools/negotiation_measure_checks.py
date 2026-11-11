#!/usr/bin/env python3
"""Proofs for the negotiation measurement tools (D-S102 item 8, plan step 2). No model, no machine,
no held-out case: every proof runs on fixtures written here, or on the worked development case.

1. Every outcome becomes a label by the plan's mapping, and a missing row is no_answer.
2. Macro-F1 averages over the key's classes, scores a class only the arm predicts as 0, and gives
   the two floors.
3. Movement precision, recall and coverage are three different figures.
4. The scorer refuses without a committed opening line, and beyond two openings.
5. A claim is shown only when both the BCa and the cluster t lower bounds lie above zero, at
   0.05 / 2^k / 5.
6. The cluster t interval uses the t quantile, not the normal one.
7. Round 3 is good only when Python kept the suggestion and the sheet passes Q, P and A; U is 0
   otherwise.
8. The B1 movement form renders the four declared quotes and a silent slot, holds every prompt to its
   rendering, and reads a reply by its exact spelling only.
9. The B1 suggestion form is the system's question over the whole last round, and its reply is read
   by the system's own checks.
10. The freeze refuses a leaked case, needs labeller 3 where the plan says, and writes a stable
    digest.
11. The power simulation is lower for a weaker system.
12. The replay pass hands a negotiation prompts file to its module.

Each proof follows scripts/effect_proof.py: neutralise, fail, restore, pass.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from effect_proof import prove_effect  # noqa: E402
import negotiation_b1 as nb  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


score = _load("score_negotiation", ROOT / "tools" / "score_negotiation.py")
freezer = _load("freeze_negotiation_set", ROOT / "tools" / "freeze_negotiation_set.py")
power_tool = _load("negotiation_power", ROOT / "tools" / "negotiation_power.py")
freezer.score = score
power_tool.score = score

T, A, U, N = "moved_toward", "moved_away", "unchanged_from_prior", "not_computable"


# ---------------------------------------------------------------------------
# a fixture case, written here (not a held-out case)

NOTES = {
    ("r1", "a"): "# Party A, round 1\n\n## Fee\n\nThe fee for {w} is 100 credits per month, paid at the start of each month for every month of the agreed service term.\n\n## Term\n\nThe term of {w} must be long, says party A.\n",
    ("r1", "b"): "# Party B, round 1\n\n## Fee\n\nThe fee for {w} is 60 credits per month.\n\n## Term\n\nA short term of {w} suits party B best.\n",
    ("r2", "a"): "# Party A, round 2\n\n## Fee\n\nThe fee for {w} is 90 credits per month.\n\n## Term\n\nThe term of {w} must still be long, says A.\n",
    ("r2", "b"): "# Party B, round 2\n\n## Fee\n\nThe fee for {w} is 70 credits per month.\n",
    ("r3", "a"): "# Party A, round 3\n\n## Fee\n\nThe fee for {w} is 85 credits per month.\n\n## Agreed\n\nBoth sides agree the venue for {w} this year.\n",
    ("r3", "b"): "# Party B, round 3\n\n## Fee\n\nThe fee for {w} is 75 credits per month.\n\n## Agreed\n\nBoth sides agree the venue for {w} this year.\n",
}
QUOTES = {"fee": "The fee is {n} credits per month.", "term": None}
# Issues no note states, so the fixture meets the plan's minimum of six issues (two of them open).
EXTRA_ISSUES = ["staffing", "reporting", "schedule"]


def write_case(folder, case_id, *, label_shift=False):
    """A two-party, three-round fixture case with keys from two labellers, in the set's layout."""
    folder = Path(folder) / case_id
    (folder / "context").mkdir(parents=True)
    sources = []
    docs = {}
    for (rnd, actor), text in NOTES.items():
        text = text.replace("{w}", case_id.split("-")[0])
        if not case_id.startswith("alpha"):
            # Each fixture case its own long passage, so the cases do not match each other.
            text = text.replace("paid at the start of each month for every month of the agreed service term",
                                "settled within ten working days after each invoice reaches the buyer's finance office")
        doc_id = "%s_%s_%s" % (case_id.replace("-", "_"), rnd, actor)
        (folder / "context" / (doc_id + ".md")).write_text(text, encoding="utf-8", newline="\n")
        docs[(rnd, actor)] = (doc_id, text)
        for issue, line in (("fee", [l for l in text.splitlines() if l.startswith("The fee")]),
                            ("term", [l for l in text.splitlines() if "term" in l.lower() and not l.startswith("#")])):
            if line:
                start = text.index(line[0])
                sources.append({"source_id": "%s-%s-%s" % (rnd, actor, issue), "round_id": rnd, "actor_id": actor,
                                "issue_id": issue, "document_id": doc_id, "unit_id": "u01", "char_start": start,
                                "char_end": start + len(line[0]), "quote": line[0], "state": "accepted"})
    manifest = {"schema_version": 1, "case_id": case_id, "fixture": False,
                "rounds": [{"round_id": r, "sequence": n, "document_ids": [docs[(r, "a")][0], docs[(r, "b")][0]]}
                           for n, r in enumerate(("r1", "r2", "r3"), start=1)],
                "actors": [{"actor_id": "a"}, {"actor_id": "b", "supported": True}],
                "issues": [{"issue_id": "fee", "unit": "credits per month", "open": True}, {"issue_id": "term"},
                           {"issue_id": "venue", "open": True}] + [{"issue_id": i} for i in EXTRA_ISSUES],
                "sources": sources}
    (folder / "case_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8", newline="\n")
    (folder / "declarations.json").write_text(json.dumps({"fee": {"text_headings": ["Fee"], "closed_headings": ["Agreed"],
                                                                   "position": "A fee of 70 credits per month.",
                                                                   "fallback": "A fee of 80 credits per month."},
                                                           "venue": {"text_headings": ["Agreed"], "closed_headings": [],
                                                                     "position": "The venue stays.", "fallback": "A nearby venue."}}),
                                              encoding="utf-8", newline="\n")
    key = [{"issue_id": "fee", "rounds": ["r1", "r2"], "label": T}, {"issue_id": "fee", "rounds": ["r2", "r3"], "label": T},
           {"issue_id": "term", "rounds": ["r1", "r2"], "label": N}, {"issue_id": "term", "rounds": ["r2", "r3"], "label": N}]
    key += [{"issue_id": i, "rounds": r, "label": N} for i in ["venue"] + EXTRA_ISSUES for r in (["r1", "r2"], ["r2", "r3"])]
    (folder / "KEY_MOVEMENT.json").write_text(json.dumps({"rows": key}), encoding="utf-8", newline="\n")
    second = [dict(r) for r in key]
    if label_shift:
        second[0]["label"] = A
    (folder / "KEY_MOVEMENT_L2.json").write_text(json.dumps({"rows": second}), encoding="utf-8", newline="\n")
    return folder


# ---------------------------------------------------------------------------
# observations


def observe_mapping():
    key = [{"case_id": "c", "issue_id": i, "rounds": ["r1", "r2"], "label": N} for i in ("x", "y", "z", "w")]
    system = {("c", "x", ("r1", "r2")): score.system_label({"outcome": "not_computed", "why": "several_figures_in_r1"}),
              ("c", "y", ("r1", "r2")): score.system_label({"outcome": "moved_toward"}),
              ("c", "z", ("r1", "r2")): score.system_label({"outcome": "something_else"})}
    replies = score.reply_answers({"rows": [{"form": "movement", "case_id": "c", "issue_id": "x", "rounds": ["r1", "r2"],
                                             "label": "garbled"}]})
    return {"system": [p for _, p in score.pairs(key, system)["c"]],
            "reply": [p for _, p in score.pairs(key, replies)["c"]]}


MAPPING = {"system": [N, T, "no_answer", "no_answer"], "reply": ["no_answer"] * 4}


ROWS = [(T, T), (T, T), (T, A), (A, A), (N, N), (N, U), (N, N), (A, "no_answer")]


def observe_figures():
    r = {name: round(fn(ROWS), 6) for name, fn in score.FIGURES.items()}
    f = score.floors(ROWS)
    return dict(r, floor_all_nc=round(f["all_not_computable"], 6), floor_majority=round(f["majority"], 6),
                majority=f["majority_label"])


def _expected_figures():
    def f1(tp, fp, fn):
        return 0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn)
    # Over the key's classes only (T, A, N): N's row predicted U, and A's no_answer row, are misses (D-395 N1).
    macro = (f1(2, 0, 1) + f1(1, 1, 1) + f1(2, 0, 1)) / 3
    said = [(k, p) for k, p in ROWS if p in (T, A, U)]
    precision = sum(1 for k, p in said if k == p) / len(said)
    moved = [(k, p) for k, p in ROWS if k in (T, A, U)]
    recall = sum(1 for k, p in moved if k == p) / len(moved)
    cov = sum(1 for k, p in moved if p in (T, A, U)) / len(moved)
    nc = (f1(0, 0, 3) + f1(0, 0, 2) + f1(3, 5, 0)) / 3
    return {"macro_f1": round(macro, 6), "movement_precision": round(precision, 6), "movement_recall": round(recall, 6),
            "coverage": round(cov, 6), "floor_all_nc": round(nc, 6), "floor_majority": round(nc, 6), "majority": T}


def observe_openings():
    s, c = "a" * 64, "b" * 64
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["git", "init", "-q", td], check=True)
        ledger = Path(td) / score.OPENINGS
        ledger.parent.mkdir(parents=True)
        ledger.write_text("negotiation-heldout opening k=1 set=%s config=%s\n" % (s, c), encoding="utf-8")
        uncommitted = score.refuse_without_opening(1, s, c, text=score.committed_text(td, score.OPENINGS))
        subprocess.run(["git", "-C", td, "add", "-A"], check=True)
        subprocess.run(["git", "-C", td, "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "-m", "x"], check=True)
        text = score.committed_text(td, score.OPENINGS)
    return {"uncommitted": uncommitted is not None,
            "committed": score.refuse_without_opening(1, s, c, text=text),
            "other_set": score.refuse_without_opening(1, "c" * 64, c, text=text) is not None,
            "third": score.refuse_without_opening(3, s, c, text=text + "negotiation-heldout opening k=3 set=%s config=%s\n" % (s, c)) is not None,
            "alpha": [score.alpha_for(1), score.alpha_for(2)]}


OPENINGS_EXPECTED = {"uncommitted": True, "committed": None, "other_set": True, "third": True, "alpha": [0.025, 0.0125]}


def _parts(right_share, cases=12, rows=12, seed=1, move_share=1.0):
    """{case: Counter of (key, predicted)}: each row right at right_share, else another label; with
    move_share below 1, a right movement row is said as not_computable instead at 1 - move_share."""
    import random
    from collections import Counter
    rng = random.Random(seed)
    out = {}
    for c in range(cases):
        keys = [T, A, U, N] * (rows // 4)
        rows_ = []
        for k in keys:
            p = k if rng.random() < right_share else rng.choice([x for x in (T, A, U, N) if x != k])
            if p in (T, A, U) and rng.random() >= move_share:
                p = N
            rows_.append((k, p))
        out["c%02d" % c] = Counter(rows_)
    return out


def observe_claims():
    with patch.object(score, "RESAMPLES", 300), patch.object(score, "INDICATORS", frozenset({"C5"})):
        strong = score.test_claim("C1", score.macro_f1, _parts(0.95), _parts(0.3, seed=2), 1)
        equal = score.test_claim("C1", score.macro_f1, _parts(0.6), _parts(0.6, seed=3), 1)
        # Precise but silent: a high movement precision bought with a large loss of recall and coverage.
        silent = score.test_claim("C2", score.movement_precision, _parts(0.95, move_share=0.2), _parts(0.7, seed=4), 1,
                                  extra={"recall": score.movement_recall, "coverage": score.coverage})
        never = score.test_claim("C2", score.FIGURES["movement_precision"], {c: __import__("collections").Counter({(T, N): 3, (N, N): 3})
                                 for c in ("a", "b", "c", "d")}, _parts(0.7, cases=4, seed=5), 1)
    with patch.object(score, "RESAMPLES", 300):
        indicator = score.test_claim("C3", score.good_rate, {c: (2, 2, 4, 0) for c in "abcdefghijkl"},
                                     {c: (0, 2, 0, 0) for c in "abcdefghijkl"}, 1)
    return {"strong_shown": strong["shown"], "equal_shown": equal["shown"], "alpha": strong["alpha"],
            "silent_precision_shown": silent["shown"], "silent_recall_upper_below_zero": silent["recall_upper"] < 0,
            "undefined_shown": never["shown"], "undefined_difference": never["difference"],
            "indicator_shown": indicator["shown"], "indicator_flag": indicator["indicator"]}


CLAIMS_EXPECTED = {"strong_shown": True, "equal_shown": False, "alpha": 0.025, "silent_precision_shown": False,
                   "silent_recall_upper_below_zero": True, "undefined_shown": False, "undefined_difference": None,
                   "indicator_shown": False, "indicator_flag": True}


def observe_resampling():
    """The exact bootstrap's resamples for 3 cases, the jackknife bound by hand, the exact permutation p."""
    from collections import Counter
    exact = score.resamples_of(3)
    big = score.resamples_of(9, resamples=50)
    parts = [(1.0, 1.0), (2.0, 1.0), (3.0, 1.0), (4.0, 1.0), (5.0, 1.0)]

    def mean_stat(c):
        return None if c is None else c[0] / c[1]
    jl = score.jackknife_lower(mean_stat, parts, 0.025)
    paired = [(Counter({(T, T): 2}), Counter({(T, A): 2})) for _ in range(4)]
    p = score.permutation_p(score._paired_stat(score.movement_recall), paired)
    return {"exact_count": len(exact), "exact_mass": round(sum(w for _, w in exact), 9), "drawn_count": len(big),
            "jackknife_lower": round(jl, 4), "permutation_p": p}


# The mean of 1..5 is 3, its jackknife SE sqrt(4/5 * sum((loo - 3)^2)) = 0.7071; t(0.975, 4) = 2.7764:
# 3 - 2.7764 * 0.7071 = 1.0368. Four cases all for the system: p = 1/16 (the identity among 16 sign flips).
RESAMPLING = {"exact_count": 10, "exact_mass": 1.0, "drawn_count": 50, "jackknife_lower": 1.0368, "permutation_p": 0.0625}


def observe_round3():
    issues = [("c1", "i1"), ("c1", "i2"), ("c1", "i3"), ("c2", "i1")]
    python = {("c1", "i1"): {"kept": True}, ("c1", "i2"): {"kept": False, "refusal": "quote_not_in_this_round"},
              ("c1", "i3"): {"kept": True}, ("c2", "i1"): {"kept": True}}
    sheet = [{"case_id": "c1", "issue_id": "i1", "Q": True, "P": True, "A": True, "U": 2},
             {"case_id": "c1", "issue_id": "i2", "Q": True, "P": True, "A": True, "U": 2},
             {"case_id": "c1", "issue_id": "i3", "Q": True, "P": False, "A": True, "U": 1}]
    return score.round3_figures(score.round3_parts(issues, python, sheet))


ROUND3 = {"good_rate": 0.25, "u_all": 0.5, "u_good": 2.0, "refusal_rate": 0.25, "n": 4}


def observe_closed_rule():
    units = [("fee", "The fee is 75 credits per month."), ("agreed", "Both sides agree the \u201cvenue\u201d  for the year.")]
    python = {("c", "i1"): {"kept": True, "quote": 'agree the "venue" for the year'},
              ("c", "i2"): {"kept": True, "quote": "The fee is 75 credits"}}
    after = score.apply_closed_rule(python, {"c": (units, {"agreed"})})
    return {k[1]: (v["kept"], v.get("refusal")) for k, v in sorted(after.items())}


CLOSED_RULE = {"i1": (False, "quote_in_agreed_text"), "i2": (True, None)}


def observe_movement_form():
    with tempfile.TemporaryDirectory() as td:
        case = write_case(td, "fixture-free")
        value = nb.build([case], Path(td) / "p.json")
        prompts = nb.load_prompts(Path(td) / "p.json")
        movement = [p for p in prompts if p["form"] == "movement"]
        tampered = json.loads((Path(td) / "p.json").read_text(encoding="utf-8"))
        tampered["prompts"][0]["user"] += " "
        (Path(td) / "t.json").write_text(json.dumps(tampered), encoding="utf-8")
        try:
            nb.load_prompts(Path(td) / "t.json")
            refused = False
        except ValueError:
            refused = True
        silent = sum(1 for p in movement if value["config"]["movement"]["silent"] in p["user"])
        return {"movement": len(movement), "silent": silent, "tampered_refused": refused,
                "parsed": [nb.parse_movement(x, value["config"]) for x in ("Narrowed.", " WIDENED ", "the gap narrowed", "")]}


MOVEMENT_FORM = {"movement": 12, "silent": 10, "tampered_refused": True,
                 "parsed": [T, A, "no_answer", "no_answer"]}


def observe_suggestion_form():
    import case_questions as cq
    with tempfile.TemporaryDirectory() as td:
        case = write_case(td, "fixture-free")
        manifest, documents, declarations = freezer.read_case(case)
        manifest = freezer.fill_declarations(manifest, documents, declarations)
        (case / "case_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        value = nb.build([case], Path(td) / "p.json")
    s = [p for p in value["prompts"] if p["form"] == "suggestion"][0]
    chosen = s["chosen"]
    sconfig = {"suggestion": value["suggestion"]}
    fee = next(p for p in chosen["passages"] if p["kind"] == "text" and "75 credits" in p["text"])
    agreed = next(p for p in chosen["passages"] if p["kind"] == "text" and "venue" in p["text"])
    good = json.dumps({"suggested_wording": "Set the fee at 75 credits per month for the whole term.", "why": "It rests on the last offer.",
                       "cites": [fee["passage_id"]], "quote": fee["text"]})
    reopen = json.dumps({"suggested_wording": "Move the venue.", "why": "Better.", "cites": [agreed["passage_id"]],
                         "quote": agreed["text"]})
    same_question = s["user"] == cq.suggestion_question(chosen, sconfig)["text"]
    return {"same_question": same_question,
            "good": nb.read_suggestion(good, chosen, sconfig)[1],
            "reopen": nb.read_suggestion(reopen, chosen, sconfig)[1],
            "every_last_round_unit": sorted({p["unit_id"].split("-", 1)[-1] for p in chosen["passages"] if p["kind"] == "text"})}


SUGGESTION_FORM = {"same_question": True, "good": None, "reopen": "reopens_agreed_text",
                   "every_last_round_unit": ["agreed", "fee"]}


LONG = "The fee for alpha is 100 credits per month, paid at the start of each month for every month of the agreed service term."


def _freeze_or_why(root, corpora, **kw):
    try:
        value = freezer.freeze(root, corpora, progress=lambda line: None, **kw)
        return value
    except ValueError as exc:
        return str(exc)


def _set(td, *, revise=False, shift_all=False):
    root = Path(td) / "set"
    write_case(root / "synthetic", "alpha-free")
    write_case(root / "synthetic", "beta", label_shift=True)
    if shift_all:
        for case in ("alpha-free", "beta"):
            path = root / "synthetic" / case / "KEY_MOVEMENT_L2.json"
            rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
            for r in rows:
                r["label"] = {N: T, T: A}.get(r["label"], r["label"])
            path.write_text(json.dumps({"rows": rows}), encoding="utf-8")
            if revise:
                for name in ("KEY_MOVEMENT_REVISED.json", "KEY_MOVEMENT_L2_REVISED.json"):
                    (root / "synthetic" / case / name).write_text((root / "synthetic" / case / "KEY_MOVEMENT.json").read_text(encoding="utf-8"),
                                                                 encoding="utf-8")
    return root


def observe_freeze():
    """The freeze on fixture sets: labeller 3, pooled kappa and its revision round, leakage through a
    planted .docx, a planted .jsonl, the same source, the minimums, and the dry run."""
    import docx
    out = {}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clean = td / "clean.md"
        clean.write_text("# Unrelated\n\nNothing like the cases.\n", encoding="utf-8")
        root = _set(td / "a")
        first = _freeze_or_why(root, [clean])
        out["needs_labeller_3"] = isinstance(first, str) and "labeller 3" in first
        (root / "synthetic" / "beta" / "KEY_MOVEMENT_L3.json").write_text(
            json.dumps({"rows": [{"issue_id": "fee", "rounds": ["r1", "r2"], "label": T}]}), encoding="utf-8")
        done = _freeze_or_why(root, [clean])
        again = _freeze_or_why(root, [clean])
        out.update(subsets=done["subsets"], rows=len(done["movement_key"]), stable=done["set_sha256"] == again["set_sha256"],
                   decided=done["kappa"]["decided_by_labeller_3"], kappa_pooled=round(done["kappa"]["kappa_before"], 4),
                   headline_shares=done["headline_class_shares"])
        low = _freeze_or_why(_set(td / "b", shift_all=True), [clean])
        out["low_kappa_needs_revision"] = isinstance(low, str) and "revision round" in low
        revised = _set(td / "c", shift_all=True, revise=True)
        after = _freeze_or_why(revised, [clean])
        out["revision_recorded"] = (isinstance(after, dict) and after["kappa"]["revised"] is True
                                    and after["kappa"]["kappa_after"] == 1.0 and after["kappa"]["kappa_before"] < 0.6)
        planted = td / "planted"
        planted.mkdir()
        d = docx.Document()
        d.add_paragraph(LONG)
        d.save(planted / "notes.docx")
        out["docx_leak_refused"] = str(_freeze_or_why(root, [planted / "notes.docx"])).startswith("leakage")
        (planted / "rows.jsonl").write_text(json.dumps({"text": LONG}) + "\n" + json.dumps({"text": "short"}) + "\n", encoding="utf-8")
        out["jsonl_leak_refused"] = str(_freeze_or_why(root, [planted / "rows.jsonl"])).startswith("leakage")
        pdfs = td / "pdfs"
        pdfs.mkdir()
        (pdfs / "scan.pdf").write_bytes(b"%PDF-1.4")
        (pdfs / "note.md").write_text("# Unrelated\n\nNothing like the cases either.\n", encoding="utf-8")
        out["skipped_refused"] = "neither read nor accepted" in str(_freeze_or_why(root, [clean, pdfs]))
        counted = _freeze_or_why(root, [clean, pdfs], accept_skipped=[".pdf"])
        out["skipped_counted"] = isinstance(counted, dict) and counted["corpus_files"][str(pdfs)]["skipped"] == {".pdf": 1}
        out["missing_corpus_refused"] = "does not exist" in str(_freeze_or_why(root, [td / "nowhere"]))
        empty = td / "empty"
        empty.mkdir()
        (empty / "only.bin").write_bytes(b"\x00")
        out["empty_corpus_refused"] = "nothing readable" in str(_freeze_or_why(root, [empty], accept_skipped=[".bin"]))
        (root / "synthetic" / "beta" / "SOURCE.md").write_text("From https://example.org/talks/round-1 only.\n", encoding="utf-8")
        cited = td / "cited.md"
        cited.write_text("Our records name https://example.org/talks/round-1 as read.\n", encoding="utf-8")
        out["same_source_refused"] = str(_freeze_or_why(root, [cited])).startswith("leakage")
        (root / "synthetic" / "beta" / "SOURCE.md").unlink()
        thin = _set(td / "d")
        manifest_path = thin / "synthetic" / "beta" / "case_manifest.json"
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        m["issues"] = [i for i in m["issues"] if i["issue_id"] not in EXTRA_ISSUES]
        manifest_path.write_text(json.dumps(m), encoding="utf-8")
        out["below_minimums_refused"] = "minimums" in str(_freeze_or_why(thin, [clean]))
        dry = _freeze_or_why(root, [clean])
        out["dry_run_file"] = (root / "FREEZE.dryrun.json").is_file() and not (root / "FREEZE.json").is_file() and dry["dry_run"] is True
    return out


FREEZE = {"needs_labeller_3": True, "subsets": {"alpha-free": "F", "beta": "S"}, "rows": 24, "stable": True, "decided": 1,
          "kappa_pooled": 0.8537, "headline_shares": {T: 4 / 24, A: 0.0, U: 0.0, N: 20 / 24},
          "low_kappa_needs_revision": True, "revision_recorded": True, "docx_leak_refused": True,
          "jsonl_leak_refused": True, "skipped_refused": True, "skipped_counted": True, "missing_corpus_refused": True,
          "empty_corpus_refused": True, "same_source_refused": True,
          "below_minimums_refused": True, "dry_run_file": True}


NEAR_COPY = LONG.replace("at the start of", "at the beginning of")


def observe_gram_index():
    """The 5-gram step (D-437 item 3): one index of the cases' gram sets gives what every pair compared
    by `jaccard` gives, and the freeze refuses a corpus holding a near copy no other test sees."""
    mine = [LONG, "the venue for alpha is the north hall for every round of the talks held this year by both sides"
                  " of the table", " ".join("word%d" % i for i in range(30))]
    theirs = [NEAR_COPY.casefold(), " ".join("word%d" % i for i in range(12, 42)), "nothing at all like any of the passages of the"
              " cases here in this list of words"]
    mine = [freezer._norm(x) for x in mine]
    theirs = [freezer._norm(x) for x in theirs]
    pairs = {("c", m) for m in mine if any(freezer.jaccard(m, q) >= freezer.JACCARD for q in theirs)}
    index = freezer.GramIndex([("c", m) for m in mine])
    out = {"index_equals_pairs": index.matches(theirs) == pairs, "pairs_found": len(pairs),
           "own_case_skipped": index.matches(mine, skip_owner="c") == set()}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        root = _set(td / "a")
        (root / "synthetic" / "beta" / "KEY_MOVEMENT_L3.json").write_text(
            json.dumps({"rows": [{"issue_id": "fee", "rounds": ["r1", "r2"], "label": T}]}), encoding="utf-8")
        near = td / "near.md"
        near.write_text("# Notes\n\n" + NEAR_COPY + "\n", encoding="utf-8")
        got = _freeze_or_why(root, [near])
        out["near_copy_refused"] = str(got).startswith("leakage")
        clean = td / "clean.md"
        clean.write_text("# Unrelated\n\nNothing like the cases.\n", encoding="utf-8")
        done = _freeze_or_why(root, [clean])
        out["jaccard_seconds_recorded"] = isinstance(done, dict) and isinstance(done.get("jaccard_seconds"), float)
    return out


GRAM_INDEX = {"index_equals_pairs": True, "pairs_found": 1, "own_case_skipped": True, "near_copy_refused": True,
              "jaccard_seconds_recorded": True}


def observe_encoding():
    """The encoding (D-437 item 2): float32 vectors, one array, the encoder handed at most ENCODE_CHUNK
    passages a call, on the freeze's own path."""
    import numpy as np
    calls = []

    def fake(texts):
        calls.append(len(texts))
        return [[float(len(t) % 7), 1.0, 0.5] for t in texts]
    arr = np.asarray(freezer.encode_chunked(fake, ["a", "bb", "ccc", "dddd", "e", "ff", "ggg"], chunk=3))
    out = {"dtype": str(arr.dtype), "shape": list(arr.shape), "calls": list(calls),
           "values_kept": arr[3].tolist() == [4.0, 1.0, 0.5]}
    calls.clear()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        root = _set(td / "a")
        (root / "synthetic" / "beta" / "KEY_MOVEMENT_L3.json").write_text(
            json.dumps({"rows": [{"issue_id": "fee", "rounds": ["r1", "r2"], "label": T}]}), encoding="utf-8")
        corpus = td / "corpus.md"
        corpus.write_text("\n\n".join(" ".join("filler%d word%d" % (k, i) for i in range(12)) for k in range(5)) + "\n",
                          encoding="utf-8")

        def unit(texts):
            calls.append(len(texts))
            # Zero vectors, float64 as handed back: no cosine hit, and the freeze must still hold float32.
            return np.zeros((len(texts), 4), dtype=np.float64)
        real_leakage = freezer.leakage
        types = []

        def spy(mine, mv, corpora, cv, **kw):
            types.extend(str(np.asarray(v).dtype) for v in cv.values())
            return real_leakage(mine, mv, corpora, cv, **kw)
        with patch.object(freezer, "ENCODE_CHUNK", 2), patch.object(freezer, "leakage", spy):
            got = _freeze_or_why(root, [corpus], encode=unit, model={"sha256": "0" * 64})
        out["freeze_ran"] = isinstance(got, dict) or str(got)
        out["largest_call"] = max(calls) if calls else None
        out["vector_types"] = sorted(set(types))
    return out


def observe_token_batches():
    """bge-m3's batches (D-437 item 2): longest first, at most BATCH_SIZE passages and TOKEN_BUDGET tokens
    a batch, a passage over the budget alone, every passage once."""
    lengths = [9000, 40, 40, 3000, 3000, 3000, 500] + [10] * 20
    batches = freezer.token_batches(lengths, budget=8192, most=16)
    flat = [i for b in batches for i in b]
    return {"every_once": sorted(flat) == list(range(len(lengths))),
            "within_budget": all(len(b) == 1 or sum(min(lengths[i], freezer.MAX_TOKENS) for i in b) <= 8192 for b in batches),
            "within_size": all(len(b) <= 16 for b in batches), "first": batches[0], "second": batches[1],
            "longest_first": flat[:4] == [0, 3, 4, 5]}


TOKEN_BATCHES = {"every_once": True, "within_budget": True, "within_size": True, "first": [0], "second": [3, 4],
                 "longest_first": True}


ENCODING = {"dtype": "float32", "shape": [7, 3], "calls": [3, 3, 1], "values_kept": True, "freeze_ran": True,
            "largest_call": 2, "vector_types": ["float32"]}


def _old_read_file(f):
    """Neutralisation: the reading before D-419 gap 1 (no .docx, a .jsonl read as one text)."""
    if f.suffix not in {".md", ".txt", ".json", ".html"} and f.suffix != ".jsonl":
        return None
    try:
        raw = f.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    return freezer.passages(raw), raw


def _assumed(system):
    return {"agreement": {"system": system, "B1": 0.30, "cloud": 0.30}, "no_answer": {"system": 0.0, "B1": 0.0, "cloud": 0.0},
            "over_not_computable": {"system": 0.0, "B1": 0.0, "cloud": 0.0},
            "good_rate": {"system": 0.9, "B1": 0.1}, "rho": 0.5}


def observe_power():
    shares = {T: .25, A: .25, U: .25, N: .25}
    with patch.object(score, "EXACT_LIMIT", 0):
        weak = power_tool.power([12] * 14, 2, shares=shares, iccs=(0.2,), sims=6, assumed=_assumed(0.30), resamples=200)
        strong = power_tool.power([12] * 14, 2, shares=shares, iccs=(0.2,), sims=6, assumed=_assumed(0.97), resamples=200)
    return {"weak_below_strong": weak["power"]["0.2"]["C1"] < strong["power"]["0.2"]["C1"],
            "strong_high": strong["power"]["0.2"]["C1"] >= 0.8, "weak_listed": "C1" in weak["below_0_8_at_any_icc"],
            "weak_indicator": weak["claim_by_plan_rule"]["C1"]}


POWER = {"weak_below_strong": True, "strong_high": True, "weak_listed": True, "weak_indicator": "indicator"}


def observe_plan_rule():
    """The power record's own reading by the plan's rule: C1 a claim only at 0.8 or more at every
    correlation, a mixed record an indicator, an indicator claim never a claim at any power."""
    mixed = {"0.2": {"C1": 0.85, "C2": 0.95}, "0.5": {"C1": 0.5, "C2": 0.95}}
    high = {"0.2": {"C1": 0.85, "C2": 0.95}, "0.5": {"C1": 0.81, "C2": 0.95}}
    return {"mixed": power_tool.claim_by_plan_rule(mixed), "high": power_tool.claim_by_plan_rule(high),
            "mixed_below": power_tool.below_at_any_icc(mixed)}


PLAN_RULE = {"mixed": {"C1": "indicator", "C2": "indicator"}, "high": {"C1": "claim", "C2": "indicator"},
             "mixed_below": ["C1"]}


def _scorer_fixture(td):
    """A frozen fixture set, its configuration, C1's power record, one system run and B1's answers:
    the command line's inputs, on fixtures only."""
    td = Path(td)
    root = td / "set"
    case = write_case(root / "synthetic", "alpha-free")
    manifest, documents, declarations = freezer.read_case(case)
    manifest = freezer.fill_declarations(manifest, documents, declarations)
    (case / "case_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    key = [dict(r, case_id="alpha-free") for r in json.loads((case / "KEY_MOVEMENT.json").read_text(encoding="utf-8"))["rows"]]
    freeze = {"set_sha256": "a" * 64, "subsets": {"alpha-free": "F"}, "movement_key": key,
              "open_issues": [["alpha-free", "fee"], ["alpha-free", "venue"]], "dry_run": False,
              "embedding": {"model": {"sha256": "b" * 64}}}
    (td / "FREEZE.json").write_text(json.dumps(freeze), encoding="utf-8")
    run = td / "run"
    (run / "audit").mkdir(parents=True)
    (run / "seal.json").write_text(json.dumps({"execution_manifest_sha256": "c" * 64}), encoding="utf-8")
    # The last row left out, so the system has one no_answer.
    gaps = [{"issue_id": r["issue_id"], "rounds": r["rounds"], "outcome": "not_computed", "why": "x"} for r in key[:-1]]
    support = [{"item": "outcome", "issue_id": "fee", "outcome": "suggested"},
               {"item": "suggestion", "issue_id": "fee", "quote": "Both sides agree the venue for alpha this year."},
               {"item": "outcome", "issue_id": "venue", "outcome": "refused", "reason": "quote_missing"}]
    (run / "audit" / "multi_round.json").write_text(json.dumps({"manifest": {"case_id": "alpha-free"}, "position_gaps": gaps,
                                                                "case_questions": {"support": support}}), encoding="utf-8")
    b1 = {"schema": "negotiation-answers-v1", "prompts_sha256": "d" * 64,
          "rows": [dict(form="movement", group="b1", case_id="alpha-free", issue_id=r["issue_id"], rounds=r["rounds"], label=r["label"])
                   for r in key] + [{"form": "suggestion", "group": "b1", "case_id": "alpha-free", "issue_id": "fee", "kept": True,
                                     "quote": "The fee for alpha is 75 credits per month."}]}
    (td / "b1.json").write_text(json.dumps(b1), encoding="utf-8")
    cloud = dict(b1, prompts_sha256="9" * 64, model_id="claude-opus-4-8",
                 rows=[dict(r, group="cloud") for r in b1["rows"]])
    (td / "cloud.json").write_text(json.dumps(cloud), encoding="utf-8")
    (td / "b1_measurement.json").write_text(json.dumps({"models": {"b1": {"digest": "f" * 64}}}), encoding="utf-8")
    power = {"set_sha256": "a" * 64, "cases": 1, "sims": 1000, "alpha": 0.025, "power": {"0.2": {"C1": 0.4}, "0.5": {"C1": 0.2}},
             "code_sha256": power_tool.code_sha256(), "assumed": power_tool.ASSUMED}
    (td / "power.json").write_text(json.dumps(power), encoding="utf-8")
    import hashlib
    power_sha = hashlib.sha256((td / "power.json").read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    configuration = {"execution_manifest_sha256": ["c" * 64], "b1_prompts_sha256": "d" * 64, "b1_model_digests": {"b1": "f" * 64},
                     "cloud_prompts_sha256": "9" * 64, "cloud_model_id": "claude-opus-4-8", "power_record_sha256": power_sha}
    (td / "configuration.json").write_text(json.dumps(configuration), encoding="utf-8")
    sheet = [{"case_id": "alpha-free", "issue_id": "fee", "Q": True, "P": True, "A": True, "U": 2}]
    for arm in ("system", "B1"):
        (td / ("sheet_%s.json" % arm)).write_text(json.dumps(sheet), encoding="utf-8")
    line = "negotiation-heldout opening k=1 set=%s config=%s\n" % ("a" * 64, hashlib.sha256((td / "configuration.json").read_bytes()).hexdigest())
    return td, line


def _committed(td, line):
    """The scorer's view of the commit in the fixture: the opening line, the fixture's power record, and
    the repository's own tools/negotiation_power.py."""
    def read(root, rel):
        if rel == score.OPENINGS:
            return line
        if rel == "tools/negotiation_power.py":
            return (ROOT / rel).read_text(encoding="utf-8")
        path = Path(td) / rel
        return path.read_text(encoding="utf-8") if path.is_file() else None
    return read


def _run_scorer(td, line, extra=(), runs=None):
    args = ["--opening", "1", "--freeze", str(td / "FREEZE.json"), "--set", str(td / "set"), "--configuration",
            str(td / "configuration.json"), "--power", str(td / "power.json"),
            "--b1-answers", str(td / "b1.json"), "--b1-measurement", str(td / "b1_measurement.json"),
            "--cloud-answers", str(td / "cloud.json"), "--sheet", "system=" + str(td / "sheet_system.json"),
            "--sheet", "B1=" + str(td / "sheet_B1.json"), "--out", str(td / "out.json")] + list(extra)
    for run in runs or [td / "run"]:
        args += ["--system-run", str(run)]
    with patch.object(score, "committed_text", _committed(td, line)), patch.object(score, "ROOT", Path(td)), \
            patch("builtins.print", lambda *a, **k: None):
        try:
            score.main(args)
        except SystemExit as exc:
            return str(exc)
    return json.loads((td / "out.json").read_text(encoding="utf-8"))


def observe_scorer_path():
    """The command line end to end on fixtures: the round-3 report behind the same refusals, the
    closed-unit rule on every arm, C1's status from its power record, a no_answer count for every arm."""
    with tempfile.TemporaryDirectory() as raw:
        td, line = _scorer_fixture(raw)
        result = _run_scorer(td, line)
        if isinstance(result, str):
            return {"refused": result}
        r3 = result["round3"]["arms"]
        return {"c1_status": result["c1_status"], "c1_shown": result["positions"]["claims"].get("C1", {}).get("shown"),
                "system_good": r3["system"]["good_rate"], "B1_good": r3["B1"]["good_rate"],
                "no_answer": {a: v.get("no_answer") for a, v in result["positions"]["arms"].items()}}


SCORER_PATH = {"c1_status": "indicator", "c1_shown": False, "system_good": 0.0, "B1_good": 0.5,
               "no_answer": {"system": 1, "B1": 0, "cloud": 0}}


def observe_scorer_refusals():
    """Each refusal on its own: a dry-run freeze, B1's answers of another prompts file, a frozen case
    with no system run, C1's power record with too few sets, an answers file of two model groups."""
    out = {}
    with tempfile.TemporaryDirectory() as raw:
        td, line = _scorer_fixture(raw)
        f = json.loads((td / "FREEZE.json").read_text(encoding="utf-8"))
        (td / "FREEZE.json").write_text(json.dumps(dict(f, dry_run=True)), encoding="utf-8")
        out["dry_run"] = "dry run" in str(_run_scorer(td, line))
        (td / "FREEZE.json").write_text(json.dumps(f), encoding="utf-8")
        b1 = json.loads((td / "b1.json").read_text(encoding="utf-8"))
        (td / "b1.json").write_text(json.dumps(dict(b1, prompts_sha256="e" * 64)), encoding="utf-8")
        out["b1_prompts"] = "prompts file" in str(_run_scorer(td, line))
        (td / "b1.json").write_text(json.dumps(b1), encoding="utf-8")
        f2 = dict(f, subsets={"alpha-free": "F", "missing-case": "S"})
        (td / "FREEZE.json").write_text(json.dumps(f2), encoding="utf-8")
        power = json.loads((td / "power.json").read_text(encoding="utf-8"))
        (td / "power.json").write_text(json.dumps(dict(power, cases=2)), encoding="utf-8")
        _rehash_power(td)
        out["missing_run"] = "no system run" in str(_run_scorer(td, _line_for(td)))
        # A run the runs' own records show failed for an infrastructure reason: its case manifest and its
        # FINAL_STATUS.json.
        failed = _failed_entry(td / "failed_run", "missing-case", INFRASTRUCTURE_STATUS)
        line2 = _line_for(td)
        out["failed_case_named"] = isinstance(_run_scorer(td, line2, runs=[td / "run", failed]), dict)
        (td / "FREEZE.json").write_text(json.dumps(f), encoding="utf-8")
        (td / "power.json").write_text(json.dumps(power), encoding="utf-8")
        _rehash_power(td)
        line = _line_for(td)
        cfg = json.loads((td / "configuration.json").read_text(encoding="utf-8"))
        (td / "configuration.json").write_text(json.dumps(dict(cfg, b1_model_digests=None)), encoding="utf-8")
        out["config_lacks_digest"] = "lacks" in str(_run_scorer(td, _line_for(td)))
        (td / "configuration.json").write_text(json.dumps(cfg), encoding="utf-8")
        out["no_measurement"] = "measurement" in str(_run_scorer(td, line, extra=[]).__repr__() if False else
                                                     _run_without(td, line, "--b1-measurement"))
        out["no_cloud_arm"] = "arm is missing" in str(_run_without(td, line, "--cloud-answers"))
        cl = json.loads((td / "cloud.json").read_text(encoding="utf-8"))
        (td / "cloud.json").write_text(json.dumps(dict(cl, model_id=None)), encoding="utf-8")
        out["cloud_without_model"] = "model id" in str(_run_scorer(td, line))
        (td / "cloud.json").write_text(json.dumps(cl), encoding="utf-8")
        (td / "power.json").write_text(json.dumps(dict(power, sims=100)), encoding="utf-8")
        out["few_sims"] = "fewer than" in str(_run_scorer(td, line))
        (td / "power.json").write_text(json.dumps(power), encoding="utf-8")
    two = {"rows": [{"form": "movement", "group": "b1", "case_id": "c", "issue_id": "i", "rounds": ["r1", "r2"], "label": T},
                    {"form": "movement", "group": "b2", "case_id": "c", "issue_id": "i", "rounds": ["r1", "r2"], "label": A}]}
    try:
        score.reply_answers(two)
        out["two_groups"] = False
    except ValueError:
        out["two_groups"] = True
    return out


# FINAL_STATUS.json records of failed entries, in the controller's shape (tools/analyze_ordinary_final_run.py),
# with the runner's terminal error in `failure_identity`'s shape (tools/ordinary_final_run.py).
_FAILED = {"status": "ORDINARY_FINAL_CLOUD_RUN_FAILED", "terminal_error": None,
           "pipeline_completion": {"state": "failed", "reached_end": False, "exit_code": 1}}
# Infrastructure: no result from the runner (a lost instance), and the host out of memory.
INFRASTRUCTURE_STATUS = dict(_FAILED, pipeline_completion=None, remote_result=None)
OOM_STATUS = dict(_FAILED, remote_result={"execution_integrity_passed": False, "reasons": ["pipeline_not_completed"]},
                  terminal_error={"error_type": "OutOfMemoryError", "error_module": "torch", "error_frame": "x.py:1:f",
                                  "error_origin": "final_models.py:10:generate"})
# The system's own: a pipeline exception, a failed backend call inside the pipeline, an incomplete run.
EXCEPTION_STATUS = dict(OOM_STATUS, terminal_error={"error_type": "KeyError", "error_module": "builtins",
                                                     "error_frame": "pipeline.py:900:main",
                                                     "error_origin": "pipeline.py:900:main"})
# A pipeline exception class that shares the memory error's name but not its module: the system's own.
# The host's own memory, the one memory error that is infrastructure.
HOST_MEMORY_STATUS = dict(OOM_STATUS, terminal_error=dict(OOM_STATUS["terminal_error"], error_type="MemoryError",
                                                          error_module="builtins"))
NAMESAKE_STATUS = dict(OOM_STATUS, terminal_error=dict(OOM_STATUS["terminal_error"], error_type="MemoryError",
                                                       error_module="pipeline_errors"))
BACKEND_STATUS = dict(_FAILED, remote_result={"execution_integrity_passed": False, "reasons": ["backend_failure"]})
OWN_REASON_STATUS = dict(_FAILED, pipeline_completion={"state": "stopped", "reached_end": True, "exit_code": 0},
                         remote_result={"execution_integrity_passed": False, "reasons": ["semantic_incomplete"]})
# FAILED although the pipeline reached its end (state completed): the assessment failed it.
FAILED_COMPLETED_STATUS = dict(_FAILED, pipeline_completion={"state": "completed", "reached_end": True, "exit_code": 0},
                               remote_result={"execution_integrity_passed": False, "reasons": ["semantic_incomplete"]})
COMPLETED_STATUS = {"status": "ORDINARY_FINAL_CLOUD_RUN_COMPLETED", "terminal_error": None,
                    "pipeline_completion": {"state": "completed", "reached_end": True, "exit_code": 0},
                    "remote_result": {"execution_integrity_passed": True, "reasons": []}}


def _failed_entry(folder, case_id, status, controller=None):
    """An entry root as the controller leaves it: collection_integrity.json and seal.json beside
    FINAL_STATUS.json and its own records."""
    folder.mkdir(parents=True)
    (folder / "collection_integrity.json").write_text("{}", encoding="utf-8")
    (folder / "case_manifest.json").write_text(json.dumps({"case_id": case_id}), encoding="utf-8")
    if status is not None:
        (folder / "FINAL_STATUS.json").write_text(json.dumps(status), encoding="utf-8")
    if controller:
        (folder / controller).write_text(json.dumps({"error_type": "RuntimeError", "message": "x"}), encoding="utf-8")
    (folder / "seal.json").write_text(json.dumps({"execution_manifest_sha256": "c" * 64}), encoding="utf-8")
    return folder


def observe_failed_entries():
    """The failed-entry path (D-437 item 1, D-451, D-456): run folders only; a failed entry of either kind
    scores no_answer on every row of its case, its rows kept in the frozen key, counted and named apart;
    infrastructure only for a cause of the runner or the machine (a lost instance, the controller's own
    failure record, the host out of memory), a pipeline exception the system's own; only infrastructure
    may call for opening 2; never a successful run, never a case recorded in a run given, never two runs."""
    import shutil
    out = {}
    with tempfile.TemporaryDirectory() as raw:
        td, _ = _scorer_fixture(raw)
        f = json.loads((td / "FREEZE.json").read_text(encoding="utf-8"))
        # beta's twelve rows in the key: a failed entry scores no_answer on each (D-451).
        key = f["movement_key"] + [dict(r, case_id="beta") for r in f["movement_key"]]
        (td / "FREEZE.json").write_text(json.dumps(dict(f, subsets={"alpha-free": "F", "beta": "S"}, movement_key=key)),
                                        encoding="utf-8")
        power = json.loads((td / "power.json").read_text(encoding="utf-8"))
        (td / "power.json").write_text(json.dumps(dict(power, cases=2)), encoding="utf-8")
        _rehash_power(td)
        line = _line_for(td)
        run = td / "run"

        def result(*runs):
            got = _run_scorer(td, line, runs=[run] + list(runs))
            if isinstance(got, dict):
                fails = got["system_failures"]
                system = got["positions"]["arms"]["system"]
                return {"kind": [k for k in ("infrastructure", "own_reasons") if fails[k]["cases"] == ["beta"]],
                        "rows_apart": {k: v["no_answer_rows"] for k, v in fails.items()},
                        "no_answer": system["no_answer"], "rows": system["n_rows"],
                        "opening_2": got["opening_2_may_be_called"]}
            return got.replace(str(td), "<td>")
        for name, status, controller in (("lost_instance", INFRASTRUCTURE_STATUS, None), ("cuda_out_of_memory", OOM_STATUS, None),
                                         ("host_out_of_memory", HOST_MEMORY_STATUS, None),
                                         ("controller_record", None, "controller_failure.json"),
                                         ("pipeline_exception", EXCEPTION_STATUS, None), ("backend_failure", BACKEND_STATUS, None),
                                         ("semantic_incomplete", OWN_REASON_STATUS, None),
                                         ("failed_but_completed", FAILED_COMPLETED_STATUS, None),
                                         ("pipeline_class_named_like_oom", NAMESAKE_STATUS, None)):
            out[name] = result(_failed_entry(td / name, "beta", status, controller))
        done = _failed_entry(td / "done", "beta", COMPLETED_STATUS)
        out["completed_status_refused"] = "COMPLETED" in result(done)
        out["status_file_refused"] = "not a run folder" in result(done / "FINAL_STATUS.json")
        out["infrastructure_status_file_refused"] = "not a run folder" in result(td / "lost_instance" / "FINAL_STATUS.json")
        # D-456 item 1: records under downloaded/ (what came back from the instance) are never read.
        planted = _failed_entry(td / "planted", "beta", OWN_REASON_STATUS)
        inner = planted / "downloaded" / "evidence" / "run"
        inner.mkdir(parents=True)
        for name, body in (("controller_failure.json", {"error_type": "RuntimeError"}), ("collection_integrity.json", {}),
                           ("seal.json", {"execution_manifest_sha256": "c" * 64}), ("FINAL_STATUS.json", INFRASTRUCTURE_STATUS)):
            (planted / "downloaded" / name).write_text(json.dumps(body), encoding="utf-8")
        out["downloaded_record_ignored"] = result(inner)
        bare = td / "bare"
        (bare / "downloaded" / "evidence" / "run").mkdir(parents=True)
        (bare / "seal.json").write_text(json.dumps({"execution_manifest_sha256": "c" * 64}), encoding="utf-8")
        (bare / "collection_integrity.json").write_text("{}", encoding="utf-8")
        (bare / "case_manifest.json").write_text(json.dumps({"case_id": "beta"}), encoding="utf-8")
        for name, body in (("controller_failure.json", {"error_type": "RuntimeError"}), ("collection_integrity.json", {}),
                           ("seal.json", {"execution_manifest_sha256": "c" * 64}), ("FINAL_STATUS.json", INFRASTRUCTURE_STATUS)):
            (bare / "downloaded" / name).write_text(json.dumps(body), encoding="utf-8")
        out["only_downloaded_refused"] = "no FINAL_STATUS.json" in result(bare / "downloaded" / "evidence" / "run")
        # D-456 item 3: the runner's reasons decide the kind; a controller record is listed beside them.
        both = _failed_entry(td / "both", "beta", OWN_REASON_STATUS, "controller_failure.json")
        got = _run_scorer(td, line, runs=[run, both])
        cause = got["system_failures"]["own_reasons"]["causes"].get("beta", "") if isinstance(got, dict) else str(got)
        out["reasons_decide"] = (isinstance(got, dict) and got["system_failures"]["own_reasons"]["cases"] == ["beta"],
                                 "semantic_incomplete" in cause, "controller record controller_failure.json beside" in cause)
        recorded = _failed_entry(td / "recorded", "alpha-free", INFRASTRUCTURE_STATUS)
        out["recorded_case_refused"] = "case record in a run given" in result(recorded)
        shutil.copytree(run, td / "run_again")
        out["two_runs_refused"] = "two system runs" in result(td / "lost_instance", td / "run_again")
    return out


def _scored(kind):
    return {"kind": [kind], "rows_apart": {"infrastructure": 12 if kind == "infrastructure" else 0,
                                           "own_reasons": 12 if kind == "own_reasons" else 0},
            "no_answer": 13, "rows": 24, "opening_2": kind == "infrastructure"}


FAILED_ENTRIES = {"lost_instance": _scored("infrastructure"), "cuda_out_of_memory": _scored("own_reasons"),
                  "host_out_of_memory": _scored("infrastructure"),
                  "controller_record": _scored("infrastructure"), "pipeline_exception": _scored("own_reasons"),
                  "backend_failure": _scored("own_reasons"), "semantic_incomplete": _scored("own_reasons"),
                  "failed_but_completed": _scored("own_reasons"), "pipeline_class_named_like_oom": _scored("own_reasons"),
                  "downloaded_record_ignored": _scored("own_reasons"), "only_downloaded_refused": True,
                  "reasons_decide": (True, True, True),
                  "completed_status_refused": True, "status_file_refused": True,
                  "infrastructure_status_file_refused": True, "recorded_case_refused": True, "two_runs_refused": True}


SCORER_REFUSALS = {"dry_run": True, "b1_prompts": True, "missing_run": True, "failed_case_named": True,
                   "config_lacks_digest": True, "no_measurement": True, "no_cloud_arm": True, "cloud_without_model": True,
                   "few_sims": True, "two_groups": True}


def _rehash_power(td):
    """The configuration's power digest after the fixture's power record changes."""
    import hashlib
    cfg = json.loads((td / "configuration.json").read_text(encoding="utf-8"))
    cfg["power_record_sha256"] = hashlib.sha256((td / "power.json").read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    (td / "configuration.json").write_text(json.dumps(cfg), encoding="utf-8")


def _line_for(td):
    import hashlib
    return "negotiation-heldout opening k=1 set=%s config=%s\n" % ("a" * 64, hashlib.sha256((td / "configuration.json").read_bytes()).hexdigest())


def _run_without(td, line, flag):
    """The scorer with one argument (and its value) left out."""
    real = score.main

    def main(argv):
        argv = list(argv)
        i = argv.index(flag)
        return real(argv[:i] + argv[i + 2:])
    with patch.object(score, "main", main):
        return _run_scorer(td, line)


def observe_c1_rule():
    """C1 a claim only at 0.8 or more at every correlation; a mixed record (0.85 and 0.5) an indicator."""
    code = (power_tool.code_sha256(), power_tool.ASSUMED)
    freeze = {"set_sha256": "a" * 64, "subsets": {"x": "F"}}
    base = {"set_sha256": "a" * 64, "cases": 1, "sims": 1000, "alpha": 0.025, "code_sha256": code[0], "assumed": code[1]}
    out = {}
    for name, power in (("both_high", {"0.2": {"C1": 0.9}, "0.5": {"C1": 0.85}}), ("mixed", {"0.2": {"C1": 0.85}, "0.5": {"C1": 0.5}}),
                        ("both_low", {"0.2": {"C1": 0.4}, "0.5": {"C1": 0.2}})):
        out[name] = score.c1_status(dict(base, power=power), freeze, committed_code=code)[0]
    out["other_code"] = score.c1_status(dict(base, power={"0.2": {"C1": 0.9}}, code_sha256="0" * 64), freeze, committed_code=code)[1] is not None
    out["other_assumptions"] = score.c1_status(dict(base, power={"0.2": {"C1": 0.9}}, assumed={}), freeze, committed_code=code)[1] is not None
    return out


C1_RULE = {"both_high": "claim", "mixed": "indicator", "both_low": "indicator", "other_code": True, "other_assumptions": True}


def observe_gpu_gate():
    """The GPU only when a reading shows it idle (D-399), refused before any model is loaded."""
    loaded = []

    def no_load():
        loaded.append(1)
        return None
    out = {"idle": freezer.gpu_idle({"memory_used_mib": 900, "utilization_percent": 5}),
           "memory_busy": freezer.gpu_idle({"memory_used_mib": 2048, "utilization_percent": 5}),
           "compute_busy": freezer.gpu_idle({"memory_used_mib": 500, "utilization_percent": 40}),
           "no_reading": freezer.gpu_idle(None)}
    import semantic_ensemble
    with patch.object(freezer, "gpu_reading", lambda: {"memory_used_mib": 4096, "utilization_percent": 80}), \
            patch.object(semantic_ensemble, "_sbert_model", no_load):
        try:
            freezer.bge_m3_encoder("cuda")
            out["busy_refused"] = False
        except RuntimeError as exc:
            out["busy_refused"] = "not idle" in str(exc)
    out["loaded_when_busy"] = bool(loaded)
    return out


class _FakeModel:
    """bge-m3's surface the encoder uses: a device, `to`, a tokenizer and `encode`, recording the device
    of every call. No model is loaded."""

    def __init__(self):
        self.device, self.calls, self.max_seq_length = "cuda:0", [], None

    def to(self, device):
        self.device = device
        return self

    def tokenizer(self, texts, **kw):
        return {"input_ids": [[0] * (len(t.split()) + 2) for t in texts]}

    def encode(self, texts, **kw):
        import numpy as np
        self.calls.append(str(self.device))
        return np.ones((len(texts), freezer.DIMENSIONS), dtype=np.float32) / freezer.DIMENSIONS ** 0.5


def _old_other_gpu_reading(own_mib=None, own_overhead_mib=None):
    """Neutralisation: the reading at e69dbe57, which took any all-numeric listing as per process even
    when this process's pid was missing from it."""
    import os
    import subprocess
    whole = freezer.gpu_reading()
    rows = [[x.strip() for x in line.split(",")[:2]] for line in subprocess.run([], capture_output=True, text=True)
            .stdout.strip().splitlines() if line.strip()]
    if all(u.replace(".", "", 1).isdigit() for _, u in rows):
        return {"method": "per_process", "utilization_percent": (whole or {}).get("utilization_percent"),
                "own_overhead_mib": None,
                "other_processes_mib": sum(float(u) for pid, u in rows if int(pid) != os.getpid())}
    return _REAL_OTHER_GPU_READING(own_mib, own_overhead_mib)


_REAL_OTHER_GPU_READING = freezer.other_gpu_reading


def observe_gpu_reading():
    """The other processes' share of the GPU (D-456 items 2, 4 and 5): per process only when the listing
    holds this process's pid, with its overhead read off the listing; a listing without it, or [N/A] as
    Windows' display driver prints, falls back to the card's use less this process's own; utilisation
    beyond this process's own over 10 percent is not idle; unreadable is not free."""
    import os
    import subprocess
    import types

    def fake_run(listing):
        return lambda *a, **k: types.SimpleNamespace(stdout=listing)
    out = {}
    with patch.object(freezer, "gpu_reading", lambda: {"memory_used_mib": 5000.0, "utilization_percent": 4}):
        with patch.object(subprocess, "run", fake_run("%d, 2900\n1, 700\n2, 500\n" % os.getpid())):
            r = freezer.other_gpu_reading(2800.0, None)
            out["with_own_pid"] = (r["method"], r["other_processes_mib"], r["own_overhead_mib"])
        with patch.object(subprocess, "run", fake_run("1, 700\n2, 500\n")):
            r = freezer.other_gpu_reading(2800.0, 300.0)
            out["without_own_pid"] = (r["method"], r["other_processes_mib"], r.get("listing"))
        with patch.object(subprocess, "run", fake_run("12056, [N/A]\n")):
            r = freezer.other_gpu_reading(2800.0, 300.0)
            out["not_available"] = (r["method"], r["other_processes_mib"], r.get("listing"))
            out["no_own_figure"] = freezer.other_gpu_reading()
    out["busy_beyond_own"] = freezer.gpu_free_of_others({"other_processes_mib": 0.0, "utilization_percent": 40})
    out["quiet"] = freezer.gpu_free_of_others({"other_processes_mib": 0.0, "utilization_percent": 4})
    out["unreadable_not_free"] = freezer.gpu_free_of_others(None)
    return out


GPU_READING = {"with_own_pid": ("per_process", 1200.0, 100.0), "without_own_pid": ("whole_less_own", 1900.0, "without this process"),
               "not_available": ("whole_less_own", 1900.0, "unreadable"), "no_own_figure": None,
               "busy_beyond_own": False, "quiet": True, "unreadable_not_free": False}


def observe_gpu_switch():
    """The GPU pass reads nvidia-smi after every chunk (D-456 item 3): another process taking the GPU
    stops the pass on it after that chunk, moves the model to the CPU and goes on there, every reading
    and the move recorded; a pass the GPU stays free for never moves."""
    import semantic_ensemble
    out = {}
    # Injected readings (memory others hold, utilisation beyond this process's) after chunks 1, 2 and 3:
    # in "taken" another process holds 3,000 MiB after chunk 2; in "busy" the card is 40 percent busy
    # beyond this process's own use after chunk 2.
    # The first reading is taken before chunk 1; "at_start" is a GPU taken while the model loaded.
    for name, others in (("taken", [(0.0, 0), (0.0, 0), (3000.0, 0), (0.0, 0)]),
                         ("busy", [(0.0, 0), (0.0, 0), (0.0, 40), (0.0, 0)]),
                         ("at_start", [(3000.0, 0)]),
                         ("free", [(0.0, 0), (0.0, 0), (0.0, 0), (0.0, 0)])):
        model, readings = _FakeModel(), iter(others)
        idle = {"memory_used_mib": 0, "utilization_percent": 0}

        def injected(*a, readings=readings):
            mem, util = next(readings, (0.0, 0))
            return {"other_processes_mib": mem, "method": "per_process", "utilization_percent": util,
                    "own_overhead_mib": 0.0}
        with patch.object(freezer, "gpu_reading", lambda: dict(idle)), \
                patch.object(freezer, "other_gpu_reading", injected), patch.object(freezer, "UTIL_SETTLE_SECONDS", 0), \
                patch.object(semantic_ensemble, "_sbert_model", lambda: model), patch.dict("os.environ"):
            encode, release, record = freezer.bge_m3_encoder("cuda")
            vectors = freezer.encode_chunked(encode, ["word %d of a passage" % i for i in range(7)], chunk=3)
            release()
        out[name] = {"devices": model.calls, "rows": int(vectors.shape[0]), "readings": len(record["gpu_readings"]),
                     "moved_after_passage": (record["moved_to_cpu"] or {}).get("after_passage"),
                     "device_at_end": record.get("device_at_end")}
    return out


GPU_SWITCH = {"taken": {"devices": ["cuda:0", "cuda:0", "cpu"], "rows": 7, "readings": 3, "moved_after_passage": 6,
                        "device_at_end": "cpu"},
              "busy": {"devices": ["cuda:0", "cuda:0", "cpu"], "rows": 7, "readings": 3, "moved_after_passage": 6,
                       "device_at_end": "cpu"},
              "at_start": {"devices": ["cpu", "cpu", "cpu"], "rows": 7, "readings": 1, "moved_after_passage": 0,
                           "device_at_end": "cpu"},
              "free": {"devices": ["cuda:0", "cuda:0", "cuda:0"], "rows": 7, "readings": 4, "moved_after_passage": None,
                       "device_at_end": "cuda"}}


GPU_GATE = {"idle": True, "memory_busy": False, "compute_busy": False, "no_reading": False, "busy_refused": True,
            "loaded_when_busy": False}


def observe_replay_hook():
    import replay_prompts
    with tempfile.TemporaryDirectory() as td:
        case = write_case(td, "fixture-free")
        nb.build([case], Path(td) / "p.json")
        try:
            return {"loaded": len(replay_prompts.load_prompts(Path(td) / "p.json"))}
        except ValueError as exc:
            return {"loaded": str(exc)[:40]}


REPLAY_HOOK = {"loaded": 14}


# ---------------------------------------------------------------------------


class NegotiationMeasureChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        NegotiationMeasureChecks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    def test_01_mapping(self):
        # Neutralised: a missing row read as not_computable, the credit the plan refuses.
        real = score.pairs

        def lenient(key_rows, predictions):
            out = real(key_rows, predictions)
            return {c: [(k, "not_computable" if p == "no_answer" else p) for k, p in rows] for c, rows in out.items()}
        self.prove("missing_or_garbled_is_no_answer", observe_mapping, MAPPING, lambda: patch.object(score, "pairs", lenient))

    def test_02_macro_f1(self):
        # Neutralised: a class only the arm predicts counted at F1 0 (the rule D-395 N1 replaced).
        def with_predicted_class(c):
            from collections import Counter
            c = c if isinstance(c, Counter) else Counter(c)
            keys = {k for k, _ in c}
            if len(keys) < 2:
                return None
            classes = keys | ({p for _, p in c} & set(score.LABELS))
            vals = []
            for cl in sorted(classes):
                tp = c[(cl, cl)]
                fp = sum(n for (k, p), n in c.items() if p == cl and k != cl)
                fn = sum(n for (k, p), n in c.items() if k == cl and p != cl)
                vals.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
            return sum(vals) / len(vals)
        self.prove("macro_f1_over_the_keys_classes_only", observe_figures, _expected_figures(),
                   lambda: patch.dict(score.FIGURES, {"macro_f1": with_predicted_class}))

    def test_03_coverage(self):
        self.prove("coverage_is_not_recall", observe_figures, _expected_figures(),
                   lambda: patch.dict(score.FIGURES, {"coverage": score.movement_recall}))

    def test_04_openings(self):
        self.prove("no_score_without_a_committed_opening", observe_openings, OPENINGS_EXPECTED,
                   lambda: patch.object(score, "committed_text", lambda root, rel: (Path(root) / rel).read_text(encoding="utf-8")))

    def test_05_openings_limit(self):
        self.prove("at_most_two_openings", observe_openings, OPENINGS_EXPECTED, lambda: patch.object(score, "MAX_OPENINGS", 3))

    def test_06_claims_bounds(self):
        # Neutralised: every bound and the permutation p forced in the claim's favour.
        def favourable():
            import contextlib
            stack = contextlib.ExitStack()
            stack.enter_context(patch.object(score, "_pair_bca", lambda fn, paired, alpha, resamples=None: (0.0, 0.01, 0.02, 0.0)))
            stack.enter_context(patch.object(score, "_pair_jackknife_lower", lambda fn, paired, alpha: 0.01))
            stack.enter_context(patch.object(score, "permutation_p", lambda stat, paired, resamples=None: 0.0))
            return stack
        self.prove("a_claim_needs_every_bound_and_the_permutation", observe_claims, CLAIMS_EXPECTED, favourable)

    def test_06b_precision_conditions(self):
        # Neutralised: the precision claims' recall and coverage conditions dropped.
        real = score.test_claim

        def without_extra(name, fn, system, other, k, *, extra=None, resamples=None):
            out = real(name, fn, system, other, k, extra=None, resamples=resamples)
            if extra:
                for label, efn in extra.items():
                    est, _, upper, _ = score._pair_bca(efn, score._paired_parts(system, other)[1], 2 * score.alpha_for(k),
                                                       resamples=resamples)
                    out[label + "_difference"], out[label + "_upper"] = est, upper
            return out
        self.prove("precision_needs_recall_and_coverage", observe_claims, CLAIMS_EXPECTED,
                   lambda: patch.object(score, "test_claim", without_extra))

    def test_06c_indicators(self):
        self.prove("an_indicator_is_never_shown", observe_claims, CLAIMS_EXPECTED,
                   lambda: patch.object(score, "INDICATORS", frozenset()))

    def test_07_resampling(self):
        self.prove("exact_bootstrap_jackknife_and_permutation", observe_resampling, RESAMPLING,
                   lambda: patch.object(score, "_t_ppf", lambda p, df: score._norm_ppf(p)))

    def test_07b_exact_bootstrap(self):
        self.prove("the_bootstrap_is_exact_below_the_limit", observe_resampling, RESAMPLING,
                   lambda: patch.object(score, "EXACT_LIMIT", 0))

    def test_08_round3(self):
        real = score.round3_parts

        def without_python(open_issues, python, sheet):
            return real(open_issues, {k: dict(v, kept=True) for k, v in python.items()}, sheet)
        self.prove("round3_good_needs_python_and_the_sheet", observe_round3, ROUND3,
                   lambda: patch.object(score, "round3_parts", without_python))

    def test_08b_closed_rule(self):
        self.prove("a_quote_in_agreed_text_by_one_rule", observe_closed_rule, CLOSED_RULE,
                   lambda: patch.object(score, "_quote_norm", lambda text: str(text or "")))

    def test_09_movement_form(self):
        def substring(reply, config):
            said = nb._norm(reply)
            for a in config["movement"]["answers"]:
                if any(nb._norm(x) in said for x in a["accepted"]) and said:
                    return a["label"]
            return nb.NO_ANSWER
        self.prove("movement_reply_read_by_exact_spelling", observe_movement_form, MOVEMENT_FORM,
                   lambda: patch.object(nb, "parse_movement", substring))

    def test_10_suggestion_form(self):
        self.prove("suggestion_read_by_the_systems_checks", observe_suggestion_form, SUGGESTION_FORM,
                   lambda: patch.object(nb, "read_suggestion", lambda reply, chosen, sconfig: ({"kept": True}, None)))

    def test_11_freeze_leakage(self):
        self.prove("a_leaked_case_refuses_the_freeze", observe_freeze, FREEZE,
                   lambda: patch.object(freezer, "leakage", lambda mine, mv, corpora, cv, urls=(), stems=(), **kw:
                                        {n: {"exact": 0, "jaccard": 0, "cosine": 0, "same_source": 0} for n in corpora}))

    def test_11b_docx_and_jsonl_are_read(self):
        self.prove("a_docx_and_a_jsonl_corpus_are_read", observe_freeze, FREEZE,
                   lambda: patch.object(freezer, "read_file", _old_read_file))

    def test_11c_same_source(self):
        import re as _re
        self.prove("the_same_source_refuses_the_freeze", observe_freeze, FREEZE,
                   lambda: patch.object(freezer, "_URL", _re.compile(r"(?!)")))

    def test_11d_minimums(self):
        self.prove("a_case_below_the_minimums_refuses", observe_freeze, FREEZE,
                   lambda: patch.object(freezer, "MINIMUMS", {"rounds": 3, "parties": 2, "issues": 1, "open_issues": 1}))

    def test_11e_gram_index(self):
        # Neutralised: the index finds nothing, so a near copy only the 5-gram test sees passes the freeze.
        self.prove("the_5gram_index_equals_every_pair", observe_gram_index, GRAM_INDEX,
                   lambda: patch.object(freezer.GramIndex, "matches", lambda self, theirs, skip_owner=None: set()))

    def test_11f_float32_in_chunks(self):
        # Neutralised: the encoding before D-437 item 2, every passage of a corpus at once into Python floats.
        def at_once(encode, texts, progress=None, label="", chunk=None):
            return [list(map(float, v)) for v in encode(list(texts))]
        self.prove("float32_vectors_encoded_in_chunks", observe_encoding, ENCODING,
                   lambda: patch.object(freezer, "encode_chunked", at_once))

    def test_11g_token_batches(self):
        # Neutralised: fixed batches of sixteen in the given order, the batching that put sixteen long
        # passages together and took a slice past 6 GB.
        def fixed(lengths, budget=None, most=None):
            return [list(range(i, min(i + 16, len(lengths)))) for i in range(0, len(lengths), 16)]
        self.prove("long_passages_never_share_a_batch", observe_token_batches, TOKEN_BATCHES,
                   lambda: patch.object(freezer, "token_batches", fixed))

    def test_12_freeze_labeller_3(self):
        # Neutralised: labeller 1's key taken as settled, with no second labeller and no labeller 3.
        def first_labeller_only(case_dirs):
            rows = []
            for case_id, case_dir in case_dirs:
                for k, v in sorted(freezer._rows(Path(case_dir) / "KEY_MOVEMENT.json").items()):
                    rows.append({"case_id": case_id, "issue_id": k[0], "rounds": list(k[1]), "label": v})
            return rows, {"kappa_before": 1.0, "per_case_before": {}, "revised": False, "kappa_after": None,
                          "labeller_3": None, "decided_by_labeller_3": 0, "dropped": 0}
        self.prove("labeller_3_where_the_plan_says", observe_freeze, FREEZE,
                   lambda: patch.object(freezer, "settle_all", first_labeller_only))

    def test_12b_pooled_kappa(self):
        # Neutralised: the floor applied case by case, as before D-419 gap 3 (beta alone falls below it).
        real = freezer.settle_all

        def per_case(case_dirs):
            settled, record = [], None
            for item in case_dirs:
                rows, rec = real([item])
                settled += rows
                record = rec if record is None else dict(record, decided_by_labeller_3=record["decided_by_labeller_3"]
                                                         + rec["decided_by_labeller_3"])
            return settled, record
        self.prove("the_kappa_floor_on_the_pooled_rows", observe_freeze, FREEZE,
                   lambda: patch.object(freezer, "settle_all", per_case))

    def test_13_power(self):
        real = power_tool.simulate_set

        def system_as_weak(shares, case_sizes, open_per_case, icc, rng, assumed=power_tool.ASSUMED):
            return real(shares, case_sizes, open_per_case, icc, rng, dict(assumed, agreement=dict(assumed["agreement"], system=0.30)))
        self.prove("power_falls_for_a_weaker_system", observe_power, POWER,
                   lambda: patch.object(power_tool, "simulate_set", system_as_weak))

    def test_13b_power_record_by_the_plan_rule(self):
        # Neutralised: the list the record carried before D-437, below 0.8 at every correlation.
        def every(power_by_icc):
            names = sorted({n for v in power_by_icc.values() for n in v})
            return [n for n in names if all(v.get(n, 0.0) < 0.8 for v in power_by_icc.values())]
        self.prove("the_power_record_read_by_the_plan_rule", observe_plan_rule, PLAN_RULE,
                   lambda: patch.object(power_tool, "below_at_any_icc", every))

    def test_15_round3_on_the_command_line(self):
        self.prove("the_round3_report_behind_the_same_refusals", observe_scorer_path, SCORER_PATH,
                   lambda: patch.object(score, "apply_closed_rule", lambda python, case_units: python))

    def test_15b_c1_status_from_its_power_record(self):
        self.prove("c1_decided_by_its_power_record", observe_scorer_path, SCORER_PATH,
                   lambda: patch.object(score, "c1_status", lambda record, freeze, **kw: ("claim", None)))

    def test_15c_no_answer_for_every_arm(self):
        real = score.counts
        self.prove("a_no_answer_count_for_every_arm", observe_scorer_path, SCORER_PATH,
                   lambda: patch.object(score, "counts", lambda rows: real(None if rows is None else
                                                                           [(k, p) for k, p in rows if p != score.NO_ANSWER])))

    def test_16_refusals(self):
        self.prove("dry_run_records_and_power_refused", observe_scorer_refusals, SCORER_REFUSALS,
                   lambda: patch.object(score, "refuse_records", lambda configuration, **kw: None))

    def test_16b_refuse_freeze(self):
        self.prove("a_dry_run_freeze_is_refused", observe_scorer_refusals, SCORER_REFUSALS,
                   lambda: patch.object(score, "refuse_freeze", lambda freeze: None))

    def test_16c_one_model_group(self):
        def any_groups(answers):
            out = {}
            for r in answers["rows"]:
                if r.get("form") == "movement":
                    out[(r["case_id"], r["issue_id"], tuple(r["rounds"]))] = r.get("label")
            return out
        self.prove("an_answers_file_of_one_model_group", observe_scorer_refusals, SCORER_REFUSALS,
                   lambda: patch.object(score, "reply_answers", any_groups))

    def test_16d_failed_entries(self):
        # Neutralised: the path before D-437 item 1, any run with a case manifest and any FINAL_STATUS.json
        # (a file path, a successful run, a failure for the system's own reasons) taken as a failed entry.
        def before(runs):
            failures = {}
            for run in runs:
                if not (Path(run) / "audit" / "multi_round.json").is_file():
                    if not (score._case_of(run) and score._final_status(run) is not None):
                        return "a system run has neither its case record nor a final status", {}
                    failures[score._case_of(run)] = {"kind": "infrastructure", "reasons": "any"}
            return None, failures
        self.prove("a_failed_entry_from_its_status_record_only", observe_failed_entries, FAILED_ENTRIES,
                   lambda: patch.object(score, "refuse_system_runs", before))

    def test_16e_failed_entry_reason(self):
        # Neutralised: every failed record read as an infrastructure failure, so the system's own failures
        # would be excused and could call for opening 2 (D-451).
        real = score.failed_entry_kind

        def all_infrastructure(status, controller_records=()):
            kind, why = real(status, controller_records)
            return ("infrastructure" if kind else None), why
        self.prove("the_systems_own_failure_named_apart", observe_failed_entries, FAILED_ENTRIES,
                   lambda: patch.object(score, "failed_entry_kind", all_infrastructure))

    def test_16f_failed_rows_kept(self):
        # Neutralised: a failed case's rows dropped from the frozen key before scoring, so its no_answer
        # rows would vanish from every figure.
        real = score.report

        def dropping(key_rows, arms, subsets, opening, *a, **kw):
            seen = {k[0] for k in arms.get("system", {})}
            return real([r for r in key_rows if r["case_id"] in seen], arms, subsets, opening, *a, **kw)
        self.prove("a_failed_case_keeps_every_row_as_no_answer", observe_failed_entries, FAILED_ENTRIES,
                   lambda: patch.object(score, "report", dropping))

    def test_16g_pipeline_exception_is_the_systems_own(self):
        # Neutralised: the rule of D-437, any terminal error read as infrastructure.
        real = score.failed_entry_kind

        def by_name_only(status, controller_records=()):
            error = (status or {}).get("terminal_error") if isinstance(status, dict) else None
            if isinstance(error, dict) and error.get("error_type") == "MemoryError":
                return "infrastructure", "by name"
            return real(status, controller_records)
        self.prove("a_terminal_error_read_by_its_recorded_identity", observe_failed_entries, FAILED_ENTRIES,
                   lambda: patch.object(score, "failed_entry_kind", by_name_only))

        def any_terminal_error(status, controller_records=()):
            if isinstance(status, dict) and status.get("terminal_error") and status.get("status") == score.FAILED_STATUS:
                return "infrastructure", "terminal error"
            return real(status, controller_records)
        self.prove("a_pipeline_exception_is_the_systems_own", observe_failed_entries, FAILED_ENTRIES,
                   lambda: patch.object(score, "failed_entry_kind", any_terminal_error))

    def test_16k_cuda_out_of_memory_is_the_systems_own(self):
        # Neutralised: the list before the lead's ruling, CUDA out-of-memory excused as infrastructure.
        self.prove("a_cuda_out_of_memory_is_the_systems_own", observe_failed_entries, FAILED_ENTRIES,
                   lambda: patch.object(score, "INFRASTRUCTURE_ERRORS", (("OutOfMemoryError", "torch.cuda"),
                                                                         ("OutOfMemoryError", "torch"),
                                                                         ("MemoryError", "builtins"))))

    def test_16h_failed_in_any_state(self):
        # Neutralised: the rule before this recheck, a FAILED status refused unless its state is failed or
        # stopped, so a run failed by its assessment after reaching its end would refuse the scoring.
        real = score.failed_entry_kind

        def state_gated(status, controller_records=()):
            state = ((status or {}).get("pipeline_completion") or {}).get("state") if isinstance(status, dict) else None
            if isinstance(status, dict) and state is not None and state not in ("failed", "stopped")                     and not controller_records:
                return None, "its pipeline state is %s, neither failed nor stopped" % state
            return real(status, controller_records)
        self.prove("a_failed_status_in_any_state_is_the_systems_own", observe_failed_entries, FAILED_ENTRIES,
                   lambda: patch.object(score, "failed_entry_kind", state_gated))

    def test_16i_entry_root_only(self):
        # Neutralised: the first folder up holding a seal, as at e69dbe57, which is downloaded/ itself.
        def first_with_seal(run):
            for folder in [Path(run)] + list(Path(run).parents)[:6]:
                if (folder / "seal.json").is_file():
                    return folder
            return None
        self.prove("records_read_only_at_the_entry_root", observe_failed_entries, FAILED_ENTRIES,
                   lambda: patch.object(score, "entry_root", first_with_seal))

    def test_16j_reasons_decide(self):
        # Neutralised: a controller record taken over the runner's reasons, as at e69dbe57.
        real = score.failed_entry_kind

        def record_first(status, controller_records=()):
            if controller_records and isinstance(status, dict) and status.get("status") == score.FAILED_STATUS:
                return "infrastructure", "controller record " + ", ".join(controller_records)
            return real(status, controller_records)
        self.prove("the_runners_reasons_decide_the_kind", observe_failed_entries, FAILED_ENTRIES,
                   lambda: patch.object(score, "failed_entry_kind", record_first))

    def test_17_c1_needs_every_correlation(self):
        # Neutralised: C1 a claim when any one correlation reaches 0.8 (the rule D-430 item 1 refuses).
        real = score.c1_status

        def any_one(record, freeze, committed_code=None):
            status, why = real(record, freeze, committed_code=committed_code)
            if why is None and any(v.get("C1", 0) >= 0.8 for v in record["power"].values()):
                return "claim", None
            return status, why
        self.prove("c1_a_claim_only_at_every_correlation", observe_c1_rule, C1_RULE,
                   lambda: patch.object(score, "c1_status", any_one))

    def test_17b_power_record_of_the_committed_code(self):
        real = score.c1_status
        self.prove("the_power_record_of_the_committed_code", observe_c1_rule, C1_RULE,
                   lambda: patch.object(score, "c1_status", lambda record, freeze, committed_code=None:
                                        real(record, freeze, committed_code=(record.get("code_sha256"), record.get("assumed")))))

    def test_18_corpora_fail_closed(self):
        real = freezer.corpus_passages

        def lenient(paths, accept_skipped=()):
            paths = [p for p in paths if Path(p).exists()]
            return real(paths, accept_skipped=sorted({".pdf", ".bin"} | set(accept_skipped))) if paths else {}
        self.prove("a_missing_empty_or_unread_corpus_refuses", observe_freeze, FREEZE,
                   lambda: patch.object(freezer, "corpus_passages", lenient))

    def test_19_gpu_only_when_idle(self):
        self.prove("the_gpu_only_when_it_reads_idle", observe_gpu_gate, GPU_GATE,
                   lambda: patch.object(freezer, "gpu_idle", lambda reading: True))

    def test_19b_gpu_given_up_when_taken(self):
        # Neutralised: the GPU read once at the start only, as before D-456 item 3.
        self.prove("the_gpu_pass_moves_to_the_cpu_when_taken", observe_gpu_switch, GPU_SWITCH,
                   lambda: patch.object(freezer, "gpu_free_of_others", lambda reading: True))

    def test_19c_gpu_reading_on_windows(self):
        # Neutralised: the [N/A] of Windows' display driver read as no other process, so a taken GPU
        # would look free.
        real = freezer.other_gpu_reading

        def na_as_zero(own_mib=None, own_overhead_mib=None):
            r = real(own_mib, own_overhead_mib)
            return dict(r, other_processes_mib=0.0) if r and r.get("method") == "whole_less_own" else r
        self.prove("the_gpu_read_where_the_driver_hides_processes", observe_gpu_reading, GPU_READING,
                   lambda: patch.object(freezer, "other_gpu_reading", na_as_zero))

    def test_19f_gpu_read_before_the_first_chunk(self):
        # Neutralised: no reading before the first chunk, so a GPU taken while the model loaded runs a
        # whole chunk before it is seen.
        self.prove("the_gpu_read_before_the_first_chunk", observe_gpu_switch, GPU_SWITCH,
                   lambda: patch.object(freezer, "WATCH_BEFORE_FIRST_CHUNK", False))

    def test_19d_listing_without_this_process(self):
        self.prove("a_listing_without_this_process_is_not_per_process", observe_gpu_reading, GPU_READING,
                   lambda: patch.object(freezer, "other_gpu_reading", _old_other_gpu_reading))

    def test_19e_utilisation_beyond_own(self):
        # Neutralised: memory only, as at e69dbe57; a card busy beyond this process's own use looks free.
        def memory_only(reading):
            return isinstance(reading, dict) and reading.get("other_processes_mib") is not None and \
                reading["other_processes_mib"] <= freezer.GPU_IDLE_MIB
        self.prove("utilisation_beyond_this_process_at_10_percent", observe_gpu_switch, GPU_SWITCH,
                   lambda: patch.object(freezer, "gpu_free_of_others", memory_only))

    def test_14_replay_hook(self):
        import replay_prompts
        self.prove("the_replay_pass_hands_the_file_on", observe_replay_hook, REPLAY_HOOK,
                   lambda: patch.object(replay_prompts, "is_negotiation", lambda path: False))


def check():
    NegotiationMeasureChecks.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(NegotiationMeasureChecks).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, no model and no held-out case: the label mapping "
                    "with no_answer always wrong, Macro-F1 over the key's classes and the two floors, coverage apart from "
                    "recall, no score without a committed opening and at most two, a claim only when the BCa and "
                    "jackknife bounds and the permutation p agree at 0.05/2^k (and, for precision, recall and coverage "
                    "not below zero), an indicator never shown, the exact bootstrap, round 3 good only with Python's "
                    "checks and the sheet, one rule for a quote in agreed text, both B1 forms, the freeze (leakage through "
                    ".docx and .jsonl corpora, a near copy through one 5-gram index equal to every pair, and the same source, float32 vectors in chunks, pooled kappa with its revision round and labeller 3, the "
                    "minimums, the dry run), the scorer's command line (round 3 behind the same refusals, C1 decided by "
                    "its power record, a no_answer count for every arm, every arm's records checked, a failed entry only from its status record and only as a run folder, either kind scored no_answer on every row and counted apart, infrastructure only for the runner's or the machine's causes, one model group), "
                    "the power simulation and its record read by the plan rule, and the replay hook" % len(NegotiationMeasureChecks.evidence))


def main():
    status, detail = check()
    for proof in NegotiationMeasureChecks.evidence:
        print(proof["name"], proof["status"])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
