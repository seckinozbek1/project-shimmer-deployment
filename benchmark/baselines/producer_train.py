"""The producer's training attempt (D-S57 item 3): a LoRA candidate for checkpoint 168, then its test.

Development, exposed. Not an arm and not a review. It rides the ordinary final runner's replay pass:
replay_prompts.py hands a `producer-training-v1` file here, as it hands a `judge-training-v1` file to
judge_train.py, so every launch rule (ledger, guard, reaper, caps, seal) stands and no bound
controller file changes. The plan, the mix and the replacement rule were written before any row was
built: docs/loop/PRODUCER_TRAINING_PLAN.md.

  tests (no model)
      py -3.12 benchmark/baselines/producer_train.py tests --compact <R1's replay file> \
          --compact <the v4 fresh set> --roles <the roles replay file> --out-test T --out-roles O
    The two replay files below, each prompt asked of `tuned` and of `candidate`, adjacent.

  assemble (no model)
      py -3.12 benchmark/baselines/producer_train.py assemble --rows R --test T --roles O
          --data-manifest M --out F --max-train-seconds S
    One sealed file: the training rows (each the validated two-turn prompt checkpoint 168 is run on,
    `system` and `user`, and its canonical `answer`), the compact test file T (a roles file of
    replay_prompts.py whose rows name `tuned` or `candidate`: DEV-84, the 52 saved failing
    partitions and the fresh set) and the other roles' file O (the same two names), as the exact
    bytes of each, the recipe, the seed and the data manifest. `recipe_sha256` is one digest of
    all of it.

  run (the rented machine, through replay_prompts.py run --prompts F --out D --paths sdpa,sdpa_constrained)
    D/training/ holds config.json, losses.jsonl, progress.json, the adapters (`candidate_half` at
    half the schedule, saved and never read, and `candidate` at its end) and result.json. Then
    the test file runs once with `tuned` (the resident 168) and `candidate` (the same pinned base
    with the candidate's adapter, held to its digests) loaded together, on the sealed paths, into
    D itself, where the runner counts one reply record a row a path; then the other roles' file on
    sdpa into D/passes/roles. A training step is not a model call and writes no reply record.

The recipe is 168's (tuning/producer_v3/experiment.json, run by tools/producer_v3_remote.py): the
4-bit base through prepare_model_for_kbit_training with gradient checkpointing, rank 8, alpha 16,
dropout .05 on the seven projections, AdamW at 1e-4 (betas .9 and .999, eps 1e-8, no weight decay),
one warmup update then linear decay, microbatch 1 with four accumulated, two passes over the rows,
the loss over the answer's tokens only (the prompt masked), bf16 autocast, gradient norm clipped at
1, eager attention, strict determinism, no TF32, seed 7. The one change (the plan's section 2): the
rows. Each pass orders the rows by SHA-256 of the seed, the pass and the row id.

The rate is measured before the run is trusted: after MEASURE_UPDATES updates the schedule is cut
to what `max_train_seconds` holds at the measured median, stated in the evidence (schedule_cut.json),
so a slow machine costs rows and not the cap. The longest row runs first, unapplied, so a memory
failure shows in minutes.
"""
import argparse
import gc
import hashlib
import json
import math
import statistics
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "scripts"), str(HERE.parents[1] / "tools")]

SCHEMA = "producer-training-v1"
CANDIDATE, HALF, TUNED = "candidate", "candidate_half", "tuned"
TEST_CHECKPOINTS = (TUNED, CANDIDATE)
MEASURE_UPDATES = 20
RECIPE = {"lora": {"r": 8, "lora_alpha": 16, "lora_dropout": 0.05, "bias": "none", "task_type": "CAUSAL_LM",
                   "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]},
          "learning_rate": 0.0001, "adam_beta1": 0.9, "adam_beta2": 0.999, "adam_epsilon": 1e-08, "weight_decay": 0.0,
          "gradient_accumulation": 4, "epochs": 2, "warmup_updates": 1, "max_grad_norm": 1.0, "seed": 7,
          "attention": "eager", "loss": "answer tokens only, prompt masked"}
ROW_FIELDS = {"row_id", "system", "user", "answer", "family", "share_alike"}
PUBLICATION = {"publishable": True,
               "rule": ("Product candidate only if it beats checkpoint 168 under docs/loop/PRODUCER_TRAINING_PLAN.md "
                        "section 4; otherwise 168 stays (D-S57 item 3). No share-alike row (D-281).")}
TEST_SCHEMA = "b3-replay-prompts-v1"


def _sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def is_training_file(value):
    return isinstance(value, dict) and value.get("schema") == SCHEMA


def recipe_digest(value):
    """One digest of the whole file but itself."""
    return _sha(_canonical({k: v for k, v in value.items() if k != "recipe_sha256"}))


def _test_value(text, name):
    value = json.loads(text)
    if not isinstance(value, dict) or value.get("schema") != TEST_SCHEMA or not value.get("prompts"):
        raise ValueError("the %s file is not a replay prompts file" % name)
    if value.get("prompt_count") != len(value["prompts"]):
        raise ValueError("the %s file's count is wrong" % name)
    seen = {}
    for p in value["prompts"]:
        if p.get("checkpoint") not in TEST_CHECKPOINTS or not p.get("pair_of"):
            raise ValueError("every %s row names tuned or candidate and its pair" % name)
        seen.setdefault(p["pair_of"], []).append(p["checkpoint"])
        if _sha(p["prompt"]) != p.get("prompt_sha256"):
            raise ValueError("a %s prompt is not its digest" % name)
    if any(sorted(v) != sorted(TEST_CHECKPOINTS) for v in seen.values()):
        raise ValueError("every %s prompt is asked once of tuned and once of the candidate" % name)
    return value


def check(value):
    """`value` held to what run() needs, or ValueError."""
    if not is_training_file(value):
        raise ValueError("not a producer training file")
    rows = value.get("rows") or []
    if not rows or value.get("rows_sha256") != _sha(_canonical(rows)):
        raise ValueError("the rows are empty or not the declared ones")
    ids = set()
    for row in rows:
        if set(row) != ROW_FIELDS or not all(isinstance(row[k], str) and row[k] for k in ("row_id", "system", "user", "answer", "family")):
            raise ValueError("a row is not {row_id, system, user, answer, family, share_alike}")
        if row["row_id"] in ids:
            raise ValueError("row ids repeat")
        ids.add(row["row_id"])
        json.loads(row["answer"])
    if value.get("publication") != PUBLICATION or any(r["share_alike"] for r in rows):
        raise ValueError("the publication rule is not the declared one, or a share-alike row is present")
    for side in ("test", "roles"):
        if value.get(side + "_sha256") != _sha(value.get(side + "_text") or ""):
            raise ValueError("the %s file is not the declared bytes" % side)
    test = _test_value(value["test_text"], "test")
    roles = _test_value(value["roles_text"], "roles")
    asked = [p["prompt"] for p in test["prompts"] + roles["prompts"]]
    # A training row's payload inside a test prompt is a test item trained on: refused.
    for row in rows:
        if any(row["user"] in prompt for prompt in asked):
            raise ValueError("a training row's payload is inside a test prompt: " + row["row_id"])
    training = value.get("training") or {}
    if {k: training.get(k) for k in RECIPE} != RECIPE:
        raise ValueError("the recipe is not 168's")
    if not training.get("model_id") or not training.get("revision") or not training.get("max_train_seconds", 0) > 0:
        raise ValueError("the model, its revision and the training time are stated")
    if value.get("recipe_sha256") != recipe_digest(value):
        raise ValueError("the file is not its recipe digest")
    return value


def read_file(path):
    return check(json.loads(Path(path).read_text(encoding="utf-8")))


def load_prompts(path):
    """The test file's rows, as replay_prompts reads them: the count the seal declares and the
    runner expects in D (the roles file's rows are written under D/passes/roles)."""
    import replay_prompts
    value = read_file(path)
    with tempfile.TemporaryDirectory() as folder:
        inner = Path(folder) / "test_prompts.json"
        inner.write_text(value["test_text"], encoding="utf-8", newline="")
        return replay_prompts.load_prompts(inner)


def paired(prompts, rename=None):
    """Replay rows asked of `tuned` and of `candidate`, adjacent, each pair named by its source.
    Plain rows are written twice; rows that already name a checkpoint keep theirs, `rename` mapping
    one (the roles file's `base`) to the candidate's name. Prompt ids are renumbered."""
    out = []
    for p in prompts:
        if "checkpoint" in p:
            names = [(rename or {}).get(p["checkpoint"], p["checkpoint"])]
        else:
            names = list(TEST_CHECKPOINTS)
        for name in names:
            row = dict(p, checkpoint=name, pair_of=p.get("pair_of") or "%s:%s" % (p.get("set"), p["source_call_id"]))
            out.append(row)
    for i, row in enumerate(out):
        row["prompt_id"] = "p%04d" % (i + 1)
    return {"schema": TEST_SCHEMA, "prompt_count": len(out), "prompts": out}


def test_files(compact_paths, roles_path, out_test, out_roles):
    """The two replay files the training file seals: the compact test (every prompt of
    `compact_paths`, which must all be compact producer prompts: DEV-84 and the 52 partitions
    from R1's file, the fresh set from the v4 build) and the other roles' file (the roles replay's
    rows, its `base` rows asked of the candidate instead)."""
    import replay_prompts
    prompts = []
    for path in compact_paths:
        for p in replay_prompts.load_prompts(path):
            if not replay_prompts.is_compact(p["prompt"]):
                raise ValueError("the compact test holds compact producer prompts only: " + str(p.get("prompt_id")))
            prompts.append({k: v for k, v in p.items() if k not in ("checkpoint", "pair_of")} if p.get("checkpoint") == TUNED or "checkpoint" not in p
                           else None)
    prompts = [p for p in prompts if p is not None]
    test = paired(prompts)
    roles = paired(replay_prompts.load_prompts(roles_path), rename={"base": CANDIDATE})
    for value, path in ((test, out_test), (roles, out_roles)):
        Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        _test_value(Path(path).read_text(encoding="utf-8"), Path(path).name)
    return test, roles


def assemble(rows_path, test_path, roles_path, data_manifest, out, max_train_seconds, *, spec=None):
    """The sealed file, from a JSON list of rows, the two replay files and the manifest."""
    import final_models
    spec = spec or final_models.specification("producer")
    rows = json.loads(Path(rows_path).read_text(encoding="utf-8"))
    rows = [{k: r[k] for k in sorted(ROW_FIELDS)} for r in rows]
    test, roles = (Path(p).read_bytes().decode("utf-8") for p in (test_path, roles_path))
    value = {"schema": SCHEMA, "status": "development, exposed (D-S57 item 3; docs/loop/PRODUCER_TRAINING_PLAN.md)",
             "training": dict(RECIPE, model_id=spec["model_id"], revision=spec["revision"], max_train_seconds=float(max_train_seconds)),
             "publication": PUBLICATION, "data_manifest": json.loads(Path(data_manifest).read_text(encoding="utf-8")),
             "rows": rows, "rows_sha256": _sha(_canonical(rows)),
             "test_text": test, "test_sha256": _sha(test), "roles_text": roles, "roles_sha256": _sha(roles)}
    value["recipe_sha256"] = recipe_digest(value)
    check(value)
    Path(out).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8", newline="\n")
    load_prompts(out)
    return value


def load_model(training):
    """The pinned 4-bit base with a fresh adapter, 168's way: (tokenizer, model, torch)."""
    import final_models
    torch = final_models.verify_runtime()
    from huggingface_hub import snapshot_download
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = Path(snapshot_download(training["model_id"], local_files_only=True))
    if path.name != training["revision"]:
        raise ValueError("the cached model is not the declared revision")
    tok = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(str(path), local_files_only=True, trust_remote_code=False, device_map={"": 0},
                                                 torch_dtype=torch.bfloat16, attn_implementation=training["attention"])
    if not model.is_loaded_in_4bit:
        raise ValueError("the base is not the 4-bit checkpoint")
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    torch.manual_seed(training["seed"])
    torch.cuda.manual_seed_all(training["seed"])
    model = get_peft_model(model, LoraConfig(**training["lora"]))
    model.peft_config["default"].base_model_name_or_path = training["model_id"]
    model.peft_config["default"].revision = training["revision"]
    return tok, model, torch


def encode(tok, row):
    """168's encoding (tuning/second_domain_agnostic_v2/runtime.py encode): the two turns through
    the model's own chat template, the answer as the assistant turn, the prompt masked, exactly one
    end-of-turn token in the answer's part."""
    messages = [{"role": "system", "content": row["system"]}, {"role": "user", "content": row["user"]}]
    prefix = list(tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
    ids = list(tok.apply_chat_template(messages + [{"role": "assistant", "content": row["answer"]}],
                                       tokenize=True, add_generation_prompt=False))
    if ids[:len(prefix)] != prefix:
        raise ValueError("prompt and answer do not split at the generation prompt: " + row["row_id"])
    suffix = ids[len(prefix):]
    if suffix.count(tok.eos_token_id) != 1:
        raise ValueError("the answer does not end on exactly one end-of-turn token: " + row["row_id"])
    return {"row_id": row["row_id"], "input_ids": ids, "labels": [-100] * len(prefix) + suffix,
            "prompt_length": len(prefix), "target_length": len(suffix)}


def schedule(rows, training):
    """The updates: each pass's rows ordered by SHA-256 of seed, pass and id, in groups of the
    accumulation (the last group of a pass its actual size)."""
    groups = []
    size = training["gradient_accumulation"]
    for epoch in range(1, training["epochs"] + 1):
        ordered = sorted(rows, key=lambda r: _sha("%s:%d:%s" % (training["seed"], epoch, r["row_id"])))
        groups += [(epoch, ordered[i:i + size]) for i in range(0, len(ordered), size)]
    return groups


def memory(torch):
    if not torch.cuda.is_available():
        return {"measured": False}
    return {"measured": True, "peak_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "peak_reserved_bytes": int(torch.cuda.max_memory_reserved())}


def save_adapter(model, folder, name, update):
    directory = Path(folder) / name
    directory.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(str(directory), safe_serialization=True)
    _write(directory / "PUBLICATION.json", PUBLICATION)
    identity = {"group": name, "update": update, "path": str(directory.resolve()),
                "weights_sha256": _sha((directory / "adapter_model.safetensors").read_bytes()),
                "config_sha256": _sha((directory / "adapter_config.json").read_bytes())}
    _write(directory / "identity.json", identity)
    return identity


def plan_after_measure(planned, seconds, max_train_seconds, spent):
    return max(1, min(planned, int((max_train_seconds - spent) / statistics.median(seconds)) + len(seconds)))


def train(value, folder, *, load=load_model, clock=time.perf_counter):
    """Train, save `candidate_half` and `candidate`, return the result. Writes only under `folder`."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    training = value["training"]
    tok, model, torch = load(training)
    encoded = {r["row_id"]: encode(tok, r) for r in value["rows"]}
    groups = schedule(value["rows"], training)
    planned = len(groups)
    params = [p for p in model.parameters() if p.requires_grad]
    settings = {"deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
                "allow_tf32": torch.backends.cuda.matmul.allow_tf32, "trainable_parameters": sum(p.numel() for p in params)}
    _write(folder / "config.json", {"training": training, "settings": settings, "rows": len(encoded), "rows_sha256": value["rows_sha256"],
                                    "data_manifest": value["data_manifest"], "recipe_sha256": value["recipe_sha256"],
                                    "planned_updates": planned, "publication": PUBLICATION,
                                    "longest_prompt_tokens": max(e["prompt_length"] for e in encoded.values()),
                                    "longest_answer_tokens": max(e["target_length"] for e in encoded.values())})

    def loss_of(datum):
        batch = {"input_ids": torch.tensor([datum["input_ids"]], dtype=torch.long, device=model.device),
                 "attention_mask": torch.ones((1, len(datum["input_ids"])), dtype=torch.long, device=model.device),
                 "labels": torch.tensor([datum["labels"]], dtype=torch.long, device=model.device)}
        with torch.autocast("cuda" if torch.cuda.is_available() else "cpu", dtype=torch.bfloat16):
            loss = model(**batch).loss
        if not bool(torch.isfinite(loss).item()):
            raise ValueError("a loss is not finite")
        return loss

    begin = clock()
    model.train()
    model.config.use_cache = False
    longest = max(encoded.values(), key=lambda e: len(e["input_ids"]))
    loss_of(longest).backward()
    model.zero_grad(set_to_none=True)
    _write(folder / "preflight.json", {"longest_row_tokens": len(longest["input_ids"]), "seconds": clock() - begin, "memory": memory(torch)})
    torch.manual_seed(training["seed"])
    torch.cuda.manual_seed_all(training["seed"])
    opt = torch.optim.AdamW(params, lr=training["learning_rate"], betas=(training["adam_beta1"], training["adam_beta2"]),
                            eps=training["adam_epsilon"], weight_decay=training["weight_decay"])
    state = {"total": planned}
    warm = training["warmup_updates"]
    scheduler = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min((s + 1) / warm, max(0., (state["total"] - s) / max(1, state["total"] - warm))))
    saved, seconds, losses, cut, update = [], [], [], None, 0
    start = clock()
    with open(folder / "losses.jsonl", "w", encoding="utf-8", newline="\n") as log:
        while update < state["total"]:
            began = clock()
            epoch, group = groups[update]
            opt.zero_grad(set_to_none=True)
            total = 0.
            for row in group:
                loss = loss_of(encoded[row["row_id"]])
                (loss / len(group)).backward()
                total += float(loss.detach())
            norm = torch.nn.utils.clip_grad_norm_(params, training["max_grad_norm"])
            rate = scheduler.get_last_lr()[0]
            opt.step()
            scheduler.step()
            update += 1
            seconds.append(clock() - began)
            losses.append(total / len(group))
            log.write(json.dumps({"update": update, "epoch": epoch, "rows": [r["row_id"] for r in group], "loss": losses[-1],
                                  "grad_norm": float(norm), "lr": rate, "seconds": seconds[-1]}) + "\n")
            log.flush()
            if len(seconds) == MEASURE_UPDATES:
                state["total"] = plan_after_measure(planned, seconds, training["max_train_seconds"], clock() - start)
                cut = {"after_update": update, "median_seconds": statistics.median(seconds), "planned": planned, "total": state["total"]}
                _write(folder / "schedule_cut.json", cut)
            _write(folder / "progress.json", {"phase": "training", "update": update, "of": state["total"], "elapsed_seconds": clock() - start,
                                              "seconds_per_update": statistics.median(seconds[-32:]), "memory": memory(torch)})
            if update == max(1, math.ceil(state["total"] / 2)) and not any(s["group"] == HALF for s in saved):
                saved.append(save_adapter(model, folder, HALF, update))
    saved.append(save_adapter(model, folder, CANDIDATE, update))
    result = {"publication": PUBLICATION, "recipe_sha256": value["recipe_sha256"], "updates": update, "planned_updates": planned,
              "training_seconds": clock() - start, "median_seconds_per_update": statistics.median(seconds),
              "first_loss": losses[0], "last_loss": losses[-1], "last_32_mean_loss": statistics.mean(losses[-32:]),
              "schedule_cut": cut, "adapters": saved, "memory": memory(torch), "settings": settings,
              "read": {"candidate": "tested", "candidate_half": "saved, never read (the plan's section 2)"}}
    _write(folder / "result.json", result)
    del model, opt
    return result


def test_readers(adapter):
    """The two checkpoints the test asks: the resident 168 and the base with the candidate's adapter."""
    import bare_model
    return {TUNED: bare_model.resolve_reader(checkpoint=bare_model.TUNED),
            CANDIDATE: dict(bare_model.resolve_reader(checkpoint=bare_model.BASE), adapter=adapter)}


def run(prompts_path, out, *, paths=("sdpa", "sdpa_constrained"), decision=None, max_new_tokens=None, load=load_model,
        replay=None, readers=test_readers):
    """Train, free the training model, then the test file into D and the roles file into
    D/passes/roles, each with both checkpoints loaded once."""
    import replay_prompts
    value = read_file(prompts_path)
    out = Path(out)
    folder = out / "training"
    result = train(value, folder, load=load)
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    candidate = next(a for a in result["adapters"] if a["group"] == CANDIDATE)
    adapter = {k: candidate[k] for k in ("path", "weights_sha256", "config_sha256")}
    files = {}
    for side in ("test", "roles"):
        files[side] = folder / ("%s_prompts.json" % side)
        files[side].write_text(value[side + "_text"], encoding="utf-8", newline="")
    # The progress reader (tools/ordinary_final_progress.py training_reading) reads a `questions`
    # phase as the reply records under `records_under` against `questions_total` (PROGRESS-A).
    counts = {side: json.loads(value[side + "_text"])["prompt_count"] for side in ("test", "roles")}
    _write(folder / "progress.json", {"phase": "questions", "part": "test", "questions_total": counts["test"] * len(paths),
                                      "started_epoch": time.time(), "records_under": str(out.resolve())})
    replay = replay or replay_prompts.run
    measurement = replay(files["test"], out, paths=list(paths), decision=decision, max_new_tokens=max_new_tokens,
                         reader=readers(adapter))
    _write(folder / "progress.json", {"phase": "questions", "part": "roles", "questions_total": counts["roles"],
                                      "started_epoch": time.time(), "records_under": str((out / "passes" / "roles").resolve())})
    replay(files["roles"], out / "passes" / "roles", paths=["sdpa"], decision=None, max_new_tokens=max_new_tokens,
           reader=readers(adapter))
    return measurement


HELDOUT_SCHEMA = "producer-heldout-v1"


def is_heldout_file(value):
    return isinstance(value, dict) and value.get("schema") == HELDOUT_SCHEMA


def check_heldout(value):
    """A held-out test-only file (producer_score.heldout_assemble, which refuses unless the opening is
    committed): its test is the declared bytes, every row asked of tuned and candidate, and the
    adapter's files carry their digests."""
    if not is_heldout_file(value):
        raise ValueError("not a producer held-out file")
    if value.get("test_sha256") != _sha(value.get("test_text") or ""):
        raise ValueError("the held-out test is not the declared bytes")
    _test_value(value["test_text"], "held-out")
    import base64
    for name in ("adapter_model.safetensors", "adapter_config.json"):
        entry = (value.get("adapter") or {}).get(name) or {}
        if _sha(base64.b64decode(entry.get("base64") or "")) != entry.get("sha256"):
            raise ValueError("the held-out file's adapter is not its digest: " + name)
    if not (isinstance(value.get("k"), int) and value["k"] >= 1):
        raise ValueError("the held-out file names its opening's k")
    return value


def heldout_run(prompts_path, out, *, paths=("sdpa", "sdpa_constrained"), decision=None, max_new_tokens=None,
                replay=None, readers=test_readers):
    """The test-only pass: write the adapter held to its digests, then the held-out test with the
    resident 168 and the candidate on the pinned base with that adapter, into D. No training."""
    import base64
    import replay_prompts
    value = check_heldout(json.loads(Path(prompts_path).read_text(encoding="utf-8")))
    out = Path(out)
    folder = out / "heldout"
    adapter_dir = folder / "candidate"
    adapter_dir.mkdir(parents=True, exist_ok=False)
    for name, entry in value["adapter"].items():
        (adapter_dir / name).write_bytes(base64.b64decode(entry["base64"]))
    adapter = {"path": str(adapter_dir.resolve()), "weights_sha256": value["adapter"]["adapter_model.safetensors"]["sha256"],
               "config_sha256": value["adapter"]["adapter_config.json"]["sha256"]}
    test = folder / "heldout_prompts.json"
    test.write_text(value["test_text"], encoding="utf-8", newline="")
    _write(folder / "progress.json", {"phase": "questions", "part": "heldout",
                                      "questions_total": json.loads(value["test_text"])["prompt_count"] * len(paths),
                                      "started_epoch": time.time(), "records_under": str(out.resolve())})
    return (replay or replay_prompts.run)(test, out, paths=list(paths), decision=decision, max_new_tokens=max_new_tokens,
                                          reader=readers(adapter))


def load_heldout_prompts(path):
    import replay_prompts
    value = check_heldout(json.loads(Path(path).read_text(encoding="utf-8")))
    with tempfile.TemporaryDirectory() as folder:
        inner = Path(folder) / "heldout_prompts.json"
        inner.write_text(value["test_text"], encoding="utf-8", newline="")
        return replay_prompts.load_prompts(inner)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("assemble")
    for name in ("--rows", "--test", "--roles", "--data-manifest", "--out"):
        a.add_argument(name, required=True)
    a.add_argument("--max-train-seconds", type=float, required=True)
    t = sub.add_parser("tests")
    t.add_argument("--compact", action="append", required=True, help="a replay file of compact producer prompts")
    t.add_argument("--roles", required=True, help="the roles replay file (producer_replays.py roles)")
    t.add_argument("--out-test", required=True)
    t.add_argument("--out-roles", required=True)
    args = parser.parse_args(argv)
    if args.command == "tests":
        test, roles = test_files(args.compact, args.roles, args.out_test, args.out_roles)
        print("test rows", test["prompt_count"], "roles rows", roles["prompt_count"])
        return 0
    value = assemble(args.rows, args.test, args.roles, args.data_manifest, args.out, args.max_train_seconds)
    print("rows", len(value["rows"]), "test rows", len(json.loads(value["test_text"])["prompts"]),
          "roles rows", len(json.loads(value["roles_text"])["prompts"]))
    print("recipe_sha256", value["recipe_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
