#!/usr/bin/env python3
"""Checks 697, 698 and 699 (NEG-READING-A, beta item 18, #326; D-929, D-930): the negotiation scorers' reading
self-check and oddity alarm (tools/neg_reading_check.py), and the launch chain's refusal of a measurement folder
without its own reading check that runs and passes (tools/loop/launch_chain.py).

697, the advisor scorer (tools/score_neg_advisor.py, not edited), on the invented item of
config/neg_reading_sample.json (no real item, key or reply, no model, nothing launched):
  1. the shipped sample reads right: every case's M1, M4 and M10 rows and answered count are the known ones;
  2. a sample with a wrong number (an answered count, an M4 row) stops: `check --sample` exits EXIT_READING with a
     stop text naming the case, and a missing or malformed sample does the same;
  3. reader faults stop: the score-time reader made to drop every stance, or to read reject as accept;
  4. the oddity alarm counts reading reasons only: exactly half not answered is scored; over half (no reply, no
     stance) leaves a comparison arm out with "okuma hatası olabilir", or refuses the score for the system arm
     (EXIT_ODD); a D-931-like arm whose every entry the reader lost (no_piece with no piece) trips it; a system
     arm whose every piece was withheld by its audit does not, nor a piece the system's Python step wrote;
  5. with nothing tripped every figure is report()'s own;
  6. the real score_neg_advisor main(["score", ...]) on a fixture set folder under the guard (refuse() spied
     and let through, since its committed openings, freeze and power records are proven by their own checks;
     report() spied): the reading check runs first, a clean score prints report()'s figures with
     reading_check PASS, and a wrong sample or a system arm over half writes no score; --set=PATH sets the stop
     folder.
Neutralised eight times, each must fail, restored and passing again.

698, on fixture launch folders in a temporary directory (no launch.py run, no ledger read): a chain.json declaring
"measurement": true loads only when "reading_check" names a non-empty Python file of the folder; that file is
run before every launch of the folder's steps (launch_step, its other calls replaced by fixtures) and must exit 0
with PASS on its last line, else the step is held as a failed preflight; a chain.json not declaring it loads and
launches as before. Neutralised four times.

699, the movement scorer (tools/score_negotiation.py, not edited): its reading check (reply texts through
reread_replies.negotiation_rows and reply_answers, gap rows through system_label) holds on the sample, stops on a
wrong label and on a reader fault; the alarm counts rows held as no_answer, not rows an arm lacks; the system over
half refuses, B1 over half is left out; with nothing tripped report()'s figures are unchanged. Neutralised three
times.
"""
from __future__ import annotations

import contextlib
import copy
import inspect
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "tools" / "loop"),
           str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from effect_proof import prove_effect  # noqa: E402
import neg_reading_check as nrc  # noqa: E402

sc = nrc.scorer()
sn = nrc.movement_scorer()
rr = sc.rr
RESAMPLES = 50
KW = dict(resamples=RESAMPLES, article_link=False, audit_marked=True)


@contextlib.contextmanager
def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


def with_source(module, name, old, new):
    """`module.name` with one passage of its own source changed, as a neutralisation."""
    source = inspect.getsource(getattr(module, name))
    assert source.count(old) == 1, old
    space = dict(vars(module))
    exec(source.replace(old, new), space)
    return patched(module, name, space[name])


def _stop_texts(folder):
    out = []
    for p in Path(folder).glob(nrc.STOP_PREFIX + "*"):
        text = p.read_text(encoding="utf-8")
        out.append(p.stem[len(nrc.STOP_PREFIX):] + (":warning" if nrc.WARNING in text else "")
                   + (":reading" if nrc.READING_FAILED in text else ""))
    return sorted(out)


def _cli(argv):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        code = nrc.main(argv)
    return code, out.getvalue()


# ---------------------------------------------------------------- 697

def _sample():
    return nrc.load_sample()


def _texts():
    """{name: reply text} from the shipped sample's cases (the fixture replies, invented)."""
    cases = {c["name"]: c for c in _sample()["cases"]}
    return {"full": cases["full reply, every proposal with its stance"]["text"],
            "nostance": cases["one stance missing"]["text"], "none": "",
            "keyed": cases["proposals as an object keyed by id (not a form the reader takes: nothing read)"]["text"],
            "unknown": cases["one unknown proposal id, the system arm"]["text"]}


def _builds():
    build = nrc.sample_build(_sample(), sc)
    other = copy.deepcopy(build)
    other["item_id"] = build["item_id"] + "-b"
    return build, other


def _set():
    """Two invented items (the sample's build and a copy under another id) and their keys."""
    items, keys = {}, {}
    for b in _builds():
        item, key = sc.build_item(copy.deepcopy(b))
        items[item["item_id"]], keys[item["item_id"]] = item, key
    return items, keys


def _answers(items, group, texts):
    config = sc.na.load_config(sc.na.CONFIG_PATH)
    prompts = [{"prompt_id": "p-%s" % i, "group": group, "form": "advice", "item_id": i, "item": items[i]}
               for i in sorted(items)]
    return rr.advisor_rows({"config": config, "_sha256": "fixture", "prompts": prompts},
                           {"p-%s" % i: texts[i] for i in sorted(items)})


def _arms(items, system, b1):
    """arms of report(): each arm's two items' reply kinds, in item order."""
    ids = sorted(items)
    t = _texts()
    return {"system": (_answers(items, "system_advice", dict(zip(ids, (t[k] for k in system)))), "system_advice"),
            "B1": (_answers(items, "b1", dict(zip(ids, (t[k] for k in b1)))), "b1")}


def _checked(items, keys, arms, **over):
    with tempfile.TemporaryDirectory() as td:
        try:
            rep = nrc.checked_report(items, keys, arms, stop_dir=td, **dict(KW, **over))
            out = {"arms": sorted(rep["figures"]), "alarm": sorted(rep.get("reading_alarm") or {}),
                   "missed": {a: [v["not_answered_for_reading"], v["rows"]] for a, v in rep["answered_rows"].items()}}
        except nrc.ReadingRefused as r:
            out = {"refused": r.code, "warning": nrc.WARNING in r.message}
        out["stops"] = _stop_texts(td)
    return out


def _sample_file(folder, change):
    sample = _sample()
    change(sample)
    path = Path(folder) / "sample.json"
    path.write_text(json.dumps(sample), encoding="utf-8")
    return path


def _bad_count(s):
    s["cases"][4]["answered"] += 1          # "one stance missing": 3 of 3 is a wrong number


def _bad_m4(s):
    s["cases"][0]["expect"]["M4"] = {"hit": 2, "miss": 1}


def _check_with(folder, sample_path):
    stops = Path(folder) / "stops"
    code, text = _cli(["check", "--sample=%s" % sample_path, "--stop-dir", str(stops)])
    return {"exit": code, "stops": _stop_texts(stops) if stops.is_dir() else []}


def _strip(rep):
    return json.dumps({k: v for k, v in rep.items() if k not in ("reading_check", "answered_rows")},
                      sort_keys=True, default=str)


def _fixture_set(root, system, b1):
    """A set folder score_neg_advisor's main reads (build_set of the two invented builds) and its answer files."""
    for b in _builds():
        (root / "build" / b["item_id"]).mkdir(parents=True)
        (root / "build" / b["item_id"] / "build.json").write_text(json.dumps(b), encoding="utf-8")
        (root / "build" / b["item_id"] / "SOURCE.md").write_text("fixture source, invented\n", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        sc.build_set(root, count=lambda user: len(user.split()))
    items = sc.na.read_items(root)
    arms = _arms(items, system, b1)
    files = {}
    for name, value in (("system", arms["system"][0]), ("b1", arms["B1"][0]), ("cloud", arms["B1"][0]),
                        ("judge", {"rows": []}), ("configuration", {})):
        files[name] = root.parent / ("%s.json" % name)
        files[name].write_text(json.dumps(value), encoding="utf-8")
    (root / sc.SUBSET_FILE).write_text(json.dumps({"items": sorted(items)}), encoding="utf-8")
    return files


def _real_main(system, b1, sample=None, set_eq=False):
    """score_neg_advisor main(["score", ...]) behind run_score; refuse() and report() spied."""
    calls = {"refuse": 0, "report": 0}
    real_report = sc.report

    def refuse_spy(**kw):
        calls["refuse"] += 1
        return None

    def report_spy(*a, **k):
        calls["report"] += 1
        return real_report(*a, **k)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "set"
        files = _fixture_set(root, system, b1)
        argv = (["--set=%s" % root] if set_eq else ["--set", str(root)]) + [
            "--configuration", str(files["configuration"]), "--k", "1", "--system", str(files["system"]),
            "--b1", str(files["b1"]), "--cloud", str(files["cloud"]), "--judge", str(files["judge"])]
        with patched(sc, "refuse", refuse_spy), patched(sc, "report", report_spy), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = nrc.main(["score"] + argv + ([] if sample is None else ["--sample", str(sample)]))
        text = out.getvalue()
        printed = None
        if text.lstrip().startswith("{"):
            rep = json.loads(text)
            printed = {"reading_check": rep["reading_check"]["status"], "figure_arms": sorted(rep["figures"])}
        stops = _stop_texts(root)
    return {"exit": code, "refuse_called": calls["refuse"], "report_calls": calls["report"], "printed": printed,
            "stops": stops}


def observe_697():
    items, keys = _set()
    out = {"sample_bad": [b[0] for b in nrc.reading_check()]}
    with tempfile.TemporaryDirectory() as td:
        out["wrong_count"] = _check_with(td, _sample_file(td, _bad_count))
    with tempfile.TemporaryDirectory() as td:
        out["wrong_m4"] = _check_with(td, _sample_file(td, _bad_m4))
    with tempfile.TemporaryDirectory() as td:
        out["missing_sample"] = _check_with(td, Path(td) / "absent.json")
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        out["malformed_sample"] = _check_with(td, bad)
    original = rr.advice

    def no_stance(text, item):
        reply, drops = original(text, item)
        if reply and "proposals" in reply:
            reply = dict(reply, proposals={p: {k: v for k, v in e.items() if k != "stance"}
                                           for p, e in reply["proposals"].items()})
        return reply, drops

    def swapped(text, item):
        reply, drops = original(text, item)
        if reply and "proposals" in reply:
            reply = dict(reply, proposals={p: dict(e, stance="accept") if e.get("stance") == "reject" else e
                                           for p, e in reply["proposals"].items()})
        return reply, drops
    with patched(rr, "advice", no_stance):
        out["reader_drops_stances"] = len(nrc.reading_check())
    with patched(rr, "advice", swapped):
        out["reader_swaps_reject"] = len(nrc.reading_check())
    out["half"] = _checked(items, keys, _arms(items, ("full", "full"), ("none", "full")))
    out["over_half_b1"] = _checked(items, keys, _arms(items, ("full", "nostance"), ("none", "nostance")))
    out["over_half_system"] = _checked(items, keys, _arms(items, ("none", "nostance"), ("full", "full")))
    # D-931-like: every B1 entry lost by the reader (no_piece, no piece at all) trips the alarm.
    out["d931_like_no_piece"] = _checked(items, keys, _arms(items, ("full", "full"), ("keyed", "keyed")))
    # every system piece withheld by its audit (audit_marked off): the system's choice, not a reading error.
    withheld = _arms(items, ("full", "full"), ("full", "full"))
    for row in withheld["system"][0]["rows"]:
        row["audit"] = {pid: sc.WITHHELD_AUDIT for pid in (row.get("reply") or {}).get("proposals") or {}}
    out["over_half_withheld"] = _checked(items, keys, withheld, audit_marked=False)
    # the system's Python step fills the proposal the reader lost (no applicable position): not counted.
    out["python_piece_not_counted"] = _checked(items, keys, _arms(items, ("unknown", "unknown"), ("full", "full")))
    out["withheld_rows"] = sum(n for parts in sc.report(items, keys, {"system": withheld["system"]},
                                                        **dict(KW, audit_marked=False))["_per_item"]["system"].values()
                               for k, n in (parts.get("M10m") or {}).items() if k == "withheld")
    arms = _arms(items, ("full", "nostance"), ("nostance", "full"))
    with tempfile.TemporaryDirectory() as td:
        out["same_figures"] = _strip(nrc.checked_report(items, keys, arms, stop_dir=td, **KW)) == _strip(
            sc.report(items, keys, arms, **KW))
    out["main_clean"] = _real_main(("full", "nostance"), ("full", "full"), set_eq=True)
    out["main_system_over_half"] = _real_main(("none", "nostance"), ("full", "full"))
    with tempfile.TemporaryDirectory() as td:
        out["main_wrong_sample"] = _real_main(("full", "full"), ("full", "full"), sample=_sample_file(td, _bad_count))
    out["stop_dir_of_set_eq"] = nrc.set_folder(["--k", "1", "--set=X/set"]) == "X/set"
    out["check_stop_dir"] = nrc.CHECK_STOP_DIR.relative_to(ROOT).as_posix()
    return out


def expected_697():
    reading = {"exit": nrc.EXIT_READING, "stops": ["reading:reading"]}
    cases = len(_sample()["cases"])
    return {"sample_bad": [], "wrong_count": reading, "wrong_m4": reading, "missing_sample": reading,
            "malformed_sample": reading, "reader_drops_stances": 10, "reader_swaps_reject": 6,
            "half": {"arms": ["B1", "system"], "alarm": [], "missed": {"B1": [3, 6], "system": [0, 6]}, "stops": []},
            "over_half_b1": {"arms": ["system"], "alarm": ["B1"], "missed": {"B1": [4, 6], "system": [1, 6]},
                             "stops": ["odd_B1:warning"]},
            "over_half_system": {"refused": nrc.EXIT_ODD, "warning": True, "stops": ["odd_system:warning"]},
            "d931_like_no_piece": {"arms": ["system"], "alarm": ["B1"], "missed": {"B1": [6, 6], "system": [0, 6]},
                                   "stops": ["odd_B1:warning"]},
            "over_half_withheld": {"arms": ["B1", "system"], "alarm": [], "missed": {"B1": [0, 6], "system": [0, 6]},
                                   "stops": []},
            "withheld_rows": 6,
            "python_piece_not_counted": {"arms": ["B1", "system"], "alarm": [], "missed": {"B1": [0, 6], "system": [0, 6]},
                                         "stops": []},
            "same_figures": True,
            "main_clean": {"exit": 0, "refuse_called": 1, "report_calls": cases + 1,
                           "printed": {"reading_check": "PASS", "figure_arms": ["B1", "cloud", "system"]}, "stops": []},
            "main_system_over_half": {"exit": nrc.EXIT_ODD, "refuse_called": 1, "report_calls": cases + 1,
                                      "printed": None, "stops": ["odd_system:warning"]},
            "main_wrong_sample": {"exit": nrc.EXIT_READING, "refuse_called": 1, "report_calls": cases,
                                  "printed": None, "stops": ["reading:reading"]},
            "stop_dir_of_set_eq": True, "check_stop_dir": "output/neg_reading_check"}


def neutralisers_697():
    return [
        ("the reading check is consulted before any figure", lambda: patched(nrc, "reading_check", lambda *a, **k: [])),
        ("a case read with other rows or counts is a failed case", lambda: with_source(
            nrc, "reading_check", "if got != want:", "if False:")),
        ("more than half not answered trips the alarm", lambda: patched(nrc, "odd_alarm", lambda n, t: False)),
        ("a withheld piece is not counted for the alarm", lambda: patched(
            nrc, "READING_REASONS", nrc.READING_REASONS + ("withheld",))),
        ("an entry the reader lost (no_piece) is counted for the alarm", lambda: patched(
            nrc, "READING_REASONS", tuple(r for r in nrc.READING_REASONS if r != "no_piece"))),
        ("a piece Python wrote is not counted for the alarm", lambda: with_source(
            nrc, "reading_misses", "if why == \"no_piece\" and piece is not None and piece.get(\"written_by\") == sc.PYTHON:",
            "if False:")),
        ("a comparison arm over half is left out of the report", lambda: with_source(
            nrc, "checked_report", "rep = report(items, keys, {a: v for a, v in arms.items() if a not in odd}, **kw)",
            "pass")),
        ("the system arm over half refuses the whole score", lambda: with_source(
            nrc, "_alarm", "if SYSTEM in odd or (odd and len(odd) == len(arms)):", "if False:")),
    ]


# ---------------------------------------------------------------- 698

def _lc():
    import launch_chain
    return launch_chain


PASSING = "print('reading check: 3 of 3')\nprint('PASS')\n"
FAILING = "import sys\nprint('FAIL')\nsys.exit(1)\n"
SILENT = "x = 1\n"
CHAIN = {"chain": 1, "steps": [{"step": "seal", "kind": "ledger", "purpose": "fixture-seal"}]}
VARIANTS = (("not declared", {}, None), ("declared false", {"measurement": False}, None),
            ("measurement with its reading check", {"measurement": True, "reading_check": "reading_check.py"},
             ("reading_check.py", PASSING)),
            ("measurement naming no reading check", {"measurement": True}, None),
            ("measurement naming a missing file", {"measurement": True, "reading_check": "reading_check.py"}, None),
            ("measurement naming a folder", {"measurement": True, "reading_check": "rc"}, ("rc/", "")),
            ("measurement naming an empty file", {"measurement": True, "reading_check": "reading_check.py"},
             ("reading_check.py", "")),
            ("measurement naming a text file", {"measurement": True, "reading_check": "reading_check.txt"},
             ("reading_check.txt", PASSING)),
            ("measurement naming an absolute path", {"measurement": True, "reading_check": "C:/rc.py"}, None),
            ("measurement naming a .. path", {"measurement": True, "reading_check": "../rc.py"}, None),
            ("measurement not a boolean", {"measurement": "yes", "reading_check": "reading_check.py"},
             ("reading_check.py", PASSING)),
            ("measurement whose check fails", {"measurement": True, "reading_check": "reading_check.py"},
             ("reading_check.py", FAILING)),
            ("measurement whose check prints no PASS", {"measurement": True, "reading_check": "reading_check.py"},
             ("reading_check.py", SILENT)))


def _launch(lc, folder, chain):
    """launch_step on the fixture folder with preflight passing, no archive problem and the ledger lock held
    after it (so a step that passes every check is deferred, never launched): the trace actions."""
    traced, waits = [], []
    step = copy.deepcopy(chain["steps"][0])

    def wait(*a, **k):
        waits.append(True)
        return len(waits) == 1          # free before preflight, held after it
    with patched(lc, "call_launch", lambda *a, **k: (0, "", "")), patched(lc, "archive_problems", lambda f: None), \
            patched(lc, "wait_ledger_lock", wait), \
            patched(lc.mc, "trace", lambda name, action, **k: traced.append(action)), \
            patched(lc.mc, "alert", lambda *a, **k: None):
        started = lc.launch_step(folder, step, {}, chain)
    return {"started": started, "traced": traced}


def observe_698():
    lc = _lc()
    out = {}
    with tempfile.TemporaryDirectory() as td:
        for n, (name, extra, made) in enumerate(VARIANTS):
            folder = Path(td) / ("F%d" % n)
            folder.mkdir()
            (folder / "launch.py").write_text("PURPOSES = {'seal': 'fixture-seal'}\n", encoding="utf-8")
            (folder / "chain.json").write_text(json.dumps(dict(CHAIN, **extra)), encoding="utf-8")
            if made and made[0].endswith("/"):
                (folder / made[0].rstrip("/")).mkdir()
            elif made:
                (folder / made[0]).write_text(made[1], encoding="utf-8")
            try:
                chain = lc.load_chain(folder)
            except lc.ChainError as exc:
                out[name] = "refused" + (" (NEG-READING-A)" if "NEG-READING-A" in str(exc) else "")
                continue
            launch = _launch(lc, folder, chain)
            out[name] = "held" if "preflight_failed" in launch["traced"] else (
                "would launch" if "deferred" in launch["traced"] else "other: %s" % launch)
    return out


def expected_698():
    return {"not declared": "would launch", "declared false": "would launch",
            "measurement with its reading check": "would launch",
            "measurement naming no reading check": "refused (NEG-READING-A)",
            "measurement naming a missing file": "refused (NEG-READING-A)",
            "measurement naming a folder": "refused (NEG-READING-A)",
            "measurement naming an empty file": "refused (NEG-READING-A)",
            "measurement naming a text file": "refused (NEG-READING-A)",
            "measurement naming an absolute path": "refused", "measurement naming a .. path": "refused",
            "measurement not a boolean": "refused",
            "measurement whose check fails": "held", "measurement whose check prints no PASS": "held"}


def neutralisers_698():
    lc = _lc()
    return [
        ("load_chain checks the reading check", lambda: patched(lc, "check_reading_check", lambda folder, chain: None)),
        ("the reading check must be a non-empty file of the folder", lambda: with_source(
            lc, "check_reading_check", "or path.stat().st_size == 0", "")),
        ("the reading check is run before every launch", lambda: with_source(
            lc, "launch_step", "    reading = reading_check_problem(folder, chain)\n", "    reading = None\n")),
        ("its last line must say PASS", lambda: with_source(
            lc, "reading_check_problem", "if done.returncode != 0 or 'PASS' not in last:", "if done.returncode != 0:")),
    ]


# ---------------------------------------------------------------- 699

KEYS6 = [{"case_id": "c%d" % (i // 3), "issue_id": "i%d" % i, "rounds": [1, 2], "label": lab}
         for i, lab in enumerate(["moved_toward", "moved_away", "unchanged_from_prior"] * 2)]
SUBSETS = {"c0": "F", "c1": "F"}


def _labels(kinds):
    """{key: label} from one kind per key row: 'right' the key's label, 'unread' no_answer, 'absent' no row."""
    out = {}
    for r, kind in zip(KEYS6, kinds):
        k = (r["case_id"], r["issue_id"], tuple(r["rounds"]))
        if kind == "right":
            out[k] = r["label"]
        elif kind == "unread":
            out[k] = sn.NO_ANSWER
    return out


def _movement(system, b1):
    with tempfile.TemporaryDirectory() as td:
        try:
            rep = nrc.checked_movement_report(KEYS6, {"system": _labels(system), "B1": _labels(b1)}, SUBSETS, 1,
                                              stop_dir=td, resamples=RESAMPLES)
            out = {"arms": sorted(rep["arms"]), "alarm": sorted(rep.get("reading_alarm") or {})}
        except nrc.ReadingRefused as r:
            out = {"refused": r.code}
        out["stops"] = _stop_texts(td)
    return out


def observe_699():
    out = {"sample_bad": [b[0] for b in nrc.movement_check()]}
    sample = _sample()
    sample["movement"]["replies"][0]["label"] = "moved_away"
    out["wrong_label"] = [b[0] for b in nrc.movement_check(sample)]
    with patched(rr, "movement", lambda reply, config: (sn.NO_ANSWER, "fixture")):
        out["reader_fault"] = len(nrc.movement_check())
    right, half = ["right"] * 6, ["unread"] * 3 + ["right"] * 3
    over = ["unread"] * 4 + ["right"] * 2
    out["half"] = _movement(right, half)
    out["over_half_b1"] = _movement(right, over)
    out["over_half_system"] = _movement(over, right)
    out["absent_not_reading"] = _movement(right, ["absent"] * 6)
    arms = {"system": _labels(right), "B1": _labels(half)}
    with tempfile.TemporaryDirectory() as td:
        out["same_figures"] = _strip(nrc.checked_movement_report(KEYS6, arms, SUBSETS, 1, stop_dir=td,
                                                                 resamples=RESAMPLES)) == _strip(
            sn.report(KEYS6, arms, SUBSETS, 1, resamples=RESAMPLES))
    return out


def expected_699():
    return {"sample_bad": [], "wrong_label": ["a declared answer"], "reader_fault": 4,
            "half": {"arms": ["B1", "system"], "alarm": [], "stops": []},
            "over_half_b1": {"arms": ["system"], "alarm": ["B1"], "stops": ["odd_B1:warning"]},
            "over_half_system": {"refused": nrc.EXIT_ODD, "stops": ["odd_system:warning"]},
            "absent_not_reading": {"arms": ["B1", "system"], "alarm": [], "stops": []},
            "same_figures": True}


def neutralisers_699():
    return [
        ("a reply read with another label is a failed case", lambda: with_source(
            nrc, "movement_check", "if read.get((\"rc-case\", \"rc-%d\" % i, (1, 2))) != c[\"label\"]]", "if False]")),
        ("rows held as no_answer trip the alarm", lambda: patched(nrc, "odd_alarm", lambda n, t: False)),
        ("a row an arm lacks is not a reading error", lambda: with_source(
            nrc, "checked_movement_report", "if x in labels and labels[x] == sn.NO_ANSWER",
            "if labels.get(x, sn.NO_ANSWER) == sn.NO_ANSWER")),
    ]


PROOFS = {697: (observe_697, expected_697, neutralisers_697), 698: (observe_698, expected_698, neutralisers_698),
          699: (observe_699, expected_699, neutralisers_699)}
SAYS = {697: "the advisor scorer reads a known sample first (M1, M4, M10 rows and counts) and stops on any difference "
             "or a bad sample; over half not answered for a reading reason is 'okuma hatası olabilir' and no score; "
             "otherwise report()'s figures unchanged, also through the real main",
        698: "a launch folder declaring a measurement is refused whole without a non-empty Python reading check, and "
             "held unless that check runs and prints PASS before each launch",
        699: "the movement scorer reads a known sample first and stops on a wrong label; over half held unread is "
             "'okuma hatası olabilir' and no score"}


def run_check(number):
    observe, expected, neutralisers = PROOFS[number]
    want = json.dumps(expected(), sort_keys=True)
    names = []
    for name, neutralise in neutralisers():
        prove_effect(name=name, validate=lambda: nrc.SAMPLE_PATH.is_file(), observe=observe,
                     check=lambda: ("PASS" if json.dumps(observe(), sort_keys=True) == want else "FAIL", name),
                     neutralise=neutralise)
        names.append(name)
    return "PASS", "%d proofs, each neutralise, fail, restore, pass: %s (%s)" % (len(names), SAYS[number], "; ".join(names))


if __name__ == "__main__":
    numbers = [int(a) for a in sys.argv[1:] if a.isdigit()] or sorted(PROOFS)
    for number in numbers:
        if "--show" in sys.argv:
            print(number, json.dumps(PROOFS[number][0](), indent=1, sort_keys=True, default=str))
            continue
        print(number, json.dumps(run_check(number)))
