"""No-generation contract, routing and adversarial consumer proofs.

Every semantic judgment is pre-authored in the labeled fixture. Nothing here
starts pipeline.main, a provider, a generation model or a GPU workload.
"""
from copy import deepcopy
from contextlib import nullcontext
import ast
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

import multi_round as mr
import multi_round_phase as phase
from reference_builder import ReferenceIndex
from run_context import for_run_dir

ROOT = Path(__file__).resolve().parent.parent


def fixture():
    return json.loads((ROOT / "benchmark/fixtures/multi_round_fixture.json").read_text(encoding="utf-8"))


def saved(ctx):
    f = fixture()
    record = mr.begin(ctx, f["manifest"])
    refs = ReferenceIndex.open(ctx.project_root, index_path=ctx.reference_index_path())
    record["evidence"] = mr.bind_sources(f["manifest"], f["documents"], refs)
    record["records"] = phase.accept_review(f["manifest"], record["evidence"],
        f["producer_envelope"]["items"], f["reviewer_envelope"]["items"],
        producer={"agent": "PROCESSOR", "backend": "fixture_producer", "model": "authored_producer", "call_id": "fixture_p"},
        verifier={"agent": "VERIFIER", "backend": "fixture_auditor", "model": "authored_auditor", "call_id": "fixture_v"})
    record["activation"] = mr.activation(True, eligible=True, reached=True)
    mr.write_record(ctx, record)
    return record


class MultiRoundChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="shimmer_multi_round_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ctx = for_run_dir(self.root, self.root / "output/runs" / ("a" * 32))
        self.record = saved(self.ctx)

    def test_order_gaps_late_entry_and_disappearance(self):
        v = mr.project(self.record)
        self.assertEqual([r["sequence"] for r in v["rounds"]], [1, 2, 4])
        self.assertEqual(v["missing_sequences"], [3])
        self.assertEqual(len(v["actor_history"]["actor_b"]), 1)
        self.assertEqual(len(v["issue_history"]["issue_b"]), 1)
        self.assertEqual({p["actor_id"] for p in v["current_positions"]}, {"actor_a"})
        self.assertEqual({p["issue_id"] for p in v["current_positions"]}, {"issue_a"})
        m = deepcopy(self.record["manifest"])
        m["rounds"].reverse()
        self.assertEqual(mr.project(dict(self.record, manifest=m)), v)

    def test_typed_semantics_and_non_adjacent_comparison(self):
        v = mr.project(self.record)
        self.assertEqual({m["movement"] for m in v["movements"]}, mr.MOVEMENTS - {"unknown"})
        self.assertTrue(all(m["confidence"] == "UNCERTAIN" for m in v["movements"]))
        self.assertTrue(all(c["delta"] == 3 for c in v["structural_comparisons"]))
        self.assertTrue(v["trajectory"] and v["decision_support"] and v["unresolved"])
        self.assertFalse(any(r["category"] == "recommendation" for r in v["records"]))
        r = deepcopy(self.record)
        p = next(p for p in r["records"] if p["record_id"] == "p_s4_actor_a")
        p["position"] = "typed_a"
        self.assertTrue(all(c["typed_position_equal"] for c in mr.project(r)["structural_comparisons"]))
        # The typed judgments survive unchanged; equality cannot infer stability.
        self.assertEqual([m["movement"] for m in mr.project(r)["movements"]],
                         [m["movement"] for m in v["movements"]])
        r["records"][0]["value"] = -1e308
        r["records"][2]["value"] = 1e308
        self.assertTrue(all(c["delta_state"] == "not_comparable" for c in mr.project(r)["structural_comparisons"]))

    def test_recommendations_need_explicit_separate_request(self):
        r = deepcopy(self.record)
        row = next(x for x in r["records"] if x["kind"] == "decision_support")
        row["category"] = "recommendation"
        with self.assertRaises(mr.InvalidState):
            mr.project(r)
        r["manifest"]["allow_recommendations"] = True
        self.assertEqual(mr.project(r)["decision_support"][0]["category"], "recommendation")

    def test_real_server_form_and_worker_routing_without_http(self):
        from types import SimpleNamespace
        tree = ast.parse((ROOT / "scripts/server.py").read_text(encoding="utf-8"))
        submit = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "submit")
        start = next(i for i, n in enumerate(submit.body) if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "case_manifest")
        prefix = ast.Module(body=submit.body[start:start + 2], type_ignores=[])

        class HTTPRefusal(Exception):
            pass

        def form(requested, manifest, task="review", sensitive="false"):
            ns = {"json": json, "multi_round": requested, "multi_round_manifest": manifest,
                  "task": task, "sensitive": sensitive, "HTTPException": HTTPRefusal}
            exec(compile(prefix, "actual_server_form", "exec"), ns)
            return ns["case_manifest"]

        self.assertIsNone(form(None, None))
        self.assertIsNone(form("false", None))
        m = deepcopy(fixture()["manifest"])
        m["fixture"] = False
        self.assertEqual(form("true", json.dumps(m)), m)
        for flag, manifest, task, sensitive in [(None, json.dumps(m), "review", "false"),
            ("true", "{", "review", "false"), ("true", json.dumps(m), "draft", "false"),
            ("true", json.dumps(m), "review", "true"), ("true", json.dumps(fixture()["manifest"]), "review", "false")]:
            with self.assertRaises(HTTPRefusal):
                form(flag, manifest, task, sensitive)
        worker = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_run_job")
        branch = next(n for n in ast.walk(worker) if isinstance(n, ast.If) and ast.unparse(n.test) == "(job or {}).get('multi_round') is True")
        for job, expected in [({}, []), ({"multi_round": False}, []), ({"multi_round": True},
            ["--multi-round", "--multi-round-manifest", str(self.ctx.audit_dir() / "multi_round_request.json")])]:
            ns = {"job": job, "argv": [], "out_dir": self.ctx.run_dir}
            exec(compile(ast.Module(body=[branch], type_ignores=[]), "actual_worker_branch", "exec"), ns)
            self.assertEqual(ns["argv"], expected)

    def test_malformed_manifest_refuses(self):
        changes = [lambda m: m["rounds"].append(m["rounds"][0]),
                   lambda m: m["rounds"][1].update(sequence=1),
                   lambda m: m["sources"][0].update(round_id="missing"),
                   lambda m: m["actors"].append(m["actors"][0]),
                   lambda m: m["issues"].append(m["issues"][0]),
                   lambda m: m["rounds"][1].update(document_ids=["doc1"])]
        for change in changes:
            m = deepcopy(self.record["manifest"])
            change(m)
            with self.subTest(change=changes.index(change)), self.assertRaises(mr.InvalidState):
                mr.validate_manifest(m)

    def test_wrong_round_actor_issue_evidence_and_missing_support(self):
        changes = [lambda rows: rows[0].update(round_id="r2"),
                   lambda rows: rows[0].update(actor_id="actor_b"),
                   lambda rows: rows[0].update(issue_id="issue_b"),
                   lambda rows: rows[0].update(source_ids=[]),
                   lambda rows: rows[4].update(source_ids=["s4_actor_a"]),
                   lambda rows: rows[4].update(previous_position_id="p_s2_actor_b"),
                   lambda rows: rows[4].update(previous_round_id="r4"),
                   lambda rows: rows[0].update(case_id="other_case")]
        for change in changes:
            r = deepcopy(self.record)
            change(r["records"])
            with self.subTest(change=changes.index(change)), self.assertRaises(mr.InvalidState):
                mr.project(r)
        r = deepcopy(self.record)
        r["records"][4].update(round_id="r2", current_position_id="p_s2_actor_a")
        r["records"][4]["source_ids"].append("s2_actor_a")
        with self.assertRaises(mr.InvalidState):
            mr.project(r)

    def test_source_span_binding(self):
        f = fixture()
        f["documents"][0]["text"] = "Different source."
        refs = ReferenceIndex.open(self.root, index_path=self.ctx.reference_index_path())
        with self.assertRaises(mr.InvalidState):
            mr.bind_sources(f["manifest"], f["documents"], refs)

    def test_review_withholding_and_provenance(self):
        f = fixture()
        decisions = f["reviewer_envelope"]["items"][1:]
        rows = phase.accept_review(f["manifest"], self.record["evidence"],
            f["producer_envelope"]["items"], decisions,
            producer={"agent":"PROCESSOR", "backend":"fixture_p", "model":"authored_p", "call_id":"p"},
            verifier={"agent":"VERIFIER", "backend":"fixture_v", "model":"authored_v", "call_id":"v"})
        self.assertEqual(rows[0]["state"], "unresolved")
        self.assertTrue(all(r["state"] == "unresolved" for r in rows if r["kind"] == "movement"))
        self.assertTrue(all(r["producer_call_id"] == "p" and r["reviewer_call_id"] == "v" for r in rows))

    def test_activation_and_default_parser(self):
        # Execute only the actual parser definition, not pipeline imports/main.
        import agent_activation
        tree = ast.parse((ROOT / "scripts/pipeline.py").read_text(encoding="utf-8"))
        parser_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_build_arg_parser")
        scope = {"argparse": argparse, "agent_activation": agent_activation}
        exec(compile(ast.Module(body=[parser_node], type_ignores=[]), "pipeline_parser", "exec"), scope)
        for task in ["review", "draft"]:
            for profile in ["dense", "sparse"]:
                args = scope["_build_arg_parser"]().parse_args(["--task", task, "--activation-profile", profile])
                self.assertFalse(args.multi_round)
                self.assertIsNone(args.multi_round_manifest)
                self.assertIsNone(mr.normalize_request(args.multi_round, None))
        self.assertEqual(mr.activation()["state"], "not_requested")
        self.assertEqual(mr.activation(True)["state"], "phase_not_reached")
        self.assertFalse(mr.activation(True)["activated"])
        self.assertEqual(mr.activation(True, eligible=False)["state"], "refused")
        with self.assertRaises(mr.InvalidState):
            mr.normalize_request(False, fixture()["manifest"])

    def test_pre_multi_round_pipeline_contract_is_unchanged(self):
        baseline = json.loads((ROOT / "benchmark/fixtures/multi_round_baseline_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(baseline["baseline_commit"], mr.BASELINE)
        from execution_topology_checks import reference_tree
        tree = reference_tree((ROOT / "scripts/pipeline.py").read_text(encoding="utf-8"))
        digests = {}
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name == "main":
                removed = []
                body = []
                for statement in node.body:
                    if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id in {"multi_record", "multi_manifest"}:
                        self.assertIsNone(statement.value.value)
                        removed.append(statement)
                    elif isinstance(statement, ast.If) and ast.unparse(statement.test) in {
                            "args.multi_round or args.multi_round_manifest", "multi_manifest is not None", "multi_record is not None"}:
                        self.assertFalse(statement.orelse)
                        removed.append(statement)
                    else:
                        body.append(statement)
                self.assertEqual(len(removed), 5)
                node.body = body
            if node.name == "_build_arg_parser":
                node.body = [s for s in node.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
                    and s.value.args and isinstance(s.value.args[0], ast.Constant)
                    and s.value.args[0].value in {"--multi-round", "--multi-round-manifest"})]
            normalized = ast.dump(node, include_attributes=False).replace(", type_params=[]", "")
            digests[node.name] = hashlib.sha256(normalized.encode()).hexdigest()
        self.assertEqual(digests, baseline["function_ast_sha256"])

    def test_saved_api_auth_identity_and_safe_projection(self):
        import importlib.util
        if importlib.util.find_spec("fastapi") is None:
            self.skipTest("UNVERIFIED HTTP integration: FastAPI is not installed")
        from fastapi.testclient import TestClient
        from startup_submit_checks import _isolated_server
        server = _isolated_server(self.root / "server")
        ctx = for_run_dir(self.root, server.RUNS_DIR / ("b" * 32))
        saved(ctx)
        access = secrets.token_urlsafe(24)
        with patch.dict(os.environ, {"SHIMMER_TOKEN_HASH": hashlib.sha256(access.encode()).hexdigest()}):
            client = TestClient(server.app)
            url = "/runs/" + ctx.run_id + "/multi-round"
            self.assertEqual(client.get(url).status_code, 401)
            response = client.get(url, headers={"Authorization": "Bearer " + access})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["fixture"])
            self.assertEqual(response.json()["view"], mr.project(self.record))
            ctx.multi_round_path().write_text("{", encoding="utf-8")
            self.assertEqual(client.get(url, headers={"Authorization": "Bearer " + access}).json()["availability"], "invalid")
        self.assertEqual(mr.read_saved(self.ctx.run_dir, "wrong")["availability"], "invalid")

    def test_actual_route_definition_and_saved_identity(self):
        tree = ast.parse((ROOT / "scripts/server.py").read_text(encoding="utf-8"))
        route = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "run_multi_round")
        self.assertIn("Depends(verify_token)", ast.unparse(route.decorator_list[0]))
        route.decorator_list = []
        namespace = {"_validated_run_dir": lambda run_id: self.ctx.run_dir}
        exec(compile(ast.Module(body=[route], type_ignores=[]), "server_route", "exec"), namespace)
        # The real handler contains no await. Drive its coroutine directly;
        # Windows event-loop setup would otherwise open an internal socket pair.
        with self.assertRaises(StopIteration) as returned:
            namespace["run_multi_round"](self.ctx.run_id).send(None)
        self.assertEqual(returned.exception.value["view"], mr.project(self.record))
        self.assertEqual(mr.read_saved(self.ctx.run_dir, "wrong")["availability"], "invalid")
        r = deepcopy(self.record)
        r["evidence"][0]["ref_id"] = "REF-missing"
        mr.write_record(self.ctx, r)
        self.assertEqual(mr.read_saved(self.ctx.run_dir, self.ctx.run_id)["availability"], "invalid")

    def test_missing_requested_state_is_not_not_requested(self):
        self.ctx.multi_round_path().unlink()
        self.assertEqual(mr.read_saved(self.ctx.run_dir, self.ctx.run_id)["activation"]["state"], "not_requested")
        self.ctx.status_path().write_text(json.dumps({"run_id": self.ctx.run_id, "multi_round": True}), encoding="utf-8")
        view = mr.read_saved(self.ctx.run_dir, self.ctx.run_id)
        self.assertTrue(view["activation"]["requested"])
        self.assertEqual(view["availability"], "unavailable")

    def test_cross_actor_claim_needs_both_rounds_for_each_actor(self):
        r = deepcopy(self.record)
        claim = next(x for x in r["records"] if x["kind"] == "trajectory")
        claim["actor_ids"] = ["actor_a", "actor_b"]
        with self.assertRaises(mr.InvalidState):
            mr.project(r)
        for sid in ["s1_actor_a", "s4_actor_a"]:
            s = deepcopy(next(s for s in r["manifest"]["sources"] if s["source_id"] == sid))
            s.update(source_id=sid + "_b", actor_id="actor_b")
            r["manifest"]["sources"].append(s)
            e = deepcopy(s)
            e["ref_id"] = "REF-" + sid + "_b"
            r["evidence"].append(e)
            claim["source_ids"].append(e["source_id"])
        self.assertEqual(mr.project(r)["trajectory"][0]["actor_ids"], ["actor_a", "actor_b"])

    def test_real_phase_with_authored_agent_envelopes(self):
        from agent_wrapper import AgentWrapper, CallResult
        from constitution import Constitution
        from message_bus import MessageBus
        import agent_activation
        f = fixture()
        m = deepcopy(f["manifest"])
        # The production guard refuses a fixture-marked live request. Here the
        # entire transport is replaced, and no real model/provider can execute.
        m["fixture"] = False
        ctx = for_run_dir(self.root, self.root / "output/runs" / ("c" * 32))
        r = mr.begin(ctx, m)
        r["test_fixture_notice"] = f["fixture_notice"]
        refs = ReferenceIndex.open(self.root, index_path=ctx.reference_index_path())
        bus = MessageBus.open(ctx.bus_path())
        registry = json.loads((ROOT / "config/agent_registry.json").read_text(encoding="utf-8"))["agents"]
        agent_activation.initialize(ctx, registry, "dense")
        constitution = Constitution.load(ROOT / "config/constitution.json")
        calls = []

        def factory(name):
            return AgentWrapper(name, constitution, bus, registry, {}, keys={"fixture": True}, run_context=ctx)

        def authored(wrapper, *args, **kwargs):
            calls.append(wrapper.name)
            payload = deepcopy(f["producer_envelope" if wrapper.name == "PROCESSOR" else "reviewer_envelope"])
            for i, item in enumerate(payload["items"]):
                item.update(ref="fixture_" + str(i), kind=item.get("kind", "finding"), confidence=item.get("confidence", "UNCERTAIN"))
            return CallResult(ok=True, raw_text=json.dumps(payload), backend=wrapper.backend, model=wrapper.model, usage={})

        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(AgentWrapper, "dispatch", authored):
            code = phase.execute(ctx, r, f["documents"], refs, factory, sensitive=False)
        self.assertEqual(code, 0, r.get("activation"))
        self.assertEqual(calls, ["PROCESSOR", "VERIFIER"])
        self.assertEqual(r["outcome"], "reviewed")
        self.assertTrue(any(msg["body"].get("event") == "MULTI_ROUND_REVIEWED" for msg in bus.read_all()))
        for name, content in before.items():
            if not name.startswith(str(ctx.run_dir.relative_to(self.root))):
                self.assertEqual((self.root / name).read_bytes(), content)
        self.assertFalse((self.root / "durable").exists())
        self.assertFalse((self.root / "ontology").exists())
        calls.clear()
        self.assertEqual(phase.execute(ctx, r, f["documents"], refs, factory, sensitive=True), 8)
        self.assertFalse(calls)

    def test_neutralise_fail_restore_and_noop_refused(self):
        from effect_proof import prove_effect, ProofFailure
        expected = mr.project(self.record)
        observe = lambda: mr.read_saved(self.ctx.run_dir, self.ctx.run_id)
        check = lambda: ("PASS" if observe().get("view") == expected else "FAIL", "saved projection")
        args = dict(name="multi_round_saved_consumer", validate=lambda: True, observe=observe, check=check)
        prove_effect(**args, neutralise=lambda: patch.object(mr, "project", return_value={}))
        with self.assertRaises(ProofFailure) as exc:
            prove_effect(**args, neutralise=nullcontext)
        self.assertEqual(exc.exception.category, "NO_OBSERVED_EFFECT")

    def test_evidence_guard_neutralise_fail_restore(self):
        from effect_proof import prove_effect
        wrong = deepcopy(self.record)
        wrong["records"][0]["actor_id"] = "actor_b"

        def observe():
            try:
                mr.project(wrong)
                return {"unsupported_claim_accepted": True}
            except mr.InvalidState:
                return {"unsupported_claim_accepted": False}

        prove_effect(name="actor_evidence_guard", validate=lambda: True, observe=observe,
            check=lambda: ("FAIL" if observe()["unsupported_claim_accepted"] else "PASS", "evidence integrity"),
            neutralise=lambda: patch.object(mr, "require", lambda *args: None))

    def test_missing_position_can_remain_insufficient(self):
        r = deepcopy(self.record)
        r["records"][4].update(previous_position_id=None, state="insufficient_evidence", confidence="UNCERTAIN")
        self.assertTrue(any(x["record_id"] == r["records"][4]["record_id"] for x in mr.project(r)["unresolved"]))


def check():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MultiRoundChecks)
    result = unittest.TestResult()
    suite.run(result)
    return ("SKIP" if result.skipped else "PASS", f"{result.testsRun - len(result.skipped)} fixture-only cases passed; {len(result.skipped)} unavailable checks; no generation") if result.wasSuccessful() else (
        "FAIL", f"{len(result.failures)} failures, {len(result.errors)} errors")


if __name__ == "__main__":
    unittest.main()
