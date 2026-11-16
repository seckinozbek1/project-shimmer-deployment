"""Gate checks 420 to 424: the tool audit's first table tools (D-694 item 4, docs/loop/stages/TOOL_AUDIT.md,
scripts/table_tools_extra.py). No model, no provider, no key: fixture tables and contexts, the shipped
registry, the real parser, grammar and vetting.

Each proof is neutralise, fail, restore, pass (scripts/effect_proof.py):
  A (420) percent_change, sum_cells, mean_cells and rank_in_column are right on a fixture table,
      through the one batch executor and the registry's own entries;
  B (421) figure_step finds every single step of two cells of one row or one column that gives a
      figure at the figure's own rounding, says where a figure stands when a cell writes it, and
      says so when no step gives it;
  C (422) rounds_to rounds half up to the decimals the second figure writes, read by the review's
      one comma rule ("71,2" writes one decimal, "1,254" none);
  D (423) each new tool refuses a percent against a plain number, a zero divisor, a cell holding no
      single number and an id the table does not hold; the parser refuses a typed number and too
      many arguments for them, and the request grammar admits none of those;
  E (424) every new entry is vetted as declared in two fresh processes with no socket and no write,
      is approved by a decision on the registry's approving_decisions, is shown by structure only (a
      table with no numbers is shown none of them), and no shipped contract declares request_tools,
      so the request stays off until the lead switches it on.
"""
import contextlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import contract_decoding  # noqa: E402
import table_tools  # noqa: E402
import table_tools_extra  # noqa: E402
import tool_registry  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

EXTRA = ["figure_step", "rounds_to", "percent_change", "sum_cells", "mean_cells", "rank_in_column"]
TABLE = {"header": ["Name", "P", "Q", "S"],
         "rows": [["Alpha", "71.24", "40.5%", "12"], ["Beta", "68.0", "45.0%", "0"], ["Gamma", "71.2", "36.0%", "8"],
                  ["Delta", "50", "-", "4"]]}
CLAIM = "Alpha is 3.24 above Beta, Q rises 11.1% and P reaches 71.2, a ratio of 1.5, then 0.7 and 0.07 apart, Q 4.5 points up."
WORDS_TABLE = {"header": ["Name", "Kind"], "rows": [["Alpha", "first"], ["Beta", "second"]]}


@contextlib.contextmanager
def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


def with_source(module, name, old, new):
    import cell_selection_checks
    return cell_selection_checks.with_source(module, name, old, new)


def _context():
    return table_tools.context_of(TABLE, CLAIM)


def _run(calls):
    """Each (tool, ids) through table_tools.execute and the registry's own entries: its value or its refusal."""
    registry = tool_registry.load()
    rows = [{"line": i, "tool": name, "args": list(args), "refused": None} for i, (name, args) in enumerate(calls)]
    table_tools.execute(rows, _context(), lambda name: tool_registry.resolve(tool_registry.entry(registry, name)))
    return [row["value"] if row["ok"] else row["refused"] for row in rows]


# ---------- A: arithmetic on a fixture ---------------------------------------------------------

def observe_arithmetic():
    return _run([("percent_change", ["r2c3", "r1c3"]), ("percent_change", ["r1c2", "r2c2"]),
                 ("sum_cells", ["r1c4", "r2c4", "r3c4", "r4c4"]), ("sum_cells", ["r1c2", "r2c2"]),
                 ("mean_cells", ["r1c4", "r2c4", "r3c4", "r4c4"]), ("mean_cells", ["r1c3", "r2c3", "r3c3"]),
                 ("rank_in_column", ["r3c2"]), ("rank_in_column", ["r4c4"]), ("rank_in_column", ["r2c4"])])


def expected_arithmetic():
    # Worked by hand: (45 - 40.5) / 40.5 * 100 = 11.111111; (71.24 - 68) / 68 * 100 = 4.764706;
    # 12 + 0 + 8 + 4 = 24, mean 6; (40.5 + 45 + 36) / 3 = 40.5; P is 71.24, 71.2, 68, 50.
    return ["11.111111", "4.764706", "24", "139.24", "6", "40.5",
            "2 of 4 from the highest; 3 of 4 from the lowest; ties none",
            "3 of 4 from the highest; 2 of 4 from the lowest; ties none",
            "4 of 4 from the highest; 1 of 4 from the lowest; ties none"]


def proofs_a():
    return [
        ("a percent change is of the second figure", observe_arithmetic, expected_arithmetic,
         lambda: with_source(table_tools_extra, "percent_change", "(x - y) / y * 100", "(x - y) / x * 100")),
        ("a sum adds every cell", observe_arithmetic, expected_arithmetic,
         lambda: with_source(table_tools_extra, "sum_cells", "sum(_numbers(context, refs))", "sum(_numbers(context, refs)[1:])")),
        ("a mean divides by the count", observe_arithmetic, expected_arithmetic,
         lambda: with_source(table_tools_extra, "mean_cells", "sum(values) / len(values)", "sum(values) / (len(values) + 1)")),
        ("a rank counts from the highest", observe_arithmetic, expected_arithmetic,
         lambda: with_source(table_tools_extra, "rank_in_column", "1 + sum(1 for v, _ in found if v > value)",
                             "1 + sum(1 for v, _ in found if v < value)")),
        ("a tool runs the registry's entry", observe_arithmetic, expected_arithmetic,
         lambda: patched(tool_registry, "resolve", lambda entry: table_tools_extra.sum_cells)),
    ]


# ---------- B: where a figure comes from -------------------------------------------------------

def observe_steps():
    context = _context()
    return {ref: table_tools_extra.figure_step(context, ref) for ref in context["figures"]}


def expected_steps():
    # f1 3.24 = 71.24 - 68.0 (one column); f2 11.1% = the change from 40.5% to 45.0% (one column);
    # f3 71.2 stands in a cell; f4 1.5 = 12 / 8 (column S) and = 12 / 8 only, rows hold no such pair;
    # f5 0.7 is four ratios at one decimal (50 / 71.24, 50 / 68, 50 / 71.2 in P; 8 / 12 in S), every one listed;
    # f6 0.07 is no single step at two decimals; f7 4.5, a plain figure, is points between two percents of Q.
    return {"f1": "in no cell; difference(r1c2, r2c2) = 3.24",
            "f2": "in no cell; percent_change(r2c3, r1c3) = 11.111111; percent_change(r3c3, r1c3) = -11.111111",
            "f3": "stands in r3c2",
            "f4": "in no cell; ratio(r1c4, r3c4) = 1.5",
            "f5": "in no cell; ratio(r4c2, r1c2) = 0.701853; ratio(r4c2, r2c2) = 0.735294; ratio(r4c2, r3c2) = 0.702247; "
                  "ratio(r3c4, r1c4) = 0.666667",
            "f6": "in no cell; no single step of two cells of one row or one column gives it",
            "f7": "in no cell; difference(r1c3, r2c3) = -4.5; difference(r1c3, r3c3) = 4.5"}


def proofs_b():
    return [
        ("a step is read at the figure's own rounding", observe_steps, expected_steps,
         lambda: with_source(table_tools_extra, "figure_step", "not _same(value, target, places)",
                             "abs(value) != target")),
        ("columns are read, not rows only", observe_steps, expected_steps,
         lambda: with_source(table_tools_extra, "_lines", "    return out\n", "    return out[:len(rows)]\n")),
        ("a figure a cell writes is said to stand there", observe_steps, expected_steps,
         lambda: with_source(table_tools_extra, "figure_step", 'if at != "in no cell":', "if False:")),
        ("a percent figure is matched by percent steps only", observe_steps, expected_steps,
         lambda: with_source(table_tools_extra, "_steps", "if figure_percent:", "if True:")),
        ("two percents give points for a plain figure", observe_steps, expected_steps,
         lambda: with_source(table_tools_extra, "_steps", "out = [(DIFFERENCE, x - y)]", "out = [] if px else [(DIFFERENCE, x - y)]")),
    ]


# ---------- C: rounding as the figure writes it ------------------------------------------------

ROUNDING = {"cells": {"r1c1": "71.25", "r2c1": "71,2", "r3c1": "1,254", "r4c1": "1254.4", "r5c1": "0.349", "r6c1": "0.35"},
            "columns": {"c1": "X"}, "rows": 6, "figures": {"f1": "71.3", "f2": "0.3"}}


def observe_rounding():
    calls = [("r1c1", "f1"), ("r1c1", "r2c1"), ("r4c1", "r3c1"), ("r5c1", "r6c1"), ("r5c1", "f2")]
    return {"rounds": [table_tools_extra.rounds_to(ROUNDING, a, b) for a, b in calls],
            "decimals": [table_tools_extra.decimals(ROUNDING["cells"][r]) for r in ("r1c1", "r2c1", "r3c1", "r6c1")]}


def expected_rounding():
    return {"rounds": ["equal at 1 decimal place", "not equal at 1 decimal place: a rounds to 71.3",
                       "equal at 0 decimal places", "equal at 2 decimal places",
                       "equal at 1 decimal place"],
            "decimals": [2, 1, 0, 2]}


def proofs_c():
    return [
        ("half up, not half even", observe_rounding, expected_rounding,
         lambda: patched(table_tools_extra, "ROUND_HALF_UP", "ROUND_HALF_EVEN")),
        ("groups of three are thousands", observe_rounding, expected_rounding,
         lambda: with_source(table_tools_extra, "decimals", "if _THOUSANDS.fullmatch(token):", "if False:")),
        ("a single comma is a decimal comma", observe_rounding, expected_rounding,
         lambda: with_source(table_tools_extra, "decimals", 'if token.count(",") == 1:', "if False:")),
    ]


# ---------- D: refusals, the parser and the grammar --------------------------------------------

def _shown():
    registry = tool_registry.load()
    return [tool_registry.entry(registry, name) for name in EXTRA]


def observe_refusals():
    context = _context()
    refused = _run([("percent_change", ["r1c2", "r1c3"]), ("percent_change", ["r1c4", "r2c4"]),
                    ("sum_cells", ["r1c2", "r1c3"]), ("mean_cells", ["r1c1", "r2c2"]), ("rank_in_column", ["r4c3"]),
                    ("rounds_to", ["r1c3", "f3"]), ("figure_step", ["f9"])])
    shown, ids = _shown(), table_tools.ids_of(context)
    reply = "\n".join(("sum_cells(r1c2, 12)", "sum_cells(r1c2, r1c2, r1c2, r1c2, r1c2, r1c2, r1c2)",
                       "rank_in_column(c2)", "mean_cells(r1c2, r2c2)"))
    parsed = [row["refused"] for row in table_tools.parse(reply, shown, ids, 4)]
    spec = table_tools.grammar_spec(shown, ids, 4)
    grammar = [contract_decoding.request_accepts(spec, text) for text in
               ("sum_cells(r1c2, 12)", "sum_cells(r1c2, r1c2, r1c2, r1c2, r1c2, r1c2, r1c2)", "rank_in_column(c2)",
                "mean_cells(r1c2, r2c2)", "figure_step(f1)\nrounds_to(r1c2, f3)")]
    return {"refused": refused, "parsed": parsed, "grammar": grammar}


def expected_refusals():
    return {"refused": ["percent_against_plain", "zero_divisor", "percent_against_plain", "not_one_number",
                        "not_one_number", "percent_against_plain", "id_not_valid"],
            "parsed": ["literal_number", "wrong_arguments", "id_not_valid", None],
            "grammar": [False, False, False, True, True]}


def _uncapped(original):
    """slots_of with a repeating last slot's cap lifted, as a neutralisation."""
    return lambda entry: [(kind, least, 99 if most > 1 else most) for kind, least, most in original(entry)]


def proofs_d():
    return [
        ("a percent is not added to a plain number", observe_refusals, expected_refusals,
         lambda: with_source(table_tools_extra, "_numbers", "if len({percent for _, percent in found}) > 1:", "if False:")),
        ("a zero divisor is refused", observe_refusals, expected_refusals,
         lambda: with_source(table_tools_extra, "percent_change", "if y == 0:", "if False:")),
        ("a typed number is refused by the parser", observe_refusals, expected_refusals,
         lambda: patched(table_tools, "_LITERAL", __import__("re").compile(r"(?!)"))),
        ("the grammar holds the repeat cap", observe_refusals, expected_refusals,
         lambda: patched(table_tools, "slots_of", _uncapped(table_tools.slots_of))),
    ]


# ---------- E: vetted, approved, shown by structure, off as shipped ----------------------------

def _facts(table, claim):
    """The structural facts of a selection that shows the whole table."""
    context = table_tools.context_of(table, claim)
    selection = {"rows": list(range(len(table["rows"]))), "columns": list(range(len(table["header"])))}
    return table_tools.facts_of(context, selection)


def _declared_request_tools():
    contracts = json.loads((ROOT / "config" / "agent_contracts.json").read_text(encoding="utf-8"))["contracts"]
    out = []
    for name, contract in contracts.items():
        for task, spec in ((contract.get("judge") or {}).get("tasks") or {}).items():
            if isinstance(spec, dict) and spec.get("request_tools"):
                out.append("%s:%s" % (name, task))
    return out


def observe_shipped():
    import vet_table_tool
    registry = tool_registry.load()
    entries = [tool_registry.entry(registry, name) for name in EXTRA]
    return {"refusals": {e["name"]: tool_registry.entry_refusals(e, registry) for e in entries},
            "vetted": {e["name"]: list(vet_table_tool.vet(e, registry)) for e in entries},
            "approved_by": sorted({e["approved_by"] for e in entries}),
            "shown numbers": [e["name"] for e in tool_registry.relevant(registry, EXTRA, "cell_claim", _facts(TABLE, CLAIM), 6)],
            "shown words": [e["name"] for e in tool_registry.relevant(registry, EXTRA, "cell_claim",
                                                                       _facts(WORDS_TABLE, "Alpha is first."), 6)],
            "declared": _declared_request_tools()}


def expected_shipped():
    return {"refusals": {name: [] for name in EXTRA}, "vetted": {name: [True, []] for name in EXTRA},
            "approved_by": ["D-694"], "shown numbers": EXTRA, "shown words": [], "declared": []}


def _unapproved_load(original=tool_registry.load):
    def load(path=None):
        registry = original(path)
        registry["approving_decisions"] = [d for d in registry["approving_decisions"] if d != "D-694"]
        return registry
    return load


def proofs_e():
    return [
        ("an entry no listed decision approves is refused", observe_shipped, expected_shipped,
         lambda: patched(tool_registry, "load", _unapproved_load())),
        ("a changed tool is not vetted as declared", observe_shipped, expected_shipped,
         lambda: patched(tool_registry, "vetted_sha256", lambda entry_, root=None, search=None: "0" * 64)),
        ("a table with no numbers is shown none of them", observe_shipped, expected_shipped,
         lambda: patched(tool_registry, "applies", lambda entry_, facts: True)),
        ("no shipped contract declares request_tools", observe_shipped, expected_shipped,
         lambda: patched(sys.modules[__name__], "_declared_request_tools", lambda: ["JUDGE:cell_claim"])),
    ]


PROOFS = {"A": proofs_a, "B": proofs_b, "C": proofs_c, "D": proofs_d, "E": proofs_e}
SAYS = {"A": "percent change, sum, mean and rank are right on a fixture table, through the registry's own entries",
        "B": "figure_step finds the single steps of one row or one column at the figure's own rounding, and says where a written figure stands",
        "C": "rounds_to rounds half up to the decimals the second figure writes, by the review's one comma rule",
        "D": "each new tool refuses a percent against a plain number, a zero divisor, a cell with no single number and an unknown id; the parser and grammar refuse a typed number and too many arguments",
        "E": "every new entry is vetted as declared with no socket and no write, approved by a listed decision, shown by structure only, and no shipped contract declares request_tools"}


def run_check(letter):
    proofs = PROOFS[letter]()
    for name, observe, expected, neutralise in proofs:
        prove_effect(name=name, validate=lambda: tool_registry.REGISTRY_PATH.is_file(),
                     observe=observe, check=lambda observe=observe, expected=expected, name=name:
                     ("PASS" if observe() == expected() else "FAIL", name), neutralise=neutralise)
    return "PASS", "%d proofs, each neutralise, fail, restore, pass: %s" % (len(proofs), SAYS[letter])


if __name__ == "__main__":
    letters = sys.argv[1:] or sorted(PROOFS)
    for letter in letters:
        print(letter, json.dumps(run_check(letter)))
