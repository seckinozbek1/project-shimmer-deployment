"""Gate check 277: the operator setting SHIMMER_INST_FINDER switches INST_FINDER off
only under a ratified DELTA, and is never ignored silently.

Three cases, each in a temporary directory with copied configuration (the real
config/, durable/ and ontology/ are never written):

  (a) the variable absent: INST_FINDER is dispatched exactly as before;
  (b) `off` with the real constitution: the start-up guard refuses with one line
      naming the missing DELTA, main() returns 9 on it before any model call, and
      phase 3-4 refuses rather than dispatching;
  (c) `off` with a fixture constitution carrying a ratified amendment: INST_FINDER
      is not dispatched, the activation record gives the reason, and every
      gathered result carries its own agent's name.

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

import pipeline
import routing_view
import run_context as run_context_mod

ROOT = Path(__file__).resolve().parent.parent
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


def _produce(root, waves, phase=None):
    """Run the real phase 3-4 corpus loop with the model boundary replaced."""
    ctx = run_context_mod.create_run(root)
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


def _projected_calls(root):
    seen = {}
    with patch.object(pipeline, "ROOT", root), \
            patch.object(pipeline, "estimate_cost", lambda **kw: seen.update(kw) or kw):
        pipeline._cost_projection(1, 0)
        return seen["claude_calls"], pipeline._local_progress_baseline(1)


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
        root = _root(self.tmp.name)
        baseline_calls, baseline_progress = None, None

        def observe():
            nonlocal baseline_calls, baseline_progress
            with _setting(None):
                ctx = run_context_mod.create_run(root)
                self.assertIsNone(pipeline._inst_finder_startup_guard(ctx, root))
                saved = json.loads((ctx.audit_dir() / "agent_switches.json").read_text(encoding="utf-8"))
                self.assertEqual((saved["setting"], saved["value"], saved["switched_off"]), ("on", None, []))
                self.assertIn("- INST_FINDER: on (SHIMMER_INST_FINDER is not off)", _summary(ctx))
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
                self.assertIn("switched off by the ratified SHIMMER_INST_FINDER setting, amendment " + FIXTURE_ID,
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


def check():
    del PROOFS[:]
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(InstFinderSwitchChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(t) + ": " + tb.strip().splitlines()[-1] for t, tb in result.failures + result.errors]
        return "FAIL", "%d failures, %d errors: %s" % (len(result.failures), len(result.errors), "; ".join(problems)[:900])
    return "PASS", ("SHIMMER_INST_FINDER: absent dispatches all three corpus agents; off without a ratified "
                    "amendment refuses in one line (guard, main before any model call, phase 3-4); off with a "
                    "ratified fixture amendment skips INST_FINDER, records it switched_off with the reason, and "
                    "labels every result with its own agent, waves on and off; neutralise/fail/restore/pass: "
                    + ", ".join(PROOFS) + "; real constitution ratifying amendments: %d" % len(_real_ratifying_ids()))


if __name__ == "__main__":
    status, detail = check()
    print(status, detail)
    raise SystemExit(0 if status == "PASS" else 1)
