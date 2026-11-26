#!/usr/bin/env python3
"""Checks 703 and 704 (beta list item 17, Seckin 23 November 2026): every empty answer is tagged `empty`,
counted, listed by item id beside the score report, and read again at the next run; no score changes.

703 (tools/coverage_check.py, the ContraDoc and SciTab label outputs): each not-answered row is tagged empty with
    its basis as the reason; the coverage counts and the verdict are the same as without the tag; the item ids go
    to the --empty-list file only, never to the printed lines; --recheck reads an earlier listing and gives each
    previously empty item now_answered, still_empty or not_in_this_run.
704 (the negotiation scorer, never edited): tools/empty_answers.py negotiation_report calls
    score_neg_advisor.report() unchanged and tags each proposal an arm left without an answer empty with M10's own
    reason (no_reply, no_piece, withheld, no_stance, stance_not_declared); the report is the same bytes with and
    without it; `neg-score` wraps `score`, prints counts only and writes the listing inside the set folder only;
    recheck_listings reads an earlier listing per arm; and score_neg_advisor.py's code_sha256, pinned in every
    negotiation power record, equals the base commit's (52fbd0f3).

Each proof neutralised, failed, restored and passed (scripts/effect_proof.py). Invented fixtures only: no model,
no benchmark item, no answer key.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
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
import coverage_check as cc  # noqa: E402
import empty_answers as ea  # noqa: E402

# score_neg_advisor.code_sha256() at 52fbd0f3 (LF bytes): pinned in every negotiation power record.
SCORER_SHA256_AT_BASE = "5530723390a33f79a28b4d46ab6a1e2a31caa98030d57849eae6ba29e17192a9"

# Invented label rows: one answered, three not answered under three bases.
LABEL_ROWS = [
    {"item_id": "fx-i1", "document_id": "fx-d1", "basis": "ok", "class": "CLEAR"},
    {"item_id": "fx-i2", "document_id": "fx-d2", "basis": "silent", "class": "CLEAR"},
    {"item_id": "fx-i3", "document_id": "fx-d3", "basis": "dev_not_established", "class": "ABSTAIN"},
    {"item_id": "fx-i4", "document_id": "fx-d4", "basis": "run_failure", "class": "ABSTAIN"},
]


def _labels(folder, rows, name="labels.json"):
    path = Path(folder) / name
    path.write_text(json.dumps({"primary": {"labels": rows}}), encoding="utf-8")
    return path


def _coverage(folder, rows, previous=None):
    """(exit code, printed text, report, listing) of one coverage_check run on invented rows."""
    labels = _labels(folder, rows)
    report, listing = Path(folder) / "report.json", Path(folder) / "empty.json"
    argv = [str(labels), "--out", str(report), "--empty-list", str(listing)]
    if previous is not None:
        argv += ["--recheck", str(previous)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cc.main(argv)
    return (code, buf.getvalue(), json.loads(report.read_text(encoding="utf-8")),
            json.loads(listing.read_text(encoding="utf-8")))


class EmptyAnswerChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        EmptyAnswerChecks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    # ---- 703: the coverage check
    def test_703a_not_answered_rows_tagged_and_listed_by_id(self):
        def observe():
            with tempfile.TemporaryDirectory(prefix="empty703_") as td:
                code, text, report, listing = _coverage(td, LABEL_ROWS)
            c = report["files"]["labels.json"]
            return (code, c["answered"], c["not_answered"], report["verdict"],
                    [(e["item_id"], e["tag"], e["reason"]) for e in listing["empty"]],
                    c["empty"]["count"], c["empty"]["label_tr"], len(listing["scored_keys"]),
                    any(r["item_id"] in text for r in LABEL_ROWS))
        want = (3, 1, 3, "refused",
                [("fx-i2", "empty", "silent"), ("fx-i3", "empty", "dev_not_established/ABSTAIN"),
                 ("fx-i4", "empty", "run_failure/ABSTAIN")], 3, ea.LABEL_TR, 4, False)
        self.assertEqual(observe(), want)
        # The tag changes no count: the same counts and verdict as the check's own basis reading.
        self.prove("coverage_empty_rows_listed_by_id", observe, want,
                   lambda: patch.object(ea, "entry", lambda item_id, reason, sub_id=None: {
                       "item_id": None, "sub_id": None, "tag": ea.TAG, "reason": reason}))
        self.prove("coverage_counts_unchanged_by_the_tag", observe, want,
                   lambda: patch.object(cc, "ANSWERED", cc.ANSWERED + ("silent",)))

    def test_703b_recheck_reads_each_previous_empty_item(self):
        def observe():
            with tempfile.TemporaryDirectory(prefix="empty703r_") as td:
                first = Path(td) / "first"
                first.mkdir()
                _coverage(first, LABEL_ROWS)
                second = Path(td) / "second"
                second.mkdir()
                rows = [dict(LABEL_ROWS[0]), dict(LABEL_ROWS[1], basis="ok"), dict(LABEL_ROWS[2])]
                code, text, report, listing = _coverage(second, rows, previous=first / "empty.json")
            return (report["recheck"], sorted((e["item_id"], e["status"]) for e in listing["recheck"]["items"]),
                    "previously empty 3: now answered 1, still empty 1, not in this run 1" in text)
        want = ({"now_answered": 1, "still_empty": 1, "not_in_this_run": 1},
                [("fx-i2", "now_answered"), ("fx-i3", "still_empty"), ("fx-i4", "not_in_this_run")], True)
        self.assertEqual(observe(), want)
        self.prove("recheck_now_answered_still_empty_absent", observe, want,
                   lambda: patch.object(ea, "NOW_ANSWERED", ea.NOT_IN_THIS_RUN))

    def test_703c_cli_recheck_and_refusals(self):
        with tempfile.TemporaryDirectory(prefix="empty703c_") as td:
            labels = _labels(td, LABEL_ROWS)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cc.main([str(labels), "--recheck", str(labels)]), 2)   # recheck needs a listing out
                self.assertEqual(cc.main([str(labels), "--empty-list", str(Path(td) / "e.json"),
                                          "--recheck", str(labels)]), 2)             # not a listing
                self.assertEqual(ea.main(["recheck", str(labels), str(labels)]), 2)

    # ---- 704: the negotiation advisor scorer
    def _neg(self):
        import neg_advisor_checks as base
        sc = ea._scorer()   # the module negotiation_report and neg-score use
        item, key = base.built()
        iid = item["item_id"]
        one = base.reply_of(item, dict(base.GOOD_REPLY, proposals=[base.GOOD_REPLY["proposals"][0]]))
        rows = lambda group, reply: {"rows": [{"item_id": iid, "form": "advice", "group": group, "reply": reply,
                                               "audit": {}, "drops": {}}]}
        arms = {"B1": (rows("b1", one), "b1"), "system": (rows("system_advice", copy.deepcopy(one)), "system_advice"),
                "cloud": (rows("b1", None), "b1")}
        return sc, iid, item, key, arms

    def test_704a_empty_pieces_tagged_per_arm_figures_unchanged(self):
        sc, iid, item, key, arms = self._neg()

        def observe():
            _rep, listed, summ = ea.negotiation_report({iid: item}, {iid: key}, copy.deepcopy(arms), resamples=50)
            return ({a: (s["count"], s["scored"], s["by_reason"]) for a, s in sorted(summ.items())},
                    sorted((e["item_id"], e["sub_id"], e["reason"]) for e in listed["B1"]["empty"]),
                    sorted(listed["cloud"]["scored_keys"]) == sorted(ea.key_of(iid, p) for p in key["proposals"]))
        got = observe()
        n = len(key["proposals"])
        self.assertEqual(got[0]["B1"], (n - 1, n, {"no_piece": n - 1}))
        self.assertEqual(got[0]["cloud"], (n, n, {"no_reply": n}))
        self.assertEqual(got[1], sorted((iid, p, "no_piece") for p in key["proposals"] if p != "P-A1-1"))
        self.assertTrue(got[2])
        self.prove("negotiation_empty_pieces_tagged_by_reason", observe, got,
                   lambda: patch.object(sc, "open_point_prediction", lambda reply, given, pid: ("settled", None)))
        # The scorer's report is returned as it is: the same bytes with and without the recording, module restored.
        plain = sc.report({iid: item}, {iid: key}, copy.deepcopy(arms), resamples=50)
        wrapped = ea.negotiation_report({iid: item}, {iid: key}, copy.deepcopy(arms), resamples=50)[0]
        self.assertEqual(json.dumps(plain, sort_keys=True, default=str), json.dumps(wrapped, sort_keys=True, default=str))
        self.assertIs(sc.item_parts.__module__, sc.__name__)
        self.assertIs(sc.replies_by_item.__module__, sc.__name__)

    def test_704b_recheck_per_arm(self):
        sc, iid, item, key, arms = self._neg()
        previous = copy.deepcopy(ea.negotiation_report({iid: item}, {iid: key}, copy.deepcopy(arms), resamples=50)[1])
        previous["B1"]["empty"].append(ea.entry("fx-gone", "no_reply", "P-X-1"))
        import neg_advisor_checks as base
        full = base.reply_of(item, base.GOOD_REPLY)
        later = dict(arms, B1=({"rows": [{"item_id": iid, "form": "advice", "group": "b1", "reply": full,
                                          "audit": {}, "drops": {}}]}, "b1"))
        n = len(key["proposals"])

        def observe():
            now = ea.negotiation_report({iid: item}, {iid: key}, copy.deepcopy(later), resamples=50)[1]
            return ea.recheck_listings(previous, now)
        got = observe()
        self.assertEqual(got["B1"], {"now_answered": n - 1, "still_empty": 0, "not_in_this_run": 1})
        self.assertEqual(got["cloud"], {"now_answered": 0, "still_empty": n, "not_in_this_run": 0})
        self.prove("negotiation_recheck_per_arm", observe, got,
                   lambda: patch.object(ea, "STILL_EMPTY", ea.NOW_ANSWERED))

    def test_704c_the_cli_wraps_score_and_writes_inside_the_set_only(self):
        sc, iid, item, key, arms = self._neg()

        def fake_main(argv):
            # Stands in for `score` past its refusals: the module's report() as main calls it, then its print.
            rep = sc.report({iid: item}, {iid: key}, copy.deepcopy(arms), resamples=50)
            rep.pop("_per_item", None)
            print(json.dumps({"figures": sorted(rep["figures"])}))
            return 0

        def observe():
            with tempfile.TemporaryDirectory(prefix="empty704_") as td:
                setdir = Path(td) / "set"
                setdir.mkdir()
                buf = io.StringIO()
                with patch.object(sc, "main", fake_main), contextlib.redirect_stdout(buf):
                    code = ea.main(["neg-score", "--empty-list", str(setdir / "empty.json"), "--",
                                    "score", "--set", str(setdir)])
                    outside = None
                    try:
                        ea.main(["neg-score", "--empty-list", str(Path(td) / "empty.json"), "--",
                                 "score", "--set", str(setdir)])
                    except ValueError:
                        outside = "refused"
                    default = ea.main(["neg-score", "--", "score", "--set", str(setdir)])   # D-950: set folder
                    bad = ea.main(["neg-score", "--", "score"])
                default = (default, (setdir / ea.DEFAULT_NEG_LISTING).is_file(),
                           str((setdir / ea.DEFAULT_NEG_LISTING).resolve()) in buf.getvalue())
                listed = json.loads((setdir / "empty.json").read_text(encoding="utf-8"))
                last = json.loads(buf.getvalue().strip().splitlines()[1])
            return (code, sorted(listed), (last["empty"].get("B1") or {}).get("count"), outside, default, bad,
                    iid in buf.getvalue(), sc.report.__module__ == sc.__name__)
        n = len(key["proposals"])
        want = (0, ["B1", "cloud", "system"], n - 1, "refused", (0, True, True), 2, False, True)
        self.assertEqual(observe(), want)
        self.prove("neg_score_wrapper_writes_listing_inside_the_set", observe, want,
                   lambda: patch.object(ea, "_listings", lambda found: {}))

    def test_704d_the_scorer_bytes_are_those_of_the_base_commit(self):
        # Every negotiation power record pins score_neg_advisor.code_sha256(); the empty tagging never edits it.
        sc = self._neg()[0]
        self.assertEqual(sc.code_sha256(), SCORER_SHA256_AT_BASE)
        observe = lambda: sc.code_sha256() == SCORER_SHA256_AT_BASE
        with tempfile.TemporaryDirectory(prefix="empty704d_") as td:
            edited = Path(td) / "score_neg_advisor.py"
            edited.write_bytes(Path(sc.__file__).read_bytes() + b"\n# an edit\n")
            self.prove("scorer_code_sha256_unchanged", observe, True,
                       lambda: patch.object(sc, "__file__", str(edited)))

    # ---- Revision 2 (Seckin 18:10, G-20261123-1812): (a) both figures side by side, (c) withheld apart from silence
    def test_703d_both_figures_and_withheld_apart_from_silence(self):
        rows = ([{"item_id": "fx-c%02d" % n, "document_id": "fx-t%d" % (n % 4), "basis": "ok", "class": "CLEAR"}
                 for n in range(13)]
                + [{"item_id": "fx-c13", "document_id": "fx-t1", "basis": "dev_not_established", "class": "ABSTAIN"},
                   {"item_id": "fx-c14", "document_id": "fx-t2", "basis": "dev_silence", "class": "ABSTAIN"}])

        def observe():
            with tempfile.TemporaryDirectory(prefix="empty703d_") as td:
                labels = _labels(td, rows)
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = cc.main([str(labels), "--out", str(Path(td) / "r.json"), "--empty-list",
                                    str(Path(td) / "e.json"), "--correct", "11"])
                report = json.loads((Path(td) / "r.json").read_text(encoding="utf-8"))
            text = buf.getvalue()
            lines = [ln for ln in text.splitlines() if "main figure" in ln or "withheld by" in ln or "silence (no" in ln]
            return (code, report["figures"]["main"], report["figures"]["blanks_counted_wrong"],
                    report["files"]["labels.json"]["answered"], report["files"]["labels.json"]["empty"]["by_kind"],
                    lines, any(r["item_id"] in text for r in rows), "e.json" in text)
        want = (3, 0.8462, 0.7333, 13, {"withheld": 1, "silence": 1},
                ["labels.json: empty (%s), withheld by the system as unsupported: 1" % ea.LABEL_TR,
                 "labels.json: empty (%s), silence (no answer given): 1" % ea.LABEL_TR,
                 "main figure 0.8462 (11 of 13 answered right) | blanks counted wrong 0.7333 (11 of 15)"],
                False, True)
        self.assertEqual(observe(), want)
        self.prove("coverage_both_figures_side_by_side", observe, want,
                   lambda: patch.object(ea, "both_figures", lambda c, a, n: {
                       "main": round(c / a, 4), "blanks_counted_wrong": round(c / a, 4), "correct": c,
                       "answered": a, "items": a}))
        self.prove("coverage_withheld_counted_apart_from_silence", observe, want,
                   lambda: patch.object(ea, "kind_of", lambda reason: ea.SILENCE))

    def test_703e_the_listing_defaults_to_the_report_folder(self):
        # D-950 (Seckin 18:10, item b): with no --empty-list the listing is written beside the --out report.
        def observe():
            with tempfile.TemporaryDirectory(prefix="empty703e_") as td:
                folder = Path(td) / "report_folder"
                folder.mkdir()
                labels = _labels(td, LABEL_ROWS)
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    cc.main([str(labels), "--out", str(folder / "cov.json")])
                report = json.loads((folder / "cov.json").read_text(encoding="utf-8"))
                where = folder / "cov_empty.json"
                return (where.is_file(), report.get("listing") == str(where.resolve()),
                        str(where.resolve()) in buf.getvalue())
        want = (True, True, True)
        self.assertEqual(observe(), want)
        self.prove("coverage_listing_in_the_report_folder", observe, want,
                   lambda: patch.object(cc, "default_listing", lambda out: str(Path(out).parent.parent / "cov_empty.json")))

    def test_704e_negotiation_both_figures_and_withheld_line(self):
        sc, iid, item, key, arms = self._neg()
        entries = [ea.entry(iid, "withheld", "P-A1-1"), ea.entry(iid, "no_piece", "P-A1-2"),
                   ea.entry(iid, "no_reply", "P-A2-1")]

        def observe():
            rep = ea.negotiation_report({iid: item}, {iid: key}, copy.deepcopy(arms), resamples=50)[0]
            both = ea.neg_both_figures(rep)
            line = {"empty": {"system": ea.summary(entries, 3)}, "figures": {"system": both.get("system", {})},
                    "listing": "empty.json"}
            figures = {f: rep["figures"]["system"].get(f) for f in ea.NEG_FIGURES}
            return (sorted(both), all(v["main"] == v["blanks_counted_wrong"] for a in both.values() for v in a.values()),
                    {f: (v or {}).get("estimate") for f, v in figures.items()} == {
                        f: v["main"] for f, v in both["system"].items()},
                    ea.neg_lines(line)[-3:], any(e["item_id"] in "".join(ea.neg_lines(line)) for e in entries))
        want = (["B1", "cloud", "system"], True, True,
                ["system: empty (%s) 3 of 3 proposals, listed in empty.json" % ea.LABEL_TR,
                 "system: empty (%s), withheld by the system as unsupported: 1" % ea.LABEL_TR,
                 "system: empty (%s), silence (no answer given): 2" % ea.LABEL_TR], False)
        self.assertEqual(observe(), want)
        self.prove("negotiation_withheld_line_apart_from_silence", observe, want,
                   lambda: patch.object(ea, "kind_of", lambda reason: ea.SILENCE))


def check():
    EmptyAnswerChecks.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(EmptyAnswerChecks).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:5])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, invented fixtures: every not-answered label row "
                    "and every unanswered negotiation proposal tagged empty with its reason, counted, listed by id "
                    "beside the report only, read again at the next run, and no count, verdict or figure changed"
                    % len(EmptyAnswerChecks.evidence))


def check_703():
    return _subset("test_703")


def check_704():
    return _subset("test_704")


def _subset(prefix):
    EmptyAnswerChecks.evidence = []
    suite = unittest.TestSuite(t for t in unittest.defaultTestLoader.loadTestsFromTestCase(EmptyAnswerChecks)
                               if t.id().split(".")[-1].startswith(prefix))
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful() or not result.testsRun:
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors] or ["no test ran"]
        return "FAIL", "; ".join(problems[:5])
    return "PASS", "%d tests, %d proofs, each neutralise, fail, restore, pass, invented fixtures" % (
        result.testsRun, len(EmptyAnswerChecks.evidence))


def main():
    status, detail = check()
    for proof in EmptyAnswerChecks.evidence:
        print(proof["name"], proof["status"])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
