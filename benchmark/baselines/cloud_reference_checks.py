"""Proofs for benchmark/baselines/cloud_reference.py (D-S70 item 5, D-326), on fakes only.

No provider, no network, no key: a planted prompts file, bar, items file, price table and runs
folder in a temporary folder, a fake client recording every request, a fake live model list. Each
guarded rule is neutralised in memory, the proof must FAIL, the rule is restored, the proof must
PASS. One line per proof, a summary line; exit 1 on any failure.

    py -3.12 -X utf8 benchmark/baselines/cloud_reference_checks.py
"""
import contextlib
import hashlib
import json
import os
import re
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cloud_reference as cr  # noqa: E402

KEY = "CLOUDREF-PROOF-KEY-" + "not-a-real-value-0001"
# A key-shaped string the provider might echo that is NOT the loaded key: only the regex path of
# agent_wrapper._scrub_error can remove it (the checker's item 11). Built, never written whole.
OTHER = "-".join(("sk", "ant", "Y" * 32))
# What the environment holds in the D-S106 item 1 proofs: never to be read or sent.
ENV_KEY = "ENV-PROOF-KEY-" + "never-to-be-sent-0002"
APPROVAL = "FOR_SECKIN 2026-11-09 18:00"
# The entry the lead writes, and the evet line it adds only after Seckin's answer (D-401 item 3).
FOR_SECKIN_TEXT = ("# For Seckin\n\n## FOR_SECKIN 2026-11-09 18:00: a paid cloud reference run\n\nWhat it costs.\n\n"
                   "Seckin: evet (2026-11-09 18:05)\n\n## FOR_SECKIN 2026-11-09 19:00: another question\n\n"
                   "No answer yet.\n")
CREDIT = 61.69
# Named here, not read from the module, so a neutralised module cannot hide what it left.
ENV_NAMES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
PRICES = {"input_per_mtok": 5.0, "output_per_mtok": 25.0, "source": "fixture prices, not the provider's"}
DEPRECATION = "https://example.invalid/deprecations, 2026-11-08, not deprecated"


def registry_model():
    return cr.seat_model()


def documents():
    """Four documents a benchmark, so C's split puts two in each half."""
    return {b: ["%s%02d" % (b[:2], i) for i in range(4)] for b in ("contradoc", "scitab")}


def c_split(dropped=()):
    """Half A and half B from C's own function, on the fixture's documents less any whose items are
    all left out: independent of the module under test."""
    import choice_read
    docs = {d: {"benchmark": b} for b, ids in documents().items() for d in ids if d not in dropped}
    return {b: (set(a), set(bb)) for b, (a, bb) in choice_read.split(docs).items()}


def build(folder, extra_user="", extra_item=False, wrong_document=False, left_out_document=None):
    """A prompts file in J1's shape, a bar naming its digest, the items file of its universe, one
    answer key per document (read by the fake scorer), a price table for the registry's model, the
    budget file, a spend store folder and an empty runs folder."""
    folder = Path(folder)
    prompts, n = [], 0
    for benchmark, ids in documents().items():
        for d in ids:
            for group in cr.GROUP_ORDER:
                for form in ("b1", "agent"):
                    n += 1
                    prompts.append({"prompt_id": "p%03d" % n, "benchmark": benchmark, "document_id": d,
                                    "item_id": d + "-i1", "rule_id": "R1", "group": group, "form": form,
                                    "max_new_tokens": 1000, "system": "system turn" if form == "b1" else None,
                                    "user": "document %s, %s, %s%s" % (d, group, form, extra_user)})
    if extra_item:
        prompts.append(dict(prompts[0], prompt_id="p999", item_id="not-in-the-universe"))
    if wrong_document:
        prompts[0] = dict(prompts[0], document_id="co99")
    left_out = [left_out_document + "-i1"] if left_out_document else []
    value = {"kind": "doc_judge", "config_sha256": "c" * 64, "prompts": prompts, "agent_calls": {}}
    path = folder / "prompts.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    bar = folder / "bar.json"
    bar.write_text(json.dumps({"prompts_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "left_out": left_out}),
                   encoding="utf-8")
    items = folder / "items.json"
    items.write_text(json.dumps({b: [d + "-i1" for d in ids if d + "-i1" not in left_out] for b, ids in documents().items()}
                                | {"left_out": left_out}), encoding="utf-8")
    keys = []
    for benchmark, ids in documents().items():
        for d in ids:
            key = folder / "keys" / (d + ".json")
            key.parent.mkdir(exist_ok=True)
            key.write_text(json.dumps({"document_id": d, "benchmark": benchmark, "items": [
                {"item_id": d + "-i1", "document_id": d, "rule_id": "R1", "benchmark": benchmark}]}), encoding="utf-8")
            keys.append(key)
    ledger = folder / "ledger.jsonl"
    ledger.write_text(json.dumps({"event": "budget_open", "time_utc": "2026-11-01T00:00:00+00:00", "budget_usd": 300.0,
                                  "hard_stop_usd": 299.0}) + "\n", encoding="utf-8")
    (folder / "private").mkdir()
    store = folder / "private" / cr.SPEND_STORE_NAME
    store.write_text(json.dumps({"event": "ceiling", "time_utc": "2026-11-09T19:00:00+00:00", "ceiling_usd": 60.0,
                                 "warning_usd": 50.0}) + chr(10), encoding="utf-8")   # created by the operator before the first run   # D-S121: the API ceiling line
    (store.parent / cr.FOR_SECKIN_NAME).write_text(FOR_SECKIN_TEXT, encoding="utf-8")
    prices = folder / "prices.json"
    prices.write_text(json.dumps({"models": {registry_model(): {"input_per_mtok": 5.0, "output_per_mtok": 25.0,
                                                                "source": "fixture", "read_on": "2026-11-08"}}}),
                      encoding="utf-8")
    runs = folder / "output" / "cloud_reference"
    runs.mkdir(parents=True)
    return SimpleNamespace(tmp=folder, path=path, bar=bar, items=items, prices=prices, runs=runs, value=value,
                           keys=keys, ledger=ledger, store=store)


class FakeClient:
    """Records every request. `fail` raises on create ("all", or a set of call numbers, or a
    KeyboardInterrupt number); `usage` None gives a reply with no usage; `inflate` multiplies the
    reported input tokens over the counted ones; `record` is the model record's extra fields."""

    def __init__(self, fail=None, interrupt_at=None, usage=True, inflate=1, output_tokens=200, record=None,
                 count_fails=False, retrieve_fails=False, bad_content=False, other_key=False, cache_write_at=None):
        self.counted, self.created = [], []
        self.fail, self.interrupt_at, self.usage, self.inflate = fail, interrupt_at, usage, inflate
        self.output_tokens, self.record, self.count_fails, self.retrieve_fails = output_tokens, record or {}, count_fails, retrieve_fails
        self.bad_content, self.other_key, self.cache_write_at = bad_content, other_key, cache_write_at
        self.messages = self
        self.models = SimpleNamespace(retrieve=self._retrieve)

    def _retrieve(self, model):
        if self.retrieve_fails:
            raise RuntimeError("no record")
        # The SDK's own shape: to_dict() in python mode keeps created_at a datetime, mode="json"
        # turns it into text (anthropic ModelInfo).
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        fields = {"id": model, "display_name": "fixture", "type": "model", **self.record}

        def to_dict(mode="python"):
            return dict(fields, created_at=when.isoformat() if mode == "json" else when)
        return SimpleNamespace(to_dict=to_dict)

    def count_tokens(self, **params):
        if self.count_fails:
            raise RuntimeError("count failed for %s and %s" % (KEY, OTHER))
        self.counted.append(params)
        return SimpleNamespace(input_tokens=1000)

    def create(self, **params):
        self.created.append(params)
        number = len(self.created)
        if self.interrupt_at == number:
            raise KeyboardInterrupt()
        if self.fail == "all" or (isinstance(self.fail, set) and number in self.fail):
            raise RuntimeError("authentication failed for %s" % (OTHER if self.other_key else KEY))
        usage = SimpleNamespace(input_tokens=int(1000 * self.inflate), output_tokens=self.output_tokens,
                                cache_creation_input_tokens=500 if self.cache_write_at == number else 0,
                                cache_read_input_tokens=0) if self.usage else None
        if self.bad_content:
            class Unreadable:
                stop_reason = "end_turn"

                @property
                def content(self):
                    raise ValueError("a reply shape the code does not know")
            reply = Unreadable()
            reply.usage = usage
            return reply
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"items": []}')], stop_reason="end_turn",
                               usage=usage)


def live(models):
    return lambda backend, keys: set(models)


@contextlib.contextmanager
def sandbox(**kw):
    """A fixture, with doc_judge's pin admitting the fixture's items file alone (the real pin is
    proved apart, on the same file, unpatched)."""
    import doc_judge
    with tempfile.TemporaryDirectory(prefix="shimmer_cloud_reference_") as tmp:
        box = build(tmp, **kw)
        real = doc_judge._pinned
        scorer = SimpleNamespace(item_table=lambda key: json.loads(Path(key).read_text(encoding="utf-8")))
        with patch.object(doc_judge, "_pinned", lambda p: Path(p).resolve() == box.items.resolve() or real(p)), \
                patch.object(doc_judge, "_score_corpus", lambda: scorer):
            yield box


_APPROVALS = iter(range(1, 10000))


def fresh_approval(store):
    """A new FOR_SECKIN heading with its evet line, for a proof that runs more than one paid run in
    one fixture (one evet approves one run, D-401 item 3a)."""
    n = next(_APPROVALS)
    heading = "FOR_SECKIN 2026-11-10 %02d:%02d" % divmod(n, 60)
    path = Path(store).parent / cr.FOR_SECKIN_NAME
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n## %s: a fixture run\n\nSeckin: evet (2026-11-10 23:59)\n" % heading)
    return heading


def go(box, client, cap=15.0, models=None, name="out", prices=None, deprecation=DEPRECATION,
       out=None, mod=cr, root=None, prompts=None, credit=CREDIT, approval="fresh", keys="proof", list_models=None,
       **more):
    extra = {"root": root} if root is not None else {}
    if approval == "fresh":
        approval = fresh_approval(box.store)
    extra.update(more)
    return mod.run(prompts or box.path, box.bar, box.items, box.keys, out if out is not None else box.runs / name,
                   cap_usd=cap, credit_usd=credit, seckin_approved=approval, prices=prices or PRICES,
                   deprecation_checked=deprecation,
                   keys={"ANTHROPIC_API_KEY": KEY} if keys == "proof" else keys, client=client,
                   list_models=None if list_models == "default" else live(models if models is not None else {registry_model()}),
                   runs_root=box.runs, prices_path=box.prices, store=box.store, ledgers=[box.ledger], **extra)


def stopped(call, kind=cr.Stop):
    try:
        call()
    except kind as exc:
        return str(exc) or type(exc).__name__
    return None


def measurement(box, name):
    return json.loads((box.runs / name / cr.MEASUREMENT_FILE).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------


def proof_half_b_refused():
    with sandbox() as box:
        m = go(box, FakeClient(), cap=15.0)
        sent = {r["document_id"] for r in m["rows"]}
        truth = c_split()
        half_a = {d for a, b in truth.values() for d in a}
        half_b = {d for a, b in truth.values() for d in b}
        named = stopped(lambda: cr.selection(box.value, json.loads(box.bar.read_text()), box.items, box.keys, "B"))
        ok = sent == half_a and not (sent & half_b) and named and "half B is reserved" in named
        return ok, "sent %s; C's half A %s, half B %s; asking for half B: %r" % (sorted(sent), sorted(half_a),
                                                                                 sorted(half_b), named)


def proof_universe_is_c_s():
    with sandbox(extra_item=True) as box:
        extra = stopped(lambda: go(box, FakeClient()))
    with sandbox(wrong_document=True) as box:
        moved = stopped(lambda: go(box, FakeClient(), name="moved"))
    with sandbox(left_out_document="sc01") as box:
        m = go(box, FakeClient(), name="dropped")
        sent = {r["document_id"] for r in m["rows"]}
        truth = c_split(dropped=("sc01",))
        dropped_ok = "sc01" not in sent and sent == {d for a, b in truth.values() for d in a}
    import doc_judge
    with tempfile.TemporaryDirectory() as tmp, \
            patch.object(doc_judge, "_score_corpus", lambda: SimpleNamespace(item_table=lambda k: json.loads(Path(k).read_text()))):
        box = build(tmp)
        unpinned = stopped(lambda: go(box, FakeClient()))   # the real pin, unpatched
    ok = (extra and "not C's universe" in extra and moved and "its item's key names another" in moved and dropped_ok
          and unpinned and "pinned" in unpinned)
    return ok, ("an item outside C's universe: %r; a prompt naming another document: %r; a document whose items are all "
                "left out dropped, half A as C splits the rest: %s; an unpinned items file: %r"
                % (extra, moved, dropped_ok, unpinned))


def proof_cap_stops_before_spend():
    with sandbox() as box:
        # 8 prompts a group, each worst case 1000 in + 1000 out = 0.03 USD: 0.24 USD a group,
        # 0.01 USD actually spent a call.
        tight = FakeClient()
        none = go(box, tight, cap=0.2, name="none")
        one = go(box, FakeClient(), cap=0.3, name="one")
        groups_sent = sorted({r["group"] for r in one["rows"]})
        ok = (not tight.created and none["sent"] == 0 and none["stopped"].startswith("cap: judge_direct not started")
              and groups_sent == ["judge_direct"] and one["stopped"].startswith("cap: judge_reason not started")
              and one["spent_usd"] <= 0.3)
        return ok, ("cap 0.2: %d calls, %r; cap 0.3: groups sent %s, spent %.4f, %r"
                    % (len(tight.created), none["stopped"], groups_sent, one["spent_usd"], one["stopped"]))


def proof_per_call_check_holds_alone():
    """The provider reports three times the counted input: the group fits on its counts, the spend
    outruns them, and the check before each call stops it below the cap."""
    with sandbox() as box:
        m = go(box, FakeClient(inflate=3, output_tokens=1000), cap=0.3, name="inflated")
        ok = m["spent_usd"] <= 0.3 and m["stopped"] and m["stopped"].startswith("cap: ") and 0 < m["sent"] < 8
        return ok, "sent %d, spent %.4f of 0.30, %r" % (m["sent"], m["spent_usd"], m["stopped"])


def proof_failed_and_unread_calls_count_worst():
    with sandbox() as box:
        failed = go(box, FakeClient(fail="all"), cap=5.0, name="failed")
        blind = go(box, FakeClient(usage=False), cap=5.0, name="blind")
        worst_each = cr.worst_case(1000, 1000, PRICES)
        ok = (abs(failed["spent_usd"] - worst_each * failed["sent"]) < 1e-9
              and abs(blind["spent_usd"] - worst_each * blind["sent"]) < 1e-9
              and all(r["cost_is"].startswith("worst case") for r in failed["rows"] + blind["rows"]))
        return ok, "failed calls %d spent %.4f; replies with no usage %d spent %.4f; worst each %.4f" % (
            failed["sent"], failed["spent_usd"], blind["sent"], blind["spent_usd"], worst_each)


def proof_count_tokens_failing_stops():
    with sandbox() as box:
        client = FakeClient(count_fails=True)
        m = go(box, client, name="nocount")
        ok = (not client.created and m["sent"] == 0 and m["stopped"].startswith("count_tokens failed")
              and KEY not in json.dumps(m))
        return ok, "calls %d, %r" % (len(client.created), m["stopped"])


def proof_no_retry():
    """The client is built with max_retries=0, and no prompt is sent twice by the module."""
    built, made = {}, []
    fake = types.ModuleType("anthropic")

    def construct(**kwargs):
        built.update(kwargs)
        made.append(FakeClient(fail={1}))
        return made[-1]
    fake.Anthropic = construct
    with sandbox() as box, patch.dict(sys.modules, {"anthropic": fake}):
        m = go(box, None, name="retry")
    ids = [r["prompt_id"] for r in m["rows"]]
    requests = len(made[0].created) if made else None
    ok = (built.get("max_retries") == 0 and len(ids) == len(set(ids)) == requests and m["max_retries"] == 0
          and m["rows"][0]["failure"])
    return ok, "client built with %s; prompts recorded %d, requests made %s; the failed first call was not resent" % (
        {k: v for k, v in built.items() if k != "api_key"}, len(ids), requests)


def proof_cap_within_the_total():
    """D-S121 (D-453): the cap is held to the API's own ceiling (60, from the store's ceiling line), less
    the shared store's earlier spend; 290 USD of Lambda spend in the loop ledgers never blocks an API
    run with room. A store that cannot be read refuses."""
    with sandbox() as box:
        with box.ledger.open("a", encoding="utf-8") as stream:
            for n, cost_usd in enumerate((260.0, 30.0)):
                name = "shimmer-loop-fixture-%d" % n
                stream.write(json.dumps({"event": "launch", "time_utc": "2026-11-02T00:00:00+00:00", "instance_id": "i%d" % n,
                                         "instance_name": name, "launch_requested_utc": "2026-11-02T00:00:00+00:00",
                                         "price_usd_per_hour": 1.0}) + "\n")
                stream.write(json.dumps({"event": "termination", "time_utc": "2026-11-02T01:00:00+00:00", "instance_id": "i%d" % n,
                                         "instance_name": name, "actual_cost": cost_usd}) + "\n")
        cr.append_store(box.store, {"run_id": "earlier", "spent_usd": 10.0})
        # The API ceiling 60 less the earlier 10: 50 left, whatever Lambda has spent (290 of its 299).
        fits = go(box, FakeClient(), cap=15.0, name="fits")
        over = stopped(lambda: go(box, FakeClient(), cap=55.0, name="over"))
        lines = cr.read_store(box.store)
        box.store.write_text("not json\n", encoding="utf-8")
        unreadable = stopped(lambda: cr.check_cap(1.0, box.store, [box.ledger], kind=cr.SCHEMA))
        ok = (fits["budget"]["lambda"]["instance_spend_usd"] == 290.0 and fits["budget"]["left_usd"] == 50.0
              and fits["budget"]["earlier_reference_spent_usd"] == 10.0 and len(lines) == 2
              and lines[-1]["spent_usd"] == fits["spent_usd"]
              and over and "would pass the API ceiling 60.00" in over and unreadable and "cannot be read" in unreadable)
        return ok, ("cap 15 with 290 of Lambda spent and 10 of API spent: %s left; cap 55 after it: %r; an unreadable "
                    "store: %r" % (fits["budget"]["left_usd"], over, unreadable))


def proof_prices_match_the_table():
    with sandbox() as box:
        wrong = stopped(lambda: go(box, FakeClient(), prices=dict(PRICES, output_per_mtok=20.0), name="wrong"))
        box.prices.write_text(json.dumps({"models": {}}), encoding="utf-8")
        missing = stopped(lambda: go(box, FakeClient(), name="missing"))
        ok = wrong and "not the recorded ones" in wrong and missing and "No recorded price" in missing
        return ok, "prices unlike the table: %r; no row: %r" % (wrong, missing)


def proof_deprecated_model_stops():
    with sandbox() as box:
        client = FakeClient()
        gone = stopped(lambda: go(box, client, models=set(), name="gone"))
        ambiguous = stopped(lambda: go(box, client, models={registry_model() + "-20990101",
                                                            registry_model() + "-20990202"}, name="amb"))
        flagged = FakeClient(record={"deprecation_date": "2026-12-01"})
        recorded = stopped(lambda: go(box, flagged, name="flagged"))
        unread = stopped(lambda: go(box, FakeClient(retrieve_fails=True), name="unread"))
        unchecked = stopped(lambda: go(box, FakeClient(), deprecation="", name="unchecked"))
        ok = (not client.counted and not client.created and not flagged.created and "deprecated" in (gone or "")
              and "ambiguous" in (ambiguous or "") and "names a deprecation" in (recorded or "")
              and "could not be read" in (unread or "") and "deprecations page" in (unchecked or ""))
        return ok, "gone %r; ambiguous %r; record %r; record unread %r; no page reading %r" % (
            gone, ambiguous, recorded, unread, unchecked)


def proof_planted_key_refuses():
    with sandbox(extra_user=" " + "-".join(("sk", "ant", "x" * 30))) as box:
        client = FakeClient()
        why = stopped(lambda: go(box, client))
    with sandbox(extra_user=" " + KEY) as box:
        client_two = FakeClient()
        own = stopped(lambda: go(box, client_two))
    ok = (why and "key-shaped" in why and own and "provider key" in own
          and not (client.counted or client.created or client_two.counted or client_two.created))
    return ok, "a key-shaped string: %r; the key itself: %r" % (why, own)


def proof_no_key_in_output():
    with sandbox() as box:
        m = go(box, FakeClient(fail="all"), cap=15.0)
        line = cr.summary_line(m)
        texts = [p.read_text(encoding="utf-8", errors="replace") for p in (box.runs / "out").rglob("*") if p.is_file()]
        carrying = [t for t in texts + [line, json.dumps(m)] if KEY in t]
        ok = m["sent"] > 0 and all(r["failure"] for r in m["rows"]) and not carrying
        return ok, "failed calls %d, each error carrying the key; files and outputs still carrying it: %d" % (
            m["sent"], len(carrying))


def proof_spend_written_on_any_exit(mod=cr):
    with sandbox() as box:
        client = FakeClient(interrupt_at=3)
        raised = stopped(lambda: go(box, client, name="cut", mod=mod), kind=KeyboardInterrupt)
        path = box.runs / "cut" / cr.MEASUREMENT_FILE
        m = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        expected = 2 * cr.cost(1000, 200, PRICES) + cr.worst_case(1000, 1000, PRICES)
        store = cr.read_store(box.store) if box.store.exists() else []
        ok = (raised is not None and m is not None and m["sent"] == 2 and abs(m["spent_usd"] - expected) < 1e-9
              and m["stopped"].startswith("interrupted") and store and abs(store[-1]["spent_usd"] - expected) < 1e-9)
        return ok, ("interrupted in call 3's request: measurement written %s, sent %s, spent %s (two replies and the "
                    "interrupted call's worst case: %.4f), store line %s" % (
                        m is not None, m and m["sent"], m and m["spent_usd"], expected, store[-1] if store else None))


def proof_run_folder_under_output():
    with sandbox() as box:
        outside = stopped(lambda: go(box, FakeClient(), out=box.tmp / "elsewhere"))
        go(box, FakeClient(), name="once", cap=1.0)
        again = stopped(lambda: go(box, FakeClient(), name="once"))
        (box.runs / "orphan" / "audit" / "model_replies").mkdir(parents=True)
        orphan = stopped(lambda: go(box, FakeClient(), name="orphan"))
        ok = (outside and "output/cloud_reference" in outside and again and "holds a run already" in again
              and orphan and "audit/ but no readable measurement" in orphan)
        return ok, "outside output/cloud_reference: %r; a used folder: %r; audit/ with no measurement: %r" % (
            outside, again, orphan)


def proof_seat_is_the_registry_model_and_registry_unedited():
    registry = cr.ROOT / "config" / "agent_registry.json"
    before = hashlib.sha256(registry.read_bytes()).hexdigest()
    with sandbox() as box:
        client = FakeClient()
        m = go(box, client, cap=15.0)
        models = {c["model"] for c in client.created}
        b1 = [c for c in client.created if "system" in c]
        agent = [c for c in client.created if "system" not in c]
    after = hashlib.sha256(registry.read_bytes()).hexdigest()
    ok = (models == {registry_model()} and m["model"]["resolved"] == registry_model() and before == after
          and b1 and agent and all(c["system"] == "system turn" for c in b1))
    return ok, "model sent %s, registry %s, unchanged %s; b1 calls with their system turn %d, agent calls %d" % (
        sorted(models), registry_model(), before == after, len(b1), len(agent))


def proof_only_the_bar_s_file():
    with sandbox() as box:
        other = box.tmp / "other.json"
        other.write_text(box.path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        why = stopped(lambda: go(box, FakeClient(), prompts=other, name="o"))
        return why and "J1's bar names" in why, "a prompts file the bar does not name: %r" % why


def proof_plan_calls_nothing():
    with sandbox() as box:
        chosen = cr.selection(box.value, json.loads(box.bar.read_text()), box.items, box.keys, "A")
        p = cr.plan(chosen, PRICES)
        ok = (set(p["groups"]) == set(cr.GROUP_ORDER) and all(g["prompts"] == 8 for g in p["groups"].values())
              and all(g["worst_case_usd"] > 0 for g in p["groups"].values()) and p["label"] == cr.LABEL)
        return ok, "plan: %s" % json.dumps({k: (v["prompts"], v["worst_case_usd"]) for k, v in p["groups"].items()})


def proof_unreadable_reply_counted_once():
    """A billed reply the code cannot read: its spend is counted once, from its usage, and the run
    goes on (the checker's item 9)."""
    with sandbox() as box:
        m = go(box, FakeClient(bad_content=True), cap=5.0, name="unreadable")
        each = cr.cost(1000, 200, PRICES)
        ok = (m["sent"] == 16 and abs(m["spent_usd"] - each * 16) < 1e-9
              and all(r["failure"] == "reply not readable" for r in m["rows"]))
        return ok, "replies unreadable %d, spent %.4f, %.4f expected (usage once each)" % (m["sent"], m["spent_usd"], each * 16)


def proof_count_margin_covers_the_bill():
    """The provider bills 8 percent above count_tokens' estimate: no call costs more than the worst
    case counted for it (the checker's item 10)."""
    with sandbox() as box:
        m = go(box, FakeClient(inflate=1.08, output_tokens=1000), cap=5.0, name="margin")
        over = [r["prompt_id"] for r in m["rows"] if r["cost_usd"] > r["worst_case_usd"] + 1e-12]
        ok = m["sent"] == 16 and not over and m["count_margin"] >= 1.08
        return ok, "calls %d, calls billed above their worst case %d, margin %s" % (m["sent"], len(over), m["count_margin"])


def proof_key_shaped_echo_scrubbed():
    """A provider error echoing a key-shaped string that is not the loaded key is scrubbed by the
    regex path alone."""
    with sandbox() as box:
        m = go(box, FakeClient(fail="all", other_key=True), cap=5.0, name="echo")
        texts = [p.read_text(encoding="utf-8", errors="replace") for p in (box.runs / "echo").rglob("*") if p.is_file()]
        carrying = [t for t in texts + [json.dumps(m), cr.summary_line(m)] if OTHER in t]
        ok = m["sent"] > 0 and not carrying
        return ok, "failed calls %d echoing a key-shaped string; outputs still carrying it: %d" % (m["sent"], len(carrying))


def proof_main_prints_and_logs_no_key():
    """main()'s stdout, stderr and every log record, on a run whose count_tokens error carries the
    key and a key-shaped string."""
    import io
    import logging
    with sandbox() as box:
        records = []

        class Keep(logging.Handler):
            def emit(self, record):
                records.append(self.format(record))
        handler = Keep()
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        original = cr.run

        def bound(*a, **k):
            k.update(keys={"ANTHROPIC_API_KEY": KEY}, client=FakeClient(count_fails=True),
                     list_models=live({registry_model()}), runs_root=box.runs, prices_path=box.prices,
                     store=box.store, ledgers=[box.ledger])
            return original(*a, **k)
        out, err = io.StringIO(), io.StringIO()
        try:
            with patch.object(cr, "run", bound), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cr.main(["run", "--prompts", str(box.path), "--bar", str(box.bar), "--items", str(box.items),
                                *[x for k in box.keys for x in ("--key", str(k))],
                                "--out", str(box.runs / "main"), "--cap-usd", "5", "--credit-usd", "61.69",
                                "--seckin-approved", APPROVAL,
                                "--price-input-per-mtok", "5", "--price-output-per-mtok", "25",
                                "--price-source", "fixture", "--deprecation-checked", DEPRECATION])
        finally:
            root_logger.removeHandler(handler)
        seen = out.getvalue() + err.getvalue() + "\n".join(records)
        ok = code == 0 and "count_tokens failed" in out.getvalue() and KEY not in seen and OTHER not in seen
        return ok, "exit %s; stdout, stderr and %d log records carry the key %s, a key-shaped string %s" % (
            code, len(records), KEY in seen, OTHER in seen)


def proof_model_is_read_from_the_registry():
    """A registry naming another Anthropic model seats that model: nothing in the module names one."""
    with sandbox() as box:
        root = box.tmp / "root"
        (root / "config").mkdir(parents=True)
        registry = json.loads((cr.ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))
        registry["agents"][cr.SEAT_AGENT] = dict(registry["agents"][cr.SEAT_AGENT], backend="claude_api",
                                                 model="claude-fixture-9-9")
        (root / "config" / "agent_registry.json").write_text(json.dumps(registry), encoding="utf-8")
        table = json.loads(box.prices.read_text(encoding="utf-8"))
        table["models"]["claude-fixture-9-9"] = dict(table["models"][registry_model()])
        box.prices.write_text(json.dumps(table), encoding="utf-8")
        client = FakeClient()
        m = go(box, client, cap=5.0, models={"claude-fixture-9-9"}, root=root, name="fixture-model")
        models = {c["model"] for c in client.created}
        ok = models == {"claude-fixture-9-9"} and m["model"]["configured"] == "claude-fixture-9-9"
        return ok, "a registry naming claude-fixture-9-9: requests used %s" % sorted(models)


def proof_plan_builds_no_client():
    """plan, through main(), builds no client and lists no model."""
    import io
    import model_registry
    built, listed = [], []
    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda **kwargs: built.append(kwargs) or FakeClient()
    with sandbox() as box, patch.dict(sys.modules, {"anthropic": fake}), \
            patch.object(model_registry, "list_available_models", lambda *a: listed.append(a) or set()), \
            contextlib.redirect_stdout(io.StringIO()):
        code = cr.main(["plan", "--prompts", str(box.path), "--bar", str(box.bar), "--items", str(box.items),
                        *[x for k in box.keys for x in ("--key", str(k))],
                        "--price-input-per-mtok", "5", "--price-output-per-mtok", "25", "--price-source", "fixture"])
    ok = code == 0 and not built and not listed
    return ok, "exit %s; clients built %d, model lists read %d" % (code, len(built), len(listed))


def _plan_building_a_client(original):
    def plan(prompts, prices=None):
        cr.make_client("x")
        return original(prompts, prices)
    return plan


def proof_absent_store_refuses():
    """An absent spend store is refused before any call, even where its folder exists; it is never
    read as no spend (D-358)."""
    with sandbox() as box:
        box.store.unlink()
        client = FakeClient()
        why = stopped(lambda: go(box, client, cap=1.0, name="nostore"))
        ok = why and "does not exist" in why and not client.counted and not client.created and not box.store.exists()
        return ok, "the store removed, its folder kept: %r; provider calls %d" % (why, len(client.counted) + len(client.created))


def proof_record_with_a_datetime_is_written(mod=cr):
    """The SDK's record carries created_at as a datetime: the measurement and the spend line are
    still written, created_at as text (the checker's round 2, item 1)."""
    with sandbox() as box:
        stopped(lambda: go(box, FakeClient(), cap=1.0, name="dated", mod=mod), kind=Exception)
        if not (box.runs / "dated" / cr.MEASUREMENT_FILE).exists():
            return False, "no measurement was written"
        written = json.loads((box.runs / "dated" / cr.MEASUREMENT_FILE).read_text(encoding="utf-8"))
        created = written["model"]["provider_record"].get("created_at")
        ok = isinstance(created, str) and created.startswith("2026-01-01") and cr.read_store(box.store)
        return ok, "created_at written as %r; spend line written %s" % (created, bool(cr.read_store(box.store)))


def proof_store_found_from_git_not_cwd():
    """The spend store is the main checkout's docs/loop/private/, found from git's common directory
    of this file's tree, whatever the working folder."""
    import subprocess
    try:
        common = subprocess.run(["git", "-C", str(cr.ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, timeout=30,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        return None, "git absent: the store's resolution is not provable here"
    if common.returncode != 0:
        return None, "not a git tree (the container image): the store's resolution is not provable here"
    expected = Path(common.stdout.strip()).resolve().parent / "docs" / "loop" / "private" / cr.SPEND_STORE_NAME
    here = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.chdir(tmp)
            found = cr.spend_store()
        finally:
            os.chdir(here)
    ok = found == expected
    return ok, "from another working folder: %s; expected %s" % (found, expected)


def proof_prices_digest_recorded():
    with sandbox() as box:
        m = go(box, FakeClient(), cap=1.0, name="digest")
        digest = hashlib.sha256(box.prices.read_bytes()).hexdigest()
        ok = m["prices"].get("table_sha256") == digest
        return ok, "the table's digest recorded: %s" % (m["prices"].get("table_sha256") == digest)


def proof_deprecation_reading_has_its_form():
    with sandbox() as box:
        bad = [stopped(lambda d=d: go(box, FakeClient(), deprecation=d, name="dep")) for d in (
            "checked", "https://example.invalid/deprecations, 2026-11-08", "example.invalid, 2026-11-08, not deprecated",
            "https://example.invalid/deprecations, 8 Nov, not deprecated",
            "https://example.invalid/deprecations, 2026-11-08, deprecated")]
        good = go(box, FakeClient(), cap=1.0, name="dep-ok")
        ok = all(b and "not deprecated" in b for b in bad) and good["model"]["deprecation_checked"] == DEPRECATION
        return ok, "five readings out of form refused %s; the form accepted %s" % (
            all(b for b in bad), good["model"]["deprecation_checked"] == DEPRECATION)


def proof_cache_writes_stop_the_run():
    with sandbox() as box:
        m = go(box, FakeClient(cache_write_at=2), cap=5.0, name="cache")
        each = cr.cost(1000, 200, PRICES)
        worst = cr.worst_case(1000, 1000, PRICES)
        ok = (m["sent"] == 2 and m["stopped"].startswith("usage reports 500 cache-write tokens")
              and abs(m["spent_usd"] - (each + worst)) < 1e-9)
        return ok, "sent %d, %r, spent %.4f (one reply and the cache-writing call's worst case %.4f)" % (
            m["sent"], m["stopped"], m["spent_usd"], each + worst)


class BadRequestError(Exception):
    """Named as the SDK names a 400, the error a credit balance run out returns."""


def proof_no_credit_stops_cleanly():
    with sandbox() as box:
        client = FakeClient()
        original = client.create

        def create(**params):
            if client.created:
                client.created.append(params)
                raise BadRequestError("Your credit balance is too low")
            return original(**params)
        client.create = create
        m = go(box, client, cap=5.0, name="nocredit")
    ok = len(client.created) == 2 and m["stopped"] and "stops cleanly" in m["stopped"] and m["sent"] == 2
    return ok, "no credit after one call: %d sent, %r" % (len(client.created), m["stopped"])


@contextlib.contextmanager
def credential_file(exists=True):
    """A credential file holding the proof key, the only candidate the resolver sees (the real
    candidates are never looked at), and an environment whose key variables point elsewhere."""
    import agent_wrapper
    with tempfile.TemporaryDirectory(prefix="shimmer_cloud_key_") as tmp:
        cfg = Path(tmp) / "config.py"
        if exists:
            cfg.write_text('ANTHROPIC_API_KEY = "%s"\n' % KEY, encoding="utf-8")
        env = {"ANTHROPIC_API_KEY": ENV_KEY, "ANTHROPIC_AUTH_TOKEN": ENV_KEY,
               "ANTHROPIC_BASE_URL": "https://elsewhere.invalid"}
        with patch.dict(os.environ, env), \
                patch.object(agent_wrapper, "candidate_config_paths", lambda: [("SHIMMER_CONFIG_PATH", cfg)]):
            yield cfg


def fake_sdk(built):
    fake = types.ModuleType("anthropic")

    def construct(**kwargs):
        built.update(kwargs)
        built["environment_at_build"] = {n: os.environ.get(n) for n in ENV_NAMES}
        built.setdefault("clients", []).append(FakeClient())
        return built["clients"][-1]
    fake.Anthropic = construct
    return fake


def proof_key_only_from_the_resolver():
    """D-S106 item 1: the key is the credential file's, named by its source; an environment key,
    token or base URL is removed before the client is built and never sent; no file, no run."""
    built = {}
    with credential_file() as cfg, patch.dict(sys.modules, {"anthropic": fake_sdk(built)}):
        key, label = cr.resolve_key()
        cr.make_client(key)
        left = {n: os.environ.get(n) for n in ENV_NAMES}
    with credential_file(exists=False):
        none = stopped(cr.resolve_key)
    env = built.get("environment_at_build", {})
    ok = (key == KEY and label == "SHIMMER_CONFIG_PATH" and built.get("api_key") == KEY
          and built.get("auth_token") is None and built.get("base_url") == cr.API_BASE_URL
          and all(v is None for v in env.values()) and all(v is None for v in left.values())
          and none is not None and ENV_KEY not in repr(built))
    return ok, ("source %s; client given the file's key %s, the environment's %s; environment at build %s; with no "
                "file: %r" % (label, built.get("api_key") == KEY, ENV_KEY in repr(built),
                              sorted(n for n, v in env.items() if v is not None) or "clear", none))


def proof_run_takes_the_resolver_s_key():
    """A run given no keys builds its client from the resolver's key alone, and records the source."""
    built = {}
    with sandbox() as box, credential_file(), patch.dict(sys.modules, {"anthropic": fake_sdk(built)}):
        m = go(box, None, name="resolver", keys=None)
        line = json.loads(box.store.read_text(encoding="utf-8").splitlines()[-1])
    sent_keys = {built.get("api_key")}
    ok = (sent_keys == {KEY} and m["key_source"] == "SHIMMER_CONFIG_PATH" and line["key_source"] == "SHIMMER_CONFIG_PATH"
          and m["complete"] and ENV_KEY not in json.dumps(m))
    return ok, "client key from the file %s; source in the measurement %r and the spend line %r" % (
        sent_keys == {KEY}, m.get("key_source"), line.get("key_source"))


def proof_approval_required():
    """D-S106 item 2: no heading time of Seckin's yes, no run and nothing sent; with it, it is in
    the measurement and the spend line."""
    with sandbox() as box:
        client = FakeClient()
        why = stopped(lambda: go(box, client, name="a", approval="FOR_SECKIN entry written, waiting"))
        empty = stopped(lambda: go(box, client, name="a2", approval=None))
        count = len(client.created) + len(client.counted)
        unanswered = stopped(lambda: go(box, client, name="a4", approval="FOR_SECKIN 2026-11-09 19:00"))
        count = len(client.created) + len(client.counted)
        m = go(box, FakeClient(), name="a3", cap=5.0, approval=APPROVAL)
        line = json.loads(box.store.read_text(encoding="utf-8").splitlines()[-1])
    recorded = line.get("seckin_approved") or {}
    ok = (why is not None and "heading" in why and empty is not None and unanswered is not None
          and "Seckin: evet" in unanswered and count == 0 and m["seckin_approved"]["named"] == APPROVAL
          and recorded.get("evet_line") == "Seckin: evet (2026-11-09 18:05)" and "lead-attested" in recorded.get("attested", ""))
    return ok, "no such heading: %r; none refused %s; a heading with no evet line: %r; %d requests; recorded %r" % (
        why, empty is not None, unanswered, count, recorded.get("evet_line"))


def proof_credit_bounds_the_worst_case():
    """--credit-usd below a group's worst case: the group is not started, nothing sent."""
    with sandbox() as box:
        client = FakeClient()
        m = go(box, client, name="credit", cap=15.0, credit=0.05)
    ok = not client.created and bool(m["stopped"]) and m["stopped"].startswith("cap: ") and m["limit_usd"] == 0.05
    return ok, "credit 0.05 under a cap of 15: %d sent, %r" % (len(client.created), m["stopped"])


class CreditGone(FakeClient):
    """Answers `answers` calls, then refuses as the provider does when the credit is gone."""

    def __init__(self, answers, **kw):
        super().__init__(**kw)
        self.answers = answers

    def create(self, **params):
        if len(self.created) >= self.answers:
            self.created.append(params)
            raise BadRequestError("Your credit balance is too low to access the Anthropic API")
        return super().create(**params)


def requests(client):
    return [json.dumps([c.get("system"), c["messages"]], sort_keys=True) for c in client.created]


def proof_credit_fault_then_resume():
    """D-S106 item 3: the credit runs out after three replies; the run stops cleanly with the spend
    line written; resumed from its folder, only the prompts not answered are sent, none twice, and
    every prompt is answered."""
    with sandbox() as box:
        first = CreditGone(3)
        cut = go(box, first, cap=5.0, name="cut")
        lines = cr.read_store(box.store)
        second = FakeClient()
        done = go(box, second, cap=5.0, name="resumed", resume_from=box.runs / "cut")
        copied = len(list((box.runs / "resumed" / "audit" / "model_replies").glob("*.json")))
    answered = set(requests(first)[:3])
    again = answered & set(requests(second))
    ok = (len(first.created) == 4 and bool(cut["stopped"]) and "stops cleanly" in cut["stopped"] and len(lines) == 1
          and not again and done["complete"] and done["reused_answers"] == 3
          and done["sent"] == done["prompts"] - 3 and done["answered"] == done["prompts"] and copied == done["prompts"])
    return ok, ("credit gone after 3 replies: %d requests, %r, %d spend line; resumed: %d sent of %d, %d again, "
                "%d answered" % (len(first.created), cut["stopped"], len(lines), done["sent"], done["prompts"],
                                 len(again), done["answered"]))


def proof_chunks_and_resume(mod=cr):
    """--max-calls 2: two calls and a clean stop; the next chunk, resumed, sends the rest, none twice."""
    with sandbox() as box:
        one = FakeClient()
        cut = go(box, one, cap=5.0, name="chunk1", max_calls=2, mod=mod)
        two = FakeClient()
        rest = go(box, two, cap=5.0, name="chunk2", resume_from=box.runs / "chunk1", mod=mod)
    again = set(requests(one)) & set(requests(two))
    ok = (len(one.created) == 2 and str(cut["stopped"]).startswith("chunk done") and not again and rest["complete"]
          and rest["sent"] == rest["prompts"] - 2)
    return ok, "chunk of 2: %d sent, %r; the rest: %d sent, %d again" % (len(one.created), cut["stopped"],
                                                                         len(two.created), len(again))

class ListingClient(FakeClient):
    """A fake client whose model list holds the registry's model."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.models.list = lambda: [SimpleNamespace(id=registry_model())]


def listing_sdk(built):
    """A fake SDK recording every client it builds: its arguments and the environment then."""
    fake = types.ModuleType("anthropic")

    def construct(**kwargs):
        built.setdefault("builds", []).append(dict({k: v for k, v in kwargs.items() if k != "api_key"},
                                                   key_is_the_file_s=kwargs.get("api_key") == KEY,
                                                   environment={n: os.environ.get(n) for n in ENV_NAMES}))
        built.setdefault("clients", []).append(ListingClient())
        return built["clients"][-1]
    fake.Anthropic = construct
    return fake


def proof_model_list_built_like_the_client():
    """D-401 item 1: the environment is cleared and the provider's base URL passed before ANY client
    is built, the live model list's included (the runner's own list, under a fake SDK)."""
    built = {}
    env = {"ANTHROPIC_BASE_URL": "https://elsewhere.invalid", "ANTHROPIC_API_KEY": ENV_KEY,
           "ANTHROPIC_AUTH_TOKEN": ENV_KEY}
    with sandbox() as box, patch.dict(os.environ, env), patch.dict(sys.modules, {"anthropic": listing_sdk(built)}):
        m = go(box, None, cap=5.0, name="listing", models=None, list_models="default")
    builds = built.get("builds", [])
    ok = (len(builds) >= 2 and all(b.get("base_url") == cr.API_BASE_URL and b["key_is_the_file_s"]
                                   and all(v is None for v in b["environment"].values()) for b in builds)
          and m["complete"] and m["model"]["resolved"] == registry_model())
    return ok, "%d clients built (the model list's first), each with the provider's URL %s and a clear environment %s" % (
        len(builds), all(b.get("base_url") == cr.API_BASE_URL for b in builds),
        all(all(v is None for v in b["environment"].values()) for b in builds))


def _paid_folder(box, name, cap=5.0):
    """A finished paid run of the fixture: its folder."""
    go(box, FakeClient(), cap=cap, name=name)
    return box.runs / name


def _edit_records(folder, change):
    for path in (folder / "audit" / "model_replies").glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        change(record)
        path.write_text(json.dumps(record), encoding="utf-8")


def _edit_measurement(folder, change):
    path = folder / cr.MEASUREMENT_FILE
    value = json.loads(path.read_text(encoding="utf-8"))
    change(value)
    path.write_text(json.dumps(value), encoding="utf-8")


def proof_resume_refuses_steering(mod=cr):
    """D-401 item 2: a resume from a steering check is refused, whether the steering stamp is on its
    measurement, on one record, or the folder is the steering runner's own."""
    import claim_guard
    import cloud_reference_steering as st
    with sandbox() as box:
        stamped = _paid_folder(box, "stamped")
        _edit_measurement(stamped, lambda v: v.update(label=claim_guard.STEERING_LABEL, claim=False))
        on_measurement = stopped(lambda: go(box, FakeClient(), cap=5.0, name="r1", resume_from=stamped, mod=mod), mod.Stop)
        one = _paid_folder(box, "one")
        first = sorted((one / "audit" / "model_replies").glob("*.json"))[0]
        record = json.loads(first.read_text(encoding="utf-8"))
        record["backend"] = "claude_subscription"
        first.write_text(json.dumps(record), encoding="utf-8")
        on_record = stopped(lambda: go(box, FakeClient(), cap=5.0, name="r2", resume_from=one, mod=mod), mod.Stop)
        steer_root = box.tmp / "steering_runs"
        steer_root.mkdir()
        subset = box.tmp / "subset.json"
        subset.write_text(json.dumps(sorted({p["item_id"] for p in box.value["prompts"]})), encoding="utf-8")
        sets = box.tmp / "sets.json"
        sets.write_text(json.dumps({"allowed": [{"name": "fixture", "prompts_sha256": cr.sha(box.path),
                                                 "subset_sha256": cr.sha(subset)}], "refused": []}), encoding="utf-8")
        st.run(box.path, subset, cr.sha(subset), steer_root / "s", caller=lambda m_, t, c: ('{"items": []}', None, None),
               status=lambda cwd: (dict(st.SUBSCRIPTION, subscriptionType="max"), None), runs_root=steer_root,
               sets_path=sets, fresh_source=box.tmp / "none.py")
        own = stopped(lambda: go(box, FakeClient(), cap=5.0, name="r3", resume_from=steer_root / "s", mod=mod), mod.Stop)
    ok = bool(on_measurement and on_record and own)
    return ok, "steering stamp on the measurement: %r; on one record: %r; the steering runner's folder: %r" % (
        on_measurement, on_record, own)


def proof_resume_refuses_other_runs(mod=cr):
    """D-401 item 2: a resume is refused from a run on another model (its records or its measurement),
    on other inputs (the prompts digest), or whose replies ran other settings."""
    with sandbox() as box:
        a = _paid_folder(box, "a")
        _edit_records(a, lambda r: r.update(model_id="claude-other-model"))
        records = stopped(lambda: go(box, FakeClient(), cap=5.0, name="r1", resume_from=a, mod=mod), mod.Stop)
        b = _paid_folder(box, "b")
        _edit_measurement(b, lambda v: v["model"].update(resolved="claude-other-model"))
        measured = stopped(lambda: go(box, FakeClient(), cap=5.0, name="r2", resume_from=b, mod=mod), mod.Stop)
        c = _paid_folder(box, "c")
        _edit_measurement(c, lambda v: v.update(prompts_sha256="0" * 64))
        inputs = stopped(lambda: go(box, FakeClient(), cap=5.0, name="r3", resume_from=c, mod=mod), mod.Stop)
        d = _paid_folder(box, "d")
        _edit_records(d, lambda r: r.update(decoding=dict(r.get("decoding") or {}, max_tokens=99)))
        settings = stopped(lambda: go(box, FakeClient(), cap=5.0, name="r4", resume_from=d, mod=mod), mod.Stop)
    ok = bool(records and measured and inputs and settings)
    return ok, "another model in the records: %r; in the measurement: %r; other prompts: %r; other settings: %r" % (
        records, measured, inputs, settings)


def proof_intent_counts_while_open():
    """D-401 item 5: a run writes its intent under the store's lock before its first request; an open
    intent's cap counts as running until its close line; a held lock refuses."""
    with sandbox() as box:
        m = go(box, FakeClient(), cap=5.0, name="first")
        rows = [r for r in (json.loads(l) for l in box.store.read_text(encoding="utf-8").splitlines())
                if r.get("event") in ("intent", "close")]   # the fixture's API ceiling line set apart (D-S121)
        pair = [r.get("event") for r in rows] == ["intent", "close"] and rows[0]["run_id"] == rows[1]["run_id"] == m["run_id"]
        closed = cr.spend.state(box.store)["running_caps_usd"] == 0.0
        cr.append_store(box.store, {"event": "intent", "run_id": "open-elsewhere", "cap_usd": 290.0,
                                    "time_utc": "2026-11-09T00:00:00+00:00"})
        client = FakeClient()
        open_cap = stopped(lambda: go(box, client, cap=15.0, name="second"))
        lock = Path(str(box.store) + ".lock")
        lock.write_text(json.dumps({"pid": 1, "created_epoch": 0}), encoding="utf-8")
        held = stopped(lambda: go(box, client, cap=1.0, name="third"))
        lock.unlink()
        sent = len(client.created) + len(client.counted)
    # an open intent's cap counts: by the API ceiling's running caps (D-S121) or the total's runs open
    ok = (pair and closed and bool(open_cap) and ("runs open" in open_cap or "running 290" in open_cap) and bool(held)
          and "lock" in held and sent == 0)
    return ok, "intent then close %s, closed counts 0 %s; an open 290 USD intent: %r; a held lock: %r; %d requests" % (
        pair, closed, open_cap, held, sent)


def proof_handed_back_file_blocks_the_lead():
    """D-401 item 11: a role C spend file in the drop folder and not appended stops the lead's next
    paid run before any request, and through `lead_may_spend` the guard's next launch; appended once,
    its spend is counted and a second append is refused."""
    with sandbox() as box:
        drop = cr.spend.handback_dir(box.store)
        drop.mkdir()
        handed = drop / "role_c_spend.jsonl"
        # The lead opened role C's intent first (cloud_reference_b1.py open-role-c); the append closes it.
        cr.append_store(box.store, {"event": "intent", "run_id": "role-c-1", "cap_usd": 3.0,
                                    "kind": cr.spend.ROLE_C_KIND, "time_utc": "2026-11-09T00:00:00+00:00"})
        handed.write_text(json.dumps({"run_id": "role-c-1", "spent_usd": 2.5, "kind": "cloud-reference-b1-v1"}) + "\n",
                          encoding="utf-8")
        client = FakeClient()
        blocked = stopped(lambda: go(box, client, cap=1.0, name="blocked"))
        guard_reading = cr.spend.lead_may_spend(box.store)
        cr.spend.append_handed_back(box.store, handed)
        twice = None
        try:
            cr.spend.append_handed_back(box.store, handed)
        except cr.spend.SpendStoreError as exc:
            twice = str(exc)
        figures = cr.spend.state(box.store)
        m = go(box, FakeClient(), cap=1.0, name="after")
    ok = (bool(blocked) and "handed back" in blocked and guard_reading and not client.created and not client.counted
          and twice and figures["spent_usd"] == 2.5 and m["budget"]["earlier_reference_spent_usd"] == 2.5)
    return ok, "unappended: %r; the guard's reading %r; appended: spend %.2f counted, again: %r" % (
        blocked, bool(guard_reading), figures["spent_usd"], twice)


def proof_role_c_marker():
    """D-401 item 11: the lead's form refuses in a role C session."""
    with sandbox() as box, patch.dict(os.environ, {cr.ROLE_ENVIRONMENT: cr.ROLE_C}):
        client = FakeClient()
        why = stopped(lambda: go(box, client, cap=1.0, name="c"))
    ok = bool(why) and "role C session" in why and not client.created
    return ok, "lead's form under %s=%s: %r" % (cr.ROLE_ENVIRONMENT, cr.ROLE_C, why)


def proof_credit_carries_across_chunks():
    """D-401 item 12: each resumed chunk's limit is the credit less what the chain spent before it."""
    with sandbox() as box:
        one = go(box, FakeClient(), cap=5.0, name="k1", max_calls=2)
        two = go(box, FakeClient(), cap=5.0, name="k2", max_calls=2, resume_from=box.runs / "k1")
        chain = round(one["spent_usd"] + two["spent_usd"], 6)
        client = FakeClient()
        three = go(box, client, cap=5.0, name="k3", resume_from=box.runs / "k2", credit=chain + 0.0001)
    ok = (two["chain_spent_before_usd"] == one["spent_usd"] and three["chain_spent_before_usd"] == chain
          and abs(three["limit_usd"] - 0.0001) < 1e-9 and not client.created
          and str(three["stopped"]).startswith("cap: "))
    return ok, ("chunk 2 counts %.4f spent before it, chunk 3 %.4f; a credit of chain + 0.0001: limit %.6f, %d sent"
                % (two["chain_spent_before_usd"], three["chain_spent_before_usd"], three["limit_usd"], len(client.created)))


def proof_provider_record_kept_after_a_resume():
    """D-401 item 10: a resumed run's measurement keeps the provider's model record, not a reply record."""
    with sandbox() as box:
        go(box, FakeClient(), cap=5.0, name="p1", max_calls=2)
        m = go(box, FakeClient(), cap=5.0, name="p2", resume_from=box.runs / "p1")
    record = m["model"]["provider_record"]
    ok = record.get("display_name") == "fixture" and record.get("id") == registry_model() and "payload" not in record
    return ok, "after a resume the provider record is %s" % ({k: record.get(k) for k in ("id", "display_name")} if "payload" not in record
                                                              else "a reply record")


def proof_ledgers_found_beside_the_store():
    """D-401 item 12: with no ledgers given, the budget is read from the budget ledger beside the
    store (the main checkout's private folder, by the store's path rule), never the worktree's."""
    import loop_budget_guard  # noqa: F401
    import instance_reaper
    with sandbox() as box, patch.object(instance_reaper, "R_LEDGER", box.tmp / "no_R_ledger.jsonl"):
        beside = box.store.parent / Path(instance_reaper.PRIVATE_LEDGER).name
        beside.write_text(json.dumps({"event": "budget_open", "time_utc": "2026-11-01T00:00:00+00:00",
                                      "budget_usd": 40.0, "hard_stop_usd": 39.0}) + "\n", encoding="utf-8")
        figures = cr.check_cap(1.0, box.store, kind=cr.SCHEMA)
        found = cr.loop_ledgers(box.store)
    ok = figures["lambda"]["budget_usd"] == 40.0 and found[0] == beside   # reported, never a limit (D-S121)
    return ok, "with no ledgers given: budget %s from %s" % (figures["lambda"]["budget_usd"], found[0].name)


def proof_one_evet_one_run():
    """D-401 item 3a: a FOR_SECKIN heading that approved a run approves no other; a resume of that
    run (and of its own chain) may use it again; a heading an open intent names is refused too."""
    with sandbox() as box:
        first = go(box, FakeClient(), cap=5.0, name="first", approval=APPROVAL, max_calls=2)
        client = FakeClient()
        again = stopped(lambda: go(box, client, cap=5.0, name="again", approval=APPROVAL))
        second = go(box, FakeClient(), cap=5.0, name="second", approval=APPROVAL, max_calls=2,
                    resume_from=box.runs / "first")
        third = go(box, FakeClient(), cap=5.0, name="third", approval=APPROVAL, resume_from=box.runs / "second")
        heading = fresh_approval(box.store)
        line = [l for l in box.store.parent.joinpath(cr.FOR_SECKIN_NAME).read_text(encoding="utf-8").splitlines()
                if heading in l][0]
        cr.append_store(box.store, {"event": "intent", "run_id": "open-elsewhere", "cap_usd": 1.0,
                                    "seckin_approved_heading": line.strip(), "time_utc": "2026-11-09T00:00:00+00:00"})
        held = stopped(lambda: go(box, client, cap=1.0, name="held", approval=heading))
    ok = (bool(again) and "one evet approves one run" in again and not client.created and not client.counted
          and second["chain_run_ids_before"] == [first["run_id"]]
          and third["chain_run_ids_before"] == [first["run_id"], second["run_id"]] and third["complete"]
          and bool(held) and "open-elsewhere" in held)
    return ok, "a second fresh run under the heading: %r; resumes of its chain ran (complete %s); an open intent's: %r" % (
        again, third["complete"], held)


def proof_reading_keeps_half_a():
    truth = c_split()
    rows = [{"document_id": d, "benchmark": b} for b, ids in documents().items() for d in ids]
    kept = cr.half_a_rows(rows, truth)
    a = {d for aa, bb in truth.values() for d in aa}
    ok = {r["document_id"] for r in kept} == a and len(kept) == len(rows) // 2
    return ok, "rows %d, kept %d, all half A %s" % (len(rows), len(kept), {r["document_id"] for r in kept} == a)


PROOFS = [
    ("half B (C's own split) is never sent, and asking for it is refused", proof_half_b_refused),
    ("the prompts must be C's universe on the pinned items file", proof_universe_is_c_s),
    ("the cap stops a group before it starts, and nothing passes it", proof_cap_stops_before_spend),
    ("the check before each call holds on its own when the spend outruns the counts", proof_per_call_check_holds_alone),
    ("a failed call and a reply with no usage are counted at their worst case", proof_failed_and_unread_calls_count_worst),
    ("count_tokens failing stops before any billed call", proof_count_tokens_failing_stops),
    ("the client has no retry and no prompt is sent twice", proof_no_retry),
    ("the cap fits what is left of the total budget, the guard's reading less earlier reference spend", proof_cap_within_the_total),
    ("the prices must equal the recorded table for the resolved model", proof_prices_match_the_table),
    ("a gone, ambiguous or record-deprecated model, or no deprecations-page reading, stops before any call",
     proof_deprecated_model_stops),
    ("a planted key-shaped string or the key itself refuses the run before any call", proof_planted_key_refuses),
    ("no file, record, line or measurement carries the key", proof_no_key_in_output),
    ("the measurement and the spend are written on any exit", proof_spend_written_on_any_exit),
    ("the run folder is a new one under output/cloud_reference", proof_run_folder_under_output),
    ("the judge's seat is the registry's Anthropic model, the registry unedited, B1 keeps its system turn",
     proof_seat_is_the_registry_model_and_registry_unedited),
    ("only the prompts file J1's bar names is sent", proof_only_the_bar_s_file),
    ("plan counts and prices with no provider call", proof_plan_calls_nothing),
    ("a billed reply the code cannot read is counted once", proof_unreadable_reply_counted_once),
    ("the count margin keeps every call within its worst case", proof_count_margin_covers_the_bill),
    ("a key-shaped echo that is not the key is scrubbed", proof_key_shaped_echo_scrubbed),
    ("main()'s stdout, stderr and logs carry no key", proof_main_prints_and_logs_no_key),
    ("the model is read from the registry, never named in the module", proof_model_is_read_from_the_registry),
    ("plan builds no client and reads no model list", proof_plan_builds_no_client),
    ("an absent spend store refuses the run, never read as no spend", proof_absent_store_refuses),
    ("a provider record carrying a datetime is written as text", proof_record_with_a_datetime_is_written),
    ("the spend store is found from git, never from the working folder", proof_store_found_from_git_not_cwd),
    ("the price table's digest is recorded", proof_prices_digest_recorded),
    ("the deprecations page reading must be \"<url>, <date>, not deprecated\"", proof_deprecation_reading_has_its_form),
    ("a usage reporting cache writes stops the run, the call at its worst case", proof_cache_writes_stop_the_run),
    ("a provider refusal (no credit) stops the run cleanly at once", proof_no_credit_stops_cleanly),
    ("the reading keeps half A only", proof_reading_keeps_half_a),
    ("the key is the credential file's alone; the environment's key variables are removed, never sent",
     proof_key_only_from_the_resolver),
    ("a run given no keys builds its client from the resolver's key and records the source",
     proof_run_takes_the_resolver_s_key),
    ("a paid run needs the heading time of Seckin's yes, recorded in the spend line", proof_approval_required),
    ("the credit left bounds the worst case", proof_credit_bounds_the_worst_case),
    ("the credit gone mid-run stops cleanly; a resumed run sends only what was not answered, none twice",
     proof_credit_fault_then_resume),
    ("a chunk stops cleanly and the next one sends the rest", proof_chunks_and_resume),
    ("the environment is cleared and the base URL passed before any client, the model list's included",
     proof_model_list_built_like_the_client),
    ("a resume from a steering check is refused (its measurement, a record, its own folder)",
     proof_resume_refuses_steering),
    ("a resume from another model, other inputs or other settings is refused", proof_resume_refuses_other_runs),
    ("an intent is written under the lock and counts as running until closed; a held lock refuses",
     proof_intent_counts_while_open),
    ("a handed-back file not appended stops the lead's next paid run and the guard's next launch",
     proof_handed_back_file_blocks_the_lead),
    ("the lead's form refuses in a role C session", proof_role_c_marker),
    ("the credit carries across resumed chunks", proof_credit_carries_across_chunks),
    ("a resumed run keeps the provider's model record", proof_provider_record_kept_after_a_resume),
    ("with no ledgers given, the budget ledger beside the store is read", proof_ledgers_found_beside_the_store),
    ("one evet approves one run; a resume of that run's chain may use it again", proof_one_evet_one_run),
]


def _all_in_half_a(value, items_path):
    split = {b: (set(a), set(bb)) for b, (a, bb) in __import__("choice_read").split(
        {p["document_id"]: {"benchmark": p["benchmark"]} for p in value["prompts"]}).items()}
    return {b: (a | bb, set()) for b, (a, bb) in split.items()}


def _unchecked_universe(value, items_path):
    return {p["document_id"]: {"benchmark": p["benchmark"]} for p in value["prompts"]}


def _sent_twice(original):
    def call(client, p, *args, **kwargs):
        spent, row, over = original(client, p, *args, **kwargs)
        if row is not None and row.get("failure"):
            original(client, p, *args, **kwargs)
        return spent, row, over
    return call


def _no_finally():
    """The module with its try/finally made a plain block after the try: an exception skips the write."""
    source = Path(cr.__file__).read_text(encoding="utf-8")
    needle = "    finally:\n        measurement = {"
    if source.count(needle) != 1:
        raise RuntimeError("the finally moved, so the neutralisation cannot be applied")
    mod = types.ModuleType("cloud_reference_no_finally")
    mod.__file__ = cr.__file__
    exec(compile(source.replace(needle, "    if True:\n        measurement = {"), cr.__file__, "exec"), mod.__dict__)
    return mod


@contextlib.contextmanager
def _swap_spend_proof():
    """Runs the spend-on-exit proof against the module with no finally."""
    mod = _no_finally()
    original = PROOFS_BY_NAME["proof_spend_written_on_any_exit"]
    globals()["proof_spend_written_on_any_exit"] = lambda: original(mod)
    try:
        yield
    finally:
        globals()["proof_spend_written_on_any_exit"] = original


class _no_lock:
    def __init__(self, store):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _module_with(old, new):
    """The module with one source passage changed, for a neutralisation the patch tool cannot reach."""
    source = Path(cr.__file__).read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError("the passage moved, so the neutralisation cannot be applied")
    mod = types.ModuleType("cloud_reference_neutralised")
    mod.__file__ = cr.__file__
    exec(compile(source.replace(old, new), cr.__file__, "exec"), mod.__dict__)
    return mod


@contextlib.contextmanager
def _swap(proof_name, mod):
    """Runs one proof against a neutralised copy of the module."""
    original = PROOFS_BY_NAME[proof_name]
    globals()[proof_name] = lambda: original(mod)
    try:
        yield
    finally:
        globals()[proof_name] = original


def _record_neutral():
    mod = _module_with('        fields = record.to_dict(mode="json")', '        fields = record.to_dict()')
    mod.json_default = lambda value: (_ for _ in ()).throw(TypeError("not serialisable"))
    return mod


def _python_mode_record(client, model):
    fields = client.models.retrieve(model).to_dict()
    return {k: fields[k] for k in ("id", "display_name", "created_at") if k in fields}


PROOFS_BY_NAME = {f.__name__: f for _, f in PROOFS}

NEUTRALISATIONS = [
    ("the split puts every document in half A", "proof_half_b_refused", lambda: patch.object(cr, "halves", _all_in_half_a)),
    ("the universe not compared", "proof_universe_is_c_s", lambda: patch.object(cr, "universe", _unchecked_universe)),
    ("worst case counted as nothing", "proof_cap_stops_before_spend",
     lambda: patch.object(cr, "worst_case", lambda i, m, p: 0.0)),
    ("the check before each call removed", "proof_per_call_check_holds_alone",
     lambda: patch.object(cr, "call_fits", lambda spent, worst, cap: True)),
    ("a reply with no usage counted as free", "proof_failed_and_unread_calls_count_worst",
     lambda: patch.object(cr, "usage_tokens", lambda reply: (0, 0))),
    ("a failed count_tokens ignored", "proof_count_tokens_failing_stops",
     lambda: patch.object(FakeClient, "count_tokens", lambda self, **p: SimpleNamespace(input_tokens=1000))),
    ("a failed call sent again", "proof_no_retry", lambda: patch.object(cr, "call_one", _sent_twice(cr.call_one))),
    ("the client built with the SDK's retries", "proof_no_retry",
     lambda: patch.object(cr, "make_client", lambda key: __import__("anthropic").Anthropic(api_key=key))),
    ("the cap not held to the API ceiling", "proof_cap_within_the_total",
     lambda: patch.object(cr.spend, "api_room", lambda store, kind, worst: {"ok": True, "reason": None, "warn": False,
                                                                           "ceiling_usd": 60.0, "warning_usd": 50.0,
                                                                           "spent_usd": 0.0, "running_caps_usd": 0.0,
                                                                           "reserved_before_usd": 0.0})),
    ("the prices not compared", "proof_prices_match_the_table",
     lambda: patch.object(cr, "check_prices", lambda prices, model, path: prices)),
    ("the model's record not read", "proof_deprecated_model_stops",
     lambda: patch.object(cr, "model_record", lambda client, model: {})),
    ("every live status accepted", "proof_deprecated_model_stops",
     lambda: patch.object(cr, "resolve", lambda configured, available: ("exact", configured))),
    ("the prompt scan removed", "proof_planted_key_refuses", lambda: patch.object(cr, "scan", lambda prompts, key: None)),
    ("the key not scrubbed from errors", "proof_no_key_in_output",
     lambda: patch.object(cr, "scrub", lambda text, key: str(text))),
    ("the measurement written only on a clean exit", "proof_spend_written_on_any_exit", _swap_spend_proof),
    ("any run folder accepted", "proof_run_folder_under_output",
     lambda: patch.object(cr, "run_folder", lambda out, root: Path(out))),
    ("the system turn dropped", "proof_seat_is_the_registry_model_and_registry_unedited",
     lambda: patch.object(cr, "turns", lambda prompt: (None, prompt["user"]))),
    ("the bar's digest not compared", "proof_only_the_bar_s_file",
     lambda: patch.object(cr, "sha", lambda path: json.loads(Path(path).with_name("bar.json").read_text())["prompts_sha256"])),
    ("an unreadable reply raising out of the call", "proof_unreadable_reply_counted_once",
     lambda: patch.object(cr, "read_reply", lambda reply: (reply.content, None))),
    ("no margin on count_tokens' estimate", "proof_count_margin_covers_the_bill", lambda: patch.object(cr, "COUNT_MARGIN", 1.0)),
    ("the scrubber's regex path removed", "proof_key_shaped_echo_scrubbed",
     lambda: patch.object(__import__("agent_wrapper"), "_scrub_error", lambda text: text)),
    ("errors printed unscrubbed", "proof_main_prints_and_logs_no_key",
     lambda: patch.object(cr, "scrub", lambda text, key: str(text))),
    ("a model named in the module", "proof_model_is_read_from_the_registry",
     lambda: patch.object(cr, "seat_model", lambda root=None: "claude-opus-4-8")),
    ("plan building a client", "proof_plan_builds_no_client",
     lambda: patch.object(cr, "plan", _plan_building_a_client(cr.plan))),
    ("the record turned in python mode and json given no fallback", "proof_record_with_a_datetime_is_written",
     lambda: _swap("proof_record_with_a_datetime_is_written", _record_neutral())),
    ("the store found from the working folder", "proof_store_found_from_git_not_cwd",
     lambda: patch.object(cr, "spend_store", lambda root=None: Path.cwd() / "docs" / "loop" / "private" / cr.SPEND_STORE_NAME)),
    ("the store read as empty", "proof_cap_within_the_total", lambda: patch.object(cr.spend, "state", lambda store: {
        "spent_usd": 0.0, "running_caps_usd": 0.0, "open_runs": [], "closed_runs": 0, "handed_back": []})),
    ("an absent store read as no spend", "proof_absent_store_refuses",
     lambda: patch.object(cr.spend, "read", (lambda original: lambda path: [] if not Path(path).exists() else original(path))(cr.spend.read))),
    ("Lambda's spend held against an API run (the rule D-S121 withdrew)", "proof_cap_within_the_total",
     lambda: patch.object(cr, "check_cap", (lambda original: lambda cap, store, ledgers=None, now=None, *, kind: (
         cr.refuse(cap <= 9.0, "The cap passes what is left of the total budget"), original(cap, store, ledgers, now, kind=kind))[1])(
         cr.check_cap))),
    ("the interrupted call's worst case counted after the request", "proof_spend_written_on_any_exit",
     lambda: _swap("proof_spend_written_on_any_exit",
                   _module_with('    state["spent"] += worst\n    try:\n        reply = client.messages.create',
                                '    try:\n        reply = client.messages.create'))),
    ("the table's digest not recorded", "proof_prices_digest_recorded",
     lambda: patch.object(cr, "check_prices", (lambda original: lambda prices, model, path: {k: v for k, v in original(prices, model, path).items() if k != "table_sha256"})(cr.check_prices))),
    ("any deprecations reading accepted", "proof_deprecation_reading_has_its_form",
     lambda: patch.object(cr, "DEPRECATION_FORM", re.compile(r".*", re.S))),
    ("a document from the prompts, not the keys", "proof_universe_is_c_s",
     lambda: patch.object(cr, "universe", lambda value, items, keys: ({p["document_id"]: {"benchmark": p["benchmark"]} for p in value["prompts"]}, set()))),
    ("cache writes read as none", "proof_cache_writes_stop_the_run",
     lambda: patch.object(cr, "usage_tokens", (lambda original: lambda reply: dict(original(reply), cache_write=0) if original(reply) else None)(cr.usage_tokens))),
    ("a refusal taken for a passing failure", "proof_no_credit_stops_cleanly", lambda: patch.object(cr, "STOP_ERRORS", ())),
    ("the environment's key variables left in place", "proof_key_only_from_the_resolver",
     lambda: patch.object(cr, "KEY_ENVIRONMENT", ())),
    ("the key read from the environment", "proof_key_only_from_the_resolver",
     lambda: patch.object(cr, "resolve_key", lambda: (os.environ.get("ANTHROPIC_API_KEY"), "environment"))),
    ("the key read from the environment", "proof_run_takes_the_resolver_s_key",
     lambda: patch.object(cr, "resolve_key", lambda: (os.environ.get("ANTHROPIC_API_KEY"), "environment"))),
    ("no approval needed", "proof_approval_required",
     lambda: patch.object(cr, "check_approval", lambda a, f: {"named": a, "evet_line": "Seckin: evet (2026-11-09 18:05)",
                                                              "attested": cr.LEAD_ATTESTED})),
    ("the evet line not required", "proof_approval_required",
     lambda: patch.object(cr, "EVET_LINE", __import__("re").compile(r".*"))),
    ("the credit not held", "proof_credit_bounds_the_worst_case",
     lambda: patch.object(cr, "spend_limit", lambda cap, credit: cap)),
    ("a credit refusal taken for a passing failure", "proof_credit_fault_then_resume",
     lambda: patch.object(cr, "STOP_ERRORS", ())),
    ("answered prompts sent again", "proof_credit_fault_then_resume", lambda: patch.object(cr, "answered", lambda f: {})),
    ("answered prompts sent again", "proof_chunks_and_resume", lambda: patch.object(cr, "answered", lambda f: {})),
    ("no chunk bound", "proof_chunks_and_resume", lambda: _swap("proof_chunks_and_resume", _module_with(
        '                if max_calls is not None and state["calls"] >= max_calls:',
        '                if False:'))),
    ("the model list built by the registry helper", "proof_model_list_built_like_the_client",
     lambda: patch.object(cr, "provider_models", __import__("model_registry").list_available_models)),
    ("the environment not cleared", "proof_model_list_built_like_the_client",
     lambda: patch.object(cr, "clear_environment", lambda: None)),
    ("the steering stamp on a measurement not read", "proof_resume_refuses_steering", lambda: _swap(
        "proof_resume_refuses_steering", _module_with(
            '''    refuse(not claim_guard.is_steering(earlier), "The run''', '''    refuse(True, "The run'''))),
    ("a record's backend not read", "proof_resume_refuses_steering", lambda: _swap(
        "proof_resume_refuses_steering", _module_with(
            '''        refuse(record.get("backend") == "claude_api" and not claim_guard.is_steering(record),''',
            '''        refuse(True,'''))),
    ("a record's model not read", "proof_resume_refuses_other_runs", lambda: _swap(
        "proof_resume_refuses_other_runs", _module_with(
            '''        refuse(record.get("model_id") == model,''', '''        refuse(True,'''))),
    ("the measurement's model not read", "proof_resume_refuses_other_runs", lambda: _swap(
        "proof_resume_refuses_other_runs", _module_with(
            '''    refuse((earlier.get("model") or {}).get("resolved") == model,''', '''    refuse(True,'''))),
    ("the inputs' digests not compared", "proof_resume_refuses_other_runs", lambda: _swap(
        "proof_resume_refuses_other_runs", _module_with(
            '''        refuse(value == expected,''', '''        refuse(True,'''))),
    ("the replies' settings not compared", "proof_resume_refuses_other_runs", lambda: _swap(
        "proof_resume_refuses_other_runs", _module_with(
            '''            refuse(decoding(record),''', '''            refuse(True,'''))),
    ("open intents not counted", "proof_intent_counts_while_open",
     lambda: patch.object(cr.spend, "state", (lambda original: lambda store: dict(original(store), running_caps_usd=0.0))(
         cr.spend.state))),
    ("no lock held", "proof_intent_counts_while_open", lambda: patch.object(cr.spend, "StoreLock", _no_lock)),
    ("handed-back files not looked at", "proof_handed_back_file_blocks_the_lead",
     lambda: patch.object(cr.spend, "lead_may_spend", lambda store: None)),
    ("no role marker read", "proof_role_c_marker", lambda: patch.object(cr, "check_role", lambda lead_side: None)),
    ("the chain's spend not subtracted", "proof_credit_carries_across_chunks",
     lambda: patch.object(cr, "chain_spent", lambda earlier: 0.0)),
    ("the provider record overwritten by a reply record", "proof_provider_record_kept_after_a_resume", lambda: _swap(
        "proof_provider_record_kept_after_a_resume", _module_with(
            '''                earlier_path, earlier_record = found''',
            '''                earlier_path, earlier_record = found
                provider_record = earlier_record'''))),
    ("an evet used twice", "proof_one_evet_one_run",
     lambda: patch.object(cr, "approval_unused", lambda store, approval, chain: None)),
    ("the resumed chain not exempt", "proof_one_evet_one_run",
     lambda: patch.object(cr, "chain_runs", lambda earlier: [])),
    ("the worktree's own ledgers read", "proof_ledgers_found_beside_the_store",
     lambda: patch.object(cr, "loop_ledgers", lambda store: __import__("loop_budget_guard").reaper_ledgers())),
    ("the reading keeps every row", "proof_reading_keeps_half_a",
     lambda: patch.object(cr, "half_a_rows", lambda rows, split: rows)),
]


def run(name):
    try:
        return globals()[name]()
    except (Exception, SystemExit) as exc:
        return False, "raised %s: %s" % (type(exc).__name__, str(exc)[:200])


def main():
    failures = 0
    for what, proof in PROOFS:
        ok, detail = run(proof.__name__)
        failures += not ok
        print("%s %s: %s" % ("PASS" if ok else "FAIL", what, detail))
    for what, name, patcher in NEUTRALISATIONS:
        with patcher():
            ok, detail = run(name)
        if ok:
            failures += 1
            print("FAIL neutralised (%s) and the proof still passes: %s" % (what, detail))
            continue
        ok, _ = run(name)
        if not ok:
            failures += 1
            print("FAIL restored (%s) and the proof fails" % what)
            continue
        print("PASS neutralised (%s): FAIL; restored: PASS" % what)
    total = len(PROOFS) + len(NEUTRALISATIONS)
    print("%s cloud reference: %d of %d proofs and neutralisations pass" % ("PASS" if not failures else "FAIL",
                                                                          total - failures, total))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
