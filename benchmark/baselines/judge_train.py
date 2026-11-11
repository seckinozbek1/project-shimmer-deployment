"""The judge's training pass (T, D-S42 item 2): a LoRA adapter for the decision format, then a replay.

Development, exposed. Not an arm and not a review. It rides the ordinary final runner's replay pass:
replay_prompts.py hands a `judge-training-v1` file here, as it hands a G1 file to doc_judge.py, so
every launch rule (ledger, guard, reaper, caps, seal) stands and no bound controller file changes.

  assemble (no model)
      py -3.12 benchmark/baselines/judge_train.py assemble --rows R --held-out H --judge-prompts P
          --checkpoint trained_half=0.5 --checkpoint trained_full=1 --passes base,trained_half,trained_full
          --data-manifest M --out F --max-train-seconds S --model-id ID --revision REV
          --mix dev_mix|permissive_mix --max-updates U
    One sealed file: the training rows of tools/build_judge_training.py, its held-out rows, the
    checkpoints, fixed here before training, and C's questions as the exact bytes of their file. So
    each question keeps its `prompt_id` and `user_sha256` in every pass, which is what the bar binds
    decisions by. The forms the rows were built on must be the forms the questions ask.
    `recipe_sha256` is one digest of all of it (rows, questions, recipe, seeds, checkpoints).

  recipes (no model)
      py -3.12 benchmark/baselines/judge_train.py recipes --dev F1 --permissive F2
    The one digest over both files, refused unless they differ in their rows alone: same recipe,
    seeds, updates, checkpoints and questions, so the two compare.

  session (no model)
      py -3.12 benchmark/baselines/judge_train.py session --dev F1 --permissive F2 --out F
    One sealed file holding both recipes for ONE instance session (a batch admits no pair of B1
    bundles, and this changes no bound file). The run trains and asks dev_mix first under
    D/dev_mix/, then permissive_mix, whose last pass writes to D itself, where the runner counts
    one reply record a prompt. `recipes_sha256` is the same digest `recipes` gives.

The operator's ruling (a publication rule, not a measurement rule): the published adapter is trained
on `permissive_mix` only. A `dev_mix` adapter is measured and is never published, packaged or copied
outside `external/`. The file, config.json, result.json and every adapter folder state which it is.

  run (the rented machine, through replay_prompts.py run --prompts F --out D --paths sdpa)
    D/training/ holds config.json, losses.jsonl, progress.json, held_out_<update>.json, the adapters
    and result.json. Then one doc_judge pass per name of `question_passes` runs C's file unchanged,
    a trained pass taking its adapter through `reader_for`, held to the digests of the files just
    saved. The last pass, the final checkpoint, writes to D itself, where the runner counts one reply
    record a prompt; each earlier pass writes to D/passes/<name>. A training step is not a model
    call and writes no reply record: nothing it computes reaches a finding.

The recipe is the Producer's (tuning/producer_v3/experiment.json, tools/producer_v3_remote.py): the
4-bit base through prepare_model_for_kbit_training with gradient checkpointing, rank 8, alpha 16,
dropout .05 on the seven projections, AdamW at 1e-4, linear decay, microbatch 1, eager attention,
strict determinism, no TF32, seed 7. What differs, each for the format: the target is ONE token, the
answer's, read after the prompt by choice_decision.bind as a decision reads it, so the loss is the
cross entropy of that token over the whole vocabulary and the head runs at that position alone;
one pass over the rows, 16 rows an update, and a warmup in proportion to the longer schedule.

The rate is not known before the run. After MEASURE_UPDATES updates the schedule is cut to what
`max_train_seconds` holds at the measured median, stated in the evidence, so a slow machine costs
rows and not the cap. The longest row runs first, unapplied, so a memory failure comes in minutes.
"""
import argparse
import gc
import hashlib
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "scripts"), str(HERE.parents[1] / "tools")]

SCHEMA = "judge-training-v1"
SESSION_SCHEMA = "judge-training-session-v1"
SESSION_ORDER = ("dev_mix", "permissive_mix")
BASE_PASS = "base"
MAX_CHECKPOINTS = 4           # the last and at most three earlier (C_BAR.md)
MAX_TOKENS = 2048
MEASURE_UPDATES = 20
RECIPE = {"lora": {"r": 8, "lora_alpha": 16, "lora_dropout": 0.05, "bias": "none", "task_type": "CAUSAL_LM",
                   "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]},
          "learning_rate": 0.0001, "gradient_accumulation": 16, "warmup_updates": 20, "max_grad_norm": 1.0,
          "seed": 7, "attention": "eager"}
ROW_FIELDS = {"row_id", "form", "user", "answer", "share_alike"}
PUBLICATION = {
    "dev_mix": {"mix": "dev_mix", "publishable": False,
                "rule": "Development measurement only (operator's ruling). Trained on share-alike rows: never publish, package or copy this adapter outside external/."},
    "permissive_mix": {"mix": "permissive_mix", "publishable": True,
                       "rule": "Product candidate (operator's ruling). If it scores clearly worse than dev_mix, tell the operator before publishing anything."},
}


def _sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def _file_sha(path):
    return _sha(Path(path).read_bytes())


def _canonical_rows(rows):
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def forms_digest(forms):
    return _sha(_canonical_rows(forms))


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _doc_judge():
    import doc_judge
    return doc_judge


def is_training_file(value):
    return isinstance(value, dict) and value.get("schema") in (SCHEMA, SESSION_SCHEMA)


def questions_of(value):
    return json.loads(value["judge_prompts_text"])


def _forms(value):
    return questions_of(value)["config"]["choice"]["forms"]


def recipe_digest(value):
    """One digest of the whole file but itself: rows, questions, recipe, seeds and checkpoints."""
    return _sha(_canonical_rows({k: v for k, v in value.items() if k != "recipe_sha256"}))


def check(value):
    """`value` with its rows and fractions held to what run() needs, or ValueError. A session is
    each of its recipes so held, in the declared order, under their one digest."""
    if isinstance(value, dict) and value.get("schema") == SESSION_SCHEMA:
        recipes = value.get("recipes") or []
        if [r.get("publication", {}).get("mix") for r in recipes] != list(SESSION_ORDER):
            raise ValueError("a session holds dev_mix then permissive_mix")
        for recipe in recipes:
            check(recipe)
        if value.get("recipes_sha256") != pair_digest(*recipes):
            raise ValueError("the session is not its recipes digest")
        return value
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("not a judge training file")
    forms = _forms(value)
    if value["data_manifest"].get("forms_sha256") != forms_digest(forms):
        raise ValueError("the rows were built on other forms than the questions ask")
    if value["judge_prompts_sha256"] != _sha(value["judge_prompts_text"]):
        raise ValueError("the questions are not the declared ones")
    groups = [g["group"] for g in questions_of(value)["config"]["models"]]
    if "trained_groups" in value:
        if not value["trained_groups"] or len(set(value["trained_groups"])) != len(value["trained_groups"]) \
                or not set(value["trained_groups"]) <= set(groups):
            raise ValueError("the trained groups are model groups of the questions, each once")
    elif len(groups) != 1:
        raise ValueError("the questions come from one model group, which every pass reuses")
    if "earlier_pass_documents" in value:
        named = {q["document_id"] for q in questions_of(value)["prompts"]}
        listed = value["earlier_pass_documents"]
        if not listed or len(set(listed)) != len(listed) or not set(listed) <= named or "trained_groups" not in value:
            raise ValueError("the earlier pass's documents are documents of the questions, each once, beside trained groups")
    for side in ("rows", "held_out"):
        rows = value[side]
        if not rows or value[side + "_sha256"] != _sha(_canonical_rows(rows)):
            raise ValueError("the %s are empty or not the declared ones" % side)
        for row in rows:
            if not ROW_FIELDS <= set(row) or row["form"] not in forms:
                raise ValueError("a row lacks its form, its text or its answer")
            if row["answer"] not in {a["label"] for a in forms[row["form"]]["answers"]}:
                raise ValueError("a row's answer is not one of its form's fixed answers")
    if {r["row_id"] for r in value["rows"]} & {r["row_id"] for r in value["held_out"]}:
        raise ValueError("a row id sits on both sides")
    if {r["user"] for r in value["rows"]} & {r["user"] for r in value["held_out"]}:
        raise ValueError("a prompt sits on both sides")
    checkpoints = value["checkpoints"]
    fractions = list(checkpoints.values())
    if not 1 <= len(fractions) <= MAX_CHECKPOINTS or not all(0 < f <= 1 for f in fractions) or len(set(fractions)) != len(fractions) \
            or max(fractions) != 1:
        raise ValueError("the checkpoints are the last and at most three earlier, each at a fraction of the schedule")
    passes = value["question_passes"]
    last = max(checkpoints, key=checkpoints.get)
    if not passes or passes[-1] != last or len(set(passes)) != len(passes) or not set(passes) <= set(checkpoints) | {BASE_PASS}:
        raise ValueError("the question passes name base or a checkpoint once each, and end on the last checkpoint")
    publication = value["publication"]
    if publication != PUBLICATION.get(publication.get("mix")):
        raise ValueError("the file does not state a declared mix and its publication rule")
    if publication["publishable"] and any(r["share_alike"] for side in ("rows", "held_out") for r in value[side]):
        raise ValueError("a publishable mix holds a share-alike row")
    if value["training"].get("max_updates", 0) <= 0 or value["training"]["max_updates"] * value["training"]["gradient_accumulation"] > len(value["rows"]):
        raise ValueError("the updates are stated and the rows hold them")
    if value["training"].get("max_train_seconds", 0) <= 0:
        raise ValueError("a training pass states how long it may train")
    if value["recipe_sha256"] != recipe_digest(value):
        raise ValueError("the file is not its recipe digest")
    return value


def read_file(path):
    return check(json.loads(Path(path).read_text(encoding="utf-8")))


def recipes_of(value):
    return value["recipes"] if value["schema"] == SESSION_SCHEMA else [value]


def load_prompts(path):
    """The questions, as doc_judge reads them: the count the seal declares and the runner expects,
    the last recipe's last pass being the one written where the runner counts."""
    value = recipes_of(read_file(path))[-1]
    with tempfile.TemporaryDirectory() as folder:
        inner = Path(folder) / "judge_prompts.json"
        inner.write_text(value["judge_prompts_text"], encoding="utf-8", newline="")
        return _doc_judge().load_prompts(inner)


def assemble(rows_path, held_out_path, judge_prompts_path, checkpoints, passes, data_manifest, out, max_train_seconds, model_id, revision,
             mix, max_updates, trained_groups=None, earlier_pass_documents=None):
    def rows_of(path):
        keep = sorted(ROW_FIELDS | {"tokens"})
        return [{k: r[k] for k in keep} for r in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines())]
    rows, held = rows_of(rows_path), rows_of(held_out_path)
    text = Path(judge_prompts_path).read_bytes().decode("utf-8")
    value = {"schema": SCHEMA, "status": "development, exposed (D-S42 item 2, step T)",
             "training": dict(RECIPE, model_id=model_id, revision=revision, max_train_seconds=max_train_seconds, max_updates=max_updates),
             "publication": PUBLICATION[mix], "checkpoints": checkpoints, "question_passes": passes, "data_manifest": json.loads(Path(data_manifest).read_text(encoding="utf-8")),
             "rows": rows, "rows_sha256": _sha(_canonical_rows(rows)), "held_out": held, "held_out_sha256": _sha(_canonical_rows(held)),
             "judge_prompts_text": text, "judge_prompts_sha256": _sha(text)}
    if trained_groups:
        value["trained_groups"] = list(trained_groups)
    if earlier_pass_documents:
        value["earlier_pass_documents"] = sorted(earlier_pass_documents)
    value["recipe_sha256"] = recipe_digest(value)
    check(value)
    Path(out).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8", newline="\n")
    load_prompts(out)
    return value


def recipes_digest(dev_path, permissive_path):
    """One digest over a dev_mix file and a permissive_mix file that differ in their rows alone."""
    return pair_digest(read_file(dev_path), read_file(permissive_path))


def pair_digest(dev, loose):
    if (dev["publication"]["mix"], loose["publication"]["mix"]) != SESSION_ORDER:
        raise ValueError("one dev_mix file and one permissive_mix file")
    for key in ("training", "checkpoints", "judge_prompts_sha256"):
        if dev[key] != loose[key]:
            raise ValueError("the two recipes differ in more than their rows: " + key)
    if dev["question_passes"][-1] != loose["question_passes"][-1]:
        raise ValueError("the two recipes end on different checkpoints")
    return _sha("dev_mix:%s\npermissive_mix:%s\n" % (dev["recipe_sha256"], loose["recipe_sha256"]))


def session(dev_path, permissive_path, out):
    dev, loose = read_file(dev_path), read_file(permissive_path)
    value = {"schema": SESSION_SCHEMA, "status": "development, exposed (D-S42 item 2, step T): one session, two recipes",
             "recipes": [dev, loose], "recipes_sha256": pair_digest(dev, loose)}
    check(value)
    Path(out).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8", newline="\n")
    load_prompts(out)
    return value


def load_model(training):
    """The 4-bit base with a fresh adapter, the Producer's way: (tokenizer, model, torch)."""
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


def encoded(tok, rows, forms):
    """Each row as (row, prompt ids, the answer's token, every answer's token), through the model's
    own chat template and choice_decision.bind, so a target is the token a decision reads."""
    import choice_decision

    def encode(text):
        return tok(text, add_special_tokens=False)["input_ids"]
    out = []
    for row in rows:
        prompt = tok.apply_chat_template([{"role": "user", "content": row["user"]}], tokenize=False, add_generation_prompt=True)
        bound = choice_decision.bind(choice_decision.declare(prompt, forms[row["form"]]["answers"]), encode)
        ids = encode(prompt)
        if len(ids) > MAX_TOKENS:
            raise ValueError("a row is over the cap the memory arithmetic holds to: " + row["row_id"])
        tokens = {a["label"]: a["token_id"] for a in bound["answers"]}
        out.append((row, ids, tokens[row["answer"]], tokens))
    return out


def decision_logits(model, torch, ids):
    """The next-token logits after `ids`, the head run at the last position alone."""
    inner = model.get_base_model()
    tensor = torch.tensor([ids], device=inner.device)
    hidden = inner.model(input_ids=tensor, use_cache=False).last_hidden_state[:, -1]
    return inner.lm_head(hidden.to(inner.lm_head.weight.dtype)).float()


def row_loss(model, torch, ids, target):
    logits = decision_logits(model, torch, ids)
    return torch.nn.functional.cross_entropy(logits, torch.tensor([target], device=logits.device))


def held_out_report(model, torch, rows, update, folder):
    """Loss over the vocabulary, and the declared answers' top pick, per form and answer."""
    model.eval()
    totals = {}
    with torch.no_grad():
        for row, ids, target, tokens in rows:
            logits = decision_logits(model, torch, ids)[0]
            loss = float(torch.nn.functional.cross_entropy(logits[None], torch.tensor([target], device=logits.device)))
            picked = max(tokens, key=lambda label: float(logits[tokens[label]]))
            cell = totals.setdefault(row["form"], {"rows": 0, "loss": 0.0, "right": 0, "confusion": {}})
            cell["rows"] += 1
            cell["loss"] += loss
            cell["right"] += picked == row["answer"]
            pair = row["answer"] + " -> " + picked
            cell["confusion"][pair] = cell["confusion"].get(pair, 0) + 1
    model.train()
    report = {"update": update, "forms": {f: dict(c, loss=c["loss"] / c["rows"], accuracy=c["right"] / c["rows"]) for f, c in totals.items()}}
    count = sum(c["rows"] for c in totals.values())
    report["loss"] = sum(c["loss"] for c in totals.values()) / count
    report["accuracy"] = sum(c["right"] for c in totals.values()) / count
    _write(Path(folder) / ("held_out_%06d.json" % update), report)
    return report


def memory(torch):
    if not torch.cuda.is_available():
        return {"measured": False}
    return {"measured": True, "peak_allocated_bytes": int(torch.cuda.max_memory_allocated()), "peak_reserved_bytes": int(torch.cuda.max_memory_reserved())}


def save_adapter(model, folder, name, update, publication):
    directory = Path(folder) / name
    directory.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(str(directory), safe_serialization=True)
    _write(directory / "PUBLICATION.json", publication)
    identity = {"group": name, "update": update, "publication": publication, "path": str(directory.resolve()),
                "weights_sha256": _file_sha(directory / "adapter_model.safetensors"),
                "config_sha256": _file_sha(directory / "adapter_config.json")}
    _write(directory / "identity.json", identity)
    return identity


def plan_after_measure(planned, seconds, max_train_seconds, spent):
    """The updates to run, given the measured seconds an update and the seconds already spent."""
    return max(1, min(planned, int((max_train_seconds - spent) / statistics.median(seconds)) + len(seconds)))


def train(value, folder, *, load=load_model, clock=time.perf_counter):
    """Train, save every named checkpoint and return the result. Writes only under `folder`."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    training, forms = value["training"], _forms(value)
    tok, model, torch = load(training)
    rows, held = encoded(tok, value["rows"], forms), encoded(tok, value["held_out"], forms)
    accumulate = training["gradient_accumulation"]
    planned = min(len(rows) // accumulate, training["max_updates"])
    if planned < 1:
        raise ValueError("fewer rows than one update")
    params = [p for p in model.parameters() if p.requires_grad]
    settings = {"deterministic_algorithms": torch.are_deterministic_algorithms_enabled(), "allow_tf32": torch.backends.cuda.matmul.allow_tf32,
                "seed": training["seed"], "attention": training["attention"], "trainable_parameters": sum(p.numel() for p in params)}
    _write(folder / "config.json", {"training": training, "settings": settings, "rows": len(rows), "held_out": len(held),
                                    "rows_sha256": value["rows_sha256"], "held_out_sha256": value["held_out_sha256"],
                                    "data_manifest": value["data_manifest"], "checkpoints": value["checkpoints"], "recipe_sha256": value["recipe_sha256"],
                                    "publication": value["publication"],
                                    "planned_updates": planned})
    begin = clock()
    longest = max(rows, key=lambda r: len(r[1]))
    model.train()
    row_loss(model, torch, longest[1], longest[2]).backward()
    model.zero_grad(set_to_none=True)
    preflight = {"longest_row_tokens": len(longest[1]), "seconds": clock() - begin, "memory": memory(torch)}
    _write(folder / "preflight.json", preflight)
    torch.manual_seed(training["seed"])
    torch.cuda.manual_seed_all(training["seed"])
    reports = [held_out_report(model, torch, held, 0, folder)]
    opt = torch.optim.AdamW(params, lr=training["learning_rate"], betas=(.9, .999), eps=1e-8, weight_decay=0.)
    state = {"total": planned}
    warm = training["warmup_updates"]
    scheduler = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min((s + 1) / warm, max(0., (state["total"] - s) / max(1, state["total"] - warm))))
    fractions = sorted(value["checkpoints"].items(), key=lambda item: item[1])
    saved, seconds, tokens, losses = [], [], 0, []
    start = clock()
    update, cut = 0, None
    with open(folder / "losses.jsonl", "w", encoding="utf-8", newline="\n") as log:
        while update < state["total"]:
            began = clock()
            total = 0.
            for row, ids, target, _tokens in rows[update * accumulate:(update + 1) * accumulate]:
                loss = row_loss(model, torch, ids, target)
                (loss / accumulate).backward()
                total += float(loss)
                tokens += len(ids)
            norm = torch.nn.utils.clip_grad_norm_(params, training["max_grad_norm"])
            rate = scheduler.get_last_lr()[0]
            opt.step()
            scheduler.step()
            opt.zero_grad(set_to_none=True)
            update += 1
            seconds.append(clock() - began)
            losses.append(total / accumulate)
            log.write(json.dumps({"update": update, "loss": losses[-1], "grad_norm": float(norm), "lr": rate, "seconds": seconds[-1]}) + "\n")
            log.flush()
            if len(seconds) == MEASURE_UPDATES:
                state["total"] = plan_after_measure(planned, seconds, training["max_train_seconds"], clock() - start)
                cut = {"after_update": update, "median_seconds": statistics.median(seconds), "planned": planned, "total": state["total"]}
                _write(folder / "schedule_cut.json", cut)
            _write(folder / "progress.json", {"phase": "training", "update": update, "of": state["total"], "elapsed_seconds": clock() - start,
                                              "seconds_per_update": statistics.median(seconds[-32:]), "memory": memory(torch)})
            while fractions and update >= max(1, round(fractions[0][1] * state["total"])):
                name, _fraction = fractions.pop(0)
                saved.append(save_adapter(model, folder, name, update, value["publication"]))
                reports.append(held_out_report(model, torch, held, update, folder))
    result = {"publication": value["publication"], "recipe_sha256": value["recipe_sha256"], "updates": update, "planned_updates": planned, "rows_used": update * accumulate, "rows": len(rows), "tokens_used": tokens,
              "training_seconds": clock() - start, "median_seconds_per_update": statistics.median(seconds),
              "tokens_per_second": tokens / max(sum(seconds), 1e-9), "first_loss": losses[0], "last_loss": losses[-1],
              "last_32_mean_loss": statistics.mean(losses[-32:]), "schedule_cut": cut, "held_out": reports, "adapters": saved,
              "memory": memory(torch), "preflight": preflight, "settings": settings}
    _write(folder / "result.json", result)
    return result


def adapter_reader(adapter, groups=None):
    """doc_judge's `reader_for`: the reader it would resolve, with `adapter` on it for a group of
    `groups` (every group when None) when the pass has one. The questions stay as sealed, and
    bare_model.apply_adapter holds the files to these digests before reading them. None is the base
    model's pass."""
    import bare_model

    def reader_for(group, allowance):
        reader = bare_model.resolve_reader(agent=group["agent"], checkpoint=group["checkpoint"], max_new_tokens=allowance)
        trained = groups is None or group["group"] in groups
        return reader if adapter is None or not trained else dict(reader, adapter=adapter)
    return reader_for


def trained_subset(prompts, groups, documents=None):
    """The questions of `groups` alone, each prompt as sealed (its id and digest unchanged), the
    config naming those groups and its digest written again. An earlier checkpoint is asked only
    what a trained group asks, and only on `documents` when the file names them (half A, D-313:
    the fresh set is asked of the last checkpoint alone); the untrained groups run once, in the
    last pass."""
    tool = _doc_judge()
    value = json.loads(json.dumps(prompts))
    value["config"]["models"] = [g for g in value["config"]["models"] if g["group"] in groups]
    value["prompts"] = [q for q in value["prompts"] if q["group"] in groups and (documents is None or q["document_id"] in documents)]
    value["prompt_count"] = len(value["prompts"])
    value["config_sha256"] = tool._sha(tool._canonical(value["config"]))
    return value


def run(prompts_path, out, *, paths=("sdpa",), decision=None, max_new_tokens=None, load=load_model, judge=None, reader=adapter_reader):
    """The whole pass, recipe by recipe: every recipe but the last under D/<mix>/, the last in D."""
    recipes = recipes_of(read_file(prompts_path))
    measurement = None
    for number, value in enumerate(recipes):
        place = Path(out) if number == len(recipes) - 1 else Path(out) / value["publication"]["mix"]
        measurement = run_recipe(value, place, paths=paths, decision=decision, max_new_tokens=max_new_tokens, load=load, judge=judge,
                                 reader=reader)
    return measurement


def run_recipe(value, out, *, paths, decision, max_new_tokens, load, judge, reader):
    """One recipe: train, then ask its questions once per pass. The model is freed before the
    questions load it again, adapter by adapter."""
    folder = Path(out) / "training"
    result = train(value, folder, load=load)
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    questions = folder / "judge_prompts.json"
    questions.write_text(value["judge_prompts_text"], encoding="utf-8", newline="")
    adapters = {a["group"]: {k: a[k] for k in ("path", "weights_sha256", "config_sha256")} for a in result["adapters"]}
    if set(adapters) != set(value["checkpoints"]):
        raise ValueError("a checkpoint has no adapter")
    passes = value["question_passes"]
    sealed = questions_of(value)
    groups = value.get("trained_groups")
    earlier = value.get("earlier_pass_documents")
    subset = trained_subset(sealed, groups, set(earlier) if earlier else None) if groups else sealed
    if groups:
        _write(folder / "trained_questions.json", subset)
    total = sealed["prompt_count"] + subset["prompt_count"] * (len(passes) - 1)
    _write(folder / "progress.json", {"phase": "questions", "questions_total": total, "started_epoch": time.time(),
                                      "records_under": str(Path(out).resolve()), "mix": value["publication"]["mix"]})
    measurement = None
    for name in passes:
        last = name == passes[-1]
        target = Path(out) if last else Path(out) / "passes" / name
        asked = questions if last or not groups else folder / "trained_questions.json"
        measurement = (judge or _doc_judge().run)(asked, target, paths=list(paths), decision=decision, max_new_tokens=max_new_tokens,
                                                  reader_for=reader(adapters.get(name)) if groups is None else reader(adapters.get(name), groups))
    return measurement


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("assemble")
    for name in ("--rows", "--held-out", "--judge-prompts", "--data-manifest", "--out", "--model-id", "--revision", "--passes"):
        a.add_argument(name, required=True)
    a.add_argument("--checkpoint", action="append", required=True, help="name=fraction of the schedule")
    a.add_argument("--max-train-seconds", type=float, required=True)
    a.add_argument("--mix", required=True, choices=sorted(PUBLICATION))
    a.add_argument("--max-updates", type=int, required=True)
    a.add_argument("--trained-group", action="append", default=None, help="a model group of the questions that takes the adapter")
    a.add_argument("--earlier-pass-documents", default=None, help="a JSON list of the document ids an earlier checkpoint is asked on")
    r = sub.add_parser("recipes")
    r.add_argument("--dev", required=True)
    r.add_argument("--permissive", required=True)
    s = sub.add_parser("session")
    s.add_argument("--dev", required=True)
    s.add_argument("--permissive", required=True)
    s.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "recipes":
        print("recipes_sha256", recipes_digest(args.dev, args.permissive))
        return 0
    if args.command == "session":
        print("recipes_sha256", session(args.dev, args.permissive, args.out)["recipes_sha256"])
        return 0
    checkpoints = {k: float(v) for k, v in (c.split("=", 1) for c in args.checkpoint)}
    value = assemble(args.rows, args.held_out, args.judge_prompts, checkpoints, args.passes.split(","), args.data_manifest, args.out,
                     args.max_train_seconds, args.model_id, args.revision, args.mix, args.max_updates, args.trained_group,
                     json.loads(Path(args.earlier_pass_documents).read_text(encoding="utf-8")) if args.earlier_pass_documents else None)
    print("rows", len(value["rows"]), "held out", len(value["held_out"]), "questions", questions_of(value)["prompt_count"],
          "passes", len(value["question_passes"]))
    print("recipe_sha256", value["recipe_sha256"])
    print("judge_prompts_sha256", value["judge_prompts_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
