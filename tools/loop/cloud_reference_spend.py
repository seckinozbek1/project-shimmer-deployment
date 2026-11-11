#!/usr/bin/env python3
"""The cloud reference's spend store: one reader for the paid runners and the loop budget guard.

The store is `docs/loop/private/cloud_reference_spend.jsonl` of the MAIN checkout, found from git's
common directory (`store_path`), never from the working folder: the one path rule both the runners
and the guard use. It is created once, empty, by the operator; an absent or unreadable store is
never read as no spend.

Its lines, append-only:
  - a closed run: `spent_usd` (a line with no `event`, as the runs before D-401 wrote it, or
    `event: close`, which names the run's `run_id`);
  - `event: intent`: a paid run starting, written under the store's lock with its `cap_usd` before
    its first request; until a close line names its `run_id`, its cap counts as RUNNING, so two
    runs, or a run and a launch, can never both spend one dollar;
  - `event: handed_back`: a role C spend file appended by the lead (`append_handed_back`), with the
    file's digest; the file's own lines follow, each carrying `handed_back_sha256`.

Before role C runs, the lead opens an intent for it (`cloud_reference_b1.py open-role-c`), which holds
its cap as running; the append closes it, and refuses a line naming no such intent.
A role C run writes its spend line to a file of its own, which the lead drops into
`docs/loop/private/cloud_reference_handed_back/` and appends with `append-handed-back`. While a
file there has no `handed_back` line naming its digest, the lead side refuses its next paid run
and, through `lead_may_spend`, its next instance launch (D-401 item 11).

    py -3.12 -X utf8 tools/loop/cloud_reference_spend.py status
    py -3.12 -X utf8 tools/loop/cloud_reference_spend.py append-handed-back <file in the drop folder>

This module imports nothing from the guard, so the guard can import it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud_run_common import no_window  # noqa: E402  (HIDDEN-A: every tools/loop start has no window)

STORE_NAME = "cloud_reference_spend.jsonl"
HANDBACK_DIR_NAME = "cloud_reference_handed_back"
LINE_EVENTS = (None, "close", "intent", "handed_back", "ceiling", "reserve", "skipped")
# D-S121 (D-453), D-441: the API's own ceiling is read from the store's latest `ceiling` line
# ({"event": "ceiling", "time_utc", "ceiling_usd", "warning_usd"}), never a code constant. A
# `reserve` line ({"event": "reserve", "kind", "order", "worst_case_usd"}) holds a planned run's
# worst case for the runs ordered after it until that run opens an intent or a `skipped` line
# ({"event": "skipped", "kind"}) records it skipped.
ROLE_C_KIND = "cloud-reference-b1-role-c"
FOR_SECKIN_NAME = "FOR_SECKIN.md"   # beside the store   # the intent the lead opens for role C's run (open-role-c)


class SpendStoreError(Exception):
    """The store cannot give a spend figure, or refuses a write."""


def store_path(root):
    """The one store, from git's common directory as seen from `root`."""
    try:
        done = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                              capture_output=True, text=True, timeout=30, creationflags=no_window())
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SpendStoreError("The main checkout cannot be found from git (%s)" % type(exc).__name__)
    if done.returncode != 0 or not done.stdout.strip():
        raise SpendStoreError("The main checkout cannot be found from git")
    return Path(done.stdout.strip()).resolve().parent / "docs" / "loop" / "private" / STORE_NAME


def handback_dir(store):
    return Path(store).parent / HANDBACK_DIR_NAME


def read(store):
    """Every line of the store. Absent, unreadable, or a line that cannot be counted: refused."""
    store = Path(store)
    if not store.is_file():
        raise SpendStoreError("The spend store %s does not exist; the operator creates it (empty) before the first "
                              "run, and its absence is never read as no spend" % store)
    try:
        rows = [json.loads(l) for l in store.read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError):
        raise SpendStoreError("The spend store %s cannot be read; its spend is unknown" % store.name)
    for r in rows:
        if not isinstance(r, dict) or r.get("event") not in LINE_EVENTS:
            raise SpendStoreError("A spend store line is not one of the declared kinds; its spend is unknown")
        if r.get("event") == "intent":
            if not (isinstance(r.get("cap_usd"), (int, float)) and r.get("run_id")):
                raise SpendStoreError("An intent line has no cap or no run id; its spend is unknown")
        elif r.get("event") == "ceiling":
            ceiling, warning = r.get("ceiling_usd"), r.get("warning_usd")
            if not (_money(ceiling) and ceiling > 0 and _money(warning) and 0 < warning <= ceiling and r.get("time_utc")):
                raise SpendStoreError("A ceiling line needs time_utc, ceiling_usd and warning_usd at or below it")
        elif r.get("event") == "reserve":
            if not (r.get("kind") and _money(r.get("worst_case_usd")) and r["worst_case_usd"] >= 0
                    and isinstance(r.get("order"), int) and not isinstance(r.get("order"), bool)):
                raise SpendStoreError("A reserve line needs a kind, an order and its worst case")
        elif r.get("event") == "skipped":
            if not r.get("kind"):
                raise SpendStoreError("A skipped line names the kind it skips")
        elif r.get("event") != "handed_back" and not isinstance(r.get("spent_usd"), (int, float)):
            raise SpendStoreError("A spend store line has no spent_usd; its spend is unknown")
    return rows


def _money(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def ceiling(store):
    """The API's ceiling and warning from the store's latest `ceiling` line (by its time, then its
    place), or None when the store holds none: there is no code default (D-S121)."""
    lines = [(str(r.get("time_utc")), i, r) for i, r in enumerate(read(store)) if r.get("event") == "ceiling"]
    if not lines:
        return None
    latest = max(lines)[2]
    return {"ceiling_usd": float(latest["ceiling_usd"]), "warning_usd": float(latest["warning_usd"]),
            "time_utc": latest["time_utc"]}


def reserved_before(store, kind):
    """D-441: the worst cases reserved by planned runs ordered before `kind` that have not opened an
    intent and are not recorded skipped (a kind with no reserve line comes after every reserved one)."""
    rows = read(store)
    started = {r.get("kind") for r in rows if r.get("event") == "intent"}
    skipped = {r.get("kind") for r in rows if r.get("event") == "skipped"}
    reserves = {r["kind"]: r for r in rows if r.get("event") == "reserve"}
    own = reserves.get(kind, {}).get("order")
    return round(sum(float(r["worst_case_usd"]) for k, r in reserves.items()
                     if k != kind and k not in started and k not in skipped
                     and (own is None or r["order"] < own)), 6)


def api_room(store, kind, worst_case_usd):
    """D-S121, D-441: whether a paid run of `kind` with this worst case fits the API ceiling: closed
    spend, running intents' caps, the reserves of runs ordered before it and its own worst case,
    together at or below the latest ceiling line. Returns {ok, reason, warn, ...}; with no ceiling line
    the run is refused (no code default)."""
    limits = ceiling(store)
    figures = state(store)
    if limits is None:
        return {"ok": False, "reason": "The spend store holds no API ceiling line; the lead writes one before any paid run",
                "warn": False}
    reserved = reserved_before(store, kind)
    total = figures["spent_usd"] + figures["running_caps_usd"] + reserved + float(worst_case_usd)
    out = {"ceiling_usd": limits["ceiling_usd"], "warning_usd": limits["warning_usd"], "spent_usd": figures["spent_usd"],
           "running_caps_usd": figures["running_caps_usd"], "reserved_before_usd": reserved,
           "worst_case_usd": float(worst_case_usd), "total_usd": round(total, 6),
           "warn": figures["spent_usd"] + figures["running_caps_usd"] + reserved >= limits["warning_usd"]
                   or total >= limits["warning_usd"]}
    if total > limits["ceiling_usd"] + 1e-9:
        return dict(out, ok=False, reason="This run's worst case %.4f USD would pass the API ceiling %.2f USD (spent %.4f, "
                                          "running %.4f, reserved before it %.4f)" % (float(worst_case_usd),
                                          limits["ceiling_usd"], figures["spent_usd"], figures["running_caps_usd"], reserved))
    return dict(out, ok=True, reason=None)


def state(store):
    """{spent_usd, running_caps_usd, open_runs, closed_runs, handed_back}: spend is every closed
    line (once per run id), running caps every intent no close line names."""
    rows = read(store)
    closed, spent, open_caps, handed = set(), 0.0, {}, []
    for r in rows:
        event = r.get("event")
        if event == "intent":
            open_caps[r["run_id"]] = float(r["cap_usd"])
        elif event == "handed_back":
            handed.append(r.get("file_sha256"))
        elif event in ("ceiling", "reserve", "skipped"):
            continue   # the API ceiling and the planned runs' reserves are no spend (D-S121, D-441)
        else:
            run_id = r.get("run_id")
            if run_id is not None and run_id in closed:
                continue   # a run's spend is counted once
            if run_id is not None:
                closed.add(run_id)
            spent += float(r["spent_usd"])
    running = {k: v for k, v in open_caps.items() if k not in closed}
    return {"spent_usd": round(spent, 6), "running_caps_usd": round(sum(running.values()), 6),
            "open_runs": sorted(running), "closed_runs": len(closed), "handed_back": handed}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unappended(store):
    """The handed-back files in the drop folder whose digest no `handed_back` line names."""
    folder = handback_dir(store)
    if not folder.is_dir():
        return []
    done = set(state(store)["handed_back"])
    return sorted(p.name for p in folder.iterdir() if p.is_file() and sha(p) not in done)


def lead_may_spend(store):
    """None when the lead side may start a paid run or an instance launch, else the reason. The
    guard calls this before a launch; the paid runners before their first request."""
    try:
        waiting = unappended(store)
    except SpendStoreError as exc:
        return str(exc)
    if waiting:
        return ("A role C spend file is handed back and not appended (%s); append it with "
                "tools/loop/cloud_reference_spend.py append-handed-back first" % ", ".join(waiting[:3]))
    return None


def _utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


class StoreLock:
    """An exclusive lock beside the store, held from a run's decision through its intent line. A
    lock left by a crash is reported with its age and pid; it is never broken here."""

    def __init__(self, store):
        self.path = Path(str(store) + ".lock")

    def __enter__(self):
        try:
            with open(self.path, "x", encoding="utf-8") as handle:
                now = time.time()
                handle.write(json.dumps({"pid": os.getpid(), "created_epoch": now, "time_utc": _utc(now)}) + "\n")
        except FileExistsError:
            try:
                held = json.loads(self.path.read_text(encoding="utf-8"))
                holder = "held %.0f s by pid %s" % (time.time() - float(held["created_epoch"]), held["pid"])
            except (OSError, ValueError, KeyError, TypeError):
                holder = "holder unreadable"
            raise SpendStoreError("Another run holds the spend store lock (%s, %s); remove it only if no run is "
                                  "deciding" % (self.path.name, holder)) from None
        return self

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)
        return False


def append(store, line):
    with Path(store).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(line, sort_keys=True, default=str) + "\n")


def unplanned_runs(rows, lines):
    """The handed-back lines' run ids that name no role C intent the lead opened."""
    opened = {r["run_id"] for r in rows if r.get("event") == "intent" and r.get("kind") == ROLE_C_KIND}
    return [l["run_id"] for l in lines if l["run_id"] not in opened]


def over_cap(rows, lines):
    """[(run id, spent, cap)] for each handed-back line whose spend passes its role C intent's cap."""
    caps = {r["run_id"]: float(r["cap_usd"]) for r in rows if r.get("event") == "intent" and r.get("kind") == ROLE_C_KIND}
    return [(l["run_id"], float(l["spent_usd"]), caps[l["run_id"]]) for l in lines
            if l["run_id"] in caps and float(l["spent_usd"]) > caps[l["run_id"]] + 1e-9]


def flag_for_seckin(store, run_id, spent, cap, name, digest):
    """A flag at the top of FOR_SECKIN.md (beside the store): a role C run spent more than its
    intent held. Written under its own heading, below the file's title line when it has one."""
    path = Path(store).parent / FOR_SECKIN_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    flag = ("## FLAG %s: a role C cloud reference run spent above its held cap\n\n"
            "Run %s spent %.4f USD; the intent the lead opened held %.4f USD. The handed-back file %s (sha256 %s) "
            "was not appended; its spend is real and is not yet in the store. Nothing else ran because of it.\n\n"
            % (_utc(time.time()), run_id, spent, cap, name, digest))
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("# "):
        text = lines[0] + "\n" + flag + "".join(lines[1:]).lstrip("\n")
    else:
        text = flag + text
    path.write_text(text, encoding="utf-8")


def append_handed_back(store, handed):
    """A role C spend file into the store, once: its lines, each marked with the file's digest,
    after one `handed_back` line. Refused for a file outside the drop folder, appended before, or
    holding a run id the store already counts."""
    handed = Path(handed).resolve()
    if handed.parent != handback_dir(store).resolve():
        raise SpendStoreError("A handed-back file is appended from %s only" % HANDBACK_DIR_NAME)
    digest = sha(handed)
    with StoreLock(store):
        now = state(store)
        if digest in now["handed_back"]:
            raise SpendStoreError("This handed-back file is appended already")
        lines = [json.loads(l) for l in handed.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lines or not all(isinstance(l, dict) and isinstance(l.get("spent_usd"), (int, float)) and l.get("run_id")
                                for l in lines):
            raise SpendStoreError("A handed-back file holds a line with no spent_usd or no run id")
        rows = read(store)
        closed = {r.get("run_id") for r in rows if r.get("event") in (None, "close") and r.get("run_id")}
        twice = [l["run_id"] for l in lines if l["run_id"] in closed]
        if twice:
            raise SpendStoreError("The store counts run %s already" % twice[0])
        unplanned = unplanned_runs(rows, lines)
        if unplanned:
            raise SpendStoreError("Run %s has no role C intent the lead opened; its spend was never held as a "
                                  "running cap" % unplanned[0])
        over = over_cap(rows, lines)
        if over:
            run_id, spent, cap = over[0]
            flag_for_seckin(store, run_id, spent, cap, handed.name, digest)
            raise SpendStoreError("Run %s spent %.4f USD against the %.4f USD its intent held; not appended, and "
                                  "flagged at the top of FOR_SECKIN.md" % (run_id, spent, cap))
        append(store, {"event": "handed_back", "file_sha256": digest, "file": handed.name, "lines": len(lines),
                       "time_utc": _utc(time.time()), "spent_usd": 0.0})
        for l in lines:
            append(store, dict(l, event="close", handed_back_sha256=digest))
    return {"file_sha256": digest, "lines": len(lines), "spent_usd": round(sum(float(l["spent_usd"]) for l in lines), 6)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_reference_spend.py", allow_abbrev=False,
                                     description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    p = sub.add_parser("append-handed-back")
    p.add_argument("file")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[2]
    try:
        store = store_path(root)
        if args.command == "status":
            figures = state(store)
            figures["unappended"] = unappended(store)
            print(json.dumps(figures, sort_keys=True))
        else:
            print(json.dumps(append_handed_back(store, args.file), sort_keys=True))
    except SpendStoreError as exc:
        print("cloud_reference_spend: %s" % exc, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
