"""Proofs for order 99 at the seal admission (tools/seal_route_driver.py admission_stale_reason, loop_record_reason
and budget_reason), on fixtures only: no launch, no seal, no network, no real ledger. Gate checks 460 to 464, each
proof neutralised in memory, FAILS, restored, PASSES.

    py -3.12 -X utf8 tools/seal_parallel_checks.py [460 ... 464]

460  complete guarded loop records of other instances after the read copy do not refuse (the 16 November evening
     case: two fs-listing launches during a seal job), end to end through admit();
461  a foreign line that is malformed, of another kind or out of its record's order refuses;
462  a budget the current ledgers no longer carry (the guard refuses, or its cap is below a bundle's sealed hard cap)
     refuses and admits nothing;
463  the seal job's own lines still verify, alone and among foreign lines, and alone need no budget recheck;
464  a removed or rewritten earlier line (of the budget ledger, R's ledger or the spend store) refuses.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tools", ROOT / "tools" / "loop"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import seal_route as sr  # noqa: E402
import seal_route_driver as driver  # noqa: E402
import loop_budget_guard as guard  # noqa: E402

DRIVER = ROOT / "tools" / "seal_route_driver.py"
T0 = datetime(2026, 11, 16, 16, 0, tzinfo=timezone.utc)
NOW = (T0 + timedelta(hours=2)).timestamp()
RATE = 1.29
FORECAST_MINUTES = 30
STORAGE = 0.5
RESERVE_SECONDS = 300
OWN_NAME = "shimmer-loop-08e943e-73022166"
OWN_ID = "f" * 32


def at(minutes):
    return (T0 + timedelta(minutes=minutes)).isoformat()


BUDGET_OPEN = {"event": "budget_open", "time_utc": at(-600), "budget_usd": 20.0, "hard_stop_usd": 19.0}


def record(name, iid, start, minutes=5, cost=None, purpose="fs-listing", cap=0.6289, end=True):
    """A guarded loop launch's lines as tools/loop/fs_listing.py and the controller write them."""
    common = dict(instance_name=name, type="gpu_1x_a10", region="us-east-1", price_usd_per_hour=RATE, purpose=purpose,
                  forecast_usd=0.4193, cap_usd=cap)
    asked, deadline = at(start), at(start + 30)
    lines = [dict(common, event="launch_intent", time_utc=asked, launch_requested_utc=asked, deadline_utc=deadline),
             dict(common, event="launch", time_utc=at(start + 0.03), launch_requested_utc=asked, instance_id=iid,
                  deadline_utc=deadline)]
    if end:
        lines.append(dict(common, event="termination", time_utc=at(start + minutes), launch_requested_utc=asked,
                          instance_id=iid, actual_minutes=minutes,
                          actual_cost=round(RATE * minutes / 60, 4) if cost is None else cost))
    return lines


def own_lines():
    """The seal job's own lines as the controller writes them (with seal_on), its name from its binding."""
    lines = record(OWN_NAME, OWN_ID, 0, minutes=24, purpose="route-gate-tip-seal", cap=1.0481)
    return [dict(line, seal_on="instance") for line in lines]


def reaper_termination(name, reason="intent_without_instance", iid=None):
    return {"event": "termination", "by": "reaper", "time_utc": at(90), "instance_id": iid, "instance_name": name,
            "reason": reason, "type": "gpu_1x_a10", "region": "us-east-1", "actual_minutes": 30, "actual_cost": 0.645}


def jsonl(rows):
    return b"".join(((r if isinstance(r, str) else json.dumps(r, sort_keys=True)) + "\n").encode("utf-8") for r in rows)


def entry(data):
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


class Records:
    """Live records with their read copies taken: the budget ledger, R's ledger and the spend store."""

    def __init__(self, folder, prior=None, r_prior=None, spend=None):
        self.live = {}
        copies = {}
        for key, rows in (("budget_ledger", prior if prior is not None else [BUDGET_OPEN]),
                          ("r_ledger", r_prior if r_prior is not None else [record("shimmer-loop-r-1", "r" * 32, -200)[0]]),
                          ("spend_store", spend if spend is not None else [{"event": "ceiling", "ceiling_usd": 60.0}])):
            path = Path(folder) / (key + ".jsonl")
            data = jsonl(rows)
            path.write_bytes(data)
            self.live[key] = path
            copies[key] = entry(data)
        self.job = {"read_copies": copies}

    def append(self, key, rows):
        with self.live[key].open("ab") as stream:
            stream.write(jsonl(rows))


def concurrent_lines():
    """What a seal job's ledger gains while other launches run: its own record interleaved with two complete
    fs-listing records, the termination of a launch that was running when the copy was taken, a reaper close of
    an intent with no instance, and a launch still open (with its deadline)."""
    own = own_lines()
    fsl1 = record("shimmer-loop-fs-listing-20261116t160050", "4" * 32, 1, minutes=5)
    fsl2 = record("shimmer-loop-fs-listing-20261116t160713", "0" * 32, 7, minutes=10)
    running_before = record("shimmer-loop-a-running", "a" * 32, -20, minutes=40)
    intent_only = record("shimmer-loop-b-no-instance", "b" * 32, 20)[0]
    still_open = record("shimmer-loop-c-open", "c" * 32, 60, end=False)
    added = [own[0], fsl1[0], fsl1[1], own[1], fsl1[2], *fsl2, running_before[2], intent_only,
             reaper_termination("shimmer-loop-b-no-instance"), *still_open, own[2]]
    prior = [BUDGET_OPEN, running_before[0], running_before[1]]
    return prior, added, len(added) - 3


def stale(mod, records, own=(OWN_NAME, OWN_ID)):
    found = []
    reason = mod.admission_stale_reason(records.job, records.live, set(own), found)
    return reason, found


# ---------------------------------------------------------------------------
# an admission end to end: the seal_route_checks job fixture with budget figures in each returned manifest


def budget_job(tmp):
    """seal_route_checks.returned_job with a read copy of a real budget line, requests that name their forecast and
    storage forecast, and returned manifests carrying the figures their budget was sealed on (hard cap at the
    guard's own figure on that copy)."""
    import seal_route_checks as src
    real_fixture, real_sealer = src.job_fixture, src.fake_sealer
    copy = jsonl([BUDGET_OPEN])
    figures = dict(instance_candidates=[dict(type="gpu_1x_a10", max_hourly_rate=RATE)], forecast_minutes=FORECAST_MINUTES,
                   workload_stop_reserve_seconds=RESERVE_SECONDS,
                   hard_ceiling_usd=round(guard.CAP_FACTOR * guard.forecast_usd(FORECAST_MINUTES, RATE), 4))

    def fixture(tmp_, mod=sr):
        base, tree, job, assets, models = real_fixture(tmp_, mod)
        (base / sr.read_copy_name("budget_ledger")).write_bytes(copy)
        job["read_copies"]["budget_ledger"] = dict(job["read_copies"]["budget_ledger"], **entry(copy))
        for request in job["requests"]:
            request["argv"] += ["--forecast-minutes", str(FORECAST_MINUTES), "--storage-forecast-usd", str(STORAGE)]
        (base / sr.JOB_FILE).write_text(json.dumps(job), encoding="utf-8")
        manifest = json.loads((base / "execution_manifest.json").read_text(encoding="utf-8"))
        manifest["seal_job"] = job
        manifest["support_files"][sr.JOB_FILE] = sr.sha(base / sr.JOB_FILE)
        manifest["support_files"][sr.read_copy_name("budget_ledger")] = entry(copy)["sha256"]
        (base / "execution_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return base, tree, job, assets, models

    def sealer(assets, models):
        run, calls = real_sealer(assets, models)

        def wrapped(argv, cwd, env, stdin, stdout, stderr, timeout):
            done = run(argv, cwd, env, stdin, stdout, stderr, timeout)
            out = Path(argv[argv.index("--output-dir") + 1])
            manifest = json.loads((out / "execution_manifest.json").read_text(encoding="utf-8"))
            manifest.update(figures)
            (out / "execution_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            return done
        return wrapped, calls
    with patch.object(src, "job_fixture", fixture), patch.object(src, "fake_sealer", sealer):
        job_bundle, run_folder, reuse, live, result, base = src.returned_job(tmp)
    return job_bundle, run_folder, reuse, live


def admit_with(mod, tmp, foreign_rows, out_name="admitted", recheck=None):
    """The fixture's admission after `foreign_rows` were appended to its live ledger: (rows or None, the refusal
    text or None, whether the admission folder and a refused folder exist, budget rechecks made)."""
    job_bundle, run_folder, reuse, live = budget_job(tmp)
    with live["budget_ledger"].open("ab") as stream:
        stream.write(jsonl(foreign_rows))
    calls = []
    real = mod.budget_reason

    def counted(*a, **k):
        calls.append(1)
        return (recheck or real)(*a, **k)
    out = tmp / out_name
    with patch.object(mod, "budget_reason", counted):
        try:
            rows, refusal = mod.admit(job_bundle, run_folder, reuse, out, live, live["budget_ledger"], steps=False,
                                      lock=lambda ledger: "held", unlock=lambda held: None, clock=lambda: NOW), None
        except sr.RouteError as exc:
            rows, refusal = None, str(exc)
    return rows, refusal, out.exists(), out.with_name(out.name + ".refused").exists(), len(calls)


# ---------------------------------------------------------------------------
# the proofs (each takes the driver module, so a neutralised copy can be put in its place)


def proof_460(mod=driver):
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        prior, added, foreign_count = concurrent_lines()
        records = Records(tmp, prior=prior)
        records.append("budget_ledger", added)
        records.append("r_ledger", record("shimmer-loop-r-2", "s" * 32, 3))
        reason, found = stale(mod, records)
        out["foreign complete records with the job's own admitted"] = reason is None
        out["each foreign line counted for the budget recheck"] = len(found) == foreign_count + 3
    with tempfile.TemporaryDirectory() as tmp:
        evening = record("shimmer-loop-fs-listing-20261116t160050", "4" * 32, 1) + \
            record("shimmer-loop-fs-listing-20261116t160713", "0" * 32, 7, minutes=10)
        rows, refusal, admitted, refused, rechecks = admit_with(mod, Path(tmp), evening)
        out["the 16 November case (6 fs-listing lines) admits every bundle"] = (
            refusal is None and rows is not None and len(rows) == 3 and admitted and not refused)
        out["each bundle held to the current ledgers"] = rechecks == 3
    return all(out.values()), out


BAD_CASES = {
    "a budget_change line": [{"event": "budget_change", "time_utc": at(5), "budget_usd": 30.0}],
    "a line of another kind inside a launch's record": [record("shimmer-loop-x-15", "f6" * 16, 5)[0],
                                                        dict(record("shimmer-loop-x-15", "f6" * 16, 5)[0], event="budget_change")],
    "a field outside IV.3": [dict(record("shimmer-loop-x-1", "1" * 32, 5)[0], note="free text")],
    "a launch with no intent before it": [record("shimmer-loop-x-2", "2" * 32, 5)[1]],
    "a second intent of one launch": [record("shimmer-loop-x-3", "3" * 32, 5)[0]] * 2,
    "a launch after its termination": record("shimmer-loop-x-4", "4" * 32, 5) + [record("shimmer-loop-x-4", "4" * 32, 5)[1]],
    "a termination of no recorded launch": [record("shimmer-loop-x-5", "5" * 32, 5)[2]],
    "a launch with another deadline than its intent": [record("shimmer-loop-x-6", "6" * 32, 5)[0],
                                                        dict(record("shimmer-loop-x-6", "6" * 32, 5)[1], deadline_utc=at(500))],
    "a launch with a raised cap": [record("shimmer-loop-x-7", "7" * 32, 5)[0],
                                   dict(record("shimmer-loop-x-7", "7" * 32, 5)[1], cap_usd=9.0)],
    "an intent with no price": [{k: v for k, v in record("shimmer-loop-x-8", "8" * 32, 5)[0].items()
                                 if k != "price_usd_per_hour"}],
    "an intent with no deadline": [{k: v for k, v in record("shimmer-loop-x-9", "9" * 32, 5)[0].items() if k != "deadline_utc"}],
    "a termination naming another instance id": record("shimmer-loop-x-10", "a1" * 16, 5)[:2]
    + [dict(record("shimmer-loop-x-10", "a1" * 16, 5)[2], instance_id="b2" * 16)],
    "a negative cost": record("shimmer-loop-x-11", "c3" * 16, 5)[:2] + [dict(record("shimmer-loop-x-11", "c3" * 16, 5)[2], actual_cost=-1.0)],
    "a line naming no loop instance": [dict(record("shimmer-loop-x-12", "d4" * 16, 5)[0], instance_name="other-12")],
    "a hand copy of a launch from another ledger": [dict(record("shimmer-loop-x-13", "e5" * 16, 5)[1], copied_from="R_ledger")],
    "a line that is not JSON": ['{"event": "launch", "instance_name": "shimmer-loop-x-14"'],
    "a JSON line that is not an object": ["[1, 2]"],
}


def proof_461(mod=driver):
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        prior, added, _ = concurrent_lines()
        for n, (case, rows) in enumerate(BAD_CASES.items()):
            folder = Path(tmp) / str(n)
            folder.mkdir()
            records = Records(folder, prior=prior)
            records.append("budget_ledger", added + rows)
            reason, _found = stale(mod, records)
            out[case + " refused"] = bool(reason) and "after its read copy" in reason
        folder = Path(tmp) / "r"
        folder.mkdir()
        records = Records(folder, prior=prior)
        records.append("budget_ledger", added)
        records.append("r_ledger", [record("shimmer-loop-r-3", "9" * 32, 5)[1]])
        reason, _found = stale(mod, records)
        out["a launch with no intent in R's ledger refused"] = bool(reason) and "r_ledger" in reason
        folder = Path(tmp) / "clean"
        folder.mkdir()
        records = Records(folder, prior=prior)
        records.append("budget_ledger", added)
        out["the same ledger without them admitted (control)"] = stale(mod, records)[0] is None
    with tempfile.TemporaryDirectory() as tmp:
        rows, refusal, admitted, staged, _ = admit_with(mod, Path(tmp), BAD_CASES["a launch with no intent before it"])
        # Refused at the stale check, before anything is staged (as a stale copy always was).
        out["admit() refuses it before staging anything"] = (rows is None and "read copy is stale" in (refusal or "")
                                                             and not admitted and not staged)
    return all(out.values()), out


def proof_462(mod=driver):
    out = {}
    f = guard.forecast_usd(FORECAST_MINUTES, RATE)
    hard = round(guard.CAP_FACTOR * f, 4)
    room = 19.0 - STORAGE - guard.overrun_reserve([], RATE)
    with tempfile.TemporaryDirectory() as tmp:
        spent = record("shimmer-loop-big-1", "9a" * 16, 5, minutes=600, cost=round(room - f / 2, 4))
        rows, refusal, admitted, refused, _ = admit_with(mod, Path(tmp), spent)
        out["the guard refusing on the current ledgers refuses the admission"] = (
            rows is None and "guard refuses" in (refusal or "") and not admitted and refused)
    with tempfile.TemporaryDirectory() as tmp:
        # A cap between the forecast and the sealed hard cap: the guard admits a launch, but not this bundle's cap.
        spent = record("shimmer-loop-big-2", "9b" * 16, 5, minutes=600, cost=round(room - (f + hard) / 2, 4))
        rows, refusal, admitted, refused, _ = admit_with(mod, Path(tmp), spent)
        out["a cap below a bundle's sealed hard cap refuses"] = (
            rows is None and "below its sealed hard cap" in (refusal or "") and not admitted and refused)
    with tempfile.TemporaryDirectory() as tmp:
        spent = record("shimmer-loop-small-3", "9c" * 16, 5, minutes=10)
        rows, refusal, admitted, refused, _ = admit_with(mod, Path(tmp), spent)
        out["the same launch at its real cost admitted (control)"] = refusal is None and admitted
    request = {"argv": ["--forecast-minutes", "30", "--storage-forecast-usd", "0.5"]}
    abbreviated = {"argv": ["--forecast-minutes", "30", "--storage-forecast", "0.5"]}
    twice = {"argv": ["--storage-forecast-usd", "0.5", "--storage-forecast-usd=0"]}
    out["the storage forecast read only when named once in full"] = (
        mod.sealed_storage_forecast(request["argv"]) == 0.5 and mod.sealed_storage_forecast(abbreviated["argv"]) is None
        and mod.sealed_storage_forecast(twice["argv"]) is None)
    with tempfile.TemporaryDirectory() as tmp:
        records = Records(tmp)
        manifest = dict(instance_candidates=[dict(max_hourly_rate=RATE)], forecast_minutes=FORECAST_MINUTES,
                        workload_stop_reserve_seconds=RESERVE_SECONDS, hard_ceiling_usd=hard)
        out["a request without its storage forecast refuses"] = bool(mod.budget_reason(manifest, abbreviated, records.live, NOW))
        out["a manifest without its sealed figures refuses"] = bool(mod.budget_reason({}, request, records.live, NOW))
    return all(out.values()), out


def proof_463(mod=driver):
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        records = Records(tmp)
        records.append("budget_ledger", own_lines())
        reason, found = stale(mod, records)
        out["the job's own lines (as the controller writes them) admitted"] = reason is None and found == []
    with tempfile.TemporaryDirectory() as tmp:
        records = Records(tmp)
        # As the admission fixture holds them: a name-only intent, and the id on the launch and termination.
        records.append("budget_ledger", [{"event": "launch_intent", "instance_name": OWN_NAME},
                                         {"event": "launch", "instance_name": OWN_NAME, "instance_id": OWN_ID},
                                         {"event": "termination", "instance_id": OWN_ID},
                                         reaper_termination(OWN_NAME, "deadline", OWN_ID)])
        reason, found = stale(mod, records)
        out["name-only and id-only own lines admitted"] = reason is None and found == []
    with tempfile.TemporaryDirectory() as tmp:
        prior, added, foreign_count = concurrent_lines()
        records = Records(tmp, prior=prior)
        records.append("budget_ledger", added)
        reason, found = stale(mod, records)
        out["own lines among foreign ones admitted, not counted as foreign"] = reason is None and len(found) == foreign_count
    with tempfile.TemporaryDirectory() as tmp:
        rows, refusal, admitted, refused, rechecks = admit_with(mod, Path(tmp), [])
        out["own lines alone admit every bundle with no budget recheck"] = (
            refusal is None and admitted and rechecks == 0 and len(rows or []) == 3)
    return all(out.values()), out


def proof_464(mod=driver):
    out = {}

    def case(name, change, key="budget_ledger"):
        with tempfile.TemporaryDirectory() as tmp:
            prior, added, _ = concurrent_lines()
            records = Records(tmp, prior=prior + [record("shimmer-loop-old-1", "01" * 16, -100)[0]])
            path = records.live[key]
            path.write_bytes(change(path.read_bytes()))
            records.append("budget_ledger", added)
            reason, _found = stale(mod, records)
            out[name] = bool(reason) and "does not begin with its read copy" in reason
    lines = lambda data: data.splitlines(keepends=True)
    case("an earlier line removed refused", lambda d: b"".join(lines(d)[:1] + lines(d)[2:]))
    case("an earlier line rewritten, same length, refused", lambda d: d.replace(b'"price_usd_per_hour": 1.29', b'"price_usd_per_hour": 0.29', 1))
    case("the ledger cut below its copy refused", lambda d: b"".join(lines(d)[:2]))
    case("an earlier line moved refused", lambda d: b"".join([lines(d)[1], lines(d)[0]] + lines(d)[2:]))
    case("R's ledger rewritten refused", lambda d: d.replace(b"1.29", b"0.29", 1), key="r_ledger")
    case("the spend store rewritten refused", lambda d: d.replace(b"60.0", b"90.0"), key="spend_store")
    with tempfile.TemporaryDirectory() as tmp:
        prior, added, _ = concurrent_lines()
        records = Records(tmp, prior=prior)
        records.append("budget_ledger", added)
        records.append("spend_store", [{"event": "close", "spent_usd": 0.1}])
        out["nothing rewritten, a spend store appended to, admitted (control)"] = stale(mod, records)[0] is None
    return all(out.values()), out


# ---------------------------------------------------------------------------
# the neutralisations: each a copy of the driver with one passage changed


def _driver_with(*passages):
    source = DRIVER.read_text(encoding="utf-8")
    for old, new in passages:
        if source.count(old) != 1:
            raise RuntimeError("the passage moved, so the neutralisation cannot be applied: " + old[:60])
        source = source.replace(old, new)
    mod = types.ModuleType("seal_route_driver_neutralised")
    mod.__file__ = str(DRIVER)
    exec(compile(source, str(DRIVER), "exec"), mod.__dict__)
    return mod


NEUTRALISATIONS = {
    460: [("every foreign line refused, as before order 99",
           ("            problem = loop_record_reason(row, history)\n",
            "            problem = 'not the seal job\\'s own'\n"))],
    461: [("a launch with no intent admitted", ("        if not intents:\n            return 'a launch line with no",
                                               "        if False:\n            return 'a launch line with no")),
          ("any line kind admitted", ("    if event not in guard.EVENTS:\n", "    if False:\n")),
          ("a field outside IV.3 admitted", ("    extra = guard.undeclared(row)\n", "    extra = set()\n")),
          ("a second intent admitted", ("        if record:\n            return 'a launch_intent", "        if False:\n            return 'a launch_intent")),
          ("a launch's deadline and cap not held to its intent's",
           ("        if any(row.get(f) != intents[0].get(f) for f in ('deadline_utc', 'price_usd_per_hour', 'cap_usd')):",
            "        if False:")),
          ("an intent's price and cap not required", ("            if not _amount(row.get(field), True):\n", "            if False:\n")),
          ("a termination's id not held to its launch",
           ("    if iid is not None and launches and launches[-1].get('instance_id') != iid:", "    if False:"))],
    462: [("the budget recheck skipped", ("                if foreign:\n                    # Order 99",
                                          "                if False:\n                    # Order 99")),
          ("the sealed hard cap not compared", ("    if not math.isfinite(hard) or decision['cap_usd'] + 1e-9 < hard:",
                                                "    if not math.isfinite(hard):")),
          ("the storage forecast taken in any spelling",
           ("    if len(spelled) != 1 or argv[spelled[0]] != flag or spelled[0] + 1 >= len(argv):\n        return None\n",
            "    if not spelled:\n        return None\n"))],
    463: [("the job's own lines held as foreign", ("            if isinstance(row, dict) and _named(row) & own:\n",
                                                   "            if False:\n")),
          ("own lines alone rechecked", ("                if foreign:\n                    # Order 99",
                                         "                if True:\n                    # Order 99"))],
    464: [("the read copy not held as a prefix",
           ("        if len(data) < entry['bytes'] or hashlib.sha256(data[:entry['bytes']]).hexdigest() != entry['sha256']:\n"
            "            return 'the live %s does not begin with its read copy (rewritten, not appended)' % key\n", ""))],
}
PROOFS = {460: proof_460, 461: proof_461, 462: proof_462, 463: proof_463, 464: proof_464}
SAYS = {460: "complete guarded loop records of other instances admitted, the 16 November case end to end",
        461: "a malformed, other-kind or out-of-order foreign line refused",
        462: "a budget the current ledgers no longer carry refused, nothing admitted",
        463: "the seal job's own lines still verify and alone need no recheck",
        464: "a removed or rewritten earlier line refused"}


def _run(proof, mod):
    try:
        return proof(mod)
    except Exception as exc:
        return False, {"raised %s: %s" % (type(exc).__name__, str(exc)[:160]): False}


def run_check(number):
    """('PASS' or 'FAIL', detail): the proof passes on the driver, fails on each neutralised copy, passes again."""
    proof = PROOFS[number]
    ok, detail = _run(proof, driver)
    if not ok:
        return "FAIL", "%d: %s" % (number, "; ".join(k for k, v in detail.items() if not v))
    names = []
    for name, passage in NEUTRALISATIONS[number]:
        try:
            neutralised = _driver_with(passage)
        except RuntimeError as exc:
            return "FAIL", "%d: %s" % (number, exc)
        if _run(proof, neutralised)[0]:
            return "FAIL", "%d: still passes when neutralised (%s)" % (number, name)
        if not _run(proof, driver)[0]:
            return "FAIL", "%d: fails when restored (%s)" % (number, name)
        names.append(name)
    return "PASS", "%d proofs (%s), each neutralised, failed, restored, passed: %s" % (
        len(detail), SAYS[number], "; ".join(names))


def check():
    results = {n: run_check(n) for n in PROOFS}
    failed = [n for n, (status, _d) in results.items() if status != "PASS"]
    if failed:
        return "FAIL", "; ".join(results[n][1] for n in failed)
    return "PASS", "; ".join("%d %s" % (n, results[n][1]) for n in PROOFS)


def main(argv=None):
    numbers = [int(a) for a in (argv if argv is not None else sys.argv[1:]) if a.isdigit()] or sorted(PROOFS)
    failures = 0
    for number in numbers:
        status, detail = run_check(number)
        failures += status != "PASS"
        print(status, detail)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
