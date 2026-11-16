"""D-713, document review half: two reasoning methods for the claim and passage choice questions.

Shimmer's small local models have no thinking mode of their own, so more reasoning is asked for by
method. The questions are the two ContraDoc and SciTab measure on the replay pass (doc_judge.py
form `choice`): `pair` (do two passages of one document contradict each other) and `claim` (do the
table cells select_cells chose show that a claim holds). Development only, exposed, off by default.

A choice config may declare `choice.methods`; a model group picks one by its `method` key. A group
with no `method`, or `method: direct`, is asked exactly as before: one forward pass over the form's
own question, byte for byte (the shipped choice_judge_prompt.json declares no method). A method is
chosen in config, never typed in, and the config is pinned by its digest in every prompts file.

  reason_first   1. rationale: the model writes a short rationale after the declared field label
                    (generated, at most `allowance` tokens). Python keeps the field's first line,
                    whitespace-normalised and cut at `rationale_chars`, and nothing else of the
                    reply.
                 2. label: the form's question with the rationale shown, decided from the model's
                    probabilities over the form's own answers (choice_decision), so the answer's
                    format cannot break. The rationale is never scored and never read for meaning
                    (WORDS-A); an empty one is counted and shown as empty, never a refusal.

  stepwise       1. evidence: claim, the ids of the cells the claim rests on, from a list Python
                    numbered (R<row>C<column>, the selected cells only); pair, one quote from each
                    passage after the fields `A:` and `B:`. Generated. Python checks it before the
                    next step: every id named exists in the list and at most `max_cells` are named;
                    each quote is found in its own passage (whitespace-normalised) and is its
                    content (doc_judge.quote_is_content, open item 84).
                 2. comparison: the checked evidence (Python's rendering of the named cells, or
                    the two quotes) against the claim, or the two quotes against each other,
                    decided from probabilities over the method's declared comparison answers. A tie
                    is refused.
                 3. label: the form's question with the evidence and the comparison shown, decided
                    over the form's own answers.
                 A step that fails its check stops the chain: the prompt has no decision (an
                 abstention, counted in the dropped-answer rate by its step and reason). Python never
                 decides the label and never repairs a step's output beyond its form (outer spaces,
                 a matched pair of quote marks, the field label).

Every model call is one reply record (REPLIES-A). The chain's LAST call is the prompt's record in
the pass folder (the runner's one-record-per-prompt count, tools/ordinary_final_run.py
replay_observation, unchanged); the earlier steps' records go to `<pass>/method_steps/`. A refused
step's record is written with backend_ok false and error `method_refused: <step> <reason>` and no
decision, so no reader takes a comparison's probabilities for a label.

`dropped(rows)` reads a pass's measurement rows: per group, the prompts with no decision by reason.
`adopt(direct, method, bar)` is D-713's adoption rule on development figures.
"""
from __future__ import annotations

import re

DIRECT = "direct"
REASON_FIRST = "reason_first"
STEPWISE = "stepwise"
METHODS = (DIRECT, REASON_FIRST, STEPWISE)
STEPS_DIR = "method_steps"
KINDS = ("pair", "claim")

# The slots each step's template fills, by method and kind; a template fills exactly these.
SLOTS = {
    REASON_FIRST: {
        "pair": {"rationale": {"passage_a", "passage_b"}, "label": {"passage_a", "passage_b", "reasoning"}},
        "claim": {"rationale": {"cells", "claim", "tools"}, "label": {"cells", "claim", "tools", "reasoning"}},
    },
    STEPWISE: {
        "pair": {"evidence": {"passage_a", "passage_b"}, "comparison": {"quote_a", "quote_b"},
                 "label": {"passage_a", "passage_b", "evidence", "comparison"}},
        "claim": {"evidence": {"cell_list", "claim"}, "comparison": {"evidence", "claim"},
                  "label": {"cells", "claim", "tools", "evidence", "comparison"}},
    },
}
STEP_ORDER = {REASON_FIRST: ("rationale", "label"), STEPWISE: ("evidence", "comparison", "label")}
GENERATED = {"rationale", "evidence"}
_SLOT = re.compile(r"\{(passage_a|passage_b|cells|claim|tools|reasoning|cell_list|quote_a|quote_b|evidence|comparison)\}")
_WS = re.compile(r"\s+")
_CELL_ID = re.compile(r"\bR(\d+)\s*C(\d+)\b", re.I)
_QUOTES = (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"), ("`", "`"), ("*", "*"))

# Step refusals, each its own reason in the dropped-answer count.
NO_CELL_NAMED, CELL_NOT_SHOWN, TOO_MANY_CELLS = "no_cell_named", "cell_not_shown", "too_many_cells"
QUOTE_MISSING, QUOTE_NOT_FOUND, QUOTE_NOT_CONTENT = "quote_missing", "quote_not_found", "quote_not_content"
COMPARISON_TIE, OVER_CONTEXT = "comparison_tie", "prompt_over_context"
REASONS = (NO_CELL_NAMED, CELL_NOT_SHOWN, TOO_MANY_CELLS, QUOTE_MISSING, QUOTE_NOT_FOUND, QUOTE_NOT_CONTENT,
           COMPARISON_TIE, OVER_CONTEXT)


class StepRefused(ValueError):
    """A step's output failed its Python check; `reason` is one of REASONS."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def method_of(group):
    return group.get("method") or DIRECT


def _norm(text):
    return _WS.sub(" ", str(text)).strip()


def _fills(template):
    return {m.group(1) for m in _SLOT.finditer(template)} if isinstance(template, str) else None


def check(choice, groups):
    """Refuses a methods block or a group's method that is not as declared here. Called from
    doc_judge.check_config, so a prompts file whose config breaks it never loads."""
    import choice_decision
    methods = (choice or {}).get("methods") if isinstance(choice, dict) else None
    forms = (choice or {}).get("forms") or {} if isinstance(choice, dict) else {}
    for g in groups:
        name = g.get("method", DIRECT)
        if name not in METHODS:
            raise ValueError("a group's method is one of: " + ", ".join(METHODS))
        if name != DIRECT and name not in (methods or {}):
            raise ValueError("group %s names method %s, which its choice block does not declare" % (g.get("group"), name))
    if methods is None:
        return
    if not isinstance(methods, dict) or not methods or set(methods) - {REASON_FIRST, STEPWISE}:
        raise ValueError("a methods block declares reason_first or stepwise, nothing else (direct is the form itself)")
    for name, method in methods.items():
        allowance = method.get("allowance") if isinstance(method, dict) else None
        if type(allowance) is not int or not 0 < allowance <= 512:
            raise ValueError("method %s declares its generated allowance, 1 to 512 tokens" % name)
        if name == REASON_FIRST and not (isinstance(method.get("field"), str) and method["field"].strip()
                                         and type(method.get("rationale_chars")) is int and method["rationale_chars"] > 0):
            raise ValueError("reason_first declares its field label and rationale_chars")
        if name == STEPWISE:
            fields = method.get("fields")
            if not (isinstance(fields, dict) and all(isinstance(fields.get(k), str) and fields[k].strip() for k in ("cells", "quote_a", "quote_b"))
                    and type(method.get("max_cells")) is int and method["max_cells"] > 0):
                raise ValueError("stepwise declares its fields (cells, quote_a, quote_b) and max_cells")
        declared = method.get("forms")
        if not isinstance(declared, dict) or not declared or set(declared) - set(forms):
            raise ValueError("method %s declares templates for forms its choice block declares" % name)
        for kind, steps in declared.items():
            for step, slots in SLOTS[name][kind].items():
                value = steps.get(step) if isinstance(steps, dict) else None
                template = value.get("template") if step == "comparison" and isinstance(value, dict) else value
                if _fills(template) != slots:
                    raise ValueError("method %s, form %s, step %s fills %s" % (name, kind, step, ", ".join(sorted(slots))))
                if step == "comparison":
                    answers = value.get("answers")
                    choice_decision.declare(template, answers)
                    if not all(isinstance(a.get("shown"), str) and a["shown"].strip() for a in answers):
                        raise ValueError("each comparison answer declares the line the label step shows")
                if step == "label":
                    choice_decision.declare(template, forms[kind]["answers"])


def render(template, slots):
    """One pass over the template, so a passage's braces stay text."""
    return _SLOT.sub(lambda m: slots[m.group(1)], template)


# ---------------------------------------------------------------------------
# the slots, from the document's own text


def slots(config, doc, prompt):
    """(kind, slots) of a choice prompt: the passages, or the selected cells, the claim and the
    `{tools}` slot as the form itself fills them (doc_judge.choice_user's reading)."""
    import doc_judge
    import judge_agent
    kind = prompt.get("choice")
    if kind == "pair":
        first, second = doc_judge.pair_passages(doc, prompt)
        return kind, {"passage_a": first, "passage_b": second}
    cells = doc_judge.select_cells(doc["text"], prompt["claim"])["cells"]
    return kind, {"cells": cells, "claim": prompt["claim"], "tools": judge_agent.claim_tools(cells, prompt["claim"])}


def cell_list(cells):
    """{id: line} of the selected cells shown, numbered by Python: R<row>C<column>, both from 1 over
    the shown table's body rows and its columns, with the row's label and the column's header.
    The label columns (cell_selection.key_columns) are labels, not cells to cite; a table holding
    nothing else lists every column."""
    import cell_selection
    found = cell_selection.tables(cells)
    if not found:
        return {}
    table = found[0]
    keys = cell_selection.key_columns(table)
    columns = [c for c in range(len(table["header"])) if c not in keys] or list(range(len(table["header"])))
    out = {}
    for r, row in enumerate(table["rows"]):
        label = " / ".join(row[k] for k in keys if row[k]) or "row %d" % (r + 1)
        for c in columns:
            if row[c].strip():
                out["R%dC%d" % (r + 1, c + 1)] = '%s / %s = %s' % (label, table["header"][c], row[c])
    return out


# ---------------------------------------------------------------------------
# reading a generated step: form only (ANSWER-FORM-A), never meaning (WORDS-A)


def _unwrap(text):
    text = text.strip()
    for left, right in _QUOTES:
        if len(text) >= 2 and text.startswith(left) and text.endswith(right):
            return text[len(left):-len(right)].strip()
    return text


def _after_label(line, label):
    head = line.lstrip()
    return head[len(label):].strip() if head.casefold().startswith(label.strip().casefold()) else None


def field_value(text, label):
    """The value of the fixed field `label` in a generated reply: the text after the label on its
    first line that carries it (or on the next non-empty line, when the label stands alone); with no
    line carrying it, the reply's first non-empty line. "" for an empty reply."""
    lines = [line for line in str(text or "").splitlines() if line.strip()]
    for at, line in enumerate(lines):
        value = _after_label(line, label)
        if value is not None:
            return _unwrap(value or (lines[at + 1] if at + 1 < len(lines) else ""))
    return _unwrap(lines[0]) if lines else ""


def rationale(text, method):
    """The rationale Python keeps: the field's value, whitespace-normalised, cut at the last space
    before `rationale_chars`. Never read for what it says."""
    value = _norm(field_value(text, method["field"]))
    cap = method["rationale_chars"]
    if len(value) > cap:
        cut = value[:cap]
        value = cut[:cut.rfind(" ")] if " " in cut else cut
    return value


def named_cells(text):
    """D-715 item 2: the cell ids (R<row>C<column>) a step's text names, by their form alone, each once in the
    order named, whether or not the list holds them. An audit record only: no check, label or score reads it."""
    named = []
    for m in _CELL_ID.finditer(str(text or "")):
        cid = "R%dC%d" % (int(m.group(1)), int(m.group(2)))
        if cid not in named:
            named.append(cid)
    return named


def cited_cells(text, method, listed):
    """The cell ids the evidence step names, checked: each one listed, at least one, at most
    `max_cells`, each once in the order named. StepRefused otherwise."""
    value = field_value(text, method["fields"]["cells"])
    named = []
    for m in _CELL_ID.finditer(value):
        cid = "R%dC%d" % (int(m.group(1)), int(m.group(2)))
        if cid not in named:
            named.append(cid)
    if not named:
        raise StepRefused(NO_CELL_NAMED)
    if any(cid not in listed for cid in named):
        raise StepRefused(CELL_NOT_SHOWN)
    if len(named) > method["max_cells"]:
        raise StepRefused(TOO_MANY_CELLS)
    return named


def cited_quotes(text, method, first, second):
    """(quote from passage A, quote from passage B), each after its field label, checked: present,
    found in its own passage once both are whitespace-normalised, and that passage's content."""
    import doc_judge
    out = []
    for label, passage in ((method["fields"]["quote_a"], first), (method["fields"]["quote_b"], second)):
        value = None
        for line in str(text or "").splitlines():
            value = _after_label(line, label)
            if value is not None:
                break
        quote = _norm(_unwrap(value or ""))
        if not quote:
            raise StepRefused(QUOTE_MISSING)
        if quote not in _norm(passage):
            raise StepRefused(QUOTE_NOT_FOUND)
        if not doc_judge.quote_is_content(quote, passage, {"marker_patterns": []}):
            raise StepRefused(QUOTE_NOT_CONTENT)
        out.append(quote)
    return tuple(out)


# ---------------------------------------------------------------------------
# the chain


def run_method(name, config, kind, slot_values, *, generate, choose, fits, steps):
    """Runs method `name` on one choice prompt. `generate(user, allowance)` and `choose(user, answers)`
    are the backend's calls on the model's own template (one user turn); `fits(user, allowance)` is
    whether a step's prompt fits the model's context. Each call is appended to `steps` as it returns
    ({step, op, user, allowance, result, check}), so a caller whose backend raises still holds every
    call made. Returns {"final": the label step's result or None, "refused": None or {step, reason}}."""
    method = config["choice"]["methods"][name]
    declared = method["forms"][kind]
    answers = config["choice"]["forms"][kind]["answers"]
    values = dict(slot_values)

    def call(step, user, op_value):
        op = "generate" if step in GENERATED else "choose"
        allowance = method["allowance"] if op == "generate" else 0
        entry = {"step": step, "op": op, "user": user, "allowance": allowance, "result": None, "check": "ok"}
        if not fits(user, allowance):
            entry["check"] = OVER_CONTEXT
            steps.append(entry)
            raise StepRefused(OVER_CONTEXT)
        steps.append(entry)
        entry["result"] = (generate(user, allowance) if op == "generate" else choose(user, op_value)) or {}
        return entry

    try:
        if name == REASON_FIRST:
            first = call("rationale", render(declared["rationale"], values), None)
            values["reasoning"] = rationale(first["result"].get("text"), method)
            first["kept_chars"] = len(values["reasoning"])
            if kind == "claim":
                # D-715 item 2: a cell the rationale names is recorded (the kept line, the one shown), never read.
                first["cells_named"] = named_cells(values["reasoning"])
        else:
            if kind == "claim":
                listed = cell_list(values["cells"])
                values["cell_list"] = "\n".join("%s: %s" % item for item in listed.items())
                first = call("evidence", render(declared["evidence"], values), None)
                # D-715 item 2: every id the evidence step names is recorded, also when its check refuses it.
                first["cells_named"] = named_cells(field_value(first["result"].get("text"), method["fields"]["cells"]))
                try:
                    named = cited_cells(first["result"].get("text"), method, listed)
                except StepRefused as refused:
                    first["check"] = refused.reason
                    raise
                first["cells"] = named
                values["evidence"] = "\n".join("%s: %s" % (cid, listed[cid]) for cid in named)
                compare = {"evidence": values["evidence"], "claim": values["claim"]}
            else:
                first = call("evidence", render(declared["evidence"], values), None)
                try:
                    quote_a, quote_b = cited_quotes(first["result"].get("text"), method, values["passage_a"], values["passage_b"])
                except StepRefused as refused:
                    first["check"] = refused.reason
                    raise
                first["quotes"] = 2
                values["evidence"] = "A: %s\nB: %s" % (quote_a, quote_b)
                compare = {"quote_a": quote_a, "quote_b": quote_b}
            spec = declared["comparison"]
            second = call("comparison", render(spec["template"], compare), spec["answers"])
            decision = second["result"].get("decision") or {}
            if decision.get("top") is None:
                second["check"] = COMPARISON_TIE
                raise StepRefused(COMPARISON_TIE)
            second["compared"] = decision["top"]
            values["comparison"] = next(a["shown"] for a in spec["answers"] if a["label"] == decision["top"])
        last = call("label", render(declared["label"], values), answers)
        return {"final": last["result"], "refused": None}
    except StepRefused as refused:
        return {"final": None, "refused": {"step": steps[-1]["step"], "reason": refused.reason}}


def step_row(entry):
    """A step as the measurement row holds it: names, counts and numbers, never text."""
    import hashlib
    result = entry.get("result") or {}
    decision = result.get("decision") or {}
    row = {"step": entry["step"], "op": entry["op"], "check": entry["check"], "allowance": entry["allowance"],
           "user_sha256": hashlib.sha256(entry["user"].encode("utf-8")).hexdigest(),
           "output_tokens": result.get("output_tokens") if type(result.get("output_tokens")) is int else None}
    for key in ("kept_chars", "cells", "cells_named", "quotes", "compared"):
        if key in entry:
            row[key] = entry[key]
    if decision:
        row["probabilities"] = {a["label"]: a["probability"] for a in decision.get("answers") or []}
    return row


# ---------------------------------------------------------------------------
# reading the pass, and the adoption rule


def dropped(rows):
    """{group: {prompts, decided, dropped, rate, by_reason}} over a pass's measurement rows: a prompt
    is dropped when it has no decision, by a failed call (its failure kind) or a refused step
    (`<step>:<reason>`). A tie at the label is a decision (unsettled, as on the direct form)."""
    out = {}
    for row in rows:
        if row.get("form") != "choice":
            continue
        g = out.setdefault(row["group"], {"prompts": 0, "decided": 0, "dropped": 0, "by_reason": {}})
        g["prompts"] += 1
        refused = row.get("method_refused")
        reason = row.get("failure") or (refused and "%s:%s" % (refused["step"], refused["reason"]))
        if reason:
            g["dropped"] += 1
            g["by_reason"][reason] = g["by_reason"].get(reason, 0) + 1
        else:
            g["decided"] += 1
    for g in out.values():
        g["rate"] = g["dropped"] / g["prompts"] if g["prompts"] else None
    return out


def adopt(direct, method, bar):
    """D-713's adoption rule on the development sets. `direct` and `method` map each set to its
    figures ({figure: value} plus `dropped_rate`); `bar` maps each figure to its floor. A method is
    adopted only when, on every set, no figure moves away from its bar while at least one moves
    toward it (for a figure direct already holds at or above its floor: one that rises and stays
    there; one that falls but stays at or above the floor has not moved away), and its
    dropped-answer rate is not above direct's. Returns (adopted, reasons)."""
    reasons = []
    if not direct or set(direct) != set(method):
        return False, ["the method and direct were not measured on the same sets"]
    for name in sorted(direct):
        d, m = direct[name], method[name]
        toward = False
        for figure, floor in sorted(bar.items()):
            if figure not in d or figure not in m:
                reasons.append("%s: %s not measured on both" % (name, figure))
                continue
            gap_d, gap_m = max(0.0, floor - d[figure]), max(0.0, floor - m[figure])
            if gap_m > gap_d:
                reasons.append("%s: %s moved away from its bar (%.4f to %.4f)" % (name, figure, d[figure], m[figure]))
            elif gap_m < gap_d or (gap_d == 0 and m[figure] > d[figure]):
                toward = True
        if not toward:
            reasons.append("%s: no figure moved toward its bar" % name)
        if m.get("dropped_rate") is None or d.get("dropped_rate") is None or m["dropped_rate"] > d["dropped_rate"]:
            reasons.append("%s: the dropped-answer rate rose or was not measured" % name)
    return not reasons, reasons
