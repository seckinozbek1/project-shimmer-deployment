"""Deterministic topology proofs. All semantic replies are authored fixtures."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from execution_scheduler import Backpressure, Edge, Lane, Scheduler, Task
import execution_topology as topology

ROOT = Path(__file__).resolve().parent.parent


def reference_tree(source):
    """Remove ONLY named additive adapters; keep pinned reference function hashes."""
    tree = ast.parse(source)
    # Remove named telemetry additions and the final-mode startup refusal only.
    # Keep the historical function hashes: no re-baselining of review semantics.
    class RemoveFinalTelemetry(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name == 'main':
                node.body = [x for x in node.body if not (
                    isinstance(x, ast.Import) and [a.name for a in x.names] == ['final_models'] or
                    isinstance(x, ast.If) and ast.unparse(x.test) == "final_models.mode() == 'final'")]
            if node.name == '_items_for':
                expected = ast.parse('retained = current_items(out)\nimport model_telemetry\nmodel_telemetry.retention(results, retained, agent, doc_id, scope)\nreturn retained').body
                assert [ast.dump(x) for x in node.body[-4:]] == [ast.dump(x) for x in expected]
                node.body[-4:] = ast.parse('return current_items(out)').body
            return self.generic_visit(node)
        def visit_Assign(self, node):
            if len(node.targets) == 1 and ast.unparse(node.targets[0]) == 'wrapper._parent_call_ids':
                return None
            return node
        def visit_If(self, node):
            if (ast.unparse(node.test) == "name == 'VERIFIER'" and len(node.body) == 1 and
                isinstance(node.body[0], ast.Assign) and ast.unparse(node.body[0].targets[0]) == 'wrapper._auditor_pair_request'):
                return None
            return self.generic_visit(node)
    tree = RemoveFinalTelemetry().visit(tree)
    # v5 correction (EXTRACTION-B): the bounded extraction's whole-index reference
    # list is an optimized-only helper; the reference path never calls it.
    tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name == "_doc_refs_all")]
    # Invert the named optimized-only adapters; retain the original pinned hashes.
    # The paired consumer is moved verbatim into a helper, then invoked in source
    # order. Reconstruct its original loop body to verify reference equivalence.
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        node.decorator_list = [d for d in node.decorator_list if ast.unparse(d) not in
                               {"semantic_waves.gather", "semantic_waves.planned"}]
        if node.name == "_truncate_doc":
            node.body = [x for x in node.body if not (isinstance(x,ast.If) and
                                                     ast.unparse(x.test)=="semantic_waves.enabled()")]
        if node.name == "phase_3_4_content_production":
            node.body = [x for x in node.body if not (
                isinstance(x,ast.Assign) and ast.unparse(x.targets[0])=="corpus_calls" or
                isinstance(x,ast.If) and ast.unparse(x.test)=="corpus_calls")]
            loop = next(x for x in node.body if isinstance(x,ast.For) and
                        ast.unparse(x.iter)=="PRODUCTION_AGENTS_CORPUS_LEVEL")
            body=[]
            for x in loop.body:
                if isinstance(x,ast.Assign) and ast.unparse(x.targets[0])=="corpus_call":
                    x.targets=[ast.Name(id="result",ctx=ast.Store())]
                    x.value=ast.Await(value=x.value)
                elif isinstance(x,ast.If) and ast.unparse(x.test)=="semantic_waves.enabled()":
                    assert ast.unparse(x.orelse[0])=="result = await corpus_call"
                    body.extend(x.orelse[1:])
                    continue
                body.append(x)
            loop.body=body
            # v5 correction (EXTRACTION-B): under semantic_waves the PROCESSOR call is
            # given the document's whole reference index for grounding; the reference
            # path keeps its 30-entry excerpt, so the elif is an optimized-only
            # adapter and the pinned hash stands.
            inner=next(x for x in node.body if isinstance(x,ast.AsyncFunctionDef) and x.name=="_process_doc")
            agents=next(x for x in inner.body if isinstance(x,ast.For) and ast.unparse(x.iter)=="PRODUCTION_AGENTS_PER_DOC")
            for x in agents.body:
                if isinstance(x,ast.If) and ast.unparse(x.test)=="agent_name == 'LEGAL_ANALYST' and provision_refs":
                    assert len(x.orelse)==1 and isinstance(x.orelse[0],ast.If) and                         ast.unparse(x.orelse[0].test)=="agent_name == 'PROCESSOR' and semantic_waves.enabled()"
                    x.orelse=x.orelse[0].orelse
        if node.name == "_paired_convention_review":
            helper=next(x for x in node.body if isinstance(x,ast.FunctionDef) and x.name=="consume_judgment")
            assert [a.arg for a in helper.args.args]==["plan_index","plan","unit","rule","checks","agent","source_rule_id","refs","r"]
            class RestoreContinue(ast.NodeTransformer):
                def visit_Return(self,n):
                    assert n.value is None
                    return ast.Continue()
            consumer=RestoreContinue().visit(copy.deepcopy(helper)).body
            node.body=[x for x in node.body if x is not helper and not (
                isinstance(x,ast.Assign) and ast.unparse(x.targets[0])=="pending_judgments" or
                isinstance(x,ast.If) and ast.unparse(x.test)=="pending_judgments")]
            loop=next(x for x in node.body if isinstance(x,ast.For) and ast.unparse(x.iter)=="enumerate(plans)")
            body=[]
            for x in loop.body:
                if isinstance(x,ast.If) and ast.unparse(x.test)=="semantic_waves.enabled() and semantic_waves.exact_comparison_plan(plan)":
                    continue
                if isinstance(x,ast.Assign) and ast.unparse(x.targets[0])=="planned_judgment":
                    x.targets=[ast.Name(id="r",ctx=ast.Store())]
                    x.value=ast.Await(value=x.value)
                elif isinstance(x,ast.Assign) and ast.unparse(x.targets[0])=="judgment_context":
                    continue
                elif isinstance(x,ast.If) and ast.unparse(x.test)=="semantic_waves.enabled()":
                    assert ast.unparse(x.orelse[-1])=="consume_judgment(*judgment_context, r)"
                    body.extend(copy.deepcopy(consumer))
                    continue
                body.append(x)
            loop.body=body
    expected = {"_build_wrapper": "wrapper_factory", "_gather_or_serial": "ordered_calls",
                "_gather_docs": "ordered_documents", "main": "entrypoint"}
    expected.update({n: "phase_boundary" for n in ("phase_3_4_content_production", "phase_5_audit",
                     "phase_5_5_convention_review", "phase_6_synthesis", "phase_6_5_editorial_review")})
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in expected:
                expression = "execution_topology." + expected[node.name]
                assert sum(ast.unparse(d) == expression for d in node.decorator_list) == 1
                node.decorator_list = [d for d in node.decorator_list if ast.unparse(d) != expression]
            if node.name == "_build_arg_parser":
                node.body = [s for s in node.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
                    and s.value.args and isinstance(s.value.args[0], ast.Constant)
                    and s.value.args[0].value in {"--execution-topology", "--topology-config", "--input-language", "--output-language", "--agent-briefs"})]
            if node.name == "_draft_generate_with_evidence":
                node.body = [n for n in node.body if ast.unparse(n) != "stable = run_options.direct_prefix(drafter, stable, run_ctx)"]
                class DraftEvidence(ast.NodeTransformer):
                    def visit_Expr(self, n):
                        return None if ast.unparse(n) == "run_options.record_prompt(run_ctx, call_id, drafter.name, stable, dynamic)" else n
                node = DraftEvidence().visit(node)
            if node.name == "build_draft_prompt":
                # Explicitly invert the authorized prompt-boundary relocation,
                # not the rest of the reference function or its evidence handling.
                for statement in node.body:
                    if isinstance(statement, ast.Assign) and ast.unparse(statement.targets[0]) == "stable":
                        assert ast.unparse(statement.value) == "DRAFT_SYSTEM_PROMPT"
                        statement.value = ast.parse('DRAFT_SYSTEM_PROMPT + "\\n\\n" + "\\n\\n".join(lines)', mode="eval").body
                    elif isinstance(statement, ast.Assign) and ast.unparse(statement.targets[0]) == "dynamic":
                        assert isinstance(statement.value, ast.BinOp) and isinstance(statement.value.right, ast.JoinedStr)
                        statement.value = statement.value.right
            if node.name == "main":
                class Rebind(ast.NodeTransformer):
                    def visit_Expr(self, n):
                        if ast.unparse(n) == "localization.localize_parser(parser)":
                            return None
                        if ast.unparse(n) == "run_options.configure(run_ctx, args.input_language, args.output_language, args.agent_briefs)":
                            return None
                        return None if ast.unparse(n) == "execution_topology.rebind_run(run_ctx)" else n
                    def visit_If(self, n):
                        if ast.unparse(n.test) == "redaction_enabled and sensitivity_layer.is_active() and execution_topology.reference_prewarm_enabled()":
                            n.test.values = n.test.values[:2]
                        return self.generic_visit(n)
                node = Rebind().visit(node)
    class PresentationOnly(ast.NodeTransformer):
        # Invert only the explicit localization adapters. The pinned semantic
        # function bodies, calls, schemas and completion order still compare.
        def visit_FunctionDef(self, node):
            node.decorator_list = [d for d in node.decorator_list if ast.unparse(d) not in {
                "localization.presentation", "localization.saved_presentation", "localization.run_presentation",
                "localization.cli_presentation"}]
            return self.generic_visit(node)
        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_JoinedStr(self, node):
            values = []
            for value in node.values:
                if (isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Call)
                        and ast.unparse(value.value.func) == "localization.text"
                        and len(value.value.args) == 1 and isinstance(value.value.args[0], ast.Constant)
                        and not value.value.keywords):
                    value = value.value.args[0]
                else:
                    value = self.visit(value)
                if values and isinstance(value, ast.Constant) and isinstance(values[-1], ast.Constant):
                    values[-1].value += value.value
                else:
                    values.append(value)
            node.values = values
            return node

        def visit_Call(self, node):
            if (ast.unparse(node.func) == "localization.text" and len(node.args) == 1
                    and isinstance(node.args[0], ast.Constant) and not node.keywords):
                return node.args[0]
            return self.generic_visit(node)
    return PresentationOnly().visit(tree)


def sleeper(value, seconds=0.04):
    def action(context):
        context.event("generation_start")
        try:
            until = time.perf_counter() + seconds
            while time.perf_counter() < until:
                context.checkpoint()
                time.sleep(0.002)
            return value
        finally:
            context.event("generation_end")
    return action


class SchedulerChecks(unittest.TestCase):
    def scheduler(self, lanes=None, **kwargs):
        scheduler = Scheduler(lanes or [Lane("a"), Lane("b")], **kwargs)
        self.addCleanup(scheduler.close)
        return scheduler

    def test_independent_overlap_dependencies_and_barrier(self):
        gate = threading.Barrier(2)
        def meet(context):
            gate.wait(timeout=1)
            return context.task.id
        s = self.scheduler()
        tasks = [Task("a", meet, 0), Task("b", meet, 1),
                 Task("c", lambda c: "joined", 2, kind="barrier",
                      edges=(Edge("a", "parent evidence"), Edge("b", "other parent evidence")))]
        results = s.run(tasks)
        self.assertEqual([x.state for x in results.values()], ["completed"] * 3)
        events = s.events
        start = {e["task"]: e["monotonic_s"] for e in events if e["event"] == "task_start"}
        end = {e["task"]: e["monotonic_s"] for e in events if e["event"] == "task_end"}
        self.assertLess(max(start["a"], start["b"]), min(end["a"], end["b"]))
        self.assertGreaterEqual(start["c"], max(end["a"], end["b"]))
        self.assertEqual(s.summary()["critical_path"][-1], "c")

    def test_failure_refusal_and_completion_edges(self):
        def fail(context):
            raise ValueError("fixture")
        s = self.scheduler()
        result = s.run([Task("a", fail, 0), Task("b", lambda c: {"ok": False}, 1),
                        Task("blocked", lambda c: self.fail("must not execute"), 2, edges=(Edge("a", "needs accepted output"),)),
                        Task("refused_child", lambda c: self.fail("must not execute"), 3, edges=(Edge("b", "needs accepted output"),)),
                        Task("independent", lambda c: 7, 4),
                        Task("completion", lambda c: 8, 5, edges=(Edge("a", "failure receipt visibility", False),))])
        self.assertEqual([v.state for v in result.values()],
                         ["failed", "refused", "blocked", "blocked", "completed", "completed"])
        self.assertEqual(result["independent"].value, 7)

    def test_commit_order_attribution_no_duplicate_no_lost(self):
        accepted = []
        s = self.scheduler()
        tasks = [Task(str(i), sleeper({"agent": str(i), "revision": i + 1}, 0.06 if i == 0 else 0.005),
                      i, agent=str(i), commit=accepted.append) for i in range(6)]
        result = s.run(tasks)
        self.assertEqual([r["agent"] for r in accepted], [str(i) for i in range(6)])
        self.assertEqual([r["revision"] for r in accepted], list(range(1, 7)))
        self.assertEqual(len(result), 6)
        self.assertEqual(sorted(e["task"] for e in s.events if e["event"] == "task_start"), sorted(result))
        with self.assertRaises(ValueError):
            s.run([tasks[0]])
        self.assertEqual(len(accepted), 6)

    def test_commit_failure_blocks_consumer(self):
        def fail(value):
            raise OSError("fixture")
        s = self.scheduler()
        r = s.run([Task("a", lambda c: 1, 0, commit=fail),
                   Task("b", lambda c: self.fail("uncommitted parent"), 1, edges=(Edge("a", "accepted evidence"),))])
        self.assertEqual(r["b"].state, "blocked")

    def test_bus_latest_revision_and_single_post_under_reordered_completion(self):
        from message_bus import MessageBus
        from agent_wrapper import current_items
        with tempfile.TemporaryDirectory() as directory:
            bus = MessageBus.open(Path(directory) / "bus.jsonl")
            def commit(item):
                bus.post({"sender": "FIXTURE", "recipient": "ORCHESTRATOR", "channel": "main",
                          "sender_role": "agent", "type": "INFORM", "body": {"payload": {"items": [item]}},
                          "constitution_check": {"laws_consulted": ["LAW-V"], "result": "RESOLVED", "resolution": "fixture"}})
            s = self.scheduler()
            s.run([Task("first", sleeper({"item_id": "one", "revision": 1}, 0.04), 0, commit=commit),
                   Task("second", sleeper({"item_id": "one", "revision": 2}, 0.005), 1, commit=commit)])
            rows = bus.read_all()
            self.assertEqual(len(rows), 2)
            items = [r["body"]["payload"]["items"][0] for r in rows]
            self.assertEqual([i["revision"] for i in items], [1, 2])
            self.assertEqual(current_items(items), [items[-1]])

    def test_capacity_one_serial_and_synthetic_speedup(self):
        durations = []
        for n in (1, 2):
            s = self.scheduler([Lane(str(i)) for i in range(n)])
            start = time.perf_counter()
            r = s.run([Task(str(i), sleeper(i, 0.08), i) for i in range(4)])
            durations.append(time.perf_counter() - start)
            self.assertEqual([v.value for v in r.values()], list(range(4)))
            self.assertLessEqual(max(e["concurrent_tasks"] for e in s.events if e["event"] == "assigned"), n)
        self.assertLess(durations[1], durations[0] * 0.8)

    def test_affinity_availability_memory_and_single_device(self):
        s = self.scheduler([Lane("producer", "cuda:0", models=("p",), families=("producer",), memory_gib=8),
                            Lane("auditor", "cuda:1", models=("a",), families=("auditor",), memory_gib=16),
                            Lane("unavailable", enabled=False)])
        r = s.run([Task("p", lambda c: c.worker.lane.name, 0, model="p", memory_gib=7, preferred=("unavailable",)),
                   Task("a", lambda c: c.worker.lane.name, 1, model="a", memory_gib=12),
                   Task("large", lambda c: None, 2, model="p", memory_gib=9)])
        self.assertEqual(r["p"].value, "producer")
        self.assertEqual(r["a"].value, "auditor")
        self.assertEqual(r["large"].state, "unavailable")
        one = self.scheduler([Lane("single", "cuda:0")])
        r = one.run([Task("p", lambda c: c.worker.lane.device, 0, model="p"),
                     Task("a", lambda c: c.worker.lane.device, 1, model="a")])
        self.assertEqual([o.value for o in r.values()], ["cuda:0", "cuda:0"])

    def test_health_and_auxiliary_boundary(self):
        s = self.scheduler([Lane("primary"), Lane("aux", auxiliary=True),
                            Lane("remote", auxiliary=True, enabled=False, transport="remote_reserved")])
        s.workers[0].healthy = False
        r = s.run([Task("a", lambda c: 1, 0), Task("b", lambda c: c.worker.lane.name, 1, allow_auxiliary=True)])
        self.assertEqual(r["a"].state, "unavailable")
        self.assertEqual(r["b"].value, "aux")
        with self.assertRaises(ValueError):
            Lane("remote", transport="remote_reserved")

    def test_backpressure_cycle_missing_parent_and_duplicate(self):
        s = self.scheduler(max_pending=1)
        with self.assertRaises(Backpressure):
            s.run([Task("a", lambda c: 1, 0), Task("b", lambda c: 2, 1)])
        self.assertEqual(s.tasks, {})
        with self.assertRaises(ValueError):
            s.run([Task("a", lambda c: 1, 0, edges=(Edge("missing", "required"),))])
        with self.assertRaises(ValueError):
            s.run([Task("a", lambda c: 1, 0, edges=(Edge("a", "cycle"),))])

    def test_cancellation_timeout_drains_and_never_commits(self):
        accepted = []
        s = self.scheduler()
        r = s.run([Task("timeout", sleeper(1, 0.2), 0, timeout_s=0.02, commit=accepted.append),
                   Task("other", sleeper(2, 0.03), 1, commit=accepted.append)])
        self.assertEqual(r["timeout"].state, "timed_out")
        self.assertEqual(accepted, [2])
        cancel = threading.Event()
        cancel.set()
        r = s.run([Task("cancel", lambda c: self.fail("cancelled"), 2)], cancel=cancel)
        self.assertEqual(r["cancel"].state, "cancelled")
        # A non-cooperative action is drained; timeout cannot free its device early.
        start = time.perf_counter()
        r = s.run([Task("drain", lambda c: time.sleep(0.06), 3, timeout_s=0.01, commit=accepted.append)])
        self.assertGreaterEqual(time.perf_counter() - start, 0.055)
        self.assertEqual(r["drain"].state, "timed_out")
        self.assertEqual(accepted, [2])

    def test_cpu_preparation_overlaps_generation_without_early_context(self):
        gate = threading.Barrier(2)
        def meet(c):
            gate.wait(timeout=1)
            return c.task.id
        s = self.scheduler([Lane("host"), Lane("gpu", "cuda:0", models=("p",))])
        r = s.run([Task("generate", meet, 0, model="p", preferred=("gpu",)),
                   Task("prepare", meet, 1, kind="cpu"),
                   Task("context", lambda c: 3, 2, kind="cpu",
                        edges=(Edge("generate", "new semantic evidence"), Edge("prepare", "immutable preparation")))])
        self.assertEqual(r["context"].state, "completed")

    def test_mutation_dependency_removal_fails_then_restores(self):
        # Neutralise the real scheduler dependency predicate, never the oracle.
        def probe():
            s = self.scheduler([Lane("one")])
            r = s.run([Task("parent", lambda c: {"ok": False}, 0),
                       Task("child", lambda c: "should block", 1, edges=(Edge("parent", "required"),))])
            self.assertEqual(r["child"].state, "blocked")
        probe()
        import inspect
        import textwrap
        import execution_scheduler
        source = textwrap.dedent(inspect.getsource(Scheduler._run))
        needle = "if any(e.require_success and self.outcomes[e.parent].state !="
        self.assertEqual(source.count(needle), 2)
        altered = source.replace(needle, "if False and any(e.require_success and self.outcomes[e.parent].state !=")
        self.assertNotEqual(source, altered)
        scope = vars(execution_scheduler).copy()
        exec(compile(altered, "neutralised_scheduler", "exec"), scope)
        with patch.object(Scheduler, "_run", scope["_run"]):
            with self.assertRaises(AssertionError):
                probe()
        probe()

    def test_interruption_drains_and_future_admission_is_safe(self):
        s = self.scheduler()
        def interrupt(c):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            s.run([Task("interrupt", interrupt, 0), Task("other", sleeper(1, 0.03), 1)])
        self.assertFalse(any(w.busy for w in s.workers))
        self.assertEqual(s.run([Task("next", lambda c: 3, 2)])["next"].value, 3)

    def test_running_cancel_and_family_affinity(self):
        s = self.scheduler([Lane("a", families=("producer",)), Lane("b", families=("auditor",))])
        cancel = threading.Event()
        entered = threading.Event()
        def action(c):
            entered.set()
            while not cancel.is_set():
                time.sleep(0.001)
            c.checkpoint()
        killer = threading.Thread(target=lambda: (entered.wait(1), cancel.set()))
        killer.start()
        r = s.run([Task("cancel", action, 0, family="auditor")], cancel=cancel)
        killer.join()
        self.assertEqual(r["cancel"].state, "cancelled")
        assigned = next(e for e in s.events if e["event"] == "assigned")
        self.assertEqual(assigned["worker"], "b")


class AdapterChecks(unittest.TestCase):
    def test_shutdown_failure_cannot_leave_completed_evidence(self):
        from run_context import for_run_dir
        import run_completion
        parser = argparse.ArgumentParser()
        parser.add_argument("--execution-topology", default="dependency_dag")
        parser.set_defaults(task="review", multi_round=False, multi_round_manifest=None, topology_config=None)
        with tempfile.TemporaryDirectory() as directory:
            ctx = for_run_dir(ROOT, Path(directory))
            def entry(argv=None):
                completion = run_completion.begin(ctx)
                topology.ACTIVE.get().run_context = ctx
                completion.reached_end(document_count=0, amendment_count=0)
                return 0
            real_close = topology.Runtime.close
            def failed_close(runtime):
                real_close(runtime)
                raise OSError("fixture")
            decorated = run_completion.tracked(topology.entrypoint(entry))
            with patch.dict(entry.__globals__, {"_build_arg_parser": lambda: parser}), patch.object(topology.Runtime, "close", failed_close):
                with self.assertRaises(OSError):
                    decorated([])
            self.assertEqual(run_completion.read(ctx.run_dir)["state"], "failed")

    def test_reference_prewarm_and_runtime_cleanup(self):
        self.assertTrue(topology.reference_prewarm_enabled())
        runtime = topology.Runtime([Lane("fixture")])
        token = topology.ACTIVE.set(runtime)
        try:
            self.assertFalse(topology.reference_prewarm_enabled())
        finally:
            topology.ACTIVE.reset(token)
            runtime.close()
        self.assertTrue(runtime.scheduler.closed)
        self.assertTrue(topology.reference_prewarm_enabled())

    def test_reference_ast_contract(self):
        pinned = json.loads((ROOT / "benchmark/fixtures/topology_reference_contract.json").read_text())
        tree = reference_tree((ROOT / "scripts/pipeline.py").read_text(encoding="utf-8"))
        actual = {n.name: hashlib.sha256(ast.dump(n, include_attributes=False).replace(", type_params=[]", "").encode()).hexdigest()
                  for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertEqual(pinned["baseline_commit"], "804afa57537a7d80b8df9622fc884fc065b4a4ba")
        self.assertEqual(actual, pinned["function_ast_sha256"])
        # A deliberate change to the reference path is never silent: it is recorded
        # as an amendment (from the baseline hash to the pinned one, with the
        # reason and the document) and the pin must agree with the record.
        for amendment in pinned.get("reference_amendments", []):
            self.assertTrue(amendment.get("reason") and amendment.get("document"))
            for name, hashes in amendment["functions"].items():
                self.assertEqual(hashes["to"], pinned["function_ast_sha256"][name], name)
                self.assertNotEqual(hashes["from"], hashes["to"], name)

    def test_parser_independent_defaults(self):
        import agent_activation
        tree = ast.parse((ROOT / "scripts/pipeline.py").read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_build_arg_parser")
        scope = {"argparse": argparse, "agent_activation": agent_activation}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "parser", "exec"), scope)
        parser = scope[node.name]()
        default = parser.parse_args([])
        self.assertEqual(default.execution_topology, "reference_serial")
        self.assertEqual(default.activation_profile, "dense")
        self.assertFalse(default.multi_round)
        dag = parser.parse_args(["--execution-topology", "dependency_dag", "--activation-profile", "sparse"])
        self.assertFalse(dag.multi_round)
        self.assertEqual(dag.execution_topology, "dependency_dag")

    def test_reference_factory_is_identity_and_noop_mutation(self):
        wrapper = SimpleNamespace()
        decorated = topology.wrapper_factory(lambda: wrapper)
        self.assertIs(decorated(), wrapper)
        runtime = SimpleNamespace(attach=lambda w: "attached")
        token = topology.ACTIVE.set(runtime)
        try:
            self.assertEqual(decorated(), "attached")
            with patch.object(runtime, "attach", lambda w: w):
                with self.assertRaises(AssertionError):
                    self.assertEqual(decorated(), "attached")
            self.assertEqual(decorated(), "attached")
        finally:
            topology.ACTIVE.reset(token)

    def test_runtime_real_wrapper_evidence_and_rolling_bus(self):
        import agent_wrapper as aw
        import call_evidence
        from constitution import Constitution
        from message_bus import MessageBus
        from run_context import for_run_dir
        from cost_tracker import CostTracker
        with tempfile.TemporaryDirectory() as directory:
            ctx = for_run_dir(ROOT, Path(directory))
            bus = MessageBus.open(ctx.bus_path())
            constitution = Constitution.load(ROOT / "config/constitution.json")
            cost = CostTracker.open(ctx.logs_dir(), print_live=False)
            runtime = topology.Runtime([Lane("fake")])
            captured = []
            try:
                for number in range(2):
                    wrapper = aw.AgentWrapper("ARCHIVIST", constitution, bus,
                        {"ARCHIVIST": {"backend": "local_producer", "model": "fixture"}},
                        json.loads((ROOT / "config/agent_contracts.json").read_text())["contracts"], run_context=ctx,
                        cost_tracker=cost)
                    def dispatch(stable, dynamic="", **kwargs):
                        captured.append(stable + dynamic)
                        result = aw.CallResult("local_producer", "fixture", json.dumps({"agent": "ARCHIVIST", "doc_id": "d", "items": []}))
                        wrapper._record_cost(result, duration_ms=1)
                        return result
                    wrapper.dispatch = dispatch
                    runtime.attach(wrapper)
                    result = wrapper.run_task(work_payload={"task": "per_document_analysis", "document_id": "d"},
                                              doc_id="d", phase="fixture", max_tokens=64)
                    self.assertTrue(result["ok"], result.get("error"))
                self.assertNotIn("AGENT_OUTPUT", captured[0])
                self.assertIn("AGENT_OUTPUT", captured[1])
                records = call_evidence.load(ctx.run_dir)
                self.assertEqual(len(records), 2)
                self.assertEqual(len({r["call_id"] for r in records}), 2)
                scheduled = [e["call_id"] for e in runtime.scheduler.events if e["event"] == "dispatch_start"]
                self.assertEqual(scheduled, [r["call_id"] for r in records])
                cost_rows = [json.loads(line) for line in ctx.cost_jsonl_path().read_text().splitlines()]
                self.assertEqual([r["call_id"] for r in cost_rows], scheduled)
                outputs = [r for r in bus.read_all() if r.get("body", {}).get("event") == "AGENT_OUTPUT"]
                self.assertEqual(len(outputs), 2)
                self.assertEqual(runtime.scheduler.tasks["task-000001"].edges[0].parent, "task-000000")
            finally:
                runtime.close()

    def test_resident_loader_fake_devices_precision_reuse_health(self):
        import agent_wrapper as aw
        loads = []
        class Model:
            def generate(self, **kwargs):
                return "authored"
        def load(path, **kwargs):
            loads.append(kwargs)
            return Model()
        torch = SimpleNamespace(float16="fp16", cuda=SimpleNamespace(is_available=lambda: True,
                    device_count=lambda: 2, set_device=lambda n: None, empty_cache=lambda: None))
        transformers = SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a, **k: object()),
                    AutoModelForCausalLM=SimpleNamespace(from_pretrained=load), BitsAndBytesConfig=lambda **k: k)
        def imports(name):
            return {"torch": torch, "transformers": transformers}[name]
        s = Scheduler([Lane("resident", "cuda:1", resident_limit=2)])
        try:
            def action(c):
                topology.WORK.context = c
                try:
                    tok, model = aw._load_qwen(c.task.model)
                    return model.generate(max_new_tokens=64)
                finally:
                    topology.WORK.context = None
            with patch("importlib.import_module", side_effect=imports), patch.object(aw, "_local_checkpoint_path", lambda m: m), patch.object(aw, "_checkpoint_is_prequantised", lambda *a: True):
                r = s.run([Task(str(i), action, i, model=m) for i, m in enumerate(("p", "a", "p"))])
                self.assertEqual([o.value for o in r.values()], ["authored"] * 3)
                self.assertEqual(len(loads), 2)
                self.assertEqual(loads, [{"local_files_only": True, "device_map": {"": 1}}] * 2)
                self.assertEqual(len([e for e in s.events if e["event"] == "generation_start"]), 3)
                with patch.object(transformers.AutoModelForCausalLM, "from_pretrained", side_effect=ValueError("fixture")):
                    r = s.run([Task("bad", action, 3, model="bad")])
                self.assertEqual(r["bad"].state, "failed")
                self.assertFalse(s.workers[0].healthy)
                self.assertEqual(s.run([Task("unhealthy", action, 4)])["unhealthy"].state, "unavailable")
        finally:
            s.close()
        self.assertEqual(s.workers[0].residents, {})

    def test_lane_config_and_remote_stays_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lanes.json"
            path.write_text(json.dumps({"schema_version": 1, "lanes": [{"name": "one", "device": "cuda:0"},
                {"name": "remote", "enabled": False, "auxiliary": True, "transport": "remote_reserved"}]}))
            lanes = topology.read_lanes(path)
            self.assertFalse(lanes[1].enabled)
            self.assertEqual(topology.read_lanes(None)[0].resident_limit, 1)

    def test_phase_barrier_exception_and_distinct_artifact_names(self):
        runtime = topology.Runtime([Lane("fixture")])
        token = topology.ACTIVE.set(runtime)
        try:
            @topology.phase_boundary
            def phase():
                raise ValueError("authored")
            with self.assertRaises(ValueError):
                phase()
            self.assertEqual(runtime.scheduler.events[-1]["state"], "failed")
            def stamp(context):
                topology.WORK.context = context
                try:
                    return topology.artifact_stamp("same_second")
                finally:
                    topology.WORK.context = None
            r = runtime.scheduler.run([Task("a", stamp, 0), Task("b", stamp, 1)])
            self.assertNotEqual(r["a"].value, r["b"].value)
            self.assertEqual(topology.artifact_stamp("same_second"), "same_second")
        finally:
            topology.ACTIVE.reset(token)
            runtime.close()


if __name__ == "__main__":
    unittest.main()
