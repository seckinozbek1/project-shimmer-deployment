#!/usr/bin/env python3
"""NEG-READING-A (beta item 18, #326; D-929, D-930): the negotiation scorers' reading self-check and oddity alarm.

The pattern is the SciTab and ContraDoc scoring of D-929, `reading_check` and `odd_alarm` in
external/s05/R2_ROLE_STARTS/BSCORE/score_untouched.py of the main checkout (a role start folder outside git; no
tracked file holds it). Here it is carried to both negotiation scorers, neither of which is edited:
tools/score_neg_advisor.py (the advisor, M1 to M10; its power records pin its own SHA-256, plan section 7.3) and
tools/score_negotiation.py (the movement scorer, C1 to C5).

- Reading check. Before any figure, the known sample config/neg_reading_sample.json goes through the scorer's own
  reading code.
  - Advisor: an invented item and replies in the runner's saved form go through tools/reread_replies.py
    advisor_rows (the score-time reader, ANSWER-FORM-A) and score_neg_advisor.report(). The run uses the same
    article_link and audit_marked settings as the score it guards, or the development config's when run alone.
    Each case's per-item M1, M4 and M10 rows and its answered count are compared with the known ones.
  - Movement: reply texts go through reread_replies.negotiation_rows and score_negotiation.reply_answers, and
    system gap rows through score_negotiation.system_label. Each label is compared with the known one.

  Any difference stops the scoring: no score is written, a stop text names the cases (no real item, id, label
  or text) and the exit code is EXIT_READING. A sample with a wrong number stops the same way, and so does a
  missing or malformed sample: the sample is the known answer.
- Oddity alarm. After report(), each arm's rows NOT ANSWERED FOR A READING REASON are counted.
  - Advisor: each M10 row whose miss reason is in READING_REASONS (no_reply, no_piece, no_stance,
    stance_not_declared), read by the scorer's own functions on the same replies (replies_by_item, and for the
    system arm system_python and withhold, as report() runs them). Not counted (the lead, 23 November 2026): a
    piece the system withheld (`withheld`), and a `no_piece` row whose piece the system's Python step wrote
    (written_by python: the model gave none and Python filled it). A `no_piece` row with no piece at all is
    counted: it covers an entry the reader dropped (an unknown id, a form not read), and D-931's refusal of B1
    (118 such rows of 197) depended on it.
  - Movement: a key row an arm holds with the label no_answer (the reader or system_label could not read it). A
    row the arm does not hold at all (a failed entry) is not a reading error.

  More than ODD_SHARE (half) not answered means a reading fault is likelier than a result. WARNING ("okuma hatası
  olabilir", a possible reading error) is written. For the system arm the whole score is refused (EXIT_ODD). A
  comparison arm (B1, the cloud) is left out of the report, the report is computed again without it, and the
  warning goes in `reading_alarm`.
- When nothing trips, every figure is exactly report()'s. The report gains only `reading_check` and
  `answered_rows`.

    py -3.12 -X utf8 tools/neg_reading_check.py check [--sample F] [--stop-dir D]
    py -3.12 -X utf8 tools/neg_reading_check.py score <score_neg_advisor.py score arguments> [--sample F] [--stop-dir D]
    py -3.12 -X utf8 tools/neg_reading_check.py movement-score <score_negotiation.py arguments> [--sample F] [--stop-dir D]

Stop texts go to --stop-dir. When it is not given, `check` writes them to output/neg_reading_check/ (gitignored)
and the score commands write them to the --set folder's top. The freeze digest reads only the set's items/
(score_neg_advisor.set_digest), and score_negotiation reads only the case units under it, so a stop text there
does not move a frozen set's digest. A role script that calls report() itself calls `checked_report` (advisor)
or `checked_movement_report` (movement) in its place. Development and untouched scoring read replies the same
way in both scorers (neither has a detection_dev mode), so one sample serves both. Counts only leave this file.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import copy
import datetime as dt
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SAMPLE_PATH = ROOT / "config" / "neg_reading_sample.json"
SAMPLE_SCHEMA = "neg-reading-sample-v2"
CHECK_STOP_DIR = ROOT / "output" / "neg_reading_check"
ODD_SHARE = 0.5
READING_REASONS = ("no_reply", "no_piece", "no_stance", "stance_not_declared")
FIGURES = ("M1", "M4", "M10")
WARNING = "okuma hatası olabilir (a possible reading error): more than half of the rows not answered, no score written"
READING_FAILED = "okuma sağlaması tutmadı (the reading check failed)"
EXIT_ODD = 3
EXIT_READING = 5
STOP_PREFIX = "NEG_READING_STOP_"
SYSTEM = "system"
NO_ANSWER = "no_answer"
PROMPT_ID = "reading-check"


class ReadingRefused(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def scorer():
    """tools/score_neg_advisor.py of this tree, loaded once."""
    return _load("score_neg_advisor", ROOT / "tools" / "score_neg_advisor.py")


def movement_scorer():
    """tools/score_negotiation.py of this tree, loaded once (the same module score_neg_advisor loads as `sn`)."""
    return _load("score_negotiation", ROOT / "tools" / "score_negotiation.py")


def load_sample(path=None):
    sample = json.loads(Path(path or SAMPLE_PATH).read_text(encoding="utf-8"))
    if not isinstance(sample, dict) or sample.get("schema") != SAMPLE_SCHEMA or not sample.get("cases") \
            or not (sample.get("movement") or {}).get("replies"):
        raise ValueError("the reading sample is not of %s or holds no case" % SAMPLE_SCHEMA)
    return sample


def sample_build(sample, sc):
    """The sample's build with its terms text under neg_advisor.TERMS_FIELD (kept apart in the file)."""
    build = copy.deepcopy(sample["build"])
    if "terms_field_text" in build:
        build[sc.na.TERMS_FIELD] = build.pop("terms_field_text")
    return build


def _key(k):
    return ast.literal_eval(k)


def answered_rows(per_item):
    """(answered, rows) over one arm's per-item M10 rows as report() writes them (keys the str of a
    (key class, prediction) tuple): a row predicted no_answer is not answered."""
    answered = rows = 0
    for parts in (per_item or {}).values():
        for k, v in (parts.get("M10") or {}).items():
            rows += v
            if _key(k)[1] != NO_ANSWER:
                answered += v
    return answered, rows


def reading_misses(items, keys, arm, answers, group, ids, sc, *, article_link, audit_marked, python_step=True):
    """(rows not answered for a reading reason, M10 rows) of one arm over the item ids report() scored it on,
    each proposal read as report() reads it (score_neg_advisor._report_on and open_point_part): the system arm
    through system_python and withhold first. A withheld piece and a piece Python wrote are not counted."""
    rows = sc.replies_by_item(answers, group)
    missed = total = 0
    for i in ids:
        row = rows.get(i) or {}
        reply = given = row.get("reply")
        if arm == SYSTEM:
            if python_step:
                reply, _counts = sc.system_python(sc.linked_item(items[i], article_link, Counter()), reply)
            reply, _trail = sc.withhold(items[i], reply, row.get("audit"), marked=audit_marked)
        for pid, krow in keys[i]["proposals"].items():
            if sc.open_point_class(krow.get("fate")) is None:
                continue
            total += 1
            _pred, why = sc.open_point_prediction(reply, given, pid)
            if why not in READING_REASONS:
                continue
            piece = ((reply or {}).get("proposals") or {}).get(pid)
            if why == "no_piece" and piece is not None and piece.get("written_by") == sc.PYTHON:
                continue
            missed += 1
    return missed, total


def odd_alarm(not_answered, total):
    """Tuhaflık alarmı: more than ODD_SHARE of an arm's rows not answered for a reading reason."""
    return total > 0 and not_answered / total > ODD_SHARE


def settings(sc, kw=None):
    """(article_link, audit_marked) the guarded score uses: its own arguments, else the development config's."""
    kw = kw or {}
    article_link, audit_marked = kw.get("article_link"), kw.get("audit_marked")
    if article_link is None:
        article_link = sc.article_link_on(sc.dev_config())
    if audit_marked is None:
        audit_marked = sc.audit_marked_on(sc.dev_config())
    return bool(article_link), bool(audit_marked)


def _case_answers(case, item, sc):
    """The case's answers file as the score-time reader writes it from a saved reply (or a composed step-wise one)."""
    rr, na = sc.rr, sc.na
    prompt = {"prompt_id": PROMPT_ID, "group": case["group"], "form": "advice", "item_id": item["item_id"],
              "item": item}
    value = {"config": na.load_config(na.CONFIG_PATH), "_sha256": "reading-check", "prompts": [prompt]}
    composed = None
    if "composed" in case:
        reply = na.parse_advice(case["composed"]["text"], item)
        steps = [{"step": s.split(":", 1)[0], "refused": s.split(":", 1)[1]} for s in case["composed"]["steps_refused"]]
        composed = {PROMPT_ID: (reply, steps)}
    return rr.advisor_rows(value, {PROMPT_ID: case.get("text")}, composed=composed)


def read_case(case, items, keys, sc, report, article_link, audit_marked):
    """What the reading gives for one advisor case: its per-item M1, M4 and M10 rows and (answered, rows)."""
    item = next(iter(items.values()))
    arm = SYSTEM if case["group"] == "system_advice" else "B1"
    rep = report(items, keys, {arm: (_case_answers(case, item, sc), case["group"])}, resamples=50,
                 article_link=article_link, audit_marked=audit_marked)
    parts = (rep["_per_item"].get(arm) or {}).get(item["item_id"]) or {}
    return {"rows": {f: dict(sorted((parts.get(f) or {}).items())) for f in FIGURES},
            "answered": list(answered_rows(rep["_per_item"].get(arm)))}


def reading_check(sample=None, sc=None, report=None, *, article_link=None, audit_marked=None):
    """[(case name, wanted, read)] of every advisor case the reading gets wrong; empty when the reading holds.
    `report` is the scorer's own report() (not a guarded one)."""
    sc = sc or scorer()
    report = report or sc.report
    sample = sample if isinstance(sample, dict) else load_sample(sample)
    link, marked = settings(sc, {"article_link": article_link, "audit_marked": audit_marked})
    item, key = sc.build_item(sample_build(sample, sc))
    items, keys = {item["item_id"]: item}, {item["item_id"]: key}
    bad = []
    for case in sample["cases"]:
        got = read_case(case, items, keys, sc, report, link, marked)
        want = {"rows": {f: dict(sorted(case["expect"][f].items())) for f in FIGURES},
                "answered": [case["answered"], case["rows"]]}
        if got != want:
            diff = [f for f in FIGURES if got["rows"][f] != want["rows"][f]]
            if got["answered"] != want["answered"]:
                diff.append("answered %s, wanted %s" % (got["answered"], want["answered"]))
            bad.append((case["name"], diff))
    return bad


def movement_check(sample=None, sn=None):
    """[(case name, wanted label, read label)] of every movement case read wrong; empty when the reading holds."""
    sn = sn or movement_scorer()
    sample = sample if isinstance(sample, dict) else load_sample(sample)
    import negotiation_b1 as nb
    import reread_replies as rr
    m = sample["movement"]
    prompts = [{"prompt_id": "rc-%d" % i, "group": "b1", "form": "movement", "case_id": "rc-case",
                "issue_id": "rc-%d" % i, "rounds": [1, 2]} for i in range(len(m["replies"]))]
    value = {"config": nb.load_config(nb.CONFIG_PATH), "suggestion": {}, "_sha256": "reading-check", "prompts": prompts}
    answers = rr.negotiation_rows(value, {p["prompt_id"]: c["text"] for p, c in zip(prompts, m["replies"])})
    read = sn.reply_answers(answers)
    bad = [(c["name"], c["label"], read.get(("rc-case", "rc-%d" % i, (1, 2))))
           for i, c in enumerate(m["replies"]) if read.get(("rc-case", "rc-%d" % i, (1, 2))) != c["label"]]
    bad += [(c["name"], c["label"], sn.system_label(c["row"])) for c in m["system_rows"]
            if sn.system_label(c["row"]) != c["label"]]
    return bad


def now():
    return dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def stop_file(stop_dir, name, text):
    """Never end silently: a stop text, reason and counts only."""
    if stop_dir is None:
        return None
    path = Path(stop_dir) / ("%s%s.txt" % (STOP_PREFIX, name))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("%s %s\n" % (now(), text), encoding="utf-8")
    return path


def _refuse_reading(stop_dir, text):
    stop_file(stop_dir, "reading", text)
    raise ReadingRefused(EXIT_READING, text)


def require_reading(sample=None, sc=None, stop_dir=None, report=None, *, movement=False, **settings_kw):
    """Runs the reading check (the advisor's, or the movement scorer's with `movement`); the number of cases, or
    ReadingRefused (EXIT_READING) with a stop text. A missing or malformed sample is a failed check."""
    try:
        value = sample if isinstance(sample, dict) else load_sample(sample)
        bad = movement_check(value) if movement else reading_check(value, sc, report, **settings_kw)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _refuse_reading(stop_dir, "%s: the sample could not be read (%s: %s); no score written"
                        % (READING_FAILED, type(exc).__name__, exc))
    if bad:
        _refuse_reading(stop_dir, "%s: %d of the known sample cases read wrong: %s; no score written" % (
            READING_FAILED, len(bad), "; ".join("%s (%s)" % (b[0], ", ".join(map(str, b[1:]))) for b in bad)))
    return len(value["movement"]["replies"]) + len(value["movement"]["system_rows"]) if movement else len(value["cases"])


def _alarm(counts, arms, stop_dir):
    """The arms over the alarm; raises ReadingRefused (EXIT_ODD) when the system arm, or every arm, is one."""
    odd = sorted(arm for arm, (missed, n) in counts.items() if odd_alarm(missed, n))
    for arm in odd:
        stop_file(stop_dir, "odd_" + arm, "%s: arm %s, %d of %d rows not answered for a reading reason"
                  % (WARNING, arm, *counts[arm]))
    if SYSTEM in odd or (odd and len(odd) == len(arms)):
        raise ReadingRefused(EXIT_ODD, "%s: %s" % (WARNING, ", ".join("%s %d of %d not answered" % (a, *counts[a])
                                                                        for a in odd)))
    return odd


def _stamp(rep, cases, counts, odd, answered=None):
    rep["reading_check"] = {"status": "PASS", "cases": cases}
    rep["answered_rows"] = {arm: dict({"not_answered_for_reading": m, "rows": n},
                                      **({"answered": answered[arm][0]} if answered and arm in answered else {}))
                            for arm, (m, n) in counts.items()}
    if odd:
        rep["reading_alarm"] = {arm: {"not_answered_for_reading": counts[arm][0], "rows": counts[arm][1],
                                      "warning": WARNING} for arm in odd}
    return rep


def checked_report(items, keys, arms, *, sample=None, stop_dir=None, report=None, sc=None, **kw):
    """score_neg_advisor.report() behind the reading check and the oddity alarm (module docstring)."""
    sc = sc or scorer()
    report = report or sc.report
    link, marked = settings(sc, kw)
    cases = require_reading(sample, sc, stop_dir, report, article_link=link, audit_marked=marked)
    rep = report(items, keys, arms, **kw)
    counts = {arm: reading_misses(items, keys, arm, answers, group, sorted(rep["_per_item"].get(arm) or {}), sc,
                                  article_link=link, audit_marked=marked, python_step=kw.get("python_step", True))
              for arm, (answers, group) in arms.items()}
    odd = _alarm(counts, arms, stop_dir)
    if odd:
        rep = report(items, keys, {a: v for a, v in arms.items() if a not in odd}, **kw)
    return _stamp(rep, cases, counts, odd, {a: answered_rows(rep["_per_item"].get(a)) for a in arms if a not in odd})


def checked_movement_report(key_rows, arms, subsets, k, *, sample=None, stop_dir=None, report=None, sn=None, **kw):
    """score_negotiation.report() behind the movement reading check and the oddity alarm (module docstring)."""
    sn = sn or movement_scorer()
    report = report or sn.report
    cases = require_reading(sample, stop_dir=stop_dir, movement=True)
    keys = [(r["case_id"], r["issue_id"], tuple(r["rounds"])) for r in key_rows]
    counts = {arm: (sum(1 for x in keys if x in labels and labels[x] == sn.NO_ANSWER), len(keys))
              for arm, labels in arms.items()}
    odd = _alarm(counts, arms, stop_dir)
    rep = report(key_rows, {a: v for a, v in arms.items() if a not in odd}, subsets, k, **kw)
    return _stamp(rep, cases, counts, odd)


@contextlib.contextmanager
def guarded(sc, *, sample=None, stop_dir=None):
    """score_neg_advisor's report() replaced by checked_report for the length of the block."""
    original = sc.report

    def report(items, keys, arms, **kw):
        return checked_report(items, keys, arms, sample=sample, stop_dir=stop_dir, report=original, sc=sc, **kw)
    sc.report = report
    try:
        yield
    finally:
        sc.report = original


@contextlib.contextmanager
def guarded_movement(sn, *, sample=None, stop_dir=None):
    """score_negotiation's report() replaced by checked_movement_report for the length of the block."""
    original = sn.report

    def report(key_rows, arms, subsets, k, **kw):
        return checked_movement_report(key_rows, arms, subsets, k, sample=sample, stop_dir=stop_dir, report=original,
                                       sn=sn, **kw)
    sn.report = report
    try:
        yield
    finally:
        sn.report = original


def run_score(score_argv, *, sample=None, stop_dir=None, sc=None):
    """score_neg_advisor.py score with its own arguments, behind the guard; the exit code."""
    sc = sc or scorer()
    with guarded(sc, sample=sample, stop_dir=stop_dir):
        try:
            return sc.main(["score"] + list(score_argv))
        except ReadingRefused as r:
            print("refused: " + r.message)
            return r.code


def run_movement_score(argv, *, sample=None, stop_dir=None, sn=None):
    """score_negotiation.py with its own arguments, behind the guard; the exit code."""
    sn = sn or movement_scorer()
    with guarded_movement(sn, sample=sample, stop_dir=stop_dir):
        try:
            return sn.main(list(argv))
        except ReadingRefused as r:
            print("refused: " + r.message)
            return r.code


def _split(argv):
    """(own options, the rest) of argv: --sample F and --stop-dir D (or --sample=F, --stop-dir=D) are this file's."""
    own, rest, i = {}, [], 0
    while i < len(argv):
        name, eq, value = argv[i].partition("=")
        if name in ("--sample", "--stop-dir"):
            if eq:
                own[name[2:].replace("-", "_")] = value
                i += 1
                continue
            if i + 1 < len(argv):
                own[name[2:].replace("-", "_")] = argv[i + 1]
                i += 2
                continue
        rest.append(argv[i])
        i += 1
    return own, rest


def set_folder(argv):
    """The --set value of the scorer's own arguments (--set PATH or --set=PATH), or None."""
    for i, a in enumerate(argv):
        if a == "--set" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--set="):
            return a.split("=", 1)[1]
    return None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("check", "score", "movement-score"):
        print(__doc__.split("\n\n")[0])
        print("usage: neg_reading_check.py check|score|movement-score [--sample F] [--stop-dir D] [scorer arguments]")
        return 2
    own, rest = _split(argv[1:])
    sample = own.get("sample")
    if argv[0] == "check":
        if rest:
            print("refused: check takes only --sample and --stop-dir")
            return 2
        stop_dir = own.get("stop_dir") or CHECK_STOP_DIR
        try:
            n = require_reading(sample, stop_dir=stop_dir)
            m = require_reading(sample, stop_dir=stop_dir, movement=True)
        except ReadingRefused as r:
            print("refused: " + r.message)
            return r.code
        print(json.dumps({"reading_check": "PASS", "cases": n, "movement_cases": m}))
        return 0
    stop_dir = own.get("stop_dir") or set_folder(rest)
    if argv[0] == "movement-score":
        return run_movement_score(rest, sample=sample, stop_dir=stop_dir)
    return run_score(rest, sample=sample, stop_dir=stop_dir)


if __name__ == "__main__":
    raise SystemExit(main())
