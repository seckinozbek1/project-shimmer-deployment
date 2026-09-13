"""Executable desktop entry, authentication, lifetime and restoration proofs."""
from __future__ import annotations

import contextlib
import ast
import copy
import errno
import hashlib
import io
import inspect
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import desktop_launcher as desktop
from effect_proof import prove_effect

ROOT = Path(__file__).resolve().parent.parent
_DIGEST = hashlib.sha256


class ProcessFixture:
    def __init__(self):
        self.returncode = None
        self.stdin = io.StringIO()
        self.pid = 1
        self.waited = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.waited = True
        self.returncode = 0
        return 0


def observe_session(*, confirmed=True, open_browser=True):
    with tempfile.TemporaryDirectory(prefix="shimmer_startup_check_") as td:
        captured = []
        opened = []
        proc = ProcessFixture()
        def spawn(argv, **kwargs):
            captured.append((argv, kwargs["env"]))
            return proc
        session = desktop.DesktopSession(root=Path(td), environment={"SHIMMER_PORT": "8173"},
                                         popen=spawn, ready=lambda *_: True,
                                         browser=lambda url: opened.append(url) or True)
        with patch.object(desktop, "ensure_port_available"):
            started = session.start("local", confirmed=confirmed, open_browser=open_browser)
        valid_hash = bool(captured and captured[0][1]["SHIMMER_TOKEN_HASH"] ==
                          _DIGEST(session.access_token.encode()).hexdigest())
        token_leaked = bool(captured and (session.access_token in captured[0][0] or
                                         session.access_token in captured[0][1].values() or
                                         any(session.access_token in u for u in opened)))
        observation = {"started": started, "spawned": len(captured), "opened": list(opened),
                       "profile": captured[0][1].get("SHIMMER_BACKEND_PROFILE") if captured else None,
                       "host": captured[0][1].get("SHIMMER_HOST") if captured else None,
                       "token_hash_valid": valid_hash, "token_leaked": token_leaked}
        session.stop()
        observation.update({"waited": proc.waited, "alive": session.process is not None,
                            "token_released": session.access_token is None})
        return observation


def _assert_session():
    normal = observe_session()
    assert normal == {"started": True, "spawned": 1,
                      "opened": ["http://127.0.0.1:8173/console"], "profile": "local",
                      "host": "127.0.0.1", "token_hash_valid": True, "token_leaked": False,
                      "waited": True, "alive": False, "token_released": True}
    cancelled = observe_session(confirmed=False)
    assert cancelled["spawned"] == 0 and not cancelled["opened"] and not cancelled["started"]
    assert observe_session(open_browser=False)["opened"] == []
    with patch.object(desktop.subprocess, "run", return_value=subprocess.CompletedProcess(
            [], 1, json.dumps({"ready": True, "checks": [{"status": "FAIL", "message": "Missing dependency. Install prerequisites."}]}), "")):
        assert desktop.check_readiness("local")["ready"] is False
    with patch.object(desktop.subprocess, "run", side_effect=OSError):
        try:
            desktop.check_readiness("local")
        except desktop.StartupFailure as exc:
            assert "prerequisites" in str(exc)
        else:
            raise AssertionError("missing Python must fail")
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        try:
            desktop.ensure_port_available("127.0.0.1", held.getsockname()[1])
        except desktop.StartupFailure as exc:
            assert "port" in str(exc) and "try again" in str(exc)
        else:
            raise AssertionError("occupied port accepted")


def _verdict():
    try:
        _assert_session()
        return "PASS", "desktop consumer outcomes"
    except AssertionError:
        return "FAIL", "desktop consumer regression"


def mutation_proofs():
    real_start = desktop.DesktopSession.start
    real_open = desktop.DesktopSession.open_console
    real_stop = desktop.DesktopSession.stop

    def accept_decline(self, profile, **kwargs):
        kwargs["confirmed"] = True
        return real_start(self, profile, **kwargs)

    def open_root(self):
        return self.browser(self.settings.console_url.replace("/console", "/"))

    def leave_running(self, timeout=20):
        # Close fixture log handles but neutralise the process wait/release.
        if self._log:
            self._log.close()
            self._log = None

    proofs = []
    for name, observer, mutation in [
        ("decline starts nothing", lambda: observe_session(confirmed=False),
         lambda: patch.object(desktop.DesktopSession, "start", accept_decline)),
        ("browser opens console", observe_session,
         lambda: patch.object(desktop.DesktopSession, "open_console", open_root)),
        ("stop waits and releases", observe_session,
         lambda: patch.object(desktop.DesktopSession, "stop", leave_running)),
    ]:
        proofs.append(prove_effect(name=name, validate=lambda: ProcessFixture().poll() is None,
                                  observe=observer, check=_verdict, neutralise=mutation))
    return proofs


def port_lifetime_proof():
    """A live reusable listener blocks; a closed TIME_WAIT listener restarts.

    Sockets are prepared once outside mutation scope. Only the real availability
    probe loses SO_REUSEADDR during neutralisation; fixture setup is unchanged.
    Windows keeps its exclusive-bind behavior and occupied-port coverage above.
    """
    if os.name == "nt":
        return [], "POSIX TIME_WAIT reuse proof not applicable on Windows; exclusive occupied-port proof retained"

    def reusable_listener():
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.settimeout(3)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        return listener

    with reusable_listener() as live:
        live_port = live.getsockname()[1]
        with reusable_listener() as stopped:
            stopped_port = stopped.getsockname()[1]
            with socket.create_connection(("127.0.0.1", stopped_port), timeout=3) as client:
                with stopped.accept()[0] as accepted:
                    accepted.settimeout(3)
                    # The server actively closes first. Waiting for each EOF
                    # completes the handshake and leaves its port in TIME_WAIT.
                    accepted.shutdown(socket.SHUT_WR)
                    if client.recv(1) != b"":
                        raise AssertionError("fixture server did not send EOF")
                    client.shutdown(socket.SHUT_WR)
                    if accepted.recv(1) != b"":
                        raise AssertionError("fixture client did not send EOF")
        def valid():
            if live.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) != 1:
                return False
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as raw:
                try:
                    raw.bind(("127.0.0.1", stopped_port))
                except OSError as exc:
                    return exc.errno == errno.EADDRINUSE
            return False  # No lingering socket state, so this is not the fixture.

        def observe():
            outcomes = {}
            for label, port in (("live", live_port), ("stopped", stopped_port)):
                try:
                    desktop.ensure_port_available("127.0.0.1", port)
                    outcomes[label] = "available"
                except desktop.StartupFailure:
                    outcomes[label] = "busy"
            return outcomes

        def verdict():
            return ("PASS" if observe() == {"live": "busy", "stopped": "available"} else "FAIL",
                    "real listener lifetime boundary")

        original = desktop.ensure_port_available
        def neutralise():
            tree = ast.parse(inspect.getsource(original))
            call = next(node for node in ast.walk(tree)
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "setsockopt" and len(node.args) == 3
                        and isinstance(node.args[1], ast.Attribute)
                        and node.args[1].attr == "SO_REUSEADDR")
            call.args[2] = ast.Constant(value=0)
            ast.fix_missing_locations(tree)
            namespace = {}
            exec(compile(tree, "<port availability mutation>", "exec"), original.__globals__, namespace)
            return patch.object(desktop, "ensure_port_available", namespace[original.__name__])

        proof = prove_effect(name="stopped reusable listener can restart despite TIME_WAIT",
                             validate=valid, observe=observe, check=verdict, neutralise=neutralise)
        if proof["mutated"] != {"live": "busy", "stopped": "busy"}:
            raise AssertionError("reuse mutation did not expose the stopped-port failure")
        return [proof], "live reusable listener refused; stopped TIME_WAIT port immediately reusable"


def _assert_python_selection():
    # Execute the actual cheap subprocess probe, loading only the standard library.
    assert desktop._probe_python(sys.executable, ["json", "shimmer_absent_fixture_package"]) == ["shimmer_absent_fixture_package"]
    # Probe the same configured import environment that readiness/server use.
    # An isolated-mode probe would hide configured packages and choose wrongly.
    with tempfile.TemporaryDirectory(prefix="shimmer_python_path_") as td:
        (Path(td) / "shimmer_environment_fixture.py").write_text("raise AssertionError('probe must not import')\n", encoding="utf-8")
        with patch.dict(os.environ, {"PYTHONPATH": td}):
            assert desktop._probe_python(sys.executable, ["shimmer_environment_fixture"]) == []
    with tempfile.TemporaryDirectory(prefix="shimmer_python_selection_") as td:
        root = Path(td)
        venv = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        venv.parent.mkdir(parents=True)
        venv.write_bytes(b"declared interpreter path fixture, never executed")
        host = str(root / "host_python")
        seen = []
        def probe(candidate, names):
            seen.append(list(names))
            return inventory[candidate]
        inventory = {str(venv): [], host: ["fastapi", "openai"]}
        assert desktop.select_python("cloud", root=root, current=host, probe=probe)[0] == str(venv)
        assert all("openai" in names and "torch" not in names for names in seen)
        inventory = {str(venv): ["torch", "transformers"], host: []}
        assert desktop.select_python("local", root=root, current=host, probe=probe)[0] == host
        assert "torch" in seen[-1] and "openai" not in seen[-1]
        inventory[str(venv)] = None
        assert desktop.select_python("local", root=root, current=host, probe=probe)[0] == host


def _gui_report(ready):
    return {"ready": ready, "checks": [{"status": "PASS" if ready else "FAIL",
            "message": "Prerequisites available." if ready else "Missing prerequisites. Install them, then retry.",
            "detail": "fixture package details"}]}


def _valid_gui_inputs(confirmed, ready):
    report = _gui_report(ready)
    return (isinstance(confirmed, bool) and isinstance(ready, bool)
            and report["ready"] == all(row["status"] != "FAIL" for row in report["checks"])
            and all(row["message"] and row["detail"] for row in report["checks"]))


def observe_gui(*, confirmed=True, ready=True, crash=False, no_browser=False):
    """Execute the real GUI and callback chain with inert widgets and dispatch.

    The real DesktopSession.start/stop run against a process fixture. No native
    clipboard, browser, provider, model or live repository server is touched.
    """
    widgets, dialogs, timers, opened, spawned, readiness_calls = [], [], [], [], [], []

    class Variable:
        def __init__(self, value=""):
            self.value = value
        def get(self):
            return self.value
        def set(self, value):
            self.value = value

    class Widget:
        def __init__(self, *args, **kwargs):
            self.options = kwargs
            self.content = ""
            widgets.append(self)
        def pack(self, **kwargs):
            pass
        def configure(self, **kwargs):
            self.options.update(kwargs)
        def delete(self, *args):
            self.content = ""
        def insert(self, position, value):
            self.content += value
        def title(self, value):
            self.options["title"] = value
        def geometry(self, *args):
            pass
        def minsize(self, *args):
            pass
        def protocol(self, *args):
            pass
        def invoke(self):
            assert self.options.get("state") != "disabled", "fixture clicked a disabled control"
            if "value" in self.options:
                self.options["variable"].set(self.options["value"])
            elif self.options.get("command"):
                self.options["command"]()

    def button(name):
        return next(widget for widget in widgets if widget.options.get("text") == name)

    observation = {}
    class Window(Widget):
        clipboard = ""
        def after(self, delay, callback):
            if delay == 0:
                callback()
            else:
                timers.append(callback)
        def clipboard_clear(self):
            self.clipboard = ""
        def clipboard_append(self, value):
            self.clipboard = value
        def clipboard_get(self):
            return self.clipboard
        def destroy(self):
            pass
        def mainloop(self):
            button("Cloud: configured providers, usage charges apply").invoke()
            button("Check and start").invoke()
            observation["copied"] = False
            if session.process:
                button("Copy access token").invoke()
                observation["copied"] = self.clipboard == session.access_token
            button("View startup log").invoke()
            observation["details"] = any("fixture package details" in widget.content for widget in widgets)
            observation["selected_shown"] = any(
                widget.options.get("textvariable") and
                widget.options["textvariable"].get() == "Selected Python: " + chosen_python
                for widget in widgets)
            if crash and session.process:
                session.process.returncode = 7
                timers.pop(0)()
                observation["crash_recovered"] = session.process is None and button("Check and start").options["state"] == "normal"
            elif session.process:
                button("Stop Shimmer").invoke()
            observation["clipboard_cleared"] = not self.clipboard

    class Thread:
        def __init__(self, target, **kwargs):
            self.target = target
        def start(self):
            self.target()

    boxes = SimpleNamespace(
        askyesno=lambda *a, **k: dialogs.append("confirmation") or confirmed,
        showerror=lambda *a, **k: dialogs.append("error"),
        showinfo=lambda *a, **k: dialogs.append("info"))
    ttk = SimpleNamespace(**{name: Widget for name in ("Frame", "Label", "Radiobutton", "Entry", "Button")})
    tk = SimpleNamespace(Tk=Window, StringVar=Variable, Text=Widget, Toplevel=Widget,
                         TclError=RuntimeError, messagebox=boxes, ttk=ttk)
    real_session = desktop.DesktopSession
    with tempfile.TemporaryDirectory(prefix="shimmer_gui_check_") as td:
        chosen_python = str(Path(td) / "selected_python")
        proc = ProcessFixture()
        def spawn(argv, **kwargs):
            spawned.append((argv, kwargs["env"]))
            return proc
        session = real_session(root=Path(td), environment={"SHIMMER_PORT": "8173"},
                               popen=spawn, ready=lambda *_: True,
                               browser=lambda url: opened.append(url) or True)
        report = _gui_report(ready)
        def readiness(profile, *, python):
            readiness_calls.append((profile, python))
            return copy.deepcopy(report)
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"SHIMMER_PORT": "8000"}))
            stack.enter_context(patch.dict(sys.modules, {"tkinter": tk, "tkinter.ttk": ttk,
                                                        "tkinter.messagebox": boxes}))
            stack.enter_context(patch.object(desktop, "DesktopSession", return_value=session))
            stack.enter_context(patch.object(desktop, "select_python", return_value=(chosen_python, [{"python": chosen_python, "missing": []}])))
            stack.enter_context(patch.object(desktop, "check_readiness", side_effect=readiness))
            stack.enter_context(patch.object(desktop, "ensure_port_available"))
            stack.enter_context(patch.object(desktop.threading, "Thread", Thread))
            code = desktop.run_gui(no_browser=no_browser)
        observation.update({"exit": code, "spawned": len(spawned), "confirmations": dialogs.count("confirmation"),
                            "errors": dialogs.count("error"), "opened": opened,
                            "selected_consistent": bool(readiness_calls == [("cloud", chosen_python)] and
                                session.python == chosen_python and
                                (not spawned or spawned[0][0][0] == chosen_python)),
                            "profile": spawned[0][1]["SHIMMER_BACKEND_PROFILE"] if spawned else None,
                            "stopped": session.process is None})
    return observation


def _assert_gui():
    normal = observe_gui()
    assert normal["spawned"] == 1 and normal["exit"] == 0 and normal["stopped"]
    assert normal["selected_consistent"] and normal["selected_shown"] and normal["profile"] == "cloud"
    assert normal["copied"] and normal["clipboard_cleared"] and normal["details"]
    assert normal["opened"] == ["http://127.0.0.1:8000/console"]
    decline = observe_gui(confirmed=False)
    assert decline["spawned"] == 0 and decline["confirmations"] == 1 and not decline["opened"]
    missing = observe_gui(ready=False)
    assert missing["spawned"] == 0 and missing["confirmations"] == 0 and missing["exit"] == 1
    assert missing["errors"] == 1 and missing["details"]
    crashed = observe_gui(crash=True)
    assert crashed["crash_recovered"] and crashed["exit"] == 1 and crashed["stopped"]
    assert not observe_gui(no_browser=True)["opened"]


def gui_mutation_proofs():
    """Neutralise real nested callback branches, then execute the entire GUI."""
    original = desktop.run_gui
    def mutate(branch):
        tree = ast.parse(inspect.getsource(original))
        checked = next(node for node in ast.walk(tree)
                       if isinstance(node, ast.FunctionDef) and node.name == "checked")
        guards = [node for node in checked.body if isinstance(node, ast.If)]
        # Identify the executed gates structurally, never by asserting source text.
        target = next(node for node in guards if isinstance(node.test, ast.UnaryOp)) if branch == "readiness" else next(
            node for node in guards if isinstance(node.test, ast.Call))
        target.test = ast.Constant(value=branch == "confirmation")
        ast.fix_missing_locations(tree)
        namespace = {}
        exec(compile(tree, "<desktop GUI mutation>", "exec"), original.__globals__, namespace)
        return patch.object(desktop, "run_gui", namespace["run_gui"])
    def verdict():
        try:
            _assert_gui()
            return "PASS", "GUI consumer outcomes"
        except AssertionError:
            return "FAIL", "GUI consumer regression"
    return [prove_effect(name="GUI declined confirmation launches nothing", validate=lambda: _valid_gui_inputs(False, True),
                         observe=lambda: observe_gui(confirmed=False), check=verdict,
                         neutralise=lambda: mutate("confirmation")),
            prove_effect(name="GUI failed readiness blocks server startup", validate=lambda: _valid_gui_inputs(True, False),
                         observe=lambda: observe_gui(ready=False), check=verdict,
                         neutralise=lambda: mutate("readiness"))]


def entry_check():
    """Execute the real Windows batch file, including quoting from a spaced cwd."""
    if os.name != "nt":
        return "Windows batch execution unavailable on this platform"
    result = subprocess.run(["cmd.exe", "/d", "/c", str(ROOT / "start_shimmer.bat"), "--check-entry"],
                            cwd=tempfile.gettempdir(), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=20)
    assert result.returncode == 0, "clickable entry failed"
    record = json.loads(result.stdout.strip().splitlines()[-1])
    assert record["entry"] == "desktop_launcher"
    assert Path(record["root"]).resolve() == ROOT.resolve()
    return "real Windows batch reaches desktop_launcher"


def live_server_check():
    """Run the real owned server on a temporary fixture tree, never a review.

    This is an isolated process-lifetime fixture, not the later fresh-clone test.
    All provider/process dispatch in the child is guarded and forbidden.
    """
    with tempfile.TemporaryDirectory(prefix="shimmer_owned_server_") as td:
        root = Path(td)
        shutil.copytree(ROOT / "scripts", root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(ROOT / "config", root / "config")
        guard = root / "guard"
        guard.mkdir()
        (guard / "sitecustomize.py").write_text(
            "import asyncio, socket, subprocess\n"
            "from pathlib import Path\n"
            "def forbidden(*a, **k):\n"
            "    Path(__file__).with_name('forbidden_attempt').touch()\n"
            "    raise RuntimeError('Fixture forbids provider and child dispatch')\n"
            "original_connect = socket.socket.connect\n"
            "def local_connect(self, address):\n"
            "    if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):\n"
            "        return original_connect(self, address)\n"
            "    return forbidden()\n"
            "socket.socket.connect = local_connect\n"
            "socket.create_connection = forbidden\n"
            "subprocess.Popen = forbidden\n", encoding="utf-8")
        with socket.socket() as port_sock:
            port_sock.bind(("127.0.0.1", 0))
            port = port_sock.getsockname()[1]
        env = os.environ.copy()
        env.update({"SHIMMER_PORT": str(port), "SHIMMER_OUTPUT_DIR": str(root / "runs"),
                    "SHIMMER_AUTO_CLEAR": "false", "PYTHONPATH": str(guard),
                    "TMP": str(root), "TEMP": str(root)})
        opened = []
        session = desktop.DesktopSession(root=root, environment=env,
                                         browser=lambda u: opened.append(u) or True)
        try:
            assert session.start("cloud", confirmed=True, timeout=30)
            proc = session.process
            assert proc.poll() is None
            assert opened == ["http://127.0.0.1:%d/console" % port]
            # A different bearer is rejected by the real server hash mechanism.
            assert not desktop.authenticated_ready(session.settings.console_url, "fixture-invalid")
            assert not (guard / "forbidden_attempt").exists()
            session.stop()
            assert proc.poll() == 0, "server still running or failed shutdown"
            desktop.ensure_port_available("127.0.0.1", port)
            # Restart receives a new token; owner EOF also shuts the child down.
            assert session.start("cloud", confirmed=True, open_browser=False, timeout=30)
            restarted = session.process
            restarted.stdin.close()
            assert restarted.wait(timeout=20) == 0
            session.stop()
            assert not (guard / "forbidden_attempt").exists()
        finally:
            session.stop()
    return "real authenticated console, restart, Stop and owner EOF; zero forbidden dispatches"


def check():
    try:
        _assert_session()
        proofs = mutation_proofs()
        port_proofs, port_detail = port_lifetime_proof()
        proofs += port_proofs
        _assert_python_selection()
        _assert_gui()
        proofs += gui_mutation_proofs()
        entry = entry_check()
        live = live_server_check()
        return "PASS", "%s; %s; %s; %d restoring mutations" % (entry, live, port_detail, len(proofs))
    except Exception as exc:
        # No exception value or subprocess output can reveal the bearer.
        return "FAIL", "desktop startup fixture failed (%s)" % type(exc).__name__


if __name__ == "__main__":
    result = check()
    print(*result)
    sys.exit(0 if result[0] == "PASS" else 1)
