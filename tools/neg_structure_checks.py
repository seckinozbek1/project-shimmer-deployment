#!/usr/bin/env python3
"""Checks 490 to 494 (lane neg-structure): the negotiation items' party structure (Seckin 16 November 2026 20:32),
D-668 audit gaps 4 (three-party moves) and 6 (coalition personas), D-664 (red lines stored with their source) and
D-666 (the advisor takes in the document reader's layers), proven on the invented fixture of
tools/neg_advisor_checks.py, no model and no item.

490, structure: each item's structure (two_singles, teams, one_vs_coalition, three_or_more) is computed from its
    declared parties alone; a declared structure that differs is refused; a frozen key without it is read from
    its item, a key naming another refused; every bar figure and class floor is reported per structure and
    overall; a bar reading is refused for a set holding one structure only.
491, gap 4: every other party's movement toward or away from the persona over the rounds on record (toward,
    away, steady, not_stated) in the key and, from the stances it checked, in the step-wise chain; the report gives, per arm
    and structure, the share of parties moving toward (and away) that the arm approached.
492, gap 6: a coalition declares its members; a member's position stated on behalf of its coalition is the
    coalition's (its speaker kept and shown), a member's own position stays its own; a non-member speaking for
    it, members on a single party, a coalition of one or of itself, and a persona whose kind is not its party's
    are refused; the report gives every cell by persona kind.
493, D-664: a red line is a position id or {position, source}, its source one of the declared sources; the
    item's persona and the key's proposal carry the source; the checker's sheet leaves the sources out with the
    red lines.
494, D-666: the reader's layers (a .docx's insertions, deletions and comments with their anchors; a PDF's
    annotations; an HTML page's changes) become the build's layer entries; each is an item passage with a
    `LAY-<n>` id shown under its article (or outside the excerpt) with its kind, author and anchor, citable as a
    reason and as an inferred entry's line; the layers the reader could not read are named in the prompt; an
    item without layers renders as before.
Each proof neutralised, failed, restored and passed (scripts/effect_proof.py).
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from effect_proof import prove_effect  # noqa: E402
import neg_advisor as na  # noqa: E402
import neg_advisor_checks as base  # noqa: E402

sc = base.sc
B = base.BUILD


def build(**extra):
    return dict(copy.deepcopy(B), **copy.deepcopy(extra))


def two_parties(kinds, **extra):
    """The fixture with two parties of the given kinds (the persona first)."""
    parties = [{"id": "ALPHA", "kind": kinds[0]}, {"id": "BETA", "kind": kinds[1]}]
    return build(parties=parties, persona={"id": "ALPHA", "kind": kinds[0]}, **extra)


def refusal(b):
    try:
        sc.build_item(b)
    except ValueError as e:
        text = str(e)
        lead = "%s: " % b.get("item_id")
        return (text[len(lead):] if text.startswith(lead) else text)[:40]
    return None


def parsed(item, value=base.GOOD_REPLY):
    return na.parse_advice(json.dumps(value), item)


def many(b, n=None):
    """`n` copies of a build (MIN_ITEMS_PER_STRUCTURE by default, D-715 item 1), each with its own id."""
    return [dict(copy.deepcopy(b), item_id="%s-%d" % (b["item_id"], k))
            for k in range(sc.MIN_ITEMS_PER_STRUCTURE if n is None else n)]


def bar_set(builds):
    built = [sc.build_item(b) for b in builds]
    items = {i["item_id"]: i for i, _k in built}
    keys = {k["item_id"]: k for _i, k in built}
    rows = [{"item_id": i, "form": "advice", "group": g, "reply": parsed(items[i]), "audit": {}, "drops": {}}
            for i in items for g in ("b1", "system_advice")]
    return items, keys, {"B1": ({"rows": rows}, "b1"), "system": ({"rows": rows}, "system_advice")}


class _Proofs(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        type(self).evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))


class StructureChecks(_Proofs):
    evidence = []

    def test_01_structure_computed_from_the_parties(self):
        def observe():
            out = [sc.build_item(b)[1]["structure"] for b in (
                two_parties(("single", "single")), two_parties(("coalition", "coalition")),
                two_parties(("single", "coalition")), two_parties(("coalition", "single")), build())]
            out.append(refusal(build(structure="two_singles")))
            out.append(refusal(build(structure="three_or_more")))
            out.append(refusal(build(parties=[{"id": "ALPHA", "kind": "single"}])))
            return out
        want = ["two_singles", "teams", "one_vs_coalition", "one_vs_coalition", "three_or_more",
                "the declared structure is not the one it", None, "an item names at least two parties"]
        self.assertEqual(observe(), want)
        self.prove("structure_computed_from_declared_parties", observe, want,
                   lambda: patch.object(sc, "structure_of", lambda parties: sc.THREE_OR_MORE))

    def test_02_frozen_key_and_a_key_naming_another(self):
        item, key = sc.build_item(build())
        old = {f: v for f, v in key.items() if f != "structure"}

        def read(k):
            try:
                return sc.item_structure(item, k)
            except ValueError:
                return "refused"

        def observe():
            return [read(old), read(key), read(dict(key, structure="teams"))]
        want = ["three_or_more", "three_or_more", "refused"]
        self.assertEqual(observe(), want)
        self.prove("a_key_naming_another_structure_refused", observe, want,
                   lambda: patch.object(sc, "structure_of", lambda parties: "teams"))

    def test_03_bar_per_structure_and_refused_on_one(self):
        complete = build(record_kind="complete")
        missing = two_parties(("single", "single"), item_id="fx-k2-beta", record_kind="missing_notes",
                              masked_party="BETA")
        missing_same = build(item_id="fx-k2-beta", record_kind="missing_notes", masked_party="BETA")

        def observe():
            two = sc.report(*bar_set(many(complete) + many(missing)), resamples=50)
            one = sc.report(*bar_set(many(complete) + many(missing_same)), resamples=50)
            block = two["by_structure"]["system"]
            return (sorted(block), sorted(block["overall"]), [f["figure"] for f in (block.get("two_singles") or {}).get("floors", [])],
                    two["neg_bar"].get("refused"), sorted(two["neg_bar"].get("structures") or {}),
                    sorted(two["cells"]["system"]["structure"]), (one["neg_bar"].get("refused") or "")[:40])
        want = (["overall", "three_or_more", "two_singles"], ["drops", "figures", "floors", "items"],
                ["M1", "M1m", "M10", "M4f", "M4f", "M4f"], None, ["overall", "three_or_more", "two_singles"],
                ["three_or_more", "two_singles"], "the set holds one party structure only (")
        self.assertEqual(observe(), want)
        self.prove("bar_refused_on_one_structure", observe, want, lambda: patch.object(sc, "MIN_STRUCTURES", 1))
        self.prove("figures_per_structure", observe, want,
                   lambda: patch.object(sc, "item_structure", lambda item, key: sc.THREE_OR_MORE))


# D-668 gap 4: BETA moves toward the persona on A2 (support, then oppose with it), GAMMA away on A1 (with it,
# then against), GROUP1 steady on A2 and with one round on A1.
MOVES = build(parties=B["parties"] + [{"id": "GAMMA", "kind": "single"}], positions=B["positions"] + [
    {"id": "POS-7", "party": "BETA", "round": 1, "article": "A2", "proposal": None, "stance": "support",
     "quote": "Assessed contributions would help.", "source": "fixture 7"},
    {"id": "POS-8", "party": "GROUP1", "round": 2, "article": "A2", "proposal": None, "stance": "support",
     "quote": "Assessed contributions remain our view.", "source": "fixture 8"},
    {"id": "POS-9", "party": "GAMMA", "round": 1, "article": "A1", "proposal": 1, "stance": "support",
     "quote": "Fixed reporting times help us.", "source": "fixture 9"},
    {"id": "POS-10", "party": "GAMMA", "round": 2, "article": "A1", "proposal": 1, "stance": "oppose",
     "quote": "We can no longer accept fixed times.", "source": "fixture 10"}])


def stance_ask(b):
    """The step-wise chain's fake generate (tools/neg_advisor_d711_checks.fake_ask) answering each position's
    stance as the build declares it and every red line yes."""
    import neg_advisor_d711_checks as d711
    stance_of = {p["quote"]: p["stance"] for p in b["positions"]}
    inner = d711.fake_ask({"red_line": "yes"})

    def ask(step, user, answers):
        if step == "stance":
            return next(s for q, s in stance_of.items() if q in user)
        return inner(step, user, answers)
    return ask


MOVES_WANT = {"A1": {"BETA": "not_stated", "GAMMA": "away", "GROUP1": "not_stated"},
              "A2": {"BETA": "toward", "GAMMA": "not_stated", "GROUP1": "steady"},
              "A3": {"BETA": "not_stated", "GAMMA": "not_stated", "GROUP1": "not_stated"}}


class MovementChecks(_Proofs):
    evidence = []

    def test_01_movement_in_the_key_and_the_stepwise_chain(self):
        item, _key = sc.build_item(copy.deepcopy(MOVES))
        config = na.load_config()

        def observe():
            # The key from the declared stances; the system's step-wise chain from the stances it checked.
            reply, _steps = na.stepwise_advice(config, item, stance_ask(MOVES))
            return sc.build_item(copy.deepcopy(MOVES))[1]["movement"], reply["movement"]
        want = (MOVES_WANT, MOVES_WANT)
        self.assertEqual(observe(), want)
        self.prove("movement_from_the_rounds_on_record", observe, want,
                   lambda: patch.object(na, "party_movement", lambda *a: "steady"))
        self.prove("movement_relation_by_sign", observe, want, lambda: patch.object(na, "_sign_of", lambda stances: 1))

    def test_02_report_whom_each_arm_approached(self):
        builds = [dict(copy.deepcopy(MOVES), item_id="fx-move-%d" % n) for n in range(sc.MIN_CELL)]

        def observe():
            rep = sc.report(*bar_set(builds), resamples=20)["movement"]
            cell = rep["arms"]["system"]["three_or_more"]
            return (rep["status"], cell["items"], cell["toward_approached"], cell["away_approached"],
                    cell["counts"]["toward"], sorted(rep["arms"]["system"]))
        # The reply approaches BETA (moving toward) and not GAMMA (moving away).
        want = (sc.MOVEMENT_STATUS, 5, 1.0, 0.0, 5, ["overall", "three_or_more"])
        self.assertEqual(observe(), want)
        self.prove("approach_read_against_movement", observe, want,
                   lambda: patch.object(sc, "party_moves", lambda key: {"BETA": "away", "GAMMA": "toward"}))


# D-668 gap 6: the persona GROUP1 is a coalition of BETA and GAMMA; BETA states POS-7 on its behalf.
COALITION = build(persona={"id": "GROUP1", "kind": "coalition"}, red_lines=[],
                  parties=[{"id": "ALPHA", "kind": "single"}, {"id": "BETA", "kind": "single"},
                           {"id": "GAMMA", "kind": "single"},
                           {"id": "GROUP1", "kind": "coalition", "members": ["BETA", "GAMMA"]}],
                  positions=B["positions"] + [
                      {"id": "POS-7", "party": "BETA", "on_behalf_of": "GROUP1", "round": 2, "article": "A1",
                       "proposal": 2, "stance": "oppose", "quote": "On behalf of the group we oppose this option.",
                       "source": "fixture 7"}])


class CoalitionChecks(_Proofs):
    evidence = []

    def test_01_on_behalf_positions_are_the_coalitions(self):
        def observe():
            item, key = sc.build_item(copy.deepcopy(COALITION))
            pos = {p["id"]: (p["party"], p.get("speaker")) for p in item["positions"]}
            text = na.render_advice(na.load_config(), item)
            return (pos["POS-7"], pos["POS-3"], key["proposals"]["P-A1-2"]["conflict"],
                    "GROUP1 (coalition of BETA, GAMMA)" in text, "POS-7, GROUP1, said by BETA, round 2" in text,
                    item["parties"][3].get("members"), key["structure"])
        want = (("GROUP1", "BETA"), ("BETA", None), "conflict", True, True, ["BETA", "GAMMA"], "three_or_more")
        self.assertEqual(observe(), want)
        self.prove("member_speaks_for_its_coalition", observe, want,
                   lambda: patch.object(sc, "credited", lambda positions, parties: positions))
        self.prove("coalition_members_shown", observe, want,
                   lambda: patch.object(na, "party_text", lambda p: "%s (%s)" % (p["id"], p["kind"])))

    def test_02_refusals(self):
        parties = COALITION["parties"]

        def observe():
            group = lambda **f: [p if p["id"] != "GROUP1" else dict(p, **f) for p in parties]
            positions = [dict(p, party="ALPHA") if p["id"] == "POS-7" else p for p in COALITION["positions"]]
            return [refusal(copy.deepcopy(COALITION)),
                    refusal(dict(copy.deepcopy(COALITION), positions=positions)),
                    refusal(dict(copy.deepcopy(COALITION), parties=[dict(p, members=["X", "Y"]) if p["id"] == "ALPHA"
                                                                    else p for p in parties])),
                    refusal(dict(copy.deepcopy(COALITION), parties=group(members=["BETA"]))),
                    refusal(dict(copy.deepcopy(COALITION), parties=group(members=["BETA", "GROUP1"]))),
                    refusal(dict(copy.deepcopy(COALITION), persona={"id": "GROUP1", "kind": "single"})),
                    refusal(dict(copy.deepcopy(COALITION), persona={"id": "NOBODY", "kind": "coalition"}))]
        want = [None, "a position on behalf of a coalition is s", "only a coalition declares members, at le",
                "only a coalition declares members, at le", "a coalition's members are other parties,",
                "the persona's kind is its party's kind", "the persona is one of the item's parties"]
        self.assertEqual(observe(), want)
        self.prove("coalition_declarations_refused", observe, want,
                   lambda: patch.object(sc, "check_parties", lambda b: None))

    def test_03_cells_by_persona_kind(self):
        single = build(record_kind="complete")
        group = dict(copy.deepcopy(COALITION), item_id="fx-k2-group", record_kind="missing_notes", masked_party="ALPHA")

        def observe():
            return sorted(sc.report(*bar_set([single, group]), resamples=20)["cells"]["system"]["persona_kind"])
        want = ["coalition", "single"]
        self.assertEqual(observe(), want)
        real = sc.cell_dimensions
        # Neutralised: the persona-kind dimension reads every persona as single.
        off = lambda items, keys, structures: tuple((d, (lambda i: "single") if d == "persona_kind" else v)
                                                    for d, v in real(items, keys, structures))
        self.prove("cells_by_persona_kind", observe, want, lambda: patch.object(sc, "cell_dimensions", off))


class RedLineChecks(_Proofs):
    evidence = []

    def test_01_red_lines_carry_their_source(self):
        def observe():
            out = []
            for lines in (["POS-2"], [{"position": "POS-2", "source": "from the document"}], [{"position": "POS-2"}]):
                item, key = sc.build_item(build(red_lines=lines))
                out.append((item["persona"]["red_lines"], item["persona"]["red_line_sources"],
                            key["proposals"]["P-A2-1"]["red_line_source"], na.red_line_source(item["persona"], "POS-2"),
                            na.red_line_source(item["persona"], "POS-1")))
            out += [refusal(build(red_lines=[{"position": "POS-2", "source": "the operator"}])),
                    refusal(build(red_lines=[{"source": "from the document"}])),
                    refusal(build(red_lines=["POS-2", "POS-2"])),
                    na.red_line_source({"red_lines": ["POS-2"]}, "POS-2")]
            return out
        row = (["POS-2"], {"POS-2": "from the document"}, "from the document", "from the document", None)
        want = [row, row, row, "a red line's source is one of: from the ", "a red line is a position id or {position",
                "a red line is declared twice: POS-2", "from the document"]
        self.assertEqual(observe(), want)
        self.prove("red_line_source_declared_and_checked", observe, want,
                   lambda: patch.object(na, "RED_LINE_SOURCES", ("from the document", "the operator")))

    def test_02_checker_sheet_leaves_sources_out(self):
        def observe():
            with tempfile.TemporaryDirectory() as tmp:
                for n in range(sc.SAMPLE_MIN):
                    item, key = sc.build_item(build(item_id="fx-sheet-%d" % n))
                    sc._write_json(Path(tmp) / "items" / item["item_id"] / "item.json", item)
                    sc._write_json(Path(tmp) / "items" / item["item_id"] / "key.json", key)
                sheet = sc.sample_sheet(tmp)
            return sorted({f for e in sheet["items"] for f in e["item"]["persona"]})
        want = ["id", "kind"]
        self.assertEqual(observe(), want)
        self.prove("checker_sheet_without_sources", observe, want,
                   lambda: patch.object(sc, "CHECKER_HIDDEN", ("red_lines",)))


def _docx(path):
    """A minimal .docx: one tracked insertion, one deletion and one anchored comment, each with its author."""
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    document = ('<w:document %s><w:body><w:p><w:r><w:t>Each party shall report.</w:t></w:r>'
                '<w:ins w:id="1" w:author="Delegate A" w:date="2026-01-01T00:00:00Z"><w:r><w:t>within seventy two hours'
                '</w:t></w:r></w:ins><w:del w:id="2" w:author="Delegate B"><w:r><w:delText>when it judges appropriate'
                '</w:delText></w:r></w:del><w:commentRangeStart w:id="0"/><w:r><w:t>mandatory contributions</w:t></w:r>'
                '<w:commentRangeEnd w:id="0"/></w:p></w:body></w:document>') % w
    comments = ('<w:comments %s><w:comment w:id="0" w:author="Delegate A"><w:p><w:r><w:t>This is our red line and we '
                'cannot accept it</w:t></w:r></w:p></w:comment></w:comments>') % w
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", document)
        z.writestr("word/comments.xml", comments)


class _Page(dict):
    def __init__(self, text, annots):
        super().__init__({"/Annots": annots})
        self.text = text

    def extract_text(self):
        return self.text


class LayerChecks(_Proofs):
    evidence = []

    def test_01_reader_layers_become_entries(self):
        import docx_layers
        import html_layers
        import pdf_layers
        marks = json.loads((ROOT / "config" / "document_reader.json").read_text(encoding="utf-8"))["html_track_changes"]
        reader = type("R", (), {"pages": [_Page("Article text.", [
            {"/Subtype": "/Text", "/T": "Delegate C", "/Contents": "We reserve our position here"},
            {"/Subtype": "/Link"}])]})()

        def observe():
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "round.docx"
                _docx(path)
                with patch("sys.stderr"):
                    docx = na.layers_from_reader(docx_layers.read_layers(path))
            pdf = na.layers_from_reader(pdf_layers.read_reader(reader))
            html = na.layers_from_reader(html_layers.read_text(
                '<p>Text <ins data-author="Delegate D">added words</ins> <del data-author="Delegate E">old words</del>'
                ' <ins></ins></p>', marks))
            return ([(e["layer"], e["text"], e["author"], e["anchor"]) for e in docx["layers"]],
                    [(e["layer"], e["text"], e["author"]) for e in pdf["layers"]], pdf["not_read"][:1],
                    [(e["layer"], e["text"], e["author"]) for e in html["layers"]], html["empty"])
        want = ([("insertion", "within seventy two hours", "Delegate A", ""),
                 ("deletion", "when it judges appropriate", "Delegate B", ""),
                 ("comment", "This is our red line and we cannot accept it", "Delegate A", "mandatory contributions")],
                [("annotation", "We reserve our position here", "Delegate C")], ["structure"],
                [("insertion", "added words", "Delegate D"), ("deletion", "old words", "Delegate E")], 1)
        self.assertEqual(observe(), want)
        self.prove("reader_layers_taken_in", observe, want,
                   lambda: patch.object(na, "_READER_LAYERS", (("insertions", "insertion"),)))

    def test_02_layers_in_the_item_and_the_prompt(self):
        layers = [{"layer": "comment", "text": "This is our red line and we cannot accept it", "author": "Delegate A",
                   "anchor": "mandatory contributions", "article": "A2"},
                  {"layer": "footnote", "text": "The annex follows in the next round.", "author": "", "article": None}]
        with_layers = build(layers=layers, layers_not_read=["text boxes"])
        config = na.load_config()

        def observe():
            item, key = sc.build_item(copy.deepcopy(with_layers))
            plain, _k = sc.build_item(build())
            empty, _k = sc.build_item(build(layers=[]))
            text = na.render_advice(config, item)
            reply = parsed(item, dict(base.GOOD_REPLY, proposals=[dict(base.GOOD_REPLY["proposals"][2],
                                                                       reasons=["POS-2", "LAY-1"])]))
            cite = sc.checks(item, key, reply, mode="key")["P-A2-1"]["C-cite"]
            a2 = text.split("ARTICLE A2")[1].split("ARTICLE A3")[0]
            return ([e["id"] for e in item["layers"]], 'LAY-1, comment by Delegate A on "mandatory contributions"' in a2,
                    "NOTES AND CHANGES IN THE DOCUMENT OUTSIDE THESE ARTICLES:\n- LAY-2, footnote: The annex" in text,
                    "COULD NOT READ: text boxes" in text, "LAY-1" in na.item_ids(item)[0], cite,
                    sc.basis_refusal(item, "This is our red line and we cannot accept it"),
                    na.render_advice(config, plain) == na.render_advice(config, empty), "NOTES AND" in
                    na.render_advice(config, plain), bool(na.CITATION_ID.search("see LAY-1")))
        want = (["LAY-1", "LAY-2"], True, True, True, True, True, None, True, False, True)
        self.assertEqual(observe(), want)
        self.prove("layers_shown_in_the_prompt", observe, want, lambda: patch.object(na, "_layer_block", lambda h, e: ""))
        self.prove("layers_citable", observe, want,
                   lambda: patch.object(sc, "item_texts", lambda item: []))
        self.prove("layer_entries_checked", lambda: refusal(build(layers=[{"layer": "margin", "text": "x"}])),
                   "a layer entry's kind is one of insertion", lambda: patch.object(sc, "check_layers", lambda b: None))


def _run(cls, what):
    cls.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(cls).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", "%d proofs, each neutralise, fail, restore, pass, no model and no item: %s" % (len(cls.evidence), what)


def check_structure():
    return _run(StructureChecks, "each item's party structure computed from its declared parties, a differing "
                                 "declaration or key refused, every bar figure and floor per structure and overall, a "
                                 "bar reading refused on one structure")


def check_movement():
    return _run(MovementChecks, "every other party's movement toward or away from the persona over the rounds on "
                                "record in the key and the step-wise chain, and whom each arm approached")


def check_coalitions():
    return _run(CoalitionChecks, "a coalition's declared members, a member's position on its behalf credited to it "
                                 "with its speaker shown, the declarations refused when wrong, cells by persona kind")


def check_red_line_sources():
    return _run(RedLineChecks, "every red line with its declared source in the item and the key, other sources "
                               "refused, the checker's sheet without them")


def check_layers():
    return _run(LayerChecks, "the reader's .docx, PDF and HTML layers taken in as entries, each a citable LAY "
                             "passage under its article, the layers not read named, an item without layers unchanged")


def main():
    code = 0
    for name, fn in (("490", check_structure), ("491", check_movement), ("492", check_coalitions),
                     ("493", check_red_line_sources), ("494", check_layers)):
        status, detail = fn()
        print(name, status, detail)
        code |= status != "PASS"
    return code


if __name__ == "__main__":
    raise SystemExit(main())
