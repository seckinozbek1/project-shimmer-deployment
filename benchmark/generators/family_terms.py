"""Family 4: contract terms across two or three versions (a negotiation-style test,
section 9, that is also a declared multi-round case).

The version before the last is the prior; the last version is the target; the
conventions file is the mandate, one rule per term of the target, each stating the band
that side wants (section 6, "Negotiation-style tests"). The key is negotiation-style:
`prior_records` (the change records a correct reviewer writes, unchanged ones included)
and `band_irregularities` (every band breach in the later version), plus fields the
scorer ignores: `version_changes` (the family's own plan of every term), `rename_probes`
(one typed row per rename-probe kind), `expected_refusals`, `clean`, and per band row
`unit_id`, `value_b` and `kind`.

Every expectation is GROUND TRUTH, decided here from what this family planted, never
from what Shimmer computes (D-042): a term renamed with its value unchanged or moved is
the same term, so a correct reviewer does not call it withdrawn (a refusal, or a matched
rename, satisfies the key; a withdrawal record is a false positive); a term truly
withdrawn is `absent_since_prior`, also when an unrelated new term sits in the same
section in the same measure; a renamed term moved to another section is not withdrawn.

Version changes planted between the prior and the target: terms unchanged, terms
changed inside the band, terms moved toward or away from the band, a term renamed with
its value unchanged, a term renamed with its value moved (by a seeded 2.05 to 45
percent, so never within 2% of the larger figure; its twin's repair is such a move
too), a term renamed and moved to another section (also by 2.05 to 45 percent), a
withdrawn term, a withdrawn term beside an unrelated new term in the same measure, terms
new in the later version, sections reordered, and a value written in a different format
(unchanged).

The flaws (band breaches in the later version) come in six kinds: a breach left
unchanged, a breach the later version moved into, a breach the later version moved
toward the band but not into it, a breach on a new term, a breach on a renamed term,
and a breach on a value written in a different format.

With `rounds=3` an earliest version comes first: the prior with three ordinary terms
at other figures, same labels, same section order. It is a grounding file, never a
declared prior, and only the case manifest names it (round r1). Every bundle carries
the live case manifest (`multi_round_case.py`) and holds only case documents in
`context/` (INPUT_FORMAT section 12): no reference file.
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
    ("Rebate threshold", "EUR", 2000, 8000, 0, "Rebate trigger", "Discount floor"),
    ("Batch size", "box", 20, 80, 0, "Lot size", "Run quantity"),
    ("Reporting lag", "days", 5, 15, 0, "Report delay", "Statement gap"),
    ("Support hours", "hours", 20, 60, 0, "Help hours", "Assistance time"),
    ("Uptime target", "%", 95.0, 99.5, 1, "Availability goal", "Service level"),
]
# A moved rename moves by a seeded 2.05 to 45 percent of the earlier figure. The low end
# sits above 2/0.98 = 2.0408 percent, so a moved figure is never within 2% of the larger
# of the two (section 6's possible-rename window), whichever way it moves.
MOVE_LOW, MOVE_HIGH = 0.0205, 0.45
RENAME_WINDOW = 0.02     # section 6: within 2% of the larger figure in absolute value

# The ground-truth expectation for each rename-probe kind. The honest refusal a blind
# reviewer may give instead of matching the rename follows from the planted figures
# (expected_refusal_kind), never from the role.
RENAME_KINDS = {
    "renamed_unchanged": ("renamed_value_unchanged", "same_term_new_label"),
    "breach_renamed_moved": ("renamed_value_moved", "same_term_new_label_moved_value"),
    "renamed_moved_section": ("renamed_moved_to_other_section", "same_term_new_label_other_section"),
}


def expected_refusal_kind(before, after, same_section):
    """The refusal kind the planted figures support (INPUT_FORMAT sections 6 and 9):
    another section, any refusal (None); the figures within 2% of the larger,
    `possible_rename`; otherwise `possible_successor`."""
    if not same_section:
        return None
    if abs(after - before) <= RENAME_WINDOW * max(abs(before), abs(after)):
        return "possible_rename"
    return "possible_successor"


def in_move_range(before, after):
    """A moved rename's figures: moved by MOVE_LOW to MOVE_HIGH of the earlier figure,
    and so never within 2% of the larger."""
    p = abs(after - before) / abs(before)
    return (MOVE_LOW <= p <= MOVE_HIGH
            and abs(after - before) > RENAME_WINDOW * max(abs(before), abs(after)))


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


def moved_percent(before, after):
    """How far a figure moved, in percent of the earlier figure."""
    return round(abs(after - before) * 100.0 / abs(before), 2)


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


def _moved_from(rng, t, later, inside=False):
    """An earlier figure from which `later` moved by a seeded 2.05 to 45 percent (of the
    earlier figure), optionally itself inside the band."""
    lo, hi, dec = t[2], t[3], t[4]
    for _ in range(2000):
        m = rng.uniform(MOVE_LOW, MOVE_HIGH)
        before = round(later / (1 + rng.choice([-1, 1]) * m), dec)
        if before <= 0 or tr.same(before, later):
            continue
        if inside and not lo < before < hi:
            continue
        if in_move_range(before, later):
            return float(before)
    raise ValueError("no moved earlier figure for %s" % t[0])


def _moved_to_band(rng, t, before):
    """A figure inside the band (bounds included) moved from `before` by 2.05 to 45
    percent: the twin of a moved rename, which stays a moved rename; None if none."""
    lo, hi, dec = t[2], t[3], t[4]
    for _ in range(400):
        v = round(before * (1 + rng.choice([-1, 1]) * rng.uniform(MOVE_LOW, MOVE_HIGH)), dec)
        if lo <= v <= hi and in_move_range(before, v):
            return float(v)
    return None


def _inside_moved(rng, t):
    """(earlier, later), both inside the band, the later moved by 2.05 to 45 percent."""
    for _ in range(200):
        later = _values(rng, t, "inside")
        try:
            return _moved_from(rng, t, later, inside=True), later
        except ValueError:
            continue
    raise ValueError("no inside move for %s" % t[0])


ROUND_CHANGES = 3          # ordinary terms at another figure in the earliest version
REUSE_ROLES = ("breach_moved_away", "breach_moved_toward", "changed_inside", "moved_into_band",
               "unchanged_inside")
SPECIAL = ("breach_new_term", "breach_renamed_moved", "renamed_unchanged", "withdrawn",
           "withdrawn_beside_newcomer", "newcomer_unrelated", "renamed_moved_section")


def _earliest(seed, terms, prior_units, prior_order, title, preamble):
    """The earliest version (round r1 of a three-round case): the prior with
    ROUND_CHANGES ordinary terms, in distinct sections, at a figure more than 5% away.
    Its own random stream."""
    rng = wl.make_rng(FAMILY + "-rounds", seed)
    pool = [e for e in terms if e["role"] in REUSE_ROLES and e["prior"] is not None]
    rng.shuffle(pool)
    chosen, units = [], set()
    for e in pool:
        if e["prior_unit"] not in units:
            chosen.append(e)
            units.add(e["prior_unit"])
        if len(chosen) == ROUND_CHANGES:
            break
    if len(chosen) != ROUND_CHANGES:
        raise ValueError("no earliest-version changes")
    early_units = [u.clone() for u in prior_units]
    changes = []
    for e in chosen:
        for _ in range(500):
            v = _values(rng, e["t"], rng.choice(["inside", "above", "below"]))
            if abs(v - e["prior"]) > 0.05 * max(abs(v), abs(e["prior"])):
                break
        else:
            raise ValueError("no earliest value for %s" % e["label"])
        early_units[e["prior_unit"]].set_line(e["label"], _fmt(e["t"], v))
        changes.append({"field_label": tr.norm(e["label"]),
                        "prior_position": prior_order.index(e["prior_unit"]),
                        "value_before": tr.r6(v), "value_after": tr.r6(e["prior"]), "unit": e["t"][1]})
    changes.sort(key=lambda c: c["field_label"])
    return md.Doc(title, preamble, [early_units[i] for i in prior_order]), changes


def _pick_roles(rng):
    """(role, term) pairs. The withdrawal beside a newcomer and its newcomer share a
    measure; every other term is drawn at random."""
    exit_term = [t for t in TERMS if t[0] == "Exit charge"][0]
    pool = [t for t in TERMS if t is not exit_term]
    rng.shuffle(pool)
    by_measure = {}
    for t in pool:
        by_measure.setdefault(t[1], []).append(t)
    pair_measure = rng.choice(sorted(m for m, ts in by_measure.items() if len(ts) >= 2))
    gone, newcomer = by_measure[pair_measure][:2]
    pool = [t for t in pool if t is not gone and t is not newcomer]
    roles = [("breach_reformatted", exit_term), ("withdrawn_beside_newcomer", gone),
             ("newcomer_unrelated", newcomer)]
    breach_roles = (["breach_unchanged"] * 2 + ["breach_moved_away"] * 3
                    + ["breach_moved_toward"] * 2 + ["breach_new_term", "breach_renamed_moved"])
    other_roles = ["unchanged_inside", "changed_inside", "moved_into_band", "renamed_unchanged",
                   "withdrawn", "at_bound", "renamed_moved_section"]
    for r in breach_roles + other_roles:
        roles.append((r, pool.pop()))
    return roles


def build(seed, rounds=2):
    if rounds not in (2, 3):
        raise ValueError("family 4 writes two or three rounds")
    rng = wl.make_rng(FAMILY, seed)
    terms = []
    for role, t in _pick_roles(rng):
        label, meas, lo, hi, dec, alt, alt2 = t
        side = rng.choice(["above", "below"])
        e = {"role": role, "t": t, "label": label, "later_label": label, "prior": None, "later": None,
             "twin": None, "kind": None}
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
        elif role in ("breach_new_term", "newcomer_unrelated"):
            e["later"] = _values(rng, t, side if role == "breach_new_term" else "inside")
        elif role == "breach_renamed_moved":
            # The breach and its twin's repair are both moves of 2.05 to 45 percent from
            # the earlier figure, so the twin's rename is a moved rename too.
            for _ in range(500):
                e["later"] = _values(rng, t, side)
                e["prior"] = _moved_from(rng, t, e["later"])
                e["twin"] = _moved_to_band(rng, t, e["prior"])
                if e["twin"] is not None:
                    break
            else:
                raise ValueError("no moved rename with a moved twin for %s" % label)
            e["later_label"] = alt
        elif role == "renamed_moved_section":
            e["prior"], e["later"] = _inside_moved(rng, t)
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
        elif role in ("withdrawn", "withdrawn_beside_newcomer"):
            e["prior"] = _values(rng, t, "inside")
        elif role == "at_bound":
            e["prior"] = e["later"] = float(rng.choice([lo, hi]))
        if role.startswith("breach_"):
            e["side"] = side
            e["kind"] = role
            # the twin repairs the breach inside the band, more than 5% from the earlier
            # figure (a moved rename's twin is already drawn above)
            if role != "breach_renamed_moved":
                for _ in range(200):
                    tv = _values(rng, t, "inside")
                    if e["prior"] is None or abs(tv - e["prior"]) > 0.05 * abs(e["prior"]):
                        break
                e["twin"] = tv
        else:
            e["twin"] = e["later"]
        terms.append(e)
    # Units. Each special term sits beside one ordinary partner (never a breach left
    # unchanged, which probe 3 uses); the withdrawal beside a newcomer shares its unit
    # with that newcomer; the renamed term moved to another section leaves its earlier
    # unit (which keeps its partner) for a plain unit of its own; a clean distractor
    # unit holds the term on its bound and an unchanged term; the rest one or two per unit.
    by_role = {}
    for e in terms:
        by_role.setdefault(e["role"], []).append(e)
    reserved = by_role["at_bound"] + by_role["unchanged_inside"]
    ordinary = [e for e in terms if e["role"] not in SPECIAL and e not in reserved]
    rng.shuffle(ordinary)
    partners = [e for e in ordinary if e["role"] != "breach_unchanged"]
    groups = []
    for role in ("breach_new_term", "breach_renamed_moved", "renamed_unchanged", "withdrawn",
                 "renamed_moved_section"):
        groups.append([partners.pop(), by_role[role][0]])
    groups.append([partners.pop()] + by_role["withdrawn_beside_newcomer"] + by_role["newcomer_unrelated"])
    groups.append(reserved)
    rest = [e for e in ordinary if not any(e in g for g in groups)]
    plain = []
    while rest:
        k = 2 if len(rest) >= 2 and rng.random() < 0.5 else 1
        plain.append([rest.pop() for _ in range(k)])
        groups.append(plain[-1])
    rng.shuffle(groups)
    moved = by_role["renamed_moved_section"][0]
    later_home = rng.choice(plain)
    for gi, g in enumerate(groups):
        for e in g:
            e["unit"] = e["prior_unit"] = gi
    moved["unit"] = groups.index(later_home)
    heads = wl.pick(rng, wl.BIRDS, len(groups))
    later_units, prior_units, twin_units = [], [], []
    for gi, h in enumerate(heads):
        lu, pu, tu = [], [], []
        members = groups[gi] + ([moved] if moved["unit"] == gi else [])
        for e in members:
            if e["later"] is not None and e["unit"] == gi:
                grouped = e["role"] == "breach_reformatted"
                lu.append([e["later_label"], _fmt(e["t"], e["later"], grouped)])
                tu.append([e["later_label"], _fmt(e["t"], e["twin"], grouped)])
            if e["prior"] is not None and e["prior_unit"] == gi:
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

    def plan_row(e, which, dropped=None):
        """The family's own ground truth for one term (D-042)."""
        lo, hi = e["t"][2], e["t"][3]
        now = e[which]
        then = None if e is dropped else e["prior"]
        meas = e["t"][1]
        ln, lp = tr.norm(e["later_label"]), tr.norm(e["label"])
        v = {"field_label": lp, "later_field_label": None, "change": e["role"], "expect": None,
             "value_a": None, "value_b": then, "unit": meas, "section": None}
        if e["role"] in ("withdrawn", "withdrawn_beside_newcomer"):
            v["expect"] = "absent_since_prior"
        elif then is None:
            v.update(field_label=ln, change="new_in_later_version", expect="none", value_a=now)
        elif e["role"] in RENAME_KINDS:
            v.update(later_field_label=ln, expect="not_withdrawn", value_a=now,
                     section="other" if e["unit"] != e["prior_unit"] else "same")
        else:
            v.update(change="value_in_different_format" if e["role"] == "breach_reformatted" else e["role"],
                     expect=_orient(then, now, lo, hi), value_a=now)
        for f in ("value_a", "value_b"):
            if v[f] is not None:
                v[f] = tr.r6(v[f])
        return v

    def plan(which, dropped=None):
        return sorted((plan_row(e, which, dropped) for e in terms), key=lambda v: v["field_label"])

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
    # One typed row per rename-probe kind, from the same ground truth; units are the
    # target's and the prior's unit indexes, mapped to the bundle's ids when written.
    probe_kinds = {"withdrawn": ("withdrawn", "no_successor"),
                   "withdrawn_beside_newcomer": ("withdrawn_beside_newcomer",
                                                 "unrelated_newcomer_same_measure"),
                   "breach_new_term": ("new_in_later_version", "not_stated_in_earlier_version"),
                   "breach_reformatted": ("value_in_different_format", "comma_grouped_digits")}
    probe_kinds.update(RENAME_KINDS)

    def rename_probes(which):
        out = []
        for e in terms:
            if e["role"] not in probe_kinds:
                continue
            kind, reason = probe_kinds[e["role"]]
            now = e[which]
            refusal = None
            if e["role"] in RENAME_KINDS:
                refusal = expected_refusal_kind(e["prior"], now, e["unit"] == e["prior_unit"])
            lp, ln = tr.norm(e["label"]), tr.norm(e["later_label"])
            v = plan_row(e, which)
            row = {"kind": kind, "field_label": ln if e["prior"] is None else lp,
                   "later_field_label": ln if now is not None else None,
                   "unit_id": e["unit"] if now is not None else None,
                   "prior_unit_id": e["prior_unit"] if e["prior"] is not None else None,
                   "prior_order": [],
                   "value_before": tr.r6(e["prior"]) if e["prior"] is not None else None,
                   "value_after": tr.r6(now) if now is not None else None, "unit": e["t"][1],
                   "written_before": _fmt(e["t"], e["prior"]) if e["prior"] is not None else None,
                   "written_after": (_fmt(e["t"], now, e["role"] == "breach_reformatted")
                                     if now is not None else None),
                   "moved_percent": (moved_percent(e["prior"], now)
                                     if e["prior"] is not None and now is not None else None),
                   "expect": v["expect"], "reason": reason, "refusal_kind": refusal,
                   "satisfied_by": None, "false_positive_if": None}
            if v["expect"] == "not_withdrawn":
                row["satisfied_by"] = ["refusal", "matched_rename"]
                row["false_positive_if"] = "absent_since_prior"
            elif v["expect"] == "absent_since_prior":
                row["satisfied_by"] = ["absent_since_prior"]
            out.append(row)
        out.append({"kind": "reordered_sections", "field_label": None, "later_field_label": None,
                    "unit_id": None, "prior_unit_id": None, "prior_order": list(prior_order),
                    "value_before": None, "value_after": None, "unit": None,
                    "written_before": None, "written_after": None, "moved_percent": None,
                    "expect": "records_follow_headings", "reason": "unit_identity_by_heading",
                    "refusal_kind": None, "satisfied_by": None, "false_positive_if": None})
        return sorted(out, key=lambda r: r["kind"])

    issues = {}
    for e in terms:
        issues[e["label"]] = issues[e["later_label"]] = "issue-" + tr.slug(e["label"])
    earliest, round_changes = (None, [])
    if rounds == 3:
        earliest, round_changes = _earliest(seed, terms, prior_units, prior_order, title, preamble)
    clean_unit = [e["unit"] for e in terms if e["role"] == "at_bound"][0]
    # For the multi-round key: every label a round may write for a term the mandate
    # governs (its earlier and its later label), with that term's band, rule and issue.
    term_bands = {}
    for e in terms:
        if id(e) in rule_of:
            for lab in (e["label"], e["later_label"]):
                term_bands[lab] = {"lo": e["t"][2], "hi": e["t"][3], "rule": rule_of[id(e)],
                                   "issue": issues[lab]}
    # probes
    # The dropped term leaves its earlier unit with another line where it can.
    size = {gi: len(g) for gi, g in enumerate(groups)}
    reword_term, dropped = sorted(by_role["breach_unchanged"], key=lambda e: size[e["unit"]])
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
        "references": [],
        "bands": bands, "clean": [clean_unit],
        "version_changes": plan("later"), "twin_version_changes": plan("twin"),
        "term_version_changes": plan("later", dropped),
        "rename_probes": rename_probes("later"), "twin_rename_probes": rename_probes("twin"),
        "rounds": rounds, "earliest": earliest, "round_changes": round_changes, "issues": issues,
        "term_bands": term_bands,
        "clean_label": [e["label"] for e in terms if e["role"] == "at_bound"][0],
        "doc_stem": "terms", "conv_stem": "mandate",
        "task": "Compare the later version of the supply terms with the earlier one and review it against the mandate.",
        "probes": {
            "reword": {"old": reword_term["later_label"], "new": reword_term["t"][6]},
            "reorder": wl.reorder(len(groups), rng),
            # Probe 3: a keyed breach on a term only in the later version. The term is
            # dropped from every earlier version; the target is unchanged.
            "term": {"unit": dropped["unit"], "label": dropped["label"], "drop_from_prior": True},
            "reformat": reform,
        },
    }
