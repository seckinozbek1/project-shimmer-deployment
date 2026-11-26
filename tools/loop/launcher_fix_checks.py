#!/usr/bin/env python3
"""Gate proofs for beta items 25 and 26 (checks 705 and 706): temp fixture folders only, no provider call, no model.

705 (item 25, OPEN_ITEMS 174), tools/loop/prior_parts.py and the launch.py lines of docs/loop/LAUNCH_CHAIN.md
"Earlier parts":
  failed_table     an earlier batch part with a table at exit 2 refuses the next part, naming the count and the table
  clean            earlier parts all at exit 0, and an earlier part not launched, refuse nothing
  other_arm        a sibling folder of the same bench and set (another arm) with a failed earlier part refuses too
  short_end        a part still running with tables missing refuses nothing; the same part ended refuses
  failure          an earlier part with controller_failure.json refuses
  decision         D-NNN lets the launch go on (the override printed); a malformed id is a refusal
  launcher         a fixture launch.py with the documented lines: `launch.py V2` by hand refuses and launches
                   nothing, `launch.py V2 --decision D-1` and `launch.py V1` launch; a module that cannot be read
                   refuses the part
706 (item 26, OPEN_ITEMS 184), tools/loop/launch_chain.py and tools/loop/task_args_check.py:
  one_bundle_batch a part of one bundle run in batch form (batch_manifests.json) reads done from its batch entry,
                   failed when the entry's evidence is not exit 0; a plain one-bundle part still reads workload_return
  batch_file       one bundle with batch_<step>.json beside launch.py reads as a batch too
  ending           ledger ended but phase terminate_instance written a minute ago reads running; 30 minutes ago, or
                   with controller_failure, failed
  task_args        an argument holding `s05$d` is flagged twice (unexpanded variable, missing path); `$(eventId)`,
                   %TEMP% and existing paths are not
  cause            (an observation of Python, no neutralisation) a wrapper whose working folder does not exist exits 1
                   before any child starts, the 20:49 and 20:54 task results

Each proof is run as built (passes), with one line of the module neutralised (must fail), restored and run again.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "tools" / "loop"), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import launch_chain as lc  # noqa: E402
import mechanism_common as mc  # noqa: E402
import prior_parts as pp  # noqa: E402
import reasoning_methods_checks as rmc  # noqa: E402
import task_args_check as tac  # noqa: E402

caught, with_source = rmc.caught, rmc.with_source
SOURCE_EDIT = None      # (old, new) applied to prior_parts.py's text in the launcher proof (its neutralisation)


# ---- fixtures ----

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding="utf-8")
    return path


def evidence(path, code):
    """A collected_evidence.tar.gz holding evidence/result.json with pipeline_exit_code `code`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"pipeline_exit_code": code}).encode("utf-8")
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo("evidence/result.json")
        info.size = len(body)
        tar.addfile(info, io.BytesIO(body))


def measurement(base, name, parts, arm=None, bench="b", set_name="s"):
    """A launch folder: plan.json with `parts` {part: [bundles]}; returns its path."""
    folder = Path(base) / name
    plan = {"bundles": parts, "purposes": {p: "fx-" + p.lower() for p in parts}}
    if arm is not None:
        plan.update(bench=bench, set=set_name, arm=arm)
    write(folder / "plan.json", plan)
    return folder


def run_part(folder, part, exits, ended=True, failure=False, bundles=None, evidence_for=None, phase_age_s=None):
    """admitted/<first bundle>/batch/NN_<item>_B3/workload_return.json per exit code with its collected evidence
    (every table, or only the indices in evidence_for), the ending files when ended, and a CURRENT_PHASE.json
    written phase_age_s ago when given (a part whose controller stopped writing)."""
    plan = json.loads((Path(folder) / "plan.json").read_text(encoding="utf-8"))
    names = bundles or plan["bundles"][part]
    run = Path(folder) / "admitted" / names[0]
    for i, code in enumerate(exits):
        write(run / "batch" / ("%02d_%s_B3" % (i, names[i][-6:])) / "workload_return.json",
              {"epoch": 1.0, "exit_code": code, "full_run_retried": False})
        if evidence_for is None or i in evidence_for:
            write(run / "batch" / ("%02d_%s_B3" % (i, names[i][-6:])) / "collected_evidence.tar.gz", "x")
    if phase_age_s is not None:
        write(run / "CURRENT_PHASE.json", {"phase": "batch_workload", "epoch": time.time() - phase_age_s})
    if ended:
        write(run / "TERMINATION_VERIFIED.json", {"phase": "terminated"})
        write(run / "CURRENT_PHASE.json", {"phase": "terminated_and_cleaned", "epoch": time.time()})
    if failure:
        write(run / "controller_failure.json", {"error_type": "RuntimeError", "message": "x"})
    return run


THREE = {"V1": ["M_V1_aaaaaa", "M_V1_bbbbbb", "M_V1_cccccc"], "V2": ["M_V2_dddddd", "M_V2_eeeeee"]}


# ---- 705 proofs ----

def observe_failed_table():
    with tempfile.TemporaryDirectory() as base:
        f = measurement(base, "M_OFF", THREE)
        run_part(f, "V1", [0, 2, 0])
        line = pp.refusal(f, "V2")
        return bool(line) and "1 of 3 tables with a non-zero exit code" in line and "01_bbbbbb_B3 exit 2" in line, \
            pp.refusal(f, "V1")


def expected_failed_table():
    return True, None


def observe_clean():
    with tempfile.TemporaryDirectory() as base:
        f = measurement(base, "M_OFF", dict(THREE, V3=["M_V3_ffffff"]))
        run_part(f, "V1", [0, 0, 0])
        return pp.refusal(f, "V2"), pp.refusal(f, "V3")


def expected_clean():
    return None, None


def observe_other_arm():
    with tempfile.TemporaryDirectory() as base:
        off = measurement(base, "M_OFF", THREE, arm="off")
        on = measurement(base, "M_ON", THREE, arm="on")
        other = measurement(base, "M_OTHER", THREE, arm="on", set_name="another")
        run_part(off, "V1", [0, 0, 2])
        run_part(on, "V1", [0, 0, 0])
        run_part(other, "V1", [0, 0, 0])
        line = pp.refusal(on, "V2")
        return bool(line) and "M_OFF V1: 1 of 3" in line, pp.refusal(other, "V2")


def expected_other_arm():
    return True, None


def observe_short_end():
    with tempfile.TemporaryDirectory() as base:
        f = measurement(base, "M_OFF", THREE)
        run = run_part(f, "V1", [0], ended=False)
        running = pp.refusal(f, "V2")
        write(run / "TERMINATION_VERIFIED.json", {"phase": "terminated"})
        line = pp.refusal(f, "V2")
        return running, bool(line) and "ended (termination verified) with 1 of 3 tables returned" in line


def expected_short_end():
    return None, True


def observe_failure():
    with tempfile.TemporaryDirectory() as base:
        f = measurement(base, "M_OFF", THREE)
        run_part(f, "V1", [0, 0], ended=False, failure=True)
        line = pp.refusal(f, "V2")
        return bool(line) and "controller_failure RuntimeError" in line


def expected_failure():
    return True


def observe_decision():
    with tempfile.TemporaryDirectory() as base:
        f = measurement(base, "M_OFF", THREE)
        run_part(f, "V1", [2, 0, 0])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            allowed = pp.refusal(f, "V2", "D-900")
        bad = pp.refusal(f, "V2", "because")
        return allowed, "launched under D-900" in out.getvalue(), bool(bad) and "not of the form D-NNN" in bad


def expected_decision():
    return None, True, True


def observe_entry_failure():
    with tempfile.TemporaryDirectory() as base:
        f = measurement(base, "M_OFF", THREE)
        run = run_part(f, "V1", [0, 0], ended=False)
        write(run / "batch" / "02_cccccc_B3" / "entry_failure.json", {"error_type": "TransportFailure"})
        line = pp.refusal(f, "V2")
        return bool(line) and "1 of 3 tables with entry_failure.json (02_cccccc_B3)" in line


def expected_entry_failure():
    return True


def observe_no_evidence():
    with tempfile.TemporaryDirectory() as base:
        f = measurement(base, "M_OFF", THREE)
        run_part(f, "V1", [0, 0, 0], evidence_for=(0, 2))
        line = pp.refusal(f, "V2")
        g = measurement(base, "M_RUN", THREE)
        run_part(g, "V1", [0, 0, 0], ended=False, evidence_for=(0, 2))
        return bool(line) and "1 tables without collected_evidence.tar.gz (01_bbbbbb_B3)" in line, pp.refusal(g, "V2")


def expected_no_evidence():
    return True, None


def observe_killed():
    with tempfile.TemporaryDirectory() as base:
        stale = measurement(base, "M_STALE", THREE)
        run_part(stale, "V1", [0], ended=False, phase_age_s=7 * 3600)
        fresh = measurement(base, "M_FRESH", THREE)
        run_part(fresh, "V1", [0], ended=False, phase_age_s=600)
        closed = measurement(base, "M_CLOSED", THREE)
        run_part(closed, "V1", [0], ended=False, phase_age_s=600)
        ledger = Path(base) / "ledger.jsonl"
        ledger.write_text("\n".join(json.dumps(r) for r in (
            {"event": "launch", "purpose": "fx-v1"}, {"event": "termination", "purpose": "fx-v1"})) + "\n", encoding="utf-8")
        a = pp.refusal(stale, "V2")
        b = pp.refusal(fresh, "V2")
        with patch.object(pp, "LEDGER", ledger):
            c = pp.refusal(closed, "V2")
        return (bool(a) and "no phase written for 7.0 hours" in a and "1 of 3 tables returned" in a, b,
                bool(c) and "ended (ledger termination) with 1 of 3" in c)


def expected_killed():
    return True, None, True


LAUNCH_PY = r'''
import importlib.util, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
M = Path(sys.argv[1])
BUNDLES = json.loads((HERE / 'plan.json').read_text(encoding='utf-8'))['bundles']


def prior_part_problem(step, decision=None):
    try:
        spec = importlib.util.spec_from_file_location('prior_parts', M / 'tools' / 'loop' / 'prior_parts.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.refusal(HERE, step, decision)
    except Exception as exc:
        return 'tools/loop/prior_parts.py could not be read (%s): the part is not launched' % type(exc).__name__


def preflight(disk_floor, step='preflight', decision=None):
    problems = []
    if step in BUNDLES:
        prior = prior_part_problem(step, decision)
        if prior:
            problems.append(prior)
    print('preflight %s: %s' % (step, '; '.join(problems) or 'all checks hold'), flush=True)
    if problems:
        raise SystemExit('Stop and tell the lead (%d problems)' % len(problems))


def main(args):
    decision = None
    if '--decision' in args:
        i = args.index('--decision')
        decision = args[i + 1] if i + 1 < len(args) else ''
        del args[i:i + 2]
    step = args[0]
    if step in BUNDLES:
        preflight(11.0, step, decision)
        (HERE / ('LAUNCHED_%s' % step)).write_text('x', encoding='utf-8')
        return 0
    raise SystemExit('unknown step')


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[2:]))
'''


def _launch(folder, root, *args):
    done = subprocess.run([sys.executable, "-X", "utf8", str(Path(folder) / "launch.py"), str(root)] + list(args),
                          capture_output=True, text=True, timeout=120, creationflags=mc.no_window())
    return done.returncode


def observe_launcher():
    with tempfile.TemporaryDirectory() as base:
        root = Path(base) / "main"
        text = Path(pp.__file__).read_text(encoding="utf-8")
        if SOURCE_EDIT:
            if text.count(SOURCE_EDIT[0]) != 1:
                raise AssertionError("the neutralisation's line is not in prior_parts.py once")
            text = text.replace(*SOURCE_EDIT)
        write(root / "tools" / "loop" / "prior_parts.py", text)
        f = measurement(base, "M_OFF", THREE)
        write(f / "launch.py", LAUNCH_PY)
        run_part(f, "V1", [0, 2, 0])
        by_hand = _launch(f, root, "V2")
        held = not (f / "LAUNCHED_V2").exists()
        first = _launch(f, root, "V1")
        decided = _launch(f, root, "V2", "--decision", "D-1")
        launched = (f / "LAUNCHED_V2").exists()
        (f / "LAUNCHED_V2").unlink()
        unreadable = _launch(f, Path(base) / "nowhere", "V2")
        return by_hand != 0, held, first, decided, launched, unreadable != 0, not (f / "LAUNCHED_V2").exists()


def expected_launcher():
    return True, True, 0, 0, True, True, True


# ---- 706 proofs ----

def chain_step(name):
    return {"step": name, "kind": "ledger", "purpose": "fx-" + name}


def ended_row(run, cost=0.5):
    """What launch.py status prints for an ended part: the phase files' kept keys (launch.py phase())."""
    phase = {}
    for name in ("CURRENT_PHASE.json", "controller_failure.json", "TERMINATION_VERIFIED.json", "workload_return.json"):
        if (run / name).is_file():
            value = json.loads((run / name).read_text(encoding="utf-8"))
            phase[name.split(".")[0]] = {k: value.get(k) for k in ("phase", "error_type", "message", "exit_code")
                                         if k in value}
    return {"cost": cost, "state": "ended", "phase": phase}


def one_bundle(base, name, code, how="manifests"):
    f = measurement(base, name, {"r1": ["STR_111111111111"]})
    run = f / "admitted" / "STR_111111111111"
    if how == "manifests":
        write(run / "batch_manifests.json", ["0" * 64])
    else:
        write(f / "batch_r1.json", {"form": "b3_only", "entries": []})
    write(run / "batch" / "00_111111111111_B3" / "workload_return.json", {"exit_code": code})
    evidence(run / "batch" / "00_111111111111_B3" / "collected_evidence.tar.gz", code)
    write(run / "TERMINATION_VERIFIED.json", {"phase": "terminated"})
    write(run / "CURRENT_PHASE.json", {"phase": "terminated_and_cleaned", "epoch": time.time()})
    return f, run


def observe_one_bundle_batch():
    with tempfile.TemporaryDirectory() as base:
        good, run = one_bundle(base, "QG", 0)
        bad, run_bad = one_bundle(base, "QB", 2)
        plain = measurement(base, "QP", {"r1": ["STR_222222222222"]})
        prun = plain / "admitted" / "STR_222222222222"
        write(prun / "workload_return.json", {"exit_code": 0})
        write(prun / "CURRENT_PHASE.json", {"phase": "terminated_and_cleaned", "epoch": time.time()})
        return (lc.own_state(good, chain_step("r1"), {"r1": ended_row(run)})[0],
                lc.own_state(bad, chain_step("r1"), {"r1": ended_row(run_bad)})[0],
                lc.own_state(plain, chain_step("r1"), {"r1": ended_row(prun)})[0])


def expected_one_bundle_batch():
    return "done", "failed", "done"


def observe_batch_file():
    with tempfile.TemporaryDirectory() as base:
        f, run = one_bundle(base, "QF", 0, how="file")
        return lc.own_state(f, chain_step("r1"), {"r1": ended_row(run)})[0]


def expected_batch_file():
    return "done"


def observe_ending():
    with tempfile.TemporaryDirectory() as base:
        f = measurement(base, "QE", {"D2": ["B_%012d" % i for i in range(3)]})
        run = f / "admitted" / "B_000000000000"
        write(run / "CURRENT_PHASE.json", {"phase": "terminate_instance", "epoch": time.time() - 60})
        fresh = lc.own_state(f, chain_step("D2"), {"D2": ended_row(run)})
        write(run / "CURRENT_PHASE.json", {"phase": "terminate_instance", "epoch": time.time() - 30 * 60})
        old = lc.own_state(f, chain_step("D2"), {"D2": ended_row(run)})[0]
        write(run / "CURRENT_PHASE.json", {"phase": "terminate_instance", "epoch": time.time() - 60})
        write(run / "controller_failure.json", {"error_type": "RuntimeError"})
        failed = lc.own_state(f, chain_step("D2"), {"D2": ended_row(run)})[0]
        return fresh[0], fresh[1].startswith("ending: phase terminate_instance"), old, failed


def expected_ending():
    return "running", True, "failed", "failed"


def observe_ending_retry():
    with tempfile.TemporaryDirectory() as base:
        f = measurement(base, "QR", {"D2": ["B_%012d" % i for i in range(3)]})
        first = f / "admitted" / "B_000000000000"
        retry = f / "admitted" / "B_000000000000.2"
        write(first / "CURRENT_PHASE.json", {"phase": "terminate_instance", "epoch": time.time() - 3 * 3600})
        write(retry / "CURRENT_PHASE.json", {"phase": "terminate_instance", "epoch": time.time() - 60})
        row = ended_row(first)
        by_file = lc.own_state(f, chain_step("D2"), {"D2": row})[0]
        reported = dict(row, phase={"CURRENT_PHASE": {"phase": "terminate_instance", "epoch": time.time() - 30}})
        write(retry / "CURRENT_PHASE.json", {"phase": "terminate_instance", "epoch": time.time() - 3 * 3600})
        by_row = lc.own_state(f, chain_step("D2"), {"D2": reported})[0]
        return by_file, by_row


def expected_ending_retry():
    return "running", "running"


TASK_ROOT_706 = "C:\\shimmer_fixture_706"   # Windows form on every host: Task Scheduler paths are Windows paths


def observe_task_args():
    # task_args_check reads Windows Task Scheduler actions, so its ABSOLUTE pattern knows C:\ and \\server\ only; a
    # temp folder on Linux (/tmp/...) would never be read as a path. The fixture's paths are Windows paths on every
    # host and which of them exist is declared here, so no file is written and the host's file system is not asked.
    here = TASK_ROOT_706
    s05 = here + "\\s05"
    pyw = s05 + "\\UNT_after_gated.pyw"
    present = {here + "\\py.exe", s05, pyw}
    bad = {"task": "T1", "state": "Disabled", "execute": here + "\\py.exe",
           "arguments": '-3.12 "%s" "%s"' % (pyw, s05 + "$d")}
    good = {"task": "T2", "state": "Ready", "execute": pyw,
            "arguments": '-X utf8 "%s" --event-id $(eventId) "%%TEMP%%"' % s05}
    exists = lambda p: p in present or (not p.startswith(here) and Path(p).exists())  # noqa: E731
    lines, n = tac.report([bad, good], exists=exists)
    kinds = sorted(k for _f, k, _t in tac.problems(bad, exists))
    return n, kinds, any("$d" in x for x in lines), tac.problems(good, exists)


def expected_task_args():
    return 2, ["missing", "variable"], True, []


def observe_cause():
    with tempfile.TemporaryDirectory() as base:
        wrapper = write(Path(base) / "gated.py", "import subprocess, sys\nfrom pathlib import Path\n"
                        "folder = Path(sys.argv[1])\n"
                        "raise SystemExit(subprocess.run([sys.executable, '-c', 'pass'], cwd=str(folder),"
                        " stdin=subprocess.DEVNULL).returncode)\n")
        codes = []
        for folder in (Path(base) / "s05$d", Path(base)):
            codes.append(subprocess.run([sys.executable, str(wrapper), str(folder)], capture_output=True,
                                        timeout=60, creationflags=mc.no_window()).returncode)
        return codes


def expected_cause():
    return [1, 0]


PROOFS_705 = ("failed_table", "clean", "other_arm", "short_end", "failure", "decision", "launcher", "entry_failure",
              "no_evidence", "killed")
PROOFS_706 = ("one_bundle_batch", "batch_file", "ending", "ending_retry", "task_args", "cause")
NEUTRALISATIONS_705 = {
    "entry_failure_ignored": (lambda: with_source(pp, "part_problem", "    if failed:\n", "    if False:\n"), ("entry_failure",)),
    "evidence_ignored": (lambda: with_source(pp, "part_problem", "    if no_evidence:\n", "    if False:\n"), ("no_evidence",)),
    "stale_ignored": (lambda: with_source(pp, "ended", "if age is not None and age > STALE_PHASE_HOURS:", "if False:"),
                      ("killed",)),
    "ledger_ignored": (lambda: with_source(pp, "ended", "    if ledger_terminated(purpose):\n", "    if False:\n"),
                       ("killed",)),
    "exit_ignored": (lambda: with_source(pp, "part_problem", "    if bad:\n", "    if False:\n"),
                     ("failed_table", "other_arm", "decision")),
    "arms_ignored": (lambda: with_source(pp, "problems", "for other in arms_of(folder, plan):", "for other in []:"),
                     ("other_arm",)),
    "short_end_ignored": (lambda: with_source(pp, "part_problem", "if len(returned) < len(bundles):",
                                              "if False:"), ("short_end",)),
    "failure_ignored": (lambda: with_source(pp, "part_problem", "if (run / 'controller_failure.json').is_file():",
                                            "if False:"), ("failure",)),
    "decision_unchecked": (lambda: with_source(pp, "refusal", "if not DECISION.match(str(decision)):", "if False:"),
                           ("decision",)),
    "launcher_module_lax": (lambda: patch.object(sys.modules[__name__], "SOURCE_EDIT",
                                                 ("    if bad:\n", "    if False:\n")), ("launcher",)),
}
NEUTRALISATIONS_706 = {
    "first_attempt_only": (lambda: with_source(lc, "phase_age_minutes", "run = latest_run_folder(folder, step, bundles)",
                                               "run = batch_run_folder(folder, step, bundles)"), ("ending_retry",)),
    "reported_epoch_ignored": (lambda: with_source(lc, "phase_age_minutes",
                                                   "    reported = ((row or {}).get('phase') or {}).get('CURRENT_PHASE') or {}\n",
                                                   "    reported = {}\n"), ("ending_retry",)),
    "many_bundles_only": (lambda: with_source(lc, "own_state", "if batch_form(folder, step, bundles):",
                                              "if bundles and len(bundles) > 1:"), ("one_bundle_batch", "batch_file")),
    "manifests_ignored": (lambda: with_source(lc, "batch_form", "return run is not None and (run / 'batch_manifests"
                                              ".json').is_file() and not through_links(folder, run)", "return False"),
                          ("one_bundle_batch",)),
    "batch_file_ignored": (lambda: with_source(lc, "batch_form", "if (Path(folder) / ('batch_%s.json' % step['step']))"
                                               ".is_file():", "if False:"), ("batch_file",)),
    "ending_failed": (lambda: with_source(lc, "batch_state", "if current == ENDING_PHASE and 'controller_failure' "
                                          "not in phase:", "if False:"), ("ending",)),
    "ending_unbounded": (lambda: with_source(lc, "batch_state", "if age is not None and age <= ENDING_MINUTES:",
                                             "if age is not None:"), ("ending",)),
    "variable_unseen": (lambda: patch.object(tac, "VARIABLE", re.compile(r"(?!)")), ("task_args",)),
    "event_value_flagged": (lambda: patch.object(tac, "VARIABLE", re.compile(r"\$\(?([A-Za-z_][A-Za-z0-9_]*)")),
                            ("task_args",)),
    "missing_unseen": (lambda: with_source(tac, "problems", "if ABSOLUTE.match(expanded) and not exists(expanded):",
                                           "if False:"), ("task_args",)),
}


def run_set(proofs, neutralisations, summary):
    space = globals()
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            first = {n: space["observe_" + n]() for n in proofs}
            broken = {}
            for name, (make, names) in neutralisations.items():
                with make():
                    broken[name] = {n: caught(space["observe_" + n]) for n in names}
            again = {n: space["observe_" + n]() for n in proofs}
    except Exception as exc:
        return "FAIL", "%s %s" % (type(exc).__name__, str(exc)[:300])
    expected = {n: space["expected_" + n]() for n in proofs}
    for n in proofs:
        if first[n] != expected[n]:
            return "FAIL", "%s as built: %s" % (n, str(first[n])[:700])
        if again[n] != expected[n]:
            return "FAIL", "%s after restore: %s" % (n, str(again[n])[:400])
    for name, (_make, names) in neutralisations.items():
        for n in names:
            if broken[name][n] == expected[n]:
                return "FAIL", "%s still passes when %s is neutralised" % (n, name)
    return "PASS", "%d proofs, %d neutralisations, fail, restore, pass: %s (%s)" % (
        len(proofs), len(neutralisations), summary, ", ".join(proofs))


def run_705():
    with tempfile.TemporaryDirectory() as base:
        empty = Path(base) / "ledger.jsonl"
        empty.write_text("", encoding="utf-8")
        with patch.object(pp, "LEDGER", empty):
            return _run_705()


def _run_705():
    return run_set(PROOFS_705, NEUTRALISATIONS_705,
                   "a hand launch of part N+1 refuses while an earlier part of this or another arm has a table with a "
                   "non-zero exit code, a controller failure or ended short; a decision id overrides; a launcher "
                   "that cannot read the rule refuses")


def run_706():
    return run_set(PROOFS_706, NEUTRALISATIONS_706,
                   "a one-bundle batch part reads from its batch entry, a part in terminate_instance reads running "
                   "for 15 minutes, a task argument with an unexpanded variable or a missing path is flagged")


if __name__ == "__main__":
    worst = 0
    for label, fn in (("705", run_705), ("706", run_706)):
        status, detail = fn()
        print(label, status, detail)
        worst = max(worst, 0 if status == "PASS" else 1)
    sys.exit(worst)
