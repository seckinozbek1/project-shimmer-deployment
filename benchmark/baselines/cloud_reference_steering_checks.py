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
    ("the call is headless Claude Code on the subscription, the registry's alias, no tools, no API credential",
     proof_call_is_the_subscription_with_the_registry_alias),
    ("every file the steering check writes carries the label and claim false", proof_every_file_carries_the_label),
    ("the scorer refuses a steering pass as the cloud reference's figure", proof_the_scorer_refuses_a_steering_pass),
    ("a page or report row holding a steering result is refused; an API run is not", proof_the_page_refuses_a_steering_row),
    ("the CLI's own status must report a subscription sign-in, recorded, before any call", proof_only_a_subscription_sign_in),
    ("only an allowed set runs; the fresh set is refused by digest", proof_only_allowed_sets),
]

NEUTRALISATIONS = [
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
