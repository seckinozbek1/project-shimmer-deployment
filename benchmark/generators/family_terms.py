"""Family 4: contract terms across two versions (a negotiation-style test, section 9).

The earlier version is the prior; the later version is the target; the conventions file
is the mandate, one rule per term of the target, each stating the band that side
wants (section 6, "Negotiation-style tests"). The key is negotiation-style:
`prior_records` (every change record Python writes, unchanged ones included) and
`band_irregularities` (every irregular band finding), plus fields the scorer ignores:
`version_changes` (the family's own plan, computed here from its own figures and
checked against the audit), `clean`, and per band row `unit_id`, `value_b` and `kind`.

Version changes planted between the two versions: terms unchanged, terms changed
inside the band, terms moved toward or away from the band, a term renamed with its
value unchanged (refused as a possible rename, no record), a term renamed with its
value moved (absent_since_prior on the old label), a withdrawn term (absent_since_prior),
a term new in the later version (no record), sections reordered, and a value written
in a different format (unchanged).

The flaws (band irregularities in the later version) come in six kinds: a breach left
unchanged, a breach the later version moved into, a breach the later version moved
toward the band but not into it, a breach on a new term, a breach on a renamed term,
and a breach on a value written in a different format.

The two-version form only. The three-version (multi-round) case declaration waits for
S2 and is not written here (see README.md, TODO).
"""
from . import model as md
from . import textrules as tr
from . import wordlists as wl

FAMILY = "f4"
NAME = "contract terms across versions"

# label, measure, low, high, decimals, renamed label, reworded label (probe 1)
TERMS = [
    ("Annual fee", "%", 2.0, 4.0, 1, "Yearly fee", "Fee per annum"),
    ("Notice period", "days", 30, 60, 0, "Notice interval", "Advance warning"),
    ("Deposit amount", "EUR", 500, 2000, 0, "Security deposit", "Upfront sum"),
    ("Payment term", "days", 15, 45, 0, "Settlement term", "Days to pay"),
    ("Late charge", "EUR", 50, 200, 0, "Overdue charge", "Arrears levy"),
    ("Service credit", "%", 5.0, 15.0, 1, "Service rebate", "Outage refund"),
    ("Renewal cap", "%", 1.0, 3.0, 1, "Renewal ceiling", "Price uplift maximum"),
    ("Liability limit", "EUR", 10000, 50000, 0, "Maximum liability", "Liability ceiling"),
    ("Minimum volume", "box", 100, 400, 0, "Volume floor", "Order quantity"),
    ("Response time", "hours", 4, 24, 0, "Reply time", "Reaction delay"),
    ("Warranty length", "months", 12, 36, 0, "Warranty duration", "Guarantee span"),
    ("Exit charge", "EUR", 1000, 5000, 0, "Termination charge", "Leaving fee"),
    ("Audit interval", "months", 6, 24, 0, "Inspection interval", "Review frequency"),
    ("Cure window", "days", 10, 30, 0, "Remedy window", "Repair allowance"),
    ("Training allowance", "hours", 8, 40, 0, "Training budget", "Instruction quota"),
    ("Storage charge", "EUR", 100, 600, 0, "Warehousing charge", "Holding cost"),
    ("Interest margin", "%", 1.0, 4.0, 1, "Interest spread", "Rate premium"),
    ("Delivery window", "days", 5, 20, 0, "Delivery lead", "Shipping lag"),
]
NEW_TERM_PROBE = ("Review cycle", "6 months")


def _fmt(t, v, grouped=False):
    label, meas, lo, hi, dec = t[:5]
    s = tr.format_number(v, dec, grouped)
    return s + "%" if meas == "%" else "%s %s" % (s, meas)


def _dist(v, lo, hi):
    return 0.0 if lo <= v <= hi else min(abs(v - lo), abs(v - hi))


def _orient(prior, now, lo, hi):
    if tr.same(prior, now):
        return "unchanged_from_prior"
    da, db = _dist(now, lo, hi), _dist(prior, lo, hi)
    if tr.same(da, db):
        return "changed_from_prior"
    return "moved_toward" if da < db else "moved_away"


def _values(rng, t, how):
    lo, hi, dec = t[2], t[3], t[4]
    s = hi - lo
    for _ in range(500):
        if how == "inside":
            v = round(rng.uniform(lo + 0.2 * s, hi - 0.2 * s), dec)
            ok = lo < v < hi
        elif how == "above":
            v = round(hi + s * rng.uniform(0.2, 0.6), dec)
            ok = v > hi
        elif how == "far_above":
            v = round(hi + s * rng.uniform(0.9, 1.3), dec)
            ok = v > hi
        elif how == "below":
            v = round(lo * rng.uniform(0.4, 0.7), dec)
            ok = 0 < v < lo
        elif how == "far_below":
            v = round(lo * rng.uniform(0.05, 0.2), dec)
            ok = 0 <= v < lo
        else:
            raise ValueError(how)
        if ok:
            return float(v)
    raise ValueError("no value for %s %s" % (t[0], how))


def build(seed):
    rng = wl.make_rng(FAMILY, seed)
    exit_term = [t for t in TERMS if t[0] == "Exit charge"][0]
    pool = [t for t in TERMS if t is not exit_term]
    rng.shuffle(pool)
    breach_roles = (["breach_unchanged"] * 2 + ["breach_moved_away"] * 3
                    + ["breach_moved_toward"] * 2 + ["breach_new_term", "breach_renamed_moved"])
    other_roles = ["unchanged_inside", "changed_inside", "moved_into_band", "renamed_unchanged",
                   "withdrawn", "at_bound"]
    roles = [("breach_reformatted", exit_term)]
    for r in breach_roles + other_roles:
        roles.append((r, pool.pop()))
    # values: prior and later (target) and the twin's later value
    terms = []
    for role, t in roles:
        label, meas, lo, hi, dec, alt, alt2 = t
        side = rng.choice(["above", "below"])
        e = {"role": role, "t": t, "label": label, "later_label": label, "prior": None, "later": None,
             "twin": None, "relation": None, "kind": None}
        if role == "breach_reformatted":
            e["prior"] = e["later"] = _values(rng, t, "above")
            side = "above"
        elif role == "breach_unchanged":
            e["prior"] = e["later"] = _values(rng, t, side)
        elif role == "breach_moved_away":
            e["prior"] = _values(rng, t, "inside")
            e["later"] = _values(rng, t, side)
        elif role == "breach_moved_toward":
            e["prior"] = _values(rng, t, "far_" + side)
            for _ in range(200):
                e["later"] = _values(rng, t, side)
                if _dist(e["later"], lo, hi) < _dist(e["prior"], lo, hi):
                    break
            else:
                raise ValueError("no move toward")
        elif role == "breach_new_term":
            e["later"] = _values(rng, t, side)
        elif role == "breach_renamed_moved":
            e["prior"] = _values(rng, t, "inside")
            e["later"] = _values(rng, t, side)
            e["later_label"] = alt
        elif role == "unchanged_inside":
            e["prior"] = e["later"] = _values(rng, t, "inside")
        elif role == "changed_inside":
            e["prior"] = _values(rng, t, "inside")
            for _ in range(200):
                e["later"] = _values(rng, t, "inside")
                if not tr.same(e["later"], e["prior"]):
                    break
        elif role == "moved_into_band":
            e["prior"] = _values(rng, t, rng.choice(["above", "below"]))
            e["later"] = _values(rng, t, "inside")
        elif role == "renamed_unchanged":
            e["prior"] = e["later"] = _values(rng, t, "inside")
            e["later_label"] = alt
        elif role == "withdrawn":
            e["prior"] = _values(rng, t, "inside")
        elif role == "at_bound":
            e["prior"] = e["later"] = float(rng.choice([lo, hi]))
        if role.startswith("breach_"):
            e["side"] = side
            e["kind"] = role
            # the twin repairs the breach inside the band, more than 2% from the earlier figure
            for _ in range(200):
                tv = _values(rng, t, "inside")
                if e["prior"] is None or abs(tv - e["prior"]) > 0.05 * abs(e["prior"]):
                    break
            e["twin"] = tv
        else:
            e["twin"] = e["later"]
        terms.append(e)
    # units: four special terms each beside one ordinary partner, a clean distractor
    # unit (at_bound with unchanged_inside), the rest one or two per unit
    special = [e for e in terms if e["role"] in ("breach_new_term", "breach_renamed_moved",
                                                 "renamed_unchanged", "withdrawn")]
    reserved = [e for e in terms if e["role"] in ("at_bound", "unchanged_inside")]
    ordinary = [e for e in terms if e not in special and e not in reserved]
    rng.shuffle(ordinary)
    groups = []
    for s in special:
        groups.append([ordinary.pop(), s])
    groups.append(reserved)
    while ordinary:
        k = 2 if len(ordinary) >= 2 and rng.random() < 0.5 else 1
        groups.append([ordinary.pop() for _ in range(k)])
    rng.shuffle(groups)
    heads = wl.pick(rng, wl.BIRDS, len(groups))
    later_units, prior_units, twin_units = [], [], []
    for gi, (g, h) in enumerate(zip(groups, heads)):
        lu, pu, tu = [], [], []
        for e in g:
            e["unit"] = gi
            if e["later"] is not None:
                grouped = e["role"] == "breach_reformatted"
                lu.append([e["later_label"], _fmt(e["t"], e["later"], grouped)])
                tu.append([e["later_label"], _fmt(e["t"], e["twin"], grouped)])
            if e["prior"] is not None:
                pu.append([e["label"], _fmt(e["t"], e["prior"])])
        later_units.append(md.Unit("Clause " + h, [("lines", lu)]))
        twin_units.append(md.Unit("Clause " + h, [("lines", tu)]))
        prior_units.append(md.Unit("Clause " + h, [("lines", pu)]))
    prior_order = wl.reorder(len(prior_units), rng)
    title = "Supply terms " + wl.letters_tag(rng).title()
    preamble = "These terms govern the supply agreement between the two parties."
    doc = md.Doc(title, preamble, later_units)
    twin = md.Doc(title, preamble, twin_units)
    prior = md.Doc(title, preamble, [prior_units[i] for i in prior_order])
    # the mandate: one rule per term the later version states, in reading order
    rules, rule_of = [], {}
    for u_i in range(len(groups)):
        for e in terms:
            if e["unit"] == u_i and e["later"] is not None:
                rid = "CONV-T" + chr(ord("A") + len(rules))
                lo, hi = e["t"][2], e["t"][3]
                text = "The %s must lie between %s and %s." % (
                    e["later_label"].lower(), _fmt(e["t"], lo), _fmt(e["t"], hi))
                rules.append(md.Rule(rid, e["later_label"], text))
                rule_of[id(e)] = rid
    conv = md.Conventions("Mandate", "These rules state the reviewing side's position on each term.", rules)
    # the family's own plan of change records, from its own figures
    def plan(which):
        out = []
        for e in terms:
            lo, hi = e["t"][2], e["t"][3]
            now = e[which]
            meas = e["t"][1]
            ln, lp = tr.norm(e["later_label"]), tr.norm(e["label"])
            if e["role"] == "withdrawn":
                out.append({"field_label": lp, "change": "withdrawn", "expect": "absent_since_prior",
                            "value_a": None, "value_b": e["prior"], "unit": meas})
            elif e["role"] == "breach_new_term":
                out.append({"field_label": ln, "change": "new_in_later_version", "expect": "none",
                            "value_a": now, "value_b": None, "unit": meas})
            elif e["role"] in ("renamed_unchanged", "breach_renamed_moved"):
                # refused as a possible rename within 2% of the larger figure, inclusive
                moved = abs(now - e["prior"]) > 0.02 * max(abs(now), abs(e["prior"]))
                out.append({"field_label": lp, "change": "renamed_to_" + ln.replace(" ", "_"),
                            "expect": "absent_since_prior" if moved else "refused",
                            "value_a": None, "value_b": e["prior"], "unit": meas})
            else:
                out.append({"field_label": lp,
                            "change": "value_in_different_format" if e["role"] == "breach_reformatted" else e["role"],
                            "expect": _orient(e["prior"], now, lo, hi),
                            "value_a": now, "value_b": e["prior"], "unit": meas})
        for v in out:
            for f in ("value_a", "value_b"):
                if v[f] is not None:
                    v[f] = tr.r6(v[f])
        return sorted(out, key=lambda v: v["field_label"])
    bands = []
    for e in terms:
        if not e["role"].startswith("breach_"):
            continue
        lo, hi = e["t"][2], e["t"][3]
        above = e["later"] > hi
        bands.append({"unit": e["unit"], "field_label": tr.norm(e["later_label"]),
                      "relation": "above_band" if above else "below_band",
                      "value_a": e["later"], "value_b": hi if above else lo,
                      "rule": rule_of[id(e)], "kind": e["kind"]})
    bands.sort(key=lambda b: (b["unit"], b["field_label"]))
    clean_unit = [e["unit"] for e in terms if e["role"] == "at_bound"][0]
    # probes
    unchanged_breach = [e for e in terms if e["role"] == "breach_unchanged"][0]
    plain_units = [gi for gi, g in enumerate(groups)
                   if not any(e in special for e in g)]
    reform = None
    for e in terms:
        if e["role"] in ("breach_moved_away", "changed_inside", "moved_into_band") and e["later"] is not None:
            v = e["later"]
            if v >= 1000:
                text = _fmt(e["t"], v, True)
            elif e["t"][4] == 0:
                text = _fmt(e["t"], v).replace(" ", ".0 ", 1)
            else:
                text = _fmt(e["t"], v).replace("%", "0%")
            reform = {"unit": e["unit"], "label": e["later_label"], "text": text}
            break
    return {
        "family": FAMILY, "family_name": NAME, "seed": seed, "mode": "negotiation",
        "doc": doc, "twin": twin, "prior": prior, "conventions": conv,
        "references": [("note", "Negotiation note", [
            ("prose", "The parties exchange successive versions of the supply terms."),
            ("prose", "Each version restates every term that remains on the table.")])],
        "bands": bands, "clean": [clean_unit],
        "version_changes": plan("later"), "twin_version_changes": plan("twin"),
        "doc_stem": "terms", "conv_stem": "mandate",
        "task": "Compare the later version of the supply terms with the earlier one and review it against the mandate.",
        "probes": {
            "reword": {"old": unchanged_breach["later_label"], "new": unchanged_breach["t"][6]},
            "reorder": wl.reorder(len(groups), rng),
            "term": {"unit": plain_units[0], "label": NEW_TERM_PROBE[0], "value": NEW_TERM_PROBE[1]},
            "reformat": reform,
        },
    }
