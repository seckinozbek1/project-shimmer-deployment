"""Proofs for the subscription steering checks (benchmark/baselines/cloud_reference_steering.py,
claim_guard.py; D-S104 item 1), on fakes only: no Claude Code call, no network, no subscription use.

Each guarded rule is neutralised in memory, the proof must FAIL, the rule is restored and the proof
must PASS. One line per proof, a summary line; exit 1 on any failure.

    py -3.12 -X utf8 benchmark/baselines/cloud_reference_steering_checks.py
"""
import contextlib
import json
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import claim_guard as cg  # noqa: E402
import cloud_reference as cr  # noqa: E402
import cloud_reference_checks as base  # noqa: E402
import cloud_reference_steering as st  # noqa: E402

LABEL = "subscription, steering only"   # the words D-S104 item 1 gives, written out


@contextlib.contextmanager
def fixture():
    """A J1-shaped prompts file and bar (cloud_reference_checks' builder), a quick subset of three
    items, and an empty steering runs folder."""
    with tempfile.TemporaryDirectory(prefix="shimmer_steering_checks_") as tmp:
        box = base.build(tmp)
        subset = Path(tmp) / "subset.json"
        subset.write_text(json.dumps(["co00-i1", "co02-i1", "sc01-i1"]), encoding="utf-8")
        runs = Path(tmp) / "output" / "cloud_reference_steering"
        runs.mkdir(parents=True)
        sets = Path(tmp) / "sets.json"
        sets.write_text(json.dumps({"allowed": [{"name": "fixture quick subset", "prompts_sha256": cr.sha(box.path),
                                                 "subset_sha256": cr.sha(subset)}],
                                    "refused": [{"name": "a fixture fresh set", "sha256": "f" * 64}]}), encoding="utf-8")
        box.sets, box.fresh_source = sets, Path(tmp) / "no_system_test.py"
        yield box, subset, runs


class FakeCaller:
    """Stands in for headless Claude Code: records each call and answers with an empty items list."""

    def __init__(self):
        self.calls = []

    def __call__(self, model, text, cwd):
        self.calls.append({"model": model, "text": text, "cwd": str(cwd), "cwd_files": os.listdir(cwd)})
        return '{"items": []}', {"input_tokens": 10, "output_tokens": 5}, None


SIGNED_IN = dict(st.SUBSCRIPTION, subscriptionType="max")


def signed_in(cwd):
    return dict(SIGNED_IN), None


def steer(box, subset, runs, caller, name="check", mod=st, status=signed_in, sets=None):
    return mod.run(box.path, subset, cr.sha(subset), runs / name, caller=caller, runs_root=runs, status=status,
                   sets_path=sets or box.sets, fresh_source=box.fresh_source)


def refused(call):
    try:
        call()
    except (cg.SteeringNotAClaim, cr.Stop) as exc:
        return str(exc)
    return None


def proof_call_is_the_subscription_with_the_registry_alias():
    """The command, the alias, the fixed system prompt, no tools, an empty folder outside the
    repository, and no API credential in the child's environment."""
    argv = st.argv("claude-opus-4-8")
    planted = {"ANTHROPIC_API_KEY": "fixture-not-a-key", "ANTHROPIC_AUTH_TOKEN": "fixture",
               "ANTHROPIC_BASE_URL": "https://elsewhere.invalid", "CLAUDE_CODE_USE_BEDROCK": "1",
               "CLAUDE_CODE_USE_VERTEX": "1", "ANTHROPIC_VERTEX_PROJECT_ID": "p", "CLOUD_ML_REGION": "r",
               "AWS_BEARER_TOKEN_BEDROCK": "t", "CLAUDE_CODE_USE_FOUNDRY": "1"}
    with patch.dict(os.environ, planted):
        env = st.child_environment()
    with fixture() as (box, subset, runs):
        caller = FakeCaller()
        m = steer(box, subset, runs, caller)
    calls = caller.calls
    ok = (argv[:2] == ["claude", "-p"] and argv[argv.index("--model") + 1] == "claude-opus-4-8"
          and argv[argv.index("--system-prompt") + 1] == st.STEERING_SYSTEM and argv[argv.index("--tools") + 1] == ""
          and "--no-session-persistence" in argv and "--bare" not in argv
          and not set(planted) & set(env)
          and calls and all(c["model"] == cr.seat_model() for c in calls)
          and all(c["cwd_files"] == [] and not Path(c["cwd"]).resolve().is_relative_to(cr.ROOT) for c in calls)
          and m["model"]["route"] == "subscription")
    return ok, ("argv %s; API variables in the child's environment: %s; calls %d with the registry's alias, from an empty "
                "folder outside the repository" % (" ".join(repr(a) for a in argv[:6]),
                                                    sorted(set(planted) & set(env)), len(calls)))


def proof_only_a_subscription_sign_in():
    """The CLI's own status must report a claude.ai sign-in on the first-party provider before any
    call, and the reading is recorded; an API key sign-in, another provider or an unreadable status
    refuses with no call (D-401 item 7)."""
    with fixture() as (box, subset, runs):
        readings = {"api key": ({"loggedIn": True, "authMethod": "api_key", "apiProvider": "firstParty"}, None),
                    "bedrock": ({"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "bedrock"}, None),
                    "signed out": ({"loggedIn": False, "authMethod": None, "apiProvider": None}, None),
                    "unreadable": (None, "claude auth status exited 1")}
        caller = FakeCaller()
        refusals = {name: refused(lambda r=r, name=name: steer(box, subset, runs, caller, name="s-" + name.replace(" ", "-"),
                                                               status=lambda cwd, r=r: r))
                    for name, r in readings.items()}
        m = steer(box, subset, runs, FakeCaller(), name="ok")
    ok = all(refusals.values()) and not caller.calls and m["sign_in"] == SIGNED_IN
    return ok, "%s; no call %s; a subscription sign-in recorded %s" % (
        "; ".join("%s refused %s" % (k, bool(v)) for k, v in refusals.items()), not caller.calls, m["sign_in"] == SIGNED_IN)


def proof_only_allowed_sets():
    """Only a listed (prompts file, subset) pair runs; the fresh set's digest (the sets file's refused
    list or system_test.py's FRESH_PROMPTS_SHA256) is refused (D-401 item 6)."""
    with fixture() as (box, subset, runs):
        caller = FakeCaller()
        other = Path(box.tmp) / "other_subset.json"
        other.write_text(json.dumps(["co00-i1"]), encoding="utf-8")
        unlisted = refused(lambda: box_run(box, other, runs, caller, "u"))
        fresh_listed = Path(box.tmp) / "sets_fresh.json"
        fresh_listed.write_text(json.dumps({"allowed": [{"name": "x", "prompts_sha256": cr.sha(box.path),
                                                         "subset_sha256": cr.sha(subset)}],
                                            "refused": [{"name": "the fresh set", "sha256": cr.sha(box.path)}]}),
                                encoding="utf-8")
        refused_list = refused(lambda: steer(box, subset, runs, caller, name="f", sets=fresh_listed))
        source = Path(box.tmp) / "system_test.py"
        source.write_text('FRESH_PROMPTS_SHA256 = "%s"\n' % cr.sha(box.path), encoding="utf-8")
        from_source = refused(lambda: st.run(box.path, subset, cr.sha(subset), runs / "g", caller=caller, runs_root=runs,
                                             status=signed_in, sets_path=box.sets, fresh_source=source))
    ok = (unlisted and "not an allowed steering set" in unlisted and refused_list and "refused list" in refused_list
          and from_source and "refused list" in from_source and not caller.calls)
    return ok, "an unlisted subset: %r; a listed set whose digest is refused: %r; the fresh digest from system_test.py: %r" % (
        unlisted, refused_list, from_source)


def box_run(box, subset, runs, caller, name):
    return st.run(box.path, subset, cr.sha(subset), runs / name, caller=caller, runs_root=runs, status=signed_in,
                  sets_path=box.sets, fresh_source=box.fresh_source)


def proof_every_file_carries_the_label():
    with fixture() as (box, subset, runs):
        steer(box, subset, runs, FakeCaller())
        folder = runs / "check"
        m = json.loads((folder / cr.MEASUREMENT_FILE).read_text(encoding="utf-8"))
        records = [json.loads(p.read_text(encoding="utf-8")) for p in (folder / "audit" / "model_replies").glob("*.json")]
    ok = (m.get("label") == LABEL and m.get("claim") is False and m["rows"]
          and all(r.get("label") == LABEL and r.get("claim") is False for r in m["rows"])
          and records and all(r["decoding"].get("label") == LABEL and r["decoding"].get("claim") is False for r in records))
    return ok, "measurement, %d rows and %d reply records carry %r and claim false" % (len(m["rows"]), len(records), LABEL)


def proof_the_scorer_refuses_a_steering_pass():
    with fixture() as (box, subset, runs):
        steer(box, subset, runs, FakeCaller())
        why = refused(lambda: cr.read(box.path, box.bar, box.items, runs / "check", box.keys, runs / "read", "t"))
    ok = why is not None and "never read as the cloud reference's figure" in why
    return ok, "cloud_reference.read on a steering pass: %r" % why


def proof_the_page_refuses_a_steering_row():
    """What a page or report reads: a row holding a steering result anywhere is refused; the
    stamped steering view is refused; an API measurement is not."""
    stamped = cg.steering_view({"views": {"judge_direct": {}}})
    page_row = {"benchmark": "scitab", "arms": {"reference": {"figure": 0.9, "evidence": stamped}}}
    with fixture() as (box, subset, runs), base.sandbox() as sbox:
        api = base.go(sbox, base.FakeClient(), cap=1.0, name="api")
        nested = refused(lambda: cg.refuse_claim(page_row, "on the page"))
        direct = refused(lambda: cg.refuse_claim(stamped, "on the page"))
        api_ok = cg.refuse_claim(api, "on the page") is api
    ok = nested and direct and api_ok and stamped["claim"] is False and stamped["label"] == LABEL
    return ok, "a page row holding a steering view: %r; the view itself refused %s; the API run's measurement passes %s" % (
        nested, direct is not None, api_ok)


# ---------------------------------------------------------------------------
# the gate's quick subset (lane/cloud-gate)

GOLD = {"i00": "FLAG", "i01": "CLEAR", "i02": "FLAG"}
B1_LABEL = {"FLAG": "contradictory", "CLEAR": "not_contradictory"}


def write_keys(tmp):
    """One fixture key per gate document: its item and gold."""
    keys = {}
    for d, i in base.GATE_DOCS.items():
        keys[d] = Path(tmp) / "keys" / (d + ".json")
        keys[d].parent.mkdir(parents=True, exist_ok=True)
        keys[d].write_text(json.dumps({"document_id": d, "benchmark": "contradoc", "items": [
            {"item_id": i, "rule_id": "R1", "gold": GOLD[i]}]}), encoding="utf-8")
    return keys


@contextlib.contextmanager
def fake_scorer():
    """item_table reads the fixture key; benchmark_labels reads the B1 label files label_rows writes
    and the key's gold; the adapters are the real ones."""
    import doc_judge

    def labels(key, folder, arm):
        table = json.loads(Path(key).read_text(encoding="utf-8"))
        out = []
        for item in table["items"]:
            label = json.loads((Path(folder) / "labels" / (item["item_id"] + ".json")).read_text(encoding="utf-8"))["label"]
            cls = {v: k for k, v in B1_LABEL.items()}.get(label, "ABSTAIN")
            out.append({"item_id": item["item_id"], "gold_class": item["gold"], "b1_class": cls})
        return {"availability": "labelled", "arm": arm, "items": out}
    sys.path.insert(0, str(Path(doc_judge.__file__).resolve().parents[2] / "tools"))
    import score_corpus as real   # the real module for its adapters, whatever doc_judge._score_corpus is patched to
    scorer = types.SimpleNamespace(item_table=lambda key: json.loads(Path(key).read_text(encoding="utf-8")),
                                   benchmark_labels=labels, _adapter_for=real._adapter_for)
    with patch.object(doc_judge, "_score_corpus", lambda: scorer), patch.object(doc_judge, "load_prompts", lambda path: None):
        yield


@contextlib.contextmanager
def gate_fixture(drop=None):
    """The base checks' gate files as a quick subset (the pin patched to the fixture's digest), an
    allowed sets file naming them, one fixture key per document, and a fake scorer: item_table reads
    the key, benchmark_labels reads the B1 label files label_rows writes and the key's gold."""
    import doc_judge
    import gate_score
    with tempfile.TemporaryDirectory(prefix="shimmer_steering_gate_") as tmp:
        tmp = Path(tmp)
        subset, prompts = base.gate_files(tmp, set_name="quick", drop=drop)
        runs = tmp / "output" / "cloud_reference_steering"
        runs.mkdir(parents=True)
        sets = tmp / "sets.json"
        sets.write_text(json.dumps({"allowed": [{"name": "fixture gate quick subset", "prompts_sha256": cr.sha(prompts),
                                                 "subset_sha256": cr.sha(subset)}], "refused": []}), encoding="utf-8")
        keys = write_keys(tmp)
        with patch.object(gate_score, "QUICK_SET_SHA256", cr.sha(subset)), fake_scorer():
            yield types.SimpleNamespace(tmp=tmp, subset=subset, prompts=prompts, runs=runs, sets=sets, keys=keys)


class GateCaller(FakeCaller):
    """Answers in B1's own reply form: the gold label on judge_direct, the other one on judge_reason."""

    def __init__(self, mode="split"):
        super().__init__()
        self.mode = mode

    def __call__(self, model, text, cwd):
        super().__call__(model, text, cwd)
        return self.answer(text, self.mode), None, None

    @staticmethod
    def answer(text, mode="split"):
        """`split`: judge_direct right, judge_reason wrong. `tie`: both right. `floor`: judge_direct
        right on two items and unreadable on the third (past D-241's floor), judge_reason wrong."""
        group = "judge_reason" if "judge_reason" in text else "judge_direct"
        item = {"cd%s" % i[1:]: i for i in GOLD}[text.split("document ")[1].split(",")[0]]
        gold = GOLD[item]
        wrong = B1_LABEL["CLEAR" if gold == "FLAG" else "FLAG"]
        if group == "judge_direct":
            if mode == "floor" and item == "i02":
                return "no reply object here"
            label = B1_LABEL[gold]
        else:
            label = B1_LABEL[gold] if mode == "tie" else wrong
        return json.dumps({"item_id": item, "label": label, "evidence": "", "reason": "fixture"})


class GateClient(base.FakeClient):
    """The paid run's fake client, answering in B1's own reply form as GateCaller does."""

    def create(self, **params):
        reply = super().create(**params)
        text = (params.get("system") or "") + "\n\n" + params["messages"][0]["content"]
        reply.content = [types.SimpleNamespace(type="text", text=GateCaller.answer(text))]
        return reply


def proof_paid_cloud_arm(gs=None):
    """The paid gate run's cloud arm (gate_score.cloud_arm, steering False) on the claim set: one row
    per item in the adapter's label space, no claim mark; refused for a run of another kind, a run on
    another set digest, another prompts file, and when read as a steering check."""
    import gate_score
    import shutil
    gs = gs or gate_score
    out = {}
    with base.sandbox() as box:
        set_file, prompts = base.gate_files(box.tmp)
        pin = cr.sha(set_file)
        with patch.object(gate_score, "CLAIM_SET_SHA256", pin), patch.object(gs, "CLAIM_SET_SHA256", pin):
            base.go_gate(box, GateClient(), set_file, prompts)
            folder = box.runs / "gate"
            keys = write_keys(box.tmp)

            def variant(name, **fields):
                target = box.tmp / name
                shutil.copytree(folder, target)
                m = json.loads((target / cr.MEASUREMENT_FILE).read_text(encoding="utf-8"))
                m.update(fields)
                (target / cr.MEASUREMENT_FILE).write_text(json.dumps(m), encoding="utf-8")
                return target
            other_prompts = box.tmp / "other_prompts.json"
            other_prompts.write_bytes(prompts.read_bytes() + b" ")

            def why(call):
                try:
                    call()
                except ValueError as exc:
                    return str(exc)
                return None
            with fake_scorer():
                rows = gs.cloud_arm("contradoc", prompts, folder, keys, set_file, "judge_direct", steering=False)
                out["kind"] = why(lambda: gs.cloud_arm("contradoc", prompts, variant("j1kind", kind=cr.SCHEMA), keys, set_file,
                                                       "judge_direct", steering=False))
                out["set"] = why(lambda: gs.cloud_arm("contradoc", prompts, variant("otherset", gate_set_sha256="e" * 64), keys,
                                                      set_file, "judge_direct", steering=False))
                out["prompts"] = why(lambda: gs.cloud_arm("contradoc", other_prompts, folder, keys, set_file, "judge_direct",
                                                          steering=False))
                out["as steering"] = why(lambda: gs.cloud_arm("contradoc", prompts, folder, keys, set_file, "judge_direct",
                                                              steering=True))
            spec = gs._adapter("contradoc").SPEC
    right = sum(r["label"] == spec.label(GOLD[r["item_id"]]) for r in rows)
    ok = (len(rows) == 3 and right == 3 and all("claim" not in r for r in rows)
          and out["kind"] and "not a paid gate run" in out["kind"] and out["set"] and "claim set it ran on" in out["set"]
          and out["prompts"] and "not a pass of these prompts" in out["prompts"]
          and out["as steering"] and "not a subscription steering check" in out["as steering"])
    return ok, "rows %d, right %d, no claim mark %s; refusals %s" % (len(rows), right, all("claim" not in r for r in rows), out)


def gate_steer(g, caller, name="gate", mod=st):
    return mod.run(g.prompts, g.subset, cr.sha(g.subset), g.runs / name, caller=caller, runs_root=g.runs,
                   status=signed_in, sets_path=g.sets, fresh_source=g.tmp / "no_system_test.py")


def proof_gate_quick_subset_file(mod=st):
    """The gate's frozen quick subset file is a subset: its items read for the prompts' benchmark,
    every one of them in every group sent; a prompts file missing one, a set file that is not the
    pinned quick subset, and the claim set's file refuse with no call."""
    import gate_score
    with gate_fixture() as g:
        caller = FakeCaller()
        m = gate_steer(g, caller, mod=mod)
        sent = len(caller.calls)
        with patch.object(gate_score, "QUICK_SET_SHA256", "0" * 64):
            unpinned = refused(lambda: gate_steer(g, FakeCaller(), "unpinned", mod=mod))
        (g.tmp / "claim").mkdir()
        claim, claim_prompts = base.gate_files(g.tmp / "claim")
        sets = json.loads(g.sets.read_text(encoding="utf-8"))
        sets["allowed"].append({"name": "the claim set, listed to reach the subset reader",
                                "prompts_sha256": cr.sha(claim_prompts), "subset_sha256": cr.sha(claim)})
        g.sets.write_text(json.dumps(sets), encoding="utf-8")
        as_claim = refused(lambda: mod.run(claim_prompts, claim, cr.sha(claim), g.runs / "claim", caller=caller,
                                           runs_root=g.runs, status=signed_in, sets_path=g.sets,
                                           fresh_source=g.tmp / "none.py"))
    with gate_fixture(drop=("judge_reason", "i01")) as g:
        missing_caller = FakeCaller()
        missing = refused(lambda: gate_steer(g, missing_caller, "missing", mod=mod))
    ok = (sent == 6 and m["sent"] == 6 and m["gate_benchmark"] == "contradoc" and unpinned
          and "frozen quick subset" in unpinned and as_claim and "frozen quick subset file" in as_claim
          and missing and "not the quick subset's" in missing and not missing_caller.calls)
    return ok, "sent %d (benchmark %s); unpinned: %r; the claim set's file: %r; a missing item: %r" % (
        sent, m.get("gate_benchmark"), unpinned, as_claim, missing)


def proof_cloud_arm_is_steering_only(gs=None):
    """A steering check's cloud arm (`read`, through gate_score.cloud_arm) gives one row per item in the
    adapter's label space, each `claim: false`; gate_score.figures takes it beside the system and B1 on
    the quick subset (steering only) and refuses it on the claim set; the paid reader refuses it."""
    import gate_score
    gs = gs or gate_score
    with gate_fixture() as g:
        gate_steer(g, GateCaller())
        folder = g.runs / "gate"
        _rows, summary = st.read(g.prompts, folder, g.subset, list(g.keys.values()))
        rows = gs.cloud_arm("contradoc", g.prompts, folder, g.keys, g.subset, "judge_direct", steering=True)
        reason_rows = gs.cloud_arm("contradoc", g.prompts, folder, g.keys, g.subset, "judge_reason", steering=True)
        spec = gs._adapter("contradoc").SPEC
        truth = [{"item_id": i, "cluster": d, "label": spec.label(GOLD[i]), "gold": spec.label(GOLD[i])}
                 for d, i in base.GATE_DOCS.items()]
        arms = {"system": truth, "b1": truth, "cloud": rows}
        quick = gs.figures("contradoc", arms, g.subset)
        with patch.object(gs, "CLAIM_SET_SHA256", cr.sha(g.subset)), patch.object(gs, "QUICK_SET_SHA256", "0" * 64):
            try:
                gs.figures("contradoc", arms, g.subset)
                claim = None
            except cg.SteeringNotAClaim as exc:
                claim = str(exc)
            except ValueError as exc:
                claim = "not the steering refusal: " + str(exc)
            paid = refused(lambda: gs.cloud_arm("contradoc", g.prompts, folder, g.keys, g.subset, "judge_direct",
                                                steering=False))
    right = sum(r["label"] == t["label"] for r, t in zip(sorted(rows, key=lambda r: r["item_id"]), truth))
    wrong = sum(r["label"] != t["label"] for r, t in zip(sorted(reason_rows, key=lambda r: r["item_id"]), truth))
    ok = (len(rows) == 3 and all(r.get("claim") is False for r in rows) and right == 3 and wrong == 3
          and summary["label"] == LABEL and summary["claim"] is False and summary["items"] == 3
          and quick["read"] == "steering only" and quick["arms"]["cloud"]["value"] == 1.0
          and quick["against_cloud"]["value"] == 0.0
          and claim and "never" in claim and not claim.startswith("not the") and paid and "never" in paid)
    return ok, ("rows %d, claim false on each %s, direct right %d of 3, reasoning wrong %d of 3; quick read %r, cloud %s; "
                "on the claim set: %r; the paid reader: %r" % (len(rows), all(r.get("claim") is False for r in rows), right,
                                                                wrong, quick["read"], quick["arms"]["cloud"]["value"], claim, paid))


def proof_cloud_arm_takes_b1_s_comparator_rule(gs=None):
    """D-554: the cloud arm is B1's comparator rule over its two groups (choice_read.choose_group):
    the better group in the paper's metric, a tie to judge_reason, a group past D-241's abstain floor
    no comparator; the steering read reports the group it took."""
    import gate_score
    gs = gs or gate_score
    picked = {}
    for mode in ("split", "tie", "floor"):
        with gate_fixture() as g:
            gate_steer(g, GateCaller(mode), name=mode)
            rows, record = gs.cloud_reference_arm("contradoc", g.prompts, g.runs / mode, g.keys, g.subset, steering=True)
            _rows, summary = st.read(g.prompts, g.runs / mode, g.subset, list(g.keys.values()))
            picked[mode] = (record["group"], summary["group"], record["groups"][record["group"]]["value"])
    ok = (picked["split"][:2] == ("judge_direct", "judge_direct") and picked["tie"][:2] == ("judge_reason", "judge_reason")
          and picked["floor"][:2] == ("judge_reason", "judge_reason"))
    return ok, "chosen (arm, read, value): %s" % picked


def _gate_score_with(old, new):
    import gate_score
    source = Path(gate_score.__file__).read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError("the passage moved, so the neutralisation cannot be applied")
    gs = types.ModuleType("gate_score_neutralised")
    gs.__file__ = gate_score.__file__
    exec(compile(source.replace(old, new), gate_score.__file__, "exec"), gs.__dict__)
    return gs


def _swap_proof(name, **kwargs):
    @contextlib.contextmanager
    def swap():
        original = globals()[name]
        made = {k: v() for k, v in kwargs.items()}
        globals()[name] = lambda: original(**made)
        try:
            yield
        finally:
            globals()[name] = original
    return swap


def _top_level_only(value):
    return isinstance(value, dict) and (value.get("claim") is False or value.get("label") == LABEL)


def _module_with(old, new):
    source = Path(st.__file__).read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError("the passage moved, so the neutralisation cannot be applied")
    mod = types.ModuleType("cloud_reference_steering_neutralised")
    mod.__file__ = st.__file__
    exec(compile(source.replace(old, new), st.__file__, "exec"), mod.__dict__)
    return mod


@contextlib.contextmanager
def _unlabelled():
    mod = _module_with('    stamp = {"label": claim_guard.STEERING_LABEL, "kind": claim_guard.STEERING_KIND, "claim": False}',
                       '    stamp = {}')
    original = globals()["steer"]
    globals()["steer"] = lambda box, subset, runs, caller, name="check", mod=mod: original(box, subset, runs, caller, name, mod)
    try:
        yield
    finally:
        globals()["steer"] = original


PROOFS = [
    ("the gate's frozen quick subset file is a subset: every item in every group, the claim set refused",
     proof_gate_quick_subset_file),
    ("a steering check's cloud arm is steering only: figures take it on the quick subset, refuse it on the claim set",
     proof_cloud_arm_is_steering_only),
    ("the paid gate run's cloud arm reads the claim set into labelled rows; each wrong input refused", proof_paid_cloud_arm),
    ("the cloud arm takes B1's comparator rule over its two groups (D-554)", proof_cloud_arm_takes_b1_s_comparator_rule),
    ("the call is headless Claude Code on the subscription, the registry's alias, no tools, no API credential",
     proof_call_is_the_subscription_with_the_registry_alias),
    ("every file the steering check writes carries the label and claim false", proof_every_file_carries_the_label),
    ("the scorer refuses a steering pass as the cloud reference's figure", proof_the_scorer_refuses_a_steering_pass),
    ("a page or report row holding a steering result is refused; an API run is not", proof_the_page_refuses_a_steering_row),
    ("the CLI's own status must report a subscription sign-in, recorded, before any call", proof_only_a_subscription_sign_in),
    ("only an allowed set runs; the fresh set is refused by digest", proof_only_allowed_sets),
]

NEUTRALISATIONS = [
    ("the cloud arm always judge_direct, not B1's rule", "proof_cloud_arm_takes_b1_s_comparator_rule",
     _swap_proof("proof_cloud_arm_takes_b1_s_comparator_rule", gs=lambda: _gate_score_with(
         "chosen = choice_read.choose_group(benchmark, groups)", 'chosen = "judge_direct"'))),
    ("B1's rule with no abstain floor", "proof_cloud_arm_takes_b1_s_comparator_rule",
     lambda: patch.object(__import__("doc_judge"), "BAR_MAX_B1_ABSTAIN", 1.0)),
    ("the paid arm's kind not read", "proof_paid_cloud_arm", _swap_proof("proof_paid_cloud_arm", gs=lambda: _gate_score_with(
        'if measurement.get("kind") != CLOUD_KINDS["paid"]:', "if False:"))),
    ("the paid arm's set digest not read", "proof_paid_cloud_arm", _swap_proof("proof_paid_cloud_arm", gs=lambda: _gate_score_with(
        'if set_sha256 != CLAIM_SET_SHA256 or measurement.get("gate_set_sha256") != set_sha256:',
        "if set_sha256 != CLAIM_SET_SHA256:"))),
    ("the paid arm's prompts digest not read", "proof_paid_cloud_arm", _swap_proof("proof_paid_cloud_arm", gs=lambda: _gate_score_with(
        'if measurement.get("prompts_sha256") != hashlib.sha256(Path(prompts).read_bytes()).hexdigest():', "if False:"))),
    ("the quick subset's items not held to the prompts", "proof_gate_quick_subset_file",
     _swap_proof("proof_gate_quick_subset_file", mod=lambda: _module_with("and set(ids) == set(listed),", "or True,"))),
    ("the quick subset's pin not compared", "proof_gate_quick_subset_file",
     _swap_proof("proof_gate_quick_subset_file", mod=lambda: _module_with(
         "cr.refuse(cr.sha(subset_path) == gate_score.QUICK_SET_SHA256,", "cr.refuse(True,"))),
    ("figures taking a steering arm on the claim set", "proof_cloud_arm_is_steering_only",
     _swap_proof("proof_cloud_arm_is_steering_only", gs=lambda: _gate_score_with(
         'claim_guard.refuse_claim(rows, "an arm of a claim read (arm %s)" % name)', "pass"))),
    ("the cloud arm's rows not marked claim false", "proof_cloud_arm_is_steering_only",
     _swap_proof("proof_cloud_arm_is_steering_only", gs=lambda: _gate_score_with(
         "rows = [dict(r, claim=False) for r in rows]", "pass"))),
    ("the paid reader taking a steering folder", "proof_cloud_arm_is_steering_only",
     _swap_proof("proof_cloud_arm_is_steering_only", gs=lambda: _gate_score_with(
         "claim_guard.refuse_claim(measurement if claim_guard.is_steering(measurement) else list(records.values()),",
         "(measurement if claim_guard.is_steering(measurement) else list(records.values()),"))),
    ("the API credentials left in the child's environment", "proof_call_is_the_subscription_with_the_registry_alias",
     lambda: patch.object(st, "child_environment", lambda: dict(os.environ))),
    ("the files written without the label", "proof_every_file_carries_the_label", _unlabelled),
    ("the scorer's steering test removed", "proof_the_scorer_refuses_a_steering_pass",
     lambda: patch.object(cg, "is_steering", lambda value: False)),
    ("only the top level read for the label", "proof_the_page_refuses_a_steering_row",
     lambda: patch.object(cg, "is_steering", _top_level_only)),
    ("every record taken for steering", "proof_the_page_refuses_a_steering_row",
     lambda: patch.object(cg, "is_steering", lambda value: True)),
    ("only the API key variables stripped", "proof_call_is_the_subscription_with_the_registry_alias",
     lambda: patch.object(st, "stripped", lambda name: name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"))),
    ("any sign-in accepted", "proof_only_a_subscription_sign_in",
     lambda: patch.object(st, "check_subscription", lambda reading, error: reading)),
    ("any set accepted", "proof_only_allowed_sets",
     lambda: patch.object(st, "allowed_set", lambda *a, **k: {"name": "any"})),
    ("system_test.py's fresh digest not read", "proof_only_allowed_sets",
     lambda: patch.object(st, "fresh_digests", lambda source=None: set())),
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
    print("%s steering checks: %d of %d proofs and neutralisations pass" % ("PASS" if not failures else "FAIL",
                                                                          total - failures, total))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
