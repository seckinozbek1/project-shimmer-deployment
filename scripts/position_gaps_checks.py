"""Gate check: the gap between the parties, computed (D-S46 item 2, D-319). No model anywhere.

A computed movement means the same sentence with only the figure changed: two quotes are compared
only when they are identical as written (spacing collapsed, case kept) except for their one figure.

1. The worked case, scored against EXPECTED_MOVEMENT.json (the key written before the code) by
   tools/score_case_movement.py, and a perturbation the builder did not write against (parties
   swapped, measures renamed, each span located again): the measured 11 of 16, each row the rule
   refuses named with its reason.
2. The rule on small cases: another word anywhere refuses, spacing is collapsed, case is kept, all
   four quotes of two rounds must be the one sentence; equal gaps are unchanged; nothing is computed
   from words, carried forward or chosen among three parties; the parties' order changes nothing.
3. The independent checker's three rounds replayed (benchmark/fixtures/position_gaps_replay.json):
   its first case row by row, and every quote of its attack probes as a proof of its own, none a
   confident wrong record.
4. A position carries a figure and a unit only when it takes part in a computed gap; every other
   position names why it carries none.
5. Through the case phase, and a model's answer on a movement kept only on quotes in the round text.

Each is neutralise, fail, restore, pass (scripts/effect_proof.py). The key and the scorer live
outside scripts/ and are read by path.
"""
import copy
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from effect_proof import prove_effect  # noqa: E402
import multi_round as mr  # noqa: E402
import multi_round_phase as ph  # noqa: E402
import paired_review  # noqa: E402
import position_gaps as pg  # noqa: E402

CASE = ROOT / "benchmark" / "dev_cases" / "host_agreement_three_rounds"
KEY = CASE / "EXPECTED_MOVEMENT.json"
# The perturbation's renames, read from the fixture: the words are the case's own measures.
RENAMES = ()


def _scorer():
    spec = importlib.util.spec_from_file_location("shimmer_score_case_movement", ROOT / "tools" / "score_case_movement.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _case():
    """(manifest, {document id: text}) of the worked case, read as a run reads it."""
    import text_extract
    manifest = json.loads((CASE / "workload" / "case_manifest.json").read_text(encoding="utf-8"))
    texts = {p.stem: text_extract.extract_text(p).replace("\r\n", "\n") for p in sorted((CASE / "workload" / "context").iterdir())}
    return manifest, texts


def _rows(manifest, texts):
    manifest = mr.validate_manifest(manifest)
    evidence = []
    for i, s in enumerate(manifest["sources"], start=1):
        assert texts[s["document_id"]][s["char_start"]:s["char_end"]] == s["quote"], s["source_id"]
        evidence.append(dict(s, ref_id="REF-%04d" % i))
    positions = [r for r in ph.computed_records(manifest, evidence) if r["kind"] == "position"]
    return pg.gaps(manifest, positions)[1]


def _renames():
    """The perturbation's renames (each measure the worked case writes, to another), from the fixture."""
    return [tuple(pair) for pair in json.loads(REPLAY_FIXTURE.read_text(encoding="utf-8"))["perturbation_renames"]]


REPLAY_FIXTURE = ROOT / "benchmark" / "fixtures" / "position_gaps_replay.json"


def perturbed(manifest, texts):
    """The case with its two parties swapped and its measures renamed, each span located again."""
    manifest, texts = copy.deepcopy(manifest), dict(texts)
    swap = {"host_state": "organisation", "organisation": "host_state"}
    for doc_id, text in texts.items():
        for old, new in _renames():
            text = re.sub(r"\b%s\b" % old, new, text)
        texts[doc_id] = text
    for actor in manifest["actors"]:
        actor["actor_id"] = swap[actor["actor_id"]]
    for issue in manifest["issues"]:
        # The declared unit is the operator's own word in the documents' language: renamed with them.
        if "unit" in issue:
            for old, new in _renames():
                issue["unit"] = re.sub(r"\b%s\b" % old, new, issue["unit"])
    for source in manifest["sources"]:
        source["actor_id"] = swap[source["actor_id"]]
        quote = source["quote"]
        for old, new in _renames():
            quote = re.sub(r"\b%s\b" % old, new, quote)
        start = texts[source["document_id"]].find(quote)
        assert start >= 0, source["source_id"]
        source.update(quote=quote, char_start=start, char_end=start + len(quote))
    return manifest, texts



def _scored(rows):
    """The key's score, and each missed row with the reason Python gave, so a change that silently
    recovers or loses a row fails."""
    result = _scorer().score(rows, json.loads(KEY.read_text(encoding="utf-8")))
    why = {(r["issue_id"], tuple(r["rounds"])): r.get("why") for r in rows}
    return {"matched": result["matched"], "of": result["of"],
            "missed": [(r["issue_id"], r["rounds"], r["got"], why.get((r["issue_id"], tuple(r["rounds"]))))
                       for r in result["rows"] if not r["ok"]]}


def observe_key():
    """The worked case and its perturbation, each scored against the key."""
    return {"worked": _scored(_rows(*_case())), "perturbed": _scored(_rows(*perturbed(*_case())))}


# D-322 (D-S70 item 4): the worked case declares each figure issue's unit (days, months, its currency), so its
# figures are read against the operator's own words and every row matches the key.
WORKED = {"matched": 16, "of": 16, "missed": []}
# Without the declared units (D-319's same-sentence path alone) five rows are refused, each named:
# no quote of the worked case is the other party's sentence with only the figure changed.
WORKED_WITHOUT_UNITS = {"matched": 11, "of": 16, "missed": [
    ("entry-period", ["r1", "r2"], "not_computed", "quotes_differ_outside_figure_in_r1"),
    ("termination-notice", ["r1", "r2"], "not_computed", "quotes_differ_outside_figure_in_r1"),
    ("termination-notice", ["r2", "r3"], "not_computed", "quotes_differ_outside_figure_in_r2"),
    ("annual-contribution", ["r1", "r2"], "not_computed", "quotes_differ_outside_figure_in_r1"),
    ("annual-contribution", ["r2", "r3"], "not_computed", "quotes_differ_outside_figure_in_r2")]}


def _no_declared_units():
    return patch.object(pg, "declared_unit", lambda manifest, issue_id: None)


def observe_key_without_units():
    with _no_declared_units():
        return observe_key()


_REAL_SENTENCE = pg.sentence


def _loose_sentence(text):
    """Neutralisation: every quote with one figure is "the same sentence" (the reading of D-S46 item 2
    before D-319: the words around a figure are not compared at all)."""
    form, value = _REAL_SENTENCE(text)
    return (pg.FIGURE, value) if form is not None else (form, value)


def _position(actor, rnd, value, issue="i1", text=None):
    """A position record as the case phase writes one; its figure is read from its text."""
    if text is None:
        text = "Stated in words only." if value is None else "Notice: %r days." % value
    return {"record_id": "position.%s.%s.%s" % (rnd, actor, issue), "kind": "position", "state": "accepted",
            "actor_id": actor, "issue_id": issue, "round_id": rnd, "source_ids": ["s.%s.%s" % (rnd, actor)],
            "ref_ids": ["REF-%s-%s" % (rnd, actor)], "position": text, "text": text}


MANIFEST = {"case_id": "gap_fixture", "rounds": [{"round_id": "r1", "sequence": 1}, {"round_id": "r2", "sequence": 2},
                                                   {"round_id": "r3", "sequence": 3}],
            "issues": [{"issue_id": "i1"}]}


def _why(rows):
    return rows[0].get("why", rows[0]["outcome"])


def observe_rules():
    """The rule on small cases: equal gaps, nothing from words, nothing carried, not three parties,
    another word anywhere, spacing collapsed, case kept, and the four quotes of both rounds."""
    def gaps(*positions):
        return _why(pg.gaps(MANIFEST, list(positions))[1])
    p = _position
    return {
        "equal": gaps(p("a", "r1", 30), p("b", "r1", 20.0), p("a", "r2", 25.0000000001), p("b", "r2", 15)),
        "words": gaps(p("a", "r1", None), p("b", "r1", 20), p("a", "r2", 25), p("b", "r2", 15)),
        "carried": gaps(p("a", "r1", 30), p("b", "r1", 20), p("a", "r2", 25)),
        "three": gaps(*[p(x, r, 10) for x in ("a", "b", "c") for r in ("r1", "r2")]),
        "another_word": gaps(p("a", "r1", 30), p("b", "r1", None, text="Notice: 20 days only."),
                             p("a", "r2", 25), p("b", "r2", 15)),
        "spacing": gaps(p("a", "r1", None, text="Notice:   30\tdays."), p("b", "r1", 20),
                        p("a", "r2", 25), p("b", "r2", 15)),
        "case": gaps(p("a", "r1", None, text="notice: 30 days."), p("b", "r1", 20), p("a", "r2", 25), p("b", "r2", 15)),
        "across_rounds": gaps(p("a", "r1", 30), p("b", "r1", 20), p("a", "r2", None, text="Notice: 25 weeks."),
                              p("b", "r2", None, text="Notice: 15 weeks.")),
    }


RULES = {"equal": "unchanged_from_prior", "words": "a_position_in_words_in_r1", "carried": "a_party_states_nothing_in_r2",
         "three": "more_than_two_parties_in_r1", "another_word": "quotes_differ_outside_figure_in_r1",
         "spacing": "unchanged_from_prior", "case": "quotes_differ_outside_figure_in_r1",
         "across_rounds": "quotes_differ_outside_figure_between_r1_and_r2"}


DECLARED = {"case_id": "declared", "rounds": MANIFEST["rounds"], "issues": [{"issue_id": "i1", "unit": "days"}]}


def observe_declared():
    """A declared unit (days) read as written: any words around the figure and its unit, but the unit
    must stand right after the figure, whole, to a word's edge; any other measure is refused."""
    def gaps(*texts):
        positions = [_position(x, r, None, text=t) for (x, r), t in zip((("a", "r1"), ("b", "r1"), ("a", "r2"), ("b", "r2")), texts)]
        return _why(pg.gaps(DECLARED, positions)[1])
    return {
        "prose_around": gaps("A decision within 14 days is the norm.", "Visa applications need 30 days.",
                             "It proposes 21 days for visas.", "It can accept 21 days in principle."),
        "another_measure": gaps("Within 14 days.", "Within 3 weeks.", "Within 21 days.", "Within 21 days."),
        "a_longer_word": gaps("Within 14 dayshifts.", "Within 30 dayshifts.", "Within 21 days.", "Within 21 days."),
        "a_qualifier_between": gaps("Within 14 calendar days.", "Within 30 days.", "Within 21 days.", "Within 21 days."),
        "case_kept": gaps("Within 14 Days.", "Within 30 days.", "Within 21 days.", "Within 21 days."),
        "two_figures": gaps("Not 90 days but 45 days.", "Within 30 days.", "Within 21 days.", "Within 21 days."),
    }


DECLARED_OUTCOMES = {"prose_around": "moved_toward", "another_measure": "not_the_declared_unit_in_r1",
                     "a_longer_word": "not_the_declared_unit_in_r1", "a_qualifier_between": "not_the_declared_unit_in_r1",
                     "case_kept": "not_the_declared_unit_in_r1", "two_figures": "several_figures_in_r1"}


def _any_unit(text, unit):
    """Neutralisation: the declared unit not read at all; a quote's one figure is taken in it."""
    value, why = _REAL_DECLARED(text, unit)
    if why == "not_the_declared_unit":
        found = [m for m in paired_review._QUANTITY.finditer(str(text)) if paired_review.norm_number(m.group("num")) is not None]
        return paired_review.norm_number(found[0].group("num")), None
    return value, why


_REAL_DECLARED = pg.declared_figure


def observe_order():
    """The gap is between the parties whoever they are: one case with its parties written in each
    order (the larger figure first, then second)."""
    out = {}
    for name, (a, b) in (("larger_first", ("a", "b")), ("larger_second", ("b", "a"))):
        out[name] = _why(pg.gaps(MANIFEST, [_position(a, "r1", 40), _position(b, "r1", 10),
                                            _position(a, "r2", 35), _position(b, "r2", 20)])[1])
    return out


ORDER = {"larger_first": "moved_toward", "larger_second": "moved_toward"}


REPLAY = ROOT / "benchmark" / "fixtures" / "position_gaps_replay.json"


def observe_replay():
    """The independent checker's first case replayed: every row's outcome or reason."""
    value = json.loads(REPLAY.read_text(encoding="utf-8"))
    positions = [_position(q["actor_id"], q["round_id"], None, issue=q["issue_id"], text=q["quote"]) for q in value["quotes"]]
    manifest = {"case_id": "replay", "issues": [{"issue_id": i} for i in value["issues"]],
                "rounds": [{"round_id": r, "sequence": n} for n, r in enumerate(value["rounds"])]}
    return {"%s %s-%s" % (r["issue_id"], *r["rounds"]): _why([r]) for r in pg.gaps(manifest, positions)[1]}


REPLAYED = {"rent r1-r2": "quotes_differ_outside_figure_in_r1", "rent r2-r3": "quotes_differ_outside_figure_in_r2",
            "deposit r1-r2": "quotes_differ_outside_figure_in_r1", "deposit r2-r3": "quotes_differ_outside_figure_in_r2",
            "lease-term r1-r2": "quotes_differ_outside_figure_in_r1",
            "lease-term r2-r3": "quotes_differ_outside_figure_in_r2",
            "subletting r1-r2": "a_position_in_words_in_r1", "subletting r2-r3": "a_position_in_words_in_r2",
            "notice r1-r2": "quotes_differ_outside_figure_in_r1", "notice r2-r3": "several_figures_in_r2",
            "maintenance-cap r1-r2": "quotes_differ_outside_figure_in_r1", "maintenance-cap r2-r3": "a_position_in_words_in_r2"}


TWO_ROUNDS = {"case_id": "attack", "rounds": [{"round_id": "r1", "sequence": 1}, {"round_id": "r2", "sequence": 2}],
              "issues": [{"issue_id": "i1"}]}


def _attacks():
    return json.loads(REPLAY.read_text(encoding="utf-8"))["attacks"]


def observe_attack(name, declared=False):
    """One of the checker's round-2 and round-3 attacks: its outcome or reason, with no declared unit
    (the same-sentence path) or read against the unit an operator would declare for it."""
    attack = next(a for a in _attacks() if a["name"] == name)
    positions = [_position(actor, rnd, None, text=text) for rnd in ("r1", "r2") for actor, text in zip(("a", "b"), attack[rnd])]
    manifest = dict(TWO_ROUNDS, issues=[{"issue_id": "i1", "unit": attack["declared_unit"]}]) if declared else TWO_ROUNDS
    return _why(pg.gaps(manifest, positions)[1])


# Against its declared unit every same-money attack (groups A and D) is refused; the shapes that
# state one measure compute (the deposit "3 months of rent" against "2 months", the verb after the
# unit, the bracket after it, the label).
ATTACKS_DECLARED = {"b4_trailing_words_known": "moved_away", "c1_article_number": "several_figures_in_r1",
                    "c2_written_number": "a_position_in_words_in_r1", "e1_3-word_measure_then_verb": "moved_toward",
                    "e2_bracket_not_a_measure": "moved_toward", "e3_shape_that_computes": "moved_toward",
                    "e4_label_colon": "moved_toward"}


def _declared_attack_neutraliser(name):
    if name == "c1_article_number":
        return lambda: patch.object(pg, "declared_figure", lambda text, unit: _REAL_DECLARED(
            str(text)[:[m for m in paired_review._QUANTITY.finditer(str(text))][1].start()]
            if len(list(paired_review._QUANTITY.finditer(str(text)))) > 1 else text, unit))
    if name == "c2_written_number":
        return lambda: patch.object(pg, "declared_figure", lambda text, unit: (
            (0.0, None) if _REAL_DECLARED(text, unit)[1] == "a_position_in_words" else _REAL_DECLARED(text, unit)))
    if ATTACKS_DECLARED.get(name, "").startswith("moved"):
        return lambda: patch.object(pg, "relation", lambda before, now: "unchanged_from_prior")
    return lambda: patch.object(pg, "declared_figure", _any_unit)


# Every attack's outcome. Only the label with a colon is the same sentence with only the figure
# changed; everything else, including the shapes that look harmless, is refused.
ATTACKS = {"c1_article_number": "several_figures_in_r1", "c2_written_number": "a_position_in_words_in_r1",
           "e4_label_colon": "moved_toward"}


def _first_figure_sentence(text):
    """Neutralisation: a quote with several figures read by its first one."""
    found = [m for m in paired_review._QUANTITY.finditer(str(text or "")) if paired_review.norm_number(m.group("num")) is not None]
    if len(found) > 1:
        return _REAL_SENTENCE(str(text)[:found[1].start()])
    return _REAL_SENTENCE(text)


def _figure_from_words(text):
    """Neutralisation: a quote with no figure read as the figure 0."""
    form, value = _REAL_SENTENCE(text)
    return (text, 0.0) if form is None and value == "a_position_in_words" else (form, value)


def _attack_neutraliser(name):
    """What would make this attack give a different answer: for a refusal, the reading it refuses;
    for the one that computes, a relation that does not follow the gap."""
    if name == "c1_article_number":
        return lambda: patch.object(pg, "sentence", _first_figure_sentence)
    if name == "c2_written_number":
        return lambda: patch.object(pg, "sentence", _figure_from_words)
    if name == "e4_label_colon":
        return lambda: patch.object(pg, "relation", lambda before, now: "moved_away")
    return lambda: patch.object(pg, "sentence", _loose_sentence)


def observe_agreement():
    """Through the case phase's own records, on a case with one issue the same sentence with only the
    figure changed and one that is not: a position carries a figure only when it takes part in a
    computed gap, its unit that gap's sentence, and every other position names why it carries none."""
    rows = [("r1", "a", "i1", "Notice: 90 days"), ("r1", "b", "i1", "Notice: 30 days"),
            ("r2", "a", "i1", "Notice: 60 days"), ("r2", "b", "i1", "Notice: 45 days"),
            ("r1", "a", "i2", "The monthly rent is 9,000 credits."), ("r1", "b", "i2", "The yearly rent is 108,000 credits."),
            ("r2", "a", "i2", "The monthly rent is 9,000 credits."), ("r2", "b", "i2", "The yearly rent is 100,000 credits.")]
    sources = [{"source_id": "s%d" % n, "round_id": r, "actor_id": a, "issue_id": i, "document_id": "doc_" + r,
                "unit_id": "u01", "char_start": 0, "char_end": len(q), "quote": q, "state": "accepted"}
               for n, (r, a, i, q) in enumerate(rows, start=1)]
    manifest = mr.validate_manifest({
        "schema_version": 1, "case_id": "agreement", "fixture": True, "sources": sources,
        "actors": [{"actor_id": "a"}, {"actor_id": "b"}], "issues": [{"issue_id": "i1"}, {"issue_id": "i2"}],
        "rounds": [{"round_id": "r1", "sequence": 1, "document_ids": ["doc_r1"]},
                   {"round_id": "r2", "sequence": 2, "document_ids": ["doc_r2"]}]})
    records = ph.computed_records(manifest, [dict(s, ref_id="REF-%04d" % n) for n, s in enumerate(sources, start=1)])
    trajectories = [r for r in records if r["kind"] == "trajectory"]
    in_gap = {pid: t["measure"] for t in trajectories for pid in t["position_ids"]}
    return {"trajectories": [(t["issue_id"], t["relation"], t["measure"]) for t in trajectories],
            "positions": sorted((r["issue_id"], r["round_id"], r["actor_id"], r.get("value"), r.get("unit"),
                                 r.get("figure_left_out"), r["record_id"] in in_gap and r.get("unit") == in_gap[r["record_id"]])
                                for r in records if r["kind"] == "position")}


AGREEMENT = {"trajectories": [("i1", "moved_toward", "Notice: [figure] days")],
             "positions": sorted([
                 ("i1", "r1", "a", 90.0, "Notice: [figure] days", None, True),
                 ("i1", "r1", "b", 30.0, "Notice: [figure] days", None, True),
                 ("i1", "r2", "a", 60.0, "Notice: [figure] days", None, True),
                 ("i1", "r2", "b", 45.0, "Notice: [figure] days", None, True),
                 ("i2", "r1", "a", None, None, "quotes_differ_outside_figure_in_r1", False),
                 ("i2", "r1", "b", None, None, "quotes_differ_outside_figure_in_r1", False),
                 ("i2", "r2", "a", None, None, "quotes_differ_outside_figure_in_r1", False),
                 ("i2", "r2", "b", None, None, "quotes_differ_outside_figure_in_r1", False)])}


def _any_single_figure(position, in_gaps):
    """Neutralisation: a position carries the figure of any quote holding one, as before D-319."""
    form, value = pg.sentence(position.get("position", ""))
    return (value, form) if form is not None else (None, value)


def _phase_manifest():
    """The case phase's fixture case with a second party stating the same figure in both rounds."""
    from multi_round_rounds_checks import documents, manifest
    value = manifest(documents(70))
    value["actors"] = [{"actor_id": "actor_a"}, {"actor_id": "actor_b"}]
    value["sources"] = value["sources"] + [dict(s, source_id=s["source_id"] + "_b", actor_id="actor_b")
                                           for s in value["sources"]]
    return value


def observe_phase():
    import case_questions as cq
    from multi_round_rounds_checks import mocked_multi_round_run
    config = dict(cq.load_config(), agent=None)   # nothing asked: what Python computes, alone
    with tempfile.TemporaryDirectory(prefix="shimmer_gaps_") as td, patch.object(cq, "load_config", lambda: config):
        run = mocked_multi_round_run(td, case_manifest=_phase_manifest())
        trajectories = [r for r in run["record"]["records"] if r["kind"] == "trajectory"]
        text = next(Path(run["run_dir"]).rglob("case_positions.md")).read_text(encoding="utf-8")
        return {"code": run["code"], "rows": [r["outcome"] for r in run["record"].get("position_gaps") or []],
                "trajectories": [(r["relation"], r["written_by"], r["actor_ids"]) for r in trajectories],
                "shown": "Computed: unchanged_from_prior" in text}


PHASE = {"code": 0, "rows": ["unchanged_from_prior"],
         "trajectories": [("unchanged_from_prior", "python", ["actor_a", "actor_b"])], "shown": True}


def observe_quotes():
    import case_questions as cq
    from case_questions_checks import fixture, stub, _movement
    out = {}
    standing = {}
    for s in fixture()["evidence"]:
        standing[s["document_id"]] = standing.get(s["document_id"], "") + s["quote"] + " "
    for name, documents in (("standing", [{"id": k, "text": v} for k, v in standing.items()]),
                            ("absent", [{"id": k, "text": "Other words only."} for k in standing])):
        record = fixture()
        layer = cq.run(record, documents, decide=stub("toward"))
        out[name] = (sorted({r["outcome"] for r in layer["movements"]}), _movement(record)["movement"])
    return out


QUOTES = {"standing": (["decided", "not_asked_no_other_position"], "concession"),
          "absent": (["not_asked_no_other_position", "refused_quotes_not_in_round"], "unknown")}


class PositionGapChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        PositionGapChecks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    def test_the_key(self):
        if not KEY.is_file():
            self.skipTest("benchmark/dev_cases/ is not in this tree")
        # The declared units are what makes 16 of 16: without them the case falls to its same-sentence
        # reading.
        self.prove("scored_against_the_key", observe_key, {"worked": WORKED, "perturbed": WORKED}, _no_declared_units)

    def test_the_key_without_declared_units(self):
        if not KEY.is_file():
            self.skipTest("benchmark/dev_cases/ is not in this tree")
        # D-319's path alone: the measured 11 of 16 is that rule and nothing else; with the words around
        # the figure not compared the five rows come back.
        self.prove("scored_against_the_key_without_declared_units", observe_key_without_units,
                   {"worked": WORKED_WITHOUT_UNITS, "perturbed": WORKED_WITHOUT_UNITS},
                   lambda: patch.object(pg, "sentence", _loose_sentence))

    def test_a_declared_unit_is_read_as_written(self):
        self.prove("a_declared_unit_is_read_as_written", observe_declared, DECLARED_OUTCOMES,
                   lambda: patch.object(pg, "declared_figure", _any_unit))

    def test_a_declared_unit_ends_at_a_words_edge(self):
        real = pg.declared_figure

        def no_edge(text, unit):
            # The edge test removed: "dayshifts" read as "days".
            return real(str(text).replace(unit + "hifts", unit), unit) if (unit + "hifts") in str(text) else real(text, unit)
        self.prove("a_declared_unit_ends_at_a_words_edge", lambda: observe_declared()["a_longer_word"],
                   DECLARED_OUTCOMES["a_longer_word"], lambda: patch.object(pg, "declared_figure", no_edge))

    def test_the_rule(self):
        self.prove("only_the_same_sentence_with_the_figure_changed", observe_rules, RULES,
                   lambda: patch.object(pg, "sentence", _loose_sentence))

    def test_a_gap_needs_its_two_quotes_to_agree(self):
        # One round, two parties: with only this level removed, "Notice: 20 days only." is compared
        # with "Notice: 30 days." as if the same sentence.
        self.prove("a_gap_needs_its_two_quotes_to_agree", observe_rules, RULES,
                   lambda: patch.object(pg, "same_sentence", lambda a, b: True))

    def test_a_movement_needs_all_four_quotes_to_agree(self):
        # Round 1's two quotes agree and round 2's two agree, but round 2's sentence is not round 1's
        # ("weeks" for "days"): with only the across-rounds level removed the movement is computed.
        self.prove("a_movement_needs_all_four_quotes_to_agree", lambda: observe_rules()["across_rounds"],
                   RULES["across_rounds"], lambda: patch.object(pg, "rounds_agree", lambda a, b: True))

    def test_equal_gaps_are_unchanged(self):
        self.prove("equal_gaps_unchanged", observe_rules, RULES,
                   lambda: patch.object(paired_review, "_close", lambda a, b: a == b))

    def test_nothing_carried_forward(self):
        real = pg._stated

        def carried(positions, round_id, issue_id):
            out = real(positions, round_id, issue_id)
            for p in positions:
                if p["issue_id"] == issue_id and p["actor_id"] not in out:
                    out[p["actor_id"]] = p
            return out
        self.prove("no_position_carried_forward", observe_rules, RULES, lambda: patch.object(pg, "_stated", carried))

    def test_whoever_the_parties_are(self):
        def signed(stated, unit=None):
            gap, form, actors = real(stated, unit)
            if gap is None:
                return gap, form, actors
            first, second = (pg.sentence(stated[a]["position"])[1] for a in sorted(stated))
            return first - second, form, actors
        real = pg._gap
        self.prove("whoever_the_parties_are", observe_order, ORDER, lambda: patch.object(pg, "_gap", signed))

    def test_the_first_checkers_case(self):
        if not REPLAY.is_file():
            self.skipTest("benchmark/fixtures/ is not in this tree")
        self.prove("the_first_checkers_case_replayed", observe_replay, REPLAYED,
                   lambda: patch.object(pg, "sentence", _loose_sentence))

    def test_every_attack(self):
        if not REPLAY.is_file():
            self.skipTest("benchmark/fixtures/ is not in this tree")
        for attack in _attacks():
            name = attack["name"]
            expected = ATTACKS.get(name, "quotes_differ_outside_figure_in_r1")
            self.prove("attack_" + name, lambda name=name: observe_attack(name), expected, _attack_neutraliser(name))

    def test_every_attack_against_its_declared_unit(self):
        if not REPLAY.is_file():
            self.skipTest("benchmark/fixtures/ is not in this tree")
        for attack in _attacks():
            name = attack["name"]
            expected = ATTACKS_DECLARED.get(name, "not_the_declared_unit_in_r1")
            self.prove("declared_attack_" + name, lambda name=name: observe_attack(name, declared=True), expected,
                       _declared_attack_neutraliser(name))

    def test_a_position_carries_a_figure_only_in_a_gap(self):
        self.prove("a_position_carries_a_figure_only_in_a_gap", observe_agreement, AGREEMENT,
                   lambda: patch.object(ph, "_numeric", _any_single_figure))

    def test_through_the_phase(self):
        self.prove("through_the_case_phase", observe_phase, PHASE,
                   lambda: patch.object(pg, "gaps", lambda manifest, positions: ([], [])))

    def test_a_models_quotes_are_checked(self):
        import case_questions as cq
        self.prove("a_models_quotes_are_checked", observe_quotes, QUOTES,
                   lambda: patch.object(cq, "check_quotes", lambda record, documents, rows: None))


def check():
    PositionGapChecks.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(PositionGapChecks).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:4])
    if result.skipped:
        return "SKIP", "benchmark/dev_cases/ is not in this tree"
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, no model: a gap is computed only between quotes that "
                    "state one figure in the unit the case declares for the issue, as written, or, with none declared, are "
                    "the same sentence with only the figure changed; the worked case scores 16 of 16 with its declared "
                    "units and the measured 11 of 16 without them, each refused row named; every one of the checker's "
                    "attacks (22) gives its own answer on both paths, none a confident wrong record; equal gaps are unchanged, nothing is computed from words, carried forward or "
                    "chosen among three parties, the parties' order changes nothing, a position carries a figure only in a "
                    "computed gap, and a model's answer stands only on quotes found in the round text"
                    % len(PositionGapChecks.evidence))


def main():
    status, detail = check()
    for proof in PositionGapChecks.evidence:
        print(proof["name"], proof["status"])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
