"""Family 5: regulation-style provisions (cross-references, definitions far from their
use, conditions pointing at a field and at another rule).

Provisions are of five types. Definition provisions define a term in prose and state
the term and its source. Filing provisions state a filing date and a notice date,
reply provisions a receipt date and an answer date, fee provisions a fee class and a
filing fee in EUR, appeal provisions the appeal body. Every provision that uses a
defined term carries a text cross reference to the provision that defines it.

The two date windows are bound by sentences in the reference schedule (section 7,
"A date window"); the fee band comes from the schedule's table keyed by fee class.
The appeal rule's scope is pinned to a field value ([scope: provision type=Appeal]),
which is the condition pointing at a field; its text is read with another rule, the
condition pointing at another rule. Section 5 forbids [unless: ...], so that second
condition lives in the rule text only, where only the model reads it.

Planted kinds: a filing-to-notice gap over its window, a receipt-to-answer gap over
its window, a filing fee above its band, one below it, a definition without its
source, an appeal provision without its appeal body. Every planted entry names the
unit it relates to (`related_unit`): the definition behind it, or for a definition,
the provision that uses it. Distractors: gaps exactly equal to the window, fees
exactly on a bound, and filing provisions that state no appeal body (outside the
pinned scope).

With long_range=True the definitions open the document and every flaw sits far from
the unit it relates to (S3 item 12).
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


def _date(offset):
    return (BASE_DATE + datetime.timedelta(days=offset)).isoformat()


def build(seed, long_range=False):
    rng = wl.make_rng(FAMILY + ("L" if long_range else ""), seed)
    kinds = (["notice_window_exceeded"] * 3 + ["answer_window_exceeded"] * 2 + ["fee_above_band"] * 2
             + ["fee_below_band"] * 1 + ["missing_definition_source"] * 1 + ["missing_appeal_body"] * 2)
    if long_range:
        kinds += ["notice_window_exceeded", "answer_window_exceeded", "fee_above_band"]
        counts = {"filing": 10, "reply": 8, "fee": 8, "appeal": 5}
    else:
        counts = {"filing": 6, "reply": 5, "fee": 5, "appeal": 3}
    # the use units, each with its type
    uses = []
    for typ, n in sorted(counts.items()):
        uses.extend([typ] * n)
    rng.shuffle(uses)
    defs = ["notice", "answer", "fee", "appeal"]
    rng.shuffle(defs)
    if long_range:
        # retry the order of the uses until each type has room, far from its
        # definition, for its flaws and one distractor
        need_far = {"filing": kinds.count("notice_window_exceeded"),
                    "reply": kinds.count("answer_window_exceeded"),
                    "fee": kinds.count("fee_above_band") + kinds.count("fee_below_band"),
                    "appeal": kinds.count("missing_appeal_body")}
        for _ in range(500):
            layout = [("def", d) for d in defs] + [("use", t) for t in uses]
            dpos = {d: i for i, d in enumerate(defs)}
            far = {}
            for i, (k, t) in enumerate(layout):
                if k == "use" and i - dpos[{"filing": "notice", "reply": "answer", "fee": "fee",
                                             "appeal": "appeal"}[t]] >= MIN_DISTANCE:
                    far[t] = far.get(t, 0) + 1
            if all(far.get(t, 0) >= need_far[t] + 1 for t in need_far):
                break
            rng.shuffle(uses)
        else:
            raise ValueError("no long-range layout")
    else:
        layout = [("use", t) for t in uses]
        for d in defs:
            layout.insert(rng.randrange(len(layout) + 1), ("def", d))
    n = len(layout)
    heads = wl.pick(rng, wl.BIRDS, n)
    def_unit = {d: i for i, (k, d) in enumerate(layout) if k == "def"}
    for_type = {"filing": "notice", "reply": "answer", "fee": "fee", "appeal": "appeal"}
    # which units carry which flaw: far from their definition when long_range
    by_type = {}
    for i, (k, t) in enumerate(layout):
        if k == "use":
            by_type.setdefault(t, []).append(i)
    need = {"notice_window_exceeded": "filing", "answer_window_exceeded": "reply",
            "fee_above_band": "fee", "fee_below_band": "fee", "missing_appeal_body": "appeal"}
    plan, used = {}, set()
    for kind in kinds:
        if kind == "missing_definition_source":
            continue
        typ = need[kind]
        cands = [i for i in by_type[typ] if i not in used]
        if long_range:
            cands = [i for i in cands if i - def_unit[for_type[typ]] >= MIN_DISTANCE]
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
            dref = def_unit[for_type[t]]
            referencing[for_type[t]].append(i)
            xref = ["Cross reference", "Provision " + heads[dref]]
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
                                                     [labels[0], _date(start)], [labels[1], _date(start + g)], xref])])
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
                                                     ["Filing fee", "%d EUR" % f], xref])])
                clean_u = mk(fee)
                flawed = clean_u.clone()
                if kind == "fee_above_band":
                    bad = hi + rng.randint(10, (hi - lo) // 2)
                    flawed = mk(bad)
                    planted.append({"unit": i, "rule": "CONV-RC", "relation": "above_band", "kind": kind,
                                    "field_label": "filing fee", "value_a": bad, "value_b": hi, "links": links})
                elif kind == "fee_below_band":
                    bad = rng.randint(max(1, lo // 3), lo - 5)
                    flawed = mk(bad)
                    planted.append({"unit": i, "rule": "CONV-RC", "relation": "below_band", "kind": kind,
                                    "field_label": "filing fee", "value_a": bad, "value_b": lo, "links": links})
            else:
                body = rng.choice(BODIES)
                clean_u = md.Unit(head, [("lines", [["Provision type", "Appeal"], ["Appeal body", body], xref])])
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
        if long_range and abs(p["unit"] - p["links"]["related_unit"]) < MIN_DISTANCE:
            raise ValueError("a long-range flaw sits within %d units of its related unit" % MIN_DISTANCE)
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
    flaw_units = {p["unit"] for p in planted}
    plain_fee = [i for i in by_type["fee"] if i not in flaw_units and i not in clean]
    fee_flaw = [p for p in planted if p["relation"] in ("above_band", "below_band")][0]
    fee_text = doc_units[fee_flaw["unit"]].line_value("Filing fee").replace(" EUR", ".00 EUR")
    spec = {
        "family": FAMILY, "family_name": NAME, "seed": seed, "mode": "single",
        "doc": doc, "twin": twin, "conventions": conv, "references": [reference],
        "planted": sorted(planted, key=lambda p: p["unit"]), "clean": sorted(clean),
        "doc_stem": "provisions", "conv_stem": "rules",
        "task": "Review the provisions against the provision conventions, grounded in the schedule.",
        "probes": {
            "reword": {"old": "Filed", "new": "Lodged"},
            "reorder": wl.reorder(n, rng),
            "term": {"unit": plain_fee[0], "label": "Filing fee"},
            "reformat": {"unit": fee_flaw["unit"], "label": "Filing fee", "text": fee_text},
        },
    }
    if long_range:
        spec["family"] = "f5lr"
        spec["key_extra"] = {"long_range": {
            "related_by": "every planted entry names in related_unit the unit a reader needs to judge it: "
                          "the definition behind it, or for a definition, the farthest provision that uses it",
            "definitions_first": True, "min_distance": MIN_DISTANCE}}
    return spec
