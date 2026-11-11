#!/usr/bin/env python3
"""The cloud reference on a benchmark build, in bare_model.py's own layout (D-S102 item 2, D-388).

Reference: a paid cloud model on the same items. Not Shimmer's performance.

B1's own run loop (`bare_model._run`), unchanged, with the paid model in place of the local one: one
call per item, B1's two turns rendered by bare_model's own functions (the system turn as the system
prompt, the user turn as the one user message), B1's own output allowance (`PRODUCTION_MAX_TOKENS`),
its own reply parsing (`parse_reply`) and its own label files. So each document's replies land in
`<out>/<document id>/labels/<item id>.json` and `b1_summary.json`, which the benchmark adapters read
unchanged (`label-reference`, under the arm name REFERENCE).

    py -3.12 -X utf8 benchmark/baselines/cloud_reference_b1.py run --build <build folder>
        --items-sha256 <items.json's> --parts-sha256 <parts.json's> --out <new folder>
        --cap-usd <USD> --price-input-per-mtok <row> --price-output-per-mtok <row> --price-source "<page, date>"
        --deprecation-checked "<url>, <YYYY-MM-DD>, not deprecated" --seckin-approved "<FOR_SECKIN entry heading time>" --credit-usd <USD left>
        [--opening <HELDOUT_OPENINGS row>] [--budget-left-usd <USD> --spend-file <path> --for-seckin <copy>]
        [--resume-from <earlier run folder>] [--max-calls <N>]

The build must be one the allowed list names (`cloud_reference_builds.json`: role B's build record,
its items and parts digests, its side and the digest of every bundle file); its side is read from
role B's own build record (parts.json's declared side and every document's), never given on the
command line; a holdout build runs only under a HELDOUT_OPENINGS row read at HEAD whose first cell
is the opening exactly and which writes the build's full items digest (D-401 items 8 and 9).

Which sets may go (D-388): the gate set (development since D-S100), PUBHEALTH's development part,
its holdout only under a committed HELDOUT_OPENINGS row; the causal probe only from role C's session
(below). Never the fresh set, sealed test material or a key. Before every paid run Seckin's "evet"
on a FOR_SECKIN entry (D-S106 item 2): the lead passes its heading time in `--seckin-approved` only after it; the key is only the one
`agent_wrapper.load_api_keys` resolves, his own (D-S106 item 1).

Role C's form (the causal probe, whose items never pass the lead's side): role C runs this command
in its own session from its sealed build, with `--budget-left-usd` (the figure the lead gives, from
the ledgers and the spend store) in place of reading the loop's ledgers, which its side does not
hold, `--spend-file <path>`, a file of its own it hands back, and `--for-seckin <copy>`, the copy of
the FOR_SECKIN entry with its evet line the lead hands it; it runs only under the role C marker
(`SHIMMER_ROLE=C`), where the lead's form refuses. The lead drops the handed-back file into
`docs/loop/private/cloud_reference_handed_back/` and appends it with
`tools/loop/cloud_reference_spend.py append-handed-back`; until then the lead's next paid run and
instance launch refuse (D-401 item 11). Nothing but counts and timings leaves role C.

Every rule of `cloud_reference.py run` holds: the build pinned by the digests role B recorded; every
rendered prompt scanned for key-shaped strings and the key itself; the registry's model resolved
live (gone, ambiguous or an unreadable list stops it); its record read for a deprecation field; the
prices equal to the recorded row; a document starts only when its whole worst case fits under the
cap, and each call is checked again; the worst case counted before each request; max_retries 0;
cache writes refused; the measurement and the spend line written on any exit. A provider refusal
that going on would only repeat (a 4xx, a credit balance run out among them) stops the run cleanly at
once, every reply so far recorded; `--resume-from` an earlier folder skips the documents it finished,
so the work runs in resumable chunks (D-S106 item 3).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines"),
              str(ROOT / "benchmark" / "adapters")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bare_model  # noqa: E402
import cloud_reference as cr  # noqa: E402

SCHEMA = "cloud-reference-b1-v1"
ROLE_C_KIND = "cloud-reference-b1-role-c"
ROLE_C_RUN_ID = re.compile(r"role-c-[0-9a-f]{12}")
MEASUREMENT_FILE = "cloud_reference_b1.json"
LABEL = "Reference: a paid cloud model on the same items. Not Shimmer's performance."
SIDES = ("development", "holdout")
OPENINGS_PATH = "docs/loop/HELDOUT_OPENINGS.md"   # read at HEAD (git show), never the working copy
BUILDS_PATH = Path(__file__).resolve().with_name("cloud_reference_builds.json")
DIGEST = re.compile(r"\b[0-9a-f]{64}\b")
ATTENTION = {"provider": "anthropic_api", "local_attention": "not applicable"}
# Errors that do not pass by going on (D-S106 item 3: a credit balance run out is a 400): the run
# stops cleanly at the first one, every reply so far recorded, and can be resumed.
STOP_ERRORS = ("BadRequestError", "AuthenticationError", "PermissionDeniedError", "NotFoundError")


class CapReached(bare_model.SetupError):
    """A call whose worst case would pass the cap: the run stops before sending it. It is a
    bare_model SetupError, so bare_model._run re-raises it instead of recording a failed call and
    going on to the next item."""


def bundle_files(build, docs):
    """{path relative to the build: sha256} of every file of every document's bundle the run reads."""
    out = {}
    for d in docs:
        for path in sorted((Path(build) / d).rglob("*")):
            if path.is_file():
                out[path.relative_to(build).as_posix()] = cr.sha(path)
    return out


def allowed_build(items_sha256, parts_sha256, builds_path=BUILDS_PATH):
    """The allowed list's entry for this build, or a refusal (D-401 item 8)."""
    try:
        listed = json.loads(Path(builds_path).read_text(encoding="utf-8")).get("builds") or []
    except (OSError, ValueError):
        raise cr.Stop("The allowed build list cannot be read")
    found = [b for b in listed if b.get("items_sha256") == items_sha256 and b.get("parts_sha256") == parts_sha256]
    cr.refuse(len(found) == 1, "This build is not on the allowed list (%s)" % Path(builds_path).name)
    entry = found[0]
    cr.refuse(entry.get("side") in SIDES and isinstance(entry.get("files"), dict) and entry["files"]
              and entry.get("role_b_record"), "The allowed list's entry for this build is incomplete")
    return entry


def build_side(parts):
    """The side role B's build record gives: parts.json's declared side, and every document's."""
    sides = {d.get("side") for d in parts.get("documents") or []}
    declared = parts.get("declared_side")
    cr.refuse(len(sides) == 1 and (declared is None or {declared} == sides),
              "Role B's build record gives no single side for this build")
    side = sides.pop()
    cr.refuse(side in SIDES, "Role B's build record gives an unknown side")
    return side


def build_files(build, items_sha256, parts_sha256, builds_path=BUILDS_PATH):
    """The build's bundles, item table, side and allowed-list entry, refused unless items.json and
    parts.json are the files role B recorded, the build is on the allowed list with that side, and
    every bundle file is the one the list records (D-401 items 8 and 9)."""
    build = Path(build)
    cr.refuse(cr.sha(build / "items.json") == items_sha256, "items.json is not the file role B recorded")
    cr.refuse(cr.sha(build / "parts.json") == parts_sha256, "parts.json is not the file role B recorded")
    entry = allowed_build(items_sha256, parts_sha256, builds_path)
    parts = json.loads((build / "parts.json").read_text(encoding="utf-8"))
    side = build_side(parts)
    cr.refuse(side == entry["side"], "Role B's build record gives side %s; the allowed list says %s" % (side, entry["side"]))
    table = json.loads((build / "items.json").read_text(encoding="utf-8"))
    rows = table.get("items") if isinstance(table, dict) else table
    docs = sorted({str(r["document_id"]) for r in rows or []})
    cr.refuse(docs, "items.json lists no document")
    missing = [d for d in docs if not (build / d / "context").is_dir()]
    cr.refuse(not missing, "A document in items.json has no bundle: %s" % ", ".join(missing[:3]))
    recorded = {d.get("document_id") for d in parts.get("documents") or []}
    cr.refuse(set(docs) <= recorded, "A document in items.json is not in role B's build record")
    found = bundle_files(build, docs)
    differ = sorted(k for k in set(found) | set(entry["files"]) if found.get(k) != entry["files"].get(k))
    cr.refuse(not differ, "A bundle file is not the one the allowed list records: %s" % ", ".join(differ[:3]))
    return build / "items.json", [build / d for d in docs], side, entry


def build_entry(build, name, role_b_record):
    """The allowed-list entry for a build as it stands: its digests, the side role B's record gives
    and every bundle file's digest. Printed for the lead to check and commit; never written here."""
    build = Path(build)
    parts = json.loads((build / "parts.json").read_text(encoding="utf-8"))
    table = json.loads((build / "items.json").read_text(encoding="utf-8"))
    rows = table.get("items") if isinstance(table, dict) else table
    docs = sorted({str(r["document_id"]) for r in rows or []})
    cr.refuse(docs, "items.json lists no document")
    return {"name": name, "role_b_record": role_b_record, "side": build_side(parts),
            "items_sha256": cr.sha(build / "items.json"), "parts_sha256": cr.sha(build / "parts.json"),
            "files": bundle_files(build, docs)}


def open_role_c(cap_usd, seckin_approved, *, resumes=(), root=cr.ROOT, store=None, ledgers=None, now=None):
    """The lead's side of role C's form (D-401 item 11): under the store's lock, the cap held to the
    total budget and Seckin's yes checked once, then an intent line for role C's run, holding its
    cap as running until the lead appends the spend file role C hands back (whose close line
    names the same run id). Returns what the lead hands role C: the run id and the budget figure."""
    cr.clear_environment()
    cr.check_role(lead_side=True)
    store = cr.spend_store(root) if store is None else Path(store)
    approval = cr.check_approval(seckin_approved, store.parent / cr.FOR_SECKIN_NAME)
    run_id = "role-c-" + hashlib.sha256(("%s %s" % (time.time(), os.getpid())).encode()).hexdigest()[:12]
    budget = cr.open_run(store, run_id, cap_usd, None, ROLE_C_KIND,
                         lambda: cr.check_cap(cap_usd, store, ledgers, now, kind=ROLE_C_KIND), approval=approval, chain=list(resumes))
    # Role C is handed the intent's own cap as its budget figure, never the whole budget left, so its
    # run can never pass what the store holds for it (D-401 item 11).
    return {"role_c_run_id": run_id, "cap_usd": cap_usd, "budget_left_usd": cap_usd,
            "total_left_after_usd": round(budget["left_usd"] - cap_usd, 6),
            "seckin_approved": approval["heading"]}


def committed_openings(root=cr.ROOT):
    """HELDOUT_OPENINGS.md as committed at HEAD, never the working copy (D-401 item 8)."""
    import subprocess
    try:
        done = subprocess.run(["git", "-C", str(root), "show", "HEAD:" + OPENINGS_PATH], capture_output=True,
                              text=True, encoding="utf-8", timeout=30,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        raise cr.Stop("HELDOUT_OPENINGS.md cannot be read at HEAD")
    cr.refuse(done.returncode == 0, "HELDOUT_OPENINGS.md is not committed at HEAD")
    return done.stdout


def rendered(bundle, items_path):
    """(document id, [(item, system, user)]) exactly as bare_model._run renders them."""
    import python_only
    from common import prompt as b1_prompt
    spec = bare_model.load_prompt()
    data = python_only.load_bundle(bundle)
    cr.refuse(len(data["targets"]) == 1, "A bundle names exactly one document under review")
    doc = data["targets"][0]
    items = bare_model.load_items(items_path, doc["id"])
    conventions = b1_prompt.conventions_from_bundle(bundle)
    reference = b1_prompt.reference_from_bundle(bundle)
    out = []
    for i in items:
        key = str(i["benchmark"]).lower()
        cr.refuse(key in spec["benchmarks"], "No B1 prompt for benchmark %s" % key)
        out.append((i, bare_model.render_system(spec, key),
                    bare_model.render_user(spec, key, document=doc["text"], conventions=conventions, item=i,
                                           reference=reference)))
    return doc["id"], out


def check_side(side, opening, items_sha256, openings):
    """A holdout build reads only under the committed HELDOUT_OPENINGS row whose first cell is the
    opening exactly and which writes this build's full items digest. `openings()` gives the text."""
    cr.refuse(side in SIDES, "The side is development or holdout")
    if side == "development":
        cr.refuse(opening is None, "A development build takes no opening")
        return None
    cr.refuse(isinstance(opening, str) and opening.strip(), "A holdout build needs its HELDOUT_OPENINGS row (--opening)")
    rows = []
    for line in openings().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == opening.strip():
            rows.append(line)
    cr.refuse(len(rows) == 1, "No single committed HELDOUT_OPENINGS row %s" % opening)
    cr.refuse(items_sha256 in DIGEST.findall(rows[0]), "The opening's row does not write this build's items digest")
    return rows[0]


class ChunkDone(bare_model.SetupError):
    """The chunk's call count is reached: the run stops cleanly, to be resumed."""


class ProviderStop(bare_model.SetupError):
    """A provider refusal that going on would only repeat (a 4xx: no credit, no access): stop."""


class AnthropicBackend:
    """The backend bare_model._run takes (prepare, count_prompt, max_context, generate), on the paid
    model. Each generate is held to the cap and its worst case counted before the request."""

    def __init__(self, client, model, prices, state, cap_usd, key, record, max_calls=None, earlier=None):
        self.client, self.model, self.prices, self.state = client, model, prices, state
        self.cap_usd, self.key, self.record, self.max_calls = cap_usd, key, record, max_calls
        # {payload sha256: reply text} an earlier run of this build recorded (D-S106 item 3).
        self.earlier = earlier or {}
        self.decoding = {"status": "provider_default", "source": "Anthropic Messages API: model, max_tokens, "
                         "system and one user message, nothing else", "kwargs": {}}
        self.decoding["sha256"] = hashlib.sha256(json.dumps(self.decoding, sort_keys=True).encode()).hexdigest()

    def params(self, system, user):
        p = {"model": self.model, "messages": [{"role": "user", "content": user}]}
        if system:
            p["system"] = system
        return p

    def prepare(self):
        return {"model_id": self.model, "digest": "api:" + self.model, "decoding": self.decoding,
                "attention": ATTENTION, "checkpoint": {"checkpoint": "api", "provider_record": self.record}}

    def count_prompt(self, system, user):
        return int(self.client.messages.count_tokens(**self.params(system, user)).input_tokens)

    def max_context(self):
        return int(self.record.get("max_input_tokens") or 1_000_000)

    def answered_before(self, system, user):
        return cr.text_digest((system + "\n\n" if system else "") + user) in self.earlier

    def generate(self, system, user, max_new_tokens):
        if self.state["halt"]:
            # A cache-write halt stops at the next call, not at the document's end (D-401 item 12).
            raise ProviderStop(self.state["halt"])
        payload = (system + "\n\n" if system else "") + user
        text = self.earlier.get(cr.text_digest(payload))
        if text is not None:
            # Answered by the earlier run: its reply is used again and nothing is sent (D-S106 item 3).
            self.state["reused"] += 1
            return {"text": text, "payload": payload, "form": "anthropic_messages_text", "output_tokens": None,
                    "attention": ATTENTION, "stop_reason": "answered_by_the_earlier_run"}
        if self.max_calls is not None and self.state["calls"] >= self.max_calls:
            raise ChunkDone("chunk done: %d calls; resume with --resume-from this folder" % self.max_calls)
        counted = self.count_prompt(system, user)
        worst = cr.worst_case(counted, max_new_tokens, self.prices)
        if not cr.call_fits(self.state["spent"], worst, self.cap_usd):
            raise CapReached("cap: %.4f USD spent and the next call's worst case %.4f USD would pass the %.2f USD cap"
                             % (self.state["spent"], worst, self.cap_usd))
        self.state["spent"] += worst
        self.state["calls"] += 1
        try:
            reply = self.client.messages.create(max_tokens=max_new_tokens, **self.params(system, user))
        except Exception as exc:
            self.state["errors"].append(cr.scrub("%s: %s" % (type(exc).__name__, exc), self.key)[:200])
            if type(exc).__name__ in STOP_ERRORS:
                raise ProviderStop("the provider refused the call (%s); the run stops cleanly and can be resumed"
                                   % type(exc).__name__)
            raise RuntimeError("the provider call failed")  # bare_model records the class only
        used = cr.usage_tokens(reply)
        if used is not None and not used["cache_write"]:
            self.state["spent"] += cr.cost(used["input"], used["output"], self.prices) - worst
            self.state["input_tokens"] += used["input"]
            self.state["output_tokens"] += used["output"]
        elif used is not None:
            self.state["halt"] = "usage reports cache-write tokens; they are not priced here, so the run stops"
        text, stop = cr.read_reply(reply)
        return {"text": text, "payload": (system + "\n\n" if system else "") + user, "form": "anthropic_messages_text",
                "output_tokens": used["output"] if used else None, "attention": ATTENTION, "stop_reason": stop}


def earlier_replies(resume_from, model, decoding):
    """{payload sha256: reply text} of the calls an earlier run answered (cr.answered)."""
    return {digest: record["reply"]["text"]
            for digest, (_path, record) in cr.answered(resume_from, model=model, decoding=decoding).items()}


def output_folder(out, runs_root=cr.RUNS_ROOT):
    """A new, empty folder; inside the repository only under output/cloud_reference/."""
    out = Path(out).resolve()
    if out.is_relative_to(cr.ROOT):
        cr.refuse(out.parent == Path(runs_root).resolve(), "Inside the repository the folder must be output/cloud_reference/<name>")
    cr.refuse(not out.exists() or not any(out.iterdir()), "This folder is not empty; a new run takes a new folder")
    return out


def run(build, items_sha256, parts_sha256, out, *, cap_usd, credit_usd, prices, deprecation_checked, seckin_approved,
        opening=None, budget_left_usd=None, spend_file=None, for_seckin=None, role_c_run_id=None, resume_from=None,
        max_calls=None,
        keys=None, client=None, list_models=None, root=cr.ROOT,
        runs_root=cr.RUNS_ROOT, prices_path=cr.PRICES_PATH, store=None, ledgers=None, openings=None,
        builds_path=BUILDS_PATH, clock=time.perf_counter):
    cr.clear_environment()
    role_c = budget_left_usd is not None
    cr.check_role(lead_side=not role_c)
    cr.refuse(isinstance(credit_usd, (int, float)) and credit_usd > 0, "The API credit left is required (--credit-usd)")
    cr.refuse(max_calls is None or (isinstance(max_calls, int) and max_calls > 0), "--max-calls is a positive count")
    cr.refuse(isinstance(prices, dict) and prices.get("input_per_mtok", 0) > 0 and prices.get("output_per_mtok", 0) > 0
              and prices.get("source"), "Prices per million tokens and their source (page and date) are required")
    cr.refuse(isinstance(deprecation_checked, str) and cr.DEPRECATION_FORM.fullmatch(deprecation_checked.strip()),
              'The deprecations page reading is required in the form "<url>, <YYYY-MM-DD>, not deprecated"')
    out = output_folder(out, runs_root)
    items_path, bundles, side, allowed = build_files(build, items_sha256, parts_sha256, builds_path)
    opening_row = check_side(side, opening, items_sha256, openings or (lambda: committed_openings(root)))
    if role_c:
        # Role C's form: the lead's figure stands in for the ledgers its side does not hold.
        cr.refuse(spend_file is not None, "--budget-left-usd goes with --spend-file, the file handed back")
        cr.refuse(isinstance(budget_left_usd, (int, float)) and cap_usd <= budget_left_usd + 1e-9,
                  "The cap %.2f USD passes the budget left the lead gave (%s USD)" % (cap_usd, budget_left_usd))
        store_path = Path(spend_file)
        cr.refuse(not store_path.exists(), "The spend file to hand back must be new")
        # Role C's form never runs where the lead's store is reachable: that is the lead's checkout
        # (D-401 item 11).
        try:
            lead_store = cr.spend.store_path(root)
        except cr.spend.SpendStoreError:
            lead_store = None
        cr.refuse(lead_store is None or not lead_store.exists(),
                  "Role C's form refuses in the lead's checkout (the lead's spend store is reachable from here)")
        cr.refuse(isinstance(role_c_run_id, str) and ROLE_C_RUN_ID.fullmatch(role_c_run_id),
                  "Role C's form needs --role-c-run-id, the id the lead's open-role-c intent gave")
        # Role C holds no FOR_SECKIN.md: the lead hands it a copy of the entry with the evet line.
        cr.refuse(for_seckin is not None, "Role C's form needs --for-seckin, the copy of the entry the lead hands it")
        approval = dict(cr.check_approval(seckin_approved, for_seckin), copy="a copy handed to role C by the lead")
    else:
        cr.refuse(spend_file is None and for_seckin is None,
                  "--spend-file and --for-seckin are role C's form only")
        store_path = cr.spend_store(root) if store is None else Path(store)
        approval = cr.check_approval(seckin_approved, store_path.parent / cr.FOR_SECKIN_NAME)
    plans = [rendered(b, items_path) for b in bundles]
    if keys is None:
        key, key_source = cr.resolve_key()   # Seckin's own key, the one resolver (D-S106 item 1)
        keys = {"ANTHROPIC_API_KEY": key}
    else:
        key, key_source = keys.get("ANTHROPIC_API_KEY"), "given by a proof"
    cr.refuse(bool(key), "No ANTHROPIC_API_KEY in the credential file found; set SHIMMER_CONFIG_PATH")
    cr.scan([{"prompt_id": "%s/%s" % (doc, i["item_id"]), "system": s, "user": u} for doc, rows in plans for i, s, u in rows],
            key)
    if list_models is None:
        list_models = cr.provider_models
    configured = cr.seat_model(root)
    status, model = cr.resolve(configured, list_models("claude_api", keys))
    prices = cr.check_prices(prices, model, prices_path)
    earlier = cr.earlier_run(resume_from, measurement_file=MEASUREMENT_FILE, kind=SCHEMA, model=model,
                             digests={"build.items_sha256": items_sha256, "build.parts_sha256": parts_sha256})
    spent_before = cr.chain_spent(earlier)
    limit = cr.spend_limit(cap_usd, credit_usd - spent_before)
    cr.refuse(limit > 0, "The credit left after this chain's earlier runs (%.4f USD spent) is %.4f USD"
              % (spent_before, credit_usd - spent_before))
    if client is None:
        client = cr.make_client(key)
    provider_record = cr.model_record(client, model)
    allowance = int(bare_model.pipeline_literal("PRODUCTION_MAX_TOKENS", Path(root) / "scripts" / "pipeline.py"))
    state = {"spent": 0.0, "calls": 0, "input_tokens": 0, "output_tokens": 0, "errors": [], "halt": None, "reused": 0}
    backend = AnthropicBackend(client, model, prices, state, limit, key, provider_record, max_calls)
    import decoding_policy
    sent_decoding = json.loads(json.dumps(dict(decoding_policy.usage_fields(backend.decoding),
                                               max_new_tokens=allowance)))
    backend.earlier = earlier_replies(resume_from, model, lambda r: r.get("decoding") == sent_decoding)
    reader = {"agent": "CLOUD_REFERENCE", "agent_source": "argument", "backend": "claude_api", "model_id": model,
              "model_mode": "api", "checkpoint": "api", "role": "reference", "decoding": backend.decoding,
              "max_new_tokens": allowance, "max_new_tokens_source": "pipeline PRODUCTION_MAX_TOKENS", "sources": {},
              "attention": ATTENTION}
    expected = {"model_id": model, "digest": "api:" + model, "decoding": backend.decoding}
    documents, stopped, started = [], None, clock()
    run_id = (role_c_run_id if role_c else
              "cloud-reference-b1-" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:12])
    chain = cr.chain_runs(earlier)
    if role_c:
        budget = {"rule": "the lead's figure of what is left of the total budget (role C's form)",
                  "left_usd": budget_left_usd}
    else:
        budget = cr.open_run(store_path, run_id, limit, out.name, SCHEMA,
                             lambda: cr.check_cap(cap_usd, store_path, ledgers, kind=SCHEMA), approval=approval, chain=chain)
    try:
        for doc_id, rows in plans:
            # A prompt an earlier run answered (keyed by its digest) costs nothing and is not sent; the
            # document's whole label set and summary are written again from those replies.
            todo = [(s_, u_) for _, s_, u_ in rows if not backend.answered_before(s_, u_)]
            worst = sum(cr.worst_case(backend.count_prompt(s, u), allowance, prices) for s, u in todo)
            if not cr.group_fits(state["spent"], worst, limit):
                stopped = ("cap: document %s not started, its worst case %.4f USD after %.4f USD spent would pass the "
                           "%.2f USD limit (the cap or the credit left, whichever is lower)"
                           % (doc_id, worst, state["spent"], limit))
                break
            context = bare_model.RunContext(out / doc_id, run_id)
            try:
                summary = bare_model._run(Path(build) / doc_id, items_path, out / doc_id, backend=backend, reader=reader,
                                          context=context, expected=expected)
                documents.append({"document_id": doc_id, "items": len(rows), "answered_before": len(rows) - len(todo),
                                  "benchmarks": summary.get("benchmarks")})
            except (CapReached, ProviderStop, ChunkDone) as exc:
                stopped = str(exc)
                break
            if state["halt"]:
                stopped = state["halt"]
                break
    except BaseException as exc:
        stopped = stopped or "interrupted: %s" % type(exc).__name__
        raise
    finally:
        measurement = {"schema": SCHEMA, "kind": SCHEMA, "label": LABEL, "run_id": run_id, "side": side,
                       "opening": opening_row, "allowed_build": allowed.get("name"),
                       "role_b_record": allowed.get("role_b_record"), "seckin_approved": approval,
                       "key_source": key_source, "chain_spent_before_usd": spent_before,
                       "chain_run_ids_before": chain,
                       "credit_usd": credit_usd, "limit_usd": limit, "max_calls": max_calls,
                       "resumed_from": None if resume_from is None else Path(resume_from).name,
                       "reused_answers": state["reused"], "build": {"items_sha256": items_sha256,
                                                                               "parts_sha256": parts_sha256},
                       "documents": documents, "documents_planned": len(plans),
                       "items_planned": sum(len(r) for _, r in plans), "calls": state["calls"],
                       "complete": stopped is None and len(documents) == len(plans), "stopped": stopped,
                       "model": {"configured": configured, "resolved": model, "status": status, "registry_unedited": True,
                                 "provider_record": provider_record, "deprecation_checked": deprecation_checked},
                       "allowance": allowance, "cap_usd": cap_usd, "budget": budget, "prices": prices, "max_retries": 0,
                       "count_margin": cr.COUNT_MARGIN, "spent_usd": round(state["spent"], 6),
                       "input_tokens": state["input_tokens"], "output_tokens": state["output_tokens"],
                       "errors": state["errors"], "seconds": round(clock() - started, 3)}
        failures = []
        try:
            line = cr.close_line(run_id, state["spent"], run_folder=out.name, model=model,
                                 complete=measurement["complete"], stopped=stopped, kind=SCHEMA,
                                 seckin_approved=approval, key_source=key_source)
            if role_c:
                line.pop("event")   # the handed-back file holds spend lines only; the lead appends them
            cr.append_store(store_path, line)
        except Exception as exc:
            failures.append(exc)
        try:
            cr.write_json(out / MEASUREMENT_FILE, measurement)
        except Exception as exc:
            failures.append(exc)
        if failures:
            raise failures[0]
    return measurement


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_reference_b1.py", allow_abbrev=False, description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", allow_abbrev=False)
    for name in ("--build", "--items-sha256", "--parts-sha256", "--out", "--price-source", "--deprecation-checked",
                 "--seckin-approved"):
        p.add_argument(name, required=True)
    p.add_argument("--max-calls", type=int, default=None, help="a chunk: stop cleanly after this many calls")
    for name in ("--cap-usd", "--credit-usd", "--price-input-per-mtok", "--price-output-per-mtok"):
        p.add_argument(name, type=float, required=True)
    p.add_argument("--opening", default=None, help="a holdout build's HELDOUT_OPENINGS row (its first cell)")
    p.add_argument("--for-seckin", default=None, help="role C's form: the copy of the FOR_SECKIN entry the lead hands")
    p.add_argument("--role-c-run-id", default=None, help="role C's form: the run id open-role-c gave the lead")
    p.add_argument("--budget-left-usd", type=float, default=None, help="role C's form: the lead's figure")
    p.add_argument("--spend-file", default=None, help="role C's form: the new file handed back to the lead")
    p.add_argument("--resume-from", default=None, help="an earlier run of this build: its finished documents are skipped")
    o = sub.add_parser("open-role-c", allow_abbrev=False,
                       help="the lead: hold role C's cap in the store and print what to hand role C")
    o.add_argument("--cap-usd", type=float, required=True)
    o.add_argument("--seckin-approved", required=True)
    o.add_argument("--resumes", nargs="*", default=(), help="the role C run ids this chunk resumes (one evet for the chain)")
    r = sub.add_parser("record-build", allow_abbrev=False,
                       help="print the allowed-list entry for a build (nothing is written); the lead commits it")
    r.add_argument("--build", required=True)
    r.add_argument("--name", required=True)
    r.add_argument("--role-b-record", required=True, help="role B's build record it comes from, by name")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "open-role-c":
        try:
            print(json.dumps(open_role_c(args.cap_usd, args.seckin_approved, resumes=args.resumes), sort_keys=True))
        except cr.Stop as exc:
            print("cloud_reference_b1 stopped: %s" % exc, file=sys.stderr)
            return 3
        return 0
    if args.command == "record-build":
        try:
            print(json.dumps(build_entry(args.build, args.name, args.role_b_record), indent=1, sort_keys=True))
        except cr.Stop as exc:
            print("cloud_reference_b1 stopped: %s" % exc, file=sys.stderr)
            return 3
        return 0
    try:
        m = run(args.build, args.items_sha256, args.parts_sha256, args.out, cap_usd=args.cap_usd,
                prices={"input_per_mtok": args.price_input_per_mtok, "output_per_mtok": args.price_output_per_mtok,
                        "source": args.price_source},
                deprecation_checked=args.deprecation_checked, seckin_approved=args.seckin_approved,
                credit_usd=args.credit_usd, max_calls=args.max_calls, for_seckin=args.for_seckin,
                role_c_run_id=args.role_c_run_id,
                opening=args.opening, budget_left_usd=args.budget_left_usd, spend_file=args.spend_file,
                resume_from=args.resume_from)
    except cr.Stop as exc:
        print("cloud_reference_b1 stopped: %s" % exc, file=sys.stderr)
        return 3
    print("%s | model %s | documents %d of %d | calls %d | spent %.4f of %.2f USD | %s"
          % (LABEL, m["model"]["resolved"], len(m["documents"]), m["documents_planned"], m["calls"], m["spent_usd"],
             m["cap_usd"], "complete" if m["complete"] else "stopped: " + str(m["stopped"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
