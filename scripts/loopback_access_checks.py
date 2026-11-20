"""Gate proof for keyless local mode (check 681; D-835, Seckin 20 November 2026 13:11).

In the alpha the review desk opens with no key, but only while the server binds a loopback
address. scripts/server.py arms the mode through arm_keyless_local(host), called by each start
path with the exact host it hands to uvicorn; SHIMMER_KEYLESS_LOCAL=1 only asks for it.

  1  No mode: with the variable unset, arming answers False, /inputs, /runs and /approvals are
     401 without a token and 200 with the right one, and the desk page carries no keyless mark.
  2  Keyless on a non-loopback host: arming 0.0.0.0, ::, a LAN address and a name refuses
     (KeylessRefused), the mode stays off and the routes stay 401 without a token.
  3  Keyless on loopback (127.0.0.1, ::1, localhost): the protected routes answer 200 with no
     token for a loopback client, a wrong token changes nothing, and the desk page carries the
     keyless mark.
  4  The second layer: while keyless, a non-loopback client address, a foreign Host, a foreign
     Origin and a proxy forwarding header are each refused (403).
  5  The start paths: `python scripts/server.py` and `scripts/desktop_server.py` with the mode on
     and SHIMMER_HOST=0.0.0.0 exit 1 with the keyless refusal before anything is served; with no
     mode and no token hash, server.py still refuses as before.
Rows 1 to 4 run on a server module loaded on a temporary root through FastAPI's test client;
no process is started by them and no pipeline runs. Neutralised twice, each fails: is_loopback_host
answering True for every host (row 2: a non-loopback host is armed), and the second layer
_check_keyless_request a no-op (row 4: a non-loopback client is served); restored, it passes. Needs fastapi and httpx; without
them it says it did not run. No token value is printed or written.
"""
import hashlib
import os
import secrets
import subprocess
import sys
import tempfile
from contextlib import contextmanager, nullcontext
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT / "tools") not in sys.path:
    sys.path.append(str(ROOT / "tools"))

PROTECTED = ("/inputs", "/runs", "/approvals")
MARK = 'var DESK_ACCESS = "keyless-local";'
NON_LOOPBACK = ("0.0.0.0", "::", "192.168.1.10", "example.org", "")
LOOPBACK = ("127.0.0.1", "::1", "localhost")


class Refused(AssertionError):
    pass


def _need(cond, what):
    if not cond:
        raise Refused(what)


@contextmanager
def _env(**values):
    saved = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _server(root):
    import startup_submit_checks as ssc
    server = ssc._isolated_server(root)
    server.INPUT_DIR = root / "input"
    (root / "input" / "conventions").mkdir(parents=True, exist_ok=True)
    server.CONVENTION_REGISTRY_PATH = root / "input" / "registry.json"
    return server


def _client(server, client_host="127.0.0.1"):
    from fastapi.testclient import TestClient
    return TestClient(server.app, base_url="http://127.0.0.1:8000", client=(client_host, 50123))


def _rows(server, neutral):
    """Rows 1 to 4 on one server module. Returns a short count line."""
    from fastapi import HTTPException
    access = secrets.token_urlsafe(24)
    digest = hashlib.sha256(access.encode("utf-8")).hexdigest()
    good = {"Authorization": "Bearer " + access}
    wrong = {"Authorization": "Bearer wrong-" + secrets.token_hex(4)}
    asked = 0
    ctx = (patch.object(server, "is_loopback_host", lambda host: True) if neutral == "host" else
           patch.object(server, "_check_keyless_request", lambda client_host, headers: None) if neutral == "layer"
           else nullcontext())
    with ctx, _env(SHIMMER_TOKEN_HASH=digest, SHIMMER_KEYLESS_LOCAL=None):
        local = _client(server)
        # Row 1: no mode, the token gate as before.
        _need(server.arm_keyless_local("127.0.0.1") is False and not server.keyless_active(),
              "with SHIMMER_KEYLESS_LOCAL unset, arming switched keyless on")
        for path in PROTECTED:
            _need(local.get(path).status_code == 401, "no mode: %s without a token was not 401" % path)
            _need(local.get(path, headers=wrong).status_code == 401, "no mode: %s with a wrong token was not 401" % path)
            _need(local.get(path, headers=good).status_code == 200, "no mode: %s with the token was not 200" % path)
            asked += 3
        _need(MARK not in local.get("/console?view=desk").text, "no mode: the desk page carries the keyless mark")

        with _env(SHIMMER_KEYLESS_LOCAL="1"):
            # Row 2: keyless asked for on a host that is not loopback refuses.
            for host in NON_LOOPBACK:
                try:
                    server.arm_keyless_local(host)
                except server.KeylessRefused:
                    pass
                else:
                    raise Refused("keyless on host %r was armed, not refused" % host)
                _need(not server.keyless_active(), "keyless stayed on after host %r was refused" % host)
            for path in PROTECTED:
                _need(local.get(path).status_code == 401, "refused keyless: %s without a token was not 401" % path)
                asked += 1

            # Row 3: keyless on loopback serves the protected routes with no token.
            with _env(SHIMMER_TOKEN_HASH=None):
                for host in LOOPBACK:
                    _need(server.arm_keyless_local(host) is True and server.keyless_active(),
                          "keyless on loopback host %r was not armed" % host)
                    for path in PROTECTED:
                        _need(local.get(path).status_code == 200, "keyless %s: %s without a token was not 200" % (host, path))
                        _need(local.get(path, headers=wrong).status_code == 200,
                              "keyless %s: %s with a stray token was not 200" % (host, path))
                        asked += 2
                ipv6 = _client(server, "::1")
                _need(ipv6.get("/inputs").status_code == 200, "keyless: an ::1 client was refused")
                _need(MARK in local.get("/console?view=desk").text, "keyless: the desk page lacks the keyless mark")

                # Row 4: the second layer refuses anything that is not this computer.
                remote = _client(server, "192.168.1.20")
                tunnel_like = {"X-Forwarded-For": "203.0.113.9"}
                cases = (("a non-loopback client", remote, {}),
                         ("a foreign Host", local, {"Host": "evil.example"}),
                         ("a foreign Origin", local, {"Origin": "http://evil.example"}),
                         ("a forwarded request", local, tunnel_like),
                         ("a Cloudflare forwarded request", local, {"CF-Connecting-IP": "203.0.113.9"}))
                for what, client, headers in cases:
                    for path in PROTECTED:
                        got = client.get(path, headers=headers).status_code
                        _need(got == 403, "keyless: %s on %s answered %d, expected 403" % (what, path, got))
                        asked += 1
                _need(local.get("/inputs", headers={"Origin": "http://127.0.0.1:8000"}).status_code == 200,
                      "keyless: the page's own loopback Origin was refused")
                try:
                    server._check_keyless_request(None, {"host": "127.0.0.1"})
                except HTTPException as error:
                    _need(error.status_code == 403, "keyless: no client address raised %d" % error.status_code)
                else:
                    raise Refused("keyless: a request with no client address was served")
        server._KEYLESS["host"] = None
    return asked


def _start(script, extra):
    from cloud_run_common import no_window  # HIDDEN-A
    with tempfile.TemporaryDirectory(prefix="shimmer_keyless_start_", ignore_cleanup_errors=True) as td:
        env = {k: v for k, v in os.environ.items()
               if not any(w in k.upper() for w in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL"))
               and k not in ("SHIMMER_CONFIG_PATH", "SHIMMER_OUTPUT_DIR", "SHIMMER_HOST")}
        env.update({"SHIMMER_OUTPUT_DIR": str(Path(td) / "runs"), "TEMP": td, "TMP": td,
                    "PYTHONIOENCODING": "utf-8", "SHIMMER_BACKEND_PROFILE": "local"})
        env.update(extra)
        done = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / script)], cwd=str(ROOT), env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120, creationflags=no_window())
        return done.returncode, done.stderr


def _starts():
    """Row 5: the real start paths refuse keyless on a non-loopback host; no mode refuses as before."""
    for script, line in (("server.py", "Refusing to start: keyless local mode"),
                         ("desktop_server.py", "Cannot start: keyless local mode")):
        code, err = _start(script, {"SHIMMER_KEYLESS_LOCAL": "1", "SHIMMER_HOST": "0.0.0.0"})
        _need(code == 1 and line in err, "%s keyless on 0.0.0.0: exit %s, %r" % (script, code, err[-300:]))
    code, err = _start("server.py", {"SHIMMER_HOST": "127.0.0.1"})
    _need(code == 1 and "SHIMMER_TOKEN_HASH environment variable is not set" in err,
          "server.py with no mode and no token hash: exit %s, %r" % (code, err[-300:]))
    return 3


def _once(neutral=None):
    with tempfile.TemporaryDirectory(prefix="shimmer_keyless_", ignore_cleanup_errors=True) as td:
        return _rows(_server(Path(td)), neutral)


def run_check():
    """("PASS" or "FAIL", detail)."""
    try:
        import fastapi  # noqa: F401
        import httpx  # noqa: F401
    except ImportError as error:
        return "PASS", "not run here: %s absent" % error.name
    try:
        asked = _once()
        starts = _starts()
    except Refused as error:
        return "FAIL", str(error)
    failed = {}
    for mode, what in (("host", "every host taken as loopback"), ("layer", "the second layer a no-op")):
        try:
            _once(neutral=mode)
            return "FAIL", "neutralised (%s), the proof still passed: it does not discriminate" % what
        except Refused as error:
            failed[mode] = str(error)
    try:
        _once()
    except Refused as error:
        return "FAIL", "restored: %s" % error
    return "PASS", ("no mode: data routes 401 without or with a wrong token, 200 with it; keyless refused on %d "
                    "non-loopback hosts and the routes stay 401; keyless on 127.0.0.1, ::1 and localhost: routes 200 "
                    "with no token and the desk page marked; a non-loopback client, foreign Host, foreign Origin and "
                    "forwarded requests 403; %d requests; server.py and desktop_server.py refuse keyless on 0.0.0.0, "
                    "server.py still refuses with no mode and no hash (%d starts); neutralised (every host loopback) "
                    "failed: %s; neutralised (second layer a no-op) failed: %s; restored, passed"
                    % (len(NON_LOOPBACK), asked, starts, failed["host"][:100], failed["layer"][:100]))


if __name__ == "__main__":
    status, detail = run_check()
    print(status, detail)
    sys.exit(0 if status == "PASS" else 1)
