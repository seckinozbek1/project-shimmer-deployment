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

# Job C: an ISO date, optionally with a time, exactly as the document writes one
# ("2026-06-01" or "2026-06-01 09:00" or "...09:00:00"). Nothing looser: a
# calendar written any other way (a month name, a slash-separated date, an
# ordinal) is not matched, so a document that states a date differently gets
# no duration check rather than a misread one. The two rules this job answers
# (a fault window, a service interval) both compare a gap in hours or days,
# never in minutes or seconds, so seconds are accepted but not required and
# never read.
_ISO_DATETIME = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?\b")


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
# Job C: a gap between two timestamps, computed in Python, never guessed at.
#
# Two of the device rules ("acknowledged within the standard fault window",
# "must not exceed the standard service interval") say "state the two
# timestamps and the gap between them", which is an instruction to compute,
# not to judge, but nothing in this pipeline subtracted two dates before this.
# The shape is read structurally, the same discipline reference_tables.py
# already holds for a range: a label line's own words are what connect it to
# the rule, never a hardcoded word like "last" or "next", and more than the
# expected count of dates in play is refused rather than picked from.


def _parse_iso_datetime(token):
    """One ISO date, optionally timed, as a (datetime, has_time) pair, or None.

    Refuses rather than guesses: a token with no match, or a malformed one
    (day 32, month 13) that datetime itself rejects, yields None. Never reads
    a second candidate out of a longer string; the caller decides how many
    dates a piece of text may hold."""
    import datetime as _dt
    m = _ISO_DATETIME.fullmatch(token.strip())
    if not m:
        return None
    year, month, day, hour, minute, second = m.groups()
    try:
        if hour is not None:
            return (_dt.datetime(int(year), int(month), int(day), int(hour),
                                 int(minute), int(second or 0)), True)
        return (_dt.datetime(int(year), int(month), int(day)), False)
    except ValueError:
        return None


def _label_lines_with_dates(unit_text):
    """Every `label: value` line whose value is EXACTLY one or EXACTLY two ISO
    datetimes, as ((label_words, described_words), [datetime, ...], has_time).
    A value carrying any other number of dates, or a date alongside other
    non-date text this function cannot separate cleanly, is not returned:
    ambiguous material yields no candidate rather than a guessed one.

    The two word-sets are the two INDEPENDENT routes by which a rule can name
    this pair, kept apart rather than unioned (see the end of this docstring),
    and the way described_words is drawn is the whole point of this function.

    The words are taken PER DATE, from the window of text running from the
    previous date (or the start of the value) up to this date, and for a
    two-date line only the INTERSECTION of the two windows is kept. A word
    that describes what the pair IS appears beside both dates; a word that
    distinguishes one date FROM the other appears beside only one. On the
    device corpus's own service record, "Service record: last calibration
    visit <date>, next calibration visit logged <date>", the windows are
    {last, calibration, visit} and {next, calibration, visit, logged}, and
    the intersection is {calibration, visit}: exactly the concept the rule
    names, with the ordinal markers "last" and "next" excluded because they
    are how the document tells its two dates apart, not what the rule is
    about.

    This replaces taking the whole post-date remainder as one undifferentiated
    bag, which was noise collection rather than matching: it dragged "last",
    "next" and "record" in as though the rule had stated them, and no rule
    ever would, so the pair could never be named however the tokeniser was
    tuned. The narrowing is structural, by position relative to the figures,
    and carries no word list: nothing here knows that "last" is an ordinal,
    only that it sits beside one date and not the other.

    A ONE-date line keeps its whole window, since there is no second window
    to intersect with and the remainder genuinely describes that one date
    (the device corpus's "Fault logged: <date>" lines, whose own labels
    already carry the vocabulary, are unaffected either way)."""
    import pairing_map as _pm
    out = []
    for line in (unit_text or "").splitlines():
        m = _LABEL_LINE.match(line)
        if not m:
            continue
        label = _pm._norm_label(m.group(1))
        if not label:
            continue
        value = m.group(2).strip()
        matches = list(_ISO_DATETIME.finditer(value))
        if not matches or len(matches) > 2:
            continue
        parsed = []
        ok = True
        for mm in matches:
            got = _parse_iso_datetime(mm.group(0))
            if got is None:
                ok = False
                break
            parsed.append(got)
        if not ok or len(parsed) != len(matches):
            continue
        # One window per date: from the end of the previous date (or the
        # start of the value) to the start of this one.
        windows = []
        cursor = 0
        for mm in matches:
            windows.append(set(_pm._norm_label(value[cursor:mm.start()])))
            cursor = mm.end()
        described = set.intersection(*windows) if len(windows) > 1 else windows[0]
        # Two INDEPENDENT routes to naming this pair, kept apart rather than
        # unioned: the line's own label, and the words the value uses to
        # describe its dates. A rule that names either has named the pair.
        # Unioning them required a rule to state BOTH, which the device
        # corpus's own D05 never does: its label is "Service record" and the
        # rule says "service interval", so "record" alone blocked a pair
        # whose description ("calibration visit") the rule states outright.
        out.append(((set(label), described),
                    [p[0] for p in parsed], all(p[1] for p in parsed)))
    return out


def date_pair_for_rule(unit_text, rule_text):
    """(earlier, earlier_label, later, later_label, has_time) for the ONE date
    pair this rule's own words connect to in this unit, or None.

    Two shapes, tried in order, EXACTLY one of which may match:

      - ONE label line whose value holds two dates (UNIT-VETCH's "Service
        record: last calibration visit 2026-01-01, next calibration visit
        logged 2026-06-01"): its connecting words (the label's own words
        UNIONED with the value's own words, dates removed, so "calibration
        visit" reaches the test even when the outer label "Service record"
        does not share the rule's vocabulary) must be named by the rule,
        word containment, and the two dates are read in the order the
        document writes them.
      - TWO SEPARATE label lines, each holding one date, whose connecting
        words together satisfy the rule (UNIT-TEASEL's "Fault logged:" /
        "Fault acknowledged:"): both must be named by the rule, and exactly
        two such single-date lines may be named, or the pair is refused as
        ambiguous (which one goes with the rule is not decidable by field
        matching alone once a third candidate exists).

    A date the value line cannot resolve to a single unambiguous datetime, a
    unit with no date-bearing line the rule names, or a unit where the rule
    names three or more single-date lines all yield None: refuse rather than
    pick one. The gap is never assumed to run forward; a pair where the
    second date precedes the first is still returned (compute_checks reads
    the gap as an absolute duration, never a signed one, since which entry
    the document lists first is not a claim about order)."""
    import pairing_map as _pm

    candidates = _label_lines_with_dates(unit_text)
    if not candidates:
        return None
    # The rule's own words, read by pairing_map._norm_label: the SAME
    # function needed_fields and _label_lines_with_dates' own connecting
    # words already go through. This used to be a second, independent raw
    # split, disagreeing with _norm_label on the exact axis that mattered:
    # the device corpus's own D05 rule says "logged calibration visits" and
    # the document's value line says "calibration visit", and only a split
    # that folds the plural on BOTH sides can ever equate the two.
    rule_words = set(_pm._norm_label(rule_text or ""))

    def _named(routes):
        """The rule names this pair when it names EITHER route: the line's own
        label, or the words the value uses to describe its dates. Either on
        its own is a complete naming; requiring both meant a rule had to
        restate the document's wrapper label as well as its subject."""
        label_words, described = routes
        return ((bool(label_words) and label_words <= rule_words)
                or (bool(described) and described <= rule_words))

    def _display(routes):
        """The human-readable field name for a matched line: its own label
        where it has one, else the words describing its dates."""
        label_words, described = routes
        return " ".join(label_words or described)

    two_date_lines = [(routes, dts, has_time) for routes, dts, has_time in candidates
                      if len(dts) == 2 and _named(routes)]
    one_date_lines = [(routes, dts[0], has_time) for routes, dts, has_time in candidates
                      if len(dts) == 1 and _named(routes)]

    if two_date_lines and one_date_lines:
        return None  # both shapes matched: ambiguous, refuse rather than pick
    if len(two_date_lines) > 1:
        return None  # more than one same-line pair the rule names: ambiguous
    if two_date_lines:
        routes, (d1, d2), has_time = two_date_lines[0]
        name = _display(routes)
        return (d1, name + " (first)", d2, name + " (second)", has_time)
    if len(one_date_lines) == 2:
        (r1, d1, t1), (r2, d2, t2) = one_date_lines
        return (d1, _display(r1), d2, _display(r2), t1 and t2)
    return None  # zero, or three-or-more, single-date lines the rule names


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
                   vocabulary=None, unit_labels=None, unit_text="",
                   duration_bound=None):
    """Every comparison the figures themselves support. The model computes nothing.

    Four families, each proposed mechanically:
      sum_mismatch      a column summed against the scalar whose label contains the
                        column's label words
      product_mismatch  a scalar against the product of two fields whose units
                        multiply to the scalar's unit
      ratio_out_of_range / above_band / below_band
                        a ratio of two fields against bounds the RULE ITSELF states
      date_window       (Job C) the gap between two timestamps this unit states,
                        against a bound read from the reference corpus's own
                        prose, when the rule names a date pair AND a bound is
                        supplied (duration_bound); no duration is computed
                        without both, and neither is guessed at
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

    # Job C: two of the device rules say "state the two timestamps and the
    # gap between them", an instruction to compute, not to judge. The rule
    # must both connect to a date pair this unit states (date_pair_for_rule,
    # refusing rather than guessing on any ambiguity) AND have a bound the
    # caller found in the reference corpus's own prose (duration_bound,
    # reference_tables.scalar_bound_from_entries, computed once per rule by
    # the caller the same way reference_bands already is): with only one of
    # the two, nothing is computed and the pair still gets its call, the same
    # honest outcome bounds_from_rule already gives a rule with no bound.
    if duration_bound is not None and unit_text:
        pair = date_pair_for_rule(unit_text, rule_text)
        if pair is not None:
            earlier, earlier_label, later, later_label, has_time = pair
            bound_value, bound_unit, bound_ref = duration_bound
            gap_seconds = abs((later - earlier).total_seconds())
            gap_by_unit = {"hours": gap_seconds / 3600.0, "days": gap_seconds / 86400.0}
            # The gap unit must match the bound's own unit exactly (hours or
            # days, the only two either device rule states); a bound in a
            # unit this reader does not recognise computes nothing rather
            # than converting through an assumed calendar.
            if bound_unit in gap_by_unit:
                gap = gap_by_unit[bound_unit]
                agrees = gap <= bound_value or _close(gap, bound_value)
                checks.append({
                    "relation": "date_window",
                    "computed": round(gap, 6), "computed_unit": bound_unit,
                    "stated": bound_value, "stated_unit": bound_unit,
                    "agrees": agrees,
                    "basis": "%s to %s, %s in the reference corpus" % (
                        earlier_label, later_label,
                        ("a %s gap" % bound_unit)),
                    "stated_field": earlier_label,
                    "ref_id": bound_ref,
                })
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


def adjacent_units(unit, unit_texts):
    """The unit immediately before and after `unit`, by index, or None for either.

    docs/api/UNIT_CONTEXT_DESIGN.md, option B: the narrowest addition that can
    catch a provision that is only wrong, or only sound, beside its neighbor,
    without giving back wide mode's whole-document framing. `unit_texts` is
    whatever map the caller already built (pipeline.py's unit_text, keyed by
    unit_id, every value carrying "index" since the order fix). This function
    does not care about the map's keys, only its values' own "index" field:
    it scans for the two values whose index is exactly one less and one more
    than `unit`'s own, so it works identically whether the caller's dict
    happens to be keyed by unit_id, by index, or by anything else.

    A unit missing "index" (a caller on the old, pre-fix shape, or a
    hand-built fixture that never set it) returns (None, None) for both
    rather than guessing from list position: this function has exactly one
    source of truth for adjacency, index, and no fallback that could point at
    the wrong unit while looking like it worked.
    """
    idx = unit.get("index")
    if idx is None:
        return None, None
    prev_unit = next((u for u in (unit_texts or {}).values()
                      if isinstance(u, dict) and u.get("index") == idx - 1), None)
    next_unit = next((u for u in (unit_texts or {}).values()
                      if isinstance(u, dict) and u.get("index") == idx + 1), None)
    return prev_unit, next_unit


def build_pair_payload(*, unit, rule, checks, refs=None, source_rule_id="",
                       unit_texts=None, document_units=None, qualifying_rules=None):
    """The work payload for one (unit, rule) pair.

    Carries the computed values and NOT the arithmetic. The model is asked whether
    the discrepancy is material and how to state it for a reader; it is never asked
    what the figures add up to, because H1 measured that it cannot do it.

    unit_texts (docs/api/UNIT_CONTEXT_DESIGN.md, option B): when given, the
    immediately preceding and following unit's own text is attached under
    NEW, SEPARATELY NAMED fields (preceding_unit_text/following_unit_text),
    never merged into document_text. This is the operator's own requirement,
    proven here rather than asserted: a model reading this payload can tell
    the unit it is judging from its neighbors by FIELD NAME ALONE, before
    reading a single word of content, because "document_text" (what is being
    judged, unchanged, still exactly one unit's own text, this function's
    contract to every existing caller is unbroken) and
    "preceding_unit_text"/"following_unit_text" (what surrounds it) are
    different keys carrying different, non-overlapping strings; a payload
    dict has no way to let two fields collide into one, so this separation
    holds by construction, not by convention. neighbor_note states in words
    what the field names already state in structure: read the neighbors for
    whether they bear on this unit, do not judge the neighbors themselves,
    do not cite them as the passage under review. Absent when unit_texts is
    not given (every existing caller of this function before today), so the
    contract change is additive: a caller that does not opt in sees no new
    fields at all, not empty ones.

    document_units (docs/api/UNIT_CONTEXT_DESIGN.md, option D, already built
    into the wide-mode payload at pipeline.py's document_units block, reused
    here rather than duplicated): the ordered id/title list for the whole
    document, when given, under "document_map", with structure_note stating
    plainly it is orientation, not evidence: titles only, no unit's own text,
    nothing here answers what a neighbor SAYS, only where it sits.
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
        # A rule this one is suspended by, carried WITH it. A model asked about
        # an exception in isolation from the rule it qualifies gives the wrong
        # answer however well it reads, so when this rule declares
        # [unless: CONV-X] the text of CONV-X travels in the same payload. Empty
        # for the ordinary case, so a pair with no qualifying rule is unchanged.
        "qualified_by": [
            {"rule_id": q.get("id"), "rule_text": q.get("rule", ""),
             "source_rule_id": q.get("category")}
            for q in (qualifying_rules or []) if q],
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
    if unit_texts is not None:
        prev_unit, next_unit = adjacent_units(unit, unit_texts)
        if prev_unit is not None:
            payload["preceding_unit_text"] = prev_unit.get("text", "")
        if next_unit is not None:
            payload["following_unit_text"] = next_unit.get("text", "")
        if prev_unit is not None or next_unit is not None:
            payload["neighbor_note"] = (
                "preceding_unit_text and following_unit_text, when present, are the "
                "units immediately before and after the one you are judging (document_text "
                "above), given so you can tell whether either one changes what this unit "
                "means, for example because one creates an exception the other's own text "
                "does not state, or because one contradicts what this unit states. They "
                "are context, not evidence: do not evaluate them against the rule, do not "
                "cite them as the passage under review, and do not treat anything they say "
                "as this unit's own statement. Your evaluation is still about document_text "
                "alone, against rule_text alone."
            )
    if document_units:
        payload["document_map"] = [
            {"unit_id": u.get("unit_id"), "title": u.get("title", "")}
            for u in document_units
        ]
        payload["structure_note"] = (
            "document_map lists every unit in this document, in order, by id and title "
            "only: no unit's own text is in it. It is orientation, not evidence, for "
            "seeing where the unit you are judging sits in the document's overall shape. "
            "Do not treat it as a summary of what any unit says, and do not cite it as a "
            "source: it names units, it does not describe their content."
        )
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


def _absence_check(label):
    """The computed check for a declared required field a unit in scope lacks
    (D, option 2). Same shape as compute_checks' own missing_field check, so
    finding_from_check mints it the same way: Python's 0 of 1 required."""
    return {"relation": "missing_field", "computed": 0, "computed_unit": "values",
            "stated": 1, "stated_unit": "required", "agrees": False,
            "basis": "the rule declares %s required and this unit does not carry it" % " ".join(label),
            "stated_field": " ".join(label)}


def refuses_judged_absence(item, rule, fields_present):
    """True when a judged item claims a field is MISSING from a unit that
    Python has already parsed as carrying it.

    Where Python can settle it, Python settles it: the same discipline that
    already makes the arithmetic outrank the model, applied to the one claim a
    judged-absence call can make that Python can disprove outright.

    A judged-absence call asks the model whether a scoped rule's requirement
    applies to one unit and is met, because the rule declares no required field
    and the condition has to be read from its text. The unit is in scope
    BECAUSE it carries the field the scope declares. So a missing_field verdict
    on such a unit contradicts the very fact that put it in scope: the unit
    could not have been paired at all if the field were absent.

    THREE refusals, and the first two are about FORM, not truth.

    0. A missing_field claim with NO QUOTE is refused. An absence claim is the
       one claim the document itself can refute, and the one the model invents
       most; a quote is what makes it checkable at all. Required here, at the
       point of judging, and deliberately NOT in the contract's "required" list:
       putting it there would mark every finding of every past run a violation,
       including the 62 published on 2026-09-11. A contract applies from the
       commit that introduces it.

    1. A missing_field claim that names NO field is refused as malformed. Not
       because Python disproves it, but because it is not checkable: nothing
       can confirm it, cite it, or score it, and the operator's own D07-shaped
       rule already requires a finding to state the entry and the figures it
       concerns. This is the discipline the verifiability gate applies when it
       downgrades an affirmative finding that cites nothing. A model that spots
       a real absence and does not say which field is refused too: naming the
       field is the minimum for the claim to exist as a claim.

    2. A claim that DOES name a field is refused when the unit demonstrably
       carries that field, which Python has already parsed into fields_present.

    Inference about WHICH field an unnamed claim means is deliberately not
    attempted. Two such heuristics were tried and both suppressed a legitimate
    answer in gate check 209's fixture, whose rule is scoped on `device` and
    says "a device entry states a fault only when the fault window in the
    glossary allows it": a missing_field answer there is about the fault, not
    the device label. A third heuristic would have been a guess dressed as a
    rule.

    Measured on the clean twin (2026-09-12, run 479f3219): 9 of the 11 false
    positives were judged absences and ALL NINE named no field, while seven of
    them asserted a calibration authority signature missing from entries whose
    own parsed fields list it. On the flawed twin the same refusal removes the
    SPRUCE and VETCH items, which the scorer had counted as catches: the model
    emits a near-identical wrong sentence on both twins (on VETCH, that the
    document "does not mention the next calibration visit" when the entry
    states it in plain words), so those were coincidences that scored, not
    detections. Long-range recall falls 3/3 to 1/3 and the clean twin's false
    positives fall 11 to 2. Both numbers are reported as they are.

    Structural and domain-free: it knows no field name of its own, reads the
    rule's own scope declaration and the unit's own parsed labels through the
    one shared tokeniser, and touches only the missing_field relation."""
    if not isinstance(item, dict):
        return False
    if str(item.get("relation") or "") != "missing_field":
        return False
    if not str(item.get("quote") or "").strip():
        # An ABSENCE claim must show the words it rests on. This is the one
        # relation where the model invents most, and the one a quote can
        # actually check: the document itself refutes a false absence. A claim
        # with no quote cannot be checked against the text at all, so it is
        # refused for the same reason a claim naming no field is.
        #
        # FORWARD ONLY, and deliberately so: the requirement lives here, at the
        # point a reply is judged, and not in the contract's `required` list.
        # Putting it in `required` would mark every finding of every past run a
        # contract violation, including 62 already published on 2026-09-11.
        # A contract applies from the commit that introduces it.
        return True
    stated = item.get("stated_field") or item.get("field_label")
    claimed = pairing_map._norm_label(stated) if stated else ()
    if not claimed:
        # Names no field: not checkable, so not a finding.
        return True
    # Names a field: refuse only if the unit carries that very field.
    have = {pairing_map._norm_label(label) for label in (fields_present or [])}
    return claimed in have


def _squash(text):
    """Whitespace-folded, lowercased text, for comparing a quote against a unit
    without being defeated by a line break or a doubled space."""
    return " ".join(str(text or "").split()).lower()


def quote_not_in_unit(item, unit_text):
    """True when a finding quotes words that do NOT appear in the unit it is about.

    The claim a model makes about ABSENCE is the one claim it can make that the
    document itself refutes, and until now nothing checked it. Measured on the
    2026-09-11 clean twin: the model asserted that the document "does not
    mention the next calibration visit" for UNIT-VETCH, whose entry reads
    "Service record: last calibration visit 2026-01-01, next calibration visit
    logged 2026-03-15". It said the same thing, almost word for word, about the
    flawed twin. Nothing caught it, because the claim was checked for shape and
    never against the text.

    The contract now asks for a `quote`: the exact words the finding rests on,
    copied from the unit text the model was shown (that same text is sent to it
    as `document_text`). This compares the quote against the unit, folding
    whitespace and case so a line break cannot defeat it, and nothing else: no
    model, no embedding, no second call.

    Deliberately narrow. A finding with NO quote is not refused here, because
    the field is optional in the contract and most relations are settled by
    arithmetic that needs no quote; requiring one everywhere would turn every
    existing finding into a violation, which is not a measurement, it is a
    migration. Only a quote that is present AND absent from the unit is refused,
    which is the case the model can get wrong and Python can prove."""
    if not isinstance(item, dict):
        return False
    quote = item.get("quote")
    if not quote or not str(quote).strip():
        return False
    if not str(unit_text or "").strip():
        # No text to check against: unanswerable, so never a refusal.
        return False
    return _squash(quote) not in _squash(unit_text)


def absence_plans(unit, rule_ids, rules_by_id, present, *, required_fields_for=None):
    """D, option 2, Python first: for every rule paired on this unit that declares
    a scope, a plan per declared required field the unit does not carry
    (kind absence_computed, no call: Python decides), and for a scoped rule that
    declares NO required field, one narrow question for the model on this unit
    alone (kind absence_judged), since the requirement's condition then has to be
    read from the rule's text. A scoped rule's text-named fields are never
    requirements. Returns (plans, scoped rule ids)."""
    required_fields_for = required_fields_for or pairing_map.required_declaration
    plans, scoped = [], []
    for rule_id in rule_ids:
        rule = rules_by_id.get(rule_id)
        if not rule or not pairing_map.scope_declaration(rule):
            continue
        scoped.append(rule_id)
        required = required_fields_for(rule)
        if required:
            for label in sorted(required):
                if label not in present:
                    plans.append({"unit": unit, "rule": rule, "checks": [_absence_check(label)],
                                  "kind": "absence_computed"})
        else:
            plans.append({"unit": unit, "rule": rule, "checks": [], "kind": "absence_judged"})
    return plans, scoped


DURATION_RELATIONS = ("date_window",)


def plan_calls(units_by_id, pairs, rules_by_id, vocabulary, *, needed_fields_for=None,
               reference_bands_for=None, known_units=None, required_fields_for=None,
               duration_bound_for=None):
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
        # D, option 2: declared absences first (Python decides, or the model is
        # asked on this unit alone); a scoped rule contributes nothing to the
        # text-derived needed set, so a glossary label its text mentions is never
        # a requirement of an entry.
        declared, scoped_rule_ids = absence_plans(unit, rule_ids, rules_by_id, present,
                                                  required_fields_for=required_fields_for)
        plans.extend(declared)
        needed_union = set()
        for rule_id in rule_ids:
            rule = rules_by_id.get(rule_id)
            if rule and rule_id not in scoped_rule_ids:
                needed_union |= needed_fields_for(rule.get("rule", ""))

        # Rule-independent: computed once for the unit. date_window is excluded
        # for the same reason BAND_RELATIONS is: it depends on a specific
        # rule's own text (which date pair it names) and a duration_bound this
        # call was not given, so it is never actually produced here (an empty
        # rule_text names nothing, and duration_bound defaults to None), but
        # the exclusion is made explicit rather than relying on that silently.
        shared = [c for c in compute_checks(scalars, columns, rule_text="",
                                            row_counts=row_counts, needed=needed_union,
                                            present_labels=present)
                  if c["relation"] not in BAND_RELATIONS
                  and c["relation"] not in DURATION_RELATIONS]
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
        # the reference corpus that the rule points at, or (Job C) a duration
        # bound lives in the reference corpus's own prose, so each is computed
        # per rule. settled_rule_ids tracks every rule this loop reached a
        # verdict for, agreeing or not: an AGREEING band or duration (a value
        # in range, a gap inside its window) is still Python having answered
        # the question, and must not fall through to the uncomputable check
        # below, which cannot see either bound (both are external to the
        # rule's own text: a reference-table row and a reference-corpus
        # sentence, neither reachable from compute_checks(rule_text=...)
        # alone). Found while proving Job C: an out-of-range table band
        # DISAGREES and used to double-book (a correct "band" plan plus a
        # spurious "uncomputable" one asking the model the same question a
        # second time), a pre-existing defect in the R1 mechanism this
        # tracking now also closes, not only Job C's own new duration path.
        settled_rule_ids = set()
        for rule_id in rule_ids:
            rule = rules_by_id.get(rule_id)
            if not rule:
                continue
            bands = (reference_bands_for(unit.get("text", ""), rule)
                     if reference_bands_for else ())
            duration_bound = (duration_bound_for(rule) if duration_bound_for else None)
            rule_checks = compute_checks(scalars, columns,
                                         rule_text=rule.get("rule", ""),
                                         row_counts=row_counts,
                                         # R6: the band branch needs to know which
                                         # fields THIS rule names, or a stated band
                                         # is applied to every same-unit figure in
                                         # the unit. Only BAND_RELATIONS and
                                         # DURATION_RELATIONS are kept below, so the
                                         # missing_field checks this now also
                                         # computes are discarded here and still
                                         # come from the shared pass above.
                                         needed=needed_fields_for(rule.get("rule", "")),
                                         present_labels=present,
                                         reference_bands=bands,
                                         vocabulary=vocabulary,
                                         unit_labels=present,
                                         unit_text=unit.get("text", ""),
                                         duration_bound=duration_bound)
            band = [c for c in rule_checks if c["relation"] in BAND_RELATIONS]
            if band:
                settled_rule_ids.add(rule_id)
            for check in disagreements(band):
                plans.append({"unit": unit, "rule": rule, "checks": [check],
                              "kind": "band"})
            duration = [c for c in rule_checks if c["relation"] in DURATION_RELATIONS]
            if duration:
                settled_rule_ids.add(rule_id)
            for check in disagreements(duration):
                plans.append({"unit": unit, "rule": rule, "checks": [check],
                              "kind": "duration"})

        # A rule that is BOTH scoped (absence_plans already declared its
        # absence_judged plan, unconditionally, before this loop ran) AND
        # settled here by a band or duration verdict: the Python-computed
        # answer is strictly better (it costs no call and cites real
        # figures, where absence_judged asks the model a now-redundant
        # generic question), so the declared absence_judged plan for this
        # (unit, rule) is dropped in favor of it. Found alongside the
        # pre-existing R1 double-booking this fix already closes for the
        # unscoped case: not yet observed on the device corpus (D04's and
        # D05's duration checks do not currently succeed there), but latent
        # the moment either rule's wording gap closes, so it is closed here
        # rather than shipped half-fixed. A scoped rule's absence_computed
        # plans (a declared required field genuinely missing) are never
        # touched: that is Python having already decided a different,
        # narrower question this loop does not re-ask.
        for rule_id in set(scoped_rule_ids) & settled_rule_ids:
            plans = [p for p in plans
                    if not (p["unit"] is unit and p["rule"].get("id") == rule_id
                            and p["kind"] == "absence_judged")]

        # A pair where nothing at all could be computed still needs the model, on
        # the text, for one unit against one rule.
        if not shared:
            for rule_id in rule_ids:
                rule = rules_by_id.get(rule_id)
                if rule is None or rule_id in scoped_rule_ids:
                    continue  # a scoped rule's question was planned above
                if rule_id in settled_rule_ids:
                    continue  # a band or duration verdict was planned above
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
    # finding_record.resolved_rule_id reads whichever of the four names a real
    # agent contract actually uses (rule_id, procedure_id, conv_id,
    # convention_ref), not only the canonical rule_id. Found live: PRACTICE_
    # AUDITOR wrote 5 genuinely irregular findings under procedure_id, this
    # function required rule_id specifically, found none, returned None, and
    # every one of the 5 was silently dropped with no record it had existed.
    rule_id = finding_record.resolved_rule_id(item)
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
        # The TYPED record, carried through rather than dropped. finding_type
        # above is a coarse label ("factual"), not the Finding record's own
        # relation, so an amendment used to be the one artifact from which a
        # claim could be located but never checked: UNIT-VETCH scored as
        # "reason unverifiable" on 2026-09-11 for exactly this reason, because
        # it was reachable only through an amendment. The typed fields exist on
        # the item this amendment is built from; they are copied here, never
        # invented, and absent when the item carries none.
        "finding_relation": item.get("relation"),
        "finding_field_label": item.get("field_label"),
        "finding_value_a": item.get("value_a"),
        "finding_unit_a": item.get("unit_a"),
        "finding_value_b": item.get("value_b"),
        "finding_unit_b": item.get("unit_b"),
        # night W7 b: the agent whose Finding this amendment rests on, so the ontology's
        # provenance struct can name it. Absent when the item carries none; never invented.
        "agent": item.get("agent"),
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
                                   unit_texts=None, refusal_sink=None):
    """Add an amendment for every irregular Finding not already represented.

    unit_texts: passed straight through to amendment_from_finding (see its own
    docstring): the {unit_id: {"text": ...}} map the caller already built once
    per document from unit_texts_for(doc["text"], doc["id"]), so a computed
    amendment's original_text is the document's actual passage, not its unit
    id. Optional, defaults to None (amendment_from_finding's own fallback),
    for any caller not yet passing it.

    refusal_sink: optional, a list the caller supplies to be appended to (not
    the return value: changing this function's return SHAPE would break every
    existing 2-value-unpack caller, of which there are a dozen, most in the
    gate). Purely additive: None (the default, every caller before today) means
    no tracking, byte-identical behavior. When given, one dict is appended for
    every irregular Finding this function could NOT turn into an amendment,
    with the reason and the item itself, so a caller with bus access (pipeline.
    py) can post a visible refusal rather than the finding simply vanishing.
    Found live: PRACTICE_AUDITOR wrote 5 genuinely irregular findings tonight
    that amendment_from_finding could not build from (before the rule_id-alias
    fix above, none of them named their rule under the one field name this
    function required); every one was dropped with nothing on the bus, in the
    console, or anywhere else saying it had ever existed.

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
        resolved_rule = finding_record.resolved_rule_id(item)
        key = (str(item.get("unit_id") or ""), str(resolved_rule or ""))
        if key in covered:
            continue
        built = amendment_from_finding(item, document_level=document_level, unit_texts=unit_texts)
        if built is None:
            if refusal_sink is not None:
                reason = ("no rule id under any known field name "
                         "(rule_id/procedure_id/conv_id/convention_ref)") if not resolved_rule \
                    else "amendment_from_finding declined this finding"
                refusal_sink.append({"item": item, "reason": reason,
                                     "unit_id": item.get("unit_id"), "rule_id": resolved_rule})
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
