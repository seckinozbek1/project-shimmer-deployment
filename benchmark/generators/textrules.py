"""Reading rules of the published input format, implemented here independently.

This module never imports Shimmer's own code. It implements, from the text of
docs/INPUT_FORMAT.md (input-format-v1-draft), the pieces the generators need to
audit what they write: the slug and unit id (section 2), label normalisation
(section 2), the figure reader and the measure algebra (section 2), and the
tolerance of section 6.

It reads a RESTRICTED subset of the format on purpose. Every value the
generators write is one of three shapes: text with no digit, a figure written
as `<number> <measure>` (or `<number>%`), or one ISO date. Anything else is
refused by `classify_value`, so a template change that drifts outside the
subset fails validation instead of being read differently by Shimmer.
"""
import re

FORMAT_VERSION = "input-format-v1-draft"

STOP_WORDS = frozenset((
    "a above all also an and another any are as at be been being below between both but "
    "by can could did do does down each for from had has have her his how if in into is "
    "it its least less may might more most must no not of on only onto or other our out "
    "over per same shall should such than that the their then these this those to under "
    "up was were what when where which who whom whose why will with without would your"
).split())

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def words(text):
    """Section 2 normalisation, as a list of words in order."""
    out = []
    for tok in _TOKEN.findall(str(text).lower()):
        if len(tok) <= 2 or tok in STOP_WORDS:
            continue
        if len(tok) > 4 and tok.endswith("ies"):
            tok = tok[:-3] + "y"
        elif len(tok) > 3 and tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
            tok = tok[:-1]
        out.append(tok)
    return out


def norm(text):
    """The normalised label: the words joined by single spaces."""
    return " ".join(words(text))


def slug(heading_text):
    """Section 2 slug: lowercase, runs of non [a-z0-9] to one '-', trim, first 40."""
    s = re.sub(r"[^a-z0-9]+", "-", str(heading_text).lower()).strip("-")
    s = s[:40]
    return s or "unit"


def unit_id(position, heading_text):
    return "u%02d-%s" % (position, slug(heading_text))


# The figure reader. Grouped form first (comma groups of three), then plain form.
NUMBER = r"-?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_FIGURE_VALUE = re.compile(r"^(" + NUMBER + r")( ?)([A-Za-z%][A-Za-z/%]*)$")
_DATE_VALUE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_PLAIN_CELL = re.compile(r"^(" + NUMBER + r")$")
_RANGE_CELL = re.compile(r"^(" + NUMBER + r") to (" + NUMBER + r")$")


def to_number(text):
    return float(text.replace(",", ""))


def classify_value(value):
    """('text', None, None) | ('figure', number, measure) | ('date', (y, m, d), '') | ('bad', why)."""
    v = value.strip()
    if not v:
        return ("bad", "empty value")
    m = _DATE_VALUE.match(v)
    if m:
        return ("date", (int(m.group(1)), int(m.group(2)), int(m.group(3))), "")
    m = _FIGURE_VALUE.match(v)
    if m:
        measure = m.group(3)
        if m.group(2) == "" and measure != "%" and not measure.startswith("%"):
            return ("bad", "a measure joined to its number other than %: %r" % v)
        return ("figure", to_number(m.group(1)), measure)
    if re.search(r"\d", v):
        return ("bad", "a digit in a value that is not a figure or a date: %r" % v)
    if re.search(r"[|:\[\]]", v):
        return ("bad", "a reserved character in a text value: %r" % v)
    return ("text", None, None)


def classify_cell(cell):
    c = cell.strip()
    if not c:
        return ("blank", None)
    m = _PLAIN_CELL.match(c)
    if m:
        return ("number", to_number(m.group(1)))
    m = _RANGE_CELL.match(c)
    if m:
        return ("range", (to_number(m.group(1)), to_number(m.group(2))))
    if re.search(r"\d", c):
        # a document cell's own measure would replace the header's (section 2), and a
        # reference cell's would be ignored (section 7): cells here are plain numbers
        return ("bad", "a table cell that is not a plain number, a plain range or text: %r" % c)
    return ("text", c)


def measure_powers(measure):
    """Section 2: split at '/', keep letters and '%' per part; later parts divide."""
    powers = {}
    if not measure:
        return ()
    for i, part in enumerate(measure.split("/")):
        clean = re.sub(r"[^A-Za-z%]", "", part)
        if not clean:
            continue
        powers[clean] = powers.get(clean, 0) + (1 if i == 0 else -1)
    return tuple(sorted((k, p) for k, p in powers.items() if p))


def mul(a, b, sign=1):
    d = dict(a)
    for k, p in b:
        d[k] = d.get(k, 0) + sign * p
    return tuple(sorted((k, p) for k, p in d.items() if p))


def div(a, b):
    return mul(a, b, -1)


def same(a, b):
    """Section 6 tolerance: within 1e-9, or within one millionth of the larger."""
    a, b = float(a), float(b)
    return abs(a - b) <= 1e-9 or abs(a - b) <= 1e-6 * max(abs(a), abs(b))


def r6(x):
    """Round to 6 places; an integral value comes back as int (stable JSON)."""
    v = round(float(x), 6)
    if v == int(v):
        return int(v)
    return v


def numbers_with_measures(text):
    """Every number in a free text with the measure token right after it (rule texts,
    grounding sentences). Returns [(number, measure or '')]."""
    out = []
    for m in re.finditer(r"(?<![\w.])(" + NUMBER + r")(?![\d])", text):
        rest = text[m.end():]
        mm = re.match(r"\s*([A-Za-z%][A-Za-z0-9/%^-]*)", rest)
        measure = ""
        if mm:
            tok = mm.group(1).rstrip("-")
            measure = tok
        out.append((to_number(m.group(1)), measure))
    return out


def is_ascii_clean(text):
    """ASCII only, no em or en dash, no curly quotes, no tab, no CR, no BOM."""
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return False
    return "\t" not in text and "\r" not in text


def format_number(x, decimals=0, grouped=False):
    """Plain digits with a point for decimals, or comma groups of three."""
    if decimals:
        s = "%.*f" % (decimals, x)
    else:
        s = "%d" % int(round(x))
    if grouped:
        neg = s.startswith("-")
        body = s[1:] if neg else s
        whole, _, frac = body.partition(".")
        groups = []
        while len(whole) > 3:
            groups.insert(0, whole[-3:])
            whole = whole[:-3]
        groups.insert(0, whole)
        s = ("-" if neg else "") + ",".join(groups) + (("." + frac) if frac else "")
    return s


# ---- plain string reading of a rendered file (no audit), for the reference readings ----

def _table_cells(line):
    """The cells of a table line, or None for the separator line under a header."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if all(c and set(c) <= set("-: ") for c in cells):
        return None
    return cells


def plain_table(text):
    """(header labels with any measure in parentheses dropped, rows of cells) of the first
    table in a text, read line by line."""
    header, rows = None, []
    for ln in text.split("\n"):
        if not ln.startswith("|"):
            if header is not None:
                break
            continue
        cells = _table_cells(ln)
        if cells is None:
            continue
        if header is None:
            header = [c.split(" (", 1)[0] for c in cells]
        else:
            rows.append(cells)
    return header or [], rows


def plain_units(text):
    """Every `## ` unit of a rendered document, read with plain string handling: its unit
    id (section 2), heading, `Label: value` lines and its table (header labels, rows)."""
    out = []
    for pos, block in enumerate(text.split("\n## ")[1:], start=1):
        heading, _, body = block.partition("\n")
        lines = {}
        for ln in body.split("\n"):
            label, sep, value = ln.partition(": ")
            if sep and label and not ln.startswith("|"):
                lines[label] = value.strip()
        header, rows = plain_table(body)
        out.append({"id": unit_id(pos, heading), "heading": heading, "lines": lines,
                    "header": header, "rows": rows})
    return out


def leading_figure(value):
    """The number a value starts with (comma groups allowed), or None."""
    m = re.match(NUMBER, (value or "").strip())
    return to_number(m.group(0)) if m else None


def reference_sentences(text):
    """The prose sentences of a rendered reference file: every paragraph that is not a
    heading or a table, its runs of spaces joined, split after each full stop that a
    space follows."""
    out = []
    for para in text.split("\n\n"):
        p = " ".join(para.split())
        if not p or p.startswith("#") or p.startswith("|"):
            continue
        out.extend(s for s in re.split(r"(?<=\.) ", p) if s)
    return out
