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

The gate's claim set (lane/cloud-gate; D-S92, D-379: bar (b) needs the cloud reference on the gate
items): `plan` and `run` with `--gate-set <claim_set_ids.json>` in place of `--bar`, `--items` and
`--key` send B1's own prompts (`gate-prompts --held <role B's held build>`, built as the B1 arm's own
file is) for one benchmark, held to gate_score.CLAIM_SET_SHA256: every claim-set item in every group
named, one prompt each, under the document the set lists; and `--gate-held <that held build>` is
required, the prompts file refused unless it is, byte for byte, the one gate-prompts rebuilds from
it (ids alone do not pin the text sent). Every guard below holds; the kind is
`cloud-reference-gate-v1` (its intent and close lines, reserves and resumes are read by it). The plan
states the worst case per group and for the direct form alone and direct plus reasoning, at the
recorded prices of the registry's configured model, with the store's room for each, read only.
gate_score.cloud_arm reads the run as the `cloud` arm of gate_score.figures.

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
    reply whose usage was read and priced field by field (`usage_cost`): uncached input, output,
    cache reads and cache writes by duration, at the route's recorded rates; a usage field it cannot
    price stops the run, the call kept at its worst case.

D-610 cuts 1 and 2 (Seckin's yes of 13 November 2026, 15:06):
  - `--route batch --batch-deadline-minutes M` sends each group as one Message Batch. Each request
    body is `request_for`, the dict the single route passes to `messages.create`, so the bytes are the
    same; every call's worst case is checked and counted at the recorded BATCH rates before the batch
    is sent; the batch id goes to `batches.json` in the run folder at once and to the spend line; the
    batch is read every minute until it ends, cancelled past its deadline (which must be below the
    provider's 24-hour expiry) and read 15 minutes more; results are joined by custom id, and an
    errored, canceled, expired or missing result is a recorded no_answer, never sent again by the run;
  - (checker round 1) the batch record (its run-scoped custom-id prefix `id_prefix`, request count
    and send time) is written to batches.json BEFORE the request, so a crash during it loses no
    batch: its calls stay no_answer rows at their worst case, and `reconcile --run <folder>`
    (read-only on the provider) lists the batches made since, takes the one whose every result
    carries the prefix, reads a given-up batch again, and appends what it found to reconcile.json,
    never changing the spend line; a resume carries the earlier run's no_answer rows forward and
    sends none of them again unless `--resend-no-answer`; every close line field is declared in
    CLOSE_LINE_FIELDS;
  - a B1 system turn that the provider counts at or above the model's minimum cacheable length
    (the recorded `cache.min_tokens`) and that two or more prompts of a group send is sent as one
    text block of the same text with cache_control (1 hour on both routes, from the table, so the
    two routes send the same bytes); the user turn is never split. Every rate, the cache rule and the
    batch limits are in cloud_reference_prices.json, none in code.
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


# ---------------------------------------------------------------------------
# the gate's claim set (D-S92, D-S99, D-379: bar (b) needs the cloud reference on the gate items)

GATE_SCHEMA = "cloud-reference-gate-v1"
GATE_LABEL = ("Reference: a paid cloud model on the gate's claim set, on B1's own prompts. Not Shimmer's "
              "performance.")
GATE_PROMPTS_SCHEMA = "doc-judge-prompts-v1"
B1_FORM = "b1"


def load_gate_prompts(prompts_path):
    """A gate prompts file: B1's own prompts (`doc_judge.py build --b1`), form `b1` only."""
    value = json.loads(Path(prompts_path).read_text(encoding="utf-8"))
    refuse(isinstance(value, dict) and value.get("schema") == GATE_PROMPTS_SCHEMA
           and isinstance(value.get("prompts"), list) and value["prompts"],
           "The gate prompts file is not a %s file with prompts" % GATE_PROMPTS_SCHEMA)
    refuse(all(p.get("form") == B1_FORM for p in value["prompts"]),
           "The gate prompts file holds a prompt that is not B1's own (form b1)")
    return value


J1_CONFIG = Path(__file__).resolve().with_name("doc_judge_prompt_j1.json")


def build_gate_prompts(held, out, config_path=J1_CONFIG):
    """B1's own prompts for one held gate build (role B's folder: one bundle per document and its
    items.json), as the B1 arm's own files are built: `doc_judge.build` over every document with the
    build's items.json, `--b1`, under J1's config (groups judge_direct and judge_reason), then the
    prompts of form b1 kept, their ids unchanged, and `prompt_count` set to their count. Reproduced
    byte for byte the quick-read lane's b1_prompts_contradoc.json and b1_prompts_scitab.json from
    held_D-S100's quick builds. Returns the file's digest and count."""
    import doc_judge
    held, out = Path(held), Path(out)
    docs = sorted(p for p in held.iterdir() if p.is_dir())
    refuse(docs and (held / "items.json").is_file(), "The held build has no documents or no items.json")
    full = out.with_name(out.name + ".full.tmp")
    try:
        value = doc_judge.build(docs, full, items=[held / "items.json"] * len(docs), config_path=config_path, b1=True)
    finally:
        if full.exists():
            full.unlink()
    value["prompts"] = [p for p in value["prompts"] if p.get("form") == B1_FORM]
    value["prompt_count"] = len(value["prompts"])
    doc_judge._write_json(out, value)
    return {"prompts_sha256": sha(out), "prompt_count": value["prompt_count"], "documents": len(value["documents"])}


def gate_selection(value, set_file, groups=GROUP_ORDER, pin=None):
    """The prompts a gate claim-set run sends: one benchmark, held to the frozen claim set file
    (`gate_score.CLAIM_SET_SHA256`, never the quick subset or any other set), every group given
    holding exactly one prompt per item of the set file under the document the set file lists it
    under. Returns (prompts in group order, benchmark, set digest)."""
    import gate_score
    pin = gate_score.CLAIM_SET_SHA256 if pin is None else pin
    refuse(groups and set(groups) <= set(GROUP_ORDER), "Groups are judge_direct and judge_reason")
    refuse(sha(set_file) == pin, "The set file is not the frozen gate claim set (gate_score.CLAIM_SET_SHA256): "
                                 "nothing is sent")
    benchmarks = {p.get("benchmark") for p in value["prompts"]}
    refuse(len(benchmarks) == 1, "A gate prompts file holds one benchmark")
    benchmark = benchmarks.pop()
    refuse(benchmark in ("contradoc", "scitab"), "The gate reads contradoc and scitab only")
    _digest, listed = gate_score.set_items(set_file, benchmark)
    refuse(listed, "The claim set lists no %s item" % benchmark)
    chosen = []
    for group in groups:
        mine = [p for p in value["prompts"] if p.get("group") == group]
        ids = [p["item_id"] for p in mine]
        refuse(len(ids) == len(set(ids)) and set(ids) == set(listed),
               "The prompts of group %s are not the claim set's %s items, one each" % (group, benchmark))
        stray = sorted(p["prompt_id"] for p in mine if listed[p["item_id"]] != p["document_id"])
        refuse(not stray, "Prompt %s names another document than the claim set lists" % (stray[:1] or [""])[0])
        chosen += mine
    return chosen, benchmark, pin


def check_gate_prompts(prompts_path, held, rebuild=None):
    """The gate prompts file must be the one `build_gate_prompts` rebuilds from the named held build,
    byte for byte: ids alone do not pin the text a paid run sends. Rebuilt into a temporary folder;
    returns what is recorded."""
    import tempfile
    rebuild = build_gate_prompts if rebuild is None else rebuild
    refuse(held is not None and Path(held).is_dir(), "A gate run names the held build its prompts are rebuilt from (--gate-held)")
    with tempfile.TemporaryDirectory(prefix="shimmer_gate_rebuild_") as tmp:
        rebuilt = Path(tmp) / "rebuilt.json"
        rebuild(held, rebuilt)
        digest = sha(rebuilt)
    refuse(digest == sha(prompts_path), "The gate prompts file is not the one gate-prompts rebuilds from %s: nothing is sent"
           % Path(held).name)
    return {"held": Path(held).name, "rebuilt_sha256": digest}


def gate_plan(prompts_path, set_file, groups=GROUP_ORDER, root=ROOT, prices_path=PRICES_PATH, store=None,
              measured=None, held=None, rebuild=None):
    """The claim-set run's plan, with no provider call: counts, characters, the token estimate and
    the worst case at the RECORDED prices of the registry's configured model (not resolved live:
    the run resolves it and refuses prices that differ), per group and for the direct form alone and
    direct plus reasoning; the spend store's room for each (read only); and, when `measured` gives
    the output tokens per call a measured run wrote per group, an expected figure labelled so."""
    value = load_gate_prompts(prompts_path)
    chosen, benchmark, digest = gate_selection(value, set_file, tuple(groups))
    rebuilt = check_gate_prompts(prompts_path, held, rebuild)
    configured = seat_model(root)
    row = recorded_prices(configured, prices_path)
    prices = {"input_per_mtok": float(row["input_per_mtok"]), "output_per_mtok": float(row["output_per_mtok"])}
    out = plan(chosen, prices)
    out.update(label=GATE_LABEL, benchmark=benchmark, gate_set_sha256=digest, prompts_sha256=sha(prompts_path), rebuilt=rebuilt,
               model={"configured": configured, "resolved": "not read: the run resolves it live"},
               prices=dict(row, table_sha256=sha(prices_path)), count_margin=COUNT_MARGIN,
               worst_case_is="the token estimate x %.2f and the full output allowance on every call, at the recorded "
                             "prices" % COUNT_MARGIN)
    forms = {"direct": ("judge_direct",), "direct_and_reasoning": ("judge_direct", "judge_reason")}
    out["forms"] = {}
    for name, wanted in forms.items():
        if not set(wanted) <= set(out["groups"]):
            continue
        worst = round(sum(out["groups"][g]["worst_case_usd"] for g in wanted), 2)
        entry = {"groups": list(wanted), "prompts": sum(out["groups"][g]["prompts"] for g in wanted),
                 "worst_case_usd": worst}
        if isinstance(row.get("batch"), dict):
            batch = {"input_per_mtok": float(row["batch"]["input_per_mtok"]),
                     "output_per_mtok": float(row["batch"]["output_per_mtok"])}
            entry["batch_worst_case_usd"] = round(sum(
                worst_case(out["groups"][g]["input_tokens_estimate"], out["groups"][g]["output_allowance"], batch)
                for g in wanted), 2)
        if measured:
            expected = sum(cost(out["groups"][g]["input_tokens_estimate"], measured[g] * out["groups"][g]["prompts"], prices)
                           for g in wanted)
            entry["expected_usd"] = round(expected, 2)
            if isinstance(row.get("batch"), dict):
                entry["batch_expected_usd"] = round(sum(
                    cost(out["groups"][g]["input_tokens_estimate"], measured[g] * out["groups"][g]["prompts"], batch)
                    for g in wanted), 2)
                entry["batch_expected_is"] = "the same estimate at the recorded batch rates, no prompt marked for cache"
            entry["expected_is"] = ("estimate: the input token estimate and the output tokens per call measured in %s"
                                    % measured.get("source"))
        try:
            entry["store"] = spend.api_room(spend_store(root) if store is None else store, GATE_SCHEMA, worst)
        except (Stop, spend.SpendStoreError) as exc:
            entry["store"] = {"ok": None, "reason": "the spend store cannot be read: %s" % exc}
        out["forms"][name] = entry
    return out


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


def batch_limits(prices):
    """The provider's batch limits as the recorded table gives them (requests, bytes, expiry hours)."""
    limits = ((prices or {}).get("recorded") or {}).get("batch_limits") or {}
    refuse(all(isinstance(limits.get(f), int) and limits[f] > 0 for f in ("max_requests", "max_bytes", "expiry_hours")),
           "The recorded price row has no batch limits (max_requests, max_bytes, expiry_hours)")
    return {f: limits[f] for f in ("max_requests", "max_bytes", "expiry_hours")}


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


# Every field a close line of the paid runners may carry (this module's and cloud_reference_b1.py's),
# declared here, beside the writer: the spend reader (tools/loop/cloud_reference_spend.py) is a bound
# controller file and reads only `event`, `run_id` and `spent_usd`; the standing-orders check reads
# `seckin_approved`, `key_source`, `chain_run_ids_before` and `time_utc`. D-610 adds `route`, `rates`,
# `batch_ids` and `batch_custom_id_prefixes`, which no reader of the store needs to count a spend.
CLOSE_LINE_FIELDS = ("event", "run_id", "spent_usd", "time_utc", "run_folder", "model", "complete", "stopped",
                     "seckin_approved", "key_source", "kind", "route", "rates", "batch_ids",
                     "batch_custom_id_prefixes")


def close_line(run_id, spent_usd, **fields):
    undeclared = sorted(set(fields) - set(CLOSE_LINE_FIELDS))
    refuse(not undeclared, "A close line field is not declared in CLOSE_LINE_FIELDS: %s" % ", ".join(undeclared))
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
    return [Path(store).parent / ledger_name(), Path(instance_reaper.R_LEDGER)]


def ledger_name():
    """The budget ledger's file name: a proof's PRIVATE_LEDGER when one is set, else shared_paths.LEDGER_NAME.
    Since DELETE-SAFE-A item 2 (ed7b5faf) instance_reaper.PRIVATE_LEDGER is None and resolved at use; only the
    name is needed here, so nothing resolves the main checkout (none may exist, as on the Lambda gate)."""
    import loop_budget_guard  # noqa: F401  (puts tools/loop on the path for the reaper)
    import instance_reaper
    import shared_paths
    if instance_reaper.PRIVATE_LEDGER is not None:
        return Path(instance_reaper.PRIVATE_LEDGER).name
    return shared_paths.LEDGER_NAME


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


# D-610 cuts 1 and 2: the price set a route bills at, the cache rule, and every usage field priced.
RATE_FIELDS = ("input_per_mtok", "output_per_mtok", "cache_write_5m_per_mtok", "cache_write_1h_per_mtok",
               "cache_read_per_mtok")
ROUTES = ("single", "batch")
# The usage fields priced here, and the one field read but not priced (the service tier, which must be
# the route's own). Any other field carrying a value is a usage this code cannot price: the run stops.
PRICED_USAGE = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                "cache_creation")
TIER_OF_ROUTE = {"single": ("standard",), "batch": ("batch",)}
CUSTOM_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")   # the provider's custom_id form (batch-processing page)
BATCH_POLL_SECONDS = 60        # how often a batch is read while it runs (not a budget figure)
BATCH_CANCEL_GRACE_SECONDS = 900   # after a cancel, how long the batch is read until it ends


class Unpriceable(Exception):
    """A usage this code cannot price; the call stays at its worst case and the run stops."""


def route_rates(prices, route):
    """The five rates a route bills at, from the RECORDED row the run checked (`check_prices`): the
    row itself for `single`, its `batch` block for `batch`. Every rate must be recorded; none is
    computed here (the table records the batch rates as the pricing page gives them)."""
    refuse(route in ROUTES, "The route is single or batch")
    row = (prices or {}).get("recorded") or {}
    rates = row if route == "single" else row.get("batch")
    refuse(isinstance(rates, dict) and all(isinstance(rates.get(f), (int, float)) and rates[f] > 0 for f in RATE_FIELDS),
           "The recorded price row has no %s rates for %s (%s)" % (route, ", ".join(RATE_FIELDS),
                                                                   "cloud_reference_prices.json"))
    return {f: float(rates[f]) for f in RATE_FIELDS}


def cache_rule(prices):
    """{min_tokens, ttl: {route: ttl}} from the recorded row: the model's minimum cacheable length and
    the cache duration each route marks (the batch page advises the 1-hour cache, a batch running
    longer than 5 minutes)."""
    row = (prices or {}).get("recorded") or {}
    rule = row.get("cache") or {}
    refuse(isinstance(rule.get("min_tokens"), int) and rule["min_tokens"] > 0
           and all((rule.get("ttl") or {}).get(r) in ("5m", "1h") for r in ROUTES),
           "The recorded price row has no cache rule (min_tokens and a ttl per route)")
    return {"min_tokens": rule["min_tokens"], "ttl": dict(rule["ttl"])}


def reserve_rates(rates, ttl):
    """The rates a call's worst case is reserved at: with a cache mark, every input token at the
    higher of the input rate and that duration's write rate (the safe side)."""
    if not ttl:
        return rates
    return dict(rates, input_per_mtok=max(rates["input_per_mtok"], rates["cache_write_%s_per_mtok" % ttl]))


def _fields(obj):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return dict(obj)
    for name in ("to_dict", "model_dump"):
        method = getattr(obj, name, None)
        if callable(method):
            try:
                return dict(method())
            except Exception:
                pass
    try:
        return dict(vars(obj))
    except TypeError:
        return None


def _carries(value):
    """True when a usage field holds anything but nothing: a non-zero number, a non-empty text or a
    container holding one."""
    if value in (None, False, 0, "", [], {}):
        return False
    if isinstance(value, (int, float)):
        return value != 0
    nested = _fields(value) if not isinstance(value, (str, list, tuple)) else None
    if nested is not None:
        return any(_carries(v) for v in nested.values())
    if isinstance(value, (list, tuple)):
        return any(_carries(v) for v in value)
    return True


def usage_cost(reply, rates, *, ttl=None, route="single"):
    """The reported cost of a reply from every field of its usage, or None when the usage cannot be
    read. Raises Unpriceable for a field it cannot price: an unknown field carrying a value, a service
    tier other than the route's, or a cache write whose duration is neither broken down nor marked."""
    usage = _fields(getattr(reply, "usage", None))
    if usage is None:
        return None
    try:
        fresh = int(usage.get("input_tokens"))
        output = int(usage.get("output_tokens"))
        read = int(usage.get("cache_read_input_tokens") or 0)
        written = int(usage.get("cache_creation_input_tokens") or 0)
    except (TypeError, ValueError):
        return None
    tier = usage.get("service_tier")
    if tier is not None and tier not in TIER_OF_ROUTE[route]:
        raise Unpriceable("service tier %s on the %s route" % (tier, route))
    unknown = sorted(k for k, v in usage.items() if k not in PRICED_USAGE + ("service_tier",) and _carries(v))
    if unknown:
        raise Unpriceable("usage field %s" % ", ".join(unknown))
    split = _fields(usage.get("cache_creation"))
    if split is not None and _carries(split):
        extra = sorted(k for k, v in split.items()
                       if k not in ("ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens") and _carries(v))
        if extra:
            raise Unpriceable("cache_creation field %s" % ", ".join(extra))
        five, hour = int(split.get("ephemeral_5m_input_tokens") or 0), int(split.get("ephemeral_1h_input_tokens") or 0)
        if five + hour != written:
            raise Unpriceable("cache writes %d not the sum of their durations %d + %d" % (written, five, hour))
    elif written:
        if not ttl:
            raise Unpriceable("%d cache-write tokens with no duration reported and no cache mark sent" % written)
        five, hour = (written, 0) if ttl == "5m" else (0, written)
    else:
        five = hour = 0
    usd = (fresh * rates["input_per_mtok"] + output * rates["output_per_mtok"] + read * rates["cache_read_per_mtok"]
           + five * rates["cache_write_5m_per_mtok"] + hour * rates["cache_write_1h_per_mtok"]) / 1e6
    return {"cost_usd": usd, "input_tokens": fresh + read + written, "uncached_input_tokens": fresh,
            "output_tokens": output, "cache_read_tokens": read, "cache_write_5m_tokens": five,
            "cache_write_1h_tokens": hour}


def usage_tokens(reply):
    """{input, output, cache_write} from a reply's usage, or None when it cannot be read: the reader
    cloud_reference_b1.py prices with (it sends no cache_control and refuses cache writes). This
    module's own runs price every usage field with `usage_cost` (D-610 cut 2)."""
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


def no_answer_before(earlier):
    """{prompt id: its row} of the no_answer rows the run resumed recorded (its own and those it
    carried): calls a resume must not send again, since a batch given up may still answer and bill them."""
    if earlier is None:
        return {}
    keep = ("prompt_id", "document_id", "form", "group", "rule_id", "call_id", "failure", "no_answer", "route",
            "batch_id", "max_new_tokens")
    return {r["prompt_id"]: {k: r.get(k) for k in keep}
            for r in earlier.get("rows") or [] if r.get("no_answer") and r.get("prompt_id")}


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


def params_for(prompt, model, cache_ttl=None):
    """The request a prompt becomes: its user turn, and its system turn when it has one. With
    `cache_ttl` (D-610 cut 2) the system turn is sent as one text block of the same text carrying
    cache_control; the user turn is never split, so no byte of what the model reads moves."""
    system, user = turns(prompt)
    params = {"model": model, "messages": [{"role": "user", "content": user}]}
    if system is not None:
        params["system"] = (system if not cache_ttl else
                            [{"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": cache_ttl}}])
    return params


def request_for(prompt, model, cache_ttl=None):
    """The one request body both routes send: the single call's keyword arguments, and a batch
    request's `params`, the same dict (D-610 cut 1: the batch bytes are the single call's)."""
    return dict(params_for(prompt, model, cache_ttl), max_tokens=int(prompt["max_new_tokens"]))


def cache_marks(client, prompts, model, rule, route):
    """{system text: ttl or None} for the prompts of one group: a system turn is marked only when the
    provider counts it at or above the model's minimum cacheable length AND two or more prompts send
    it (a write read by no later call costs more than no cache). The count is the provider's
    count_tokens of the system turn with a one-character user turn, which it slightly overstates; a
    prefix the provider finds too short is simply not cached, with no error and no write."""
    repeats = {}
    for p in prompts:
        system, _ = turns(p)
        if system is not None:
            repeats[system] = repeats.get(system, 0) + 1
    marks, counted = {}, {}
    for system, n in repeats.items():
        if n < 2:
            marks[system], counted[text_digest(system)] = None, None
            continue
        tokens = int(client.messages.count_tokens(model=model, system=system,
                                                  messages=[{"role": "user", "content": "."}]).input_tokens)
        counted[text_digest(system)] = tokens
        marks[system] = rule["ttl"][route] if tokens >= rule["min_tokens"] else None
    return marks, counted


def mark_of(prompt, marks):
    system, _ = turns(prompt)
    return marks.get(system) if system is not None else None


def call_row(p, counted, worst):
    row = {k: p[k] for k in ("prompt_id", "document_id", "form", "group", "rule_id")}
    row.update(max_new_tokens=int(p["max_new_tokens"]), prompt_tokens=counted, worst_case_usd=round(worst, 6))
    return row


def settle(reply, p, row, worst, state, rates, ttl, route, model, key, context):
    """A reply that came back, on either route: its cost read from every usage field and put in
    place of the worst case already counted, or the worst case kept (usage unreadable, or a field
    this code cannot price, which also stops the run); its text saved through reply_records.write."""
    import reply_records
    allowance = int(p["max_new_tokens"])
    try:
        used = usage_cost(reply, rates, ttl=ttl, route=route)
    except Unpriceable as exc:
        used = None
        row.update(cost_usd=round(worst, 6), cost_is="worst case, the usage carries what is not priced here: %s" % exc)
        state["halt"] = ("%s on %s cannot be priced here, so the run stops (the call kept at its worst case)"
                         % (exc, p["prompt_id"]))
    else:
        if used is None:
            row.update(cost_usd=round(worst, 6), cost_is="worst case, the reply's usage could not be read")
        else:
            state["spent"] += used["cost_usd"] - worst
            row.update({k: v for k, v in used.items() if k != "cost_usd"}, cost_usd=round(used["cost_usd"], 6))
    text, stop_reason = read_reply(reply)
    call_id = reply_records.write(context, agent="CLOUD_REFERENCE_" + p["group"].upper(), backend="claude_api",
                                  model_id=model, payload=payload_text(p), payload_form="anthropic_messages_text",
                                  reply=text, ok=text is not None,
                                  error=None if text is not None else "reply not readable: " + str(stop_reason),
                                  decoding={"max_tokens": allowance, "other_settings": "provider_default"},
                                  phase="cloud_reference", doc_id=p["document_id"])
    row.update(call_id=call_id, failure=None if text is not None else "reply not readable", stop_reason=stop_reason,
               length_reached_allowance=stop_reason == "max_tokens", route=route, cache_ttl=ttl,
               reply=None if text is None else {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                                                "length_bytes": len(text.encode("utf-8"))})
    return row


def no_answer(p, row, why, cost_usd, cost_is, route, model, context):
    """A call with no answer, recorded as such and never sent again by this run (D-610 cut 1)."""
    import reply_records
    call_id = reply_records.write(context, agent="CLOUD_REFERENCE_" + p["group"].upper(), backend="claude_api",
                                  model_id=model, payload=payload_text(p), payload_form="anthropic_messages_text",
                                  reply=None, ok=False, error="no_answer: " + why, phase="cloud_reference",
                                  doc_id=p["document_id"])
    row.update(call_id=call_id, failure="no_answer: " + why, no_answer=True, length_reached_allowance=None,
               cost_usd=round(cost_usd, 6), cost_is=cost_is, route=route, seconds=None)
    return row


def call_one(client, p, model, counted, state, cap_usd, rates, key, context, clock, ttl=None):
    """One call on the single route, after the stop: (row, None), or (None, why) when its worst case
    would pass the cap.

    The call's worst case is added to `state["spent"]` BEFORE the request, so an interruption
    during it (a KeyboardInterrupt in messages.create) leaves it counted; it is taken back, and the
    reported cost put in its place, only on a completed reply whose usage was read and priced
    (`settle`). Its reply is saved through reply_records.write; its error is scrubbed of the key."""
    import reply_records
    worst = worst_case(counted, int(p["max_new_tokens"]), reserve_rates(rates, ttl))
    if not call_fits(state["spent"], worst, cap_usd):
        return None, ("cap: %.4f USD spent and %s's worst case %.4f USD would pass the %.2f USD cap"
                      % (state["spent"], p["prompt_id"], worst, cap_usd))
    row = call_row(p, counted, worst)
    started = clock()
    state["spent"] += worst
    try:
        reply = client.messages.create(**request_for(p, model, ttl))
    except Exception as exc:
        # A failed call reports no usage: its worst case stays counted, the safe side.
        error = scrub("%s: %s" % (type(exc).__name__, exc), key)
        call_id = reply_records.write(context, agent="CLOUD_REFERENCE_" + p["group"].upper(), backend="claude_api",
                                      model_id=model, payload=payload_text(p), payload_form="anthropic_messages_text",
                                      reply=None, ok=False, error=error, phase="cloud_reference", doc_id=p["document_id"])
        row.update(call_id=call_id, failure=error[:200], length_reached_allowance=None, cost_usd=round(worst, 6),
                   cost_is="worst case, the call failed", route="single", cache_ttl=ttl)
        row["seconds"] = round(clock() - started, 3)
        if type(exc).__name__ in STOP_ERRORS:
            state["halt"] = ("the provider refused the call (%s); the run stops cleanly, every reply so far recorded "
                             "(D-S106 item 3)" % type(exc).__name__)
        return row, None
    settle(reply, p, row, worst, state, rates, ttl, "single", model, key, context)
    row["seconds"] = round(clock() - started, 3)
    return row, None


def id_prefix(run_id):
    """The run-scoped custom-id prefix: `r`, the run id's last 12 characters, `_`. Every request of a
    run's batches starts with it, so a batch whose id was lost can be recognised from its results
    (`reconcile`)."""
    tail = str(run_id)[-12:]
    refuse(CUSTOM_ID.fullmatch(tail), "The run id cannot give a custom-id prefix")
    return "r%s_" % tail


def custom_ids(prompts, run_id):
    """{custom_id: prompt}: one id per prompt, the provider's form: the run's prefix and the prompt
    id's digest."""
    out = {}
    for p in prompts:
        cid = id_prefix(run_id) + hashlib.sha256(str(p["prompt_id"]).encode("utf-8")).hexdigest()[:40]
        refuse(CUSTOM_ID.fullmatch(cid) and cid not in out, "Two prompts share a custom id (%s)" % p["prompt_id"])
        out[cid] = p
    return out


def _attr(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def batch_group(client, group, mine, model, counted, state, cap_usd, rates, marks, key, context, clock, sleep,
                deadline_seconds, limits, out, max_calls=None):
    """One group on the batch route (D-610 cut 1). Every call's worst case at the batch rates is
    checked against the cap one by one and counted BEFORE the batch is sent; the batch id is written
    to the run folder as soon as the provider gives it. The batch is read every BATCH_POLL_SECONDS
    until it ends or `deadline_seconds` pass; past the deadline it is cancelled and read for up to
    BATCH_CANCEL_GRACE_SECONDS more. Results are joined by custom id: a succeeded result is settled
    as a single reply is; an errored, canceled or expired one (not billed, by the batch page) and a
    custom id with no result (its worst case kept) are each a recorded no_answer, never sent again.
    Returns (rows, why stopped or None)."""
    ids = custom_ids(mine, context.run_id)
    plan_rows, chosen, reserved, why = {}, [], 0.0, None
    for cid, p in ids.items():
        if max_calls is not None and state["calls"] >= max_calls:
            why = "chunk done: %d calls; resume with --resume-from this folder" % max_calls
            break
        ttl = mark_of(p, marks)
        worst = worst_case(counted[p["prompt_id"]], int(p["max_new_tokens"]), reserve_rates(rates, ttl))
        if not call_fits(state["spent"] + reserved, worst, cap_usd):
            why = ("cap: %.4f USD spent and reserved, and %s's worst case %.4f USD would pass the %.2f USD cap"
                   % (state["spent"] + reserved, p["prompt_id"], worst, cap_usd))
            break
        reserved += worst
        state["calls"] += 1
        plan_rows[cid] = (p, worst, ttl)
        chosen.append({"custom_id": cid, "params": request_for(p, model, ttl)})
    if not chosen:
        return [], why
    size = len(json.dumps(chosen).encode("utf-8"))
    refuse(len(chosen) <= limits["max_requests"] and size <= limits["max_bytes"],
           "The batch holds %d requests in %d bytes, over the provider's limit (%d, %d bytes)"
           % (len(chosen), size, limits["max_requests"], limits["max_bytes"]))
    record = {"group": group, "id": None, "requests": len(chosen), "bytes": size, "reserved_usd": round(reserved, 6),
              "deadline_seconds": deadline_seconds, "price_set": "batch", "status": "sending",
              "custom_id_prefix": id_prefix(context.run_id),
              "sent_after_utc": datetime.now(timezone.utc).isoformat()}
    state["batches"].append(record)
    started = clock()
    state["spent"] += reserved
    # Written BEFORE the request: an interruption during it leaves the record (prefix, count, time) on
    # disk, so `reconcile` can find a batch the provider holds whose id never came back.
    write_json(Path(out) / "batches.json", state["batches"])
    try:
        batch = client.messages.batches.create(requests=chosen)
    except BaseException as exc:
        # Nothing came back to say the batch exists, yet the provider may hold it: every call stays a
        # no_answer at its worst case, which a resume does not send again, and `reconcile` looks for it.
        error = scrub("%s: %s" % (type(exc).__name__, exc), key)
        lost = [no_answer(p, call_row(p, counted[p["prompt_id"]], w), "the batch request did not return (%s); "
                          "the provider may hold it" % type(exc).__name__, w, "worst case, the batch request did not "
                          "return", "batch", model, context) for p, w, _ in plan_rows.values()]
        if not isinstance(exc, Exception):
            record.update(status="create interrupted: the provider may hold this batch; run reconcile",
                          error=type(exc).__name__)
            write_json(Path(out) / "batches.json", state["batches"])
            state["interrupted_rows"] = lost
            raise
        record.update(status="create failed: the provider may hold this batch; run reconcile", error=error[:200])
        write_json(Path(out) / "batches.json", state["batches"])
        rows = lost
        if type(exc).__name__ in STOP_ERRORS:
            state["halt"] = "the provider refused the batch (%s); the run stops cleanly" % type(exc).__name__
        return rows, why or "the batch for %s was not accepted: %s" % (group, error[:200])
    record.update(id=str(_attr(batch, "id")), status=_attr(batch, "processing_status"))
    write_json(Path(out) / "batches.json", state["batches"])
    status, rows = record["status"], []
    try:
        status, cancelled, give_up, polls = record["status"], False, None, 0
        deadline = started + deadline_seconds
        while status != "ended":
            now = clock()
            if not cancelled and now >= deadline:
                cancelled = True
                record["cancelled_at_seconds"] = round(now - started, 3)
                try:
                    client.messages.batches.cancel(record["id"])
                except Exception as exc:
                    record["cancel_error"] = scrub(type(exc).__name__, key)
                give_up = now + BATCH_CANCEL_GRACE_SECONDS
                write_json(Path(out) / "batches.json", state["batches"])
            elif cancelled and now >= give_up:
                break
            sleep(BATCH_POLL_SECONDS)
            polls += 1
            try:
                status = _attr(client.messages.batches.retrieve(record["id"]), "processing_status")
            except Exception as exc:
                record["poll_errors"] = record.get("poll_errors", 0) + 1
                record["last_poll_error"] = scrub(type(exc).__name__, key)
        record.update(status=status, polls=polls, cancelled=cancelled, seconds=round(clock() - started, 3))
        results, read_error = {}, None
        if status == "ended":
            try:
                for item in client.messages.batches.results(record["id"]):
                    cid = _attr(item, "custom_id")
                    if cid in plan_rows and cid not in results:
                        results[cid] = _attr(item, "result")
            except Exception as exc:
                read_error = scrub(type(exc).__name__, key)
                record["results_error"] = read_error
        kinds = {}
        for cid, (p, worst, ttl) in plan_rows.items():
            row = call_row(p, counted[p["prompt_id"]], worst)
            result = results.get(cid)
            kind = _attr(result, "type") if result is not None else None
            kinds[kind or "missing"] = kinds.get(kind or "missing", 0) + 1
            if kind == "succeeded":
                settle(_attr(result, "message"), p, row, worst, state, rates, ttl, "batch", model, key, context)
                row["seconds"] = None
                rows.append(row)
            elif kind in ("errored", "canceled", "expired"):
                state["spent"] -= worst
                rows.append(no_answer(p, row, kind, 0.0, "not billed: a %s batch result is not billed (the provider's "
                                                         "batch-processing page)" % kind, "batch", model, context))
            else:
                rows.append(no_answer(p, row, "no result for its custom id" + ("" if status == "ended" else
                                      " (the batch had not ended)"), worst, "worst case, no result came back",
                                      "batch", model, context))
            rows[-1]["batch_id"] = record["id"]
        record["results"] = kinds
        write_json(Path(out) / "batches.json", state["batches"])
        if cancelled:
            why = why or ("batch %s passed its %d s deadline and was cancelled; %s" % (
                record["id"], deadline_seconds, "it ended" if status == "ended" else "it had not ended when it was given up"))
        elif read_error:
            why = why or "batch %s results could not be read (%s)" % (record["id"], read_error)
        return rows, why
    except BaseException as exc:
        # Interrupted after the provider took the batch (while it was read, or its results): the batch
        # is cancelled once, the cancel itself bounded by its own catch, and every planned call with no
        # row yet becomes a no_answer at its worst case, so neither the run nor a resume sends it again.
        if status != "ended":
            try:
                client.messages.batches.cancel(record["id"])
                record["cancelled_on_interrupt"] = True
            except BaseException as cancel_exc:
                record["cancel_error"] = scrub(type(cancel_exc).__name__, key)
        settled = {r["prompt_id"] for r in rows}
        lost = []
        for cid, (p, worst, ttl) in plan_rows.items():
            if p["prompt_id"] in settled:
                continue
            lost.append(no_answer(p, call_row(p, counted[p["prompt_id"]], worst), "the run was interrupted while the "
                                  "batch was followed (%s)" % type(exc).__name__, worst, "worst case, interrupted after "
                                  "the batch was sent", "batch", model, context))
            lost[-1]["batch_id"] = record["id"]
        record.update(status="interrupted while followed: %s" % type(exc).__name__)
        write_json(Path(out) / "batches.json", state["batches"])
        state["interrupted_rows"] = rows + lost
        raise


RECONCILE_FILE = "reconcile.json"
RECONCILE_SKEW_SECONDS = 300   # a batch created this long before the recorded send time still counts as a candidate


def _when(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _read_results(client, batch_id, prefix, rates):
    """(custom ids, {type: count}, billed USD at the rates) of an ended batch's results; reads only."""
    ids, kinds, billed = [], {}, 0.0
    for item in client.messages.batches.results(batch_id):
        ids.append(str(_attr(item, "custom_id")))
        result = _attr(item, "result")
        kind = _attr(result, "type") or "unknown"
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == "succeeded":
            try:
                used = usage_cost(_attr(result, "message"), rates, ttl="1h", route="batch")
            except Unpriceable:
                used = None
            billed += used["cost_usd"] if used else float("nan")
    return ids, kinds, billed


def reconcile(run_dir, client, *, limit=100):
    """The recovery path for a run's batches (D-610 cut 1): read-only on the provider (it lists,
    retrieves and reads results; it never sends, cancels or deletes). For a batch whose id never came
    back (its record in batches.json has none), the batches created since its recorded send time are
    listed, and one that has ended whose every result carries the run's custom-id prefix, in the
    recorded number, is that batch; one still running is named a candidate to read again later. For a
    batch given up before it ended, it is read again, and its results counted when it has ended.
    Appends what it found to reconcile.json in the run folder. The spend line is not changed: every
    call stays counted at its worst case there, the safe side; what the provider billed is recorded
    beside it for the lead."""
    run_dir = Path(run_dir)
    try:
        batches = json.loads((run_dir / "batches.json").read_text(encoding="utf-8"))
        rates = json.loads((run_dir / MEASUREMENT_FILE).read_text(encoding="utf-8"))["rates"]
    except (OSError, ValueError, KeyError, TypeError):
        raise Stop("The run folder has no readable batches.json and measurement with its rates")
    listed, out = None, []
    for rec in batches:
        prefix, entry = rec.get("custom_id_prefix"), {"group": rec.get("group"), "recorded_id": rec.get("id"),
                                                      "requests": rec.get("requests")}
        refuse(isinstance(prefix, str) and prefix, "A batch record has no custom-id prefix")
        if rec.get("id") is None:
            if listed is None:
                listed = list(client.messages.batches.list(limit=limit))
            since = _when(rec.get("sent_after_utc"))
            refuse(since is not None, "A batch record has no send time")
            matches, running = [], []
            for b in listed:
                created = _when(_attr(b, "created_at"))
                if created is None or (since - created).total_seconds() > RECONCILE_SKEW_SECONDS:
                    continue
                if _attr(b, "processing_status") != "ended":
                    running.append(str(_attr(b, "id")))
                    continue
                ids, kinds, billed = _read_results(client, _attr(b, "id"), prefix, rates)
                if ids and all(i.startswith(prefix) for i in ids) and len(ids) == rec.get("requests"):
                    matches.append({"id": str(_attr(b, "id")), "results": kinds, "billed_usd": round(billed, 6)})
            entry.update(found=matches, candidates_running=running,
                         outcome="found" if len(matches) == 1 else ("ambiguous" if matches else
                                                                    ("read again later" if running else "not found")))
        elif rec.get("status") != "ended":
            status = _attr(client.messages.batches.retrieve(rec["id"]), "processing_status")
            entry["status_now"] = status
            if status == "ended":
                ids, kinds, billed = _read_results(client, rec["id"], prefix, rates)
                entry.update(outcome="ended after it was given up", results=kinds, billed_usd=round(billed, 6),
                             all_ours=all(i.startswith(prefix) for i in ids))
            else:
                entry["outcome"] = "still running: read again later"
        else:
            entry["outcome"] = "ended within the run"
        out.append(entry)
    record = {"time_utc": datetime.now(timezone.utc).isoformat(), "batches": out,
              "spend": "unchanged: every call of these batches stays at its worst case in the spend line"}
    path = run_dir / RECONCILE_FILE
    try:
        earlier = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except ValueError:
        raise Stop("reconcile.json cannot be read; nothing is overwritten")
    write_json(path, earlier + [record])
    return record


def run(prompts_path, bar_path, items_path, answer_keys, out, *, cap_usd, credit_usd, prices, deprecation_checked,
        seckin_approved, groups=GROUP_ORDER, resume_from=None, max_calls=None, keys=None, client=None,
        list_models=None, clock=time.perf_counter, root=ROOT, runs_root=RUNS_ROOT, prices_path=PRICES_PATH,
        store=None, ledgers=None, for_seckin=None, gate_set=None, gate_held=None, gate_rebuild=None,
        route="single", batch_deadline_seconds=None, sleep=time.sleep, resend_no_answer=False):
    """The paid run. `route` is `single` (one request a call) or `batch` (D-610 cut 1: one Message
    Batch a group, the same request bodies, every worst case at the recorded batch rates, cancelled
    and recorded past `batch_deadline_seconds`, which the batch route requires and which must be
    below the provider's own expiry). A resume carries the earlier run's no_answer rows forward and
    sends none of those prompts again (a given-up batch may still bill them) unless `resend_no_answer`. With `gate_set` (the frozen claim set file) it is the gate's claim-set mode: B1's own
    prompts of one benchmark, every item of the claim set, no J1 bar, items or keys (those are None),
    every other guard the same; its kind is GATE_SCHEMA. `client`, `keys` and `list_models` are the SDK client (make_client), the
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
    refuse(route in ROUTES, "The route is single or batch")
    refuse(route == "single" or (isinstance(batch_deadline_seconds, (int, float)) and batch_deadline_seconds > 0),
           "The batch route needs its deadline (--batch-deadline-minutes)")
    refuse(route == "batch" or batch_deadline_seconds is None, "A batch deadline belongs to the batch route")
    out = run_folder(out, runs_root)
    store = spend_store(root) if store is None else Path(store)
    approval = check_approval(seckin_approved, Path(store).parent / FOR_SECKIN_NAME if for_seckin is None else for_seckin)
    if gate_set is None:
        value, bar = load(prompts_path, bar_path)
        chosen = selection(value, bar, items_path, answer_keys, "A", tuple(groups))
        kind, label, scope = SCHEMA, LABEL, {"half": "A", "reads": "J1's prompts file, half A; ids, counts, tokens "
                                                                     "and dollars here, the replies in the reply records"}
    else:
        refuse(bar_path is None and items_path is None and not answer_keys,
               "A gate claim-set run takes no J1 bar, items or keys")
        value = load_gate_prompts(prompts_path)
        chosen, benchmark, gate_digest = gate_selection(value, gate_set, tuple(groups))
        rebuilt = check_gate_prompts(prompts_path, gate_held, gate_rebuild)
        kind, label, scope = GATE_SCHEMA, GATE_LABEL, {
            "half": None, "set": "gate claim set", "gate_set_sha256": gate_digest, "benchmark": benchmark,
            "rebuilt": rebuilt,
            "reads": "B1's own prompts on the gate's claim set; ids, counts, tokens and dollars here, the replies in "
                     "the reply records"}
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
    rates, caching = route_rates(prices, route), cache_rule(prices)
    limits = batch_limits(prices) if route == "batch" else None
    if route == "batch":
        refuse(batch_deadline_seconds < limits["expiry_hours"] * 3600,
               "The batch deadline must be below the provider's %d-hour expiry" % limits["expiry_hours"])
    resume_digests = {"prompts_sha256": sha(prompts_path), "config_sha256": value.get("config_sha256")}
    if gate_set is not None:
        resume_digests["gate_set_sha256"] = scope["gate_set_sha256"]
    earlier = earlier_run(resume_from, measurement_file=MEASUREMENT_FILE, kind=kind, model=model, digests=resume_digests)
    allowances = {text_digest(payload_text(p)): int(p["max_new_tokens"]) for p in chosen}
    done_before = answered(resume_from, model=model, decoding=lambda r: r.get("decoding") == {
        "max_tokens": allowances.get((r.get("payload") or {}).get("sha256")), "other_settings": "provider_default"})
    carried_ids = {} if resend_no_answer else no_answer_before(earlier)
    spent_before = chain_spent(earlier)
    limit = spend_limit(cap_usd, credit_usd - spent_before)
    refuse(limit > 0, "The credit left after this chain's earlier runs (%.4f USD spent) is %.4f USD"
           % (spent_before, credit_usd - spent_before))
    if client is None:
        client = make_client(key)
    provider_record = model_record(client, model)
    context = RunContext(out, "cloud-reference-" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:12])
    chain = chain_runs(earlier)
    budget = open_run(store, context.run_id, limit, out.name, kind, lambda: check_cap(cap_usd, store, ledgers, kind=kind),
                      approval=approval, chain=chain)
    rows, skipped, counted, reused, carried = [], [], {}, [], []
    state = {"spent": 0.0, "stopped": None, "halt": None, "calls": 0, "batches": []}
    cache_counts = {}
    try:
        for group in groups:
            mine = []
            for p in [q for q in chosen if q["group"] == group]:
                if p["prompt_id"] in carried_ids and text_digest(payload_text(p)) not in done_before:
                    # A no_answer of the run resumed: not sent again, carried forward as it was recorded.
                    rows.append(dict(carried_ids[p["prompt_id"]], resumed_from=Path(resume_from).name, cost_usd=0.0,
                                     cost_is="a no_answer of the earlier run, carried forward and not sent again "
                                             "(its spend in the earlier run's line; --resend-no-answer sends it)",
                                     seconds=0.0))
                    carried.append(p["prompt_id"])
                    continue
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
                marks, cache_counts[group] = cache_marks(client, mine, model, caching, route)
                for p in mine:
                    counted[p["prompt_id"]] = int(client.messages.count_tokens(
                        **params_for(p, model, mark_of(p, marks))).input_tokens)
            except Exception as exc:
                state["stopped"] = "count_tokens failed in %s: %s" % (group, scrub("%s: %s" % (type(exc).__name__, exc), key))
                break
            group_worst = sum(worst_case(counted[p["prompt_id"]], int(p["max_new_tokens"]),
                                         reserve_rates(rates, mark_of(p, marks))) for p in mine)
            if not group_fits(state["spent"], group_worst, limit):
                skipped.append({"group": group, "worst_case_usd": round(group_worst, 4),
                                "spent_before_usd": round(state["spent"], 4)})
                state["stopped"] = ("cap: %s not started, its worst case %.4f USD after %.4f USD spent would pass the "
                                    "%.2f USD limit (the cap or the credit left, whichever is lower)"
                                    % (group, group_worst, state["spent"], limit))
                break
            if route == "batch":
                done, over = batch_group(client, group, mine, model, counted, state, limit, rates, marks, key, context,
                                         clock, sleep, batch_deadline_seconds, limits, out, max_calls)
                rows.extend(done)
                state["stopped"] = state["halt"] or over
                if state["stopped"]:
                    break
                continue
            for p in mine:
                if max_calls is not None and state["calls"] >= max_calls:
                    state["stopped"] = ("chunk done: %d calls; resume with --resume-from this folder" % max_calls)
                    break
                state["calls"] += 1
                row, over = call_one(client, p, model, counted[p["prompt_id"]], state, limit, rates, key, context,
                                     clock, mark_of(p, marks))
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
        rows.extend(state.pop("interrupted_rows", []))
        raise
    finally:
        measurement = dict(scope, **{
            "schema": MEASUREMENT_SCHEMA, "kind": kind, "label": label, "prompts_sha256": sha(prompts_path),
            "config_sha256": value.get("config_sha256"), "groups": list(groups), "rows": rows,
            "prompts": len(chosen), "sent": len(rows) - len(reused) - len(carried), "answered": len(rows),
            "carried_no_answer": len(carried), "resend_no_answer": bool(resend_no_answer), "complete": state["stopped"] is None and len(rows) == len(chosen),
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
            "route": route, "rates": rates, "batches": state["batches"], "batch_deadline_seconds": batch_deadline_seconds,
            "cache": {"rule": caching, "system_prefix_tokens": cache_counts},
            "max_retries": 0, "count_margin": COUNT_MARGIN, "seconds": round(sum(r.get("seconds") or 0 for r in rows), 3), "run_id": context.run_id})
        # The spend line first (small, the one the next run's cap reads), then the measurement; each in
        # its own try, so one failing never loses the other, and the first failure is raised after both.
        failures = []
        try:
            append_store(store, close_line(context.run_id, state["spent"], run_folder=out.name, model=model,
                                           complete=measurement["complete"], stopped=state["stopped"],
                                           seckin_approved=approval, key_source=key_source, kind=kind,
                                           route=route, rates=rates,
                                           batch_ids=[b["id"] for b in state["batches"]],
                                           batch_custom_id_prefixes=sorted({b["custom_id_prefix"]
                                                                            for b in state["batches"]})))
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
            % (measurement.get("label") or LABEL, measurement["model"]["resolved"], measurement["model"]["status"], measurement["sent"],
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


def measured_output(path):
    """{group: output tokens per call of form b1} from a paid run's measurement, and its source; None
    when no path is given. Only completed calls with a reported output count."""
    if path is None:
        return None
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {"source": "%s (%s, run %s)" % (Path(path).parent.name, m.get("kind"), m.get("run_id"))}
    for g in GROUP_ORDER:
        tokens = [r["output_tokens"] for r in m.get("rows") or []
                  if r.get("group") == g and r.get("form") == B1_FORM and isinstance(r.get("output_tokens"), int)]
        refuse(tokens, "The measurement holds no completed b1 call of group %s" % g)
        out[g] = sum(tokens) / len(tokens)
    return out


def prices_from(args):
    return {"input_per_mtok": args.price_input_per_mtok, "output_per_mtok": args.price_output_per_mtok,
            "source": args.price_source}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_reference.py", allow_abbrev=False, description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run", "read"):
        p = sub.add_parser(name, allow_abbrev=False)
        p.add_argument("--prompts", required=True)
        p.add_argument("--bar", required=name == "read", help="J1's j1_bar.json")
        p.add_argument("--items", required=name == "read", help="the pinned g1_bar_items.json (C's universe)")
        p.add_argument("--key", action="append", required=name == "read",
                       help="an adapter answer key, read by the scorer only, for C's universe (repeat)")
        if name in ("plan", "run"):
            p.add_argument("--gate-set", default=None,
                           help="the gate's claim-set mode: the frozen claim_set_ids.json (gate_score.CLAIM_SET_SHA256), "
                                "with B1's own prompts of one benchmark, in place of --bar, --items and --key")
            p.add_argument("--gate-held", default=None,
                           help="the gate mode: role B's held build the prompts file is rebuilt from, byte for byte")
            p.add_argument("--measured-output", default=None,
                           help="plan in the gate mode: a measurement whose output tokens per call per group give an "
                                "expected figure beside the worst case (labelled an estimate)")
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
            p.add_argument("--route", choices=list(ROUTES), default="single",
                           help="single (one request a call) or batch (one Message Batch a group, D-610 cut 1)")
            p.add_argument("--resend-no-answer", action="store_true",
                           help="with --resume-from: send again the prompts the earlier run recorded as no_answer "
                                "(by default they are carried forward, never resent)")
            p.add_argument("--batch-deadline-minutes", type=float, default=None,
                           help="the batch route: a batch still running this long after it was sent is cancelled")
        if name == "read":
            p.add_argument("--run", required=True)
            p.add_argument("--out", required=True)
            p.add_argument("--tag", required=True)
            p.add_argument("--steering", action="store_true",
                           help="read a subscription steering check, its figures labelled steering only (D-S104)")
    r = sub.add_parser("reconcile", allow_abbrev=False,
                       help="read a run's batches again (lost ids, given-up batches); read-only on the provider")
    r.add_argument("--run", required=True, help="the run folder holding batches.json")
    g = sub.add_parser("gate-prompts", allow_abbrev=False,
                       help="build B1's own prompts for one held gate build (no provider call)")
    g.add_argument("--held", required=True, help="role B's held build folder (bundles and items.json)")
    g.add_argument("--out", required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "gate-prompts":
        try:
            print(json.dumps(build_gate_prompts(args.held, args.out), indent=1))
        except Stop as exc:
            print("cloud_reference stopped: %s" % exc, file=sys.stderr)
            return 3
        return 0
    if args.command == "reconcile":
        try:
            clear_environment()
            key, _source = resolve_key()
            refuse(bool(key), "No ANTHROPIC_API_KEY in the credential file found; set SHIMMER_CONFIG_PATH")
            found = reconcile(args.run, make_client(key))
        except Stop as exc:
            print("cloud_reference stopped: %s" % exc, file=sys.stderr)
            return 3
        print(json.dumps([{k: b.get(k) for k in ("group", "recorded_id", "outcome")} for b in found["batches"]], indent=1))
        return 0
    gate = getattr(args, "gate_set", None)
    if args.command in ("plan", "run") and (gate is None) != bool(args.bar and args.items and args.key):
        parser.error("give --gate-set alone, or --bar, --items and --key without it")
    if gate is not None and (args.bar or args.items or args.key):
        parser.error("--gate-set takes no --bar, --items or --key")
    if args.command in ("plan", "run") and gate is None and (args.measured_output or args.gate_held):
        parser.error("--measured-output and --gate-held belong to the gate mode (--gate-set)")
    if args.command == "plan" and gate is not None and (args.price_input_per_mtok or args.price_output_per_mtok
                                                        or args.price_source):
        parser.error("the gate plan reads the recorded prices; it takes no --price-*")
    if args.command == "run" and args.measured_output:
        parser.error("--measured-output belongs to plan")
    try:
        if args.command == "plan" and gate is not None:
            print(json.dumps(gate_plan(args.prompts, gate, tuple(args.group or GROUP_ORDER),
                                       measured=measured_output(args.measured_output), held=args.gate_held),
                             indent=1, default=json_default))
        elif args.command == "plan":
            value, bar = load(args.prompts, args.bar)
            prices = prices_from(args) if args.price_input_per_mtok and args.price_output_per_mtok else None
            print(json.dumps(plan(selection(value, bar, args.items, args.key, "A", tuple(args.group or GROUP_ORDER)),
                                  prices), indent=1))
        elif args.command == "run":
            print(summary_line(run(args.prompts, args.bar, args.items, args.key, args.out, cap_usd=args.cap_usd,
                                   credit_usd=args.credit_usd, seckin_approved=args.seckin_approved,
                                   resume_from=args.resume_from, max_calls=args.max_calls, prices=prices_from(args),
                                   deprecation_checked=args.deprecation_checked, gate_set=gate, gate_held=args.gate_held,
                                   groups=tuple(args.group or GROUP_ORDER), route=args.route,
                                   batch_deadline_seconds=None if args.batch_deadline_minutes is None
                                   else args.batch_deadline_minutes * 60, resend_no_answer=args.resend_no_answer)))
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
