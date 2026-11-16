"""The table tools of a cell claim and the one request round (D-681, docs/loop/stages/TABLE_TOOL_DESIGN.md).

Python still selects the cells (CELLS-A). With the request switched on (a judge contract declaring
`request_tools` for `cell_claim`, honoured only under a ratified amendment, `tool_registry`), the
model may then ask, ONCE per claim and table, for what else it needs from the tools shown to it.
Python parses every line of that one reply, runs every call in one batch and hands the results
back as a RESULTS block in the question's existing `{tools}` slot; the unchanged `call_choice`
then decides. There is never a second round.

    context_of(table, claim)                      the JSON context every tool reads
    facts_of(context, selection)                  the structural facts `applies_when` reads
    render_request(request, cells, claim, ...)    the request's user text
    parse(reply, shown, ids, max_calls)           each line of the reply, read or refused
    execute(calls, context, registry)             every read call run, in one batch
    request_round(...)                            the whole round for one question

A tool takes only ids: a cell (`r3c2`, the table's row 3 below its header and column 2, counted
from 1 over the WHOLE table, so a cell the selection left out can be asked for), a figure the claim
writes (`f1`) or a column (`c2`). A typed number is refused (`literal_number`): the model cannot
invent a figure. Everything is structural; which arithmetic a claim asks for is never read here
(WORDS-A). A tool is a pure function of its context and its ids; `tools/vet_table_tool.py` checks
each one before the operator approves it.

The audit keeps digests only: a call's row names the tool, its argument ids, ok or the refusal's
reason and the SHA-256 of its result, never a value.
"""
import hashlib
import re

import cell_selection

REQUEST_TASK = "cell_claim_request"
REQUEST_PLAN = "cell_claim_request"
CELL, FIGURE, COLUMN, CELL_OR_FIGURE = "cell", "figure", "column", "cell_or_figure"
SLOT_TYPES = (CELL, FIGURE, COLUMN, CELL_OR_FIGURE)
NONE_REPLY = "NONE"
_CELL_ID = re.compile(r"r([1-9][0-9]*)c([1-9][0-9]*)")
_FIGURE_ID = re.compile(r"f([1-9][0-9]*)")
_COLUMN_ID = re.compile(r"c([1-9][0-9]*)")
_LITERAL = re.compile(r"[-+]?[0-9]+(?:[.,][0-9]+)*%?")
_CALL = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)")
_SIGNS = "-−"

# Refusal reasons, the program's own closed set.
ZERO_DIVISOR, PERCENT_AGAINST_PLAIN, NOT_ONE_NUMBER = "zero_divisor", "percent_against_plain", "not_one_number"
NO_NUMBERS, NOT_A_CALL, TOOL_NOT_SHOWN, ID_NOT_VALID = "no_numbers", "not_a_call", "tool_not_shown", "id_not_valid"
LITERAL_NUMBER, WRONG_ARGUMENTS, ABOVE_MAX_CALLS = "literal_number", "wrong_arguments", "above_max_calls"


class ToolRefused(ValueError):
    """A tool cannot answer for these ids: its message is the reason."""


def sha256(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


# ---------- the context ----------------------------------------------------------------------

def claim_figures(claim):
    """The figures `claim` writes, each value once, in its order: the token with a percent mark
    kept when the claim writes one after it."""
    text, out, seen = str(claim or ""), [], set()
    for match in cell_selection._NUMBER.finditer(text):
        value = cell_selection.figure_value(match.group(0))
        if value is None or value in seen:
            continue
        seen.add(value)
        percent = text[match.end():].lstrip().startswith("%")
        start = match.start()
        sign = "-" if start > 0 and text[start - 1] in _SIGNS else ""
        out.append(sign + match.group(0) + ("%" if percent else ""))
    return out


def context_of(table, claim):
    """{cells, columns, rows, figures}: every cell of `table` by its id, each column's header, the
    row count, and each figure the claim writes by its id. JSON-safe, so a tool can be run in a
    fresh process on it."""
    cells = {}
    for r, row in enumerate(table["rows"], 1):
        for c, value in enumerate(row, 1):
            cells["r%dc%d" % (r, c)] = value
    return {"cells": cells, "columns": {"c%d" % c: name for c, name in enumerate(table["header"], 1)},
            "rows": len(table["rows"]),
            "figures": {"f%d" % i: token for i, token in enumerate(claim_figures(claim), 1)}}


def number(text):
    """(value, percent) of a text holding exactly one figure, signed; ToolRefused otherwise."""
    text = str(text or "")
    found = [m for m in cell_selection._NUMBER.finditer(text) if cell_selection.figure_value(m.group(0)) is not None]
    if len(found) != 1:
        raise ToolRefused(NOT_ONE_NUMBER)
    match = found[0]
    value = cell_selection.figure_value(match.group(0))
    before = text[:match.start()].rstrip()
    if before and before[-1] in _SIGNS:
        value = -value
    return value, "%" in text[match.end():]


def value_of(context, ref):
    """The text an id stands for: a cell's text or a figure as the claim writes it."""
    if _FIGURE_ID.fullmatch(ref):
        if ref not in context["figures"]:
            raise ToolRefused(ID_NOT_VALID)
        return context["figures"][ref]
    if ref not in context["cells"]:
        raise ToolRefused(ID_NOT_VALID)
    return context["cells"][ref]


def fmt(value):
    """A number as the results write it: an integer plainly, otherwise up to six decimals."""
    value = 0.0 if value == 0 else float(value)
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return ("%.6f" % value).rstrip("0").rstrip(".")


def _pair(context, a, b):
    (x, px), (y, py) = number(value_of(context, a)), number(value_of(context, b))
    if px != py:
        raise ToolRefused(PERCENT_AGAINST_PLAIN)
    return x, y


# ---------- the six tools (D-681 item 1; the set is fixed in the design) -----------------------

def get_cells(context, *refs):
    """Each cell's text, by its id."""
    return "; ".join("%s = %s" % (ref, value_of(context, ref)) for ref in refs)


def difference(context, a, b):
    """a minus b."""
    x, y = _pair(context, a, b)
    return fmt(x - y)


def ratio(context, a, b):
    """a divided by b."""
    x, y = _pair(context, a, b)
    if y == 0:
        raise ToolRefused(ZERO_DIVISOR)
    return fmt(x / y)


def compare(context, a, b):
    """Whether a is greater than, less than or equal to b."""
    x, y = _pair(context, a, b)
    return "greater" if x > y else "less" if x < y else "equal"


def find_figure(context, figure):
    """The cells of the whole table that write the figure, by id."""
    value = cell_selection.figure_value(value_of(context, figure).strip("%"))
    at = [ref for ref, text in context["cells"].items() if value in cell_selection.figures(text)]
    return ", ".join(at) if at else "in no cell"


def column_extreme(context, column):
    """The highest and the lowest one-number cells of a column, over every row of the table."""
    match = _COLUMN_ID.fullmatch(column)
    if not match or column not in context["columns"]:
        raise ToolRefused(ID_NOT_VALID)
    found = []
    for r in range(1, context["rows"] + 1):
        ref = "r%dc%s" % (r, match.group(1))
        try:
            found.append((number(context["cells"].get(ref, ""))[0], ref))
        except ToolRefused:
            continue
    if not found:
        raise ToolRefused(NO_NUMBERS)
    high, low = max(v for v, _ in found), min(v for v, _ in found)
    return "highest %s = %s; lowest %s = %s" % (", ".join(ref for v, ref in found if v == high), fmt(high),
                                                ", ".join(ref for v, ref in found if v == low), fmt(low))


# ---------- what the request shows ------------------------------------------------------------

def facts_of(context, selection):
    """The structural facts `applies_when` reads (WORDS-A): how many shown cells hold one number, how
    many cells of the table the selection left out, how many figures the claim writes."""
    shown = 0
    for r in selection.get("rows") or []:
        for c in selection.get("columns") or []:
            try:
                number(context["cells"].get("r%dc%d" % (r + 1, c + 1), ""))
                shown += 1
            except ToolRefused:
                continue
    total = len(context["cells"])
    return {"shown_numbers": shown, "claim_figures": len(context["figures"]),
            "cells_left_out": total - len(selection.get("rows") or []) * len(selection.get("columns") or [])}


def ids_of(context):
    """{slot type: [ids]}: every id each slot type admits on this table and claim."""
    cells, figures = list(context["cells"]), list(context["figures"])
    return {CELL: cells, FIGURE: figures, COLUMN: list(context["columns"]), CELL_OR_FIGURE: cells + figures}


def slots_of(entry):
    """[(slot type, least, most)] of a registry entry's inputs; only the last may repeat."""
    out = []
    for slot in entry.get("inputs") or []:
        out.append((slot["type"], int(slot.get("min", 1)), int(slot.get("max", 1))))
    return out


def signature(entry):
    names = []
    for slot in entry.get("inputs") or []:
        name = slot["name"] + ("..." if int(slot.get("max", 1)) > 1 else "")
        names.append(name)
    return "%s(%s)" % (entry["name"], ", ".join(names))


def render_request(request, cells, claim, context, shown):
    """The request's user text: the question's cells and claim, the table's index (its columns and
    rows by id, row labels from its key columns), the claim's figures by id, and the shown tools."""
    columns = "; ".join("%s %s" % (ref, name) for ref, name in context["columns"].items())
    keys = [c + 1 for c in context.get("key_columns", [0])]
    rows = []
    for r in range(1, min(context["rows"], int(request["max_listed_rows"])) + 1):
        rows.append("r%d %s" % (r, " / ".join(context["cells"].get("r%dc%d" % (r, k), "") for k in keys)))
    figures = "; ".join("%s %s" % (ref, token) for ref, token in context["figures"].items()) or "none"
    index = "COLUMNS: %s\nROWS: %s\nFIGURES IN THE CLAIM: %s\n\n" % (columns, "; ".join(rows), figures)
    tools = "\n".join("%s: %s" % (signature(e), e["does"]) for e in shown)
    slots = {"cells": cells, "claim": claim, "index": index, "tools": tools, "max_calls": str(int(request["max_calls"]))}
    return re.sub(r"\{(cells|claim|index|tools|max_calls)\}", lambda m: slots[m.group(1)], request["template"])


def grammar_spec(shown, ids, max_calls):
    """What the request's decoding grammar admits (contract_decoding.RequestGrammar)."""
    return {"tools": [[e["name"], [list(s) for s in slots_of(e)]] for e in shown],
            "ids": {k: list(v) for k, v in ids.items()}, "max_calls": int(max_calls)}


# ---------- reading the one reply -------------------------------------------------------------

def _id_shaped(arg):
    return bool(_CELL_ID.fullmatch(arg) or _FIGURE_ID.fullmatch(arg) or _COLUMN_ID.fullmatch(arg))


def parse(reply, shown, ids, max_calls):
    """[{line, tool, args, refused}] for each non-blank line of the reply; [] for NONE. A line is
    refused (with its reason, never dropped) when it is above `max_calls`, not a call, a tool not
    shown, the wrong number of arguments, a typed number, or an id this table does not hold. `tool`
    is a shown tool's name or None, and `args` only ids, so no text of the reply is kept."""
    lines = [line.strip() for line in str(reply or "").splitlines() if line.strip()]
    if lines == [NONE_REPLY]:
        return []
    by_name = {e["name"]: e for e in shown}
    out = []
    for at, line in enumerate(lines):
        row = {"line": at, "tool": None, "args": [], "refused": None}
        out.append(row)
        match = _CALL.fullmatch(line)
        name = match.group(1) if match else None
        row["tool"] = name if name in by_name else None
        if at >= max_calls:
            row["refused"] = ABOVE_MAX_CALLS
            continue
        if not match:
            row["refused"] = NOT_A_CALL
            continue
        if name not in by_name:
            row["refused"] = TOOL_NOT_SHOWN
            continue
        args = [a.strip() for a in match.group(2).split(",")] if match.group(2).strip() else []
        row["args"] = [a for a in args if _id_shaped(a)]
        slots = slots_of(by_name[name])
        least = sum(s[1] for s in slots)
        most = sum(s[2] for s in slots)
        if not least <= len(args) <= most:
            row["refused"] = WRONG_ARGUMENTS
            continue
        if any(_LITERAL.fullmatch(a) for a in args):
            row["refused"] = LITERAL_NUMBER
            continue
        types = [s[0] for s in slots for _ in range(s[1])] + [slots[-1][0]] * (len(args) - least)
        if any(a not in ids[t] for a, t in zip(args, types)):
            row["refused"] = ID_NOT_VALID
    return out


def execute(calls, context, run):
    """Every read call run, in one batch: each row gains `ok`, its `value` (for the results block
    only) or its refusal. `run(name)` is the tool's function (tool_registry.resolve)."""
    for row in calls:
        row["ok"], row["value"] = False, None
        if row["refused"]:
            continue
        try:
            row["value"] = str(run(row["tool"])(context, *row["args"]))
            row["ok"] = True
        except ToolRefused as exc:
            row["refused"] = str(exc)
        except Exception as exc:   # a tool's own failure is a refusal, recorded, never a crash of the review
            row["refused"] = "tool_error_" + type(exc).__name__
    return calls


def results_block(request, calls):
    """The RESULTS block, one line per line of the reply; "" when there was none."""
    if not calls:
        return ""
    lines = []
    for row in calls:
        head = "%s(%s)" % (row["tool"], ", ".join(row["args"])) if row["tool"] else "line %d" % (row["line"] + 1)
        lines.append("%s = %s" % (head, row["value"]) if row["ok"] else "%s: refused (%s)" % (head, row["refused"]))
    return request["results_head"] + "\n" + "\n".join(lines) + "\n\n"


def audit_rows(calls):
    """One judge_tools.jsonl row per line of the reply: the tool, its argument ids, ok or the
    reason, the result's digest. No value and no text."""
    return [{"tool": row["tool"], "args": list(row["args"]), "ok": bool(row.get("ok")), "refused": row["refused"],
             "result_sha256": sha256(row["value"]) if row.get("ok") else None, "line": row["line"],
             "request_call": True} for row in calls]


def request_round(text, selection, claim, config, names, ask_request, calls, registry=None):
    """(the RESULTS block, the audit rows, the request's user text or None) of one question: ONE
    request at most, never a second. Nothing is asked when no shown tool applies to this table and
    claim (`requests_skipped`); a failed request leaves the question as it would be with no tool
    asked (`request_failed`). `ask_request(spec)` is the request's narrow call, given the grammar
    spec its decoding admits, and returns the reply's text or None."""
    import tool_registry
    request = config["request"]
    # The registry the request block declares (config/cell_selection.json `request.registry`).
    registry = tool_registry.load(tool_registry.ROOT / request["registry"]) if registry is None else registry
    table = cell_selection.tables(text)[selection.get("table") or 0]
    context = dict(context_of(table, claim), key_columns=cell_selection.key_columns(table))
    shown = tool_registry.relevant(registry, names, "cell_claim", facts_of(context, selection), int(request["max_shown"]))
    if not shown:
        calls["requests_skipped"] += 1
        return "", [], None
    ids = ids_of(context)
    prompt = render_request(request, selection["cells"], claim, context, shown)
    calls["requests"] += 1
    reply = ask_request(dict(grammar_spec(shown, ids, request["max_calls"]), max_new_tokens=int(request["max_new_tokens"])))(prompt)
    if reply is None:
        calls["request_failed"] += 1
        return "", [], prompt
    context.pop("key_columns", None)
    parsed = execute(parse(reply, shown, ids, int(request["max_calls"])), context,
                     lambda name: tool_registry.resolve(tool_registry.entry(registry, name)))
    calls["request_calls"] += len(parsed)
    return results_block(request, parsed), audit_rows(parsed), prompt


# ---------- the request's narrow call --------------------------------------------------------

def send(wrapper, stable, dynamic, spec):
    """The request's one model call, already masked: free text under the per-request grammar
    (contract_decoding.for_call reads `_tool_request`), the frozen decoding policy unchanged."""
    wrapper._tool_request = spec
    try:
        return wrapper.dispatch(stable, dynamic, max_new_tokens=int(spec["max_new_tokens"]))
    finally:
        wrapper._tool_request = None


def answer_of(result):
    return result.raw_text if getattr(result, "ok", False) else None


def outcome_of(result):
    return "free_text" if getattr(result, "ok", False) else "backend_failure"
