"""Checks for the five benchmark adapters under benchmark/adapters/ (loop stage S4c), run
by the verify gate (scripts/verify_session1.py) through check(); check_group(name) runs one
group, and `py -3.12 -X utf8 scripts/adapter_checks.py [group ...]` runs them by hand.

Every case runs on small synthetic items in each benchmark's release schema, as confirmed
on the B-dev development items (the fixtures beside each adapter: hand-written, CUAD's 41
QA entries per contract expanded by the tracked
benchmark/adapters/cuad/fixtures/make_synthetic_items.py), in temporary
folders; nothing under config/, durable/, ontology/ or output/ is read or written, and no
benchmark data under external/ is ever needed. benchmark/ is not shipped in the container
image, so with benchmark/adapters/ absent every case is SKIPPED with the reason.

  build      building twice gives byte-identical output; the cut budget is computed per
             document from the bundle's own conventions with the B1 prompt; the cut rule
             keeps whole parts and writes the cut line with hand-counted words; evidence
             units are read on the kept text; a build without a budget, or with a
             document off its declared side, is refused; an empty document is skipped;
             one word rule (section 5.6, Words) counts every part, band and cut line;
             ContractNLI makes one part per span of the agreement's own span list
  split      the hash split rule (SHA-256 of the document's split key, mod 5) is
             recomputed here independently, and every item of a document falls on
             that document's side, including where the item's own id would not
  opaque     opaque ids equal the first 12 hex characters of SHA-256 of
             `item:<benchmark>:<source id>` (and `document:...`), and no source id
             appears in any file inside a bundle
  structure  each bundle passes a structural reading of input-format-v1-draft: the
             headings give the expected unit ids, every unit's label line is
             `Passage: part` with no digit, a source `#` line never starts a unit, one
             rule per item, the manifest names the target alone; and Shimmer's own unit
             splitter (scripts/pairing_map.split_units) gives the same unit ids, keeps an
             escaped `#` line inside its unit, and numbers positions above 99 as u100
  mapping    the section 5.1 and 5.2 mapping gives the expected label for every case
             of the hand-written run outputs (run failure from the completion record,
             refusal, silence, irregular, ok, superseded revisions, CUAD missing_field
             against another relation, prior relations), for B2, B1 and B0, with S-1
             and S-2; B3 is refused while the typed-record key is unsettled
  metrics    each benchmark's metric on a tiny confusion example equals the hand
             computation written beside it, and an end-to-end score on a built
             bundle gives the hand-computed accuracy, location recall and false
             positives
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "benchmark" / "adapters"
NAMES = ("contradoc", "cuad", "scitab", "findver", "contractnli")
ABSENT_REASON = "benchmark/adapters/ is not present here (the container image ships no benchmark/)"
_MODULES = {}


def _absent(base=None) -> bool:
    base = Path(base) if base is not None else ADAPTERS
    return not (base / "common" / "bundle.py").is_file() or not all(
        (base / n / "adapter.py").is_file() for n in NAMES)


def _common():
    if "common" not in _MODULES:
        sys.path.insert(0, str(ADAPTERS))
        try:
            _MODULES["common"] = {m: importlib.import_module("common." + m)
                                  for m in ("ids", "bundle", "cut", "mapping", "metrics", "cli",
                                            "prompt")}
        finally:
            sys.path.remove(str(ADAPTERS))
    return _MODULES["common"]


def _adapter(name):
    if name not in _MODULES:
        _common()
        sys.path.insert(0, str(ADAPTERS))
        try:
            spec = importlib.util.spec_from_file_location("benchmark_adapter_" + name,
                                                          ADAPTERS / name / "adapter.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            while str(ADAPTERS) in sys.path:
                sys.path.remove(str(ADAPTERS))
        _MODULES[name] = module
    return _MODULES[name]


def _fixture(name, file_name):
    return ADAPTERS / name / "fixtures" / file_name


# FinDVer's fixture is laid out as the release is: an items file under data/ and the
# filings under financial_reports/ beside it.
_SOURCES = {"findver": "data/testmini.json"}


def _source(name):
    """The synthetic items file of one adapter."""
    return _fixture(name, _SOURCES.get(name, "synthetic_items.json"))


def _build(name, out, source=None, **options):
    """A build of the synthetic items; --development unless the caller says otherwise."""
    options.setdefault("development", True)
    if name == "findver" and source is not None:
        options.setdefault("reports", _fixture("findver", "financial_reports"))
    return _common()["cli"].build(_adapter(name), source or _source(name), out, **options)


class WordCounter:
    """A stand-in tokenizer: one token per whitespace-separated word; the prompt with
    an empty document counts a fixed `overhead` (or its lines, when `lines` is set)."""

    def __init__(self, overhead=100, lines=False):
        self.overhead, self.lines = overhead, lines

    def count(self, text):
        return len(text.split())

    def count_prompt(self, system, user):
        return (system + "\n" + user).count("\n") + 1 if self.lines else self.overhead


def _files(folder):
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class _Case(unittest.TestCase):
    def setUp(self):
        if _absent():
            self.skipTest(ABSENT_REASON)
        self.tmp = tempfile.TemporaryDirectory(prefix="adapter_check_")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        if hasattr(self, "tmp"):
            self.tmp.cleanup()


# ---------------------------------------------------------------------------
# build


class BuildChecks(_Case):
    def test_build_twice_is_byte_identical(self):
        for name in NAMES:
            _build(name, self.root / name / "one")
            _build(name, self.root / name / "two")
            one, two = _files(self.root / name / "one"), _files(self.root / name / "two")
            self.assertTrue(one, name)
            self.assertEqual(sorted(one), sorted(two), name + ": the same files")
            for path in one:
                self.assertEqual(one[path], two[path], "%s: %s differs between two builds" % (name, path))
                self.assertNotIn(b"\r", one[path], "%s: %s carries a CR" % (name, path))
                self.assertFalse(one[path].startswith(b"\xef\xbb\xbf"), name + ": a byte-order mark")

    def test_cut_rule_keeps_whole_parts_with_counted_words(self):
        c = _common()
        # Budget = context - prompt overhead - output allowance - 32 = 198 - 100 - 10 - 32 = 56.
        _build("contradoc", self.root / "cut", max_context=198, output_allowance=10,
               token_counter=WordCounter(100))
        parts = {d["source_document_id"]: d for d in _json(self.root / "cut" / "parts.json")["documents"]}
        doc = parts["101"]
        self.assertEqual((doc["cut"]["budget"], doc["cut"]["prompt_overhead"]), (56, 100))
        # ContraDoc document 101: parts of 16, 18 and 12 words (46 in all). The rendered
        # document adds the title (2 words), and per part a heading (2) and the label
        # line (2). The cut line "[Document cut. The remaining N of M words are not
        # shown.]" is 11 words. Whole: 2 + 20 + 22 + 16 = 60 > 56; two whole parts with
        # the cut line: 2 + 20 + 22 + 11 = 55 <= 56; three would be 71. Removed 46 - 34 = 12.
        self.assertEqual((doc["cut"]["cut"], doc["cut"]["parts_kept"], doc["cut"]["words_removed"],
                          doc["cut"]["words_total"], doc["source_words"]), (True, 2, 12, 46, 46))
        text = (self.root / "cut" / doc["document_id"] / "context" / (doc["document_id"] + ".md")).read_text(encoding="utf-8")
        self.assertTrue(text.endswith("sits here.\n[Document cut. The remaining 12 of 46 words are not shown.]\n"))
        self.assertEqual([p["part"] for p in doc["parts_beyond_cut"]], [3])
        self.assertFalse(parts["409"]["cut"]["cut"], "a document that fits is not cut")
        # Evidence units are read on the kept text: the evidence sentence of 101 was in the
        # cut third part, its reference sentence in the first part, which is kept.
        answer = _json(self.root / "cut" / doc["document_id"] / "answer_key.json")["items"][0]
        self.assertEqual((answer["evidence_unit_ids"], answer["evidence_beyond_cut"]), (["u01-p-00001"], True))
        # A part cut mid-text keeps only the evidence that survived: one paragraph of 8 + 7
        # words, budget 162 - 100 - 10 - 32 = 20: whole 2 + 4 + 15 = 21 > 20; the part with
        # the line is 32; three words and the line are 2 + 4 + 3 + 11 = 20. The evidence
        # sentence was in the cut tail, so its unit is no longer an evidence unit.
        source = self.root / "one.json"
        source.write_text(json.dumps({"pos": {"501": {
            "unique id": "501", "text": "Alpha one two three four five six seven. "
                                        "The orchard has no trees at all.",
            "evidence": "The orchard has no trees at all."}}}), encoding="utf-8")
        _build("contradoc", self.root / "tail", source, max_context=162, output_allowance=10,
               token_counter=WordCounter(100))
        record = _json(self.root / "tail" / "parts.json")["documents"][0]
        self.assertEqual((record["cut"]["whole_parts_kept"], record["cut"]["words_removed"]), (0, 12))
        answer = _json(self.root / "tail" / record["document_id"] / "answer_key.json")["items"][0]
        self.assertEqual((answer["evidence_unit_ids"], answer["evidence_beyond_cut"]), ([], True))
        # A first part that alone does not fit is cut at the last whitespace that fits:
        # parts of 20 and 1 words, budget 15: one part with the line is 31; four words
        # and the 11-word line are 15. Removed: 21 - 4 = 17.
        first = " ".join("w%d" % i for i in range(1, 21))
        count = WordCounter().count
        kept, info = c["cut"].cut_parts([first, "w21"], 15, count, lambda t: "\n".join(t))
        self.assertEqual(kept, ["w1 w2 w3 w4\n[Document cut. The remaining 17 of 21 words are not shown.]"])
        self.assertEqual((info["parts_kept"], info["whole_parts_kept"], info["words_removed"]), (1, 0, 17))
        # A table part counts its cell words, as the source word count does.
        self.assertEqual(c["cut"].words("| A | 71.2 |\n|---|---|\n| B \\| C | 9 |"), 6)

    def test_one_word_rule_for_bands_and_the_cut_line(self):
        # Section 5.6, Words: whitespace-separated tokens, a token made only of `|`, `-` and
        # `:` with at least one `|` (table markup) not counted. One function counts every
        # part, the band and the cut line: a token of hyphens or colons alone, or a pipe
        # inside other characters, is still a word.
        c = _common()
        sample = "Revenue | 2023 rose :--| 5 percent -- a|b ||"
        self.assertEqual(c["ids"].word_count(sample), 7)
        self.assertEqual(c["cut"].words(sample), c["ids"].word_count(sample))
        for name in ("contradoc", "cuad", "findver", "contractnli"):
            _build(name, self.root / name)
            for record in _json(self.root / name / "parts.json")["documents"]:
                text = (self.root / name / record["document_id"] / "context"
                        / (record["document_id"] + ".md")).read_text(encoding="utf-8")
                units = c["bundle"].read_units(text)
                self.assertEqual([p["words"] for p in record["parts"]],
                                 [c["ids"].word_count(u[3]) for u in units], name)
                self.assertEqual(record["source_words"], sum(p["words"] for p in record["parts"]))
                self.assertEqual(record["length_band"], c["ids"].length_band(record["source_words"]))
        # A FinDVer table counts its cell words, not its pipes: the fixture's table entry is
        # 6 words of text and 6 cell words between 9 pipes on 3 rows (17 with the line of
        # text after it), where splitting at whitespace alone gives 26.
        entry = _json(_fixture("findver", "financial_reports/SYNA-2024-01-31_10-K.json"))["context"][1]
        self.assertEqual((_adapter("findver").entry_text(entry)[2], len(entry["context"].split())), (17, 26))

    def test_budget_is_computed_per_document_from_its_own_conventions(self):
        # One line per convention in the B1 prompt: the two-claim table's prompt is one
        # line longer than the one-claim table's, so its budget is one token smaller.
        _build("scitab", self.root / "b", max_context=5000, output_allowance=100,
               token_counter=WordCounter(lines=True))
        docs = {d["source_document_id"]: d["cut"] for d in _json(self.root / "b" / "parts.json")["documents"]}
        self.assertEqual(docs["syn-tab-1"]["prompt_overhead"] - docs["syn-tab-3"]["prompt_overhead"], 1)
        for cut in docs.values():
            self.assertEqual(cut["budget"], 5000 - cut["prompt_overhead"] - 100 - 32)

    def test_build_refuses_without_budget_or_off_its_declared_side(self):
        with self.assertRaisesRegex(ValueError, "never skipped"):
            _build("cuad", self.root / "a", development=False, side="holdout")
        budget = dict(max_context=5000, output_allowance=10, token_counter=WordCounter())
        # SciTab: syn-paper-bz is development, syn-paper-a holdout: a holdout build refuses.
        with self.assertRaisesRegex(ValueError, "not on the declared side holdout"):
            _build("scitab", self.root / "b", development=False, side="holdout", **budget)
        self.assertFalse((self.root / "b").exists() and any((self.root / "b").iterdir()),
                         "a refused build writes nothing")
        # FinDVer: a holdout build needs testmini and refuses a report testmini holds.
        records = _json(_source("findver"))
        mini = self.root / "mini.json"
        mini.write_text(json.dumps([records[0]]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "needs --testmini"):
            _build("findver", self.root / "c", development=False, side="holdout", **budget)
        with self.assertRaisesRegex(ValueError, "also appear in testmini"):
            _build("findver", self.root / "d", development=False, side="holdout", testmini=mini, **budget)
        # An item whose own `split` names the other official split is refused: the testmini
        # items are not holdout, even with no report in common with the testmini file given.
        other = self.root / "other_mini.json"
        other.write_text(json.dumps([dict(records[0], report="SYN-NONE-2024-01-01_10-K.json")]),
                         encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "official split is not the declared side holdout: syn-ex-1"):
            _build("findver", self.root / "e", development=False, side="holdout", testmini=other, **budget)

    def test_findver_reads_claims_and_filings_apart(self):
        # The release (confirmed on the B-dev development items) keeps the claims in
        # data/<split>.json and each filing in financial_reports/<report>: `statement` is the
        # claim, `entailment_label` a boolean (true is entailed), `relevant_context` the
        # integer ids of the filing's entries, from 0. A table entry is pipe rows with no
        # separator row; it is written with one after its first row (section 5.6, as
        # SciTab's), and its words are its cell words.
        _build("findver", self.root / "b")
        ids_ = _common()["ids"]
        doc = ids_.opaque_document_id("findver", "SYNA-2024-01-31_10-K.json")
        record = next(d for d in _json(self.root / "b" / "parts.json")["documents"] if d["document_id"] == doc)
        # 5 words; 6 + 6 cell words + 5 (pipes not counted); `#` is a word, 2 + 5.
        self.assertEqual([p["words"] for p in record["parts"]], [5, 17, 7])
        self.assertEqual([p["source"] for p in record["parts"]],
                         [{"context_index": 0, "kind": "paragraph"}, {"context_index": 1, "kind": "table"},
                          {"context_index": 2, "kind": "paragraph"}])
        self.assertEqual((record["issuer_cik"], record["context_index_base"]), (1000001, 0))
        self.assertEqual(record["report_sha256"], hashlib.sha256(
            _fixture("findver", "financial_reports/SYNA-2024-01-31_10-K.json").read_bytes()).hexdigest())
        text = (self.root / "b" / doc / "context" / (doc + ".md")).read_text(encoding="utf-8")
        self.assertIn("Units by quarter are shown below.\n\n| Quarter | Units |\n|---|---|\n"
                      "| First | 120 |\n| Second | 140 |\n\nUnits are counted when shipped.", text)
        answers = {a["item_id"]: a for a in _json(self.root / "b" / doc / "answer_key.json")["items"]}
        gold = {s: answers[ids_.opaque_item_id("findver", s)] for s in ("syn-ex-1", "syn-ex-2", "syn-ex-3")}
        self.assertEqual([(g["gold"], g["subset"], g["evidence_unit_ids"], g["location_measurable"])
                          for g in gold.values()],
                         [("entailed", "ie", ["u02-p-00002"], False),
                          ("refuted", "numeric", ["u02-p-00002"], True),
                          ("refuted", "ie", ["u01-p-00001"], True)])
        rules = (self.root / "b" / doc / "conventions" / "rules.md").read_text(encoding="utf-8")
        self.assertIn("Claim about the filing: The company sells two products. The claim must agree "
                      "with the passages of the filing.", rules)
        # A label that is not a boolean, and a filing whose entry ids are not 0, 1, 2 ..., are
        # refused rather than read.
        adapter = _adapter("findver")
        with self.assertRaisesRegex(ValueError, "not a boolean"):
            adapter._gold({"example_id": "x", "entailment_label": "true"})
        folder = self.root / "reports"
        folder.mkdir()
        (folder / "X-2024-01-01_10-K.json").write_text(json.dumps(
            {"url": "", "context": [{"id": 1, "context": "a", "type": "paragraph"}]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not carry id 0"):
            adapter.read_filing(folder, "X-2024-01-01_10-K.json")
        with self.assertRaisesRegex(ValueError, "a report name is a file name"):
            adapter.read_filing(folder, "../X-2024-01-01_10-K.json")

    def test_contractnli_items_rules_and_evidence(self):
        # 2 agreements x 3 hypotheses; one rule per hypothesis with the hypothesis as its
        # only slot (whitespace collapsed). One part per span of the agreement's own span
        # list (section 5.6): 7101 has 7 spans, span 3 a single space (no part), span 2 and
        # span 4 two halves of one line (two parts), span 5 a `#` line (escaped). An
        # evidence index marks the part made from the span it names; nda-1 names spans 1
        # and 3, and the space marks nothing.
        _build("contractnli", self.root / "b")
        items = _json(self.root / "b" / "items.json")["items"]
        self.assertEqual(len(items), 6)
        doc = _common()["ids"].opaque_document_id("contractnli", 7101)
        rules = (self.root / "b" / doc / "conventions" / "rules.md").read_text(encoding="utf-8")
        self.assertIn("## CONV-CNLI-NDA-2 Hypothesis [required] [conformance]\n\nHypothesis about the "
                      "agreement: The receiving party shall not share the information with its "
                      "employees. The hypothesis must agree with the passages of the agreement. If the "
                      "agreement does not settle the hypothesis, emit UNCERTAIN.\n", rules)
        record = next(d for d in _json(self.root / "b" / "parts.json")["documents"] if d["document_id"] == doc)
        self.assertEqual([p["source"]["span"] for p in record["parts"]], [0, 1, 2, 4, 5, 6])
        self.assertEqual((record["spans"], record["spans_without_text"]), (7, [3]))
        self.assertEqual([p["words"] for p in record["parts"]], [3, 10, 7, 8, 2, 10])
        text = (self.root / "b" / doc / "context" / (doc + ".md")).read_text(encoding="utf-8")
        self.assertIn("## P-00003\n\nPassage: part\n\nThe receiving party may share confidential "
                      "information\n\n## P-00004\n\nPassage: part\n\nwith its employees who need "
                      "to know it.\n\n## P-00005\n\nPassage: part\n\n\\# Term\n\n## P-00006", text)
        answers = {a["hypothesis_key"]: a for a in _json(self.root / "b" / doc / "answer_key.json")["items"]}
        self.assertEqual((answers["nda-2"]["gold"], answers["nda-2"]["evidence_unit_ids"],
                          answers["nda-2"]["location_measurable"]), ("contradiction", ["u04-p-00004"], True))
        self.assertEqual((answers["nda-1"]["evidence_unit_ids"], answers["nda-1"]["location_measurable"]),
                         (["u02-p-00002"], False))
        self.assertEqual(answers["nda-11"]["gold"], "not mentioned")
        other = _common()["ids"].opaque_document_id("contractnli", 7102)
        answers = {a["hypothesis_key"]: a for a in _json(self.root / "b" / other / "answer_key.json")["items"]}
        self.assertEqual(answers["nda-11"]["evidence_unit_ids"], ["u03-p-00003"])
        # Text the spans leave out is kept as a part of its own (span None), never dropped;
        # spans out of order, overlapping or outside the text, a missing span list, and an
        # evidence index naming no span are refused rather than read.
        adapter = _adapter("contractnli")
        self.assertEqual(adapter.span_pieces("Head. Body text. Tail", [[6, 16]]),
                         [{"span": None, "start": 0, "end": 6}, {"span": 0, "start": 6, "end": 16},
                          {"span": None, "start": 16, "end": 21}])
        for spans, message in (([[5, 9], [3, 4]], "out of order"), ([[0, 5], [4, 9]], "out of order"),
                               ([[0, 99]], "outside the text"), ([], "has no 'spans' list"),
                               ([[0, "5"]], "not a \\[start, end\\] pair")):
            with self.assertRaisesRegex(ValueError, message):
                adapter.span_pieces("Some agreement text.", spans, "x")
        data = adapter.read_source(_fixture("contractnli", "synthetic_items.json"))
        data["documents"][0]["annotation_sets"][0]["annotations"]["nda-2"]["spans"] = [7]
        with self.assertRaisesRegex(ValueError, "evidence index 7 for nda-2 names no span"):
            adapter.documents(data)

    def test_contradoc_reads_the_release_shape(self):
        # The release (confirmed on the B-dev development items) is {"pos": {...}, "neg":
        # {...}}: gold comes from the container, and `ref sentences` is a string, a list of
        # strings, or absent. 101's evidence is in part 3 and its reference (a list) in part
        # 1; 205's evidence is in part 3 and its reference (a string) in part 2.
        _build("contradoc", self.root / "b")
        ids_ = _common()["ids"]
        answers = {}
        for source in ("101", "102", "205", "409"):
            doc = ids_.opaque_document_id("contradoc", source)
            answers[source] = _json(self.root / "b" / doc / "answer_key.json")["items"][0]
        self.assertEqual({s: a["gold"] for s, a in answers.items()},
                         {"101": "contradictory", "102": "not contradictory",
                          "205": "contradictory", "409": "not contradictory"})
        self.assertEqual(answers["101"]["evidence_unit_ids"], ["u01-p-00001", "u03-p-00003"])
        self.assertEqual(answers["205"]["evidence_unit_ids"], ["u02-p-00002", "u03-p-00003"])
        self.assertEqual([answers[s]["location_measurable"] for s in ("101", "102", "205", "409")],
                         [True, False, True, False])
        adapter = _adapter("contradoc")
        for bad, message in (([{"unique id": "1", "text": "x"}], "expected an object"),
                             ({"pos": {"1": {"unique id": "2", "text": "x"}}}, "carries unique id"),
                             ({"pos": {"1": {"unique id": "1", "text": "x"}},
                               "neg": {"1": {"unique id": "1", "text": "y"}}}, "in both containers")):
            source = self.root / "bad.json"
            source.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, message):
                adapter.read_source(source)

    def test_cuad_matches_the_data_spelling(self):
        # The QA ids spell 15 categories differently from the paper's list (confirmed on the
        # B-dev development items): the item is found by the data's spelling at the end of
        # its id, and the rule text keeps the paper's name (section 5.5).
        _build("cuad", self.root / "b")
        ids_ = _common()["ids"]
        source = _json(_fixture("cuad", "synthetic_items.json"))
        alpha = next(e for e in source["data"] if e["title"] == "SYN-AARDVARK-COPY")
        doc = ids_.opaque_document_id("cuad", hashlib.sha256(
            alpha["paragraphs"][0]["context"].encode("utf-8")).hexdigest())
        answers = {a["category_row"]: a for a in _json(self.root / "b" / doc / "answer_key.json")["items"]}
        self.assertEqual(answers["cuad-16"]["item_id"], ids_.opaque_item_id(
            "cuad", "SYN-AARDVARK-COPY__Termination For Convenience"))
        self.assertEqual((answers["cuad-16"]["gold"], answers["cuad-07"]["gold"]), ("present", "absent"))
        rules = (self.root / "b" / doc / "conventions" / "rules.md").read_text(encoding="utf-8")
        self.assertIn("## CONV-CUAD-16 Category [required] [conformance]\n\nThe document must contain, "
                      "in at least one passage, a clause of this category: Termination for "
                      "Convenience.\n", rules)
        # A QA id spelled as the paper spells it matches no row: the build is refused, never
        # guessed.
        changed = json.loads(json.dumps(source))
        entry = next(e for e in changed["data"] if e["title"] == "SYN-AARDVARK-COPY")
        qa = next(q for q in entry["paragraphs"][0]["qas"] if q["id"].endswith("Terminate Renewal"))
        qa["id"] = "SYN-AARDVARK-COPY__Notice to Terminate Renewal"
        path = self.root / "wrong.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "0 QA entries for category 'Notice Period To Terminate Renewal'"):
            _build("cuad", self.root / "w", path)

    def test_scitab_table_stored_differently_by_its_claims(self):
        # On the B-dev development items one table's claims store different cells. The build
        # is not refused: the document is the table as its first claim in file order stores
        # it, and parts.json names every claim whose table differs, with the fields. Claims
        # of one table naming different papers are still refused (the paper is the split key).
        records = _json(_fixture("scitab", "synthetic_items.json"))
        variant = json.loads(json.dumps(records[1]))
        variant["table_content_values"] = [["A", "71.2", "64.0"], ["B", "73.5", "65.9"]]
        source = self.root / "variants.json"
        source.write_text(json.dumps([records[0], variant] + records[2:]), encoding="utf-8")
        _build("scitab", self.root / "b", source)
        record = next(d for d in _json(self.root / "b" / "parts.json")["documents"]
                      if d["source_document_id"] == "syn-tab-1")
        self.assertEqual((record["table_from_claim"], record["table_variants"]),
                         ("9001", [{"source_item_id": "9002", "fields": ["table_content_values"]}]))
        text = (self.root / "b" / record["document_id"] / "context" / (record["document_id"] + ".md")).read_text(encoding="utf-8")
        self.assertIn("| B | 73.5 | 63.1 |", text)
        self.assertNotIn("65.9", text)
        variant["paper_id"] = "syn-paper-other"
        source.write_text(json.dumps([records[0], variant]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "disagree on paper_id"):
            _build("scitab", self.root / "c", source)

    def test_empty_document_is_skipped_and_listed(self):
        records = _json(_fixture("contradoc", "synthetic_items.json"))
        records["neg"]["777"] = {"unique id": "777", "text": "  \n\n \n"}
        source = self.root / "with_empty.json"
        source.write_text(json.dumps(records), encoding="utf-8")
        summary = _build("contradoc", self.root / "b", source)
        self.assertEqual([s["source_document_id"] for s in summary["skipped_documents"]], ["777"])
        self.assertEqual(summary["documents"], 4)
        self.assertEqual(len(_json(self.root / "b" / "parts.json")["skipped"]), 1)


# ---------------------------------------------------------------------------
# split


def _independent_side(key) -> str:
    text = str(key)
    value = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest(), "big")
    return "development" if value % 5 == 0 else "holdout"


class SplitChecks(_Case):
    # the documented split key of each hash-split benchmark, read from the source record
    def _expected_keys(self, name):
        source = _json(_source(name))
        if name == "contradoc":  # 101 and 102 share 6 of 7 sentences: one group, key 101
            return {"101": "101", "102": "101", "205": "205", "409": "409"}
        if name == "scitab":
            return {r["table_id"]: r["paper_id"] for r in source}
        if name == "cuad":
            return {hashlib.sha256(e["paragraphs"][0]["context"].encode("utf-8")).hexdigest():
                    hashlib.sha256(e["paragraphs"][0]["context"].encode("utf-8")).hexdigest()
                    for e in source["data"]}
        raise AssertionError(name)

    def test_every_item_of_a_document_on_one_side(self):
        differs = 0
        for name in ("contradoc", "cuad", "scitab"):
            _build(name, self.root / name)
            parts = _json(self.root / name / "parts.json")["documents"]
            items = _json(self.root / name / "items.json")["items"]
            keys = self._expected_keys(name)
            side_of = {}
            for doc in parts:
                self.assertEqual(doc["split_key"], keys[doc["source_document_id"]],
                                 "%s: the split key is the documented document key" % name)
                side = _independent_side(doc["split_key"])
                self.assertEqual(doc["side"], side, "%s: side of %s" % (name, doc["document_id"]))
                side_of[doc["document_id"]] = side
            by_doc = {}
            for item in items:
                by_doc.setdefault(item["document_id"], set()).add(side_of[item["document_id"]])
                differs += _independent_side(item["source_item_id"]) != side_of[item["document_id"]]
            self.assertTrue(all(len(s) == 1 for s in by_doc.values()), name)
            rows = _adapter(name).split_rows(_adapter(name).read_source(_source(name)))
            for row in rows:
                self.assertEqual(row["side"], _independent_side(row["split_key"]), name)
        self.assertGreater(differs, 0, "no fixture item whose own id would fall on another side")
        self.assertIn("development", {_independent_side(k) for k in ("409", "syn-paper-bz")})

    def test_contradoc_groups_come_from_the_frozen_assignment(self):
        # The assignment is computed once on the whole input; a later build from a sample
        # holding only 102 keeps 102 in group 101 (its near-duplicate 101 is not in the
        # sample), where regrouping the sample would have made 102 its own group.
        adapter = _adapter("contradoc")
        records = _json(_fixture("contradoc", "synthetic_items.json"))
        assignment = self.root / "assignment.json"
        code = _common()["cli"].main(adapter, ["split", "--input", str(_fixture("contradoc", "synthetic_items.json")),
                                               "--out", str(assignment)])
        self.assertEqual(code, 0)
        sample = self.root / "sample.json"
        sample.write_text(json.dumps({"neg": {"102": records["neg"]["102"]}}), encoding="utf-8")
        budget = dict(max_context=5000, output_allowance=10, token_counter=WordCounter())
        _build("contradoc", self.root / "b", sample, development=False, side="holdout",
               assignment=assignment, **budget)
        record = _json(self.root / "b" / "parts.json")
        self.assertEqual([(d["cluster"], d["groups_from"]) for d in record["documents"]], [("101", "assignment")])
        self.assertEqual(record["assignment_sha256"], hashlib.sha256(assignment.read_bytes()).hexdigest())
        _build("contradoc", self.root / "c", sample)
        self.assertEqual(_json(self.root / "c" / "parts.json")["documents"][0]["cluster"], "102")
        with self.assertRaisesRegex(ValueError, "not on the declared side development"):
            _build("contradoc", self.root / "d", sample, development=False, side="development",
                   assignment=assignment, **budget)
        with self.assertRaisesRegex(ValueError, "needs --assignment"):
            _build("contradoc", self.root / "e", sample, development=False, side="holdout", **budget)

    def test_contradoc_reads_the_split_file_b_dev_wrote(self):
        # B-dev froze the groups with its own implementation of section 1, in the shape
        # {"assignments": {unique id: {"group", "side"}}}. The build reads it as it reads the
        # adapter's own `split --out` file, and refuses a side that is not the hash rule on
        # the group key.
        rows = _adapter("contradoc").split_rows(_adapter("contradoc").read_source(
            _fixture("contradoc", "synthetic_items.json")))
        frozen = {"benchmark": "contradoc", "assignments": {
            r["source_document_id"]: {"group": r["split_key"], "side": r["side"]} for r in rows}}
        assignment = self.root / "bdev_split.json"
        assignment.write_text(json.dumps(frozen), encoding="utf-8")
        records = _json(_fixture("contradoc", "synthetic_items.json"))
        sample = self.root / "sample.json"
        sample.write_text(json.dumps({"neg": {"102": records["neg"]["102"]}}), encoding="utf-8")
        side = _independent_side("101")
        budget = dict(max_context=5000, output_allowance=10, token_counter=WordCounter())
        _build("contradoc", self.root / "b", sample, development=False, side=side,
               assignment=assignment, **budget)
        record = _json(self.root / "b" / "parts.json")
        self.assertEqual([(d["cluster"], d["side"], d["groups_from"]) for d in record["documents"]],
                         [("101", side, "assignment")])
        frozen["assignments"]["102"]["side"] = "holdout" if side == "development" else "development"
        assignment.write_text(json.dumps(frozen), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not the hash rule on their group key: 102"):
            _build("contradoc", self.root / "c", sample, development=False, side=side,
                   assignment=assignment, **budget)

    def test_contractnli_official_split(self):
        # The dev split is development, the test split the holdout pool: the side is the
        # one declared for the file, never a hash, and every agreement carries it.
        adapter = _adapter("contractnli")
        data = adapter.read_source(_fixture("contractnli", "synthetic_items.json"))
        for side in ("development", "holdout"):
            args = type("A", (), {"official": side})()
            self.assertEqual({r["side"] for r in adapter.split_rows(data, args)}, {side})
            budget = dict(max_context=5000, output_allowance=10, token_counter=WordCounter())
            _build("contractnli", self.root / side, development=False, side=side, **budget)
            record = _json(self.root / side / "parts.json")
            self.assertEqual({d["side"] for d in record["documents"]}, {side})
            self.assertEqual(sorted(d["split_key"] for d in record["documents"]), ["7101", "7102"])
        with self.assertRaisesRegex(ValueError, "required for ContractNLI"):
            adapter.split_rows(data, type("A", (), {"official": None})())

    def test_findver_official_split_drops_testmini_reports(self):
        adapter = _adapter("findver")
        records = adapter.read_source(_source("findver"))
        mini = self.root / "mini.json"
        mini.write_text(json.dumps([records[0]]), encoding="utf-8")
        args = type("A", (), {"official": "holdout", "testmini": str(mini)})()
        rows = {r["source_document_id"]: r["side"] for r in adapter.split_rows(records, args)}
        self.assertEqual(rows, {"SYNA-2024-01-31_10-K.json": "removed_overlap",
                                "SYNB-WT-2024-02-29_10-Q.json": "holdout"})


# ---------------------------------------------------------------------------
# opaque ids


class OpaqueChecks(_Case):
    def test_opaque_ids_leak_no_source_id(self):
        for name in NAMES:
            _build(name, self.root / name)
            items = _json(self.root / name / "items.json")["items"]
            sources = set()
            for item in items:
                self.assertEqual(item["item_id"], hashlib.sha256(
                    ("item:%s:%s" % (name, item["source_item_id"])).encode("utf-8")).hexdigest()[:12])
                self.assertEqual(item["document_id"], hashlib.sha256(
                    ("document:%s:%s" % (name, item["source_document_id"])).encode("utf-8")).hexdigest()[:12])
                sources.update({str(item["source_item_id"]), str(item["source_document_id"])})
            if name == "cuad":
                sources.update(e["title"] for e in _json(_source(name))["data"])
            if name == "scitab":
                sources.update(r[k] for r in _json(_source(name))
                               for k in ("paper_id", "paper"))
            if name == "contractnli":
                sources.update(d["file_name"] for d in _json(_source(name))["documents"])
            patterns = [re.compile(r"(?<![0-9A-Za-z])" + re.escape(s) + r"(?![0-9A-Za-z])") for s in sources]
            bundles = [p for p in (self.root / name).iterdir() if p.is_dir()]
            self.assertEqual(sorted(p.name for p in bundles), sorted({i["document_id"] for i in items}))
            for folder in bundles:
                for path, data in _files(folder).items():
                    text = data.decode("utf-8")
                    for pattern in patterns:
                        self.assertIsNone(pattern.search(text), "%s: source id %s in %s/%s"
                                          % (name, pattern.pattern, folder.name, path))


# ---------------------------------------------------------------------------
# structure (a structural reading of input-format-v1-draft, written here on its own)


_HEADING = re.compile(r"^(#{1,6}) (.*)$")
_RULE_HEADING = re.compile(r"^## (CONV-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*) ([A-Za-z ]+) \[required\] \[conformance\]$")


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "unit"


class StructureChecks(_Case):
    def _document(self, folder, doc_id, record):
        text = (folder / "context" / (doc_id + ".md")).read_text(encoding="utf-8")
        lines = text.split("\n")
        self.assertEqual(lines[0], "# D-" + doc_id)
        headings, label_lines, position = [], [], 0
        for i, line in enumerate(lines[1:], start=1):
            if line.lstrip(" \t").startswith("#") and not _HEADING.match(line):
                self.fail("a line starting with # that is no unit heading: " + line)
            m = _HEADING.match(line)
            if m:
                self.assertEqual(len(m.group(1)), 2, "a unit heading is level 2: " + line)
                position += 1
                self.assertEqual(m.group(2), "P-%05d" % position)
                headings.append("u%02d-%s" % (position, _slug(m.group(2))))
                follow = [l for l in lines[i + 1:] if l.strip()]
                label_lines.append(follow[0] if follow else "")
        self.assertEqual(headings, [p["unit_id"] for p in record["parts"]], doc_id)
        for label in label_lines:
            self.assertEqual(label, "Passage: part")
            self.assertIsNone(re.search(r"\d", label.split(":", 1)[1]), "a digit in a label value")
        return headings

    def _rules(self, folder):
        lines = (folder / "conventions" / "rules.md").read_text(encoding="utf-8").split("\n")
        self.assertEqual(lines[:2], ["# Review rules", ""])
        rules, i = [], 2
        while i < len(lines) and lines[i] != "":
            m = _RULE_HEADING.match(lines[i])
            self.assertIsNotNone(m, "rule heading: " + lines[i])
            self.assertEqual(lines[i + 1], "")
            self.assertTrue(lines[i + 2] and not re.match(r"^\s*([-*+]|\d+[.)])\s", lines[i + 2]))
            self.assertGreaterEqual(len(lines[i + 2]), 16)
            self.assertEqual(lines[i + 3], "")
            self.assertNotRegex(lines[i], r"\[(scope|requires|unless)\s*:")
            rules.append(m.group(1))
            i += 4
        self.assertEqual(lines[i:], [""], "nothing after the last rule")
        self.assertEqual(rules, sorted(rules), "rules in rule-id order")
        return rules

    def _shimmer_splits_the_same_way(self, records_by_name):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import pairing_map
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        for name, records in records_by_name.items():
            for doc_id, record in records.items():
                text = (self.root / name / doc_id / "context" / (doc_id + ".md")).read_text(encoding="utf-8")
                units = pairing_map.split_units(text, document_id=doc_id)
                self.assertEqual([u["unit_id"] for u in units], [p["unit_id"] for p in record["parts"]],
                                 "%s %s: Shimmer's splitter" % (name, doc_id))
        c = _common()
        text = c["bundle"].render_document("x", ["Word number %s." % w for w in ("one",) * 102])
        units = [u["unit_id"] for u in pairing_map.split_units(text, document_id="x")]
        self.assertEqual(units[98:101], ["u99-p-00099", "u100-p-00100", "u101-p-00101"])
        self.assertEqual(units, [c["bundle"].unit_id(k) for k in range(1, 103)])

    def test_bundles_follow_the_input_format(self):
        records_by_name = {}
        for name in NAMES:
            _build(name, self.root / name)
            items = _json(self.root / name / "items.json")["items"]
            records = {d["document_id"]: d for d in _json(self.root / name / "parts.json")["documents"]}
            records_by_name[name] = records
            for doc_id, record in records.items():
                folder = self.root / name / doc_id
                self.assertEqual(sorted(p.name for p in (folder / "context").iterdir()),
                                 sorted([doc_id + ".md", "_review_targets.json"]))
                self.assertEqual(_json(folder / "context" / "_review_targets.json"),
                                 {"targets": [doc_id + ".md"], "grounding": [], "prior": [],
                                  "source": "operator", "resolved_at": ""})
                self.assertEqual([p.name for p in (folder / "conventions").iterdir()], ["rules.md"])
                units = self._document(folder, doc_id, record)
                rules = self._rules(folder)
                mine = [i["rule_id"] for i in items if i["document_id"] == doc_id]
                self.assertEqual(sorted(rules), sorted(mine), "%s: one rule per item" % name)
                self.assertEqual(len(set(rules)), len(rules))
                answer = _json(folder / "answer_key.json")
                for key in ("document", "task_given_to_the_pipeline", "twin_of", "planted", "clean"):
                    self.assertIn(key, answer)
                self.assertEqual(answer["document"], doc_id + ".md")
                self.assertEqual(sorted(a["item_id"] for a in answer["items"]),
                                 sorted(i["item_id"] for i in items if i["document_id"] == doc_id))
                if name == "scitab":
                    self.assertEqual(len(units), 1)
                if name == "findver":
                    indices = [p["source"]["context_index"] for p in record["parts"]]
                    self.assertEqual(indices, list(range(len(indices))))
        self._shimmer_splits_the_same_way(records_by_name)
        # the escaped hash line and the escaped cell, read back as written
        _build("scitab", self.root / "again")
        texts = [p.read_text(encoding="utf-8") for p in (self.root / "again").rglob("*.md")
                 if p.parent.name == "context"]
        self.assertTrue(any("\\# Table 2: Model sizes" in t and "| Model | Size \\| layers |" in t
                            for t in texts))


# ---------------------------------------------------------------------------
# mapping


def _materialise(cases, root):
    runs, b1 = root / "runs", root / "b1"
    for doc, run in cases["runs"].items():
        folder = runs / doc
        folder.mkdir(parents=True)
        if run.get("completion") is not None:
            (folder / "audit").mkdir()
            (folder / "audit" / "run_completion.json").write_text(json.dumps(run["completion"]), encoding="utf-8")
        deliverables = folder / "deliverables" / doc
        deliverables.mkdir(parents=True)
        if run.get("review_data") is not None:
            (deliverables / "review_data.json").write_text(json.dumps(run["review_data"]), encoding="utf-8")
        for file_name, text in (run.get("deliverables") or {}).items():
            (deliverables / file_name).write_text(text, encoding="utf-8")
        if run.get("pairing_map") is not None:
            (folder / "audit").mkdir(exist_ok=True)
            (folder / "audit" / "pairing_map.json").write_text(json.dumps(run["pairing_map"]), encoding="utf-8")
    for doc, labels in (cases.get("b1") or {}).items():
        folder = b1 / doc / "labels"
        folder.mkdir(parents=True)
        for item_id, record in labels.items():
            (folder / (item_id + ".json")).write_text(json.dumps(record), encoding="utf-8")
    items = root / "items.json"
    items.write_text(json.dumps({"items": cases["items"]}), encoding="utf-8")
    return items, runs, b1


class MappingChecks(_Case):
    def _compare(self, name, label, result, expected):
        got = {r["item_id"]: [r["class"], r["label"], r["basis"]] for r in result["labels"]}
        self.assertEqual(got, expected, "%s %s" % (name, label))

    def test_mapping_gives_the_expected_label_for_every_case(self):
        c = _common()
        for name in NAMES:
            adapter = _adapter(name)
            cases = _json(_fixture(name, "mapping_cases.json"))
            items, runs, b1 = _materialise(cases, self.root / name)
            arms = {"B2": c["cli"].label(adapter, items, "B2", runs),
                    "B1": c["cli"].label(adapter, items, "B1", b1)}
            for arm in ("B3", "B4"):
                with self.assertRaises(c["mapping"].Refused, msg=name + " " + arm):
                    c["cli"].label(adapter, items, arm, runs)
            for arm, labels in arms.items():
                for variant in ("", " S-1", " S-2"):
                    key = arm + variant
                    if key in cases["expected"]:
                        self._compare(name, key, labels[variant.strip() or "primary"], cases["expected"][key])
                for item_id, detail in cases.get("expected_detail", {}).get(arm, {}).items():
                    row = next(r for r in labels["primary"]["labels"] if r["item_id"] == item_id)
                    for field, value in detail.items():
                        self.assertEqual(row[field], value, "%s %s %s %s" % (name, arm, item_id, field))
                for field, value in cases.get("expected_counts", {}).get(arm, {}).items():
                    self.assertEqual(labels["primary"]["counts"][field], value, "%s %s count %s" % (name, arm, field))
                for doc, detail in cases.get("expected_documents", {}).get(arm, {}).items():
                    row = next(d for d in labels["primary"]["documents"] if d["document_id"] == doc)
                    for field, value in detail.items():
                        got = row["unattached"]["count"] if field == "unattached" else (
                            row["unattached"]["per_deliverable"] if field == "per_deliverable" else row[field])
                        self.assertEqual(got, value, "%s %s %s %s" % (name, arm, doc, field))
            b0 = c["cli"].label(adapter, items, "B0")["primary"]
            self.assertEqual({r["class"] for r in b0["labels"]}, {"CLEAR"}, name + " B0")
        # an adapter fault makes the label command exit 3 (FinDVer: no typed-record key)
        cases = _json(_fixture("findver", "mapping_cases.json"))
        items, runs, _ = _materialise(cases, self.root / "exit")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = c["cli"].main(_adapter("findver"), ["label", "--items", str(items), "--arm", "B2",
                                                       "--runs", str(runs), "--out", str(self.root / "l.json")])
            refused = c["cli"].main(_adapter("findver"), ["label", "--items", str(items), "--arm", "B3",
                                                          "--runs", str(runs), "--out", str(self.root / "m.json")])
        self.assertEqual((code, refused), (3, 4))
        self.assertFalse((self.root / "m.json").exists(), "a refused arm writes no labels")


# ---------------------------------------------------------------------------
# metrics


class MetricChecks(_Case):
    def test_tiny_confusion_examples_equal_the_hand_computation(self):
        A = "ABSTAIN"
        # ContraDoc. (pred, gold): TP, FN by ABSTAIN, FN, FP, TN, ABSTAIN on clear.
        pairs = [("contradictory", "contradictory"), (A, "contradictory"),
                 ("not contradictory", "contradictory"), ("contradictory", "not contradictory"),
                 ("not contradictory", "not contradictory"), (A, "not contradictory")]
        rows = [{"item_id": str(i), "class": "", "arm": "B3", "cited_unit_ids": []} for i in range(6)]
        answers = {str(i): {"gold": g} for i, (_p, g) in enumerate(pairs)}
        h = _adapter("contradoc").headline(pairs, rows, answers, lambda d, u: "")
        # accuracy 2/6; P = 1/(1+1); R = 1/3; F1 = 2 * 1/2 * 1/3 / (1/2 + 1/3) = 0.4
        self.assertAlmostEqual(h["accuracy"]["accuracy"], 2 / 6)
        self.assertAlmostEqual(h["contradictory"]["precision"], 0.5)
        self.assertAlmostEqual(h["contradictory"]["recall"], 1 / 3)
        self.assertAlmostEqual(h["contradictory"]["f1"], 0.4)
        # SciTab. supports: tp 2 fp 0 fn 1 -> F1 0.8; refutes: tp 1 fp 1 fn 1 -> 0.5;
        # not enough info: tp 1 fp 1 fn 1 (ABSTAIN) -> 0.5; macro (0.8 + 0.5 + 0.5) / 3 = 0.6
        s, r, n = "supports", "refutes", "not enough info"
        h = _adapter("scitab").headline([(s, s), (s, s), (r, s), (n, r), (r, r), (A, n), (n, n)])
        self.assertAlmostEqual(h["macro_f1"], 0.6)
        self.assertEqual(h["confusion"][n][A], 1)
        self.assertEqual(h["confusion"][s][r], 1)
        # CUAD. absent: tp 1 fp 1 fn 1 -> 0.5; present: tp 2 fp 1 fn 2 -> P 2/3, R 1/2,
        # F1 4/7; pooled macro (1/2 + 4/7) / 2 = 15/28. Category A (first three):
        # absent F1 2/3, present F1 2/3, macro 2/3. Category B: absent tp 0 fp 1 fn 0 ->
        # 0 (recall and F1 zero denominators), present tp 1 fp 0 fn 2 -> 1/2; macro 1/4.
        # Mean over categories (2/3 + 1/4) / 2 = 11/24. Zero denominators, counted as
        # scikit-learn counts them: only category B's absent recall (tp + fn = 0); its F1
        # denominator 2tp + fp + fn = 1 is not zero.
        ab, pr = "absent", "present"
        pairs = [(ab, ab), (pr, ab), (pr, pr), (pr, pr), (A, pr), (ab, pr)]
        rows = [{"item_id": str(i)} for i in range(6)]
        answers = {str(i): {"category_row": "cuad-01" if i < 3 else "cuad-02"} for i in range(6)}
        h = _adapter("cuad").headline(pairs, rows, answers)
        self.assertAlmostEqual(h["macro_f1"], 15 / 28)
        self.assertAlmostEqual(h["present"]["precision"], 2 / 3)
        self.assertAlmostEqual(h["present"]["recall"], 0.5)
        self.assertAlmostEqual(h["secondary_mean_category_macro_f1"], 11 / 24)
        self.assertEqual(h["secondary_zero_denominators"], 1)
        # Zero division: no item predicted or gold absent -> every absent ratio is 0, three
        # zero denominators; macro (1 + 0) / 2.
        h = _adapter("cuad").headline([(pr, pr)], [{"item_id": "z"}], {"z": {"category_row": "cuad-01"}})
        self.assertAlmostEqual(h["macro_f1"], 0.5)
        self.assertEqual(h["zero_denominators"], 3)
        # FinDVer. accuracy 2/4 (ABSTAIN wrong), coverage 3/4, accuracy on answered 2/3;
        # ie (FDV-IE) 1/2, numeric (FDV-MATH) 1/2 with coverage 1/2, by the stored spellings.
        e, f = "entailed", "refuted"
        pairs = [(f, f), (e, f), (A, e), (e, e)]
        answers = {str(i): {"subset": "ie" if i < 2 else "numeric"} for i in range(4)}
        h = _adapter("findver").headline(pairs, [{"item_id": str(i)} for i in range(4)], answers)
        self.assertAlmostEqual(h["accuracy"]["accuracy"], 0.5)
        self.assertAlmostEqual(h["coverage"]["coverage"], 0.75)
        self.assertAlmostEqual(h["coverage"]["accuracy_on_answered"], 2 / 3)
        self.assertAlmostEqual(h["per_subset"]["numeric"]["accuracy"]["accuracy"], 0.5)
        self.assertAlmostEqual(h["per_subset"]["numeric"]["coverage"]["coverage"], 0.5)
        # ContractNLI. (pred, gold): 3 of 6 correct (ABSTAIN wrong): accuracy 1/2.
        # contradiction: tp 1, fp 1, fn 1 -> F1 2/(2+1+1) = 1/2; entailment: tp 1, fp 1,
        # fn 2 (ABSTAIN and contradiction) -> P 1/2, R 1/3, F1 2/(2+1+2) = 2/5.
        c, e, n = "contradiction", "entailment", "not mentioned"
        h = _adapter("contractnli").headline([(c, c), (e, c), (n, n), (A, e), (e, e), (c, e)])
        self.assertAlmostEqual(h["accuracy"]["accuracy"], 0.5)
        self.assertAlmostEqual(h["contradiction"]["f1"], 0.5)
        self.assertAlmostEqual(h["entailment"]["recall"], 1 / 3)
        self.assertAlmostEqual(h["entailment"]["f1"], 0.4)
        self.assertEqual(h["confusion"][e][A], 1)

    def test_end_to_end_score_on_a_built_bundle(self):
        c = _common()
        adapter = _adapter("contradoc")
        _build("contradoc", self.root / "b")
        item = {s: c["ids"].opaque_item_id("contradoc", s) for s in (101, 102, 205, 409)}
        doc = {s: c["ids"].opaque_document_id("contradoc", s) for s in (101, 102, 205, 409)}

        def row(source, cls, cited):
            return {"item_id": item[source], "document_id": doc[source], "rule_id": "CONV-CDOC-01",
                    "arm": "B3", "class": cls, "label": adapter.SPEC.label(cls), "basis": "fixture",
                    "cited_unit_ids": cited, "layer": "judged", "evidence": None, "faults": []}
        labels = {"arm": "B3", "analysis": "primary", "documents": [],
                  "counts": {"refusals": 0, "run_failure_documents": 0},
                  "labels": [row(101, "FLAG", ["U03-P-00003"]), row(102, "FLAG", ["u01-p-00001"]),
                             row(205, "FLAG", ["u01-p-00001"]), row(409, "CLEAR", [])]}
        result = c["metrics"].score_arm(adapter.SPEC, labels, self.root / "b", adapter.headline)
        # 101 and 205 are contradictory, 102 and 409 are not: 3 of 4 correct; 101 cites
        # the unit holding its evidence, 205 cites a unit holding neither its evidence
        # nor its reference: location recall 1/2; 102 is the one item-level false positive.
        self.assertAlmostEqual(result["headline"]["accuracy"]["accuracy"], 0.75)
        self.assertAlmostEqual(result["location"]["value"], 0.5)
        self.assertEqual(result["false_positives"]["item_level"], 1)
        self.assertAlmostEqual(result["headline"]["evidence_containment"]["value"], 0.5)
        self.assertEqual((result["documents"], result["clusters"], result["decisions"]), (4, 3, 4))
        self.assertIn("Not comparable", result["comparability"])
        # B1: 101's evidence quotes two sentences from two different units; one of them lies
        # in an evidence unit, so it is located. 205 quotes a sentence in no evidence unit.
        b1 = dict(labels, arm="B1", labels=[
            dict(row(101, "FLAG", []), arm="B1", evidence="The harbour bridge opened in spring. "
                 "The   bridge has never opened to traffic."),
            dict(row(205, "FLAG", []), arm="B1", evidence="A small orchard sits by the river."),
            dict(row(102, "CLEAR", []), arm="B1"), dict(row(409, "CLEAR", []), arm="B1")])
        result = c["metrics"].score_arm(adapter.SPEC, b1, self.root / "b", adapter.headline)
        self.assertAlmostEqual(result["location"]["value"], 0.5)
        # A gold item of a labelled document with no label is an error, never skipped:
        # SciTab's table syn-tab-1 carries two claims and only one is labelled.
        scitab = _adapter("scitab")
        _build("scitab", self.root / "s")
        table = c["ids"].opaque_document_id("scitab", "syn-tab-1")
        one = {"item_id": c["ids"].opaque_item_id("scitab", 9001), "document_id": table,
               "rule_id": "x", "arm": "B3", "class": "CLEAR", "label": "supports", "basis": "fixture",
               "cited_unit_ids": [], "layer": "", "evidence": None, "faults": []}
        short = dict(labels, labels=[one])
        with self.assertRaisesRegex(ValueError, "have no label"):
            c["metrics"].score_arm(scitab.SPEC, short, self.root / "s", scitab.headline)


class AbsentChecks(unittest.TestCase):
    def test_absent_folder_skips(self):
        with tempfile.TemporaryDirectory(prefix="adapter_absent_") as tmp:
            self.assertTrue(_absent(Path(tmp) / "benchmark" / "adapters"))


# ---------------------------------------------------------------------------
# verdicts


def _run(case):
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(case).run(result)
    return result


def _verdict(results, what):
    failures = sum(len(r.failures) + len(r.errors) for r in results)
    if failures:
        test, trace = next((r.failures + r.errors)[0] for r in results if r.failures or r.errors)
        lines = trace.strip().splitlines()
        cause = next((l for l in reversed(lines) if l.split(":", 1)[0].endswith(("Error", "Exception"))),
                     lines[-1])
        return ("FAIL", "%d failures/errors; first: %s: %s" % (
            failures, test.id().rsplit(".", 1)[-1], cause.strip()[:300]))
    if _absent():
        return ("SKIP", ABSENT_REASON)
    ran = sum(r.testsRun - len(r.skipped) for r in results)
    return ("PASS", "%d cases: %s" % (ran, what))


GROUPS = {
    "build": (BuildChecks, "two builds of every adapter are byte-identical; the budget is per "
                           "document from its own conventions; the cut keeps whole parts with the "
                           "hand-counted cut line and evidence read on the kept text; no budget, "
                           "an off-side document or a testmini report is refused; empty documents "
                           "are skipped and listed; one word rule counts every part, band and cut "
                           "line (table markup not a word); each release's schema is read as the "
                           "B-dev development items showed it, ContractNLI one part per span of its "
                           "own span list"),
    "split": (SplitChecks, "the split key is the documented document key, its SHA-256 mod 5 "
                           "recomputed independently, every item of a document on its side, "
                           "ContraDoc groups read from the frozen assignment, FinDVer's testmini "
                           "reports dropped from the holdout, ContractNLI on its declared official side"),
    "opaque": (OpaqueChecks, "opaque ids are SHA-256 prefixes of the documented strings and no "
                             "source id appears in any bundle file"),
    "structure": (StructureChecks, "every bundle reads back as the input format: expected unit "
                                   "ids, `Passage: part` with no digit, escaped # lines, one "
                                   "rule per item, the target-only manifest, and Shimmer's own splitter "
                                   "agrees, above 99 units too"),
    "mapping": (MappingChecks, "the section 5.1 and 5.2 mapping gives the hand-written expected "
                               "label for every run-output case (completion record, supersession, "
                               "refusal, CUAD missing_field), for B2, B1 and B0 with S-1 and S-2; "
                               "B3 and B4 refused while the typed-record key is unsettled"),
    "metrics": (MetricChecks, "every benchmark's metric equals the hand computation on a tiny "
                              "confusion example, and an end-to-end score (location for B3 and B1, "
                              "false positives, unlabelled gold refused) matches by hand"),
}


def check_group(name):
    case, what = GROUPS[name]
    return _verdict([_run(case), _run(AbsentChecks)], what)


def check():
    results = [_run(case) for case, _ in GROUPS.values()] + [_run(AbsentChecks)]
    return _verdict(results, "the five benchmark adapters build byte-identical bundles that read "
                             "back as the input format and as Shimmer splits them, cut per document, "
                             "split by document, leak no source id, map synthetic run outputs to "
                             "the expected labels (B2, B1, B0, S-1, S-2; B3 refused until the "
                             "typed-record key is settled) and score tiny examples as computed by hand")


if __name__ == "__main__":
    names = sys.argv[1:] or list(GROUPS)
    for group in names:
        print(group, check_group(group))
    if not sys.argv[1:]:
        print("all", check())
