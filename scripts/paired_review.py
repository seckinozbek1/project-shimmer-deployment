"""Paired review: one narrow call per (unit, rule) pair, with the arithmetic in Python.

H1 settled the question this module exists to answer. With no review framing at
all, only figures and a question, the local producer scored 5 of 30 on plain
arithmetic and the local auditor 9 of 30, against 27 of 30 for the cloud model on
identical cases. No amount of prompting fixes a 17 percent adder. So the model is
never asked to add anything here. Python computes; the model is shown the computed
values and asked only whether the discrepancy is material and how to state it.

The computation is mechanical and domain-free (S5). Three things make that possible
without any domain vocabulary in this file:

  * A UNIT ALGEBRA over the unit strings the operator's own document uses. "TRY/t"
    is {TRY: 1, t: -1}; multiplying it by "t" gives "TRY". So a stated value in TRY
    can be checked against a quantity in t times a price in TRY/t, and the check is
    proposed by dimensional consistency, not by knowing what wheat costs.
  * LABEL CONTAINMENT for sums. A scalar whose label words are a superset of a
    column's label words is that column's stated total, so the column is summed and
    compared. Nothing here knows the word for "total" in any language; it knows that
    "total declared area" contains "area".
  * BOUNDS READ FROM THE RULE'S OWN TEXT, when the rule states them. A rule that
    states no numbers yields no band comparison, and the pair still gets its call.

Deliberate limit, recorded rather than hidden: a band that lives in the reference
corpus rather than in the rule text is not extracted here. Those pairs are computed
as far as the figures allow (the ratio is computed and shown) and the model judges
against the retrieved passages, which is the same job it had before, on one pair
instead of a whole document.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import finding_record
import pairing_map

_ROOT = Path(__file__).resolve().parent.parent
_RENAME_TOLERANCE_CACHE: float | None = None
# Fallback used only when the config file is missing or malformed, so a corrupted
# or deleted config/rename_tolerance.json degrades to a documented default rather
# than to a crash or to silent fabrication resuming unnoticed.
_RENAME_TOLERANCE_FALLBACK = 0.02


def rename_tolerance() -> float:
    """The relative tolerance for rename corroboration, read from
    config/rename_tolerance.json (operator-editable, R7).

    Deliberately NOT paired_review.REL_TOLERANCE: that constant tests whether two
    figures are the same number to within floating-point noise (1e-6), and this
    question is different in kind: whether a new label's value is close enough to
    a vanished label's value to be plausibly the same fact. See
    docs/fix/STEP_G1_REPORT.md for why the two must not share a constant.
    """
    global _RENAME_TOLERANCE_CACHE
    if _RENAME_TOLERANCE_CACHE is not None:
        return _RENAME_TOLERANCE_CACHE
    value = _RENAME_TOLERANCE_FALLBACK
    try:
        cfg = json.loads(
            (_ROOT / "config" / "rename_tolerance.json").read_text(encoding="utf-8"))
        candidate = cfg.get("rename_rel_tolerance")
        if isinstance(candidate, (int, float)) and candidate >= 0:
            value = float(candidate)
    except Exception:
        value = _RENAME_TOLERANCE_FALLBACK
    _RENAME_TOLERANCE_CACHE = value
    return value

# R6: every currency symbol Unicode defines (general category Sc), as one character
# class. Computed, not listed: which characters are currency symbols is whatever the
# Unicode database says, so no currency is named here.
_CURRENCY_SYMBOLS = "".join(
    chr(i) for i in range(0x20, 0x10000) if unicodedata.category(chr(i)) == "Sc")
_SYM = "[" + re.escape(_CURRENCY_SYMBOLS) + "]"
# A letter in any script: \w minus digits and the underscore.
_LETTER = r"[^\W\d_]"

# A number with optional grouped thousands and an optional decimal tail. It may be
# PRECEDED by a currency symbol attached to it or by a short all-caps code and a
# space, and it may be FOLLOWED by a unit token. The unit is whatever token the
# document uses; nothing is recognised from a list. A prefix outranks a following
# word: in "<symbol>105 per year" the figure is in that currency and "per" is prose,
# which is exactly what a currency prefix is for. Measured before this: such a
# figure read as 105 with unit "per", and "<symbol>7,000" read with no unit at all.
_QUANTITY = re.compile(
    r"(?:(?P<code>(?<![^\W\d_])[A-Z]{2,4})[   ]+|(?P<sym>" + _SYM + r")[   ]?)?"
    r"(?P<num>-?\d{1,3}(?:[   ,]\d{3})+(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?)"
    r"[   ]*(?P<unit>(?:" + _LETTER + r"|%)(?:[^\W_]|[/%·^-])*"
    r"(?:\s*/\s*" + _LETTER + r"[^\W_%]*)?)?"
)
# How many words a unit written in prose may run to. A phrase is a unit only when
# the document writes it after a figure at least twice (unit_phrases).
UNIT_PHRASE_MAX_WORDS = 3
_UNIT_WORD = re.compile(r"[   ]+(" + _LETTER + r"+)")
_LABEL_LINE = pairing_map._LABEL_LINE
_TABLE_SEP = pairing_map._TABLE_SEP

# Relative tolerance for "these two figures are the same number". Anything inside it
# is rounding, not a discrepancy.
REL_TOLERANCE = 1e-6
ABS_TOLERANCE = 1e-9


def norm_number(token):
    """'1 254 000' and '1,254,000' and '1254000' are the same number."""
    t = str(token).strip().replace(" ", " ").replace(" ", " ")
    if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?", t):
        t = t.replace(",", "")
    t = t.replace(" ", "")
    if t.count(",") == 1 and t.count(".") == 0:
        t = t.replace(",", ".")
    else:
        t = t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _unit_token(part):
    """The characters of a unit token that carry meaning: letters in any script,
    the percent sign and currency symbols. Digits and punctuation are dropped
    (m2 -> m). It was `[^A-Za-z%]`, which cut an accented unit at the accent and
    dropped a currency symbol entirely, so a currency amount had no unit at all."""
    return "".join(ch for ch in str(part)
                   if ch.isalpha() or ch == "%" or unicodedata.category(ch) == "Sc")


def unit_exponents(unit_str):
    """A unit string as a map of token to exponent. 'kes/qm' -> {'kes': 1, 'qm': -1}.

    Purely syntactic: the tokens are whatever the operator's document writes.
    """
    if not unit_str:
        return {}
    text = str(unit_str).strip().rstrip(".,;")
    exponents = defaultdict(int)
    for sign, part in _split_unit(text):
        token = _unit_token(part)
        if token:
            exponents[token] += sign
    return {k: v for k, v in exponents.items() if v}


def _split_unit(text):
    out, sign = [], 1
    for part in re.split(r"([/·*])", text):
        if part == "/":
            sign = -1
            continue
        if part in ("·", "*"):
            sign = 1
            continue
        if part.strip():
            out.append((sign, part.strip()))
            sign = 1
    return out


def _same_unit(a, b):
    return unit_exponents(a) == unit_exponents(b)


def _multiply(a, b):
    out = defaultdict(int)
    for k, v in unit_exponents(a).items():
        out[k] += v
    for k, v in unit_exponents(b).items():
        out[k] += v
    return {k: v for k, v in out.items() if v}


def _divide(a, b):
    out = defaultdict(int)
    for k, v in unit_exponents(a).items():
        out[k] += v
    for k, v in unit_exponents(b).items():
        out[k] -= v
    return {k: v for k, v in out.items() if v}


def _unit_str(exponents):
    """Render an exponent map as a unit string, EXPONENTS INCLUDED.

    The first version dropped the magnitude, so {kes: 1, qm: -2} rendered as
    "kes/qm", the same string as {kes: 1, qm: -1}. Two different units then
    compared equal, and a price per unit divided by a quantity was accepted as a
    price per unit and checked against a price band: a false finding built out of
    a rendering bug. Found by R1's first band run on the operator's document, not by
    reading. Rendering the exponent makes the function injective on exponent maps,
    which is the property every comparison here relies on."""
    if not exponents:
        return ""

    def _render(token, power):
        return token if power == 1 else "%s^%d" % (token, power)

    num = [_render(k, v) for k, v in sorted(exponents.items()) if v > 0]
    den = [_render(k, -v) for k, v in sorted(exponents.items()) if v < 0]
    head = "*".join(num) or "1"
    return head + ("/" + "*".join(den) if den else "")


# ---------------------------------------------------------------------------
# reading the figures out of a unit


def extract_fields(unit_text, known_units=None):
    """Named numeric fields from a unit: scalars from `label: value` lines, and
    columns from any table with a separator row.

    Deterministic. The chain allows a small local call with a strict JSON schema
    where the unit is not a table, but on material that labels its own fields a
    parser is exact and free, and an exact free answer beats a sampled one from a
    model that cannot add.

    `known_units` (R6) is the document's own unit vocabulary, so a multi-word unit
    the document writes more than once is read whole. None means "this unit's own
    text", which is self-contained and byte-identical for every existing caller.

    Returns (scalars, columns) where scalars maps a label tuple to (value, unit)
    and columns maps a label tuple to a list of (value, unit).
    """
    if known_units is None:
        known_units = unit_phrases(unit_text)
    scalars, columns, row_counts = {}, defaultdict(list), defaultdict(int)
    for line in (unit_text or "").splitlines():
        m = _LABEL_LINE.match(line)
        if not m:
            continue
        label = pairing_map._norm_label(m.group(1))
        if not label:
            continue
        q = first_quantity(m.group(2), known_units)
        if q is not None:
            scalars[label] = q

    for block in pairing_map._table_blocks(unit_text or ""):
        if len(block) < 3 or not _TABLE_SEP.match(block[1]):
            continue
        raw_headers = [c.strip() for c in block[0].strip().strip("|").split("|")]
        # header_label strips the unit parenthetical BEFORE normalising, so a
        # three-letter unit does not leak into the label and break every containment
        # test downstream (pairing_map.header_label explains the failure it fixes).
        headers = [pairing_map.header_label(c) for c in raw_headers]
        # A table states its unit once, in the header: "Area (ha)". The cells then
        # carry bare numbers. Without this the column has no unit, nothing can be
        # compared against a scalar that does have one, and every sum check is
        # silently impossible.
        header_units = [_header_unit(c) for c in raw_headers]
        block_rows = len(block) - 2
        body_cells = []
        for row in block[2:]:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            body_cells.append(cells)
            for header, header_unit, cell in zip(headers, header_units, cells):
                if not header:
                    continue
                q = first_quantity(cell)
                if q is None:
                    continue
                value, unit = q
                columns[header].append((value, unit or header_unit))
        # A column counts toward the hole check ONLY if it is a measurement column:
        # it declares a unit in its header, or EVERY one of its non-empty cells
        # parses as a figure. This is the same standard reference_tables.parse_table
        # uses to call a column "value", and the two should not disagree.
        #
        # Two corpora were needed to get it right. An identifier column whose cells
        # carry no digit at all ("P-A", "P-B") parsed zero values and was reported as
        # "filled in 0 of N rows"; the first fix admitted any column that parsed at
        # least one figure, and the second negotiation corpus then produced a false
        # amendment from a 13-row TEXT column in which exactly one cell happened to
        # contain a number (the "401" inside a plan name), reported as "1 values
        # against 13 rows". One incidental figure does not make a column of prose a
        # column of measurements. A blank cell is still a hole: blanks are not
        # counted as non-empty, so a column of ten figures and three blanks still
        # reports ten of thirteen, which is the case the check exists for.
        for i, (header, header_unit) in enumerate(zip(headers, header_units)):
            if not header:
                continue
            cells = [row[i] for row in body_cells if i < len(row) and row[i].strip()]
            if header_unit or (cells and all(first_quantity(c) is not None for c in cells)):
                row_counts[header] += block_rows
    return scalars, dict(columns), dict(row_counts)


def _header_unit(raw_header):
    """The unit a table header declares for its column, e.g. 'Area (ha)' -> 'ha'."""
    m = re.search(r"\(([^)]{1,16})\)\s*$", str(raw_header or "").strip())
    if not m:
        return ""
    candidate = m.group(1).strip()
    ok = re.fullmatch(r"(?:" + _LETTER + r"|%|" + _SYM + r")(?:[^\W_]|[/%·*-])*", candidate)
    return candidate if ok else ""


def _match_unit(m, text, known_units=()):
    """The unit of one _QUANTITY match, honouring a prefix and a known phrase."""
    if m.group("sym"):
        return m.group("sym")
    if m.group("code"):
        return m.group("code")
    unit = (m.group("unit") or "").strip()
    if not unit or not known_units or not re.fullmatch(_LETTER + r"+", unit):
        return unit
    # Extend a one-word unit into the longest following phrase the document itself
    # uses as a unit: a two-word unit is read whole only when the phrase is in
    # known_units, which unit_phrases fills from phrases that recur after figures.
    best, pos, words = unit, m.end(), [unit]
    for _ in range(UNIT_PHRASE_MAX_WORDS - 1):
        w = _UNIT_WORD.match(text, pos)
        if not w:
            break
        words.append(w.group(1))
        pos = w.end()
        phrase = " ".join(words)
        if phrase in known_units:
            best = phrase
    return best


def first_quantity(text, known_units=()):
    """The first (value, unit) in a cell or value string, or None."""
    text = str(text or "")
    for m in _QUANTITY.finditer(text):
        value = norm_number(m.group("num"))
        if value is None:
            continue
        return (value, _match_unit(m, text, known_units))
    return None


def quantities(text, known_units=()):
    """Every (value, unit, start, end) in a string, in order."""
    text = str(text or "")
    out = []
    for m in _QUANTITY.finditer(text):
        value = norm_number(m.group("num"))
        if value is None:
            continue
        out.append((value, _match_unit(m, text, known_units), m.start(), m.end()))
    return out


def unit_phrases(text):
    """Multi-word units the document itself uses: a phrase of up to
    UNIT_PHRASE_MAX_WORDS letter-words following a figure in at least two places.
    Self-validating in the same sense as reference_tables.resolve_unit: one
    occurrence is prose, two is the document's own vocabulary."""
    text = str(text or "")
    seen = defaultdict(int)
    for m in _QUANTITY.finditer(text):
        if m.group("sym") or m.group("code"):
            continue
        unit = (m.group("unit") or "").strip()
        if not unit or not re.fullmatch(_LETTER + r"+", unit):
            continue
        pos, words = m.end(), [unit]
        for _ in range(UNIT_PHRASE_MAX_WORDS - 1):
            w = _UNIT_WORD.match(text, pos)
            if not w:
                break
            words.append(w.group(1))
            pos = w.end()
            seen[" ".join(words)] += 1
    return {phrase for phrase, n in seen.items() if n >= 2}


def bounds_from_rule(rule_text):
    """Numeric bounds the rule states in its own text, as (low, high, unit) or None.

    Only fires when the rule carries at least two numbers sharing a unit, which is
    what a stated band looks like. A rule that states no numbers yields nothing and
    no band comparison is attempted, which is the honest outcome rather than a
    guessed one.
    """
    found = [(value, unit) for value, unit, _, _ in quantities(rule_text)]
    by_unit = defaultdict(list)
    for value, unit in found:
        by_unit[_unit_str(unit_exponents(unit))].append(value)
    for unit, values in by_unit.items():
        if unit and len(values) >= 2:
            return (min(values), max(values), unit)
    return None


# ---------------------------------------------------------------------------
# the arithmetic, in Python


def _band_comparisons(scalars, columns, low, high, bound_unit):
    """Every comparison a band supports, as (relation, computed, label, basis).

    Shared by the rule-stated band and the reference-table band so the two can
    never drift into comparing different things. A value inside the band yields
    nothing for a direct comparison and an agreeing check for a ratio, exactly as
    the rule-stated path always did."""
    out = []
    direct = list(scalars.items())
    for label, values in sorted(columns.items()):
        for i, value_unit in enumerate(values):
            direct.append((label + ("row%d" % (i + 1),), value_unit))
    for label, (value, unit) in direct:
        if _unit_str(unit_exponents(unit)) != bound_unit:
            continue
        if value > high:
            relation, agrees = "above_band", False
        elif value < low:
            relation, agrees = "below_band", False
        else:
            # IN RANGE IS STILL COMPUTED. This branch used to emit nothing for a
            # value inside its band, which plan_calls then read as "nothing could be
            # computed for this pair" and sent to the model. The first corpus with
            # one figure per unit made 35 calls for 29 pairs because of it: Python
            # had decided every one of those values was fine and asked anyway. An
            # agreeing check, the same idiom the ratio branch below already uses,
            # marks the pair settled and costs no call.
            relation, agrees = "ratio_out_of_range", True
        out.append((relation, value, agrees, " ".join(label),
                    "%s against the range" % " ".join(label), (label,)))
    items = sorted(scalars.items())
    for la, (va, ua) in items:
        for lb, (vb, ub) in items:
            if la == lb or vb == 0:
                continue
            if _unit_str(_divide(ua, ub)) != bound_unit:
                continue
            ratio = va / vb
            if ratio > high:
                relation, agrees = "above_band", False
            elif ratio < low:
                relation, agrees = "below_band", False
            else:
                relation, agrees = "ratio_out_of_range", True
            out.append((relation, round(ratio, 6), agrees, "",
                        "%s divided by %s" % (" ".join(la), " ".join(lb)), (la, lb)))
    return out


def compute_checks(scalars, columns, *, rule_text="", row_counts=None,
                   needed=None, present_labels=None, reference_bands=(),
                   vocabulary=None, unit_labels=None):
    """Every comparison the figures themselves support. The model computes nothing.

    Three families, each proposed mechanically:
      sum_mismatch      a column summed against the scalar whose label contains the
                        column's label words
      product_mismatch  a scalar against the product of two fields whose units
                        multiply to the scalar's unit
      ratio_out_of_range / above_band / below_band
                        a ratio of two fields against bounds the RULE ITSELF states
    """
    checks = []

    # A column that parsed fewer values than its table has rows has a hole in it.
    # This is how a blank cell becomes a finding rather than a silence: the table
    # itself says how many rows there are, so the absence is measurable.
    for col_label, expected in sorted((row_counts or {}).items()):
        got = len(columns.get(col_label, []))
        if expected and got < expected:
            checks.append({
                "relation": "missing_field",
                "computed": got, "computed_unit": "values",
                "stated": expected, "stated_unit": "rows",
                "agrees": False,
                "basis": "%s is filled in %d of %d rows" % (" ".join(col_label), got, expected),
                "stated_field": " ".join(col_label),
            })

    # A field the RULE names, that this unit does not carry at all.
    #
    # Presence is judged against the unit's own LABELS, not against the numeric
    # maps. A field whose value is text ("Region: <name>") is present but has no
    # number, and checking the numeric maps reported every such field as missing
    # on every unit. That was 8 false positives out of 18 on the operator's
    # document before this was fixed.
    present = set(present_labels) if present_labels is not None else (
        set(scalars) | set(columns or {}))
    for label in sorted(needed or ()):
        if label in present:
            continue
        checks.append({
            "relation": "missing_field",
            "computed": 0, "computed_unit": "values",
            "stated": 1, "stated_unit": "required",
            "agrees": False,
            "basis": "the rule names %s and this unit does not carry it" % " ".join(label),
            "stated_field": " ".join(label),
        })

    for col_label, values in sorted(columns.items()):
        if len(values) < 2:
            continue
        col_unit = values[0][1]
        if not col_unit:
            # A column with no unit anywhere is an identifier column, not a
            # measurement. Summing parcel numbers would be arithmetic about nothing.
            continue
        if not all(_same_unit(u, col_unit) for _, u in values):
            continue
        total = math.fsum(v for v, _ in values)
        for label, (value, unit) in sorted(scalars.items()):
            if not set(col_label) < set(label):
                continue
            if not _same_unit(unit, col_unit):
                continue
            checks.append({
                "relation": "sum_mismatch",
                "computed": round(total, 6), "computed_unit": col_unit,
                "stated": value, "stated_unit": unit,
                "agrees": _close(total, value),
                "basis": "sum of %d values under %s" % (len(values), " ".join(col_label)),
                "stated_field": " ".join(label),
            })

    items = sorted(scalars.items())
    for i, (la, (va, ua)) in enumerate(items):
        for lb, (vb, ub) in items[i + 1:]:
            product_unit = _multiply(ua, ub)
            if not product_unit:
                continue
            for lc, (vc, uc) in items:
                if lc in (la, lb):
                    continue
                if unit_exponents(uc) != product_unit:
                    continue
                computed = va * vb
                checks.append({
                    "relation": "product_mismatch",
                    "computed": round(computed, 6), "computed_unit": _unit_str(product_unit),
                    "stated": vc, "stated_unit": uc,
                    "agrees": _close(computed, vc),
                    "basis": "%s times %s" % (" ".join(la), " ".join(lb)),
                    "stated_field": " ".join(lc),
                })

    bounds = bounds_from_rule(rule_text)
    if bounds:
        low, high, bound_unit = bounds
        # A band can sit on a VALUE, not only on a ratio. A rule saying a
        # figure must lie inside a range is the commonest kind there is, and
        # the first version only ever compared ratios, so a direct band was
        # never checked at all. Found by a gate check, not by reading.
        direct = list(scalars.items())
        for label, values in sorted(columns.items()):
            for i, value_unit in enumerate(values):
                direct.append((label + ("row%d" % (i + 1),), value_unit))
        # R6: a band the rule STATES applies to the fields the rule NAMES, when it
        # names any this unit carries. It used to apply to every figure in the unit
        # sharing the bound's unit of measure. Measured on the first negotiation
        # corpus: a rule reading "the year one increase must sit inside 15% to 20%"
        # was compared against the general wage increase total and the year two,
        # three and four increases, five false band records on one unit, one of
        # which reached the deliverable as an amendment. This is the same rule R1
        # established for a band read off a reference table (the rule must name the
        # range column), which was never applied to a band the rule states itself.
        # A rule that names no field of this unit keeps the old behaviour, because
        # otherwise it could never fire at all.
        named_here = {lbl for lbl in (needed or ()) if lbl in scalars or lbl in columns}
        if named_here:
            direct = [(lbl, v) for lbl, v in direct
                      if lbl in named_here or lbl[:-1] in named_here]
        for label, (value, unit) in direct:
            if _unit_str(unit_exponents(unit)) != bound_unit:
                continue
            if value > high:
                relation, agrees = "above_band", False
            elif value < low:
                relation, agrees = "below_band", False
            else:
                continue
            checks.append({
                "relation": relation,
                "computed": value, "computed_unit": bound_unit,
                "stated": None, "stated_unit": bound_unit,
                "band_low": low, "band_high": high,
                "agrees": agrees,
                "basis": "%s against the range the rule states" % " ".join(label),
                "stated_field": " ".join(label),
            })
        for la, (va, ua) in items:
            for lb, (vb, ub) in items:
                if la == lb or vb == 0:
                    continue
                ratio_unit = _divide(ua, ub)
                if _unit_str(ratio_unit) != bound_unit:
                    continue
                ratio = va / vb
                if ratio > high:
                    relation, agrees = "above_band", False
                elif ratio < low:
                    relation, agrees = "below_band", False
                else:
                    relation, agrees = "ratio_out_of_range", True
                checks.append({
                    "relation": relation,
                    "computed": round(ratio, 6), "computed_unit": bound_unit,
                    "stated": None, "stated_unit": bound_unit,
                    "band_low": low, "band_high": high,
                    "agrees": agrees,
                    "basis": "%s divided by %s" % (" ".join(la), " ".join(lb)),
                    "stated_field": "",
                })

    # R1: a band that lives in the reference corpus's own TABLE, not in the rule.
    # The rule points at the table; reference_tables matched this unit to a row and
    # read (low, high, unit) off it. The comparison below is the same one the
    # rule-stated path makes, so a table band and a rule band are judged alike, and
    # the finding cites the reference PASSAGE the band came from rather than
    # whatever excerpt happened to be in the prompt.
    for band in reference_bands or ():
        low, high, bound_unit = band["low"], band["high"], band["unit"]
        for relation, computed, agrees, stated_field, basis, labels in _band_comparisons(
                scalars, columns, low, high, bound_unit):
            check = {
                "relation": relation,
                "computed": computed, "computed_unit": bound_unit,
                "stated": None, "stated_unit": bound_unit,
                "band_low": low, "band_high": high,
                "agrees": agrees,
                "basis": "%s against %s in the reference corpus" % (
                    basis, band.get("row_label") or "the matched row"),
                "stated_field": stated_field,
                "ref_id": band.get("ref_id") or "",
                "band_row": band.get("row_label") or "",
            }
            if relation == "below_band":
                # The low side can carry a condition the figures alone cannot
                # settle. Whether it does is decided from the rule's own named
                # fields against this comparison's fields, never from prose.
                import reference_tables

                used = set(band.get("key_labels") or ()) | set(labels)
                condition, verdict = reference_tables.low_side_condition(
                    rule_text, vocabulary, used, unit_labels)
                if verdict == "model":
                    check["conditional_on"] = [" ".join(c) for c in condition]
            checks.append(check)
    return checks


def _close(a, b):
    if a is None or b is None:
        return False
    if abs(a - b) <= ABS_TOLERANCE:
        return True
    scale = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / scale <= REL_TOLERANCE


def disagreements(checks):
    """Only the computed comparisons that do NOT agree."""
    return [c for c in checks if not c.get("agrees")]


# ---------------------------------------------------------------------------
# the judging call


def build_pair_payload(*, unit, rule, checks, refs=None, source_rule_id=""):
    """The work payload for one (unit, rule) pair.

    Carries the computed values and NOT the arithmetic. The model is asked whether
    the discrepancy is material and how to state it for a reader; it is never asked
    what the figures add up to, because H1 measured that it cannot do it.
    """
    disagree = disagreements(checks)
    payload = {
        "task": "paired_review",
        "document_id": unit["unit_id"],
        "document_name": unit.get("title") or unit["unit_id"],
        "unit_id": unit["unit_id"],
        "document_text": unit.get("text", ""),
        "rule_id": rule["id"],
        "rule_text": rule.get("rule", ""),
        "evaluate_against": [rule["id"]],
        "computed_comparisons": [
            {
                "relation": c["relation"],
                "computed_value": c["computed"],
                "computed_unit": c["computed_unit"],
                "stated_value": c["stated"],
                "stated_unit": c["stated_unit"],
                "stated_field": c.get("stated_field", ""),
                "basis": c["basis"],
                "band_low": c.get("band_low"),
                "band_high": c.get("band_high"),
            }
            for c in disagree
        ],
        "arithmetic_note": (
            "The comparisons above were computed in code from this unit's own "
            "figures. Do not recompute them and do not perform any arithmetic. "
            "Decide only whether the difference is material under the rule, and "
            "write one explanation a person can read."
        ),
    }
    if source_rule_id:
        payload["source_rule_id"] = source_rule_id
    if refs:
        payload["reference_index_excerpt"] = refs
    return payload


def finding_from_check(*, unit_id, rule, check, source_rule_id="", refs=None,
                       explanation=""):
    """A typed Finding record built from a COMPUTED comparison.

    The values in the record are the ones Python computed. Whatever the model says
    about materiality lands in `explanation` and nowhere else, so a wrong sentence
    can never change a figure.
    """
    # R1: a band read off a reference table cites THAT passage. Anything else
    # cites whatever excerpt happened to be in the prompt, which is not what the
    # finding actually rests on.
    band_ref = str(check.get("ref_id") or "")
    # R6: a prior-version check carries every citation of the earlier statement
    # (a line and a summary table may both state it). Existing checks carry no
    # ref_ids, so their citation is byte-identical to before.
    cited = ([str(r) for r in (check.get("ref_ids") or []) if r]
             or ([band_ref] if band_ref else list(refs or [])))
    item = {
        "ref": (cited or ["document-level"])[0],
        "kind": "finding",
        "confidence": "CONFIDENT",
        "rule_id": rule["id"],
        "unit_id": unit_id,
        "relation": check["relation"],
        "record_verdict": "ok" if check.get("agrees") else "irregular",
        "value_a": check["computed"],
        "unit_a": check["computed_unit"] or "1",
        "source_refs": cited,
        "explanation": explanation or _default_explanation(check),
    }
    if check.get("computed") is None:
        # R6: absent_since_prior has nothing to state as value_a; the earlier
        # figure travels as value_b below. An empty value_a is omitted, never None.
        item.pop("value_a")
        item.pop("unit_a")
    # A low-side result the rule qualifies is carried with its condition named, so
    # nothing downstream can promote it to a settled irregularity behind the
    # operator's back. Flat, per INFRA-037: an array of scalars.
    if check.get("conditional_on"):
        item["conditional_on"] = list(check["conditional_on"])
    if check.get("stated") is not None:
        item["value_b"] = check["stated"]
        item["unit_b"] = check["stated_unit"] or "1"
    elif check.get("band_low") is not None or check.get("band_high") is not None:
        # refine R2: report the bound that was actually CROSSED. This used to take
        # band_high unconditionally, so a below_band finding stated the top of the
        # range as the figure it fell short of, which is the wrong number in the
        # one sentence a reader checks.
        bound = (check.get("band_low") if check["relation"] == "below_band"
                 else check.get("band_high"))
        if bound is None:
            bound = check.get("band_high") if check.get("band_high") is not None \
                else check.get("band_low")
        item["value_b"] = bound
        item["unit_b"] = check["computed_unit"] or "1"
    if source_rule_id:
        item["source_rule_id"] = source_rule_id
    # R6 / INFRA-044: the optional comparison fields, set whenever the check carries
    # them. field_label is set for EVERY relation with a named field, so a consumer
    # can join a band record to a prior record on (unit_id, field_label).
    if check.get("stated_field"):
        item["field_label"] = str(check["stated_field"])
    if check.get("delta") is not None:
        item["delta"] = check["delta"]
    if check.get("band_distance_change") is not None:
        item["band_distance_change"] = check["band_distance_change"]
    return item


def _default_explanation(check):
    relation = str(check.get("relation") or "")
    if relation in finding_record.PRIOR_RELATIONS:
        field = check.get("stated_field") or "the field"
        if relation == "unchanged_from_prior":
            return "%s is %s %s, unchanged from the earlier document." % (
                field, check["computed"], check["computed_unit"])
        if relation == "absent_since_prior":
            return "%s was %s %s in the earlier document and is not stated here." % (
                field, check["stated"], check["stated_unit"])
        sentence = "%s is %s %s, changed from %s %s in the earlier document (delta %+g %s)." % (
            field, check["computed"], check["computed_unit"], check["stated"],
            check["stated_unit"], check.get("delta") or 0.0, check["computed_unit"])
        if check.get("band_distance_change") is not None:
            direction = "toward" if relation == "moved_toward" else (
                "away from" if relation == "moved_away" else "relative to")
            sentence += " It moved %s the band the rule states (%s to %s), by %+g %s." % (
                direction, check.get("band_low"), check.get("band_high"),
                check["band_distance_change"], check["computed_unit"])
        return sentence
    if check.get("stated") is not None:
        return ("%s gives %s %s, while the document states %s %s."
                % (check["basis"], check["computed"], check["computed_unit"],
                   check["stated"], check["stated_unit"]))
    return ("%s gives %s %s against a stated range of %s to %s."
            % (check["basis"], check["computed"], check["computed_unit"],
               check.get("band_low"), check.get("band_high")))


def dedupe(items):
    """One finding per (unit_id, rule_id, relation, basis of the comparison)."""
    seen, out = set(), []
    for item in items or []:
        key = (item.get("unit_id"), item.get("rule_id"), item.get("relation"),
               item.get("value_a"), item.get("value_b"))
        if item.get("relation") in finding_record.PRIOR_RELATIONS:
            # R6: two fields of one unit may hold the same figure under the same
            # rule (two terms both unchanged at 45 kes). They are two records.
            key += (item.get("field_label"),)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


BAND_RELATIONS = ("above_band", "below_band", "ratio_out_of_range")


def plan_calls(units_by_id, pairs, rules_by_id, vocabulary, *, needed_fields_for=None,
               reference_bands_for=None, known_units=None):
    """One judging call per DISTINCT computed disagreement, not per pair.

    Found by measuring the plan at H7 rather than by reading the code. A sum or a
    product does not depend on which rule is being applied: compute_checks ignores
    the rule text except to read bounds out of it. So a unit with one arithmetic
    mismatch and ten paired rules was producing that same mismatch ten times and
    asking the model about it ten times. On the operator's document that was 40
    calls and a projected 52 to 57 minutes, SLOWER than the 40.3 minute wide run
    paired mode replaced, which would have made the whole step a regression.

    The fix follows the arithmetic. Rule-independent checks (sums, products,
    missing fields) are computed ONCE per unit and judged once, attributed to a
    rule that names the fields involved. Only band checks, which read their bounds
    from a rule's own text, are computed per rule.

    Returns a list of call specs: {unit, rule, checks, kind}.
    """
    needed_fields_for = needed_fields_for or (lambda text: set())
    by_unit = {}
    for unit_id, rule_id in pairs:
        by_unit.setdefault(unit_id, []).append(rule_id)

    plans = []
    for unit_id, rule_ids in by_unit.items():
        unit = units_by_id.get(unit_id)
        if unit is None:
            continue
        scalars, columns, row_counts = extract_fields(unit.get("text", ""), known_units)
        present = pairing_map.unit_fields(unit.get("text", ""))
        needed_union = set()
        for rule_id in rule_ids:
            rule = rules_by_id.get(rule_id)
            if rule:
                needed_union |= needed_fields_for(rule.get("rule", ""))

        # Rule-independent: computed once for the unit.
        shared = [c for c in compute_checks(scalars, columns, rule_text="",
                                            row_counts=row_counts, needed=needed_union,
                                            present_labels=present)
                  if c["relation"] not in BAND_RELATIONS]
        seen = set()
        for check in disagreements(shared):
            key = (check["relation"], check.get("basis"), check.get("computed"),
                   check.get("stated"))
            if key in seen:
                continue
            seen.add(key)
            plans.append({"unit": unit, "rule": rules_by_id.get(
                _rule_for_check(check, rule_ids, rules_by_id, needed_fields_for)),
                "checks": [check], "kind": "computed"})

        # Rule-dependent: a band lives in a rule's own text, or (R1) in a table in
        # the reference corpus that the rule points at, so it is computed per rule.
        for rule_id in rule_ids:
            rule = rules_by_id.get(rule_id)
            if not rule:
                continue
            bands = (reference_bands_for(unit.get("text", ""), rule)
                     if reference_bands_for else ())
            band = [c for c in compute_checks(scalars, columns,
                                              rule_text=rule.get("rule", ""),
                                              row_counts=row_counts,
                                              # R6: the band branch needs to know which
                                              # fields THIS rule names, or a stated band
                                              # is applied to every same-unit figure in
                                              # the unit. Only BAND_RELATIONS are kept
                                              # below, so the missing_field checks this
                                              # now also computes are discarded here and
                                              # still come from the shared pass above.
                                              needed=needed_fields_for(rule.get("rule", "")),
                                              present_labels=present,
                                              reference_bands=bands,
                                              vocabulary=vocabulary,
                                              unit_labels=present)
                    if c["relation"] in BAND_RELATIONS]
            for check in disagreements(band):
                plans.append({"unit": unit, "rule": rule, "checks": [check],
                              "kind": "band"})

        # A pair where nothing at all could be computed still needs the model, on
        # the text, for one unit against one rule.
        if not shared:
            for rule_id in rule_ids:
                rule = rules_by_id.get(rule_id)
                if rule is None:
                    continue
                if not compute_checks(scalars, columns, rule_text=rule.get("rule", ""),
                                      row_counts=row_counts, needed=set(),
                                      present_labels=present):
                    plans.append({"unit": unit, "rule": rule, "checks": [],
                                  "kind": "uncomputable"})
    return [pl for pl in plans if pl["rule"] is not None]


def _rule_for_check(check, rule_ids, rules_by_id, needed_fields_for):
    """Attribute a rule-independent finding to a rule that names its field.

    The comparison is the same whichever rule prompted it, but the finding has to
    cite one, and the honest one is a rule that actually mentions the field the
    comparison is about. Falls back to the first paired rule when none does.
    """
    field = str(check.get("stated_field") or "")
    words = {w for w in field.lower().split() if w}
    basis_words = {w for w in str(check.get("basis") or "").lower().split() if w}
    # Scored by OVERLAP, not by containment. Containment was too strict to ever
    # fire: a sum finding on "total declared extent" was being compared against a
    # rule that names the column "extent", and {total, declared, extent} is not a
    # subset of {extent, plot}, so every finding fell through to the first paired
    # rule regardless of what any rule said. Found by a gate check.
    best, best_score = None, 0
    first = None
    for rule_id in rule_ids:
        rule = rules_by_id.get(rule_id)
        if not rule:
            continue
        if first is None:
            first = rule_id
        flat = {w for label in needed_fields_for(rule.get("rule", "")) for w in label}
        if not flat:
            continue
        score = len(flat & words) * 2 + len(flat & basis_words)
        if score > best_score:
            best, best_score = rule_id, score
    return best or first


# ---------------------------------------------------------------------------
# R6: the same field in an EARLIER VERSION of the document
#
# A negotiation is reviewed round by round, and the question about round N is
# never only "is this inside the mandate" but "what moved since round N-1, which
# way, what held, and what was dropped". The earlier version is a role the
# operator declares (the manifest's `prior` list); nothing here infers it. Its
# figures are read exactly as the document under review's are (label lines and
# single-value table columns), matched by label word-set EQUALITY, and every
# record cites the paragraph of the earlier version the figure came from. A match
# with no citation, a tie, a unit mismatch or a disagreement between the bands
# that would orient the move is REFUSED and written down, never minted. The
# records are ok-verdict by construction (INFRA-044): movement is information,
# not an irregularity, so none of them ever becomes an amendment.


def prior_index(prior_text, ref_for_paragraph, known_units=()):
    """Every figure an earlier version states, with the REF-* of its paragraph.

    Reads the FULL text rather than the reference index's excerpts on purpose:
    an excerpt is capped (reference_builder.PROSE_EXCERPT_CHARS) and would drop
    label lines and table rows. The paragraphs are split exactly as
    ReferenceIndex.index_document splits them, so paragraph i (1-based) is the
    entry whose location["paragraph"] == i, and `ref_for_paragraph(i)` returns
    that entry's REF-* id or "" when none is on file.
    """
    import reference_builder
    import reference_tables

    paras = [p.strip() for p in reference_builder._PARA_RE.split(prior_text or "") if p.strip()]
    units = pairing_map.split_units(prior_text or "")

    def _slug_of(unit):
        uid = unit.get("unit_id", "")
        return uid.split("-", 1)[1] if "-" in uid else ""

    lines, tables, uncited = [], [], 0
    for i, para in enumerate(paras, start=1):
        ref = str(ref_for_paragraph(i) or "")
        if not ref:
            uncited += 1
        slug = next((_slug_of(u) for u in units if para in u.get("text", "")), "")
        scalars, _, _ = extract_fields(para, known_units=known_units)
        for label, (value, unit) in scalars.items():
            lines.append({"label": label, "value": value,
                          "unit": _unit_str(unit_exponents(unit)) if unit else "",
                          "ref_id": ref, "paragraph": i, "unit_slug": slug,
                          "source": "line"})
        for table in reference_tables.parse_tables(para, ref_id=ref, document_id="",
                                                   known_units=known_units):
            tables.append({"table": table, "ref_id": ref, "paragraph": i, "unit_slug": slug})
    return {"lines": lines, "tables": tables, "paragraph_count": len(paras),
            "uncited_paragraphs": uncited}


def prior_lookup(index, scalars, unit_slug):
    """The earlier figure for each of this unit's labelled fields, or a refusal.

    A label may be stated more than once in the earlier version (a line and a
    summary table, or the same label under two headings). Agreement is fine and
    every citation is kept; disagreement is narrowed to the earlier unit whose
    heading slug matches this unit's, and a disagreement that survives that is a
    tie and is refused. An earlier statement with no citation on file is refused
    too: a record that cannot cite its source is not written.
    """
    import reference_tables

    candidates, refused = {}, []
    for entry in index.get("lines", []):
        if entry["label"] in scalars:
            candidates.setdefault(entry["label"], []).append(entry)
    for t in index.get("tables", []):
        hits, table_refused = reference_tables.prior_values_for_scalars(t["table"], scalars)
        for label, hit in hits.items():
            candidates.setdefault(label, []).append(
                {**hit, "unit_slug": t["unit_slug"], "source": "table", "paragraph": t["paragraph"]})
        for r in table_refused:
            # A whole-table refusal carries an empty label; it is kept so the operator
            # can see why a table of the earlier version supplied no figure at all.
            refused.append({"label": r.get("label", ""), "reason": r["reason"],
                            "ref_ids": [r["ref_id"]] if r.get("ref_id") else []})

    def _distinct(cands):
        return {(round(c["value"], 9), c["unit"]) for c in cands}

    hits = {}
    for label, cands in sorted(candidates.items()):
        chosen = cands if len(_distinct(cands)) == 1 else [
            c for c in cands if c.get("unit_slug") and c["unit_slug"] == unit_slug]
        if len(_distinct(chosen)) != 1:
            refused.append({"label": " ".join(label),
                            "reason": "tie: %d differing earlier statements" % len(_distinct(cands)),
                            "ref_ids": sorted({c["ref_id"] for c in cands if c.get("ref_id")})})
            continue
        refs = sorted({c["ref_id"] for c in chosen if c.get("ref_id")})
        if not refs:
            refused.append({"label": " ".join(label),
                            "reason": "no citation on file for the earlier statement",
                            "ref_ids": []})
            continue
        first = chosen[0]
        hits[label] = {"value": first["value"], "unit": first["unit"], "ref_ids": refs,
                       "source": first["source"], "row_label": first.get("row_label", "")}
    return hits, refused


def _band_distance(value, low, high):
    return 0.0 if low <= value <= high else min(abs(value - low), abs(value - high))


def prior_checks(scalars, hits, bands_by_label):
    """One comparison per field the earlier version also states.

    unchanged_from_prior    the same figure, within the arithmetic tolerance
    moved_toward            a different figure, and exactly one band from a paired
    moved_away              rule that NAMES the field orients it: the relation is
                            the SIGN of the change in distance to that band
    changed_from_prior      a different figure with no single band to orient it
                            (no band, or a change that leaves the distance as it was)

    `agrees` is True on every check on purpose: it is the signal plan_calls uses
    to buy a judging call and finding_from_check uses to set the verdict, and a
    movement is information, not an irregularity (INFRA-044).
    """
    checks, refused = [], []
    for label, (value, unit) in sorted(scalars.items()):
        hit = hits.get(label)
        if hit is None:
            continue
        ue = _unit_str(unit_exponents(unit))
        if not ue or ue != hit["unit"]:
            refused.append({"label": " ".join(label), "reason": "units differ or are empty",
                            "ref_ids": list(hit["ref_ids"])})
            continue
        same = _close(value, hit["value"])
        check = {
            "relation": "unchanged_from_prior" if same else "changed_from_prior",
            "computed": value, "computed_unit": ue,
            "stated": hit["value"], "stated_unit": ue,
            "delta": 0.0 if same else round(value - hit["value"], 6),
            "agrees": True,
            "basis": "%s against the same field in the earlier document" % " ".join(label),
            "stated_field": " ".join(label),
            "ref_id": hit["ref_ids"][0], "ref_ids": list(hit["ref_ids"]),
        }
        bands = [b for b in (bands_by_label.get(label) or []) if b.get("unit") == ue]
        spans = {(b["low"], b["high"]) for b in bands}
        if len(spans) == 1:
            low, high = next(iter(spans))
            change = round(_band_distance(value, low, high)
                           - _band_distance(hit["value"], low, high), 6)
            check["band_distance_change"] = change
            check["band_low"], check["band_high"] = low, high
            check["band_rule_id"] = bands[0].get("rule_id", "")
            if not same and change < 0:
                check["relation"] = "moved_toward"
            elif not same and change > 0:
                check["relation"] = "moved_away"
        elif len(spans) > 1:
            refused.append({"label": " ".join(label),
                            "reason": "bands disagree: %d spans" % len(spans),
                            "ref_ids": list(hit["ref_ids"])})
        checks.append(check)
    return checks, refused


def absent_checks(index, present_labels, unit_slug, scalars=None, hits=None):
    """A field the earlier version stated under THIS unit's heading that no unit
    of the document under review states any more: absent_since_prior.

    Attached to the unit whose heading slug the earlier statement sat under, so
    a term dropped from one section is reported against that section. A dropped
    term whose earlier heading has no counterpart here is not silently lost: the
    caller reports it as a refusal. The earlier figure travels as value_b; there
    is no value_a, because there is nothing to state. Returns (checks, refused):
    a dropped term whose earlier statement has no citation on file is refused.

    G2 (the rename fabrication fix): exact label matching cannot tell a genuine
    withdrawal from a field that was merely reworded, because a rewording changes
    the normalised label tuple and the two look identical to a membership test
    (docs/fix/STEP_F1_REPORT.md, STEP_F2_REPORT.md). Before minting, a vanished
    label is checked against every label THIS unit states that the earlier version
    did not (`scalars` minus `hits`, i.e. "new since prior, same section"): if one
    of those carries a value within `rename_tolerance()` of the vanished label's
    value, in the same unit, the mint is refused instead, naming both labels and
    both values. `scalars`/`hits` are optional and default to no corroboration
    pool, so a caller that does not yet pass them keeps today's behaviour rather
    than crashing; every real caller (pipeline._prior_comparison) passes both.
    """
    import reference_tables

    scalars = scalars or {}
    hits = hits or {}
    candidates = [(lbl, val, unit) for lbl, (val, unit) in scalars.items()
                  if lbl not in hits]

    def _rename_candidate(label, value, unit):
        ue = _unit_str(unit_exponents(unit)) if unit else ""
        for cand_label, cand_val, cand_unit in candidates:
            cue = _unit_str(unit_exponents(cand_unit)) if cand_unit else ""
            if cue != ue or not ue:
                continue
            scale = max(abs(value), abs(cand_val), 1e-12)
            if abs(value - cand_val) / scale <= rename_tolerance():
                return cand_label, cand_val
        return None

    seen, checks, refused = set(), [], []
    entries = list(index.get("lines", []))
    for t in index.get("tables", []):
        table = t["table"]
        keys = [i for i in reference_tables.key_column_indexes(table)
                if i != table.get("unit_column")]
        values = [i for i, k in enumerate(table["kinds"]) if k == "value"]
        if not keys or len(values) != 1:
            continue
        for row in table["rows"]:
            q = first_quantity(row[values[0]])
            if q is None:
                continue
            for k in keys:
                label = pairing_map._norm_label(row[k])
                if label:
                    unit = reference_tables._accept_cell_unit(
                        q[1], table["header_units"][values[0]]
                        or (row[table["unit_column"]].strip()
                            if table.get("unit_column") is not None else ""))
                    entries.append({"label": label, "value": q[0],
                                    "unit": _unit_str(unit_exponents(unit)) if unit else "",
                                    "ref_id": t["ref_id"], "unit_slug": t["unit_slug"]})
    for entry in entries:
        label = entry["label"]
        if label in present_labels or label in seen:
            continue
        if entry.get("unit_slug") != unit_slug:
            continue
        seen.add(label)
        # Every earlier statement of the dropped term is cited (a line and a summary
        # table may both state it), as long as they agree on the figure.
        same = [e for e in entries if e["label"] == label
                and _close(e["value"], entry["value"]) and e["unit"] == entry["unit"]]
        refs = sorted({e["ref_id"] for e in same if e.get("ref_id")})
        if not refs:
            # A dropped term with no citation on file is refused like any other
            # uncited earlier statement: a record that cannot cite its source is not
            # written, and the refusal says why.
            refused.append({"label": " ".join(label),
                            "reason": "no citation on file for the earlier statement",
                            "ref_ids": []})
            continue
        rename = _rename_candidate(label, entry["value"], entry["unit"])
        if rename is not None:
            # A label newly stated in this section carries a value close enough to
            # the vanished label's to be plausibly the same fact under a new name.
            # Exact matching cannot tell a rename from a withdrawal
            # (docs/fix/STEP_F1_REPORT.md), so this is refused rather than minted:
            # refusing is always allowed, fabricating an absence never is.
            cand_label, cand_val = rename
            refused.append({
                "label": " ".join(label),
                "reason": (
                    "possible rename, not a confirmed withdrawal: '%s' (%g) vanished "
                    "but '%s' (%g) is newly stated in the same section within %.0f%% "
                    "of the same value" % (
                        " ".join(label), entry["value"],
                        " ".join(cand_label), cand_val,
                        rename_tolerance() * 100)),
                "ref_ids": refs,
            })
            continue
        checks.append({
            "relation": "absent_since_prior",
            "computed": None, "computed_unit": entry["unit"],
            "stated": entry["value"], "stated_unit": entry["unit"],
            "agrees": True,
            "basis": "%s is stated in the earlier document and not here" % " ".join(label),
            "stated_field": " ".join(label),
            "ref_id": refs[0],
            "ref_ids": refs,
        })
    return checks, refused


def prior_findings(unit, rule_ids, rules_by_id, checks, *, needed_fields_for,
                   source_rule_id_for, agent, all_rules_by_id=None):
    """Typed ok-verdict records for the comparisons, each citing a rule.

    A band-oriented check cites the rule whose band oriented it. Any other check
    cites the paired rule that names its field, falling back to the first paired
    rule (_rule_for_check). An absent_since_prior check may cite ANY registry rule
    that names the dropped field, because by definition no rule naming it can
    have paired with a unit that no longer carries it. A check with no rule to
    cite is not minted: a Finding needs a registry CONV-*.

    item_id is set EXPLICITLY. make_envelope derives one from (agent, kind, ref,
    idx) only when absent, and two envelopes for the same agent would otherwise
    collide on it and one record would silently supersede the other.
    """
    if not checks:
        return []
    out = []
    for check in checks:
        rid = check.get("band_rule_id") if check.get("band_rule_id") in rules_by_id else None
        if rid is None and check.get("relation") == "absent_since_prior":
            # The dropped field is, by definition, carried by no unit here, so no
            # rule naming it can have paired with this unit: look across the whole
            # registry for a rule that names it BEFORE falling back to the unit's
            # first paired rule. `needed_fields_for` must test against a vocabulary
            # that includes the earlier version's labels for this to find anything.
            field = pairing_map._norm_label(check.get("stated_field") or "")
            for cand_id, cand in sorted((all_rules_by_id or rules_by_id).items()):
                if field and field in needed_fields_for(cand.get("rule", "")):
                    rid = cand_id
                    break
        if rid is None and rule_ids:
            rid = _rule_for_check(check, rule_ids, rules_by_id, needed_fields_for)
        rule = (rules_by_id.get(rid) or (all_rules_by_id or {}).get(rid)) if rid else None
        if rule is None:
            continue
        item = finding_from_check(unit_id=unit["unit_id"], rule=rule, check=check,
                                  source_rule_id=source_rule_id_for(rule["id"]),
                                  refs=check.get("ref_ids") or [])
        item["item_id"] = "%s:prior:%s:%s:%s" % (
            agent, unit["unit_id"], pairing_map._slug(check["stated_field"]), check["relation"])
        item["provenance"] = "computed"
        out.append(item)
    return out


def pairs_from_map(pairing, *, cap_per_unit=None):
    """The (unit_id, rule_id) pairs the map decided, optionally capped per unit.

    H4 measured 80 pairs on the operator's document and H3 measured 78 to 85
    seconds for a local call, which is about 106 minutes for one document. The cap
    is the lever, and it is explicit rather than hidden: the pairs a cap drops are
    reported so a run never quietly reviews less than it claims.
    """
    pairs, dropped = [], []
    for entry in pairing.get("units", []):
        paired = [p["rule_id"] for p in entry.get("paired", [])]
        keep = paired if cap_per_unit is None else paired[:cap_per_unit]
        for rid in keep:
            pairs.append((entry["unit_id"], rid))
        dropped.extend((entry["unit_id"], rid) for rid in paired[len(keep):])
    return pairs, dropped


# ---------------------------------------------------------------------------
# a computed finding must reach the deliverable even if every model call fails


def _repair_unit_id(unit_id, unit_texts):
    """One narrow, structural second chance when unit_id is not a unit_texts key.

    The contract now tells a convention-review agent to copy its unit_id from
    document_units (pipeline.py's own payload addition), and both wide-mode
    agents were changed to receive that list, so this should fire rarely. It
    exists for whatever a model still gets wrong: nothing about a contract is
    enforced, only asked for.

    The check is a boundary check, not a guess: a document-content identifier
    an agent invents instead (its reading of "the unit's own id") is, by
    construction, written INSIDE the unit's own text (that is what made it an
    identifier the agent could name at all), so unit_id appearing verbatim,
    case-insensitively, inside exactly one unit's text is real corroborating
    evidence, the same shape of evidence the rest of this module already
    trusts (label containment, most-specific-wins). Two or more units
    containing the same string, or none, is refused rather than guessed: a
    wrong repair would silently attach the wrong passage to a finding, worse
    than the honest fallback it would replace. No domain vocabulary here (S5):
    the test is string containment over the operator's own document, nothing
    is read from a list this file owns.

    Returns (resolved_unit_id, unit_record) on a single unambiguous match,
    or (None, None) when unit_id is falsy, already a direct key, or the match
    is zero-or-many.
    """
    if not unit_id or not isinstance(unit_texts, dict) or unit_id in unit_texts:
        return None, None
    needle = str(unit_id).strip().lower()
    if not needle:
        return None, None
    hits = [(uid, rec) for uid, rec in unit_texts.items()
           if isinstance(rec, dict) and needle in str(rec.get("text") or "").lower()]
    if len(hits) != 1:
        return None, None
    return hits[0]


def amendment_from_finding(item, *, document_level="document-level", unit_texts=None):
    """Build an amendment from a typed Finding record, with no model involved.

    unit_texts: the {unit_id: {"text": ..., ...}} map unit_texts_for(doc["text"],
    doc["id"]) already builds in pipeline.py, from the SAME document split that
    produced this finding's own unit_id. Passed in rather than recomputed here,
    since the caller (ensure_amendments_for_findings) already has it once per
    document and this function is called once per finding.

    Console fresh-eyes finding: original_text used to be str(unit_id) (e.g.
    "u09"), not the document's actual passage, even though the operator's own
    instruction is "change THIS passage to THAT", and the text was available
    the whole time, the document is read and split into units before any
    finding is computed, this function simply never received the result. That
    was not a display gap; it was data computed and then dropped before it
    ever reached the record that claims to describe the passage. Fixed at the
    source: when unit_texts has this finding's unit_id, original_text is the
    unit's actual text (the whole unit split_units produced, a section, a
    table row, or a table block, never only the single line the figure sits
    on, since the pipeline does not identify a narrower span than the unit
    itself). Falls back to the unit id, prefixed to say plainly what it is,
    only if unit_texts is not given or does not have this id (a defensive
    path for a caller that has not been updated, not the expected case for a
    real run through pipeline.py).

    Boundary repair (found on a real run against the catalogue_records
    corpus): a direct lookup misses for any finding whose own unit_id was
    written by a wide-mode agent stating the document's own identifier for
    what it was describing (e.g. "CAT-BIRCH") rather than the pipeline's
    split_units id (e.g. "u02-record-cat-birch"). The agent contract and its
    work payload were both changed to close most of this at the source
    (pipeline.py now hands PRACTICE_AUDITOR and STYLE_GUARDIAN the real
    id/title list, and the contract tells them to copy from it), but a
    contract cannot be enforced, only asked for, so this function still
    tries one narrow, structural second chance (_repair_unit_id) before
    falling back: the miss-shaped id, found written inside exactly one
    unit's own text. A single unambiguous match is used, and the amendment
    records unit_id_repaired_to so a reader can tell a repaired lookup from
    a direct one; zero or multiple matches are refused, same fallback as
    before, never guessed.

    H7's first scored run is why this exists. Python computed four arithmetic
    disagreements with certainty, AMENDMENT_DRAFTER then failed its contract
    (outcome=violated, items=0), and because the deliverable is assembled only
    from the drafter's output, review_data.json carried ZERO amendments. Four
    findings that were not in doubt were discarded because a local model could not
    write valid JSON.

    Everything the amendment contract requires is already in the record:
    convention_ref is rule_id, location is the first source_ref, ref_ids are the
    source_refs, and the comment can be written from the computed values. So it is
    written here. A finding the arithmetic is sure of does not get to depend on a
    model call succeeding.
    """
    if not isinstance(item, dict):
        return None
    rule_id = item.get("rule_id")
    if not rule_id:
        return None
    # R1: a finding whose rule attaches a condition to this side is NOT something
    # the arithmetic is sure of. The figure is outside the band, but the rule says
    # that alone is not the irregularity, and whether the condition holds is not in
    # the figures. Promoting it here would state as settled exactly the thing the
    # reference corpus says must not be stated as settled. It stays a finding on the
    # bus and reaches the deliverable only if the model's judgement carries it.
    if item.get("conditional_on"):
        return None
    refs = [str(r) for r in (item.get("source_refs") or []) if r]
    location = refs[0] if refs else document_level
    explanation = str(item.get("explanation") or "").strip()
    unit_id = item.get("unit_id")
    # The comment must carry at least one CONV-* and one REF-*, and it is the
    # human-facing sentence, so it says what was computed and what it rests on.
    # The operator's own id goes in the SENTENCE, not only in a field. A reader
    # comparing the review against their own rulebook needs CONV-A02, not the
    # registry's renumbered CONV-007, and a field nobody renders is a field
    # nobody reads. Measured: attribution scored 0 of 5 with the id in a field.
    own = item.get("source_rule_id")
    rule_text = ("%s (%s)" % (rule_id, own)) if own and own != rule_id else rule_id
    citation = "%s at %s" % (rule_text, refs[0] if refs else document_level)
    # refine R2: the COMPUTED FIGURES lead, always. They used to be a fallback,
    # used only when no model sentence existed, and the model's sentence usually
    # existed and usually named no figure. Measured on one run's own output: with
    # the arithmetic identical and only this prose differing, recall was 2/9 with
    # the model's sentences and 5/9 with figure-bearing ones, and a true band
    # finding scored as a false positive purely for saying "exceeds the typical
    # yield range" instead of "8.8 t/ha against a stated range of 1.6 to 3.4".
    # CONV-A10-style rules ask for the specific figures in so many words. So the
    # computed sentence is always present and the model's sentence, when there is
    # one and it says something different, follows it rather than replacing it.
    computed = _computed_sentence(item)
    parts = [computed]
    if explanation and explanation.strip() and explanation.strip() != computed:
        parts.append(explanation.strip())
    parts.append("Computed in code from the figures in this unit, not judged by a model.")
    parts.append("Grounded in %s." % citation)
    comment = " ".join(parts)
    unit_record = (unit_texts or {}).get(unit_id) if unit_id else None
    repaired_unit_id = None
    if unit_record is None and unit_id:
        repaired_unit_id, unit_record = _repair_unit_id(unit_id, unit_texts)
    unit_text = str(unit_record.get("text") or "").strip() if isinstance(unit_record, dict) else ""
    original_text = unit_text if unit_text else ("unit id %s (text not available)" % (unit_id or document_level))
    amendment = {
        "ref": location,
        "kind": "amendment",
        "confidence": item.get("confidence") or "CONFIDENT",
        "location": location,
        "convention_ref": rule_id,
        "original_text": original_text,
        "proposed_text": None,
        "action": "flag",
        "comment": comment,
        "severity": "required",
        "finding_type": "factual",
        "ref_ids": refs or [],
        "derived_from": "computed_finding",
        "finding_unit_id": item.get("unit_id"),
        "finding_rule_id": rule_id,
    }
    # The boundary repair, recorded rather than silently folded into a normal
    # direct hit: a reader (or the gate) can tell "the passage came from the
    # id the finding stated" from "the passage came from a unit_id the agent
    # wrote that did not match anything, resolved by finding that same string
    # written inside exactly one unit's own text instead." Absent entirely on
    # a direct hit or a genuine miss, never a blank/null placeholder field.
    if repaired_unit_id:
        amendment["unit_id_repaired_to"] = repaired_unit_id
    if item.get("source_rule_id"):
        amendment["source_convention_ref"] = item["source_rule_id"]
    # refine R2: the one thing the arithmetic genuinely cannot produce. Python can
    # say a figure is outside its band; it cannot say what the corrected line
    # should read. Where an optional polish pass supplied that, it is carried;
    # where it did not, the amendment stays a flag with no proposed text, exactly
    # as it always was. `action` is untouched either way: proposing wording is not
    # the same as deciding the change is safe to make.
    proposed = item.get("proposed_text")
    if isinstance(proposed, str) and proposed.strip():
        amendment["proposed_text"] = proposed.strip()
    return amendment


# refine R2: the two fields, and the ONLY two fields, an optional model polish pass
# may write onto a Finding record. Everything else about an amendment (its rule id,
# its location, its refs, its figures) is computed and is not the model's to touch.
# This is enforced by construction in apply_polish rather than checked afterwards:
# the model's output never becomes an amendment, it only ever supplies these two
# values to a record Python already built.
POLISHABLE_FIELDS = ("explanation", "proposed_text")


def apply_polish(item, polished):
    """Merge a polish pass's two fields into a Finding record. Returns a new item.

    Anything else the model returned is DISCARDED here, not validated and rejected
    later, which is the difference between a guard and a design: a model that
    cannot write a field cannot get a field wrong. An empty or missing value
    leaves the record exactly as it was, so a failed or silent call degrades to
    the deterministic template rather than to nothing.
    """
    if not isinstance(item, dict):
        return item
    if not isinstance(polished, dict):
        return dict(item)
    out = dict(item)
    for field in POLISHABLE_FIELDS:
        value = polished.get(field)
        if isinstance(value, str) and value.strip():
            out[field] = value.strip()
    return out


def _computed_sentence(item):
    """The one sentence that must carry the figures, whatever any model wrote.

    refine R2: relation-aware, because "against a stated 3.4" is the wrong phrase
    for a band bound and the right phrase for a stated total, and the reader
    checking the review against their own rulebook needs the figures either way."""
    a, b = item.get("value_a"), item.get("value_b")
    unit_a = item.get("unit_a") or ""
    unit_b = item.get("unit_b") or ""
    relation = str(item.get("relation") or "")
    if a is None:
        return "A required value is absent."
    if b is None:
        return "The computed value is %s %s." % (a, unit_a)
    if relation == "above_band":
        return ("The computed value is %s %s, above the reference bound of %s %s."
                % (a, unit_a, b, unit_b))
    if relation == "below_band":
        return ("The computed value is %s %s, below the reference bound of %s %s."
                % (a, unit_a, b, unit_b))
    return ("The computed value is %s %s against a stated %s %s."
            % (a, unit_a, b, unit_b))


def ensure_amendments_for_findings(amendments, findings, *, document_level="document-level",
                                   unit_texts=None):
    """Add an amendment for every irregular Finding not already represented.

    unit_texts: passed straight through to amendment_from_finding (see its own
    docstring): the {unit_id: {"text": ...}} map the caller already built once
    per document from unit_texts_for(doc["text"], doc["id"]), so a computed
    amendment's original_text is the document's actual passage, not its unit
    id. Optional, defaults to None (amendment_from_finding's own fallback),
    for any caller not yet passing it.

    Returns (amendments, added). An amendment the model wrote is never replaced;
    this only fills gaps, so a working drafter is unaffected and a failed one no
    longer costs the run its findings.
    """
    out = list(amendments or [])
    covered = set()
    for a in out:
        if isinstance(a, dict):
            covered.add((str(a.get("finding_unit_id") or a.get("original_text") or ""),
                         str(a.get("convention_ref") or "")))
    added = 0
    for item in findings or []:
        if not finding_record.is_finding(item):
            continue
        if str(item.get("record_verdict") or "").lower() != "irregular":
            continue
        key = (str(item.get("unit_id") or ""), str(item.get("rule_id") or ""))
        if key in covered:
            continue
        built = amendment_from_finding(item, document_level=document_level, unit_texts=unit_texts)
        if built is None:
            continue
        out.append(built)
        covered.add(key)
        added += 1
    return out, added


def suppress_contradicted_amendments(amendments, unit_texts, rules_by_id, vocabulary):
    """Drop a model-authored amendment that the arithmetic has already refuted.

    The control run is why this exists. On a document with nothing wrong in it,
    paired review computed zero findings and made zero calls, and AMENDMENT_DRAFTER
    then wrote an amendment claiming the parcel areas did not sum. Python had
    computed that exact sum on that exact unit and found it correct. One invented
    finding on a clean document is the number the answer key says decides whether
    the system is usable.

    The rule is narrow on purpose. An amendment is refused ONLY when all three hold:
    it was not derived from a computed finding, Python actually computed a check for
    its (unit, rule) pair, and every such check AGREED. A claim about something the
    arithmetic cannot decide is untouched, because the model is still the only thing
    that can read a band out of a corpus passage.

    Returns (kept, refused). Each refused amendment is returned with the reason, so
    it is refused loudly rather than vanishing.
    """
    kept, refused = [], []
    for amendment in amendments or []:
        if not isinstance(amendment, dict):
            kept.append(amendment)
            continue
        if amendment.get("derived_from") == "computed_finding":
            kept.append(amendment)
            continue
        unit_id = str(amendment.get("finding_unit_id") or amendment.get("original_text") or "")
        rule_id = str(amendment.get("convention_ref") or "")
        unit = unit_texts.get(unit_id)
        rule = rules_by_id.get(rule_id)
        if unit is None or rule is None:
            kept.append(amendment)
            continue
        scalars, columns, row_counts = extract_fields(unit.get("text", ""))
        present = pairing_map.unit_fields(unit.get("text", ""))
        needed = pairing_map.needed_fields(rule.get("rule", ""), vocabulary)
        checks = compute_checks(scalars, columns, rule_text=rule.get("rule", ""),
                                row_counts=row_counts, needed=needed,
                                present_labels=present)
        # compute_checks returns the unit's sum and product checks whatever the
        # rule is, because those do not depend on it. So a band rule looked
        # "decided" by arithmetic about a completely different field. Only a check
        # whose stated field is one THIS rule names counts as this rule's evidence.
        relevant = [c for c in checks
                    if pairing_map._norm_label(c.get("stated_field") or "") in needed]
        if not relevant:
            kept.append(amendment)          # arithmetic has no opinion on this rule
            continue
        if disagreements(relevant):
            kept.append(amendment)          # arithmetic agrees there is a problem
            continue
        checks = relevant
        refused.append((amendment,
                        "the arithmetic computed %d check(s) for %s on %s and every one "
                        "agreed" % (len(checks), rule_id, unit_id)))
    return kept, refused


def unit_texts_for(document_text, document_id=""):
    """The unit map suppress_contradicted_amendments needs, keyed by unit id."""
    return {u["unit_id"]: u for u in pairing_map.split_units(document_text,
                                                             document_id=document_id)}
