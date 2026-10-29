"""Render the loop S7 console screenshots (docs/loop/ui/) from the committed fixture.

Every figure in a shot comes from the committed fixture under
scripts/fixtures/console/ or from what this tool writes deterministically into a
temporary copy of it:

- runs/<exposed id>/: the committed exposed run, plus three saved model replies
  written by the real writer (reply_records.write) under the fixed fixture clock
  (console_view_checks.REPLY_TIMES and OUTCOME_TIMES, inside the run's window);
- runs/<sealed id>/: the same run under another id, with the committed
  session/ files (run_record.json with exposure sealed added, FINAL_STATUS.json,
  execution_manifest.json) and a seal.json saying sealed;
- runs/<turkish id>/: the same run under another id whose status.json and
  audit/run_options.json say the output language is tr.

Nothing in the repository is written except the PNGs in --out. The server runs
under --server-python (an interpreter with fastapi and uvicorn) as a child of
this process, bound to 127.0.0.1, with a token generated here and passed to it
only as its SHA-256; it is stopped by its own process handle when the shots are
done. Playwright (Chromium) runs under the interpreter running this tool. No
pipeline run, no model, no network beyond the loopback server.

    py -3.12 tools/console_screenshots.py --server-python <python with fastapi and uvicorn>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEFAULT_OUT = ROOT / "docs" / "loop" / "ui"

EXPOSED_ID = "0c0501e00c0501e00c0501e00c0501e0"
SEALED_ID = "5ea1ed005ea1ed005ea1ed005ea1ed00"
TURKISH_ID = "7e570000000000000000000000000000"
SECTIONS = ("model-findings-section", "replies-section", "switches-section", "report-section",
            "multi-round-summary")
WIDTHS = (1280, 390)
PAGES = (
    ("run_detail_exposed", "#/runs/" + EXPOSED_ID, "en", WIDTHS),
    ("run_detail_exposed_tr", "#/runs/" + TURKISH_ID, "tr", (1280,)),
    ("run_detail_sealed", "#/runs/" + SEALED_ID, "en", WIDTHS),
    ("test_change_requests", "#/test-changes", "en", WIDTHS),
)


def _rename_run(source, target, old_id, new_id):
    """Copy a run folder under another id, the id replaced in every JSON file."""
    shutil.copytree(source, target)
    for path in sorted(target.rglob("*")):
        if path.suffix in (".json", ".jsonl"):
            text = path.read_text(encoding="utf-8")
            if old_id in text:
                path.write_text(text.replace(old_id, new_id), encoding="utf-8")


def build_runs(runs):
    """The three runs the shots show, in `runs`, from the committed fixture only."""
    sys.path.insert(0, str(SCRIPTS))
    import console_view_checks as fixture

    if fixture.RUN_ID != EXPOSED_ID:
        raise SystemExit("the committed fixture run id changed; update EXPOSED_ID")
    exposed = fixture._copy_fixture(runs)
    sealed = runs / SEALED_ID
    _rename_run(exposed, sealed, EXPOSED_ID, SEALED_ID)
    fixture._make_session(sealed, "sealed")
    turkish = runs / TURKISH_ID
    _rename_run(exposed, turkish, EXPOSED_ID, TURKISH_ID)
    status_path = turkish / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["output_language"] = "tr"
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    (turkish / "audit" / "run_options.json").write_text(json.dumps(
        {"schema_version": 1, "input_language": "auto", "output_language": "tr", "agent_briefs": "enabled"},
        indent=2) + "\n", encoding="utf-8")


def serve(runs, port):
    """Child mode: serve the console on `runs`. The token hash arrives in the
    environment (SHIMMER_TOKEN_HASH), set by the parent."""
    os.environ["SHIMMER_OUTPUT_DIR"] = str(runs)
    os.environ.setdefault("SHIMMER_LOG_LEVEL", "warning")
    sys.path.insert(0, str(SCRIPTS))
    import uvicorn
    import server
    uvicorn.run(server.app, host="127.0.0.1", port=port, log_level="warning")


def _free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _wait_ready(port, child, seconds=60):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if child.poll() is not None:
            raise SystemExit("the console server exited with code %s" % child.returncode)
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise SystemExit("the console server did not answer /health within %d s" % seconds)


def _shoot(port, token, out):
    from playwright.sync_api import sync_playwright

    base = "http://127.0.0.1:%d/console" % port
    written = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for name, fragment, language, widths in PAGES:
                for width in widths:
                    context = browser.new_context(viewport={"width": width, "height": 900})
                    context.add_init_script(
                        "sessionStorage.setItem('shimmer_console_token', %s);"
                        "sessionStorage.setItem('shimmer_output_language', %s);"
                        % (json.dumps(token), json.dumps(language)))
                    page = context.new_page()
                    page.goto(base + fragment)
                    page.wait_for_load_state("networkidle")
                    time.sleep(1.0)
                    page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
                    if name == "test_change_requests":
                        target = out / ("%s_%d.png" % (name, width))
                        page.screenshot(path=str(target), full_page=False)
                        written.append(target)
                    else:
                        for section in SECTIONS:
                            element = page.query_selector("#" + section)
                            if element is None:
                                raise SystemExit("section %s missing on %s at %d px" % (section, name, width))
                            element.scroll_into_view_if_needed()
                            short = section.replace("-section", "").replace("-summary", "")
                            target = out / ("%s_%s_%d.png" % (name, short, width))
                            element.screenshot(path=str(target))
                            written.append(target)
                    context.close()
        finally:
            browser.close()
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--server-python", help="an interpreter with fastapi and uvicorn that runs the server")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder for the PNGs (default docs/loop/ui)")
    parser.add_argument("--serve-runs", help=argparse.SUPPRESS)
    parser.add_argument("--serve-port", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.serve_runs:
        serve(Path(args.serve_runs), args.serve_port)
        return 0
    if not args.server_python:
        parser.error("--server-python is required")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="shimmer_console_shots_"))
    child = None
    try:
        runs = temporary / "runs"
        build_runs(runs)
        token = secrets.token_urlsafe(24)
        port = _free_port()
        env = dict(os.environ, SHIMMER_TOKEN_HASH=hashlib.sha256(token.encode()).hexdigest(),
                   KMP_DUPLICATE_LIB_OK="TRUE")
        child = subprocess.Popen([args.server_python, "-X", "utf8", str(Path(__file__).resolve()),
                                  "--serve-runs", str(runs), "--serve-port", str(port)],
                                 env=env, stdin=subprocess.DEVNULL, cwd=str(temporary))
        print("console server pid %d on 127.0.0.1:%d" % (child.pid, port), flush=True)
        _wait_ready(port, child)
        written = _shoot(port, token, out)
        print("%d screenshots written to %s" % (len(written), out), flush=True)
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=20)
        shutil.rmtree(temporary, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
