"""More table tools for the one request round (D-694 item 4; the audit is docs/loop/stages/TOOL_AUDIT.md).

The six tools of D-681 and D-689 stand in `table_tools`. These are the audit's first additions, the
arithmetic a cell claim's judge is otherwise left to do in its head:

    figure_step(figure)          a claim figure in no cell: every single step of two one-number cells
                                 of one row or one column that gives it, within the figure's own rounding
    rounds_to(a, b)              whether a, rounded to the decimals b writes, is b
    percent_change(a, b)         the change from b to a as a percent of b
    sum_cells(cell, cell, ...)   the sum of these cells
    mean_cells(cell, cell, ...)  the mean of these cells
    rank_in_column(cell)         where a cell's figure stands in its column, from the highest and the lowest

Each is a pure function of the context `table_tools.context_of` builds and of ids only, so the
model cannot type a number (`literal_number` is refused by the parser before a tool runs). Each
refuses with a reason of the closed set (`table_tools.ToolRefused`), never guesses. Nothing here
reads what a claim's words mean (WORDS-A): `figure_step` lists arithmetic facts, every one it finds,
and never says which one the claim means. The product rule (D-694 item 3 a): no tool reaches the
internet; these compute only on the context they are handed. Declared in config/table_tools.json
and vetted by tools/vet_table_tool.py, as the six are.
"""
import re
from decimal import Decimal, ROUND_HALF_UP

import cell_selection
import table_tools
from table_tools import ToolRefused, fmt, number, value_of

STEP_LIMIT = 4
DIFFERENCE, RATIO, PERCENT_OF, PERCENT_CHANGE = "difference", "ratio", "percent_of", "percent_change"
_CELL_ID = re.compile(r"r([1-9][0-9]*)c([1-9][0-9]*)")
_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")


# ---------- reading a figure's own rounding -----------------------------------------------------

def decimals(text):
    """How many decimals the one figure of `text` writes, read by the review's one comma rule
    (paired_review.norm_number): "71,2" writes one, "1,254" none, "0.50" two."""
    number(text)   # refuses a text holding no figure or more than one
    token = [m.group(0) for m in cell_selection._NUMBER.finditer(str(text))
             if cell_selection.figure_value(m.group(0)) is not None][0]
    if _THOUSANDS.fullmatch(token):
        return len(token.split(".", 1)[1]) if "." in token else 0
    if "." in token:
        return len(token.rsplit(".", 1)[1])
    if token.count(",") == 1:
        return len(token.split(",", 1)[1])
    return 0


def rounded(value, places):
    """`value` rounded half up to `places` decimals, exactly (Decimal), as a Decimal."""
    return Decimal(repr(float(value))).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _same(value, target, places):
    """True when `value`, rounded to `places`, is `target` as written (both magnitudes)."""
    return rounded(abs(value), places) == rounded(abs(target), places)


# ---------- the tools ---------------------------------------------------------------------------

def rounds_to(context, a, b):
    """Whether a, rounded half up to the decimals b writes, is b."""
    x, y = table_tools._pair(context, a, b)
    places = decimals(value_of(context, b))
    unit = "decimal place" if places == 1 else "decimal places"
    if _same(x, y, places):
        return "equal at %d %s" % (places, unit)
    return "not equal at %d %s: a rounds to %s" % (places, unit, rounded(x, places))


def percent_change(context, a, b):
    """The change from b to a as a percent of b: (a - b) / b * 100."""
    x, y = table_tools._pair(context, a, b)
    if y == 0:
        raise ToolRefused(table_tools.ZERO_DIVISOR)
    return fmt((x - y) / y * 100)


def _numbers(context, refs):
    found = [number(value_of(context, ref)) for ref in refs]
    if len({percent for _, percent in found}) > 1:
        raise ToolRefused(table_tools.PERCENT_AGAINST_PLAIN)
    return [value for value, _ in found]


def sum_cells(context, *refs):
    """The sum of these cells."""
    return fmt(sum(_numbers(context, refs)))


def mean_cells(context, *refs):
    """The mean of these cells."""
    values = _numbers(context, refs)
    return fmt(sum(values) / len(values))


def _column_numbers(context, column):
    """[(value, ref)] of the one-number cells of column `column` (its number), over every row."""
    out = []
    for r in range(1, context["rows"] + 1):
        ref = "r%dc%d" % (r, column)
        try:
            out.append((number(context["cells"].get(ref, ""))[0], ref))
        except ToolRefused:
            continue
    return out


def rank_in_column(context, cell):
    """Where the cell's figure stands among the one-number cells of its column, counted from the
    highest and from the lowest, with the cells it ties."""
    match = _CELL_ID.fullmatch(cell)
    if not match or cell not in context["cells"]:
        raise ToolRefused(table_tools.ID_NOT_VALID)
    value = number(context["cells"][cell])[0]
    found = _column_numbers(context, int(match.group(2)))
    high = 1 + sum(1 for v, _ in found if v > value)
    low = 1 + sum(1 for v, _ in found if v < value)
    ties = [ref for v, ref in found if v == value and ref != cell]
    return "%d of %d from the highest; %d of %d from the lowest; ties %s" % (
        high, len(found), low, len(found), ", ".join(ties) if ties else "none")


def _lines(context):
    """Each row's and each column's one-number cells: [[(value, percent, ref)]]."""
    cells = {}
    for ref, text in context["cells"].items():
        match = _CELL_ID.fullmatch(ref)
        try:
            value, percent = number(text)
        except ToolRefused:
            continue
        cells[(int(match.group(1)), int(match.group(2)))] = (value, percent, ref)
    rows = sorted({r for r, _ in cells})
    columns = sorted({c for _, c in cells})
    out = [[cells[k] for k in sorted(cells) if k[0] == r] for r in rows]
    out += [[cells[k] for k in sorted(cells, key=lambda k: (k[1], k[0])) if k[1] == c] for c in columns]
    return out


def _steps(x, px, y, py, figure_percent):
    """[(operation, value)] of one ordered pair of cells of one kind (both plain or both percent): their
    difference whatever the figure writes (a plain figure may be points between two percents, and a
    percent figure may be written for them), and, divided, a ratio for a plain figure or the percent
    of and the percent change for a percent figure."""
    if px != py:
        return []
    out = [(DIFFERENCE, x - y)]
    if y != 0:
        if figure_percent:
            out += [(PERCENT_OF, x / y * 100), (PERCENT_CHANGE, (x - y) / y * 100)]
        else:
            out.append((RATIO, x / y))
    return out


def figure_step(context, figure):
    """Where a claim figure comes from: the cells that write it, or, when none does, every single
    step (difference, ratio, percent of, percent change) of two one-number cells of one row or one
    column whose result, rounded to the decimals the figure writes, is the figure (as a magnitude,
    as the review reads figures). At most STEP_LIMIT steps, in table order; which step the claim
    means is never decided here."""
    text = value_of(context, figure)
    target, percent = number(text)
    places = decimals(text)
    at = table_tools.find_figure(context, figure)
    if at != "in no cell":
        return "stands in %s" % at
    found, seen = [], set()
    for line in _lines(context):
        for i, (x, px, a) in enumerate(line):
            for j, (y, py, b) in enumerate(line):
                if i == j:
                    continue
                for operation, value in _steps(x, px, y, py, percent):
                    key = (operation, a, b) if operation != DIFFERENCE else (operation,) + tuple(sorted((a, b)))
                    if key in seen or not _same(value, target, places):
                        continue
                    seen.add(key)
                    found.append("%s(%s, %s) = %s" % (operation, a, b, fmt(value)))
    if not found:
        return "in no cell; no single step of two cells of one row or one column gives it"
    more = len(found) - STEP_LIMIT
    return "in no cell; " + "; ".join(found[:STEP_LIMIT]) + ("; and %d more" % more if more > 0 else "")
