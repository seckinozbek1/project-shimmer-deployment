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
                       (Scripts/) and honours SHIMMER_SKIP_INSTALL; shimmer.sh
                       started from another folder with no /usr/bin on PATH
                       finds its own folder and reaches its menu, /usr/bin
                       appended for the tools after it (open item 54), with no
                       empty entry even to an empty PATH, so a python3 in its
                       own folder never runs (S7 round 3); the draft
                       path announces the draft only once setup succeeded; no
                       batch label is dead and no goto names a missing label;
                       start_shimmer.bat --check-entry answers.
  check_banner         the server banner in both launchers names exactly the
                       routes the app answers without a token.
  check_chat_window    menu option [2], the chat window, withdrawn so it is never
                       shown, in command mode with no model: help, a cutoff
                       written to a temporary scope file, a draft confirmed and a
                       review cancelled, every launch recorded and none run; a
                       request whose worker raises frees the window instead of
                       answering "Still working" to everything after it; a bare
                       "draft" asks for its topic instead of drafting on "draft".

A launcher file that is absent (the container image ships none) is skipped with
that reason. The batch half needs cmd.exe and runs on Windows only; the shell
half needs a bash that is not the WSL launcher.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BAT = ROOT / "shimmer.bat"
SH = ROOT / "shimmer.sh"
START = ROOT / "start_shimmer.bat"
RESOLVE = ROOT / "tools" / "resolve_python.bat"
CHAT = ROOT / "scripts" / "chat.py"
# Every process these checks start runs with no window of its own (D-079's rule).
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

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
                                stdout=sink, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
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
                       capture_output=True, timeout=30, creationflags=NO_WINDOW)
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
        # The bash's own folder (Git's usr/bin on Windows) carries the tools the
        # launcher calls (cat, rm, mktemp). A gate started from PowerShell or cmd
        # does not have it on PATH, and 307 and 308 then failed (D-147, S7 close).
        env["PATH"] = os.pathsep.join((str(fake.parent), str(Path(bash).parent), env.get("PATH", "")))
        env["LAUNCHER_CHECK_PYTHON"] = _posix(fake)
        return _run([bash, _posix(tmp / "shimmer.sh")], tmp, env, answers, timeout)


# The activate stand-in for the bare-PATH case calls an external tool by name, as the
# real one calls cygpath on Git Bash (Python 3.12's activate: VIRTUAL_ENV=$(cygpath ...)).
_ACTIVATE_CALLS_A_TOOL = 'cat </dev/null && echo "STUB_ACTIVATE cat ran"\n'


# A python3 planted in the launcher's own folder, which is the current folder after its cd:
# it runs only if PATH has an empty entry, which bash reads as the current folder.
_PLANTED_PYTHON = '#!%s\necho "PLANTED_PYTHON ran from the current folder" >&2\nexit 1\n'
PLANTED_MARK = "PLANTED_PYTHON ran from the current folder"


def _drive_sh_bare_path(bash, text, answers, timeout=PASS_BOUND_SECONDS, path=None):
    """shimmer.sh started as a scripted caller starts it from a non-login Git Bash
    (open item 54): PATH holds only the python stand-in's folder, so neither Git's
    usr/bin nor /usr/bin is on it, and the launcher is started from ANOTHER folder,
    so finding its own folder matters. The stand-in's shebang names bash by absolute
    path, since /usr/bin/env would look bash up on that PATH. With `path` given, PATH
    is exactly that (an empty one included) and a python3 is planted in the launcher's
    own folder, which runs only through an empty PATH entry (S7 round 3, adversarial 5)."""
    with tempfile.TemporaryDirectory(prefix="shimmer_launcher_sh_bare_", ignore_cleanup_errors=True) as td:
        tmp = Path(td)
        project = tmp / "project"
        fake = _sh_fixture(project, text)
        _write(project / ".venv" / "Scripts" / "activate", _ACTIVATE_CALLS_A_TOOL)
        shell = "/usr/bin/bash" if _windows() else _posix(bash)
        _write(fake, '#!%s\nif [ "$1" = "-m" ]; then echo "STUB_PYTHON refused -m $2"; exit 1; fi\n'
                     'exec "%s" "$@"\n' % (shell, _posix(sys.executable)))
        os.chmod(fake, 0o755)
        elsewhere = tmp / "elsewhere"
        elsewhere.mkdir()
        env = _clean_env(tmp)
        env["LAUNCHER_CHECK_PYTHON"] = _posix(fake)
        if path is None:
            env["PATH"] = str(fake.parent)
            return _run([bash, _posix(project / "shimmer.sh")], elsewhere, env, answers, timeout)
        planted = project / "python3"
        _write(planted, _PLANTED_PYTHON % shell)
        os.chmod(planted, 0o755)
        # PATH is set inside bash: Windows passes an empty PATH in the environment block to Git
        # Bash as "=", so the empty value is written by a bash that then starts the launcher.
        return _run([bash, "-c", 'PATH=%s; export PATH; exec %s "$1"' % (shlex.quote(path), shell), "launcher",
                     _posix(project / "shimmer.sh")], elsewhere, env, answers, timeout)


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
                          capture_output=True, timeout=120, creationflags=NO_WINDOW)
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

    # The draft is announced only after its setup succeeded (S7 close, adversarial 7:
    # the same neutralisation as the batch launcher's).
    answers = "L\n1\nD\nA question\nQ\n"
    ok = _drive_sh(bash, text, answers)
    quiet = "Draft setup cancelled." in ok["out"] and "Drafting a memo" not in ok["out"]
    early = ('DRAFT_FLAGS_FILE="${TMPDIR:-/tmp}/shimmer_draft_flags.$$"',
             'echo "Drafting a memo, then reviewing it ..."\n'
             '                        DRAFT_FLAGS_FILE="${TMPDIR:-/tmp}/shimmer_draft_flags.$$"')
    broken = _drive_sh(bash, _neutralise(text, early[0], early[1], "the early draft line"), answers)
    again = _drive_sh(bash, text, answers)
    _prove("sh draft is announced only after setup", quiet,
           "Drafting a memo" in broken["out"] and "Draft setup cancelled." in broken["out"],
           "Drafting a memo" not in again["out"])

    # Open item 54: started from another folder with no /usr/bin on PATH, the launcher
    # finds its own folder with no external tool and reaches its menu.
    def reached(result):
        return (_ended(result) and MENU_PROMPT in result["out"] and "Goodbye." in result["out"]
                and "command not found" not in result["out"])

    ok = _drive_sh_bare_path(bash, text, "L\nQ\n")
    here = text[text.index('case "$0" in'):text.index('cd "$SHIMMER_HERE"\n') + len('cd "$SHIMMER_HERE"')]
    broken = _drive_sh_bare_path(bash, _neutralise(text, here, 'cd "$(dirname "$0")"', "the own-folder lookup"),
                                 "L\nQ\n")
    again = _drive_sh_bare_path(bash, text, "L\nQ\n")
    _prove("sh reaches its menu with no /usr/bin on PATH", reached(ok),
           "dirname" in broken["out"] and "command not found" in broken["out"]
           and MENU_PROMPT not in broken["out"] and broken["rc"] == 1,
           reached(again))

    # The tools reached after that (the real activate's cygpath on Git Bash, the menu's
    # cat and rm) run because /usr/bin is appended where PATH lacks it.
    appended = text[text.index('case ":$PATH:" in'):text.index('esac', text.index('case ":$PATH:" in')) + 4]
    broken = _drive_sh_bare_path(bash, _neutralise(text, appended, ":", "the /usr/bin append"), "L\nQ\n")
    again = _drive_sh_bare_path(bash, text, "L\nQ\n")
    _prove("sh puts /usr/bin on a PATH that lacks it", "STUB_ACTIVATE cat ran" in ok["out"],
           "STUB_ACTIVATE cat ran" not in broken["out"] and "command not found" in broken["out"],
           "STUB_ACTIVATE cat ran" in again["out"] and reached(again))

    # S7 round 3, adversarial 5: an empty PATH gains /usr/bin and no empty entry, so a
    # python3 in the launcher's own folder (the current folder after its cd) never runs.
    new_line = ('[ -d /usr/bin ] && SHIMMER_PATH_HEAD="${PATH%:}" \\\n'
                '           && PATH="${SHIMMER_PATH_HEAD:+$SHIMMER_PATH_HEAD:}/usr/bin" && export PATH ;;')
    old_line = '[ -d /usr/bin ] && PATH="$PATH:/usr/bin" && export PATH ;;'
    empty = _drive_sh_bare_path(bash, text, "L\nQ\n", path="")
    broken = _drive_sh_bare_path(bash, _neutralise(text, new_line, old_line, "the empty-entry-free append"),
                                 "L\nQ\n", path="")
    again = _drive_sh_bare_path(bash, text, "L\nQ\n", path="")
    _prove("sh appends /usr/bin to an empty PATH with no empty entry",
           not empty["timed_out"] and PLANTED_MARK not in empty["out"],
           PLANTED_MARK in broken["out"],
           not again["timed_out"] and PLANTED_MARK not in again["out"])


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


# --- the chat window (menu option [2]) ----------------------------------------------

_CHAT_GUARD = "threading.Thread(target=self._guarded, args=(target, cmd), daemon=True).start()"
_CHAT_UNGUARDED = "threading.Thread(target=target, args=(cmd,), daemon=True).start()"


def _load_chat(text, tmp):
    """The chat module from TEXT, its files pointed into TMP. Nothing it would
    start runs: each launch is recorded, and the first one raises, as a wizard
    that cannot start or a flags file that cannot be written would."""
    import importlib.util
    path = tmp / "chat_under_check.py"
    _write(path, text)
    spec = importlib.util.spec_from_file_location("chat_under_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SCOPE_PATH = tmp / "config" / "review_scope.json"
    module.RUNS_ROOT = tmp / "runs"
    launches = []

    def recorded(self, argv, stdin_str):
        launches.append([Path(a).name for a in argv[3:5]])
        if len(launches) == 1:
            raise OSError("stand-in: the first launch cannot start")
        return 0

    def no_model(self):
        self.qwen_available = False
        self.ui(self.post, "Local AI model not available. Using command mode.")

    module.ChatApp._stream_subprocess = recorded
    module.ChatApp._check_qwen = no_model
    return module, launches


def _drive_chat(text, typed):
    """Type each line into a withdrawn chat window (never shown) and return the
    transcript after each, and the recorded launches."""
    import tkinter as tk
    import time
    with tempfile.TemporaryDirectory(prefix="shimmer_chat_", ignore_cleanup_errors=True) as td:
        tmp = Path(td)
        module, launches = _load_chat(text, tmp)
        root = tk.Tk()
        root.withdraw()
        app = module.ChatApp(root)
        replies = []

        def script():
            for line in typed:
                before = len(app.msg.get("1.0", "end"))
                app.entry.delete(0, "end")
                app.entry.insert(0, line)
                app.on_send()
                deadline = time.monotonic() + 2
                # a confirmed request runs on a worker; wait for it to settle
                while app.busy and time.monotonic() < deadline:
                    yield
                yield
                replies.append(app.msg.get("1.0", "end")[before:])

        steps = script()

        def tick():
            try:
                next(steps)
            except StopIteration:
                root.destroy()
                return
            root.after(20, tick)

        root.after(50, tick)
        # the neutralised copy's worker dies by design; keep its traceback off stderr
        import threading
        hook, threading.excepthook = threading.excepthook, lambda args: None
        try:
            root.mainloop()
        finally:
            threading.excepthook = hook
        scope = (json.loads(module.SCOPE_PATH.read_text(encoding="utf-8"))
                 if module.SCOPE_PATH.is_file() else None)
        return replies, launches, scope


def _chat():
    text = CHAT.read_text(encoding="utf-8")
    typed = ["help", "set cutoff 2026-01-15", "draft a memo on staffing", "y",
             "status", "draft a memo on staffing", "y", "review", "n", "draft", "y"]

    def passes(result):
        replies, launches, scope = result
        return (len(replies) == len(typed) and "draft a memo on <topic>" in replies[0]
                and scope == {"cutoff_date": "2026-01-15", "cutoff_type": "date"}
                and "stopped with an error (OSError)" in replies[3]
                and "Current settings:" in replies[4]
                and launches == [["pipeline.py", "--task"], ["pipeline.py", "--task"]]
                and "Cancelled." in replies[8]
                and "Tell me what the memo should be about." in replies[10])

    def stuck(result):
        replies = result[0]
        return len(replies) > 4 and "Still working on the previous request" in replies[4]

    def topic_draft(result):
        replies, launches = result[0], result[1]
        return len(replies) > 10 and len(launches) == 3 and "Draft and review complete." in replies[10]

    # the draft lead-in as chat.py writes it, and as it was before a bare draft got no topic
    lead_in = r"(draft|write|prepare|compose)\b\s*(me\s+)?"
    old_lead_in = r"(draft|write|prepare|compose)\s+(me\s+)?"
    shipped = passes(_drive_chat(text, typed))
    neutral = _neutralise(text, _CHAT_GUARD, _CHAT_UNGUARDED, "the chat worker guard")
    _prove("a failed chat request frees the window", shipped,
           stuck(_drive_chat(neutral, typed)), passes(_drive_chat(text, typed)))
    neutral = _neutralise(text, lead_in, old_lead_in, "the draft lead-in")
    _prove("a bare draft asks for its topic", shipped,
           topic_draft(_drive_chat(neutral, typed)), passes(_drive_chat(text, typed)))


def _tk_unavailable():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.destroy()
    except Exception as exc:  # no Tcl/Tk, or no display
        return "tkinter cannot open a window here (%s)" % type(exc).__name__
    return None


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


def check_chat_window():
    """Menu option [2] in command mode, withdrawn, with no model and nothing run."""
    return _collect([("chat window", _missing(CHAT) or _tk_unavailable() or _chat)])


def check():
    """All four, for running this file by hand."""
    results = [("end of input", check_end_of_input()), ("bootstrap", check_bootstrap()),
               ("banner", check_banner()), ("chat window", check_chat_window())]
    worst = "PASS"
    for _name, (status, _detail) in results:
        if status == "FAIL":
            worst = "FAIL"
    return worst, " | ".join("%s: %s %s" % (name, status, detail) for name, (status, detail) in results)


if __name__ == "__main__":
    for title, function in (("end of input", check_end_of_input), ("bootstrap", check_bootstrap),
                            ("banner", check_banner), ("chat window", check_chat_window)):
        status, detail = function()
        print("%s: %s %s" % (title, status, detail))
