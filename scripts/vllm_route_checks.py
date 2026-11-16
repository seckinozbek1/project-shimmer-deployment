"""Proofs of the vLLM route through AgentWrapper.call_local (D-630 part A, A2), on the envelope checks'
fixture tokenizer and a stand-in link (no vLLM, no model, no subprocess; the link's own protocol is
proved in scripts/vllm_link_checks.py and the server in scripts/vllm_server_checks.py).

The stand-in server builds its constraint as the real one does (contract_decoding.for_prompt from the
rendered prompt and the agent, vllm_constraint.Slot), so the runner's digest comparison is proved on
the real code. Each proof that guards a property is neutralised (the property broken) and must fail.

    py -3.12 -X utf8 scripts/vllm_route_checks.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "benchmark" / "baselines"))

import agent_wrapper  # noqa: E402
import contract_decoding as cd  # noqa: E402
import decoding_policy  # noqa: E402
import envelope_decoding_checks as edc  # noqa: E402
import vllm_link  # noqa: E402
import vllm_route  # noqa: E402
import final_models  # noqa: E402
import model_telemetry  # noqa: E402

TOK = edc.EnvelopeTokenizer()
import vllm_constraint  # noqa: E402
import vllm_replay  # noqa: E402

NF4 = {"quant_method": "bitsandbytes", "bnb_4bit_quant_type": "nf4", "compute_dtype": "bfloat16"}
REPLAY = SimpleNamespace(quantisation=lambda path: (NF4, None), dtype_refusal=vllm_replay.dtype_refusal,
                         vllm_dtypes=vllm_replay.vllm_dtypes)


def cfg(**over):
    found = dict(max_position_embeddings=100000, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2,
                 hidden_size=8)
    found.update(over)
    return SimpleNamespace(**found)


CONFIG = cfg()
JOB = {"dtype": "float16", "max_model_len": 32768, "gpu_memory_utilization": 0.7, "request_seconds": 600}
ON = {vllm_link.AGENTS_ENV: "VERIFIER", vllm_link.PYTHON_ENV: sys.executable, "SHIMMER_MODEL_MODE": "base",
      vllm_link.JOB_ENV: json.dumps(JOB)}
CARD = 24 * 2 ** 30


class StandInLink:
    """What the server answers: the reply's ids and the constraint record for_prompt builds."""

    def __init__(self, reply_text, tamper=None, fail=None, cut=None):
        self.reply_text, self.tamper, self.fail, self.cut = reply_text, tamper, fail, cut
        self.requests = []
        self.starts = self.attempts = 0
        self.hello = {"versions": {"vllm": "stand-in"}, "start_seconds": 1.5,
                      "loaded": {"quantization": "bitsandbytes", "dtype": "torch.float16", "batch_invariant_mode": True}}

    def generate(self, ids, max_new_tokens, eos, constraint=None, seconds=None):
        self.attempts += 1
        self.requests.append(dict(ids=list(ids), max_new_tokens=max_new_tokens, eos=list(eos), constraint=constraint,
                                  seconds=seconds))
        if isinstance(self.fail, Exception):
            raise self.fail
        if self.fail:
            raise vllm_link.LinkError(self.fail)
        record = None
        if constraint is not None:
            slot = vllm_constraint.Slot(dict(constraint, key="stand-in", prompt_tokens=len(ids), eos=eos), TOK)
            vllm_constraint.COUNTS.pop("stand-in", None)
            record = dict(slot.constraint.summary(), steps=3, interventions=0)
            if self.tamper:
                record.update(self.tamper)
        out = TOK.encode(self.reply_text)[:self.cut or max_new_tokens]
        finish = "length"
        if self.cut is None and len(out) < max_new_tokens:
            out.append(eos[0])
            finish = "stop"
        return {"op": "reply", "id": "r1", "token_ids": out, "finish_reason": finish, "seconds": 0.25,
                "constraint": record}


_YIELDED = vllm_link.Yielded


class ShutOnce(StandInLink):
    """A server a transformers load on another lane shut down after its start: the first request is
    refused before it is sent (vllm_link.Yielded); the next start answers."""

    def __init__(self, reply_text):
        super().__init__(reply_text)
        self.shut, self.start_number = True, 2

    def generate(self, ids, max_new_tokens, eos, constraint=None, seconds=None):
        if self.shut:
            self.attempts += 1
            self.shut = False
            raise _YIELDED("the server was shut down to give the card back (a transformers model loads)")
        return super().generate(ids, max_new_tokens, eos, constraint, seconds)


def declared_contract(agent):
    return json.loads((HERE.parent / "config" / "agent_contracts.json").read_text(encoding="utf-8"))["contracts"][agent]


def wrapper(name="VERIFIER", backend="local_auditor", run_dir=None, contract=None):
    w = object.__new__(agent_wrapper.AgentWrapper)
    w.name, w.backend, w.model, w.cost_tracker = name, backend, "fixture", None
    w.contract = contract if contract is not None else {}
    w._optimized_semantics = True
    w.run_context = SimpleNamespace(run_dir=str(run_dir), run_id="fixture", logs_dir=lambda: Path(run_dir) / "logs")
    return w


def no_transformers(*args, **kwargs):
    raise AssertionError("the transformers model was loaded on a routed call")


def started(link):
    """The stand-in start: counted on the link."""
    link.starts = getattr(link, "starts", 0) + 1
    return link


def routed_call(link, env=ON, name="VERIFIER", backend="local_auditor", prompt="plain prompt", config=CONFIG,
                replay=None, tokenizer=None, raises=None, contract=None, method="call_local", transformers="4.51.3"):
    """One call_local through the route with the switch as `env` sets it. Returns (result, records,
    events); with `raises`, the exception call_local raised stands in for the result."""
    events = []
    with tempfile.TemporaryDirectory() as tmp:
        w = wrapper(name, backend, tmp, contract)
        with patch.dict(os.environ, env, clear=False), \
                patch.object(agent_wrapper, "_load_qwen", no_transformers), \
                patch.object(agent_wrapper, "_local_checkpoint_path", lambda m: "/models/fixture"), \
                patch.object(vllm_route, "tokenizer", tokenizer or (lambda m, p: (TOK, config))), \
                patch.object(vllm_route, "_replay", lambda: replay or REPLAY), \
                patch.object(vllm_route, "card_bytes", lambda: CARD), \
                patch.object(vllm_route, "transformers_version", lambda: transformers), \
                patch.object(model_telemetry, "emit", lambda ctx, name, **f: events.append((name, f))), \
                patch.object(vllm_route, "start", lambda m, p, t, log_dir=None: started(link)):
            if method == "call_choice":
                result = w.call_choice(prompt, ["yes", "no"], None)
            elif raises:
                try:
                    w.call_local(prompt, max_new_tokens=edc.CAP)
                except raises as exc:
                    result = exc
                else:
                    raise AssertionError("call_local did not raise %s" % raises.__name__)
            else:
                result = w.call_local(prompt, max_new_tokens=edc.CAP)
        records = [json.loads(p.read_text(encoding="utf-8"))
                   for p in (Path(tmp) / "audit" / "model_replies").glob("*.json")]
    return result, records, events


def routed(link, **kw):
    result, records, _ = routed_call(link, **kw)
    return result, records


class Route(unittest.TestCase):
    def test_a_routed_verifier_call_is_vllms_reply_under_the_runners_constraint_and_record(self):
        link = StandInLink(edc.V_VALID)
        result, records = routed(link)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.raw_text, edc.V_VALID)
        self.assertEqual(edc.reasons("VERIFIER", result.raw_text), [])
        policy = decoding_policy.policy("local_auditor")["kwargs"]
        (sent,) = link.requests
        rendered = TOK.apply_chat_template([{"role": "user", "content": "plain prompt"}])
        self.assertEqual(sent["ids"], TOK.encode(rendered))                  # the runner's own ids
        self.assertEqual(sent["eos"], policy["eos_token_id"])                 # the frozen policy's stops
        self.assertEqual(sent["constraint"], {"prompt": rendered, "agent": "VERIFIER"})
        self.assertEqual(sent["max_new_tokens"], edc.CAP)
        self.assertEqual(len(records), 1)                                     # one reply record per call
        record = records[0]
        self.assertEqual((record["attention"]["engine"], record["attention"]["request_seconds"]), ("vllm", 0.25))
        self.assertEqual(record["decoding"]["decoding_kwargs"], policy)
        usage = result.usage
        self.assertEqual((usage["engine"], usage["finish_reason"], usage["decoding_constraint"]["agent"]),
                         ("vllm", "eos", "VERIFIER"))
        self.assertEqual(usage["decoding_constraint"]["contract_sha256"], edc.contract_of("VERIFIER")[0].digest())
        self.assertEqual(record["decoding_constraint"], usage["decoding_constraint"])

    def test_with_the_switch_off_nothing_is_routed(self):
        link = StandInLink(edc.V_VALID)
        model = edc.base.StandInModel(TOK, edc.V_VALID, edc.V_VALID)
        with tempfile.TemporaryDirectory() as tmp:
            w = wrapper(run_dir=tmp)
            env = {"SHIMMER_MODEL_MODE": "base"}
            with patch.dict(os.environ, env), patch.object(agent_wrapper, "_load_qwen", return_value=(TOK, model)), \
                    patch.object(vllm_route, "start", lambda *a: link):
                saved = os.environ.pop(vllm_link.AGENTS_ENV, None)
                try:
                    result = w.call_local("plain prompt", max_new_tokens=edc.CAP)
                finally:
                    if saved is not None:
                        os.environ[vllm_link.AGENTS_ENV] = saved
        self.assertTrue(result.ok, result.error)
        self.assertEqual(link.requests, [])
        self.assertNotIn("engine", result.usage)
        self.assertEqual(len(model.calls), 1)

    def test_a_server_constraint_that_is_not_the_runners_fails_the_call(self):
        result, records = routed(StandInLink(edc.V_VALID, tamper={"contract_sha256": "0" * 64}))
        self.assertFalse(result.ok)
        self.assertIn("not the runner's", result.error)
        self.assertEqual(len(records), 1)
        # Neutralised: a comparison that always agrees lets the foreign constraint's reply through.
        with patch.object(vllm_route, "same_constraint", lambda a, b: True):
            broken, _ = routed(StandInLink(edc.V_VALID, tamper={"contract_sha256": "0" * 64}))
        self.assertTrue(broken.ok)

    def test_a_link_failure_is_a_failed_call_and_never_a_fall_back(self):
        result, records = routed(StandInLink(edc.V_VALID, fail="the server closed its output (exit 4)"))
        self.assertFalse(result.ok)
        self.assertIn("vllm route: the server closed its output", result.error)
        self.assertEqual(len(records), 1)      # no_transformers would have raised on a fall back

    def test_a_switch_without_its_python_is_refused(self):
        env = dict(ON)
        env.pop(vllm_link.PYTHON_ENV)
        link = StandInLink(edc.V_VALID)
        saved = os.environ.pop(vllm_link.PYTHON_ENV, None)
        try:
            result, _ = routed(link, env=env)
        finally:
            if saved is not None:
                os.environ[vllm_link.PYTHON_ENV] = saved
        self.assertFalse(result.ok)
        self.assertIn("is not set", result.error)
        self.assertEqual(link.requests, [])

    def test_an_over_context_prompt_is_refused_before_it_is_sent(self):
        link = StandInLink(edc.V_VALID)
        result, records = routed(link, config=cfg(max_position_embeddings=50))
        self.assertFalse(result.ok)
        self.assertIn("prompt_over_context", result.error)
        self.assertEqual(link.requests, [])
        self.assertTrue(records[0]["context"]["over_context"])

    def test_part_a_routes_local_auditor_only(self):
        link = StandInLink(edc.V_VALID)
        env = dict(ON, **{vllm_link.AGENTS_ENV: "ARCHIVIST"})
        result, _ = routed(link, env=env, name="ARCHIVIST", backend="local_producer")
        self.assertFalse(result.ok)
        self.assertIn("part A routes local_auditor only", result.error)
        self.assertEqual(link.requests, [])

    def test_a_policy_without_its_own_stop_ids_is_refused(self):
        with self.assertRaises(vllm_route.RouteRefused):
            vllm_route.policy_stops({"kwargs": {"do_sample": False, "num_beams": 1}})
        with self.assertRaises(vllm_route.RouteRefused):
            vllm_route.policy_stops({"kwargs": {"do_sample": True, "eos_token_id": [1]}})
        self.assertEqual(vllm_route.policy_stops(decoding_policy.policy("local_auditor")),
                         decoding_policy.policy("local_auditor")["kwargs"]["eos_token_id"])

    def test_a_checkpoint_that_is_not_prequantised_nf4_is_refused(self):
        link = StandInLink(edc.V_VALID)
        refusing = SimpleNamespace(quantisation=lambda path: (None, "not a pre-quantised NF4 checkpoint"))
        result, _ = routed(link, replay=refusing)
        self.assertFalse(result.ok)
        self.assertIn("pre-quantised NF4", result.error)
        self.assertEqual(link.requests, [])

    def test_the_server_starts_on_a_card_the_transformers_models_have_left(self):
        order = []
        made = SimpleNamespace(process=SimpleNamespace(poll=lambda: None), broken=None)
        env = dict(ON)
        with patch.dict(os.environ, env),                 patch.object(vllm_route, "job_for", lambda *a: order.append("job") or {}),                 patch.object(vllm_route, "free_gpu", lambda: order.append("free")),                 patch.object(vllm_route, "_replay", lambda: SimpleNamespace(child_env=lambda py, inv: {})),                 patch.object(vllm_link, "Link", lambda *a, **k: order.append("link") or made):
            vllm_link._LINKS.clear()
            try:
                self.assertIs(vllm_route.start("fixture-free", "/models/fixture", TOK), made)
            finally:
                vllm_link._LINKS.clear()
        self.assertEqual(order, ["job", "free", "link"])
        import agent_wrapper as aw
        import execution_topology
        aw._QWEN_MODELS["stand-in"] = (object(), object())
        final_models._RESIDENTS["final-stand-in"] = (object(), object())
        worker = SimpleNamespace(residents={"stand-in-worker": (object(), object())})
        saved = getattr(execution_topology.WORK, "context", None)
        execution_topology.WORK.context = SimpleNamespace(worker=worker)
        try:
            vllm_route.free_gpu()
            self.assertNotIn("stand-in", aw._QWEN_MODELS)
            self.assertNotIn("final-stand-in", final_models._RESIDENTS)
            self.assertEqual(worker.residents, {})
        finally:
            aw._QWEN_MODELS.pop("stand-in", None)
            final_models._RESIDENTS.pop("final-stand-in", None)
            execution_topology.WORK.context = saved

    def test_the_server_builds_the_constraint_from_the_wrappers_own_contract(self):
        contract = dict(declared_contract("VERIFIER"))
        contract["required"] = list(contract.get("required", [])) + ["extra_runtime_field"]
        link = StandInLink(edc.V_VALID)
        result, _ = routed(link, contract=contract)
        self.assertEqual(link.requests[0]["constraint"]["contract"], contract)
        runner = cd.envelope_constraint("VERIFIER", TOK, 0, [1], "contract", contract).summary()
        self.assertEqual(result.usage["decoding_constraint"]["contract_sha256"], runner["contract_sha256"])
        self.assertNotEqual(runner["contract_sha256"],
                            cd.envelope_constraint("VERIFIER", TOK, 0, [1], "contract").summary()["contract_sha256"])

    def test_each_request_is_held_to_the_sealed_request_time(self):
        link = StandInLink(edc.V_VALID)
        routed(link)
        self.assertEqual(link.requests[0]["seconds"], 600)

    def test_the_engines_dtypes_are_checked_and_recorded(self):
        result, records = routed(StandInLink(edc.V_VALID))
        self.assertEqual(records[0]["attention"]["dtypes"], {"transformers_dtype": "float16",
                                                             "checkpoint_compute_dtype": "bfloat16",
                                                             "vllm_dtype": "float16",
                                                             "transformers_version": "4.51.3"})
        env = dict(ON, **{vllm_link.JOB_ENV: json.dumps(dict(JOB, dtype="bfloat16"))})
        refused, _ = routed(StandInLink(edc.V_VALID), env=env)
        self.assertIn("is not the float16 the transformers load runs", refused.error)
        other = SimpleNamespace(**dict(vars(REPLAY), quantisation=lambda path: (dict(NF4, compute_dtype="float16"), None)))
        refused, _ = routed(StandInLink(edc.V_VALID), replay=other)
        self.assertIn("4-bit compute dtype float16 is not the plugin's", refused.error)

    def test_a_routed_agents_choice_decision_is_refused_and_recorded(self):
        link = StandInLink(edc.V_VALID)
        result, records = routed(link, method="call_choice")
        self.assertFalse(result.ok)
        self.assertIn("not served by the vLLM route", result.error)
        self.assertEqual(len(records), 1)
        self.assertEqual(link.requests, [])

    def test_a_server_that_loaded_anything_but_the_sealed_engine_is_refused(self):
        for loaded, words in (({"quantization": None, "dtype": "torch.float16", "batch_invariant_mode": True}, "not bitsandbytes"),
                              ({"quantization": "bitsandbytes", "dtype": "torch.bfloat16", "batch_invariant_mode": True}, "not the sealed"),
                              ({"quantization": "bitsandbytes", "dtype": "torch.float16", "batch_invariant_mode": False}, "batch-invariant")):
            with self.subTest(words=words):
                link = StandInLink(edc.V_VALID)
                link.hello = dict(link.hello, loaded=loaded)
                retired = []
                with patch.object(vllm_link, "retire", lambda key, reason: retired.append((key, reason))):
                    result, _ = routed(link)
                self.assertFalse(result.ok)
                self.assertIn(words, result.error)
                self.assertEqual(link.requests, [])
                self.assertEqual([k for k, _ in retired], [("fixture", "/models/fixture")])

    def test_a_server_shut_down_before_the_request_is_started_again_once(self):
        link = ShutOnce(edc.V_VALID)
        result, records = routed(link)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(len(link.requests), 1)                              # sent once, to the started server
        self.assertEqual((link.starts, link.attempts), (2, 2))               # started again exactly once
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["attention"]["server_start"], 2)
        twice = StandInLink(edc.V_VALID, fail=_YIELDED("shut down again"))
        result, records = routed(twice)
        self.assertFalse(result.ok)                                          # a second shut-down is a failed call
        self.assertEqual(result.error, "vllm route: shut down again")
        self.assertEqual((twice.starts, twice.attempts), (2, 2))             # never a third start
        self.assertEqual(len(records), 1)

    def test_a_retired_server_is_closed_and_never_started_again(self):
        closed = []
        held = SimpleNamespace(process=SimpleNamespace(poll=lambda: None), broken=None,
                               close=lambda graceful=True: closed.append(graceful))
        vllm_link._LINKS[("m", "/p")] = held
        try:
            vllm_link.retire(("m", "/p"), "the server loaded 'None' weights")
            self.assertEqual(closed, [False])
            with self.assertRaises(vllm_link.LinkError) as caught:
                vllm_link.link_for(("m", "/p"), lambda: self.fail("started again"))
            self.assertIn("failed earlier in this run", str(caught.exception))
        finally:
            vllm_link._LINKS.pop(("m", "/p"), None)
            vllm_link._FAILED.pop(("m", "/p"), None)

    def test_the_transformers_load_dtype_is_read_only_for_the_versions_it_was_measured_on(self):
        result, _ = routed(StandInLink(edc.V_VALID), transformers="5.20.2")
        self.assertFalse(result.ok)
        self.assertIn("this runner has 5.20.2", result.error)
        result, records = routed(StandInLink(edc.V_VALID), transformers="4.52.3")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(records[0]["attention"]["dtypes"]["transformers_version"], "4.52.3")

    def test_the_server_log_goes_to_its_own_file_not_the_workload_stderr(self):
        seen = {}

        class Recording:
            def __init__(self, python, job, **kw):
                seen.update(kw)
                self.process = SimpleNamespace(poll=lambda: None)
                self.broken = None
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, ON), \
                patch.object(vllm_route, "job_for", lambda *a: {}), patch.object(vllm_route, "free_gpu", lambda: None), \
                patch.object(vllm_route, "_replay", lambda: SimpleNamespace(child_env=lambda py, inv: {})), \
                patch.object(vllm_link, "Link", Recording):
            vllm_link._LINKS.clear()
            try:
                vllm_route.start("fixture-log", "/models/fixture", TOK, Path(d) / "logs" / "vllm_server")
            finally:
                vllm_link._LINKS.clear()
            self.assertEqual(seen["stderr_path"], Path(d) / "logs" / "vllm_server" / "server.stderr.log")

    def test_the_runners_token_table_digest_is_the_servers(self):
        import vllm_constraint
        self.assertEqual(vllm_route.table_digest(TOK), vllm_constraint.table_digest(TOK))

    def test_a_call_past_the_servers_length_is_the_declared_exclusion(self):
        link = StandInLink(edc.V_VALID)
        env = dict(ON, **{vllm_link.JOB_ENV: json.dumps(dict(JOB, max_model_len=60))})
        result, records = routed(link, env=env)
        self.assertFalse(result.ok)
        self.assertIn("prompt_over_context", result.error)
        self.assertEqual(link.requests, [])
        context = records[0]["context"]
        self.assertEqual((context["over_context"], context["model_context"], context["held_to"],
                          context["model_positions"]), (True, 60, "vllm_max_model_len", 100000))

    def test_a_reply_vllm_cut_for_length_is_a_truncation_never_complete(self):
        result, _ = routed(StandInLink(edc.V_VALID, cut=5))
        self.assertTrue(result.ok)
        self.assertEqual((result.usage["finish_reason"], result.usage["truncated"]), ("length", True))

    def test_a_server_out_of_memory_is_the_named_failure_recorded_once(self):
        link = StandInLink(edc.V_VALID, fail=vllm_link.RequestFailed("OutOfMemoryError: CUDA out of memory. Tried"))
        exc, records, events = routed_call(link, raises=final_models.GenerationFailure)
        self.assertEqual(exc.kind, final_models.GenerationOutOfMemory.kind)
        self.assertEqual([(r["backend_ok"], r["error_category"]) for r in records], [(False, exc.kind)])
        self.assertIn("generation_failure", [name for name, _ in events])

    def test_another_server_error_is_one_failed_call(self):
        result, records = routed(StandInLink(edc.V_VALID, fail=vllm_link.RequestFailed("ValueError: bad request")))
        self.assertFalse(result.ok)
        self.assertIn("ValueError: bad request", result.error)
        self.assertEqual(len(records), 1)

    def test_any_other_route_error_is_still_one_recorded_failed_call(self):
        def broken(model_id, path):
            raise OSError("tokenizer files missing")
        result, records = routed(StandInLink(edc.V_VALID), tokenizer=broken)
        self.assertFalse(result.ok)
        self.assertIn("OSError: tokenizer files missing", result.error)
        self.assertEqual(len(records), 1)

    def test_what_the_route_does_not_carry_is_refused_not_dropped(self):
        policy = decoding_policy.policy("local_auditor")
        with self.assertRaises(vllm_route.RouteRefused) as caught:
            vllm_route.policy_stops(dict(policy, kwargs=dict(policy["kwargs"], top_k=5)))
        self.assertIn("top_k", str(caught.exception))
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(vllm_route.generation_refusal(d))
            (Path(d) / "generation_config.json").write_text(json.dumps({"repetition_penalty": 1.05, "min_length": 0}),
                                                            encoding="utf-8")
            self.assertIsNone(vllm_route.generation_refusal(d))
            (Path(d) / "generation_config.json").write_text(json.dumps({"no_repeat_ngram_size": 3}), encoding="utf-8")
            self.assertIn("no_repeat_ngram_size", vllm_route.generation_refusal(d))

    def test_the_card_share_must_hold_one_full_length_cache(self):
        phi = cfg(num_hidden_layers=32, num_attention_heads=32, num_key_value_heads=32, hidden_size=3072)
        card = 23028 * 2 ** 20
        with patch.object(vllm_route, "weight_bytes", lambda path: int(2.2 * 2 ** 30)):
            plan, why = vllm_route.memory_plan(phi, "/models/fixture", 28672, 0.55, card)
            self.assertEqual(plan["kv_bytes_per_token"], 393216)          # 384 KiB, no grouped KV heads
            self.assertIn("cannot hold", why)
            plan, why = vllm_route.memory_plan(phi, "/models/fixture", 28672, 0.7, card)
            self.assertIsNone(why)
            self.assertGreaterEqual(plan["remainder_bytes"], vllm_route.REMAINDER_FLOOR_BYTES)
            self.assertIn("transformers models loaded beside it",
                          vllm_route.memory_plan(phi, "/models/fixture", 28672, 0.8, card)[1])
            link = StandInLink(edc.V_VALID)
            env = dict(ON, **{vllm_link.JOB_ENV: json.dumps(dict(JOB, max_model_len=28672, gpu_memory_utilization=0.55))})
            with patch.object(vllm_route, "card_bytes", lambda: card):
                result, _ = routed(link, env=env, config=phi)
        self.assertFalse(result.ok)
        self.assertIn("cannot hold", result.error)
        self.assertEqual(link.requests, [])

    def test_the_servers_job_is_the_sealed_fields_and_the_runners_own_readings(self):
        replay = SimpleNamespace(repetition_penalty=lambda path: 1.05, _observer=lambda: "/obs/cloud_run_observer.py",
                                 dtype_refusal=vllm_replay.dtype_refusal, vllm_dtypes=vllm_replay.vllm_dtypes)
        with patch.dict(os.environ, ON), patch.object(vllm_route, "_replay", lambda: replay):
            job = vllm_route.job_for("fixture", "/models/fixture", TOK)
        self.assertIsNone(vllm_link.job_error(job))
        self.assertEqual(json.loads(ON[vllm_link.JOB_ENV])["request_seconds"], 600)
        self.assertEqual((job["dtype"], job["max_model_len"], job["gpu_memory_utilization"], job["repetition_penalty"],
                          job["observer"], job["adapter"]), ("float16", 32768, 0.7, 1.05, "/obs/cloud_run_observer.py", None))
        self.assertEqual(job["token_table_sha256"], vllm_route.table_digest(TOK))


def _local_stop_only(last, eos, count, requested, finish_reason):
    import generation_observation
    return generation_observation.local_stop(last, eos, count, requested)


_ORIGINAL_START = vllm_route.start


# Each rule, neutralised, must make its proof fail; restored, the proof passes.
NEUTRALIZATIONS = [
    ("test_with_the_switch_off_nothing_is_routed", vllm_link, "routed", lambda name: True),
    ("test_a_server_constraint_that_is_not_the_runners_fails_the_call", vllm_route, "same_constraint", lambda a, b: True),
    ("test_a_call_past_the_servers_length_is_the_declared_exclusion", vllm_route, "held_context", lambda c, n: c),
    ("test_a_reply_vllm_cut_for_length_is_a_truncation_never_complete", vllm_route, "stop_of", _local_stop_only),
    ("test_part_a_routes_local_auditor_only", vllm_route, "BACKENDS", ("local_auditor", "local_producer")),
    ("test_a_checkpoint_that_is_not_prequantised_nf4_is_refused", vllm_route, "quant_of", lambda path: NF4),
    ("test_a_routed_verifier_call_is_vllms_reply_under_the_runners_constraint_and_record", vllm_route, "policy_stops",
     lambda decoding: [0]),
    ("test_the_server_starts_on_a_card_the_transformers_models_have_left", vllm_route, "free_gpu", lambda: None),
    ("test_the_card_share_must_hold_one_full_length_cache", vllm_route, "memory_plan", lambda *a: ({}, None)),
    ("test_a_server_out_of_memory_is_the_named_failure_recorded_once", final_models, "named_generation_failure",
     lambda exc: None),
    ("test_what_the_route_does_not_carry_is_refused_not_dropped", vllm_route, "POLICY_KWARGS",
     vllm_route.POLICY_KWARGS | {"top_k"}),
    ("test_what_the_route_does_not_carry_is_refused_not_dropped", vllm_route, "UNCARRIED_GENERATION", {}),
    # Round 2.
    ("test_a_link_failure_is_a_failed_call_and_never_a_fall_back", vllm_link, "routed", lambda name: False),
    ("test_any_other_route_error_is_still_one_recorded_failed_call", agent_wrapper.AgentWrapper, "_vllm_call",
     lambda self, prompt, system, n, decoding, applied, sent, model_id: vllm_route.call(self, prompt, system, n, decoding,
                                                                                     applied, sent)),
    ("test_another_server_error_is_one_failed_call", final_models, "named_generation_failure",
     lambda exc: final_models.GenerationOutOfMemory("RuntimeError")),
    ("test_a_switch_without_its_python_is_refused", vllm_link, "routed", lambda name: name in vllm_link.agents()),
    ("test_an_over_context_prompt_is_refused_before_it_is_sent", final_models, "context_record",
     lambda model, n, m: dict(prompt_tokens=n, max_new_tokens=m, model_context=None, over_context=False)),
    ("test_the_runners_token_table_digest_is_the_servers", vllm_route, "table_digest", lambda tok: "0" * 64),
    ("test_the_server_builds_the_constraint_from_the_wrappers_own_contract", vllm_route, "server_request",
     lambda local, prompt, w: None if local is None else {"prompt": prompt, "agent": local.get("agent")}),
    ("test_each_request_is_held_to_the_sealed_request_time", vllm_link, "sealed_job",
     lambda: dict(JOB, request_seconds=1800)),
    ("test_the_engines_dtypes_are_checked_and_recorded", vllm_route, "dtype_plan", lambda dtype, quant: {}),
    ("test_a_routed_agents_choice_decision_is_refused_and_recorded", vllm_link, "routed", lambda name: False),
    ("test_the_card_share_must_hold_one_full_length_cache", vllm_route, "REMAINDER_FLOOR_BYTES", 0),
    # Round 3.
    ("test_a_server_that_loaded_anything_but_the_sealed_engine_is_refused", vllm_route, "loaded_refusal",
     lambda hello, sealed: None),
    ("test_the_transformers_load_dtype_is_read_only_for_the_versions_it_was_measured_on", vllm_route,
     "TRANSFORMERS_FLOAT16_VERSIONS", ("4.", "5.")),
    ("test_the_server_log_goes_to_its_own_file_not_the_workload_stderr", vllm_route, "start",
     lambda m, p, t, log_dir=None, popen=None: _ORIGINAL_START(m, p, t, None, popen)),
    ("test_the_servers_job_is_the_sealed_fields_and_the_runners_own_readings", vllm_route, "checkpoint_penalty",
     lambda path: 1.0),
    # Round 4.
    ("test_a_retired_server_is_closed_and_never_started_again", vllm_link, "retire",
     lambda key, reason: None),
    # #297: the card handed back (the load sites are proved in scripts/vllm_link_checks.py, CardHandback).
    ("test_a_server_shut_down_before_the_request_is_started_again_once", vllm_link, "Yielded",
     type("NotTheYield", (vllm_link.LinkError,), {})),
    ("test_a_server_shut_down_before_the_request_is_started_again_once", vllm_route, "YIELD_RESTARTS", 2),
    ("test_a_server_shut_down_before_the_request_is_started_again_once", vllm_route, "YIELD_RESTARTS", 0),
]


class Neutralizations(unittest.TestCase):
    def test_each_proof_fails_when_its_rule_is_neutralised_and_passes_restored(self):
        import io
        for name, module, attribute, broken in NEUTRALIZATIONS:
            with self.subTest(name=name, attribute=attribute):
                with patch.object(module, attribute, broken):
                    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(Route(name))
                self.assertFalse(result.wasSuccessful(), "%s still passes with %s neutralised" % (name, attribute))
                restored = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(Route(name))
                self.assertTrue(restored.wasSuccessful(), name)


if __name__ == "__main__":
    unittest.main(verbosity=1)
