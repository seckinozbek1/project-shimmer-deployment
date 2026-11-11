"""Checks for the general fixes adopted from the L2 diagnosis (docs/loop/DECISIONS.md D-061 (a),
(b) and (c)), run by the verify gate (scripts/verify_session1.py check 289) through check();
`py -3.12 -X utf8 scripts/l2_diagnosis_checks.py` runs them by hand and `--prove` runs the
neutralise, fail, restore, pass proofs alone.

  (a) a VERIFIER reply that is not a JSON object (or whose items are not a list of objects) is a
      recorded contract failure in auditor_pairs.compare: the call's contract_valid is false
      and the join event names the reason; nothing raises (L2 entry 06 crashed there);
  (b) the runner's assessment (tools/ordinary_final_run.py assess) reports a pipeline that
      reached its end with exit 0 but semantically incomplete as `semantic_incomplete`, never
      as `pipeline_not_completed`;
  (c) a failed producer partition whose call decoded deterministically (greedy, one beam) is not
      retried (L2: 9 of 9 retries repeated their request and reply bytes); the skip is recorded
      on the generation observation and as the call's reply outcome,
      `retry_skipped_deterministic`; a call that sampled is still retried once, as before.

No model, no pipeline run: fixture wrappers, a fixture bus and fake dispatches, in temporary
directories only.
"""
import ast
import asyncio
import importlib.util
import json
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import auditor_pairs  # noqa: E402
import reply_records  # noqa: E402
import semantic_waves as waves  # noqa: E402
import execution_topology as topology  # noqa: E402
from agent_wrapper import AgentWrapper, CallResult  # noqa: E402
from report_recommendations_checks import RecommendationChecks, SOURCE  # noqa: E402


def _runner():
    """tools/ordinary_final_run.py, imported by path (it imports no model library)."""
    loaded = sys.modules.get("ordinary_final_run")
    if loaded is not None:
        return loaded
    spec = importlib.util.spec_from_file_location("ordinary_final_run", ROOT / "tools" / "ordinary_final_run.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ordinary_final_run"] = module
    spec.loader.exec_module(module)
    return module


GREEDY = {"do_sample": False, "num_beams": 1, "use_cache": True}
SAMPLED = {"do_sample": True, "num_beams": 1, "top_p": 0.9}


class L2DiagnosisChecks(RecommendationChecks):
    """Reuses the bounded-mechanism fixtures (a fixture run context, bus, constitution and
    contracts, live wrappers and the live _run_one) of scripts/report_recommendations_checks.py;
    only the tests below run here."""

    # ---- (a) ---------------------------------------------------------------------------------

    def _telemetry(self, event):
        path = self.ctx.logs_dir() / "model_telemetry.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
        return [r for r in rows if r.get("event") == event]

    def test_a_verifier_reply_that_is_no_object_is_a_recorded_contract_failure(self):
        record = dict(pair_id="pair-1", producer_item_id="P:1", producer_revision=1, source_span_id="s1",
                      source_ref_ids=[], classifier_status="classified", auditor_relation="MATCH")
        cases = (([{"finding": "MATCH"}], "reply_not_object"), ("MATCH", "reply_not_object"),
                 ({"items": "MATCH"}, "items_not_list"), ({"items": ["MATCH", {"finding": "MATCH"}]}, "item_not_object"))
        for parsed, reason in cases:
            wrapper = SimpleNamespace(run_context=self.ctx, _auditor_pair_state=[record], _observed_contract_valid=True)
            result = {"ok": True, "parsed": parsed, "raw_text": json.dumps(parsed), "call_id": "v-" + reason}
            auditor_pairs.compare(wrapper, result)          # never raises
            self.assertIs(wrapper._observed_contract_valid, False, reason)
            event = self._telemetry("auditor_verifier_join")[-1]
            self.assertEqual((event["verifier_call_id"], event["contract_failure"]), ("v-" + reason, reason))
        # a well-formed reply is read as before: no contract failure, its finding joined
        wrapper = SimpleNamespace(run_context=self.ctx, _auditor_pair_state=[record], _observed_contract_valid=True)
        good = {"items": [{"item_id": "V:1", "finding": "MATCH", "auditor_pair_id": "pair-1"}]}
        auditor_pairs.compare(wrapper, {"ok": True, "parsed": good, "raw_text": json.dumps(good), "call_id": "v-good"})
        self.assertIs(wrapper._observed_contract_valid, True)
        event = self._telemetry("auditor_verifier_join")[-1]
        self.assertEqual((event["contract_failure"], event["finding_count"], event["findings"][0]["agreement"]),
                         (None, 1, "agree"))
        # the runner reads the failure off the call's telemetry as a required contract failure
        rows = [dict(event="model_call", agent="VERIFIER", contract_valid=False)]
        self.assertIn("required_contract_failure", _runner().assess(None, rows)["reasons"])

    # ---- (b) ---------------------------------------------------------------------------------

    def test_b_a_semantically_incomplete_end_is_reported_as_its_own_reason(self):
        runner = _runner()

        def reason(completion):
            found = [r for r in runner.assess(completion, [])["reasons"]
                     if r in ("semantic_incomplete", "pipeline_not_completed")]
            return found[0] if found else None
        incomplete = dict(state="stopped", reached_end=True, exit_code=0, semantic_complete=False)
        self.assertEqual(reason(incomplete), "semantic_incomplete")
        self.assertEqual(reason(dict(incomplete, exit_code=2)), "pipeline_not_completed")
        self.assertEqual(reason(dict(incomplete, reached_end=False)), "pipeline_not_completed")
        self.assertEqual(reason(dict(state="stopped", reached_end=True, exit_code=0)), "pipeline_not_completed")
        self.assertEqual(reason(None), "pipeline_not_completed")
        self.assertIsNone(reason(dict(state="completed", reached_end=True, exit_code=0)))
        # the record run_completion writes for such a run is exactly that shape
        from run_completion import RunCompletion
        import generation_observation
        completion = RunCompletion(self.ctx)
        completion.reached_end(document_count=1, amendment_count=0)
        generation_observation.mark_incomplete(self.ctx)
        completion.finish(0)
        self.assertEqual(reason(completion.record), "semantic_incomplete")

    # ---- (c) ---------------------------------------------------------------------------------

    def _partitions(self, decoding_kwargs):
        """The live _run_one (read from pipeline.py) on a source of several partitions, the first
        partition's first reply truncated; every reply records `decoding_kwargs` as its call's
        decoding, as call_local records the frozen policy. Returns (result, the span ids each
        dispatch was asked for)."""
        tree = ast.parse((ROOT / "scripts/pipeline.py").read_text(encoding="utf-8"))
        fn = next(x for x in tree.body if isinstance(x, ast.AsyncFunctionDef) and x.name == "_run_one")
        namespace = dict(semantic_waves=waves, asyncio=asyncio, time=time,
                         _is_local_profile=lambda: False, _emit_progress=lambda **k: None)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "live_run_one", "exec"), namespace)
        runtime = self.runtime(1)
        counts = []

        def dispatch(instance, stable, dynamic="", **kwargs):
            payload = json.loads(dynamic)
            ids = [s["alias"] for s in payload["source_spans"]]
            counts.append(ids)
            items = [dict(span=x, claims=[], questions=[], uncertainty=[], status="empty", refs=[]) for x in ids]
            r = CallResult(instance.backend, instance.model, json.dumps(dict(items=items)), usage=dict(
                truncated=len(counts) == 1, output_tokens=40, requested_max_output_tokens=80,
                decoding_kwargs=dict(decoding_kwargs)))
            instance._record_cost(r)
            return r
        async def one(wrapper):
            return await namespace["_run_one"](wrapper, dict(document_id="fixture", document_text=SOURCE * 30), "fixture")
        state = topology.ACTIVE.set(runtime)
        try:
            with patch.object(AgentWrapper, "dispatch", dispatch):
                w = runtime.attach(self.wrapper())
                result = asyncio.run(one(w))
        finally:
            topology.ACTIVE.reset(state)
        return result, counts

    def _observations(self):
        path = self.ctx.logs_dir() / "generation_observation.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_c_a_deterministic_partition_failure_is_not_retried_and_says_so(self):
        result, counts = self._partitions(GREEDY)
        self.assertEqual(counts.count(counts[0]), 1, "a greedy partition was retried")
        self.assertFalse(result["ok"], "the failed partition stands")
        skipped = [r for r in self._observations() if r.get("event") == "partition_retry_skipped"]
        self.assertEqual([(r["outcome"], r["retry_skipped_deterministic"], r["retry_reason"]) for r in skipped],
                         [("retry_skipped_deterministic", True, "truncation")])
        outcomes = reply_records.outcomes(Path(self.ctx.run_dir) / "audit" / "model_replies")
        self.assertEqual(outcomes.get(skipped[0]["call_id"]), "retry_skipped_deterministic")
        self.assertIn("retry_skipped_deterministic", reply_records.OUTCOMES)
        # a call that sampled is retried once, as before, and its retry recorded as such
        self.setUp()
        result, counts = self._partitions(SAMPLED)
        self.assertEqual(counts.count(counts[0]), 2)
        self.assertTrue(result["ok"])
        self.assertEqual([r for r in self._observations() if r.get("event") == "partition_retry_skipped"], [])


NEUTRALIZATIONS = [
    ("test_a_verifier_reply_that_is_no_object_is_a_recorded_contract_failure", auditor_pairs,
     "verifier_contract_failure", lambda parsed: None),
    ("test_b_a_semantically_incomplete_end_is_reported_as_its_own_reason", "runner", "semantic_incomplete",
     lambda completion: False),
    ("test_c_a_deterministic_partition_failure_is_not_retried_and_says_so", waves, "skip_deterministic_retry",
     lambda runtime, wrapper, result, reason: False),
]
TESTS = [entry[0] for entry in NEUTRALIZATIONS]


def _single(name):
    result = unittest.TestResult()
    L2DiagnosisChecks(name).run(result)
    return result.wasSuccessful() and not result.skipped


def prove_neutralizations():
    """{passed, proofs}: every NEUTRALIZATIONS entry passes, fails with its mutant in place
    (which was called), and passes again restored."""
    proofs = []
    for name, owner, attribute, mutant in NEUTRALIZATIONS:
        owner = _runner() if owner == "runner" else owner
        invocations = []

        def counted(*args, _mutant=mutant, **kwargs):
            invocations.append(1)
            return _mutant(*args, **kwargs)
        before = _single(name)
        with patch.object(owner, attribute, counted):
            failed = not _single(name)
        after = _single(name)
        proofs.append({"check": name, "neutralized": owner.__name__ + "." + attribute, "baseline_pass": before,
                       "neutralized_fail": failed and bool(invocations), "restored_pass": after,
                       "mutated_branch_invocations": len(invocations)})
    return {"passed": all(p["baseline_pass"] and p["neutralized_fail"] and p["restored_pass"] for p in proofs),
            "proofs": proofs}


def check():
    suite = unittest.TestSuite(L2DiagnosisChecks(name) for name in TESTS)
    result = unittest.TestResult()
    suite.run(result)
    problems = result.failures + result.errors
    if problems:
        lines = problems[0][1].strip().splitlines()
        return ("FAIL", "%d failures/errors; first: %s" % (len(problems), lines[-1]))
    proofs = prove_neutralizations()
    if not proofs["passed"]:
        bad = [p["check"] + " (" + p["neutralized"] + ")" for p in proofs["proofs"]
               if not (p["baseline_pass"] and p["neutralized_fail"] and p["restored_pass"])]
        return ("FAIL", "a neutralise, fail, restore, pass proof did not hold: " + ", ".join(bad))
    return ("PASS", "%d cases and %d neutralise/fail/restore/pass proofs (D-061): a VERIFIER reply that is "
            "no JSON object is a recorded contract failure, never a crash; a run that reached its end with exit "
            "0 but semantically incomplete is assessed semantic_incomplete, not pipeline_not_completed; a failed "
            "partition under deterministic decoding is not retried and is recorded retry_skipped_deterministic "
            "on the observation and the reply outcome, while a sampled one is retried once as before"
            % (result.testsRun, len(proofs["proofs"])))


if __name__ == "__main__":
    if sys.argv[1:] == ["--prove"]:
        receipt = prove_neutralizations()
        print(json.dumps(receipt, indent=2))
        sys.exit(0 if receipt["passed"] else 1)
    print(check())
