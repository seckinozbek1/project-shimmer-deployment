"""Gate check 322 (R1, operator decision D-S22 item 1 (d)): on both judged paths Python
refuses an answer it has nothing to check against.

The defect class: on a judged absence and on D-068's plan Python could compute nothing for,
a model's answer was kept whenever it passed the quote check and the missing_field
refusals. Three kinds of answer passed and could not be checked by anything: an absence
relation other than missing_field written with no quote, a relation that compares two
figures written with no figure, and an earlier-version relation in a run that declared no
earlier version. On the saved L12 records the parallel track found all five wrong ContractNLI
flags decided by such answers (docs/loop/private/parallel/FINDING_PUBLIC_GAP.md, not
tracked).

`paired_review.judged_item_refusal`, the one test for both judged paths, now refuses
(a) a relation of finding_record.ABSENCE_RELATIONS with no quote,
(b) a relation of finding_record.figure_relations() (read off the declared schema) with
    neither value_a nor value_b,
(c) a relation of finding_record.PRIOR_RELATIONS when no earlier version is declared
    (`prior_declared`, which the pipeline sets from the loaded earlier versions
    `_prior_comparison` runs on),
each with its own reason, tested after the refusals of today so none of those moves.

INFRA-046 (D-264): the same test holds a contradiction in words, the one relation with no
figure: (d) not marked irregular, (e) fewer than two quotes, no unit text, a quote too short
to be a passage, (f) a second quote the unit does not hold, (g) one passage quoted twice,
the same words or overlapping places. A contradiction with two passages of its unit is kept
on both judged paths and reaches the bus and review_data.json with both quotes and Python's
mark. Without that mark, from any other agent, or with a mark the model wrote, it is no
finding and no benchmark record. Two contradictions of one unit stay two, and one read
twice stays one. A reader sees both passages, on one line. Python checks the words, never
that they contradict.

Each observation runs the real phase 5.5 paired review on a mocked run
(`honest_output_checks.mocked_run`): no model, provider, network or GPU. The replies are
PRE-AUTHORED, NOT MODEL OUTPUT. Everything is written under a tempdir and removed. Each
refusal, and the pipeline's passing of the declared earlier version, is proven by
neutralise, fail, restore, pass.
"""
from __future__ import annotations

import ast
import contextlib
import functools
import importlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import agent_wrapper
import constitution_guard
import honest_output_checks as hoc
import judged_refusal_checks as jrc
import paired_review as pr
import uncomputable_judgment_checks as ujc

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmark" / "adapters"))
records = importlib.import_module("common.records")

A_REASON = pr.NO_QUOTE_ABSENCE_RELATION
B_REASON = pr.NO_FIGURES_FIGURE_RELATION
C_REASON = pr.PRIOR_RELATION_NO_EARLIER_VERSION
D_REASON = pr.CONTRADICTION_NOT_IRREGULAR
E_REASON = pr.CONTRADICTION_NEEDS_TWO_QUOTES
E_BLANK = pr.CONTRADICTION_NO_UNIT_TEXT
E_SHORT = pr.CONTRADICTION_QUOTE_TOO_SHORT
F_REASON = pr.CONTRADICTION_SECOND_QUOTE_NOT_IN_UNIT
G_REASON = pr.CONTRADICTION_SAME_PASSAGE
TODAY = sorted([jrc.NO_QUOTE_REASON, jrc.QUOTE_REASON])
CONTRADICTION_REFUSED = [D_REASON, E_REASON, E_SHORT, F_REASON, G_REASON]
# The relation of each kind the fixture writes: the first of each declared set, read from
# the declared source, so the fixture names no relation of its own.
ABSENCE_OTHER = next(r for r in pr.finding_record.ABSENCE_RELATIONS if r != "missing_field")
FIGURE = pr.finding_record.figure_relations()[0]
PRIOR = pr.finding_record.PRIOR_RELATIONS[0]
TEXT = pr.finding_record.TEXT_RELATIONS[0]
# Four passages added to the last unit of each fixture document.
P1, P2 = "The seal was intact on arrival", "The seal was broken at the gate"
P3, P4 = "The gate log was signed twice", "The gate log was never signed"
PASSAGES = "\n%s.\n%s.\n%s.\n%s.\n" % (P1, P2, P3, P4)


def _item(relation, rule_id, **extra):
    item = {"kind": "finding", "record_verdict": "irregular", "relation": relation,
            "explanation": "PRE-AUTHORED, NOT MODEL OUTPUT."}
    if rule_id:
        item["rule_id"] = rule_id
    item.update(extra)
    return item


def authored(kept_quote, rule_id):
    """PRE-AUTHORED, NOT MODEL OUTPUT. Per kind one answer refused and the same answer
    carrying what makes it checkable; plus the two refusals of today (an absence claim
    with no quote, a quote the unit does not contain)."""
    return [
        _item(ABSENCE_OTHER, rule_id, stated_field="countersignature"),              # (a) refused
        _item(ABSENCE_OTHER, rule_id, stated_field="countersignature", quote=kept_quote),  # kept
        _item(FIGURE, rule_id),                                                       # (b) refused
        _item(FIGURE, rule_id, value_a="N/A", value_b="none"),          # (b) placeholders refused
        _item(FIGURE, rule_id, value_a=12, unit_a="units", value_b=13, unit_b="units"),    # kept
        _item(PRIOR, rule_id, field_label="reading"),       # (c) refused unless declared
        _item("missing_field", rule_id, stated_field="countersignature"),             # today
        _item("missing_field", rule_id, stated_field="countersignature",
              quote="the countersignature is not stated"),                           # today
        _item(TEXT, rule_id, quote=P1, quote_b=P2),                                   # kept
        _item(TEXT, rule_id, quote=P3, quote_b=P4),                           # kept, a second
        _item(TEXT, rule_id, quote=P1, quote_b=P2, record_verdict="ok"),              # (d)
        _item(TEXT, rule_id, quote=P1),                                               # (e)
        _item(TEXT, rule_id, quote=P1, quote_b="gate"),                               # (e) short
        _item(TEXT, rule_id, quote=P1, quote_b="words this unit does not hold"),      # (f)
        _item(TEXT, rule_id, quote=P1, quote_b=" %s " % P1),                          # (g)
    ]


def _absence_reply(payload, call_id):
    items = (authored(jrc.ABSENCE_KEPT_QUOTE, hoc.JUDGED_RULE["id"])
             if jrc.ABSENCE_UNIT in str(payload.get("unit_id") or "") else [])
    return {"ok": True, "backend": "local_auditor", "model": "fixture-auditor", "call_id": call_id,
            "raw_text": "", "item_count": len(items),
            "parsed": {"agent": "PRACTICE_AUDITOR", "items": items}}


def _uncomputable_reply(payload, call_id, kwargs):
    if payload.get("rule_id") != ujc.RULE_ID:
        return None
    items = authored(ujc.KEPT_QUOTE, None)
    return {"ok": True, "backend": ujc.BACKEND, "model": ujc.MODEL, "call_id": call_id, "raw_text": "",
            "item_count": len(items), "parsed": {"agent": "PRACTICE_AUDITOR", "items": items}}


def _with_prior(declared):
    """The real phase 5.5, given one loaded earlier version when `declared` (as main()
    passes the documents _prior_docs_for loaded), else exactly as mocked_run calls it."""
    import pipeline as pl
    if not declared:
        return contextlib.nullcontext()
    earlier = {"id": "batch_sheet_earlier", "name": "batch_sheet_earlier.md", "text": hoc.DOC_TEXT}
    return patch.object(pl, "phase_5_5_convention_review",
                        functools.partial(pl.phase_5_5_convention_review, prior_docs=[earlier]))


def observe(declared):
    """What the real phase 5.5 refused and kept on both judged paths (no verdict here)."""
    td = tempfile.mkdtemp(prefix="shimmer_judged_unchecked_")
    try:
        for name in ("absence", "uncomputable"):
            (Path(td) / name).mkdir()
        with _with_prior(declared):
            run = hoc.mocked_run(Path(td) / "absence", style_guardian=False, rules=jrc.ABSENCE_RULES,
                                 text=hoc.DOC_TEXT + PASSAGES, absence_reply=_absence_reply)
        pairing = jrc._pairing(run)
        absence = {
            "refused": sorted(e.get("reason") for e in pairing.get("absence_refused") or []
                              if jrc.ABSENCE_UNIT in str(e.get("unit_id"))),
            "kept": sum(int(e.get("items") or 0) for e in pairing.get("absence") or []
                        if e.get("path") == "judged" and jrc.ABSENCE_UNIT in str(e.get("unit_id"))),
            "reached": _reached(run),
        }
        with _with_prior(declared):
            run = hoc.mocked_run(Path(td) / "uncomputable", style_guardian=False, text=ujc.TEXT + PASSAGES,
                                 rules=ujc.RULES, other_reply=_uncomputable_reply)
        pairing = jrc._pairing(run)
        uncomputable = {
            "refused": sorted(e.get("reason") for e in pairing.get("uncomputable_refused") or []
                              if e.get("rule_id") == ujc.RULE_ID),
            "kept": sum(int(e.get("items") or 0) for e in pairing.get("uncomputable_judged") or []
                        if e.get("rule_id") == ujc.RULE_ID),
            "reached": _reached(run),
        }
        return {"absence_judged": absence, "uncomputable": uncomputable}
    finally:
        shutil.rmtree(td, ignore_errors=True)


REACHED = sorted(sorted(pair) for pair in ([P1.lower(), P2.lower()], [P3.lower(), P4.lower()]))


def _reached(run):
    """The contradictions as review_data.json carries them: the two passages of each, read
    from the master, with Python's mark and the model's stamp, in order."""
    found = []
    for path in sorted(Path(run["run_dir"]).rglob("review_data.json")):
        for f in json.loads(path.read_text(encoding="utf-8")).get("model_findings_not_promoted") or []:
            if f.get("relation") == TEXT and f.get(pr.finding_record.SCREENED_FIELD) is True \
                    and f.get("written_by") == "model" and f.get("promoted") is False:
                found.append(sorted(str(f.get(k)).lower() for k in ("quote", "quote_b")))
    return sorted(found)


def _verdict(observed, want_refused, want_kept, what):
    problems = []
    for path, got in sorted(observed.items()):
        if got["refused"] != want_refused or got["kept"] != want_kept or got["reached"] != REACHED:
            problems.append("%s: refused %s, kept %d, reached %s; expected %s, kept %d"
                            % (path, got["refused"], got["kept"], got["reached"], want_refused, want_kept))
    return ("FAIL", "; ".join(problems)) if problems else ("PASS", what)


def body_undeclared():
    """No earlier version declared: (a), (b) and (c) refused with their own reasons, the
    quoted absence and the figure comparison kept, today's two refusals unchanged."""
    return _verdict(observe(False),
                    sorted(TODAY + [A_REASON, B_REASON, B_REASON, C_REASON] + CONTRADICTION_REFUSED), 4,
                    "with no earlier version declared, on both judged paths an absence relation "
                    "with no quote, a figure relation with no figures and an earlier-version "
                    "relation are refused with their own reasons (placeholder strings are no figures), the quoted and figured answers "
                    "kept, today's refusals unchanged; a contradiction is kept only irregular "
                    "and with two passages of its unit, and reaches review_data.json with both")


def body_declared():
    """An earlier version declared: the earlier-version answer is kept, nothing else moves."""
    return _verdict(observe(True), sorted(TODAY + [A_REASON, B_REASON, B_REASON] + CONTRADICTION_REFUSED), 5,
                    "with an earlier version declared the earlier-version answer is kept on both "
                    "judged paths")


# (quote, quote_b, unit text, verdict) -> reason, each on the one test of both judged paths.
UNIT = PASSAGES + "\nThe seal is intact. The seal is intact only on paper.\n"
CASES = [
    ((P1, P2, UNIT, "irregular"), None),
    ((P2, P1, UNIT, "IRREGULAR"), None),
    (("The seal is intact", "The seal is intact only on paper", UNIT, "irregular"), None),
    ((P1, P2, UNIT, "ok"), D_REASON),
    ((P1, None, UNIT, "irregular"), E_REASON),
    ((None, P2, UNIT, "irregular"), E_REASON),
    ((5, 6, "5 and 6 and 7", "irregular"), E_REASON),
    ((True, P2, UNIT, "irregular"), pr.QUOTE_NOT_IN_UNIT),
    ((P1, "   ", UNIT, "irregular"), E_REASON),
    (("made up first words", "made up second words", "", "irregular"), E_BLANK),
    (("made up first words", "made up second words", None, "irregular"), E_BLANK),
    (("a", "e", "a e i o u", "irregular"), E_SHORT),
    ((".", "!", ". !", "irregular"), E_SHORT),
    ((P1, "gate", UNIT, "irregular"), E_SHORT),
    ((P1, "words the unit lacks", UNIT, "irregular"), F_REASON),
    (("words the unit lacks", P2, UNIT, "irregular"), pr.QUOTE_NOT_IN_UNIT),
    ((P1, P1.upper(), UNIT, "irregular"), G_REASON),
    ((P1, "seal was intact on", UNIT, "irregular"), G_REASON),
    (("the seal was intact", "was intact on arrival", UNIT, "irregular"), G_REASON),
    (("The seal was intact", "The seal was intact.", "The seal was intact. The seal was intact.", "irregular"),
     G_REASON),
    (("2026-11-05", "2026-11-06", "2026-11-05 2026-11-06", "irregular"), E_SHORT),
    (("1,000.00", P2, UNIT + " 1,000.00", "irregular"), E_SHORT),
    (("| 12 |", "| 13 |", "| 12 |\n| 13 |", "irregular"), E_SHORT),
    (("| 2026-11-05 |", "| 2026-11-06 |", "| 2026-11-05 |\n| 2026-11-06 |", "irregular"), E_SHORT),
    (("| --- | --- |", P2, UNIT + " | --- | --- |", "irregular"), E_SHORT),
    (("- - -", P2, UNIT + " - - -", "irregular"), E_SHORT),
]


def _case_reason(case):
    quote, quote_b, unit, verdict = case
    try:
        return pr.judged_item_refusal({"relation": TEXT, "record_verdict": verdict, "quote": quote, "quote_b": quote_b},
                                      None, [], unit)
    except (TypeError, AttributeError) as exc:  # the type guard neutralised: a non-text quote reaches the readers
        return "raised: %s" % exc


def body_cases():
    """Each contradiction on the one test: kept, or refused with its own reason."""
    wrong = [(c[:2], want, _case_reason(c)) for c, want in CASES if _case_reason(c) != want]
    return ("FAIL", "%s" % wrong) if wrong else ("PASS", "%d contradiction cases decided" % len(CASES))


def body_only_screened():
    """Unscreened, from any agent, or with a mark the model wrote: no finding, no record. A
    screened one is both, and the benchmark reader's copies are the pipeline's."""
    fr = pr.finding_record
    raw = {"relation": TEXT, "record_verdict": "irregular", "quote": P1, "quote_b": P2}
    reply = {"agent": "VERIFIER", "doc_id": "d", "items": [dict(raw, **{fr.SCREENED_FIELD: True})]}
    with patch.object(agent_wrapper.AgentWrapper, "_contract_missing", lambda self, obj: []):
        forged = object.__new__(agent_wrapper.AgentWrapper)._finalize_envelope(reply)[0]["items"][0]
    screened = pr.mark_screened(dict(raw))
    other = pr.mark_screened({"relation": FIGURE, "record_verdict": "irregular"})
    problems = []
    if not fr.is_finding_shaped(raw):
        problems.append("the judged paths cannot read the reply")
    if fr.is_finding(raw) or records.is_typed_record(raw):
        problems.append("an unscreened contradiction is a finding or a record")
    if records.is_typed_record(dict(raw, relation=TEXT.title())):
        problems.append("another spelling of the relation is a benchmark record")
    if fr.is_finding(forged) or records.is_typed_record(forged):
        problems.append("a mark the model wrote survives its reading")
    if not (fr.is_finding(screened) and records.is_typed_record(screened)):
        problems.append("a screened contradiction is not a finding and a record")
    if fr.SCREENED_FIELD in other:
        problems.append("the mark reaches another relation")
    if (records.TEXT_RELATIONS, records.SCREENED_FIELD) != (fr.TEXT_RELATIONS, fr.SCREENED_FIELD):
        problems.append("the benchmark reader's copies differ")
    return ("FAIL", "; ".join(problems)) if problems else (
        "PASS", "only a contradiction Python screened is a finding or a benchmark record")


def body_dedupe():
    """Two contradictions of one unit stay two; one read in the other order or case stays one."""
    a = {"unit_id": "u", "rule_id": "r", "relation": TEXT, "quote": P1, "quote_b": P2}
    b = dict(a, quote=P3, quote_b=P4)
    swapped = dict(a, quote=" %s " % P2.upper(), quote_b=P1)
    got = len(pr.dedupe([a, b, swapped]))
    return ("PASS", "two contradictions stay two, one read twice stays one") if got == 2 else (
        "FAIL", "dedupe kept %d of 3, expected 2" % got)


def body_reader():
    """A reader sees both passages on one line, whatever their line breaks."""
    fr = pr.finding_record
    line = fr.reader_line(fr.model_finding_for_reader(
        {"relation": TEXT, "quote": "first\n# words", "quote_b": "second words",
         "record_verdict": "irregular", "unit_id": "u01-a"}))
    ok = "first # words" in line and "second words" in line and "\n" not in line
    return ("PASS", "a reader sees both passages on one line") if ok else ("FAIL", "the reader's line: %r" % line)


def _constitution():
    return json.loads((ROOT / "config" / "constitution.json").read_text(encoding="utf-8"))


def _unapproved():
    data = json.loads((ROOT / "config" / "constitution.json").read_text(encoding="utf-8"))
    for a in data["amendments"]:
        if a.get("id") == "INFRA-046":
            a["operator_approved"] = False
    return data


def body_governed():
    """INFRA-046 is the verified next id after INFRA-045, operator-approved, naming the
    relation, and the relation is declared in the schema and the fallback, no figure relation."""
    fr = pr.finding_record
    now = _constitution()
    ids = [a.get("id") for a in now["amendments"]]
    upto = dict(now, amendments=now["amendments"][:ids.index("INFRA-046") + 1]) if "INFRA-046" in ids else now
    before = dict(upto, amendments=upto["amendments"][:-1])
    entry = upto["amendments"][-1]
    problems = []
    if entry.get("id") != "INFRA-046" or TEXT not in str(entry.get("change")):
        problems.append("no INFRA-046 names the relation")
    if not constitution_guard.verify_amendment_append(before, upto).get("ok"):
        problems.append("the append does not verify")
    if TEXT not in fr.relations() or TEXT not in fr._FALLBACK["relations"]:
        problems.append("the relation is not declared in the schema and the fallback")
    if TEXT in fr.figure_relations():
        problems.append("the relation reads as a figure relation")
    return ("FAIL", "; ".join(problems)) if problems else (
        "PASS", "INFRA-046 verifies as the next id and the relation is declared in words")


def _function_without(name, line, new="pass", module=pr):
    """Function `name` of `module` compiled from the REAL source with the one `line`
    replaced. The file is read, never written. None when the function or the line cannot
    be found, which the caller reports as a failure."""
    source = Path(module.__file__).read_text(encoding="utf-8")
    node = next((n for n in ast.parse(source).body
                 if isinstance(n, ast.FunctionDef) and n.name == name), None)
    if node is None:
        return None
    lines = source.splitlines(keepends=True)
    func = "".join(lines[node.lineno - 1:node.end_lineno])
    if func.count(line) != 1:
        return None
    scope = dict(vars(module))
    exec(compile(func.replace(line, new, 1), "neutralised_source", "exec"), scope)
    return scope[name]


def _neutralise_in(name, line, new="pass", module=pr):
    fn = _function_without(name, line, new, module)
    if fn is None:
        raise RuntimeError("%s has no single line %s" % (name, line))
    return patch.object(module, name, fn)


@contextlib.contextmanager
def _really_kept(target, case):
    """The refusal `target` gone and the two-passages test out of the way, so that `case`
    is KEPT, not refused under the next reason. The patch comes first: the neutralised
    function is compiled against a copy of the module as it then stands. A case not kept
    stops the check, so this cannot pass as proven for another reason."""
    with patch.object(pr, "_two_passages", lambda a, b, text: True), _neutralise_line(target):
        if _case_reason(case) is not None:
            raise RuntimeError("neutralising %s kept nothing: %s" % (target, _case_reason(case)))
        yield


def _neutralise_line(target):
    return _neutralise_in("judged_item_refusal", "return %s" % target)


def _prior_never_passed():
    real = pr.judged_item_refusal

    def refusal(item, rule, fields_present, unit_text, **kwargs):
        return real(item, rule, fields_present, unit_text)
    return patch.object(pr, "judged_item_refusal", refusal)


def _neutralisations():
    return [
        ("(a) no-quote absence relation kept", body_undeclared,
         lambda: _neutralise_line("NO_QUOTE_ABSENCE_RELATION")),
        ("(b) figure relation with no figures kept", body_undeclared,
         lambda: _neutralise_line("NO_FIGURES_FIGURE_RELATION")),
        ("(b) a placeholder string read as a figure", body_undeclared,
         lambda: patch.object(pr, "_is_figure", pr._carries_value)),
        ("(c) earlier-version relation kept with none declared", body_undeclared,
         lambda: _neutralise_line("PRIOR_RELATION_NO_EARLIER_VERSION")),
        ("the pipeline never passes the declared earlier version", body_declared, _prior_never_passed),
        ("(d) a contradiction kept while not irregular", body_cases,
         lambda: _neutralise_line("CONTRADICTION_NOT_IRREGULAR")),
        ("(e) a one-quote contradiction not refused for that reason", body_cases,
         lambda: _neutralise_line("CONTRADICTION_NEEDS_TWO_QUOTES")),
        ("(e) a blank unit keeps invented quotes", body_cases,
         lambda: _really_kept("CONTRADICTION_NO_UNIT_TEXT", ("made up first words", "made up second words", "", "irregular"))),
        ("(e) a one-word quote kept", body_cases,
         lambda: _neutralise_line("CONTRADICTION_QUOTE_TOO_SHORT")),
        ("(e) table bars counted as words", body_cases,
         lambda: _neutralise_in("judged_item_refusal",
                                r'if any(sum(1 for w in q.split() if re.search(r"\w", w)) < PASSAGE_MIN_WORDS for q in quotes):',
                                "if any(len(q.split()) < PASSAGE_MIN_WORDS for q in quotes):")),
        ("(f) a second quote the unit does not hold kept", body_cases,
         lambda: _really_kept("CONTRADICTION_SECOND_QUOTE_NOT_IN_UNIT", (P1, "words the unit lacks", UNIT, "irregular"))),
        ("(g) one passage quoted twice kept", body_cases,
         lambda: _neutralise_line("CONTRADICTION_SAME_PASSAGE")),
        ("(g) overlapping places read as two passages", body_cases,
         lambda: _neutralise_in("_two_passages", "return any(a + len(first) <= b or b + len(second) <= a",
                                "return bool(places(first)) or any(a + len(first) <= b or b + len(second) <= a")),
        ("(g) a quote inside the other refused though it stands elsewhere", body_cases,
         lambda: patch.object(pr, "_two_passages", lambda a, b, text: a != b and a not in b and b not in a)),
        ("the relation in words read as a figure relation", body_cases,
         lambda: _neutralise_in("figure_relations", "                 and r not in TEXT_RELATIONS)",
                                "                 )", pr.finding_record)),
        ("(g) the same words with other punctuation read as two passages", body_cases,
         lambda: _neutralise_in("_two_passages", "if _one_wording(first, second):",
                                "if first == second:")),
        ("a kept contradiction never marked", body_undeclared,
         lambda: patch.object(pr, "mark_screened", lambda item: item)),
        ("an unmarked contradiction is a finding", body_only_screened,
         lambda: patch.object(pr.finding_record, "is_finding", pr.finding_record.is_finding_shaped)),
        ("a mark the model wrote survives", body_only_screened,
         lambda: patch.object(pr.finding_record, "without_screened_mark", lambda item: item)),
        ("the benchmark reader counts an unmarked contradiction", body_only_screened,
         lambda: patch.object(records, "TEXT_RELATIONS", ())),
        ("the benchmark reader misses another spelling", body_only_screened,
         lambda: _neutralise_in("is_typed_record",
                                'if str(item.get("relation") or "").casefold() in TEXT_RELATIONS',
                                'if item.get("relation") in TEXT_RELATIONS', records)),
        ("two contradictions of one unit deduped to one", body_dedupe,
         lambda: _neutralise_in("dedupe", 'key += tuple(sorted((_squash(item.get("quote")), _squash(item.get("quote_b")))))')),
        ("one contradiction read twice kept as two", body_dedupe,
         lambda: _neutralise_in("dedupe", 'key += tuple(sorted((_squash(item.get("quote")), _squash(item.get("quote_b")))))',
                                'key += (item.get("quote"), item.get("quote_b"))')),
        ("the reader's line loses the passages", body_reader,
         lambda: patch.object(pr.finding_record, "TEXT_RELATIONS", ())),
        ("the reader's line keeps a line break", body_reader,
         lambda: _neutralise_in("reader_line", 'first = " ".join(str(item.get("quote") or "?").split())',
                                'first = str(item.get("quote") or "?")', pr.finding_record)),
        ("INFRA-046 not approved", body_governed,
         lambda: patch.object(sys.modules[__name__], "_constitution", _unapproved)),
    ]


BODIES = (body_undeclared, body_declared, body_cases, body_only_screened, body_dedupe, body_reader,
          body_governed)


def check():
    shipped = [body() for body in BODIES]
    if any(v != "PASS" for v, _ in shipped):
        return "FAIL", "shipped: " + "; ".join(d for v, d in shipped if v != "PASS")
    for name, body, neutralise in _neutralisations():
        try:
            with neutralise():
                verdict, detail = body()
        except RuntimeError as e:
            return "FAIL", str(e)
        if verdict != "FAIL":
            return "FAIL", "neutralised (%s) still passed: %s" % (name, detail)
    restored = [body() for body in BODIES]
    if any(v != "PASS" for v, _ in restored):
        return "FAIL", "after restore: " + "; ".join(d for v, d in restored if v != "PASS")
    return "PASS", "%s; %d neutralisations fail, restore passes" % (
        "; ".join(d for _, d in shipped), len(_neutralisations()))


if __name__ == "__main__":
    print(json.dumps(check()))
