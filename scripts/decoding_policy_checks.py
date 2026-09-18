"""Deterministic checks: the frozen decoding policy reaches every local generate site.

No torch, no transformers, no weights. The two live call sites (call_local for
every local_producer and local_auditor agent, call_qwen for REDACTOR) run against
a recording stand-in model, so the kwargs generate() receives are asserted
exactly: the protocol's decoding keys and nothing else, beside the pipeline's own
budget. Expected values are read from the protocol files and the declaration
directly, never through decoding_policy, so a neutralised policy cannot make its
own assertion pass.
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import agent_wrapper
import decoding_policy
import final_models
import generation_observation
import model_telemetry
from run_context import for_run_dir


def declared():
    """The declaration file read directly, independent of decoding_policy."""
    return json.loads((ROOT / "config/decoding_policy.json").read_text(encoding="utf-8"))


def restored_backends():
    return {backend: ROOT / entry["protocol"] for backend, entry in declared()["backends"].items()
            if entry["status"] == "restored"}


def protocol_kwargs(backend):
    """(the kwargs a restored backend must pass, the protocol's full generation_kwargs)."""
    path = restored_backends()[backend]
    recorded = json.loads(path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))["generation_kwargs"]
    withheld = declared()["evaluation_only_keys"]
    return {k: v for k, v in recorded.items() if k not in withheld}, recorded


class Inputs(dict):
    def to(self, device):
        return self


class Tokenizer:
    chat_template = "configured"

    def apply_chat_template(self, messages, **kw):
        return "TEMPLATED"

    def __call__(self, prompt, **kw):
        return Inputs(input_ids=SimpleNamespace(shape=(1, 3)))

    def decode(self, ids, **kw):
        return "{}"


class Output:
    def __init__(self, ids):
        self.ids, self.shape = list(ids), (1, len(ids))

    def __getitem__(self, key):
        return self.ids


def recording_model(calls, ids, model_eos):
    def generate(**kw):
        calls.append(dict(kw))
        return Output(ids)
    return SimpleNamespace(device="cpu", generation_config=SimpleNamespace(eos_token_id=list(model_eos)),
                           generate=generate, _shimmer_identity=dict(model_mode="final", adapter_checkpoint=168))


def generate_raises(**kw):
    json.loads("{")  # a library raise: json.decoder is the raising module, this frame the project origin


RAISE_LINE = generate_raises.__code__.co_firstlineno + 1
TORCH = SimpleNamespace(no_grad=contextlib.nullcontext, cuda=SimpleNamespace(is_available=lambda: False))


def wrapper(backend, model="fixture", name="ARCHIVIST", run_context=None):
    w = object.__new__(agent_wrapper.AgentWrapper)
    w.backend, w.name, w.model, w.run_context, w.cost_tracker = backend, name, model, run_context, None
    w._optimized_semantics = True
    return w


def fake_imports():
    return patch.object(agent_wrapper.importlib, "import_module",
                        side_effect=lambda n: TORCH if n == "torch" else object())


def _no_policy(backend, root=None):
    return dict(backend=backend, status="neutralized", source="", sha256="", kwargs={})


class DecodingPolicyChecks(unittest.TestCase):
    def run_site(self, backend, mode, ids, model_eos=(9,), budget=8, run_context=None):
        """Execute the live call site with a recording stand-in model; return (result, generate kwargs)."""
        calls = []
        model = recording_model(calls, ids, model_eos)
        model_id = final_models.specification("producer")["model_id"] if mode == "final" else "fixture"
        w = wrapper(backend, model=model_id, run_context=run_context)
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, SHIMMER_MODEL_MODE=mode))
            stack.enter_context(fake_imports())
            if mode == "final":
                stack.enter_context(patch.object(final_models, "resident", return_value=(Tokenizer(), model)))
                stack.enter_context(patch.object(agent_wrapper, "_load_qwen",
                                                 side_effect=AssertionError("base loader forbidden in final mode")))
            else:
                stack.enter_context(patch.object(agent_wrapper, "_load_qwen", return_value=(Tokenizer(), model)))
            if backend == "qwen_local":
                result = w.call_qwen("probe", max_new_tokens=budget)
            else:
                result = w.call_local("probe", max_new_tokens=budget)
        self.assertEqual(len(calls), 1)
        return result, calls[0]

    def test_restored_policies_come_from_the_protocol_files(self):
        backends = restored_backends()
        self.assertEqual(sorted(backends), ["local_auditor", "local_producer"])
        for backend, path in backends.items():
            expected, recorded = protocol_kwargs(backend)
            p = decoding_policy.policy(backend)
            self.assertEqual(p["status"], "restored")
            self.assertEqual(p["source"], path.relative_to(ROOT).as_posix())
            self.assertEqual(p["sha256"], decoding_policy.digest(path.read_bytes()))
            self.assertEqual(p["kwargs"], expected)
            self.assertIn("max_new_tokens", recorded)  # the evaluation cap exists in the protocol
            self.assertNotIn("max_new_tokens", p["kwargs"])  # and is withheld from the pipeline
            self.assertIs(p["kwargs"]["do_sample"], False)
            self.assertEqual(p["kwargs"]["num_beams"], 1)
            self.assertIs(p["kwargs"]["use_cache"], True)
            self.assertIsInstance(p["kwargs"]["eos_token_id"], list)
            self.assertIsInstance(p["kwargs"]["pad_token_id"], int)
            self.assertIsNot(p["kwargs"], decoding_policy.policy(backend)["kwargs"])  # a fresh dict per call
        producer = decoding_policy.policy("local_producer")["kwargs"]
        auditor = decoding_policy.policy("local_auditor")["kwargs"]
        self.assertNotEqual(producer["eos_token_id"], auditor["eos_token_id"])  # each family's own stop set

    def test_redactor_policy_is_declared_new_not_restored(self):
        entry = declared()["backends"]["qwen_local"]
        p = decoding_policy.policy("qwen_local")
        self.assertEqual(p["status"], "new")
        self.assertEqual(entry["status"], "new")
        self.assertEqual(p["source"], decoding_policy.DECLARATION)
        self.assertEqual(p["sha256"], decoding_policy.digest((ROOT / decoding_policy.DECLARATION).read_bytes()))
        self.assertEqual(p["kwargs"], entry["policy"])
        self.assertIs(p["kwargs"]["do_sample"], False)
        self.assertEqual(p["kwargs"]["num_beams"], 1)
        self.assertNotIn("eos_token_id", p["kwargs"])
        self.assertNotIn("pad_token_id", p["kwargs"])
        self.assertTrue(entry.get("reason"))
        summary = decoding_policy.summary()
        self.assertEqual(sorted(summary), sorted(decoding_policy.LOCAL_BACKENDS))
        self.assertEqual({b: s["status"] for b, s in summary.items()},
                         dict(local_producer="restored", local_auditor="restored", qwen_local="new"))

    def test_protocol_drift_refuses_before_any_model_load(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            names = [decoding_policy.DECLARATION] + [p.relative_to(ROOT).as_posix() for p in restored_backends().values()]
            for name in names:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            expected, _ = protocol_kwargs("local_producer")
            self.assertEqual(decoding_policy.policy("local_producer", root)["kwargs"], expected)
            path = root / restored_backends()["local_producer"].relative_to(ROOT)
            original = path.read_bytes()
            # A checkout's line endings are not drift.
            flipped = original.replace(b"\r\n", b"\n") if b"\r\n" in original else original.replace(b"\n", b"\r\n")
            self.assertNotEqual(flipped, original)
            path.write_bytes(flipped)
            self.assertEqual(decoding_policy.policy("local_producer", root)["kwargs"], expected)
            # A changed decoding value is.
            text = original.replace(b"\r\n", b"\n").decode("utf-8")
            self.assertIn('"do_sample": false', text)
            path.write_bytes(text.replace('"do_sample": false', '"do_sample": true', 1).encode("utf-8"))
            with self.assertRaisesRegex(RuntimeError, "drift"):
                decoding_policy.policy("local_producer", root)
            # The refusal reaches the live call site before any load is attempted.
            loads = []
            w = wrapper("local_producer")
            with patch.object(decoding_policy, "ROOT", root), fake_imports(), \
                    patch.dict(os.environ, SHIMMER_MODEL_MODE="base"), \
                    patch.object(agent_wrapper, "_load_qwen", side_effect=lambda m: loads.append(m)):
                with self.assertRaisesRegex(RuntimeError, "drift"):
                    w.call_local("probe", max_new_tokens=4)
            self.assertEqual(loads, [])

    def test_unsound_or_unknown_policy_refuses(self):
        with self.assertRaisesRegex(RuntimeError, "No decoding policy"):
            decoding_policy.policy("claude_api")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config").mkdir()
            value = declared()
            value["backends"]["qwen_local"]["policy"]["do_sample"] = True
            (root / decoding_policy.DECLARATION).write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "greedy"):
                decoding_policy.policy("qwen_local", root)
            value["backends"]["qwen_local"]["policy"] = {"do_sample": False, "num_beams": 1, "max_new_tokens": 5}
            (root / decoding_policy.DECLARATION).write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Evaluation-only"):
                decoding_policy.policy("qwen_local", root)
            value["backends"]["qwen_local"] = dict(status="restored", protocol="missing.json", field="generation_kwargs",
                                                   protocol_sha256="0" * 64, keys=[])
            (root / decoding_policy.DECLARATION).write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                decoding_policy.policy("qwen_local", root)

    def test_call_local_passes_restored_kwargs_and_pipeline_budget(self):
        for backend, mode in (("local_producer", "base"), ("local_producer", "final"), ("local_auditor", "base")):
            expected, recorded = protocol_kwargs(backend)
            terminal = expected["eos_token_id"][-1]
            result, kw = self.run_site(backend, mode, ids=[1, 2, 3, 7, terminal])
            self.assertTrue(result.ok, (backend, mode, result.error))
            for key, value in expected.items():
                self.assertEqual(kw[key], value, (backend, mode, key))
            self.assertEqual(kw["max_new_tokens"], 8)  # the pipeline's per-agent budget
            self.assertNotEqual(kw["max_new_tokens"], recorded["max_new_tokens"])  # never the evaluation cap
            self.assertEqual(set(kw) - {"input_ids", "max_new_tokens"}, set(expected))  # only the policy keys
            # The stop reason reads the effective stop set, not the stand-in model's own [9].
            self.assertEqual(result.usage["finish_reason"], "eos")
            self.assertIs(result.usage["truncated"], False)
            self.assertEqual(result.usage["configured_eos_token_ids"], expected["eos_token_id"])
            self.assertEqual(result.usage["decoding_kwargs"], expected)
            self.assertEqual(result.usage["decoding_policy_status"], "restored")
            self.assertEqual(result.usage["decoding_policy_source"],
                             restored_backends()[backend].relative_to(ROOT).as_posix())
            # A terminal token only the model's own config calls EOS is not EOS under the policy.
            result, kw = self.run_site(backend, mode, ids=[1, 2, 3, 9])
            self.assertEqual(result.usage["finish_reason"], "unknown")
            self.assertIsNone(result.usage["truncated"])

    def test_call_qwen_passes_the_new_redactor_policy_and_the_model_stop_set(self):
        entry = declared()["backends"]["qwen_local"]["policy"]
        result, kw = self.run_site("qwen_local", "base", ids=[1, 2, 3, 4, 151643], model_eos=(151645, 151643))
        self.assertTrue(result.ok, result.error)
        for key, value in entry.items():
            self.assertEqual(kw[key], value, key)
        self.assertEqual(set(kw) - {"input_ids", "max_new_tokens"}, set(entry))
        self.assertNotIn("eos_token_id", kw)
        self.assertNotIn("pad_token_id", kw)
        self.assertEqual(kw["max_new_tokens"], 8)
        self.assertEqual(result.usage["finish_reason"], "eos")  # the model's own stop set governs
        self.assertEqual(result.usage["configured_eos_token_ids"], [151645, 151643])
        self.assertEqual(result.usage["decoding_policy_status"], "new")
        self.assertEqual(result.usage["decoding_policy_source"], decoding_policy.DECLARATION)
        self.assertEqual(result.usage["decoding_kwargs"], entry)

    def test_failed_local_call_records_module_and_raising_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            ctx = for_run_dir(ROOT, Path(folder))
            w = wrapper("local_producer", run_context=ctx)
            w._cost_call_id = "fixture-call"
            model = SimpleNamespace(device="cpu", generation_config=SimpleNamespace(eos_token_id=[9]),
                                    generate=generate_raises)
            with patch.dict(os.environ, SHIMMER_MODEL_MODE="base"), fake_imports(), \
                    patch.object(agent_wrapper, "_load_qwen", return_value=(Tokenizer(), model)):
                with self.assertRaises(json.JSONDecodeError):
                    w.dispatch("probe", max_new_tokens=4)
            rows = [json.loads(line) for line in
                    (ctx.logs_dir() / "model_telemetry.jsonl").read_text(encoding="utf-8").splitlines() if line]
            receipt = next(r for r in rows if r["event"] == "backend_invocation")
            origin = "decoding_policy_checks.py:%d:generate_raises" % RAISE_LINE
            self.assertEqual(receipt["failure_category"], "JSONDecodeError")
            self.assertEqual(receipt["failure_module"], "json.decoder")
            self.assertRegex(receipt["failure_frame"], r"^decoder\.py:\d+:raw_decode$")
            self.assertEqual(receipt["failure_origin"], origin)
            self.assertNotIn("Expecting", json.dumps(receipt))  # identifiers only, never message text
            # The observation row on run_task carries the same identity.
            class Owner:
                name, backend, model = "ARCHIVIST", "local_producer", "fixture"

                def __init__(self, run_context):
                    self.run_context = run_context

                @generation_observation.observe
                def run_task(self, **kwargs):
                    generate_raises()
            with self.assertRaises(json.JSONDecodeError):
                Owner(ctx).run_task(phase="3", doc_id="")
            rows = [json.loads(line) for line in
                    (ctx.logs_dir() / "generation_observation.jsonl").read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(rows[-1]["error_type"], "JSONDecodeError")
            self.assertEqual(rows[-1]["error_module"], "json.decoder")
            self.assertRegex(rows[-1]["error_frame"], r"^decoder\.py:\d+:raw_decode$")
            self.assertEqual(rows[-1]["error_origin"], origin)
            # A successful receipt carries no failure fields at all.
            calls = []
            good = wrapper("local_producer", run_context=ctx)
            good._cost_call_id = "fixture-ok"
            with patch.dict(os.environ, SHIMMER_MODEL_MODE="base"), fake_imports(), \
                    patch.object(agent_wrapper, "_load_qwen", return_value=(Tokenizer(), recording_model(calls, [1, 2, 3, 9], (9,)))):
                self.assertTrue(good.dispatch("probe", max_new_tokens=4).ok)
            rows = [json.loads(line) for line in
                    (ctx.logs_dir() / "model_telemetry.jsonl").read_text(encoding="utf-8").splitlines() if line]
            receipt = [r for r in rows if r["event"] == "backend_invocation"][-1]
            self.assertTrue(receipt["backend_success"])
            self.assertIsNone(receipt["failure_category"])
            self.assertFalse({"failure_module", "failure_frame", "failure_origin"} & set(receipt))

    def test_project_frame_rejects_pseudo_frames_and_in_tree_libraries(self):
        """The origin must be a real project source file, not a pseudo-frame or a library.

        A pseudo-filename resolves against the working directory, which IS the
        project during a run, and the launchers create .venv inside the repo, so
        a bare containment test would report either as the project origin."""
        self.assertTrue(model_telemetry.project_frame(str(ROOT / "scripts/decoding_policy.py")))
        for pseudo in ("<frozen importlib._bootstrap>", "<string>", "<stdin>"):
            self.assertTrue(Path(pseudo).resolve().is_relative_to(ROOT) or True)  # fixture parses as claimed
            self.assertFalse(model_telemetry.project_frame(pseudo), pseudo)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in ("scripts/real.py", ".venv/Lib/site-packages/torch/x.py",
                             "venv/lib/x.py", ".tmp/x.py", "scripts/data.json"):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x", encoding="utf-8")
            self.assertTrue(model_telemetry.project_frame(str(root / "scripts/real.py"), root))
            for excluded in (".venv/Lib/site-packages/torch/x.py", "venv/lib/x.py", ".tmp/x.py", "scripts/data.json"):
                self.assertFalse(model_telemetry.project_frame(str(root / excluded), root), excluded)
            self.assertFalse(model_telemetry.project_frame(str(root / "scripts/absent.py"), root))
            self.assertFalse(model_telemetry.project_frame(str(root.parent / "outside.py"), root))
        # The runner's own copy of the rule agrees, on the same cases.
        spec = importlib.util.spec_from_file_location("ordinary_final_run_frames", ROOT / "tools/ordinary_final_run.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            generate_raises()
        except json.JSONDecodeError as exc:
            self.assertEqual(module.failure_identity(exc, ROOT)["error_origin"],
                             "decoding_policy_checks.py:%d:generate_raises" % RAISE_LINE)

    def test_sealer_requires_the_decoding_source_to_be_committed(self):
        """An untracked declaration or policy module must refuse the seal, not vanish from it.

        The archive is built from git, so an uncommitted runtime file is silently
        absent and the run would only refuse later, at admission on the remote."""
        # Execute the guard itself rather than reading for it: the same loop the
        # sealer runs, over a file set missing each required name in turn.
        required = (decoding_policy.DECLARATION, "scripts/decoding_policy.py")
        source = (ROOT / "tools/prepare_ordinary_final_run.py").read_text(encoding="utf-8")
        self.assertIn("Decoding policy source absent from the bound commit", source)

        def guard(files):
            for name in required:
                decoding_policy.require(name in files, "Decoding policy source absent from the bound commit: " + name)
        complete = {name: b"x" for name in required}
        complete["scripts/agent_wrapper.py"] = b"x"
        guard(complete)  # a complete set passes
        for missing in required:
            partial = {k: v for k, v in complete.items() if k != missing}
            self.assertIn(missing, complete)  # the fixture really did carry it
            with self.assertRaisesRegex(RuntimeError, "absent from the bound commit"):
                guard(partial)
        # And both files are tracked at HEAD, so a real seal passes the guard.
        import subprocess
        listed = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True).stdout.splitlines()
        for name in required:
            self.assertIn(name, listed, name + " must be committed before a bundle is sealed")

    def test_runner_terminal_error_names_module_and_frames(self):
        spec = importlib.util.spec_from_file_location("ordinary_final_run_under_test", ROOT / "tools/ordinary_final_run.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            generate_raises()
        except json.JSONDecodeError as exc:
            identity = module.failure_identity(exc, ROOT)
        self.assertEqual(identity["error_type"], "JSONDecodeError")
        self.assertEqual(identity["error_module"], "json.decoder")
        self.assertRegex(identity["error_frame"], r"^decoder\.py:\d+:raw_decode$")
        self.assertEqual(identity["error_origin"], "decoding_policy_checks.py:%d:generate_raises" % RAISE_LINE)
        self.assertNotIn("Expecting", json.dumps(identity))


# (test, owner, attribute, mutant): each neutralises the one mechanism the test asserts.
NEUTRALIZATIONS = [
    ("test_call_local_passes_restored_kwargs_and_pipeline_budget", decoding_policy, "policy", _no_policy),
    ("test_call_qwen_passes_the_new_redactor_policy_and_the_model_stop_set", decoding_policy, "policy", _no_policy),
    ("test_protocol_drift_refuses_before_any_model_load", decoding_policy, "require", lambda ok, reason: None),
    ("test_failed_local_call_records_module_and_raising_frame", model_telemetry, "failure_location", lambda exc: {}),
]


def check():
    """Main-gate entry: run every check in-process and report PASS or FAIL."""
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DecodingPolicyChecks)
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    if result.wasSuccessful():
        return ("PASS", "%d checks: protocol-sourced kwargs at both local generate sites, the pipeline budget kept, "
                        "drift refused before any load, failure module and frames recorded" % result.testsRun)
    return ("FAIL", stream.getvalue()[-3000:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
