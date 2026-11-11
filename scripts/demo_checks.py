"""Gate check: the console's demo (D-S48) opens with nothing to type and asks nothing of the network.

Every proof EXECUTES the demo: tools/build_demo.py builds it from the committed fixture
(scripts/fixtures/demo, two INVENTED cases written by tools/demo_fixture.py, no text from benchmark/ or
external/), and Node runs the built index.html's own script against a small stand-in for the browser's
document, in which every way out (fetch, XMLHttpRequest, WebSocket, EventSource, sendBeacon, Image,
Worker, window.open, a script or link element with a source) and every place a token could be read
from (localStorage, sessionStorage, indexedDB, cookies, prompt) is a trap that records its use. Node
clicks every button the page shows, in both languages, on every case and every screen.

1. No request and no token: no trap is touched, the first screen says what the demo is (saved
   results of two demonstration cases, not benchmark evidence) with no step before it, the page
   carries the Content Security Policy that forbids every request, and names no address on the web.
2. Every model item shown carries finding_record.MODEL_FINDING_MARK in the language on screen (its
   row in that language), and the page shows as many model items as the saved records hold.
3. Every label has a row in the second language (tr), so no screen falls back to English in the second language.
4. Every file offered for download is in the folder, a byte copy of the run's own file.
5. Two builds from the same fixture are byte-identical, file by file.
6. Every case screen states how each run ended, from its own records: the fixture's synthetic review
   is written as failed, and its screens name the set-aside agent and Python's reason in both languages.
7. A batch entry whose seal record says sealed is refused; an exposed one is built.

Each is neutralise, fail, restore, pass: a fetch in the page, a token read, the mark dropped from the
model item, the policy removed, a clock in the build. Needs Node: without it the check says SKIP.
"""
import contextlib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import build_demo  # noqa: E402
import finding_record  # noqa: E402
import localization  # noqa: E402

FIXTURE = ROOT / "scripts" / "fixtures" / "demo"
CASES = {"synthetic": "demo_water_accord", "public": "demo_clean_rivers_resolution"}
CSP = "default-src 'none'"
TEST_MATERIAL = "This build uses invented test material, not the worked cases' saved results."

NODE_HARNESS = r"""
const fs = require("fs"), vm = require("vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const touched = [];
function trap(name) { return function () { touched.push(name); throw new Error("blocked: " + name); }; }
function TrapClass(name) { return function () { touched.push(name); throw new Error("blocked: " + name); }; }
function storage(name) {
  return new Proxy({}, { get(_, key) { touched.push(name + "." + String(key)); return () => null; },
                         set(_, key) { touched.push(name + "." + String(key)); return true; } });
}
class N {
  constructor(tag) { this.tagName = tag; this.children = []; this.attrs = {}; this.listeners = {}; this.className = ""; this._text = ""; }
  get textContent() { return this.tagName === "#text" ? this._text : this.children.map(c => c.textContent).join(""); }
  set textContent(v) { this.children = []; if (v !== "") { const t = new N("#text"); t._text = String(v); this.children.push(t); } }
  appendChild(c) { this.children.push(c); return c; }
  setAttribute(k, v) {
    if ((k === "src" || k === "href") && /^[a-z]+:\/\//i.test(String(v))) { touched.push("address:" + v); }
    this.attrs[k] = String(v);
  }
  getAttribute(k) { return this.attrs[k]; }
  addEventListener(type, f) { (this.listeners[type] = this.listeners[type] || []).push(f); }
  click() { (this.listeners.click || []).forEach(f => f({ preventDefault() {} })); }
  walk(out) { out.push(this); this.children.forEach(c => c.walk(out)); return out; }
}
const ids = {};
["title", "mode", "languages", "cases", "sections", "main"].forEach(id => { ids[id] = new N("div"); });
const docEl = new N("html");
const documentStub = {
  createElement(tag) {
    if (tag === "script" || tag === "iframe" || tag === "link" || tag === "img") { touched.push("element:" + tag); }
    return new N(tag);
  },
  createTextNode(t) { const n = new N("#text"); n._text = String(t); return n; },
  getElementById(id) { return ids[id] || null; },
  documentElement: docEl, title: "",
};
Object.defineProperty(documentStub, "cookie", { get() { touched.push("document.cookie"); return ""; },
                                                 set() { touched.push("document.cookie"); } });
const context = {
  document: documentStub, console,
  fetch: trap("fetch"), XMLHttpRequest: TrapClass("XMLHttpRequest"), WebSocket: TrapClass("WebSocket"),
  EventSource: TrapClass("EventSource"), Image: TrapClass("Image"), Worker: TrapClass("Worker"),
  importScripts: trap("importScripts"), prompt: trap("prompt"), alert: trap("alert"), confirm: trap("confirm"),
  localStorage: storage("localStorage"), sessionStorage: storage("sessionStorage"), indexedDB: storage("indexedDB"),
  navigator: { sendBeacon: trap("navigator.sendBeacon") }, open: trap("window.open"),
};
context.window = context; context.self = context; context.globalThis = context;
vm.createContext(context);
const out = { touched, screens: [], errors: [] };
try {
  scripts.forEach(s => vm.runInContext(s, context));
} catch (e) { out.errors.push("load: " + e.message); }
function nav(prefix) {
  const all = []; Object.values(ids).forEach(n => n.walk(all));
  return all.filter(n => n.attrs["data-nav"] && n.attrs["data-nav"].startsWith(prefix));
}
function press(name) {
  const hit = nav(name).filter(n => n.attrs["data-nav"] === name)[0];
  if (!hit) { out.errors.push("no button " + name); return false; }
  try { hit.click(); } catch (e) { out.errors.push(name + ": " + e.message); return false; }
  return true;
}
function screen(lang, view, section) {
  const nodes = ids.main.walk([]);
  const models = nodes.filter(n => /(^| )model-item( |$)/.test(n.className)).map(n => n.textContent);
  const pythons = nodes.filter(n => /(^| )python-item( |$)/.test(n.className)).length;
  out.screens.push({ lang, view, section, text: ids.main.textContent, header: ids.title.textContent + " | " + ids.mode.textContent,
                     models, pythons, links: nodes.filter(n => n.tagName === "a").map(n => n.attrs.href) });
}
out.first = { text: ids.main.textContent, header: ids.title.textContent + " | " + ids.mode.textContent };
for (const lang of ["en", "tr"]) {
  if (!press("lang-" + lang)) continue;
  if (press("view-start")) screen(lang, "start", null);
  const views = nav("view-").map(n => n.attrs["data-nav"]).filter(v => v !== "view-start");
  for (const view of views) {
    if (!press(view)) continue;
    const sections = nav("section-").map(n => n.attrs["data-nav"]);
    for (const section of sections) { if (press(section)) screen(lang, view.slice(5), section.slice(8)); }
  }
}
out.misses = context.__demo_misses || null;
process.stdout.write(JSON.stringify(out));
"""


def node():
    return shutil.which("node")


def build_fixture_demo(out):
    f = FIXTURE
    cases = {kind: {"rounds": f / "runs" / (name + "_rounds"), "review": f / "runs" / (name + "_review"),
                    "documents": f / "documents" / name} for kind, name in CASES.items()}
    return build_demo.build(out, cases, test_material=True)


def _run_page(index):
    with tempfile.TemporaryDirectory(prefix="shimmer_demo_node_") as td:
        harness = Path(td) / "harness.js"
        harness.write_text(NODE_HARNESS, encoding="utf-8")
        done = subprocess.run([node(), str(harness), str(index)], capture_output=True, text=True, encoding="utf-8",
                              timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if done.returncode != 0:
        raise RuntimeError("node failed: %s" % done.stderr[-400:])
    return json.loads(done.stdout)


def _expected_model_items(data):
    """Per case kind: every item a model wrote in the saved records the demo was given."""
    out = {}
    for case in data["cases"]:
        n = sum(1 for m in case.get("movements") or [] if m["written_by"] == "model")
        n += len((case.get("support") or {}).get("suggestions") or [])
        for doc in case.get("review") or []:
            n += len(doc["model_findings"]) + sum(1 for a in doc["amendments"] if a["written_by"] != "python")
        out[case["key"]] = n
    return out


def _tree(folder):
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def observe():
    """One build of the fixture, run in Node: what the page touched and showed."""
    with tempfile.TemporaryDirectory(prefix="shimmer_demo_") as td:
        out = Path(td) / "demo"
        data = build_fixture_demo(out)
        page = (out / "index.html").read_text(encoding="utf-8")
        run = _run_page(out / "index.html")
        catalog = localization.catalog()
        marks = {"en": finding_record.MODEL_FINDING_MARK, "tr": catalog.get(finding_record.MODEL_FINDING_MARK)}
        disclaimer = {"en": build_demo.STRINGS[2], "tr": catalog.get(build_demo.STRINGS[2])}
        shown = {}
        unmarked = []
        for s in run["screens"]:
            if s["view"] == "start":
                continue
            key = (s["lang"], s["view"])
            shown[key] = shown.get(key, 0) + len(s["models"])
            unmarked += ["%s/%s/%s" % (s["lang"], s["view"], s["section"]) for t in s["models"] if marks[s["lang"]] not in t]
        expected = _expected_model_items(data)
        links = sorted({l for s in run["screens"] for l in s["links"]})
        sources = {}
        for case in data["cases"]:
            name = CASES[case["key"]]
            for d in case["downloads"]:
                src = FIXTURE / "runs" / ("%s_%s" % (name, d["source"])) / "run" / "deliverables" / d["document_id"] / d["file"]
                sources[d["href"]] = src.read_bytes() == (out / d["href"]).read_bytes() if (out / d["href"]).is_file() else False
        return {
            "touched": sorted(set(run["touched"])), "errors": run["errors"],
            "first_screen_says_what_it_is": disclaimer["en"] in run["first"]["text"]
            and "Demo: no installation, saved examples" in run["first"]["header"],
            "start_in_turkish": any(s["view"] == "start" and s["lang"] == "tr" and disclaimer["tr"] in s["text"]
                                    for s in run["screens"]),
            "policy": CSP in page and "Content-Security-Policy" in page,
            "web_addresses": sorted(set(re.findall(r"""(?:src|href|action)\s*=\s*["']?((?:[a-z]+:)?//[^"'\s>]*)""",
                                                   page, flags=re.I))),
            "screens": len(run["screens"]),
            "status_said": _status_said(run["screens"], catalog),
            "test_material_said": all(catalog.get(TEST_MATERIAL, TEST_MATERIAL) in s["text"] if s["lang"] == "tr"
                                      else TEST_MATERIAL in s["text"] for s in run["screens"]),
            "model_items_shown": {"%s/%s" % k: v for k, v in sorted(shown.items())},
            "model_items_expected": expected, "unmarked": unmarked,
            "misses": run["misses"], "turkish_rows": all(s in catalog for s in build_demo.STRINGS),
            "downloads": {"offered": links, "byte_copies": sources},
        }


def observe_identical():
    with tempfile.TemporaryDirectory(prefix="shimmer_demo_twice_") as td:
        build_fixture_demo(Path(td) / "a")
        build_fixture_demo(Path(td) / "b")
        a, b = _tree(Path(td) / "a"), _tree(Path(td) / "b")
        return {"files": len(a), "differ": sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))}


STATUS = {"failed": "This run finished, but did not pass its integrity check. Part of its work is incomplete: "
                    "what is shown here is everything it produced, and nothing more.",
          "passed": "This run finished and passed its integrity check."}


def _status_said(screens, catalog):
    """On every case screen, in each language: the synthetic case states its ordinary review's failure
    with the set-aside agent and Python's own reason, and every case states its passed runs."""
    out = {"failure_on_every_synthetic_screen": True, "pass_on_every_public_screen": True}
    for s in screens:
        if s["view"] == "start":
            continue
        tr = s["lang"] == "tr"
        failed, passed = ((catalog[STATUS["failed"]], catalog[STATUS["passed"]]) if tr
                          else (STATUS["failed"], STATUS["passed"]))
        if s["view"] == "synthetic" and not (failed in s["text"] and "VERIFIER" in s["text"]
                                             and "not a canonical envelope" in s["text"] and "13263" in s["text"]):
            out["failure_on_every_synthetic_screen"] = False
        if s["view"] == "public" and passed not in s["text"]:
            out["pass_on_every_public_screen"] = False
    return out


def judge(o):
    problems = []
    if not all(o["status_said"].values()):
        problems.append("how a run ended is not stated on every case screen: %s" % o["status_said"])
    if o["touched"]:
        problems.append("the page touched: %s" % o["touched"])
    if o["errors"]:
        problems.append("the page failed: %s" % o["errors"][:3])
    if not o["first_screen_says_what_it_is"] or not o["start_in_turkish"]:
        problems.append("the first screen does not say what the demo is")
    if not o["test_material_said"]:
        problems.append("a screen of the fixture build does not say it is invented test material")
    if not o["policy"]:
        problems.append("the page carries no policy forbidding requests")
    if o["web_addresses"]:
        problems.append("the page names a web address: %s" % o["web_addresses"])
    if o["unmarked"]:
        problems.append("model items without the mark on %s" % o["unmarked"][:3])
    for kind, n in o["model_items_expected"].items():
        for lang in ("en", "tr"):
            if o["model_items_shown"].get("%s/%s" % (lang, kind)) != n:
                problems.append("%s %s: %s model items shown, %d saved" % (lang, kind, o["model_items_shown"].get(
                    "%s/%s" % (lang, kind)), n))
    if not sum(o["model_items_expected"].values()):
        problems.append("the fixture holds no model item, so the mark is not proven")
    if not o["turkish_rows"] or o["misses"]:
        problems.append("labels with no row in the second language (tr): %s" % o["misses"])
    if not o["downloads"]["offered"] or set(o["downloads"]["offered"]) != set(o["downloads"]["byte_copies"]) \
            or not all(o["downloads"]["byte_copies"].values()):
        problems.append("a download is missing or not the run's own bytes")
    return problems


def check_page():
    o = observe()
    problems = judge(o)
    if problems:
        return "FAIL", "; ".join(problems)
    return "PASS", ("%d screens clicked in two languages, nothing touched; %s model items, each marked"
                    % (o["screens"], sum(o["model_items_expected"].values())))


def check_identical():
    o = observe_identical()
    if o["differ"] or not o["files"]:
        return "FAIL", "two builds differ in %s" % o["differ"][:5]
    return "PASS", "two builds byte-identical (%d files)" % o["files"]


def check_refusals():
    """The builder never reads benchmark/ (beyond the exposed dev cases) or external/, and refuses a
    sealed run: each refused before anything is written."""
    refused = []
    with tempfile.TemporaryDirectory(prefix="shimmer_demo_refuse_") as td:
        sealed = Path(td) / "sealed_run"
        (sealed / "deliverables").mkdir(parents=True)
        (sealed / "status.json").write_text(json.dumps({"exposure": "sealed"}), encoding="utf-8")
        # A batch entry sealed for the test: its seal record two folders above the run.
        entry = Path(td) / "sealed_entry"
        shutil.copytree(FIXTURE / "runs" / (CASES["public"] + "_review"), entry / "evidence")
        (entry / "seal.json").write_text(json.dumps({"exposure": "sealed"}), encoding="utf-8")
        # The same entry exposed: built.
        exposed = Path(td) / "exposed_entry"
        shutil.copytree(FIXTURE / "runs" / (CASES["public"] + "_review"), exposed / "evidence")
        (exposed / "seal.json").write_text(json.dumps({"exposure": "exposed"}), encoding="utf-8")
        # Folders that do not exist: refused by location before any read, and with the guard
        # neutralised nothing is read either (the build then fails on the missing folder).
        for name, case in (("benchmark", {"documents": ROOT / "benchmark" / "no_such_folder_demo_check"}),
                           ("external", {"documents": ROOT / "external" / "no_such_folder_demo_check"}),
                           ("sealed", {"review": sealed}), ("sealed_entry", {"review": entry})):
            out = Path(td) / ("out_" + name)
            try:
                build_demo.build(out, {"synthetic": case})
            except build_demo.Refused:
                if not out.exists():
                    refused.append(name)
            except OSError:
                pass   # not refused: the build went on to read the folder
        try:
            build_demo.build(Path(td) / "out_exposed", {"public": {"review": exposed}})
            exposed_built = (Path(td) / "out_exposed" / "index.html").is_file()
        except build_demo.Refused:
            exposed_built = False
    want = ["benchmark", "external", "sealed", "sealed_entry"]
    if refused != want or not exposed_built:
        return "FAIL", "the builder did not refuse %s, or refused an exposed entry (%s)" % (
            sorted(set(want) - set(refused)), not exposed_built)
    try:   # the worked cases' own source documents stay readable
        build_demo._refuse_location(ROOT / "benchmark" / "dev_cases" / "any_case" / "workload" / "context")
    except build_demo.Refused:
        return "FAIL", "benchmark/dev_cases/ refused"
    return "PASS", ("every other path under benchmark/, external/, a sealed run and a sealed batch entry refused; "
                    "an exposed entry built; benchmark/dev_cases/ read")


def _pack(entry, archive, extra=()):
    """A fixture entry (run/ and result.json) as a collected_evidence.tar.gz holds it (evidence/run/...,
    evidence/result.json), plus `extra` members (name, bytes) planted beside it."""
    import io
    import tarfile
    with tarfile.open(archive, "w:gz") as tar:
        for p in sorted(Path(entry).rglob("*")):
            if p.is_file():
                tar.add(p, arcname="evidence/" + p.relative_to(entry).as_posix())
        for name, data in extra:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


PLANTED = (("evidence/run/audit/model_replies/call-0001.json", b'{"raw_text": "planted"}'),
           ("evidence/../escaped.txt", b"planted"))


def observe_archive():
    """The fixture's four run folders given as archives build the same demo as the folders; the
    members unpacked from an archive with a planted reply record and a parent path."""
    import tarfile
    with tempfile.TemporaryDirectory(prefix="shimmer_demo_archive_") as td:
        td = Path(td)
        cases = {}
        for kind, name in CASES.items():
            # No --documents: the case's documents travel in the archive, as a batch entry's
            # workload does, and must be found there.
            documents = tuple(("evidence/workload/context/" + p.name, p.read_bytes())
                              for p in sorted((FIXTURE / "documents" / name).iterdir()))
            entry = {}
            for arm in ("rounds", "review"):
                archive = td / ("%s_%s.tar.gz" % (kind, arm))
                _pack(FIXTURE / "runs" / ("%s_%s" % (name, arm)), archive, PLANTED + documents)
                entry[arm] = archive
            cases[kind] = entry
        try:
            build_demo.build(td / "from_archives", cases, test_material=True)
            built = _tree(td / "from_archives")
        except Exception as exc:  # recorded by type: a build that cannot read the archive
            built = {"error": type(exc).__name__}
        build_fixture_demo(td / "from_folders")
        with tarfile.open(cases["synthetic"]["rounds"], "r:gz") as tar:
            kept = sorted(m.name for m in build_demo._safe_members(tar))
        return {"same_as_folders": built == _tree(td / "from_folders"),
                "planted_kept": [n for n, _ in PLANTED if n in kept],
                "escaped": (td / "escaped.txt").exists()}


def check_archive():
    o = observe_archive()
    if not o["same_as_folders"] or o["planted_kept"] or o["escaped"]:
        return "FAIL", "archive input: %s" % o
    return "PASS", ("collected_evidence.tar.gz builds the same demo as the run folders, its documents read from the "
                    "archive's own evidence; no reply record or parent path unpacked")


CONSOLE = {"path": ROOT / "scripts" / "ui" / "console.html"}
CONSOLE_LINES = {
    "en": "Demo: no installation, saved examples. Open open_demo.bat in the demo folder",
    "tr": "Demo: kurulum yok, kayıtlı örnekler. Demo klasöründeki open_demo.bat dosyasını açın",
}


def check_console_line():
    """console.html names the demo in both languages, says how to open it, and links to it relative
    to the file, at the folder tools/build_demo.py writes by default; served as /console serves it."""
    import localization
    path = CONSOLE["path"]
    served = localization.console_document(path)
    footer = re.search(r'<footer class="demo-line" id="demo-line">(.*?)</footer>', served, re.S)
    if not footer:
        return "FAIL", "console.html carries no demo line"
    body = footer.group(1)
    missing = [lang for lang, line in CONSOLE_LINES.items()
               if not re.search(r'<p lang="%s">%s \(<a href="([^"]+)">' % (lang, re.escape(line)), body)]
    hrefs = set(re.findall(r'href="([^"]+)"', body))
    target = {(ROOT / "scripts" / "ui" / h).resolve() for h in hrefs}
    if missing or target != {(build_demo.DEFAULT_OUT / "index.html").resolve()}:
        return "FAIL", "demo line missing in %s, or its link leads elsewhere: %s" % (missing, sorted(hrefs))
    return "PASS", "console.html names the demo and how to open it in both languages, linking to demo/index.html"


_ASSET = re.compile(r"""<(?:script|link|img)\b[^>]*?\b(?:src|href)\s*=\s*["']([^"'#?]+)["']""", re.I)


def page_assets(html):
    """Every local file the page loads (a script, stylesheet or image named relative to it), read
    from the page itself, so a file the console starts to load is copied with it. A web address or
    an absolute path is not a local asset; the demo link (a plain `<a>`) is not loaded."""
    out = []
    for name in _ASSET.findall(html):
        if "://" in name or name.startswith(("/", "//", "data:")):
            continue
        if name not in out:
            out.append(name)
    return out


@contextlib.contextmanager
def console_with(old, new):
    source = CONSOLE["path"].read_text(encoding="utf-8")
    if old is not None and source.count(old) != 1:
        raise RuntimeError("the console line to neutralise moved")
    with tempfile.TemporaryDirectory(prefix="shimmer_demo_console_") as td:
        for name in page_assets(source):
            target = Path(td) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CONSOLE["path"].parent / name, target)
        copy = Path(td) / "console.html"
        copy.write_text(source if old is None else source.replace(old, new), encoding="utf-8")
        saved, CONSOLE["path"] = CONSOLE["path"], copy
        try:
            yield
        finally:
            CONSOLE["path"] = saved


def observe_console_copy():
    """The console copied as the line proofs copy it: what the page loads, what was copied, and
    whether the served form (localization.console_document) can be built from the copy."""
    import localization
    source = CONSOLE["path"].read_text(encoding="utf-8")
    loaded = page_assets(source)
    with console_with(None, None):
        copied = sorted(p.relative_to(CONSOLE["path"].parent).as_posix()
                        for p in CONSOLE["path"].parent.rglob("*") if p.is_file() and p.name != "console.html")
        try:
            localization.console_document(CONSOLE["path"])
            served = True
        except OSError as exc:
            served = type(exc).__name__
    return {"loaded": loaded, "copied": copied, "served": served}


def check_console_copy():
    o = observe_console_copy()
    if not o["loaded"] or sorted(o["loaded"]) != o["copied"] or o["served"] is not True:
        return "FAIL", "the console copy lacks what the page loads: %s" % o
    return "PASS", ("the console copy holds every file the page loads, read from the page (%s), and the "
                    "served console builds from it" % ", ".join(o["loaded"]))


@contextlib.contextmanager
def template_with(old, new, what):
    source = build_demo.TEMPLATE.read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError(what + ": the text to neutralise moved")
    with tempfile.TemporaryDirectory(prefix="shimmer_demo_neutral_") as td:
        path = Path(td) / "demo.html"
        path.write_text(source.replace(old, new), encoding="utf-8")
        with patch.object(build_demo, "TEMPLATE", path):
            yield


NEUTRALISATIONS = [
    ("a fetch in the page", check_page,
     lambda: template_with("  render();\n})();", "  render();\n  try { fetch('results.json'); } catch (e) {}\n})();", "fetch")),
    ("a token read from storage", check_page,
     lambda: template_with("  render();\n})();", "  var token = localStorage.getItem('shimmer_token');\n  render();\n})();", "token")),
    ("the mark dropped from a model item", check_page,
     lambda: template_with('[el("p", "mark", [T(DEMO_TEXT.marks.model)])].concat(children)', "children", "mark")),
    ("the policy removed", check_page,
     lambda: template_with("default-src 'none'; ", "", "policy")),
    ("benchmark/ and external/ readable", check_refusals,
     lambda: patch.object(build_demo, "REFUSED_ROOTS", ())),
    ("a sealed run accepted", check_refusals,
     lambda: patch.object(build_demo, "_refuse_sealed", lambda run: None)),
    ("an archive read as a folder", check_archive,
     lambda: patch.object(build_demo, "_run_folder", lambda path, name, stack: (Path(path), Path(path).parent))),
    ("documents not read from the evidence", check_archive,
     lambda: patch.object(build_demo, "_documents_in_evidence", lambda roots, ids: None)),
    ("reply records unpacked", check_archive,
     lambda: patch.object(build_demo, "_safe_members", lambda archive: [
         m for m in archive.getmembers() if m.isfile() or m.isdir()])),
    ("the tr demo line removed from console.html", check_console_line,
     lambda: console_with(CONSOLE_LINES["tr"], "Demo")),
    ("the console link pointed elsewhere", check_console_line,
     lambda: console_with('<p lang="en">' + CONSOLE_LINES["en"] + ' (<a href="../../demo/index.html">',
                          '<p lang="en">' + CONSOLE_LINES["en"] + ' (<a href="../demo/index.html">')),
    ("the failure left unsaid", check_page,
     lambda: template_with("    main.appendChild(statusBlock(c, false));\n", "", "status")),
    ("a batch entry's seal record ignored", check_refusals,
     lambda: patch.object(build_demo, "SEAL_RECORDS", ())),
    ("the console copy from a fixed list missing a file", check_console_copy,
     lambda: patch.object(sys.modules[__name__], "page_assets",
                          lambda html: ["localization_catalog.js", "localization.js"])),
    ("a clock in the build", check_identical,
     lambda: patch.object(build_demo, "_inline", lambda v, _real=build_demo._inline: _real(v) + "/*%d*/" % __import__("time").perf_counter_ns())),
]


def check():
    if node() is None:
        return "SKIP", "node is not on PATH: the demo proof runs the built page's own script in Node"
    results = [check_page(), check_identical(), check_refusals(), check_archive(), check_console_copy(),
               check_console_line()]
    for verdict, detail in results:
        if verdict != "PASS":
            return "FAIL", "original: " + detail
    proofs = []
    for what, run, neutralise in NEUTRALISATIONS:
        with neutralise():
            verdict, detail = run()
        if verdict != "FAIL":
            return "FAIL", "neutralised (%s) and the check still passes" % what
        again, _ = run()
        if again != "PASS":
            return "FAIL", "restored (%s) and the check does not pass" % what
        proofs.append(what)
    return "PASS", "%s; neutralised (%s): each FAIL, restored: PASS" % ("; ".join(r[1] for r in results),
                                                                          "; ".join(proofs))


if __name__ == "__main__":
    verdict, detail = check()
    print(verdict, detail)
    sys.exit(0 if verdict in ("PASS", "SKIP") else 1)
