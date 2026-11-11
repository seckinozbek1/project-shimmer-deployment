"""Gate check 316 (D-S23 item 1, open item 68): under the local backend profile no agent
reaches the web, whatever its registry flag (may_use_web) says; web access opens only under
the cloud profile.

The one place web access is opened is `search_router.SearchRouter.search`: every engine it
can reach (the api plan, the direct institution fetch, the ddgs package, the DDG scrape and
Brave) is called from there and from nowhere else. This module runs that path under the
local profile with `urllib.request.urlopen`, `socket.create_connection` and
`socket.socket.connect` replaced by stand-ins that record the host and refuse, and the ddgs
package replaced by a recorder on the router (it does not go through Python's sockets), and
fails if any non-local connection is attempted; then the same path under the cloud profile,
where it must try (the stand-ins still refuse, so nothing leaves this machine). The refusal
is logged (`web_access_refused`) and the run summary states the profile and whether web
access was open.

Neutralised twice: the refusal statement removed from `search()`, and the rule
`web_access_open` opened for every profile; each must fail, and the restored code must pass.
No network, no weights, temporary folders only."""

from __future__ import annotations

import ast
import contextlib
import inspect
import json
import logging
import os
import socket
import tempfile
import textwrap
import urllib.request
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import search_router

PLAN_URL = "https://records.example.org/v1/lookup"
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
EGRESS_METHODS = ("_fetch_url", "_ddg_search", "_ddg_package", "_ddg_html_scrape", "_brave_search")
WEB_AGENT = "FACT_CHECKER"
CLOSED_LINE = "web access: closed for this run"
OPEN_LINE = "web access: open for this run"


class _Refused(OSError):
    """Raised by every network stand-in: the check never lets a connection through."""


def _host(address):
    if isinstance(address, tuple) and address:
        return str(address[0])
    return str(address)


@contextlib.contextmanager
def _recorded_network(attempts):
    def urlopen(request, *args, **kwargs):
        url = getattr(request, "full_url", None) or str(request)
        attempts.append(("urlopen", urlparse(url).hostname or url))
        raise _Refused("network refused by check 316")

    def create_connection(address, *args, **kwargs):
        attempts.append(("create_connection", _host(address)))
        raise _Refused("network refused by check 316")

    def connect(self, address):
        attempts.append(("socket.connect", _host(address)))
        raise _Refused("network refused by check 316")

    with patch.object(urllib.request, "urlopen", urlopen), \
            patch.object(socket, "create_connection", create_connection), \
            patch.object(socket.socket, "connect", connect):
        yield


class _Records(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _router(cls, root, attempts):
    router = cls(project_root=root, keys={}, registry={WEB_AGENT: {"may_use_web": True}})

    def ddgs_package(query, max_results):
        attempts.append(("ddgs", "ddgs package"))
        return [], "ddgs refused by check 316"

    router._ddg_package = ddgs_package
    return router


def _leg(cls, profile):
    """Run search() for a web-enabled roster agent and for a system caller under `profile`.
    Returns (attempts, refusals, log messages)."""
    attempts, refusals = [], []
    records = _Records()
    logger = logging.getLogger("shimmer")
    logger.addHandler(records)
    try:
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(os.environ, {"SHIMMER_BACKEND_PROFILE": profile}), \
                _recorded_network(attempts):
            for agent in (WEB_AGENT, None):
                router = _router(cls, Path(tmp), attempts)
                try:
                    router.search("check 316 query", agent=agent, claim_type="check316",
                                  query_plan={"primary": {"engine": "api", "url": PLAN_URL}})
                except PermissionError:
                    refusals.append(agent or "system")
    finally:
        logger.removeHandler(records)
    return attempts, refusals, records.messages


def _non_local(attempts):
    return [f"{kind} {host}" for kind, host in attempts if host not in LOCAL_HOSTS]


def _summary(profile):
    """The run summary's own writer, executed in isolation, under `profile`."""
    import localization_checks
    write = localization_checks.pipeline_function("write_deliverables_run_summary")
    with tempfile.TemporaryDirectory() as tmp, \
            patch.dict(os.environ, {"SHIMMER_BACKEND_PROFILE": profile}):
        path = write(Path(tmp) / "deliverables", [], {}, total_cost_usd=0.0, task="review")
        return path.read_text(encoding="utf-8")


def _problems(cls):
    """Every way the web path breaks the rule, as a list of sentences (empty is a pass)."""
    problems, notes = [], []
    attempts, refusals, messages = _leg(cls, "local")
    reached = _non_local(attempts)
    if reached:
        problems.append("under the local profile a non-local connection was attempted: "
                        + ", ".join(reached))
    if refusals != [WEB_AGENT, "system"]:
        problems.append(f"under the local profile search() refused {refusals}, "
                        f"expected [{WEB_AGENT!r}, 'system']")
    logged = [m for m in messages if m.startswith("web_access_refused backend_profile=local")]
    if len(logged) != 2:
        problems.append(f"{len(logged)} web_access_refused events logged under the local "
                        f"profile, expected 2")
    attempts, refusals, _ = _leg(cls, "")
    if _non_local(attempts) or len(refusals) != 2:
        problems.append("an empty backend profile opened web access")
    attempts, refusals, _ = _leg(cls, "cloud")
    hosts = {host for _, host in attempts}
    if refusals:
        problems.append(f"under the cloud profile search() refused {refusals}")
    expected = {urlparse(PLAN_URL).hostname, "html.duckduckgo.com", "ddgs package"}
    if not expected <= hosts:
        problems.append(f"under the cloud profile the web path did not try every engine: "
                        f"tried {sorted(hosts)}, expected at least {sorted(expected)}")
    notes.append(f"cloud tried {len(attempts)} connection(s), all refused by the stand-ins")
    local_text, cloud_text = _summary("local"), _summary("cloud")
    if CLOSED_LINE not in local_text or "- backend profile: local" not in local_text:
        problems.append("the local run summary does not say the profile and that web access "
                        "was closed")
    if OPEN_LINE not in cloud_text or "- backend profile: cloud" not in cloud_text:
        problems.append("the cloud run summary does not say the profile and that web access "
                        "was open")
    return problems, notes


def egress_outside_search(source):
    """Names of functions in `source` (search_router.py) that call an egress method or
    urlopen while being neither search() nor an egress method: any such function would be a
    second way to the web that the refusal does not cover."""
    allowed = set(EGRESS_METHODS) | {"search"}
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name in allowed:
            continue
        for inner in ast.walk(node):
            name = (inner.attr if isinstance(inner, ast.Attribute)
                    else inner.id if isinstance(inner, ast.Name) else "")
            if name in EGRESS_METHODS or name == "urlopen":
                found.append(node.name)
                break
    return found


def _without_refusal():
    """search() with its profile refusal statement removed, on a subclass of the router."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(search_router.SearchRouter.search)))
    func = tree.body[0]
    kept = [s for s in func.body
            if not (isinstance(s, ast.If) and ast.unparse(s.test) == "not web_access_open(profile)")]
    if len(kept) != len(func.body) - 1:
        raise AssertionError("the profile refusal statement was not found in search(); "
                             "the neutralisation cannot be built")
    func.body = kept
    func.decorator_list = []
    namespace = dict(vars(search_router))
    exec(compile(ast.Module(body=[func], type_ignores=[]), "search_neutralised", "exec"), namespace)
    return type("NeutralisedRouter", (search_router.SearchRouter,), {"search": namespace["search"]})


def check():
    """(status, detail) for the gate."""
    source = Path(inspect.getsourcefile(search_router)).read_text(encoding="utf-8")
    second = egress_outside_search(source)
    if second:
        return "FAIL", "a second way to the web outside search(): " + ", ".join(second)
    if egress_outside_search(source + "\n\ndef probe(r):\n    return r._fetch_url('x')\n") != ["probe"]:
        return "FAIL", "the egress scan did not flag a planted second caller; it proves nothing"
    problems, notes = _problems(search_router.SearchRouter)
    if problems:
        return "FAIL", "; ".join(problems)
    proofs = []
    try:
        neutral_cls = _without_refusal()
    except AssertionError as exc:
        return "FAIL", str(exc)
    broken, _ = _problems(neutral_cls)
    if not any("non-local connection" in p for p in broken):
        return "FAIL", "neutralised (refusal removed), the local leg still passed; the check proves nothing"
    proofs.append("refusal removed FAILS (" + broken[0] + ")")
    with patch.object(search_router, "web_access_open", lambda profile=None: True):
        broken, _ = _problems(search_router.SearchRouter)
    if not (any("non-local connection" in p for p in broken)
            and any("local run summary" in p for p in broken)):
        return "FAIL", "neutralised (rule opened for every profile), a leg still passed; the check proves nothing"
    proofs.append("rule opened for every profile FAILS (" + "; ".join(broken[:1] + broken[-1:]) + ")")
    again, _ = _problems(search_router.SearchRouter)
    if again:
        return "FAIL", "after restoring: " + "; ".join(again)
    return "PASS", ("local profile: search() refused the web agent and the system caller, 0 non-local "
                    "connections, 2 web_access_refused events; empty profile closed; "
                    + "; ".join(notes) + "; run summary states profile and web access under both; "
                    "egress only through search(); neutralise: " + " | ".join(proofs)
                    + "; restore PASSES")


if __name__ == "__main__":
    print(json.dumps(check()))
