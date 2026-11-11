"""Gate check: the negotiation multi-round development case (loop S5 item 0.9, DS5-10).

benchmark/dev_cases/negotiation_three_rounds/ is a live case manifest (three rounds, two
actors, fourteen issues, every source an exact span) written from the anonymised
negotiation files tracked under benchmark/corpora/ (H6: no other copy is read). It is an
exposed development case: the material and its earlier keys are in the repository.

Every case EXECUTES the project's own code on the committed folder, no model, no
pipeline run, no provider:

1. the sealer's own reader (prepare_ordinary_final_run.workload_members) reads the folder
   as it reads a test archive, the controller's case_corpus_documents loads the case
   documents with the bound pipeline's own _load_corpus, and the controller's
   validate_live_case_manifest accepts the manifest against them (all seven rules of
   docs/INPUT_FORMAT.md section 12); the run's own multi_round.bind_sources binds every
   span into a temporary reference index; a copy with one span shifted by a character is
   refused by both;
2. the folder is exactly what benchmark/dev_cases/build_negotiation_case.py builds, and
   each case document and the conventions are byte copies (LF) of the anonymised corpus
   files, so nothing else entered the case;
3. a .docx with tracked changes is read as it would stand with every change accepted
   (insertions in, in a paragraph, a table cell and a moved run; deletions, a deleted
   paragraph mark and a deleted table row out), and one with no tracked change keeps every
   text python-docx reads from it (scripts/text_extract.py); and a .docx keeps its structure
   for the pipeline's splitter and field reader: headings by outline level, never a style's
   name, paragraphs apart, a table as rows where it stands, and top-level sections as units;
4. the two worked cases of D-S39 (host_agreement_three_rounds, draft_resolution_revision): the
   sealer's reader takes each workload and refuses the case folder that holds it, so EXPECTED.md
   cannot travel; the controller and the run's binder accept each manifest and refuse a shifted
   span; each folder equals its build; case 1's input is its texts as .docx and its notes as
   Markdown, and each .docx reads, accepted, as its round and, rejected, as the state before;
   every published word of the real documents is kept.

Each is proven by neutralise, fail, restore, pass (scripts/effect_proof.py). SKIP when
benchmark/dev_cases/ is absent (the container image does not ship benchmark/).
"""
import contextlib
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmark" / "dev_cases"
CASE = CASES / "negotiation_three_rounds"
BUILDER = CASES / "build_negotiation_case.py"
CORPORA = ROOT / "benchmark" / "corpora"

for _path in (str(ROOT / "scripts"), str(ROOT / "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from effect_proof import prove_effect  # noqa: E402


_BUILDER = {}


def _builder():
    """The builder module, loaded once, so a neutralisation patches the one observed."""
    if "module" not in _BUILDER:
        spec = importlib.util.spec_from_file_location("shimmer_dev_case_builder", BUILDER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _BUILDER["module"] = module
    return _BUILDER["module"]


def _controller():
    import ordinary_final_run
    import prepare_ordinary_final_run
    return ordinary_final_run, prepare_ordinary_final_run


def _verdict(function):
    try:
        function()
    except Exception as exc:  # a refusal names its rule; that is the observation
        return "refused: %s" % str(exc).splitlines()[0][:120]
    return "accepted"


def observe_validation():
    ofr, sealer = _controller()
    import multi_round as mr
    from reference_builder import ReferenceIndex
    members = sealer.workload_members(CASE)
    case = json.loads(members[ofr.CASE_MANIFEST].decode("utf-8"))
    context = {n[len("context/"):]: d for n, d in members.items() if n.startswith("context/")}
    pipeline_source = (ROOT / "scripts" / "pipeline.py").read_bytes()
    documents = ofr.case_corpus_documents(context, pipeline_source)
    shifted = copy.deepcopy(case)
    shifted["sources"][0]["char_start"] += 1
    shifted["sources"][0]["char_end"] += 1

    def bind(manifest):
        with tempfile.TemporaryDirectory(prefix="shimmer_dev_case_") as td:
            refs = ReferenceIndex.open(Path(td), index_path=Path(td) / "reference_index.json")
            rows = [dict(id=k, name=k, text=v) for k, v in documents.items()]
            return mr.bind_sources(mr.validate_manifest(manifest), rows, refs)
    return {"controller": _verdict(lambda: ofr.validate_live_case_manifest(case, documents)),
            "controller_shifted": _verdict(lambda: ofr.validate_live_case_manifest(shifted, documents)),
            "bound": _verdict(lambda: bind(case)),
            "bound_shifted": _verdict(lambda: bind(shifted)),
            "rounds": [r["round_id"] for r in sorted(case["rounds"], key=lambda r: r["sequence"])],
            "actors": sorted(a["actor_id"] for a in case["actors"]),
            "issues": len(case["issues"]), "sources": len(case["sources"]),
            "documents": sorted(documents), "fixture": case.get("fixture")}


VALIDATION = {"controller": "accepted",
              "controller_shifted": "refused: Case source span does not match the bundled document text",
              "bound": "accepted", "bound_shifted": "refused: source_span_mismatch",
              "rounds": ["r2", "r3", "r4"], "actors": ["company", "union"], "issues": 14, "sources": 34,
              "documents": ["company_a_union_b_offer_2024_09_23", "company_a_union_b_offer_2024_10_19",
                            "company_a_union_b_offer_2024_10_31"], "fixture": False}


def observe_provenance():
    b = _builder()
    disk = b.on_disk(CASE)
    copies = {}
    for _rid, _seq, folder, name in b.ROUNDS:
        copies["context/" + name] = (CORPORA / folder / "context" / name)
    copies["conventions/" + b.CONVENTIONS[1]] = CORPORA / b.CONVENTIONS[0] / "conventions" / b.CONVENTIONS[1]
    return {"builds_to_disk": b.build() == disk,
            "copies": {k: disk.get(k) == p.read_bytes().replace(b"\r\n", b"\n") for k, p in sorted(copies.items())},
            "members": sorted(disk)}


PROVENANCE = {"builds_to_disk": True,
              "copies": {"context/company_a_union_b_offer_2024_09_23.md": True,
                         "context/company_a_union_b_offer_2024_10_19.md": True,
                         "context/company_a_union_b_offer_2024_10_31.md": True,
                         "conventions/mandate_conventions.md": True},
              "members": ["_review_targets.json", "case_manifest.json",
                          "context/company_a_union_b_offer_2024_09_23.md",
                          "context/company_a_union_b_offer_2024_10_19.md",
                          "context/company_a_union_b_offer_2024_10_31.md",
                          "conventions/mandate_conventions.md"]}


def _tracked(kind, inner, ident):
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    return parse_xml('<w:%s %s w:id="%d" w:author="Fixture" w:date="2026-01-01T00:00:00Z">%s</w:%s>'
                     % (kind, nsdecls("w"), ident, inner, kind))


def _run(text, tag="t"):
    return '<w:r><w:%s xml:space="preserve">%s</w:%s></w:r>' % (tag, text, tag)


def observe_tracked_docx():
    """A small tracked file and an untracked one, built here and read by the shared extractor."""
    import docx
    import text_extract
    tracked = docx.Document()
    first = tracked.add_paragraph("kept ")
    first._p.append(_tracked("ins", _run("inserted "), 1))
    first._p.append(_tracked("del", _run("deleted ", "delText"), 2))
    first._p.append(_tracked("ins", _tracked_nested_deletion(), 3))
    first._p.append(_tracked("moveTo", _run("moved "), 4))
    first._p.append(_tracked("moveFrom", _run("left "), 5))
    first.add_run("end")
    joined = tracked.add_paragraph("joined ")
    mark = joined._p.get_or_add_pPr()
    mark.append(_mark_deleted())
    tracked.add_paragraph("to the next")
    gone = tracked.add_paragraph()
    gone._p.get_or_add_pPr().append(_mark_deleted())
    gone._p.append(_tracked("del", _run("removed paragraph", "delText"), 6))
    tracked.add_paragraph("last")
    table = tracked.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "cell "
    table.cell(0, 0).paragraphs[0]._p.append(_tracked("ins", _run("inserted"), 7))
    table.cell(0, 1).text = "second"
    table.cell(1, 0).text = "deleted row"
    table.rows[1]._tr.get_or_add_trPr().append(_tracked("del", "", 8))
    plain = docx.Document()
    plain.add_paragraph("first")
    plain.add_paragraph("")
    plain.add_paragraph("second\tafter a tab")
    grid = plain.add_table(rows=1, cols=2)
    grid.cell(0, 0).text, grid.cell(0, 1).text = "a", "b"
    with tempfile.TemporaryDirectory(prefix="shimmer_tracked_docx_") as td:
        tracked_path, plain_path = Path(td) / "tracked.docx", Path(td) / "plain.docx"
        tracked.save(str(tracked_path))
        plain.save(str(plain_path))
        reopened = docx.Document(str(plain_path))
        by_library = ([p.text for p in reopened.paragraphs if p.text.strip()]
                      + [c.text for t in reopened.tables for r in t.rows for c in r.cells])
        read = text_extract.extract_text(plain_path)
        return {"tracked": text_extract.extract_text(tracked_path),
                "plain_keeps_the_library_text": all(text in read for text in by_library)}


def _tracked_nested_deletion():
    """An insertion later deleted: w:ins holding w:del. Accepted, it is gone."""
    return ('<w:del w:id="9" w:author="Fixture" w:date="2026-01-01T00:00:00Z">%s</w:del>'
            % _run("inserted then deleted ", "delText"))


def _mark_deleted():
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    return parse_xml('<w:rPr %s><w:del w:id="10" w:author="Fixture" w:date="2026-01-01T00:00:00Z"/></w:rPr>'
                     % nsdecls("w"))


TRACKED_DOCX = {"tracked": "kept inserted moved end\n\njoined to the next\n\nlast\n\n"
                           "| cell inserted | second |\n|---|---|",
                "plain_keeps_the_library_text": True}


def observe_docx_structure():
    """A .docx read through the extractor and into the pipeline's own splitter and field reader:
    headings by outline level (on the paragraph, through a style's chain, under a style whose name
    is no heading word), a table where it stands, and a document of top-level sections."""
    import docx
    from docx.enum.style import WD_STYLE_TYPE
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    import paired_review
    import pairing_map
    import text_extract

    def outline(element, value):
        element.append(parse_xml('<w:outlineLvl %s w:val="%d"/>' % (nsdecls("w"), value)))

    shaped = docx.Document()
    shaped.add_heading("Whole title", 1)
    shaped.add_paragraph("Opening words.")
    shaped.add_heading("First part", 2)
    shaped.add_paragraph("Quantity label: 3 box")
    table = shaped.add_table(rows=3, cols=2)
    for r, row in enumerate((("Item", "Cost (credits)"), ("One", "5"), ("Two", "7"))):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    shaped.add_paragraph("Total cost: 12 credits")
    named = shaped.styles.add_style("Baslik ozel", WD_STYLE_TYPE.PARAGRAPH)
    outline(named.element.get_or_add_pPr(), 1)
    shaped.add_paragraph("Second part", style=named)
    inherited = shaped.styles.add_style("Devam", WD_STYLE_TYPE.PARAGRAPH)
    inherited.base_style = named
    shaped.add_paragraph("Third part", style=inherited)
    direct = shaped.add_paragraph("Fourth part")
    outline(direct._p.get_or_add_pPr(), 2)
    shaped.add_paragraph("")
    sections = docx.Document()
    for name in ("Alpha", "Beta", "Gamma"):
        sections.add_heading(name, 1)
        sections.add_paragraph("Words of the part.")
    with tempfile.TemporaryDirectory(prefix="shimmer_docx_shape_") as td:
        shaped_path, sections_path = Path(td) / "shaped.docx", Path(td) / "sections.docx"
        shaped.save(str(shaped_path))
        sections.save(str(sections_path))
        text = text_extract.extract_text(shaped_path)
        section_text = text_extract.extract_text(sections_path)
    import reference_builder
    units = pairing_map.split_units(text)
    columns = paired_review.extract_fields(text)[1]
    return {"units": [u["unit_id"] for u in units],
            "passages": len([p for p in reference_builder._PARA_RE.split(text) if p.strip()]),
            "section_units": [u["unit_id"] for u in pairing_map.split_units(section_text)],
            "columns": sorted(" ".join(k) for k in columns),
            "table_before_total": 0 <= text.find("| Item |") < text.find("Total cost"),
            "ends_clean": text == text.strip()}


DOCX_STRUCTURE = {"units": ["u00-whole-title", "u01-first-part", "u02-second-part", "u03-third-part",
                            "u04-fourth-part"],
                  "passages": 9,
                  "section_units": ["u01-alpha", "u02-beta", "u03-gamma"],
                  "columns": ["cost"], "table_before_total": True, "ends_clean": True}


WORKED_CASES = {"host_agreement_three_rounds": "build_host_agreement_case.py",
                "draft_resolution_revision": "build_resolution_case.py"}
_WORKED = {}


def _worked_builder(case):
    if case not in _WORKED:
        spec = importlib.util.spec_from_file_location("shimmer_worked_" + case, CASES / WORKED_CASES[case])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _WORKED[case] = module
    return _WORKED[case]


def observe_worked_case(case):
    """One worked case through the sealer's reader, the controller and the run's binder."""
    ofr, sealer = _controller()
    import multi_round as mr
    from reference_builder import ReferenceIndex
    folder = CASES / case
    members = sealer.workload_members(folder / "workload")
    manifest = json.loads(members[ofr.CASE_MANIFEST].decode("utf-8"))
    context = {n[len("context/"):]: d for n, d in members.items() if n.startswith("context/")}
    documents = ofr.case_corpus_documents(context, (ROOT / "scripts" / "pipeline.py").read_bytes())
    shifted = copy.deepcopy(manifest)
    shifted["sources"][0]["char_start"] += 1
    shifted["sources"][0]["char_end"] += 1

    def bind(value):
        with tempfile.TemporaryDirectory(prefix="shimmer_worked_case_") as td:
            refs = ReferenceIndex.open(Path(td), index_path=Path(td) / "reference_index.json")
            rows = [dict(id=k, name=k, text=v) for k, v in documents.items()]
            return mr.bind_sources(mr.validate_manifest(value), rows, refs)
    return {"case_folder_refused": _verdict(lambda: sealer.workload_members(folder)).startswith("refused"),
            "expected_travels": any("EXPECTED" in n for n in members),
            "controller": _verdict(lambda: ofr.validate_live_case_manifest(manifest, documents)),
            "controller_shifted": _verdict(lambda: ofr.validate_live_case_manifest(shifted, documents)),
            "bound": _verdict(lambda: bind(manifest)), "bound_shifted": _verdict(lambda: bind(shifted)),
            "documents": len(documents), "sources": len(manifest["sources"]), "fixture": manifest.get("fixture"),
            "input_kinds": sorted(Path(n).suffix for n in context),
            "ordinary_is_the_workload_without_its_manifest": _verdict(
                lambda: sealer.workload_members(folder / "ordinary")) == "accepted" and
            sealer.workload_members(folder / "ordinary") == {k: v for k, v in members.items() if k != ofr.CASE_MANIFEST}}


def _worked_expected(documents, sources, kinds):
    return {"case_folder_refused": True, "expected_travels": False, "controller": "accepted",
            "controller_shifted": "refused: Case source span does not match the bundled document text",
            "bound": "accepted", "bound_shifted": "refused: source_span_mismatch",
            "documents": documents, "sources": sources, "fixture": False, "input_kinds": kinds,
            "ordinary_is_the_workload_without_its_manifest": True}


WORKED = {"host_agreement_three_rounds": _worked_expected(9, 41, [".docx"] * 3 + [".md"] * 6),
          "draft_resolution_revision": _worked_expected(2, 10, [".md"] * 2)}


def observe_worked_cases():
    return {case: observe_worked_case(case) for case in sorted(WORKED_CASES)}


def observe_worked_builds():
    host, resolution = (_worked_builder(c) for c in ("host_agreement_three_rounds", "draft_resolution_revision"))
    differ, proofs = host.compare(host.build(), host.on_disk())
    return {"host_differs": differ, "rounds": {str(k): v for k, v in sorted(proofs.items())},
            "resolution_is_the_build": resolution.on_disk() == resolution.build(),
            "published_words_kept": {k: resolution.published_words_kept(k) for k in sorted(resolution.VERSIONS)}}


_ROUND_PROOF = {"accepted_is_this_round": True, "rejected_is_the_state_before": True}
WORKED_BUILDS = {"host_differs": [], "rounds": {"1": _ROUND_PROOF, "2": _ROUND_PROOF, "3": _ROUND_PROOF},
                 "resolution_is_the_build": True,
                 "published_words_kept": {"l34": True, "rev1": True}}


# ---- neutralisations ---------------------------------------------------------------------

def sealer_takes_any_member():
    """The sealer's own refusal is off: a folder holding EXPECTED.md would travel whole."""
    _, sealer = _controller()
    return patch.object(sealer, "require", lambda condition, message: None)


def tracked_docx_is_the_wrong_round():
    """Each round's .docx is compared with the round after it: what a builder that shifted its
    versions by one would pass off as the right file."""
    host = _worked_builder("host_agreement_three_rounds")
    real = host.reads_as_round
    return patch.object(host, "reads_as_round", lambda reading, rnd: real(reading, min(rnd + 1, 3)))


def outline_levels_not_read():
    """No paragraph is a heading: a whole .docx is one unit again."""
    import text_extract
    return patch.object(text_extract, "_outline_level", lambda paragraph: None)


def tables_read_flat():
    """A table's rows are tab-separated lines again: its column gives no figures."""
    import text_extract

    def flat(table):
        return "\n".join("\t".join(c.text for c in r.cells) for r in table.rows)
    return patch.object(text_extract, "_table_block", flat)


def paragraphs_not_apart():
    """Paragraphs follow on single lines: a table has no paragraph of its own."""
    import text_extract
    return patch.object(text_extract, "_PARAGRAPH_GAP", "\n")


def top_level_never_moves():
    """A level used for every section stays level 1, which the splitter reads as a title."""
    import text_extract
    real = text_extract._heading_marks
    return patch.object(text_extract, "_heading_marks", lambda level, shift: real(level, 0))


def tracked_changes_not_read():
    """The paragraph text python-docx gives alone: what the extractor did before."""
    import text_extract
    return patch.object(text_extract, "_ACCEPTED_CONTENT", "w:r | w:hyperlink")


def spans_not_measured():
    """The controller validates the manifest's shape only, never measuring a span (the
    validator called without the documents), and the run's binding skips the comparison."""
    ofr, _ = _controller()
    import multi_round as mr
    real_validate, real_bind = ofr.validate_live_case_manifest, mr.bind_sources

    def unmeasured_bind(manifest, documents, refs):
        texts = {d["id"]: d["text"] for d in documents}
        fixed = copy.deepcopy(manifest)
        for s in fixed["sources"]:
            s["quote"] = texts[s["document_id"]][s["char_start"]:s["char_end"]]
        return real_bind(fixed, documents, refs)
    stack = contextlib.ExitStack()
    stack.enter_context(patch.object(ofr, "validate_live_case_manifest",
                                     lambda value, documents=None: real_validate(value)))
    stack.enter_context(patch.object(mr, "bind_sources", unmeasured_bind))
    return stack


def builder_off_by_one():
    """The builder measures every span one character late: its build no longer equals
    the committed folder."""
    b = _builder()
    real = b.sources

    def late(docs):
        out = real(docs)
        for s in out:
            s["char_start"] += 1
            s["char_end"] += 1
        return out
    return patch.object(b, "sources", late)


class DevCaseChecks(unittest.TestCase):
    evidence = []

    @classmethod
    def setUpClass(cls):
        if not (CASE / "case_manifest.json").is_file() or not BUILDER.is_file():
            raise unittest.SkipTest("benchmark/dev_cases/ is not in this tree")

    def prove(self, name, observe, expected, neutralise):
        result = prove_effect(name=name, validate=lambda: (CASE / "case_manifest.json").is_file(),
                              observe=observe,
                              check=lambda: ("PASS" if observe() == expected else "FAIL", name),
                              neutralise=neutralise)
        DevCaseChecks.evidence.append(result)

    def test_the_controller_accepts_the_case_and_measures_every_span(self):
        """Neutralised: spans are not measured; the shifted copy is accepted."""
        self.prove("case_accepted_spans_measured", observe_validation, VALIDATION, spans_not_measured)

    def test_the_folder_is_the_build_from_the_anonymised_corpus(self):
        """Neutralised: the builder measures one character late; its build differs."""
        self.prove("case_is_the_build", observe_provenance, PROVENANCE, builder_off_by_one)

    def test_a_tracked_docx_reads_as_with_every_change_accepted(self):
        """Neutralised: insertions and moved text are dropped, as they silently were."""
        self.prove("tracked_docx_read_accepted", observe_tracked_docx, TRACKED_DOCX, tracked_changes_not_read)

    def test_a_docx_keeps_its_headings_paragraphs_and_tables(self):
        """Neutralised four ways: no outline level, flat tables, no paragraph gap, no moved level."""
        for name, neutralise in (("docx_outline_levels", outline_levels_not_read),
                                 ("docx_tables_as_rows", tables_read_flat),
                                 ("docx_paragraphs_apart", paragraphs_not_apart),
                                 ("docx_top_level_sections", top_level_never_moves)):
            self.prove(name, observe_docx_structure, DOCX_STRUCTURE, neutralise)

    def test_the_worked_cases_are_accepted_and_their_expectations_do_not_travel(self):
        """Neutralised: the sealer takes any member; the case folder is no longer refused."""
        self.prove("worked_cases_accepted", observe_worked_cases, WORKED, sealer_takes_any_member)

    def test_the_worked_cases_are_their_builds_and_each_docx_is_its_round(self):
        """Neutralised: the versions shift by one; no .docx reads as its round."""
        self.prove("worked_cases_are_the_build", observe_worked_builds, WORKED_BUILDS,
                   tracked_docx_is_the_wrong_round)


def check():
    DevCaseChecks.evidence = []
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DevCaseChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:160]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    if result.skipped:
        return "SKIP", "development case checks skipped: %s" % result.skipped[0][1]
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: the negotiation development case "
                    "(three rounds, two actors, fourteen issues, 34 exact spans) is read by the sealer's own "
                    "reader, its documents loaded by the bound pipeline's _load_corpus, accepted by the "
                    "controller's validate_live_case_manifest and bound by multi_round.bind_sources, and a "
                    "span shifted by one character is refused by both; the folder is exactly the builder's "
                    "output and its documents and conventions are byte copies of the anonymised corpus "
                    "files; a .docx with tracked changes reads as with every change accepted; the two "
                    "worked cases are accepted, equal their builds, and their expectations do not travel"
                    % result.testsRun)


def main():
    status, detail = check()
    for proof in DevCaseChecks.evidence:
        print(proof["name"], proof["status"])
        print("  before:  ", json.dumps(proof["before"], sort_keys=True)[:400])
        print("  mutated: ", json.dumps(proof["mutated"], sort_keys=True)[:400])
        print("  restored:", json.dumps(proof["restored"], sort_keys=True)[:400])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
