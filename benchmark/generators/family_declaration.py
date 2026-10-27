"""Family 2: declarations with arithmetic (products, rates, sums, cross-row totals).

Declaration lines state a goods class, a quantity in box, a unit price (a rate in
EUR/box), the line value in EUR and the country of origin. Consignment summaries copy
the line values of the lines before them into a table and state their total. Bands on
the unit price come from a reference table keyed by goods class; the ratio of line
value to quantity is compared with the same band (section 7), so every price figure
is planted where that ratio agrees with it.

Planted kinds: a line value that is not quantity times unit price, a unit price above
its band, one below it, a consignment total that does not add up, a missing country
of origin. Distractors: unit prices exactly on a bound, a line value with decimals
that is right, and a consignment total written with comma groups that is right.
"""
from . import model as md
from . import textrules as tr
from . import wordlists as wl

FAMILY = "f2"
NAME = "declaration with arithmetic"

CLASSES = [("Fasteners", 2.0, 6.0), ("Hinges", 4.0, 12.0), ("Brackets", 8.0, 15.0),
           ("Gaskets", 1.5, 4.5), ("Valves", 20.0, 45.0), ("Bearings", 12.0, 30.0),
           ("Filters", 6.0, 18.0)]
COUNTRIES = ["Norway", "Portugal", "Chile", "Canada", "Kenya", "Japan", "Peru", "Ghana"]

RULES = [
    md.Rule("CONV-DA", "Line arithmetic", "The line value must equal the quantity times the unit price."),
    md.Rule("CONV-DB", "Price band", "The unit price must lie within the price band for the goods class."),
    md.Rule("CONV-DC", "Consignment total", "The total line value must equal the sum of the line value column."),
    md.Rule("CONV-DD", "Origin", "Every declaration line must state the country of origin.",
            scope=["goods class"], requires=["country of origin"]),
]


def _price(rng, lo, hi):
    span = hi - lo
    return round(rng.uniform(lo + 0.25 * span, hi - 0.25 * span) * 4) / 4.0


def build(seed):
    rng = wl.make_rng(FAMILY, seed)
    classes = rng.sample(CLASSES, 5)
    n_lines = rng.choice([16, 18, 19])
    group = 4
    heads = wl.pick(rng, wl.TREES, n_lines)
    sum_heads = wl.pick(rng, wl.BIRDS, (n_lines + group - 1) // group)
    slots = list(range(n_lines))
    rng.shuffle(slots)
    kinds = (["product_mismatch"] * 3 + ["band_above"] * 2 + ["band_below"] * 2
             + ["missing_required_field"] * 2)
    plan = dict(zip(slots, kinds))
    rest = slots[len(kinds):]
    distract = {rest[0]: "at_high_bound", rest[1]: "at_low_bound", rest[2]: "decimal_product"}
    lines_flawed, lines_clean, info = [], [], []
    for i in range(n_lines):
        kind = plan.get(i)
        cname, lo, hi = classes[i % len(classes)]
        qty = rng.randint(6, 40)
        price = _price(rng, lo, hi)
        if distract.get(i) == "at_high_bound":
            price = hi
        elif distract.get(i) == "at_low_bound":
            price = lo
        elif distract.get(i) == "decimal_product":
            price = round(price) + 0.35 if round(price) + 0.35 < hi else price
        flaw_price = price
        if kind == "band_above":
            flaw_price = round((hi + rng.uniform(0.2, 0.6) * (hi - lo)) * 4) / 4.0
        elif kind == "band_below":
            flaw_price = round(lo * rng.uniform(0.4, 0.7) * 4) / 4.0
            if not 0 < flaw_price < lo:
                raise ValueError("below-band price out of reach")

        def unit(p, value, with_origin=True):
            ls = [["Goods class", cname], ["Quantity", "%d box" % qty],
                  ["Unit price", "%s EUR/box" % tr.format_number(p, 2)],
                  ["Line value", "%s EUR" % tr.format_number(value, 2)]]
            if with_origin:
                ls.append(["Country of origin", rng.choice(COUNTRIES)])
            return md.Unit("Line " + heads[i], [("lines", ls)])
        state = rng.getstate()
        clean_u = unit(price, qty * price)
        rng.setstate(state)
        planted = None
        if kind == "product_mismatch":
            # off by a whole number of unit prices or a slip of a few EUR, ratio kept in band
            stated = round(qty * price + rng.choice([-1, 1]) * rng.randint(2, 9), 2)
            ratio = stated / qty
            if not lo <= ratio <= hi:
                stated = round(qty * price + (1 if ratio < lo else -1), 2)
            flawed_u = unit(price, stated)
            planted = {"rule": "CONV-DA", "relation": "product_mismatch", "kind": kind,
                       "field_label": "line value", "value_a": tr.r6(qty * price), "value_b": stated}
            value = stated
        elif kind in ("band_above", "band_below"):
            flawed_u = unit(flaw_price, qty * flaw_price)
            planted = {"rule": "CONV-DB", "relation": "above_band" if kind == "band_above" else "below_band",
                       "kind": kind, "field_label": "unit price", "value_a": flaw_price,
                       "value_b": hi if kind == "band_above" else lo}
            value = qty * flaw_price
        elif kind == "missing_required_field":
            flawed_u = unit(price, qty * price, with_origin=False)
            planted = {"rule": "CONV-DD", "relation": "missing_field", "kind": kind,
                       "field_label": "country origin", "value_a": 0, "value_b": 1}
            value = qty * price
        else:
            flawed_u = clean_u.clone()
            value = qty * price
        rng.setstate(state)
        unit(price, 0)              # consume the same draws as the clean unit
        lines_flawed.append(flawed_u)
        lines_clean.append(clean_u)
        info.append({"planted": planted, "value": value, "clean_value": qty * price,
                     "distract": distract.get(i)})
    # interleave consignment summaries after every group of lines
    doc_units, twin_units, planted, clean = [], [], [], []
    sum_plan = rng.sample(range(len(sum_heads)), 3)
    comma_summary = [s for s in range(len(sum_heads)) if s not in sum_plan][0]
    for g, sname in enumerate(sum_heads):
        members = list(range(g * group, min((g + 1) * group, n_lines)))
        for m in members:
            idx = len(doc_units)
            doc_units.append(lines_flawed[m])
            twin_units.append(lines_clean[m])
            if info[m]["planted"]:
                p = dict(info[m]["planted"])
                p["unit"] = idx
                planted.append(p)
            if info[m]["distract"]:
                clean.append(idx)
        if len(members) < 2:
            continue
        rows_f = [[lines_flawed[m].heading, tr.format_number(info[m]["value"], 2)] for m in members]
        rows_c = [[lines_clean[m].heading, tr.format_number(info[m]["clean_value"], 2)] for m in members]
        total_f = sum(round(info[m]["value"], 2) for m in members)
        total_c = sum(round(info[m]["clean_value"], 2) for m in members)
        grouped = g == comma_summary and total_c >= 1000
        idx = len(doc_units)
        stated_f = total_f
        if g in sum_plan:
            stated_f = round(total_f + rng.choice([-1, 1]) * rng.randint(10, 60), 2)
            planted.append({"unit": idx, "rule": "CONV-DC", "relation": "sum_mismatch",
                            "kind": "total_mismatch", "field_label": "total line value",
                            "value_a": tr.r6(total_f), "value_b": stated_f})
        if grouped:
            clean.append(idx)
        doc_units.append(md.Unit("Consignment " + sname, [
            ("table", ["Entry", "Line value (EUR)"], rows_f),
            ("lines", [["Total line value", "%s EUR" % tr.format_number(stated_f, 2, grouped)]])]))
        twin_units.append(md.Unit("Consignment " + sname, [
            ("table", ["Entry", "Line value (EUR)"], rows_c),
            ("lines", [["Total line value", "%s EUR" % tr.format_number(total_c, 2, grouped)]])]))
    title = "Declaration " + wl.letters_tag(rng).title()
    preamble = "This declaration lists the goods of one shipment and its consignment totals."
    doc = md.Doc(title, preamble, doc_units)
    twin = md.Doc(title, preamble, twin_units)
    table = ("table", ["Goods class", "Price band (EUR/box)"],
             [[c, "%s to %s" % (tr.format_number(lo, 2), tr.format_number(hi, 2))] for c, lo, hi in classes])
    reference = ("bands", "Price bands",
                 [("prose", "These price bands apply to every declaration line of the shipment."), table])
    conv = md.Conventions("Declaration conventions", "These rules govern the declaration.", RULES)
    flaw_units = {p["unit"] for p in planted}
    plain = [i for i, u in enumerate(doc_units) if i not in flaw_units and i not in clean
             and u.heading.startswith("Line ")]
    prod = [p for p in planted if p["relation"] == "product_mismatch"][0]
    stated_value = doc_units[prod["unit"]].line_value("Line value")
    return {
        "family": FAMILY, "family_name": NAME, "seed": seed, "mode": "single",
        "doc": doc, "twin": twin, "conventions": conv, "references": [reference],
        "planted": planted, "clean": sorted(clean), "doc_stem": "declaration", "conv_stem": "rules",
        "task": "Review the declaration against the declaration conventions, grounded in the price bands.",
        "probes": {
            "reword": {"old": "Line value", "new": "Line amount"},
            "reorder": wl.reorder(len(doc_units), rng),
            "term": {"unit": plain[0], "label": "Quantity"},
            "reformat": {"unit": prod["unit"], "label": "Line value",
                         "text": stated_value.replace(" EUR", "0 EUR")},
        },
    }
