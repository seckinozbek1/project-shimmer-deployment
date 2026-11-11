#!/usr/bin/env python3
"""Steering checks of the cloud reference on the Claude subscription (D-S104 item 1).

Subscription, steering only: never a claim, never on the page, never in the report.

A quick check of the big model on the quick subset, on the subscription of the account the lead
runs on, to save money. It is not the cloud reference's measurement: every claim figure is the API
run (`cloud_reference.py run`) on the claim set, with the bare prompt, fixed settings and recorded
cost. These checks count toward the D-S91 usage questions; the seven-day usage read before the run
is recorded with it.

How it calls the model: headless Claude Code, one call per prompt.
  - `claude -p --model <alias> --system-prompt <STEERING_SYSTEM> --tools "" --output-format json
    --no-session-persistence --strict-mcp-config --setting-sources ""`, the prompt on stdin;
  - the alias is the registry's own (`cloud_reference.seat_model`), the one the API run uses;
  - the system prompt is the fixed minimal one below; the prompt's own two turns (B1's system turn,
    then its user turn) are the message;
  - no tools, no project settings, no session kept, run from an empty folder outside the repository;
  - every ANTHROPIC_ variable (key, token, base URL), the Bedrock, Vertex and Foundry switches and
    their own settings are taken out of the child's environment, so the call cannot bill the API or
    another provider; before the first call the CLI's own status command (`claude auth status
    --json`) must report a claude.ai sign-in on the first-party provider, and that reading is
    recorded (D-401 item 7): it runs on the subscription or not at all;
  - only an allowed set runs (`cloud_reference_steering_sets.json`, by the digests of the prompts
    file and the subset); the fresh set and anything on the refused list are refused by digest
    (D-401 item 6).

What it writes, under output/cloud_reference_steering/<name>/: the reply records
(`reply_records.write`, backend `claude_subscription`) and `replay_measurement.json`. Each of them
carries `claim_guard.STEERING_LABEL` and `"claim": false` in the file itself, so the scorer
(`cloud_reference.read`) and anything that reads figures for the page or a claim refuses it
(`claim_guard.refuse_claim`).

    py -3.12 -X utf8 benchmark/baselines/cloud_reference_steering.py run --prompts <J1-shaped prompts file>
        --subset <quick subset: a JSON list of item ids> --subset-sha256 <its digest> --out <name>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import claim_guard  # noqa: E402
import cloud_reference as cr  # noqa: E402

STEERING_SYSTEM = ("Answer the user's message exactly as it asks, in the format it asks for. "
                   "Use no tools and add nothing else.")
RUNS_ROOT = ROOT / "output" / "cloud_reference_steering"
CALL_TIMEOUT_SECONDS = 600
# Taken out of the child's environment (D-401 item 7): every variable with one of these prefixes,
# and these names. A subscription sign-in needs none of them.
STRIPPED_PREFIXES = ("ANTHROPIC_", "CLAUDE_CODE_USE_", "AWS_BEARER_TOKEN_BEDROCK")
STRIPPED_NAMES = ("CLAUDE_CODE_SKIP_BEDROCK_AUTH", "CLAUDE_CODE_SKIP_VERTEX_AUTH", "CLAUDE_CODE_SKIP_FOUNDRY_AUTH",
                  "CLOUD_ML_REGION", "VERTEX_REGION_CLAUDE_3_5_SONNET")
SETS_PATH = Path(__file__).resolve().with_name("cloud_reference_steering_sets.json")
FRESH_SOURCE = Path(__file__).resolve().with_name("system_test.py")
# The status reading a steering check needs, read from `claude auth status --json`.
SUBSCRIPTION = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty"}
STATUS_FIELDS = ("loggedIn", "authMethod", "apiProvider", "subscriptionType")


def message(prompt):
    """The one message the subscription call carries: the prompt's own turns, in order."""
    system, user = cr.turns(prompt)
    return (system + "\n\n" if system else "") + user


def argv(model):
    return ["claude", "-p", "--model", model, "--system-prompt", STEERING_SYSTEM, "--tools", "",
            "--output-format", "json", "--no-session-persistence", "--strict-mcp-config", "--setting-sources", ""]


def stripped(name):
    return name.startswith(STRIPPED_PREFIXES) or name in STRIPPED_NAMES


def child_environment():
    """The child's environment with every API, base-URL and other-provider variable removed."""
    return {k: v for k, v in os.environ.items() if not stripped(k)}


def auth_status(cwd):
    """The CLI's own status reading, in the child's environment: (fields kept, error or None).
    Only the fields STATUS_FIELDS names are kept; the account's name and address are not."""
    try:
        done = subprocess.run(["claude", "auth", "status", "--json"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=str(cwd), env=child_environment(),
                              timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, type(exc).__name__
    if done.returncode != 0:
        return None, "claude auth status exited %d" % done.returncode
    try:
        value = json.loads(done.stdout)
    except ValueError:
        return None, "claude auth status wrote no JSON"
    return {k: value.get(k) for k in STATUS_FIELDS}, None


def check_subscription(reading, error):
    cr.refuse(error is None and isinstance(reading, dict),
              "The CLI's sign-in could not be read (%s); a steering check runs on the subscription only" % error)
    wrong = sorted(k for k, v in SUBSCRIPTION.items() if reading.get(k) != v)
    cr.refuse(not wrong, "The CLI does not report a subscription sign-in (%s); a steering check runs on the "
                         "subscription only" % ", ".join("%s=%r" % (k, reading.get(k)) for k in wrong))
    return reading


def fresh_digests(source=FRESH_SOURCE):
    """The fresh set's digest as system_test.py pins it, read without importing it; none where the
    file is not in this tree (the refused list in the sets file still holds it)."""
    import ast
    try:
        tree = ast.parse(Path(source).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    out = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "FRESH_PROMPTS_SHA256" for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                out.add(node.value.value)
    return out


def allowed_set(prompts_sha256, subset_sha256, sets_path=SETS_PATH, fresh_source=FRESH_SOURCE):
    """The allowed list's entry for this prompts file and subset, refused for anything else, and
    for any digest on the refused list or the fresh set's (D-401 item 6)."""
    try:
        sets = json.loads(Path(sets_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise cr.Stop("The steering sets list cannot be read")
    refused = {r.get("sha256") for r in sets.get("refused") or []} | fresh_digests(fresh_source)
    cr.refuse(prompts_sha256 not in refused and subset_sha256 not in refused,
              "This set is on the refused list (the fresh set or sealed material): never a steering check")
    found = [a for a in sets.get("allowed") or []
             if a.get("prompts_sha256") == prompts_sha256 and a.get("subset_sha256") == subset_sha256]
    cr.refuse(len(found) == 1, "This prompts file and subset are not an allowed steering set (%s)" % Path(sets_path).name)
    return found[0]


def call_claude_code(model, text, cwd):
    """One headless call: (reply text, usage dict or None, error or None)."""
    try:
        done = subprocess.run(argv(model), input=text, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=str(cwd), env=child_environment(), timeout=CALL_TIMEOUT_SECONDS,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, None, type(exc).__name__
    if done.returncode != 0:
        return None, None, "claude exited %d" % done.returncode
    try:
        value = json.loads(done.stdout)
    except ValueError:
        return None, None, "the reply was not the JSON --output-format json writes"
    if value.get("is_error"):
        return None, None, "claude reported an error: %s" % str(value.get("subtype") or "")[:80]
    return value.get("result"), value.get("usage"), None


def seven_day_usage(root=ROOT):
    """The seven-day usage figure D-S91 watches, as recorded; None when it cannot be read."""
    try:
        status = json.loads((Path(root) / ".claude" / "loop_status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for key in ("seven_day_percent", "seven_day", "usage_seven_day"):
        if key in status:
            return status[key]
    return None


def run(prompts_path, subset_path, subset_sha256, out, *, caller=call_claude_code, status=auth_status, root=ROOT,
        runs_root=RUNS_ROOT, sets_path=SETS_PATH, fresh_source=FRESH_SOURCE, clock=time.perf_counter):
    """The steering check. Every output carries the steering label and `claim: false`."""
    import reply_records
    refuse = cr.refuse
    refuse(cr.sha(subset_path) == subset_sha256, "The quick subset is not the file whose digest was given")
    allowed = allowed_set(cr.sha(prompts_path), subset_sha256, sets_path, fresh_source)
    subset = json.loads(Path(subset_path).read_text(encoding="utf-8"))
    refuse(isinstance(subset, list) and subset and all(isinstance(i, str) for i in subset),
           "The quick subset is a JSON list of item ids")
    value = json.loads(Path(prompts_path).read_text(encoding="utf-8"))
    chosen = [p for p in value.get("prompts") or [] if p.get("item_id") in set(subset)]
    refuse(chosen, "No prompt of the prompts file is in the quick subset")
    cr.scan(chosen, None)
    out = Path(out).resolve()
    refuse(out.parent == Path(runs_root).resolve(), "The steering folder must be output/cloud_reference_steering/<name>")
    refuse(not out.exists() or not any(out.iterdir()), "This steering folder is not empty; a new check takes a new folder")
    model = cr.seat_model(root)
    context = cr.RunContext(out, "steering-" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:12])
    stamp = {"label": claim_guard.STEERING_LABEL, "kind": claim_guard.STEERING_KIND, "claim": False}
    rows = []
    usage_before = seven_day_usage(root)
    with tempfile.TemporaryDirectory(prefix="shimmer_steering_") as empty:
        sign_in = check_subscription(*status(empty))
        for p in chosen:
            text = message(p)
            started = clock()
            reply, usage, error = caller(model, text, empty)
            call_id = reply_records.write(context, agent="CLOUD_REFERENCE_STEERING", backend="claude_subscription",
                                          model_id=model, payload=text, payload_form="claude_code_print_stdin",
                                          reply=reply, ok=error is None, error=error or "",
                                          decoding=dict(stamp, route="subscription", system=STEERING_SYSTEM),
                                          phase="cloud_reference_steering", doc_id=p["document_id"])
            rows.append(dict(stamp, call_id=call_id, prompt_id=p["prompt_id"], document_id=p["document_id"],
                             form=p.get("form"), group=p.get("group"), rule_id=p.get("rule_id"),
                             failure=error, usage=usage, seconds=round(clock() - started, 3),
                             length_reached_allowance=None,
                             reply=None if reply is None else {"sha256": hashlib.sha256(reply.encode("utf-8")).hexdigest(),
                                                               "length_bytes": len(reply.encode("utf-8"))}))
    measurement = dict(stamp, schema=cr.MEASUREMENT_SCHEMA, prompts_sha256=cr.sha(prompts_path),
                       config_sha256=value.get("config_sha256"), subset_sha256=subset_sha256, rows=rows,
                       allowed_set=allowed.get("name"), sign_in=sign_in,
                       prompts=len(chosen), sent=len(rows), model={"configured": model, "route": "subscription"},
                       system_prompt=STEERING_SYSTEM, usage_watch={"seven_day_before": usage_before,
                                                                   "seven_day_after": seven_day_usage(root),
                                                                   "rule": "D-S91: counts toward the usage questions"},
                       cost="not billed to the API; drawn from the subscription's usage",
                       time_utc=datetime.now(timezone.utc).isoformat(), run_id=context.run_id)
    # The records carry the label too: each reply record's decoding names it (above), so a record
    # read on its own is refused as well.
    cr.write_json(out / cr.MEASUREMENT_FILE, measurement)
    return measurement


def main(argv_=None):
    parser = argparse.ArgumentParser(prog="cloud_reference_steering.py", allow_abbrev=False,
                                     description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", allow_abbrev=False)
    p.add_argument("--prompts", required=True)
    p.add_argument("--subset", required=True, help="the quick subset: a JSON list of item ids")
    p.add_argument("--subset-sha256", required=True)
    p.add_argument("--out", required=True, help="a new folder output/cloud_reference_steering/<name>")
    args = parser.parse_args(sys.argv[1:] if argv_ is None else argv_)
    try:
        m = run(args.prompts, args.subset, args.subset_sha256, args.out)
    except cr.Stop as exc:
        print("cloud_reference_steering stopped: %s" % exc, file=sys.stderr)
        return 3
    print("%s | %d of %d sent | %s" % (claim_guard.STEERING_LABEL, m["sent"], m["prompts"], m["cost"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
