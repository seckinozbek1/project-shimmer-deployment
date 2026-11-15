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
# The recorded row the fixture's table holds (D-610): fixture rates, not the provider's, in the
# provider's proportions, so a batch figure is visibly half a single one.
FIXTURE_ROW = {"input_per_mtok": 5.0, "output_per_mtok": 25.0, "source": "fixture", "read_on": "2026-11-08",
               "cache_write_5m_per_mtok": 6.25, "cache_write_1h_per_mtok": 10.0, "cache_read_per_mtok": 0.5,
               "batch": {"input_per_mtok": 2.5, "output_per_mtok": 12.5, "cache_write_5m_per_mtok": 3.125,
                         "cache_write_1h_per_mtok": 5.0, "cache_read_per_mtok": 0.25},
               "cache": {"min_tokens": 1024, "ttl": {"single": "1h", "batch": "1h"}},
               "batch_limits": {"max_requests": 100000, "max_bytes": 268435456, "expiry_hours": 24}}


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
    prices.write_text(json.dumps({"models": {registry_model(): FIXTURE_ROW}}), encoding="utf-8")
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
        ok = (m["sent"] == 2 and m["stopped"].startswith("500 cache-write tokens with no duration reported and no cache "
                                                         "mark sent on")
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


# ---------------------------------------------------------------------------
# the gate's claim-set mode (lane/cloud-gate)

GATE_DOCS = {"cd00": "i00", "cd01": "i01", "cd02": "i02"}


def gate_files(folder, set_name="claim", drop=None, other_form=None, benchmark="contradoc", pad=""):
    """A frozen gate set file (its schema and the items of one benchmark) and a B1 prompts file of
    form b1 in both groups for every item; `drop` leaves (group, item) out, `other_form` gives one
    prompt another form."""
    folder = Path(folder)
    set_file = folder / ("%s_set_ids.json" % set_name)
    set_file.write_text(json.dumps({"schema": "shimmer-gate-%s-set-v2" % set_name, "set": set_name,
                                    benchmark: [{"document_id": d, "item_id": i, "group": d} for d, i in GATE_DOCS.items()]}),
                        encoding="utf-8")
    spec = json.loads((HERE / "b1_prompt.json").read_text(encoding="utf-8"))
    prompts, n = [], 0
    for group in cr.GROUP_ORDER:
        for d, i in GATE_DOCS.items():
            if drop == (group, i):
                continue
            n += 1
            prompts.append({"prompt_id": "c%04d" % n, "benchmark": benchmark, "document_id": d, "item_id": i,
                            "rule_id": "R1", "group": group, "form": other_form if (other_form and n == 1) else "b1",
                            "max_new_tokens": 1000, "system": "system turn %s" % group, "user": "document %s, %s%s" % (d, group, pad)})
    path = folder / ("gate_prompts_%s.json" % set_name)
    path.write_text(json.dumps({"schema": "doc-judge-prompts-v1", "kind": "doc_judge", "config_sha256": "c" * 64,
                                "b1_prompt": spec, "prompts": prompts}), encoding="utf-8")
    sync_held(path)
    return set_file, path


def held_for(prompts):
    """The fixture's held build of a prompts file: a folder whose rebuilt.json is what the fake
    rebuild writes (the real one rebuilds through doc_judge.build)."""
    return Path(prompts).with_name(Path(prompts).stem + "_held")


def sync_held(prompts):
    held = held_for(prompts)
    held.mkdir(exist_ok=True)
    (held / "rebuilt.json").write_bytes(Path(prompts).read_bytes())


def rebuild_copy(held, out):
    Path(out).write_bytes((Path(held) / "rebuilt.json").read_bytes())
    return {}


def go_gate(box, client, set_file, prompts, name="gate", mod=cr, cap=15.0, list_models=None, deprecation=DEPRECATION,
            **more):
    more.setdefault("gate_held", held_for(prompts))
    more.setdefault("gate_rebuild", rebuild_copy)
    return mod.run(prompts, None, None, None, box.runs / name, cap_usd=cap, credit_usd=CREDIT,
                   seckin_approved=fresh_approval(box.store), prices=PRICES, deprecation_checked=deprecation,
                   keys={"ANTHROPIC_API_KEY": KEY}, client=client, list_models=list_models or live({registry_model()}),
                   runs_root=box.runs, prices_path=box.prices, store=box.store, ledgers=[box.ledger], gate_set=set_file, **more)


def store_lines(box):
    return [json.loads(l) for l in box.store.read_text(encoding="utf-8").splitlines() if l.strip()]


def proof_gate_claim_set_only(mod=cr):
    """The gate mode sends B1's own prompts of the frozen claim set alone: every item in both groups,
    its kind and the set's digest in the measurement and the store; another set file (the quick
    subset's digest, or any file but the pinned claim set), a missing item, a prompt of another form
    or a J1 bar given beside it refuse before any request or store line."""
    import gate_score
    with sandbox() as box:
        set_file, prompts = gate_files(box.tmp)
        _q, _qp = gate_files(box.tmp, set_name="quick")
        before = len(store_lines(box))
        unpinned = FakeClient()
        not_pinned = stopped(lambda: go_gate(box, unpinned, set_file, prompts, name="unpinned", mod=mod))
        lines_after_refusal = len(store_lines(box))
        with patch.object(gate_score, "CLAIM_SET_SHA256", cr.sha(set_file)):
            client = FakeClient()
            m = go_gate(box, client, set_file, prompts, mod=mod)
            quick = stopped(lambda: go_gate(box, FakeClient(), _q, _qp, name="quick", mod=mod))
            (Path(box.tmp) / "drop").mkdir()
            drop_set, drop_prompts = gate_files(Path(box.tmp) / "drop", drop=("judge_reason", "i01"))
        with patch.object(gate_score, "CLAIM_SET_SHA256", cr.sha(drop_set)):
            missing = stopped(lambda: go_gate(box, FakeClient(), drop_set, drop_prompts, name="missing", mod=mod))
        (Path(box.tmp) / "form").mkdir()
        form_set, form_prompts = gate_files(Path(box.tmp) / "form", other_form="agent")
        with patch.object(gate_score, "CLAIM_SET_SHA256", cr.sha(form_set)):
            other_form = stopped(lambda: go_gate(box, FakeClient(), form_set, form_prompts, name="form", mod=mod))
            with_bar = stopped(lambda: mod.run(prompts, box.bar, None, None, box.runs / "bar", cap_usd=15.0, credit_usd=CREDIT,
                                               seckin_approved=fresh_approval(box.store), prices=PRICES,
                                               deprecation_checked=DEPRECATION, keys={"ANTHROPIC_API_KEY": KEY},
                                               client=FakeClient(), list_models=live({registry_model()}), runs_root=box.runs,
                                               prices_path=box.prices, store=box.store, ledgers=[box.ledger], gate_set=form_set,
                                               gate_held=held_for(prompts), gate_rebuild=rebuild_copy))
        lines = store_lines(box)
        set_digest = cr.sha(set_file)
    sent = sorted((p["system"].split()[-1], p["messages"][0]["content"].split(",")[0].split()[-1]) for p in client.created)
    want = sorted((g, d) for g in cr.GROUP_ORDER for d in GATE_DOCS)
    kinds = {l.get("kind") for l in lines if l.get("event") in ("intent", "close")}
    ok = (not_pinned and "frozen gate claim set" in not_pinned and not unpinned.created and lines_after_refusal == before
          and sent == want and m["kind"] == cr.GATE_SCHEMA and m["gate_set_sha256"] == set_digest
          and m["benchmark"] == "contradoc" and m["half"] is None and m["label"] == cr.GATE_LABEL and m["complete"]
          and kinds == {cr.GATE_SCHEMA}
          and quick and "frozen gate claim set" in quick and missing and "not the claim set's" in missing
          and other_form and "not B1's own" in other_form and with_bar and "takes no J1 bar" in with_bar)
    return ok, ("unpinned set file: %r (no request %s, no store line %s); sent %d of %d (group, document) pairs; kind %s, "
                "set digest recorded %s; store kinds %s; the quick subset: %r; a missing item: %r; another form: %r; a bar "
                "beside it: %r" % (not_pinned, not unpinned.created, lines_after_refusal == before, len(sent), len(want),
                                   m["kind"], m["gate_set_sha256"] == set_digest, sorted(map(str, kinds)), quick,
                                   missing, other_form, with_bar))


def proof_gate_run_keeps_the_guards():
    """The gate mode goes through every guard of the paid run: Seckin's yes, the key scan, the live
    model, the recorded prices and the API ceiling (D-441), each refusing before any request."""
    import gate_score
    with sandbox() as box:
        set_file, prompts = gate_files(box.tmp)
        (Path(box.tmp) / "keyed").mkdir()
        k_set, k_prompts = gate_files(Path(box.tmp) / "keyed")
        value = json.loads(k_prompts.read_text(encoding="utf-8"))
        value["prompts"][0]["user"] += " " + OTHER
        k_prompts.write_text(json.dumps(value), encoding="utf-8")
        sync_held(k_prompts)
        clients = [FakeClient() for _ in range(6)]
        with patch.object(gate_score, "CLAIM_SET_SHA256", cr.sha(set_file)):
            no_yes = stopped(lambda: cr.run(prompts, None, None, None, box.runs / "noyes", cap_usd=15.0, credit_usd=CREDIT,
                                            seckin_approved="FOR_SECKIN 2099-01-01 00:00", prices=PRICES,
                                            deprecation_checked=DEPRECATION, keys={"ANTHROPIC_API_KEY": KEY},
                                            client=clients[0], list_models=live({registry_model()}), runs_root=box.runs,
                                            prices_path=box.prices, store=box.store, ledgers=[box.ledger], gate_set=set_file,
                                            gate_held=held_for(prompts), gate_rebuild=rebuild_copy))
            gone = stopped(lambda: go_gate(box, clients[1], set_file, prompts, name="gone", list_models=live({"another-model"})))
            prices = stopped(lambda: cr.run(prompts, None, None, None, box.runs / "prices", cap_usd=15.0, credit_usd=CREDIT,
                                            seckin_approved=fresh_approval(box.store),
                                            prices=dict(PRICES, input_per_mtok=1.0), deprecation_checked=DEPRECATION,
                                            keys={"ANTHROPIC_API_KEY": KEY}, client=clients[2],
                                            list_models=live({registry_model()}), runs_root=box.runs, prices_path=box.prices,
                                            store=box.store, ledgers=[box.ledger], gate_set=set_file,
                                            gate_held=held_for(prompts), gate_rebuild=rebuild_copy))
            ceiling = stopped(lambda: go_gate(box, clients[3], set_file, prompts, name="ceiling", cap=70.0))
            no_page = stopped(lambda: go_gate(box, clients[5], set_file, prompts, name="nopage", deprecation=""))
        with patch.object(gate_score, "CLAIM_SET_SHA256", cr.sha(k_set)):
            keyed = stopped(lambda: go_gate(box, clients[4], k_set, k_prompts, name="keyed"))
    ok = bool(no_yes and "FOR_SECKIN" in no_yes and gone and "live list" in gone and keyed and "key-shaped" in keyed
              and prices and "not the recorded" in prices and ceiling and "ceiling" in ceiling
              and no_page and "deprecations page" in no_page and not any(c.created for c in clients))
    return ok, ("no evet: %r; a model gone from the list: %r; a key-shaped string: %r; other prices: %r; a cap past the "
                "API ceiling: %r; no deprecations-page reading: %r; requests sent %d"
                % (no_yes, gone, keyed, prices, ceiling, no_page, sum(len(c.created) for c in clients)))


def proof_gate_prompts_pinned_to_held(mod=cr):
    """The paid gate mode and its plan send or count a prompts file only when it is, byte for byte,
    the one gate-prompts rebuilds from the named held build: a file edited by hand with its ids
    intact, or no held build named, refuses before any request or store line; the rebuilt digest is
    recorded."""
    import gate_score
    with sandbox() as box:
        set_file, prompts = gate_files(box.tmp)
        value = json.loads(prompts.read_text(encoding="utf-8"))
        value["prompts"][0]["user"] += " (edited by hand)"
        prompts.write_text(json.dumps(value), encoding="utf-8")   # held/rebuilt.json keeps the built text
        before = len(store_lines(box))
        edited_client, none_client = FakeClient(), FakeClient()
        with patch.object(gate_score, "CLAIM_SET_SHA256", cr.sha(set_file)):
            edited = stopped(lambda: go_gate(box, edited_client, set_file, prompts, name="edited", mod=mod))
            no_held = stopped(lambda: go_gate(box, none_client, set_file, prompts, name="noheld", mod=mod, gate_held=None))
            edited_plan = stopped(lambda: mod.gate_plan(prompts, set_file, prices_path=box.prices, store=box.store,
                                                        held=held_for(prompts), rebuild=rebuild_copy))
            sync_held(prompts)
            m = go_gate(box, FakeClient(), set_file, prompts, name="rebuilt", mod=mod)
            digest = cr.sha(prompts)
        after = len(store_lines(box))
    ok = (edited and "not the one gate-prompts rebuilds" in edited and no_held and "--gate-held" in no_held
          and edited_plan and "not the one gate-prompts rebuilds" in edited_plan
          and not edited_client.created and not none_client.created and after == before + 2
          and m["rebuilt"]["rebuilt_sha256"] == digest and m["complete"])
    return ok, ("a hand-edited file: %r; no held build: %r; the plan of the edited file: %r; requests %d; the rebuilt file "
                "runs, its digest recorded %s" % (edited, no_held, edited_plan, len(edited_client.created) + len(none_client.created),
                                                   m["rebuilt"]["rebuilt_sha256"] == digest))


def proof_gate_resume(mod=cr):
    """A gate run resumes only a gate run on the same prompts, set and model: a J1 run refused, an
    earlier gate run on another set digest refused, and a clean resume sends only what was not
    answered, none twice."""
    import gate_score
    import shutil
    with sandbox() as box:
        set_file, prompts = gate_files(box.tmp)
        with patch.object(gate_score, "CLAIM_SET_SHA256", cr.sha(set_file)):
            first = FakeClient()
            go_gate(box, first, set_file, prompts, name="chunk", mod=mod, max_calls=2)
            second = FakeClient()
            m = go_gate(box, second, set_file, prompts, name="resumed", mod=mod, resume_from=box.runs / "chunk")
            go(box, FakeClient(), name="j1")
            cross = stopped(lambda: go_gate(box, FakeClient(), set_file, prompts, name="cross", mod=mod,
                                            resume_from=box.runs / "j1"))
            shutil.copytree(box.runs / "chunk", box.tmp / "other_set")
            other = json.loads((box.tmp / "other_set" / cr.MEASUREMENT_FILE).read_text(encoding="utf-8"))
            other["gate_set_sha256"] = "e" * 64
            (box.tmp / "other_set" / cr.MEASUREMENT_FILE).write_text(json.dumps(other), encoding="utf-8")
            other_set = stopped(lambda: go_gate(box, FakeClient(), set_file, prompts, name="otherset", mod=mod,
                                                resume_from=box.tmp / "other_set"))
    sent_first = [c["messages"][0]["content"] for c in first.created]
    sent_second = [c["messages"][0]["content"] for c in second.created]
    ok = (len(sent_first) == 2 and len(sent_second) == 4 and not set(sent_first) & set(sent_second)
          and m["complete"] and m["reused_answers"] == 2 and cross and "not a cloud-reference-gate-v1 run" in cross
          and other_set and "gate_set_sha256 differs" in other_set)
    return ok, ("first chunk %d, resumed %d, sent twice %d, reused %s; from a J1 run: %r; from another set: %r" % (
        len(sent_first), len(sent_second), len(set(sent_first) & set(sent_second)), m["reused_answers"], cross, other_set))


def proof_gate_cli_rules():
    """The CLI: --measured-output and --gate-held only in the gate mode, --measured-output only in
    plan, and the gate plan takes no --price-* (it reads the recorded prices)."""
    import io
    def exits(argv):
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                cr.main(argv)
        except SystemExit as exc:
            return exc.code
        return None
    j1 = ["plan", "--prompts", "p.json", "--bar", "b.json", "--items", "i.json", "--key", "k.json"]
    measured_j1 = exits(j1 + ["--measured-output", "m.json"])
    held_j1 = exits(j1 + ["--gate-held", "h"])
    priced = exits(["plan", "--prompts", "p.json", "--gate-set", "s.json", "--price-input-per-mtok", "5"])
    ok = measured_j1 == 2 and held_j1 == 2 and priced == 2
    return ok, "--measured-output without --gate-set exits %r; --gate-held without it %r; a gate plan with a price %r" % (
        measured_j1, held_j1, priced)


def proof_gate_plan_at_recorded_prices():
    """The gate plan gives each group's and each form's worst case at the recorded prices of the
    registry's configured model (the token estimate x COUNT_MARGIN and the full allowance on every
    call), the store's room read without a write, an expected figure from a measurement's output per
    call, and builds no client."""
    import gate_score
    with sandbox() as box:
        set_file, prompts = gate_files(box.tmp, pad=" padding" * 50000)
        measured = {"source": "fixture", "judge_direct": 200.0, "judge_reason": 400.0}
        before = box.store.read_bytes()
        with patch.object(gate_score, "CLAIM_SET_SHA256", cr.sha(set_file)), \
                patch.object(cr, "make_client", lambda key: (_ for _ in ()).throw(AssertionError("a client was built"))):
            plan = cr.gate_plan(prompts, set_file, prices_path=box.prices, store=box.store, measured=measured,
                                held=held_for(prompts), rebuild=rebuild_copy)
        unchanged = box.store.read_bytes() == before
        value = json.loads(prompts.read_text(encoding="utf-8"))
        set_digest = cr.sha(set_file)
    want, expected = {}, {}
    for g in cr.GROUP_ORDER:
        mine = [p for p in value["prompts"] if p["group"] == g]
        tokens = round(sum(len(p["system"]) + len(p["user"]) for p in mine) / 4 * 1.35)
        allowance = sum(p["max_new_tokens"] for p in mine)
        want[g] = round((tokens * 1.10 * 5.0 + allowance * 25.0) / 1e6, 2)
        expected[g] = (tokens * 5.0 + measured[g] * len(mine) * 25.0) / 1e6
    forms = plan["forms"]
    ok = (unchanged and {g: plan["groups"][g]["worst_case_usd"] for g in cr.GROUP_ORDER} == want
          and forms["direct"]["worst_case_usd"] == want["judge_direct"]
          and forms["direct_and_reasoning"]["worst_case_usd"] == round(want["judge_direct"] + want["judge_reason"], 2)
          and forms["direct"]["expected_usd"] == round(expected["judge_direct"], 2)
          and forms["direct"]["store"]["ok"] is True and forms["direct"]["store"]["ceiling_usd"] == 60.0
          and plan["prices"]["input_per_mtok"] == 5.0 and plan["gate_set_sha256"] == set_digest)
    return ok, ("worst case per group %s (wanted %s); forms %s; store unchanged %s" % (
        {g: plan["groups"][g]["worst_case_usd"] for g in cr.GROUP_ORDER}, want,
        {k: (v["worst_case_usd"], v.get("expected_usd"), v["store"].get("ok")) for k, v in forms.items()}, unchanged))


def proof_gate_prompts_keep_b1_alone(mod=cr):
    """`gate-prompts` keeps exactly the b1-form prompts doc_judge.build gives, their ids unchanged,
    and sets prompt_count to their count."""
    import doc_judge
    built = {"schema": "doc-judge-prompts-v1", "documents": {"cd00": {}}, "prompt_count": 4, "prompts": [
        {"prompt_id": "g0001", "form": "document", "group": "judge_direct"},
        {"prompt_id": "g0002", "form": "document", "group": "judge_reason"},
        {"prompt_id": "c0001", "form": "b1", "group": "judge_direct"},
        {"prompt_id": "c0002", "form": "b1", "group": "judge_reason"}]}
    with tempfile.TemporaryDirectory() as tmp:
        held = Path(tmp) / "held"
        (held / "cd00").mkdir(parents=True)
        (held / "items.json").write_text("[]", encoding="utf-8")
        seen = {}

        def fake_build(workloads, out, **kw):
            seen.update(workloads=[Path(w).name for w in workloads], **kw)
            Path(out).write_text("{}", encoding="utf-8")
            return json.loads(json.dumps(built))
        with patch.object(doc_judge, "build", fake_build):
            got = mod.build_gate_prompts(held, Path(tmp) / "out.json")
        value = json.loads((Path(tmp) / "out.json").read_text(encoding="utf-8"))
        leftover = sorted(p.name for p in Path(tmp).iterdir())
    ok = ([p["prompt_id"] for p in value["prompts"]] == ["c0001", "c0002"] and value["prompt_count"] == 2
          and got["prompt_count"] == 2 and seen.get("b1") is True and seen.get("workloads") == ["cd00"]
          and Path(seen["config_path"]).name == "doc_judge_prompt_j1.json" and leftover == ["held", "out.json"])
    return ok, "kept %s, count %s, built with b1 %s under %s; folder left %s" % (
        [p["prompt_id"] for p in value["prompts"]], value["prompt_count"], seen.get("b1"),
        Path(seen.get("config_path", "")).name, leftover)


def _gate_module_with(old, new):
    source = Path(cr.__file__).read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError("the passage moved, so the neutralisation cannot be applied")
    mod = types.ModuleType("cloud_reference_gate_neutralised")
    mod.__file__ = cr.__file__
    exec(compile(source.replace(old, new), cr.__file__, "exec"), mod.__dict__)
    return mod


# ---------------------------------------------------------------------------
# D-610 cuts 1 and 2: the batch route and prompt caching, on fakes only


class FakeClock:
    """A clock the fake sleep moves; it raises once a batch loop has run far past any deadline, so a
    neutralised deadline ends the proof instead of looping."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self.t > 400000:
            raise RuntimeError("the batch loop ran unbounded")


def reply_text(cid):
    return '{"items": [], "for": "%s"}' % cid


class FakeBatchClient(FakeClient):
    """FakeClient with messages.batches. `ends_after` polls end a batch (None: never, unless
    cancelled and `cancel_ends`); `missing` and `errored` are request positions with no result or an
    errored one; `shuffle` reverses the results' order; `usage` per succeeded result as FakeClient's,
    or `usage_fields` merged into it."""

    def __init__(self, ends_after=2, cancel_ends=True, missing=(), errored=(), shuffle=False, usage_fields=None,
                 system_tokens=1000, **kw):
        super().__init__(**kw)
        self.batch_requests, self.cancelled, self.polls = [], [], 0
        self.ends_after, self.cancel_ends, self.missing, self.errored = ends_after, cancel_ends, set(missing), set(errored)
        self.shuffle, self.usage_fields, self.system_tokens = shuffle, usage_fields or {}, system_tokens
        self.batches = SimpleNamespace(create=self._create, retrieve=self._retrieve_batch, results=self._results,
                                       cancel=self._cancel)

    def count_tokens(self, **params):
        if params.get("messages") == [{"role": "user", "content": "."}]:
            self.counted.append(params)
            return SimpleNamespace(input_tokens=self.system_tokens)
        return super().count_tokens(**params)

    def _create(self, requests):
        self.batch_requests.append(json.loads(json.dumps(requests)))
        return SimpleNamespace(id="msgbatch_fixture%d" % len(self.batch_requests), processing_status="in_progress")

    def _ended(self, batch_id):
        n = int(batch_id.rsplit("fixture", 1)[1])
        return ((self.ends_after is not None and self.polls >= self.ends_after * n)
                or (batch_id in self.cancelled and self.cancel_ends))

    def _retrieve_batch(self, batch_id):
        self.polls += 1
        return SimpleNamespace(id=batch_id, processing_status="ended" if self._ended(batch_id) else "in_progress")

    def _cancel(self, batch_id):
        self.cancelled.append(batch_id)
        return SimpleNamespace(id=batch_id, processing_status="canceling")

    def _results(self, batch_id):
        requests = self.batch_requests[int(batch_id.rsplit("fixture", 1)[1]) - 1]
        out = []
        for i, r in enumerate(requests):
            if i in self.missing:
                continue
            if i in self.errored:
                out.append(SimpleNamespace(custom_id=r["custom_id"], result=SimpleNamespace(type="errored")))
                continue
            if batch_id in self.cancelled and i >= len(requests) // 2:
                out.append(SimpleNamespace(custom_id=r["custom_id"], result=SimpleNamespace(type="canceled")))
                continue
            usage = SimpleNamespace(**dict({"input_tokens": 1000, "output_tokens": self.output_tokens,
                                            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                                            "service_tier": "batch"}, **self.usage_fields))
            message = SimpleNamespace(content=[SimpleNamespace(type="text", text=reply_text(r["custom_id"]))],
                                      stop_reason="end_turn", usage=usage)
            out.append(SimpleNamespace(custom_id=r["custom_id"], result=SimpleNamespace(type="succeeded", message=message)))
        return list(reversed(out)) if self.shuffle else out


def go_batch(box, client, deadline=3600, name="batch", clock=None, **kw):
    clock = clock or FakeClock()
    return go(box, client, name=name, route="batch", batch_deadline_seconds=deadline, clock=clock, sleep=clock.sleep, **kw)


def batch_rows(m):
    return [r for r in m["rows"] if r.get("route") == "batch"]


def proof_batch_bytes_equal_single(mod=cr):
    """Every batch request's params are, byte for byte as JSON, the request the single route sent for
    the same prompt, with and without a cache mark."""
    with sandbox() as box:
        out = []
        for tokens in (1000, 2000):   # below and above the fixture's 1024-token minimum
            single, batch = FakeBatchClient(system_tokens=tokens), FakeBatchClient(system_tokens=tokens)
            a = go(box, single, cap=5.0, name="single%d" % tokens, mod=mod)
            b = go_batch(box, batch, cap=5.0, name="batch%d" % tokens, mod=mod)
            sent = [json.dumps(p, sort_keys=True) for p in single.created]
            batched = [json.dumps(r["params"], sort_keys=True) for req in batch.batch_requests for r in req]
            marked = sum(1 for p in single.created if isinstance(p.get("system"), list))
            out.append((sent == batched and len(sent) == a["sent"] == b["sent"] > 0
                        and (marked > 0) == (tokens >= 1024), len(sent), len(batched), marked))
        ok = all(o[0] for o in out)
        return ok, "; ".join("%d single and %d batched requests identical, %d marked" % o[1:] for o in out)


def proof_batch_reserve_at_batch_price(mod=cr):
    """Under a cap that holds a group's worst case at the batch rates but not at the single rates,
    the batch route sends every call and the single route none; the spend line names the route, the
    batch rates and the batch ids, and the spend is the batch-rate bill."""
    with sandbox() as box:
        single = go(box, FakeClient(), cap=0.2, name="single", mod=mod)
        client = FakeBatchClient()
        batch = go_batch(box, client, cap=0.2, mod=mod)
        closes = [l for l in store_lines(box) if l.get("event") == "close" and l.get("run_folder") == "batch"]
        line = closes[-1] if closes else {}
        bill = sum(cr.cost(1000, 200, {"input_per_mtok": 2.5, "output_per_mtok": 12.5}) for _ in batch_rows(batch))
        ok = (single["sent"] == 0 and batch["sent"] == 16 and abs(batch["spent_usd"] - bill) < 1e-9
              and line.get("route") == "batch" and line.get("rates", {}).get("input_per_mtok") == 2.5
              and line.get("batch_ids") == ["msgbatch_fixture1", "msgbatch_fixture2"])
        return ok, "single sent %d under 0.20 USD, batch sent %d, spent %.4f (bill %.4f), line route %s ids %s" % (
            single["sent"], batch["sent"], batch["spent_usd"], bill, line.get("route"), line.get("batch_ids"))


def proof_batch_deadline_cancels(mod=cr):
    """A batch still running at its deadline is cancelled once and recorded: its id in batches.json
    and the spend line, the answered half settled, the canceled half a no_answer at no cost; one that
    does not end even after the cancel is given up within the grace, every call kept at its worst."""
    with sandbox() as box:
        client = FakeBatchClient(ends_after=None, cancel_ends=True)
        m = go_batch(box, client, deadline=600, cap=5.0, name="late", mod=mod)
        held = json.loads((box.runs / "late" / "batches.json").read_text(encoding="utf-8"))
        rows = batch_rows(m)
        answered = [r for r in rows if not r.get("no_answer")]
        canceled = [r for r in rows if r.get("failure") == "no_answer: canceled"]
        first = (client.cancelled == ["msgbatch_fixture1"] and "deadline" in (m["stopped"] or "")
                 and held[0]["id"] == "msgbatch_fixture1" and held[0]["cancelled"] and len(answered) == 4
                 and len(canceled) == 4 and all(r["cost_usd"] == 0.0 for r in canceled))
        stuck = FakeBatchClient(ends_after=None, cancel_ends=False)
        clock = FakeClock()
        s = go_batch(box, stuck, deadline=600, cap=5.0, name="stuck", clock=clock, mod=mod)
        worst = cr.worst_case(1000, 1000, {"input_per_mtok": 2.5, "output_per_mtok": 12.5})
        second = (stuck.cancelled == ["msgbatch_fixture1"] and all(r.get("no_answer") for r in batch_rows(s))
                  and abs(s["spent_usd"] - worst * len(batch_rows(s))) < 1e-9
                  and clock.t <= 600 + cr.BATCH_CANCEL_GRACE_SECONDS + cr.BATCH_POLL_SECONDS
                  and s["batches"][0]["id"] == "msgbatch_fixture1")
        return first and second, ("cancelled %s, %d answered, %d canceled at no cost; stuck batch given up at %.0f s, "
                                  "%d calls at their worst, spent %.4f" % (client.cancelled, len(answered), len(canceled),
                                                                           clock.t, len(batch_rows(s)), s["spent_usd"]))


def proof_batch_missing_result_is_no_answer(mod=cr):
    """Results joined by custom id, in any order: each reply is its own prompt's; a missing result
    is a no_answer at its worst case, an errored one a no_answer at no cost, and neither is sent
    again (one batch a group, no single request)."""
    with sandbox() as box:
        client = FakeBatchClient(missing=(1, 2), errored=(3,), shuffle=True)
        m = go_batch(box, client, cap=5.0, mod=mod)
        rows = batch_rows(m)
        ids = {cid: p for cid, p in cr.custom_ids([{"prompt_id": r["prompt_id"]} for r in rows], m["run_id"]).items()}
        by_prompt = {p["prompt_id"]: cid for cid, p in ids.items()}
        joined = all(r["reply"]["sha256"] == hashlib.sha256(reply_text(by_prompt[r["prompt_id"]]).encode()).hexdigest()
                     for r in rows if not r.get("no_answer"))
        missing = [r for r in rows if (r.get("failure") or "").startswith("no_answer: no result")]
        errored = [r for r in rows if r.get("failure") == "no_answer: errored"]
        worst = cr.worst_case(1000, 1000, {"input_per_mtok": 2.5, "output_per_mtok": 12.5})
        each = cr.cost(1000, 200, {"input_per_mtok": 2.5, "output_per_mtok": 12.5})
        spent = len(missing) * worst + (len(rows) - len(missing) - len(errored)) * each
        records = [json.loads(p.read_text(encoding="utf-8")) for p in (box.runs / "batch").rglob("model_replies/*.json")]
        ok = (joined and len(missing) == 4 and len(errored) == 2 and all(r["cost_usd"] == 0.0 for r in errored)
              and all(r["cost_usd"] == round(worst, 6) for r in missing)
              and abs(m["spent_usd"] - spent) < 1e-9 and not client.created and len(client.batch_requests) == 2
              and sum(1 for r in records if not r.get("backend_ok")) == 6)
        return ok, "joined %s, %d missing at worst, %d errored at no cost, spent %.4f of %.4f, %d batches, %d single" % (
            joined, len(missing), len(errored), m["spent_usd"], spent, len(client.batch_requests), len(client.created))


RATES = {"input_per_mtok": 5.0, "output_per_mtok": 25.0, "cache_write_5m_per_mtok": 6.25,
         "cache_write_1h_per_mtok": 10.0, "cache_read_per_mtok": 0.5}


def usage_reply(**fields):
    return SimpleNamespace(usage=SimpleNamespace(**fields))


def proof_cache_priced(mod=cr):
    """Cache reads and writes are priced from the usage, by duration; a run whose system turn reaches
    the minimum and repeats marks it (5 minutes single, 1 hour batch) and bills reads and writes; a
    prefix under the minimum is never marked."""
    got = mod.usage_cost(usage_reply(input_tokens=100, output_tokens=50, cache_read_input_tokens=2000,
                                     cache_creation_input_tokens=1500,
                                     cache_creation=SimpleNamespace(ephemeral_5m_input_tokens=500,
                                                                    ephemeral_1h_input_tokens=1000)), RATES)
    want = (100 * 5.0 + 50 * 25.0 + 2000 * 0.5 + 500 * 6.25 + 1000 * 10.0) / 1e6
    unit = abs(got["cost_usd"] - want) < 1e-12 and got["input_tokens"] == 3600
    with sandbox() as box:
        client = FakeBatchClient(system_tokens=2000, usage_fields={"cache_read_input_tokens": 1500,
                                                                    "cache_creation_input_tokens": 0})
        b = go_batch(box, client, cap=5.0, mod=mod)
        ttls = {r["params"]["system"][0]["cache_control"]["ttl"] for req in client.batch_requests for r in req
                if isinstance(r["params"].get("system"), list)}
        b_rates = {"input_per_mtok": 2.5, "output_per_mtok": 12.5, "cache_read_per_mtok": 0.25}
        bill = sum((1000 * 2.5 + 200 * 12.5 + 1500 * 0.25) / 1e6 for _ in batch_rows(b))
        run_ok = abs(b["spent_usd"] - bill) < 1e-9 and ttls == {"1h"} and b["stopped"] is None
        short = FakeBatchClient(system_tokens=1000)
        go(box, short, cap=5.0, name="short", mod=mod)
        unmarked = all(not isinstance(p.get("system"), list) for p in short.created)
        long = FakeBatchClient(system_tokens=2000)
        go(box, long, cap=5.0, name="long", mod=mod)
        single_ttls = {p["system"][0]["cache_control"]["ttl"] for p in long.created if isinstance(p.get("system"), list)}
    ok = unit and run_ok and unmarked and single_ttls == {"1h"}
    return ok, ("unit %.6f of %.6f; batch run spent %.4f of %.4f, marks %s, stopped %r; short prefix unmarked %s; "
                "single marks %s" % (got["cost_usd"], want, b["spent_usd"], bill, sorted(ttls), b["stopped"], unmarked,
                                     sorted(single_ttls)))


def proof_unpriceable_usage_halts(mod=cr):
    """A usage field this code cannot price stops the run with the call at its worst case: an unknown
    field carrying a value, a service tier not the route's; an unknown field holding zeros does not."""
    with sandbox() as box:
        tool = go_batch(box, FakeBatchClient(usage_fields={"server_tool_use": SimpleNamespace(web_search_requests=2)}),
                        cap=5.0, name="tool", mod=mod)
        tier = go_batch(box, FakeBatchClient(usage_fields={"service_tier": "priority"}), cap=5.0, name="tier", mod=mod)
        zero = go_batch(box, FakeBatchClient(usage_fields={"server_tool_use": SimpleNamespace(web_search_requests=0)}),
                        cap=5.0, name="zero", mod=mod)
        worst = cr.worst_case(1000, 1000, {"input_per_mtok": 2.5, "output_per_mtok": 12.5})
        kept = all(r["cost_usd"] == round(worst, 6) for r in batch_rows(tool) if not r.get("no_answer"))
        ok = ("server_tool_use" in (tool["stopped"] or "") and "service tier priority" in (tier["stopped"] or "")
              and kept and zero["stopped"] is None and len(batch_rows(tool)) == 8)
        return ok, "tool %r; tier %r; zeros stopped %r; tool calls at their worst %s" % (
            (tool["stopped"] or "")[:80], (tier["stopped"] or "")[:60], zero["stopped"], kept)




# ---------------------------------------------------------------------------
# D-610, the checker's round 1 (items 2 to 8)


class RoundTwoClient(FakeBatchClient):
    """FakeBatchClient that can also: raise KeyboardInterrupt in batches.create after the provider has
    taken the batch (`create_interrupt`); list batches (`decoy`: one more ended batch of another run);
    answer every request even before the batch ends (`late_results`); and read the run folder's
    batches.json at the first poll (`watch`)."""

    def __init__(self, create_interrupt=False, decoy=False, late_results=False, watch=None, **kw):
        super().__init__(**kw)
        self.create_interrupt, self.decoy, self.late_results, self.watch = create_interrupt, decoy, late_results, watch
        self.seen, self.results_read, self.created_at, self.at_create = None, 0, {}, None
        self.batches.list = self._list

    def _create(self, requests):
        if self.watch is not None and self.at_create is None:
            # what a crash at this moment would leave on disk (the process gone, no handler run)
            path = Path(self.watch) / "batches.json"
            self.at_create = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        batch = super()._create(requests)
        self.created_at[batch.id] = datetime.now(timezone.utc)
        if self.create_interrupt and len(self.batch_requests) == 1:
            raise KeyboardInterrupt()
        return batch

    def _retrieve_batch(self, batch_id):
        if self.watch is not None and self.seen is None:
            self.seen = json.loads((Path(self.watch) / "batches.json").read_text(encoding="utf-8"))
        return super()._retrieve_batch(batch_id)

    def _ended(self, batch_id):
        if batch_id == "msgbatch_decoy":
            return True
        return super()._ended(batch_id)

    def _results(self, batch_id):
        self.results_read += 1
        if batch_id == "msgbatch_decoy":
            requests = self.batch_requests[0]
            return [SimpleNamespace(custom_id="rDECOYDECOY12_" + r["custom_id"][14:], result=SimpleNamespace(type="errored"))
                    for r in requests]
        if self.late_results:
            saved, self.cancelled = self.cancelled, []
            try:
                return super()._results(batch_id)
            finally:
                self.cancelled = saved
        return super()._results(batch_id)

    def _list(self, limit=20):
        out = [SimpleNamespace(id=b, created_at=self.created_at[b], processing_status="ended")
               for b in self.created_at]
        if self.decoy:
            out.append(SimpleNamespace(id="msgbatch_decoy", created_at=datetime.now(timezone.utc), processing_status="ended"))
        return out


B_PRICES = {"input_per_mtok": 2.5, "output_per_mtok": 12.5}


def interrupted(call):
    try:
        call()
    except KeyboardInterrupt:
        return True
    return False


def proof_batch_create_interrupt_keeps_worst(mod=cr):
    """A KeyboardInterrupt in batches.create (the provider took the batch, no id came back): the close
    line keeps every call of the batch at its worst case with the run's custom-id prefix; batches.json
    holds the record; `reconcile` finds the batch by its prefix among another run's; a resume sends none
    of those calls again."""
    with sandbox() as box:
        client = RoundTwoClient(create_interrupt=True, decoy=True, watch=box.runs / "lost")
        raised = interrupted(lambda: go_batch(box, client, cap=5.0, name="lost", mod=mod))
        close = [l for l in store_lines(box) if l.get("event") == "close" and l.get("run_folder") == "lost"][-1]
        worst = cr.worst_case(1000, 1000, B_PRICES)
        held = json.loads((box.runs / "lost" / "batches.json").read_text(encoding="utf-8"))
        m = measurement(box, "lost")
        found = mod.reconcile(box.runs / "lost", client)
        outcome = found["batches"][0]
        again = RoundTwoClient()
        r = go_batch(box, again, cap=5.0, name="after", resume_from=box.runs / "lost", mod=mod)
        resent = {req["custom_id"][14:] for req in again.batch_requests[0]} & {req["custom_id"][14:] for req in client.batch_requests[0]} if again.batch_requests else set()
        ok = (raised and abs(close["spent_usd"] - 8 * worst) < 1e-6 and close["batch_ids"] == [None]
              and close["batch_custom_id_prefixes"] == [held[0]["custom_id_prefix"]]
              and held[0]["status"].startswith("create interrupted") and client.at_create
              and client.at_create[0].get("custom_id_prefix") == held[0]["custom_id_prefix"]
              and client.at_create[0].get("status") == "sending" and sum(1 for x in m["rows"] if x.get("no_answer")) == 8
              and outcome["outcome"] == "found" and outcome["found"][0]["id"] == "msgbatch_fixture1"
              and not resent and r["carried_no_answer"] == 8)
        return ok, ("interrupted %s, close %.4f (8 x %.4f), ids %s, record %r, reconcile %s %s, resumed %d carried, "
                    "%d resent" % (raised, close["spent_usd"], worst, close["batch_ids"], held[0]["status"][:20],
                                   outcome["outcome"], [f["id"] for f in outcome.get("found", [])],
                                   r["carried_no_answer"], len(resent)))


def proof_resume_keeps_no_answer(mod=cr):
    """A resume does not send the earlier run's no_answer calls; --resend-no-answer sends them."""
    with sandbox() as box:
        go_batch(box, FakeBatchClient(missing=(1, 2)), cap=5.0, name="first", mod=mod)
        held = FakeClient()
        kept = go(box, held, cap=5.0, name="kept", resume_from=box.runs / "first", mod=mod)
        sent = FakeClient()
        again = go(box, sent, cap=5.0, name="again", resume_from=box.runs / "first", resend_no_answer=True, mod=mod)
        carried = [x for x in kept["rows"] if x.get("no_answer")]
        ok = (len(held.created) == 0 and kept["carried_no_answer"] == 4 and len(carried) == 4
              and all(x["cost_usd"] == 0.0 for x in carried) and len(sent.created) == 4 and again["carried_no_answer"] == 0)
        return ok, "resumed: %d sent, %d carried; with --resend-no-answer: %d sent" % (
            len(held.created), kept["carried_no_answer"], len(sent.created))


def proof_late_results_stay_worst(mod=cr):
    """A batch given up before it ended keeps every call at its worst case, though the provider would
    answer them later: its results are not read in the run, and reconcile records what it later billed
    without changing the spend line."""
    with sandbox() as box:
        client = RoundTwoClient(ends_after=None, cancel_ends=False, late_results=True)
        m = go_batch(box, client, deadline=600, cap=5.0, name="late", mod=mod)
        worst = cr.worst_case(1000, 1000, B_PRICES)
        rows = batch_rows(m)
        close = [l for l in store_lines(box) if l.get("event") == "close" and l.get("run_folder") == "late"][-1]
        read_in_run = client.results_read
        client.cancel_ends = True   # the provider ends it later
        found = mod.reconcile(box.runs / "late", client)["batches"][0]
        after = [l for l in store_lines(box) if l.get("event") == "close" and l.get("run_folder") == "late"][-1]
        ok = (read_in_run == 0 and all(x.get("no_answer") and x["cost_usd"] == round(worst, 6) for x in rows)
              and abs(close["spent_usd"] - 8 * worst) < 1e-6 and found["outcome"] == "ended after it was given up"
              and found["billed_usd"] > 0 and after == close)
        return ok, "results read in the run %d; %d calls at %.4f; close %.4f; reconcile %r billed %s" % (
            read_in_run, len(rows), worst, close["spent_usd"], found["outcome"], found.get("billed_usd"))


def proof_batch_id_written_at_once(mod=cr):
    """batches.json names the batch id while the batch is still running, before any result."""
    with sandbox() as box:
        client = RoundTwoClient(watch=box.runs / "watched")
        go_batch(box, client, cap=5.0, name="watched", mod=mod)
        seen = client.seen or [{}]
        ok = seen[0].get("id") == "msgbatch_fixture1" and seen[0].get("status") == "in_progress"
        return ok, "at the first poll batches.json read %r" % ({k: seen[0].get(k) for k in ("id", "status")},)


def proof_reserve_rates_safe_side(mod=cr):
    """A marked call's worst case counts every input token at the higher of the input and the 1-hour
    write rate; an unmarked call at the input rate."""
    with sandbox() as box:
        client = FakeBatchClient(system_tokens=2000)
        m = go(box, client, cap=5.0, name="reserve", mod=mod)
        marked = cr.worst_case(1000, 1000, {"input_per_mtok": 10.0, "output_per_mtok": 25.0})
        plain = cr.worst_case(1000, 1000, {"input_per_mtok": 5.0, "output_per_mtok": 25.0})
        rows = m["rows"]
        ok = (all(x["worst_case_usd"] == round(marked if x.get("cache_ttl") else plain, 6) for x in rows)
              and any(x.get("cache_ttl") for x in rows) and any(not x.get("cache_ttl") for x in rows))
        return ok, "marked calls reserved at %.4f, unmarked at %.4f: %s" % (marked, plain, sorted({x["worst_case_usd"] for x in rows}))


def proof_batch_deadline_below_expiry(mod=cr):
    """A batch deadline at the provider's 24-hour expiry is refused before any request; just below it runs."""
    with sandbox() as box:
        client = FakeBatchClient()
        why = stopped(lambda: go_batch(box, client, deadline=24 * 3600, cap=5.0, name="day", mod=mod))
        fine = go_batch(box, FakeBatchClient(), deadline=24 * 3600 - 60, cap=5.0, name="under", mod=mod)
        ok = bool(why) and "expiry" in why and not client.batch_requests and not client.counted and fine["sent"] == 16
        return ok, "24 h: %r; just under: sent %d" % (why, fine["sent"])


def proof_batch_limits_refuse(mod=cr):
    """A batch over the recorded request count or byte size is refused before it is sent."""
    with sandbox() as box:
        out = []
        for name, change in (("count", {"max_requests": 3}), ("bytes", {"max_bytes": 100})):
            row = json.loads(json.dumps(FIXTURE_ROW))
            row["batch_limits"].update(change)
            box.prices.write_text(json.dumps({"models": {registry_model(): row}}), encoding="utf-8")
            client = FakeBatchClient()
            why = stopped(lambda: go_batch(box, client, cap=5.0, name=name, mod=mod))
            out.append((bool(why) and "over the provider's limit" in why and not client.batch_requests, why))
        return all(o[0] for o in out), "; ".join(repr(o[1])[:90] for o in out)


def proof_cache_write_split_must_add_up(mod=cr):
    """Cache writes whose durations do not add up to the reported total cannot be priced: the run stops."""
    bad = usage_reply(input_tokens=10, output_tokens=5, cache_creation_input_tokens=500,
                      cache_creation=SimpleNamespace(ephemeral_5m_input_tokens=100, ephemeral_1h_input_tokens=100))
    unit = stopped(lambda: mod.usage_cost(bad, RATES), mod.Unpriceable)
    with sandbox() as box:
        m = go_batch(box, FakeBatchClient(usage_fields={
            "cache_creation_input_tokens": 500,
            "cache_creation": SimpleNamespace(ephemeral_5m_input_tokens=100, ephemeral_1h_input_tokens=100)}),
            cap=5.0, name="split", mod=mod)
    ok = bool(unit) and "not the sum" in (m["stopped"] or "")
    return ok, "unit %r; run %r" % (unit, (m["stopped"] or "")[:80])


def _params_for_before_d610(prompt, model):
    # The function as it stood at 53b3e25d (before D-610), copied verbatim: the golden body.
    """The request a prompt becomes: its user turn, and its system turn when it has one."""
    system, user = cr.turns(prompt)
    params = {"model": model, "messages": [{"role": "user", "content": user}]}
    if system is not None:
        params["system"] = system
    return params


def proof_unmarked_bodies_as_before(mod=cr):
    """With nothing marked, every single-route body is, byte for byte as JSON, what the module sent
    before D-610: messages.create(max_tokens=allowance, **params_for(p, model))."""
    with sandbox() as box:
        client = FakeClient()
        go(box, client, cap=5.0, name="golden", mod=mod)
        prompts = {p["user"]: p for p in box.value["prompts"]}
        golden = [json.dumps(dict(max_tokens=int(prompts[b["messages"][0]["content"]]["max_new_tokens"]),
                                  **_params_for_before_d610(prompts[b["messages"][0]["content"]], registry_model())),
                             sort_keys=True) for b in client.created]
        sent = [json.dumps(b, sort_keys=True) for b in client.created]
        ok = sent == golden and len(sent) == 16
        return ok, "%d bodies, identical to the pre-D-610 body: %s" % (len(sent), sent == golden)


def proof_batch_close_line_read_by_the_readers(mod=cr):
    """A batch run's close line (route, rates, batch_ids, custom-id prefixes) is read as spend by the
    spend reader (state, api_room), passes the standing-orders API check, and counts in the reaper's
    API warning; its fields are all declared in CLOSE_LINE_FIELDS."""
    import cloud_reference_spend as spend
    import instance_reaper
    import standing_orders_check
    with sandbox() as box:
        m = go_batch(box, FakeBatchClient(), cap=5.0, name="readers", mod=mod)
        close = [l for l in store_lines(box) if l.get("event") == "close" and l.get("run_folder") == "readers"][-1]
        figures = spend.state(box.store)
        room = spend.api_room(box.store, cr.SCHEMA, 1.0)
        ctx = SimpleNamespace(private_text=lambda name: (box.store.parent / name).read_text(encoding="utf-8")
                              if (box.store.parent / name).exists() else None)
        api_ok, api_detail = standing_orders_check.check_api_key(ctx, names=["given by a proof"])
        lines = box.store.read_text(encoding="utf-8")
        box.store.write_text(lines + json.dumps({"event": "ceiling", "time_utc": "2026-11-13T12:00:00+00:00",
                                                 "ceiling_usd": 60.0, "warning_usd": 0.01}) + "\n", encoding="utf-8")
        due = instance_reaper.warnings_due({}, box.store)
        undeclared = sorted(set(close) - set(cr.CLOSE_LINE_FIELDS))
        ok = (close["route"] == "batch" and close["batch_ids"] == ["msgbatch_fixture1", "msgbatch_fixture2"]
              and abs(figures["spent_usd"] - m["spent_usd"]) < 1e-9 and room["ok"]
              and abs(room["spent_usd"] - m["spent_usd"]) < 1e-9 and api_ok and not undeclared
              and any(k == "API" and abs(s - m["spent_usd"]) < 1e-9 for k, _, s, _ in due))
        return ok, "state %.4f, api_room ok %s, api check %s (%s), reaper API warning %s, undeclared %s" % (
            figures["spent_usd"], room["ok"], api_ok, api_detail[:60], [d[0] for d in due], undeclared)


# ---------------------------------------------------------------------------
# D-610, the checker's round 2


class FollowInterruptClient(RoundTwoClient):
    """The provider takes the batch; the run is interrupted at the first read of it."""

    def _retrieve_batch(self, batch_id):
        raise KeyboardInterrupt()


def proof_interrupt_while_following(mod=cr):
    """A KeyboardInterrupt while the batch is followed (after create): the batch is cancelled once, every
    planned call is a no_answer at its worst case in the run and its close line, and a resume sends none
    of them again."""
    with sandbox() as box:
        client = FollowInterruptClient()
        raised = interrupted(lambda: go_batch(box, client, cap=5.0, name="followed", mod=mod))
        worst = cr.worst_case(1000, 1000, B_PRICES)
        m = measurement(box, "followed")
        close = [l for l in store_lines(box) if l.get("event") == "close" and l.get("run_folder") == "followed"][-1]
        held = json.loads((box.runs / "followed" / "batches.json").read_text(encoding="utf-8"))
        again = RoundTwoClient()
        r = go_batch(box, again, cap=5.0, name="after", resume_from=box.runs / "followed", mod=mod)
        first = {q["custom_id"][14:] for q in client.batch_requests[0]}
        resent = sum(1 for req in again.batch_requests for q in req if q["custom_id"][14:] in first)
        lost = [x for x in m["rows"] if x.get("no_answer")]
        ok = (raised and client.cancelled == ["msgbatch_fixture1"] and len(lost) == 8
              and all(x["cost_usd"] == round(worst, 6) and x["batch_id"] == "msgbatch_fixture1" for x in lost)
              and abs(close["spent_usd"] - 8 * worst) < 1e-6 and close["batch_ids"] == ["msgbatch_fixture1"]
              and held[0]["status"].startswith("interrupted while followed") and resent == 0
              and r["carried_no_answer"] == 8)
        return ok, "interrupted %s, cancelled %s, %d no_answer at %.4f, close %.4f, resumed %d carried, %d resent" % (
            raised, client.cancelled, len(lost), worst, close["spent_usd"], r["carried_no_answer"], resent)


def proof_gate_plan_batch_figures(mod=cr):
    """On invented groups, the gate plan's batch_worst_case_usd and batch_expected_usd are the sums of the
    groups' token estimates (x COUNT_MARGIN for the worst case) and allowances, or measured output, at
    the recorded batch rates."""
    import gate_score
    with sandbox() as box:
        set_file, prompts = gate_files(box.tmp, pad=" padding" * 40000)
        measured = {"source": "fixture", "judge_direct": 300.0, "judge_reason": 700.0}
        with patch.object(gate_score, "CLAIM_SET_SHA256", cr.sha(set_file)):
            plan = mod.gate_plan(prompts, set_file, prices_path=box.prices, store=box.store, measured=measured,
                                 held=held_for(prompts), rebuild=rebuild_copy)
        value = json.loads(prompts.read_text(encoding="utf-8"))
    worst, expected = {}, {}
    for g in cr.GROUP_ORDER:
        mine = [p for p in value["prompts"] if p["group"] == g]
        tokens = round(sum(len(p["system"]) + len(p["user"]) for p in mine) / 4 * 1.35)
        allowance = sum(p["max_new_tokens"] for p in mine)
        worst[g] = (tokens * 1.10 * 2.5 + allowance * 12.5) / 1e6
        expected[g] = (tokens * 2.5 + measured[g] * len(mine) * 12.5) / 1e6
    forms = plan["forms"]
    both = ("judge_direct", "judge_reason")
    ok = (forms["direct"]["batch_worst_case_usd"] == round(worst["judge_direct"], 2)
          and forms["direct"]["batch_expected_usd"] == round(expected["judge_direct"], 2)
          and forms["direct_and_reasoning"]["batch_worst_case_usd"] == round(sum(worst[g] for g in both), 2)
          and forms["direct_and_reasoning"]["batch_expected_usd"] == round(sum(expected[g] for g in both), 2)
          and forms["direct_and_reasoning"]["batch_worst_case_usd"] < forms["direct_and_reasoning"]["worst_case_usd"])
    return ok, "batch worst %s, batch expected %s (wanted %s and %s)" % (
        {k: v.get("batch_worst_case_usd") for k, v in forms.items()},
        {k: v.get("batch_expected_usd") for k, v in forms.items()},
        (round(worst["judge_direct"], 2), round(sum(worst[g] for g in both), 2)),
        (round(expected["judge_direct"], 2), round(sum(expected[g] for g in both), 2)))


def _gate_swap(proof, passage, replacement):
    @contextlib.contextmanager
    def swap():
        mod = _gate_module_with(passage, replacement)
        original = PROOFS_BY_NAME[proof]
        globals()[proof] = lambda: original(mod)
        try:
            yield
        finally:
            globals()[proof] = original
    return swap


PROOFS = [
    ("the gate mode sends B1's own prompts of the frozen claim set alone, every item in both groups",
     proof_gate_claim_set_only),
    ("the gate mode keeps every guard of the paid run", proof_gate_run_keeps_the_guards),
    ("the gate plan gives the worst case per group and form at the recorded prices, no client, no write",
     proof_gate_plan_at_recorded_prices),
    ("gate-prompts keeps the b1 prompts doc_judge builds, ids unchanged", proof_gate_prompts_keep_b1_alone),
    ("the gate prompts file must be the one rebuilt from the named held build", proof_gate_prompts_pinned_to_held),
    ("a gate run resumes only a gate run on the same prompts, set and model, none sent twice", proof_gate_resume),
    ("the gate mode's CLI rules", proof_gate_cli_rules),
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
    ("a cache write with no duration reported and no cache mark sent stops the run, the call at its worst case",
     proof_cache_writes_stop_the_run),
    ("D-610: every batch request is, byte for byte, the single route's request for the same prompt",
     proof_batch_bytes_equal_single),
    ("D-610: the batch route reserves and checks each worst case at the recorded batch rates; the spend line names "
     "the route, the rates and the batch ids", proof_batch_reserve_at_batch_price),
    ("D-610: a batch past its deadline is cancelled and recorded, and one that never ends is given up within the "
     "grace, every call at its worst", proof_batch_deadline_cancels),
    ("D-610: results joined by custom id; a missing or errored result is a recorded no_answer, never sent again",
     proof_batch_missing_result_is_no_answer),
    ("D-610: cache reads and writes priced from the usage by duration; only a repeated prefix at the minimum is marked",
     proof_cache_priced),
    ("D-610: a usage field that cannot be priced stops the run, the call at its worst case", proof_unpriceable_usage_halts),
    ("D-610: an interrupted batch request keeps its calls at their worst case, and reconcile finds the batch by its "
     "prefix", proof_batch_create_interrupt_keeps_worst),
    ("D-610: a resume never sends the earlier run's no_answer calls unless asked", proof_resume_keeps_no_answer),
    ("D-610: a given-up batch's later results leave its calls at their worst case", proof_late_results_stay_worst),
    ("D-610: batches.json names the batch id while it runs", proof_batch_id_written_at_once),
    ("D-610: a marked call is reserved at the higher of the input and write rates", proof_reserve_rates_safe_side),
    ("D-610: the batch deadline must be below the provider's expiry", proof_batch_deadline_below_expiry),
    ("D-610: a batch over the recorded limits is refused before it is sent", proof_batch_limits_refuse),
    ("D-610: cache writes whose durations do not add up stop the run", proof_cache_write_split_must_add_up),
    ("D-610: unmarked single-route bodies are the bodies before D-610", proof_unmarked_bodies_as_before),
    ("D-610: a batch close line is read by the spend reader, the API check and the reaper's warning",
     proof_batch_close_line_read_by_the_readers),
    ("D-610: an interrupt while the batch is followed cancels it and keeps every call a no_answer at its worst",
     proof_interrupt_while_following),
    ("D-610: the gate plan's batch figures are the sums at the recorded batch rates", proof_gate_plan_batch_figures),
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
    needle = "    finally:\n        measurement = dict(scope, **{"
    if source.count(needle) != 1:
        raise RuntimeError("the finally moved, so the neutralisation cannot be applied")
    mod = types.ModuleType("cloud_reference_no_finally")
    mod.__file__ = cr.__file__
    exec(compile(source.replace(needle, "    if True:\n        measurement = dict(scope, **{"), cr.__file__, "exec"), mod.__dict__)
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
    ("the claim set's pin not compared", "proof_gate_claim_set_only",
     _gate_swap("proof_gate_claim_set_only", "refuse(sha(set_file) == pin,", "refuse(True or sha(set_file) == pin,")),
    ("a group's items not held to the claim set", "proof_gate_claim_set_only",
     _gate_swap("proof_gate_claim_set_only", "and set(ids) == set(listed),", "or True,")),
    ("a prompt of another form admitted", "proof_gate_claim_set_only",
     _gate_swap("proof_gate_claim_set_only", 'refuse(all(p.get("form") == B1_FORM for p in value["prompts"]),', "refuse(True,")),
    ("the prompt scan removed in the gate mode", "proof_gate_run_keeps_the_guards",
     lambda: patch.object(cr, "scan", lambda prompts, key: None)),
    ("Seckin's yes not checked in the gate mode", "proof_gate_run_keeps_the_guards",
     lambda: patch.object(cr, "check_approval", lambda named, path: {"heading": str(named)})),
    ("the API ceiling not read in the gate mode", "proof_gate_run_keeps_the_guards",
     lambda: patch.object(cr, "check_cap", lambda cap, store, ledgers=None, now=None, *, kind: {"left_usd": 999.0})),
    ("the gate plan with no margin on the token estimate", "proof_gate_plan_at_recorded_prices",
     lambda: patch.object(cr, "COUNT_MARGIN", 1.0)),
    ("the gate plan not reading the store", "proof_gate_plan_at_recorded_prices",
     lambda: patch.object(cr.spend, "api_room", lambda store, kind, worst: (_ for _ in ()).throw(cr.spend.SpendStoreError("x")))),
    ("the gate prompts' text not pinned to the held build", "proof_gate_prompts_pinned_to_held",
     _gate_swap("proof_gate_prompts_pinned_to_held", "refuse(digest == sha(prompts_path),", "refuse(True,")),
    ("the set digest not read on a gate resume", "proof_gate_resume",
     _gate_swap("proof_gate_resume", 'resume_digests["gate_set_sha256"] = scope["gate_set_sha256"]', "pass")),
    ("the gate resume read by the J1 kind", "proof_gate_resume",
     _gate_swap("proof_gate_resume", "kind=kind, model=model, digests=resume_digests", "kind=SCHEMA, model=model, digests=resume_digests")),
    ("--measured-output admitted outside the gate mode", "proof_gate_cli_rules",
     lambda: patch.object(cr.argparse.ArgumentParser, "error", (lambda original: lambda self, message: None
                          if "belong to the gate mode" in message else original(self, message))(cr.argparse.ArgumentParser.error))),
    ("the recorded prices not compared in the gate mode", "proof_gate_run_keeps_the_guards",
     lambda: patch.object(cr, "check_prices", lambda prices, model, path: prices)),
    ("every live status accepted in the gate mode", "proof_gate_run_keeps_the_guards",
     lambda: patch.object(cr, "resolve", lambda configured, available: ("exact", configured))),
    ("any deprecations reading accepted in the gate mode", "proof_gate_run_keeps_the_guards",
     lambda: patch.object(cr, "DEPRECATION_FORM", re.compile(r".*", re.S))),
    ("gate-prompts keeping every form", "proof_gate_prompts_keep_b1_alone",
     _gate_swap("proof_gate_prompts_keep_b1_alone",
                'value["prompts"] if p.get("form") == B1_FORM]', 'value["prompts"]]')),
    ("the split puts every document in half A", "proof_half_b_refused", lambda: patch.object(cr, "halves", _all_in_half_a)),
    ("the universe not compared", "proof_universe_is_c_s", lambda: patch.object(cr, "universe", _unchecked_universe)),
    ("worst case counted as nothing", "proof_cap_stops_before_spend",
     lambda: patch.object(cr, "worst_case", lambda i, m, p: 0.0)),
    ("the check before each call removed", "proof_per_call_check_holds_alone",
     lambda: patch.object(cr, "call_fits", lambda spent, worst, cap: True)),
    ("a reply with no usage counted as free", "proof_failed_and_unread_calls_count_worst",
     lambda: patch.object(cr, "usage_cost", lambda reply, rates, **kw: {"cost_usd": 0.0, "input_tokens": 0,
                                                                          "output_tokens": 0})),
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
     lambda: _swap("proof_cache_writes_stop_the_run", _module_with(
         "        if not ttl:\n            raise Unpriceable(", "        if False:\n            raise Unpriceable("))),
    ("D-610: the batch request built without the single route's body", "proof_batch_bytes_equal_single",
     lambda: _swap("proof_batch_bytes_equal_single", _module_with(
         '"params": request_for(p, model, ttl)}', '"params": dict(params_for(p, model), max_tokens=int(p["max_new_tokens"]))}'))),
    ("D-610: the batch route reserved at the single rates", "proof_batch_reserve_at_batch_price",
     lambda: patch.object(cr, "route_rates", (lambda original: lambda prices, route: original(prices, "single"))(cr.route_rates))),
    ("D-610: the batch deadline never acted on", "proof_batch_deadline_cancels",
     lambda: _swap("proof_batch_deadline_cancels", _module_with(
         "        if not cancelled and now >= deadline:", "        if False:"))),
    ("D-610: the batch given up never after a cancel", "proof_batch_deadline_cancels",
     lambda: _swap("proof_batch_deadline_cancels", _module_with(
         "        elif cancelled and now >= give_up:", "        elif False:"))),
    ("D-610: a missing result counted as free", "proof_batch_missing_result_is_no_answer",
     lambda: _swap("proof_batch_missing_result_is_no_answer", _module_with(
         '" (the batch had not ended)"), worst,', '" (the batch had not ended)"), 0.0,'))),
    ("D-610: results joined by their order, not their custom id", "proof_batch_missing_result_is_no_answer",
     lambda: _swap("proof_batch_missing_result_is_no_answer", _module_with(
         '                cid = _attr(item, "custom_id")', '                cid = list(plan_rows)[len(results)]'))),
    ("D-610: cache reads priced at the input rate", "proof_cache_priced",
     lambda: _swap("proof_cache_priced", _module_with(
         'read * rates["cache_read_per_mtok"]', 'read * rates["input_per_mtok"]'))),
    ("D-610: a prefix under the minimum marked", "proof_cache_priced",
     lambda: _swap("proof_cache_priced", _module_with(
         'if tokens >= rule["min_tokens"] else None', 'if tokens >= 0 else None'))),
    ("D-610: unknown usage fields not read", "proof_unpriceable_usage_halts",
     lambda: _swap("proof_unpriceable_usage_halts", _module_with("    if unknown:\n", "    if False:\n"))),
    ("D-610: the interrupted batch's calls not kept in the run", "proof_batch_create_interrupt_keeps_worst",
     lambda: _swap("proof_batch_create_interrupt_keeps_worst", _module_with(
         '        rows.extend(state.pop("interrupted_rows", []))', '        pass'))),
    ("D-610: batches.json not written before the request", "proof_batch_create_interrupt_keeps_worst",
     lambda: _swap("proof_batch_create_interrupt_keeps_worst", _module_with(
         '    write_json(Path(out) / "batches.json", state["batches"])\n    try:\n        batch = client.messages.batches.create(',
         '    try:\n        batch = client.messages.batches.create('))),
    ("D-610: reconcile not holding the results to the run's prefix", "proof_batch_create_interrupt_keeps_worst",
     lambda: _swap("proof_batch_create_interrupt_keeps_worst", _module_with(
         "if ids and all(i.startswith(prefix) for i in ids) and len(ids) == rec.get(\"requests\"):", "if ids:"))),
    ("D-610: no_answer calls resent on a resume", "proof_resume_keeps_no_answer",
     lambda: patch.object(cr, "no_answer_before", lambda earlier: {})),
    ("D-610: a given-up batch's results read", "proof_late_results_stay_worst",
     lambda: _swap("proof_late_results_stay_worst", _module_with(
         '        if status == "ended":\n            try:\n                for item in client.messages.batches.results(record["id"]):',
         '        if True:\n            try:\n                for item in client.messages.batches.results(record["id"]):'))),
    ("D-610: the batch id written only at the end", "proof_batch_id_written_at_once",
     lambda: _swap("proof_batch_id_written_at_once", _module_with(
         '    record.update(id=str(_attr(batch, "id")), status=_attr(batch, "processing_status"))\n    write_json(Path(out) / "batches.json", state["batches"])\n',
         '    record.update(id=str(_attr(batch, "id")), status=_attr(batch, "processing_status"))\n'))),
    ("D-610: a marked call reserved at the input rate", "proof_reserve_rates_safe_side",
     lambda: patch.object(cr, "reserve_rates", lambda rates, ttl: rates)),
    ("D-610: any batch deadline admitted", "proof_batch_deadline_below_expiry",
     lambda: _swap("proof_batch_deadline_below_expiry", _module_with(
         '        refuse(batch_deadline_seconds < limits["expiry_hours"] * 3600,', '        refuse(True,'))),
    ("D-610: the batch limits not checked", "proof_batch_limits_refuse",
     lambda: _swap("proof_batch_limits_refuse", _module_with(
         '    refuse(len(chosen) <= limits["max_requests"] and size <= limits["max_bytes"],', '    refuse(True,'))),
    ("D-610: the durations' sum not checked", "proof_cache_write_split_must_add_up",
     lambda: _swap("proof_cache_write_split_must_add_up", _module_with(
         "        if five + hour != written:", "        if False:"))),
    ("D-610: a single-route body changed", "proof_unmarked_bodies_as_before",
     lambda: _swap("proof_unmarked_bodies_as_before", _module_with(
         'return dict(params_for(prompt, model, cache_ttl), max_tokens=int(prompt["max_new_tokens"]))',
         'return dict(params_for(prompt, model, cache_ttl), max_tokens=int(prompt["max_new_tokens"]), metadata={})'))),
    ("D-610: a close line field undeclared", "proof_batch_close_line_read_by_the_readers",
     lambda: patch.object(cr, "CLOSE_LINE_FIELDS", tuple(f for f in cr.CLOSE_LINE_FIELDS if f != "batch_ids"))),
    ("D-610: the followed batch's calls not kept on an interrupt", "proof_interrupt_while_following",
     lambda: _swap("proof_interrupt_while_following", _module_with(
         '        state["interrupted_rows"] = rows + lost', '        state["interrupted_rows"] = rows'))),
    ("D-610: the followed batch not cancelled on an interrupt", "proof_interrupt_while_following",
     lambda: _swap("proof_interrupt_while_following", _module_with(
         '                client.messages.batches.cancel(record["id"])\n                record["cancelled_on_interrupt"] = True',
         '                record["cancelled_on_interrupt"] = False'))),
    ("D-610: the gate plan's batch figures at the single rates", "proof_gate_plan_batch_figures",
     lambda: _swap("proof_gate_plan_batch_figures", _module_with(
         '"output_per_mtok": float(row["batch"]["output_per_mtok"])}', '"output_per_mtok": float(row["output_per_mtok"])}'))),
    ("D-610: the service tier not read", "proof_unpriceable_usage_halts",
     lambda: _swap("proof_unpriceable_usage_halts", _module_with(
         "    if tier is not None and tier not in TIER_OF_ROUTE[route]:", "    if False:"))),
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
