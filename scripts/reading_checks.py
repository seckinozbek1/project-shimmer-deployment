"""Gate checks 410 to 414: READING-A, the this-version fixes of issue #281 (D-667) for
numbers, dates and rule bands. No model, no provider, no key: invented-vocabulary units and
rules, run through the real readers, paired_review.plan_calls, compute_checks and
reviewed_document.render.

Each proof is neutralise, fail, restore, pass (scripts/effect_proof.py):
  410 (gap 3) a number's marks are decided from its own form, then from the numbers of the
      same text, then from config/number_reading.json; one run is one number; a number none
      of them decides is refused (ambiguous_separator) into relation_refusals at its unit, and
      a column with a refused cell keeps no figure;
  411 (gap 2) a label line writing a date in a form other than ISO is listed as
      date_form_not_read on every unit a duration rule is checked on, never silent;
  412 (gap 15) a band read from a rule's prose is taken only from exactly two figures in one
      measure; more figures, figures in another role or a refused number refuse the band into
      relation_refusals, and no band comparison is made;
  413 (gap 16) a computed date window carries order_checked false and a
      date_order_not_checked row, and docs/INPUT_FORMAT.md states the limit;
  414 (HONEST-OUTPUT-A) reviewed_document.md shows each of these at its unit (a rule's band
      at no part) with a header count in English and in tr, and renders as before when there
      is none.
"""
import contextlib
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import localization  # noqa: E402
import paired_review as pr  # noqa: E402
import reviewed_document as rd  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

GUIDE = ROOT / "docs" / "INPUT_FORMAT.md"
GUIDE_LIMIT = "a date pair is compared as a duration only"
DOC_ID = "kiln_log"
BOUND = (24.0, "hours", "REF-KILN-1")
TOKENS = ["1,250", "1.250", "1.254.000", "1.250,75", "1,250.75", "12,5", "0,250", "1234,567",
          "1 250,5", "1.234.5", "12,34,567", "3,5,7"]
# A unit whose own numbers decide that the point groups: its lone "1.250" is 1250.
DECIDED_UNIT = "\n".join(["## Kiln Batch A", "", "Glaze load: 1.254.000 g", "Slip load: 1.250 g",
                          "Ash load: 12,34,567 g", "", "| Shelf | Load (g) |", "|---|---|",
                          "| Upper | 1,5 |", "| Lower | 3,5,7 |", "", "| Tray | Mass (g) |", "|---|---|",
                          "| Left | 4 |", "| Right | 6 |", "", "Total mass: 10 g", ""])
DATE_DOC = "\n".join(["# Kiln log", "", "## Firing One", "", "Kiln lit: 2026-03-01 09:00",
                      "Kiln banked: 03.03.2026", "", "## Firing Two", "", "Kiln lit: 2026-03-05 09:00",
                      "Kiln banked: 2026-03-04 21:00", ""])
DATE_RULE = {"id": "CONV-K01", "severity": "required", "category": "conv-k01",
             "rule": "A kiln must be banked within the kiln window after the kiln is lit."}
BAND_RULES = {"CONV-K02": "The glaze share must sit inside 40% to 45%.",
              "CONV-K03": "In year 2 the glaze share must sit inside 40% to 45%.",
              "CONV-K04": "The glaze share must sit inside 40% to 45%, or 48%.",
              "CONV-K05": "The glaze cost must sit inside 1,23,4 g to 2,000 g."}
BAND_UNIT = "## Kiln Batch B\n\nGlaze share: 50 %\n"


@contextlib.contextmanager
def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


def with_source(module, name, old, new):
    """`module.name` with one passage of its own source changed, as a neutralisation."""
    source = inspect.getsource(getattr(module, name))
    assert source.count(old) == 1, old
    space = dict(vars(module))
    exec(source.replace(old, new), space)
    return patched(module, name, space[name])


def _units(text):
    return pr.unit_texts_for(text, DOC_ID)


def _plan(text, rules, **kwargs):
    units = _units(text)
    sink = []
    pr.plan_calls(units, [(u, r["id"]) for u in units for r in rules], {r["id"]: r for r in rules}, {},
                  relation_refusal_sink=sink, **kwargs)
    return units, sink


# ---------------------------------------------------------------- 410 (gap 3)

def observe_410():
    fields = []
    scalars, columns, rows = pr.extract_fields(DECIDED_UNIT, refusals=fields)
    _units_, sink = _plan(DECIDED_UNIT, [DATE_RULE])
    return {"read": [list(pr.read_number(t)) for t in TOKENS],
            "convention": [pr.separator_convention(t) for t in ("x 1.254.000", "x 1,254,000 and 1.254.000", "x 1,250")],
            "scalars": sorted([" ".join(k), v[0]] for k, v in scalars.items()),
            "columns": sorted(" ".join(k) for k in columns), "rows": sorted(" ".join(k) for k in rows),
            "refused_fields": fields,
            "pairing_rows": [r for r in sink if r.get("relation") == pr.FIGURE_READING]}


def expected_410():
    refused = pr.AMBIGUOUS_SEPARATOR
    return {"read": [[1250.0, None], [1.25, None], [1254000.0, None], [1250.75, None], [1250.75, None],
                     [12.5, None], [0.25, None], [1234.567, None], [1250.5, None], [None, refused],
                     [None, refused], [None, refused]],
            "convention": [{".": "group", ",": "decimal"}, pr.CONFLICT, None],
            "scalars": [["glaze load", 1254000.0], ["slip load", 1250.0], ["total mass", 10.0]],
            "columns": ["mass"], "rows": ["mass"],
            "refused_fields": [{"field": "ash load", "figure": "12,34,567", "reason": refused},
                               {"field": "load", "figure": "3,5,7", "reason": refused}],
            "pairing_rows": [
                {"unit_id": next(iter(_units(DECIDED_UNIT))), "rule_id": "", "relation": pr.FIGURE_READING,
                 "reason": refused, "fields": ["ash load"], "figures": ["12,34,567"]},
                {"unit_id": next(iter(_units(DECIDED_UNIT))), "rule_id": "", "relation": pr.FIGURE_READING,
                 "reason": refused, "fields": ["load"], "figures": ["3,5,7"]}]}


def _old_quantity():
    import re
    sp = "   "
    old = pr._QUANTITY.pattern.replace(
        "(?P<num>-?(?:\\d{1,3}(?:[" + sp + "]\\d{3}(?!\\d))+|\\d+)(?:[.,]\\d+)*)",
        "(?P<num>-?\\d{1,3}(?:[" + sp + ",]\\d{3})+(?:[.,]\\d+)?|-?\\d+(?:[.,]\\d+)?)")
    assert old != pr._QUANTITY.pattern
    return patched(pr, "_QUANTITY", re.compile(old))


def neutralisers_410():
    return [
        ("one run is one number", _old_quantity),
        ("a repeated mark groups", lambda: with_source(
            pr, "_form_roles", 'return {mark: "group"} if _grouped(digits) else "malformed"', 'return "malformed"')),
        ("the unit's own numbers decide an undecided mark", lambda: patched(pr, "separator_convention", lambda text: None)),
        ("config/number_reading.json decides what nothing else does", lambda: patched(
            pr, "number_reading_declaration", lambda: None)),
        ("a column with a refused cell keeps no figure", lambda: with_source(
            pr, "extract_fields", "for header in refused_columns:", "for header in ():")),
        ("a refused figure is on the pairing map", lambda: with_source(
            pr, "plan_calls", "for row in figure_refusals:", "for row in ():")),
    ]


# ---------------------------------------------------------------- 411 (gap 2)

def observe_411():
    units, sink = _plan(DATE_DOC, [DATE_RULE], duration_bound_for=lambda rule: BOUND)
    order = {u: i for i, u in enumerate(units)}
    return {"forms": pr.other_date_forms("15.03.2026, 3/4/26, 1 Brumaire 2026, Brumaire 12, 2026, "
                                         "2026-03-01T09:30Z, 2026-03-01, 1.2.3, 1.254.000"),
            "rows": sorted([order[r["unit_id"]], r["rule_id"], r["fields"]] for r in sink
                           if r.get("reason") == pr.DATE_FORM_NOT_READ),
            "no_bound_rows": [r for r in _plan(DATE_DOC, [DATE_RULE])[1] if r.get("reason") == pr.DATE_FORM_NOT_READ]}


def expected_411():
    return {"forms": ["15.03.2026", "3/4/26", "1 Brumaire 2026", "Brumaire 12, 2026", "2026-03-01T09:30Z"],
            "rows": [[0, "CONV-K01", ["kiln banked"]]], "no_bound_rows": []}


def neutralisers_411():
    return [
        ("a non-ISO date form is found", lambda: patched(pr, "other_date_forms", lambda text: [])),
        ("the unread line is on the record", lambda: with_source(
            pr, "compute_checks", "for label, _count in unread_date_lines(unit_text):",
            "for label, _count in ():")),
    ]


# ---------------------------------------------------------------- 412 (gap 15)

def observe_412():
    rules = [{"id": k, "severity": "required", "category": k.lower(), "rule": v} for k, v in BAND_RULES.items()]
    _u, sink = _plan(BAND_UNIT, rules)
    scalars, columns, _rows = pr.extract_fields(BAND_UNIT)
    bands = {}
    for rule in rules:
        checks = pr.compute_checks(scalars, columns, rule_text=rule["rule"], refusals=[], rule_id=rule["id"],
                                   needed=set(), present_labels=set(scalars))
        bands[rule["id"]] = sorted(c["relation"] for c in checks if c["relation"] in pr.BAND_RELATIONS)
    return {"readings": {k: list(pr.bounds_reading(v)) for k, v in BAND_RULES.items()}, "bands": bands,
            "rows": sorted([r["rule_id"], r["unit_id"], r["reason"]] for r in sink if r.get("relation") == pr.BAND_READING)}


def expected_412():
    return {"readings": {"CONV-K02": [[40.0, 45.0, "%"], None], "CONV-K03": [None, pr.BAND_MIXED_ROLES],
                         "CONV-K04": [None, pr.BAND_TOO_MANY_FIGURES], "CONV-K05": [None, pr.AMBIGUOUS_SEPARATOR]},
            "bands": {"CONV-K02": ["above_band"], "CONV-K03": [], "CONV-K04": [], "CONV-K05": []},
            "rows": [["CONV-K03", "", pr.BAND_MIXED_ROLES], ["CONV-K04", "", pr.BAND_TOO_MANY_FIGURES],
                     ["CONV-K05", "", pr.AMBIGUOUS_SEPARATOR]]}


def neutralisers_412():
    return [
        ("more than two figures refuse the band", lambda: with_source(
            pr, "bounds_reading", "if len(found) > 2:", "if False:")),
        ("a refused number refuses the band", lambda: with_source(
            pr, "bounds_reading", "if refused and len(found) + len(refused) >= 2:", "if False:")),
        ("the band refusal is on the record", lambda: with_source(
            pr, "compute_checks", "    if band_refused:\n", "    if False:\n")),
    ]


# ---------------------------------------------------------------- 413 (gap 16)

def observe_413():
    units, sink = _plan(DATE_DOC, [DATE_RULE], duration_bound_for=lambda rule: BOUND)
    second = list(units)[1]
    scalars, columns, _rows = pr.extract_fields(units[second]["text"])
    checks = [c for c in pr.compute_checks(scalars, columns, rule_text=DATE_RULE["rule"], unit_text=units[second]["text"],
                                           duration_bound=BOUND, refusals=[], unit_id=second, rule_id="CONV-K01")
              if c["relation"] == "date_window"]
    return {"window": [[c["computed"], c["agrees"], c.get("order_checked")] for c in checks],
            "rows": [[r["unit_id"] == second, r["fields"]] for r in sink if r.get("reason") == pr.DATE_ORDER_NOT_CHECKED],
            "guide_states_limit": GUIDE_LIMIT in GUIDE.read_text(encoding="utf-8")}


def expected_413():
    # Banked twelve hours BEFORE it was lit: inside the window, so no finding, and the
    # record says the order was not checked.
    return {"window": [[12.0, True, False]], "rows": [[True, ["kiln lit", "kiln banked"]]],
            "guide_states_limit": True}


def neutralisers_413():
    import tempfile
    temp = Path(tempfile.mkdtemp()) / "INPUT_FORMAT.md"
    temp.write_text("A date pair is compared.\n", encoding="utf-8")
    return [
        ("the window says the order was not checked", lambda: with_source(
            pr, "compute_checks", '"order_checked": False,', "")),
        ("the order note is on the record", lambda: with_source(
            pr, "compute_checks", "DATE_ORDER_NOT_CHECKED,\n", "DATE_FORM_NOT_READ,\n")),
        ("the input format guide states the limit", lambda: patched(sys.modules[__name__], "GUIDE", temp)),
    ]


# ---------------------------------------------------------------- 414 (report)

def _render(pairing, language="en"):
    return rd.render(document_id=DOC_ID, document_name="Kiln log", document_text=DATE_DOC, master={},
                     python_findings=[], pairing=pairing, output_language=language)


def _pairing():
    units, sink = _plan(DATE_DOC, [DATE_RULE] + [{"id": "CONV-K03", "severity": "required", "category": "k03",
                                                   "rule": BAND_RULES["CONV-K03"]}],
                        duration_bound_for=lambda rule: BOUND if rule["id"] == "CONV-K01" else None)
    return {"not_judged": [], "judging_calls": [], "absence_refused": [], "uncomputable_refused": [],
            "relation_refusals": sink}


def observe_414():
    pairing = _pairing()
    en, tr = _render(pairing), _render(pairing, "tr")
    empty = dict(pairing, relation_refusals=[])
    label_en, label_tr = localization.text(rd.NOT_READ_LABEL, "en"), localization.text(rd.NOT_READ_LABEL, "tr")
    english = [rd.NOT_READ_LABEL, rd.COUNT_NOT_READ.split("{")[0]] + [s.split("{")[0] for s in rd.NOT_READ_REASONS.values()]
    return {"blocks_en": en.count("**%s**" % label_en), "blocks_tr": tr.count("**%s**" % label_tr),
            "count_line": rd.COUNT_NOT_READ.format(n=len(rd.not_read_entries(pairing))) in en,
            "band_at_no_part": "Rule CONV-K03 states figures in more than one measure" in en,
            "unread_date_shown": "The date under kiln banked is not written" in en,
            "order_shown": "The two dates under kiln lit / kiln banked were compared as a gap only" in en,
            "no_english_in_tr": [s for s in english if s.strip() and s in tr],
            "unchanged_without": _render(empty) == _render({k: v for k, v in empty.items() if k != "relation_refusals"})}


def expected_414():
    return {"blocks_en": 3, "blocks_tr": 3, "count_line": True, "band_at_no_part": True, "unread_date_shown": True,
            "order_shown": True, "no_english_in_tr": [], "unchanged_without": True}


def _catalog_without_reading():
    cat = dict(localization.catalog())
    for key in [rd.NOT_READ_LABEL, rd.COUNT_NOT_READ] + list(rd.NOT_READ_REASONS.values()):
        cat.pop(key, None)
    return patched(localization, "catalog", lambda: cat)


def neutralisers_414():
    return [
        ("the not-read rows are shown", lambda: patched(rd, "not_read_entries", lambda pairing: [])),
        ("tr renders them in tr", _catalog_without_reading),
    ]


PROOFS = {410: (observe_410, expected_410, neutralisers_410), 411: (observe_411, expected_411, neutralisers_411),
          412: (observe_412, expected_412, neutralisers_412), 413: (observe_413, expected_413, neutralisers_413),
          414: (observe_414, expected_414, neutralisers_414)}
SAYS = {410: "a number's marks decided by its form, its text or the declaration, else refused at its unit",
        411: "a non-ISO date on a label line is listed as date_form_not_read",
        412: "a rule band is read only from exactly two figures in one measure, else refused on the record",
        413: "a date window carries order_checked false and a date_order_not_checked row; the guide states it",
        414: "reviewed_document.md shows each not-read figure, date and band, in English and tr"}


def run_check(number):
    observe, expected, neutralisers = PROOFS[number]
    want = json.dumps(expected(), sort_keys=True)
    names = []
    for name, neutralise in neutralisers():
        prove_effect(name=name, validate=lambda: pr.NUMBER_READING_PATH.is_file() and GUIDE.is_file(),
                     observe=observe,
                     check=lambda: ("PASS" if json.dumps(observe(), sort_keys=True) == want else "FAIL", name),
                     neutralise=neutralise)
        names.append(name)
    return "PASS", "%d proofs, each neutralise, fail, restore, pass: %s (%s)" % (len(names), SAYS[number], "; ".join(names))


if __name__ == "__main__":
    numbers = [int(a) for a in sys.argv[1:] if a.isdigit()] or sorted(PROOFS)
    for number in numbers:
        if "--show" in sys.argv:
            print(number, json.dumps(PROOFS[number][0](), indent=1, sort_keys=True, default=str))
            continue
        print(number, json.dumps(run_check(number)))
