"""Proofs of the vLLM comparison (#217), on the laptop with no vLLM and no model.

  py -3.12 -X utf8 benchmark/baselines/vllm_replay_checks.py

1. The port: the vLLM logits processor (vllm_constraint.ShimmerConstraint) gives every row of a
   batch the very mask the transformers ContractProcessor gives the same request alone, step by
   step, on frozen DEV replies of checkpoint 168 with the real tokenizer, with the rows reordered
   every step, a request joining late and partial prefill rows in between. Neutralised (the
   bookkeeping drops the token fed at a row), it fails.
2. The file: load_prompts counts one row per prompt per arm, refuses a changed prompt, and
   replay_prompts.load_prompts hands the file to it (the sealer's count).
3. The pass: run() with the current engine and the child replaced writes one reply record per
   prompt per arm in one folder, starts the child from venv_aux beside the prompts, with
   VLLM_BATCH_INVARIANT=1 and offline, no SHIMMER_ or credential variable, and its figures count
   identity, validity and speed. Neutralised (the child's environment passes everything), it fails.
4. The labels: macro-F1 of identical labels is 1 and its lower bound 1; one changed label lowers it.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT / "scripts"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import vllm_constraint  # noqa: E402
import vllm_replay  # noqa: E402

DEV = ROOT / "docs/fix/producer_tuning_v3_run/downloaded/evidence/checkpoint-168/full_dev.jsonl"
TOKENIZER = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"
EOS = [151645]
RESUME_AT = 4   # the step at which request 0 is preempted and resumed
RESUMED_SLOT = 7   # the slot it comes back in


def _tok():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)


def _dev_rows(n):
    rows = []
    for line in DEV.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if not row.get("truncated"):
                rows.append(row)
        if len(rows) == n:
            break
    return rows


class Ctx:
    def __init__(self, torch, mapping, pos, fed):
        self.expanded_idx_mapping = torch.tensor(mapping)
        self.pos = torch.tensor(pos)
        self.input_ids = torch.tensor(fed)


def _drive(torch, tok, rows, neutralise=False):
    """Every request's masks as the vLLM processor makes them in a shared batch, and as the
    transformers processor makes them alone; returns the number of steps that differ."""
    import contract_decoding
    processor = vllm_constraint.ShimmerConstraint()
    processor.path = TOKENIZER
    vllm_constraint._TOKENIZERS[TOKENIZER] = tok
    width = len(tok) + 7          # vLLM's padded vocabulary is wider than the tokenizer
    requests = []
    for slot, row in enumerate(rows):
        prompt_ids = tok(row["prompt"], add_special_tokens=False)["input_ids"]
        reply = list(row["output_token_ids"])
        alone = contract_decoding.for_prompt(row["prompt"], tok, len(prompt_ids), EOS)
        params = types.SimpleNamespace(extra_args={vllm_constraint.KEY: {
            "prompt": row["prompt"], "agent": None, "prompt_tokens": len(prompt_ids), "eos": EOS, "key": str(slot)}})
        requests.append(dict(slot=slot, params=params, prompt=prompt_ids, reply=reply, alone=alone, step=-2, joined=False))
    if neutralise:
        original = vllm_constraint.Slot.follow
        vllm_constraint.Slot.follow = lambda self, position, fed: self.ids
    differ, step = 0, 0
    try:
        while any(r["step"] < len(r["reply"]) for r in requests):
            live = []
            for r in requests:
                if r["step"] >= len(r["reply"]):
                    continue
                if r["slot"] == 1 and step < 3:      # a request joining late
                    continue
                if not r["joined"]:
                    processor.add_request(r["slot"], r["params"])
                    r["joined"] = True
                live.append(r)
            live = live[::-1] if step % 2 else live   # rows reordered every step
            for r in live:
                if r["slot"] == 0 and r["step"] == RESUME_AT and not r.get("resumed"):
                    # Preempted, then resumed: Model Runner V2 adds the request again, in another
                    # slot, and recomputes the prompt and the reply so far in chunks; none of
                    # those rows is sampled, so none may be changed.
                    processor.add_request(RESUMED_SLOT, r["params"])
                    r["slot"] = RESUMED_SLOT
                    k = r["step"]
                    rows_pos = [len(r["prompt"]) - 1 + g for g in range(0, k)]
                    rows_fed = [r["prompt"][-1] if g == 0 else r["reply"][g - 1] for g in range(0, k)]
                    logits = torch.randn(len(rows_pos), width)
                    before = logits.clone()
                    out = processor.apply(logits, Ctx(torch, [RESUMED_SLOT] * len(rows_pos), rows_pos, rows_fed))
                    differ += int(not torch.equal(out, before))
                    r["resumed"] = True
            mapping, pos, fed = [], [], []
            for r in live:
                if r["step"] == -2:                    # a partial prefill row first
                    mapping.append(r["slot"]); pos.append(len(r["prompt"]) // 2); fed.append(r["prompt"][len(r["prompt"]) // 2])
                else:
                    k = r["step"]
                    mapping.append(r["slot"]); pos.append(len(r["prompt"]) - 1 + k)
                    fed.append(r["prompt"][-1] if k == 0 else r["reply"][k - 1])
            logits = torch.randn(len(live), width)
            before = logits.clone()
            out = processor.apply(logits, Ctx(torch, mapping, pos, fed))
            for i, r in enumerate(live):
                if r["step"] == -2:
                    differ += int(not torch.equal(out[i], before[i]))
                    r["step"] = 0
                    continue
                k = r["step"]
                ids = torch.tensor([r["prompt"] + r["reply"][:k]])
                expected = r["alone"].processor(ids, before[i:i + 1])[0]
                differ += int(not torch.equal(out[i], expected))
                r["step"] += 1
            step += 1
    except RuntimeError:
        differ += 1
    finally:
        if neutralise:
            vllm_constraint.Slot.follow = original
    # Each request's counts, the resumed one's included, are an uninterrupted run's.
    for r in requests:
        differ += int(vllm_constraint.COUNTS.get(r["params"].extra_args[vllm_constraint.KEY]["key"]) != r["alone"].record)
    return differ


class PortProof(unittest.TestCase):
    def test_batched_rows_get_the_alone_mask(self):
        import torch
        torch.manual_seed(0)
        tok = _tok()
        self.assertEqual(_drive(torch, tok, _dev_rows(3)), 0)

    def test_neutralised_resume_handling_fails(self):
        """The rule before this fix: every add_request made a fresh Slot, so a resumed request lost
        its ids (its recomputation rows masked, then a raise)."""
        import torch
        torch.manual_seed(0)
        original = vllm_constraint.ShimmerConstraint.add_request

        def fresh(self, req_idx, sampling_params):
            args = (getattr(sampling_params, "extra_args", None) or {}).get(vllm_constraint.KEY)
            self.slots[int(req_idx)] = vllm_constraint.Slot(args, vllm_constraint.tokenizer(self.path)) if args else None
            return args is not None
        vllm_constraint.ShimmerConstraint.add_request = fresh
        try:
            self.assertGreater(_drive(torch, _tok(), _dev_rows(2)), 0)
        finally:
            vllm_constraint.ShimmerConstraint.add_request = original

    def test_neutralised_counts_on_resume_fail(self):
        """A resume that keeps the ids but starts a new record: the counts no longer add up."""
        import torch
        torch.manual_seed(0)
        original = vllm_constraint.ShimmerConstraint.add_request

        def recount(self, req_idx, sampling_params):
            args = (getattr(sampling_params, "extra_args", None) or {}).get(vllm_constraint.KEY)
            old = self.by_key.get(args["key"])
            slot = vllm_constraint.Slot(args, vllm_constraint.tokenizer(self.path))
            if old is not None:
                slot.ids, slot.started = old.ids, old.started
            self.by_key[args["key"]] = self.slots[int(req_idx)] = slot
            return True
        vllm_constraint.ShimmerConstraint.add_request = recount
        try:
            self.assertGreater(_drive(torch, _tok(), _dev_rows(2)), 0)
        finally:
            vllm_constraint.ShimmerConstraint.add_request = original

    def test_neutralised_bookkeeping_fails(self):
        import torch
        torch.manual_seed(0)
        self.assertGreater(_drive(torch, _tok(), _dev_rows(2), neutralise=True), 0)


def _file(folder, n=2, text="prompt"):
    import replay_prompts
    prompts = []
    for i in range(n):
        prompt = "%s %d" % (text, i)
        prompts.append({"prompt_id": "p%d" % i, "agent": "CITATION_RESOLVER", "prompt": prompt,
                        "prompt_sha256": vllm_replay._sha(prompt), "max_new_tokens": 8})
    value = {"schema": vllm_replay.SCHEMA, "batch": 4, "arms": list(vllm_replay.ARMS),
             "groups": [{"name": "plain", "kind": "plain", "current_path": "sdpa",
                         "file": {"schema": replay_prompts.SCHEMA, "prompt_count": n, "prompts": prompts}}]}
    value["prompt_count"] = len(vllm_replay.load_value(value))
    path = Path(folder) / "replay_prompts.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, value


class FileProof(unittest.TestCase):
    def test_count_and_dispatch(self):
        import replay_prompts
        with tempfile.TemporaryDirectory() as d:
            path, value = _file(d, 3)
            self.assertEqual(len(vllm_replay.load_prompts(path)), 9)
            self.assertEqual(len(replay_prompts.load_prompts(path)), 9)
            value["groups"][0]["file"]["prompts"][1]["prompt"] = "changed"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                vllm_replay.load_prompts(path)


NF4 = {"quantization_config": {"quant_method": "bitsandbytes", "bnb_4bit_quant_type": "nf4", "load_in_4bit": True,
                               "bnb_4bit_compute_dtype": "bfloat16"}}
SECRET_PROMPT = "prompt text that never leaves the instance"


class PassProof(unittest.TestCase):
    """run() with the current engine, the child, the eviction and the model paths replaced."""

    def _run(self, leak=False, runner=None, config=NF4, allowance=8, evict=None, dtype="bfloat16", folder=None,
             run_id=None, compute="bfloat16"):
        reply = '{"items":[{"resolved":"yes","source_document":"d"}]}'
        seen = {"order": []}

        def current(path, out, paths, texts, seconds, dtypes):
            import bare_model
            import reply_records
            value = json.loads(Path(path).read_text(encoding="utf-8"))
            context = bare_model.RunContext(out, "fake")
            rows = []
            for p in value["prompts"]:
                call = reply_records.write(context, agent="E", backend="local_producer", model_id="m", model_mode="x",
                                           payload=p["prompt"], payload_form="rendered_prompt", reply=reply, ok=True,
                                           error="", decoding={}, sensitive=True, phase="E", doc_id="")
                texts.setdefault(paths[0], {})[p["prompt_id"]] = reply
                rows.append({"prompt_id": p["prompt_id"], paths[0]: {"reply": {"sha256": vllm_replay._sha(reply)},
                                                                       "output_tokens": 4, "max_new_tokens": allowance,
                                                                       "call_id": call}})
            seconds[paths[0]] = 2.0
            dtypes["None"] = {"dtype": dtype, "compute_dtype": compute}
            (Path(out) / "replay_measurement.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
            seen["order"].append("current")
            return {"rows": rows}

        def fake_runner(argv, env, stdout, stderr, timeout, cwd):
            seen["order"].append("child")
            seen["argv"], seen["env"] = argv, env
            job = json.loads(Path(argv[argv.index("--job") + 1]).read_text(encoding="utf-8"))
            seen["job"] = job
            arms = {}
            for arm, text in (("vllm_b1", reply), ("vllm_batch", reply.replace("yes", "no"))):
                arms[arm] = {"seconds": 1.0, "output_tokens": 8,
                             "rows": {arm + ":" + p["prompt_id"]: {"text": text, "token_ids": [1], "output_tokens": 4,
                                                                    "finish_reason": "stop", "constraint": None}
                                      for p in job["prompts"]}}
            Path(argv[argv.index("--out") + 1]).write_text(json.dumps({"arms": arms, "error": None}), encoding="utf-8")
            return types.SimpleNamespace(returncode=0)

        def fake_evict():
            seen["order"].append("evict")
            return {"free_bytes": 22, "total_bytes": 24}

        with (contextlib.nullcontext(folder) if folder else tempfile.TemporaryDirectory()) as d:
            path, value = _file(d, 2, text=SECRET_PROMPT)
            base = Path(d) / "base"
            base.mkdir(exist_ok=True)
            (base / "config.json").write_text(json.dumps(config), encoding="utf-8")
            os.environ["SHIMMER_FAKE_SECRET"] = "x"
            original = vllm_replay.child_env
            if leak:
                vllm_replay.child_env = lambda python: dict(os.environ)
            try:
                result = vllm_replay.run(path, Path(d) / "evidence" / "b1" / (run_id or "vllm"), runner=runner or fake_runner,
                                         run_id=run_id,
                                         current=current, evict=evict or fake_evict, digest_for=lambda tok: "d" * 64,
                                         tokenizer_for=lambda b: (lambda text, add_special_tokens: {"input_ids": [1, 2]}),
                                         paths_for=lambda replay, group, prompts: (str(base), None, None))
            finally:
                vllm_replay.child_env = original
                os.environ.pop("SHIMMER_FAKE_SECRET", None)
            out = Path(d) / "evidence"
            files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
            leaked = [f for f in files if SECRET_PROMPT in (out / f).read_text(encoding="utf-8", errors="replace")]
            return result, files, leaked, seen, value

    def test_records_env_and_figures(self):
        result, files, leaked, seen, value = self._run()
        records = [f for f in files if f.startswith("b1/vllm/audit/model_replies/")]
        self.assertEqual(len(records), value["prompt_count"])
        self.assertEqual(Path(seen["argv"][0]).parts[-3:], ("venv_aux", "bin", "python"))
        env = seen["env"]
        self.assertEqual((env["VLLM_BATCH_INVARIANT"], env["HF_HUB_OFFLINE"], env["VLLM_USE_V2_MODEL_RUNNER"]), ("1", "1", "1"))
        self.assertFalse([k for k in env if k.startswith("SHIMMER_") or "KEY" in k or "TOKEN" in k])
        f = result["groups"]["plain"]["figures"]["CITATION_RESOLVER"]
        self.assertEqual(f["identical_to_current"], {"vllm_b1": 2, "vllm_batch": 0})
        self.assertEqual(f["batch_identical_to_alone"], 0)
        self.assertEqual(f["label_macro_f1_vs_current"]["vllm_b1"]["point"], 1.0)
        self.assertLess(f["label_macro_f1_vs_current"]["vllm_batch"]["point"], 1.0)
        arms = result["groups"]["plain"]["arms"]
        self.assertEqual((arms["current"]["seconds"], arms["vllm_b1"]["tokens_per_second"]), (2.0, 8.0))
        # D-608: the agreement in aggregate and each arm's specification.
        self.assertEqual((f["agreement_rate_with_current"], f["differing_from_current"], f["batch_agreement_rate"]),
                         ({"vllm_b1": 1.0, "vllm_batch": 0.0}, {"vllm_b1": 0, "vllm_batch": 2}, 0.0))
        spec = result["groups"]["plain"]["specification"]["current"]
        self.assertEqual((spec["engine"], spec["batch"], spec["quantisation"]["bnb_4bit_quant_type"]), ("transformers", 1, "nf4"))
        for key in ("platform", "python", "nvidia_smi", "decoding", "lora", "repetition_penalty", "seed"):
            self.assertIn(key, spec)

    def test_only_records_and_the_measurement_leave_and_no_prompt_text(self):
        """Item 1: under evidence only the reply records (hashes) and the measurement; the job,
        the results and the prompts stay in the working folder beside the bundle."""
        _, files, leaked, seen, _ = self._run()
        extra = [f for f in files if not (f.startswith("b1/vllm/audit/model_replies/") and f.endswith(".json"))
                 and f != "b1/vllm/replay_measurement.json"]
        self.assertEqual((extra, leaked), ([], []))
        self.assertNotIn("evidence", Path(seen["argv"][seen["argv"].index("--job") + 1]).parts)

    def test_neutralised_work_folder_leaks(self):
        original = vllm_replay.work_root
        vllm_replay.work_root = lambda prompts_path: Path(prompts_path).resolve().parent / "evidence" / "work"
        try:
            _, files, leaked, _, _ = self._run()
        finally:
            vllm_replay.work_root = original
        self.assertTrue(leaked)

    def test_eviction_before_the_child_and_the_allowance_from_the_current_engine(self):
        result, _, _, seen, _ = self._run(allowance=7)
        self.assertEqual(seen["order"], ["current", "evict", "child"])
        self.assertEqual({p["max_new_tokens"] for p in seen["job"]["prompts"]}, {7})
        self.assertEqual(result["groups"]["plain"]["gpu_before_child"], {"free_bytes": 22, "total_bytes": 24})
        self.assertEqual((seen["job"]["dtype"], seen["job"]["token_table_sha256"]), ("bfloat16", "d" * 64))

    def test_an_unrecorded_allowance_is_refused(self):
        with self.assertRaises(ValueError):
            self._run(allowance=None)

    def test_a_checkpoint_not_nf4_runs_no_child(self):
        result, _, _, seen, _ = self._run(config={"torch_dtype": "bfloat16"})
        self.assertNotIn("child", seen["order"])
        self.assertIn("NF4", result["groups"]["plain"]["child_error"])

    def test_a_missing_child_or_a_deadline_keeps_the_current_figures(self):
        import subprocess
        for exc in (FileNotFoundError("venv_aux"), subprocess.TimeoutExpired("python", 1)):
            def runner(*args, **kwargs):
                raise exc
            result, files, _, _, _ = self._run(runner=runner)
            self.assertIn("b1/vllm/replay_measurement.json", files)
            self.assertEqual(result["groups"]["plain"]["arms"]["current"]["seconds"], 2.0)
            self.assertTrue(result["groups"]["plain"]["child_error"])

    def test_a_float16_group_is_compared_in_float16(self):
        """The auditor path: float16 weights (transformers' 4-bit quantizer with no torch_dtype)
        under bfloat16 4-bit compute, which is the plugin's own: compared, vLLM given float16."""
        result, _, _, seen, _ = self._run(dtype="float16")
        self.assertIn("child", seen["order"])
        self.assertEqual(seen["job"]["dtype"], "float16")
        g = result["groups"]["plain"]
        self.assertEqual((g["current_dtype"], g["vllm_dtype"]), ({"dtype": "float16", "compute_dtype": "bfloat16"},
                                                                 {"dtype": "float16", "compute_dtype": "bfloat16"}))
        self.assertEqual((g["specification"]["current"]["dtype"], g["specification"]["current"]["compute_dtype"]),
                         ("float16", "bfloat16"))

    def test_neutralised_dtype_rule_refuses_float16(self):
        """The round-2 rule (model dtype must equal compute dtype) refused the auditor groups."""
        original = vllm_replay.dtype_refusal
        vllm_replay.dtype_refusal = lambda current, quant: (None if current["dtype"] == current["compute_dtype"]
                                                            else "refused")
        try:
            _, _, _, seen, _ = self._run(dtype="float16")
        finally:
            vllm_replay.dtype_refusal = original
        self.assertNotIn("child", seen["order"])

    def test_a_compute_dtype_the_plugin_cannot_run_is_refused(self):
        result, _, _, seen, _ = self._run(compute="float32")
        self.assertNotIn("child", seen["order"])
        g = result["groups"]["plain"]
        self.assertIn("not the plugin's bfloat16", g["child_error"])
        # Refused, so nothing was compared: not measured, and no difference claimed.
        self.assertIsNot(g["stability_finding"]["differs"], True)
        self.assertEqual({a["measured"] for a in g["agreement"].values()}, {False})
        self.assertEqual(g["agreement"]["vllm_b1"]["label_agreement_rate"], None)

    def test_neutralised_not_run_arm_claims_a_difference(self):
        """Neutralised (every arm counted as run), a refused group claims a difference."""
        original = vllm_replay.group_agreement
        vllm_replay.group_agreement = lambda rows, ran: original(rows, set(vllm_replay.ARMS[1:]))
        try:
            result, _, _, _, _ = self._run(compute="float32")
        finally:
            vllm_replay.group_agreement = original
        self.assertIs(result["groups"]["plain"]["stability_finding"]["differs"], True)

    def test_the_group_records_agreement_and_names_a_difference_a_finding(self):
        result, _, _, _, _ = self._run()
        g = result["groups"]["plain"]
        self.assertEqual(g["agreement"]["vllm_b1"]["label_agreement_rate"], 1.0)
        self.assertEqual(g["agreement"]["vllm_batch"]["label_agreement_rate"], 0.0)
        self.assertEqual(g["agreement"]["vllm_batch"]["byte_identical_rate"], 0.0)
        self.assertTrue(g["stability_finding"]["differs"])
        self.assertIn("never a failure", g["stability_finding"]["reading"])

    def test_two_passes_keep_their_own_work_folders(self):
        with tempfile.TemporaryDirectory() as d:
            first = self._run(folder=d, run_id="pass-a")
            second = self._run(folder=d, run_id="pass-b")
            work = Path(d) / vllm_replay.WORK
            self.assertEqual(sorted(p.name for p in work.iterdir()), ["pass-a", "pass-b"])
            self.assertEqual((first[0]["failures"], second[0]["failures"]), (0, 0))

    def test_neutralised_shared_work_folder_collides(self):
        original = vllm_replay.pass_folder
        with tempfile.TemporaryDirectory() as d:
            vllm_replay.pass_folder = lambda prompts_path, run_id: vllm_replay.work_root(prompts_path)
            try:
                self._run(folder=d, run_id="pass-a")
                with self.assertRaises(FileExistsError):
                    self._run(folder=d, run_id="pass-b")
            finally:
                vllm_replay.pass_folder = original

    def test_neutralised_environment_fails(self):
        _, _, _, seen, _ = self._run(leak=True)
        self.assertTrue([k for k in seen["env"] if k.startswith("SHIMMER_")])


class EvictProof(unittest.TestCase):
    """free_gpu empties final_models' resident cache and agent_wrapper's; neutralised, they stay."""

    def _fill(self):
        import agent_wrapper
        import final_models
        final_models._RESIDENTS["producer"] = object()
        agent_wrapper._QWEN_MODELS["fake/model"] = (object(), object())
        return final_models, agent_wrapper

    def test_free_gpu_evicts_both_caches(self):
        final_models, agent_wrapper = self._fill()
        vllm_replay.free_gpu()
        self.assertEqual((dict(final_models._RESIDENTS), dict(agent_wrapper._QWEN_MODELS)), ({}, {}))

    def test_neutralised_eviction_leaves_them(self):
        final_models, agent_wrapper = self._fill()
        try:
            original = final_models.release_reference_residency
            final_models.release_reference_residency = lambda: None
            evict = agent_wrapper._evict_generation_models
            agent_wrapper._evict_generation_models = lambda keep_model_id=None: None
            vllm_replay.free_gpu()
            self.assertTrue(final_models._RESIDENTS and agent_wrapper._QWEN_MODELS)
        finally:
            final_models.release_reference_residency = original
            agent_wrapper._evict_generation_models = evict
            final_models._RESIDENTS.clear()
            agent_wrapper._QWEN_MODELS.clear()


class TimingHookProof(unittest.TestCase):
    """The real replay_prompts.run with a fake backend whose prepare() takes LOAD seconds: the
    seconds= hook times the generation loop alone (no load), texts= is filled, dtypes= carries the
    model's dtypes, and the measurement with the hooks is the measurement without them."""

    LOAD = 0.6

    class Backend:
        def __init__(self):
            self.model = types.SimpleNamespace(dtype="torch.bfloat16", config=types.SimpleNamespace(
                quantization_config={"bnb_4bit_compute_dtype": "bfloat16"}))

        def prepare(self):
            import time
            time.sleep(TimingHookProof.LOAD)
            return {"model_id": "m", "digest": "d", "checkpoint": "tuned"}

        def count(self, prompt):
            return 3

        def max_context(self):
            return 10 ** 6

        def generate(self, prompt, attention, max_new_tokens, constraint=False, agent=None):
            return {"text": '{"items":[]}', "output_tokens": 2, "attention": attention, "prefill": None, "truncated": False}

    def _run(self, hooks):
        import decoding_policy
        import replay_prompts
        reader = {"decoding": decoding_policy.policy("local_producer"), "model_id": "m", "model_mode": "final",
                  "max_new_tokens": 8}
        with tempfile.TemporaryDirectory() as d:
            prompts = [{"prompt_id": "p%d" % i, "agent": "CITATION_RESOLVER", "prompt": "plain prompt %d" % i,
                        "prompt_sha256": vllm_replay._sha("plain prompt %d" % i), "max_new_tokens": 8} for i in range(3)]
            path = Path(d) / "replay_prompts.json"
            path.write_text(json.dumps({"schema": replay_prompts.SCHEMA, "prompt_count": 3, "prompts": prompts}), encoding="utf-8")
            result = replay_prompts.run(path, Path(d) / "out", paths=["sdpa"], backend=self.Backend(), reader=reader,
                                        run_id="fixed", **hooks)
        for key in ("finished_at",):
            result.pop(key, None)
        for row in result["rows"]:
            row["sdpa"].pop("call_id", None)
        return result

    def test_the_hooks_time_the_loop_fill_the_texts_and_change_nothing(self):
        texts, seconds, dtypes = {}, {}, {}
        hooked = self._run(dict(texts=texts, seconds=seconds, dtypes=dtypes))
        plain = self._run({})
        self.assertLess(seconds["sdpa"], self.LOAD)
        self.assertEqual(sorted(texts["sdpa"]), ["p0", "p1", "p2"])
        self.assertEqual(dtypes, {"None": {"dtype": "bfloat16", "compute_dtype": "bfloat16"}})
        self.assertEqual(hooked, plain)

    def test_neutralised_timing_origin_counts_the_load(self):
        import replay_prompts
        original = replay_prompts.timing_origin
        replay_prompts.timing_origin = lambda before_load, loop_start: before_load
        try:
            seconds = {}
            self._run(dict(seconds=seconds))
        finally:
            replay_prompts.timing_origin = original
        self.assertFalse(seconds["sdpa"] < self.LOAD)


class SecondRunProof(unittest.TestCase):
    """The two fixes after vllm-test-217b and the vLLM-only rerun against that run's measurement."""

    def test_the_aux_venv_bin_comes_first_on_the_childs_path(self):
        result, _, _, seen, _ = PassProof()._run()
        path = seen["env"]["PATH"].split(os.pathsep)
        self.assertEqual(Path(path[0]), Path(seen["argv"][0]).parent)

    def test_neutralised_path_leaves_the_venv_off(self):
        original = vllm_replay.child_env

        def old(base_python):
            env = {k: os.environ[k] for k in vllm_replay.ENV_KEPT if k in os.environ}
            env.update(VLLM_BATCH_INVARIANT="1", HF_HUB_OFFLINE="1", VLLM_USE_V2_MODEL_RUNNER="1")
            return env
        vllm_replay.child_env = old
        try:
            _, _, _, seen, _ = PassProof()._run()
        finally:
            vllm_replay.child_env = original
        self.assertNotEqual(Path(seen["env"].get("PATH", "").split(os.pathsep)[0]), Path(seen["argv"][0]).parent)

    def test_a_float32_producer_group_runs_in_float32(self):
        result, _, _, seen, _ = PassProof()._run(dtype="float32")
        self.assertIn("child", seen["order"])
        self.assertEqual(seen["job"]["dtype"], "float32")
        self.assertEqual(result["groups"]["plain"]["vllm_dtype"], {"dtype": "float32", "compute_dtype": "bfloat16"})

    def test_neutralised_float32_is_refused(self):
        original = vllm_replay.MODEL_DTYPES
        vllm_replay.MODEL_DTYPES = ("float16", "bfloat16")
        try:
            _, _, _, seen, _ = PassProof()._run(dtype="float32")
        finally:
            vllm_replay.MODEL_DTYPES = original
        self.assertNotIn("child", seen["order"])

    def _baseline_run(self, keep_texts=True, kept_text=None):
        """A first pass (both engines), then a vLLM-only pass built against its measurement."""
        first, _, _, _, value = PassProof()._run(run_id="first")
        reply = '{"items":[{"resolved":"yes","source_document":"d"}]}'
        prompts = value["groups"][0]["file"]["prompts"]
        texts = {vllm_replay._sha(reply): reply} if keep_texts else {}
        block = vllm_replay.baseline_block(first, "plain", prompts, texts)
        if kept_text is not None:   # a kept current text that does not parse
            block["texts"] = {pid: kept_text for pid in block["rows"]}
        second = dict(value, arms=list(vllm_replay.ARMS[1:]), groups=[dict(value["groups"][0], baseline=block)])
        second.pop("prompt_count", None)
        second["prompt_count"] = len(vllm_replay.load_value(second))
        seen = {"order": []}

        def no_current(*args, **kwargs):
            raise AssertionError("the current engine ran in a vLLM-only pass")

        def runner(argv, env, stdout, stderr, timeout, cwd):
            seen["order"].append("child")
            job = json.loads(Path(argv[argv.index("--job") + 1]).read_text(encoding="utf-8"))
            seen["allowances"] = {p["prompt_id"]: p["max_new_tokens"] for p in job["prompts"]}
            arms = {arm: {"seconds": 1.0, "output_tokens": 8,
                          "rows": {arm + ":" + p["prompt_id"]: {"text": reply, "token_ids": [1], "output_tokens": 4,
                                                                 "finish_reason": "stop", "constraint": None}
                                   for p in job["prompts"]}} for arm in vllm_replay.ARMS[1:]}
            Path(argv[argv.index("--out") + 1]).write_text(json.dumps({"arms": arms, "error": None}), encoding="utf-8")
            return types.SimpleNamespace(returncode=0)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "replay_prompts.json"
            path.write_text(json.dumps(second), encoding="utf-8")
            base = Path(d) / "base"
            base.mkdir()
            (base / "config.json").write_text(json.dumps(NF4), encoding="utf-8")
            out = Path(d) / "evidence" / "b1" / "vllm"
            result = vllm_replay.run(path, out, runner=runner, current=no_current, evict=lambda: None,
                                     digest_for=lambda tok: "d" * 64, run_id="second",
                                     tokenizer_for=lambda b: (lambda text, add_special_tokens: {"input_ids": [1, 2]}),
                                     paths_for=lambda replay, group, prompts: (str(base), None, None))
            records = len(list((out / "audit" / "model_replies").glob("*.json")))
        self.seen = seen
        return first, second, result, records

    def test_a_vllm_only_pass_compares_with_the_earlier_session(self):
        first, second, result, records = self._baseline_run()
        g = result["groups"]["plain"]
        self.assertEqual(records, second["prompt_count"])          # two arms per prompt, no current record
        self.assertEqual(records, 2 * len(second["groups"][0]["file"]["prompts"]))
        self.assertIn("cross-session", g["timing"])
        self.assertIn("first", g["timing"])
        self.assertEqual(g["arms"]["current"]["seconds"], first["groups"]["plain"]["arms"]["current"]["seconds"])
        self.assertEqual(g["agreement"]["vllm_b1"]["byte_identical"], 2)
        self.assertEqual(g["agreement"]["vllm_b1"]["label_agreement_rate"], 1.0)
        self.assertEqual((g["current_texts_kept"], g["current_labels_parsed"]), (2, 2))
        # vLLM is given the very allowance the earlier session used.
        # (replay_prompts.run's rule with no --max-new-tokens: each prompt's own, what the first pass used)
        self.assertEqual(self.seen["allowances"],
                         {p["prompt_id"]: p["max_new_tokens"] for p in second["groups"][0]["file"]["prompts"]})

    def test_neutralised_texts_leave_the_labels_unknown_never_disagreeing(self):
        _, _, result, _ = self._baseline_run(keep_texts=False)
        g = result["groups"]["plain"]
        self.assertEqual((g["current_texts_kept"], g["current_labels_parsed"]), (0, 0))
        self.assertIsNone(g["agreement"]["vllm_b1"]["label_agreement_rate"])
        self.assertEqual(g["agreement"]["vllm_b1"]["byte_identical"], 2)

    def test_a_kept_but_unparseable_current_reply_is_a_disagreement(self):
        _, _, result, _ = self._baseline_run(kept_text="not json at all")
        g = result["groups"]["plain"]
        self.assertEqual((g["current_texts_kept"], g["current_labels_parsed"]), (2, 0))
        self.assertEqual(g["agreement"]["vllm_b1"]["label_agreement_rate"], 0.0)

    def test_full_mode_keeps_its_absent_pairs(self):
        """Full three-arm mode: an unparsed current reply against a parsed vLLM one is a disagreement."""
        self.assertEqual(vllm_replay.pairs_of(None, {"k": "v"}), [("<absent>", "v")])
        self.assertEqual(vllm_replay.pairs_of(vllm_replay.NOT_KEPT, {"k": "v"}), [])
        self.assertEqual(vllm_replay.pairs_of(None, None), [])

    def test_neutralised_pairs_rule_drops_full_mode_disagreement(self):
        """The 7928df34 rule (no reference, nothing compared) dropped them."""
        original = vllm_replay.pairs_of
        vllm_replay.pairs_of = lambda reference, other: [] if reference is None else original(reference, other)
        try:
            self.assertNotEqual(vllm_replay.pairs_of(None, {"k": "v"}), [("<absent>", "v")])
        finally:
            vllm_replay.pairs_of = original

    def test_a_prompt_without_its_allowance_is_refused_at_build(self):
        first, _, _, _, value = PassProof()._run(run_id="first")
        prompts = [dict(p) for p in value["groups"][0]["file"]["prompts"]]
        prompts[0].pop("max_new_tokens")
        with self.assertRaises(ValueError):
            vllm_replay.baseline_block(first, "plain", prompts, {})

    def test_a_vllm_only_file_without_its_baseline_is_refused(self):
        _, second, _, _ = self._baseline_run()
        broken = dict(second, groups=[{k: v for k, v in second["groups"][0].items() if k != "baseline"}])
        with self.assertRaises(ValueError):
            vllm_replay.load_value(broken)


class LabelProof(unittest.TestCase):
    def test_macro_f1(self):
        same = [[("a", "a"), ("b", "b")], [("a", "a")]]
        self.assertEqual(vllm_replay.bootstrap_lower(same), (1.0, 1.0))
        moved = [[("a", "a"), ("b", "a")], [("a", "a")]]
        self.assertLess(vllm_replay.bootstrap_lower(moved)[0], 1.0)
        self.assertEqual(vllm_replay.pairs_of({"x": "1"}, None), [("1", "<unparsed>")])


FAKE_VLLM = '''
import json, os, socket, types
__version__ = "fake"
def _try():
    try:
        socket.create_connection(("192.0.2.1", 80), timeout=0.2)
        return "connected"
    except RuntimeError as exc:
        return "blocked" if "forbids network" in str(exc) else "other"
    except OSError:
        return "attempted"
def _log(text):
    with open(os.environ["FAKE_VLLM_LOG"], "a") as log:
        log.write(text + " ")
_log("import:" + _try())
class SamplingParams:
    def __init__(self, **kw):
        _log("params:" + json.dumps({k: kw[k] for k in ("ignore_eos", "stop_token_ids", "temperature")}, separators=(",", ":")))
class _Out:
    def __init__(self):
        self.text, self.token_ids, self.finish_reason = "ok", [1], "stop"
class _Req:
    def __init__(self):
        self.outputs = [_Out()]
class LLM:
    def __init__(self, **kw):
        _log("engine:" + _try())
        self.llm_engine = types.SimpleNamespace(model_config=types.SimpleNamespace(quantization="bitsandbytes", dtype="bfloat16"))
    def generate(self, prompts, params, lora_request=None, use_tqdm=False):
        return [_Req() for _ in prompts]
'''
FAKE_MODULES = {
    "vllm/inputs/__init__.py": "class TokensPrompt(dict):\n    def __init__(self, prompt_token_ids):\n"
                               "        super().__init__(prompt_token_ids=prompt_token_ids)\n",
    "vllm/model_executor/__init__.py": "",
    "vllm/model_executor/determinism/__init__.py": "",
    "vllm/model_executor/determinism/batch_invariant.py": "_batch_invariant_MODE = True\n",
    "vllm/v1/__init__.py": "", "vllm/v1/worker/__init__.py": "", "vllm/v1/worker/gpu/__init__.py": "",
    "vllm/v1/worker/gpu/sample/__init__.py": "",
    "vllm/v1/worker/gpu/sample/logits_processor/__init__.py":
        "class LogitsProcessor:\n    def __init__(self, vllm_config=None, req_states=None):\n        pass\n",
}


class ChildProof(unittest.TestCase):
    """The child, run as its own process on a fake vLLM: the runner's network denial applied before
    vLLM is imported (refused at import and at engine start, both in the child's own log), the
    stop rule (ignore_eos with the policy's ids), what the engine loaded, and the token table held
    to the runner's digest. Neutralised (an observer whose denial does nothing), it fails."""

    def _run(self, observer, digest=None, modules=True):
        import subprocess
        tok = _tok()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "fake" / "vllm").mkdir(parents=True)
            (d / "fake" / "vllm" / "__init__.py").write_text(FAKE_VLLM, encoding="utf-8")
            for name, text in (FAKE_MODULES.items() if modules else ()):
                (d / "fake" / name).parent.mkdir(parents=True, exist_ok=True)
                (d / "fake" / name).write_text(text, encoding="utf-8")
            job = {"observer": str(observer), "model": "m", "tokenizer": TOKENIZER, "adapter": None, "batch": 2,
                   "dtype": "bfloat16", "max_model_len": 64,
                   "token_table_sha256": digest or vllm_constraint.table_digest(tok),
                   "prompts": [{"prompt_id": "p0", "token_ids": [1, 2], "max_new_tokens": 4, "eos": EOS, "constraint": None}]}
            (d / "job.json").write_text(json.dumps(job), encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(d / "fake"), str(ROOT / "scripts"), str(HERE)]),
                       FAKE_VLLM_LOG=str(d / "fake.log"), VLLM_REPLAY_CHILD="1", HF_HUB_OFFLINE="1")
            done = subprocess.run([sys.executable, str(HERE / "vllm_child.py"), "--job", str(d / "job.json"),
                                   "--out", str(d / "results.json")], env=env, capture_output=True, timeout=600)
            result = json.loads((d / "results.json").read_text(encoding="utf-8"))
            log = (d / "fake.log").read_text(encoding="utf-8").split() if (d / "fake.log").is_file() else []
            return done.returncode, result, log, vllm_replay.network_events(d)

    def test_the_child_denies_the_network_and_stops_on_the_policy_ids_alone(self):
        code, result, log, network = self._run(vllm_replay._observer())
        self.assertEqual((code, result["error"]), (0, None), result.get("error"))
        self.assertEqual(log[:2], ["import:blocked", "engine:blocked"])
        self.assertIn('params:{"ignore_eos":true,"stop_token_ids":[151645],"temperature":0.0}', log)
        self.assertTrue(network["denied_in_child"])
        self.assertEqual(network["blocked"].get("create_connection"), 2)
        self.assertEqual(sorted(result["arms"]), ["vllm_b1", "vllm_batch"])
        spec = result["spec"]
        self.assertEqual((spec["engine"], spec["seed"], spec["sampling"]["ignore_eos"]), ("vllm", 0, True))
        for key in ("platform", "nvidia_smi", "batch_invariant", "v2_model_runner", "quantisation", "lora", "dtype"):
            self.assertIn(key, spec)
        self.assertEqual(result["loaded"], {"quantization": "bitsandbytes", "dtype": "bfloat16",
                                            "batch_invariant_mode": True, "batch_invariant_env": os.environ.get("VLLM_BATCH_INVARIANT")})

    def test_neutralised_denial_fails(self):
        with tempfile.TemporaryDirectory() as d:
            stub = Path(d) / "stub_observer.py"
            stub.write_text("class Recorder:\n    def __init__(self, path):\n        pass\n"
                            "def deny_network(rec):\n    pass\n", encoding="utf-8")
            _, _, log, _ = self._run(stub)
        self.assertNotIn("import:blocked", log)

    def test_another_token_table_is_refused(self):
        code, result, _, _ = self._run(vllm_replay._observer(), digest="0" * 64)
        self.assertNotEqual(code, 0)
        self.assertIn("token table", result["error"])
        self.assertEqual(result["arms"], {})

    def test_the_mrv2_interface_missing_in_the_child_raises(self):
        """No stand-in on the instance: in the child (VLLM_REPLAY_CHILD=1) the constraint module
        raises when vLLM's MRV2 interface does not import; on the laptop it takes the stand-in."""
        import subprocess
        code = "import vllm_constraint; print(vllm_constraint._Base.__module__)"
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / "scripts"), str(HERE)]))
        env.pop("VLLM_REPLAY_CHILD", None)
        laptop = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, timeout=120)
        child = subprocess.run([sys.executable, "-c", code], env=dict(env, VLLM_REPLAY_CHILD="1"),
                               capture_output=True, timeout=120)
        self.assertEqual(laptop.returncode, 0, laptop.stderr[-300:])
        self.assertNotEqual(child.returncode, 0)
        self.assertIn(b"ModuleNotFoundError", child.stderr)


class SealerProof(unittest.TestCase):
    """The sealer takes an auxiliary lock only with a vllm-replay-v1 replay file, in an exposed B1
    bundle, and that form only with its lock; and only a lock whose every entry is one exact
    version with sha256 hashes of 64 hex digits (the committed lock passes). Each rule neutralised fails."""

    GOOD = b"pkg==1.0 \\\n    --hash=sha256:" + b"a" * 64 + b"\n"
    BAD = (b"vllm==1\n",                                                  # no hash
           b"--extra-index-url https://example.invalid\n",                # an option
           b"vllm>=1 --hash=sha256:" + b"a" * 64 + b"\n",                 # not exact
           b"vllm==1.* --hash=sha256:" + b"a" * 64 + b"\n",               # a wildcard
           b"vllm==1.0 --hash=sha256:abc\n",                              # a short hash
           b"vllm==1.0 --hash=sha256:" + b"A" * 64 + b"\n",               # not lower-case hex
           b"vllm==1.0 --hash=md5:" + b"a" * 32 + b"\n",                  # another algorithm
           b"vllm==1.0 --hash=sha256:" + b"a" * 64 + b" ; extra\n",       # something else on the line
           b"vllm @ file:///tmp/x.whl --hash=sha256:" + b"a" * 64 + b"\n",  # a location
           b"# only a comment\n")                                         # nothing pinned

    def _sealer(self):
        if str(ROOT / "tools") not in sys.path:
            sys.path.insert(0, str(ROOT / "tools"))
        import prepare_ordinary_final_run as sealer
        return sealer

    def _lock_rule_holds(self, sealer):
        return (sealer.aux_lock_error((HERE / "vllm_aux.lock").read_bytes()) is None
                and sealer.aux_lock_error(self.GOOD) is None
                and all(sealer.aux_lock_error(bad) is not None for bad in self.BAD))

    def test_the_lock_rule(self):
        self.assertTrue(self._lock_rule_holds(self._sealer()))

    def test_the_lock_rule_neutralised_fails(self):
        sealer = self._sealer()
        original = sealer.aux_lock_error
        sealer.aux_lock_error = lambda data: None
        try:
            self.assertFalse(self._lock_rule_holds(sealer))
        finally:
            sealer.aux_lock_error = original

    def _forms(self, d):
        vllm_form = Path(d) / "vllm.json"
        vllm_form.write_text(json.dumps({"schema": vllm_replay.SCHEMA}), encoding="utf-8")
        plain = Path(d) / "plain.json"
        plain.write_text(json.dumps({"schema": "b3-replay-prompts-v1"}), encoding="utf-8")
        return vllm_form, plain

    def _admission_holds(self, sealer, d):
        vllm_form, plain = self._forms(d)
        lock = HERE / "vllm_aux.lock"
        admitted = lambda *args: sealer.aux_lock_admitted(*args)
        return (admitted(lock, "B1", False, vllm_form)                 # the one admitted case
                and not admitted(lock, "B1", True, vllm_form)          # a sealed B1 replay
                and not admitted(lock, "B1", False, None)              # an exposed B1 without replay
                and not admitted(lock, "B1", False, plain)             # another replay form
                and not admitted(lock, "B3", False, vllm_form)         # another arm
                and not admitted(None, "B1", False, vllm_form)         # the form without its lock
                and admitted(None, "B1", False, plain)                 # an ordinary replay bundle
                and admitted(None, "B3", False, None))                 # an ordinary bundle

    def test_the_admission_rule(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(self._admission_holds(self._sealer(), d))

    def test_the_admission_rule_neutralised_fails(self):
        sealer = self._sealer()
        original = sealer.aux_lock_admitted
        sealer.aux_lock_admitted = lambda aux_lock, arm, sealed, replay_prompts: True
        try:
            with tempfile.TemporaryDirectory() as d:
                self.assertFalse(self._admission_holds(sealer, d))
        finally:
            sealer.aux_lock_admitted = original

    def test_prepare_refuses_before_writing(self):
        sealer = self._sealer()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError) as raised:
                sealer.prepare(Path(d) / "bundle", aux_lock=HERE / "vllm_aux.lock")
            self.assertIn("auxiliary environment", str(raised.exception))
            self.assertFalse((Path(d) / "bundle").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
