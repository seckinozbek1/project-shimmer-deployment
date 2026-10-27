"""Family 3: financial-statement style (line items, subtotals, totals, period comparisons).

Each section is a table of line items with a current-period and a prior-period column
in EUR, the two stated subtotals, the period change in percent and the preparer. A
closing summary section lists every section's stated subtotals and totals them. The
period change is checked against the band the rule itself states (section 7, "A rule
may state its own band"), so the statement's own reference file carries no figure.

Planted kinds: a current-period subtotal that does not add up, a prior-period one, a
period change above the band, one below it, and a missing preparer. Distractors: a
period change just inside a bound, and a subtotal written with comma groups that adds
up.
"""
from . import model as md
from . import textrules as tr
from . import wordlists as wl

FAMILY = "f3"
NAME = "financial statement"

SECTIONS = {
    "Staff costs": ["Salaries", "Overtime", "Pensions", "Benefits", "Recruitment"],
    "Premises": ["Rent", "Cleaning", "Security", "Repairs", "Rates"],
    "Travel": ["Rail fares", "Air fares", "Hotels", "Subsistence", "Mileage"],
    "Supplies": ["Stationery", "Printing", "Postage", "Software", "Hardware"],
    "Maintenance": ["Vehicles", "Plant", "Grounds", "Lifts", "Heating"],
    "Training": ["Courses", "Conferences", "Books", "Coaching", "Exams"],
    "Utilities": ["Electricity", "Gas", "Water", "Telephone", "Broadband"],
    "Insurance": ["Buildings", "Contents", "Fleet", "Cyber", "Travel cover"],
    "Professional fees": ["Audit", "Advice", "Valuation", "Translation", "Design"],
    "Marketing": ["Campaigns", "Events", "Sponsorship", "Website", "Brochures"],
    "Catering": ["Meals", "Beverages", "Hospitality", "Vending", "Kitchen stock"],
    "Logistics": ["Freight", "Couriers", "Storage", "Packaging", "Customs fees"],
    "Research": ["Materials", "Testing", "Surveys", "Prototypes", "Field work"],
    "Community": ["Grants", "Donations", "Volunteering", "Outreach", "Bursaries"],
    "Fleet": ["Leases", "Fuel", "Tyres", "Servicing", "Parking"],
    "Archives": ["Shelving", "Digitising", "Binding", "Retrieval", "Conservation"],
    "Health and safety": ["Inspections", "First aid", "Protective wear", "Signage", "Drills"],
    "Hospitality": ["Receptions", "Gifts", "Venue hire", "Flowers", "Guest travel"],
}

LOW, HIGH = -8.0, 8.0
RULES = [
    md.Rule("CONV-FA", "Current subtotal", "The total current period must equal the sum of the current period column."),
    md.Rule("CONV-FB", "Prior subtotal", "The total prior period must equal the sum of the prior period column."),
    md.Rule("CONV-FC", "Period change", "The period change must lie between -8% and 8%."),
    md.Rule("CONV-FD", "Preparer", "Every statement section must state who prepared it.",
            scope=["line item"], requires=["prepared by"]),
]


def _section(rng, items, zone):
    """Rows and totals whose period change falls in the zone; tries until it does."""
    for _ in range(2000):
        prior = [rng.randint(8, 90) * 100 + rng.randint(0, 99) for _ in items]
        if zone == "clean":
            g = rng.uniform(-0.05, 0.05)
        elif zone == "above":
            g = rng.uniform(0.11, 0.2)
        elif zone == "below":
            g = rng.uniform(-0.2, -0.11)
        else:
            g = rng.choice([-1, 1]) * rng.uniform(0.07, 0.079)
        cur = [int(round(p * (1 + g + rng.uniform(-0.01, 0.01)))) for p in prior]
        tc, tp = sum(cur), sum(prior)
        z = round((tc - tp) * 100.0 / tp, 1)
        ok = {"clean": abs(z) <= 6.0, "above": z >= 10.0, "below": z <= -10.0,
              "near": 7.0 <= abs(z) <= 7.9}[zone]
        if ok:
            return cur, prior, tc, tp, z
    raise ValueError("no section in zone %s" % zone)


def _unit(name, items, cur, prior, tc, tp, z, preparer, grouped=False):
    rows = [[it, str(c), str(p)] for it, c, p in zip(items, cur, prior)]
    lines = [["Total current period", "%s EUR" % tr.format_number(tc, 0, grouped)],
             ["Total prior period", "%s EUR" % tr.format_number(tp, 0, grouped)]]
    if z is not None:
        lines.append(["Period change", "%s%%" % tr.format_number(z, 1)])
    if preparer:
        lines.append(["Prepared by", preparer])
    return md.Unit(name, [("table", ["Line item", "Current period (EUR)", "Prior period (EUR)"], rows),
                          ("lines", lines)])


def build(seed):
    rng = wl.make_rng(FAMILY, seed)
    names = rng.sample(sorted(SECTIONS), rng.randint(14, 16))
    n = len(names)
    slots = list(range(n))
    rng.shuffle(slots)
    kinds = (["current_total_mismatch"] * 3 + ["prior_total_mismatch"] * 2 + ["change_above"] * 2
             + ["change_below"] * 2 + ["missing_required_field"] * 2)
    plan = dict(zip(slots, kinds))
    rest = slots[len(kinds):]
    distract = {rest[0]: "near_bound"}
    if len(rest) > 1:
        distract[rest[1]] = "grouped_total"
    doc_units, twin_units, planted, clean = [], [], [], []
    stated_rows, clean_rows = [], []
    for i, name in enumerate(names):
        items = rng.sample(SECTIONS[name], rng.randint(3, 5))
        kind = plan.get(i)
        preparer = wl.person(rng)
        zone = "near" if distract.get(i) == "near_bound" else "clean"
        cur, prior, tc, tp, z = _section(rng, items, zone)
        grouped = distract.get(i) == "grouped_total"
        clean_u = _unit(name, items, cur, prior, tc, tp, z, preparer, grouped)
        flawed = clean_u.clone()
        stc, stp = tc, tp
        if kind == "current_total_mismatch":
            stc = tc + rng.choice([-1, 1]) * rng.randint(10, 400)
            flawed.set_line("Total current period", "%d EUR" % stc)
            planted.append({"unit": i, "rule": "CONV-FA", "relation": "sum_mismatch", "kind": kind,
                            "field_label": "total current period", "value_a": tc, "value_b": stc})
        elif kind == "prior_total_mismatch":
            stp = tp + rng.choice([-1, 1]) * rng.randint(10, 400)
            flawed.set_line("Total prior period", "%d EUR" % stp)
            planted.append({"unit": i, "rule": "CONV-FB", "relation": "sum_mismatch", "kind": kind,
                            "field_label": "total prior period", "value_a": tp, "value_b": stp})
        elif kind in ("change_above", "change_below"):
            fc, fp, ftc, ftp, fz = _section(rng, items, "above" if kind == "change_above" else "below")
            flawed = _unit(name, items, fc, fp, ftc, ftp, fz, preparer)
            stc, stp = ftc, ftp
            planted.append({"unit": i, "rule": "CONV-FC",
                            "relation": "above_band" if kind == "change_above" else "below_band",
                            "kind": kind, "field_label": "period change", "value_a": fz,
                            "value_b": HIGH if kind == "change_above" else LOW})
        elif kind == "missing_required_field":
            flawed.remove_line("Prepared by")
            planted.append({"unit": i, "rule": "CONV-FD", "relation": "missing_field", "kind": kind,
                            "field_label": "prepared", "value_a": 0, "value_b": 1})
        if i in distract:
            clean.append(i)
        doc_units.append(flawed)
        twin_units.append(clean_u)
        stated_rows.append([name, stc, stp])
        clean_rows.append([name, tc, tp])
    preparer = wl.person(rng)
    for units, rows in ((doc_units, stated_rows), (twin_units, clean_rows)):
        tc = sum(r[1] for r in rows)
        tp = sum(r[2] for r in rows)
        units.append(md.Unit("Statement summary", [
            ("table", ["Line item", "Current period (EUR)", "Prior period (EUR)"],
             [[r[0], str(r[1]), str(r[2])] for r in rows]),
            ("lines", [["Total current period", "%s EUR" % tr.format_number(tc, 0, True)],
                       ["Total prior period", "%s EUR" % tr.format_number(tp, 0, True)],
                       ["Prepared by", preparer]])]))
    title = "Cost statement " + wl.letters_tag(rng).title()
    preamble = "This statement compares the costs of the current period with the prior period."
    doc = md.Doc(title, preamble, doc_units)
    twin = md.Doc(title, preamble, twin_units)
    reference = ("policy", "Statement policy", [
        ("prose", "Each section of the statement lists its line items for the current and the prior period."),
        ("prose", "The period change is the movement of the current total against the prior total, in percent."),
    ])
    conv = md.Conventions("Statement conventions", "These rules govern the cost statement.", RULES)
    flaw_units = {p["unit"] for p in planted}
    plain = [i for i in range(n) if i not in flaw_units and i not in clean]
    cur_sum = [p for p in planted if p["kind"] == "current_total_mismatch"][0]
    return {
        "family": FAMILY, "family_name": NAME, "seed": seed, "mode": "single",
        "doc": doc, "twin": twin, "conventions": conv, "references": [reference],
        "planted": planted, "clean": sorted(clean), "doc_stem": "statement", "conv_stem": "rules",
        "task": "Review the cost statement against the statement conventions, grounded in the statement policy.",
        "probes": {
            "reword": {"old": "Period change", "new": "Change on prior period"},
            "reorder": wl.reorder(len(doc_units), rng),
            "term": {"unit": plain[0], "label": "Period change"},
            "reformat": {"unit": cur_sum["unit"], "label": "Total current period",
                         "text": "%s EUR" % tr.format_number(cur_sum["value_b"], 0, True)},
        },
    }
