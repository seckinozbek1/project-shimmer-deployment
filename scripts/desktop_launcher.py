"""Windows desktop startup, with an owned server and no automatic submission.

The GUI uses only the standard library. Readiness runs in a separate process
using the selected interpreter so a broken dependency cannot take down the UI.
The usable bearer token remains in memory; only its hash enters the server.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from startup_settings import resolve_server_settings
from run_choices import resolve_backend_profile

ROOT = Path(__file__).resolve().parent.parent


class StartupFailure(RuntimeError):
    """A human-readable startup failure; details belong in the startup log."""


def _probe_python(python, names):
    """Check package locations in a candidate, without importing those packages."""
    code = ("import importlib.util,json,sys\n"
            "missing=[]\n"
            "for name in json.loads(sys.argv[1]):\n"
            " try:\n"
            "  if importlib.util.find_spec(name) is None: missing.append(name)\n"
            " except (ImportError,ValueError,AttributeError): missing.append(name)\n"
            "print(json.dumps({'supported':sys.version_info >= (3,9),'missing':missing}))\n")
    try:
        result = subprocess.run([str(python), "-B", "-c", code, json.dumps(names)],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=15, creationflags=_hidden_flags())
        data = json.loads(result.stdout.strip().splitlines()[-1])
        if result.returncode == 0 and data.get("supported") is True:
            missing = data.get("missing")
            if isinstance(missing, list) and all(name in names for name in missing):
                return missing
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError, AttributeError):
        pass
    return None


def select_python(profile, *, root=ROOT, current=None, probe=None):
    """Prefer the installed environment with the chosen backend's packages.

    The batch interpreter only opens the standard-library GUI. A complete venv
    wins over a bare host; an incomplete venv cannot hide an equipped host.
    This cheap selection does not replace the real readiness import checks.
    """
    try:
        profile = resolve_backend_profile(profile)
    except ValueError:
        raise StartupFailure("Choose Local or Cloud before checking Python.") from None
    names = ["fastapi", "uvicorn", "python_multipart"]
    names += (["torch", "transformers", "accelerate", "bitsandbytes"] if profile == "local"
              else ["anthropic", "openai"])
    current = str(current or sys.executable)
    venv = Path(root) / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    candidates = [str(venv)] if venv.is_file() else []
    if os.path.normcase(os.path.abspath(current)) not in {
            os.path.normcase(os.path.abspath(candidate)) for candidate in candidates}:
        candidates.append(current)
    inspect = probe or _probe_python
    reports, usable = [], []
    for candidate in candidates:
        missing = inspect(candidate, names)
        reports.append({"python": candidate, "missing": missing})
        if missing is not None:
            usable.append((len(missing), len(usable), candidate))
    if not usable:
        raise StartupFailure("No usable Python environment was found. Repair Python 3.9 or later and the prerequisites in docs/RUNBOOK.md (Start Shimmer), then retry.")
    return min(usable)[2], reports


def ensure_port_available(host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if os.name == "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                # Match Uvicorn's reusable listener on POSIX. A closed server's
                # TIME_WAIT connections must not masquerade as a live listener.
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
    except OSError:
        raise StartupFailure(
            "The console port is already in use or unavailable. Stop the other "
            "Shimmer window, or choose another port, then try again.") from None


def check_readiness(profile, *, python=None, root=ROOT):
    """Read only. Never install, download, submit or invoke a provider."""
    command = [python or sys.executable, "-X", "utf8",
               str(root / "scripts" / "preflight.py"), "--check-startup",
               "--backend-profile", profile, "--json"]
    try:
        result = subprocess.run(command, cwd=str(root), capture_output=True,
                                text=True, encoding="utf-8", errors="replace",
                                timeout=120, creationflags=_hidden_flags())
    except (OSError, subprocess.TimeoutExpired):
        raise StartupFailure(
            "The Python environment could not finish its readiness check. "
            "Check the installed prerequisites in docs/RUNBOOK.md (Start Shimmer), then retry.") from None
    try:
        # Libraries may emit incidental informational lines before the report.
        report = json.loads(result.stdout.strip().splitlines()[-1])
        if not isinstance(report["checks"], list):
            raise ValueError
    except (ValueError, KeyError, IndexError, TypeError):
        raise StartupFailure(
            "The Python environment could not load Shimmer's readiness checks. "
            "Repair the prerequisites in docs/RUNBOOK.md (Start Shimmer), then retry.") from None
    if result.returncode != 0:
        report["ready"] = False
    return report


def _hidden_flags():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def authenticated_ready(console_url, access_token):
    """Authenticate to the actual child before opening its console.

    Health alone could belong to a different process that won a port race.
    Disable proxy inheritance for these strictly loopback requests.
    """
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = console_url.rsplit("/console", 1)[0]
    req = urllib.request.Request(base + "/runs", headers={
        "Authorization": "Bearer " + access_token})
    try:
        with opener.open(req, timeout=0.5) as response:
            if response.status != 200:
                return False
        with opener.open(console_url, timeout=0.5) as response:
            return response.status == 200 and "text/html" in response.headers.get("Content-Type", "")
    except (OSError, urllib.error.URLError):
        return False


class DesktopSession:
    """Own exactly one server and terminate it before releasing the session."""

    def __init__(self, *, root=ROOT, python=None, environment=None,
                 popen=None, ready=None, browser=None):
        self.root = Path(root)
        self.python = python or sys.executable
        self.environment = dict(os.environ if environment is None else environment)
        self.popen = popen or subprocess.Popen
        self.ready = ready or authenticated_ready
        self.browser = browser or webbrowser.open
        self.process = None
        self.access_token = None
        self.settings = None
        self.log_path = None
        self._log = None

    def start(self, profile, *, confirmed, open_browser=True, timeout=45):
        if not confirmed:
            return False
        try:
            profile = resolve_backend_profile(profile)
        except ValueError:
            raise StartupFailure("Choose Local or Cloud before starting.") from None
        if self.process is not None:
            raise StartupFailure("Stop the current Shimmer session before restarting.")
        try:
            self.settings = resolve_server_settings(self.environment, desktop=True)
        except ValueError as exc:
            raise StartupFailure(str(exc)) from None
        ensure_port_available(self.settings.host, self.settings.port)
        self.access_token = secrets.token_hex(32)
        child_env = self.environment.copy()
        child_env.update({
            "SHIMMER_TOKEN_HASH": hashlib.sha256(self.access_token.encode("utf-8")).hexdigest(),
            "SHIMMER_HOST": self.settings.host,
            "SHIMMER_PORT": str(self.settings.port),
            "SHIMMER_BACKEND_PROFILE": profile,
        })
        log_dir = self.root / "output" / "startup"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            # A unique local log contains no usable token, argv token or URL token.
            self.log_path = log_dir / ("server_" + time.strftime("%Y%m%d_%H%M%S")
                                       + "_" + secrets.token_hex(4) + ".log")
            self._log = self.log_path.open("w", encoding="utf-8")
            self.process = self.popen(
                [self.python, "-X", "utf8", str(self.root / "scripts" / "desktop_server.py")],
                cwd=str(self.root), env=child_env, stdin=subprocess.PIPE,
                stdout=self._log, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", creationflags=_hidden_flags())
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise StartupFailure(
                        "The console server could not start. Open the startup log "
                        "for details, repair the reported problem, then retry.")
                if self.ready(self.settings.console_url, self.access_token):
                    if open_browser:
                        self.open_console()
                    return True
                time.sleep(0.1)
            raise StartupFailure(
                "The console server did not become ready in time. Open the startup "
                "log for details, then retry.")
        except Exception:
            self.stop()
            raise

    def open_console(self):
        if not self.process or self.process.poll() is not None:
            raise StartupFailure("Shimmer is stopped. Start the console first.")
        try:
            return bool(self.browser(self.settings.console_url))
        except Exception:
            return False

    def stop(self, timeout=20):
        proc = self.process
        forced = False
        try:
            if proc and proc.poll() is None:
                try:
                    proc.stdin.write("stop\n")
                    proc.stdin.flush()
                    proc.stdin.close()
                except (OSError, ValueError):
                    pass
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    forced = True
                    # Windows /T targets only descendants of our owned PID.
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                       capture_output=True, timeout=10,
                                       creationflags=_hidden_flags())
                    else:
                        proc.kill()
                    proc.wait(timeout=10)
            if proc and proc.poll() is None:
                raise StartupFailure("Shimmer could not stop. Keep this window open and retry Stop.")
        finally:
            if proc is None or proc.poll() is not None:
                self.process = None
                self.access_token = None
                if self._log:
                    self._log.close()
                    self._log = None
        if forced:
            raise StartupFailure(
                "Shimmer had to be forcibly stopped. Any unfinished review remains "
                "incomplete. Check its status when you restart.")
        if proc and proc.returncode:
            raise StartupFailure("The console server exited with a failure. View the startup log before restarting.")


def run_gui(*, no_browser=False):
    import tkinter as tk
    from tkinter import messagebox, ttk

    window = tk.Tk()
    window.title("Start Shimmer")
    window.geometry("730x640")
    window.minsize(650, 550)
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Project Shimmer", font=("Segoe UI", 22, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Start your document review console", font=("Segoe UI", 12)).pack(anchor="w", pady=(0, 14))
    ttk.Label(frame, text="Choose where models will run. Starting the console does not start a review.", wraplength=670).pack(anchor="w")
    profile = tk.StringVar(value="")
    choices = ttk.Frame(frame)
    choices.pack(fill="x", pady=10)
    radios = [ttk.Radiobutton(choices, text="Local: installed models, no provider API charges", variable=profile, value="local"),
              ttk.Radiobutton(choices, text="Cloud: configured providers, usage charges apply", variable=profile, value="cloud")]
    for radio in radios:
        radio.pack(anchor="w", pady=3)
    port_row = ttk.Frame(frame)
    port_row.pack(fill="x")
    ttk.Label(port_row, text="Console port:").pack(side="left")
    port = tk.StringVar(value=os.environ.get("SHIMMER_PORT", "8000"))
    port_entry = ttk.Entry(port_row, textvariable=port, width=8)
    port_entry.pack(side="left", padx=6)
    ttk.Label(port_row, text="Only this computer can connect.").pack(side="left")
    status = tk.StringVar(value="Choose a backend, then click Check and start.")
    ttk.Label(frame, textvariable=status, wraplength=670).pack(anchor="w", pady=(14, 5))
    report_box = tk.Text(frame, height=11, wrap="word", state="disabled", font=("Segoe UI", 10))
    report_box.pack(fill="both", expand=True)
    python_label = tk.StringVar(value="Python environment will be selected from the installed prerequisites.")
    ttk.Label(frame, textvariable=python_label, wraplength=670).pack(anchor="w", pady=5)
    url = tk.StringVar(value="")
    ttk.Label(frame, textvariable=url, wraplength=670).pack(anchor="w")
    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", pady=10)
    session = DesktopSession()
    state = {"busy": False, "exit": 0, "closing": False, "readiness_detail": ""}

    def show_report(text):
        report_box.configure(state="normal")
        report_box.delete("1.0", "end")
        report_box.insert("1.0", text)
        report_box.configure(state="disabled")

    def controls():
        running = session.process is not None
        for item in radios + [port_entry, start_button]:
            item.configure(state="disabled" if running or state["busy"] else "normal")
        for item in [copy_button, browser_button, stop_button]:
            item.configure(state="normal" if running and not state["busy"] else "disabled")

    def failed(message):
        state["busy"] = False
        state["exit"] = 1
        status.set(message)
        controls()
        messagebox.showerror("Shimmer could not complete startup", message, parent=window)

    def started():
        state["busy"] = False
        state["exit"] = 0
        url.set(session.settings.console_url)
        status.set("Console ready. Click Copy access token, paste it into the browser's Access token field, then click Use this token.")
        controls()
        if not no_browser and not session.open_console():
            status.set("Console ready, but the browser could not open. Click Open console to retry. "
                       "Copy access token and paste it into the sign-in field.")

    def launch():
        state["busy"] = True
        status.set("Starting the console server...")
        controls()
        # Copy values in the GUI thread before the worker accesses process state.
        chosen = profile.get()
        session.environment["SHIMMER_PORT"] = port.get()
        def launch_worker():
            try:
                session.start(chosen, confirmed=True, open_browser=False)
            except Exception as exc:
                message = str(exc) if isinstance(exc, StartupFailure) else "Startup failed. Check the startup log and installed prerequisites, then retry."
                window.after(0, lambda: failed(message))
            else:
                window.after(0, started)
        threading.Thread(target=launch_worker, daemon=True).start()

    def checked(report, python, environments):
        state["busy"] = False
        session.python = python
        python_label.set("Selected Python: " + python)
        detail = ["Selected Python: " + python, "", "Installed environment checks:"]
        for candidate in environments:
            missing = candidate["missing"]
            outcome = ("could not check this interpreter" if missing is None else
                       "missing packages: " + ", ".join(missing) if missing else "required packages found")
            detail.append(candidate["python"] + ": " + outcome)
        detail.extend(["", "Readiness report:"])
        for check in report["checks"]:
            detail.append(check["status"] + ": " + check["message"])
            if check.get("detail"):
                detail.append("  " + check["detail"])
        state["readiness_detail"] = "\n".join(detail)
        show_report("\n".join(c["status"] + ": " + c["message"] for c in report["checks"]))
        controls()
        if not report.get("ready"):
            failed("Shimmer is not ready. Resolve the failed checks shown here, then try again.")
            return
        if messagebox.askyesno("Start the console?", "Readiness checks passed. Start the " + profile.get().title()
                               + " console on this computer?\n\nReview or Draft, files and privacy are chosen in the console. No review starts now.", parent=window):
            launch()
        else:
            status.set("Start cancelled. No server or review was started.")

    def check_and_start():
        chosen = profile.get()
        if chosen not in ("local", "cloud"):
            messagebox.showinfo("Choose a backend", "Select Local or Cloud first.", parent=window)
            return
        try:
            settings = resolve_server_settings(dict(os.environ, SHIMMER_PORT=port.get()), desktop=True)
            ensure_port_available(settings.host, settings.port)
        except (StartupFailure, ValueError) as exc:
            failed(str(exc))
            return
        state["busy"] = True
        status.set("Checking installed prerequisites. No models or documents are being sent to a provider...")
        controls()
        def worker():
            try:
                python, environments = select_python(chosen)
                report = check_readiness(chosen, python=python)
            except StartupFailure as exc:
                message = str(exc)
                window.after(0, lambda: failed(message))
            else:
                window.after(0, lambda: checked(report, python, environments))
        threading.Thread(target=worker, daemon=True).start()

    def copy_access():
        if session.access_token:
            window.clipboard_clear()
            window.clipboard_append(session.access_token)
            status.set("Access token copied. In the browser, paste it into Access token and click Use this token. "
                       "Then choose Submit. Keep this window open; Stop Shimmer ends this session.")

    def finish_stop(message=None):
        state["busy"] = False
        if message:
            state["exit"] = 1
            status.set(message)
        else:
            status.set("Shimmer stopped. Click Check and start to restart, or close this window.")
        url.set("")
        controls()
        if state["closing"] and session.process is None:
            window.destroy()

    def stop():
        # Clear only this session's clipboard value, preserving unrelated copies.
        try:
            if session.access_token and window.clipboard_get() == session.access_token:
                window.clipboard_clear()
        except tk.TclError:
            pass
        state["busy"] = True
        status.set("Stopping Shimmer and waiting for its processes to exit...")
        controls()
        def worker():
            message = None
            try:
                session.stop()
            except Exception:
                message = "Shimmer did not stop cleanly. Check the startup log before restarting."
            window.after(0, lambda: finish_stop(message))
        threading.Thread(target=worker, daemon=True).start()

    def close():
        if state["busy"]:
            messagebox.showinfo("Please wait", "Wait for startup or shutdown to finish, then close this window.", parent=window)
            return
        if session.process:
            if not messagebox.askyesno("Stop Shimmer?", "Closing this window stops Shimmer and any unfinished review. Continue?", parent=window):
                return
            state["closing"] = True
            stop()
        else:
            window.destroy()

    def log_view():
        sections = [state["readiness_detail"]] if state["readiness_detail"] else []
        if session.log_path and session.log_path.is_file():
            sections.append("Server startup log:\n" + session.log_path.read_text(encoding="utf-8", errors="replace"))
        if sections:
            detail = tk.Toplevel(window)
            detail.title("Shimmer startup details and log")
            box = tk.Text(detail, width=110, height=28, wrap="word")
            box.pack(fill="both", expand=True)
            box.insert("1.0", "\n\n".join(sections))
            box.configure(state="disabled")
        else:
            messagebox.showinfo("Startup log", "No server has started yet. The readiness report above names the problem.", parent=window)

    start_button = ttk.Button(buttons, text="Check and start", command=check_and_start)
    copy_button = ttk.Button(buttons, text="Copy access token", command=copy_access)
    browser_button = ttk.Button(buttons, text="Open console", command=session.open_console)
    stop_button = ttk.Button(buttons, text="Stop Shimmer", command=stop)
    for button in [start_button, copy_button, browser_button, stop_button]:
        button.pack(side="left", padx=(0, 6))
    ttk.Button(frame, text="View startup log", command=log_view).pack(anchor="w")
    ttk.Label(frame, text="In the browser: Submit > Review or Draft > choose documents and privacy > confirm. "
              "Closing the browser does not stop Shimmer. Use Stop Shimmer here.", wraplength=670).pack(anchor="w", pady=(10, 0))

    def poll():
        if session.process and not state["busy"] and session.process.poll() is not None:
            try:
                session.stop()
            except StartupFailure:
                pass
            state["exit"] = 1
            status.set("The server stopped unexpectedly. View the startup log, then restart when the problem is resolved.")
            controls()
        window.after(500, poll)
    controls()
    window.protocol("WM_DELETE_WINDOW", close)
    window.after(500, poll)
    try:
        window.mainloop()
    finally:
        session.stop()
    return state["exit"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start the Shimmer desktop console")
    parser.add_argument("--no-browser", action="store_true", help="leave browser opening to the Open console button")
    parser.add_argument("--check-entry", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.check_entry:
        print(json.dumps({"entry": "desktop_launcher", "python": sys.executable, "root": str(ROOT)}))
        return 0
    try:
        return run_gui(no_browser=args.no_browser)
    except Exception:
        # Last resort also works when tkinter itself is missing. Do not expose
        # arbitrary exception contents: imported modules can contain credentials.
        message = "Shimmer could not open its startup window. Install Python with Tcl/Tk and the prerequisites in docs/RUNBOOK.md (Start Shimmer), then retry."
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "Start Shimmer", 0x10)
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
