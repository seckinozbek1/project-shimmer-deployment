"""Gate check: what changed between versions, and references that lead nowhere (D-S39).

Every proof EXECUTES scripts/version_changes.py with no model: on invented fixtures, through the
real case phase with stand-in backends, and, where benchmark/dev_cases/ is in the tree, on the
worked case. Each is neutralise, fail, restore, pass (scripts/effect_proof.py).

1. A changed sentence is one record citing both versions, an added or removed one cites its own,
   a sentence standing in both is no change wherever it stands, and a tie is refused.
2. A changed table cell, a removed row and an added row are recorded by row and column, and a
   changed text value by its label: none of them has a change record in the two-version review.
3. A labelled figure comes from the two-version review's own functions, and a term whose label
   vanished is refused as a possible rename rather than called withdrawn.
4. A reference to a unit or paragraph the document lacks is a computed note; one it has is not.
   Every pattern is config: another set of patterns reads other words, and with none declared
   nothing is checked.
5. The case phase writes the record and one deliverable per later version.
6. On the worked case: the cell that had no record, and the one broken reference, alone.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from effect_proof import prove_effect  # noqa: E402
import version_changes as vc  # noqa: E402

CONFIG = {"min_sentence_similarity": 0.6, "min_shared_headings": 0.5}
BEFORE = {"id": "doc_a", "text": (
    "# Title\n\n## Part One\n\nState: open\n\nThe first party shall deliver the goods within ten days.\n\n"
    "This sentence stays exactly as it was written.\n\nThis sentence is going away for good now.\n\n"
    "## Part Two\n\nPeriod length: 30 days\n\n| Line | Cost (credits) |\n|---|---|\n| Alpha entry | 10 |\n"
    "| Beta entry | 20 |\n| Gamma entry | 30 |\n")}
AFTER = {"id": "doc_b", "text": (
    "# Title\n\n## Part One\n\nState: closed\n\nThe first party shall deliver the goods within twenty days.\n\n"
    "An entirely new sentence arrives here today.\n\n"
    "## Part Two\n\nThis sentence stays exactly as it was written.\n\nPeriod length: 21 days\n\n"
    "| Line | Cost (credits) |\n|---|---|\n| Alpha entry | 10 |\n| Gamma entry | 35 |\n| Delta entry | 40 |\n")}
TIE_BEFORE = {"id": "tie_a", "text": "## Part One\n\nThe red box stands on the table today.\n"}
TIE_AFTER = {"id": "tie_b", "text": "## Part One\n\nThe blue box stands on the table today.\n\n"
                                    "The green box stands on the table today.\n"}
RENAME_BEFORE = {"id": "ren_a", "text": "## Part One\n\nOld period name: 21 days\n"}
RENAME_AFTER = {"id": "ren_b", "text": "## Part One\n\nNew period title: 21 days\n"}
REFERENCES = {"id": "refs", "text": (
    "## Article 1. First\n\n1. See paragraph 2 of Article 2 and Annex I.\n\n2. See Article 9 and Annex V.\n\n"
    "3. See paragraph 4 of Article 2, and paragraph 3 of Article 2.\n\n4. See Article 5 of the Convention.\n\n"
    "## Article 2. Second\n\n1. Words of the paragraph.\n\n2. Words of the paragraph.\n\n3. [Deleted]\n\n"
    "## Annex I. Schedule\n\nWords of the annex here.\n")}
OTHER_WORDS = {"id": "other", "text": "## Section 1. One\n\nThis sends the reader to Section 7 instead.\n"}
OTHER_PATTERNS = {"numbered_references": {
    "targets": [{"name": "t", "regex": "^(section)\\s+([0-9]+)", "kind_group": 1, "number_group": 2}],
    "references": [{"name": "r", "regex": "\\b(section)\\s+([0-9]+)", "kind_group": 1, "number_group": 2}]}}
WORKED = ROOT / "benchmark" / "dev_cases" / "host_agreement_three_rounds" / "workload"


def observe_sentences():
    rows = vc.sentence_changes(BEFORE, AFTER, CONFIG)
    tie = vc.sentence_changes(TIE_BEFORE, TIE_AFTER, CONFIG)
    return {"rows": sorted((r["change"], (r.get("before") or {}).get("text", ""), (r.get("after") or {}).get("text", ""),
                            (r.get("before") or {}).get("document_id", ""), (r.get("after") or {}).get("document_id", ""))
                           for r in rows),
            "tie": sorted(r["change"] for r in tie)}


SENTENCES = {"rows": sorted([
    ("changed", "The first party shall deliver the goods within ten days.",
     "The first party shall deliver the goods within twenty days.", "doc_a", "doc_b"),
    ("removed", "This sentence is going away for good now.", "", "doc_a", ""),
    ("added", "", "An entirely new sentence arrives here today.", "", "doc_b")]),
    "tie": ["added", "added", "removed"]}


def observe_cells_and_fields():
    made = vc.document_changes(BEFORE, AFTER, CONFIG)
    return {"cells": sorted((c["change"], c["row"], c.get("before", ""), c.get("after", "")) for c in made["cells"]),
            "fields": [(f["change"], f["label"], f["before"], f["after"]) for f in made["fields"]]}


CELLS_AND_FIELDS = {
    "cells": sorted([("row_removed", "Beta entry", "Beta entry | 20", ""),
                     ("cell_changed", "Gamma entry", "30", "35"), ("row_added", "Delta entry", "", "Delta entry | 40")]),
    "fields": [("value_changed", "State", "open", "closed")]}


def observe_figures():
    made = vc.document_changes(BEFORE, AFTER, CONFIG)
    renamed = vc.document_changes(RENAME_BEFORE, RENAME_AFTER, CONFIG)
    return {"figures": [(r["relation"], r["label"], r["earlier"], r["now"], r["measure"]) for r in made["figures"]],
            "withdrawn": [r["label"] for r in renamed["figures"] if r["relation"] == "absent_since_prior"],
            "refused": [(r["label"], r["reason_kind"]) for r in renamed["figure_refusals"]]}


FIGURES = {"figures": [("changed_from_prior", "period length", 30.0, 21.0, "days"),
                       ("absent_since_prior", "beta entry", 20.0, None, "credits")], "withdrawn": [],
           "refused": [("old period name", "possible_rename")]}


def observe_references():
    with tempfile.TemporaryDirectory(prefix="shimmer_ref_patterns_") as td:
        other = Path(td) / "patterns.json"
        other.write_text(json.dumps(OTHER_PATTERNS), encoding="utf-8")
        empty = Path(td) / "none.json"
        empty.write_text("{}", encoding="utf-8")
        return {"declared": sorted((n["reference"], n["reason"]) for n in vc.broken_references(
                    REFERENCES, vc.load_reference_patterns())),
                "other_words": [n["reference"] for n in vc.broken_references(
                    OTHER_WORDS, vc.load_reference_patterns(other))],
                "none_declared": vc.broken_references(REFERENCES, vc.load_reference_patterns(empty)),
                "no_numbered_unit": vc.broken_references(BEFORE, vc.load_reference_patterns())}


REFERENCE_NOTES = {"declared": sorted([("Article 9", "no_such_unit"), ("Annex V", "no_such_unit"),
                                       ("paragraph 4 of Article 2", "no_such_paragraph"),
                                       ("paragraph 3 of Article 2", "paragraph_deleted")]),
                   "other_words": ["Section 7"], "none_declared": [], "no_numbered_unit": []}


def observe_phase():
    from multi_round_rounds_checks import mocked_multi_round_run
    with tempfile.TemporaryDirectory(prefix="shimmer_version_phase_") as td:
        run = mocked_multi_round_run(td)
        record = run["record"].get("version_changes") or {}
        folders = sorted(p.parent.name for p in (Path(run["run_dir"]) / "deliverables").rglob("version_changes.md"))
        audit = (Path(run["run_dir"]) / "audit" / vc.RECORD_NAME).is_file()
        return {"code": run["code"], "availability": record.get("availability"), "folders": len(folders), "audit": audit}


PHASE = {"code": 0, "availability": "recorded", "folders": 1, "audit": True}


def observe_worked_case():
    manifest = json.loads((WORKED / "case_manifest.json").read_text(encoding="utf-8"))
    import text_extract
    documents = [{"id": p.stem, "name": p.name, "text": text_extract.extract_text(p).replace("\r\n", "\n")}
                 for p in sorted((WORKED / "context").iterdir())]
    record = vc.case_changes(manifest, documents)
    last = next(c for c in record["comparisons"] if c["after"].endswith("round_3") and "agreement" in c["after"])
    return {"cells": [(c["row"], c["before"], c["after"]) for c in last["cells"]],
            "references": [(n["round_id"], n["reference"], n["reason"]) for n in record["references"]]}


WORKED_CASE = {"cells": [("Security services", "300,000", "200,000")],
               "references": [("r3", "paragraph 4 of Article 8", "no_such_paragraph")]}


def _deliverable_not_written():
    import multi_round_phase
    return patch.object(multi_round_phase, "version_change_record", lambda *a, **k: {"availability": "failed"})


class VersionChangeChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        VersionChangeChecks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    def test_sentences(self):
        self.prove("changed_sentences_cite_both", observe_sentences, SENTENCES,
                   lambda: patch.object(vc, "_similar", lambda a, b: 0.0))

    def test_a_tie_is_refused(self):
        self.prove("a_tie_is_refused", observe_sentences, SENTENCES, lambda: patch.object(vc, "_TIE", -1.0))

    def test_cells(self):
        self.prove("table_cells_recorded", observe_cells_and_fields, CELLS_AND_FIELDS,
                   lambda: patch.object(vc, "_table_changes", lambda a, b: ([], [])))

    def test_fields(self):
        self.prove("text_values_recorded", observe_cells_and_fields, CELLS_AND_FIELDS,
                   lambda: patch.object(vc, "_text_field_changes", lambda a, b, c: []))

    def test_figures(self):
        self.prove("figures_from_the_review_functions", observe_figures, FIGURES,
                   lambda: patch.object(vc, "_figure_changes", lambda a, b: ([], [], set())))

    def test_references(self):
        self.prove("references_checked_from_config", observe_references, REFERENCE_NOTES,
                   lambda: patch.object(vc, "_declared_targets", lambda units, patterns: {}))

    def test_phase(self):
        self.prove("the_case_phase_writes_it", observe_phase, PHASE, _deliverable_not_written)

    def test_worked_case(self):
        if not WORKED.is_dir():
            self.skipTest("benchmark/dev_cases/ is not in this tree")
        self.prove("the_worked_case", observe_worked_case, WORKED_CASE,
                   lambda: patch.object(vc, "broken_references", lambda d, p: []))


def check():
    VersionChangeChecks.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(VersionChangeChecks).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: sentences, table cells, text values and "
                    "figures that changed between versions are recorded with their citations, a tie is refused, "
                    "numbered references are checked from config alone, and the case phase writes the deliverable"
                    % len(VersionChangeChecks.evidence))


def main():
    status, detail = check()
    for proof in VersionChangeChecks.evidence:
        print(proof["name"], proof["status"])
        print("  mutated:", json.dumps(proof["mutated"], sort_keys=True, default=str)[:300])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
