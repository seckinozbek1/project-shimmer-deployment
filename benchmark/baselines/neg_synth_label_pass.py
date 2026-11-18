#!/usr/bin/env python3
"""Role V's blind labelling pass on the sealed replay pass (D-706 item 1, NEG-SYNTH-A; lane/v-synlab-launch).

Seckin's decision of 18 November 2026 14:20: role V launches its own blind labelling job on Lambda under the budget
guard, the ledger and the reaper, and the lead sees counts only. The job rides the replay pass as EMBED-ROUTE-A's
embedding does: an exposed B1 bundle sealed with `--replay-prompts <this file>`; replay_prompts.py hands a file of
this schema to `run` here, so no bound controller file changes.

The split, so nothing on the instance needs the laptop's tools:
  - laptop, before the seal (tools/neg_synth_label.py `build-pass`): role S's label sheets are checked
    (an answer field refuses the sheet unread), every position's question rendered from the declared template, and
    the prompts written here with the labeller block of config/neg_synth.json and the sheets' digests;
  - instance (`run`): the declared labeller resolved from the SEALED model cache only (the run's network is denied
    and the hub is offline), the first candidate whose snapshot is sealed, whose config the pinned transformers
    knows, and whose card states the declared terms; a Qwen, Phi, Claude, GPT, generator-family or dated id is
    refused (`check_model`, the one rule tools/neg_synth_label.py also uses); greedy decoding as declared; one
    reply record per prompt (REPLIES-A) and replay_measurement.json with digests and counts only;
  - laptop, after the fetch (tools/neg_synth_label.py `read-pass`): each saved reply read once by the project's one
    form reader (tools/answer_form.py, ANSWER-FORM-A) into labels_<set>.json and LABELLER_<set>.json.

Nothing here prints a text, a quote, an item id or a label: counts and digests only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "scripts"

SCHEMA = "neg-synth-label-pass-v1"
MEASUREMENT_SCHEMA = "neg-synth-label-pass-measurement-v1"
MEASUREMENT_FILE = "replay_measurement.json"
PROGRESS_FILE = "label_progress.json"
AGENT_LABEL = "NEG_SYNTH_LABELLER"
PHASE = "neg_synth_label"
PATH = "sdpa"
PROMPT_KEYS = {"prompt_id", "set", "item_id", "position_id", "prompt", "prompt_sha256", "answers"}
# The reply's fields whose declared answers are scored at their deciding token (D-736: the labeller's probability
# over the declared answer set, CHOICE-A's rule, read from the generation's own forward passes, no extra pass).
FIELDS = ("article", "wording", "stance", "firm_limit")
CONFIDENCE_FIELD = "stance"
LABELLER_KEYS = ("family", "candidates", "terms_required", "families_never_labeller", "decoding")
SET_NAME = re.compile(r"^[a-z][a-z0-9]*_[0-9]+$")
# The same form as tools/neg_synth.py's _DATED: a repository id ending in a date is a dated snapshot.
DATED = re.compile(r"(?:^|[-_@])20\d{2}-?\d{2}-?\d{2}$")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ---------------------------------------------------------------------------
# the model rule (shared with tools/neg_synth_label.py)


def check_model(model_id, labeller, generator_family):
    """The labeller's model: a family the system under test and the generator never use, a bare id."""
    mid = str(model_id or "").strip()
    low = mid.lower()
    if not mid:
        raise ValueError("refused: no labeller model resolved")
    if any(f in low for f in labeller["families_never_labeller"]) or str(generator_family).lower() in low:
        raise ValueError("refused: a family of the system under test or of the generator never labels")
    if labeller["family"] not in low:
        raise ValueError("refused: the labeller's family is declared as %s" % labeller["family"])
    if DATED.search(mid):
        raise ValueError("refused: a dated snapshot id; a bare repository id read live is recorded")
    return mid


# ---------------------------------------------------------------------------
# the file


def is_prompts_file(value):
    return isinstance(value, dict) and value.get("schema") == SCHEMA


def is_prompts_path(path):
    try:
        with open(path, "rb") as fh:
            head = fh.read(256)
    except OSError:
        return False
    return (b'"schema": "' + SCHEMA.encode() + b'"') in head or (b'"schema":"' + SCHEMA.encode() + b'"') in head


def write_file(path, labeller, generator_family, template_sha256, sets, prompts):
    """The prompts file, schema first (so `is_prompts_path` reads the head only). `sets` is
    {name: {sheets_sha256, items, positions}}; `prompts` the rendered questions in order."""
    value = {"schema": SCHEMA, "written_at": _now(),
             "labeller": {k: labeller[k] for k in LABELLER_KEYS}, "generator_family": generator_family,
             "template_sha256": template_sha256, "sets": sets, "prompt_count": len(prompts), "prompts": prompts}
    check_file(value)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return value


def check_file(value):
    """Every refusal of a labelling prompts file; returns its prompts."""
    if not is_prompts_file(value):
        raise ValueError("not a labelling pass file (%s)" % SCHEMA)
    lab = value.get("labeller") or {}
    if set(lab) != set(LABELLER_KEYS) or not lab["candidates"]:
        raise ValueError("the file's labeller block is not the declared one")
    if lab["decoding"].get("do_sample") is not False or int(lab["decoding"].get("max_new_tokens", 0)) <= 0:
        raise ValueError("the labeller decodes greedily within a declared allowance")
    for repo in lab["candidates"]:
        check_model(repo, lab, value.get("generator_family", ""))
    sets, prompts = value.get("sets") or {}, value.get("prompts")
    if not sets or not all(SET_NAME.match(s) for s in sets):
        raise ValueError("the file names no set, or a set of another form")
    if not isinstance(prompts, list) or not prompts or value.get("prompt_count") != len(prompts):
        raise ValueError("the file holds no prompt, or its count is wrong")
    ids, per_set = set(), {}
    for p in prompts:
        if set(p) != PROMPT_KEYS:
            raise ValueError("a prompt carries other fields than %s" % sorted(PROMPT_KEYS))
        answers = p["answers"]
        if not isinstance(answers, dict) or set(answers) - set(FIELDS) or CONFIDENCE_FIELD not in answers \
                or any(not isinstance(v, list) or len(v) < 2 or len(set(v)) != len(v) for v in answers.values()):
            raise ValueError("a prompt's declared answers are not one list of two or more per field")
        if not isinstance(p["prompt"], str) or _sha(p["prompt"]) != p["prompt_sha256"]:
            raise ValueError("a prompt does not match its SHA-256")
        if p["prompt_id"] in ids or p["set"] not in sets:
            raise ValueError("a prompt id repeats, or a prompt names an undeclared set")
        ids.add(p["prompt_id"])
        per_set[p["set"]] = per_set.get(p["set"], 0) + 1
    if any(per_set.get(s, 0) != int(sets[s]["positions"]) for s in sets):
        raise ValueError("the prompts do not add up to each set's declared positions")
    return prompts


def read_file(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_prompts(path):
    return check_file(read_file(path))


# ---------------------------------------------------------------------------
# on the instance: the sealed cache, offline


def hub_cache():
    for name in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE"):
        if os.environ.get(name):
            return Path(os.environ[name])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def card_terms(snapshot):
    """The licence the model card's front matter states, or ''."""
    card = Path(snapshot) / "README.md"
    if not card.is_file():
        return ""
    lines = card.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.lower().startswith("license:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return ""


def known_model_type(model_type):
    try:
        from transformers import CONFIG_MAPPING
    except ImportError:
        return False
    return model_type in CONFIG_MAPPING


def sealed_info(repo, cache=None, known=known_model_type):
    """What the sealed cache says of one candidate: {sealed, revision, terms, loadable}. Offline: nothing is fetched."""
    folder = Path(cache or hub_cache()) / ("models--" + repo.replace("/", "--"))
    ref = folder / "refs" / "main"
    if not ref.is_file():
        return {"sealed": False}
    revision = ref.read_text(encoding="utf-8").strip()
    snapshot = folder / "snapshots" / revision
    try:
        model_type = json.loads((snapshot / "config.json").read_text(encoding="utf-8")).get("model_type")
    except (OSError, ValueError):
        model_type = None
    return {"sealed": snapshot.is_dir(), "revision": revision, "terms": card_terms(snapshot),
            "loadable": bool(model_type) and bool(known(model_type)), "model_type": model_type}


def resolve(value, info=None):
    """The first declared candidate the sealed cache holds, that the pinned transformers can load and whose card
    states the declared terms; every candidate passed over is counted by why. None resolving refuses the run."""
    lab = value["labeller"]
    info = info or sealed_info
    passed = {}
    for repo in lab["candidates"]:
        meta = info(repo) or {}
        why = ("not_sealed" if not meta.get("sealed") else "not_loadable" if not meta.get("loadable")
               else "other_terms" if str(meta.get("terms", "")).lower() != lab["terms_required"] else None)
        if why is None:
            return {"model_id": check_model(repo, lab, value["generator_family"]), "revision": meta.get("revision"),
                    "terms": lab["terms_required"], "passed_over": passed}
        passed[repo] = why
    raise ValueError("refused: no declared labeller candidate is sealed, loadable and %s (%s)"
                     % (lab["terms_required"], ", ".join("%s" % w for w in passed.values())))


KEY_OPEN = {f: re.compile(r'"%s"\s*:\s*"$' % f) for f in FIELDS}


def field_decisions(gen_ids, step_logits, decode, encode, answers):
    """{field: decision or {refused}} for each declared field: the deciding step is the first generated step whose
    decoded prefix ends with the field's key and its opening quote; there the step's own logits are read over the
    declared answers' first tokens after that prefix (choice_decision.bind and probabilities, CHOICE-A: one
    forward pass, the generation's own). Refused, never guessed, when the field is not reached, the prefix does not
    re-encode to the generated tokens, or two answers share a first token."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import choice_decision as cd
    out = {}
    for field, values in answers.items():
        step = next((k for k in range(1, len(gen_ids)) if KEY_OPEN[field].search(decode(gen_ids[:k]))), None)
        if step is None:
            out[field] = {"refused": "field_not_reached"}
            continue
        prefix = decode(gen_ids[:step])
        if list(encode(prefix)) != list(gen_ids[:step]):
            out[field] = {"refused": "prefix_retokenised"}
            continue
        try:
            q = cd.bind(cd.declare(prefix, [{"label": v, "surface": v} for v in values]), encode)
            shares, mass = cd.probabilities(step_logits(step), [a["token_id"] for a in q["answers"]])
        except cd.ChoiceRefused as exc:
            out[field] = {"refused": "choice:" + type(exc).__name__ + ":" + str(exc).split(" ")[0]}
            continue
        probs = {a["label"]: round(float(x), 6) for a, x in zip(q["answers"], shares)}
        top = max(probs, key=probs.get)
        out[field] = {"probabilities": probs, "top": top, "top_probability": probs[top],
                      "declared_mass": round(float(mass), 6), "step": step}
    return out


def confidence_of(decisions):
    """The label's confidence: the deciding field's top probability over its declared answers, or None."""
    d = decisions.get(CONFIDENCE_FIELD) or {}
    return d.get("top_probability")


PREFLIGHT_FILE = ROOT / "config" / "labeller_preflight.json"


def model_preflight(model_id, model, tok, declared=None):
    """{model_class, markers, eos_token} once the labeller loaded, before its first prompt: the class the pinned
    transformers resolved, the tokenizer's built-in chat template carrying every declared marker, and its declared
    end-of-text token (config/labeller_preflight.json). Refused, before any prompt, on anything else."""
    declared = declared if declared is not None else json.loads(PREFLIGHT_FILE.read_text(encoding="utf-8"))
    want = (declared.get("models") or {}).get(model_id)
    if not want:
        raise ValueError("refused: the labeller %s has no preflight entry" % model_id)
    got_class = type(model).__name__
    if got_class != want["model_class"]:
        raise ValueError("refused: the labeller loaded as %s, not %s" % (got_class, want["model_class"]))
    template = getattr(tok, "chat_template", None) or ""
    missing = [m for m in want["chat_template_markers"] if m not in template]
    if missing:
        raise ValueError("refused: the tokenizer's chat template lacks %s" % ", ".join(missing))
    if getattr(tok, "eos_token", None) != want["eos_token"]:
        raise ValueError("refused: the tokenizer's end-of-text token is not %s" % want["eos_token"])
    return {"model_class": got_class, "markers": list(want["chat_template_markers"]), "eos_token": want["eos_token"]}


def hf_generate(model_id, revision, decoding):
    """Greedy generation with the sealed model on the instance's GPU (never in a proof)."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_id, revision=revision, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, local_files_only=True,
                                                 torch_dtype=torch.bfloat16, device_map="cuda",
                                                 attn_implementation=PATH)
    model.eval()
    checked = model_preflight(model_id, model, tok)

    def generate(prompt, answers):
        ids = tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True,
                                      return_tensors="pt").to(model.device)
        with torch.no_grad():
            gen = model.generate(ids, attention_mask=torch.ones_like(ids), do_sample=False,
                                 max_new_tokens=int(decoding["max_new_tokens"]), pad_token_id=tok.eos_token_id,
                                 output_scores=True, return_dict_in_generate=True)
        new = gen.sequences[0, ids.shape[1]:].tolist()
        # scores[k] are the logits that chose generated token k, so the deciding step k reads scores[k].
        decisions = field_decisions(new, lambda k: gen.scores[k][0].float().tolist(),
                                    lambda t: tok.decode(t, skip_special_tokens=True),
                                    lambda text: tok.encode(text, add_special_tokens=False), answers)
        return {"reply": tok.decode(new, skip_special_tokens=True), "prompt_tokens": int(ids.shape[1]),
                "new_tokens": len(new), "decisions": decisions}
    generate.preflight = checked
    return generate


def run(prompts_path, out, *, paths=(PATH,), decision=None, max_new_tokens=None, generate=None, info=None,
        run_id=None):
    """Every prompt asked once, one reply record each; the measurement written only when every call was saved.
    `generate(prompt, answers) -> {reply, prompt_tokens, new_tokens, decisions}` and `info(repo)` are injected by
    the proofs. Each reply record carries its fields' decisions (probabilities and labels of the declared answer
    set, no text); the measurement row carries the confidence alone."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import bare_model
    import reply_records
    if list(paths) != [PATH] or decision is not None or max_new_tokens is not None:
        raise ValueError("a labelling pass runs the %s path alone, no decision, no token allowance" % PATH)
    value = read_file(prompts_path)
    prompts = check_file(value)
    model = resolve(value, info)
    decoding = dict(value["labeller"]["decoding"])
    gen = generate or hf_generate(model["model_id"], model["revision"], decoding)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    context = bare_model.RunContext(out, run_id or ("label-" + uuid.uuid4().hex[:12]))
    started, rows, at_allowance = time.perf_counter(), [], 0
    for n, p in enumerate(prompts, 1):
        t0 = time.perf_counter()
        got = gen(p["prompt"], p["answers"])
        reply, prompt_tokens, new_tokens = got["reply"], got["prompt_tokens"], got["new_tokens"]
        decisions = got["decisions"]
        call = reply_records.write(context, agent=AGENT_LABEL, backend="local_labeller", model_id=model["model_id"],
                                   model_mode="sealed", payload=p["prompt"], payload_form="chat_user",
                                   reply=reply, ok=True, error="", decoding=decoding, sensitive=False,
                                   phase=PHASE, doc_id=p["prompt_id"],
                                   attention={"implementation": PATH, "revision": model["revision"]},
                                   decision={"schema": "neg-synth-label-fields-v1", "fields": decisions})
        if not call:
            raise RuntimeError("the reply record of prompt %d could not be written" % n)
        at_allowance += int(new_tokens >= int(decoding["max_new_tokens"]))
        rows.append({"prompt_id": p["prompt_id"], "set": p["set"], "prompt_sha256": p["prompt_sha256"],
                     "reply_sha256": _sha(reply), "call_id": call, "prompt_tokens": prompt_tokens,
                     "confidence": confidence_of(decisions),
                     "decisions_sha256": _sha(json.dumps(decisions, sort_keys=True)),
                     "new_tokens": new_tokens, "seconds": round(time.perf_counter() - t0, 3)})
        (out / PROGRESS_FILE).write_text(json.dumps({"done": n, "prompts": len(prompts),
                                                     "seconds": round(time.perf_counter() - started, 1)}),
                                         encoding="utf-8")
    measurement = {"schema": MEASUREMENT_SCHEMA, "model_id": model["model_id"], "revision": model["revision"],
                   "terms": model["terms"], "passed_over": model["passed_over"], "decoding": decoding,
                   "path": PATH, "prompts_file_sha256": hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest(),
                   "template_sha256": value["template_sha256"], "sets": value["sets"], "rows": rows,
                   "at_allowance": at_allowance, "prompts": len(prompts), "failures": 0,
                   "preflight": getattr(gen, "preflight", None),
                   "seconds": round(time.perf_counter() - started, 1), "finished_at": _now()}
    (out / MEASUREMENT_FILE).write_text(json.dumps(measurement, indent=1, sort_keys=True), encoding="utf-8")
    return measurement
