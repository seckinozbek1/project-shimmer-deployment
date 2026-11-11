#!/usr/bin/env python3
"""Does a clean install of Shimmer work? A check that needs no model, no GPU and no provider key.

Run it from a fresh clone, with any Python 3.12. It uses the standard library only until the new
environment exists, and every later step runs in that environment.

    python3.12 tools/clean_install_check.py --venv <new empty folder>

    1 python     the interpreter meets tools/cloud_run/runtime.json
    2 venv       a new virtual environment, in a folder that must be new or empty
    3 install    pip install -r requirements.txt, into that environment (needs the network and
                 several gigabytes: torch is in the list)
    4 packages   the packages the console and a review import, imported
    5 startup    scripts/preflight.py --check-startup: the console's own read-only readiness
    6 no_model   benchmark/baselines/python_only.py on the worked case, a real run of Shimmer's
                 computing layer with no model call: it must complete, make no model call and
                 find the total in Annex II that does not add up
    7 console    scripts/server.py on a free local port: /health and /console answer, a run list
                 is refused with no token and given with the right one, and the server stops

What it does not show. No model is loaded, so it says nothing about a review with a model. Step 5
reports whether model files are present and does not fail on them. A review with a model needs
the weights, a GPU and hours. Nothing is downloaded but the packages of step 3.

    python3.12 tools/clean_install_check.py --python <interpreter>

uses an environment that already exists and skips steps 2 and 3. Its report says so, and it does
not count as a clean install. Exit 0 only when every step that ran passed. Each step's result goes
to the screen and, with --report <file>, to a JSON file. Nothing in the checkout is written: the
review and the server write under a temporary folder.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "benchmark" / "dev_cases" / "host_agreement_three_rounds" / "workload"
TARGETS = "_review_targets.json"
PACKAGES = ("fastapi", "uvicorn", "multipart", "docx", "lxml", "pypdf", "bs4", "torch", "transformers",
            "sentence_transformers", "numpy")
# The console refuses to start under the local profile with no model files, and this check has
# none. The cloud profile starts with no key: a key is read when a run needs one, and none runs.
SERVER_PROFILE = "cloud"
SERVER_START_SECONDS = 180
EXPECTED_FINDING = ("sum_mismatch", 2100000.0, 2200000.0)


class Failed(RuntimeError):
    """A step did not pass. The message says why, in one line."""


def run(argv, *, timeout=None, env=None, cwd=None):
    """(exit code, standard output, standard error) of a child process."""
    done = subprocess.run([str(a) for a in argv], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=env, cwd=str(cwd or ROOT))
    return done.returncode, done.stdout, done.stderr


def child_env(extra=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", KMP_DUPLICATE_LIB_OK="TRUE")
    env.pop("PYTHONPATH", None)
    env.update(extra or {})
    return env


def step_python(python, runner=run):
    code, out, err = runner([python, ROOT / "tools" / "runtime_contract.py", "--resolve", "--candidate", python,
                             "--path-only"])
    if code != 0:
        raise Failed("the interpreter does not meet tools/cloud_run/runtime.json: %s" % (err or out).strip()[-200:])
    return out.strip()


def step_venv(python, folder, runner=run):
    folder = Path(folder)
    if folder.exists() and any(folder.iterdir()):
        raise Failed("the environment folder is not empty: %s" % folder)
    code, out, err = runner([python, "-m", "venv", folder])
    if code != 0:
        raise Failed("the environment was not created: %s" % (err or out).strip()[-200:])
    found = [p for p in (folder / "Scripts" / "python.exe", folder / "bin" / "python") if p.is_file()]
    if not found:
        raise Failed("the environment has no interpreter")
    return found[0]


def step_install(python, runner=run):
    code, out, err = runner([python, "-m", "pip", "install", "-r", ROOT / "requirements.txt"])
    if code != 0:
        raise Failed("pip failed: %s" % (err or out).strip()[-300:])
    return "requirements.txt installed"


def step_packages(python, runner=run):
    probe = ("import importlib, json\nout = {}\nfor name in %r:\n    try:\n        importlib.import_module(name)\n"
             "        out[name] = None\n    except Exception as e:\n        out[name] = type(e).__name__\n"
             "print(json.dumps(out))\n" % (PACKAGES,))
    code, out, err = runner([python, "-c", probe], env=child_env())
    if code != 0:
        raise Failed("the import probe failed: %s" % err.strip()[-200:])
    missing = {k: v for k, v in json.loads(out.strip().splitlines()[-1]).items() if v}
    if missing:
        raise Failed("not importable: %s" % ", ".join(sorted(missing)))
    return "%d packages import" % len(PACKAGES)


def step_startup(python, runner=run):
    code, out, err = runner([python, ROOT / "scripts" / "preflight.py", "--check-startup", "--json",
                             "--backend-profile", "local"], env=child_env())
    try:
        report = json.loads(out.strip().splitlines()[-1])
        rows = {row["id"]: row for row in report["checks"]}
    except (ValueError, KeyError, IndexError):
        raise Failed("the startup check gave no report: %s" % (err or out).strip()[-200:])
    if rows.get("server", {}).get("status") != "PASS":
        raise Failed("the console's packages are not ready: %s" % rows.get("server", {}).get("detail", ""))
    return "console packages ready; local models %s; GPU %s" % (
        rows.get("local_models", {}).get("status", "not checked"), rows.get("gpu", {}).get("status", "not checked"))


def stage_case(folder):
    """The worked case in a bundle's layout: the targets file inside context/."""
    folder = Path(folder)
    for name in ("context", "conventions"):
        shutil.copytree(CASE / name, folder / name)
    shutil.copy2(CASE / TARGETS, folder / "context" / TARGETS)
    return folder


def judge_no_model_run(status, findings):
    """Why a no-model run did not pass, or None."""
    if status.get("state") != "completed":
        return "the run did not complete: %s" % status.get("state")
    if status.get("model_calls") != 0:
        return "the run made model calls: %s" % status.get("model_calls")
    relation, computed, stated = EXPECTED_FINDING
    if not any(f.get("relation") == relation and {f.get("value_a"), f.get("value_b")} == {computed, stated}
               for f in findings):
        return "the total that does not add up was not found"
    return None


def step_no_model(python, work, runner=run):
    bundle, out = stage_case(Path(work) / "bundle"), Path(work) / "no_model_run"
    code, stdout, stderr = runner([python, ROOT / "benchmark" / "baselines" / "python_only.py", "--bundle", bundle,
                                   "--out", out], env=child_env())
    if code != 0:
        raise Failed("the no-model run exited %s: %s" % (code, stderr.strip()[-300:]))
    text = stdout[stdout.index("{"):] if "{" in stdout else ""
    try:
        status = json.loads(text)
    except ValueError:
        raise Failed("the no-model run gave no status")
    findings = []
    for path in out.rglob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        findings += _records(value)
    why = judge_no_model_run(status, findings)
    if why:
        raise Failed(why)
    return "completed with no model call; found %s, %d against %d" % EXPECTED_FINDING


def _records(value):
    """Every object carrying a relation, anywhere in a run's JSON."""
    out = []
    if isinstance(value, dict):
        if "relation" in value:
            out.append(value)
        for item in value.values():
            out += _records(item)
    elif isinstance(value, list):
        for item in value:
            out += _records(item)
    return out


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fetch(url, token=None):
    """The status of a GET, whatever it is."""
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token} if token else {})
    try:
        with urllib.request.urlopen(request, timeout=20) as reply:
            return reply.status
    except urllib.error.HTTPError as e:
        return e.code


def judge_console(statuses):
    """Why the console did not pass, or None."""
    wanted = {"health": 200, "console": 200, "runs_no_token": 401, "runs_with_token": 200}
    wrong = {k: statuses.get(k) for k, v in wanted.items() if statuses.get(k) != v}
    return "unexpected answers: %s" % wrong if wrong else None


def step_console(python, work):
    token = secrets.token_urlsafe(24)
    port = free_port()
    log = Path(work) / "server.log"
    env = child_env({"SHIMMER_TOKEN_HASH": hashlib.sha256(token.encode()).hexdigest(), "SHIMMER_PORT": str(port),
                     "SHIMMER_HOST": "127.0.0.1", "SHIMMER_BACKEND_PROFILE": SERVER_PROFILE,
                     "SHIMMER_OUTPUT_DIR": str(Path(work) / "runs")})
    base = "http://127.0.0.1:%d" % port
    with log.open("w", encoding="utf-8") as sink:
        server = subprocess.Popen([str(python), str(ROOT / "scripts" / "server.py")], stdout=sink, stderr=sink,
                                  env=env, cwd=str(ROOT))
        try:
            deadline = time.time() + SERVER_START_SECONDS
            while True:
                if server.poll() is not None:
                    tail = log.read_text(encoding="utf-8", errors="replace").strip()[-300:]
                    raise Failed("the server stopped: %s" % tail)
                try:
                    if fetch(base + "/health") == 200:
                        break
                except OSError:
                    pass
                if time.time() > deadline:
                    raise Failed("the server did not answer within %d seconds" % SERVER_START_SECONDS)
                time.sleep(1)
            statuses = {"health": fetch(base + "/health"), "console": fetch(base + "/console"),
                        "runs_no_token": fetch(base + "/runs"), "runs_with_token": fetch(base + "/runs", token)}
        finally:
            server.terminate()
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                server.kill()
    why = judge_console(statuses)
    if why:
        raise Failed(why)
    return "the console answers, and a token is required"


def perform(steps):
    """Runs (name, function) in order until one fails. Returns the rows, later steps not_run."""
    rows, stopped = [], False
    for name, function in steps:
        if stopped:
            rows.append({"step": name, "status": "NOT_RUN", "detail": "an earlier step failed"})
            continue
        started = time.time()
        try:
            rows.append({"step": name, "status": "PASS", "detail": str(function() or ""),
                         "seconds": round(time.time() - started, 1)})
        except (Failed, OSError, subprocess.SubprocessError, ValueError) as exc:
            stopped = True
            rows.append({"step": name, "status": "FAIL", "detail": str(exc) or type(exc).__name__,
                         "seconds": round(time.time() - started, 1)})
    return rows


def verdict(rows, clean):
    """(exit code, the one line a reader takes away)."""
    if any(r["status"] != "PASS" for r in rows):
        return 1, "FAILED at step %s" % next(r["step"] for r in rows if r["status"] != "PASS")
    return 0, ("Clean install passed. No model was run." if clean else
               "Every step passed in an existing environment. This is not a clean install: nothing was installed.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--venv", type=Path, help="a new or empty folder for the new environment")
    where.add_argument("--python", type=Path, help="an existing environment's interpreter: no install")
    parser.add_argument("--report", type=Path, help="write the steps as JSON here")
    args = parser.parse_args(argv)
    held = {"python": args.python or Path(sys.executable)}
    with tempfile.TemporaryDirectory(prefix="shimmer_clean_install_") as work:
        def new_environment():
            held["python"] = step_venv(held["python"], args.venv)
            return str(held["python"])
        steps = [("python", lambda: step_python(held["python"]))]
        if args.venv:
            steps += [("venv", new_environment), ("install", lambda: step_install(held["python"]))]
        steps += [("packages", lambda: step_packages(held["python"])),
                  ("startup", lambda: step_startup(held["python"])),
                  ("no_model", lambda: step_no_model(held["python"], work)),
                  ("console", lambda: step_console(held["python"], work))]
        rows = perform(steps)
    code, line = verdict(rows, clean=bool(args.venv))
    for row in rows:
        print("[%s] %s: %s" % (row["status"], row["step"], row["detail"]))
    print(line)
    if args.report:
        args.report.write_text(json.dumps({"clean_install": bool(args.venv), "exit": code, "verdict": line,
                                           "steps": rows}, indent=2) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
