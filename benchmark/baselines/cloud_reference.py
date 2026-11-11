#!/usr/bin/env python3
"""The cloud reference: a paid Anthropic model on development items already read (D-S70 item 5,
D-S35, D-S33 item 1; plan docs/loop/stages/CLOUD_REFERENCE_PLAN.md, decisions D-326).

Reference: a paid cloud model on development items already read. Not Shimmer's performance.

It sends J1's own prompts (`external/s05/J1/j1_prompts.json`, the digest J1's bar names), byte for
byte, to the registry's Anthropic model:
  - the `b1` form, B1's two turns, as the system prompt and the one user message;
  - the `agent` form, the pipeline's own judging calls from saved B3 runs, as one user message.
It sends them on HALF A ONLY. Half A is taken from C's own split (`choice_read.split`) over C's
universe, read by C's own `choice_read.universe`: the pinned `g1_bar_items.json`, each item's
document from the answer keys' tables (through the scorer, the one reader of a key), documents
whose items are all left out dropped. The prompts must be exactly that universe. Half B is reserved for C's and T's one read (docs/loop/stages/C_BAR.md).

It writes a pass folder in the shape J1's pass has (`replay_measurement.json` and reply records
through `reply_records.write`), so J1's reader functions read it. No pipeline runs, no instance is
used, and the key never leaves this machine but in the request to the provider.

    plan  counts, characters and the worst case at the recorded prices; no provider call
    run   the paid run (below)
    read  half A rows of a pass folder (this one or J1's local one) through J1's reader functions
          and the scorer, labelled a reference

The run, in order, before any request that can be billed:
  - the prompts file must be the one J1's bar names, and its items C's universe;
  - every prompt is scanned for key-shaped strings and for the key itself;
  - the model is the registry's, resolved live (`model_registry.resolve_model_id`). Only a model
    that is GONE from the provider's list, or AMBIGUOUS between snapshots, or a list that cannot be
    read, stops it. A model still listed but announced as deprecated is NOT caught by the list: the
    Models API carries no deprecation field. The run also reads the model's own record
    (`models.retrieve`) and stops if it carries any field naming a deprecation, and it requires
    `--deprecation-checked "<url>, <YYYY-MM-DD>, not deprecated"`, the operator's reading of the
    provider's deprecations page, which it records. The SDK's ModelInfo has no deprecation field, so
    the record scan cannot fire on it today. Nothing here can prove the model is not deprecated;
  - the prices given must equal the recorded table (`cloud_reference_prices.json`, its digest
    recorded) for the resolved id; and the cap must fit what is left of the loop's TOTAL budget
    (D-S102 item 12 lifted D-S35's 15 USD cap; D-S95 item 4): the guard's cap ceiling of the latest
    budget line less the instances' spend and running caps, less the spend every earlier run appended
    to the one shared store (`docs/loop/private/` of the main checkout, found from git's common
    directory), which refuses when it is absent or cannot be read;
  - a group starts only when its whole worst case (counted input tokens and the full output
    allowance, at the price) fits under the cap; each call is checked again on its own;
  - the client is built with `max_retries=0`, so a billed request is never sent twice; each call's
    worst case is counted before the request and replaced by the reported cost only on a completed
    reply whose usage was read; a usage reporting cache writes stops the run.
The spend line and the measurement are written on any exit (try/finally), so the spend is never lost.

D-401 (the cloud-check's twelve gaps on fad0f075):
  - the environment's key, token and base URL are removed before ANY client, the live model list's
    included (`provider_models` builds its client as `make_client` does);
  - a resume is refused unless the earlier folder is a paid run of this kind (no steering stamp on
    its measurement or any record), on the same prompts and config digests, the same model, and
    every reused reply ran the settings this run would send;
  - Seckin's yes is read from FOR_SECKIN.md beside the store: exactly one heading naming
    `--seckin-approved`, and under it the line "Seckin: evet (<time>)", which the lead writes only
    after his answer. It is LEAD-ATTESTED: the runner checks the line is there, not who wrote it;
  - the store (`tools/loop/cloud_reference_spend.py`, the reader the guard imports too): an intent
    line under the store's lock before the first request, its limit counted as running until the
    close line; a handed-back role C file not appended refuses the run; the lead's form refuses in
    a role C session (`SHIMMER_ROLE=C`);
  - the credit carries across resumed chunks: each chunk's limit is the lower of the cap and the
    credit less what the chain spent before it (`chain_spent`).

D-S106 (Seckin's own key, his yes, his credit):
  - item 1: the key is only the one the repository's rule resolves ($SHIMMER_CONFIG_PATH, then
    ../api_keys/config.py, then the .env_path pointer; `resolve_key`), recorded by its source name,
    never its value. ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN and ANTHROPIC_BASE_URL are removed from
    the environment before the client is built, which is given the key and the provider's own URL;
  - item 2: a paid run refuses without `--seckin-approved "<FOR_SECKIN entry heading time>"`, passed
    only after his evet, and records it in the measurement and the spend line;
  - item 3: `--credit-usd` (the API credit left): a group starts only when its worst case fits
    under the lower of the cap and the credit. Every reply is recorded as it arrives; a provider
    refusal (a 400, which a credit balance run out is) stops the run cleanly, never retried;
    `--max-calls` ends a chunk cleanly; `--resume-from <earlier run folder>` copies in every reply
    that run recorded, keyed by the prompt's digest, and sends none of those prompts again.

The cap, the total and the prices are arguments or recorded files, never code constants. The
repository's `AgentWrapper.call_claude` sends one user turn and no system turn, so B1's two turns
could not pass through it unchanged; the call here is the SDK's own `messages.create`, with the
key from `agent_wrapper.load_api_keys`, errors through `agent_wrapper._scrub_error` and a replace
of the key itself, and every reply saved by `reply_records.write`, as call_claude does.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "tools" / "loop"),
              str(ROOT / "benchmark" / "baselines"), str(ROOT / "benchmark" / "adapters")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import cloud_reference_spend as spend  # noqa: E402  (the one reader of the spend store, D-401 items 4 and 5)

LABEL = "Reference: a paid cloud model on development items already read. Not Shimmer's performance."
SCHEMA = "cloud-reference-v1"
MEASUREMENT_SCHEMA = "doc-judge-measurement-v1"   # the shape J1's pass folder has
MEASUREMENT_FILE = "replay_measurement.json"
GROUP_ORDER = ("judge_direct", "judge_reason")
SEAT_AGENT = "LEGAL_ANALYST"   # the registry agent whose Anthropic model takes the judge's seat (D-326)
ACCEPTED_MODEL_STATUS = ("exact", "bound")
# Errors that do not pass by going on (a credit balance run out is a 400): the run stops at the first.
STOP_ERRORS = ("BadRequestError", "AuthenticationError", "PermissionDeniedError", "NotFoundError")
PRICES_PATH = Path(__file__).resolve().with_name("cloud_reference_prices.json")
RUNS_ROOT = ROOT / "output" / "cloud_reference"
SPEND_STORE_NAME = spend.STORE_NAME   # in the main checkout's docs/loop/private/ (gitignored)
FOR_SECKIN_NAME = "FOR_SECKIN.md"   # beside the store
# The marker of a role C session (D-401 item 11): the --budget-left-usd form runs only under it, the
# lead's form never does.
ROLE_ENVIRONMENT = "SHIMMER_ROLE"
ROLE_C = "C"
DEPRECATION_FORM = re.compile(r"https?://\S+, \d{4}-\d{2}-\d{2}, not deprecated")


class Stop(Exception):
    """A one-line stop, before or during the run."""


def refuse(condition, message):
    if not condition:
        raise Stop(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_default(value):
    """What json cannot write is written as its text (a datetime from the SDK above all), so a
    record the provider returns can never stop the measurement being written."""
    return str(value)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False, default=json_default) + "\n",
                    encoding="utf-8")


# ---------------------------------------------------------------------------
# which prompts: J1's file, its bar, C's universe, half A


def load(prompts_path, bar_path):
    """J1's prompts and bar, refused unless the bar names this file's digest."""
    value = json.loads(Path(prompts_path).read_text(encoding="utf-8"))
    bar = json.loads(Path(bar_path).read_text(encoding="utf-8"))
    refuse(bar.get("prompts_sha256") == sha(prompts_path),
           "The prompts file is not the one J1's bar names: only items already read are sent")
    refuse(isinstance(value.get("prompts"), list) and value["prompts"], "The prompts file holds no prompts")
    return value, bar


def universe(value, items_path, keys):
    """C's documents {id: {benchmark}} and items, by C's own reading (`choice_read.universe`: the
    pinned items file, each item's document from the key tables through the scorer, documents whose
    items are all left out dropped). Refused unless, for each benchmark, the prompts' items (the
    left-out ones aside) are exactly C's, and each prompt names the document its item's key names."""
    import choice_read
    try:
        out, left_out, _ = choice_read.universe(list(keys), items_path)
    except (ValueError, SystemExit) as exc:
        raise Stop("C's universe could not be read: %s" % exc)
    item_document = {i["item_id"]: (b, d) for b, docs in out.items() for d, listed in docs.items() for i in listed}
    for benchmark in sorted({p["benchmark"] for p in value["prompts"]}):
        have = {p["item_id"] for p in value["prompts"] if p["benchmark"] == benchmark and p["item_id"] not in left_out}
        wanted = {i for i, (b, d) in item_document.items() if b == benchmark}
        refuse(wanted and have == wanted, "The prompts' %s items are not C's universe (pinned items and keys)" % benchmark)
    for p in value["prompts"]:
        if p["item_id"] in left_out:
            continue
        refuse(item_document[p["item_id"]] == (p["benchmark"], p["document_id"]),
               "Prompt %s names document %s; its item's key names another" % (p["prompt_id"], p["document_id"]))
    documents = {d: {"benchmark": b} for b, docs in out.items() for d in docs}
    return documents, set(left_out)


def halves(value, items_path, keys):
    """{benchmark: (half A, half B)}: C's own split (`choice_read.split`) of C's universe, and the
    left-out items."""
    import choice_read
    documents, left_out = universe(value, items_path, keys)
    split = choice_read.split(documents)
    return {b: (set(a), set(bb)) for b, (a, bb) in split.items()}, left_out


def selection(value, bar, items_path, keys, half="A", groups=GROUP_ORDER):
    """The prompts the reference sends: half A, the left-out items dropped, in group order. Half B
    is refused by name."""
    refuse(half == "A", "Only half A is read by the reference; half B is reserved for C's and T's one read")
    refuse(groups and set(groups) <= set(GROUP_ORDER), "Groups are judge_direct and judge_reason")
    split, left_out = halves(value, items_path, keys)
    left_out |= set(bar.get("left_out") or ())
    chosen = [p for g in groups for p in value["prompts"]
              if p["group"] == g and p["item_id"] not in left_out and p["document_id"] in split[p["benchmark"]][0]]
    assert_half_a(chosen, split)
    return chosen


def assert_half_a(prompts, split):
    """No prompt of a half B document is ever sent."""
    stray = sorted({p["document_id"] for p in prompts if p["document_id"] not in split[p["benchmark"]][0]})
    refuse(not stray, "A document outside half A reached the reference: %s" % ", ".join(stray[:5]))


def turns(prompt):
    """(system, user): B1's two turns as written, or the agent's one user turn."""
    system = prompt.get("system")
    return (system if isinstance(system, str) and system else None), prompt["user"]


# ---------------------------------------------------------------------------
# the key, kept out of everything


def scan(prompts, key):
    """Refuse a prompt carrying a key-shaped string or the key itself. Names the prompt, never the
    string."""
    import guard_secrets
    for p in prompts:
        for text in turns(p):
            if not text:
                continue
            refuse(not (guard_secrets.ANTHROPIC_RE.search(text) or guard_secrets.GENERIC_SK_RE.search(text)
                        or guard_secrets.AWS_RE.search(text)),
                   "Prompt %s carries a key-shaped string; nothing is sent" % p["prompt_id"])
            refuse(not key or key not in text, "Prompt %s carries the provider key; nothing is sent" % p["prompt_id"])


def scrub(text, key):
    import agent_wrapper
    text = agent_wrapper._scrub_error(str(text or ""))
    return text.replace(key, "[REDACTED_KEY]") if key else text


# ---------------------------------------------------------------------------
# the model, read live


def seat_model(root=ROOT):
    """The registry's Anthropic model for the judge's seat, as configured (never typed here)."""
    registry = json.loads((Path(root) / "config" / "agent_registry.json").read_text(encoding="utf-8"))
    entry = registry["agents"][SEAT_AGENT]
    refuse(entry.get("backend") == "claude_api" and entry.get("model"),
           "The registry's %s has no Anthropic model" % SEAT_AGENT)
    return entry["model"]


def resolve(configured, available):
    """The live id, or a stop when the model is gone from the list, ambiguous between snapshots, or
    the list cannot be read (INFRA-026); there is no swap. A model still listed but announced as
    deprecated passes this test: the list carries no deprecation."""
    import model_registry
    status, resolved, candidates = model_registry.resolve_model_id(configured, available)
    refuse(status in ACCEPTED_MODEL_STATUS,
           "Model %s is %s on the provider's live list; the run stops for the operator (no swap)" % (configured, status))
    return status, resolved


def model_record(client, model):
    """The model's own record from the provider, as plain fields, refused when any field names a
    deprecation with a value set. Returns the fields kept (no text the model wrote)."""
    try:
        record = client.models.retrieve(model)
    except Exception as exc:
        raise Stop("The provider's record of %s could not be read (%s); the run stops" % (model, type(exc).__name__))
    # mode="json" turns the SDK's datetime (`created_at`) into text; a record that cannot be turned is
    # passed through json with its text, so the measurement can always be written.
    try:
        fields = record.to_dict(mode="json")
    except TypeError:
        fields = record.to_dict() if hasattr(record, "to_dict") else dict(vars(record))
    fields = json.loads(json.dumps(fields, default=json_default))
    # The SDK's ModelInfo (anthropic 0.87 and 0.95: id, capabilities, created_at, display_name,
    # max_input_tokens, max_tokens, type) has NO deprecation field, so this scan cannot fire on the
    # current SDK type. It is kept for a later type that carries one; it proves nothing today.
    flagged = sorted(k for k, v in fields.items() if "deprecat" in str(k).lower() and v not in (None, False, "", []))
    refuse(not flagged, "The provider's record of %s names a deprecation (%s); the run stops" % (model, ", ".join(flagged)))
    return {k: fields[k] for k in ("id", "display_name", "created_at", "max_input_tokens", "max_tokens") if k in fields}


# ---------------------------------------------------------------------------
# money


def recorded_prices(model, path=PRICES_PATH):
    """The recorded price row for a model id, or a stop."""
    try:
        table = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Stop("No recorded price table (%s)" % Path(path).name)
    row = (table.get("models") or {}).get(model)
    refuse(isinstance(row, dict) and row.get("input_per_mtok") and row.get("output_per_mtok") and row.get("source")
           and row.get("read_on"), "No recorded price for %s in %s" % (model, Path(path).name))
    return row


def check_prices(prices, model, path=PRICES_PATH):
    """The prices given must equal the recorded row for the resolved id."""
    row = recorded_prices(model, path)
    refuse(float(prices["input_per_mtok"]) == float(row["input_per_mtok"])
           and float(prices["output_per_mtok"]) == float(row["output_per_mtok"]),
           "The prices given are not the recorded ones for %s (%s per million in, %s out, %s, read %s)"
           % (model, row["input_per_mtok"], row["output_per_mtok"], row["source"], row["read_on"]))
    return dict(prices, recorded=row, table_sha256=sha(path))


def spend_store(root=ROOT):
    """The one spend store every checkout shares, by the one path rule the guard reads too
    (`cloud_reference_spend.store_path`: docs/loop/private/ of the MAIN checkout, from git's common
    directory as seen from this file's own tree, never from the working folder)."""
    try:
        return spend.store_path(root)
    except spend.SpendStoreError as exc:
        raise Stop(str(exc))


def read_store(path):
    """Every closed run's spend line (intents and hand-back markers are not spend lines). The store
    is created once by the operator (D-358's choice): absent or unreadable, it refuses."""
    try:
        return [r for r in spend.read(path) if r.get("event") in (None, "close")]
    except spend.SpendStoreError as exc:
        raise Stop(str(exc))


def append_store(path, line):
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(line, sort_keys=True, default=json_default) + "\n")


def approval_unused(store, approval, chain):
    """One evet approves one run (D-401 item 3a): refused when an intent or close line of the store
    already names this FOR_SECKIN heading for a run outside `chain` (the run ids this run resumes)."""
    try:
        rows = spend.read(store)
    except spend.SpendStoreError as exc:
        raise Stop(str(exc))
    heading = approval["heading"]
    used = sorted({r["run_id"] for r in rows if r.get("run_id") and approved_heading(r) == heading}
                  - set(chain))
    refuse(not used, "The FOR_SECKIN heading %r approved run %s already; one evet approves one run (a resume of "
                     "that run may use it again)" % (heading, used[0] if used else ""))


def approved_heading(row):
    """The FOR_SECKIN heading a store line names, on an intent or a close line."""
    approval = row.get("seckin_approved")
    if isinstance(approval, dict):
        return approval.get("heading")
    return row.get("seckin_approved_heading")


def chain_runs(earlier):
    """The run ids of the chain a run resumes: the earlier run's and those it resumed in turn."""
    if earlier is None:
        return []
    return list(earlier.get("chain_run_ids_before") or []) + [earlier.get("run_id")]


def open_run(store, run_id, limit_usd, run_folder, kind, check, approval=None, chain=()):
    """Under the store's lock: the budget decision (`check()`, which reads the store) and the one-use
    check of Seckin's yes, then the intent line holding this run's limit as a running cap until its
    close line, naming the heading it was approved under (D-401 items 3a and 5)."""
    try:
        with spend.StoreLock(store):
            budget = check()
            if approval is not None:
                approval_unused(store, approval, chain)
            append_store(store, {"event": "intent", "run_id": run_id, "cap_usd": round(float(limit_usd), 6),
                                 "run_folder": run_folder, "kind": kind,
                                 "seckin_approved_heading": None if approval is None else approval["heading"],
                                 "time_utc": datetime.now(timezone.utc).isoformat()})
    except spend.SpendStoreError as exc:
        raise Stop(str(exc))
    return budget


def close_line(run_id, spent_usd, **fields):
    return dict(fields, event="close", run_id=run_id, spent_usd=round(spent_usd, 6),
                time_utc=datetime.now(timezone.utc).isoformat())


def check_role(lead_side):
    """The lead's form never runs in a role C session, and role C's form only there (D-401 item 11)."""
    in_c = os.environ.get(ROLE_ENVIRONMENT) == ROLE_C
    if lead_side:
        refuse(not in_c, "This is a role C session (%s=%s): only role C's form (--budget-left-usd) runs here"
               % (ROLE_ENVIRONMENT, ROLE_C))
    else:
        refuse(in_c, "Role C's form (--budget-left-usd) runs only in a role C session (%s=%s)"
               % (ROLE_ENVIRONMENT, ROLE_C))


def loop_ledgers(store):
    """The loop ledgers by the store's own path rule (D-401 item 12): the budget ledger beside the
    store, in the MAIN checkout's docs/loop/private found from git, never a worktree's own copy,
    and role R's ledger, where the reaper reads it."""
    import loop_budget_guard  # noqa: F401  (puts tools/loop on the path for the reaper)
    import instance_reaper
    return [Path(store).parent / Path(instance_reaper.PRIVATE_LEDGER).name, Path(instance_reaper.R_LEDGER)]


def check_cap(cap_usd, store, ledgers=None, now=None, *, kind):
    """D-S121 (D-453), D-441: the cap must fit the API's own ceiling, read from the spend store's latest
    ceiling line: closed spend, running intents' caps, the reserves of runs ordered before this one and
    this cap together at or below it (`cloud_reference_spend.api_room`). Lambda's budget is a separate
    ceiling and never limits an API run: the loop ledgers are read for the report only (their budget,
    hard stop and instance spend, `None` where they cannot be given), never to refuse. `kind` is the
    caller's own run kind (the one its intent line records), never defaulted (D-467 item 2): the
    reserves ordered before it are read by that kind."""
    refuse(isinstance(cap_usd, (int, float)) and cap_usd > 0, "A cap in dollars is required")
    refuse(isinstance(kind, str) and kind, "A run kind is required")
    try:
        figures = spend.state(store)
    except spend.SpendStoreError as exc:
        raise Stop(str(exc))
    waiting = spend.lead_may_spend(store)
    refuse(waiting is None, str(waiting))
    try:
        room = spend.api_room(store, kind, cap_usd)
    except spend.SpendStoreError as exc:
        raise Stop(str(exc))
    refuse(room["ok"], str(room["reason"]))
    left = round(room["ceiling_usd"] - room["spent_usd"] - room["running_caps_usd"] - room["reserved_before_usd"], 6)
    return {"rule": "the API's own ceiling (D-S121); Lambda's budget never limits an API run",
            "ceiling_usd": room["ceiling_usd"], "warning_usd": room["warning_usd"], "warn": room["warn"],
            "earlier_reference_spent_usd": figures["spent_usd"], "reference_runs_open_usd": figures["running_caps_usd"],
            "reference_runs_open": figures["open_runs"], "earlier_runs": figures["closed_runs"],
            "reserved_before_usd": room["reserved_before_usd"], "left_usd": left, "store": str(store),
            "lambda": lambda_report(store, ledgers, now), "api_room": room}


def lambda_report(store, ledgers=None, now=None):
    """Lambda's budget and spend from the loop ledgers, for the report only (D-S121): a separate
    ceiling, never a limit on an API run. Ledgers that cannot give a budget report None."""
    import loop_budget_guard as guard   # puts tools/loop on the path for the reaper
    import instance_reaper
    try:
        paths = [Path(x) for x in (loop_ledgers(store) if ledgers is None else ledgers)]
        rows = []
        for path in paths:
            rows.extend(instance_reaper.read_ledger(path))
        budget, hard_stop = instance_reaper.budget_figures(rows)
        spent, _, caps, _ = guard.ledger_state(paths, time.time() if now is None else now)
    except Exception as exc:   # the report only: never a refusal
        return {"budget_usd": None, "hard_stop_usd": None, "unreadable": type(exc).__name__}
    return {"budget_usd": budget, "hard_stop_usd": hard_stop, "instance_spend_usd": round(spent, 6),
            "running_caps_usd": round(caps, 6), "warning_usd": instance_reaper.warning_figure(rows)}


def cost(input_tokens, output_tokens, prices):
    return (input_tokens * prices["input_per_mtok"] + output_tokens * prices["output_per_mtok"]) / 1e6


# count_tokens' figure is the provider's estimate, and the billed input can be slightly higher, so
# the worst case counts the input this much above it (the checker's item 10 on 1d40a5da). It is a
# safety margin on an estimate, not a budget figure; the measurement records it.
COUNT_MARGIN = 1.10


def worst_case(input_tokens, max_tokens, prices):
    return cost(input_tokens * COUNT_MARGIN, max_tokens, prices)


def group_fits(spent, group_worst, cap_usd):
    return spent + group_worst <= cap_usd


def call_fits(spent, worst, cap_usd):
    return spent + worst <= cap_usd


def usage_tokens(reply):
    """{input, output, cache_write} from a reply's usage, or None when it cannot be read. Cache
    reads are counted at the input price (they cost less: the safe side). Cache writes are not
    priced here: the run sends no cache_control, so a usage reporting them is refused (the call
    kept at its worst case and the run stopped)."""
    usage = getattr(reply, "usage", None)
    try:
        used_in = int(usage.input_tokens) + int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        return {"input": used_in, "output": int(usage.output_tokens),
                "cache_write": int(getattr(usage, "cache_creation_input_tokens", 0) or 0)}
    except (AttributeError, TypeError, ValueError):
        return None


def read_reply(reply):
    """(text, stop_reason) of a reply, never raising: a reply the code cannot read is recorded as
    such, and its spend, already counted, stays counted once."""
    try:
        text = "".join(getattr(b, "text", "") or "" for b in (getattr(reply, "content", None) or [])
                       if getattr(b, "type", None) == "text")
    except Exception as exc:
        return None, "unreadable: %s" % type(exc).__name__
    try:
        stop = getattr(reply, "stop_reason", None)
    except Exception as exc:
        stop = "unreadable: %s" % type(exc).__name__
    return text, stop if stop is None or isinstance(stop, str) else str(stop)


def plan(prompts, prices=None):
    """Counts, characters and the worst case per group. Tokens are an estimate here (characters/4
    times 1.35) and are labelled so; the run counts them with the provider's own figures."""
    out = {"label": LABEL, "groups": {}, "tokens_are": "estimate: characters / 4 x 1.35, until count_tokens"}
    for g in GROUP_ORDER:
        mine = [p for p in prompts if p["group"] == g]
        if not mine:
            continue
        chars = sum(len(t or "") for p in mine for t in turns(p))
        tokens = round(chars / 4 * 1.35)
        allowance = sum(int(p["max_new_tokens"]) for p in mine)
        row = {"prompts": len(mine), "characters": chars, "input_tokens_estimate": tokens,
               "output_allowance": allowance,
               "forms": {f: sum(1 for p in mine if p["form"] == f) for f in sorted({p["form"] for p in mine})}}
        if prices:
            row["worst_case_usd"] = round(worst_case(tokens, allowance, prices), 2)
        out["groups"][g] = row
    return out


# ---------------------------------------------------------------------------
# the run


class RunContext:
    def __init__(self, run_dir, run_id):
        self.run_dir, self.run_id = str(run_dir), run_id


def run_folder(out, runs_root=RUNS_ROOT):
    """A fresh folder under output/cloud_reference/, never anywhere else and never reused."""
    out = Path(out).resolve()
    refuse(out.parent == Path(runs_root).resolve(), "The run folder must be output/cloud_reference/<name>")
    if out.exists():
        held = sorted(p.name for p in out.iterdir())
        refuse(not (out / MEASUREMENT_FILE).exists(), "This run folder holds a run already; a new run takes a new folder")
        refuse(not (out / "audit").exists(),
               "This run folder holds audit/ but no readable measurement: a run's replies whose spend is unknown")
        refuse(not held, "This run folder is not empty (%s); a new run takes a new folder" % ", ".join(held[:5]))
    return out


# The SDK reads these from the process environment when it builds a client. None of them may decide
# which key is sent or where it goes (D-S106 item 1): they are removed before the client is built.
KEY_ENVIRONMENT = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
API_BASE_URL = "https://api.anthropic.com"
EVET_LINE = re.compile(r"Seckin: evet \(([^()\n]+)\)")
LEAD_ATTESTED = ("lead-attested: the lead writes the evet line under the FOR_SECKIN heading only after Seckin's "
                 "answer; the runner checks that the line is there, it cannot check who wrote it")


def clear_environment():
    """Every variable the SDK would read for a key, a token or a base URL, removed from this
    process before ANY client is built, the model list's included (D-401 item 1)."""
    for name in KEY_ENVIRONMENT:
        os.environ.pop(name, None)


def make_client(key):
    """The SDK client, built only from the key `resolve_key` gave (D-S106 item 1): the environment
    cleared first, the provider's own base URL, no retry, so a billed request is never sent twice."""
    import anthropic
    clear_environment()
    return anthropic.Anthropic(api_key=key, auth_token=None, base_url=API_BASE_URL, max_retries=0)


def provider_models(backend, keys):
    """The live model list, from a client built as `make_client` builds it (never the registry
    helper's own client, which takes the base URL from the environment)."""
    refuse(backend == "claude_api", "Only the Anthropic API is read here")
    try:
        return {m.id for m in make_client(keys["ANTHROPIC_API_KEY"]).models.list()}
    except Stop:
        raise
    except Exception:
        return None   # cannot verify: `resolve` refuses an unreadable list


def resolve_key():
    """(key, source label) by the repository's one rule: $SHIMMER_CONFIG_PATH, then the sibling
    ../api_keys/config.py, then the .env_path pointer (agent_wrapper). The environment's own
    ANTHROPIC_API_KEY is never consulted. The label names the source, never the value."""
    import agent_wrapper
    path = agent_wrapper.resolve_config_path()
    refuse(path is not None, "No provider credential file found; set SHIMMER_CONFIG_PATH")
    label = next((name for name, candidate in agent_wrapper.candidate_config_paths()
                  if Path(candidate).resolve() == Path(path).resolve()), "unnamed")
    key = agent_wrapper.load_api_keys().get("ANTHROPIC_API_KEY")
    refuse(bool(key), "No ANTHROPIC_API_KEY in the credential file found; set SHIMMER_CONFIG_PATH")
    return key, label


def spend_limit(cap_usd, credit_usd):
    """What a run may spend: the cap or the API credit left, whichever is lower (D-S106 item 3)."""
    return min(float(cap_usd), float(credit_usd))


def check_approval(seckin_approved, for_seckin):
    """Seckin's yes (D-S106 item 2, D-401 item 3): `seckin_approved` names one heading of
    FOR_SECKIN.md (its time), and a line beneath it, before the next heading, reads exactly
    "Seckin: evet (<time>)". Lead-attested (LEAD_ATTESTED). Returns what is recorded."""
    refuse(isinstance(seckin_approved, str) and seckin_approved.strip(),
           'A paid run needs Seckin\'s yes: --seckin-approved "<FOR_SECKIN entry heading time>" (D-S106 item 2)')
    named = seckin_approved.strip()
    try:
        lines = Path(for_seckin).read_text(encoding="utf-8").splitlines()
    except OSError:
        raise Stop("FOR_SECKIN.md cannot be read, so Seckin's yes cannot be checked")
    heads = [i for i, l in enumerate(lines) if l.startswith("#") and named in l]
    refuse(len(heads) == 1, "FOR_SECKIN.md has %s heading naming %r; a paid run needs exactly one"
           % ("no" if not heads else "more than one", named))
    start = heads[0]
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("#")), len(lines))
    yes = [l.strip() for l in lines[start + 1:end] if EVET_LINE.fullmatch(l.strip())]
    refuse(len(yes) == 1, 'No line "Seckin: evet (<time>)" under the heading %r; the lead writes it only after '
                          "Seckin's answer" % lines[start].strip())
    return {"named": named, "heading": lines[start].strip(), "evet_line": yes[0],
            "for_seckin_sha256": sha(for_seckin), "attested": LEAD_ATTESTED}


def chain_spent(earlier):
    """What the chain of runs this one resumes has spent, from the earlier run's own measurement:
    its spend plus what its own chain had spent before it (D-401 item 12)."""
    if earlier is None:
        return 0.0
    return round(float(earlier.get("spent_usd") or 0) + float(earlier.get("chain_spent_before_usd") or 0), 6)


def earlier_run(folder, *, measurement_file, kind, digests, model):
    """The measurement of the run to resume from, refused unless it is a paid run of this kind, on
    the same inputs (`digests`: {path in the measurement: expected value}) and the same model, and
    not a steering check (D-401 item 2)."""
    import claim_guard
    if folder is None:
        return None
    folder = Path(folder)
    refuse(folder.is_dir(), "The run to resume from does not exist")
    try:
        earlier = json.loads((folder / measurement_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Stop("The run to resume from has no readable %s" % measurement_file)
    refuse(not claim_guard.is_steering(earlier), "The run to resume from is a subscription steering check; a paid "
                                                 "run never takes its replies")
    refuse(earlier.get("kind") == kind, "The run to resume from is not a %s run" % kind)
    for path, expected in digests.items():
        value = earlier
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        refuse(value == expected, "The run to resume from read other inputs (%s differs)" % path)
    refuse((earlier.get("model") or {}).get("resolved") == model,
           "The run to resume from ran another model")
    return earlier


def answered(folder, *, model, decoding):
    """{payload sha256: (reply record path, record)} of the calls an earlier run answered, keyed
    by the prompt's digest, so a resumed run never sends one again (D-S106 item 3). Refused unless
    EVERY record of that folder is a paid call (backend claude_api, no steering stamp) on `model`,
    and every answered one carries `decoding(record)` true (D-401 item 2)."""
    import claim_guard
    out = {}
    if folder is None:
        return out
    folder = Path(folder)
    refuse(folder.is_dir(), "The run to resume from does not exist")
    for path in sorted(folder.rglob("audit/model_replies/*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise Stop("A reply record of the run to resume from cannot be read: %s" % path.name)
        refuse(record.get("backend") == "claude_api" and not claim_guard.is_steering(record),
               "A reply record of the run to resume from is not a paid API call: %s" % path.name)
        refuse(record.get("model_id") == model, "A reply record of the run to resume from names another model: %s"
               % path.name)
        payload, reply = record.get("payload") or {}, record.get("reply") or {}
        if record.get("backend_ok") and payload.get("sha256") and isinstance(reply.get("text"), str):
            refuse(decoding(record), "A reply record of the run to resume from ran other settings: %s" % path.name)
            out[payload["sha256"]] = (path, record)
    return out


def text_digest(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def payload_text(prompt):
    """The text a call's reply record keys the prompt by: its system turn, a blank line, its user turn."""
    system, user = turns(prompt)
    return (system + "\n\n" if system else "") + user


def params_for(prompt, model):
    """The request a prompt becomes: its user turn, and its system turn when it has one."""
    system, user = turns(prompt)
    params = {"model": model, "messages": [{"role": "user", "content": user}]}
    if system is not None:
        params["system"] = system
    return params


def call_one(client, p, model, counted, state, cap_usd, prices, key, context, clock):
    """One call, after the stop: (row, None), or (None, why) when its worst case would pass the cap.

    The call's worst case is added to `state["spent"]` BEFORE the request, so an interruption
    during it (a KeyboardInterrupt in messages.create) leaves it counted; it is taken back, and the
    reported cost put in its place, only on a completed reply whose usage was read and carries no
    cache writes. Its reply is saved through reply_records.write; its error is scrubbed of the key."""
    import reply_records
    allowance = int(p["max_new_tokens"])
    worst = worst_case(counted, allowance, prices)
    if not call_fits(state["spent"], worst, cap_usd):
        return None, ("cap: %.4f USD spent and %s's worst case %.4f USD would pass the %.2f USD cap"
                      % (state["spent"], p["prompt_id"], worst, cap_usd))
    params = params_for(p, model)
    payload = payload_text(p)
    agent = "CLOUD_REFERENCE_" + p["group"].upper()
    row = {k: p[k] for k in ("prompt_id", "document_id", "form", "group", "rule_id")}
    row.update(max_new_tokens=allowance, prompt_tokens=counted, worst_case_usd=round(worst, 6))
    started = clock()
    state["spent"] += worst
    try:
        reply = client.messages.create(max_tokens=allowance, **params)
    except Exception as exc:
        # A failed call reports no usage: its worst case stays counted, the safe side.
        error = scrub("%s: %s" % (type(exc).__name__, exc), key)
        call_id = reply_records.write(context, agent=agent, backend="claude_api", model_id=model, payload=payload,
                                      payload_form="anthropic_messages_text", reply=None, ok=False, error=error,
                                      phase="cloud_reference", doc_id=p["document_id"])
        row.update(call_id=call_id, failure=error[:200], length_reached_allowance=None, cost_usd=round(worst, 6),
                   cost_is="worst case, the call failed")
        row["seconds"] = round(clock() - started, 3)
        if type(exc).__name__ in STOP_ERRORS:
            state["halt"] = ("the provider refused the call (%s); the run stops cleanly, every reply so far recorded "
                             "(D-S106 item 3)" % type(exc).__name__)
        return row, None
    used = usage_tokens(reply)
    if used is None:
        row.update(cost_usd=round(worst, 6), cost_is="worst case, the reply's usage could not be read")
    elif used["cache_write"]:
        row.update(cost_usd=round(worst, 6), cost_is="worst case, the usage reports cache writes",
                   cache_write_tokens=used["cache_write"])
        state["halt"] = ("usage reports %d cache-write tokens on %s; they are not priced here, so the run stops"
                         % (used["cache_write"], p["prompt_id"]))
    else:
        actual = cost(used["input"], used["output"], prices)
        state["spent"] += actual - worst
        row.update(input_tokens=used["input"], output_tokens=used["output"], cost_usd=round(actual, 6))
    text, stop_reason = read_reply(reply)
    call_id = reply_records.write(context, agent=agent, backend="claude_api", model_id=model, payload=payload,
                                  payload_form="anthropic_messages_text", reply=text, ok=text is not None,
                                  error=None if text is not None else "reply not readable: " + str(stop_reason),
                                  decoding={"max_tokens": allowance, "other_settings": "provider_default"},
                                  phase="cloud_reference", doc_id=p["document_id"])
    row.update(call_id=call_id, failure=None if text is not None else "reply not readable", stop_reason=stop_reason,
               length_reached_allowance=stop_reason == "max_tokens",
               reply=None if text is None else {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                                                "length_bytes": len(text.encode("utf-8"))})
    row["seconds"] = round(clock() - started, 3)
    return row, None


def run(prompts_path, bar_path, items_path, answer_keys, out, *, cap_usd, credit_usd, prices, deprecation_checked,
        seckin_approved, groups=GROUP_ORDER, resume_from=None, max_calls=None, keys=None, client=None,
        list_models=None, clock=time.perf_counter, root=ROOT, runs_root=RUNS_ROOT, prices_path=PRICES_PATH,
        store=None, ledgers=None, for_seckin=None):
    """The paid run. `client`, `keys` and `list_models` are the SDK client (make_client), the
    credential file's keys and model_registry.list_available_models unless a proof hands stand-ins.
    Returns the measurement, which is written to `out` on any exit once the folder exists."""
    refuse(isinstance(prices, dict) and prices.get("input_per_mtok", 0) > 0 and prices.get("output_per_mtok", 0) > 0
           and prices.get("source"), "Prices per million tokens and their source (page and date) are required")
    refuse(isinstance(deprecation_checked, str) and DEPRECATION_FORM.fullmatch(deprecation_checked.strip()),
           'The deprecations page reading is required in the form "<url>, <YYYY-MM-DD>, not deprecated"')
    clear_environment()
    check_role(lead_side=True)
    refuse(isinstance(credit_usd, (int, float)) and credit_usd > 0, "The API credit left is required (--credit-usd)")
    refuse(max_calls is None or (isinstance(max_calls, int) and max_calls > 0), "--max-calls is a positive count")
    out = run_folder(out, runs_root)
    store = spend_store(root) if store is None else Path(store)
    approval = check_approval(seckin_approved, Path(store).parent / FOR_SECKIN_NAME if for_seckin is None else for_seckin)
    value, bar = load(prompts_path, bar_path)
    chosen = selection(value, bar, items_path, answer_keys, "A", tuple(groups))
    if keys is None:
        key, key_source = resolve_key()
        keys = {"ANTHROPIC_API_KEY": key}
    else:
        key, key_source = keys.get("ANTHROPIC_API_KEY"), "given by a proof"
    refuse(bool(key), "No ANTHROPIC_API_KEY in the credential file found; set SHIMMER_CONFIG_PATH")
    scan(chosen, key)
    if list_models is None:
        list_models = provider_models
    configured = seat_model(root)
    status, model = resolve(configured, list_models("claude_api", keys))
    prices = check_prices(prices, model, prices_path)
    earlier = earlier_run(resume_from, measurement_file=MEASUREMENT_FILE, kind=SCHEMA, model=model,
                          digests={"prompts_sha256": sha(prompts_path), "config_sha256": value.get("config_sha256")})
    allowances = {text_digest(payload_text(p)): int(p["max_new_tokens"]) for p in chosen}
    done_before = answered(resume_from, model=model, decoding=lambda r: r.get("decoding") == {
        "max_tokens": allowances.get((r.get("payload") or {}).get("sha256")), "other_settings": "provider_default"})
    spent_before = chain_spent(earlier)
    limit = spend_limit(cap_usd, credit_usd - spent_before)
    refuse(limit > 0, "The credit left after this chain's earlier runs (%.4f USD spent) is %.4f USD"
           % (spent_before, credit_usd - spent_before))
    if client is None:
        client = make_client(key)
    provider_record = model_record(client, model)
    context = RunContext(out, "cloud-reference-" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:12])
    chain = chain_runs(earlier)
    budget = open_run(store, context.run_id, limit, out.name, SCHEMA, lambda: check_cap(cap_usd, store, ledgers, kind=SCHEMA),
                      approval=approval, chain=chain)
    rows, skipped, counted, reused = [], [], {}, []
    state = {"spent": 0.0, "stopped": None, "halt": None, "calls": 0}
    try:
        for group in groups:
            mine = []
            for p in [q for q in chosen if q["group"] == group]:
                found = done_before.get(text_digest(payload_text(p)))
                if found is None:
                    mine.append(p)
                    continue
                # Answered before: its record is copied in, nothing is sent (D-S106 item 3).
                earlier_path, earlier_record = found
                target = out / "audit" / "model_replies" / earlier_path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(earlier_path, target)
                rows.append({"prompt_id": p["prompt_id"], "document_id": p["document_id"], "form": p["form"],
                             "group": p["group"], "rule_id": p["rule_id"], "call_id": earlier_record["call_id"],
                             "failure": None, "length_reached_allowance": None, "resumed_from": Path(resume_from).name,
                             "reply": {k: earlier_record["reply"][k] for k in ("sha256", "length_bytes")}, "seconds": 0.0,
                             "cost_usd": 0.0, "cost_is": "answered by the earlier run, its spend in its own line"})
                reused.append(p["prompt_id"])
            # A group starts only when its whole worst case fits under what is left of the cap (D-326:
            # judge_reason runs only if it still fits after judge_direct); each call is checked again.
            try:
                for p in mine:
                    counted[p["prompt_id"]] = int(client.messages.count_tokens(**params_for(p, model)).input_tokens)
            except Exception as exc:
                state["stopped"] = "count_tokens failed in %s: %s" % (group, scrub("%s: %s" % (type(exc).__name__, exc), key))
                break
            group_worst = sum(worst_case(counted[p["prompt_id"]], int(p["max_new_tokens"]), prices) for p in mine)
            if not group_fits(state["spent"], group_worst, limit):
                skipped.append({"group": group, "worst_case_usd": round(group_worst, 4),
                                "spent_before_usd": round(state["spent"], 4)})
                state["stopped"] = ("cap: %s not started, its worst case %.4f USD after %.4f USD spent would pass the "
                                    "%.2f USD limit (the cap or the credit left, whichever is lower)"
                                    % (group, group_worst, state["spent"], limit))
                break
            for p in mine:
                if max_calls is not None and state["calls"] >= max_calls:
                    state["stopped"] = ("chunk done: %d calls; resume with --resume-from this folder" % max_calls)
                    break
                state["calls"] += 1
                row, over = call_one(client, p, model, counted[p["prompt_id"]], state, limit, prices, key, context,
                                     clock)
                if over:
                    state["stopped"] = over
                    break
                rows.append(row)
                if state["halt"]:
                    state["stopped"] = state["halt"]
                    break
            if state["stopped"]:
                break
    except BaseException as exc:
        state["stopped"] = "interrupted: %s" % scrub(type(exc).__name__, key)
        raise
    finally:
        measurement = {
            "schema": MEASUREMENT_SCHEMA, "kind": SCHEMA, "label": LABEL, "prompts_sha256": sha(prompts_path),
            "config_sha256": value.get("config_sha256"), "half": "A", "groups": list(groups), "rows": rows,
            "prompts": len(chosen), "sent": len(rows) - len(reused), "answered": len(rows), "complete": state["stopped"] is None and len(rows) == len(chosen),
            "stopped": state["stopped"], "groups_not_started": skipped,
            "model": {"configured": configured, "resolved": model, "status": status, "seat_agent": SEAT_AGENT,
                      "registry_unedited": True, "provider_record": provider_record,
                      "deprecation_checked": deprecation_checked,
                      "deprecation_note": "the live list catches a gone or ambiguous model only; a listed model "
                                          "announced as deprecated is caught only by the record's own field or "
                                          "the operator's reading of the deprecations page"},
            "cap_usd": cap_usd, "credit_usd": credit_usd, "limit_usd": limit, "seckin_approved": approval,
            "key_source": key_source, "resumed_from": None if resume_from is None else Path(resume_from).name,
            "reused_answers": len(reused), "max_calls": max_calls, "calls_made": state["calls"],
            "chain_spent_before_usd": spent_before, "chain_run_ids_before": chain,
            "budget": budget, "spent_usd": round(state["spent"], 6), "prices": prices,
            "max_retries": 0, "count_margin": COUNT_MARGIN, "seconds": round(sum(r.get("seconds") or 0 for r in rows), 3), "run_id": context.run_id,
            "reads": "J1's prompts file, half A; ids, counts, tokens and dollars here, the replies in the reply records"}
        # The spend line first (small, the one the next run's cap reads), then the measurement; each in
        # its own try, so one failing never loses the other, and the first failure is raised after both.
        failures = []
        try:
            append_store(store, close_line(context.run_id, state["spent"], run_folder=out.name, model=model,
                                           complete=measurement["complete"], stopped=state["stopped"],
                                           seckin_approved=approval, key_source=key_source, kind=SCHEMA))
        except Exception as exc:
            failures.append(exc)
        try:
            write_json(out / MEASUREMENT_FILE, measurement)
        except Exception as exc:
            failures.append(exc)
        if failures:
            raise failures[0]
    return measurement


def summary_line(measurement):
    """What the run prints: counts and dollars only."""
    return ("%s | model %s (%s) | sent %d of %d | spent %.4f of %.2f USD | %s"
            % (LABEL, measurement["model"]["resolved"], measurement["model"]["status"], measurement["sent"],
               measurement["prompts"], measurement["spent_usd"], measurement["cap_usd"],
               "complete" if measurement["complete"] else "stopped: " + str(measurement["stopped"])))


# ---------------------------------------------------------------------------
# the reading


def half_a_rows(rows, split):
    """Only half A's documents, whatever the pass held: J1's local pass covers both halves."""
    return [r for r in rows if r["document_id"] in split[r["benchmark"]][0]]


def read(prompts_path, bar_path, items_path, run_dir, keys, out, tag, steering=False):
    """Half A figures of one pass folder, through J1's reader functions and the scorer. A pass
    folder that is a subscription steering check (D-S104 item 1: its measurement or any reply record
    carries the steering label) is refused, unless `steering` is asked for; its figures then carry the
    steering label and `claim: false`, so nothing downstream can take them for a claim."""
    import claim_guard
    import judge_read
    import reply_records
    value, bar = load(prompts_path, bar_path)
    run_dir = Path(run_dir)
    measurement = json.loads((run_dir / MEASUREMENT_FILE).read_text(encoding="utf-8"))
    records = {r.get("call_id"): r for r in reply_records.records(run_dir / "audit" / "model_replies")}
    # The steering test comes before anything is scored or a key is touched.
    is_steering = claim_guard.is_steering(measurement) or claim_guard.is_steering(list(records.values()))
    if is_steering and not steering:
        claim_guard.refuse_claim(measurement if claim_guard.is_steering(measurement) else list(records.values()),
                                 "read as the cloud reference's figure")
    refuse(measurement.get("prompts_sha256") == sha(prompts_path), "The pass folder is not a pass of these prompts")
    split, _ = halves(value, items_path, keys)
    by_prompt = {r["prompt_id"]: r for r in measurement["rows"]}
    per_item, counts = judge_read.agent_rows(value, by_prompt, records)
    left_out = set(bar.get("left_out") or ())
    reference = measurement.get("kind") == SCHEMA
    result = {"label": LABEL if reference else "J1 local pass, half A", "half": "A", "views": {},
              "models": measurement.get("model") or measurement.get("models")}
    for group in GROUP_ORDER:
        result["views"][group] = {}
        for view in judge_read.VIEWS:
            rows = []
            for (v, g, benchmark, document_id, rule_id, item_id), calls in per_item.items():
                if (v, g) == (view, group):
                    cls, source = judge_read.item_class(calls)
                    rows.append({"document_id": document_id, "item_id": item_id, "benchmark": benchmark,
                                 "cls": cls, "source": source})
            scored = judge_read.label_rows(half_a_rows(rows, split), keys, out, left_out, "%s_%s_%s" % (tag, group, view))
            result["views"][group][view] = judge_read.figures(scored, judge_read.G1_SETTINGS)
        bare = [dict(r, cls=None) for r in judge_read.b1_rows(value, by_prompt, records) if r["group"] == group]
        scored = judge_read.label_rows(half_a_rows(bare, split), keys, out, left_out, "%s_%s_b1" % (tag, group))
        result["views"][group]["b1"] = judge_read.figures(scored, judge_read.G1_SETTINGS)
    result["spent_usd"] = measurement.get("spent_usd")
    result["seconds"] = measurement.get("seconds")
    if is_steering:
        result = claim_guard.steering_view(result)
    write_json(Path(out) / ("%s_half_a.json" % tag), result)
    return result


# ---------------------------------------------------------------------------


def prices_from(args):
    return {"input_per_mtok": args.price_input_per_mtok, "output_per_mtok": args.price_output_per_mtok,
            "source": args.price_source}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_reference.py", allow_abbrev=False, description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run", "read"):
        p = sub.add_parser(name, allow_abbrev=False)
        p.add_argument("--prompts", required=True)
        p.add_argument("--bar", required=True, help="J1's j1_bar.json")
        p.add_argument("--items", required=True, help="the pinned g1_bar_items.json (C's universe)")
        p.add_argument("--key", action="append", required=True,
                       help="an adapter answer key, read by the scorer only, for C's universe (repeat)")
        if name in ("plan", "run"):
            p.add_argument("--group", action="append", choices=list(GROUP_ORDER))
            p.add_argument("--price-input-per-mtok", type=float, required=name == "run")
            p.add_argument("--price-output-per-mtok", type=float, required=name == "run")
            p.add_argument("--price-source", required=name == "run", help="the pricing page and the date it was read")
        if name == "run":
            p.add_argument("--cap-usd", type=float, required=True)
            p.add_argument("--credit-usd", type=float, required=True, help="the API credit left; never passed by a worst case")
            p.add_argument("--seckin-approved", required=True,
                           help="the FOR_SECKIN entry heading's time, passed only after Seckin's evet (D-S106 item 2)")
            p.add_argument("--resume-from", default=None, help="an earlier run folder: its answered prompts are not sent")
            p.add_argument("--max-calls", type=int, default=None, help="a chunk: stop cleanly after this many calls")
            p.add_argument("--deprecation-checked", required=True,
                           help='the deprecations page reading: "<url>, <YYYY-MM-DD>, not deprecated"')
            p.add_argument("--out", required=True, help="a new folder output/cloud_reference/<name>")
        if name == "read":
            p.add_argument("--run", required=True)
            p.add_argument("--out", required=True)
            p.add_argument("--tag", required=True)
            p.add_argument("--steering", action="store_true",
                           help="read a subscription steering check, its figures labelled steering only (D-S104)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "plan":
            value, bar = load(args.prompts, args.bar)
            prices = prices_from(args) if args.price_input_per_mtok and args.price_output_per_mtok else None
            print(json.dumps(plan(selection(value, bar, args.items, args.key, "A", tuple(args.group or GROUP_ORDER)),
                                  prices), indent=1))
        elif args.command == "run":
            print(summary_line(run(args.prompts, args.bar, args.items, args.key, args.out, cap_usd=args.cap_usd,
                                   credit_usd=args.credit_usd, seckin_approved=args.seckin_approved,
                                   resume_from=args.resume_from, max_calls=args.max_calls, prices=prices_from(args),
                                   deprecation_checked=args.deprecation_checked,
                                   groups=tuple(args.group or GROUP_ORDER))))
        else:
            result = read(args.prompts, args.bar, args.items, args.run, args.key, args.out, args.tag, steering=args.steering)
            print(json.dumps({"label": result["label"], "half": "A"}, indent=1))
    except Stop as exc:
        print("cloud_reference stopped: %s" % exc, file=sys.stderr)
        return 3
    except ValueError as exc:
        if type(exc).__name__ != "SteeringNotAClaim":
            raise
        print("cloud_reference refused: %s" % exc, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
