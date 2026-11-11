"""Gate check: every refusal of a change record carries a typed `reason_kind` (D-042).

A refused comparison with an earlier version used to carry only a sentence for a human
(`reason`), which a scorer is told not to parse (docs/OUTPUT_FORMAT.md section 7.1), so
an answer key could not state an expected refusal and a rename could not be told from a
tie. Every refusal now also carries `reason_kind`, one of
paired_review.PRIOR_REFUSAL_KINDS, written where the refusal is made and copied into
review_data.json's `prior_refusals` by pipeline._prior_refusals_for.

Executed, not read: each refusal path runs on invented fixtures (no model, no network):
paired_review.absent_checks (possible_rename, possible_successor,
possible_successor_no_unit, no_citation), paired_review.prior_lookup (tie, and a table's
refusals passed through), paired_review.prior_checks (unit_mismatch, disagreeing_bands),
reference_tables.prior_values_for_scalars (no_key_column, value_column_count, tie,
reverse_tie), and pipeline._prior_comparison on a real orchestrator (no_rule, orphan),
whose pairing map is then read back through pipeline._prior_refusals_for. Every refusal
must carry a kind from the list, each fixture the kind it was built for, and the copy
must keep it. Neutralised in process two ways (the copy drops the kind; absent_checks
loses it), each caught, restored, and passing again.

D-275: a table row is withdrawn only when it is gone. pipeline._prior_comparison, on a real
orchestrator with no model, is given an earlier version and a later one sharing a table with
one value column: a row kept unchanged and a row whose figure changed read as present, a row
removed is still absent_since_prior, and neither surviving row gets a withdrawal, on invented
fixtures and, where benchmark/dev_cases/ is in the tree, on the worked case's own Annex II.
Neutralised three ways (no row of the document read; the changed row's label lost; the earlier
table's rows not read), each caught, restored, and passing again.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

V1 = "## Part One\n\nAlpha count: 42 units\nBeta level: 17 units\nGamma total: 9 units\n"
V1_NO_UNIT = "## Part One\n\nAlpha count: 42\nBeta level: 17\nGamma total: 9\n"


def _absent(v2_lines, v1=V1, ref="REF-0001"):
    import paired_review as pr
    import pairing_map as pm
    v2 = "## Part One\n\n" + "".join(line + "\n" for line in v2_lines)
    index = pr.prior_index(v1, lambda i: ref, known_units=set())
    units = pm.split_units(v2, document_id="v2")
    present = set()
    for unit in units:
        present |= pm.unit_fields(unit.get("text", ""))
    unit = units[0]
    scalars, _, _ = pr.extract_fields(unit.get("text", ""), known_units=set())
    slug = unit["unit_id"].split("-", 1)[1]
    hits, refused1 = pr.prior_lookup(index, scalars, slug)
    _, refused2 = pr.absent_checks(index, present, slug, scalars=scalars, hits=hits)
    return refused1 + refused2


def _table(text):
    import reference_tables as rt
    return rt.parse_tables(text, ref_id="REF-0009", document_id="", known_units={"units"})[0]


def _table_refusals(text, labels):
    import reference_tables as rt
    scalars = {tuple(lbl.split()): (1.0, "units") for lbl in labels}
    return rt.prior_values_for_scalars(_table(text), scalars)[1]


def _checks(bands):
    import paired_review as pr
    scalars = {("alpha", "count"): (40.0, "units"), ("beta", "level"): (17.0, "kg")}
    hits = {("alpha", "count"): {"value": 42.0, "unit": "units", "ref_ids": ["REF-0001"]},
            ("beta", "level"): {"value": 17.0, "unit": "units", "ref_ids": ["REF-0001"]}}
    return pr.prior_checks(scalars, hits, {("alpha", "count"): bands})[1]


def _tie():
    import paired_review as pr
    text = "## Part One\n\nAlpha count: 42 units\n\n## Part Two\n\nAlpha count: 44 units\n"
    index = pr.prior_index(text, lambda i: "REF-%04d" % i, known_units=set())
    scalars = {("alpha", "count"): (43.0, "units")}
    return pr.prior_lookup(index, scalars, "part-three")[1]


def _pipeline_run():
    """pipeline._prior_comparison on a real orchestrator with a registry whose only rule
    names nothing the document carries (every comparison: no_rule) and an earlier heading
    the document no longer has (orphan); returns (unit refusals, orphans, the copy)."""
    import pairing_map as pm
    import pipeline as pl
    import reference_builder as rb
    from harness.run_agent import build_orchestrator
    prior = {"id": "zr_prior", "name": "zr_prior.md",
             "text": "# Earlier\n\n## Part One\n\nAlpha count: 40 units\n\n## Part Gone\n\nOmega count: 3 units\n"}
    doc = {"id": "zr_doc", "name": "zr_doc.md", "text": "# Now\n\n## Part One\n\nAlpha count: 42 units\n"}
    reg = {"conventions": [{"id": "CONV-001", "category": "conv-z01", "severity": "required",
                            "rule": "The sigma figure must be stated."}]}

    async def _no_call(*a, **k):
        raise AssertionError("a model call was attempted")

    with tempfile.TemporaryDirectory(prefix="shimmer_gate_refusal_kind_") as tmp:
        orch = build_orchestrator(root=ROOT, out_root=tmp)
        index = rb.ReferenceIndex.open(ROOT, index_path=Path(tmp) / "refs.json")
        index.index_document(input_type="context", document_id=prior["id"],
                             document_name=prior["name"], text=prior["text"])
        pairing = pm.build_pairing_map(doc["text"], reg["conventions"], document_id=doc["id"],
                                       convention_registry=reg)
        saved = pl._run_one
        pl._run_one = _no_call
        try:
            pl._prior_comparison(orch, doc, pairing, reg, [prior], index,
                                 [e.as_dict() for e in index.entries])
        finally:
            pl._run_one = saved
    refused = [r for u in pairing.get("units", [])
               for r in (u.get("prior_comparisons") or {}).get("refused") or []]
    copied = pl._prior_refusals_for({"_pairing": pairing})
    return refused, list(pairing.get("prior_orphans") or []), copied


ROWS_BEFORE = ("# Earlier\n\n## Part One\n\nRecord state: open\n\n| Line | Line cost (credits) |\n|---|---|\n"
               "| Alpha entry | 10 |\n| Beta entry | 20 |\n| Gamma entry | 30 |\n")
ROWS_AFTER = ("# Now\n\n## Part One\n\nRecord state: open\n\n| Line | Line cost (credits) |\n|---|---|\n"
              "| Alpha entry | 10 |\n| Gamma entry | 35 |\n")
ROWS_RULE = {"id": "CONV-001", "category": "conv-z01", "severity": "required",
             "rule": "The record state must stay consistent with the text."}
WORKED_CONTEXT = ROOT / "benchmark" / "dev_cases" / "host_agreement_three_rounds" / "workload" / "context"


def _compared(prior_text, doc_text, rules):
    """{field: relation} of what pipeline._prior_comparison minted, and the items' count."""
    import pairing_map as pm
    import pipeline as pl
    import reference_builder as rb
    from harness.run_agent import build_orchestrator
    prior = {"id": "zr_prior", "name": "zr_prior.md", "text": prior_text}
    doc = {"id": "zr_doc", "name": "zr_doc.md", "text": doc_text}
    reg = {"conventions": rules}

    async def _no_call(*a, **k):
        raise AssertionError("a model call was attempted")

    with tempfile.TemporaryDirectory(prefix="shimmer_gate_table_rows_") as tmp:
        orch = build_orchestrator(root=ROOT, out_root=tmp)
        index = rb.ReferenceIndex.open(ROOT, index_path=Path(tmp) / "refs.json")
        index.index_document(input_type="context", document_id=prior["id"],
                             document_name=prior["name"], text=prior["text"])
        pairing = pm.build_pairing_map(doc["text"], rules, document_id=doc["id"], convention_registry=reg)
        saved = pl._run_one
        pl._run_one = _no_call
        try:
            out = pl._prior_comparison(orch, doc, pairing, reg, [prior], index,
                                       [e.as_dict() for e in index.entries])
        finally:
            pl._run_one = saved
    items = out[0]["parsed"]["items"] if out else []
    return {i.get("field_label"): i.get("relation") for i in items}


def _worked_rows():
    """The worked case's rounds 2 and 3, or None where benchmark/ is not in the tree."""
    import convention_parser as cp
    import text_extract
    if not WORKED_CONTEXT.is_dir():
        return None
    with tempfile.TemporaryDirectory(prefix="shimmer_gate_worked_rows_") as tmp:
        root = Path(tmp)
        (root / "input" / "conventions").mkdir(parents=True)
        for rules in (WORKED_CONTEXT.parent / "conventions").iterdir():
            (root / "input" / "conventions" / rules.name).write_bytes(rules.read_bytes())
        conventions = cp.parse_conventions(root).as_dict()["conventions"]

    def read(name):
        return text_extract.extract_text(WORKED_CONTEXT / name)
    return _compared(read("seat_agreement_round_2.docx"), read("seat_agreement_round_3.docx"), conventions)


def _rows_problem():
    """None, or what is wrong: a row is withdrawn only when it is gone."""
    problems = []
    made = _compared(ROWS_BEFORE, ROWS_AFTER, [ROWS_RULE])
    withdrawn = sorted(k for k, v in made.items() if v == "absent_since_prior")
    if withdrawn != ["beta entry"]:
        problems.append("rows read as withdrawn: %r" % withdrawn)
    worked = _worked_rows()
    if worked is not None:
        withdrawn = sorted(k for k, v in worked.items() if v == "absent_since_prior")
        if withdrawn != ["refund decision period"]:
            problems.append("worked case withdrawals: %r" % withdrawn)
    return "; ".join(problems) or None


FIXTURES = [
    ("possible_rename", lambda: _absent(["Alpha count: 42 units", "Beta score: 17 units", "Gamma total: 9 units"])),
    ("possible_successor", lambda: _absent(["Alpha count: 42 units", "Beta score: 21.25 units",
                                            "Gamma total: 9 units"])),
    ("possible_successor_no_unit", lambda: _absent(["Alpha count: 42", "Beta score: 21.25", "Gamma total: 9"],
                                                   V1_NO_UNIT)),
    ("no_citation", lambda: _absent(["Alpha count: 42 units", "Beta level: 17 units"], ref="")),
    ("tie", _tie),
    ("unit_mismatch", lambda: _checks([])),
    ("disagreeing_bands", lambda: _checks([{"low": 1.0, "high": 5.0, "unit": "units"},
                                           {"low": 2.0, "high": 9.0, "unit": "units"}])),
    ("no_key_column", lambda: _table_refusals("| Item | Figure |\n|---|---|\n| Alpha count | 4 units |\n"
                                              "| Alpha count | 5 units |\n", ["alpha count"])),
    ("value_column_count", lambda: _table_refusals("| Item | Low | High |\n|---|---|---|\n"
                                                   "| Alpha count | 4 units | 5 units |\n"
                                                   "| Beta level | 6 units | 7 units |\n", ["alpha count"])),
    ("tie", lambda: _table_refusals("| Item | Alias | Figure |\n|---|---|---|\n"
                                    "| Alpha count | Zeta mark | 4 units |\n"
                                    "| Beta level | Alpha count | 5 units |\n", ["alpha count"])),
    ("reverse_tie", lambda: _table_refusals("| Item | Other | Figure |\n|---|---|---|\n"
                                            "| Alpha count | Beta level | 4 units |\n"
                                            "| Gamma total | Delta span | 5 units |\n",
                                            ["alpha count", "beta level"])),
]


def observe():
    """(ok, detail): every fixture yields its kind, every refusal a listed kind, and the
    copy into review_data.json keeps it."""
    import paired_review as pr
    kinds = set(pr.PRIOR_REFUSAL_KINDS)
    for want, run in FIXTURES:
        refused = run()
        got = [r.get("reason_kind") for r in refused]
        if want not in got or any(k not in kinds for k in got) or any(not r.get("reason") for r in refused):
            return False, "%s: refusals carry %r" % (want, got)
    refused, orphans, copied = _pipeline_run()
    if "no_rule" not in [r.get("reason_kind") for r in refused] or not refused:
        return False, "pipeline: no_rule missing from %r" % [r.get("reason_kind") for r in refused]
    if [o.get("reason_kind") for o in orphans] != ["orphan"]:
        return False, "pipeline: orphans carry %r" % [o.get("reason_kind") for o in orphans]
    if [c.get("reason_kind") for c in copied] != [r.get("reason_kind") for r in refused]:
        return False, "review_data copy carries %r" % [c.get("reason_kind") for c in copied]
    problem = _rows_problem()
    if problem:
        return False, problem
    return True, "%d fixtures, the pipeline run and the table rows" % len(FIXTURES)


def _old_copy(doc):
    """pipeline._prior_refusals_for as it was before D-042: the kind is dropped."""
    out = []
    for entry in ((doc.get("_pairing") or {}).get("units") or []):
        for r in ((entry.get("prior_comparisons") or {}).get("refused") or []):
            out.append({"unit_id": entry.get("unit_id"), "label": r.get("label", ""),
                        "reason": r.get("reason", "")})
    return out


def _strip_kind(original):
    def absent_checks(*a, **k):
        checks, refused = original(*a, **k)
        return checks, [{x: y for x, y in r.items() if x != "reason_kind"} for r in refused]
    return absent_checks


def _no_document_rows(original):
    """As before D-275: no row of the document under review is present."""
    return lambda text, known_units=(): set()


def _changed_row_lost(original):
    """Only the row whose figure changed is lost: a change read as a withdrawal."""
    return lambda text, known_units=(): {label for label in original(text, known_units)
                                         if label not in {("gamma", "entry"), ("security", "service")}}


def _earlier_rows_not_read(original):
    """The earlier table's rows are not read: a row really removed goes unreported."""
    return lambda table: []


def neutralisations():
    import paired_review as pr
    import pipeline as pl
    return [("the review_data copy drops reason_kind", pl, "_prior_refusals_for", lambda orig: _old_copy),
            ("absent_checks writes no reason_kind", pr, "absent_checks", _strip_kind),
            ("no table row of the document is read", pr, "table_row_labels", _no_document_rows),
            ("a row whose figure changed is lost", pr, "table_row_labels", _changed_row_lost),
            ("an earlier table's rows are not read", pr, "_table_row_figures", _earlier_rows_not_read)]


def check():
    ok, detail = observe()
    if not ok:
        return ("FAIL", detail)
    proofs = []
    for name, obj, attr, make in neutralisations():
        original = getattr(obj, attr)
        setattr(obj, attr, make(original))
        try:
            caught, why = observe()
        finally:
            setattr(obj, attr, original)
        if caught:
            return ("FAIL", "neutralised (%s) and not caught" % name)
        restored, again = observe()
        if not restored:
            return ("FAIL", "restored (%s) and failing: %s" % (name, again))
        proofs.append("%s: caught (%s), restored" % (name, why))
    return ("PASS", "every refusal of a change record carries a typed reason_kind from "
                    "paired_review.PRIOR_REFUSAL_KINDS beside its sentence: %s; "
                    "pipeline._prior_comparison writes no_rule and orphan, and "
                    "_prior_refusals_for keeps the kind in review_data.json; a table row is "
                    "withdrawn only when it is gone (D-275); neutralised five ways and restored "
                    "(%s)" % (detail, "; ".join(proofs)))


if __name__ == "__main__":
    print(check())
