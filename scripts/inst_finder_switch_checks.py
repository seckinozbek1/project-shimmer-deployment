"""Gate check 277: the operator setting SHIMMER_INST_FINDER switches INST_FINDER off
only under a ratified DELTA, and is never ignored silently.

Four cases, each in a temporary directory with copied configuration (the real
config/, durable/ and ontology/ are never written):

  (a) the variable absent: INST_FINDER is dispatched exactly as before;
  (b) `off` with the real constitution: the start-up guard refuses with one line
      naming the missing DELTA, main() returns 9 on it before any model call, and
      phase 3-4 refuses rather than dispatching;
  (c) `off` with a fixture constitution carrying a ratified amendment: INST_FINDER
      is not dispatched, the activation record gives the reason, and every
      gathered result carries its own agent's name;
  (d) the decision is made once, by main() at start-up, and saved: a constitution
      or variable changed between start-up and phase time does not change what
      phase 3-4 dispatches, what the cost projection counts or what the progress
      baseline counts, in either direction; an unreadable saved record refuses;
  (e) D-570, off by default: with no value INST_FINDER is off only under a ratified
      amendment that declares `"default": "off"` (on with none, and on under one that
      ratifies the switch alone), recorded with source `default` and stated in the
      run summary; `on` runs it with or without the amendment; the sealer's test,
      which evaluates the same bound function, seals the same setting.

Every case drives the real code (pipeline._inst_finder_startup_guard and
pipeline.phase_3_4_content_production, with the model boundary replaced: no
wrapper is built and no model is called) under semantic_waves.enabled() true and
false, and each is proved by neutralise, fail, restore, pass. No generation.
"""
from __future__ import annotations

import ast
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sys

import pipeline
import routing_view
import run_context as run_context_mod

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
VARIABLE = "SHIMMER_INST_FINDER"
REASON = "switched off by operator setting"
ALL = ["ARCHIVIST", "INST_FINDER", "CITATION_RESOLVER"]
FIXTURE_ID = "FIXTURE-INST-FINDER-SWITCH"
PROOFS = []


@contextmanager
def _setting(value):
    with patch.dict(os.environ):
        os.environ.pop(VARIABLE, None)
        if value is not None:
            os.environ[VARIABLE] = value
        yield


def _real_ratifying_ids():
    """Amendments in the REAL constitution that would ratify the switch (none today)."""
    with _setting("off"):
        record = pipeline._inst_finder_switch(ROOT)
    return [] if record["refusal"] else [record["ratified_by"]]


def _root(tmp, *, amendment=None, strip_ratifying=False):
    """A throwaway project root with copies of the configuration the run reads."""
    root = Path(tmp) / "root"
    (root / "config").mkdir(parents=True)
    for name in ("constitution.json", "agent_registry.json", "agent_contracts.json"):
        shutil.copy2(ROOT / "config" / name, root / "config" / name)
    path = root / "config" / "constitution.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if strip_ratifying:
        ids = set(_real_ratifying_ids())
        data["amendments"] = [a for a in data.get("amendments", []) if a.get("id") not in ids]
    if amendment is not None:
        data["amendments"].append(amendment)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return root


def _ratifying(**overrides):
    value = {"id": FIXTURE_ID, "created": "2026-10-27", "kind": "agent_switch",
             "title": "Fixture: the operator may switch INST_FINDER off per run",
             "operator_approved": True,
             "change": {"setting": "SHIMMER_INST_FINDER=off switches INST_FINDER off for the run."}}
    value.update(overrides)
    return value


DEFAULT_OFF = {"default": "off",
               "setting": "SHIMMER_INST_FINDER: with no value INST_FINDER is off by default; on runs it."}


def _switch_with(old, new):
    """pipeline._inst_finder_switch rebuilt from its own source with one passage replaced."""
    tree = ast.parse(Path(pipeline.__file__).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_inst_finder_switch")
    source = ast.get_source_segment(Path(pipeline.__file__).read_text(encoding="utf-8"), node)
    assert source.count(old) == 1, "the passage moved, so the neutralisation cannot be applied"
    namespace = {}
    exec(compile(source.replace(old, new), pipeline.__file__, "exec"), pipeline.__dict__, namespace)
    return namespace["_inst_finder_switch"]


def _mutated_phase(transform):
    """phase_3_4_content_production rebuilt from its own source after `transform`,
    with the pipeline module's globals, so the same patches apply to it."""
    tree = ast.parse(Path(pipeline.__file__).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                and n.name == "phase_3_4_content_production")
    transform(node)
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), pipeline.__file__, "exec"),
         pipeline.__dict__, namespace)
    return namespace["phase_3_4_content_production"]


def _label_with_the_constant(node):
    replaced = 0
    for call in ast.walk(node):
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "zip"
                and call.args and isinstance(call.args[0], ast.Name) and call.args[0].id == "dispatched"):
            call.args[0] = ast.Name(id="PRODUCTION_AGENTS_CORPUS_LEVEL", ctx=ast.Load())
            replaced += 1
    assert replaced == 1, replaced


def _produce(root, waves, phase=None, ctx=None):
    """Run the real phase 3-4 corpus loop with the model boundary replaced. With
    `ctx`, the phase runs in that run folder (and reads any decision saved there)."""
    ctx = ctx or run_context_mod.create_run(root)
    agents = json.loads((root / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    pipeline.agent_activation.initialize(ctx, agents, "dense")
    orch = SimpleNamespace(run_context=ctx)
    requested = []

    def run_one(wrapper, payload, objectives, **kwargs):
        requested.append(wrapper.name)

        async def reply():
            return {"ok": True, "parsed": None, "called_as": wrapper.name}
        return reply()

    function = phase or pipeline.phase_3_4_content_production
    error = None
    results = []
    with patch.object(pipeline, "_build_wrapper", lambda name, orch, keys: SimpleNamespace(name=name)), \
            patch.object(pipeline, "_run_one", run_one), \
            patch.object(pipeline.semantic_waves, "enabled", lambda: waves):
        try:
            results = asyncio.run(function(orch, {}, [], [], "Fixture objective", {"conventions": []},
                                           SimpleNamespace(entries=[]), []))
        except RuntimeError as exc:
            error = str(exc)
    audit = json.loads((ctx.audit_dir() / "agent_activation.json").read_text(encoding="utf-8"))
    return {"requested": requested, "error": error, "ctx": ctx, "audit": audit,
            "labels": [(r["agent"], r.get("called_as")) for r in results if r.get("scope") == "corpus"]}


def _main_guard_order(source):
    """main() saves the setting after the run options and returns 9 on a refusal
    before the sensitivity gate, the cost tracker and the first key load."""
    main = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "main")
    text = [ast.unparse(s) for s in main.body]
    configure = next(i for i, t in enumerate(text) if t.startswith("run_options.configure("))
    guard = text.index("inst_finder_refusal = _inst_finder_startup_guard(run_ctx, ROOT)")
    refusal = main.body[guard + 1]
    assert isinstance(refusal, ast.If) and ast.unparse(refusal.test) == "inst_finder_refusal", \
        "main() does not act on the guard's refusal right after the guard"
    assert any(isinstance(s, ast.Return) and ast.unparse(s.value) == "9" for s in refusal.body), \
        "main() does not return 9 on the refusal"
    later = [next(i for i, t in enumerate(text) if marker in t) for marker in
             ("sensitivity_layer.is_active()", "CostTracker.open(", "load_api_keys()")]
    assert configure < guard < min(later), (configure, guard, later)


def _without_refusal(source):
    tree = ast.parse(source)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    main.body = [s for s in main.body if not (isinstance(s, ast.If) and ast.unparse(s.test) == "inst_finder_refusal")]
    return ast.unparse(tree)


def _summary(ctx):
    return pipeline.write_deliverables_run_summary(
        ctx.deliverables_dir(), [], {}, total_cost_usd=0.0, task="review").read_text(encoding="utf-8")


def _projected_calls(root, ctx=None):
    seen = {}
    with patch.object(pipeline, "ROOT", root), \
            patch.object(pipeline, "estimate_cost", lambda **kw: seen.update(kw) or kw):
        pipeline._cost_projection(1, 0, run_ctx=ctx)
        return seen["claude_calls"], pipeline._local_progress_baseline(1, run_ctx=ctx)


def _corpus_count(calls, progress):
    """The corpus-level agents counted by the cost projection and the progress
    baseline, for one operational document."""
    return (calls - len(pipeline.PRODUCTION_AGENTS_PER_DOC) - len(pipeline.CONVENTION_REVIEW_AGENTS) - 1 - 3,
            progress - len(pipeline.PRODUCTION_AGENTS_PER_DOC) - len(pipeline.AUDIT_AGENTS_PER_DOC)
            - len(pipeline.CONVENTION_REVIEW_AGENTS) - 1)


class InstFinderSwitchChecks(unittest.TestCase):
    def prove(self, case, name, observe, neutralise):
        observe()                                      # pass
        with neutralise():
            with self.assertRaises(AssertionError):    # neutralised: fails
                observe()
        observe()                                      # restored: passes again
        PROOFS.append("%s:%s" % (case, name))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="shimmer_check277_")
        self.addCleanup(self.tmp.cleanup)

    # (a) absent: dispatched exactly as before ------------------------------------
    def test_a_absent_dispatches_as_before(self):
        root = _root(self.tmp.name, strip_ratifying=True)   # the state before a ratified default off (INFRA-052)
        baseline_calls, baseline_progress = None, None

        def observe():
            nonlocal baseline_calls, baseline_progress
            with _setting(None):
                ctx = run_context_mod.create_run(root)
                self.assertIsNone(pipeline._inst_finder_startup_guard(ctx, root))
                saved = json.loads((ctx.audit_dir() / "agent_switches.json").read_text(encoding="utf-8"))
                self.assertEqual((saved["setting"], saved["value"], saved["switched_off"]), ("on", None, []))
                self.assertIn("- INST_FINDER: switched on for this run", _summary(ctx))
                for waves in (False, True):
                    out = _produce(root, waves)
                    self.assertIsNone(out["error"])
                    self.assertEqual(out["requested"], ALL)
                    self.assertEqual([a for a, _ in out["labels"]], ALL)
                    self.assertTrue(all(a == c for a, c in out["labels"]), out["labels"])
                    self.assertFalse([d for d in out["audit"]["decisions"] if d["agent"] == "INST_FINDER"])
                calls, progress = _projected_calls(root)
                self.assertEqual(calls - len(pipeline.PRODUCTION_AGENTS_PER_DOC) - len(pipeline.CONVENTION_REVIEW_AGENTS) - 1 - 3, 3)
                self.assertEqual(progress, len(ALL) + len(pipeline.PRODUCTION_AGENTS_PER_DOC)
                                 + len(pipeline.AUDIT_AGENTS_PER_DOC) + len(pipeline.CONVENTION_REVIEW_AGENTS) + 1)

        real = pipeline._inst_finder_switch

        def default_not_honoured(root_):
            record = dict(real(root_))
            record.update(setting="off", switched_off=["INST_FINDER"], ratified_by="ignored")
            return record
        self.prove("a", "default_not_honoured", observe,
                   lambda: patch.object(pipeline, "_inst_finder_switch", default_not_honoured))

    # (e) D-570: no value under a ratified default off; `on` always runs it ---------
    def test_e_default_off_only_under_a_ratified_default(self):
        tmp = Path(self.tmp.name)
        roots = {"none": _root(tmp / "none", strip_ratifying=True),
                 "switch only": _root(tmp / "switch", amendment=_ratifying(), strip_ratifying=True),
                 "default off": _root(tmp / "default", amendment=_ratifying(change=DEFAULT_OFF), strip_ratifying=True)}

        sealer_source = [None]   # None: the pipeline file as it stands; a neutralisation swaps it

        def expected(value, kind):
            """(setting, switched off, source, summary line, refused) for a value under an amendment kind."""
            asked = value.strip().lower() if isinstance(value, str) else None
            asked = asked or None
            if asked not in (None, "on", "off"):
                return "on", [], "variable", "- INST_FINDER: the setting was neither on nor off", True
            source = "default" if asked is None else "variable"
            off = (asked == "off" and kind != "none") or (asked is None and kind == "default off")
            if asked == "off" and kind == "none":
                return "off", [], source, "- INST_FINDER: switched off without a ratified amendment", True
            if not off:
                return "on", [], source, "- INST_FINDER: switched on for this run", False
            line = ("- INST_FINDER: off by default for this run, as ratified in amendment " if kind == "default off"
                    else "- INST_FINDER: switched off for this run by the operator, as ratified in amendment ") + FIXTURE_ID
            return "off", ["INST_FINDER"], source, line, False

        def observe():
            for value in (None, "", "on", "On", "off", " off ", "OFF", "maybe"):
                for kind, root in roots.items():
                    setting, off, source, line, refused = expected(value, kind)
                    with _setting(value):
                        ctx = run_context_mod.create_run(root)
                        refusal = pipeline._inst_finder_startup_guard(ctx, root)
                        self.assertEqual(bool(refusal), refused, (value, kind, refusal))
                        saved = json.loads((ctx.audit_dir() / "agent_switches.json").read_text(encoding="utf-8"))
                        self.assertEqual((saved["setting"], saved["switched_off"], saved["source"]),
                                         (setting, off, source), (value, kind))
                        self.assertIn(line, _summary(ctx), (value, kind))
                        if refused:
                            continue
                        if off:
                            self.assertEqual(saved["ratified_by"], FIXTURE_ID)
                        for waves in (False, True):
                            out = _produce(root, waves, ctx=ctx)
                            self.assertIsNone(out["error"])
                            self.assertEqual(out["requested"], [a for a in ALL if a not in off], (value, kind, waves))
                            if off:
                                row = next(d for d in out["audit"]["decisions"] if d["agent"] == "INST_FINDER")
                                self.assertEqual((row["state"], row["evidence"]["source"]), ("switched_off", source))
            # The sealer evaluates the same bound function from the source file: the same setting, or a refusal.
            import prepare_ordinary_final_run as prep
            files = {"scripts/pipeline.py": sealer_source[0] or Path(pipeline.__file__).read_bytes()}
            for kind, root in roots.items():
                files["config/constitution.json"] = (root / "config" / "constitution.json").read_bytes()
                for value in (None, "", "on", "On", "off", " off ", "OFF", "maybe"):
                    setting, _off, _source, _line, refused = expected(value, kind)
                    record = prep.inst_finder_setting(files, value)
                    self.assertEqual((record["setting"], bool(record["refusal"])), (setting, refused), ("sealer", value, kind))

        real = pipeline._inst_finder_switch

        def no_value_forced_on(root_):
            record = dict(real(root_))
            if not (record["value"] or "").strip():
                record.update(setting="on", switched_off=[], ratified_by=None)
            return record

        def no_value_forced_off(root_):
            record = dict(real(root_))
            if not (record["value"] or "").strip():
                record.update(setting="off", switched_off=["INST_FINDER"], ratified_by="forced")
            return record

        def on_ignored(root_):
            with _setting(None):
                return real(root_)
        self.prove("e", "default_off_ignored", observe,
                   lambda: patch.object(pipeline, "_inst_finder_switch", no_value_forced_on))
        self.prove("e", "default_off_without_a_ratified_default", observe,
                   lambda: patch.object(pipeline, "_inst_finder_switch", no_value_forced_off))
        self.prove("e", "on_not_honoured", observe,
                   lambda: patch.object(pipeline, "_inst_finder_switch", on_ignored))
        self.prove("e", "any_ratifying_amendment_taken_as_default_off", observe,
                   lambda: patch.object(pipeline, "_inst_finder_switch", _switch_with(
                       "if value is None and not declares_default_off:", "if False:")))

        @contextmanager
        def sealer_reads_a_neutralised_source():
            text = Path(pipeline.__file__).read_text(encoding="utf-8")
            old = "if value is None and not declares_default_off:"
            assert text.count(old) == 1, "the passage moved, so the neutralisation cannot be applied"
            sealer_source[0] = text.replace(old, "if False:").encode("utf-8")
            try:
                yield
            finally:
                sealer_source[0] = None
        self.prove("e", "sealer_source_takes_any_ratifying_amendment_as_default_off", observe,
                   sealer_reads_a_neutralised_source)

        def odd_values_taken_as_on(root_):
            record = dict(real(root_))
            if record["refusal"] and record["setting"] == "on":
                record["refusal"] = None
            return record
        self.prove("e", "a_value_neither_on_nor_off_accepted", observe,
                   lambda: patch.object(pipeline, "_inst_finder_switch", odd_values_taken_as_on))

    # (b) off with the real constitution: refuses -----------------------------------
    def test_b_off_without_ratification_refuses(self):
        root = _root(self.tmp.name, strip_ratifying=True)
        source = Path(pipeline.__file__).read_text(encoding="utf-8")

        def observe():
            with _setting("off"):
                ctx = run_context_mod.create_run(root)
                refusal = pipeline._inst_finder_startup_guard(ctx, root)
                self.assertTrue(refusal)
                self.assertNotIn("\n", refusal)
                for needle in ("SHIMMER_INST_FINDER=off", "INST_FINDER", "DELTA",
                               "docs/INST_FINDER_SWITCH_DELTA_DRAFT.md"):
                    self.assertIn(needle, refusal)
                saved = json.loads((ctx.audit_dir() / "agent_switches.json").read_text(encoding="utf-8"))
                self.assertEqual((saved["setting"], saved["refusal"], saved["switched_off"]), ("off", refusal, []))
                for waves in (False, True):
                    out = _produce(root, waves)
                    self.assertEqual(out["error"], refusal)
                    self.assertEqual(out["requested"], [])
                # Neither an unapproved amendment nor one naming only the agent ratifies.
                for weak in (_ratifying(operator_approved=False),
                             _ratifying(change={"setting": "INST_FINDER may be switched off."})):
                    path = root / "config" / "constitution.json"
                    original = path.read_text(encoding="utf-8")
                    try:
                        data = json.loads(original)
                        data["amendments"].append(weak)
                        path.write_text(json.dumps(data), encoding="utf-8")
                        self.assertTrue(pipeline._inst_finder_switch(root)["refusal"])
                    finally:
                        path.write_text(original, encoding="utf-8")
            _main_guard_order(source)

        real = pipeline._inst_finder_switch

        def refusal_dropped(root_):
            record = dict(real(root_))
            record["refusal"] = None
            return record
        self.prove("b", "refusal_dropped", observe,
                   lambda: patch.object(pipeline, "_inst_finder_switch", refusal_dropped))

        @contextmanager
        def main_return_dropped():
            nonlocal source
            saved, source = source, _without_refusal(source)
            try:
                yield
            finally:
                source = saved
        self.prove("b", "main_return_dropped", observe, main_return_dropped)

    # (c) off with a ratified fixture amendment: not dispatched, recorded ------------
    def test_c_off_ratified_is_not_dispatched_and_recorded(self):
        root = _root(self.tmp.name, amendment=_ratifying(), strip_ratifying=True)
        phase = [None]

        def observe():
            with _setting("off"):
                ctx = run_context_mod.create_run(root)
                self.assertIsNone(pipeline._inst_finder_startup_guard(ctx, root))
                saved = json.loads((ctx.audit_dir() / "agent_switches.json").read_text(encoding="utf-8"))
                self.assertEqual((saved["switched_off"], saved["ratified_by"]), (["INST_FINDER"], FIXTURE_ID))
                self.assertIn("switched off for this run by the operator, as ratified in amendment " + FIXTURE_ID,
                              _summary(ctx))
                for waves in (False, True):
                    out = _produce(root, waves, phase[0])
                    self.assertIsNone(out["error"])
                    self.assertEqual(out["requested"], ["ARCHIVIST", "CITATION_RESOLVER"])
                    self.assertEqual([a for a, _ in out["labels"]], ["ARCHIVIST", "CITATION_RESOLVER"])
                    self.assertTrue(all(a == c for a, c in out["labels"]), (waves, out["labels"]))
                    rows = [d for d in out["audit"]["decisions"] if d["agent"] == "INST_FINDER"]
                    self.assertEqual(len(rows), 1)
                    self.assertEqual((rows[0]["reason"], rows[0]["state"], rows[0]["activated"],
                                      rows[0]["actual_call"], rows[0]["evidence"]["ratified_by"]),
                                     (REASON, "switched_off", False, False, FIXTURE_ID))
                    state = next(s for s in out["audit"]["agent_states"] if s["agent"] == "INST_FINDER")
                    self.assertEqual((state["state"], state["actual_calls"]), ("switched_off", 0))
                    view = routing_view.read_activation(out["ctx"].run_dir, out["ctx"].run_id)
                    self.assertEqual(view["availability"], "recorded")
                    self.assertIn({"agent": "INST_FINDER", "state": "switched_off", "eligible": False,
                                   "activated": False, "actual_calls": 0}, view["agent_states"])
                self.assertIn("INST_FINDER", pipeline.PRODUCTION_AGENTS_CORPUS_LEVEL)
                calls, progress = _projected_calls(root)
                self.assertEqual(calls - len(pipeline.PRODUCTION_AGENTS_PER_DOC) - len(pipeline.CONVENTION_REVIEW_AGENTS) - 1 - 3, 2)
                self.assertEqual(progress, 2 + len(pipeline.PRODUCTION_AGENTS_PER_DOC)
                                 + len(pipeline.AUDIT_AGENTS_PER_DOC) + len(pipeline.CONVENTION_REVIEW_AGENTS) + 1)

        self.prove("c", "not_called_record_dropped", observe,
                   lambda: patch.object(pipeline.agent_activation, "not_called", lambda *a, **k: None))
        real = pipeline._inst_finder_switch

        def setting_ignored(root_):
            with _setting(None):
                return real(root_)
        self.prove("c", "setting_ignored", observe,
                   lambda: patch.object(pipeline, "_inst_finder_switch", setting_ignored))

        @contextmanager
        def labels_from_the_constant():
            phase[0] = _mutated_phase(_label_with_the_constant)
            try:
                yield
            finally:
                phase[0] = None
        self.prove("c", "labels_from_the_constant", observe, labels_from_the_constant)

    # (d) the decision is made once, at start-up: a later change does not move it ----
    def test_d_saved_decision_wins_over_a_later_change(self):
        root = _root(self.tmp.name, strip_ratifying=True)
        path = root / "config" / "constitution.json"
        unratified = path.read_text(encoding="utf-8")
        data = json.loads(unratified)
        data["amendments"].append(_ratifying())
        ratified = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

        def observe():
            try:
                # Started switched off under a ratified amendment; by phase time the
                # amendment is gone and the variable unset. The saved decision stands.
                path.write_text(ratified, encoding="utf-8")
                with _setting("off"):
                    ctx = run_context_mod.create_run(root)
                    self.assertIsNone(pipeline._inst_finder_startup_guard(ctx, root))
                path.write_text(unratified, encoding="utf-8")
                with _setting(None):
                    for waves in (False, True):
                        out = _produce(root, waves, ctx=ctx)
                        self.assertIsNone(out["error"])
                        self.assertEqual(out["requested"], ["ARCHIVIST", "CITATION_RESOLVER"])
                    self.assertEqual(_corpus_count(*_projected_calls(root, ctx)), (2, 2))
                # Started on; by phase time a ratifying amendment exists and the
                # variable says off. Still on: all three are dispatched.
                with _setting(None):
                    ctx = run_context_mod.create_run(root)
                    self.assertIsNone(pipeline._inst_finder_startup_guard(ctx, root))
                path.write_text(ratified, encoding="utf-8")
                with _setting("off"):
                    for waves in (False, True):
                        out = _produce(root, waves, ctx=ctx)
                        self.assertIsNone(out["error"])
                        self.assertEqual(out["requested"], ALL)
                    self.assertEqual(_corpus_count(*_projected_calls(root, ctx)), (3, 3))
                # A saved record that cannot be read refuses rather than recomputing.
                (ctx.audit_dir() / "agent_switches.json").write_text("{", encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    pipeline._inst_finder_decision(ctx, root)
            finally:
                path.write_text(unratified, encoding="utf-8")

        def recomputed(run_ctx, root_):
            return pipeline._inst_finder_switch(root_)
        self.prove("d", "decision_recomputed_at_phase_time", observe,
                   lambda: patch.object(pipeline, "_inst_finder_decision", recomputed))


def check():
    del PROOFS[:]
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(InstFinderSwitchChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(t) + ": " + tb.strip().splitlines()[-1] for t, tb in result.failures + result.errors]
        return "FAIL", "%d failures, %d errors: %s" % (len(result.failures), len(result.errors), "; ".join(problems)[:900])
    return "PASS", ("SHIMMER_INST_FINDER: absent dispatches all three corpus agents with no ratified default, and is "
                    "off by default only under a ratified amendment declaring default off (D-570), on running it either "
                    "way, the sealer sealing the same; off without a ratified "
                    "amendment refuses in one line (guard, main before any model call, phase 3-4); off with a "
                    "ratified fixture amendment skips INST_FINDER, records it switched_off with the reason, and "
                    "labels every result with its own agent, waves on and off; the decision saved at start-up "
                    "wins over a constitution or variable changed by phase time; neutralise/fail/restore/pass: "
                    + ", ".join(PROOFS) + "; real constitution ratifying amendments: %d" % len(_real_ratifying_ids()))


if __name__ == "__main__":
    status, detail = check()
    print(status, detail)
    raise SystemExit(0 if status == "PASS" else 1)
