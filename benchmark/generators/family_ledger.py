"""Family 6: neighbour-dependent flaws, as a running stock count.

Each count is one unit: a location, a table of movements in box whose first row is
the opening quantity carried from the count before, the stated closing quantity, the
shrinkage in percent and the counter. CONV-LA says exactly what is computed (S3 checker
round 3): the closing quantity equals the sum of the quantity column, and the opening
row carries the sum of the quantity column of the count before. Every keyed unit breaks
that text as written and every other unit keeps it; `units_breaking_carry_rule` reads it
a second time from the rendered text with plain string handling. The count procedure
(the reference file, REFERENCE_PROSE) states the same column-sum reading, and its
sentences are read against every unit too (REFERENCE_READINGS, S3 tie-break item 1).

Neighbour-dependent kinds (each with `depends_on_unit`, the neighbour it depends on):
- carry_in: the opening row was mis-carried from the count before (it is not that
  count's column sum); the stated closing quantity is right given that neighbour.
  Python sees a sum mismatch in the unit; only the neighbour says which figure is wrong
  (the opening row). The count after a carry_in carries the carry_in's column sum, the
  mis-carried figure included, and its issued (or received) row absorbs the difference,
  so it adds up on its own and closes as the twin's does: a clean distractor, which
  read beside its neighbour's stated closing looks mis-carried, and is not. A carry_in
  is never the last count, whose successor in the reordered-sections probe is the first.
- carry_out: the stated closing quantity is wrong; the count after carries the column
  sum as its opening. Python sees a sum mismatch; only the next count confirms the
  computed sum. The count after a carry_out is a clean distractor in the same way.
- carry_mismatch: wrong ONLY given the neighbour. The opening row differs from the
  column sum of the count before, and the received row absorbs the difference, so each
  count adds up on its own and only the pair shows the flaw. Python compares no two
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
            "must carry the sum of the quantity column of the count before it."),
    md.Rule("CONV-LB", "Shrinkage", "The shrinkage must lie between 0.5% and 3%."),
    md.Rule("CONV-LC", "Counter", "Every stock count must state who counted it.",
            scope=["movement"], requires=["counted by"]),
]
GROUND_TRUTH = [{"check": "carry", "kind": "carry_mismatch", "rule": "CONV-LA",
                 "closing": "closing quantity", "column": "quantity"}]
# What each keyed kind's rule text must state (bundle.check_rule_statements reads the
# rendered conventions): the clause a unit of that kind breaks as written.
RULE_STATEMENTS = {
    "carry_in": ("the closing quantity must equal the sum of the quantity column",),
    "carry_out": ("the closing quantity must equal the sum of the quantity column",),
    "carry_mismatch": ("the opening row must carry the sum of the quantity column of the count before it",),
    "shrinkage_above": ("the shrinkage must lie between 0.5% and 3%",),
    "shrinkage_below": ("the shrinkage must lie between 0.5% and 3%",),
    "missing_counter": ("must state who counted it",),
}


# The count procedure, the family's reference file (a grounding file), one paragraph per
# sentence. It states what CONV-LA states, in the column-sum reading (S3 tie-break item
# 1): it used to say "Each count opens with the closing quantity of the count before
# it", which the clean count after every carry_out and carry_in contradicts.
REFERENCE_PROSE = (
    "Each count opens with the sum of the quantity column of the count before it.",
    "The closing quantity of each count is the sum of its own quantity column.",
    "An issued quantity is written as a negative movement, or as zero when nothing was issued.",
)


def _column(u):
    return [int(r[1]) for r in u["rows"] if len(r) == 2 and r[1].lstrip("-").isdigit()]


def _as_label(words):
    return words[:1].upper() + words[1:]


def _opens_with(units, m, label, _reference):
    """'Each count opens with the <figure> of the count before it': the figure is the sum
    of the count's quantity column, or a line the count states (the sentence's words as
    its label). The counts whose opening row is not that figure of the count before."""
    figure, out, before = m.group(1), set(), None
    for u in units:
        column = _column(u)
        if not column:
            before = None
            continue
        if before is not None and column[0] != before:
            out.add(u["id"])
        if figure == "sum of the quantity column":
            before = sum(column)
        else:
            before = tr.leading_figure(u["lines"].get(label(_as_label(figure))))
    return out


def _closes_at(units, m, label, _reference):
    """'The <line> of each count is the sum of its own quantity column': the counts whose
    stated line is missing or is not the sum of their quantity column."""
    out = set()
    for u in units:
        column = _column(u)
        if column and tr.leading_figure(u["lines"].get(label(_as_label(m.group(1))))) != sum(column):
            out.add(u["id"])
    return out


def _issued(units, _m, _label, _reference):
    """The counts with an issued row above zero."""
    return {u["id"] for u in units for r in u["rows"]
            if len(r) == 2 and r[0] == "Issued" and r[1].lstrip("-").isdigit() and int(r[1]) > 0}


# How each sentence of the reference file is read (bundle.check_reference_texts): a
# pattern the whole sentence matches, and the reader that names the units breaking it.
REFERENCE_READINGS = (
    (r"Each count opens with the (.+) of the count before it\.", _opens_with),
    (r"The (.+) of each count is the sum of its own quantity column\.", _closes_at),
    (r"An issued quantity is written as a negative movement, or as zero when nothing was issued\.", _issued),
)


def units_breaking_carry_rule(text, closing_label="Closing quantity"):
    """An independent second reading of CONV-LA as written, straight from a rendered
    document with plain string handling (no audit, no scanner): the headings of the
    counts whose closing quantity is not the sum of their quantity column, or whose
    opening row is not the sum of the quantity column of the count before. The gate
    check requires them to be exactly the units keyed under CONV-LA (in the
    reworded-labels probe, `closing_label` is the label the probe writes)."""
    out, before = set(), None
    for block in text.split("\n## ")[1:]:
        heading, _, body = block.partition("\n")
        column, closing = [], None
        for ln in body.split("\n"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")] if ln.startswith("|") else []
            if len(cells) == 2 and cells[1].lstrip("-").isdigit():
                column.append(int(cells[1]))
            label, sep, value = ln.partition(": ")
            if sep and label == closing_label:
                closing = int(value.split(" ")[0].replace(",", "").split(".")[0])
        if not column or closing is None:
            before = None
            continue
        if closing != sum(column) or (before is not None and column[0] != before):
            out.add(heading)
        before = sum(column)
    return out


def _unit(head, place, rows, closing, shrink, counter):
    lines_after = [["Closing quantity", "%s box" % tr.format_number(closing, 0, closing >= 1000)],
                   ["Shrinkage", "%s%%" % tr.format_number(shrink, 1)]]
    if counter:
        lines_after.append(["Counted by", counter])
    return md.Unit(head, [("lines", [["Location", place]]),
                          ("table", ["Movement", "Quantity (box)"], [[m, str(v)] for m, v in rows]),
                          ("lines", lines_after)])


def build(seed, attempt=0):
    rng = wl.make_rng(FAMILY, seed, attempt)
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
            if kind == "carry_in" and i == n - 1:
                # its successor in the rotated probe would be the first count, which
                # opens at the true chain and not at the carry_in's column sum
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
    after_in = [i + 1 for i, k in plan.items() if k == "carry_in"]
    at_bound = rest.pop()
    clean = sorted(set(after_out + [at_bound] + [i for i in after_in if i not in plan]))
    carried_in = {}     # the count after a carry_in: the mis-carried difference it carries
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
        # The document's rows: the twin's, except in the count after a carry_in, which
        # carries that count's column sum (the mis-carried difference included) and
        # absorbs the difference in its issued row (received, when it would make the
        # issued row positive), so it adds up and closes as the twin's count does.
        shown = [list(r) for r in rows]
        if i in carried_in:
            d = carried_in[i]
            shown[0][1] = opening + d
            if d > 0:
                shown[2][1] = issued - d
            else:
                shown[1][1] = received - d
        kind = plan.get(i)
        flawed = _unit(head, place, shown, closing, shrink, counter)
        if kind == "carry_in":
            delta = rng.choice([-1, 1]) * rng.randint(3, 15)
            if opening + delta < 0:
                delta = abs(delta)
            bad_rows = [list(r) for r in shown]
            bad_rows[0][1] = opening + delta
            flawed = _unit(head, place, bad_rows, closing, shrink, counter)
            carried_in[i + 1] = delta
            planted.append({"unit": i, "rule": "CONV-LA", "relation": "sum_mismatch", "kind": kind,
                            "field_label": "closing quantity", "value_a": closing + delta,
                            "value_b": closing, "links": {"depends_on_unit": i - 1}})
        elif kind == "carry_mismatch":
            received_row = shown[1][1]
            if received_row >= 3:
                delta = rng.randint(3, min(15, received_row))
            else:
                delta = -rng.randint(3, min(15, opening)) if opening >= 3 else 3
            bad_rows = [list(r) for r in shown]
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
            flawed = _unit(head, place, shown, closing + delta, shrink, counter)
            planted.append({"unit": i, "rule": "CONV-LA", "relation": "sum_mismatch", "kind": kind,
                            "field_label": "closing quantity", "value_a": closing,
                            "value_b": closing + delta, "links": {"depends_on_unit": i + 1}})
        elif kind in ("shrinkage_above", "shrinkage_below"):
            bad = round(rng.uniform(3.4, 6.0), 1) if kind == "shrinkage_above" else round(rng.uniform(0.0, 0.3), 1)
            flawed = _unit(head, place, shown, closing, bad, counter)
            planted.append({"unit": i, "rule": "CONV-LB",
                            "relation": "above_band" if kind == "shrinkage_above" else "below_band",
                            "kind": kind, "field_label": "shrinkage", "value_a": bad,
                            "value_b": HIGH if kind == "shrinkage_above" else LOW})
        elif kind == "missing_counter":
            flawed = _unit(head, place, shown, closing, shrink, None)
            planted.append({"unit": i, "rule": "CONV-LC", "relation": "missing_field", "kind": kind,
                            "field_label": "counted", "value_a": 0, "value_b": 1})
        doc_units.append(flawed)
        twin_units.append(clean_u)
        opening = closing
    title = "Stock count " + wl.letters_tag(rng).title()
    preamble = "This record lists the successive stock counts of one store, each carried into the next."
    doc = md.Doc(title, preamble, doc_units)
    twin = md.Doc(title, preamble, twin_units)
    reference = ("procedure", "Count procedure", [("prose", s) for s in REFERENCE_PROSE])
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
