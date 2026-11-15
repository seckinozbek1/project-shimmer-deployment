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
        self.assertEqual(counts.count(counts[0]), 1, "a greedy partition was retried with the same input")
        # D-575, D-577: the same input is never asked again; the changed-input retry asks each
        # owned span of the failed two-span request alone, so the partition is answered.
        self.assertEqual(len(counts[0]), 2)
        self.assertEqual(counts[-2:], [[counts[0][0]], [counts[0][1]]], "the changed-input retry asks one span each")
        self.assertTrue(result["ok"], "the partition is answered by its changed-input retry")
        self.assertEqual([r["kind"] for r in self._observations() if r.get("event") == "changed_input_retry"],
                         ["split_to_single_spans"])
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


    def _refused_last(self):
        """A source whose last bounded request owns one span; that request's first reply is the
        refusal object ({"items": [], "status": "refused"}), every other reply answers. Returns
        (result, the alias lists of every dispatch, the source's span count)."""
        import bounded_extraction as extraction
        import compact_contracts
        size = compact_contracts.request_size()
        text = next(SOURCE * n for n in range(30, 60) if len(extraction.ledger(SOURCE * n, "fixture")) % size == 1)
        spans = extraction.ledger(text, "fixture")
        tree = ast.parse((ROOT / "scripts/pipeline.py").read_text(encoding="utf-8"))
        fn = next(x for x in tree.body if isinstance(x, ast.AsyncFunctionDef) and x.name == "_run_one")
        namespace = dict(semantic_waves=waves, asyncio=asyncio, time=time,
                         _is_local_profile=lambda: False, _emit_progress=lambda **k: None)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "live_run_one", "exec"), namespace)
        runtime = self.runtime(1)
        counts = []
        last = extraction.wire_id(spans[-1])

        def dispatch(instance, stable, dynamic="", **kwargs):
            ids = [s["alias"] for s in json.loads(dynamic)["source_spans"]]
            counts.append(ids)
            if ids == [last] and counts.count(ids) == 1:
                body = dict(items=[], status="refused")
            else:
                body = dict(items=[dict(span=x, claims=[], questions=[], uncertainty=[], status="empty", refs=[]) for x in ids])
            r = CallResult(instance.backend, instance.model, json.dumps(body), usage=dict(
                truncated=False, output_tokens=40, requested_max_output_tokens=80, decoding_kwargs=dict(GREEDY)))
            instance._record_cost(r)
            return r
        async def one(wrapper):
            return await namespace["_run_one"](wrapper, dict(document_id="fixture", document_text=text), "fixture")
        state = topology.ACTIVE.set(runtime)
        try:
            with patch.object(AgentWrapper, "dispatch", dispatch):
                result = asyncio.run(one(runtime.attach(self.wrapper())))
        finally:
            topology.ACTIVE.reset(state)
        return result, counts, spans

    def test_c_b_a_refused_single_span_is_asked_once_with_the_span_before_it(self):
        """D-577: a refused one-span request (the document's last) is asked once more as a two-span
        request with the span before it, never three; only the refused span's items are kept from
        it, so every span is owned once and the document's extraction is complete."""
        import bounded_extraction as extraction
        result, counts, spans = self._refused_last()
        before, last = extraction.wire_id(spans[-2]), extraction.wire_id(spans[-1])
        self.assertEqual(counts[-1], [before, last], "the retry asks the refused span with the span before it")
        self.assertTrue(all(len(c) <= 2 for c in counts), "no request owns three spans")
        self.assertTrue(result["ok"], "the document is complete after the retry")
        owned = [i["source_span_id"] for i in result["parsed"]["items"]]
        self.assertEqual(len(owned), len(set(owned)), "the span before is not owned twice")
        self.assertEqual(sorted(owned), sorted(s.id for s in spans))
        kinds = [r["kind"] for r in self._observations() if r.get("event") == "changed_input_retry"]
        self.assertEqual(kinds, ["with_previous_span"])
        # a valid partition is never asked again: each other request appears once
        self.assertTrue(all(counts.count(c) == 1 for c in counts[:-1]))
        # the re-ask posts the refused span's items alone: every item id is on the bus once per revision
        posted = [(i.get("item_id"), i.get("revision")) for m in self.bus.read_all()
                  for i in ((((m.get("body") or {}).get("payload")) or {}).get("items") or []) if str(i.get("item_id", "")).startswith("PROCESSOR:")]
        self.assertTrue(posted, "the partitions posted their items")
        self.assertEqual(len(posted), len(set(posted)), "an item id is on the bus twice at one revision")


    def test_c_c_a_capped_verifier_is_asked_on_two_halves_of_its_pairs(self):
        """#246: a VERIFIER call that ran to its cap is asked again on the two halves of its own
        input (the producer delivery's items, their receipts and their draft view), each item seen in
        exactly one half; the merged items pass the unchanged validator, and a call that did not reach
        its cap is never asked again."""
        tree = ast.parse((ROOT / "scripts/pipeline.py").read_text(encoding="utf-8"))
        fn = next(x for x in tree.body if isinstance(x, ast.AsyncFunctionDef) and x.name == "_run_one")
        namespace = dict(semantic_waves=waves, asyncio=asyncio, time=time,
                         _is_local_profile=lambda: False, _emit_progress=lambda **k: None)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "live_run_one", "exec"), namespace)
        ids = ["PROCESSOR:fixture:s%d" % n for n in range(1, 5)]
        draft = {"agent": "PROCESSOR", "doc_id": "fixture", "items": [{"item_id": i, "draft_text": "text " + i} for i in ids]}
        producer = {"ok": True, "parsed": draft, "source_ownership": [{"producer_item_id": i} for i in ids]}
        seen = []

        def dispatch(instance, stable, dynamic="", **kwargs):
            asked = [i for i in ids if i in dynamic]
            seen.append(asked)
            items = [dict(ref="REF-0001", kind="comparison", confidence="CONFIDENT", paragraph=i, finding="MATCH",
                          severity="low", reasoning="fixture") for i in asked]
            capped = len(asked) == len(ids)
            text = json.dumps(dict(agent="VERIFIER", doc_id="fixture", items=items))
            r = CallResult(instance.backend, instance.model, text[: len(text) // 2] if capped else text, usage=dict(
                truncated=capped, output_tokens=80 if capped else 40, requested_max_output_tokens=80, decoding_kwargs=dict(GREEDY)))
            instance._record_cost(r)
            return r
        runtime = self.runtime(1)

        state = topology.ACTIVE.set(runtime)
        try:
            with patch.object(AgentWrapper, "dispatch", dispatch):
                w = runtime.attach(self.wrapper("VERIFIER"))
                w._auditor_pair_request = dict(document=dict(id="fixture"), producer=producer, references=[])
                # phase 5 gathers its audit calls (_gather_or_serial), which is the path that plans them
                plan = namespace["_run_one"](w, dict(document_id="fixture", processor_draft=draft), "fixture")
                result = asyncio.run(waves.execute_plans([plan]))[0]
        finally:
            topology.ACTIVE.reset(state)
        self.assertEqual(seen[0], ids, "the first call carries every item")
        self.assertEqual(seen[1:], [ids[:2], ids[2:]], "each half carries its own items once")
        self.assertTrue(result["ok"], result.get("contract_missing"))
        self.assertEqual([i["paragraph"] for i in result["parsed"]["items"]], ids)
        self.assertEqual([r["kind"] for r in self._observations() if r.get("event") == "changed_input_retry"], ["verifier_halves"])

    def test_d_a_mixed_replay_file_is_refused_where_it_is_built(self):
        """D-577: a replay file that holds envelope agents' prompts beside producer prompts is refused
        by load_prompts (which the sealer's checks and the runner both read) with the runner's own
        sentence, so it is caught on the laptop, not on a rented machine; one kind alone loads."""
        import hashlib
        import tempfile
        baselines = str(ROOT / "benchmark" / "baselines")
        if baselines not in sys.path:
            sys.path.insert(0, baselines)
        import replay_prompts

        def row(i, envelope):
            text = "prompt %d" % i
            return dict({"prompt_id": "p%04d" % i, "set": "records", "agent": "SPEECH_ACT_TAGGER" if envelope else "PROCESSOR",
                         "backend": "local_producer", "model_id": None, "prompt": text,
                         "prompt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}, **({"envelope": True} if envelope else {}))
        with tempfile.TemporaryDirectory() as tmp:
            for name, rows, refused in (("mixed", [row(1, True), row(2, False)], True), ("envelope", [row(1, True), row(2, True)], False),
                                        ("producer", [row(1, False), row(2, False)], False)):
                path = Path(tmp) / (name + ".json")
                path.write_text(json.dumps(dict(schema=replay_prompts.SCHEMA, prompt_count=len(rows), prompts=rows)), encoding="utf-8")
                if refused:
                    with self.assertRaisesRegex(ValueError, "not both"):
                        replay_prompts.load_prompts(path)
                else:
                    self.assertEqual(len(replay_prompts.load_prompts(path)), 2)
        self.assertEqual(replay_prompts.MIXED_REFUSAL, "a replay file holds envelope agents' prompts or producer prompts, not both")


def _replay_prompts():
    baselines = str(ROOT / "benchmark" / "baselines")
    if baselines not in sys.path:
        sys.path.insert(0, baselines)
    import replay_prompts
    return replay_prompts


NEUTRALIZATIONS = [
    ("test_a_verifier_reply_that_is_no_object_is_a_recorded_contract_failure", auditor_pairs,
     "verifier_contract_failure", lambda parsed: None),
    ("test_b_a_semantically_incomplete_end_is_reported_as_its_own_reason", "runner", "semantic_incomplete",
     lambda completion: False),
    ("test_c_a_deterministic_partition_failure_is_not_retried_and_says_so", waves, "skip_deterministic_retry",
     lambda runtime, wrapper, result, reason: False),
    ("test_c_b_a_refused_single_span_is_asked_once_with_the_span_before_it", waves, "retry_plan",
     lambda spans, owned, result: ("not_failed", [])),
    ("test_c_b_a_refused_single_span_is_asked_once_with_the_span_before_it", waves, "post_only_kept",
     lambda clone, keep: None),
    ("test_c_c_a_capped_verifier_is_asked_on_two_halves_of_its_pairs", waves, "verifier_halves",
     lambda wrapper, kwargs: None),
    ("test_c_c_a_capped_verifier_is_asked_on_two_halves_of_its_pairs", waves, "merged_halves",
     lambda wrapper, first, second: first),
    ("test_d_a_mixed_replay_file_is_refused_where_it_is_built", "replay_prompts", "refuse_mixed",
     lambda prompts: None),
]
TESTS = list(dict.fromkeys(entry[0] for entry in NEUTRALIZATIONS))


def _single(name):
    result = unittest.TestResult()
    L2DiagnosisChecks(name).run(result)
    return result.wasSuccessful() and not result.skipped


def prove_neutralizations():
    """{passed, proofs}: every NEUTRALIZATIONS entry passes, fails with its mutant in place
    (which was called), and passes again restored."""
    proofs = []
    for name, owner, attribute, mutant in NEUTRALIZATIONS:
        owner = _runner() if owner == "runner" else (_replay_prompts() if owner == "replay_prompts" else owner)
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
            "on the observation and the reply outcome, then asked once with changed input (a two-span request one span each, a refused one-span request with the span before it, D-577), while a sampled one is retried once as before"
            % (result.testsRun, len(proofs["proofs"])))


if __name__ == "__main__":
    if sys.argv[1:] == ["--prove"]:
        receipt = prove_neutralizations()
        print(json.dumps(receipt, indent=2))
        sys.exit(0 if receipt["passed"] else 1)
    print(check())
