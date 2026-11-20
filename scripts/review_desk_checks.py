"""Gate proof for the v1.05 review desk, step 1 (check 620, 539 before the renumbering;
docs/loop/stages/V105_UI_DESIGN.md).

Three parts, all on fixtures in a temporary folder; no run is started (the server's
subprocess.Popen is replaced by a fake that fails the proof if called), no model is called
and nothing under the repository's input/, output/, config/ or durable/ is written.

  A  scripts/review_desk.py executed: the inputs listing names files and carries no content;
     progress_reading's four values on a fixture run equal the hand-computed figures, and an
     unstarted run says why each is not measurable; reviewed_document serves the declared
     document and refuses an unknown or escaping name. Neutralised (the listing match taken
     out of reviewed_document), a name escaping the deliverables folder is served, so the
     proof fails; restored, it passes.
  B  (fastapi and node present) the real app through a test client: GET /console?view=desk is
     served without a token, an unknown view is 404, and the three new routes answer 401
     without one; with the token they answer, a sealed run's reviewed document is 403 and its
     progress carries counts only.
  C  (with B) the page's own DeskViews functions run in Node on the route answers from B:
     a sealed run plans no per-flaw route, a model-written finding
     carries the server's mark, Python's does not, and document text is escaped; every route
     the page plans for the exposed run then answers 200 through the test client.
"""
import contextlib
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import review_desk  # noqa: E402

PAGE = ROOT / "scripts" / "ui" / "desk.html"
EXPOSED_ID = "20261119_010000__abc123"
SEALED_ID = "20261119_010500__def456"
CONTENT_MARKER = "fixture-content-never-listed"
TOKEN = "gate-desk-token"
_REAL_POPEN = subprocess.Popen


class Refused(AssertionError):
    pass


def _need(cond, what):
    if not cond:
        raise Refused(what)


def _fixture(tmp):
    """An input root and a runs folder with one exposed and one sealed run."""
    inputs = tmp / "input"
    (inputs / "conventions").mkdir(parents=True)
    (inputs / "context").mkdir()
    (inputs / "conventions" / "rules.md").write_text("# Rules\n" + CONTENT_MARKER, encoding="utf-8")
    (inputs / "context" / "notes.md").write_text(CONTENT_MARKER, encoding="utf-8")
    (inputs / "context" / ".hidden").write_text("x", encoding="utf-8")
    runs = tmp / "runs"
    for run_id in (EXPOSED_ID, SEALED_ID):
        run = runs / run_id
        (run / "deliverables" / "doc_a").mkdir(parents=True)
        (run / "deliverables" / "doc_b").mkdir()
        (run / "deliverables" / "doc_a" / "reviewed_document.md").write_text(
            "# doc_a\n\nu01 <script>x</script> finding quoted here\n", encoding="utf-8")
        (run / "outside").mkdir()
        (run / "outside" / "reviewed_document.md").write_text("escaped", encoding="utf-8")
        (run / "logs").mkdir()
        (run / "audit").mkdir()
        (run / "audit" / "pairing_map.json").write_text(json.dumps(
            {d: {"document_id": d, "pair_count": 2} for d in ("doc_a", "doc_b")}), encoding="utf-8")
    (inputs / "registry.json").write_text(json.dumps({"conventions": [
        {"id": "CONV-001", "category": "CONV-T01", "severity": "required", "rule": "text never listed"}]}),
        encoding="utf-8")
    (runs / SEALED_ID / "seal.json").write_text(json.dumps({"exposure": "sealed"}), encoding="utf-8")
    item = {"relation": "sum_mismatch", "record_verdict": "irregular", "unit_id": "u01", "rule_id": "CONV-001",
            "source_rule_id": "CONV-T01", "explanation": "the total differs"}
    posts = [{"sender": "PAIRED", "body": {"backend": "paired", "model": "python-computed",
                                            "payload": {"agent": "PAIRED", "doc_id": "doc_a", "items": [dict(item, item_id="p1")]}}},
             {"sender": "AUDITOR", "body": {"backend": "local", "model": "fixture-model",
                                             "payload": {"agent": "AUDITOR", "doc_id": "doc_a",
                                                         "items": [dict(item, item_id="m1", explanation="a model says so")]}}}]
    (runs / EXPOSED_ID / "logs" / "agent_bus.jsonl").write_text(
        "\n".join(json.dumps(p) for p in posts) + "\n", encoding="utf-8")
    return inputs, runs


def _job(run_id, now, minutes=10, progress="phase=5.5/9 doc=2/3 agent=AUDITOR status=running"):
    return {"run_id": run_id, "status": "running", "task": "review", "review_mode": "paired",
            "submitted_at": (now - timedelta(minutes=minutes + 1)).isoformat(),
            "started_at": (now - timedelta(minutes=minutes)).isoformat(), "progress": progress,
            "files": [], "native_intake": True}


def part_a(tmp):
    inputs, runs = _fixture(tmp)
    listing = review_desk.inputs_listing(inputs)
    _need(CONTENT_MARKER not in json.dumps(listing), "the inputs listing carries file content")
    _need([f["name"] for f in listing["conventions"]["files"]] == ["rules.md"], "conventions listing wrong: %r" % listing)
    _need([f["name"] for f in listing["context"]["files"]] == ["notes.md"], "hidden file listed or context wrong")
    _need(listing["operational"] == {"present": False, "files": [], "count": 0, "truncated": False},
          "an absent folder is not listed as absent")

    now = datetime(2026, 11, 19, 2, 0, tzinfo=timezone.utc)
    run = runs / EXPOSED_ID
    p = review_desk.progress_reading(_job(EXPOSED_ID, now), run, now=now)
    got = (p["documents_done"], p["documents_total"], p["elapsed_seconds"], p["rate_documents_per_minute"], p["remaining_minutes"])
    _need(got == (1, 3, 600.0, 0.1, 20.0), "four values %r, expected (1, 3, 600.0, 0.1, 20.0)" % (got,))
    _need(p["not_measurable"] == {} and "nominal 9" in (p["phase_note"] or ""), "a measured run lists a gap: %r" % p)
    idle = review_desk.progress_reading({"run_id": EXPOSED_ID, "status": "queued"}, runs / SEALED_ID, now=now)
    _need(idle["elapsed_seconds"] is None and set(idle["not_measurable"]) == {"elapsed", "total", "rate", "remaining"},
          "an unstarted run does not say why each value is not measurable: %r" % idle["not_measurable"])

    _need("finding quoted here" in review_desk.reviewed_document(run, "doc_a"), "the declared document is not served")
    for bad in ("../outside", "doc_b", "nope", ".."):
        try:
            review_desk.reviewed_document(run, bad)
        except LookupError:
            continue
        raise Refused("reviewed_document served %r" % bad)

    # Neutralise: the listing match taken out; an escaping name must then be served.
    source = inspect.getsource(review_desk.reviewed_document)
    line = "    if doc_id not in names:\n        raise LookupError(\"document not found for this run\")\n"
    _need(source.count(line) == 1, "neutralisation anchor not found once")
    space = dict(vars(review_desk))
    exec(source.replace(line, ""), space)
    try:
        leaked = space["reviewed_document"](run, "../outside")
    except LookupError:
        leaked = None
    _need(leaked == "escaped", "neutralised, the escaping name was still refused: the proof does not discriminate")
    try:
        review_desk.reviewed_document(run, "../outside")
        raise Refused("restored, the escaping name is served")
    except LookupError:
        pass
    return inputs, runs, now


@contextlib.contextmanager
def _server(runs, inputs):
    """server.py reloaded on the fixture runs folder, its input root and Popen replaced."""
    import importlib
    saved_env = {k: os.environ.get(k) for k in ("SHIMMER_OUTPUT_DIR", "SHIMMER_TOKEN_HASH")}
    os.environ["SHIMMER_OUTPUT_DIR"] = str(runs)
    os.environ["SHIMMER_TOKEN_HASH"] = hashlib.sha256(TOKEN.encode("utf-8")).hexdigest()
    started = []

    def no_run(*a, **k):
        import traceback
        started.append(a)
        raise Refused("a desk route started a process: %r from %s" % (
            a[:1], " < ".join("%s:%d" % (Path(f.filename).name, f.lineno) for f in traceback.extract_stack()[-6:-1])))

    server = importlib.reload(importlib.import_module("server"))
    saved_popen = server.subprocess.Popen
    server.subprocess.Popen = no_run
    server.INPUT_DIR = inputs
    server.CONVENTION_REGISTRY_PATH = inputs / "registry.json"
    try:
        yield server, started
    finally:
        server.subprocess.Popen = saved_popen
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        # Not reloaded again here: a reload on the real output/runs would rewrite any
        # running job's status.json there (_rebuild_jobs_from_disk).


def part_b(runs, inputs):
    from fastapi.testclient import TestClient
    answers = {}
    now = datetime.now(timezone.utc)  # the route reads the real clock.
    with _server(runs, inputs) as (server, started):
        with server.JOBS_LOCK:
            server.JOBS[:] = [_job(EXPOSED_ID, now), _job(SEALED_ID, now)]
        client = TestClient(server.app)
        page = client.get("/console?view=desk")
        _need(page.status_code == 200 and "DeskViews" in page.text, "GET /console?view=desk did not serve the page")
        _need(client.get("/console?view=deks").status_code == 404, "an unknown view fell back to a page")
        _need("DeskViews" not in client.get("/console").text, "the plain console route serves the desk")
        routes = ("/inputs", "/runs/%s/progress" % EXPOSED_ID, "/runs/%s/reviewed/doc_a" % EXPOSED_ID)
        for path in routes:
            _need(client.get(path).status_code == 401, "%s answered without a token" % path)
        auth = {"Authorization": "Bearer " + TOKEN}
        got = client.get("/inputs", headers=auth)
        _need(got.status_code == 200 and CONTENT_MARKER not in got.text
              and got.json()["folders"]["conventions"]["files"][0]["name"] == "rules.md"
              and got.json()["conventions_compiled"] == [{"id": "CONV-001", "category": "CONV-T01", "severity": "required"}]
              and "text never listed" not in got.text, "/inputs: %s" % got.text[:300])
        prog = client.get(routes[1], headers=auth)
        _need(prog.status_code == 200 and prog.json()["documents_total"] == 3 and prog.json()["exposure"] == "exposed",
              "/progress: %s" % prog.text[:300])
        text = client.get(routes[2], headers=auth)
        _need(text.status_code == 200 and "finding quoted here" in text.text, "/reviewed: %s" % text.text[:200])
        _need(client.get("/runs/%s/reviewed/nope" % EXPOSED_ID, headers=auth).status_code == 404, "unknown doc not 404")
        _need(client.get("/runs/%s/reviewed/doc_a" % SEALED_ID, headers=auth).status_code == 403,
              "a sealed run's reviewed document was served")
        sealed_prog = client.get("/runs/%s/progress" % SEALED_ID, headers=auth).json()
        _need(sealed_prog["exposure"] == "sealed" and isinstance(sealed_prog["documents_done"], int),
              "sealed progress: %r" % sealed_prog)
        answers["exposed_record"] = client.get("/runs/" + EXPOSED_ID, headers=auth).json()
        answers["sealed_record"] = client.get("/runs/" + SEALED_ID, headers=auth).json()
        answers["inputs"] = got.json()
        answers["progress"] = prog.json()
        answers["findings"] = client.get("/runs/%s/findings" % EXPOSED_ID, headers=auth).json()
        answers["model_findings"] = client.get("/runs/%s/model-findings" % EXPOSED_ID, headers=auth).json()
        answers["reviewed"] = text.text
        planned = _node(answers)
        for path in planned["exposed_plan"]:
            code = client.get(path, headers=auth).status_code
            _need(code == 200, "the page plans %s, which answered %d" % (path, code))
        _need(not started, "a process was started")
    return planned


NODE = r"""
const fs = require("fs"), vm = require("vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const a = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const ctx = { console }; ctx.window = ctx; vm.createContext(ctx);
[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].forEach(m => vm.runInContext(m[1], ctx));
const V = vm.runInContext("DeskViews", ctx);
const out = {
  exposed_plan: V.plan(a.exposed_record), sealed_plan: V.plan(a.sealed_record),
  sealed_view: V.runHtml(a.sealed_record), exposed_view: V.runHtml(a.exposed_record),
  findings: V.findingsHtml(a.findings, a.model_findings.mark), progress: V.progressHtml(a.progress),
  inputs: V.inputsHtml(a.inputs), reviewed: V.reviewedHtml("doc_a", a.reviewed),
  runs: V.runsHtml([a.exposed_record, a.sealed_record])
};
process.stdout.write(JSON.stringify(out));
"""


def _node(answers):
    with tempfile.TemporaryDirectory(prefix="shimmer_desk_node_") as td:
        script, data = Path(td) / "views.js", Path(td) / "answers.json"
        script.write_text(NODE, encoding="utf-8")
        data.write_text(json.dumps(answers), encoding="utf-8")
        if str(ROOT / "tools") not in sys.path:
            sys.path.append(str(ROOT / "tools"))
        from cloud_run_common import no_window  # HIDDEN-A
        # The proof's own node call runs on the real Popen; the server's stays the fake.
        fake, subprocess.Popen = subprocess.Popen, _REAL_POPEN
        try:
            done = subprocess.run(["node", str(script), str(PAGE), str(data)], capture_output=True, text=True,
                                  encoding="utf-8", timeout=60, creationflags=no_window())
        finally:
            subprocess.Popen = fake
    _need(done.returncode == 0, "node: %s" % done.stderr[:400])
    out = json.loads(done.stdout)
    mark = answers["model_findings"].get("mark") or ""
    _need(out["sealed_plan"] == ["/runs/%s/progress" % SEALED_ID], "a sealed run plans %r" % out["sealed_plan"])
    _need("doc_a" not in out["sealed_view"] and "counts and timings only" in out["sealed_view"],
          "the sealed view names a document or lacks the counts-only note")
    _need("/runs/%s/reviewed/doc_a" % EXPOSED_ID in out["exposed_plan"], "the exposed plan lacks the reviewed document")
    _need(mark and out["findings"].count(mark) == 1 and "python-item" in out["findings"] and "model-item" in out["findings"],
          "the model mark is not on exactly the model finding")
    _need("&lt;script&gt;" in out["reviewed"] and "<script>" not in out["reviewed"], "document text is not escaped")
    _need("1 of 3" in out["progress"] and "documents/min" in out["progress"] and "not measurable" not in out["progress"]
          and "phase 5.5 of a nominal 9" in out["progress"], "progress view: %s" % out["progress"][:300])
    _need("rules.md" in out["inputs"] and CONTENT_MARKER not in out["inputs"], "inputs view wrong")
    return out


def run_all():
    """("PASS" or "FAIL", detail): part A always; B and C when fastapi and node are both present."""
    with tempfile.TemporaryDirectory(prefix="shimmer_gate_desk_") as td:
        tmp = Path(td)
        try:
            inputs, runs, _ = part_a(tmp)
            notes = ["A: listing names only, four progress values (1 of 3, 10.0 min, 0.1/min, 20.0 min), "
                     "reviewed document served by listing, neutralised escape served then refused"]
            try:
                import fastapi  # noqa: F401
                has_api = True
            except ImportError:
                has_api = False
            has_node = shutil.which("node") is not None
            if has_api and has_node:
                part_b(runs, inputs)
                notes.append("B: /console?view=desk ungated, three routes 401 without token, 200 with, sealed reviewed 403, no process")
                notes.append("C: page functions in node on those answers; sealed plans progress only; model mark on the "
                             "model finding alone; text escaped; every planned route 200")
            else:
                notes.append("B and C not run here: %s absent" % " and ".join(
                    n for n, ok in (("fastapi", has_api), ("node", has_node)) if not ok))
        except Refused as error:
            return "FAIL", str(error)
    return "PASS", "; ".join(notes)


if __name__ == "__main__":
    status, detail = run_all()
    print(status, detail)
    sys.exit(0 if status == "PASS" else 1)
