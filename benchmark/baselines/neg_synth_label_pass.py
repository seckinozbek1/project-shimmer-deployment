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

D-799 (operator, 19 November 2026 15:28; lane/label-constrained): a `neg-synth-label-pass-v2` file carries, per
prompt, a `constraint` block (the fixed key order, the article ids, the stances, the firm-limit values, and each
article's own count of bracketed wordings). Its replies are generated under a per-request logits constraint
(LabelGrammar, run by DECODING-B's own processor, scripts/contract_decoding.ContractProcessor): every token whose text
would leave the one reply object is set to -inf, so only `{"article": "<id>", "wording": "<whole or 1..n of that
article>", "stance": "<declared>", "firm_limit": "<declared>"}` can be generated, keys, order and punctuation forced,
the wording list chosen after the article is decoded. The declared greedy decoding is unchanged (the constraint is a
logits processor beside it). A reply still outside the language is never read by guess here: it is counted by
reason in replay_measurement.json (`constraint.by_reason`). A `neg-synth-label-pass-v1` file (no constraint) is read,
checked and run exactly as before, so the saved first pass stays re-readable.
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
# D-799: a v2 file's prompts each carry a `constraint` block; v1 files (no constraint) are read unchanged.
SCHEMA_V2 = "neg-synth-label-pass-v2"
SCHEMAS = (SCHEMA, SCHEMA_V2)
CONSTRAINT_SCHEMA = "neg-synth-label-constraint-v1"
CONSTRAINT_NAME = "neg_synth_label_reply"
CONSTRAINT_VERSION = 1
CONSTRAINT_KEYS = {"schema", "order", "values", "wording"}
CONSTRAINT_VALUE_FIELDS = ("article", "stance", "firm_limit")
# Why a constrained reply is still outside the one reply object (counted, never read by guess).
INSIDE = "inside"
OUTSIDE_REASONS = ("dead_end", "at_allowance", "unfinished", "left_language")
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
# D-843: also the D-798 validation set's names (`validation`, `validation_strata`), so it can be labelled as named
# (OPEN_ITEMS 164); still lower-case letters and digits in underscore-joined words, nothing else.
SET_NAME = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
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
    return isinstance(value, dict) and value.get("schema") in SCHEMAS


def is_prompts_path(path):
    try:
        with open(path, "rb") as fh:
            head = fh.read(256)
    except OSError:
        return False
    return any((b'"schema": "' + s.encode() + b'"') in head or (b'"schema":"' + s.encode() + b'"') in head
               for s in SCHEMAS)


def _plain_value(v):
    """A declared value the reply object can carry with no JSON escape: a non-empty string with no quote, no
    backslash and no control character."""
    return isinstance(v, str) and bool(v) and not any(c in '"\\' or c < " " for c in v)


def check_constraint(c, answers):
    """Every refusal of one prompt's constraint block (D-799); returns it."""
    if not isinstance(c, dict) or set(c) != CONSTRAINT_KEYS or c["schema"] != CONSTRAINT_SCHEMA:
        raise ValueError("a prompt's constraint is not a %s block" % CONSTRAINT_SCHEMA)
    if list(c["order"]) != list(FIELDS):
        raise ValueError("a prompt's constraint does not hold the declared key order")
    values = c["values"]
    if not isinstance(values, dict) or set(values) != set(CONSTRAINT_VALUE_FIELDS) or any(
            not isinstance(v, list) or not v or len(set(v)) != len(v) or not all(_plain_value(x) for x in v)
            for v in values.values()):
        raise ValueError("a prompt's constraint values are not one list of plain distinct values per field")
    w = c["wording"]
    if not isinstance(w, dict) or set(w) != {"whole", "per_article"} or not _plain_value(w["whole"]) \
            or w["whole"].isdigit() or not isinstance(w["per_article"], dict) \
            or set(w["per_article"]) != set(values["article"]) \
            or any(not isinstance(n, int) or isinstance(n, bool) or n < 0 for n in w["per_article"].values()):
        raise ValueError("a prompt's constraint does not give every article its own count of wordings")
    for field in CONSTRAINT_VALUE_FIELDS:
        if field in answers and list(answers[field]) != list(values[field]):
            raise ValueError("a prompt's constraint and its declared answers differ")
    return c


def write_file(path, labeller, generator_family, template_sha256, sets, prompts):
    """The prompts file, schema first (so `is_prompts_path` reads the head only). `sets` is
    {name: {sheets_sha256, items, positions}}; `prompts` the rendered questions in order. Prompts carrying a
    `constraint` block make a v2 file (D-799); prompts without one a v1 file, as before."""
    value = {"schema": SCHEMA_V2 if any("constraint" in p for p in prompts) else SCHEMA, "written_at": _now(),
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
    keys = PROMPT_KEYS | {"constraint"} if value["schema"] == SCHEMA_V2 else PROMPT_KEYS
    for p in prompts:
        if set(p) != keys:
            raise ValueError("a prompt carries other fields than %s" % sorted(keys))
        answers = p["answers"]
        if not isinstance(answers, dict) or set(answers) - set(FIELDS) or CONFIDENCE_FIELD not in answers \
                or any(not isinstance(v, list) or len(v) < 2 or len(set(v)) != len(v) for v in answers.values()):
            raise ValueError("a prompt's declared answers are not one list of two or more per field")
        if "constraint" in keys:
            check_constraint(p["constraint"], answers)
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


# ---------------------------------------------------------------------------
# D-799: the reply object generated under a per-request logits constraint


def wording_values(constraint, article):
    """The wording field's declared values once `article` is decoded: `whole` and 1..n of that article's own
    bracketed wordings (n from the prompts file, counted on the laptop), never the sheet's largest count."""
    w = constraint["wording"]
    return [w["whole"]] + [str(i) for i in range(1, int(w["per_article"][article]) + 1)]


class LabelGrammar:
    """The language of one labelling reply (D-799): exactly
    {"article": "<id>", "wording": "<value>", "stance": "<value>", "firm_limit": "<value>"}, the keys in the declared
    order, `": "` and `", "` between them as the template's example writes them, nothing before or after, and each
    value one of its declared values (the wording's list chosen from the article already decoded). Same interface as
    contract_decoding.Grammar, so DECODING-B's ContractProcessor runs it unchanged. A state is
    ('lit', i, matched, article), ('val', i, partial, article) or contract_decoding.DONE."""

    def __init__(self, constraint):
        import contract_decoding as cd
        self.done = cd.DONE
        self.c = constraint
        self.order = list(constraint["order"])
        keys = [json.dumps(k) for k in self.order]
        self.lits = ["{" + keys[0] + ': "'] + ['", ' + k + ': "' for k in keys[1:]] + ['"}']
        self.signature = _sha(json.dumps(constraint, sort_keys=True, ensure_ascii=False))

    def values(self, i, article):
        field = self.order[i]
        return wording_values(self.c, article) if field == "wording" else self.c["values"][field]

    def start(self):
        return ("lit", 0, 0, None)

    def step(self, state, ch):
        if state is None or state == self.done:
            return None
        kind, i, got, article = state
        if kind == "lit":
            lit = self.lits[i]
            if ch != lit[got]:
                return None
            if got + 1 < len(lit):
                return ("lit", i, got + 1, article)
            return self.done if i == len(self.order) else ("val", i, "", article)
        values = self.values(i, article)
        if ch == '"' and got in values:
            return ("lit", i + 1, 1, got if self.order[i] == "article" else article)
        grown = got + ch
        return ("val", i, grown, article) if any(v.startswith(grown) for v in values) else None

    def walk(self, state, text):
        for ch in text:
            state = self.step(state, ch)
            if state is None:
                return None
        return state

    def next_chars(self, state):
        if state is None or state == self.done:
            return set()
        kind, i, got, article = state
        if kind == "lit":
            return {self.lits[i][got]}
        values = self.values(i, article)
        out = {v[len(got)] for v in values if v.startswith(got) and len(v) > len(got)}
        return out | ({'"'} if got in values else set())

    def free(self, state):
        return False

    def unrestricted(self, state):
        return False

    def accepting(self, state):
        return state == self.done

    def article_of(self, text):
        """The article the reply decoded, or None when the reply never closed that field."""
        state, article = self.start(), None
        for ch in text:
            state = self.step(state, ch)
            if state is None or state == self.done:
                break
            article = state[3]
        return article


def accepts(constraint, text):
    """True when `text` is a complete reply of the constraint's language."""
    g = LabelGrammar(constraint)
    return g.accepting(g.walk(g.start(), text))


def outcome(constraint, text, new_tokens, max_new_tokens, dead_end=False):
    """`inside`, or why a reply is still outside the language: the constraint reached a dead end, the reply ran to
    its token allowance before the object closed, it stopped before closing, or it left the language (a reply not
    generated under the constraint). Python only; the reply is never read here."""
    g = LabelGrammar(constraint)
    state = g.walk(g.start(), text)
    if g.accepting(state):
        return INSIDE
    if dead_end:
        return "dead_end"
    if state is None:
        return "left_language"
    return "at_allowance" if int(new_tokens) >= int(max_new_tokens) else "unfinished"


def constrained_answers(answers, constraint, reply):
    """The declared answers the confidence record reads for a constrained reply: the wording's list narrowed to the
    decoded article's own values (dropped, as declared_answers drops a field, when that article has none to choose
    between); the other fields as declared. Unchanged when the article was not decoded."""
    article = LabelGrammar(constraint).article_of(reply)
    if article is None or article not in constraint["wording"]["per_article"]:
        return dict(answers)
    out = dict(answers)
    values = wording_values(constraint, article)
    if len(values) >= 2:
        out["wording"] = values
    else:
        out.pop("wording", None)
    return out


def constraint_processor(tok, prompt_tokens, eos_ids, constraint, record):
    """DECODING-B's logits processor (contract_decoding.ContractProcessor) over this request's LabelGrammar: every
    token whose text would leave the language set to -inf, the stop tokens admitted only once the object closed,
    each step where the model's own top token was not admitted counted into `record`."""
    import contract_decoding as cd
    return cd.ContractProcessor(None, None, tok, prompt_tokens, eos_ids, record, grammar=LabelGrammar(constraint))


def _eos_ids(model, tok):
    ids = [tok.eos_token_id]
    extra = getattr(getattr(model, "generation_config", None), "eos_token_id", None)
    ids += extra if isinstance(extra, (list, tuple)) else [extra]
    return sorted({int(i) for i in ids if i is not None})


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
    generate = make_generate(model, tok, decoding)
    generate.preflight = checked
    return generate


def make_generate(model, tok, decoding):
    """`generate(prompt, answers, constraint=None)` over a loaded model and tokenizer (the sealed labeller on the
    instance; a fake tokenizer and model in the proofs). Greedy as declared, the decoding values read from the
    prompts file at call time and never typed here. With a constraint (a v2 prompt, D-799) the one logits processor
    of DECODING-B rides beside those values, the raw logits are kept for the confidence record, and its counts come
    back as `constraint`; without one (a v1 prompt) the call is the one the first pass made."""
    import torch

    def generate(prompt, answers, constraint=None):
        ids = tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True,
                                      return_tensors="pt").to(model.device)
        kwargs = dict(attention_mask=torch.ones_like(ids), do_sample=False,
                      max_new_tokens=int(decoding["max_new_tokens"]), pad_token_id=tok.eos_token_id,
                      output_scores=True, return_dict_in_generate=True)
        record = None
        if constraint is not None:
            from transformers import LogitsProcessorList
            record = {}
            processor = constraint_processor(tok, int(ids.shape[1]), _eos_ids(model, tok), constraint, record)
            kwargs.update(logits_processor=LogitsProcessorList([processor]), output_logits=True)
        with torch.no_grad():
            gen = model.generate(ids, **kwargs)
        new = gen.sequences[0, ids.shape[1]:].tolist()
        reply = tok.decode(new, skip_special_tokens=True)
        # scores[k] (logits[k] under a constraint, before its mask) chose generated token k, so step k reads [k].
        chosen = gen.scores if constraint is None else gen.logits
        asked = answers if constraint is None else constrained_answers(answers, constraint, reply)
        decisions = field_decisions(new, lambda k: chosen[k][0].float().tolist(),
                                    lambda t: tok.decode(t, skip_special_tokens=True),
                                    lambda text: tok.encode(text, add_special_tokens=False), asked)
        out = {"reply": reply, "prompt_tokens": int(ids.shape[1]), "new_tokens": len(new), "decisions": decisions}
        if constraint is not None:
            out["constraint"] = dict(name=CONSTRAINT_NAME, version=CONSTRAINT_VERSION,
                                     constraint_sha256=LabelGrammar(constraint).signature,
                                     **{k: record.get(k) for k in ("steps", "interventions",
                                                                    "first_intervention_step", "dead_end")})
        return out
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
    constrained = value["schema"] == SCHEMA_V2
    by_reason, interventions = {}, 0
    for n, p in enumerate(prompts, 1):
        t0 = time.perf_counter()
        c = p.get("constraint")
        got = gen(p["prompt"], p["answers"], c) if c is not None else gen(p["prompt"], p["answers"])
        reply, prompt_tokens, new_tokens = got["reply"], got["prompt_tokens"], got["new_tokens"]
        decisions = got["decisions"]
        held = None
        if c is not None:
            # D-799: whether the reply is inside the one reply object, decided in Python; never read by guess.
            held = dict(got.get("constraint") or {"name": CONSTRAINT_NAME, "version": CONSTRAINT_VERSION,
                                                    "applied": False})
            held["outcome"] = outcome(c, reply, new_tokens, decoding["max_new_tokens"], bool(held.get("dead_end")))
            by_reason[held["outcome"]] = by_reason.get(held["outcome"], 0) + 1
            interventions += int(held.get("interventions") or 0)
        call = reply_records.write(context, agent=AGENT_LABEL, backend="local_labeller", model_id=model["model_id"],
                                   model_mode="sealed", payload=p["prompt"], payload_form="chat_user",
                                   reply=reply, ok=True, error="", decoding=decoding, sensitive=False,
                                   phase=PHASE, doc_id=p["prompt_id"],
                                   attention={"implementation": PATH, "revision": model["revision"]},
                                   decoding_constraint=held,
                                   decision={"schema": "neg-synth-label-fields-v1", "fields": decisions})
        if not call:
            raise RuntimeError("the reply record of prompt %d could not be written" % n)
        at_allowance += int(new_tokens >= int(decoding["max_new_tokens"]))
        row = {"prompt_id": p["prompt_id"], "set": p["set"], "prompt_sha256": p["prompt_sha256"],
               "reply_sha256": _sha(reply), "call_id": call, "prompt_tokens": prompt_tokens,
               "confidence": confidence_of(decisions),
               "decisions_sha256": _sha(json.dumps(decisions, sort_keys=True)),
               "new_tokens": new_tokens, "seconds": round(time.perf_counter() - t0, 3)}
        if held is not None:
            row["constraint_outcome"] = held["outcome"]
        rows.append(row)
        (out / PROGRESS_FILE).write_text(json.dumps({"done": n, "prompts": len(prompts),
                                                     "seconds": round(time.perf_counter() - started, 1)}),
                                         encoding="utf-8")
    measurement = {"schema": MEASUREMENT_SCHEMA, "model_id": model["model_id"], "revision": model["revision"],
                   "terms": model["terms"], "passed_over": model["passed_over"], "decoding": decoding,
                   "path": PATH, "prompts_file_sha256": hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest(),
                   "template_sha256": value["template_sha256"], "sets": value["sets"], "rows": rows,
                   "at_allowance": at_allowance, "prompts": len(prompts), "failures": 0,
                   "preflight": getattr(gen, "preflight", None), "prompts_schema": value["schema"],
                   # D-799: each constrained reply by outcome; everything but `inside` is outside the lists.
                   "constraint": None if not constrained else {
                       "schema": CONSTRAINT_SCHEMA, "name": CONSTRAINT_NAME, "version": CONSTRAINT_VERSION,
                       "by_reason": by_reason, "outside": sum(v for k, v in by_reason.items() if k != INSIDE),
                       "interventions": interventions},
                   "seconds": round(time.perf_counter() - started, 1), "finished_at": _now()}
    (out / MEASUREMENT_FILE).write_text(json.dumps(measurement, indent=1, sort_keys=True), encoding="utf-8")
    return measurement
