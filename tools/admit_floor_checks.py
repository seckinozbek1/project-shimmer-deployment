#!/usr/bin/env python3
"""Check 521 (lane/admit-floor, D-726): the seal admission's laptop room never holds the budget ledger lock.

On 18 November the parse sweep's admission (tools/seal_route_driver.py admit) took the ledger lock, then waited in
wait_for_room for the 30 GiB D-099 floor (standing_orders_check.DISK_FLOOR) at 28.7 GiB free, holding every other
launch. D-726 (Seckin 12:08): laptop disk below a floor never again makes a measurement wait. Seckin 19 Nov 2026
12:03: heavy laptop work needs its own footprint plus the margin of config/laptop_disk_floor.json. Proofs:

1. floor: the admission's steps (reverify, preflight) need their expected bytes plus the laptop rule's margin
   (admit_floor_bytes, margin_gib 12 GiB read at each call), not the old fixed 30 GiB floor: at 20 GiB free every
   bundle is admitted, each gate line names the 12 GiB margin; a margin moved in the file moves the gate.
2. no wait under the lock: with no room at first, the admission waits before it takes the lock and takes it only
   once the room is there.
3. refusal under the lock: when the room read before the lock is gone at a step's own gate, the admission refuses
   at once (nothing admitted, the staging kept as refused, the lock released), never waits holding the lock;
   on disk or on memory alike. 4. its refusing reading is an event 'refused' line of .refused/gate_log.jsonl.
5. the room waited for before the lock counts the collected evidence archive extracted under it.
6. open item 157 (a): a refusing step's stdout and stderr tails (last 20 lines, key-like strings masked) reach
   admit.log before the refusal is raised.
7. open item 157 (b): while no declared type is offered at its sealed rate, the admission polls the free inventory
   (read-only) before the ledger lock, every poll interval up to the limit in config/admit_capacity_wait.json, and
   past the limit refuses with the lock never taken.

Stand-ins only (seal_route_checks.returned_job: a seal job run on stand-ins, its evidence collected), no provider,
no key, nothing launched. Each proof run as built (passes), neutralised (must fail), restored, run again (passes).
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import time
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools"), str(ROOT / "tools" / "loop")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import seal_route_checks as src  # noqa: E402
import seal_route_driver as driver  # noqa: E402

GIB = 2 ** 30
DRIVER = Path(driver.__file__)


class WouldWait(Exception):
    """A neutralised gate that would wait forever: the wait is the observation."""


def _reading(free_gib, memory_gb=4.0):
    return dict(memory_gb=memory_gb, disk_bytes=int(free_gib * GIB), disk_gb=round(free_gib, 2), other_seals=0)


def _admit(drv, frees, on_sleep):
    """admit() with steps on the stand-in job; free disk read from `frees` in turn (the last repeated), each read,
    sleep, lock, step and unlock recorded in order."""
    events, queue = [], list(frees)

    def resources(_path):
        events.append("read")
        value = queue.pop(0) if len(queue) > 1 else queue[0]
        return _reading(*value) if isinstance(value, tuple) else _reading(value)

    def sleep(_seconds):
        events.append("sleep")
        on_sleep()

    def step_run(argv, capture_output, text):
        events.append("step")
        return types.SimpleNamespace(returncode=0)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, _result, _base = src.returned_job(tmp)
        out = tmp / "out"
        with patch.object(drv, "resources", resources), patch.object(time, "sleep", sleep):
            try:
                rows = drv.admit(job_bundle, run_folder, reuse, out, live, live["budget_ledger"], steps=True,
                                 run=step_run, lock=lambda ledger: events.append("lock") or "held",
                                 unlock=lambda held: events.append("unlock"))
                outcome = "admitted %d" % len(rows)
            except WouldWait:
                outcome = "would wait"
            except Exception as exc:
                outcome = "refused" if "No room" in str(exc) else "raised %s" % type(exc).__name__
        import json
        floors, lines = [], []
        for log in (tmp / "out.staging" / "gate_log.jsonl", tmp / "out.refused" / "gate_log.jsonl"):
            if log.is_file():
                lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x]
                floors = [x["disk_floor_bytes"] for x in lines]
        archive = (Path(run_folder) / "collected_evidence.tar.gz").stat().st_size
        return {"outcome": outcome, "events": events, "floors_gib": sorted({f / GIB for f in floors}),
                "gate_lines": len(floors), "refused_kept": (tmp / "out.refused").is_dir(), "admitted": out.is_dir(),
                "lines": lines, "archive_bytes": archive}


def _raise():
    raise WouldWait()


def proof_floor(drv=None):
    import json
    import launch_floors as lf
    drv = drv or driver
    seen = _admit(drv, [20.0], _raise)
    direct = (drv.admits(_reading(12.02), 16 * 2 ** 20, drv.admit_floor_bytes()),
              drv.admits(_reading(11.99), 16 * 2 ** 20, drv.admit_floor_bytes()))
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "laptop_disk_floor.json"
        cfg.write_text(json.dumps({"margin_gib": 25}), encoding="utf-8")
        with patch.object(lf, "DISK_CONFIG", cfg):
            moved = drv.admits(_reading(20.0), 16 * 2 ** 20, drv.admit_floor_bytes())
    return {"outcome": seen["outcome"], "floors_gib": seen["floors_gib"], "gate_lines": seen["gate_lines"],
            "12 GiB plus expected": direct, "margin 25 in the file holds at 20 GiB": moved}


def expected_floor():
    # 3 bundles x 2 steps under the lock, plus the room line read before it; every line at the 12 GiB margin.
    return {"outcome": "admitted 3", "floors_gib": [12.0], "gate_lines": 7, "12 GiB plus expected": (True, False),
            "margin 25 in the file holds at 20 GiB": False}


def neutralise_floor():
    # The old fixed 30 GiB floor (D-099) typed back into the admission.
    return _swap("proof_floor", "def admit_floor_bytes():\n    return int(launch_floors.margin_gib()[0] * 2 ** 30)",
                 "def admit_floor_bytes():\n    return int(30.0 * 2 ** 30)")


def proof_no_wait_under_the_lock(drv=None):
    drv = drv or driver
    seen = _admit(drv, [11.0, 11.0, 20.0], lambda: None)
    ev = seen["events"]
    return {"outcome": seen["outcome"], "before the lock": ev[:ev.index("lock")] if "lock" in ev else ev,
            "sleeps after the lock": ev[ev.index("lock"):].count("sleep") if "lock" in ev else None}


def expected_no_wait_under_the_lock():
    return {"outcome": "admitted 3", "before the lock": ["read", "sleep", "read", "sleep", "read"],
            "sleeps after the lock": 0}


def neutralise_no_wait_under_the_lock():
    # The 18 November form: no room wait before the lock, each step's gate waiting under it.
    return _swap("proof_no_wait_under_the_lock",
                 "    if steps:\n        if gate is not None:\n            gate(ADMIT_ROOM)",
                 "    if False:\n        if gate is not None:\n            gate(ADMIT_ROOM)",
                 ("floor_bytes=admit_floor_bytes(), wait=False))", "floor_bytes=admit_floor_bytes(), wait=True))"))


def proof_refusal_under_the_lock(drv=None):
    drv = drv or driver
    out = {}
    for case, frees in (("disk", [20.0, 11.0, 20.0]), ("memory", [20.0, (20.0, 1.0), 20.0])):
        seen = _admit(drv, frees, lambda: None)
        ev = seen["events"]
        refused = [x for x in seen["lines"] if x.get("event") == "refused"]
        out[case] = {"outcome": seen["outcome"], "admitted": seen["admitted"], "refused kept": seen["refused_kept"],
                     "unlocked last": bool(ev) and ev[-1] == "unlock", "sleeps": ev.count("sleep"),
                     "refused lines": [(x["step"], x["disk_gb"], x["memory_gb"]) for x in refused]}
    return out


def expected_refusal_under_the_lock():
    # The refusing reading is written as an event 'refused' line in the kept .refused/gate_log.jsonl; a refusal
    # on memory under the lock is intended (D-726: the lock is never held through a wait).
    base = {"outcome": "refused", "admitted": False, "refused kept": True, "unlocked last": True, "sleeps": 0}
    return {"disk": dict(base, **{"refused lines": [("ordinary_final_bound_reverify.py", 11.0, 4.0)]}),
            "memory": dict(base, **{"refused lines": [("ordinary_final_bound_reverify.py", 20.0, 1.0)]})}


def neutralise_refusal_under_the_lock():
    return _swap("proof_refusal_under_the_lock", "floor_bytes=admit_floor_bytes(), wait=False))",
                 "floor_bytes=admit_floor_bytes(), wait=True))")


def _swap(proof, old, new, *more):
    @contextlib.contextmanager
    def swap():
        original = globals()[proof]
        mod = src._module_from(DRIVER, old, new, "seal_route_driver_neutralised", more)
        globals()[proof] = lambda: original(mod)
        try:
            yield
        finally:
            globals()[proof] = original
    return swap()


def proof_refusing_reading_logged(drv=None):
    """The refusal's own reading is an event 'refused' line of the kept .refused/gate_log.jsonl (proof 3's cases)."""
    return proof_refusal_under_the_lock(drv)


def expected_refusing_reading_logged():
    return expected_refusal_under_the_lock()


def neutralise_refusing_reading_logged():
    return _swap("proof_refusing_reading_logged", "        if not wait and log is not None:", "        if False:")


def proof_evidence_counted_before_the_lock(drv=None):
    """The room waited for before the lock counts the collected evidence archive extracted under it."""
    drv = drv or driver
    seen = _admit(drv, [20.0], _raise)
    room = [x for x in seen["lines"] if x.get("lock") == "before"]
    steps = sum(drv.EXPECTED_BYTES[s] for s in drv.ADMIT_STEPS) * 3
    return {"outcome": seen["outcome"], "room expected": room[0]["expected_bytes"] - steps if room else None,
            "archive": seen["archive_bytes"]}


def expected_evidence_counted_before_the_lock():
    return "same"


def _evidence_view(value):
    if not isinstance(value, dict) or value.get("outcome") != "admitted 3" or not value.get("archive"):
        return value
    return "same" if value["room expected"] == value["archive"] else value


def neutralise_evidence_counted_before_the_lock():
    return _swap("proof_evidence_counted_before_the_lock",
                 "            evidence = archive.stat().st_size if archive.is_file() else 0" + chr(10),
                 "            evidence = 0" + chr(10))


FAKE_KEY = "sk-" + "ant-" + "B" * 30          # a key-like body to be masked; not a key
CAPACITY_REFUSAL = "No declared instance type offered at its sealed rate; poll again later"


def _admit_steps(drv, step_run, capacity=None):
    """admit() on the stand-in job with room to spare; (outcome, events, what admit.log got)."""
    events = []
    log = io.StringIO()

    def sleep(_seconds):
        events.append("sleep")

    def probe(manifests):
        events.append("probe")
        return capacity(manifests) if capacity else None
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, _result, _base = src.returned_job(tmp)
        with patch.object(drv, "resources", lambda _p: _reading(20.0)), patch.object(time, "sleep", sleep), \
                contextlib.redirect_stdout(log):
            try:
                rows = drv.admit(job_bundle, run_folder, reuse, tmp / "out", live, live["budget_ledger"], steps=True,
                                 run=step_run, capacity=probe, lock=lambda ledger: events.append("lock") or "held",
                                 unlock=lambda held: events.append("unlock"))
                outcome = "admitted %d" % len(rows)
            except Exception as exc:
                outcome = "refused: " + str(exc)[:60]
    return outcome, events, log.getvalue()


def proof_refusal_tail_logged(drv=None):
    """Open item 157 (a): the refusing step's stdout and stderr tails reach admit.log, masked, before the raise."""
    drv = drv or driver
    lines = "\n".join(["line %02d" % i for i in range(1, 25)] + ["token = " + FAKE_KEY])

    def step_run(argv, capture_output, text):
        if argv[3].endswith("ordinary_final_bound_preflight.py"):
            return types.SimpleNamespace(returncode=1, stdout=lines, stderr="GuardRefusal: " + CAPACITY_REFUSAL)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    outcome, _events, log = _admit_steps(drv, step_run)
    return {"refused": outcome.startswith("refused: ordinary_final_bound_preflight.py refused"),
            "last 20 lines": "line 06" in log and "line 24" in log and "line 05" not in log,
            "stderr tail": CAPACITY_REFUSAL in log, "key masked": FAKE_KEY not in log and "[masked]" in log}


def expected_refusal_tail_logged():
    return {"refused": True, "last 20 lines": True, "stderr tail": True, "key masked": True}


def neutralise_refusal_tail_logged():
    return patch.object(driver, "write_refusal_tail", lambda *a, **k: None)


def proof_capacity_waited_before_the_lock(drv=None):
    """Open item 157 (b): while the free inventory offers no declared type at its sealed rate, the admission polls
    before the ledger lock (every poll interval, up to the declared limit), never refusing on the first reading;
    past the limit it refuses with the lock never taken."""
    drv = drv or driver
    ok = lambda argv, capture_output, text: types.SimpleNamespace(returncode=0, stdout="", stderr="")
    answers = [CAPACITY_REFUSAL, CAPACITY_REFUSAL, None]
    outcome, events, log = _admit_steps(drv, ok, capacity=lambda m: answers.pop(0))
    with patch.object(driver, "CAPACITY_CONFIG", Path(tempfile.gettempdir()) / "admit_capacity_wait_absent.json"), \
            patch.object(drv, "capacity_settings", lambda path=None: (120, 4)):
        never, ev2, _ = _admit_steps(drv, ok, capacity=lambda m: CAPACITY_REFUSAL)
    return {"outcome": outcome, "before the lock": events[:events.index("lock")] if "lock" in events else events,
            "logged": "waiting for capacity before the ledger lock" in log,
            "past the limit": (never.startswith("refused: No capacity within"), ev2.count("probe"), "lock" in ev2)}


def expected_capacity_waited_before_the_lock():
    return {"outcome": "admitted 3", "before the lock": ["probe", "sleep", "probe", "sleep", "probe"], "logged": True,
            "past the limit": (True, 3, False)}


def neutralise_capacity_waited_before_the_lock():
    return patch.object(driver, "wait_for_capacity", lambda manifests, probe, stream=None: probe(manifests) and None)


PROOFS = ("floor", "no_wait_under_the_lock", "refusal_under_the_lock", "refusing_reading_logged",
          "evidence_counted_before_the_lock", "refusal_tail_logged", "capacity_waited_before_the_lock")
VIEWS = {"evidence_counted_before_the_lock": _evidence_view}


def caught(function):
    try:
        return function()
    except Exception as exc:
        return "raised " + type(exc).__name__


def run_check():
    done = []
    space = globals()
    for name in PROOFS:
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                view = VIEWS.get(name, lambda v: v)
                first = view(space["proof_" + name]())
                with space["neutralise_" + name]():
                    broken = view(caught(lambda: space["proof_" + name]()))
                again = view(space["proof_" + name]())
        except Exception as exc:
            return "FAIL", "%s: %s %s" % (name, type(exc).__name__, str(exc)[:300])
        want = space["expected_" + name]()
        if first != want:
            return "FAIL", "%s as built: %s" % (name, str(first)[:600])
        if broken == want:
            return "FAIL", "%s still passes when neutralised" % name
        if again != want:
            return "FAIL", "%s after restore: %s" % (name, str(again)[:400])
        done.append(name)
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, stand-ins only: the admission's room is its "
                    "expected bytes plus the 12 GiB margin of config/laptop_disk_floor.json (Seckin 19 Nov 12:03), waited for before the ledger lock, refused (never waited "
                    "for) under it, its refusing reading logged, the evidence archive counted, a refusing step's tail in admit.log, capacity waited for before the lock (%s)" % (len(done), ", ".join(done)))


if __name__ == "__main__":
    status, detail = run_check()
    print(status, detail)
    raise SystemExit(0 if status == "PASS" else 1)
