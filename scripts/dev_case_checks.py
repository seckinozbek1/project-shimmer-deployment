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
   files, so nothing else entered the case.

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


# ---- neutralisations ---------------------------------------------------------------------

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
                    "files" % result.testsRun)


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
