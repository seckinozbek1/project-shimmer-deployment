"""Instruction optimisation tooling (#255; docs/loop/stages/notes/DESIGN_instruction_optimisation.md).

Development material only; nothing here reads a key, a gate-set id or a reply. Two targets, each a
decision question in config whose answers are decided from the judge's own probabilities (CHOICE-A):

  T1  config/passage_pairs.json  decision.template   rendered by passage_pairs.render
  T2  config/cell_selection.json decision.template   rendered by cell_selection.question

A candidate may change only the text BEFORE the shipped answer block (from "Answer with one word."
to the end), which it must end with byte for byte, so the answers' tokens and the next-token read
are unchanged. `screen` checks structure only (WORDS-A: no meaning is decided here): the answer block,
each shipped placeholder exactly once and no other, and the length under 1.5 times the shipped text.
`candidate_config` gives the target's config with a candidate in place, for its own renderer.
`proposer_prompt` writes the proposer's request from the shipped text, its fixed answers and
FIT-only counts (per gold class and per decided class), never an item.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {"T1": "config/passage_pairs.json", "T2": "config/cell_selection.json"}
ANSWER_BLOCK_START = "Answer with one word."
MAX_LENGTH_FACTOR = 1.5
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def target_config(target, root=ROOT):
    if target not in TARGETS:
        raise ValueError("the targets are T1 and T2, not %r" % (target,))
    return json.loads((Path(root) / TARGETS[target]).read_text(encoding="utf-8"))


def shipped(target, root=ROOT):
    return target_config(target, root)["decision"]["template"]


def answer_block(template):
    at = template.find(ANSWER_BLOCK_START)
    if at < 0:
        raise ValueError("the shipped question has no answer block")
    return template[at:]


def screen(target, candidate, root=ROOT):
    """(True, "") or (False, the first structural reason the candidate is refused)."""
    base = shipped(target, root)
    if not isinstance(candidate, str) or not candidate.strip():
        return False, "empty"
    block = answer_block(base)
    if not candidate.endswith(block) or candidate.count(ANSWER_BLOCK_START) != 1:
        return False, "the answer block is not the shipped one, once, at the end"
    want = sorted(PLACEHOLDER.findall(base))
    have = sorted(PLACEHOLDER.findall(candidate))
    if have != want:
        return False, "placeholders %s, not the shipped %s" % (have, want)
    if len(candidate) > MAX_LENGTH_FACTOR * len(base):
        return False, "longer than %.1f times the shipped question" % MAX_LENGTH_FACTOR
    if candidate == base:
        return False, "the shipped question itself"
    return True, ""


def candidate_config(target, candidate, root=ROOT):
    """The target's config with `candidate` as its decision template, refused unless it screens."""
    ok, why = screen(target, candidate, root)
    if not ok:
        raise ValueError("candidate refused: " + why)
    config = copy.deepcopy(target_config(target, root))
    config["decision"]["template"] = candidate
    if "form" in config:
        # The question is asked in the decision form (the measured K1 setting); the shipped
        # passage_pairs form stays `reply` in the product until a decision adopts it.
        config["form"] = "decision"
    return config


def candidate_id(candidate):
    return "cand_" + hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:12]


def proposer_prompt(target, fit_counts, best=None, n=8, root=ROOT):
    """The proposer's request: the shipped question, the answer block it must keep, what FIT showed
    as counts only ({"gold": {class: n}, "decided": {class: n}, "undecided": n}), and in round 2 the
    best texts so far with their FIT figure. No item, passage, cell or claim text is included."""
    if not isinstance(fit_counts, dict) or set(fit_counts) - {"gold", "decided", "undecided"}:
        raise ValueError("fit_counts holds counts only: gold, decided, undecided")
    for value in fit_counts.values():
        if isinstance(value, dict):
            if not all(isinstance(v, int) for v in value.values()):
                raise ValueError("fit_counts holds counts only")
        elif not isinstance(value, int):
            raise ValueError("fit_counts holds counts only")
    base = shipped(target, root)
    lines = ["You rewrite the instruction part of a yes/no/unclear question that a separate model answers with one word.",
             "Keep every placeholder in braces exactly once. End with this answer block exactly, unchanged:",
             "<<<", answer_block(base), ">>>",
             "The current question:", "<<<", base, ">>>",
             "On the development items it was asked on, the counts were: " + json.dumps(fit_counts, sort_keys=True) + "."]
    for text, figure in (best or []):
        lines += ["A rewrite that scored %.3f:" % figure, "<<<", text, ">>>"]
    lines += ["Write %d different rewrites. Put each between <<< and >>>, nothing else." % n]
    return "\n".join(lines)


def read_proposals(reply):
    """The texts between <<< and >>> in a proposer reply, in order, deduplicated."""
    seen, out = set(), []
    for text in re.findall(r"<<<\n?(.*?)\n?>>>", str(reply or ""), re.DOTALL):
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


PROPOSER_MODEL = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"
PROPOSER_ALLOWANCE = 1536


def proposer_file(requests, out, tokenizer=None):
    """A replay prompts file of the proposer form (replay_prompts.PROPOSER_FORM): one prompt per
    request, each rendered as one user turn through the base model's own chat template (the local
    cache only), run on the base with no adapter, the sdpa path alone. `requests` is
    [(set_label, text)]. Returns the written value."""
    import replay_prompts
    if tokenizer is None:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(PROPOSER_MODEL, local_files_only=True)
    prompts = []
    for i, (label, text) in enumerate(requests, 1):
        rendered = tokenizer.apply_chat_template([{"role": "user", "content": text}], add_generation_prompt=True, tokenize=False)
        prompts.append({"prompt_id": "p%04d" % i, "set": label, "form": replay_prompts.PROPOSER_FORM, "agent": "PROPOSER",
                        "backend": replay_prompts.PRODUCER_BACKEND, "model_id": None, "doc_id": "",
                        "max_new_tokens": PROPOSER_ALLOWANCE, "prompt": rendered,
                        "prompt_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest()})
    value = {"schema": replay_prompts.SCHEMA, "sources": [{"proposer": "instruction_opt"}], "min_chars": 0,
             "prompt_count": len(prompts), "prompts": prompts}
    Path(out).write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    replay_prompts.load_prompts(out)
    return value
