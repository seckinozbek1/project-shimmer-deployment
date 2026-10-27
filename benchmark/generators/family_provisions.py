"""Family 5: regulation-style provisions (cross-references, definitions far from their
use, conditions pointing at a field and at another rule).

Provisions are of five types. Definition provisions define a term in prose and state
the term and its source. Filing provisions state a filing date and a notice date,
reply provisions a receipt date and an answer date, fee provisions a fee class and a
filing fee in EUR, appeal provisions the appeal body.

The appeal rule's scope is pinned to a field value ([scope: provision type=Appeal]),
which is the condition pointing at a field; its text is read with another rule, the
condition pointing at another rule. Section 5 forbids [unless: ...], so that second
condition lives in the rule text only, where only the model reads it.

Ordinary layout: definitions anywhere, every use carries a cross-reference line to its
definition, the two windows are bound by sentences in the reference schedule (section
7, "A date window") and the fee band comes from the schedule's table keyed by fee
class. Planted kinds: a filing-to-notice gap over its window, a receipt-to-answer gap
over its window, a filing fee above its band, one below it, a definition without its
source, an appeal provision without its appeal body. Every planted entry names the unit
it relates to (`related_unit`): the definition behind it, or for a definition, the
provision that uses it farthest away. Distractors: gaps exactly equal to the window,
fees exactly on a bound, and filing provisions that state no appeal body (outside the
pinned scope).

Long-range layout (S3 item 12, D-042, revised in S3 checker round 2): every provision
belongs to a track (Ordinary or Expedited), and the figure that decides each planted
flaw lives ONLY in a distant unit of the use's own track: a window definition (four of
them, a notice and an answer window per track) or a fee table (two of them, one per
track, which are schedules and no definitions). Six definitions in all (the four
windows, the fee class and the appeal body) against four use types, spread through the
document with the fee tables and the uses, so no position and no label alone finds the
deciding unit: a planted flaw cannot be judged without the right unit of its track, at
least twelve units away. The reference schedule carries no figure at all. Only about
half of the uses (seeded) carry a cross-reference line, among the planted uses as
well, so a cross-reference baseline is not perfect by construction; `baselines`
measures a positional ("the first k units") and two label-only baselines, and every
bundle keeps all of them below 1. Python computes none of these flaws (no bound
sentence, no reference table): they are keyed from this family's own ground truth and
found again by the ground-truth scanner (ground_truth.py). Planted kinds: a notice
window exceeded, an answer window exceeded, a filing fee above, and below, the band its
track's fee table sets for its class. Distractors: gaps equal to their window, a fee on
a bound, and a filing (and a fee) that the other track's window (or table) would break
and its own does not.
"""
import datetime

from . import model as md
from . import textrules as tr
from . import wordlists as wl

FAMILY = "f5"
NAME = "regulation-style provisions"

NOTICE_DAYS, ANSWER_DAYS = 30, 14
MIN_DISTANCE = 12
FEE_CLASSES = [("Minor", 50, 150), ("Major", 150, 400), ("Complex", 400, 900), ("Urgent", 200, 600)]
DEFINED = {
    "notice": ("Notice window", "the time allowed between the filing of a matter and the notice given on it"),
    "answer": ("Answer window", "the time allowed between the receipt of a request and the answer to it"),
    "fee": ("Fee class", "the class that sets the band within which a filing fee must lie"),
    "appeal": ("Appeal body", "the panel that hears an appeal against a decision under these provisions"),
}
SOURCES = ["Schedule of windows", "Schedule of fees", "General part", "Interpretation part"]
BODIES = ["Review Panel", "Appeals Board", "Standing Committee", "Hearing Chamber"]

RULES = [
    md.Rule("CONV-RA", "Notice window",
            "The gap between the filed date and the notice date must not exceed the standard notice window."),
    md.Rule("CONV-RB", "Answer window",
            "The gap between the received date and the answered date must not exceed the standard answer window."),
    md.Rule("CONV-RC", "Fee band", "The filing fee must lie within the fee band for the fee class."),
    md.Rule("CONV-RD", "Definition source", "Every definition must state the source of the definition.",
            scope=["defined term"], requires=["definition source"]),
    md.Rule("CONV-RE", "Appeal body", "Read with CONV-RD, every appeal provision must name the appeal body.",
            scope=["provision type=Appeal"], requires=["appeal body"]),
]
BASE_DATE = datetime.date(2026, 1, 5)
NEED = {"notice_window_exceeded": "filing", "answer_window_exceeded": "reply",
        "fee_above_band": "fee", "fee_below_band": "fee", "missing_appeal_body": "appeal",
        "notice_window_far": "filing", "answer_window_far": "reply",
        "fee_above_band_far": "fee", "fee_below_band_far": "fee"}
FOR_TYPE = {"filing": "notice", "reply": "answer", "fee": "fee", "appeal": "appeal"}

# ---- the long-range layout --------------------------------------------------------
USE_LABEL, XREF_LABEL = "Provision type", "Cross reference"     # read by the gate check
TRACKS = ("Ordinary", "Expedited")
WINDOW_DAYS = {("notice", "Ordinary"): 30, ("notice", "Expedited"): 10,
               ("answer", "Ordinary"): 14, ("answer", "Expedited"): 7}
FEE_TABLES = {"Ordinary": [("Minor", 50, 150), ("Major", 150, 400), ("Complex", 400, 900)],
              "Expedited": [("Minor", 80, 200), ("Major", 250, 600), ("Complex", 600, 1200)]}
LONG_RULES = [
    md.Rule("CONV-RA", "Notice window",
            "The gap between the filed date and the notice date must not exceed the notice window for its track."),
    md.Rule("CONV-RB", "Answer window",
            "The gap between the received date and the answered date must not exceed the answer window "
            "for its track."),
    md.Rule("CONV-RC", "Fee band",
            "The filing fee must lie within the band the fee table of its track sets for its fee class."),
    md.Rule("CONV-RD", "Definition source", "Every definition must state the source of the definition.",
            scope=["defined term"], requires=["definition source"]),
    md.Rule("CONV-RE", "Appeal body", "Read with CONV-RD, every appeal provision must name the appeal body.",
            scope=["provision type=Appeal"], requires=["appeal body"]),
    md.Rule("CONV-RF", "Fee table", "Every fee table must name the body that issued it.",
            scope=["provision type=Fee table"], requires=["issued by"]),
]
LONG_RANGE_TRUTH = [
    {"check": "far_window", "bound_label": "window length", "match_label": "track",
     "pairs": [["filed", "notice", [["defined term", "Notice window"]], "CONV-RA", "notice_window_far"],
               ["received", "answered", [["defined term", "Answer window"]], "CONV-RB", "answer_window_far"]]},
    {"check": "far_fee", "select": [["provision type", "Fee table"]], "match_label": "track",
     "fee": "filing fee", "class": "fee class", "table_column": "fee range", "rule": "CONV-RC",
     "kinds": {"above": "fee_above_band_far", "below": "fee_below_band_far"}},
]
# The label a label-only baseline looks for, by the relation of the planted entry.
DECIDED_BY_LABEL = {"date_window": "window length", "above_band": "fee range", "below_band": "fee range"}
LONG_KINDS = (["notice_window_far"] * 4 + ["answer_window_far"] * 3 + ["fee_above_band_far"] * 3
              + ["fee_below_band_far"])
LONG_USES = {"filing": 10, "reply": 8, "fee": 8, "appeal": 5}


def _date(offset):
    return (BASE_DATE + datetime.timedelta(days=offset)).isoformat()


def baselines(units, planted, decided_by=DECIDED_BY_LABEL):
    """How well three baselines that read no value find each planted entry's related
    unit (the fraction of planted entries they get right; 1 is perfect).

    `units` is [(unit id, set of normalised labels)] in reading order; `planted` is
    [(unit id, related unit id, relation)]. The baselines:
    - `first_4` and `first_k`: the related unit is among the first 4 units (the old
      layout's definitions), or among the first k, k the number of distinct related
      units the test has (the smallest set that could be perfect);
    - `label_nearest`: the nearest other unit that carries the deciding label (a window
      length, or a fee range column), ties to the earlier;
    - `label_first`: the first unit in reading order that carries it."""
    pos = {u: i for i, (u, _) in enumerate(units)}
    k = len({r for _, r, _ in planted})
    out = {"k": k, "first_4": 0, "first_k": 0, "label_nearest": 0, "label_first": 0}
    for use, rel, relation in planted:
        label = decided_by[relation]
        carriers = [i for i, (u, labs) in enumerate(units) if label in labs and u != use]
        out["first_4"] += pos[rel] < 4
        out["first_k"] += pos[rel] < k
        if carriers:
            near = min(carriers, key=lambda i: (abs(i - pos[use]), i))
            out["label_nearest"] += units[near][0] == rel
            out["label_first"] += units[carriers[0]][0] == rel
    n = float(len(planted) or 1)
    for key in ("first_4", "first_k", "label_nearest", "label_first"):
        out[key] = round(out[key] / n, 3)
    return out


def baselines_below_one(scores):
    return all(scores[k] < 1 for k in ("first_4", "first_k", "label_nearest", "label_first"))


def _far_reorder(n, rng, planted, labels):
    """A reordered-sections permutation (blocks moved, wl.reorder), retried until every
    planted use stays at least MIN_DISTANCE units from its related unit and every
    baseline stays below 1. The key then states the true distances."""
    for _ in range(2000):
        order = wl.reorder(n, rng)
        pos = {orig: p for p, orig in enumerate(order)}
        if not all(abs(pos[p["unit"]] - pos[p["links"]["related_unit"]]) >= MIN_DISTANCE for p in planted):
            continue
        units = [(p, labels[orig]) for p, orig in enumerate(order)]
        scores = baselines(units, [(pos[p["unit"]], pos[p["links"]["related_unit"]], p["relation"])
                                   for p in planted])
        if baselines_below_one(scores):
            return order
    raise ValueError("no long-range reordering")


def build(seed, long_range=False):
    if long_range:
        return build_long_range(seed)
    rng = wl.make_rng(FAMILY, seed)
    kinds = (["notice_window_exceeded"] * 3 + ["answer_window_exceeded"] * 2 + ["fee_above_band"] * 2
             + ["fee_below_band"] * 1 + ["missing_definition_source"] * 1 + ["missing_appeal_body"] * 2)
    counts = {"filing": 6, "reply": 5, "fee": 5, "appeal": 3}
    # the use units, each with its type
    uses = []
    for typ, n in sorted(counts.items()):
        uses.extend([typ] * n)
    rng.shuffle(uses)
    defs = ["notice", "answer", "fee", "appeal"]
    rng.shuffle(defs)
    layout = [("use", t) for t in uses]
    for d in defs:
        layout.insert(rng.randrange(len(layout) + 1), ("def", d))
    n = len(layout)
    heads = wl.pick(rng, wl.BIRDS, n)
    def_unit = {d: i for i, (k, d) in enumerate(layout) if k == "def"}
    by_type = {}
    for i, (k, t) in enumerate(layout):
        if k == "use":
            by_type.setdefault(t, []).append(i)
    plan, used = {}, set()
    for kind in kinds:
        if kind == "missing_definition_source":
            continue
        typ = NEED[kind]
        cands = [i for i in by_type[typ] if i not in used]
        i = rng.choice(cands)
        plan[i] = kind
        used.add(i)
    missing_def = rng.choice(defs)
    distract = {}
    for typ, tag in (("filing", "gap_equals_window"), ("reply", "gap_equals_window"),
                     ("fee", "fee_on_bound")):
        free = [i for i in by_type[typ] if i not in used]
        j = rng.choice(free)
        distract[j] = tag
        used.add(j)
    doc_units, twin_units, planted, clean = [], [], [], []
    referencing = {d: [] for d in defs}
    for i, (k, t) in enumerate(layout):
        head = "Provision " + heads[i]
        kind = plan.get(i)
        if k == "def":
            term, meaning = DEFINED[t]
            prose = "In these provisions the %s means %s." % (term.lower(), meaning)
            lines = [["Defined term", term], ["Definition source", rng.choice(SOURCES)]]
            clean_u = md.Unit(head, [("lines", lines), ("prose", prose)])
            flawed = clean_u.clone()
            if t == missing_def:
                flawed.remove_line("Definition source")
                planted.append({"unit": i, "rule": "CONV-RD", "relation": "missing_field",
                                "kind": "missing_definition_source", "field_label": "definition source",
                                "value_a": 0, "value_b": 1, "links": {"related_unit": None}, "def": t})
        else:
            dref = def_unit[FOR_TYPE[t]]
            referencing[FOR_TYPE[t]].append(i)
            xref = [["Cross reference", "Provision " + heads[dref]]]
            links = {"related_unit": dref}
            if t in ("filing", "reply"):
                bound = NOTICE_DAYS if t == "filing" else ANSWER_DAYS
                start = rng.randint(0, 300)
                gap = rng.randint(2, bound - 2)
                if distract.get(i) == "gap_equals_window":
                    gap = bound
                bad = bound + rng.randint(3, 20)
                labels = ("Filed", "Notice") if t == "filing" else ("Received", "Answered")

                def mk(g):
                    return md.Unit(head, [("lines", [["Provision type", "Filing" if t == "filing" else "Reply"],
                                                     [labels[0], _date(start)], [labels[1], _date(start + g)]]
                                           + xref)])
                clean_u = mk(gap)
                flawed = mk(bad) if kind else clean_u.clone()
                if kind:
                    planted.append({"unit": i, "rule": "CONV-RA" if t == "filing" else "CONV-RB",
                                    "relation": "date_window", "kind": kind,
                                    "field_label": labels[0].lower(), "value_a": bad, "value_b": bound,
                                    "links": links})
            elif t == "fee":
                cname, lo, hi = rng.choice(FEE_CLASSES)
                fee = rng.randint(lo + (hi - lo) // 5, hi - (hi - lo) // 5)
                if distract.get(i) == "fee_on_bound":
                    fee = rng.choice([lo, hi])

                def mk(f):
                    return md.Unit(head, [("lines", [["Provision type", "Fee"], ["Fee class", cname],
                                                     ["Filing fee", "%d EUR" % f]] + xref)])
                clean_u = mk(fee)
                flawed = clean_u.clone()
                if kind == "fee_above_band":
                    bad = hi + rng.randint(10, (hi - lo) // 2)
                    flawed = mk(bad)
                    planted.append({"unit": i, "rule": "CONV-RC", "relation": "above_band", "kind": kind,
                                    "field_label": "filing fee", "value_a": bad, "value_b": hi,
                                    "links": links})
                elif kind == "fee_below_band":
                    bad = rng.randint(max(1, lo // 3), lo - 5)
                    flawed = mk(bad)
                    planted.append({"unit": i, "rule": "CONV-RC", "relation": "below_band", "kind": kind,
                                    "field_label": "filing fee", "value_a": bad, "value_b": lo,
                                    "links": links})
            else:
                body = rng.choice(BODIES)
                clean_u = md.Unit(head, [("lines", [["Provision type", "Appeal"], ["Appeal body", body]] + xref)])
                flawed = clean_u.clone()
                if kind == "missing_appeal_body":
                    flawed.remove_line("Appeal body")
                    planted.append({"unit": i, "rule": "CONV-RE", "relation": "missing_field", "kind": kind,
                                    "field_label": "appeal body", "value_a": 0, "value_b": 1, "links": links})
        if i in distract:
            clean.append(i)
        doc_units.append(flawed)
        twin_units.append(clean_u)
    for p in planted:
        if p["kind"] == "missing_definition_source":
            refs = referencing[p.pop("def")]
            p["links"]["related_unit"] = max(refs, key=lambda r: abs(r - p["unit"]))
    title = "Procedural provisions " + wl.letters_tag(rng).title()
    preamble = "These provisions govern filings, replies, fees and appeals before the board."
    doc = md.Doc(title, preamble, doc_units)
    twin = md.Doc(title, preamble, twin_units)
    reference = ("schedule", "Schedule", [
        ("prose", "This schedule sets the standard windows and the fee bands."),
        ("prose", "The standard notice window is %d days." % NOTICE_DAYS),
        ("prose", "The standard answer window is %d days." % ANSWER_DAYS),
        ("table", ["Fee class", "Fee band (EUR)"], [[c, "%d to %d" % (lo, hi)] for c, lo, hi in FEE_CLASSES]),
    ])
    conv = md.Conventions("Provision conventions", "These rules govern the procedural provisions.", RULES)
    fee_flaw = [p for p in planted if p["relation"] in ("above_band", "below_band")][0]
    fee_text = doc_units[fee_flaw["unit"]].line_value("Filing fee").replace(" EUR", ".00 EUR")
    planted = sorted(planted, key=lambda p: p["unit"])
    return {
        "family": FAMILY, "family_name": NAME, "seed": seed, "mode": "single",
        "doc": doc, "twin": twin, "conventions": conv, "references": [reference],
        "planted": planted, "clean": sorted(clean),
        "doc_stem": "provisions", "conv_stem": "rules",
        "task": "Review the provisions against the provision conventions, grounded in the schedule.",
        "probes": {
            "reword": {"old": "Filed", "new": "Lodged"},
            "reorder": wl.reorder(n, rng),
            # probe 3: the term only in the later version carries a keyed flaw
            "term": {"unit": fee_flaw["unit"], "label": "Filing fee"},
            "reformat": {"unit": fee_flaw["unit"], "label": "Filing fee", "text": fee_text},
        },
    }


def _long_layout(rng):
    """(layout, deciders, plan, distract) for the long-range layout, or None to retry.
    layout: [(kind, what, track)] in reading order; deciders: {(type, track): position}."""
    uses = []
    for typ, n in sorted(LONG_USES.items()):
        uses.extend([typ] * n)
    units = ([("def", "notice", tk) for tk in TRACKS] + [("def", "answer", tk) for tk in TRACKS]
             + [("def", "fee", None), ("def", "appeal", None)] + [("table", "fee", tk) for tk in TRACKS]
             + [("use", t, None if t == "appeal" else rng.choice(TRACKS)) for t in uses])
    rng.shuffle(units)
    deciders = {}
    for i, (k, what, tk) in enumerate(units):
        if (k == "def" and what in ("notice", "answer")) or k == "table":
            deciders[(FOR_TYPE_BY_DECIDER[what], tk)] = i
    far = {}
    for i, (k, t, tk) in enumerate(units):
        if k == "use" and t != "appeal" and abs(i - deciders[(t, tk)]) >= MIN_DISTANCE:
            far.setdefault(t, []).append(i)
    plan, used = {}, set()
    for kind in LONG_KINDS:
        cands = [i for i in far.get(NEED[kind], []) if i not in used]
        if not cands:
            return None
        i = rng.choice(cands)
        plan[i] = kind
        used.add(i)
    # the window flaws of each type sit on both tracks, so no one definition decides them all
    for typ in ("filing", "reply"):
        if len({units[i][2] for i, k in plan.items() if NEED[k] == typ}) != 2:
            return None
    distract = {}
    for typ, tag in (("filing", "gap_equals_window"), ("reply", "gap_equals_window"),
                     ("fee", "fee_on_bound"), ("filing", "other_track_breaks"),
                     ("fee", "other_track_breaks")):
        free = [i for i, (k, t, tk) in enumerate(units) if k == "use" and t == typ and i not in used
                and (tag != "other_track_breaks" or tk == ("Ordinary" if typ == "filing" else "Expedited"))]
        if not free:
            return None
        j = rng.choice(free)
        distract[j] = tag
        used.add(j)
    return units, deciders, plan, distract


FOR_TYPE_BY_DECIDER = {"notice": "filing", "answer": "reply", "fee": "fee"}


def build_long_range(seed):
    rng = wl.make_rng(FAMILY + "L", seed)
    for _ in range(2000):
        got = _long_layout(rng)
        if got is None:
            continue
        units, deciders, plan, distract = got
        labels = []
        for k, what, tk in units:
            if k == "def":
                labels.append({"defined term", "definition source"}
                              | ({"window length", "track"} if what in ("notice", "answer") else set()))
            elif k == "table":
                labels.append({"provision type", "track", "issued", "fee class", "fee range"})
            else:
                labels.append({"provision type"})
        planted_pos = [(i, deciders[(NEED[kd], units[i][2])], "date_window" if NEED[kd] != "fee"
                        else ("above_band" if "above" in kd else "below_band")) for i, kd in plan.items()]
        if baselines_below_one(baselines(list(enumerate(labels)), planted_pos)):
            break
    else:
        raise ValueError("no long-range layout")
    n = len(units)
    heads = wl.pick(rng, wl.BIRDS, n)
    # About half the uses carry a cross-reference line, planted ones included, with and
    # without it among the planted (seeded, retried until both hold).
    use_pos = [i for i, u in enumerate(units) if u[0] == "use"]
    for _ in range(500):
        xref_on = {i: rng.random() < 0.5 for i in use_pos}
        share = sum(xref_on.values()) / float(len(xref_on))
        if 0.4 <= share <= 0.6 and {xref_on[i] for i in plan} == {True, False}:
            break
    else:
        raise ValueError("no cross-reference draw")
    doc_units, twin_units, planted, clean = [], [], [], []
    appeal_def = [j for j, u in enumerate(units) if u[:2] == ("def", "appeal")][0]
    for i, (k, what, tk) in enumerate(units):
        head = "Provision " + heads[i]
        kind = plan.get(i)
        if k == "def":
            term, meaning = DEFINED[what]
            prose = "In these provisions the %s means %s." % (term.lower(), meaning)
            lines = [["Defined term", term]]
            if tk is not None:
                lines.append(["Track", tk])
            lines.append(["Definition source", rng.choice(SOURCES)])
            if what in ("notice", "answer"):
                lines.append(["Window length", "%d days" % WINDOW_DAYS[(what, tk)]])
            clean_u = md.Unit(head, [("lines", lines), ("prose", prose)])
            flawed = clean_u.clone()
        elif k == "table":
            clean_u = md.Unit(head, [
                ("lines", [["Provision type", "Fee table"], ["Track", tk], ["Issued by", rng.choice(BODIES)]]),
                ("table", ["Fee class", "Fee range (EUR)"],
                 [[c, "%d to %d" % (lo, hi)] for c, lo, hi in FEE_TABLES[tk]])])
            flawed = clean_u.clone()
        else:
            # the unit a use refers to: its track's decider, or the appeal-body definition
            rel = deciders[(what, tk)] if what != "appeal" else appeal_def
            xref = [["Cross reference", "Provision " + heads[rel]]] if xref_on[i] else []
            links = {"related_unit": rel}
            extra = {"cross_reference_line": bool(xref)}
            if what in ("filing", "reply"):
                term = FOR_TYPE[what]
                bound = WINDOW_DAYS[(term, tk)]
                start = rng.randint(0, 300)
                gap = rng.randint(2, bound - 2)
                if distract.get(i) == "gap_equals_window":
                    gap = bound
                elif distract.get(i) == "other_track_breaks":
                    other = WINDOW_DAYS[(term, "Expedited")]
                    gap = rng.randint(other + 2, bound - 1)
                bad = bound + rng.randint(3, 20)
                labs = ("Filed", "Notice") if what == "filing" else ("Received", "Answered")

                def mk(g):
                    return md.Unit(head, [("lines", [["Provision type", "Filing" if what == "filing" else "Reply"],
                                                     ["Track", tk], [labs[0], _date(start)],
                                                     [labs[1], _date(start + g)]] + xref)])
                clean_u = mk(gap)
                flawed = mk(bad) if kind else clean_u.clone()
                if kind:
                    planted.append({"unit": i, "rule": "CONV-RA" if what == "filing" else "CONV-RB",
                                    "relation": "date_window", "kind": kind,
                                    "field_label": labs[0].lower(), "value_a": bad, "value_b": bound,
                                    "links": links, "extra": extra})
            elif what == "fee":
                cname, lo, hi = rng.choice(FEE_TABLES[tk])
                fee = rng.randint(lo + (hi - lo) // 5, hi - (hi - lo) // 5)
                if distract.get(i) == "fee_on_bound":
                    fee = rng.choice([lo, hi])
                elif distract.get(i) == "other_track_breaks":
                    # inside its own (Expedited) band, above the Ordinary band for its class
                    o_hi = [h for c, _, h in FEE_TABLES["Ordinary"] if c == cname][0]
                    fee = rng.randint(max(lo, o_hi + 1), hi)

                def mk(f):
                    return md.Unit(head, [("lines", [["Provision type", "Fee"], ["Track", tk], ["Fee class", cname],
                                                     ["Filing fee", "%d EUR" % f]] + xref)])
                clean_u = mk(fee)
                flawed = clean_u.clone()
                if kind == "fee_above_band_far":
                    bad = hi + rng.randint(10, (hi - lo) // 2)
                    flawed = mk(bad)
                    planted.append({"unit": i, "rule": "CONV-RC", "relation": "above_band", "kind": kind,
                                    "field_label": "filing fee", "value_a": bad, "value_b": hi,
                                    "links": links, "extra": extra})
                elif kind == "fee_below_band_far":
                    bad = rng.randint(max(1, lo // 3), lo - 5)
                    flawed = mk(bad)
                    planted.append({"unit": i, "rule": "CONV-RC", "relation": "below_band", "kind": kind,
                                    "field_label": "filing fee", "value_a": bad, "value_b": lo,
                                    "links": links, "extra": extra})
            else:
                clean_u = md.Unit(head, [("lines", [["Provision type", "Appeal"],
                                                    ["Appeal body", rng.choice(BODIES)]] + xref)])
                flawed = clean_u.clone()
        if i in distract:
            clean.append(i)
        doc_units.append(flawed)
        twin_units.append(clean_u)
    for p in planted:
        if abs(p["unit"] - p["links"]["related_unit"]) < MIN_DISTANCE:
            raise ValueError("a long-range flaw sits within %d units of its related unit" % MIN_DISTANCE)
    title = "Procedural provisions " + wl.letters_tag(rng).title()
    preamble = "These provisions govern filings, replies, fees and appeals before the board."
    doc = md.Doc(title, preamble, doc_units)
    twin = md.Doc(title, preamble, twin_units)
    reference = ("schedule", "Schedule", [
        ("prose", "This schedule explains how the provisions are read."),
        ("prose", "Each window is stated in the provision that defines it for a track, and each fee band "
                  "in the fee table of a track."),
    ])
    conv = md.Conventions("Provision conventions", "These rules govern the procedural provisions.", LONG_RULES)
    fee_flaw = [p for p in planted if p["relation"] in ("above_band", "below_band")][0]
    fee_text = doc_units[fee_flaw["unit"]].line_value("Filing fee").replace(" EUR", ".00 EUR")
    planted = sorted(planted, key=lambda p: p["unit"])
    return {
        "family": "f5lr", "family_name": NAME, "seed": seed, "mode": "single",
        "doc": doc, "twin": twin, "conventions": conv, "references": [reference],
        "planted": planted, "clean": sorted(clean),
        "doc_stem": "provisions", "conv_stem": "rules",
        "task": "Review the provisions against the provision conventions, grounded in the schedule.",
        "ground_truth_checks": LONG_RANGE_TRUTH,
        "key_extra": {"long_range": {
            "related_by": "every planted entry names in related_unit the unit of its own track whose figure "
                          "decides it (a window definition's window length, or a fee table's range for its "
                          "class), stated only there; distance is how many units apart the two are",
            "definitions_first": all(units[i][0] == "def" for i in range(6)),
            "min_distance": MIN_DISTANCE,
            "decided_by_label": DECIDED_BY_LABEL,
            "cross_reference_share": round(sum(xref_on.values()) / float(len(xref_on)), 2)}},
        "probes": {
            "reword": {"old": "Filed", "new": "Lodged"},
            "reorder": _far_reorder(n, rng, planted, labels),
            # probe 3: the term only in the later version carries a keyed flaw
            "term": {"unit": fee_flaw["unit"], "label": "Filing fee"},
            "reformat": {"unit": fee_flaw["unit"], "label": "Filing fee", "text": fee_text},
        },
    }
