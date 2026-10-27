"""Family 1: tabular result sheets against reference ranges.

Each entry is one sample: a parameter, a result in mg/L, the analyst, and a table of
aliquot volumes in mL, most with a stated total. Bands come from a reference table
keyed by parameter. Planted kinds: a result above its range, a result below it, a
total volume that does not add up, a missing analyst (computed absence), and a blank
aliquot cell. Clean distractors: results exactly on a bound, and totals in decimals
that do add up.
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
]
ORDINALS = ["First", "Second", "Third", "Fourth"]


def _fmt2(x):
    return tr.format_number(x, 2)


def _inside(rng, lo, hi):
    span = hi - lo
    return round(rng.uniform(lo + 0.15 * span, hi - 0.15 * span), 2)


def build(seed):
    rng = wl.make_rng(FAMILY, seed)
    params = rng.sample(PARAMETERS, 6)
    n = rng.randint(20, 24)
    heads = wl.pick(rng, wl.TREES, n)
    places = wl.PLACES
    # flaw plan: kinds over unit slots
    slots = list(range(n))
    rng.shuffle(slots)
    plan = {}
    kinds = (["band_above"] * 3 + ["band_below"] * 2 + ["total_mismatch"] * 3
             + ["missing_required_field"] * 2 + ["blank_cell"] * 2)
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
        has_total = kind != "blank_cell" and (kind == "total_mismatch" or distract.get(i) == "decimal_total"
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
    clean_plain = [i for i in range(n) if i not in plan and i not in distract]
    return {
        "family": FAMILY, "family_name": NAME, "seed": seed, "mode": "single",
        "doc": doc, "twin": twin, "conventions": conv, "references": [reference],
        "planted": planted, "clean": sorted(clean), "doc_stem": "sheet", "conv_stem": "rules",
        "task": "Review the sampling sheet against the sampling conventions, grounded in the reference ranges.",
        "probes": {
            "reword": {"old": "Total volume", "new": "Combined volume"},
            "reorder": wl.reorder(n, rng),
            "term": {"unit": clean_plain[0], "label": "Result"},
            "reformat": {"unit": reform_unit, "label": "Total volume",
                         "text": stated_total.replace(" mL", "0 mL")},
        },
    }
