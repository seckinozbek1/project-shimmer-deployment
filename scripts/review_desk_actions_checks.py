"""Gate proof for the v1.05 review desk, steps 2 and 3 (checks 621 and 622;
docs/loop/stages/V105_UI_DESIGN.md).

No pipeline is run: the server is loaded from scripts/server.py into a temporary root
(startup_submit_checks._isolated_server: its run scan, staging scan, context and run
folders all confined), and its subprocess.Popen is replaced. The page's own DeskViews
functions run in Node; their output is sent to the real routes through FastAPI's test
client. Each group is neutralised (one line of the page taken out), fails, is restored
and passes.

  start    (621) the start form. DeskViews.startPlan refuses no target, a duplicate name,
           no privacy choice and Sensitive while the privacy layer is inactive (the server
           refuses that one too, 409); submitFields gives nothing until confirmed. The
           confirmed fields and the files go to POST /submit, and the fake run starter sees
           both override flags, --output-dir on the run's own folder, --mode standalone,
           the targets and the earlier version as the page planned them. Neutralised (the
           privacy field dropped), the server refuses with 400 and nothing starts.
  actions  (622) cancel, decisions, log and downloads on fixture runs. An exposed run
           waiting for a decision shows its question, the page's Approve body is recorded
           (202, the decision file written verbatim) and the page says recorded, not
           resumed; a second answer is 409. A queued run is cancelled through the page's
           planned route and the page says nothing was deleted. Every log and download
           route the page plans for the exposed run answers 200, a running run's archive
           is called partial. A sealed run's question is timings only, its record plans
           no log and no download, and GET /approvals shows it without its text.
           Neutralised (the sealed return taken out), the page plans a sealed log route
           the server refuses (403), so the proof fails.
"""
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

PAGE = ROOT / "scripts" / "ui" / "desk.html"
FLAGS = ("--sensitivity-layer-inactive-override", "--no-redaction-override")
EXPOSED_ID = "20261119_020000__aaa111"
QUEUED_ID = "20261119_020500__bbb222"
SEALED_ID = "20261119_021000__ccc333"
SEALED_MARKER = "sealed-question-never-shown"
PRIVACY_LINE = 'sensitive: privacy === "sensitive" ? "true" : "false",'
SEALED_LINE = "if (sealed) { return acts; }"

NODE = r"""
const fs = require("fs"), vm = require("vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const calls = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const ctx = { console }; ctx.window = ctx; vm.createContext(ctx);
[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].forEach(m => vm.runInContext(m[1], ctx));
const V = vm.runInContext("DeskViews", ctx), out = {};
calls.forEach(c => { out[c[0]] = V[c[1]].apply(null, c[2]); });
process.stdout.write(JSON.stringify(out));
"""


class Refused(AssertionError):
    pass


def _need(cond, what):
    if not cond:
        raise Refused(what)


def _views(page_text, calls):
    """Run DeskViews functions in Node: calls is [[key, function, [args]]]."""
    if str(ROOT / "tools") not in sys.path:
        sys.path.append(str(ROOT / "tools"))
    from cloud_run_common import no_window  # HIDDEN-A
    with tempfile.TemporaryDirectory(prefix="shimmer_desk_actions_node_") as td:
        script, page, data = Path(td) / "views.js", Path(td) / "desk.html", Path(td) / "calls.json"
        script.write_text(NODE, encoding="utf-8")
        page.write_text(page_text, encoding="utf-8")
        data.write_text(json.dumps(calls), encoding="utf-8")
        done = subprocess.run(["node", str(script), str(page), str(data)], capture_output=True, text=True,
                              encoding="utf-8", timeout=60, creationflags=no_window())
    _need(done.returncode == 0, "node: %s" % done.stderr[:400])
    return json.loads(done.stdout)


def _neutralised(text, line):
    _need(text.count(line) == 1, "neutralisation anchor %r not found once in desk.html" % line)
    return text.replace(line, "")


class _Child:
    def __init__(self):
        self.returncode = 0
        self.stdout = iter(())

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode


def _fake_subprocess(popen):
    return SimpleNamespace(Popen=popen, run=subprocess.run, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT,
                           TimeoutExpired=subprocess.TimeoutExpired)


# ---------------------------------------------------------------- start (621)
def _start_once(page_text):
    """One pass of the start-form proof on page_text; Refused on any gap."""
    from fastapi.testclient import TestClient
    import preflight
    import role_resolution
    import startup_submit_checks as ssc
    with tempfile.TemporaryDirectory(prefix="shimmer_desk_start_") as tmp:
        root = Path(tmp)
        server = ssc._isolated_server(root)
        files = ssc._fixture(root)
        access = secrets.token_urlsafe(24)
        headers = {"Authorization": "Bearer " + access}
        calls = []

        def child(argv, **kwargs):
            roles = role_resolution.resolve_review_roles(root)
            calls.append({"argv": list(argv), "targets": roles["targets"], "prior": roles["prior"]})
            return _Child()

        server.subprocess = _fake_subprocess(child)
        original_start = server._start_next_job
        server._start_next_job = lambda: None
        listing = [{"name": n, "size": len(c)} for n, c in files.items()]
        roles = {"sample.md": "target", "earlier.md": "prior", "reference.md": "grounding",
                 "review_conventions.md": "rules"}
        inactive, active = {"sensitive_layer_active": False}, {"sensitive_layer_active": True}
        out = _views(page_text, [
            ["no_target", "startPlan", [listing, {}, "normal", inactive, ""]],
            ["duplicate", "startPlan", [listing + [{"name": "SAMPLE.md", "size": 1}], roles, "normal", inactive, ""]],
            ["no_privacy", "startPlan", [listing, roles, None, inactive, ""]],
            ["sensitive", "startPlan", [listing, roles, "sensitive", inactive, ""]],
            ["sensitive_active", "startPlan", [listing, roles, "sensitive", active, ""]],
            ["normal", "startPlan", [listing, roles, "normal", inactive, "Check this synthetic document."]],
        ])
        for key in ("no_target", "duplicate", "no_privacy", "sensitive"):
            _need(not out[key]["ok"] and out[key]["fields"] is None, "the page accepted the %s plan" % key)
        _need("inactive" in out["sensitive"]["note"] and out["sensitive_active"]["ok"],
              "the Sensitive note or the active-layer plan is wrong: %r" % out["sensitive"]["note"])
        plan = out["normal"]
        _need(plan["ok"] and plan["targets"] == ["sample.md"] and plan["prior"] == ["earlier.md"]
              and plan["rules"] == ["review_conventions.md"] and all(f in plan["note"] for f in FLAGS),
              "the Normal plan is wrong: %r" % plan)
        fields = _views(page_text, [["unconfirmed", "submitFields", [plan, False]],
                                    ["confirmed", "submitFields", [plan, True]],
                                    ["html", "startPlanHtml", [plan]]])
        _need(fields["unconfirmed"] is None, "fields were given before the plan was confirmed")
        _need("review_conventions.md" in fields["html"] and "never overwritten" in fields["html"], "plan view wrong")
        data = dict(fields["confirmed"])
        upload = [("files", (n, c.encode(), "text/plain")) for n, c in files.items()]
        with patch.dict(os.environ, {"SHIMMER_TOKEN_HASH": hashlib.sha256(access.encode()).hexdigest(),
                                     "SHIMMER_BACKEND_PROFILE": "local"}), \
                patch.object(preflight, "sensitive_readiness", return_value=(False, "inactive in this fixture")):
            client = TestClient(server.app)
            try:
                refused = client.post("/submit", headers=headers, files=upload,
                                      data=dict(data, sensitive="true"))
                _need(refused.status_code == 409 and not calls,
                      "the server took a Sensitive run the page refused: %d" % refused.status_code)
                accepted = client.post("/submit", headers=headers, files=upload, data=data)
                _need(accepted.status_code == 202, "/submit refused the page's fields: %d %s"
                      % (accepted.status_code, accepted.text[:300]))
                run_id = accepted.json()["run_id"]
                server._run_job(run_id)
            finally:
                server._start_next_job = original_start
                server.shutdown_jobs()
                client.close()
        _need(len(calls) == 1, "the fake run starter saw %d starts" % len(calls))
        argv = calls[0]["argv"]
        _need(all(f in argv for f in FLAGS), "the start lacks an override flag: %r" % argv)
        _need(argv[argv.index("--output-dir") + 1] == str(server.RUNS_DIR / run_id), "--output-dir is not the run folder")
        _need(argv[argv.index("--mode") + 1] == "standalone" and argv[argv.index("--task") + 1] == "review"
              and argv[argv.index("--question") + 1] == "Check this synthetic document.", "mode, task or question wrong")
        _need(calls[0]["targets"] == ["sample.md"] and calls[0]["prior"] == ["earlier.md"],
              "roles at the start: %r" % calls[0])
    return "fields from the page, 202, one fake start with both flags and --output-dir"


def run_start():
    if not _ready():
        return "PASS", "not run here: %s" % _missing()
    text = PAGE.read_text(encoding="utf-8")
    try:
        detail = _start_once(text)
    except Refused as error:
        return "FAIL", str(error)
    try:
        _start_once(_neutralised(text, PRIVACY_LINE))
        return "FAIL", "neutralised (no privacy field), the start proof still passed: it does not discriminate"
    except Refused as error:
        failed = str(error)
    try:
        _start_once(text)
    except Refused as error:
        return "FAIL", "restored: %s" % error
    return "PASS", "%s; neutralised (privacy field dropped) failed: %s; restored, passed" % (detail, failed[:120])


# ---------------------------------------------------------------- actions (622)
def _action_fixture(runs, now):
    for run_id in (EXPOSED_ID, QUEUED_ID, SEALED_ID):
        run = runs / run_id
        (run / "audit").mkdir(parents=True)
        (run / "logs").mkdir()
        if run_id == QUEUED_ID:
            continue
        (run / "deliverables" / "doc_a").mkdir(parents=True)
        (run / "deliverables" / "doc_a" / "reviewed_document.md").write_text("# doc_a\n", encoding="utf-8")
        (run / "audit" / "pairing_map.json").write_text(json.dumps({"doc_a": {"document_id": "doc_a"}}), encoding="utf-8")
        (run / "logs" / "pipeline_stdout.log").write_text(
            "".join("line %d\n" % i for i in range(60)) + "last <b>line</b>\n", encoding="utf-8")
        message = SEALED_MARKER if run_id == SEALED_ID else "Approve the new model for CONV-001?"
        (run / "audit" / "pending_approval.json").write_text(json.dumps(
            {"topic": "model_gate", "payload": {"message": message, "rule": "CONV-001"},
             "asked_at": (now - timedelta(minutes=2)).isoformat()}), encoding="utf-8")
    (runs / SEALED_ID / "seal.json").write_text(json.dumps({"exposure": "sealed"}), encoding="utf-8")


def _action_job(run_id, now, status):
    return {"run_id": run_id, "status": status, "task": "review", "review_mode": "paired",
            "submitted_at": (now - timedelta(minutes=10)).isoformat(),
            "started_at": None if status == "queued" else (now - timedelta(minutes=9)).isoformat(),
            "completed_at": None, "progress": None, "files": ["doc_a.md"], "native_intake": True}


def _actions_once(page_text):
    from fastapi.testclient import TestClient
    import startup_submit_checks as ssc
    with tempfile.TemporaryDirectory(prefix="shimmer_desk_actions_") as tmp:
        root = Path(tmp)
        server = ssc._isolated_server(root)
        started = []

        def no_run(*a, **k):
            started.append(a)
            raise Refused("a desk action started a process")

        server.subprocess = _fake_subprocess(no_run)
        now = datetime.now(timezone.utc)
        _action_fixture(server.RUNS_DIR, now)
        with server.JOBS_LOCK:
            server.JOBS[:] = [_action_job(EXPOSED_ID, now, "running"), _action_job(QUEUED_ID, now, "queued"),
                              _action_job(SEALED_ID, now, "running")]
        access = secrets.token_urlsafe(24)
        auth = {"Authorization": "Bearer " + access}
        with patch.dict(os.environ, {"SHIMMER_TOKEN_HASH": hashlib.sha256(access.encode()).hexdigest()}):
            client = TestClient(server.app)
            try:
                exposed = client.get("/runs/" + EXPOSED_ID, headers=auth).json()
                queued = client.get("/runs/" + QUEUED_ID, headers=auth).json()
                sealed = client.get("/runs/" + SEALED_ID, headers=auth).json()
                approvals = client.get("/approvals", headers=auth).json()
                log_text = client.get("/runs/%s/log" % EXPOSED_ID, headers=auth).text
                _need(exposed["state"] == "awaiting_approval" and sealed["state"] == "awaiting_approval",
                      "fixture states: %s %s" % (exposed["state"], sealed["state"]))
                out = _views(page_text, [
                    ["exposed", "actions", [exposed]], ["sealed", "actions", [sealed]], ["queued", "actions", [queued]],
                    ["exposed_html", "approvalHtml", [exposed]], ["sealed_html", "approvalHtml", [sealed]],
                    ["approvals", "approvalsHtml", [approvals]], ["body", "approvalBody", ["APPROVE", " fixture reason "]],
                    ["log", "logHtml", [log_text]], ["partial", "downloadNote", [True]],
                    ["sealed_actions_html", "actionsHtml", [sealed]]])
                _need("Approve the new model" in out["exposed_html"] and 'data-decision="DENY"' in out["exposed_html"],
                      "the exposed question or its buttons are missing")
                _need(SEALED_MARKER not in json.dumps(out) and "timings only" in out["sealed_html"]
                      and "timings only" in out["approvals"], "a sealed question is shown or not marked timings only")
                ex = out["exposed"]
                _need(ex["cancel"] and ex["approval"] and ex["log"] and len(ex["downloads"]) == 2, "exposed actions: %r" % ex)
                sa = out["sealed"]
                for path in [sa["log"]] + [d["path"] for d in sa["downloads"]]:
                    if path:
                        code = client.get(path, headers=auth).status_code
                        _need(code == 200, "the page plans %s for a sealed run, which answered %d" % (path, code))
                _need(sa["log"] is None and not sa["downloads"] and sa["cancel"] and sa["approval"]
                      and "data-log" not in out["sealed_actions_html"], "sealed actions: %r" % sa)
                for path in [ex["log"]] + [d["path"] for d in ex["downloads"]]:
                    got = client.get(path, headers=auth)
                    _need(got.status_code == 200, "the page plans %s, which answered %d" % (path, got.status_code))
                    if "/deliverables" in path and path.endswith("/deliverables"):
                        _need(got.headers.get("X-Shimmer-Partial") == "true", "a running run's archive is not partial")
                _need("Partial archive" in out["partial"], "the partial note is missing")
                _need("last &lt;b&gt;line&lt;/b&gt;" in out["log"] and "line 20\n" not in out["log"] and "(40 lines)" in out["log"],
                      "the log tail is wrong or not escaped")
                answer = client.post(ex["approval"], headers=auth, json=out["body"])
                _need(answer.status_code == 202, "the page's decision was not recorded: %d" % answer.status_code)
                written = json.loads((server.RUNS_DIR / EXPOSED_ID / "audit" / "approval_decision.json").read_text(encoding="utf-8"))
                _need(written["decision"] == "APPROVE" and written["rationale"] == "fixture reason", "decision file: %r" % written)
                _need(client.post(ex["approval"], headers=auth, json=out["body"]).status_code == 409, "a second answer was taken")
                cancelled = client.post(out["queued"]["cancel"], headers=auth)
                _need(cancelled.status_code == 200 and cancelled.json()["state"] == "cancelled",
                      "the page's cancel route: %d %s" % (cancelled.status_code, cancelled.text[:200]))
                after = _views(page_text, [["approval", "approvalResultHtml", [answer.json()]],
                                           ["cancel", "cancelResultHtml", [cancelled.json()]],
                                           ["done", "actions", [cancelled.json()]]])
                _need("Recorded is not resumed" in after["approval"] and "approved" not in after["approval"].lower(),
                      "the decision answer claims more than a record")
                _need("Nothing was deleted" in after["cancel"] and after["done"]["cancel"] is None,
                      "the cancel answer or the cancelled run's actions are wrong")
                _need((server.RUNS_DIR / QUEUED_ID / "audit").is_dir(), "the cancelled run's folder was removed")
            finally:
                server.shutdown_jobs()
                client.close()
        _need(not started, "a process was started")
    return ("exposed question shown, decision recorded verbatim (202, then 409), page says recorded not resumed; "
            "queued run cancelled, nothing deleted; log and two zips 200, archive partial; sealed: timings only, no log or download")


def run_actions():
    if not _ready():
        return "PASS", "not run here: %s" % _missing()
    text = PAGE.read_text(encoding="utf-8")
    try:
        detail = _actions_once(text)
    except Refused as error:
        return "FAIL", str(error)
    try:
        _actions_once(_neutralised(text, SEALED_LINE))
        return "FAIL", "neutralised (sealed return taken out), the actions proof still passed: it does not discriminate"
    except Refused as error:
        failed = str(error)
    try:
        _actions_once(text)
    except Refused as error:
        return "FAIL", "restored: %s" % error
    return "PASS", "%s; neutralised failed: %s; restored, passed" % (detail, failed[:120])


def _missing():
    absent = []
    try:
        import fastapi  # noqa: F401
    except ImportError:
        absent.append("fastapi")
    if shutil.which("node") is None:
        absent.append("node")
    return " and ".join(absent) + " absent" if absent else ""


def _ready():
    return not _missing()


def run_group(name):
    return {"start": run_start, "actions": run_actions}[name]()


if __name__ == "__main__":
    status = 0
    for group in sys.argv[1:] or ["start", "actions"]:
        result, detail = run_group(group)
        print(group, result, detail)
        status |= result != "PASS"
    sys.exit(status)
