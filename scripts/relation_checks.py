"""RELATIONS-A: four relations Python computes from the document's own figures.

The Finding record could state a disagreement inside one unit (a sum, a product, a
band, a missing field) and nothing else, so four kinds of flaw had no record Python
could write: a figure that is not a stated percentage of another figure of its unit,
a figure written in another measure than the one its column or band uses, a figure
copied into one unit from another that differs from it, and a figure carried from
the unit before that differs from what that unit closed with. Measured, not
preferred: on the 27 L12 development entries (families f1 to f6) the parallel track's miss
diagnosis found 32 losses, 20 of them in these four kinds (rate and ratio 8, copy 4, carry
4, unit 4), as INFRA-045's reason states; the loop has not reproduced that count (D-198).
Constitution amendment INFRA-045 appends the four relations to the record.

Everything here is STRUCTURAL, like the rest of the paired review. No domain word, no
unit name and no language is named in this file:

  * A RATE (`rate_mismatch`) is three label-line figures of one unit: a part and a
    whole written in the same measure, and a proportion written in a dimensionless
    scale (the percent sign, from config/unit_conversions.json). The part must be the
    whole times the proportion. The rule decides whether it applies: it must name the
    proportion and one of the other two by the unit's own labels; the third is the one
    same-measure figure whose label shares most words with the rule, and a tie is
    refused. Which of the three the rule states as its subject is the one it names
    first; that figure is the one compared, against the value the other two give.
  * A UNIT MISMATCH (`unit_mismatch`) is a figure whose measure differs from the
    measure its column (the column whose label its own label contains, as a stated
    total) or its band (the rule's stated band, or the reference table's) uses, by a
    decimal prefix on the same base. The figure is converted and both are stated; a
    pair that cannot be converted is refused on the pairing map, never guessed.
  * A COPY (`copy_mismatch`) is a table row whose key cell is exactly the heading of
    another unit, in a column whose label is a label line of that unit: the row must
    carry that unit's figure. The rule must name the key column and the value column.
  * A CARRY (`carry_mismatch`) is the first row of a table column that the unit just
    before also carries, under the same first-row key: the first row must carry the
    sum of that column in the unit before. The rule must name the column and the first
    row's key. When the unit before does not add up on its own (its stated total and
    its column sum differ, or its column has a hole), which figure it carries is not
    decided by arithmetic, and the carry is refused.

Every refusal is a dict for the pairing map (`relation_refusals`): the unit, the rule,
the relation, a reason kind and the figures involved, never text from the document.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pairing_map

ROOT = Path(__file__).resolve().parent.parent
CONVERSIONS_PATH = ROOT / "config" / "unit_conversions.json"

RATE = "rate_mismatch"
UNIT = "unit_mismatch"
COPY = "copy_mismatch"
CARRY = "carry_mismatch"
# The four relations, in the order INFRA-045 appends them to the record.
RELATIONS = (RATE, CARRY, COPY, UNIT)
# The two that read another unit of the document.
CROSS_UNIT_RELATIONS = (COPY, CARRY)

# Reason kinds a refusal carries (the pairing map's `relation_refusals`).
RATE_THIRD_FIGURE_TIED = "rate_third_figure_tied"
RATE_THIRD_FIGURE_UNNAMED = "rate_third_figure_unnamed"
RATE_PART_WHOLE_UNDECIDED = "rate_part_whole_undecided"
RATE_TOO_MANY_FIGURES = "rate_too_many_figures"
UNIT_NOT_CONVERTIBLE = "unit_not_convertible"
COPY_SUBJECT_AMBIGUOUS = "copy_subject_ambiguous"
COPY_SOURCE_LACKS_FIELD = "copy_source_lacks_field"
COPY_MEASURE_DIFFERS = "copy_measure_differs"
CARRY_SOURCE_DOES_NOT_ADD_UP = "carry_source_does_not_add_up"
CARRY_SOURCE_INCOMPLETE = "carry_source_incomplete"
CARRY_MEASURE_DIFFERS = "carry_measure_differs"
# D-198: the figures fit another plain reading than a part as a proportion of a whole
# (the larger is the smaller plus or minus the proportion of it), so which arithmetic the
# rule states is not decided by the figures; refused, never read from the rule's words.
RATE_READING_AMBIGUOUS = "rate_reading_ambiguous"
# D-198 (open item 76): a unit mismatch is attributed to the one paired rule whose
# declared scope or requirement reads the figure's label or its measure; none, or more
# than one, is refused.
UNIT_RULE_UNDECLARED = "unit_rule_undeclared"
UNIT_RULE_AMBIGUOUS = "unit_rule_ambiguous"
REFUSAL_KINDS = (RATE_THIRD_FIGURE_TIED, RATE_THIRD_FIGURE_UNNAMED, RATE_PART_WHOLE_UNDECIDED,
                 RATE_TOO_MANY_FIGURES, UNIT_NOT_CONVERTIBLE, COPY_SUBJECT_AMBIGUOUS,
                 COPY_SOURCE_LACKS_FIELD, COPY_MEASURE_DIFFERS, CARRY_SOURCE_DOES_NOT_ADD_UP,
                 CARRY_SOURCE_INCOMPLETE, CARRY_MEASURE_DIFFERS, RATE_READING_AMBIGUOUS,
                 UNIT_RULE_UNDECLARED, UNIT_RULE_AMBIGUOUS)

_CONVERSIONS_CACHE = None
# A unit carrying an exponent the unit reader would drop (`m2`, `m^2`) is never
# converted: unit_exponents reads both as `m`, so a prefix factor would be wrong.
_EXPONENT_IN_UNIT = re.compile(r"[\d^²³]")


def conversions():
    """config/unit_conversions.json, read once. A missing or broken file converts
    nothing (every pair is then refused), never a built-in table."""
    global _CONVERSIONS_CACHE
    if _CONVERSIONS_CACHE is None:
        try:
            data = json.loads(CONVERSIONS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        prefixes = {str(k): float(v) for k, v in (data.get("prefixes") or {}).items()
                    if isinstance(v, (int, float)) and v > 0 and str(k)}
        scales = {str(k): float(v) for k, v in (data.get("dimensionless_scales") or {}).items()
                  if isinstance(v, (int, float)) and v > 0 and str(k)}
        # D-198: the bases a prefix may stand before; a token whose base is not
        # declared is never read as a prefix and a base.
        bases = {str(b) for b in (data.get("bases") or []) if isinstance(b, str) and b}
        _CONVERSIONS_CACHE = {"prefixes": prefixes, "scales": scales, "bases": bases}
    return _CONVERSIONS_CACHE


def _pr():
    import paired_review
    return paired_review


def _r6(x):
    return round(float(x), 6)


# ---------------------------------------------------------------------------
# measures


def scale_of(unit):
    """The size of a dimensionless scale symbol (0.01 for a percent), or None."""
    exps = _pr().unit_exponents(unit)
    if len(exps) != 1:
        return None
    (token, power), = exps.items()
    scale = conversions()["scales"].get(token)
    return scale if scale is not None and power == 1 else None


def _prefix_split(token):
    """Every (prefix, base) reading of a token over DECLARED bases only (D-198): the bare
    token when it is a declared base, and each declared prefix it starts with that
    leaves a declared base. Reading by letters alone converted `ha` to `a`, `dB` to `B`,
    `min` to `in` and `cd` to `d`."""
    bases = conversions()["bases"]
    out = [("", token)] if token in bases else []
    for prefix in conversions()["prefixes"]:
        rest = token[len(prefix):]
        if token.startswith(prefix) and rest and rest in bases:
            out.append((prefix, rest))
    return out


def conversion_factor(from_unit, to_unit):
    """f such that a figure in `from_unit` times f is the same figure in `to_unit`,
    or None. Only a decimal prefix on the same base converts; the tokens are the
    document's own. Identical measures are not a conversion (None), and a pairing
    of tokens that is not one-to-one is refused (None)."""
    if not from_unit or not to_unit:
        return None
    if _EXPONENT_IN_UNIT.search(str(from_unit)) or _EXPONENT_IN_UNIT.search(str(to_unit)):
        return None
    pr = _pr()
    a, b = dict(pr.unit_exponents(from_unit)), dict(pr.unit_exponents(to_unit))
    if not a or not b or a == b:
        return None
    scales = conversions()["scales"]
    if any(t in scales for t in list(a) + list(b)):
        return None
    for token in list(a):
        if token in b and a[token] == b[token]:
            del a[token]
            del b[token]
    if len(a) != len(b) or not a:
        return None
    prefixes = conversions()["prefixes"]
    factor = 1.0
    used = set()
    for ta, pa_power in a.items():
        matches = []
        for tb, pb_power in b.items():
            if tb in used or pb_power != pa_power:
                continue
            for pa, base_a in _prefix_split(ta):
                for pb, base_b in _prefix_split(tb):
                    if base_a == base_b and (pa or pb) and pa != pb:
                        matches.append((tb, pa, pb))
        if len({m[0] for m in matches}) != 1 or len(matches) != 1:
            return None
        tb, pa, pb = matches[0]
        used.add(tb)
        size_a = prefixes.get(pa, 1.0) if pa else 1.0
        size_b = prefixes.get(pb, 1.0) if pb else 1.0
        factor *= (size_a / size_b) ** pa_power
    return factor


def converted(value, from_unit, to_unit):
    """`value` in `to_unit`, rounded to 6 places, or None when it does not convert."""
    f = conversion_factor(from_unit, to_unit)
    return None if f is None else _r6(value * f)


# ---------------------------------------------------------------------------
# what a rule names


def named_labels(rule_text, labels):
    """{label: first word position} for every label of `labels` the rule names as
    itself: its words written together, in order, in the rule's own words (the one
    tokeniser, pairing_map._norm_label), at a place that is not inside the rule's
    naming of a longer label. "the freight share ... the freight" names both."""
    words = list(pairing_map._norm_label(rule_text or ""))
    spans = {}
    for label in labels:
        label = tuple(label)
        n = len(label)
        if not n:
            continue
        spans[label] = [(i, i + n) for i in range(len(words) - n + 1) if tuple(words[i:i + n]) == label]
    named = {}
    for label, occurrences in spans.items():
        for start, end in occurrences:
            inside = any(len(other) > len(label) and s <= start and end <= e
                         for other, occ in spans.items() if other != label for s, e in occ)
            if not inside:
                named[label] = start
                break
    return named


def _words(text):
    return set(pairing_map._norm_label(text or ""))


def _decimals_written(unit_text, label):
    """How many decimals the unit writes for the label line `label`, or None."""
    pr = _pr()
    for line in (unit_text or "").splitlines():
        m = pairing_map._LABEL_LINE.match(line)
        if not m or tuple(pairing_map._norm_label(m.group(1))) != tuple(label):
            continue
        q = pr._QUANTITY.search(m.group(2))
        if not q:
            return None
        num = q.group("num")
        tail = re.search(r"[.,](\d+)$", num.replace(" ", "").replace(" ", ""))
        if tail and not re.fullmatch(r"-?\d{1,3}(?:,\d{3})+", num):
            return len(tail.group(1))
        return 0
    return None


def _agrees_as_written(computed, stated, decimals):
    """The computed figure, read to the precision the stated one is written to, is
    the stated figure. Without a written precision, the arithmetic tolerance."""
    pr = _pr()
    if pr._close(computed, stated):
        return True
    if decimals is None:
        return False
    return abs(computed - stated) <= 0.5 * 10 ** (-decimals) + 1e-9


# ---------------------------------------------------------------------------
# rate_mismatch


def rate_checks(scalars, rule_text, *, unit_text="", unit_id="", rule_id="", refusals=None):
    """Every rate a rule states over three label-line figures of one unit."""
    pr = _pr()
    named = named_labels(rule_text, scalars)
    checks = []
    for rate_label in sorted(named, key=lambda lb: named[lb]):
        rate_value, rate_unit = scalars[rate_label]
        scale = scale_of(rate_unit)
        if scale is None:
            continue
        partners = {}
        for label in named:
            if label == rate_label or scale_of(scalars[label][1]) is not None:
                continue
            measure = pr._unit_str(pr.unit_exponents(scalars[label][1]))
            if measure:
                partners.setdefault(measure, []).append(label)
        for measure, group in sorted(partners.items()):
            if len(group) > 2:
                _refuse(refusals, unit_id, rule_id, RATE, RATE_TOO_MANY_FIGURES,
                        fields=[" ".join(lb) for lb in [rate_label] + sorted(group)])
                continue
            if len(group) == 1:
                others = [lb for lb in scalars if lb not in named
                          and pr._unit_str(pr.unit_exponents(scalars[lb][1])) == measure]
                rule_words = _words(rule_text)
                scored = sorted(((len(set(lb) & rule_words), lb) for lb in others), reverse=True)
                if not scored or scored[0][0] == 0:
                    if others:
                        _refuse(refusals, unit_id, rule_id, RATE, RATE_THIRD_FIGURE_UNNAMED,
                                fields=[" ".join(lb) for lb in [rate_label] + group])
                    continue
                third = unique_best(scored)
                if third is None:
                    _refuse(refusals, unit_id, rule_id, RATE, RATE_THIRD_FIGURE_TIED,
                            fields=[" ".join(lb) for lb in [rate_label] + group
                                    + [lb for s, lb in scored if s == scored[0][0]]])
                    continue
                pair = [group[0], third]
            else:
                pair = list(group)
            fraction = rate_value * scale
            (la, (va, _ua)), (lb, (vb, _ub)) = [(lb, scalars[lb]) for lb in pair]
            if abs(va) == abs(vb) or abs(fraction) == 1 or fraction == 0:
                _refuse(refusals, unit_id, rule_id, RATE, RATE_PART_WHOLE_UNDECIDED,
                        fields=[" ".join(rate_label), " ".join(la), " ".join(lb)])
                continue
            # The part is the whole times a fraction: smaller in size when the
            # fraction is, larger when it is not. Arithmetic, not a word.
            small, large = (la, lb) if abs(va) < abs(vb) else (lb, la)
            part, whole = (small, large) if abs(fraction) < 1 else (large, small)
            check = _rate_check(scalars, named, rate_label, part, whole, scale, unit_text=unit_text)
            if check is None:
                _refuse(refusals, unit_id, rule_id, RATE, RATE_PART_WHOLE_UNDECIDED,
                        fields=[" ".join(rate_label), " ".join(la), " ".join(lb)])
                continue
            if not check["agrees"] and other_reading_fits(scalars[small][0], scalars[large][0],
                                                          fraction):
                _refuse(refusals, unit_id, rule_id, RATE, RATE_READING_AMBIGUOUS,
                        fields=[" ".join(rate_label), " ".join(small), " ".join(large)])
                continue
            checks.append(check)
    return checks


def other_reading_fits(small, large, fraction):
    """D-198: whether the two same-measure figures fit a plain reading other than a part
    as `fraction` of a whole: the larger is the smaller increased by that proportion of
    it, or the smaller is the larger decreased by that proportion of it (a figure before
    and after the proportion is added or taken off). When one does, the figures admit
    more than one reading of the rule's arithmetic and a proportion mismatch is not
    Python's to state; which reading the rule's words mean is never decided here
    (WORDS-A)."""
    pr = _pr()
    f = abs(fraction)
    return bool(pr._close(abs(small) * (1 + f), abs(large))
                or pr._close(abs(large) * (1 - f), abs(small)))


def unique_best(scored):
    """The label with the most words shared with the rule, from [(score, label)] sorted
    best first, or None when two share the best score: a tie is refused, never broken."""
    if len(scored) > 1 and scored[1][0] == scored[0][0]:
        return None
    return scored[0][1]


def _rate_check(scalars, named, rate_label, part, whole, scale, *, unit_text=""):
    rate_value, rate_unit = scalars[rate_label]
    part_value, part_unit = scalars[part]
    whole_value, _whole_unit = scalars[whole]
    # The subject is the figure the rule names first; the other two give its value.
    order = sorted((lb for lb in (rate_label, part, whole) if lb in named), key=lambda lb: named[lb])
    subject = order[0]
    if subject == rate_label:
        if not whole_value:
            return None  # D-198: a share of a zero whole is undecided; the caller refuses it
        computed = part_value / whole_value / scale
        stated, unit = rate_value, rate_unit
    elif subject == part:
        computed = whole_value * rate_value * scale
        stated, unit = part_value, part_unit
    else:
        computed = part_value / (rate_value * scale)
        stated, unit = whole_value, part_unit
    decimals = _decimals_written(unit_text, subject)
    agrees = _agrees_as_written(computed, stated, decimals)
    names = [" ".join(rate_label), " ".join(part), " ".join(whole)]
    return {
        "relation": RATE,
        "computed": _r6(computed), "computed_unit": unit,
        "stated": stated, "stated_unit": unit,
        "agrees": agrees,
        "basis": "%s is %s of %s" % (names[1], names[0], names[2]),
        "stated_field": " ".join(subject),
        # Reader check RC1: the three figures, named, with their values.
        "rate_fields": names,
        "rate_figures": [rate_value, part_value, whole_value],
    }


# ---------------------------------------------------------------------------
# unit_mismatch


def column_unit_checks(scalars, columns, *, unit_id="", refusals=None):
    """A stated total (a scalar whose label contains a column's label) written in
    another measure than its column: the unit mismatch, and the sum read in the
    column's measure. A measure that does not convert is refused, never compared."""
    pr = _pr()
    checks = []
    for col_label, values in sorted(columns.items()):
        if len(values) < 2:
            continue
        col_unit = values[0][1]
        if not col_unit or not all(pr._same_unit(u, col_unit) for _, u in values):
            continue
        total = math.fsum(v for v, _ in values)
        for label, (value, unit) in sorted(scalars.items()):
            if not set(col_label) < set(label) or not unit or pr._same_unit(unit, col_unit):
                continue
            as_column = converted(value, unit, col_unit)
            if as_column is None:
                _refuse(refusals, unit_id, "", UNIT, UNIT_NOT_CONVERTIBLE,
                        fields=[" ".join(label), " ".join(col_label)], units=[unit, col_unit])
                continue
            checks.append({
                "relation": UNIT,
                "computed": as_column, "computed_unit": col_unit,
                "stated": value, "stated_unit": unit,
                "agrees": False,
                "basis": "%s is written in %s; the column %s it adds up is in %s" % (
                    " ".join(label), unit, " ".join(col_label), col_unit),
                "stated_field": " ".join(label),
                "compared_field": " ".join(col_label),
            })
            checks.append({
                "relation": "sum_mismatch",
                "computed": _r6(total), "computed_unit": col_unit,
                "stated": as_column, "stated_unit": col_unit,
                "agrees": pr._close(total, as_column),
                "basis": "sum of %d values under %s, the stated %s read in %s" % (
                    len(values), " ".join(col_label), " ".join(label), col_unit),
                "stated_field": " ".join(label),
                "addend_field": " ".join(col_label),
                "addends": [v for v, _ in values],
            })
    return checks


def band_unit_checks(direct, low, high, bound_unit, *, unit_id="", rule_id="", refusals=None,
                     refuse_labels=()):
    """A figure a band applies to, written in another measure than the band's: the
    unit mismatch, and the band comparison read in the band's measure. `direct` is
    [(label tuple, (value, unit))], the figures the band branch already considers.
    A figure whose measure does not convert is refused into `refusals` when the rule
    names it (`refuse_labels`, D-198); a figure the rule does not name is not the
    band's, so its other measure is no refusal."""
    pr = _pr()
    checks = []
    named = {tuple(lb) for lb in refuse_labels or ()}
    for label, (value, unit) in direct:
        if not unit or pr._unit_str(pr.unit_exponents(unit)) == bound_unit:
            continue
        as_band = converted(value, unit, bound_unit)
        if as_band is None:
            if tuple(label) in named or tuple(label)[:-1] in named:
                _refuse(refusals, unit_id, rule_id, UNIT, UNIT_NOT_CONVERTIBLE,
                        fields=[" ".join(label)], units=[unit, bound_unit])
            continue
        checks.append({
            "relation": UNIT,
            "computed": as_band, "computed_unit": bound_unit,
            "stated": value, "stated_unit": unit,
            "band_low": low, "band_high": high,
            "agrees": False,
            "basis": "%s is written in %s; the band it is compared with is in %s" % (
                " ".join(label), unit, bound_unit),
            "stated_field": " ".join(label),
            "band_unit_mismatch": True,
        })
        if as_band > high:
            relation, agrees = "above_band", False
        elif as_band < low:
            relation, agrees = "below_band", False
        else:
            relation, agrees = "ratio_out_of_range", True
        checks.append({
            "relation": relation,
            "computed": as_band, "computed_unit": bound_unit,
            "stated": None, "stated_unit": bound_unit,
            "band_low": low, "band_high": high,
            "agrees": agrees,
            "basis": "%s read in %s against the range" % (" ".join(label), bound_unit),
            "stated_field": " ".join(label),
            # The labels the comparison used, for the low-side condition; the
            # caller removes it before the check travels anywhere.
            "_labels": (tuple(label),),
        })
    return checks


# ---------------------------------------------------------------------------
# tables, for copy and carry


def unit_tables(unit_text):
    """Every table with a separator row: its labels (pairing_map.header_label), the
    unit each header declares, and its body rows as cells."""
    pr = _pr()
    out = []
    for block in pairing_map._table_blocks(unit_text or ""):
        if len(block) < 3 or not pairing_map._TABLE_SEP.match(block[1]):
            continue
        raw = [c.strip() for c in block[0].strip().strip("|").split("|")]
        rows = [[c.strip() for c in row.strip().strip("|").split("|")] for row in block[2:]]
        out.append({"labels": [tuple(pairing_map.header_label(c)) for c in raw],
                    "units": [pr._header_unit(c) for c in raw], "rows": rows})
    return out


def _cell_figure(cell, header_unit):
    q = _pr().first_quantity(cell)
    if q is None:
        return None
    value, unit = q
    return value, (unit or header_unit)


def _text_column(table, i):
    cells = [row[i] for row in table["rows"] if i < len(row) and row[i].strip()]
    return bool(cells) and all(_pr().first_quantity(c) is None for c in cells)


def _column_values(table, i):
    out = []
    for row in table["rows"]:
        fig = _cell_figure(row[i], table["units"][i]) if i < len(row) else None
        out.append(fig)
    return out


def _by_index(units_by_id):
    return {u.get("index"): u for u in (units_by_id or {}).values()
            if isinstance(u, dict) and isinstance(u.get("index"), int)}


# ---------------------------------------------------------------------------
# copy_mismatch


def one_source(sources):
    """The one unit a row's key cell names by its heading, or None when more than one
    unit carries that heading: which one was copied is not decided by guessing."""
    return sources[0] if len(sources) == 1 else None


def _titles(unit, units_by_id):
    """{normalised heading: [other units carrying it]}."""
    by_title = {}
    for other in (units_by_id or {}).values():
        if not isinstance(other, dict) or other.get("unit_id") == unit.get("unit_id", ""):
            continue
        key = tuple(pairing_map._norm_label(other.get("title") or ""))
        if key:
            by_title.setdefault(key, []).append(other)
    return by_title


def _copy_tables(unit, rule_text):
    """(table, key column, value columns) for each table whose one text key column and
    value columns the rule names, as copy_checks reads them."""
    out = []
    for table in unit_tables(unit.get("text", "")):
        labels = table["labels"]
        named = named_labels(rule_text, [lb for lb in labels if lb])
        keys = [i for i, lb in enumerate(labels) if lb in named and _text_column(table, i)]
        values = [i for i, lb in enumerate(labels) if lb in named and i not in keys]
        if len(keys) == 1 and values:
            out.append((table, keys[0], values))
    return out


def copy_subjects(unit, rule_text, units_by_id):
    """D-198: the ids of every unit a key cell of a copy table names by its heading,
    whatever the copy's outcome (computed, refused for an ambiguous subject, a missing
    field or another measure, or a cell with no figure), so the multi-round signature
    covers each source a copy reads or could read."""
    by_title = _titles(unit, units_by_id)
    out = set()
    for table, k, _values in _copy_tables(unit, rule_text):
        for row in table["rows"]:
            subject = tuple(pairing_map._norm_label(row[k])) if k < len(row) else ()
            for source in by_title.get(subject, []) if subject else []:
                out.add(source.get("unit_id", ""))
    out.discard("")
    return out


def copy_checks(unit, rule_text, units_by_id, *, rule_id="", refusals=None, known_units=None):
    """Every table row of `unit` naming another unit by its heading, in a column whose
    label that unit states: the row must carry that unit's figure."""
    pr = _pr()
    unit_id = unit.get("unit_id", "")
    by_title = _titles(unit, units_by_id)
    checks = []
    for table, k, values in _copy_tables(unit, rule_text):
        labels = table["labels"]
        for j in values:
            column = _column_values(table, j)
            for r, row in enumerate(table["rows"]):
                if k >= len(row) or column[r] is None:
                    continue
                subject = tuple(pairing_map._norm_label(row[k]))
                sources = by_title.get(subject, []) if subject else []
                if not sources:
                    continue
                field = "%s row%d" % (" ".join(labels[j]), r + 1)
                source = one_source(sources)
                if source is None:
                    _refuse(refusals, unit_id, rule_id, COPY, COPY_SUBJECT_AMBIGUOUS, fields=[field],
                            units_named=sorted(s.get("unit_id", "") for s in sources))
                    continue
                scalars, _c, _r = pr.extract_fields(source.get("text", ""), known_units)
                if labels[j] not in scalars:
                    _refuse(refusals, unit_id, rule_id, COPY, COPY_SOURCE_LACKS_FIELD, fields=[field],
                            units_named=[source.get("unit_id", "")])
                    continue
                source_value, source_unit = scalars[labels[j]]
                stated_value, stated_unit = column[r]
                if not pr._same_unit(source_unit, stated_unit):
                    _refuse(refusals, unit_id, rule_id, COPY, COPY_MEASURE_DIFFERS, fields=[field],
                            units=[stated_unit, source_unit], units_named=[source.get("unit_id", "")])
                    continue
                checks.append({
                    "relation": COPY,
                    "computed": source_value, "computed_unit": source_unit,
                    "stated": stated_value, "stated_unit": stated_unit,
                    "agrees": pr._close(source_value, stated_value),
                    "basis": "%s of the row naming %s, against that unit's own %s" % (
                        field, source.get("title", ""), " ".join(labels[j])),
                    "stated_field": field,
                    "compared_unit_id": source.get("unit_id", ""),
                    "compared_field": " ".join(labels[j]),
                    "key_field": " ".join(labels[k]),
                })
    return checks


# ---------------------------------------------------------------------------
# carry_mismatch


def _carry_tables(unit, rule_text):
    """(table, column index, column label, first-row key) for each table of `unit`
    whose value column and first-row key the rule names."""
    rule_words = _words(rule_text)
    out = []
    for table in unit_tables(unit.get("text", "")):
        labels = table["labels"]
        keys = [i for i, lb in enumerate(labels) if lb and _text_column(table, i)]
        if len(keys) != 1 or not table["rows"]:
            continue
        k = keys[0]
        first_key = tuple(pairing_map._norm_label(table["rows"][0][k] if k < len(table["rows"][0]) else ""))
        if not first_key or not set(first_key) <= rule_words:
            continue
        named = named_labels(rule_text, [lb for i, lb in enumerate(labels) if lb and i != k])
        for j, lb in enumerate(labels):
            if j != k and lb in named:
                out.append((table, j, lb, first_key, k))
    return out


def source_adds_up(column_sum, stated_totals):
    """Whether the unit before adds up on its own: every total it states for the column
    is the column's sum. When it does not, its stated total and its sum are two figures
    the next unit could be carrying, and which one is not decided by arithmetic."""
    pr = _pr()
    return all(pr._close(v, column_sum) for v in stated_totals)


def carry_sources(unit, rule_text, units_by_id):
    """The unit a carry of `unit` under this rule reads (the unit just before), or None."""
    if not _carry_tables(unit, rule_text):
        return None
    before = _by_index(units_by_id).get((unit.get("index") or 0) - 1)
    return before.get("unit_id") if isinstance(before, dict) else None


def carry_checks(unit, rule_text, units_by_id, *, rule_id="", refusals=None, known_units=None):
    """The first row of each named column against the column sum of the unit before,
    which must hold the same column under the same first-row key."""
    pr = _pr()
    unit_id = unit.get("unit_id", "")
    idx = unit.get("index")
    before = _by_index(units_by_id).get(idx - 1) if isinstance(idx, int) else None
    if not isinstance(before, dict):
        return []
    checks = []
    for table, j, label, first_key, k in _carry_tables(unit, rule_text):
        opening = _column_values(table, j)[0]
        if opening is None:
            continue
        source = None
        for other in unit_tables(before.get("text", "")):
            ok = [i for i, lb in enumerate(other["labels"]) if lb == label]
            keys = [i for i, lb in enumerate(other["labels"]) if lb and _text_column(other, i)]
            if len(ok) != 1 or len(keys) != 1 or not other["rows"]:
                continue
            row0 = other["rows"][0]
            if tuple(pairing_map._norm_label(row0[keys[0]] if keys[0] < len(row0) else "")) != first_key:
                continue
            source = (other, ok[0])
            break
        if source is None:
            continue
        field = "%s row1" % " ".join(label)
        other, oj = source
        figures = _column_values(other, oj)
        if any(f is None for f in figures) or not figures:
            _refuse(refusals, unit_id, rule_id, CARRY, CARRY_SOURCE_INCOMPLETE, fields=[field],
                    units_named=[before.get("unit_id", "")])
            continue
        source_unit = figures[0][1]
        if not all(pr._same_unit(u, source_unit) for _, u in figures) or not pr._same_unit(opening[1], source_unit):
            _refuse(refusals, unit_id, rule_id, CARRY, CARRY_MEASURE_DIFFERS, fields=[field],
                    units=sorted({str(u) for _, u in figures} | {str(opening[1])}),
                    units_named=[before.get("unit_id", "")])
            continue
        column_sum = _r6(math.fsum(v for v, _ in figures))
        scalars, _c, _r = pr.extract_fields(before.get("text", ""), known_units)
        stated_totals = [(lb, v) for lb, (v, u) in sorted(scalars.items())
                         if set(label) < set(lb) and pr._same_unit(u, source_unit)]
        if not source_adds_up(column_sum, [v for _lb, v in stated_totals]):
            _refuse(refusals, unit_id, rule_id, CARRY, CARRY_SOURCE_DOES_NOT_ADD_UP, fields=[field],
                    units_named=[before.get("unit_id", "")],
                    figures=[column_sum] + [v for _lb, v in stated_totals])
            continue
        checks.append({
            "relation": CARRY,
            "computed": column_sum, "computed_unit": source_unit,
            "stated": opening[0], "stated_unit": opening[1],
            "agrees": pr._close(column_sum, opening[0]),
            "basis": "%s against the sum of %s in %s" % (field, " ".join(label), before.get("title", "")),
            "stated_field": field,
            "compared_unit_id": before.get("unit_id", ""),
            "compared_field": " ".join(label),
            "key_field": " ".join(table["labels"][k]),
        })
    return checks


# ---------------------------------------------------------------------------
# what a plan of one unit reads, and the refusals


def cross_unit_sources(unit, rules, units_by_id, known_units=None):
    """The ids of the other units a copy or carry check of `unit` under `rules` reads or
    could read, sorted. multi_round_rounds puts their text in the unit's signature, so a
    unit whose neighbour or copied source changed is recomputed, never reused. D-198:
    every unit a key cell names is signed whatever the copy's outcome (copy_subjects),
    not only the sources of the copies computed this round. `known_units` is accepted as
    plan_calls passes it; the reading of headings does not depend on it."""
    out = set()
    for rule in rules or ():
        text = rule.get("rule", "") if isinstance(rule, dict) else ""
        before = carry_sources(unit, text, units_by_id)
        if before:
            out.add(before)
        out |= copy_subjects(unit, text, units_by_id)
    return sorted(out)


def _field_label(check):
    field = tuple(pairing_map._norm_label(str(check.get("stated_field") or "")))
    if field and field[-1].startswith("row") and field[-1][3:].isdigit():
        field = field[:-1]
    return field


def measure_rule(check, rule_ids, rules_by_id):
    """D-198 (open item 76): the one rule of `rule_ids` whose DECLARED scope or
    requirement (the heading brackets: pairing_map.scope_declaration and
    required_declaration) reads the figure's own label or a measure it is written in or
    compared with, as (rule_id, None); (None, reason) when none or more than one does.
    A unit mismatch is about the measure, so it is never attributed to the sum or band
    rule it was compared under, and never by the rule's words."""
    field = _field_label(check)
    measures = {tuple(pairing_map._norm_label(str(u))) for u in
                (check.get("stated_unit"), check.get("computed_unit")) if u}
    wanted = ({field} if field else set()) | {m for m in measures if m}
    hits = []
    for rid in rule_ids:
        rule = rules_by_id.get(rid)
        if not isinstance(rule, dict):
            continue
        declared = {lb for lb, _v in pairing_map.scope_declaration(rule)} | \
            set(pairing_map.required_declaration(rule))
        if declared & wanted and rid not in hits:
            hits.append(rid)
    if len(hits) == 1:
        return hits[0], None
    return None, (UNIT_RULE_AMBIGUOUS if hits else UNIT_RULE_UNDECLARED)


def labels_read(check):
    """D-198: the label tuples a rate, copy or carry check read, so plan_calls settles a
    rule by it only when the rule names nothing else."""
    out = set()
    for name in list(check.get("rate_fields") or []) + [check.get("compared_field"),
                                                       check.get("key_field")]:
        if name:
            out.add(tuple(pairing_map._norm_label(str(name))))
    field = _field_label(check)
    if field:
        out.add(field)
    out.discard(())
    return out


def _refuse(sink, unit_id, rule_id, relation, reason, **detail):
    if sink is None:
        return
    row = {"unit_id": unit_id, "rule_id": rule_id, "relation": relation, "reason": reason}
    row.update({k: v for k, v in detail.items() if v not in (None, [], "")})
    if row not in sink:
        sink.append(row)
