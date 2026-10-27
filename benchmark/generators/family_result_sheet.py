"""Family 1: tabular result sheets against reference ranges.

Each entry is one sample: a parameter, a result in mg/L, the analyst, and a table of
aliquot volumes in mL, most with a stated total. Bands come from a reference table
keyed by parameter. Planted kinds: a result above its range, a result below it, a
total volume that does not add up, a missing analyst (computed absence), a blank
aliquot cell, and a unit mismatch: a result written in g/L against a reference range in
mg/L, or a total volume written in L against a volume column in mL (the figure, read in
the right measure, is correct: only the measure is wrong). CONV-SE requires each result
in its range's measure and each total in its column's measure, so a unit mismatch breaks
a convention as written, and its key cites CONV-SE. Python compares nothing in another
measure, so the unit mismatches are keyed from this family's own ground truth and found
again by the ground-truth scanner (ground_truth.py), not by the audit.
Clean distractors: results exactly on a bound, and totals in decimals that do add up.
"""
from . import model as md
from . import textrules as tr
from . import wordlists as wl

FAMILY = "f1"
NAME = "tabular result sheet"

PARAMETERS = [("Nitrate", 0.5, 10.0), ("Sulphate", 5.0, 250.0), ("Chloride", 10.0, 200.0),
              ("Fluoride", 0.1, 1.5), ("Ammonium", 0.05, 0.5), ("Phosphate", 0.1, 2.0),
              ("Calcium", 15.0, 120.0), ("Magnesium", 2.0, 50.0)]

RULES = [
    md.Rule("CONV-SA", "Result range", "The result must lie within the reference range for the parameter."),
    md.Rule("CONV-SB", "Volume total", "The total volume must equal the sum of the volume column."),
    md.Rule("CONV-SC", "Aliquot form", "Each aliquot volume must be given as a figure in millilitres."),
    md.Rule("CONV-SD", "Analyst", "Every sample entry must state the analyst.",
            scope=["parameter"], requires=["analyst"]),
    # The rule a unit mismatch breaks, cited in its key. Worded to name only the result and
    # the parameter (never the range column's header, which would give it a band, nor the
    # total's label, which would tie it with CONV-SB for the sum findings).
    md.Rule("CONV-SE", "Measures",
            "Each result must be written in the measure in which its parameter's range is given, "
            "and each total in the measure of the column it adds up."),
]
# What each keyed kind's rule text must state (bundle.check_rule_statements reads the
# rendered conventions): the clause a unit of that kind breaks as written.
RULE_STATEMENTS = {
    "band_above": ("must lie within the reference range for the parameter",),
    "band_below": ("must lie within the reference range for the parameter",),
    "total_mismatch": ("must equal the sum of the volume column",),
    "blank_cell": ("must be given as a figure in millilitres",),
    "missing_required_field": ("must state the analyst",),
    "unit_mismatch": ("must be written in the measure in which its parameter's range is given",
                      "each total in the measure of the column it adds up"),
}


def _every_sample_ranged(units, _m, label, reference):
    """The samples whose parameter has no row in the reference file's range table."""
    keys = {r[0] for r in tr.plain_table(reference)[1] if r}
    return {u["id"] for u in units if u["lines"].get(label("Parameter")) not in keys}


# How each sentence of the reference file is read (bundle.check_reference_texts).
REFERENCE_READINGS = (
    (r"These ranges apply to every sample of the round\.", _every_sample_ranged),
)
ORDINALS = ["First", "Second", "Third", "Fourth"]
# The conversions a unit mismatch is planted with, and read back by the scanner.
CONVERSIONS = [["g/L", "mg/L", 1000], ["L", "mL", 1000]]
GROUND_TRUTH = [{"check": "measure", "kind": "unit_mismatch", "conversions": CONVERSIONS,
                 "row_key": "parameter", "rule_for": {"reference": "CONV-SE", "column": "CONV-SE"}}]


def _fmt2(x):
    return tr.format_number(x, 2)


def _inside(rng, lo, hi):
    span = hi - lo
    return round(rng.uniform(lo + 0.15 * span, hi - 0.15 * span), 2)


def build(seed, attempt=0):
    rng = wl.make_rng(FAMILY, seed, attempt)
    params = rng.sample(PARAMETERS, 6)
    n = rng.randint(20, 24)
    heads = wl.pick(rng, wl.TREES, n)
    places = wl.PLACES
    # flaw plan: kinds over unit slots
    slots = list(range(n))
    rng.shuffle(slots)
    plan = {}
    kinds = (["band_above"] * 3 + ["band_below"] * 2 + ["total_mismatch"] * 3
             + ["missing_required_field"] * 2 + ["blank_cell"] * 2
             + ["unit_mismatch_result", "unit_mismatch_total"])
    for k, s in zip(kinds, slots):
        plan[s] = k
    rest = slots[len(kinds):]
    distract = {rest[0]: "at_high_bound", rest[1]: "at_low_bound", rest[2]: "decimal_total"}
    doc_units, twin_units, planted, clean = [], [], [], []
    for i in range(n):
        kind = plan.get(i)
        pname, lo, hi = params[i % len(params)] if i < len(params) else rng.choice(params)
        result = _inside(rng, lo, hi)
        if distract.get(i) == "at_high_bound":
            result = hi
        elif distract.get(i) == "at_low_bound":
            result = lo
        has_total = kind != "blank_cell" and (kind in ("total_mismatch", "unit_mismatch_total")
                                              or distract.get(i) == "decimal_total"
                                              or rng.random() < 0.6)
        rows = rng.randint(3, 4)
        tenths = [rng.randint(20, 95) for _ in range(rows)]
        if distract.get(i) == "decimal_total":
            tenths = [t if t % 10 else t + 3 for t in tenths]
        lines = [["Site", rng.choice(places)], ["Parameter", pname],
                 ["Result", "%s mg/L" % _fmt2(result)], ["Analyst", wl.person(rng)]]
        table_rows = [[ORDINALS[r], tr.format_number(t / 10.0, 1)] for r, t in enumerate(tenths)]
        blocks = [("lines", lines), ("table", ["Aliquot", "Volume (mL)"], table_rows)]
        total = sum(tenths) / 10.0
        if has_total:
            blocks.append(("lines", [["Total volume", "%s mL" % tr.format_number(total, 1)]]))
        clean_unit = md.Unit("Sample " + heads[i], blocks)
        flawed = clean_unit.clone()
        if kind == "band_above":
            bad = round(hi + rng.uniform(0.2, 0.8) * (hi - lo), 2)
            flawed.set_line("Result", "%s mg/L" % _fmt2(bad))
            planted.append({"unit": i, "rule": "CONV-SA", "relation": "above_band", "kind": kind,
                            "field_label": "result", "value_a": bad, "value_b": hi})
        elif kind == "band_below":
            bad = round(lo * rng.uniform(0.3, 0.7), 2)
            if bad >= lo or bad <= 0:
                raise ValueError("below-band figure out of reach")
            flawed.set_line("Result", "%s mg/L" % _fmt2(bad))
            planted.append({"unit": i, "rule": "CONV-SA", "relation": "below_band", "kind": kind,
                            "field_label": "result", "value_a": bad, "value_b": lo})
        elif kind == "total_mismatch":
            delta = rng.choice([-1, 1]) * rng.randint(5, 25)
            stated = (sum(tenths) + delta) / 10.0
            flawed.set_line("Total volume", "%s mL" % tr.format_number(stated, 1))
            planted.append({"unit": i, "rule": "CONV-SB", "relation": "sum_mismatch", "kind": kind,
                            "field_label": "total volume", "value_a": round(total, 6),
                            "value_b": stated})
        elif kind == "missing_required_field":
            flawed.remove_line("Analyst")
            planted.append({"unit": i, "rule": "CONV-SD", "relation": "missing_field", "kind": kind,
                            "field_label": "analyst", "value_a": 0, "value_b": 1})
        elif kind == "blank_cell":
            r = rng.randrange(rows)
            flawed.blocks[1][2][r][1] = ""
            planted.append({"unit": i, "rule": "CONV-SC", "relation": "missing_field", "kind": kind,
                            "field_label": "volume", "value_a": rows - 1, "value_b": rows})
        elif kind == "unit_mismatch_result":
            # the right result, written in g/L: 45.23 mg/L as 0.04523 g/L
            flawed.set_line("Result", "%s g/L" % tr.format_number(result / 1000.0, 5))
            planted.append({"unit": i, "rule": "CONV-SE", "relation": "unit_mismatch",
                            "kind": "unit_mismatch", "field_label": "result",
                            "value_a": round(result / 1000.0, 6), "value_b": result,
                            "unit_a": "g/L", "unit_b": "mg/L", "extra": {"compared_with": "reference"}})
        elif kind == "unit_mismatch_total":
            # the right total, written in L: 12.3 mL as 0.0123 L
            flawed.set_line("Total volume", "%s L" % tr.format_number(total / 1000.0, 4))
            planted.append({"unit": i, "rule": "CONV-SE", "relation": "unit_mismatch",
                            "kind": "unit_mismatch", "field_label": "total volume",
                            "value_a": round(total / 1000.0, 6), "value_b": round(total, 6),
                            "unit_a": "L", "unit_b": "mL", "extra": {"compared_with": "column"}})
        if i in distract:
            clean.append(i)
        doc_units.append(flawed)
        twin_units.append(clean_unit)
    title = "Sampling sheet " + wl.letters_tag(rng).title()
    preamble = "This sheet records the results of the spring sampling round."
    doc = md.Doc(title, preamble, doc_units)
    twin = md.Doc(title, preamble, twin_units)
    table = ("table", ["Parameter", "Reference range (mg/L)"],
             [[p, "%s to %s" % (tr.format_number(lo, 2), tr.format_number(hi, 2))] for p, lo, hi in params])
    reference = ("ranges", "Reference ranges",
                 [("prose", "These ranges apply to every sample of the round."), table])
    conv = md.Conventions("Sampling conventions", "These rules govern the sampling sheet.", RULES)
    sums = [p for p in planted if p["kind"] == "total_mismatch"]
    reform_unit = sums[0]["unit"]
    stated_total = doc_units[reform_unit].line_value("Total volume")
    above = [p for p in planted if p["kind"] == "band_above"][0]
    return {
        "family": FAMILY, "family_name": NAME, "seed": seed, "mode": "single",
        "doc": doc, "twin": twin, "conventions": conv, "references": [reference],
        "planted": planted, "clean": sorted(clean), "doc_stem": "sheet", "conv_stem": "rules",
        "ground_truth_checks": GROUND_TRUTH,
        "task": "Review the sampling sheet against the sampling conventions, grounded in the reference ranges.",
        "probes": {
            "reword": {"old": "Total volume", "new": "Combined volume"},
            "reorder": wl.reorder(n, rng),
            # probe 3: the term only in the later version carries a keyed flaw
            "term": {"unit": above["unit"], "label": "Result"},
            "reformat": {"unit": reform_unit, "label": "Total volume",
                         "text": stated_total.replace(" mL", "0 mL")},
        },
    }
