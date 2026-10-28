"""Checks for B3's local attention and prefill (docs/loop/DECISIONS.md D-058, D-060 and D-061),
run by the verify gate (scripts/verify_session1.py check 288) through check(); `py -3.12 -X utf8
scripts/local_attention_checks.py` runs them by hand and `--prove` runs the neutralise, fail,
restore, pass proofs alone.

On mocked models (no weights, no download, no device: a model "on CUDA" is a device name), with
the real torch for the sdpa backend switches, and on one tiny randomly built CPU Qwen2 model
(2 layers, built in the check, no download):

  - the producer's attention is a sealed setting with exactly two values: eager by default
    (D-060), sdpa only with a recorded decision (D-NNN); anything else refuses;
  - the producer's prefill is a sealed setting (D-061): chunked at 512 tokens under D-061 by
    default; one-shot or another chunk size only with a recorded decision; anything else refuses;
  - final_models.load loads the tuned producer with its attention and prefill and the
    Auditor896 classifier eager, which its runtime contract (config/final_models.json and
    tuning/auditor_final/runtime_contract.json) still says; a contract naming another
    attention refuses;
  - _load_qwen (VERIFIER, PRACTICE_AUDITOR, FACT_CHECKER, REDACTOR, the base-mode producer)
    names sdpa on every one of its three loads;
  - every producer call through agent_wrapper.call_local runs under the producer's attention
    (eager, unpinned; an sdpa measurement producer pinned) with its sealed prefill, and every
    _load_qwen model's call through call_local and call_qwen runs inside
    torch.nn.attention.sdpa_kernel([SDPBackend.EFFICIENT_ATTENTION]) in one shot; each reply
    record carries the kernel, the backend, the decision, the pin and the prefill setting,
    and what the prefill measured;
  - on the tiny CPU model, a producer call of three full chunks and the 2-token tail through
    call_local gives byte for byte the reply the same call gives prefilled in one shot;
  - out of memory, or a refused kernel, is one recorded failure raised under its own name
    (final_models.GenerationOutOfMemory, AttentionKernelRefused), generate called once;
  - a prompt that does not fit the model's context with the call's output allowance is
    refused before generating, recorded in its reply record and as a prompt_over_context
    telemetry event, never truncated (D-058 condition v).

Every case runs in a temporary directory and writes nothing under config/, durable/,
ontology/ or output/.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import final_models  # noqa: E402

ENV_KEYS = (final_models.PRODUCER_ATTENTION_ENV, final_models.PRODUCER_ATTENTION_DECISION_ENV,
            final_models.PRODUCER_PREFILL_ENV, final_models.PRODUCER_PREFILL_DECISION_ENV)
E = {"prefill": "chunked", "prefill_chunk_tokens": 512, "prefill_decision": "D-061"}
ONE_SHOT = {"prefill": "one_shot", "prefill_chunk_tokens": None, "prefill_decision": None}
PINNED = dict({"attention_implementation": "sdpa", "sdpa_backend": "EFFICIENT_ATTENTION",
               "attention_decision": None, "pinned": True}, **ONE_SHOT)
PRODUCER = dict({"attention_implementation": "eager", "sdpa_backend": None, "attention_decision": None,
                 "pinned": False}, **E)


def _torch():
    import torch
    return torch


def _enabled_backends():
    """The sdpa backends torch allows right now, read here, not through final_models."""
    cuda = _torch().backends.cuda
    flags = {"CUDNN_ATTENTION": cuda.cudnn_sdp_enabled(), "EFFICIENT_ATTENTION": cuda.mem_efficient_sdp_enabled(),
             "FLASH_ATTENTION": cuda.flash_sdp_enabled(), "MATH": cuda.math_sdp_enabled()}
    return "+".join(name for name, on in sorted(flags.items()) if on)


class _Batch(dict):
    def to(self, device):
        return self


class _Tokenizer:
    """One id per word (the word itself when it is a number, else its position); decodes ids
    back to numbers joined by spaces."""
    chat_template = "fixture"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        return "\n".join(m["content"] for m in messages)

    def __call__(self, text, return_tensors=None, add_special_tokens=True):
        torch = _torch()
        words = text.split()
        ids = [int(w) if w.isdigit() else k + 1 for k, w in enumerate(words)]
        return _Batch(input_ids=torch.tensor([ids]), attention_mask=torch.ones((1, len(ids)), dtype=torch.long))

    def decode(self, ids, skip_special_tokens=True):
        return " ".join(str(int(i)) for i in ids) if len(ids) else "{}"


class _Model:
    """A resident model, mocked: its attention setting, a device name and a context; generate()
    records the setting and the enabled sdpa backends at the moment it is called."""

    def __init__(self, attention="sdpa", device="cuda:0", context=10 ** 6, sealed=None, prefill=None):
        self.config = SimpleNamespace(_attn_implementation=attention, max_position_embeddings=context)
        self.device, self.calls, self.fail = device, [], None
        self.generation_config = SimpleNamespace(eos_token_id=None)
        self._shimmer_identity = {"model_mode": "final", "adapter_checkpoint": 168}
        if sealed is not None:
            self._shimmer_attention = sealed
        if prefill is not None:
            self._shimmer_prefill = prefill

    def generate(self, input_ids=None, attention_mask=None, max_new_tokens=1, **kwargs):
        torch = _torch()
        self.calls.append((self.config._attn_implementation, _enabled_backends()))
        if self.fail is not None:
            raise self.fail
        return torch.cat([input_ids, torch.tensor([[7, 7]])], dim=1)


def _tiny_producer():
    """A tiny randomly built CPU Qwen2 (2 layers, no download), eager, as final_models loads the
    producer, carrying the sealed producer settings the way final_models.load sets them. Its
    vocabulary covers the frozen decoding policy's stop and pad ids."""
    torch = _torch()
    from transformers import Qwen2Config, Qwen2ForCausalLM
    torch.manual_seed(0)
    config = Qwen2Config(vocab_size=151700, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                         num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=4096,
                         sliding_window=None, use_sliding_window=False, attn_implementation="eager")
    model = Qwen2ForCausalLM(config).eval()
    model._shimmer_identity = {"model_mode": "final", "adapter_checkpoint": 168}
    model._shimmer_attention = final_models.producer_attention({})
    return model


class _RunContext:
    def __init__(self, run_dir):
        self.run_dir, self.run_id = str(run_dir), "attention-fixture"

    def logs_dir(self):
        return Path(self.run_dir) / "logs"


class LocalAttentionChecks(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="b3_attention_")
        self.env = mock.patch.dict(os.environ)
        self.env.start()
        for key in ENV_KEYS:
            os.environ.pop(key, None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    # ---- the settings --------------------------------------------------------------------

    def test_the_producer_attention_defaults_to_eager_and_sdpa_needs_a_decision(self):
        self.assertEqual(final_models.producer_attention({}),
                         {"attention_implementation": "eager", "sdpa_backend": None, "attention_decision": None})
        self.assertEqual(final_models.load_attention("producer"), "eager")
        sdpa = {final_models.PRODUCER_ATTENTION_ENV: "sdpa", final_models.PRODUCER_ATTENTION_DECISION_ENV: "D-061"}
        self.assertEqual(final_models.producer_attention(sdpa),
                         {"attention_implementation": "sdpa", "sdpa_backend": "EFFICIENT_ATTENTION",
                          "attention_decision": "D-061"})
        for value, decision in (("sdpa", None), ("eager", "D-061"), ("sdpa", "decided"), ("flash", None),
                                ("", None), ("SDPA", "D-061")):
            environ = {final_models.PRODUCER_ATTENTION_ENV: value}
            if decision is not None:
                environ[final_models.PRODUCER_ATTENTION_DECISION_ENV] = decision
            with self.assertRaises(RuntimeError, msg=(value, decision)):
                final_models.producer_attention(environ)
        with mock.patch.dict(os.environ, {final_models.PRODUCER_ATTENTION_ENV: "sdpa"}):
            with self.assertRaisesRegex(RuntimeError, "recorded decision"):
                final_models.load_attention("producer")

    def test_the_producer_prefill_is_chunked_and_one_shot_needs_a_decision(self):
        self.assertEqual(final_models.producer_prefill({}), E)
        self.assertEqual(final_models.prefill_setting(), E)
        self.assertEqual(final_models.prefill_setting(512, "D-061"), E)
        self.assertEqual(final_models.producer_prefill({final_models.PRODUCER_PREFILL_ENV: "one_shot",
                                                        final_models.PRODUCER_PREFILL_DECISION_ENV: "D-061"}),
                         dict(ONE_SHOT, prefill_decision="D-061"))
        self.assertEqual(final_models.producer_prefill({final_models.PRODUCER_PREFILL_ENV: "1024",
                                                        final_models.PRODUCER_PREFILL_DECISION_ENV: "D-099"}),
                         {"prefill": "chunked", "prefill_chunk_tokens": 1024, "prefill_decision": "D-099"})
        for chunk, decision in (("one_shot", None), ("1024", None), (None, "D-099"), ("512", "D-099"),
                                ("0", "D-099"), ("-5", "D-099"), ("half", "D-099"), ("1024", "decided"),
                                ("ONE_SHOT", "D-061")):
            environ = {} if chunk is None else {final_models.PRODUCER_PREFILL_ENV: chunk}
            if decision is not None:
                environ[final_models.PRODUCER_PREFILL_DECISION_ENV] = decision
            with self.assertRaises(RuntimeError, msg=(chunk, decision)):
                final_models.producer_prefill(environ)
        self.assertEqual(final_models.GENERATE_TAIL_TOKENS, 2)

    def test_the_classifier_stays_eager_as_its_runtime_contract_says(self):
        # The tuning record is not in the container image (it copies scripts/, config/ and a few
        # named files): there the configuration's copy of the contract is the one checked.
        recorded = ROOT / "tuning/auditor_final/runtime_contract.json"
        if recorded.is_file():
            self.assertEqual(json.loads(recorded.read_text(encoding="utf8"))["attn_implementation"], "eager")
        self.assertEqual(final_models.specification("auditor")["runtime"]["attn_implementation"], "eager")
        self.assertEqual(final_models.load_attention("auditor"), "eager")
        # the producer's setting never reaches the classifier
        with mock.patch.dict(os.environ, {final_models.PRODUCER_ATTENTION_ENV: "sdpa",
                                          final_models.PRODUCER_ATTENTION_DECISION_ENV: "D-061"}):
            self.assertEqual(final_models.load_attention("auditor"), "eager")
        spec = json.loads((ROOT / "config/final_models.json").read_text(encoding="utf8"))["auditor"]
        spec["runtime"]["attn_implementation"] = "sdpa"
        with self.assertRaisesRegex(RuntimeError, "classifier runs eager"):
            final_models.load_attention("auditor", spec)

    def _load(self, role, environ=None):
        """final_models.load with every library and file mocked; returns the kwargs the
        model was loaded with and the loaded object."""
        captured = []

        class AutoModelForCausalLM:
            @staticmethod
            def from_pretrained(path, **kw):
                captured.append(kw)
                model = _Model(attention=kw.get("attn_implementation"))
                model.config.model_type = "qwen2" if role == "producer" else "llama"
                model.config.quantization_config = {"bnb_4bit_quant_type": "nf4", "bnb_4bit_compute_dtype": "bfloat16"}
                model.is_loaded_in_4bit = True
                return model

        class PeftModel:
            @staticmethod
            def from_pretrained(model, adapter_dir, **kw):
                return model

        def prepared(model, **kw):
            model.requires_grad_ = model.eval = model.gradient_checkpointing_disable = lambda *a: model
            return model
        transformers = SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a, **k: _Tokenizer()),
                                       AutoModelForCausalLM=AutoModelForCausalLM)
        peft = SimpleNamespace(PeftModel=PeftModel, prepare_model_for_kbit_training=prepared)
        spec = final_models.specification(role)
        paths = {"adapter": Path(self.tmp.name) / "adapter.safetensors", "adapter_config": Path(self.tmp.name) / "c"}
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, environ or {}))
            stack.enter_context(mock.patch.dict(sys.modules, {"transformers": transformers, "peft": peft}))
            stack.enter_context(mock.patch.object(final_models, "verify", return_value=(spec, paths)))
            stack.enter_context(mock.patch.object(final_models, "verify_runtime",
                                                  return_value=SimpleNamespace(bfloat16="bfloat16")))
            stack.enter_context(mock.patch.object(final_models, "base_path", return_value=Path(self.tmp.name)))
            stack.enter_context(mock.patch.object(final_models, "Classifier", lambda torch, model, p, s: model))
            _, model = final_models.load(role, "cuda:0")
        return captured[0], model

    def test_final_models_loads_the_producer_with_its_settings_and_the_classifier_eager(self):
        kwargs, model = self._load("producer")
        self.assertEqual(kwargs["attn_implementation"], "eager")
        self.assertEqual((model._shimmer_attention["attention_implementation"], model._shimmer_prefill), ("eager", E))
        measurement = {final_models.PRODUCER_ATTENTION_ENV: "sdpa", final_models.PRODUCER_ATTENTION_DECISION_ENV: "D-061",
                       final_models.PRODUCER_PREFILL_ENV: "one_shot", final_models.PRODUCER_PREFILL_DECISION_ENV: "D-061"}
        kwargs, model = self._load("producer", measurement)
        self.assertEqual((kwargs["attn_implementation"], model._shimmer_attention["attention_decision"],
                          model._shimmer_prefill["prefill"]), ("sdpa", "D-061", "one_shot"))
        kwargs, model = self._load("auditor", measurement)
        self.assertEqual(kwargs["attn_implementation"], "eager")
        self.assertFalse(hasattr(model, "_shimmer_attention") or hasattr(model, "_shimmer_prefill"))
        with self.assertRaisesRegex(RuntimeError, "recorded decision"):
            self._load("producer", {final_models.PRODUCER_ATTENTION_ENV: "sdpa"})
        with self.assertRaisesRegex(RuntimeError, "recorded decision"):
            self._load("producer", {final_models.PRODUCER_PREFILL_ENV: "one_shot"})

    def test_load_qwen_names_sdpa_on_every_load(self):
        import agent_wrapper
        captured = []

        def model_loader(path, **kw):
            captured.append(kw)
            return SimpleNamespace(parameters=lambda: iter([SimpleNamespace(device="cuda:0")]))
        for prequantised, cuda in ((True, True), (False, True), (False, False)):
            fake_torch = SimpleNamespace(float16="float16", cuda=SimpleNamespace(
                is_available=lambda c=cuda: c, memory_allocated=lambda device: 0, empty_cache=lambda: None))
            config = SimpleNamespace(quantization_config={"quant_method": "bitsandbytes"} if prequantised else None)
            transformers = SimpleNamespace(
                AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a, **k: _Tokenizer()),
                AutoConfig=SimpleNamespace(from_pretrained=lambda *a, **k: config),
                AutoModelForCausalLM=SimpleNamespace(from_pretrained=model_loader),
                BitsAndBytesConfig=lambda **k: SimpleNamespace(**k))
            with mock.patch.dict(sys.modules, {"transformers": transformers, "torch": fake_torch}), \
                    mock.patch.dict(agent_wrapper._QWEN_MODELS, clear=True), \
                    mock.patch.object(agent_wrapper, "_local_checkpoint_path", lambda model_id: model_id), \
                    mock.patch.object(final_models, "release_reference_residency", lambda: None), \
                    mock.patch("execution_topology.resident_model", lambda model_id: None), \
                    contextlib.redirect_stderr(io.StringIO()):
                agent_wrapper._load_qwen("fixture/attention-model")
        self.assertEqual(len(captured), 3)
        self.assertEqual([kw.get("attn_implementation") for kw in captured], ["sdpa"] * 3)

    # ---- the calls -----------------------------------------------------------------------

    def _wrapper(self, backend, model_id="fixture/model"):
        import agent_wrapper
        wrapper = object.__new__(agent_wrapper.AgentWrapper)
        wrapper.backend, wrapper.model, wrapper.name = backend, model_id, "PROCESSOR"
        wrapper.run_context = _RunContext(Path(self.tmp.name) / "run")
        wrapper._optimized_semantics, wrapper._cost_call_id = False, ""
        wrapper._record_cost = lambda r, **kw: None
        return wrapper

    def _records(self):
        import reply_records
        return reply_records.records(Path(self.tmp.name) / "run" / "audit" / "model_replies")

    def _telemetry(self, event):
        path = Path(self.tmp.name) / "run" / "logs" / "model_telemetry.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()] if path.exists() else []
        return [row for row in rows if row["event"] == event]

    @contextlib.contextmanager
    def _resident(self, model, mode="final"):
        """The tuned producer resident in final mode, or the _load_qwen model in base mode."""
        import agent_wrapper
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": mode}))
            stack.enter_context(mock.patch.object(final_models, "specification",
                                                  return_value={"model_id": "fixture/model"}))
            stack.enter_context(mock.patch.object(final_models, "resident", return_value=(_Tokenizer(), model)))
            stack.enter_context(mock.patch.object(agent_wrapper, "_load_qwen", return_value=(_Tokenizer(), model)))
            yield

    def test_every_local_call_runs_its_attention_and_prefill_and_records_them(self):
        everything = _enabled_backends()
        self.assertNotEqual(everything, "EFFICIENT_ATTENTION")
        # the frozen producer: eager, unpinned, chunked prefill (E) under D-061
        model = _Model(attention="eager", sealed=final_models.producer_attention({}), prefill=E)
        with self._resident(model):
            self.assertTrue(self._wrapper("local_producer").call_local("a fixture prompt", max_new_tokens=2).ok)
        self.assertEqual(model.calls, [("eager", everything)])
        record = self._records()[-1]
        self.assertEqual(record["attention"], PRODUCER)
        self.assertEqual({k: record["prefill"][k] for k in ("prompt_tokens", "chunks", "chunked_tokens", "tail_tokens")},
                         {"prompt_tokens": 3, "chunks": 0, "chunked_tokens": 0, "tail_tokens": 3})
        self.assertEqual(record["context"],
                         {"prompt_tokens": 3, "max_new_tokens": 2, "model_context": 10 ** 6, "over_context": False})
        # the base-mode producer (_load_qwen, sdpa): pinned, and still a producer call, so chunked
        # under the sealed prefill setting; the _load_qwen agents and REDACTOR: pinned, one shot
        sites = (("base", "local_producer", "call_local", dict(PINNED, **E)),
                 ("base", "local_auditor", "call_local", PINNED), ("base", "qwen_local", "call_qwen", PINNED))
        for mode, backend, site, expected in sites:
            model = _Model()
            with self._resident(model, mode):
                result = getattr(self._wrapper(backend), site)("a fixture prompt", max_new_tokens=2)
            self.assertTrue(result.ok, (backend, result.error))
            self.assertEqual(model.calls, [("sdpa", "EFFICIENT_ATTENTION")], (mode, backend))
            self.assertEqual(self._records()[-1]["attention"], expected, (mode, backend))
        self.assertEqual(_enabled_backends(), everything, "the pin ends with the call")
        # a producer sealed sdpa for a measurement runs pinned and records its decision
        sealed = final_models.producer_attention({final_models.PRODUCER_ATTENTION_ENV: "sdpa",
                                                  final_models.PRODUCER_ATTENTION_DECISION_ENV: "D-061"})
        model = _Model(attention="sdpa", sealed=sealed, prefill=E)
        with self._resident(model):
            self.assertTrue(self._wrapper("local_producer").call_local("a fixture prompt", max_new_tokens=2).ok)
        self.assertEqual(model.calls, [("sdpa", "EFFICIENT_ATTENTION")])
        self.assertEqual(self._records()[-1]["attention"], dict(PINNED, attention_decision="D-061", **E))
        # on a CPU, which has no memory-efficient kernel, a call runs unpinned and says so
        model = _Model(device="cpu")
        with self._resident(model, "base"):
            self.assertTrue(self._wrapper("qwen_local").call_qwen("a fixture prompt", max_new_tokens=2).ok)
        self.assertEqual((model.calls, self._records()[-1]["attention"]["pinned"]), ([("sdpa", everything)], False))

    def test_a_producer_call_in_chunks_replies_as_one_shot_on_a_tiny_cpu_model(self):
        """D-061 items 3 and 6 end to end: call_local on the resident producer (final mode), a
        prompt of three full 512-token chunks and the 2-token tail, the frozen decoding policy;
        the reply is byte for byte the one the same call gives prefilled in one shot, and each
        reply record says how it was prefilled."""
        torch = _torch()
        model = _tiny_producer()
        words = [str(int(i)) for i in torch.randint(1, 5000, (3 * 512 + 2,), generator=torch.Generator().manual_seed(3))]
        prompt = " ".join(words)
        replies = {}
        for name, prefill in (("e", E), ("one_shot", final_models.prefill_setting("one_shot", "D-061"))):
            model._shimmer_prefill = prefill
            with self._resident(model):
                result = self._wrapper("local_producer").call_local(prompt, max_new_tokens=4)
            self.assertTrue(result.ok, result.error)
            replies[name] = (result.raw_text, self._records()[-1])
        (e_text, e_record), (one_text, one_record) = replies["e"], replies["one_shot"]
        self.assertEqual(e_text, one_text, "the chunked reply differs from the one-shot reply")
        self.assertEqual(e_record["reply"]["sha256"], one_record["reply"]["sha256"])
        self.assertEqual(e_record["attention"], PRODUCER)
        self.assertEqual(one_record["attention"], dict(PRODUCER, prefill="one_shot", prefill_chunk_tokens=None))
        self.assertEqual({k: e_record["prefill"][k] for k in ("prompt_tokens", "chunks", "chunked_tokens", "tail_tokens")},
                         {"prompt_tokens": 1538, "chunks": 3, "chunked_tokens": 1536, "tail_tokens": 2})
        self.assertEqual((one_record["prefill"]["chunks"], one_record["prefill"]["tail_tokens"]), (0, 1538))
        for record in (e_record, one_record):
            self.assertIsInstance(record["prefill"]["prefill_seconds"], float)
        # the cache chunked_prefill leaves holds every prompt token but the last two
        ids = torch.tensor([[int(w) for w in words]])
        with torch.no_grad():
            cache, chunks = final_models.chunked_prefill(model, ids, 512)
        self.assertEqual((chunks, cache.get_seq_length()), (3, 1536))

    def test_out_of_memory_and_a_refused_kernel_are_named_failures_never_retried(self):
        torch = _torch()
        cases = ((torch.cuda.OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB (fixture)"),
                  final_models.GenerationOutOfMemory, "out_of_memory"),
                 (RuntimeError("No available kernel. Aborting execution."),
                  final_models.AttentionKernelRefused, "attention_kernel_refused"))
        for site, backend in (("call_local", "local_producer"), ("call_qwen", "qwen_local")):
            for error, named, kind in cases:
                model = _Model()
                model.fail = error
                before = len(self._records())
                with self._resident(model, "final" if backend == "local_producer" else "base"):
                    with self.assertRaises(named, msg=(site, kind)) as caught:
                        getattr(self._wrapper(backend), site)("a fixture prompt", max_new_tokens=2)
                self.assertIs(caught.exception.__cause__, error)
                self.assertEqual(len(model.calls), 1, "generate is called once, never retried")
                records = self._records()[before:]
                self.assertEqual([(r["backend_ok"], r["error_category"]) for r in records], [(False, kind)])
                self.assertEqual({k: records[0]["attention"][k] for k in ("attention_implementation", "pinned")},
                                 {"attention_implementation": "sdpa", "pinned": True})
                self.assertEqual(self._telemetry("generation_failure")[-1]["kind"], kind)
        # any other failure is raised unchanged, recorded under its own type
        model = _Model()
        model.fail = ValueError("fixture failure")
        with self._resident(model, "base"), self.assertRaises(ValueError):
            self._wrapper("local_auditor").call_local("a fixture prompt", max_new_tokens=2)
        self.assertEqual(self._records()[-1]["error_category"], "ValueError")

    def test_a_prompt_over_the_context_is_refused_and_recorded_never_truncated(self):
        for site, backend, mode in (("call_local", "local_producer", "final"), ("call_qwen", "qwen_local", "base")):
            model = _Model(context=10)
            with self._resident(model, mode):
                wrapper = self._wrapper(backend)
                wrapper._cost_doc_id = "doc-over"
                result = getattr(wrapper, site)("one two three four five six seven eight", max_new_tokens=4)
            self.assertFalse(result.ok)
            self.assertTrue(result.error.startswith("prompt_over_context"), result.error)
            self.assertEqual(model.calls, [], "an over-context prompt is never generated")
            record = self._records()[-1]
            self.assertEqual((record["backend_ok"], record["error_category"]), (False, "prompt_over_context"))
            self.assertEqual(record["context"], {"prompt_tokens": 8, "max_new_tokens": 4, "model_context": 10,
                                                 "over_context": True})
            self.assertNotIn("attention", record)
            event = self._telemetry("prompt_over_context")[-1]
            self.assertEqual({k: event[k] for k in ("doc_id", "prompt_tokens", "max_new_tokens", "model_context")},
                             {"doc_id": "doc-over", "prompt_tokens": 8, "max_new_tokens": 4, "model_context": 10})
        # exactly at the context it fits: prompt plus allowance equal to the positions
        model = _Model(context=12)
        with self._resident(model):
            self.assertTrue(self._wrapper("local_producer").call_local(
                "one two three four five six seven eight", max_new_tokens=4).ok)
        self.assertEqual(len(model.calls), 1)


def _pin_that_pins_nothing(original):
    """The per-call pin that records the memory-efficient backend but never pins it."""
    @contextlib.contextmanager
    def pin(model, decision=None):
        yield dict({k: v for k, v in PINNED.items() if k not in ONE_SHOT}, attention_decision=decision)
    return pin


def _attention_without_its_decision(original):
    """The setting without the rule that sdpa needs its recorded decision."""
    def setting(environ=None):
        environ = os.environ if environ is None else environ
        value = environ.get(final_models.PRODUCER_ATTENTION_ENV) or "eager"
        return dict(attention_implementation=value, sdpa_backend=None,
                    attention_decision=environ.get(final_models.PRODUCER_ATTENTION_DECISION_ENV))
    return setting


def _prefill_without_its_decision(original):
    """The prefill rule taking one-shot or any chunk size as asked, without its decision."""
    def setting(chunk=None, decision=None):
        if chunk == "one_shot":
            return dict(prefill="one_shot", prefill_chunk_tokens=None, prefill_decision=decision)
        return original(None if decision is None else chunk, decision)
    return setting


def _always_one_shot(original):
    """The shared generate helper that never chunks, whatever the call's prefill says."""
    def generate(model, inputs, **kw):
        return original(model, inputs, **dict(kw, prefill=dict(ONE_SHOT)))
    return generate


def _prefill_leaving_one_token(original):
    """Chunked prefill that leaves one prompt token to generate(), not two (D-061 item 3)."""
    def prefill(model, input_ids, chunk_tokens, *, cache=None):
        torch = _torch()
        return original(model, torch.cat([input_ids, input_ids[:, -1:]], dim=1), chunk_tokens, cache=cache)
    return prefill


# Neutralise, fail, restore, pass: each entry names a check, the function it holds and a mutant
# built from the original; prove_neutralizations() runs the check, then with the mutant in
# place (it must fail and the mutant must have been called), then restored.
NEUTRALIZATIONS = [
    ("test_the_producer_attention_defaults_to_eager_and_sdpa_needs_a_decision", final_models,
     "producer_attention", _attention_without_its_decision),
    ("test_the_producer_prefill_is_chunked_and_one_shot_needs_a_decision", final_models,
     "prefill_setting", _prefill_without_its_decision),
    ("test_the_classifier_stays_eager_as_its_runtime_contract_says", final_models, "load_attention",
     lambda original: (lambda role, spec=None: "sdpa")),
    ("test_final_models_loads_the_producer_with_its_settings_and_the_classifier_eager", final_models,
     "load_attention", lambda original: (lambda role, spec=None: "sdpa")),
    ("test_load_qwen_names_sdpa_on_every_load", None, "LOCAL_ATTENTION", None),
    ("test_every_local_call_runs_its_attention_and_prefill_and_records_them", final_models, "pinned_attention",
     _pin_that_pins_nothing),
    ("test_a_producer_call_in_chunks_replies_as_one_shot_on_a_tiny_cpu_model", final_models,
     "generate_with_prefill", _always_one_shot),
    ("test_a_producer_call_in_chunks_replies_as_one_shot_on_a_tiny_cpu_model", final_models,
     "chunked_prefill", _prefill_leaving_one_token),
    ("test_out_of_memory_and_a_refused_kernel_are_named_failures_never_retried", final_models,
     "named_generation_failure", lambda original: (lambda exc: None)),
    ("test_a_prompt_over_the_context_is_refused_and_recorded_never_truncated", final_models,
     "context_record", lambda original: (lambda model, prompt_tokens, max_new_tokens: dict(
         original(model, prompt_tokens, max_new_tokens), over_context=False))),
]


def _single(name):
    result = unittest.TestResult()
    LocalAttentionChecks(name).run(result)
    return result.wasSuccessful() and not result.skipped


def prove_neutralizations():
    """{passed, proofs}: every NEUTRALIZATIONS entry passes, fails with its mutant in place
    (which was called, or for a constant, read), and passes again restored."""
    import agent_wrapper
    proofs = []
    for name, owner, attribute, mutant in NEUTRALIZATIONS:
        invocations = []
        if owner is None:
            # a constant: _load_qwen's attention set to the library default's other choice
            patcher = mock.patch.object(agent_wrapper, attribute, "eager")
            owner_name = "agent_wrapper"
        else:
            replacement = mutant(getattr(owner, attribute))

            def counted(*args, _replacement=replacement, **kwargs):
                invocations.append(1)
                return _replacement(*args, **kwargs)
            patcher = mock.patch.object(owner, attribute, counted)
            owner_name = owner.__name__
        before = _single(name)
        with patcher:
            failed = not _single(name)
        after = _single(name)
        called = bool(invocations) if owner is not None else True
        proofs.append({"check": name, "neutralized": owner_name + "." + attribute, "baseline_pass": before,
                       "neutralized_fail": failed and called, "restored_pass": after,
                       "mutated_branch_invocations": len(invocations) if owner is not None else None})
    return {"passed": all(p["baseline_pass"] and p["neutralized_fail"] and p["restored_pass"] for p in proofs),
            "proofs": proofs}


def check():
    try:
        _torch()
        import transformers  # noqa: F401  the tiny CPU model's classes
    except ImportError as exc:
        return ("FAIL", "torch and transformers are needed for the sdpa switches and the tiny CPU model: " + str(exc))
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(LocalAttentionChecks).run(result)
    problems = result.failures + result.errors
    if problems:
        lines = problems[0][1].strip().splitlines()
        return ("FAIL", "%d failures/errors; first: %s" % (len(problems), lines[-1]))
    proofs = prove_neutralizations()
    if not proofs["passed"]:
        bad = [p["check"] + " (" + p["neutralized"] + ")" for p in proofs["proofs"]
               if not (p["baseline_pass"] and p["neutralized_fail"] and p["restored_pass"])]
        return ("FAIL", "a neutralise, fail, restore, pass proof did not hold: " + ", ".join(bad))
    return ("PASS", "%d cases and %d neutralise/fail/restore/pass proofs: the producer's attention is "
            "eager by default and sdpa only with a recorded decision (D-060); its prefill is chunked at "
            "512 tokens under D-061 and one-shot or another size only with a recorded decision; "
            "final_models loads the producer with both and the Auditor896 classifier eager (its runtime "
            "contract); _load_qwen names sdpa on every load; every producer call runs eager through the "
            "one shared generate helper with its sealed prefill, every _load_qwen call pinned to the "
            "memory-efficient sdpa backend on CUDA in one shot, each recorded; a producer call of three "
            "chunks and the 2-token tail replies byte for byte as one-shot on a tiny CPU model; out of "
            "memory or a refused kernel is one named failure, never retried; a prompt over the context is "
            "refused and recorded, never truncated (D-058, D-061)"
            % (result.testsRun, len(proofs["proofs"])))


if __name__ == "__main__":
    if sys.argv[1:] == ["--prove"]:
        receipt = prove_neutralizations()
        print(json.dumps(receipt, indent=2))
        sys.exit(0 if receipt["passed"] else 1)
    print(check())
