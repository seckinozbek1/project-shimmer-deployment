#!/usr/bin/env python3
"""Proofs of tools/loop/fail_fast.py (the in-run early stop, D-873, D-888, Seckin G-20261121-0735).

On invented snapshots shaped like tools/ordinary_final_live.py snapshot_for's (one row per finished call with doc_id,
status and finished_epoch) and a fake launch module (run_folder, costs, main stop): no instance, no key, no model,
no real item.

  empty_run        a fake run whose replies are all empty (every call refused) stops the part: TERMINATE_REQUEST is
                   written through the folder's own stop, FAIL_FAST_<part>.json holds the reason and counts, a later
                   look stops nothing twice, and the cost is added once the part has ended
  good_run         a run of answered items with a few refused calls stops nothing and writes no stop
  not_due          under the first look's item count nothing is read as a decision
  interval         a look at 3 items, none again before 6 more have returned, a bad item among the next looks stops
  share_bar        1 empty item of 20 (5 percent) holds, 2 of 20 stops
  form_bar         every item answered but 20 percent of the calls refused stops, with the form reason
  in_progress      the item still running is not counted until the run has ended or the item count is reached
  unreadable       a snapshot the instance did not answer is no look and no stop

Each is run as built, with one line of the module neutralised (must fail), restored and run again (passes).
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "tools" / "loop"), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import fail_fast as ff  # noqa: E402
import reasoning_methods_checks as rmc  # noqa: E402

caught, with_source = rmc.caught, rmc.with_source


def snap(items, readable=True, exit_code=None):
    """items: [(doc_id, [statuses])] -> a snapshot_for-shaped dict."""
    rows, t = [], 1000.0
    for doc, statuses in items:
        for s in statuses:
            t += 3
            rows.append({"doc_id": doc, "status": s, "finished_epoch": t, "sequence": len(rows)})
    return {"rows": rows, "readable": readable, "workload_exit_code": exit_code}


def good(n, refused_every=0):
    return [("i%02d" % i, ["passed"] * 9 + (["refused"] if refused_every and i % refused_every == 0 else []))
            for i in range(n)]


def bad(n):
    return [("i%02d" % i, ["refused"] * 6) for i in range(n)]


class FakeLaunch:
    """What watch_look needs of a folder's launch module."""
    def __init__(self, folder):
        self.HERE, self.WT = Path(folder), Path(folder)
        self.PARTS = {"pilot": {"items": 24}}
        self.phase = "running"

    def run_folder(self, part):
        return self.HERE / ("run_" + part)

    def costs(self):
        return {"pilot": (0.42, self.phase)}

    def main(self, args):
        if args[0] == "stop":
            self.run_folder(args[1]).mkdir(exist_ok=True)
            (self.run_folder(args[1]) / "TERMINATE_REQUEST").touch()
        return 0


def _watch(items, **kw):
    with tempfile.TemporaryDirectory(prefix="ff_") as td:
        launch = FakeLaunch(td)
        out = {}
        first = ff.watch_look(launch, "pilot", snapshot_of=lambda f: snap(items, **kw))
        out["stop"] = bool(first and first["stop"])
        out["terminate"] = (launch.run_folder("pilot") / "TERMINATE_REQUEST").exists()
        state = json.loads((Path(td) / "FAIL_FAST_pilot.json").read_text(encoding="utf-8")) \
            if (Path(td) / "FAIL_FAST_pilot.json").exists() else {}
        out["reasons"] = state.get("reasons")
        out["looks"] = [(k["returned"], k["no_answer_items"]) for k in state.get("looks", [])]
        out["again"] = ff.watch_look(launch, "pilot", snapshot_of=lambda f: snap(items, **kw))
        launch.phase = "ended"
        ff.watch_look(launch, "pilot", snapshot_of=lambda f: snap(items, **kw))
        state = json.loads((Path(td) / "FAIL_FAST_pilot.json").read_text(encoding="utf-8")) \
            if (Path(td) / "FAIL_FAST_pilot.json").exists() else {}
        out["cost"] = state.get("cost_usd")
        return out


def observe_empty_run():
    return _watch(bad(5))


def expected_empty_run():
    return {"stop": True, "terminate": True,
            "reasons": ["4 of 4 returned items returned no answer (100.0 percent, limit 5 percent)",
                        "form: 24 of 24 calls refused (100.0 percent, limit 10 percent)"],
            "looks": [(4, 4)], "again": None, "cost": 0.42}


def observe_good_run():
    out = _watch(good(8, refused_every=4))
    out.pop("again")
    return out


def expected_good_run():
    return {"stop": False, "terminate": False, "reasons": None, "looks": [(7, 0)], "cost": None}


def observe_not_due():
    d = ff.decide(snap(bad(3)))     # three items in the file, the third still running: 2 returned
    return {"returned": d["returned"], "due": d["due"], "stop": d["stop"]}


def expected_not_due():
    return {"returned": 2, "due": False, "stop": False}


def observe_interval():
    seen = [ff.decide(snap(good(n)), checked=c) for n, c in ((4, 0), (5, 3), (8, 3), (10, 3))]
    last = ff.decide(snap(good(9) + [("b00", ["refused"] * 6), ("i99", ["passed"])]), checked=3)
    return {"due": [d["due"] for d in seen], "stop_at_bad_item": last["stop"], "returned": last["returned"]}


def expected_interval():
    return {"due": [True, False, False, True], "stop_at_bad_item": True, "returned": 10}


def observe_share_bar():
    one = good(20)
    one[10] = ("e1", ["refused"] * 3)         # one empty item of 20: 5 percent, not above the bar
    two = list(one)
    two[11] = ("e2", ["crashed"] * 3)         # two of 20: 10 percent
    d1 = ff.decide(snap(one), total_items=20)
    d2 = ff.decide(snap(two), total_items=20)
    return {"one": (d1["no_answer_items"], [r for r in d1["reasons"] if not r.startswith("form")]),
            "two": (d2["no_answer_items"], len([r for r in d2["reasons"] if not r.startswith("form")]))}


def expected_share_bar():
    return {"one": (1, []), "two": (2, 1)}


def observe_form_bar():
    d = ff.decide(snap([("i%02d" % i, ["passed"] * 4 + ["refused"]) for i in range(6)], exit_code=0), finished=True)
    return {"stop": d["stop"], "reasons": d["reasons"], "empty": d["no_answer_items"]}


def expected_form_bar():
    return {"stop": True, "reasons": ["form: 6 of 30 calls refused (20.0 percent, limit 10 percent)"], "empty": 0}


def observe_in_progress():
    running = good(4) + [("i04", ["refused"] * 2)]
    return {"running": ff.decide(snap(running))["no_answer_items"],
            "ended": ff.decide(snap(running, exit_code=0), finished=True)["no_answer_items"],
            "all_items": ff.decide(snap(running), total_items=5)["no_answer_items"]}


def expected_in_progress():
    return {"running": 0, "ended": 1, "all_items": 1}


def observe_unreadable():
    return _watch(bad(5), readable=False)["stop"], _watch(bad(5), readable=False)["terminate"]


def expected_unreadable():
    return False, False


class LoopLaunch(FakeLaunch):
    """A launch module whose ledger moves with the loop: not launched, running (at `rate` USD a look), ended once a
    stop was requested or after `steps` looks."""
    PURPOSES = {"seal": "s", "pilot": "p"}

    def __init__(self, folder, rate=0.1, steps=6):
        super().__init__(folder)
        self.n, self.rate, self.steps, self.stopped, self.log = -1, rate, steps, [], []

    def guard_figures(self, part):
        return (1.0, 1.5, 1.35)

    def costs(self):
        self.n += 1
        if self.n == 0:
            return {"pilot": (0.0, "not launched")}
        if self.stopped or self.n > self.steps:
            return {"pilot": (round(0.05 * self.n, 3), "ended")}
        return {"pilot": (round(self.rate * self.n, 3), "running")}

    def main(self, args):
        if args[0] == "stop":
            self.stopped.append(args[1])
        if args[0] == "status":
            print("status line")
        return 0


def _loop(items, rate=0.1):
    clock = [0.0]
    with tempfile.TemporaryDirectory(prefix="ffl_") as td:
        launch = LoopLaunch(td, rate=rate)
        result = ff.watch(launch, "pilot", sleep=lambda s: clock.__setitem__(0, clock[0] + s), now=lambda: clock[0],
                          snapshot_of=lambda f: snap(items))
        state = json.loads((Path(td) / "FAIL_FAST_pilot.json").read_text(encoding="utf-8")) \
            if (Path(td) / "FAIL_FAST_pilot.json").exists() else {}
        text = (Path(td) / "watch.log").read_text(encoding="utf-8")
        return {"result": result, "stopped": launch.stopped, "reason": bool(state.get("reasons")),
                "cost": state.get("cost_usd"), "status_lines": text.count("status line"),
                "cost_stop": "90 percent of the cap" in text}


def observe_watch_loop():
    return {"empty": _loop(bad(5)), "good": _loop(good(8)), "dear": _loop(good(8), rate=0.5)}


def expected_watch_loop():
    return {"empty": {"result": "ended", "stopped": ["pilot"], "reason": True, "cost": 0.15, "status_lines": 1,
                      "cost_stop": False},
            "good": {"result": "ended", "stopped": [], "reason": False, "cost": None, "status_lines": 2,
                     "cost_stop": False},
            "dear": {"result": "ended", "stopped": ["pilot"], "reason": False, "cost": None, "status_lines": 1,
                     "cost_stop": True}}


def observe_blind():
    """Many finished calls and none with an item id: no stop (nothing can be counted by item) but the state says so;
    records with no item id never count as an item; one long item is not blind."""
    anon = [("", ["refused"] * 40)]
    with tempfile.TemporaryDirectory(prefix="ffb_") as td:
        launch = FakeLaunch(td)
        first = ff.watch_look(launch, "pilot", snapshot_of=lambda f: snap(anon))
        state = json.loads((Path(td) / "FAIL_FAST_pilot.json").read_text(encoding="utf-8"))
        terminate = (launch.run_folder("pilot") / "TERMINATE_REQUEST").exists()
    return {"decision": first, "blind": bool(state.get("blind")), "terminate": terminate,
            "one_long_item": ff.decide(snap([("i00", ["passed"] * 40)]))["blind"],
            "items": len(ff.returned_items(snap(anon + good(4))))}


def expected_blind():
    return {"decision": None, "blind": True, "terminate": False, "one_long_item": False, "items": 3}


PROOFS = ("empty_run", "good_run", "not_due", "interval", "share_bar", "form_bar", "in_progress", "unreadable",
          "watch_loop", "blind")
NEUTRALISATIONS = {
    "no_stop": ((ff, "decide", 'out["stop"] = bool(out["reasons"])', 'out["stop"] = False'),
                ("empty_run", "interval", "form_bar")),
    "share_ignored": ((ff, "decide", "elif empty / returned > no_answer_share:", "elif False:"),
                      ("empty_run", "share_bar")),
    "form_ignored": ((ff, "decide", "if calls and refused / calls > refusal_share:", "if False:"),
                     ("empty_run", "form_bar")),
    "in_progress_counted": ((ff, "returned_items", "return {d: s for d, s in by_doc.items() if d != in_progress}",
                             "return by_doc"), ("in_progress", "not_due")),
    "interval_ignored": ((ff, "decide", "(checked and returned < checked + interval_items)", "False"),
                         ("interval",)),
    "first_ignored": ((ff, "decide", "if returned < first_items or", "if False or"), ("not_due",)),
    "loop_never_looks": ((ff, "watch", '        if state == "running":\n            watch_look(launch, step, snapshot_of)\n',
                         '        if state == "running":\n            pass\n'), ("watch_loop",)),
    "cost_not_written": ((ff, "finalize", 'state["cost_usd"] = spent', "pass"), ("empty_run", "watch_loop")),
    "cost_stop_dropped": ((ff, "watch", 'if spent >= stop_at and state == "running" and not asked:',
                           "if False:"), ("watch_loop",)),
    "anon_counted": ((ff, "returned_items", '        if r.get("doc_id"):', "        if True:"), ("blind",)),
    "blind_unflagged": ((ff, "look", 'if decision["blind"] and not state.get("blind"):', "if False:"), ("blind",)),
    "stop_not_requested": ((ff, "look", "        request_stop()\n", "        pass\n"), ("empty_run",)),
    "unreadable_looked": ((ff, "watch_look", 'if not snapshot or not snapshot.get("readable", True):',
                           "if not snapshot:"), ("unreadable",)),
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
            return "FAIL", "%s as built: %s" % (n, str(first[n])[:700])
        if again[n] != expected[n]:
            return "FAIL", "%s after restore: %s" % (n, str(again[n])[:400])
    for name, (_patch, proofs) in NEUTRALISATIONS.items():
        for n in proofs:
            if broken[name][n] == expected[n]:
                return "FAIL", "%s still passes when %s is neutralised" % (n, name)
    return "PASS", ("%d proofs, %d neutralisations, fail, restore, pass, no model: a fake run with empty replies "
                    "stops the part through the folder's stop (TERMINATE_REQUEST, FAIL_FAST file with reason, counts "
                    "and cost), a good fake run does not; looks at the first 3 items then each 6 more; the 5 percent "
                    "no-answer bar, the form bar, the item still in progress and an unreadable snapshot held (%s)"
                    % (len(PROOFS), len(NEUTRALISATIONS), ", ".join(PROOFS)))


if __name__ == "__main__":
    status, detail = run()
    print("fail_fast", status, detail)
    sys.exit(0 if status == "PASS" else 1)
