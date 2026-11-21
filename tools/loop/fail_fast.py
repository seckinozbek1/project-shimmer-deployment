#!/usr/bin/env python3
"""In-run early stop for a negotiation part (D-873 fail-fast, D-888, Seckin G-20261121-0735).

One importable decision, called by every launch folder's watch.py (never copied per folder). It reads the run's own
counts, never a reply, a label or an item: the live view's snapshot (tools/ordinary_final_live.py snapshot_for, which
reads the instance's per-call records and sends only ids, outcomes and times) gives one row per finished model call
with its status (passed, refused, out_of_memory, crashed) and its `doc_id` (the item the call belongs to).

What counts, all from those rows:
- returned items: the distinct doc_ids with a finished call; while the part is running the item with the latest
  finished call may still be in progress, so it is left out until the part's declared item count is reached or the
  run is no longer growing (`finished` true).
- an item with no answer: a returned item none of whose calls passed (every call refused, crashed or out of memory).
- form failure: the share of refused calls among finished calls above `refusal_share` (the plan's bar line 5 limit,
  0.10, tools/score_neg_advisor.py NEG_BAR_DROP_SHARE), or crashed and out-of-memory calls above `crash_share`.

When it looks: first after `first_items` returned items (3), then each time `interval_items` more have returned (6).
It stops the part when, at a look, the no-answer items are above `no_answer_share` (0.05) of the returned items or the
first `first_items` items all returned no answer, or a form failure holds. The stop is the existing watch stop path:
`launch.py stop <part>` writes TERMINATE_REQUEST in the part's run folder, the controller's own termination follows
(the instance's STOP_WORKLOAD and terminate, the evidence downloaded, the spend written to the budget ledger by the
controller). Beside it this module writes FAIL_FAST_<part>.json in the launch folder (reason, counts, the look time)
and, once the part has ended, the cost read from the ledger through the folder's own launch.costs().

Nothing here writes under docs/loop/private; the lead copies the reason into its own ledger line. No model, no key.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

FIRST_ITEMS = 3
INTERVAL_ITEMS = 6
NO_ANSWER_SHARE = 0.05
REFUSAL_SHARE = 0.10
CRASH_SHARE = 0.05
STATUS_FILE = "FAIL_FAST_%s.json"
BLIND_ROWS = 30


def _rows(snapshot):
    return [r for r in (snapshot or {}).get("rows") or [] if r.get("finished_epoch") is not None or "status" in r]


def returned_items(snapshot, total_items=None, finished=False):
    """{doc_id: [statuses of its finished calls]} for the items that have returned (see the module text)."""
    by_doc = {}
    for r in sorted(_rows(snapshot), key=lambda r: (r.get("finished_epoch") or 0, r.get("sequence") or 0)):
        if r.get("doc_id"):          # a record with no item id (a group-level record) belongs to no item
            by_doc.setdefault(r["doc_id"], []).append(r.get("status"))
    if not by_doc:
        return {}
    in_progress = list(by_doc)[-1]
    if finished or (total_items is not None and len(by_doc) >= total_items):
        return by_doc
    return {d: s for d, s in by_doc.items() if d != in_progress}


def decide(snapshot, *, total_items=None, finished=False, checked=0, first_items=FIRST_ITEMS,
           interval_items=INTERVAL_ITEMS, no_answer_share=NO_ANSWER_SHARE, refusal_share=REFUSAL_SHARE,
           crash_share=CRASH_SHARE):
    """The decision of one look at a snapshot: {'due', 'stop', 'reasons', 'returned', 'no_answer_items', 'calls',
    'refused', 'crashed'}. `checked` is the returned count at the last look (0 before the first)."""
    items = returned_items(snapshot, total_items, finished)
    returned = len(items)
    statuses = [s for v in items.values() for s in v]
    calls = len(statuses)
    refused = sum(1 for s in statuses if s == "refused")
    crashed = sum(1 for s in statuses if s in ("crashed", "out_of_memory"))
    empty = sum(1 for v in items.values() if v and "passed" not in v)
    out = {"due": False, "stop": False, "reasons": [], "returned": returned, "no_answer_items": empty,
           "calls": calls, "refused": refused, "crashed": crashed,
           "blind": len(_rows(snapshot)) >= BLIND_ROWS and not any(r.get("doc_id") for r in _rows(snapshot))}   # many calls, none with an item id: no look possible
    if returned < first_items or (checked and returned < checked + interval_items):
        return out
    out["due"] = True
    if empty and empty == returned and returned <= first_items:
        out["reasons"].append("the first %d items all returned no answer" % returned)
    elif empty / returned > no_answer_share:
        out["reasons"].append("%d of %d returned items returned no answer (%.1f percent, limit %.0f percent)"
                              % (empty, returned, 100 * empty / returned, 100 * no_answer_share))
    if calls and refused / calls > refusal_share:
        out["reasons"].append("form: %d of %d calls refused (%.1f percent, limit %.0f percent)"
                              % (refused, calls, 100 * refused / calls, 100 * refusal_share))
    if calls and crashed / calls > crash_share:
        out["reasons"].append("form: %d of %d calls crashed or ran out of memory (limit %.0f percent)"
                              % (crashed, calls, 100 * crash_share))
    out["stop"] = bool(out["reasons"])
    return out


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def finalize(folder, part, cost):
    """Once a stopped part has ended, its cost (the launch folder's own costs(), read from the budget ledger the
    controller wrote) is added to FAIL_FAST_<part>.json, once. Returns the state."""
    path = Path(folder) / (STATUS_FILE % part)
    state = _load(path)
    if state.get("stopped") and cost is not None and "cost_usd" not in state:
        spent, phase = cost()
        if phase == "ended":
            state["cost_usd"] = spent
            path.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    return state


def look(folder, part, snapshot, *, total_items=None, finished=False, request_stop, cost=None, now=time.time,
         **limits):
    """One look at `snapshot` for `part` of the launch `folder`. State is kept in FAIL_FAST_<part>.json (the count at
    the last look, the looks so far, and the stop with its reason). `request_stop()` is called once, on a stop,
    and is the folder's own `launch.py stop <part>`. Returns the decision, or None when no look was due or the part
    was already stopped."""
    path = Path(folder) / (STATUS_FILE % part)
    state = _load(path)
    if state.get("stopped"):
        finalize(folder, part, cost)
        return None
    decision = decide(snapshot, total_items=total_items, finished=finished, checked=state.get("checked", 0), **limits)
    if decision["blind"] and not state.get("blind"):
        state["blind"] = "records carry no item id: the early stop cannot look (counted, never a stop)"
        path.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    if not decision["due"]:
        return None
    state.setdefault("looks", []).append({"time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now())),
                                          **{k: decision[k] for k in ("returned", "no_answer_items", "calls",
                                                                      "refused", "crashed", "stop")}})
    state["checked"] = decision["returned"]
    if decision["stop"]:
        state.update(stopped=True, part=part, reasons=decision["reasons"], counts_only=True)
        path.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
        request_stop()
    else:
        path.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    return decision


def watch_look(launch, part, snapshot_of=None):
    """The folder's watch.py hook: one look for `part` of the imported launch module. `snapshot_of(folder)` defaults
    to the live view's reading of the part's run folder; a failed reading is no look (never a stop)."""
    if part not in getattr(launch, "PARTS", {}):
        return None            # the seal step reads no items
    if _load(Path(launch.HERE) / (STATUS_FILE % part)).get("stopped"):
        finalize(launch.HERE, part, lambda: launch.costs()[part])
        return None            # stopped already: no reading of an ended run, only its cost
    folder = launch.run_folder(part)
    try:
        if snapshot_of is None:
            sys.path[:0] = [str(launch.WT / "tools")]
            import ordinary_final_live as live
            snapshot = live.snapshot_for(folder)
        else:
            snapshot = snapshot_of(folder)
    except Exception:
        return None
    if not snapshot or not snapshot.get("readable", True):
        return None
    done = snapshot.get("workload_exit_code") is not None
    return look(launch.HERE, part, snapshot, total_items=launch.PARTS[part]["items"], finished=done,
                request_stop=lambda: launch.main(["stop", part]), cost=lambda: launch.costs()[part])


def watch(launch, step, *, look_seconds=60, status_seconds=300, hours=4, sleep=time.sleep, now=time.time,
          snapshot_of=None):
    """The whole of a launch folder's watch.py (which only imports and calls this): every `look_seconds` the step's
    cost and phase are read from the folder's launch module; every `status_seconds` its `status` is appended to
    watch.log; the step is stopped at 90 percent of its guard cap (launch.guard_figures, as before); while a part
    runs, the in-run early stop looks (watch_look); it ends when the step has ended (the stopped part's cost is then
    written to FAIL_FAST_<part>.json) or after `hours`."""
    import contextlib
    import io
    if step not in launch.PURPOSES:
        raise SystemExit("unknown step %r; steps: %s" % (step, ", ".join(launch.PURPOSES)))
    stop_at = launch.guard_figures(step)[2]
    log = Path(launch.HERE) / "watch.log"

    def say(text):
        with log.open("a", encoding="utf-8") as f:
            f.write(text + "\n")

    start, asked, last = now(), False, None
    while now() - start < hours * 3600:
        spent, state = launch.costs()[step]
        if last is None or now() - last >= status_seconds:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                launch.main(["status"])
            say(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now())) + " [%s, stop at %.3f USD]\n" % (step, stop_at)
                + out.getvalue())
            last = now()
        if spent >= stop_at and state == "running" and not asked:
            launch.main(["stop", step])
            asked = True
            say("STOP requested at %.3f USD (90 percent of the cap)" % spent)
        if state == "running":
            watch_look(launch, step, snapshot_of)
        if state == "ended":
            watch_look(launch, step, snapshot_of)
            print("ended", step, launch.costs()[step])
            return "ended"
        sleep(look_seconds)
    return "timeout"
