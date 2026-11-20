"""Gate proof for the review desk against a running server process (check 662; D-831 item 2,
D-832 item 3: the link test on the laptop; docs/loop/stages/V105_UI_DESIGN.md).

Checks 620 to 622 drive the app in-process through FastAPI's test client. This check runs the
server as its own process on 127.0.0.1 and a free port and asks it over HTTP, the way the desk
page asks it. No pipeline runs: the server is loaded on a temporary root
(startup_submit_checks._isolated_server: run scan, staging scan, context and run folders
confined) and its PIPELINE is a mock script in that root, which writes a finished run's fixture
outputs and exits 0. The token is made in memory, its hash goes to the child through the
environment, and neither is printed, logged or written.

  1  Start refusal: `python scripts/server.py` with no SHIMMER_TOKEN_HASH exits 1 with its
     "Refusing to start" line.
  2  The open routes: /health and /console?view=desk answer without a token, an unknown view
     is 404; /inputs, /runs, /approvals and a run's /progress are 401 without a token and with
     a wrong one.
  3  The control walk (D-832): the page's own script runs in Node with a small stand-in
     document whose fetch goes to the live server. Every control is fired in turn (Connect,
     Start the review with two files, roles, privacy and the confirm box, Open, Read reviewed
     document, Show the end of the log, each Download, Approve with a rationale, Cancel, the
     /console link) and the requests that follow each one are recorded. CONTROLS maps each
     control to its routes; the page's controls (form ids, input names, links, every data-*
     attribute) must equal the map and the inputs that feed it (FEEDS), every route literal in
     the page's script must belong to a mapped route, every mapped route must be registered in
     scripts/server.py and listed in docs/RUNTIME_REFERENCE.md, and each control must call
     exactly its mapped routes, each answering 200 or 202.
  4  Each control reads or writes the right record: Connect lists input/conventions; Start
     makes one mock pipeline start with both override flags and --output-dir on the run's own
     folder, and the run ends succeeded; Open draws the bus findings (the server's model mark on
     the model finding alone) and the measured progress; Read shows
     deliverables/<doc>/reviewed_document.md; the log shows logs/pipeline_stdout.log; Download
     returns a complete archive holding the reviewed document; Approve writes
     audit/approval_decision.json verbatim and says recorded, not resumed; Cancel moves the
     queued run to cancelled and deletes nothing.
  5  A sealed run shows counts only (CONSOLE-A): its screen says counts and timings only, names
     no document and offers no log or download, its question text appears in no answer or
     screen, and its findings, reviewed document and log are 403.
  6  No key on any screen: no answer and no drawn screen carries the token, its hash, a fixture
     credential placed in the server's environment, or a fixture answer key placed under the
     server's benchmark/keys.
Neutralised twice, each fails: the server's sealed-run refusal replaced by a no-op (a sealed
run's findings are served), and the page's log control taken out (a mapped control is missing
from the page); restored, it passes. Then a keyless pass (D-835): the same server process with
SHIMMER_KEYLESS_LOCAL=1 on 127.0.0.1 and no token hash at all, armed from the host handed to
uvicorn; the page the server serves (with its keyless line) connects by itself before any
control is fired, rows 2 to 6 run with no token anywhere (the data routes 200 without one), and
a sealed run still shows counts only. In the token passes the page must not connect by itself.
Needs fastapi, uvicorn, httpx and node; without them it says it did not run.

`--serve DIR` (operator aid, not the gate) builds the same fixture in DIR, walks the controls,
and keeps the server up until stdin closes, for screenshots; the token is read from the
environment variable SHIMMER_DESK_LIVE_TOKEN and never printed.
"""
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT / "tools") not in sys.path:
    sys.path.append(str(ROOT / "tools"))

PAGE = ROOT / "scripts" / "ui" / "desk.html"
FLAGS = ("--sensitivity-layer-inactive-override", "--no-redaction-override")
SEALED_ID = "20261120_010000__eee111"
QUEUED_ID = "20261120_010500__bbb222"
SEALED_DOC = "doc_sealedname"
SEALED_QUESTION = "sealed-question-text-never-shown"
FINDING_TEXT = "the labelled field is missing in this fixture"
MODEL_TEXT = "a model says the field is missing"

MOCK_PIPELINE = r'''
import json, sys
from pathlib import Path
argv = sys.argv[1:]
out = Path(argv[argv.index("--output-dir") + 1])
record = Path(__file__).with_name("mock_calls.jsonl")
with record.open("a", encoding="utf-8") as f:
    f.write(json.dumps(argv) + "\n")
(out / "audit").mkdir(parents=True, exist_ok=True)
(out / "logs").mkdir(parents=True, exist_ok=True)
(out / "deliverables" / "sample").mkdir(parents=True, exist_ok=True)
(out / "audit" / "pairing_map.json").write_text(json.dumps({"sample": {"document_id": "sample", "pair_count": 1}}), encoding="utf-8")
(out / "deliverables" / "sample" / "reviewed_document.md").write_text(
    "# sample\n\nu01 A labelled field is present.\n\n> CONV-X01: %s\n" % FINDING, encoding="utf-8")
item = {"relation": "sum_mismatch", "record_verdict": "irregular", "unit_id": "u01", "rule_id": "CONV-X01",
        "source_rule_id": "CONV-X01", "explanation": FINDING}
posts = [{"sender": "PAIRED", "body": {"backend": "paired", "model": "python-computed",
          "payload": {"agent": "PAIRED", "doc_id": "sample", "items": [dict(item, item_id="p1")]}}},
         {"sender": "AUDITOR", "body": {"backend": "local", "model": "fixture-model",
          "payload": {"agent": "AUDITOR", "doc_id": "sample", "items": [dict(item, item_id="m1", explanation=MODEL)]}}}]
(out / "logs" / "agent_bus.jsonl").write_text("\n".join(json.dumps(p) for p in posts) + "\n", encoding="utf-8")
print("[progress] phase=9/9 doc=1/1 status=done", flush=True)
'''

LAUNCHER = r'''
import json, sys
from pathlib import Path
repo, root, port, neutral = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4] == "1"
sys.path.insert(0, str(repo / "scripts"))
import startup_submit_checks as ssc
server = ssc._isolated_server(root)
server.PIPELINE = root / "mock_pipeline.py"
server.INPUT_DIR = root / "input"
server.CONVENTION_REGISTRY_PATH = root / "input" / "registry.json"
# The sealed fixture job is "running" (waiting for a decision) from the start; the queue runs one
# job at a time, so the queue starter looks past it, or the started run would wait behind it.
fixture_jobs = json.loads((root / "jobs.json").read_text(encoding="utf-8"))
fixture_ids = {j["run_id"] for j in fixture_jobs}
with server.JOBS_LOCK:
    server.JOBS.extend(fixture_jobs)
_queue_start = server._start_next_job
def _start_past_fixture():
    with server.JOBS_LOCK:
        held = [j for j in server.JOBS if j["run_id"] in fixture_ids]
        server.JOBS[:] = [j for j in server.JOBS if j["run_id"] not in fixture_ids]
    try:
        _queue_start()
    finally:
        with server.JOBS_LOCK:
            server.JOBS[:0] = held
server._start_next_job = _start_past_fixture
if neutral:
    server._refuse_sealed = lambda run_dir: None
import uvicorn
# D-835: keyless local mode is armed from the very host handed to uvicorn, as every start path
# does; it is on only when the environment asks for it (the keyless pass).
host = "127.0.0.1"
server.arm_keyless_local(host)
uvicorn.run(server.app, host=host, port=port, log_level="warning")
'''


# D-832: every control of the desk page and the server routes it calls. A page control missing
# here, a control here missing from the page, a route the walk sees that is not here, or a route
# here the walk does not see, fails. Inputs that only feed a control carry the control they feed.
CONTROLS = {
    "token-form": {("GET", "/inputs"), ("GET", "/health"), ("GET", "/approvals"), ("GET", "/runs")},
    "start-submit": {("POST", "/submit"), ("GET", "/runs")},
    "data-run": {("GET", "/runs/{run_id}"), ("GET", "/runs/{run_id}/progress"),
                 ("GET", "/runs/{run_id}/model-findings"), ("GET", "/runs/{run_id}/findings")},
    "data-doc": {("GET", "/runs/{run_id}/reviewed/{doc_id}")},
    "data-log": {("GET", "/runs/{run_id}/log")},
    "data-download": {("GET", "/runs/{run_id}/deliverables"), ("GET", "/runs/{run_id}/deliverables/{doc_id}")},
    "data-approve": {("POST", "/runs/{run_id}/approval"), ("GET", "/approvals")},
    "data-cancel": {("POST", "/runs/{run_id}/cancel"), ("GET", "/runs")},
    "href:/console": {("GET", "/console")},
}
FEEDS = {"token": "token-form", "start-files": "start-submit", "start-question": "start-submit",
         "start-privacy": "start-submit", "start-confirm": "start-submit", "data-role-file": "start-submit",
         "data-rationale": "data-approve", "data-decision": "data-approve"}

# The page's own script, run in Node with a small stand-in document; its fetch goes to the live
# server. Each step dispatches one control's event and records the requests that follow it.
WALK = r"""
const fs = require("fs"), vm = require("vm");
const [page, base, token, out] = process.argv.slice(2);
const html = fs.readFileSync(page, "utf8");
const els = {}, docHandlers = {}, log = [], steps = [];
let inflight = 0, privacy = null, submitted = null;
function el(id) {
  if (!els[id]) {
    const h = {};
    els[id] = { id, value: "", checked: false, files: [], innerHTML: "", textContent: "", listeners: h,
      addEventListener: (t, f) => { (h[t] = h[t] || []).push(f); }, getAttribute: () => null };
  }
  return els[id];
}
const document = {
  getElementById: el,
  addEventListener: (t, f) => { (docHandlers[t] = docHandlers[t] || []).push(f); },
  querySelector: (sel) => {
    if (sel.indexOf("start-privacy") >= 0) { return privacy ? { value: privacy } : null; }
    if (sel.indexOf("data-rationale") >= 0) { return { value: " fixture reason " }; }
    return null;
  },
  activeElement: null,
  createElement: () => ({ click() {}, remove() {} }),
  body: { appendChild() {} },
};
function pageFetch(path, options) {
  options = options || {};
  inflight++;
  return fetch(base + path, options).then(async (r) => {
    const entry = { method: options.method || "GET", path, status: r.status };
    if (path === "/submit") { try { submitted = await r.clone().json(); } catch (e) {} }
    log.push(entry); inflight--; return r;
  }, (e) => { inflight--; log.push({ method: options.method || "GET", path, status: 0 }); throw e; });
}
const ctx = { console, document, fetch: pageFetch, FormData, File, Blob, Object, Promise, JSON, String,
  URL: { createObjectURL: () => "blob:x", revokeObjectURL() {} },
  setTimeout: () => 0, clearTimeout() {}, confirm: () => true };
ctx.window = ctx; vm.createContext(ctx);
[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].forEach(m => vm.runInContext(m[1], ctx));
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
async function idle() { let quiet = 0; while (quiet < 3) { await sleep(120); quiet = inflight ? 0 : quiet + 1; } }
function target(attrs, extra) { return Object.assign({ getAttribute: (k) => (k in attrs ? attrs[k] : null) }, extra || {}); }
async function step(control, fire) { const from = log.length; fire(); await idle(); steps.push({ control, calls: log.slice(from) }); }
function attrs(text, name) { return [...String(text).matchAll(new RegExp(name + '="([^"]*)"', "g"))].map(m => m[1].replace(/&amp;/g, "&")); }
const click = (a) => (docHandlers.click || []).forEach(f => f({ target: target(a) }));
const change = (t) => (docHandlers.change || []).forEach(f => f({ target: t }));
async function harness(path) {
  const r = await fetch(base + path, { headers: token ? { Authorization: "Bearer " + token } : {} });
  return r.status === 200 ? r.json() : null;
}
async function until(path, ok) {
  for (let i = 0; i < 300; i++) { const r = await harness(path); if (r && ok(r)) { return r; } await sleep(300); }
  return null;
}
const snap = {};
(async () => {
  // D-835: with no user action. In keyless local mode the page connects by itself; otherwise
  // it waits for the token and calls nothing.
  await step("token-form", () => {});
  snap.auto_state = el("token-state").textContent; snap.auto_inputs = el("inputs").innerHTML;
  const connect = () => { el("token").value = token; el("token-form").listeners.submit.forEach(f => f({ preventDefault() {} })); };
  await step("token-form", connect);
  snap.inputs = el("inputs").innerHTML;
  const files = [new File(["# Synthetic document\n\nA labelled field is present.\n"], "sample.md", { type: "text/plain" }),
                 new File(["# Synthetic review rules\n\n## CONV-X01 [required]\nThe labelled field must be present.\n"], "review_conventions.md", { type: "text/plain" })];
  el("start-files").files = files;
  el("start-files").listeners.change.forEach(f => f({}));
  change(target({ "data-role-file": "0" }, { value: "target" }));
  change(target({ "data-role-file": "1" }, { value: "rules" }));
  privacy = "normal"; change(target({}, { name: "start-privacy" }));
  el("start-confirm").checked = true;
  await step("start-submit", () => el("start-submit").listeners.click.forEach(f => f({})));
  snap.start_state = el("start-state").innerHTML + el("start-state").textContent;
  const runId = submitted && submitted.run_id;
  snap.run_id = runId;
  snap.finished = await until("/runs/" + runId, r => r.state === "stopped");
  snap.sealed = await until("/runs/__SEALED__", r => r.state === "awaiting_approval");
  await step("data-run", () => click({ "data-run": runId }));
  snap.run = el("run").innerHTML; snap.findings = el("findings").innerHTML; snap.model = el("model-findings").innerHTML;
  snap.progress = el("progress").innerHTML;
  for (const d of attrs(snap.run, "data-doc")) { await step("data-doc", () => click({ "data-doc": d })); }
  snap.reader = el("reader").innerHTML;
  for (const p of attrs(snap.run, "data-log")) { await step("data-log", () => click({ "data-log": p })); }
  snap.log = el("log").innerHTML;
  snap.downloads = [];
  for (const p of attrs(snap.run, "data-download")) {
    await step("data-download", () => click({ "data-download": p })); snap.downloads.push(el("action-result").innerHTML);
  }
  await step("token-form", connect);
  snap.approvals = el("approvals").innerHTML; snap.runs = el("runs").innerHTML;
  for (const id of attrs(snap.approvals, "data-run")) { await step("data-run", () => click({ "data-run": id })); }
  snap.sealed_run = el("run").innerHTML; snap.sealed_progress = el("progress").innerHTML;
  for (const id of new Set(attrs(snap.sealed_run, "data-approve"))) {
    await step("data-approve", () => click({ "data-approve": id, "data-decision": "APPROVE" }));
    snap.approval_result = el("action-result").innerHTML;
  }
  // A running fixture has no process to stop (the server answers 409), so the cancel control is
  // drawn by the page's own actionsHtml for the queued fixture run and clicked there.
  const queued = await harness("/runs/__QUEUED__");
  snap.queued_actions = queued ? vm.runInContext("DeskViews", ctx).actionsHtml(queued) : "";
  for (const id of attrs(snap.queued_actions, "data-cancel")) {
    await step("data-cancel", () => click({ "data-cancel": id })); snap.cancel_result = el("action-result").innerHTML;
  }
  for (const href of attrs(html.split("<script>")[0], "href")) {
    const from = log.length; await pageFetch(href).then(r => r.text()); steps.push({ control: "href:" + href, calls: log.slice(from) });
  }
  snap.elements = Object.fromEntries(Object.entries(els).map(([k, v]) => [k, v.innerHTML + " " + v.textContent]));
  fs.writeFileSync(out, JSON.stringify({ steps, snap }));
})().catch(e => { fs.writeFileSync(out, JSON.stringify({ error: String(e && e.stack || e) })); });
"""


class Refused(AssertionError):
    pass


def _need(cond, what):
    if not cond:
        raise Refused(what)


def _no_window():
    from cloud_run_common import no_window  # HIDDEN-A
    return no_window()


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _fixture(root):
    """Inputs, one sealed run waiting for a decision, the mock pipeline and the planted secrets."""
    (root / "input" / "conventions").mkdir(parents=True)
    (root / "input" / "conventions" / "rules.md").write_text("# Rules\n", encoding="utf-8")
    (root / "input" / "registry.json").write_text(json.dumps({"conventions": [
        {"id": "CONV-X01", "category": "CONV-X01", "severity": "required"}]}), encoding="utf-8")
    answer_marker = "ANSWERKEY-" + secrets.token_hex(8)
    (root / "benchmark" / "keys").mkdir(parents=True)
    (root / "benchmark" / "keys" / "answer_key.json").write_text(json.dumps({"key": answer_marker}), encoding="utf-8")
    run = root / "runs" / SEALED_ID
    (run / "deliverables" / SEALED_DOC).mkdir(parents=True)
    (run / "deliverables" / SEALED_DOC / "reviewed_document.md").write_text("# sealed\n", encoding="utf-8")
    (run / "logs").mkdir()
    (run / "logs" / "pipeline_stdout.log").write_text("sealed log line\n", encoding="utf-8")
    (run / "audit").mkdir()
    (run / "audit" / "pairing_map.json").write_text(json.dumps({SEALED_DOC: {"document_id": SEALED_DOC}}), encoding="utf-8")
    now = datetime.now(timezone.utc)
    (run / "audit" / "pending_approval.json").write_text(json.dumps(
        {"topic": "model_gate", "payload": {"message": SEALED_QUESTION, "rule": "CONV-X01"},
         "asked_at": (now - timedelta(minutes=2)).isoformat()}), encoding="utf-8")
    (run / "seal.json").write_text(json.dumps({"exposure": "sealed"}), encoding="utf-8")
    (root / "jobs.json").write_text(json.dumps([{
        "run_id": SEALED_ID, "status": "running", "task": "review", "review_mode": "paired",
        "submitted_at": (now - timedelta(minutes=10)).isoformat(), "started_at": (now - timedelta(minutes=9)).isoformat(),
        "completed_at": None, "progress": None, "files": [SEALED_DOC + ".md"], "native_intake": True}, {
        "run_id": QUEUED_ID, "status": "queued", "task": "review", "review_mode": "paired",
        "submitted_at": (now - timedelta(minutes=5)).isoformat(), "started_at": None,
        "completed_at": None, "progress": None, "files": ["doc_q.md"], "native_intake": True}]), encoding="utf-8")
    (root / "runs" / QUEUED_ID / "audit").mkdir(parents=True)
    (root / "mock_pipeline.py").write_text(
        "FINDING = %r\nMODEL = %r\n" % (FINDING_TEXT, MODEL_TEXT) + MOCK_PIPELINE, encoding="utf-8")
    (root / "launcher.py").write_text(LAUNCHER, encoding="utf-8")
    return answer_marker


def _child_env(root, extra):
    """The parent's environment without any credential-named variable or config path, plus extra."""
    env = {k: v for k, v in os.environ.items()
           if not any(w in k.upper() for w in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL"))
           and k not in ("SHIMMER_CONFIG_PATH", "SHIMMER_OUTPUT_DIR")}
    env.update({"TEMP": str(root), "TMP": str(root), "PYTHONIOENCODING": "utf-8",
                "SHIMMER_BACKEND_PROFILE": "local"})
    env.update(extra)
    return env


def _refusal(root):
    """Row 1: the operator's start without a token hash refuses."""
    out = root / "refusal_runs"
    out.mkdir()
    done = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "server.py")], cwd=str(ROOT),
                          env=_child_env(root, {"SHIMMER_OUTPUT_DIR": str(out)}), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, creationflags=_no_window())
    _need(done.returncode == 1 and "Refusing to start" in done.stderr,
          "server.py without a token hash: exit %s, %r" % (done.returncode, done.stderr[-300:]))


class _Server:
    def __init__(self, root, token, fake_key, neutral, keyless=False):
        self.port = _free_port()
        self.base = "http://127.0.0.1:%d" % self.port
        # D-835: the keyless pass sets no token hash at all, only the mode.
        access = ({"SHIMMER_KEYLESS_LOCAL": "1"} if keyless else
                  {"SHIMMER_TOKEN_HASH": hashlib.sha256(token.encode("utf-8")).hexdigest()})
        env = _child_env(root, dict(access, ANTHROPIC_API_KEY=fake_key))
        self.proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", str(root / "launcher.py"), str(ROOT), str(root), str(self.port),
             "1" if neutral else "0"], cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=_no_window())

    def wait_up(self, client):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise Refused("the server exited %s: %s" % (self.proc.returncode, self.proc.stderr.read()[-400:]))
            try:
                if client.get(self.base + "/health").status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise Refused("the server did not answer /health within 90 s")

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=20)
        if self.proc.stderr:
            self.proc.stderr.close()


def _route_tables():
    """(the server's registered routes, the RUNTIME_REFERENCE route table), as (METHOD, path) sets."""
    src = (ROOT / "scripts" / "server.py").read_text(encoding="utf-8")
    server = {(m.upper(), p) for m, p in re.findall(r'@app\.(get|post|put|delete)\("([^"]+)"', src)}
    doc = (ROOT / "docs" / "RUNTIME_REFERENCE.md").read_text(encoding="utf-8")
    table = set(re.findall(r'^\| `(GET|POST|PUT|DELETE)` \| `([^`]+)` \|', doc, re.M))
    return server, table


def _inventory(page_text):
    """Every control on the page: ids and names of form controls, links, and every data-* attribute."""
    head = page_text.split("<script>")[0]
    found = set(re.findall(r'<(?:form|button|input|select|a)\b[^>]*\bid="([^"]+)"', head))
    found |= set(re.findall(r'<input\b[^>]*\bname="([^"]+)"', head))
    found |= {"href:" + h for h in re.findall(r'href="([^"]+)"', head)}
    found |= {"data-" + d for d in re.findall(r'data-([a-z-]+)="', page_text)}
    return found


def _fragments(page_text):
    """Every route literal in the page's script ("/runs/", "/progress", ...)."""
    script = "".join(re.findall(r"<script>([\s\S]*?)</script>", page_text))
    return set(re.findall(r'"(/[a-z][a-z\-/]*)', script))


def _norm(path):
    path = path.split("?")[0]
    path = re.sub(r"^/runs/[^/]+", "/runs/{run_id}", path)
    return re.sub(r"/(reviewed|deliverables)/[^/]+$", r"/\1/{doc_id}", path)


def _walk(page, base, token):
    with tempfile.TemporaryDirectory(prefix="shimmer_desk_walk_", ignore_cleanup_errors=True) as td:
        script, out = Path(td) / "walk.js", Path(td) / "walk.json"
        script.write_text(WALK.replace("__SEALED__", SEALED_ID).replace("__QUEUED__", QUEUED_ID), encoding="utf-8")
        done = subprocess.run(["node", str(script), str(page), base, token, str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=240, creationflags=_no_window())
        _need(out.is_file(), "the walk wrote nothing: exit %s %s" % (done.returncode, done.stderr[-300:]))
        walk = json.loads(out.read_text(encoding="utf-8"))
    _need("error" not in walk, "the walk failed: %s" % str(walk.get("error"))[:400])
    return walk


def _check_map(page_text, walk):
    """D-832: controls against the map, the map against the walk and both route tables."""
    expected = set(CONTROLS) | set(FEEDS)
    found = _inventory(page_text)
    _need(found == expected, "controls without a route: %s; mapped controls not on the page: %s"
          % (sorted(found - expected), sorted(expected - found)))
    routes = set().union(*CONTROLS.values())
    loose = [f for f in _fragments(page_text) if not any(f in p for _, p in routes)]
    _need(not loose, "route literals in the page that no control maps: %s" % loose)
    server, table = _route_tables()
    _need(routes <= server, "mapped routes the server does not register: %s" % sorted(routes - server))
    _need(routes <= table, "mapped routes missing from docs/RUNTIME_REFERENCE.md: %s" % sorted(routes - table))
    seen = {}
    for s in walk["steps"]:
        for c in s["calls"]:
            _need(c["status"] in (200, 202), "%s %s from %s answered %d" % (c["method"], c["path"], s["control"], c["status"]))
            seen.setdefault(s["control"], set()).add((c["method"], _norm(c["path"])))
    for control, want in CONTROLS.items():
        got = seen.get(control, set())
        _need(got == want, "%s: routes called %s, mapped %s" % (control, sorted(got), sorted(want)))
    return len(found), len(routes), sum(len(s["calls"]) for s in walk["steps"])


def _session(root, token, fake_key, answer_marker, neutral, keep=None, keyless=False):
    """Rows 2 to 6 against one server process. neutral is None, "server" (the sealed refusal a
    no-op) or "page" (the log control taken out of the page). keep(server, client, auth, run_id)
    is called before the server stops (the --serve aid); the gate passes none. keyless (D-835):
    the server runs in keyless local mode with no token hash, the page served by the server is
    walked, every control and every direct request goes with no token."""
    import httpx
    seen = []
    server = _Server(root, token, fake_key, neutral == "server", keyless=keyless)
    client = httpx.Client(trust_env=False, timeout=30)
    auth = {} if keyless else {"Authorization": "Bearer " + token}
    page_text = PAGE.read_text(encoding="utf-8")
    if neutral == "page":
        line = "if (a.log) { html += '<p><button data-log=\"' + esc(a.log) + '\">Show the end of the log</button></p>'; }"
        _need(page_text.count(line) == 1, "page neutralisation anchor not found once")
        page_text = page_text.replace(line, "")
    page = root / "desk.html"

    def get(path, headers=None, status=200):
        got = client.get(server.base + path, headers=headers)
        seen.append(got.text)
        _need(got.status_code == status, "GET %s answered %d, expected %d: %s" % (path, got.status_code, status, got.text[:200]))
        return got

    try:
        server.wait_up(client)
        # Row 2: the open routes and the token gate.
        get("/health")
        get("/console?view=desk")
        _need("DeskViews" in seen[-1], "/console?view=desk did not serve the desk page")
        mark = 'var DESK_ACCESS = "keyless-local";'
        _need((mark in seen[-1]) == keyless, "the desk page keyless mark is %s in %s mode"
              % ("present" if mark in seen[-1] else "absent", "keyless" if keyless else "token"))
        if keyless:
            # The page the browser gets, with its keyless line, is the page walked.
            page_text = seen[-1]
        page.write_text(page_text, encoding="utf-8")
        get("/console?view=nope", status=404)
        for path in ("/inputs", "/runs", "/approvals", "/runs/%s/progress" % SEALED_ID):
            get(path, status=200 if keyless else 401)
            get(path, headers={"Authorization": "Bearer wrong-" + secrets.token_hex(4)}, status=200 if keyless else 401)

        # Row 3 (D-832): every control walked in the page's own script, its routes against the map.
        walk = _walk(page, server.base, token)
        n_controls, n_routes, n_calls = _check_map(page_text, walk)
        snap = walk["snap"]
        run_id = snap.get("run_id")
        auto = str(snap.get("auto_state"))
        if keyless:
            _need(auto.startswith("connected (local trial") and "rules.md" in str(snap.get("auto_inputs")),
                  "keyless: the page did not connect by itself with no token: %r" % auto[:200])
        else:
            _need(not auto.startswith("connected"), "token mode: the page connected with no token: %r" % auto[:200])

        # Row 4: each control read or wrote the right record.
        _need("rules.md" in snap["inputs"], "Connect: the inputs screen does not list input/conventions/rules.md")
        fin = snap.get("finished") or {}
        _need(fin.get("state") == "stopped" and fin.get("outcome") == "succeeded", "the started run ended %r" % fin)
        calls = [json.loads(x) for x in (root / "mock_calls.jsonl").read_text(encoding="utf-8").splitlines()]
        _need(len(calls) == 1 and all(f in calls[0] for f in FLAGS)
              and calls[0][calls[0].index("--output-dir") + 1] == str(root / "runs" / run_id),
              "Start: the mock pipeline starts were %r" % calls)
        model = get("/runs/%s/model-findings" % run_id, headers=auth).json()
        _need("succeeded" in snap["run"] and "Read reviewed document" in snap["run"], "Open: results screen %s" % snap["run"][:300])
        _need(FINDING_TEXT in snap["findings"] and model.get("mark") and snap["findings"].count(model["mark"]) == 1,
              "Open: the findings screen lacks the bus finding or the model mark is not on the model finding alone: %s"
              % re.sub(r"\s+", " ", snap["findings"])[:500])
        _need(MODEL_TEXT in snap["findings"] and "Documents done" in snap["progress"],
              "Open: the model-written bus finding or the progress screen is missing")
        _need(FINDING_TEXT in snap["reader"], "Read: the reviewed document screen lacks deliverables/sample/reviewed_document.md")
        _need("phase=9/9" in snap["log"], "Log: the screen lacks logs/pipeline_stdout.log")
        _need(snap["downloads"] and all("Complete archive." in d for d in snap["downloads"]), "Download: %r" % snap["downloads"])
        archive = client.get(server.base + "/runs/%s/deliverables" % run_id, headers=auth)
        _need("sample/reviewed_document.md" in zipfile.ZipFile(io.BytesIO(archive.content)).namelist(),
              "Download: the archive lacks the reviewed document")
        decision = json.loads((root / "runs" / SEALED_ID / "audit" / "approval_decision.json").read_text(encoding="utf-8"))
        _need(decision.get("decision") == "APPROVE" and decision.get("rationale") == "fixture reason"
              and "Recorded is not resumed" in snap.get("approval_result", ""), "Approve: decision record %r" % decision)
        after = get("/runs/" + QUEUED_ID, headers=auth).json()
        _need(after.get("state") == "cancelled" and (root / "runs" / QUEUED_ID / "audit").is_dir()
              and "Nothing was deleted" in snap.get("cancel_result", ""), "Cancel: %r" % after.get("state"))

        # Row 5: a sealed run shows counts only.
        _need((snap.get("sealed") or {}).get("exposure") == "sealed", "the sealed fixture run was not seen as sealed")
        _need("counts and timings only" in snap["sealed_run"] and SEALED_DOC not in snap["sealed_run"]
              and "data-log" not in snap["sealed_run"] and "data-download" not in snap["sealed_run"],
              "the sealed screen names a document, plans a log or download, or lacks the counts-only note")
        for path in ("/runs/%s/findings" % SEALED_ID, "/runs/%s/reviewed/%s" % (SEALED_ID, SEALED_DOC),
                     "/runs/%s/log" % SEALED_ID):
            get(path, headers=auth, status=403)
        screens = json.dumps(snap.get("elements")) + json.dumps(snap.get("sealed_progress"))
        _need(SEALED_QUESTION not in screens and not any(SEALED_QUESTION in s for s in seen),
              "the sealed run's question text reached an answer or a screen")

        # Row 6: no key, token or answer key on any answer or screen.
        everything = seen + [json.dumps(snap.get("elements")), json.dumps(walk["steps"])]
        secrets_planted = [(fake_key, "the fixture credential"), (answer_marker, "the fixture answer key")]
        if token:
            secrets_planted += [(token, "the token"), (hashlib.sha256(token.encode("utf-8")).hexdigest(), "the token hash")]
        for secret, what in secrets_planted:
            _need(not any(secret in s for s in everything), "%s appears in an answer or a screen" % what)
        if keep:
            keep(server, client, auth, run_id)
        return "%d controls, %d routes, %d page requests, %d direct requests" % (n_controls, n_routes, n_calls, len(seen))
    finally:
        client.close()
        server.stop()


def _once(neutral=None, keyless=False):
    with tempfile.TemporaryDirectory(prefix="shimmer_desk_live_", ignore_cleanup_errors=True) as td:
        root = Path(td)
        answer_marker = _fixture(root)
        token = "" if keyless else secrets.token_urlsafe(24)
        fake_key = "sk-" + "ant-" + "fixture-" + secrets.token_hex(12)
        if neutral is None and not keyless:
            _refusal(root)
        return _session(root, token, fake_key, answer_marker, neutral, keyless=keyless)



def _missing():
    absent = []
    for name in ("fastapi", "uvicorn", "httpx"):
        try:
            __import__(name)
        except ImportError:
            absent.append(name)
    if shutil.which("node") is None:
        absent.append("node")
    return " and ".join(absent) + " absent" if absent else ""


def run_check():
    """("PASS" or "FAIL", detail)."""
    missing = _missing()
    if missing:
        return "PASS", "not run here: %s" % missing
    try:
        counts = _once()
    except Refused as error:
        return "FAIL", str(error)
    failed = {}
    for mode, what in (("server", "the server's sealed refusal a no-op"), ("page", "the page's log control taken out")):
        try:
            _once(mode)
            return "FAIL", "neutralised (%s), the proof still passed: it does not discriminate" % what
        except Refused as error:
            failed[mode] = str(error)
    try:
        _once()
    except Refused as error:
        return "FAIL", "restored: %s" % error
    # D-835: the same walk with the server in keyless local mode on 127.0.0.1 and no token hash.
    try:
        keyless_counts = _once(keyless=True)
    except Refused as error:
        return "FAIL", "keyless pass: %s" % error
    return "PASS", ("server.py refuses without a token hash; a server process on 127.0.0.1 with a mock pipeline: "
                    "/health and the desk page open, data routes 401 without or with a wrong token; every page control "
                    "walked in the page's own script (%s), each calling exactly its mapped routes, all registered and in "
                    "RUNTIME_REFERENCE; start 202, one mock start with both flags, run succeeded, results, findings, "
                    "reviewed document, log and archive read from their records; decision recorded, cancel deleted "
                    "nothing; sealed run counts only, findings, reviewed and log 403; no token, hash, credential or "
                    "answer key on any answer or screen; neutralised (sealed refusal) failed: %s; neutralised (log "
                    "control) failed: %s; restored, passed; keyless pass (D-835, loopback, no token hash): the page connects by "
                    "itself, every control reaches its mapped routes with no token (%s), sealed run still counts only"
                    % (counts, failed["server"][:110], failed["page"][:110], keyless_counts))



def _serve(target):
    """Operator aid for screenshots: the fixture in target, the started run finished, the server kept up."""
    token = os.environ.get("SHIMMER_DESK_LIVE_TOKEN")
    if not token:
        print("set SHIMMER_DESK_LIVE_TOKEN first", file=sys.stderr)
        return 2
    root = Path(target)
    root.mkdir(parents=True, exist_ok=False)
    marker = _fixture(root)

    def keep(server, client, auth, run_id):
        print(json.dumps({"port": server.port, "run_id": run_id, "sealed_id": SEALED_ID}), flush=True)
        sys.stdin.read()

    _session(root, token, "sk-" + "ant-" + "fixture-" + secrets.token_hex(12), marker, None, keep)
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--serve":
        sys.exit(_serve(sys.argv[2]))
    status, detail = run_check()
    print(status, detail)
    sys.exit(0 if status == "PASS" else 1)
