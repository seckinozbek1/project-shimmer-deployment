"""Family 6: neighbour-dependent flaws, as a running stock count.

Each count is one unit: a location, a table of movements in box whose first row is
the opening quantity carried from the count before, the stated closing quantity, the
shrinkage in percent and the counter. The chain is: opening of count k equals the
closing quantity of count k - 1.

Neighbour-dependent kinds (each with `depends_on_unit`, the neighbour it depends on):
- carry_in: the opening row was mis-carried from the count before; the stated closing
  quantity is right given the neighbour. Python sees a sum mismatch in the unit; only
  the neighbour says which figure is wrong (the opening row).
- carry_out: the stated closing quantity is wrong; the count after carries the right
  figure as its opening. Python sees a sum mismatch; only the next count confirms the
  computed sum. The count after a carry_out is a clean distractor: read beside its
  neighbour's stated closing it looks mis-carried, and it is not.
- carry_mismatch: wrong ONLY given the neighbour. The opening row differs from the
  closing quantity of the count before, and the received row absorbs the difference, so
  each count adds up on its own and only the pair shows the flaw. Python compares no two
  units, so this kind is keyed from this family's own ground truth and found again by
  the ground-truth scanner (ground_truth.py), with the neighbour in `depends_on_unit`.
Other kinds: shrinkage above the band the rule states, a missing counter.
"""
from . import model as md
from . import textrules as tr
from . import wordlists as wl

FAMILY = "f6"
NAME = "neighbour-dependent stock count"

LOW, HIGH = 0.5, 3.0
RULES = [
    md.Rule("CONV-LA", "Closing quantity",
            "The closing quantity must equal the sum of the quantity column, and the opening row "
            "must carry the closing quantity of the count before it."),
    md.Rule("CONV-LB", "Shrinkage", "The shrinkage must lie between 0.5% and 3%."),
    md.Rule("CONV-LC", "Counter", "Every stock count must state who counted it.",
            scope=["movement"], requires=["counted by"]),
]
GROUND_TRUTH = [{"check": "carry", "kind": "carry_mismatch", "rule": "CONV-LA",
                 "closing": "closing quantity", "column": "quantity"}]


def _unit(head, place, rows, closing, shrink, counter):
    lines_after = [["Closing quantity", "%s box" % tr.format_number(closing, 0, closing >= 1000)],
                   ["Shrinkage", "%s%%" % tr.format_number(shrink, 1)]]
    if counter:
        lines_after.append(["Counted by", counter])
    return md.Unit(head, [("lines", [["Location", place]]),
                          ("table", ["Movement", "Quantity (box)"], [[m, str(v)] for m, v in rows]),
                          ("lines", lines_after)])


def build(seed):
    rng = wl.make_rng(FAMILY, seed)
    n = rng.randint(24, 27)
    heads = wl.pick(rng, wl.TREES, n)
    # place neighbour-dependent flaws two or more units apart, then the rest
    taken = set()
    plan = {}

    order = list(range(n))
    rng.shuffle(order)
    for kind, count in (("carry_out", 3), ("carry_in", 3), ("carry_mismatch", 2)):
        placed = 0
        for i in order:
            if placed == count:
                break
            pair = {i, i + 1} if kind == "carry_out" else {i - 1, i}
            if min(pair) < 0 or max(pair) > n - 1 or pair & taken:
                continue
            plan[i] = kind
            taken |= pair
            placed += 1
        if placed != count:
            raise ValueError("cannot place %s" % kind)
    rest = [i for i in order if i not in taken]
    for kind, count in (("shrinkage_above", 2), ("shrinkage_below", 1), ("missing_counter", 2)):
        for _ in range(count):
            plan[rest.pop()] = kind
    after_out = [i + 1 for i, k in plan.items() if k == "carry_out"]
    at_bound = rest.pop()
    clean = sorted(after_out + [at_bound])
    # the true chain
    opening = first_opening = rng.randint(40, 200)
    doc_units, twin_units, planted = [], [], []
    places = wl.PLACES
    true_closing = []
    for i in range(n):
        received = rng.randint(0, 60)
        issued = -rng.randint(0, min(opening + received, 60))
        ret = rng.randint(1, 9) if rng.random() < 0.3 else None
        if i == n - 1:
            # The last count closes at the first count's opening quantity, so the
            # reordered-sections probe (a rotation, `rotate`) creates no neighbour pair
            # that breaks the chain: its one new pair is the last count before the first.
            issued = first_opening - opening - received - (ret or 0)
            if issued > 0:
                received, issued = received + issued, 0
        rows = [["Opening", opening], ["Received", received], ["Issued", issued]]
        if ret is not None:
            rows.append(["Returned", ret])
        closing = sum(v for _, v in rows)
        true_closing.append(closing)
        shrink = round(rng.uniform(0.6, 2.8), 1)
        if i == at_bound:
            shrink = rng.choice([LOW, HIGH])
        place = rng.choice(places)
        counter = wl.person(rng)
        head = "Count " + heads[i]
        clean_u = _unit(head, place, rows, closing, shrink, counter)
        kind = plan.get(i)
        flawed = clean_u.clone()
        if kind == "carry_in":
            delta = rng.choice([-1, 1]) * rng.randint(3, 15)
            if opening + delta < 0:
                delta = abs(delta)
            bad_rows = [list(r) for r in rows]
            bad_rows[0][1] = opening + delta
            flawed = _unit(head, place, bad_rows, closing, shrink, counter)
            planted.append({"unit": i, "rule": "CONV-LA", "relation": "sum_mismatch", "kind": kind,
                            "field_label": "closing quantity", "value_a": closing + delta,
                            "value_b": closing, "links": {"depends_on_unit": i - 1}})
        elif kind == "carry_mismatch":
            received_row = rows[1][1]
            if received_row >= 3:
                delta = rng.randint(3, min(15, received_row))
            else:
                delta = -rng.randint(3, min(15, opening)) if opening >= 3 else 3
            bad_rows = [list(r) for r in rows]
            bad_rows[0][1] = opening + delta
            bad_rows[1][1] = received_row - delta
            if bad_rows[0][1] < 0 or bad_rows[1][1] < 0:
                raise ValueError("no carry mismatch that keeps the rows non-negative")
            flawed = _unit(head, place, bad_rows, closing, shrink, counter)
            planted.append({"unit": i, "rule": "CONV-LA", "relation": "carry_mismatch", "kind": kind,
                            "field_label": "quantity row1", "value_a": opening,
                            "value_b": opening + delta, "links": {"depends_on_unit": i - 1},
                            "extra": {"chain_label": "closing quantity"}})
        elif kind == "carry_out":
            delta = rng.choice([-1, 1]) * rng.randint(3, 15)
            flawed = _unit(head, place, rows, closing + delta, shrink, counter)
            planted.append({"unit": i, "rule": "CONV-LA", "relation": "sum_mismatch", "kind": kind,
                            "field_label": "closing quantity", "value_a": closing,
                            "value_b": closing + delta, "links": {"depends_on_unit": i + 1}})
        elif kind in ("shrinkage_above", "shrinkage_below"):
            bad = round(rng.uniform(3.4, 6.0), 1) if kind == "shrinkage_above" else round(rng.uniform(0.0, 0.3), 1)
            flawed = _unit(head, place, rows, closing, bad, counter)
            planted.append({"unit": i, "rule": "CONV-LB",
                            "relation": "above_band" if kind == "shrinkage_above" else "below_band",
                            "kind": kind, "field_label": "shrinkage", "value_a": bad,
                            "value_b": HIGH if kind == "shrinkage_above" else LOW})
        elif kind == "missing_counter":
            flawed = _unit(head, place, rows, closing, shrink, None)
            planted.append({"unit": i, "rule": "CONV-LC", "relation": "missing_field", "kind": kind,
                            "field_label": "counted", "value_a": 0, "value_b": 1})
        doc_units.append(flawed)
        twin_units.append(clean_u)
        opening = closing
    title = "Stock count " + wl.letters_tag(rng).title()
    preamble = "This record lists the successive stock counts of one store, each carried into the next."
    doc = md.Doc(title, preamble, doc_units)
    twin = md.Doc(title, preamble, twin_units)
    reference = ("procedure", "Count procedure", [
        ("prose", "Each count opens with the closing quantity of the count before it."),
        ("prose", "Issued quantities are written as negative movements."),
    ])
    conv = md.Conventions("Count conventions", "These rules govern the stock count record.", RULES)
    keep = []
    for p in planted:
        if "links" in p:
            keep.append((p["unit"], p["links"]["depends_on_unit"]))
    above = [p for p in planted if p["kind"] == "shrinkage_above"][0]
    carry = [p for p in planted if p["kind"] == "carry_out"][0]
    stated = doc_units[carry["unit"]].line_value("Closing quantity")
    return {
        "family": FAMILY, "family_name": NAME, "seed": seed, "mode": "single",
        "doc": doc, "twin": twin, "conventions": conv, "references": [reference],
        "planted": planted, "clean": clean, "doc_stem": "counts", "conv_stem": "rules",
        "ground_truth_checks": GROUND_TRUTH,
        "task": "Review the stock count record against the count conventions, reading each count beside the counts next to it.",
        "probes": {
            "reword": {"old": "Closing quantity", "new": "Quantity at close"},
            # A rotation: the last count (which closes at the first count's opening)
            # comes before the first, so every neighbour pair still carries.
            "reorder": wl.rotate(n, rng, keep),
            # probe 3: the term only in the later version carries a keyed flaw
            "term": {"unit": above["unit"], "label": "Shrinkage"},
            "reformat": {"unit": carry["unit"], "label": "Closing quantity",
                         "text": stated.replace(" box", ".0 box")},
        },
    }
