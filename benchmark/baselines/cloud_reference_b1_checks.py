"""Proofs for benchmark/baselines/cloud_reference_b1.py (D-S102 item 2, D-388), on fakes only.

The committed fixture bundle (benchmark/baselines/fixtures/bundle_q4, four items on four benchmarks)
staged as a build, a fake provider client, a fake live model list, fixture ledgers and stores. No
network, no key, no paid call. Each guarded rule is neutralised in memory, the proof must FAIL, the
rule is restored, the proof must PASS. Exit 1 on any failure.

    py -3.12 -X utf8 benchmark/baselines/cloud_reference_b1_checks.py
"""
import contextlib
import json
import shutil
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bare_model  # noqa: E402
import cloud_reference as cr  # noqa: E402
import cloud_reference_b1 as cb  # noqa: E402
import cloud_reference_checks as base  # noqa: E402

FIXTURES = HERE / "fixtures"
APPROVAL = "FOR_SECKIN 2026-11-09 18:00"
FOR_SECKIN_TEXT = base.FOR_SECKIN_TEXT
CREDIT = 61.69


@contextlib.contextmanager
def fixture(planted="", side="development", listed_side=None, listed=True):
    """A build of one document (dq4, items a1 to a4), its items.json and a parts.json, a runs folder,
    a ledger with a budget line, an empty spend store and an openings file."""
    with tempfile.TemporaryDirectory(prefix="shimmer_cloud_b1_") as tmp:
        tmp = Path(tmp)
        build = tmp / "build"
        shutil.copytree(FIXTURES / "bundle_q4", build / "dq4")
        if planted:
            doc = build / "dq4" / "context" / "dq4.md"
            doc.write_text(doc.read_text(encoding="utf-8") + "\n" + planted + "\n", encoding="utf-8")
        rows = [r for r in json.loads((FIXTURES / "items_q4.json").read_text(encoding="utf-8"))["items"]
                if r["document_id"] == "dq4"]
        (build / "items.json").write_text(json.dumps({"items": rows}), encoding="utf-8")
        (build / "parts.json").write_text(json.dumps({
            "benchmark": "fixture", "declared_side": side if side == "holdout" else None,
            "documents": [{"document_id": "dq4", "side": side}]}), encoding="utf-8")
        runs = tmp / "output" / "cloud_reference"
        runs.mkdir(parents=True)
        ledger = tmp / "ledger.jsonl"
        ledger.write_text(json.dumps({"event": "budget_open", "time_utc": "2026-11-01T00:00:00+00:00", "budget_usd": 500.0,
                                      "hard_stop_usd": 499.0}) + "\n", encoding="utf-8")
        (tmp / "private").mkdir()
        store = tmp / "private" / cr.SPEND_STORE_NAME
        store.write_text(json.dumps({"event": "ceiling", "time_utc": "2026-11-09T19:00:00+00:00", "ceiling_usd": 60.0,
                                     "warning_usd": 50.0}) + chr(10), encoding="utf-8")   # D-S121: the API ceiling line
        (store.parent / cr.FOR_SECKIN_NAME).write_text(FOR_SECKIN_TEXT, encoding="utf-8")
        prices = tmp / "prices.json"
        prices.write_text(json.dumps({"models": {cr.seat_model(): {"input_per_mtok": 5.0, "output_per_mtok": 25.0,
                                                                   "source": "fixture", "read_on": "2026-11-09"}}}),
                          encoding="utf-8")
        items_sha = cr.sha(build / "items.json")
        # The committed openings as `committed_openings` would give them: a decoy whose first cell
        # only begins with the opening, then the row itself, writing the full items digest.
        openings = ("| Part | k | Alpha | Attempt | Held-out material (file, digest) | Tuning | Written | Result |\n"
                    "|---|---|---|---|---|---|---|---|\n"
                    "| pubhealth-holdout-extra | 1 | 0.025 | 1 | items.json %s | x | 2026-11-09 | |\n"
                    "| pubhealth-holdout | 1 | 0.025 | 1 | items.json %s | x | 2026-11-09 | |\n" % (items_sha, items_sha))
        builds = tmp / "builds.json"
        entry = cb.build_entry(build, "fixture build", "fixture role B record")
        entry["side"] = listed_side or entry["side"]
        builds.write_text(json.dumps({"builds": [entry] if listed else []}), encoding="utf-8")
        (tmp / "for_seckin_copy.md").write_text(FOR_SECKIN_TEXT, encoding="utf-8")
        yield types.SimpleNamespace(tmp=tmp, build=build, rows=rows, runs=runs, ledger=ledger, store=store,
                                    prices=prices, items_sha=items_sha, parts_sha=cr.sha(build / "parts.json"),
                                    openings=openings, builds=builds, copy=tmp / "for_seckin_copy.md")


def go(box, client, name="b1", cap=5.0, mod=cb, lead_store=False, **kw):
    args = dict(cap_usd=cap, prices=base.PRICES, deprecation_checked=base.DEPRECATION,
                seckin_approved=(APPROVAL if kw.get("budget_left_usd") is not None else base.fresh_approval(box.store))
                if "seckin_approved" not in kw else None,
                credit_usd=CREDIT, keys={"ANTHROPIC_API_KEY": base.KEY}, client=client, list_models=base.live({cr.seat_model()}),
                runs_root=box.runs, prices_path=box.prices, store=box.store, ledgers=[box.ledger],
                openings=lambda: box.openings, builds_path=box.builds)
    if kw.get("budget_left_usd") is not None:
        args["role_c_run_id"] = "role-c-" + "0" * 12
    args.update(kw)
    # Role C's form refuses where the lead's store is reachable; a proof runs it as role C's own
    # checkout would see it (no store), unless it asks for the lead's.
    where = box.store if lead_store else box.tmp / "no_lead_checkout" / cr.SPEND_STORE_NAME
    with patch.object(cr.spend, "store_path", lambda root: where):
        return mod.run(box.build, box.items_sha, box.parts_sha, box.runs / name, **args)


def stopped(call):
    try:
        call()
    except cr.Stop as exc:
        return str(exc)
    return None


def proof_bare_model_layout_and_prompts():
    """Each item one call with B1's two turns as bare_model renders them, B1's allowance, and the
    replies in bare_model's own layout under <out>/<document>/."""
    with fixture() as box:
        client = base.FakeClient()
        m = go(box, client)
        out = box.runs / "b1" / "dq4"
        labels = sorted(p.stem for p in (out / "labels").glob("*.json"))
        label = json.loads((out / "labels" / "a2.json").read_text(encoding="utf-8"))
        doc, rendered = cb.rendered(box.build / "dq4", box.build / "items.json")
        sent = [(c.get("system"), c["messages"][0]["content"], c["max_tokens"]) for c in client.created]
        expected = [(s, u, m["allowance"]) for _, s, u in rendered]
        summary = (out / "b1_summary.json").is_file()
    ok = (labels == ["a1", "a2", "a3", "a4"] and label["schema"] == "b1-label-v2" and label["arm"] == bare_model.ARM
          and summary and sent == expected and m["allowance"] == 2048 and m["complete"]
          and m["label"] == cb.LABEL)
    return ok, "labels %s in bare_model's layout; %d calls equal to bare_model's rendering at the allowance %s" % (
        labels, len(sent), m["allowance"])


def proof_build_pinned():
    with fixture() as box:
        wrong = stopped(lambda: cb.run(box.build, "0" * 64, box.parts_sha, box.runs / "x", cap_usd=1.0, prices=base.PRICES,
                                       deprecation_checked=base.DEPRECATION, seckin_approved=APPROVAL, credit_usd=CREDIT,
                                       keys={"ANTHROPIC_API_KEY": base.KEY}, client=base.FakeClient(),
                                       list_models=base.live({cr.seat_model()}), runs_root=box.runs,
                                       prices_path=box.prices, store=box.store, ledgers=[box.ledger],
                                       builds_path=box.builds))
    return wrong is not None and "role B recorded" in wrong, "an items.json role B did not record: %r" % wrong


def proof_holdout_needs_its_opening():
    """The side is role B's: a holdout build reads only under the row whose first cell is the opening
    exactly and which writes the full items digest; a development build takes no opening."""
    with fixture(side="holdout") as box:
        none = stopped(lambda: go(box, base.FakeClient(), name="h1"))
        other = stopped(lambda: go(box, base.FakeClient(), name="h2", opening="no-such-row"))
        prefix = stopped(lambda: go(box, base.FakeClient(), name="h3", opening="pubhealth-holdout-ex"))
        short = stopped(lambda: go(box, base.FakeClient(), name="h5", opening="pubhealth-holdout",
                                   openings=lambda: box.openings.replace(box.items_sha, box.items_sha[:12])))
        m = go(box, base.FakeClient(), name="h4", opening="pubhealth-holdout")
    with fixture() as box:
        dev_with = stopped(lambda: go(box, base.FakeClient(), name="h6", opening="pubhealth-holdout"))
    ok = (none and "--opening" in none and other and "No single committed" in other and prefix
          and "No single committed" in prefix and short and "items digest" in short and dev_with
          and m["side"] == "holdout" and m["opening"].startswith("| pubhealth-holdout |"))
    return ok, ("holdout with no opening: %r; an unknown row: %r; a prefix of a row: %r; a row with a short digest: %r; "
                "development with one: %r; with its row: read" % (none, other, prefix, short, dev_with))


def proof_openings_read_at_head(mod=None):
    """HELDOUT_OPENINGS.md is read as committed at HEAD: a row only in the working copy is not seen."""
    import subprocess
    mod = mod or cb
    with tempfile.TemporaryDirectory(prefix="shimmer_openings_") as tmp:
        tmp = Path(tmp)
        path = tmp / mod.OPENINGS_PATH
        path.parent.mkdir(parents=True)
        path.write_text("| committed-row | 1 |\n", encoding="utf-8")
        flags = {"capture_output": True, "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
        subprocess.run(["git", "-C", str(tmp), "init", "-q"], **flags)
        subprocess.run(["git", "-C", str(tmp), "add", mod.OPENINGS_PATH], **flags)
        subprocess.run(["git", "-C", str(tmp), "-c", "user.name=proof", "-c", "user.email=proof@example.invalid",
                        "commit", "-q", "-m", "fixture"], **flags)
        path.write_text("| committed-row | 1 |\n| working-copy-row | 1 |\n", encoding="utf-8")
        text = mod.committed_openings(tmp)
    ok = "committed-row" in text and "working-copy-row" not in text
    return ok, "the committed row seen %s; the uncommitted row seen %s" % ("committed-row" in text, "working-copy-row" in text)


def proof_allowed_build_only():
    """A build not on the allowed list, a bundle file not the one it records, or a side role B's
    record does not give, is refused before any request (D-401 items 8 and 9)."""
    with fixture(listed=False) as box:
        client = base.FakeClient()
        unlisted = stopped(lambda: go(box, client, name="u"))
    with fixture() as box:
        rules = box.build / "dq4" / "conventions" / "rules.md"
        rules.write_text(rules.read_text(encoding="utf-8") + "\nOne more line.\n", encoding="utf-8")
        changed = stopped(lambda: go(box, client, name="f"))
    with fixture(side="holdout", listed_side="development") as box:
        side = stopped(lambda: go(box, client, name="s", opening="pubhealth-holdout"))
    sent = len(client.created) + len(client.counted)
    ok = (unlisted and "not on the allowed list" in unlisted and changed and "rules.md" in changed and side
          and "allowed list says development" in side and sent == 0)
    return ok, "not listed: %r; a bundle file changed: %r; another side: %r; %d requests" % (unlisted, changed, side, sent)


def proof_resume_refuses_other_runs():
    """A resume from a steering-stamped run, another model's or another build's is refused."""
    import claim_guard
    with fixture() as box:
        go(box, base.FakeClient(), name="a")
        path = box.runs / "a" / cb.MEASUREMENT_FILE
        value = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(dict(value, label=claim_guard.STEERING_LABEL, claim=False)), encoding="utf-8")
        steering = stopped(lambda: go(box, base.FakeClient(), name="r1", resume_from=box.runs / "a"))
        go(box, base.FakeClient(), name="b")
        for rec in (box.runs / "b").rglob("audit/model_replies/*.json"):
            r = json.loads(rec.read_text(encoding="utf-8"))
            rec.write_text(json.dumps(dict(r, model_id="claude-other-model")), encoding="utf-8")
        other_model = stopped(lambda: go(box, base.FakeClient(), name="r2", resume_from=box.runs / "b"))
        go(box, base.FakeClient(), name="c")
        path = box.runs / "c" / cb.MEASUREMENT_FILE
        value = json.loads(path.read_text(encoding="utf-8"))
        value["build"]["items_sha256"] = "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
        other_build = stopped(lambda: go(box, base.FakeClient(), name="r3", resume_from=box.runs / "c"))
    ok = bool(steering and other_model and other_build)
    return ok, "steering-stamped: %r; another model: %r; another build: %r" % (steering, other_model, other_build)


def proof_cache_write_halts_at_the_next_call():
    """A reply reporting cache writes halts at the next call, not at the document's end."""
    with fixture() as box:
        client = base.FakeClient(cache_write_at=1)
        m = go(box, client, name="cw")
    ok = len(client.created) == 1 and "cache-write" in str(m["stopped"]) and not m["complete"]
    return ok, "cache writes on the first reply: %d sent of 4, %r" % (len(client.created), m["stopped"])


def proof_credit_carries_across_chunks():
    with fixture() as box:
        one = go(box, base.FakeClient(), name="k1", max_calls=2)
        client = base.FakeClient()
        two = go(box, client, name="k2", resume_from=box.runs / "k1", credit_usd=one["spent_usd"] + 0.0001)
    ok = (two["chain_spent_before_usd"] == one["spent_usd"] and abs(two["limit_usd"] - 0.0001) < 1e-9
          and not client.created and str(two["stopped"]).startswith("cap: "))
    return ok, "chunk 2 counts %.4f spent before it; a credit of chain + 0.0001: limit %.6f, %d sent" % (
        two["chain_spent_before_usd"], two["limit_usd"], len(client.created))


def proof_role_marker_and_copy():
    """Role C's form runs only under the role C marker and with the entry's copy; the lead's form
    never under the marker."""
    import os
    with fixture() as box:
        handed = box.tmp / "c_spend.jsonl"
        no_marker = stopped(lambda: go(box, base.FakeClient(), name="m1", cap=3.0, budget_left_usd=4.0, spend_file=handed,
                                       for_seckin=box.copy))
        with patch.dict(os.environ, {cr.ROLE_ENVIRONMENT: cr.ROLE_C}):
            no_copy = stopped(lambda: go(box, base.FakeClient(), name="m2", cap=3.0, budget_left_usd=4.0,
                                         spend_file=handed))
            lead_in_c = stopped(lambda: go(box, base.FakeClient(), name="m3"))
    ok = (no_marker and "role C session" in no_marker and no_copy and "--for-seckin" in no_copy and lead_in_c
          and "role C session" in lead_in_c)
    return ok, "no marker: %r; no copy: %r; the lead's form in role C: %r" % (no_marker, no_copy, lead_in_c)


def proof_role_c_runs_under_the_lead_s_intent():
    """D-401 item 11: the lead opens role C's intent (open-role-c: its cap held as running, Seckin's
    yes used once); role C's run carries that id; the append closes it and counts its spend; a
    handed-back line naming no such intent is refused; role C's form refuses in the lead's checkout."""
    import os
    with fixture() as box:
        handed = {}
        heading = base.fresh_approval(box.store)
        opened = cb.open_role_c(3.0, heading, store=box.store, ledgers=[box.ledger])
        running = cr.spend.state(box.store)["running_caps_usd"]
        drop = cr.spend.handback_dir(box.store)
        drop.mkdir()
        with patch.dict(os.environ, {cr.ROLE_ENVIRONMENT: cr.ROLE_C}):
            in_lead = stopped(lambda: go(box, base.FakeClient(), name="lc", cap=3.0, budget_left_usd=opened["budget_left_usd"],
                                         spend_file=drop / "x.jsonl", for_seckin=box.copy, lead_store=True,
                                         role_c_run_id=opened["role_c_run_id"]))
            m = go(box, base.FakeClient(), name="rc", cap=3.0, budget_left_usd=opened["budget_left_usd"],
                   spend_file=drop / "role_c.jsonl", for_seckin=box.copy, role_c_run_id=opened["role_c_run_id"])
        cr.spend.append_handed_back(box.store, drop / "role_c.jsonl")
        after = cr.spend.state(box.store)
        twice = stopped(lambda: cb.open_role_c(3.0, heading, store=box.store, ledgers=[box.ledger]))
        stray = drop / "stray.jsonl"
        stray.write_text(json.dumps({"run_id": "role-c-ffffffffffff", "spent_usd": 1.0}) + "\n", encoding="utf-8")
        try:
            cr.spend.append_handed_back(box.store, stray)
            handed["stray"] = None
        except cr.spend.SpendStoreError as exc:
            handed["stray"] = str(exc)
    ok = (running == 3.0 and bool(in_lead) and "lead's checkout" in in_lead and m["run_id"] == opened["role_c_run_id"]
          and after["running_caps_usd"] == 0.0 and abs(after["spent_usd"] - m["spent_usd"]) < 1e-9
          and handed["stray"] and "no role C intent" in handed["stray"] and bool(twice) and "one evet" in twice)
    return ok, ("intent held %.2f; in the lead's checkout: %r; appended: running %.2f, spent %.4f; a stray line: %r; "
                "the heading again: %r" % (running, in_lead, after["running_caps_usd"], after["spent_usd"],
                                            handed["stray"], twice))


def proof_each_caller_passes_its_own_kind():
    """D-467 item 2: each check_cap caller passes its own run kind to the API room reading (the
    paid B1 run its SCHEMA, the lead's opening of role C its ROLE_C_KIND, the base runner its own);
    check_cap has no default kind, so a caller that names none is refused."""
    seen = []
    original = cr.spend.api_room
    with fixture() as box:
        with patch.object(cr.spend, "api_room", lambda store, kind, worst: (seen.append(kind), original(store, kind, worst))[1]):
            go(box, base.FakeClient(), name="kinds", cap=3.0)
            cb.open_role_c(3.0, base.fresh_approval(box.store), store=box.store, ledgers=[box.ledger])
        unnamed = stopped(lambda: cr.check_cap(1.0, box.store, [box.ledger], kind=""))
        try:
            cr.check_cap(1.0, box.store, [box.ledger])
            positional = None
        except TypeError as exc:
            positional = str(exc)
    with base.sandbox() as sbox:
        with patch.object(cr.spend, "api_room", lambda store, kind, worst: (seen.append(kind), original(store, kind, worst))[1]):
            base.go(sbox, base.FakeClient(), cap=3.0, name="base_kind")
    ok = (seen == [cb.SCHEMA, cb.ROLE_C_KIND, cr.SCHEMA] and bool(unnamed) and "kind" in unnamed
          and positional is not None and "kind" in positional)
    return ok, "kinds read: %s; an empty kind: %r; none named: %r" % (seen, unnamed, positional)


def proof_role_c_held_to_its_intent_cap():
    """D-401 item 11: role C is handed the intent's cap as its budget figure and refuses a cap above
    it; a handed-back line above its intent's cap is not appended and is flagged at the top of
    FOR_SECKIN.md."""
    import os
    with fixture() as box:
        opened = cb.open_role_c(2.0, base.fresh_approval(box.store), store=box.store, ledgers=[box.ledger])
        drop = cr.spend.handback_dir(box.store)
        drop.mkdir()
        with patch.dict(os.environ, {cr.ROLE_ENVIRONMENT: cr.ROLE_C}):
            above = stopped(lambda: go(box, base.FakeClient(), name="above", cap=2.5,
                                       budget_left_usd=opened["budget_left_usd"], spend_file=drop / "a.jsonl",
                                       for_seckin=box.copy, role_c_run_id=opened["role_c_run_id"]))
        over = drop / "over.jsonl"
        over.write_text(json.dumps({"run_id": opened["role_c_run_id"], "spent_usd": 2.75}) + "\n", encoding="utf-8")
        refused_append = None
        try:
            cr.spend.append_handed_back(box.store, over)
        except cr.spend.SpendStoreError as exc:
            refused_append = str(exc)
        lines = (box.store.parent / cr.FOR_SECKIN_NAME).read_text(encoding="utf-8").splitlines()
        flagged = len(lines) > 2 and lines[0].startswith("# ") and lines[2].startswith("## FLAG ") and \
            opened["role_c_run_id"] in "\n".join(lines[:6])
        stored = cr.spend.state(box.store)
    ok = (opened["budget_left_usd"] == 2.0 and bool(above) and "budget left the lead gave" in above
          and bool(refused_append) and "against the 2.0000 USD" in refused_append and flagged
          and stored["spent_usd"] == 0.0 and stored["running_caps_usd"] == 2.0)
    return ok, ("handed figure %.2f for a 2.00 intent; a 2.50 cap: %r; a 2.75 spend line: %r; flagged on top %s"
                % (opened["budget_left_usd"], above, refused_append, flagged))


def proof_one_evet_one_run():
    with fixture() as box:
        go(box, base.FakeClient(), name="first", seckin_approved=APPROVAL, max_calls=2)
        client = base.FakeClient()
        again = stopped(lambda: go(box, client, name="again", seckin_approved=APPROVAL))
        rest = go(box, base.FakeClient(), name="rest", seckin_approved=APPROVAL, resume_from=box.runs / "first")
    ok = bool(again) and "one evet approves one run" in again and not client.created and rest["complete"]
    return ok, "a second fresh run under the heading: %r; its resume ran (complete %s)" % (again, rest["complete"])


def proof_approval_required():
    """No heading time of Seckin's yes, no run, nothing sent; with it, it is in the spend line."""
    with fixture() as box:
        client = base.FakeClient()
        why = stopped(lambda: go(box, client, name="a", seckin_approved="FOR_SECKIN entry written, waiting"))
        empty = stopped(lambda: go(box, client, name="a2", seckin_approved=""))
        count = len(client.created)
        go(box, base.FakeClient(), name="a3", seckin_approved=APPROVAL)
        line = cr.read_store(box.store)[-1]
    ok = (why is not None and "heading" in why and empty is not None and count == 0
          and (line.get("seckin_approved") or {}).get("evet_line") == "Seckin: evet (2026-11-09 18:05)")
    return ok, "no time: %r; empty refused %s; %d sent; the spend line records %r" % (
        why, empty is not None, count, line.get("seckin_approved"))


def proof_credit_bounds_the_worst_case():
    """--credit-usd below a document's worst case: the document is not started, nothing sent."""
    with fixture() as box:
        client = base.FakeClient()
        m = go(box, client, name="credit", cap=5.0, credit_usd=0.05)
    ok = not client.created and bool(m["stopped"]) and m["stopped"].startswith("cap: ") and m["limit_usd"] == 0.05
    return ok, "credit 0.05 under a cap of 5: %d sent, %r" % (len(client.created), m["stopped"])


def sent(client):
    return [json.dumps([c.get("system"), c["messages"]], sort_keys=True) for c in client.created]


def proof_role_c_form():
    """Role C's form: the lead's figure for the budget, the spend line in the file handed back."""
    import os
    with fixture() as box, patch.dict(os.environ, {cr.ROLE_ENVIRONMENT: cr.ROLE_C}):
        handed = box.tmp / "role_c_spend.jsonl"
        over = stopped(lambda: go(box, base.FakeClient(), name="c1", cap=5.0, budget_left_usd=4.0, spend_file=handed,
                                  for_seckin=box.copy))
        m = go(box, base.FakeClient(), name="c2", cap=3.0, budget_left_usd=4.0, spend_file=handed, for_seckin=box.copy)
        line = [json.loads(l) for l in handed.read_text(encoding="utf-8").splitlines()]
        # untouched: only the API ceiling line the fixture's operator wrote (D-S121)
        shared = [json.loads(l).get("event") for l in box.store.read_text(encoding="utf-8").splitlines()] == ["ceiling"]
    ok = (over and "budget left the lead gave" in over and len(line) == 1 and line[0]["spent_usd"] == m["spent_usd"]
          and shared and m["budget"]["left_usd"] == 4.0)
    return ok, "cap 5 over the lead's 4: %r; cap 3: its spend line in the file handed back, the shared store untouched %s" % (
        over, shared)


def proof_cap_stops_inside_a_document():
    """A call whose worst case would pass the cap stops the run; it is never recorded as a failed
    call with the next item sent."""
    with fixture() as box, patch.object(cr, "group_fits", lambda spent, worst, cap: True):
        client = base.FakeClient()
        m = go(box, client, name="cap", cap=0.07)
    ok = len(client.created) == 2 and m["stopped"] and m["stopped"].startswith("cap: ") and not m["complete"]
    return ok, "cap 0.07: %d calls sent of 4, %r" % (len(client.created), m["stopped"])


def proof_planted_key_refused():
    with fixture(planted="-".join(("sk", "ant", "Z" * 30))) as box:
        client = base.FakeClient()
        why = stopped(lambda: go(box, client, name="k"))
    return why is not None and "key-shaped" in why and not client.created, "a key-shaped string in the document: %r" % why


class BadRequestError(Exception):
    """Named as the SDK names a 400, the error a credit balance run out returns."""


class RefusingClient(base.FakeClient):
    """Answers the first call, then refuses every one after it as the provider does with no credit."""

    def create(self, **params):
        if self.created:
            self.created.append(params)
            raise BadRequestError("Your credit balance is too low")
        return super().create(**params)


def proof_stops_cleanly_and_resumes():
    """No credit (a 400) mid-run: the run stops at the first refusal, the reply so far recorded and
    the spend line written; resumed from that folder, only the unanswered prompts are sent, none
    twice, and the document's four labels are written (D-S106 item 3)."""
    with fixture() as box:
        client = RefusingClient()
        cut = go(box, client, name="cut")
        records = list((box.runs / "cut" / "dq4" / "audit" / "model_replies").glob("*.json"))
        lines = cr.read_store(box.store)
        again = base.FakeClient()
        resumed = go(box, again, name="resumed", resume_from=box.runs / "cut")
        labels = list((box.runs / "resumed" / "dq4" / "labels").glob("*.json"))
        first, second = sent(client)[:1], sent(again)
    ok = (len(client.created) == 2 and bool(cut["stopped"]) and "can be resumed" in cut["stopped"]
          and len(records) == 1 and len(lines) == 1 and not set(first) & set(second) and len(second) == 3
          and resumed["complete"] and resumed["reused_answers"] == 1 and len(labels) == 4)
    return ok, ("no credit after one call: %d sent, %d reply recorded, %d spend line; resumed: %d sent, %d again, "
                "%d reused, %d labels" % (len(client.created), len(records), len(lines), len(second),
                                          len(set(first) & set(second)), resumed["reused_answers"], len(labels)))


def proof_chunks_and_resume():
    """--max-calls 2: two calls, a clean stop; resumed, the other two, none sent twice."""
    with fixture() as box:
        one = base.FakeClient()
        cut = go(box, one, name="chunk1", max_calls=2)
        two = base.FakeClient()
        rest = go(box, two, name="chunk2", resume_from=box.runs / "chunk1")
    ok = (len(one.created) == 2 and str(cut["stopped"]).startswith("chunk done") and len(two.created) == 2
          and not set(sent(one)) & set(sent(two)) and rest["complete"])
    return ok, "chunk of 2: %d sent, %r; the rest: %d sent, %d again" % (
        len(one.created), cut["stopped"], len(two.created), len(set(sent(one)) & set(sent(two))))


def _unchecked_answers(folder, *, model, decoding):
    """cr.answered with every check removed: every recorded reply taken."""
    out = {}
    if folder is None:
        return out
    for path in sorted(Path(folder).rglob("audit/model_replies/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("backend_ok") and isinstance((record.get("reply") or {}).get("text"), str):
            out[record["payload"]["sha256"]] = (path, record)
    return out


@contextlib.contextmanager
def _swap_proof(name, mod):
    original = globals()[name]
    globals()[name] = lambda: original(mod)
    try:
        yield
    finally:
        globals()[name] = original


@contextlib.contextmanager
def _swap_open_role_c():
    """open_role_c handing role C the whole budget left, as it did before."""
    original = cb.open_role_c

    def whole(cap_usd, seckin_approved, **kw):
        opened = original(cap_usd, seckin_approved, **kw)
        return dict(opened, budget_left_usd=opened["total_left_after_usd"] + cap_usd)
    with patch.object(cb, "open_role_c", whole):
        yield


def _no_chunk(init):
    def wrapped(self, *a, **kw):
        init(self, *a, **kw)
        self.max_calls = None
    return wrapped


def _module_with(old, new):
    source = Path(cb.__file__).read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError("the passage moved, so the neutralisation cannot be applied")
    mod = types.ModuleType("cloud_reference_b1_neutralised")
    mod.__file__ = cb.__file__
    exec(compile(source.replace(old, new), cb.__file__, "exec"), mod.__dict__)
    return mod


@contextlib.contextmanager
def _against(mod):
    original = globals()["go"]
    globals()["go"] = lambda box, client, name="b1", cap=5.0, mod_=mod, **kw: original(box, client, name, cap, mod_, **kw)
    try:
        yield
    finally:
        globals()["go"] = original


PROOFS = [
    ("B1's two turns as bare_model renders them, its allowance, the replies in bare_model's layout",
     proof_bare_model_layout_and_prompts),
    ("the build is the one role B recorded", proof_build_pinned),
    ("a holdout build reads only under its exact committed HELDOUT_OPENINGS row", proof_holdout_needs_its_opening),
    ("HELDOUT_OPENINGS.md is read at HEAD, never the working copy", proof_openings_read_at_head),
    ("only an allowed build, its files and side as listed", proof_allowed_build_only),
    ("a resume from a steering-stamped run, another model or another build is refused", proof_resume_refuses_other_runs),
    ("a cache-write halt stops at the next call", proof_cache_write_halts_at_the_next_call),
    ("the credit carries across resumed chunks", proof_credit_carries_across_chunks),
    ("role C's form only under its marker and with the entry's copy", proof_role_marker_and_copy),
    ("role C runs under the lead's intent, closed by the append; never in the lead's checkout",
     proof_role_c_runs_under_the_lead_s_intent),
    ("one evet approves one run; its resume may use it again", proof_one_evet_one_run),
    ("role C is held to its intent's cap; a spend line above it is refused and flagged", proof_role_c_held_to_its_intent_cap),
    ("each check_cap caller passes its own kind; none is defaulted", proof_each_caller_passes_its_own_kind),
    ("a paid run needs the heading time of Seckin's yes, recorded in the spend line", proof_approval_required),
    ("the credit left bounds the worst case", proof_credit_bounds_the_worst_case),
    ("role C's form: the lead's budget figure, the spend line in the file handed back", proof_role_c_form),
    ("the cap stops a document mid-way, never recorded as a failed call", proof_cap_stops_inside_a_document),
    ("a key-shaped string in a rendered prompt refuses the run", proof_planted_key_refused),
    ("no credit mid-run stops cleanly; a resumed run sends only what was not answered, none twice",
     proof_stops_cleanly_and_resumes),
    ("a chunk stops cleanly and the next one sends the rest", proof_chunks_and_resume),
]

NEUTRALISATIONS = [
    ("every caller read as the base runner's kind", "proof_each_caller_passes_its_own_kind",
     lambda: patch.object(cr, "check_cap", (lambda original: lambda cap, store, ledgers=None, now=None, *, kind=None:
                                            original(cap, store, ledgers, now, kind=cr.SCHEMA))(cr.check_cap))),
    ("the system turn dropped", "proof_bare_model_layout_and_prompts",
     lambda: patch.object(cb.AnthropicBackend, "params", lambda self, system, user: {
         "model": self.model, "messages": [{"role": "user", "content": user}]})),
    ("the build's digests not compared", "proof_build_pinned",
     lambda: patch.object(cb, "build_files", lambda build, items, parts: (
         Path(build) / "items.json", [p for p in Path(build).iterdir() if (p / "context").is_dir()]))),
    ("the working copy read for the openings", "proof_openings_read_at_head",
     lambda: _swap_proof("proof_openings_read_at_head", _module_with(
         '["git", "-C", str(root), "show", "HEAD:" + OPENINGS_PATH]',
         '["git", "-C", str(root), "show", "HEAD:" + OPENINGS_PATH] if False else [sys.executable, "-c", '
         '"import sys,pathlib;sys.stdout.write(pathlib.Path(sys.argv[1]).read_text())", str(Path(root) / OPENINGS_PATH)]'))),
    ("an opening matched as a substring", "proof_holdout_needs_its_opening", lambda: _against(_module_with(
        '        if cells and cells[0] == opening.strip():', '        if opening.strip() in line:'))),
    ("the allowed list not read", "proof_allowed_build_only",
     lambda: patch.object(cb, "allowed_build", lambda i, p_, b=None: {"name": "any", "side": "development",
                                                                      "files": {}, "role_b_record": "x"})),
    ("the bundle files not compared", "proof_allowed_build_only", lambda: _against(_module_with(
        '    cr.refuse(not differ,', '    cr.refuse(True,'))),
    ("the side not read from role B's record", "proof_allowed_build_only",
     lambda: patch.object(cb, "build_side", lambda parts: "development")),
    ("an earlier run's measurement not checked", "proof_resume_refuses_other_runs",
     lambda: patch.object(cr, "earlier_run", lambda folder, **k: None)),
    ("earlier replies taken unchecked", "proof_resume_refuses_other_runs",
     lambda: patch.object(cr, "answered", _unchecked_answers)),
    ("the halt read only at the document's end", "proof_cache_write_halts_at_the_next_call", lambda: _against(_module_with(
        '        if self.state["halt"]:\n            # A cache-write halt', '        if False:\n            # A cache-write halt'))),
    ("the chain's spend not subtracted", "proof_credit_carries_across_chunks",
     lambda: patch.object(cr, "chain_spent", lambda earlier: 0.0)),
    ("a handed-back line taken with no intent", "proof_role_c_runs_under_the_lead_s_intent",
     lambda: patch.object(cr.spend, "unplanned_runs", lambda rows, lines: [])),
    ("role C's form in the lead's checkout", "proof_role_c_runs_under_the_lead_s_intent", lambda: _against(_module_with(
        "        cr.refuse(lead_store is None or not lead_store.exists(),", "        cr.refuse(True,"))),
    ("open-role-c not checking the evet's use", "proof_role_c_runs_under_the_lead_s_intent",
     lambda: patch.object(cr, "approval_unused", lambda store, approval, chain: None)),
    ("the whole budget left handed to role C", "proof_role_c_held_to_its_intent_cap", lambda: _swap_open_role_c()),
    ("role C's cap not held to the figure", "proof_role_c_held_to_its_intent_cap", lambda: _against(_module_with(
        "        cr.refuse(isinstance(budget_left_usd, (int, float)) and cap_usd <= budget_left_usd + 1e-9,",
        "        cr.refuse(True,"))),
    ("a spend line above its intent's cap appended", "proof_role_c_held_to_its_intent_cap",
     lambda: patch.object(cr.spend, "over_cap", lambda rows, lines: [])),
    ("no flag written", "proof_role_c_held_to_its_intent_cap",
     lambda: patch.object(cr.spend, "flag_for_seckin", lambda *a: None)),
    ("an evet used twice", "proof_one_evet_one_run",
     lambda: patch.object(cr, "approval_unused", lambda store, approval, chain: None)),
    ("no role marker read", "proof_role_marker_and_copy", lambda: patch.object(cr, "check_role", lambda lead_side: None)),
    ("a holdout read with no opening", "proof_holdout_needs_its_opening",
     lambda: patch.object(cb, "check_side", lambda side, opening, items, openings: opening)),
    ("no approval needed", "proof_approval_required", lambda: patch.object(cr, "check_approval", lambda a, f: {"named": a, "evet_line": "Seckin: evet (2026-11-09 18:05)"})),
    ("the credit not held", "proof_credit_bounds_the_worst_case",
     lambda: patch.object(cr, "spend_limit", lambda cap, credit: cap)),
    ("the lead's budget figure not held", "proof_role_c_form",
     lambda: _against(_module_with("cap_usd <= budget_left_usd + 1e-9", "True"))),
    ("the cap stop recorded as a failed call", "proof_cap_stops_inside_a_document",
     lambda: _against(_module_with("class CapReached(bare_model.SetupError):", "class CapReached(Exception):"))),
    ("the prompt scan removed", "proof_planted_key_refused", lambda: patch.object(cr, "scan", lambda prompts, key: None)),
    ("a refusal taken for a passing failure", "proof_stops_cleanly_and_resumes", lambda: patch.object(cb, "STOP_ERRORS", ())),
    ("answered prompts sent again", "proof_stops_cleanly_and_resumes",
     lambda: patch.object(cb, "earlier_replies", lambda resume_from: {})),
    ("answered prompts sent again", "proof_chunks_and_resume",
     lambda: patch.object(cb, "earlier_replies", lambda resume_from: {})),
    ("no chunk bound", "proof_chunks_and_resume",
     lambda: patch.object(cb.AnthropicBackend, "__init__", _no_chunk(cb.AnthropicBackend.__init__))),
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
    print("%s cloud reference B1 path: %d of %d proofs and neutralisations pass" % (
        "PASS" if not failures else "FAIL", total - failures, total))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
