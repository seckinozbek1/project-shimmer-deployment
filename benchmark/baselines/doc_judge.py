"""G1, document-level judging: each (document, rule) judged ONCE over the whole document.

An evaluation tool, not a review and not an arm (development, exposed). The question is the
rule's own text, the prompt one short neutral user turn with no filled example
(doc_judge_prompt.json), the reply one JSON object {outcome, quote, reason} with three declared
outcomes (holds, not met, cannot be settled). Python keeps a holds or a not met only when its
quote occurs in the document (whitespace-normalised) and is the document's content (open item 84,
`quote_not_content`), and refuses everything else it cannot read;
cannot be settled is kept. The outcome's class (FLAG, CLEAR, UNDECIDED) becomes each benchmark's
label through the adapters' own Spec (benchmark/adapters/<name>/adapter.py), and the labels are
scored only through tools/score_corpus.py, the one reader of a key.

Four commands:

  build (no model)
      py -3.12 benchmark/baselines/doc_judge.py build --workload W [--workload W ...]
          (--items ITEMS.json ... | --benchmark NAME ...) --out replay_prompts.json [--config F] [--b1]
    W is a staged workload (tools/stage_workload.py: _review_targets.json at the top or in
    context/, context/, conventions/) naming one document under review. One prompt per rule
    heading carrying an operator id (common/prompt.py), per model group of the config, in the
    config's group order. --items (the staged items.json of each workload, in the same order)
    gives the item ids and the benchmark; --benchmark gives the benchmark alone (item ids are
    then read through the scorer at scoring time). The file is deterministic (no time stamp),
    carries the config it was rendered with, every document's text once and each user turn with
    its SHA-256, and is sealed as the B1 replay prompts of one exposed bundle
    (tools/prepare_ordinary_final_run.py --replay-prompts; benchmark/baselines/replay_prompts.py
    reads it through load_prompts below).

  run (loads each model group in turn; the rented machine only)
      reached as replay_prompts.py run --prompts replay_prompts.json --out <dir> --paths sdpa,
      the sealed replay pass of tools/ordinary_final_run.py (no bound controller file changes).
    Every prompt goes through bare_model.py's LocalBackend (the run's own loaders, the model's
    own chat template with one user turn, the frozen decoding policy, sdpa pinned, one-shot
    prefill; no system turn is sent, a comparator prompt apart, which carries B1's, but a model's
    own chat template may add its default one,
    as Qwen2.5's stock template does, and the rendered prompt saved in every reply record shows
    what was sent) and writes exactly one reply record (reply_records.write, reply text kept: exposed
    development material) under <dir>/audit/model_replies, and <dir>/replay_measurement.json
    (ids, counts, seconds; no text), rewritten after every prompt with `complete` false until the
    end, so a stopped pass stays readable. A prompt over its model's context is recorded as a failure
    before generating; an out-of-memory error or a refused kernel is recorded for that prompt
    and the run goes on (never retried); any other error stops the pass.

  judge (no model)
      py -3.12 benchmark/baselines/doc_judge.py judge --prompts replay_prompts.json
          --run <pass folder> --out <dir>
    Reads the pass's reply records and writes <dir>/judgements.json: per prompt the outcome as
    written, kept or refused (and why), the class, the quote, whether it was found and the units
    holding it; and, under b1_comparator, B1's label per comparator prompt.

  score (no model; the keys only through tools/score_corpus.py)
      py -3.12 benchmark/baselines/doc_judge.py score --judgements <dir>/judgements.json
          --key KEY.json [--key KEY.json ...] --out <dir> [--bar-items F]
    Per model group and view it writes bare_model-format label folders
    (<dir>/labels/<group>/<view>/<document id>/labels/<item id>.json) and scores them with
    score_corpus.benchmark_items(..., arm="B1") (the adapters' label_b1 and Spec), then
    <dir>/g1_scores.json and <dir>/G1_RESULTS.md. Views: `screened` (the judge's primary: a
    refused answer or a failed call is ABSTAIN), `unscreened` (the outcome as written, no quote
    rule: what the refusals changed) and `as_b3` (a refused answer or a failed call read as
    silence, the nothing-wrong class B3's labeller gives an item with no kept record). Per
    benchmark: precision, recall and F1 of the FLAG class, accuracy, the refusals that removed a
    wrong answer and those that removed a right one, and how many labels (and correct labels)
    come from a kept claim, a kept cannot be settled, a refusal or silence. Silence is counted
    apart and is never a detection.

The comparator (D-241). `build --b1` adds, per model group and item, B1's own prompt: the
preregistered system and user turns (common/prompt.py, the renderer bare_model.py uses), with
B1's output allowance, as form `b1`. A B1 bundle holds one document, so this is how one sealed
replay pass gives B1's figures on the same model and items. Three things differ from a B1 run: a
failed or over-context call is recorded and the pass goes on, where B1 stops as a setup failure,
so here it is an abstention and counts toward the bar's void rule; the loaded identity is recorded
for reading afterwards rather than verified before the first item; and a call whose observed
attention differs from the declared one is recorded, where B1 stops. Such a prompt's reply
is read by bare_model.parse_reply into a b1-label-v2 label and scored as the view
`b1_comparator`. `score --bar-items FILE` names the items the decision fixed and the items left
out of every figure, with the prompts' and the keys' digests (benchmark/baselines/g1_bar_items.json,
whose own digest is pinned here as BAR_ITEMS_SHA256), and g1_scores.json then carries `bar`, the
verdict of D-241's per-benchmark bar, computed here, with the code's digest. Another file, other
prompts or keys, or a run that scored other items on the two benchmarks gets no verdict
(`bar_refused`), and a folder holding a verdict is never written again. `judge` runs at the bound
commit, since it reads the repository's config. These guard a mistake; what stops a second pass
is that a bundle launches once. A pass means a pilot go only, never above B1.

The choice form (D-S41). A prompt of form `choice` is decided, not answered: LocalBackend.choose
runs one forward pass (scripts/choice_decision.py) and its reply record carries the declared
answers' probabilities and no reply. Its config's `choice` block declares each kind, `pair` (two
passages) and `claim` (a claim on the table cells select_cells chose), with its template and
answers. No threshold is applied: a pass saves probabilities, and the threshold is set from them.
Built by benchmark/baselines/choice_judge.py, on the same replay pass, so no bound controller file
changes.

A choice row of the measurement also carries `tie`, `declared_mass` and `logits_dtype`, and the
measurement counts `ties`, so the mass and the ties can be read without opening a reply record.

A group naming its model may also declare `adapter` {path, weights_sha256, config_sha256}: a LoRA
adapter applied at load (bare_model.apply_adapter) on any form, so a trained judge is a change to the
config alone (D-S42). The path is read on the machine that runs the pass, against the project when
relative; a file there that is not the declared one refuses the pass before any prompt. An adapter
made on the instance has no digest to seal ahead: the caller computes them and passes run a
`reader_for` whose reader carries `adapter`, and run keeps it, so the same route applies it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "scripts"
ADAPTERS = HERE.parent / "adapters"
for _p in (str(SCRIPTS), str(HERE), str(ADAPTERS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common import bundle as units  # noqa: E402  the one writer of a key's evidence unit ids
from common import prompt as rules_text  # noqa: E402  the one reader of a bundle's rule headings

CONFIG_PATH = HERE / "doc_judge_prompt.json"
CONFIG_SCHEMA = "doc-judge-prompt-v1"
SCHEMA = "doc-judge-prompts-v1"
MEASUREMENT_SCHEMA = "doc-judge-measurement-v1"
MEASUREMENT_FILE = "replay_measurement.json"   # the name tools/ordinary_final_run.py checks
KIND = "doc_judge"
AGENT_LABEL = "G1_DOC_JUDGE"
COMPARATOR_LABEL = "G1_B1_COMPARATOR"
B1_FORM = "b1"
AGENT_FORM = "agent"           # a saved B3 judging prompt replayed on another model (J1, D-262)
PAIR_FORM = "pair"             # two passages of one document, one question (P2 (a), pair_judge.py)
CHOICE_FORM = "choice"         # decided from next-token probabilities, no text (D-S41, choice_judge.py)
CHOICE_SLOTS = {"pair": {"passage_a", "passage_b"}, "claim": {"cells", "claim", "tools"}}
EARLY_STOP = 12               # a named model whose first replies all run to the allowance is stopped (D-262)
COMPARATOR = "b1_comparator"
PHASE = "G1"
# The one path a G1 pass runs: sdpa pinned, one shot, the run proper's setting (D-063).
PATH = "sdpa"
CLASSES = ("FLAG", "CLEAR", "UNDECIDED")
ABSTAIN = "ABSTAIN"
VIEWS = ("screened", "unscreened", "as_b3")
# D-241's bar: the benchmarks it reads, the fewest correct flags and documents, and the chance limit.
BAR_BENCHMARKS = ("contradoc", "scitab")
BAR_EVIDENCE = ("contradoc",)        # where the key marks the passages a correct flag should quote
BAR_ITEMS_SHA256 = "e460abea5820405b1c0046c5a453364e96ef5ad8ffff6d813873a7f4e59a67c9"   # g1_bar_items.json with LF line ends (D-241)
BAR_MIN_CORRECT = 2
BAR_CHANCE = 0.05
BAR_MAX_B1_ABSTAIN = 0.05            # the section 5.4 parse floor: past it B1 is no comparator
BAR_EVIDENCE_WORDS = 3               # a quote shorter than this says nothing of where it came from
_UNIT = re.compile(r"^## (P-\d+)[ \t]*$", re.M)
_SLOT = re.compile(r"\{(document|rule_text|outcome_lines)\}")
_PAIR_SLOT = re.compile(r"\{(passage_a|passage_b|outcome_lines)\}")
_CHOICE_SLOT = re.compile(r"\{(passage_a|passage_b|cells|claim|tools)\}")
_CELL_EDGE = re.compile(r"(?<!\\)\|")
_WS = re.compile(r"\s+")
# Sources a label comes from (score): a kept holds or not met, a kept cannot be settled, a
# refused answer, a call that gave no reply.
KEPT_CLAIM, KEPT_UNSETTLED, REFUSED, NO_REPLY, AS_WRITTEN = (
    "kept_claim", "kept_unsettled", "refused", "no_reply", "as_written")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _write_text(path, text):
    """Whole or not at all, and a model's lone surrogate is written as its escape: a reply can
    hold one, and it must never stop `judge` after a paid pass."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    partial.write_text(text, encoding="utf-8", errors="backslashreplace", newline="\n")
    os.replace(partial, path)


def _write_json(path, data):
    # LF on every platform, so a build on Windows gives the same bytes (and SHA-256) as here.
    _write_text(path, json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def normalise(text):
    """Every run of whitespace one space, trimmed (the quote rule)."""
    return _WS.sub(" ", str(text)).strip()


def _outcome_key(value):
    return normalise(str(value).lower().replace("_", " "))


# ---------------------------------------------------------------------------
# the prompt


def load_config(path=CONFIG_PATH):
    value = json.loads(Path(path).read_text(encoding="utf-8")) if not isinstance(path, dict) else path
    return check_config(value)


def check_config(value):
    if not isinstance(value, dict) or value.get("schema") != CONFIG_SCHEMA:
        raise ValueError("not a doc_judge prompt config (%s)" % CONFIG_SCHEMA)
    template = value.get("user_template")
    if not isinstance(template, str) or {m.group(1) for m in _SLOT.finditer(template)} != {"document", "rule_text", "outcome_lines"}:
        raise ValueError("the user template fills {document}, {rule_text} and {outcome_lines}")
    outcomes = value.get("outcomes")
    if not isinstance(outcomes, list) or len(outcomes) != 3:
        raise ValueError("the config declares three outcomes")
    seen = set()
    for o in outcomes:
        if not isinstance(o, dict) or o.get("class") not in CLASSES or not isinstance(o.get("value"), str):
            raise ValueError("an outcome needs a value and a class (FLAG, CLEAR or UNDECIDED)")
        accepted = {_outcome_key(a) for a in o.get("accepted") or []}
        if _outcome_key(o["value"]) not in accepted or accepted & seen:
            raise ValueError("each outcome accepts its own value, and no spelling twice")
        seen |= accepted
    if sorted(o["class"] for o in outcomes) != sorted(CLASSES):
        raise ValueError("the three outcomes carry the three classes once each")
    required = value.get("quote_required_for")
    if not isinstance(required, list) or not set(required) <= {o["value"] for o in outcomes}:
        raise ValueError("quote_required_for names declared outcomes")
    if type(value.get("max_new_tokens")) is not int or value["max_new_tokens"] <= 0:
        raise ValueError("the config declares a positive max_new_tokens")
    groups = value.get("models")
    if not isinstance(groups, list) or not groups or len({g.get("group") for g in groups}) != len(groups):
        raise ValueError("the config declares its model groups once each")
    for g in groups:
        if not (isinstance(g.get("group"), str) and re.fullmatch(r"[a-z0-9_]+", g["group"])
                and g.get("backend") in ("local_auditor", "local_producer") and isinstance(g.get("agent"), str)
                and g.get("checkpoint") in ("base", "tuned")):
            raise ValueError("a model group needs a name, a local backend, an agent and a checkpoint")
        if "model_id" in g and not (isinstance(g["model_id"], str) and g["model_id"].strip() and type(g.get("reasoning")) is bool
                                    and g["backend"] == "local_auditor" and g["checkpoint"] == "base"):
            raise ValueError("a group names its own model only on the auditor's backend, at the base checkpoint, "
                             "and says whether it reasons first (D-262)")
        adapter = g.get("adapter")
        if "adapter" in g and not ("model_id" in g and isinstance(adapter, dict) and set(adapter) == {"path", "weights_sha256", "config_sha256"}
                                   and isinstance(adapter["path"], str) and adapter["path"].strip()
                                   and all(re.fullmatch(r"[0-9a-f]{64}", str(adapter[k])) for k in ("weights_sha256", "config_sha256"))):
            raise ValueError("an adapter belongs to a group naming its model, and states its path and both SHA-256 digests (D-S42)")
    pair = value.get("pair")
    if pair is not None and not (isinstance(pair, dict) and isinstance(pair.get("template"), str)
                                 and {m.group(1) for m in _PAIR_SLOT.finditer(pair["template"])} == {"passage_a", "passage_b", "outcome_lines"}
                                 and type(pair.get("limit")) is int and pair["limit"] > 0):
        raise ValueError("a pair block fills {passage_a}, {passage_b} and {outcome_lines} and declares its limit")
    choice = value.get("choice")
    if choice is not None:
        _check_choice(choice, groups)
    if pair is None and choice is None and any("model_id" in g for g in groups):
        j1 = value.get("j1")
        if not (isinstance(j1, dict) and isinstance((j1.get("b1_direct") or {}).get("from"), str)
                and isinstance((j1.get("b1_direct") or {}).get("to"), str) and isinstance(j1.get("agent_note"), str)
                and type(j1.get("agent_allowance")) is int and type(j1.get("agent_reason_allowance")) is int):
            raise ValueError("a named model needs the J1 block: B1's direct line, the agent's note and both allowances")
    return value


def _check_choice(choice, groups):
    import choice_decision
    forms = choice.get("forms") if isinstance(choice, dict) else None
    if not isinstance(forms, dict) or not forms or set(forms) - set(CHOICE_SLOTS):
        raise ValueError("a choice block declares its forms, each one of: " + ", ".join(sorted(CHOICE_SLOTS)))
    for kind, form in forms.items():
        template = form.get("template")
        if not isinstance(template, str) or {m.group(1) for m in _CHOICE_SLOT.finditer(template)} != CHOICE_SLOTS[kind]:
            raise ValueError("a %s choice fills %s" % (kind, " and ".join(sorted(CHOICE_SLOTS[kind]))))
        if kind == "pair" and not (type(form.get("limit")) is int and form["limit"] > 0):
            raise ValueError("a pair choice declares its limit")
        answers = form.get("answers")
        choice_decision.declare(template, answers)
        if sorted(a.get("class") or "" for a in answers) != sorted(CLASSES):
            raise ValueError("a choice's answers carry the three classes once each")


def comparator_system(config, group, system):
    """B1's system turn. A J1 group with reasoning false loses B1's own 'work through the item
    first', the only place B1 reasons; a group with reasoning true keeps B1 as shipped."""
    if group.get("reasoning") is False:
        direct = config["j1"]["b1_direct"]
        if system.count(direct["from"]) != 1:
            raise ValueError("B1's system turn does not hold the line J1 replaces, once")
        return system.replace(direct["from"], direct["to"])
    return system


def render_pair(config, first, second):
    """The one question on two passages, in the order given. One pass over the template, so a
    passage holding braces is never read as a slot."""
    lines = chr(10).join(o["line"] for o in config["outcomes"])
    slots = {"passage_a": first, "passage_b": second, "outcome_lines": lines}
    return _PAIR_SLOT.sub(lambda m: slots[m.group(1)], config["pair"]["template"])


def pair_passages(doc, prompt):
    """The two passages a pair prompt names, read from the document by their offsets."""
    text = doc["text"]
    first, second = prompt.get("span_a"), prompt.get("span_b")
    if not all(isinstance(s, list) and len(s) == 2 and all(type(i) is int for i in s)
               and 0 <= s[0] < s[1] <= len(text) for s in (first, second)):
        raise ValueError("a pair prompt names no two passages: " + str(prompt.get("prompt_id")))
    return text[first[0]:first[1]], text[second[0]:second[1]]


def answers_moved(form):
    """A form's template with its answer lines moved round by one, so each stands in another place.
    Derived, never declared: the forms stay the ones a trained judge was built on. Its answer lines
    close the template, one per answer."""
    lines = form["template"].split("\n")
    count = len(form["answers"])
    return "\n".join(lines[:-count] + lines[-count + 1:] + lines[-count:-count + 1])


def render_choice(config, kind, slots, order_control=False):
    """A choice form's question, one pass over its template, so a passage's braces stay text. An
    order control asks it with the answer lines moved. A claim's `{tools}` slot, when the caller
    gives none, is filled as the pipeline fills it (`judge_agent.claim_tools`, the shipped contracts),
    so a replay's question is the pipeline's byte for byte."""
    form = config["choice"]["forms"][kind]
    if kind == "claim" and "tools" not in slots:
        import judge_agent
        slots = dict(slots, tools=judge_agent.claim_tools(slots.get("cells", ""), slots.get("claim", "")))
    return _CHOICE_SLOT.sub(lambda m: slots[m.group(1)], answers_moved(form) if order_control else form["template"])


class CellsRefused(ValueError):
    """`cell_selection` refused a claim: its message is the reason, and a build lists the claim."""


def select_cells(text, claim):
    """The cells of a table a claim bears on, by `scripts/cell_selection.py` (P2 (b)): the caption
    and the selected rows and columns. A pure function of the text and the claim, with no embedding
    injected, since `load_prompts` selects again and refuses a difference."""
    import cell_selection
    chosen = cell_selection.select(text, claim, cell_selection.load_config())
    if not chosen["selected"]:
        raise CellsRefused(chosen["refused"])
    return {"cells": chosen["cells"], "rows": len(chosen["rows"]), "of_rows": chosen["of_rows"],
            "columns": len(chosen["columns"]), "of_columns": chosen["of_columns"], "selected_by": chosen["selected_by"]}


def choice_user(config, doc, prompt):
    """The user turn of a choice prompt, from the document's own text alone."""
    kind, moved = prompt.get("choice"), prompt.get("order_control") is True
    if kind == "pair":
        first, second = pair_passages(doc, prompt)
        return render_choice(config, kind, {"passage_a": first, "passage_b": second}, moved)
    claim = prompt.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("a claim prompt states its claim: " + str(prompt.get("prompt_id")))
    return render_choice(config, kind, {"cells": select_cells(doc["text"], claim)["cells"], "claim": claim}, moved)


def choice_answers(config, prompt):
    return config["choice"]["forms"][prompt["choice"]]["answers"]


def agent_user(config, group, user):
    """A saved judging prompt as it was sent; a reasoning group's ends with the note. Every reply
    is read for its last JSON object, so the reasoning is never read as the answer."""
    return user + "\n\n" + config["j1"]["agent_note"] if group.get("reasoning") else user


def own_stops(decoding, group):
    """A group that names its own model stops on that model's own tokens. The backend's frozen
    protocol holds Phi-3.5's stop and pad ids, which are other tokens in another vocabulary, so
    they are dropped and generate() reads the model's generation config (D-261). Greedy,
    single-beam and cached stay as they were."""
    kwargs = {k: v for k, v in decoding["kwargs"].items() if k not in ("eos_token_id", "pad_token_id")}
    return dict(decoding, kwargs=kwargs, status="new", source="doc_judge group " + group["group"] + " model_id",
                sha256=_sha(_canonical(group)))


def render_user(config, *, document, rule_text):
    values = {"document": document, "rule_text": rule_text,
              "outcome_lines": "\n".join(o["line"] for o in config["outcomes"])}
    # One pass: a filled slot is never read again, so braces in the document stay text.
    return _SLOT.sub(lambda m: values[m.group(1)], config["user_template"])


def _targets(workload):
    workload = Path(workload)
    for path in (workload / "context" / "_review_targets.json", workload / "_review_targets.json"):
        if path.is_file():
            targets = json.loads(path.read_text(encoding="utf-8")).get("targets") or []
            if len(targets) != 1:
                raise ValueError("a workload names exactly one document under review: " + str(workload))
            return targets[0]
    raise ValueError("no _review_targets.json in " + str(workload))


def _has_reference(workload):
    workload = Path(workload)
    for path in (workload / "context" / "_review_targets.json", workload / "_review_targets.json"):
        if path.is_file():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            return bool(manifest.get("grounding") or manifest.get("prior"))
    return False


def _document_text(path):
    import text_extract
    text = text_extract.extract_text(Path(path))
    if not text.strip():
        raise ValueError("an empty document: " + str(path))
    return text


def workload_rules(workload):
    """{rule id: rule text} of every rule heading carrying an operator id, in file order."""
    rules = {}
    for heading, text in rules_text.conventions_from_bundle(workload):
        rid = rules_text.rule_id_of(heading)
        if not rid or not text:
            continue
        if rid in rules:
            raise ValueError("a rule id repeats in %s: %s" % (workload, rid))
        rules[rid] = text
    if not rules:
        raise ValueError("no rule heading with an operator id in " + str(workload))
    return rules


def _items(path, document_id):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = rows.get("items") if isinstance(rows, dict) else rows
    rows = [r for r in rows or [] if str(r.get("document_id")) == document_id]
    if not rows:
        raise ValueError("the item table holds no item of document " + document_id)
    return rows


def _comparator_prompts(cases, documents, config, spec, allowance):
    """B1's own turns for every (model group, item), rendered as bare_model.py renders them."""
    out = []
    for group in config["models"]:
        for case in cases:
            doc = documents[case["document_id"]]
            user = rules_text.render_user(spec, case["benchmark"], document=doc["text"],
                                          conventions=doc["conventions"], item=case, reference="")
            out.append(dict(case, prompt_id="c%04d" % (len(out) + 1), form=B1_FORM, group=group["group"],
                            backend=group["backend"], agent=group["agent"], checkpoint=group["checkpoint"],
                            max_new_tokens=allowance,
                            system=comparator_system(config, group, rules_text.render_system(spec, case["benchmark"])),
                            user=user, user_sha256=_sha(user)))
    return out


def _agent_prompts(saved, config, documents):
    """Saved judging prompts, one per model group and call (agent form, J1). Each is the call's
    own user turn, its model's chat tags taken off when it was extracted."""
    out = []
    for group in config["models"]:
        reasoning = group.get("reasoning") is True
        for call in saved:
            if call["document_id"] not in documents:
                raise ValueError("a saved call's document is not in the sample: " + str(call["document_id"]))
            user = agent_user(config, group, call["user"])
            out.append({"document_id": call["document_id"], "benchmark": documents[call["document_id"]]["benchmark"],
                        "rule_id": call["rule_id"], "item_id": call["item_id"], "unit_id": call["unit_id"],
                        "source_call_id": call["call_id"], "prompt_id": "a%04d" % (len(out) + 1), "form": AGENT_FORM,
                        "group": group["group"], "backend": group["backend"], "agent": group["agent"],
                        "checkpoint": group["checkpoint"], "system": None, "user": user, "user_sha256": _sha(user),
                        "max_new_tokens": config["j1"]["agent_reason_allowance" if reasoning else "agent_allowance"]})
    return out


def build(workloads, out, *, items=None, benchmarks=None, config_path=CONFIG_PATH, b1=False, agent_calls=None):
    """replay_prompts.json for G1 (see the module text); returns its content."""
    config = load_config(config_path)
    if b1 and not items:
        raise ValueError("the comparator needs each workload's items.json: B1 asks by item id")
    items = list(items or [])
    benchmarks = list(benchmarks or [])
    if not workloads or (items and len(items) != len(workloads)) or (benchmarks and len(benchmarks) != len(workloads)) \
            or bool(items) == bool(benchmarks):
        raise ValueError("name every workload once, with either its items.json or its benchmark (in the same order)")
    documents, cases = {}, []
    for k, workload in enumerate(workloads):
        workload = Path(workload)
        target = _targets(workload)
        document_id = Path(target).stem
        if document_id in documents:
            raise ValueError("a document is named twice: " + document_id)
        text = _document_text(workload / "context" / target)
        rules = workload_rules(workload)
        if items:
            rows = _items(items[k], document_id)
            by_rule = {}
            for r in rows:
                if r.get("rule_id") in by_rule:
                    raise ValueError("two items of %s name rule %s" % (document_id, r.get("rule_id")))
                by_rule[r.get("rule_id")] = r
            if set(by_rule) != set(rules):
                raise ValueError("the item table and the rules of %s differ" % document_id)
            bench = {str(r.get("benchmark")).lower() for r in rows}
            if len(bench) != 1:
                raise ValueError("the items of %s name more than one benchmark" % document_id)
            benchmark = bench.pop()
        else:
            by_rule, benchmark = {}, str(benchmarks[k]).lower()
        documents[document_id] = {"benchmark": benchmark, "text": text, "sha256": _sha(text), "target": target}
        if b1:
            if _has_reference(workload):
                raise ValueError("the comparator renders no reference material: " + str(workload))
            documents[document_id]["conventions"] = [list(c) for c in rules_text.conventions_from_bundle(workload)]
        for rid, rule in rules.items():
            cases.append({"document_id": document_id, "benchmark": benchmark, "rule_id": rid, "rule_text": rule,
                          "item_id": (by_rule.get(rid) or {}).get("item_id")})
    prompts = []
    saved = None
    if agent_calls:
        saved = json.loads(Path(agent_calls).read_text(encoding="utf-8"))
        prompts += _agent_prompts(saved, config, documents)
    for group in () if saved else config["models"]:
        for case in cases:
            user = render_user(config, document=documents[case["document_id"]]["text"], rule_text=case["rule_text"])
            prompts.append(dict(case, prompt_id="g%04d" % (len(prompts) + 1), group=group["group"],
                                backend=group["backend"], agent=group["agent"], checkpoint=group["checkpoint"],
                                max_new_tokens=config["max_new_tokens"], user=user, user_sha256=_sha(user)))
    extra = {}
    if b1:
        import python_only
        spec = rules_text.load_prompt()
        prompts += _comparator_prompts(cases, documents, config, spec, int(python_only.pipeline_literal("PRODUCTION_MAX_TOKENS")))
        extra.update(b1_prompt=spec, b1_prompt_sha256=_sha(_canonical(spec)))
    if saved:
        extra.update(agent_calls={c["call_id"]: c for c in saved})
    value = dict({"schema": SCHEMA, "kind": KIND, "config": config, "config_sha256": _sha(_canonical(config)),
                  "documents": documents, "prompt_count": len(prompts), "prompts": prompts,
                  "reads": "the staged workloads only: no answer key, no reply, no label"}, **extra)
    _write_json(out, value)
    return value


def is_prompts_file(value):
    return isinstance(value, dict) and value.get("schema") == SCHEMA


def _b1_prompt_holds(value):
    return "b1_prompt" not in value or value.get("b1_prompt_sha256") == _sha(_canonical(value["b1_prompt"]))


def load_prompts(path):
    """The prompts of a G1 replay_prompts.json, each re-rendered from the file's own config,
    document and rule text and held to its SHA-256 (so a prompt is what this template says)."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not is_prompts_file(value) or not isinstance(value.get("prompts"), list) or not value["prompts"]:
        raise ValueError("not a G1 prompts file (" + SCHEMA + ")")
    config = check_config(value.get("config"))
    if value.get("config_sha256") != _sha(_canonical(config)):
        raise ValueError("the G1 prompts file's config does not match its SHA-256")
    if value.get("prompt_count") != len(value["prompts"]):
        raise ValueError("the G1 prompts file's count is wrong")
    if not _b1_prompt_holds(value):
        raise ValueError("the G1 prompts file's B1 prompt does not match its SHA-256")
    documents = value.get("documents") or {}
    for doc_id, doc in documents.items():
        if not isinstance(doc, dict) or _sha(doc.get("text") or "") != doc.get("sha256"):
            raise ValueError("a document does not match its SHA-256: " + str(doc_id))
    groups = {g["group"]: g for g in config["models"]}
    ids, pairs = set(), set()
    for p in value["prompts"]:
        g = groups.get(p.get("group"))
        if g is None or any(p.get(k) != g[k] for k in ("backend", "agent", "checkpoint")):
            raise ValueError("a prompt names a model group its config does not declare: " + str(p.get("prompt_id")))
        doc = documents.get(p.get("document_id"))
        if doc is None or p.get("benchmark") != doc.get("benchmark"):
            raise ValueError("a prompt names a document the file does not hold: " + str(p.get("prompt_id")))
        if p.get("form") == B1_FORM:
            spec = value.get("b1_prompt")
            if not isinstance(spec, dict) or not p.get("item_id"):
                raise ValueError("a comparator prompt needs the file's B1 prompt and an item id: " + str(p.get("prompt_id")))
            user = rules_text.render_user(spec, p["benchmark"], document=doc["text"], conventions=doc.get("conventions") or [],
                                          item=p, reference="")
            system = comparator_system(config, g, rules_text.render_system(spec, p["benchmark"]))
        elif p.get("form") == AGENT_FORM:
            call = (value.get("agent_calls") or {}).get(p.get("source_call_id"))
            if not isinstance(call, dict) or any(p.get(k) != call.get(k) for k in ("document_id", "rule_id", "item_id", "unit_id")):
                raise ValueError("an agent prompt names a call the file does not hold: " + str(p.get("prompt_id")))
            user, system = agent_user(config, g, call["user"]), None
        elif p.get("form") == PAIR_FORM:
            if not isinstance(config.get("pair"), dict) or not p.get("pair_id"):
                raise ValueError("a pair prompt needs the config's pair block and a pair id: " + str(p.get("prompt_id")))
            user, system = render_pair(config, *pair_passages(doc, p)), None
        elif p.get("form") == CHOICE_FORM:
            if p.get("choice") not in ((config.get("choice") or {}).get("forms") or {}) or p.get("max_new_tokens") != 0:
                raise ValueError("a choice prompt names a declared form and generates nothing: " + str(p.get("prompt_id")))
            user, system = choice_user(config, doc, p), None
        else:
            user = render_user(config, document=doc["text"], rule_text=str(p.get("rule_text")))
            system = None
        if p.get("user") != user or p.get("user_sha256") != _sha(user) or p.get("system") != system:
            raise ValueError("a prompt is not its template's rendering: " + str(p.get("prompt_id")))
        pair = (p["group"], p["document_id"], p.get("rule_id"), p.get("form"), p.get("unit_id"), p.get("pair_id"))
        if p.get("prompt_id") in ids or pair in pairs:
            raise ValueError("a prompt id, or a (group, document, rule), repeats")
        ids.add(p["prompt_id"])
        pairs.add(pair)
    return value["prompts"]


def read_file(path):
    load_prompts(path)
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# run (the rented machine)


def failure_kind(exc):
    """The named failure of one call, on which the pass goes on, or None for any other, which stops
    it. Logits that cannot be read are one call's; a refused declaration is every call's, so it
    stops the pass at its first prompt."""
    import choice_decision
    import final_models
    return "unreadable_logits" if isinstance(exc, choice_decision.ChoiceUnreadable) else final_models.generation_failure_kind(exc)


def make_backend(reader, context):
    """bare_model.py's LocalBackend: the run's own loaders (see bare_model.LocalBackend.prepare)."""
    import bare_model
    return bare_model.LocalBackend(reader, context)


def _save_progress(out, measurement):
    _write_json(Path(out) / MEASUREMENT_FILE, measurement)


def run(prompts_path, out, *, paths=(PATH,), decision=None, max_new_tokens=None, backend_factory=None,
        reader_for=None, run_id=None):
    """Every prompt through its model group's backend (see the module text); returns the
    measurement. `backend_factory(reader, context)` and `reader_for(group, allowance)` are for
    the checks' canned models; by default bare_model.LocalBackend and bare_model.resolve_reader."""
    import bare_model
    import final_models
    import reply_records
    import decoding_policy
    if list(paths) != [PATH]:
        raise ValueError("a G1 pass runs the %s path alone (sdpa pinned, one shot, D-063)" % PATH)
    if max_new_tokens is not None:
        raise ValueError("a G1 pass takes each prompt's own allowance: an override would cut B1's")
    if decision is not None:
        raise ValueError("a G1 pass runs no measurement path, so it names no decision")
    value = read_file(prompts_path)
    prompts, config = value["prompts"], value["config"]
    out = Path(out)
    context = bare_model.RunContext(out, run_id or ("g1-" + uuid.uuid4().hex[:12]))
    factory = backend_factory or make_backend
    rows, memory, models, prefill_seconds = [], {}, {}, []
    declared = bare_model.attention_record()
    prompts_sha256 = hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest()

    def snapshot(complete):
        """The measurement as it stands. Written after every prompt: it alone joins a prompt to its
        reply record, so a pass stopped late must still be readable."""
        peaks = [m for m in memory.values() if m.get("measured")]
        widest = max(peaks, key=lambda m: m["peak_allocated_bytes"]) if peaks else (next(iter(memory.values()), None)
                                                                                  or bare_model.read_gpu_memory(None, None))
        return {"schema": MEASUREMENT_SCHEMA, "kind": KIND, "run_id": context.run_id, "prompts": len(prompts), "complete": complete,
                "comparator_prompts": sum(1 for p in prompts if p.get("form") == B1_FORM),
                # the sealed prompts file's own digest (prepare_ordinary_final_run.replay_declaration)
                "prompts_sha256": prompts_sha256,
                "config_sha256": value["config_sha256"], "paths": {PATH: declared}, "decision": None,
                "models": models, "groups": memory,
                # The replay shape the analyser reads (tools/analyze_ordinary_final_run.py): per path.
                "gpu_memory": {PATH: widest},
                "prefill_seconds": {PATH: {"measured": len(prefill_seconds),
                                           "total": round(sum(prefill_seconds), 6) if prefill_seconds else None,
                                           "max": max(prefill_seconds) if prefill_seconds else None}},
                "failures": {PATH: sum(1 for r in rows if r["failure"])}, "comparisons": {},
                "ties": sum(1 for r in rows if r.get("tie") is True),
                "seconds": {g: round(sum(r["seconds"] or 0 for r in rows if r["group"] == g), 3)
                            for g in sorted(set(memory) | {r["group"] for r in rows})},
                "rows": rows, "reads": "the G1 prompts file; ids, counts and seconds only here, the replies in the reply records"}
    for group in config["models"]:
        mine = [p for p in prompts if p["group"] == group["group"]]
        if not mine:
            continue
        reader_allowance = int(config["max_new_tokens"])
        reader = (reader_for(group, reader_allowance) if reader_for is not None else
                  bare_model.resolve_reader(agent=group["agent"], checkpoint=group["checkpoint"], max_new_tokens=reader_allowance))
        if reader["backend"] != group["backend"]:
            raise ValueError("group %s resolves to backend %s, not %s" % (group["group"], reader["backend"], group["backend"]))
        if group.get("model_id"):
            reader = dict(reader, model_id=group["model_id"], decoding=own_stops(reader["decoding"], group))
            if group.get("adapter"):
                reader["adapter"] = group["adapter"]
        if final_models.mode() == "final":
            # The run's own process setting (strict determinism), as every local call has it.
            final_models.verify_runtime()
        backend = factory(reader, context)
        try:
            loaded = backend.prepare()
            models[group["group"]] = {"model_id": loaded.get("model_id"), "digest": loaded.get("digest"),
                                      "checkpoint": (loaded.get("checkpoint") or {}).get("checkpoint"),
                                      "adapter_applied": (loaded.get("checkpoint") or {}).get("adapter_applied"),
                                      "adapter_sha256": (loaded.get("checkpoint") or {}).get("adapter_sha256"),
                                      "backend": reader["backend"], "agent": reader["agent"]}
            limit = backend.max_context()
            cuda, at_start = bare_model.start_gpu_memory()
            for p in mine:
                allowance = int(p["max_new_tokens"])
                decoding = dict(decoding_policy.usage_fields(reader["decoding"]), max_new_tokens=allowance)
                system = p.get("system")
                tokens = backend.count_prompt(system, p["user"])
                window = {"prompt_tokens": int(tokens), "max_new_tokens": allowance, "model_context": int(limit),
                          "over_context": int(tokens) + allowance > int(limit)}
                row = {"prompt_id": p["prompt_id"], "form": p.get("form") or "g1", "group": group["group"], "document_id": p["document_id"],
                       "rule_id": p["rule_id"], "prompt_tokens": int(tokens), "max_new_tokens": allowance,
                       "failure": None, "reply": None, "output_tokens": None, "seconds": None,
                       "length_reached_allowance": None}
                result, error = {}, ""
                if window["over_context"]:
                    row["failure"] = error = "prompt_over_context"
                else:
                    started = time.perf_counter()
                    try:
                        result = (backend.choose(system, p["user"], choice_answers(config, p)) if p.get("form") == CHOICE_FORM
                                  else backend.generate(system, p["user"], allowance)) or {}
                    except Exception as exc:
                        kind = failure_kind(exc)
                        if kind is None:
                            raise
                        row["failure"] = error = kind
                        result = {}
                        if cuda is not None:
                            cuda.empty_cache()
                    row["seconds"] = round(time.perf_counter() - started, 3)
                text = result.get("text") if isinstance(result.get("text"), str) else None
                if text is not None:
                    row["reply"] = {"sha256": _sha(text), "length_bytes": len(text.encode("utf-8"))}
                    row["output_tokens"] = result.get("output_tokens") if type(result.get("output_tokens")) is int else None
                    row["length_reached_allowance"] = bare_model.length_reached(result, allowance)
                decision = result.get("decision")
                if decision:
                    row.update(tie=decision["why"] == "tie", declared_mass=decision["declared_mass"],
                               logits_dtype=decision.get("logits_dtype"), model_logits_dtype=decision.get("model_logits_dtype"),
                               undeclared_top=decision.get("undeclared_top"),
                               undeclared_above_top=bool(decision.get("undeclared_top")) and decision["undeclared_top"]["probability"]
                               > max(a["probability"] for a in decision["answers"]) * decision["declared_mass"])
                if isinstance(result.get("prefill"), dict) and isinstance(result["prefill"].get("prefill_seconds"), (int, float)):
                    prefill_seconds.append(result["prefill"]["prefill_seconds"])
                call = reply_records.write(
                    context, agent=COMPARATOR_LABEL if p.get("form") == B1_FORM else AGENT_LABEL,
                    backend=reader["backend"], model_id=reader["model_id"],
                    model_mode=reader["model_mode"], payload=result.get("payload"), payload_form=result.get("form"),
                    reply=text, ok=not error, error=error, decoding=decoding, sensitive=False, phase=PHASE,
                    doc_id=p["document_id"], attention=result.get("attention") or declared,
                    prefill=result.get("prefill"), context=window, decision=result.get("decision"))
                if not call:
                    raise RuntimeError("the reply record for prompt %s could not be written" % p["prompt_id"])
                row["call_id"] = call
                rows.append(row)
                _save_progress(out, snapshot(False))
                if group.get("model_id"):
                    first = [r for r in rows if r["group"] == group["group"] and r["form"] != CHOICE_FORM]
                    if len(first) == EARLY_STOP and all(r["length_reached_allowance"] is True or not r["reply"] for r in first):
                        raise RuntimeError("the first %d replies of group %s all ran to the allowance or were empty: "
                                           "stopped, the model is not stopping on its own" % (EARLY_STOP, group["group"]))
            memory[group["group"]] = bare_model.read_gpu_memory(cuda, at_start)
        finally:
            release = getattr(backend, "release", None)
            if callable(release):
                release()
    result = snapshot(True)
    _save_progress(out, result)
    return result


# ---------------------------------------------------------------------------
# judge (no model)


def parse_reply(reply, config):
    """{outcome, written, quote, reason, failure}: the last balanced JSON object of the reply
    (bare_model.py's section 5.4 reader, fences dropped, invalid escapes repaired), its outcome
    read against the declared spellings."""
    import bare_model
    out = {"outcome": None, "written": None, "quote": None, "reason": None, "failure": None}
    if not isinstance(reply, str) or not reply.strip():
        out["failure"] = "empty_reply"
        return out
    candidate = bare_model._last_balanced_object(bare_model._without_fences(reply))
    if candidate is None:
        out["failure"] = "no_json_object"
        return out
    try:
        obj, _ = bare_model._loads(candidate)
    except ValueError:
        try:
            # A quote copied over a line break holds a raw newline; the quote rule normalises it.
            obj = json.loads(candidate, strict=False)
        except ValueError:
            out["failure"] = "json_invalid"
            return out
    if not isinstance(obj, dict) or not isinstance(obj.get("outcome"), str):
        out["failure"] = "no_outcome"
        return out
    out["written"] = obj["outcome"]
    out["quote"] = obj.get("quote") if isinstance(obj.get("quote"), str) else None
    out["reason"] = obj.get("reason") if isinstance(obj.get("reason"), str) else None
    wanted = _outcome_key(obj["outcome"])
    match = next((o for o in config["outcomes"] if wanted in {_outcome_key(a) for a in o.get("accepted") or []}), None)
    if match is None:
        out["failure"] = "outcome_not_declared"
        return out
    out["outcome"] = match["value"]
    return out


def content_text(document, config):
    """The document without its heading and passage label lines, whitespace-normalised."""
    for pattern in config.get("marker_patterns") or ():
        document = re.sub(pattern, " ", document, flags=re.M)
    return normalise(document)


def quote_is_content(quote, document, config):
    """Open item 84: a found quote counts only when it is the document's content: it occurs
    with the markers taken out, holds a letter or digit, and its first and last letters or digits
    somewhere lie at a word's or a number's edge, so a piece of a word or of a figure such as
    81.5 does not pass and a whole table cell does. `quote` is whitespace-normalised."""
    content = content_text(document, config)
    marks = [k for k, c in enumerate(quote) if c.isalnum()]
    if not marks:
        return False
    at = content.find(quote)
    while at != -1:
        if not _inside(content, at + marks[0], -1) and not _inside(content, at + marks[-1], 1):
            return True
        at = content.find(quote, at + 1)
    return False


def _inside(content, edge, step):
    """True when the letter or digit at `edge` continues past it: another beside it, or a digit
    carried over a decimal point or group comma to another digit."""
    beside, further = edge + step, edge + 2 * step
    if not 0 <= beside < len(content):
        return False
    if content[beside].isalnum():
        return True
    return content[edge].isdigit() and content[beside] in ".," and 0 <= further < len(content) and content[further].isdigit()


def screen(parsed, document, config):
    """(kept, refusal): the quote rule on a parsed reply."""
    if parsed["failure"]:
        return False, parsed["failure"]
    if parsed["outcome"] in config["quote_required_for"]:
        quote = normalise(parsed["quote"] or "")
        if not quote:
            return False, "quote_missing"
        if quote not in normalise(document):
            return False, "quote_not_in_document"
        if not quote_is_content(quote, document, config):
            return False, "quote_not_content"
    return True, None


def quote_units(document, quote, config):
    """The key-form unit ids (bundle.unit_id: `u01-p-00001`) of the units whose content holds the
    quote, whitespace-normalised; the k-th `## P-NNNNN` heading is unit k."""
    wanted = normalise(quote or "")
    marks = list(_UNIT.finditer(document))
    if not wanted:
        return []
    return [units.unit_id(k + 1) for k, m in enumerate(marks)
            if wanted in content_text(document[m.end():marks[k + 1].start() if k + 1 < len(marks) else len(document)], config)]


def outcome_class(config, outcome):
    return next(o["class"] for o in config["outcomes"] if o["value"] == outcome)


def _comparator_rows(value, by_prompt, records):
    """B1's labels on the comparator prompts, by bare_model.py's own reader of a reply."""
    import bare_model
    rows = []
    for p in value["prompts"]:
        if p.get("form") != B1_FORM:
            continue
        seen = by_prompt.get(p["prompt_id"])
        record = records.get((seen or {}).get("call_id"))
        reply = (record or {}).get("reply") or {}
        text = reply.get("text") if isinstance(reply, dict) else None
        ok = bool(seen and record and record.get("backend_ok") and text is not None)
        bench = value["b1_prompt"]["benchmarks"][p["benchmark"]]
        parsed = bare_model.parse_reply(text if ok else None, bench, p["item_id"])
        rows.append(dict({k: p[k] for k in ("prompt_id", "group", "document_id", "benchmark", "rule_id", "item_id")},
                         label=parsed["label"], abstain=not parsed["parsed"], parse_failure=parsed["failure"] if ok else "no_reply",
                         length_reached_allowance=(seen or {}).get("length_reached_allowance"),
                         evidence=parsed["evidence"], reason=parsed["reason"]))
    return rows


def judge(prompts_path, run_dir, out):
    """judgements.json from one pass's reply records (see the module text)."""
    import reply_records
    value = read_file(prompts_path)
    config, documents = value["config"], value["documents"]
    run_dir = Path(run_dir)
    measurement = json.loads((run_dir / MEASUREMENT_FILE).read_text(encoding="utf-8"))
    if measurement.get("schema") != MEASUREMENT_SCHEMA or measurement.get("config_sha256") != value["config_sha256"] \
            or measurement.get("prompts_sha256") != hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest():
        raise ValueError("the pass folder is not a G1 pass of these prompts")
    records = {r.get("call_id"): r for r in reply_records.records(run_dir / "audit" / "model_replies")}
    by_prompt = {r["prompt_id"]: r for r in measurement.get("rows") or []}
    rows = []
    for p in value["prompts"]:
        if p.get("form") == B1_FORM:
            continue
        seen = by_prompt.get(p["prompt_id"])
        record = records.get((seen or {}).get("call_id"))
        row = {k: p[k] for k in ("prompt_id", "group", "document_id", "benchmark", "rule_id", "item_id")}
        reply = (record or {}).get("reply") or {}
        text = reply.get("text") if isinstance(reply, dict) else None
        if record is not None and record.get("sensitive"):
            raise ValueError("a reply record keeps its hash only; a G1 pass keeps the reply text")
        if seen is None or record is None or not record.get("backend_ok") or text is None:
            row.update(source=NO_REPLY, kept=False, refusal=(seen or {}).get("failure") or "no_reply", outcome=None,
                       written=None, quote=None, quote_found=None, reason=None, cls=ABSTAIN, written_cls=ABSTAIN)
            rows.append(row)
            continue
        parsed = parse_reply(text, config)
        kept, refusal = screen(parsed, documents[p["document_id"]]["text"], config)
        written_cls = outcome_class(config, parsed["outcome"]) if parsed["outcome"] else ABSTAIN
        quote = parsed["quote"]
        row.update(outcome=parsed["outcome"], written=parsed["written"], quote=quote, reason=parsed["reason"],
                   quote_found=(normalise(quote) in normalise(documents[p["document_id"]]["text"])
                                if quote and normalise(quote) else None),
                   quote_units=quote_units(documents[p["document_id"]]["text"], quote, config),
                   kept=kept, refusal=refusal, written_cls=written_cls,
                   cls=written_cls if kept else ABSTAIN,
                   source=(REFUSED if not kept else KEPT_UNSETTLED if written_cls == "UNDECIDED" else KEPT_CLAIM),
                   output_tokens=seen.get("output_tokens"), length_reached_allowance=seen.get("length_reached_allowance"))
        rows.append(row)
    counts = {}
    for r in rows:
        c = counts.setdefault(r["group"], {"prompts": 0, "kept_claim": 0, "kept_unsettled": 0, "refused": 0,
                                           "no_reply": 0, "refusals": {}, "no_reply_reasons": {}})
        c["prompts"] += 1
        c[r["source"]] += 1
        bucket = c["refusals"] if r["source"] == REFUSED else c["no_reply_reasons"] if r["source"] == NO_REPLY else None
        if bucket is not None:
            bucket[r["refusal"]] = bucket.get(r["refusal"], 0) + 1
    result = {"schema": "doc-judge-judgements-v1", "config_sha256": value["config_sha256"],
              "repository_config_matches": _sha(_canonical(load_config())) == value["config_sha256"],
              "repository_b1_prompt_matches": ("b1_prompt_sha256" not in value or
                                               _sha(_canonical(rules_text.load_prompt())) == value["b1_prompt_sha256"]),
              "groups": [g["group"] for g in config["models"]], "run_id": measurement.get("run_id"),
              "complete": measurement.get("complete") is True,
              "prompts_sha256": measurement.get("prompts_sha256"),
              "models": measurement.get("models"), "counts": counts, "judgements": rows,
              COMPARATOR: _comparator_rows(value, by_prompt, records)}
    _write_json(Path(out) / "judgements.json", result)
    return result


# ---------------------------------------------------------------------------
# score (the keys only through tools/score_corpus.py)


def _score_corpus():
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import score_corpus
    return score_corpus


def _adapter(benchmark):
    adapter = _score_corpus()._adapter_for(benchmark)
    if adapter is None:
        raise ValueError("no adapter for benchmark " + benchmark)
    return adapter


def label_name(spec, cls):
    """The benchmark's B1 label name for a class (the adapter's own Spec), or None."""
    return next((name for name, c in spec.b1_labels.items() if c == cls), None)


def view_class(row, view):
    """(class, source) of a judgement under a view."""
    if view == "screened":
        return row["cls"], row["source"]
    if view == "unscreened":
        return row["written_cls"], (AS_WRITTEN if row["written_cls"] != ABSTAIN else row["source"])
    # as_b3: an item with no kept answer is read as B3's labeller reads an item with no record.
    if row["source"] in (REFUSED, NO_REPLY):
        return "CLEAR", "silence"
    return row["cls"], row["source"]


def metrics(scored):
    """One benchmark's figures from rows {gold, cls, source, was_refused, written_cls}: the FLAG
    class's precision, recall and F1 and the accuracy by the adapters' own measures
    (common/metrics.py: ABSTAIN wrong, a zero denominator 0 and counted), and where the
    labels come from."""
    from common import metrics as measures
    pairs = [(r["cls"], r["gold"]) for r in scored]
    flag = measures.class_scores(pairs, "FLAG")
    sources, correct = {}, {}
    for r in scored:
        sources[r["source"]] = sources.get(r["source"], 0) + 1
        if r["cls"] == r["gold"]:
            correct[r["source"]] = correct.get(r["source"], 0) + 1
    by_doc = {}
    for r in scored:
        row = by_doc.setdefault(r["document_id"], [0, 0, 0])
        row[0] += 1
        row[1] += r["gold"] == "FLAG"
        row[2] += r["cls"] == "FLAG"
    single = [row for row in by_doc.values() if row[0] == 1]
    strata = [row for row in by_doc.values() if row[0] > 1]
    if single:
        strata.append([len(single), sum(r[1] for r in single), sum(r[2] for r in single)])
    return {"items": len(scored), "flag_tp": flag["tp"], "flag_fp": flag["fp"], "flag_fn": flag["fn"], "strata": strata,
            "tp_quoting_evidence": sum(1 for r in scored if r["cls"] == "FLAG" and r["gold"] == "FLAG" and r.get("quotes_evidence")),
            "truncated": sum(1 for r in scored if r.get("truncated")),
            "flag_tp_documents": len({r["document_id"] for r in scored if r["cls"] == "FLAG" and r["gold"] == "FLAG"}),
            "precision": flag["precision"], "recall": flag["recall"], "f1": flag["f1"],
            "zero_denominators": flag["zero_denominators"], "accuracy": measures.accuracy(pairs)["accuracy"],
            "abstain": sum(1 for r in scored if r["cls"] == ABSTAIN),
            "labels_by_source": dict(sorted(sources.items())), "correct_by_source": dict(sorted(correct.items())),
            # A refusal of a reply with a declared outcome either removed a wrong answer (correct)
            # or a right one; a reply with no readable outcome had no answer to remove.
            "refusals": sum(1 for r in scored if r["was_refused"]),
            "refusals_unreadable": sum(1 for r in scored if r["was_refused"] and r["written_cls"] == ABSTAIN),
            "correct_refusals": sum(1 for r in scored if r["was_refused"] and r["written_cls"] not in (ABSTAIN, r["gold"])),
            "refusals_that_removed_a_right_answer": sum(1 for r in scored if r["was_refused"] and r["written_cls"] == r["gold"]),
            "silence_labels": sources.get("silence", 0),
            "silence_flags": sum(1 for r in scored if r["source"] == "silence" and r["cls"] == "FLAG"),
            "silence_note": "silence is counted apart and is never a detection"}


def _hypergeometric(items, gold, flags):
    """{correct flags: probability} when `flags` of `items` are flagged with no regard to gold."""
    if not (0 <= gold <= items and 0 <= flags <= items):
        raise ValueError("a stratum's gold and flags lie within its items")
    total = math.comb(items, flags)
    return {x: math.comb(gold, x) * math.comb(items - gold, flags - x) / total
            for x in range(max(0, flags - (items - gold)), min(gold, flags) + 1)}


def chance_tail(strata, correct):
    """P(at least `correct` correct flags) with each stratum's gold and flag counts held fixed,
    the flags falling anywhere in their stratum: the convolution of one hypergeometric per
    stratum. A table's claims are one stratum, so flagging by table, or by a table's share of
    refuted claims, earns nothing; single-item documents pool into one stratum."""
    spread = {0: 1.0}
    for items, gold, flags in strata:
        one, nxt = _hypergeometric(items, gold, flags), {}
        for x, p in spread.items():
            for y, q in one.items():
                nxt[x + y] = nxt.get(x + y, 0.0) + p * q
        spread = nxt
    return sum(p for x, p in spread.items() if x >= correct)


def bar_row(mine, b1, benchmark=None):
    """D-241's conditions on one model and benchmark, from the screened and comparator figures.
    The net rate is recall less the false-flag rate, in integers: a cautious, silent or
    flag-everything B1 is compared on one scale. Void, neither met nor missed, when too many of
    B1's answers are unreadable to compare with, unless a condition that needs no B1 is missed."""
    items, gold = mine["items"], mine["flag_tp"] + mine["flag_fn"]
    clear = items - gold
    chance = chance_tail(mine["strata"], mine["flag_tp"]) if mine["flag_tp"] + mine["flag_fp"] else 1.0
    row = {"net_rate_at_least_b1": mine["flag_tp"] * clear - mine["flag_fp"] * gold
           >= b1["flag_tp"] * clear - b1["flag_fp"] * gold,
           "two_correct_flags": mine["flag_tp"] >= BAR_MIN_CORRECT,
           "from_two_documents": mine["flag_tp_documents"] >= BAR_MIN_CORRECT,
           "above_chance": chance <= BAR_CHANCE}
    if benchmark in BAR_EVIDENCE:
        row["quotes_gold_evidence"] = mine["tp_quoting_evidence"] >= BAR_MIN_CORRECT
    void = b1["abstain"] > BAR_MAX_B1_ABSTAIN * b1["items"]
    # What needs no comparator is read first: a model missing it misses, whatever B1 did.
    alone = all(v for k, v in row.items() if k != "net_rate_at_least_b1")
    state = "missed" if not alone else "void" if void else "met" if row["net_rate_at_least_b1"] else "missed"
    return dict(row, passes=state == "met", void=void, state=state, chance=round(chance, 6), gold=gold, items=items,
                screened={"tp": mine["flag_tp"], "fp": mine["flag_fp"], "fn": mine["flag_fn"], "abstain": mine["abstain"],
                          "truncated": mine["truncated"], "tp_quoting_evidence": mine["tp_quoting_evidence"]},
                b1={"tp": b1["flag_tp"], "fp": b1["flag_fp"], "fn": b1["flag_fn"], "abstain": b1["abstain"],
                    "truncated": b1["truncated"]})


def bar(figures):
    """The bar's verdict: one model, the same on both benchmarks, meets every condition on each.
    None without a comparator, so a run with no B1 figures can never read as a pass. `verdict` is
    usable, not_usable, or void: no model met it and at least one missed nothing but was void
    somewhere, so B1 could not be compared; void is no miss and sends nothing to G2 (D-241)."""
    rows = {}
    for group, views in figures.items():
        mine, b1 = views.get("screened") or {}, views.get(COMPARATOR) or {}
        if not all(b in mine and b in b1 for b in BAR_BENCHMARKS):
            return None
        rows[group] = {b: bar_row(mine[b], b1[b], b) for b in BAR_BENCHMARKS}
    passing = sorted(g for g, r in rows.items() if all(x["state"] == "met" for x in r.values()))
    open_rows = [g for g, r in rows.items() if any(x["state"] == "void" for x in r.values())
                 and not any(x["state"] == "missed" for x in r.values())]
    verdict = "usable" if passing else "void" if open_rows else "not_usable"
    return {"rows": rows, "models_passing": passing, "models_void": sorted(open_rows), "verdict": verdict,
            "usable_signal": None if verdict == "void" else bool(passing),
            "means": "a pilot go for D-S22 item 2 only, never above B1"} if rows else None


def bar_refusal(per_group, manifest):
    """None, or why the bar is not read: every model and arm must have scored exactly the items
    of the decision's own file (its digest is pinned), and every model the config names."""
    if not per_group:
        return "nothing was scored"
    for group, views in per_group.items():
        for view in ("screened", COMPARATOR):
            for benchmark in BAR_BENCHMARKS:
                got = sorted(r["item_id"] for r in (views.get(view) or {}).get(benchmark) or [])
                if got != sorted(manifest[benchmark]):
                    return "%s %s %s scored %d items, not the %d the decision names" % (
                        group, view, benchmark, len(got), len(manifest[benchmark]))
    return None


def discordant(per_group):
    """Per model and benchmark, the items and documents where only one arm is right: reported,
    never a condition (D-241). They size the later paired test."""
    out = {}
    for group, views in per_group.items():
        for benchmark, rows in (views.get("screened") or {}).items():
            b1 = {r["item_id"]: r for r in (views.get(COMPARATOR) or {}).get(benchmark) or []}
            lead, one = {}, {"g1_only": 0, "b1_only": 0}
            for r in rows:
                other = b1.get(r["item_id"])
                if other is None:
                    continue
                g1_right, b1_right = r["cls"] == r["gold"], other["cls"] == r["gold"]
                if g1_right != b1_right:
                    one["g1_only" if g1_right else "b1_only"] += 1
                    lead[r["document_id"]] = lead.get(r["document_id"], 0) + (1 if g1_right else -1)
            out.setdefault(group, {})[benchmark] = dict(one, documents_g1_ahead=sum(1 for v in lead.values() if v > 0),
                                                        documents_b1_ahead=sum(1 for v in lead.values() if v < 0))
    return out


def _all_evidence(units, evidence):
    return bool(units) and set(units) <= set(evidence or ())


def quotes_evidence(quote, units, evidence):
    """Every unit holding the quote is evidence, and the quote is long enough to say where it came
    from, so a word found all over counts for nothing."""
    return _all_evidence(units, evidence) and len((quote or "").split()) >= BAR_EVIDENCE_WORDS


def _lf_sha(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def keys_digest(sc, keys):
    """One digest over every key's own, in sorted order: what the items file records of the keys."""
    return _sha("\n".join(sorted(sc.key_digest(k) for k in keys)))


def _pinned(bar_items):
    return _lf_sha(bar_items) == BAR_ITEMS_SHA256


def _matches_repository(value):
    return bool(value.get("repository_config_matches") and value.get("repository_b1_prompt_matches"))


def _same_groups(value, per_group):
    return set(value.get("groups") or ()) == set(per_group)


def _same_prompts(value, manifest):
    return value.get("prompts_sha256") == manifest.get("prompts_sha256")


def _same_keys(digest, manifest):
    return digest == manifest.get("keys_sha256")


def _no_verdict_yet(out):
    """False when the folder already holds a verdict; a score that gave none blocks nothing."""
    path = Path(out) / "g1_scores.json"
    return not path.exists() or json.loads(path.read_text(encoding="utf-8")).get("bar") is None


def _finished(value):
    return value.get("complete") is True


def verdict_refusal(value, per_group, manifest, bar_items, digest):
    """None, or why this score gives no verdict."""
    if not manifest:
        return "no --bar-items: the decision's items were not given"
    if not _finished(value):
        return "the pass did not finish: what it answered is scored, and a decision says what follows"
    if not _pinned(bar_items):
        return "the items file is not the one D-243 pinned"
    if not _matches_repository(value):
        return "the prompts' config or B1 prompt differs from the repository's"
    if not _same_groups(value, per_group):
        return "a model the config names has no scores"
    if not _same_prompts(value, manifest):
        return "the prompts are not the ones the items file names"
    if not _same_keys(digest, manifest):
        return "the keys are not the ones the items file names"
    return bar_refusal(per_group, manifest)


def score(judgements_path, keys, out, bar_items=None):
    """g1_scores.json and G1_RESULTS.md (see the module text)."""
    sc = _score_corpus()
    out = Path(out)
    manifest = json.loads(Path(bar_items).read_text(encoding="utf-8")) if bar_items else None
    left_out = set((manifest or {}).get("left_out") or ())
    if not _no_verdict_yet(out):
        raise ValueError("this folder already holds a verdict: the first score stands (D-243)")
    value = json.loads(Path(judgements_path).read_text(encoding="utf-8"))
    rows = value["judgements"]
    comparator = value.get(COMPARATOR) or []
    groups = sorted({r["group"] for r in rows})
    tables = {}
    for key in keys:
        table = sc.item_table(key)
        doc_id, benchmark = table["document_id"], table["benchmark"]
        if doc_id in tables:
            raise ValueError("two keys name document " + doc_id)
        spec = _adapter(benchmark).SPEC
        mine = [r for r in rows if r["document_id"] == doc_id]
        if not mine:
            raise ValueError("no judgement for the key's document " + doc_id)
        by_rule = {}
        for item in table["items"]:
            if item["rule_id"].lower() in by_rule:
                raise ValueError("two items of %s name rule %s" % (doc_id, item["rule_id"]))
            by_rule[item["rule_id"].lower()] = item
        tables[doc_id] = (key, benchmark, spec, by_rule)
    per_group = {}
    for group in groups:
        for view in VIEWS:
            for doc_id, (key, benchmark, spec, by_rule) in tables.items():
                folder = out / "labels" / group / view / doc_id
                mine = {r["rule_id"].lower(): r for r in rows if r["group"] == group and r["document_id"] == doc_id}
                if set(mine) != set(by_rule):
                    raise ValueError("the judgements and the key's items of %s name different rules" % doc_id)
                sources = {}
                for rid, item in by_rule.items():
                    r = mine[rid]
                    if r.get("item_id") not in (None, item["item_id"]):
                        raise ValueError("the item id of %s %s differs from the key's" % (doc_id, rid))
                    cls, source = view_class(r, view)
                    name = label_name(spec, cls) if cls != ABSTAIN else None
                    _write_json(folder / "labels" / (item["item_id"] + ".json"), {
                        "arm": "G1", "schema": "b1-label-v2", "item_id": item["item_id"], "document_id": doc_id,
                        "rule_id": item["rule_id"], "benchmark": benchmark, "label": name, "abstain": name is None,
                        "evidence": r.get("quote"), "reason": r.get("reason"), "g1_source": source,
                        "g1_refusal": r.get("refusal"), "group": group, "view": view})
                    sources[item["item_id"]] = (source, r)
                labelled = sc.benchmark_labels(key, folder, arm="B1")
                if labelled.get("availability") != "labelled" or labelled.get("arm") != "B1":
                    raise ValueError("the scorer did not label %s as a B1 folder: %s"
                                     % (doc_id, labelled.get("availability")))
                bench = per_group.setdefault(group, {}).setdefault(view, {}).setdefault(benchmark, [])
                for item in labelled["items"]:
                    if item["item_id"] in left_out:
                        continue
                    source, r = sources[item["item_id"]]
                    bench.append({"document_id": doc_id, "item_id": item["item_id"], "gold": item["gold_class"],
                                  "cls": item["b1_class"], "basis": item["basis"], "source": source,
                                  "was_refused": r["source"] == REFUSED, "written_cls": r["written_cls"],
                                  "quote": r.get("quote"), "truncated": r.get("length_reached_allowance") is True,
                                  "quotes_evidence": quotes_evidence(r.get("quote"), r.get("quote_units"), item.get("evidence_unit_ids"))})
            for doc_id, (key, benchmark, spec, by_rule) in tables.items() if view == VIEWS[-1] else ():
                mine = {r["rule_id"].lower(): r for r in comparator if r["group"] == group and r["document_id"] == doc_id}
                if not mine:
                    continue
                if set(mine) != set(by_rule):
                    raise ValueError("the comparator and the key's items of %s name different rules" % doc_id)
                folder = out / "labels" / group / COMPARATOR / doc_id
                for rid, item in by_rule.items():
                    r = mine[rid]
                    if r["item_id"] != item["item_id"]:
                        raise ValueError("the item id of %s %s differs from the key's" % (doc_id, rid))
                    _write_json(folder / "labels" / (item["item_id"] + ".json"), {
                        "arm": "B1", "schema": "b1-label-v2", "item_id": item["item_id"], "document_id": doc_id,
                        "rule_id": item["rule_id"], "benchmark": benchmark, "label": r["label"], "abstain": r["abstain"],
                        "evidence": r["evidence"], "reason": r["reason"], "parse_failure": r["parse_failure"],
                        "group": group, "view": COMPARATOR})
                labelled = sc.benchmark_labels(key, folder, arm="B1")
                if labelled.get("availability") != "labelled" or labelled.get("arm") != "B1":
                    raise ValueError("the scorer did not label %s as a B1 folder: %s" % (doc_id, labelled.get("availability")))
                bench = per_group.setdefault(group, {}).setdefault(COMPARATOR, {}).setdefault(benchmark, [])
                evidence = {r["item_id"]: r for r in mine.values()}
                for item in labelled["items"]:
                    if item["item_id"] in left_out:
                        continue
                    bench.append({"document_id": doc_id, "item_id": item["item_id"], "gold": item["gold_class"],
                                  "cls": item["b1_class"], "basis": item["basis"], "source": "b1_label",
                                  "was_refused": False, "written_cls": item["b1_class"], "quote": evidence[item["item_id"]]["evidence"],
                                  "truncated": evidence[item["item_id"]].get("length_reached_allowance") is True})
    figures = {g: {v: {b: metrics(s) for b, s in sorted(bench.items())} for v, bench in views.items()}
               for g, views in per_group.items()}
    flags = {g: {v: [{k: r[k] for k in ("document_id", "item_id", "gold", "cls", "quote")} | {"benchmark": b}
                     for b, s in sorted(views[v].items()) for r in s
                     if (r["source"] == KEPT_CLAIM if v == "screened" else r["cls"] == "FLAG")]
                 for v in ("screened", COMPARATOR) if v in views}
             for g, views in per_group.items()}
    refused = verdict_refusal(value, per_group, manifest, bar_items, keys_digest(sc, keys))
    result = {"schema": "doc-judge-scores-v1", "models": value.get("models"), "views": list(VIEWS),
              "left_out": sorted(left_out), "bar": None if refused else bar(figures), "bar_refused": refused,
              "flags": flags, "discordant": discordant(per_group),
              "doc_judge_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "bar_items_sha256": _lf_sha(bar_items) if bar_items else None,
              "judgements_sha256": hashlib.sha256(Path(judgements_path).read_bytes()).hexdigest(),
              "key_sha256": {t[0]: sc.key_digest(t[0]) for t in tables.values()},
              "prompts_sha256": value.get("prompts_sha256"), "run_id": value.get("run_id"),
              "repository_config_matches": value.get("repository_config_matches"),
              "repository_b1_prompt_matches": value.get("repository_b1_prompt_matches"),
              "judging": value.get("counts"), "scores": figures,
              "scored_by": "tools/score_corpus.py benchmark_labels (the adapters' label_b1 and Spec); the keys were opened there only",
              "statement": "development, exposed; not comparable with published numbers"}
    _write_json(out / "g1_scores.json", result)
    _write_text(out / "G1_RESULTS.md", report(result))
    return result


def _pct(value):
    return "n/a" if value is None else "%.2f" % value


def report(result):
    lines = ["# G1 document-level judging: results", "",
             "Development, exposed. Not comparable with published numbers. Scored through tools/score_corpus.py.", "",
             "Views: screened (the judge's own reading: a refused answer is ABSTAIN), unscreened (the outcome as "
             "written, no quote rule), as_b3 (a refused answer read as silence, the nothing-wrong class). Silence is "
             "counted apart and is never a detection.", ""]
    for group, views in result["scores"].items():
        model = (result.get("models") or {}).get(group) or {}
        lines += ["## %s (%s)" % (group, model.get("model_id") or "model not recorded"), ""]
        judging = (result.get("judging") or {}).get(group) or {}
        lines += ["Answers: %s prompts, %s kept claims, %s kept cannot be settled, %s refused (%s), %s without a reply (%s)."
                  % (judging.get("prompts"), judging.get("kept_claim"), judging.get("kept_unsettled"), judging.get("refused"),
                     ", ".join("%s %s" % kv for kv in sorted((judging.get("refusals") or {}).items())) or "none",
                     judging.get("no_reply"),
                     ", ".join("%s %s" % kv for kv in sorted((judging.get("no_reply_reasons") or {}).items())) or "none"), ""]
        lines += ["| view | benchmark | items | precision | recall | F1 | accuracy | refusals (unreadable / removed a wrong answer / removed a right answer) | labels by source | correct by source |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for view, benches in views.items():
            for bench, m in benches.items():
                lines.append("| %s | %s | %d | %s | %s | %s | %s | %d (%d / %d / %d) | %s | %s |" % (
                    view, bench, m["items"], _pct(m["precision"]), _pct(m["recall"]), _pct(m["f1"]), _pct(m["accuracy"]),
                    m["refusals"], m["refusals_unreadable"], m["correct_refusals"], m["refusals_that_removed_a_right_answer"],
                    ", ".join("%s %d" % kv for kv in m["labels_by_source"].items()),
                    ", ".join("%s %d" % kv for kv in m["correct_by_source"].items()) or "none"))
        lines.append("")
        for view, rows in ((result.get("flags") or {}).get(group) or {}).items():
            lines += ["%s of `%s` (%d), each with its quote:" % ("Kept claims" if view == "screened" else "Flags", view, len(rows)), ""]
            lines += ["- %s %s (%s, gold %s): %s" % (r["benchmark"], r["item_id"], r["cls"], r["gold"], json.dumps(r["quote"], ensure_ascii=False))
                      for r in rows]
            lines.append("")
    verdict = result.get("bar")
    lines += ["## The bar (D-241)", ""]
    if verdict is None:
        lines += ["Not read: " + str(result.get("bar_refused") or "this run has no comparator on both benchmarks") + ".", ""]
    else:
        for group, row in verdict["rows"].items():
            for bench, r in row.items():
                failed = [] if r["state"] == "void" else [k for k, v in r.items() if v is False and k not in ("passes", "void")
                                                          and not (r["void"] and k == "net_rate_at_least_b1")]
                lines.append("- %s, %s: %s (screened %s; B1 %s; chance %s; gold %s of %s)%s" % (
                    group, bench, "void: B1 too often unreadable" if r["state"] == "void" else "meets" if r["passes"] else "misses",
                    r["screened"], r["b1"], r["chance"], r["gold"], r["items"],
                    "; missed: " + ", ".join(failed) if failed else ""))
        lines += ["", "Verdict: %s. Models meeting it on both: %s. A pass is %s."
                  % (verdict["verdict"], ", ".join(verdict["models_passing"]) or "none", verdict["means"]), ""]
    for group, benches in (result.get("discordant") or {}).items():
        for bench, d in benches.items():
            lines.append("- Only one arm right, %s %s: G1 %d, B1 %d; documents ahead: G1 %d, B1 %d (reported, not a condition)."
                         % (group, bench, d["g1_only"], d["b1_only"], d["documents_g1_ahead"], d["documents_b1_ahead"]))
    lines.append("")
    if result.get("left_out"):
        lines += ["Left out of every figure: " + ", ".join(result["left_out"]), ""]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(prog="doc_judge.py", allow_abbrev=False, description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    b = commands.add_parser("build", allow_abbrev=False)
    b.add_argument("--workload", action="append", required=True)
    b.add_argument("--items", action="append", default=[])
    b.add_argument("--benchmark", action="append", default=[])
    b.add_argument("--config", default=str(CONFIG_PATH))
    b.add_argument("--b1", action="store_true", help="add B1's own prompt per model group and item (needs --items)")
    b.add_argument("--agent-calls", help="saved judging prompts to replay, in place of the document prompts (J1)")
    b.add_argument("--out", required=True)
    j = commands.add_parser("judge", allow_abbrev=False)
    j.add_argument("--prompts", required=True)
    j.add_argument("--run", required=True, help="the pass folder (evidence/b1/<pass name>)")
    j.add_argument("--out", required=True)
    s = commands.add_parser("score", allow_abbrev=False)
    s.add_argument("--judgements", required=True)
    s.add_argument("--key", action="append", required=True)
    s.add_argument("--bar-items", help="the items the decision fixed and those left out (g1_bar_items.json)")
    s.add_argument("--out", required=True)
    return parser


def main(argv=None):
    args = build_parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    try:
        if args.command == "build":
            value = build(args.workload, args.out, items=args.items, benchmarks=args.benchmark, config_path=args.config, b1=args.b1,
                          agent_calls=args.agent_calls)
            print(json.dumps({"prompt_count": value["prompt_count"], "documents": len(value["documents"]),
                              "sha256": hashlib.sha256(Path(args.out).read_bytes()).hexdigest()}, indent=1))
        elif args.command == "judge":
            print(json.dumps(judge(args.prompts, args.run, args.out)["counts"], indent=1))
        else:
            result = score(args.judgements, args.key, args.out, bar_items=args.bar_items)
            print(report(result).encode("ascii", "backslashreplace").decode("ascii"))
        return 0
    except Exception as exc:
        print("doc_judge stopped: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
