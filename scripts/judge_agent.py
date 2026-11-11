"""The judge as a registered agent (D-S55 items 1, 2, 4 and 5; D-S56 item 1).

A role is a contract and a prompt; a model is a loaded backend. The judge is the agent whose
contract in `config/agent_contracts.json` declares a `judge` block: the narrow tasks it takes, the
answers it gives (decided from its own probabilities, D-S41) and the tools Python runs for it. No
agent name is written here: the agent that declares a task takes it, and with none declaring it the
task keeps the route it had (`pipeline._paired_judging_agent`), byte for byte.

    role_for(task, registry, contracts, deciding)    which agent takes a task, or None
    declared_tools(task, contracts)                  the tools a task runs, in the contract's order
    figures_block(cells, claim)                      the `locate_figures` result, as the model sees it
    tools_block(task, contracts, cells, claim)       the `{tools}` slot of the task's question
    tool_rows(...)                                   one record per tool call, numbers and ids only
    family_violations(registry, contracts)           a checking role on the backend or model it checks

The tools. A tool is Python's, run by Python, never chosen by the model: a forward pass writes no
text, so the model cannot call one. `find_cells` is the cell selection (its result is the CELLS
block), `locate_figures` reads each figure the claim writes against the cells shown and its result
enters the question as the FIGURES block, and `check_quote` is the judged paths' refusal
(`paired_review.judged_item_refusal`), run after the decision and never shown. A tool the contract
declares and this module does not know is refused, as is a task whose tool list names one twice.

Everything is structural: a figure is digits as `cell_selection` reads them, a row's label is its
key cells, a column's label its header. Which arithmetic a claim asks for is never read (WORDS-A).
"""
import hashlib
import json
from pathlib import Path

import cell_selection

CONTRACTS_PATH = Path(__file__).resolve().parents[1] / "config" / "agent_contracts.json"
TOOL_RECORDS = "judge_tools.jsonl"
CELL_CLAIM, PASSAGE_PAIR = "cell_claim", "passage_pair"
FIND_CELLS, LOCATE_FIGURES, CHECK_QUOTE = "find_cells", "locate_figures", "check_quote"
# Each tool's place: before the question (its result shown, or the evidence itself) or after it.
KNOWN_TOOLS = {FIND_CELLS: (CELL_CLAIM,), LOCATE_FIGURES: (CELL_CLAIM,), CHECK_QUOTE: (CELL_CLAIM, PASSAGE_PAIR)}
SHOWN_TOOLS = (LOCATE_FIGURES,)
FIGURES_HEAD = "FIGURES"
NOT_SHOWN = "in no cell shown"


class ContractRefused(ValueError):
    """A judge contract this module cannot run: its message names what."""


def _judge(contract):
    block = (contract or {}).get("judge")
    return block if isinstance(block, dict) else None


def judges(registry, contracts):
    """The registered agents whose contract declares any task, sorted: whose records phase 6 reads."""
    return sorted(name for name, contract in (contracts or {}).items()
                  if name in (registry or {}) and ((_judge(contract) or {}).get("tasks")))


def declaring(task, registry, contracts):
    """The registered agents whose contract declares `task`, sorted."""
    return sorted(name for name, contract in (contracts or {}).items()
                  if name in (registry or {}) and task in ((_judge(contract) or {}).get("tasks") or {}))


def role_for(task, registry, contracts, deciding=True):
    """The one registered agent whose contract declares `task`, or None (the task keeps its route).
    A judge answers from its probabilities, so a task asked in another form (a reply the model
    writes) is not its task and keeps its route too. Two agents declaring one task is refused:
    which one takes it would be a guess."""
    names = declaring(task, registry, contracts)
    if len(names) > 1:
        raise ContractRefused("more than one agent declares the task %s: %s" % (task, ", ".join(names)))
    if not names or not deciding:
        return None
    declared_tools(task, contracts)
    return names[0]


def declared_tools(task, contracts):
    """The tools `task` runs, as its declaring contract lists them; [] when no contract declares it."""
    for contract in (contracts or {}).values():
        block = _judge(contract)
        entry = ((block or {}).get("tasks") or {}).get(task)
        if entry is None:
            continue
        tools = list(entry.get("tools") or [])
        if len(set(tools)) != len(tools):
            raise ContractRefused("the task %s names a tool twice" % task)
        for tool in tools:
            if task not in KNOWN_TOOLS.get(tool, ()):
                raise ContractRefused("the task %s declares a tool Python does not run for it: %s" % (task, tool))
        return tools
    return []


def _written(claim):
    """The figures `claim` writes, each once, in its own order and spelling."""
    out, seen = [], set()
    for token in cell_selection._NUMBER.findall(str(claim or "")):
        try:
            value = float(token.replace(",", ""))
        except ValueError:
            continue
        if value not in seen:
            seen.add(value)
            out.append((token, value))
    return out


def locate_figures(cells, claim):
    """[(figure as the claim writes it, [(row index, column index)])] on the cells shown: `cells` is
    the CELLS block itself (caption and pipe table), so the result is read off what the model sees.
    [] when the claim writes no figure or the block holds no table."""
    found = cell_selection.tables(cells)
    if not found:
        return []
    table = found[0]
    out = []
    for token, value in _written(claim):
        at = [(r, c) for r, row in enumerate(table["rows"]) for c, cell in enumerate(row)
              if value in cell_selection.figures(cell)]
        out.append((token, at))
    return out


def _row_label(table, row):
    keys = cell_selection.key_columns(table)
    return " / ".join(table["rows"][row][k] for k in keys)


def figures_block(cells, claim):
    """The FIGURES block: one line per figure the claim writes, where it stands among the cells
    shown, or that it stands in none. "" when there is nothing to say."""
    located = locate_figures(cells, claim)
    if not located:
        return ""
    table = cell_selection.tables(cells)[0]
    lines = []
    for token, at in located:
        if not at:
            lines.append("%s: %s" % (token, NOT_SHOWN))
            continue
        lines.append("%s: %s" % (token, "; ".join('row "%s", column "%s"' % (_row_label(table, r), table["header"][c])
                                                 for r, c in at)))
    return FIGURES_HEAD + "\n" + "\n".join(lines) + "\n\n"


def tools_block(task, contracts, cells="", claim=""):
    """The `{tools}` slot of `task`'s question: the shown tools' results, in the contract's order;
    "" when the contract declares none, which leaves the question as it was measured, byte for byte."""
    out = []
    for tool in declared_tools(task, contracts):
        if tool == LOCATE_FIGURES:
            out.append(figures_block(cells, claim))
    return "".join(out)


def shipped_contracts(path=CONTRACTS_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8")).get("contracts", {})


def claim_tools(cells, claim, contracts=None):
    """The `{tools}` slot of a cell claim's question under `contracts` (the shipped ones by default):
    the one function the pipeline's question and the replay's both fill it with."""
    return tools_block(CELL_CLAIM, shipped_contracts() if contracts is None else contracts, cells, claim)


def sha256(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def find_cells_row(selection):
    """`find_cells`'s record: what Python selected, indexes and counts only."""
    return {"tool": FIND_CELLS, "selected": bool(selection.get("selected")), "refused": selection.get("refused"),
            "selected_by": selection.get("selected_by"), "rows": list(selection.get("rows") or []),
            "columns": list(selection.get("columns") or []), "of_rows": selection.get("of_rows"),
            "of_columns": selection.get("of_columns")}


def locate_figures_row(cells, claim):
    """`locate_figures`'s record: how many figures the claim writes and where each stands, as
    indexes into the cells shown. No figure and no text."""
    located = locate_figures(cells, claim)
    return {"tool": LOCATE_FIGURES, "figures": len(located), "located": sum(1 for _, at in located if at),
            "at": [[list(p) for p in at] for _, at in located]}


def check_quote_row(refusal):
    """`check_quote`'s record: kept, or the refusal's reason."""
    return {"tool": CHECK_QUOTE, "kept": not refusal, "reason": refusal or None}


def tool_rows(task, contracts, rule_id, unit_id, prompt, rows):
    """The declared tools' records of one question, each stamped with the task, the rule, the unit and
    the digest of the question it served (`prompt`, None for a selection no question followed). A
    row of a tool the task does not declare is dropped: only a declared tool is the judge's."""
    declared = declared_tools(task, contracts)
    return [dict(row, task=task, rule_id=rule_id, unit_id=unit_id,
                 prompt_sha256=sha256(prompt) if prompt is not None else None)
            for row in rows if row.get("tool") in declared]


def write_tool_rows(run_context, rows, call_of):
    """Append each record to `<run>/audit/judge_tools.jsonl`, its call id joined from `call_of`
    ({prompt digest: call id}). Nothing is written with no run context, as reply records are not."""
    if run_context is None or not rows:
        return 0
    path = Path(run_context.audit_dir()) / TOOL_RECORDS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(dict(row, call_id=call_of.get(row.get("prompt_sha256"))), sort_keys=True) + "\n")
    return len(rows)


def refusals(registry, contracts):
    """Every reason the roster cannot run as declared, [] when it can: a task two agents declare, a
    tool a task cannot run, a checking role on the model it checks. Boot refuses on any."""
    out = []
    tasks = sorted({t for c in (contracts or {}).values() for t in ((_judge(c) or {}).get("tasks") or {})})
    for task in tasks:
        try:
            role_for(task, registry, contracts)
        except ContractRefused as exc:
            out.append(str(exc))
    for checker, checked in family_violations(registry, contracts):
        out.append("%s checks %s on the same backend or model, or on a role the registry does not hold" % (checker, checked))
    return out


def _family(spec):
    return (spec or {}).get("backend"), (spec or {}).get("model")


def family_violations(registry, contracts):
    """[(checker, checked)] where a role whose contract declares `checks: [ROLE]` runs on ROLE's
    backend or ROLE's model (D-S55 item 5): such a check is the model agreeing with itself. A
    checked role the registry does not hold is a violation too, since its model cannot be read."""
    out = []
    for name in sorted(contracts or {}):
        if name not in (registry or {}):
            continue
        for checked in (contracts[name] or {}).get("checks") or []:
            if checked not in registry:
                out.append((name, checked))
                continue
            (b1, m1), (b2, m2) = _family(registry[name]), _family(registry[checked])
            if b1 == b2 or (m1 and m1 == m2):
                out.append((name, checked))
    return out
