"""vLLM against the current engine on saved prompts (#217, D-598 to D-601): a measurement, exposed,
development only. Not an arm, not a review, and nothing in a run reads it.

  build (no model, the laptop)
      py -3.12 benchmark/baselines/vllm_replay.py build --group NAME=FILE [--group ...]
          [--batch 16] --out vllm_replay.json
    Each FILE is a replay_prompts.json (replay_prompts.py extract): the compact producer's
    prompts (with --dev the 84 DEV rows of checkpoint 168), a file of envelope agents' prompts
    (one model a file), or other producer prompts. The file is copied whole into its group, with
    the engine path its prompts take on the current engine (`sdpa_constrained` for compact and
    envelope prompts, `sdpa` for the rest) and whether vLLM constrains them the same way.

  run: never called by hand. replay_prompts.py's `run` hands a vllm-replay-v1 file here, on the
    sdpa path alone, inside the sealed replay pass. Per group: the current engine first, in this
    process, through replay_prompts.run (its model loaded, every prompt, then released; its
    generation loop alone timed); every resident model evicted and the free GPU memory read;
    then the group's job in the auxiliary environment's own Python
    (`venv_aux/bin/python` beside the prompts file, made by the controller from the sealed lock),
    as a child process: vLLM on the same base and adapter, the same token ids, greedy, under
    VLLM_BATCH_INVARIANT=1, each prompt alone and then all together, each with the output
    allowance the current engine used and the frozen policy's stop ids alone. Both engines load the
    checkpoint's own pre-quantised NF4 snapshot at its compute dtype, or the group runs no child.
    Prompts, jobs, results and texts stay in `vllm_work/` beside the prompts file, outside the
    evidence the controller packs. One reply record per prompt
    per arm (hashes only), all under <out>/audit/model_replies, and <out>/replay_measurement.json:
    per group and arm the seconds, output tokens and tokens per second, the speed factor of each
    vLLM arm against the current engine, byte-identical replies (vLLM against the current engine,
    batch against alone), contract validity by the same validators replay_prompts uses, the
    constraint's counts, and per agent the agreement of each item's label (the field
    `LABEL_FIELDS` names) with the current engine's: counts and a macro-F1 with a paired
    bootstrap lower bound over prompts. Ids, hashes, counts, reasons and seconds only.

The bar (D-601, written before any figure): contract validity not lower than the current
engine's for any agent, label macro-F1 against the current engine at least 0.99 at the bootstrap
lower bound (a change of at most 1 point in any score read from those labels), and PROCESSOR DEV
102 of 102 items valid. This tool decides nothing; it reports the counts the bar is read on.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT / "scripts"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCHEMA = "vllm-replay-v1"
ARMS = ("current", "vllm_b1", "vllm_batch")
AUX_PYTHON = Path("venv_aux") / "bin" / "python"
WORK = "vllm_work"
CHILD = HERE / "vllm_child.py"
CHILD_SECONDS = 4 * 3600
# The item field each agent's label is read from (a measurement map, not product code); the
# compact producer's items are labelled by their `status`.
LABEL_FIELDS = {"PROCESSOR": "status", "PROCESSOR_DEV": "status", "ARCHIVIST": "confidence",
                "EDITOR_CLERK": "verdict", "CITATION_RESOLVER": "resolved", "SPEECH_ACT_TAGGER": "speech_act",
                "LEGAL_ANALYST": "verdict", "VERIFIER": "finding", "PRACTICE_AUDITOR": "verdict"}
KEY_FIELDS = ("alias", "ref", "utterance_id", "claim_id", "paragraph", "item_id")
BOOTSTRAP = 2000
ENV_KEPT = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "CUDA_VISIBLE_DEVICES", "CUBLAS_WORKSPACE_CONFIG",
            "HF_HOME", "HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "XDG_CACHE_HOME")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _replay():
    import replay_prompts
    return replay_prompts


# ---------------------------------------------------------------------------
# build and load


def group_kind(prompts):
    """compact, envelope or plain: the engine path and constraint a group's prompts take."""
    replay = _replay()
    if all(p.get("envelope") is True for p in prompts):
        return "envelope"
    if any(p.get("envelope") is True for p in prompts):
        raise ValueError("a group holds envelope agents' prompts or producer prompts, not both")
    compact = [replay.is_compact(p["prompt"]) for p in prompts]
    if all(compact):
        return "compact"
    if any(compact):
        raise ValueError("a group holds compact producer prompts or other producer prompts, not both")
    return "plain"


def baseline_block(measured, name, prompts, texts_by_sha):
    """A group's current engine as an earlier session measured it (its replay_measurement.json):
    its seconds and output tokens, dtypes, specification and per prompt the reply's digest,
    validity, items and output tokens, and the reply's text where a saved reply with that very
    digest is given (texts_by_sha, the source runs' saved replies and the frozen DEV replies)."""
    group = measured["groups"][name]
    rows = {}
    for p in prompts:
        allowance = p.get("max_new_tokens")
        if not isinstance(allowance, int) or isinstance(allowance, bool) or allowance <= 0:
            raise ValueError("prompt %s carries no output allowance the earlier session used" % p["prompt_id"])
        # replay_prompts.run's rule with no --max-new-tokens: the prompt's own allowance.
        rows[p["prompt_id"]] = dict(group["rows"][p["prompt_id"]]["current"], max_new_tokens=allowance)
    return {"run_id": measured["run_id"], "current_dtype": group["current_dtype"],
            "current": {k: group["arms"]["current"].get(k) for k in ("seconds", "output_tokens")},
            "specification": (group.get("specification") or {}).get("current"), "rows": rows,
            "texts": {pid: texts_by_sha[r["sha256"]] for pid, r in rows.items() if r.get("sha256") in texts_by_sha}}


def saved_texts(sources):
    """{sha256: text} of saved replies: reply-records folders (each record's reply text) and DEV
    replies .jsonl files (each row's raw_output). Read on the laptop at build time only."""
    found = {}
    for source in sources:
        source = Path(source)
        if source.is_dir():
            for path in source.glob("*.json"):
                text = (json.loads(path.read_text(encoding="utf-8")).get("reply") or {}).get("text")
                if isinstance(text, str):
                    found[_sha(text)] = text
        else:
            for line in source.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    text = json.loads(line).get("raw_output")
                    if isinstance(text, str):
                        found[_sha(text)] = text
    return found


def build(groups, out, batch=16, baseline=None, texts_by_sha=None):
    """`baseline`, an earlier pass's replay_measurement.json: the vLLM arms alone run, compared with
    that session's current engine (its digests, validity and, where a saved reply matches its
    digest, its text); the timing is then cross-session."""
    replay = _replay()
    built = []
    for name, path in groups:
        if any(g["name"] == name for g in built):
            raise ValueError("group names repeat: " + name)
        prompts = replay.load_prompts(path)
        if len({replay.model_key(p) for p in prompts}) != 1:
            raise ValueError("a group holds one model's prompts: " + name)
        kind = group_kind(prompts)
        built.append({"name": name, "kind": kind, "current_path": "sdpa" if kind == "plain" else "sdpa_constrained",
                      "file": json.loads(Path(path).read_text(encoding="utf-8"))})
        if baseline is not None:
            built[-1]["baseline"] = baseline_block(baseline, name, prompts, texts_by_sha or {})
    value = {"schema": SCHEMA, "batch": int(batch), "arms": list(ARMS if baseline is None else ARMS[1:]), "groups": built,
             "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    value["prompt_count"] = len(load_value(value))
    Path(out).write_text(json.dumps(value, indent=1, ensure_ascii=False), encoding="utf-8")
    return value


def is_prompts_file(value):
    return isinstance(value, dict) and value.get("schema") == SCHEMA


def is_prompts_path(path):
    try:
        with open(path, "rb") as stream:
            head = stream.read(4096).decode("utf-8", "ignore")
    except OSError:
        return False
    return '"schema": "%s"' % SCHEMA in head or '"schema":"%s"' % SCHEMA in head


def load_value(value):
    """One row per prompt per arm, each prompt held to its SHA-256: the sealed count."""
    replay = _replay()
    arms = list(value.get("arms") or []) if is_prompts_file(value) else []
    with_baseline = arms == list(ARMS[1:])
    if arms not in (list(ARMS), list(ARMS[1:])) or not value.get("groups"):
        raise ValueError("not a vllm-replay-v1 file")
    if with_baseline and not all("baseline" in g for g in value["groups"]):
        raise ValueError("a vLLM-only file needs every group's baseline")
    rows, seen = [], set()
    for group in value["groups"]:
        file = group["file"]
        if file.get("schema") != replay.SCHEMA or file.get("prompt_count") != len(file.get("prompts") or []) \
                or not file["prompts"]:
            raise ValueError("group %s holds no replay_prompts.json" % group.get("name"))
        for prompt in file["prompts"]:
            if not isinstance(prompt.get("prompt"), str) or _sha(prompt["prompt"]) != prompt.get("prompt_sha256"):
                raise ValueError("a prompt does not match its SHA-256: " + str(prompt.get("prompt_id")))
            key = (group["name"], prompt["prompt_id"])
            if key in seen:
                raise ValueError("prompt ids repeat in group " + group["name"])
            seen.add(key)
            if with_baseline and prompt["prompt_id"] not in group["baseline"]["rows"]:
                raise ValueError("prompt %s has no baseline row" % prompt["prompt_id"])
            rows += [dict(prompt, group=group["name"], arm=arm) for arm in arms]
    if value.get("prompt_count") is not None and value["prompt_count"] != len(rows):
        raise ValueError("a vllm-replay-v1 file's count is wrong")
    return rows


def load_prompts(path):
    return load_value(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# labels and the bar's figures


def items_of(text):
    """The reply's items as the validators read them: a compact reply's `items`, an envelope's
    `items`, or the parsed object's list under its one list field; None when it does not parse."""
    try:
        value = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
    except (ValueError, AttributeError):
        return None
    if isinstance(value, dict):
        for key in ("items",) + tuple(k for k, v in value.items() if isinstance(v, list)):
            if isinstance(value.get(key), list):
                return [i for i in value[key] if isinstance(i, dict)]
        return [value]
    return [i for i in value if isinstance(i, dict)] if isinstance(value, list) else None


def labels(agent, text):
    """{item key: label} of one reply; the key is the item's own id field, else its position."""
    found = items_of(text) if isinstance(text, str) else None
    if found is None:
        return None
    field = LABEL_FIELDS.get(agent, "verdict")
    out = {}
    for index, item in enumerate(found):
        key = next((str(item[k]) for k in KEY_FIELDS if k in item and not isinstance(item[k], (list, dict))), None)
        out[key if key is not None else "#%d" % index] = json.dumps(item.get(field), sort_keys=True)
    return out


NOT_KEPT = "<text not kept>"   # baseline mode only: the earlier current reply's text is not on hand


def pairs_of(reference, other):
    """(reference label, other label) per item key, an absent side being "<absent>"; an
    unparsed reply counts every reference item as "<unparsed>"."""
    if reference is NOT_KEPT or (reference is None and other is None):
        return []   # nothing to compare: the earlier session's text was not kept, or neither side parsed
    reference, missing = reference or {}, "<unparsed>" if other is None else "<absent>"
    other = other or {}
    return [(reference.get(k, "<absent>"), other.get(k, missing)) for k in sorted(set(reference) | set(other))]


def macro_f1(pairs):
    classes = sorted({a for a, _ in pairs})
    if not classes:
        return None
    scores = []
    for c in classes:
        tp = sum(1 for a, b in pairs if a == c and b == c)
        fp = sum(1 for a, b in pairs if a != c and b == c)
        fn = sum(1 for a, b in pairs if a == c and b != c)
        scores.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(scores) / len(scores)


def bootstrap_lower(by_prompt, seed=0, n=BOOTSTRAP, level=0.05):
    """The macro-F1 of all pairs and its paired bootstrap lower bound, resampling prompts."""
    clusters = [p for p in by_prompt if p]
    point = macro_f1([x for c in clusters for x in c])
    if point is None:
        return None, None
    rng, values = random.Random(seed), []
    for _ in range(n):
        sample = [x for _ in clusters for x in clusters[rng.randrange(len(clusters))]]
        values.append(macro_f1(sample) or 0.0)
    values.sort()
    return round(point, 4), round(values[int(level * n)], 4)


# ---------------------------------------------------------------------------
# run (on the instance, inside the sealed replay pass)


def _validity(replay, kind, prompt, text, truncated):
    if text is None:
        return {"valid": False, "reason": "no reply"}
    if kind == "compact":
        reason = replay.contract_reason(prompt["prompt"], text)
        return {"valid": reason is None, "reason": reason}
    found = replay.envelope_reasons(prompt["agent"], text, truncated)
    return {"valid": not found, "reason": "; ".join(found)[:160] or None}


def model_paths(replay, group, prompts):
    """The base folder, adapter folder (or None), LoRA rank and tokenizer folder vLLM loads: the
    current engine's own, read from the sealed specification and the local cache."""
    import final_models
    backend, model_id = replay.model_key(prompts[0])
    if backend == replay.PRODUCER_BACKEND and final_models.mode() == "final":
        spec, paths = final_models.verify("producer")
        base = final_models.base_path("producer", spec)
        adapter = Path(paths["adapter"]).parent
        rank = int(json.loads((adapter / "adapter_config.json").read_text(encoding="utf-8"))["r"])
        return str(base), str(adapter), rank
    import agent_wrapper
    return agent_wrapper._local_checkpoint_path(model_id), None, None


def repetition_penalty(base):
    try:
        config = json.loads((Path(base) / "generation_config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1.0
    return float(config.get("repetition_penalty") or 1.0)


def child_env(base_python):
    env = {k: os.environ[k] for k in ENV_KEPT if k in os.environ}
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", VLLM_BATCH_INVARIANT="1", VLLM_NO_USAGE_STATS="1",
               DO_NOT_TRACK="1", VLLM_DO_NOT_TRACK="1", VLLM_ENABLE_V1_MULTIPROCESSING="0", VLLM_HOST_IP="127.0.0.1",
               VLLM_USE_V2_MODEL_RUNNER="1", VLLM_REPLAY_CHILD="1",
               PYTHONPATH=os.pathsep.join([str(ROOT / "scripts"), str(HERE)]))
    # The auxiliary venv's own executables (ninja for vLLM's JIT among them) come first.
    env["PATH"] = os.pathsep.join([str(Path(base_python).parent)] + ([env["PATH"]] if env.get("PATH") else []))
    return env


def work_root(prompts_path):
    """The pass's working folder: beside the sealed prompts file in the bundle's root, never under
    the pass's evidence folder, so prompts, replies and token ids stay on the instance (the
    controller packs `evidence/` and the root's own json and log files, never a folder there)."""
    return Path(prompts_path).resolve().parent / WORK


def pass_folder(prompts_path, run_id):
    """One working folder per pass, named by its run id, never shared between passes."""
    return work_root(prompts_path) / run_id


def run_child(aux_python, job, folder, runner=subprocess.run):
    """The child, started once; a child that cannot start or runs past its deadline is recorded
    as such, so the current engine's figures and the measurement still stand."""
    (folder / "job.json").write_text(json.dumps(job), encoding="utf-8")
    out = folder / "results.json"
    try:
        with open(folder / "child.stdout.log", "wb") as stdout, open(folder / "child.stderr.log", "wb") as stderr:
            done = runner([str(aux_python), str(CHILD), "--job", str(folder / "job.json"), "--out", str(out)],
                          env=child_env(aux_python), stdout=stdout, stderr=stderr, timeout=CHILD_SECONDS, cwd=str(folder))
        code = done.returncode
    except FileNotFoundError:
        return {"error": "the auxiliary environment's python is missing", "arms": {}, "exit_code": None}
    except subprocess.TimeoutExpired:
        return {"error": "the child ran past %d s" % CHILD_SECONDS, "arms": {}, "exit_code": None}
    result = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {"error": "no results", "arms": {}}
    result["exit_code"] = code
    return result


def free_gpu():
    """Every model the replay pass left resident, evicted before the child asks for the GPU (the
    tuned producer stays in final_models' cache after its backend is released, and an auditor in
    agent_wrapper's); returns the device's free and total bytes then, or None without CUDA."""
    import gc
    import final_models
    final_models.release_reference_residency()
    agent_wrapper = sys.modules.get("agent_wrapper")
    if agent_wrapper is not None:
        with agent_wrapper._QWEN_LOAD_LOCK:
            agent_wrapper._evict_generation_models()
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is None or not torch.cuda.is_available():
        return None
    torch.cuda.empty_cache()
    free, total = torch.cuda.mem_get_info()
    return {"free_bytes": int(free), "total_bytes": int(total)}


def quantisation(base):
    """The checkpoint's own quantisation, read from its config: both engines load this snapshot, so
    both run its NF4 weights at its compute dtype. Anything else is refused (None and the reason)."""
    try:
        config = json.loads((Path(base) / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "the checkpoint's config cannot be read"
    q = config.get("quantization_config") or {}
    if q.get("quant_method") != "bitsandbytes" or q.get("bnb_4bit_quant_type") != "nf4" or not q.get("load_in_4bit"):
        return None, "not a pre-quantised NF4 checkpoint: both engines would not load the same weights"
    return {"quant_method": "bitsandbytes", "bnb_4bit_quant_type": "nf4",
            "compute_dtype": q.get("bnb_4bit_compute_dtype")}, None


# vllm-bnb-plugin 0.0.3 (the wheel the lock pins) computes every 4-bit matmul in bfloat16 whatever
# the model dtype: quantization/linear.py `_apply_4bit_weight` casts x to torch.bfloat16, fills a
# bfloat16 output and casts it back to the input's dtype. The model dtype is vLLM's `dtype`.
VLLM_BNB_COMPUTE = "bfloat16"
# float32: the tuned producer's load (final_models.load, prepare_model_for_kbit_training) upcasts its
# non-4-bit layers; vLLM is then given float32, the plugin's 4-bit compute staying bfloat16.
MODEL_DTYPES = ("float16", "bfloat16", "float32")


def vllm_dtypes(current):
    """The dtypes vLLM runs a group in: the current engine's own model dtype (transformers 4.51's
    4-bit quantizer forces float16 for the other layers when no torch_dtype is given, the auditor
    path; the producer loads bfloat16), and the plugin's fixed 4-bit compute dtype."""
    return {"dtype": current.get("dtype"), "compute_dtype": VLLM_BNB_COMPUTE}


def dtype_refusal(current, quant):
    """None when vLLM can run the group in the current engine's own dtypes: its model dtype is one
    vLLM takes, and its 4-bit compute dtype is the plugin's. Anything else is refused with its
    reason, never compared in dtypes it did not run in."""
    if not current or not current.get("dtype"):
        return "the current engine's dtype was not recorded"
    if current["dtype"] not in MODEL_DTYPES:
        return "the current engine's model dtype %s is not one vLLM is given" % current["dtype"]
    if current.get("compute_dtype") != VLLM_BNB_COMPUTE:
        return ("the current engine's 4-bit compute dtype %s is not the plugin's %s"
                % (current.get("compute_dtype"), VLLM_BNB_COMPUTE))
    return None


def from_baseline(group, prompts):
    """The current engine of an earlier session, in the shape run() reads from replay_prompts.run."""
    b = group["baseline"]
    by_id = {p["prompt_id"]: {"reply": {"sha256": b["rows"][p["prompt_id"]].get("sha256")},
                              "contract": {"valid": b["rows"][p["prompt_id"]].get("valid"),
                                           "reason": b["rows"][p["prompt_id"]].get("reason")},
                              "items": b["rows"][p["prompt_id"]].get("items"),
                              "output_tokens": b["rows"][p["prompt_id"]].get("output_tokens"),
                              "max_new_tokens": b["rows"][p["prompt_id"]]["max_new_tokens"],
                              "reference_identical": b["rows"][p["prompt_id"]].get("reference_identical")}
             for p in prompts}
    return None, by_id, dict(b["texts"]), b["current"]["seconds"], {"None": b["current_dtype"]}


TIMING_SAME = "same session: both engines timed on this instance"
TIMING_CROSS = ("cross-session: the current engine's seconds are session %s's, on the same machine type; "
                "only the vLLM arm ran here")


def allowances(prompts, by_id):
    """Each prompt's output allowance: the one the current engine used, for vLLM too. A prompt
    whose allowance is not recorded is refused, never given a default."""
    out = {}
    for p in prompts:
        value = (by_id.get(p["prompt_id"]) or {}).get("max_new_tokens")
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError("prompt %s has no recorded output allowance" % p["prompt_id"])
        out[p["prompt_id"]] = value
    return out


def run(prompts_path, out, *, runner=subprocess.run, current=None, tokenizer_for=None, paths_for=None, run_id=None,
        evict=None, digest_for=None):
    """The pass (module text). `runner`, `current`, `tokenizer_for`, `paths_for`, `evict` and
    `digest_for` are the seams the proofs replace: the child's start, replay_prompts.run, the
    tokenizer loader, the model paths, the GPU eviction and the token-table digest."""
    import bare_model
    import reply_records
    replay = _replay()
    out = Path(out)
    value = json.loads(Path(prompts_path).read_text(encoding="utf-8"))
    load_value(value)
    aux_python = Path(prompts_path).resolve().parent / AUX_PYTHON
    current = current or replay.run
    evict = evict or free_gpu
    context = bare_model.RunContext(out, run_id or ("vllm-replay-" + uuid.uuid4().hex[:12]))
    replies = out / "audit" / "model_replies"
    replies.mkdir(parents=True, exist_ok=True)
    work = pass_folder(prompts_path, context.run_id)
    groups = {}
    for group in value["groups"]:
        name, kind, prompts = group["name"], group["kind"], group["file"]["prompts"]
        folder = work / name
        folder.mkdir(parents=True)
        (folder / "replay_prompts.json").write_text(json.dumps(group["file"]), encoding="utf-8")
        # The current engine: replay_prompts.run, unchanged, its generation loop timed by itself
        # (no model load), its records moved into the pass's folder.
        if "baseline" in group:
            # The vLLM arm alone: the current engine is the earlier session's, as measured.
            measured, by_id, texts, current_seconds, dtypes = from_baseline(group, prompts)
        else:
            kept, seconds, dtypes = {}, {}, {}
            measured = current(folder / "replay_prompts.json", folder / "current", paths=[group["current_path"]],
                               texts=kept, seconds=seconds, dtypes=dtypes)
            current_seconds = seconds.get(group["current_path"])
            for record in sorted((folder / "current" / "audit" / "model_replies").glob("*.json")):
                shutil.move(str(record), str(replies / ("current_" + record.name)))
            by_id = {r["prompt_id"]: r[group["current_path"]] for r in measured["rows"]}
            texts = kept.get(group["current_path"], {})
        # vLLM, in the auxiliary environment, on the same snapshot.
        base, adapter, rank = (paths_for or model_paths)(replay, group, prompts)
        quant, refused = quantisation(base)
        current_dtype = next(iter(dtypes.values()), None) if len(dtypes) == 1 else None
        if quant is not None:
            refused = dtype_refusal(current_dtype, quant)
            if refused:
                quant = None
        gpu = evict()
        child = {"error": refused, "arms": {}}
        if quant is not None:
            tok = (tokenizer_for or _tokenizer)(base)
            allowed = allowances(prompts, by_id)
            eos = _eos(replay, prompts)
            job = {"observer": _observer(), "model": base, "tokenizer": base, "adapter": adapter, "lora_rank": rank,
                   "batch": int(value["batch"]), "dtype": vllm_dtypes(current_dtype)["dtype"], "max_model_len": 32768,
                   "repetition_penalty": repetition_penalty(base),
                   "token_table_sha256": (digest_for or _table_digest)(tok),
                   "prompts": [{"prompt_id": p["prompt_id"], "token_ids": tok(p["prompt"], add_special_tokens=False)["input_ids"],
                                "max_new_tokens": allowed[p["prompt_id"]], "eos": eos,
                                "constraint": None if kind == "plain" else {"prompt": p["prompt"],
                                                                             "agent": p["agent"] if kind == "envelope" else None}}
                               for p in prompts]}
            child = run_child(aux_python, job, folder, runner)
            child["network"] = network_events(folder)
        child["gpu_before_child"], child["quantisation"], child["current_dtype"] = gpu, quant, current_dtype
        child["current_spec"] = (dict(group["baseline"]["specification"] or {}, session=group["baseline"]["run_id"])
                                 if "baseline" in group else current_spec(replay, group, prompts, base, adapter, quant, current_dtype))
        groups[name] = summarise(replay, reply_records, context, group, prompts, by_id, texts, current_seconds,
                                 measured, child)
    result = {"schema": "vllm-replay-measurement-v1", "run_id": context.run_id,
              "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "prompts": sum(len(g["file"]["prompts"]) for g in value["groups"]), "groups": groups,
              "failures": sum(g["failures"] for g in groups.values()),
              "reads": "prompts and replies on the instance only; this file holds ids, hashes, counts and seconds"}
    (out / replay.MEASUREMENT_FILE).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def platform_spec(torch=None):
    """The platform an arm ran on (D-608): OS, machine, Python, torch and its CUDA, the GPU and its
    driver (nvidia-smi, a local process). Read in each engine's own process."""
    import platform
    spec = {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()}
    if torch is not None:
        spec.update(torch=torch.__version__, torch_cuda=getattr(torch.version, "cuda", None),
                    gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
    try:
        done = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                              capture_output=True, timeout=20)
        spec["nvidia_smi"] = done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        spec["nvidia_smi"] = None
    return spec


def _file_sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def current_spec(replay, group, prompts, base, adapter, quant, dtypes=None):
    """The current engine's full specification (D-608): engine and versions, the platform, the
    snapshot and its quantisation, the adapter and its digest, the attention path and the frozen
    decoding policy's kwargs."""
    import decoding_policy
    torch = sys.modules.get("torch")
    transformers = sys.modules.get("transformers")
    backend = replay.model_key(prompts[0])[0]
    return dict(platform_spec(torch), engine="transformers", engine_version=getattr(transformers, "__version__", None),
                bitsandbytes=_version("bitsandbytes"), peft=_version("peft"), model=str(base),
                config_sha256=_file_sha(Path(base) / "config.json"), quantisation=quant,
                dtype=(dtypes or {}).get("dtype"), compute_dtype=(dtypes or {}).get("compute_dtype"),
                lora=None if not adapter else {"adapter": str(adapter),
                                               "weights_sha256": _file_sha(Path(adapter) / "adapter_model.safetensors")},
                path=group["current_path"], decoding=decoding_policy.policy(backend)["kwargs"],
                repetition_penalty=repetition_penalty(base), seed=None, batch=1,
                deterministic=bool(torch.are_deterministic_algorithms_enabled()) if torch is not None else None)


def _version(name):
    import importlib.metadata
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _table_digest(tok):
    import vllm_constraint
    return vllm_constraint.table_digest(tok)


def _observer():
    """The network denial the runner applied to itself (tools/cloud_run_observer.py, as imported),
    which the child applies to itself before importing vLLM."""
    module = sys.modules.get("cloud_run_observer")
    if module is None:
        import importlib
        sys.path.insert(0, str(ROOT / "tools"))
        module = importlib.import_module("cloud_run_observer")
    return str(Path(module.__file__).resolve())


def network_events(folder):
    """The child's blocked network attempts, counted by kind, from its own log."""
    counts = {}
    path = Path(folder) / "child_network.jsonl"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("event") == "network_blocked":
                counts[row.get("network_kind")] = counts.get(row.get("network_kind"), 0) + 1
    return {"denied_in_child": path.is_file(), "blocked": counts}


def _tokenizer(base):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(base, local_files_only=True)


def _eos(replay, prompts):
    import decoding_policy
    backend = replay.model_key(prompts[0])[0]
    return [int(e) for e in decoding_policy.policy(backend)["kwargs"]["eos_token_id"]]


def summarise(replay, reply_records, context, group, prompts, by_id, texts, current_seconds, measured, child):
    name, kind = group["name"], group["kind"]
    arms = {"current": {"seconds": round(current_seconds, 3),
                        "output_tokens": sum(int(r.get("output_tokens") or 0) for r in by_id.values())}}
    rows, failures = {}, 0
    for p in prompts:
        pid = p["prompt_id"]
        cur = by_id[pid]
        # replay_prompts.run judges compact and envelope replies itself; a plain producer reply is
        # judged here by the same validator, complete only when it stopped inside its allowance.
        judged = cur.get("contract") or _validity(replay, kind, p, texts.get(pid),
                                                   int(cur.get("output_tokens") or 0) >= int(cur.get("max_new_tokens") or 0))
        rows[pid] = {"agent": p.get("agent"), "current": {"sha256": (cur.get("reply") or {}).get("sha256"),
                                                          "valid": judged.get("valid"),
                                                          "reason": judged.get("reason"),
                                                          "output_tokens": cur.get("output_tokens"),
                                                          "items": (cur["items"] if "items" in cur else
                                                                    _items(texts.get(pid)) if judged.get("valid") else 0),
                                                          "reference_identical": cur.get("reference_identical")},
                     "current_labels": (NOT_KEPT if "baseline" in group and pid not in texts
                                        else labels(p.get("agent"), texts.get(pid))),
                     "current_text_kept": pid in texts}
    for arm in ARMS[1:]:
        seen = (child.get("arms") or {}).get(arm)
        if not seen:
            arms[arm] = {"error": child.get("error") or "not run", "exit_code": child.get("exit_code")}
            failures += len(prompts)
            for p in prompts:
                _record(reply_records, context, p, arm, None, "vllm_not_run")
            continue
        arms[arm] = {"seconds": seen["seconds"], "output_tokens": seen["output_tokens"]}
        for p in prompts:
            pid = p["prompt_id"]
            got = seen["rows"].get(arm + ":" + pid) or {}
            text = got.get("text")
            truncated = got.get("finish_reason") != "stop"
            check = _validity(replay, kind, p, text, truncated)
            rows[pid][arm] = {"sha256": _sha(text) if isinstance(text, str) else None, "valid": check["valid"],
                              "items": _items(text) if check["valid"] else 0,
                              "reference_identical": (None if not p.get("reference_reply_sha256") or not isinstance(text, str)
                                                      else _sha(text) == p["reference_reply_sha256"]),
                              "reason": check["reason"], "output_tokens": got.get("output_tokens"),
                              "finish_reason": got.get("finish_reason"), "constraint": got.get("constraint"),
                              "labels": labels(p.get("agent"), text)}
            failures += int(text is None)
            _record(reply_records, context, p, arm, text, None if text is not None else "no reply")
    for arm, seen in arms.items():
        if seen.get("seconds") and seen.get("output_tokens") is not None:
            seen["tokens_per_second"] = round(seen["output_tokens"] / seen["seconds"], 3)
    for arm in ARMS[1:]:
        if arms[arm].get("seconds") and arms["current"]["seconds"]:
            arms[arm]["speed_factor"] = round(arms["current"]["seconds"] / arms[arm]["seconds"], 3)
    agreement = group_agreement(rows, {arm for arm in ARMS[1:] if "error" not in arms[arm]})
    return {"kind": kind, "current_path": group["current_path"], "prompts": len(prompts), "arms": arms,
            "timing": TIMING_CROSS % group["baseline"]["run_id"] if "baseline" in group else TIMING_SAME,
            "current_texts_kept": sum(1 for r in rows.values() if r.get("current_text_kept")),
            "current_labels_parsed": sum(1 for r in rows.values() if r.get("current_labels") not in (None, NOT_KEPT)),
            "agreement": agreement, "stability_finding": stability_finding(agreement),
            "versions": child.get("versions"), "engine_seconds": child.get("engine_seconds"),
            "specification": {"current": child.get("current_spec"), "vllm": child.get("spec")},
            "peak_gpu_bytes": child.get("peak_gpu_bytes"), "child_error": child.get("error"),
            "network": child.get("network"), "gpu_before_child": child.get("gpu_before_child"),
            "quantisation": child.get("quantisation"), "loaded": child.get("loaded"),
            "current_dtype": child.get("current_dtype"),
            "vllm_dtype": vllm_dtypes(child["current_dtype"]) if child.get("current_dtype") else None,
            "token_table_sha256": child.get("token_table_sha256"),
            "failures": failures, "figures": figures(rows, prompts),
            "rows": {pid: {k: ({kk: vv for kk, vv in v.items() if kk != "labels"} if isinstance(v, dict) else v)
                           for k, v in r.items() if k not in ("current_labels", "current_text_kept")} for pid, r in rows.items()}}


STABILITY = ("a difference between the engines is a cross-platform stability finding (D-608), "
             "recorded in aggregate; it is never a failure and never a stop")


def group_agreement(rows, ran):
    """Per vLLM arm, over the group: replies byte-identical with the current engine, and item
    labels equal to the current engine's (the label field LABEL_FIELDS names, item by item). An
    arm that never ran (a refusal, a child error) is not measured: every figure None."""
    out = {}
    for arm in ARMS[1:]:
        if arm not in ran:
            out[arm] = {"measured": False, "replies": None, "byte_identical": None, "byte_identical_rate": None,
                        "labels": None, "labels_equal": None, "label_agreement_rate": None}
            continue
        replies = identical = labels_total = labels_equal = 0
        for r in rows.values():
            replies += 1
            mine = r.get(arm) or {}
            identical += int(mine.get("sha256") is not None and mine.get("sha256") == r["current"]["sha256"])
            for a, b in pairs_of(r.get("current_labels"), mine.get("labels")):
                labels_total += 1
                labels_equal += int(a == b)
        out[arm] = {"measured": True, "replies": replies, "byte_identical": identical,
                    "byte_identical_rate": round(identical / replies, 4) if replies else None,
                    "labels": labels_total, "labels_equal": labels_equal,
                    "label_agreement_rate": round(labels_equal / labels_total, 4) if labels_total else None}
    return out


def stability_finding(agreement):
    """The group's D-608 field: whether the engines differed, named a stability finding; None when
    no vLLM arm ran, since nothing was compared."""
    measured = [a for a in agreement.values() if a["measured"]]
    if not measured:
        return {"differs": None, "measured_arms": 0, "reading": STABILITY}
    differs = any(a["byte_identical"] < a["replies"] or (a["labels"] and a["labels_equal"] < a["labels"])
                  for a in measured)
    return {"differs": differs, "measured_arms": len(measured), "reading": STABILITY}


def _items(text):
    found = items_of(text) if isinstance(text, str) else None
    return len(found) if found else 0


def figures(rows, prompts):
    """Per agent: replies, valid on each arm, byte-identical with the current engine, batch
    identical with alone, and the label macro-F1 of each vLLM arm against the current engine's
    labels, with its paired bootstrap lower bound over prompts."""
    out = {}
    for p in prompts:
        agent = p.get("agent") or "PROCESSOR"
        r = rows[p["prompt_id"]]
        f = out.setdefault(agent, {"replies": 0, "valid": {a: 0 for a in ARMS}, "items_in_valid_replies": {a: 0 for a in ARMS},
                                   "identical_to_reference": {a: 0 for a in ARMS}, "with_reference": 0,
                                   "identical_to_current": {a: 0 for a in ARMS[1:]},
                                   "batch_identical_to_alone": 0, "_pairs": {a: [] for a in ARMS[1:]}})
        f["replies"] += 1
        f["with_reference"] += int(bool(p.get("reference_reply_sha256")))
        for arm in ARMS:
            f["valid"][arm] += int(bool((r.get(arm) or {}).get("valid")))
            f["items_in_valid_replies"][arm] += int((r.get(arm) or {}).get("items") or 0)
            f["identical_to_reference"][arm] += int((r.get(arm) or {}).get("reference_identical") is True)
        for arm in ARMS[1:]:
            mine = (r.get(arm) or {}).get("sha256")
            f["identical_to_current"][arm] += int(mine is not None and mine == r["current"]["sha256"])
            f["_pairs"][arm].append(pairs_of(r.get("current_labels"), (r.get(arm) or {}).get("labels")))
        b1, bn = (r.get("vllm_b1") or {}).get("sha256"), (r.get("vllm_batch") or {}).get("sha256")
        f["batch_identical_to_alone"] += int(b1 is not None and b1 == bn)
    for f in out.values():
        pairs = f.pop("_pairs")
        f["label_macro_f1_vs_current"] = {arm: dict(zip(("point", "lower_bound"), bootstrap_lower(pairs[arm])))
                                          for arm in ARMS[1:]}
        # D-608: a difference is a finding, recorded in aggregate.
        f["agreement_rate_with_current"] = {arm: round(f["identical_to_current"][arm] / f["replies"], 4)
                                            for arm in ARMS[1:]}
        f["differing_from_current"] = {arm: f["replies"] - f["identical_to_current"][arm] for arm in ARMS[1:]}
        f["batch_agreement_rate"] = round(f["batch_identical_to_alone"] / f["replies"], 4)
    return out


def _record(reply_records, context, prompt, arm, text, error):
    call = reply_records.write(context, agent="VLLM_REPLAY", backend=prompt.get("backend") or "local_producer",
                               model_id=prompt.get("model_id") or "", model_mode="replay", payload=prompt["prompt"],
                               payload_form="rendered_prompt", reply=text, ok=error is None, error=error or "",
                               decoding={"arm": arm, "max_new_tokens": prompt.get("max_new_tokens")}, sensitive=True,
                               phase="VLLM_REPLAY", doc_id=prompt.get("doc_id") or "")
    if not call:
        raise RuntimeError("the reply record for prompt %s, arm %s could not be written" % (prompt["prompt_id"], arm))
    return call


def main(argv=None):
    parser = argparse.ArgumentParser(prog="vllm_replay.py", allow_abbrev=False, description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    b = commands.add_parser("build", allow_abbrev=False)
    b.add_argument("--group", action="append", required=True, help="NAME=replay_prompts.json")
    b.add_argument("--batch", type=int, default=16)
    b.add_argument("--out", required=True)
    b.add_argument("--baseline", default=None,
                   help="an earlier pass's replay_measurement.json: run the vLLM arms alone against its current engine")
    b.add_argument("--texts-from", action="append", default=[],
                   help="a reply-records folder or a DEV replies .jsonl whose replies give the baseline's texts by digest")
    args = parser.parse_args(argv)
    groups = []
    for spec in args.group:
        name, _, path = spec.partition("=")
        if not name or not path:
            parser.error("--group is NAME=FILE")
        groups.append((name, path))
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8")) if args.baseline else None
    value = build(groups, args.out, batch=args.batch, baseline=baseline, texts_by_sha=saved_texts(args.texts_from))
    print(json.dumps({"prompt_count": value["prompt_count"], "groups": [(g["name"], g["kind"], len(g["file"]["prompts"]))
                                                                         for g in value["groups"]]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
