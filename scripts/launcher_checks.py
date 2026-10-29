"""Gate checks for the root launchers (loop stage S7, item 5).

The launchers are shimmer.bat (Windows), shimmer.sh (macOS, Linux and Git Bash
on Windows) and start_shimmer.bat (the desktop starter). Each check below drives
the REAL launcher text, copied into a temporary folder beside stand-ins for the
few files it calls (the runtime contract, the preflight, the intake wizard and
the venv's activate script), so nothing is installed, no model is loaded, no
review starts and the repository is never written. Every fix is proved by
neutralise, fail, restore, pass: the defect is put back into the copied text,
the run must show it, and the restored text must pass again.

  check_end_of_input   both menus end when their input ends; the Git Bash
                       token question treats the end of input as a no.
  check_bootstrap      shimmer.bat reaches its menu (the for /f quoting), keeps
                       its input through the venv's activate script, honours
                       SHIMMER_SKIP_INSTALL; shimmer.sh finds a Windows venv
                       (Scripts/) and honours SHIMMER_SKIP_INSTALL; the draft
                       path announces the draft only once setup succeeded; no
                       batch label is dead and no goto names a missing label;
                       start_shimmer.bat --check-entry answers.
  check_banner         the server banner in both launchers names exactly the
                       routes the app answers without a token.

A launcher file that is absent (the container image ships none) is skipped with
that reason. The batch half needs cmd.exe and runs on Windows only; the shell
half needs a bash that is not the WSL launcher.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BAT = ROOT / "shimmer.bat"
SH = ROOT / "shimmer.sh"
START = ROOT / "start_shimmer.bat"
RESOLVE = ROOT / "tools" / "resolve_python.bat"

PASS_BOUND_SECONDS = 30
LOOP_PROBE_SECONDS = 8
LOOP_REDRAWS = 20
MENU_PROMPT = "Choose an option [1-5, Q]:"
PROOFS = []


# --- stand-ins written into each temporary launcher folder ------------------

_CONTRACT_STUB = """import os, sys
args = sys.argv[1:]
if "--resolve" in args:
    print(os.environ.get("LAUNCHER_CHECK_PYTHON") or sys.executable)
sys.exit(0)
"""

_PREFLIGHT_STUB = """import sys
print("STUB_PREFLIGHT " + " ".join(sys.argv[1:]))
sys.exit(0)
"""

_WIZARD_STUB = """import sys
print("STUB_WIZARD " + " ".join(sys.argv[1:]))
sys.exit(1)
"""


def _windows():
    return os.name == "nt"


def _bash():
    """A bash that runs the script itself. On Windows that is Git's bash, found
    beside git; the System32 bash is the WSL launcher and is never used."""
    if _windows():
        git = shutil.which("git")
        if not git:
            return None
        # git sits in <Git>/cmd, <Git>/bin or <Git>/mingw64/bin, so look upward.
        for base in list(Path(git).resolve().parents)[:3]:
            for candidate in (base / "usr" / "bin" / "bash.exe", base / "bin" / "bash.exe"):
                if candidate.is_file():
                    return str(candidate)
        return None
    return shutil.which("bash")


def _write(path, text, crlf=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\r\n", "\n")
    if crlf:
        data = data.replace("\n", "\r\n")
    path.write_bytes(data.encode("utf-8"))


def _clean_env(tmp):
    env = dict(os.environ)
    for name in ("SHIMMER_TOKEN_HASH", "SHIMMER_BACKEND_PROFILE", "SHIMMER_SKIP_INSTALL",
                 "LAUNCHER_CHECK_PYTHON", "VIRTUAL_ENV"):
        env.pop(name, None)
    env.update({"SHIMMER_SKIP_INSTALL": "1", "PIP_NO_INDEX": "1",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1", "TMPDIR": str(tmp), "TEMP": str(tmp),
                "TMP": str(tmp), "PYTHONIOENCODING": "utf-8"})
    return env


def _run(argv, cwd, env, answers, timeout):
    """Run with answers as a FILE on stdin: cmd's set /p loses everything after
    the first line of a pipe, so a pipe would test cmd, not the launcher."""
    feed = Path(cwd) / "answers.txt"
    feed.write_bytes(answers.encode("utf-8"))
    log = Path(cwd) / "launcher_output.txt"
    with open(feed, "rb") as stdin, open(log, "wb") as sink:
        # Output goes to a file, not a pipe: a timed-out launcher's children
        # would otherwise hold the pipe open and the wait would never end.
        proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=stdin,
                                stdout=sink, stderr=subprocess.STDOUT)
        try:
            proc.wait(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc)
    out = log.read_bytes().decode("utf-8", errors="replace")
    return {"rc": None if timed_out else proc.returncode, "out": out, "timed_out": timed_out}


def _kill_tree(proc):
    """Stop the launcher and every process it started (Git's bash.exe is a
    wrapper that starts a second bash, which a plain kill leaves running)."""
    if _windows():
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, timeout=30)
    else:
        proc.kill()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass


# --- the batch launcher -------------------------------------------------------

def _bat_fixture(tmp, text):
    """A folder shimmer.bat can start in. The activate stand-in reads the rest
    of its input, exactly what the real activate script's chcp child does, so a
    call without its own input loses every later answer."""
    _write(tmp / "shimmer.bat", text, crlf=True)
    _write(tmp / "tools" / "resolve_python.bat",
           '@echo off\nset "SHIMMER_PYTHON=%s"\nexit /b 0\n' % sys.executable, crlf=True)
    _write(tmp / "tools" / "runtime_contract.py", _CONTRACT_STUB)
    _write(tmp / "scripts" / "preflight.py", _PREFLIGHT_STUB)
    _write(tmp / "scripts" / "intake_wizard.py", _WIZARD_STUB)
    _write(tmp / ".venv" / "Scripts" / "activate.bat",
           '@echo off\n"%PYTHON_CMD%" -c "import sys; sys.stdin.read()"\n', crlf=True)


def _drive_bat(text, answers, timeout=PASS_BOUND_SECONDS):
    with tempfile.TemporaryDirectory(prefix="shimmer_launcher_bat_", ignore_cleanup_errors=True) as td:
        tmp = Path(td)
        _bat_fixture(tmp, text)
        return _run(["cmd.exe", "/d", "/c", "shimmer.bat"], tmp, _clean_env(tmp), answers, timeout)


def _neutralise(text, old, new, label):
    if old not in text:
        raise AssertionError("cannot neutralise %s: the expected text is not in the launcher" % label)
    return text.replace(old, new, 1)


def _batch_labels(text):
    """Dead labels and missing goto targets in one batch file. A label is live
    when a goto or call names it; :eof is cmd's own."""
    labels = {m.group(1).lower() for m in re.finditer(r"(?im)^\s*:([A-Za-z_][\w-]*)", text)}
    jumps = {m.group(1).lower() for m in re.finditer(r"(?i)\bgoto\s+:?([A-Za-z_][\w-]*)", text)}
    calls = {m.group(1).lower() for m in re.finditer(r"(?i)\bcall\s+:([A-Za-z_][\w-]*)", text)}
    targets = (jumps | calls) - {"eof"}
    return sorted(labels - targets), sorted(targets - labels)


# --- the shell launcher -------------------------------------------------------

def _posix(path):
    return Path(path).as_posix()


def _sh_fixture(tmp, text, layout="Scripts"):
    """A folder shimmer.sh can start in. python3 on PATH is a stand-in that
    refuses -m (venv, pip) with a marker and passes everything else to this
    interpreter, so an attempted install or venv creation is seen, never done."""
    _write(tmp / "shimmer.sh", text)
    _write(tmp / "tools" / "runtime_contract.py", _CONTRACT_STUB)
    _write(tmp / "scripts" / "preflight.py", _PREFLIGHT_STUB)
    _write(tmp / "scripts" / "intake_wizard.py", _WIZARD_STUB)
    _write(tmp / ".venv" / layout / "activate", "# stand-in\n")
    fake = tmp / "fakebin" / "python3"
    _write(fake, '#!/usr/bin/env bash\nif [ "$1" = "-m" ]; then echo "STUB_PYTHON refused -m $2"; exit 1; fi\n'
                 'exec "%s" "$@"\n' % _posix(sys.executable))
    os.chmod(fake, 0o755)
    return fake


def _drive_sh(bash, text, answers, timeout=PASS_BOUND_SECONDS, layout="Scripts"):
    with tempfile.TemporaryDirectory(prefix="shimmer_launcher_sh_", ignore_cleanup_errors=True) as td:
        tmp = Path(td)
        fake = _sh_fixture(tmp, text, layout)
        env = _clean_env(tmp)
        env["PATH"] = str(fake.parent) + os.pathsep + env.get("PATH", "")
        env["LAUNCHER_CHECK_PYTHON"] = _posix(fake)
        return _run([bash, _posix(tmp / "shimmer.sh")], tmp, env, answers, timeout)


# --- proofs ---------------------------------------------------------------------

def _loops(result):
    return result["timed_out"] and result["out"].count(MENU_PROMPT) >= LOOP_REDRAWS


def _ended(result):
    return (not result["timed_out"]) and result["rc"] == 0


def _prove(name, passed_now, neutralised_fails, restored_passes):
    if not passed_now:
        raise AssertionError("%s: the launcher as shipped fails" % name)
    if not neutralised_fails:
        raise AssertionError("%s: the neutralised launcher did not show the defect, so the check proves nothing" % name)
    if not restored_passes:
        raise AssertionError("%s: the restored launcher does not pass" % name)
    PROOFS.append(name)


def _bat_end_of_input():
    text = BAT.read_text(encoding="utf-8")
    ok = _drive_bat(text, "L\r\n")
    passed = (_ended(ok) and "Leaving the menu." in ok["out"]
              and ok["out"].count(MENU_PROMPT) == 3)
    guard = text[text.index("if not defined choice ("):text.index('set "EMPTY_ANSWERS=0"\n\nif /i')]
    broken = _drive_bat(_neutralise(text, guard, "", "the empty-answer guard"), "L\r\n",
                        timeout=LOOP_PROBE_SECONDS)
    again = _drive_bat(text, "L\r\n")
    _prove("bat menu ends at end of input", passed, _loops(broken),
           _ended(again) and "Leaving the menu." in again["out"])


def _sh_end_of_input(bash):
    text = SH.read_text(encoding="utf-8")
    ok = _drive_sh(bash, text, "L\n")
    passed = _ended(ok) and "End of input. Goodbye." in ok["out"]
    old = 'if ! read -r choice; then\n        echo\n        echo "End of input. Goodbye."\n        exit 0\n    fi'
    broken = _drive_sh(bash, _neutralise(text, old, "read -r choice", "the menu read"), "L\n",
                       timeout=LOOP_PROBE_SECONDS)
    again = _drive_sh(bash, text, "L\n")
    _prove("sh menu ends at end of input", passed, _loops(broken),
           _ended(again) and "End of input. Goodbye." in again["out"])

    ok = _drive_sh(bash, text, "L\n3\n")
    declined = "No token generated. The server was not started." in ok["out"] and "Access token" not in ok["out"]
    broken = _drive_sh(bash, _neutralise(text, 'read -r gen || gen="n"', "read -r gen", "the token question"),
                       "L\n3\n")
    again = _drive_sh(bash, text, "L\n3\n")
    _prove("sh token question reads the end of input as no", _ended(ok) and declined,
           "Access token" in broken["out"],
           "No token generated." in again["out"] and "Access token" not in again["out"])


def _bat_bootstrap():
    text = BAT.read_text(encoding="utf-8")
    # The for /f quoting: without the outer pair the menu is never reached.
    ok = _drive_bat(text, "L\r\nQ\r\n")
    reached = _ended(ok) and MENU_PROMPT in ok["out"] and "Goodbye." in ok["out"]
    quoted = ("('\"\"!SHIMMER_PYTHON!\" tools\\runtime_contract.py --resolve --candidate "
              "\"%CD%\\.venv\\Scripts\\python.exe\" --path-only\"')")
    unquoted = ("('\"!SHIMMER_PYTHON!\" tools\\runtime_contract.py --resolve --candidate "
                "\"%CD%\\.venv\\Scripts\\python.exe\" --path-only')")
    broken = _drive_bat(_neutralise(text, quoted, unquoted, "the for /f quoting"), "L\r\nQ\r\n")
    again = _drive_bat(text, "L\r\nQ\r\n")
    _prove("bat for /f quoting reaches the menu", reached,
           broken["rc"] == 1 and MENU_PROMPT not in broken["out"],
           _ended(again) and MENU_PROMPT in again["out"])

    # The activate call keeps the answers that follow it.
    local = "Backend profile: local" in ok["out"] and "STUB_PREFLIGHT --backend-profile local" in ok["out"]
    broken = _drive_bat(_neutralise(text, 'call ".venv\\Scripts\\activate.bat" < nul',
                                    'call ".venv\\Scripts\\activate.bat"', "the activate input"),
                        "L\r\nQ\r\n")
    again = _drive_bat(text, "L\r\nQ\r\n")
    _prove("bat answers survive the activate script", local,
           "Backend profile: cloud" in broken["out"], "Backend profile: local" in again["out"])

    # SHIMMER_SKIP_INSTALL skips the install.
    skipped = "the dependency install and the CUDA torch swap are skipped" in ok["out"] \
        and "Installing dependencies" not in ok["out"]
    broken = _drive_bat(_neutralise(text, 'if "!SHIMMER_SKIP_INSTALL!"=="1" (',
                                    'if "!SHIMMER_SKIP_INSTALL!"=="never" (', "the install skip"),
                        "L\r\nQ\r\n")
    again = _drive_bat(text, "L\r\nQ\r\n")
    _prove("bat SHIMMER_SKIP_INSTALL skips the install", skipped,
           "Installing dependencies" in broken["out"],
           "Installing dependencies" not in again["out"] and _ended(again))

    # The draft is announced only after its setup succeeded.
    answers = "L\r\n1\r\nD\r\nA question\r\nQ\r\n"
    ok = _drive_bat(text, answers)
    quiet = "Draft setup cancelled." in ok["out"] and "Drafting a memo" not in ok["out"]
    early = ('set "DRAFT_FLAGS_FILE=%TEMP%\\shimmer_draft_flags.txt"',
             'echo Drafting a memo, then reviewing it ...\nset "DRAFT_FLAGS_FILE=%TEMP%\\shimmer_draft_flags.txt"')
    broken = _drive_bat(_neutralise(text, early[0], early[1], "the early draft line"), answers)
    again = _drive_bat(text, answers)
    _prove("bat draft is announced only after setup", quiet,
           "Drafting a memo" in broken["out"] and "Draft setup cancelled." in broken["out"],
           "Drafting a memo" not in again["out"])


def _bat_labels():
    files = [p for p in (BAT, START, RESOLVE) if p.is_file()]
    problems = []
    for path in files:
        dead, missing = _batch_labels(path.read_text(encoding="utf-8"))
        if dead or missing:
            problems.append("%s: dead %s, missing %s" % (path.name, dead, missing))
    start = START.read_text(encoding="utf-8")
    old = 'scripts\\desktop_launcher.py %*\n'
    neutral = start.replace("\r\n", "\n").replace(old, old + "\n:finished\n", 1)
    if neutral == start.replace("\r\n", "\n"):
        raise AssertionError("cannot neutralise start_shimmer.bat: its launch line was not found")
    _prove("no dead batch label", not problems, _batch_labels(neutral)[0] == ["finished"],
           not _batch_labels(start)[0])
    if problems:
        raise AssertionError("; ".join(problems))


def _start_entry():
    proc = subprocess.run(["cmd.exe", "/d", "/c", str(START), "--check-entry"], cwd=str(ROOT),
                          capture_output=True, timeout=120)
    out = proc.stdout.decode("utf-8", errors="replace").strip().splitlines()
    try:
        entry = json.loads(out[-1])
    except (ValueError, IndexError):
        entry = {}
    if proc.returncode != 0 or entry.get("entry") != "desktop_launcher":
        raise AssertionError("start_shimmer.bat --check-entry returned %r with %r"
                             % (proc.returncode, out[-1:] if out else out))
    if Path(entry.get("root", "")).resolve() != ROOT.resolve():
        raise AssertionError("start_shimmer.bat --check-entry ran another tree's launcher")
    PROOFS.append("start_shimmer.bat --check-entry answers (executed, no neutralisation)")


def _sh_bootstrap(bash):
    text = SH.read_text(encoding="utf-8")
    ok = _drive_sh(bash, text, "L\nQ\n")
    found = (_ended(ok) and "Creating a local virtual environment" not in ok["out"]
             and "STUB_PYTHON refused" not in ok["out"] and "Backend profile: local" in ok["out"])
    old = ('    if [ -f ".venv/Scripts/activate" ] && [ ! -f ".venv/bin/activate" ]; then\n'
           '        echo ".venv/Scripts"\n    else\n        echo ".venv/bin"\n    fi')
    broken = _drive_sh(bash, _neutralise(text, old, '    echo ".venv/bin"', "the venv layout"), "L\nQ\n")
    again = _drive_sh(bash, text, "L\nQ\n")
    _prove("sh finds a Windows venv layout", found,
           "STUB_PYTHON refused -m venv" in broken["out"] and broken["rc"] == 1,
           _ended(again) and "Creating a local virtual environment" not in again["out"])
    posix = _drive_sh(bash, text, "L\nQ\n", layout="bin")
    if not (_ended(posix) and "Creating a local virtual environment" not in posix["out"]):
        raise AssertionError("shimmer.sh no longer finds a bin/ venv")

    skipped = "the dependency install and the CUDA torch swap are skipped" in ok["out"]
    broken = _drive_sh(bash, _neutralise(text, '"${SHIMMER_SKIP_INSTALL:-}" = "1"',
                                         '"${SHIMMER_SKIP_INSTALL:-}" = "never"', "the install skip"),
                       "L\nQ\n")
    again = _drive_sh(bash, text, "L\nQ\n")
    _prove("sh SHIMMER_SKIP_INSTALL skips the install", skipped,
           "STUB_PYTHON refused -m pip" in broken["out"] and broken["rc"] == 1,
           _ended(again) and "STUB_PYTHON refused" not in again["out"])

    answers = "L\n1\nD\nA question\nQ\n"
    ok = _drive_sh(bash, text, answers)
    if not ("Draft setup cancelled." in ok["out"] and "Drafting a memo" not in ok["out"]):
        raise AssertionError("shimmer.sh announces a draft whose setup was cancelled")


# --- the banner -------------------------------------------------------------------

def _open_routes():
    """Every path the app answers without the token dependency, read off the
    live app object (FastAPI's own documentation routes included)."""
    from fastapi.dependencies.utils import get_flat_dependant
    from fastapi.routing import APIRoute
    server = sys.modules.get("server")
    if server is None:
        saved = os.environ.get("SHIMMER_OUTPUT_DIR")
        with tempfile.TemporaryDirectory(prefix="shimmer_launcher_server_") as td:
            os.environ["SHIMMER_OUTPUT_DIR"] = td
            try:
                import server  # noqa: F401  (imported for its app object)
            finally:
                if saved is None:
                    os.environ.pop("SHIMMER_OUTPUT_DIR", None)
                else:
                    os.environ["SHIMMER_OUTPUT_DIR"] = saved
        server = sys.modules["server"]
    open_paths, gated = set(), set()
    for route in server.app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        if isinstance(route, APIRoute):
            calls = {dep.call for dep in get_flat_dependant(route.dependant).dependencies}
            if server.verify_token in calls:
                gated.add(path)
                continue
        open_paths.add(path)
    return open_paths, gated


def banner_paths(text):
    """The paths a launcher's banner says answer without a token: the sentence
    that says so, read for its paths. None when no such sentence exists."""
    for line in text.splitlines():
        if line.lstrip().startswith("echo") and "without a token" in line:
            return set(re.findall(r"(/[a-z][a-z0-9_./-]*)", line))
    return None


def _banner():
    open_paths, gated = _open_routes()
    if "/runs" not in gated:
        raise AssertionError("the app's /runs route carries no token dependency; the route reading is wrong")
    problems = []
    for path in (BAT, SH):
        named = banner_paths(path.read_text(encoding="utf-8"))
        if named != open_paths:
            problems.append("%s names %s; the app answers %s without a token"
                            % (path.name, sorted(named or []), sorted(open_paths)))
        if "the only route with no token" in path.read_text(encoding="utf-8"):
            problems.append("%s still calls /health the only route with no token" % path.name)
    if problems:
        raise AssertionError("; ".join(problems))
    text = SH.read_text(encoding="utf-8")
    neutral = _neutralise(text, "Only /health and /console answer without a token.",
                          "Only /health answers without a token.", "the banner sentence")
    _prove("banner names the open routes", True, banner_paths(neutral) != open_paths,
           banner_paths(text) == open_paths)


# --- entry points for the gate ------------------------------------------------------

def _missing(*paths):
    gone = [p.name for p in paths if not p.is_file()]
    return ("launcher file(s) not present in this tree: %s; the container image ships no "
            "launcher by design" % ", ".join(gone)) if gone else None


def _collect(parts):
    """parts: (name, callable or skip reason). Returns the gate's (status, detail)."""
    del PROOFS[:]
    ran, skipped = [], []
    for name, step in parts:
        if isinstance(step, str):
            skipped.append("%s (%s)" % (name, step))
            continue
        try:
            step()
        except AssertionError as exc:
            return "FAIL", "%s: %s" % (name, exc)
        ran.append(name)
    if not ran:
        return "SKIP", "nothing could run here: " + "; ".join(skipped)
    detail = "neutralise/fail/restore/pass: " + ", ".join(PROOFS)
    if skipped:
        detail += "; not run here: " + "; ".join(skipped)
    return "PASS", detail


def check_end_of_input():
    bash = _bash()
    return _collect([
        ("shimmer.bat", _missing(BAT) or ("cmd.exe runs on Windows only" if not _windows() else _bat_end_of_input)),
        ("shimmer.sh", _missing(SH) or ("no bash outside the WSL launcher" if not bash
                                        else (lambda: _sh_end_of_input(bash)))),
    ])


def check_bootstrap():
    bash = _bash()
    windows_only = "cmd.exe runs on Windows only"
    return _collect([
        ("shimmer.bat", _missing(BAT, RESOLVE) or (windows_only if not _windows() else _bat_bootstrap)),
        ("batch labels", _missing(BAT, START, RESOLVE) or _bat_labels),
        ("start_shimmer.bat", _missing(START, RESOLVE) or (windows_only if not _windows() else _start_entry)),
        ("shimmer.sh", _missing(SH) or ("no bash outside the WSL launcher" if not bash
                                        else (lambda: _sh_bootstrap(bash)))),
    ])


def check_banner():
    missing = _missing(BAT, SH)
    if missing:
        return "SKIP", missing
    try:
        import fastapi  # noqa: F401
    except ImportError:
        return "SKIP", "fastapi absent: the app's routes cannot be read here"
    return _collect([("banner", _banner)])


def check():
    """All three, for running this file by hand."""
    results = [("end of input", check_end_of_input()), ("bootstrap", check_bootstrap()),
               ("banner", check_banner())]
    worst = "PASS"
    for _name, (status, _detail) in results:
        if status == "FAIL":
            worst = "FAIL"
    return worst, " | ".join("%s: %s %s" % (name, status, detail) for name, (status, detail) in results)


if __name__ == "__main__":
    for title, function in (("end of input", check_end_of_input), ("bootstrap", check_bootstrap),
                            ("banner", check_banner)):
        status, detail = function()
        print("%s: %s %s" % (title, status, detail))
