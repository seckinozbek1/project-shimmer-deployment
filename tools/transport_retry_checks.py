#!/usr/bin/env python3
"""Gate proofs for beta item 28 (check 707; OPEN_ITEMS 180, 181), bound files: temp fixtures only, no provider call.

  classify       ssh exit 255, and scp at exit 255 or with a connect-stage message (timed out, refused, unreachable,
                 no route, resolve, kex) are transport failures; a remote command's own non-zero exit, scp's
                 'lost connection', 'Connection closed' or 'Broken pipe' after a remote failure, and exit 0 are not
  retry          a required call failing for its connection is tried again after 5, 15 and 45 s and succeeds;
                 still failing after four tries it is exhausted; not required, or a remote exit 1, is never retried;
                 a wait that does not fit in what is left of the timeout is not taken; the first try keeps the whole
                 timeout; a hang (TimeoutExpired) is raised unchanged
  batch          a batch entry whose transport failed after its retries is recorded and the next entry runs; any
                 other failure stops the batch as before; a failed phase start stops it unless a poll reads the
                 phase dead; a second entry failing in a row stops it
  start_once     (a Linux shell: bash with setsid here, else WSL Ubuntu; skipped and said so when neither exists)
                 retried_launch_command sent twice with one nonce starts the work once and returns the same pid; a new
                 nonce starts it again
  cat_file       archive_closure.Tree reads every file through one `git cat-file --batch` process, byte for byte what
                 `git show` gives; a name the commit does not hold is Unreadable, and an uncached file read after it
                 is still what `git show` gives
  disk_rule      launch_floors reads config/laptop_disk_floor.json of the main checkout SHIMMER_MAIN_CHECKOUT names,
                 not its own tree's copy; with no main checkout named, its own copy; a patched DISK_CONFIG as it is

Each proof is run as built (passes), with one line of the module neutralised (must fail), restored and run again.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools" / "loop"), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import archive_closure as ac  # noqa: E402
import launch_floors as lf  # noqa: E402
import ordinary_final_cloud as ofc  # noqa: E402
import reasoning_methods_checks as rmc  # noqa: E402
from cloud_run_common import no_window  # noqa: E402

caught, with_source = rmc.caught, rmc.with_source
SKIPPED = []


def done(code, err=b""):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=b"", stderr=err)


def observe_classify():
    ssh, scp = ["ssh", "-o", "x", "host", "cmd"], ["scp", "a", "host:b"]
    return (ofc.transport_failed(ssh, 255, b"ssh: connect to host 1.2.3.4 port 22: Connection timed out"),
            ofc.transport_failed(scp, 1, b"ssh: connect to host 1.2.3.4 port 22: Connection timed out\r\nlost connection"),
            ofc.transport_failed(ssh, 1, b""), ofc.transport_failed(scp, 1, b"scp: /x: No such file or directory"),
            ofc.transport_failed(ssh, 0, b""), ofc.transport_failed(["ssh-keygen"], 255, b""),
            ofc.transport_failed(scp, 1, b"scp: write remote: No space left on device\r\nlost connection"),
            ofc.transport_failed(scp, 1, b"Connection closed by remote host"),
            ofc.transport_failed(scp, 1, b"client_loop: send disconnect: Broken pipe"),
            ofc.transport_failed(scp, 255, b""))


def expected_classify():
    return True, True, False, False, False, False, False, False, False, True


class Script:
    """A fake `run(argv, seconds)` answering each call from a list, with a fake clock that sleep advances."""

    def __init__(self, codes, hang_at=None):
        self.codes, self.calls, self.now, self.waits, self.hang_at = list(codes), [], 1000.0, [], hang_at

    def run(self, argv, seconds):
        self.calls.append(seconds)
        if self.hang_at is not None and len(self.calls) == self.hang_at:
            raise subprocess.TimeoutExpired(argv, seconds)
        code = self.codes.pop(0)
        return done(code, b"Connection timed out" if code else b"")

    def sleep(self, s):
        self.waits.append(s)
        self.now += s

    def clock(self):
        self.now += 0.25        # every reading of the clock takes a little time, as a real one does
        return self.now


def _retry(codes, required=True, timeout=600, argv=("ssh", "h", "c"), hang_at=None):
    s = Script(codes, hang_at)
    seen = []
    r, attempts, exhausted = ofc.run_with_retry(list(argv), timeout, required, s.run, s.sleep, s.clock,
                                                on_retry=lambda n, code, wait: seen.append((n, code, wait)))
    return r.returncode, attempts, exhausted, s.waits, s.calls[0], len(seen)


def observe_retry():
    recovered = _retry([255, 255, 0])
    exhausted = _retry([255, 255, 255, 255])
    not_required = _retry([255], required=False)
    remote_exit = _retry([1])
    short = _retry([255, 0], timeout=4)
    hang = caught(lambda: _retry([0], hang_at=1))
    return recovered, exhausted, not_required, remote_exit, short, hang


def expected_retry():
    return ((0, 3, False, [5, 15], 600, 2), (255, 4, True, [5, 15, 45], 600, 3), (255, 1, False, [], 600, 0),
            (1, 1, False, [], 600, 0), (255, 1, True, [], 4, 0), "raised TimeoutExpired")


def observe_batch():
    ran, recorded = [], []

    def one(entry):
        ran.append(entry["index"])
        if entry["index"] == 1:
            raise ofc.TransportFailure("Transport failed after 4 attempts: batch_project_from_store_start")

    failed = ofc.run_batch([{"index": i} for i in range(4)], one, lambda e, exc, f: recorded.append((e["index"], list(f))))
    stopped = []

    def other(entry):
        stopped.append(entry["index"])
        if entry["index"] == 1:
            raise RuntimeError("Salvage requested: no new phase is started")

    stop = caught(lambda: ofc.run_batch([{"index": i} for i in range(4)], other, lambda *a: None))

    def start_lost(entry):
        if entry["index"] == 1:
            exc = ofc.TransportFailure("Transport failed after 4 attempts: batch_workload_start")
            exc.phase_key = "batch_workload_1"
            raise exc

    polled = []
    alive = caught(lambda: ofc.run_batch([{"index": i} for i in range(3)], start_lost, lambda *a: None,
                                         lambda key: polled.append(key) or False))
    dead = ofc.run_batch([{"index": i} for i in range(3)], start_lost, lambda *a: None, lambda key: True)
    unpolled = caught(lambda: ofc.run_batch([{"index": i} for i in range(3)], start_lost, lambda *a: None))

    def two_in_a_row(entry):
        if entry["index"] in (1, 2):
            raise ofc.TransportFailure("Transport failed after 4 attempts: batch_transfer")

    row = caught(lambda: ofc.run_batch([{"index": i} for i in range(4)], two_in_a_row, lambda *a: None))

    def apart(entry):
        if entry["index"] in (0, 2):
            raise ofc.TransportFailure("Transport failed after 4 attempts: batch_transfer")

    separate = ofc.run_batch([{"index": i} for i in range(4)], apart, lambda *a: None)
    return ran, failed, recorded, stopped, stop, alive, polled, dead, unpolled, row, separate


def expected_batch():
    return ([0, 1, 2, 3], [1], [(1, [1])], [0, 1], "raised RuntimeError", "raised TransportFailure",
            ["batch_workload_1"], [1], "raised TransportFailure", "raised TransportFailure", [0, 2])


def linux_runner():
    if os.name != "nt" and shutil.which("bash") and shutil.which("setsid"):
        def run(command):
            r = subprocess.run(["bash", "-c", command], capture_output=True, timeout=60)
            return r.returncode, (r.stdout + r.stderr).decode("utf8", "replace")
        return run
    exe = shutil.which("wsl.exe") or shutil.which("wsl")
    if exe is None:
        return None

    def run(command):
        r = subprocess.run([exe, "-d", "Ubuntu", "-e", "bash", "-c", command], capture_output=True, timeout=60,
                           creationflags=no_window())
        return r.returncode, (r.stdout + r.stderr).decode("utf8", "replace")
    try:
        rc, out = run("echo linux-shell-ready")
    except Exception:  # noqa: BLE001 - no shell
        return None
    return run if rc == 0 and "linux-shell-ready" in out else None


def observe_start_once():
    run = linux_runner()
    if run is None:
        if "start_once" not in SKIPPED:
            SKIPPED.append("start_once")
        return "skipped"
    root = "/tmp/shimmer_retry_%d_%d" % (os.getpid(), int(time.time() * 1000) % 10 ** 9)
    phases = ofc.phases_dir(root)
    count = phases + "/count"
    work = "echo x >> %s; sleep 3" % count
    try:
        a = run(ofc.retried_launch_command(root, "start", work, "n1"))
        b = run(ofc.retried_launch_command(root, "start", work, "n1"))
        time.sleep(1)
        once = run("wc -l < %s" % count)[1].strip()
        c = run(ofc.retried_launch_command(root, "start", work, "n2"))
        time.sleep(1)
        twice = run("wc -l < %s" % count)[1].strip()
        same_pid = a[0] == 0 and b[0] == 0 and a[1].strip().splitlines()[-1] == b[1].strip().splitlines()[-1]
        return same_pid, once, c[0], twice
    finally:
        run("rm -rf %s %s" % (root, phases))


def expected_start_once():
    return "skipped" if "start_once" in SKIPPED else (True, "1", 0, "2")


def observe_cat_file():
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                          creationflags=no_window()).stdout.strip()
    tree = ac.Tree(ROOT, head)
    names = sorted(n for n in tree.names if n.startswith("tools/loop/") and n.endswith(".py"))[:12]
    try:
        same = all(tree.read(n) == subprocess.run(["git", "-C", str(ROOT), "show", "%s:%s" % (head, n)],
                                                  capture_output=True, creationflags=no_window()).stdout for n in names)
        one_process = tree._batch is not None
        missing = caught(lambda: tree.read("no/such/file.py"))
        fresh = sorted(n for n in tree.names if n.startswith("tools/loop/") and n.endswith(".py"))[12]
        after = fresh not in tree._cache and tree.read(fresh) == subprocess.run(
            ["git", "-C", str(ROOT), "show", "%s:%s" % (head, fresh)], capture_output=True,
            creationflags=no_window()).stdout
    finally:
        tree.close()
    return len(names) == 12, same, one_process, missing, after


def expected_cat_file():
    return True, True, True, "raised Unreadable", True


def observe_disk_rule():
    with tempfile.TemporaryDirectory() as base:
        main = Path(base) / "main"
        (main / ".git").mkdir(parents=True)
        (main / "config").mkdir()
        (main / "config" / "laptop_disk_floor.json").write_text(json.dumps({"margin_gib": 7, "lambda_launch_floor_gib": 9}),
                                                                 encoding="utf-8")
        own = json.loads(lf.OWN_DISK_CONFIG.read_text(encoding="utf-8"))["margin_gib"]
        with patch.dict(os.environ, {"SHIMMER_MAIN_CHECKOUT": str(main)}):
            named = (lf.margin_gib(), lf.lambda_launch_floor_gib(), lf.disk_config() == main / "config" / "laptop_disk_floor.json")
        with patch.dict(os.environ, {"SHIMMER_MAIN_CHECKOUT": str(Path(base) / "absent")}):
            refused = lf.disk_config() == lf.OWN_DISK_CONFIG, lf.margin_gib()[0] == float(own)
        fixture = Path(base) / "fixture.json"
        fixture.write_text(json.dumps({"margin_gib": 3}), encoding="utf-8")
        with patch.dict(os.environ, {"SHIMMER_MAIN_CHECKOUT": str(main)}), patch.object(lf, "DISK_CONFIG", fixture):
            patched = lf.margin_gib()
        return named, refused, patched


def expected_disk_rule():
    return ((7.0, "config"), (9.0, "config"), True), (True, True), (3.0, "config")


PROOFS = ("classify", "retry", "batch", "start_once", "cat_file", "disk_rule")
NEUTRALISATIONS = {
    "ssh_any_exit": (lambda: with_source(ofc, "transport_failed", "('ssh','ssh.exe'):return returncode==255", "('ssh','ssh.exe'):return True"), ("classify",)),
    "scp_never": (lambda: with_source(ofc, "transport_failed",
                                      "return returncode==255 or bool(CONNECTION_FAILURE.search(output or b''))",
                                      "return False"), ("classify",)),
    "no_retry": (lambda: with_source(ofc, "run_with_retry",
                                     "if not (required and transport_failed(argv,r.returncode,r.stderr)):return r,attempt+1,False",
                                     "return r,attempt+1,False"), ("retry",)),
    "wait_unbounded": (lambda: with_source(ofc, "retry_wait", "return wait if remaining is None or wait<remaining else None",
                                           "return wait"), ("retry",)),
    "first_try_shortened": (lambda: with_source(ofc, "run_with_retry", "timeout if attempt==0 else ", ""), ("retry",)),
    "start_not_checked": (lambda: with_source(ofc, "run_batch",
                                             "            if exc.phase_key and not (start_dead and start_dead(exc.phase_key)):raise\n",
                                             ""), ("batch",)),
    "row_not_checked": (lambda: with_source(ofc, "run_batch", "            if previous:raise\n", ""), ("batch",)),
    "scp_wide": (lambda: patch.object(ofc, "CONNECTION_FAILURE", __import__("re").compile(
        rb"Connection (?:timed out|refused|reset|closed)|Broken pipe|lost connection")), ("classify",)),
    "batch_stops": (lambda: with_source(ofc, "run_batch", "        except TransportFailure as exc:\n",
                                        "        except ZeroDivisionError as exc:\n"), ("batch",)),
    "batch_swallows_all": (lambda: with_source(ofc, "run_batch", "        except TransportFailure as exc:\n",
                                               "        except Exception as exc:\n"), ("batch",)),
    "start_twice": (lambda: with_source(ofc, "retried_launch_command",
                                        "+' ] && [ -f '+shlex.quote(started)+' ]; then cat '", "+' ] && false; then cat '"),
                    ("start_once",)),
    "show_per_file": (lambda: patch.object(ac.Tree, "read", lambda self, name: self._git("show", "%s:%s" % (self.commit, name)) if name != "no/such/file.py" else self._git("show", "x:" + name)),
                      ("cat_file",)),
    "own_tree_rule": (lambda: with_source(lf, "disk_config", "        if main.is_file() and not shared._is_link(main)",
                                          "        if False and main.is_file() and not shared._is_link(main)"),
                      ("disk_rule",)),
    "fixture_overridden": (lambda: with_source(lf, "disk_config", "    if Path(DISK_CONFIG) != OWN_DISK_CONFIG:\n",
                                               "    if False:\n"), ("disk_rule",)),
}


def run():
    space = globals()
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            first = {n: space["observe_" + n]() for n in PROOFS}
            broken = {}
            for name, (make, proofs) in NEUTRALISATIONS.items():
                if any(p in SKIPPED for p in proofs):
                    continue
                with make():
                    broken[name] = {n: caught(space["observe_" + n]) for n in proofs}
            again = {n: space["observe_" + n]() for n in PROOFS}
    except Exception as exc:
        return "FAIL", "%s %s" % (type(exc).__name__, str(exc)[:300])
    expected = {n: space["expected_" + n]() for n in PROOFS}
    for n in PROOFS:
        if first[n] != expected[n]:
            return "FAIL", "%s as built: %s" % (n, str(first[n])[:700])
        if again[n] != expected[n]:
            return "FAIL", "%s after restore: %s" % (n, str(again[n])[:400])
    for name, results in broken.items():
        for n, value in results.items():
            if value == expected[n]:
                return "FAIL", "%s still passes when %s is neutralised" % (n, name)
    note = "; skipped with no Linux shell: %s" % ", ".join(SKIPPED) if SKIPPED else ""
    return "PASS", ("%d proofs, %d neutralisations, fail, restore, pass: one-shot ssh and scp calls retried on a lost "
                    "connection within the phase deadline, a failed batch entry ended and the next run, a retried start "
                    "never starting the work twice, the archive closure reading through one git process, the disk rule "
                    "read from the main checkout (%s)%s" % (len(PROOFS), len(broken), ", ".join(PROOFS), note))


if __name__ == "__main__":
    status, detail = run()
    print("transport_retry", status, detail)
    sys.exit(0 if status == "PASS" else 1)
